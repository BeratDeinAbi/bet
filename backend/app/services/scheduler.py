"""
Einfacher Daily-Scheduler — startet einen Daemon-Thread, der zur
nächsten 04:00 UTC aufwacht und den Self-Improve-Zyklus läuft:

  1. Heutige Spiele aktualisieren (kann inzwischen FINISHED haben)
  2. Outcomes evaluieren
  3. Kalibrierungs-Kurven neu fitten
  4. Modelle re-trainieren (nutzt jetzt mehr finished games)
  5. Cache neu laden — neue Predictions ab jetzt kalibriert

Bewusst kein APScheduler oder Celery — der Job läuft 1× täglich, die
Komplexität ist nicht gerechtfertigt.  Bei Server-Restart wird der Job
beim nächsten 04:00 wieder ausgeführt.  Manueller Trigger über
``POST /admin/daily-cycle`` jederzeit möglich.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, time, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()


def run_daily_cycle() -> dict:
    """Führt den vollen Self-Improve-Zyklus synchron aus.  Wird vom
    Scheduler-Thread und vom manuellen Endpoint genutzt."""
    from app.db.database import SessionLocal
    from app.services.evaluation import (
        evaluate_finished_matches, compute_calibration, reload_calibration_cache,
    )
    from app.services.ingestion import ingest_today_matches

    started = datetime.now(timezone.utc)
    result: dict = {"started": started.isoformat()}
    db = SessionLocal()
    try:
        # 1. heutige + neue Endergebnisse holen, damit FINISHED-Status frisch ist
        try:
            n_today = ingest_today_matches(db)
            result["matches_refreshed"] = n_today
        except Exception as e:
            logger.warning(f"daily ingest failed: {e}")
            result["ingest_error"] = str(e)

        # 2. Outcomes evaluieren
        n_eval = evaluate_finished_matches(db)
        result["new_outcomes_evaluated"] = n_eval

        # 3. Kalibrierung
        n_bins = compute_calibration(db, days=90)
        result["calibration_bins_written"] = n_bins
        reload_calibration_cache(db)

        # 4. Modelle re-trainieren (parallel)
        try:
            from concurrent.futures import ThreadPoolExecutor
            from ml.training.train_models import (
                train_football_models, train_hockey_models,
                train_basketball_models, train_baseball_models,
            )
            with ThreadPoolExecutor(max_workers=4) as pool:
                futs = [
                    pool.submit(train_football_models),
                    pool.submit(train_hockey_models),
                    pool.submit(train_basketball_models),
                    pool.submit(train_baseball_models),
                ]
                for f in futs:
                    f.result()
            result["models_retrained"] = True
        except Exception as e:
            logger.warning(f"daily retrain failed: {e}")
            result["retrain_error"] = str(e)

        # 5. Modell-Cache invalidieren, damit neue Predictions die neuen
        #    .pkl-Dateien sofort sehen
        from app.services import prediction as pred_svc
        pred_svc._model_cache.clear()
    finally:
        db.close()

    duration = (datetime.now(timezone.utc) - started).total_seconds()
    result["duration_seconds"] = round(duration, 1)
    logger.info(f"Daily cycle finished in {duration:.1f}s: {result}")
    return result


def _seconds_until_next(target_hour: int = 4, target_minute: int = 0) -> float:
    """Sekunden bis zum nächsten 04:00 UTC."""
    now = datetime.now(timezone.utc)
    target = now.replace(hour=target_hour, minute=target_minute,
                         second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return (target - now).total_seconds()


def _scheduler_loop():
    logger.info("Daily scheduler thread started")
    while not _stop_event.is_set():
        wait_s = _seconds_until_next(4, 0)
        logger.info(f"Daily cycle scheduled in {wait_s/3600:.1f}h")
        # In 60-Sekunden-Schritten warten, damit ein stop_event schnell greift
        elapsed = 0.0
        while elapsed < wait_s and not _stop_event.is_set():
            sleep_for = min(60.0, wait_s - elapsed)
            if _stop_event.wait(sleep_for):
                return
            elapsed += sleep_for
        if _stop_event.is_set():
            return
        try:
            run_daily_cycle()
        except Exception as e:
            logger.exception(f"daily cycle crash: {e}")


def start_scheduler():
    """Startet den Daemon-Thread.  Kein Restart wenn schon läuft."""
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_scheduler_loop, name="daily-scheduler",
                               daemon=True)
    _thread.start()


def stop_scheduler():
    _stop_event.set()

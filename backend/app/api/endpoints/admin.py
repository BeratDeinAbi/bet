import sys, os
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.ingestion import ingest_today_matches, ingest_historical_matches
from app.services.prediction import predict_today

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/refresh")
def refresh_matches(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Fetch today's matches AND backfill the last 3 days of finished
    games + auto-evaluate so the Modellgüte-page reflects yesterday.

    Bestehende Predictions für noch nicht gestartete Spiele werden
    vorher gelöscht, damit Schema-Änderungen sofort wirken.
    """
    from app.db.models import Match, Prediction
    from app.services.ingestion import backfill_recent_results
    from app.services.evaluation import (
        evaluate_finished_matches, compute_calibration, reload_calibration_cache,
    )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    stale = (
        db.query(Prediction)
        .join(Match, Prediction.match_id == Match.id)
        .filter(Match.kickoff_time > now)
        .all()
    )
    for p in stale:
        db.delete(p)
    db.commit()

    def _run(db):
        # 1) Past 3 Tage Status-Update (Vortages-Ergebnisse holen)
        backfill_recent_results(db, days_back=3)
        # 2) Heutige Spiele holen
        ingest_today_matches(db)
        # 3) Bookmaker-Quoten holen (z. B. Betano via The-Odds-API).
        #    Muss VOR predict_today laufen, damit der RecommendedPick-
        #    Service die Quoten bei der Pick-Selektion berücksichtigt.
        from app.services.ingestion import ingest_odds
        ingest_odds(db)
        # 4) Predictions für heute generieren (inkl. RecommendedPick)
        predict_today(db)
        # 5) Outcomes evaluieren — direkt damit Modellgüte aktuell ist
        evaluate_finished_matches(db)
        compute_calibration(db)
        reload_calibration_cache(db)
    background_tasks.add_task(_run, db)
    return {
        "status": "refresh started — incl. 3-day backfill + auto-evaluation",
        "stale_predictions_cleared": len(stale),
    }


@router.post("/train")
def train_models(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ingest historical data (ESPN last 30 weeks) and retrain all models."""
    def _run(db):
        ingest_historical_matches(db)
        from ml.training.train_models import (
            train_football_models, train_hockey_models,
            train_basketball_models, train_baseball_models,
        )
        train_football_models()
        train_hockey_models()
        train_basketball_models()
        train_baseball_models()
    background_tasks.add_task(_run, db)
    return {"status": "training started"}


@router.post("/daily-cycle")
def trigger_daily_cycle():
    """Manueller Trigger des täglichen Self-Improve-Zyklus:
    Outcomes evaluieren → Kalibrierung neu fitten → Modelle re-trainieren.
    Läuft sonst automatisch täglich um 04:00 UTC."""
    from app.services.scheduler import run_daily_cycle
    return run_daily_cycle()


@router.post("/evaluate")
def trigger_evaluation(db: Session = Depends(get_db)):
    """Nur die Evaluation laufen lassen (ohne Retrain) — für schnelles
    Auffüllen der Outcome-Tabelle nach einem History-Import."""
    from app.services.evaluation import (
        evaluate_finished_matches, compute_calibration, reload_calibration_cache,
    )
    n_eval = evaluate_finished_matches(db)
    n_bins = compute_calibration(db)
    reload_calibration_cache(db)
    return {"new_outcomes": n_eval, "calibration_bins": n_bins}


@router.post("/backfill-recommended")
def backfill_recommended_picks(db: Session = Depends(get_db)):
    """Erzeugt Recommended Picks für alle bestehenden Predictions die
    noch keinen Pick haben.  Einmaliger Catch-Up nach Schema-Update."""
    from app.db.models import Match, Prediction, RecommendedPick
    from app.services.recommended import (
        persist_recommended_pick, evaluate_recommended_picks,
    )

    existing_pids = {
        row[0] for row in db.query(RecommendedPick.prediction_id).all()
    }
    preds = (
        db.query(Prediction, Match)
        .join(Match, Prediction.match_id == Match.id)
        .all()
    )
    n_created = 0
    n_skipped_no_pick = 0
    for pred, match in preds:
        if pred.id in existing_pids:
            continue
        rp = persist_recommended_pick(db, match, pred)
        if rp is None:
            n_skipped_no_pick += 1
        else:
            n_created += 1
    db.commit()
    n_eval = evaluate_recommended_picks(db)
    return {
        "created": n_created,
        "no_qualifying_pick": n_skipped_no_pick,
        "evaluated_after_backfill": n_eval,
    }


@router.post("/seed")
def seed_real_data(db: Session = Depends(get_db)):
    """
    Full pipeline with REAL data:
    1. Fetch historical results parallel from ESPN/NHL/MLB/OpenLigaDB
    2. Train all 4 sport models in parallel
    3. Fetch today's real matches
    4. Generate predictions

    Speed-up vs. v1: provider fetches und Trainings laufen jeweils
    parallel.  Auf einer typischen Verbindung: 60-90 s → 15-25 s.
    Ergebnis ist deterministisch identisch — gleiche Modelle, gleiche
    Predictions.
    """
    from concurrent.futures import ThreadPoolExecutor

    # Step 1: historical real data for training (intern bereits parallel)
    hist = ingest_historical_matches(db)

    # Step 2: train models — alle 4 Sportarten parallel.  Trainings sind
    # CPU-bound (numpy/scipy), aber numpy gibt während BLAS-Calls die GIL
    # frei → echter Parallelismus möglich.
    train_warning = None
    try:
        from ml.training.train_models import (
            train_football_models, train_hockey_models,
            train_basketball_models, train_baseball_models,
        )
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [
                pool.submit(train_football_models),
                pool.submit(train_hockey_models),
                pool.submit(train_basketball_models),
                pool.submit(train_baseball_models),
            ]
            for f in futures:
                f.result()  # propagiert Fehler
    except Exception as e:
        train_warning = str(e)

    # Step 3: real today matches
    n = ingest_today_matches(db)

    # Step 3b: Bookmaker-Quoten (Betano via The-Odds-API).
    # Best-effort: wenn ODDS_API_KEY leer ist, skippt die Funktion.
    from app.services.ingestion import ingest_odds
    odds_n = ingest_odds(db)

    # Step 4: predictions (RecommendedPick liest ODDS_API-Quoten)
    p = predict_today(db)

    result = {
        "status": "ok",
        "data_source": "ESPN public API + NHL public API (no key required)",
        "historical_matches_for_training": hist,
        "matches_today": n,
        "odds_lines_fetched": odds_n,
        "predictions_generated": p,
    }
    if train_warning:
        result["warning"] = f"Model training: {train_warning} — using fallback Poisson"
    return result

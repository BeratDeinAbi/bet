"""
Sports Prediction Dashboard — FastAPI Backend
Start: uvicorn main:app --reload --port 8000
"""
import sys
import os
import logging

# Make ml/ importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.database import init_db
from app.api.endpoints import matches, predictions, admin, backtests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Local sports prediction dashboard for football and NHL",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(admin.router)
app.include_router(backtests.router)


@app.on_event("startup")
async def on_startup():
    logger.info("Initializing database...")
    init_db()

    # Competition-Zeilen für alle konfigurierten Ligen garantiert anlegen,
    # damit das Frontend-Dropdown immer alle Ligen zeigt — auch vor dem
    # ersten Seed-Klick.
    from app.db.database import SessionLocal
    from app.services.ingestion import COMPETITIONS, _ensure_competition
    db = SessionLocal()
    try:
        all_leagues = (
            list(settings.ACTIVE_FOOTBALL_LEAGUES)
            + list(settings.ACTIVE_HOCKEY_LEAGUES)
            + list(settings.ACTIVE_BASKETBALL_LEAGUES)
            + list(settings.ACTIVE_BASEBALL_LEAGUES)
        )
        for code in all_leagues:
            _ensure_competition(db, code)
        db.commit()
        logger.info(f"Competitions initialized: {all_leagues}")
    except Exception as e:
        logger.warning(f"Competition init warning: {e}")
    finally:
        db.close()

    # Kalibrierungs-Cache aus DB laden (falls vom letzten Run vorhanden)
    db = SessionLocal()
    try:
        from app.services.evaluation import reload_calibration_cache
        reload_calibration_cache(db)
    except Exception as e:
        logger.warning(f"Calibration cache load failed: {e}")
    finally:
        db.close()

    # Daily-Self-Improve-Scheduler starten (04:00 UTC)
    try:
        from app.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logger.warning(f"Scheduler start failed: {e}")

    # Catch-Up: Wenn die letzte Outcome-Evaluation mehr als 24h her ist
    # (oder noch nie lief), läuft der Daily-Cycle einmal direkt — sonst
    # entstehen Daten-Lücken wenn der Server zwischen den 04:00-Slots
    # gestartet/gestoppt wurde.
    try:
        import threading
        from datetime import datetime, timedelta, timezone
        from app.db.models import PredictionOutcome
        from app.db.database import SessionLocal as _SL
        with _SL() as _db:
            last = _db.query(PredictionOutcome).order_by(
                PredictionOutcome.evaluated_at.desc()
            ).first()
        threshold = datetime.now(timezone.utc) - timedelta(hours=24)
        needs_catchup = (
            last is None or
            last.evaluated_at is None or
            (last.evaluated_at.replace(tzinfo=timezone.utc) if last.evaluated_at.tzinfo is None else last.evaluated_at) < threshold
        )
        if needs_catchup:
            logger.info("Last evaluation >24h ago — running daily-cycle catch-up in background")
            from app.services.scheduler import run_daily_cycle
            threading.Thread(
                target=lambda: run_daily_cycle(),
                name="startup-catchup",
                daemon=True,
            ).start()
    except Exception as e:
        logger.warning(f"Startup catch-up check failed: {e}")

    logger.info(f"Database ready. Football provider: {settings.FOOTBALL_PROVIDER}")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "football_provider": settings.FOOTBALL_PROVIDER,
        "hockey_provider": settings.HOCKEY_PROVIDER,
        "mock_fallback": settings.USE_MOCK_FALLBACK,
    }

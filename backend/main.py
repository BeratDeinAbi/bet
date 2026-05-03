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
        )
        for code in all_leagues:
            _ensure_competition(db, code)
        db.commit()
        logger.info(f"Competitions initialized: {all_leagues}")
    except Exception as e:
        logger.warning(f"Competition init warning: {e}")
    finally:
        db.close()

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

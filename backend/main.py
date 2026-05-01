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

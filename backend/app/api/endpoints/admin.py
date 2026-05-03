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
    """Fetch today's real matches from ESPN/NHL API and generate predictions."""
    def _run(db):
        n = ingest_today_matches(db)
        p = predict_today(db)
        return n, p
    background_tasks.add_task(_run, db)
    return {"status": "refresh started — real data from ESPN + NHL API"}


@router.post("/train")
def train_models(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ingest historical data (ESPN last 30 weeks) and retrain all models."""
    def _run(db):
        ingest_historical_matches(db)
        from ml.training.train_models import (
            train_football_models, train_hockey_models, train_basketball_models,
        )
        train_football_models()
        train_hockey_models()
        train_basketball_models()
    background_tasks.add_task(_run, db)
    return {"status": "training started"}


@router.post("/seed")
def seed_real_data(db: Session = Depends(get_db)):
    """
    Full pipeline with REAL data:
    1. Fetch historical results from ESPN (last 30 weeks per league) + NHL
    2. Train Poisson/Elo/Ensemble models on real results
    3. Fetch today's real matches from ESPN + NHL
    4. Generate predictions for all today's matches
    """
    # Step 1: historical real data for training
    hist = ingest_historical_matches(db)

    # Step 2: train models
    train_warning = None
    try:
        from ml.training.train_models import (
            train_football_models, train_hockey_models, train_basketball_models,
        )
        train_football_models()
        train_hockey_models()
        train_basketball_models()
    except Exception as e:
        train_warning = str(e)

    # Step 3: real today matches
    n = ingest_today_matches(db)

    # Step 4: predictions
    p = predict_today(db)

    result = {
        "status": "ok",
        "data_source": "ESPN public API + NHL public API (no key required)",
        "historical_matches_for_training": hist,
        "matches_today": n,
        "predictions_generated": p,
    }
    if train_warning:
        result["warning"] = f"Model training: {train_warning} — using fallback Poisson"
    return result

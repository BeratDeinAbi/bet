from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.ingestion import ingest_today_matches, ingest_historical_matches
from app.services.prediction import predict_today

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/refresh")
def refresh_matches(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Fetch today's matches from providers and run predictions."""
    def _run(db):
        ingest_today_matches(db)
        predict_today(db)
    background_tasks.add_task(_run, db)
    return {"status": "refresh started"}


@router.post("/train")
def train_models(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Ingest historical data and retrain all models."""
    def _run(db):
        ingest_historical_matches(db)
        from ml.training.train_models import train_football_models, train_hockey_models
        train_football_models()
        train_hockey_models()
    background_tasks.add_task(_run, db)
    return {"status": "training started"}


@router.post("/seed")
def seed_demo_data(db: Session = Depends(get_db)):
    """
    Run full seed pipeline synchronously:
    1. Ingest historical mock data
    2. Train models
    3. Ingest today's matches
    4. Generate predictions
    """
    ingest_historical_matches(db)
    try:
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../"))
        from ml.training.train_models import train_football_models, train_hockey_models
        train_football_models()
        train_hockey_models()
    except Exception as e:
        return {"status": "partial", "warning": f"Model training failed: {e}", "note": "predictions will use fallback"}
    n = ingest_today_matches(db)
    p = predict_today(db)
    return {"status": "ok", "matches_ingested": n, "predictions_generated": p}

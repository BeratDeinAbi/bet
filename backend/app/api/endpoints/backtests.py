from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.schemas.prediction import BacktestSummary, ModelStatus
from app.db.models import ModelRun

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("/summary", response_model=List[BacktestSummary])
def get_backtest_summary(db: Session = Depends(get_db)):
    """Return backtesting results summary from latest model runs."""
    runs = db.query(ModelRun).filter(ModelRun.active == True).all()
    summaries = []
    for run in runs:
        metrics = run.metrics or {}
        for market, market_metrics in metrics.get("markets", {}).items():
            summaries.append(BacktestSummary(
                sport=run.sport,
                league=metrics.get("league"),
                market=market,
                mae=market_metrics.get("mae", 0.0),
                rmse=market_metrics.get("rmse", 0.0),
                brier_score=market_metrics.get("brier_score", 0.0),
                calibration_error=market_metrics.get("calibration_error", 0.0),
                sample_size=market_metrics.get("sample_size", 0),
                period=metrics.get("period", "2023-2024"),
            ))
    if not summaries:
        # Demo data when no models trained yet
        summaries = [
            BacktestSummary(sport="football", league="BL1", market="total_goals", mae=0.82,
                            rmse=1.14, brier_score=0.23, calibration_error=0.04, sample_size=306, period="2023-2024"),
            BacktestSummary(sport="football", league="PL", market="h1_goals", mae=0.61,
                            rmse=0.89, brier_score=0.21, calibration_error=0.03, sample_size=380, period="2023-2024"),
            BacktestSummary(sport="hockey", league="NHL", market="total_goals", mae=1.12,
                            rmse=1.54, brier_score=0.24, calibration_error=0.05, sample_size=500, period="2023-2024"),
        ]
    return summaries


@router.get("/models/status", response_model=List[ModelStatus])
def get_model_status(db: Session = Depends(get_db)):
    import os
    from app.core.config import settings
    statuses = []
    model_files = {
        "football_BL1": ("football", "FootballEnsemble"),
        "football_PL": ("football", "FootballEnsemble"),
        "football_PD": ("football", "FootballEnsemble"),
        "football_SSL": ("football", "FootballEnsemble"),
        "hockey_NHL": ("hockey", "NHLEnsemble"),
    }
    for key, (sport, model_name) in model_files.items():
        path = os.path.join(settings.MODEL_DIR, f"{key}.pkl")
        exists = os.path.exists(path)
        mtime = None
        if exists:
            import datetime
            mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
        statuses.append(ModelStatus(
            sport=sport,
            model_name=f"{model_name} ({key})",
            model_version="1.0",
            training_date=mtime,
            active=exists,
            metrics=None,
        ))
    return statuses

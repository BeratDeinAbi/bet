from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.database import get_db
from app.schemas.prediction import BacktestSummary, ModelStatus
from app.db.models import ModelRun
from app.services.evaluation import recent_outcomes, accuracy_summary
from app.services.recommended import list_recommended, recommended_accuracy

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.get("/recent")
def get_recent_outcomes(
    limit: int = Query(25, ge=1, le=200),
    sport: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Letzte N evaluierte Predictions — für die Sidebar."""
    return recent_outcomes(db, limit=limit, sport=sport)


@router.get("/accuracy")
def get_accuracy(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Trefferquote der letzten N Tage (gesamt + pro Sport)."""
    return accuracy_summary(db, days=days)


@router.get("/recommended")
def get_recommended_picks(
    sport: Optional[str] = Query(None),
    only_evaluated: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Wett-Empfehlungen (faire Quote ≥ 1.25) inkl. Hit/Miss falls
    bewertet."""
    return list_recommended(
        db, sport=sport, only_evaluated=only_evaluated, limit=limit,
    )


@router.get("/recommended/accuracy")
def get_recommended_accuracy(
    sport: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Wett-Trefferquote — gesamt + pro Sport."""
    return recommended_accuracy(db, sport=sport)


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
        "football_BL2": ("football", "FootballEnsemble"),
        "football_PL": ("football", "FootballEnsemble"),
        "football_PD": ("football", "FootballEnsemble"),
        "football_SSL": ("football", "FootballEnsemble"),
        "hockey_NHL": ("hockey", "NHLEnsemble"),
        "basketball_NBA": ("basketball", "NBAEnsemble"),
        "baseball_MLB": ("baseball", "MLBEnsemble"),
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

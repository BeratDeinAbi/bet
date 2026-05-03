from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app.db.database import get_db
from app.db.models import Match, Prediction, Competition
from app.schemas.prediction import PredictionSchema, PredictionWithMatchSchema, Top3Response
from app.services.ranking import rank_top3_predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


TODAY_WINDOW_PAST = timedelta(hours=6)
TODAY_WINDOW_FUTURE = timedelta(hours=36)


def _within_today_window(kickoff) -> bool:
    if kickoff is None:
        return False
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - TODAY_WINDOW_PAST) <= kickoff <= (now + TODAY_WINDOW_FUTURE)


def _enrich(pred: Prediction, match: Match) -> PredictionWithMatchSchema:
    return PredictionWithMatchSchema(
        **{c.name: getattr(pred, c.name) for c in pred.__table__.columns},
        sport=match.sport,
        league=match.competition.code if match.competition else "",
        home_team=match.home_team_name,
        away_team=match.away_team_name,
        kickoff_time=match.kickoff_time,
    )


@router.get("/today", response_model=List[PredictionWithMatchSchema])
def get_today_predictions(
    sport: Optional[str] = Query(None),
    league: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Prediction).join(Match).join(Competition)
    if sport:
        query = query.filter(Match.sport == sport)
    if league:
        query = query.filter(Competition.code == league)

    preds = query.all()
    result = []
    for pred in preds:
        match = pred.match
        if match and _within_today_window(match.kickoff_time):
            result.append(_enrich(pred, match))
    return result


@router.get("/top3", response_model=Top3Response)
def get_top3_predictions(db: Session = Depends(get_db)):
    return rank_top3_predictions(db)


@router.get("/{match_id}", response_model=PredictionWithMatchSchema)
def get_prediction_for_match(match_id: int, db: Session = Depends(get_db)):
    pred = db.query(Prediction).filter(Prediction.match_id == match_id).first()
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found for this match")
    return _enrich(pred, pred.match)

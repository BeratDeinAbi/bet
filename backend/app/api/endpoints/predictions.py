from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date

from app.db.database import get_db
from app.db.models import Match, Prediction, Competition
from app.schemas.prediction import PredictionSchema, PredictionWithMatchSchema, Top3Response
from app.services.ranking import rank_top3_predictions

router = APIRouter(prefix="/predictions", tags=["predictions"])


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
    today = date.today()
    query = db.query(Prediction).join(Match).join(Competition)
    if sport:
        query = query.filter(Match.sport == sport)
    if league:
        query = query.filter(Competition.code == league)

    preds = query.all()
    result = []
    for pred in preds:
        match = pred.match
        if match and match.kickoff_time and match.kickoff_time.date() == today:
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

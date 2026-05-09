from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict
from datetime import datetime, timedelta, timezone, date as date_type

from app.db.database import get_db
from app.db.models import Match, Prediction, Competition, RecommendedPick
from app.schemas.prediction import (
    PredictionSchema, PredictionWithMatchSchema, RecommendedPickSchema,
    Top3Response,
)
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


def _parse_date(s: str) -> date_type:
    """YYYY-MM-DD → date.  Raised HTTPException bei Schrott."""
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültiges Datum (erwarte YYYY-MM-DD)")


def _pick_for(db, pred: Prediction) -> Optional[RecommendedPickSchema]:
    rp = (
        db.query(RecommendedPick)
        .filter(RecommendedPick.prediction_id == pred.id)
        .first()
    )
    if not rp:
        return None
    return RecommendedPickSchema(
        market=rp.market,
        line=rp.line,
        direction=rp.direction,
        model_probability=rp.model_probability,
        fair_odds=rp.fair_odds,
        confidence_label=rp.confidence_label or pred.confidence_label,
    )


def _enrich(db, pred: Prediction, match: Match) -> PredictionWithMatchSchema:
    return PredictionWithMatchSchema(
        **{c.name: getattr(pred, c.name) for c in pred.__table__.columns},
        sport=match.sport,
        league=match.competition.code if match.competition else "",
        home_team=match.home_team_name,
        away_team=match.away_team_name,
        kickoff_time=match.kickoff_time,
        recommended_pick=_pick_for(db, pred),
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
    # Falls heute mehrere Predictions pro Match wegen Snapshot-Edge-Cases
    # vorliegen: jüngste gewinnt.
    by_match: Dict[int, Prediction] = {}
    for pred in preds:
        match = pred.match
        if not (match and _within_today_window(match.kickoff_time)):
            continue
        existing = by_match.get(match.id)
        if existing is None or pred.created_at > existing.created_at:
            by_match[match.id] = pred

    return [_enrich(db, p, p.match) for p in by_match.values()]


@router.get("/by-date", response_model=List[PredictionWithMatchSchema])
def get_predictions_by_date(
    date: str = Query(..., description="YYYY-MM-DD — Tag, an dem die Prediction erstellt wurde"),
    sport: Optional[str] = Query(None),
    league: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Predictions, die am gewählten Tag (UTC) erstellt wurden.

    Filtert auf ``Prediction.created_at`` im Fenster
    ``[date 00:00 UTC, date+1 00:00 UTC)``.  Bei mehreren Predictions
    pro Match am Tag gewinnt die jüngste.
    """
    target = _parse_date(date)
    day_start = datetime.combine(target, datetime.min.time(), tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)

    query = (
        db.query(Prediction)
        .join(Match)
        .join(Competition)
        .filter(
            Prediction.created_at >= day_start,
            Prediction.created_at < day_end,
        )
        .order_by(Prediction.created_at.desc())
    )
    if sport:
        query = query.filter(Match.sport == sport)
    if league:
        query = query.filter(Competition.code == league)

    by_match: Dict[int, Prediction] = {}
    for pred in query.all():
        if pred.match_id not in by_match:
            by_match[pred.match_id] = pred  # erste = jüngste dank ORDER BY desc

    return [_enrich(db, p, p.match) for p in by_match.values() if p.match]


@router.get("/history/dates", response_model=List[str])
def get_prediction_history_dates(
    limit: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
):
    """Liste der Tage (UTC, neueste zuerst), an denen Predictions
    erstellt wurden.  Für den Date-Picker im Frontend.
    """
    rows = (
        db.query(func.date(Prediction.created_at).label("d"))
        .distinct()
        .order_by(func.date(Prediction.created_at).desc())
        .limit(limit)
        .all()
    )
    out: List[str] = []
    for r in rows:
        d = r[0]
        if d is None:
            continue
        # SQLite liefert str, andere Backends date — beides normalisieren
        out.append(str(d) if not isinstance(d, date_type) else d.isoformat())
    return out


@router.get("/top3", response_model=Top3Response)
def get_top3_predictions(
    date: Optional[str] = Query(None, description="Optional YYYY-MM-DD für historische Top-3"),
    db: Session = Depends(get_db),
):
    """Top-3-Picks.  Ohne ``date``-Parameter: live (heute + nächste 36 h).
    Mit ``date``: rekonstruiert aus den Predictions des angegebenen Tages.
    """
    snapshot_date = _parse_date(date) if date else None
    return rank_top3_predictions(db, snapshot_date=snapshot_date)


@router.get("/{match_id}", response_model=PredictionWithMatchSchema)
def get_prediction_for_match(match_id: int, db: Session = Depends(get_db)):
    pred = (
        db.query(Prediction)
        .filter(Prediction.match_id == match_id)
        .order_by(Prediction.created_at.desc())
        .first()
    )
    if not pred:
        raise HTTPException(status_code=404, detail="Prediction not found for this match")
    return _enrich(db, pred, pred.match)

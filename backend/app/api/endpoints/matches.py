from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime, timedelta, timezone

from app.db.database import get_db
from app.db.models import Match, Competition
from app.schemas.match import MatchSchema, MatchListResponse

router = APIRouter(prefix="/matches", tags=["matches"])


# Sliding window for "Heutige Spiele":
#   - 6h zurück → laufende Spiele bleiben sichtbar.
#   - 36h vorwärts → Partien morgen (z. B. BL2 So-Spiele am Sa-Abend
#     auf dem Dashboard) werden bereits angezeigt.
TODAY_WINDOW_PAST = timedelta(hours=6)
TODAY_WINDOW_FUTURE = timedelta(hours=36)


def _within_today_window(kickoff: Optional[datetime]) -> bool:
    if kickoff is None:
        return False
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - TODAY_WINDOW_PAST) <= kickoff <= (now + TODAY_WINDOW_FUTURE)


@router.get("/today", response_model=MatchListResponse)
def get_today_matches(
    sport: Optional[str] = Query(None, description="Filter by sport: football | hockey"),
    league: Optional[str] = Query(None, description="Filter by league code: BL1, BL2, PL, PD, SSL, NHL"),
    db: Session = Depends(get_db),
):
    query = db.query(Match).join(Competition)

    if sport:
        query = query.filter(Match.sport == sport)
    if league:
        query = query.filter(Competition.code == league)

    matches = query.all()
    today_matches = [m for m in matches if _within_today_window(m.kickoff_time)]

    return MatchListResponse(total=len(today_matches), matches=today_matches)


@router.get("/{match_id}", response_model=MatchSchema)
def get_match(match_id: int, db: Session = Depends(get_db)):
    match = db.query(Match).filter(Match.id == match_id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return match

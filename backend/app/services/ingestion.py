"""
Ingestion service: fetches today's matches and historical data, stores in DB.
"""
import logging
import time
from datetime import datetime, timezone, date
from typing import List

from sqlalchemy.orm import Session

from app.db.models import Competition, Team, Match, MatchSegment, ProviderLog
from app.providers.base import ProviderMatch, ProviderHistoricalMatch
from app.providers.provider_factory import get_football_provider, get_superlig_provider, get_hockey_provider
from app.core.config import settings

logger = logging.getLogger(__name__)

COMPETITIONS = {
    "BL1":  {"name": "Bundesliga",    "sport": "football", "country": "Germany"},
    "PL":   {"name": "Premier League","sport": "football", "country": "England"},
    "PD":   {"name": "La Liga",       "sport": "football", "country": "Spain"},
    "SSL":  {"name": "Süper Lig",     "sport": "football", "country": "Turkey"},
    "NHL":  {"name": "NHL",           "sport": "hockey",   "country": "North America"},
}


def _ensure_competition(db: Session, code: str) -> Competition:
    comp = db.query(Competition).filter(Competition.code == code).first()
    if not comp:
        meta = COMPETITIONS.get(code, {"name": code, "sport": "unknown", "country": ""})
        comp = Competition(code=code, **meta, provider="auto")
        db.add(comp)
        db.flush()
    return comp


def _upsert_match(db: Session, pm: ProviderMatch, competition_id: int) -> Match:
    match = db.query(Match).filter(Match.external_id == pm.external_id).first()
    if not match:
        match = Match(
            external_id=pm.external_id,
            competition_id=competition_id,
            home_team_name=pm.home_team_name,
            away_team_name=pm.away_team_name,
            kickoff_time=_parse_dt(pm.kickoff_time),
            status=pm.status,
            sport=pm.sport,
            home_score=pm.home_score,
            away_score=pm.away_score,
            source=pm.sport,
        )
        db.add(match)
    else:
        match.status = pm.status
        match.home_score = pm.home_score
        match.away_score = pm.away_score
    return match


def _parse_dt(dt_str: str) -> datetime:
    if not dt_str:
        return datetime.now(timezone.utc)
    try:
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)


def _log_provider(db: Session, provider: str, endpoint: str, success: bool, records: int, error: str = None, duration_ms: int = 0):
    log = ProviderLog(
        provider=provider,
        endpoint=endpoint,
        success=success,
        records_fetched=records,
        error_message=error,
        duration_ms=duration_ms,
    )
    db.add(log)


def ingest_today_matches(db: Session) -> int:
    total = 0

    # Football — ESPN covers ALL leagues including SSL (no key needed)
    all_football_leagues = list(settings.ACTIVE_FOOTBALL_LEAGUES)
    fp = get_football_provider()
    t0 = time.time()
    try:
        matches = fp.get_today_matches(all_football_leagues)
        for pm in matches:
            comp = _ensure_competition(db, pm.competition_code)
            _upsert_match(db, pm, comp.id)
            total += 1
        db.flush()
        _log_provider(db, fp.name, "today_matches", True, len(matches), duration_ms=int((time.time()-t0)*1000))
        logger.info(f"Football: {len(matches)} matches from {fp.name}")
    except Exception as e:
        _log_provider(db, fp.name, "today_matches", False, 0, str(e))
        logger.error(f"Football ingestion error: {e}")

    # Hockey (NHL)
    hp = get_hockey_provider()
    t0 = time.time()
    try:
        nhl_matches = hp.get_today_matches()
        for pm in nhl_matches:
            comp = _ensure_competition(db, "NHL")
            _upsert_match(db, pm, comp.id)
            total += 1
        db.flush()
        _log_provider(db, hp.name, "today_matches", True, len(nhl_matches), duration_ms=int((time.time()-t0)*1000))
    except Exception as e:
        _log_provider(db, hp.name, "today_matches", False, 0, str(e))
        logger.error(f"NHL ingestion error: {e}")

    db.commit()
    logger.info(f"Ingested {total} matches for today")
    return total


def ingest_historical_matches(db: Session, seasons: List[str] = None) -> int:
    if seasons is None:
        seasons = ["2023", "2024"]
    total = 0

    fp = get_football_provider()
    for code in settings.ACTIVE_FOOTBALL_LEAGUES:
        try:
            matches = fp.get_historical_matches(code, seasons)
            for pm in matches:
                comp = _ensure_competition(db, pm.competition_code)
                match = _upsert_match(db, pm, comp.id)
                db.flush()
                if hasattr(pm, "segments") and pm.segments:
                    for seg in pm.segments:
                        existing = db.query(MatchSegment).filter(
                            MatchSegment.match_id == match.id,
                            MatchSegment.segment_code == seg["segment_code"]
                        ).first()
                        if not existing:
                            db.add(MatchSegment(match_id=match.id, **seg))
                total += 1
        except Exception as e:
            logger.error(f"Historical football error {code}: {e}")

    hp = get_hockey_provider()
    try:
        nhl_hist = hp.get_historical_matches(seasons)
        for pm in nhl_hist:
            comp = _ensure_competition(db, "NHL")
            match = _upsert_match(db, pm, comp.id)
            db.flush()
            if hasattr(pm, "segments") and pm.segments:
                for seg in pm.segments:
                    existing = db.query(MatchSegment).filter(
                        MatchSegment.match_id == match.id,
                        MatchSegment.segment_code == seg["segment_code"]
                    ).first()
                    if not existing:
                        db.add(MatchSegment(match_id=match.id, **seg))
            total += 1
    except Exception as e:
        logger.error(f"Historical NHL error: {e}")

    db.commit()
    logger.info(f"Ingested {total} historical matches")
    return total

"""
Ingestion service: fetches today's matches and historical data, stores in DB.
"""
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, date
from typing import List, Optional, Set

from sqlalchemy.orm import Session

from app.db.models import Competition, Team, Match, MatchSegment, ProviderLog
from app.providers.base import ProviderMatch, ProviderHistoricalMatch
from app.providers.provider_factory import (
    get_football_provider,
    get_german_football_provider,
    get_superlig_provider,
    get_hockey_provider,
    get_basketball_provider,
    get_baseball_provider,
)
from app.core.config import settings

# OpenLigaDB-Liga-Codes (1. + 2. Bundesliga)
GERMAN_LEAGUES = {"BL1", "BL2"}

logger = logging.getLogger(__name__)

COMPETITIONS = {
    "BL1":  {"name": "Bundesliga",    "sport": "football", "country": "Germany"},
    "BL2":  {"name": "2. Bundesliga", "sport": "football", "country": "Germany"},
    "PL":   {"name": "Premier League","sport": "football", "country": "England"},
    "PD":   {"name": "La Liga",       "sport": "football", "country": "Spain"},
    "SSL":  {"name": "Süper Lig",     "sport": "football", "country": "Turkey"},
    "NHL":  {"name": "NHL",           "sport": "hockey",   "country": "North America"},
    "NBA":  {"name": "NBA",           "sport": "basketball","country": "USA"},
    "MLB":  {"name": "MLB",           "sport": "baseball",  "country": "USA"},
}


def _ensure_competition(db: Session, code: str) -> Competition:
    comp = db.query(Competition).filter(Competition.code == code).first()
    if not comp:
        meta = COMPETITIONS.get(code, {"name": code, "sport": "unknown", "country": ""})
        comp = Competition(code=code, **meta, provider="auto")
        db.add(comp)
        db.flush()
    return comp


def _extract_context(pm: ProviderMatch) -> Optional[dict]:
    """Sammelt sport-spezifische Live-Kontext-Daten (Pitcher-ERA, Goalie etc.),
    die der Provider via dynamische setattr() angehängt hat."""
    ctx = {}
    for key in ("home_pitcher_era", "away_pitcher_era",
                "home_pitcher_xfip", "away_pitcher_xfip",
                "home_goalie", "away_goalie"):
        val = getattr(pm, key, None)
        if val is not None:
            ctx[key] = val
    return ctx or None


def _upsert_match(db: Session, pm: ProviderMatch, competition_id: int) -> Match:
    match = db.query(Match).filter(Match.external_id == pm.external_id).first()
    ctx = _extract_context(pm)
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
            context=ctx,
        )
        db.add(match)
    else:
        match.status = pm.status
        match.home_score = pm.home_score
        match.away_score = pm.away_score
        if ctx:
            match.context = ctx
        # Mock-Matches immer mit aktueller Kickoff-Zeit überschreiben
        if pm.external_id.startswith("mock_"):
            match.kickoff_time = _parse_dt(pm.kickoff_time)
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


def _mock_fallback_leagues(db: Session, missing_codes: List[str], total: int) -> int:
    """Füllt fehlende Ligen mit Mock-Daten, damit immer alle konfigurierten
    Ligen im Dashboard auftauchen — auch wenn der Live-Provider nichts
    zurückgibt (kein Spieltag heute, API-Ausfall o. ä.)."""
    if not missing_codes or not settings.USE_MOCK_FALLBACK:
        return total
    from app.providers.mock_provider import MockFootballProvider
    mock = MockFootballProvider()
    mock_matches = mock.get_today_matches(missing_codes)
    for pm in mock_matches:
        comp = _ensure_competition(db, pm.competition_code)
        _upsert_match(db, pm, comp.id)
        total += 1
    if mock_matches:
        db.flush()
        logger.info(f"Mock fallback: {len(mock_matches)} Spiele für {missing_codes}")
    return total


def ingest_today_matches(db: Session) -> int:
    total = 0

    active = list(settings.ACTIVE_FOOTBALL_LEAGUES)
    german = [c for c in active if c in GERMAN_LEAGUES]
    other = [c for c in active if c not in GERMAN_LEAGUES]

    # 1. OpenLigaDB für 1. + 2. Bundesliga (kostenlos, ohne API-Key)
    if german:
        gp = get_german_football_provider()
        t0 = time.time()
        fetched_german: Set[str] = set()
        fetched_german_scheduled: Set[str] = set()
        try:
            matches = gp.get_today_matches(german)
            for pm in matches:
                comp = _ensure_competition(db, pm.competition_code)
                _upsert_match(db, pm, comp.id)
                fetched_german.add(pm.competition_code)
                if pm.status == "SCHEDULED":
                    fetched_german_scheduled.add(pm.competition_code)
                total += 1
            db.flush()
            _log_provider(db, gp.name, "today_matches", True, len(matches),
                          duration_ms=int((time.time() - t0) * 1000))
            logger.info(f"German football ({', '.join(german)}): {len(matches)} matches from {gp.name}")
        except Exception as e:
            _log_provider(db, gp.name, "today_matches", False, 0, str(e))
            logger.error(f"German football ingestion error: {e}")

        # Mock-Fallback für Ligen ohne anstehende (SCHEDULED) Spiele
        missing = [c for c in german if c not in fetched_german_scheduled]
        total = _mock_fallback_leagues(db, missing, total)

    # 2. ESPN/football-data für alle übrigen Ligen
    if other:
        fp = get_football_provider()
        t0 = time.time()
        fetched_other: Set[str] = set()
        fetched_other_scheduled: Set[str] = set()
        try:
            matches = fp.get_today_matches(other)
            for pm in matches:
                comp = _ensure_competition(db, pm.competition_code)
                _upsert_match(db, pm, comp.id)
                fetched_other.add(pm.competition_code)
                if pm.status == "SCHEDULED":
                    fetched_other_scheduled.add(pm.competition_code)
                total += 1
            db.flush()
            _log_provider(db, fp.name, "today_matches", True, len(matches),
                          duration_ms=int((time.time() - t0) * 1000))
            logger.info(f"Football: {len(matches)} matches from {fp.name}")
        except Exception as e:
            _log_provider(db, fp.name, "today_matches", False, 0, str(e))
            logger.error(f"Football ingestion error: {e}")

        # Fallback für Ligen ohne anstehende (SCHEDULED) Spiele
        missing_other = [c for c in other if c not in fetched_other_scheduled]
        total = _mock_fallback_leagues(db, missing_other, total)

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

    # Basketball (NBA)
    bp = get_basketball_provider()
    t0 = time.time()
    nba_scheduled_count = 0
    try:
        nba_matches = bp.get_today_matches()
        for pm in nba_matches:
            comp = _ensure_competition(db, "NBA")
            _upsert_match(db, pm, comp.id)
            total += 1
            if pm.status == "SCHEDULED":
                nba_scheduled_count += 1
        db.flush()
        _log_provider(db, bp.name, "today_matches", True, len(nba_matches),
                      duration_ms=int((time.time() - t0) * 1000))
        logger.info(f"NBA: {len(nba_matches)} matches from {bp.name} ({nba_scheduled_count} scheduled)")
    except Exception as e:
        _log_provider(db, bp.name, "today_matches", False, 0, str(e))
        logger.error(f"NBA ingestion error: {e}")

    # Mock-Fallback wenn keine anstehenden NBA-Spiele (off-day, Spiele bereits beendet…)
    if nba_scheduled_count == 0 and settings.USE_MOCK_FALLBACK:
        from app.providers.mock_provider import MockBasketballProvider
        for pm in MockBasketballProvider().get_today_matches():
            comp = _ensure_competition(db, "NBA")
            _upsert_match(db, pm, comp.id)
            total += 1
        db.flush()
        logger.info("NBA Mock-Fallback aktiv — keine anstehenden Spiele heute")

    # Baseball (MLB)
    bbp = get_baseball_provider()
    t0 = time.time()
    mlb_count = 0
    try:
        mlb_matches = bbp.get_today_matches()
        for pm in mlb_matches:
            comp = _ensure_competition(db, "MLB")
            _upsert_match(db, pm, comp.id)
            total += 1
            mlb_count += 1
        db.flush()
        _log_provider(db, bbp.name, "today_matches", True, len(mlb_matches),
                      duration_ms=int((time.time() - t0) * 1000))
        logger.info(f"MLB: {len(mlb_matches)} games from {bbp.name}")
    except Exception as e:
        _log_provider(db, bbp.name, "today_matches", False, 0, str(e))
        logger.error(f"MLB ingestion error: {e}")

    if mlb_count == 0 and settings.USE_MOCK_FALLBACK:
        from app.providers.mock_provider import MockBaseballProvider
        for pm in MockBaseballProvider().get_today_matches():
            comp = _ensure_competition(db, "MLB")
            _upsert_match(db, pm, comp.id)
            total += 1
        db.flush()
        logger.info("MLB Mock-Fallback aktiv für heute")

    db.commit()
    logger.info(f"Ingested {total} matches for today")
    return total


def _persist_historical(db: Session, fixed_code: Optional[str], matches) -> int:
    """Schreibt eine Liste historischer Spiele inkl. Segmente in die DB.

    ``fixed_code`` ist gesetzt für Sportarten mit fester Liga (NHL, NBA,
    MLB).  Bei Football kommt der Code aus ``pm.competition_code``.
    """
    n = 0
    for pm in matches:
        code = fixed_code or pm.competition_code
        comp = _ensure_competition(db, code)
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
        n += 1
    return n


def ingest_historical_matches(db: Session, seasons: List[str] = None) -> int:
    """Holt alle historischen Spiele aus den 4 Sport-Quellen parallel
    (I/O-bound — ESPN/NHL/MLB/OpenLigaDB) und schreibt das Ergebnis dann
    sequentiell in die DB.  SQLite verträgt keine parallelen Writes,
    aber die Fetches selbst (90 % der Zeit) laufen jetzt gleichzeitig.

    Speed-Up grob: vorher Football(5×3s) + NHL(15s) + NBA(10s) + MLB(15s)
    ≈ 55 s sequentiell.  Jetzt: max(15 s) + DB-Writes (~3 s) ≈ 18 s.
    """
    if seasons is None:
        seasons = ["2023", "2024"]

    fp = get_football_provider()
    gp = get_german_football_provider()
    hp = get_hockey_provider()
    bp = get_basketball_provider()
    bbp = get_baseball_provider()

    def _fetch_football(code: str):
        provider = gp if code in GERMAN_LEAGUES else fp
        try:
            matches = provider.get_historical_matches(code, seasons)
            if not matches and settings.USE_MOCK_FALLBACK:
                from app.providers.mock_provider import MockFootballProvider
                matches = MockFootballProvider().get_historical_matches(code, seasons)
                logger.info(f"Historical mock fallback für {code}: {len(matches)} Spiele")
            return code, matches
        except Exception as e:
            logger.error(f"Historical football error {code}: {e}")
            return code, []

    def _fetch_nhl():
        try:
            return hp.get_historical_matches(seasons)
        except Exception as e:
            logger.error(f"Historical NHL error: {e}")
            return []

    def _fetch_nba():
        try:
            matches = bp.get_historical_matches(seasons)
            if not matches and settings.USE_MOCK_FALLBACK:
                from app.providers.mock_provider import MockBasketballProvider
                matches = MockBasketballProvider().get_historical_matches(seasons)
                logger.info(f"Historical NBA mock fallback: {len(matches)} Spiele")
            return matches
        except Exception as e:
            logger.error(f"Historical NBA error: {e}")
            return []

    def _fetch_mlb():
        try:
            matches = bbp.get_historical_matches(seasons)
            if not matches and settings.USE_MOCK_FALLBACK:
                from app.providers.mock_provider import MockBaseballProvider
                matches = MockBaseballProvider().get_historical_matches(seasons)
                logger.info(f"Historical MLB mock fallback: {len(matches)} Spiele")
            return matches
        except Exception as e:
            logger.error(f"Historical MLB error: {e}")
            return []

    # Parallel fetch — alle Provider gleichzeitig
    football_codes = list(settings.ACTIVE_FOOTBALL_LEAGUES)
    with ThreadPoolExecutor(max_workers=8) as pool:
        football_futs = [pool.submit(_fetch_football, code) for code in football_codes]
        nhl_fut = pool.submit(_fetch_nhl)
        nba_fut = pool.submit(_fetch_nba)
        mlb_fut = pool.submit(_fetch_mlb)

        football_results = [f.result() for f in football_futs]
        nhl_matches = nhl_fut.result()
        nba_matches = nba_fut.result()
        mlb_matches = mlb_fut.result()

    # Sequentielle DB-Writes — SQLite mag keine parallelen Schreiber
    total = 0
    for _code, matches in football_results:
        total += _persist_historical(db, None, matches)
    total += _persist_historical(db, "NHL", nhl_matches)
    total += _persist_historical(db, "NBA", nba_matches)
    total += _persist_historical(db, "MLB", mlb_matches)

    db.commit()
    logger.info(f"Ingested {total} historical matches (parallel fetch)")
    return total

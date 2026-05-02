"""
OpenLigaDB provider — free, community-run API for German football data.

No API key required, no rate limit. Lizenz: ODbL (Open Database License).
Quelle: https://www.openligadb.de

Liga-Kürzel:
  BL1 → bl1  (1. Bundesliga)
  BL2 → bl2  (2. Bundesliga)

Verfügbare Endpoints (Auswahl):
  GET /getmatchdata/{league}                      aktueller Spieltag
  GET /getmatchdata/{league}/{season}             ganze Saison
  GET /getmatchdata/{league}/{season}/{matchday}  einzelner Spieltag
  GET /getbltable/{league}/{season}               Tabelle
"""
import logging
from datetime import date, datetime, timezone
from typing import List, Optional

import requests

from app.providers.base import (
    BaseFootballProvider,
    ProviderHistoricalMatch,
    ProviderMatch,
)

logger = logging.getLogger(__name__)

OPENLIGADB_BASE = "https://api.openligadb.de"

LEAGUE_MAP = {
    "BL1": {"slug": "bl1", "name": "Bundesliga"},
    "BL2": {"slug": "bl2", "name": "2. Bundesliga"},
}


def _parse_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # OpenLigaDB liefert ISO-8601, UTC-Variante endet auf "Z"
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _result(match: dict, name_keys: List[str]) -> Optional[dict]:
    for r in match.get("matchResults", []) or []:
        rn = (r.get("resultName") or "").lower()
        if any(k in rn for k in name_keys):
            return r
    return None


def _fulltime(match: dict) -> Optional[dict]:
    # Bevorzugt "Endergebnis", fallback auf höchste resultOrderID
    end = _result(match, ["endergebnis", "final"])
    if end:
        return end
    results = match.get("matchResults") or []
    if not results:
        return None
    return max(results, key=lambda r: r.get("resultOrderID", 0))


def _halftime(match: dict) -> Optional[dict]:
    return _result(match, ["halbzeit", "half"])


class OpenLigaDBProvider(BaseFootballProvider):
    """Football provider for the German Bundesliga & 2. Bundesliga."""

    name = "openligadb"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SportsPredictionDashboard/1.0",
            "Accept": "application/json",
        })

    def supports(self, league_code: str) -> bool:
        return league_code in LEAGUE_MAP

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{OPENLIGADB_BASE}/getmatchdata/bl1", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get(self, path: str) -> Optional[list]:
        url = f"{OPENLIGADB_BASE}/{path.lstrip('/')}"
        try:
            r = self.session.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data if isinstance(data, list) else None
        except Exception as e:
            logger.warning(f"OpenLigaDB error {path}: {e}")
            return None

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def _map_status(self, raw: dict) -> str:
        if raw.get("matchIsFinished"):
            return "FINISHED"
        kickoff = _parse_dt(raw.get("matchDateTimeUTC") or raw.get("matchDateTime"))
        if kickoff is None:
            return "SCHEDULED"
        now = datetime.now(timezone.utc)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        # Spielzeit (inkl. HZ-Pause) ~ 110 Minuten
        if kickoff <= now:
            return "LIVE"
        return "SCHEDULED"

    def _parse_match(self, raw: dict, league_code: str) -> ProviderMatch:
        team1 = raw.get("team1") or {}
        team2 = raw.get("team2") or {}
        kickoff = raw.get("matchDateTimeUTC") or raw.get("matchDateTime") or ""

        ft = _fulltime(raw)
        home_score = ft.get("pointsTeam1") if ft else None
        away_score = ft.get("pointsTeam2") if ft else None

        info = LEAGUE_MAP.get(league_code, {"name": league_code})

        return ProviderMatch(
            external_id=f"oldb_{raw.get('matchID')}",
            sport="football",
            competition_code=league_code,
            competition_name=info["name"],
            home_team_name=team1.get("teamName") or "Unknown",
            away_team_name=team2.get("teamName") or "Unknown",
            kickoff_time=kickoff,
            status=self._map_status(raw),
            home_score=home_score,
            away_score=away_score,
            home_team_external_id=str(team1.get("teamId") or ""),
            away_team_external_id=str(team2.get("teamId") or ""),
        )

    def _segments_from_match(self, raw: dict) -> List[dict]:
        ft = _fulltime(raw)
        ht = _halftime(raw)
        if not ft or not ht:
            return []
        h1_home = ht.get("pointsTeam1") or 0
        h1_away = ht.get("pointsTeam2") or 0
        ft_home = ft.get("pointsTeam1") or 0
        ft_away = ft.get("pointsTeam2") or 0
        h2_home = max(ft_home - h1_home, 0)
        h2_away = max(ft_away - h1_away, 0)
        return [
            {"segment_code": "H1", "home_score": h1_home, "away_score": h1_away,
             "total_goals": h1_home + h1_away},
            {"segment_code": "H2", "home_score": h2_home, "away_score": h2_away,
             "total_goals": h2_home + h2_away},
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        today = date.today()
        matches: List[ProviderMatch] = []

        supported = [c for c in league_codes if c in LEAGUE_MAP]
        for code in supported:
            slug = LEAGUE_MAP[code]["slug"]
            data = self._get(f"getmatchdata/{slug}")
            if not data:
                continue
            for raw in data:
                kickoff = _parse_dt(raw.get("matchDateTimeUTC") or raw.get("matchDateTime"))
                if kickoff is None:
                    continue
                # Compare against UTC date
                if kickoff.tzinfo is None:
                    kickoff = kickoff.replace(tzinfo=timezone.utc)
                if kickoff.date() != today:
                    continue
                try:
                    matches.append(self._parse_match(raw, code))
                except Exception as e:
                    logger.warning(f"OpenLigaDB parse error ({code}): {e}")

        logger.info(
            f"OpenLigaDB: {len(matches)} matches today ({', '.join(supported) or 'none'})"
        )
        return matches

    def get_historical_matches(
        self, league_code: str, seasons: List[str]
    ) -> List[ProviderHistoricalMatch]:
        if league_code not in LEAGUE_MAP:
            return []
        slug = LEAGUE_MAP[league_code]["slug"]
        historical: List[ProviderHistoricalMatch] = []
        seen: set = set()

        for season in seasons:
            season_str = str(season).strip()
            data = self._get(f"getmatchdata/{slug}/{season_str}")
            if not data:
                continue
            for raw in data:
                mid = raw.get("matchID")
                if mid in seen:
                    continue
                seen.add(mid)
                if not raw.get("matchIsFinished"):
                    continue
                try:
                    pm = self._parse_match(raw, league_code)
                    if pm.home_score is None or pm.away_score is None:
                        continue
                    historical.append(ProviderHistoricalMatch(
                        **pm.__dict__,
                        segments=self._segments_from_match(raw),
                    ))
                except Exception as e:
                    logger.warning(f"OpenLigaDB historical parse error: {e}")

        logger.info(
            f"OpenLigaDB historical: {len(historical)} finished matches for {league_code}"
        )
        return historical

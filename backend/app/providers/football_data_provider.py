"""
Adapter for football-data.org API v4.
Covers: Bundesliga (BL1), Premier League (PL), La Liga (PD).
Free tier: 10 requests/minute, no Süper Lig.
"""
import requests
import logging
from datetime import date, datetime, timezone
from typing import List, Optional

from app.core.config import settings
from app.providers.base import BaseFootballProvider, ProviderMatch, ProviderHistoricalMatch

logger = logging.getLogger(__name__)

LEAGUE_NAMES = {
    "BL1": "Bundesliga",
    "PL": "Premier League",
    "PD": "La Liga",
}


class FootballDataProvider(BaseFootballProvider):
    name = "football_data"

    def __init__(self):
        self.api_key = settings.FOOTBALL_DATA_API_KEY
        self.base_url = settings.FOOTBALL_DATA_BASE_URL
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-Auth-Token": self.api_key})

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        url = f"{self.base_url}/{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"FootballDataProvider error {endpoint}: {e}")
            return None

    def _parse_match(self, raw: dict, competition_code: str) -> ProviderMatch:
        utc_date = raw.get("utcDate", "")
        home = raw.get("homeTeam", {})
        away = raw.get("awayTeam", {})
        score = raw.get("score", {})
        full = score.get("fullTime", {})
        return ProviderMatch(
            external_id=f"fd_{raw['id']}",
            sport="football",
            competition_code=competition_code,
            competition_name=LEAGUE_NAMES.get(competition_code, competition_code),
            home_team_name=home.get("name", "Unknown"),
            away_team_name=away.get("name", "Unknown"),
            kickoff_time=utc_date,
            status=raw.get("status", "SCHEDULED"),
            home_score=full.get("home"),
            away_score=full.get("away"),
            home_team_external_id=str(home.get("id", "")),
            away_team_external_id=str(away.get("id", "")),
        )

    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        today = date.today().isoformat()
        matches = []
        # Only fetch leagues supported by this provider (not SSL)
        supported = [c for c in league_codes if c in LEAGUE_NAMES]
        for code in supported:
            data = self._get(f"competitions/{code}/matches", {"dateFrom": today, "dateTo": today})
            if data and "matches" in data:
                for raw in data["matches"]:
                    matches.append(self._parse_match(raw, code))
        return matches

    def get_historical_matches(self, league_code: str, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        if league_code not in LEAGUE_NAMES:
            return []
        historical = []
        for season in seasons:
            data = self._get(f"competitions/{league_code}/matches", {"season": season})
            if data and "matches" in data:
                for raw in data["matches"]:
                    if raw.get("status") == "FINISHED":
                        m = self._parse_match(raw, league_code)
                        score = raw.get("score", {})
                        ht = score.get("halfTime", {})
                        segments = []
                        if ht.get("home") is not None:
                            h1_home = ht["home"]
                            h1_away = ht["away"]
                            ft_home = score.get("fullTime", {}).get("home", 0) or 0
                            ft_away = score.get("fullTime", {}).get("away", 0) or 0
                            h2_home = ft_home - h1_home
                            h2_away = ft_away - h1_away
                            segments = [
                                {"segment_code": "H1", "home_score": h1_home, "away_score": h1_away, "total_goals": h1_home + h1_away},
                                {"segment_code": "H2", "home_score": h2_home, "away_score": h2_away, "total_goals": h2_home + h2_away},
                            ]
                        historical.append(ProviderHistoricalMatch(**m.__dict__, segments=segments))
        return historical

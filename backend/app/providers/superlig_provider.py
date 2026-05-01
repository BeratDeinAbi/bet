"""
Adapter for Süper Lig — second football provider.
In MVP: uses mock data when API key is missing.
To activate: set SUPERLIG_API_KEY and SUPERLIG_API_URL in .env.
Interface is fully built for seamless activation.
"""
import requests
import logging
from datetime import date
from typing import List, Optional

from app.core.config import settings
from app.providers.base import BaseFootballProvider, ProviderMatch, ProviderHistoricalMatch

logger = logging.getLogger(__name__)


class SuperLigProvider(BaseFootballProvider):
    name = "superlig_provider"

    COMPETITION_CODE = "SSL"
    COMPETITION_NAME = "Süper Lig"

    def __init__(self):
        self.api_key = settings.SUPERLIG_API_KEY
        self.base_url = settings.SUPERLIG_API_URL
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def is_available(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        if not self.is_available():
            return None
        try:
            resp = self.session.get(f"{self.base_url}/{endpoint}", params=params, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"SuperLigProvider error: {e}")
            return None

    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        if "SSL" not in league_codes or not self.is_available():
            return []
        today = date.today().isoformat()
        # Adapter: map your actual API response shape here
        data = self._get("matches", {"date": today, "competition": "superlig"})
        if not data:
            return []
        matches = []
        for raw in data.get("matches", []):
            matches.append(ProviderMatch(
                external_id=f"ssl_{raw.get('id', '')}",
                sport="football",
                competition_code="SSL",
                competition_name=self.COMPETITION_NAME,
                home_team_name=raw.get("homeTeam", {}).get("name", "Unknown"),
                away_team_name=raw.get("awayTeam", {}).get("name", "Unknown"),
                kickoff_time=raw.get("date", ""),
                status=raw.get("status", "SCHEDULED"),
            ))
        return matches

    def get_historical_matches(self, league_code: str, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        if league_code != "SSL" or not self.is_available():
            return []
        historical = []
        for season in seasons:
            data = self._get("matches", {"competition": "superlig", "season": season, "status": "finished"})
            if not data:
                continue
            for raw in data.get("matches", []):
                historical.append(ProviderHistoricalMatch(
                    external_id=f"ssl_{raw.get('id', '')}",
                    sport="football",
                    competition_code="SSL",
                    competition_name=self.COMPETITION_NAME,
                    home_team_name=raw.get("homeTeam", {}).get("name", "Unknown"),
                    away_team_name=raw.get("awayTeam", {}).get("name", "Unknown"),
                    kickoff_time=raw.get("date", ""),
                    status="FINISHED",
                    home_score=raw.get("score", {}).get("home"),
                    away_score=raw.get("score", {}).get("away"),
                    segments=[],
                ))
        return historical

"""
Adapter for the public NHL API (api-web.nhle.com/v1).
No API key required.
"""
import requests
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from typing import List, Optional

from app.core.config import settings
from app.providers.base import BaseHockeyProvider, ProviderMatch, ProviderHistoricalMatch

logger = logging.getLogger(__name__)


class NHLProvider(BaseHockeyProvider):
    name = "nhl_api"

    def __init__(self):
        self.base_url = settings.NHL_API_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "SportsPredictionDashboard/1.0"})

    def is_available(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/schedule/now", timeout=5)
            return resp.status_code == 200
        except Exception:
            return False

    def _get(self, endpoint: str) -> Optional[dict]:
        url = f"{self.base_url}/{endpoint}"
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"NHLProvider error {endpoint}: {e}")
            return None

    def _parse_game(self, game: dict) -> ProviderMatch:
        home = game.get("homeTeam", {})
        away = game.get("awayTeam", {})
        game_state = game.get("gameState", "FUT")
        status_map = {"FUT": "SCHEDULED", "PRE": "SCHEDULED", "LIVE": "LIVE", "CRIT": "LIVE", "FINAL": "FINISHED", "OFF": "FINISHED"}
        return ProviderMatch(
            external_id=f"nhl_{game.get('id', '')}",
            sport="hockey",
            competition_code="NHL",
            competition_name="NHL",
            home_team_name=f"{home.get('placeName', {}).get('default', '')} {home.get('commonName', {}).get('default', '')}".strip(),
            away_team_name=f"{away.get('placeName', {}).get('default', '')} {away.get('commonName', {}).get('default', '')}".strip(),
            kickoff_time=game.get("startTimeUTC", ""),
            status=status_map.get(game_state, "SCHEDULED"),
            home_score=home.get("score"),
            away_score=away.get("score"),
            home_team_external_id=str(home.get("id", "")),
            away_team_external_id=str(away.get("id", "")),
        )

    def get_today_matches(self) -> List[ProviderMatch]:
        today = date.today().isoformat()
        # Try date-specific endpoint first (more reliable than /now)
        data = self._get(f"schedule/{today}")
        if not data:
            data = self._get("schedule/now")
        if not data:
            return []
        games = []
        for day in data.get("gameWeek", []):
            if day.get("date") == today:
                for game in day.get("games", []):
                    games.append(self._parse_game(game))
        logger.info(f"NHL: fetched {len(games)} games for {today}")
        return games

    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        """Sammelt finished games und holt die Periodenscores parallel
        (8 Worker).  Reihenfolge des Outputs ist nicht garantiert —
        irrelevant fürs Training (Modelle sortieren intern nach kickoff)."""
        candidates: List[dict] = []
        for season in seasons:
            data = self._get(f"schedule/season/{season}")
            if not data:
                continue
            for day in data.get("gameWeek", []):
                for game in day.get("games", []):
                    if game.get("gameState") in ("FINAL", "OFF"):
                        candidates.append(game)

        def _build(game: dict) -> Optional[ProviderHistoricalMatch]:
            try:
                m = self._parse_game(game)
                game_id = game.get("id")
                segments = self._get_periods(game_id) if game_id else []
                return ProviderHistoricalMatch(**m.__dict__, segments=segments)
            except Exception:
                return None

        historical: List[ProviderHistoricalMatch] = []
        if candidates:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for result in pool.map(_build, candidates):
                    if result is not None:
                        historical.append(result)
        return historical

    def _get_periods(self, game_id: str) -> List[dict]:
        data = self._get(f"gamecenter/{game_id}/boxscore")
        if not data:
            return []
        segments = []
        for period in data.get("periodDescriptor", {}).get("periods", []):
            p_num = period.get("periodNumber", 0)
            if p_num in (1, 2, 3):
                code = f"P{p_num}"
                home_goals = sum(
                    1 for g in data.get("summary", {}).get("scoring", [])
                    if g.get("periodDescriptor", {}).get("number") == p_num
                    and g.get("teamAbbrev") == data.get("homeTeam", {}).get("abbrev")
                )
                away_goals = sum(
                    1 for g in data.get("summary", {}).get("scoring", [])
                    if g.get("periodDescriptor", {}).get("number") == p_num
                    and g.get("teamAbbrev") == data.get("awayTeam", {}).get("abbrev")
                )
                segments.append({
                    "segment_code": code,
                    "home_score": home_goals,
                    "away_score": away_goals,
                    "total_goals": home_goals + away_goals,
                })
        return segments

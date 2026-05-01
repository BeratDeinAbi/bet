"""
ESPN public API provider — no API key required.
Covers all target football leagues.

Leagues:
  BL1  → ger.1  (Bundesliga)
  PL   → eng.1  (Premier League)
  PD   → esp.1  (La Liga)
  SSL  → tur.1  (Süper Lig)
"""
import requests
import logging
from datetime import date, timedelta
from typing import List, Optional

from app.providers.base import BaseFootballProvider, ProviderMatch, ProviderHistoricalMatch

logger = logging.getLogger(__name__)

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"

LEAGUE_MAP = {
    "BL1": {"slug": "ger.1",  "name": "Bundesliga"},
    "PL":  {"slug": "eng.1",  "name": "Premier League"},
    "PD":  {"slug": "esp.1",  "name": "La Liga"},
    "SSL": {"slug": "tur.1",  "name": "Süper Lig"},
}

# ESPN uses many status names — map all finished/live states
FINISHED_STATUSES = {
    "STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_FT",
    "STATUS_FULL_PEN", "STATUS_ABANDONED",
}
LIVE_STATUSES = {
    "STATUS_IN_PROGRESS", "STATUS_HALFTIME",
    "STATUS_END_PERIOD", "STATUS_DELAYED",
}


def _espn_status(status_name: str) -> str:
    if status_name in FINISHED_STATUSES:
        return "FINISHED"
    if status_name in LIVE_STATUSES:
        return "LIVE"
    if status_name in ("STATUS_POSTPONED", "STATUS_CANCELLED", "STATUS_SUSPENDED"):
        return "POSTPONED"
    return "SCHEDULED"


class ESPNFootballProvider(BaseFootballProvider):
    name = "espn_football"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SportsPredictionDashboard/1.0",
            "Accept": "application/json",
        })

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{ESPN_BASE}/ger.1/scoreboard", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def _get_scoreboard(self, slug: str, target_date: Optional[str] = None) -> List[dict]:
        params = {}
        if target_date:
            params["dates"] = target_date  # already YYYYMMDD
        url = f"{ESPN_BASE}/{slug}/scoreboard"
        try:
            r = self.session.get(url, params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("events", [])
        except Exception as e:
            logger.warning(f"ESPN fetch error ({slug}): {e}")
            return []

    def _parse_event(self, event: dict, league_code: str) -> ProviderMatch:
        comp = event["competitions"][0]
        competitors = comp.get("competitors", [])

        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        status_name = comp.get("status", {}).get("type", {}).get("name", "STATUS_SCHEDULED")
        status = _espn_status(status_name)

        home_score = None
        away_score = None
        if status in ("LIVE", "FINISHED"):
            try:
                home_score = int(home.get("score", 0))
                away_score = int(away.get("score", 0))
            except (ValueError, TypeError):
                pass

        league_info = LEAGUE_MAP.get(league_code, {"name": league_code})

        return ProviderMatch(
            external_id=f"espn_{event['id']}",
            sport="football",
            competition_code=league_code,
            competition_name=league_info["name"],
            home_team_name=home.get("team", {}).get("displayName", "Unknown"),
            away_team_name=away.get("team", {}).get("displayName", "Unknown"),
            kickoff_time=event.get("date", ""),
            status=status,
            home_score=home_score,
            away_score=away_score,
            home_team_external_id=str(home.get("team", {}).get("id", "")),
            away_team_external_id=str(away.get("team", {}).get("id", "")),
        )

    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        today = date.today().strftime("%Y%m%d")
        matches = []
        for code in league_codes:
            info = LEAGUE_MAP.get(code)
            if not info:
                continue
            events = self._get_scoreboard(info["slug"], today)
            for event in events:
                try:
                    matches.append(self._parse_event(event, code))
                except Exception as e:
                    logger.warning(f"ESPN parse error for {code}: {e}")
        logger.info(f"ESPN: {len(matches)} matches today ({', '.join(league_codes)})")
        return matches

    def get_historical_matches(self, league_code: str, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        """
        Fetch last ~90 days of real results from ESPN scoreboard.
        Samples every 3 days to cover both weekends and midweek fixtures.
        Capped at 60 finished matches per league for training efficiency.
        """
        info = LEAGUE_MAP.get(league_code)
        if not info:
            return []

        historical = []
        today = date.today()
        seen_ids: set = set()

        # Sample every 3 days for the last 90 days
        for days_ago in range(2, 91, 3):
            if len(historical) >= 60:
                break
            target = (today - timedelta(days=days_ago)).strftime("%Y%m%d")
            events = self._get_scoreboard(info["slug"], target)
            for event in events:
                if event["id"] in seen_ids:
                    continue
                seen_ids.add(event["id"])
                try:
                    pm = self._parse_event(event, league_code)
                    if pm.status == "FINISHED" and pm.home_score is not None:
                        historical.append(ProviderHistoricalMatch(
                            **pm.__dict__,
                            segments=[],
                        ))
                except Exception:
                    continue

        logger.info(f"ESPN historical: {len(historical)} finished matches for {league_code}")
        return historical

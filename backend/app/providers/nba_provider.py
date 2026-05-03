"""
NBA provider — ESPN public API, kein API-Key nötig.

Endpoints:
  Scoreboard:  https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard
               ?dates=YYYYMMDD

ESPN liefert pro Spiel ``competitions[0].competitors[].linescores`` mit
einem Eintrag pro Viertel (4× Reguläre Spielzeit, +OT).  Das nutzen wir
für Q1–Q4-Punkte; OT ignorieren wir bewusst (Wettmärkte beziehen sich
auf reguläre Spielzeit).
"""
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

import requests

from app.providers.base import (
    BaseHockeyProvider,  # gleiche Schnittstelle: get_today_matches() + get_historical_matches(seasons)
    ProviderHistoricalMatch,
    ProviderMatch,
)

logger = logging.getLogger(__name__)

ESPN_NBA_BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

FINISHED_STATUSES = {"STATUS_FINAL", "STATUS_FULL_TIME", "STATUS_FT"}
LIVE_STATUSES = {
    "STATUS_IN_PROGRESS", "STATUS_HALFTIME",
    "STATUS_END_PERIOD", "STATUS_DELAYED",
}


def _map_status(status_name: str) -> str:
    if status_name in FINISHED_STATUSES:
        return "FINISHED"
    if status_name in LIVE_STATUSES:
        return "LIVE"
    if status_name in ("STATUS_POSTPONED", "STATUS_CANCELLED", "STATUS_SUSPENDED"):
        return "POSTPONED"
    return "SCHEDULED"


class NBAProvider(BaseHockeyProvider):
    """
    Hängt am ``BaseHockeyProvider``-Interface (gleiches Vertragsmuster:
    ``get_today_matches()`` + ``get_historical_matches(seasons)``), damit
    sich der Provider sauber neben NHL einfügen lässt.  Sport ist
    ``basketball``, Liga ``NBA``.
    """

    name = "nba_espn"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SportsPredictionDashboard/1.0",
            "Accept": "application/json",
        })

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{ESPN_NBA_BASE}/scoreboard", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get_scoreboard(self, target_date: Optional[str] = None) -> List[dict]:
        params = {}
        if target_date:
            params["dates"] = target_date  # YYYYMMDD
        try:
            r = self.session.get(f"{ESPN_NBA_BASE}/scoreboard", params=params, timeout=10)
            r.raise_for_status()
            return r.json().get("events", []) or []
        except Exception as e:
            logger.warning(f"NBA fetch error ({target_date}): {e}")
            return []

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    def _parse_event(self, event: dict) -> ProviderMatch:
        comp = event["competitions"][0]
        competitors = comp.get("competitors", []) or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})

        status_name = comp.get("status", {}).get("type", {}).get("name", "STATUS_SCHEDULED")
        status = _map_status(status_name)

        home_score: Optional[int] = None
        away_score: Optional[int] = None
        if status in ("LIVE", "FINISHED"):
            try:
                home_score = int(home.get("score", 0))
                away_score = int(away.get("score", 0))
            except (ValueError, TypeError):
                pass

        return ProviderMatch(
            external_id=f"nba_{event.get('id', '')}",
            sport="basketball",
            competition_code="NBA",
            competition_name="NBA",
            home_team_name=home.get("team", {}).get("displayName", "Unknown"),
            away_team_name=away.get("team", {}).get("displayName", "Unknown"),
            kickoff_time=event.get("date", ""),
            status=status,
            home_score=home_score,
            away_score=away_score,
            home_team_external_id=str(home.get("team", {}).get("id", "")),
            away_team_external_id=str(away.get("team", {}).get("id", "")),
        )

    @staticmethod
    def _quarters_from_event(event: dict) -> List[dict]:
        """Q1–Q4 aus den ESPN-Linescores extrahieren. OT wird ignoriert."""
        comp = event.get("competitions", [{}])[0]
        competitors = comp.get("competitors", []) or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), {})
        away = next((c for c in competitors if c.get("homeAway") == "away"), {})
        h_lines = home.get("linescores") or []
        a_lines = away.get("linescores") or []
        if len(h_lines) < 4 or len(a_lines) < 4:
            return []
        segments = []
        for i in range(4):
            try:
                h = int(h_lines[i].get("value", 0) or 0)
                a = int(a_lines[i].get("value", 0) or 0)
            except (TypeError, ValueError):
                return []
            segments.append({
                "segment_code": f"Q{i + 1}",
                "home_score": h,
                "away_score": a,
                "total_goals": h + a,  # column heißt total_goals, hier: total_points
            })
        return segments

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_today_matches(self) -> List[ProviderMatch]:
        # NBA-Spielzeit ist abends US-Zeit → vor allem nachts EU-Zeit.
        # Wir holen heute + morgen (UTC), damit europäische User auch
        # die laufenden Spiele sehen.
        today = date.today()
        targets = [
            today.strftime("%Y%m%d"),
            (today + timedelta(days=1)).strftime("%Y%m%d"),
        ]
        seen_ids: set = set()
        matches: List[ProviderMatch] = []
        for target in targets:
            for event in self._get_scoreboard(target):
                eid = event.get("id")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                try:
                    matches.append(self._parse_event(event))
                except Exception as e:
                    logger.warning(f"NBA parse error: {e}")
        logger.info(f"NBA: {len(matches)} matches in 2-day window")
        return matches

    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        """
        ESPN gruppiert NBA-Spiele nicht nach Season-Endpoints, deshalb
        sampeln wir die letzten ~120 Tage in 3-Tages-Schritten (deckt
        Saison-Spiele zuverlässig ab) und nehmen alles Beendete mit.
        Capped bei 80 finished matches für Trainingseffizienz.
        """
        historical: List[ProviderHistoricalMatch] = []
        seen_ids: set = set()
        today = date.today()

        for days_ago in range(2, 121, 3):
            if len(historical) >= 80:
                break
            target = (today - timedelta(days=days_ago)).strftime("%Y%m%d")
            events = self._get_scoreboard(target)
            for event in events:
                eid = event.get("id")
                if eid in seen_ids:
                    continue
                seen_ids.add(eid)
                try:
                    pm = self._parse_event(event)
                    if pm.status != "FINISHED" or pm.home_score is None:
                        continue
                    segments = self._quarters_from_event(event)
                    historical.append(ProviderHistoricalMatch(
                        **pm.__dict__,
                        segments=segments,
                    ))
                except Exception:
                    continue

        logger.info(f"NBA historical: {len(historical)} finished matches")
        return historical

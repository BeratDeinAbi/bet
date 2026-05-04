"""
MLB Provider — offizielle MLB-Stats-API (kostenlos, kein Key).

Endpoints:
  Schedule (heute):
    https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=YYYY-MM-DD
    &hydrate=probablePitcher,team
  Boxscore (Innings + Pitcher-Linescores):
    https://statsapi.mlb.com/api/v1/game/{gameId}/boxscore

Wir holen den Spielplan + die Probable-Pitcher-Hydration für Heute,
und für historische Spiele die Inning-Linescores.  „F5" (erste 5
Innings) wird als Segment gespeichert — das ist der populärste MLB-
Wettmarkt nach Total Runs.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import requests

from app.providers.base import (
    BaseHockeyProvider,
    ProviderHistoricalMatch,
    ProviderMatch,
)

logger = logging.getLogger(__name__)

MLB_BASE = "https://statsapi.mlb.com/api/v1"

FINISHED_STATES = {"Final", "Game Over", "Completed Early"}
LIVE_STATES = {"In Progress", "Manager challenge", "Delayed", "Warmup"}


def _map_status(detailed_state: str) -> str:
    if detailed_state in FINISHED_STATES:
        return "FINISHED"
    if detailed_state in LIVE_STATES:
        return "LIVE"
    if detailed_state in ("Postponed", "Cancelled", "Suspended"):
        return "POSTPONED"
    return "SCHEDULED"


class MLBProvider(BaseHockeyProvider):
    """Sport: ``baseball``, Liga: ``MLB``.  Hängt am gleichen Interface
    wie NHL/NBA — get_today_matches() + get_historical_matches(seasons).
    """

    name = "mlb_statsapi"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SportsPredictionDashboard/1.0",
            "Accept": "application/json",
        })

    def is_available(self) -> bool:
        try:
            r = self.session.get(f"{MLB_BASE}/sports/1", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------
    def _get(self, path: str, params: Optional[Dict] = None) -> Optional[dict]:
        url = f"{MLB_BASE}/{path.lstrip('/')}"
        try:
            r = self.session.get(url, params=params or {}, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"MLB fetch error {path}: {e}")
            return None

    def _schedule(self, target_date: str) -> List[dict]:
        data = self._get("schedule", {
            "sportId": 1,
            "date": target_date,           # YYYY-MM-DD
            # ``probablePitcher(stats(group=pitching,type=season))`` lädt
            # die Saison-ERA des Probable Pitchers direkt mit, sodass wir
            # keinen Extra-Call pro Pitcher brauchen.
            "hydrate": "probablePitcher(stats(group=pitching,type=season)),team",
        }) or {}
        games: List[dict] = []
        for d in data.get("dates", []) or []:
            for g in d.get("games", []) or []:
                games.append(g)
        return games

    # ------------------------------------------------------------------
    # Mapping
    # ------------------------------------------------------------------
    @staticmethod
    def _team_name(t: dict) -> str:
        return t.get("team", {}).get("name") or t.get("team", {}).get("teamName") or "Unknown"

    @staticmethod
    def _team_id(t: dict) -> str:
        return str(t.get("team", {}).get("id") or "")

    @staticmethod
    def _probable_pitcher_era(team_block: dict) -> Optional[float]:
        """Extrahiert Saison-ERA des probable pitchers aus dem Schedule-Hydrate.

        MLB-StatsAPI liefert bei ``hydrate=probablePitcher`` ein ``probablePitcher``-
        Objekt mit ``stats[]`` (für die aktuelle Saison).  Wir greifen auf
        die ``pitching``-Stats zu und holen ``era`` als Float.  Liefert None
        wenn nicht verfügbar (z. B. ganz junger Pitcher ohne Daten).
        """
        pp = team_block.get("probablePitcher") or {}
        for stat in pp.get("stats", []) or []:
            group = (stat.get("group") or {}).get("displayName", "").lower()
            if group != "pitching":
                continue
            splits = stat.get("splits") or []
            if not splits:
                continue
            era_str = (splits[0].get("stat") or {}).get("era")
            try:
                return float(era_str) if era_str else None
            except (TypeError, ValueError):
                return None
        return None

    def _parse_game(self, raw: dict) -> ProviderMatch:
        teams = raw.get("teams", {}) or {}
        home = teams.get("home", {}) or {}
        away = teams.get("away", {}) or {}

        detailed = (raw.get("status", {}) or {}).get("detailedState", "Scheduled")
        status = _map_status(detailed)

        home_score: Optional[int] = None
        away_score: Optional[int] = None
        if status in ("LIVE", "FINISHED"):
            try:
                home_score = int(home.get("score", 0))
                away_score = int(away.get("score", 0))
            except (ValueError, TypeError):
                pass

        pm = ProviderMatch(
            external_id=f"mlb_{raw.get('gamePk', '')}",
            sport="baseball",
            competition_code="MLB",
            competition_name="MLB",
            home_team_name=self._team_name(home),
            away_team_name=self._team_name(away),
            kickoff_time=raw.get("gameDate", ""),
            status=status,
            home_score=home_score,
            away_score=away_score,
            home_team_external_id=self._team_id(home),
            away_team_external_id=self._team_id(away),
        )
        # Pitcher-ERA als zusätzliche Attribute setzen (nicht im Dataclass-
        # Schema → dynamisch).  Vom Prediction-Service via getattr() gelesen.
        setattr(pm, "home_pitcher_era", self._probable_pitcher_era(home))
        setattr(pm, "away_pitcher_era", self._probable_pitcher_era(away))
        return pm

    @staticmethod
    def _segments_from_linescore(linescore: dict) -> List[dict]:
        """Extrahiert F5 (erste 5 Innings) und F9 (Restspiel) als Segmente.

        MLB-Boxscore liefert ``innings[]`` mit pro Inning home/away
        ``runs``-Feld.  Über reguläre 9 Innings hinaus (Extra Innings)
        werden gewertet aber nicht in ein eigenes Segment ausgelagert.
        """
        innings = linescore.get("innings") or []
        if len(innings) < 5:
            return []
        f5_h, f5_a = 0, 0
        late_h, late_a = 0, 0
        for i, inn in enumerate(innings, start=1):
            h = (inn.get("home") or {}).get("runs") or 0
            a = (inn.get("away") or {}).get("runs") or 0
            try:
                h, a = int(h), int(a)
            except (TypeError, ValueError):
                h, a = 0, 0
            if i <= 5:
                f5_h += h
                f5_a += a
            else:
                late_h += h
                late_a += a
        return [
            {"segment_code": "F5", "home_score": f5_h, "away_score": f5_a,
             "total_goals": f5_h + f5_a},
            {"segment_code": "L4", "home_score": late_h, "away_score": late_a,
             "total_goals": late_h + late_a},
        ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_today_matches(self) -> List[ProviderMatch]:
        # MLB-Spiele finden vorrangig abends US-Zeit statt → in der EU
        # nachts.  Wir holen heute + morgen damit europäische User
        # auch das nahende US-Programm sehen.
        today = date.today()
        targets = [
            today.isoformat(),
            (today + timedelta(days=1)).isoformat(),
        ]
        seen: set = set()
        out: List[ProviderMatch] = []
        for t in targets:
            for raw in self._schedule(t):
                gid = raw.get("gamePk")
                if gid in seen:
                    continue
                seen.add(gid)
                try:
                    out.append(self._parse_game(raw))
                except Exception as e:
                    logger.warning(f"MLB parse error: {e}")
        logger.info(f"MLB: {len(out)} games in 2-day window")
        return out

    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        """
        Liefert die letzten ~120 Tage finished games.  120 Tage decken
        eine MLB-Saison (April–Sep) zuverlässig ab; Gesamtcap 100 Spiele
        für Trainings-Effizienz.  Inning-Daten kommen über das
        ``boxscore``-Endpoint (1 Extra-Call pro finished game).
        """
        out: List[ProviderHistoricalMatch] = []
        seen: set = set()
        today = date.today()

        for days_ago in range(2, 121, 2):
            if len(out) >= 100:
                break
            target = (today - timedelta(days=days_ago)).isoformat()
            for raw in self._schedule(target):
                gid = raw.get("gamePk")
                if gid in seen:
                    continue
                seen.add(gid)
                try:
                    pm = self._parse_game(raw)
                    if pm.status != "FINISHED" or pm.home_score is None:
                        continue
                    segments = self._fetch_innings(gid) or []
                    out.append(ProviderHistoricalMatch(
                        **pm.__dict__,
                        segments=segments,
                    ))
                except Exception:
                    continue

        logger.info(f"MLB historical: {len(out)} finished games")
        return out

    def _fetch_innings(self, game_pk: int) -> List[dict]:
        """Holt Inning-Linescores via /game/{gamePk}/linescore."""
        data = self._get(f"game/{game_pk}/linescore")
        if not data:
            return []
        return self._segments_from_linescore(data)

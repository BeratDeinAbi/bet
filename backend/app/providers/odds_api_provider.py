"""
Odds-Provider via The-Odds-API (https://the-odds-api.com).

Free-Tier:
  500 Requests / Monat — reicht bei einem täglichen Refresh aller
  Sportarten locker (5 Ligen × 1× = 5 Req/Tag = 150/Monat).

Endpoint:
  GET /v4/sports/{sport_key}/odds
      ?regions={eu,uk,us,...}
      &markets=totals
      &bookmakers=betano
      &oddsFormat=decimal
      &apiKey={key}

Response-Form (vereinfacht):
  [
    {
      "id": "abc",
      "sport_key": "soccer_germany_bundesliga",
      "commence_time": "2026-05-04T13:30:00Z",
      "home_team": "FC Bayern München",
      "away_team": "Borussia Dortmund",
      "bookmakers": [
        {
          "key": "betano",
          "title": "Betano",
          "last_update": "2026-05-04T11:02:00Z",
          "markets": [
            {
              "key": "totals",
              "outcomes": [
                {"name": "Over",  "price": 1.55, "point": 2.5},
                {"name": "Under", "price": 2.40, "point": 2.5}
              ]
            }
          ]
        }
      ]
    }
  ]

Wir geben pro Spiel + Linie + Direction einen flachen ``OddsLineDict``
zurück, den der Ingestion-Layer auf die ``OddsLine``-Tabelle mappt.
Ein ``commence_time`` und ``home_team``/``away_team`` reisen mit, damit
die Ingestion das Spiel in der DB matchen kann.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List, Optional, TypedDict

import requests

from app.core.config import settings
from app.providers.base import BaseOddsProvider

logger = logging.getLogger(__name__)


class OddsLineDict(TypedDict, total=False):
    sport_key: str
    league_code: str
    home_team: str
    away_team: str
    commence_time: str        # ISO-8601 UTC
    market: str               # immer "Total" im MVP (totals-Markt)
    line: float
    direction: str            # "over" | "under"
    bookmaker: str            # z. B. "betano"
    bookmaker_odds: float
    implied_probability: float


# Liga-Code (DB) → The-Odds-API sport_key
SPORT_KEY_MAP: Dict[str, str] = {
    "BL1": "soccer_germany_bundesliga",
    "BL2": "soccer_germany_bundesliga2",
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "SSL": "soccer_turkey_super_league",
    "NHL": "icehockey_nhl",
    "NBA": "basketball_nba",
    "MLB": "baseball_mlb",
}


# Häufige Präfixe/Suffixe in Team-Namen, die wir beim Matching ignorieren,
# weil sie zwischen Quellen variieren (ESPN vs. OpenLigaDB vs. Odds-API).
_NAME_NOISE = re.compile(
    r"\b(fc|cf|sc|ac|afc|bsc|cd|sv|tsv|tsg|vfb|vfl|fsv|borussia|club|cp)\b",
    re.IGNORECASE,
)
_NON_ALPHANUM = re.compile(r"[^a-z0-9]+")


def _normalize_team_name(name: str) -> str:
    """„FC Bayern München" → „bayernmunchen".

    Kein perfektes Matching, aber gut genug damit „Bayern München"
    (OpenLigaDB) und „FC Bayern München" (Odds-API) das gleiche
    Resultat ergeben.
    """
    if not name:
        return ""
    s = name.lower()
    # Umlaute auf ASCII reduzieren — robuste Variante ohne unicodedata-Import
    s = (s.replace("ä", "a").replace("ö", "o").replace("ü", "u")
           .replace("ß", "ss").replace("é", "e").replace("è", "e")
           .replace("á", "a").replace("í", "i").replace("ó", "o"))
    s = _NAME_NOISE.sub(" ", s)
    s = _NON_ALPHANUM.sub("", s)
    return s


def _market_label_for_totals() -> str:
    """Single source of truth fürs Markt-Label das wir in OddsLine
    schreiben.  Stimmt absichtlich mit dem überein, was
    ``ranking._best_pick_per_match`` als ``cand["market"]`` setzt:
    bei Football „Total", bei Basketball „Total Punkte" usw.

    Aktuell speichert The-Odds-API alle ``totals``-Märkte gleich (egal
    ob Tore/Punkte/Runs).  Wir bekommen das richtige Label im Lookup
    durch ``ranking._candidates_for`` — nicht beim Speichern.  Speichern
    tun wir generisch ``"Total"``.
    """
    return "Total"


class OddsAPIProvider(BaseOddsProvider):
    name = "odds_api"

    def __init__(self):
        self.api_key = settings.ODDS_API_KEY
        self.base_url = settings.ODDS_API_BASE_URL
        self.bookmaker = settings.ODDS_BOOKMAKER
        self.regions = settings.ODDS_API_REGIONS
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "SportsPredictionDashboard/1.0",
            "Accept": "application/json",
        })

    def is_available(self) -> bool:
        return bool(self.api_key)

    # Schnittstelle des BaseOddsProvider — wird von älterem Code benutzt.
    def get_odds(self, sport: str, league_code: str,
                 match_external_id: str) -> List[dict]:  # noqa: ARG002
        """Erfüllt das Base-Interface, aber unsere Ingestion ruft
        direkt ``get_odds_for_sport`` auf — pro-Match-Lookup wäre
        ein API-Call/Match und würde das 500/Monat-Limit zerlegen."""
        if league_code not in SPORT_KEY_MAP:
            return []
        return list(self.get_odds_for_sport(SPORT_KEY_MAP[league_code]))

    def get_odds_for_sport(self, sport_key: str) -> List[OddsLineDict]:
        """Holt Bookmaker-Quoten für eine Sportart.  Pro API-Call ein
        Sport.  Liefert flache Liste von OddsLineDicts."""
        if not self.api_key:
            return []
        url = f"{self.base_url.rstrip('/')}/sports/{sport_key}/odds"
        params = {
            "regions": self.regions,
            "markets": "totals",
            "bookmakers": self.bookmaker,
            "oddsFormat": "decimal",
            "apiKey": self.api_key,
        }
        try:
            r = self.session.get(url, params=params, timeout=10)
            if r.status_code == 401:
                logger.warning("Odds-API: 401 unauthorized — Key prüfen")
                return []
            if r.status_code == 429:
                logger.warning("Odds-API: 429 Rate-Limit erreicht — skip")
                return []
            r.raise_for_status()
        except requests.RequestException as e:
            logger.warning(f"Odds-API: fetch error für {sport_key}: {e}")
            return []

        try:
            events = r.json() or []
        except ValueError as e:
            logger.warning(f"Odds-API: ungültige JSON-Response: {e}")
            return []

        # Liga-Code aus sport_key zurückrechnen (für Ingestion-Match-Lookup)
        league_code = next(
            (lc for lc, sk in SPORT_KEY_MAP.items() if sk == sport_key),
            "",
        )

        out: List[OddsLineDict] = []
        for event in events:
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            commence = event.get("commence_time", "")
            for bm in event.get("bookmakers") or []:
                if (bm.get("key") or "").lower() != self.bookmaker.lower():
                    continue
                for market in bm.get("markets") or []:
                    if (market.get("key") or "") != "totals":
                        continue
                    for outcome in market.get("outcomes") or []:
                        try:
                            line = float(outcome.get("point"))
                            price = float(outcome.get("price"))
                        except (TypeError, ValueError):
                            continue
                        direction_raw = (outcome.get("name") or "").lower()
                        if direction_raw not in ("over", "under"):
                            continue
                        out.append({
                            "sport_key": sport_key,
                            "league_code": league_code,
                            "home_team": home,
                            "away_team": away,
                            "commence_time": commence,
                            "market": _market_label_for_totals(),
                            "line": line,
                            "direction": direction_raw,
                            "bookmaker": self.bookmaker,
                            "bookmaker_odds": price,
                            "implied_probability": round(1.0 / max(price, 1e-6), 4),
                        })
        return out

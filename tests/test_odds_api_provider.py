"""Tests für den The-Odds-API-Provider."""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.providers.odds_api_provider import (
    OddsAPIProvider,
    SPORT_KEY_MAP,
    _normalize_team_name,
)


# ---------------------------------------------------------------------------
# Team-Name-Normalisierung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("FC Bayern München", "Bayern München"),
    ("Borussia Dortmund", "Dortmund"),
    ("Real Madrid CF", "Real Madrid"),
    ("Manchester City FC", "Manchester City"),
])
def test_normalize_makes_variants_match(a, b):
    assert _normalize_team_name(a) == _normalize_team_name(b)


def test_normalize_distinguishes_actually_different_teams():
    assert _normalize_team_name("Bayern München") != _normalize_team_name("Bayer Leverkusen")


# ---------------------------------------------------------------------------
# Sport-Key-Mapping
# ---------------------------------------------------------------------------

def test_sport_key_map_covers_all_active_leagues():
    expected = {"BL1", "BL2", "PL", "PD", "SSL", "NHL", "NBA", "MLB"}
    assert set(SPORT_KEY_MAP.keys()) == expected


# ---------------------------------------------------------------------------
# Response-Parsing
# ---------------------------------------------------------------------------

def _api_event(home="Bayern Munich", away="Dortmund",
               line=2.5, over_price=1.55, under_price=2.40,
               commence="2026-05-04T13:30:00Z"):
    return {
        "id": "abc",
        "sport_key": "soccer_germany_bundesliga",
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "bookmakers": [{
            "key": "betano",
            "title": "Betano",
            "last_update": commence,
            "markets": [{
                "key": "totals",
                "outcomes": [
                    {"name": "Over",  "price": over_price, "point": line},
                    {"name": "Under", "price": under_price, "point": line},
                ],
            }],
        }],
    }


def _mock_response(json_data, status=200):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


@patch("app.providers.odds_api_provider.requests.Session")
def test_get_odds_for_sport_parses_outcomes(mock_session_class, monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "TEST")
    from app.core.config import settings
    settings.ODDS_API_KEY = "TEST"

    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.get.return_value = _mock_response([_api_event()])

    p = OddsAPIProvider()
    lines = p.get_odds_for_sport("soccer_germany_bundesliga")

    # 1 Event × 2 Outcomes (Over/Under) = 2 Linien
    assert len(lines) == 2
    over = next(l for l in lines if l["direction"] == "over")
    assert over["bookmaker"] == "betano"
    assert over["bookmaker_odds"] == 1.55
    assert over["line"] == 2.5
    assert over["league_code"] == "BL1"
    assert abs(over["implied_probability"] - (1 / 1.55)) < 1e-4


@patch("app.providers.odds_api_provider.requests.Session")
def test_get_odds_for_sport_skips_other_bookmakers(mock_session_class, monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "TEST")
    from app.core.config import settings
    settings.ODDS_API_KEY = "TEST"

    mock_session = MagicMock()
    mock_session_class.return_value = mock_session

    event = _api_event()
    # Andere Bookmaker zusätzlich — die müssen ignoriert werden
    event["bookmakers"].append({
        "key": "bet365",
        "title": "Bet365",
        "markets": [{"key": "totals", "outcomes": [
            {"name": "Over", "price": 1.50, "point": 2.5},
        ]}],
    })
    mock_session.get.return_value = _mock_response([event])

    p = OddsAPIProvider()
    lines = p.get_odds_for_sport("soccer_germany_bundesliga")
    assert all(l["bookmaker"] == "betano" for l in lines)
    assert len(lines) == 2  # nur die Betano-Outcomes


@patch("app.providers.odds_api_provider.requests.Session")
def test_get_odds_returns_empty_on_429(mock_session_class, monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "TEST")
    from app.core.config import settings
    settings.ODDS_API_KEY = "TEST"

    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    mock_session.get.return_value = _mock_response([], status=429)

    p = OddsAPIProvider()
    assert p.get_odds_for_sport("soccer_germany_bundesliga") == []


def test_get_odds_returns_empty_without_key(monkeypatch):
    monkeypatch.setenv("ODDS_API_KEY", "")
    from app.core.config import settings
    settings.ODDS_API_KEY = ""

    p = OddsAPIProvider()
    assert p.is_available() is False
    assert p.get_odds_for_sport("soccer_germany_bundesliga") == []

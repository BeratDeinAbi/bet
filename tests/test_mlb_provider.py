"""Tests für den MLB-Provider (statsapi.mlb.com)."""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.providers.mlb_provider import MLBProvider, _map_status


def _sample_game(game_pk=1, home="Yankees", away="Red Sox",
                 home_score=5, away_score=3,
                 detailed_state="Final",
                 game_date="2025-04-15T23:05:00Z"):
    return {
        "gamePk": game_pk,
        "gameDate": game_date,
        "status": {"detailedState": detailed_state},
        "teams": {
            "home": {"score": home_score, "team": {"id": 147, "name": home}},
            "away": {"score": away_score, "team": {"id": 111, "name": away}},
        },
    }


def test_map_status_finished():
    assert _map_status("Final") == "FINISHED"
    assert _map_status("Game Over") == "FINISHED"
    assert _map_status("In Progress") == "LIVE"
    assert _map_status("Postponed") == "POSTPONED"
    assert _map_status("Scheduled") == "SCHEDULED"


def test_parse_game_finished():
    p = MLBProvider()
    pm = p._parse_game(_sample_game())
    assert pm.external_id == "mlb_1"
    assert pm.sport == "baseball"
    assert pm.competition_code == "MLB"
    assert pm.home_team_name == "Yankees"
    assert pm.away_team_name == "Red Sox"
    assert pm.home_score == 5
    assert pm.away_score == 3
    assert pm.status == "FINISHED"


def test_parse_game_scheduled_no_score():
    p = MLBProvider()
    pm = p._parse_game(_sample_game(detailed_state="Scheduled",
                                    home_score=0, away_score=0))
    assert pm.status == "SCHEDULED"
    assert pm.home_score is None
    assert pm.away_score is None


def test_segments_from_linescore_f5_late():
    linescore = {
        "innings": [
            {"home": {"runs": 1}, "away": {"runs": 0}},
            {"home": {"runs": 0}, "away": {"runs": 2}},
            {"home": {"runs": 1}, "away": {"runs": 0}},
            {"home": {"runs": 0}, "away": {"runs": 0}},
            {"home": {"runs": 1}, "away": {"runs": 1}},  # F5 endet hier
            {"home": {"runs": 2}, "away": {"runs": 0}},  # später
            {"home": {"runs": 0}, "away": {"runs": 0}},
            {"home": {"runs": 0}, "away": {"runs": 0}},
            {"home": {"runs": 0}, "away": {"runs": 0}},
        ],
    }
    segs = MLBProvider._segments_from_linescore(linescore)
    assert len(segs) == 2
    f5 = next(s for s in segs if s["segment_code"] == "F5")
    late = next(s for s in segs if s["segment_code"] == "L4")
    assert f5["home_score"] == 3   # 1+0+1+0+1
    assert f5["away_score"] == 3   # 0+2+0+0+1
    assert late["home_score"] == 2
    assert late["away_score"] == 0


def test_segments_empty_for_short_games():
    """Wenn weniger als 5 Innings → keine Segmente (corrupt/abandoned game)."""
    short = {"innings": [{"home": {"runs": 0}, "away": {"runs": 0}}]}
    assert MLBProvider._segments_from_linescore(short) == []


def test_get_today_matches_dedups_2day_window():
    p = MLBProvider()
    today_game = _sample_game(game_pk=10)
    tomorrow_game = _sample_game(game_pk=20)
    with patch.object(p, "_schedule") as mocked:
        mocked.side_effect = [
            [today_game, tomorrow_game],   # heute
            [today_game],                   # morgen — schon gesehen
        ]
        result = p.get_today_matches()
    assert mocked.call_count == 2
    ids = [m.external_id for m in result]
    assert ids == ["mlb_10", "mlb_20"]


def test_get_historical_only_finished():
    p = MLBProvider()
    finished = _sample_game(game_pk=99, detailed_state="Final")
    scheduled = _sample_game(game_pk=100, detailed_state="Scheduled",
                             home_score=0, away_score=0)
    with patch.object(p, "_schedule", return_value=[finished, scheduled]):
        with patch.object(p, "_fetch_innings", return_value=[]):
            hist = p.get_historical_matches(["2024"])
    ids = [h.external_id for h in hist]
    assert "mlb_99" in ids
    assert "mlb_100" not in ids

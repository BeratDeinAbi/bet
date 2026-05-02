"""Tests for OpenLigaDB football provider (Bundesliga / 2. Bundesliga)."""
import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.providers.openligadb_provider import (
    LEAGUE_MAP,
    OpenLigaDBProvider,
    _fulltime,
    _halftime,
)


def _sample_match(match_id=1, finished=True, kickoff="2025-08-22T18:30:00Z",
                  team1="Bayern München", team2="Borussia Dortmund",
                  ft=(3, 1), ht=(1, 0)):
    return {
        "matchID": match_id,
        "matchDateTime": kickoff.replace("Z", ""),
        "matchDateTimeUTC": kickoff,
        "matchIsFinished": finished,
        "leagueShortcut": "bl1",
        "leagueSeason": 2025,
        "team1": {"teamId": 100, "teamName": team1},
        "team2": {"teamId": 200, "teamName": team2},
        "matchResults": [
            {"resultName": "Halbzeit", "pointsTeam1": ht[0], "pointsTeam2": ht[1], "resultOrderID": 1},
            {"resultName": "Endergebnis", "pointsTeam1": ft[0], "pointsTeam2": ft[1], "resultOrderID": 2},
        ],
    }


def test_league_map_contains_bl1_bl2():
    assert "BL1" in LEAGUE_MAP
    assert "BL2" in LEAGUE_MAP
    assert LEAGUE_MAP["BL1"]["slug"] == "bl1"
    assert LEAGUE_MAP["BL2"]["slug"] == "bl2"


def test_supports():
    p = OpenLigaDBProvider()
    assert p.supports("BL1")
    assert p.supports("BL2")
    assert not p.supports("PL")
    assert not p.supports("NHL")


def test_fulltime_picks_endergebnis():
    raw = _sample_match(ft=(2, 0), ht=(1, 0))
    ft = _fulltime(raw)
    assert ft is not None
    assert ft["pointsTeam1"] == 2
    assert ft["pointsTeam2"] == 0


def test_halftime_extraction():
    raw = _sample_match(ht=(1, 1))
    ht = _halftime(raw)
    assert ht is not None
    assert ht["pointsTeam1"] == 1
    assert ht["pointsTeam2"] == 1


def test_parse_match_finished():
    p = OpenLigaDBProvider()
    pm = p._parse_match(_sample_match(), "BL1")
    assert pm.external_id == "oldb_1"
    assert pm.sport == "football"
    assert pm.competition_code == "BL1"
    assert pm.competition_name == "Bundesliga"
    assert pm.home_team_name == "Bayern München"
    assert pm.away_team_name == "Borussia Dortmund"
    assert pm.home_score == 3
    assert pm.away_score == 1
    assert pm.status == "FINISHED"


def test_parse_match_scheduled_future():
    p = OpenLigaDBProvider()
    raw = _sample_match(finished=False, kickoff="2099-01-01T18:00:00Z", ft=(0, 0), ht=(0, 0))
    pm = p._parse_match(raw, "BL2")
    assert pm.competition_code == "BL2"
    assert pm.competition_name == "2. Bundesliga"
    assert pm.status == "SCHEDULED"


def test_segments_from_match():
    p = OpenLigaDBProvider()
    raw = _sample_match(ft=(3, 1), ht=(1, 0))
    segs = p._segments_from_match(raw)
    assert len(segs) == 2
    h1 = next(s for s in segs if s["segment_code"] == "H1")
    h2 = next(s for s in segs if s["segment_code"] == "H2")
    assert h1["home_score"] == 1 and h1["away_score"] == 0
    assert h2["home_score"] == 2 and h2["away_score"] == 1


def test_get_today_matches_filters_by_date():
    p = OpenLigaDBProvider()
    today = datetime.now(timezone.utc).replace(hour=18, minute=30, second=0, microsecond=0)
    today_iso = today.strftime("%Y-%m-%dT%H:%M:%SZ")
    yesterday_iso = "2000-01-01T18:00:00Z"

    payload = [
        _sample_match(match_id=1, kickoff=today_iso, finished=False, ft=(0, 0), ht=(0, 0)),
        _sample_match(match_id=2, kickoff=yesterday_iso, finished=True),
    ]

    with patch.object(p, "_get", return_value=payload) as mocked:
        result = p.get_today_matches(["BL1", "BL2", "PL"])

    # PL is unsupported and gets ignored, both supported leagues query OpenLigaDB
    assert mocked.call_count == 2
    # Each league call returns the same payload, so we expect 2× match_id=1
    assert all(m.external_id == "oldb_1" for m in result)
    assert len(result) == 2


def test_get_historical_matches_only_finished():
    p = OpenLigaDBProvider()
    payload = [
        _sample_match(match_id=10, finished=True, ft=(2, 1), ht=(1, 0)),
        _sample_match(match_id=11, finished=False, ft=(0, 0), ht=(0, 0)),
        _sample_match(match_id=12, finished=True, ft=(0, 0), ht=(0, 0)),
    ]
    with patch.object(p, "_get", return_value=payload):
        hist = p.get_historical_matches("BL1", ["2024"])

    ids = [h.external_id for h in hist]
    assert "oldb_10" in ids
    assert "oldb_12" in ids
    assert "oldb_11" not in ids
    finished = next(h for h in hist if h.external_id == "oldb_10")
    assert len(finished.segments) == 2


def test_get_historical_matches_unsupported_league():
    p = OpenLigaDBProvider()
    assert p.get_historical_matches("PL", ["2024"]) == []

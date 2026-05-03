"""Tests für den NBA-Provider (ESPN-basiert)."""
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.providers.nba_provider import NBAProvider


def _sample_event(event_id="401", home="Lakers", away="Celtics",
                  home_score="118", away_score="112",
                  status_name="STATUS_FINAL",
                  date_str="2025-01-15T01:00Z",
                  with_quarters=True):
    home_lines = [{"value": 30}, {"value": 28}, {"value": 32}, {"value": 28}] if with_quarters else []
    away_lines = [{"value": 26}, {"value": 30}, {"value": 28}, {"value": 28}] if with_quarters else []
    return {
        "id": event_id,
        "date": date_str,
        "competitions": [{
            "status": {"type": {"name": status_name}},
            "competitors": [
                {
                    "homeAway": "home",
                    "score": home_score,
                    "team": {"id": "13", "displayName": home},
                    "linescores": home_lines,
                },
                {
                    "homeAway": "away",
                    "score": away_score,
                    "team": {"id": "2", "displayName": away},
                    "linescores": away_lines,
                },
            ],
        }],
    }


def test_parse_event_finished():
    p = NBAProvider()
    pm = p._parse_event(_sample_event())
    assert pm.external_id == "nba_401"
    assert pm.sport == "basketball"
    assert pm.competition_code == "NBA"
    assert pm.home_team_name == "Lakers"
    assert pm.away_team_name == "Celtics"
    assert pm.home_score == 118
    assert pm.away_score == 112
    assert pm.status == "FINISHED"


def test_parse_event_scheduled_no_score():
    p = NBAProvider()
    raw = _sample_event(status_name="STATUS_SCHEDULED",
                        home_score="0", away_score="0", with_quarters=False)
    pm = p._parse_event(raw)
    assert pm.status == "SCHEDULED"
    assert pm.home_score is None
    assert pm.away_score is None


def test_quarters_extracted_correctly():
    quarters = NBAProvider._quarters_from_event(_sample_event())
    assert len(quarters) == 4
    codes = [q["segment_code"] for q in quarters]
    assert codes == ["Q1", "Q2", "Q3", "Q4"]
    # Test summing matches box score
    total_home = sum(q["home_score"] for q in quarters)
    total_away = sum(q["away_score"] for q in quarters)
    assert total_home == 118
    assert total_away == 112


def test_quarters_empty_when_no_linescores():
    raw = _sample_event(with_quarters=False)
    quarters = NBAProvider._quarters_from_event(raw)
    assert quarters == []


def test_get_today_matches_dedups_2day_window():
    """Provider holt heute + morgen — Spiele dürfen nicht doppelt rein."""
    p = NBAProvider()
    today_event = _sample_event(event_id="100")
    tomorrow_event = _sample_event(event_id="200")
    with patch.object(p, "_get_scoreboard") as mocked:
        mocked.side_effect = [
            [today_event, tomorrow_event],   # heute
            [today_event],                    # morgen — schon gesehen
        ]
        result = p.get_today_matches()
    assert mocked.call_count == 2
    ids = [m.external_id for m in result]
    assert ids == ["nba_100", "nba_200"]


def test_get_historical_only_finished_with_quarters():
    p = NBAProvider()
    finished = _sample_event(event_id="900")
    scheduled = _sample_event(event_id="901", status_name="STATUS_SCHEDULED",
                              home_score="0", away_score="0", with_quarters=False)

    with patch.object(p, "_get_scoreboard", return_value=[finished, scheduled]):
        hist = p.get_historical_matches(["2024"])

    ids = [h.external_id for h in hist]
    assert "nba_900" in ids
    assert "nba_901" not in ids
    finished_match = next(h for h in hist if h.external_id == "nba_900")
    assert len(finished_match.segments) == 4

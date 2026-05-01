"""Tests for mock data providers."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.providers.mock_provider import MockFootballProvider, MockHockeyProvider


def test_mock_football_today():
    provider = MockFootballProvider()
    matches = provider.get_today_matches(["BL1", "PL", "PD", "SSL"])
    assert len(matches) > 0
    for m in matches:
        assert m.sport == "football"
        assert m.competition_code in ["BL1", "PL", "PD", "SSL"]
        assert m.home_team_name
        assert m.away_team_name
        assert m.kickoff_time


def test_mock_football_filter():
    provider = MockFootballProvider()
    matches = provider.get_today_matches(["BL1"])
    assert all(m.competition_code == "BL1" for m in matches)


def test_mock_football_historical():
    provider = MockFootballProvider()
    matches = provider.get_historical_matches("BL1", ["2024"])
    assert len(matches) > 5
    for m in matches:
        assert m.home_score is not None
        assert m.away_score is not None
        assert len(m.segments) == 2


def test_mock_hockey_today():
    provider = MockHockeyProvider()
    matches = provider.get_today_matches()
    assert len(matches) > 0
    for m in matches:
        assert m.sport == "hockey"
        assert m.competition_code == "NHL"


def test_mock_hockey_historical():
    provider = MockHockeyProvider()
    matches = provider.get_historical_matches(["2024"])
    assert len(matches) > 10
    for m in matches:
        assert len(m.segments) == 3
        period_codes = [s["segment_code"] for s in m.segments]
        assert "P1" in period_codes
        assert "P2" in period_codes
        assert "P3" in period_codes

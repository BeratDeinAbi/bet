"""Tests for NHL hockey prediction models."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from ml.models.hockey_model import (
    NHLTeamStrengthModel, NHLEloModel, NHLPeriodModel, NHLEnsemble
)

SAMPLE_MATCHES = [
    {"home_team": "Bruins", "away_team": "Leafs", "home_score": 4, "away_score": 2,
     "segments": [
         {"segment_code": "P1", "home_score": 1, "away_score": 1, "total_goals": 2},
         {"segment_code": "P2", "home_score": 2, "away_score": 0, "total_goals": 2},
         {"segment_code": "P3", "home_score": 1, "away_score": 1, "total_goals": 2},
     ]},
    {"home_team": "Leafs", "away_team": "Bruins", "home_score": 3, "away_score": 5,
     "segments": [
         {"segment_code": "P1", "home_score": 1, "away_score": 2, "total_goals": 3},
         {"segment_code": "P2", "home_score": 1, "away_score": 2, "total_goals": 3},
         {"segment_code": "P3", "home_score": 1, "away_score": 1, "total_goals": 2},
     ]},
    {"home_team": "Avs", "away_team": "Bruins", "home_score": 6, "away_score": 3,
     "segments": [
         {"segment_code": "P1", "home_score": 2, "away_score": 1, "total_goals": 3},
         {"segment_code": "P2", "home_score": 2, "away_score": 1, "total_goals": 3},
         {"segment_code": "P3", "home_score": 2, "away_score": 1, "total_goals": 3},
     ]},
    {"home_team": "Bruins", "away_team": "Avs", "home_score": 2, "away_score": 4,
     "segments": [
         {"segment_code": "P1", "home_score": 1, "away_score": 1, "total_goals": 2},
         {"segment_code": "P2", "home_score": 0, "away_score": 2, "total_goals": 2},
         {"segment_code": "P3", "home_score": 1, "away_score": 1, "total_goals": 2},
     ]},
    {"home_team": "Leafs", "away_team": "Avs", "home_score": 1, "away_score": 3,
     "segments": [
         {"segment_code": "P1", "home_score": 0, "away_score": 1, "total_goals": 1},
         {"segment_code": "P2", "home_score": 0, "away_score": 1, "total_goals": 1},
         {"segment_code": "P3", "home_score": 1, "away_score": 1, "total_goals": 2},
     ]},
]


def test_nhl_team_strength_fits():
    model = NHLTeamStrengthModel()
    model.fit(SAMPLE_MATCHES)
    assert model.fitted
    lh, la = model.predict_lambdas("Bruins", "Leafs")
    assert lh > 0
    assert la > 0


def test_nhl_elo_model():
    model = NHLEloModel()
    model.fit(SAMPLE_MATCHES)
    ratio = model.strength_ratio("Bruins", "Leafs")
    assert isinstance(ratio, float)
    assert ratio > 0


def test_nhl_period_model():
    model = NHLPeriodModel()
    model.fit(SAMPLE_MATCHES)
    assert model.fitted
    preds = model.predict(5.5)
    total = preds["expected_goals_p1"] + preds["expected_goals_p2"] + preds["expected_goals_p3"]
    assert total == pytest.approx(5.5, abs=0.05)
    assert 0 < preds["prob_over_0_5_p1"] < 1


def test_nhl_ensemble_predict():
    ensemble = NHLEnsemble()
    ensemble.fit(SAMPLE_MATCHES)
    result = ensemble.predict("Bruins", "Leafs")
    assert "expected_total_goals" in result
    assert "expected_goals_p1" in result
    assert "prob_over_0_5_p1" in result
    assert result["expected_total_goals"] > 0
    assert 0 < result["prob_over_0_5_p1"] < 1

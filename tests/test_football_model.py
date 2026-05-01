"""Tests for football prediction models."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from ml.models.football_model import (
    TeamStrengthModel, EloModel, HalfTimeModel,
    FootballEnsemble, poisson_prob_over, total_goals_probs_from_grid,
    dixon_coles_rho,
)

SAMPLE_MATCHES = [
    {"home_team": "Bayern", "away_team": "Dortmund", "home_score": 3, "away_score": 1,
     "segments": [{"segment_code": "H1", "home_score": 2, "away_score": 0, "total_goals": 2},
                  {"segment_code": "H2", "home_score": 1, "away_score": 1, "total_goals": 2}]},
    {"home_team": "Dortmund", "away_team": "Bayern", "home_score": 0, "away_score": 1,
     "segments": [{"segment_code": "H1", "home_score": 0, "away_score": 0, "total_goals": 0},
                  {"segment_code": "H2", "home_score": 0, "away_score": 1, "total_goals": 1}]},
    {"home_team": "Bayern", "away_team": "Leverkusen", "home_score": 2, "away_score": 2,
     "segments": [{"segment_code": "H1", "home_score": 1, "away_score": 1, "total_goals": 2},
                  {"segment_code": "H2", "home_score": 1, "away_score": 1, "total_goals": 2}]},
    {"home_team": "Leverkusen", "away_team": "Dortmund", "home_score": 1, "away_score": 0,
     "segments": [{"segment_code": "H1", "home_score": 1, "away_score": 0, "total_goals": 1},
                  {"segment_code": "H2", "home_score": 0, "away_score": 0, "total_goals": 0}]},
    {"home_team": "Dortmund", "away_team": "Leverkusen", "home_score": 2, "away_score": 3,
     "segments": [{"segment_code": "H1", "home_score": 1, "away_score": 2, "total_goals": 3},
                  {"segment_code": "H2", "home_score": 1, "away_score": 1, "total_goals": 2}]},
]


def test_poisson_prob_over():
    p = poisson_prob_over(2.5, 2.5)
    assert 0 < p < 1
    assert poisson_prob_over(5.0, 2.5) > poisson_prob_over(1.0, 2.5)


def test_dixon_coles_grid_sums_to_one():
    grid = dixon_coles_rho(1.4, 1.1)
    assert abs(grid.sum() - 1.0) < 1e-6


def test_total_goals_probs_valid():
    from ml.models.football_model import dixon_coles_rho
    grid = dixon_coles_rho(1.5, 1.2)
    probs = total_goals_probs_from_grid(grid)
    for key, val in probs.items():
        assert 0 < val < 1, f"{key}={val} out of range"


def test_team_strength_model_fits():
    model = TeamStrengthModel(league_code="BL1")
    model.fit(SAMPLE_MATCHES)
    lam_h, lam_a = model.predict_lambdas("Bayern", "Dortmund")
    assert lam_h > 0
    assert lam_a > 0


def test_elo_model_updates_ratings():
    model = EloModel()
    model.fit(SAMPLE_MATCHES)
    assert "Bayern" in model.ratings
    assert "Dortmund" in model.ratings
    diff = model.get_diff("Bayern", "Dortmund")
    assert diff > 0  # Bayern should be stronger


def test_halftime_model():
    model = HalfTimeModel(league_code="BL1")
    model.fit(SAMPLE_MATCHES)
    preds = model.predict(2.5)
    assert "expected_goals_h1" in preds
    assert "expected_goals_h2" in preds
    assert preds["expected_goals_h1"] + preds["expected_goals_h2"] == pytest.approx(2.5, abs=0.01)


def test_football_ensemble_predict():
    ensemble = FootballEnsemble("BL1")
    ensemble.fit(SAMPLE_MATCHES)
    result = ensemble.predict("Bayern", "Dortmund")
    assert "expected_total_goals" in result
    assert "prob_over_2_5" in result
    assert "expected_goals_h1" in result
    assert 0 < result["expected_total_goals"] < 15
    assert 0 < result["prob_over_2_5"] < 1


def test_ensemble_unfitted_fallback():
    ensemble = FootballEnsemble("BL1")
    # Should not crash with default values
    result = ensemble.predict("TeamA", "TeamB")
    assert "expected_total_goals" in result

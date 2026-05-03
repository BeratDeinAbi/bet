"""Tests für das MLB-Vorhersagemodell."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.models.mlb_model import (
    F5_LINES,
    MLBEloModel,
    MLBEnsemble,
    MLBF5Model,
    MLBRollingForm,
    MLBTeamStrengthModel,
    MLB_PRIOR,
    TOTAL_LINES,
    poisson_prob_over,
)

TEAMS = ["Yankees", "Red Sox", "Dodgers", "Giants"]


def _sample_matches(n=80, seed=11):
    rng = random.Random(seed)
    matches = []
    base_year = 2024
    for i in range(n):
        h = rng.choice(TEAMS)
        a = rng.choice([t for t in TEAMS if t != h])
        # Poisson-typisch: ~4.5 Runs pro Team
        hs = rng.choices(range(0, 13), weights=[4, 8, 10, 11, 10, 8, 6, 4, 3, 2, 1, 1, 1])[0]
        as_ = rng.choices(range(0, 13), weights=[5, 9, 11, 11, 10, 8, 5, 4, 3, 2, 1, 1, 1])[0]
        total = hs + as_
        # F5: ungefähr 55% der Runs
        f5 = max(0, min(total, int(round(total * 0.55))))
        # Splitting auf home/away anhand Score-Verhältnis
        if total > 0:
            f5_h = round(f5 * (hs / total))
            f5_a = f5 - f5_h
        else:
            f5_h = f5_a = 0
        matches.append({
            "home_team": h,
            "away_team": a,
            "home_score": hs,
            "away_score": as_,
            "kickoff_time": f"{base_year}-06-{(i % 28) + 1:02d}T19:00:00Z",
            "segments": [
                {"segment_code": "F5", "home_score": f5_h, "away_score": f5_a,
                 "total_goals": f5_h + f5_a},
                {"segment_code": "L4", "home_score": hs - f5_h, "away_score": as_ - f5_a,
                 "total_goals": (hs - f5_h) + (as_ - f5_a)},
            ],
        })
    return matches


def test_poisson_prob_monotonic():
    p_low = poisson_prob_over(9.0, 6.5)
    p_mid = poisson_prob_over(9.0, 8.5)
    p_high = poisson_prob_over(9.0, 11.5)
    assert p_low > p_mid > p_high
    assert 0 <= p_high <= p_mid <= p_low <= 1


def test_team_strength_fits_and_predicts():
    model = MLBTeamStrengthModel()
    model.fit(_sample_matches(80))
    assert model.fitted
    lam_h, lam_a = model.predict_lambdas("Yankees", "Red Sox")
    assert 1.0 <= lam_h <= 8.0
    assert 1.0 <= lam_a <= 8.0
    # Sample-Daten haben keinen eingebauten Heim-Boost — nur Sanity:
    # Wert plausibel im Bereich.
    assert 0.5 < model.home_advantage < 1.5


def test_elo_updates():
    elo = MLBEloModel()
    elo.fit(_sample_matches(40))
    for t in TEAMS:
        assert t in elo.ratings


def test_f5_model_ratio_in_bounds():
    f5 = MLBF5Model()
    f5.fit(_sample_matches(80))
    assert 0.30 <= f5.f5_ratio <= 0.80


def test_f5_predict_keys_and_ranges():
    f5 = MLBF5Model()
    out = f5.predict(expected_total=8.5)
    assert "expected_runs_f5" in out
    for line in F5_LINES:
        lk = str(line).replace(".", "_")
        assert f"prob_over_{lk}_f5" in out
        assert f"prob_under_{lk}_f5" in out
        assert 0.001 <= out[f"prob_over_{lk}_f5"] <= 0.999


def test_ensemble_predict_full_output():
    ens = MLBEnsemble()
    ens.fit(_sample_matches(80))
    out = ens.predict("Yankees", "Red Sox")
    # Total Runs vernünftig
    assert 5 < out["expected_total_runs"] < 16
    # Linien
    for line in TOTAL_LINES:
        lk = str(line).replace(".", "_")
        assert f"prob_over_{lk}" in out
        assert 0.001 <= out[f"prob_over_{lk}"] <= 0.999
    # F5
    assert "expected_runs_f5" in out
    # Pitcher-Faktoren default 1.0
    assert out["pitcher_factor_home"] == 1.0
    assert out["pitcher_factor_away"] == 1.0


def test_pitcher_era_lowers_opponent_runs():
    """Ein Auswärts-Pitcher mit besserer ERA als Liga senkt Heim-Runs."""
    ens = MLBEnsemble()
    ens.fit(_sample_matches(80))
    base = ens.predict("Yankees", "Red Sox")
    with_ace = ens.predict("Yankees", "Red Sox",
                           home_pitcher_era=4.20,    # Liga-Avg
                           away_pitcher_era=2.50)    # Top-Ace
    # Der Ace pitcht für Auswärts → senkt Heim-Runs
    assert with_ace["expected_home_runs"] < base["expected_home_runs"]


def test_ensemble_too_few_matches_uses_priors():
    ens = MLBEnsemble()
    ens.fit(_sample_matches(3))  # < 10
    out = ens.predict("Yankees", "Red Sox")
    # Priors müssen irgendetwas Vernünftiges liefern
    assert out["expected_total_runs"] > 5

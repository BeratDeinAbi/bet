"""Tests für das NBA-Vorhersagemodell."""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ml.models.nba_model import (
    NBAEnsemble,
    NBAEloModel,
    NBAQuarterModel,
    NBARollingForm,
    NBATeamStrengthModel,
    NBA_PRIOR,
    QUARTER_LINES,
    TOTAL_LINES,
    normal_prob_over,
)

TEAMS = ["Lakers", "Celtics", "Warriors", "Nuggets"]


def _sample_matches(n: int = 60, seed: int = 7):
    rng = random.Random(seed)
    matches = []
    base_year = 2024
    for i in range(n):
        h = rng.choice(TEAMS)
        a = rng.choice([t for t in TEAMS if t != h])
        hs = max(85, int(rng.gauss(114, 11)))
        as_ = max(85, int(rng.gauss(110, 11)))
        # 4 Quarter splits, sum = total
        rem_h, rem_a = hs, as_
        segments = []
        for q in range(1, 5):
            if q < 4:
                qh = max(15, int(rng.gauss(hs / 4, 3)))
                qa = max(15, int(rng.gauss(as_ / 4, 3)))
                qh = min(qh, rem_h - 15 * (4 - q))
                qa = min(qa, rem_a - 15 * (4 - q))
                qh = max(qh, 15)
                qa = max(qa, 15)
            else:
                qh, qa = rem_h, rem_a
            rem_h -= qh
            rem_a -= qa
            segments.append({
                "segment_code": f"Q{q}",
                "home_score": qh,
                "away_score": qa,
                "total_goals": qh + qa,
            })
        matches.append({
            "home_team": h, "away_team": a,
            "home_score": hs, "away_score": as_,
            "kickoff_time": f"{base_year}-11-{(i % 28) + 1:02d}T19:30:00Z",
            "segments": segments,
        })
    return matches


def test_normal_prob_over_monotonic():
    # Höhere Linie → niedrigere Wahrscheinlichkeit
    p_low = normal_prob_over(225, 18, 200.5)
    p_mid = normal_prob_over(225, 18, 220.5)
    p_high = normal_prob_over(225, 18, 240.5)
    assert p_low > p_mid > p_high
    assert 0.0 <= p_high <= p_mid <= p_low <= 1.0


def test_normal_prob_over_centered():
    # Bei mean = line muss prob ≈ 0.5 sein
    p = normal_prob_over(220.5, 18, 220.5)
    assert 0.45 <= p <= 0.55


def test_team_strength_fits_and_predicts():
    model = NBATeamStrengthModel()
    model.fit(_sample_matches(80))
    assert model.fitted
    mu_h, mu_a = model.predict_means("Lakers", "Celtics")
    # NBA-typisch: zwischen 90 und 130 Punkten pro Team
    assert 90 <= mu_h <= 135
    assert 90 <= mu_a <= 135
    # Heimvorteil > 0
    assert model.home_advantage >= 1.0


def test_elo_updates_ratings():
    elo = NBAEloModel()
    elo.fit(_sample_matches(40))
    # Alle Teams haben Ratings
    for t in TEAMS:
        assert t in elo.ratings


def test_quarter_model_ratios_sum_to_one():
    qm = NBAQuarterModel()
    qm.fit(_sample_matches(60))
    total_ratio = sum(qm.ratios.values())
    assert abs(total_ratio - 1.0) < 0.05


def test_quarter_model_predict_keys():
    qm = NBAQuarterModel()
    pred = qm.predict(expected_total=224.0)
    # Erwartete Keys: expected_points_q1..q4 + prob_over/under für jede Linie
    for q in ("q1", "q2", "q3", "q4"):
        assert f"expected_points_{q}" in pred
        for line in QUARTER_LINES:
            lk = str(line).replace(".", "_")
            assert f"prob_over_{lk}_{q}" in pred
            assert f"prob_under_{lk}_{q}" in pred


def test_ensemble_predict_full_output():
    ens = NBAEnsemble()
    ens.fit(_sample_matches(80))
    out = ens.predict("Lakers", "Celtics")

    # Total
    assert 180 < out["expected_total_points"] < 280
    # Total-Linien
    for line in TOTAL_LINES:
        lk = str(line).replace(".", "_")
        assert f"prob_over_{lk}" in out
        assert f"prob_under_{lk}" in out
        # Wahrscheinlichkeiten sind Wahrscheinlichkeiten
        assert 0.001 <= out[f"prob_over_{lk}"] <= 0.999
    # Quarters
    for q in ("q1", "q2", "q3", "q4"):
        assert f"expected_points_{q}" in out
    # Agreement-Score
    assert 0.0 <= out["model_agreement_score"] <= 1.0


def test_ensemble_total_equals_quarters_sum():
    ens = NBAEnsemble()
    ens.fit(_sample_matches(80))
    out = ens.predict("Lakers", "Warriors")
    quarters_sum = sum(out[f"expected_points_q{i}"] for i in range(1, 5))
    # Quarters müssen ~Total ergeben (Rundungsfehler erlaubt)
    assert abs(quarters_sum - out["expected_total_points"]) < 1.0


def test_ensemble_with_too_few_matches_uses_priors():
    """Ensemble darf bei wenig Daten nicht crashen, aber liefert Priors."""
    ens = NBAEnsemble()
    ens.fit(_sample_matches(3))  # < 10 → strength model fällt auf Priors zurück
    out = ens.predict("Lakers", "Celtics")
    # Mindestens irgendwas vernünftiges (Priors greifen)
    assert out["expected_total_points"] > 100

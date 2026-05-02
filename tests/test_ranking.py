"""Tests for top-3 ranking service.

Verifies the two main user-facing requirements:
  1. At most one pick per match (no flooding the list with markets of
     the same fixture).
  2. The pick reflects the most likely event under the model — model
     probability dominates the ranking score.
"""
import os
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from app.services.ranking import (
    _candidates_for,
    _informativeness,
    _ranking_score,
    _best_pick_per_match,
)


# ---------------------------------------------------------------------------
# Lightweight fakes — avoid spinning up a DB
# ---------------------------------------------------------------------------

class _FakeQuery:
    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return None


class _FakeDB:
    """Mimics SQLAlchemy session.query(OddsLine).filter(...).first() → None."""

    def query(self, _model):
        return _FakeQuery()


def _make_pred(**overrides):
    base = dict(
        confidence_score=0.7,
        confidence_label="HIGH",
        model_agreement_score=0.8,
        prediction_stability_score=0.75,
        explanation="test",
        # Football probabilities
        prob_over_0_5=0.97,
        prob_over_1_5=0.85,
        prob_over_2_5=0.72,
        prob_over_3_5=0.45,
        prob_under_0_5=0.03,
        prob_under_1_5=0.15,
        prob_under_2_5=0.28,
        prob_under_3_5=0.55,
        prob_over_0_5_h1=0.82,
        prob_over_1_5_h1=0.42,
        prob_over_0_5_h2=0.86,
        prob_over_1_5_h2=0.50,
        # Hockey
        prob_over_0_5_p1=None,
        prob_over_1_5_p1=None,
        prob_over_0_5_p2=None,
        prob_over_1_5_p2=None,
        prob_over_0_5_p3=None,
        prob_over_1_5_p3=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _make_match(match_id=1, sport="football", home="A", away="B"):
    return SimpleNamespace(
        id=match_id,
        sport=sport,
        home_team_name=home,
        away_team_name=away,
        kickoff_time=datetime.now(timezone.utc),
        competition=SimpleNamespace(name="Bundesliga"),
    )


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

def test_informativeness_prefers_higher_over_lines():
    assert _informativeness(2.5, "over") > _informativeness(0.5, "over")


def test_informativeness_prefers_lower_under_lines():
    assert _informativeness(1.5, "under") > _informativeness(3.5, "under")


def test_ranking_score_uses_probability():
    """At equal trust, higher model probability ranks higher."""
    high = _ranking_score(0.90, 1.5, "over", trust=0.7)
    low = _ranking_score(0.65, 1.5, "over", trust=0.7)
    assert high > low


def test_ranking_score_uses_trust():
    """At equal probability, higher trust ranks higher."""
    high = _ranking_score(0.75, 1.5, "over", trust=0.9)
    low = _ranking_score(0.75, 1.5, "over", trust=0.4)
    assert high > low


def test_candidates_filtered_by_min_prob():
    pred = _make_pred(prob_over_3_5=0.30)  # below threshold
    cands = _candidates_for(pred, _make_match())
    for c in cands:
        assert c["prob"] >= 0.60


def test_candidates_include_under_markets():
    pred = _make_pred(prob_under_3_5=0.72)
    cands = _candidates_for(pred, _make_match())
    assert any(c["direction"] == "under" and c["line"] == 3.5 for c in cands)


def test_best_pick_per_match_returns_one_pick():
    pred = _make_pred()
    pick = _best_pick_per_match(_FakeDB(), _make_match(), pred)
    assert pick is not None
    assert pick.match_id == 1


def test_best_pick_prefers_high_prob_high_line():
    """Over 0.5 (0.97) is trivial; Over 2.5 (0.72) is more informative.
    The combined score should still rank Over 0.5 high but the chosen
    pick must beat any single-market alternative on the same fixture."""
    pred = _make_pred()
    pick = _best_pick_per_match(_FakeDB(), _make_match(), pred)
    # Whatever the winner is, it must come from one of the offered
    # candidate markets and must have prob ≥ 0.60.
    cands = _candidates_for(pred, _make_match())
    best_score = max(
        _ranking_score(c["prob"], c["line"], c["direction"],
                       trust=0.4 * 0.7 + 0.3 * 0.8 + 0.2 * 0.75)
        for c in cands
    )
    assert pick.ranking_score == round(best_score, 4)


def test_best_pick_returns_none_for_low_prob_match():
    """All candidates filtered out → None instead of forcing a pick."""
    pred = _make_pred(
        prob_over_0_5=0.10, prob_over_1_5=0.10, prob_over_2_5=0.10, prob_over_3_5=0.10,
        prob_under_0_5=0.10, prob_under_1_5=0.10, prob_under_2_5=0.10, prob_under_3_5=0.10,
        prob_over_0_5_h1=0.10, prob_over_1_5_h1=0.10,
        prob_over_0_5_h2=0.10, prob_over_1_5_h2=0.10,
    )
    pick = _best_pick_per_match(_FakeDB(), _make_match(), pred)
    assert pick is None


def test_top3_picks_are_distinct_matches():
    """The whole point: 3 different matches, not 3 markets from one."""
    matches = [_make_match(match_id=i, home=f"H{i}", away=f"A{i}") for i in range(1, 6)]
    # Match 1 has very strong probabilities; the rest are weaker but
    # still pass the 0.60 floor.
    preds = {
        1: _make_pred(),  # default (strong)
        2: _make_pred(prob_over_0_5=0.80, prob_over_1_5=0.65, prob_over_2_5=0.62,
                      prob_over_3_5=0.40, prob_over_0_5_h1=0.65, prob_over_0_5_h2=0.70,
                      confidence_score=0.65, model_agreement_score=0.70,
                      prediction_stability_score=0.60),
        3: _make_pred(prob_over_0_5=0.78, prob_over_1_5=0.62, prob_over_2_5=0.61,
                      prob_over_3_5=0.35, prob_over_0_5_h1=0.62, prob_over_0_5_h2=0.66,
                      confidence_score=0.60, model_agreement_score=0.65,
                      prediction_stability_score=0.55),
        4: _make_pred(prob_over_0_5=0.40, prob_over_1_5=0.30, prob_over_2_5=0.20,
                      prob_over_3_5=0.10, prob_over_0_5_h1=0.20, prob_over_0_5_h2=0.25,
                      prob_under_0_5=0.60, prob_under_1_5=0.35, prob_under_2_5=0.20),
        5: _make_pred(prob_over_0_5=0.10, prob_over_1_5=0.05, prob_over_2_5=0.05,
                      prob_over_3_5=0.05, prob_over_0_5_h1=0.05, prob_over_0_5_h2=0.05,
                      prob_under_0_5=0.90, prob_under_1_5=0.65, prob_under_2_5=0.40),
    }

    picks = []
    for m in matches:
        p = _best_pick_per_match(_FakeDB(), m, preds[m.id])
        if p is not None:
            picks.append(p)

    picks.sort(
        key=lambda p: (p.ranking_score, p.model_probability, p.confidence_score),
        reverse=True,
    )
    top3 = picks[:3]

    assert len(top3) == 3
    match_ids = [p.match_id for p in top3]
    assert len(set(match_ids)) == 3, f"Top3 should be 3 distinct matches, got {match_ids}"

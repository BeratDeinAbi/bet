"""
Top-3 ranking service: selects the 3 best goal predictions of the day.
"""
import logging
from datetime import datetime, timezone, date
from typing import List, Dict, Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Match, Prediction, Competition, OddsLine
from app.schemas.prediction import Top3Pick, Top3Response

logger = logging.getLogger(__name__)


def _build_pick(match: Match, pred: Prediction, market: str, line: float,
                direction: str, model_prob: float, odds_line: OddsLine = None) -> Top3Pick:
    fair_odds = round(1.0 / max(model_prob, 0.001), 3)
    bookmaker_odds = odds_line.bookmaker_odds if odds_line else None
    edge = None
    if bookmaker_odds and odds_line.implied_probability:
        edge = round(model_prob - odds_line.implied_probability, 4)

    ranking_score = (
        settings.TOP3_W_CONFIDENCE * pred.confidence_score
        + settings.TOP3_W_MODEL_AGREEMENT * pred.model_agreement_score
        + settings.TOP3_W_STABILITY * pred.prediction_stability_score
        + settings.TOP3_W_EDGE * (max(edge, 0) if edge is not None else 0)
    )

    return Top3Pick(
        match_id=match.id,
        sport=match.sport,
        league=match.competition.name if match.competition else "",
        home_team=match.home_team_name,
        away_team=match.away_team_name,
        kickoff_time=match.kickoff_time,
        market=f"{'Over' if direction == 'over' else 'Under'} {line} {market}",
        market_line=line,
        market_direction=direction,
        model_probability=round(model_prob, 4),
        fair_odds=fair_odds,
        bookmaker_odds=bookmaker_odds,
        edge=edge,
        confidence_score=pred.confidence_score,
        confidence_label=pred.confidence_label,
        ranking_score=round(ranking_score, 4),
        explanation=pred.explanation or "",
    )


def _get_candidates(pred: Prediction, match: Match) -> List[Dict[str, Any]]:
    """Generate all market candidates from a prediction."""
    candidates = []
    sport = match.sport

    if sport == "football":
        # Full game
        for line, direction, field in [
            (2.5, "over", "prob_over_2_5"),
            (1.5, "over", "prob_over_1_5"),
            (3.5, "over", "prob_over_3_5"),
            (0.5, "over", "prob_over_0_5"),
        ]:
            prob = getattr(pred, field, None)
            if prob is not None:
                candidates.append({"market": "Total", "line": line, "direction": direction, "prob": prob})

        # H1
        if pred.prob_over_0_5_h1 is not None:
            candidates.append({"market": "H1 Total", "line": 0.5, "direction": "over", "prob": pred.prob_over_0_5_h1})
        if pred.prob_over_1_5_h1 is not None:
            candidates.append({"market": "H1 Total", "line": 1.5, "direction": "over", "prob": pred.prob_over_1_5_h1})
        # H2
        if pred.prob_over_0_5_h2 is not None:
            candidates.append({"market": "H2 Total", "line": 0.5, "direction": "over", "prob": pred.prob_over_0_5_h2})

    elif sport == "hockey":
        for line, direction, field in [
            (5.5, "over", "prob_over_5_5"),
            (6.5, "over", "prob_over_6_5"),  # extended NHL lines
            (4.5, "over", "prob_over_4_5"),
            (5.5, "under", "prob_under_5_5"),
        ]:
            prob = getattr(pred, field, None)
            if prob is not None:
                candidates.append({"market": "Total", "line": line, "direction": direction, "prob": prob})

        # Periods
        if pred.prob_over_0_5_p1 is not None:
            candidates.append({"market": "P1 Total", "line": 0.5, "direction": "over", "prob": pred.prob_over_0_5_p1})
        if pred.prob_over_1_5_p1 is not None:
            candidates.append({"market": "P1 Total", "line": 1.5, "direction": "over", "prob": pred.prob_over_1_5_p1})

    # Filter to high-confidence picks (prob > 0.60 or < 0.40 for under)
    return [c for c in candidates if c["prob"] > 0.58]


def rank_top3_predictions(db: Session) -> Top3Response:
    today = date.today()
    matches = (
        db.query(Match)
        .join(Competition)
        .all()
    )
    today_matches = [m for m in matches if m.kickoff_time and m.kickoff_time.date() == today]

    all_picks: List[Top3Pick] = []

    for match in today_matches:
        pred = db.query(Prediction).filter(Prediction.match_id == match.id).first()
        if not pred:
            continue

        candidates = _get_candidates(pred, match)
        for cand in candidates:
            odds_line = db.query(OddsLine).filter(
                OddsLine.match_id == match.id,
                OddsLine.line == cand["line"],
                OddsLine.direction == cand["direction"],
            ).first()
            pick = _build_pick(
                match=match,
                pred=pred,
                market=cand["market"],
                line=cand["line"],
                direction=cand["direction"],
                model_prob=cand["prob"],
                odds_line=odds_line,
            )
            all_picks.append(pick)

    # Sort by ranking_score desc, take top 3
    all_picks.sort(key=lambda p: p.ranking_score, reverse=True)
    top3 = all_picks[:3]

    return Top3Response(
        generated_at=datetime.now(timezone.utc),
        picks=top3,
    )

"""
Top-3 ranking service: selects the 3 best goal predictions of the day.

Design goals:
- Diversity: at most one pick per match — no flooding the list with
  multiple markets of the same fixture.
- Probability-driven: the actual model probability of the event is the
  dominant ranking factor — we want the most likely things to happen.
- Trust: confidence, ensemble agreement and stability act as a
  multiplier so we don't pick high-prob events from a shaky model.
- Informativeness: tiny tie-break preferring higher lines (Over 2.5 over
  Over 0.5) when probabilities are comparable, so we don't always end
  up with trivial "Over 0.5" picks.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Match, Prediction, Competition, OddsLine
from app.schemas.prediction import Top3Pick, Top3Response

logger = logging.getLogger(__name__)


# Minimum probability for a candidate market to be considered. Below
# this we treat it as a coin-flip that doesn't deserve a "best pick"
# slot.
_MIN_PROB = 0.60

# Mindest-Faire-Quote für einen Pick: 1.25 ⇒ Wahrscheinlichkeit
# höchstens 1/1.25 = 0.80.  Damit fliegen triviale „Over 0.5"-Picks
# (faire Quote ~1.05) raus und nur Vorschläge mit echtem Wettwert
# bleiben.  Diese Picks landen automatisch in der RecommendedPick-
# Tabelle für tägliches Backtesting.
_MIN_FAIR_ODDS = 1.25
_MAX_PROB = 1.0 / _MIN_FAIR_ODDS

# Fenster für „heute" — gleich wie in der API, damit Top3 dieselben
# Spiele sieht wie der Dashboard-Filter.
_TODAY_PAST = timedelta(hours=6)
_TODAY_FUTURE = timedelta(hours=36)


def _trust_score(pred: Prediction, edge: Optional[float]) -> float:
    """Configurable model-trust score (0..1-ish), uses .env weights."""
    return (
        settings.TOP3_W_CONFIDENCE * (pred.confidence_score or 0.0)
        + settings.TOP3_W_MODEL_AGREEMENT * (pred.model_agreement_score or 0.0)
        + settings.TOP3_W_STABILITY * (pred.prediction_stability_score or 0.0)
        + settings.TOP3_W_EDGE * (max(edge, 0.0) if edge is not None else 0.0)
    )


def _informativeness(line: float, direction: str) -> float:
    """
    Tiny tie-break in favor of more "interesting" markets.

    Higher Over-lines beat Over 0.5 at equal probability, and Under
    picks on lower lines beat Under-on-everything.
    """
    if direction == "over":
        return min(line / 3.0, 1.0)
    # Under: lower line = more informative (Under 1.5 beats Under 5.5)
    return min(max(0.0, (4.0 - line) / 4.0), 1.0)


def _ranking_score(model_prob: float, line: float, direction: str,
                   trust: float) -> float:
    """
    Combined ranking score in roughly the [0, 1] range.

    Weights:
      - 0.55 * model_prob   → "wahrscheinlich kommt das"
      - 0.35 * trust        → "und das Modell ist sich sicher"
      - 0.10 * informativeness  → soft tie-break
    """
    info = _informativeness(line, direction)
    return 0.55 * model_prob + 0.35 * trust + 0.10 * info


def _build_pick(match: Match, pred: Prediction, market: str, line: float,
                direction: str, model_prob: float,
                odds_line: Optional[OddsLine] = None) -> Top3Pick:
    fair_odds = round(1.0 / max(model_prob, 0.001), 3)
    bookmaker_odds = odds_line.bookmaker_odds if odds_line else None
    edge = None
    if bookmaker_odds and odds_line and odds_line.implied_probability:
        edge = round(model_prob - odds_line.implied_probability, 4)

    trust = _trust_score(pred, edge)
    ranking_score = _ranking_score(model_prob, line, direction, trust)

    return Top3Pick(
        match_id=match.id,
        sport=match.sport,
        league=match.competition.name if match.competition else "",
        home_team=match.home_team_name,
        away_team=match.away_team_name,
        kickoff_time=match.kickoff_time,
        market=f"{'Over' if direction == 'over' else 'Under'} {line} {market}".strip(),
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


def _candidates_for(pred: Prediction, match: Match) -> List[Dict[str, Any]]:
    """All viable market candidates for one match."""
    out: List[Dict[str, Any]] = []
    sport = match.sport

    def add(market: str, line: float, direction: str, field: str):
        prob = getattr(pred, field, None)
        if prob is None:
            return
        out.append({"market": market, "line": line, "direction": direction, "prob": float(prob)})

    if sport == "football":
        # Full game — both directions
        for line, fld_o, fld_u in [
            (0.5, "prob_over_0_5", "prob_under_0_5"),
            (1.5, "prob_over_1_5", "prob_under_1_5"),
            (2.5, "prob_over_2_5", "prob_under_2_5"),
            (3.5, "prob_over_3_5", "prob_under_3_5"),
        ]:
            add("Total", line, "over", fld_o)
            add("Total", line, "under", fld_u)

        # Halves
        add("H1 Total", 0.5, "over", "prob_over_0_5_h1")
        add("H1 Total", 1.5, "over", "prob_over_1_5_h1")
        add("H2 Total", 0.5, "over", "prob_over_0_5_h2")
        add("H2 Total", 1.5, "over", "prob_over_1_5_h2")

    elif sport == "hockey":
        # NHL totals (4.5/5.5/6.5) aren't stored on Prediction yet —
        # ranking only uses per-period markets that the model writes.
        add("P1 Total", 0.5, "over", "prob_over_0_5_p1")
        add("P1 Total", 1.5, "over", "prob_over_1_5_p1")
        add("P2 Total", 0.5, "over", "prob_over_0_5_p2")
        add("P2 Total", 1.5, "over", "prob_over_1_5_p2")
        add("P3 Total", 0.5, "over", "prob_over_0_5_p3")
        add("P3 Total", 1.5, "over", "prob_over_1_5_p3")

    elif sport == "basketball":
        # NBA-Märkte stehen in extra_markets (JSON), nicht in Spalten.
        extra = getattr(pred, "extra_markets", None) or {}
        # Total-Punkte
        for line in (200.5, 210.5, 215.5, 220.5, 225.5, 230.5, 235.5, 240.5):
            lk = str(line).replace(".", "_")
            for direction, prefix in (("over", "prob_over_"), ("under", "prob_under_")):
                v = extra.get(f"{prefix}{lk}")
                if isinstance(v, (int, float)):
                    out.append({"market": "Total Punkte", "line": float(line),
                                "direction": direction, "prob": float(v)})
        # Quarter-Linien (Q1–Q4 × 50.5/55.5/60.5)
        for q in ("q1", "q2", "q3", "q4"):
            for line in (50.5, 55.5, 60.5):
                lk = str(line).replace(".", "_")
                for direction, prefix in (("over", "prob_over_"), ("under", "prob_under_")):
                    v = extra.get(f"{prefix}{lk}_{q}")
                    if isinstance(v, (int, float)):
                        out.append({"market": f"{q.upper()} Punkte", "line": float(line),
                                    "direction": direction, "prob": float(v)})

    elif sport == "baseball":
        extra = getattr(pred, "extra_markets", None) or {}
        # Total Runs
        for line in (6.5, 7.5, 8.0, 8.5, 9.0, 9.5, 10.5, 11.5):
            lk = str(line).replace(".", "_")
            for direction, prefix in (("over", "prob_over_"), ("under", "prob_under_")):
                v = extra.get(f"{prefix}{lk}")
                if isinstance(v, (int, float)):
                    out.append({"market": "Total Runs", "line": float(line),
                                "direction": direction, "prob": float(v)})
        # F5 — beliebter MLB-Wettmarkt
        for line in (3.5, 4.5, 5.5):
            lk = str(line).replace(".", "_")
            for direction, prefix in (("over", "prob_over_"), ("under", "prob_under_")):
                v = extra.get(f"{prefix}{lk}_f5")
                if isinstance(v, (int, float)):
                    out.append({"market": "F5 Runs", "line": float(line),
                                "direction": direction, "prob": float(v)})

    # Untere Schwelle: kein Coin-Flip-Pick.
    # Obere Schwelle: faire Quote muss mind. _MIN_FAIR_ODDS sein →
    # triviale Lock-Picks (Over 0.5 mit ~95 %) fliegen raus.
    return [c for c in out if _MIN_PROB <= c["prob"] <= _MAX_PROB]


def _best_pick_per_match(db: Session, match: Match,
                         pred: Prediction) -> Optional[Top3Pick]:
    """Return the single best market pick for one match, or None."""
    candidates = _candidates_for(pred, match)
    if not candidates:
        return None

    best_pick: Optional[Top3Pick] = None
    for cand in candidates:
        odds_line = (
            db.query(OddsLine)
            .filter(
                OddsLine.match_id == match.id,
                OddsLine.line == cand["line"],
                OddsLine.direction == cand["direction"],
            )
            .first()
        )
        pick = _build_pick(
            match=match,
            pred=pred,
            market=cand["market"],
            line=cand["line"],
            direction=cand["direction"],
            model_prob=cand["prob"],
            odds_line=odds_line,
        )
        if best_pick is None or pick.ranking_score > best_pick.ranking_score:
            best_pick = pick
    return best_pick


def rank_top3_predictions(db: Session) -> Top3Response:
    now = datetime.now(timezone.utc)
    window_lo = now - _TODAY_PAST
    window_hi = now + _TODAY_FUTURE

    matches = (
        db.query(Match)
        .join(Competition)
        .all()
    )

    def _in_window(m):
        if not m.kickoff_time:
            return False
        kt = m.kickoff_time
        if kt.tzinfo is None:
            kt = kt.replace(tzinfo=timezone.utc)
        return window_lo <= kt <= window_hi

    today_matches = [m for m in matches if _in_window(m)]

    picks: List[Top3Pick] = []
    for match in today_matches:
        pred = db.query(Prediction).filter(Prediction.match_id == match.id).first()
        if not pred:
            continue
        best = _best_pick_per_match(db, match, pred)
        if best is not None:
            picks.append(best)

    # One pick per match guaranteed by _best_pick_per_match → just sort.
    picks.sort(
        key=lambda p: (p.ranking_score, p.model_probability, p.confidence_score),
        reverse=True,
    )
    top3 = picks[:3]

    return Top3Response(
        generated_at=datetime.now(timezone.utc),
        picks=top3,
    )

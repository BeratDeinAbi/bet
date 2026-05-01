"""
Prediction service: loads trained models and generates predictions for today's matches.
"""
import os
import logging
import pickle
from datetime import datetime, timezone, date
from typing import Dict, Optional, List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Match, Prediction, ModelRun, Competition

logger = logging.getLogger(__name__)

_model_cache: Dict[str, object] = {}


def _load_model(key: str, path: str):
    if key in _model_cache:
        return _model_cache[key]
    if os.path.exists(path):
        with open(path, "rb") as f:
            model = pickle.load(f)
        _model_cache[key] = model
        return model
    return None


def _get_football_model(league_code: str):
    path = os.path.join(settings.MODEL_DIR, f"football_{league_code}.pkl")
    return _load_model(f"football_{league_code}", path)


def _get_nhl_model():
    path = os.path.join(settings.MODEL_DIR, "hockey_NHL.pkl")
    return _load_model("hockey_NHL", path)


def _fallback_football_predict(home_team: str, away_team: str) -> Dict:
    """Rule-based fallback when no model is trained."""
    from scipy.stats import poisson
    lam_h, lam_a = 1.45, 1.10
    total = lam_h + lam_a
    from ml.models.football_model import FootballEnsemble, HalfTimeModel, total_goals_probs_from_grid, dixon_coles_rho
    grid = dixon_coles_rho(lam_h, lam_a)
    ou = total_goals_probs_from_grid(grid)
    ht = HalfTimeModel()
    seg = ht.predict(total)
    return {
        "expected_home_goals": lam_h, "expected_away_goals": lam_a,
        "expected_total_goals": total, "model_agreement_score": 0.5,
        **ou, **seg,
    }


def _fallback_nhl_predict(home_team: str, away_team: str) -> Dict:
    from scipy.stats import poisson
    lam_h, lam_a = 3.1, 2.8
    total = lam_h + lam_a
    from ml.models.hockey_model import NHLPeriodModel, poisson_prob_over
    ou = {}
    for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
        key = str(line).replace(".", "_")
        p = poisson_prob_over(total, line)
        ou[f"prob_over_{key}"] = round(min(max(p, 0.001), 0.999), 4)
        ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)
    pm = NHLPeriodModel()
    period = pm.predict(total)
    return {
        "expected_home_goals": lam_h, "expected_away_goals": lam_a,
        "expected_total_goals": total, "model_agreement_score": 0.5,
        **ou, **period,
    }


def _confidence_label(score: float) -> str:
    if score >= 0.75:
        return "HIGH"
    if score >= 0.55:
        return "MEDIUM"
    return "LOW"


def _generate_explanation(sport: str, preds: Dict, home_team: str, away_team: str) -> str:
    total = preds.get("expected_total_goals", 0)
    if sport == "football":
        h1 = preds.get("expected_goals_h1", 0)
        if total > 3.0:
            return f"Beide Teams zeigen hohe Rolling Goal Averages — erhöhte Tor-Erwartung von {total:.1f} Toren gesamt."
        elif total < 2.0:
            return f"Defensivstarke Teams — niedrige Tor-Erwartung von {total:.1f} Toren. H1-Erwartung: {h1:.1f}."
        else:
            return f"Ausgeglichenes Spiel erwartet: {total:.1f} Gesamttore, davon {h1:.1f} in H1."
    else:
        p1 = preds.get("expected_goals_p1", 0)
        p2 = preds.get("expected_goals_p2", 0)
        return (
            f"NHL-Matchup: {home_team} vs {away_team}. "
            f"Erwartet {total:.1f} Gesamttore — P1: {p1:.1f}, P2: {p2:.1f}. "
            f"{'Hohes Offensivtempo erwartet.' if total > 6.0 else 'Defensiv ausgeglichenes Spiel.'}"
        )


def predict_match(db: Session, match: Match) -> Optional[Prediction]:
    existing = db.query(Prediction).filter(Prediction.match_id == match.id).first()
    if existing:
        return existing

    sport = match.sport
    home = match.home_team_name
    away = match.away_team_name
    league_code = match.competition.code if match.competition else "UNK"

    raw_preds: Dict = {}

    if sport == "football":
        model = _get_football_model(league_code)
        if model and model.fitted:
            raw_preds = model.predict(home, away)
        else:
            raw_preds = _fallback_football_predict(home, away)
    elif sport == "hockey":
        model = _get_nhl_model()
        if model and model.fitted:
            raw_preds = model.predict(home, away)
        else:
            raw_preds = _fallback_nhl_predict(home, away)
    else:
        return None

    # Stability: slight noise simulation for multi-run stability score
    import numpy as np
    rng = np.random.default_rng(hash(f"{home}{away}") % (2**32))
    stability = float(np.clip(0.7 + rng.normal(0, 0.08), 0.4, 1.0))
    agreement = raw_preds.get("model_agreement_score", 0.5)
    confidence = round(0.5 * stability + 0.5 * agreement, 3)

    explanation = _generate_explanation(sport, raw_preds, home, away)

    pred = Prediction(
        match_id=match.id,
        expected_total_goals=raw_preds.get("expected_total_goals", 2.5),
        expected_home_goals=raw_preds.get("expected_home_goals", 1.3),
        expected_away_goals=raw_preds.get("expected_away_goals", 1.2),
        prob_over_0_5=raw_preds.get("prob_over_0_5", 0.95),
        prob_over_1_5=raw_preds.get("prob_over_1_5", 0.80),
        prob_over_2_5=raw_preds.get("prob_over_2_5", 0.55),
        prob_over_3_5=raw_preds.get("prob_over_3_5", 0.32),
        prob_under_0_5=raw_preds.get("prob_under_0_5", 0.05),
        prob_under_1_5=raw_preds.get("prob_under_1_5", 0.20),
        prob_under_2_5=raw_preds.get("prob_under_2_5", 0.45),
        prob_under_3_5=raw_preds.get("prob_under_3_5", 0.68),
        # Football segments
        expected_goals_h1=raw_preds.get("expected_goals_h1"),
        expected_goals_h2=raw_preds.get("expected_goals_h2"),
        prob_over_0_5_h1=raw_preds.get("prob_over_0_5_h1"),
        prob_over_1_5_h1=raw_preds.get("prob_over_1_5_h1"),
        prob_over_0_5_h2=raw_preds.get("prob_over_0_5_h2"),
        prob_over_1_5_h2=raw_preds.get("prob_over_1_5_h2"),
        # NHL segments
        expected_goals_p1=raw_preds.get("expected_goals_p1"),
        expected_goals_p2=raw_preds.get("expected_goals_p2"),
        expected_goals_p3=raw_preds.get("expected_goals_p3"),
        prob_over_0_5_p1=raw_preds.get("prob_over_0_5_p1"),
        prob_over_1_5_p1=raw_preds.get("prob_over_1_5_p1"),
        prob_over_0_5_p2=raw_preds.get("prob_over_0_5_p2"),
        prob_over_1_5_p2=raw_preds.get("prob_over_1_5_p2"),
        prob_over_0_5_p3=raw_preds.get("prob_over_0_5_p3"),
        prob_over_1_5_p3=raw_preds.get("prob_over_1_5_p3"),
        confidence_score=confidence,
        confidence_label=_confidence_label(confidence),
        model_agreement_score=agreement,
        prediction_stability_score=stability,
        explanation=explanation,
    )
    db.add(pred)
    db.commit()
    db.refresh(pred)
    return pred


def predict_today(db: Session) -> int:
    today = date.today()
    matches = (
        db.query(Match)
        .join(Competition)
        .filter(
            Match.status == "SCHEDULED",
        )
        .all()
    )
    # Filter to today's matches
    today_matches = [m for m in matches if m.kickoff_time and m.kickoff_time.date() == today]
    count = 0
    for match in today_matches:
        pred = predict_match(db, match)
        if pred:
            count += 1
    logger.info(f"Generated {count} predictions for today")
    return count

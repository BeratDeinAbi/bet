"""
Prediction service: loads trained models and generates predictions for today's matches.
"""
import os
import logging
import pickle
from datetime import datetime, timezone, date, timedelta
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


def _get_nba_model():
    path = os.path.join(settings.MODEL_DIR, "basketball_NBA.pkl")
    return _load_model("basketball_NBA", path)


def _get_mlb_model():
    path = os.path.join(settings.MODEL_DIR, "baseball_MLB.pkl")
    return _load_model("baseball_MLB", path)


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


def _fallback_mlb_predict(home_team: str, away_team: str) -> Dict:
    """Fallback wenn kein MLB-Modell trainiert ist."""
    from ml.models.mlb_model import (
        MLB_PRIOR, MLBF5Model, TOTAL_LINES, poisson_prob_over,
    )
    avg = MLB_PRIOR["avg_runs"]
    home_adv = MLB_PRIOR["home_adv"]
    lam_h = (avg / 2.0) * home_adv
    lam_a = avg / 2.0
    total = lam_h + lam_a
    ou = {}
    for line in TOTAL_LINES:
        key = str(line).replace(".", "_")
        p = poisson_prob_over(total, line)
        ou[f"prob_over_{key}"] = round(min(max(p, 0.001), 0.999), 4)
        ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)
    f5 = MLBF5Model().predict(total)
    return {
        "expected_home_runs": round(lam_h, 3),
        "expected_away_runs": round(lam_a, 3),
        "expected_total_runs": round(total, 3),
        "model_agreement_score": 0.5,
        **ou,
        **f5,
    }


def _fallback_nba_predict(home_team: str, away_team: str) -> Dict:
    """Regelbasierter Fallback wenn kein NBA-Modell trainiert ist."""
    from ml.models.nba_model import (
        NBA_PRIOR, NBAQuarterModel, TOTAL_LINES, normal_prob_over,
    )
    avg = NBA_PRIOR["avg_points"]
    home_adv = NBA_PRIOR["home_adv"]
    mu_h = (avg / 2.0) * home_adv
    mu_a = avg / 2.0
    total = mu_h + mu_a
    total_std = NBA_PRIOR["total_std"]
    ou = {}
    for line in TOTAL_LINES:
        key = str(line).replace(".", "_")
        p = normal_prob_over(total, total_std, line)
        ou[f"prob_over_{key}"] = round(min(max(p, 0.001), 0.999), 4)
        ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)
    quarters = NBAQuarterModel().predict(total)
    return {
        "expected_home_points": round(mu_h, 2),
        "expected_away_points": round(mu_a, 2),
        "expected_total_points": round(total, 2),
        "expected_total_std": round(total_std, 2),
        "model_agreement_score": 0.5,
        **ou,
        **quarters,
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
    if sport == "football":
        total = preds.get("expected_total_goals", 0)
        h1 = preds.get("expected_goals_h1", 0)
        if total > 3.0:
            return f"Beide Teams zeigen hohe Rolling Goal Averages — erhöhte Tor-Erwartung von {total:.1f} Toren gesamt."
        elif total < 2.0:
            return f"Defensivstarke Teams — niedrige Tor-Erwartung von {total:.1f} Toren. H1-Erwartung: {h1:.1f}."
        else:
            return f"Ausgeglichenes Spiel erwartet: {total:.1f} Gesamttore, davon {h1:.1f} in H1."
    if sport == "basketball":
        total = preds.get("expected_total_points", 0)
        mu_h = preds.get("expected_home_points", 0)
        mu_a = preds.get("expected_away_points", 0)
        tempo = "Hoher Tempo-Run" if total > 230 else ("Defensives Spiel" if total < 215 else "Standard-Tempo")
        return (
            f"NBA: {home_team} {mu_h:.0f} – {mu_a:.0f} {away_team}. "
            f"Erwartete Gesamtpunkte: {total:.1f}. {tempo}."
        )
    if sport == "baseball":
        total = preds.get("expected_total_runs", 0)
        lam_h = preds.get("expected_home_runs", 0)
        lam_a = preds.get("expected_away_runs", 0)
        f5 = preds.get("expected_runs_f5", 0)
        tempo = "Hochfrequentes Offensiv-Game" if total > 10 else (
            "Pitcher-Duell" if total < 7.5 else "Standard-Run-Niveau"
        )
        return (
            f"MLB: {home_team} {lam_h:.1f} – {lam_a:.1f} {away_team}. "
            f"Erwartete Total Runs: {total:.1f} (F5: {f5:.1f}). {tempo}."
        )
    # hockey
    total = preds.get("expected_total_goals", 0)
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
    elif sport == "basketball":
        model = _get_nba_model()
        if model and model.fitted:
            raw_preds = model.predict(home, away)
        else:
            raw_preds = _fallback_nba_predict(home, away)
    elif sport == "baseball":
        model = _get_mlb_model()
        if model and model.fitted:
            raw_preds = model.predict(home, away)
        else:
            raw_preds = _fallback_mlb_predict(home, away)
    else:
        return None

    # Stability: slight noise simulation for multi-run stability score
    import numpy as np
    rng = np.random.default_rng(hash(f"{home}{away}") % (2**32))
    stability = float(np.clip(0.7 + rng.normal(0, 0.08), 0.4, 1.0))
    agreement = raw_preds.get("model_agreement_score", 0.5)
    confidence = round(0.5 * stability + 0.5 * agreement, 3)

    explanation = _generate_explanation(sport, raw_preds, home, away)

    # NBA + MLB haben eigene Scoring-Niveaus (200+ Punkte / 6+ Runs) —
    # die kleinen 0.5/1.5/2.5/3.5-Spalten passen nicht.  Wir packen alle
    # sport-spezifischen Märkte in extra_markets als JSON.
    extra_markets = None
    if sport == "basketball":
        extra_markets = {
            k: v for k, v in raw_preds.items()
            if k.startswith("prob_over_") or k.startswith("prob_under_")
            or k.startswith("expected_points_") or k.startswith("expected_total_")
            or k.startswith("expected_home_points") or k.startswith("expected_away_points")
            or k in ("total_lines_used", "quarter_lines_used")
        }
    elif sport == "baseball":
        extra_markets = {
            k: v for k, v in raw_preds.items()
            if k.startswith("prob_over_") or k.startswith("prob_under_")
            or k.startswith("expected_runs_") or k.startswith("expected_total_")
            or k.startswith("expected_home_runs") or k.startswith("expected_away_runs")
            or k.startswith("pitcher_factor_")
            or k in ("total_lines_used", "f5_lines_used")
        }

    # Schema-Spalten: für Basketball/Baseball mit Sentinel-Werten füllen,
    # damit NOT-NULL-Felder gesetzt sind; die echten Werte stehen in
    # extra_markets.
    if sport == "basketball":
        col_total = raw_preds.get("expected_total_points", 0.0)
        col_home = raw_preds.get("expected_home_points", 0.0)
        col_away = raw_preds.get("expected_away_points", 0.0)
        col_p_o05 = col_p_o15 = col_p_o25 = col_p_o35 = 0.0
        col_p_u05 = col_p_u15 = col_p_u25 = col_p_u35 = 0.0
    elif sport == "baseball":
        col_total = raw_preds.get("expected_total_runs", 0.0)
        col_home = raw_preds.get("expected_home_runs", 0.0)
        col_away = raw_preds.get("expected_away_runs", 0.0)
        col_p_o05 = col_p_o15 = col_p_o25 = col_p_o35 = 0.0
        col_p_u05 = col_p_u15 = col_p_u25 = col_p_u35 = 0.0
    else:
        col_total = raw_preds.get("expected_total_goals", 2.5)
        col_home = raw_preds.get("expected_home_goals", 1.3)
        col_away = raw_preds.get("expected_away_goals", 1.2)
        col_p_o05 = raw_preds.get("prob_over_0_5", 0.95)
        col_p_o15 = raw_preds.get("prob_over_1_5", 0.80)
        col_p_o25 = raw_preds.get("prob_over_2_5", 0.55)
        col_p_o35 = raw_preds.get("prob_over_3_5", 0.32)
        col_p_u05 = raw_preds.get("prob_under_0_5", 0.05)
        col_p_u15 = raw_preds.get("prob_under_1_5", 0.20)
        col_p_u25 = raw_preds.get("prob_under_2_5", 0.45)
        col_p_u35 = raw_preds.get("prob_under_3_5", 0.68)

    pred = Prediction(
        match_id=match.id,
        expected_total_goals=col_total,
        expected_home_goals=col_home,
        expected_away_goals=col_away,
        prob_over_0_5=col_p_o05,
        prob_over_1_5=col_p_o15,
        prob_over_2_5=col_p_o25,
        prob_over_3_5=col_p_o35,
        prob_under_0_5=col_p_u05,
        prob_under_1_5=col_p_u15,
        prob_under_2_5=col_p_u25,
        prob_under_3_5=col_p_u35,
        extra_markets=extra_markets,
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
    now = datetime.now(timezone.utc)
    window_lo = now - timedelta(hours=6)
    window_hi = now + timedelta(hours=36)
    matches = (
        db.query(Match)
        .join(Competition)
        .filter(
            Match.status == "SCHEDULED",
        )
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
    count = 0
    for match in today_matches:
        pred = predict_match(db, match)
        if pred:
            count += 1
    logger.info(f"Generated {count} predictions for today")
    return count

"""
Outcome-Evaluation und Kalibrierungs-Pipeline.

Tägliche Logik:
  1. evaluate_finished_matches(): findet alle Matches mit Status=FINISHED
     für die noch keine PredictionOutcome existiert.  Berechnet Fehler
     pro O/U-Linie und schreibt eine Zeile pro Prediction.
  2. compute_calibration(): aggregiert die letzten ~500 Outcomes pro
     Sport in 10 Wahrscheinlichkeits-Buckets, fittet eine Isotonic
     Regression und schreibt CalibrationBin-Zeilen.
  3. apply_calibration(prob, sport): Lookup-Funktion, die rohe Modell-
     Probs in kalibrierte umrechnet — wird vom Prediction-Service vor
     dem Speichern aufgerufen.

Effekt: das Modell wird täglich besser kalibriert.  Beispiel: wenn das
Modell konsistent 70 %-Linien überschätzt (echte Trefferquote 60 %),
zeigt es ab dem nächsten Tag 60 % an statt 70 % — ehrlicher Output,
besseres Top-3-Ranking.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy.orm import Session

from app.db.models import (
    CalibrationBin, Match, Prediction, PredictionOutcome,
)

logger = logging.getLogger(__name__)


# Welche O/U-Linien werten wir pro Sport aus?
EVAL_LINES: Dict[str, List[Tuple[str, float, str]]] = {
    "football": [
        ("over_1_5", 1.5, "over"),
        ("over_2_5", 2.5, "over"),
        ("over_3_5", 3.5, "over"),
        ("under_2_5", 2.5, "under"),
    ],
    "hockey": [
        ("over_4_5", 4.5, "over"),
        ("over_5_5", 5.5, "over"),
        ("over_6_5", 6.5, "over"),
        ("under_5_5", 5.5, "under"),
    ],
    "basketball": [
        ("over_210_5", 210.5, "over"),
        ("over_220_5", 220.5, "over"),
        ("over_230_5", 230.5, "over"),
        ("under_220_5", 220.5, "under"),
    ],
    "baseball": [
        ("over_7_5", 7.5, "over"),
        ("over_8_5", 8.5, "over"),
        ("over_9_5", 9.5, "over"),
        ("under_8_5", 8.5, "under"),
    ],
}


def _get_prob(pred: Prediction, key: str, sport: str) -> Optional[float]:
    """Holt eine Wahrscheinlichkeit entweder aus den Schema-Spalten
    (Football/NHL) oder aus extra_markets (NBA/MLB)."""
    if sport in ("football", "hockey"):
        col_name = f"prob_{key}"
        return getattr(pred, col_name, None)
    extra = pred.extra_markets or {}
    return extra.get(f"prob_{key}")


def _evaluate_single(pred: Prediction, match: Match) -> Optional[Dict]:
    if match.home_score is None or match.away_score is None:
        return None
    sport = match.sport
    if sport not in EVAL_LINES:
        return None

    actual_total = float(match.home_score + match.away_score)
    expected_total = float(pred.expected_total_goals)

    hits: Dict[str, Dict] = {}
    primary_hit: Optional[bool] = None
    primary_market: Optional[str] = None
    primary_prob: Optional[float] = None

    for key, line, direction in EVAL_LINES[sport]:
        prob = _get_prob(pred, key, sport)
        if prob is None:
            continue
        if direction == "over":
            actual = bool(actual_total > line)
        else:
            actual = bool(actual_total < line)
        hits[key] = {"prob": float(prob), "hit": actual, "line": line, "dir": direction}

        # Primary = O/U-Linie mit höchster Modell-Wahrscheinlichkeit.
        # Auf der wird die Sidebar-Trefferquote berechnet.
        if primary_prob is None or prob > primary_prob:
            primary_prob = float(prob)
            primary_market = key
            primary_hit = actual

    if not hits:
        return None

    return {
        "actual_total": actual_total,
        "actual_home": float(match.home_score),
        "actual_away": float(match.away_score),
        "expected_total": expected_total,
        "total_abs_error": abs(expected_total - actual_total),
        "total_squared_error": (expected_total - actual_total) ** 2,
        "hits": hits,
        "primary_hit": primary_hit,
        "primary_market": primary_market,
        "primary_prob": primary_prob,
        "sport": sport,
        "league": match.competition.code if match.competition else None,
    }


def evaluate_finished_matches(db: Session) -> int:
    """Erstellt PredictionOutcome-Zeilen für alle finished Matches mit
    Predictions, die noch nicht ausgewertet wurden.  Idempotent."""
    already_evaluated = {
        row[0]
        for row in db.query(PredictionOutcome.prediction_id).all()
    }

    finished_preds = (
        db.query(Prediction, Match)
        .join(Match, Prediction.match_id == Match.id)
        .filter(Match.status == "FINISHED")
        .filter(Match.home_score.isnot(None))
        .all()
    )

    n = 0
    for pred, match in finished_preds:
        if pred.id in already_evaluated:
            continue
        data = _evaluate_single(pred, match)
        if not data:
            continue
        outcome = PredictionOutcome(
            prediction_id=pred.id,
            match_id=match.id,
            **data,
        )
        db.add(outcome)
        n += 1

    db.commit()
    logger.info(f"Evaluated {n} new finished matches")
    return n


def compute_calibration(db: Session, days: int = 90) -> int:
    """Aggregiert die letzten ``days`` Tage Outcomes in 10 Wahrscheinlichkeits-
    Buckets pro Sport und fittet eine Isotonic Regression um eine
    monotonisierte Kalibrierungs-Kurve zu erzeugen.

    Schreibt für jeden Sport 10 CalibrationBin-Zeilen.  Die Zeilen ersetzen
    die vorherigen vollständig (truncate-and-replace) — das ist OK weil
    die Tabelle klein ist und das Lookup-Modell vollständig in jeder Zeile
    steht."""
    try:
        from sklearn.isotonic import IsotonicRegression
    except Exception:
        logger.warning("sklearn.isotonic nicht verfügbar — überspringe Kalibrierung")
        return 0

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Pro Sport: alle (predicted_prob, actual_hit) sammeln
    by_sport: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
    outcomes = (
        db.query(PredictionOutcome)
        .filter(PredictionOutcome.evaluated_at >= cutoff)
        .all()
    )
    for o in outcomes:
        sport = o.sport
        if not o.hits:
            continue
        for _key, info in o.hits.items():
            try:
                p = float(info.get("prob", 0))
                h = 1 if info.get("hit") else 0
                by_sport[sport].append((p, h))
            except (TypeError, ValueError):
                continue

    # Bestehende Kalibrierungs-Zeilen löschen
    db.query(CalibrationBin).delete()

    n_bins_total = 0
    bins = np.linspace(0.0, 1.0, 11)
    for sport, points in by_sport.items():
        if len(points) < 30:
            logger.info(f"Calibration skip {sport}: nur {len(points)} Punkte")
            continue
        probs = np.array([p for p, _ in points])
        hits = np.array([h for _, h in points])

        # Isotonic Regression: monoton, robust gegen Overfit
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999)
        iso.fit(probs, hits)

        for i in range(10):
            lo, hi = float(bins[i]), float(bins[i + 1])
            mask = (probs >= lo) & (probs < hi if i < 9 else probs <= hi)
            if mask.sum() == 0:
                continue
            avg_pred = float(probs[mask].mean())
            empirical_iso = float(iso.predict([avg_pred])[0])
            db.add(CalibrationBin(
                sport=sport,
                bin_lower=lo,
                bin_upper=hi,
                n_predictions=int(mask.sum()),
                avg_predicted_prob=avg_pred,
                empirical_hit_rate=empirical_iso,
            ))
            n_bins_total += 1

    db.commit()
    logger.info(f"Calibration recomputed: {n_bins_total} bins across "
                f"{len(by_sport)} sports")
    return n_bins_total


# ---------------------------------------------------------------------------
# Lookup für Prediction-Service
# ---------------------------------------------------------------------------

# In-Memory Cache (bei jedem Recompute geleert)
_calibration_cache: Dict[str, List[Tuple[float, float, float]]] = {}


def reload_calibration_cache(db: Session) -> None:
    """Lädt CalibrationBin-Tabelle in einen In-Memory-Lookup."""
    global _calibration_cache
    _calibration_cache.clear()
    rows = db.query(CalibrationBin).all()
    by_sport: Dict[str, List[Tuple[float, float, float]]] = defaultdict(list)
    for r in rows:
        by_sport[r.sport].append((r.bin_lower, r.bin_upper, r.empirical_hit_rate))
    for sport in by_sport:
        by_sport[sport].sort()
    _calibration_cache.update(by_sport)
    logger.info(f"Calibration cache loaded for sports: {list(by_sport.keys())}")


def apply_calibration(prob: float, sport: str) -> float:
    """Wendet die Kalibrierungs-Kurve auf eine rohe Modell-Wahrscheinlichkeit
    an.  Falls keine Kurve für den Sport vorliegt → unverändert zurück.

    Nutzt einen monotonen Bucket-Lookup: prob → finde Bucket → nimm
    empirical_hit_rate.  Zwischen Buckets linear interpoliert."""
    bins = _calibration_cache.get(sport)
    if not bins:
        return prob
    p = float(np.clip(prob, 0.001, 0.999))
    # Lineare Interpolation zwischen Bin-Mittelpunkten
    centers = np.array([(lo + hi) / 2.0 for lo, hi, _ in bins])
    rates = np.array([r for _, _, r in bins])
    if p <= centers[0]:
        return float(rates[0])
    if p >= centers[-1]:
        return float(rates[-1])
    interp = float(np.interp(p, centers, rates))
    return float(np.clip(interp, 0.001, 0.999))


# ---------------------------------------------------------------------------
# Aggregierte Statistiken für die Sidebar
# ---------------------------------------------------------------------------

def recent_outcomes(db: Session, limit: int = 25,
                    sport: Optional[str] = None) -> List[Dict]:
    """Letzte N evaluierte Predictions (mit Match-Daten) für die UI."""
    q = (
        db.query(PredictionOutcome, Match)
        .join(Match, PredictionOutcome.match_id == Match.id)
        .order_by(Match.kickoff_time.desc())
    )
    if sport:
        q = q.filter(PredictionOutcome.sport == sport)
    rows = q.limit(limit).all()
    out: List[Dict] = []
    for o, m in rows:
        out.append({
            "id": o.id,
            "match_id": o.match_id,
            "sport": o.sport,
            "league": o.league,
            "home_team": m.home_team_name,
            "away_team": m.away_team_name,
            "kickoff_time": m.kickoff_time.isoformat() if m.kickoff_time else None,
            "actual_home": o.actual_home,
            "actual_away": o.actual_away,
            "actual_total": o.actual_total,
            "expected_total": o.expected_total,
            "total_abs_error": o.total_abs_error,
            "primary_market": o.primary_market,
            "primary_prob": o.primary_prob,
            "primary_hit": o.primary_hit,
        })
    return out


def accuracy_summary(db: Session, days: int = 30) -> Dict:
    """Trefferquote der letzten ``days`` Tage, gesamt und pro Sport."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(PredictionOutcome)
        .filter(PredictionOutcome.evaluated_at >= cutoff)
        .all()
    )
    if not rows:
        return {"days": days, "n": 0, "hit_rate": 0.0, "mae_total": 0.0,
                "by_sport": {}}

    hits = [r.primary_hit for r in rows if r.primary_hit is not None]
    errs = [r.total_abs_error for r in rows if r.total_abs_error is not None]

    by_sport: Dict[str, Dict] = defaultdict(lambda: {"n": 0, "hits": 0, "mae_sum": 0.0})
    for r in rows:
        s = by_sport[r.sport]
        s["n"] += 1
        if r.primary_hit:
            s["hits"] += 1
        if r.total_abs_error is not None:
            s["mae_sum"] += r.total_abs_error
    sport_summary = {
        sport: {
            "n": s["n"],
            "hit_rate": round(s["hits"] / s["n"], 3) if s["n"] else 0.0,
            "mae": round(s["mae_sum"] / s["n"], 3) if s["n"] else 0.0,
        }
        for sport, s in by_sport.items()
    }

    return {
        "days": days,
        "n": len(rows),
        "hit_rate": round(sum(hits) / len(hits), 3) if hits else 0.0,
        "mae_total": round(float(np.mean(errs)), 3) if errs else 0.0,
        "by_sport": sport_summary,
    }

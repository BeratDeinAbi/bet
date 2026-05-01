"""
Walk-forward backtesting for goals prediction models.
Metrics: MAE, RMSE, Brier Score, Calibration Error.
"""
import numpy as np
from typing import List, Dict, Tuple
from scipy.stats import poisson


def brier_score(y_true: List[int], y_prob: List[float]) -> float:
    """Brier score for binary outcome (e.g. Over 2.5)."""
    return float(np.mean([(p - t) ** 2 for p, t in zip(y_prob, y_true)]))


def calibration_error(y_true: List[int], y_prob: List[float], n_bins: int = 10) -> float:
    """Expected calibration error."""
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = [(bins[i] <= p < bins[i+1]) for p in y_prob]
        if sum(mask) == 0:
            continue
        avg_conf = np.mean([y_prob[j] for j in range(n) if mask[j]])
        avg_acc = np.mean([y_true[j] for j in range(n) if mask[j]])
        ece += sum(mask) / n * abs(avg_conf - avg_acc)
    return float(ece)


def backtest_football_model(matches: List[Dict], league_code: str) -> Dict:
    """
    Walk-forward validation for football total goals.
    Uses first 60% as training, last 40% as test.
    """
    from ml.models.football_model import FootballEnsemble

    if len(matches) < 10:
        return {"error": "Not enough matches for backtesting"}

    n_train = int(len(matches) * 0.6)
    train = matches[:n_train]
    test = matches[n_train:]

    model = FootballEnsemble(league_code)
    model.fit(train)

    true_totals = []
    pred_totals = []
    over25_true = []
    over25_prob = []
    over15_h1_true = []
    over15_h1_prob = []

    for m in test:
        if m.get("home_score") is None:
            continue
        try:
            pred = model.predict(m["home_team"], m["away_team"])
        except Exception:
            continue

        actual_total = m["home_score"] + m["away_score"]
        pred_total = pred.get("expected_total_goals", 2.5)

        true_totals.append(actual_total)
        pred_totals.append(pred_total)

        over25_true.append(int(actual_total > 2.5))
        over25_prob.append(pred.get("prob_over_2_5", 0.5))

        segs = m.get("segments", [])
        h1 = next((s for s in segs if s["segment_code"] == "H1"), None)
        if h1:
            h1_total = h1.get("total_goals", 0)
            over15_h1_true.append(int(h1_total > 1.5))
            over15_h1_prob.append(pred.get("prob_over_1_5_h1", 0.3))

    if not true_totals:
        return {"error": "No test predictions generated"}

    errors = [abs(p - t) for p, t in zip(pred_totals, true_totals)]
    sq_errors = [(p - t) ** 2 for p, t in zip(pred_totals, true_totals)]

    result = {
        "league": league_code,
        "train_size": n_train,
        "test_size": len(true_totals),
        "markets": {
            "total_goals": {
                "mae": round(float(np.mean(errors)), 4),
                "rmse": round(float(np.sqrt(np.mean(sq_errors))), 4),
                "brier_score": round(brier_score(over25_true, over25_prob), 4),
                "calibration_error": round(calibration_error(over25_true, over25_prob), 4),
                "sample_size": len(true_totals),
            }
        },
        "period": "walk-forward 60/40",
    }

    if over15_h1_true:
        h1_errors = [abs(pred.get("expected_goals_h1", 0.7) - (t / 2)) for t in over15_h1_true]
        result["markets"]["h1_goals"] = {
            "mae": round(float(np.mean(h1_errors)), 4),
            "rmse": round(float(np.sqrt(np.mean([e**2 for e in h1_errors]))), 4),
            "brier_score": round(brier_score(over15_h1_true, over15_h1_prob), 4),
            "calibration_error": round(calibration_error(over15_h1_true, over15_h1_prob), 4),
            "sample_size": len(over15_h1_true),
        }

    return result


def backtest_nhl_model(matches: List[Dict]) -> Dict:
    from ml.models.hockey_model import NHLEnsemble

    if len(matches) < 10:
        return {"error": "Not enough NHL matches"}

    n_train = int(len(matches) * 0.6)
    train = matches[:n_train]
    test = matches[n_train:]

    model = NHLEnsemble()
    model.fit(train)

    true_totals, pred_totals = [], []
    over55_true, over55_prob = [], []

    for m in test:
        if m.get("home_score") is None:
            continue
        try:
            pred = model.predict(m["home_team"], m["away_team"])
        except Exception:
            continue

        actual = m["home_score"] + m["away_score"]
        predicted = pred.get("expected_total_goals", 5.5)
        true_totals.append(actual)
        pred_totals.append(predicted)
        over55_true.append(int(actual > 5.5))
        over55_prob.append(pred.get("prob_over_5_5", 0.45))

    if not true_totals:
        return {"error": "No test predictions"}

    errors = [abs(p - t) for p, t in zip(pred_totals, true_totals)]
    sq_errors = [(p - t) ** 2 for p, t in zip(pred_totals, true_totals)]

    return {
        "league": "NHL",
        "train_size": n_train,
        "test_size": len(true_totals),
        "markets": {
            "total_goals": {
                "mae": round(float(np.mean(errors)), 4),
                "rmse": round(float(np.sqrt(np.mean(sq_errors))), 4),
                "brier_score": round(brier_score(over55_true, over55_prob), 4),
                "calibration_error": round(calibration_error(over55_true, over55_prob), 4),
                "sample_size": len(true_totals),
            }
        },
        "period": "walk-forward 60/40",
    }

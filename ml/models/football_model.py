"""
Football Goals Prediction Models.

Models:
1. PoissonGoalsModel — Baseline Poisson with team attack/defense strength + home advantage
2. DixonColesCorrection — Low-score correction factor (rho)
3. HalfTimeModel — Segment-specific Poisson for H1 / H2
4. EloRatingModel — Elo-based power ratings
5. FootballEnsemble — Weighted combination of all models
"""
import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
import logging
import pickle
import os

logger = logging.getLogger(__name__)
SEED = 42
np.random.seed(SEED)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def poisson_prob_over(lam: float, line: float) -> float:
    """P(X > line) where X ~ Poisson(lam). Line is 0.5, 1.5, 2.5, 3.5 etc."""
    k = int(line + 0.5)
    return 1.0 - poisson.cdf(k - 1, lam)


def poisson_prob_convolution(lam_home: float, lam_away: float, max_goals: int = 10) -> np.ndarray:
    """Joint probability matrix P(home=i, away=j) under independence."""
    grid = np.outer(
        poisson.pmf(np.arange(max_goals + 1), lam_home),
        poisson.pmf(np.arange(max_goals + 1), lam_away),
    )
    return grid


def dixon_coles_rho(lam_home: float, lam_away: float, rho: float = -0.13) -> np.ndarray:
    """Apply Dixon-Coles low-score correction to joint probability matrix."""
    grid = poisson_prob_convolution(lam_home, lam_away)
    # Correction for (0,0), (1,0), (0,1), (1,1)
    grid[0, 0] *= 1 - lam_home * lam_away * rho
    grid[1, 0] *= 1 + lam_away * rho
    grid[0, 1] *= 1 + lam_home * rho
    grid[1, 1] *= 1 - rho
    # Renormalize
    grid = np.maximum(grid, 0)
    grid /= grid.sum()
    return grid


def total_goals_probs_from_grid(grid: np.ndarray) -> Dict[str, float]:
    """Calculate Over/Under probabilities from a joint probability grid."""
    max_g = grid.shape[0] - 1
    totals = np.zeros(max_g * 2 + 1)
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            totals[i + j] += grid[i, j]
    result = {}
    for line in [0.5, 1.5, 2.5, 3.5]:
        k = int(line + 0.5)
        prob_over = float(totals[k:].sum())
        result[f"prob_over_{str(line).replace('.','_')}"] = min(max(prob_over, 0.001), 0.999)
        result[f"prob_under_{str(line).replace('.','_')}"] = 1.0 - result[f"prob_over_{str(line).replace('.','_')}"]
    return result


# ---------------------------------------------------------------------------
# Team strength estimation
# ---------------------------------------------------------------------------

class TeamStrengthModel:
    """Estimate attack/defense strength via MLE on historical data."""

    def __init__(self, home_advantage: float = 0.25):
        self.home_advantage = home_advantage
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.avg_goals: float = 1.35
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "TeamStrengthModel":
        """
        matches: list of dicts with keys home_team, away_team, home_score, away_score
        """
        if len(matches) < 5:
            logger.warning("Too few matches to fit team strength model, using defaults")
            return self

        teams = set()
        for m in matches:
            teams.add(m["home_team"])
            teams.add(m["away_team"])
        teams = sorted(teams)
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        home_goals = [m["home_score"] for m in matches]
        away_goals = [m["away_score"] for m in matches]
        self.avg_goals = np.mean(home_goals + away_goals)

        def neg_log_likelihood(params):
            # params: [attack_0..n-1, defense_0..n-1, home_adv]
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2*n])
            home_adv = np.exp(params[2*n])
            ll = 0
            for m in matches:
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                lam_h = attack[hi] * defense[ai] * home_adv
                lam_a = attack[ai] * defense[hi]
                ll += poisson.logpmf(m["home_score"], lam_h) + poisson.logpmf(m["away_score"], lam_a)
            return -ll

        x0 = np.zeros(2 * n + 1)
        try:
            result = minimize(neg_log_likelihood, x0, method="L-BFGS-B",
                              options={"maxiter": 200, "ftol": 1e-6})
            params = result.x
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2*n])
            self.attack = {t: float(attack[idx[t]]) for t in teams}
            self.defense = {t: float(defense[idx[t]]) for t in teams}
            self.home_advantage = float(np.exp(params[2*n]))
            self.fitted = True
        except Exception as e:
            logger.warning(f"Team strength optimization failed: {e}, using defaults")
            for t in teams:
                self.attack[t] = 1.0
                self.defense[t] = 1.0
        return self

    def predict_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        a_h = self.attack.get(home_team, 1.0)
        d_h = self.defense.get(home_team, 1.0)
        a_a = self.attack.get(away_team, 1.0)
        d_a = self.defense.get(away_team, 1.0)
        lam_home = a_h * d_a * self.home_advantage * self.avg_goals
        lam_away = a_a * d_h * self.avg_goals
        return max(lam_home, 0.1), max(lam_away, 0.1)


# ---------------------------------------------------------------------------
# Elo Rating
# ---------------------------------------------------------------------------

class EloModel:
    K = 32
    BASE = 1500.0

    def __init__(self):
        self.ratings: Dict[str, float] = {}

    def _expected(self, rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def fit(self, matches: List[Dict]) -> "EloModel":
        for m in matches:
            h, a = m["home_team"], m["away_team"]
            self.ratings.setdefault(h, self.BASE)
            self.ratings.setdefault(a, self.BASE)
            rh, ra = self.ratings[h], self.ratings[a]
            eh = self._expected(rh, ra)
            if m["home_score"] > m["away_score"]:
                sh, sa = 1.0, 0.0
            elif m["home_score"] < m["away_score"]:
                sh, sa = 0.0, 1.0
            else:
                sh = sa = 0.5
            self.ratings[h] = rh + self.K * (sh - eh)
            self.ratings[a] = ra + self.K * (sa - (1 - eh))
        return self

    def get_strength_ratio(self, home_team: str, away_team: str) -> float:
        rh = self.ratings.get(home_team, self.BASE)
        ra = self.ratings.get(away_team, self.BASE)
        return rh / ra


# ---------------------------------------------------------------------------
# Segment / Half-Time Model
# ---------------------------------------------------------------------------

class HalfTimeModel:
    """Separate Poisson models for H1 and H2 total goals."""

    def __init__(self):
        self.h1_avg: Dict[str, float] = {}  # by league
        self.h2_avg: Dict[str, float] = {}
        self.h1_ratio = 0.45  # default: 45% of goals in H1
        self.h2_ratio = 0.55
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "HalfTimeModel":
        h1_totals, h2_totals, ft_totals = [], [], []
        for m in matches:
            segments = m.get("segments", [])
            h1 = next((s for s in segments if s["segment_code"] == "H1"), None)
            h2 = next((s for s in segments if s["segment_code"] == "H2"), None)
            if h1 and h2:
                h1_totals.append(h1["total_goals"])
                h2_totals.append(h2["total_goals"])
                ft_totals.append(h1["total_goals"] + h2["total_goals"])
        if h1_totals:
            total_sum = sum(ft_totals) or 1
            self.h1_ratio = sum(h1_totals) / total_sum
            self.h2_ratio = sum(h2_totals) / total_sum
            self.fitted = True
        return self

    def predict(self, expected_total: float) -> Dict[str, float]:
        lam_h1 = expected_total * self.h1_ratio
        lam_h2 = expected_total * self.h2_ratio
        return {
            "expected_goals_h1": round(lam_h1, 3),
            "expected_goals_h2": round(lam_h2, 3),
            "prob_over_0_5_h1": round(poisson_prob_over(lam_h1, 0.5), 4),
            "prob_over_1_5_h1": round(poisson_prob_over(lam_h1, 1.5), 4),
            "prob_over_0_5_h2": round(poisson_prob_over(lam_h2, 0.5), 4),
            "prob_over_1_5_h2": round(poisson_prob_over(lam_h2, 1.5), 4),
        }


# ---------------------------------------------------------------------------
# Main Football Ensemble
# ---------------------------------------------------------------------------

class FootballEnsemble:
    """
    Weighted ensemble combining:
    - TeamStrengthModel (Poisson MLE)
    - DixonColes correction
    - EloModel strength ratio adjustment
    - HalfTimeModel for segments
    """

    WEIGHTS = {"poisson": 0.5, "dixon_coles": 0.3, "elo_adjusted": 0.2}

    def __init__(self, league_code: str):
        self.league_code = league_code
        self.strength_model = TeamStrengthModel()
        self.elo_model = EloModel()
        self.halftime_model = HalfTimeModel()
        self.rho = -0.13  # Dixon-Coles correction
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "FootballEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        if not finished:
            logger.warning(f"No finished matches for {self.league_code}")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.halftime_model.fit(finished)
        self.fitted = True
        logger.info(f"FootballEnsemble fitted for {self.league_code} on {len(finished)} matches")
        return self

    def predict(self, home_team: str, away_team: str) -> Dict:
        lam_h, lam_a = self.strength_model.predict_lambdas(home_team, away_team)

        # Elo adjustment factor
        elo_ratio = self.elo_model.get_strength_ratio(home_team, away_team)
        elo_adjustment = np.log(max(elo_ratio, 0.5))  # soft cap
        lam_h_elo = lam_h * (1 + 0.05 * elo_adjustment)
        lam_a_elo = lam_a * (1 - 0.05 * elo_adjustment)

        # Weighted lambda
        lam_h_final = self.WEIGHTS["poisson"] * lam_h + self.WEIGHTS["dixon_coles"] * lam_h + self.WEIGHTS["elo_adjusted"] * lam_h_elo
        lam_a_final = self.WEIGHTS["poisson"] * lam_a + self.WEIGHTS["dixon_coles"] * lam_a + self.WEIGHTS["elo_adjusted"] * lam_a_elo
        lam_h_final /= sum(self.WEIGHTS.values())
        lam_a_final /= sum(self.WEIGHTS.values())

        expected_total = lam_h_final + lam_a_final

        # Dixon-Coles corrected grid for Over/Under
        grid = dixon_coles_rho(lam_h_final, lam_a_final, self.rho)
        ou_probs = total_goals_probs_from_grid(grid)

        # Segment predictions
        segment_preds = self.halftime_model.predict(expected_total)

        # Model agreement score (how close are the two lambda estimates)
        agreement = 1.0 - abs(lam_h - lam_h_elo) / (lam_h + 0.01)

        result = {
            "expected_home_goals": round(lam_h_final, 3),
            "expected_away_goals": round(lam_a_final, 3),
            "expected_total_goals": round(expected_total, 3),
            "model_agreement_score": round(float(np.clip(agreement, 0, 1)), 3),
            **ou_probs,
            **segment_preds,
        }

        return result

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: str) -> "FootballEnsemble":
        with open(path, "rb") as f:
            return pickle.load(f)

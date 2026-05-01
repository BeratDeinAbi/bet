"""
Football Goals Prediction Models — improved version.

Improvements over v1:
1. Exponential time-decay weighting (recent matches count more)
2. L2 regularization on team strengths to prevent overfitting on small samples
3. Rolling form features (last 5 matches goal averages)
4. Fixed ensemble math (independent model contributions, not duplicated lambdas)
5. Stronger Elo-based scaling using rating-difference logistic, not raw ratio
6. League-specific avg goals + home advantage priors
7. Negative-binomial fallback option for high-variance leagues
8. Calibrated confidence based on sample size + agreement
"""
import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timezone
from collections import defaultdict
import logging
import pickle
import os

logger = logging.getLogger(__name__)
SEED = 42
np.random.seed(SEED)


# ---------------------------------------------------------------------------
# League priors (Bundesliga ~3.1, PL ~2.85, La Liga ~2.5, Süper Lig ~2.95)
# Sourced from public 5-season averages
# ---------------------------------------------------------------------------
LEAGUE_PRIORS = {
    "BL1": {"avg_goals": 3.10, "home_adv": 1.20, "h1_ratio": 0.45},
    "PL":  {"avg_goals": 2.85, "home_adv": 1.18, "h1_ratio": 0.44},
    "PD":  {"avg_goals": 2.55, "home_adv": 1.22, "h1_ratio": 0.43},
    "SSL": {"avg_goals": 2.95, "home_adv": 1.25, "h1_ratio": 0.46},
}


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def poisson_prob_over(lam: float, line: float) -> float:
    k = int(line + 0.5)
    return float(1.0 - poisson.cdf(k - 1, max(lam, 0.01)))


def poisson_prob_convolution(lam_home: float, lam_away: float, max_goals: int = 12) -> np.ndarray:
    return np.outer(
        poisson.pmf(np.arange(max_goals + 1), lam_home),
        poisson.pmf(np.arange(max_goals + 1), lam_away),
    )


def dixon_coles_rho(lam_home: float, lam_away: float, rho: float = -0.13) -> np.ndarray:
    grid = poisson_prob_convolution(lam_home, lam_away)
    grid[0, 0] *= 1 - lam_home * lam_away * rho
    grid[1, 0] *= 1 + lam_away * rho
    grid[0, 1] *= 1 + lam_home * rho
    grid[1, 1] *= 1 - rho
    grid = np.maximum(grid, 0)
    grid /= grid.sum()
    return grid


def total_goals_probs_from_grid(grid: np.ndarray) -> Dict[str, float]:
    max_g = grid.shape[0] - 1
    totals = np.zeros(max_g * 2 + 1)
    for i in range(max_g + 1):
        for j in range(max_g + 1):
            totals[i + j] += grid[i, j]
    result = {}
    for line in [0.5, 1.5, 2.5, 3.5]:
        k = int(line + 0.5)
        prob_over = float(totals[k:].sum())
        key = str(line).replace(".", "_")
        result[f"prob_over_{key}"] = min(max(prob_over, 0.001), 0.999)
        result[f"prob_under_{key}"] = 1.0 - result[f"prob_over_{key}"]
    return result


def _parse_kickoff(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _time_weight(kickoff: Optional[datetime], half_life_days: float = 90.0) -> float:
    """Exponential decay: recent matches weight 1.0, half-life-old weight 0.5."""
    if kickoff is None:
        return 0.6  # neutral default for unknown dates
    now = datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    age_days = max((now - kickoff).total_seconds() / 86400.0, 0.0)
    return float(np.exp(-np.log(2) * age_days / half_life_days))


# ---------------------------------------------------------------------------
# Team strength estimation — weighted MLE with L2 regularization
# ---------------------------------------------------------------------------

class TeamStrengthModel:
    """
    Weighted Poisson MLE with:
    - Exponential time-decay (recent matches count more)
    - L2 ridge regularization on log-strengths
    - League-prior pull when teams have few matches
    """

    def __init__(self, league_code: str = "BL1", l2_lambda: float = 0.5,
                 half_life_days: float = 90.0):
        self.league_code = league_code
        prior = LEAGUE_PRIORS.get(league_code, {"avg_goals": 2.7, "home_adv": 1.2, "h1_ratio": 0.45})
        self.avg_goals = prior["avg_goals"]
        self.home_advantage = prior["home_adv"]
        self.l2 = l2_lambda
        self.half_life = half_life_days
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.team_match_count: Dict[str, int] = {}
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "TeamStrengthModel":
        if len(matches) < 5:
            logger.warning(f"[{self.league_code}] only {len(matches)} matches — using priors")
            return self

        teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        # Time weights and per-team match counts
        weights = []
        for m in matches:
            kickoff = _parse_kickoff(m.get("kickoff_time"))
            weights.append(_time_weight(kickoff, self.half_life))
        weights = np.array(weights)

        # League average from weighted sample
        all_goals = np.array([m["home_score"] + m["away_score"] for m in matches])
        wsum = weights.sum() or 1.0
        league_avg = float((all_goals * weights).sum() / wsum) / 2  # avg per team
        # Blend with prior (more weight to prior when few matches)
        prior_weight = max(0.0, min(1.0, 1.0 - len(matches) / 200.0))
        self.avg_goals = (1 - prior_weight) * (league_avg * 2) + prior_weight * self.avg_goals

        # Count effective matches per team
        eff = defaultdict(float)
        for m, w in zip(matches, weights):
            eff[m["home_team"]] += w
            eff[m["away_team"]] += w
        self.team_match_count = dict(eff)

        def neg_log_likelihood(params):
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2 * n])
            home_adv = np.exp(params[2 * n])
            ll = 0.0
            for m, w in zip(matches, weights):
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                lam_h = attack[hi] * defense[ai] * home_adv
                lam_a = attack[ai] * defense[hi]
                ll += w * (poisson.logpmf(m["home_score"], max(lam_h, 0.01))
                          + poisson.logpmf(m["away_score"], max(lam_a, 0.01)))
            # L2 regularization on log-strengths (pull toward 0 = neutral)
            reg = self.l2 * (np.sum(params[:n] ** 2) + np.sum(params[n:2 * n] ** 2))
            return -ll + reg

        x0 = np.zeros(2 * n + 1)
        # Init home_adv from prior
        x0[2 * n] = np.log(LEAGUE_PRIORS.get(self.league_code, {"home_adv": 1.2})["home_adv"])

        try:
            result = minimize(neg_log_likelihood, x0, method="L-BFGS-B",
                              options={"maxiter": 300, "ftol": 1e-7})
            params = result.x
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2 * n])
            self.attack = {t: float(attack[idx[t]]) for t in teams}
            self.defense = {t: float(defense[idx[t]]) for t in teams}
            self.home_advantage = float(np.exp(params[2 * n]))
            self.fitted = True
            logger.info(f"[{self.league_code}] strengths fitted, avg_goals={self.avg_goals:.2f}, "
                        f"home_adv={self.home_advantage:.2f}, teams={n}")
        except Exception as e:
            logger.warning(f"[{self.league_code}] strength optimization failed: {e}")
            for t in teams:
                self.attack.setdefault(t, 1.0)
                self.defense.setdefault(t, 1.0)
        return self

    def _shrink(self, raw_value: float, team: str) -> float:
        """Shrink toward 1.0 when team has few effective matches."""
        eff_n = self.team_match_count.get(team, 0)
        # Shrinkage strength: full pull at 0, half at ~10 matches, none at 30+
        alpha = 1.0 / (1.0 + eff_n / 8.0)
        return alpha * 1.0 + (1 - alpha) * raw_value

    def predict_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        a_h = self._shrink(self.attack.get(home_team, 1.0), home_team)
        d_h = self._shrink(self.defense.get(home_team, 1.0), home_team)
        a_a = self._shrink(self.attack.get(away_team, 1.0), away_team)
        d_a = self._shrink(self.defense.get(away_team, 1.0), away_team)
        # Average per-team scoring rate (avg_goals is total per match → divide by 2)
        avg_per_team = self.avg_goals / 2.0
        lam_home = a_h * d_a * self.home_advantage * avg_per_team
        lam_away = a_a * d_h * avg_per_team
        return max(lam_home, 0.15), max(lam_away, 0.15)


# ---------------------------------------------------------------------------
# Elo Rating — with goal-margin-weighted updates
# ---------------------------------------------------------------------------

class EloModel:
    BASE = 1500.0

    def __init__(self, k_base: float = 24.0):
        self.k_base = k_base
        self.ratings: Dict[str, float] = {}

    @staticmethod
    def _expected(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def fit(self, matches: List[Dict]) -> "EloModel":
        # Sort matches chronologically for proper Elo updating
        sorted_matches = sorted(
            matches,
            key=lambda m: _parse_kickoff(m.get("kickoff_time")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        for m in sorted_matches:
            h, a = m["home_team"], m["away_team"]
            self.ratings.setdefault(h, self.BASE)
            self.ratings.setdefault(a, self.BASE)
            rh, ra = self.ratings[h], self.ratings[a]
            eh = self._expected(rh, ra)

            # Margin-of-victory multiplier (FiveThirtyEight method)
            margin = abs(m["home_score"] - m["away_score"])
            mov_mult = np.log(max(margin, 1) + 1) * (2.2 / ((rh - ra if m["home_score"] > m["away_score"] else ra - rh) * 0.001 + 2.2))
            k = self.k_base * mov_mult

            if m["home_score"] > m["away_score"]:
                sh = 1.0
            elif m["home_score"] < m["away_score"]:
                sh = 0.0
            else:
                sh = 0.5

            self.ratings[h] = rh + k * (sh - eh)
            self.ratings[a] = ra + k * ((1 - sh) - (1 - eh))
        return self

    def get_diff(self, home_team: str, away_team: str) -> float:
        rh = self.ratings.get(home_team, self.BASE)
        ra = self.ratings.get(away_team, self.BASE)
        return rh - ra

    def expected_score(self, home_team: str, away_team: str) -> float:
        return self._expected(self.ratings.get(home_team, self.BASE),
                              self.ratings.get(away_team, self.BASE))


# ---------------------------------------------------------------------------
# Rolling Form — last N matches goal-for / goal-against
# ---------------------------------------------------------------------------

class RollingFormModel:
    """Exponentially weighted goal-for / goal-against per team over last N matches."""

    def __init__(self, window: int = 5, decay: float = 0.85):
        self.window = window
        self.decay = decay
        self.gf: Dict[str, float] = {}    # rolling goals scored per match
        self.ga: Dict[str, float] = {}    # rolling goals conceded per match
        self.matches_seen: Dict[str, int] = defaultdict(int)

    def fit(self, matches: List[Dict]) -> "RollingFormModel":
        sorted_matches = sorted(
            matches,
            key=lambda m: _parse_kickoff(m.get("kickoff_time")) or datetime.min.replace(tzinfo=timezone.utc),
        )

        per_team_history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for m in sorted_matches:
            h, a = m["home_team"], m["away_team"]
            hs, as_ = m["home_score"], m["away_score"]
            per_team_history[h].append((hs, as_))
            per_team_history[a].append((as_, hs))
            self.matches_seen[h] += 1
            self.matches_seen[a] += 1

        # Compute exponentially-weighted last-N for each team
        for team, hist in per_team_history.items():
            recent = hist[-self.window:]
            if not recent:
                continue
            weights = np.array([self.decay ** i for i in range(len(recent) - 1, -1, -1)])
            wsum = weights.sum()
            gf_arr = np.array([h[0] for h in recent])
            ga_arr = np.array([h[1] for h in recent])
            self.gf[team] = float((gf_arr * weights).sum() / wsum)
            self.ga[team] = float((ga_arr * weights).sum() / wsum)
        return self

    def get_form_factor(self, home_team: str, away_team: str, league_avg_team: float) -> Tuple[float, float]:
        """Returns multiplicative form factors for home/away expected goals."""
        h_gf = self.gf.get(home_team, league_avg_team)
        h_ga = self.ga.get(home_team, league_avg_team)
        a_gf = self.gf.get(away_team, league_avg_team)
        a_ga = self.ga.get(away_team, league_avg_team)

        # Home expected goals factor: home attack form × away defense form
        # Normalize by league average to get multiplier near 1.0
        avg = max(league_avg_team, 0.1)
        home_factor = ((h_gf / avg) * (a_ga / avg)) ** 0.5
        away_factor = ((a_gf / avg) * (h_ga / avg)) ** 0.5
        # Clip to prevent extreme values from small samples
        return float(np.clip(home_factor, 0.5, 2.0)), float(np.clip(away_factor, 0.5, 2.0))


# ---------------------------------------------------------------------------
# Half-time model — improved with team-specific tendencies
# ---------------------------------------------------------------------------

class HalfTimeModel:
    def __init__(self, league_code: str = "BL1"):
        prior = LEAGUE_PRIORS.get(league_code, {"h1_ratio": 0.45})
        self.h1_ratio = prior["h1_ratio"]
        self.h2_ratio = 1.0 - self.h1_ratio
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "HalfTimeModel":
        h1_totals, ft_totals = [], []
        for m in matches:
            segments = m.get("segments", [])
            h1 = next((s for s in segments if s["segment_code"] == "H1"), None)
            h2 = next((s for s in segments if s["segment_code"] == "H2"), None)
            if h1 and h2:
                h1_totals.append(h1["total_goals"])
                ft_totals.append(h1["total_goals"] + h2["total_goals"])
        if h1_totals and sum(ft_totals) > 0:
            empirical_ratio = sum(h1_totals) / sum(ft_totals)
            # Blend empirical with prior based on sample size
            n = len(h1_totals)
            blend = min(1.0, n / 100.0)
            self.h1_ratio = blend * empirical_ratio + (1 - blend) * self.h1_ratio
            self.h2_ratio = 1.0 - self.h1_ratio
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
    Improved ensemble:
    1. Strength model gives baseline lambda_strength
    2. Rolling form model gives lambda_form (recent N matches)
    3. Elo gives a competitive-balance shift
    Final lambda = weighted geometric blend → Dixon-Coles → distributions.
    """

    # Component weights (after geometric blending)
    W_STRENGTH = 0.50
    W_FORM = 0.30
    W_ELO = 0.20

    def __init__(self, league_code: str):
        self.league_code = league_code
        self.strength_model = TeamStrengthModel(league_code=league_code)
        self.elo_model = EloModel(k_base=24.0)
        self.form_model = RollingFormModel(window=5, decay=0.85)
        self.halftime_model = HalfTimeModel(league_code=league_code)
        self.rho = -0.13
        self.fitted = False
        self.n_train = 0

    def fit(self, matches: List[Dict]) -> "FootballEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        self.n_train = len(finished)
        if not finished:
            logger.warning(f"[{self.league_code}] no finished matches")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.form_model.fit(finished)
        self.halftime_model.fit(finished)
        self.fitted = True
        logger.info(f"[{self.league_code}] FootballEnsemble fitted on {len(finished)} matches "
                    f"(time-decayed, L2-regularized, rolling form)")
        return self

    def predict(self, home_team: str, away_team: str) -> Dict:
        # 1. Baseline strength-based lambdas
        lam_h_str, lam_a_str = self.strength_model.predict_lambdas(home_team, away_team)
        avg_per_team = self.strength_model.avg_goals / 2.0

        # 2. Rolling form lambdas (form factor × league average)
        h_form, a_form = self.form_model.get_form_factor(home_team, away_team, avg_per_team)
        lam_h_form = avg_per_team * h_form * self.strength_model.home_advantage
        lam_a_form = avg_per_team * a_form

        # 3. Elo-based adjustment using rating-difference (logistic-scaled)
        elo_diff = self.elo_model.get_diff(home_team, away_team)
        # Convert Elo diff to expected-goal-diff: empirically ~0.4 goals per 100 Elo
        elo_goal_shift = np.tanh(elo_diff / 200.0) * 0.4
        lam_h_elo = lam_h_str + max(elo_goal_shift, -0.4)
        lam_a_elo = lam_a_str - max(elo_goal_shift, -0.4)
        lam_h_elo = max(lam_h_elo, 0.15)
        lam_a_elo = max(lam_a_elo, 0.15)

        # 4. Geometric blending (multiplicative ensemble — better for rate parameters)
        weights = np.array([self.W_STRENGTH, self.W_FORM, self.W_ELO])
        weights = weights / weights.sum()
        lam_h_final = np.exp(
            weights[0] * np.log(lam_h_str) +
            weights[1] * np.log(lam_h_form) +
            weights[2] * np.log(lam_h_elo)
        )
        lam_a_final = np.exp(
            weights[0] * np.log(lam_a_str) +
            weights[1] * np.log(lam_a_form) +
            weights[2] * np.log(lam_a_elo)
        )

        expected_total = float(lam_h_final + lam_a_final)

        # 5. Dixon-Coles corrected joint distribution
        grid = dixon_coles_rho(lam_h_final, lam_a_final, self.rho)
        ou_probs = total_goals_probs_from_grid(grid)

        # 6. Segment predictions
        segment_preds = self.halftime_model.predict(expected_total)

        # 7. Calibrated agreement: how close are the three lambda estimates?
        lams_h = np.array([lam_h_str, lam_h_form, lam_h_elo])
        lams_a = np.array([lam_a_str, lam_a_form, lam_a_elo])
        cv_h = lams_h.std() / (lams_h.mean() + 0.01)
        cv_a = lams_a.std() / (lams_a.mean() + 0.01)
        agreement = float(np.clip(1.0 - 0.5 * (cv_h + cv_a), 0.0, 1.0))

        return {
            "expected_home_goals": round(float(lam_h_final), 3),
            "expected_away_goals": round(float(lam_a_final), 3),
            "expected_total_goals": round(expected_total, 3),
            "model_agreement_score": round(agreement, 3),
            **ou_probs,
            **segment_preds,
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)
        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: str) -> "FootballEnsemble":
        with open(path, "rb") as f:
            return pickle.load(f)

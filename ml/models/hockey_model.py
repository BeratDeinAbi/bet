"""
NHL Hockey Goals Prediction Models.

Models:
1. NHLPoissonModel — Baseline Poisson with team strength + home advantage
2. PeriodModel — Separate Poisson for P1, P2, P3
3. EloModel (shared with football base)
4. NHLEnsemble — Weighted combination
"""
import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
from typing import Dict, List, Tuple
import logging
import pickle
import os

logger = logging.getLogger(__name__)
SEED = 42
np.random.seed(SEED)


def poisson_prob_over(lam: float, line: float) -> float:
    k = int(line + 0.5)
    return float(1.0 - poisson.cdf(k - 1, lam))


class NHLTeamStrengthModel:
    """Attack/defense MLE for NHL teams."""

    def __init__(self, home_advantage: float = 0.10):
        self.home_advantage = home_advantage
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.avg_goals: float = 3.0
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NHLTeamStrengthModel":
        if len(matches) < 5:
            return self
        teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}
        all_goals = [m["home_score"] for m in matches] + [m["away_score"] for m in matches]
        self.avg_goals = np.mean(all_goals)

        def neg_ll(params):
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2*n])
            home_adv = np.exp(params[2*n])
            ll = 0
            for m in matches:
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                lam_h = attack[hi] * defense[ai] * home_adv * self.avg_goals
                lam_a = attack[ai] * defense[hi] * self.avg_goals
                ll += poisson.logpmf(m["home_score"], max(lam_h, 0.01))
                ll += poisson.logpmf(m["away_score"], max(lam_a, 0.01))
            return -ll

        x0 = np.zeros(2 * n + 1)
        try:
            res = minimize(neg_ll, x0, method="L-BFGS-B", options={"maxiter": 200})
            params = res.x
            atk = np.exp(params[:n])
            dfc = np.exp(params[n:2*n])
            self.attack = {t: float(atk[idx[t]]) for t in teams}
            self.defense = {t: float(dfc[idx[t]]) for t in teams}
            self.home_advantage = float(np.exp(params[2*n]))
            self.fitted = True
        except Exception as e:
            logger.warning(f"NHL team strength fit failed: {e}")
            for t in teams:
                self.attack[t] = 1.0
                self.defense[t] = 1.0
        return self

    def predict_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        a_h = self.attack.get(home_team, 1.0)
        d_h = self.defense.get(home_team, 1.0)
        a_a = self.attack.get(away_team, 1.0)
        d_a = self.defense.get(away_team, 1.0)
        lam_h = a_h * d_a * self.home_advantage * self.avg_goals
        lam_a = a_a * d_h * self.avg_goals
        return max(lam_h, 0.1), max(lam_a, 0.1)


class NHLEloModel:
    K = 20
    BASE = 1500.0

    def __init__(self):
        self.ratings: Dict[str, float] = {}

    def _expected(self, ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))

    def fit(self, matches: List[Dict]) -> "NHLEloModel":
        for m in matches:
            h, a = m["home_team"], m["away_team"]
            self.ratings.setdefault(h, self.BASE)
            self.ratings.setdefault(a, self.BASE)
            rh, ra = self.ratings[h], self.ratings[a]
            eh = self._expected(rh, ra)
            sh = 1.0 if m["home_score"] > m["away_score"] else (0.0 if m["home_score"] < m["away_score"] else 0.5)
            self.ratings[h] = rh + self.K * (sh - eh)
            self.ratings[a] = ra + self.K * ((1 - sh) - (1 - eh))
        return self

    def strength_ratio(self, home_team: str, away_team: str) -> float:
        rh = self.ratings.get(home_team, self.BASE)
        ra = self.ratings.get(away_team, self.BASE)
        return rh / ra


class NHLPeriodModel:
    """
    Models goal distribution across periods.
    Historical NHL averages: ~32% P1, ~34% P2, ~34% P3 (regulation).
    """
    DEFAULT = {"P1": 0.32, "P2": 0.34, "P3": 0.34}

    def __init__(self):
        self.ratios = dict(self.DEFAULT)
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NHLPeriodModel":
        period_goals = {"P1": [], "P2": [], "P3": []}
        total_goals = []
        for m in matches:
            segments = m.get("segments", [])
            pg = {}
            for seg in segments:
                code = seg.get("segment_code", "")
                if code in period_goals:
                    pg[code] = seg.get("total_goals", 0)
            if len(pg) == 3:
                total = sum(pg.values()) or 1
                total_goals.append(total)
                for p in period_goals:
                    period_goals[p].append(pg[p])
        if total_goals:
            total_sum = sum(total_goals) or 1
            for p in period_goals:
                self.ratios[p] = sum(period_goals[p]) / total_sum
            self.fitted = True
        return self

    def predict(self, expected_total: float) -> Dict[str, float]:
        result = {}
        for p_code, ratio in self.ratios.items():
            lam = expected_total * ratio
            p_key = p_code.lower()
            result[f"expected_goals_{p_key}"] = round(lam, 3)
            result[f"prob_over_0_5_{p_key}"] = round(poisson_prob_over(lam, 0.5), 4)
            result[f"prob_over_1_5_{p_key}"] = round(poisson_prob_over(lam, 1.5), 4)
        return result


class NHLEnsemble:
    WEIGHTS = {"poisson": 0.6, "elo_adjusted": 0.4}

    def __init__(self):
        self.strength_model = NHLTeamStrengthModel()
        self.elo_model = NHLEloModel()
        self.period_model = NHLPeriodModel()
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NHLEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        if not finished:
            logger.warning("No finished NHL matches to fit")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.period_model.fit(finished)
        self.fitted = True
        logger.info(f"NHLEnsemble fitted on {len(finished)} matches")
        return self

    def predict(self, home_team: str, away_team: str) -> Dict:
        lam_h, lam_a = self.strength_model.predict_lambdas(home_team, away_team)
        elo_ratio = self.elo_model.strength_ratio(home_team, away_team)
        elo_adj = np.log(max(elo_ratio, 0.5))
        lam_h_elo = lam_h * (1 + 0.04 * elo_adj)
        lam_a_elo = lam_a * (1 - 0.04 * elo_adj)

        lam_h_f = self.WEIGHTS["poisson"] * lam_h + self.WEIGHTS["elo_adjusted"] * lam_h_elo
        lam_a_f = self.WEIGHTS["poisson"] * lam_a + self.WEIGHTS["elo_adjusted"] * lam_a_elo

        expected_total = lam_h_f + lam_a_f

        # Overall Over/Under probs
        ou = {}
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]:
            key = str(line).replace(".", "_")
            p_over = float(1.0 - poisson.cdf(int(line + 0.5) - 1, expected_total))
            ou[f"prob_over_{key}"] = round(min(max(p_over, 0.001), 0.999), 4)
            ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)

        period_preds = self.period_model.predict(expected_total)

        agreement = 1.0 - abs(lam_h - lam_h_elo) / (lam_h + 0.01)

        return {
            "expected_home_goals": round(lam_h_f, 3),
            "expected_away_goals": round(lam_a_f, 3),
            "expected_total_goals": round(expected_total, 3),
            "model_agreement_score": round(float(np.clip(agreement, 0, 1)), 3),
            **ou,
            **period_preds,
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str) -> "NHLEnsemble":
        with open(path, "rb") as f:
            return pickle.load(f)

"""
NHL Hockey Goals Prediction Models — improved version.

Improvements over v1:
1. Time-decay weighting on training matches
2. L2 regularization on team strengths
3. Rolling form (last 10 games for hockey)
4. Goal-margin-weighted Elo updates
5. Fixed ensemble math (geometric blending instead of duplicated lambdas)
6. NHL-specific priors (avg ~6.0 goals/game in regulation)
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

# NHL priors (recent seasons average ~6.1 goals per regulation game)
NHL_PRIOR = {
    "avg_goals": 6.10,
    "home_adv": 1.08,            # ~8% home advantage in NHL
    "p_ratio": [0.32, 0.34, 0.34],
}


def poisson_prob_over(lam: float, line: float) -> float:
    k = int(line + 0.5)
    return float(1.0 - poisson.cdf(k - 1, max(lam, 0.01)))


def _parse_kickoff(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _time_weight(kickoff: Optional[datetime], half_life_days: float = 75.0) -> float:
    if kickoff is None:
        return 0.6
    now = datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    age_days = max((now - kickoff).total_seconds() / 86400.0, 0.0)
    return float(np.exp(-np.log(2) * age_days / half_life_days))


# ---------------------------------------------------------------------------
# NHL Team Strength
# ---------------------------------------------------------------------------

class NHLTeamStrengthModel:
    def __init__(self, l2_lambda: float = 0.4, half_life_days: float = 75.0):
        self.l2 = l2_lambda
        self.half_life = half_life_days
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.team_match_count: Dict[str, float] = {}
        self.avg_goals = NHL_PRIOR["avg_goals"]
        self.home_advantage = NHL_PRIOR["home_adv"]
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NHLTeamStrengthModel":
        if len(matches) < 5:
            logger.warning(f"NHL only {len(matches)} matches — using priors")
            return self

        teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        weights = np.array([
            _time_weight(_parse_kickoff(m.get("kickoff_time")), self.half_life)
            for m in matches
        ])

        all_goals = np.array([m["home_score"] + m["away_score"] for m in matches])
        wsum = weights.sum() or 1.0
        league_avg = float((all_goals * weights).sum() / wsum)
        prior_weight = max(0.0, min(1.0, 1.0 - len(matches) / 200.0))
        self.avg_goals = (1 - prior_weight) * league_avg + prior_weight * self.avg_goals

        eff = defaultdict(float)
        for m, w in zip(matches, weights):
            eff[m["home_team"]] += w
            eff[m["away_team"]] += w
        self.team_match_count = dict(eff)

        def neg_ll(params):
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2 * n])
            home_adv = np.exp(params[2 * n])
            avg_per_team = self.avg_goals / 2.0
            ll = 0.0
            for m, w in zip(matches, weights):
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                lam_h = attack[hi] * defense[ai] * home_adv * avg_per_team
                lam_a = attack[ai] * defense[hi] * avg_per_team
                ll += w * (poisson.logpmf(m["home_score"], max(lam_h, 0.05))
                          + poisson.logpmf(m["away_score"], max(lam_a, 0.05)))
            reg = self.l2 * (np.sum(params[:n] ** 2) + np.sum(params[n:2 * n] ** 2))
            return -ll + reg

        x0 = np.zeros(2 * n + 1)
        x0[2 * n] = np.log(NHL_PRIOR["home_adv"])

        try:
            res = minimize(neg_ll, x0, method="L-BFGS-B", options={"maxiter": 300, "ftol": 1e-7})
            params = res.x
            atk = np.exp(params[:n])
            dfc = np.exp(params[n:2 * n])
            self.attack = {t: float(atk[idx[t]]) for t in teams}
            self.defense = {t: float(dfc[idx[t]]) for t in teams}
            self.home_advantage = float(np.exp(params[2 * n]))
            self.fitted = True
            logger.info(f"NHL strengths fitted, avg={self.avg_goals:.2f}, "
                        f"home_adv={self.home_advantage:.2f}, teams={n}")
        except Exception as e:
            logger.warning(f"NHL strength fit failed: {e}")
            for t in teams:
                self.attack.setdefault(t, 1.0)
                self.defense.setdefault(t, 1.0)
        return self

    def _shrink(self, value: float, team: str) -> float:
        eff_n = self.team_match_count.get(team, 0)
        alpha = 1.0 / (1.0 + eff_n / 10.0)
        return alpha * 1.0 + (1 - alpha) * value

    def predict_lambdas(self, home_team: str, away_team: str) -> Tuple[float, float]:
        a_h = self._shrink(self.attack.get(home_team, 1.0), home_team)
        d_h = self._shrink(self.defense.get(home_team, 1.0), home_team)
        a_a = self._shrink(self.attack.get(away_team, 1.0), away_team)
        d_a = self._shrink(self.defense.get(away_team, 1.0), away_team)
        avg_per_team = self.avg_goals / 2.0
        lam_h = a_h * d_a * self.home_advantage * avg_per_team
        lam_a = a_a * d_h * avg_per_team
        return max(lam_h, 0.3), max(lam_a, 0.3)


# ---------------------------------------------------------------------------
# NHL Elo
# ---------------------------------------------------------------------------

class NHLEloModel:
    BASE = 1500.0

    def __init__(self, k_base: float = 16.0):
        self.k_base = k_base
        self.ratings: Dict[str, float] = {}

    @staticmethod
    def _expected(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def fit(self, matches: List[Dict]) -> "NHLEloModel":
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

            margin = abs(m["home_score"] - m["away_score"])
            mov_mult = np.log(max(margin, 1) + 1)
            k = self.k_base * mov_mult

            sh = 1.0 if m["home_score"] > m["away_score"] else (0.0 if m["home_score"] < m["away_score"] else 0.5)
            self.ratings[h] = rh + k * (sh - eh)
            self.ratings[a] = ra + k * ((1 - sh) - (1 - eh))
        return self

    def get_diff(self, home_team: str, away_team: str) -> float:
        return self.ratings.get(home_team, self.BASE) - self.ratings.get(away_team, self.BASE)


# ---------------------------------------------------------------------------
# Rolling Form (last 10 games — hockey volatility is higher)
# ---------------------------------------------------------------------------

class NHLRollingForm:
    def __init__(self, window: int = 10, decay: float = 0.90):
        self.window = window
        self.decay = decay
        self.gf: Dict[str, float] = {}
        self.ga: Dict[str, float] = {}

    def fit(self, matches: List[Dict]) -> "NHLRollingForm":
        sorted_matches = sorted(
            matches,
            key=lambda m: _parse_kickoff(m.get("kickoff_time")) or datetime.min.replace(tzinfo=timezone.utc),
        )
        history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)
        for m in sorted_matches:
            history[m["home_team"]].append((m["home_score"], m["away_score"]))
            history[m["away_team"]].append((m["away_score"], m["home_score"]))

        for team, hist in history.items():
            recent = hist[-self.window:]
            if not recent:
                continue
            weights = np.array([self.decay ** i for i in range(len(recent) - 1, -1, -1)])
            wsum = weights.sum()
            self.gf[team] = float(sum(h[0] * w for h, w in zip(recent, weights)) / wsum)
            self.ga[team] = float(sum(h[1] * w for h, w in zip(recent, weights)) / wsum)
        return self

    def get_form_factor(self, home_team: str, away_team: str, league_avg_team: float) -> Tuple[float, float]:
        h_gf = self.gf.get(home_team, league_avg_team)
        h_ga = self.ga.get(home_team, league_avg_team)
        a_gf = self.gf.get(away_team, league_avg_team)
        a_ga = self.ga.get(away_team, league_avg_team)
        avg = max(league_avg_team, 0.1)
        home_factor = ((h_gf / avg) * (a_ga / avg)) ** 0.5
        away_factor = ((a_gf / avg) * (h_ga / avg)) ** 0.5
        return float(np.clip(home_factor, 0.6, 1.7)), float(np.clip(away_factor, 0.6, 1.7))


# ---------------------------------------------------------------------------
# Period Model
# ---------------------------------------------------------------------------

class NHLPeriodModel:
    def __init__(self):
        self.ratios = {"P1": NHL_PRIOR["p_ratio"][0], "P2": NHL_PRIOR["p_ratio"][1], "P3": NHL_PRIOR["p_ratio"][2]}
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
            n = len(total_goals)
            blend = min(1.0, n / 100.0)
            total_sum = sum(total_goals) or 1
            for p in period_goals:
                empirical = sum(period_goals[p]) / total_sum
                self.ratios[p] = blend * empirical + (1 - blend) * self.ratios[p]
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


# ---------------------------------------------------------------------------
# NHL Ensemble
# ---------------------------------------------------------------------------

class NHLEnsemble:
    W_STRENGTH = 0.55
    W_FORM = 0.30
    W_ELO = 0.15

    def __init__(self):
        self.strength_model = NHLTeamStrengthModel()
        self.elo_model = NHLEloModel(k_base=16.0)
        self.form_model = NHLRollingForm(window=10, decay=0.90)
        self.period_model = NHLPeriodModel()
        self.fitted = False
        self.n_train = 0

    def fit(self, matches: List[Dict]) -> "NHLEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        self.n_train = len(finished)
        if not finished:
            logger.warning("NHL: no finished matches")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.form_model.fit(finished)
        self.period_model.fit(finished)
        self.fitted = True
        logger.info(f"NHLEnsemble fitted on {len(finished)} matches "
                    f"(time-decayed, L2-regularized, rolling form)")
        return self

    def predict(self, home_team: str, away_team: str) -> Dict:
        # 1. Strength baseline
        lam_h_str, lam_a_str = self.strength_model.predict_lambdas(home_team, away_team)
        avg_per_team = self.strength_model.avg_goals / 2.0

        # 2. Form factors
        h_form, a_form = self.form_model.get_form_factor(home_team, away_team, avg_per_team)
        lam_h_form = avg_per_team * h_form * self.strength_model.home_advantage
        lam_a_form = avg_per_team * a_form

        # 3. Elo shift (Elo diff → expected goal differential)
        elo_diff = self.elo_model.get_diff(home_team, away_team)
        elo_goal_shift = np.tanh(elo_diff / 250.0) * 0.6  # NHL: more goals, larger shift
        lam_h_elo = max(lam_h_str + max(elo_goal_shift, -0.6), 0.3)
        lam_a_elo = max(lam_a_str - max(elo_goal_shift, -0.6), 0.3)

        # 4. Geometric blend
        weights = np.array([self.W_STRENGTH, self.W_FORM, self.W_ELO])
        weights = weights / weights.sum()
        lam_h_final = float(np.exp(
            weights[0] * np.log(lam_h_str) +
            weights[1] * np.log(lam_h_form) +
            weights[2] * np.log(lam_h_elo)
        ))
        lam_a_final = float(np.exp(
            weights[0] * np.log(lam_a_str) +
            weights[1] * np.log(lam_a_form) +
            weights[2] * np.log(lam_a_elo)
        ))

        expected_total = lam_h_final + lam_a_final

        # 5. Over/Under for NHL lines (typical: 5.5, 6.5)
        ou = {}
        for line in [0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5]:
            key = str(line).replace(".", "_")
            p_over = poisson_prob_over(expected_total, line)
            ou[f"prob_over_{key}"] = round(min(max(p_over, 0.001), 0.999), 4)
            ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)

        # 6. Period predictions
        period_preds = self.period_model.predict(expected_total)

        # 7. Agreement
        lams_h = np.array([lam_h_str, lam_h_form, lam_h_elo])
        lams_a = np.array([lam_a_str, lam_a_form, lam_a_elo])
        cv = 0.5 * (lams_h.std() / (lams_h.mean() + 0.01) + lams_a.std() / (lams_a.mean() + 0.01))
        agreement = float(np.clip(1.0 - cv, 0.0, 1.0))

        return {
            "expected_home_goals": round(lam_h_final, 3),
            "expected_away_goals": round(lam_a_final, 3),
            "expected_total_goals": round(expected_total, 3),
            "model_agreement_score": round(agreement, 3),
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

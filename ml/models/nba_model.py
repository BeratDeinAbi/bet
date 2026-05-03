"""
NBA Punkt-Vorhersagemodell.

Designentscheidungen:
- Punkte pro Team in der NBA sind ~Gaussian (μ ≈ 112, σ ≈ 13).  Eine
  Normal-Verteilung modelliert Over/Under-Linien deutlich besser als
  Poisson, die für hohe Zähler unterdispergiert ist (Var = μ).
- Team-Stärken werden mit gewichteter Normal-MLE geschätzt
  (Time-Decay + L2).
- Elo + Rolling-Form als zusätzliche Signale.
- Quarter-Modell: empirische Q1–Q4-Anteile mit Liga-Prior-Shrinkage.
- Standardabweichung für Total + Quarters wird aus historischen Daten
  mit Mindest-Floor abgeleitet.

Konvention im Code: wir behalten die Variablennamen ``goals``/``lam``,
weil das gesamte Schema (Prediction-Spalten, Top3-Markets) goal-basiert
ist.  Inhaltlich sind das aber NBA-Punkte.
"""
from __future__ import annotations

import logging
import os
import pickle
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import minimize
from scipy.stats import norm

logger = logging.getLogger(__name__)

SEED = 42
np.random.seed(SEED)

# NBA-Prior (Mittelwerte über mehrere Saisons).
NBA_PRIOR = {
    "avg_points": 226.0,          # Total per game (regular time)
    "home_adv": 1.025,            # ~2.5% home edge
    "team_std": 13.5,             # σ pro Team-Spiel
    "total_std": 19.0,            # σ Gesamtsumme
    "quarter_std": 6.5,           # σ pro Quarter-Total
    "q_ratio": [0.252, 0.252, 0.250, 0.246],  # Q1/Q2/Q3/Q4 Anteile
}

# Standard-Linien für die Wettmärkte
TOTAL_LINES = [200.5, 210.5, 215.5, 220.5, 225.5, 230.5, 235.5, 240.5]
QUARTER_LINES = [45.5, 50.5, 55.5, 60.5]


def normal_prob_over(mean: float, std: float, line: float) -> float:
    """P(X > line) für X ~ Normal(mean, std)."""
    sd = max(std, 0.5)
    return float(1.0 - norm.cdf(line, loc=mean, scale=sd))


def _parse_kickoff(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def _time_weight(kickoff: Optional[datetime], half_life_days: float = 60.0) -> float:
    """NBA-Saison ist kürzer + intensiver → kürzere Halbwertszeit."""
    if kickoff is None:
        return 0.6
    now = datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    age_days = max((now - kickoff).total_seconds() / 86400.0, 0.0)
    return float(np.exp(-np.log(2) * age_days / half_life_days))


# ---------------------------------------------------------------------------
# Team-Stärken (Normal-MLE mit L2)
# ---------------------------------------------------------------------------

class NBATeamStrengthModel:
    def __init__(self, l2_lambda: float = 0.5, half_life_days: float = 60.0):
        self.l2 = l2_lambda
        self.half_life = half_life_days
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.team_match_count: Dict[str, float] = {}
        self.avg_points = NBA_PRIOR["avg_points"]
        self.home_advantage = NBA_PRIOR["home_adv"]
        self.team_std = NBA_PRIOR["team_std"]
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NBATeamStrengthModel":
        if len(matches) < 10:
            logger.warning(f"NBA: nur {len(matches)} Spiele — nutze Priors")
            return self

        teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        weights = np.array([
            _time_weight(_parse_kickoff(m.get("kickoff_time")), self.half_life)
            for m in matches
        ])
        wsum = weights.sum() or 1.0

        all_totals = np.array([m["home_score"] + m["away_score"] for m in matches], dtype=float)
        league_avg = float((all_totals * weights).sum() / wsum)
        prior_w = max(0.0, min(1.0, 1.0 - len(matches) / 250.0))
        self.avg_points = (1 - prior_w) * league_avg + prior_w * self.avg_points

        # Empirische Streuung je Team (mit Floor)
        emp_std = float(np.sqrt(np.var(all_totals)))
        # Total-σ → Team-σ (zwei unabhängige Teams, σ_total ≈ √2 · σ_team)
        self.team_std = max(NBA_PRIOR["team_std"] * 0.7,
                            min(NBA_PRIOR["team_std"] * 1.4, emp_std / np.sqrt(2.0)))

        eff = defaultdict(float)
        for m, w in zip(matches, weights):
            eff[m["home_team"]] += w
            eff[m["away_team"]] += w
        self.team_match_count = dict(eff)

        avg_per_team = self.avg_points / 2.0

        def neg_ll(params: np.ndarray) -> float:
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2 * n])
            home_adv = np.exp(params[2 * n])
            ll = 0.0
            sigma = max(self.team_std, 1.0)
            for m, w in zip(matches, weights):
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                mu_h = attack[hi] * defense[ai] * home_adv * avg_per_team
                mu_a = attack[ai] * defense[hi] * avg_per_team
                ll += w * (
                    norm.logpdf(m["home_score"], loc=max(mu_h, 30.0), scale=sigma)
                    + norm.logpdf(m["away_score"], loc=max(mu_a, 30.0), scale=sigma)
                )
            reg = self.l2 * (np.sum(params[:n] ** 2) + np.sum(params[n:2 * n] ** 2))
            return -ll + reg

        x0 = np.zeros(2 * n + 1)
        x0[2 * n] = np.log(NBA_PRIOR["home_adv"])

        try:
            res = minimize(neg_ll, x0, method="L-BFGS-B",
                           options={"maxiter": 300, "ftol": 1e-7})
            params = res.x
            atk = np.exp(params[:n])
            dfc = np.exp(params[n:2 * n])
            self.attack = {t: float(atk[idx[t]]) for t in teams}
            self.defense = {t: float(dfc[idx[t]]) for t in teams}
            self.home_advantage = float(np.exp(params[2 * n]))
            self.fitted = True
            logger.info(f"NBA-Stärken gefittet, avg={self.avg_points:.1f}, "
                        f"home_adv={self.home_advantage:.3f}, σ_team={self.team_std:.1f}")
        except Exception as e:
            logger.warning(f"NBA strength fit failed: {e}")
            for t in teams:
                self.attack.setdefault(t, 1.0)
                self.defense.setdefault(t, 1.0)
        return self

    def _shrink(self, value: float, team: str) -> float:
        eff_n = self.team_match_count.get(team, 0.0)
        alpha = 1.0 / (1.0 + eff_n / 12.0)
        return alpha * 1.0 + (1 - alpha) * value

    def predict_means(self, home: str, away: str) -> Tuple[float, float]:
        a_h = self._shrink(self.attack.get(home, 1.0), home)
        d_h = self._shrink(self.defense.get(home, 1.0), home)
        a_a = self._shrink(self.attack.get(away, 1.0), away)
        d_a = self._shrink(self.defense.get(away, 1.0), away)
        avg_per_team = self.avg_points / 2.0
        mu_h = a_h * d_a * self.home_advantage * avg_per_team
        mu_a = a_a * d_h * avg_per_team
        return max(mu_h, 50.0), max(mu_a, 50.0)


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------

class NBAEloModel:
    BASE = 1500.0

    def __init__(self, k_base: float = 20.0):
        self.k_base = k_base
        self.ratings: Dict[str, float] = {}

    @staticmethod
    def _expected(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def fit(self, matches: List[Dict]) -> "NBAEloModel":
        sorted_matches = sorted(
            matches,
            key=lambda m: _parse_kickoff(m.get("kickoff_time"))
            or datetime.min.replace(tzinfo=timezone.utc),
        )
        for m in sorted_matches:
            h, a = m["home_team"], m["away_team"]
            self.ratings.setdefault(h, self.BASE)
            self.ratings.setdefault(a, self.BASE)
            rh, ra = self.ratings[h], self.ratings[a]
            eh = self._expected(rh, ra)

            margin = abs(m["home_score"] - m["away_score"])
            mov_mult = float(np.log(max(margin, 1) + 1))
            k = self.k_base * mov_mult

            sh = 1.0 if m["home_score"] > m["away_score"] else (
                0.0 if m["home_score"] < m["away_score"] else 0.5)
            self.ratings[h] = rh + k * (sh - eh)
            self.ratings[a] = ra + k * ((1 - sh) - (1 - eh))
        return self

    def get_diff(self, home: str, away: str) -> float:
        return self.ratings.get(home, self.BASE) - self.ratings.get(away, self.BASE)


# ---------------------------------------------------------------------------
# Rolling Form (letzte 12 Spiele)
# ---------------------------------------------------------------------------

class NBARollingForm:
    def __init__(self, window: int = 12, decay: float = 0.92):
        self.window = window
        self.decay = decay
        self.pf: Dict[str, float] = {}  # points for
        self.pa: Dict[str, float] = {}  # points against

    def fit(self, matches: List[Dict]) -> "NBARollingForm":
        sorted_matches = sorted(
            matches,
            key=lambda m: _parse_kickoff(m.get("kickoff_time"))
            or datetime.min.replace(tzinfo=timezone.utc),
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
            self.pf[team] = float(sum(h[0] * w for h, w in zip(recent, weights)) / wsum)
            self.pa[team] = float(sum(h[1] * w for h, w in zip(recent, weights)) / wsum)
        return self

    def get_form_means(self, home: str, away: str, league_team_avg: float) -> Tuple[float, float]:
        h_pf = self.pf.get(home, league_team_avg)
        h_pa = self.pa.get(home, league_team_avg)
        a_pf = self.pf.get(away, league_team_avg)
        a_pa = self.pa.get(away, league_team_avg)
        # geometrisches Mittel der Erwartungen → robuster gegen Ausreißer
        mu_h = float(np.sqrt(max(h_pf * a_pa, 1.0)))
        mu_a = float(np.sqrt(max(a_pf * h_pa, 1.0)))
        return mu_h, mu_a


# ---------------------------------------------------------------------------
# Quarter-Modell
# ---------------------------------------------------------------------------

class NBAQuarterModel:
    def __init__(self):
        self.ratios = {f"Q{i + 1}": NBA_PRIOR["q_ratio"][i] for i in range(4)}
        self.quarter_std = NBA_PRIOR["quarter_std"]
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "NBAQuarterModel":
        q_totals: Dict[str, List[float]] = {f"Q{i + 1}": [] for i in range(4)}
        per_match_totals: List[float] = []
        for m in matches:
            segments = m.get("segments", []) or []
            pq: Dict[str, float] = {}
            for seg in segments:
                code = seg.get("segment_code", "")
                if code in q_totals:
                    pq[code] = float(seg.get("total_goals", 0))
            if len(pq) == 4:
                total = sum(pq.values())
                if total <= 0:
                    continue
                per_match_totals.append(total)
                for q in q_totals:
                    q_totals[q].append(pq[q])
        if per_match_totals:
            n = len(per_match_totals)
            blend = min(1.0, n / 80.0)
            total_sum = sum(per_match_totals) or 1.0
            for q in q_totals:
                empirical = sum(q_totals[q]) / total_sum
                self.ratios[q] = blend * empirical + (1 - blend) * self.ratios[q]
            # Empirische Streuung pro Quarter
            all_q = [v for vals in q_totals.values() for v in vals]
            if len(all_q) > 5:
                emp = float(np.std(all_q))
                self.quarter_std = max(NBA_PRIOR["quarter_std"] * 0.7,
                                       min(NBA_PRIOR["quarter_std"] * 1.4, emp))
            self.fitted = True
        return self

    def predict(self, expected_total: float) -> Dict[str, float]:
        result: Dict[str, float] = {}
        for code, ratio in self.ratios.items():
            mu = expected_total * ratio
            qkey = code.lower()  # q1, q2, q3, q4
            result[f"expected_points_{qkey}"] = round(mu, 2)
            for line in QUARTER_LINES:
                lkey = str(line).replace(".", "_")
                p_over = normal_prob_over(mu, self.quarter_std, line)
                result[f"prob_over_{lkey}_{qkey}"] = round(min(max(p_over, 0.001), 0.999), 4)
                result[f"prob_under_{lkey}_{qkey}"] = round(1.0 - result[f"prob_over_{lkey}_{qkey}"], 4)
        return result


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

class NBAEnsemble:
    W_STRENGTH = 0.50
    W_FORM = 0.30
    W_ELO = 0.20

    def __init__(self):
        self.strength_model = NBATeamStrengthModel()
        self.elo_model = NBAEloModel(k_base=20.0)
        self.form_model = NBARollingForm(window=12, decay=0.92)
        self.quarter_model = NBAQuarterModel()
        self.fitted = False
        self.n_train = 0

    def fit(self, matches: List[Dict]) -> "NBAEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        self.n_train = len(finished)
        if not finished:
            logger.warning("NBA: no finished matches")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.form_model.fit(finished)
        self.quarter_model.fit(finished)
        self.fitted = True
        logger.info(f"NBAEnsemble fitted on {len(finished)} matches "
                    f"(Normal-MLE, time-decayed, rolling form)")
        return self

    def predict(self, home_team: str, away_team: str) -> Dict:
        # 1. Strength baseline
        mu_h_str, mu_a_str = self.strength_model.predict_means(home_team, away_team)
        avg_per_team = self.strength_model.avg_points / 2.0

        # 2. Form
        mu_h_form, mu_a_form = self.form_model.get_form_means(home_team, away_team, avg_per_team)
        # leichter Home-Boost für Form-Komponente
        mu_h_form *= self.strength_model.home_advantage

        # 3. Elo-Shift in Punkte: 100 Elo ≈ ~3 Punkte Differenz
        elo_diff = self.elo_model.get_diff(home_team, away_team)
        elo_pt_shift = float(np.tanh(elo_diff / 250.0)) * 4.0
        mu_h_elo = max(mu_h_str + elo_pt_shift, 50.0)
        mu_a_elo = max(mu_a_str - elo_pt_shift, 50.0)

        # 4. Geometrischer Blend (gleiche Form wie NHL-Ensemble)
        weights = np.array([self.W_STRENGTH, self.W_FORM, self.W_ELO])
        weights = weights / weights.sum()
        mu_h_final = float(np.exp(
            weights[0] * np.log(mu_h_str) +
            weights[1] * np.log(max(mu_h_form, 50.0)) +
            weights[2] * np.log(mu_h_elo)
        ))
        mu_a_final = float(np.exp(
            weights[0] * np.log(mu_a_str) +
            weights[1] * np.log(max(mu_a_form, 50.0)) +
            weights[2] * np.log(mu_a_elo)
        ))

        expected_total = mu_h_final + mu_a_final
        # σ_total = √2 · σ_team (unabhängige Teams).  Plus kleiner Faktor
        # für Restkorrelation (Tempo-Effekt: schnelles Spiel → beide
        # Teams scoren mehr).
        total_std = float(np.sqrt(2.0) * self.strength_model.team_std * 1.05)

        # 5. Total-Markets
        ou: Dict[str, float] = {}
        for line in TOTAL_LINES:
            key = str(line).replace(".", "_")
            p_over = normal_prob_over(expected_total, total_std, line)
            ou[f"prob_over_{key}"] = round(min(max(p_over, 0.001), 0.999), 4)
            ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)

        # 6. Quarter-Predictions
        quarter_preds = self.quarter_model.predict(expected_total)

        # 7. Modell-Agreement
        mus_h = np.array([mu_h_str, mu_h_form, mu_h_elo])
        mus_a = np.array([mu_a_str, mu_a_form, mu_a_elo])
        cv = 0.5 * (mus_h.std() / (mus_h.mean() + 1.0) +
                    mus_a.std() / (mus_a.mean() + 1.0))
        agreement = float(np.clip(1.0 - cv * 8.0, 0.0, 1.0))

        return {
            "expected_home_points": round(mu_h_final, 2),
            "expected_away_points": round(mu_a_final, 2),
            "expected_total_points": round(expected_total, 2),
            "expected_total_std": round(total_std, 2),
            "model_agreement_score": round(agreement, 3),
            "total_lines_used": TOTAL_LINES,
            "quarter_lines_used": QUARTER_LINES,
            **ou,
            **quarter_preds,
        }

    # Persistence
    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str) -> "NBAEnsemble":
        with open(path, "rb") as f:
            return pickle.load(f)

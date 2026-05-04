"""
MLB Runs-Vorhersagemodell.

Statistische Annahme:
  Runs pro Team pro Spiel sind sehr gut Poisson-verteilt
  (Mittel ≈ 4.5, Varianz ≈ 4.5).  Anders als Basketball-Punkte (zu hoch
  → Normal) oder Football-Tore (passen Poisson aber niedrig) liegt
  Baseball genau in der „Sweet-Spot"-Region für Poisson-MLE.

Stack (parallel zu NHL/NBA):
  - PoissonTeamStrength mit Time-Decay (45-Tage-HL, MLB-Saison ist
    dicht), L2-Reg, Liga-Prior-Shrinkage.
  - Elo (k_base=14, MOV-Multiplier).
  - Rolling-Form über die letzten 12 Spiele.
  - F5-Modell (erste 5 Innings) — beliebter Wettmarkt; verwendet
    empirische F5/Total-Ratio, geshrinkt zur 0.55-Prior.

Speziell für Baseball:
  - Pitcher-ERA wird (falls aus dem Schedule mitgegeben) als
    optionaler Skalar in `predict()` verarbeitet.  Dafür liefert das
    Modell `predict_with_pitchers()` mit ERA-Adjustment, das den ERA-
    Quotienten zur Liga-ERA (4.20) als Multiplikator nutzt — das ist
    bewusst dezent (clamp 0.85–1.15), damit ausreißende ERAs (sehr
    junger Pitcher, kleine Sample-Größe) nicht das Modell sprengen.
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
from scipy.stats import poisson

logger = logging.getLogger(__name__)
SEED = 42
np.random.seed(SEED)


MLB_PRIOR = {
    "avg_runs": 9.0,        # Total runs pro Spiel über die Liga (regulär 9 Innings)
    "home_adv": 1.04,       # ~4 % Home Edge in MLB
    "f5_ratio": 0.55,       # ca. 55 % der Runs fallen in den ersten 5 Innings
    "league_era": 4.20,     # Liga-ERA-Mittel (3-Jahres-Schnitt)
}

TOTAL_LINES = [6.5, 7.5, 8.0, 8.5, 9.0, 9.5, 10.5, 11.5]
F5_LINES = [3.5, 4.5, 5.5]


# Park-Run-Faktoren — Multiplier auf erwartete Total Runs, basiert auf
# 3-Jahres-Average der Statcast-Park-Factors (2022–2024).
# Werte > 1 = mehr Runs, < 1 = weniger.  Quelle: ESPN/Baseball-Reference,
# auf Mittelwert 1.00 normalisiert.
PARK_FACTORS: Dict[str, float] = {
    # Hitter-Friendly
    "Colorado Rockies":      1.18,   # Coors Field — Höhe
    "Cincinnati Reds":       1.07,   # GABP — kurzes RF
    "Boston Red Sox":        1.06,   # Fenway — Green Monster
    "Texas Rangers":         1.04,   # Globe Life Field
    "Philadelphia Phillies": 1.04,   # Citizens Bank
    "Baltimore Orioles":     1.03,   # Camden Yards
    "Toronto Blue Jays":     1.03,   # Rogers Centre
    "Atlanta Braves":        1.02,   # Truist Park
    "Chicago White Sox":     1.02,
    "New York Yankees":      1.02,   # Short porch RF
    "Arizona Diamondbacks":  1.01,
    "Houston Astros":        1.01,
    "Kansas City Royals":    1.00,
    "Minnesota Twins":       1.00,
    "Washington Nationals":  1.00,
    "Los Angeles Angels":    0.99,
    "St. Louis Cardinals":   0.99,
    "Milwaukee Brewers":     0.99,
    "Tampa Bay Rays":        0.98,   # Tropicana — Dome
    "Chicago Cubs":          0.98,   # Wrigley — wind dependent (default ohne Wetter)
    "Cleveland Guardians":   0.98,
    # Pitcher-Friendly
    "New York Mets":         0.97,
    "Athletics":             0.96,
    "Oakland Athletics":     0.96,
    "Los Angeles Dodgers":   0.96,
    "Detroit Tigers":        0.95,
    "Seattle Mariners":      0.94,   # T-Mobile Park
    "Pittsburgh Pirates":    0.94,
    "Miami Marlins":         0.93,   # loanDepot Park
    "San Francisco Giants":  0.92,   # Oracle Park
    "San Diego Padres":      0.92,   # Petco
}


def _park_factor(home_team: str) -> float:
    """Liefert den Park-Factor des Heimstadiums.  Default 1.00 wenn Team unbekannt."""
    return PARK_FACTORS.get(home_team, 1.00)


# Empirische Run-Verteilung pro Inning (über alle MLB-Spiele 2020-2024).
# Quelle: Baseball-Reference Inning-Splits.  Inning 1 ist "Lineup-Top"
# (Bestesschläger gegen Starter) → leicht überdurchschnittlich.
# Innings 7-9 schlagen Bullpen → moderat höher.  9. Inning ist nur
# Auswärts (Heim braucht es nicht wenn führend).
INNING_RATIO = [
    0.121,  # Inning 1 — Top-of-Order vs. Starter, leicht überdurchschnittlich
    0.108,  # Inning 2 — Bottom-of-Order
    0.110,  # Inning 3 — Lineup-Top zurück
    0.108,  # Inning 4
    0.104,  # Inning 5 — letzte volle Starter-Inning typisch
    0.108,  # Inning 6 — Bullpen kann starten, mehr Walks
    0.115,  # Inning 7 — Setup-Reliever
    0.118,  # Inning 8 — Setup
    0.108,  # Inning 9 — Closer (top), nur Auswärts in vielen Spielen
]
# Summe ~1.0 (kleine Rundungsabweichungen → wir normalisieren in der
# Klasse).


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


def _time_weight(kickoff: Optional[datetime], half_life_days: float = 45.0) -> float:
    if kickoff is None:
        return 0.6
    now = datetime.now(timezone.utc)
    if kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=timezone.utc)
    age_days = max((now - kickoff).total_seconds() / 86400.0, 0.0)
    return float(np.exp(-np.log(2) * age_days / half_life_days))


# ---------------------------------------------------------------------------
# Team-Stärken: Poisson-MLE
# ---------------------------------------------------------------------------

class MLBTeamStrengthModel:
    def __init__(self, l2_lambda: float = 0.4, half_life_days: float = 45.0):
        self.l2 = l2_lambda
        self.half_life = half_life_days
        self.attack: Dict[str, float] = {}
        self.defense: Dict[str, float] = {}
        self.team_match_count: Dict[str, float] = {}
        self.avg_runs = MLB_PRIOR["avg_runs"]
        self.home_advantage = MLB_PRIOR["home_adv"]
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "MLBTeamStrengthModel":
        if len(matches) < 10:
            logger.warning(f"MLB: nur {len(matches)} Spiele — nutze Priors")
            return self

        teams = sorted({m["home_team"] for m in matches} | {m["away_team"] for m in matches})
        n = len(teams)
        idx = {t: i for i, t in enumerate(teams)}

        weights = np.array([
            _time_weight(_parse_kickoff(m.get("kickoff_time")), self.half_life)
            for m in matches
        ])
        wsum = weights.sum() or 1.0

        all_totals = np.array(
            [m["home_score"] + m["away_score"] for m in matches], dtype=float
        )
        league_avg = float((all_totals * weights).sum() / wsum)
        prior_w = max(0.0, min(1.0, 1.0 - len(matches) / 200.0))
        self.avg_runs = (1 - prior_w) * league_avg + prior_w * self.avg_runs

        eff = defaultdict(float)
        for m, w in zip(matches, weights):
            eff[m["home_team"]] += w
            eff[m["away_team"]] += w
        self.team_match_count = dict(eff)

        avg_per_team = self.avg_runs / 2.0

        def neg_ll(params: np.ndarray) -> float:
            attack = np.exp(params[:n])
            defense = np.exp(params[n:2 * n])
            home_adv = np.exp(params[2 * n])
            ll = 0.0
            for m, w in zip(matches, weights):
                hi, ai = idx[m["home_team"]], idx[m["away_team"]]
                lam_h = attack[hi] * defense[ai] * home_adv * avg_per_team
                lam_a = attack[ai] * defense[hi] * avg_per_team
                ll += w * (
                    poisson.logpmf(m["home_score"], max(lam_h, 0.05))
                    + poisson.logpmf(m["away_score"], max(lam_a, 0.05))
                )
            reg = self.l2 * (np.sum(params[:n] ** 2) + np.sum(params[n:2 * n] ** 2))
            return -ll + reg

        x0 = np.zeros(2 * n + 1)
        x0[2 * n] = np.log(MLB_PRIOR["home_adv"])
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
            logger.info(f"MLB strengths fitted: avg={self.avg_runs:.2f}, "
                        f"home_adv={self.home_advantage:.3f}, teams={n}")
        except Exception as e:
            logger.warning(f"MLB strength fit failed: {e}")
            for t in teams:
                self.attack.setdefault(t, 1.0)
                self.defense.setdefault(t, 1.0)
        return self

    def _shrink(self, value: float, team: str) -> float:
        eff_n = self.team_match_count.get(team, 0.0)
        alpha = 1.0 / (1.0 + eff_n / 10.0)
        return alpha * 1.0 + (1 - alpha) * value

    def predict_lambdas(self, home: str, away: str) -> Tuple[float, float]:
        a_h = self._shrink(self.attack.get(home, 1.0), home)
        d_h = self._shrink(self.defense.get(home, 1.0), home)
        a_a = self._shrink(self.attack.get(away, 1.0), away)
        d_a = self._shrink(self.defense.get(away, 1.0), away)
        avg_per_team = self.avg_runs / 2.0
        lam_h = a_h * d_a * self.home_advantage * avg_per_team
        lam_a = a_a * d_h * avg_per_team
        return max(lam_h, 0.5), max(lam_a, 0.5)


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------

class MLBEloModel:
    BASE = 1500.0

    def __init__(self, k_base: float = 14.0):
        self.k_base = k_base
        self.ratings: Dict[str, float] = {}

    @staticmethod
    def _expected(rating_a: float, rating_b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((rating_b - rating_a) / 400.0))

    def fit(self, matches: List[Dict]) -> "MLBEloModel":
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
            sh = (1.0 if m["home_score"] > m["away_score"]
                  else 0.0 if m["home_score"] < m["away_score"] else 0.5)
            self.ratings[h] = rh + k * (sh - eh)
            self.ratings[a] = ra + k * ((1 - sh) - (1 - eh))
        return self

    def get_diff(self, home: str, away: str) -> float:
        return self.ratings.get(home, self.BASE) - self.ratings.get(away, self.BASE)


# ---------------------------------------------------------------------------
# Rolling Form
# ---------------------------------------------------------------------------

class MLBRollingForm:
    def __init__(self, window: int = 12, decay: float = 0.92):
        self.window = window
        self.decay = decay
        self.rs: Dict[str, float] = {}
        self.ra: Dict[str, float] = {}

    def fit(self, matches: List[Dict]) -> "MLBRollingForm":
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
            self.rs[team] = float(sum(h[0] * w for h, w in zip(recent, weights)) / wsum)
            self.ra[team] = float(sum(h[1] * w for h, w in zip(recent, weights)) / wsum)
        return self

    def get_form_lambdas(
        self, home: str, away: str, league_team_avg: float,
    ) -> Tuple[float, float]:
        h_rs = self.rs.get(home, league_team_avg)
        h_ra = self.ra.get(home, league_team_avg)
        a_rs = self.rs.get(away, league_team_avg)
        a_ra = self.ra.get(away, league_team_avg)
        # geometrisches Mittel — robuster gegen Ausreißer
        lam_h = float(np.sqrt(max(h_rs * a_ra, 0.25)))
        lam_a = float(np.sqrt(max(a_rs * h_ra, 0.25)))
        return lam_h, lam_a


# ---------------------------------------------------------------------------
# F5 (erste 5 Innings)
# ---------------------------------------------------------------------------

class MLBInningModel:
    """Verteilt erwartete Total-Runs auf die 9 Innings.

    Trainings-Logik: wenn historische Inning-Daten vorhanden sind (über
    Match-Segmente "INN1"…"INN9"), wird das empirische Verhältnis pro
    Inning gemischt mit dem MLB-Liga-Prior (Baseball-Reference 2020-24).
    Falls keine Inning-Segmente vorliegen (heute hat unser Provider nur
    F5/L4) → Modell bleibt im Prior-Mode, was statistisch besser ist als
    eine flache 1/9-Verteilung weil Inning 1, 7, 8 nachweislich höhere
    Scoring-Raten haben.

    Output pro Inning:
      - expected_runs_inn_X: λ für dieses Inning (Poisson-Mittel)
      - prob_over_0_5_inn_X: Wahrscheinlichkeit ≥ 1 Run
      - prob_over_1_5_inn_X: Wahrscheinlichkeit ≥ 2 Runs
    """

    def __init__(self):
        ratios = np.array(INNING_RATIO, dtype=float)
        self.ratios = (ratios / ratios.sum()).tolist()
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "MLBInningModel":
        sums = np.zeros(9)
        n_full = 0
        for m in matches:
            segments = m.get("segments") or []
            inn_runs = {}
            for seg in segments:
                code = seg.get("segment_code", "") or ""
                if not code.startswith("INN"):
                    continue
                try:
                    idx = int(code[3:]) - 1
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < 9:
                    inn_runs[idx] = (inn_runs.get(idx, 0)
                                     + (seg.get("total_goals") or 0))
            if len(inn_runs) >= 9:
                total = sum(inn_runs.values()) or 1
                for i in range(9):
                    sums[i] += inn_runs.get(i, 0) / total
                n_full += 1
        if n_full >= 30:
            empirical = sums / n_full
            empirical = empirical / empirical.sum()
            blend = min(1.0, n_full / 200.0)
            mixed = blend * empirical + (1 - blend) * np.array(self.ratios)
            self.ratios = (mixed / mixed.sum()).tolist()
            self.fitted = True
        return self

    def predict(self, expected_total: float) -> Dict:
        out: Dict = {}
        for i, ratio in enumerate(self.ratios, start=1):
            lam = max(expected_total * ratio, 0.001)
            out[f"expected_runs_inn_{i}"] = round(lam, 3)
            out[f"prob_over_0_5_inn_{i}"] = round(
                min(max(poisson_prob_over(lam, 0.5), 0.001), 0.999), 4
            )
            out[f"prob_over_1_5_inn_{i}"] = round(
                min(max(poisson_prob_over(lam, 1.5), 0.001), 0.999), 4
            )
        # Prozentanteil pro Inning für UI-Visualisierung
        out["inning_distribution_pct"] = [round(r * 100, 1) for r in self.ratios]
        return out


class MLBF5Model:
    def __init__(self):
        self.f5_ratio = MLB_PRIOR["f5_ratio"]
        self.fitted = False

    def fit(self, matches: List[Dict]) -> "MLBF5Model":
        ratios = []
        for m in matches:
            segments = m.get("segments") or []
            f5 = next((s for s in segments if s.get("segment_code") == "F5"), None)
            if not f5:
                continue
            total = (m.get("home_score") or 0) + (m.get("away_score") or 0)
            if total <= 0:
                continue
            r = max(0.1, min(0.9, (f5.get("total_goals") or 0) / total))
            ratios.append(r)
        if ratios:
            n = len(ratios)
            blend = min(1.0, n / 80.0)
            empirical = float(np.mean(ratios))
            self.f5_ratio = blend * empirical + (1 - blend) * self.f5_ratio
            self.fitted = True
        return self

    def predict(self, expected_total: float) -> Dict[str, float]:
        lam_f5 = expected_total * self.f5_ratio
        out: Dict[str, float] = {"expected_runs_f5": round(lam_f5, 3)}
        for line in F5_LINES:
            key = str(line).replace(".", "_")
            p = poisson_prob_over(lam_f5, line)
            out[f"prob_over_{key}_f5"] = round(min(max(p, 0.001), 0.999), 4)
            out[f"prob_under_{key}_f5"] = round(1.0 - out[f"prob_over_{key}_f5"], 4)
        return out


# ---------------------------------------------------------------------------
# Ensemble
# ---------------------------------------------------------------------------

class MLBEnsemble:
    W_STRENGTH = 0.55
    W_FORM = 0.30
    W_ELO = 0.15

    def __init__(self):
        self.strength_model = MLBTeamStrengthModel()
        self.elo_model = MLBEloModel(k_base=14.0)
        self.form_model = MLBRollingForm(window=12, decay=0.92)
        self.f5_model = MLBF5Model()
        self.inning_model = MLBInningModel()
        self.fitted = False
        self.n_train = 0

    def fit(self, matches: List[Dict]) -> "MLBEnsemble":
        finished = [m for m in matches if m.get("home_score") is not None]
        self.n_train = len(finished)
        if not finished:
            logger.warning("MLB: keine finished matches")
            return self
        self.strength_model.fit(finished)
        self.elo_model.fit(finished)
        self.form_model.fit(finished)
        self.f5_model.fit(finished)
        self.inning_model.fit(finished)
        self.fitted = True
        logger.info(f"MLBEnsemble fitted on {len(finished)} games "
                    f"(Poisson-MLE, time-decayed, F5+inning-distribution)")
        return self

    def _pitcher_factor(self, era: Optional[float], xfip: Optional[float] = None) -> float:
        """Pitcher-Mult auf erwartete gegnerische Runs.

        Bevorzugt xFIP wenn verfügbar (deutlich besserer Prediktor als ERA),
        sonst ERA.  Clamp 0.75–1.25 — eng genug, um Outlier-ERA-Werte
        kleiner Sample-Größen zu dämpfen, weit genug für echte Cy-Young-vs-
        Replacement-Level-Spreads.  (Vorher 0.85–1.15 war zu konservativ.)
        """
        metric = xfip if (xfip is not None and xfip > 0) else era
        if metric is None or metric <= 0:
            return 1.0
        f = metric / MLB_PRIOR["league_era"]
        return float(np.clip(f, 0.75, 1.25))

    def predict(
        self,
        home_team: str,
        away_team: str,
        home_pitcher_era: Optional[float] = None,
        away_pitcher_era: Optional[float] = None,
        home_pitcher_xfip: Optional[float] = None,
        away_pitcher_xfip: Optional[float] = None,
    ) -> Dict:
        lam_h_str, lam_a_str = self.strength_model.predict_lambdas(home_team, away_team)
        avg_per_team = self.strength_model.avg_runs / 2.0

        lam_h_form, lam_a_form = self.form_model.get_form_lambdas(
            home_team, away_team, avg_per_team,
        )
        lam_h_form *= self.strength_model.home_advantage

        elo_diff = self.elo_model.get_diff(home_team, away_team)
        # Elo-Shift in Runs: 100 Elo ≈ ~0.4 Runs Differenz
        elo_run_shift = float(np.tanh(elo_diff / 250.0)) * 0.7
        lam_h_elo = max(lam_h_str + elo_run_shift, 0.5)
        lam_a_elo = max(lam_a_str - elo_run_shift, 0.5)

        weights = np.array([self.W_STRENGTH, self.W_FORM, self.W_ELO])
        weights = weights / weights.sum()
        lam_h_final = float(np.exp(
            weights[0] * np.log(lam_h_str)
            + weights[1] * np.log(max(lam_h_form, 0.5))
            + weights[2] * np.log(lam_h_elo)
        ))
        lam_a_final = float(np.exp(
            weights[0] * np.log(lam_a_str)
            + weights[1] * np.log(max(lam_a_form, 0.5))
            + weights[2] * np.log(lam_a_elo)
        ))

        # Pitcher-Adjustment (gegnerischer ERA/xFIP wirkt auf Heim/Auswärts-Runs)
        # Wenn Auswärtspitcher schwach ist → Heim-Team scort mehr.
        h_factor = self._pitcher_factor(away_pitcher_era, away_pitcher_xfip)
        a_factor = self._pitcher_factor(home_pitcher_era, home_pitcher_xfip)
        lam_h_final *= h_factor
        lam_a_final *= a_factor

        # Park-Adjustment — wirkt auf BEIDE Teams (Park modifiziert Total Runs).
        park = _park_factor(home_team)
        lam_h_final *= park
        lam_a_final *= park

        expected_total = lam_h_final + lam_a_final

        ou: Dict[str, float] = {}
        for line in TOTAL_LINES:
            key = str(line).replace(".", "_")
            p = poisson_prob_over(expected_total, line)
            ou[f"prob_over_{key}"] = round(min(max(p, 0.001), 0.999), 4)
            ou[f"prob_under_{key}"] = round(1.0 - ou[f"prob_over_{key}"], 4)

        f5 = self.f5_model.predict(expected_total)
        innings = self.inning_model.predict(expected_total)

        # Modell-Agreement
        lams_h = np.array([lam_h_str, lam_h_form, lam_h_elo])
        lams_a = np.array([lam_a_str, lam_a_form, lam_a_elo])
        cv = 0.5 * (lams_h.std() / (lams_h.mean() + 0.05)
                    + lams_a.std() / (lams_a.mean() + 0.05))
        agreement = float(np.clip(1.0 - cv, 0.0, 1.0))

        return {
            "expected_home_runs": round(lam_h_final, 3),
            "expected_away_runs": round(lam_a_final, 3),
            "expected_total_runs": round(expected_total, 3),
            "model_agreement_score": round(agreement, 3),
            "pitcher_factor_home": round(h_factor, 3),
            "pitcher_factor_away": round(a_factor, 3),
            "park_factor": round(park, 3),
            "total_lines_used": TOTAL_LINES,
            "f5_lines_used": F5_LINES,
            **ou,
            **f5,
            **innings,
        }

    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, path: str) -> "MLBEnsemble":
        with open(path, "rb") as f:
            return pickle.load(f)

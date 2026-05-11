"""
Recommended-Picks-Pipeline.

Konzept:
  Pro neu erzeugter Prediction erzeugt ``persist_recommended_pick``
  einen einzelnen Wett-Vorschlag (höchster Ranking-Score, faire Quote
  ≥ 1.25).  Diese Vorschläge sind die Wett-Empfehlungen des Modells
  und werden in der Datenbank persistiert, sobald sie generiert sind.

  Sobald das Match auf FINISHED steht, fährt
  ``evaluate_recommended_picks`` über alle nicht-bewerteten Picks und
  setzt ``actual_hit`` und ``actual_total``.

  Das Frontend zeigt diese Picks pro Sport — bewertet (Hit/Miss) und
  noch offen (zukünftige Spiele).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Match, OddsLine, Prediction, RecommendedPick,
)
from app.services.ranking import _best_pick_per_match, _candidates_for

logger = logging.getLogger(__name__)


def _market_to_canonical(market: str) -> str:
    """Mapping Markt-Label aus ranking.py → Bookmaker-Markt-Label.

    Aktuell speichert die Odds-Ingestion alle ``totals``-Märkte als
    ``"Total"``.  Ranking nennt Football-Totals ``"Total"``, NBA
    ``"Total Punkte"``, MLB ``"Total Runs"`` — alle drei mappen wir
    für den Lookup auf das gleiche generische ``"Total"``.
    """
    m = (market or "").lower()
    if m in ("total", "total punkte", "total runs"):
        return "Total"
    return market  # Segment-Märkte (H1/H2, F5, Q1-Q4 …) bleiben wie sind


def _find_bookmaker_odds(
    db: Session,
    match_id: int,
    market: str,
    line: float,
    direction: str,
) -> Optional[OddsLine]:
    """Lookup einer OddsLine vom konfigurierten Bookmaker."""
    return (
        db.query(OddsLine)
        .filter(
            OddsLine.match_id == match_id,
            OddsLine.market == _market_to_canonical(market),
            OddsLine.line == line,
            OddsLine.direction == direction,
            OddsLine.provider == settings.ODDS_BOOKMAKER,
        )
        .order_by(OddsLine.fetched_at.desc())
        .first()
    )


def _ev_pick_for_match(
    db: Session, match: Match, pred: Prediction,
) -> Optional[dict]:
    """Wählt unter allen Markt-Kandidaten den mit höchstem EV.

    Filter:
      - Modell-Wahrscheinlichkeit aus ``_candidates_for`` (≥ 60 %, ≤ 80 %)
      - Bookmaker-Quote vom konfigurierten Anbieter vorhanden
      - Bookmaker-Quote ≥ ``ODDS_MIN_BOOKMAKER_ODDS`` (default 1.25)

    Aus den verbleibenden Kandidaten gewinnt der mit höchstem
    ``EV = model_probability × bookmaker_odds``.  Liefert Dict mit
    allen Feldern für das RecommendedPick-Insert oder None.
    """
    # cap_max_prob=False, weil bei echten Bookmaker-Quoten die
    # Quote selbst entscheidet, nicht das synthetische faire-Quote-Cap.
    cands = _candidates_for(pred, match, cap_max_prob=False)
    if not cands:
        return None

    best = None
    best_ev = -1.0
    for c in cands:
        odds = _find_bookmaker_odds(
            db, match.id, c["market"], c["line"], c["direction"],
        )
        if odds is None or not odds.bookmaker_odds:
            continue
        if odds.bookmaker_odds < settings.ODDS_MIN_BOOKMAKER_ODDS:
            continue
        ev = c["prob"] * odds.bookmaker_odds
        if ev > best_ev:
            best_ev = ev
            implied = odds.implied_probability or (1.0 / odds.bookmaker_odds)
            best = {
                "market": c["market"],
                "line": c["line"],
                "direction": c["direction"],
                "model_probability": c["prob"],
                "fair_odds": round(1.0 / max(c["prob"], 0.001), 3),
                "bookmaker_name": odds.provider,
                "bookmaker_odds": odds.bookmaker_odds,
                "edge": round(c["prob"] - implied, 4),
                "ranking_score": round(ev, 4),  # EV als ranking-score
            }
    return best


def persist_recommended_pick(db: Session, match: Match,
                             pred: Prediction) -> Optional[RecommendedPick]:
    """Erzeugt + speichert genau einen Pick pro Match (oder None wenn
    keine Linie die Wettwert-Schwelle erreicht).

    Pick-Strategie:
      1. **Bookmaker-EV-Pick** (Standard, wenn ``ODDS_API_KEY`` gesetzt):
         der Markt mit höchstem ``model_prob × bookmaker_odds``, gefiltert
         auf bookmaker_odds ≥ ``ODDS_MIN_BOOKMAKER_ODDS``.
      2. Fallback: alter Faire-Quote-Pick aus ``_best_pick_per_match``,
         falls keine Bookmaker-Quote für irgendeinen Kandidaten existiert.

    Idempotent: wenn schon ein Pick für diese Prediction existiert,
    wird einfach der bestehende zurückgegeben.
    """
    existing = (
        db.query(RecommendedPick)
        .filter(RecommendedPick.prediction_id == pred.id)
        .first()
    )
    if existing:
        return existing

    # Pfad 1: EV-Pick mit echter Bookmaker-Quote
    ev = _ev_pick_for_match(db, match, pred)
    if ev is not None:
        rp = RecommendedPick(
            prediction_id=pred.id,
            match_id=match.id,
            sport=match.sport,
            league=match.competition.code if match.competition else None,
            market=ev["market"],
            line=ev["line"],
            direction=ev["direction"],
            model_probability=ev["model_probability"],
            fair_odds=ev["fair_odds"],
            ranking_score=ev["ranking_score"],
            confidence_label=pred.confidence_label,
            bookmaker_name=ev["bookmaker_name"],
            bookmaker_odds=ev["bookmaker_odds"],
            edge=ev["edge"],
        )
        db.add(rp)
        db.flush()
        return rp

    # Pfad 2: Fallback — kein Bookmaker-Lookup möglich (kein API-Key
    # gesetzt, oder Spiel nicht in Odds-API).  Nur dann nehmen wir den
    # alten Faire-Quote-Pick — sonst kein Pick (User-Vorgabe: "nur
    # Betano-Quote ≥ 1.25").
    if settings.ODDS_API_KEY:
        # Key ist da → Bookmaker hat aber keine passende Quote: kein Pick.
        return None

    pick = _best_pick_per_match(db, match, pred)
    if pick is None:
        return None
    rp = RecommendedPick(
        prediction_id=pred.id,
        match_id=match.id,
        sport=match.sport,
        league=match.competition.code if match.competition else None,
        market=pick.market,
        line=pick.market_line,
        direction=pick.market_direction,
        model_probability=pick.model_probability,
        fair_odds=pick.fair_odds,
        ranking_score=pick.ranking_score,
        confidence_label=pick.confidence_label,
    )
    db.add(rp)
    db.flush()
    return rp


def _is_hit(rp: RecommendedPick, total: float) -> bool:
    """Prüft, ob der Pick gewonnen hat — abhängig davon ob es Total,
    F5, Quarter, etc. ist.

    Vereinfachung: ``total`` ist immer der **Spiel-Total** (alle
    Tore/Punkte/Runs).  Für Segment-Märkte (F5, H1, Q1 …) liefert
    diese Funktion eine Approximation, die nicht 100% korrekt ist —
    deshalb evaluieren wir momentan nur Full-Game-Märkte.  Picks auf
    Segment-Märkte lassen wir mit ``actual_hit=None`` stehen.
    """
    if rp.direction == "over":
        return total > rp.line
    return total < rp.line


def _is_full_game_market(market: Optional[str]) -> bool:
    """Wir bewerten nur Full-Game-Märkte: Total, Total Punkte, Total Runs.
    Segmente (H1/H2, F5, Q1-Q4, P1-P3) brauchen Segment-Daten und werden
    erst evaluiert, wenn wir die zuverlässig pro Match haben."""
    if not market:
        return False
    m = market.lower()
    return (
        m == "total"
        or m == "total punkte"
        or m == "total runs"
    )


def evaluate_recommended_picks(db: Session) -> int:
    """Auswertung aller noch offenen Picks deren Match FINISHED ist.

    Idempotent: nur Picks ohne ``actual_hit`` werden bewertet.
    Segment-Picks (F5, H1, Quarter etc.) bleiben unbewertet bis wir
    Segment-spezifische Auswertung implementieren.

    Returns: Anzahl neu bewerteter Picks.
    """
    rows = (
        db.query(RecommendedPick, Match)
        .join(Match, RecommendedPick.match_id == Match.id)
        .filter(RecommendedPick.actual_hit.is_(None))
        .filter(Match.status == "FINISHED")
        .filter(Match.home_score.isnot(None))
        .all()
    )

    n = 0
    now = datetime.now(timezone.utc)
    for rp, match in rows:
        if not _is_full_game_market(rp.market):
            continue
        try:
            total = float(match.home_score or 0) + float(match.away_score or 0)
        except (TypeError, ValueError):
            continue
        rp.actual_total = total
        rp.actual_hit = _is_hit(rp, total)
        rp.evaluated_at = now
        n += 1
    db.commit()
    logger.info(f"Evaluated {n} recommended picks")
    return n


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------

def list_recommended(
    db: Session,
    sport: Optional[str] = None,
    only_evaluated: bool = False,
    limit: int = 100,
) -> List[Dict]:
    q = (
        db.query(RecommendedPick, Match)
        .join(Match, RecommendedPick.match_id == Match.id)
        .order_by(Match.kickoff_time.desc())
    )
    if sport:
        q = q.filter(RecommendedPick.sport == sport)
    if only_evaluated:
        q = q.filter(RecommendedPick.actual_hit.isnot(None))
    rows = q.limit(limit).all()
    out: List[Dict] = []
    for rp, m in rows:
        out.append({
            "id": rp.id,
            "match_id": rp.match_id,
            "sport": rp.sport,
            "league": rp.league,
            "home_team": m.home_team_name,
            "away_team": m.away_team_name,
            "kickoff_time": m.kickoff_time.isoformat() if m.kickoff_time else None,
            "market": rp.market,
            "line": rp.line,
            "direction": rp.direction,
            "model_probability": rp.model_probability,
            "fair_odds": rp.fair_odds,
            "bookmaker_name": rp.bookmaker_name,
            "bookmaker_odds": rp.bookmaker_odds,
            "edge": rp.edge,
            "ranking_score": rp.ranking_score,
            "confidence_label": rp.confidence_label,
            "actual_total": rp.actual_total,
            "actual_hit": rp.actual_hit,
            "evaluated_at": rp.evaluated_at.isoformat() if rp.evaluated_at else None,
            "match_status": m.status,
        })
    return out


def recommended_accuracy(db: Session, sport: Optional[str] = None) -> Dict:
    """Aggregierte Trefferquote — gesamt + pro Sport."""
    q = db.query(RecommendedPick).filter(RecommendedPick.actual_hit.isnot(None))
    if sport:
        q = q.filter(RecommendedPick.sport == sport)
    rows = q.all()

    by_sport: Dict[str, Dict] = defaultdict(lambda: {
        "n": 0, "hits": 0, "avg_prob": 0.0, "avg_odds": 0.0,
    })
    total_n = 0
    total_hits = 0
    for r in rows:
        s = by_sport[r.sport]
        s["n"] += 1
        s["avg_prob"] += r.model_probability or 0.0
        s["avg_odds"] += r.fair_odds or 0.0
        total_n += 1
        if r.actual_hit:
            s["hits"] += 1
            total_hits += 1
    result_by_sport = {
        sp: {
            "n": s["n"],
            "hits": s["hits"],
            "hit_rate": round(s["hits"] / s["n"], 3) if s["n"] else 0.0,
            "avg_prob": round(s["avg_prob"] / s["n"], 3) if s["n"] else 0.0,
            "avg_odds": round(s["avg_odds"] / s["n"], 3) if s["n"] else 0.0,
        }
        for sp, s in by_sport.items()
    }
    return {
        "n": total_n,
        "hits": total_hits,
        "hit_rate": round(total_hits / total_n, 3) if total_n else 0.0,
        "by_sport": result_by_sport,
    }

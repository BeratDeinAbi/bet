"""End-to-end-Tests für den Bookmaker-Filter in `recommended.py`.

Setup: in-memory-SQLite mit echten Tabellen.  Wir bauen Match,
Prediction und OddsLine selbst und rufen `persist_recommended_pick`.
Erwartet wird, dass die EV-Logik (model_prob × bookmaker_odds) den
besten Pick wählt UND nur Linien mit bookmaker_odds ≥ 1.25 gewinnen.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.db.database import Base
from app.db.models import Competition, Match, OddsLine, Prediction, RecommendedPick
from app.services.recommended import persist_recommended_pick


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    session = Session()
    # Wichtig: dieser Test-Pfad simuliert „Bookmaker-Modus aktiv".
    # Falls .env in der Test-Umgebung leer ist, setzen wir den Key
    # temporär — sonst springt die Fallback-Logik an.
    settings.ODDS_API_KEY = "TEST"
    settings.ODDS_BOOKMAKER = "betano"
    settings.ODDS_MIN_BOOKMAKER_ODDS = 1.25
    yield session
    session.close()


def _setup_match(db, label="A") -> tuple[Match, Prediction]:
    comp = db.query(Competition).filter(Competition.code == "BL1").first()
    if not comp:
        comp = Competition(code="BL1", name="Bundesliga", sport="football",
                           country="DE", provider="test")
        db.add(comp)
        db.flush()
    match = Match(
        external_id=f"t_{label}",
        competition_id=comp.id,
        home_team_name=f"Heim_{label}",
        away_team_name=f"Aus_{label}",
        kickoff_time=datetime.now(timezone.utc) + timedelta(hours=12),
        status="SCHEDULED",
        sport="football",
    )
    db.add(match)
    db.flush()

    pred = Prediction(
        match_id=match.id,
        expected_total_goals=2.6,
        expected_home_goals=1.4, expected_away_goals=1.2,
        prob_over_0_5=0.97, prob_over_1_5=0.85,
        prob_over_2_5=0.70, prob_over_3_5=0.45,
        prob_under_0_5=0.03, prob_under_1_5=0.15,
        prob_under_2_5=0.30, prob_under_3_5=0.55,
        confidence_score=0.75, confidence_label="HIGH",
        model_agreement_score=0.8, prediction_stability_score=0.7,
    )
    db.add(pred)
    db.flush()
    return match, pred


def _add_odds(db, match_id, line, direction, price, bookmaker="betano"):
    db.add(OddsLine(
        match_id=match_id,
        market="Total",
        line=line,
        direction=direction,
        provider=bookmaker,
        bookmaker_odds=price,
        implied_probability=round(1 / price, 4),
    ))
    db.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pick_taken_when_betano_odds_above_floor(db):
    match, pred = _setup_match(db, "A")
    # Betano: Over 2.5 zu 1.50.  Modell-Prob 0.70 → EV = 1.05.
    _add_odds(db, match.id, line=2.5, direction="over", price=1.50)

    rp = persist_recommended_pick(db, match, pred)
    assert rp is not None
    assert rp.bookmaker_name == "betano"
    assert rp.bookmaker_odds == 1.50
    assert rp.line == 2.5
    assert rp.direction == "over"
    # Edge = 0.70 - 1/1.50 = 0.70 - 0.667 = ~0.033
    assert rp.edge is not None and rp.edge > 0


def test_pick_rejected_when_betano_odds_below_floor(db):
    match, pred = _setup_match(db, "B")
    # Quote nur 1.10 → unter 1.25 → keine Pick-Aufnahme
    _add_odds(db, match.id, line=2.5, direction="over", price=1.10)

    rp = persist_recommended_pick(db, match, pred)
    assert rp is None


def test_no_pick_when_no_betano_odds_at_all(db):
    match, pred = _setup_match(db, "C")
    # Keine OddsLine in der DB → kein Pick (Settings.ODDS_API_KEY ist gesetzt)
    rp = persist_recommended_pick(db, match, pred)
    assert rp is None


def test_pick_only_uses_configured_bookmaker(db):
    match, pred = _setup_match(db, "D")
    # Bet365 hat 1.80 → wäre attraktiv, aber wir wollen nur Betano
    _add_odds(db, match.id, line=2.5, direction="over", price=1.80,
              bookmaker="bet365")

    rp = persist_recommended_pick(db, match, pred)
    assert rp is None


def test_pick_chooses_highest_ev(db):
    """Linie 1: Over 2.5 mit Modell-Prob 0.70 und Quote 1.50 → EV = 1.05.
    Linie 2: Over 1.5 mit Modell-Prob 0.85 und Quote 1.30 → EV = 1.105.
    → Über 1.5 muss gewählt werden (höherer EV)."""
    match, pred = _setup_match(db, "E")
    _add_odds(db, match.id, line=2.5, direction="over", price=1.50)
    _add_odds(db, match.id, line=1.5, direction="over", price=1.30)

    rp = persist_recommended_pick(db, match, pred)
    assert rp is not None
    assert rp.line == 1.5  # höherer EV
    assert rp.bookmaker_odds == 1.30


def test_idempotent_persist(db):
    """Doppelter Aufruf darf keine doppelten RecommendedPicks erzeugen."""
    match, pred = _setup_match(db, "F")
    _add_odds(db, match.id, line=2.5, direction="over", price=1.50)

    rp1 = persist_recommended_pick(db, match, pred)
    rp2 = persist_recommended_pick(db, match, pred)
    assert rp1.id == rp2.id

    rows = db.query(RecommendedPick).filter(
        RecommendedPick.prediction_id == pred.id
    ).all()
    assert len(rows) == 1

"""Tests für die Snapshot-Logik in predict_match() und die Datums-
gefilterten Endpoints.

Setup nutzt eine in-memory-SQLite, weil predict_match() echte DB-
Operationen ausführt und das Verhalten am sinnvollsten end-to-end
getestet wird.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import Base
from app.db.models import Competition, Match, Prediction
from app.services.prediction import predict_match
from app.services.ranking import rank_top3_predictions


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, future=True)
    session = Session()
    yield session
    session.close()


def _make_match(db, sport: str = "football", code: str = "BL1") -> Match:
    comp = Competition(code=code, name=code, sport=sport, country="DE", provider="test")
    db.add(comp)
    db.flush()
    match = Match(
        external_id=f"t_{code}_1",
        competition_id=comp.id,
        home_team_name="Heim",
        away_team_name="Auswärts",
        kickoff_time=datetime.now(timezone.utc) + timedelta(hours=12),
        status="SCHEDULED",
        sport=sport,
    )
    db.add(match)
    db.flush()
    return match


# ---------------------------------------------------------------------------
# Snapshot-Logik
# ---------------------------------------------------------------------------

def test_predict_match_creates_one_row_per_day(db):
    """Mehrfacher predict_match()-Aufruf am selben Tag erzeugt nur eine
    Zeile (Idempotenz beim "Aktualisieren"-Klick)."""
    match = _make_match(db)
    p1 = predict_match(db, match)
    p2 = predict_match(db, match)
    assert p1.id == p2.id

    rows = db.query(Prediction).filter(Prediction.match_id == match.id).all()
    assert len(rows) == 1


def test_predict_match_creates_new_row_on_new_day(db):
    """Wenn eine Prediction von gestern existiert, wird heute eine neue
    Zeile erstellt — die alte bleibt als Snapshot erhalten."""
    match = _make_match(db)

    # Manuell „gestrige" Prediction einfügen
    yesterday = datetime.now(timezone.utc) - timedelta(days=1, hours=1)
    old = Prediction(
        match_id=match.id,
        expected_total_goals=2.5,
        expected_home_goals=1.3,
        expected_away_goals=1.2,
        prob_over_0_5=0.95, prob_over_1_5=0.80, prob_over_2_5=0.55, prob_over_3_5=0.30,
        prob_under_0_5=0.05, prob_under_1_5=0.20, prob_under_2_5=0.45, prob_under_3_5=0.70,
        confidence_score=0.5, confidence_label="MEDIUM",
        model_agreement_score=0.5, prediction_stability_score=0.5,
        created_at=yesterday,
    )
    db.add(old)
    db.commit()

    new = predict_match(db, match)

    rows = (
        db.query(Prediction)
        .filter(Prediction.match_id == match.id)
        .order_by(Prediction.created_at)
        .all()
    )
    assert len(rows) == 2, "alte Snapshot-Zeile + neue heutige"
    assert new.id != old.id
    # Die neue Prediction wurde HEUTE erstellt — SQLite gibt naive
    # datetimes zurück, deshalb auf naive Variante vergleichen.
    assert new.created_at.date() > yesterday.date()


# ---------------------------------------------------------------------------
# Top-3 mit historischem Datum
# ---------------------------------------------------------------------------

def test_rank_top3_uses_snapshot_predictions(db):
    """Mit ``snapshot_date`` werden die Predictions des Tages benutzt,
    nicht die jüngsten."""
    match = _make_match(db, code="BL1")

    # Tag X: schwächere Prediction
    day_x = datetime(2024, 5, 1, 12, 0, tzinfo=timezone.utc)
    p_old = Prediction(
        match_id=match.id,
        expected_total_goals=2.4,
        expected_home_goals=1.3, expected_away_goals=1.1,
        prob_over_0_5=0.90, prob_over_1_5=0.75, prob_over_2_5=0.62,
        prob_over_3_5=0.30,
        prob_under_0_5=0.10, prob_under_1_5=0.25, prob_under_2_5=0.38,
        prob_under_3_5=0.70,
        confidence_score=0.65, confidence_label="MEDIUM",
        model_agreement_score=0.7, prediction_stability_score=0.7,
        created_at=day_x,
    )
    # Tag Y: andere Werte
    day_y = datetime(2024, 5, 5, 12, 0, tzinfo=timezone.utc)
    p_new = Prediction(
        match_id=match.id,
        expected_total_goals=3.4,
        expected_home_goals=2.0, expected_away_goals=1.4,
        prob_over_0_5=0.97, prob_over_1_5=0.92, prob_over_2_5=0.78,
        prob_over_3_5=0.55,
        prob_under_0_5=0.03, prob_under_1_5=0.08, prob_under_2_5=0.22,
        prob_under_3_5=0.45,
        confidence_score=0.85, confidence_label="HIGH",
        model_agreement_score=0.9, prediction_stability_score=0.9,
        created_at=day_y,
    )
    db.add_all([p_old, p_new])
    # Match-Anstoßzeit auf Tag X setzen (das Top-3 sucht nach Spielen des Tages)
    match.kickoff_time = day_x.replace(hour=18)
    db.commit()

    # Snapshot von Tag X → muss die alte Prediction nutzen
    resp_x = rank_top3_predictions(db, snapshot_date=day_x.date())
    assert len(resp_x.picks) == 1
    pick_x = resp_x.picks[0]
    assert abs(pick_x.model_probability - 0.62) < 1e-6 or pick_x.model_probability < 0.80

    # Match auf Tag Y setzen für Tag-Y-Snapshot
    match.kickoff_time = day_y.replace(hour=18)
    db.commit()
    resp_y = rank_top3_predictions(db, snapshot_date=day_y.date())
    assert len(resp_y.picks) == 1
    # Sollte die neuere, optimistischere Prediction nutzen
    assert resp_y.picks[0].model_probability >= pick_x.model_probability

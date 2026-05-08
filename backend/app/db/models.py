from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.database import Base


class Competition(Base):
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True)  # BL1, PL, PD, SSL, NHL
    name = Column(String(100))
    sport = Column(String(20))  # football | hockey
    country = Column(String(50))
    provider = Column(String(50))
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    matches = relationship("Match", back_populates="competition")
    teams = relationship("Team", back_populates="competition")


class Team(Base):
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(50), index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"))
    name = Column(String(100))
    short_name = Column(String(20))
    sport = Column(String(20))
    attack_strength = Column(Float, default=1.0)
    defense_strength = Column(Float, default=1.0)
    elo_rating = Column(Float, default=1500.0)
    home_goal_avg = Column(Float, default=1.5)
    away_goal_avg = Column(Float, default=1.0)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    competition = relationship("Competition", back_populates="teams")


class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), unique=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id"))
    home_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    away_team_id = Column(Integer, ForeignKey("teams.id"), nullable=True)
    home_team_name = Column(String(100))
    away_team_name = Column(String(100))
    kickoff_time = Column(DateTime(timezone=True))
    status = Column(String(20), default="SCHEDULED")  # SCHEDULED | LIVE | FINISHED
    sport = Column(String(20))
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    source = Column(String(50))  # provider name
    # Sport-spezifische Live-Kontext-Daten (Pitcher-ERA, Goalie, Park-Wetter
    # …) — alles was vom Provider mitkommt aber nicht in das normalisierte
    # Schema passt.  Wird vom Prediction-Service zur Adjust-Time gelesen.
    context = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    competition = relationship("Competition", back_populates="matches")
    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    segments = relationship("MatchSegment", back_populates="match")
    predictions = relationship("Prediction", back_populates="match")
    odds_lines = relationship("OddsLine", back_populates="match")


class MatchSegment(Base):
    __tablename__ = "match_segments"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    segment_code = Column(String(10))  # H1, H2 for football; P1, P2, P3 for hockey
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    total_goals = Column(Integer, nullable=True)

    match = relationship("Match", back_populates="segments")


class OddsLine(Base):
    __tablename__ = "odds_lines"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    market = Column(String(50))   # total_goals, h1_goals, p1_goals, etc.
    line = Column(Float)           # 2.5, 0.5, 1.5
    direction = Column(String(10)) # over | under
    bookmaker_odds = Column(Float, nullable=True)
    implied_probability = Column(Float, nullable=True)
    provider = Column(String(50))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match", back_populates="odds_lines")


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"))
    model_run_id = Column(Integer, ForeignKey("model_runs.id"), nullable=True)

    # Full game
    expected_total_goals = Column(Float)
    expected_home_goals = Column(Float)
    expected_away_goals = Column(Float)

    prob_over_0_5 = Column(Float)
    prob_over_1_5 = Column(Float)
    prob_over_2_5 = Column(Float)
    prob_over_3_5 = Column(Float)
    prob_under_0_5 = Column(Float)
    prob_under_1_5 = Column(Float)
    prob_under_2_5 = Column(Float)
    prob_under_3_5 = Column(Float)

    # Football segments
    expected_goals_h1 = Column(Float, nullable=True)
    expected_goals_h2 = Column(Float, nullable=True)
    prob_over_0_5_h1 = Column(Float, nullable=True)
    prob_over_1_5_h1 = Column(Float, nullable=True)
    prob_over_0_5_h2 = Column(Float, nullable=True)
    prob_over_1_5_h2 = Column(Float, nullable=True)

    # NHL segments
    expected_goals_p1 = Column(Float, nullable=True)
    expected_goals_p2 = Column(Float, nullable=True)
    expected_goals_p3 = Column(Float, nullable=True)
    prob_over_0_5_p1 = Column(Float, nullable=True)
    prob_over_1_5_p1 = Column(Float, nullable=True)
    prob_over_0_5_p2 = Column(Float, nullable=True)
    prob_over_1_5_p2 = Column(Float, nullable=True)
    prob_over_0_5_p3 = Column(Float, nullable=True)
    prob_over_1_5_p3 = Column(Float, nullable=True)

    # Confidence
    confidence_score = Column(Float, default=0.5)
    confidence_label = Column(String(20), default="MEDIUM")
    model_agreement_score = Column(Float, default=0.5)
    prediction_stability_score = Column(Float, default=0.5)

    # Sport-spezifische Erweiterungen (NBA Total-Linien 200.5–240.5,
    # Q1–Q4-Punkte usw.).  Hält das Schema schlank: keine 30 Spalten
    # für jede Liga, sondern flexibler JSON-Slot für hohe Score-Sportarten.
    extra_markets = Column(JSON, nullable=True)

    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    match = relationship("Match", back_populates="predictions")
    model_run = relationship("ModelRun", back_populates="predictions")


class ModelRun(Base):
    __tablename__ = "model_runs"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20))
    model_name = Column(String(100))
    model_version = Column(String(50))
    training_date = Column(DateTime(timezone=True), server_default=func.now())
    metrics = Column(JSON, nullable=True)
    model_path = Column(String(255), nullable=True)
    active = Column(Boolean, default=True)

    predictions = relationship("Prediction", back_populates="model_run")


class ProviderLog(Base):
    __tablename__ = "provider_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String(50))
    endpoint = Column(String(255))
    status_code = Column(Integer, nullable=True)
    success = Column(Boolean)
    records_fetched = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PredictionOutcome(Base):
    """Pro Prediction die Auswertung gegen das tatsächliche Ergebnis.

    Wird vom täglichen Backtest-Job angelegt sobald ein Match auf
    FINISHED steht.  Bildet die Datenbasis für Kalibrierung und für die
    Sidebar-Trefferquote.
    """
    __tablename__ = "prediction_outcomes"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), unique=True)
    match_id = Column(Integer, ForeignKey("matches.id"), index=True)

    # Ist-Werte (für UI + Brier-Score)
    actual_total = Column(Float)
    actual_home = Column(Float)
    actual_away = Column(Float)
    expected_total = Column(Float)

    total_abs_error = Column(Float)
    total_squared_error = Column(Float)

    # Hit-Map: pro O/U-Linie ob Modell richtig lag
    # {"over_2_5": {"prob": 0.62, "hit": true}, ...}
    hits = Column(JSON, nullable=True)

    # Wurde der primäre "Top-Pick" (höchste Confidence-Linie) richtig?
    primary_hit = Column(Boolean, nullable=True)
    primary_market = Column(String(50), nullable=True)
    primary_prob = Column(Float, nullable=True)

    sport = Column(String(20), index=True)
    league = Column(String(10), index=True)
    evaluated_at = Column(DateTime(timezone=True), server_default=func.now())

    prediction = relationship("Prediction")
    match = relationship("Match")


class RecommendedPick(Base):
    """Pro vorhergesagtem Match speichert das System hier den besten
    Markt-Pick (höchster Ranking-Score, faire Quote ≥ 1.25) für späteres
    Backtesting.  Eine Zeile = ein Vorschlag, der in Wettlogik einen
    Mehrwert hätte.

    Nach Spielende wird ``actual_hit`` gesetzt (Hit=1 / Miss=0).  Damit
    bekommt das Modell pro Sportart eine ehrliche Wett-Trefferquote
    auf konservativen Picks (keine 95%-Lock-Picks-Inflation).
    """
    __tablename__ = "recommended_picks"

    id = Column(Integer, primary_key=True, index=True)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), unique=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), index=True)

    sport = Column(String(20), index=True)
    league = Column(String(10), index=True)

    market = Column(String(50))             # "Total", "F5 Runs", "Q1 Punkte" ...
    line = Column(Float)                     # 2.5, 7.5, 220.5 ...
    direction = Column(String(10))           # over | under
    model_probability = Column(Float)
    fair_odds = Column(Float)
    ranking_score = Column(Float)
    confidence_label = Column(String(20))

    # Outcome
    actual_total = Column(Float, nullable=True)
    actual_hit = Column(Boolean, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    prediction = relationship("Prediction")
    match = relationship("Match")


class CalibrationBin(Base):
    """Pro Sport eine empirische Kalibrierungs-Kurve.

    Jede Zeile entspricht einem Wahrscheinlichkeits-Bucket (z. B. 0.6–0.7).
    Das Modell sagt im Bucket im Schnitt ``avg_predicted_prob`` voraus —
    tatsächlich getroffen wurde ``empirical_hit_rate``.  Bei der Vorhersage
    werden rohe Modell-Probs durch eine monotonisierte Version dieser Tabelle
    ersetzt (Isotonic Regression).
    """
    __tablename__ = "calibration_bins"

    id = Column(Integer, primary_key=True, index=True)
    sport = Column(String(20), index=True)
    bin_lower = Column(Float)        # 0.0, 0.1, 0.2, ...
    bin_upper = Column(Float)
    n_predictions = Column(Integer)
    avg_predicted_prob = Column(Float)
    empirical_hit_rate = Column(Float)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

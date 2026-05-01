from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class PredictionSchema(BaseModel):
    id: int
    match_id: int

    expected_total_goals: float
    expected_home_goals: float
    expected_away_goals: float

    prob_over_0_5: float
    prob_over_1_5: float
    prob_over_2_5: float
    prob_over_3_5: float
    prob_under_0_5: float
    prob_under_1_5: float
    prob_under_2_5: float
    prob_under_3_5: float

    # Football
    expected_goals_h1: Optional[float] = None
    expected_goals_h2: Optional[float] = None
    prob_over_0_5_h1: Optional[float] = None
    prob_over_1_5_h1: Optional[float] = None
    prob_over_0_5_h2: Optional[float] = None
    prob_over_1_5_h2: Optional[float] = None

    # NHL
    expected_goals_p1: Optional[float] = None
    expected_goals_p2: Optional[float] = None
    expected_goals_p3: Optional[float] = None
    prob_over_0_5_p1: Optional[float] = None
    prob_over_1_5_p1: Optional[float] = None
    prob_over_0_5_p2: Optional[float] = None
    prob_over_1_5_p2: Optional[float] = None
    prob_over_0_5_p3: Optional[float] = None
    prob_over_1_5_p3: Optional[float] = None

    confidence_score: float
    confidence_label: str
    model_agreement_score: float
    prediction_stability_score: float
    explanation: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class Top3Pick(BaseModel):
    match_id: int
    sport: str
    league: str
    home_team: str
    away_team: str
    kickoff_time: datetime
    market: str           # "Over 2.5 Total", "Over 0.5 H1", "Under 6.5 Total"
    market_line: float
    market_direction: str # over | under
    model_probability: float
    fair_odds: float
    bookmaker_odds: Optional[float] = None
    edge: Optional[float] = None
    confidence_score: float
    confidence_label: str
    ranking_score: float
    explanation: str

    class Config:
        from_attributes = True


class Top3Response(BaseModel):
    generated_at: datetime
    picks: List[Top3Pick]


class PredictionWithMatchSchema(PredictionSchema):
    sport: str
    league: str
    home_team: str
    away_team: str
    kickoff_time: datetime


class BacktestSummary(BaseModel):
    sport: str
    league: Optional[str] = None
    market: str
    mae: float
    rmse: float
    brier_score: float
    calibration_error: float
    sample_size: int
    period: str


class ModelStatus(BaseModel):
    sport: str
    model_name: str
    model_version: str
    training_date: Optional[datetime]
    active: bool
    metrics: Optional[dict] = None

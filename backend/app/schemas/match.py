from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CompetitionSchema(BaseModel):
    code: str
    name: str
    sport: str
    country: str

    class Config:
        from_attributes = True


class MatchSegmentSchema(BaseModel):
    segment_code: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    total_goals: Optional[int] = None

    class Config:
        from_attributes = True


class MatchSchema(BaseModel):
    id: int
    external_id: str
    home_team_name: str
    away_team_name: str
    kickoff_time: datetime
    status: str
    sport: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    competition: Optional[CompetitionSchema] = None
    segments: List[MatchSegmentSchema] = []

    class Config:
        from_attributes = True


class MatchListResponse(BaseModel):
    total: int
    matches: List[MatchSchema]

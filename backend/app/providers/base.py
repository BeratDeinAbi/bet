from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class ProviderMatch:
    external_id: str
    sport: str
    competition_code: str
    competition_name: str
    home_team_name: str
    away_team_name: str
    kickoff_time: str  # ISO 8601
    status: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_team_external_id: Optional[str] = None
    away_team_external_id: Optional[str] = None


@dataclass
class ProviderHistoricalMatch(ProviderMatch):
    segments: List[dict] = field(default_factory=list)


class BaseFootballProvider(ABC):
    name: str = "base_football"

    @abstractmethod
    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        pass

    @abstractmethod
    def get_historical_matches(self, league_code: str, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        pass

    def is_available(self) -> bool:
        return True


class BaseHockeyProvider(ABC):
    name: str = "base_hockey"

    @abstractmethod
    def get_today_matches(self) -> List[ProviderMatch]:
        pass

    @abstractmethod
    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        pass

    def is_available(self) -> bool:
        return True


class BaseOddsProvider(ABC):
    name: str = "base_odds"

    @abstractmethod
    def get_odds(self, sport: str, league_code: str, match_external_id: str) -> List[dict]:
        pass

    def is_available(self) -> bool:
        return True

from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Sports Prediction Dashboard"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./data/predictions.db"

    # Football Data API (football-data.org)
    FOOTBALL_DATA_API_KEY: str = ""
    FOOTBALL_DATA_BASE_URL: str = "https://api.football-data.org/v4"

    # Süper Lig Provider (secondary football provider)
    SUPERLIG_API_KEY: str = ""
    SUPERLIG_API_URL: str = ""

    # NHL API (public, no key required for schedule)
    NHL_API_BASE_URL: str = "https://api-web.nhle.com/v1"

    # Odds API (optional)
    ODDS_API_KEY: str = ""
    ODDS_API_BASE_URL: str = "https://api.the-odds-api.com/v4"

    # Providers
    USE_MOCK_FALLBACK: bool = True
    FOOTBALL_PROVIDER: str = "football_data"  # football_data | mock
    HOCKEY_PROVIDER: str = "nhl_api"          # nhl_api | mock
    ODDS_PROVIDER: str = "odds_api"            # odds_api | mock

    # OpenLigaDB (free, no key, Bundesliga & 2. Bundesliga)
    OPENLIGADB_BASE_URL: str = "https://api.openligadb.de"

    # NBA via ESPN public API
    NBA_API_BASE_URL: str = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"

    # MLB via offizielle Stats API (kostenlos, kein Key)
    MLB_API_BASE_URL: str = "https://statsapi.mlb.com/api/v1"

    # Active leagues
    ACTIVE_FOOTBALL_LEAGUES: List[str] = ["BL1", "BL2", "PL", "PD", "SSL"]
    ACTIVE_HOCKEY_LEAGUES: List[str] = ["NHL"]
    ACTIVE_BASKETBALL_LEAGUES: List[str] = ["NBA"]
    ACTIVE_BASEBALL_LEAGUES: List[str] = ["MLB"]

    # ML Config
    MODEL_DIR: str = "./data/models"
    RANDOM_SEED: int = 42
    MIN_HISTORICAL_MATCHES: int = 10

    # Top3 weights
    TOP3_W_CONFIDENCE: float = 0.4
    TOP3_W_MODEL_AGREEMENT: float = 0.3
    TOP3_W_STABILITY: float = 0.2
    TOP3_W_EDGE: float = 0.1

    # CORS
    ALLOWED_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

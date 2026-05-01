from app.core.config import settings
from app.providers.base import BaseFootballProvider, BaseHockeyProvider
from app.providers.mock_provider import MockFootballProvider, MockHockeyProvider


def get_football_provider() -> BaseFootballProvider:
    if settings.FOOTBALL_PROVIDER == "football_data" and settings.FOOTBALL_DATA_API_KEY:
        from app.providers.football_data_provider import FootballDataProvider
        return FootballDataProvider()
    if settings.USE_MOCK_FALLBACK:
        return MockFootballProvider()
    raise RuntimeError("No football provider available and mock fallback is disabled.")


def get_superlig_provider() -> BaseFootballProvider:
    if settings.SUPERLIG_API_KEY and settings.SUPERLIG_API_URL:
        from app.providers.superlig_provider import SuperLigProvider
        return SuperLigProvider()
    return MockFootballProvider()


def get_hockey_provider() -> BaseHockeyProvider:
    if settings.HOCKEY_PROVIDER == "nhl_api":
        from app.providers.nhl_provider import NHLProvider
        provider = NHLProvider()
        if provider.is_available():
            return provider
    if settings.USE_MOCK_FALLBACK:
        return MockHockeyProvider()
    raise RuntimeError("No hockey provider available and mock fallback is disabled.")

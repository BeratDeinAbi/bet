import logging
from app.core.config import settings
from app.providers.base import BaseFootballProvider, BaseHockeyProvider
from app.providers.mock_provider import MockFootballProvider, MockHockeyProvider

logger = logging.getLogger(__name__)


def get_german_football_provider() -> BaseFootballProvider:
    """
    Provider für 1. + 2. Bundesliga.

    OpenLigaDB ist die bevorzugte Quelle (kostenlos, kein Key, kein Rate-Limit,
    deutsches Community-Projekt mit Halbzeit-Ergebnissen). Fällt zurück auf
    den Default-Football-Provider, falls OpenLigaDB nicht erreichbar ist.
    """
    try:
        from app.providers.openligadb_provider import OpenLigaDBProvider
        oldb = OpenLigaDBProvider()
        if oldb.is_available():
            logger.info("German football provider: OpenLigaDB (free, no key)")
            return oldb
    except Exception as e:
        logger.warning(f"OpenLigaDB provider init failed: {e}")
    return get_football_provider()


def get_football_provider() -> BaseFootballProvider:
    # 1. Try ESPN (free, no key, covers all 4 leagues)
    try:
        from app.providers.espn_provider import ESPNFootballProvider
        espn = ESPNFootballProvider()
        if espn.is_available():
            logger.info("Football provider: ESPN (free, no key)")
            return espn
    except Exception as e:
        logger.warning(f"ESPN provider init failed: {e}")

    # 2. Try football-data.org (requires key)
    if settings.FOOTBALL_DATA_API_KEY:
        from app.providers.football_data_provider import FootballDataProvider
        logger.info("Football provider: football-data.org")
        return FootballDataProvider()

    # 3. Mock fallback
    if settings.USE_MOCK_FALLBACK:
        logger.info("Football provider: Mock (fallback)")
        return MockFootballProvider()

    raise RuntimeError("No football provider available.")


def get_superlig_provider() -> BaseFootballProvider:
    # Süper Lig is covered by ESPN (tur.1) — use same ESPN provider
    try:
        from app.providers.espn_provider import ESPNFootballProvider
        espn = ESPNFootballProvider()
        if espn.is_available():
            return espn
    except Exception:
        pass
    if settings.SUPERLIG_API_KEY and settings.SUPERLIG_API_URL:
        from app.providers.superlig_provider import SuperLigProvider
        return SuperLigProvider()
    return MockFootballProvider()


def get_hockey_provider() -> BaseHockeyProvider:
    # 1. NHL public API (no key required)
    try:
        from app.providers.nhl_provider import NHLProvider
        nhl = NHLProvider()
        if nhl.is_available():
            logger.info("Hockey provider: NHL public API")
            return nhl
    except Exception as e:
        logger.warning(f"NHL provider init failed: {e}")

    # 2. Mock fallback
    if settings.USE_MOCK_FALLBACK:
        logger.info("Hockey provider: Mock (fallback)")
        return MockHockeyProvider()

    raise RuntimeError("No hockey provider available.")

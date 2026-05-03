"""
Mock/fallback provider — always works, no API keys needed.
Loads seed data from data/mock/ directory.
"""
import json
import os
import logging
from datetime import date, datetime, timedelta, timezone
from typing import List

from app.providers.base import BaseFootballProvider, BaseHockeyProvider, ProviderMatch, ProviderHistoricalMatch

logger = logging.getLogger(__name__)

MOCK_DIR = os.path.join(os.path.dirname(__file__), "../../../../data/mock")


def _load_json(filename: str) -> dict:
    path = os.path.join(MOCK_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _today_kickoffs(count: int, sport: str) -> List[str]:
    today = datetime.now(timezone.utc).replace(hour=18, minute=0, second=0, microsecond=0)
    return [(today + timedelta(hours=i)).isoformat() for i in range(count)]


class MockFootballProvider(BaseFootballProvider):
    name = "mock_football"

    def get_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        data = _load_json("football_today.json")
        matches_data = data.get("matches", []) if data else []
        if matches_data:
            return [ProviderMatch(**m) for m in matches_data if m["competition_code"] in league_codes]
        return self._generate_today_matches(league_codes)

    def _generate_today_matches(self, league_codes: List[str]) -> List[ProviderMatch]:
        fixtures = {
            "BL1": [("Bayern München", "Borussia Dortmund"), ("Bayer Leverkusen", "RB Leipzig"), ("Eintracht Frankfurt", "VfB Stuttgart")],
            "BL2": [("Hamburger SV", "FC Schalke 04"), ("1. FC Köln", "Hertha BSC"), ("Hannover 96", "Fortuna Düsseldorf")],
            "PL": [("Manchester City", "Arsenal"), ("Liverpool", "Chelsea"), ("Tottenham", "Manchester United")],
            "PD": [("Real Madrid", "FC Barcelona"), ("Atletico Madrid", "Sevilla"), ("Athletic Club", "Villarreal")],
            "SSL": [("Galatasaray", "Fenerbahçe"), ("Beşiktaş", "Trabzonspor"), ("Başakşehir", "Adana Demirspor")],
        }
        times = _today_kickoffs(15, "football")
        matches, idx = [], 0
        for code, pairs in fixtures.items():
            if code not in league_codes:
                continue
            league_names = {"BL1": "Bundesliga", "BL2": "2. Bundesliga", "PL": "Premier League", "PD": "La Liga", "SSL": "Süper Lig"}
            for home, away in pairs:
                matches.append(ProviderMatch(
                    external_id=f"mock_fb_{code}_{idx}",
                    sport="football",
                    competition_code=code,
                    competition_name=league_names.get(code, code),
                    home_team_name=home,
                    away_team_name=away,
                    kickoff_time=times[idx % len(times)],
                    status="SCHEDULED",
                ))
                idx += 1
        return matches

    def get_historical_matches(self, league_code: str, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        data = _load_json("football_historical.json")
        if data:
            return [ProviderHistoricalMatch(**m) for m in data.get("matches", []) if m.get("competition_code") == league_code]
        return self._generate_historical(league_code)

    def _generate_historical(self, league_code: str) -> List[ProviderHistoricalMatch]:
        import random
        rng = random.Random(42)
        fixtures = {
            "BL1": [("Bayern München", "Borussia Dortmund"), ("Bayer Leverkusen", "RB Leipzig")],
            "BL2": [("Hamburger SV", "FC Schalke 04"), ("1. FC Köln", "Hertha BSC")],
            "PL": [("Manchester City", "Arsenal"), ("Liverpool", "Chelsea")],
            "PD": [("Real Madrid", "FC Barcelona"), ("Atletico Madrid", "Sevilla")],
            "SSL": [("Galatasaray", "Fenerbahçe"), ("Beşiktaş", "Trabzonspor")],
        }
        pairs = fixtures.get(league_code, [("Team A", "Team B")])
        league_names = {"BL1": "Bundesliga", "BL2": "2. Bundesliga", "PL": "Premier League", "PD": "La Liga", "SSL": "Süper Lig"}
        historical = []
        base_date = datetime(2024, 8, 1, 15, 0, 0, tzinfo=timezone.utc)
        for i in range(50):
            home, away = pairs[i % len(pairs)]
            home_score = rng.choice([0, 1, 1, 2, 2, 2, 3, 3, 4])
            away_score = rng.choice([0, 0, 1, 1, 2, 2, 3])
            h1_home = min(home_score, rng.randint(0, home_score))
            h1_away = min(away_score, rng.randint(0, away_score))
            kickoff = (base_date + timedelta(days=i * 7)).isoformat()
            historical.append(ProviderHistoricalMatch(
                external_id=f"mock_hist_{league_code}_{i}",
                sport="football",
                competition_code=league_code,
                competition_name=league_names.get(league_code, league_code),
                home_team_name=home,
                away_team_name=away,
                kickoff_time=kickoff,
                status="FINISHED",
                home_score=home_score,
                away_score=away_score,
                segments=[
                    {"segment_code": "H1", "home_score": h1_home, "away_score": h1_away, "total_goals": h1_home + h1_away},
                    {"segment_code": "H2", "home_score": home_score - h1_home, "away_score": away_score - h1_away, "total_goals": (home_score - h1_home) + (away_score - h1_away)},
                ],
            ))
        return historical


class MockHockeyProvider(BaseHockeyProvider):
    name = "mock_hockey"

    def get_today_matches(self) -> List[ProviderMatch]:
        data = _load_json("nhl_today.json")
        matches_data = data.get("matches", []) if data else []
        if matches_data:
            return [ProviderMatch(**m) for m in matches_data]
        return self._generate_today_matches()

    def _generate_today_matches(self) -> List[ProviderMatch]:
        times = _today_kickoffs(4, "hockey")
        pairs = [("Boston Bruins", "Toronto Maple Leafs"), ("Colorado Avalanche", "Vegas Golden Knights"),
                 ("New York Rangers", "Carolina Hurricanes"), ("Edmonton Oilers", "Dallas Stars")]
        return [
            ProviderMatch(
                external_id=f"mock_nhl_{i}",
                sport="hockey",
                competition_code="NHL",
                competition_name="NHL",
                home_team_name=h,
                away_team_name=a,
                kickoff_time=times[i % len(times)],
                status="SCHEDULED",
            )
            for i, (h, a) in enumerate(pairs)
        ]

    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        data = _load_json("nhl_historical.json")
        if data:
            return [ProviderHistoricalMatch(**m) for m in data.get("matches", [])]
        return self._generate_historical()

    def _generate_historical(self) -> List[ProviderHistoricalMatch]:
        import random
        rng = random.Random(42)
        pairs = [("Boston Bruins", "Toronto Maple Leafs"), ("Colorado Avalanche", "Vegas Golden Knights")]
        historical = []
        base_date = datetime(2024, 10, 1, 19, 0, 0, tzinfo=timezone.utc)
        for i in range(60):
            home, away = pairs[i % len(pairs)]
            home_score = rng.choice([1, 2, 2, 3, 3, 4, 5, 6])
            away_score = rng.choice([1, 1, 2, 2, 3, 4])
            p_scores = []
            remaining_h, remaining_a = home_score, away_score
            for p in range(1, 4):
                ph = rng.randint(0, remaining_h) if p < 3 else remaining_h
                pa = rng.randint(0, remaining_a) if p < 3 else remaining_a
                remaining_h -= ph
                remaining_a -= pa
                p_scores.append({"segment_code": f"P{p}", "home_score": ph, "away_score": pa, "total_goals": ph + pa})
            kickoff = (base_date + timedelta(days=i * 3)).isoformat()
            historical.append(ProviderHistoricalMatch(
                external_id=f"mock_nhl_hist_{i}",
                sport="hockey",
                competition_code="NHL",
                competition_name="NHL",
                home_team_name=home,
                away_team_name=away,
                kickoff_time=kickoff,
                status="FINISHED",
                home_score=home_score,
                away_score=away_score,
                segments=p_scores,
            ))
        return historical


class MockBasketballProvider(BaseHockeyProvider):
    """NBA-Mock — Demo-/Fallback-Daten mit realistischen Score-Niveaus."""

    name = "mock_basketball"

    PAIRS = [
        ("Los Angeles Lakers", "Boston Celtics"),
        ("Golden State Warriors", "Denver Nuggets"),
        ("Milwaukee Bucks", "Philadelphia 76ers"),
        ("Miami Heat", "New York Knicks"),
    ]

    def get_today_matches(self) -> List[ProviderMatch]:
        data = _load_json("nba_today.json")
        matches_data = data.get("matches", []) if data else []
        if matches_data:
            return [ProviderMatch(**m) for m in matches_data]
        return self._generate_today_matches()

    def _generate_today_matches(self) -> List[ProviderMatch]:
        times = _today_kickoffs(4, "basketball")
        return [
            ProviderMatch(
                external_id=f"mock_nba_{i}",
                sport="basketball",
                competition_code="NBA",
                competition_name="NBA",
                home_team_name=h,
                away_team_name=a,
                kickoff_time=times[i % len(times)],
                status="SCHEDULED",
            )
            for i, (h, a) in enumerate(self.PAIRS)
        ]

    def get_historical_matches(self, seasons: List[str]) -> List[ProviderHistoricalMatch]:
        data = _load_json("nba_historical.json")
        if data:
            return [ProviderHistoricalMatch(**m) for m in data.get("matches", [])]
        return self._generate_historical()

    def _generate_historical(self) -> List[ProviderHistoricalMatch]:
        import random
        rng = random.Random(42)
        historical: List[ProviderHistoricalMatch] = []
        base_date = datetime(2024, 11, 1, 19, 30, 0, tzinfo=timezone.utc)
        for i in range(80):
            home, away = self.PAIRS[i % len(self.PAIRS)]
            home_score = max(85, int(rng.gauss(114, 12)))
            away_score = max(85, int(rng.gauss(110, 12)))
            quarters = []
            remaining_h, remaining_a = home_score, away_score
            for q in range(1, 5):
                if q < 4:
                    qh = max(15, int(rng.gauss(home_score / 4.0, 3)))
                    qa = max(15, int(rng.gauss(away_score / 4.0, 3)))
                    qh = min(qh, remaining_h - 15 * (4 - q))
                    qa = min(qa, remaining_a - 15 * (4 - q))
                    qh = max(qh, 15)
                    qa = max(qa, 15)
                else:
                    qh, qa = remaining_h, remaining_a
                remaining_h -= qh
                remaining_a -= qa
                quarters.append({
                    "segment_code": f"Q{q}",
                    "home_score": qh,
                    "away_score": qa,
                    "total_goals": qh + qa,
                })
            kickoff = (base_date + timedelta(days=i * 2)).isoformat()
            historical.append(ProviderHistoricalMatch(
                external_id=f"mock_nba_hist_{i}",
                sport="basketball",
                competition_code="NBA",
                competition_name="NBA",
                home_team_name=home,
                away_team_name=away,
                kickoff_time=kickoff,
                status="FINISHED",
                home_score=home_score,
                away_score=away_score,
                segments=quarters,
            ))
        return historical

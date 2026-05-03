"""
Training pipeline: loads historical matches from DB, trains models, saves to disk.
"""
import os
import sys
import logging
from typing import List, Dict

# Allow running standalone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../backend"))

from app.core.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import Match, MatchSegment, Competition

from ml.models.football_model import FootballEnsemble
from ml.models.hockey_model import NHLEnsemble

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def _fetch_football_matches(db, league_code: str) -> List[Dict]:
    comp = db.query(Competition).filter(Competition.code == league_code).first()
    if not comp:
        return []
    matches = (
        db.query(Match)
        .filter(Match.competition_id == comp.id, Match.status == "FINISHED",
                Match.home_score.isnot(None))
        .all()
    )
    result = []
    for m in matches:
        segs = db.query(MatchSegment).filter(MatchSegment.match_id == m.id).all()
        result.append({
            "home_team": m.home_team_name,
            "away_team": m.away_team_name,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "kickoff_time": m.kickoff_time.isoformat() if m.kickoff_time else None,
            "segments": [{"segment_code": s.segment_code, "home_score": s.home_score,
                          "away_score": s.away_score, "total_goals": s.total_goals} for s in segs],
        })
    return result


def _fetch_nhl_matches(db) -> List[Dict]:
    comp = db.query(Competition).filter(Competition.code == "NHL").first()
    if not comp:
        return []
    matches = (
        db.query(Match)
        .filter(Match.competition_id == comp.id, Match.status == "FINISHED",
                Match.home_score.isnot(None))
        .all()
    )
    result = []
    for m in matches:
        segs = db.query(MatchSegment).filter(MatchSegment.match_id == m.id).all()
        result.append({
            "home_team": m.home_team_name,
            "away_team": m.away_team_name,
            "home_score": m.home_score,
            "away_score": m.away_score,
            "kickoff_time": m.kickoff_time.isoformat() if m.kickoff_time else None,
            "segments": [{"segment_code": s.segment_code, "home_score": s.home_score,
                          "away_score": s.away_score, "total_goals": s.total_goals} for s in segs],
        })
    return result


def train_football_models() -> Dict[str, str]:
    init_db()
    db = SessionLocal()
    paths = {}
    try:
        for league_code in ["BL1", "BL2", "PL", "PD", "SSL"]:
            matches = _fetch_football_matches(db, league_code)
            logger.info(f"Training football model for {league_code} with {len(matches)} matches")
            ensemble = FootballEnsemble(league_code)
            ensemble.fit(matches)
            path = os.path.join(settings.MODEL_DIR, f"football_{league_code}.pkl")
            ensemble.save(path)
            paths[league_code] = path
    finally:
        db.close()
    return paths


def train_hockey_models() -> str:
    init_db()
    db = SessionLocal()
    try:
        matches = _fetch_nhl_matches(db)
        logger.info(f"Training NHL model with {len(matches)} matches")
        ensemble = NHLEnsemble()
        ensemble.fit(matches)
        path = os.path.join(settings.MODEL_DIR, "hockey_NHL.pkl")
        ensemble.save(path)
        return path
    finally:
        db.close()


if __name__ == "__main__":
    logger.info("Starting model training...")
    fb_paths = train_football_models()
    nhl_path = train_hockey_models()
    logger.info(f"Football models: {fb_paths}")
    logger.info(f"NHL model: {nhl_path}")
    logger.info("Training complete.")

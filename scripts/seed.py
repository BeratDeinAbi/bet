#!/usr/bin/env python3
"""
Seed script: ingest historical mock data, train models, generate today's predictions.
Run from repo root: python scripts/seed.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.db.database import init_db, SessionLocal
from app.services.ingestion import ingest_historical_matches, ingest_today_matches
from app.services.prediction import predict_today

def main():
    print("Initializing database...")
    init_db()
    db = SessionLocal()

    try:
        print("Ingesting historical mock data...")
        n_hist = ingest_historical_matches(db)
        print(f"  -> {n_hist} historical matches ingested")

        print("Training models...")
        try:
            from ml.training.train_models import train_football_models, train_hockey_models
            fb = train_football_models()
            nhl = train_hockey_models()
            print(f"  -> Football models: {list(fb.keys())}")
            print(f"  -> NHL model: {nhl}")
        except Exception as e:
            print(f"  ! Model training failed: {e}")
            print("  -> Will use fallback predictions")

        print("Ingesting today's matches...")
        n_today = ingest_today_matches(db)
        print(f"  -> {n_today} matches for today")

        print("Generating predictions...")
        n_preds = predict_today(db)
        print(f"  -> {n_preds} predictions generated")

        print("\n=== Seed Complete ===")
        print("Start backend: cd backend && uvicorn main:app --reload")
        print("Start frontend: cd frontend && npm run dev")

    finally:
        db.close()

if __name__ == "__main__":
    main()

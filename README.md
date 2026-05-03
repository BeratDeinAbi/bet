# Sports Prediction Dashboard

Lokale Web-App für Fußball- und NHL-Torprognosen. Täglich aktualisierte Vorhersagen mit Poisson-Modellen, Dixon-Coles-Korrektur und Elo-Rating-Ensemble.

## Features

- **Heutige Spiele**: Bundesliga, 2. Bundesliga, Premier League, La Liga, Süper Lig, NHL, NBA, MLB
- **Tor- / Punkte- / Run-Prognosen**: Gesamt, 1. HZ / 2. HZ (Fußball), Periode 1–3 (NHL), Q1–Q4 (NBA), Total Runs + F5 (MLB)
- **Over/Under**: Wahrscheinlichkeiten für alle gängigen Linien
- **Top 3 Picks**: Täglich die 3 besten Torprognosen mit Ranking-Score
- **Confidence Score**: Modellkonfidenz + Stabilitätsmetrik
- **Backtesting**: MAE, RMSE, Brier Score pro Liga und Markt
- **Mock-Fallback**: Läuft vollständig ohne API-Keys

## Tech Stack

| Layer | Technologie |
|-------|-------------|
| Frontend | React 18 + TypeScript + Vite + Tailwind |
| Backend | FastAPI + SQLAlchemy |
| DB | SQLite |
| ML | Python: Scipy, NumPy, Scikit-learn |
| ML-Modelle | Poisson MLE, Dixon-Coles, Elo, Ensemble |

## Schnellstart

### 1. Setup

```bash
cp .env.example .env
# Optional: API Keys in .env eintragen

# Backend
cd backend
pip install -r requirements.txt
cd ..

# Frontend
cd frontend
npm install
cd ..
```

### 2. Backend starten

```bash
cd backend
uvicorn main:app --reload --port 8000
```

API: http://localhost:8000 | Swagger: http://localhost:8000/docs

### 3. Frontend starten

```bash
cd frontend
npm run dev
```

Dashboard: http://localhost:5173

### 4. Daten laden

Im Browser auf **"Daten laden"** klicken oder:

```bash
python scripts/seed.py
```

Lädt: historische Mock-Daten → trainiert Modelle → generiert heutige Prognosen.

## API-Keys eintragen (.env)

```env
FOOTBALL_DATA_API_KEY=your_key   # football-data.org (BL1, PL, PD)
SUPERLIG_API_KEY=your_key        # eigener Süper Lig Provider
SUPERLIG_API_URL=https://...
ODDS_API_KEY=your_key            # the-odds-api.com (optional)
```

## Struktur

```
backend/app/
  api/endpoints/    REST Endpoints
  core/config.py   Settings (.env)
  db/              SQLAlchemy + SQLite
  providers/       Provider Abstraktion + Adapter
  schemas/         Pydantic
  services/        Business Logic

frontend/src/
  api/client.ts    API Client
  components/      MatchCard, Top3Modal, ...
  pages/           Dashboard, Detail, Backtests

ml/
  models/          FootballEnsemble, NHLEnsemble
  training/        Trainings-Pipeline
  backtesting/     Walk-forward Validierung

data/mock/         JSON Mock-Daten
data/models/       Gespeicherte Modelle (.pkl)
scripts/           Setup + Seed
```

## Wichtige Endpoints

| Endpoint | Beschreibung |
|----------|--------------|
| GET /health | Status |
| GET /matches/today | Heutige Spiele |
| GET /predictions/today | Alle Prognosen |
| GET /predictions/top3 | Top 3 Picks |
| POST /admin/seed | Daten laden + Training |
| GET /backtests/summary | Backtest-Ergebnisse |

## ML-Modelle

**Fußball**: Poisson MLE + Dixon-Coles (ρ=-0.13) + Elo Adjustment + HalfTime-Modell

**NHL**: Poisson MLE + Elo + Period-Ratios (P1/P2/P3)

**NBA**: Normal-Verteilung MLE (Punkte ~Gaussian) + Elo + Rolling-Form + Quarter-Modell (Q1–Q4)

**MLB**: Poisson MLE (Runs ~Poisson) + Elo + Rolling-Form + F5-Segment + optionales Pitcher-ERA-Adjustment

**Ensemble**: Gewichtete Kombination mit walk-forward Backtesting

## Nächste Schritte (v2)

- XGBoost als dritte Ensemble-Stufe
- Live-Score Integration
- Odds API Vollintegration (Edge-Berechnung)
- Mehr Ligen: Serie A, Champions League
- Rolling Form-Features (letzte 5 Spiele)

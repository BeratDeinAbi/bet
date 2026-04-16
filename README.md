# Sports Prediction Bot

> AI-powered prediction bot for **Football**, **Tennis** & **NHL** — built with Python, scikit-learn, XGBoost & Streamlit

---

## Projektstruktur

```
sports-prediction-bot/
├── main.py                    # Streamlit Dashboard
├── requirements.txt
├── config/
│   └── leagues.json           # Liga- & Turnierkonfiguration
├── predictors/
│   ├── football_predictor.py  # Fußball ML-Modell
│   ├── tennis_predictor.py    # Tennis ML-Modell
│   └── nhl_predictor.py       # NHL ML-Modell
└── utils/
    ├── data_fetcher.py        # API & Daten-Abruf
    └── model_trainer.py       # Modell-Training & Evaluation
```

---

## Sportarten & Features

### Fußball
**Ligen:** Bundesliga, 2. Bundesliga, 3. Liga, Premier League, Championship, Serie A, Ligue 1, Süper Lig, Eredivisie, La Liga

**Vorhersagen:**
- Welche Mannschaft gewinnt (1X2 Klassifikation)
- Erwartete Gesamttore (Poisson-Regression)
- Both Teams to Score (BTTS) — Ja/Nein
- Erwartete Tore in der 1. Halbzeit

**Algorithmen:** Poisson-Regression, XGBoost Classifier, Random Forest, Dixon-Coles Modell, ELO-Rating

### Tennis
**Kategorien:** ATP Tour, Roland Garros (Paris), Wimbledon (London)

**Vorhersagen:**
- Klarer Favorit oder offenes Match (Wahrscheinlichkeit)
- Tiebreak-Wahrscheinlichkeit pro Satz
- Satz-Verlauf (knapp / einseitig)

**Algorithmen:** Elo-basiertes Matchmodell, Serve/Return Stats, Surface-Adjusted Win Probability

### NHL (Eishockey)
**Liga:** NHL

**Vorhersagen:**
- Erwartete Tore in der regulären Spielzeit (gesamt)
- Erwartete Tore pro Team (individuell)

**Algorithmen:** Poisson-Modell (Goals/60), Corsi/Fenwick Analytics, Power-Play Efficiency

---

## Installation

```bash
git clone https://github.com/BeratDeinAbi/sports-prediction-bot.git
cd sports-prediction-bot
pip install -r requirements.txt
streamlit run main.py
```

---

## Datenquellen

- [football-data.org](https://www.football-data.org/) — kostenlose Football API
- [api-tennis.com](https://api-tennis.com/) — Tennis Statistiken
- [NHL Stats API](https://statsapi.web.nhl.com/) — offizielle NHL API (kostenlos)
- [sportsipy](https://github.com/roclark/sportsipy) — Python Sports Reference Wrapper

---

## Tech Stack

| Tool | Zweck |
|---|---|
| Python 3.11 | Hauptsprache |
| scikit-learn | ML Modelle |
| XGBoost | Gradient Boosting |
| pandas / numpy | Datenverarbeitung |
| Streamlit | Dashboard UI |
| requests | API Calls |
| scipy | Poisson Statistik |

---

*Made with Python — Data Science Projekt*

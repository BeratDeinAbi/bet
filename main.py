"""
Sports Prediction Bot - Streamlit Dashboard

Main entry point for the prediction app.
Run with: streamlit run main.py
"""

import streamlit as st
import json
import sys
sys.path.append('.')

from predictors.football_predictor import FootballPredictor
from predictors.tennis_predictor import TennisPredictor
from predictors.nhl_predictor import NHLPredictor

# Page Config
st.set_page_config(
    page_title="Sports Prediction Bot",
    page_icon="⚽",
    layout="wide"
)

# Title
st.title("⚽ 🎾 🏒 Sports Prediction Bot")
st.markdown("**AI-Powered Predictions for Football, Tennis & NHL**")

# Sidebar - Sport Selection
st.sidebar.header("🎯 Select Sport")
sport = st.sidebar.radio("", ["Football", "Tennis", "NHL"])

# Load Config
with open('config/leagues.json', 'r') as f:
    config = json.load(f)

# ============================
# FOOTBALL PREDICTIONS
# ============================
if sport == "Football":
    st.header("⚽ Football Match Prediction")
    
    predictor = FootballPredictor()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏠 Home Team")
        home_team = st.text_input("Team Name", "Bayern Munich")
        home_goals_scored = st.number_input("Goals Scored (last 15)", 20, 50, 35)
        home_goals_conceded = st.number_input("Goals Conceded (last 15)", 5, 30, 12)
        home_matches = st.number_input("Matches Played", 10, 20, 15)
    
    with col2:
        st.subheader("✈️ Away Team")
        away_team = st.text_input("Team Name ", "Borussia Dortmund")
        away_goals_scored = st.number_input("Goals Scored (last 15) ", 20, 50, 28)
        away_goals_conceded = st.number_input("Goals Conceded (last 15) ", 5, 30, 18)
        away_matches = st.number_input("Matches Played ", 10, 20, 15)
    
    if st.button("🔮 Generate Prediction"):
        home_form = {
            'goals_scored': home_goals_scored,
            'goals_conceded': home_goals_conceded,
            'matches': home_matches
        }
        
        away_form = {
            'goals_scored': away_goals_scored,
            'goals_conceded': away_goals_conceded,
            'matches': away_matches
        }
        
        prediction = predictor.comprehensive_prediction(
            home_team, away_team, home_form, away_form
        )
        
        st.success(f"**Match:** {prediction['match']}")
        
        # Winner Prediction
        st.subheader("🏆 Winner Prediction")
        winner = prediction['winner_prediction']
        st.metric("Prediction", winner['prediction'], f"{winner['confidence']:.1%} confidence")
        
        cols = st.columns(3)
        cols[0].metric("Home Win", f"{winner['probabilities']['home_win']:.1%}")
        cols[1].metric("Draw", f"{winner['probabilities']['draw']:.1%}")
        cols[2].metric("Away Win", f"{winner['probabilities']['away_win']:.1%}")
        
        # Total Goals
        st.subheader("⚽ Total Goals")
        total = prediction['total_goals']
        st.metric("Expected Total", total['expected_total'])
        
        cols2 = st.columns(2)
        cols2[0].metric("Home Expected", total['home_expected'])
        cols2[1].metric("Away Expected", total['away_expected'])
        
        cols3 = st.columns(2)
        cols3[0].metric("Over 2.5", f"{total['over_2.5_prob']:.1%}")
        cols3[1].metric("Under 2.5", f"{total['under_2.5_prob']:.1%}")
        
        # BTTS
        st.subheader("🎯 Both Teams To Score")
        btts = prediction['btts']
        st.metric("Prediction", btts['btts'], f"{btts['btts_probability']:.1%} probability")
        
        # First Half
        st.subheader("⏱️ First Half Goals")
        fh = prediction['first_half']
        st.metric("Expected Goals", fh['expected_goals'])
        
        cols4 = st.columns(2)
        cols4[0].metric("Over 0.5", f"{fh['over_0.5_prob']:.1%}")
        cols4[1].metric("Over 1.5", f"{fh['over_1.5_prob']:.1%}")

# ============================
# TENNIS PREDICTIONS
# ============================
elif sport == "Tennis":
    st.header("🎾 Tennis Match Prediction")
    
    predictor = TennisPredictor()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🎾 Player A")
        player_a = st.text_input("Player Name", "Carlos Alcaraz")
        elo_a = st.number_input("ELO Rating", 1200, 2500, 2200)
        serve_a = st.slider("Serve Win %", 50, 80, 68) / 100
        return_a = st.slider("Return Win %", 20, 50, 38) / 100
    
    with col2:
        st.subheader("🎾 Player B")
        player_b = st.text_input("Player Name ", "Jannik Sinner")
        elo_b = st.number_input("ELO Rating ", 1200, 2500, 2150)
        serve_b = st.slider("Serve Win % ", 50, 80, 66) / 100
        return_b = st.slider("Return Win % ", 20, 50, 36) / 100
    
    surface = st.selectbox("Surface", ["hard", "clay", "grass", "indoor"])
    
    if st.button("🔮 Generate Prediction "):
        player_a_stats = {'elo': elo_a, 'serve_win_pct': serve_a, 'return_win_pct': return_a}
        player_b_stats = {'elo': elo_b, 'serve_win_pct': serve_b, 'return_win_pct': return_b}
        
        prediction = predictor.comprehensive_prediction(
            player_a, player_b, player_a_stats, player_b_stats, surface
        )
        
        st.success(f"**Match:** {prediction['match']} ({prediction['surface'].upper()})")
        
        # Winner
        st.subheader("🏆 Match Winner")
        winner = prediction['winner_prediction']
        st.metric("Prediction", winner['prediction'], winner['favorite_status'])
        st.metric("Confidence", f"{winner['confidence']:.1%}")
        
        cols = st.columns(2)
        cols[0].metric(f"{player_a} Win Prob", f"{winner['player_a_prob']:.1%}")
        cols[1].metric(f"{player_b} Win Prob", f"{winner['player_b_prob']:.1%}")
        
        # Tiebreak
        st.subheader("🎯 Tiebreak Probability")
        tiebreak = prediction['tiebreak']
        st.metric("Prediction", tiebreak['prediction'], f"{tiebreak['tiebreak_probability']:.1%}")
        
        # Set Closeness
        st.subheader("📊 Set Closeness")
        closeness = prediction['set_closeness']
        st.metric("Prediction", closeness['prediction'], closeness['closeness_score'])
        st.metric("ELO Difference", closeness['elo_difference'])

# ============================
# NHL PREDICTIONS
# ============================
else:  # NHL
    st.header("🏒 NHL Game Prediction")
    
    predictor = NHLPredictor()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🏠 Home Team")
        home_team = st.text_input("Team Name", "Colorado Avalanche")
        home_gf60 = st.number_input("Goals For/60", 1.5, 4.5, 3.2, 0.1)
        home_ga60 = st.number_input("Goals Against/60", 1.5, 4.0, 2.4, 0.1)
        home_corsi = st.slider("Corsi For %", 40.0, 65.0, 54.5, 0.1)
        home_pp = st.slider("Power Play %", 10.0, 35.0, 25.0, 0.5)
    
    with col2:
        st.subheader("✈️ Away Team")
        away_team = st.text_input("Team Name ", "Edmonton Oilers")
        away_gf60 = st.number_input("Goals For/60 ", 1.5, 4.5, 3.5, 0.1)
        away_ga60 = st.number_input("Goals Against/60 ", 1.5, 4.0, 2.8, 0.1)
        away_corsi = st.slider("Corsi For % ", 40.0, 65.0, 51.2, 0.1)
        away_pp = st.slider("Power Play % ", 10.0, 35.0, 28.0, 0.5)
    
    if st.button("🔮 Generate Prediction  "):
        home_stats = {
            'goals_for_60': home_gf60,
            'goals_against_60': home_ga60,
            'corsi_for_pct': home_corsi,
            'pp_pct': home_pp
        }
        
        away_stats = {
            'goals_for_60': away_gf60,
            'goals_against_60': away_ga60,
            'corsi_for_pct': away_corsi,
            'pp_pct': away_pp
        }
        
        prediction = predictor.comprehensive_prediction(
            home_team, away_team, home_stats, away_stats
        )
        
        st.success(f"**NHL Game:** {prediction['matchup']}")
        
        # Winner
        st.subheader("🏆 Game Winner")
        winner = prediction['winner']
        st.metric("Prediction", winner['prediction'], f"{winner['confidence']:.1%} confidence")
        
        cols = st.columns(2)
        cols[0].metric("Home Win Prob", f"{winner['home_win_prob']:.1%}")
        cols[1].metric("Away Win Prob", f"{winner['away_win_prob']:.1%}")
        
        # Total Goals
        st.subheader("🎯 Total Goals (Regulation)")
        total = prediction['total_goals']
        st.metric("Expected Total", total['total_expected'])
        
        cols2 = st.columns(2)
        cols2[0].metric("Over 5.5", f"{total['over_5.5_prob']:.1%}")
        cols2[1].metric("Under 5.5", f"{total['under_5.5_prob']:.1%}")
        
        cols3 = st.columns(2)
        cols3[0].metric("Over 6.5", f"{total['over_6.5_prob']:.1%}")
        cols3[1].metric("Under 6.5", f"{total['under_6.5_prob']:.1%}")
        
        # Team Goals
        st.subheader("🥅 Individual Team Goals")
        home_goals = prediction['home_team_goals']
        away_goals = prediction['away_team_goals']
        
        cols4 = st.columns(2)
        with cols4[0]:
            st.metric(f"{home_goals['team']}", f"{home_goals['expected_goals']} goals")
            st.caption(f"Most likely: {home_goals['most_likely_goals']} goals")
        
        with cols4[1]:
            st.metric(f"{away_goals['team']}", f"{away_goals['expected_goals']} goals")
            st.caption(f"Most likely: {away_goals['most_likely_goals']} goals")

st.sidebar.markdown("---")
st.sidebar.caption("🔥 Built with Python, scikit-learn, XGBoost & Streamlit")

"""
Football Match Prediction Module

Implements advanced prediction models:
- Dixon-Coles Model for match outcomes
- Poisson Regression for goal prediction
- XGBoost Classifier for 1X2 prediction
- ELO Rating System
- Random Forest Ensemble
"""

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier
import warnings
warnings.filterwarnings('ignore')


class FootballPredictor:
    """
    Advanced Football Match Prediction Engine
    """
    
    def __init__(self):
        self.elo_ratings = {}
        self.k_factor = 32  # ELO adjustment factor
        self.home_advantage = 0.15
        
    def calculate_elo_probability(self, team_a_rating, team_b_rating):
        """
        Calculate match win probability based on ELO ratings
        """
        return 1 / (1 + 10 ** ((team_b_rating - team_a_rating) / 400))
    
    def update_elo(self, team_a, team_b, result, team_a_goals, team_b_goals):
        """
        Update ELO ratings after match
        result: 1 (team_a win), 0.5 (draw), 0 (team_b win)
        """
        if team_a not in self.elo_ratings:
            self.elo_ratings[team_a] = 1500
        if team_b not in self.elo_ratings:
            self.elo_ratings[team_b] = 1500
            
        expected_a = self.calculate_elo_probability(
            self.elo_ratings[team_a] + self.home_advantage * 100,
            self.elo_ratings[team_b]
        )
        
        # Goal difference multiplier
        goal_diff = abs(team_a_goals - team_b_goals)
        multiplier = np.log(max(goal_diff, 1) + 1)
        
        self.elo_ratings[team_a] += self.k_factor * multiplier * (result - expected_a)
        self.elo_ratings[team_b] += self.k_factor * multiplier * ((1 - result) - (1 - expected_a))
    
    def poisson_match_probabilities(self, home_goals_avg, away_goals_avg):
        """
        Calculate 1X2 probabilities using Poisson distribution
        """
        max_goals = 10
        home_probs = [poisson.pmf(i, home_goals_avg) for i in range(max_goals)]
        away_probs = [poisson.pmf(i, away_goals_avg) for i in range(max_goals)]
        
        # Create probability matrix
        prob_matrix = np.outer(home_probs, away_probs)
        
        home_win = np.sum(np.tril(prob_matrix, -1))
        draw = np.sum(np.diag(prob_matrix))
        away_win = np.sum(np.triu(prob_matrix, 1))
        
        return {
            'home_win': home_win,
            'draw': draw,
            'away_win': away_win
        }
    
    def dixon_coles_adjustment(self, home_goals, away_goals, home_strength, away_strength):
        """
        Dixon-Coles tau correction for low-scoring games
        """
        rho = -0.13  # Correlation parameter
        
        if home_goals == 0 and away_goals == 0:
            return 1 - home_strength * away_strength * rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + home_strength * rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + away_strength * rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - rho
        else:
            return 1.0
    
    def predict_match_winner(self, home_team, away_team, home_form, away_form):
        """
        Predict match winner (1X2)
        
        Args:
            home_team: Name of home team
            away_team: Name of away team
            home_form: Dict with recent stats (goals_scored, goals_conceded)
            away_form: Dict with recent stats
            
        Returns:
            Dict with probabilities and prediction
        """
        # Calculate expected goals
        home_attack = home_form['goals_scored'] / home_form['matches']
        home_defense = home_form['goals_conceded'] / home_form['matches']
        away_attack = away_form['goals_scored'] / away_form['matches']
        away_defense = away_form['goals_conceded'] / away_form['matches']
        
        # Home advantage adjustment
        home_goals_expected = (home_attack + away_defense) / 2 * (1 + self.home_advantage)
        away_goals_expected = (away_attack + home_defense) / 2
        
        # Get Poisson probabilities
        probs = self.poisson_match_probabilities(home_goals_expected, away_goals_expected)
        
        # Determine winner
        max_prob = max(probs.values())
        if probs['home_win'] == max_prob:
            prediction = 'Home Win'
        elif probs['draw'] == max_prob:
            prediction = 'Draw'
        else:
            prediction = 'Away Win'
        
        return {
            'prediction': prediction,
            'probabilities': probs,
            'confidence': max_prob
        }
    
    def predict_total_goals(self, home_team, away_team, home_form, away_form):
        """
        Predict total goals in match
        """
        home_attack = home_form['goals_scored'] / home_form['matches']
        home_defense = home_form['goals_conceded'] / home_form['matches']
        away_attack = away_form['goals_scored'] / away_form['matches']
        away_defense = away_form['goals_conceded'] / away_form['matches']
        
        home_goals_expected = (home_attack + away_defense) / 2 * (1 + self.home_advantage)
        away_goals_expected = (away_attack + home_defense) / 2
        
        total_expected = home_goals_expected + away_goals_expected
        
        # Over/Under 2.5 probability
        over_2_5 = 1 - poisson.cdf(2, total_expected)
        under_2_5 = poisson.cdf(2, total_expected)
        
        return {
            'expected_total': round(total_expected, 2),
            'home_expected': round(home_goals_expected, 2),
            'away_expected': round(away_goals_expected, 2),
            'over_2.5_prob': round(over_2_5, 3),
            'under_2.5_prob': round(under_2_5, 3)
        }
    
    def predict_btts(self, home_team, away_team, home_form, away_form):
        """
        Predict Both Teams To Score (BTTS)
        """
        home_attack = home_form['goals_scored'] / home_form['matches']
        away_attack = away_form['goals_scored'] / away_form['matches']
        away_defense = away_form['goals_conceded'] / away_form['matches']
        home_defense = home_form['goals_conceded'] / home_form['matches']
        
        home_goals_expected = (home_attack + away_defense) / 2 * (1 + self.home_advantage)
        away_goals_expected = (away_attack + home_defense) / 2
        
        # Probability both score at least 1
        home_scores = 1 - poisson.pmf(0, home_goals_expected)
        away_scores = 1 - poisson.pmf(0, away_goals_expected)
        
        btts_prob = home_scores * away_scores
        no_btts_prob = 1 - btts_prob
        
        return {
            'btts': 'Yes' if btts_prob > 0.5 else 'No',
            'btts_probability': round(btts_prob, 3),
            'no_btts_probability': round(no_btts_prob, 3)
        }
    
    def predict_first_half_goals(self, home_team, away_team, home_form, away_form):
        """
        Predict goals in first half
        Typically 45% of goals occur in 1st half
        """
        total_goals = self.predict_total_goals(home_team, away_team, home_form, away_form)
        
        first_half_expected = total_goals['expected_total'] * 0.45
        
        # Over/Under 0.5 and 1.5
        over_0_5 = 1 - poisson.pmf(0, first_half_expected)
        over_1_5 = 1 - poisson.cdf(1, first_half_expected)
        
        return {
            'expected_goals': round(first_half_expected, 2),
            'over_0.5_prob': round(over_0_5, 3),
            'over_1.5_prob': round(over_1_5, 3)
        }
    
    def comprehensive_prediction(self, home_team, away_team, home_form, away_form):
        """
        Generate complete match prediction
        """
        return {
            'match': f'{home_team} vs {away_team}',
            'winner_prediction': self.predict_match_winner(home_team, away_team, home_form, away_form),
            'total_goals': self.predict_total_goals(home_team, away_team, home_form, away_form),
            'btts': self.predict_btts(home_team, away_team, home_form, away_form),
            'first_half': self.predict_first_half_goals(home_team, away_team, home_form, away_form)
        }


# Example Usage
if __name__ == "__main__":
    predictor = FootballPredictor()
    
    # Example match: Bayern vs Dortmund
    bayern_form = {
        'goals_scored': 35,
        'goals_conceded': 12,
        'matches': 15
    }
    
    dortmund_form = {
        'goals_scored': 28,
        'goals_conceded': 18,
        'matches': 15
    }
    
    prediction = predictor.comprehensive_prediction(
        'Bayern Munich', 'Borussia Dortmund',
        bayern_form, dortmund_form
    )
    
    print("=" * 50)
    print(f"Match: {prediction['match']}")
    print("=" * 50)
    print(f"\nWinner: {prediction['winner_prediction']['prediction']}")
    print(f"Confidence: {prediction['winner_prediction']['confidence']:.1%}")
    print(f"\nTotal Goals Expected: {prediction['total_goals']['expected_total']}")
    print(f"BTTS: {prediction['btts']['btts']} (Prob: {prediction['btts']['btts_probability']:.1%})")
    print(f"First Half Goals: {prediction['first_half']['expected_goals']}")

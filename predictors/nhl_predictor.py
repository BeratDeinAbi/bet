"""
NHL Game Prediction Module

Implements:
- Poisson Model for goal prediction (Goals/60 metrics)
- Corsi/Fenwick advanced analytics
- Power Play efficiency modeling
- Team offensive/defensive strength ratings
"""

import numpy as np
import pandas as pd
from scipy.stats import poisson
import warnings
warnings.filterwarnings('ignore')


class NHLPredictor:
    """
    Advanced NHL Game Prediction Engine
    """
    
    def __init__(self):
        self.home_advantage = 0.12  # NHL home ice advantage
        self.league_avg_goals = 6.0  # NHL average total goals per game
    
    def calculate_expected_goals(self, team_stats, opponent_stats, is_home=True):
        """
        Calculate expected goals using advanced metrics
        
        Args:
            team_stats: Dict with goals_for_60, goals_against_60, corsi_for_pct, pp_pct
            opponent_stats: Dict with same metrics
            is_home: Boolean for home ice advantage
        
        Returns:
            Expected goals for the team
        """
        # Goals per 60 minutes (5v5)
        team_gf60 = team_stats.get('goals_for_60', 2.5)
        opp_ga60 = opponent_stats.get('goals_against_60', 2.5)
        
        # Baseline expected goals
        base_expected = (team_gf60 + opp_ga60) / 2
        
        # Corsi adjustment (possession metric)
        team_corsi = team_stats.get('corsi_for_pct', 50.0)
        corsi_adj = 1 + (team_corsi - 50) / 100  # +/- 10% adjustment
        
        # Power Play contribution (average 4 PP opportunities per game)
        pp_pct = team_stats.get('pp_pct', 20.0) / 100
        pp_goals_expected = 4 * pp_pct * 0.25  # 25% chance to score on PP
        
        # Home ice advantage
        if is_home:
            base_expected *= (1 + self.home_advantage)
        
        # Combine factors
        total_expected = (base_expected * corsi_adj) + pp_goals_expected
        
        return total_expected
    
    def predict_total_goals_regulation(self, home_team, away_team, home_stats, away_stats):
        """
        Predict total goals in regulation time (60 minutes)
        
        Args:
            home_team: Name of home team
            away_team: Name of away team
            home_stats: Dict with team statistics
            away_stats: Dict with team statistics
        
        Returns:
            Dict with total goals prediction
        """
        # Calculate expected goals for each team
        home_expected = self.calculate_expected_goals(home_stats, away_stats, is_home=True)
        away_expected = self.calculate_expected_goals(away_stats, home_stats, is_home=False)
        
        total_expected = home_expected + away_expected
        
        # Over/Under probabilities (common NHL totals: 5.5, 6.5)
        over_5_5 = 1 - poisson.cdf(5, total_expected)
        under_5_5 = poisson.cdf(5, total_expected)
        over_6_5 = 1 - poisson.cdf(6, total_expected)
        under_6_5 = poisson.cdf(6, total_expected)
        
        return {
            'total_expected': round(total_expected, 2),
            'home_expected': round(home_expected, 2),
            'away_expected': round(away_expected, 2),
            'over_5.5_prob': round(over_5_5, 3),
            'under_5.5_prob': round(under_5_5, 3),
            'over_6.5_prob': round(over_6_5, 3),
            'under_6.5_prob': round(under_6_5, 3)
        }
    
    def predict_team_goals(self, team_name, team_stats, opponent_stats, is_home=True):
        """
        Predict goals for a specific team
        
        Returns:
            Dict with team goal prediction and probabilities
        """
        expected_goals = self.calculate_expected_goals(team_stats, opponent_stats, is_home)
        
        # Goal range probabilities
        prob_0_goals = poisson.pmf(0, expected_goals)
        prob_1_goals = poisson.pmf(1, expected_goals)
        prob_2_goals = poisson.pmf(2, expected_goals)
        prob_3_goals = poisson.pmf(3, expected_goals)
        prob_4_plus = 1 - poisson.cdf(3, expected_goals)
        
        # Over/Under team totals
        over_2_5 = 1 - poisson.cdf(2, expected_goals)
        under_2_5 = poisson.cdf(2, expected_goals)
        over_3_5 = 1 - poisson.cdf(3, expected_goals)
        under_3_5 = poisson.cdf(3, expected_goals)
        
        return {
            'team': team_name,
            'expected_goals': round(expected_goals, 2),
            'most_likely_goals': int(np.floor(expected_goals)),
            'prob_0_goals': round(prob_0_goals, 3),
            'prob_1_goals': round(prob_1_goals, 3),
            'prob_2_goals': round(prob_2_goals, 3),
            'prob_3_goals': round(prob_3_goals, 3),
            'prob_4+_goals': round(prob_4_plus, 3),
            'over_2.5_prob': round(over_2_5, 3),
            'under_2.5_prob': round(under_2_5, 3),
            'over_3.5_prob': round(over_3_5, 3),
            'under_3.5_prob': round(under_3_5, 3)
        }
    
    def predict_game_winner(self, home_team, away_team, home_stats, away_stats):
        """
        Predict game winner based on expected goals
        """
        home_expected = self.calculate_expected_goals(home_stats, away_stats, is_home=True)
        away_expected = self.calculate_expected_goals(away_stats, home_stats, is_home=False)
        
        # Simulate game outcomes using Poisson
        max_goals = 10
        home_probs = [poisson.pmf(i, home_expected) for i in range(max_goals)]
        away_probs = [poisson.pmf(i, away_expected) for i in range(max_goals)]
        
        prob_matrix = np.outer(home_probs, away_probs)
        
        home_win_reg = np.sum(np.tril(prob_matrix, -1))  # Home scores more
        away_win_reg = np.sum(np.triu(prob_matrix, 1))   # Away scores more
        tie_reg = np.sum(np.diag(prob_matrix))            # Tied after regulation
        
        # In NHL, ties go to OT/SO - assume 50/50 split
        home_win_total = home_win_reg + (tie_reg * 0.5)
        away_win_total = away_win_reg + (tie_reg * 0.5)
        
        winner = home_team if home_win_total > away_win_total else away_team
        
        return {
            'prediction': winner,
            'home_win_prob': round(home_win_total, 3),
            'away_win_prob': round(away_win_total, 3),
            'regulation_tie_prob': round(tie_reg, 3),
            'confidence': round(max(home_win_total, away_win_total), 3)
        }
    
    def comprehensive_prediction(self, home_team, away_team, home_stats, away_stats):
        """
        Generate complete NHL game prediction
        """
        return {
            'matchup': f'{home_team} vs {away_team}',
            'winner': self.predict_game_winner(home_team, away_team, home_stats, away_stats),
            'total_goals': self.predict_total_goals_regulation(home_team, away_team, home_stats, away_stats),
            'home_team_goals': self.predict_team_goals(home_team, home_stats, away_stats, is_home=True),
            'away_team_goals': self.predict_team_goals(away_team, away_stats, home_stats, is_home=False)
        }


# Example Usage
if __name__ == "__main__":
    predictor = NHLPredictor()
    
    # Example: Colorado Avalanche vs Edmonton Oilers
    avalanche_stats = {
        'goals_for_60': 3.2,      # High offensive output
        'goals_against_60': 2.4,   # Solid defense
        'corsi_for_pct': 54.5,     # Good possession
        'pp_pct': 25.0             # Strong power play
    }
    
    oilers_stats = {
        'goals_for_60': 3.5,       # Elite offense (McDavid/Draisaitl)
        'goals_against_60': 2.8,   # Weaker defense
        'corsi_for_pct': 51.2,     # Average possession
        'pp_pct': 28.0             # Elite power play
    }
    
    prediction = predictor.comprehensive_prediction(
        'Colorado Avalanche', 'Edmonton Oilers',
        avalanche_stats, oilers_stats
    )
    
    print("=" * 60)
    print(f"NHL Game: {prediction['matchup']}")
    print("=" * 60)
    
    winner = prediction['winner']
    print(f"\nPredicted Winner: {winner['prediction']}")
    print(f"Confidence: {winner['confidence']:.1%}")
    
    total = prediction['total_goals']
    print(f"\nTotal Goals Expected (Regulation): {total['total_expected']}")
    print(f"Over 5.5: {total['over_5.5_prob']:.1%} | Under 5.5: {total['under_5.5_prob']:.1%}")
    print(f"Over 6.5: {total['over_6.5_prob']:.1%} | Under 6.5: {total['under_6.5_prob']:.1%}")
    
    home_goals = prediction['home_team_goals']
    away_goals = prediction['away_team_goals']
    print(f"\n{home_goals['team']}: {home_goals['expected_goals']} expected goals")
    print(f"  Most likely: {home_goals['most_likely_goals']} goals")
    print(f"\n{away_goals['team']}: {away_goals['expected_goals']} expected goals")
    print(f"  Most likely: {away_goals['most_likely_goals']} goals")

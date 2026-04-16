"""
Tennis Match Prediction Module

Implements:
- ELO-based match outcome prediction
- Surface-adjusted win probability
- Serve/Return statistics modeling
- Tiebreak probability calculation
- Set score closeness prediction
"""

import numpy as np
import pandas as pd
from scipy.stats import norm
import warnings
warnings.filterwarnings('ignore')


class TennisPredictor:
    """
    Advanced Tennis Match Prediction Engine
    """
    
    def __init__(self):
        self.elo_ratings = {}
        self.k_factor = 32
        
        # Surface adjustments
        self.surface_factors = {
            'hard': 1.0,
            'clay': 1.15,  # More variance on clay
            'grass': 0.90,  # Less variance on grass
            'indoor': 0.95
        }
    
    def calculate_elo_probability(self, rating_a, rating_b, surface='hard'):
        """
        Calculate win probability based on ELO with surface adjustment
        """
        surface_adj = self.surface_factors.get(surface, 1.0)
        rating_diff = (rating_a - rating_b) * surface_adj
        
        return 1 / (1 + 10 ** (-rating_diff / 400))
    
    def update_elo(self, player_a, player_b, result, importance=1.0):
        """
        Update ELO ratings
        result: 1 (player_a win), 0 (player_b win)
        importance: Grand Slam (1.5), Masters (1.2), ATP 250 (1.0)
        """
        if player_a not in self.elo_ratings:
            self.elo_ratings[player_a] = 1500
        if player_b not in self.elo_ratings:
            self.elo_ratings[player_b] = 1500
        
        expected_a = self.calculate_elo_probability(
            self.elo_ratings[player_a],
            self.elo_ratings[player_b]
        )
        
        k_adjusted = self.k_factor * importance
        
        self.elo_ratings[player_a] += k_adjusted * (result - expected_a)
        self.elo_ratings[player_b] += k_adjusted * ((1 - result) - (1 - expected_a))
    
    def predict_match_winner(self, player_a, player_b, player_a_stats, player_b_stats, surface='hard'):
        """
        Predict match winner with probability
        
        Args:
            player_a: Name of player A
            player_b: Name of player B
            player_a_stats: Dict with serve%, return%, recent_form
            player_b_stats: Dict with serve%, return%, recent_form
            surface: 'hard', 'clay', 'grass', or 'indoor'
        
        Returns:
            Dict with prediction and probabilities
        """
        # Get ELO-based probability
        elo_prob_a = self.calculate_elo_probability(
            player_a_stats.get('elo', 1500),
            player_b_stats.get('elo', 1500),
            surface
        )
        
        # Serve/Return model
        serve_a = player_a_stats.get('serve_win_pct', 0.65)
        serve_b = player_b_stats.get('serve_win_pct', 0.65)
        return_a = player_a_stats.get('return_win_pct', 0.35)
        return_b = player_b_stats.get('return_win_pct', 0.35)
        
        # Point win probability on serve
        p_a_serve = serve_a
        p_b_serve = serve_b
        
        # Game win probability (simplified)
        # Probability to win game on own serve
        g_a_serve = self._game_win_prob(p_a_serve)
        g_b_serve = self._game_win_prob(p_b_serve)
        
        # Set win probability (simplified model)
        set_prob_a = self._set_win_prob(g_a_serve, 1 - g_b_serve)
        
        # Combine ELO and serve/return model
        combined_prob_a = (elo_prob_a * 0.6 + set_prob_a * 0.4)
        combined_prob_b = 1 - combined_prob_a
        
        # Determine favorite
        if combined_prob_a > 0.65:
            favorite_status = 'Clear Favorite'
        elif combined_prob_a > 0.55:
            favorite_status = 'Slight Favorite'
        elif combined_prob_a >= 0.45:
            favorite_status = 'Even Match'
        else:
            favorite_status = 'Underdog'
        
        prediction = player_a if combined_prob_a > 0.5 else player_b
        
        return {
            'prediction': prediction,
            'player_a_prob': round(combined_prob_a, 3),
            'player_b_prob': round(combined_prob_b, 3),
            'favorite_status': favorite_status,
            'confidence': round(max(combined_prob_a, combined_prob_b), 3)
        }
    
    def _game_win_prob(self, p):
        """
        Probability of winning a game given point win probability p
        Using simplified model (not full Markov chain)
        """
        # Approximate formula
        return p**4 * (15 - 4*p - 10*p**2 / (1 - 2*p*(1-p)))
    
    def _set_win_prob(self, p_win_on_serve, p_win_on_return):
        """
        Probability of winning a set
        Simplified model
        """
        # Average game win probability
        avg_game_prob = (p_win_on_serve + p_win_on_return) / 2
        
        # Approximate set win (6 games, simplified)
        return avg_game_prob ** 6
    
    def predict_tiebreak_probability(self, player_a_stats, player_b_stats):
        """
        Predict probability of tiebreak in a set
        """
        serve_a = player_a_stats.get('serve_win_pct', 0.65)
        serve_b = player_b_stats.get('serve_win_pct', 0.65)
        
        # If both players hold serve well, tiebreak more likely
        avg_serve_strength = (serve_a + serve_b) / 2
        
        # Tiebreak probability increases with serve strength
        # Empirical model: strong servers -> more tiebreaks
        tiebreak_prob = 0.15 + (avg_serve_strength - 0.60) * 0.5
        tiebreak_prob = max(0.05, min(0.40, tiebreak_prob))  # Clamp to realistic range
        
        return {
            'tiebreak_probability': round(tiebreak_prob, 3),
            'no_tiebreak_probability': round(1 - tiebreak_prob, 3),
            'prediction': 'Likely' if tiebreak_prob > 0.25 else 'Unlikely'
        }
    
    def predict_set_closeness(self, player_a_stats, player_b_stats):
        """
        Predict whether sets will be close or one-sided
        """
        elo_a = player_a_stats.get('elo', 1500)
        elo_b = player_b_stats.get('elo', 1500)
        
        elo_diff = abs(elo_a - elo_b)
        
        # Determine set closeness based on rating difference
        if elo_diff < 50:
            prediction = 'Very Close Sets (7-6, 7-5)'
            closeness_score = 'High'
        elif elo_diff < 100:
            prediction = 'Competitive Sets (6-4, 7-5)'
            closeness_score = 'Medium'
        elif elo_diff < 200:
            prediction = 'Some Close Sets (6-3, 6-4)'
            closeness_score = 'Medium-Low'
        else:
            prediction = 'Likely One-Sided (6-2, 6-1)'
            closeness_score = 'Low'
        
        return {
            'prediction': prediction,
            'closeness_score': closeness_score,
            'elo_difference': elo_diff
        }
    
    def comprehensive_prediction(self, player_a, player_b, player_a_stats, player_b_stats, surface='hard'):
        """
        Generate complete tennis match prediction
        """
        return {
            'match': f'{player_a} vs {player_b}',
            'surface': surface,
            'winner_prediction': self.predict_match_winner(
                player_a, player_b, player_a_stats, player_b_stats, surface
            ),
            'tiebreak': self.predict_tiebreak_probability(player_a_stats, player_b_stats),
            'set_closeness': self.predict_set_closeness(player_a_stats, player_b_stats)
        }


# Example Usage
if __name__ == "__main__":
    predictor = TennisPredictor()
    
    # Example match: Alcaraz vs Sinner on Clay (Roland Garros)
    alcaraz_stats = {
        'elo': 2200,
        'serve_win_pct': 0.68,
        'return_win_pct': 0.38
    }
    
    sinner_stats = {
        'elo': 2150,
        'serve_win_pct': 0.66,
        'return_win_pct': 0.36
    }
    
    prediction = predictor.comprehensive_prediction(
        'Carlos Alcaraz', 'Jannik Sinner',
        alcaraz_stats, sinner_stats,
        surface='clay'
    )
    
    print("=" * 60)
    print(f"Match: {prediction['match']} ({prediction['surface'].upper()})")
    print("=" * 60)
    winner = prediction['winner_prediction']
    print(f"\nPredicted Winner: {winner['prediction']}")
    print(f"Confidence: {winner['confidence']:.1%}")
    print(f"Favorite Status: {winner['favorite_status']}")
    print(f"\nTiebreak Likelihood: {prediction['tiebreak']['prediction']}")
    print(f"Tiebreak Probability: {prediction['tiebreak']['tiebreak_probability']:.1%}")
    print(f"\nSet Closeness: {prediction['set_closeness']['prediction']}")

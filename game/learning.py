"""Machine Learning module for predictive player modeling.

Uses a hybrid Bayesian/Markovian approach to predict player moves 
based on historical transitions and behavioral features.
"""

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from game.models import PlayerAction, GameState

@dataclass
class Prediction:
    move: PlayerAction
    confidence: float  # 0.0 to 1.0
    probabilities: Dict[PlayerAction, float]

class PlayerPredictor:
    """Online learning model that predicts player behavior patterns."""

    def __init__(self, learning_rate: float = 0.2):
        self.learning_rate = learning_rate
        # Markov Transitions: (prev_player, prev_ai) -> counts for {SPLIT, STEAL}
        self.transitions: Dict[Tuple[str, str], Dict[str, float]] = {}
        # Global bias counts
        self.global_counts = {"SPLIT": 1.0, "STEAL": 1.0}
        self.total_rounds = 0

    def update(self, player_move: PlayerAction, prev_player_move: PlayerAction = None, prev_ai_move: PlayerAction = None):
        """Update model weights based on the actual observed move."""
        self.total_rounds += 1
        m_type = player_move.value
        
        # Update global bias
        self.global_counts[m_type] += 1.0
        
        # Update Markov transitions
        if prev_player_move and prev_ai_move:
            key = (prev_player_move.value, prev_ai_move.value)
            if key not in self.transitions:
                self.transitions[key] = {"SPLIT": 0.5, "STEAL": 0.5}
            
            # Apply learning rate to the count increment
            self.transitions[key][m_type] += (1.0 + self.learning_rate)

    def predict(self, game_state: GameState, recent_sentiment: float = 0.0) -> Prediction:
        """
        Generate a probabilistic prediction for the next player move.
        
        recent_sentiment: -1.0 (hostile) to 1.0 (cooperative)
        """
        # 1. Base probabilities from global bias
        total_global = sum(self.global_counts.values())
        p_split = self.global_counts["SPLIT"] / total_global
        p_steal = self.global_counts["STEAL"] / total_global
        
        # 2. Markov refinement if we have history
        if game_state.history:
            last = game_state.history[-1]
            key = (last.player_action.value, last.opponent_action.value)
            if key in self.transitions:
                counts = self.transitions[key]
                t_sum = sum(counts.values())
                p_split = (p_split * 0.4) + (counts["SPLIT"] / t_sum * 0.6)
                p_steal = (p_steal * 0.4) + (counts["STEAL"] / t_sum * 0.6)

        # 3. Feature-based adjustments (Linear Logits)
        # We simulate a Logistic Regression here
        logit_split = 0.0
        
        # Trust feature (Weight: 2.5)
        # Trust score 0-100 mapped to -1 to 1
        trust_norm = (game_state.trust_score - 50) / 50.0
        logit_split += trust_norm * 2.5
        
        # Sentiment feature (Weight: 1.5)
        logit_split += recent_sentiment * 1.5
        
        # Endgame feature (Weight: -2.0 for Split)
        # As we approach the last round, people tend to steal
        if game_state.total_rounds > 1:
            progress = game_state.current_round / game_state.total_rounds
            if progress > 0.8:
                logit_split -= 2.0 * progress

        # Convert logit to probability change (Sigmoid)
        p_feature_split = 1.0 / (1.0 + math.exp(-logit_split))
        
        # Ensemble the models (Markov + Features)
        final_p_split = (p_split * 0.5) + (p_feature_split * 0.5)
        final_p_steal = 1.0 - final_p_split
        
        # Determine confidence based on entropy (simplified)
        confidence = abs(final_p_split - 0.5) * 2.0
        # Boost confidence slightly as we see more rounds
        confidence = min(0.99, confidence + (min(5, self.total_rounds) * 0.05))
        
        move = PlayerAction.SPLIT if final_p_split >= 0.5 else PlayerAction.STEAL
        
        return Prediction(
            move=move,
            confidence=confidence,
            probabilities={
                PlayerAction.SPLIT: final_p_split,
                PlayerAction.STEAL: final_p_steal
            }
        )

"""Data models for game state, round results, and player actions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class PlayerAction(Enum):
    """The two possible actions a player can take."""
    SPLIT = "SPLIT"
    STEAL = "STEAL"


@dataclass
class RoundResult:
    """Outcome of a single round."""
    round_number: int
    player_action: PlayerAction
    opponent_action: PlayerAction
    player_reward: int
    opponent_reward: int
    pot: int
    negotiation_log: list[str] = field(default_factory=list)
    trust_before: int = 50
    trust_after: int = 50
    trust_delta: int = 0
    betrayal_flag: bool = False
    trust_signals: list[str] = field(default_factory=list)
    ai_personality: str = "manipulative"
    ai_intended_action: str = "SPLIT_LEAN"
    ai_confidence: float = 0.5
    ai_risk_level: str = "MEDIUM"
    ai_steal_probability: float = 0.5
    ai_memory_betrayal_rate: float = 0.0
    ai_memory_player_consistency: float = 0.5

    @property
    def outcome_label(self) -> str:
        """Human-readable outcome description."""
        p = self.player_action.value
        o = self.opponent_action.value
        return f"{p} / {o}"


@dataclass
class GameState:
    """Full state of the game across all rounds."""
    total_rounds: int
    pot_per_round: int
    current_round: int = 1
    player_score: int = 0
    opponent_score: int = 0
    trust_score: int = 50
    betrayal_count: int = 0
    history: list[RoundResult] = field(default_factory=list)
    trust_history: list[int] = field(default_factory=lambda: [50])

    @property
    def is_game_over(self) -> bool:
        return self.current_round > self.total_rounds

    def record_round(self, result: RoundResult) -> None:
        """Record a round result and update scores."""
        self.player_score += result.player_reward
        self.opponent_score += result.opponent_reward
        self.trust_score = result.trust_after
        if result.betrayal_flag:
            self.betrayal_count += 1
        self.history.append(result)
        self.trust_history.append(result.trust_after)
        self.current_round += 1

    def get_player_split_rate(self) -> float:
        """Fraction of rounds the player chose SPLIT."""
        if not self.history:
            return 0.0
        splits = sum(1 for r in self.history if r.player_action == PlayerAction.SPLIT)
        return splits / len(self.history)

    def get_opponent_split_rate(self) -> float:
        """Fraction of rounds the opponent chose SPLIT."""
        if not self.history:
            return 0.0
        splits = sum(1 for r in self.history if r.opponent_action == PlayerAction.SPLIT)
        return splits / len(self.history)

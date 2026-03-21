"""Phase 3 strategy engine for AI action tendency and confidence."""

from dataclasses import dataclass

from game.constants import PERSONALITIES


@dataclass
class StrategyAssessment:
    """Current strategic assessment before sampling the final action."""

    intended_action: str
    steal_probability: float
    confidence: float
    risk_level: str


class StrategyEngine:
    """Computes AI action tendency from trust, history, and personality."""

    def __init__(self, personality: str = "manipulative"):
        if personality not in PERSONALITIES:
            personality = "manipulative"
        self.personality = personality
        self.profile = PERSONALITIES[personality]

    def assess(
        self,
        trust_score: int,
        betrayal_count: int,
        current_round: int,
        total_rounds: int,
        memory_snapshot: dict | None = None,
    ) -> StrategyAssessment:
        memory_snapshot = memory_snapshot or {}

        base = float(self.profile["base_steal_probability"])
        risk_tolerance = float(self.profile["risk_tolerance"])

        trust_component = (50 - trust_score) / 100.0
        betrayal_component = min(0.20, betrayal_count * 0.05)
        endgame_component = 0.06 if total_rounds > 1 and current_round == total_rounds else 0.0

        memory_steal_rate = float(memory_snapshot.get("player_steal_rate", 0.0))
        memory_split_rate = float(memory_snapshot.get("player_split_rate", 0.0))
        memory_consistency = float(memory_snapshot.get("player_consistency", 0.5))
        steal_streak = int(memory_snapshot.get("player_steal_streak", 0))
        split_streak = int(memory_snapshot.get("player_split_streak", 0))
        confidence_trend = float(memory_snapshot.get("confidence_trend", 0.0))

        pattern_pressure = (memory_steal_rate - memory_split_rate) * 0.20
        streak_pressure = min(0.15, steal_streak * 0.04) - min(0.10, split_streak * 0.03)
        consistency_pressure = (memory_consistency - 0.5) * (0.08 if memory_steal_rate > 0.5 else -0.08)

        raw_probability = (
            base
            + trust_component * (0.7 + risk_tolerance * 0.3)
            + betrayal_component
            + endgame_component * risk_tolerance
            + pattern_pressure
            + streak_pressure
            + consistency_pressure
        )
        steal_probability = max(0.05, min(0.95, raw_probability))

        confidence = 0.50 + abs(steal_probability - 0.50)
        confidence += min(0.12, steal_streak * 0.03)
        confidence += min(0.06, split_streak * 0.02)
        confidence += max(-0.06, min(0.06, confidence_trend))
        confidence = min(0.99, max(0.51, confidence))

        if steal_probability >= 0.70:
            risk_level = "HIGH"
        elif steal_probability >= 0.40:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        intended_action = "STEAL_LEAN" if steal_probability >= 0.50 else "SPLIT_LEAN"

        return StrategyAssessment(
            intended_action=intended_action,
            steal_probability=steal_probability,
            confidence=confidence,
            risk_level=risk_level,
        )

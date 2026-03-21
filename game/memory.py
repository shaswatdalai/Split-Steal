"""Adaptive AI memory for Phase 6 learning behavior."""

from collections import deque

from game.models import PlayerAction


class AIMemory:
    """Tracks patterns across rounds so AI can adapt over time."""

    def __init__(self):
        self.player_actions: list[PlayerAction] = []
        self.ai_actions: list[PlayerAction] = []
        self.trust_scores: list[int] = [50]
        self.confidence_scores: list[float] = []
        self.betrayal_rounds: int = 0
        self.player_steal_streak: int = 0
        self.player_split_streak: int = 0
        self.recent_player_messages: deque[str] = deque(maxlen=12)
        self.recent_ai_messages: deque[str] = deque(maxlen=12)

    def observe_player_message(self, message: str) -> None:
        text = (message or "").strip()
        if text:
            self.recent_player_messages.append(text)

    def observe_ai_message(self, message: str) -> None:
        text = (message or "").strip()
        if text:
            self.recent_ai_messages.append(text)

    def update_after_round(
        self,
        player_action: PlayerAction,
        ai_action: PlayerAction,
        trust_score: int,
        confidence: float,
        betrayal_flag: bool,
    ) -> None:
        self.player_actions.append(player_action)
        self.ai_actions.append(ai_action)
        self.trust_scores.append(trust_score)
        self.confidence_scores.append(confidence)

        if betrayal_flag:
            self.betrayal_rounds += 1

        if player_action == PlayerAction.STEAL:
            self.player_steal_streak += 1
            self.player_split_streak = 0
        else:
            self.player_split_streak += 1
            self.player_steal_streak = 0

    def snapshot(self) -> dict:
        rounds = len(self.player_actions)
        steals = sum(1 for action in self.player_actions if action == PlayerAction.STEAL)
        splits = rounds - steals

        player_steal_rate = steals / rounds if rounds else 0.0
        player_split_rate = splits / rounds if rounds else 0.0
        betrayal_rate = self.betrayal_rounds / rounds if rounds else 0.0

        if rounds >= 2:
            recent_window = self.player_actions[-3:]
            consistency = max(
                recent_window.count(PlayerAction.SPLIT),
                recent_window.count(PlayerAction.STEAL),
            ) / len(recent_window)
        else:
            consistency = 0.5

        if len(self.confidence_scores) >= 4:
            recent_avg = sum(self.confidence_scores[-2:]) / 2
            previous_avg = sum(self.confidence_scores[-4:-2]) / 2
            confidence_trend = recent_avg - previous_avg
        else:
            confidence_trend = 0.0

        return {
            "rounds_seen": rounds,
            "betrayal_count": self.betrayal_rounds,
            "betrayal_rate": betrayal_rate,
            "player_steal_rate": player_steal_rate,
            "player_split_rate": player_split_rate,
            "player_consistency": consistency,
            "player_steal_streak": self.player_steal_streak,
            "player_split_streak": self.player_split_streak,
            "confidence_trend": confidence_trend,
            "recent_player_messages": list(self.recent_player_messages),
            "recent_ai_messages": list(self.recent_ai_messages),
        }

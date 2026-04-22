"""Player abstractions — base class, human player, and random AI."""

import random
from abc import ABC, abstractmethod
from collections import deque

from game.models import PlayerAction, GameState, RoundResult
from game.dialogue import DialogueContext, DialogueEngine
from game.intent import IntentClassifier
from game.llm import LLMClient, LLMConfig
from game.memory import AIMemory
from game.strategy import StrategyEngine, StrategyAssessment
from game.learning import PlayerPredictor


class Player(ABC):
    """Abstract base class for all players."""

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def get_action(self, game_state: GameState) -> PlayerAction:
        """Choose SPLIT or STEAL."""
        ...

    @abstractmethod
    def negotiate(self, game_state: GameState, opponent_message: str | None) -> str | None:
        """Send a negotiation message. Return None to end negotiation."""
        ...

    def notify_result(self, result) -> None:
        """Called after each round with the result. Override for learning."""
        pass

    def get_strategy_snapshot(self) -> dict | None:
        """Optional strategy metadata for display/debugging."""
        return None


class HumanPlayer(Player):
    """Player controlled via console input."""

    def __init__(self, name: str = "You"):
        super().__init__(name)

    def get_action(self, game_state: GameState) -> PlayerAction:
        """Prompt the human to choose Split or Steal."""
        while True:
            choice = input("\n  🎯 Your decision — [S]plit or S[t]eal? ").strip().lower()
            if choice in ("s", "split"):
                return PlayerAction.SPLIT
            elif choice in ("t", "steal", "st"):
                return PlayerAction.STEAL
            else:
                print("  ⚠  Please enter 'S' for Split or 'T' for Steal.")

    def negotiate(self, game_state: GameState, opponent_message: str | None) -> str | None:
        """Let the human type a negotiation message."""
        msg = input("  You: ").strip()
        if not msg or msg.lower() in ("skip", "pass", "done", ""):
            return None
        return msg


class RandomAI(Player):
    """AI player with personality-driven probabilistic strategy."""

    def __init__(
        self,
        name: str = "AI Opponent",
        personality: str = "manipulative",
        use_llm: bool = False,
        llm_model: str = "llama-3.1-8b-instant",
        llm_timeout_seconds: float = 8.0,
    ):
        super().__init__(name)
        self.strategy_engine = StrategyEngine(personality=personality)
        llm_config = LLMConfig(
            enabled=use_llm,
            model=llm_model,
            timeout_seconds=llm_timeout_seconds,
        )
        self.llm_client = LLMClient(llm_config)
        self.dialogue_engine = DialogueEngine(llm_client=self.llm_client, use_llm=use_llm)
        self.use_llm = use_llm
        self.memory = AIMemory()
        self.predictor = PlayerPredictor()
        self._last_assessment: StrategyAssessment | None = None
        self._assessment_signature: tuple[int, int, int, int] | None = None
        self._round_number_context: int | None = None
        self._round_ai_messages: deque[str] = deque(maxlen=8)
        self._round_player_messages: deque[str] = deque(maxlen=8)

    def _ensure_round_assessment(self, game_state: GameState) -> StrategyAssessment:
        if self._round_number_context != game_state.current_round:
            self._round_number_context = game_state.current_round
            self._round_ai_messages.clear()
            self._round_player_messages.clear()

        signature = (
            game_state.current_round,
            game_state.trust_score,
            game_state.betrayal_count,
            len(self.memory.player_actions),
        )

        if self._last_assessment is None or self._assessment_signature != signature:
            self._last_assessment = self.strategy_engine.assess(
                trust_score=game_state.trust_score,
                betrayal_count=game_state.betrayal_count,
                current_round=game_state.current_round,
                total_rounds=game_state.total_rounds,
                memory_snapshot=self.memory.snapshot(),
            )
            self._assessment_signature = signature
        return self._last_assessment

    def get_action(self, game_state: GameState) -> PlayerAction:
        """Choose final action based on adaptive strategy confidence."""
        self._last_state = game_state
        assessment = self._ensure_round_assessment(game_state)
        steal_probability = assessment.steal_probability
        confidence = assessment.confidence
        opportunistic_steal = self._opportunistic_steal_chance(game_state)

        if confidence >= 0.82:
            if assessment.intended_action.startswith("STEAL"):
                return PlayerAction.STEAL
            return PlayerAction.STEAL if random.random() < opportunistic_steal else PlayerAction.SPLIT

        if confidence <= 0.58:
            blended_probability = 0.50 + (steal_probability - 0.50) * 0.50
        else:
            blended_probability = steal_probability

        blended_probability = max(opportunistic_steal, blended_probability)

        return PlayerAction.STEAL if random.random() < blended_probability else PlayerAction.SPLIT

    def _opportunistic_steal_chance(self, game_state: GameState) -> float:
        base_floor = {
            "cooperative": 0.02,
            "manipulative": 0.08,
            "aggressive": 0.12,
        }.get(self.strategy_engine.personality, 0.06)

        if game_state.trust_score >= 75:
            base_floor += 0.03
        if game_state.trust_score >= 90:
            base_floor += 0.04
        if game_state.current_round == game_state.total_rounds:
            base_floor += 0.05

        return min(0.30, base_floor)

    def get_strategy_snapshot(self) -> dict | None:
        """Return the current strategic state including ML predictions."""
        if self._last_assessment is None:
            return None

        # Get ML prediction
        prediction = self.predictor.predict(
            game_state=self._last_state, 
            recent_sentiment=0.0 # Could be derived from intent analysis
        ) if hasattr(self, '_last_state') and self._last_state else None

        return {
            "personality": self.strategy_engine.personality,
            "intended_action": self._last_assessment.intended_action,
            "confidence": self._last_assessment.confidence,
            "risk_level": self._last_assessment.risk_level,
            "steal_probability": self._last_assessment.steal_probability,
            "prediction": {
                "move": prediction.move.value if prediction else "UNKNOWN",
                "confidence": prediction.confidence if prediction else 0.0
            } if prediction else None,
            "memory": self.memory.snapshot(),
            "llm_enabled": self.use_llm,
            "llm_active": self.llm_client.available,
        }

    def negotiate(self, game_state: GameState, opponent_message: str | None) -> str | None:
        """Generate strategy-constrained negotiation dialogue."""
        assessment = self._ensure_round_assessment(game_state)

        if opponent_message:
            self._round_player_messages.append(opponent_message)
            self.memory.observe_player_message(opponent_message)

            quick_reply = self._minimal_reply_for_low_content(opponent_message)
            if quick_reply is not None:
                if quick_reply:
                    self._round_ai_messages.append(quick_reply)
                    self.memory.observe_ai_message(quick_reply)
                return quick_reply

        # Always open and, in LLM mode, always respond to user follow-ups.
        if (
            opponent_message is not None
            and not self.use_llm
            and random.random() < 0.15
        ):
            return None

        context = DialogueContext(
            personality=self.strategy_engine.personality,
            intended_action=assessment.intended_action,
            confidence=assessment.confidence,
            risk_level=assessment.risk_level,
            trust_score=game_state.trust_score,
            opponent_message=opponent_message,
            recent_ai_messages=list(self._round_ai_messages) + self.memory.snapshot().get("recent_ai_messages", []),
            recent_player_messages=list(self._round_player_messages) + self.memory.snapshot().get("recent_player_messages", []),
        )
        message = self.dialogue_engine.generate(context)
        if message:
            self._round_ai_messages.append(message)
            self.memory.observe_ai_message(message)
        return message

    def _minimal_reply_for_low_content(self, opponent_message: str) -> str | None:
        text = (opponent_message or "").strip().lower()
        if not text:
            return None
        if "?" in text:
            return None

        token = "".join(ch for ch in text if ch.isalnum())
        if not token:
            return ""

        positive_ack = {
            "yes", "y", "yeah", "yep", "yup", "ok", "okay", "k", "kk", "sure", "fine", "alright"
        }
        negative_ack = {"no", "n", "nah", "nope"}
        soft_ack = {"maybe", "idk", "hmm", "huh"}

        if token in positive_ack:
            return "" if random.random() < 0.75 else random.choice(["Okay.", "Good.", "Nice."])

        if token in negative_ack:
            return "" if random.random() < 0.60 else random.choice(["Noted.", "Your call.", "Fine."])

        if token in soft_ack:
            return random.choice(["Maybe.", "Alright.", "Hm."])

        words = [w for w in text.replace(".", " ").replace("!", " ").split() if w]
        if len(words) <= 2 and all(len(word) <= 4 for word in words):
            return None

        return None

    def notify_result(self, result) -> None:
        """Update long-term memory and ML predictor after each round."""
        self.memory.update_after_round(
            player_action=result.player_action,
            ai_action=result.opponent_action,
            trust_score=result.trust_after,
            confidence=result.ai_confidence,
            betrayal_flag=result.betrayal_flag,
        )
        
        # Update ML predictor
        history = self.memory.player_actions
        prev_p = history[-2] if len(history) >= 2 else None
        prev_ai = self.memory.ai_actions[-2] if len(self.memory.ai_actions) >= 2 else None
        
        self.predictor.update(
            player_move=result.player_action,
            prev_player_move=prev_p,
            prev_ai_move=prev_ai
        )

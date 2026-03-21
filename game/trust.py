"""Trust evaluation logic for Phase 2.

This module tracks how trustworthy the human player appears to the AI
using simple heuristics and betrayal detection.
"""

from dataclasses import dataclass
import re

from game.intent import IntentClassifier
from game.llm import LLMClient
from game.models import PlayerAction


@dataclass
class TrustUpdate:
    """Result of a trust score update after one round."""

    previous_score: int
    new_score: int
    delta: int
    betrayed_promise: bool
    signals: list[str]


@dataclass
class LiveTrustUpdate:
    """Immediate trust adjustment from a single chat message."""

    previous_score: int
    new_score: int
    delta: int
    signals: list[str]


class TrustEvaluator:
    """Heuristic trust evaluator for the player's behavior."""

    def __init__(
        self,
        initial_score: int = 50,
        llm_client: LLMClient | None = None,
        use_llm: bool = False,
    ):
        self._score = max(0, min(100, initial_score))
        self._betrayal_count = 0
        self._consecutive_steals = 0
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.intent_classifier = IntentClassifier(llm_client=llm_client, use_llm=use_llm)

    @property
    def score(self) -> int:
        return self._score

    @property
    def betrayal_count(self) -> int:
        return self._betrayal_count

    def evaluate_message(self, player_message: str, round_number: int = 1) -> LiveTrustUpdate:
        """Apply context-aware trust update from one negotiation message."""
        text = (player_message or "").strip()
        previous = self._score
        if not text:
            return LiveTrustUpdate(
                previous_score=previous,
                new_score=previous,
                delta=0,
                signals=["empty message"],
            )

        analysis = self.intent_classifier.classify(player_message)
        intent_delta_map = {
            "cooperative": 3,
            "threatening": -4,
            "deceptive": -5,
            "uncertain": -1,
        }
        delta = intent_delta_map.get(analysis.intent, 0)
        delta += analysis.heuristic_delta
        delta += analysis.llm_delta

        lowered = text.lower()
        explicit_no_steal = self.intent_classifier._is_explicit_no_steal(lowered)

        if re.search(r"\b(steal|betray|take all)\b", lowered) and not explicit_no_steal:
            delta -= 3
            signals = ["explicit steal/betray threat"]
        else:
            signals = []

        if re.search(r"\b(i|we)\s+(will|gonna|going to)\s+steal\b", lowered) and not explicit_no_steal:
            delta -= 2
            signals.append("declared steal intent")

        if re.search(r"\b(let me|allow me)\s+steal\b", lowered) and not explicit_no_steal:
            delta -= 2
            signals.append("asked to steal")

        # Grace-round logic: soften opening penalties for better fairness.
        if round_number == 1 and delta < 0:
            delta = int(delta * 0.5)

        delta = max(-6, min(6, delta))
        signals = [f"intent={analysis.intent}"] + analysis.signals + signals

        new_score = max(0, min(100, previous + delta))
        self._score = new_score

        return LiveTrustUpdate(
            previous_score=previous,
            new_score=new_score,
            delta=new_score - previous,
            signals=signals,
        )

    def evaluate_round(
        self,
        player_action: PlayerAction,
        player_messages: list[str],
        previous_player_action: PlayerAction | None,
    ) -> TrustUpdate:
        """Update trust using current round behavior and return details."""
        previous = self._score
        delta = 0
        signals: list[str] = []

        promised_split = any(self._looks_like_split_promise(msg) for msg in player_messages)

        if player_action == PlayerAction.SPLIT:
            delta += 8
            signals.append("chose split")
            self._consecutive_steals = 0
        else:
            delta -= 10
            signals.append("chose steal")
            self._consecutive_steals += 1

        if previous_player_action is not None and previous_player_action == player_action:
            delta += 2
            signals.append("consistent behavior")

        if self._consecutive_steals >= 2:
            extra_penalty = min(12, 4 * (self._consecutive_steals - 1))
            delta -= extra_penalty
            signals.append(f"repeat steals x{self._consecutive_steals}")

        betrayed_promise = promised_split and player_action == PlayerAction.STEAL
        if betrayed_promise:
            delta -= 20
            self._betrayal_count += 1
            signals.append("betrayed split promise")
        elif promised_split and player_action == PlayerAction.SPLIT:
            delta += 6
            signals.append("kept split promise")

        if self._betrayal_count >= 2 and player_action == PlayerAction.STEAL:
            delta -= 5
            signals.append("pattern of betrayal")

        if self.use_llm and self.llm_client is not None:
            llm_result = self.llm_client.trust_adjustment(
                player_messages=player_messages,
                player_action=player_action.value,
            )
            if llm_result is not None:
                llm_delta, llm_signal = llm_result
                delta += llm_delta
                if llm_delta != 0:
                    signals.append(f"llm: {llm_signal}")

        self._score = max(0, min(100, self._score + delta))

        return TrustUpdate(
            previous_score=previous,
            new_score=self._score,
            delta=self._score - previous,
            betrayed_promise=betrayed_promise,
            signals=signals,
        )

    @staticmethod
    def _looks_like_split_promise(message: str) -> bool:
        text = message.strip().lower()
        if not text:
            return False

        split_words = ("split", "share")
        if not any(word in text for word in split_words):
            return False

        negation_or_hedge_patterns = (
            r"\bdon'?t\s+promise\b",
            r"\bdo\s+not\s+promise\b",
            r"\bwon'?t\s+promise\b",
            r"\bwill\s+not\s+promise\b",
            r"\bnot\s+promis",
            r"\bno\s+deal\b",
            r"\bmaybe\s+(?:split|share)\b",
            r"\bmight\s+(?:split|share)\b",
            r"\bcould\s+(?:split|share)\b",
        )
        if any(re.search(pattern, text) for pattern in negation_or_hedge_patterns):
            return False

        strong_commitment_patterns = (
            r"\b(i|we)\s+(promise|swear|guarantee|commit)\s+to\s+(split|share)\b",
            r"\b(i|we)\s+(will|gonna|going\s+to)\s+(split|share)\b",
            r"\byou\s+can\s+trust\s+me\b.*\b(split|share)\b",
        )
        if any(re.search(pattern, text) for pattern in strong_commitment_patterns):
            return True

        return False

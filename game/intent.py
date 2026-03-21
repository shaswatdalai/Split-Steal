"""Intent analysis for context-aware trust updates."""

from __future__ import annotations

from dataclasses import dataclass
import re

from game.llm import LLMClient


@dataclass
class IntentAnalysis:
    intent: str
    confidence: float
    deception_risk: float
    heuristic_delta: int
    llm_delta: int
    signals: list[str]


class IntentClassifier:
    """Hybrid intent classifier: heuristic stability + optional LLM understanding."""

    def __init__(self, llm_client: LLMClient | None = None, use_llm: bool = False):
        self.llm_client = llm_client
        self.use_llm = use_llm

    def classify(self, message: str, recent_history: list[str] | None = None) -> IntentAnalysis:
        text = (message or "").strip()
        lowered = text.lower()
        recent_history = recent_history or []

        heuristic_intent, heuristic_confidence, heuristic_delta, heuristic_signals = self._heuristic_intent(lowered)

        llm_intent = None
        llm_confidence = 0.0
        llm_deception = 0.0
        llm_signals: list[str] = []
        llm_delta = 0

        if self.use_llm and self.llm_client is not None:
            llm_result = self.llm_client.analyze_intent(
                message=text,
                recent_history=recent_history,
            )
            if llm_result is not None:
                llm_intent, llm_confidence, llm_deception = llm_result
                llm_signals.append(f"llm intent={llm_intent}")
                if llm_intent == "cooperative":
                    llm_delta += 1
                elif llm_intent == "threatening":
                    llm_delta -= 2
                elif llm_intent == "deceptive":
                    llm_delta -= 2
                elif llm_intent == "uncertain":
                    llm_delta -= 1

        final_intent = heuristic_intent
        final_confidence = heuristic_confidence
        deception_risk = max(0.0, min(1.0, llm_deception if llm_intent else 0.2 if heuristic_intent == "deceptive" else 0.0))

        if llm_intent and llm_confidence >= 0.55:
            final_intent = llm_intent
            final_confidence = llm_confidence

        # Safety guard: explicit steal/betray wording must never resolve to cooperative.
        explicit_steal_or_betray = bool(
            re.search(r"\b(steal|betray|take all|cheat|lie)\b", lowered)
        ) and not self._is_explicit_no_steal(lowered)
        if explicit_steal_or_betray and final_intent == "cooperative":
            final_intent = "threatening"
            final_confidence = max(final_confidence, 0.75)
            heuristic_signals.append("override: explicit steal/betray language")

        # Hard negation safety for common failure cases (e.g., "I won't steal")
        if self._is_explicit_no_steal(lowered):
            final_intent = "cooperative"
            final_confidence = max(final_confidence, 0.8)
            heuristic_signals.append("explicit anti-steal commitment")

        return IntentAnalysis(
            intent=final_intent,
            confidence=final_confidence,
            deception_risk=deception_risk,
            heuristic_delta=heuristic_delta,
            llm_delta=llm_delta,
            signals=heuristic_signals + llm_signals,
        )

    def _heuristic_intent(self, lowered: str) -> tuple[str, float, int, list[str]]:
        signals: list[str] = []
        if not lowered:
            return "uncertain", 0.2, 0, ["empty message"]

        if self._is_explicit_no_steal(lowered):
            return "cooperative", 0.85, +2, ["negation-aware cooperative phrase"]

        if re.search(r"\b(i|we)\s+(will|am going to|gonna)\s+steal\b", lowered):
            return "threatening", 0.9, -3, ["explicit steal intent"]

        if re.search(r"\b(might|maybe|could)\s+steal\b", lowered):
            return "uncertain", 0.7, -1, ["hedged steal intent"]

        if re.search(r"\btrust me\b", lowered) and re.search(r"\b(split|share)\b", lowered):
            return "deceptive", 0.6, -1, ["possibly manipulative promise"]

        if re.search(r"\b(split|share|cooperate|fair|together)\b", lowered):
            signals.append("cooperative language")
            return "cooperative", 0.65, +1, signals

        if re.search(r"\b(steal|betray|cheat|lie)\b", lowered):
            signals.append("threat language")
            return "threatening", 0.65, -2, signals

        return "uncertain", 0.5, 0, ["neutral/unclear intent"]

    @staticmethod
    def _is_explicit_no_steal(lowered: str) -> bool:
        patterns = (
            r"\b(i|we)\s+(won't|will not|dont|don't|do not|never)\s+steal\b",
            r"\bnot\s+going\s+to\s+steal\b",
            r"\bdon't\s+steal\b",
            r"\bdo\s+not\s+steal\b",
        )
        return any(re.search(pattern, lowered) for pattern in patterns)

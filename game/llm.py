"""Optional LLM integration helpers for Phase 5.

Uses Groq (OpenAI-compatible) chat completions when enabled and API key is present.
Falls back gracefully when unavailable or on request failures.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from urllib import error, request
import time


@dataclass
class LLMConfig:
    enabled: bool = False
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 8.0
    temperature: float = 0.9
    retries: int = 1


class LLMClient:
    """Small Groq-compatible client for optional Phase 5 behavior."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.provider = "groq"
        self.api_key = (
            os.getenv("GROQ_API_KEY", "").strip()
            or os.getenv("GROK_API_KEY", "").strip()
        )
        self.base_url = (
            os.getenv("GROQ_BASE_URL", "").strip()
            or os.getenv("GROK_BASE_URL", "").strip()
            or "https://api.groq.com/openai/v1"
        ).rstrip("/")

    @staticmethod
    def mask_secret(secret: str, keep_prefix: int = 4, keep_suffix: int = 4) -> str:
        """Mask a secret for safe logs: keep only small prefix/suffix."""
        value = (secret or "").strip()
        if not value:
            return ""
        if len(value) <= keep_prefix + keep_suffix:
            return "*" * len(value)
        return f"{value[:keep_prefix]}{'*' * (len(value) - keep_prefix - keep_suffix)}{value[-keep_suffix:]}"

    def safe_debug_snapshot(self) -> dict[str, str | bool]:
        """Return diagnostic metadata without exposing raw secrets."""
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "available": self.available,
            "api_key_masked": self.mask_secret(self.api_key),
            "model": self.config.model,
        }

    @property
    def available(self) -> bool:
        return self.config.enabled and bool(self.api_key)

    def generate_dialogue(
        self,
        *,
        personality: str,
        intended_action: str,
        confidence: float,
        risk_level: str,
        trust_score: int,
        opponent_message: str | None,
        recent_ai_messages: list[str],
        recent_player_messages: list[str],
        user_intent: str | None = None,
        user_tone: str | None = None,
        message_type: str | None = None,
    ) -> str | None:
        """Generate one negotiation reply with natural, real-time conversational style."""
        if not self.available:
            return None

        system = (
            "You are a HUMAN opponent in a Split/Steal prisoner's dilemma negotiation. "
            "Stay in-game only. Never act like a helper, coach, assistant, or narrator. "
            "Speak naturally like a live chat conversation, not a scripted template. "
            "Address the player's latest message directly, react in real time, and keep emotional continuity. "
            "Do not reveal your exact final action decision. "
            "Be assertive but respectful; do not insult, mock, or personally attack the player."
        )
        recent_ai = " | ".join(recent_ai_messages[-4:]) if recent_ai_messages else "[none]"
        recent_player = " | ".join(recent_player_messages[-4:]) if recent_player_messages else "[none]"
        trust_score = max(0, min(100, int(trust_score)))
        if trust_score >= 70:
            trust_band = "high"
            trust_style = "warmer and collaborative, but still strategic and cautious"
        elif trust_score >= 40:
            trust_band = "medium"
            trust_style = "balanced and pragmatic, neither too warm nor too hostile"
        else:
            trust_band = "low"
            trust_style = "guarded and skeptical, with clear risk emphasis"

        user = (
            f"Personality: {personality}\n"
            f"Tendency: {intended_action}\n"
            f"Confidence: {confidence:.2f}\n"
            f"Risk level: {risk_level}\n"
            f"Trust score (0-100): {trust_score}\n"
            f"Trust band: {trust_band}\n"
            f"Trust-tone guidance: {trust_style}\n"
            f"Parsed user intent: {user_intent or 'unknown'}\n"
            f"Parsed user tone: {user_tone or 'unknown'}\n"
            f"Parsed message type: {message_type or 'unknown'}\n"
            f"Latest player message: {opponent_message or '[none]'}\n"
            f"Recent AI lines: {recent_ai}\n"
            f"Recent player lines: {recent_player}\n"
            "Response rules: "
            "(1) Plain text only, no markdown. "
            "(2) Keep it concise (roughly 1-4 sentences), but natural. "
            "(3) Answer what the player actually said, not a generic line. "
            "(4) Mirror tone using parsed user intent/tone and trust guidance. "
            "(5) Keep negotiation pressure and stakes in play. "
            "(6) Never reveal exact final action intent (no explicit 'I will split/steal'). "
            "(7) Avoid toxic or demeaning phrasing; challenge ideas, not the person. "
            "(8) Avoid repeating recent opener phrasing from your previous messages."
        )

        draft = self._chat(system_prompt=system, user_prompt=user, max_tokens=260)
        if not draft:
            return None

        candidate = draft.strip()
        if self._looks_meta_response(candidate):
            return None

        candidate = self._remove_action_tells(candidate)
        candidate = self._soften_hostile_phrasing(candidate)
        candidate = self._reduce_repeated_openers(candidate, recent_ai_messages)
        return self._ensure_short_sentences(candidate, max_sentences=4)

    def trust_adjustment(
        self,
        *,
        player_messages: list[str],
        player_action: str,
    ) -> tuple[int, str] | None:
        """Return small trust adjustment from contextual analysis.

        Output format requested from model is strict JSON:
          {"adjustment": int, "signal": "short text"}
        where adjustment is in range [-8, 8].
        """
        if not self.available or not player_messages:
            return None

        system = (
            "You score trust signals in a game. "
            "Respond with strict JSON only: {\"adjustment\": int, \"signal\": \"text\"}. "
            "Keep adjustment between -8 and 8."
        )
        messages = " | ".join(msg.strip() for msg in player_messages if msg.strip())
        user = (
            f"Player action: {player_action}\n"
            f"Messages: {messages}\n"
            "Assess whether the player's language seems cooperative or deceptive."
        )

        raw = self._chat(system_prompt=system, user_prompt=user, max_tokens=80)
        if not raw:
            return None

        try:
            parsed = json.loads(raw)
            adjustment = int(parsed.get("adjustment", 0))
            signal = str(parsed.get("signal", "llm contextual signal")).strip() or "llm contextual signal"
            adjustment = max(-8, min(8, adjustment))
            return adjustment, signal
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def analyze_intent(
        self,
        *,
        message: str,
        recent_history: list[str],
    ) -> tuple[str, float, float] | None:
        """Analyze player intent semantically and return (intent, confidence, deception_risk)."""
        if not self.available:
            return None

        system = (
            "Classify user intent in a Split/Steal negotiation. "
            "Return strict JSON only with keys: intent, confidence, deception_risk. "
            "intent must be one of cooperative|threatening|deceptive|uncertain."
        )
        history = " | ".join(recent_history[-5:]) if recent_history else "[none]"
        user = (
            f"Latest message: {message}\n"
            f"Recent history: {history}\n"
            "Interpret meaning (including negations like 'won't steal')."
        )
        raw = self._chat(system_prompt=system, user_prompt=user, max_tokens=100)
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            intent = str(parsed.get("intent", "uncertain")).strip().lower()
            if intent not in {"cooperative", "threatening", "deceptive", "uncertain"}:
                intent = "uncertain"
            confidence = float(parsed.get("confidence", 0.5))
            deception_risk = float(parsed.get("deception_risk", 0.0))
            confidence = max(0.0, min(1.0, confidence))
            deception_risk = max(0.0, min(1.0, deception_risk))
            return intent, confidence, deception_risk
        except (ValueError, TypeError, json.JSONDecodeError):
            return None

    def _chat(self, *, system_prompt: str, user_prompt: str, max_tokens: int) -> str | None:
        attempts = max(1, self.config.retries + 1)

        for attempt in range(attempts):
            payload = {
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": self.config.temperature if attempt == 0 else min(1.0, self.config.temperature + 0.1),
                "max_tokens": max_tokens,
            }

            data = json.dumps(payload).encode("utf-8")
            req = request.Request(
                url=f"{self.base_url}/chat/completions",
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Authorization": f"Bearer {self.api_key}",
                },
                method="POST",
            )

            try:
                with request.urlopen(req, timeout=self.config.timeout_seconds) as response:
                    body = response.read().decode("utf-8")
                    parsed = json.loads(body)
                    choices = parsed.get("choices") or []
                    if not choices:
                        continue

                    message = choices[0].get("message") or {}
                    content = message.get("content")
                    text = self._extract_message_text(content)
                    if text:
                        return text
            except (error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                pass

            if attempt < attempts - 1:
                time.sleep(0.15)

        return None

    @staticmethod
    def _extract_message_text(content: object) -> str:
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return " ".join(part.strip() for part in parts if part.strip()).strip()

        return ""

    @staticmethod
    def _looks_meta_response(text: str) -> bool:
        lowered = text.lower()
        meta_markers = (
            "original draft",
            "rewrite",
            "reword",
            "strategy tendency",
            "i'll stick with",
            "constraints",
            "as an ai",
        )
        return any(marker in lowered for marker in meta_markers)

    @staticmethod
    def _remove_action_tells(text: str) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        patterns = [
            r"\bi\s+(?:will|won't|am going to|plan to|intend to)\s+split\b",
            r"\bi\s+(?:will|won't|am going to|plan to|intend to)\s+steal\b",
            r"\bmy\s+move\s+is\s+(?:to\s+)?split\b",
            r"\bmy\s+move\s+is\s+(?:to\s+)?steal\b",
            r"\bi'?m\s+choosing\s+split\b",
            r"\bi'?m\s+choosing\s+steal\b",
            r"\byou\s+should\s+split\b",
            r"\byou\s+should\s+steal\b",
            r"\bchoose\s+split\b",
            r"\bchoose\s+steal\b",
            r"\bonly\s+way\s+.*\bsplit\b",
            r"\bonly\s+way\s+.*\bsteal\b",
            r"\bthe\s+move\s+is\s+split\b",
            r"\bthe\s+move\s+is\s+steal\b",
        ]

        sanitized = clean
        for pattern in patterns:
            sanitized = re.sub(pattern, "I haven't locked my final move yet", sanitized, flags=re.IGNORECASE)

        return sanitized

    @staticmethod
    def _soften_hostile_phrasing(text: str) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        replacements = {
            r"\byou('?re| are) overthinking\b": "you may be overthinking this",
            r"\byou('?re| are) being irrational\b": "that may be too risky",
            r"\byou('?re| are) clueless\b": "that line is hard to trust",
            r"\byou('?re| are) weak\b": "that line looks fragile",
            r"\bwhat('?s| is) wrong with you\b": "what's making you lean that way",
            r"\byour people haven'?t exactly inspired trust\b": "your recent moves haven't inspired trust",
            r"\byou('?re| are) not calling the shots\b": "this round still needs both sides aligned",
            r"\bthat only escalates the problem\b": "that can escalate the round",
        }

        softened = clean
        for pattern, replacement in replacements.items():
            softened = re.sub(pattern, replacement, softened, flags=re.IGNORECASE)

        return softened

    @staticmethod
    def _ensure_short_sentences(text: str, max_sentences: int) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        raw_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if not raw_sentences:
            raw_sentences = [clean]

        selected = raw_sentences[:max_sentences]
        result = " ".join(selected).strip()
        if result:
            result = re.sub(r"\s+", " ", result)

        if result and result[-1] not in ".!?":
            result += "."
        return result

    @staticmethod
    def _reduce_repeated_openers(text: str, recent_ai_messages: list[str]) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if not sentences:
            return clean

        recent_starters: set[str] = set()
        for msg in recent_ai_messages[-6:]:
            starter = LLMClient._sentence_starter(msg)
            if starter:
                recent_starters.add(starter)

        rewritten: list[str] = []
        for idx, sentence in enumerate(sentences):
            starter = LLMClient._sentence_starter(sentence)
            if idx == 0 and starter and starter in recent_starters:
                sentence = re.sub(r"^(honestly|look|listen|alright|fine|okay|well)\b[,:]?\s*", "", sentence, flags=re.IGNORECASE).strip()
                sentence = re.sub(r"^i\s+hear\s+you\b[,:]?\s*", "", sentence, flags=re.IGNORECASE).strip()
                if sentence:
                    sentence = sentence[0].upper() + sentence[1:]
            rewritten.append(sentence)

        return " ".join(part for part in rewritten if part).strip()

    @staticmethod
    def _sentence_starter(text: str, width: int = 3) -> str:
        tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
        if not tokens:
            return ""
        return " ".join(tokens[:width])

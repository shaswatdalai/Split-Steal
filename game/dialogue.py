"""Phase 4 dialogue engine constrained by strategy output."""

from dataclasses import dataclass
import random
import re

from game.intent import IntentClassifier
from game.llm import LLMClient


@dataclass
class DialogueContext:
    """Inputs used to generate an AI negotiation message."""

    personality: str
    intended_action: str
    confidence: float
    risk_level: str
    trust_score: int
    opponent_message: str | None
    recent_ai_messages: list[str]
    recent_player_messages: list[str]


@dataclass
class UserMessageProfile:
    message_type: str
    intent: str
    tone: str
    asks_question: bool
    hostility: int
    cooperation: int


class DialogueEngine:
    """Generates negotiation lines while staying aligned to strategy intent."""

    def __init__(self, llm_client: LLMClient | None = None, use_llm: bool = False):
        self.llm_client = llm_client
        self.use_llm = use_llm
        self.intent_classifier = IntentClassifier(llm_client=llm_client, use_llm=use_llm)
        self.last_generation_source = "fallback"

    _OPENERS = {
        "cooperative": ["", "Honestly,", "Alright,"],
        "manipulative": ["", "Look,", "Come on,"],
        "aggressive": ["", "Listen,", "Fine,"],
    }

    _REACTIONS = {
        "question": [
            "Fair question.",
            "That's a fair ask.",
            "Good point.",
            "You're right to ask.",
        ],
        "doubt": [
            "I get the doubt.",
            "Trust is fragile here.",
            "Skepticism makes sense.",
            "I hear you.",
        ],
        "threat": [
            "If we escalate, we both get burned.",
            "That line can zero us both.",
            "Threats usually kill the pot.",
            "That move can backfire.",
        ],
        "cooperation": [
            "Good, we're aligned.",
            "That's the right direction.",
            "That makes this cleaner.",
            "We're on the same page.",
        ],
        "neutral": [
            "We can still keep this clean.",
            "This is still recoverable.",
            "There's still a clean win path.",
            "We can keep this simple.",
        ],
    }

    _KEYWORD_REACTIONS = {
        "trust": [
            "Trust is earned, not just spoken.",
            "Consistency is the only thing that builds trust here.",
            "I want to trust the line, but I'm watching the moves.",
        ],
        "split": [
            "A split is the only way we both walk away with value.",
            "Splitting keeps the game stable for both of us.",
            "I'm leaning towards a split if you are.",
        ],
        "steal": [
            "Stealing might look good for one round, but it kills the game.",
            "If someone steals, the trust index hits zero immediately.",
            "A steal is a one-time win that costs everything later.",
        ],
        "deal": [
            "I'm open to a deal if it stays consistent.",
            "A deal only works if both sides stick to it.",
            "Let's see if we can keep this deal alive.",
        ],
    }


    _SPLIT_PUSH = {
        "cooperative": [
            "the safer line protects both sides and keeps value on the table",
            "we both do better when this stays stable and predictable",
            "we don't need hero moves here, just a clean outcome",
        ],
        "manipulative": [
            "the smart move is the one that locks value instead of gambling it",
            "you keep your upside by staying cooperative for one clean round",
            "forcing chaos here is a bad trade",
        ],
        "aggressive": [
            "discipline beats chaos in this spot",
            "don't torch the round when control is still possible",
            "highest percentage line is the controlled one",
        ],
    }

    _STEAL_LEAN_PUSH = {
        "cooperative": [
            "I'm open to cooperation, but I need consistency from you",
            "I can meet you halfway if your signal stays stable",
            "I want fair, but not blind trust",
        ],
        "manipulative": [
            "keep it clean and this stays smooth",
            "show commitment and this stays favorable for both",
            "stay predictable and this remains profitable",
        ],
        "aggressive": [
            "push this and we both lose value",
            "I don't reward reckless plays",
            "one bad move and this whole round implodes",
        ],
    }

    _FOLLOW_UPS = {
        "question": ["so what's your move?", "can you commit to that?", "you in?"],
        "doubt": ["what would convince you?", "what do you need to hear?", "want one clean round first?"],
        "threat": ["you sure that's worth the risk?", "you really want zero-zero?", "is that your best line?"],
        "cooperation": ["deal?", "we good then?", "let's lock it in?"],
        "neutral": ["where are you leaning?", "what's your call?", "safe line or chaos?"],
    }

    _HEDGES = ("maybe", "honestly", "probably", "kinda", "I mean")

    _TONE_LINES = {
        "warm": [
            "I'm good with steady play if you are.",
            "We can make this work if we keep it clean.",
            "I'm open to a fair line if you stay consistent.",
        ],
        "guarded": [
            "I hear you, but trust has to be earned here.",
            "I get the concern, but words alone don't settle it.",
            "I'm listening, but I'm not moving blind.",
        ],
        "firm": [
            "Push this too hard and both sides lose value.",
            "If this turns reckless, nobody wins the round.",
            "I'm not rewarding chaos.",
        ],
        "calm": [
            "Let's keep this practical.",
            "No drama, just smart play.",
            "Simple works better here.",
        ],
    }

    def generate(self, context: DialogueContext) -> str:
        """Generate a strategy-aligned negotiation message."""
        user_profile = self._analyze_user_response(
            message=context.opponent_message,
            recent_player_messages=context.recent_player_messages,
            trust_score=context.trust_score,
        )

        if self.use_llm and self.llm_client is not None:
            llm_text = self.llm_client.generate_dialogue(
                personality=context.personality,
                intended_action=context.intended_action,
                confidence=context.confidence,
                risk_level=context.risk_level,
                trust_score=context.trust_score,
                opponent_message=context.opponent_message,
                recent_ai_messages=context.recent_ai_messages,
                recent_player_messages=context.recent_player_messages,
                user_intent=user_profile.intent,
                user_tone=user_profile.tone,
                message_type=user_profile.message_type,
            )
            if llm_text and self._is_strategy_aligned(llm_text, context.intended_action):
                self.last_generation_source = "llm"
                return self._compose_llm_reply(llm_text=llm_text)

        self.last_generation_source = "fallback"
        return self._generate_fallback(context, user_profile)

    def _generate_fallback(self, context: DialogueContext, user_profile: UserMessageProfile) -> str:
        persona = context.personality if context.personality in self._OPENERS else "manipulative"
        message_type = user_profile.message_type

        # Priority: Keyword-based reaction
        reaction = None
        lowered_msg = (context.opponent_message or "").lower()
        for kw, pool in self._KEYWORD_REACTIONS.items():
            if kw in lowered_msg:
                reaction = self._pick_non_repeating_fragment(pool, context.recent_ai_messages)
                break
        
        if not reaction:
            reaction = self._pick_non_repeating_fragment(
                self._REACTIONS[message_type],
                context.recent_ai_messages,
            )

        if context.intended_action.startswith("SPLIT"):
            strategy_line = self._pick_non_repeating_fragment(self._SPLIT_PUSH[persona], context.recent_ai_messages)
        else:
            strategy_line = self._pick_non_repeating_fragment(self._STEAL_LEAN_PUSH[persona], context.recent_ai_messages)

        follow_up = self._pick_non_repeating_fragment(self._FOLLOW_UPS[message_type], context.recent_ai_messages)
        tone_line = self._pick_non_repeating_fragment(
            self._TONE_LINES.get(user_profile.tone, self._TONE_LINES["calm"]),
            context.recent_ai_messages,
        )
        opener = random.choice(self._OPENERS[persona])


        if context.confidence < 0.62:
            middle = f"{random.choice(self._HEDGES)}, {strategy_line}."
        elif context.confidence > 0.84:
            middle = f"{strategy_line}."
        else:
            middle = f"honestly, {strategy_line}."

        first = f"{opener} {reaction}.".strip()
        first = re.sub(r"\s+", " ", first)
        response = f"{first} {tone_line} {middle}"
        if user_profile.asks_question or user_profile.hostility > 0:
            response = f"{response} {follow_up}"
        response = self._shape_short_sentences(response, max_sentences=3)
        return self._normalize_grammar(self._clean(response))

    def _compose_llm_reply(self, llm_text: str) -> str:
        clean = self._clean(llm_text)
        shaped = self._shape_short_sentences(clean, max_sentences=4)
        deduped = self._dedupe_repeated_sentences(shaped)
        return self._normalize_grammar(deduped)

    def _analyze_user_response(
        self,
        message: str | None,
        recent_player_messages: list[str],
        trust_score: int,
    ) -> UserMessageProfile:
        text = (message or "").strip()
        lowered = text.lower()

        message_type = self._classify_user_message(text)
        analysis = self.intent_classifier.classify(
            message=text,
            recent_history=recent_player_messages[-5:],
        ) if text else None

        hostility = sum(
            1 for token in ("liar", "fake", "betray", "steal", "threat", "punish", "cheat")
            if token in lowered
        )
        cooperation = sum(
            1 for token in ("deal", "fair", "cooperate", "split", "trust", "agree")
            if token in lowered
        )
        asks_question = "?" in lowered

        if hostility >= 2 or (analysis and analysis.intent == "threatening"):
            tone = "firm"
        elif message_type == "doubt" or (analysis and analysis.intent in {"deceptive", "uncertain"}):
            tone = "guarded"
        elif cooperation >= 1 or message_type == "cooperation" or (analysis and analysis.intent == "cooperative"):
            tone = "warm" if trust_score >= 45 else "guarded"
        else:
            tone = "calm"

        intent = analysis.intent if analysis else "uncertain"
        return UserMessageProfile(
            message_type=message_type,
            intent=intent,
            tone=tone,
            asks_question=asks_question,
            hostility=hostility,
            cooperation=cooperation,
        )

    @staticmethod
    def _classify_user_message(message: str | None) -> str:
        text = (message or "").strip().lower()
        if not text:
            return "neutral"

        if "?" in text or re.search(r"\b(why|how|what|prove|explain|sure)\b", text):
            return "question"
        if re.search(r"\b(don't trust|dont trust|liar|lying|fake|doubt|skeptic)\b", text):
            return "doubt"
        if re.search(r"\b(steal|betray|threat|punish|take all|i might steal|i will steal)\b", text):
            return "threat"
        if re.search(r"\b(split|share|cooperate|deal|fair)\b", text):
            return "cooperation"
        return "neutral"

    @staticmethod
    def _is_strategy_aligned(text: str, intended_action: str) -> bool:
        lowered = text.lower()
        cooperative_markers = ("split", "share", "cooperate", "fair", "together")
        aggressive_markers = ("steal", "betray", "take all", "no mercy")

        anti_split_patterns = (
            r"\bdon't\s+split\b",
            r"\bdo\s+not\s+split\b",
            r"\bwon't\s+split\b",
            r"\bwill\s+not\s+split\b",
            r"\bnever\s+split\b",
            r"\bsplitting\s+is\s+not\s+the\s+way\b",
            r"\bdon't\s+think\s+splitting\s+is\s+the\s+way\b",
            r"\bsplit\s+is\s+(?:dumb|stupid|bad|for\s+fools|weak)\b",
            r"\bforget\s+split\b",
            r"\bnot\s+split\b",
            r"\bavoid\s+split\b",
            r"\bno\s+split\b",
        )
        anti_steal_patterns = (
            r"\bdon't\s+steal\b",
            r"\bdo\s+not\s+steal\b",
            r"\bwon't\s+steal\b",
            r"\bwill\s+not\s+steal\b",
            r"\bnever\s+steal\b",
            r"\bstealing\s+is\s+not\s+the\s+way\b",
            r"\bsteal\s+is\s+(?:dumb|stupid|bad|wrong|for\s+fools)\b",
            r"\bforget\s+steal\b",
            r"\bnot\s+steal\b",
            r"\bavoid\s+steal\b",
            r"\bno\s+steal\b",
        )

        coop_score = sum(1 for token in cooperative_markers if token in lowered)
        aggressive_score = sum(1 for token in aggressive_markers if token in lowered)

        if intended_action.startswith("SPLIT"):
            if any(re.search(pattern, lowered) for pattern in anti_split_patterns):
                return False
            return coop_score + 1 >= aggressive_score

        if any(re.search(pattern, lowered) for pattern in anti_steal_patterns):
            return False
        return True

    @staticmethod
    def _pick_non_repeating_fragment(pool: list[str], recent_messages: list[str]) -> str:
        recent_window = recent_messages[-6:]
        recent_text = " | ".join(msg.lower() for msg in recent_window)
        recent_signatures = {
            DialogueEngine._fragment_signature(msg)
            for msg in recent_window
            if msg
        }

        candidates = [
            fragment
            for fragment in pool
            if fragment.lower() not in recent_text
            and DialogueEngine._fragment_signature(fragment) not in recent_signatures
        ]
        if not candidates:
            candidates = pool
        return random.choice(candidates)

    @staticmethod
    def _fragment_signature(text: str, width: int = 4) -> str:
        tokens = re.findall(r"[a-z0-9']+", (text or "").lower())
        if not tokens:
            return ""
        return " ".join(tokens[:width])

    @staticmethod
    def _clean(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        compact = re.sub(r"\.{2,}", ".", compact)
        return compact

    @staticmethod
    def _shape_short_sentences(text: str, max_sentences: int) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if not sentences:
            sentences = [clean]

        selected = sentences[:max_sentences]
        result = " ".join(selected).strip()
        if result:
            result = re.sub(r"\s+", " ", result)

        if result and result[-1] not in ".!?":
            result += "."
        return result

    @staticmethod
    def _normalize_grammar(text: str) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        clean = re.sub(r"\bi\b", "I", clean)
        clean = clean.replace(" i'", " I'")

        parts = re.split(r"([.!?]\s+)", clean)
        rebuilt: list[str] = []
        for idx, part in enumerate(parts):
            if idx % 2 == 0 and part:
                stripped = part.lstrip()
                if stripped:
                    part = part[: len(part) - len(stripped)] + stripped[0].upper() + stripped[1:]
            rebuilt.append(part)

        result = "".join(rebuilt).strip()
        return result

    @staticmethod
    def _dedupe_repeated_sentences(text: str) -> str:
        clean = " ".join((text or "").split()).strip()
        if not clean:
            return clean

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clean) if s.strip()]
        if not sentences:
            return clean

        unique: list[str] = []
        seen_norm: set[str] = set()
        for sentence in sentences:
            norm = re.sub(r"[^a-z0-9\s]", "", sentence.lower()).strip()
            if not norm or norm in seen_norm:
                continue
            seen_norm.add(norm)
            unique.append(sentence)

        if len(unique) >= 2:
            first_norm = re.sub(r"[^a-z0-9\s]", "", unique[0].lower()).strip()
            second_norm = re.sub(r"[^a-z0-9\s]", "", unique[1].lower()).strip()
            if first_norm.startswith("i hear you") and second_norm.startswith("i hear you"):
                unique.pop(1)

        result = " ".join(unique).strip()
        return result if result else clean

# Split & Steal

A console-based Prisoner’s Dilemma game where a human plays against an adaptive AI opponent.

The project combines:

- deterministic game logic (payoffs, rounds, scorekeeping),
- adaptive AI strategy (trust + memory + personality),
- negotiation dialogue (fallback rules and LLM generation),
- real-time trust updates from user chat and final trust updates from round outcomes.

---

## 1) Project Overview

In each round:

1. Human and AI can negotiate.
2. Both choose one action: `SPLIT` or `STEAL`.
3. Rewards are resolved by payoff matrix.
4. Trust and memory are updated.
5. The game advances until configured rounds are completed.

### Core idea

The AI is not only random. It adapts based on:

- player language,
- player historical actions,
- detected betrayal patterns,
- selected AI personality,
- round context (including endgame pressure),
- optional LLM semantic enrichment.

---

## 2) Tech Stack

- Language: Python 3.13
- Runtime: CLI / terminal application
- Environment: virtual environment (`.venv`)
- Type tooling: Pyright (`pyrightconfig.json`)
- LLM integration (optional): Groq OpenAI-compatible chat completions API
- Networking for LLM calls: Python standard library `urllib`

### External services

- Groq API endpoint (default): `https://api.groq.com/openai/v1`

### Dependencies

Core game logic uses Python standard library only.

---

## 3) Folder Structure

- `main.py` — application entrypoint, CLI args, `.env` loading, wiring players and engine.
- `game/constants.py` — defaults, payoff matrix, AI personality profiles.
- `game/models.py` — domain data structures (`GameState`, `RoundResult`, `PlayerAction`).
- `game/engine.py` — main game loop orchestration and round lifecycle.
- `game/display.py` — terminal UI (colors, banners, scoreboards, trust updates).
- `game/players.py` — `HumanPlayer`, adaptive `RandomAI` behavior and action sampling.
- `game/strategy.py` — AI strategic assessment and probability modeling.
- `game/trust.py` — live chat trust updates + round-level trust evaluation.
- `game/intent.py` — hybrid heuristic + optional LLM intent classifier.
- `game/memory.py` — cross-round memory and behavioral pattern tracking.
- `game/dialogue.py` — dialogue generation pipeline (fallback + LLM post-processing).
- `game/llm.py` — Groq-compatible client, dialogue/trust/intent API requests.

---

## 4) Rules and Payoff Logic

Defined in `game/constants.py`:

| You   | AI    | You Earn | AI Earn |
| ----- | ----- | -------: | ------: |
| SPLIT | SPLIT |      50% |     50% |
| STEAL | SPLIT |     100% |      0% |
| SPLIT | STEAL |       0% |    100% |
| STEAL | STEAL |       0% |      0% |

Defaults:

- rounds: 5
- pot per round: ₹100,000
- negotiation messages per side (max): 3

---

## 5) Runtime Workflow (End-to-End)

### Startup

1. `main.py` loads `.env` (if present).
2. CLI arguments are parsed.
3. Human player and AI opponent are created.
4. `GameEngine` is initialized with trust evaluator.

### Per-round lifecycle

In `game/engine.py`:

1. Show round header.
2. Enter negotiation loop.
3. Update trust live after each user message.
4. Ask both sides for final action.
5. Resolve rewards via payoff matrix.
6. Apply round trust update (action + promise/betrayal logic).
7. Record result in `GameState` and display outcome.
8. Notify both players to update memory.

### Negotiation loop details

- AI opens the round with a generated line.
- User can send up to configured message limit or stop early.
- Trust changes can happen immediately per message.
- AI can reply each turn.

---

## 6) AI System Design

### 6.1 Personality model

Personalities in `game/constants.py`:

- `cooperative`
- `manipulative`
- `aggressive`

Each profile contributes:

- base steal probability,
- risk tolerance.

### 6.2 Strategy engine (`game/strategy.py`)

Computes `StrategyAssessment` each round:

- `intended_action` (`SPLIT_LEAN` or `STEAL_LEAN`),
- `steal_probability`,
- `confidence`,
- `risk_level`.

Inputs include:

- trust score,
- betrayal count,
- current vs total rounds,
- memory snapshot (streaks, rates, consistency, confidence trend).

### 6.3 Action selection (`game/players.py`)

Final action is sampled from strategic probabilities with safeguards:

- high-confidence path can be deterministic for clear steal intent,
- opportunistic steal floor prevents “never-betray” lock states,
- confidence blending avoids brittle behavior at low certainty.

### 6.4 Trust system (`game/trust.py`)

Two trust update channels:

1. **Live message updates** (`evaluate_message`) during negotiation.
2. **Round outcome updates** (`evaluate_round`) after actions resolve.

Trust signals include:

- cooperative/threat/deceptive language,
- consistency patterns,
- repeated steals,
- promise-keeping vs betrayal,
- optional LLM trust delta.

### 6.5 Intent understanding (`game/intent.py`)

Hybrid classifier:

- heuristic rules for stable baseline,
- optional LLM intent inference for semantic nuance,
- explicit anti-negation safeguards (e.g., “I won’t steal”).

### 6.6 Memory (`game/memory.py`)

Tracks across rounds:

- player/AI actions,
- betrayal count/rate,
- steal/split streaks,
- consistency trend,
- confidence trend,
- recent player/AI messages.

Memory feeds strategy assessment each round.

---

## 7) Dialogue Pipeline

Implemented in `game/dialogue.py` + `game/llm.py`.

### 7.1 User-response understanding

`DialogueEngine` builds a `UserMessageProfile`:

- message type (`question`, `doubt`, `threat`, `cooperation`, `neutral`),
- inferred intent,
- tone bucket (`warm`, `guarded`, `firm`, `calm`),
- hostility/cooperation signal counts,
- question flag.

### 7.2 Generation modes

1. **LLM mode** (if enabled + API key present):
   - sends strategy + trust + context + parsed user intent/tone,
   - requires human-like but non-revealing negotiation text,
   - sanitizes direct action leaks.
2. **Fallback mode**:
   - deterministic template fragments,
   - tone and context adaptive,
   - anti-repetition selection from recent dialogue history.

### 7.3 Safety and realism constraints

- Avoid assistant-like/meta wording.
- Keep outputs concise and conversational.
- Do not reveal exact final action intent.
- Use minimal/silent replies for low-content user inputs where appropriate.

---

## 8) LLM Integration

### Environment variables

Supported in `game/llm.py`:

- `GROQ_API_KEY` (preferred)
- `GROQ_BASE_URL` (optional override)

Compatibility aliases also supported:

- `GROK_API_KEY`
- `GROK_BASE_URL`

Default base URL:

- `https://api.groq.com/openai/v1`

### API behavior

- OpenAI-compatible `/chat/completions` calls.
- Retry support with temperature bump on retry.
- Structured helpers for:
  - dialogue generation,
  - trust adjustment,
  - intent analysis.

### Secret handling

- `mask_secret` and `safe_debug_snapshot` avoid exposing raw API key.

---

## 9) CLI Usage

From project root:

- `python main.py`
- `python main.py --rounds 3`
- `python main.py --pot 50000`
- `python main.py --name "Alice"`
- `python main.py --personality manipulative`
- `python main.py --use-llm`
- `python main.py --use-llm --llm-model llama-3.1-8b-instant --llm-timeout 8`

### Main CLI options

- `--rounds`
- `--pot`
- `--name`
- `--personality` (`cooperative`, `manipulative`, `aggressive`, `random`)
- `--use-llm`
- `--llm-model`
- `--llm-timeout`

---

## 10) Development and Validation

### Type analysis

- `pyrightconfig.json` is configured for Python 3.13 and `.venv`.

### Quick compile validation

- `python -m compileall game main.py`

### Current test status

- No dedicated test suite is currently present.
- Existing validation approach is compile checks + runtime smoke runs.

---

## 11) Design Characteristics

### Strengths

- Modular architecture with clean separation of concerns.
- Adaptive AI behavior driven by trust + memory + intent.
- Human-like negotiation layer with optional LLM enhancement.
- CLI-first UX with readable game telemetry (strategy, trust, score).

### Practical constraints

- No persistent storage/database (state resets each run).
- No formal automated tests yet.
- Fallback dialogue still template-derived (though context-aware).

---

## 12) Suggested Next Enhancements

1. Add automated tests for trust, strategy, and dialogue branching.
2. Add run-level analytics export (JSON/CSV) for behavior inspection.
3. Add deterministic seed option in CLI for reproducible AI behavior.
4. Add optional persistent player profile/history across sessions.

---

## 13) Quick Start Checklist

1. Create and activate virtual environment.
2. Put Groq key in `.env` if using LLM mode.
3. Run `python main.py --use-llm` (or omit LLM flag for fallback mode).
4. Play rounds, monitor trust updates, and observe AI adaptation.

---

## 14) License / Ownership

This repository currently does not define an explicit license file.
If needed, add one (for example MIT/Apache-2.0) based on your distribution goals.

"""Split & Steal — Entry Point.

Usage:
    python main.py                   # Default: 5 rounds, ₹100,000 pot
    python main.py --rounds 3        # Custom number of rounds
    python main.py --pot 50000       # Custom pot size
    python main.py --name "Alice"    # Custom player name
    python main.py --use-llm         # Enable optional LLM enhancement
"""

import argparse
import os
import random
from pathlib import Path

from game.constants import DEFAULT_ROUNDS, DEFAULT_POT
from game.players import HumanPlayer, RandomAI
from game.engine import GameEngine
from game.constants import PERSONALITIES


def load_local_env() -> None:
    """Load simple KEY=VALUE pairs from .env into os.environ if unset."""
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"").strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main():
    load_local_env()

    parser = argparse.ArgumentParser(
        description="Split & Steal — A Prisoner's Dilemma Game"
    )
    parser.add_argument(
        "--rounds", type=int, default=DEFAULT_ROUNDS,
        help=f"Number of rounds to play (default: {DEFAULT_ROUNDS})"
    )
    parser.add_argument(
        "--pot", type=int, default=DEFAULT_POT,
        help=f"Pot size per round in ₹ (default: {DEFAULT_POT:,})"
    )
    parser.add_argument(
        "--name", type=str, default="You",
        help="Your display name (default: You)"
    )
    parser.add_argument(
        "--personality",
        type=str,
        choices=sorted(PERSONALITIES.keys()) + ["random"],
        default="random",
        help="AI personality profile (or random per game)"
    )
    parser.add_argument(
        "--use-llm",
        action="store_true",
        help="Enable optional LLM-backed dialogue/trust enhancement (requires GROQ_API_KEY)"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default="llama-3.1-8b-instant",
        help="Groq model name for Phase 5 integration"
    )
    parser.add_argument(
        "--llm-timeout",
        type=float,
        default=8.0,
        help="LLM request timeout in seconds"
    )
    args = parser.parse_args()

    selected_personality = (
        random.choice(sorted(PERSONALITIES.keys()))
        if args.personality == "random"
        else args.personality
    )

    player = HumanPlayer(name=args.name)
    opponent = RandomAI(
        name="AI Opponent",
        personality=selected_personality,
        use_llm=args.use_llm,
        llm_model=args.llm_model,
        llm_timeout_seconds=args.llm_timeout,
    )

    engine = GameEngine(
        player=player,
        opponent=opponent,
        total_rounds=args.rounds,
        pot_per_round=args.pot,
        use_llm=args.use_llm,
    )

    try:
        engine.run()
    except KeyboardInterrupt:
        print("\n\n  Game aborted. See you next time! 👋\n")


if __name__ == "__main__":
    main()

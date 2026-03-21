"""Game constants, configuration, and payoff matrix."""

# ─── Game Defaults ───────────────────────────────────────────────
DEFAULT_ROUNDS = 5
DEFAULT_POT = 100_000  # ₹100,000
NEGOTIATION_MESSAGE_LIMIT = 3  # Max messages per player per round

# ─── Payoff Matrix ───────────────────────────────────────────────
# Format: (player_action, opponent_action) -> (player_share%, opponent_share%)
PAYOFF_MATRIX = {
    ("SPLIT", "SPLIT"): (50, 50),    # Both cooperate → share equally
    ("STEAL", "SPLIT"): (100, 0),    # Player betrays → takes all
    ("SPLIT", "STEAL"): (0, 100),    # Opponent betrays → loses all
    ("STEAL", "STEAL"): (0, 0),      # Both betray → nobody gets anything
}

# ─── AI Personality Profiles (for Phase 3) ───────────────────────
PERSONALITIES = {
    "cooperative": {
        "description": "Tends to trust and split",
        "base_steal_probability": 0.2,
        "risk_tolerance": 0.3,
    },
    "aggressive": {
        "description": "Tends to steal and dominate",
        "base_steal_probability": 0.7,
        "risk_tolerance": 0.8,
    },
    "manipulative": {
        "description": "Says split, considers steal",
        "base_steal_probability": 0.5,
        "risk_tolerance": 0.5,
    },
}

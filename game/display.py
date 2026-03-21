"""Console display utilities — colors, formatting, and game UI."""

import os
import sys

# ─── ANSI Color Codes ────────────────────────────────────────────
class C:
    """ANSI color/style codes for pretty console output."""
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    ITALIC  = "\033[3m"

    # Colors
    RED     = "\033[31m"
    GREEN   = "\033[32m"
    YELLOW  = "\033[33m"
    BLUE    = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN    = "\033[36m"
    WHITE   = "\033[37m"

    # Bright variants
    BRED    = "\033[91m"
    BGREEN  = "\033[92m"
    BYELLOW = "\033[93m"
    BBLUE   = "\033[94m"
    BMAGENTA= "\033[95m"
    BCYAN   = "\033[96m"

    # Background
    BG_RED    = "\033[41m"
    BG_GREEN  = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE   = "\033[44m"


def enable_ansi_windows():
    """Enable ANSI escape codes on Windows terminals."""
    if sys.platform == "win32":
        os.system("")  # Trick to enable ANSI on Windows


def clear_screen():
    os.system("cls" if sys.platform == "win32" else "clear")


def format_currency(amount: int) -> str:
    """Format amount as ₹XX,XXX."""
    return f"₹{amount:,}"


# ─── Game Display Functions ──────────────────────────────────────

def show_banner():
    """Display the game title banner."""
    banner = f"""
{C.BOLD}{C.BCYAN}╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     ███████╗██████╗ ██╗     ██╗████████╗                     ║
║     ██╔════╝██╔══██╗██║     ██║╚══██╔══╝                     ║
║     ███████╗██████╔╝██║     ██║   ██║                        ║
║     ╚════██║██╔═══╝ ██║     ██║   ██║                        ║
║     ███████║██║     ███████╗██║   ██║     ██╗                ║
║     ╚══════╝╚═╝     ╚══════╝╚═╝   ╚═╝     ╚═╝                ║
║               {C.BYELLOW}&   S T E A L{C.BCYAN}                               ║
║                                                              ║
║          {C.WHITE}A Prisoner's Dilemma Game{C.BCYAN}                         ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
"""
    print(banner)


def show_rules():
    """Display game rules and payoff matrix."""
    print(f"""
{C.BOLD}{C.WHITE}  ── HOW IT WORKS ──────────────────────────────────────────{C.RESET}

  You and an AI opponent each have a pot of money.
  Each round, you'll {C.CYAN}negotiate{C.RESET} and then {C.BOLD}decide{C.RESET}:

    {C.BGREEN}SPLIT{C.RESET}  — Share the pot fairly
    {C.BRED}STEAL{C.RESET}  — Try to take it all

{C.BOLD}{C.WHITE}  ── PAYOFF MATRIX ─────────────────────────────────────────{C.RESET}

    ┌───────────────────┬────────────────────┬────────────────────┐
    │                   │  {C.DIM}Opponent SPLITS{C.RESET}   │  {C.DIM}Opponent STEALS{C.RESET}   │
    ├───────────────────┼────────────────────┼────────────────────┤
    │  {C.BGREEN}You SPLIT{C.RESET}        │  {C.GREEN}You 50% / AI 50%{C.RESET}  │  {C.RED}You  0% / AI 100%{C.RESET} │
    ├───────────────────┼────────────────────┼────────────────────┤
    │  {C.BRED}You STEAL{C.RESET}        │  {C.GREEN}You 100% / AI 0%{C.RESET}  │  {C.RED}You  0% / AI  0%{C.RESET}  │
    └───────────────────┴────────────────────┴────────────────────┘

  {C.DIM}Trust is earned. Betrayal has consequences.{C.RESET}
""")


def show_runtime_mode(use_llm: bool, llm_active: bool):
    """Show runtime AI mode (local fallback vs LLM active)."""
    if not use_llm:
        mode_text = f"{C.DIM}LLM: OFF (template dialogue + heuristic trust){C.RESET}"
    elif llm_active:
        mode_text = f"{C.BGREEN}LLM: ACTIVE{C.RESET}{C.DIM} (API-backed dialogue + contextual trust){C.RESET}"
    else:
        mode_text = f"{C.BYELLOW}LLM: FALLBACK{C.RESET}{C.DIM} (enabled but API unavailable; using local logic){C.RESET}"

    print(f"  {mode_text}\n")


def show_round_header(round_num: int, total_rounds: int, pot: int):
    """Display the header for a new round."""
    print(f"""
{C.BOLD}{C.BBLUE}  ═══════════════════════════════════════════════════════════
  ║  ROUND {round_num} of {total_rounds}                    Pot: {format_currency(pot)}
  ═══════════════════════════════════════════════════════════{C.RESET}
""")


def show_negotiation_header():
    """Display the negotiation phase header."""
    print(f"  {C.BOLD}{C.CYAN}── NEGOTIATION PHASE ──{C.RESET}")
    print(f"  {C.DIM}Chat with the AI. Type 'done' or press Enter to skip.{C.RESET}")
    print()


def show_ai_message(name: str, message: str):
    """Display a message from the AI."""
    print(f"  {C.BMAGENTA}{name}{C.RESET}: {C.WHITE}{message}{C.RESET}")


def show_decision_header():
    """Display the decision phase header."""
    print(f"\n  {C.BOLD}{C.YELLOW}── DECISION TIME ──{C.RESET}")
    print(f"  {C.DIM}Choose wisely. Your fate depends on both choices.{C.RESET}")


def show_round_result(round_num, player_action, opponent_action,
                       player_reward, opponent_reward, player_name, opponent_name,
                       ai_personality, ai_intended_action, ai_confidence, ai_risk_level, ai_steal_probability):
    """Display the result of a round with dramatic reveal."""
    p_action = player_action.value
    o_action = opponent_action.value

    p_color = C.BGREEN if p_action == "SPLIT" else C.BRED
    o_color = C.BGREEN if o_action == "SPLIT" else C.BRED

    print(f"""
  {C.BOLD}{C.WHITE}── ROUND {round_num} RESULT ──────────────────────────────────{C.RESET}

    {player_name} chose:   {p_color}{C.BOLD}{p_action}{C.RESET}
    {opponent_name} chose:  {o_color}{C.BOLD}{o_action}{C.RESET}
""")

    # Show outcome message
    if p_action == "SPLIT" and o_action == "SPLIT":
        print(f"  {C.BGREEN}🤝 Both cooperated! The pot is shared fairly.{C.RESET}")
    elif p_action == "STEAL" and o_action == "SPLIT":
        print(f"  {C.BYELLOW}😈 You stole everything! The AI trusted you.{C.RESET}")
    elif p_action == "SPLIT" and o_action == "STEAL":
        print(f"  {C.BRED}💔 You were betrayed! The AI took it all.{C.RESET}")
    else:
        print(f"  {C.BRED}💀 Mutual destruction! Greed destroys both sides.{C.RESET}")

    print(f"""
    {C.DIM}Earnings this round:{C.RESET}
      {player_name}: {C.BOLD}{format_currency(player_reward)}{C.RESET}
      {opponent_name}: {C.BOLD}{format_currency(opponent_reward)}{C.RESET}
""")

    print(
        f"    {C.DIM}AI strategy: personality={ai_personality}, "
        f"tendency={ai_intended_action}, "
        f"confidence={ai_confidence:.2f}, risk={ai_risk_level}, "
        f"steal_prob={ai_steal_probability:.2f}{C.RESET}"
    )
    print()


def show_scoreboard(player_name, opponent_name, player_score, opponent_score,
                     round_num, total_rounds, trust_score, betrayal_count):
    """Display current scores."""
    print(f"  {C.BOLD}{C.WHITE}── SCOREBOARD ──────────────────────────────────────────{C.RESET}")
    print(f"    {player_name:.<20s} {C.BGREEN}{format_currency(player_score):>12s}{C.RESET}")
    print(f"    {opponent_name:.<20s} {C.BCYAN}{format_currency(opponent_score):>12s}{C.RESET}")

    remaining = total_rounds - round_num
    if remaining > 0:
        print(f"    {C.DIM}Rounds remaining: {remaining}{C.RESET}")
    print(f"    {C.DIM}AI trust in you: {trust_score}/100{C.RESET}")
    print(f"    {C.DIM}Detected betrayals: {betrayal_count}{C.RESET}")
    print()


def show_trust_update(
    trust_before: int,
    trust_after: int,
    trust_delta: int,
    trust_signals: list[str],
    betrayal_flag: bool,
):
    """Display how trust changed this round and why."""
    if trust_delta > 0:
        delta_text = f"{C.BGREEN}+{trust_delta}{C.RESET}"
    elif trust_delta < 0:
        delta_text = f"{C.BRED}{trust_delta}{C.RESET}"
    else:
        delta_text = f"{C.DIM}0{C.RESET}"

    print(f"  {C.BOLD}{C.WHITE}── TRUST UPDATE ───────────────────────────────────────{C.RESET}")
    print(
        f"    Trust score: {trust_before} → {trust_after} "
        f"(Δ {delta_text})"
    )

    if betrayal_flag:
        print(f"    {C.BRED}⚠ Promise betrayal detected this round{C.RESET}")

    if trust_signals:
        signals = ", ".join(trust_signals)
        print(f"    Signals: {C.DIM}{signals}{C.RESET}")
    print()


def show_game_over(
    player_name,
    opponent_name,
    player_score,
    opponent_score,
    history,
    final_trust,
    betrayal_count,
):
    """Display the final game-over screen with full results."""
    print(f"""
{C.BOLD}{C.BCYAN}╔══════════════════════════════════════════════════════════════╗
║                        GAME OVER                             ║
╚══════════════════════════════════════════════════════════════╝{C.RESET}
""")

    if player_score > opponent_score:
        verdict = f"{C.BGREEN}🏆 YOU WIN!{C.RESET}"
    elif opponent_score > player_score:
        verdict = f"{C.BRED}💀 AI WINS!{C.RESET}"
    else:
        verdict = f"{C.BYELLOW}🤝 IT'S A TIE!{C.RESET}"

    print(f"  {verdict}")
    print()
    print(f"  {C.BOLD}Final Scores:{C.RESET}")
    print(f"    {player_name:.<20s} {C.BGREEN}{format_currency(player_score):>12s}{C.RESET}")
    print(f"    {opponent_name:.<20s} {C.BCYAN}{format_currency(opponent_score):>12s}{C.RESET}")
    print()

    print(f"  {C.BOLD}{C.WHITE}── ROUND HISTORY ───────────────────────────────────────{C.RESET}")
    print(f"    {'Round':<8} {'You':<10} {'AI':<10} {'Your Earn':<14} {'AI Earn':<14}")
    print(f"    {'─'*8} {'─'*10} {'─'*10} {'─'*14} {'─'*14}")

    for round_result in history:
        player_color = C.GREEN if round_result.player_action.value == "SPLIT" else C.RED
        opponent_color = C.GREEN if round_result.opponent_action.value == "SPLIT" else C.RED
        print(
            f"    {round_result.round_number:<8} "
            f"{player_color}{round_result.player_action.value:<10}{C.RESET} "
            f"{opponent_color}{round_result.opponent_action.value:<10}{C.RESET} "
            f"{format_currency(round_result.player_reward):<14} "
            f"{format_currency(round_result.opponent_reward):<14}"
        )

    print()

    total_rounds = len(history)
    player_splits = sum(1 for round_result in history if round_result.player_action.value == "SPLIT")
    opponent_splits = sum(1 for round_result in history if round_result.opponent_action.value == "SPLIT")

    print(f"  {C.BOLD}Stats:{C.RESET}")
    print(
        f"    Your cooperation rate:  {player_splits}/{total_rounds} "
        f"({player_splits/total_rounds*100:.0f}%)"
    )
    print(
        f"    AI cooperation rate:    {opponent_splits}/{total_rounds} "
        f"({opponent_splits/total_rounds*100:.0f}%)"
    )
    print(f"    Final AI trust score:   {final_trust}/100")
    print(f"    Betrayals detected:     {betrayal_count}")

    mutual_coop = sum(
        1
        for round_result in history
        if round_result.player_action.value == "SPLIT"
        and round_result.opponent_action.value == "SPLIT"
    )
    mutual_betray = sum(
        1
        for round_result in history
        if round_result.player_action.value == "STEAL"
        and round_result.opponent_action.value == "STEAL"
    )
    print(f"    Mutual cooperation:     {mutual_coop}/{total_rounds}")
    print(f"    Mutual betrayal:        {mutual_betray}/{total_rounds}")
    print()

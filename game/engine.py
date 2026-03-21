"""Core game engine — orchestrates the full gameplay loop."""

from game.constants import (
    DEFAULT_ROUNDS,
    DEFAULT_POT,
    NEGOTIATION_MESSAGE_LIMIT,
    PAYOFF_MATRIX,
)
from game.models import GameState, RoundResult, PlayerAction
from game.players import Player
from game.trust import TrustEvaluator
from game import display


class GameEngine:
    """
    Manages the Split & Steal game loop.

    Flow per round:
      1. Show round header
      2. Negotiation phase (message exchange)
      3. Decision phase (both players choose)
      4. Resolution (apply payoff matrix)
      5. Display results & scoreboard
    """

    def __init__(
        self,
        player: Player,
        opponent: Player,
        total_rounds: int = DEFAULT_ROUNDS,
        pot_per_round: int = DEFAULT_POT,
        use_llm: bool = False,
    ):
        self.player = player
        self.opponent = opponent
        self.state = GameState(
            total_rounds=total_rounds,
            pot_per_round=pot_per_round,
        )
        opponent_llm_client = getattr(opponent, "llm_client", None)
        self.trust_evaluator = TrustEvaluator(
            initial_score=self.state.trust_score,
            llm_client=opponent_llm_client,
            use_llm=use_llm,
        )

    def run(self) -> None:
        """Run the full game from start to finish."""
        display.enable_ansi_windows()
        display.clear_screen()
        display.show_banner()
        display.show_rules()

        use_llm = bool(getattr(self.opponent, "use_llm", False))
        llm_client = getattr(self.opponent, "llm_client", None)
        llm_active = bool(llm_client and getattr(llm_client, "available", False))
        display.show_runtime_mode(use_llm=use_llm, llm_active=llm_active)

        input(f"  {display.C.DIM}Press Enter to start the game...{display.C.RESET}")

        while not self.state.is_game_over:
            self._play_round()

        display.show_game_over(
            player_name=self.player.name,
            opponent_name=self.opponent.name,
            player_score=self.state.player_score,
            opponent_score=self.state.opponent_score,
            history=self.state.history,
            final_trust=self.state.trust_score,
            betrayal_count=self.state.betrayal_count,
        )

    def _play_round(self) -> None:
        """Execute a single round of the game."""
        round_num = self.state.current_round
        pot = self.state.pot_per_round

        # ── Round Header ──
        display.clear_screen()
        display.show_round_header(round_num, self.state.total_rounds, pot)

        # ── Negotiation Phase ──
        negotiation_log = self._negotiation_phase()
        player_messages = [
            entry.split(": ", 1)[1]
            for entry in negotiation_log
            if entry.startswith(f"{self.player.name}: ") and ": " in entry
        ]
        previous_player_action = (
            self.state.history[-1].player_action if self.state.history else None
        )

        # ── Decision Phase ──
        display.show_decision_header()
        player_action = self.player.get_action(self.state)
        opponent_action = self.opponent.get_action(self.state)
        opponent_strategy = self.opponent.get_strategy_snapshot() or {}

        # ── Resolution ──
        player_reward, opponent_reward = self._resolve(
            player_action, opponent_action, pot
        )

        trust_update = self.trust_evaluator.evaluate_round(
            player_action=player_action,
            player_messages=player_messages,
            previous_player_action=previous_player_action,
        )

        result = RoundResult(
            round_number=round_num,
            player_action=player_action,
            opponent_action=opponent_action,
            player_reward=player_reward,
            opponent_reward=opponent_reward,
            pot=pot,
            negotiation_log=negotiation_log,
            trust_before=trust_update.previous_score,
            trust_after=trust_update.new_score,
            trust_delta=trust_update.delta,
            betrayal_flag=trust_update.betrayed_promise,
            trust_signals=trust_update.signals,
            ai_personality=opponent_strategy.get("personality", "manipulative"),
            ai_intended_action=str(opponent_strategy.get("intended_action", "SPLIT_LEAN")),
            ai_confidence=float(opponent_strategy.get("confidence", 0.5)),
            ai_risk_level=str(opponent_strategy.get("risk_level", "MEDIUM")),
            ai_steal_probability=float(opponent_strategy.get("steal_probability", 0.5)),
            ai_memory_betrayal_rate=float((opponent_strategy.get("memory") or {}).get("betrayal_rate", 0.0)),
            ai_memory_player_consistency=float((opponent_strategy.get("memory") or {}).get("player_consistency", 0.5)),
        )

        self.state.record_round(result)

        # ── Display Result ──
        display.show_round_result(
            round_num=round_num,
            player_action=player_action,
            opponent_action=opponent_action,
            player_reward=player_reward,
            opponent_reward=opponent_reward,
            player_name=self.player.name,
            opponent_name=self.opponent.name,
            ai_personality=result.ai_personality,
            ai_intended_action=result.ai_intended_action,
            ai_confidence=result.ai_confidence,
            ai_risk_level=result.ai_risk_level,
            ai_steal_probability=result.ai_steal_probability,
        )

        display.show_scoreboard(
            player_name=self.player.name,
            opponent_name=self.opponent.name,
            player_score=self.state.player_score,
            opponent_score=self.state.opponent_score,
            round_num=round_num,
            total_rounds=self.state.total_rounds,
            trust_score=self.state.trust_score,
            betrayal_count=self.state.betrayal_count,
        )

        display.show_trust_update(
            trust_before=result.trust_before,
            trust_after=result.trust_after,
            trust_delta=result.trust_delta,
            trust_signals=result.trust_signals,
            betrayal_flag=result.betrayal_flag,
        )

        # Notify players
        self.player.notify_result(result)
        self.opponent.notify_result(result)

        # Pause before next round
        if not self.state.is_game_over:
            input(f"  {display.C.DIM}Press Enter for next round...{display.C.RESET}")

    def _negotiation_phase(self) -> list[str]:
        """Run the negotiation chat between player and opponent."""
        display.show_negotiation_header()

        log: list[str] = []
        ai_opening = self.opponent.negotiate(self.state, None)
        if ai_opening:
            display.show_ai_message(self.opponent.name, ai_opening)
            log.append(f"{self.opponent.name}: {ai_opening}")

        for _ in range(NEGOTIATION_MESSAGE_LIMIT):
            player_msg = self.player.negotiate(self.state, log[-1] if log else None)
            if not player_msg:
                break

            log.append(f"{self.player.name}: {player_msg}")

            live_trust = self.trust_evaluator.evaluate_message(
                player_msg,
                round_number=self.state.current_round,
            )
            self.state.trust_score = live_trust.new_score
            if live_trust.delta != 0:
                sign = "+" if live_trust.delta > 0 else ""
                print(
                    f"  {display.C.DIM}[Trust update: {live_trust.previous_score} → "
                    f"{live_trust.new_score} ({sign}{live_trust.delta})]{display.C.RESET}"
                )

            ai_msg = self.opponent.negotiate(self.state, player_msg)
            if ai_msg:
                display.show_ai_message(self.opponent.name, ai_msg)
                log.append(f"{self.opponent.name}: {ai_msg}")

        if not log:
            print(f"  {display.C.DIM}(No negotiation this round){display.C.RESET}")

        return log

    @staticmethod
    def _resolve(player_action: PlayerAction, opponent_action: PlayerAction,
                 pot: int) -> tuple[int, int]:
        """Apply the payoff matrix and return (player_reward, opponent_reward)."""
        key = (player_action.value, opponent_action.value)
        player_pct, opponent_pct = PAYOFF_MATRIX[key]
        player_reward = pot * player_pct // 100
        opponent_reward = pot * opponent_pct // 100
        return player_reward, opponent_reward

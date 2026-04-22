import uuid
import sys
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from game.engine import GameEngine
from game.players import RandomAI
from game.models import GameState, RoundResult, PlayerAction
from game.trust import TrustEvaluator

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

load_local_env()

app = FastAPI(title="Split & Steal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

sessions = {}

class StartGameRequest(BaseModel):
    playerName: str
    rounds: int = 5
    pot: int = 300
    personality: str = "cooperative"
    llm: bool = False
    llmModel: Optional[str] = "llama-3.1-8b-instant"

class PlayRoundRequest(BaseModel):
    sessionId: str
    playerMove: str

class NegotiateRequest(BaseModel):
    sessionId: str
    playerMessage: Optional[str] = None

class SessionRequest(BaseModel):
    sessionId: str

@app.post("/start-game")
async def start_game(req: StartGameRequest):
    session_id = str(uuid.uuid4())
    personality = req.personality
    if personality == "random":
        import random
        from game.constants import PERSONALITIES
        personality = random.choice(list(PERSONALITIES.keys()))

    llm_enabled = req.llm
    if not llm_enabled and (os.getenv("GROQ_API_KEY") or os.getenv("GROK_API_KEY")):
        llm_enabled = True

    try:
        opponent = RandomAI(
            name="AI Opponent",
            personality=personality,
            use_llm=llm_enabled,
            llm_model=req.llmModel
        )
        game_state = GameState(
            total_rounds=req.rounds,
            pot_per_round=req.pot,
        )
        trust_evaluator = TrustEvaluator(
            initial_score=game_state.trust_score,
            llm_client=getattr(opponent, "llm_client", None),
            use_llm=llm_enabled
        )
        
        sessions[session_id] = {
            "opponent": opponent,
            "game_state": game_state,
            "trust_evaluator": trust_evaluator,
            "round_player_messages": [],
            "previous_action": None,
            "player_name": req.playerName,
            "personality": personality,
        }
        
        print(f"Started session {session_id} for {req.playerName} (LLM: {llm_enabled})")

        return {
            "ok": True,
            "sessionId": session_id,
            "state": {
                "playerName": req.playerName,
                "rounds": req.rounds,
                "pot": req.pot,
                "personality": personality,
                "currentRound": 1,
                "playerScore": 0,
                "aiScore": 0,
                "trustLevel": 50
            }
        }
    except Exception as e:
        print(f"Error in start_game: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/negotiate")
async def negotiate(req: NegotiateRequest):
    if req.sessionId not in sessions:
        return {"ok": False, "error": "Session not found"}
        
    try:
        s = sessions[req.sessionId]
        game_state = s["game_state"]
        opponent = s["opponent"]
        trust_evaluator = s["trust_evaluator"]
        
        # If the player sent a message, evaluate trust
        if req.playerMessage:
            s["round_player_messages"].append(req.playerMessage)
            live_trust = trust_evaluator.evaluate_message(
                req.playerMessage,
                round_number=game_state.current_round
            )
            game_state.trust_score = live_trust.new_score
            
        ai_msg = opponent.negotiate(game_state, req.playerMessage)
        strategy = opponent.get_strategy_snapshot() or {}
        
        return {
            "ok": True,
            "aiMessage": ai_msg,
            "trustScore": game_state.trust_score,
            "prediction": strategy.get("prediction")
        }

    except Exception as e:
        print(f"Error in negotiate: {e}")
        return {"ok": False, "error": str(e)}


@app.post("/play-round")
async def play_round(req: PlayRoundRequest):
    if req.sessionId not in sessions:
        return {"ok": False, "error": "Session not found"}
        
    try:
        s = sessions[req.sessionId]
        game_state = s["game_state"]
        opponent = s["opponent"]
        trust_evaluator = s["trust_evaluator"]
        
        player_move_str = req.playerMove.lower().strip()
        player_action = PlayerAction.SPLIT if player_move_str == "split" else PlayerAction.STEAL
        
        print(f"Playing round {game_state.current_round} for {req.sessionId}. Move: {player_action}")
        
        opponent_action = opponent.get_action(game_state)
        opponent_strategy = opponent.get_strategy_snapshot() or {}
        
        player_reward, opponent_reward = GameEngine._resolve(
            player_action, opponent_action, game_state.pot_per_round
        )
        
        trust_update = trust_evaluator.evaluate_round(
            player_action=player_action,
            player_messages=s["round_player_messages"],
            previous_player_action=s["previous_action"]
        )
        
        result = RoundResult(
            round_number=game_state.current_round,
            player_action=player_action,
            opponent_action=opponent_action,
            player_reward=player_reward,
            opponent_reward=opponent_reward,
            pot=game_state.pot_per_round,
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
        
        game_state.record_round(result)
        opponent.notify_result(result)
        
        # Reset for next round
        s["round_player_messages"] = []
        s["previous_action"] = player_action
        
        print(f"Round {result.round_number} complete. AI move: {opponent_action}")

        return {
            "ok": True,
            "aiMove": opponent_action.value.lower(),
            "playerGain": player_reward,
            "aiGain": opponent_reward,
            "trustScore": game_state.trust_score,
            "strategy": {
                "personality": result.ai_personality,
                "intendedAction": result.ai_intended_action,
                "confidence": result.ai_confidence,
                "riskLevel": result.ai_risk_level,
                "stealProbability": result.ai_steal_probability,
                "betrayal": result.betrayal_flag,
                "prediction": opponent_strategy.get("prediction")
            }

        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error in play_round: {e}")
        return {"ok": False, "error": str(e)}


@app.get("/get-state")
async def get_state(session_id: str):
    if session_id not in sessions:
        return {"ok": False, "error": "Session not found"}
    s = sessions[session_id]
    gs = s["game_state"]
    return {
        "ok": True, 
        "state": {
            "currentRound": gs.current_round,
            "playerScore": gs.player_score,
            "aiScore": gs.opponent_score,
            "trustLevel": gs.trust_score
        }
    }

@app.post("/end-game")
async def end_game(req: SessionRequest):
    sessions.pop(req.sessionId, None)
    return {"ok": True}

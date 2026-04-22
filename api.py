import uuid
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from game.engine import GameEngine
from game.players import RandomAI
from game.models import GameState, RoundResult, PlayerAction
from game.trust import TrustEvaluator

app = FastAPI(title="Split & Steal API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

sessions = {}

class StartGameRequest(BaseModel):
    player_name: str
    rounds: int = 5
    pot: int = 300
    personality: str = "cooperative"
    llm: bool = False

class PlayRoundRequest(BaseModel):
    session_id: str
    player_move: str

class NegotiateRequest(BaseModel):
    session_id: str
    player_message: Optional[str] = None

class SessionRequest(BaseModel):
    session_id: str

@app.post("/start-game")
async def start_game(req: StartGameRequest):
    session_id = str(uuid.uuid4())
    opponent = RandomAI(
        name="AI Opponent",
        personality=req.personality,
        use_llm=req.llm
    )
    game_state = GameState(
        total_rounds=req.rounds,
        pot_per_round=req.pot,
    )
    trust_evaluator = TrustEvaluator(
        initial_score=game_state.trust_score,
        llm_client=getattr(opponent, "llm_client", None),
        use_llm=req.llm
    )
    
    sessions[session_id] = {
        "opponent": opponent,
        "game_state": game_state,
        "trust_evaluator": trust_evaluator,
        "round_player_messages": [],
        "previous_action": None,
        "player_name": req.player_name,
    }
    
    return {
        "ok": True,
        "sessionId": session_id,
        "state": {
            "playerName": req.player_name,
            "rounds": req.rounds,
            "pot": req.pot,
            "personality": req.personality,
            "currentRound": 1,
            "playerScore": 0,
            "aiScore": 0,
            "trustLevel": 50
        }
    }

@app.post("/negotiate")
async def negotiate(req: NegotiateRequest):
    if req.session_id not in sessions:
        return {"ok": False, "error": "Session not found"}
        
    s = sessions[req.session_id]
    game_state = s["game_state"]
    opponent = s["opponent"]
    trust_evaluator = s["trust_evaluator"]
    
    # If the player sent a message, evaluate trust
    if req.player_message:
        s["round_player_messages"].append(req.player_message)
        live_trust = trust_evaluator.evaluate_message(
            req.player_message,
            round_number=game_state.current_round
        )
        game_state.trust_score = live_trust.new_score
        
    ai_msg = opponent.negotiate(game_state, req.player_message)
    
    return {
        "ok": True,
        "aiMessage": ai_msg,
        "trustScore": game_state.trust_score
    }

@app.post("/play-round")
async def play_round(req: PlayRoundRequest):
    if req.session_id not in sessions:
        return {"ok": False, "error": "Session not found"}
        
    s = sessions[req.session_id]
    game_state = s["game_state"]
    opponent = s["opponent"]
    trust_evaluator = s["trust_evaluator"]
    
    player_action = PlayerAction.SPLIT if req.player_move.lower() == "split" else PlayerAction.STEAL
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
    
    return {
        "ok": True,
        "aiMove": opponent_action.value.lower(),
        "playerGain": player_reward,
        "aiGain": opponent_reward,
        "trustScore": game_state.trust_score
    }

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
    sessions.pop(req.session_id, None)
    return {"ok": True}

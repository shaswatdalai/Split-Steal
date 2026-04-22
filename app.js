/* ═══════════════════════════════════════════════════════════
   app.js — Game Engine, Mock Backend, FastAPI Integration
═══════════════════════════════════════════════════════════ */

'use strict';

/* ════════════════════════════════════════════════════════
   ██████╗  ██████╗ ███╗   ██╗███████╗██╗ ██████╗
   ██╔════╝██╔═══██╗████╗  ██║██╔════╝██║██╔════╝
   ██║     ██║   ██║██╔██╗ ██║█████╗  ██║██║  ███╗
   ██║     ██║   ██║██║╚██╗██║██╔══╝  ██║██║   ██║
   ╚██████╗╚██████╔╝██║ ╚████║██║     ██║╚██████╔╝
    ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝     ╚═╝ ╚═════╝
════════════════════════════════════════════════════════ */

/* ─── CONFIG ─────────────────────────────────────── */
const USE_REAL_BACKEND = true;            // Set true to use FastAPI
const API_BASE = 'http://localhost:8000'; // FastAPI URL

/* ─── GAME STATE ─────────────────────────────────── */
let gameState = {
    playerName: 'AGENT',
    rounds: 5,
    pot: 300,
    personality: 'cooperative',
    llm: false,
    currentRound: 1,
    playerScore: 0,
    aiScore: 0,
    trustLevel: 50,
    trustHistory: [],
    playerMoves: [],
    aiMoves: [],
    playerRoundScores: [],
    aiRoundScores: [],
    sessionId: null,
    waitingForAI: false,
    gameOver: false,
};

/* ═══════════════════════════════════════════════════
   MOCK BACKEND (pure JS — no server needed)
═══════════════════════════════════════════════════ */
const MockBackend = (() => {

    function aiDecide(personality, playerHistory, round) {
        switch (personality) {
            case 'cooperative':
                // 80% split, 20% steal — slightly more likely to copy player's last move
                if (playerHistory.length && playerHistory[playerHistory.length - 1] === 'steal')
                    return Math.random() < .55 ? 'steal' : 'split';
                return Math.random() < .82 ? 'split' : 'steal';

            case 'greedy':
                // 85% steal
                return Math.random() < .85 ? 'steal' : 'split';

            case 'balanced':
                // Tit-for-tat: copy last player move
                if (playerHistory.length === 0) return 'split';
                return playerHistory[playerHistory.length - 1];

            case 'random':
                return Math.random() < .5 ? 'split' : 'steal';

            default:
                return Math.random() < .6 ? 'split' : 'steal';
        }
    }

    function calcPayout(playerMove, aiMove, pot) {
        if (playerMove === 'split' && aiMove === 'split')
            return { player: Math.floor(pot / 2), ai: Math.floor(pot / 2) };
        if (playerMove === 'steal' && aiMove === 'steal')
            return { player: 0, ai: 0 };
        if (playerMove === 'steal' && aiMove === 'split')
            return { player: pot, ai: 0 };
        // player split, ai steal
        return { player: 0, ai: pot };
    }

    async function startGame(settings) {
        return {
            ok: true,
            sessionId: 'mock-' + Date.now(),
            state: { ...settings, currentRound: 1, playerScore: 0, aiScore: 0 },
        };
    }

    async function playRound(sessionId, playerMove, state) {
        // Simulate AI "thinking" delay
        await delay(900 + Math.random() * 800);

        const aiMove = aiDecide(state.personality, state.playerMoves, state.currentRound);
        const payout = calcPayout(playerMove, aiMove, state.pot);

        return {
            ok: true,
            aiMove,
            playerGain: payout.player,
            aiGain: payout.ai,
        };
    }

    async function getState(sessionId) {
        return { ok: true, state: { ...gameState } };
    }

    async function endGame(sessionId) {
        return { ok: true };
    }

    async function negotiate(sessionId, playerMessage) {
        await delay(600);
        return { ok: true, aiMessage: playerMessage ? "I hear you, but trust is earned." : "Let's work together. I will split.", trustScore: 50 };
    }

    return { startGame, playRound, getState, endGame, negotiate };
})();

/* ═══════════════════════════════════════════════════
   REAL BACKEND (FastAPI — set USE_REAL_BACKEND=true)
═══════════════════════════════════════════════════ */
const RealBackend = (() => {
    async function post(endpoint, body) {
        const res = await fetch(API_BASE + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    }

    async function get(endpoint) {
        const res = await fetch(API_BASE + endpoint);
        if (!res.ok) throw new Error(`API error: ${res.status}`);
        return res.json();
    }

    async function startGame(settings) {
        return post('/start-game', settings);
    }

    async function playRound(sessionId, playerMove, state) {
        return post('/play-round', { session_id: sessionId, player_move: playerMove });
    }

    async function getState(sessionId) {
        return get(`/get-state?session_id=${sessionId}`);
    }

    async function negotiate(sessionId, playerMessage) {
        return post('/negotiate', { session_id: sessionId, player_message: playerMessage || null });
    }

    return { startGame, playRound, getState, endGame, negotiate };
})();

/* ─── BACKEND SELECTOR ───────────────────────────── */
const Backend = USE_REAL_BACKEND ? RealBackend : MockBackend;

/* ═══════════════════════════════════════════════════
   GAME CONTROLLER
═══════════════════════════════════════════════════ */
const Game = (() => {

    async function start(settings) {
        // Reset state
        Object.assign(gameState, {
            ...settings,
            currentRound: 1,
            playerScore: 0,
            aiScore: 0,
            trustLevel: 50,
            trustHistory: [],
            playerMoves: [],
            aiMoves: [],
            playerRoundScores: [],
            aiRoundScores: [],
            waitingForAI: false,
            gameOver: false,
        });

        try {
            const res = await Backend.startGame(settings);
            if (res.ok) gameState.sessionId = res.sessionId;
        } catch (e) {
            console.warn('Backend start error, using local state:', e);
        }

        // Initialize UI
        TrustMeter.reset();
        ResultDisplay.reset();
        HistoryChips.clear('player-history');
        HistoryChips.clear('ai-history');
        ScorePanel.update(0, 0);
        HUD.update(1, gameState.rounds, gameState.pot, gameState.personality);
        const pName = document.getElementById('display-player-name');
        if (pName) pName.textContent = gameState.playerName.toUpperCase();

        const aiIcon = document.getElementById('ai-icon');
        if (aiIcon) aiIcon.textContent = AIAvatar.getIcon(gameState.personality);

        // Initial chart
        drawTrustChart();

        ScreenManager.show('screen-game');
        startRound();
    }

    async function startRound() {
        ChatUI.clear();
        ChatUI.show(true);
        ChatUI.setStatus('NEGOTIATION PHASE', 'var(--neon-green)');
        setDecisionsEnabled(false);
        showNextRoundBtn(false);

        ChatUI.setEnabled(false);
        ResultDisplay.showThinking();

        try {
            const res = await Backend.negotiate(gameState.sessionId, null);
            if (res && res.aiMessage) {
                ChatUI.addMessage('ai', res.aiMessage);
            }
        } catch (e) {
            console.error('Initial negotiate error:', e);
        }

        ChatUI.setEnabled(true);
        ResultDisplay.reset();
    }

    async function sendChat() {
        const msg = ChatUI.getAndClearInput();
        if (!msg) return;

        ChatUI.addMessage('player', msg);
        ChatUI.setEnabled(false);
        ResultDisplay.showThinking();

        try {
            const res = await Backend.negotiate(gameState.sessionId, msg);
            if (res.ok) {
                if (res.trustScore !== undefined) {
                    TrustMeter.setTrust(res.trustScore);
                    gameState.trustLevel = res.trustScore;
                    gameState.trustHistory[gameState.trustHistory.length - 1] = res.trustScore;
                    drawTrustChart();
                }
                if (res.aiMessage) {
                    ChatUI.addMessage('ai', res.aiMessage);
                }
            }
        } catch (e) {
            console.error('Chat error', e);
        }

        ChatUI.setEnabled(true);
        ResultDisplay.reset();
        document.getElementById('chat-input')?.focus();
    }

    function endNegotiation() {
        ChatUI.show(false);
        setDecisionsEnabled(true);
        ResultDisplay.reset();
        const idleText = document.querySelector('.result-idle-text');
        if (idleText) idleText.textContent = 'WAITING FOR DECISION...';
    }

    async function playRound(playerMove) {
        if (gameState.waitingForAI || gameState.gameOver) return;
        gameState.waitingForAI = true;

        setDecisionsEnabled(false);
        ResultDisplay.showThinking();
        AIAvatar.startThinking();

        let aiMove, playerGain, aiGain;

        try {
            const res = await Backend.playRound(gameState.sessionId, playerMove, gameState);
            aiMove = res.aiMove;
            playerGain = res.playerGain;
            aiGain = res.aiGain;
        } catch (e) {
            console.error('Round error:', e);
            gameState.waitingForAI = false;
            setDecisionsEnabled(true);
            ResultDisplay.reset();
            AIAvatar.stopThinking(gameState.personality);
            return;
        }

        // Update state
        gameState.playerMoves.push(playerMove);
        gameState.aiMoves.push(aiMove);
        gameState.playerScore += playerGain;
        gameState.aiScore += aiGain;
        gameState.playerRoundScores.push(playerGain);
        gameState.aiRoundScores.push(aiGain);

        // Trust update
        if (res && res.trustScore !== undefined) {
            gameState.trustLevel = res.trustScore;
            TrustMeter.setTrust(res.trustScore);
        } else {
            TrustMeter.updateFromMoves(playerMove, aiMove);
            gameState.trustLevel = TrustMeter.get();
        }
        gameState.trustHistory.push(gameState.trustLevel);

        // Update UI
        AIAvatar.stopThinking(gameState.personality);
        HistoryChips.add('player-history', playerMove);
        HistoryChips.add('ai-history', aiMove);
        ScorePanel.update(gameState.playerScore, gameState.aiScore);
        HUD.update(gameState.currentRound, gameState.rounds, gameState.pot, gameState.personality);

        const deltaText = buildDeltaText(playerMove, aiMove, playerGain, aiGain);
        ResultDisplay.showResult(playerMove, aiMove, null, deltaText);
        drawTrustChart();

        gameState.waitingForAI = false;

        if (gameState.currentRound >= gameState.rounds) {
            gameState.gameOver = true;
            showNextRoundBtn(true, true);
        } else {
            gameState.currentRound++;
            HUD.update(gameState.currentRound, gameState.rounds, gameState.pot, gameState.personality);
            showNextRoundBtn(true, false);
        }
    }

    function buildDeltaText(playerMove, aiMove, playerGain, aiGain) {
        if (playerMove === 'split' && aiMove === 'split')
            return `You earned ¢${playerGain}  ·  AI earned ¢${aiGain}`;
        if (playerMove === 'steal' && aiMove === 'steal')
            return `Nobody earns anything this round`;
        if (playerMove === 'steal' && aiMove === 'split')
            return `You take ¢${playerGain}  ·  AI loses everything`;
        return `AI takes ¢${aiGain}  ·  You are left with nothing`;
    }

    function nextRound() {
        showNextRoundBtn(false);
        ResultDisplay.reset();
        startRound();
    }

    function endGame() {
        // Build final screen
        const p = gameState;
        WinnerBanner.show(p.playerName, p.playerScore, p.aiScore, `${p.personality.toUpperCase()} AI`);
        ScorePanel.updateFinal(p.playerScore, p.aiScore, p.playerName, `${p.personality.toUpperCase()} AI`);

        const playerSplits = p.playerMoves.filter(m => m === 'split').length;
        const playerSteals = p.playerMoves.filter(m => m === 'steal').length;
        const aiSplits = p.aiMoves.filter(m => m === 'split').length;
        const aiSteals = p.aiMoves.filter(m => m === 'steal').length;

        buildStatBars('stat-player-bars', playerSplits, playerSteals, p.rounds);
        buildStatBars('stat-ai-bars', aiSplits, aiSteals, p.rounds);
        buildResultMessage(p.playerName, p.playerScore, p.aiScore, p.trustLevel, p.rounds);

        // Final chart
        setTimeout(() => {
            const fc = document.getElementById('final-chart');
            if (fc) BarChart.draw(fc, p.playerRoundScores, p.aiRoundScores);
        }, 100);

        ScreenManager.show('screen-results');

        try { Backend.endGame(gameState.sessionId); } catch (e) { }
    }

    function drawTrustChart() {
        const canvas = document.getElementById('trust-chart');
        if (canvas) TrustChart.draw(canvas, gameState.trustHistory, gameState.rounds);
    }

    function setDecisionsEnabled(enabled) {
        const btnSplit = document.getElementById('btn-split');
        const btnSteal = document.getElementById('btn-steal');
        const da = document.getElementById('decision-area');
        if (btnSplit) btnSplit.disabled = !enabled;
        if (btnSteal) btnSteal.disabled = !enabled;
        if (da) da.style.opacity = enabled ? '1' : '.4';
    }

    function showNextRoundBtn(show, isFinal = false) {
        const nra = document.getElementById('next-round-area');
        const da = document.getElementById('decision-area');
        const btn = document.getElementById('btn-next-round');

        if (!nra) return;
        if (show) {
            nra.classList.remove('hidden');
            if (da) da.classList.add('hidden');
            if (btn) btn.querySelector('.btn-text').textContent = isFinal ? '▶ SEE RESULTS' : '▶ NEXT ROUND';
        } else {
            nra.classList.add('hidden');
            if (da) da.classList.remove('hidden');
        }
    }

    return { start, playRound, nextRound, endGame, sendChat, endNegotiation };
})();

/* ═══════════════════════════════════════════════════
   LANDING TYPING SUBTITLES
═══════════════════════════════════════════════════ */
const SUBTITLES = [
    'GAME THEORY SIMULATION LOADED',
    'TRUST IS A VULNERABILITY',
    'COOPERATE. DEFECT. SURVIVE.',
    'EVERY ROUND REWRITES THE DEAL',
];

function startSubtitleCycle() {
    const el = document.getElementById('typing-subtitle');
    if (!el) return;
    let idx = 0;
    function next() {
        Typer.type(el, SUBTITLES[idx++ % SUBTITLES.length], 45, () => {
            setTimeout(() => {
                // Erase
                let text = el.textContent;
                const eraser = setInterval(() => {
                    text = text.slice(0, -1);
                    el.textContent = text;
                    if (!text.length) { clearInterval(eraser); setTimeout(next, 400); }
                }, 28);
            }, 2200);
        });
    }
    setTimeout(next, 600);
}

/* ═══════════════════════════════════════════════════
   EVENT LISTENERS
═══════════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', () => {

    /* Boot */
    ParticleSystem.init();
    startSubtitleCycle();

    /* Ripple effects */
    document.querySelectorAll('.btn-primary, .btn-secondary, .btn-decision').forEach(addRipple);

    /* Landing → Start */
    document.getElementById('btn-start')?.addEventListener('click', () => {
        const nameInput = document.getElementById('player-name');
        const name = nameInput?.value?.trim() || 'AGENT';
        const settings = SettingsPanel.getSettings();
        Game.start({ playerName: name, ...settings });
    });

    /* Enter key on name input */
    document.getElementById('player-name')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') document.getElementById('btn-start')?.click();
    });

    /* Settings open/close */
    document.getElementById('btn-settings')?.addEventListener('click', () => SettingsPanel.open());
    document.getElementById('btn-close-settings')?.addEventListener('click', () => SettingsPanel.close());
    document.getElementById('btn-save-settings')?.addEventListener('click', () => SettingsPanel.close());

    /* Decision buttons */
    document.getElementById('btn-split')?.addEventListener('click', () => Game.playRound('split'));
    document.getElementById('btn-steal')?.addEventListener('click', () => Game.playRound('steal'));

    /* Chat buttons */
    document.getElementById('btn-chat-send')?.addEventListener('click', () => Game.sendChat());
    document.getElementById('btn-chat-skip')?.addEventListener('click', () => Game.endNegotiation());

    /* Enter key on chat input */
    document.getElementById('chat-input')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') document.getElementById('btn-chat-send')?.click();
    });

    /* Next round / final */
    document.getElementById('btn-next-round')?.addEventListener('click', () => {
        if (gameState.gameOver) {
            Game.endGame();
        } else {
            Game.nextRound();
        }
    });

    /* Results → restart / home */
    document.getElementById('btn-restart')?.addEventListener('click', () => {
        const nameInput = document.getElementById('player-name');
        const name = nameInput?.value?.trim() || gameState.playerName;
        const settings = SettingsPanel.getSettings();
        Game.start({ playerName: name, ...settings });
    });

    document.getElementById('btn-home')?.addEventListener('click', () => {
        ScreenManager.show('screen-landing');
        startSubtitleCycle();
    });

    /* Keyboard shortcuts */
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && SettingsPanel.isVisible()) SettingsPanel.close();
        // S = split, T = steal during game
        const gameScreen = document.getElementById('screen-game');
        if (!gameScreen?.classList.contains('active')) return;
        if (e.key === 's' || e.key === 'S') document.getElementById('btn-split')?.click();
        if (e.key === 't' || e.key === 'T') document.getElementById('btn-steal')?.click();
    });

    // Resize redraw charts
    window.addEventListener('resize', () => {
        const canvas = document.getElementById('trust-chart');
        if (canvas && gameState.trustHistory.length) {
            TrustChart.draw(canvas, gameState.trustHistory, gameState.rounds);
        }
    });
});

/* ════════════════════════════════════════════════════════

   ██████╗  █████╗  ██████╗██╗  ██╗███████╗███╗   ██╗██████╗
   ██╔══██╗██╔══██╗██╔════╝██║ ██╔╝██╔════╝████╗  ██║██╔══██╗
   ██████╔╝███████║██║     █████╔╝ █████╗  ██╔██╗ ██║██║  ██║
   ██╔══██╗██╔══██║██║     ██╔═██╗ ██╔══╝  ██║╚██╗██║██║  ██║
   ██████╔╝██║  ██║╚██████╗██║  ██╗███████╗██║ ╚████║██████╔╝
   ╚═════╝ ╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝╚═════╝
   FastAPI INTEGRATION GUIDE
════════════════════════════════════════════════════════

─── STEP 1: Install dependencies ───────────────────────
  pip install fastapi uvicorn pydantic

─── STEP 2: backend/api.py ─────────────────────────────

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid, sys

# Import your existing game engine
sys.path.append('..')
from game_engine import GameEngine
from players import HumanPlayer, RandomAI
from constants import DEFAULT_POT, DEFAULT_ROUNDS

app = FastAPI(title="Split & Steal API")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"])

sessions = {}   # session_id -> game state dict

class StartGameRequest(BaseModel):
    player_name: str
    rounds: int = 5
    pot: int = 300
    personality: str = "cooperative"
    llm: bool = False

class PlayRoundRequest(BaseModel):
    session_id: str
    player_move: str   # "split" or "steal"

class SessionRequest(BaseModel):
    session_id: str

@app.post("/start-game")
async def start_game(req: StartGameRequest):
    session_id = str(uuid.uuid4())
    engine = GameEngine(
        player=HumanPlayer(req.player_name),
        ai=RandomAI(personality=req.personality),
        rounds=req.rounds,
        pot=req.pot,
        use_llm=req.llm
    )
    sessions[session_id] = {
        "engine": engine,
        "player_name": req.player_name,
        "rounds": req.rounds,
        "pot": req.pot,
        "personality": req.personality,
        "current_round": 1,
        "player_score": 0,
        "ai_score": 0,
    }
    return {
        "ok": True,
        "sessionId": session_id,
        "state": sessions[session_id]
    }

@app.post("/play-round")
async def play_round(req: PlayRoundRequest):
    if req.session_id not in sessions:
        return {"ok": False, "error": "Session not found"}
    s = sessions[req.session_id]
    engine = s["engine"]
    # Get AI move from engine
    ai_move = engine.get_ai_move(req.player_move)
    payouts = engine.calculate_payout(req.player_move, ai_move)
    s["player_score"] += payouts["player"]
    s["ai_score"]     += payouts["ai"]
    s["current_round"] += 1
    return {
        "ok": True,
        "aiMove": ai_move,
        "playerGain": payouts["player"],
        "aiGain": payouts["ai"],
    }

@app.get("/get-state")
async def get_state(session_id: str):
    if session_id not in sessions:
        return {"ok": False, "error": "Session not found"}
    s = {k: v for k, v in sessions[session_id].items() if k != "engine"}
    return {"ok": True, "state": s}

@app.post("/end-game")
async def end_game(req: SessionRequest):
    sessions.pop(req.session_id, None)
    return {"ok": True}

─── STEP 3: Run server ────────────────────────────────
  uvicorn backend.api:app --reload --port 8000

─── STEP 4: Enable in frontend ───────────────────────
  At the top of app.js, change:
    const USE_REAL_BACKEND = true;

─── API ENDPOINTS ─────────────────────────────────────
  POST /start-game    { player_name, rounds, pot, personality, llm }
  POST /play-round    { session_id, player_move }
  GET  /get-state     ?session_id=...
  POST /end-game      { session_id }

════════════════════════════════════════════════════════ */
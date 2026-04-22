/* ═══════════════════════════════════════════════════════════
   ui.js — UI component controllers
═══════════════════════════════════════════════════════════ */

'use strict';

/* ─── TRUST METER ────────────────────────────────── */
const TrustMeter = (() => {
    let trustLevel = 50;
    const fill = document.getElementById('trust-fill');
    const glow = document.getElementById('trust-glow');
    const pctEl = document.getElementById('trust-pct');

    function setTrust(val, animate = true) {
        trustLevel = Math.max(0, Math.min(100, val));
        const pct = trustLevel;

        if (fill) {
            fill.style.width = pct + '%';
            // Shift gradient position: 0 = red end, 100 = green end
            fill.style.backgroundPosition = `${100 - pct}% 0`;
        }
        if (pctEl) pctEl.textContent = pct + '%';

        if (pctEl) {
            if (pct >= 65) {
                pctEl.style.color = 'var(--neon-green)';
            } else if (pct >= 35) {
                pctEl.style.color = 'var(--neon-yellow)';
            } else {
                pctEl.style.color = 'var(--neon-red)';
            }
        }
    }

    function pulse(active) {
        if (!glow) return;
        if (active) {
            glow.classList.add('pulsing');
        } else {
            glow.classList.remove('pulsing');
        }
    }

    function updateFromMoves(playerMove, aiMove) {
        let delta = 0;
        if (playerMove === 'split' && aiMove === 'split') delta = +14;
        if (playerMove === 'steal' && aiMove === 'steal') delta = -12;
        if (playerMove === 'split' && aiMove === 'steal') delta = -18;
        if (playerMove === 'steal' && aiMove === 'split') delta = -6;
        setTrust(trustLevel + delta);
    }

    function reset() { setTrust(50); }

    return { setTrust, pulse, updateFromMoves, reset, get: () => trustLevel };
})();

/* ─── SCORE PANEL ────────────────────────────────── */
const ScorePanel = (() => {
    function update(playerScore, aiScore) {
        const ps = document.getElementById('player-score');
        const as = document.getElementById('ai-score');
        if (ps) ps.textContent = '¢ ' + playerScore;
        if (as) as.textContent = '¢ ' + aiScore;

        // Pulse whichever changed
        [ps, as].forEach(el => {
            if (!el) return;
            el.style.transform = 'scale(1.25)';
            el.style.transition = 'transform .2s';
            setTimeout(() => { el.style.transform = 'scale(1)'; }, 220);
        });
    }

    function updateFinal(playerScore, aiScore, playerName, aiName) {
        const sp = document.getElementById('stat-player-score');
        const sa = document.getElementById('stat-ai-score');
        const sn = document.getElementById('stat-player-name');
        const an = document.getElementById('stat-ai-name');
        if (sp) sp.textContent = '¢ ' + playerScore;
        if (sa) { sa.textContent = '¢ ' + aiScore; sa.style.color = 'var(--neon-red)'; sa.style.textShadow = '0 0 20px rgba(255,42,94,.5)'; }
        if (sn) sn.textContent = playerName;
        if (an) an.textContent = aiName;
    }

    return { update, updateFinal };
})();

/* ─── HISTORY CHIPS ──────────────────────────────── */
const HistoryChips = (() => {
    function add(containerId, move) {
        const container = document.getElementById(containerId);
        if (!container) return;
        const chip = document.createElement('div');
        chip.className = `history-chip ${move}`;
        chip.textContent = move === 'split' ? '🤝 S' : '⚔️ T';
        container.appendChild(chip);
    }

    function clear(containerId) {
        const el = document.getElementById(containerId);
        if (el) el.innerHTML = '';
    }

    return { add, clear };
})();

/* ─── RESULT DISPLAY ─────────────────────────────── */
const ResultDisplay = (() => {
    function showThinking() {
        const idle = document.getElementById('result-idle');
        const reveal = document.getElementById('result-reveal');
        const dots = document.getElementById('thinking-dots');
        const idleText = document.querySelector('.result-idle-text');

        if (reveal) reveal.classList.add('hidden');
        if (idle) idle.style.display = 'block';
        if (idleText) idleText.textContent = 'OPPONENT CALCULATING...';
        if (dots) dots.classList.add('active');
        TrustMeter.pulse(true);
    }

    function showResult(playerMove, aiMove, outcome, deltaText) {
        const idle = document.getElementById('result-idle');
        const reveal = document.getElementById('result-reveal');
        const pChoice = document.getElementById('r-player-choice');
        const aChoice = document.getElementById('r-ai-choice');
        const outcomeEl = document.getElementById('result-outcome');
        const deltaEl = document.getElementById('result-delta');
        const dots = document.getElementById('thinking-dots');

        if (idle) idle.style.display = 'none';
        if (dots) dots.classList.remove('active');
        TrustMeter.pulse(false);

        if (pChoice) {
            pChoice.className = `choice-box ${playerMove}`;
            pChoice.innerHTML = `<div style="font-size:.65rem;opacity:.6;margin-bottom:4px">YOU</div>${playerMove === 'split' ? '🤝 SPLIT' : '⚔️ STEAL'}`;
        }
        if (aChoice) {
            aChoice.className = `choice-box ${aiMove}`;
            aChoice.innerHTML = `<div style="font-size:.65rem;opacity:.6;margin-bottom:4px">AI</div>${aiMove === 'split' ? '🤝 SPLIT' : '⚔️ STEAL'}`;
        }

        if (outcomeEl) {
            const { text, color } = getOutcomeStyle(playerMove, aiMove);
            outcomeEl.textContent = text;
            outcomeEl.style.color = color;
            outcomeEl.style.textShadow = `0 0 20px ${color}`;
        }
        if (deltaEl) deltaEl.textContent = deltaText;

        if (reveal) reveal.classList.remove('hidden');
    }

    function getOutcomeStyle(playerMove, aiMove) {
        if (playerMove === 'split' && aiMove === 'split')
            return { text: '✦ MUTUAL COOPERATION', color: 'var(--neon-green)' };
        if (playerMove === 'steal' && aiMove === 'steal')
            return { text: '✖ MUTUAL BETRAYAL', color: 'var(--neon-red)' };
        if (playerMove === 'split' && aiMove === 'steal')
            return { text: '⚠ YOU WERE BETRAYED', color: 'var(--neon-red)' };
        return { text: '◆ YOU DEFECTED', color: 'var(--neon-yellow)' };
    }

    function reset() {
        const idle = document.getElementById('result-idle');
        const reveal = document.getElementById('result-reveal');
        const idleText = document.querySelector('.result-idle-text');
        const dots = document.getElementById('thinking-dots');

        if (reveal) reveal.classList.add('hidden');
        if (idle) idle.style.display = 'block';
        if (idleText) idleText.textContent = 'AWAITING DECISION...';
        if (dots) dots.classList.remove('active');
        TrustMeter.pulse(false);
    }

    return { showThinking, showResult, reset };
})();

/* ─── HUD ────────────────────────────────────────── */
const HUD = (() => {
    function update(round, totalRounds, pot, personality) {
        const r = document.getElementById('hud-round');
        const p = document.getElementById('hud-pot');
        const pe = document.getElementById('hud-personality');
        if (r) r.textContent = `${round} / ${totalRounds}`;
        if (p) p.textContent = `¢ ${pot}`;
        if (pe) pe.textContent = personality.toUpperCase();
    }
    return { update };
})();

/* ─── SETTINGS PANEL ─────────────────────────────── */
const SettingsPanel = (() => {
    let visible = false;
    const modal = document.getElementById('modal-settings');

    function open() {
        visible = true;
        modal.classList.remove('hidden');
    }

    function close() {
        visible = false;
        modal.classList.add('hidden');
    }

    function isVisible() { return visible; }

    // Slider live-update
    const sliderRounds = document.getElementById('setting-rounds');
    const sliderPot = document.getElementById('setting-pot');
    const roundsVal = document.getElementById('rounds-val');
    const potVal = document.getElementById('pot-val');

    if (sliderRounds) sliderRounds.addEventListener('input', () => {
        if (roundsVal) roundsVal.textContent = sliderRounds.value;
    });
    if (sliderPot) sliderPot.addEventListener('input', () => {
        if (potVal) potVal.textContent = sliderPot.value;
    });

    // Personality cards
    const pcards = document.querySelectorAll('.personality-card');
    const tooltip = document.getElementById('p-tooltip');
    pcards.forEach(card => {
        card.addEventListener('click', () => {
            pcards.forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            if (tooltip) tooltip.textContent = card.dataset.tip || '';
        });
        card.addEventListener('mouseenter', () => {
            if (tooltip) tooltip.textContent = card.dataset.tip || '';
        });
        card.addEventListener('mouseleave', () => {
            const active = document.querySelector('.personality-card.active');
            if (tooltip && active) tooltip.textContent = active.dataset.tip || '';
        });
    });

    function getSettings() {
        const activeP = document.querySelector('.personality-card.active');
        return {
            rounds: parseInt(sliderRounds?.value || '5'),
            pot: parseInt(sliderPot?.value || '300'),
            personality: activeP?.dataset.val || 'cooperative',
            llm: document.getElementById('setting-llm')?.checked || false,
        };
    }

    // Close on overlay click
    if (modal) modal.addEventListener('click', (e) => {
        if (e.target === modal) close();
    });

    return { open, close, isVisible, getSettings };
})();

/* ─── AI AVATAR THINKING ─────────────────────────── */
const AIAvatar = (() => {
    const icon = document.getElementById('ai-icon');
    let thinkInterval = null;
    const thinkFrames = ['🤖', '💭', '🤔', '⚡', '🧠'];
    let frameIdx = 0;

    function startThinking() {
        if (!icon) return;
        thinkInterval = setInterval(() => {
            icon.textContent = thinkFrames[frameIdx++ % thinkFrames.length];
        }, 200);
    }

    function stopThinking(personality) {
        clearInterval(thinkInterval);
        if (icon) icon.textContent = getIcon(personality);
    }

    function getIcon(personality) {
        const map = { cooperative: '🤝', greedy: '💀', balanced: '⚖️', random: '🎲' };
        return map[personality] || '🤖';
    }

    return { startThinking, stopThinking, getIcon };
})();

/* ─── WINNER BANNER ──────────────────────────────── */
const WinnerBanner = (() => {
    function show(playerName, playerScore, aiScore, aiName) {
        const label = document.getElementById('winner-label');
        const name = document.getElementById('winner-name');
        const sub = document.getElementById('winner-sub');

        if (playerScore > aiScore) {
            if (label) label.textContent = '🏆 VICTORY';
            if (name) {
                name.textContent = playerName.toUpperCase();
                name.style.color = 'var(--neon-green)';
                name.style.textShadow = '0 0 30px rgba(0,255,136,.7), 0 0 60px rgba(0,255,136,.3)';
            }
            if (sub) sub.textContent = `OUTPLAYED THE AI — ${playerScore} vs ${aiScore}`;
        } else if (aiScore > playerScore) {
            if (label) label.textContent = '💀 DEFEAT';
            if (name) {
                name.textContent = (aiName || 'AI').toUpperCase();
                name.style.color = 'var(--neon-red)';
                name.style.textShadow = '0 0 30px rgba(255,42,94,.7), 0 0 60px rgba(255,42,94,.3)';
            }
            if (sub) sub.textContent = `The machine wins — ${aiScore} vs ${playerScore}`;
        } else {
            if (label) label.textContent = '⚡ STALEMATE';
            if (name) {
                name.textContent = 'DRAW';
                name.style.color = 'var(--neon-yellow)';
                name.style.textShadow = '0 0 30px rgba(255,233,77,.7)';
            }
            if (sub) sub.textContent = `Perfectly matched — ${playerScore} each`;
        }
    }

    return { show };
})();

/* ─── STAT BARS ──────────────────────────────────── */
function buildStatBars(containerId, splits, steals, totalRounds) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';

    const splitPct = totalRounds ? Math.round(splits / totalRounds * 100) : 0;
    const stealPct = totalRounds ? Math.round(steals / totalRounds * 100) : 0;

    const rows = [
        { label: 'SPLITS', pct: splitPct, color: 'var(--neon-green)' },
        { label: 'STEALS', pct: stealPct, color: 'var(--neon-red)' },
        { label: 'WIN RATE', pct: Math.round((splits + steals > 0 ? splits / (splits + steals) : 0) * 100), color: 'var(--neon-blue)' },
    ];

    rows.forEach(row => {
        const wrap = document.createElement('div');
        wrap.className = 'stat-bar-row';
        wrap.innerHTML = `
      <div class="stat-bar-label">
        <span>${row.label}</span>
        <span>${row.pct}%</span>
      </div>
      <div class="stat-bar-track">
        <div class="stat-bar-fill" style="width:0; background:${row.color}; box-shadow:0 0 8px ${row.color}44;"></div>
      </div>`;
        container.appendChild(wrap);
        // Animate after paint
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                const fill = wrap.querySelector('.stat-bar-fill');
                if (fill) fill.style.width = row.pct + '%';
            });
        });
    });
}

/* ─── RESULT MESSAGE ─────────────────────────────── */
function buildResultMessage(playerName, playerScore, aiScore, trustFinal, rounds) {
    const el = document.getElementById('result-message');
    if (!el) return;

    let mood = '';
    if (trustFinal >= 70) mood = '[ TRUST ESTABLISHED ] Both agents demonstrated consistent cooperation.';
    else if (trustFinal <= 30) mood = '[ TRUST COLLAPSED ] Mutual defection dominated this simulation.';
    else mood = '[ MIXED SIGNALS ] Strategies fluctuated throughout the experiment.';

    const analysis = playerScore > aiScore
        ? `Agent ${playerName} achieved superior earnings through strategic decision-making.`
        : playerScore < aiScore
            ? `The AI exploited predictable patterns in Agent ${playerName}'s behavior.`
            : `A perfectly balanced outcome. Both agents performed at equivalent levels.`;

    el.innerHTML = `
    <div style="color:var(--neon-blue);margin-bottom:8px">> DEBRIEF LOG</div>
    <div>${mood}</div>
    <div style="margin-top:6px;opacity:.7">${analysis} Final trust index: ${trustFinal}%. Total rounds: ${rounds}.</div>
  `;
}

/* ─── CHAT UI ────────────────────────────────────── */
const ChatUI = (() => {
    function addMessage(sender, text, isSystem = false) {
        const log = document.getElementById('chat-log');
        if (!log) return;

        const msg = document.createElement('div');
        msg.className = `chat-msg ${isSystem ? 'system' : sender}`;

        if (isSystem) {
            msg.textContent = text;
        } else {
            msg.innerHTML = `<span style="opacity:0.6;font-size:0.65rem;display:block;margin-bottom:3px">${sender === 'player' ? 'YOU' : 'AI OPPONENT'}</span>${text}`;
        }

        log.appendChild(msg);
        log.scrollTop = log.scrollHeight;
    }

    function clear() {
        const log = document.getElementById('chat-log');
        if (log) log.innerHTML = '';
    }

    function setStatus(text, color) {
        const st = document.getElementById('chat-status');
        if (st) {
            st.textContent = text;
            st.style.color = color || 'var(--neon-green)';
        }
    }

    function show(showChat) {
        const section = document.getElementById('chat-section');
        if (section) {
            if (showChat) {
                section.classList.remove('hidden');
            } else {
                section.classList.add('hidden');
            }
        }
    }

    function setEnabled(enabled) {
        const input = document.getElementById('chat-input');
        const sendBtn = document.getElementById('btn-chat-send');
        if (input) input.disabled = !enabled;
        if (sendBtn) sendBtn.disabled = !enabled;
    }

    function getAndClearInput() {
        const input = document.getElementById('chat-input');
        if (!input) return '';
        const val = input.value.trim();
        input.value = '';
        return val;
    }

    return { addMessage, clear, setStatus, show, setEnabled, getAndClearInput };
})();
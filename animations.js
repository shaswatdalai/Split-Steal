/* ═══════════════════════════════════════════════════════════
   animations.js — Particles, Canvas chart, Typing effect
═══════════════════════════════════════════════════════════ */

'use strict';

/* ─── PARTICLE SYSTEM ────────────────────────────── */
const ParticleSystem = (() => {
    let canvas, ctx, particles = [], W, H, raf;

    const CONFIG = {
        count: 80,
        color: [0, 200, 255],
        secondColor: [0, 255, 136],
        speed: 0.28,
        connectDist: 120,
        size: { min: 1, max: 2.5 },
    };

    function resize() {
        W = canvas.width = window.innerWidth;
        H = canvas.height = window.innerHeight;
    }

    function mkParticle() {
        const speed = CONFIG.speed;
        return {
            x: Math.random() * W,
            y: Math.random() * H,
            vx: (Math.random() - .5) * speed,
            vy: (Math.random() - .5) * speed,
            r: CONFIG.size.min + Math.random() * (CONFIG.size.max - CONFIG.size.min),
            hue: Math.random() > .5 ? CONFIG.color : CONFIG.secondColor,
            alpha: .3 + Math.random() * .5,
        };
    }

    function init() {
        canvas = document.getElementById('particle-canvas');
        if (!canvas) return;
        ctx = canvas.getContext('2d');
        resize();
        window.addEventListener('resize', resize);
        particles = Array.from({ length: CONFIG.count }, mkParticle);
        loop();
    }

    function loop() {
        ctx.clearRect(0, 0, W, H);

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Move
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > W) p.vx *= -1;
            if (p.y < 0 || p.y > H) p.vy *= -1;

            // Draw dot
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${p.hue.join(',')},${p.alpha})`;
            ctx.fill();

            // Connect nearby
            for (let j = i + 1; j < particles.length; j++) {
                const q = particles[j];
                const dx = p.x - q.x, dy = p.y - q.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < CONFIG.connectDist) {
                    const alpha = (1 - dist / CONFIG.connectDist) * .12;
                    ctx.beginPath();
                    ctx.moveTo(p.x, p.y);
                    ctx.lineTo(q.x, q.y);
                    ctx.strokeStyle = `rgba(0,200,255,${alpha})`;
                    ctx.lineWidth = .7;
                    ctx.stroke();
                }
            }
        }

        raf = requestAnimationFrame(loop);
    }

    function stop() { cancelAnimationFrame(raf); }

    return { init, stop };
})();

/* ─── TYPING ANIMATION ───────────────────────────── */
const Typer = (() => {
    function type(el, text, speed = 42, onDone) {
        el.textContent = '';
        let i = 0;
        const interval = setInterval(() => {
            el.textContent += text[i++];
            if (i >= text.length) {
                clearInterval(interval);
                if (onDone) onDone();
            }
        }, speed);
        return interval;
    }

    function typeLines(el, lines, speed = 42, lineDelay = 600, onDone) {
        let lineIdx = 0;
        function nextLine() {
            if (lineIdx >= lines.length) { if (onDone) onDone(); return; }
            type(el, lines[lineIdx++], speed, () => setTimeout(nextLine, lineDelay));
        }
        nextLine();
    }

    return { type, typeLines };
})();

/* ─── TRUST CHART ────────────────────────────────── */
const TrustChart = (() => {
    const COLORS = {
        bothSplit: '#00ff88',
        bothSteal: '#ff2a5e',
        playerStole: '#ffe94d',
        aiStole: '#b44fff',
    };

    function resolveColor(pMove, aiMove) {
        if (pMove === 'split' && aiMove === 'split') return COLORS.bothSplit;
        if (pMove === 'steal' && aiMove === 'steal') return COLORS.bothSteal;
        if (pMove === 'steal' && aiMove === 'split') return COLORS.playerStole;
        return COLORS.aiStole;
    }

    function draw(canvasEl, trustHistory, rounds) {
        const canvas = canvasEl;
        const W = canvas.offsetWidth || 600;
        const H = canvas.height;
        canvas.width = W;

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, W, H);

        if (!trustHistory || trustHistory.length === 0) {
            ctx.fillStyle = 'rgba(255,255,255,.05)';
            ctx.fillRect(20, H / 2 - 1, W - 40, 2);
            return;
        }

        const pad = { l: 20, r: 20, t: 12, b: 20 };
        const innerW = W - pad.l - pad.r;
        const innerH = H - pad.t - pad.b;

        // Grid lines
        [0, 25, 50, 75, 100].forEach(pct => {
            const y = pad.t + innerH * (1 - pct / 100);
            ctx.beginPath();
            ctx.moveTo(pad.l, y);
            ctx.lineTo(W - pad.r, y);
            ctx.strokeStyle = 'rgba(255,255,255,.04)';
            ctx.lineWidth = 1;
            ctx.stroke();
        });

        // Compute x positions
        const pts = trustHistory.map((val, i) => ({
            x: pad.l + (i / Math.max(rounds - 1, 1)) * innerW,
            y: pad.t + innerH * (1 - val / 100),
            val,
        }));

        // Fill gradient under line
        if (pts.length > 1) {
            const grad = ctx.createLinearGradient(0, pad.t, 0, H - pad.b);
            grad.addColorStop(0, 'rgba(0,200,255,.15)');
            grad.addColorStop(1, 'rgba(0,200,255,.01)');
            ctx.beginPath();
            ctx.moveTo(pts[0].x, H - pad.b);
            ctx.lineTo(pts[0].x, pts[0].y);
            pts.forEach(p => ctx.lineTo(p.x, p.y));
            ctx.lineTo(pts[pts.length - 1].x, H - pad.b);
            ctx.closePath();
            ctx.fillStyle = grad;
            ctx.fill();

            // Line
            ctx.beginPath();
            ctx.moveTo(pts[0].x, pts[0].y);
            pts.forEach(p => ctx.lineTo(p.x, p.y));
            ctx.strokeStyle = 'rgba(0,200,255,.6)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        // Dots
        pts.forEach((p, i) => {
            const entry = trustHistory[i]; // trust value
            ctx.beginPath();
            ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
            ctx.fillStyle = entry >= 60 ? COLORS.bothSplit : entry <= 40 ? COLORS.bothSteal : COLORS.aiStole;
            ctx.fill();
            ctx.strokeStyle = 'rgba(0,0,0,.4)';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // Glow
            ctx.beginPath();
            ctx.arc(p.x, p.y, 9, 0, Math.PI * 2);
            ctx.fillStyle = `${entry >= 60 ? COLORS.bothSplit : entry <= 40 ? COLORS.bothSteal : COLORS.aiStole}33`;
            ctx.fill();
        });
    }

    return { draw };
})();

/* ─── FINAL BAR CHART ────────────────────────────── */
const BarChart = (() => {
    function draw(canvasEl, playerHistory, aiHistory) {
        const W = canvasEl.offsetWidth || 260;
        const H = canvasEl.height;
        canvasEl.width = W;

        const ctx = canvasEl.getContext('2d');
        ctx.clearRect(0, 0, W, H);

        const rounds = Math.max(playerHistory.length, aiHistory.length);
        if (rounds === 0) return;

        const barW = Math.floor((W - 40) / rounds / 2 - 4);
        const pad = { l: 20, r: 20, t: 10, b: 24 };
        const innerH = H - pad.t - pad.b;

        const maxScore = Math.max(...playerHistory, ...aiHistory, 100);

        for (let i = 0; i < rounds; i++) {
            const groupX = pad.l + i * ((W - 40) / rounds);

            // Player bar
            const ph = (playerHistory[i] || 0) / maxScore * innerH;
            const py = pad.t + (innerH - ph);
            ctx.fillStyle = 'rgba(0,255,136,.3)';
            ctx.fillRect(groupX, py, barW, ph);
            ctx.fillStyle = 'rgba(0,255,136,.8)';
            ctx.fillRect(groupX, py, barW, 2);

            // AI bar
            const ah = (aiHistory[i] || 0) / maxScore * innerH;
            const ay = pad.t + (innerH - ah);
            ctx.fillStyle = 'rgba(255,42,94,.3)';
            ctx.fillRect(groupX + barW + 4, ay, barW, ah);
            ctx.fillStyle = 'rgba(255,42,94,.8)';
            ctx.fillRect(groupX + barW + 4, ay, barW, 2);

            // Round label
            ctx.fillStyle = 'rgba(122,160,192,.4)';
            ctx.font = '9px Share Tech Mono, monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`R${i + 1}`, groupX + barW, H - 6);
        }

        // Legend
        ctx.fillStyle = 'rgba(0,255,136,.7)';
        ctx.fillRect(W - 90, H - 18, 10, 10);
        ctx.fillStyle = 'rgba(122,160,192,.5)';
        ctx.font = '8px Share Tech Mono, monospace';
        ctx.textAlign = 'left';
        ctx.fillText('YOU', W - 76, H - 10);

        ctx.fillStyle = 'rgba(255,42,94,.7)';
        ctx.fillRect(W - 90, H - 32, 10, 10);
        ctx.fillStyle = 'rgba(122,160,192,.5)';
        ctx.fillText('AI', W - 76, H - 24);
    }

    return { draw };
})();

/* ─── SCROLL REVEAL ──────────────────────────────── */
const ScrollReveal = (() => {
    function init() {
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(e => {
                if (e.isIntersecting) {
                    e.target.style.opacity = '1';
                    e.target.style.transform = 'translateY(0)';
                }
            });
        }, { threshold: .1 });

        document.querySelectorAll('.glass-panel').forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(16px)';
            el.style.transition = 'opacity .5s ease, transform .5s ease';
            observer.observe(el);
        });
    }

    return { init };
})();

/* ─── SCREEN TRANSITION ──────────────────────────── */
const ScreenManager = (() => {
    function show(id) {
        document.querySelectorAll('.screen').forEach(s => {
            s.classList.remove('active');
            s.classList.add('hidden');
        });
        const screen = document.getElementById(id);
        if (screen) {
            screen.classList.remove('hidden');
            requestAnimationFrame(() => screen.classList.add('active'));
        }
    }

    return { show };
})();

/* ─── RESULT FLASH ───────────────────────────────── */
function flashResult(message, color) {
    const el = document.getElementById('result-outcome');
    if (!el) return;
    el.textContent = message;
    el.style.color = color;
    el.style.textShadow = `0 0 20px ${color}`;
}

/* ─── NEON BUTTON RIPPLE ─────────────────────────── */
function addRipple(btn) {
    btn.addEventListener('click', function (e) {
        const rect = btn.getBoundingClientRect();
        const ripple = document.createElement('span');
        ripple.style.cssText = `
      position:absolute; border-radius:50%;
      transform:scale(0); animation:ripple .5s linear;
      background:rgba(255,255,255,.15);
      width:120px; height:120px;
      top:${e.clientY - rect.top - 60}px;
      left:${e.clientX - rect.left - 60}px;
      pointer-events:none; z-index:99;
    `;
        btn.appendChild(ripple);
        setTimeout(() => ripple.remove(), 500);
    });
}

// Inject ripple keyframe
const rippleStyle = document.createElement('style');
rippleStyle.textContent = `@keyframes ripple { to { transform:scale(4); opacity:0; } }`;
document.head.appendChild(rippleStyle);
/* Himanshu & Simran — interactions.
   One passive scroll listener, one rAF, cached layout, transform/opacity writes only. */
(() => {
  'use strict';

  // ── Settings you may want to change ─────────────────────────────
  const SETTINGS = {
    firstEvent: '2026-12-12T14:00:00+05:30',
    rsvp: {
      // Replies are saved to a Google Form (and its linked Sheet).
      // Paste the form's "pre-filled link" here: in Google Forms choose ⋮ → Get pre-filled link,
      // type the answers  name / attending / functions / guests / note  into the five questions,
      // then Get link → Copy link. The site reads the question ids from that link.
      googleFormLink: 'https://docs.google.com/forms/d/e/1FAIpQLSfYjUvfqADoue4CZLprtm61ETY0fK2FfrF2rbFUOBjiNDoZkQ/viewform?usp=pp_url&entry.1412932122=name&entry.1069906385=attending&entry.2112312748=functions&entry.1376362738=guests&entry.812003100=note',
      // Used only while googleFormLink is empty: replies open as a WhatsApp message to this
      // number (country code, no "+", e.g. '919876543210'). Empty = guest picks the chat.
      whatsapp: '',
    },
  };
  // ────────────────────────────────────────────────────────────────

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const clamp = (v, a = 0, b = 1) => (v < a ? a : v > b ? b : v);
  const root = document.documentElement;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Petal burst ── */
  const burstEl = $('#burst');
  const PETALS = ['#f2a3b3', '#f7c6cf', '#f9c23c', '#e8791a', '#fff3d6', '#e88ba0'];
  function burst(n = 34) {
    if (reduce) return;
    const frag = document.createDocumentFragment();
    for (let i = 0; i < n; i++) {
      const p = document.createElement('i');
      const ang = Math.random() * Math.PI * 2, dist = 30 + Math.random() * 60;
      p.style.setProperty('--x', `${(Math.cos(ang) * dist).toFixed(1)}vw`);
      p.style.setProperty('--y', `${(Math.sin(ang) * dist - 18).toFixed(1)}vh`);
      p.style.setProperty('--r', `${(Math.random() * 900 - 450).toFixed(0)}deg`);
      p.style.setProperty('--t', `${(1.4 + Math.random() * 1.3).toFixed(2)}s`);
      p.style.setProperty('--c', PETALS[i % PETALS.length]);
      frag.appendChild(p);
    }
    burstEl.appendChild(frag);
    setTimeout(() => { burstEl.textContent = ''; }, 3000);
  }

  /* ── Music ── */
  const song = $('#song');
  const musicBtn = $('#music');
  let wantMusic = false;
  song.volume = .7;
  function setMusic(on, retry = false) {
    wantMusic = on;
    if (on) song.play().catch(() => { wantMusic = false; syncMusic(); if (retry) retryOnGesture(); });
    else song.pause();
    syncMusic();
  }
  function syncMusic() {
    const playing = wantMusic && !song.paused;
    musicBtn.classList.toggle('is-playing', wantMusic);
    musicBtn.setAttribute('aria-pressed', String(wantMusic));
    musicBtn.setAttribute('aria-label', wantMusic ? 'Pause music' : 'Play music');
    return playing;
  }
  // Browsers (iOS Safari especially) only allow audio to start inside a tap. The doors open from an
  // animation frame, not the tap itself, so the song is unlocked silently on the first touch and
  // any blocked start is retried on the next tap.
  let primed = false;
  function primeSong() {
    if (primed) return;
    primed = true;
    song.muted = true;
    const p = song.play();
    const done = () => { if (!wantMusic) { song.pause(); song.currentTime = 0; } song.muted = false; };
    if (p && p.then) p.then(done, () => { song.muted = false; primed = false; }); else done();
  }
  function retryOnGesture() {
    const go = () => { ['pointerup', 'touchend', 'click', 'keydown'].forEach((t) => removeEventListener(t, go, true)); if (!wantMusic && !song.dataset.userPaused) setMusic(true); };
    ['pointerup', 'touchend', 'click', 'keydown'].forEach((t) => addEventListener(t, go, { capture: true, passive: true }));
  }
  musicBtn.addEventListener('click', () => { if (wantMusic) song.dataset.userPaused = '1'; else delete song.dataset.userPaused; setMusic(!wantMusic); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) song.pause(); else if (wantMusic) song.play().catch(() => {}); });

  /* ── Doors: push them open ── */
  const gate = $('#gate');
  const knock = $('#knock');
  let opened = false;
  function openDoors(instant) {
    if (opened) return;
    opened = true;
    if (instant) gate.classList.add('is-instant');
    gate.classList.add('is-open');
    root.classList.remove('is-locked');
    musicBtn.hidden = false;
    if (!instant) { setMusic(true, true); burst(44); }
    setTimeout(() => gate.classList.add('is-gone'), instant ? 0 : 2000);
  }

  // The doors are two hinged, heavy bodies. A finger drags the edge it grabbed (or simply
  // leans on the door); on release they either swing shut or carry on open and hit the stop.
  function pushDoors() {
    const doorsEl = $('#doors'), lightEl = $('#doorLight'), hint = $('#knockHint');
    const MAX = 1.5; // radians, about 86°
    const mk = (id, sign) => { const el = $(id); return { el, sign, shade: $('.door__shade', el), sheen: $('.door__sheen', el), a: 0, w: 0, held: false, grab: 1, x: 0, downAt: 0, downX: 0, drawn: -1 }; };
    const L = mk('#doorL', 1), R = mk('#doorR', -1);
    const doors = [L, R];
    const other = (d) => (d === L ? R : L);
    let W = 0, committed = false, running = true, last = 0, idleFrom = performance.now(), taps = 0, lit = -1, settleAt = 0;

    // a soft wooden thump when a door meets its stop
    let actx = null;
    function wake() { try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); if (actx.state === 'suspended') actx.resume(); } catch (e) { actx = null; } }
    function thud(v) {
      if (navigator.vibrate) try { navigator.vibrate(Math.round(8 + v * 18)); } catch (e) { /* not allowed yet */ }
      if (!actx || actx.state !== 'running') return;
      const t = actx.currentTime, o = actx.createOscillator(), g = actx.createGain();
      o.type = 'sine'; o.frequency.setValueAtTime(118, t); o.frequency.exponentialRampToValueAtTime(40, t + .17);
      g.gain.setValueAtTime(.0001, t); g.gain.exponentialRampToValueAtTime(.55 * v + .05, t + .012); g.gain.exponentialRampToValueAtTime(.0001, t + .3);
      o.connect(g).connect(actx.destination); o.start(t); o.stop(t + .32);
    }

    function commit() {
      if (committed) return;
      committed = true;
      settleAt = performance.now() + 2600;
      for (const d of doors) d.w = Math.max(d.w, 1.2);
      openDoors(false);
    }

    // the angle at which the grabbed point of the door sits under the finger
    const dragAngle = (d) => Math.acos(clamp((d === L ? d.x : W - d.x) / d.grab, Math.cos(MAX), 1));

    function step(d, dt, now) {
      let target, k, c;
      if (committed) { target = MAX * 1.08; k = 30; c = 4.2; }                 // swings on and leans on its stop
      else if (d.held) {                                                       // follows the hand, with a little weight
        const drag = dragAngle(d);
        const lean = clamp((now - d.downAt - 130) / 1000 * 1.15, 0, MAX * .8); // just pressing leans the door open
        target = Math.max(drag, lean); k = 240; c = 27;
      } else if (other(d).held) { target = other(d).a * .6; k = 70; c = 12; } // its partner is drawn along
      else {                                                                   // left alone: breathes, then falls shut
        const idle = (now - idleFrom) / 1000;
        target = idle > 1.6 ? .07 * (1 - Math.cos((idle - 1.6) * 1.9)) : 0; k = 26; c = 5.4;
      }
      d.w += (k * (target - d.a) - c * d.w) * dt;
      d.a += d.w * dt;
      if (d.a < 0) { d.a = 0; if (d.w < -.7) thud(Math.min(1, -d.w / 5) * .6); d.w *= -.2; }
      if (d.a > MAX) { d.a = MAX; if (d.w > .5) thud(Math.min(1, d.w / 4.5)); d.w *= -.3; }
    }

    function draw(d) {
      if (Math.abs(d.a - d.drawn) < .0005) return;
      d.drawn = d.a;
      d.el.style.transform = `rotateY(${(d.sign * d.a * 57.2958).toFixed(2)}deg)`;
      d.shade.style.opacity = Math.min(.62, d.a * .44).toFixed(3);
      d.sheen.style.transform = `translate3d(${(d.sign * d.a / MAX * 330).toFixed(1)}%,0,0)`;
    }

    function frame(now) {
      if (!running) return;
      const dt = Math.min(.05, (now - (last || now)) / 1000); last = now;
      for (let t = 0; t < dt; t += 1 / 240) for (const d of doors) step(d, Math.min(1 / 240, dt - t), now);
      for (const d of doors) draw(d);
      const glow = +clamp(Math.max(L.a, R.a) / .6).toFixed(3);
      if (glow !== lit) { lit = glow; lightEl.style.opacity = glow; }
      if (!committed) { for (const d of doors) if (d.a > 1.02) commit(); }
      else if (now > settleAt) { running = false; return; }
      requestAnimationFrame(frame);
    }

    const pointers = new Map();
    const at = (ev) => ev.clientX - knock.getBoundingClientRect().left;
    knock.addEventListener('pointerdown', (ev) => {
      if (committed || ev.target.closest('button')) return;
      ev.preventDefault(); wake(); primeSong();
      W = knock.getBoundingClientRect().width;
      const x = at(ev), d = x < W / 2 ? L : R;
      if (d.held) return;
      d.held = true; d.x = d.downX = x; d.downAt = performance.now();
      d.grab = Math.max(W * .1, d === L ? x : W - x);
      pointers.set(ev.pointerId, d);
      try { knock.setPointerCapture(ev.pointerId); } catch (e) { /* synthetic pointers cannot be captured */ }
      doorsEl.classList.add('is-touched'); knock.classList.add('is-pushing');
    });
    knock.addEventListener('pointermove', (ev) => { const d = pointers.get(ev.pointerId); if (d) d.x = at(ev); });
    const release = (ev) => {
      const d = pointers.get(ev.pointerId);
      if (!d) return;
      pointers.delete(ev.pointerId); d.held = false;
      const now = performance.now(); idleFrom = now;
      if (!pointers.size) knock.classList.remove('is-pushing');
      if (committed) return;
      const tap = now - d.downAt < 230 && Math.abs(d.x - d.downX) < 8;
      if (tap) {                                    // a knock: the door gives a little, and more each time
        taps++; d.w += 2.4 + taps * .8; other(d).w += 1.2;
        if (taps >= 3) commit();
        else hint.querySelector('small').textContent = 'Not a knock. Give them a proper push.';
      } else if (d.a > .42 || d.w > 2 || dragAngle(d) > .7) commit(); // pushed far or fast enough: it carries on
    };
    knock.addEventListener('pointerup', release); knock.addEventListener('pointercancel', release);
    $('#knockSkip').addEventListener('click', () => { wake(); primeSong(); commit(); });
    requestAnimationFrame(frame);
  }

  if ('scrollRestoration' in history) history.scrollRestoration = 'manual';
  if (location.hash) {
    openDoors(true);
    retryOnGesture(); // opened straight to a section: start the song on the first tap
  } else {
    scrollTo(0, 0);
    root.classList.add('is-locked');
    pushDoors();
  }

  /* ── Decorations built once ── */
  // a mandala that turns as you scroll
  const mandala = $('#mandala');
  (() => {
    let h = '';
    const ring = (n, r0, r1, w) => {
      const a = r0 + (r1 - r0) * .35, b = r0 + (r1 - r0) * .8;
      for (let i = 0; i < n; i++) h += `<path transform="rotate(${(360 / n * i).toFixed(2)})" d="M0,${-r0}C${w},${-a} ${w * .6},${-b} 0,${-r1}C${-w * .6},${-b} ${-w},${-a} 0,${-r0}Z"/>`;
    };
    ring(12, 20, 46, 9); ring(24, 48, 72, 6.5); ring(36, 74, 97, 5);
    for (const r of [19, 47, 73, 98]) h += `<circle r="${r}"/>`;
    mandala.innerHTML = `<g fill="none" stroke="currentColor" stroke-width=".6">${h}</g>`;
  })();

  // titles that arrive letter by letter
  for (const el of $$('[data-split]')) {
    const text = el.textContent;
    el.setAttribute('aria-label', text);
    el.textContent = '';
    let i = 0;
    for (const word of text.split(' ')) {
      const w = document.createElement('span');
      w.style.cssText = 'display:inline-block;white-space:nowrap';
      w.setAttribute('aria-hidden', 'true');
      for (const ch of word) {
        const s = document.createElement('span');
        s.dataset.ch = ''; s.style.setProperty('--i', i++); s.textContent = ch;
        w.appendChild(s);
      }
      el.appendChild(w); el.appendChild(document.createTextNode(' '));
    }
  }

  /* ── Cached layout ── */
  const stage = $('.gate__stage');
  const arches = [
    { el: $('.gate__arch--1'), start: 0, span: .46, k: 3.2 },
    { el: $('.gate__arch--2'), start: .16, span: .48, k: 4.2 },
    { el: $('.gate__arch--3'), start: .34, span: .56, k: 5.5 },
  ];
  const gateInner = $('#gateInner'), gateScroll = $('#gateScroll'), gatePlate = $('#gatePlate');
  // Where scroll-driven CSS animations exist (Chrome/Android, Safari 26+), the gate is driven by the
  // compositor, not this script, so it cannot lag behind the finger. Others fall back to the JS loop below.
  const cssGate = !reduce && !!(window.CSS && CSS.supports('animation-timeline: view()') && CSS.supports('view-timeline: --g block'));
  if (cssGate) {
    const pct = (x) => `${(x * 100).toFixed(2)}%`;
    let css = '.gate--css{view-timeline:--gate block}';
    arches.forEach((a, i) => {
      const f = ['0%{transform:scale(1);opacity:1}'];
      for (let s = 0; s <= 12; s++) {
        const q = s / 12;
        f.push(`${pct(a.start + q * a.span)}{transform:scale(${(1 + q * q * a.k).toFixed(4)});opacity:${(1 - clamp((q - .68) / .32)).toFixed(3)}}`);
      }
      f.push(`100%{transform:scale(${(1 + a.k).toFixed(4)});opacity:0}`);
      css += `@keyframes gate-a${i}{${f.join('')}}.gate--css .gate__arch--${i + 1}{animation:gate-a${i} linear both;animation-timeline:--gate;animation-range:contain 0% contain 100%}`;
    });
    css += '@keyframes gate-in{0%{transform:scale(.84)}80%,100%{transform:scale(1)}}.gate--css .gate__inner{animation:gate-in linear both;animation-timeline:--gate;animation-range:contain 0% contain 100%}';
    css += '@keyframes gate-pl{0%{transform:scale(1.22)}90%,100%{transform:scale(1)}}.gate--css .gate__plate{animation:gate-pl linear both;animation-timeline:--gate;animation-range:contain 0% contain 100%}';
    css += '@keyframes gate-sc{0%{opacity:1}12%,100%{opacity:0}}.gate--css .gate__scroll{animation:gate-sc linear both;animation-timeline:--gate;animation-range:contain 0% contain 100%}';
    const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);
    gate.classList.add('gate--css');
  }
  const pill = $('#pill'), pillText = $('#pillText');
  const pages = $$('.page').map((el) => ({ el, pill: el.dataset.pill || '', dark: 'dark' in el.dataset, top: 0, bottom: 0 }));
  const strips = $$('[data-strip]').map((el) => ({ el, kind: el.dataset.strip, top: 0, h: 0, t: '' }));
  const drifts = $$('[data-drift]').map((el) => ({ el, top: 0, h: 0 }));
  const walker = $('#walker'), datePage = $('#date');
  const turns = $$('[data-turn]').map((el) => ({ el, kind: el.dataset.turn, orb: $('.turn__orb', el), stars: $('.turn__stars', el), top: 0, h: 0 }));
  const portrait = $('.portrait');

  let vh = 0, col = 0, gateDist = 1, dateTop = 0, dateH = 0, portraitTop = 0;
  const pageY = (el) => { let y = 0; for (let n = el; n; n = n.offsetParent) y += n.offsetTop; return y; };

  function measure() {
    vh = innerHeight;
    col = $('main').offsetWidth;
    gateDist = Math.max(1, gate.offsetHeight - stage.offsetHeight);
    for (const p of pages) { p.top = pageY(p.el); p.bottom = p.top + p.el.offsetHeight; }
    for (const s of strips) { s.top = pageY(s.el); s.h = s.el.offsetHeight; }
    for (const d of drifts) { d.top = pageY(d.el.parentElement); d.h = d.el.parentElement.offsetHeight; }
    dateTop = pageY(datePage); dateH = datePage.offsetHeight;
    for (const t of turns) { t.top = pageY(t.el); t.h = t.el.offsetHeight; }
    portraitTop = pageY(portrait);
    lastY = -1;
    requestTick();
  }

  /* ── The frame loop ── */
  let ticking = false, lastY = -1, lastGateP = -1, lastPill = null;
  function requestTick() { if (!ticking) { ticking = true; requestAnimationFrame(update); } }
  const put = (o, t) => { if (o.t !== t) { o.t = t; o.el.style.transform = t; } };

  function update() {
    ticking = false;
    const y = scrollY;
    if (y === lastY) return;
    lastY = y;
    const c = y + vh / 2;

    // the time pill
    let label = '', dark = false;
    for (const p of pages) if (c >= p.top && c < p.bottom) { label = p.pill; dark = p.dark; break; }
    if (label !== lastPill) {
      lastPill = label;
      if (label) { pillText.textContent = label; pill.classList.toggle('is-dark', dark); }
      pill.classList.toggle('is-on', !!label);
    }

    if (reduce) return;

    // walk through the arches (fallback for browsers without scroll-driven animations)
    const p = clamp(y / gateDist);
    if (!cssGate && p !== lastGateP) {
      lastGateP = p;
      for (const a of arches) {
        const q = clamp((p - a.start) / a.span);
        a.el.style.transform = `scale(${(1 + q * q * a.k).toFixed(4)})`;
        a.el.style.opacity = (1 - clamp((q - .68) / .32)).toFixed(3);
      }
      gateInner.style.transform = `scale(${(.84 + .16 * clamp(p / .8)).toFixed(4)})`;
      gatePlate.style.transform = `scale(${(1.22 - .22 * clamp(p / .9)).toFixed(4)})`;
      gateScroll.style.opacity = (1 - clamp(p / .12)).toFixed(3);
    }

    // artwork settles into place as each page arrives
    for (const s of strips) {
      if (s.top + s.h < y - 80 || s.top > y + vh + 80) continue;
      if (s.kind === 'top') {
        const d = clamp((s.top - y) / vh);
        put(s, `translate3d(0,${(-d * 54).toFixed(1)}px,0) scale(${(1 + d * .05).toFixed(4)})`);
      } else {
        const d = clamp((s.top - y - vh * .4) / (vh * .6));
        put(s, `translate3d(0,${(d * 60).toFixed(1)}px,0)`);
      }
    }

    // the portrait drifts in its arch while the mandala turns behind it
    for (const d of drifts) {
      if (d.top + d.h < y || d.top > y + vh) continue;
      const prog = clamp((c - (d.top + d.h / 2)) / vh, -1, 1);
      d.el.style.transform = `translate3d(0,${(prog * d.h * .025).toFixed(1)}px,0)`;
    }
    if (portraitTop < y + vh + 200 && portraitTop > y - vh) mandala.style.transform = `rotate(${(y * .05).toFixed(2)}deg)`;

    // between the pehars the sky keeps time: the sun sets, rises, and the moon comes up
    for (const t of turns) {
      if (t.top + t.h < y || t.top > y + vh) continue;
      const p = clamp((y + vh - t.top) / (vh + t.h));
      const oy = (t.kind === 'set' ? .04 + p * 1.05 : 1.02 - p * .98) * t.h;
      const ox = (t.kind === 'set' ? -1 : 1) * (.27 + (p - .5) * .1) * col; // keeps to one side, clear of the caption
      t.orb.style.transform = `translate3d(${ox.toFixed(1)}px,${oy.toFixed(1)}px,0)`;
      if (t.stars) t.stars.style.opacity = clamp((p - .42) * 2.4).toFixed(2);
    }

    // the couple stroll in on the date page
    if (dateTop < y + vh && dateTop + dateH > y) {
      const prog = clamp((y + vh - dateTop - dateH * .55) / (vh * .75));
      walker.style.transform = `translate3d(${((-.3 + prog * .58) * col).toFixed(1)}px,0,0)`;
    }
  }

  addEventListener('scroll', requestTick, { passive: true });
  let rz = 0;
  const remeasure = () => { cancelAnimationFrame(rz); rz = requestAnimationFrame(measure); };
  let lastW = innerWidth, lastH = innerHeight;
  addEventListener('resize', () => {
    // on phones the address bar sliding in and out fires resize while scrolling; re-measuring then causes jumps
    if (innerWidth === lastW && Math.abs(innerHeight - lastH) < 160) return;
    lastW = innerWidth; lastH = innerHeight; remeasure();
  });
  addEventListener('load', measure);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
  if ('ResizeObserver' in window) new ResizeObserver(remeasure).observe($('main'));
  measure();

  /* ── Reveal on scroll ── */
  const revealEls = $$('[data-reveal]');
  const groups = new Map();
  for (const el of revealEls) {
    const n = groups.get(el.parentElement) || 0;
    el.style.setProperty('--d', `${Math.min(n, 6) * .09}s`);
    groups.set(el.parentElement, n + 1);
  }
  if ('IntersectionObserver' in window && !reduce) {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); }
    }, { rootMargin: '0px 0px -10% 0px', threshold: .12 });
    revealEls.forEach((el) => io.observe(el));
    const live = new IntersectionObserver((entries) => {
      for (const e of entries) e.target.classList.toggle('is-live', e.isIntersecting);
    }, { rootMargin: '10% 0px 10% 0px' });
    pages.forEach((p) => live.observe(p.el));
  } else {
    revealEls.forEach((el) => el.classList.add('is-in'));
    pages.forEach((p) => p.el.classList.add('is-live'));
  }

  const reel = $('#reel'), reelHint = $('.reel__hint');
  reel.addEventListener('scroll', () => reelHint.classList.add('is-done'), { passive: true, once: true });

  /* ── Scratch to reveal the dates; the countdown unlocks after ── */
  const dateBody = $('.date__body');
  let unlockCountdown = () => {};
  (() => {
    const cv = $('#foil'), card = $('#scratch');
    if (reduce) { cv.remove(); dateBody.classList.add('is-unlocked'); return; }
    const ctx = cv.getContext('2d');
    let w = 0, h = 0, dpr = 1, drawing = false, moved = 0, done = false, lx = 0, ly = 0, taps = 0, dustAt = 0, buzzAt = 0;
    function paint() {
      const r = cv.getBoundingClientRect();
      if (!r.width || done) return;
      dpr = Math.min(devicePixelRatio || 1, 2);
      w = cv.width = Math.round(r.width * dpr); h = cv.height = Math.round(r.height * dpr);
      const g = ctx.createLinearGradient(0, 0, w, h);
      g.addColorStop(0, '#fbe7a6'); g.addColorStop(.28, '#c8962f'); g.addColorStop(.5, '#fff0b8'); g.addColorStop(.74, '#a87724'); g.addColorStop(1, '#f0d28a');
      ctx.globalCompositeOperation = 'source-over';
      ctx.fillStyle = g; ctx.fillRect(0, 0, w, h);
      // brushed-metal grain and glitter
      for (let i = 0; i < h; i += 2 * dpr) { ctx.fillStyle = `rgba(255,255,255,${(Math.random() * .08).toFixed(3)})`; ctx.fillRect(0, i, w, dpr); }
      for (let i = 0; i < 140; i++) { ctx.fillStyle = `rgba(255,255,255,${(.3 + Math.random() * .6).toFixed(2)})`; const sz = dpr * (Math.random() < .15 ? 2.4 : 1.2); ctx.fillRect(Math.random() * w, Math.random() * h, sz, sz); }
      ctx.strokeStyle = 'rgba(92,58,10,.55)'; ctx.lineWidth = dpr; ctx.setLineDash([4 * dpr, 4 * dpr]);
      ctx.strokeRect(6 * dpr, 6 * dpr, w - 12 * dpr, h - 12 * dpr); ctx.setLineDash([]);
      ctx.fillStyle = '#4a2c05'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.font = `${Math.round(h * .26)}px Marcellus, Georgia, serif`;
      ctx.fillText('SCRATCH ME', w / 2, h * .42);
      ctx.font = `italic ${Math.round(h * .17)}px 'Cormorant Garamond', Georgia, serif`;
      ctx.fillText('the dates are hiding here', w / 2, h * .72);
    }
    function reveal() {
      if (done) return;
      done = true;
      card.classList.add('is-touched', 'is-revealed');
      cv.classList.add('is-gone'); cv.setAttribute('aria-hidden', 'true'); cv.tabIndex = -1;
      burst(28);
      if (navigator.vibrate) try { navigator.vibrate([12, 60, 24]); } catch (e) { /* not allowed */ }
      setTimeout(() => { dateBody.classList.add('is-unlocked'); unlockCountdown(); }, 350);
    }
    function dust(e) {
      const now = performance.now();
      if (now - dustAt < 40) return;
      dustAt = now;
      const r = card.getBoundingClientRect();
      for (let i = 0; i < 3; i++) {
        const d = document.createElement('i');
        d.className = 'scratch__dust';
        d.style.left = `${e.clientX - r.left}px`; d.style.top = `${e.clientY - r.top}px`;
        d.style.setProperty('--dx', `${(Math.random() * 60 - 30).toFixed(0)}px`);
        d.style.setProperty('--dy', `${(Math.random() * 40 + 10).toFixed(0)}px`);
        d.addEventListener('animationend', () => d.remove(), { once: true });
        card.appendChild(d);
      }
      if (navigator.vibrate && now - buzzAt > 90) { buzzAt = now; try { navigator.vibrate(3); } catch (err) { /* not allowed */ } }
    }
    function scratch(e) {
      const r = cv.getBoundingClientRect(), k = w / r.width;
      const x = (e.clientX - r.left) * k, y = (e.clientY - r.top) * k;
      ctx.globalCompositeOperation = 'destination-out';
      ctx.lineWidth = h * .42; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(lx || x, ly || y); ctx.lineTo(x, y); ctx.stroke();
      moved += Math.hypot(x - (lx || x), y - (ly || y));
      lx = x; ly = y;
      dust(e);
      if (moved > w * 1.25) reveal(); // a few strokes is enough: the rest flakes away by itself
    }
    cv.addEventListener('pointerdown', (e) => {
      if (done) return;
      e.preventDefault();
      card.classList.add('is-touched');
      drawing = true; lx = ly = 0;
      try { cv.setPointerCapture(e.pointerId); } catch (err) { /* synthetic pointers cannot be captured */ }
      scratch(e);
    });
    cv.addEventListener('pointermove', (e) => { if (drawing && !done) scratch(e); });
    const end = () => {
      if (!drawing || done) return;
      drawing = false;
      if (moved < w * .05 && ++taps >= 2) reveal(); // two taps also work, for anyone who does not scratch
    };
    cv.addEventListener('pointerup', end); cv.addEventListener('pointercancel', end);
    cv.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); reveal(); } });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(paint);
    addEventListener('load', paint);
    paint();
  })();

  /* ── Countdown ── */
  const FIRST_EVENT = Date.parse(SETTINGS.firstEvent);
  const cd = { d: $('#cdD'), h: $('#cdH'), m: $('#cdM'), s: $('#cdS') };
  const pad = (n) => String(n).padStart(2, '0');
  function tick() {
    let s = Math.floor((FIRST_EVENT - Date.now()) / 1000);
    if (s <= 0) { $('#countdown').innerHTML = '<p style="grid-column:1/-1;font-style:italic">The celebrations have begun</p>'; clearInterval(timer); return; }
    cd.d.textContent = Math.floor(s / 86400); s %= 86400;
    cd.h.textContent = pad(Math.floor(s / 3600)); s %= 3600;
    cd.m.textContent = pad(Math.floor(s / 60));
    cd.s.textContent = pad(s % 60);
  }
  let rolling = false;
  unlockCountdown = () => {
    // the numbers spin up to the real value, then carry on ticking
    let s = Math.max(0, Math.floor((FIRST_EVENT - Date.now()) / 1000));
    const target = [Math.floor(s / 86400), Math.floor(s % 86400 / 3600), Math.floor(s % 3600 / 60), s % 60];
    const els = [cd.d, cd.h, cd.m, cd.s], t0 = performance.now(), dur = 1400;
    rolling = true;
    (function roll(now) {
      const p = clamp((now - t0) / dur), e = 1 - (1 - p) ** 4;
      els.forEach((el, i) => { const n = Math.round(target[i] * e); el.textContent = i ? pad(n) : n; });
      if (p < 1) requestAnimationFrame(roll); else { rolling = false; tick(); }
    })(t0);
  };
  const timer = setInterval(() => { if (!document.hidden && !rolling) tick(); }, 1000);
  tick();

  /* ── RSVP ── */
  const RSVP_KEYS = ['name', 'attending', 'functions', 'guests', 'note'];
  function parseGoogleForm(link) {
    if (!link) return null;
    try {
      const u = new URL(link);
      const fields = {};
      for (const [k, v] of u.searchParams) if (k.startsWith('entry.')) fields[v.trim().toLowerCase()] = k;
      const missing = RSVP_KEYS.filter((k) => !fields[k]);
      if (!/\/viewform$/.test(u.pathname) || missing.length) throw new Error(missing.length ? `no question pre-filled with: ${missing.join(', ')}` : 'not a pre-filled form link');
      return { action: u.origin + u.pathname.replace(/\/viewform$/, '/formResponse'), fields };
    } catch (err) {
      console.warn(`RSVP: googleFormLink was ignored (${err.message}). Replies will use WhatsApp instead.`);
      return null;
    }
  }
  const googleForm = parseGoogleForm(SETTINGS.rsvp.googleFormLink);

  const form = $('#rsvpForm'), more = $('#rsvpMore'), submit = $('#rsvpSubmit'), errorEl = $('#rsvpError'), doneEl = $('#rsvpDone');
  const guestsOut = $('#guestsOut');
  const attending = () => form.elements.attending.value === 'yes';
  form.addEventListener('change', (e) => {
    if (e.target.name !== 'attending') return;
    more.hidden = !attending();
    submit.textContent = attending() ? 'Count me in' : 'Send my regrets';
    remeasure();
  });
  $$('[data-step]', form).forEach((b) => b.addEventListener('click', () => {
    const v = clamp(+form.elements.guests.value + +b.dataset.step, 1, 10);
    form.elements.guests.value = v; guestsOut.textContent = v;
  }));

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = new FormData(form);
    const name = String(f.get('name') || '').trim();
    const yes = attending();
    const fns = f.getAll('fn');
    errorEl.hidden = true;
    if (!name) { errorEl.textContent = 'Please tell us your name.'; errorEl.hidden = false; form.elements.name.focus(); return; }
    if (yes && !fns.length) { errorEl.textContent = 'Pick at least one celebration to join.'; errorEl.hidden = false; return; }
    const reply = {
      name,
      attending: yes ? 'Joyfully accepting' : 'Regretfully declining',
      functions: yes ? fns.join(', ') : '',
      guests: yes ? String(f.get('guests')) : '0',
      note: String(f.get('note') || '').trim(),
    };
    const { whatsapp } = SETTINGS.rsvp;
    submit.disabled = true; submit.textContent = 'Sending…';
    try {
      if (googleForm) {
        const body = new URLSearchParams();
        for (const k of RSVP_KEYS) body.append(googleForm.fields[k], reply[k]);
        await fetch(googleForm.action, { method: 'POST', mode: 'no-cors', body });
      } else {
        const lines = ['RSVP for Himanshu & Simran', `Name: ${reply.name}`, reply.attending];
        if (yes) lines.push(`Joining for: ${reply.functions}`, `Guests: ${reply.guests}`);
        if (reply.note) lines.push(`Note: ${reply.note}`);
        window.open(`https://wa.me/${whatsapp}?text=${encodeURIComponent(lines.join('\n'))}`, '_blank', 'noopener');
      }
      $('#rsvpDoneTitle').textContent = yes ? "You're on the list!" : 'You will be missed';
      $('#rsvpDoneText').textContent = yes ? `Thank you, ${name.split(' ')[0]}. We can't wait to celebrate with you in Nagpur.` : `Thank you for letting us know, ${name.split(' ')[0]}. You'll be in our hearts.`;
      form.hidden = true; doneEl.hidden = false; doneEl.focus({ preventScroll: true });
      if (yes) burst(40);
    } catch (err) {
      errorEl.textContent = 'We could not send your RSVP. Please try again.'; errorEl.hidden = false;
    } finally {
      submit.disabled = false; submit.textContent = attending() ? 'Count me in' : 'Send my regrets';
      remeasure();
    }
  });
  $('#rsvpAgain').addEventListener('click', () => { doneEl.hidden = true; form.hidden = false; remeasure(); });
})();

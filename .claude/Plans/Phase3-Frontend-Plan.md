# Phase 3 — Frontend Implementation Plan

**Document ID:** PLAN-PHASE-3-v1.0  
**Status:** Ready for Implementation  
**Source of Truth:** `.claude/Specs/Phase3-Frontend-Spec.md` (91 FRs, 23 NFRs, 35 ACs)  
**Branch:** `feature/phase-3`  
**Created:** 2026-04-24

---

## Context

Phase 3 builds the complete browser UI for the USDJPY Smart Agent — three HTML pages, one CSS file, and four JavaScript files. No frameworks, no build tools, no CDN. Everything served as static files by the FastAPI server at `http://localhost:8000`.

**All files are greenfield.** Zero frontend code exists. Every file below is created from scratch.

**Phase 3 can only begin after Phases 1 and 2 are complete.** The frontend is a read-only consumer of the REST API. It does not implement strategy logic, does not write to SQLite, and does not communicate with MT5.

---

## Prerequisites Check

Before writing any frontend code, verify every item below with the FastAPI server running (`python backend/main.py`). If any item fails, fix Phase 1 or 2 first.

```bash
curl http://localhost:8000/api/status
# → HTTP 200, data.mt5_connected (bool), data.last_evaluation (UTC ISO 8601)

curl http://localhost:8000/api/dashboard
# → HTTP 200, data.usdjpy_bid, data.usdjpy_ask, data.us10y, data.dxy,
#   data.vix, data.next_event, data.next_event_time, data.next_event_impact,
#   data.valid_count, data.wait_count, data.no_trade_count, data.mt5_connected

curl http://localhost:8000/api/strategies
# → HTTP 200, data is array of exactly 20 objects, each has:
#   id, name, type, timeframes, status, direction, entry, sl, tp1, rrr,
#   confidence, evaluated_at

curl http://localhost:8000/api/strategy/1
# → HTTP 200, data has all summary fields plus:
#   tp2, tp3, probability, wait_zone, conditions_to_meet,
#   reasons_for, reasons_against, verdict_summary,
#   agents (array of 4, each with name, score, conditions[11], flags)
```

**CRITICAL:** All responses are wrapped — `{ "success": bool, "data": {...}, "error": null }`. JavaScript must access `response.data.*`, not `response.*` directly.

Also verify the `frontend/` directory exists and FastAPI has the StaticFiles mount registered **after** all API routes in `backend/main.py`:

```python
from fastapi.staticfiles import StaticFiles
# Last line — must come after all @app.get() routes
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
```

---

## Files to Create

```
frontend/
├── index.html          ← Step 3
├── strategies.html     ← Step 5
├── detail.html         ← Step 7
├── css/
│   └── styles.css      ← Step 1
└── js/
    ├── shared.js       ← Step 2  (polling engine, countdown, stale banner)
    ├── dashboard.js    ← Step 4
    ├── strategies.js   ← Step 6
    └── detail.js       ← Step 8
```

`shared.js` is a utility module (not a page-specific file) included in all three HTML pages. It does not violate NFR-3-12, which specifies one page-specific JS file per page.

---

## Step 1 — CSS Design System (`frontend/css/styles.css`)

**Delivers:** All visual styling. Every subsequent step depends on this.

### 1.1 CSS Custom Properties (root variables)

```css
:root {
  /* Status colours */
  --color-valid:      #22c55e;
  --color-wait:       #f59e0b;
  --color-no-trade:   #374151;
  --color-buy:        #16a34a;
  --color-sell:       #dc2626;
  --color-score-low:  #ef4444;

  /* Background tints for cards */
  --tint-valid:       rgba(34, 197, 94, 0.08);
  --tint-wait:        rgba(245, 158, 11, 0.08);

  /* Dark theme surfaces */
  --bg-primary:       #111827;
  --bg-surface:       #1f2937;
  --bg-elevated:      #374151;

  /* Text */
  --text-primary:     #f9fafb;
  --text-secondary:   #e5e7eb;
  --text-muted:       #9ca3af;

  /* Borders */
  --border-default:   #374151;
  --border-subtle:    #1f2937;

  /* Semantic supporting/opposing */
  --bg-supporting:    rgba(34, 197, 94, 0.1);
  --bg-opposing:      rgba(239, 68, 68, 0.1);
  --text-supporting:  #4ade80;
  --text-opposing:    #f87171;
}
```

### 1.2 Base Reset and Body

```css
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-primary);
  color: var(--text-primary);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-size: 14px;
  line-height: 1.5;
}
a { color: inherit; text-decoration: none; }
```

### 1.3 Navigation Bar

```css
.nav {
  position: sticky; top: 0; z-index: 100;
  background: var(--bg-surface);
  border-bottom: 1px solid var(--border-default);
  padding: 0 1.5rem;
  height: 52px;
  display: flex; align-items: center; gap: 1.5rem;
}
.nav-title { font-weight: 700; font-size: 1rem; color: var(--text-primary); margin-right: auto; }
.nav-link { color: var(--text-muted); font-size: 0.875rem; }
.nav-link:hover { color: var(--text-primary); }
.nav-price { font-weight: 600; font-size: 0.9rem; }
.nav-clock { color: var(--text-muted); font-size: 0.8rem; font-variant-numeric: tabular-nums; }
.nav-countdown { color: var(--text-muted); font-size: 0.8rem; white-space: nowrap; }

/* MT5 status dot */
.mt5-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: var(--color-no-trade);
}
.mt5-dot.connected { background: var(--color-valid); }
.mt5-dot.disconnected { background: var(--color-sell); }
```

### 1.4 Layout Containers

```css
.container { max-width: 1400px; margin: 0 auto; padding: 1.5rem; }
.section { margin-bottom: 1.5rem; }

/* Two-column split */
.col-split { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }

/* Four-tile strip */
.tile-strip { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; }
.tile {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 1rem;
}
.tile-label { font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
.tile-value { font-size: 1.5rem; font-weight: 700; margin: 0.25rem 0; }
.tile-sub { font-size: 0.8rem; color: var(--text-muted); }
```

### 1.5 Status Badge and Chips

```css
.badge {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}
.badge-valid    { background: var(--color-valid); color: #fff; }
.badge-wait     { background: var(--color-wait); color: #111; }
.badge-no-trade { background: var(--color-no-trade); color: var(--text-muted); }
.badge-large    { padding: 0.4rem 1rem; font-size: 0.875rem; }

.chip-buy  { background: var(--color-buy); color: #fff; padding: 0.2rem 0.75rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }
.chip-sell { background: var(--color-sell); color: #fff; padding: 0.2rem 0.75rem; border-radius: 999px; font-size: 0.8rem; font-weight: 700; }

.type-badge {
  display: inline-block;
  border: 1px solid var(--border-default);
  border-radius: 4px;
  padding: 0.1rem 0.5rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}
.tf-chip {
  display: inline-block;
  background: var(--bg-elevated);
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  font-size: 0.7rem;
  color: var(--text-muted);
}
```

### 1.6 Signal Summary Count Badges

```css
.count-group { display: flex; gap: 1rem; flex-wrap: wrap; }
.count-badge {
  display: flex; flex-direction: column; align-items: center;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  min-width: 100px;
}
.count-badge-valid    { background: rgba(34,197,94,0.15); border: 1px solid var(--color-valid); }
.count-badge-wait     { background: rgba(245,158,11,0.15); border: 1px solid var(--color-wait); }
.count-badge-no-trade { background: var(--bg-surface); border: 1px solid var(--border-default); }
.count-badge .count   { font-size: 2rem; font-weight: 700; }
.count-badge .label   { font-size: 0.7rem; text-transform: uppercase; color: var(--text-muted); }
```

### 1.7 Strategy Cards

```css
.cards-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
}
.card {
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  padding: 1rem;
  cursor: pointer;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
  border-left: 1px solid var(--border-default); /* default, overridden per status */
}
.card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.4); transform: translateY(-2px); }
.card.valid    { border-left: 2px solid var(--color-valid); background: var(--tint-valid); }
.card.wait     { border-left: 2px solid var(--color-wait); background: var(--tint-wait); }
.card.no-trade { border: 1px solid var(--border-default); }
.card.hidden   { display: none; }

.card-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 0.5rem; }
.card-num { font-size: 0.7rem; color: var(--text-muted); }
.card-name { font-weight: 600; font-size: 0.9rem; margin-bottom: 0.25rem; }
.card-tags { display: flex; gap: 0.25rem; flex-wrap: wrap; margin-bottom: 0.75rem; }

.card-params { margin-bottom: 0.75rem; }
.card-param-row { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 0.2rem; }
.card-param-label { color: var(--text-muted); }
.card-param-value { font-weight: 600; }

.card-footer { border-top: 1px solid var(--border-subtle); padding-top: 0.5rem; margin-top: 0.5rem; }
.card-status-row { display: flex; justify-content: space-between; align-items: center; font-size: 0.75rem; }
.card-time { color: var(--text-muted); font-size: 0.7rem; }
```

### 1.8 Confidence / Probability Score Bars

```css
.score-bar-container { margin-bottom: 0.75rem; }
.score-bar-label { display: flex; justify-content: space-between; font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem; }
.score-bar-track { background: var(--bg-elevated); border-radius: 999px; height: 6px; overflow: hidden; }
.score-bar-fill { height: 100%; border-radius: 999px; transition: width 0.3s ease; }
/* Colour applied via JS: --color-valid (≥75), --color-wait (50-74), #ef4444 (<50) */
```

### 1.9 Filter Bar

```css
.filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1.5rem; flex-wrap: wrap; align-items: center; }
.filter-btn {
  padding: 0.4rem 1rem;
  border-radius: 6px;
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 0.8rem;
  transition: background 0.15s, color 0.15s;
}
.filter-btn:hover { background: var(--bg-elevated); color: var(--text-primary); }
.filter-btn.active { background: var(--bg-elevated); color: var(--text-primary); border-color: var(--text-muted); }
```

### 1.10 Active Signals Panel

```css
.active-panel { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 8px; overflow: hidden; }
.active-panel-header { padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-default); font-weight: 600; font-size: 0.875rem; }
.signal-row {
  display: flex; align-items: center; gap: 0.75rem;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s;
}
.signal-row:last-child { border-bottom: none; }
.signal-row:hover { background: var(--bg-elevated); }
.signal-name { font-weight: 600; font-size: 0.85rem; flex: 1; }
.signal-params { display: flex; gap: 1rem; font-size: 0.78rem; color: var(--text-muted); }
.signal-confidence { font-size: 0.78rem; color: var(--text-muted); white-space: nowrap; }
.empty-state { padding: 2rem; text-align: center; color: var(--text-muted); font-size: 0.875rem; }
```

### 1.11 Detail Page — Trade Parameters Grid

```css
.params-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem 2rem; margin-bottom: 1.5rem; }
.param-item { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid var(--border-subtle); }
.param-label { color: var(--text-muted); font-size: 0.825rem; }
.param-value { font-weight: 600; font-size: 0.9rem; }
.param-sub { font-size: 0.7rem; color: var(--text-muted); }
```

### 1.12 4-Agent Debate Collapsibles

```css
.agent-section { border: 1px solid var(--border-default); border-radius: 8px; margin-bottom: 0.75rem; overflow: hidden; }
.agent-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 0.875rem 1rem;
  cursor: pointer;
  background: var(--bg-surface);
  user-select: none;
}
.agent-header:hover { background: var(--bg-elevated); }
.agent-title { font-weight: 600; font-size: 0.875rem; }
.agent-score { font-size: 0.8rem; color: var(--text-muted); }
.agent-chevron { transition: transform 0.25s ease; color: var(--text-muted); font-size: 0.75rem; }
.agent-section.expanded .agent-chevron { transform: rotate(180deg); }
.agent-body { display: none; padding: 1rem; background: var(--bg-primary); border-top: 1px solid var(--border-default); }
.agent-section.expanded .agent-body { display: block; }

.condition-list { list-style: none; margin-bottom: 0.75rem; }
.condition-item { display: flex; align-items: flex-start; gap: 0.5rem; padding: 0.25rem 0; font-size: 0.825rem; }
.condition-icon { width: 16px; flex-shrink: 0; text-align: center; }
.condition-icon.met     { color: var(--color-valid); }
.condition-icon.not-met { color: var(--color-sell); }
.condition-icon.partial { color: var(--color-wait); }
.condition-label { color: var(--text-secondary); }

.flags-list { margin-top: 0.5rem; }
.flag-item { font-size: 0.8rem; color: var(--text-muted); padding: 0.2rem 0; }
.flag-item::before { content: '⚑ '; }
```

### 1.13 Verdict Summary

```css
.verdict-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1.5rem; }
.verdict-col { background: var(--bg-supporting); border-radius: 8px; padding: 1rem; }
.verdict-col.opposing { background: var(--bg-opposing); }
.verdict-col-title { font-weight: 600; font-size: 0.825rem; margin-bottom: 0.75rem; }
.verdict-col.supporting .verdict-col-title { color: var(--text-supporting); }
.verdict-col.opposing .verdict-col-title   { color: var(--text-opposing); }
.verdict-list { list-style: none; }
.verdict-list li { font-size: 0.8rem; color: var(--text-secondary); padding: 0.2rem 0 0.2rem 1rem; position: relative; }
.verdict-list li::before { content: '•'; position: absolute; left: 0; }
.verdict-summary-text { background: var(--bg-surface); border: 1px solid var(--border-default); border-radius: 8px; padding: 1rem; font-size: 0.875rem; line-height: 1.7; color: var(--text-secondary); }
```

### 1.14 Stale Data Banner

```css
.stale-banner {
  display: none;
  background: rgba(245, 158, 11, 0.15);
  border-bottom: 1px solid var(--color-wait);
  padding: 0.5rem 1.5rem;
  font-size: 0.8rem;
  color: var(--color-wait);
  text-align: center;
}
.stale-banner.visible { display: block; }
```

### 1.15 Session and Price Display

```css
.price-row { display: flex; align-items: baseline; gap: 2rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
.price-bid { font-size: 3rem; font-weight: 700; letter-spacing: -0.02em; }
.price-ask { font-size: 1.5rem; color: var(--text-muted); }
.price-spread { font-size: 0.8rem; color: var(--text-muted); }
.session-badge {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.3rem 0.75rem; border-radius: 6px;
  font-size: 0.825rem; font-weight: 600;
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
}
.session-badge.tokyo    { border-color: #60a5fa; color: #60a5fa; }
.session-badge.london   { border-color: #a78bfa; color: #a78bfa; }
.session-badge.new-york { border-color: #34d399; color: #34d399; }
.session-badge.off      { color: var(--text-muted); }
.session-next { font-size: 0.75rem; color: var(--text-muted); margin-top: 0.25rem; }
```

### 1.16 Responsive Breakpoints

```css
@media (max-width: 1199px) {
  .cards-grid { grid-template-columns: repeat(2, 1fr); }
  .tile-strip { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 767px) {
  .cards-grid { grid-template-columns: 1fr; }
  .tile-strip { grid-template-columns: 1fr 1fr; }
  .col-split { grid-template-columns: 1fr; }
  .params-grid { grid-template-columns: 1fr; }
  .verdict-columns { grid-template-columns: 1fr; }
}
@media (max-width: 479px) {
  .nav .nav-clock,
  .nav .nav-link:not(:first-of-type) { display: none; }
  .tile-strip { grid-template-columns: 1fr; }
}
```

### 1.17 Loading and Error States

```css
.loading-msg { text-align: center; padding: 3rem; color: var(--text-muted); font-size: 0.9rem; }
.error-page { text-align: center; padding: 4rem 2rem; }
.error-page h2 { font-size: 1.25rem; margin-bottom: 0.75rem; }
.error-page p { color: var(--text-muted); margin-bottom: 1.5rem; }
.back-link { color: var(--color-valid); text-decoration: underline; cursor: pointer; }
```

**Verify after Step 1:** Open the CSS file in a browser or editor and confirm all custom properties are defined and there are no syntax errors. No page rendering needed yet.

---

## Step 2 — Shared JavaScript (`frontend/js/shared.js`)

**Delivers:** Polling engine, countdown timer, stale banner, MT5 dot update, UTC clock. Used by all three pages.

```javascript
const API_BASE = 'http://localhost:8000';

// ── State ──────────────────────────────────────────────────────────────
let isInFlight = false;
let countdown = 60;
let lastSuccessTime = null;

// ── Nav bar elements (populated after DOM is ready) ──────────────────
let navPrice, navClock, navCountdown, navMt5Dot, staleBanner;

function initSharedNav() {
  navPrice     = document.getElementById('nav-price');
  navClock     = document.getElementById('nav-clock');
  navCountdown = document.getElementById('nav-countdown');
  navMt5Dot    = document.getElementById('mt5-dot');
  staleBanner  = document.getElementById('stale-banner');

  // UTC clock — updates every second
  setInterval(() => {
    if (navClock) navClock.textContent = new Date().toUTCString().slice(17, 25) + ' UTC';
  }, 1000);
}

// ── Polling engine ────────────────────────────────────────────────────
function startPolling(fetchFn) {
  // Fire immediately on load
  runFetch(fetchFn);

  setInterval(() => {
    countdown--;
    if (navCountdown) navCountdown.textContent = `Refreshing in: ${countdown}s`;
    if (countdown <= 0) {
      countdown = 60;
      if (!isInFlight) runFetch(fetchFn);
    }
  }, 1000);
}

async function runFetch(fetchFn) {
  if (isInFlight) return;
  isInFlight = true;
  try {
    await fetchFn();
    lastSuccessTime = new Date();
    hideStaleBanner();
  } catch (err) {
    showStaleBanner();
    console.error('[USDJPY Agent] Fetch error:', err);
  } finally {
    isInFlight = false;
    countdown = 60;
    if (navCountdown) navCountdown.textContent = `Refreshing in: ${countdown}s`;
  }
}

// ── Stale banner ──────────────────────────────────────────────────────
function showStaleBanner() {
  if (!staleBanner) return;
  const ts = lastSuccessTime
    ? lastSuccessTime.toUTCString().slice(0, 25) + ' UTC'
    : 'never';
  staleBanner.textContent = `Stale data — last updated ${ts}`;
  staleBanner.classList.add('visible');
}
function hideStaleBanner() {
  if (staleBanner) staleBanner.classList.remove('visible');
}

// ── MT5 dot ───────────────────────────────────────────────────────────
function updateMt5Dot(connected) {
  if (!navMt5Dot) return;
  navMt5Dot.className = 'mt5-dot ' + (connected ? 'connected' : 'disconnected');
  navMt5Dot.title = connected ? 'MT5 Connected' : 'MT5 Disconnected';
}

// ── Price display (nav bar) ───────────────────────────────────────────
function updateNavPrice(bid) {
  if (navPrice && bid != null) navPrice.textContent = `¥${bid.toFixed(3)}`;
}

// ── Relative time (e.g. "14 mins ago") ───────────────────────────────
function relativeTime(isoString) {
  if (!isoString) return '—';
  const diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
  if (diff < 60)  return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)} mins ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

// ── Score bar colour ──────────────────────────────────────────────────
function scoreColour(score) {
  if (score >= 75) return 'var(--color-valid)';
  if (score >= 50) return 'var(--color-wait)';
  return '#ef4444';
}

// ── VIX regime label ──────────────────────────────────────────────────
function vixLabel(vix) {
  if (vix < 15)  return 'Low';
  if (vix < 25)  return 'Elevated';
  return 'High';
}

// ── Session detection (UTC hour) ──────────────────────────────────────
function currentSession(utcHour) {
  // Overlapping sessions: London takes priority over Tokyo (08:00–09:00),
  // New York takes priority over London (13:00–17:00)
  if (utcHour >= 13 && utcHour < 22) return 'New York';
  if (utcHour >= 8  && utcHour < 17) return 'London';
  if (utcHour >= 0  && utcHour < 9)  return 'Tokyo';
  return 'Off-Hours';
}

// Returns minutes until next session opens
function minsToNextSession(utcHour, utcMin) {
  const sessionStarts = [0, 8, 13]; // Tokyo, London, New York (UTC hours)
  const totalMins = utcHour * 60 + utcMin;
  for (const h of sessionStarts) {
    const sessionMins = h * 60;
    if (sessionMins > totalMins) return sessionMins - totalMins;
  }
  // Next is Tokyo tomorrow
  return (24 * 60) - totalMins;
}

// ── Pip distance (USDJPY: pip = 0.01) ────────────────────────────────
function pips(a, b) {
  return Math.abs((a - b) * 100).toFixed(1);
}

// ── Countdown to UTC time (HH:MM) ─────────────────────────────────────
function countdownToUtc(isoString) {
  if (!isoString) return '—';
  const diff = Math.max(0, new Date(isoString).getTime() - Date.now());
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}`;
}

// ── Safe API fetch (handles response wrapper) ─────────────────────────
async function apiFetch(path) {
  const res = await fetch(API_BASE + path);
  if (!res.ok) throw new Error(`HTTP ${res.status} from ${path}`);
  const json = await res.json();
  if (!json.success) throw new Error(json.error || `API error from ${path}`);
  return json.data;
}

// ── Status fetch (for MT5 dot) ────────────────────────────────────────
async function fetchStatus() {
  try {
    const data = await apiFetch('/api/status');
    updateMt5Dot(data.mt5_connected);
  } catch {
    updateMt5Dot(false);
  }
}
```

**Verify after Step 2:** No page yet, but open browser dev tools console and include this script in an HTML file — confirm no syntax errors.

---

## Step 3 — Dashboard HTML (`frontend/index.html`)

**Delivers:** Dashboard page shell with all structural HTML. No data yet — just skeleton.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>USDJPY Smart Agent — Dashboard</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>

<nav class="nav">
  <span class="nav-title">USDJPY Smart Agent</span>
  <a href="/index.html" class="nav-link">Dashboard</a>
  <a href="/strategies.html" class="nav-link">Strategies</a>
  <span class="mt5-dot" id="mt5-dot" title="MT5 status"></span>
  <span class="nav-price" id="nav-price">—</span>
  <span class="nav-clock" id="nav-clock">—</span>
  <span class="nav-countdown" id="nav-countdown">Refreshing in: 60s</span>
</nav>

<div class="stale-banner" id="stale-banner"></div>

<div class="container">

  <!-- Row 1: Price + Session -->
  <div class="section">
    <div class="price-row">
      <div>
        <div class="price-bid" id="price-bid">—</div>
        <div class="price-spread" id="price-spread">Spread: — pips</div>
      </div>
      <div>
        <div style="color:var(--text-muted);font-size:0.8rem;margin-bottom:0.25rem;">Ask</div>
        <div class="price-ask" id="price-ask">—</div>
      </div>
      <div>
        <div class="session-badge" id="session-badge">—</div>
        <div class="session-next" id="session-next"></div>
      </div>
    </div>
  </div>

  <!-- Row 2: Market Context Strip -->
  <div class="section">
    <div class="tile-strip">
      <div class="tile">
        <div class="tile-label">DXY</div>
        <div class="tile-value" id="tile-dxy">—</div>
      </div>
      <div class="tile">
        <div class="tile-label">US 10Y Yield</div>
        <div class="tile-value" id="tile-us10y">—</div>
        <div class="tile-sub">%</div>
      </div>
      <div class="tile">
        <div class="tile-label">VIX</div>
        <div class="tile-value" id="tile-vix">—</div>
        <div class="tile-sub" id="tile-vix-regime">—</div>
      </div>
      <div class="tile">
        <div class="tile-label">Next Event</div>
        <div class="tile-value" id="tile-event-countdown" style="font-size:1.2rem">—</div>
        <div class="tile-sub" id="tile-event-name">—</div>
        <span class="badge" id="tile-event-impact" style="margin-top:0.25rem"></span>
      </div>
    </div>
  </div>

  <!-- Row 3: Signal Summary + Active Signals -->
  <div class="section col-split">

    <!-- Left: Signal Summary Counts -->
    <div>
      <h3 style="margin-bottom:1rem;font-size:0.875rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;">Signal Summary</h3>
      <div class="count-group">
        <div class="count-badge count-badge-valid">
          <span class="count" id="count-valid">—</span>
          <span class="label">Valid Trade</span>
        </div>
        <div class="count-badge count-badge-wait">
          <span class="count" id="count-wait">—</span>
          <span class="label">Wait for Levels</span>
        </div>
        <div class="count-badge count-badge-no-trade">
          <span class="count" id="count-no-trade">—</span>
          <span class="label">No Trade</span>
        </div>
      </div>
    </div>

    <!-- Right: Active Signals Panel -->
    <div>
      <div class="active-panel">
        <div class="active-panel-header">Active Signals</div>
        <div id="active-signals-list">
          <div class="empty-state">Loading…</div>
        </div>
      </div>
    </div>

  </div>
</div>

<script src="/js/shared.js"></script>
<script src="/js/dashboard.js"></script>
</body>
</html>
```

**Verify after Step 3:** Open `http://localhost:8000` in Chrome. Page loads (HTTP 200), nav renders, all placeholder "—" values visible, no console errors.

---

## Step 4 — Dashboard JavaScript (`frontend/js/dashboard.js`)

**Delivers:** All data fetching and rendering logic for the Dashboard.

```javascript
const API_BASE = 'http://localhost:8000'; // single source — also in shared.js

document.addEventListener('DOMContentLoaded', () => {
  initSharedNav();
  startPolling(fetchDashboardData);
});

async function fetchDashboardData() {
  const [dash, strategies] = await Promise.all([
    apiFetch('/api/dashboard'),
    apiFetch('/api/strategies')
  ]);
  fetchStatus(); // MT5 dot — fire and forget
  renderPrice(dash);
  renderSession();
  renderMarketContext(dash);
  renderSignalCounts(dash);
  renderActiveSignals(strategies);
  updateNavPrice(dash.usdjpy_bid);
}

// ── Price row ─────────────────────────────────────────────────────────
function renderPrice(d) {
  document.getElementById('price-bid').textContent = d.usdjpy_bid != null ? d.usdjpy_bid.toFixed(3) : '—';
  document.getElementById('price-ask').textContent = d.usdjpy_ask != null ? d.usdjpy_ask.toFixed(3) : '—';
  if (d.usdjpy_bid != null && d.usdjpy_ask != null) {
    const spread = ((d.usdjpy_ask - d.usdjpy_bid) * 100).toFixed(1);
    document.getElementById('price-spread').textContent = `Spread: ${spread} pips`;
  }
}

// ── Session row ───────────────────────────────────────────────────────
function renderSession() {
  const now = new Date();
  const h = now.getUTCHours();
  const m = now.getUTCMinutes();
  const session = currentSession(h);
  const badge = document.getElementById('session-badge');
  badge.textContent = session;
  badge.className = 'session-badge ' + session.toLowerCase().replace(' ', '-').replace('-hours', '');

  const mins = minsToNextSession(h, m);
  const nextH = String(Math.floor(mins / 60)).padStart(2, '0');
  const nextM = String(mins % 60).padStart(2, '0');
  document.getElementById('session-next').textContent = `Next session in ${nextH}:${nextM}`;
}

// ── Market context strip ──────────────────────────────────────────────
function renderMarketContext(d) {
  if (d.dxy   != null) document.getElementById('tile-dxy').textContent   = d.dxy.toFixed(2);
  if (d.us10y != null) document.getElementById('tile-us10y').textContent = d.us10y.toFixed(2);
  if (d.vix   != null) {
    document.getElementById('tile-vix').textContent        = d.vix.toFixed(1);
    document.getElementById('tile-vix-regime').textContent = vixLabel(d.vix);
  }
  if (d.next_event) {
    document.getElementById('tile-event-name').textContent      = d.next_event;
    document.getElementById('tile-event-countdown').textContent  = countdownToUtc(d.next_event_time);
    const impactBadge = document.getElementById('tile-event-impact');
    impactBadge.textContent = d.next_event_impact || '';
    impactBadge.className = 'badge ' + (d.next_event_impact === 'High' ? 'badge-wait' : '');
  }
}

// ── Signal summary counts ─────────────────────────────────────────────
function renderSignalCounts(d) {
  document.getElementById('count-valid').textContent    = d.valid_count    ?? '—';
  document.getElementById('count-wait').textContent     = d.wait_count     ?? '—';
  document.getElementById('count-no-trade').textContent = d.no_trade_count ?? '—';
}

// ── Active signals panel ──────────────────────────────────────────────
function renderActiveSignals(strategies) {
  const active = strategies.filter(s => s.status === 'VALID' || s.status === 'WAIT');
  const list = document.getElementById('active-signals-list');
  list.innerHTML = ''; // safe — no API data inserted as HTML

  if (active.length === 0) {
    const msg = document.createElement('div');
    msg.className = 'empty-state';
    msg.textContent = 'No active setups at this time';
    list.appendChild(msg);
    return;
  }

  for (const s of active) {
    const row = document.createElement('div');
    row.className = 'signal-row';
    row.addEventListener('click', () => {
      window.location.href = `/detail.html?strategy=${s.id}`;
    });

    const name = document.createElement('div');
    name.className = 'signal-name';
    name.textContent = s.name;

    const chip = document.createElement('span');
    chip.className = s.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
    chip.textContent = s.direction ?? '—';

    const params = document.createElement('div');
    params.className = 'signal-params';
    params.textContent = `E: ${s.entry?.toFixed(3) ?? '—'}  SL: ${s.sl?.toFixed(3) ?? '—'}  TP1: ${s.tp1?.toFixed(3) ?? '—'}`;

    const conf = document.createElement('div');
    conf.className = 'signal-confidence';
    conf.textContent = `${s.confidence ?? '—'}% confidence`;

    row.appendChild(name);
    row.appendChild(chip);
    row.appendChild(params);
    row.appendChild(conf);
    list.appendChild(row);
  }
}
```

**Verify after Step 4:** Dashboard shows live bid/ask/spread, session badge, DXY/US10Y/VIX values, signal counts, and active signals list (or empty state). No console errors.

---

## Step 5 — Strategy Cards HTML (`frontend/strategies.html`)

**Delivers:** Strategies page shell with filter bar and cards grid.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>USDJPY Smart Agent — Strategies</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>

<nav class="nav">
  <span class="nav-title">USDJPY Smart Agent</span>
  <a href="/index.html" class="nav-link">Dashboard</a>
  <a href="/strategies.html" class="nav-link">Strategies</a>
  <span class="mt5-dot" id="mt5-dot" title="MT5 status"></span>
  <span class="nav-price" id="nav-price">—</span>
  <span class="nav-clock" id="nav-clock">—</span>
  <span class="nav-countdown" id="nav-countdown">Refreshing in: 60s</span>
</nav>

<div class="stale-banner" id="stale-banner"></div>

<div class="container">
  <div class="filter-bar" id="filter-bar">
    <button class="filter-btn active" data-filter="all">All <span id="count-all">(20)</span></button>
    <button class="filter-btn" data-filter="VALID">Valid Trade <span id="count-valid">(0)</span></button>
    <button class="filter-btn" data-filter="WAIT">Wait for Levels <span id="count-wait">(0)</span></button>
    <button class="filter-btn" data-filter="NO_TRADE">No Trade <span id="count-no-trade">(0)</span></button>
  </div>
  <div class="cards-grid" id="cards-grid">
    <div class="loading-msg">Loading strategies…</div>
  </div>
</div>

<script src="/js/shared.js"></script>
<script src="/js/strategies.js"></script>
</body>
</html>
```

**Verify after Step 5:** Page loads, filter bar with four buttons visible, "Loading strategies…" shown. No console errors.

---

## Step 6 — Strategy Cards JavaScript (`frontend/js/strategies.js`)

**Delivers:** All card rendering, filter logic, and state preservation.

```javascript
let activeFilter = 'all';
let strategiesData = [];

// Strategy type → CSS class map (for type badge label)
const TYPE_LABELS = {
  'Trend': 'Trend', 'Breakout': 'Breakout',
  'Mean Reversion': 'Mean Rev.', 'Hybrid': 'Hybrid', 'Event-Driven': 'Event'
};

document.addEventListener('DOMContentLoaded', () => {
  initSharedNav();
  setupFilterButtons();
  startPolling(fetchStrategies);
});

function setupFilterButtons() {
  document.getElementById('filter-bar').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    activeFilter = btn.dataset.filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    applyFilter();
  });
}

async function fetchStrategies() {
  const [data, dash] = await Promise.all([
    apiFetch('/api/strategies'),
    apiFetch('/api/dashboard')
  ]);
  fetchStatus();
  strategiesData = data;
  updateNavPrice(dash.usdjpy_bid);
  updateFilterCounts(data);
  renderCards(data);
  applyFilter();
}

function updateFilterCounts(strategies) {
  const valid    = strategies.filter(s => s.status === 'VALID').length;
  const wait     = strategies.filter(s => s.status === 'WAIT').length;
  const noTrade  = strategies.filter(s => s.status === 'NO_TRADE').length;
  document.getElementById('count-all').textContent     = `(${strategies.length})`;
  document.getElementById('count-valid').textContent   = `(${valid})`;
  document.getElementById('count-wait').textContent    = `(${wait})`;
  document.getElementById('count-no-trade').textContent = `(${noTrade})`;
}

function renderCards(strategies) {
  const grid = document.getElementById('cards-grid');
  grid.innerHTML = '';
  for (const s of strategies) {
    grid.appendChild(buildCard(s));
  }
}

function buildCard(s) {
  const statusClass = s.status === 'VALID' ? 'valid' : s.status === 'WAIT' ? 'wait' : 'no-trade';
  const card = document.createElement('div');
  card.className = `card ${statusClass}`;
  card.dataset.status = s.status;
  card.dataset.strategyId = s.id;

  // Header row
  const hdr = document.createElement('div');
  hdr.className = 'card-header';
  const numEl = document.createElement('span');
  numEl.className = 'card-num';
  numEl.textContent = `#${s.id}`;
  const typeEl = document.createElement('span');
  typeEl.className = 'type-badge';
  typeEl.textContent = TYPE_LABELS[s.type] ?? s.type;
  hdr.appendChild(numEl);
  hdr.appendChild(typeEl);

  const nameEl = document.createElement('div');
  nameEl.className = 'card-name';
  nameEl.textContent = s.name;

  // Timeframe tags
  const tagsEl = document.createElement('div');
  tagsEl.className = 'card-tags';
  if (s.timeframes) {
    for (const tf of s.timeframes.split('/')) {
      const chip = document.createElement('span');
      chip.className = 'tf-chip';
      chip.textContent = tf.trim();
      tagsEl.appendChild(chip);
    }
  }

  // Trade params (VALID/WAIT only)
  let paramsEl = null;
  if (s.status !== 'NO_TRADE') {
    paramsEl = document.createElement('div');
    paramsEl.className = 'card-params';

    const dirChip = document.createElement('div');
    dirChip.style.marginBottom = '0.5rem';
    const chip = document.createElement('span');
    chip.className = s.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
    chip.textContent = s.direction ?? '—';
    dirChip.appendChild(chip);

    for (const [label, value] of [
      ['Entry', s.entry?.toFixed(3)],
      ['Stop Loss', s.sl?.toFixed(3)],
      ['TP1', s.tp1?.toFixed(3)],
      ['RRR', s.rrr?.toFixed(2)]
    ]) {
      const row = document.createElement('div');
      row.className = 'card-param-row';
      const lbl = document.createElement('span');
      lbl.className = 'card-param-label';
      lbl.textContent = label;
      const val = document.createElement('span');
      val.className = 'card-param-value';
      val.textContent = value ?? '—';
      row.appendChild(lbl);
      row.appendChild(val);
      paramsEl.appendChild(row);
    }
    paramsEl.insertBefore(dirChip, paramsEl.firstChild);
  }

  // Confidence bar
  const confContainer = document.createElement('div');
  confContainer.className = 'score-bar-container';
  const confLabel = document.createElement('div');
  confLabel.className = 'score-bar-label';
  const confLabelText = document.createElement('span');
  confLabelText.textContent = 'Confidence';
  const confNum = document.createElement('span');
  confNum.textContent = `${s.confidence ?? '—'}%`;
  confLabel.appendChild(confLabelText);
  confLabel.appendChild(confNum);
  const track = document.createElement('div');
  track.className = 'score-bar-track';
  const fill = document.createElement('div');
  fill.className = 'score-bar-fill';
  fill.style.width = `${s.confidence ?? 0}%`;
  fill.style.background = scoreColour(s.confidence ?? 0);
  track.appendChild(fill);
  confContainer.appendChild(confLabel);
  confContainer.appendChild(track);

  // Footer
  const footer = document.createElement('div');
  footer.className = 'card-footer';
  const statusRow = document.createElement('div');
  statusRow.className = 'card-status-row';
  const statusLabelEl = document.createElement('span');
  statusLabelEl.className = `badge badge-${statusClass}`;
  statusLabelEl.textContent = s.status === 'NO_TRADE' ? 'No Trade' : s.status === 'VALID' ? 'Valid Trade' : 'Wait for Levels';
  const timeEl = document.createElement('span');
  timeEl.className = 'card-time';
  timeEl.textContent = relativeTime(s.evaluated_at);
  statusRow.appendChild(statusLabelEl);
  statusRow.appendChild(timeEl);
  footer.appendChild(statusRow);

  // Assemble
  card.appendChild(hdr);
  card.appendChild(nameEl);
  card.appendChild(tagsEl);
  if (paramsEl) card.appendChild(paramsEl);
  card.appendChild(confContainer);
  card.appendChild(footer);

  // Click handler
  card.addEventListener('click', () => {
    window.location.href = `/detail.html?strategy=${s.id}`;
  });

  return card;
}

function applyFilter() {
  document.querySelectorAll('.card').forEach(card => {
    if (activeFilter === 'all' || card.dataset.status === activeFilter) {
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
    }
  });
}
```

**Verify after Step 6:**
- 20 cards render with correct status colours
- Filter buttons show/hide correct cards
- Counts in parentheses are accurate
- Clicking a card navigates to detail page
- No console errors

---

## Step 7 — Strategy Detail HTML (`frontend/detail.html`)

**Delivers:** Detail page shell with all section structure.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>USDJPY Smart Agent — Strategy Detail</title>
  <link rel="stylesheet" href="/css/styles.css">
</head>
<body>

<nav class="nav">
  <span class="nav-title">USDJPY Smart Agent</span>
  <a href="/index.html" class="nav-link">Dashboard</a>
  <a href="/strategies.html" class="nav-link">Strategies</a>
  <span class="mt5-dot" id="mt5-dot" title="MT5 status"></span>
  <span class="nav-price" id="nav-price">—</span>
  <span class="nav-clock" id="nav-clock">—</span>
  <span class="nav-countdown" id="nav-countdown">Refreshing in: 60s</span>
</nav>

<div class="stale-banner" id="stale-banner"></div>

<div class="container" id="main-content">
  <div class="loading-msg" id="loading-msg">Loading strategy…</div>
  <div id="error-view" style="display:none" class="error-page">
    <h2>Invalid Strategy</h2>
    <p>The strategy ID in the URL is not valid (must be 1–20).</p>
    <a href="/strategies.html" class="back-link">← Return to Strategies</a>
  </div>
  <div id="detail-view" style="display:none">

    <!-- Header -->
    <div class="section">
      <a href="/strategies.html" class="back-link" style="font-size:0.825rem;">← Back to Strategies</a>
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-top:0.75rem;flex-wrap:wrap;gap:0.5rem;">
        <div>
          <h1 id="detail-name" style="font-size:1.5rem;font-weight:700;margin-bottom:0.5rem;">—</h1>
          <div style="display:flex;gap:0.5rem;flex-wrap:wrap;" id="detail-tags"></div>
        </div>
        <div style="text-align:right;">
          <div id="detail-status-badge"></div>
          <div style="font-size:0.75rem;color:var(--text-muted);margin-top:0.25rem;" id="detail-eval-time"></div>
        </div>
      </div>
    </div>

    <!-- Trade Parameters -->
    <div class="section" id="params-section">
      <h2 style="font-size:0.875rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">Trade Parameters</h2>
      <div class="params-grid" id="params-grid"></div>
    </div>

    <!-- Scores -->
    <div class="section">
      <h2 style="font-size:0.875rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">Scores</h2>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;" id="scores-grid">
        <div class="score-bar-container">
          <div class="score-bar-label">
            <span>Confidence</span><span id="conf-num">—</span>
          </div>
          <div class="score-bar-track"><div class="score-bar-fill" id="conf-bar"></div></div>
        </div>
        <div class="score-bar-container">
          <div class="score-bar-label">
            <span>Probability</span><span id="prob-num">—</span>
          </div>
          <div class="score-bar-track"><div class="score-bar-fill" id="prob-bar"></div></div>
        </div>
      </div>
    </div>

    <!-- 4-Agent Debate -->
    <div class="section">
      <h2 style="font-size:0.875rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">4-Agent Debate</h2>
      <div id="agents-container"></div>
    </div>

    <!-- Verdict Summary -->
    <div class="section">
      <h2 style="font-size:0.875rem;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:1rem;">Verdict Summary</h2>
      <div class="verdict-columns">
        <div class="verdict-col supporting">
          <div class="verdict-col-title">Supporting Reasons</div>
          <ul class="verdict-list" id="reasons-for"></ul>
        </div>
        <div class="verdict-col opposing">
          <div class="verdict-col-title">Opposing Reasons</div>
          <ul class="verdict-list" id="reasons-against"></ul>
        </div>
      </div>
      <div class="verdict-summary-text" id="verdict-summary"></div>
    </div>

  </div><!-- #detail-view -->
</div>

<script src="/js/shared.js"></script>
<script src="/js/detail.js"></script>
</body>
</html>
```

**Verify after Step 7:** `detail.html?strategy=99` shows "Invalid Strategy" error message with back link. `detail.html` with no param also shows error. No console errors.

---

## Step 8 — Strategy Detail JavaScript (`frontend/js/detail.js`)

**Delivers:** Full detail page rendering with agent debate collapsibles and state preservation.

```javascript
// Validate query param before any fetch
const params = new URLSearchParams(window.location.search);
const rawId = params.get('strategy');
const strategyId = parseInt(rawId, 10);

const CONDITION_ICONS = { met: '✓', not_met: '✗', partial: '⚠' };
const CONDITION_CLASSES = { met: 'met', not_met: 'not-met', partial: 'partial' };

document.addEventListener('DOMContentLoaded', () => {
  if (!rawId || isNaN(strategyId) || strategyId < 1 || strategyId > 20) {
    document.getElementById('loading-msg').style.display = 'none';
    document.getElementById('error-view').style.display = 'block';
    return;
  }
  initSharedNav();
  startPolling(fetchDetail);
});

async function fetchDetail() {
  const data = await apiFetch(`/api/strategy/${strategyId}`);
  fetchStatus();
  document.getElementById('loading-msg').style.display = 'none';
  document.getElementById('detail-view').style.display = 'block';
  renderHeader(data);
  renderParams(data);
  renderScores(data);
  renderAgents(data.agents);
  renderVerdict(data);
}

// ── Header ────────────────────────────────────────────────────────────
function renderHeader(d) {
  document.getElementById('detail-name').textContent = d.name;

  const tags = document.getElementById('detail-tags');
  tags.innerHTML = '';
  const typeBadge = document.createElement('span');
  typeBadge.className = 'type-badge';
  typeBadge.textContent = d.type;
  tags.appendChild(typeBadge);
  if (d.timeframes) {
    for (const tf of d.timeframes.split('/')) {
      const chip = document.createElement('span');
      chip.className = 'tf-chip';
      chip.textContent = tf.trim();
      tags.appendChild(chip);
    }
  }

  const statusClass = d.status === 'VALID' ? 'valid' : d.status === 'WAIT' ? 'wait' : 'no-trade';
  const statusBadge = document.getElementById('detail-status-badge');
  statusBadge.innerHTML = '';
  const badge = document.createElement('span');
  badge.className = `badge badge-${statusClass} badge-large`;
  badge.textContent = d.status === 'NO_TRADE' ? 'No Trade' : d.status === 'VALID' ? 'Valid Trade' : 'Wait for Levels';
  statusBadge.appendChild(badge);

  document.getElementById('detail-eval-time').textContent =
    d.evaluated_at ? `Evaluated: ${new Date(d.evaluated_at).toUTCString()}` : '';
}

// ── Trade parameters ──────────────────────────────────────────────────
function renderParams(d) {
  const section = document.getElementById('params-section');
  const grid = document.getElementById('params-grid');
  grid.innerHTML = '';

  if (d.status === 'NO_TRADE') {
    section.style.display = 'none';
    return;
  }
  section.style.display = 'block';

  const rows = [
    ['Direction', null, d.direction],   // special render
    ['Entry',     null, d.entry?.toFixed(3)],
    ['Stop Loss', d.entry && d.sl ? `${pips(d.entry, d.sl)} pips` : null, d.sl?.toFixed(3)],
    ['Take Profit 1', d.entry && d.tp1 ? `+${pips(d.entry, d.tp1)} pips` : null, d.tp1?.toFixed(3)],
    ['Take Profit 2', null, d.tp2?.toFixed(3)],
    ['Take Profit 3', null, d.tp3 ? d.tp3.toFixed(3) : null],
    ['Risk-Reward', null, d.rrr ? `${d.rrr.toFixed(2)}:1` : null],
  ];

  if (d.status === 'WAIT') {
    rows.push(['Wait Zone', null, d.wait_zone ?? 'Watch for price to reach entry zone']);
  }

  for (const [label, sub, value] of rows) {
    if (value == null && label !== 'Wait Zone') continue; // skip null optional rows
    const item = document.createElement('div');
    item.className = 'param-item';
    const lbl = document.createElement('span');
    lbl.className = 'param-label';
    lbl.textContent = label;
    const valWrap = document.createElement('div');
    valWrap.style.textAlign = 'right';

    if (label === 'Direction') {
      const chip = document.createElement('span');
      chip.className = d.direction === 'BUY' ? 'chip-buy' : 'chip-sell';
      chip.textContent = d.direction ?? '—';
      valWrap.appendChild(chip);
    } else {
      const val = document.createElement('div');
      val.className = 'param-value';
      val.textContent = value ?? '—';
      valWrap.appendChild(val);
      if (sub) {
        const subEl = document.createElement('div');
        subEl.className = 'param-sub';
        subEl.textContent = sub;
        valWrap.appendChild(subEl);
      }
    }

    item.appendChild(lbl);
    item.appendChild(valWrap);
    grid.appendChild(item);
  }

  // Conditions to meet (WAIT only)
  if (d.status === 'WAIT' && d.conditions_to_meet?.length) {
    const condSection = document.createElement('div');
    condSection.style.marginTop = '1rem';
    const condTitle = document.createElement('div');
    condTitle.style.cssText = 'font-size:0.8rem;color:var(--text-muted);margin-bottom:0.5rem;';
    condTitle.textContent = 'Conditions to Meet Before Entry:';
    const condList = document.createElement('ul');
    condList.className = 'verdict-list';
    condList.style.color = 'var(--text-secondary)';
    for (const cond of d.conditions_to_meet) {
      const li = document.createElement('li');
      li.textContent = cond;
      condList.appendChild(li);
    }
    condSection.appendChild(condTitle);
    condSection.appendChild(condList);
    grid.appendChild(condSection);
  }
}

// ── Scores ────────────────────────────────────────────────────────────
function renderScores(d) {
  setBar('conf-bar', 'conf-num', d.confidence);
  setBar('prob-bar', 'prob-num', d.probability);
}
function setBar(barId, numId, score) {
  document.getElementById(numId).textContent = score != null ? `${score}%` : '—';
  const bar = document.getElementById(barId);
  bar.style.width = `${score ?? 0}%`;
  bar.style.background = scoreColour(score ?? 0);
}

// ── 4-Agent Debate ────────────────────────────────────────────────────
function renderAgents(agents) {
  if (!agents?.length) return;

  // Capture current expanded state before re-rendering
  const expandedIndices = new Set();
  document.querySelectorAll('.agent-section').forEach((el, i) => {
    if (el.classList.contains('expanded')) expandedIndices.add(i);
  });

  const container = document.getElementById('agents-container');
  container.innerHTML = '';

  agents.forEach((agent, idx) => {
    const section = document.createElement('div');
    section.className = 'agent-section' + (expandedIndices.has(idx) ? ' expanded' : '');
    section.dataset.agentIndex = idx;

    const header = document.createElement('div');
    header.className = 'agent-header';
    header.addEventListener('click', () => section.classList.toggle('expanded'));

    const title = document.createElement('span');
    title.className = 'agent-title';
    title.textContent = agent.name;
    const scoreEl = document.createElement('span');
    scoreEl.className = 'agent-score';
    scoreEl.textContent = `Score: ${agent.score?.toFixed(1) ?? '—'}/10`;
    const chevron = document.createElement('span');
    chevron.className = 'agent-chevron';
    chevron.textContent = '▾';

    header.appendChild(title);
    header.appendChild(scoreEl);
    header.appendChild(chevron);

    const body = document.createElement('div');
    body.className = 'agent-body';

    // Conditions list
    if (agent.conditions?.length) {
      const condList = document.createElement('ul');
      condList.className = 'condition-list';
      for (const c of agent.conditions) {
        const li = document.createElement('li');
        li.className = 'condition-item';
        const icon = document.createElement('span');
        icon.className = `condition-icon ${CONDITION_CLASSES[c.result] ?? ''}`;
        icon.textContent = CONDITION_ICONS[c.result] ?? '?';
        const lbl = document.createElement('span');
        lbl.className = 'condition-label';
        lbl.textContent = c.label;
        li.appendChild(icon);
        li.appendChild(lbl);
        condList.appendChild(li);
      }
      body.appendChild(condList);
    }

    // Flags
    if (agent.flags?.length) {
      const flagsDiv = document.createElement('div');
      flagsDiv.className = 'flags-list';
      for (const flag of agent.flags) {
        const f = document.createElement('div');
        f.className = 'flag-item';
        f.textContent = flag;
        flagsDiv.appendChild(f);
      }
      body.appendChild(flagsDiv);
    }

    section.appendChild(header);
    section.appendChild(body);
    container.appendChild(section);
  });
}

// ── Verdict Summary ───────────────────────────────────────────────────
function renderVerdict(d) {
  const forList = document.getElementById('reasons-for');
  const againstList = document.getElementById('reasons-against');
  forList.innerHTML = '';
  againstList.innerHTML = '';

  for (const reason of (d.reasons_for ?? [])) {
    const li = document.createElement('li');
    li.textContent = reason;
    forList.appendChild(li);
  }
  for (const reason of (d.reasons_against ?? [])) {
    const li = document.createElement('li');
    li.textContent = reason;
    againstList.appendChild(li);
  }

  document.getElementById('verdict-summary').textContent = d.verdict_summary ?? '';
}
```

**Verify after Step 8:**
- Clicking any strategy card/signal navigates to detail page
- All sections render with correct data
- Confidence/probability bars fill and colour correctly
- 4 collapsible agent sections toggle individually
- Expanded sections stay expanded across refresh cycles
- WAIT verdict shows Wait Zone and conditions
- NO TRADE verdict hides trade parameters grid

---

## Step 9 — Final Integration and Verification

### 9.1 FastAPI Mount Confirmation

Confirm `backend/main.py` ends with (after all API routes):

```python
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="frontend", html=True), name="static")
```

### 9.2 Acceptance Criteria Verification Checklist

Run through each of the 35 ACs from Spec Section 10 in Chrome with MT5 connected and disconnected states:

| AC | Test Action | Pass Condition |
|----|------------|----------------|
| AC-3-01 | Open `http://localhost:8000` | HTTP 200, dashboard renders |
| AC-3-02 | Check nav bar on all 3 pages | Title, links, MT5 dot, price, clock, countdown all visible |
| AC-3-03 | Look at dashboard row 1 | Bid, ask, spread displayed |
| AC-3-04 | Check dashboard at different UTC hours | Correct session name highlighted |
| AC-3-05 | Look at market context strip | DXY, US10Y, VIX + regime, next event + countdown |
| AC-3-06 | Count badges vs API | Counts sum to 20, match `/api/strategies` |
| AC-3-07 | Active signals panel | VALID+WAIT listed, or "No active setups" empty state |
| AC-3-08 | Click active signal | Navigates to correct `detail.html?strategy={id}` |
| AC-3-09 | Open strategies.html | Exactly 20 cards rendered |
| AC-3-10 | Inspect card borders | Green/amber/grey left borders correct per status |
| AC-3-11 | Inspect card content | Type badge, TF chips, conf bar, status label, "X mins ago" |
| AC-3-12 | VALID/WAIT vs NO_TRADE cards | Direction+params shown/hidden correctly |
| AC-3-13 | Click each filter button | Only matching cards visible |
| AC-3-14 | Check filter counts | Parenthesis counts match card counts |
| AC-3-15 | Click any strategy card | Navigates to correct strategy detail |
| AC-3-16 | Detail page header | Name, type badge, TF chips, status badge, UTC timestamp |
| AC-3-17 | VALID strategy detail | All param rows present (direction, entry, SL, TP1, TP2, TP3?, RRR) |
| AC-3-18 | SL and TP1 rows | Pip distances shown alongside prices |
| AC-3-19 | NO_TRADE strategy detail | Params section absent |
| AC-3-20 | Score bars | Fill width = score%, colour green/amber/red by threshold |
| AC-3-21 | Agent sections | 4 present, each toggles independently |
| AC-3-22 | Expand each agent section | Score, 11 conditions with ✓/✗/⚠, any flags |
| AC-3-23 | Verdict section | Two columns: green-tinted (for) + red-tinted (against) |
| AC-3-24 | Verdict narrative | Text paragraph below columns |
| AC-3-25 | All pages | Countdown visible and counting down every second |
| AC-3-26 | Wait 60s | New fetch fires automatically |
| AC-3-27 | Slow API simulation | Only one in-flight request at a time |
| AC-3-28 | Kill backend, wait for next poll | Stale banner appears, last data still visible |
| AC-3-29 | Restart backend, wait for next poll | Banner disappears, data updates |
| AC-3-30 | Open `detail.html` (no param) | Graceful error message displayed |
| AC-3-31 | Open `detail.html?strategy=abc` | Graceful error message displayed |
| AC-3-32 | All pages, normal state | Zero JS console errors in Chrome DevTools |
| AC-3-33 | Resize browser window | Cards: 4→2→1 columns at correct breakpoints |
| AC-3-34 | Inspect HTML files | No inline `style` attributes on elements |
| AC-3-35 | Search all frontend files | No credentials, tokens, or API keys present |

### 9.3 Edge Cases to Manually Test

- Strategy with `tp3: null` → TP3 row absent on detail page
- All 20 strategies return NO_TRADE → active signals panel shows empty state
- WAIT strategy with `wait_zone: null` → shows "Watch for price to reach entry zone"
- Filter set to "Valid Trade" when refresh fires → filter is preserved after re-render
- Expand agent section 2, wait for 60s refresh → section 2 remains expanded
- `detail.html?strategy=0` and `detail.html?strategy=21` → both show error

---

## Critical Implementation Notes

1. **Never use `innerHTML` with API data.** Always `textContent` or programmatic element creation. This prevents XSS (NFR-3-16).

2. **API base URL in one place per file.** `const API_BASE = 'http://localhost:8000'` at the top of `shared.js`. Pages reference `apiFetch()` which uses this constant (NFR-3-15).

3. **USDJPY pip = 0.01** — the formula is `abs(a - b) * 100`, not `* 10000` like forex majors. USDJPY is quoted to 3 decimal places.

4. **StaticFiles mount must be last** in `main.py`. If registered before API routes, it captures all requests and the API 404s.

5. **`apiFetch()` unwraps the response envelope.** All endpoints return `{ "success": bool, "data": {...} }`. The function returns `json.data` directly.

6. **Session overlap logic:** London and New York sessions overlap. The spec doesn't define priority — the plan resolves it as: New York takes priority over London (13:00–17:00 UTC), London takes priority over Tokyo (08:00–09:00 UTC).

7. **Relative timestamps** must be recalculated every DOM render, not cached — per NFR-3-11. The `relativeTime()` function calls `Date.now()` at invocation time.

8. **Filter state preserved on refresh:** `activeFilter` is a module-level variable in `strategies.js`. After `renderCards()` runs on a poll, `applyFilter()` is called immediately to re-apply the active filter.

9. **Agent section expanded state preserved on refresh:** Before `renderAgents()` clears the container, it records which indices are expanded. After re-rendering, it re-adds the `expanded` class to those indices.

10. **`shared.js` is included before the page-specific JS** in every HTML `<script>` tag order. The page JS relies on functions exported by `shared.js` (`initSharedNav`, `startPolling`, `apiFetch`, etc.).

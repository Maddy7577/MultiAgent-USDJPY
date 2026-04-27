# Phase 4 — Notifications & Signal History Plan

## Context

Phases 1–3 delivered the full evaluation engine, 20 strategy modules, 4-agent debate framework, SQLite signal store, FastAPI backend, and the 3-page frontend (Dashboard, Strategies, Detail). Phase 4 is purely additive: it wires up Telegram alerts for VALID_TRADE transitions and adds a queryable signal history log to the frontend. No changes to the strategy engine or core evaluation logic.

---

## Current State

- `backend/notifications/__init__.py` — empty stub, ready for implementation
- `backend/api/history.py` — `GET /api/history` and `GET /api/history/{id}` already exist; missing `status` filter param and `PATCH` outcome endpoint
- `backend/db/signal_store.py` — `get_signals()` only filters by `strategy_id`; no deduplication logic; no `update_outcome()` function
- `backend/scheduler.py` — `_h1_evaluation()` calls `batch_insert_signals()` but has no Telegram hook or last-cycle caching
- `frontend/` — no `history.html`; nav in all 3 pages has no "History" link
- `config.py` — `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are already defined from env vars

---

## Implementation Steps

### Step 1 — Database migration: add `telegram_failed` column

**File:** `backend/db/signal_store.py`

In `initialize()`, after the existing migration block, add:
```python
cursor.execute("ALTER TABLE signals ADD COLUMN telegram_failed INTEGER DEFAULT 0")
```
Wrap in `try/except` for `OperationalError` (column already exists pattern used by existing migrations).

Also add a new function:
```python
def update_signal_outcome(signal_id: int, outcome: str) -> bool:
    # UPDATE signals SET outcome = ? WHERE id = ?
    # Returns True if rowcount == 1
```

---

### Step 2 — Signal write deduplication

**File:** `backend/db/signal_store.py`, `insert_signal()` function

Before the INSERT, run a lookup:
```sql
SELECT id FROM signals
WHERE strategy_id = ? AND status = ? AND entry IS ? AND sl IS ?
  AND timestamp >= datetime('now', '-4 hours')
ORDER BY timestamp DESC LIMIT 1
```
- If a match exists: run `UPDATE signals SET timestamp = ? WHERE id = ?` and return the existing `id`
- If no match: proceed with INSERT as before

This prevents thousands of identical NO_TRADE rows accumulating overnight.

---

### Step 3 — History API completion

**File:** `backend/api/history.py`

**3a. Add `status` query param to `GET /api/history`:**
```python
@router.get("/history")
async def get_history(page: int = 1, per_page: int = 50, status: str = None, strategy_id: int = None):
```
Pass `status` through to `signal_store.get_signals()`.

Also update `signal_store.get_signals()` to accept `status: str = None` and add `AND status = ?` to the WHERE clause when provided.

**3b. Add `PATCH /api/history/{signal_id}/outcome`:**
```python
@router.patch("/history/{signal_id}/outcome")
async def update_outcome(signal_id: int, body: OutcomeUpdate):
    # body: { "outcome": "WIN" | "LOSS" | "N/A" }
    # validates outcome value, calls signal_store.update_signal_outcome()
```

---

### Step 4 — Telegram bot module

**File:** `backend/notifications/telegram_bot.py` (new file)

Uses `python-telegram-bot` v20+ (async). Do NOT use `requests` directly since the FastAPI event loop is already running.

```python
async def send_valid_trade_alert(result: StrategyResult) -> bool:
    """
    Sends one Telegram message for a VALID_TRADE result.
    Returns True on success, False on permanent failure (after 1 retry).
    Logs errors but never raises.
    """
```

**Message template** (matches spec exactly):
```
[USDJPY Smart Agent] 🔔 VALID TRADE

Strategy: {strategy_name} (#{strategy_id})
Direction: {direction}
Entry: {entry:.3f}
Stop Loss: {sl:.3f}  ({sl_pips:+.0f} pips)
TP1: {tp1:.3f}  ({tp1_pips:+.0f} pips)
TP2: {tp2:.3f}  ({tp2_pips:+.0f} pips)   ← omit if tp2 is None
Risk-Reward: 1:{rrr:.1f}
Confidence: {confidence}/100
Timeframes: {" / ".join(timeframes)}

Why: {", ".join(reasons_for[:3])}
Against: {", ".join(reasons_against[:2])}

Evaluated: {evaluated_at.strftime("%H:%M")} UTC
```

**Error handling:**
1. Try to send via `bot.send_message(chat_id, text, parse_mode=None)`
2. On exception: wait 30 seconds, retry once
3. On second failure: return False (caller marks `telegram_failed = 1` in DB)

**Availability guard:** Return immediately if `config.TELEGRAM_TOKEN` is empty (bot not configured).

---

### Step 5 — Scheduler integration (transition detection)

**File:** `backend/scheduler.py`

**5a. Add module-level cache:**
```python
_last_valid_strategy_ids: set[int] = set()
```

**5b. Modify `_h1_evaluation()` after `batch_insert_signals()`:**
```python
# Detect transitions to VALID_TRADE
current_valid_ids = {r.strategy_id for r in results if r.status == "VALID_TRADE"}
newly_valid = [r for r in results if r.strategy_id in (current_valid_ids - _last_valid_strategy_ids)]
_last_valid_strategy_ids = current_valid_ids  # update for next cycle

# Fire Telegram for each newly valid strategy
for result in newly_valid:
    success = await send_valid_trade_alert(result)  # or asyncio.create_task
    if not success:
        signal_store.mark_telegram_failed(result.strategy_id)
```

Since the scheduler runs in a background thread (APScheduler), Telegram sends must be dispatched to the running event loop via `asyncio.run_coroutine_threadsafe()`.

Add `mark_telegram_failed(strategy_id: int)` to `signal_store.py` — updates the most recent signal row for that strategy: `UPDATE signals SET telegram_failed = 1 WHERE strategy_id = ? ORDER BY timestamp DESC LIMIT 1`.

---

### Step 6 — Frontend: history.html + history.js

**File:** `frontend/history.html` (new)

Structure:
```html
<nav>  <!-- same nav as other pages, with History link added -->
<div class="stale-banner" id="stale-banner" hidden>...</div>
<main class="container">
  <!-- Summary stats bar -->
  <div class="history-stats-bar" id="stats-bar">
    <span id="stat-total">— signals</span>
    <span id="stat-valid">— VALID TRADE</span>
    <span id="stat-winrate">Win Rate: —</span>
    <span id="stat-avg-conf">Avg Confidence: —</span>
  </div>

  <!-- Filter row -->
  <div class="history-filters">
    <select id="filter-strategy">All Strategies / Strategy 1..20</select>
    <select id="filter-status">All Statuses / Valid Trade / Wait / No Trade</select>
    <input type="date" id="filter-from" />
    <input type="date" id="filter-to" />
    <button id="apply-filters">Apply Filters</button>
  </div>

  <!-- Table -->
  <table class="history-table">
    <thead>Timestamp | Strategy | Status | Direction | Entry | SL | TP1 | RRR | Confidence | Outcome</thead>
    <tbody id="history-tbody"></tbody>
  </table>

  <!-- Pagination controls -->
  <div class="pagination" id="pagination"></div>
</main>
```

**File:** `frontend/js/history.js` (new)

Follows the same fetch pattern as `shared.js` (`apiFetch`, `startPolling`).

Key functions:
- `fetchHistoryData()` — calls `apiFetch('/api/history?page=X&per_page=50&status=Y&strategy_id=Z')`; renders table rows + stats bar
- `renderRow(signal)` — creates a `<tr>` with proper badge/chip classes; attaches click handler to navigate to `detail.html?strategy={id}`; attaches inline outcome edit handler on the Outcome `<td>` for PENDING rows
- `renderStatsBar(items, total)` — computes total, VALID count, win rate (with "Insufficient data" guard < 10 resolved), avg confidence of VALID signals
- `handleOutcomeEdit(signalId, td)` — replaces cell text with `<select>WIN/LOSS</select>`, calls `PATCH /api/history/{id}/outcome` on change, re-renders cell

**Existing CSS reused:** `.badge-valid`, `.badge-wait`, `.badge-no-trade`, `.chip-buy`, `.chip-sell`

**New CSS needed in `frontend/css/styles.css`:**
- `.history-table` — full-width, border-collapse, small font
- `.history-table th/td` — padding, border-bottom
- `.history-table tr:hover` — subtle highlight + cursor pointer
- `.history-stats-bar` — flex row, gap, small muted text
- `.history-filters` — flex row, gap, align-center
- `.outcome-win` — green text
- `.outcome-loss` — red text
- `.outcome-pending` — gray text
- `.pagination` — flex row, gap, page buttons

---

### Step 7 — Navigation update (all pages)

**Files:** `frontend/index.html`, `frontend/strategies.html`, `frontend/detail.html`, `frontend/history.html`

Add after the Strategies link in every nav:
```html
<a href="/history.html" class="nav-link">History</a>
```

---

## Critical Files

| File | Change |
|---|---|
| `backend/db/signal_store.py` | Add: deduplication in `insert_signal()`, `update_signal_outcome()`, `mark_telegram_failed()`, migration for `telegram_failed` column, `status` param in `get_signals()` |
| `backend/api/history.py` | Add: `status` query param, `PATCH /history/{id}/outcome` endpoint |
| `backend/notifications/telegram_bot.py` | **NEW** — full async send with retry |
| `backend/scheduler.py` | Add: `_last_valid_strategy_ids` cache, transition detection, Telegram dispatch after `batch_insert_signals()` |
| `frontend/history.html` | **NEW** — filter row, stats bar, table, pagination |
| `frontend/js/history.js` | **NEW** — fetch, render, inline outcome edit |
| `frontend/css/styles.css` | Add: history table, stats bar, outcome badge styles |
| `frontend/index.html` | Add: History nav link |
| `frontend/strategies.html` | Add: History nav link |
| `frontend/detail.html` | Add: History nav link |

---

## Verification Checklist

1. **Telegram transition fire:** Manually call `POST /api/evaluate`, confirm message appears in Telegram within 30s for any VALID_TRADE result. Check that evaluating again immediately does NOT send a duplicate.
2. **Telegram message format:** Compare received message to template — all fields present, pips calculated correctly.
3. **Telegram failure handling:** Temporarily set `TELEGRAM_TOKEN=""` in `.env`, run evaluate — confirm system continues, logs error, `telegram_failed=1` written to DB.
4. **Signal deduplication:** Run `POST /api/evaluate` three times in quick succession; check DB that NO_TRADE strategies have only one updated row, not three.
5. **History API pagination:** `GET /api/history?page=1&per_page=5` returns 5 items; `?status=VALID_TRADE` returns only VALID rows; `?strategy_id=1` returns only strategy 1.
6. **Outcome PATCH:** Call `PATCH /api/history/1/outcome` with `{"outcome": "WIN"}`, verify DB updated, `GET /api/history/1` returns `outcome: WIN`.
7. **History page:** Open `http://localhost:8000/history.html` — table loads with data, filter dropdowns work, status badges are color-coded, BUY/SELL chips correct.
8. **Inline outcome edit:** Click Outcome cell on a PENDING row — dropdown appears, selecting WIN updates in place without page reload.
9. **Win rate stat:** With < 10 resolved signals shows "Insufficient data"; with ≥ 10 resolved shows correct percentage.
10. **Navigation:** History link appears in all 4 pages; active page highlighted.

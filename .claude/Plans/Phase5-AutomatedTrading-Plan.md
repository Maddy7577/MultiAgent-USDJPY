# Phase 5 — AutomatedTrading: Implementation Plan

**Spec:** `.claude/Specs/Phase5-AutomatedTrading-Spec.md`  
**Branch:** `feature/phase-5`  
**Created:** 2026-04-27

---

## Context

Phase 5 adds automated MT5 order execution, position management, and hard risk controls to the USDJPY Smart Agent. The signal engine (Phase 2) already produces fully-formed VALID TRADE verdicts with entry/SL/TP — Phase 5 closes the loop by placing real orders through the live MT5 terminal and managing them through their lifecycle.

This is the highest-risk phase of the project. All implementation must prioritise safety: the global kill-switch defaults to disabled, strategies must be individually opt-in, and every order placement is gated behind 7 mandatory checks.

---

## Key Architecture Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Automation state | In-memory only, resets to `False` on restart | Forces explicit re-enable after every restart — deliberate friction |
| Magic number | `20250000 + strategy_id` | Encodes strategy into every MT5 order; survives backend restarts |
| Drawdown state | Module-level, reconstituted from DB on startup | DB is source of truth; no duplicate accumulation |
| CORS | Add `POST` to `allow_methods` | Required for `/api/automation/toggle` |
| Schema extension | `schema.sql` for table + `_migrate()` guard in `signal_store.py` | Matches existing pattern for both new installs and upgrades |

---

## Critical Prerequisites

Before starting implementation, all of the following must be true:

1. **Phase 4 complete** — `backend/notifications/telegram_bot.py` exists with a working `send_valid_trade_signal()` function (currently missing; Phase 4 has a plan but is not implemented).
2. **MT5 terminal running** — locally installed, authenticated, and connected.
3. **Signal validation gate met** — 60+ days of live signals, 50+ VALID signals, 30+ resolved with WIN/LOSS.

---

## New Files to Create

| File | Purpose |
|------|---------|
| `backend/data/mt5_execution.py` | MT5 order placement, modification, close, query |
| `backend/agents/position_sizer.py` | Lot size calculation |
| `backend/agents/execution_gate.py` | Pre-execution gate (7 checks) |
| `backend/agents/trade_manager.py` | Per-position lifecycle management |
| `backend/agents/drawdown_tracker.py` | Daily drawdown accumulation and halt |
| `backend/agents/execution_orchestrator.py` | Signal → gate → size → place → log → notify |
| `backend/api/automation.py` | 4 new REST endpoints |

## Existing Files to Modify

| File | Change |
|------|--------|
| `backend/config.py` | Add 12 Phase 5 constants |
| `backend/db/schema.sql` | Add `executions` table |
| `backend/db/signal_store.py` | `_migrate()` guard + 5 new functions |
| `backend/scheduler.py` | Extend `_h1_evaluation()`; add drawdown reset job |
| `backend/main.py` | Register automation router; add POST to CORS; startup drawdown init |
| `backend/notifications/telegram_bot.py` | Add 5 Phase 5 notification functions |
| `frontend/index.html` | Add automation status panel |
| `frontend/js/dashboard.js` | Add automation panel polling + render + toggle |

---

## Implementation Steps

### Step 1 — Config Additions
**File:** `backend/config.py`

Append after the existing verdict thresholds block:

```python
# Phase 5 — Automated Trading
AUTOMATION_ENABLED = False               # Global kill-switch — always False at startup
STRATEGIES_ENABLED_FOR_AUTO: list = []   # Must explicitly opt-in each strategy by ID
MAX_RISK_PER_TRADE_PCT = 0.5             # % of equity risked per trade
MAX_CONCURRENT_POSITIONS = 2             # Hard position cap (enforced in gate, not just config)
MAX_DAILY_DRAWDOWN_PCT = 3.0             # Daily loss limit — halts all execution when hit
MAX_SPREAD_EXECUTION_PIPS = 2.5          # Tighter than signal MAX_SPREAD_PIPS=3.0
MAX_LOT_SIZE = 1.0                       # Absolute lot ceiling regardless of sizing calc
TP1_PARTIAL_CLOSE_PCT = 0.50             # Fraction of position closed at TP1

# Signal validation gate — must all pass before automation can be enabled
SIGNAL_VALIDATION_MIN_DAYS = 60
SIGNAL_VALIDATION_MIN_VALID_SIGNALS = 50
SIGNAL_VALIDATION_MIN_RESOLVED = 30

# Strategy management rules: strategy_id → management config dict
# Keys: tp1_partial_pct, trailing_stop_rule, time_stop_bars, invalidation_condition
# Populate when adding a strategy to STRATEGIES_ENABLED_FOR_AUTO
STRATEGY_MANAGEMENT_RULES: dict = {}
```

---

### Step 2 — Database Schema Extension

**File:** `backend/db/schema.sql`

Append after the `market_context` CREATE TABLE block:

```sql
CREATE TABLE IF NOT EXISTS executions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp               DATETIME NOT NULL,
    signal_id               INTEGER  NOT NULL,
    strategy_id             INTEGER  NOT NULL,
    event_type              TEXT     NOT NULL,  -- ORDER_PLACED / ORDER_MODIFIED / ORDER_CLOSED / ORDER_BLOCKED
    direction               TEXT,               -- BUY / SELL / NULL
    lot_size                REAL,
    requested_entry         REAL,
    actual_fill_price       REAL,               -- MT5 fill price (market orders only)
    sl                      REAL,
    tp1                     REAL,
    tp2                     REAL,
    tp3                     REAL,
    ticket                  INTEGER,            -- MT5 ticket number
    mt5_response_code       INTEGER,
    mt5_response_message    TEXT,
    block_reason            TEXT,               -- populated for ORDER_BLOCKED events
    modified_field          TEXT,               -- SL_TRAIL / TP1_PARTIAL for ORDER_MODIFIED
    close_reason            TEXT,               -- TP1 / TP2 / TP3 / SL / TIME_STOP / INVALIDATION
    result_pips             REAL,               -- populated for ORDER_CLOSED
    result_currency         REAL,               -- P&L in account currency
    account_equity_at_trade REAL                -- live equity at time of trade
);
```

**File:** `backend/db/signal_store.py`

In `_migrate()`, add a guard to create the executions table on existing databases:

```python
def _migrate(conn: sqlite3.Connection):
    # Existing Phase 2 column additions ...
    new_columns = [
        ("strategy_type", "TEXT"),
        ("wait_zone", "TEXT"),
        ("conditions_to_meet", "TEXT"),
        ("agent_scores", "TEXT"),
    ]
    for col, col_type in new_columns:
        try:
            conn.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass

    # Phase 5: create executions table if not present
    conn.execute("""
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            signal_id INTEGER NOT NULL,
            strategy_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            direction TEXT, lot_size REAL, requested_entry REAL,
            actual_fill_price REAL, sl REAL, tp1 REAL, tp2 REAL, tp3 REAL,
            ticket INTEGER, mt5_response_code INTEGER, mt5_response_message TEXT,
            block_reason TEXT, modified_field TEXT, close_reason TEXT,
            result_pips REAL, result_currency REAL, account_equity_at_trade REAL
        )
    """)
```

Add 5 new functions following the existing `_conn()` / parameterised SQL / `with _conn() as conn` pattern:

```python
def insert_execution(execution: dict) -> int:
    """Persist one execution event. Returns new row id."""

def get_executions_today(page: int = 1, per_page: int = 50) -> dict:
    """Paginated execution log for today (UTC). Returns {total, page, per_page, items}."""
    # WHERE date(timestamp) = date('now', 'utc') ORDER BY timestamp DESC

def get_execution_by_ticket(ticket: int) -> Optional[dict]:
    """Most recent ORDER_PLACED record for a given MT5 ticket."""

def get_daily_closed_pnl() -> float:
    """Sum of result_currency for ORDER_CLOSED events today. Returns 0.0 if none."""

def get_signal_validation_gate_status() -> dict:
    """
    Query signals table for gate progress.
    Returns {days_elapsed, valid_count, resolved_count,
             days_required, valid_required, resolved_required, all_passed}.
    """
```

---

### Step 3 — MT5 Execution Layer
**New file:** `backend/data/mt5_execution.py`

Follows the same MT5 import pattern as `mt5_feed.py`. Every function returns a dict to match the API envelope style and never raises — all MT5 errors are captured and returned.

```python
import MetaTrader5 as mt5
import logging
from backend import config

logger = logging.getLogger(__name__)

def place_market_order(symbol, direction, lot_size, sl, tp,
                       magic=None, comment="USDJPY-Agent") -> dict:
    """
    Place a market buy or sell order.
    Returns {"success": bool, "ticket": int|None, "fill_price": float|None, "error": str|None,
             "mt5_code": int, "mt5_message": str}
    direction: "BUY" or "SELL"
    magic defaults to 20250000 + strategy_id (caller must pass if known)
    """

def place_pending_order(symbol, direction, order_type, price, lot_size, sl, tp,
                        magic=None, comment="USDJPY-Agent") -> dict:
    """
    Place a pending order (BUY_LIMIT, SELL_LIMIT, BUY_STOP, SELL_STOP).
    order_type: one of those four string literals
    """

def modify_order(ticket, sl, tp) -> dict:
    """Modify SL and/or TP on an existing position by ticket."""

def close_position(ticket, lot_size=None) -> dict:
    """
    Close position by ticket. If lot_size is given and < current volume, partial close.
    Returns {"success": bool, "closed_pips": float|None, "closed_pnl": float|None, "error": str|None}
    """

def get_open_positions(symbol="USDJPY") -> list:
    """Return list of open position dicts with fields from mt5.PositionInfo."""

def get_pending_orders(symbol="USDJPY") -> list:
    """Return list of pending order dicts."""

def get_account_info() -> dict:
    """Return {"equity": float, "balance": float, "margin_free": float, "currency": str}."""
```

**Key implementation notes:**
- Check `mt5.initialize()` before every operation. If not connected, return `{"success": False, "error": "MT5 not connected"}`.
- All `mt5.order_send()` calls must include `sl` and `tp` fields — never leave them at 0.
- Magic number convention: `20250000 + strategy_id`. Caller provides it.
- Use `mt5.ORDER_TIME_GTC` (good till cancelled) for pending orders.

---

### Step 4 — Position Sizing Engine
**New file:** `backend/agents/position_sizer.py`

```python
from decimal import Decimal, ROUND_DOWN
import MetaTrader5 as mt5
import logging

logger = logging.getLogger(__name__)


def calculate_lot_size(account_equity: float, risk_pct: float,
                       sl_pips: float, pip_value_per_lot: float) -> float:
    """
    Formula: floor((equity × risk_pct/100) / (sl_pips × pip_value)) to 0.01 lots.
    Returns 0.0 if result rounds to zero or inputs are invalid.
    """
    if sl_pips <= 0 or pip_value_per_lot <= 0 or account_equity <= 0:
        return 0.0
    raw = (Decimal(str(account_equity)) * Decimal(str(risk_pct)) / 100) \
          / (Decimal(str(sl_pips)) * Decimal(str(pip_value_per_lot)))
    return float(raw.quantize(Decimal("0.01"), rounding=ROUND_DOWN))


def get_pip_value_per_lot(symbol: str, current_price: float) -> float:
    """
    For USDJPY (JPY-quoted pair): 1 pip = 0.01. 1 lot = 100,000 units.
    Pip value per lot in JPY = 1,000 JPY.
    If account currency is USD: pip_value = 1000 / current_price.
    If account currency is JPY: pip_value = 1000.
    Uses mt5.account_info().currency to determine account currency.
    Falls back to USD-denominated calculation if MT5 is unavailable.
    """
```

---

### Step 5 — Execution Gate
**New file:** `backend/agents/execution_gate.py`

```python
from dataclasses import dataclass
from typing import Optional
from backend import config
from backend.agents import drawdown_tracker
from backend.data import mt5_execution

# Block reason constants — used in execution log
AUTOMATION_DISABLED   = "AUTOMATION_DISABLED"
STRATEGY_NOT_ELIGIBLE = "STRATEGY_NOT_ELIGIBLE"
MT5_DISCONNECTED      = "MT5_DISCONNECTED"
SPREAD_EXCEEDED       = "SPREAD_EXCEEDED"
DAILY_DRAWDOWN_LIMIT  = "DAILY_DRAWDOWN_LIMIT"
MAX_POSITIONS_REACHED = "MAX_POSITIONS_REACHED"
NEWS_PROXIMITY        = "NEWS_PROXIMITY"
SIGNAL_INVALIDATED    = "SIGNAL_INVALIDATED"
INVALID_LOT_SIZE      = "INVALID_LOT_SIZE"


@dataclass
class GateResult:
    passed: bool
    block_reason: Optional[str]


def run_all_checks(result, market_data: dict,
                   open_positions: list, daily_drawdown_pct: float) -> GateResult:
    """
    Run all 8 checks in order. Return the first failure encountered.
    result: StrategyResult object.
    market_data: dict with keys 'spread_pips', 'current_price', 'news_events'.
    """
    for check in [
        _check_automation_enabled,
        _check_strategy_eligible,
        _check_mt5_connected,
        _check_spread,
        _check_daily_drawdown,
        _check_position_count,
        _check_news_proximity,
        _check_signal_still_valid,
    ]:
        gate = check(result, market_data, open_positions, daily_drawdown_pct)
        if not gate.passed:
            return gate
    return GateResult(passed=True, block_reason=None)
```

Each `_check_*` is a private function with the same signature as the checks list. Each reads from `config` and the passed parameters — no external calls except `_check_mt5_connected` which calls `mt5_execution.get_account_info()`.

`_check_signal_still_valid`: Verifies current live price is within 5 pips of the signal's entry price. If price has moved more than that, the entry is stale.

---

### Step 6 — Trade Manager
**New file:** `backend/agents/trade_manager.py`

```python
from dataclasses import dataclass, field
from typing import Optional
from backend import config

@dataclass
class ManagementAction:
    ticket: int
    action: str                      # PARTIAL_CLOSE / MODIFY_SL / CLOSE
    strategy_id: int
    lot_size: Optional[float] = None # PARTIAL_CLOSE: lots to close
    new_sl: Optional[float] = None   # MODIFY_SL: new stop loss price
    close_reason: Optional[str] = None  # TP1/TP2/TP3/SL/TIME_STOP/INVALIDATION


def scan_open_positions(open_positions: list, market_data: dict) -> list[ManagementAction]:
    """
    Evaluate each open position for management actions.
    Returns list of actions to execute (at most one per position).
    Skips positions not in STRATEGY_MANAGEMENT_RULES.
    """
    actions = []
    for pos in open_positions:
        strategy_id = pos.get("magic", 0) - 20250000
        rules = config.STRATEGY_MANAGEMENT_RULES.get(strategy_id)
        if rules is None:
            continue
        action = (
            _check_tp1_hit(pos, market_data, rules)
            or _check_trailing_stop(pos, market_data, rules)
            or _check_time_stop(pos, market_data, rules)
            or _check_invalidation(pos, market_data, rules)
        )
        if action:
            actions.append(action)
    return actions
```

Management rule keys (per-strategy dict in `STRATEGY_MANAGEMENT_RULES`):
- `tp1_partial_pct` (float, 0–1): fraction of position to close at TP1
- `trailing_indicator` (str): e.g., `"H4_EMA20"` — interpreted in `_check_trailing_stop`
- `time_stop_bars` (int): max H1 bars to hold without reaching breakeven
- `breakeven_r` (float): R multiple required before time stop applies
- `invalidation_htf_close` (str): e.g., `"H4_close_below_EMA50_long"` — interpreted in `_check_invalidation`

---

### Step 7 — Drawdown Tracker
**New file:** `backend/agents/drawdown_tracker.py`

Module-level state — in-memory, reconstituted from DB at startup:

```python
import logging
from backend import config

logger = logging.getLogger(__name__)

_daily_pnl: float = 0.0       # Sum of today's closed P&L in account currency
_halt_active: bool = False
_starting_equity: float = 0.0


def initialize(account_equity: float) -> None:
    """
    Called once at startup (after DB is ready).
    Reconstitutes today's accumulated P&L from the executions table.
    Sets _halt_active if the limit was already reached today.
    """

def record_close(pnl_currency: float) -> None:
    """Update accumulator after a position is closed. Triggers halt if limit hit."""

def get_daily_drawdown_pct() -> float:
    """Current drawdown as % of starting equity. Only counts losses (not gains)."""

def is_halt_active() -> bool:
    return _halt_active

def reset_for_new_day() -> None:
    """Called at 00:01 UTC. Clears accumulator and lifts halt."""
```

---

### Step 8 — Execution Orchestrator
**New file:** `backend/agents/execution_orchestrator.py`

Central coordinator called from `scheduler._h1_evaluation()` after signals are persisted to DB.

```python
import logging
from datetime import datetime, timezone
from backend import config
from backend.agents import drawdown_tracker, execution_gate, position_sizer, trade_manager
from backend.data import mt5_execution
from backend.db import signal_store
from backend.notifications import telegram_bot

logger = logging.getLogger(__name__)


def process_valid_signals(results: list, market_data: dict, signal_ids: dict) -> None:
    """
    Filter VALID_TRADE results for eligible strategies and attempt execution.
    signal_ids: dict mapping strategy_id → newly inserted signal DB id.
    """
    if not config.AUTOMATION_ENABLED:
        return
    valid = [r for r in results
             if r.status == "VALID_TRADE" and r.strategy_id in config.STRATEGIES_ENABLED_FOR_AUTO]
    if not valid:
        return

    open_positions = mt5_execution.get_open_positions()
    drawdown_pct = drawdown_tracker.get_daily_drawdown_pct()

    for result in valid:
        signal_id = signal_ids.get(result.strategy_id)
        _execute_signal(result, market_data, open_positions, drawdown_pct, signal_id)


def run_position_management(market_data: dict) -> None:
    """
    Check all open positions against their strategy management rules.
    Execute PARTIAL_CLOSE, MODIFY_SL, or CLOSE actions as needed.
    """
    open_positions = mt5_execution.get_open_positions()
    if not open_positions:
        return
    actions = trade_manager.scan_open_positions(open_positions, market_data)
    for action in actions:
        _execute_management_action(action)
```

`_execute_signal()` contains the full flow:
1. Run `execution_gate.run_all_checks()` → if blocked, log + notify + return
2. Call `mt5_execution.get_account_info()` for live equity
3. Calculate SL distance in pips: `abs(result.entry - result.sl) / 0.01`
4. Call `position_sizer.get_pip_value_per_lot()` + `position_sizer.calculate_lot_size()`
5. Cap at `config.MAX_LOT_SIZE`; if lot ≤ 0, log INVALID_LOT_SIZE block + return
6. Call `mt5_execution.place_market_order()` with magic = `20250000 + result.strategy_id`
7. Call `signal_store.insert_execution()` with full details
8. Call `telegram_bot.send_order_placed()` if success; `telegram_bot.send_order_failed()` if not

`_execute_management_action()` handles PARTIAL_CLOSE/MODIFY_SL/CLOSE, calls the appropriate `mt5_execution` function, logs the result, sends Telegram notification, and calls `drawdown_tracker.record_close()` for CLOSE actions.

**Note:** `scheduler._h1_evaluation()` currently calls `batch_insert_signals()` which returns a count, not the individual IDs. This must be changed: either `batch_insert_signals()` returns a `dict[strategy_id → signal_id]`, or a separate pass reads the IDs back after insert. The cleanest change is to update `batch_insert_signals()` to return `dict[int, int]` (strategy_id → inserted id).

---

### Step 9 — Telegram Phase 5 Notifications
**File:** `backend/notifications/telegram_bot.py`

After Phase 4 is implemented, add these 5 functions alongside the existing `send_valid_trade_signal()`:

```python
def send_order_placed(strategy_name: str, direction: str, lot_size: float,
                      fill_price: float, sl: float, tp1: float) -> None:
    """[USDJPY Smart Agent] ORDER PLACED: {direction} {strategy_name} @ {fill_price}
       Lots: {lot_size} | SL: {sl} | TP1: {tp1}"""

def send_order_blocked(strategy_name: str, block_reason: str) -> None:
    """[USDJPY Smart Agent] EXECUTION BLOCKED: {strategy_name}
       Reason: {block_reason}"""

def send_order_modified(ticket: int, modified_field: str, new_value) -> None:
    """[USDJPY Smart Agent] ORDER MODIFIED: Ticket #{ticket}
       {modified_field} updated to {new_value}"""

def send_order_closed(ticket: int, close_reason: str,
                      result_pips: float, result_currency: float) -> None:
    """[USDJPY Smart Agent] ORDER CLOSED: Ticket #{ticket}
       Reason: {close_reason} | Result: {result_pips:+.1f} pips ({result_currency:+.2f})"""

def send_drawdown_halt(drawdown_pct: float) -> None:
    """[USDJPY Smart Agent] DAILY DRAWDOWN HALT
       Reached {drawdown_pct:.2f}% — all execution blocked for today"""
```

---

### Step 10 — New API Endpoints
**New file:** `backend/api/automation.py`

```python
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from backend import config
from backend.agents import drawdown_tracker
from backend.data import mt5_execution
from backend.db import signal_store

router = APIRouter()


@router.get("/automation/status")
def get_automation_status():
    """Returns full automation state, config, gate progress, and drawdown status."""
    if not signal_store.is_initialized():
        return {"success": True, "data": {"automation_enabled": False}, "error": None}
    gate = signal_store.get_signal_validation_gate_status()
    return {
        "success": True,
        "data": {
            "automation_enabled": config.AUTOMATION_ENABLED,
            "strategies_enabled": config.STRATEGIES_ENABLED_FOR_AUTO,
            "config": {
                "max_risk_pct": config.MAX_RISK_PER_TRADE_PCT,
                "max_concurrent_positions": config.MAX_CONCURRENT_POSITIONS,
                "max_daily_drawdown_pct": config.MAX_DAILY_DRAWDOWN_PCT,
                "max_spread_pips": config.MAX_SPREAD_EXECUTION_PIPS,
                "max_lot_size": config.MAX_LOT_SIZE,
            },
            "daily_drawdown_pct": drawdown_tracker.get_daily_drawdown_pct(),
            "daily_drawdown_halted": drawdown_tracker.is_halt_active(),
            "gate": gate,
        },
        "error": None,
    }


@router.post("/automation/toggle")
async def toggle_automation(request: Request):
    """Toggle AUTOMATION_ENABLED. Localhost-only. Checks gate before enabling."""
    if request.client.host not in ("127.0.0.1", "::1"):
        return JSONResponse(status_code=403, content={"success": False, "data": None,
                                                       "error": "Localhost only"})
    if not config.AUTOMATION_ENABLED:
        gate = signal_store.get_signal_validation_gate_status()
        if not gate["all_passed"]:
            return JSONResponse(status_code=400, content={
                "success": False, "data": None,
                "error": "Signal validation gate not passed"
            })
    config.AUTOMATION_ENABLED = not config.AUTOMATION_ENABLED
    return {"success": True, "data": {"automation_enabled": config.AUTOMATION_ENABLED}, "error": None}


@router.get("/automation/positions")
def get_open_positions():
    """Return all open USDJPY positions from MT5."""
    positions = mt5_execution.get_open_positions()
    return {"success": True, "data": {"positions": positions}, "error": None}


@router.get("/automation/executions")
def get_executions(page: int = Query(1, ge=1), per_page: int = Query(50, ge=1, le=200)):
    """Paginated execution log for today."""
    if not signal_store.is_initialized():
        return {"success": True, "data": {"total": 0, "page": page, "per_page": per_page,
                                           "items": []}, "error": None}
    data = signal_store.get_executions_today(page=page, per_page=per_page)
    return {"success": True, "data": data, "error": None}
```

---

### Step 11 — Scheduler Updates
**File:** `backend/scheduler.py`

**Extend `_h1_evaluation()`** — after `signal_store.batch_insert_signals(results)`:

```python
def _h1_evaluation():
    global last_h1_eval_time
    from datetime import datetime, timezone
    from backend.strategies.evaluation_orchestrator import run_evaluation_cycle
    from backend.db import signal_store
    from backend import config

    try:
        results, market_data = run_evaluation_cycle()   # NOTE: orchestrator must return both
        signal_ids = {}
        if signal_store.is_initialized():
            signal_ids = signal_store.batch_insert_signals(results)  # returns dict[strategy_id→id]
        last_h1_eval_time = datetime.now(tz=timezone.utc).isoformat()

        # Phase 5: execution and position management
        if config.AUTOMATION_ENABLED:
            from backend.agents import execution_orchestrator
            execution_orchestrator.process_valid_signals(results, market_data, signal_ids)
            execution_orchestrator.run_position_management(market_data)

    except Exception as exc:
        logger.error(f"H1 evaluation cycle failed: {exc}", exc_info=True)
        last_h1_eval_time = f"ERROR: {exc}"
```

**Note:** `evaluation_orchestrator.run_evaluation_cycle()` currently returns only `list[StrategyResult]`. It must be updated to also return `market_data` as a second value. The market_data dict needs at minimum: `spread_pips`, `current_price`, `news_events`, `h4_bars` (for trailing stop checks).

**Add daily drawdown reset job** in `start()`:

```python
_scheduler.add_job(
    _daily_drawdown_reset,
    CronTrigger(hour=0, minute=1, timezone="UTC"),
    id="drawdown_reset",
    replace_existing=True,
)
```

```python
def _daily_drawdown_reset():
    from backend.agents import drawdown_tracker
    drawdown_tracker.reset_for_new_day()
    logger.info("Daily drawdown accumulator reset for new UTC day")
```

---

### Step 12 — main.py Updates
**File:** `backend/main.py`

Three targeted changes:

**1. Register automation router** (add to imports and include_router block):
```python
from backend.api import automation
# ...
app.include_router(automation.router, prefix="/api")
```

**2. Allow POST in CORS middleware**:
```python
allow_methods=["GET", "POST"],
```

**3. Initialize drawdown tracker at startup** (in `lifespan`, after `scheduler.start()`):
```python
try:
    from backend.agents import drawdown_tracker
    from backend.data import mt5_execution
    acct = mt5_execution.get_account_info()
    if acct.get("equity"):
        drawdown_tracker.initialize(acct["equity"])
    else:
        drawdown_tracker.initialize(0.0)
except Exception as exc:
    logger.warning(f"Drawdown tracker init failed (non-fatal): {exc}")
```

---

### Step 13 — Frontend: Automation Panel
**File:** `frontend/index.html`

Add a new `<section id="automation-panel" class="card">` after the active-signals panel. Structure:

```html
<section id="automation-panel" class="card">
  <div class="panel-header">
    <span class="panel-title">AUTOMATION</span>
    <span id="auto-status-badge" class="badge badge-disabled">DISABLED</span>
    <button id="auto-toggle-btn" class="btn">Enable</button>
  </div>

  <!-- Confirmation dialog -->
  <dialog id="auto-confirm-dialog">
    <p id="auto-confirm-msg"></p>
    <div class="dialog-actions">
      <button id="auto-confirm-yes" class="btn btn-danger">Confirm</button>
      <button id="auto-confirm-no" class="btn">Cancel</button>
    </div>
  </dialog>

  <div class="panel-body three-col">
    <!-- Strategies enabled -->
    <div id="auto-strategies-section">
      <h4>Strategies Enabled for Auto</h4>
      <ul id="auto-strategies-list"><li>None configured</li></ul>
    </div>

    <!-- Open positions -->
    <div id="auto-positions-section">
      <h4>Open Positions</h4>
      <table id="auto-positions-table">
        <thead><tr><th>Strategy</th><th>Dir</th><th>Lots</th><th>Entry</th><th>SL</th><th>TP</th><th>P&L</th></tr></thead>
        <tbody></tbody>
      </table>
      <p id="auto-no-positions">No open positions</p>
    </div>

    <!-- Today's executions -->
    <div id="auto-executions-section">
      <h4>Today's Executions</h4>
      <table id="auto-executions-table">
        <thead><tr><th>Time</th><th>Strategy</th><th>Type</th><th>Dir</th><th>Lots</th><th>Result/Reason</th></tr></thead>
        <tbody></tbody>
      </table>
      <p id="auto-no-executions">No executions today</p>
    </div>
  </div>
</section>
```

**File:** `frontend/js/dashboard.js`

Add to the existing polling function (runs every 60 seconds):

```javascript
async function refreshAutomationPanel() {
    // Fetch all three endpoints in parallel
    const [statusRes, posRes, execRes] = await Promise.all([
        fetch('/api/automation/status').then(r => r.json()).catch(() => null),
        fetch('/api/automation/positions').then(r => r.json()).catch(() => null),
        fetch('/api/automation/executions').then(r => r.json()).catch(() => null),
    ]);
    renderAutomationStatus(statusRes);
    renderOpenPositions(posRes);
    renderExecutionLog(execRes);
}
```

Wire up the toggle button:
```javascript
document.getElementById('auto-toggle-btn').addEventListener('click', () => {
    const isEnabled = document.getElementById('auto-status-badge').classList.contains('badge-enabled');
    document.getElementById('auto-confirm-msg').textContent =
        `Are you sure you want to ${isEnabled ? 'disable' : 'enable'} automated trading?`;
    document.getElementById('auto-confirm-dialog').showModal();
});

document.getElementById('auto-confirm-yes').addEventListener('click', async () => {
    document.getElementById('auto-confirm-dialog').close();
    await fetch('/api/automation/toggle', { method: 'POST' });
    refreshAutomationPanel();
});

document.getElementById('auto-confirm-no').addEventListener('click', () => {
    document.getElementById('auto-confirm-dialog').close();
});
```

Use existing CSS variables and card styling from `frontend/css/styles.css`. P&L values: positive → green text, negative → red text.

---

## Testing Protocol

Execute strictly in this order before enabling automation on the live account.

### Phase A — Unit Tests (No MT5 Required)

| Test | Input | Expected Output |
|------|-------|-----------------|
| `calculate_lot_size(10000, 0.5, 20, 10)` | equity=10k, risk=0.5%, sl=20pip, pipval=10 | `0.25` lots |
| `calculate_lot_size(10000, 0.5, 3, 10)` | very tight SL | `1.66` → `1.66` lots (cap check) |
| `calculate_lot_size(100, 0.5, 50, 10)` | tiny equity | `0.00` (rounds to zero, blocked) |
| `drawdown_tracker`: add losses up to 3%, check `is_halt_active()` | — | True at threshold |
| `execution_gate`: mock `AUTOMATION_ENABLED=False` | — | `AUTOMATION_DISABLED` block |
| `execution_gate`: mock spread=3.0 pips (> 2.5 limit) | — | `SPREAD_EXCEEDED` block |
| `execution_gate`: mock 2 open positions | — | `MAX_POSITIONS_REACHED` block |
| `execution_gate`: mock news event in 15 min | — | `NEWS_PROXIMITY` block |

### Phase B — Gate Integration Test (MT5 Demo, Single Cycle)

1. Set `AUTOMATION_ENABLED = True`, `STRATEGIES_ENABLED_FOR_AUTO = []` → trigger evaluation → confirm zero orders placed
2. Add strategy 1 to `STRATEGIES_ENABLED_FOR_AUTO`, wait for next VALID TRADE → confirm order appears in MT5 with correct SL and TP set on the order
3. With 2 positions already open, trigger another VALID TRADE → confirm `MAX_POSITIONS_REACHED` in execution log
4. Send `POST /api/automation/toggle` from non-localhost → confirm 403 response

### Phase C — Demo Account Full Test (Minimum 2 Weeks)

- Run with `STRATEGIES_ENABLED_FOR_AUTO = [1]` (Strategy 1 only)
- Verify every placed order has hard SL and TP on the MT5 order itself
- Verify partial close at TP1 executes at correct lot fraction
- Temporarily set `MAX_DAILY_DRAWDOWN_PCT = 0.01` → let one small loss trigger halt → verify no further orders that day → verify next day execution resumes
- Check Telegram receives all 5 event types (placed, blocked, modified, closed, halt)

### Phase D — Acceptance Criteria Sweep

Verify all 20 AC items from `Phase5-AutomatedTrading-Spec.md` pass before enabling on live account.

---

## Key Gotchas

1. **`batch_insert_signals()` must return `dict[strategy_id → signal_id]`** — currently returns a count. Update it or add a companion function before Step 8 can work.
2. **`run_evaluation_cycle()` must return `(results, market_data)`** — currently returns only `list[StrategyResult]`. Check `evaluation_orchestrator.py` for the cleanest way to expose `market_data` (it's built internally as `market_data = {ohlcv, indicators, context}`).
3. **`config.AUTOMATION_ENABLED` mutated at runtime** — Python module-level constants are mutable in-memory. The toggle endpoint does `config.AUTOMATION_ENABLED = not config.AUTOMATION_ENABLED`. This works in a single-process Uvicorn setup but will **not** work with multi-worker deployments. Keep `reload=False` and single worker.
4. **CORS currently GET-only** — `allow_methods=["GET"]` blocks POST. Must add `"POST"` before the toggle endpoint works from the frontend.
5. **Partial close lot precision** — MT5 requires lot sizes to match broker minimum step (usually 0.01). Use `ROUND_DOWN` to avoid "invalid volume" errors on partial closes.

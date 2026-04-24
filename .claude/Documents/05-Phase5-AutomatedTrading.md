# Phase 5 — Automated Trading (MT5 Execution)

**Phase:** 5 of 5  
**Phase Status:** FUTURE — Do not implement until Phase 1–4 signals have been live-monitored and validated over a meaningful period.  
**Goal:** Add MT5 order execution capability so the system can place, manage, and close trades automatically based on VALID TRADE verdicts. This phase is gated behind a mandatory signal validation protocol.  
**Deliverable:** A tested, risk-controlled automated execution layer that places real orders through the already-running MT5 terminal.

---

## Mandatory Gate: Signal Validation Protocol

**Phase 5 must not begin until all of the following conditions are met:**

1. The system has been running live (Phases 1–4) for a minimum of **60 calendar days**
2. At least **50 VALID TRADE signals** have been generated across strategies
3. At least **30 of those signals** have been manually tracked to resolution (WIN or LOSS recorded in the history log)
4. The overall observed win rate and average RRR across live signals is consistent with the backtest KPI targets defined in `USDJPY_Algo_Strategy_Reference.md`
5. No systematic errors have been found in the signal engine (false validations, wrong entry levels, incorrect SL/TP calculations)
6. A full review of the signal log has been completed — strategies with poor live performance should be disabled or re-evaluated before automation

**Do not skip or shorten this gate.** Automated trading on unvalidated signals is how accounts are blown.

---

## What Gets Built in This Phase

### 1. MT5 Execution Layer (`data/mt5_execution.py`)

New module alongside `mt5_feed.py`. Uses the same running MT5 terminal connection.

**Capabilities:**
- Place a market order (Buy / Sell) with defined lot size, SL, and TP
- Place a pending order (Buy Limit / Sell Limit / Buy Stop / Sell Stop) at a specific price
- Modify an existing order's SL and TP
- Close a specific open position by ticket number
- Close all positions for USDJPY
- Query all currently open USDJPY positions
- Query pending orders

**Safety rules built into every execution function:**
- Maximum 2 concurrent USDJPY positions at any time (enforced in code, not just config)
- No order is placed if daily drawdown has hit the configured limit
- No order is placed if the spread at execution time exceeds the configured maximum
- Every order placement is logged to SQLite with full parameters and MT5 response
- If MT5 returns an error code, log it and do not retry automatically — raise an alert

### 2. Position Sizing Engine (`agents/position_sizer.py`)

Calculates lot size per trade based on:
- Account equity (fetched live from MT5 at time of trade)
- Configured risk percentage per trade (default 0.5%)
- Stop loss distance in pips
- Current pip value for USDJPY at current price

Formula:
```
Lot Size = (Account Equity × Risk %) / (SL Distance in pips × Pip Value per lot)
```

Lot size is rounded down to the nearest 0.01 lots. Never exceeds the configured maximum lot size.

### 3. Trade Manager (`agents/trade_manager.py`)

Monitors open positions placed by the system and manages them:
- Checks for TP1 hit → close partial position (as defined per strategy — typically 50%)
- Checks for trailing stop conditions (e.g., Strategy 1 trails H4 EMA20)
- Checks for time-stop conditions (e.g., Strategy 1: exit if not at +1R within 18 H1 bars)
- Checks for invalidation conditions (e.g., Strategy 1: exit if H4 closes below EMA50 while long)
- Runs on the same H1 evaluation cycle

### 4. Execution Gate Checks (before any order is placed)

Before executing any VALID TRADE signal, the system runs a pre-execution checklist:

| Check | Action if Failed |
|---|---|
| MT5 connected | Block execution, send Telegram warning |
| Spread ≤ configured max | Block execution, log reason |
| Daily drawdown < limit | Block ALL execution for rest of day |
| Open positions < 2 | Block execution |
| No high-impact news within 30 min | Block execution, log reason |
| Signal still valid (re-check on execution) | Block execution if conditions changed |
| Lot size > 0 and ≤ max lot | Block execution |

All blocked executions are logged with reason. A Telegram notification is sent when a signal is blocked at execution time.

### 5. Automation Configuration (new entries in `config.py`)

```
AUTOMATION_ENABLED        = False  (default OFF — must be manually enabled)
MAX_RISK_PER_TRADE_PCT    = 0.5
MAX_CONCURRENT_POSITIONS  = 2
MAX_DAILY_DRAWDOWN_PCT    = 3.0
MAX_SPREAD_PIPS           = 2.5
MAX_LOT_SIZE              = 1.0
STRATEGIES_ENABLED_FOR_AUTO = []   (empty by default — must explicitly list strategy IDs)
```

`AUTOMATION_ENABLED` defaults to `False`. The user must explicitly set it to `True` in config to activate execution. This is a deliberate friction point.

`STRATEGIES_ENABLED_FOR_AUTO` is an empty list by default. Individual strategies must be explicitly added to this list before they are eligible for automated execution. This allows phased rollout — e.g., enable only Strategy 1 first, validate it, then add others.

### 6. Dashboard Update — Automation Status Panel

New section added to the Dashboard:

- Automation status: ENABLED / DISABLED (with toggle — requires confirmation dialog)
- Strategies enabled for automation: list of strategy names
- Open positions: list of currently open MT5 positions placed by the system
- Today's execution log: orders placed, results, drawdown used

### 7. Telegram Updates for Phase 5

Additional notification types:
- Order placed: strategy name, direction, lot size, entry, SL, TP1
- Order modified: ticket, what changed (SL trailed, TP hit, partial close)
- Order closed: ticket, reason (TP1/TP2/TP3/SL/time-stop/invalidation), result in pips and dollars
- Execution blocked: strategy, reason blocked
- Daily drawdown limit reached: hard halt notice

---

## Phase 5 Testing Protocol (Before Going Live)

Execute these steps in order:

**Step 1 — Demo account testing (minimum 2 weeks)**
- Set `AUTOMATION_ENABLED = True` with `STRATEGIES_ENABLED_FOR_AUTO = [1]` (start with Strategy 1 only)
- Run against a demo/practice account in MT5
- Verify every placed order has correct entry, SL, and TP
- Verify position sizing calculations are correct
- Verify partial close at TP1 executes correctly
- Verify trailing stop logic follows the strategy rules
- Verify daily drawdown halt works

**Step 2 — Prop firm paper review**
- Review all automated trades against prop firm rules (even though rules are not restrictive, confirm alignment)
- Check that no orders were placed during prohibited times or conditions

**Step 3 — Live micro-lot testing (minimum 2 weeks)**
- Switch to the live prop firm account
- Set maximum lot size to 0.01 (minimum)
- Run live for 2 weeks, monitoring every trade
- Compare live execution prices against signal entry prices — check for slippage

**Step 4 — Gradual scale-up**
- If micro-lot testing is satisfactory, increase to 0.5% risk per trade
- Enable additional strategies one at a time
- Monitor drawdown daily

---

## Phase 5 Success Criteria

1. A VALID TRADE signal results in a correctly placed MT5 order with accurate lot size, SL, and TP
2. Pre-execution gate blocks trades correctly when conditions are not met
3. Position sizing formula produces correct lot sizes across different account sizes and SL distances
4. Partial close at TP1 executes correctly and remaining position stays open
5. Daily drawdown halt stops all execution when the limit is reached
6. All executed trades are logged in SQLite with full order detail
7. Telegram notifications fire for every execution event
8. `AUTOMATION_ENABLED = False` in config completely disables all order placement with zero exceptions

---

## Known Risks for This Phase

- **Slippage**: Market orders on USDJPY during news events can have significant slippage. The spread check at execution time reduces but does not eliminate this risk.
- **MT5 terminal closure**: If MT5 closes while positions are open, open positions remain but the trade manager can no longer monitor or modify them. Mitigation: always set physical SL and TP on the MT5 order itself (not just in the system) — this is enforced by the execution layer.
- **Network interruption**: If the Python backend crashes while positions are open, MT5-native SL/TP are the last line of defence. All orders must always include hard SL and TP on placement.
- **Carry unwind events**: Events like August 2024 (USDJPY 162→142 in 3 weeks) can invalidate all open long positions rapidly. The system cannot predict these — wide stops and small sizing are the only defence.
- **Strategy correlation**: Running multiple trend-following strategies simultaneously may result in correlated positions. The 2-position cap is the primary safeguard.

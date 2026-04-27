# Phase 5 — AutomatedTrading Specification

---

## Document Control

| Field        | Value                          |
|--------------|-------------------------------|
| Document ID  | SPEC-PHASE-5-v1.0              |
| Version      | v1.0                           |
| Status       | Draft                          |
| Created      | 2026-04-27                     |
| Author       | USDJPY Smart Agent Project     |
| Phase        | 5 of 5                         |
| Phase Name   | AutomatedTrading               |

### Change History

| Version | Date       | Author | Summary of Changes |
|---------|------------|--------|--------------------|
| v1.0    | 2026-04-27 | —      | Initial draft      |

---

## 1. Introduction

### 1.1 Purpose

This document is the formal software requirements specification for Phase 5 (AutomatedTrading) of the USDJPY Smart Agent system. It defines the complete behavioural requirements — what the system must do — for the automated order execution layer that closes the loop between signal generation and live trade placement through the MetaTrader 5 terminal. This document is intended for use by the developer implementing Phase 5, and as a baseline for acceptance testing once implementation is complete. It does not specify implementation approaches or code structure.

### 1.2 Scope

This specification covers:
- The mandatory signal validation gate that must be passed before automated execution can be activated
- Automation configuration requirements including a global enable/disable control and per-strategy eligibility
- All pre-execution gate checks that must pass before any order is placed
- Order placement (market and pending orders) and the constraints that govern it
- Position sizing calculations
- Position management (partial close, trailing stop, time stop, invalidation exit)
- Daily drawdown tracking and enforcement
- Execution event logging and persistence
- New Telegram notification types introduced in this phase
- New REST API endpoints required to support automation status and control
- Dashboard additions for the automation status panel

This specification does not cover:
- The signal generation pipeline (Phases 1–2)
- The frontend strategy pages and debate display (Phase 3)
- The existing Telegram VALID TRADE signal alert introduced in Phase 4
- The signal history query interface introduced in Phase 4
- Any behaviour of the MT5 terminal itself (order routing, broker fill logic)
- Account management, balance transfers, or broker-level operations
- Multi-currency or multi-symbol execution

### 1.3 Definitions and Abbreviations

| Term / Abbreviation | Definition |
|---------------------|------------|
| MT5 | MetaTrader 5 — the third-party trading terminal used for both price data and order execution |
| OHLCV | Open, High, Low, Close, Volume — the standard bar data format |
| ATR | Average True Range — a volatility indicator |
| EMA | Exponential Moving Average |
| FRED | Federal Reserve Economic Data — the St. Louis Fed public data API |
| VALID TRADE | A strategy verdict indicating a high-confidence, rule-compliant trade setup with entry, SL, and TP defined |
| WAIT FOR LEVELS | A strategy verdict indicating a valid setup in principle where price has not yet reached the entry zone |
| NO TRADE | A strategy verdict indicating conditions are not met or opposing factors are too strong |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| SL | Stop Loss — the price level at which the position is closed to limit loss |
| TP | Take Profit — the price level at which the position is closed to capture a gain; TP1 is the first target, TP2 the second, TP3 the third |
| RRR | Risk-Reward Ratio — the ratio of potential profit to potential loss |
| AC | Acceptance Criterion |
| Market Order | An order to buy or sell immediately at the current available price |
| Pending Order | An order to buy or sell at a future specified price (Buy Limit, Sell Limit, Buy Stop, Sell Stop) |
| Lot Size | The volume unit for MT5 orders; 1 standard lot = 100,000 units of base currency |
| Pip Value | The monetary value per 0.01-price-unit movement per lot for USDJPY at a given price |
| Daily Drawdown | The cumulative realised loss across all positions closed since 00:00 UTC of the current calendar day |
| Partial Close | Closing a defined percentage of an open position while leaving the remainder open |
| Trailing Stop | A stop loss that advances toward current price as profit grows, to lock in gains |
| Time Stop | A position exit triggered by elapsed time rather than price movement |
| Invalidation Condition | A strategy-defined price event that signals the original trade premise is no longer valid |
| Execution Gate | The set of mandatory pre-checks that must all pass before an order is placed |
| Signal Validation Gate | The mandatory live-monitoring period and criteria that must be satisfied before automated execution can be activated |
| Ticket | The unique integer identifier assigned by MT5 to each individual order or position |
| Slippage | The difference between the expected execution price and the actual fill price |
| AUTOMATION_ENABLED | The global boolean configuration flag controlling whether any automated execution is active |
| STRATEGIES_ENABLED_FOR_AUTO | The configuration list of strategy IDs that are eligible for automated order placement |
| Demo Account | An MT5 practice account with simulated funds used for testing execution logic before live deployment |
| Pip | The minimum price increment for USDJPY, equal to 0.01 (i.e., 2 decimal places) |

### 1.4 References

- USDJPY Smart Agent System Architecture (`system_architecture.md`)
- Phase 5 Build Guide (`05-Phase5-AutomatedTrading.md`)
- USDJPY Algorithmic Strategy Reference (`USDJPY_Algo_Strategy_Reference.md`) — referenced for per-strategy position management rules (trailing stop logic, time-stop durations, invalidation conditions, and TP1 partial-close percentages)
- MetaTrader 5 Python Package documentation — `MetaTrader5` Python API used for order operations
- Python APScheduler documentation — scheduler used for H1 evaluation cycle

---

## 2. System Context

### 2.1 Phase Position in System

Phase 5 is the final phase of the USDJPY Smart Agent project. It depends on Phases 1 through 4 being complete, stable, and validated. Phase 1 provides the data pipeline and database schema. Phase 2 provides the strategy engine and 4-agent debate system that generates VALID TRADE verdicts. Phase 3 provides the frontend dashboard. Phase 4 provides Telegram alerting and the signal history log. Phase 5 adds the automated execution capability that converts those validated verdicts into real MT5 orders. There are no successor phases — Phase 5 is the terminal phase.

### 2.2 Phase Goal

Phase 5 must add a safe, gated, risk-controlled automated order execution layer that places, manages, and closes USDJPY trades through the live MT5 terminal based solely on VALID TRADE verdicts generated by the strategy engine, subject to configurable risk controls that cannot be bypassed.

### 2.3 In Scope for This Phase

- Mandatory signal validation gate with explicit criteria that must be met before automation can be enabled
- A global automation enable/disable flag that defaults to disabled
- A per-strategy automation eligibility list that defaults to empty
- Configurable risk parameters: risk percentage per trade, maximum concurrent positions, maximum daily drawdown percentage, maximum spread pips, maximum lot size
- Pre-execution gate checks run before every order placement attempt
- Market order placement for USDJPY with mandatory hard SL and TP
- Pending order placement for USDJPY with mandatory hard SL and TP
- Order modification (SL and TP changes)
- Position closure by ticket number
- Position sizing calculation based on account equity, configured risk percentage, SL distance, and pip value
- Partial close execution when TP1 is hit
- Trailing stop management per strategy-specific rules
- Time-stop exit logic per strategy-specific rules
- Invalidation condition monitoring and position exit
- Daily drawdown tracking, enforcement, and daily reset
- Execution event persistence to the database for every execution attempt (placed, modified, closed, blocked)
- New Telegram notification types for all execution events
- New REST API endpoints for automation status, open positions, and execution log
- Automation status panel on the existing dashboard page
- Dashboard toggle control for enabling/disabling automation, with mandatory confirmation

### 2.4 Out of Scope for This Phase

- Signal generation, strategy evaluation, and the debate engine — these are Phase 2 deliverables and must not be modified by this phase
- Manual trade entry or trade copying from external sources
- Automated strategy backtesting or forward-testing beyond what is run through the live evaluation cycle
- Multi-currency execution (this system trades USDJPY exclusively)
- Account management operations (deposit, withdrawal, account switching)
- Modification of existing broker or MT5 account settings
- Email or SMS notifications (Telegram is the sole notification channel)
- A fully automated start-up sequence that enables automation without explicit user action
- Hedging (simultaneous long and short positions on USDJPY)
- Grid trading, martingale, or position-averaging strategies
- Any execution on an account that is not accessible via the already-running local MT5 terminal
- Reporting or analytics dashboards beyond the execution log panel described in this spec

### 2.5 Predecessor Dependencies

The following specific deliverables must be complete and verified before Phase 5 implementation can begin:

- MT5 terminal connection is established and stable, and `mt5_feed.py` successfully returns live OHLCV data
- All 20 strategy modules evaluate correctly and produce `StrategyResult` objects with populated `entry`, `sl`, and `tp1` fields when verdict is VALID TRADE
- The debate engine produces `confidence` and `probability` scores within expected ranges
- The SQLite `signals` table exists with all columns defined in the system architecture, including the `outcome` column
- `signal_store.py` successfully reads and writes signals without raw SQL in calling code
- The APScheduler H1 evaluation cycle fires reliably at HH:02:00 UTC
- The Telegram bot successfully sends VALID TRADE alerts (Phase 4 deliverable)
- The signal history log is populated with real live signals covering the signal validation gate criteria (60 days, 50 VALID signals, 30 resolved outcomes)
- The `/api/history` endpoint is functional and returns paginated signal data

---

## 3. Functional Requirements

### 3.1 Signal Validation Gate

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-01 | The system SHALL enforce a mandatory signal validation gate that prevents automated execution from being activated until all gate conditions are satisfied | MUST | Given automation has never been enabled, when any single gate condition is unmet, then the system SHALL refuse to activate automation and report which condition failed |
| FR-5-02 | The system SHALL require a minimum of 60 calendar days to have elapsed since the first recorded signal before automated execution can be enabled | MUST | Given the first signal timestamp in the database, when fewer than 60 calendar days have elapsed, then the automation enable action is rejected with a message stating the days remaining |
| FR-5-03 | The system SHALL require a minimum of 50 VALID TRADE signals to exist in the signal history before automated execution can be enabled | MUST | Given the signal history, when fewer than 50 signals with status VALID exist, then the automation enable action is rejected with a message stating the count remaining |
| FR-5-04 | The system SHALL require a minimum of 30 signals with a recorded outcome of WIN or LOSS (not PENDING) before automated execution can be enabled | MUST | Given the signal history, when fewer than 30 signals have a non-PENDING outcome, then the automation enable action is rejected with a message stating the count remaining |
| FR-5-05 | The system SHALL report the current signal validation gate status, showing for each of the four gate conditions whether it is passed or failed and the current progress value | MUST | Given a request for gate status, when the gate status endpoint is called, then the response includes each condition's name, required value, current value, and pass/fail state |

### 3.2 Automation Configuration

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-06 | The system SHALL have a global automation enable/disable flag that defaults to disabled at all times, including on system start-up and restart | MUST | Given a fresh system start, when no explicit enable action has been taken, then AUTOMATION_ENABLED is false and no orders are placed regardless of signal verdicts |
| FR-5-07 | The system SHALL have a per-strategy automation eligibility list that defaults to an empty list | MUST | Given a system with AUTOMATION_ENABLED = true, when STRATEGIES_ENABLED_FOR_AUTO is empty, then no orders are placed for any strategy |
| FR-5-08 | The system SHALL support configuring a maximum risk percentage per trade | MUST | Given a configured risk percentage, when a lot size is calculated, then the monetary risk for the trade does not exceed that percentage of current account equity |
| FR-5-09 | The system SHALL support configuring a maximum number of concurrent open positions | MUST | Given the configured maximum, when the count of open USDJPY positions equals that maximum, then no new orders are placed until a position is closed |
| FR-5-10 | The system SHALL support configuring a maximum daily drawdown percentage | MUST | Given the configured limit, when cumulative daily realised loss reaches that percentage of starting-day equity, then all order placement halts for the remainder of that calendar day |
| FR-5-11 | The system SHALL support configuring a maximum allowable spread in pips at time of execution | MUST | Given the configured maximum, when the live spread at execution time exceeds that value, then the order is blocked and logged |
| FR-5-12 | The system SHALL support configuring a maximum lot size that cannot be exceeded regardless of position sizing calculations | MUST | Given the configured maximum, when the calculated lot size exceeds it, then the lot size is capped at the maximum and the trade is placed at the capped size |
| FR-5-13 | The system SHALL NOT execute any automated trade while AUTOMATION_ENABLED is false | MUST | Given AUTOMATION_ENABLED = false, when any VALID TRADE verdict is produced, then no order is placed and no execution gate checks are run |
| FR-5-14 | The system SHALL NOT execute any automated trade for a strategy whose ID is not present in STRATEGIES_ENABLED_FOR_AUTO | MUST | Given a strategy not in STRATEGIES_ENABLED_FOR_AUTO, when it produces a VALID TRADE verdict, then no order is placed |

### 3.3 Pre-Execution Gate Checks

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-15 | The system SHALL verify MT5 terminal connectivity before placing any order | MUST | Given an MT5 disconnection, when an execution is attempted, then the order is blocked, the block is logged with reason MT5_DISCONNECTED, and a notification is sent |
| FR-5-16 | The system SHALL verify that the live spread at execution time does not exceed the configured maximum before placing any order | MUST | Given a spread above the configured maximum, when an execution is attempted, then the order is blocked and logged with reason SPREAD_EXCEEDED |
| FR-5-17 | The system SHALL verify that cumulative daily drawdown has not reached the configured limit before placing any order | MUST | Given daily drawdown at or above the limit, when an execution is attempted, then the order is blocked and logged with reason DAILY_DRAWDOWN_LIMIT |
| FR-5-18 | The system SHALL verify that the current count of open USDJPY positions is below the configured maximum before placing any order | MUST | Given open positions at or above the configured maximum, when an execution is attempted, then the order is blocked and logged with reason MAX_POSITIONS_REACHED |
| FR-5-19 | The system SHALL verify that no high-impact economic event is scheduled within 30 minutes of execution time before placing any order | MUST | Given a high-impact event within 30 minutes, when an execution is attempted, then the order is blocked and logged with reason NEWS_PROXIMITY |
| FR-5-20 | The system SHALL re-evaluate signal conditions at execution time and verify the original signal conditions are still valid before placing any order | MUST | Given conditions having changed since the signal was generated, when an execution is attempted, then the order is blocked and logged with reason SIGNAL_INVALIDATED |
| FR-5-21 | The system SHALL verify the calculated lot size is greater than zero before placing any order | MUST | Given a lot size calculation that produces zero or a negative value, when an execution is attempted, then the order is blocked and logged with reason INVALID_LOT_SIZE |
| FR-5-22 | The system SHALL log every blocked execution attempt to persistent storage with the strategy ID, timestamp, signal ID, and specific reason for blocking | MUST | Given any blocked execution, when the block occurs, then a record exists in the execution log with status BLOCKED and the reason field populated |
| FR-5-23 | The system SHALL send a Telegram notification when a signal is blocked at execution time | MUST | Given a blocked execution, when the block occurs, then a Telegram message is sent within 60 seconds containing the strategy name and the reason for blocking |

### 3.4 Order Placement

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-24 | The system SHALL be capable of placing a market order (buy or sell) for USDJPY with a specified lot size, stop loss, and take profit | MUST | Given a VALID TRADE verdict passing all gate checks, when a market order is placed, then MT5 confirms an open position with the specified direction and parameters |
| FR-5-25 | The system SHALL be capable of placing a pending order (Buy Limit, Sell Limit, Buy Stop, Sell Stop) for USDJPY with a specified entry price, lot size, stop loss, and take profit | MUST | Given a VALID TRADE verdict with a non-market entry price, when a pending order is placed, then MT5 confirms a pending order record with the specified parameters |
| FR-5-26 | The system SHALL always include a hard stop loss on every order sent to MT5 | MUST | Given any order placement, when the MT5 order request is constructed, then the SL field is populated with the value from the signal's sl field and is not zero |
| FR-5-27 | The system SHALL always include a hard take profit (TP1) on every order sent to MT5 | MUST | Given any order placement, when the MT5 order request is constructed, then the TP field is populated with the signal's tp1 value and is not zero |
| FR-5-28 | The system SHALL log every order placement attempt to persistent storage, including the full order parameters and the MT5 response code and message | MUST | Given any order placement attempt (successful or failed), when MT5 responds, then an execution record exists with all order parameters, the MT5 return code, and the MT5 return message |
| FR-5-29 | The system SHALL NOT automatically retry a failed order placement | MUST | Given an MT5 error response to an order request, when the error is received, then no retry attempt is made automatically, and a notification is sent alerting to the failure |
| FR-5-30 | The system SHALL send a Telegram notification when an order is successfully placed | MUST | Given a successful order placement, when MT5 confirms the order, then a notification is sent within 60 seconds containing the strategy name, direction, lot size, entry, SL, and TP1 |

### 3.5 Position Sizing

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-31 | The system SHALL calculate lot size using the formula: (Account Equity × Risk Percentage) ÷ (SL Distance in Pips × Pip Value per Lot) | MUST | Given known account equity, risk percentage, SL distance, and pip value, when the formula is applied, then the lot size equals the formula result before rounding |
| FR-5-32 | The system SHALL fetch current account equity from MT5 at the time each trade is evaluated for execution, not at a cached earlier time | MUST | Given account equity having changed since the last cycle, when a new lot size is calculated, then the calculation uses the equity value returned by the live MT5 account query made at execution time |
| FR-5-33 | The system SHALL round the calculated lot size down to the nearest 0.01 lots | MUST | Given a calculation result of 0.237 lots, when rounded, then the lot size used is 0.23 lots |
| FR-5-34 | The system SHALL cap the lot size at the configured maximum lot size when the calculated value exceeds it | MUST | Given a calculated lot size of 2.50 and a configured maximum of 1.00, when the cap is applied, then the order is placed with 1.00 lots |
| FR-5-35 | The system SHALL block order placement when the rounded lot size calculates to zero | MUST | Given an account equity too small relative to the SL distance and pip value, when the calculated lot size rounds to zero, then the order is blocked with reason INVALID_LOT_SIZE |

### 3.6 Position Management

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-36 | The system SHALL monitor all open USDJPY positions placed by the system on each H1 evaluation cycle | MUST | Given one or more open positions, when the H1 cycle runs, then the system queries open positions and evaluates each one for management actions |
| FR-5-37 | The system SHALL execute a partial close when a position reaches TP1, closing the percentage of the position defined by the originating strategy | MUST | Given an open position where current price has reached or passed TP1, when the H1 cycle evaluates it, then a partial close order is sent to MT5 for the strategy-defined percentage of the position |
| FR-5-38 | The system SHALL apply trailing stop logic to open positions according to the originating strategy's defined trailing rules | MUST | Given an open position with trailing stop conditions met per the strategy rules, when the H1 cycle evaluates it, then the SL on the MT5 position is modified to the new trailing level |
| FR-5-39 | The system SHALL close a position when the time-stop condition defined by the originating strategy is met | MUST | Given an open position where the elapsed bar count since entry equals the strategy's time-stop threshold without reaching the minimum profit target, when the H1 cycle evaluates it, then a close order is sent to MT5 |
| FR-5-40 | The system SHALL close a position when the strategy-specific invalidation condition is met | MUST | Given an open position where the H4 close satisfies the strategy's invalidation rule, when the H1 cycle evaluates it, then a close order is sent to MT5 with close reason INVALIDATION |
| FR-5-41 | The system SHALL be capable of modifying the stop loss and take profit of an existing order by ticket number | MUST | Given a valid ticket and new SL/TP values, when a modification request is sent to MT5, then MT5 confirms the updated order parameters |
| FR-5-42 | The system SHALL be capable of closing a specific open position by its MT5 ticket number | MUST | Given a valid ticket number of an open position, when a close request is sent, then MT5 confirms the position is closed |
| FR-5-43 | The system SHALL be capable of querying all currently open USDJPY positions | MUST | Given one or more open positions, when a position query is made, then the response contains all open USDJPY positions with ticket, direction, lot size, open price, current SL, current TP, and unrealised P&L |
| FR-5-44 | The system SHALL be capable of querying all pending USDJPY orders | MUST | Given one or more pending orders, when a pending order query is made, then the response contains all pending USDJPY orders with ticket, type, price, lot size, SL, and TP |
| FR-5-45 | The system SHALL send a Telegram notification when an order is modified, stating the ticket number and the field that was changed | MUST | Given a successful order modification, when MT5 confirms the change, then a notification is sent within 60 seconds containing the ticket and the nature of the change |
| FR-5-46 | The system SHALL send a Telegram notification when an order is closed, stating the ticket, the reason for closure, and the result in pips and account currency | MUST | Given a successful position close, when MT5 confirms the closure, then a notification is sent within 60 seconds containing the ticket, close reason (TP1/TP2/TP3/SL/TIME_STOP/INVALIDATION), result in pips, and result in account currency |

### 3.7 Daily Drawdown Control

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-47 | The system SHALL track the cumulative realised loss from all positions closed since 00:00 UTC of the current calendar day | MUST | Given two positions closed at a loss of 1.5% and 1.8% of starting equity, when the drawdown is queried, then the system reports 3.3% cumulative daily drawdown |
| FR-5-48 | The system SHALL halt all new order placement for the remainder of the current calendar day when cumulative daily drawdown reaches the configured limit | MUST | Given daily drawdown at the configured limit, when a new VALID TRADE verdict occurs, then no order is placed, the block is logged with reason DAILY_DRAWDOWN_LIMIT, and a notification is sent |
| FR-5-49 | The system SHALL send a Telegram notification when the daily drawdown limit is reached | MUST | Given drawdown hitting the limit, when the limit is crossed, then a notification is sent within 60 seconds stating the limit has been reached and all execution is halted for the day |
| FR-5-50 | The system SHALL reset the daily drawdown accumulator at 00:00 UTC each calendar day | MUST | Given execution halted due to drawdown limit, when 00:00 UTC of the next calendar day passes, then new order placement is no longer blocked by the drawdown halt |

### 3.8 Execution Logging

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-51 | The system SHALL persist every execution event to a dedicated execution log table in the database | MUST | Given any execution event (ORDER_PLACED, ORDER_MODIFIED, ORDER_CLOSED, ORDER_BLOCKED), when the event occurs, then a record is written to the execution log before the event is considered complete |
| FR-5-52 | The system SHALL record the MT5 response code and message for every order placement attempt | MUST | Given an MT5 response to any order request, when the response is received, then the response code and message are stored in the execution log record for that attempt |
| FR-5-53 | The system SHALL record the actual fill price for every successfully placed market order | MUST | Given a successfully placed market order, when the MT5 confirmation is received, then the fill price is stored in the execution log record |
| FR-5-54 | The system SHALL record the reason for closure for every closed position | MUST | Given a position closure, when the close completes, then the close reason (TP1, TP2, TP3, SL, TIME_STOP, INVALIDATION) is stored in the execution log record |
| FR-5-55 | The system SHALL record the result in pips and account currency for every closed position | MUST | Given a closed position, when the close completes, then both the pips result and the currency P&L are stored in the execution log record |

### 3.9 Dashboard Automation Panel

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-56 | The dashboard SHALL display the current automation status as either ENABLED or DISABLED | MUST | Given AUTOMATION_ENABLED is true, when the dashboard is loaded, then the automation panel displays ENABLED; given false, it displays DISABLED |
| FR-5-57 | The dashboard SHALL display the list of strategies currently enabled for automated execution by name | MUST | Given STRATEGIES_ENABLED_FOR_AUTO contains strategy IDs [1, 3], when the dashboard is loaded, then the panel shows the names of Strategy 1 and Strategy 3 |
| FR-5-58 | The dashboard SHALL display all currently open USDJPY positions placed by the system, including direction, lot size, open price, current SL, current TP, and unrealised P&L | MUST | Given one or more open positions, when the dashboard is loaded, then each position is listed with all specified fields visible |
| FR-5-59 | The dashboard SHALL display the execution log for the current trading day, listing each execution event with its type, strategy, timestamp, and result | MUST | Given execution events today, when the dashboard is loaded, then each event appears in the execution log panel |
| FR-5-60 | The dashboard SHALL provide a control to toggle automation status | MUST | Given the toggle control is present, when it is clicked, then a confirmation dialog is displayed before any state change occurs |
| FR-5-61 | The dashboard SHALL NOT change automation status unless the user explicitly confirms the action in the confirmation dialog | MUST | Given the toggle was clicked, when the user dismisses the confirmation dialog without confirming, then the automation status remains unchanged |
| FR-5-62 | The dashboard automation panel SHALL refresh its data on the same 60-second polling cycle as the rest of the dashboard | SHOULD | Given the panel is visible, when 60 seconds elapse, then the open positions list and execution log are updated without a manual page reload |

### 3.10 New REST API Endpoints

| ID | Requirement | Priority | Acceptance Criterion |
|----|-------------|----------|----------------------|
| FR-5-63 | The system SHALL provide a GET endpoint that returns the current automation status, the list of strategies enabled for automation, the current values of all risk configuration parameters, and the signal validation gate status | MUST | Given a GET request to the automation status endpoint, when the response is received, then it contains all specified fields in the standard `{ "success": true, "data": {} }` format |
| FR-5-64 | The system SHALL provide a POST endpoint to toggle the automation enabled/disabled state | MUST | Given a POST request to the automation toggle endpoint, when processed, then AUTOMATION_ENABLED is changed to the opposite state and the new state is returned in the response |
| FR-5-65 | The system SHALL provide a GET endpoint that returns all currently open USDJPY positions | MUST | Given open positions, when the endpoint is called, then the response lists each position with ticket, direction, lot size, open price, current SL, current TP, and unrealised P&L |
| FR-5-66 | The system SHALL provide a GET endpoint that returns the execution log for the current calendar day, paginated | MUST | Given execution events today, when the endpoint is called, then the response contains a paginated list of execution records for the current day |
| FR-5-67 | All new endpoints SHALL conform to the standard response envelope: `{ "success": bool, "data": {}, "error": null }` | MUST | Given any new endpoint call, when the response is returned, then it contains the `success`, `data`, and `error` fields regardless of success or failure |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-01 | The complete execution gate check sequence — from verdict detection to either order placement or block log — MUST complete within 10 seconds of the VALID TRADE verdict being produced | MUST |
| NFR-5-02 | The order placement request to MT5 MUST be sent within 5 seconds of all gate checks passing | MUST |
| NFR-5-03 | The position management scan across all open positions MUST complete within 15 seconds of the H1 evaluation cycle starting | MUST |
| NFR-5-04 | The daily drawdown accumulator MUST be updated within 5 seconds of a position close event being detected | MUST |
| NFR-5-05 | The automation status panel on the dashboard MUST reflect the current state within one polling cycle (60 seconds) of any state change | SHOULD |

### 4.2 Reliability

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-06 | If MT5 returns an error code during an order placement attempt, the system MUST log the error and send a notification but MUST NOT crash or halt the evaluation cycle | MUST |
| NFR-5-07 | If MT5 becomes unavailable while positions are open, the system MUST NOT attempt order modifications or closures, and MUST log the disconnected state on every cycle until reconnection | MUST |
| NFR-5-08 | If the economic calendar data is stale (older than 6 hours), the system MUST treat the news-proximity gate check as failed and block execution rather than skipping the check | MUST |
| NFR-5-09 | If the position management scan fails for an individual position due to an MT5 error, the system MUST log the failure and continue scanning remaining positions — one position error MUST NOT halt the entire scan | MUST |
| NFR-5-10 | The daily drawdown accumulator MUST survive a backend restart within the same calendar day — accumulated losses for the day MUST be re-derived from the execution log on start-up | MUST |

### 4.3 Data Integrity

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-11 | The same signal (identified by signal ID) MUST NOT result in more than one active open position | MUST |
| NFR-5-12 | Every execution log record MUST be written to the database before the corresponding MT5 action is considered complete — no execution event is considered unlogged | MUST |
| NFR-5-13 | Lot size calculations MUST use Python decimal arithmetic or equivalent precision to prevent floating-point rounding errors from producing incorrect lot values | MUST |
| NFR-5-14 | The daily drawdown accumulator MUST only count closed positions and MUST NOT include unrealised P&L from open positions | MUST |
| NFR-5-15 | The fill price recorded for a market order MUST be the actual execution price returned by MT5, not the signal's entry price | MUST |

### 4.4 Maintainability

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-16 | All automation risk parameters (risk percentage, max positions, max drawdown, max spread, max lot size) MUST be defined exclusively in `config.py` and MUST NOT appear as literals in any execution module | MUST |
| NFR-5-17 | The execution layer MUST be implemented as discrete modules with clear boundaries: MT5 operations, position sizing, trade management, and gate checks each in their own module | MUST |
| NFR-5-18 | No raw SQL MUST appear outside `signal_store.py` for any new database writes introduced in Phase 5 | MUST |

### 4.5 Security

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-19 | No MT5 account credentials (login, password, server) MUST be stored in any project file, environment variable, or database record | MUST |
| NFR-5-20 | The automation toggle API endpoint MUST only be accessible from localhost (127.0.0.1) | MUST |
| NFR-5-21 | No position sizing data, account equity values, or trade parameters MUST be transmitted outside the local machine except via the Telegram bot (which uses end-to-end encrypted transport) | MUST |

### 4.6 Compatibility

| ID | Requirement | Priority |
|----|-------------|----------|
| NFR-5-22 | The execution layer MUST operate on Windows 10 and Windows 11 only — no cross-platform compatibility is required | MUST |
| NFR-5-23 | The system MUST use Python 3.11 or later | MUST |
| NFR-5-24 | The system MUST be compatible with the MetaTrader 5 Python package version 5.0.45 or later | MUST |
| NFR-5-25 | The MT5 terminal MUST be open and authenticated before the execution layer can function — the system MUST report a clear error if MT5 is not running at start-up | MUST |
| NFR-5-26 | The automation status panel MUST render correctly in the same browsers already supported by the Phase 3 frontend (Chromium-based browsers and Firefox, latest stable versions) | MUST |

---

## 5. Data Specifications

### 5.1 Data Models

**New table: `executions`**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY, AUTO INCREMENT | Unique execution record identifier |
| timestamp | DATETIME | NOT NULL | UTC datetime of the execution event |
| signal_id | INTEGER | NOT NULL, FK → signals.id | The signal that triggered this execution |
| strategy_id | INTEGER | NOT NULL, 1–20 | The strategy that produced the signal |
| event_type | TEXT | NOT NULL, one of: ORDER_PLACED, ORDER_MODIFIED, ORDER_CLOSED, ORDER_BLOCKED | The type of execution event |
| direction | TEXT | BUY or SELL or NULL | Trade direction; NULL for ORDER_BLOCKED events |
| lot_size | REAL | NULL permitted | Lot size used; NULL for ORDER_BLOCKED |
| requested_entry | REAL | NULL permitted | Entry price from the original signal |
| actual_fill_price | REAL | NULL permitted | Actual execution price returned by MT5; populated only for ORDER_PLACED |
| sl | REAL | NULL permitted | Stop loss sent to MT5 |
| tp1 | REAL | NULL permitted | Take profit 1 sent to MT5 |
| tp2 | REAL | NULL permitted | Take profit 2, if applicable |
| tp3 | REAL | NULL permitted | Take profit 3, if applicable |
| ticket | INTEGER | NULL permitted | MT5 ticket number; NULL for ORDER_BLOCKED |
| mt5_response_code | INTEGER | NULL permitted | MT5 return code; NULL for ORDER_BLOCKED |
| mt5_response_message | TEXT | NULL permitted | MT5 return message text; NULL for ORDER_BLOCKED |
| block_reason | TEXT | NULL permitted | Reason code for blocked execution; NULL for non-blocked events (MT5_DISCONNECTED, SPREAD_EXCEEDED, DAILY_DRAWDOWN_LIMIT, MAX_POSITIONS_REACHED, NEWS_PROXIMITY, SIGNAL_INVALIDATED, INVALID_LOT_SIZE) |
| modified_field | TEXT | NULL permitted | For ORDER_MODIFIED: what was changed (SL_TRAIL, TP1_PARTIAL, TP2_PARTIAL) |
| close_reason | TEXT | NULL permitted | For ORDER_CLOSED: reason for closure (TP1, TP2, TP3, SL, TIME_STOP, INVALIDATION) |
| result_pips | REAL | NULL permitted | Pips gained or lost; populated only for ORDER_CLOSED |
| result_currency | REAL | NULL permitted | Account currency P&L; populated only for ORDER_CLOSED |
| account_equity_at_trade | REAL | NULL permitted | Account equity at the moment of execution, from live MT5 query |

**New field on existing `signals` table:** No schema changes — the `outcome` field (WIN/LOSS/PENDING) introduced in Phase 1 is the mechanism for manual tracking that feeds the signal validation gate.

**In-memory state (not persisted as a separate table):**

| State | Type | Description |
|-------|------|-------------|
| daily_drawdown_pct | REAL | Cumulative realised loss today as a percentage of starting-day equity; re-derived from execution log on start-up |
| daily_drawdown_halted | BOOLEAN | Whether execution is halted today due to drawdown; derived from daily_drawdown_pct vs. config |

### 5.2 Data Flows

**Flow 1: VALID TRADE → Order Placement**
- Trigger: APScheduler H1 cycle completes strategy evaluation and produces one or more VALID TRADE results
- Source: `signals` table record just written by the debate engine
- Transformation: Gate checks run; if all pass, lot size calculated; MT5 order request constructed
- Destination: MT5 terminal receives order request; execution record written to `executions` table; Telegram notification sent
- Unavailability: If any gate check fails, a blocked execution record is written to `executions`; the original signal record in `signals` is unchanged

**Flow 2: H1 Cycle → Position Management**
- Trigger: Same APScheduler H1 cycle, after new signal evaluation completes
- Source: Live MT5 position query for all open USDJPY positions placed by the system
- Transformation: Each open position checked against its originating strategy's management rules (TP1 hit, trailing stop, time stop, invalidation)
- Destination: MT5 receives modify or close requests where conditions are met; execution records written for each action; Telegram notifications sent for each action
- Unavailability: If MT5 is unreachable, no management actions are attempted; disconnected state is logged

**Flow 3: Daily Drawdown Reset**
- Trigger: System clock reaching 00:00 UTC
- Source: Current daily_drawdown_halted and daily_drawdown_pct state
- Transformation: Reset daily_drawdown_pct to 0.0 and daily_drawdown_halted to false
- Destination: In-memory state updated; new orders are eligible from this point

**Flow 4: Dashboard Automation Panel → API**
- Trigger: Frontend polling cycle every 60 seconds
- Source: `config.py` (automation status, risk parameters), live MT5 position query, `executions` table (today's log)
- Transformation: Data aggregated by the automation status endpoint
- Destination: JSON response to browser; rendered in automation status panel

### 5.3 Interface Contracts

**MT5 Python API — Order Operations**
- Interface: `MetaTrader5` Python package
- Direction: Bidirectional (query positions/account; send order requests)
- Data format: MT5 Python package native types (`TradeRequest`, `TradeResult`, `PositionInfo`, `OrderInfo`, account info struct)
- Frequency: On each VALID TRADE gate evaluation; on each H1 position management scan; on toggle of automation status (position query only)
- Error conditions: MT5 returns a non-zero `retcode` on failure; the system logs the code and message and does not retry

**SQLite `executions` table**
- Interface: `signal_store.py` (all reads and writes)
- Direction: Bidirectional
- Data format: Python dict matching the `executions` schema above
- Frequency: Written once per execution event; read on dashboard polling and on start-up for drawdown reconstitution
- Error conditions: SQLite write failure raises an exception, which is caught, logged, and does not block the MT5 action from being reported

**Telegram Bot API — Execution Notifications**
- Interface: `python-telegram-bot` library
- Direction: Outbound only
- Data format: Plain text message with `[USDJPY Smart Agent]` prefix; one message per execution event type
- Frequency: Asynchronous, triggered by each execution event
- Error conditions: Telegram send failures are logged but do not block the execution action or prevent the execution record from being written

---

## 6. Interface Specifications

### 6.1 Internal API Contracts

**GET /api/automation/status**

Returns the full automation state, configuration, and signal validation gate progress.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| (none) | — | — | No parameters |

Response schema:

| Field | Type | Description |
|-------|------|-------------|
| automation_enabled | boolean | Current value of AUTOMATION_ENABLED |
| strategies_enabled | array[integer] | Strategy IDs in STRATEGIES_ENABLED_FOR_AUTO |
| config.max_risk_pct | number | Configured maximum risk percentage per trade |
| config.max_concurrent_positions | integer | Configured maximum concurrent positions |
| config.max_daily_drawdown_pct | number | Configured daily drawdown limit |
| config.max_spread_pips | number | Configured maximum spread |
| config.max_lot_size | number | Configured maximum lot size |
| daily_drawdown_pct | number | Current cumulative daily drawdown percentage |
| daily_drawdown_halted | boolean | Whether execution is halted today due to drawdown |
| gate.days_elapsed | integer | Calendar days since first signal |
| gate.days_required | integer | 60 |
| gate.valid_signals_count | integer | Count of VALID TRADE signals in history |
| gate.valid_signals_required | integer | 50 |
| gate.resolved_signals_count | integer | Count of signals with WIN or LOSS outcome |
| gate.resolved_signals_required | integer | 30 |
| gate.all_passed | boolean | True only if all four gate conditions are met |

Error response: `{ "success": false, "data": null, "error": "MT5 unavailable" }` with HTTP 503 if MT5 is unreachable.

Example response:
```json
{
  "success": true,
  "data": {
    "automation_enabled": false,
    "strategies_enabled": [1],
    "config": {
      "max_risk_pct": 0.5,
      "max_concurrent_positions": 2,
      "max_daily_drawdown_pct": 3.0,
      "max_spread_pips": 2.5,
      "max_lot_size": 1.0
    },
    "daily_drawdown_pct": 0.0,
    "daily_drawdown_halted": false,
    "gate": {
      "days_elapsed": 45,
      "days_required": 60,
      "valid_signals_count": 38,
      "valid_signals_required": 50,
      "resolved_signals_count": 22,
      "resolved_signals_required": 30,
      "all_passed": false
    }
  },
  "error": null
}
```

---

**POST /api/automation/toggle**

Toggles the AUTOMATION_ENABLED state. Only accessible from localhost.

Request body: none required.

Response schema:

| Field | Type | Description |
|-------|------|-------------|
| automation_enabled | boolean | The new state after toggle |
| gate_passed | boolean | Whether the signal validation gate was passed before enabling |

Error responses:
- HTTP 403 if request originates from a non-localhost address
- HTTP 400 `{ "success": false, "data": null, "error": "Signal validation gate not passed" }` if gate has not been passed and the toggle would enable automation

---

**GET /api/automation/positions**

Returns all currently open USDJPY positions placed by the system.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| (none) | — | — | No parameters |

Response schema (array of position objects):

| Field | Type | Description |
|-------|------|-------------|
| ticket | integer | MT5 ticket number |
| strategy_id | integer | Strategy that generated the originating signal |
| strategy_name | string | Human-readable strategy name |
| direction | string | BUY or SELL |
| lot_size | number | Current lot size |
| open_price | number | Actual fill price |
| current_sl | number | Current stop loss on the MT5 position |
| current_tp | number | Current take profit on the MT5 position |
| unrealised_pnl | number | Unrealised P&L in account currency |
| open_time | string | UTC ISO-8601 datetime when position was opened |

Error response: `{ "success": false, "data": null, "error": "MT5 unavailable" }` with HTTP 503 if MT5 is unreachable.

---

**GET /api/automation/executions**

Returns the execution log for the current calendar day, paginated.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| page | integer | Optional (default 1) | Page number |
| page_size | integer | Optional (default 50) | Records per page |

Response schema:

| Field | Type | Description |
|-------|------|-------------|
| executions | array | List of execution records (fields match `executions` table columns) |
| total | integer | Total records for today |
| page | integer | Current page |
| page_size | integer | Records per page |

---

### 6.2 External System Interfaces

**MetaTrader 5 Python Package**
- System name: MetaTrader 5 Python Integration, version 5.0.45+
- Authentication: Session-based; MT5 terminal must be running and authenticated independently — the Python package connects to the already-open terminal, no credentials are passed programmatically
- Key operations used: `mt5.order_send()` for placing/modifying/closing orders; `mt5.positions_get()` for querying open positions; `mt5.orders_get()` for pending orders; `mt5.account_info()` for live equity; `mt5.symbol_info()` for pip value; `mt5.initialize()` and `mt5.shutdown()` for connection lifecycle
- Rate limits: No documented API rate limit; operations are local IPC to the MT5 terminal process — no throttling required
- Fallback: If `mt5.initialize()` fails, all execution is blocked; if `mt5.order_send()` returns a non-zero retcode, the failure is logged and not retried

**Telegram Bot API**
- System name: Telegram Bot API (via `python-telegram-bot` library)
- Authentication: Bot token stored in the `TELEGRAM_TOKEN` environment variable; chat ID stored in `TELEGRAM_CHAT_ID` environment variable — both already configured in Phase 4
- Key operations used: `bot.send_message()` — all communication is outbound message delivery
- Rate limits: Telegram enforces a per-bot rate limit of 30 messages per second; the system sends at most one notification per execution event, which is well within this limit
- Fallback: Failed Telegram sends are logged but do not affect execution logic; the execution record is still written to the database

### 6.3 User Interface Specifications

**Automation Status Panel — Dashboard (`index.html`)**

This is a new section appended to the existing dashboard page below the active signals panel.

- Purpose: Give the user a single-glance view of automation state and the ability to enable/disable it safely.
- Layout: Full-width panel with a header row containing the status badge and toggle button; below that, three sub-sections side by side: strategies enabled, open positions, and today's execution log.

**Status Header Row:**
- Displays "AUTOMATION" label
- Status badge: solid green "ENABLED" or solid grey "DISABLED"
- Toggle button: labelled "Enable" when disabled, "Disable" when enabled
- On toggle button click: a confirmation dialog appears with the text "Are you sure you want to [enable/disable] automated trading?" and two buttons: "Confirm" and "Cancel". No state change occurs unless "Confirm" is clicked.

**Strategies Enabled Sub-section:**
- Heading: "Strategies Enabled for Auto"
- Lists strategy names from STRATEGIES_ENABLED_FOR_AUTO; if the list is empty, displays "None configured"
- Data source: `GET /api/automation/status`

**Open Positions Sub-section:**
- Heading: "Open Positions"
- Table with columns: Strategy, Direction, Lots, Entry, SL, TP, P&L
- If no open positions: displays "No open positions"
- P&L displayed in account currency, positive values in green, negative in red
- Data source: `GET /api/automation/positions`

**Today's Execution Log Sub-section:**
- Heading: "Today's Executions"
- Table with columns: Time (UTC), Strategy, Event Type, Direction, Lots, Result/Reason
- Event type displayed with colour coding: ORDER_PLACED (green), ORDER_CLOSED (blue), ORDER_MODIFIED (amber), ORDER_BLOCKED (red)
- If no events today: displays "No executions today"
- Data source: `GET /api/automation/executions`

**Loading state:** Each sub-section displays a "Loading..." placeholder while the API call is in flight.

**Error state:** If an API call fails, the sub-section displays "Data unavailable" in red text.

**Refresh behaviour:** All three sub-sections refresh on the same 60-second polling interval as the rest of the dashboard.

---

## 7. Constraints

- **Platform:** Windows 10 and Windows 11 only. The MetaTrader 5 Python package is a Windows-only library and the MT5 terminal is a Windows-only application. Phase 5 cannot be ported to macOS or Linux.
- **Language:** Python 3.11 or later. No other language may be introduced.
- **MT5 dependency:** The MT5 terminal must be locally installed, running, and authenticated with a valid trading account before the execution layer can function. The system cannot open or authenticate MT5 itself.
- **AUTOMATION_ENABLED defaults to false:** This is a non-negotiable default. The flag must never be set to true in any committed configuration file, environment default, or start-up routine.
- **No credentials stored:** MT5 account credentials (login number, password, server name) must never be stored in any file, environment variable, or database in this project.
- **No JavaScript frameworks:** The automation panel is added to the existing dashboard using the same vanilla HTML/CSS/JS approach already established in Phase 3. No additional frontend libraries or build tools may be introduced.
- **Single writer to SQLite:** The existing system design enforces single-writer access to the SQLite database. All execution log writes must go through `signal_store.py` and no direct SQLite writes are permitted from execution modules.
- **No external paid services:** No new paid third-party APIs or services may be introduced in this phase.
- **Max 2 concurrent positions:** This is a hard limit built into the execution gate, not a soft guideline. It cannot be overridden by configuration alone — the check is enforced in code.
- **Physical SL and TP on every order:** Every order sent to MT5 must include hard SL and TP fields set on the order itself. Relying solely on Python-side monitoring for position protection is prohibited.

---

## 8. Assumptions

It is assumed that the MT5 terminal has been authorised by the account holder for algorithmic trading. If this is incorrect, MT5 will reject order placement requests and the execution layer cannot function.

It is assumed that the prop firm account in use permits automated algorithmic trading. If this is incorrect, the account may be in violation of firm rules, which must be resolved before Phase 5 is activated.

It is assumed that USDJPY pip value is denominated in JPY per lot (USDJPY is a JPY-quoted pair where the second currency is JPY). If the account is denominated in USD, pip value conversion logic must account for the cross rate. If the account base currency is not JPY, the pip value calculation must use the current USDJPY rate to convert JPY pips to account currency.

It is assumed that the `signals` table `outcome` field is being populated manually with WIN or LOSS by the user during the Phase 4 live-monitoring period. If this has not been done, the signal validation gate conditions requiring 30 resolved outcomes cannot be met, and the gate status report will reflect this.

It is assumed that the economic calendar data fetched by Phase 1/4 is accurate and current (less than 6 hours old) during trading hours. If calendar data is consistently stale, the news-proximity gate check will block all executions.

It is assumed that the Telegram bot token and chat ID configured in Phase 4 remain valid for Phase 5. If the bot is deactivated or the chat ID changes, Telegram notifications will fail silently (logged, not blocking).

It is assumed that a single-lot USDJPY trade on the target account is within the minimum and maximum volume constraints enforced by the broker. If the broker minimum is above 0.01 lots, the lot-size floor check must be updated to use the broker's minimum.

---

## 9. Risks and Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|----|------|------------|--------|------------|
| RISK-5-01 | MT5 terminal closes unexpectedly while positions are open, leaving positions unmanaged by the system | Medium | High | Every order placed must have hard SL and TP set on the MT5 order itself; positions remain protected at the broker level even if the Python backend is offline |
| RISK-5-02 | Python backend crashes while positions are open, preventing the trade manager from running its H1 scan | Medium | High | MT5-native SL and TP provide last-line-of-defence protection; Telegram notification on backend start-up will alert the user to check open positions manually |
| RISK-5-03 | Significant slippage on USDJPY market orders during high-impact news events causes fill prices materially worse than the signal's entry price | High | Medium | The news-proximity gate check blocks execution within 30 minutes of scheduled high-impact events; the max spread check at execution time provides a secondary filter |
| RISK-5-04 | A carry unwind event (e.g., August 2024 style rapid JPY strengthening) invalidates all open long positions simultaneously beyond SL levels | Low | High | Small position sizing (0.5% risk per trade maximum) and a hard 2-position cap limit total exposure; these controls cannot prevent gap-downs past SL but limit the loss |
| RISK-5-05 | Multiple trend-following strategies simultaneously produce VALID TRADE verdicts in the same direction, resulting in correlated positions exceeding intended risk | Medium | Medium | The 2-position cap enforces a hard ceiling; strategies must be added to STRATEGIES_ENABLED_FOR_AUTO one at a time to observe correlation behaviour before enabling more |
| RISK-5-06 | The daily drawdown tracking accumulator is lost on system restart and is not correctly reconstituted from the execution log, allowing trading beyond the daily limit after a restart | Low | High | The accumulator reconstitution logic must query the execution log on every start-up for closed positions from the current calendar day; this must be a tested requirement |
| RISK-5-07 | A misconfigured risk percentage or max lot size produces oversized positions | Low | High | All risk parameters are in `config.py` with their defaults set conservatively (0.5% risk, 1.0 max lots); position sizing calculations must include a pre-placement sanity check that the monetary risk is within expected bounds |
| RISK-5-08 | The signal re-validation check at execution time is too permissive and does not catch conditions that have genuinely changed since the signal was generated | Medium | Medium | The re-validation must use fresh data, not cached values from the evaluation cycle; if fresh data is unavailable, execution must be blocked rather than proceeding on stale data |
| RISK-5-09 | The prop firm account hits a daily loss limit imposed by the firm that is stricter than the system's configured drawdown limit | Low | High | The user must configure MAX_DAILY_DRAWDOWN_PCT to be below the prop firm's rule; this must be verified before Phase 5 is activated on a live prop account |

---

## 10. Acceptance Criteria

| ID | Criterion |
|----|-----------|
| AC-5-01 | With AUTOMATION_ENABLED set to false, no order is placed in MT5 regardless of signal verdicts produced during the evaluation cycle |
| AC-5-02 | With AUTOMATION_ENABLED set to true and STRATEGIES_ENABLED_FOR_AUTO set to an empty list, no order is placed in MT5 regardless of signal verdicts produced |
| AC-5-03 | With AUTOMATION_ENABLED true and strategy 1 in STRATEGIES_ENABLED_FOR_AUTO, a VALID TRADE verdict from strategy 1 that passes all gate checks results in an MT5 order with the entry, SL, and TP1 values from the signal |
| AC-5-04 | The lot size on any placed order equals `floor((equity × risk_pct) / (sl_pips × pip_value) / 0.01) × 0.01` where equity is the live MT5 account equity at execution time, rounded down to 0.01 lots |
| AC-5-05 | When two USDJPY positions are already open, a third VALID TRADE signal that passes all other gate checks is blocked with reason MAX_POSITIONS_REACHED, and a blocked execution record is written to the database |
| AC-5-06 | When the live spread at execution time exceeds MAX_SPREAD_PIPS, the order is blocked with reason SPREAD_EXCEEDED and logged to the executions table |
| AC-5-07 | When cumulative daily realised losses reach MAX_DAILY_DRAWDOWN_PCT of starting-day equity, all subsequent order placement attempts are blocked for the remainder of that calendar day with reason DAILY_DRAWDOWN_LIMIT |
| AC-5-08 | When a high-impact economic event is scheduled within 30 minutes of execution time, the order is blocked with reason NEWS_PROXIMITY and logged |
| AC-5-09 | When AUTOMATION_ENABLED is set to true while the signal validation gate has not been fully passed, the toggle is rejected and AUTOMATION_ENABLED remains false |
| AC-5-10 | When a placed market order's TP1 is subsequently hit, a partial close order is sent to MT5 for the strategy-defined percentage of the position, and the remaining portion of the position stays open |
| AC-5-11 | Every order placed by the system has a non-zero hard SL and a non-zero hard TP1 set on the MT5 order itself, verified by querying the position/order record from MT5 after placement |
| AC-5-12 | Every execution event (ORDER_PLACED, ORDER_MODIFIED, ORDER_CLOSED, ORDER_BLOCKED) produces a record in the `executions` table with all mandatory fields populated before the next evaluation cycle runs |
| AC-5-13 | A Telegram notification is sent for each execution event type: order placed, order blocked, order modified, order closed, and daily drawdown limit reached |
| AC-5-14 | The dashboard displays the current automation status (ENABLED/DISABLED), the list of strategies enabled, the open positions list, and today's execution log within one 60-second polling cycle |
| AC-5-15 | Clicking the automation toggle on the dashboard presents a confirmation dialog; dismissing without confirming leaves automation status unchanged |
| AC-5-16 | At 00:00 UTC the following day after a daily drawdown halt, new order placement is no longer blocked and the daily drawdown accumulator reads 0.0% |
| AC-5-17 | After a backend restart during a calendar day where losses have already been incurred, the daily drawdown accumulator correctly reflects those losses (re-derived from the execution log), and the drawdown halt state is correctly restored if the limit was already reached |
| AC-5-18 | When MT5 returns an error code on an order placement attempt, the error is logged to the executions table, a Telegram notification is sent, and the evaluation cycle continues without crashing |
| AC-5-19 | The `GET /api/automation/status` endpoint returns the automation status, strategies enabled, all risk config values, current daily drawdown, and signal validation gate progress in the standard response envelope |
| AC-5-20 | The `GET /api/automation/positions` endpoint returns all currently open USDJPY positions with ticket, direction, lot size, open price, current SL, current TP, and unrealised P&L |

---

## 11. Traceability Matrix

| Acceptance Criterion | Functional Requirement(s) |
|----------------------|---------------------------|
| AC-5-01 | FR-5-06, FR-5-13 |
| AC-5-02 | FR-5-07, FR-5-14 |
| AC-5-03 | FR-5-24, FR-5-26, FR-5-27 |
| AC-5-04 | FR-5-31, FR-5-32, FR-5-33 |
| AC-5-05 | FR-5-18, FR-5-22 |
| AC-5-06 | FR-5-16, FR-5-22 |
| AC-5-07 | FR-5-17, FR-5-47, FR-5-48 |
| AC-5-08 | FR-5-19, FR-5-22 |
| AC-5-09 | FR-5-01, FR-5-02, FR-5-03, FR-5-04 |
| AC-5-10 | FR-5-37 |
| AC-5-11 | FR-5-26, FR-5-27 |
| AC-5-12 | FR-5-51, FR-5-52, FR-5-53, FR-5-54, FR-5-55 |
| AC-5-13 | FR-5-23, FR-5-30, FR-5-45, FR-5-46, FR-5-49 |
| AC-5-14 | FR-5-56, FR-5-57, FR-5-58, FR-5-59, FR-5-62 |
| AC-5-15 | FR-5-60, FR-5-61 |
| AC-5-16 | FR-5-50 |
| AC-5-17 | FR-5-47, FR-5-50 |
| AC-5-18 | FR-5-28, FR-5-29 |
| AC-5-19 | FR-5-63, FR-5-67 |
| AC-5-20 | FR-5-65, FR-5-67 |

---

## 12. Open Questions

| ID | Question | Impact if Unresolved | Owner |
|----|----------|----------------------|-------|
| OQ-5-01 | Does the prop firm account permit fully automated algorithmic trading, or are there restrictions on execution frequency, hold time, or order type? | If automated trading is restricted, Phase 5 cannot be activated on the live account and must remain on a demo account indefinitely | User (account holder) |
| OQ-5-02 | What is the prop firm's daily loss limit, and is it stricter than the system's 3.0% MAX_DAILY_DRAWDOWN_PCT default? | If the prop firm limit is lower, the default must be changed before going live to avoid rule violations | User (account holder) |
| OQ-5-03 | For strategies that specify a TP1 partial close, what percentage of the position should be closed at TP1? The strategy reference defines TP1 hit logic but does not universally specify the partial close percentage for all 20 strategies. | Without a defined percentage, the partial close in FR-5-37 cannot be implemented; a default must be agreed or each strategy must be reviewed | User / USDJPY_Algo_Strategy_Reference.md |
| OQ-5-04 | Should the trailing stop and time-stop management logic run only on positions opened by the system in the current session, or should it also apply to positions the system opened in a previous session (surviving a backend restart)? | If positions from previous sessions are excluded, they will be unmanaged after restart; if included, the system needs to re-associate open positions with their originating signals correctly on start-up | User |
| OQ-5-05 | Should the automation toggle endpoint be accessible via the dashboard frontend (localhost), or should it require a separate manual config file edit to prevent accidental toggles? | A UI toggle is more convenient but carries the risk of accidental clicks; a config-file-only toggle is safer but less ergonomic | User |

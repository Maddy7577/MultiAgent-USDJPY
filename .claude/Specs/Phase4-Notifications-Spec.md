# Phase 4 — Notifications Specification

---

## Document Control

| Field        | Value                          |
|--------------|-------------------------------|
| Document ID  | SPEC-PHASE-4-v1.0              |
| Version      | v1.0                           |
| Status       | Draft                          |
| Created      | 2026-04-24                     |
| Author       | USDJPY Smart Agent Project     |
| Phase        | 4 of 5                         |
| Phase Name   | Notifications                  |

### Change History

| Version | Date       | Author | Summary of Changes |
|---------|------------|--------|--------------------|
| v1.0    | 2026-04-24 | —      | Initial draft      |

---

## 1. Introduction

### 1.1 Purpose
This document specifies the functional and non-functional requirements for Phase 4 of the USDJPY Smart Agent system. Phase 4 adds Telegram alert delivery for VALID TRADE signals and a persistent, queryable signal history layer with a dedicated frontend page. This document is intended for the developer implementing Phase 4 and serves as the authoritative source of truth for what the system must do when this phase is complete.

### 1.2 Scope
This specification covers Telegram bot integration (message composition, delivery, retry, and failure handling), completion of the signal history write path to SQLite, three new REST API endpoints for history query and outcome update, a new `history.html` frontend page with filtering and inline editing, and a navigation update across all existing pages. It does not cover strategy evaluation logic, the debate engine, any frontend changes to `index.html`, `strategies.html`, or `detail.html` beyond navigation bar addition, MT5 order execution, or any change to the existing API endpoints introduced in Phases 1–3.

### 1.3 Definitions and Abbreviations

| Term / Abbreviation | Definition |
|---|---|
| MT5 | MetaTrader 5 — the trading terminal providing OHLCV price data |
| OHLCV | Open, High, Low, Close, Volume — standard candlestick data fields |
| ATR | Average True Range — a volatility indicator |
| EMA | Exponential Moving Average |
| FRED | Federal Reserve Economic Data — macroeconomic data API from the St. Louis Fed |
| VALID TRADE | A strategy verdict indicating a high-confidence, rule-compliant trade setup with full parameters |
| WAIT FOR LEVELS | A strategy verdict indicating a valid setup in principle where price has not yet reached the ideal entry zone |
| NO TRADE | A strategy verdict indicating conditions are not met or opposing factors are too strong |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| SL | Stop Loss — the price level at which a trade is closed to limit loss |
| TP | Take Profit — the price level at which a trade is closed to realise a gain |
| TP1 / TP2 / TP3 | Take Profit 1, 2, and 3 — tiered exit targets |
| RRR | Risk-Reward Ratio — the ratio of potential profit to potential loss |
| PENDING | Outcome state for a VALID or WAIT signal that has not yet been resolved as WIN or LOSS |
| N/A | Not Applicable — outcome state assigned to NO TRADE signals |
| Transition | The event where a strategy's verdict changes from a non-VALID state to VALID_TRADE |
| Evaluation Cycle | One full pass of all 20 strategies executed by the scheduler on H1 candle close |
| Deduplication | Logic that prevents writing an identical signal row within a defined time window |
| python-telegram-bot | The Python library used to send messages via the Telegram Bot API |
| APScheduler | The Python scheduling library that triggers evaluation cycles on candle close |
| UTC | Coordinated Universal Time — all timestamps in this system are UTC |
| iCal | iCalendar format used to retrieve the Forex Factory economic calendar |
| DXY | US Dollar Index |
| VIX | CBOE Volatility Index |

### 1.4 References

- USDJPY Smart Agent System Architecture — `.claude/Documents/system_architecture.md`
- Phase 4 Build Guide — `.claude/Documents/04-Phase4-Notifications.md`
- Telegram Bot API documentation — https://core.telegram.org/bots/api
- python-telegram-bot library documentation — https://python-telegram-bot.org

---

## 2. System Context

### 2.1 Phase Position in System
Phase 4 is the fourth of five phases. It depends on Phase 1 (data pipeline, SQLite schema, FastAPI skeleton), Phase 2 (strategy engine and debate verdicts), and Phase 3 (frontend structure and navigation). Phase 5 (Automated Trading — MT5 order execution) depends on Phase 4 being complete and stable, as automated trading requires a reliable, validated signal history to confirm system performance before order placement is enabled.

### 2.2 Phase Goal
Phase 4 must deliver real-time Telegram alerts for every new VALID TRADE verdict and a fully queryable, outcome-trackable signal history accessible from both the API and the frontend.

### 2.3 In Scope for This Phase
- Telegram bot message composition, delivery, retry logic, and failure handling
- Detection of the VALID TRADE transition (new VALID, not repeated VALID)
- Caching of last-cycle verdicts in memory by the scheduler for transition detection
- Completion of the signal history write path: every evaluation result written to SQLite
- Deduplication of identical strategy results within a 4-hour window
- Addition of a `telegram_failed` field to the `signals` table
- `GET /api/history` endpoint with pagination and filtering
- `GET /api/history/{id}` endpoint for single signal detail
- `PATCH /api/history/{id}/outcome` endpoint for outcome update
- `history.html` frontend page with filter row, data table, inline outcome editing, and summary stats bar
- Addition of a "History" navigation link across all four pages

### 2.4 Out of Scope for This Phase
- Any modification to strategy evaluation logic, agent scoring, or the debate engine
- Changes to existing API endpoints (`/api/dashboard`, `/api/strategies`, `/api/strategy/{id}`, `/api/status`)
- Changes to `index.html`, `strategies.html`, or `detail.html` beyond adding the History navigation link
- Bulk outcome update (updating multiple signals at once)
- Export of signal history to CSV or any external format
- Email, SMS, Discord, or any notification channel other than Telegram
- Notification preferences, mute windows, or user-configurable alert settings
- Trade performance analytics beyond win rate and average confidence
- MT5 order execution (Phase 5)
- User authentication or access control of any kind

### 2.5 Predecessor Dependencies
The following must be complete and working before Phase 4 implementation begins:

- SQLite database file exists at `data/usdjpy_signals.db` with the `signals` and `market_context` tables created per the Phase 1 schema
- `signal_store.py` read/write module is functional
- The 20-strategy evaluation cycle runs on H1 candle close and produces `StrategyResult` objects with all required fields populated
- FastAPI server starts cleanly and serves existing endpoints
- `frontend/index.html`, `strategies.html`, and `detail.html` are functional with an existing navigation bar structure
- A valid Telegram bot token and chat ID are available in the project's `.env` file

---

## 3. Functional Requirements

### 3.1 Telegram Alert Delivery

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-01 | The system SHALL send a Telegram message when a strategy transitions to VALID_TRADE status | MUST | Given a strategy that was not VALID_TRADE in the previous evaluation cycle, when the current cycle produces a VALID_TRADE verdict, then a Telegram message is sent within 30 seconds of the evaluation completing |
| FR-4-02 | The system SHALL NOT send a Telegram message for strategies with a WAIT_FOR_LEVELS verdict | MUST | Given a strategy producing WAIT_FOR_LEVELS, when the evaluation cycle completes, then no Telegram message is sent for that strategy |
| FR-4-03 | The system SHALL NOT send a Telegram message for strategies with a NO_TRADE verdict | MUST | Given a strategy producing NO_TRADE, when the evaluation cycle completes, then no Telegram message is sent for that strategy |
| FR-4-04 | The system SHALL NOT re-send a Telegram message if the same strategy remains VALID_TRADE in the next evaluation cycle | MUST | Given a strategy that was VALID_TRADE in cycle N, when cycle N+1 also produces VALID_TRADE for that same strategy, then no new Telegram message is sent |
| FR-4-05 | The system SHALL send one Telegram message per strategy when multiple strategies become VALID_TRADE in the same evaluation cycle | MUST | Given three strategies all transitioning to VALID_TRADE in the same cycle, when the cycle completes, then exactly three separate Telegram messages are sent |
| FR-4-06 | The system SHALL prefix every Telegram message with `[USDJPY Smart Agent]` | MUST | Given any sent Telegram message, when inspected, then the message text begins with the literal string `[USDJPY Smart Agent]` |
| FR-4-07 | The system SHALL include the strategy name and strategy number in the Telegram message | MUST | Given a VALID_TRADE alert for Strategy 1, when the message is received, then it contains "Multi-Timeframe Trend Alignment (#1)" or equivalent name-and-number format |
| FR-4-08 | The system SHALL include the trade direction in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the direction field shows either BUY or SELL |
| FR-4-09 | The system SHALL include the entry price in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the entry price is present and matches the value stored in the signal record |
| FR-4-10 | The system SHALL include the stop loss price and pip distance in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the SL price and the pip distance from entry are both present |
| FR-4-11 | The system SHALL include TP1 and TP2 prices and their pip distances in the Telegram message | MUST | Given a VALID_TRADE alert with TP1 and TP2 populated, when the message is received, then both targets with pip distances are present |
| FR-4-12 | The system SHALL include the risk-reward ratio in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the RRR field is present in 1:N format |
| FR-4-13 | The system SHALL include the confidence score in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the confidence score is present as a value out of 100 |
| FR-4-14 | The system SHALL include the timeframes used in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the timeframes field lists the relevant timeframes (e.g., H1 / H4 / D) |
| FR-4-15 | The system SHALL include a brief summary of supporting reasons in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the Why field contains at least one reason drawn from the strategy's reasons_for list |
| FR-4-16 | The system SHALL include a brief summary of opposing reasons in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the Against field contains at least one reason drawn from the strategy's reasons_against list |
| FR-4-17 | The system SHALL include the evaluation timestamp (UTC) in the Telegram message | MUST | Given a VALID_TRADE alert, when the message is received, then the Evaluated field shows the UTC time at which the evaluation cycle ran |
| FR-4-18 | The system SHALL read the Telegram bot token from an environment variable | MUST | Given the application starting with no hardcoded Telegram token, when `TELEGRAM_TOKEN` environment variable is set, then the bot connects successfully |
| FR-4-19 | The system SHALL read the Telegram chat ID from an environment variable | MUST | Given the application starting with no hardcoded chat ID, when `TELEGRAM_CHAT_ID` environment variable is set, then messages are delivered to the correct chat |

### 3.2 Telegram Error Handling

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-20 | The system SHALL retry a failed Telegram send exactly once after a 30-second delay | MUST | Given a Telegram send that fails on the first attempt, when 30 seconds have elapsed, then exactly one retry attempt is made |
| FR-4-21 | The system SHALL log an error when a Telegram send fails on both the initial attempt and the retry | MUST | Given a Telegram send that fails on both attempts, when the retry is exhausted, then an error entry is written to the application log |
| FR-4-22 | The system SHALL set a `telegram_failed` flag on the corresponding signal record when both send attempts fail | MUST | Given a Telegram send that fails on both attempts, when the retry is exhausted, then the signal record in SQLite has `telegram_failed = TRUE` |
| FR-4-23 | The system SHALL NOT halt or crash the evaluation cycle when a Telegram send fails | MUST | Given a Telegram send failure during an evaluation cycle, when the failure is handled, then subsequent strategies in the same cycle continue to be evaluated and stored normally |

### 3.3 Transition Detection

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-24 | The scheduler SHALL maintain an in-memory cache of the most recent verdict for each of the 20 strategies | MUST | Given a completed evaluation cycle, when the next cycle begins, then the system has access to all 20 previous verdicts for comparison |
| FR-4-25 | The system SHALL define a transition as a strategy's verdict changing from any non-VALID_TRADE state to VALID_TRADE | MUST | Given a strategy that was NO_TRADE in cycle N, when it becomes VALID_TRADE in cycle N+1, then the system identifies this as a transition and sends a Telegram alert |
| FR-4-26 | The system SHALL treat the first evaluation cycle after startup as a transition baseline and SHALL NOT send Telegram alerts for strategies that are VALID_TRADE on the very first evaluation cycle after server start | SHOULD | Given the server starting and the first evaluation cycle running, when one or more strategies produce VALID_TRADE, then no Telegram message is sent (the first cycle populates the baseline cache only) |

### 3.4 Signal History Write Path

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-27 | The system SHALL write every strategy result to the `signals` table after each evaluation cycle, regardless of verdict | MUST | Given a completed evaluation cycle producing 20 results, when all writes are complete, then 20 records (or fewer if deduplication applies) are present in the signals table for that cycle |
| FR-4-28 | The system SHALL set the `outcome` field to `PENDING` for all VALID_TRADE and WAIT_FOR_LEVELS signal records | MUST | Given a VALID_TRADE or WAIT_FOR_LEVELS result written to SQLite, when the row is inspected, then the outcome column contains the value `PENDING` |
| FR-4-29 | The system SHALL set the `outcome` field to `N/A` for all NO_TRADE signal records | MUST | Given a NO_TRADE result written to SQLite, when the row is inspected, then the outcome column contains the value `N/A` |
| FR-4-30 | The system SHALL add a `telegram_failed` boolean column to the `signals` table | MUST | Given the Phase 4 database migration running, when the signals table is inspected, then a `telegram_failed` column of boolean type is present with a default value of FALSE |

### 3.5 Signal Deduplication

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-31 | The system SHALL NOT write a new signal row if the same strategy produced the same verdict with the same entry price and the same SL price within the preceding 4-hour window | MUST | Given strategy S1 producing NO_TRADE with a fixed entry/SL, when evaluated again within 4 hours with an identical result, then no new row is inserted |
| FR-4-32 | The system SHALL update the `timestamp` field of the existing signal record when deduplication suppresses a new row | MUST | Given deduplication matching an existing record, when the duplicate write is suppressed, then the existing record's `timestamp` is updated to the current evaluation time |
| FR-4-33 | The system SHALL always write a new row when the verdict changes, even if within the 4-hour window | MUST | Given a strategy that was NO_TRADE and transitions to VALID_TRADE within 4 hours, when the new result is processed, then a new row is inserted rather than updating the existing NO_TRADE record |

### 3.6 Signal History API

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-34 | The system SHALL expose a `GET /api/history` endpoint that returns a paginated list of signal records ordered by timestamp descending | MUST | Given a request to `GET /api/history`, when the response is received, then signals are returned in descending timestamp order in the standard `{ success, data, error }` envelope |
| FR-4-35 | `GET /api/history` SHALL accept a `page` query parameter (integer, default 1) | MUST | Given `GET /api/history?page=2`, when the response is received, then the second page of results is returned |
| FR-4-36 | `GET /api/history` SHALL accept a `per_page` query parameter (integer, default 50, maximum 200) | MUST | Given `GET /api/history?per_page=25`, when the response is received, then at most 25 records are returned |
| FR-4-37 | `GET /api/history` SHALL accept a `status` query parameter to filter by verdict (VALID_TRADE, WAIT_FOR_LEVELS, NO_TRADE) | MUST | Given `GET /api/history?status=VALID_TRADE`, when the response is received, then only VALID_TRADE records are returned |
| FR-4-38 | `GET /api/history` SHALL accept a `strategy_id` query parameter (integer 1–20) to filter results to a single strategy | MUST | Given `GET /api/history?strategy_id=3`, when the response is received, then only records for strategy 3 are returned |
| FR-4-39 | The `GET /api/history` response SHALL include pagination metadata: total record count, current page, per_page value, and total pages | MUST | Given `GET /api/history`, when the response is received, then the data object contains `total`, `page`, `per_page`, and `total_pages` fields |
| FR-4-40 | The system SHALL expose a `GET /api/history/{id}` endpoint that returns the full detail of a single signal record | MUST | Given `GET /api/history/42`, when the record with id=42 exists, then all columns of that record are returned in the response |
| FR-4-41 | `GET /api/history/{id}` SHALL return a 404 status with an appropriate error message when the requested signal ID does not exist | MUST | Given `GET /api/history/99999` where no such record exists, when the response is received, then the HTTP status is 404 and the error field is populated |
| FR-4-42 | The system SHALL expose a `PATCH /api/history/{id}/outcome` endpoint that updates the `outcome` field of a signal record | MUST | Given `PATCH /api/history/42/outcome` with body `{ "outcome": "WIN" }`, when the request is processed, then the signal record's outcome field is updated to `WIN` |
| FR-4-43 | `PATCH /api/history/{id}/outcome` SHALL only accept the values `WIN`, `LOSS`, or `N/A` | MUST | Given a PATCH request with `{ "outcome": "MAYBE" }`, when the request is processed, then a 422 Unprocessable Entity response is returned |
| FR-4-44 | `PATCH /api/history/{id}/outcome` SHALL return a 404 status when the requested signal ID does not exist | MUST | Given a PATCH request for a non-existent ID, when the request is processed, then the HTTP status is 404 |

### 3.7 History Frontend Page

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-45 | The system SHALL provide a `history.html` page accessible from the frontend | MUST | Given a browser navigating to `history.html`, when the page loads, then it renders without errors and displays the history table |
| FR-4-46 | The history page SHALL display a filter row with a strategy dropdown listing all 20 strategies plus an "All Strategies" option | MUST | Given the history page loaded, when the strategy dropdown is opened, then it contains "All Strategies" and entries for each of the 20 strategies by name |
| FR-4-47 | The history page SHALL display a filter row with a status dropdown offering: All Statuses, Valid Trade, Wait For Levels, No Trade | MUST | Given the history page loaded, when the status dropdown is opened, then all four options are present |
| FR-4-48 | The history page SHALL display a date range picker with From and To date inputs | MUST | Given the history page loaded, when the filter row is inspected, then two date input fields are present and labelled From and To |
| FR-4-49 | The history page SHALL include an "Apply Filters" button that re-fetches data from `GET /api/history` with the selected filter parameters | MUST | Given filter selections are made and "Apply Filters" is clicked, when the button is activated, then the table re-renders showing only matching records |
| FR-4-50 | The history table SHALL display the following columns: Timestamp (UTC), Strategy, Status, Direction, Entry, SL, TP1, RRR, Confidence, Outcome | MUST | Given the history page with data loaded, when the table is inspected, then all ten columns are present with the correct labels |
| FR-4-51 | The Status column SHALL use color-coded badges: green for VALID TRADE, amber for WAIT FOR LEVELS, grey for NO TRADE | MUST | Given a table row with VALID_TRADE status, when the row is rendered, then the status cell shows a green badge |
| FR-4-52 | The Direction column SHALL display a BUY chip in green or SELL chip in red, and SHALL be empty for NO TRADE records | MUST | Given a table row with direction=BUY, when rendered, then a green BUY chip is shown; for NO TRADE rows, the Direction cell is empty |
| FR-4-53 | The Outcome column SHALL display WIN in green, LOSS in red, PENDING in grey, and N/A in muted style | MUST | Given rows with different outcome values, when rendered, then each outcome uses the correct color treatment |
| FR-4-54 | Clicking any row in the history table SHALL navigate to the detail view for that signal | MUST | Given a rendered history table row, when the row is clicked, then the browser navigates to `detail.html` for that signal's ID |
| FR-4-55 | The history page SHALL support inline outcome editing: clicking the Outcome cell of a PENDING row SHALL reveal a dropdown with WIN and LOSS options | MUST | Given a row with PENDING outcome, when the Outcome cell is clicked, then a dropdown appears with WIN and LOSS as selectable options |
| FR-4-56 | Selecting WIN or LOSS from the inline dropdown SHALL call `PATCH /api/history/{id}/outcome` and update the displayed cell without a full page reload | MUST | Given a PENDING row with the inline dropdown open and WIN selected, when the selection is confirmed, then the API is called and the cell updates to display WIN in green |
| FR-4-57 | The history page SHALL display a summary stats bar above the table showing: total signals in the filtered view, VALID TRADE count, win rate, and average confidence of VALID signals | MUST | Given a history page with 20 signal records loaded, when the summary bar is inspected, then all four stats are displayed |
| FR-4-58 | The win rate stat SHALL show "Insufficient data" when fewer than 10 resolved (WIN or LOSS) signals exist in the current filtered view | MUST | Given a filtered view containing 5 resolved VALID signals, when the summary bar is rendered, then the win rate displays "Insufficient data" |
| FR-4-59 | The history page SHALL display a loading state while data is being fetched from the API | SHOULD | Given the history page loading for the first time, when the API call is in flight, then a loading indicator is visible in the table area |
| FR-4-60 | The history page SHALL display an empty state message when no signals match the applied filters | SHOULD | Given filters that match zero records, when the table renders, then a "No signals found for the selected filters" message is shown instead of an empty table |

### 3.8 Navigation Update

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-4-61 | The navigation bar on `index.html` SHALL include a "History" link pointing to `history.html` | MUST | Given `index.html` loaded, when the navigation bar is inspected, then a History link is present and functional |
| FR-4-62 | The navigation bar on `strategies.html` SHALL include a "History" link pointing to `history.html` | MUST | Given `strategies.html` loaded, when the navigation bar is inspected, then a History link is present and functional |
| FR-4-63 | The navigation bar on `detail.html` SHALL include a "History" link pointing to `history.html` | MUST | Given `detail.html` loaded, when the navigation bar is inspected, then a History link is present and functional |
| FR-4-64 | The navigation bar on `history.html` SHALL include links to Dashboard, Strategies, and History with History visually marked as active | MUST | Given `history.html` loaded, when the navigation bar is inspected, then all three links are present and the History link has an active visual state |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-01 | Telegram message delivery SHALL complete within 30 seconds of the evaluation cycle writing the VALID_TRADE signal record | MUST | Given a VALID_TRADE transition detected, when measured from signal write to message delivery confirmation, then the elapsed time is ≤ 30 seconds |
| NFR-4-02 | The `GET /api/history` endpoint SHALL return a response within 500 milliseconds for any query returning up to 200 records | MUST | Given a history query returning up to 200 records, when response time is measured, then it is ≤ 500 ms |
| NFR-4-03 | The `PATCH /api/history/{id}/outcome` endpoint SHALL return a response within 200 milliseconds | MUST | Given an outcome update request, when response time is measured, then it is ≤ 200 ms |
| NFR-4-04 | The history page SHALL render the initial table within 2 seconds of page load under normal local network conditions | SHOULD | Given the history page opening in a browser, when the load is timed from navigation to first table row visible, then elapsed time is ≤ 2 seconds |
| NFR-4-05 | The Telegram retry logic SHALL NOT block the evaluation scheduler for more than 30 seconds | MUST | Given a Telegram failure with a retry in progress, when measured from failure detection to evaluation cycle resumption, then the scheduler is delayed by no more than 30 seconds |

### 4.2 Reliability

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-06 | The evaluation cycle and signal write path SHALL continue to operate normally when Telegram is unavailable | MUST | Given the Telegram API being unreachable, when an evaluation cycle runs, then all 20 strategy results are still written to SQLite and no exception propagates to the scheduler |
| NFR-4-07 | The system SHALL log all Telegram send failures with sufficient detail for diagnosis (timestamp, strategy ID, error message) | MUST | Given a Telegram failure, when the log is inspected, then an entry contains the UTC timestamp, the strategy ID, and the exception message |
| NFR-4-08 | The history API endpoints SHALL return a structured error response rather than an unhandled exception for all error conditions | MUST | Given any error condition (invalid ID, database error, invalid parameter), when the API responds, then the response uses the standard `{ success: false, data: null, error: "..." }` envelope |
| NFR-4-09 | Signal writes to SQLite SHALL be atomic — either the full record is written or no partial record is written | MUST | Given the system being killed mid-write, when the database is inspected, then no partial or corrupt signal rows exist |

### 4.3 Data Integrity

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-10 | All pip distance calculations in Telegram messages SHALL be accurate to 0.1 pips | MUST | Given a VALID_TRADE with entry 149.850 and SL 149.200, when the Telegram message is inspected, then the SL pip distance shown matches the actual distance computed from entry and SL |
| NFR-4-11 | Win rate calculations SHALL use only resolved signals (outcome = WIN or LOSS), never PENDING or N/A signals, as the denominator | MUST | Given 10 resolved signals (7 WIN, 3 LOSS) and 5 PENDING signals in view, when win rate is displayed, then it shows 70% (7/10), not 46.7% (7/15) |
| NFR-4-12 | The deduplication logic SHALL compare both entry price AND SL price, not verdict alone, before suppressing a write | MUST | Given the same strategy producing NO_TRADE twice with different SL values within 4 hours, when both results are processed, then two separate rows exist in the signals table |
| NFR-4-13 | Outcome updates via `PATCH /api/history/{id}/outcome` SHALL be persisted to SQLite immediately and SHALL survive a server restart | MUST | Given an outcome updated to WIN, when the server is restarted and the record is re-fetched, then the outcome field still shows WIN |

### 4.4 Maintainability

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-14 | All Telegram message composition logic SHALL reside exclusively in `notifications/telegram_bot.py` | MUST | Given a review of the codebase, when searching for string formatting related to Telegram message content, then all such logic is found only in `notifications/telegram_bot.py` |
| NFR-4-15 | All signal history database operations SHALL go through `db/signal_store.py` — no raw SQL in the API layer or scheduler | MUST | Given a review of `api/history.py` and `scheduler.py`, when searching for SQL statements, then none are found — all DB access is via `signal_store.py` functions |
| NFR-4-16 | All configuration values (retry delay, deduplication window, per_page default) SHALL be sourced from `config.py` | MUST | Given a review of `notifications/telegram_bot.py` and `api/history.py`, when searching for numeric literals matching retry delay or window values, then none are hardcoded |

### 4.5 Security

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-17 | The Telegram bot token SHALL NOT appear in any source file, commit, or log output | MUST | Given a full-text search of the repository for the token value, when the search completes, then no matches are found in any `.py`, `.html`, `.js`, or `.md` file |
| NFR-4-18 | The Telegram chat ID SHALL NOT appear hardcoded in any source file | MUST | Given a review of all Python and JavaScript files, when searching for the chat ID value, then no hardcoded matches are found |
| NFR-4-19 | The `PATCH /api/history/{id}/outcome` endpoint SHALL validate and sanitise the outcome value before writing to SQLite | MUST | Given a PATCH request with a SQL injection payload in the outcome field, when the request is processed, then the database is not modified and a 422 response is returned |

### 4.6 Compatibility

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-4-20 | The Telegram integration SHALL use `python-telegram-bot` version 20 or higher and SHALL correctly await all async send operations within FastAPI's async context | MUST | Given the server running and a VALID_TRADE trigger occurring, when the Telegram send is executed, then no asyncio runtime warnings or errors appear in the log |
| NFR-4-21 | The `history.html` page SHALL render correctly in current versions of Chrome, Edge, and Firefox on Windows | MUST | Given `history.html` opened in Chrome, Edge, and Firefox, when each page is inspected, then all columns, filters, badges, and inline editing function correctly |
| NFR-4-22 | The system SHALL run on Python 3.11 or higher | MUST | Given the server starting with Python 3.11, when `main.py` is executed, then no syntax or compatibility errors occur |

---

## 5. Data Specifications

### 5.1 Data Models

#### 5.1.1 `signals` Table — Phase 4 Additions

The `signals` table was created in Phase 1. Phase 4 adds one new column:

| Field           | Type    | Constraints               | Description                                                      |
|-----------------|---------|---------------------------|------------------------------------------------------------------|
| telegram_failed | BOOLEAN | NOT NULL, DEFAULT FALSE   | Set to TRUE when all Telegram send attempts for this signal fail |

All other columns defined in Phase 1 remain unchanged.

#### 5.1.2 `signals` Table — Complete Schema (for reference)

| Field          | Type     | Constraints        | Description                                              |
|----------------|----------|--------------------|----------------------------------------------------------|
| id             | INTEGER  | PK, AUTOINCREMENT  | Unique signal identifier                                 |
| timestamp      | DATETIME | NOT NULL           | UTC time when the signal was generated or last updated   |
| strategy_id    | INTEGER  | NOT NULL, 1–20     | Strategy number                                          |
| strategy_name  | TEXT     | NOT NULL           | Human-readable strategy name                             |
| status         | TEXT     | NOT NULL           | VALID_TRADE / WAIT_FOR_LEVELS / NO_TRADE                 |
| direction      | TEXT     | NULLABLE           | BUY / SELL / NULL                                        |
| entry          | REAL     | NULLABLE           | Entry price                                              |
| sl             | REAL     | NULLABLE           | Stop loss price                                          |
| tp1            | REAL     | NULLABLE           | Take profit 1 price                                      |
| tp2            | REAL     | NULLABLE           | Take profit 2 price                                      |
| tp3            | REAL     | NULLABLE           | Take profit 3 price (optional)                           |
| rrr            | REAL     | NULLABLE           | Risk-reward ratio                                        |
| confidence     | INTEGER  | NULLABLE, 0–100    | Debate engine confidence score                           |
| probability    | INTEGER  | NULLABLE, 0–100    | Debate engine probability score                          |
| timeframes     | TEXT     | NULLABLE           | Timeframes used (e.g., "H1/H4/D")                       |
| reasons_for    | TEXT     | NULLABLE           | JSON array of supporting reasons                         |
| reasons_against| TEXT     | NULLABLE           | JSON array of opposing reasons                           |
| verdict_summary| TEXT     | NULLABLE           | Final decision narrative                                 |
| outcome        | TEXT     | NOT NULL           | WIN / LOSS / PENDING / N/A                               |
| telegram_failed| BOOLEAN  | NOT NULL, DEFAULT FALSE | Phase 4 addition — TRUE if Telegram send failed     |

#### 5.1.3 `GET /api/history` Response Envelope

| Field       | Type    | Description                                      |
|-------------|---------|--------------------------------------------------|
| success     | BOOLEAN | TRUE if query succeeded                          |
| data        | OBJECT  | Contains `signals` array and pagination metadata |
| error       | STRING  | NULL on success; error message on failure        |

`data` object fields:

| Field       | Type    | Description                          |
|-------------|---------|--------------------------------------|
| signals     | ARRAY   | Array of signal record objects       |
| total       | INTEGER | Total matching records               |
| page        | INTEGER | Current page number                  |
| per_page    | INTEGER | Records per page                     |
| total_pages | INTEGER | Total number of pages                |

#### 5.1.4 `PATCH /api/history/{id}/outcome` Request Body

| Field   | Type   | Required | Allowed Values     |
|---------|--------|----------|--------------------|
| outcome | STRING | Yes      | WIN, LOSS, N/A     |

### 5.2 Data Flows

#### Telegram Alert Flow
1. Scheduler completes an evaluation cycle → 20 `StrategyResult` objects produced
2. Scheduler compares each result against the in-memory last-cycle cache
3. For each strategy where verdict changed to VALID_TRADE: `telegram_bot.py` composes message
4. `telegram_bot.py` sends message to Telegram Bot API
5. On success: `telegram_failed` remains FALSE on the signal record
6. On failure: 30-second wait → retry → on second failure: log error, set `telegram_failed = TRUE` on the signal record
7. In-memory cache is updated with the current cycle's verdicts

If Telegram is unavailable: steps 4–6 still execute (logging and flag setting), but step 7 completes regardless and the scheduler continues normally.

#### Signal Write Flow
1. Each `StrategyResult` from the evaluation cycle is passed to `signal_store.py`
2. `signal_store.py` queries for an existing record: same strategy_id, same status, same entry, same sl, within the last 4 hours
3. If a matching record exists: UPDATE timestamp only
4. If no matching record (or verdict changed): INSERT new row with appropriate outcome default
5. All writes are committed within a single SQLite transaction per evaluation cycle

If SQLite is unavailable: the error is logged; the scheduler does not crash; Telegram is still attempted for VALID transitions detected from the in-memory cache.

#### History Page Data Flow
1. `history.html` loads in browser
2. `history.js` calls `GET /api/history` with default parameters
3. Response received: summary stats bar is populated; table rows are rendered
4. User adjusts filters and clicks "Apply Filters": `history.js` calls `GET /api/history` with filter parameters
5. User clicks an Outcome cell on a PENDING row: dropdown rendered inline
6. User selects WIN or LOSS: `history.js` calls `PATCH /api/history/{id}/outcome`; on success, the cell updates in place

### 5.3 Interface Contracts

#### Telegram Bot API
- **Direction:** Outbound (system → Telegram)
- **Protocol:** HTTPS POST to `https://api.telegram.org/bot{token}/sendMessage`
- **Data format:** JSON body with `chat_id` (string) and `text` (string, Markdown or plain text)
- **Expected frequency:** At most 20 messages per evaluation cycle, at most once per strategy per cycle in steady state; typically 0–3 per cycle
- **Rate limits:** Telegram allows 30 messages per second per bot — well within system capacity
- **Error conditions:** HTTP 4xx (bad token, bad chat ID), HTTP 5xx (Telegram outage), network timeout. All are handled by logging and the single retry mechanism.

#### FastAPI Signal History Endpoints
- **Direction:** Inbound (browser → FastAPI)
- **Protocol:** HTTP over localhost
- **Frequency:** On-demand from browser; no polling
- **Error conditions:** Invalid IDs return 404; invalid parameter values return 422; all errors use the standard response envelope

---

## 6. Interface Specifications

### 6.1 Internal API Contracts

#### `GET /api/history`
- **Method:** GET
- **Path:** `/api/history`
- **Query Parameters:**

| Name        | Type    | Required | Default | Description                                      |
|-------------|---------|----------|---------|--------------------------------------------------|
| page        | integer | No       | 1       | Page number (1-indexed)                          |
| per_page    | integer | No       | 50      | Records per page, maximum 200                    |
| status      | string  | No       | —       | Filter: VALID_TRADE, WAIT_FOR_LEVELS, or NO_TRADE |
| strategy_id | integer | No       | —       | Filter: strategy number 1–20                     |

- **Response Schema (200 OK):**
```json
{
  "success": true,
  "data": {
    "signals": [
      {
        "id": 42,
        "timestamp": "2026-04-24T14:02:00Z",
        "strategy_id": 1,
        "strategy_name": "Multi-Timeframe Trend Alignment",
        "status": "VALID_TRADE",
        "direction": "BUY",
        "entry": 149.850,
        "sl": 149.200,
        "tp1": 150.500,
        "tp2": 151.150,
        "tp3": null,
        "rrr": 2.0,
        "confidence": 82,
        "probability": 78,
        "timeframes": "H1/H4/D",
        "reasons_for": ["H4 higher-low confirmed", "H1 MACD bullish cross"],
        "reasons_against": ["VIX slightly elevated"],
        "verdict_summary": "Strong alignment across timeframes with acceptable risk.",
        "outcome": "PENDING",
        "telegram_failed": false
      }
    ],
    "total": 1240,
    "page": 1,
    "per_page": 50,
    "total_pages": 25
  },
  "error": null
}
```
- **Error Responses:**

| Status | Condition | Error Body |
|---|---|---|
| 422 | Invalid `status` value | `{ "success": false, "data": null, "error": "Invalid status value. Must be VALID_TRADE, WAIT_FOR_LEVELS, or NO_TRADE" }` |
| 422 | `strategy_id` out of range | `{ "success": false, "data": null, "error": "strategy_id must be an integer between 1 and 20" }` |

---

#### `GET /api/history/{id}`
- **Method:** GET
- **Path:** `/api/history/{id}`
- **Path Parameters:**

| Name | Type    | Required | Description       |
|------|---------|----------|-------------------|
| id   | integer | Yes      | Signal record ID  |

- **Response Schema (200 OK):** Same signal object structure as above but wrapped in `data` directly (not an array)
- **Error Responses:**

| Status | Condition | Error Body |
|---|---|---|
| 404 | Signal ID not found | `{ "success": false, "data": null, "error": "Signal with id {id} not found" }` |

---

#### `PATCH /api/history/{id}/outcome`
- **Method:** PATCH
- **Path:** `/api/history/{id}/outcome`
- **Path Parameters:**

| Name | Type    | Required | Description       |
|------|---------|----------|-------------------|
| id   | integer | Yes      | Signal record ID  |

- **Request Body:**
```json
{ "outcome": "WIN" }
```
- **Response Schema (200 OK):**
```json
{
  "success": true,
  "data": { "id": 42, "outcome": "WIN" },
  "error": null
}
```
- **Error Responses:**

| Status | Condition | Error Body |
|---|---|---|
| 404 | Signal ID not found | `{ "success": false, "data": null, "error": "Signal with id {id} not found" }` |
| 422 | Invalid outcome value | `{ "success": false, "data": null, "error": "outcome must be WIN, LOSS, or N/A" }` |

---

### 6.2 External System Interfaces

#### Telegram Bot API
- **System:** Telegram Bot API v7+
- **Authentication:** Bot token passed in the URL path (`/bot{TELEGRAM_TOKEN}/sendMessage`)
- **Key operation:** `sendMessage` — POST with `chat_id` and `text`
- **Rate limits:** 30 messages per second per bot; 1 message per second per chat (system sends at most a few messages per evaluation cycle, well within limits)
- **Constraints:** Token and chat ID must be environment variables; messages are plain text or Markdown; no file attachments in Phase 4
- **Fallback:** If unavailable, log error, set `telegram_failed = TRUE`, continue normal operation

### 6.3 User Interface Specifications

#### `history.html` — Signal History Page

**Purpose:** Allow the user to browse, filter, and manage the full signal history log including outcome tracking.

**Layout:**
- Navigation bar at top: Dashboard | Strategies | History (History active)
- Summary stats bar below navigation: 4 stat tiles in a horizontal row
- Filter row below stats bar: strategy dropdown, status dropdown, from/to date inputs, Apply Filters button
- Data table filling the remaining page width
- Pagination controls below the table

**Summary Stats Bar:**
- Total Signals: integer count of records matching the current filter
- Valid Trades: count of VALID_TRADE records in the filtered view
- Win Rate: percentage of resolved (WIN+LOSS) signals that are WIN; shows "Insufficient data" if fewer than 10 resolved signals exist
- Avg Confidence: mean confidence score of VALID_TRADE records in the filtered view; shows "—" if no VALID records exist

**Filter Row:**
- Strategy dropdown: options are "All Strategies" plus each of the 20 strategy names
- Status dropdown: options are "All Statuses", "Valid Trade", "Wait For Levels", "No Trade"
- From date input: type="date", optional, limits results to signals on or after this date
- To date input: type="date", optional, limits results to signals on or before this date
- Apply Filters button: triggers API call with current filter values

**Data Table:**

| Column    | Source Field     | Render Notes                                                   |
|-----------|------------------|----------------------------------------------------------------|
| Timestamp | `timestamp`      | Formatted as YYYY-MM-DD HH:mm UTC                              |
| Strategy  | `strategy_name`  | Plain text                                                     |
| Status    | `status`         | Color-coded badge: green (VALID_TRADE), amber (WAIT), grey (NO_TRADE) |
| Direction | `direction`      | Green BUY chip / Red SELL chip / empty for NO_TRADE            |
| Entry     | `entry`          | 3 decimal places; empty if NULL                                |
| SL        | `sl`             | 3 decimal places; empty if NULL                                |
| TP1       | `tp1`            | 3 decimal places; empty if NULL                                |
| RRR       | `rrr`            | Format: "1:X.X"; empty if NULL                                 |
| Confidence| `confidence`     | Integer 0–100; empty if NULL                                   |
| Outcome   | `outcome`        | WIN (green) / LOSS (red) / PENDING (grey, editable) / N/A (muted) |

**Interactive Elements:**
- Clicking any row (except the Outcome cell on a PENDING row): navigates to `detail.html?id={id}`
- Clicking the Outcome cell on a PENDING row: shows an inline dropdown with WIN and LOSS options
- Selecting WIN or LOSS from the inline dropdown: calls PATCH endpoint, updates cell in place, recalculates summary stats
- Apply Filters button: re-fetches data with current filter values; resets to page 1
- Pagination controls: Previous / Next buttons and page number indicator

**Loading State:** A spinner or "Loading..." text is shown in the table area while the API call is in flight.

**Empty State:** When no records match the applied filters, the table body shows a single full-width row with the message "No signals found for the selected filters."

**Error State:** If the API call fails, a banner above the table reads "Failed to load signal history. Please try again."

---

## 7. Constraints

- **Platform:** Windows only — the system runs on a local Windows machine with MT5 terminal
- **Language:** Python 3.11 or higher for all backend code
- **Telegram library:** `python-telegram-bot` v20 or higher — async API must be properly integrated with FastAPI's async event loop
- **Frontend technology:** Vanilla HTML5, CSS3, and JavaScript — no JavaScript frameworks or build tools
- **Notification channel:** Telegram only — no other notification channels are in scope for this phase
- **Credentials:** Telegram token and chat ID must be stored in environment variables loaded via `python-dotenv` — never in source code
- **Database:** SQLite only, accessed exclusively through `db/signal_store.py` — no raw SQL in other modules
- **Configuration:** All numeric constants (retry delay, deduplication window, pagination defaults) must be defined in `config.py`
- **Single user:** No authentication layer is required; the system is accessed only by the developer on the local machine
- **Signal write access:** The `outcome` field is the only signal field that can be modified after initial write — all other fields are immutable once written

---

## 8. Assumptions

- It is assumed that the user's Telegram bot is already created and that a valid `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are available in the `.env` file before Phase 4 testing. If this is incorrect, Telegram integration tests cannot be validated until the bot is configured.
- It is assumed that the Telegram chat is a personal or private chat owned by the user, not a public channel with rate restrictions that differ from standard bot API limits. If this is incorrect, the send frequency design may need to be re-evaluated.
- It is assumed that `python-telegram-bot` v20+ is listed in `requirements.txt` and can be installed without conflicts. If this is incorrect, the async integration design must be revisited for a compatible version.
- It is assumed that the SQLite `signals` table exists with all Phase 1 columns intact before Phase 4 begins. If this is incorrect, the database migration script must also re-create the base table, not only add the `telegram_failed` column.
- It is assumed that the `detail.html` page already accepts a signal ID via URL query parameter (e.g., `?id=42`) and can display a historical signal. If this is incorrect, `detail.html` may require modification beyond navigation bar addition.
- It is assumed that all 20 evaluation cycles per hour produce a maximum of 20 new signal rows, giving SQLite a write load of at most 480 rows per day before deduplication. If evaluation frequency increases significantly, the deduplication window may need tuning.
- It is assumed that the browser accessing the frontend is running on the same Windows machine as the backend server (localhost). If this is incorrect, CORS configuration may need to be added to FastAPI.

---

## 9. Risks and Mitigations

| ID        | Risk                                                              | Likelihood | Impact | Mitigation                                                                                                           |
|-----------|-------------------------------------------------------------------|------------|--------|----------------------------------------------------------------------------------------------------------------------|
| RISK-4-01 | Telegram Bot API is unavailable (network outage or Telegram outage) | Medium  | Low    | Retry once after 30s; log failure; set `telegram_failed` flag; evaluation cycle continues unaffected                 |
| RISK-4-02 | Bot token is invalid or bot has been revoked                      | Low        | Medium | Failure is caught and logged on first send; system does not crash; user is alerted via log that token should be checked |
| RISK-4-03 | python-telegram-bot async calls deadlock or conflict with FastAPI event loop | Low | High | Use the library's correct async integration pattern (ApplicationBuilder with proper await); validate during development |
| RISK-4-04 | Same VALID_TRADE signal fires Telegram repeatedly due to in-memory cache being reset on server restart | Low | Low | Cache is populated on first cycle after restart without sending; subsequent cycles compare normally                   |
| RISK-4-05 | Deduplication logic incorrectly suppresses new rows when strategy parameters change subtly | Low | Medium | Deduplication checks both entry AND SL price; a change to either forces a new row regardless of verdict              |
| RISK-4-06 | Signal history table grows unbounded and query performance degrades over months | Low | Low | SQLite handles tens of thousands of rows easily for a single-user system; index on `strategy_id` and `timestamp` mitigates query time |
| RISK-4-07 | Win rate displayed is misleading if the user has few resolved signals | Medium | Low | Win rate shows "Insufficient data" below 10 resolved signals, preventing false conclusions from small samples          |
| RISK-4-08 | SQLite write failure (disk full, permissions) causes signal loss   | Low        | High   | Error is caught and logged; scheduler does not crash; next evaluation cycle retries the write path                   |

---

## 10. Acceptance Criteria

| ID     | Acceptance Criterion                                                                                                                            |
|--------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| AC-4-01 | A test VALID_TRADE result produced by the strategy engine triggers a Telegram message that is received within 30 seconds                        |
| AC-4-02 | The received Telegram message contains all ten required fields: strategy name and number, direction, entry, SL with pip distance, TP1 and TP2 with pip distances, RRR, confidence, timeframes, Why summary, Against summary, and Evaluated timestamp |
| AC-4-03 | The Telegram message begins with the exact prefix `[USDJPY Smart Agent]`                                                                        |
| AC-4-04 | When the same strategy remains VALID_TRADE in two consecutive evaluation cycles, exactly one Telegram message is sent (not two)                 |
| AC-4-05 | When the Telegram API is unreachable, the evaluation cycle completes normally, all 20 signal results are written to SQLite, and the failed signal record has `telegram_failed = TRUE` |
| AC-4-06 | After 24 hours of continuous operation, the signals table contains no more than one NO_TRADE row per 4-hour window per strategy (deduplication is working) |
| AC-4-07 | Every evaluation cycle writes exactly the expected number of rows (or fewer due to deduplication) — no signals are silently lost                |
| AC-4-08 | VALID_TRADE signal records have `outcome = PENDING` on creation; NO_TRADE records have `outcome = N/A`                                          |
| AC-4-09 | `GET /api/history` returns results in descending timestamp order with correct pagination metadata                                               |
| AC-4-10 | `GET /api/history?status=VALID_TRADE` returns only VALID_TRADE records                                                                          |
| AC-4-11 | `GET /api/history?strategy_id=5` returns only records for strategy 5                                                                           |
| AC-4-12 | `GET /api/history/99999` returns HTTP 404 with the standard error envelope                                                                      |
| AC-4-13 | `PATCH /api/history/{id}/outcome` with `{ "outcome": "WIN" }` updates the record and the change persists after server restart                   |
| AC-4-14 | `PATCH /api/history/{id}/outcome` with an invalid value returns HTTP 422                                                                        |
| AC-4-15 | `history.html` renders correctly in Chrome, Edge, and Firefox with all columns, badges, and filters visible                                     |
| AC-4-16 | Filtering by strategy and status on the history page returns only matching records                                                              |
| AC-4-17 | Clicking the Outcome cell of a PENDING row reveals a WIN/LOSS dropdown; selecting WIN updates the cell in place without a page reload           |
| AC-4-18 | The win rate stat shows "Insufficient data" when fewer than 10 resolved signals are in the current filtered view                                |
| AC-4-19 | All four pages (`index.html`, `strategies.html`, `detail.html`, `history.html`) display a navigation bar with a working History link            |
| AC-4-20 | The Telegram bot token and chat ID are not present in any source file or committed to the repository                                            |

---

## 11. Traceability Matrix

| Acceptance Criterion | Functional Requirement(s)                        |
|----------------------|--------------------------------------------------|
| AC-4-01              | FR-4-01, FR-4-18, FR-4-19                        |
| AC-4-02              | FR-4-07, FR-4-08, FR-4-09, FR-4-10, FR-4-11, FR-4-12, FR-4-13, FR-4-14, FR-4-15, FR-4-16, FR-4-17 |
| AC-4-03              | FR-4-06                                          |
| AC-4-04              | FR-4-04, FR-4-24, FR-4-25                        |
| AC-4-05              | FR-4-20, FR-4-21, FR-4-22, FR-4-23              |
| AC-4-06              | FR-4-31, FR-4-32                                 |
| AC-4-07              | FR-4-27, FR-4-33                                 |
| AC-4-08              | FR-4-28, FR-4-29                                 |
| AC-4-09              | FR-4-34, FR-4-39                                 |
| AC-4-10              | FR-4-37                                          |
| AC-4-11              | FR-4-38                                          |
| AC-4-12              | FR-4-41                                          |
| AC-4-13              | FR-4-42, FR-4-43                                 |
| AC-4-14              | FR-4-43                                          |
| AC-4-15              | FR-4-45, FR-4-50, FR-4-51, FR-4-52, FR-4-53     |
| AC-4-16              | FR-4-46, FR-4-47, FR-4-49                        |
| AC-4-17              | FR-4-55, FR-4-56                                 |
| AC-4-18              | FR-4-58                                          |
| AC-4-19              | FR-4-61, FR-4-62, FR-4-63, FR-4-64              |
| AC-4-20              | FR-4-18, FR-4-19                                 |

---

## 12. Open Questions

| ID      | Question                                                                                                                                                    | Impact if Unresolved                                                                                   | Owner |
|---------|-------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|-------|
| OQ-4-01 | Should the `detail.html` page support displaying historical signals (accessed from the history table) in addition to live signals from the current cycle? Phase 3 built `detail.html` for live strategy data; it may need a mode switch or a separate history detail view. | If unresolved, clicking a history table row has no valid destination and FR-4-54 cannot be implemented | Developer |
| OQ-4-02 | Should the first evaluation cycle after server restart suppress Telegram alerts (FR-4-26 is SHOULD priority)? In a live trading context, missing a VALID signal on restart could be costly. | If alerts fire on every restart, the user may receive duplicate alerts for long-running VALID signals; if suppressed, a real new signal immediately after restart is missed | Developer / User |
| OQ-4-03 | Is TP2 always populated for VALID_TRADE signals, or can it be NULL? If TP2 is nullable, the Telegram message format must handle its absence gracefully without showing a blank TP2 line. | If unresolved and TP2 is sometimes NULL, the Telegram message may include a malformed line | Developer |

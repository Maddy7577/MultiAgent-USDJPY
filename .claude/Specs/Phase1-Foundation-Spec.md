# Phase 1 — Foundation Specification

---

## Document Control

| Field        | Value                          |
|--------------|-------------------------------|
| Document ID  | SPEC-PHASE-1-v1.0              |
| Version      | v1.0                           |
| Status       | Draft                          |
| Created      | 2026-04-24                     |
| Author       | USDJPY Smart Agent Project     |
| Phase        | 1 of 5                         |
| Phase Name   | Foundation                     |

### Change History

| Version | Date | Author | Summary of Changes |
|---|---|---|---|
| v1.0 | 2026-04-24 | — | Initial draft |

---

## 1. Introduction

### 1.1 Purpose

This document is the formal software specification for Phase 1 (Foundation) of the USDJPY Smart Agent system. It defines the complete functional and non-functional requirements for the data ingestion pipeline, persistent storage layer, background scheduler, and REST API skeleton that together form the infrastructure upon which all subsequent phases are built. It is intended for use by the developer implementing Phase 1 and by any reviewer verifying that the phase deliverable meets its acceptance criteria before Phase 2 begins.

### 1.2 Scope

This specification covers all system behaviour required to establish a running local server capable of: connecting to the MetaTrader 5 terminal and retrieving USDJPY price data; fetching macro context data from FRED and yfinance; parsing and caching the Forex Factory economic calendar; creating and operating a local persistent signal store; exposing a set of REST API endpoints (some as stubs); and running a UTC-synchronised background scheduler.

This specification does not cover: strategy evaluation logic, the 4-agent debate framework, trade signal generation, Telegram notification delivery, frontend rendering, or any automated order execution. All of those belong to Phases 2 through 5.

### 1.3 Definitions and Abbreviations

| Term / Abbreviation | Definition |
|---|---|
| MT5 | MetaTrader 5 — the third-party trading terminal used as the OHLCV data source |
| OHLCV | Open, High, Low, Close, Volume — the standard candlestick bar data format |
| H1, H4, M15, M30, D | Candlestick timeframes: 1-hour, 4-hour, 15-minute, 30-minute, Daily |
| FRED | Federal Reserve Economic Data — St. Louis Fed's public economic data API |
| DGS10 | FRED series identifier for the US 10-Year Treasury Constant Maturity Yield |
| DFF | FRED series identifier for the Effective Federal Funds Rate |
| DXY | US Dollar Index — a measure of USD strength against a basket of currencies |
| VIX | CBOE Volatility Index — a measure of expected market volatility |
| FF iCal | Forex Factory public economic calendar in iCalendar format |
| BoJ | Bank of Japan |
| FOMC | Federal Open Market Committee — the US Federal Reserve's rate-setting body |
| NFP | US Non-Farm Payrolls — monthly US employment data release |
| CPI | Consumer Price Index — a measure of inflation |
| PCE | Personal Consumption Expenditures — an alternative US inflation measure |
| VALID TRADE | A trade verdict indicating a high-confidence, rule-compliant setup with full parameters |
| WAIT FOR LEVELS | A trade verdict indicating a valid setup that has not yet reached its ideal entry zone |
| NO TRADE | A trade verdict indicating conditions are not met or opposing factors are too strong |
| RRR | Risk-Reward Ratio — the ratio of potential profit to potential loss on a trade |
| SL | Stop Loss — the price level at which a losing trade is closed |
| TP | Take Profit — the price level at which a winning trade is closed |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| AC | Acceptance Criterion |
| UTC | Coordinated Universal Time — the timezone standard used throughout this system |
| CORS | Cross-Origin Resource Sharing — an HTTP mechanism allowing browsers to access APIs from different origins |
| iCal | iCalendar — a standard format for calendar data (RFC 5545) |
| JSON | JavaScript Object Notation — the data format used by all API responses |
| API | Application Programming Interface |
| REST | Representational State Transfer — the architectural style used for the HTTP API |

### 1.4 References

| Document | Location |
|---|---|
| USDJPY Smart Agent System Architecture | `.claude/Documents/system_architecture.md` |
| Phase 1 Build Guide | `.claude/Documents/01-Phase1-Foundation.md` |
| FRED API Documentation | https://fred.stlouisfed.org/docs/api/fred/ |
| MetaTrader 5 Python API Documentation | https://www.mql5.com/en/docs/python_metatrader5 |
| Forex Factory iCal Feed | Public iCal URL (no key required) |
| iCalendar Standard | RFC 5545 |

---

## 2. System Context

### 2.1 Phase Position in System

Phase 1 is the first of five phases and is the foundational layer upon which all other phases depend. It has no predecessor phases within this project. All four subsequent phases (Strategy Engine, Frontend, Notifications, Automated Trading) require Phase 1 to be complete and fully operational before they can be built or tested.

```
Phase 1 (Foundation)  ◄── this document
    └── Phase 2 (Strategy Engine)
        └── Phase 3 (Frontend)
            └── Phase 4 (Notifications)
                └── Phase 5 (Automated Trading)
```

### 2.2 Phase Goal

Establish a running local server that connects to all data sources, stores market context persistently, and exposes a working REST API, so that Phase 2 can immediately begin consuming live data without any infrastructure work.

### 2.3 In Scope for This Phase

- Python project structure and dependency manifest (`requirements.txt`)
- Single-module centralised configuration (`config.py`) sourcing all constants from environment variables
- MT5 data feed: terminal connection, OHLCV fetch for M15/M30/H1/H4/D timeframes, graceful disconnection handling
- FRED API feed: US 10-Year Treasury Yield and Federal Funds Rate, with caching
- yfinance market feed: DXY and VIX values, with caching
- Forex Factory iCal feed: parsing, USDJPY-relevant event filtering, daily refresh, 24-hour cache, news-imminent boolean query
- SQLite database: automatic schema creation on first run, `signals` table, `market_context` table, read/write access module
- FastAPI HTTP server: startup, CORS configuration, all five REST endpoints (four as stubs, `/api/dashboard` and `/api/status` as functional)
- APScheduler background scheduler: UTC timezone, three scheduled jobs (H1, H4, daily), starting with the server
- Market context snapshot: periodically written to the database after each data refresh

### 2.4 Out of Scope for This Phase

- Any strategy evaluation, indicator calculation, or trade signal generation
- The 4-agent debate framework (Opportunity Agents, Risk Agents, Debate Engine)
- Strategy result writing to the `signals` table (signals table is created but remains empty)
- Telegram notification delivery
- Frontend HTML/CSS/JS pages (Dashboard, Strategy Cards, Strategy Detail)
- MT5 order placement, modification, or cancellation
- User authentication or access control
- Any database content beyond market context snapshots
- Populating `/api/strategies`, `/api/strategy/{id}`, or `/api/history` with real data
- Backtesting, historical analysis, or performance reporting
- BoJ policy rate data feed (field exists in schema but source not yet wired up)
- Automated trading risk controls

### 2.5 Predecessor Dependencies

Phase 1 has no predecessor phases. However, the following external dependencies must be satisfied before development can proceed:

- A MetaTrader 5 terminal must be installed and running on the Windows machine with a USDJPY symbol available
- A FRED API key must be registered and available (free registration at fred.stlouisfed.org)
- Python 3.11 or higher must be installed
- Internet connectivity must be available for FRED, yfinance, and Forex Factory requests

---

## 3. Functional Requirements

### 3.1 Project Configuration

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-01 | The system SHALL load the FRED API key exclusively from an environment variable named `FRED_API_KEY`. | MUST | Given `FRED_API_KEY` is set in the environment, when the system starts, then FRED data is fetched successfully without the key appearing in any source file. |
| FR-1-02 | The system SHALL load the Telegram bot token exclusively from an environment variable named `TELEGRAM_TOKEN`. | MUST | Given `TELEGRAM_TOKEN` is set in the environment, when the configuration module is loaded, then the token value is available to the application without appearing in any source file. |
| FR-1-03 | The system SHALL load the Telegram target chat ID exclusively from an environment variable named `TELEGRAM_CHAT_ID`. | MUST | Given `TELEGRAM_CHAT_ID` is set in the environment, when the configuration module is loaded, then the chat ID value is available to the application without appearing in any source file. |
| FR-1-04 | The system SHALL define the USDJPY symbol identifier as a configuration constant. | MUST | Given the configuration module is loaded, when the symbol constant is accessed, then it returns the string `"USDJPY"`. |
| FR-1-05 | The system SHALL define the list of active timeframes as a configuration constant, containing M15, M30, H1, H4, and D. | MUST | Given the configuration module is loaded, when the timeframes constant is accessed, then all five timeframe identifiers are present. |
| FR-1-06 | The system SHALL define the scheduler evaluation offset as a configuration constant representing seconds after candle close. | MUST | Given the configuration module is loaded, when the eval offset constant is accessed, then it returns 120 (representing 2 minutes). |
| FR-1-07 | The system SHALL define the news buffer duration as a configuration constant representing the number of minutes before a high-impact event that triggers the news-imminent flag. | MUST | Given the configuration module is loaded, when the news buffer constant is accessed, then it returns 30 (representing 30 minutes). |
| FR-1-08 | The system SHALL define the path to the database file as a configuration constant. | MUST | Given the configuration module is loaded, when the database path constant is accessed, then it returns a valid relative or absolute path to the `.db` file location. |

### 3.2 MT5 Data Feed

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-09 | The system SHALL establish a connection to the locally running trading terminal on application startup. | MUST | Given the MT5 terminal is running, when the application starts, then GET /api/status returns `"mt5_connected": true`. |
| FR-1-10 | The system SHALL verify the terminal connection state before each OHLCV data fetch. | MUST | Given the MT5 terminal disconnects mid-session, when the next scheduled data fetch occurs, then the system detects the disconnection without crashing. |
| FR-1-11 | The system SHALL fetch OHLCV bar data for USDJPY on the M15 timeframe. | MUST | Given a connected terminal, when M15 OHLCV data is requested, then a structured data collection is returned containing time, open, high, low, close, and volume columns. |
| FR-1-12 | The system SHALL fetch OHLCV bar data for USDJPY on the M30 timeframe. | MUST | Given a connected terminal, when M30 OHLCV data is requested, then a structured data collection is returned containing time, open, high, low, close, and volume columns. |
| FR-1-13 | The system SHALL fetch OHLCV bar data for USDJPY on the H1 timeframe. | MUST | Given a connected terminal, when H1 OHLCV data is requested, then a structured data collection is returned containing time, open, high, low, close, and volume columns with at least 200 bars. |
| FR-1-14 | The system SHALL fetch OHLCV bar data for USDJPY on the H4 timeframe. | MUST | Given a connected terminal, when H4 OHLCV data is requested, then a structured data collection is returned containing time, open, high, low, close, and volume columns with at least 200 bars. |
| FR-1-15 | The system SHALL fetch OHLCV bar data for USDJPY on the Daily timeframe. | MUST | Given a connected terminal, when Daily OHLCV data is requested, then a structured data collection is returned containing time, open, high, low, close, and volume columns with at least 200 bars. |
| FR-1-16 | The system SHALL return OHLCV data with consistent, standardised column names across all timeframes. | MUST | Given OHLCV data from any timeframe, when the column names are inspected, then they are identical across all timeframes. |
| FR-1-17 | The system SHALL log a warning when the trading terminal is not reachable. | MUST | Given the MT5 terminal is closed, when a connection or data fetch is attempted, then a warning-level log entry is produced identifying MT5 as unavailable. |
| FR-1-18 | The system SHALL continue operating without crashing when the trading terminal is not reachable. | MUST | Given the MT5 terminal is closed before or during system operation, when the next data fetch cycle runs, then the application process does not terminate. |
| FR-1-19 | The system SHALL expose a function that returns the next candle close time in UTC for a specified timeframe. | MUST | Given a valid timeframe identifier (e.g. H1), when the next close time function is called, then a UTC datetime is returned representing the time the next candle will close on that timeframe. |

### 3.3 FRED API Data Feed

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-20 | The system SHALL fetch the US 10-Year Treasury Yield from the FRED API using series DGS10. | MUST | Given a valid FRED API key, when the US 10Y yield is requested, then a float representing the yield percentage is returned. |
| FR-1-21 | The system SHALL fetch the Effective Federal Funds Rate from the FRED API using series DFF. | MUST | Given a valid FRED API key, when the Fed Funds Rate is requested, then a float representing the rate percentage is returned. |
| FR-1-22 | The system SHALL cache the US 10-Year Treasury Yield and not re-fetch from FRED within a 4-hour window. | MUST | Given the US 10Y yield was fetched less than 4 hours ago, when the yield is requested again, then the cached value is returned and no FRED API call is made. |
| FR-1-23 | The system SHALL cache the Federal Funds Rate and not re-fetch from FRED within a 24-hour window. | MUST | Given the Fed Funds Rate was fetched less than 24 hours ago, when the rate is requested again, then the cached value is returned and no FRED API call is made. |
| FR-1-24 | The system SHALL return the last successfully cached FRED value if the FRED API is temporarily unavailable. | MUST | Given the FRED API returns a network error or timeout, when yield or rate data is requested, then the last successfully cached value is returned. |
| FR-1-25 | The system SHALL log an error when a FRED API request fails. | MUST | Given the FRED API is unreachable, when a data fetch is attempted, then an error-level log entry is produced identifying FRED as the failing source. |

### 3.4 Market Data Feed (yfinance)

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-26 | The system SHALL fetch the most recent daily close of the US Dollar Index (DXY). | MUST | Given internet connectivity, when DXY data is requested, then a float representing the most recent daily close value is returned. |
| FR-1-27 | The system SHALL fetch the latest value of the CBOE Volatility Index (VIX). | MUST | Given internet connectivity, when VIX data is requested, then a float representing the current or most recent VIX level is returned. |
| FR-1-28 | The system SHALL cache DXY data and not re-fetch within a 4-hour window. | MUST | Given DXY data was fetched less than 4 hours ago, when DXY is requested again, then the cached value is returned and no network call is made. |
| FR-1-29 | The system SHALL cache VIX data and not re-fetch within a 4-hour window. | MUST | Given VIX data was fetched less than 4 hours ago, when VIX is requested again, then the cached value is returned and no network call is made. |
| FR-1-30 | The system SHALL return the last successfully cached value if the market data provider is temporarily unavailable. | MUST | Given the market data provider returns an error, when DXY or VIX is requested, then the last successfully cached value is returned. |
| FR-1-31 | The system SHALL log an error when a market data request fails. | MUST | Given the market data provider is unreachable, when a fetch is attempted, then an error-level log entry is produced identifying market data as the failing source. |

### 3.5 Economic Calendar Feed

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-32 | The system SHALL retrieve the Forex Factory economic calendar from its public iCal feed. | MUST | Given internet connectivity, when the calendar feed is fetched, then a structured list of calendar events is produced. |
| FR-1-33 | The system SHALL parse each calendar event to extract at minimum: event name, scheduled UTC datetime, and impact level. | MUST | Given a successfully fetched calendar, when individual events are inspected, then each contains name (string), datetime (UTC), and impact (string or enum). |
| FR-1-34 | The system SHALL filter calendar events to retain only high-impact events relevant to USDJPY. | MUST | Given a parsed calendar containing mixed-impact events, when the filtered list is returned, then it contains only events of these types: FOMC decisions, BoJ decisions, US Non-Farm Payrolls, US CPI, US PCE, BoJ Governor speeches, US 10-Year Bond Auction, Tokyo CPI. |
| FR-1-35 | The system SHALL cache the parsed calendar for 24 hours from the time of last successful fetch. | MUST | Given the calendar was successfully fetched, when the same calendar is requested again within 24 hours, then the cached data is returned and no network call is made. |
| FR-1-36 | The system SHALL trigger a calendar refresh daily at 00:01 UTC. | MUST | Given the scheduler is running, when the clock reaches 00:01 UTC, then the system attempts a fresh calendar fetch. |
| FR-1-37 | The system SHALL return the last successfully cached calendar if the iCal feed is temporarily unavailable. | MUST | Given the iCal feed returns an error or timeout, when calendar data is requested, then the last cached calendar is returned. |
| FR-1-38 | The system SHALL log an error when the calendar feed fetch fails. | MUST | Given the iCal feed is unreachable, when a fetch is attempted, then an error-level log entry is produced identifying the calendar feed as the failing source. |
| FR-1-39 | The system SHALL expose a function that returns `true` if any high-impact event is scheduled within the next 30 minutes in UTC. | MUST | Given a high-impact event is scheduled 25 minutes from the current UTC time, when the news-imminent function is called, then it returns `true`. |
| FR-1-40 | The system SHALL expose a function that returns `false` if no high-impact event is scheduled within the next 30 minutes in UTC. | MUST | Given no high-impact event is scheduled within the next 30 minutes, when the news-imminent function is called, then it returns `false`. |
| FR-1-41 | The system SHALL expose a function that returns a list of upcoming high-impact events in ascending UTC datetime order. | MUST | Given the calendar contains multiple future high-impact events, when the upcoming events function is called requesting 5 events, then up to 5 events are returned sorted by scheduled datetime ascending. |

### 3.6 Persistent Data Store

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-42 | The system SHALL automatically create the database file on first run if it does not already exist. | MUST | Given no database file exists at the configured path, when the application starts for the first time, then a database file is created at the configured location. |
| FR-1-43 | The system SHALL automatically create the `signals` table on first run if it does not exist. | MUST | Given a newly created database, when the signals table is queried, then it exists and contains the following columns: id, timestamp, strategy_id, strategy_name, status, direction, entry, sl, tp1, tp2, tp3, rrr, confidence, probability, timeframes, reasons_for, reasons_against, verdict_summary, outcome. |
| FR-1-44 | The system SHALL automatically create the `market_context` table on first run if it does not exist. | MUST | Given a newly created database, when the market_context table is queried, then it exists and contains the following columns: id, timestamp, usdjpy_price, us10y, dxy, vix, fed_rate, boj_rate, next_event, next_event_time. |
| FR-1-45 | The system SHALL write a new market context snapshot to the `market_context` table after each successful data refresh. | MUST | Given all data sources return valid data, when the scheduled refresh job completes, then a new row is present in the market_context table with the current timestamp. |
| FR-1-46 | The system SHALL expose a function to retrieve the most recently written market context record. | MUST | Given one or more rows exist in the market_context table, when the latest-context function is called, then the row with the most recent timestamp is returned. |
| FR-1-47 | The system SHALL expose a function to insert a new signal record into the `signals` table. | MUST | Given a valid signal data object, when the insert-signal function is called, then a new row is written to the signals table and the new record's ID is returned. |
| FR-1-48 | The system SHALL expose a function to retrieve all signal records from the `signals` table in descending timestamp order. | MUST | Given the signals table contains multiple rows, when the get-all-signals function is called, then all rows are returned sorted by timestamp descending. |
| FR-1-49 | The system SHALL expose a function to retrieve a single signal record by its ID. | MUST | Given a valid signal ID that exists in the database, when the get-signal-by-id function is called, then the matching record is returned. |
| FR-1-50 | The system SHALL return null or an equivalent empty result when get-signal-by-id is called with an ID that does not exist. | MUST | Given an ID that does not correspond to any signal row, when get-signal-by-id is called, then null or an empty result is returned without raising an exception. |

### 3.7 REST API Server

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-51 | The system SHALL start an HTTP server bound to localhost on application startup. | MUST | Given the application is started, when an HTTP GET request is sent to localhost on the configured port, then a response is received. |
| FR-1-52 | The system SHALL allow cross-origin requests from localhost browser origins. | MUST | Given a browser page on localhost makes a cross-origin API request, when the browser inspects the response, then the appropriate CORS headers are present and the request is not blocked. |
| FR-1-53 | The system SHALL format all API responses using a consistent JSON envelope with the fields `success`, `data`, and `error`. | MUST | Given any registered API endpoint is called, when the response body is parsed, then it contains exactly: `success` (boolean), `data` (object or array), `error` (string or null). |
| FR-1-54 | The system SHALL respond to `GET /api/status` with the MT5 connection state. | MUST | Given the system is running, when `GET /api/status` is called, then the response `data` contains `mt5_connected` as a boolean. |
| FR-1-55 | The system SHALL respond to `GET /api/status` with the timestamp of the last successful MT5 data fetch. | MUST | Given at least one successful MT5 fetch has occurred, when `GET /api/status` is called, then `last_mt5_fetch` in the response is a non-null UTC datetime string. |
| FR-1-56 | The system SHALL respond to `GET /api/status` with the timestamp of the last successful FRED data fetch. | MUST | Given at least one successful FRED fetch has occurred, when `GET /api/status` is called, then `last_fred_fetch` in the response is a non-null UTC datetime string. |
| FR-1-57 | The system SHALL respond to `GET /api/status` with the timestamp of the last successful market data fetch. | MUST | Given at least one successful market data fetch has occurred, when `GET /api/status` is called, then `last_market_fetch` in the response is a non-null UTC datetime string. |
| FR-1-58 | The system SHALL respond to `GET /api/status` with the timestamp of the last successful calendar fetch. | MUST | Given at least one successful calendar fetch has occurred, when `GET /api/status` is called, then `last_calendar_fetch` in the response is a non-null UTC datetime string. |
| FR-1-59 | The system SHALL respond to `GET /api/status` with a boolean indicating whether the database connection is operational. | MUST | Given the database file exists and is accessible, when `GET /api/status` is called, then `db_connected` in the response is `true`. |
| FR-1-60 | The system SHALL respond to `GET /api/dashboard` with the current live USDJPY price. | MUST | Given MT5 is connected and OHLCV data has been fetched, when `GET /api/dashboard` is called, then the response `data` contains `usdjpy_price` as a float. |
| FR-1-61 | The system SHALL respond to `GET /api/dashboard` with the current DXY value. | MUST | Given DXY data has been fetched, when `GET /api/dashboard` is called, then the response `data` contains `dxy` as a float. |
| FR-1-62 | The system SHALL respond to `GET /api/dashboard` with the current US 10-Year Treasury Yield. | MUST | Given FRED data has been fetched, when `GET /api/dashboard` is called, then the response `data` contains `us10y` as a float. |
| FR-1-63 | The system SHALL respond to `GET /api/dashboard` with the current VIX value. | MUST | Given VIX data has been fetched, when `GET /api/dashboard` is called, then the response `data` contains `vix` as a float. |
| FR-1-64 | The system SHALL respond to `GET /api/dashboard` with the current Federal Funds Rate. | MUST | Given FRED data has been fetched, when `GET /api/dashboard` is called, then the response `data` contains `fed_rate` as a float. |
| FR-1-65 | The system SHALL respond to `GET /api/dashboard` with the name and UTC datetime of the next high-impact calendar event. | MUST | Given the calendar has been populated, when `GET /api/dashboard` is called, then the response `data` contains `next_event` (string) and `next_event_time` (UTC datetime string). |
| FR-1-66 | The system SHALL respond to `GET /api/strategies` with an empty list and `success: true`. | MUST | Given the system is in Phase 1 with no strategy engine, when `GET /api/strategies` is called, then the response is `{"success": true, "data": [], "error": null}`. |
| FR-1-67 | The system SHALL respond to `GET /api/strategy/{id}` with a 404 HTTP status and `success: false`. | MUST | Given the system is in Phase 1, when `GET /api/strategy/1` is called, then the HTTP status code is 404 and the response body contains `"success": false`. |
| FR-1-68 | The system SHALL respond to `GET /api/history` with an empty list and `success: true` when no signals exist. | MUST | Given the signals table is empty, when `GET /api/history` is called, then the response is `{"success": true, "data": [], "error": null}`. |

### 3.8 Background Scheduler

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-1-69 | The system SHALL start the background scheduler automatically on application startup. | MUST | Given the application has been running for 1 minute, when application logs are inspected, then entries are present confirming the scheduler is active. |
| FR-1-70 | The system SHALL operate the scheduler in UTC timezone regardless of the host machine's local timezone setting. | MUST | Given a host machine configured to JST (UTC+9), when scheduled jobs fire, then their execution timestamps correspond to the configured UTC times, not local times. |
| FR-1-71 | The system SHALL register a job that fires at 2 minutes past every hour (HH:02:00 UTC) to trigger the strategy evaluation stub. | MUST | Given the scheduler is running, when the clock reaches any HH:02:00 UTC, then a log entry confirms the H1 hourly job executed. |
| FR-1-72 | The system SHALL register a job that fires at 00:02, 04:02, 08:02, 12:02, 16:02, and 20:02 UTC daily to refresh H4-timeframe data. | MUST | Given the scheduler is running, when the clock reaches any of the six H4 job times, then a log entry confirms the H4 refresh job executed. |
| FR-1-73 | The system SHALL register a job that fires once daily at 00:05 UTC to refresh FRED data, market data, and the economic calendar. | MUST | Given the scheduler is running, when the clock reaches 00:05 UTC, then a log entry confirms the daily data refresh job executed. |
| FR-1-74 | The system SHALL log a warning and continue operating if a scheduled job throws an exception. | MUST | Given a scheduled job raises an exception during execution, when the next scheduled job time arrives, then the scheduler continues to execute subsequent jobs without the application exiting. |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-01 | The system SHALL start and be ready to serve HTTP requests within 10 seconds of `python main.py` being executed. | MUST | Given the application is launched on the target Windows machine, when 10 seconds have elapsed, then `GET /api/status` returns an HTTP 200 response. |
| NFR-1-02 | The system SHALL respond to any API endpoint within 500 milliseconds when all data is available in cache. | MUST | Given all data sources have been previously fetched and are cached, when any API endpoint is called, then the response is received within 500ms as measured at the client. |
| NFR-1-03 | The system SHALL complete an MT5 OHLCV fetch for all five timeframes within 5 seconds. | MUST | Given the MT5 terminal is connected, when OHLCV data is requested for all five timeframes in a single call sequence, then all data is returned within 5 seconds. |
| NFR-1-04 | The system SHALL complete a full market context refresh (FRED + yfinance combined) within 20 seconds under normal network conditions. | SHOULD | Given network connectivity is available, when the daily refresh job fires, then all FRED and yfinance values are updated within 20 seconds of the job starting. |
| NFR-1-05 | The system SHALL complete an economic calendar fetch and parse within 15 seconds under normal network conditions. | SHOULD | Given the Forex Factory iCal feed is accessible, when the calendar refresh job fires, then the calendar is parsed and cached within 15 seconds. |

### 4.2 Reliability

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-06 | The system SHALL not terminate when the MT5 terminal is closed while the system is running. | MUST | Given the application is running and MT5 is subsequently closed, when the next scheduled data fetch cycle executes, then the application process remains running. |
| NFR-1-07 | The system SHALL not terminate when the FRED API is unreachable. | MUST | Given the FRED API returns a connection error or HTTP 5xx response, when a FRED fetch is attempted, then the application process remains running and the error is logged. |
| NFR-1-08 | The system SHALL not terminate when the Forex Factory iCal feed is unreachable. | MUST | Given the iCal feed URL returns a connection error or timeout, when the calendar refresh is attempted, then the application process remains running and the error is logged. |
| NFR-1-09 | The system SHALL not terminate when the yfinance market data provider is unreachable. | MUST | Given yfinance returns an error, when DXY or VIX is requested, then the application process remains running and the error is logged. |
| NFR-1-10 | The system SHALL produce a log entry for every error that includes a UTC timestamp, the component name, and the error description. | MUST | Given any error occurs in any component, when the application log is inspected, then the corresponding entry contains: timestamp (UTC), component identifier, error message. |

### 4.3 Data Integrity

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-11 | The system SHALL store all timestamps written to the database in UTC. | MUST | Given any row is written to the database with a timestamp field, when the raw value is read from the database, then it represents a UTC datetime. |
| NFR-1-12 | The system SHALL not insert a duplicate market context row if a row with the same timestamp already exists. | SHOULD | Given a market_context row with timestamp T already exists, when the system attempts to insert another row with the same timestamp T, then no duplicate row is created. |
| NFR-1-13 | The system SHALL return numeric OHLCV values that match the values visible in the MT5 terminal chart for the same bar. | MUST | Given a specific H1 bar is visible in the MT5 terminal, when the same bar is fetched via the data feed, then the open, high, low, and close values are identical to the terminal display. |

### 4.4 Maintainability

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-14 | The system SHALL isolate all database read and write operations within a single dedicated data-access module. | MUST | Given a review of all source files excluding the data-access module, when those files are searched for database query syntax, then none is found. |
| NFR-1-15 | The system SHALL isolate all application configuration constants within a single configuration module. | MUST | Given a review of all source files excluding the configuration module, when those files are searched for hardcoded operational values (symbol strings, timeframe values, numeric thresholds, cache durations), then none are found outside the configuration module. |
| NFR-1-16 | The system SHALL produce structured log output that distinguishes between INFO, WARNING, and ERROR severity levels. | MUST | Given the system is running and performing normal operations, when the application log is inspected, then entries are labelled with distinct severity levels. |

### 4.5 Security

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-17 | The system SHALL not include any API key, token, or credential value in any source file committed to version control. | MUST | Given all source files in the repository are reviewed and searched for known credential patterns (strings matching API key formats, token formats), then no credential values are present. |
| NFR-1-18 | The system SHALL read all credentials from environment variables at runtime. | MUST | Given credentials are removed from environment variables, when the application starts, then it fails to authenticate to external services (confirming no hardcoded fallback exists). |
| NFR-1-19 | The system SHALL not return any credential or API key value in any API endpoint response. | MUST | Given all five API endpoints are called, when each response body is inspected, then no credential values, API keys, or Telegram tokens are present in any response field. |
| NFR-1-20 | The system SHALL not log credential values at any severity level. | MUST | Given the application runs through at least one full scheduler cycle, when the application log is inspected in full, then no API key values, Telegram tokens, or credential strings appear. |

### 4.6 Compatibility

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| NFR-1-21 | The system SHALL run without errors on Windows 10 (build 19041+) and Windows 11. | MUST | Given the system is installed on Windows 11, when `python main.py` is executed, then the application starts without platform-specific exceptions. |
| NFR-1-22 | The system SHALL be compatible with Python 3.11 and Python 3.12. | MUST | Given Python 3.11 is the active interpreter, when the application is started, then no version-incompatibility errors or deprecation warnings from Python version differences are produced. |
| NFR-1-23 | The system SHALL interface with MetaTrader 5 terminal build 3000 or higher. | SHOULD | Given MT5 terminal build 3000+ is running, when the system connects, then OHLCV data is successfully retrieved for all five timeframes. |

---

## 5. Data Specifications

### 5.1 Data Models

#### Table: `signals`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTO INCREMENT, NOT NULL | Unique row identifier |
| timestamp | DATETIME | NOT NULL | UTC datetime when the signal was generated |
| strategy_id | INTEGER | NOT NULL, CHECK (1–20) | Strategy number from 1 to 20 |
| strategy_name | TEXT | NOT NULL | Human-readable strategy name |
| status | TEXT | NOT NULL, CHECK IN ('VALID_TRADE','WAIT_FOR_LEVELS','NO_TRADE') | Strategy evaluation verdict |
| direction | TEXT | NULLABLE, CHECK IN ('BUY','SELL', NULL) | Trade direction, null for NO_TRADE |
| entry | REAL | NULLABLE | Entry price in USDJPY pips |
| sl | REAL | NULLABLE | Stop loss price |
| tp1 | REAL | NULLABLE | Take profit 1 price |
| tp2 | REAL | NULLABLE | Take profit 2 price |
| tp3 | REAL | NULLABLE | Take profit 3 price (optional) |
| rrr | REAL | NULLABLE | Risk-reward ratio (e.g. 2.5) |
| confidence | INTEGER | NULLABLE, CHECK (0–100) | Confidence score from debate engine |
| probability | INTEGER | NULLABLE, CHECK (0–100) | Probability score from debate engine |
| timeframes | TEXT | NULLABLE | Slash-separated list e.g. "H1/H4/D" |
| reasons_for | TEXT | NULLABLE | JSON array of supporting reason strings |
| reasons_against | TEXT | NULLABLE | JSON array of opposing reason strings |
| verdict_summary | TEXT | NULLABLE | Narrative description of the final verdict |
| outcome | TEXT | NULLABLE, CHECK IN ('WIN','LOSS','PENDING', NULL) | Trade outcome — manually updated post-trade |

#### Table: `market_context`

| Column | Type | Constraints | Description |
|---|---|---|---|
| id | INTEGER | PRIMARY KEY, AUTO INCREMENT, NOT NULL | Unique row identifier |
| timestamp | DATETIME | NOT NULL | UTC datetime of this market snapshot |
| usdjpy_price | REAL | NULLABLE | USDJPY last price at snapshot time |
| us10y | REAL | NULLABLE | US 10-Year Treasury Yield percentage |
| dxy | REAL | NULLABLE | US Dollar Index value |
| vix | REAL | NULLABLE | CBOE VIX index value |
| fed_rate | REAL | NULLABLE | Effective Federal Funds Rate percentage |
| boj_rate | REAL | NULLABLE | Bank of Japan policy rate percentage (not wired in Phase 1) |
| next_event | TEXT | NULLABLE | Name of the next high-impact calendar event |
| next_event_time | DATETIME | NULLABLE | UTC datetime of the next high-impact event |

#### Calendar Event (in-memory)

| Field | Type | Constraints | Description |
|---|---|---|---|
| name | string | NOT NULL | Event name as returned from Forex Factory feed |
| event_time | datetime | NOT NULL, UTC | Scheduled UTC datetime of the event |
| impact | string | NOT NULL | Impact level string (e.g. "High") |

### 5.2 Data Flows

| Flow | Trigger | Source | Destination | Unavailability Handling |
|---|---|---|---|---|
| USDJPY OHLCV fetch | H1 scheduler job (HH:02 UTC) | MT5 terminal (local) | In-memory cache, consumed by API endpoints | Log warning, return last cached data, skip DB write |
| FRED yield + rate fetch | Daily job (00:05 UTC) or cache expiry | FRED REST API | In-memory cache | Log error, return last cached value |
| DXY + VIX fetch | Daily job (00:05 UTC) or cache expiry | yfinance | In-memory cache | Log error, return last cached value |
| Calendar fetch | Daily job (00:01 UTC) or cache expiry | Forex Factory iCal | In-memory calendar cache | Log error, return last cached calendar |
| Market context write | After each full data refresh | In-memory cache (all sources) | `market_context` table in database | Log error, skip DB write |
| API response assembly | HTTP GET request from client | In-memory cache + database | HTTP response body (JSON) | Serve cached/partial data, report null fields |

### 5.3 Interface Contracts

#### MT5 Terminal

| Attribute | Value |
|---|---|
| Interface Name | MetaTrader5 Python Package |
| Direction | Inbound (system reads from MT5) |
| Data Format | Python DataFrame: columns `time` (datetime), `open` (float), `high` (float), `low` (float), `close` (float), `tick_volume` (int) |
| Frequency | On-demand; called each H1 close and H4 close |
| Authentication | Session-based; terminal must be running locally; no login credentials passed |
| Rate Limits | None documented; calls are synchronous and local |
| Error Handling | If `mt5.initialize()` returns False, log warning, mark mt5_connected=false, return None from fetch functions |

#### FRED REST API

| Attribute | Value |
|---|---|
| Interface Name | FRED API v1 |
| Direction | Inbound |
| Data Format | JSON response containing series observation records with `date` (string) and `value` (string/float) fields |
| Frequency | Maximum once per 4 hours for DGS10; once per 24 hours for DFF |
| Authentication | API key passed as query parameter `api_key`; sourced from environment variable |
| Rate Limits | 120 requests per minute on free tier; caching policy in this spec operates well within that limit |
| Error Handling | On HTTP error or timeout: log error, return last cached float value; if no cache exists, return None |

#### yfinance Market Data Provider

| Attribute | Value |
|---|---|
| Interface Name | yfinance (Yahoo Finance) |
| Direction | Inbound |
| Data Format | pandas DataFrame with date index and `Close` column (float); latest row used |
| Frequency | Maximum once per 4 hours |
| Authentication | None required |
| Rate Limits | Not formally published; usage well within limits given 4-hour cache |
| Error Handling | On exception: log error, return last cached float value; if no cache exists, return None |

#### Forex Factory iCal Feed

| Attribute | Value |
|---|---|
| Interface Name | Forex Factory iCal (RFC 5545) |
| Direction | Inbound |
| Data Format | iCalendar format; each VEVENT contains SUMMARY (event name), DTSTART (UTC datetime), and custom properties for impact level |
| Frequency | Once daily at 00:01 UTC; cached for 24 hours |
| Authentication | None required (public feed) |
| Rate Limits | Not published; once-daily access pattern poses no risk |
| Error Handling | On network error or parse failure: log error, return last cached calendar; if no cache exists, return empty list |

---

## 6. Interface Specifications

### 6.1 Internal API Contracts

#### `GET /api/status`

- **Purpose:** Returns the current health state of all system components.
- **Request parameters:** None
- **Response schema:**

| Field | Type | Description |
|---|---|---|
| success | boolean | Always `true` for this endpoint |
| error | null | Always null for this endpoint |
| data.mt5_connected | boolean | Whether MT5 terminal is currently reachable |
| data.last_mt5_fetch | string \| null | ISO 8601 UTC datetime of last successful MT5 fetch |
| data.last_fred_fetch | string \| null | ISO 8601 UTC datetime of last successful FRED fetch |
| data.last_market_fetch | string \| null | ISO 8601 UTC datetime of last successful yfinance fetch |
| data.last_calendar_fetch | string \| null | ISO 8601 UTC datetime of last successful calendar fetch |
| data.db_connected | boolean | Whether the database is accessible |

- **Error responses:** HTTP 500 with `success: false, error: "Internal server error"` if the status check itself throws.
- **Example response:**
```json
{
  "success": true,
  "data": {
    "mt5_connected": true,
    "last_mt5_fetch": "2026-04-24T10:02:05Z",
    "last_fred_fetch": "2026-04-24T00:05:12Z",
    "last_market_fetch": "2026-04-24T00:05:18Z",
    "last_calendar_fetch": "2026-04-24T00:01:03Z",
    "db_connected": true
  },
  "error": null
}
```

#### `GET /api/dashboard`

- **Purpose:** Returns the current live market context for display.
- **Request parameters:** None
- **Response schema:**

| Field | Type | Description |
|---|---|---|
| success | boolean | `true` if data was assembled successfully |
| error | string \| null | Error description if success is false |
| data.usdjpy_price | float \| null | Most recent USDJPY close price from MT5 |
| data.dxy | float \| null | Most recent DXY daily close |
| data.us10y | float \| null | US 10-Year Treasury Yield percentage |
| data.vix | float \| null | VIX index value |
| data.fed_rate | float \| null | Effective Federal Funds Rate percentage |
| data.next_event | string \| null | Name of the next high-impact calendar event |
| data.next_event_time | string \| null | ISO 8601 UTC datetime of next high-impact event |

- **Error responses:** HTTP 500 with `success: false` if the context assembly fails entirely.
- **Example response:**
```json
{
  "success": true,
  "data": {
    "usdjpy_price": 154.823,
    "dxy": 105.42,
    "us10y": 4.38,
    "vix": 13.21,
    "fed_rate": 5.33,
    "next_event": "US Non-Farm Payrolls",
    "next_event_time": "2026-05-02T12:30:00Z"
  },
  "error": null
}
```

#### `GET /api/strategies`

- **Purpose:** Returns all strategy evaluation results (stub in Phase 1).
- **Request parameters:** None
- **Response:** `{"success": true, "data": [], "error": null}` — always empty list in Phase 1.

#### `GET /api/strategy/{id}`

- **Purpose:** Returns full debate detail for a single strategy (stub in Phase 1).
- **Request parameters:** `id` (integer, 1–20, path parameter)
- **Response:** HTTP 404, `{"success": false, "data": null, "error": "Strategy engine not available in Phase 1"}`

#### `GET /api/history`

- **Purpose:** Returns paginated signal log from the database.
- **Request parameters:** None (pagination parameters added in Phase 4)
- **Response:** `{"success": true, "data": [], "error": null}` — always empty list in Phase 1 as no signals are written.

### 6.2 External System Interfaces

Covered in full in Section 5.3 Interface Contracts.

### 6.3 User Interface Specifications

This section is not applicable to Phase 1. No frontend pages are built in this phase. All interaction with the Phase 1 system is via direct HTTP calls to the REST API or via application logs.

---

## 7. Constraints

| Constraint | Statement |
|---|---|
| Platform | The system runs on Windows 10 (build 19041+) or Windows 11 only. The MT5 Python package does not support macOS or Linux. |
| Language | The backend is implemented in Python 3.11 or higher. |
| MT5 Availability | The MetaTrader 5 terminal must be installed, running, and logged into an account with USDJPY available before market data can be retrieved. The Python process and the MT5 terminal must run on the same machine. |
| MT5 Credentials | No MT5 account credentials (login, password, server) are stored in code or configuration. The terminal session must already be authenticated before the system connects. |
| FRED API | A FRED API key is required. It is freely available but requires registration at fred.stlouisfed.org. The key must be set as an environment variable before startup. |
| Database | The persistent store is a single file-based database. No database server, network database, or cloud storage is used. |
| Single Writer | The database has a single writer (the Python application process). No concurrent writes from multiple processes. |
| No Strategy Logic | Phase 1 contains no strategy evaluation, indicator computation, or trade signal generation. The strategy evaluation scheduler job is a stub log statement only. |
| No Frontend | Phase 1 contains no HTML, CSS, or JavaScript. |
| No Telegram | Phase 1 does not send any Telegram messages. The Telegram credentials are loaded into config but the notification module is not invoked. |
| No Paid Services | No external services requiring payment beyond the agreed stack (FRED is free, yfinance is free, Forex Factory iCal is free) are used. |
| BoJ Rate Source | The `boj_rate` field in the `market_context` schema is defined and reserved in Phase 1 but its data source is not wired up. The field will store NULL until a source is connected in a future phase. |

---

## 8. Assumptions

1. It is assumed that the Forex Factory iCal feed remains a free, publicly accessible URL without authentication. If this is incorrect, the calendar feed implementation must be replaced with an alternative calendar source.

2. It is assumed that the yfinance library continues to provide DXY (ticker: `DX-Y.NYB`) and VIX (ticker: `^VIX`) data without authentication. If Yahoo Finance removes or restricts access to these tickers, an alternative market data provider must be identified.

3. It is assumed that the FRED API free tier permits at least 10 requests per day without rate-limiting errors. If FRED tightens its rate limit below this, the caching strategy may need adjustment.

4. It is assumed that USDJPY is available as a symbol in the running MT5 terminal. If the terminal is connected to a broker that does not offer USDJPY or uses a different symbol name, the `MT5_SYMBOL` configuration constant must be updated.

5. It is assumed that the host Windows machine has a stable internet connection available for FRED, yfinance, and Forex Factory requests. If the machine operates in an offline environment, FRED and yfinance data will be unavailable and the system will operate on cached-or-null values only.

6. It is assumed that Python 3.11 or higher is installed and available as the default `python` or `python3` interpreter. If the machine has an older Python version as default, the interpreter must be specified explicitly.

7. It is assumed that all five API endpoints defined in this specification are sufficient for Phase 3 (Frontend) to build against. If the frontend requires additional endpoints, they will be added in Phase 3.

---

## 9. Risks and Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-1-01 | MT5 terminal is not running or crashes during system operation, causing all price data to be stale or unavailable | Medium | High | System logs a clear warning on each failed fetch; `/api/status` reflects `mt5_connected: false`; API endpoints return last cached values where available; system does not crash |
| RISK-1-02 | FRED API returns stale data (last observation is days old) due to weekends or public holidays | Medium | Low | FRED series DGS10 and DFF are only updated on US business days; cached values from the most recent business day are acceptable for macro context purposes; spec accepts this as valid behaviour |
| RISK-1-03 | Forex Factory iCal feed is offline or returns malformed data during the daily refresh | Medium | Medium | Calendar module retains the previous 24-hour cached calendar; news-imminent function continues to operate on stale-but-better-than-nothing data; error is logged clearly |
| RISK-1-04 | Scheduler fires at incorrect local times if host timezone is set to a non-UTC zone | Low | High | Scheduler is explicitly configured to UTC timezone; this must be tested by verifying job fire times against a UTC clock rather than local system clock |
| RISK-1-05 | Database file becomes corrupted or locked due to an unclean application shutdown | Low | High | Application uses proper connection lifecycle (open/close per operation or a persistent connection with WAL mode); no multi-process access; risk is low in single-user local context |
| RISK-1-06 | yfinance DXY or VIX data returns incorrect or null values due to market closure or provider issue | Medium | Low | DXY and VIX are macro context signals; stale values from the most recent trading session are acceptable; null handling in API responses returns null fields gracefully |
| RISK-1-07 | Python package versions in `requirements.txt` conflict or break on the target machine | Low | Medium | Pin all package versions in `requirements.txt` using `==` version specifiers after confirming a working install; include a `requirements.lock` or equivalent if the project grows in complexity |
| RISK-1-08 | FRED API key is accidentally committed to the repository | Low | High | Enforced by NFR-1-17: no credentials in source files; use a `.gitignore` entry for `.env` files; pre-commit check recommended |

---

## 10. Acceptance Criteria

The following criteria must all be true for Phase 1 to be considered complete. Each criterion is independently verifiable.

| ID | Acceptance Criterion |
|---|---|
| AC-1-01 | `python main.py` executed on the target Windows machine starts without any Python exception or error output, and the process remains running after 30 seconds. |
| AC-1-02 | With the MT5 terminal running, `GET /api/status` returns HTTP 200 with `"mt5_connected": true` in the response body. |
| AC-1-03 | With the MT5 terminal closed, `GET /api/status` returns HTTP 200 with `"mt5_connected": false`, and the application process continues running without termination. |
| AC-1-04 | `GET /api/dashboard` returns HTTP 200 containing non-null float values for `usdjpy_price`, `dxy`, `us10y`, `vix`, and `fed_rate`. |
| AC-1-05 | `GET /api/dashboard` returns a non-null `next_event` string and a valid `next_event_time` UTC datetime string representing an upcoming high-impact event. |
| AC-1-06 | A database file exists at the path defined in `config.py`, contains the `signals` table with all 19 defined columns, and contains the `market_context` table with all 9 defined columns. |
| AC-1-07 | At least one row exists in the `market_context` table after the system has been running for 5 minutes, confirming that the initial data refresh was persisted. |
| AC-1-08 | Application logs show a scheduler job entry firing at HH:02:00 UTC (within ±10 seconds) on an observed hour boundary, confirming the H1 scheduler job is registered and executing. |
| AC-1-09 | H1 and H4 OHLCV DataFrames returned from the MT5 data feed contain at least 200 rows and include `time`, `open`, `high`, `low`, `close`, and `tick_volume` columns. |
| AC-1-10 | The upcoming events function returns a list containing at least 5 high-impact events with correct names and UTC datetimes when the calendar is populated. |
| AC-1-11 | `GET /api/strategies` returns HTTP 200 with `{"success": true, "data": [], "error": null}`. |
| AC-1-12 | `GET /api/strategy/1` returns HTTP 404 with `"success": false` in the response body. |
| AC-1-13 | `GET /api/history` returns HTTP 200 with `{"success": true, "data": [], "error": null}`. |
| AC-1-14 | No source file in the repository contains a hardcoded FRED API key, Telegram token, or Telegram chat ID value. |
| AC-1-15 | All five API endpoint responses contain the `success`, `data`, and `error` fields at the top level of the JSON response body.  |

---

## 11. Traceability Matrix

| Acceptance Criterion | Functional Requirement(s) |
|---|---|
| AC-1-01 | FR-1-51, FR-1-69, NFR-1-01 |
| AC-1-02 | FR-1-09, FR-1-54 |
| AC-1-03 | FR-1-17, FR-1-18, NFR-1-06 |
| AC-1-04 | FR-1-60, FR-1-61, FR-1-62, FR-1-63, FR-1-64 |
| AC-1-05 | FR-1-65, FR-1-32, FR-1-33, FR-1-34 |
| AC-1-06 | FR-1-42, FR-1-43, FR-1-44 |
| AC-1-07 | FR-1-45 |
| AC-1-08 | FR-1-69, FR-1-70, FR-1-71 |
| AC-1-09 | FR-1-11, FR-1-13, FR-1-14, FR-1-16 |
| AC-1-10 | FR-1-41 |
| AC-1-11 | FR-1-66, FR-1-53 |
| AC-1-12 | FR-1-67, FR-1-53 |
| AC-1-13 | FR-1-68, FR-1-53 |
| AC-1-14 | FR-1-01, FR-1-02, FR-1-03, NFR-1-17, NFR-1-18 |
| AC-1-15 | FR-1-53 |

---

## 12. Open Questions

| ID | Question | Impact if Unresolved | Owner |
|---|---|---|---|
| OQ-1-01 | What is the specific public URL for the Forex Factory iCal feed? The feed is publicly accessible but the exact URL should be confirmed and pinned in configuration before implementation begins, as FF has historically changed it without notice. | Calendar feed will fail to fetch on first run | Developer |
| OQ-1-02 | The `market_context` table schema includes a `boj_rate` field but no data source for BoJ policy rate is defined for Phase 1. Should this field be populated with a hardcoded known value as a placeholder, or left as NULL? | NULL stored for all Phase 1 records; Phase 3 frontend must handle null gracefully | Developer |
| OQ-1-03 | Should the in-memory data cache survive an application restart, or is it acceptable to start with empty cache on each restart requiring a fresh data fetch on startup? The current spec assumes cache is rebuilt on startup. If cold-start time is a concern (e.g., FRED may be slow), cache persistence to disk may be needed. | Cold start could take up to 20 seconds before first dashboard response is fully populated | Developer |
| OQ-1-04 | What port number should the FastAPI/Uvicorn server bind to? The architecture document does not specify a port. Port 8000 is the Uvicorn default, but it should be set as a configuration constant and confirmed here to avoid conflicts with other running applications. | Frontend pages built in Phase 3 will have the wrong API base URL | Developer |

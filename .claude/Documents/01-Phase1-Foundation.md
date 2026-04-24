# Phase 1 — Foundation & Data Layer

**Phase:** 1 of 5  
**Goal:** Get the entire data pipeline working end-to-end, the database schema live, and the FastAPI server running and serving raw data to the browser.  
**Deliverable:** A running local server that connects to MT5, pulls USDJPY OHLCV and all supporting data, stores it, and exposes it via API endpoints. No strategy logic yet — pure infrastructure.

---

## What Gets Built in This Phase

### 1. Python Project Setup
- Create the full folder structure as defined in `system_architecture.md`
- Set up `requirements.txt` with all dependencies
- Create `config.py` with all configuration constants (timeframes, API keys, Telegram token, thresholds, timezone settings)
- No hardcoded values anywhere — everything referenced from config

### 2. MT5 Data Layer (`data/mt5_feed.py`)
- Connect to the already-running MT5 terminal using `mt5.initialize()` — no credentials
- Verify connection and log terminal info (broker name, account type — not credentials)
- Fetch OHLCV bars for USDJPY across all required timeframes: M15, M30, H1, H4, D
- Return clean pandas DataFrames with standardized column names
- Handle MT5 terminal not running gracefully (log warning, retry on next cycle)
- Include a utility to detect the current candle close time per timeframe

### 3. FRED API Data Layer (`data/fred_feed.py`)
- Connect using `fredapi` with a free FRED API key (obtained from fred.stlouisfed.org — free registration)
- Fetch US 10-Year Treasury Yield (series: DGS10)
- Fetch Effective Federal Funds Rate (series: DFF)
- Cache results locally to avoid redundant calls (refresh every 4 hours for yield, daily for Fed rate)
- Return latest values as simple floats

### 4. Market Data Layer (`data/market_feed.py`)
- Use `yfinance` to fetch DXY (ticker: DX-Y.NYB) daily close
- Use `yfinance` to fetch VIX (ticker: ^VIX) latest value
- These are macro context signals, not candle data — daily snapshot is sufficient
- Cache with 4-hour refresh

### 5. Economic Calendar (`data/calendar_feed.py`)
- Subscribe to Forex Factory iCal feed (public URL, no key required)
- Parse the iCal feed using `icalendar` library
- Filter for high-impact events relevant to USDJPY: FOMC, BoJ Decision, NFP, US CPI, US PCE, BoJ Governor speeches, US 10Y Auction, Tokyo CPI
- Store upcoming events with name, datetime (UTC), and impact level
- Expose: "is there a high-impact event within the next 2 hours?" as a boolean function — used by strategy engine as a filter
- Refresh daily at 00:01 UTC, cache for 24 hours

### 6. SQLite Database Setup (`db/schema.sql` + `db/signal_store.py`)
- Create the SQLite database file at `data/usdjpy_signals.db`
- Define and create both tables on first run:
  - `signals` — full trade signal log (see schema in system_architecture.md)
  - `market_context` — periodic market snapshot (USDJPY price, US10Y, DXY, VIX, next event)
- `signal_store.py` exposes clean read/write functions — no raw SQL outside this module
- DB is created automatically on first run if it does not exist

### 7. FastAPI Server Skeleton (`main.py` + `api/`)
- FastAPI app with Uvicorn runner
- CORS enabled for local frontend access
- Endpoints wired up (return placeholder/raw data at this stage):
  - `GET /api/dashboard` — returns live price + market context snapshot
  - `GET /api/strategies` — returns empty list (strategy engine not built yet)
  - `GET /api/strategy/{id}` — returns 404 placeholder
  - `GET /api/history` — returns signal log (empty at this stage)
  - `GET /api/status` — returns MT5 connection state, last data fetch times, DB status
- All responses use a consistent JSON envelope: `{ success: bool, data: {}, error: null }`

### 8. APScheduler Setup (`scheduler.py`)
- Initialize APScheduler with timezone set to UTC
- Register jobs (strategy engine jobs are empty stubs at this phase):
  - Every H1 close (fires at HH:02:00 UTC) → stub for strategy evaluation
  - Every H4 close (fires at 00:02, 04:02, 08:02, 12:02, 16:02, 20:02 UTC) → refresh H4 data
  - Daily at 00:05 UTC → refresh FRED, yfinance, calendar data
- Scheduler starts with the FastAPI server and runs in background

---

## Dependencies (requirements.txt entries for this phase)

```
fastapi
uvicorn
MetaTrader5
fredapi
yfinance
pandas
numpy
icalendar
requests
apscheduler
python-dotenv
```

---

## Configuration (`config.py` — key entries for this phase)

- `MT5_SYMBOL` = "USDJPY"
- `TIMEFRAMES` = list of MT5 timeframe constants (M15, M30, H1, H4, D1)
- `FRED_API_KEY` = loaded from environment variable
- `TELEGRAM_TOKEN` = loaded from environment variable
- `TELEGRAM_CHAT_ID` = loaded from environment variable
- `DB_PATH` = relative path to SQLite file
- `EVAL_OFFSET_SECONDS` = 120 (fire 2 minutes after candle close)
- `CALENDAR_REFRESH_HOUR` = 0 (midnight UTC)
- `NEWS_BUFFER_MINUTES` = 30 (flag news events within 30 min as risk factor)

---

## Phase 1 Success Criteria

By the end of Phase 1, the following must all be true:

1. `python main.py` starts the server without errors
2. MT5 terminal is running → `GET /api/status` shows `mt5_connected: true`
3. `GET /api/dashboard` returns a live USDJPY price, DXY, US10Y, VIX values, and next event
4. SQLite database file exists at `data/usdjpy_signals.db` with correct tables
5. Scheduler is running — logs show data refresh jobs firing at correct intervals
6. OHLCV data for H1 and H4 is fetchable and returns correct bar counts
7. Economic calendar shows at least the next 5 high-impact events with correct UTC times
8. If MT5 terminal is closed, system logs a warning but does not crash

---

## Known Constraints for This Phase

- FRED API requires a free account and API key — takes 5 minutes to register
- MT5 terminal must be running on the same Windows machine as the Python process
- yfinance DXY data is end-of-day only — this is acceptable for macro context (not candle data)
- Forex Factory iCal feed may occasionally be slow or offline — cache must protect against this
- SQLite is single-writer — no concurrency issues in single-user local setup

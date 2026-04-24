# Phase 1 — Foundation Implementation Plan

## Context

The USDJPY Smart Agent is a local, Windows-only, single-user trade intelligence system that monitors USDJPY across 20 strategies using a 4-agent debate framework. Phase 1 builds the entire infrastructure layer: data ingestion from MT5, FRED, yfinance, and Forex Factory; a SQLite signal store; a FastAPI REST API skeleton; and a UTC-synchronised APScheduler. All four subsequent phases (Strategy Engine, Frontend, Notifications, Automated Trading) depend on Phase 1 being complete and passing its 15 Acceptance Criteria.

The repository is **100% greenfield** — no code exists yet. Every file listed below must be created from scratch.

Source of truth: `.claude/Specs/Phase1-Foundation-Spec.md` (74 FRs, 23 NFRs, 15 ACs).

---

## Resolved Open Questions (from Spec Section 12)

| OQ | Decision |
|---|---|
| OQ-1-01 Forex Factory iCal URL | `https://www.forexfactory.com/ff_calendar_thisweek.ics` — store as `FOREX_FACTORY_ICAL_URL` in `config.py` |
| OQ-1-02 boj_rate field | Column present in schema; written as `NULL` in Phase 1; documented with a comment in `schema.sql` |
| OQ-1-03 Cache persistence | In-memory only; rebuilt on restart; startup event in `main.py` performs immediate feed fetch to minimise cold-start gap |
| OQ-1-04 Server port | `SERVER_PORT = 8000` in `config.py`; consumed by `uvicorn.run()` |

---

## Build Sequence (Dependency Order)

```
Step 1:  Scaffold            → requirements.txt, .env.example, .gitignore, data/.gitkeep
Step 2:  config.py           → all constants, load_dotenv
Step 3:  db/schema.sql       → CREATE TABLE IF NOT EXISTS (both tables, exact spec schema)
Step 4:  db/signal_store.py  → init_db(), all read/write functions
Step 5:  data/mt5_feed.py    → initialize, OHLCV fetch, price, next close time
Step 6:  data/fred_feed.py   → US10Y, Fed Funds Rate, 4h/24h cache
Step 7:  data/market_feed.py → DXY, VIX, 4h cache
Step 8:  data/calendar_feed.py → iCal fetch, parse, filter, news-imminent, upcoming events
Step 9:  scheduler.py        → 4 APScheduler jobs (H1 stub, H4 refresh, daily refresh, calendar)
Step 10: api/dashboard.py    → GET /api/dashboard
Step 11: api/strategies.py   → GET /api/strategies, GET /api/strategy/{id}
Step 12: api/history.py      → GET /api/history
Step 13: main.py             → FastAPI app, CORS, routers, startup/shutdown events, uvicorn
```

---

## File-by-File Specification

### Step 1 — Scaffold

**`requirements.txt`** (pinned):
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
python-dotenv==1.0.1
MetaTrader5==5.0.4424
pandas==2.2.2
fredapi==0.5.2
yfinance==0.2.40
icalendar==5.0.13
APScheduler==3.10.4
requests==2.31.0
pytz==2024.1
```
Pin rationale: `APScheduler` must be `3.x` (not `4.x` — completely different async-first API). `MetaTrader5` is Windows-only; pin to last known stable build.

**`.env.example`**:
```
FRED_API_KEY=your_fred_api_key_here
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

**`.gitignore`** must include: `.env`, `data/*.db`, `__pycache__/`, `*.pyc`, `.venv/`

**`data/.gitkeep`** — empty file to commit the `data/` directory without the `.db` file.

---

### Step 2 — `backend/config.py`

Key design decisions:
- Call `load_dotenv()` at top of file (before any `os.getenv`) so all imports get populated env
- `DB_PATH` built with `pathlib.Path(__file__).parent.parent / "data" / "usdjpy_signals.db"` (absolute, works from any CWD)
- **Do NOT import MetaTrader5 here** — MT5 constants are integers; hardcode them to avoid import failure on non-MT5 machines
- MT5 timeframe integer constants: `M15=15, M30=30, H1=16385, H4=16388, D1=16408`
- `CALENDAR_HIGH_IMPACT_EVENTS` filter list must include both `"Non-Farm"` AND `"Nonfarm"` (Forex Factory uses both spellings)

Constants to define:
```python
MT5_SYMBOL = "USDJPY"
TIMEFRAMES = {"M15": 15, "M30": 30, "H1": 16385, "H4": 16388, "D1": 16408}
EVAL_OFFSET_SECONDS = 120
NEWS_BUFFER_MINUTES = 30
DB_PATH = Path(...)          # absolute, as above
SERVER_PORT = 8000
FOREX_FACTORY_ICAL_URL = "https://www.forexfactory.com/ff_calendar_thisweek.ics"
CALENDAR_HIGH_IMPACT_EVENTS = ["FOMC", "BoJ", "Non-Farm", "Nonfarm", "CPI", "PCE",
                                "BoJ Governor", "10-Year Bond", "Tokyo CPI"]
FRED_CACHE_SECONDS = 14400      # 4 hours
MARKET_CACHE_SECONDS = 14400    # 4 hours
FED_FUNDS_CACHE_SECONDS = 86400 # 24 hours
CALENDAR_CACHE_SECONDS = 86400  # 24 hours

FRED_API_KEY = os.getenv("FRED_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
```

---

### Step 3 — `backend/db/schema.sql`

**Critical: column names must match the spec exactly (FR-1-43, FR-1-44).**

```sql
CREATE TABLE IF NOT EXISTS signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    strategy_id     INTEGER NOT NULL CHECK(strategy_id BETWEEN 1 AND 20),
    strategy_name   TEXT NOT NULL,
    status          TEXT NOT NULL CHECK(status IN ('VALID_TRADE','WAIT_FOR_LEVELS','NO_TRADE')),
    direction       TEXT CHECK(direction IN ('BUY','SELL')),
    entry           REAL,
    sl              REAL,
    tp1             REAL,
    tp2             REAL,
    tp3             REAL,
    rrr             REAL,
    confidence      INTEGER CHECK(confidence BETWEEN 0 AND 100),
    probability     INTEGER CHECK(probability BETWEEN 0 AND 100),
    timeframes      TEXT,
    reasons_for     TEXT,   -- JSON array
    reasons_against TEXT,   -- JSON array
    verdict_summary TEXT,
    outcome         TEXT CHECK(outcome IN ('WIN','LOSS','PENDING'))
);

CREATE TABLE IF NOT EXISTS market_context (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    usdjpy_price    REAL,
    us10y           REAL,
    dxy             REAL,
    vix             REAL,
    fed_rate        REAL,
    boj_rate        REAL,   -- No data source in Phase 1; always NULL
    next_event      TEXT,
    next_event_time TEXT
);
```

Store timestamps as ISO 8601 UTC strings (`"2026-04-24T10:02:00Z"`). SQLite has no native datetime; TEXT ISO sorts correctly and is trivially JSON-serialisable.

---

### Step 4 — `backend/db/signal_store.py`

**All database read/write operations live exclusively in this module (NFR-1-14).**

Design decisions:
- Use `sqlite3` (stdlib) with **per-operation connections** (open → execute → close), not a module-level singleton — avoids Windows file-lock issues when APScheduler jobs and FastAPI handlers both write
- Set `conn.row_factory = sqlite3.Row`; convert to `dict` before returning (prevents JSON serialisation failures)
- `init_db()` must call `DB_PATH.parent.mkdir(parents=True, exist_ok=True)` before opening connection (creates `data/` directory if absent); reads `schema.sql` with `conn.executescript()`
- All functions wrap in `try/except`, log errors, return safe defaults (None, [], -1) — never raise

Functions to implement:
```python
def init_db() -> None
def write_market_context(snapshot: dict) -> None
def get_latest_market_context() -> dict | None    # ORDER BY timestamp DESC LIMIT 1
def write_signal(signal: dict) -> int             # returns new row ID (lastrowid)
def get_all_signals(limit: int = 500) -> list[dict]  # ORDER BY timestamp DESC
def get_signal_by_id(signal_id: int) -> dict | None
```

---

### Step 5 — `backend/data/mt5_feed.py`

Design decisions:
- At module level: `try: import MetaTrader5 as mt5; MT5_AVAILABLE = True` / `except ImportError: MT5_AVAILABLE = False` — prevents import crash on machines without MT5
- `initialize_mt5()` → `mt5.initialize()` with no arguments (session-based, no credentials). Returns `bool`. On failure, logs `mt5.last_error()`.
- `is_connected()` → `bool(mt5.terminal_info() is not None)` — lightweight pre-fetch check
- `get_ohlcv(timeframe_label: str, bars: int = 500) -> pd.DataFrame | None`:
  - Resolve label to int via `TIMEFRAMES` from config
  - Call `mt5.copy_rates_from_pos(MT5_SYMBOL, tf_int, 0, bars)`
  - Convert numpy array → DataFrame; rename `time` column: `pd.to_datetime(df['time'], unit='s', utc=True)`
  - Column order: `time, open, high, low, close, tick_volume`
- `get_current_price() -> float | None` → `mt5.symbol_info_tick(MT5_SYMBOL)`, return `(bid+ask)/2`
- `get_next_candle_close(timeframe_label: str) -> datetime` → arithmetic from `datetime.now(timezone.utc)` using timeframe interval seconds
- `shutdown_mt5() -> None` → `mt5.shutdown()` in try/except
- Every function: check `MT5_AVAILABLE` and `is_connected()` first; log warning and return `None` on failure; never raise

---

### Step 6 — `backend/data/fred_feed.py`

Design decisions:
- Module-level `fredapi.Fred` instance: `_fred = fredapi.Fred(api_key=FRED_API_KEY)`. If key is None, log WARNING at import time; functions will fail gracefully when called.
- Cache: `_cache: dict[str, tuple[float, datetime]]` — maps series ID → `(value, fetched_at_utc)`
- Private helper `_is_fresh(series_id, ttl_seconds) -> bool`
- `get_us10y() -> float | None`: series `"DGS10"`, TTL 4h. Use `.dropna().iloc[-1]` on returned Series (FRED has NaN for weekends)
- `get_fed_funds_rate() -> float | None`: series `"FEDFUNDS"`, TTL 24h
- On error: log WARNING, return stale cached value if any, else `None`; never raise

---

### Step 7 — `backend/data/market_feed.py`

Design decisions:
- Same cache pattern as `fred_feed.py`
- `get_dxy() -> float | None`: `yf.Ticker("DX-Y.NYB").fast_info["lastPrice"]`; fallback `.history(period="2d")["Close"].dropna().iloc[-1]` if `fast_info` returns 0
- `get_vix() -> float | None`: same pattern with `"^VIX"`
- Wrap in broad `except Exception` (Windows `ssl.SSLError` on first yfinance call is common)
- TTL 4h for both
- On error: return stale cached value or `None`; never raise

---

### Step 8 — `backend/data/calendar_feed.py`

Design decisions:
- Module-level state: `_cached_events: list[dict]`, `_cache_fetched_at: datetime | None`
- Each event dict: `{"name": str, "event_time": datetime (UTC-aware), "impact": str}`
- `fetch_and_cache_calendar() -> None`:
  - `requests.get(FOREX_FACTORY_ICAL_URL, timeout=10)`; handle non-200 (Forex Factory occasionally 403s) by falling back to stale cache and logging WARNING
  - `Calendar.from_ical(response.content)`, iterate `cal.walk("VEVENT")`
  - Normalise `DTSTART`: if `date` (not `datetime`), treat as midnight UTC; if naive datetime, localise to UTC
  - Filter: case-insensitive substring match against `CALENDAR_HIGH_IMPACT_EVENTS`
  - Sort ascending by `event_time`; update `_cached_events` and `_cache_fetched_at`
- `is_news_imminent() -> bool`: return `True` if any event has `event_time` within `±NEWS_BUFFER_MINUTES` of `datetime.now(UTC)`; return `False` if cache is empty (do not block on empty cache)
- `get_upcoming_events(n: int = 5) -> list[dict]`: events where `event_time > now(UTC)`, first `n`
- `get_next_event() -> dict | None`: first element of `get_upcoming_events(1)` or `None`

Edge case: Forex Factory iCal only covers the current week. `get_upcoming_events` may return an empty list late in the week. Document this limitation in a code comment.

---

### Step 9 — `backend/scheduler.py`

Design decisions:
- `APScheduler 3.x BackgroundScheduler` with `timezone=pytz.utc` — **must be 3.x, not 4.x**
- 4 jobs:

| Job | Cron | Action |
|---|---|---|
| H1 evaluation stub | `minute=2` (every hour) | Log `"[Scheduler] H1 cycle triggered"` |
| H4 data refresh | `hour="0,4,8,12,16,20", minute=2` | Fetch all feeds → `write_market_context()` |
| Calendar refresh | `hour=0, minute=1` | `fetch_and_cache_calendar()` |
| Daily FRED + market refresh | `hour=0, minute=5` | Force-refresh all feeds (cache expired at midnight) → `write_market_context()` |

- Wrap every job body in `try/except Exception`; log error and continue
- `start_scheduler() -> None` — adds jobs, calls `_scheduler.start()`
- `stop_scheduler() -> None` — calls `_scheduler.shutdown(wait=False)`
- Module-level singleton: `_scheduler = BackgroundScheduler(timezone=pytz.utc)`
- Extract a shared `_build_and_write_snapshot()` helper (used by both H4 and daily refresh jobs)

---

### Step 10 — `backend/api/dashboard.py`

- `APIRouter` with prefix `"/api"`
- `GET /api/dashboard`: calls cached getters from all feeds (no live fetches); all fields nullable; consistent envelope
- `GET /api/status`: reads `mt5_connected`, `db_connected`, `last_*_fetch` timestamps; each feed module must expose `get_last_fetch_time() -> datetime | None`

---

### Step 11 — `backend/api/strategies.py`

- `GET /api/strategies` → `{"success": true, "data": [], "error": null}`
- `GET /api/strategy/{id: int}` → HTTP 404, `{"success": false, "data": null, "error": "Strategy engine not available in Phase 1"}`

---

### Step 12 — `backend/api/history.py`

- `GET /api/history` → calls `get_all_signals()`; returns `{"success": true, "data": [], "error": null}` in Phase 1

---

### Step 13 — `backend/main.py`

Design decisions:
- `CORSMiddleware` origins: `["http://localhost:8000", "http://127.0.0.1:8000", "null"]` — `"null"` allows `file://` HTML opens in Phase 3
- Custom `HTTPException` handler wraps all errors in envelope (replaces FastAPI's default `{"detail": "..."}`)
- `@app.on_event("startup")` sequence:
  1. Configure logging (UTC timestamps, INFO level)
  2. `init_db()`
  3. `initialize_mt5()` — log result; do not abort on False
  4. Initial feed fetch: all four feeds — populates caches before first request
  5. `start_scheduler()`
- `@app.on_event("shutdown")`: `stop_scheduler()`, `shutdown_mt5()`
- Entry: `uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=False)`
- Launch command: `python backend/main.py` from project root

---

## Import Dependency Rules (no circular imports)

```
config.py          ← imports: dotenv, os, pathlib only
signal_store.py    ← imports: config, sqlite3, logging
*_feed.py          ← imports: config, logging, third-party libs ONLY
scheduler.py       ← imports: config, all feeds, signal_store
api/*.py           ← imports: feeds, signal_store (NOT each other)
main.py            ← imports: config, signal_store, mt5_feed, scheduler, all api routers
```

---

## Critical Files

| File | Purpose |
|---|---|
| `backend/config.py` | Single source of all constants and secrets |
| `backend/db/schema.sql` | Authoritative DB schema — must match spec exactly |
| `backend/db/signal_store.py` | Only file permitted to contain raw SQL |
| `backend/data/calendar_feed.py` | Most complex feed; iCal parsing + filtering |
| `backend/scheduler.py` | Orchestrates all feed refreshes and writes |
| `backend/main.py` | Entry point; startup sequence matters |

---

## Verification Against Acceptance Criteria

| AC | Verification Step |
|---|---|
| AC-1-01 | Run `python backend/main.py` → no exception, process alive after 30s |
| AC-1-02 | MT5 terminal running → `GET /api/status` → `mt5_connected: true` |
| AC-1-03 | MT5 terminal closed → `GET /api/status` → `mt5_connected: false`, process still running |
| AC-1-04 | `GET /api/dashboard` → all five float fields non-null |
| AC-1-05 | `GET /api/dashboard` → `next_event` and `next_event_time` non-null |
| AC-1-06 | Inspect `data/usdjpy_signals.db` with DB Browser → both tables, correct column names and types |
| AC-1-07 | Wait 5 min → `SELECT COUNT(*) FROM market_context` → ≥ 1 row |
| AC-1-08 | Wait until HH:02 UTC → check logs for `"[Scheduler] H1 cycle triggered"` |
| AC-1-09 | Call `get_ohlcv("H1")` and `get_ohlcv("H4")` → DataFrames with 200+ rows, 6 correct columns |
| AC-1-10 | Call `get_upcoming_events(5)` → list of ≥ 5 dicts with `name` and `event_time` |
| AC-1-11 | `GET /api/strategies` → HTTP 200, `data: []`, `success: true` |
| AC-1-12 | `GET /api/strategy/1` → HTTP 404, `success: false` |
| AC-1-13 | `GET /api/history` → HTTP 200, `data: []`, `success: true` |
| AC-1-14 | No hardcoded FRED key, Telegram token, or chat ID in any source file |
| AC-1-15 | All 5 endpoint responses contain `success`, `data`, `error` at top level |

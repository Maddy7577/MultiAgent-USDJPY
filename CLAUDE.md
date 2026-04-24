# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Purpose

USDJPY Smart Agent is a local, single-user AI-powered trade intelligence system. It monitors USDJPY using 20 predefined strategies, evaluates each via a 4-agent debate framework, and surfaces high-conviction trade setups with one of three verdicts: **VALID TRADE**, **WAIT FOR LEVELS**, or **NO TRADE**.

---

## How to Run

```bash
# Start the full system (FastAPI + scheduler)
python backend/main.py

# API runs at http://localhost:8000
# Frontend served as static files from frontend/
```

Environment variables required (use `.env` via `python-dotenv`):
- `FRED_API_KEY` — free registration at fred.stlouisfed.org
- `TELEGRAM_TOKEN` — Telegram bot token
- `TELEGRAM_CHAT_ID` — Target chat ID

MT5 terminal must be running on the same Windows machine before starting the server.

---

## Architecture

### Data Flow

```
MT5 (OHLCV) + FRED (US10Y/Fed rate) + yfinance (DXY/VIX) + FF iCal (calendar)
  → backend/data/          ← one module per source, results cached
  → backend/scheduler.py   ← APScheduler fires on H1/H4/D candle close (UTC)
  → backend/strategies/    ← 20 strategy modules, evaluated each H1 close
  → backend/agents/        ← 4-agent debate per strategy → verdict
  → data/usdjpy_signals.db ← SQLite signal store
  → backend/api/           ← FastAPI endpoints serve data to frontend
  → frontend/              ← Vanilla HTML/CSS/JS, polls API every 60s
```

### 4-Agent Debate Framework

Each strategy is evaluated by exactly 4 agent functions:
- **OpportunityAgent 1 & 2** — independently score positive conditions (entry quality, confluence, momentum)
- **RiskAgent 1 & 2** — independently score negative factors (HTF conflict, news risk, poor RRR, liquidity traps)

The `debate_engine.py` aggregates scores across 11 dimensions, applies alignment bonuses/conflict penalties, and produces a `confidence` (0–100) and `probability` (0–100) score. Verdict thresholds: confidence ≥ 75, probability ≥ 70, RRR ≥ 1.5, no critical risk flags → **VALID TRADE**.

Critical risk flags that auto-override to NO TRADE regardless of score:
- High-impact news event within 30 minutes
- USDJPY above 155.00 on a long strategy (intervention risk)
- Spread > 3 pips (illiquid conditions)
- Both risk agents flag the same structural invalidation

### Strategy Modules

All 20 strategies inherit from `strategies/base_strategy.py` and implement `evaluate()`. Indicators are computed **once per cycle** and passed to all strategies — never fetched per-strategy. Every strategy must return a `StrategyResult` dataclass; a VALID TRADE result must always have `entry`, `sl`, and `tp1` populated.

Special strategy constraints:
- **S3 (Carry Trade)** — macro gate first: Fed-BoJ spread > 2.5% required before any technical evaluation
- **S4 (US10Y Yield)** — only evaluate if FRED data is < 6 hours old
- **S8 (Tokyo Breakout)** and **S13 (London Breakout)** — session detection mandatory; return NO TRADE outside session windows
- **S20 (Post-News)** — only fires within 90 minutes of a confirmed high-impact event; calendar data must be current
- **S11, S14, S16** (mean reversion) — require a trending regime filter built into the module

### Scheduler Timing (UTC)

- Every H1 close → fires at HH:02:00 → full 20-strategy evaluation cycle
- Every H4 close → fires at 00:02, 04:02, 08:02, 12:02, 16:02, 20:02 → refresh H4 indicator states
- Daily at 00:05 UTC → refresh FRED, yfinance, economic calendar

### REST API

| Endpoint | Returns |
|---|---|
| `GET /api/dashboard` | Live price, market context, signal summary counts |
| `GET /api/strategies` | All 20 latest strategy verdicts |
| `GET /api/strategy/{id}` | Full debate output for one strategy |
| `GET /api/history` | Paginated signal log |
| `GET /api/status` | MT5 connection state, last evaluation time |

All responses use: `{ "success": bool, "data": {}, "error": null }`

---

## Key Design Decisions

- **No hardcoded values** — everything is referenced from `config.py`
- **No raw SQL outside `db/signal_store.py`** — all DB reads/writes go through that module
- **Agents are pure scoring functions** — no external calls, deterministic, receive pre-computed data only
- **Indicators computed once per cycle** — shared across all 20 strategies to avoid redundant calculation
- **MT5 connection is session-based** — no credentials stored; terminal must already be open
- **SQLite is single-writer** — no concurrency concerns in this single-user local setup

---

## Implementation Phases

Phase documents are in `.claude/Documents/`:

| Phase | Document | Deliverable |
|---|---|---|
| 1 | `01-Phase1-Foundation.md` | Data pipeline, DB schema, FastAPI skeleton |
| 2 | `02-Phase2-StrategyEngine.md` | All 20 strategies, 4-agent debate, scheduled evaluation |
| 3 | `03-Phase3-Frontend.md` | Dashboard, strategy cards, detail pages |
| 4 | `04-Phase4-Notifications.md` | Telegram alerts, signal history queries |
| 5 | `05-Phase5-AutomatedTrading.md` | MT5 order execution after signal validation |

Each phase is independently testable. System architecture reference is in `.claude/Documents/system_architecture.md`. Full strategy rules are in `USDJPY_Algo_Strategy_Reference.md`.

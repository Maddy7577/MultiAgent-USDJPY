# USDJPY Smart Agent — System Architecture

**Version:** 1.0  
**Date:** April 24, 2026  
**Author:** Maddy  
**Platform:** Windows (local machine)  
**Pair:** USD/JPY

---

## 1. Project Overview

USDJPY Smart Agent is a local, single-user AI-powered trade intelligence system. It continuously monitors USDJPY using 20 predefined strategies, evaluates each strategy independently through a 4-agent debate framework, and surfaces only high-conviction trade setups. The system is designed for disciplined, rule-based decision-making — not signal spam.

The final output per strategy is always one of three verdicts:
- **VALID TRADE** — high-confidence, rule-compliant setup with full parameters
- **WAIT FOR LEVELS** — valid in principle but price has not reached the ideal zone yet
- **NO TRADE** — conditions not met or opposing factors too strong

---

## 2. Core Principles

- Quality over quantity — only surface the best setups
- Every strategy is evaluated independently
- No trade without a defined stop loss
- Risk-reward must be acceptable before any VALID verdict
- The system is a decision support tool first; automation comes only after rigorous signal validation
- No credentials are stored; MT5 terminal connection is session-based

---

## 3. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                             │
│  MT5 Terminal (OHLCV)  │  FRED API  │  yfinance  │  FF iCal    │
└──────────────┬──────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────┐
│                     BACKEND (Python / FastAPI)                  │
│                                                                 │
│  ┌─────────────┐    ┌──────────────────────────────────────┐   │
│  │ APScheduler │───▶│         Strategy Engine              │   │
│  │ (candle     │    │  20 Strategy Modules                 │   │
│  │  close      │    │  Each with 4 Agent Functions:        │   │
│  │  trigger)   │    │   • Opportunity Agent 1              │   │
│  └─────────────┘    │   • Opportunity Agent 2              │   │
│                     │   • Risk / Opposition Agent 1        │   │
│                     │   • Risk / Opposition Agent 2        │   │
│                     │                                      │   │
│                     │  Debate Engine → Verdict             │   │
│                     └──────────────┬───────────────────────┘   │
│                                    │                            │
│                     ┌──────────────▼───────────────────────┐   │
│                     │        SQLite Signal Store           │   │
│                     └──────────────┬───────────────────────┘   │
│                                    │                            │
│  ┌─────────────┐    ┌──────────────▼───────────────────────┐   │
│  │  Telegram   │◀───│         FastAPI REST Server          │   │
│  │  Bot        │    │  /api/dashboard                      │   │
│  │  (VALID     │    │  /api/strategies                     │   │
│  │   alerts)   │    │  /api/strategy/{id}                  │   │
│  └─────────────┘    │  /api/history                        │   │
│                     └──────────────┬───────────────────────┘   │
└──────────────────────────────────────┼──────────────────────────┘
                                       │ HTTP polling (60s)
               ┌───────────────────────▼────────────────────┐
               │           FRONTEND (Vanilla HTML/CSS/JS)   │
               │  index.html       → Dashboard              │
               │  strategies.html  → 20 Strategy Cards      │
               │  detail.html      → Single Strategy Debate │
               └────────────────────────────────────────────┘
```

---

## 4. Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Language | Python 3.11+ | Backend and strategy engine |
| Web Framework | FastAPI | REST API server |
| ASGI Server | Uvicorn | Local server runner |
| Scheduler | APScheduler | Candle-close evaluation triggers |
| MT5 Data | `MetaTrader5` Python package | USDJPY OHLCV from running terminal |
| Macro Data | `fredapi` | US 10Y yield, Fed Funds Rate |
| Market Data | `yfinance` | DXY, VIX |
| Calendar | `icalendar` + Forex Factory iCal | Economic events |
| Database | SQLite (stdlib `sqlite3`) | Signal history log |
| Notifications | `python-telegram-bot` | VALID TRADE alerts |
| Frontend | HTML5 + CSS3 + Vanilla JS | Dashboard and strategy UI |

---

## 5. Data Sources

| Data | Source | Frequency | Purpose |
|---|---|---|---|
| USDJPY M15/M30/H1/H4/D OHLCV | MT5 Python API | On candle close | Primary price data for all strategies |
| US 10Y Treasury Yield | FRED API (DGS10) | Every 4 hours | Strategies 3, 4, 5 macro filter |
| Fed Funds Rate | FRED API (DFF) | Daily | Carry-trade bias (Strategy 3) |
| DXY (US Dollar Index) | yfinance (DX-Y.NYB) | Every 4 hours | USD strength filter |
| VIX (Volatility Index) | yfinance (^VIX) | Every 4 hours | Risk-on/off regime |
| Economic Calendar | Forex Factory iCal | Daily (cached) | News event filters (Strategy 20 etc.) |

---

## 6. Evaluation Cycle

```
Every H1 close (fires 2 minutes after the hour):
  1. Pull latest OHLCV from MT5 (M15, H1, H4, D)
  2. For each of the 20 strategies:
       a. Compute required indicators
       b. Run Opportunity Agent 1  → score positive conditions
       c. Run Opportunity Agent 2  → independently score positive conditions
       d. Run Risk Agent 1         → score negative / invalidation factors
       e. Run Risk Agent 2         → independently score negative factors
       f. Debate Engine aggregates → confidence score, probability score
       g. Apply threshold logic    → VALID / WAIT / NO TRADE
       h. Write result to SQLite
  3. If any result = VALID TRADE → send Telegram notification
  4. FastAPI serves updated results immediately

Additional cycles:
  Every H4 close  → refresh H4 indicator states
  Every D close   → refresh Daily bias, re-pull FRED + yfinance data
  Daily 00:01 UTC → re-fetch and cache Forex Factory economic calendar
```

---

## 7. The 4-Agent Framework (Per Strategy)

Each of the 20 strategies is evaluated by exactly 4 agent functions.

### Agent Roles

| Agent | Role | Focus |
|---|---|---|
| Opportunity Agent 1 | Confirms trade setup | Entry quality, rule compliance, confluence |
| Opportunity Agent 2 | Independently confirms | Timing, structure, momentum alignment |
| Risk Agent 1 | Opposes the trade | Weak structure, poor RRR, news risk, HTF conflict |
| Risk Agent 2 | Independently opposes | Liquidity traps, spread risk, invalidation strength |

### Debate Scoring Dimensions

Each agent scores against 11 dimensions:

1. Strategy rule compliance
2. Market structure quality
3. Trend alignment (higher timeframe)
4. Confluence factors
5. Volatility conditions
6. Entry precision
7. Stop loss logic
8. Take profit realism
9. Risk-reward ratio
10. Invalidation strength
11. Macro / news sensitivity

### Verdict Thresholds

| Condition | Verdict |
|---|---|
| Both opportunity agents strong, both risk agents weak, score > high threshold, RRR acceptable | **VALID TRADE** |
| Strategy valid in principle, but price not yet at ideal level | **WAIT FOR LEVELS** |
| Any other combination | **NO TRADE** |

---

## 8. Strategy Output Format

### VALID TRADE
Strategy Name, Direction (Buy/Sell), Entry Price, Stop Loss, TP1, TP2, TP3 (optional), Risk-Reward Ratio, Confidence Score (0–100), Probability Score (0–100), Timeframes Used, Reasons For, Reasons Against, Final Verdict Summary

### WAIT FOR LEVELS
All fields above, plus: Direction Bias, Wait Zone / Entry Zone, Conditions That Must Be Met Before Entry

### NO TRADE
Strategy Name, Status, Confidence Score, Main Rejection Reasons

---

## 9. Database Schema (SQLite)

### Table: `signals`

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| timestamp | DATETIME | When signal was generated |
| strategy_id | INTEGER | 1–20 |
| strategy_name | TEXT | Human-readable name |
| status | TEXT | VALID / WAIT / NO_TRADE |
| direction | TEXT | BUY / SELL / NULL |
| entry | REAL | Entry price |
| sl | REAL | Stop loss |
| tp1 | REAL | Take profit 1 |
| tp2 | REAL | Take profit 2 |
| tp3 | REAL | Take profit 3 (optional) |
| rrr | REAL | Risk-reward ratio |
| confidence | INTEGER | 0–100 |
| probability | INTEGER | 0–100 |
| timeframes | TEXT | e.g. "H1/H4/D" |
| reasons_for | TEXT | JSON array of supporting reasons |
| reasons_against | TEXT | JSON array of opposing reasons |
| verdict_summary | TEXT | Final decision narrative |
| outcome | TEXT | WIN / LOSS / PENDING (manually updated) |

### Table: `market_context`

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Auto-increment |
| timestamp | DATETIME | Snapshot time |
| usdjpy_price | REAL | Last price |
| us10y | REAL | US 10Y yield |
| dxy | REAL | Dollar Index |
| vix | REAL | VIX level |
| fed_rate | REAL | Fed Funds Rate |
| boj_rate | REAL | BoJ Policy Rate |
| next_event | TEXT | Next high-impact event |
| next_event_time | DATETIME | When it fires |

---

## 10. REST API Endpoints

| Endpoint | Method | Returns |
|---|---|---|
| `/api/dashboard` | GET | Live price, market context, signal summary counts |
| `/api/strategies` | GET | All 20 latest strategy verdicts |
| `/api/strategy/{id}` | GET | Full debate output for one strategy |
| `/api/history` | GET | Paginated signal log from SQLite |
| `/api/history/{id}` | GET | Single historical signal detail |
| `/api/status` | GET | System health, last evaluation time, MT5 connection state |

---

## 11. Frontend Pages

### Dashboard (`index.html`)
- Live USDJPY price (bid/ask)
- Current trading session (Tokyo / London / NY / Off)
- Market context strip: DXY, US10Y, VIX, next major news event + countdown
- Signal summary: VALID / WAIT / NO TRADE counts across 20 strategies
- Active signals panel: list of current VALID and WAIT entries with key parameters
- Auto-refresh every 60 seconds with visible countdown

### Strategy Cards (`strategies.html`)
- Filter bar: All / Valid / Wait / No Trade
- 20 cards, one per strategy
- Each card shows:
  - Strategy name + type badge (Trend / Breakout / Mean Reversion / etc.)
  - Timeframe tags (e.g. H1/H4/D)
  - Status border color: Green (VALID) / Amber (WAIT) / Grey (NO TRADE)
  - Direction chip: BUY (green) / SELL (red)
  - Entry, SL, TP1 prices
  - Confidence score
  - Last evaluated timestamp
- Click on card → detail page

### Strategy Detail (`detail.html`)
- Full strategy name and type
- Status badge with timestamp
- Trade parameters: Entry / SL / TP1 / TP2 / TP3 / RRR
- Confidence and Probability scores (progress bars)
- 4-Agent Debate section (expandable per agent):
  - Opportunity Agent 1 findings
  - Opportunity Agent 2 findings
  - Risk Agent 1 findings
  - Risk Agent 2 findings
- Two-column layout: Supporting Reasons vs Opposing Reasons
- Final Verdict summary

---

## 12. Telegram Notifications

- Fires only on **VALID TRADE** verdict
- Uses the user's existing Telegram bot
- Message prefix: `[USDJPY Smart Agent]`
- Content: Strategy name, Direction, Entry, SL, TP1, TP2, Confidence Score, brief reason summary

---

## 13. Project Folder Structure

```
MultiAgent-USDJPY/
├── .claude/
│   └── Documents/
│       ├── system_architecture.md       ← this file
│       ├── 01-Phase1-Foundation.md
│       ├── 02-Phase2-StrategyEngine.md
│       ├── 03-Phase3-Frontend.md
│       ├── 04-Phase4-Notifications.md
│       └── 05-Phase5-AutomatedTrading.md
│
├── backend/
│   ├── main.py                          ← FastAPI entry point + Uvicorn runner
│   ├── config.py                        ← All configuration constants
│   ├── scheduler.py                     ← APScheduler setup and candle-close jobs
│   │
│   ├── data/
│   │   ├── mt5_feed.py                  ← MT5 connection and OHLCV fetcher
│   │   ├── fred_feed.py                 ← FRED API (US10Y, Fed rate)
│   │   ├── market_feed.py               ← yfinance (DXY, VIX)
│   │   └── calendar_feed.py             ← Forex Factory iCal parser
│   │
│   ├── strategies/
│   │   ├── base_strategy.py             ← Base class all strategies inherit
│   │   ├── s01_mtf_trend.py             ← Strategy 1: Multi-Timeframe Trend
│   │   ├── s02_ichimoku.py              ← Strategy 2: Ichimoku
│   │   ├── s03_carry_pullback.py        ← Strategy 3: Carry-Trade Pullback
│   │   ├── s04_yield_correlation.py     ← Strategy 4: US10Y Yield Correlation
│   │   ├── s05_confluence.py            ← Strategy 5: Confluence System
│   │   ├── s06_macd_ema.py              ← Strategy 6: MACD + 200 EMA
│   │   ├── s07_adx_dmi.py               ← Strategy 7: ADX + DMI Filter
│   │   ├── s08_tokyo_breakout.py        ← Strategy 8: Tokyo Range Breakout
│   │   ├── s09_keltner.py               ← Strategy 9: Keltner Channel Breakout
│   │   ├── s10_ema_crossover.py         ← Strategy 10: 50/200 EMA Crossover
│   │   ├── s11_asian_fade.py            ← Strategy 11: Asian Session Range Fade
│   │   ├── s12_donchian.py              ← Strategy 12: Donchian/Turtle Breakout
│   │   ├── s13_london_breakout.py       ← Strategy 13: London Open Breakout
│   │   ├── s14_bollinger_mr.py          ← Strategy 14: Bollinger Band Mean Reversion
│   │   ├── s15_engulfing.py             ← Strategy 15: Engulfing at Key Level
│   │   ├── s16_rsi_mr.py                ← Strategy 16: RSI Mean Reversion
│   │   ├── s17_fibonacci.py             ← Strategy 17: Fibonacci Pullback
│   │   ├── s18_inside_bar.py            ← Strategy 18: Inside Bar Breakout
│   │   ├── s19_pivot_breakout.py        ← Strategy 19: Daily Pivot Breakout
│   │   └── s20_post_news.py             ← Strategy 20: Post-News Breakout
│   │
│   ├── agents/
│   │   ├── opportunity_agent.py         ← Opportunity scoring logic (shared base)
│   │   ├── risk_agent.py                ← Risk/opposition scoring logic (shared base)
│   │   └── debate_engine.py             ← Aggregation, thresholds, verdict generation
│   │
│   ├── api/
│   │   ├── dashboard.py                 ← /api/dashboard endpoint
│   │   ├── strategies.py                ← /api/strategies and /api/strategy/{id}
│   │   └── history.py                   ← /api/history endpoints
│   │
│   ├── notifications/
│   │   └── telegram_bot.py              ← Telegram message builder and sender
│   │
│   └── db/
│       ├── schema.sql                   ← SQLite table definitions
│       └── signal_store.py              ← All read/write operations to SQLite
│
├── frontend/
│   ├── index.html                       ← Dashboard
│   ├── strategies.html                  ← 20 strategy cards
│   ├── detail.html                      ← Single strategy detail / debate view
│   ├── css/
│   │   └── styles.css                   ← All styling
│   └── js/
│       ├── dashboard.js                 ← Dashboard data fetching and rendering
│       ├── strategies.js                ← Cards rendering, filter logic
│       └── detail.js                    ← Debate detail rendering
│
├── data/
│   └── usdjpy_signals.db                ← SQLite database file
│
├── USDJPY_Algo_Strategy_Reference.md    ← Source strategy document
└── requirements.txt                     ← Python dependencies
```

---

## 14. Implementation Phases Summary

| Phase | Name | Key Deliverable |
|---|---|---|
| 1 | Foundation & Data Layer | MT5 connects, all data flows in, DB schema live, FastAPI serves raw data |
| 2 | Strategy Engine | All 20 strategies evaluate independently, 4-agent verdicts generated on schedule |
| 3 | Frontend | Dashboard and strategy pages fully functional in browser |
| 4 | Notifications & History | Telegram alerts live, signal log queryable |
| 5 | Automated Trading | MT5 order execution after rigorous signal validation |

Each phase is independently testable and delivers a working increment of the system.

---

## 15. Key Design Decisions

| Decision | Choice | Reason |
|---|---|---|
| Data source | MT5 Python API | Same price feed as execution, free, already running |
| Evaluation timing | Candle close (H1 base) | Aligns with all strategy pseudocode, prevents intrabar noise |
| Agent intelligence | Algorithmic (rule-based) | Zero cost, deterministic, traceable |
| Storage | SQLite | Embedded, zero infrastructure, sufficient for single-user |
| Frontend | Vanilla HTML/CSS/JS | Simple, no build tools, easy to maintain |
| MT5 connection | Session-based, no credentials stored | Terminal already open, account-agnostic |
| Notifications | Telegram (existing bot) | Instant, mobile, trading-context chat already active |

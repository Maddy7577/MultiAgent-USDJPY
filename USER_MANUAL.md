# USDJPY Smart Agent — User Manual

**Version 1.0 | April 2026**

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Installation & Setup](#2-installation--setup)
3. [Running the System](#3-running-the-system)
4. [The Dashboard](#4-the-dashboard)
5. [The Strategies Page](#5-the-strategies-page)
6. [Strategy Detail Page](#6-strategy-detail-page)
7. [The 20 Trading Strategies](#7-the-20-trading-strategies)
8. [The 4-Agent Debate Framework](#8-the-4-agent-debate-framework)
9. [Evaluation Schedule](#9-evaluation-schedule)
10. [Telegram Notifications](#10-telegram-notifications)
11. [REST API Reference](#11-rest-api-reference)
12. [Configuration Reference](#12-configuration-reference)
13. [Live Trading Guidelines](#13-live-trading-guidelines)
14. [Troubleshooting](#14-troubleshooting)
15. [Glossary](#15-glossary)

---

## 1. Introduction

**USDJPY Smart Agent** is a local, Windows-based AI-powered trade intelligence system. It monitors the USD/JPY currency pair continuously using 20 predefined algorithmic strategies, evaluates each one through a 4-agent debate framework, and surfaces high-conviction trade setups with one of three verdicts:

| Verdict | Meaning |
|---|---|
| **VALID TRADE** | All thresholds passed — setup is ready for discretionary entry |
| **WAIT FOR LEVELS** | Strategy conditions are broadly valid; price not yet in the ideal entry zone |
| **NO TRADE** | Conditions not met, or a critical risk flag has triggered an override |

### Core Philosophy

Quality over quantity. Every potential signal passes through two independent Opportunity Agents and two independent Risk Agents before a verdict is reached. Critical risks (high-impact news, spread too wide, BoJ intervention zone) automatically override to NO TRADE regardless of any score.

### What the System Does NOT Do

- It does **not** place trades automatically (unless Phase 5 is implemented).
- It does **not** guarantee profitability. It surfaces setups; trade management is your responsibility.
- It does **not** replace macro awareness. Always check the calendar before entering a position.

---

## 2. Installation & Setup

### Requirements

- **Operating System**: Windows 10 or Windows 11
- **Python**: 3.11 or higher
- **MetaTrader 5**: Installed, running, and logged into a broker account on the same machine
- **Internet connection**: Required for FRED, Yahoo Finance, and Telegram

### Step 1 — Install Python Dependencies

```bash
# From the project root directory
pip install -r requirements.txt
```

If you prefer an isolated environment (recommended):

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Step 2 — Create the .env File

Create a file named `.env` in the project root with these three variables:

```
FRED_API_KEY=your_fred_api_key_here
TELEGRAM_TOKEN=your_telegram_bot_token_here
TELEGRAM_CHAT_ID=your_telegram_chat_id_here
```

**Getting a FRED API Key**

1. Go to [fred.stlouisfed.org](https://fred.stlouisfed.org) and create a free account.
2. Under your profile, request an API key.
3. It is emailed to you instantly and is free.

FRED provides the US 10-Year Treasury Yield and Fed Funds Rate that several strategies depend on.

**Getting a Telegram Bot Token and Chat ID**

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts to name your bot.
3. BotFather will give you a token like: `123456789:ABCdefGHIjklMnOpqrSTUvwxyz`
4. Start a conversation with your new bot (send `/start`).
5. To find your Chat ID, visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and look for `"chat":{"id":123456789}`.

### Step 3 — Prepare MT5

1. Open your MetaTrader 5 terminal.
2. In **Market Watch**, ensure USDJPY is listed. If not, right-click → Show All (or search for USDJPY).
3. Leave the terminal running. The system connects to it automatically.

---

## 3. Running the System

```bash
python backend/main.py
```

On successful startup you will see output like:

```
Database ready at data/usdjpy_signals.db
Scheduler started
Server ready — API at http://localhost:8000
```

Then open your browser to:

```
http://localhost:8000
```

Keep the terminal window open while you are using the system. Closing it stops all data feeds, evaluations, and notifications.

---

## 4. The Dashboard

The Dashboard (`/index.html`) is your at-a-glance trade intelligence center. It refreshes automatically every 60 seconds.

### Navigation Bar (top, always visible)

| Element | Description |
|---|---|
| **MT5 status dot** | Green = connected, Red = disconnected |
| **Live price** | Current USDJPY bid (updates every 60 s) |
| **UTC clock** | Current UTC time, 24-hour format |
| **Refresh countdown** | Seconds until next data poll |

### Price Section

Displays the current **bid**, **ask**, and **spread in pips**. If spread exceeds 3 pips, a warning indicator appears because all new longs and shorts are automatically blocked at that spread level. The active trading session badge (Tokyo / London / New York / Off-Hours) and minutes until the next session open are also shown here.

### Market Context Strip

Four tiles showing the macro environment:

| Tile | What it shows | Why it matters |
|---|---|---|
| **DXY** | US Dollar Index | USD strength drives USDJPY |
| **US 10Y Yield** | Treasury yield (%) | Single strongest USDJPY macro driver |
| **VIX** | Implied volatility regime label | High VIX = risk-off = JPY strength |
| **Next Event** | Upcoming high-impact release + countdown | Pre-event caution window |

### Signal Summary Counts

Three colored badges at a glance:
- **Green** — number of VALID TRADE setups right now
- **Amber** — number of WAIT FOR LEVELS setups
- **Gray** — number of NO TRADE (not worth showing)

### Active Signals Panel

Lists every VALID TRADE and WAIT FOR LEVELS setup with:
- Strategy name (click to open the full debate)
- BUY or SELL direction chip
- Entry / SL / TP1 prices
- Confidence score

When no setups are active, the panel shows "No active setups at this time."

### Stale Data Banner

If the API becomes unreachable for longer than one cycle, a yellow banner appears showing the timestamp of the last successful update. This typically means the backend has stopped or MT5 went offline. Restart the backend and refresh the browser.

---

## 5. The Strategies Page

The Strategies page (`/strategies.html`) shows all 20 strategy cards in a grid.

### Filter Bar

Click any filter to instantly narrow the view:

- **All** — all 20 strategies
- **Valid Trade** — only green-border cards
- **Wait for Levels** — only amber-border cards
- **No Trade** — only gray-border cards

### Strategy Card

Each card displays:

| Field | Description |
|---|---|
| Border color | Green (VALID TRADE) / Amber (WAIT) / Gray (NO TRADE) |
| Strategy name | e.g., "Multi-Timeframe Trend Alignment" |
| Type badge | Trend / Breakout / Mean Reversion / Session / Correlation |
| Timeframe chips | Which timeframes this strategy evaluates (M30 / H1 / H4 / D1) |
| Direction chip | BUY (green) or SELL (red) — blank if no trade |
| Entry / SL / TP1 | Exact price levels |
| Confidence | 0–100 score; green ≥75, yellow 50–74, red <50 |
| Last evaluated | Relative time (e.g., "3 mins ago") |

Click any card to open the full Strategy Detail page for that strategy.

---

## 6. Strategy Detail Page

The detail page (`/detail.html?strategy=N`) breaks down exactly why a strategy received its verdict.

### Header

Strategy name, type, status badge, and the timestamp of the last evaluation.

### Trade Parameters

If a trade direction exists, this grid shows:
- Entry, Stop Loss, TP1, TP2, TP3 (where applicable)
- Risk-Reward Ratio (e.g., 2.1)
- Timeframes used in the evaluation

### Score Bars

Two progress bars:

- **Confidence (0–100)** — How certain is the 4-agent debate that all conditions are met?
- **Probability (0–100)** — How likely is this setup to be structurally sound (rule compliance + market structure + HTF alignment)?

Both must reach 75 and 70 respectively for a VALID TRADE verdict.

### 4-Agent Debate Section

Four expandable cards — one per agent. Click to expand and see all 11 evaluated dimensions.

| Agent | Role |
|---|---|
| Opportunity Agent 1 | Scores how good the setup looks |
| Opportunity Agent 2 | Independent second opinion on opportunity |
| Risk Agent 1 | Scores how risky the setup is |
| Risk Agent 2 | Independent second opinion on risk |

Each agent card shows:
- The agent's score (0–10)
- Pass / Partial / Fail status for each of the 11 dimensions
- Specific reasons and flags

### Verdict Summary Section

A two-column panel:
- **Supporting reasons** (what is in favor of the trade)
- **Opposing reasons** (what is against it)

Below that, the **Final Verdict** in one line — for example:

```
VALID TRADE: BUY @ 150.250 | SL 149.500 | TP1 151.000 | RRR 1.67 | Confidence 82 | Probability 78
```

or:

```
WAIT FOR LEVELS: Price needs to retrace to 150.100–150.300 zone
```

or:

```
NO TRADE: Confidence 35 / Probability 42 / HTF conflict detected
```

---

## 7. The 20 Trading Strategies

All strategies are evaluated on every H1 candle close. They share pre-computed indicators; nothing is recalculated per-strategy.

### Strategy Reference Table

| # | Name | Type | Timeframes | Approx Win Rate | R:R | Freq (trades/wk) |
|---|------|------|-----------|----------------|-----|-----------------|
| 1 | Multi-Timeframe Trend Alignment | Trend | D+H4+H1 | 45–55% | 1:2–1:3 | 2–5 |
| 2 | Full Ichimoku System | Trend/Japanese | H4/D | 40–50% | 1:2–1:3 | 1–2 |
| 3 | Carry-Trade Pullback | Hybrid | D bias + H4 entry | 50–60% | 1:2–1:3 | 0.5–1.5 |
| 4 | US 10Y Yield Correlation | Correlation | D bias + H4 entry | 55–65% | 1:2–1:4 | 0.5–1.5 |
| 5 | Confluence System | Multi-Signal | D bias + H4 entry | 55–65% | 1:2–1:3 | 1–2 |
| 6 | MACD + 200 EMA | Trend | H1/H4 | 45–55% | 1:1–1:2 | 2–5 |
| 7 | ADX + DMI Filter | Trend Filter | H4 | 45–55% | 1:1.5–1:2 | 0–4 |
| 8 | Tokyo Range Breakout | Session | M30/H1 | 40–50% | 1.5:1–2:1 | 3–4 |
| 9 | Keltner Channel Breakout | Volatility | H1/H4 | 40–50% | 1.5:1–2:1 | 2–4 |
| 10 | 50/200 EMA Crossover | Trend | H4 | 35–45% | 1:1.5–1:3 | 0.5–2 |
| 11 | Asian Session Range Fade | Mean Reversion | M30 | 60–70% | 0.5:1–0.8:1 | 4–6 |
| 12 | Donchian/Turtle Breakout | Trend | D/H4 | 35–45% | 1:2–1:4 | 0.25–0.75 |
| 13 | London Open Breakout | Session | M30/H1 | 45–55% | 2:1 | ~3 |
| 14 | Bollinger Band Mean Reversion | Mean Reversion | H1/H4 | 55–70%* | 1:1–1:2 | 3–5 |
| 15 | Engulfing at Key Level | Price Action | H4/D | 55–65% | 1:1.5–1:2 | 2–4 |
| 16 | RSI Mean Reversion | Mean Reversion | H1/H4 | 50–62% | 1:1–1:1.5 | 2–4 |
| 17 | Fibonacci Pullback | Retracement | H4/D | 45–58% | 1:2–1:3 | 1–3 |
| 18 | Inside Bar Breakout | Price Action | D/H4 | 45–55% | 1:2 | 0.5–1 |
| 19 | Daily Pivot Breakout | Levels | M30/H1 | 40–48% | 1.5:1–2:1 | 3–4 |
| 20 | Post-News Breakout | Event-Driven | H1 | 45–55% | 1:2 | ~0.25 |

*Win rate for Strategy 14 applies only in confirmed ranging market (ADX < 25). In trending conditions it falls significantly.

---

### Strategy Descriptions

#### S1 — Multi-Timeframe Trend Alignment

Requires three timeframes to agree: Daily uptrend (price > EMA50 > EMA200), H4 pullback to EMA20, and H1 MACD bullish cross above EMA20. Entry on a bullish confirmation candle close. Stop below the most recent H1 swing low (minimum 1.5 × ATR). This is the "fractal carry-trade" system that works well during Fed/BoJ rate-cycle divergence periods.

#### S2 — Full Ichimoku System

Requires all four Ichimoku conditions simultaneously: price above the cloud, bullish Tenkan-Kijun cross above the cloud, Chikou Span above price 26 bars ago, and future cloud is bullish (Senkou A > Senkou B). This is institutionally respected by Japanese traders, which adds a self-fulfilling dimension to its edge.

#### S3 — Carry-Trade Pullback

Carry gate fires first: the Fed Funds Rate minus BoJ policy rate must exceed 2.5% and be stable or widening. If that fails, the strategy returns NO TRADE immediately without evaluating any technical conditions. When the macro gate passes, it looks for a Daily uptrend with an H4 pullback to the Fibonacci 38.2–61.8% zone and a bullish reversal candle. Currently relevant given Fed rates near 3.75–4% versus BoJ at 0.75%.

#### S4 — US 10Y Yield Correlation

Only evaluates if FRED data is less than 6 hours old. Requires the 30-day rolling correlation between USDJPY and US 10Y yield to be 0.70 or above. Entry when the 10Y breaks to a 10-day high and USDJPY pulls back to its H4 EMA20 with a bullish rejection candle during the NY session. USDJPY has the highest yield correlation of any major pair (+0.70 to +0.95 historically).

#### S5 — Confluence System

Score-based: at least 3 of 4 conditions must be present. (1) Daily uptrend. (2) Price at a significant horizontal level (round number or prior swing). (3) Bullish candle pattern (engulfing or pin bar). (4) Bullish RSI divergence on H4. The more conditions active, the higher the Opportunity Agent scores.

#### S6 — MACD + 200 EMA

Price above the 200 EMA (regime filter), then MACD line crosses above the signal line. The system enters on the close of the cross bar and exits on an opposite MACD cross. Simple and robust; best applied to H1 and H4 to avoid Tokyo session noise.

#### S7 — ADX + DMI Filter

ADX(14) above 25 confirms a trending regime. +DI above −DI = bullish, −DI above +DI = bearish. Entry on a pullback to EMA20 with a confirmation candle. Exits when ADX drops below 20 (trend weakening) or the DI lines cross. Functions as a regime-classification layer that reduces false signals from ranging conditions.

#### S8 — Tokyo Range Breakout

Session-based: marks the Tokyo session range (00:00–07:00 UTC). Places conceptual OCO orders above and below the range. The breakout fires at London open or within the first few London hours. This strategy will return NO TRADE if evaluated outside the session window. Hard close at 16:00 UTC.

#### S9 — Keltner Channel Breakout

Adaptive ATR-based bands (EMA20 ± 2 × ATR). Entry on a close outside the bands followed by a pullback to EMA20 that holds, then a confirmation candle. Exit when price closes back through the EMA20 midline or touches the opposite band. Works well when ATR expands around BoJ events.

#### S10 — 50/200 EMA Crossover Pullback

Waits for a Golden Cross (EMA50 crosses above EMA200). Then waits for the first pullback to the EMA50 or a swing low. Entry on a bullish reversal candle. Low frequency (0.5–2 trades/week) but designed to catch regime shifts. The 2022–2024 carry-trade run from 113 to 162 would have been one extended position for this system.

#### S11 — Asian Session Range Fade

Mean reversion within the Tokyo range (first 2 hours, 00:00–02:00 UTC). The ADX(H1) must be below 20 (ranging regime) — this is mandatory, not optional. Entry on RSI below 30 with a bullish reversal candle at the range low. Hard exit at 06:30 UTC. Do not use this strategy when there is a directional trend.

#### S12 — Donchian/Turtle Breakout

Break of the 20-bar channel (high for longs, low for shorts). Skip rule: if the previous 20-bar breakout in the same direction produced a winning trade, skip the next one. Stop is 2 × ATR(20) from entry (the "2N" rule from the original Turtle system). Low win rate (35–45%) with large R:R. Requires patience through losing streaks.

#### S13 — London Open Breakout

Pre-London range (05:00–07:00 UTC) high/low as the reference. Entry only in the direction of the H1 trend (EMA20 > EMA50 = longs only; EMA20 < EMA50 = shorts only). Unfilled orders are cancelled at 10:00 UTC. Hard close at 16:00 UTC. The trend filter eliminates approximately 40% of false breakouts.

#### S14 — Bollinger Band Mean Reversion

Regime gate mandatory: ADX(14) must be below 25. Enters on a wick below the lower band (long) or above the upper band (short) followed by a confirmation candle that closes back inside the bands. Target is the middle band. Win rate drops to 30–45% in trending conditions, so the ADX filter is the most important rule in this strategy.

#### S15 — Engulfing at Key Level

A bullish or bearish engulfing candle at a key level: a prior swing, a round number (e.g., 150.00, 151.00), or a pivot. The current candle body must be at least 1.2× the average body size of the prior 10 bars. Evaluated on H4 and Daily timeframes. Reversal edge documented at approximately 79% historically at key confluence levels.

#### S16 — RSI Mean Reversion

RSI(14) below 30 with a bullish rejection candle (long), or RSI above 70 with a bearish rejection candle (short). A trend filter is built in to avoid buying oversold in a strong downtrend. Targets a return to RSI 40–60 (midrange). Pairs well with S6 or S10 for directional guidance.

#### S17 — Fibonacci Pullback

Identifies a recent multi-day impulse leg, then enters when price retraces to the 38.2, 50, or 61.8 Fibonacci level with a reversal candle confirmation. Exit targets the next Fibonacci extension (127.2 or 161.8). Lower frequency than breakout strategies but with cleaner R:R.

#### S18 — Inside Bar Breakout

An inside bar is a candle whose high and low are entirely contained within the previous bar's range (consolidation). Entry on a close beyond the inside bar's high (long) or low (short) with confirmation. Evaluated on Daily (H4 variant also included). Low frequency, mechanical, and simple.

#### S19 — Daily Pivot Breakout

Uses yesterday's high, low, and close to compute pivot levels (P, R1, R2, S1, S2). Entry on a break of R1 (long) or S1 (short) with M30/H1 confirmation. Time-of-day filtering applies. Highest frequency of all strategies (3–4 potential setups per day). Best used as a short-term intraday filter, not a swing trade system.

#### S20 — Post-News Breakout

Fires only within 90 minutes of a confirmed high-impact economic event (FOMC, BoJ decision, NFP, CPI) from the Forex Factory calendar. If no qualifying event has occurred recently, the strategy returns NO TRADE without running the debate. Enters on the break of the initial volatility spike high or low. Calendar data must be current (auto-refreshed daily at 00:05 UTC).

---

## 8. The 4-Agent Debate Framework

Every strategy runs through four independent scoring agents before a verdict is reached.

### The Four Agents

| Agent | Role | Focus |
|---|---|---|
| **Opportunity Agent 1** | Scores the quality of the setup | Conditions met, entry quality, momentum, timing |
| **Opportunity Agent 2** | Independent second opinion | Same dimensions, different weights |
| **Risk Agent 1** | Scores how dangerous the setup is | News risk, HTF conflict, R:R, spread, intervention zone |
| **Risk Agent 2** | Independent second opinion | Same dimensions, different weights |

Having two agents per role surfaces disagreements. If both opportunity agents strongly agree, a bonus is applied. If both risk agents flag the same critical issue, a penalty is applied and the verdict overrides to NO TRADE.

### The 11 Evaluation Dimensions

Every agent evaluates these dimensions and marks each as **met**, **partial**, or **not met**:

1. Strategy rule compliance
2. Market structure quality
3. Trend alignment (higher timeframe)
4. Confluence factors
5. Volatility conditions
6. Entry precision
7. Stop loss logic
8. Take profit realism
9. Risk-Reward Ratio
10. Invalidation strength
11. Macro / news sensitivity

### Scoring and Aggregation

The debate engine combines the four scores:

```
net_score = opportunity_average − risk_average + alignment_bonus − penalties
confidence = normalized(net_score)   →  0 to 100
```

Bonuses and penalties:
- **+5** if both Opportunity Agents agree within 1.5 points (aligned conviction)
- **−5** if Opportunity Agents diverge by more than 3.0 points (conflicting signals)
- **−5** if both Risk Agents flag the same critical structural issue

**Probability** is computed separately:

```
probability = (50% × rule_compliance) + (30% × structure_quality) + (20% × trend_alignment)
```

### Critical Override Flags

These four conditions automatically force **NO TRADE** regardless of any score:

| Condition | Threshold |
|---|---|
| High-impact news event | Within 30 minutes of release |
| USDJPY price (long trades only) | Above 155.00 (BoJ intervention zone) |
| Spread | Greater than 3.0 pips |
| Risk agent agreement | Both flag the same structural invalidation |

### Verdict Thresholds

```
If confidence ≥ 75
   AND probability ≥ 70
   AND RRR ≥ 1.5
   AND entry/SL/TP1 populated
   AND no critical flags:
      → VALID TRADE

Else if rule_compliance ≥ 40% AND wait zone is defined:
      → WAIT FOR LEVELS

Else:
      → NO TRADE
```

---

## 9. Evaluation Schedule

The system runs two types of scheduled work automatically.

### H1 Evaluation Cycle (every hour)

**Fires:** 2 minutes after each H1 candle close (HH:02:00 UTC)

What happens each cycle:
1. Fetch latest OHLCV from MT5 (M15 through D1)
2. Compute all technical indicators (once, shared across all 20 strategies)
3. Run each of the 20 strategies through the 4-agent debate
4. Write results to SQLite (`data/usdjpy_signals.db`)
5. Send Telegram notification for any VALID TRADE verdict
6. Results are immediately available via the REST API and the frontend

Each full cycle takes approximately 5–10 seconds.

### Secondary Refreshes

| Job | When (UTC) | What it refreshes |
|---|---|---|
| H4 indicator cache | Every H4 close: 00:02, 04:02, 08:02, 12:02, 16:02, 20:02 | H4-based indicator states |
| Daily context | 00:05 daily | FRED (US10Y, Fed rate), Yahoo Finance (DXY, VIX), economic calendar |

---

## 10. Telegram Notifications

A notification is sent only when a strategy reaches a **VALID TRADE** verdict.

### Notification Format

```
[USDJPY Smart Agent] VALID TRADE

Strategy: Multi-Timeframe Trend Alignment
Direction: BUY
Entry:         150.250
Stop Loss:     149.500
Take Profit 1: 151.000
Take Profit 2: 151.750
Confidence:    92%
Probability:   85%
Risk-Reward:   1.67

Reasons for:
- Daily uptrend confirmed (price > EMA50 > EMA200)
- H4 pullback to EMA20 with higher-low structure
- H1 MACD bullish cross above EMA20
- Confirmation candle closed bullish

Timeframes: D1, H4, H1
Evaluated:  2026-04-27 10:02:00 UTC
```

### Muting Notifications Temporarily

Set `TELEGRAM_CHAT_ID=""` in your `.env` file and restart the backend. No code changes are needed. Remove the empty value and restart to re-enable.

---

## 11. REST API Reference

All responses follow this structure:

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

### GET /api/dashboard

Returns the live price, macro context snapshot, and signal summary counts. Called by the Dashboard frontend every 60 seconds.

### GET /api/strategies

Returns the latest verdict for all 20 strategies. Called by the Strategies page to populate the strategy cards.

### GET /api/strategy/{id}

Returns the full debate breakdown for one strategy (id = 1–20). Called by the Strategy Detail page.

### GET /api/history

Returns paginated signal history from the database.

Query parameters:
- `page` (default: 1)
- `per_page` (default: 50)
- `strategy_id` (optional — filter by strategy)

### GET /api/status

Returns the system health state: MT5 connection status, last evaluation timestamp, number of signals in the database.

### POST /api/evaluate

Manually triggers a full 20-strategy evaluation cycle. Useful for testing immediately after startup without waiting for the next H1 close.

---

## 12. Configuration Reference

All settings are in `backend/config.py`. Edit the file and restart the backend to apply changes.

| Setting | Default | Description |
|---|---|---|
| `MT5_SYMBOL` | `"USDJPY"` | Trading pair |
| `MT5_BARS_COUNT` | `500` | Historical bars to fetch per timeframe |
| `EVAL_OFFSET_SECONDS` | `120` | Seconds after candle close to fire evaluation |
| `NEWS_BUFFER_MINUTES` | `30` | Minutes before/after high-impact event to block new trades |
| `INTERVENTION_LEVEL` | `155.00` | BoJ intervention zone; blocks new longs above this price |
| `MAX_SPREAD_PIPS` | `3.0` | Spread above this value forces NO TRADE |
| `CONFIDENCE_THRESHOLD` | `75` | Minimum confidence for VALID TRADE |
| `PROBABILITY_THRESHOLD` | `70` | Minimum probability for VALID TRADE |
| `MIN_RRR` | `1.5` | Minimum Risk-Reward Ratio for VALID TRADE |
| `BOJ_RATE` | `0.75` | BoJ policy rate (%) — update manually after each BoJ decision |

**Important:** When the BoJ changes its policy rate, update `BOJ_RATE` in `config.py` and restart the server. Strategy 3 (Carry-Trade Pullback) uses this value directly.

---

## 13. Live Trading Guidelines

The system is a **decision-support tool**. It tells you when a setup exists; you decide whether to enter. These guidelines help you use it safely.

### Before Entering Any VALID TRADE

- Read the Strategy Detail page — understand why the debate scored high.
- Check the macro context: is there a major event (FOMC, BoJ, NFP) within the next few hours?
- Confirm the H4 or Daily trend matches the signal direction.
- Check the current spread in the Price Section. If elevated, wait.

### Position Sizing

- Risk no more than **0.5–1.0% of account equity** per trade.
- All 20 strategies trade USDJPY — they are correlated. Running 5 concurrent positions is not 5 independent bets.
- **Maximum 2 concurrent open positions** across all 20 strategies.

### Maximum Loss Rules

| Drawdown Level | Action |
|---|---|
| −3% intraday | Close all positions, stop trading for the day |
| −6% in a week | Review all strategies; do not trade until cause is identified |

### Special Market Conditions

**BoJ Intervention Zone (USDJPY above 155.00)**
The system automatically blocks new longs when price is above 155.00. If you hold an existing long near this level, consider reducing size and widening your stop. The 2022 intervention campaigns saw 3–5% moves in minutes.

**Carry Unwind Risk**
A sudden narrowing of the Fed-BoJ rate spread (e.g., BoJ rate hike surprise or Fed emergency cut) can cause USDJPY to drop sharply. Strategy 3 monitors this via the macro gate. Monitor central bank communication during Fed and BoJ meeting windows.

**Pre-FOMC and Pre-BoJ Windows**
The system blocks new trades within 30 minutes of a high-impact event. Consider flattening or reducing existing positions before major decisions.

**Holiday Liquidity**
Japanese national holidays and US holidays cause thin liquidity. Session-based strategies (S8, S11, S13) may behave erratically. Consider skipping or reducing size on known thin-liquidity days.

### What to Track

Keep a simple log of each trade you take:
- Which strategy triggered it
- Entry, exit, actual outcome (WIN/LOSS)
- Brief note on whether the debate reasoning proved correct

After 20–30 trades per strategy you will have enough data to identify which strategies work best for your broker and execution conditions.

---

## 14. Troubleshooting

### MT5 Status Dot is Red

The backend cannot connect to MetaTrader 5.

1. Confirm the MT5 terminal is open and logged in.
2. Confirm USDJPY appears in Market Watch (not hidden).
3. Ensure no other Python application is simultaneously using the MT5 terminal.
4. Restart MT5, then restart the backend.

### Dashboard Shows 0 Active Setups

This is often normal — most strategy conditions are not met at any given moment.

If you want to verify the system is running correctly:
1. Send `POST /api/evaluate` from a REST client or browser (or open `http://localhost:8000/api/evaluate` if GET is supported).
2. Check the response for each strategy's verdict and confidence score.
3. Check the backend terminal for any `ERROR` log lines.

Note: The system waits for an H1 candle close before running its first evaluation. If you just started the backend, wait up to 60 minutes.

### Telegram Alerts Not Arriving

1. Verify `TELEGRAM_TOKEN` and `TELEGRAM_CHAT_ID` are correctly set in `.env`.
2. Confirm a VALID TRADE verdict actually exists — check `/api/strategies`.
3. Look at the backend terminal for lines containing `Telegram` to check for send errors.
4. Confirm your bot has not been blocked (try sending a message to it manually).

### "Stale Data" Banner on the Dashboard

The frontend could not reach the backend API for at least one poll cycle.

1. Check whether the backend terminal is still running (no crashes).
2. Try opening `http://localhost:8000/api/status` directly in a browser. If that fails, the backend is down.
3. Restart: `python backend/main.py`.
4. After restart, the banner clears on the next 60-second poll.

### FRED Data Warning

Strategy 4 (US 10Y Yield Correlation) will return NO TRADE if FRED data is older than 6 hours. This can happen if:
- Your FRED API key is invalid or rate-limited.
- The FRED service was temporarily unavailable during the 00:05 UTC refresh.

Check the backend log for FRED-related errors. Test your key directly at `https://api.stlouisfed.org/fred/series/observations?series_id=DGS10&api_key=YOUR_KEY&limit=1&file_type=json`.

---

## 15. Glossary

| Term | Definition |
|---|---|
| **VALID TRADE** | Setup passed all confidence, probability, and RRR thresholds with no critical flags |
| **WAIT FOR LEVELS** | Strategy logic is broadly correct but price has not yet reached the ideal entry zone |
| **NO TRADE** | Conditions not met or a critical risk flag forced an override |
| **Confidence** | 0–100 score; reflects how certain the 4-agent debate is that all strategy conditions are satisfied |
| **Probability** | 0–100 score; reflects the structural soundness of the setup (rule compliance + structure + HTF alignment) |
| **RRR** | Risk-Reward Ratio — take-profit distance divided by stop-loss distance (e.g., 2.0 means risk $1 to make $2) |
| **HTF** | Higher TimeFrame — typically Daily or H4; used as context for H1 and lower-timeframe entries |
| **Carry Trade** | A long USDJPY position held to earn the interest-rate differential between the US Fed rate and the BoJ rate |
| **Carry Unwind** | Rapid sell-off of USDJPY as carry positions are closed; typically triggered by BoJ hikes or Fed cuts |
| **BoJ Intervention** | The Japanese Ministry of Finance selling USD/buying JPY above key levels to defend the yen |
| **Kumo** | The Ichimoku cloud; a dynamic support/resistance zone calculated from Senkou Span A and B |
| **Confluence** | Multiple independent technical signals aligning at the same price level and direction |
| **Mean Reversion** | The tendency for price extremes to return toward the average; opposite of trend-following |
| **Regime** | The current market state — trending (ADX > 25) vs. ranging (ADX < 20) |
| **Sessions** | Tokyo: 00:00–07:00 UTC · London: 08:00–17:00 UTC · New York: 13:00–22:00 UTC |
| **ATR** | Average True Range; a measure of recent price volatility used for stop sizing |
| **DXY** | US Dollar Index; measures USD strength against a basket of major currencies |
| **VIX** | CBOE Volatility Index; measures implied volatility of S&P 500 options; high VIX = risk-off = JPY strength |
| **FRED** | Federal Reserve Economic Data; free API providing US macroeconomic data including Treasury yields |
| **Spread** | The difference in pips between the bid and ask price; above 3 pips blocks all new entries |
| **EMA** | Exponential Moving Average; a trend-following indicator that weights recent prices more heavily |
| **MACD** | Moving Average Convergence Divergence; a momentum indicator showing the relationship between two EMAs |
| **RSI** | Relative Strength Index; a momentum oscillator measuring overbought (>70) and oversold (<30) conditions |
| **ADX** | Average Directional Index; measures trend strength (not direction); >25 = strong trend, <20 = range |
| **Fibonacci levels** | Key retracement levels (38.2%, 50%, 61.8%) derived from the Fibonacci sequence used to find pullback entries |
| **Donchian Channel** | A channel defined by the highest high and lowest low over N bars; the basis for the Turtle Trading system |
| **Inside Bar** | A candle whose high is lower than the previous bar's high and whose low is higher than the previous bar's low |
| **Engulfing Candle** | A candle whose body completely contains the previous bar's body; signals potential reversal |
| **OCO Order** | One-Cancels-Other; a pair of orders where filling one automatically cancels the other |

---

*For the complete strategy rules and backtesting specifications, see `USDJPY_Algo_Strategy_Reference.md`. For architecture details, see `.claude/Documents/system_architecture.md`.*

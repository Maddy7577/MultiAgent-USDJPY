# Phase 2 — Strategy Engine

**Phase:** 2 of 5  
**Goal:** Build the complete strategy evaluation engine — all 20 strategy modules, the 4-agent debate framework, verdict generation, and the scheduled evaluation cycle.  
**Deliverable:** Every H1 candle close triggers evaluation of all 20 strategies. Each produces a VALID TRADE / WAIT FOR LEVELS / NO TRADE verdict with full reasoning, confidence score, and trade parameters. Results are stored in SQLite.

---

## What Gets Built in This Phase

### 1. Base Strategy Class (`strategies/base_strategy.py`)

All 20 strategy modules inherit from a common base class that provides:

- A standard interface: every strategy exposes the same `evaluate()` method
- Access to pre-fetched OHLCV DataFrames and market context (passed in, not fetched per-strategy)
- Access to the economic calendar "news imminent" flag
- Standard output structure: a `StrategyResult` dataclass containing all output fields
- A shared utility library for common indicator calculations (EMA, MACD, ATR, RSI, Bollinger Bands, Ichimoku lines, ADX/DMI, Donchian channels, Keltner channels, pivot points, Fibonacci levels)
- Swing high/low detection utility
- Session detection utility (Tokyo / London / NY / Off)

The base class ensures that no strategy can return a VALID TRADE without a defined entry, SL, and at least TP1.

---

### 2. Indicator Library (inside `base_strategy.py`)

Shared calculations used across multiple strategies. Computed once per evaluation cycle and passed to all strategies to avoid redundant calculation.

| Indicator | Used By Strategies |
|---|---|
| EMA (20, 50, 200) on H1/H4/D | 1, 3, 5, 6, 10 |
| MACD (12, 26, 9) | 1, 6 |
| ATR (14) on H1/H4 | 1, 2, 3, 7, 8, 9, 13 |
| RSI (14) on H1/H4 | 3, 5, 16 |
| Bollinger Bands (20, 2) | 14 |
| Ichimoku (9, 26, 52) | 2 |
| ADX + DMI (14) | 7 |
| Donchian Channel (20) | 12 |
| Keltner Channel (20, 1.5 ATR) | 9 |
| Fibonacci levels | 17 |
| Daily Pivot Points (Classic) | 19 |
| Swing High/Low detection | 1, 3, 8, 13, 15, 17, 18 |
| Session clock | 8, 11, 13 |
| Engulfing candle detector | 3, 15 |
| Inside bar detector | 18 |

---

### 3. The 4-Agent Framework (`agents/`)

#### Design Principle
Each strategy instance creates 4 agent functions. Agents do not call external services — they are pure scoring functions that receive pre-computed indicator data and return structured scores.

#### `opportunity_agent.py`
Defines the `OpportunityAgent` class. Two instances are created per strategy (Agent 1 and Agent 2). Each independently evaluates:
- Are all entry conditions met?
- Is the signal timing precise?
- Is there confluence across timeframes?
- Is momentum aligned?
- Is the entry zone clean (not midway through a move)?

Each agent scores 0–10 per relevant dimension from the 11-point scoring system. Not all 11 dimensions apply to every strategy — each strategy defines which dimensions are active.

Agent 1 and Agent 2 use the same rules but independent execution paths — they are designed to surface any scoring inconsistency that would indicate an ambiguous setup.

#### `risk_agent.py`
Defines the `RiskAgent` class. Two instances per strategy (Agent 1 and Agent 2). Each independently evaluates:
- Are there reasons NOT to take this trade?
- Is the higher timeframe in conflict?
- Is there a major news event imminent?
- Is the stop loss placement logical or is it in a liquidity trap zone?
- Is the risk-reward ratio acceptable?
- Is spread/slippage a concern (e.g., during illiquid hours)?
- Does the setup violate any known USDJPY-specific risk (intervention zone, carry unwind signals)?

Each risk agent returns a `risk_score` (0–10, where 10 = maximum risk / strongest case against) and a list of specific `risk_flags` as human-readable strings.

#### `debate_engine.py`
Receives the four agent outputs and produces the final verdict.

**Debate Logic:**

```
opportunity_score  = average of (OppAgent1.score + OppAgent2.score)
opposition_score   = average of (RiskAgent1.risk_score + RiskAgent2.risk_score)
alignment_bonus    = +5 if both opportunity agents agree (scores within 1.5 of each other)
conflict_penalty   = -5 if opportunity agents strongly disagree (scores > 3 apart)
risk_alignment_penalty = -5 if both risk agents flag the same critical risk

net_score = opportunity_score - opposition_score + alignment_bonus
            - conflict_penalty - risk_alignment_penalty

confidence = normalize(net_score) → 0–100
probability = weighted combination of: rule_compliance, structure_quality, trend_alignment
```

**Verdict Rules:**

| Condition | Verdict |
|---|---|
| confidence ≥ 75 AND probability ≥ 70 AND RRR ≥ 1.5 AND no critical risk flags | VALID TRADE |
| Strategy rules partially met AND price not yet at ideal zone | WAIT FOR LEVELS |
| Everything else | NO TRADE |

Critical risk flags that auto-override to NO TRADE regardless of score:
- High-impact news event within 30 minutes
- USDJPY above 155.00 on a long strategy (intervention risk)
- MT5 feed shows spread > 3 pips (illiquid conditions)
- Both risk agents flag the same structural invalidation

---

### 4. All 20 Strategy Modules

Each strategy module (`strategies/s01_mtf_trend.py` through `s20_post_news.py`) contains:

- A `StrategyConfig` dataclass with all parameters from the reference document (indicator settings, thresholds, timeframes, session filter)
- A `check_long_conditions()` function and `check_short_conditions()` function
- Input: pre-computed indicator data
- Output: a scored `OpportunityResult` or `RiskResult` fed to the debate engine
- Stop loss calculation logic specific to this strategy
- Take profit calculation logic (TP1, TP2, optional TP3)
- WAIT FOR LEVELS logic: if the setup is directionally valid but price hasn't reached the zone, return the target zone + planned trade parameters

**Strategy-specific notes:**

| Strategy | Special Handling |
|---|---|
| S1: MTF Trend | Requires Daily + H4 + H1 alignment — most complex multi-timeframe check |
| S2: Ichimoku | All 5 Ichimoku lines computed, 4-condition checklist evaluated |
| S3: Carry Trade | Macro gate first: Fed-BoJ spread > 2.5% required before any technical evaluation |
| S4: US10Y Yield | Yield direction (rising/falling) fetched from FRED data, not price action |
| S5: Confluence | 4 independent confluence factors must align — SR, candle, RSI, trend |
| S8: Tokyo Range | Session detection mandatory — only valid during or just after Tokyo session |
| S11: Asian Range Fade | Mean-reversion — treated differently from trend strategies in risk scoring |
| S13: London Breakout | London open detection required — GMT session handling |
| S20: Post-News | News calendar required — fires only after a confirmed high-impact release |

---

### 5. Evaluation Orchestrator (`scheduler.py` — expanded)

The H1 close job now calls the full evaluation pipeline:

1. Pull latest OHLCV from MT5 for all timeframes
2. Compute shared indicator library once (not per-strategy)
3. Fetch market context (US10Y, DXY, VIX, news flag)
4. Loop through all 20 strategy modules:
   a. Instantiate strategy with shared data
   b. Run 4 agent functions
   c. Run debate engine
   d. Capture `StrategyResult`
5. Batch-write all 20 results to SQLite
6. Check for any VALID TRADE results → trigger notification (Phase 4)
7. Log evaluation duration and any errors

The entire evaluation cycle for all 20 strategies should complete within 10–30 seconds on a standard machine.

---

### 6. StrategyResult Output Format

Every strategy evaluation produces a `StrategyResult` with these fields:

```
strategy_id         : int (1–20)
strategy_name       : str
strategy_type       : str (Trend / Breakout / Mean Reversion / Hybrid / Event-Driven)
status              : str (VALID_TRADE / WAIT_FOR_LEVELS / NO_TRADE)
direction           : str (BUY / SELL / None)
entry               : float or None
sl                  : float or None
tp1                 : float or None
tp2                 : float or None
tp3                 : float or None
rrr                 : float or None
confidence          : int (0–100)
probability         : int (0–100)
timeframes          : list[str]
wait_zone           : str or None (only for WAIT_FOR_LEVELS)
conditions_to_meet  : list[str] (only for WAIT_FOR_LEVELS)
reasons_for         : list[str]
reasons_against     : list[str]
verdict_summary     : str
evaluated_at        : datetime (UTC)
agent_scores        : dict (for transparency / debugging)
```

---

## Phase 2 Success Criteria

By the end of Phase 2, the following must all be true:

1. `GET /api/strategies` returns 20 strategy results with correct structure
2. Each result has a valid verdict (VALID / WAIT / NO TRADE) with reasoning
3. VALID TRADE results always have entry, SL, and at least TP1 populated
4. NO TRADE results have at least one reason_against populated
5. The H1 scheduler job runs and completes without error — visible in logs
6. All 20 results are written to SQLite after each evaluation cycle
7. Agent scores are visible in the result for debugging
8. Strategy S3 returns NO TRADE if Fed-BoJ spread check fails (macro gate test)
9. Strategy S8 and S13 return NO TRADE outside their session windows (session gate test)
10. `GET /api/strategy/1` returns the full debate detail for Strategy 1

---

## Phase 2 Development Order (Recommended)

Build in this sequence to validate incrementally:

1. Base class + indicator library + shared data structures
2. Debate engine (with mock agent data to test verdict logic)
3. Strategies 1, 6, 7 (pure trend — simplest logic, good for framework validation)
4. Remaining trend strategies: 2, 3, 4, 5, 10, 12
5. Session-based strategies: 8, 11, 13, 19
6. Price action strategies: 15, 17, 18
7. Mean reversion strategies: 14, 16
8. Breakout strategies: 9
9. Event-driven: 20 (most complex — calendar dependency)

---

## Known Constraints for This Phase

- Strategy 4 (US10Y Yield) depends on FRED data being fresh — evaluate this strategy only if FRED data is < 6 hours old
- Strategy 20 (Post-News) should only fire within 90 minutes of a confirmed high-impact event — calendar data must be current
- Mean reversion strategies (11, 14, 16) require a trending regime filter to avoid false signals in trending markets — this regime detection must be built into those modules
- Fibonacci levels (Strategy 17) require identifying the most recent clean impulse leg — the swing detection algorithm must be reliable before this strategy is enabled

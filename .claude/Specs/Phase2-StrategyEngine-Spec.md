# Phase 2 — StrategyEngine Specification

---

## Document Control

| Field        | Value                            |
|--------------|----------------------------------|
| Document ID  | SPEC-PHASE-2-v1.1                |
| Version      | v1.1                             |
| Status       | Draft                            |
| Created      | 2026-04-24                       |
| Author       | USDJPY Smart Agent Project       |
| Phase        | 2 of 5                           |
| Phase Name   | StrategyEngine                   |

### Change History

| Version | Date       | Author | Summary of Changes |
|---------|------------|--------|--------------------|
| v1.0    | 2026-04-24 | —      | Initial draft      |
| v1.1    | 2026-04-24 | —      | Resolved OQ-2-01 through OQ-2-05: confidence normalization formula, probability weights, S11 session window, S17 impulse threshold, MT5 insufficient bars behaviour |

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for Phase 2 of the USDJPY Smart Agent project: the Strategy Engine. It defines what the strategy evaluation system must do — covering all 20 strategy modules, the 4-agent debate framework, the verdict generation engine, the shared indicator library, and the scheduled evaluation orchestration — without prescribing implementation detail. This document is intended for use by the developer implementing Phase 2 and as a reference during testing and acceptance.

### 1.2 Scope

This specification covers:
- The base strategy class and shared indicator library
- The `StrategyResult` output data structure
- All 20 individual strategy evaluation modules (S1–S20)
- The `OpportunityAgent` and `RiskAgent` scoring functions
- The `DebateEngine` aggregation and verdict generation logic
- The evaluation orchestrator (H1-close trigger through full 20-strategy cycle)
- The write path from completed `StrategyResult` objects to persistent storage
- The REST API endpoints that expose strategy results to callers

This specification does not cover:
- Phase 1 data feed infrastructure (MT5, FRED, yfinance, calendar) — assumed complete
- The SQLite schema definition — specified in Phase 1
- Frontend display of results — specified in Phase 3
- Telegram alert delivery — specified in Phase 4
- MT5 order execution — specified in Phase 5

### 1.3 Definitions and Abbreviations

| Term / Acronym     | Definition |
|--------------------|------------|
| MT5                | MetaTrader 5 — the trading terminal providing OHLCV price data |
| OHLCV              | Open, High, Low, Close, Volume — standard candlestick data fields |
| H1 / H4 / D        | 1-hour / 4-hour / Daily candlestick timeframe |
| M15 / M30          | 15-minute / 30-minute candlestick timeframe |
| ATR                | Average True Range — volatility measure over N periods |
| EMA                | Exponential Moving Average |
| MACD               | Moving Average Convergence Divergence (12, 26, 9) |
| RSI                | Relative Strength Index |
| ADX                | Average Directional Index — trend-strength measure |
| DMI                | Directional Movement Index (+DI / -DI) |
| Ichimoku           | Ichimoku Kinko Hyo — 5-line Japanese candlestick system |
| Donchian           | Donchian Channel — N-period high/low envelope |
| Keltner            | Keltner Channel — EMA ± ATR-based envelope |
| Fibonacci / Fib    | Fibonacci retracement and extension levels |
| FRED               | Federal Reserve Economic Data API |
| DXY                | US Dollar Index |
| VIX                | CBOE Volatility Index |
| US10Y              | US 10-Year Treasury Yield |
| BoJ                | Bank of Japan |
| Fed                | US Federal Reserve |
| RRR                | Risk-Reward Ratio (reward divided by risk) |
| SL                 | Stop Loss — price level at which a trade is exited to limit losses |
| TP                 | Take Profit — price level at which a trade is exited to capture gains |
| TP1 / TP2 / TP3    | Take Profit levels 1, 2, and 3 respectively |
| VALID TRADE        | Verdict: strategy conditions fully met, all parameters populated |
| WAIT FOR LEVELS    | Verdict: direction is valid but price has not reached the entry zone |
| NO TRADE           | Verdict: conditions not met or risk factors override |
| FR                 | Functional Requirement |
| NFR                | Non-Functional Requirement |
| AC                 | Acceptance Criterion |
| UTC                | Coordinated Universal Time — all timestamps in the system |
| TK Cross           | Tenkan/Kijun crossover signal in Ichimoku system |
| Kumo               | The cloud region in Ichimoku (between Senkou A and B) |
| HTF                | Higher Timeframe |
| GTM                | Greenwich Mean Time (same as UTC for purposes of this system) |

### 1.4 References

- USDJPY Smart Agent System Architecture — `.claude/Documents/system_architecture.md`
- Phase 2 Build Guide — `.claude/Documents/02-Phase2-StrategyEngine.md`
- USDJPY Algorithmic Strategy Reference — `USDJPY_Algo_Strategy_Reference.md`
- Phase 1 Foundation Specification (predecessor) — `.claude/Specs/Phase1-Foundation-Spec.md` (if produced)
- APScheduler documentation — https://apscheduler.readthedocs.io/
- MetaTrader 5 Python API documentation

---

## 2. System Context

### 2.1 Phase Position in System

Phase 2 is the second of five phases. It sits directly on top of Phase 1 (data pipeline, SQLite schema, FastAPI skeleton) and is consumed by Phase 3 (frontend), Phase 4 (Telegram notifications), and Phase 5 (automated trading). Phase 2 is the computational core of the system: it transforms raw market data into structured trade verdicts.

```
Phase 1: Data Layer  →  Phase 2: Strategy Engine  →  Phase 3: Frontend
                                    ↓                      ↑
                              Phase 4: Notifications       |
                                    ↓                      |
                              Phase 5: Execution    ←------+
```

### 2.2 Phase Goal

Phase 2 must deliver a fully operational, scheduled evaluation cycle in which all 20 strategy modules are independently evaluated on every H1 candle close, each through a 4-agent debate, producing structured verdicts that are persisted to SQLite and immediately available via the REST API.

### 2.3 In Scope for This Phase

- Base strategy class with shared interface (`evaluate()`)
- Shared indicator library computed once per evaluation cycle
- All 20 strategy evaluation modules (S1–S20)
- `OpportunityAgent` class with two independent instances per strategy
- `RiskAgent` class with two independent instances per strategy
- `DebateEngine` aggregation logic, scoring formula, alignment bonuses, conflict penalties, and critical risk override rules
- Verdict generation logic: VALID TRADE / WAIT FOR LEVELS / NO TRADE
- `StrategyResult` dataclass with all required fields
- Evaluation orchestrator: H1-triggered full 20-strategy pipeline
- Batch write of all 20 `StrategyResult` objects to SQLite after each cycle
- REST endpoints: `GET /api/strategies` and `GET /api/strategy/{id}`
- Logging of evaluation cycle duration and per-strategy errors

### 2.4 Out of Scope for This Phase

- MT5 data connection, FRED data fetching, yfinance, or calendar data ingestion (Phase 1)
- SQLite schema creation or migration scripts (Phase 1)
- Frontend rendering of strategy verdicts (Phase 3)
- Telegram notifications on VALID TRADE verdicts (Phase 4)
- MT5 order placement or execution (Phase 5)
- Backtesting or historical replay mode
- Dynamic parameter tuning or machine learning components
- Multi-instrument support (this system is USDJPY only)
- User authentication or access control
- COT (Commitment of Traders) report ingestion — treated as out of scope; the strategy reference notes it as an optional filter

### 2.5 Predecessor Dependencies

The following Phase 1 deliverables must be complete and verified before Phase 2 implementation begins:

- MT5 connection established and returning OHLCV DataFrames for M15, M30, H1, H4, and D timeframes
- FRED API returning US 10Y yield and Fed Funds Rate, with timestamp metadata available
- yfinance returning DXY and VIX values, with last-fetch timestamp available
- Forex Factory iCal parser returning a list of scheduled high-impact events with UTC timestamps
- SQLite `signals` and `market_context` tables created per schema in Phase 1
- `signal_store.py` write functions accepting a `StrategyResult` object and persisting it
- APScheduler running with an H1-close job hook available for Phase 2 to populate
- FastAPI application skeleton running and accepting route registration from Phase 2 API modules
- `config.py` containing all configurable thresholds (confidence, probability, RRR, spread limit, intervention price)

---

## 3. Functional Requirements

Requirements are numbered FR-2-01 through FR-2-91 and grouped by component.

---

### 3.1 Base Strategy Class

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-01  | The system SHALL provide a `BaseStrategy` class that all 20 strategy modules inherit from. | MUST | Given any strategy module, when inspected, then it inherits from `BaseStrategy`. |
| FR-2-02  | The `BaseStrategy` class SHALL define an `evaluate()` method that every subclass must implement. | MUST | Given a strategy subclass that does not implement `evaluate()`, when instantiated, then a `NotImplementedError` is raised. |
| FR-2-03  | The `BaseStrategy` class SHALL accept pre-computed OHLCV DataFrames and market context as constructor arguments, not fetch them internally. | MUST | Given any strategy's `evaluate()` call, when execution completes, then zero external API calls have been made by the strategy. |
| FR-2-04  | The `BaseStrategy` class SHALL enforce that any result with status VALID_TRADE has `entry`, `sl`, and `tp1` fields all populated with non-null numeric values. | MUST | Given a `StrategyResult` with status VALID_TRADE and a null `entry`, `sl`, or `tp1`, when the result is returned from `evaluate()`, then a `ValueError` is raised before the result is passed to the debate engine. |
| FR-2-05  | The `BaseStrategy` class SHALL provide access to a shared indicator computation utility containing all indicators listed in Section 5.1. | MUST | Given a strategy that requires EMA(200) on D, when `evaluate()` runs, then the value is read from the shared indicator cache, not recomputed. |
| FR-2-06  | The `BaseStrategy` class SHALL provide a session detection utility returning one of: TOKYO, LONDON, NEW_YORK, or OFF for the current UTC time. | MUST | Given a UTC time of 01:00, when session detection is called, then TOKYO is returned. Given 08:00 UTC, LONDON is returned. Given 13:00 UTC, NEW_YORK is returned. Given 22:00 UTC, OFF is returned. |
| FR-2-07  | The `BaseStrategy` class SHALL provide a swing high/low detection utility accepting a price series and a lookback period, returning the most recent confirmed swing high and swing low prices. | MUST | Given a 20-bar OHLCV series with an identifiable local peak at bar -5, when swing detection is called, then the peak is returned as the most recent swing high. |
| FR-2-08  | The `BaseStrategy` class SHALL expose the economic calendar "news imminent" flag (high-impact event within 30 minutes) as a property accessible to all strategies. | MUST | Given a high-impact event scheduled at 14:00 UTC and current time 13:35 UTC, when any strategy checks the news flag, then True is returned. |

---

### 3.2 Shared Indicator Library

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-09  | The system SHALL compute all shared indicators once per evaluation cycle before any strategy module is invoked. | MUST | Given a cycle with 20 strategies, when the cycle completes, then indicator computation logs show exactly one computation per indicator per timeframe, not 20. |
| FR-2-10  | The shared indicator library SHALL compute EMA(20), EMA(50), and EMA(200) on H1, H4, and Daily timeframes. | MUST | Given 200+ bars of H1 data, when the library is computed, then EMA values for periods 20, 50, and 200 are present and finite. |
| FR-2-11  | The shared indicator library SHALL compute MACD with parameters (12, 26, 9) on H1 and H4, returning the MACD line, signal line, and histogram. | MUST | Given OHLCV data, when MACD is computed, then MACD line, signal line, and histogram are all returned as time-indexed series. |
| FR-2-12  | The shared indicator library SHALL compute ATR(14) on H1 and H4. | MUST | Given OHLCV data, when ATR(14) is computed, then the returned value is positive and expressed in price units. |
| FR-2-13  | The shared indicator library SHALL compute RSI(14) on H1 and H4, returning values in the range [0, 100]. | MUST | Given OHLCV data, when RSI is computed, then all returned values are between 0 and 100 inclusive. |
| FR-2-14  | The shared indicator library SHALL compute Bollinger Bands with parameters (20, 2σ) on H1 and H4, returning upper band, middle band (EMA20), and lower band. | MUST | Given OHLCV data, when Bollinger Bands are computed, then upper band > middle band > lower band for all non-degenerate bars. |
| FR-2-15  | The shared indicator library SHALL compute all five Ichimoku lines — Tenkan-sen (9), Kijun-sen (26), Senkou Span A, Senkou Span B (52), and Chikou Span — on H4 and Daily. | MUST | Given at least 52 bars of data, when Ichimoku is computed, then all five lines are returned with correct period calculations. |
| FR-2-16  | The shared indicator library SHALL compute ADX(14) and DMI (+DI14, -DI14) on H4. | MUST | Given OHLCV data, when ADX/DMI is computed, then ADX is a non-negative value and +DI and -DI are non-negative values. |
| FR-2-17  | The shared indicator library SHALL compute the 20-period Donchian Channel (highest high and lowest low over 20 bars) on H4 and Daily. | MUST | Given OHLCV data, when Donchian is computed, then the upper band equals the 20-period rolling maximum high and the lower band equals the 20-period rolling minimum low. |
| FR-2-18  | The shared indicator library SHALL compute a Keltner Channel on H1 using EMA(20) ± 1.5 × ATR(14). | MUST | Given OHLCV data, when Keltner is computed, then the channel width equals 3 × ATR(14). |
| FR-2-19  | The shared indicator library SHALL compute Classic Daily Pivot Points (PP, R1, R2, R3, S1, S2, S3) using the prior Daily bar's high, low, and close. | MUST | Given a prior Daily bar with H=151.50, L=150.50, C=151.00, when pivot points are computed, then PP = 151.00, R1 = 151.50, S1 = 150.50. |
| FR-2-20  | The shared indicator library SHALL detect the most recent bullish and bearish engulfing candles on H4 and Daily, returning the bar index of each. | MUST | Given an H4 bar where the body fully engulfs the prior bar's body in the bullish direction, when detection runs, then that bar index is returned as the most recent bullish engulfing. |
| FR-2-21  | The shared indicator library SHALL detect inside bars on Daily and H4, returning a boolean flag for whether the most recent closed bar is an inside bar relative to its mother bar. | MUST | Given a bar whose high is lower than the prior bar's high AND whose low is higher than the prior bar's low, when detection runs, then the inside bar flag is True. |

---

### 3.3 StrategyResult Data Structure

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-22  | The system SHALL define a `StrategyResult` dataclass with exactly the fields specified in the Phase 2 build guide: `strategy_id`, `strategy_name`, `strategy_type`, `status`, `direction`, `entry`, `sl`, `tp1`, `tp2`, `tp3`, `rrr`, `confidence`, `probability`, `timeframes`, `wait_zone`, `conditions_to_meet`, `reasons_for`, `reasons_against`, `verdict_summary`, `evaluated_at`, and `agent_scores`. | MUST | Given any strategy's completed evaluation, when the result is inspected, then all 21 fields are present with correct types. |
| FR-2-23  | The `status` field of `StrategyResult` SHALL only contain one of three values: VALID_TRADE, WAIT_FOR_LEVELS, or NO_TRADE. | MUST | Given any `StrategyResult`, when `status` is inspected, then it is one of the three defined values and no other. |
| FR-2-24  | The `confidence` field SHALL be an integer in the range [0, 100]. | MUST | Given any `StrategyResult`, when `confidence` is inspected, then it is an integer between 0 and 100 inclusive. |
| FR-2-25  | The `probability` field SHALL be an integer in the range [0, 100]. | MUST | Given any `StrategyResult`, when `probability` is inspected, then it is an integer between 0 and 100 inclusive. |
| FR-2-26  | The `rrr` field SHALL be calculated as `(tp1 - entry) / (entry - sl)` for long trades and `(entry - tp1) / (sl - entry)` for short trades, rounded to two decimal places. | MUST | Given entry=150.00, sl=149.50, tp1=151.00, when RRR is computed for a long, then rrr = 2.00. |
| FR-2-27  | The `evaluated_at` field SHALL be set to the current UTC datetime at the moment the strategy's `evaluate()` method completes. | MUST | Given an evaluation call at 09:02:15 UTC, when `evaluated_at` is inspected, then it contains a UTC datetime equal to or within 5 seconds of 09:02:15. |
| FR-2-28  | The `wait_zone` and `conditions_to_meet` fields SHALL be non-null and populated only when `status` is WAIT_FOR_LEVELS. | MUST | Given a `StrategyResult` with status VALID_TRADE, when `wait_zone` is inspected, then it is null/None. |
| FR-2-29  | The `agent_scores` field SHALL contain the raw scores from all four agent evaluations (OppAgent1, OppAgent2, RiskAgent1, RiskAgent2) indexed by agent name. | MUST | Given any `StrategyResult`, when `agent_scores` is inspected, then it contains entries for all four agents with numeric score values. |

---

### 3.4 OpportunityAgent

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-30  | The system SHALL provide an `OpportunityAgent` class that accepts pre-computed indicator data and returns a structured opportunity score. | MUST | Given indicator data passed to `OpportunityAgent.score()`, when the method returns, then zero external API calls have been made. |
| FR-2-31  | The `OpportunityAgent` SHALL evaluate five dimensions: entry condition completeness, signal timing precision, multi-timeframe confluence, momentum alignment, and entry zone cleanliness (not mid-move). | MUST | Given all five dimensions scoring 0, when `OpportunityAgent.score()` returns, then the aggregate score is 0. Given all five scoring their maximum, then the aggregate score is at maximum. |
| FR-2-32  | The `OpportunityAgent` SHALL return a numeric score per active dimension (0–10 each) and a list of human-readable strings describing positive findings. | MUST | Given a strategy with 3 active dimensions, when `score()` returns, then exactly 3 dimension scores and at least one `reasons_for` string are returned. |
| FR-2-33  | Two independent `OpportunityAgent` instances SHALL be created per strategy per evaluation cycle, both using the same indicator data but executing independently. | MUST | Given both OpportunityAgent instances for the same strategy and same data, when their `score()` methods are called independently, then each completes and returns a result without reading state from the other. |
| FR-2-34  | The `OpportunityAgent` SHALL allow each strategy to declare which of the 11 scoring dimensions are active for that strategy; inactive dimensions SHALL be excluded from the aggregate score. | MUST | Given a strategy that declares only 7 active dimensions, when `score()` runs, then only 7 dimensions contribute to the aggregate. |

---

### 3.5 RiskAgent

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-35  | The system SHALL provide a `RiskAgent` class that accepts pre-computed indicator data and returns a structured risk score and list of risk flags. | MUST | Given indicator data passed to `RiskAgent.score()`, when the method returns, then zero external API calls have been made. |
| FR-2-36  | The `RiskAgent` SHALL evaluate six risk dimensions: higher-timeframe conflict, imminent high-impact news, stop-loss placement quality, risk-reward adequacy, spread/liquidity conditions, and USDJPY-specific structural risks (intervention zone, carry unwind signals). | MUST | Given a scenario with all six risk dimensions triggered, when `RiskAgent.score()` returns, then all six are reflected in the risk score and risk flags list. |
| FR-2-37  | The `RiskAgent` SHALL return a `risk_score` (0–10, where 10 = maximum risk) and a list of `risk_flags` as human-readable strings. | MUST | Given a scenario with no risk present, when `RiskAgent.score()` returns, then `risk_score` is 0 and `risk_flags` is an empty list. |
| FR-2-38  | The `RiskAgent` SHALL flag a critical risk when USDJPY price is above 155.00 and the evaluated strategy direction is long. | MUST | Given USDJPY price = 155.50 and strategy direction = BUY, when `RiskAgent.score()` runs, then a critical risk flag for intervention zone is included. |
| FR-2-39  | The `RiskAgent` SHALL flag a critical risk when MT5-reported spread exceeds 3 pips. | MUST | Given MT5 spread = 3.2 pips, when `RiskAgent.score()` runs, then a critical risk flag for illiquid spread is included. |
| FR-2-40  | Two independent `RiskAgent` instances SHALL be created per strategy per evaluation cycle, both using the same indicator data but executing independently. | MUST | Given both RiskAgent instances for the same strategy and same data, when their `score()` methods are called independently, then each completes and returns a result without reading state from the other. |

---

### 3.6 DebateEngine

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-41  | The system SHALL provide a `DebateEngine` that accepts the outputs of two `OpportunityAgent` instances and two `RiskAgent` instances and produces a final `confidence` score, `probability` score, and verdict. | MUST | Given four agent outputs, when `DebateEngine.evaluate()` returns, then `confidence`, `probability`, and `status` are all populated. |
| FR-2-42  | The `DebateEngine` SHALL compute `opportunity_score` as the arithmetic mean of OppAgent1's aggregate score and OppAgent2's aggregate score. | MUST | Given OppAgent1 score = 7.0 and OppAgent2 score = 5.0, when `DebateEngine.evaluate()` runs, then `opportunity_score` = 6.0. |
| FR-2-43  | The `DebateEngine` SHALL compute `opposition_score` as the arithmetic mean of RiskAgent1's `risk_score` and RiskAgent2's `risk_score`. | MUST | Given RiskAgent1 risk_score = 4.0 and RiskAgent2 risk_score = 6.0, when `DebateEngine.evaluate()` runs, then `opposition_score` = 5.0. |
| FR-2-44  | The `DebateEngine` SHALL apply an `alignment_bonus` of +5 when both `OpportunityAgent` aggregate scores are within 1.5 of each other. | MUST | Given OppAgent1 = 7.0, OppAgent2 = 6.0 (difference = 1.0), when bonus logic runs, then alignment_bonus = +5. |
| FR-2-45  | The `DebateEngine` SHALL apply a `conflict_penalty` of -5 when both `OpportunityAgent` aggregate scores differ by more than 3.0. | MUST | Given OppAgent1 = 8.0, OppAgent2 = 4.0 (difference = 4.0), when penalty logic runs, then conflict_penalty = -5. |
| FR-2-46  | The `DebateEngine` SHALL apply a `risk_alignment_penalty` of -5 when both `RiskAgent` instances return the same critical risk flag string. | MUST | Given both RiskAgents returning the flag "HTF_BEARISH_CONFLICT", when penalty logic runs, then risk_alignment_penalty = -5. |
| FR-2-47  | The `DebateEngine` SHALL compute `net_score` as: `opportunity_score - opposition_score + alignment_bonus - conflict_penalty - risk_alignment_penalty`. | MUST | Given opportunity_score=7, opposition_score=3, alignment_bonus=5, conflict_penalty=0, risk_alignment_penalty=0, when net_score is computed, then net_score = 9. |
| FR-2-48  | The `DebateEngine` SHALL normalize `net_score` into a `confidence` integer in the range [0, 100] using the formula: `confidence = clamp(round(((net_score + 20) / 35) × 100), 0, 100)`. The theoretical bounds are net_score = +15 (max, maps to 100) and net_score = -20 (min, maps to 0). | MUST | Given net_score = +15, when normalized, then confidence = 100. Given net_score = -20, then confidence = 0. Given net_score = 0, then confidence = 57. |
| FR-2-49  | The `DebateEngine` SHALL compute `probability` as an equally weighted combination of three sub-scores (each contributing 33.3%): strategy rule compliance score, market structure quality score, and trend alignment score — expressed as an integer in [0, 100]. Equal weighting is used so that mean-reversion and event-driven strategies are not systematically penalised by a trend-alignment-heavy formula. | MUST | Given rule_compliance=100, structure_quality=100, trend_alignment=100, when probability is computed, then probability = 100. Given all three = 0, then probability = 0. Given rule_compliance=90, structure_quality=60, trend_alignment=30, then probability = 60. |
| FR-2-50  | The `DebateEngine` SHALL assign verdict VALID_TRADE only when: `confidence` ≥ 75, `probability` ≥ 70, `rrr` ≥ 1.5, and no critical risk flags are present. | MUST | Given confidence=74, probability=72, rrr=2.0, no critical flags, when verdict is computed, then status = NO_TRADE (confidence threshold not met). |
| FR-2-51  | The `DebateEngine` SHALL assign verdict WAIT_FOR_LEVELS when strategy rules are partially met and price has not yet reached the ideal entry zone, even if confidence/probability thresholds would otherwise be satisfied. | MUST | Given a strategy with direction confirmed but price outside the entry zone, when verdict logic runs, then status = WAIT_FOR_LEVELS. |
| FR-2-52  | The `DebateEngine` SHALL override any verdict to NO_TRADE when a high-impact news event is scheduled within 30 minutes of evaluation time, regardless of confidence or probability scores. | MUST | Given confidence=90, probability=85, rrr=3.0, and a high-impact event in 20 minutes, when verdict is computed, then status = NO_TRADE with rejection reason "NEWS_IMMINENT". |
| FR-2-53  | The `DebateEngine` SHALL override any verdict to NO_TRADE when USDJPY price exceeds 155.00 and the strategy direction is long, regardless of all other scores. | MUST | Given confidence=90, probability=85, rrr=3.0, USDJPY=156.00, direction=BUY, when verdict is computed, then status = NO_TRADE with rejection reason "INTERVENTION_ZONE". |
| FR-2-54  | The `DebateEngine` SHALL override any verdict to NO_TRADE when MT5-reported spread exceeds 3 pips. | MUST | Given spread=3.5 pips, when verdict logic runs, then status = NO_TRADE with rejection reason "SPREAD_TOO_WIDE". |
| FR-2-55  | The `DebateEngine` SHALL override any verdict to NO_TRADE when both `RiskAgent` instances flag the same structural invalidation. | MUST | Given both RiskAgents returning the same structural invalidation flag, when verdict logic runs, then status = NO_TRADE regardless of opportunity scores. |

---

### 3.7 Individual Strategy Modules — Common Requirements

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-56  | Each of the 20 strategy modules SHALL implement `check_long_conditions()` and `check_short_conditions()` functions returning structured evaluation results. | MUST | Given any of the 20 strategy modules, when both functions are called with valid indicator data, then neither raises an unhandled exception. |
| FR-2-57  | Each strategy module SHALL define a `StrategyConfig` dataclass containing all parameters from the strategy reference document (indicator settings, thresholds, timeframes, session filters). | MUST | Given any strategy module, when its `StrategyConfig` is inspected, then all parameters defined in the strategy reference for that strategy are present. |
| FR-2-58  | Each strategy module SHALL define which of the 11 scoring dimensions are active for that strategy; this list SHALL be passed to both `OpportunityAgent` instances during evaluation. | MUST | Given Strategy 8 (Tokyo Breakout) which does not use RSI divergence, when its active dimension list is inspected, then RSI divergence is not included. |
| FR-2-59  | Each strategy module SHALL compute its own stop loss price using logic specific to that strategy (not a global formula), and the stop loss SHALL always be on the correct side of the entry price. | MUST | Given a long entry at 150.00, when stop loss is computed, then sl < 150.00 for all long strategies. Given a short entry at 150.00, then sl > 150.00. |
| FR-2-60  | Each strategy module SHALL compute at minimum TP1 and TP2; TP3 is optional. TP prices SHALL always be on the correct side of the entry price relative to direction. | MUST | Given a long entry at 150.00, when TP1 is computed, then tp1 > 150.00. For a short, tp1 < 150.00. |

---

### 3.8 Individual Strategy Modules — Strategy-Specific Requirements

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-61  | Strategy S1 (Multi-Timeframe Trend) SHALL require alignment across all three timeframes (Daily bias, H4 structure, H1 entry) before scoring any opportunity conditions. | MUST | Given Daily bullish but H4 lower-high absent, when S1 evaluates, then status is NO_TRADE or WAIT_FOR_LEVELS, not VALID_TRADE. |
| FR-2-62  | Strategy S2 (Ichimoku) SHALL evaluate all four Ichimoku entry conditions (price vs Kumo, TK cross, Chikou span, future Kumo direction) before scoring any opportunity. | MUST | Given only 3 of 4 Ichimoku conditions true, when S2 evaluates, then status is NO_TRADE or WAIT_FOR_LEVELS. |
| FR-2-63  | Strategy S3 (Carry-Trade Pullback) SHALL evaluate the macro gate first: if the Fed-BoJ policy rate spread is ≤ 2.5%, the strategy SHALL return NO_TRADE without evaluating any technical conditions. | MUST | Given Fed rate = 2.0%, BoJ rate = 0.75% (spread = 1.25%), when S3 evaluates, then status = NO_TRADE and no technical indicators are evaluated. |
| FR-2-64  | Strategy S4 (US10Y Yield Correlation) SHALL return NO_TRADE if the FRED data timestamp is more than 6 hours old relative to evaluation time. | MUST | Given FRED data last fetched 7 hours ago, when S4 evaluates, then status = NO_TRADE with reason "FRED_DATA_STALE". |
| FR-2-65  | Strategy S5 (Confluence System) SHALL require all four confluence factors — support/resistance, candle signal, RSI condition, and trend alignment — to be active before issuing a VALID_TRADE verdict. | MUST | Given only 3 of 4 confluence factors met, when S5 evaluates, then status is NO_TRADE or WAIT_FOR_LEVELS. |
| FR-2-66  | Strategy S6 (MACD + 200 EMA) SHALL require both the MACD crossover signal and price position relative to the 200 EMA to be in agreement before scoring opportunity conditions. | MUST | Given MACD bullish cross but price below 200 EMA, when S6 evaluates, then no VALID_TRADE verdict is issued. |
| FR-2-67  | Strategy S7 (ADX + DMI) SHALL use ADX(14) on H4 as a regime filter; the strategy SHALL not issue a VALID_TRADE verdict when ADX is below 20. | MUST | Given H4 ADX = 17, when S7 evaluates, then status is NO_TRADE (non-trending regime). |
| FR-2-68  | Strategy S8 (Tokyo Range Breakout) SHALL perform mandatory session detection before any evaluation; if the current session is not TOKYO or within the first 2 hours post-Tokyo, the strategy SHALL return NO_TRADE immediately. | MUST | Given UTC time = 12:00 (London session), when S8 evaluates, then status = NO_TRADE with reason "OUTSIDE_SESSION_WINDOW". |
| FR-2-69  | Strategy S9 (Keltner Channel Breakout) SHALL require a confirmed close outside the Keltner Channel before issuing any opportunity score. | MUST | Given price touching but not closing outside the Keltner upper band, when S9 evaluates, then no VALID_TRADE is issued. |
| FR-2-70  | Strategy S10 (50/200 EMA Crossover) SHALL evaluate the crossover state on H4 and require a subsequent pullback to the crossover zone before scoring entry conditions. | MUST | Given a completed bullish EMA crossover but price still at the crossover level (no pullback), when S10 evaluates, then status is WAIT_FOR_LEVELS. |
| FR-2-71  | Strategy S11 (Asian Session Range Fade) SHALL include a trending regime filter; if the H4 ADX indicates a trending market (ADX > 25), the strategy SHALL return NO_TRADE to avoid fading a strong trend. | MUST | Given H4 ADX = 30, when S11 evaluates, then status = NO_TRADE with reason "TRENDING_REGIME_DETECTED". |
| FR-2-71b | Strategy S11 SHALL define the Asian session range as the high and low of price between 00:00 and 06:00 UTC. This window captures the core Tokyo session and BoJ fix flows (00:55 UTC) while excluding London pre-market activity (07:00+ UTC) which distorts the range with directional moves. Fade signals are evaluated after 06:00 UTC when price breaks outside the recorded range. | MUST | Given a range high established between 00:00–06:00 UTC, when S11 evaluates at 08:00 UTC with price above that range high, then a fade signal (short) is considered. Given evaluation at 05:30 UTC (inside the range-building window), when S11 evaluates, then status = NO_TRADE with reason "RANGE_BUILDING". |
| FR-2-72  | Strategy S12 (Donchian/Turtle Breakout) SHALL use the 20-period Donchian Channel on Daily and require a confirmed Daily close above or below the channel before issuing an entry signal. | MUST | Given a Daily close at the 20-period high (exactly equal), when S12 evaluates, then the breakout condition is considered met. |
| FR-2-73  | Strategy S13 (London Open Breakout) SHALL perform mandatory session detection before any evaluation; if the current time is outside the London open window (07:00–09:00 UTC), the strategy SHALL return NO_TRADE immediately. | MUST | Given UTC time = 06:55, when S13 evaluates, then status = NO_TRADE with reason "OUTSIDE_SESSION_WINDOW". |
| FR-2-74  | Strategy S14 (Bollinger Band Mean Reversion) SHALL include a trending regime filter; if the market is in a trending state (H4 ADX > 25 or price outside 2σ Bollinger Band for more than 3 consecutive bars), the strategy SHALL return NO_TRADE. | MUST | Given H4 ADX = 28, when S14 evaluates, then status = NO_TRADE with reason "TRENDING_REGIME_DETECTED". |
| FR-2-75  | Strategy S15 (Engulfing Candle at Key Level) SHALL require both a confirmed engulfing candle pattern AND proximity to a defined key level (support, resistance, or pivot) before scoring opportunity conditions. | MUST | Given a bullish engulfing candle mid-range with no key level within 20 pips, when S15 evaluates, then no VALID_TRADE verdict is issued. |
| FR-2-76  | Strategy S16 (RSI Mean Reversion) SHALL include a trending regime filter; if H4 RSI trend direction confirms a strong trend (RSI sustained above 60 for longs seeking a short, or below 40 for shorts seeking a long), the strategy SHALL return NO_TRADE. | MUST | Given H4 RSI = 72 sustained for 4+ bars when evaluating a short mean-reversion entry, when S16 evaluates, then status = NO_TRADE with reason "TRENDING_REGIME_DETECTED". |
| FR-2-77  | Strategy S17 (Fibonacci Pullback) SHALL identify the most recent clean impulse leg using the swing detection utility before computing Fibonacci levels; a qualifying impulse leg MUST satisfy both conditions: (1) leg size ≥ 2.0 × H4 ATR(14), AND (2) leg size ≥ 60 pips absolute. If no qualifying impulse leg is detectable in the lookback window, the strategy SHALL return NO_TRADE. The ATR multiple ensures the threshold adapts to the current volatility regime; the 60-pip floor prevents Fibonacci levels from being drawn on trivially small moves during extremely low-volatility conditions. | MUST | Given H4 ATR = 50 pips and a candidate impulse of 90 pips (1.8× ATR), when S17 evaluates, then status = NO_TRADE with reason "NO_CLEAN_IMPULSE_DETECTED" (fails ATR multiple). Given H4 ATR = 40 pips and a 90-pip impulse (2.25× ATR, above 60 pip floor), then Fibonacci levels are computed. |
| FR-2-78  | Strategy S18 (Inside Bar Breakout) SHALL use the inside bar detection utility and return WAIT_FOR_LEVELS when an inside bar is confirmed but the breakout has not yet occurred. | MUST | Given a confirmed inside bar on Daily and no breakout beyond the mother bar range, when S18 evaluates, then status = WAIT_FOR_LEVELS with the breakout levels populated in `wait_zone`. |
| FR-2-79  | Strategy S19 (Daily Pivot Breakout) SHALL compute Classic Pivot Points from the prior Daily bar and evaluate price position relative to R1/S1 levels as the primary entry trigger. | MUST | Given price breaking above R1 on H1 with confirmation, when S19 evaluates, then a VALID_TRADE or WAIT_FOR_LEVELS result is produced in the long direction. |
| FR-2-80  | Strategy S20 (Post-News Breakout) SHALL return NO_TRADE if no confirmed high-impact economic event has occurred within the prior 90 minutes at evaluation time. | MUST | Given that the last high-impact event was 95 minutes ago, when S20 evaluates, then status = NO_TRADE with reason "OUTSIDE_POST_NEWS_WINDOW". |
| FR-2-81  | Strategy S20 SHALL return NO_TRADE if the economic calendar data is not current (last fetched more than 24 hours ago). | MUST | Given calendar data last refreshed 25 hours ago, when S20 evaluates, then status = NO_TRADE with reason "CALENDAR_DATA_STALE". |

---

### 3.9 Evaluation Orchestrator

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-82  | The evaluation orchestrator SHALL trigger automatically on each H1 candle close, firing at HH:02:00 UTC (2 minutes after the hour). | MUST | Given the system running at 08:00 UTC, when the scheduler fires, then the evaluation log records a trigger at 08:02:00 UTC ± 30 seconds. |
| FR-2-83  | The evaluation orchestrator SHALL pull the latest OHLCV data from MT5 for all required timeframes (M15, M30, H1, H4, Daily) as the first step in each cycle. | MUST | Given the orchestrator firing, when the data-pull step completes, then the indicator library is computed from data current to within 2 minutes of the trigger time. |
| FR-2-83b | If the MT5 data pull returns fewer bars than the minimum required for indicator computation (200 H1 bars, 100 H4 bars, 60 Daily bars), the orchestrator SHALL write all 20 strategy results as NO_TRADE with reason "INSUFFICIENT_BARS", log the bar counts received, and exit the cycle without retrying. The system self-corrects at the next H1 close once bars have accumulated. No retry within the same cycle is performed. | MUST | Given MT5 returning only 50 H1 bars on system startup, when the orchestrator checks bar counts, then all 20 results are written as NO_TRADE("INSUFFICIENT_BARS") and the scheduler is not stopped. |
| FR-2-84  | The evaluation orchestrator SHALL compute the shared indicator library exactly once per cycle before invoking any strategy module. | MUST | Given a cycle log, when indicator computation entries are counted, then exactly one computation event exists per indicator, not 20. |
| FR-2-85  | The evaluation orchestrator SHALL evaluate all 20 strategy modules sequentially within each cycle, collecting one `StrategyResult` per strategy. | MUST | Given a completed evaluation cycle, when the results list is inspected, then exactly 20 `StrategyResult` objects are present, one per strategy (IDs 1–20). |
| FR-2-86  | The evaluation orchestrator SHALL batch-write all 20 `StrategyResult` objects to SQLite at the end of the cycle via `signal_store.py`, not mid-cycle. | MUST | Given an evaluation cycle that completes successfully, when the SQLite signals table is queried, then 20 new rows exist with the same `evaluated_at` timestamp batch. |
| FR-2-87  | The evaluation orchestrator SHALL catch and log per-strategy exceptions without halting the remaining strategy evaluations; a strategy failure SHALL produce a NO_TRADE result with an error reason, not a crash. | MUST | Given Strategy 4 raising an exception due to stale FRED data, when the orchestrator handles the exception, then strategies 5–20 still complete and their results are written. |
| FR-2-88  | The evaluation orchestrator SHALL log the total evaluation cycle duration in milliseconds upon completion. | MUST | Given a completed cycle, when the application log is inspected, then a log entry with the cycle duration in milliseconds is present. |

---

### 3.10 REST API Endpoints

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-2-89  | The system SHALL expose `GET /api/strategies` returning the most recent `StrategyResult` for all 20 strategies. | MUST | Given a completed evaluation cycle, when `GET /api/strategies` is called, then the response contains exactly 20 strategy result objects in the `data` field. |
| FR-2-90  | The system SHALL expose `GET /api/strategy/{id}` accepting an integer ID from 1 to 20 and returning the full debate detail for that strategy including `agent_scores`. | MUST | Given `GET /api/strategy/1`, when the response is inspected, then the full StrategyResult including `agent_scores` with all four agent entries is returned. |
| FR-2-91  | The system SHALL return a 404 response with `{"success": false, "error": "Strategy not found"}` when `GET /api/strategy/{id}` is called with an ID outside the range 1–20. | MUST | Given `GET /api/strategy/21`, when the response is inspected, then HTTP status = 404 and the error body matches the specified format. |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-01  | The complete evaluation cycle for all 20 strategies SHALL complete within 30 seconds on the target Windows machine under normal operating conditions. | MUST | Given 20 strategy evaluations triggered sequentially, when the cycle completes, then the logged duration is ≤ 30,000 milliseconds. |
| NFR-2-02  | Each individual strategy evaluation (including 4-agent scoring and debate engine) SHALL complete within 2 seconds. | MUST | Given any single strategy's evaluation, when the per-strategy duration is measured, then it is ≤ 2,000 milliseconds. |
| NFR-2-03  | The shared indicator library computation SHALL complete within 5 seconds for all required timeframes and indicators combined. | MUST | Given OHLCV data for all timeframes, when indicator computation completes, then the computation duration is ≤ 5,000 milliseconds. |
| NFR-2-04  | `GET /api/strategies` SHALL respond within 500 milliseconds when the most recent results are already stored in SQLite. | MUST | Given a completed cycle and a `GET /api/strategies` request, when measured from request to response, then elapsed time is ≤ 500 milliseconds. |
| NFR-2-05  | `GET /api/strategy/{id}` SHALL respond within 200 milliseconds when the strategy result exists in SQLite. | MUST | Given a completed cycle and a `GET /api/strategy/5` request, when measured from request to response, then elapsed time is ≤ 200 milliseconds. |

---

### 4.2 Reliability

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-06  | The evaluation orchestrator SHALL continue operating and trigger subsequent cycles if any single evaluation cycle fails entirely, after logging the failure. | MUST | Given an evaluation cycle that raises an unhandled exception, when the next H1 close fires, then the scheduler triggers a new cycle. |
| NFR-2-07  | A failure in any single strategy module SHALL not prevent the remaining 19 strategies from completing their evaluation in the same cycle. | MUST | Given Strategy 4 failing at evaluation time, when the cycle completes, then results for strategies 1–3 and 5–20 are present in SQLite. |
| NFR-2-08  | The system SHALL gracefully degrade Strategy S4 to NO_TRADE with reason "FRED_DATA_STALE" when FRED data is unavailable or older than 6 hours, without raising an exception. | MUST | Given FRED data unavailable, when S4 is evaluated, then a NO_TRADE result is returned, no exception propagates, and remaining strategies are unaffected. |
| NFR-2-09  | The system SHALL gracefully degrade Strategy S20 to NO_TRADE with reason "CALENDAR_DATA_STALE" when economic calendar data is unavailable or older than 24 hours. | MUST | Given calendar data unavailable, when S20 is evaluated, then a NO_TRADE result is returned, no exception propagates. |
| NFR-2-10  | The system SHALL gracefully degrade all strategies to NO_TRADE with reason "MT5_DISCONNECTED" when MT5 data is unavailable at cycle start, and retry on the next H1 close. | MUST | Given MT5 connection lost, when the evaluation orchestrator fires, then all 20 results are written as NO_TRADE with "MT5_DISCONNECTED" and the scheduler is not stopped. |

---

### 4.3 Data Integrity

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-11  | The `rrr` calculation SHALL be consistent: the value stored in SQLite SHALL equal `(tp1 - entry) / (entry - sl)` for longs and `(entry - tp1) / (sl - entry)` for shorts, to two decimal places. | MUST | Given any stored VALID_TRADE signal, when the stored entry, sl, tp1 and rrr are retrieved, then the rrr value matches the formula applied to entry, sl, tp1. |
| NFR-2-12  | Duplicate strategy results SHALL not be written to SQLite within the same evaluation cycle; each cycle SHALL produce exactly one row per strategy (20 rows per cycle). | MUST | Given a completed cycle, when the signals table is queried for the cycle's `evaluated_at` timestamp, then exactly 20 rows are returned. |
| NFR-2-13  | All price values (entry, sl, tp1, tp2, tp3) stored in SQLite SHALL be rounded to 3 decimal places to match USDJPY pricing precision. | MUST | Given an entry computed as 150.12345, when stored in SQLite and retrieved, then the value is 150.123. |
| NFR-2-14  | The `evaluated_at` timestamp stored in SQLite SHALL be in UTC and formatted as ISO 8601 (e.g., "2026-04-24T09:02:00Z"). | MUST | Given any stored result, when `evaluated_at` is retrieved, then it is parseable as ISO 8601 UTC. |
| NFR-2-15  | The `reasons_for` and `reasons_against` fields SHALL be stored as JSON arrays in SQLite and deserialize without data loss. | MUST | Given a StrategyResult with 3 reasons_for strings, when serialized to SQLite and deserialized, then the 3 original strings are present and unchanged. |

---

### 4.4 Maintainability

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-16  | All configurable thresholds (confidence ≥ 75, probability ≥ 70, RRR ≥ 1.5, spread limit 3 pips, intervention price 155.00) SHALL be defined only in `config.py` and referenced from there throughout the codebase. | MUST | Given a grep for hardcoded value `155.00` in non-config Python files, when the search completes, then no matches are found outside `config.py`. |
| NFR-2-17  | All database read and write operations SHALL be performed exclusively through `db/signal_store.py`; no raw SQL or direct SQLite calls SHALL exist in strategy modules, agent classes, or the debate engine. | MUST | Given a grep for `sqlite3.connect` in files outside `signal_store.py`, when the search completes, then no matches are found. |
| NFR-2-18  | Each strategy module SHALL be independently testable by instantiating it with mock pre-computed indicator data without requiring a live MT5 connection. | MUST | Given mocked indicator data constructed in a test, when any strategy module is instantiated and evaluated with that data, then evaluation completes without requiring MT5. |
| NFR-2-19  | The shared indicator library SHALL expose each indicator as a named, typed attribute so that strategies reference indicators by name rather than by positional index. | SHOULD | Given code that accesses H4 ATR in a strategy, when inspected, then the access reads `indicators.h4_atr14` (or equivalent named attribute), not `indicators[3]`. |

---

### 4.5 Security

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-20  | No API keys, passwords, or credentials SHALL be hardcoded in any strategy module, agent class, debate engine, or evaluation orchestrator. | MUST | Given a grep for patterns matching common credential formats across all Phase 2 Python files, when the search completes, then no hardcoded secrets are found. |
| NFR-2-21  | All external credentials (FRED_API_KEY, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID) SHALL be read exclusively from environment variables via `python-dotenv`. | MUST | Given the application running without a `.env` file present, when strategy evaluation is triggered, then no credential-related operation fails silently — a clear startup error is raised. |

---

### 4.6 Compatibility

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-2-22  | The Phase 2 implementation SHALL run on Windows 11 with Python 3.11 or higher. | MUST | Given a Windows 11 machine with Python 3.11 installed, when `python backend/main.py` is run, then no import errors or OS compatibility errors occur on startup. |
| NFR-2-23  | The Phase 2 implementation SHALL be compatible with the MetaTrader 5 Python package version available in `requirements.txt` from Phase 1. | MUST | Given the requirements.txt from Phase 1, when MT5 data is pulled within the evaluation orchestrator, then no version mismatch errors occur. |
| NFR-2-24  | All Phase 2 Python dependencies SHALL be listed in `requirements.txt` with pinned or minimum version constraints. | MUST | Given `requirements.txt`, when all Phase 2 imports are checked against it, then every imported third-party package is listed. |

---

## 5. Data Specifications

### 5.1 Data Models

#### StrategyResult (Python Dataclass)

| Field               | Type                  | Constraints                                      | Description |
|---------------------|-----------------------|--------------------------------------------------|-------------|
| strategy_id         | int                   | 1–20                                             | Unique strategy identifier |
| strategy_name       | str                   | Non-empty                                        | Human-readable strategy name |
| strategy_type       | str                   | One of: Trend, Breakout, Mean Reversion, Hybrid, Event-Driven | Strategy classification |
| status              | str                   | One of: VALID_TRADE, WAIT_FOR_LEVELS, NO_TRADE   | Evaluation verdict |
| direction           | str or None           | BUY, SELL, or None                               | Trade direction; None for NO_TRADE |
| entry               | float or None         | > 0; must not be None when status = VALID_TRADE  | Entry price |
| sl                  | float or None         | > 0; must not be None when status = VALID_TRADE  | Stop loss price |
| tp1                 | float or None         | > 0; must not be None when status = VALID_TRADE  | Take profit level 1 |
| tp2                 | float or None         | > 0; optional                                    | Take profit level 2 |
| tp3                 | float or None         | > 0; optional                                    | Take profit level 3 |
| rrr                 | float or None         | > 0 when populated                               | Risk-reward ratio to TP1 |
| confidence          | int                   | 0–100                                            | Debate engine confidence score |
| probability         | int                   | 0–100                                            | Debate engine probability score |
| timeframes          | list[str]             | Non-empty                                        | Timeframes used in evaluation |
| wait_zone           | str or None           | Non-null only when status = WAIT_FOR_LEVELS      | Description of the entry zone to wait for |
| conditions_to_meet  | list[str] or None     | Non-null only when status = WAIT_FOR_LEVELS      | Conditions that must resolve before entry |
| reasons_for         | list[str]             | Non-empty when status ≠ NO_TRADE                 | Supporting reasons from opportunity agents |
| reasons_against     | list[str]             | Non-empty when status = NO_TRADE                 | Rejection reasons from risk agents |
| verdict_summary     | str                   | Non-empty                                        | One-sentence human-readable verdict narrative |
| evaluated_at        | datetime              | UTC; set at evaluation completion time            | When this result was produced |
| agent_scores        | dict                  | Keys: opp_agent_1, opp_agent_2, risk_agent_1, risk_agent_2 | Raw per-agent scores for transparency |

#### AgentScore (Nested within agent_scores)

| Field              | Type        | Constraints    | Description |
|--------------------|-------------|----------------|-------------|
| aggregate_score    | float       | 0–10           | Overall agent score |
| dimension_scores   | dict        | Key = dimension name, value = 0–10 | Per-dimension breakdown |
| flags              | list[str]   | Empty for opportunity agents when no issues; populated for risk agents | Named flags raised by this agent |

#### IndicatorCache (Internal Computation Object)

| Field               | Type       | Description |
|---------------------|------------|-------------|
| h1_ema20            | float      | EMA(20) on H1 current bar |
| h1_ema50            | float      | EMA(50) on H1 current bar |
| h1_ema200           | float      | EMA(200) on H1 current bar |
| h4_ema20            | float      | EMA(20) on H4 current bar |
| h4_ema50            | float      | EMA(50) on H4 current bar |
| h4_ema200           | float      | EMA(200) on H4 current bar |
| d_ema20             | float      | EMA(20) on Daily current bar |
| d_ema50             | float      | EMA(50) on Daily current bar |
| d_ema200            | float      | EMA(200) on Daily current bar |
| h1_macd_line        | float      | MACD line on H1 current bar |
| h1_macd_signal      | float      | MACD signal on H1 current bar |
| h1_macd_histogram   | float      | MACD histogram on H1 current bar |
| h4_macd_line        | float      | MACD line on H4 current bar |
| h4_macd_signal      | float      | MACD signal on H4 current bar |
| h1_atr14            | float      | ATR(14) on H1, price units |
| h4_atr14            | float      | ATR(14) on H4, price units |
| h1_rsi14            | float      | RSI(14) on H1, range 0–100 |
| h4_rsi14            | float      | RSI(14) on H4, range 0–100 |
| h1_bb_upper         | float      | Bollinger upper band on H1 |
| h1_bb_mid           | float      | Bollinger middle band on H1 |
| h1_bb_lower         | float      | Bollinger lower band on H1 |
| h4_bb_upper         | float      | Bollinger upper band on H4 |
| h4_bb_mid           | float      | Bollinger middle band on H4 |
| h4_bb_lower         | float      | Bollinger lower band on H4 |
| h4_ichimoku         | dict       | All 5 Ichimoku lines on H4 (tenkan, kijun, senkou_a, senkou_b, chikou) |
| d_ichimoku          | dict       | All 5 Ichimoku lines on Daily |
| h4_adx14            | float      | ADX(14) on H4 |
| h4_plus_di14        | float      | +DI(14) on H4 |
| h4_minus_di14       | float      | -DI(14) on H4 |
| h4_donchian_upper   | float      | 20-period Donchian upper on H4 |
| h4_donchian_lower   | float      | 20-period Donchian lower on H4 |
| d_donchian_upper    | float      | 20-period Donchian upper on Daily |
| d_donchian_lower    | float      | 20-period Donchian lower on Daily |
| h1_keltner_upper    | float      | Keltner upper band on H1 |
| h1_keltner_mid      | float      | Keltner middle (EMA20) on H1 |
| h1_keltner_lower    | float      | Keltner lower band on H1 |
| d_pivot_pp          | float      | Classic Daily Pivot Point |
| d_pivot_r1          | float      | Resistance 1 |
| d_pivot_r2          | float      | Resistance 2 |
| d_pivot_r3          | float      | Resistance 3 |
| d_pivot_s1          | float      | Support 1 |
| d_pivot_s2          | float      | Support 2 |
| d_pivot_s3          | float      | Support 3 |
| swing_high_h4       | float      | Most recent confirmed swing high on H4 |
| swing_low_h4        | float      | Most recent confirmed swing low on H4 |
| swing_high_d        | float      | Most recent confirmed swing high on Daily |
| swing_low_d         | float      | Most recent confirmed swing low on Daily |
| latest_engulf_bull_h4  | int or None | Bar index of most recent bullish engulfing on H4 |
| latest_engulf_bear_h4  | int or None | Bar index of most recent bearish engulfing on H4 |
| latest_engulf_bull_d   | int or None | Bar index of most recent bullish engulfing on Daily |
| inside_bar_d        | bool       | True if the most recent Daily bar is an inside bar |
| inside_bar_h4       | bool       | True if the most recent H4 bar is an inside bar |
| current_session     | str        | TOKYO / LONDON / NEW_YORK / OFF |
| news_imminent       | bool       | True if high-impact event within 30 minutes |
| current_spread_pips | float      | MT5-reported current spread in pips |
| usdjpy_price        | float      | Current USDJPY ask price |
| us10y_yield         | float      | Latest US 10Y yield from FRED |
| us10y_timestamp     | datetime   | UTC timestamp of last FRED fetch |
| fed_rate            | float      | Current Fed Funds Rate from FRED |
| boj_rate            | float      | Current BoJ Policy Rate (from config or FRED) |
| calendar_timestamp  | datetime   | UTC timestamp of last calendar data fetch |

### 5.2 Data Flows

#### H1-Close Evaluation Flow

```
APScheduler H1 trigger (HH:02:00 UTC)
  → Pull MT5 OHLCV (M15, M30, H1, H4, D)
  → Compute IndicatorCache (once)
  → Fetch market context (US10Y, DXY, VIX, news flag) from Phase 1 cache
  → For each strategy S1–S20:
      → Instantiate strategy with IndicatorCache
      → Create OppAgent1, OppAgent2, RiskAgent1, RiskAgent2
      → Run OppAgent1.score() → opp1_result
      → Run OppAgent2.score() → opp2_result
      → Run RiskAgent1.score() → risk1_result
      → Run RiskAgent2.score() → risk2_result
      → Run DebateEngine.evaluate(opp1, opp2, risk1, risk2) → StrategyResult
  → Batch write 20 StrategyResults to SQLite via signal_store.py
  → Log cycle duration
```

If MT5 data pull fails: all 20 results written as NO_TRADE("MT5_DISCONNECTED"), cycle ends.
If individual strategy raises exception: that strategy written as NO_TRADE("EVALUATION_ERROR"), remaining strategies proceed.
If SQLite write fails: error is logged; the next cycle will overwrite pending results on next trigger.

#### API Read Flow

```
Client calls GET /api/strategies
  → FastAPI handler queries signal_store.py for latest result per strategy_id
  → Returns JSON with 20 StrategyResult objects
```

### 5.3 Interface Contracts

#### MT5 OHLCV Interface

| Attribute | Value |
|-----------|-------|
| Interface name | MT5 Python API — `copy_rates_from_pos` |
| Direction | Inbound |
| Data format | Pandas DataFrame with columns: time (UTC), open, high, low, close, tick_volume |
| Timeframes consumed | M15, M30, H1, H4, D |
| Bars requested | 500 bars per timeframe per call |
| Expected frequency | Once per H1 evaluation cycle |
| Error condition | If MT5 returns None or raises exception, all strategies return NO_TRADE("MT5_DISCONNECTED") |

#### FRED Data Interface

| Attribute | Value |
|-----------|-------|
| Interface name | Phase 1 FRED cache (fred_feed.py) |
| Direction | Inbound |
| Data | us10y_yield (float), fed_rate (float), last_fetched (datetime UTC) |
| Expected frequency | Read from Phase 1 cache (refreshed daily) |
| Error condition | If data absent or age > 6 hours, S4 returns NO_TRADE("FRED_DATA_STALE"); other strategies unaffected |

#### Economic Calendar Interface

| Attribute | Value |
|-----------|-------|
| Interface name | Phase 1 calendar cache (calendar_feed.py) |
| Direction | Inbound |
| Data | List of events: {name, impact (HIGH/MEDIUM/LOW), scheduled_utc (datetime)} |
| Expected frequency | Read from Phase 1 cache (refreshed daily) |
| Error condition | If data absent or age > 24 hours, news_imminent flag = False; S20 returns NO_TRADE("CALENDAR_DATA_STALE") |

---

## 6. Interface Specifications

### 6.1 Internal API Contracts

#### GET /api/strategies

| Attribute | Value |
|-----------|-------|
| Method | GET |
| Path | `/api/strategies` |
| Request parameters | None |
| Response schema | `{"success": true, "data": [StrategyResult × 20], "error": null}` |
| Response data fields (per item) | strategy_id (int), strategy_name (str), strategy_type (str), status (str), direction (str\|null), entry (float\|null), sl (float\|null), tp1 (float\|null), tp2 (float\|null), tp3 (float\|null), rrr (float\|null), confidence (int), probability (int), timeframes (list[str]), wait_zone (str\|null), conditions_to_meet (list[str]\|null), reasons_for (list[str]), reasons_against (list[str]), verdict_summary (str), evaluated_at (str, ISO 8601 UTC) |
| Error response | `{"success": false, "data": null, "error": "No strategy results available"}` with HTTP 503 when no results have been stored yet |

Example response (abbreviated):
```json
{
  "success": true,
  "data": [
    {
      "strategy_id": 1,
      "strategy_name": "Multi-Timeframe Trend Alignment",
      "strategy_type": "Trend",
      "status": "VALID_TRADE",
      "direction": "BUY",
      "entry": 150.250,
      "sl": 149.750,
      "tp1": 151.250,
      "tp2": 152.250,
      "tp3": null,
      "rrr": 2.00,
      "confidence": 81,
      "probability": 74,
      "timeframes": ["D", "H4", "H1"],
      "wait_zone": null,
      "conditions_to_meet": null,
      "reasons_for": ["Daily EMA50/200 bullish alignment confirmed", "H4 higher-low printed at EMA20", "H1 MACD bullish cross above signal"],
      "reasons_against": ["DXY showing minor resistance"],
      "verdict_summary": "All three timeframes aligned bullish with clean H1 MACD entry trigger.",
      "evaluated_at": "2026-04-24T09:02:11Z"
    }
  ],
  "error": null
}
```

#### GET /api/strategy/{id}

| Attribute | Value |
|-----------|-------|
| Method | GET |
| Path | `/api/strategy/{id}` |
| Path parameter | id (int, 1–20) |
| Request parameters | None additional |
| Response schema | `{"success": true, "data": StrategyResult (full, including agent_scores), "error": null}` |
| agent_scores structure | `{"opp_agent_1": {"aggregate_score": float, "dimension_scores": {...}, "flags": []}, "opp_agent_2": {...}, "risk_agent_1": {...}, "risk_agent_2": {...}}` |
| Error — not found | HTTP 404, `{"success": false, "data": null, "error": "Strategy not found"}` |
| Error — no results yet | HTTP 503, `{"success": false, "data": null, "error": "No results available for strategy {id}"}` |

### 6.2 External System Interfaces

Phase 2 does not introduce new external system integrations. All external data (MT5, FRED, yfinance, calendar) is consumed via Phase 1 cache modules. See Section 5.3 for interface contracts with those modules.

### 6.3 User Interface Specifications

Phase 2 does not introduce any user interface. Frontend display is specified in Phase 3.

---

## 7. Constraints

- **Platform**: Windows 11 only. The MetaTrader 5 Python package is Windows-exclusive.
- **Python version**: 3.11 or higher. Type hints and dataclass features rely on modern Python.
- **MT5 terminal**: Must be running and authenticated on the same machine before the backend starts. Phase 2 does not manage the MT5 session.
- **Single user**: No authentication layer, no multi-user concurrency. All operations assume one local user.
- **SQLite single writer**: Phase 2 writes results via a single scheduled job. No concurrency design is needed or permitted in this phase.
- **No external AI calls**: All agent scoring is algorithmic and rule-based. No LLM calls, no external AI API requests.
- **No hardcoded values**: Every numerical threshold must be defined in `config.py`. Strategy parameters must be defined in `StrategyConfig` per module, not scattered inline.
- **No raw SQL outside signal_store.py**: All database interaction goes through the Phase 1 module boundary.
- **Indicators computed once per cycle**: The shared indicator library is computed before strategies run, not inside individual strategy modules.
- **No COT data integration**: Commitment of Traders data is noted in the strategy reference as useful context but is not integrated in this phase due to the weekly cadence and the lack of a reliable automated feed already in Phase 1.

---

## 8. Assumptions

1. It is assumed that Phase 1 delivers a working MT5 data feed returning correctly structured OHLCV DataFrames for all five required timeframes. If this is incorrect, indicator computation will fail at the first evaluation cycle, and Phase 2 cannot complete validation.

2. It is assumed that Phase 1 delivers a working `signal_store.py` with a `write_strategy_result(result: StrategyResult)` function that accepts the Phase 2 dataclass. If the interface changes, Phase 2 write calls must be updated accordingly.

3. It is assumed that the APScheduler H1 job created in Phase 1 is hookable — i.e., Phase 2 can register a callable to be executed by the existing scheduler. If the scheduler architecture requires a different registration pattern, the orchestrator design will need adjustment.

4. It is assumed that FRED data is refreshed at least once every 6 hours by Phase 1 infrastructure. If FRED data refresh is less frequent, S4 will return NO_TRADE in most evaluation cycles.

5. It is assumed that the economic calendar is refreshed at least once every 24 hours by Phase 1 infrastructure. If refresh is less frequent, S20 will return NO_TRADE in all cycles after the first 24 hours.

6. It is assumed that the BoJ Policy Rate is not auto-fetched from a live feed in this phase; the current rate (0.75% as of April 2026) is stored in `config.py` and updated manually when the BoJ announces a policy change. If this is incorrect, the rate differential calculation for S3 may use a stale rate.

7. It is assumed that sufficient historical bar data (at least 200 H1 bars, 100 H4 bars, and 60 Daily bars) is available from MT5 for all indicator computations to be initialized. If less data is available (e.g., immediately after a fresh MT5 installation), indicator calculations may return NaN for some values and affected strategies must handle NaN gracefully.

8. It is assumed that the USDJPY_Algo_Strategy_Reference.md is the authoritative source for all strategy parameters. Any conflict between that document and the Phase 2 build guide shall be resolved in favor of the strategy reference.

---

## 9. Risks and Mitigations

| ID         | Risk | Likelihood | Impact | Mitigation |
|------------|------|------------|--------|------------|
| RISK-2-01  | MT5 connection drops during an evaluation cycle, causing data pull to fail for all strategies. | Medium | High | Orchestrator wraps MT5 call in try/except; all 20 strategies written as NO_TRADE; cycle is logged; scheduler continues. |
| RISK-2-02  | FRED API rate limit or network failure causes S4 to receive stale data persistently. | Low | Low | S4 checks data age before evaluating; returns NO_TRADE("FRED_DATA_STALE") gracefully. Other strategies are unaffected. |
| RISK-2-03  | Swing detection returns incorrect or unstable swing high/low values due to insufficient lookback bars, causing S17 Fibonacci levels to be miscalculated. | Medium | Medium | S17 requires a minimum lookback window; if bars are insufficient, returns NO_TRADE("NO_CLEAN_IMPULSE_DETECTED"). Minimum bar count validated at startup. |
| RISK-2-04  | Evaluation cycle exceeds 30-second target due to slow indicator computation on first run or when cold-starting. | Low | Low | First-run warm-up is expected; NFR-2-01 applies under steady-state conditions. Cycle duration is logged; if consistently exceeded, indicator computation can be profiled. |
| RISK-2-05  | Two or more strategies return VALID_TRADE in the same direction, creating the appearance of high-conviction but actually reflecting correlated strategies sharing inputs. | High | Medium | This is by design — the system surfaces all signals independently. The frontend (Phase 3) and user judgment manage portfolio concentration. A warning is added to the verdict_summary when >3 strategies agree on the same direction. |
| RISK-2-06  | Session detection is incorrect around daylight saving time transitions, causing S8 and S13 to evaluate outside their intended windows. | Low | Medium | Session detection uses UTC boundaries that are fixed (Tokyo 00:00–09:00 UTC, London 07:00–16:00 UTC) and therefore unaffected by DST. |
| RISK-2-07  | The debate engine confidence normalization formula produces scores that are systematically too high or too low for certain strategy types, biasing VALID_TRADE frequency. | Medium | High | Confidence thresholds in config.py allow adjustment without code changes. Initial calibration is expected to require one round of review after the first 48 hours of live data. |
| RISK-2-08  | Strategy S3's macro gate using BoJ rate from config.py becomes stale after a surprise BoJ rate decision, causing incorrect carry spread calculations. | Low | High | `config.py` includes a `BOJ_RATE_LAST_UPDATED` field; if the date is >90 days old, S3 logs a warning. The rate must be updated manually after any BoJ announcement. |
| RISK-2-09  | Inside bar detection for S18 is ambiguous when the current bar has not yet closed, causing premature signals on partial H4 or Daily bars. | Medium | Medium | All evaluations are triggered at candle close (HH:02:00 UTC), 2 minutes after the hour, ensuring the completed bar is available before evaluation. |
| RISK-2-10  | An exception raised inside the DebateEngine propagates and prevents all 20 results from being written. | Low | High | DebateEngine is wrapped in a per-strategy try/except block inside the orchestrator; a debate engine failure returns NO_TRADE("DEBATE_ENGINE_ERROR") for the affected strategy only. |

---

## 10. Acceptance Criteria

All of the following must be true for Phase 2 to be considered complete. Each criterion is binary (pass/fail) and independently verifiable.

| ID      | Acceptance Criterion |
|---------|----------------------|
| AC-2-01 | `GET /api/strategies` returns exactly 20 strategy result objects, one per strategy (IDs 1–20), with no missing IDs. |
| AC-2-02 | Every strategy result in the API response contains a non-null `status` value that is one of VALID_TRADE, WAIT_FOR_LEVELS, or NO_TRADE. |
| AC-2-03 | Every result with `status = VALID_TRADE` has non-null `entry`, `sl`, and `tp1` fields with valid numeric values, and a calculated `rrr ≥ 1.5`. |
| AC-2-04 | Every result with `status = NO_TRADE` has at least one string in the `reasons_against` list. |
| AC-2-05 | The H1 scheduler job fires, completes without raising an unhandled exception, and its completion is visible in the application log with a cycle duration entry. |
| AC-2-06 | After one complete evaluation cycle, exactly 20 rows exist in the SQLite `signals` table for that cycle's `evaluated_at` timestamp. |
| AC-2-07 | `GET /api/strategy/1` returns the full debate output for Strategy 1 including the `agent_scores` field with entries for all four agents. |
| AC-2-08 | Strategy S3 (Carry-Trade Pullback) returns `status = NO_TRADE` with a reason referencing the macro gate when the configured Fed-BoJ spread is set to 1.0% in a test run. |
| AC-2-09 | Strategy S8 (Tokyo Range Breakout) returns `status = NO_TRADE` with `"OUTSIDE_SESSION_WINDOW"` when evaluated at a time outside the Tokyo session window (e.g., 12:00 UTC). |
| AC-2-10 | Strategy S13 (London Open Breakout) returns `status = NO_TRADE` with `"OUTSIDE_SESSION_WINDOW"` when evaluated at a time outside the London open window (e.g., 20:00 UTC). |
| AC-2-11 | Strategy S4 (US10Y Yield Correlation) returns `status = NO_TRADE` with `"FRED_DATA_STALE"` when the FRED data timestamp is manually set to 7 hours in the past in a test run. |
| AC-2-12 | Strategy S20 (Post-News Breakout) returns `status = NO_TRADE` when the last confirmed high-impact event timestamp is set to 100 minutes in the past in a test run. |
| AC-2-13 | The debate engine correctly applies a VALID_TRADE verdict when confidence ≥ 75, probability ≥ 70, RRR ≥ 1.5, and no critical risk flags are present (verified via unit test with constructed agent outputs). |
| AC-2-14 | The debate engine correctly overrides to NO_TRADE when `news_imminent = True`, regardless of confidence and probability scores (verified via unit test). |
| AC-2-15 | The debate engine correctly overrides to NO_TRADE when USDJPY price > 155.00 and direction = BUY (verified via unit test). |
| AC-2-16 | The debate engine correctly overrides to NO_TRADE when spread > 3 pips (verified via unit test). |
| AC-2-17 | A simulated failure of Strategy 4's evaluation (exception raised) does not prevent strategies 1–3 and 5–20 from completing and their results being written to SQLite. |
| AC-2-18 | All 20 strategy modules can be instantiated and evaluated with mocked indicator data without requiring a live MT5 connection (unit test coverage). |
| AC-2-19 | `GET /api/strategy/25` returns HTTP 404 with `{"success": false, "error": "Strategy not found"}`. |
| AC-2-20 | A grep of all Phase 2 Python files for the hardcoded value `155.00` returns no matches outside `config.py`. |

---

## 11. Traceability Matrix

| Acceptance Criterion | Functional Requirement(s) |
|----------------------|---------------------------|
| AC-2-01              | FR-2-85, FR-2-89 |
| AC-2-02              | FR-2-23, FR-2-41 |
| AC-2-03              | FR-2-04, FR-2-26, FR-2-50 |
| AC-2-04              | FR-2-24, FR-2-55 (implied NO_TRADE path) |
| AC-2-05              | FR-2-82, FR-2-88 |
| AC-2-06              | FR-2-86, NFR-2-12 |
| AC-2-07              | FR-2-29, FR-2-90 |
| AC-2-08              | FR-2-63 |
| AC-2-09              | FR-2-68 |
| AC-2-10              | FR-2-73 |
| AC-2-11              | FR-2-64 |
| AC-2-12              | FR-2-80 |
| AC-2-13              | FR-2-50 |
| AC-2-14              | FR-2-52 |
| AC-2-15              | FR-2-53 |
| AC-2-16              | FR-2-54 |
| AC-2-17              | FR-2-87 |
| AC-2-18              | NFR-2-18, FR-2-03 |
| AC-2-19              | FR-2-91 |
| AC-2-20              | NFR-2-16 |

---

## 12. Open Questions

All open questions have been resolved. The table below records each question, its resolution, and the requirement updated.

| ID      | Question | Resolution | Requirement Updated |
|---------|----------|------------|---------------------|
| OQ-2-01 | Exact normalization formula for `net_score` → `confidence`. | Linear normalization over fixed bounds [−20, +15]: `confidence = clamp(round(((net_score + 20) / 35) × 100), 0, 100)`. Bounds derived from the theoretical min/max of the debate formula with averaged dimension scores. | FR-2-48 |
| OQ-2-02 | Weighting for `probability` sub-scores. | Equal thirds (33.3% each): rule compliance, structure quality, trend alignment. Avoids systematic bias against mean-reversion and event-driven strategies. | FR-2-49 |
| OQ-2-03 | Asian session range window for S11. | 00:00–06:00 UTC. Captures core Tokyo session and BoJ fix flows; excludes London pre-market activity which distorts the range. | FR-2-71b (new) |
| OQ-2-04 | Minimum impulse leg size for S17 Fibonacci. | Must satisfy both: ≥ 2.0× H4 ATR(14) AND ≥ 60 pips absolute. ATR multiple adapts to volatility regime; pip floor prevents trivially small setups. | FR-2-77 |
| OQ-2-05 | Orchestrator behaviour when MT5 returns insufficient bars. | Degrade gracefully: write all 20 as NO_TRADE("INSUFFICIENT_BARS"), log bar counts, exit cycle. No retry. Self-corrects at next H1 close. | FR-2-83b (new) |

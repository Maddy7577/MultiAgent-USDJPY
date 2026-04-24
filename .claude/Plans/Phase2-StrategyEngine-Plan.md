# Phase 2 — StrategyEngine Implementation Plan

## Context

Phase 2 builds the computational core of the USDJPY Smart Agent: 20 strategy modules evaluated through a 4-agent debate framework on every H1 candle close, producing VALID TRADE / WAIT FOR LEVELS / NO TRADE verdicts stored in SQLite and served via REST API.

**No code exists yet.** Phase 1 infrastructure (data feeds, scheduler, DB, FastAPI) must be implemented first. Phase 2 assumes Phase 1 is complete and passing its 15 acceptance criteria before any Phase 2 work begins.

Source of truth: `.claude/Specs/Phase2-StrategyEngine-Spec.md` (93 FRs, 24 NFRs, 20 ACs, all open questions resolved).

---

## Pre-Phase-2 Schema Extension

Phase 1's `signals` table (from the Phase 1 plan) is missing four fields required by Phase 2's `StrategyResult`. Before any Phase 2 code is written, add these columns to `backend/db/schema.sql`:

```sql
-- Additions to the signals table (add after 'verdict_summary TEXT'):
strategy_type   TEXT,
wait_zone       TEXT,
conditions_to_meet TEXT,  -- JSON array
agent_scores    TEXT      -- JSON object
```

Also add these constants to `backend/config.py`:

```python
# Phase 2 thresholds
CONFIDENCE_THRESHOLD    = 75
PROBABILITY_THRESHOLD   = 70
MIN_RRR                 = 1.5
MAX_SPREAD_PIPS         = 3.0
INTERVENTION_PRICE      = 155.00
BOJ_RATE                = 0.75        # Update manually after BoJ decisions
BOJ_RATE_LAST_UPDATED   = "2025-12-20"
CARRY_SPREAD_THRESHOLD  = 2.5
FRED_STALENESS_HOURS    = 6
CALENDAR_STALENESS_HOURS = 24
POST_NEWS_WINDOW_MINUTES = 90
MIN_H1_BARS             = 200
MIN_H4_BARS             = 100
MIN_DAILY_BARS          = 60
S11_RANGE_START_UTC     = 0    # 00:00 UTC — start of Asian range-building window
S11_RANGE_END_UTC       = 6    # 06:00 UTC — end of Asian range-building window
S17_MIN_IMPULSE_ATR_MULT = 2.0
S17_MIN_IMPULSE_PIPS    = 60
S17_FIBONACCI_LOOKBACK  = 30   # H4 bars to look back for impulse leg
```

---

## New Dependency

Add to `requirements.txt`:
```
pandas-ta==0.3.14b0
```
`pandas-ta` provides all indicator computations (EMA, MACD, ATR, RSI, Bollinger, Ichimoku, ADX/DMI, Donchian, Keltner, Pivots) as pure Python on top of pandas — no C compilation required, which matters for Windows. Do NOT use `ta-lib` (requires Visual C++ build tools and complex Windows installation).

---

## Build Sequence (Dependency Order)

```
Step 1:  config.py update          → Phase 2 constants
Step 2:  db/schema.sql update      → 4 additional columns
Step 3:  db/signal_store.py update → write_strategy_result(), get_latest_strategy_results(), get_latest_strategy_result()
Step 4:  strategies/base_strategy.py → IndicatorCache dataclass, StrategyResult dataclass, compute_indicators(), BaseStrategy abstract class, all shared utilities
Step 5:  agents/opportunity_agent.py → OpportunityAgent class
Step 6:  agents/risk_agent.py       → RiskAgent class
Step 7:  agents/debate_engine.py    → DebateEngine, all scoring formulas, verdict logic
Step 8:  strategies/s01, s06, s07   → Pure trend (framework validation)
Step 9:  strategies/s02, s03, s04, s05, s10, s12 → Remaining trend
Step 10: strategies/s08, s11, s13, s19 → Session-based
Step 11: strategies/s15, s17, s18   → Price action
Step 12: strategies/s14, s16, s09   → Mean reversion + Keltner breakout
Step 13: strategies/s20             → Event-driven (most complex)
Step 14: scheduler.py update        → Replace H1 stub with full orchestrator
Step 15: api/strategies.py update   → Return real results from SQLite
```

---

## File-by-File Specification

---

### Step 3 — `backend/db/signal_store.py` (additions)

New functions to add alongside the Phase 1 functions:

```python
def write_strategy_result(result: StrategyResult) -> int:
    """Serialize StrategyResult → dict → signals row. Returns new row ID."""
    # Serialize list/dict fields to JSON strings
    # Set outcome = "PENDING"
    # Round all price fields to 3 decimal places
    # Set timestamp = result.evaluated_at.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Call write_signal(signal_dict)

def get_latest_strategy_results() -> list[dict]:
    """One most-recent result per strategy_id, ordered by strategy_id."""
    # SQL: SELECT * FROM signals s1 WHERE id IN (
    #          SELECT MAX(id) FROM signals GROUP BY strategy_id
    #      ) ORDER BY strategy_id
    # Deserialize JSON fields (reasons_for, reasons_against, timeframes,
    #   conditions_to_meet, agent_scores) on the way out

def get_latest_strategy_result(strategy_id: int) -> dict | None:
    # SQL: SELECT * FROM signals WHERE strategy_id = ?
    #      ORDER BY timestamp DESC LIMIT 1
    # Deserialize JSON fields
```

---

### Step 4 — `backend/strategies/base_strategy.py`

This is the most important file in Phase 2. Everything else depends on it.

#### `StrategyResult` dataclass

```python
@dataclass
class StrategyResult:
    strategy_id: int
    strategy_name: str
    strategy_type: str                    # "Trend" | "Breakout" | "Mean Reversion" | "Hybrid" | "Event-Driven"
    status: str                           # "VALID_TRADE" | "WAIT_FOR_LEVELS" | "NO_TRADE"
    direction: str | None                 # "BUY" | "SELL" | None
    entry: float | None
    sl: float | None
    tp1: float | None
    tp2: float | None
    tp3: float | None
    rrr: float | None
    confidence: int                       # 0–100
    probability: int                      # 0–100
    timeframes: list[str]
    wait_zone: str | None                 # populated only when WAIT_FOR_LEVELS
    conditions_to_meet: list[str] | None  # populated only when WAIT_FOR_LEVELS
    reasons_for: list[str]
    reasons_against: list[str]
    verdict_summary: str
    evaluated_at: datetime                # UTC
    agent_scores: dict                    # keys: opp_agent_1, opp_agent_2, risk_agent_1, risk_agent_2
```

#### `IndicatorCache` dataclass

Named fields only — no positional access. All 55+ fields as shown in Spec Section 5.1. Must include:
- `h1/h4/d_ema20/50/200` (9 fields)
- `h1/h4_macd_line/signal/histogram` (partially: h4 has no histogram per spec)
- `h1/h4_atr14` (2 fields)
- `h1/h4_rsi14` (2 fields)
- `h1/h4_bb_upper/mid/lower` (6 fields)
- `h4/d_ichimoku` (2 dict fields with keys: tenkan, kijun, senkou_a, senkou_b, chikou)
- `h4_adx14`, `h4_plus_di14`, `h4_minus_di14` (3 fields)
- `h4/d_donchian_upper/lower` (4 fields)
- `h1_keltner_upper/mid/lower` (3 fields)
- `d_pivot_pp/r1/r2/r3/s1/s2/s3` (7 fields)
- `swing_high/low_h4/d` (4 fields)
- `latest_engulf_bull/bear_h4/d` (3 fields, engulf_bear_d not in spec — omit)
- `inside_bar_d`, `inside_bar_h4` (2 booleans)
- `current_session` (str)
- `news_imminent` (bool)
- `current_spread_pips` (float)
- `usdjpy_price` (float)
- `us10y_yield` (float)
- `us10y_timestamp` (datetime)
- `fed_rate` (float)
- `boj_rate` (float)
- `calendar_timestamp` (datetime)

#### `compute_indicators()` function

```python
def compute_indicators(
    bars: dict[str, pd.DataFrame],    # keys: "M15", "M30", "H1", "H4", "D"
    us10y: float | None,
    us10y_timestamp: datetime | None,
    fed_rate: float | None,
    boj_rate: float,
    calendar_timestamp: datetime | None,
    news_imminent: bool,
    current_price: float,
    current_spread_pips: float
) -> IndicatorCache:
```

Implementation notes:
- Use `pandas_ta` for all indicators: `df.ta.ema()`, `df.ta.macd()`, `df.ta.atr()`, `df.ta.rsi()`, `df.ta.bbands()`, `df.ta.adx()`, `df.ta.donchian()`, `df.ta.kc()`
- Ichimoku: `pandas_ta` has `df.ta.ichimoku()` but the returned column names can vary. Compute manually to be safe:
  ```python
  tenkan = (high.rolling(9).max() + low.rolling(9).min()) / 2
  kijun  = (high.rolling(26).max() + low.rolling(26).min()) / 2
  senkou_a = ((tenkan + kijun) / 2).shift(26)
  senkou_b = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
  chikou = close.shift(-26)  # plotted 26 bars back
  ```
- Pivot Points: Classic formula using prior Daily bar: `PP=(H+L+C)/3`, `R1=2*PP-L`, `R2=PP+(H-L)`, `R3=H+2*(PP-L)`, `S1=2*PP-H`, `S2=PP-(H-L)`, `S3=L-2*(H-PP)`
- Swing detection: 5-bar fractal — a swing high is a bar where `high[i] > max(high[i-1:i+2].drop(i))`, confirmed when 2 bars after the peak have closed (i.e., use `high[-3]` as the candidate)
- Engulfing detection: `body_now = abs(close[-1] - open[-1])`, `body_prev = abs(close[-2] - open[-2])`, bullish engulfing = `close[-1] > open[-1] AND close[-1] > open[-2] AND open[-1] < close[-2] AND body_now > body_prev`
- Inside bar: `high[-1] < high[-2] AND low[-1] > low[-2]`
- Session: based on `datetime.now(timezone.utc).hour`; TOKYO = 0–8 UTC, LONDON = 7–15 UTC (overlap = LONDON), NEW_YORK = 12–20 UTC, OFF = 20–23 UTC
- All values are `.iloc[-1]` of the computed series (current bar)
- NaN safety: if any indicator returns NaN, set it to 0.0 or False as appropriate; log a WARNING

#### `BaseStrategy` abstract class

```python
class BaseStrategy(ABC):
    def __init__(self, indicators: IndicatorCache):
        self.ind = indicators

    @abstractmethod
    def evaluate(self) -> StrategyResult: ...

    @abstractmethod
    def check_long_conditions(self) -> dict: ...

    @abstractmethod
    def check_short_conditions(self) -> dict: ...

    def _validate_result(self, result: StrategyResult) -> None:
        """Raise ValueError if VALID_TRADE without entry/sl/tp1."""

    @staticmethod
    def _compute_rrr(entry: float, sl: float, tp1: float, direction: str) -> float:
        """(tp1-entry)/(entry-sl) for BUY, flipped for SELL. Round 2dp."""

    @staticmethod
    def _no_trade(sid, name, stype, reason: str, timeframes: list[str]) -> StrategyResult:
        """Build a NO_TRADE result with one reason_against entry."""

    @staticmethod
    def _wait_for_levels(sid, name, stype, direction, wait_zone, conditions,
                         timeframes, reasons_for, confidence, probability) -> StrategyResult:
        """Build a WAIT_FOR_LEVELS result."""
```

---

### Step 5 — `backend/agents/opportunity_agent.py`

```python
@dataclass
class OpportunityResult:
    aggregate_score: float           # 0–10 (average of active dimension scores)
    dimension_scores: dict[str, float]
    reasons_for: list[str]
    flags: list[str]                 # empty for opportunity agents

class OpportunityAgent:
    ALL_DIMENSIONS = [
        "rule_compliance", "structure_quality", "trend_alignment",
        "confluence", "volatility_conditions", "entry_precision",
        "sl_logic", "tp_realism", "rrr_quality",
        "invalidation_strength", "macro_sensitivity"
    ]

    def __init__(self, instance_id: int):
        self.instance_id = instance_id   # 1 or 2

    def score(
        self,
        indicators: IndicatorCache,
        active_dimensions: list[str],
        strategy_context: dict          # entry-specific data from the strategy
    ) -> OpportunityResult:
        # Score each active dimension 0–10
        # average = sum(scores) / len(active_dimensions)
        # Build reasons_for list from high-scoring dimensions
        # Return OpportunityResult
```

Dimension scoring logic (applied uniformly across all strategies):
- `rule_compliance` — 0 if no rule met, 10 if all rules met, proportional otherwise. The strategy passes its conditions_met count and total_conditions in strategy_context.
- `structure_quality` — based on swing pattern quality: clean higher-lows/lower-highs = 8–10; choppy = 3–5
- `trend_alignment` — EMAs stacked bullishly on HTF = 9–10; mixed = 4–6; counter-trend = 0–2
- `confluence` — number of confluence factors met: 0=0, 1=3, 2=6, 3=8, 4=10
- `volatility_conditions` — ATR in healthy range (40–120 pips on H4) = 8–10; too low or too high = 2–4
- `entry_precision` — price within 0.2×ATR of ideal entry zone = 9–10; within 0.5×ATR = 6; beyond = 3
- `sl_logic` — SL beyond a structural level (swing) = 9–10; mid-range SL = 5
- `tp_realism` — TP1 at prior structure = 8–10; TP at arbitrary 1R = 6
- `rrr_quality` — RRR ≥ 2.5 = 10; 2.0–2.5 = 8; 1.5–2.0 = 6; < 1.5 = 0
- `invalidation_strength` — clear invalidation level identified = 8–10
- `macro_sensitivity` — macro aligned (DXY, US10Y) = 8–10; neutral = 5; opposed = 1

---

### Step 6 — `backend/agents/risk_agent.py`

```python
@dataclass
class RiskResult:
    risk_score: float        # 0–10 (10 = maximum risk)
    dimension_scores: dict[str, float]
    risk_flags: list[str]    # human-readable named flags
    flags: list[str]         # same as risk_flags (for agent_scores compatibility)

class RiskAgent:
    CRITICAL_FLAGS = {
        "NEWS_IMMINENT", "INTERVENTION_ZONE",
        "SPREAD_TOO_WIDE", "HTF_STRUCTURAL_CONFLICT"
    }

    def __init__(self, instance_id: int):
        self.instance_id = instance_id   # 1 or 2

    def score(
        self,
        indicators: IndicatorCache,
        direction: str | None,
        strategy_context: dict
    ) -> RiskResult:
        # Evaluate 6 risk dimensions
        # Append named flag strings for each triggered critical risk
        # risk_score = average of 6 dimension scores
```

Risk dimension scoring:
- `htf_conflict` — HTF EMA stack opposes direction → 0–10. Counter-trend H4/D = 8–10; neutral = 4; aligned = 0
- `news_risk` — event within 30 min = 10 and flag "NEWS_IMMINENT"; 30–60 min = 5; beyond = 0
- `sl_quality` — SL in liquidity trap (just above/below obvious swing) = 8; structural = 0–2
- `rrr_adequacy` — RRR < 1.0 = 10; 1.0–1.5 = 6; ≥ 1.5 = 0
- `spread_risk` — spread > 3 pips = 10 and flag "SPREAD_TOO_WIDE"; 2–3 = 4; < 2 = 0
- `structural_risk` — intervention zone (price > 155 and BUY) = 10 and flag "INTERVENTION_ZONE"; carry unwind signals (VIX > 25 on long) = 6

---

### Step 7 — `backend/agents/debate_engine.py`

```python
def evaluate(
    opp1: OpportunityResult,
    opp2: OpportunityResult,
    risk1: RiskResult,
    risk2: RiskResult,
    rrr: float | None,
    direction: str | None,
    strategy_context: dict,
    indicators: IndicatorCache
) -> tuple[int, int, str, list[str], list[str], dict]:
    # Returns: (confidence, probability, status, reasons_for, reasons_against, agent_scores)
```

Implementation (exact formulas from spec):

```python
# Step 1: base scores
opportunity_score  = (opp1.aggregate_score + opp2.aggregate_score) / 2
opposition_score   = (risk1.risk_score + risk2.risk_score) / 2

# Step 2: bonuses/penalties
alignment_bonus        = 5.0 if abs(opp1.aggregate_score - opp2.aggregate_score) <= 1.5 else 0.0
conflict_penalty       = 5.0 if abs(opp1.aggregate_score - opp2.aggregate_score) > 3.0 else 0.0
shared_flags           = set(risk1.risk_flags) & set(risk2.risk_flags)
risk_alignment_penalty = 5.0 if shared_flags else 0.0

# Step 3: net_score
net_score = (opportunity_score - opposition_score
             + alignment_bonus - conflict_penalty - risk_alignment_penalty)

# Step 4: confidence (FR-2-48)
confidence = max(0, min(100, round(((net_score + 20) / 35) * 100)))

# Step 5: probability (FR-2-49 — equal thirds)
rule_compliance   = opp1.dimension_scores.get("rule_compliance", 0) * 10
structure_quality = opp1.dimension_scores.get("structure_quality", 0) * 10
trend_alignment   = opp1.dimension_scores.get("trend_alignment", 0) * 10
probability = max(0, min(100, round((rule_compliance + structure_quality + trend_alignment) / 3)))

# Step 6: critical override checks (FR-2-52 through FR-2-55)
all_risk_flags = set(risk1.risk_flags) | set(risk2.risk_flags)
if "NEWS_IMMINENT" in all_risk_flags:
    return (confidence, probability, "NO_TRADE", [], ["NEWS_IMMINENT"], agent_scores)
if "INTERVENTION_ZONE" in all_risk_flags:
    return (..., "NO_TRADE", [], ["INTERVENTION_ZONE"], agent_scores)
if "SPREAD_TOO_WIDE" in all_risk_flags:
    return (..., "NO_TRADE", [], ["SPREAD_TOO_WIDE"], agent_scores)
if shared_flags - {"NEWS_IMMINENT", "INTERVENTION_ZONE", "SPREAD_TOO_WIDE"}:
    return (..., "NO_TRADE", [], [list(shared_flags)[0]], agent_scores)

# Step 7: VALID_TRADE threshold (FR-2-50)
rrr_ok = rrr is not None and rrr >= MIN_RRR
if confidence >= CONFIDENCE_THRESHOLD and probability >= PROBABILITY_THRESHOLD and rrr_ok:
    return (..., "VALID_TRADE", combined_reasons_for, [], agent_scores)

# Step 8: everything else is NO_TRADE
return (..., "NO_TRADE", [], combined_reasons_against, agent_scores)
```

Note: WAIT_FOR_LEVELS is set by the strategy module before calling the debate engine — it is not determined by the engine itself. Strategies that detect a directionally valid setup where price hasn't reached the zone return WAIT_FOR_LEVELS directly from `check_long_conditions()` / `check_short_conditions()`, bypassing the debate engine scoring path.

---

### Steps 8–13 — Strategy Modules

All 20 modules follow this exact structure:

```python
# backend/strategies/s01_mtf_trend.py

@dataclass
class S1Config:
    ema_periods: list[int] = field(default_factory=lambda: [20, 50, 200])
    macd_fast: int = 12; macd_slow: int = 26; macd_signal: int = 9
    atr_period: int = 14
    h4_pullback_atr_mult: float = 0.3
    min_h4_atr_pips: float = 40; max_h4_atr_pips: float = 120
    active_dimensions: list[str] = field(default_factory=lambda: [
        "rule_compliance", "trend_alignment", "confluence",
        "entry_precision", "sl_logic", "tp_realism", "rrr_quality"
    ])

class S1MTFTrend(BaseStrategy):
    STRATEGY_ID   = 1
    STRATEGY_NAME = "Multi-Timeframe Trend Alignment"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES    = ["D", "H4", "H1"]

    def __init__(self, indicators: IndicatorCache):
        super().__init__(indicators)
        self.cfg = S1Config()

    def evaluate(self) -> StrategyResult:
        long = self.check_long_conditions()
        short = self.check_short_conditions()
        direction, ctx = (long if long["valid"] else short) ...
        # Run 4 agents, debate engine, return StrategyResult

    def check_long_conditions(self) -> dict:
        ind = self.ind
        # Daily bias
        if not (ind.d_ema50 > ind.d_ema200 and ind.usdjpy_price > ind.d_ema50):
            return {"valid": False, "reason": "Daily bearish bias"}
        # H4 structure
        h4_dist = abs(ind.usdjpy_price - ind.h4_ema20)
        if h4_dist > self.cfg.h4_pullback_atr_mult * ind.h4_atr14:
            return {"valid": False, "reason": "H4 not at EMA20 pullback"}
        # Check H4 higher-low (swing_low_h4 > prior swing_low — strategy passes context)
        # H1 trigger
        if not (ind.h1_macd_line > ind.h1_macd_signal and ind.usdjpy_price > ind.h1_ema20):
            return {"valid": False, "reason": "H1 MACD/EMA trigger not met"}
        # Compute SL/TP
        entry = round(ind.usdjpy_price, 3)
        sl    = round(ind.swing_low_h1 - 1.5 * ind.h1_atr14, 3)  # need swing_low_h1 in cache
        tp1   = round(entry + (entry - sl), 3)       # 1R
        tp2   = round(entry + 2 * (entry - sl), 3)   # 2R
        rrr   = self._compute_rrr(entry, sl, tp1, "BUY")
        return {"valid": True, "direction": "BUY", "entry": entry,
                "sl": sl, "tp1": tp1, "tp2": tp2, "rrr": rrr,
                "conditions_met": 3, "total_conditions": 3}
```

**Note on swing_low_h1:** The IndicatorCache needs `swing_low_h1` and `swing_high_h1` added. These are required by S1, S6, S10, and others for H1-level SL placement. Add these two fields to the `IndicatorCache` dataclass.

#### Per-Strategy Key Logic (build order matches Steps 8–13)

**S1 — MTF Trend** (Step 8)
- Long gate: `d_ema50 > d_ema200 AND price > d_ema50` → `H4 price within 0.3×h4_atr14 of h4_ema20` → `h1_macd_line > h1_macd_signal AND price > h1_ema20`
- Short gate: mirror
- SL: `swing_low_h1 - 1.5×h1_atr14` (long) / `swing_high_h1 + 1.5×h1_atr14` (short)
- TP1: 1R, TP2: 2R

**S6 — MACD + 200 EMA** (Step 8)
- Long: `price > h1_ema200 AND h1_macd_line crossed above h1_macd_signal on current or prior bar`
- Cross detection: `h1_macd_histogram[-1] > 0 AND h1_macd_histogram[-2] <= 0` — needs prior bar histogram in IndicatorCache (`h1_macd_histogram_prev`)
- SL: `swing_low_h1 - 0.5×h1_atr14`
- TP1: 1R, TP2: 2R

**S7 — ADX + DMI** (Step 8)
- Gate: `h4_adx14 > 20`
- Long: `h4_plus_di14 > h4_minus_di14 AND h4_adx14 rising` (need `h4_adx14_prev`)
- Short: `h4_minus_di14 > h4_plus_di14`
- SL: `swing_low_h4 - 0.5×h4_atr14`
- TP1: 1.5R, TP2: 2.5R

**S2 — Ichimoku** (Step 9)
- All 4 conditions from spec FR-2-62: price vs Kumo, TK cross, Chikou span, future Kumo direction
- `kumo_top = max(h4_ichimoku["senkou_a"], h4_ichimoku["senkou_b"])`
- `kumo_bot = min(...)`
- TK cross: need prior Tenkan/Kijun values → add `h4_ichimoku_prev` to IndicatorCache
- SL: below Senkou B (Kumo bottom) for longs
- TP1: 2R, trail Kijun

**S3 — Carry Trade** (Step 9)
- Macro gate FIRST: `fed_rate - boj_rate > CARRY_SPREAD_THRESHOLD (2.5)` — if fails, return NO_TRADE immediately
- Daily: `price > d_ema50 AND d_ema50 > d_ema200`
- H4 pullback: Fib 38.2–61.8% (requires detecting last impulse — use `swing_high_d` and `swing_low_d`)
- Candle: `latest_engulf_bull_h4 == -1` (last bar) or pin bar detection on H4
- RSI: `40 <= h4_rsi14 <= 55`

**S4 — US10Y Yield** (Step 9)
- Staleness gate: `(now - us10y_timestamp).total_seconds() > FRED_STALENESS_HOURS * 3600` → NO_TRADE
- Need `us10y_10d_high` in IndicatorCache — but US10Y is a scalar, not a time series. **Decision:** add `us10y_10d_high: float` to IndicatorCache; `compute_indicators()` must compute this from a stored historical US10Y series (Phase 1 fred_feed.py should cache the last 10 readings). If not available, default to `us10y * 0.98` as a conservative fallback and log WARNING.
- `us10y > us10y_10d_high` → US10Y breaking out
- `price > d_ema20`
- H4 pullback to EMA20 + bullish rejection candle

**S5 — Confluence** (Step 9)
- Four factors must all be true: (1) SR proximity within 30 pips of `d_pivot_pp/r1/s1`, (2) engulfing or pin bar on H4, (3) `h4_rsi14` between 40–65 (not extreme), (4) `price > h4_ema50` for longs
- All four required for VALID_TRADE; 3 of 4 → WAIT_FOR_LEVELS

**S10 — 50/200 EMA Crossover** (Step 9)
- Crossover state: need `h4_ema50_prev` and `h4_ema200_prev` in IndicatorCache to detect recent cross
- Add `h4_ema50_prev: float` and `h4_ema200_prev: float` to IndicatorCache
- Recent bull cross = `h4_ema50 > h4_ema200 AND h4_ema50_prev <= h4_ema200_prev` within last 5 H4 bars — store `h4_ema_cross_bars_ago: int | None`
- Pullback: price returned within 30 pips of crossover level after diverging

**S12 — Donchian/Turtle** (Step 9)
- `price > d_donchian_upper` (long) or `price < d_donchian_lower` (short) on Daily close
- Intervention zone check for longs: price > 155 → WAIT_FOR_LEVELS

**S8 — Tokyo Breakout** (Step 10)
- Session gate: `current_session == "TOKYO" or (current_session == "LONDON" and hour < 11)` — "within 2 hours post-Tokyo"
- Range: need Tokyo high/low from 00:00–09:00 UTC bars — requires M30 or H1 bars for the current session
- Add `tokyo_session_high: float` and `tokyo_session_low: float` to IndicatorCache
- In `compute_indicators()`: filter H1/M30 bars to 00:00–09:00 UTC today; `tokyo_high = max(high)`, `tokyo_low = min(low)`
- Breakout: `price > tokyo_high + 0.1×h1_atr14` (small buffer) → long signal
- SL: `tokyo_low - 0.5×h1_atr14`

**S11 — Asian Range Fade** (Step 10)
- Regime gate: `h4_adx14 < 25` (FR-2-71)
- Session gate: if `current_session == "TOKYO"` and hour is between `S11_RANGE_START_UTC` (0) and `S11_RANGE_END_UTC` (6) → NO_TRADE("RANGE_BUILDING") (FR-2-71b)
- Range: same `tokyo_session_high/low` from IndicatorCache (00:00–06:00 UTC subset)
- Fade signal: `price >= tokyo_session_high - 0.2×h1_atr14` → SHORT; `price <= tokyo_session_low + 0.2×h1_atr14` → LONG
- SL: beyond range extreme + 0.3×h1_atr14

**S13 — London Breakout** (Step 10)
- Session gate: hour must be 7, 8, or 9 UTC (London open window)
- `london_breakout_high`: max of H1 bars from 00:00–06:59 UTC (Asian range for London to break)
- Add `london_pre_open_high: float` and `london_pre_open_low: float` to IndicatorCache
- Breakout: `price > london_pre_open_high + 0.1×h1_atr14` → long; mirror for short
- No major news imminent

**S19 — Daily Pivot** (Step 10)
- Entry: H1 close above `d_pivot_r1` → long; below `d_pivot_s1` → short
- SL: `d_pivot_pp` (below R1 for longs)
- TP1: `d_pivot_r2`

**S15 — Engulfing at Key Level** (Step 11)
- Key levels: `d_pivot_pp`, `d_pivot_r1`, `d_pivot_s1`, `swing_high_d`, `swing_low_d`
- Proximity: `abs(price - level) <= 20 pips` for any key level
- Bullish engulf: `latest_engulf_bull_h4 == -1` (last bar = current bar)

**S17 — Fibonacci Pullback** (Step 11)
- Impulse detection: use `swing_high_d` and `swing_low_d` — impulse size = `abs(swing_high_d - swing_low_d)`
- Qualifying check: `impulse_size >= S17_MIN_IMPULSE_ATR_MULT × h4_atr14 AND impulse_size >= S17_MIN_IMPULSE_PIPS / 100` (pips to price)
- Fib levels: `fib_50 = swing_low + 0.50 × impulse_size`, `fib_618 = swing_low + 0.618 × impulse_size` (for bull impulse)
- Entry zone: `fib_618 <= price <= fib_50`

**S18 — Inside Bar** (Step 11)
- `inside_bar_d == True` → WAIT_FOR_LEVELS with `wait_zone = "Above {mother_bar_high} (long) or Below {mother_bar_low} (short)"`
- Need `d_bar_high_prev: float` (mother bar high) and `d_bar_low_prev: float` in IndicatorCache
- If breakout already in progress (price outside mother bar), evaluate as entry signal

**S14 — Bollinger MR** (Step 12)
- Regime gate: `h4_adx14 < 25` (FR-2-74)
- Long: `price <= h1_bb_lower` (oversold at lower band) + reversal candle
- Short: `price >= h1_bb_upper` + reversal candle
- Do NOT enter if price has been outside the band for > 3 consecutive bars (too extended) — need to track consecutive closes outside band — add `h1_bars_below_bb_lower: int` and `h1_bars_above_bb_upper: int` to IndicatorCache

**S16 — RSI MR** (Step 12)
- Long: `h1_rsi14 < 30` (oversold); Short: `h1_rsi14 > 70` (overbought)
- Regime gate: if RSI sustained above 60 (for short attempt) or below 40 (for long attempt) for 4+ consecutive bars → NO_TRADE (trend too strong). Add `h1_rsi14_bars_below_40: int` and `h1_rsi14_bars_above_60: int` to IndicatorCache

**S9 — Keltner Breakout** (Step 12)
- Long: `price > h1_keltner_upper AND h4_adx14 > 20`
- Short: `price < h1_keltner_lower AND h4_adx14 > 20`
- SL: `h1_keltner_mid` (EMA20)

**S20 — Post-News Breakout** (Step 13 — most complex)
- Gate 1: `calendar_timestamp` not None and age < 24h (FR-2-81)
- Gate 2: a high-impact event occurred within the last 90 minutes — check cached event list for events in `(now - 90min, now)` window (FR-2-80)
- Direction bias: determined by event type — FOMC hawkish/CPI beat → BUY; BoJ hike → SELL; need `last_news_event_name: str` and `last_news_event_time: datetime` in IndicatorCache
- Entry: H1 close in the post-news breakout direction (price has moved > 0.5×h1_atr14 from pre-event price)
- SL: pre-event level ± 0.5×h1_atr14

---

### Step 14 — `backend/scheduler.py` (H1 orchestrator)

Replace the stub H1 job body with the full evaluation pipeline:

```python
def _run_h1_evaluation():
    """Full 20-strategy evaluation cycle. Fires at HH:02:00 UTC."""
    start = time.time()
    log.info("[Scheduler] H1 evaluation cycle started")

    # 1. Pull OHLCV
    bars = {tf: get_ohlcv(tf, bars=500) for tf in ["M15","M30","H1","H4","D1"]}

    # 2. Check MT5 connectivity
    if any(v is None for v in bars.values()):
        _write_all_no_trade("MT5_DISCONNECTED")
        return

    # 3. Check minimum bar counts
    counts = {tf: len(df) for tf, df in bars.items()}
    if (counts["H1"] < MIN_H1_BARS or counts["H4"] < MIN_H4_BARS
            or counts["D1"] < MIN_DAILY_BARS):
        log.warning(f"[Scheduler] Insufficient bars: {counts}")
        _write_all_no_trade("INSUFFICIENT_BARS")
        return

    # 4. Compute shared indicator cache (once)
    indicators = compute_indicators(
        bars=bars,
        us10y=get_us10y(),
        us10y_timestamp=get_us10y_last_fetch(),
        fed_rate=get_fed_funds_rate(),
        boj_rate=BOJ_RATE,
        calendar_timestamp=get_calendar_last_fetch(),
        news_imminent=is_news_imminent(),
        current_price=get_current_price(),
        current_spread_pips=get_current_spread_pips()  # new helper in mt5_feed.py
    )

    # 5. Evaluate all 20 strategies
    STRATEGIES = [S1MTFTrend, S2Ichimoku, ..., S20PostNews]
    results = []
    for StrategyClass in STRATEGIES:
        try:
            result = StrategyClass(indicators).evaluate()
        except Exception as e:
            log.error(f"[Strategy {StrategyClass.STRATEGY_ID}] {e}")
            result = BaseStrategy._no_trade(
                StrategyClass.STRATEGY_ID, StrategyClass.STRATEGY_NAME,
                StrategyClass.STRATEGY_TYPE, "EVALUATION_ERROR",
                StrategyClass.TIMEFRAMES
            )
        results.append(result)

    # 6. Batch write
    for r in results:
        write_strategy_result(r)

    # 7. Log duration
    ms = round((time.time() - start) * 1000)
    log.info(f"[Scheduler] H1 cycle complete in {ms}ms")
```

Also add `get_current_spread_pips()` to `backend/data/mt5_feed.py`:
```python
def get_current_spread_pips() -> float:
    tick = mt5.symbol_info_tick(MT5_SYMBOL)
    if tick is None: return 0.0
    return round((tick.ask - tick.bid) * 100, 2)  # USDJPY: 100 pips = 1 JPY
```

---

### Step 15 — `backend/api/strategies.py` (update)

Replace stub with real queries:

```python
@router.get("/strategies")
def get_all_strategies():
    results = get_latest_strategy_results()   # from signal_store
    if not results:
        raise HTTPException(503, detail="No strategy results available")
    return {"success": True, "data": results, "error": None}

@router.get("/strategy/{strategy_id}")
def get_strategy(strategy_id: int):
    if not 1 <= strategy_id <= 20:
        return JSONResponse(status_code=404,
            content={"success": False, "data": None, "error": "Strategy not found"})
    result = get_latest_strategy_result(strategy_id)
    if not result:
        return JSONResponse(status_code=503,
            content={"success": False, "data": None,
                     "error": f"No results available for strategy {strategy_id}"})
    return {"success": True, "data": result, "error": None}
```

---

## IndicatorCache Additions (beyond spec Section 5.1)

The following fields are required by specific strategy modules and must be added to the `IndicatorCache` dataclass and computed in `compute_indicators()`:

| Field | Type | Required By | How Computed |
|---|---|---|---|
| `swing_low_h1` | float | S1, S6, S9 | 5-bar fractal on H1 |
| `swing_high_h1` | float | S1, S6, S9 | 5-bar fractal on H1 |
| `h1_macd_histogram_prev` | float | S6 | `macd_df["MACDh_12_26_9"].iloc[-2]` |
| `h4_adx14_prev` | float | S7 | `adx_df["ADX_14"].iloc[-2]` |
| `h4_ichimoku_prev` | dict | S2 | Tenkan/Kijun from prior H4 bar |
| `h4_ema50_prev` | float | S10 | `ema_df["EMA_50"].iloc[-2]` on H4 |
| `h4_ema200_prev` | float | S10 | `ema_df["EMA_200"].iloc[-2]` on H4 |
| `h4_ema_cross_bars_ago` | int or None | S10 | Scan last 20 bars for crossover |
| `us10y_10d_high` | float | S4 | Max of last 10 US10Y readings from FRED cache |
| `tokyo_session_high` | float | S8, S11 | Max(high) of M30/H1 bars in 00:00–09:00 UTC today |
| `tokyo_session_low` | float | S8, S11 | Min(low) of M30/H1 bars in 00:00–09:00 UTC today |
| `london_pre_open_high` | float | S13 | Max(high) of H1 bars in 00:00–06:59 UTC today |
| `london_pre_open_low` | float | S13 | Min(low) of H1 bars in 00:00–06:59 UTC today |
| `h1_bars_below_bb_lower` | int | S14 | Count consecutive H1 closes below bb_lower |
| `h1_bars_above_bb_upper` | int | S14 | Count consecutive H1 closes above bb_upper |
| `h1_rsi14_bars_below_40` | int | S16 | Count consecutive H1 RSI < 40 bars |
| `h1_rsi14_bars_above_60` | int | S16 | Count consecutive H1 RSI > 60 bars |
| `d_bar_high_prev` | float | S18 | `bars["D"].iloc[-2]["high"]` |
| `d_bar_low_prev` | float | S18 | `bars["D"].iloc[-2]["low"]` |
| `last_news_event_name` | str or None | S20 | Most recent high-impact event in last 90 min |
| `last_news_event_time` | datetime or None | S20 | Timestamp of that event |

---

## Import Dependency Rules

```
config.py              ← dotenv, os, pathlib only
signal_store.py        ← config, sqlite3, json, logging
base_strategy.py       ← config, pandas, pandas_ta, dataclasses, datetime, abc
opportunity_agent.py   ← base_strategy (IndicatorCache, OpportunityResult only)
risk_agent.py          ← base_strategy (IndicatorCache, RiskResult only)
debate_engine.py       ← opportunity_agent, risk_agent, config
s0N_*.py               ← base_strategy, opportunity_agent, risk_agent, debate_engine, config
scheduler.py           ← config, all data feeds, signal_store, base_strategy, all strategies
api/strategies.py      ← signal_store, fastapi
```

No circular imports. Strategy modules MUST NOT import from each other.

---

## Critical Files

| File | Why Critical |
|---|---|
| `backend/strategies/base_strategy.py` | All 20 strategies and all 4 agents depend on it; IndicatorCache shape defines the API surface |
| `backend/agents/debate_engine.py` | Scoring formula; exact thresholds from spec (FR-2-48, FR-2-49, FR-2-50) |
| `backend/scheduler.py` | H1 orchestrator — orchestration correctness, error isolation, batch write |
| `backend/db/signal_store.py` | JSON serialisation/deserialisation of all Phase 2 fields |
| `backend/config.py` | Single source of all thresholds; no magic numbers anywhere else |

---

## Verification Against Acceptance Criteria

| AC | Verification Step |
|---|---|
| AC-2-01 | `GET /api/strategies` → count items in `data` array → exactly 20 |
| AC-2-02 | Inspect each of 20 items → `status` in {VALID_TRADE, WAIT_FOR_LEVELS, NO_TRADE} |
| AC-2-03 | Filter for status=VALID_TRADE → each has non-null entry, sl, tp1 and rrr ≥ 1.5 |
| AC-2-04 | Filter for status=NO_TRADE → each has non-empty `reasons_against` |
| AC-2-05 | Wait until HH:02 UTC → tail logs → see `[Scheduler] H1 evaluation cycle` entries |
| AC-2-06 | `SELECT strategy_id, COUNT(*) FROM signals WHERE timestamp LIKE '…' GROUP BY strategy_id` → 20 rows |
| AC-2-07 | `GET /api/strategy/1` → response has `agent_scores` with 4 keys |
| AC-2-08 | Set `BOJ_RATE = 3.75` in config (spread=0.0 < 2.5) → evaluate S3 → status=NO_TRADE |
| AC-2-09 | Patch `datetime.now(UTC).hour = 12` in test → evaluate S8 → NO_TRADE("OUTSIDE_SESSION_WINDOW") |
| AC-2-10 | Patch hour = 20 → evaluate S13 → NO_TRADE("OUTSIDE_SESSION_WINDOW") |
| AC-2-11 | Pass `us10y_timestamp = now - 7h` to compute_indicators → evaluate S4 → NO_TRADE("FRED_DATA_STALE") |
| AC-2-12 | Pass `last_news_event_time = now - 100min` → evaluate S20 → NO_TRADE("OUTSIDE_POST_NEWS_WINDOW") |
| AC-2-13 | Unit test: construct mock agent results with conf=80, prob=75, rrr=2.0, no flags → debate_engine → VALID_TRADE |
| AC-2-14 | Unit test: same inputs but `news_imminent=True` → NO_TRADE("NEWS_IMMINENT") |
| AC-2-15 | Unit test: `usdjpy_price=156.0, direction=BUY` → NO_TRADE("INTERVENTION_ZONE") |
| AC-2-16 | Unit test: `current_spread_pips=3.5` → NO_TRADE("SPREAD_TOO_WIDE") |
| AC-2-17 | Inject exception in S4 evaluate → remaining 19 strategies complete and 19 rows written |
| AC-2-18 | Instantiate all 20 strategy classes with mock IndicatorCache → evaluate() → no MT5 import required |
| AC-2-19 | `GET /api/strategy/25` → HTTP 404, `{"success":false,"error":"Strategy not found"}` |
| AC-2-20 | `grep -r "155.00" backend/ --include="*.py" \| grep -v config.py` → no output |

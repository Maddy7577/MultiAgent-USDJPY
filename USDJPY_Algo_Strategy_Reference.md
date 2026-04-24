# USDJPY Algorithmic Trading Strategy Reference

**Version:** 1.0
**Last Updated:** April 24, 2026
**Pair:** USD/JPY
**Purpose:** Complete algo-ready specification for 20 trading strategies, formatted for dashboard integration, backtesting, and systematic deployment.

---

## Document Purpose

This document is designed as a **single source of truth** for building a USDJPY trading dashboard and algorithmic trading system. Every strategy is specified with:

- **Machine-readable parameters** (indicators, thresholds, timeframes)
- **Explicit entry and exit rules** (no ambiguity)
- **Risk management specs** (stop loss, take profit, position sizing)
- **Pseudocode** that translates directly to Python/Pine Script/MQL
- **Filters** to reduce false signals
- **Known risks** specific to USDJPY
- **Backtest KPI targets** for validation

Each strategy section can be parsed independently for integration into a strategy-selection UI, a signal-scanning engine, or an automated execution layer.

---

## Table of Contents

1. [Global USDJPY Context](#global-usdjpy-context)
2. [Data Requirements](#data-requirements)
3. [Risk Management Framework](#risk-management-framework)
4. [Master Strategy Comparison Table](#master-strategy-comparison-table)
5. Strategy Specifications (1–20):
   1. [Multi-Timeframe Trend Alignment](#strategy-1-multi-timeframe-trend-alignment)
   2. [Full Ichimoku Kinko Hyo System](#strategy-2-full-ichimoku-kinko-hyo-system)
   3. [Carry-Trade Pullback](#strategy-3-carry-trade-pullback)
   4. [US 10Y Yield Correlation Bias](#strategy-4-us-10y-yield-correlation-bias)
   5. [Confluence System](#strategy-5-confluence-system-trend--sr--candle--rsi-divergence)
   6. [MACD + 200 EMA Trend-Following](#strategy-6-macd--200-ema-trend-following)
   7. [ADX + DMI Trend-Strength Filter](#strategy-7-adx--dmi-trend-strength-filter)
   8. [Tokyo Range Breakout](#strategy-8-tokyo-range-breakout-big-ben-adapted)
   9. [Keltner Channel Breakout](#strategy-9-keltner-channel-breakout-king-keltner)
   10. [50/200 EMA Crossover Pullback](#strategy-10-50200-ema-crossover-pullback)
   11. [Asian Session Range Fade](#strategy-11-asian-session-range-fade)
   12. [Donchian/Turtle Breakout](#strategy-12-donchianturtle-breakout-system-1)
   13. [London Open Breakout](#strategy-13-london-open-breakout-trend-filtered)
   14. [Bollinger Band Mean Reversion](#strategy-14-bollinger-band-mean-reversion)
   15. [Engulfing Candle at Key Level](#strategy-15-engulfing-candle-at-key-level)
   16. [RSI Mean Reversion](#strategy-16-rsi14-mean-reversion-with-trend-filter)
   17. [Fibonacci Pullback](#strategy-17-fibonacci-50--618-pullback)
   18. [Inside Bar Breakout](#strategy-18-inside-bar-breakout-mother-bar)
   19. [Daily Pivot Point Breakout](#strategy-19-daily-pivot-point-breakout)
   20. [Post-News Breakout](#strategy-20-post-news-breakout-nfp--fomc--boj)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Dashboard Integration Guide](#dashboard-integration-guide)
8. [Appendix: Common Calculations](#appendix-common-calculations)

---

## Global USDJPY Context

### Pair Characteristics

| Attribute | Value | Implication |
|-----------|-------|-------------|
| **Typical Daily Range** | 90–130 pips | Base for stop sizing |
| **Event-Day Range** | 150–250+ pips | Widen stops on event days |
| **ECN Spread** | 0.1–0.3 pips | Minimal cost on limit orders |
| **Retail Spread** | 0.8–1.5 pips | Acceptable for H1+ strategies |
| **Event Spread** | 3–10 pips | Avoid market orders during releases |
| **Pip Value (1 lot)** | ~$6.70 (at 150.00) | Position sizing calculation |
| **Best Sessions** | Tokyo, London, NY | All three are active |
| **Correlation (US10Y)** | +0.70 to +0.95 | Primary macro driver |
| **Correlation (DXY)** | +0.60 to +0.85 | Secondary confirmation |
| **Correlation (Nikkei)** | +0.40 to +0.70 | Risk-on/off proxy |

### Structural Drivers

1. **Fed-BoJ Interest Rate Differential**: Currently Fed 3.75–4.00% vs BoJ 0.75% (post-Dec 2025 hike). Drives multi-month trends through carry-trade flows.
2. **US 10Y Treasury Yields**: The single strongest yield-FX correlation in G10. Rising yields = USDJPY bullish.
3. **BoJ Policy**: Yield Curve Control legacy, intervention threats, and policy normalization shape volatility regimes.
4. **MoF Intervention Zones**: Historical intervention at 145–146 (Sep 2022), 152 (Oct 2022), 160 (Apr–May 2024). Treat 155+ as asymmetric-risk zone.
5. **Carry-Trade Unwinds**: August 2024 saw USDJPY drop 162→142 in 3 weeks. Fat left tails require tail-risk hedging.

### Event Calendar (High-Impact)

| Event | Frequency | Typical Move |
|-------|-----------|--------------|
| FOMC Decision | 8x/year | 80–200 pips |
| BoJ Decision | 8x/year | 60–200 pips |
| NFP (US Jobs) | Monthly | 50–150 pips |
| US CPI | Monthly | 50–120 pips |
| US PCE | Monthly | 40–80 pips |
| BoJ Governor Speeches | Ad-hoc | 30–100 pips |
| US 10Y Auction | Monthly | 20–60 pips |
| Tokyo CPI | Monthly | 20–50 pips |

### Holiday Calendar (Reduce Size or Skip)

- **Golden Week**: Late April / Early May (Japanese holidays)
- **Obon**: Mid-August (Japanese summer vacation)
- **Japanese New Year**: December 29 – January 3
- **US Thanksgiving + Black Friday**: Late November
- **Christmas / New Year (Western)**: December 24 – January 2

---

## Data Requirements

### Minimum Data Feeds

| Feed | Source Examples | Purpose |
|------|----------------|---------|
| USDJPY OHLCV | Broker API, TradingView, Dukascopy | Primary price data (M15, M30, H1, H4, D) |
| US 10Y Yield | FRED, CBOE (^TNX), broker | Correlation strategies |
| DXY (Dollar Index) | ICE, broker | USD strength filter |
| Economic Calendar | Forex Factory API, Investing.com, FXStreet | Event filtering |
| Fed Funds Rate | FRED (DFF) | Macro bias |
| BoJ Policy Rate | BoJ website, FRED | Macro bias |
| JPY COT Report | CFTC (weekly) | Positioning extremes |
| VIX | CBOE | Risk-on/off regime |

### Historical Data Depth (Minimum)

- **Intraday strategies (M15–H1)**: 3 years of tick or M1 data
- **Swing strategies (H4–D)**: 10 years of Daily data
- **Correlation strategies**: 5 years synchronized USDJPY + US10Y
- **Macro strategies**: 10 years of rate differential history

---

## Risk Management Framework

### Position Sizing Formula

```
Position Size (lots) = (Account Equity × Risk %) / (Stop Distance in pips × Pip Value)

Example:
  Equity = $10,000
  Risk per trade = 0.5% = $50
  Stop Distance = 25 pips
  Pip Value at 150.00 = $6.70 per 0.01 lot
  Position Size = $50 / (25 × $6.70) = 0.30 lots
```

### Portfolio-Level Rules

| Rule | Value |
|------|-------|
| **Max risk per trade** | 0.5–1.0% equity |
| **Max concurrent USDJPY positions** | 2 (across strategies) |
| **Max daily drawdown** | 3% (halt trading) |
| **Max weekly drawdown** | 6% (halt trading) |
| **Max monthly drawdown** | 10% (review all systems) |
| **Correlation cap** | Don't run 3+ trend systems simultaneously long/short |

### Intervention-Zone Protocol (Price > 155.00)

1. Reduce position size by 50% on all long strategies
2. Widen stops by 1.5× (avoid tight-stop flush-outs)
3. Monitor MoF verbal intervention feed hourly
4. Skip mean-reversion longs at resistance (asymmetric tail risk)

---

## Master Strategy Comparison Table

| # | Strategy | Type | Timeframe | Win Rate | R:R | Trades/Week | Algo Fit | Key Edge |
|---|----------|------|-----------|----------|-----|-------------|----------|----------|
| 1 | Multi-Timeframe Trend Alignment | Trend | D+H4+H1 | 45–55% | 1:2–1:3 | 2–5 | HIGH | Fractal carry-trade structure |
| 2 | Full Ichimoku System | Trend/Japanese | H4/D | 40–50% | 1:2–1:3 | 1–2 | HIGH | Designed for Japanese markets |
| 3 | Carry-Trade Pullback | Hybrid | D bias, H4 entry | 50–60% | 1:2–1:3 | 0.5–1.5 | MED-HIGH | Exploits Fed-BoJ spread |
| 4 | US 10Y Yield Correlation | Correlation | D bias, H4 entry | 55–65% | 1:2–1:4 | 0.5–1.5 | HIGH | Highest yield-FX correlation |
| 5 | Confluence System | Multi-signal | D bias, H4 entry | 55–65% | 1:2–1:3 | 1–2 | MEDIUM | Round-number respect |
| 6 | MACD + 200 EMA | Trend | H1/H4 | 45–55% | 1:1–1:2 | 2–5 | HIGH | Simple, robust |
| 7 | ADX + DMI Filter | Trend Filter | H4 | 45–55% | 1:1.5–1:2 | 0–4 | HIGH | Regime classification |
| 8 | Tokyo Range Breakout | Session Breakout | M30/H1 | 40–50% | 1.5:1–2:1 | 3–4 | HIGH | Active Tokyo session |
| 9 | Keltner Channel Breakout | Volatility | H1/H4 | 40–50% | 1.5:1–2:1 | 2–4 | HIGH | Adaptive to vol regime |
| 10 | 50/200 EMA Crossover | Trend | H4 | 35–45% | 1:1.5–1:3 | 0.5–2 | VERY HIGH | Captures regime shifts |
| 11 | Asian Session Range Fade | Mean Reversion | M30 | 60–70% | 0.5:1–0.8:1 | 4–6 | MED-HIGH | BoJ fix flows |
| 12 | Donchian/Turtle Breakout | Trend Breakout | D (H4) | 35–45% | 1:2–1:4 | 0.25–0.75 | VERY HIGH | Designed for FX/commodities |
| 13 | London Open Breakout | Session Breakout | M30/H1 | 45–55% | 2:1 | ~3 | HIGH | EU bond market open |
| 14 | Bollinger Band MR | Mean Reversion | H1/H4 | 55–70%* | 1:1–1:2 | 3–5 | HIGH | Round-number clustering |
| 15 | Engulfing at Key Level | Price Action | H4/D | 55–65% | 1:1.5–1:2 | 2–4 | HIGH | Bulkowski 79% reversal |
| 16 | RSI Mean Reversion | Mean Reversion | H1/H4 | 50–62% | 1:1–1:1.5 | 2–4 | HIGH | Range regime edge |
| 17 | Fibonacci 50/61.8 Pullback | Retracement | H4/D | 45–58% | 1:2–1:3 | 1–3 | MEDIUM | Clean pullback structure |
| 18 | Inside Bar Breakout | Price Action | D (H4) | 45–55% | 1:2 | 0.5–1 | HIGH | Trend-consolidation-break |
| 19 | Daily Pivot Breakout | Session/Levels | M30/H1 | 40–48% | 1.5:1–2:1 | 3–4 | HIGH | NY close alignment |
| 20 | Post-News Breakout | Event-driven | H1 | 45–55% | 1:2 | ~0.25 | HIGH | USDJPY policy-sensitive |

*_Bollinger MR: 55–70% in ranging regimes, 30–45% in trending regimes. Regime filter mandatory._

### Summary Statistics

- **Strategies with midpoint win rate >50%**: 8 of 20 (40%)
- **Strategies with >50% potential in favorable regimes**: 12 of 20 (60%)
- **Highest algo-fit (VERY HIGH)**: 2 strategies (#10, #12)
- **HIGH algo-fit**: 13 strategies
- **USDJPY-specific edge strategies**: 7 (#2, #3, #4, #5, #8, #11, #15)

---
## Strategy 1: Multi-Timeframe Trend Alignment

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 1 |
| **Category** | Trend Following |
| **Timeframes** | Daily (bias) + H4 (structure) + H1 (entry) |
| **Session Filter** | London + NY overlap (12:00–16:00 GMT) preferred |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 1:2 to 1:3 |
| **Trades/Day** | 0–1 |
| **Trades/Week** | 2–5 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Carry-trade driven trends produce fractal structure that aligns cleanly across H1, H4, and Daily timeframes. USDJPY is one of the most trend-persistent majors because yield-differential flows sustain directional moves for weeks or months. Requiring alignment across three timeframes filters out most counter-trend noise.

### Macro Bias Inputs
- Fed funds rate vs BoJ policy rate differential (source: FRED, BoJ)
- US 10Y yield direction (rising = USDJPY bullish bias)
- Risk sentiment: VIX < 20 supports carry/long bias
- DXY trend alignment confirms USD side of the equation

### Indicators Required
- EMA(20), EMA(50), EMA(200) on each timeframe (D, H4, H1)
- MACD(12, 26, 9) on H1 for entry timing
- ATR(14) on H4 for stop sizing
- Swing high/low detection (fractals or last 5-bar pivots)

### Long Entry Rules
1. **Daily bias**: Close > EMA50 AND EMA50 > EMA200 (bullish regime confirmed)
2. **H4 structure**: Price pulled back to within 0.3×ATR of H4 EMA20 AND printing a higher-low
3. **H1 trigger**: MACD line crosses above signal line AND price closes above H1 EMA20
4. **Confirmation candle**: The next H1 bar closes bullish (close > open) and above the trigger bar high

### Short Entry Rules
1. **Daily bias**: Close < EMA50 AND EMA50 < EMA200
2. **H4 structure**: Price rallied to within 0.3×ATR of H4 EMA20 AND printing a lower-high
3. **H1 trigger**: MACD line crosses below signal line AND price closes below H1 EMA20
4. **Confirmation candle**: Next H1 bar closes bearish below trigger bar low

### Stop Loss
- Below most recent H1 swing low for longs (above swing high for shorts)
- Minimum distance: 1.5 × ATR(14) on H1

### Take Profit
- **TP1**: 1R — close 50% of position
- **TP2**: 2R — close 30% of position
- **Runner**: Trail H4 EMA20 — close remaining 20% on H4 close beyond EMA20

### Position Sizing
- Risk 0.5% of account equity per trade
- Maximum 2 concurrent USDJPY positions across all strategies

### Exit Rules (In Addition to SL/TP)
- **Time stop**: Close position if not at +1R within 18 H1 bars
- **Invalidation**: Immediate exit if H4 closes below EMA50 (for longs)
- **Overnight rule**: Hard exit before 22:00 GMT if position is underwater
- **Event rule**: Exit all before major events (FOMC, BoJ, NFP, CPI)

### Filters (Improve Signal Quality)
- ADX(14) on H4 > 20 (confirms trending regime)
- ATR(14) on H4 between 40 and 120 pips (not too quiet, not too wild)
- Skip first 30 minutes of Tokyo open and last 30 minutes of NY close

### Known Risks
- False alignment during Tokyo session reversals
- BoJ intervention risk above 155.00 (reduce size)
- Chop losses during pre-NFP and pre-FOMC consolidation
- Overnight gap risk on Sunday open if holding Friday position

### Pseudocode
```python
# Long setup per bar close
def check_long_entry():
    # Daily bias check
    if not (Daily.Close > Daily.EMA50 and Daily.EMA50 > Daily.EMA200):
        return False
    
    # H4 structure check
    if abs(H4.Close - H4.EMA20) > 0.3 * H4.ATR14:
        return False
    if H4.LastPivot != "higher_low":
        return False
    
    # H1 trigger check
    if not (H1.MACD_line crosses_above H1.MACD_signal):
        return False
    if H1.Close <= H1.EMA20:
        return False
    
    # Confirmation
    wait_for_bar_close()
    if H1.Close > H1.Open and H1.Close > trigger_bar.high:
        # Execute trade
        entry = H1.Close
        swing_low = get_recent_swing_low()
        sl = swing_low - 1.5 * H1.ATR14
        tp1 = entry + 1 * (entry - sl)
        tp2 = entry + 2 * (entry - sl)
        trail_anchor = H4.EMA20
        return True
    return False
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥200 trades over 3 years |
| Profit factor | 1.4–1.8 |
| Max drawdown | 12–18% |
| Sharpe ratio | > 1.0 |
| Avg trade duration | 8–24 H1 bars |
| Win rate | 45–55% |

### Dashboard Signals to Surface
- Current Daily trend (Bullish/Bearish/Neutral) with EMA50 distance
- H4 pullback proximity (% distance from EMA20 in ATR units)
- H1 MACD state (bullish/bearish/crossing)
- Setup score (0–4 based on conditions met)
- Distance to nearest swing low/high for SL preview

---

## Strategy 2: Full Ichimoku Kinko Hyo System

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 2 |
| **Category** | Trend / Japanese Technical |
| **Timeframes** | H4 primary; Daily for confirmation |
| **Session Filter** | Any session (signals develop slowly) |
| **Win Rate** | 40–50% |
| **Risk:Reward** | 1:2 to 1:3 |
| **Trades/Day** | 0 |
| **Trades/Week** | 1–2 (H4); 0.25–1 (Daily) |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Invented by Goichi Hosoda specifically for Japanese markets in the 1960s. The five-line system is culturally dominant among Japanese institutional traders who trade USDJPY, creating self-fulfilling respect for the signals. The cloud acts as a dynamic support/resistance zone that aligns with institutional accumulation/distribution zones.

### Macro Bias Inputs (Optional)
- Fed-BoJ rate spread as long-term direction filter
- Chikou span (lagging) effectively encodes 26-period momentum regime
- Future Kumo thickness indicates projected volatility regime

### Indicators Required
- **Tenkan-sen (Conversion)**: (9-period high + 9-period low) / 2
- **Kijun-sen (Base)**: (26-period high + 26-period low) / 2
- **Senkou Span A**: (Tenkan + Kijun) / 2, plotted 26 periods ahead
- **Senkou Span B**: (52-period high + 52-period low) / 2, plotted 26 periods ahead
- **Chikou Span**: Current close plotted 26 periods back
- **The Cloud (Kumo)**: Area between Senkou A and Senkou B

### Long Entry Rules (All 4 Must Be True)
1. Price closes **ABOVE** the Kumo (cloud)
2. Bullish **TK cross** (Tenkan crosses above Kijun) AND this cross occurs **above** the cloud (strongest signal)
3. **Chikou Span** is above the price of 26 periods ago (clear of past price action)
4. **Future Kumo** (projected 26 bars ahead) is bullish (Senkou A > Senkou B)

**Entry execution**: On bar close when all 4 conditions true, OR on next bar retest of Tenkan/Kijun

### Short Entry Rules
Mirror all 4 conditions for shorts:
1. Price below Kumo
2. Bearish TK cross below cloud
3. Chikou below past price
4. Future Kumo bearish

### Stop Loss
- Below the cloud (Senkou B) for longs
- Above cloud for shorts
- Alternative (tighter): Below Kijun-sen

### Take Profit
- **TP1**: 2× risk — close 50%
- **Trail remainder**: Kijun-sen — exit on close beyond Kijun

### Position Sizing
- Risk 0.5–0.75% per trade
- Cloud-based stops are wider — size accordingly

### Exit Rules
- TK bearish cross while long = close immediately
- Price re-enters cloud = close immediately
- Chikou re-crosses price line = partial close (50%)
- Time exit: 40 H4 bars without TP reached

### Filters
- Kumo thickness > 0.5 × ATR(14) — avoid thin-cloud whipsaw periods
- Skip trades when Tenkan and Kijun are within 0.2 × ATR (flat market)
- Avoid entries when future Kumo is twisting (Senkou A/B crossing)

### Known Risks
- Lagging in fast reversal markets (all 4 conditions slow to invalidate)
- Subjective Chikou-span interpretation with multiple past candles nearby
- Wider stops reduce R:R vs swing-based systems
- Cloud gaps during Japanese holidays can invalidate projection logic

### Pseudocode
```python
def ichimoku_signals(bars):
    tenkan = (max(high, 9) + min(low, 9)) / 2
    kijun = (max(high, 26) + min(low, 26)) / 2
    senkou_a_future = (tenkan + kijun) / 2  # displaced +26
    senkou_b_future = (max(high, 52) + min(low, 52)) / 2  # displaced +26
    senkou_a_current = senkou_a[-26]  # current cloud
    senkou_b_current = senkou_b[-26]
    chikou = close  # plotted at bar -26
    
    kumo_top = max(senkou_a_current, senkou_b_current)
    kumo_bot = min(senkou_a_current, senkou_b_current)
    
    # Long conditions
    long_signal = (
        close > kumo_top and
        crossover(tenkan, kijun) and tenkan > kumo_top and
        chikou > close[-26] and
        senkou_a_future > senkou_b_future
    )
    
    if long_signal:
        entry = close
        sl = senkou_b_current - 0.5 * ATR14
        risk = entry - sl
        tp1 = entry + 2 * risk
        trail_anchor = kijun  # exit on close below
        return {"side": "long", "entry": entry, "sl": sl, "tp1": tp1}
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥150 trades over 5 years (H4) |
| Profit factor | 1.3–1.6 |
| Max drawdown | 15–22% |
| Win rate vs TK-only | +8–12 points from full 4-condition filter |
| Best regime | Strong trending months (rate-hike cycles) |

### Dashboard Signals to Surface
- All 5 Ichimoku lines plotted on H4/Daily
- 4-condition checklist with live status
- Kumo thickness (in pips and ATR units)
- Future Kumo direction (bullish/bearish/twisting)
- Distance from price to Kijun (trailing stop preview)

---

## Strategy 3: Carry-Trade Pullback

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 3 |
| **Category** | Hybrid (Macro Bias + Technical Entry) |
| **Timeframes** | Daily bias; H4 entry execution |
| **Session Filter** | London + NY sessions only |
| **Win Rate** | 50–60% |
| **Risk:Reward** | 1:2 to 1:3 |
| **Trades/Day** | 0 |
| **Trades/Week** | 0.5–1.5 |
| **Algo Fit** | MEDIUM-HIGH |

### Edge (Why It Works on USDJPY)
Directly monetizes USDJPY's defining characteristic — the Fed-BoJ interest rate differential. When the spread is wide and widening, long USDJPY pullbacks have a structural tailwind from global yield-hunting flows. Currently Fed 3.75–4.00% vs BoJ 0.75% (spread ~3.0–3.25%), which has narrowed from the 2024 peak of 5%+ but still supports structural long bias.

### Macro Bias Inputs (CRITICAL - Primary Gate)
- **PRIMARY**: Fed funds rate minus BoJ policy rate > 2.5% required for long bias
- **TREND**: Rate differential direction (widening or narrowing) over last 3 months
- **YIELD SPREAD**: US 10Y minus JGB 10Y yield spread > 2.5%
- **FORWARD GUIDANCE**: FOMC and BoJ language (hawkish/dovish tilt)
- **POSITIONING**: JPY net speculative positioning from CFTC COT reports (extremes warn of unwind)

### Indicators Required
- EMA(20), EMA(50) on Daily and H4
- Fibonacci retracement tool (auto-draw on last Daily impulse leg)
- RSI(14) on H4 (watching for non-oversold pullbacks, 40-55 zone)
- ATR(14) on Daily for stop sizing

### Long Entry Rules
1. **Macro gate**: Fed-BoJ spread > 2.5% AND spread widening or stable
2. **Daily trend**: Close > EMA50, EMA50 > EMA200 (confirmed uptrend)
3. **H4 pullback**: Price retraces to Fib 38.2–61.8% of last impulse OR to H4 EMA20/50 confluence
4. **Candle trigger**: Bullish engulfing or pin bar at pullback zone
5. **RSI confirmation**: RSI(14) H4 between 40 and 55 (pulled back but not oversold)

### Short Entry Rules
- Mirror for shorts **ONLY IF** Fed-BoJ spread narrowing AND Daily bearish alignment
- Short trades are historically lower quality when structural carry favors longs — **reduce size by 50%**

### Stop Loss
- Below the pullback swing low (longs)
- Typically 1.5–2.5 × ATR(H4)

### Take Profit
- **TP1**: Return to impulse high (typically 2R)
- **TP2**: 1.272 or 1.618 Fibonacci extension
- **Trail**: H4 EMA20 beyond TP1

### Position Sizing
- 0.75% per trade if macro gate fully aligned
- 0.4% if borderline (spread between 2.5–3.0% or trend unclear)

### Exit Rules
- Daily close below EMA50 = exit immediately (regime break)
- FOMC/BoJ surprise narrowing spread = flatten before event
- Intervention risk (price > 155): reduce size by 50% or skip
- Exit if 8 Daily bars elapse without fresh high

### Filters
- Skip FOMC and BoJ meeting weeks unless positioning for directional view
- Avoid trades when JPY net spec shorts > 2 std dev (unwind risk)
- No new entries in August (thin liquidity, carry unwind risk — ref August 2024)

### Known Risks
- **CARRY UNWIND**: August 2024 saw USDJPY drop 162→142 in 3 weeks with Nikkei -12% in a day
- **BoJ INTERVENTION**: April/May 2024 ~¥9.8tn sold at 160 level
- **BoJ SURPRISE HIKES**: Dec 2024, Jan 2025, Dec 2025 (to 0.75%) caused rapid spread compression
- **RISK-OFF**: VIX >30 = carry reversal across entire G10

### Pseudocode
```python
def check_carry_pullback_long():
    # Macro gate
    fed_rate = get_fed_funds_rate()  # e.g. 3.875%
    boj_rate = get_boj_policy_rate()  # e.g. 0.75%
    spread = fed_rate - boj_rate
    spread_3m_ago = get_spread_historical(-90)
    widening = spread >= spread_3m_ago
    
    if spread <= 2.5 or not widening:
        return None
    
    # Daily trend
    if not (Daily.Close > Daily.EMA50 and Daily.EMA50 > Daily.EMA200):
        return None
    
    # Identify last impulse leg
    impulse = detect_last_daily_impulse_leg()
    fib_382 = impulse.high - 0.382 * impulse.range
    fib_618 = impulse.high - 0.618 * impulse.range
    
    # H4 pullback check
    if not (fib_618 <= H4.Low <= fib_382):
        return None
    
    # Candle trigger
    if not (is_bullish_engulfing(H4) or is_pin_bar(H4, bullish=True)):
        return None
    
    # RSI confirmation
    if not (40 <= H4.RSI14 <= 55):
        return None
    
    # Execute
    entry = H4.Close
    sl = pullback_swing_low - 0.5 * ATR
    tp1 = impulse.high
    tp2 = impulse.high + 0.272 * impulse.range
    return {"side": "long", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 80–120 trades over 5 years |
| Profit factor | 1.6–2.2 |
| Max drawdown | 10–15% |
| Sharpe ratio | 1.2–1.6 |
| Best year type | Rate-hike cycles (2022–2024) |
| Worst year type | Carry-unwind years (2008, 2024-Aug) |

### Dashboard Signals to Surface
- Live Fed-BoJ spread with 3-month trend arrow
- JPY COT positioning percentile (extremes highlighted)
- Daily impulse leg auto-detected with Fib levels
- H4 pullback status (which Fib zone price is in)
- Intervention-zone warning (price > 155)

---

## Strategy 4: US 10Y Yield Correlation Bias

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 4 |
| **Category** | Correlation / Hybrid |
| **Timeframes** | Daily bias; H4 entry |
| **Session Filter** | NY session (bond market open) preferred |
| **Win Rate** | 55–65% (estimated from correlation structure) |
| **Risk:Reward** | 1:2 to 1:4 |
| **Trades/Day** | 0 |
| **Trades/Week** | 0.5–1.5 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
USDJPY has the single highest correlation to US 10Y yields among major currency pairs (+0.70 to +0.95 historically, peaked at +0.93 in 2022–2024). Trading USDJPY in the direction of US 10Y breakouts is effectively trading the cleanest yield-FX relationship in global markets. No other major pair offers this level of macro-technical alignment.

### Macro Bias Inputs
- 30-day rolling correlation coefficient between USDJPY and US 10Y yield (must be ≥ +0.70)
- US 10Y breakout direction drives trade bias
- Fed funds futures and 10Y Treasury auction results can precipitate signals
- JGB 10Y yield trend (post-YCC policy) modifies intensity

### Indicators Required
- US 10Y Treasury yield (TNX or ^TNX data feed)
- 30-day rolling correlation of USDJPY vs US 10Y
- 10-day high/low of US 10Y yield (breakout detection)
- EMA(20) on H4 for pullback entry

### Long Entry Rules
1. **Gate 1**: 30-day correlation between USDJPY and US 10Y ≥ +0.70
2. **Gate 2**: US 10Y yield closes above its 10-day high on Daily
3. **Gate 3**: Daily USDJPY close > EMA20
4. **Entry trigger**: H4 pullback to EMA20 + bullish rejection candle
5. **Time filter**: Entry during NY session (13:00–20:00 GMT) when Treasury market active

### Short Entry Rules
1. US 10Y yield closes below 10-day low
2. Correlation still ≥ +0.70
3. Daily USDJPY close < EMA20
4. H4 bearish rejection at EMA20 during NY hours

### Stop Loss
- Beyond H4 swing low (long) or high (short)
- Minimum: 1.5 × ATR(H4)

### Take Profit
- **TP1**: 2R (close 50%)
- **TP2**: Next major structure level (prior swing high)
- **Trail**: H4 EMA50

### Position Sizing
- 0.75% per trade (high-conviction macro alignment)

### Exit Rules
- US 10Y reverses and closes back inside 10-day range = exit 50%
- 30-day correlation drops below +0.50 = exit fully
- Unexpected bond-market event (auction fail, Fed communication) = exit immediately
- Before FOMC: flat position

### Filters
- No entries during FOMC week or major Treasury auction days unless aligned
- Skip if correlation is inverting (30-day trend turning negative)
- Avoid during Japanese holidays when JGB market is closed

### Known Risks
- Correlation can break temporarily during BoJ intervention
- Risk-off flight-to-quality can push yields DOWN and USDJPY DOWN simultaneously (correlation spike)
- Short end of curve (2Y) sometimes diverges from 10Y during Fed repricings
- Lag between US 10Y move and USDJPY response (10–60 minutes typical)

### Pseudocode
```python
def check_10y_correlation_long():
    # Daily-level macro gates
    us10y = get_us_10y_yield()
    correl_30d = rolling_correlation(usdjpy_daily, us10y_daily, 30)
    us10y_10d_high = max(us10y.history[-10:])
    
    if correl_30d < 0.70:
        return None
    if us10y.Close <= us10y_10d_high:
        return None
    if USDJPY.Daily.Close <= Daily.EMA20:
        return None
    
    # Wait for NY session
    if not (13 <= current_hour_gmt < 20):
        return None
    
    # H4 trigger
    if H4.Low <= H4.EMA20 and is_bullish_rejection(H4):
        entry = H4.Close
        sl = H4.SwingLow - 0.5 * ATR
        tp1 = entry + 2 * (entry - sl)
        tp2 = get_nearest_prior_swing_high(entry)
        return {"side": "long", "entry": entry, "sl": sl, "tp1": tp1, "tp2": tp2}
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 60–100 trades over 3 years |
| Profit factor | 1.8–2.4 |
| Max drawdown | 8–14% |
| Sharpe ratio | 1.3–1.7 (highest among listed strategies) |
| Data dependency | Clean US 10Y feed with sync timestamps |

### Dashboard Signals to Surface
- Live US 10Y yield with 10-day range markers
- Rolling 30-day correlation (USDJPY vs US 10Y) with threshold line
- Correlation trend (improving/stable/deteriorating)
- Next Treasury auction date
- H4 EMA20 distance for pullback monitoring

---

## Strategy 5: Confluence System (Trend + S/R + Candle + RSI Divergence)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 5 |
| **Category** | Multi-Signal Confluence |
| **Timeframes** | Daily bias, H4 entry |
| **Session Filter** | London + NY |
| **Win Rate** | 55–65% |
| **Risk:Reward** | 1:2 to 1:3 |
| **Trades/Day** | 0 |
| **Trades/Week** | 1–2 |
| **Algo Fit** | MEDIUM (tuning/overfit risk) |

### Edge (Why It Works on USDJPY)
USDJPY respects psychological round numbers (145, 150, 152, 155, 160) exceptionally well due to MoF intervention zones and option-strike clustering at these levels. Stacking multiple independent signals (trend, level, candle, divergence) at these zones produces high-probability setups with genuine order-flow justification.

### Macro Bias Inputs
- Daily trend regime (EMA50 vs EMA200)
- Intervention zones: MoF has intervened at 145–146 (Sep 2022), 152 (Oct 2022), 160 (Apr–May 2024)
- Verbal intervention watch: Kanda/Mimura statements trigger caution

### Indicators Required
- EMA(50), EMA(200) on Daily (trend)
- Horizontal S/R levels drawn at 0.5 and whole numbers, plus algorithmically detected swing highs/lows
- Candlestick pattern detection (engulfing, pin bar, doji at level)
- RSI(14) on H4 (for divergence detection)

### Long Entry Rules (Score-Based)
Require AT LEAST 3 of 4 conditions:
- **(a) Trend**: Daily trend bullish (Close > EMA50 > EMA200)
- **(b) Level**: Price at significant horizontal level (round number or prior swing)
- **(c) Candle**: Bullish engulfing or bullish pin bar on H4
- **(d) Divergence**: Bullish RSI divergence on H4 (price lower low, RSI higher low)

**Entry**: Break of trigger candle high with volume confirmation

### Short Entry Rules
Mirror: at least 3 of (Daily bearish, price at resistance level, bearish reversal candle, bearish RSI divergence).
**Short setups especially valuable near intervention zones (155+)**.

### Stop Loss
- Beyond the key level + 1 × ATR(H4) buffer

### Take Profit
- **TP1**: Next major S/R level (typically 2R)
- **TP2**: 3R
- Close remainder at end of NY session

### Position Sizing
- 0.75% if 3 conditions met
- 1.0% if all 4 met

### Exit Rules
- Daily close beyond invalidation level = exit
- Loss of confluence (price breaks through level decisively) = exit
- Exit at end of NY session if not at TP1 (no overnight if underwater)

### Filters
- Require ATR(H4) ≥ 30 pips (skip dead markets)
- Avoid during Japanese holidays
- Skip if price has whipsawed the level 3+ times in prior 10 bars

### Known Risks
- **OVERFITTING**: Adjusting confluence conditions after-the-fact inflates backtest win rate
- Subjective S/R drawing — needs algorithmic pivot detection for automation
- At intervention zones (above 155), stops can be gapped through
- Confluence can decompose in strong one-directional news moves

### Pseudocode
```python
def check_confluence_long():
    score = 0
    reasons = []
    
    # Condition (a) - Trend
    if Daily.Close > Daily.EMA50 > Daily.EMA200:
        score += 1
        reasons.append("Daily uptrend")
    
    # Condition (b) - Level
    nearest_level = find_nearest_horizontal_level(current_price)
    if abs(H4.Low - nearest_level) < 0.3 * ATR:
        score += 1
        reasons.append(f"At level {nearest_level}")
    
    # Condition (c) - Candle
    if is_bullish_engulfing(H4) or is_bullish_pin(H4):
        score += 1
        reasons.append("Bullish reversal candle")
    
    # Condition (d) - Divergence
    if has_bullish_rsi_divergence(H4, lookback=20):
        score += 1
        reasons.append("Bullish RSI divergence")
    
    if score >= 3:
        entry_trigger = trigger_candle.high + 2  # pips buffer
        sl = min(nearest_level, trigger_candle.low) - ATR
        tp1 = next_resistance_level_above(entry_trigger)  # must be >= 2R
        tp2 = tp1 + (entry_trigger - sl)
        position_size_pct = 0.75 if score == 3 else 1.0
        return {
            "side": "long",
            "entry": entry_trigger,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "score": score,
            "reasons": reasons,
            "size_pct": position_size_pct
        }
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 100–150 trades over 4 years |
| Profit factor | 1.5–2.0 |
| Max drawdown | 12–17% |
| Out-of-sample validation | Critical — use last 20% of data |
| Walk-forward optimization | Required given multi-parameter nature |

### Dashboard Signals to Surface
- Live confluence score (0–4) for both long and short setups
- Detected horizontal levels with age and test count
- Current H4 candle pattern (if any)
- RSI divergence status (live detection)
- Intervention-zone warning if price > 155

---
## Strategy 6: MACD + 200 EMA Trend-Following

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 6 |
| **Category** | Trend Following |
| **Timeframes** | H1 primary, H4 variant |
| **Session Filter** | London + NY overlap preferred |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 1:1 to 1:2 |
| **Trades/Day** | 0–1 |
| **Trades/Week** | 2–5 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Simple, robust combination. The 200 EMA acts as a regime filter (captures yield-differential trend), while MACD provides cleaner momentum entries than a naked price cross. Well-studied with documented 60%+ win rate on 2:1 R:R from independent backtests on similar pairs.

### Macro Bias Inputs (Optional)
- Fed-BoJ spread direction to set daily bias
- DXY (US Dollar Index) trend as secondary confirmation for longs

### Indicators Required
- EMA(200) on entry timeframe
- MACD(12, 26, 9)
- ATR(14) for stops
- Optional: RSI(14) to filter extreme entries

### Long Entry Rules
1. **Condition 1**: Price > EMA200 (regime filter — bullish)
2. **Condition 2**: MACD line crosses ABOVE signal line
3. **Condition 3**: Cross occurs BELOW the zero line (pullback within uptrend = best setup)
4. **Entry**: Market order at close of cross candle OR stop order at candle high

### Short Entry Rules
1. Price < EMA200
2. MACD line crosses BELOW signal line
3. Cross ABOVE zero line (best short setup — retrace within downtrend)
4. Entry at cross candle close or at candle low

### Stop Loss
- Swing low (long) or swing high (short) within last 5 bars
- Minimum: 1 × ATR

### Take Profit
- TP at 1.5× or 2× SL distance
- Classic exit: MACD opposite cross

### Position Sizing
- 0.5% per trade

### Exit Rules
- MACD opposite cross = exit
- Price closes on opposite side of EMA200 = exit
- TP hit = exit

### Filters
- ADX(14) > 20 to confirm trending regime (optional but improves edge)
- Skip MACD crosses far from zero line (stale trends)
- Avoid first 15 minutes after major economic releases

### Known Risks
- Whipsaw losses in ranging markets (Tokyo session chop common)
- MACD is lagging — signal can arrive after bulk of move completed
- EMA200 on H1 has ~8-day memory; sharp regime changes produce multiple losses

### Pseudocode
```python
def check_macd_ema200_signal():
    # Long setup
    if close > EMA200:
        if crossover(MACD_line, MACD_signal) and MACD_line < 0:
            entry = close
            recent_low = min(low[-5:])
            sl = recent_low - 0.2 * ATR
            tp = entry + 2 * (entry - sl)
            return {"side": "long", "entry": entry, "sl": sl, "tp": tp}
    
    # Short setup
    elif close < EMA200:
        if crossunder(MACD_line, MACD_signal) and MACD_line > 0:
            entry = close
            recent_high = max(high[-5:])
            sl = recent_high + 0.2 * ATR
            tp = entry - 2 * (sl - entry)
            return {"side": "short", "entry": entry, "sl": sl, "tp": tp}
    
    return None

# Exit trigger: opposite MACD cross regardless of TP/SL
def check_exit(position):
    if position.side == "long" and crossunder(MACD_line, MACD_signal):
        return "CLOSE"
    if position.side == "short" and crossover(MACD_line, MACD_signal):
        return "CLOSE"
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥200 trades over 2 years on H1 |
| Profit factor | 1.3–1.7 |
| Max drawdown | 15–20% |
| Reference | Trading Rush 60% on H1 EUR/USD (USDJPY similar) |
| Max consecutive losses | Track 4–6 in a row |

### Dashboard Signals to Surface
- MACD histogram with zero-line reference
- EMA200 distance (price premium/discount)
- Setup proximity score (how close to a valid signal)
- Current MACD state (bullish/bearish/crossing)

---

## Strategy 7: ADX + DMI Trend-Strength Filter

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 7 |
| **Category** | Trend Filter + Entry |
| **Timeframes** | H4 |
| **Session Filter** | Any (strategy is time-agnostic) |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 1:1.5 to 1:2 |
| **Trades/Day** | 0–1 |
| **Trades/Week** | 0–4 (regime dependent) |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
ADX objectively classifies USDJPY market regime (trending vs ranging). Filters out Tokyo-session chop that destroys non-filtered systems. Adds approximately 10–15 percentage points to win rate of underlying trend methods.

### Macro Bias Inputs (Optional)
- Align with Daily trend direction
- Fed-BoJ spread trend for directional bias

### Indicators Required
- ADX(14)
- +DI(14) and -DI(14)
- EMA(20) for pullback reference
- ATR(14) for stops

### Long Entry Rules
1. **Condition 1**: ADX(14) > 25 (strong trend present)
2. **Condition 2**: +DI > -DI (bullish directional movement)
3. **Condition 3**: Pullback to EMA20 or recent swing low
4. **Condition 4**: Bullish close after pullback
5. **Entry**: Close of confirmation bar

### Short Entry Rules
1. ADX > 25
2. -DI > +DI
3. Pullback to EMA20
4. Bearish close at pullback

### Stop Loss
- 1.5 × ATR(14) from entry

### Take Profit
- 2 × ATR(14) target
- OR exit when ADX drops below 20

### Position Sizing
- 0.5–0.75% per trade

### Exit Rules
- ADX < 20 = trend weakening, exit remaining position
- +DI and -DI cross = regime change, exit
- Hard TP at 2 × ATR

### Filters
- ADX > 25 threshold is critical — do NOT trade at 20–25 (ambiguous zone)
- Require DI spread > 5 points for conviction
- Skip when ADX is falling even if still > 25 (weakening trend)

### Known Risks
- ADX is lagging — confirms strength AFTER move has started
- Whipsaw risk when DI lines cross repeatedly near threshold
- Can miss fast, clean trends that never reach ADX 25 (acceleration moves)

### Pseudocode
```python
def check_adx_dmi_signal():
    if ADX14 < 25:
        return None
    
    di_spread = abs(plusDI - minusDI)
    if di_spread < 5:
        return None
    
    # Long setup
    if plusDI > minusDI:
        if pulled_back_to_EMA20() and is_bullish_close():
            entry = close
            sl = entry - 1.5 * ATR
            tp = entry + 2 * ATR
            return {
                "side": "long",
                "entry": entry,
                "sl": sl,
                "tp": tp,
                "exit_condition": "ADX < 20 or bearish DI cross"
            }
    
    # Short setup
    elif minusDI > plusDI:
        if rallied_to_EMA20() and is_bearish_close():
            entry = close
            sl = entry + 1.5 * ATR
            tp = entry - 2 * ATR
            return {"side": "short", "entry": entry, "sl": sl, "tp": tp}
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 100–150 trades over 4 years |
| Profit factor | 1.4–1.8 |
| Max drawdown | 12–16% |
| Frequency variance | Trade count varies 10x by year (trendy vs choppy) |

### Dashboard Signals to Surface
- Live ADX value with 20/25 threshold lines
- +DI / -DI with spread
- Regime classification (trending/ranging/transitional)
- Pullback proximity to EMA20

---

## Strategy 8: Tokyo Range Breakout ("Big Ben" Adapted)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 8 |
| **Category** | Session Breakout |
| **Timeframes** | M30 / H1 |
| **Session Filter** | Tokyo range (00:00–07:00 GMT), London trigger (07:00–10:00 GMT) |
| **Win Rate** | 40–50% |
| **Risk:Reward** | 1.5:1 to 2:1 |
| **Trades/Day** | 1 (max 1 setup per day) |
| **Trades/Week** | 3–4 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Unlike EURUSD where Asian session is a non-event, USDJPY has a genuinely active Tokyo session with Japanese institutional flows building real range structure. London open reliably breaks this range in approximately 70% of days, providing a clean binary setup.

### Macro Bias Inputs (Optional)
- Daily trend direction can bias which side of breakout to prefer
- Overnight US equity futures direction is a leading hint
- Japanese economic releases during Tokyo (machinery orders, Tankan) can pre-break the range

### Indicators Required
- High and Low of defined Tokyo session (00:00–07:00 GMT)
- ATR(14) on H4 (for range quality check)
- Simple moving average of session ranges for normalization

### Long Entry Rules
1. Mark Tokyo session high (TH) and low (TL) at 07:00 GMT
2. Place BUY STOP at TH + 5 pips AND SELL STOP at TL - 5 pips (OCO — one cancels other)
3. Cancel any unfilled order at 10:00 GMT if no break occurred
4. If BUY STOP triggers: long is live

### Short Entry Rules
- Mirror of long logic (sell stop at TL - 5 pips)

### Stop Loss
- Opposite side of Tokyo range
- If long at TH + 5: SL = TL - 5

### Take Profit
- TP1 = 1 × range width (typically 1R)
- TP2 = 1.5–2 × range width

### Position Sizing
- 0.5% per trade
- Range width determines exact pip SL

### Exit Rules
- If not at TP1 within 4 H1 bars after entry: close at market
- Hard close by 16:00 GMT (before NY close)
- Opposite breakout re-test: if trigger was long and price breaks back through midrange, exit

### Filters
- Range width between 0.5 × ATR(H4) and 1.5 × ATR(H4)
- Skip if range < 25 pips (false breakouts dominate)
- Skip on major NFP/FOMC days (London opens often fade the breakout)
- Avoid Golden Week, Obon, Japanese New Year (broken range structure)

### Known Risks
- False breakouts during London open — common (5-pip buffer helps but doesn't eliminate)
- News-driven gaps that jump past SL
- Japanese holidays compress range artificially
- Failed breakout fades (price returns inside range) can stop out fast

### Pseudocode
```python
def tokyo_range_breakout():
    # At 07:00 GMT
    if current_time != "07:00 GMT":
        return None
    
    tokyo_bars = get_h1_bars(start="00:00 GMT", end="07:00 GMT")
    tokyo_high = max(bar.high for bar in tokyo_bars)
    tokyo_low = min(bar.low for bar in tokyo_bars)
    range_width = tokyo_high - tokyo_low
    
    # Quality filters
    atr_h4 = H4.ATR14
    if range_width < 25:
        return None
    if range_width > 1.5 * atr_h4:
        return None
    if is_major_news_day():
        return None
    if is_japanese_holiday():
        return None
    
    # Place OCO orders
    buy_entry = tokyo_high + 5  # pips
    sell_entry = tokyo_low - 5
    
    orders = [
        {
            "type": "BUY_STOP",
            "entry": buy_entry,
            "sl": tokyo_low - 5,
            "tp1": buy_entry + range_width,
            "tp2": buy_entry + 1.5 * range_width,
            "expire": "10:00 GMT"
        },
        {
            "type": "SELL_STOP",
            "entry": sell_entry,
            "sl": tokyo_high + 5,
            "tp1": sell_entry - range_width,
            "tp2": sell_entry - 1.5 * range_width,
            "expire": "10:00 GMT"
        }
    ]
    return {"orders": orders, "oco": True}

# Post-entry monitoring
def monitor_position(position):
    hours_in_trade = get_hours_since_entry()
    if hours_in_trade >= 4 and position.pnl < position.tp1_distance:
        return "CLOSE_AT_MARKET"
    if current_time_gmt >= "16:00":
        return "HARD_CLOSE"
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥500 trades over 2 years (daily setup) |
| Profit factor | 1.3–1.6 |
| Max drawdown | 10–15% |
| DST sensitivity | Build calendar-aware session logic |

### Dashboard Signals to Surface
- Live Tokyo range as it develops (current high/low)
- Range width vs ATR comparison
- Range quality score
- Time-to-breakout-window countdown
- OCO order preview

---

## Strategy 9: Keltner Channel Breakout ("King Keltner")

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 9 |
| **Category** | Trend / Volatility Breakout |
| **Timeframes** | H1 / H4 |
| **Session Filter** | London + NY |
| **Win Rate** | 40–50% |
| **Risk:Reward** | 1.5:1 to 2:1 |
| **Trades/Day** | 0–1 |
| **Trades/Week** | 2–4 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
ATR-based bands dynamically adapt to USDJPY's changing volatility regimes around BoJ events and intervention phases. A break of the upper band plus a pullback to the midline (EMA20) creates a trend-continuation setup that works well on this pair's carry-trade driven trends.

### Macro Bias Inputs (Optional)
- Align breakout direction with Daily trend
- Avoid new breakouts during expected BoJ intervention windows

### Indicators Required
- Keltner Channel:
  - **Midline**: EMA(20)
  - **Upper/Lower**: Midline ± 2 × ATR(20)
- ATR(20) base
- Volume or tick volume for confirmation (where available)

### Long Entry Rules
1. **Step 1**: Close above the upper Keltner band (signals impulse move)
2. **Step 2**: Wait for pullback — price returns to within 0.2 × ATR of the EMA20 midline without closing below
3. **Step 3**: Bullish confirmation candle (close > open, close > EMA20)
4. **Entry**: Break of confirmation candle high

### Short Entry Rules
1. Close below lower Keltner band
2. Pullback to EMA20 midline
3. Bearish confirmation candle
4. Entry on break of its low

### Stop Loss
- Below the midline swing (longs)
- Typically 1.5–2 × ATR

### Take Profit
- TP at opposite band OR at 2 × risk
- Trail stop: exit when close crosses back through EMA20

### Position Sizing
- 0.5–0.75% per trade

### Exit Rules
- Close through EMA20 in opposite direction = exit
- Price touches lower band (for longs) = exit (full reversal signal)
- Time stop: 20 H1 bars / 10 H4 bars

### Filters
- ATR not expanding too aggressively (avoid late-stage vol spikes)
- Skip breakouts within 1 hour of major news releases
- Require prior 10 bars to show trend structure (not post-range breakout)

### Known Risks
- Whipsaw if volatility regime is changing mid-trade (bands widen, stop gets hit)
- Pullback to midline may not happen — missing the move
- BoJ intervention can invalidate the band structure instantly

### Pseudocode
```python
def keltner_breakout_signal():
    midline = EMA20(close)
    upper = midline + 2 * ATR20
    lower = midline - 2 * ATR20
    
    # State machine
    # States: 'waiting' -> 'broke_out' -> 'pulled_back' -> 'confirmed'
    
    if state == 'waiting':
        if close > upper:
            state = 'broke_out'
            breakout_direction = 'long'
            breakout_high = high
        elif close < lower:
            state = 'broke_out'
            breakout_direction = 'short'
            breakout_low = low
    
    elif state == 'broke_out':
        if breakout_direction == 'long':
            if abs(low - midline) < 0.2 * ATR:
                state = 'pulled_back'
        elif breakout_direction == 'short':
            if abs(high - midline) < 0.2 * ATR:
                state = 'pulled_back'
    
    elif state == 'pulled_back':
        if breakout_direction == 'long' and is_bullish_confirm(bar) and close > midline:
            entry_trigger = bar.high
            entry = entry_trigger  # stop order at break
            sl = midline - 1.5 * ATR
            tp = entry + 2 * (entry - sl)
            state = 'waiting'
            return {"side": "long", "entry": entry, "sl": sl, "tp": tp}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥150 trades over 3 years |
| Profit factor | 1.4–1.7 |
| Max drawdown | 14–18% |
| Reference | Quantified Strategies documented 77% on SPY variants |

### Dashboard Signals to Surface
- Keltner bands with current midline distance
- Breakout state (waiting/broke-out/pulling-back/confirmed)
- ATR regime (expanding/stable/contracting)
- Distance to midline in ATR units

---

## Strategy 10: 50/200 EMA Crossover Pullback

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 10 |
| **Category** | Trend Following (long-only swing bias) |
| **Timeframes** | H4 primary; Daily for macro |
| **Session Filter** | Any (signal-agnostic) |
| **Win Rate** | 35–45% |
| **Risk:Reward** | 1:1.5 to 1:3 |
| **Trades/Day** | 0 |
| **Trades/Week** | 0.5–2 |
| **Algo Fit** | VERY HIGH |

### Edge (Why It Works on USDJPY)
Low win rate but captures the largest USDJPY moves. The 2022–2024 carry-trade uptrend (from ~113 to 162) was effectively one position for this system. Golden/death cross has a very low signal rate but when right, catches entire regime shifts. Simple, pure-math rules = ideal for algo.

### Macro Bias Inputs
- Fed-BoJ spread direction (structural)
- DXY trend
- Global risk-on/risk-off regime

### Indicators Required
- EMA(50), EMA(200) on H4
- ATR(14) for stops
- Simple swing high/low detection

### Long Entry Rules
1. **Trigger**: EMA50 crosses ABOVE EMA200 ("Golden Cross")
2. **Wait mode**: Do NOT enter on cross; wait for first pullback
3. **Entry**: Price retraces to swing low AND bullish reversal candle forms
4. **Alternate entry**: Pullback to EMA50 + bullish bar close

### Short Entry Rules
1. Death cross (EMA50 crosses below EMA200)
2. Pullback to swing high or EMA50
3. Bearish reversal

### Stop Loss
- Below pullback swing low (longs)
- Give it room: 2–3 × ATR

### Take Profit
- TP1 at 1.5R (close 40%)
- Trail remainder at EMA50 — exit on H4 close below

### Position Sizing
- 0.5% per trade
- Low frequency justifies this size

### Exit Rules
- Opposite cross (EMA50 back below EMA200) = exit
- H4 close below EMA50 by more than 1 × ATR = partial exit
- No hard time stop — strategy is position-based

### Filters
- Require EMA50-EMA200 separation to widen post-cross (not immediately re-converging)
- Skip if cross occurs in flat market (ADX < 18)
- Best performance: 6-month or longer regime holds

### Known Risks
- Most signals are false — only 35–45% win rate
- Drawdowns can be long before a winner arrives
- Pattern failure in range-bound regimes (months of whipsaws)
- Latest cross in Dec 2025 — with BoJ hiking, regime is uncertain

### Pseudocode
```python
# State: 'no_signal' | 'waiting_pullback' | 'in_trade'

def check_ema_crossover(state):
    if state == 'no_signal':
        if crossover(EMA50, EMA200):
            return {
                "new_state": "waiting_pullback",
                "cross_bar_index": current_bar_index,
                "direction": "long"
            }
        elif crossunder(EMA50, EMA200):
            return {
                "new_state": "waiting_pullback",
                "cross_bar_index": current_bar_index,
                "direction": "short"
            }
    
    elif state == 'waiting_pullback':
        bars_since_cross = current_bar_index - cross_bar_index
        if bars_since_cross > 20:
            return {"new_state": "no_signal"}  # expired
        
        if is_pullback_to_EMA50_or_swing_low() and is_bullish_reversal():
            entry = close
            sl = pullback_low - ATR
            risk = entry - sl
            tp1 = entry + 1.5 * risk
            return {
                "new_state": "in_trade",
                "side": "long",
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "trail_anchor": "EMA50"
            }
    
    elif state == 'in_trade':
        if close < EMA50 and (EMA50 - close) > ATR:
            return {"action": "PARTIAL_EXIT", "pct": 60}
        if crossunder(EMA50, EMA200):
            return {"action": "FULL_EXIT"}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 30–50 trades over 5 years (LOW frequency) |
| Profit factor | 1.4–2.0 (driven by 1-2 huge winners per year) |
| Max drawdown | 18–25% (long losing streaks possible) |
| Backtest window | Minimum 10 years required |
| Use case | Best complement to higher-frequency MR systems |

### Dashboard Signals to Surface
- EMA50/EMA200 distance and trend
- Time since last cross
- Current state (no signal / waiting pullback / in trade)
- Pullback proximity to swing low or EMA50

---
## Strategy 11: Asian Session Range Fade

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 11 |
| **Category** | Mean Reversion |
| **Timeframes** | M30 |
| **Session Filter** | Late Asian / early Tokyo (00:00–06:30 GMT only) |
| **Win Rate** | 60–70% (in ranging regimes) |
| **Risk:Reward** | 0.5:1 to 0.8:1 |
| **Trades/Day** | 1–2 |
| **Trades/Week** | 4–6 |
| **Algo Fit** | MEDIUM-HIGH |

### Edge (Why It Works on USDJPY)
BoJ fix (09:55 JST = 00:55 GMT) and Japanese institutional flows defend psychological levels. The Tokyo range often compresses and oscillates, giving mean-reversion a high hit-rate edge. **Critical**: only works in non-trending regimes — regime filter is mandatory.

### Macro Bias Inputs
- Regime check: NOT during strong trend days
- JPY fixings (9:55 JST) can create mean-reverting flows

### Indicators Required
- Prior day H/L (Tokyo range reference)
- RSI(14) on M30 (for extreme identification)
- ADX(14) on H1 (regime filter — must be low)

### Long Entry Rules
1. **Regime gate**: ADX(H1) < 20 (confirmed ranging)
2. **Tokyo range defined**: Top and bottom from first 2 hours (00:00–02:00 GMT)
3. **Long setup**: Price touches range LOW with RSI(M30) < 30
4. **Wait for bullish reversal candle** (engulfing/pin) at range low
5. **Entry**: Break of reversal candle high

### Short Entry Rules
- Mirror: price at range high with RSI > 70 and bearish reversal

### Stop Loss
- Beyond range extreme by 8–12 pips

### Take Profit
- Midpoint of range (1R typical)
- Aggressive: opposite range extreme

### Position Sizing
- 0.5% per trade (tight stops allow reasonable size)

### Exit Rules
- Hard exit at 06:30 GMT (before London open)
- Range break (price closes beyond original range) = immediate exit
- TP at midrange achieves ~0.8R on average

### Filters
- Range width must be 20–60 pips (too narrow = no edge, too wide = trending)
- Skip if overnight US session had >1% move in equities (trend carry-over)
- Avoid Japanese holidays
- Skip days with Japanese data releases in Tokyo hours

### Known Risks
- Catastrophic if regime shifts mid-trade (trend day)
- Tight R:R means one big loss erases several wins
- False signals near the BoJ fix if large flows dominate
- Low trade count per week means slow statistical convergence

### Pseudocode
```python
def asian_range_fade():
    # Define range at 02:00 GMT
    if current_time_gmt == "02:00":
        range_bars = get_h1_bars(start="00:00", end="02:00")
        range_high = max(bar.high for bar in range_bars)
        range_low = min(bar.low for bar in range_bars)
        range_width = range_high - range_low
        
        # Validation
        if not (20 <= range_width <= 60):
            return {"valid": False, "reason": "range size"}
        if H1.ADX14 >= 20:
            return {"valid": False, "reason": "trending regime"}
        if had_overnight_equity_move():
            return {"valid": False, "reason": "overnight news"}
        
        store_range(range_high, range_low)
    
    # Monitor M30 bars 02:00–06:30
    if "02:00" < current_time_gmt < "06:30":
        # Long setup
        if M30.Low <= range_low and M30.RSI14 < 30:
            if is_bullish_reversal(M30):
                entry = M30.High  # break of high
                sl = range_low - 10
                tp = (range_high + range_low) / 2  # midrange
                return {"side": "long", "entry": entry, "sl": sl, "tp": tp}
        
        # Short setup
        if M30.High >= range_high and M30.RSI14 > 70:
            if is_bearish_reversal(M30):
                entry = M30.Low
                sl = range_high + 10
                tp = (range_high + range_low) / 2
                return {"side": "short", "entry": entry, "sl": sl, "tp": tp}
    
    # Hard exit at 06:30 GMT
    if current_time_gmt >= "06:30":
        return {"action": "FORCE_CLOSE"}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥300 trades over 3 years |
| Profit factor | 1.2–1.5 (modest due to tight R:R) |
| Max drawdown | 10–14% (ranging regimes), >20% (trend regimes) |
| Regime accuracy | Track separately from overall P&L |
| Pairing | Combine with trend system for coverage |

### Dashboard Signals to Surface
- Live Tokyo range (high/low with width)
- ADX H1 value vs threshold
- M30 RSI for both range extremes
- Time-to-hard-exit countdown
- Range-break warning if approached

---

## Strategy 12: Donchian/Turtle Breakout (System 1)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 12 |
| **Category** | Trend Breakout |
| **Timeframes** | Daily (classical); H4 adaptation |
| **Session Filter** | Any (position-based) |
| **Win Rate** | 35–45% |
| **Risk:Reward** | 1:2 to 1:4 |
| **Trades/Day** | 0 |
| **Trades/Week** | 0.25–0.75 (Daily); 1–3 (H4) |
| **Algo Fit** | VERY HIGH |

### Edge (Why It Works on USDJPY)
Designed by Richard Dennis/William Eckhardt explicitly for currencies and commodities. Captured both the 145→152 (2023) and 152→160 (2024) USDJPY breakouts. The simplicity makes it a benchmark for systematic trend-following.

### Macro Bias Inputs (Optional)
- Not required — system is purely mechanical
- Optional: align with Fed-BoJ spread direction to reduce false signals

### Indicators Required
- Donchian Channel: 20-bar high and low
- Exit Donchian: 10-bar low (longs) / high (shorts)
- ATR(20) for position sizing (called "N" in Turtle parlance)

### Long Entry Rules
1. Break above 20-bar high (Daily or H4)
2. **Original Turtle rule**: SKIP the trade if the previous 20-bar breakout in the same direction WON (filter reduces false signals after strong trends)
3. Otherwise: enter on confirmed break

### Short Entry Rules
- Break below 20-bar low
- Same skip-if-prior-won rule

### Stop Loss
- 2 × ATR (called "2N" in Turtle parlance)

### Take Profit
- No fixed TP — exit on 10-bar low (for longs) / 10-bar high (for shorts)
- Trail indefinitely

### Position Sizing
- Risk-based: Position = (1% × equity) / (2 × ATR × pip_value)

### Exit Rules
- **Trail-stop exit**: Close long on break of 10-bar low
- **Close short** on break of 10-bar high
- **Pyramid** (optional advanced): Add unit every 0.5N favorable move, up to 4 units

### Filters
- Skip rule (if previous signal won) is essential — removes ~40% of false breakouts
- Optional: require trend filter (price > 100-day SMA for longs)
- Skip in extremely compressed ATR environments (no vol to expand from)

### Known Risks
- Long losing streaks (can be 10+ in a row in ranging markets)
- Psychological difficulty: most signals are false, requires patience
- Overnight/weekend gap risk on Daily version
- Intervention-zone breakouts (above 155) have special reversal risk

### Pseudocode
```python
class TurtleSystem:
    def __init__(self):
        self.previous_long_won = False
        self.previous_short_won = False
    
    def check_signal(self):
        donchian_high_20 = max(high[-20:])
        donchian_low_20 = min(low[-20:])
        donchian_low_10 = min(low[-10:])
        donchian_high_10 = max(high[-10:])
        atr = ATR(20)
        
        # Long entry
        if close > donchian_high_20 and not self.previous_long_won:
            entry = close
            sl = entry - 2 * atr
            trail = donchian_low_10  # updates daily
            return {
                "side": "long",
                "entry": entry,
                "sl": sl,
                "trail_trigger": trail
            }
        
        # Short entry
        if close < donchian_low_20 and not self.previous_short_won:
            entry = close
            sl = entry + 2 * atr
            trail = donchian_high_10
            return {
                "side": "short",
                "entry": entry,
                "sl": sl,
                "trail_trigger": trail
            }
        
        return None
    
    def check_exit(self, position):
        if position.side == "long":
            if close < current_donchian_low_10:
                return "EXIT"
        elif position.side == "short":
            if close > current_donchian_high_10:
                return "EXIT"
    
    def position_size(self, equity, atr, pip_value):
        return (0.01 * equity) / (2 * atr * pip_value)
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 40–80 trades over 10+ years |
| Profit factor | 1.4–1.9 (1–2 massive winners carry the year) |
| Max drawdown | 20–30% (largest among listed strategies) |
| Backtest window | Minimum 10 years essential |
| Sharpe | 0.6–1.0 (noisy equity curve) |

### Dashboard Signals to Surface
- Donchian channels (20-bar + 10-bar)
- Distance to breakout level (in pips and %)
- ATR (N) for position sizing preview
- Previous signal outcome (for skip rule)
- Active trail-stop level

---

## Strategy 13: London Open Breakout (Trend-Filtered)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 13 |
| **Category** | Session Breakout |
| **Timeframes** | M30 / H1 |
| **Session Filter** | Pre-London range 05:00–07:00 GMT; breakout trades 07:00–12:00 GMT |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 2:1 |
| **Trades/Day** | 1 |
| **Trades/Week** | ~3 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
European bond markets open coincident with London, driving USDJPY through the yield-correlation channel. The pre-London consolidation range provides a clean reference for the opening burst, and trend alignment filters the common false breakouts.

### Macro Bias Inputs
- H1 trend direction (EMA20/50 alignment) must agree with breakout side
- Optional: DXY pre-London trend

### Indicators Required
- Pre-London range high/low (05:00–07:00 GMT)
- EMA(20), EMA(50) on H1 (trend filter)
- ATR(14) H1 for range quality

### Long Entry Rules
1. Mark range: 05:00–07:00 GMT high and low
2. **H1 trend filter**: EMA20 > EMA50 AND price > EMA20 (bullish)
3. **Entry**: BUY STOP at range high + 3 pips
4. Only take breakout aligned with H1 trend

### Short Entry Rules
- H1 bearish: EMA20 < EMA50, price < EMA20
- SELL STOP at range low - 3 pips

### Stop Loss
- Opposite end of range (full range width as stop)

### Take Profit
- TP1 at 1R (close 50%)
- TP2 at nearest pivot point (R1 for longs, S1 for shorts)

### Position Sizing
- 0.5% per trade

### Exit Rules
- If not at TP1 by 12:00 GMT, exit at market
- Hard close by 16:00 GMT
- Re-entry inside range after breakout = exit

### Filters
- Pre-London range 20–70 pips (ideal band)
- **Trend filter is ESSENTIAL** — non-filtered version has ~40% WR
- Skip if major EU data release (German CPI, ECB) in breakout window
- Cancel orders at 10:00 GMT if not triggered

### Known Risks
- False breakout with quick reversal is the dominant failure mode
- News-driven gaps around EU data
- DST changeovers shift London open by 1 hour
- Range-bound days produce multiple whipsaws if rules not strict

### Pseudocode
```python
def london_open_breakout():
    # At 07:00 GMT
    if current_time_gmt != "07:00":
        return None
    
    pre_london_bars = get_h1_bars(start="05:00", end="07:00")
    range_hi = max(bar.high for bar in pre_london_bars)
    range_lo = min(bar.low for bar in pre_london_bars)
    range_size = range_hi - range_lo
    
    # Filters
    if not (20 <= range_size <= 70):
        return None
    if is_major_eu_news_day():
        return None
    
    orders = []
    
    # Long: only if H1 trend bullish
    if H1.EMA20 > H1.EMA50 and H1.Close > H1.EMA20:
        entry = range_hi + 3
        orders.append({
            "type": "BUY_STOP",
            "entry": entry,
            "sl": range_lo - 3,
            "tp1": entry + range_size,
            "tp2": daily_pivot_R1,
            "expire": "10:00 GMT"
        })
    
    # Short: only if H1 trend bearish
    elif H1.EMA20 < H1.EMA50 and H1.Close < H1.EMA20:
        entry = range_lo - 3
        orders.append({
            "type": "SELL_STOP",
            "entry": entry,
            "sl": range_hi + 3,
            "tp1": entry - range_size,
            "tp2": daily_pivot_S1,
            "expire": "10:00 GMT"
        })
    
    return {"orders": orders}

# Post-entry
def monitor(position):
    if current_time_gmt >= "12:00" and position.pnl < position.tp1_distance:
        return "CLOSE"
    if current_time_gmt >= "16:00":
        return "HARD_CLOSE"
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥300 trades over 2 years |
| Profit factor | 1.4–1.7 |
| Max drawdown | 12–16% |
| DST sensitivity | Build calendar logic |
| Pairing | Tokyo range (#8) is complementary — trade whichever triggers first |

### Dashboard Signals to Surface
- Live pre-London range
- H1 trend state (bullish/bearish/neutral)
- Trade direction bias
- Setup validity checklist
- Countdown to 07:00 GMT trigger

---

## Strategy 14: Bollinger Band Mean Reversion

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 14 |
| **Category** | Mean Reversion |
| **Timeframes** | H1 / H4 |
| **Session Filter** | Any, but best in Tokyo range and pre-London |
| **Win Rate** | 55–70% (ranging); 30–45% (trending — SKIP) |
| **Risk:Reward** | 1:1 to 1:2 |
| **Trades/Day** | 1–2 |
| **Trades/Week** | 3–5 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
USDJPY round numbers plus BoJ containment create tight trading ranges where band touches revert cleanly. Adding a candle confirmation filter removes the worst band-ride losses during strong trends.

### Macro Bias Inputs
- Not macro-driven. Purely technical.
- **Critical regime check**: must NOT be in strong trend

### Indicators Required
- Bollinger Bands: SMA(20), ±2 standard deviations
- ADX(14) for regime filter
- RSI(14) for confirmation
- Simple candle pattern detection

### Long Entry Rules
1. **Regime gate**: ADX(14) < 25 (not strongly trending)
2. **Signal**: Price low wicks BELOW lower band
3. **Confirmation candle**: Subsequent bar closes bullish (close > open) WITHIN the band
4. **Optional reinforcement**: RSI < 30 at the wick and rising
5. **Entry**: Break above confirmation candle high

### Short Entry Rules
1. ADX < 25
2. Price high wicks above upper band
3. Bearish confirmation candle within band
4. Optional: RSI > 70 and falling

### Stop Loss
- 0.5–1 × ATR beyond the wick extreme

### Take Profit
- TP1: Middle band (SMA20)
- TP2: Opposite band (rare)

### Position Sizing
- 0.5% per trade

### Exit Rules
- Reach middle band = partial exit (60%)
- Close beyond middle band in original direction = full exit
- Time exit: 10 H1 bars if no TP reached

### Filters
- **ADX < 25 is hard gate** — ADX 25+ signals trend, bands ride
- Band width (standard deviation) not contracting too aggressively (imminent breakout risk)
- Avoid entries 30 min before/after news releases

### Known Risks
- Band riding in trends: worst case is repeated losses as price stays at band
- Regime-dependent — must have ADX filter
- Mean-reversion fails catastrophically during BoJ intervention unwinds

### Pseudocode
```python
def bollinger_mean_reversion():
    sma20 = SMA(close, 20)
    std = stdev(close, 20)
    upper = sma20 + 2 * std
    lower = sma20 - 2 * std
    
    # Regime gate
    if ADX14 >= 25:
        return None  # trending, skip
    
    # Long setup
    prev_bar = bars[-2]
    current_bar = bars[-1]
    
    if prev_bar.low < lower:
        if current_bar.close > current_bar.open and current_bar.close > lower:
            # Optional RSI reinforcement
            rsi_ok = RSI14 < 35
            
            entry_trigger = current_bar.high
            sl = prev_bar.low - 0.5 * ATR
            tp1 = sma20
            tp2 = upper
            
            return {
                "side": "long",
                "entry": entry_trigger,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2,
                "rsi_reinforcement": rsi_ok
            }
    
    # Short setup (mirror)
    if prev_bar.high > upper:
        if current_bar.close < current_bar.open and current_bar.close < upper:
            return {
                "side": "short",
                "entry": current_bar.low,
                "sl": prev_bar.high + 0.5 * ATR,
                "tp1": sma20,
                "tp2": lower
            }
    
    return None

# Exit logic
def monitor(position):
    if position.side == "long":
        if close >= sma20:
            return {"action": "PARTIAL_EXIT", "pct": 60}
        if close > sma20 + 0.5 * ATR:
            return {"action": "FULL_EXIT"}
    if bars_in_trade >= 10:
        return {"action": "TIME_EXIT"}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥200 trades over 3 years |
| Profit factor | 1.3–1.6 (ranging); <1.0 (pure trend) |
| Max drawdown | 12–18% |
| Regime dependency | Track separately |
| Pairing | Pair with trend system (e.g. #6 MACD+200EMA) |

### Dashboard Signals to Surface
- Bollinger bands with band width trend
- ADX regime classification
- Current distance to middle band
- RSI reinforcement status
- Recent band touches count

---

## Strategy 15: Engulfing Candle at Key Level

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 15 |
| **Category** | Price Action |
| **Timeframes** | H4 / Daily |
| **Session Filter** | Any |
| **Win Rate** | 55–65% |
| **Risk:Reward** | 1:1.5 to 1:2 |
| **Trades/Day** | 0 |
| **Trades/Week** | 2–4 (H4) |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Bulkowski's research documents a 79% reversal rate for the bearish engulfing at meaningful levels. USDJPY forms textbook engulfing patterns at round numbers (150, 152, 155, 160) because institutional order flow clusters there, and the pattern is highly mechanical to detect algorithmically.

### Macro Bias Inputs
- Not required but align direction with Daily EMA50 trend
- Engulfings against strong macro trend have lower conviction

### Indicators Required
- Candle pattern detection (bullish/bearish engulfing)
- Horizontal S/R level detection (round numbers + prior swings)
- ATR(14) for stops
- Optional: Fibonacci to find 50–61.8% retracement zones

### Long Entry Rules
1. **Step 1**: Identify a key level (horizontal S/R, Fib 50%, 61.8%, or round number)
2. **Step 2**: Bullish engulfing pattern forms — current candle body fully engulfs prior candle body, closes above prior high
3. **Step 3**: Level is tested (wick touches or pierces level)
4. **Step 4**: Close of engulfing bar is above the level
5. **Entry**: Break of engulfing bar high + 2 pips, OR market at close of engulfing bar

### Short Entry Rules
- Mirror: bearish engulfing at resistance level, close below level
- Especially high conviction at intervention zones (155+)

### Stop Loss
- Below engulfing candle low (longs)
- Add 0.5 × ATR buffer

### Take Profit
- TP1: 1.5R (close 50%)
- TP2: Next significant level
- R:R target minimum 1:1.5

### Position Sizing
- 0.5–0.75% per trade

### Exit Rules
- Close below level + 0.5 × ATR = exit (invalidation)
- TP1 hit = move SL to break-even
- Time exit: 10 H4 bars (~40 hours)

### Filters
- **Engulfing body size**: must be ≥ 1.5× average of prior 10 candles (real momentum)
- Skip engulfings inside tight consolidation (no prior trend leg to reverse)
- Require level to be tested ≤ 3 times prior (untouched levels strongest)
- Engulfing volume (tick volume) higher than prior bar

### Known Risks
- False engulfings in choppy markets
- At intervention zones, engulfings can be gapped through by BoJ action
- Subjective level identification without algorithmic drawing
- Pattern is lagging — by definition, price has already reversed

### Pseudocode
```python
def is_bullish_engulfing(bar, prev):
    body_bar = abs(bar.close - bar.open)
    body_prev = abs(prev.close - prev.open)
    avg_body_10 = mean(abs(b.close - b.open) for b in bars[-10:])
    
    return (
        bar.close > bar.open and  # bullish bar
        prev.close < prev.open and  # prior bearish
        bar.open <= prev.close and
        bar.close >= prev.open and
        body_bar >= 1.5 * avg_body_10  # momentum filter
    )

def check_engulfing_at_level():
    # Define key levels
    round_numbers = [150.00, 152.00, 155.00, 160.00]
    prior_swings = get_prior_swing_levels()
    key_levels = round_numbers + prior_swings
    
    for level in key_levels:
        # Check if price tested the level
        if abs(current_bar.low - level) < 0.3 * ATR:
            # Check for bullish engulfing
            if is_bullish_engulfing(current_bar, previous_bar):
                # Level-break confirmation
                if current_bar.close > level:
                    # Test-count filter
                    if level_test_count(level, lookback=50) <= 3:
                        entry = current_bar.close
                        sl = current_bar.low - 0.5 * ATR
                        risk = entry - sl
                        tp1 = entry + 1.5 * risk
                        tp2 = find_next_resistance_above(entry)
                        return {
                            "side": "long",
                            "level": level,
                            "entry": entry,
                            "sl": sl,
                            "tp1": tp1,
                            "tp2": tp2
                        }
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥120 trades over 4 years |
| Profit factor | 1.5–1.9 |
| Max drawdown | 10–15% |
| Reference | Bulkowski reversal rates documented |
| Engineering challenge | Algorithmic level-detection |

### Dashboard Signals to Surface
- Detected engulfing patterns on current chart
- Key levels map with test counts
- Engulfing body size vs average (momentum filter)
- Setup validity checklist
- Nearest resistance levels for TP planning

---
## Strategy 16: RSI(14) Mean Reversion with Trend Filter

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 16 |
| **Category** | Mean Reversion |
| **Timeframes** | H1 / H4 |
| **Session Filter** | Any (best in Tokyo and pre-London) |
| **Win Rate** | 50–62% |
| **Risk:Reward** | 1:1 to 1:1.5 |
| **Trades/Day** | 1–3 (H1) |
| **Trades/Week** | 2–4 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Works especially well during BoJ intervention-driven ranges (e.g., 145–150 corridors) where USDJPY oscillates without clear trend. Must be filtered for trend regime to avoid band-riding losses.

### Macro Bias Inputs
- Not required. Regime filter (trend vs range) is the key gate.

### Indicators Required
- RSI(14)
- EMA(200) for trend regime
- ADX(14) as alternative regime filter
- ATR(14) for stops

### Long Entry Rules (Two Modes)
**Mode A — Counter-trend within range**:
- ADX < 20 AND RSI crosses back above 30 from below
- Entry at close of crossback bar

**Mode B — Pullback in uptrend**:
- Price > EMA200 AND RSI dips to 40 and crosses back above 40
- Entry at close of crossback bar

### Short Entry Rules
**Mode A**: ADX < 20, RSI crosses below 70
**Mode B**: Price < EMA200, RSI crosses below 60

### Stop Loss
- 1.5 × ATR from entry

### Take Profit
- RSI reaches 50 (neutral)
- OR midrange level

### Position Sizing
- 0.5% per trade

### Exit Rules
- RSI reaches target (50) = exit
- Opposite RSI signal before TP = exit
- Time stop: 12 H1 bars

### Filters
- Regime filter mandatory: either ADX<20 OR clear trend-alignment mode
- Skip RSI signals during news windows
- Require RSI at extreme for minimum 2 bars (not just single-bar spike)

### Known Risks
- Band-riding in trends without filter
- Fast reversals can undo the RSI signal
- R:R is modest — one big loss erases multiple wins
- RSI(14) is quite responsive — shorter periods (5–7) generate too many signals

### Pseudocode
```python
def rsi_mean_reversion_signal():
    # Mode A: Counter-trend in range
    if ADX14 < 20:
        if crossover(RSI14, 30):
            entry = close
            sl = entry - 1.5 * ATR
            tp = entry + 1 * ATR  # or wait for RSI == 50
            return {
                "side": "long",
                "mode": "A_counter_trend",
                "entry": entry,
                "sl": sl,
                "tp": tp
            }
        if crossunder(RSI14, 70):
            return {
                "side": "short",
                "mode": "A_counter_trend",
                "entry": close,
                "sl": close + 1.5 * ATR,
                "tp": close - 1 * ATR
            }
    
    # Mode B: Pullback in trend
    if close > EMA200:
        if crossover(RSI14, 40):
            swing_low = min(low[-10:])
            entry = close
            sl = swing_low - 0.5 * ATR
            tp = entry + 1.5 * (entry - sl)
            return {
                "side": "long",
                "mode": "B_pullback",
                "entry": entry,
                "sl": sl,
                "tp": tp
            }
    
    if close < EMA200:
        if crossunder(RSI14, 60):
            swing_high = max(high[-10:])
            entry = close
            sl = swing_high + 0.5 * ATR
            tp = entry - 1.5 * (sl - entry)
            return {
                "side": "short",
                "mode": "B_pullback",
                "entry": entry,
                "sl": sl,
                "tp": tp
            }
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥200 trades over 3 years |
| Profit factor | 1.2–1.5 |
| Max drawdown | 12–18% |
| Mode tracking | Track Mode A and Mode B separately |
| Reference | QuantifiedStrategies documented ~55–60% WR |

### Dashboard Signals to Surface
- RSI(14) with 30/50/70 lines
- Regime classification (range vs trend)
- Active mode indicator (A or B)
- Bars since last RSI extreme
- Mode-specific win rate tracker

---

## Strategy 17: Fibonacci 50% / 61.8% Pullback

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 17 |
| **Category** | Retracement |
| **Timeframes** | H4 / Daily |
| **Session Filter** | London + NY |
| **Win Rate** | 45–58% |
| **Risk:Reward** | 1:2 to 1:3 |
| **Trades/Day** | 0 |
| **Trades/Week** | 1–3 (H4) |
| **Algo Fit** | MEDIUM (requires impulse-leg detection) |

### Edge (Why It Works on USDJPY)
Carry-trade trends produce textbook pullback structures in USDJPY. Yen liquidity and institutional order stacking at 50% / 61.8% levels create clean reaction zones. The "golden pocket" (50–61.8%) has documented statistical significance.

### Macro Bias Inputs
- Daily trend direction
- Align pullback trade with Fed-BoJ spread direction

### Indicators Required
- Fibonacci retracement tool (auto-draw on detected impulse legs)
- Swing high/low detection
- EMA(50) for trend context
- Candle pattern detection at levels

### Long Entry Rules
1. **Step 1**: Identify clear impulse leg up (from swing low to swing high, min 100 pips on H4)
2. **Step 2**: Draw Fib retracement from impulse low to impulse high
3. **Step 3**: Wait for pullback into 50% to 61.8% zone ("golden pocket")
4. **Step 4**: Bullish candle pattern at the zone (engulfing, pin bar, or hammer)
5. **Step 5**: Entry on confirmation bar close or break of its high

### Short Entry Rules
- Mirror: identify impulse leg down, pullback to 50–61.8%, bearish candle pattern

### Stop Loss
- Below 78.6% retracement
- If breached, impulse leg is invalid

### Take Profit
- TP1: Return to impulse high (100%)
- TP2: 1.272 extension
- TP3: 1.618 extension

### Position Sizing
- 0.5–0.75% per trade

### Exit Rules
- Close below 78.6% Fib = exit (impulse invalidated)
- TP1 at 100% retracement: move SL to break-even
- Runner stays in to 1.272/1.618 extensions

### Filters
- Impulse leg must be clear (no choppy structure)
- Minimum impulse leg size: 100 pips on H4, 200 pips on Daily
- Skip if pullback is extremely shallow (<38.2%) — weak retracement signals weak setup
- Skip if pullback takes more than 50% of impulse leg duration (losing momentum)

### Known Risks
- Impulse leg detection is subjective — automation requires careful pivot logic
- Deep pullbacks past 78.6% invalidate but can be early entries in new trend
- At intervention zones, Fib levels can be overridden by BoJ action
- Works better in smoothly trending regimes

### Pseudocode
```python
def detect_impulse_leg(bars, lookback=50, min_size_pips=100):
    # Find most recent swing low -> swing high (up impulse)
    # or swing high -> swing low (down impulse)
    swings = detect_swings(bars[-lookback:], fractal_size=5)
    
    if len(swings) < 2:
        return None
    
    last_two = swings[-2:]
    impulse_range = abs(last_two[1].price - last_two[0].price)
    
    if impulse_range < min_size_pips * pip_value:
        return None
    
    direction = "UP" if last_two[1].price > last_two[0].price else "DOWN"
    return {
        "direction": direction,
        "low": min(last_two[0].price, last_two[1].price),
        "high": max(last_two[0].price, last_two[1].price),
        "range": impulse_range,
        "duration_bars": last_two[1].index - last_two[0].index
    }

def fib_pullback_signal():
    impulse = detect_impulse_leg(H4_bars)
    if not impulse:
        return None
    
    if impulse["direction"] == "UP":
        fib_50 = impulse["high"] - 0.5 * impulse["range"]
        fib_618 = impulse["high"] - 0.618 * impulse["range"]
        fib_786 = impulse["high"] - 0.786 * impulse["range"]
        
        # Check if current H4 bar is in the golden pocket
        if fib_618 <= current_H4.low <= fib_50:
            # Look for bullish reversal candle
            if is_bullish_reversal(current_H4):
                entry = next_bar_open
                sl = fib_786 - 0.2 * ATR
                tp1 = impulse["high"]
                tp2 = impulse["high"] + 0.272 * impulse["range"]
                tp3 = impulse["high"] + 0.618 * impulse["range"]
                return {
                    "side": "long",
                    "entry": entry,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "tp3": tp3,
                    "impulse": impulse
                }
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 80–120 trades over 4 years |
| Profit factor | 1.5–1.9 |
| Max drawdown | 12–17% |
| Engineering risk | Reliable pivot detection |
| Parameter sensitivity | Sweep pivot lookback 10–30 bars |

### Dashboard Signals to Surface
- Detected impulse legs with auto-drawn Fib retracements
- Current price position in Fib zones
- Golden pocket highlighted (50–61.8%)
- Candle pattern status at Fib zone
- Extension targets (1.272, 1.618)

---

## Strategy 18: Inside Bar Breakout (Mother Bar)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 18 |
| **Category** | Price Action Breakout |
| **Timeframes** | Daily (classical); H4 with filter |
| **Session Filter** | Any |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 1:2 |
| **Trades/Day** | 0 |
| **Trades/Week** | 0.5–1 (Daily); 1–3 (H4) |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
Carry-trade phases produce clean trend-consolidation-breakout sequences. Inside bars represent consolidation; breaks in trend direction continue with high probability. Simple, mechanical pattern.

### Macro Bias Inputs
- Align breakout direction with Daily trend (EMA50 slope)

### Indicators Required
- Inside bar pattern detection (H < prev H AND L > prev L)
- EMA(50) for trend direction
- ATR(14) for stops

### Long Entry Rules
1. **Condition 1**: Prior bar = "mother bar"; current bar = "inside bar" (entirely within mother bar range)
2. **Condition 2**: Trend-aligned: price and EMA50 both above longer average OR clearly rising
3. **Entry**: BUY STOP at inside bar high + 2 pips (only takes trend-side break)

### Short Entry Rules
- Inside bar within mother bar, trend bearish
- SELL STOP at inside bar low - 2 pips

### Stop Loss
- Opposite end of mother bar (stronger setup) OR opposite end of inside bar (tighter)

### Take Profit
- 2R or nearest structural level

### Position Sizing
- 0.5% per trade

### Exit Rules
- Cancel pending order if a new inside bar forms over the original setup
- If not at TP within 10 bars, exit at market
- Re-entry inside the mother bar range after breakout = exit

### Filters
- Mother bar should be 1.5× average bar size (real consolidation)
- Skip if multiple inside bars stack (range contraction = false break risk)
- Only trade trend-aligned side (don't OCO both sides unless neutral trend)

### Known Risks
- False breakouts after inside-bar "traps"
- Tight stops get hit by normal noise
- In strong trends, inside bars can be single-bar pauses that resolve either way

### Pseudocode
```python
def is_inside_bar(current, previous):
    return (current.high < previous.high and 
            current.low > previous.low)

def detect_trend(ema50_slope):
    if ema50_slope > threshold:
        return "up"
    elif ema50_slope < -threshold:
        return "down"
    return "neutral"

def inside_bar_breakout():
    if not is_inside_bar(current_bar, previous_bar):
        return None
    
    mother_bar = previous_bar
    mother_size = mother_bar.high - mother_bar.low
    avg_range = mean(bars[-10:].ranges)
    
    # Filter: mother bar should be significant
    if mother_size < 1.5 * avg_range:
        return None
    
    trend = detect_trend(EMA50.slope)
    
    orders = []
    
    if trend == "up":
        orders.append({
            "type": "BUY_STOP",
            "entry": current_bar.high + 2,
            "sl": mother_bar.low - 2,  # mother bar low
            "tp_rr": 2.0,
            "expire_bars": 3
        })
    elif trend == "down":
        orders.append({
            "type": "SELL_STOP",
            "entry": current_bar.low - 2,
            "sl": mother_bar.high + 2,
            "tp_rr": 2.0,
            "expire_bars": 3
        })
    # If neutral trend: OCO both sides (lower conviction, size down)
    
    return {"orders": orders}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 60–100 trades over 4 years (Daily) |
| Profit factor | 1.4–1.7 |
| Max drawdown | 10–15% |
| Backtest window | Long window needed for Daily |
| H4 variant | 3–4x more signals, lower WR |

### Dashboard Signals to Surface
- Inside bar detection (current + past 20 bars)
- Mother bar size vs average
- Trend direction via EMA50
- Pending order preview
- Stack count (multiple inside bars)

---

## Strategy 19: Daily Pivot Point Breakout

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 19 |
| **Category** | Session Breakout / Levels |
| **Timeframes** | M30 / H1 |
| **Session Filter** | London–NY overlap (12:00–16:00 GMT) |
| **Win Rate** | 40–48% |
| **Risk:Reward** | 1.5:1 to 2:1 |
| **Trades/Day** | 1 |
| **Trades/Week** | 3–4 |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
USDJPY respects daily pivots because NY close (used for pivot calculation) aligns with institutional repositioning. Classic pivots (standard) remain effective despite being decades old due to algorithmic respect and self-fulfilling trading.

### Macro Bias Inputs
- Daily trend direction
- Optional: Fed-BoJ spread direction

### Indicators Required
- **Classic pivot points**:
  - `P = (PrevHigh + PrevLow + PrevClose) / 3`
  - `R1 = 2P - PrevLow`
  - `R2 = P + (PrevHigh - PrevLow)`
  - `S1 = 2P - PrevHigh`
  - `S2 = P - (PrevHigh - PrevLow)`
- EMA(50) on H1 for trend
- ATR(14) on H1

### Long Entry Rules
1. Wait for London–NY overlap (12:00 GMT onwards)
2. **Strong body close above R1** (close must be in upper 25% of candle range)
3. **H1 trend aligned bullish** (EMA50 rising, close > EMA50)
4. **Volume confirmation** (tick volume > prior 10-bar average)
5. **Entry**: Market at close of breakout bar

### Short Entry Rules
- Strong body close below S1
- H1 trend bearish
- Volume confirmation

### Stop Loss
- 0.5 × ATR beyond the pivot level (R1 for longs, S1 for shorts)

### Take Profit
- TP1: R2 for longs (S2 for shorts)
- TP2: Next major level

### Position Sizing
- 0.5% per trade

### Exit Rules
- Price closes back inside pivot range (below R1 for long) = exit
- Hard close by 20:00 GMT
- TP1 hit = move SL to break-even

### Filters
- Distance from pivot to R1 > 20 pips (not dead quiet days)
- Skip major news days at release time
- Require strong-body close (rejection wicks = invalid break)

### Known Risks
- False breakouts around pivot are common — body-close filter is essential
- Pivots calculated differently by platforms — standardize with NY close
- Works better when Daily trend exists; range days produce whipsaws

### Pseudocode
```python
def calculate_daily_pivots(prev_day):
    P = (prev_day.high + prev_day.low + prev_day.close) / 3
    R1 = 2 * P - prev_day.low
    R2 = P + (prev_day.high - prev_day.low)
    R3 = prev_day.high + 2 * (P - prev_day.low)
    S1 = 2 * P - prev_day.high
    S2 = P - (prev_day.high - prev_day.low)
    S3 = prev_day.low - 2 * (prev_day.high - P)
    return {"P": P, "R1": R1, "R2": R2, "R3": R3,
            "S1": S1, "S2": S2, "S3": S3}

def pivot_breakout_signal():
    # Calculate pivots at NY close (22:00 GMT)
    pivots = calculate_daily_pivots(yesterday)
    
    # Only trade during London-NY overlap
    if not (12 <= current_hour_gmt < 20):
        return None
    
    # Long setup
    body = abs(close - open)
    range_size = high - low
    strong_body = body >= 0.75 * range_size
    
    if close > pivots["R1"] and strong_body:
        if H1.EMA50.slope > 0 and close > H1.EMA50:
            avg_vol = mean(volume[-10:])
            if volume > avg_vol:
                entry = close
                sl = pivots["R1"] - 0.5 * ATR
                tp1 = pivots["R2"]
                tp2 = find_next_level_above(tp1)
                return {
                    "side": "long",
                    "entry": entry,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2
                }
    
    # Short setup (mirror at S1)
    if close < pivots["S1"] and strong_body:
        if H1.EMA50.slope < 0 and close < H1.EMA50:
            entry = close
            sl = pivots["S1"] + 0.5 * ATR
            tp1 = pivots["S2"]
            tp2 = find_next_level_below(tp1)
            return {
                "side": "short",
                "entry": entry,
                "sl": sl,
                "tp1": tp1,
                "tp2": tp2
            }
    
    return None
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | ≥300 trades over 2 years |
| Profit factor | 1.3–1.6 |
| Max drawdown | 12–17% |
| Critical | Pivot calculation standardization |
| Variant | Tokyo-session variant performs worse — stick to London-NY |

### Dashboard Signals to Surface
- Live pivot levels (P, R1-R3, S1-S3)
- Distance to nearest pivot
- H1 trend direction
- Body-close strength indicator
- Volume vs average

---

## Strategy 20: Post-News Breakout (NFP / FOMC / BoJ)

### Overview
| Field | Value |
|-------|-------|
| **Rank** | 20 |
| **Category** | Event-Driven Technical |
| **Timeframes** | H1 (post-event) |
| **Session Filter** | Only on high-impact event days |
| **Win Rate** | 45–55% |
| **Risk:Reward** | 1:2 |
| **Trades/Day** | 0 (most days); 1 on event days |
| **Trades/Week** | ~0.25 (events are infrequent) |
| **Algo Fit** | HIGH |

### Edge (Why It Works on USDJPY)
USDJPY is the most policy-sensitive major. Post-event moves on FOMC, BoJ, NFP, and US CPI routinely exceed 100 pips, and the direction is typically directional rather than mean-reverting. Skipping the release candle and trading the post-release range break gives a cleaner entry.

### Macro Bias Inputs
- Event surprise direction (actual vs consensus)
- Forward guidance language shift
- Market's pre-event positioning (COT reports)

### Indicators Required
- Post-release H1 range (first 1–2 H1 candles after event)
- RSI(14) for confirmation (>50 for longs, <50 for shorts)
- ATR(14) for stops
- Economic calendar feed integration

### Long Entry Rules
1. **SKIP** the release candle entirely
2. **Define range** using the first 1–2 H1 candles after release
3. **Entry**: BUY STOP at post-release range high + 5 pips
4. **Direction filter**: Must align with surprise direction
5. **Confirmation**: RSI > 50 on H1 at entry

### Short Entry Rules
- Mirror: SELL STOP at post-release range low - 5 pips
- Aligned with bearish surprise
- RSI < 50

### Stop Loss
- Opposite end of post-release range

### Take Profit
- TP at 2 × range width (typical 2R target)

### Position Sizing
- 0.3–0.4% per trade (elevated volatility = smaller size)

### Exit Rules
- Not at TP within 6 H1 bars = exit
- Hard close by 22:00 GMT event day
- If re-enters range after breakout = exit

### Filters
- **Only Tier 1 events**: FOMC, BoJ, NFP, US CPI, US PCE, BoJ governor speeches
- Require clear surprise (actual vs consensus differential > 0.5 std dev)
- Skip if release candle range < 30 pips (market unimpressed = low follow-through)
- Skip BoJ intervention windows (above 155 has asymmetric risk)

### Known Risks
- Widened spreads during release (3–10 pips on USDJPY)
- Slippage on stop orders through wide-spread bars
- Fakeouts: initial direction reverses within 30 minutes
- BoJ verbal intervention can cause a fade of otherwise directional moves

### Pseudocode
```python
def calculate_surprise(actual, consensus, stdev):
    if stdev == 0:
        return 0
    return (actual - consensus) / stdev

def post_news_breakout(event):
    # Event must be Tier 1
    tier_1_events = ["FOMC", "BoJ", "NFP", "US_CPI", "US_PCE", "BoJ_SPEECH"]
    if event.type not in tier_1_events:
        return None
    
    # Wait for release candle close
    release_bar = get_bar_at_time(event.time)
    
    # Define surprise
    surprise = calculate_surprise(event.actual, event.consensus, event.stdev)
    if abs(surprise) < 0.5:
        return None  # market unimpressed
    
    # Release candle quality filter
    if release_bar.range < 30:
        return None  # low follow-through likely
    
    # Define post-release range
    post_bars = [release_bar, bar_after(release_bar)]
    post_range_hi = max(bar.high for bar in post_bars)
    post_range_lo = min(bar.low for bar in post_bars)
    range_size = post_range_hi - post_range_lo
    
    # Intervention-zone check
    if current_price > 155 and surprise > 0:
        return None  # asymmetric tail risk
    
    orders = []
    
    if surprise > 0:  # hawkish US / dovish Japan
        if H1.RSI14 > 50:
            entry = post_range_hi + 5
            orders.append({
                "type": "BUY_STOP",
                "entry": entry,
                "sl": post_range_lo - 5,
                "tp": entry + 2 * range_size,
                "expire_hours": 6
            })
    elif surprise < 0:
        if H1.RSI14 < 50:
            entry = post_range_lo - 5
            orders.append({
                "type": "SELL_STOP",
                "entry": entry,
                "sl": post_range_hi + 5,
                "tp": entry - 2 * range_size,
                "expire_hours": 6
            })
    
    return {"orders": orders, "size_pct": 0.35}
```

### Backtest KPI Targets
| Metric | Target |
|--------|--------|
| Sample size | 30–50 trades per year (events limited) |
| Profit factor | 1.4–1.8 on event days |
| Max drawdown | 8–12% (position sizing small) |
| Frequency | Low = high variance; need 5+ years data |
| Data dependency | Reliable economic calendar + consensus feed |

### Dashboard Signals to Surface
- Upcoming Tier 1 events countdown
- Consensus vs actual (post-release)
- Surprise magnitude in std dev
- Post-release range as it forms
- Pre-event positioning (COT)

---
## Implementation Roadmap

### Phase 1: Foundation (Weeks 1–4)

**Goal**: Set up data infrastructure and build one strategy end-to-end.

1. **Data pipeline**
   - Secure USDJPY OHLCV feed (M15, M30, H1, H4, D)
   - Integrate US 10Y yield feed (FRED or broker)
   - Set up economic calendar feed (Forex Factory API)
   - Build timestamp synchronization layer (GMT-normalized)

2. **Backtesting framework**
   - Choose platform: Backtrader (Python), Backtesting.py, or custom
   - Build standard KPI outputs: win rate, profit factor, max drawdown, Sharpe, consecutive losses
   - Implement walk-forward and out-of-sample validation

3. **First strategy implementation**
   - Start with **Strategy 6 (MACD + 200 EMA)** — simplest rules, well-documented
   - Fully code + backtest + paper-trade for 2 weeks
   - Establish baseline performance metrics

### Phase 2: Core Strategy Suite (Weeks 5–12)

**Goal**: Implement and validate 5 core strategies covering different regimes.

Build in this order:
1. **Strategy 12 (Donchian/Turtle)** — benchmark trend system, pure math
2. **Strategy 8 (Tokyo Range Breakout)** — session-based, low complexity
3. **Strategy 14 (Bollinger MR)** — mean-reversion counterpart
4. **Strategy 1 (Multi-Timeframe Alignment)** — higher-quality trend system
5. **Strategy 4 (US 10Y Correlation)** — macro-alignment system

**Deliverables**:
- Each strategy has: spec → code → backtest report → paper-trade log
- Combined portfolio simulation (multi-strategy P&L)
- Strategy-level regime performance analysis

### Phase 3: Advanced Strategies (Weeks 13–20)

**Goal**: Add higher-complexity strategies and optimize the portfolio.

Build:
- **Strategy 3 (Carry-Trade Pullback)** — requires rate feed integration
- **Strategy 2 (Ichimoku)** — full 5-line implementation
- **Strategy 15 (Engulfing at Level)** — requires algorithmic level detection
- **Strategy 17 (Fibonacci Pullback)** — requires pivot detection
- **Strategy 20 (Post-News Breakout)** — requires consensus feed

### Phase 4: Portfolio Construction (Weeks 21–24)

**Goal**: Combine strategies into a robust portfolio.

1. **Correlation analysis**: Build correlation matrix of strategy returns
2. **Regime classification**: Auto-detect trending vs ranging regimes
3. **Strategy allocation logic**: Scale positions based on regime fit
4. **Risk overlay**: Portfolio-level drawdown controls
5. **Live paper-trading**: 3+ months before any real capital

### Phase 5: Live Deployment (Weeks 25+)

**Goal**: Deploy with strict risk controls.

1. Start with 10% of intended capital
2. Scale up monthly if live performance matches backtest ±20%
3. Monthly review of each strategy's live performance
4. Retire strategies underperforming backtest by >40%

---

## Dashboard Integration Guide

### Core Dashboard Modules

#### 1. Market Overview Panel

Display at all times:
- Current USDJPY price with 1-day, 1-week, 1-month change
- Live DXY, US 10Y yield, Nikkei 225
- Fed-BoJ rate spread (with 3-month trend)
- Distance to nearest psychological level (150, 155, 160)
- Intervention-zone warning if price > 155
- VIX level (risk regime indicator)

#### 2. Strategy Scanner Panel

For each of the 20 strategies, show:
- **Status**: Active / Watching / Invalidated
- **Setup Score**: 0–100% based on condition-checklist
- **Signal direction**: Long / Short / None
- **Entry price** (if setup valid)
- **SL / TP1 / TP2** calculated
- **Risk in pips** and **Reward in pips**
- **R:R ratio**
- **Time to next trigger** (for session-based strategies)

#### 3. Regime Classifier

Auto-classifies the current USDJPY regime:
- **Trending (strong)**: ADX H4 > 25, EMA50 slope > threshold
- **Trending (moderate)**: ADX H4 20–25
- **Ranging**: ADX H4 < 20
- **Transitional**: ADX rising/falling through 20

Display which strategies are best-suited for the current regime.

#### 4. Economic Calendar Integration

- Next 48 hours of Tier 1 events
- Previous / Consensus / Actual (when released)
- Surprise magnitude calculation
- Auto-trigger for Strategy 20 setups
- Warning to flatten positions before high-impact events

#### 5. Position Management Panel

For all open trades:
- Strategy source
- Entry time / price
- Current P&L (pips and %)
- Distance to SL / TP1 / TP2
- Time-stop countdown
- Trail-stop level
- Exit recommendations

#### 6. Performance Analytics

Per strategy:
- Win rate (rolling 30 / 90 / all-time)
- Profit factor
- Average R per trade
- Max consecutive losses
- Regime-adjusted performance
- Comparison to backtest benchmarks

### Recommended Data Refresh Rates

| Component | Refresh Rate |
|-----------|--------------|
| Price feed | Tick / Real-time |
| Indicators (H1 and below) | 1 minute |
| Indicators (H4) | 5 minutes |
| Indicators (Daily) | 15 minutes |
| Correlation data | 15 minutes |
| Macro rates feed | Hourly |
| COT positioning | Weekly (Fridays) |
| Economic calendar | 5 minutes |

### Strategy Status Calculation

For each strategy, calculate:

```python
def calculate_strategy_status(strategy, market_data):
    conditions = strategy.entry_conditions
    met_count = sum(1 for cond in conditions if cond.evaluate(market_data))
    total = len(conditions)
    
    score = (met_count / total) * 100
    
    if score == 100:
        return "SIGNAL"
    elif score >= 75:
        return "ALMOST"
    elif score >= 50:
        return "WATCHING"
    else:
        return "INACTIVE"
```

### Alert Framework

Build tiered alerts:

**Tier 1 (Critical — Push Notification)**:
- New trade signal
- Stop loss hit
- Take profit hit
- Intervention-zone breach (price > 155)
- Major macro event surprise

**Tier 2 (Important — In-App)**:
- Setup score crosses 75%
- Strategy invalidation
- Regime change detected
- Correlation breakdown

**Tier 3 (Informational — Log)**:
- Indicator crossovers
- New candle patterns
- Session transitions

### API Endpoints (If Building Web Dashboard)

Suggested REST API structure:

```
GET /api/market/usdjpy/current
GET /api/market/macro/fed-boj-spread
GET /api/market/correlations
GET /api/strategies                        # List all 20
GET /api/strategies/{id}                   # Full spec
GET /api/strategies/{id}/status            # Live status
GET /api/strategies/{id}/backtest          # Backtest results
GET /api/regime/current                    # Current regime
GET /api/events/upcoming                   # Economic calendar
GET /api/positions/open                    # Open trades
POST /api/positions/{id}/close             # Manual close
GET /api/performance/summary               # Portfolio KPIs
GET /api/performance/by-strategy           # Per-strategy metrics
```

### Database Schema (Suggested)

```sql
-- Strategies (static config)
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY,
    rank INTEGER,
    name VARCHAR(100),
    category VARCHAR(50),
    timeframe VARCHAR(50),
    win_rate_min DECIMAL(5,2),
    win_rate_max DECIMAL(5,2),
    rr_min DECIMAL(4,2),
    rr_max DECIMAL(4,2),
    algo_fit VARCHAR(20),
    spec_json JSONB                         -- full specification
);

-- Signals (each detected setup)
CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER REFERENCES strategies(id),
    detected_at TIMESTAMP,
    direction VARCHAR(10),                  -- long/short
    entry_price DECIMAL(10,4),
    sl_price DECIMAL(10,4),
    tp1_price DECIMAL(10,4),
    tp2_price DECIMAL(10,4),
    setup_score INTEGER,
    regime VARCHAR(30),
    metadata JSONB
);

-- Trades (executed)
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    signal_id INTEGER REFERENCES signals(id),
    strategy_id INTEGER REFERENCES strategies(id),
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    entry_price DECIMAL(10,4),
    exit_price DECIMAL(10,4),
    direction VARCHAR(10),
    size_lots DECIMAL(10,4),
    pnl_pips DECIMAL(10,2),
    pnl_currency DECIMAL(10,2),
    exit_reason VARCHAR(50),                -- TP1/TP2/SL/Time/Manual
    slippage_pips DECIMAL(5,2)
);

-- Market snapshots (for regime analysis)
CREATE TABLE market_snapshots (
    timestamp TIMESTAMP PRIMARY KEY,
    usdjpy_price DECIMAL(10,4),
    us_10y_yield DECIMAL(6,3),
    dxy_value DECIMAL(10,3),
    vix_value DECIMAL(6,2),
    fed_rate DECIMAL(5,3),
    boj_rate DECIMAL(5,3),
    adx_h4 DECIMAL(5,2),
    atr_h4 DECIMAL(8,4),
    regime VARCHAR(30)
);
```

---

## Appendix: Common Calculations

### Pip Value Calculation for USDJPY

```python
def pip_value_usdjpy(price, lot_size=1.0):
    """
    For USDJPY, 1 pip = 0.01 of price.
    Standard lot = 100,000 units.
    
    Pip value in USD = (0.01 / price) × 100,000 × lot_size
    """
    return (0.01 / price) * 100000 * lot_size

# Example at 150.00:
# pip_value = (0.01 / 150.00) * 100000 = $6.67 per standard lot
```

### Position Size (Risk-Based)

```python
def position_size(equity, risk_pct, sl_distance_pips, price):
    risk_amount = equity * (risk_pct / 100)
    pip_val = pip_value_usdjpy(price, lot_size=1.0)
    
    # Position in standard lots
    lots = risk_amount / (sl_distance_pips * pip_val)
    return round(lots, 2)

# Example:
# equity=10000, risk=0.5%, SL=25 pips, price=150.00
# risk_amount = $50
# pip_val = $6.67
# lots = 50 / (25 * 6.67) = 0.30 lots
```

### ATR Calculation

```python
def atr(bars, period=14):
    true_ranges = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i].high - bars[i].low,
            abs(bars[i].high - bars[i-1].close),
            abs(bars[i].low - bars[i-1].close)
        )
        true_ranges.append(tr)
    
    # Wilder's smoothing
    atr = sum(true_ranges[:period]) / period
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr
```

### EMA Calculation

```python
def ema(values, period):
    alpha = 2 / (period + 1)
    ema_values = [values[0]]
    for v in values[1:]:
        ema_values.append(alpha * v + (1 - alpha) * ema_values[-1])
    return ema_values
```

### MACD Calculation

```python
def macd(closes, fast=12, slow=26, signal=9):
    ema_fast = ema(closes, fast)
    ema_slow = ema(closes, slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = ema(macd_line, signal)
    histogram = [m - s for m, s in zip(macd_line, signal_line)]
    return macd_line, signal_line, histogram
```

### RSI Calculation

```python
def rsi(closes, period=14):
    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))
    
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    rsi_values = []
    for i in range(period, len(closes) - 1):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else 0
        rsi_val = 100 - (100 / (1 + rs))
        rsi_values.append(rsi_val)
    
    return rsi_values
```

### ADX Calculation

```python
def adx(bars, period=14):
    # Directional Movement
    plus_dm = []
    minus_dm = []
    for i in range(1, len(bars)):
        up_move = bars[i].high - bars[i-1].high
        down_move = bars[i-1].low - bars[i].low
        
        plus_dm.append(up_move if up_move > down_move and up_move > 0 else 0)
        minus_dm.append(down_move if down_move > up_move and down_move > 0 else 0)
    
    atr_vals = atr_series(bars, period)
    
    plus_di = [100 * pdm / a for pdm, a in zip(smoothed(plus_dm, period), atr_vals)]
    minus_di = [100 * ndm / a for ndm, a in zip(smoothed(minus_dm, period), atr_vals)]
    
    dx = [100 * abs(p - m) / (p + m) for p, m in zip(plus_di, minus_di) if (p + m) != 0]
    adx_vals = smoothed(dx, period)
    
    return adx_vals, plus_di, minus_di
```

### Bollinger Bands

```python
def bollinger_bands(closes, period=20, std_dev=2):
    sma_vals = [sum(closes[i-period:i]) / period for i in range(period, len(closes))]
    std_vals = [stdev(closes[i-period:i]) for i in range(period, len(closes))]
    
    upper = [s + std_dev * sd for s, sd in zip(sma_vals, std_vals)]
    lower = [s - std_dev * sd for s, sd in zip(sma_vals, std_vals)]
    
    return upper, sma_vals, lower
```

### Ichimoku Components

```python
def ichimoku(bars):
    tenkan = [(max(b.high for b in bars[i-9:i]) + 
               min(b.low for b in bars[i-9:i])) / 2 
              for i in range(9, len(bars))]
    
    kijun = [(max(b.high for b in bars[i-26:i]) + 
              min(b.low for b in bars[i-26:i])) / 2 
             for i in range(26, len(bars))]
    
    senkou_a = [(t + k) / 2 for t, k in zip(tenkan, kijun)]  # displace +26
    
    senkou_b = [(max(b.high for b in bars[i-52:i]) + 
                 min(b.low for b in bars[i-52:i])) / 2 
                for i in range(52, len(bars))]  # displace +26
    
    chikou = [b.close for b in bars]  # displace -26
    
    return {
        "tenkan": tenkan,
        "kijun": kijun,
        "senkou_a": senkou_a,
        "senkou_b": senkou_b,
        "chikou": chikou
    }
```

### Fibonacci Retracement Levels

```python
def fib_retracement(swing_low, swing_high):
    range_size = swing_high - swing_low
    return {
        "0": swing_high,
        "23.6": swing_high - 0.236 * range_size,
        "38.2": swing_high - 0.382 * range_size,
        "50": swing_high - 0.5 * range_size,
        "61.8": swing_high - 0.618 * range_size,  # golden pocket
        "78.6": swing_high - 0.786 * range_size,
        "100": swing_low,
        # Extensions
        "127.2": swing_high + 0.272 * range_size,
        "161.8": swing_high + 0.618 * range_size,
        "261.8": swing_high + 1.618 * range_size
    }
```

### Daily Pivot Points

```python
def daily_pivots(prev_high, prev_low, prev_close):
    P = (prev_high + prev_low + prev_close) / 3
    return {
        "P": P,
        "R1": 2 * P - prev_low,
        "R2": P + (prev_high - prev_low),
        "R3": prev_high + 2 * (P - prev_low),
        "S1": 2 * P - prev_high,
        "S2": P - (prev_high - prev_low),
        "S3": prev_low - 2 * (prev_high - P)
    }
```

### Session Time Conversions

```python
SESSION_GMT = {
    "TOKYO":   {"start": "00:00", "end": "09:00"},
    "LONDON":  {"start": "07:00", "end": "16:00"},
    "NY":      {"start": "12:00", "end": "21:00"},
    "SYDNEY":  {"start": "21:00", "end": "06:00"},
    "LO_NY_OVERLAP": {"start": "12:00", "end": "16:00"}
}

def is_in_session(timestamp_gmt, session_name):
    start = SESSION_GMT[session_name]["start"]
    end = SESSION_GMT[session_name]["end"]
    hour = timestamp_gmt.hour
    # Handle cross-midnight sessions
    if start > end:
        return hour >= int(start[:2]) or hour < int(end[:2])
    return int(start[:2]) <= hour < int(end[:2])
```

### Regime Classification

```python
def classify_regime(adx_h4, atr_h4, atr_avg):
    if adx_h4 >= 25:
        if atr_h4 > 1.3 * atr_avg:
            return "STRONG_TREND_HIGH_VOL"
        return "STRONG_TREND"
    elif adx_h4 >= 20:
        return "MODERATE_TREND"
    elif adx_h4 < 20:
        if atr_h4 < 0.7 * atr_avg:
            return "TIGHT_RANGE"
        return "RANGE"
    return "UNCLEAR"
```

---

## Strategy-to-Regime Matrix (Quick Reference)

| Regime | Best Strategies | Worst Strategies |
|--------|----------------|------------------|
| **Strong Trend** | 1, 6, 10, 12, 17 | 11, 14, 16 |
| **Moderate Trend** | 2, 3, 4, 7, 15 | 11 |
| **Range (tight)** | 11, 14, 16 | 10, 12, 18 |
| **Range (wide)** | 8, 13, 14, 16, 19 | 10, 12 |
| **Pre-Event** | (none — flatten) | All |
| **Post-Event** | 20 | 11, 14, 16 |
| **Intervention Zone (>155)** | 5 (shorts only), 15 (shorts) | All longs |

---

## Final Notes for Dashboard Developers

1. **Strategy state machines**: Many strategies (9, 10, 12, 14, 20) have multi-bar state transitions. Implement proper state persistence in the database, not just in-memory.

2. **Time zone handling**: Always store timestamps in UTC/GMT. Convert for display only. DST transitions (US: March/Nov, EU: March/Oct) shift session boundaries and will break session-based strategies if not handled.

3. **Weekend gaps**: USDJPY reopens Sunday 22:00 GMT. Any strategy holding positions Friday needs gap-handling logic.

4. **Japanese holiday calendar**: Hard-code Golden Week (late Apr–early May), Obon (mid-Aug), and New Year (Dec 29–Jan 3). Flag to reduce size or skip.

5. **Intervention monitoring**: Add a hard rule — when price > 155.00 on the chart, flag all long strategies for reduced size and enhanced monitoring.

6. **Correlation recalculation**: Rolling 30-day correlation (Strategy 4) is compute-intensive if done naively. Cache with incremental updates.

7. **Pivot detection**: Swing high/low detection (needed for strategies 1, 10, 15, 17) is the most common source of bugs. Use fractal-based detection with minimum 3-5 bar confirmation on each side.

8. **Backtest vs live slippage**: Expect live slippage of 0.5–2 pips on USDJPY during normal hours, 3–10 pips during events. Incorporate into live P&L tracking for honest comparison to backtests.

9. **Paper-trade before real money**: A minimum of 3 months of live paper-trading with real execution latency is strongly recommended before committing capital to any algo.

10. **Maintain this document**: Treat this file as the single source of truth. Any change to strategy rules should update this document first, then propagate to code.

---

**End of Document**

*This document is a reference specification for USDJPY algorithmic trading strategies. It is not financial advice. All strategies carry risk of loss. Past performance in backtests does not guarantee future results. Trade with capital you can afford to lose.*

"""S13: London Open Breakout — trend-filtered, 05:00-07:00 range, 07:00-12:00 trigger."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S13LondonBreakout(BaseStrategy):
    STRATEGY_ID = 13
    STRATEGY_NAME = "London Open Breakout"
    STRATEGY_TYPE = "Breakout"
    TIMEFRAMES = ["M30", "H1"]

    RANGE_MIN_PIPS = 20.0
    RANGE_MAX_PIPS = 70.0

    def evaluate(self) -> StrategyResult:
        # ── Session gate — only 07:00–12:00 GMT ─────────────────────────────
        utc_hour = self.ind.get("utc_hour", 0)
        utc_min = self.ind.get("utc_minute", 0)
        in_window = 7 <= utc_hour < 12

        if not in_window:
            return self._no_trade([
                f"Outside London breakout window (UTC {utc_hour:02d}:{utc_min:02d}) — valid 07:00-12:00 GMT"
            ])

        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)
        h1_df = self.ohlcv.get("H1")
        h1_close = ind.get("H1_close", price)
        h1_ema20 = ind.get("H1_ema20")
        h1_ema50 = ind.get("H1_ema50")
        h1_atr = ind.get("H1_atr14", 0.2)
        pivots = ind.get("daily_pivots")

        if any(v is None for v in [h1_ema20, h1_ema50]):
            return self._no_trade(["H1 EMA indicators not ready"])

        # Pre-London range from last 2 H1 bars (05:00–07:00 proxy)
        if h1_df is None or len(h1_df) < 4:
            return self._no_trade(["Not enough H1 bars for pre-London range"])

        pre_london_bars = h1_df.tail(4).head(2)
        range_high = float(pre_london_bars["high"].max())
        range_low = float(pre_london_bars["low"].min())
        range_size = range_high - range_low
        range_pips = range_size * 100

        if range_pips < self.RANGE_MIN_PIPS:
            return self._no_trade([f"Pre-London range {range_pips:.0f} pips too narrow (min {self.RANGE_MIN_PIPS})"])
        if range_pips > self.RANGE_MAX_PIPS:
            return self._no_trade([f"Pre-London range {range_pips:.0f} pips too wide (max {self.RANGE_MAX_PIPS})"])

        pip = 0.01
        bullish_trend = h1_ema20 > h1_ema50 and h1_close > h1_ema20
        bearish_trend = h1_ema20 < h1_ema50 and h1_close < h1_ema20

        broke_high = h1_close > range_high + 3 * pip
        broke_low = h1_close < range_low - 3 * pip

        if not broke_high and not broke_low:
            direction = "BUY" if bullish_trend else "SELL" if bearish_trend else "BUY"
            if direction == "BUY":
                proj_entry = round(range_high + 3 * pip, 3)
                proj_sl = round(range_low - 3 * pip, 3)
                proj_tp1 = round(proj_entry + range_size, 3)
            else:
                proj_entry = round(range_low - 3 * pip, 3)
                proj_sl = round(range_high + 3 * pip, 3)
                proj_tp1 = round(proj_entry - range_size, 3)
            return self._wait(direction,
                              f"Pre-London range {range_low:.3f}–{range_high:.3f} ({range_pips:.0f} pips) — awaiting breakout",
                              ["Break of range aligned with H1 trend"],
                              [f"Range valid: {range_pips:.0f} pips"],
                              ["No breakout yet"],
                              entry=proj_entry, sl=proj_sl, tp1=proj_tp1)

        # Trend filter — only take trend-aligned breakout
        if broke_high and not bullish_trend:
            return self._no_trade(["London breakout to upside but H1 trend bearish — skipping"])
        if broke_low and not bearish_trend:
            return self._no_trade(["London breakout to downside but H1 trend bullish — skipping"])

        tp2_level = None
        if broke_high:
            direction = "BUY"
            entry = h1_close
            sl = range_low - 3 * pip
            tp1 = entry + range_size
            tp2 = pivots["R1"] if pivots else entry + 1.5 * range_size
            reasons_for = [
                f"London bullish breakout above {range_high:.3f}",
                f"H1 trend bullish: EMA20 > EMA50",
                f"Range: {range_pips:.0f} pips",
            ]
        else:
            direction = "SELL"
            entry = h1_close
            sl = range_high + 3 * pip
            tp1 = entry - range_size
            tp2 = pivots["S1"] if pivots else entry - 1.5 * range_size
            reasons_for = [
                f"London bearish breakout below {range_low:.3f}",
                f"H1 trend bearish: EMA20 < EMA50",
                f"Range: {range_pips:.0f} pips",
            ]

        reasons_against = []
        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(3, 3, 0.8, bullish_trend or bearish_trend, True)
        opp2 = OpportunityAgent(2).evaluate(3, 3, 0.8, bullish_trend or bearish_trend, True)
        r1 = RiskAgent(1).evaluate(news, False, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, False, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.9, structure_quality=0.8, trend_alignment=1.0,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(float(tp2), 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

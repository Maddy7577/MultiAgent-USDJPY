"""S8: Tokyo Range Breakout — session gate mandatory, London open trigger."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S8TokyoRange(BaseStrategy):
    STRATEGY_ID = 8
    STRATEGY_NAME = "Tokyo Range Breakout"
    STRATEGY_TYPE = "Breakout"
    TIMEFRAMES = ["M30", "H1"]

    RANGE_MIN_PIPS = 25.0
    RANGE_MAX_ATR_MULT = 1.5

    def evaluate(self) -> StrategyResult:
        # ── Session gate — only evaluate during/after Tokyo / at London open ─
        utc_hour = self.ind.get("utc_hour", 0)
        utc_min = self.ind.get("utc_minute", 0)
        session = self.ind.get("session", "Off")

        # Valid window: 06:00–10:00 GMT (around London open after Tokyo)
        in_window = (6 <= utc_hour < 10)
        if not in_window:
            return self._no_trade([
                f"Outside Tokyo breakout window (current UTC {utc_hour:02d}:{utc_min:02d}) — valid 06:00-10:00 GMT"
            ])

        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)
        h1_df = self.ohlcv.get("H1")
        h4_atr = ind.get("H4_atr14") or ind.get("H1_atr14", 0.5)

        # Build Tokyo range from H1 bars 00:00–06:00 GMT
        if h1_df is None or len(h1_df) < 8:
            return self._no_trade(["Not enough H1 bars for Tokyo range"])

        # Use last 6 H1 bars as proxy for Tokyo session (00:00–06:00 GMT)
        tokyo_bars = h1_df.tail(8).head(6)
        tokyo_high = float(tokyo_bars["high"].max())
        tokyo_low = float(tokyo_bars["low"].min())
        range_width = tokyo_high - tokyo_low
        range_pips = range_width * 100

        if range_pips < self.RANGE_MIN_PIPS:
            return self._no_trade([f"Tokyo range {range_pips:.0f} pips too narrow (min {self.RANGE_MIN_PIPS})"])

        if h4_atr and range_width > self.RANGE_MAX_ATR_MULT * h4_atr:
            return self._no_trade([f"Tokyo range too wide ({range_pips:.0f} pips > {self.RANGE_MAX_ATR_MULT}×ATR)"])

        h1_close = ind.get("H1_close", price)
        pip = 0.01

        # ── Determine breakout direction ─────────────────────────────────────
        if h1_close > tokyo_high + 3 * pip:
            direction = "BUY"
            entry = h1_close
            sl = tokyo_low - 5 * pip
            tp1 = entry + range_width
            tp2 = entry + 1.5 * range_width
            reasons_for = [
                f"Bullish break above Tokyo high {tokyo_high:.3f}",
                f"Range width: {range_pips:.0f} pips",
            ]
            reasons_against = []
        elif h1_close < tokyo_low - 3 * pip:
            direction = "SELL"
            entry = h1_close
            sl = tokyo_high + 5 * pip
            tp1 = entry - range_width
            tp2 = entry - 1.5 * range_width
            reasons_for = [
                f"Bearish break below Tokyo low {tokyo_low:.3f}",
                f"Range width: {range_pips:.0f} pips",
            ]
            reasons_against = []
        else:
            proj_entry = round(tokyo_high + 3 * pip, 3)
            proj_sl = round(tokyo_low - 5 * pip, 3)
            proj_tp1 = round(proj_entry + range_width, 3)
            return self._wait("BUY",
                              f"Tokyo range {tokyo_low:.3f}–{tokyo_high:.3f} ({range_pips:.0f} pips) — awaiting breakout",
                              ["Break above Tokyo high or below Tokyo low"],
                              [f"Range defined: {range_pips:.0f} pips, quality valid"],
                              ["No breakout yet"],
                              entry=proj_entry, sl=proj_sl, tp1=proj_tp1)

        rrr = rrr_calc(entry, sl, tp1)
        news_flags = ["High-impact news day — reduce breakout reliability"] if news else []

        opp1 = OpportunityAgent(1).evaluate(2, 3, 0.7, True, True)
        opp2 = OpportunityAgent(2).evaluate(2, 3, 0.7, True, True)
        r1 = RiskAgent(1).evaluate(news, False, rrr, spread_pips, price, direction, news_flags)
        r2 = RiskAgent(2).evaluate(news, False, rrr, spread_pips, price, direction, news_flags)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.85, structure_quality=0.75, trend_alignment=0.6,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

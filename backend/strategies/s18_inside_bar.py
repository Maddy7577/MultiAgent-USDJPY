"""S18: Inside Bar Breakout — trend-aligned break of inside bar (mother bar)."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S18InsideBar(BaseStrategy):
    STRATEGY_ID = 18
    STRATEGY_NAME = "Inside Bar Breakout"
    STRATEGY_TYPE = "Price Action"
    TIMEFRAMES = ["D1", "H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        h4_df = self.ohlcv.get("H4")
        inside_bar = ind.get("H4_inside_bar", False)
        h4_close = ind.get("H4_close", price)
        h4_atr = ind.get("H4_atr14", 0.5)
        h4_ema50 = ind.get("H4_ema50")
        d_close = ind.get("D1_close", price)
        d_ema50 = ind.get("D1_ema50")

        if not inside_bar:
            return self._no_trade(["No inside bar pattern detected on H4"])

        if h4_df is None or len(h4_df) < 3:
            return self._no_trade(["Not enough H4 data for inside bar analysis"])

        curr = h4_df.iloc[-1]
        mother = h4_df.iloc[-2]
        mother_size = float(mother["high"]) - float(mother["low"])
        avg_range = float((h4_df["high"] - h4_df["low"]).tail(10).mean())

        if mother_size < 1.3 * avg_range:
            return self._no_trade([f"Mother bar size {mother_size*100:.0f} pips not significant (need 1.3× avg)"])

        # Trend via D1 EMA50 or H4 EMA50
        if d_ema50 is not None:
            trend = "up" if d_close > d_ema50 else "down"
        elif h4_ema50 is not None:
            trend = "up" if h4_close > h4_ema50 else "down"
        else:
            trend = "neutral"

        inside_high = float(curr["high"])
        inside_low = float(curr["low"])
        mother_high = float(mother["high"])
        mother_low = float(mother["low"])
        pip = 0.01

        broke_high = h4_close > inside_high + 2 * pip
        broke_low = h4_close < inside_low - 2 * pip

        if trend == "up" and broke_high:
            direction = "BUY"
            entry = h4_close
            sl = mother_low - 2 * pip
            risk = entry - sl
            tp1 = entry + 2 * risk
            reasons_for = [
                "Inside bar detected on H4",
                f"Mother bar: {mother_size*100:.0f} pips — significant",
                "Trend-aligned bullish breakout",
                f"Daily trend: {'UP' if trend == 'up' else 'NEUTRAL'}",
            ]
            reasons_against = []

        elif trend == "down" and broke_low:
            direction = "SELL"
            entry = h4_close
            sl = mother_high + 2 * pip
            risk = sl - entry
            tp1 = entry - 2 * risk
            reasons_for = [
                "Inside bar detected on H4",
                f"Mother bar: {mother_size*100:.0f} pips — significant",
                "Trend-aligned bearish breakout",
                f"Daily trend: DOWN",
            ]
            reasons_against = []

        elif broke_high or broke_low:
            return self._no_trade(["Inside bar broke against trend direction — skipping counter-trend"])
        else:
            wait_direction = "BUY" if trend == "up" else "SELL"
            if wait_direction == "BUY":
                proj_entry = round(inside_high + 2 * pip, 3)
                proj_sl = round(mother_low - 2 * pip, 3)
                proj_risk = proj_entry - proj_sl
                proj_tp1 = round(proj_entry + 2 * proj_risk, 3)
            else:
                proj_entry = round(inside_low - 2 * pip, 3)
                proj_sl = round(mother_high + 2 * pip, 3)
                proj_risk = proj_sl - proj_entry
                proj_tp1 = round(proj_entry - 2 * proj_risk, 3)
            return self._wait(wait_direction,
                              f"Inside bar setup valid — wait for break of {inside_high:.3f} (up) or {inside_low:.3f} (down)",
                              ["Trend-aligned break of inside bar high/low"],
                              [f"Inside bar ({inside_low:.3f}–{inside_high:.3f}), mother {mother_size*100:.0f} pips"],
                              ["No breakout yet"],
                              entry=proj_entry, sl=proj_sl, tp1=proj_tp1)

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and trend != "up") or (direction == "SELL" and trend != "down")

        opp1 = OpportunityAgent(1).evaluate(4, 4, 0.8, trend != "neutral", True)
        opp2 = OpportunityAgent(2).evaluate(4, 4, 0.8, trend != "neutral", True)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.9, structure_quality=0.8, trend_alignment=0.85,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

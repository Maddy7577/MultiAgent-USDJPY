"""S9: Keltner Channel Breakout — break upper/lower band, pull back to midline."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S9Keltner(BaseStrategy):
    STRATEGY_ID = 9
    STRATEGY_NAME = "Keltner Channel Breakout"
    STRATEGY_TYPE = "Breakout"
    TIMEFRAMES = ["H1", "H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        kc = ind.get("H1_keltner")
        if kc is None:
            return self._no_trade(["Keltner Channel not ready"])

        h1_close = ind.get("H1_close", price)
        h1_prev_close = ind.get("H1_prev_close", h1_close)
        h1_atr = ind.get("H1_atr14", 0.2)
        upper = kc["upper"]
        middle = kc["middle"]
        lower = kc["lower"]

        # ── State detection ──────────────────────────────────────────────────
        prev_broke_upper = h1_prev_close > upper
        prev_broke_lower = h1_prev_close < lower
        at_midline_long = abs(h1_close - middle) < 0.3 * h1_atr and h1_close > middle
        at_midline_short = abs(h1_close - middle) < 0.3 * h1_atr and h1_close < middle
        conf_bull = h1_close > ind.get("H1_open", h1_close)
        conf_bear = h1_close < ind.get("H1_open", h1_close)

        d1_close = ind.get("D1_close", price)
        d1_ema50 = ind.get("D1_ema50")
        daily_bullish = d1_ema50 is not None and d1_close > d1_ema50
        daily_bearish = d1_ema50 is not None and d1_close < d1_ema50

        # ── Long setup ───────────────────────────────────────────────────────
        c1_long = prev_broke_upper or h1_close > upper
        c2_long = at_midline_long
        c3_long = conf_bull

        long_conds = [
            "Price broke above upper Keltner band",
            "Pullback to midline (EMA20)",
            "Bullish confirmation candle",
        ]
        long_met = []
        if c1_long: long_met.append(long_conds[0])
        if c2_long: long_met.append(long_conds[1])
        if c3_long: long_met.append(long_conds[2])

        # ── Short setup ──────────────────────────────────────────────────────
        c1_short = prev_broke_lower or h1_close < lower
        c2_short = at_midline_short
        c3_short = conf_bear

        short_conds = [
            "Price broke below lower Keltner band",
            "Pullback to midline (EMA20)",
            "Bearish confirmation candle",
        ]
        short_met = []
        if c1_short: short_met.append(short_conds[0])
        if c2_short: short_met.append(short_conds[1])
        if c3_short: short_met.append(short_conds[2])

        ls = len(long_met) / 3
        ss = len(short_met) / 3

        if ls == 0 and ss == 0:
            return self._no_trade(["No Keltner band break detected"])

        if ls >= ss and c1_long:
            direction = "BUY"
            compliance = ls
            reasons_for = long_met
            reasons_against = [c for c in long_conds if c not in long_met]
            htf_align = daily_bullish
        else:
            direction = "SELL"
            compliance = ss
            reasons_for = short_met
            reasons_against = [c for c in short_conds if c not in short_met]
            htf_align = daily_bearish

        if direction == "BUY":
            entry = h1_close
            sl = middle - 1.5 * h1_atr
            risk = entry - sl
            tp1 = entry + 2 * risk
        else:
            entry = h1_close
            sl = middle + 1.5 * h1_atr
            risk = sl - entry
            tp1 = entry - 2 * risk

        if compliance < 0.67:
            missing = [c for c in (long_conds if direction == "BUY" else short_conds) if c not in reasons_for]
            return self._wait(direction,
                              f"Keltner break detected — waiting for pullback to midline {middle:.3f}",
                              missing, reasons_for, reasons_against,
                              entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 3, 0.8 if c2_long or c2_short else 0.4, htf_align, c2_long or c2_short)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 3, 0.8 if c2_long or c2_short else 0.4, htf_align, c2_long or c2_short)
        r1 = RiskAgent(1).evaluate(news, not htf_align, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, not htf_align, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.75, trend_alignment=0.8 if htf_align else 0.5,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

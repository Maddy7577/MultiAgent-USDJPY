"""S6: MACD + 200 EMA Trend-Following — cross below zero (long) / above zero (short)."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S6MacdEma200(BaseStrategy):
    STRATEGY_ID = 6
    STRATEGY_NAME = "MACD + 200 EMA"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES = ["H1", "H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        h1_close = ind.get("H1_close", price)
        h1_ema200 = ind.get("H1_ema200")
        h1_macd = ind.get("H1_macd")
        h1_atr = ind.get("H1_atr14", 0.2)
        h1_swing_low = ind.get("H1_swing_low")
        h1_swing_high = ind.get("H1_swing_high")

        if h1_ema200 is None:
            return self._no_trade(["H1 EMA200 not ready — need 200+ bars"])
        if h1_macd is None:
            return self._no_trade(["H1 MACD not ready"])

        macd_line = h1_macd["line"]
        macd_signal = h1_macd["signal"]

        # ── Long: price > EMA200, MACD bullish cross, cross below zero ──────
        c1_long = h1_close > h1_ema200
        c2_long = h1_macd["bullish_cross"]
        c3_long = macd_line < 0  # best setup: cross below zero line

        long_conds = [
            "H1 price > EMA200 (bullish regime)",
            "MACD bullish cross (line > signal)",
            "MACD cross below zero line (pullback in uptrend)",
        ]
        long_met = []
        if c1_long: long_met.append(long_conds[0])
        if c2_long: long_met.append(long_conds[1])
        if c3_long: long_met.append(long_conds[2])

        # ── Short: price < EMA200, MACD bearish cross, cross above zero ─────
        c1_short = h1_close < h1_ema200
        c2_short = h1_macd["bearish_cross"]
        c3_short = macd_line > 0

        short_conds = [
            "H1 price < EMA200 (bearish regime)",
            "MACD bearish cross (line < signal)",
            "MACD cross above zero line (retrace in downtrend)",
        ]
        short_met = []
        if c1_short: short_met.append(short_conds[0])
        if c2_short: short_met.append(short_conds[1])
        if c3_short: short_met.append(short_conds[2])

        ls = len(long_met) / 3
        ss = len(short_met) / 3

        if not c1_long and not c1_short:
            return self._no_trade(["Price straddling EMA200 — no clear regime"])

        if ls >= ss and c1_long:
            direction = "BUY"
            compliance = ls
            reasons_for = long_met
            reasons_against = [c for c in long_conds if c not in long_met]
        elif c1_short:
            direction = "SELL"
            compliance = ss
            reasons_for = short_met
            reasons_against = [c for c in short_conds if c not in short_met]
        else:
            return self._no_trade(["Regime not clear"])

        h1_df = self.ohlcv.get("H1")
        if direction == "BUY":
            recent_low = float(h1_df["low"].tail(5).min()) if h1_df is not None else h1_close - h1_atr
            entry = h1_close
            sl = recent_low - 0.2 * h1_atr
            risk = entry - sl
            tp1 = entry + 2 * risk
        else:
            recent_high = float(h1_df["high"].tail(5).max()) if h1_df is not None else h1_close + h1_atr
            entry = h1_close
            sl = recent_high + 0.2 * h1_atr
            risk = sl - entry
            tp1 = entry - 2 * risk

        if not (c2_long if direction == "BUY" else c2_short):
            return self._wait(direction,
                              "Waiting for MACD cross",
                              [c for c in (long_conds if direction == "BUY" else short_conds) if c not in reasons_for],
                              reasons_for, reasons_against,
                              entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = not (c1_long if direction == "BUY" else c1_short)

        in_zone = c3_long if direction == "BUY" else c3_short
        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 3, 0.7 if in_zone else 0.4, c1_long or c1_short, in_zone)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 3, 0.7 if in_zone else 0.4, c1_long or c1_short, in_zone)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.7, trend_alignment=1.0 if not htf_conflict else 0.2,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

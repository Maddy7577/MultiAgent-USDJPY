"""S10: 50/200 EMA Crossover Pullback — golden/death cross + first pullback."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S10EmaCrossover(BaseStrategy):
    STRATEGY_ID = 10
    STRATEGY_NAME = "50/200 EMA Crossover Pullback"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES = ["H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        h4_ema50 = ind.get("H4_ema50")
        h4_ema200 = ind.get("H4_ema200")
        h4_close = ind.get("H4_close", price)
        h4_atr = ind.get("H4_atr14", 0.5)
        h4_swing_low = ind.get("H4_swing_low")
        h4_swing_high = ind.get("H4_swing_high")
        golden = ind.get("H4_golden_cross", False)
        death = ind.get("H4_death_cross", False)
        crossed_recently = ind.get("H4_ema_crossed_recently", False)
        adx = ind.get("H4_adx14")

        if h4_ema200 is None:
            return self._no_trade(["H4 EMA200 not ready — need 200+ H4 bars"])

        if not crossed_recently and not golden and not death:
            return self._no_trade(["No golden/death cross detected in last 20 H4 bars"])

        if adx is not None and adx < 18:
            return self._no_trade([f"ADX {adx:.1f} < 18 — cross in flat market, low conviction"])

        if h4_ema50 > h4_ema200:
            direction = "BUY"
            at_pullback = (h4_close <= h4_ema50 * 1.002 or
                           (h4_swing_low is not None and abs(h4_close - h4_swing_low) < 0.5 * h4_atr))
            bullish_candle = h4_close > ind.get("H4_open", h4_close)
            conds = [
                ("H4 Golden Cross: EMA50 > EMA200", True),
                ("Cross occurred within 20 bars", crossed_recently or golden),
                ("Pullback to EMA50 or swing low", at_pullback),
                ("Bullish reversal at pullback", bullish_candle and at_pullback),
            ]
        else:
            direction = "SELL"
            at_pullback = (h4_close >= h4_ema50 * 0.998 or
                           (h4_swing_high is not None and abs(h4_close - h4_swing_high) < 0.5 * h4_atr))
            bearish_candle = h4_close < ind.get("H4_open", h4_close)
            conds = [
                ("H4 Death Cross: EMA50 < EMA200", True),
                ("Cross occurred within 20 bars", crossed_recently or death),
                ("Rally to EMA50 or swing high", at_pullback),
                ("Bearish reversal at pullback", bearish_candle and at_pullback),
            ]

        conditions_met = [name for name, met in conds if met]
        conditions_missed = [name for name, met in conds if not met]
        compliance = len(conditions_met) / 4

        if not at_pullback:
            return self._wait(direction,
                              f"Cross confirmed — wait for pullback to H4 EMA50 ({h4_ema50:.3f})",
                              conditions_missed, conditions_met, conditions_missed)

        if direction == "BUY":
            swing_ref = h4_swing_low or h4_close - 2 * h4_atr
            entry = h4_close
            sl = swing_ref - h4_atr
            risk = entry - sl
            tp1 = entry + 1.5 * risk
        else:
            swing_ref = h4_swing_high or h4_close + 2 * h4_atr
            entry = h4_close
            sl = swing_ref + h4_atr
            risk = sl - entry
            tp1 = entry - 1.5 * risk

        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(len(conditions_met), 4, 0.7, True, at_pullback)
        opp2 = OpportunityAgent(2).evaluate(len(conditions_met), 4, 0.7, True, at_pullback)
        r1 = RiskAgent(1).evaluate(news, False, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, False, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.7, trend_alignment=0.85,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=conditions_met, reasons_against=conditions_missed,
            evaluated_at=self.now,
        )

"""S7: ADX + DMI Trend-Strength Filter — regime classification + pullback entry."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S7AdxDmi(BaseStrategy):
    STRATEGY_ID = 7
    STRATEGY_NAME = "ADX + DMI Trend-Strength"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES = ["H4"]

    ADX_THRESHOLD = 25.0
    DI_SPREAD_MIN = 5.0

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        adx = ind.get("H4_adx14")
        plus_di = ind.get("H4_plus_di")
        minus_di = ind.get("H4_minus_di")
        h4_close = ind.get("H4_close", price)
        h4_ema20 = ind.get("H4_ema20")
        h4_atr = ind.get("H4_atr14", 0.5)

        if any(v is None for v in [adx, plus_di, minus_di, h4_ema20]):
            return self._no_trade(["ADX/DMI indicators not ready"])

        # ── Regime gate ──────────────────────────────────────────────────────
        if adx < self.ADX_THRESHOLD:
            return self._no_trade([f"ADX {adx:.1f} < {self.ADX_THRESHOLD} — ranging market, no trade"])

        di_spread = abs(plus_di - minus_di)
        if di_spread < self.DI_SPREAD_MIN:
            return self._no_trade([f"DI spread {di_spread:.1f} < {self.DI_SPREAD_MIN} — ambiguous direction"])

        # ── Direction ────────────────────────────────────────────────────────
        if plus_di > minus_di:
            direction = "BUY"
        else:
            direction = "SELL"

        # ── Entry conditions ─────────────────────────────────────────────────
        at_pullback = abs(h4_close - h4_ema20) <= 0.5 * h4_atr
        bullish_close = ind.get("H4_close", price) > ind.get("H4_open", price)
        bearish_close = ind.get("H4_close", price) < ind.get("H4_open", price)

        if direction == "BUY":
            conds = [
                (f"ADX {adx:.1f} > {self.ADX_THRESHOLD}", True),
                (f"+DI {plus_di:.1f} > -DI {minus_di:.1f}", True),
                ("Pullback to H4 EMA20", at_pullback),
                ("Bullish close at pullback", bullish_close and at_pullback),
            ]
        else:
            conds = [
                (f"ADX {adx:.1f} > {self.ADX_THRESHOLD}", True),
                (f"-DI {minus_di:.1f} > +DI {plus_di:.1f}", True),
                ("Rally to H4 EMA20", at_pullback),
                ("Bearish close at rally", bearish_close and at_pullback),
            ]

        conditions_met = [name for name, met in conds if met]
        conditions_missed = [name for name, met in conds if not met]
        compliance = len(conditions_met) / 4

        if not at_pullback:
            return self._wait(direction,
                              f"Wait for H4 pullback/rally to EMA20 ({h4_ema20:.3f})",
                              conditions_missed, conditions_met, conditions_missed)

        if direction == "BUY":
            entry = h4_close
            sl = entry - 1.5 * h4_atr
            tp1 = entry + 2 * h4_atr
            tp2 = entry + 3 * h4_atr
        else:
            entry = h4_close
            sl = entry + 1.5 * h4_atr
            tp1 = entry - 2 * h4_atr
            tp2 = entry - 3 * h4_atr

        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(len(conditions_met), 4, 0.7, True, at_pullback)
        opp2 = OpportunityAgent(2).evaluate(len(conditions_met), 4, 0.7, True, at_pullback)
        r1 = RiskAgent(1).evaluate(news, False, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, False, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.8, trend_alignment=0.9,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=conditions_met, reasons_against=conditions_missed,
            evaluated_at=self.now,
        )

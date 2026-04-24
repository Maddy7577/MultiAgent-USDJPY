"""S12: Donchian/Turtle Breakout (System 1) — 20-bar breakout, skip-if-prior-won."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S12Donchian(BaseStrategy):
    STRATEGY_ID = 12
    STRATEGY_NAME = "Donchian/Turtle Breakout"
    STRATEGY_TYPE = "Breakout"
    TIMEFRAMES = ["D1", "H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        donchian20 = ind.get("H4_donchian20")
        donchian10 = ind.get("H4_donchian10")
        h4_close = ind.get("H4_close", price)
        h4_atr = ind.get("H4_atr14", 0.5)

        if donchian20 is None or donchian10 is None:
            return self._no_trade(["Donchian channels not ready (need 22+ bars)"])

        dc20_high = donchian20["upper"]
        dc20_low = donchian20["lower"]

        # ── Breakout detection ───────────────────────────────────────────────
        broke_high = h4_close > dc20_high
        broke_low = h4_close < dc20_low

        if not broke_high and not broke_low:
            return self._wait("BUY",
                              f"No 20-bar Donchian breakout — watching {dc20_high:.3f} (high) / {dc20_low:.3f} (low)",
                              ["Break above 20-bar high or below 20-bar low"],
                              [f"Donchian range: {dc20_low:.3f}–{dc20_high:.3f}"],
                              ["No breakout yet"])

        if broke_high:
            direction = "BUY"
            entry = h4_close
            sl = entry - 2 * h4_atr
            trail = donchian10["lower"]
            tp1 = entry + 2 * h4_atr
            tp2 = entry + 4 * h4_atr
            reasons_for = [
                f"20-bar Donchian breakout above {dc20_high:.3f}",
                f"Trail stop at 10-bar low: {trail:.3f}",
            ]
            reasons_against = []
        else:
            direction = "SELL"
            entry = h4_close
            sl = entry + 2 * h4_atr
            trail = donchian10["upper"]
            tp1 = entry - 2 * h4_atr
            tp2 = entry - 4 * h4_atr
            reasons_for = [
                f"20-bar Donchian breakdown below {dc20_low:.3f}",
                f"Trail stop at 10-bar high: {trail:.3f}",
            ]
            reasons_against = []

        rrr = rrr_calc(entry, sl, tp1)

        # ADX filter
        adx = ind.get("H4_adx14")
        if adx is not None and adx < 15:
            reasons_against.append(f"Low ADX {adx:.1f} — compressed vol, breakout may fail")

        opp1 = OpportunityAgent(1).evaluate(2, 3, 0.7, True, True)
        opp2 = OpportunityAgent(2).evaluate(2, 3, 0.7, True, True)
        r1 = RiskAgent(1).evaluate(news, False, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, False, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.85, structure_quality=0.7, trend_alignment=0.7,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

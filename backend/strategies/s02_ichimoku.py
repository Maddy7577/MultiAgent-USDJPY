"""S2: Full Ichimoku Kinko Hyo System — 4-condition cloud system."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S2Ichimoku(BaseStrategy):
    STRATEGY_ID = 2
    STRATEGY_NAME = "Full Ichimoku System"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES = ["H4", "D1"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)
        ichi = ind.get("H4_ichimoku")
        atr_h4 = ind.get("H4_atr14", 0.5)

        if ichi is None:
            return self._no_trade(["Ichimoku requires 55+ H4 bars"])

        kumo_top = ichi["kumo_top"]
        kumo_bot = ichi["kumo_bottom"]
        tenkan = ichi["tenkan"]
        kijun = ichi["kijun"]
        h4_close = ind.get("H4_close", price)
        chikou = ichi["chikou"]
        close_26_ago = ichi["close_26_ago"]
        senkou_a_future = ichi["senkou_a_future"]
        senkou_b_future = ichi["senkou_b_future"]
        kumo_thick = ichi["kumo_thickness"]

        # Thin-cloud filter
        if kumo_thick < 0.5 * atr_h4:
            return self._no_trade(["Kumo too thin — whipsaw risk"])

        # ── Long conditions (all 4 must be true) ───────────────────────────
        c1_long = h4_close > kumo_top
        c2_long = ichi["tk_bullish_cross"] and tenkan > kumo_top
        c3_long = chikou > close_26_ago
        c4_long = senkou_a_future > senkou_b_future

        long_conds = [
            "Price above Kumo",
            "Bullish TK cross above cloud",
            "Chikou above price 26 bars ago",
            "Future Kumo bullish (Senkou A > B)",
        ]
        long_met = []
        if c1_long:
            long_met.append(long_conds[0])
        if c2_long:
            long_met.append(long_conds[1])
        if c3_long:
            long_met.append(long_conds[2])
        if c4_long:
            long_met.append(long_conds[3])

        # ── Short conditions ────────────────────────────────────────────────
        c1_short = h4_close < kumo_bot
        c2_short = ichi["tk_bearish_cross"] and tenkan < kumo_bot
        c3_short = chikou < close_26_ago
        c4_short = senkou_a_future < senkou_b_future

        short_conds = [
            "Price below Kumo",
            "Bearish TK cross below cloud",
            "Chikou below price 26 bars ago",
            "Future Kumo bearish (Senkou A < B)",
        ]
        short_met = []
        if c1_short:
            short_met.append(short_conds[0])
        if c2_short:
            short_met.append(short_conds[1])
        if c3_short:
            short_met.append(short_conds[2])
        if c4_short:
            short_met.append(short_conds[3])

        ls = len(long_met) / 4
        ss = len(short_met) / 4

        if ls == 0 and ss == 0:
            return self._no_trade(["Price inside Kumo — no directional signal"])

        if ls >= ss:
            direction = "BUY"
            reasons_for = long_met
            reasons_against = [c for c in long_conds if c not in long_met]
            compliance = ls
        else:
            direction = "SELL"
            reasons_for = short_met
            reasons_against = [c for c in short_conds if c not in short_met]
            compliance = ss

        if compliance < 0.75:
            return self._wait(direction,
                              f"Need all 4 Ichimoku conditions — {int(compliance*4)}/4 met",
                              [c for c in (long_conds if direction == "BUY" else short_conds)
                               if c not in reasons_for],
                              reasons_for, reasons_against)

        # ── Trade parameters ────────────────────────────────────────────────
        if direction == "BUY":
            entry = h4_close
            sl = kumo_bot - 0.5 * atr_h4
            risk = entry - sl
            tp1 = entry + 2 * risk
            tp2 = None
        else:
            entry = h4_close
            sl = kumo_top + 0.5 * atr_h4
            risk = sl - entry
            tp1 = entry - 2 * risk
            tp2 = None

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and not c1_long) or (direction == "SELL" and not c1_short)

        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 4, 0.7, c3_long or c3_short, c1_long or c1_short)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 4, 0.7, c3_long or c3_short, c1_long or c1_short)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread, news,
            rule_compliance=compliance, structure_quality=0.8, trend_alignment=1.0 if compliance == 1.0 else 0.6,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=tp2, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

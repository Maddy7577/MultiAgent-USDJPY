"""S16: RSI Mean Reversion — Mode A (range/ADX<20) and Mode B (trend pullback)."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S16RsiMR(BaseStrategy):
    STRATEGY_ID = 16
    STRATEGY_NAME = "RSI Mean Reversion"
    STRATEGY_TYPE = "Mean Reversion"
    TIMEFRAMES = ["H1", "H4"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        adx = ind.get("H4_adx14") or ind.get("H1_adx14")
        h1_close = ind.get("H1_close", price)
        h1_rsi = ind.get("H1_rsi14", 50)
        h1_rsi_prev = ind.get("H1_rsi14_prev", h1_rsi)
        h1_atr = ind.get("H1_atr14", 0.2)
        h1_ema200 = ind.get("H1_ema200")
        h4_ema200 = ind.get("H4_ema200")
        ema200 = h4_ema200 or h1_ema200

        ranging = adx is not None and adx < 20
        in_uptrend = ema200 is not None and h1_close > ema200
        in_downtrend = ema200 is not None and h1_close < ema200

        # ── Mode A: Counter-trend in range ──────────────────────────────────
        rsi_cross_above_30 = h1_rsi_prev < 30 and h1_rsi >= 30
        rsi_cross_below_70 = h1_rsi_prev > 70 and h1_rsi <= 70

        if ranging and rsi_cross_above_30:
            direction = "BUY"
            mode = "A"
            entry = h1_close
            sl = entry - 1.5 * h1_atr
            tp1 = entry + h1_atr
            reasons_for = [
                f"Mode A: ADX {adx:.1f} < 20 (ranging)",
                f"RSI crossed above 30 from {h1_rsi_prev:.0f} → {h1_rsi:.0f}",
            ]
            reasons_against = []

        elif ranging and rsi_cross_below_70:
            direction = "SELL"
            mode = "A"
            entry = h1_close
            sl = entry + 1.5 * h1_atr
            tp1 = entry - h1_atr
            reasons_for = [
                f"Mode A: ADX {adx:.1f} < 20 (ranging)",
                f"RSI crossed below 70 from {h1_rsi_prev:.0f} → {h1_rsi:.0f}",
            ]
            reasons_against = []

        # ── Mode B: Pullback in trend ────────────────────────────────────────
        elif in_uptrend and h1_rsi_prev < 40 and h1_rsi >= 40:
            direction = "BUY"
            mode = "B"
            h1_swing_low = ind.get("H1_swing_low")
            entry = h1_close
            sl = (h1_swing_low - 0.5 * h1_atr) if h1_swing_low else entry - 1.5 * h1_atr
            risk = entry - sl
            tp1 = entry + 1.5 * risk
            reasons_for = [
                f"Mode B: Price above EMA200 (uptrend)",
                f"RSI pullback to 40 then recovered: {h1_rsi_prev:.0f} → {h1_rsi:.0f}",
            ]
            reasons_against = []

        elif in_downtrend and h1_rsi_prev > 60 and h1_rsi <= 60:
            direction = "SELL"
            mode = "B"
            h1_swing_high = ind.get("H1_swing_high")
            entry = h1_close
            sl = (h1_swing_high + 0.5 * h1_atr) if h1_swing_high else entry + 1.5 * h1_atr
            risk = sl - entry
            tp1 = entry - 1.5 * risk
            reasons_for = [
                f"Mode B: Price below EMA200 (downtrend)",
                f"RSI bounce from 60 short: {h1_rsi_prev:.0f} → {h1_rsi:.0f}",
            ]
            reasons_against = []

        else:
            current_state = []
            if ranging:
                current_state.append(f"Ranging (ADX {adx:.1f}) — RSI: {h1_rsi:.0f}, no cross at 30/70")
            elif in_uptrend:
                current_state.append(f"Uptrend — RSI {h1_rsi:.0f}, waiting for 40 level crossback")
            elif in_downtrend:
                current_state.append(f"Downtrend — RSI {h1_rsi:.0f}, waiting for 60 level crossback")
            else:
                current_state.append("No clear regime — EMA200 unavailable or trend unclear")
            return self._no_trade(current_state)

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (mode == "A")  # mean reversion is inherently counter-trend

        opp1 = OpportunityAgent(1).evaluate(2, 3, 0.75, mode == "B", True, extra_factors=0.3)
        opp2 = OpportunityAgent(2).evaluate(2, 3, 0.75, mode == "B", True, extra_factors=0.3)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.85, structure_quality=0.7, trend_alignment=0.8 if mode == "B" else 0.2,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

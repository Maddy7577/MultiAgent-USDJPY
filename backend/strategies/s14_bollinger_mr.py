"""S14: Bollinger Band Mean Reversion — ADX < 25 gate, band-touch + confirmation candle."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S14BollingerMR(BaseStrategy):
    STRATEGY_ID = 14
    STRATEGY_NAME = "Bollinger Band Mean Reversion"
    STRATEGY_TYPE = "Mean Reversion"
    TIMEFRAMES = ["H1", "H4"]

    ADX_MAX = 25.0

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        adx = ind.get("H4_adx14") or ind.get("H1_adx14")
        if adx is None:
            return self._no_trade(["ADX not ready — regime filter unavailable"])

        # ── Regime gate ──────────────────────────────────────────────────────
        if adx >= self.ADX_MAX:
            return self._no_trade([f"ADX {adx:.1f} ≥ {self.ADX_MAX} — trending market, Bollinger MR unreliable"])

        bb = ind.get("H1_bb")
        if bb is None:
            return self._no_trade(["Bollinger Bands not ready"])

        h1_df = self.ohlcv.get("H1")
        h1_close = ind.get("H1_close", price)
        h1_open = ind.get("H1_open", h1_close)
        h1_atr = ind.get("H1_atr14", 0.2)
        h1_rsi = ind.get("H1_rsi14", 50)
        h1_prev_close = ind.get("H1_prev_close", h1_close)

        upper = bb["upper"]
        middle = bb["middle"]
        lower = bb["lower"]

        prev_high = float(h1_df.iloc[-2]["high"]) if h1_df is not None and len(h1_df) >= 2 else h1_close
        prev_low = float(h1_df.iloc[-2]["low"]) if h1_df is not None and len(h1_df) >= 2 else h1_close

        # ── Long setup ───────────────────────────────────────────────────────
        prev_wicked_below = prev_low < lower
        curr_bullish = h1_close > h1_open and h1_close > lower
        rsi_rising = h1_rsi < 35

        # ── Short setup ──────────────────────────────────────────────────────
        prev_wicked_above = prev_high > upper
        curr_bearish = h1_close < h1_open and h1_close < upper
        rsi_falling = h1_rsi > 65

        if prev_wicked_below and curr_bullish:
            direction = "BUY"
            entry = h1_close
            sl = prev_low - 0.5 * h1_atr
            tp1 = middle
            tp2 = upper
            reasons_for = [
                f"Prior bar wicked below lower BB ({lower:.3f})",
                "Confirmation bar closed bullish within band",
                f"ADX {adx:.1f} < {self.ADX_MAX} — ranging regime",
                f"RSI {h1_rsi:.0f} — oversold" if rsi_rising else f"RSI {h1_rsi:.0f}",
            ]
            reasons_against = []

        elif prev_wicked_above and curr_bearish:
            direction = "SELL"
            entry = h1_close
            sl = prev_high + 0.5 * h1_atr
            tp1 = middle
            tp2 = lower
            reasons_for = [
                f"Prior bar wicked above upper BB ({upper:.3f})",
                "Confirmation bar closed bearish within band",
                f"ADX {adx:.1f} < {self.ADX_MAX} — ranging regime",
                f"RSI {h1_rsi:.0f} — overbought" if rsi_falling else f"RSI {h1_rsi:.0f}",
            ]
            reasons_against = []

        else:
            reasons_for = [f"ADX {adx:.1f} — ranging regime", f"BB: {lower:.3f}–{middle:.3f}–{upper:.3f}"]
            missed = []
            if not prev_wicked_below and not prev_wicked_above:
                missed.append("No band wick (price not touching band extremes)")
            elif prev_wicked_below and not curr_bullish:
                missed.append("Band wick detected but no bullish confirmation candle yet")
            elif prev_wicked_above and not curr_bearish:
                missed.append("Band wick detected but no bearish confirmation candle yet")
            proj_sl = round(lower - 0.5 * h1_atr, 3)
            return self._wait("BUY",
                              f"BB MR: wait for band touch + confirmation. Bands: {lower:.3f}–{upper:.3f}",
                              missed, reasons_for, missed,
                              entry=round(lower, 3), sl=proj_sl, tp1=round(middle, 3))

        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(4, 4, 0.8, False, True, extra_factors=0.3)
        opp2 = OpportunityAgent(2).evaluate(4, 4, 0.8, False, True, extra_factors=0.3)
        r1 = RiskAgent(1).evaluate(news, True, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, True, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.9, structure_quality=0.8, trend_alignment=0.0,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

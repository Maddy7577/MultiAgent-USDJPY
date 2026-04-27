"""S11: Asian Session Range Fade — mean reversion, regime filter mandatory."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S11AsianFade(BaseStrategy):
    STRATEGY_ID = 11
    STRATEGY_NAME = "Asian Session Range Fade"
    STRATEGY_TYPE = "Mean Reversion"
    TIMEFRAMES = ["M30"]

    RANGE_MIN_PIPS = 20.0
    RANGE_MAX_PIPS = 60.0
    ADX_THRESHOLD = 20.0
    RSI_LOW = 30
    RSI_HIGH = 70

    def evaluate(self) -> StrategyResult:
        # ── Session gate: only 00:00–06:30 GMT ──────────────────────────────
        utc_hour = self.ind.get("utc_hour", 12)
        utc_min = self.ind.get("utc_minute", 0)
        total_min = utc_hour * 60 + utc_min
        in_window = total_min < 6 * 60 + 30

        if not in_window:
            return self._no_trade([
                f"Outside Asian session window (UTC {utc_hour:02d}:{utc_min:02d}) — valid 00:00-06:30 GMT"
            ])

        # ── Regime gate: ADX < 20 (ranging market) ──────────────────────────
        adx_h1 = self.ind.get("H1_adx14")
        if adx_h1 is None:
            return self._no_trade(["H1 ADX not ready"])
        if adx_h1 >= self.ADX_THRESHOLD:
            return self._no_trade([f"ADX(H1) {adx_h1:.1f} ≥ {self.ADX_THRESHOLD} — trending regime, skip MR"])

        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)
        h1_df = self.ohlcv.get("H1")
        h1_rsi = ind.get("H1_rsi14", 50)
        h1_atr = ind.get("H1_atr14", 0.2)

        # Build range from first 2 H1 bars of Asian session (proxy: last 2-4 bars)
        if h1_df is None or len(h1_df) < 4:
            return self._no_trade(["Not enough H1 bars"])

        asian_bars = h1_df.tail(4).head(2)
        range_high = float(asian_bars["high"].max())
        range_low = float(asian_bars["low"].min())
        range_width = range_high - range_low
        range_pips = range_width * 100
        h1_close = ind.get("H1_close", price)

        if range_pips < self.RANGE_MIN_PIPS:
            return self._no_trade([f"Asian range {range_pips:.0f} pips too narrow (min {self.RANGE_MIN_PIPS})"])
        if range_pips > self.RANGE_MAX_PIPS:
            return self._no_trade([f"Asian range {range_pips:.0f} pips too wide (trending) — skip"])

        pip = 0.01
        at_low = h1_close <= range_low + 5 * pip
        at_high = h1_close >= range_high - 5 * pip
        rsi_oversold = h1_rsi < self.RSI_LOW
        rsi_overbought = h1_rsi > self.RSI_HIGH
        bullish_candle = h1_close > ind.get("H1_open", h1_close)
        bearish_candle = h1_close < ind.get("H1_open", h1_close)

        # ── Long setup: price at range low, RSI oversold ─────────────────────
        if at_low and rsi_oversold and bullish_candle:
            direction = "BUY"
            entry = h1_close
            sl = range_low - 10 * pip
            midrange = (range_high + range_low) / 2
            tp1 = midrange
            tp2 = range_high - 5 * pip
            reasons_for = [
                f"Price at Asian range low ({range_low:.3f})",
                f"RSI oversold ({h1_rsi:.0f} < {self.RSI_LOW})",
                "Bullish reversal candle",
                f"ADX {adx_h1:.1f} — ranging regime confirmed",
            ]
            reasons_against = []

        elif at_high and rsi_overbought and bearish_candle:
            direction = "SELL"
            entry = h1_close
            sl = range_high + 10 * pip
            midrange = (range_high + range_low) / 2
            tp1 = midrange
            tp2 = range_low + 5 * pip
            reasons_for = [
                f"Price at Asian range high ({range_high:.3f})",
                f"RSI overbought ({h1_rsi:.0f} > {self.RSI_HIGH})",
                "Bearish reversal candle",
                f"ADX {adx_h1:.1f} — ranging regime confirmed",
            ]
            reasons_against = []

        else:
            reasons_for = [f"ADX {adx_h1:.1f} — ranging regime",
                           f"Asian range: {range_pips:.0f} pips ({range_low:.3f}–{range_high:.3f})"]
            if not at_low and not at_high:
                proj_sl = round(range_low - 10 * pip, 3)
                proj_tp1 = round((range_high + range_low) / 2, 3)
                return self._wait("BUY",
                                  f"Price mid-range — wait for touch of {range_low:.3f} (RSI<30) or {range_high:.3f} (RSI>70)",
                                  ["Price at range extreme with RSI confirmation"],
                                  reasons_for, ["Price not at range extreme"],
                                  entry=round(range_low, 3), sl=proj_sl, tp1=proj_tp1)
            return self._no_trade([
                "Range conditions not fully met",
                f"RSI: {h1_rsi:.0f} | At low: {at_low} | At high: {at_high}"
            ])

        rrr = rrr_calc(entry, sl, tp1)

        opp1 = OpportunityAgent(1).evaluate(4, 4, 0.8, False, True, extra_factors=0.5)
        opp2 = OpportunityAgent(2).evaluate(4, 4, 0.8, False, True, extra_factors=0.5)
        r1 = RiskAgent(1).evaluate(news, True, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, True, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.9, structure_quality=0.85, trend_alignment=0.0,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

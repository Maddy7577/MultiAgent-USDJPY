"""S1: Multi-Timeframe Trend Alignment — D + H4 + H1 fractal structure."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S1MtfTrend(BaseStrategy):
    STRATEGY_ID = 1
    STRATEGY_NAME = "Multi-Timeframe Trend Alignment"
    STRATEGY_TYPE = "Trend"
    TIMEFRAMES = ["D1", "H4", "H1"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("D1", "H4", "H1"):
            return self._no_trade(["Insufficient OHLCV data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)
        atr_h1 = ind.get("H1_atr14", 0.5)
        atr_h4 = ind.get("H4_atr14", 1.0)

        d_close = ind.get("D1_close", price)
        d_ema50 = ind.get("D1_ema50")
        d_ema200 = ind.get("D1_ema200")
        h4_close = ind.get("H4_close", price)
        h4_ema20 = ind.get("H4_ema20")
        h4_swing_low = ind.get("H4_swing_low")
        h4_swing_high = ind.get("H4_swing_high")
        h1_close = ind.get("H1_close", price)
        h1_ema20 = ind.get("H1_ema20")
        h1_macd = ind.get("H1_macd")
        h1_swing_low = ind.get("H1_swing_low")
        h1_swing_high = ind.get("H1_swing_high")

        if any(v is None for v in [d_ema50, d_ema200, h4_ema20, h4_swing_low, h1_ema20, h1_macd]):
            return self._no_trade(["Required indicators not available (need 200+ bars)"])

        # ── Long conditions ─────────────────────────────────────────────────
        long_conds = []
        long_met = []

        c1_long = d_close > d_ema50 and d_ema50 > d_ema200
        long_conds.append("Daily bullish: close > EMA50 > EMA200")
        if c1_long:
            long_met.append("Daily bullish: close > EMA50 > EMA200")

        c2_long = (abs(h4_close - h4_ema20) <= 0.3 * atr_h4 and
                   h4_swing_low is not None and h4_close > h4_swing_low)
        long_conds.append("H4 pullback near EMA20 with higher-low structure")
        if c2_long:
            long_met.append("H4 pullback near EMA20 with higher-low structure")

        c3_long = h1_macd["bullish_cross"] and h1_close > h1_ema20
        long_conds.append("H1 MACD bullish cross above EMA20")
        if c3_long:
            long_met.append("H1 MACD bullish cross above EMA20")

        c4_long = ind.get("H1_close", price) > ind.get("H1_open", price)
        long_conds.append("H1 confirmation candle bullish")
        if c4_long:
            long_met.append("H1 confirmation candle bullish")

        # ── Short conditions ────────────────────────────────────────────────
        short_conds = []
        short_met = []

        c1_short = d_close < d_ema50 and d_ema50 < d_ema200
        short_conds.append("Daily bearish: close < EMA50 < EMA200")
        if c1_short:
            short_met.append("Daily bearish: close < EMA50 < EMA200")

        c2_short = (abs(h4_close - h4_ema20) <= 0.3 * atr_h4 and
                    h4_swing_high is not None and h4_close < h4_swing_high)
        short_conds.append("H4 rally near EMA20 with lower-high structure")
        if c2_short:
            short_met.append("H4 rally near EMA20 with lower-high structure")

        c3_short = h1_macd["bearish_cross"] and h1_close < h1_ema20
        short_conds.append("H1 MACD bearish cross below EMA20")
        if c3_short:
            short_met.append("H1 MACD bearish cross below EMA20")

        c4_short = ind.get("H1_close", price) < ind.get("H1_open", price)
        short_conds.append("H1 confirmation candle bearish")
        if c4_short:
            short_met.append("H1 confirmation candle bearish")

        # ── Direction selection ─────────────────────────────────────────────
        ls = len(long_met) / len(long_conds)
        ss = len(short_met) / len(short_conds)

        if ls == 0 and ss == 0:
            return self._no_trade(["No trend alignment on any timeframe"])

        if ls > ss:
            direction = "BUY"
            conditions_met = len(long_met)
            conditions_total = len(long_conds)
            reasons_for = long_met
            reasons_against = [c for c in long_conds if c not in long_met]
            swing_ref = h1_swing_low or (h1_close - 1.5 * atr_h1)
        else:
            direction = "SELL"
            conditions_met = len(short_met)
            conditions_total = len(short_conds)
            reasons_for = short_met
            reasons_against = [c for c in short_conds if c not in short_met]
            swing_ref = h1_swing_high or (h1_close + 1.5 * atr_h1)

        # ── Trade parameters ────────────────────────────────────────────────
        if direction == "BUY":
            entry = h1_close
            sl = min(swing_ref, entry - 1.5 * atr_h1)
            risk = entry - sl
            tp1 = entry + risk
            tp2 = entry + 2 * risk
        else:
            entry = h1_close
            sl = max(swing_ref, entry + 1.5 * atr_h1)
            risk = sl - entry
            tp1 = entry - risk
            tp2 = entry - 2 * risk

        # ── WAIT check ──────────────────────────────────────────────────────
        compliance = conditions_met / conditions_total
        if compliance < 0.75:
            missing = [c for c in (long_conds if direction == "BUY" else short_conds)
                       if c not in reasons_for]
            return self._wait(direction,
                              f"Waiting for H1 MACD cross and H4 pullback to EMA20",
                              missing, reasons_for, reasons_against,
                              entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        rrr = rrr_calc(entry, sl, tp1)

        htf_conflict = (direction == "BUY" and not c1_long) or (direction == "SELL" and not c1_short)

        opp_agent1 = OpportunityAgent(1)
        opp_agent2 = OpportunityAgent(2)
        risk_agent1 = RiskAgent(1)
        risk_agent2 = RiskAgent(2)

        eq = 0.8 if c3_long or c3_short else 0.4
        in_zone = c2_long or c2_short

        opp1 = opp_agent1.evaluate(conditions_met, conditions_total, eq, c1_long or c1_short, in_zone)
        opp2 = opp_agent2.evaluate(conditions_met, conditions_total, eq, c1_long or c1_short, in_zone)
        r1 = risk_agent1.evaluate(news, htf_conflict, rrr, spread, price, direction)
        r2 = risk_agent2.evaluate(news, htf_conflict, rrr, spread, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread, news,
            rule_compliance=compliance,
            structure_quality=0.8 if in_zone else 0.5,
            trend_alignment=1.0 if c1_long or c1_short else 0.3,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

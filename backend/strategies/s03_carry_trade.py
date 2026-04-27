"""S3: Carry-Trade Pullback — Fed-BoJ spread macro gate + H4 Fib pullback."""
from __future__ import annotations

from backend.strategies.base_strategy import (
    BaseStrategy, StrategyResult, rrr_calc, is_bullish_engulfing, is_bearish_engulfing,
    is_bullish_pin_bar,
)
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate
from backend import config


class S3CarryTrade(BaseStrategy):
    STRATEGY_ID = 3
    STRATEGY_NAME = "Carry-Trade Pullback"
    STRATEGY_TYPE = "Hybrid"
    TIMEFRAMES = ["D1", "H4"]

    # Fed-BoJ spread threshold
    SPREAD_MIN = 2.5

    def evaluate(self) -> StrategyResult:
        if not self._has_data("D1", "H4"):
            return self._no_trade(["Insufficient OHLCV data"])

        ctx = self.ctx
        ind = self.ind
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        fed_rate = ctx.get("fed_rate") or 3.875
        boj_rate = ctx.get("boj_rate") or getattr(config, "BOJ_RATE", 0.75)
        rate_spread = fed_rate - boj_rate

        # ── Macro gate (CRITICAL — must pass first) ─────────────────────────
        if rate_spread < self.SPREAD_MIN:
            return self._no_trade([
                f"Fed-BoJ spread {rate_spread:.2f}% below threshold {self.SPREAD_MIN}% — no carry bias"
            ])

        h4_df = self.ohlcv.get("H4")
        d_close = ind.get("D1_close", price)
        d_ema50 = ind.get("D1_ema50")
        d_ema200 = ind.get("D1_ema200")
        h4_close = ind.get("H4_close", price)
        h4_ema20 = ind.get("H4_ema20")
        h4_ema50 = ind.get("H4_ema50")
        h4_rsi = ind.get("H4_rsi14")
        h4_atr = ind.get("H4_atr14", 0.5)
        h4_swing_low = ind.get("H4_swing_low")
        h4_swing_high = ind.get("H4_swing_high")

        if any(v is None for v in [d_ema50, d_ema200, h4_ema20, h4_rsi]):
            return self._no_trade(["Required D1/H4 indicators not ready"])

        # ── Long conditions (carry trade is inherently biased long) ─────────
        c1 = d_close > d_ema50 and d_ema50 > d_ema200
        c2 = (h4_ema20 is not None and
              abs(h4_close - h4_ema20) <= 0.5 * h4_atr)  # at H4 EMA20/50 zone
        c3 = (h4_df is not None and
              (is_bullish_engulfing(h4_df) or is_bullish_pin_bar(h4_df.iloc[-1])))
        c4 = h4_rsi is not None and 40 <= h4_rsi <= 55

        long_conds = [
            "Daily uptrend: close > EMA50 > EMA200",
            "H4 pullback to EMA20 zone",
            "Bullish reversal candle at pullback",
            "H4 RSI in 40-55 range (not oversold)",
        ]
        long_met = []
        if c1: long_met.append(long_conds[0])
        if c2: long_met.append(long_conds[1])
        if c3: long_met.append(long_conds[2])
        if c4: long_met.append(long_conds[3])

        compliance = len(long_met) / 4

        reasons_for = [f"Fed-BoJ spread: {rate_spread:.2f}% > {self.SPREAD_MIN}%"] + long_met
        reasons_against = [c for c in long_conds if c not in long_met]

        if compliance < 0.5:
            return self._no_trade(["Less than 2 of 4 carry-trade conditions met"] + reasons_against)

        direction = "BUY"
        entry = h4_close
        sl = (h4_swing_low or entry - 1.5 * h4_atr) - 0.5 * h4_atr
        sl = min(entry - 1.5 * h4_atr, sl)
        risk = entry - sl
        tp1 = entry + 2 * risk
        tp2 = entry + 3 * risk

        if compliance < 0.75:
            return self._wait("BUY",
                              "Wait for H4 pullback to EMA20 with bullish reversal + RSI 40-55",
                              [c for c in long_conds if c not in long_met],
                              reasons_for, reasons_against,
                              entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3))
        rrr = rrr_calc(entry, sl, tp1)

        htf_conflict = not c1

        opp1 = OpportunityAgent(1).evaluate(len(long_met), 4, 0.75 if c3 else 0.4, c1, c2)
        opp2 = OpportunityAgent(2).evaluate(len(long_met), 4, 0.75 if c3 else 0.4, c1, c2)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction,
                                   ["VIX risk — check risk-off environment"] if ctx.get("vix", 0) > 25 else [])
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.7 if c3 else 0.5, trend_alignment=1.0 if c1 else 0.3,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

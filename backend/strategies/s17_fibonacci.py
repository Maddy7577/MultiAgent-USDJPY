"""S17: Fibonacci 50%/61.8% Pullback — golden pocket retracement with candle confirm."""
from __future__ import annotations

from backend.strategies.base_strategy import (
    BaseStrategy, StrategyResult, rrr_calc, detect_impulse_leg, fibonacci_levels,
    is_bullish_engulfing, is_bearish_engulfing, is_bullish_pin_bar, is_bearish_pin_bar,
)
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S17Fibonacci(BaseStrategy):
    STRATEGY_ID = 17
    STRATEGY_NAME = "Fibonacci 50/61.8 Pullback"
    STRATEGY_TYPE = "Retracement"
    TIMEFRAMES = ["H4", "D1"]

    def evaluate(self) -> StrategyResult:
        if not self._has_data("H4"):
            return self._no_trade(["Insufficient H4 data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        h4_df = self.ohlcv.get("H4")
        h4_close = ind.get("H4_close", price)
        h4_atr = ind.get("H4_atr14", 0.5)
        d_close = ind.get("D1_close", price)
        d_ema50 = ind.get("D1_ema50")

        impulse = detect_impulse_leg(h4_df, lookback=50, min_pips=100)
        if impulse is None:
            return self._no_trade(["No clear H4 impulse leg detected (need 100+ pips, clean structure)"])

        fibs = fibonacci_levels(impulse)
        direction_impulse = impulse["direction"]

        if direction_impulse == "UP":
            fib_50 = fibs["ret_50.0"]
            fib_618 = fibs["ret_61.8"]
            fib_786 = fibs["ret_78.6"]
            in_golden_pocket = fib_618 <= h4_close <= fib_50
            direction = "BUY"
            reversal_candle = (is_bullish_engulfing(h4_df) or
                               (h4_df is not None and len(h4_df) > 0 and is_bullish_pin_bar(h4_df.iloc[-1])))
            entry_val = h4_close
            sl = fib_786 - 0.2 * h4_atr
            tp1 = impulse["high"]
            tp2 = fibs.get("ext_127.2", impulse["high"] + 0.272 * impulse["range"])
            tp3 = fibs.get("ext_161.8", impulse["high"] + 0.618 * impulse["range"])
        else:
            fib_50 = fibs["ret_50.0"]
            fib_618 = fibs["ret_61.8"]
            fib_786 = fibs["ret_78.6"]
            in_golden_pocket = fib_50 >= h4_close >= fib_618
            direction = "SELL"
            reversal_candle = (is_bearish_engulfing(h4_df) or
                               (h4_df is not None and len(h4_df) > 0 and is_bearish_pin_bar(h4_df.iloc[-1])))
            entry_val = h4_close
            sl = fib_786 + 0.2 * h4_atr
            tp1 = impulse["low"]
            tp2 = fibs.get("ext_127.2", impulse["low"] - 0.272 * impulse["range"])
            tp3 = fibs.get("ext_161.8", impulse["low"] - 0.618 * impulse["range"])

        d_aligned = (d_ema50 is not None and
                     ((direction == "BUY" and d_close > d_ema50) or
                      (direction == "SELL" and d_close < d_ema50)))

        conds = [
            (f"Clear H4 impulse: {impulse['range']*100:.0f} pips", True),
            (f"Price in golden pocket (50–61.8%): {fib_618:.3f}–{fib_50:.3f}", in_golden_pocket),
            ("Reversal candle at zone", reversal_candle),
            ("Daily trend aligned with direction", d_aligned),
        ]
        reasons_for = [name for name, met in conds if met]
        reasons_against = [name for name, met in conds if not met]
        compliance = len(reasons_for) / 4

        if not in_golden_pocket:
            return self._wait(direction,
                              f"Wait for pullback to golden pocket {fib_618:.3f}–{fib_50:.3f}",
                              ["Price in 50-61.8% Fib zone", "Reversal candle at zone"],
                              reasons_for, reasons_against,
                              entry=round(fib_618, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        if not reversal_candle:
            return self._wait(direction,
                              f"In golden pocket — waiting for reversal candle",
                              ["Reversal candle at Fib zone"],
                              reasons_for, reasons_against,
                              entry=round(entry_val, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        rrr = rrr_calc(entry_val, sl, tp1)
        htf_conflict = not d_aligned

        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 4, 0.85, d_aligned, in_golden_pocket)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 4, 0.85, d_aligned, in_golden_pocket)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.85, trend_alignment=0.9 if d_aligned else 0.5,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry_val, 3), sl=round(sl, 3), tp1=round(tp1, 3),
            tp2=round(tp2, 3), tp3=round(tp3, 3),
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

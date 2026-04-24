"""S5: Confluence System — trend + S/R + candle + RSI (3 of 4 required)."""
from __future__ import annotations

from backend.strategies.base_strategy import (
    BaseStrategy, StrategyResult, rrr_calc, is_bullish_engulfing, is_bearish_engulfing,
    is_bullish_pin_bar, is_bearish_pin_bar,
)
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate

_KEY_LEVELS = [145.0, 148.0, 150.0, 152.0, 155.0, 160.0]


def _nearest_level(price: float, tolerance_pips: float = 50) -> float | None:
    tol = tolerance_pips * 0.01
    for lv in sorted(_KEY_LEVELS, key=lambda x: abs(x - price)):
        if abs(price - lv) < tol:
            return lv
    return None


class S5Confluence(BaseStrategy):
    STRATEGY_ID = 5
    STRATEGY_NAME = "Confluence System"
    STRATEGY_TYPE = "Multi-Signal"
    TIMEFRAMES = ["D1", "H4"]

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
        h4_rsi = ind.get("H4_rsi14", 50)
        h4_rsi_prev = ind.get("H4_rsi14_prev", h4_rsi)
        d_close = ind.get("D1_close", price)
        d_ema50 = ind.get("D1_ema50")
        d_ema200 = ind.get("D1_ema200")

        nearest_lv = _nearest_level(h4_close)

        # ── Long score (3 of 4) ─────────────────────────────────────────────
        la = d_ema50 is not None and d_ema200 is not None and d_close > d_ema50 and d_ema50 > d_ema200
        lb = nearest_lv is not None and abs(h4_close - nearest_lv) < 0.3 * h4_atr
        lc = h4_df is not None and (is_bullish_engulfing(h4_df) or
                                     (len(h4_df) > 0 and is_bullish_pin_bar(h4_df.iloc[-1])))
        # Bullish RSI divergence: simplify to RSI < 40 rising
        ld = h4_rsi < 40 and h4_rsi > h4_rsi_prev

        long_items = [
            ("Daily uptrend: close > EMA50 > EMA200", la),
            (f"Price at key level {nearest_lv}", lb),
            ("Bullish reversal candle on H4", lc),
            ("Bullish RSI condition (< 40, rising)", ld),
        ]
        long_score = sum(1 for _, met in long_items if met)
        long_met = [name for name, met in long_items if met]

        # ── Short score (3 of 4) ────────────────────────────────────────────
        sa = d_ema50 is not None and d_ema200 is not None and d_close < d_ema50 and d_ema50 < d_ema200
        sb = nearest_lv is not None and abs(h4_close - nearest_lv) < 0.3 * h4_atr
        sc = h4_df is not None and (is_bearish_engulfing(h4_df) or
                                     (len(h4_df) > 0 and is_bearish_pin_bar(h4_df.iloc[-1])))
        sd = h4_rsi > 60 and h4_rsi < h4_rsi_prev

        short_items = [
            ("Daily downtrend: close < EMA50 < EMA200", sa),
            (f"Price at key level {nearest_lv}", sb),
            ("Bearish reversal candle on H4", sc),
            ("Bearish RSI condition (> 60, falling)", sd),
        ]
        short_score = sum(1 for _, met in short_items if met)
        short_met = [name for name, met in short_items if met]

        if long_score < 2 and short_score < 2:
            return self._no_trade(["Less than 2 confluence factors - insufficient signal",
                                   f"No key level within 50 pips" if nearest_lv is None else f"Near level: {nearest_lv}"])

        if long_score >= short_score and long_score >= 2:
            direction = "BUY"
            compliance = long_score / 4
            reasons_for = long_met
            reasons_against = [n for n, met in long_items if not met]
        else:
            direction = "SELL"
            compliance = short_score / 4
            reasons_for = short_met
            reasons_against = [n for n, met in short_items if not met]

        if (direction == "BUY" and long_score < 3) or (direction == "SELL" and short_score < 3):
            return self._wait(direction,
                              f"Need ≥3/4 confluence factors — {long_score if direction == 'BUY' else short_score}/4 met",
                              [n for n, met in (long_items if direction == "BUY" else short_items) if not met],
                              reasons_for, reasons_against)

        if direction == "BUY":
            entry = h4_close
            sl = (nearest_lv - h4_atr) if nearest_lv else (entry - 1.5 * h4_atr)
            risk = entry - sl
            tp1 = entry + 2 * risk
            tp2 = entry + 3 * risk
        else:
            entry = h4_close
            sl = (nearest_lv + h4_atr) if nearest_lv else (entry + 1.5 * h4_atr)
            risk = sl - entry
            tp1 = entry - 2 * risk
            tp2 = entry - 3 * risk

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and not la) or (direction == "SELL" and not sa)

        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 4, 0.8 if lb else 0.4, la or sa, lb)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 4, 0.8 if lb else 0.4, la or sa, lb)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.8 if lb and lc else 0.5, trend_alignment=1.0 if la or sa else 0.3,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

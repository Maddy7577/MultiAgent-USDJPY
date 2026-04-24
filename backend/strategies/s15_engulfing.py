"""S15: Engulfing Candle at Key Level — Bulkowski 79% reversal rate framework."""
from __future__ import annotations

from backend.strategies.base_strategy import (
    BaseStrategy, StrategyResult, rrr_calc, is_bullish_engulfing, is_bearish_engulfing,
)
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate

_KEY_LEVELS = [145.0, 148.0, 150.0, 152.0, 155.0, 160.0]


def _nearest_level_distance(price: float) -> tuple[float | None, float]:
    """Returns (level, distance_pips)."""
    best = None
    best_dist = float("inf")
    for lv in _KEY_LEVELS:
        d = abs(price - lv) * 100
        if d < best_dist:
            best_dist = d
            best = lv
    return best, best_dist


class S15Engulfing(BaseStrategy):
    STRATEGY_ID = 15
    STRATEGY_NAME = "Engulfing at Key Level"
    STRATEGY_TYPE = "Price Action"
    TIMEFRAMES = ["H4", "D1"]

    LEVEL_TOUCH_PIPS = 30.0

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

        nearest_lv, dist_pips = _nearest_level_distance(h4_close)
        at_level = dist_pips <= self.LEVEL_TOUCH_PIPS

        bullish_eng = ind.get("H4_bullish_engulfing", False)
        bearish_eng = ind.get("H4_bearish_engulfing", False)

        if not at_level:
            return self._no_trade([
                f"Price not at key level (nearest: {nearest_lv} — {dist_pips:.0f} pips away)"
            ])

        if not bullish_eng and not bearish_eng:
            return self._wait("BUY",
                              f"At key level {nearest_lv} — waiting for engulfing candle",
                              ["Bullish or bearish engulfing candle to form"],
                              [f"Price at key level {nearest_lv} ({dist_pips:.0f} pips away)"],
                              ["No engulfing pattern yet"])

        d_bullish = d_ema50 is not None and d_close > d_ema50
        d_bearish = d_ema50 is not None and d_close < d_ema50

        if bullish_eng and (d_bullish or d_ema50 is None):
            direction = "BUY"
            h4_low = ind.get("H4_low", h4_close - h4_atr)
            entry = h4_close
            sl = h4_low - 0.5 * h4_atr
            risk = entry - sl
            tp1 = entry + 1.5 * risk
            tp2 = entry + 2.5 * risk
            reasons_for = [
                f"Bullish engulfing at key level {nearest_lv}",
                f"Distance to level: {dist_pips:.0f} pips",
                "Daily trend supports long" if d_bullish else "No conflicting daily trend",
            ]
            reasons_against = ["Daily trend bearish — lower conviction" if d_bearish else ""]
            reasons_against = [r for r in reasons_against if r]

        elif bearish_eng and (d_bearish or d_ema50 is None):
            direction = "SELL"
            h4_high = ind.get("H4_high", h4_close + h4_atr)
            entry = h4_close
            sl = h4_high + 0.5 * h4_atr
            risk = sl - entry
            tp1 = entry - 1.5 * risk
            tp2 = entry - 2.5 * risk
            reasons_for = [
                f"Bearish engulfing at key level {nearest_lv}",
                f"Distance to level: {dist_pips:.0f} pips",
                "Daily trend supports short" if d_bearish else "No conflicting daily trend",
            ]
            reasons_against = ["Daily trend bullish — lower conviction" if d_bullish else ""]
            reasons_against = [r for r in reasons_against if r]

        else:
            return self._no_trade([
                "Engulfing candle conflicts with daily trend — skipping",
                f"Bullish engulf: {bullish_eng}, Daily bullish: {d_bullish}",
            ])

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and d_bearish) or (direction == "SELL" and d_bullish)

        opp1 = OpportunityAgent(1).evaluate(3, 3, 0.85, d_bullish or d_bearish, at_level)
        opp2 = OpportunityAgent(2).evaluate(3, 3, 0.85, d_bullish or d_bearish, at_level)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.9, structure_quality=0.85, trend_alignment=0.8 if not htf_conflict else 0.4,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

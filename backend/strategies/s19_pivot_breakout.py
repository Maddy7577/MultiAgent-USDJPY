"""S19: Daily Pivot Point Breakout — London-NY overlap, strong-body close above R1/below S1."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate


class S19PivotBreakout(BaseStrategy):
    STRATEGY_ID = 19
    STRATEGY_NAME = "Daily Pivot Breakout"
    STRATEGY_TYPE = "Breakout"
    TIMEFRAMES = ["M30", "H1"]

    def evaluate(self) -> StrategyResult:
        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        pivots = ind.get("daily_pivots")
        if pivots is None:
            return self._no_trade(["Daily pivot levels not available"])

        # ── Session filter: London-NY overlap 12:00-20:00 GMT ───────────────
        utc_hour = ind.get("utc_hour", 0)
        in_session = 12 <= utc_hour < 20
        if not in_session:
            return self._no_trade([
                f"Outside London-NY overlap (UTC {utc_hour:02d}:xx) — valid 12:00-20:00 GMT"
            ])

        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        h1_df = self.ohlcv.get("H1")
        h1_close = ind.get("H1_close", price)
        h1_open = ind.get("H1_open", h1_close)
        h1_high = ind.get("H1_high", h1_close)
        h1_low = ind.get("H1_low", h1_close)
        h1_ema50 = ind.get("H1_ema50")
        h1_atr = ind.get("H1_atr14", 0.2)

        R1 = pivots["R1"]
        R2 = pivots["R2"]
        S1 = pivots["S1"]
        S2 = pivots["S2"]
        P = pivots["P"]

        # Pivot spacing check
        pivot_range = R1 - S1
        if pivot_range < 0.20:
            return self._no_trade([f"Pivot R1-S1 spread too small ({pivot_range*100:.0f} pips)"])

        # Strong-body close filter
        body = abs(h1_close - h1_open)
        total_range = h1_high - h1_low
        strong_body = total_range > 0 and body >= 0.75 * total_range

        # Volume proxy: tick volume
        avg_vol = None
        vol = None
        if h1_df is not None and len(h1_df) >= 11 and "volume" in h1_df.columns:
            avg_vol = float(h1_df["volume"].tail(10).mean())
            vol = float(h1_df["volume"].iloc[-1])
        vol_ok = (vol is None or avg_vol is None or vol > avg_vol)

        ema50_bullish = h1_ema50 is not None and h1_close > h1_ema50
        ema50_bearish = h1_ema50 is not None and h1_close < h1_ema50

        # ── Long: close above R1 ─────────────────────────────────────────────
        if h1_close > R1:
            if not strong_body:
                return self._no_trade(["Price above R1 but no strong-body candle close — invalid break"])
            if h1_ema50 is not None and not ema50_bullish:
                return self._no_trade(["Price above R1 but H1 trend bearish — no trade"])
            direction = "BUY"
            entry = h1_close
            sl = R1 - 0.5 * h1_atr
            tp1 = R2
            tp2 = R2 + (R2 - R1)
            reasons_for = [
                f"Strong-body close above R1 ({R1:.3f})",
                f"H1 trend bullish: above EMA50" if ema50_bullish else "No EMA50 conflict",
                f"In London-NY session (UTC {utc_hour:00d}:xx)",
                "Volume confirmed" if vol_ok else "Volume N/A",
            ]
            reasons_against = ["Volume below average" if not vol_ok else ""]
            reasons_against = [r for r in reasons_against if r]

        elif h1_close < S1:
            if not strong_body:
                return self._no_trade(["Price below S1 but no strong-body candle close — invalid break"])
            if h1_ema50 is not None and not ema50_bearish:
                return self._no_trade(["Price below S1 but H1 trend bullish — no trade"])
            direction = "SELL"
            entry = h1_close
            sl = S1 + 0.5 * h1_atr
            tp1 = S2
            tp2 = S2 - (S1 - S2)
            reasons_for = [
                f"Strong-body close below S1 ({S1:.3f})",
                f"H1 trend bearish: below EMA50" if ema50_bearish else "No EMA50 conflict",
                f"In London-NY session",
                "Volume confirmed" if vol_ok else "Volume N/A",
            ]
            reasons_against = ["Volume below average" if not vol_ok else ""]
            reasons_against = [r for r in reasons_against if r]

        else:
            return self._wait("BUY",
                              f"Pivot levels: S1={S1:.3f} / P={P:.3f} / R1={R1:.3f} — awaiting breakout",
                              ["Strong-body close above R1 or below S1"],
                              [f"Pivots: R1={R1:.3f}, S1={S1:.3f}, in session"],
                              ["No breakout of R1/S1 yet"])

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and not ema50_bullish) or (direction == "SELL" and not ema50_bearish)

        opp1 = OpportunityAgent(1).evaluate(3, 4, 0.8, not htf_conflict, True)
        opp2 = OpportunityAgent(2).evaluate(3, 4, 0.8, not htf_conflict, True)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=0.85, structure_quality=0.75, trend_alignment=0.8 if not htf_conflict else 0.4,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(float(tp1), 3), tp2=round(float(tp2), 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

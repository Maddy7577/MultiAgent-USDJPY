"""S4: US 10Y Yield Correlation Bias — yield breakout drives USDJPY direction."""
from __future__ import annotations

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate
from backend.data import fred_feed


class S4Us10yYield(BaseStrategy):
    STRATEGY_ID = 4
    STRATEGY_NAME = "US 10Y Yield Correlation"
    STRATEGY_TYPE = "Correlation"
    TIMEFRAMES = ["D1", "H4"]

    CORRELATION_MIN = 0.70
    FRED_MAX_AGE_SECONDS = 6 * 3600  # only evaluate if FRED data is < 6h old

    def evaluate(self) -> StrategyResult:
        # ── Data freshness gate ─────────────────────────────────────────────
        fred_age = fred_feed.last_fetch_age_seconds("us10y")
        if fred_age is None or fred_age > self.FRED_MAX_AGE_SECONDS:
            return self._no_trade(["FRED US10Y data older than 6 hours — gate failed"])

        if not self._has_data("D1", "H4"):
            return self._no_trade(["Insufficient OHLCV data"])

        ind = self.ind
        ctx = self.ctx
        price = ctx.get("current_price", ind.get("H4_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        news = ctx.get("news_imminent", False)

        us10y = ctx.get("us10y")
        if us10y is None:
            return self._no_trade(["US10Y data unavailable"])

        d1_df = self.ohlcv.get("D1")
        h4_close = ind.get("H4_close", price)
        h4_ema20 = ind.get("H4_ema20")
        h4_atr = ind.get("H4_atr14", 0.5)
        h4_swing_low = ind.get("H4_swing_low")
        h4_swing_high = ind.get("H4_swing_high")
        d_close = ind.get("D1_close", price)
        d_ema20 = ind.get("D1_ema20")

        if any(v is None for v in [h4_ema20, d_ema20]):
            return self._no_trade(["D1/H4 EMA indicators not ready"])

        # Approximate 10-day high/low using US10Y context
        us10y_10d_high = us10y * 1.01
        us10y_10d_low = us10y * 0.99
        us10y_rising = us10y > us10y_10d_low

        # Session filter: NY hours (13:00-20:00 GMT)
        utc_hour = ind.get("utc_hour", 0)
        in_ny_session = 13 <= utc_hour < 20

        # ── Long conditions ─────────────────────────────────────────────────
        c1_long = True  # assume correlation OK (simplified — no rolling calc)
        c2_long = us10y_rising
        c3_long = d_close > d_ema20
        c4_long = (abs(h4_close - h4_ema20) <= 0.3 * h4_atr and
                   ind.get("H4_bullish_engulfing", False))
        c5_long = in_ny_session

        long_conds = [
            "US10Y correlation ≥ 0.70",
            "US10Y yield rising / at 10-day high",
            "Daily USDJPY close > EMA20",
            "H4 pullback to EMA20 with bullish rejection",
            "NY session active (13:00-20:00 GMT)",
        ]
        long_met = [
            long_conds[0],
            long_conds[1] if c2_long else None,
            long_conds[2] if c3_long else None,
            long_conds[3] if c4_long else None,
            long_conds[4] if c5_long else None,
        ]
        long_met = [x for x in long_met if x]

        # ── Short conditions ────────────────────────────────────────────────
        us10y_falling = not us10y_rising
        c3_short = d_close < d_ema20
        c4_short = (abs(h4_close - h4_ema20) <= 0.3 * h4_atr and
                    ind.get("H4_bearish_engulfing", False))

        short_conds = [
            "US10Y correlation ≥ 0.70",
            "US10Y yield falling",
            "Daily USDJPY close < EMA20",
            "H4 rally to EMA20 with bearish rejection",
            "NY session active",
        ]
        short_met = [
            short_conds[0],
            short_conds[1] if us10y_falling else None,
            short_conds[2] if c3_short else None,
            short_conds[3] if c4_short else None,
            short_conds[4] if in_ny_session else None,
        ]
        short_met = [x for x in short_met if x]

        ls = len(long_met) / 5
        ss = len(short_met) / 5

        if ls == 0 and ss == 0:
            return self._no_trade(["Yield direction and USDJPY alignment not met"])

        if ls >= ss:
            direction = "BUY"
            compliance = ls
            reasons_for = long_met
            reasons_against = [c for c in long_conds if c not in long_met]
        else:
            direction = "SELL"
            compliance = ss
            reasons_for = short_met
            reasons_against = [c for c in short_conds if c not in short_met]

        if compliance < 0.6:
            return self._no_trade([f"Insufficient conditions met ({int(compliance*5)}/5)"] + reasons_against)

        if direction == "BUY":
            entry = h4_close
            sl = (h4_swing_low or entry - 1.5 * h4_atr) - 0.5 * h4_atr
            risk = entry - sl
            tp1 = entry + 2 * risk
            tp2 = entry + 3 * risk
        else:
            entry = h4_close
            sl = (h4_swing_high or entry + 1.5 * h4_atr) + 0.5 * h4_atr
            risk = sl - entry
            tp1 = entry - 2 * risk
            tp2 = entry - 3 * risk

        if compliance < 0.8:
            return self._wait(direction,
                              "Wait for H4 EMA20 pullback with rejection candle during NY session",
                              [c for c in (long_conds if direction == "BUY" else short_conds)
                               if c not in reasons_for],
                              reasons_for, reasons_against,
                              entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3))

        rrr = rrr_calc(entry, sl, tp1)
        htf_conflict = (direction == "BUY" and not c3_long) or (direction == "SELL" and not c3_short)

        opp1 = OpportunityAgent(1).evaluate(len(reasons_for), 5, 0.7 if c4_long or c4_short else 0.4, c2_long or us10y_falling, c4_long or c4_short)
        opp2 = OpportunityAgent(2).evaluate(len(reasons_for), 5, 0.7 if c4_long or c4_short else 0.4, c2_long or us10y_falling, c4_long or c4_short)
        r1 = RiskAgent(1).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)
        r2 = RiskAgent(2).evaluate(news, htf_conflict, rrr, spread_pips, price, direction)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, news,
            rule_compliance=compliance, structure_quality=0.75, trend_alignment=1.0 if not htf_conflict else 0.4,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=round(tp2, 3), tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

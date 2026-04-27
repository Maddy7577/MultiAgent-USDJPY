"""S20: Post-News Breakout — only fires within 90 min of confirmed high-impact event."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.strategies.base_strategy import BaseStrategy, StrategyResult, rrr_calc
from backend.agents.opportunity_agent import OpportunityAgent
from backend.agents.risk_agent import RiskAgent
from backend.agents.debate_engine import run_debate

_TIER1_EVENTS = {"fomc", "boj", "nfp", "cpi", "pce", "non-farm", "federal", "bank of japan",
                 "interest rate", "gdp", "unemployment"}


def _is_tier1(event_name: str) -> bool:
    name_lower = event_name.lower()
    return any(k in name_lower for k in _TIER1_EVENTS)


class S20PostNews(BaseStrategy):
    STRATEGY_ID = 20
    STRATEGY_NAME = "Post-News Breakout"
    STRATEGY_TYPE = "Event-Driven"
    TIMEFRAMES = ["H1"]

    MAX_MINUTES_AFTER = 90

    def evaluate(self) -> StrategyResult:
        ctx = self.ctx
        ind = self.ind
        recent_events = ctx.get("recent_events", [])

        # ── Find a recently fired Tier 1 event ──────────────────────────────
        now = datetime.now(timezone.utc)
        recent_event = None
        for ev in recent_events:
            ev_time = ev.get("datetime_utc")
            if ev_time is None:
                continue
            if isinstance(ev_time, str):
                try:
                    ev_time = datetime.fromisoformat(ev_time)
                except ValueError:
                    continue
            if ev_time.tzinfo is None:
                ev_time = ev_time.replace(tzinfo=timezone.utc)
            minutes_ago = (now - ev_time).total_seconds() / 60
            if 0 <= minutes_ago <= self.MAX_MINUTES_AFTER and _is_tier1(ev.get("name", "")):
                recent_event = ev
                recent_event["minutes_ago"] = minutes_ago
                break

        if recent_event is None:
            return self._no_trade([
                f"No Tier 1 event in past {self.MAX_MINUTES_AFTER} min — S20 only fires post-event"
            ])

        if not self._has_data("H1"):
            return self._no_trade(["Insufficient H1 data"])

        price = ctx.get("current_price", ind.get("H1_close", 0))
        spread_pips = ctx.get("spread_pips", 0)
        h1_df = self.ohlcv.get("H1")
        h1_close = ind.get("H1_close", price)
        h1_rsi = ind.get("H1_rsi14", 50)
        h1_atr = ind.get("H1_atr14", 0.2)

        # Post-release range: last 2 H1 bars after event
        if h1_df is None or len(h1_df) < 3:
            return self._no_trade(["Not enough H1 bars to define post-news range"])

        post_bars = h1_df.tail(2)
        post_high = float(post_bars["high"].max())
        post_low = float(post_bars["low"].min())
        post_range = post_high - post_low
        post_range_pips = post_range * 100

        event_name = recent_event.get("name", "High-impact event")
        minutes_ago = recent_event.get("minutes_ago", 0)

        if post_range_pips < 30:
            return self._no_trade([
                f"Post-{event_name} range only {post_range_pips:.0f} pips (need 30+) — market unimpressed"
            ])

        pip = 0.01

        if h1_close > post_high + 5 * pip and h1_rsi > 50:
            direction = "BUY"
            entry = h1_close
            sl = post_low - 5 * pip
            tp1 = entry + 2 * post_range
            reasons_for = [
                f"Tier 1 event: {event_name} ({minutes_ago:.0f} min ago)",
                f"Post-event range: {post_range_pips:.0f} pips ({post_low:.3f}–{post_high:.3f})",
                "Bullish breakout above post-news range",
                f"RSI {h1_rsi:.0f} > 50 — bullish momentum",
            ]
            reasons_against = []

        elif h1_close < post_low - 5 * pip and h1_rsi < 50:
            direction = "SELL"
            entry = h1_close
            sl = post_high + 5 * pip
            tp1 = entry - 2 * post_range
            reasons_for = [
                f"Tier 1 event: {event_name} ({minutes_ago:.0f} min ago)",
                f"Post-event range: {post_range_pips:.0f} pips",
                "Bearish breakdown below post-news range",
                f"RSI {h1_rsi:.0f} < 50 — bearish momentum",
            ]
            reasons_against = []

        else:
            proj_entry = round(post_high + 5 * pip, 3)
            proj_sl = round(post_low - 5 * pip, 3)
            proj_tp1 = round(proj_entry + 2 * post_range, 3)
            return self._wait("BUY",
                              f"Post-{event_name} range forming ({post_range_pips:.0f} pips) — await directional break",
                              ["Break of post-news range + RSI confirmation"],
                              [f"Event: {event_name} {minutes_ago:.0f} min ago, range {post_range_pips:.0f} pips"],
                              ["No directional break yet"],
                              entry=proj_entry, sl=proj_sl, tp1=proj_tp1)

        rrr = rrr_calc(entry, sl, tp1)
        # Elevated spread during news is a concern
        spread_flag = ([f"Spread {spread_pips:.1f} pips — elevated post-news"]
                       if spread_pips > 1.5 else [])

        opp1 = OpportunityAgent(1).evaluate(4, 4, 0.8, True, True)
        opp2 = OpportunityAgent(2).evaluate(4, 4, 0.8, True, True)
        # news_imminent=False here — the event already happened, we're trading the aftermath
        r1 = RiskAgent(1).evaluate(False, False, rrr, spread_pips, price, direction, spread_flag)
        r2 = RiskAgent(2).evaluate(False, False, rrr, spread_pips, price, direction, spread_flag)

        return run_debate(
            opp1, opp2, r1, r2, rrr, direction, price, spread_pips, False,
            rule_compliance=0.9, structure_quality=0.8, trend_alignment=0.7,
            strategy_id=self.STRATEGY_ID, strategy_name=self.STRATEGY_NAME,
            strategy_type=self.STRATEGY_TYPE, timeframes=self.TIMEFRAMES,
            entry=round(entry, 3), sl=round(sl, 3), tp1=round(tp1, 3), tp2=None, tp3=None,
            wait_zone=None, conditions_to_meet=[],
            reasons_for=reasons_for, reasons_against=reasons_against,
            evaluated_at=self.now,
        )

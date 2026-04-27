"""Evaluation orchestrator — runs all 20 strategies in one H1 cycle."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Optional

from backend import config
from backend.data import calendar_feed, fred_feed, market_feed, mt5_feed
from backend.strategies.indicator_engine import compute_indicators
from backend.strategies.base_strategy import StrategyResult

from backend.strategies.s01_mtf_trend import S1MtfTrend
from backend.strategies.s02_ichimoku import S2Ichimoku
from backend.strategies.s03_carry_trade import S3CarryTrade
from backend.strategies.s04_us10y_yield import S4Us10yYield
from backend.strategies.s05_confluence import S5Confluence
from backend.strategies.s06_macd_ema200 import S6MacdEma200
from backend.strategies.s07_adx_dmi import S7AdxDmi
from backend.strategies.s08_tokyo_range import S8TokyoRange
from backend.strategies.s09_keltner import S9Keltner
from backend.strategies.s10_ema_crossover import S10EmaCrossover
from backend.strategies.s11_asian_fade import S11AsianFade
from backend.strategies.s12_donchian import S12Donchian
from backend.strategies.s13_london_breakout import S13LondonBreakout
from backend.strategies.s14_bollinger_mr import S14BollingerMR
from backend.strategies.s15_engulfing import S15Engulfing
from backend.strategies.s16_rsi_mr import S16RsiMR
from backend.strategies.s17_fibonacci import S17Fibonacci
from backend.strategies.s18_inside_bar import S18InsideBar
from backend.strategies.s19_pivot_breakout import S19PivotBreakout
from backend.strategies.s20_post_news import S20PostNews

logger = logging.getLogger(__name__)

_STRATEGY_CLASSES = [
    S1MtfTrend, S2Ichimoku, S3CarryTrade, S4Us10yYield, S5Confluence,
    S6MacdEma200, S7AdxDmi, S8TokyoRange, S9Keltner, S10EmaCrossover,
    S11AsianFade, S12Donchian, S13LondonBreakout, S14BollingerMR, S15Engulfing,
    S16RsiMR, S17Fibonacci, S18InsideBar, S19PivotBreakout, S20PostNews,
]


def _build_ohlcv() -> dict:
    """Fetch OHLCV for all timeframes. Returns empty dict on MT5 failure."""
    ohlcv = {}
    for tf in config.TIMEFRAME_NAMES:
        df = mt5_feed.get_ohlcv(config.MT5_SYMBOL, tf, config.MT5_BARS_COUNT)
        if df is not None:
            ohlcv[tf] = df
        else:
            logger.debug(f"No data for {tf} — MT5 unavailable or insufficient bars")
    return ohlcv


def _build_context(ohlcv: dict) -> dict:
    """Collect market context: price, spread, macro, news."""
    current_price = None
    spread_pips = 0.0

    tick = mt5_feed.get_tick(config.MT5_SYMBOL)
    if tick:
        current_price = tick.get("bid")
        spread_pips = tick.get("spread_pips", 0.0)

    # Fallback price from OHLCV
    if current_price is None and "H1" in ohlcv:
        current_price = float(ohlcv["H1"]["close"].iloc[-1])
    if current_price is None:
        current_price = 150.0

    us10y = fred_feed.get_us10y(config.FRED_API_KEY)
    fed_rate = fred_feed.get_fed_rate(config.FRED_API_KEY)
    boj_rate = getattr(config, "BOJ_RATE", 0.75)
    dxy = market_feed.get_dxy()
    vix = market_feed.get_vix()

    news_imminent = calendar_feed.is_high_impact_event_soon(
        config.CALENDAR_URL,
        config.HIGH_IMPACT_CURRENCIES,
        within_minutes=config.NEWS_BUFFER_MINUTES,
    )
    next_events = calendar_feed.get_next_events(
        config.CALENDAR_URL, config.HIGH_IMPACT_CURRENCIES, count=5
    )
    recent_events = calendar_feed.get_recent_events(
        config.CALENDAR_URL, config.HIGH_IMPACT_CURRENCIES, within_minutes=90
    )

    def _serialize_events(events):
        safe = []
        for ev in events:
            safe_ev = dict(ev)
            if hasattr(safe_ev.get("datetime_utc"), "isoformat"):
                safe_ev["datetime_utc"] = safe_ev["datetime_utc"].isoformat()
            safe.append(safe_ev)
        return safe

    safe_events = _serialize_events(next_events)
    safe_recent_events = _serialize_events(recent_events)

    return {
        "current_price": current_price,
        "spread_pips": spread_pips,
        "us10y": us10y,
        "fed_rate": fed_rate,
        "boj_rate": boj_rate,
        "dxy": dxy,
        "vix": vix,
        "news_imminent": news_imminent,
        "next_events": safe_events,
        "recent_events": safe_recent_events,
    }


def run_evaluation_cycle() -> list[StrategyResult]:
    """Full 20-strategy evaluation cycle. Returns list of StrategyResult."""
    t0 = time.time()
    logger.info("Evaluation cycle starting...")

    ohlcv = _build_ohlcv()
    context = _build_context(ohlcv)
    indicators = compute_indicators(ohlcv)

    market_data = {
        "ohlcv": ohlcv,
        "indicators": indicators,
        "context": context,
    }

    results: list[StrategyResult] = []
    errors = 0

    for StrategyClass in _STRATEGY_CLASSES:
        try:
            strategy = StrategyClass(market_data)
            result = strategy.evaluate()
            results.append(result)
        except Exception as exc:
            logger.error(f"Strategy {StrategyClass.__name__} failed: {exc}", exc_info=True)
            errors += 1
            # Produce a safe NO_TRADE placeholder so the DB always has 20 rows
            from backend.strategies.base_strategy import BaseStrategy
            dummy = StrategyClass.__new__(StrategyClass)
            dummy.STRATEGY_ID = getattr(StrategyClass, "STRATEGY_ID", 0)
            dummy.STRATEGY_NAME = getattr(StrategyClass, "STRATEGY_NAME", "Unknown")
            dummy.STRATEGY_TYPE = getattr(StrategyClass, "STRATEGY_TYPE", "Unknown")
            dummy.TIMEFRAMES = getattr(StrategyClass, "TIMEFRAMES", [])
            dummy.now = datetime.now(timezone.utc)
            results.append(dummy._no_trade([f"Strategy evaluation error: {exc}"]))

    elapsed = time.time() - t0
    valid = sum(1 for r in results if r.status == "VALID_TRADE")
    wait = sum(1 for r in results if r.status == "WAIT_FOR_LEVELS")
    logger.info(
        f"Cycle complete in {elapsed:.1f}s — {len(results)} strategies | "
        f"VALID: {valid} | WAIT: {wait} | NO_TRADE: {len(results)-valid-wait} | errors: {errors}"
    )

    return results

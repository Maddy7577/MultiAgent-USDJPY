import logging
import time
from typing import Optional

import yfinance as yf

logger = logging.getLogger(__name__)

_cache: dict = {}


def _cached(key: str) -> Optional[float]:
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["value"]
    return None


def _store(key: str, value: float, ttl: int):
    _cache[key] = {"value": value, "expires": time.time() + ttl, "fetched_at": time.time()}


def _fetch_latest_close(ticker: str) -> Optional[float]:
    try:
        hist = yf.Ticker(ticker).history(period="5d")
        if hist.empty:
            logger.warning(f"yfinance returned empty data for {ticker}")
            return None
        return float(hist["Close"].dropna().iloc[-1])
    except Exception as exc:
        logger.error(f"yfinance fetch error for {ticker}: {exc}")
        return None


def get_dxy(ttl: int = 14400) -> Optional[float]:
    """DXY (US Dollar Index) daily close via DX-Y.NYB. Cached for ttl seconds (default 4h)."""
    hit = _cached("dxy")
    if hit is not None:
        return hit

    value = _fetch_latest_close("DX-Y.NYB")
    if value is not None:
        _store("dxy", value, ttl)
        logger.info(f"DXY fetched: {value}")
    return value


def get_vix(ttl: int = 14400) -> Optional[float]:
    """VIX (Volatility Index) latest value via ^VIX. Cached for ttl seconds (default 4h)."""
    hit = _cached("vix")
    if hit is not None:
        return hit

    value = _fetch_latest_close("^VIX")
    if value is not None:
        _store("vix", value, ttl)
        logger.info(f"VIX fetched: {value}")
    return value


def refresh_all():
    """Force refresh all market data (clears cache first)."""
    _cache.pop("dxy", None)
    _cache.pop("vix", None)
    get_dxy()
    get_vix()


def last_fetch_age_seconds(key: str) -> Optional[float]:
    entry = _cache.get(key)
    return time.time() - entry["fetched_at"] if entry else None

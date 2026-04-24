import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from fredapi import Fred
    _FRED_AVAILABLE = True
except ImportError:
    _FRED_AVAILABLE = False
    logger.warning("fredapi not installed — FRED data disabled")

_cache: dict = {}


def _cached(key: str) -> Optional[float]:
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["value"]
    return None


def _store(key: str, value: float, ttl: int):
    _cache[key] = {"value": value, "expires": time.time() + ttl, "fetched_at": time.time()}


def get_us10y(api_key: str, ttl: int = 14400) -> Optional[float]:
    """US 10-Year Treasury Yield (DGS10). Cached for ttl seconds (default 4h)."""
    hit = _cached("us10y")
    if hit is not None:
        return hit

    if not _FRED_AVAILABLE or not api_key:
        logger.warning("FRED unavailable or no API key — US10Y not available")
        return None

    try:
        series = Fred(api_key=api_key).get_series("DGS10")
        value = float(series.dropna().iloc[-1])
        _store("us10y", value, ttl)
        logger.info(f"FRED US10Y fetched: {value}%")
        return value
    except Exception as exc:
        logger.error(f"FRED US10Y fetch error: {exc}")
        return None


def get_fed_rate(api_key: str, ttl: int = 86400) -> Optional[float]:
    """Effective Federal Funds Rate (DFF). Cached for ttl seconds (default 24h)."""
    hit = _cached("fed_rate")
    if hit is not None:
        return hit

    if not _FRED_AVAILABLE or not api_key:
        logger.warning("FRED unavailable or no API key — Fed rate not available")
        return None

    try:
        series = Fred(api_key=api_key).get_series("DFF")
        value = float(series.dropna().iloc[-1])
        _store("fed_rate", value, ttl)
        logger.info(f"FRED Fed rate fetched: {value}%")
        return value
    except Exception as exc:
        logger.error(f"FRED Fed rate fetch error: {exc}")
        return None


def refresh_all(api_key: str):
    """Force refresh all FRED series (clears cache first)."""
    _cache.pop("us10y", None)
    _cache.pop("fed_rate", None)
    get_us10y(api_key)
    get_fed_rate(api_key)


def last_fetch_age_seconds(key: str) -> Optional[float]:
    """Return seconds since key was last fetched, or None if not cached."""
    entry = _cache.get(key)
    return time.time() - entry["fetched_at"] if entry else None

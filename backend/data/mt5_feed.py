import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

try:
    import MetaTrader5 as mt5
    _MT5_AVAILABLE = True
except ImportError:
    _MT5_AVAILABLE = False
    logger.warning("MetaTrader5 package not available — MT5 features disabled")

_TIMEFRAME_MAP: dict = {}
if _MT5_AVAILABLE:
    _TIMEFRAME_MAP = {
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1":  mt5.TIMEFRAME_H1,
        "H4":  mt5.TIMEFRAME_H4,
        "D1":  mt5.TIMEFRAME_D1,
    }

_TF_MINUTES = {"M15": 15, "M30": 30, "H1": 60, "H4": 240, "D1": 1440}


def is_connected() -> bool:
    if not _MT5_AVAILABLE:
        return False
    info = mt5.terminal_info()
    return info is not None and info.connected


def initialize() -> bool:
    if not _MT5_AVAILABLE:
        return False
    result = mt5.initialize()
    if result:
        info = mt5.terminal_info()
        logger.info(f"MT5 connected: {info.name} build {info.build}")
    else:
        logger.warning(f"MT5 initialize failed: {mt5.last_error()}")
    return result


def shutdown():
    if _MT5_AVAILABLE:
        mt5.shutdown()


def _ensure_connected() -> bool:
    if is_connected():
        return True
    return initialize()


def get_ohlcv(symbol: str, timeframe: str, count: int = 500) -> Optional[pd.DataFrame]:
    """Fetch OHLCV bars. Returns None if MT5 is unavailable or not running."""
    if not _MT5_AVAILABLE:
        logger.warning("MT5 not available — skipping OHLCV fetch")
        return None

    tf = _TIMEFRAME_MAP.get(timeframe)
    if tf is None:
        logger.error(f"Unknown timeframe: {timeframe}")
        return None

    if not _ensure_connected():
        logger.warning("MT5 not running — cannot fetch OHLCV")
        return None

    rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
    if rates is None or len(rates) == 0:
        logger.warning(f"No data for {symbol} {timeframe}: {mt5.last_error()}")
        return None

    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    df.rename(columns={"time": "timestamp", "tick_volume": "volume"}, inplace=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def get_tick(symbol: str) -> Optional[dict]:
    """Return latest bid/ask/spread for a symbol."""
    if not _MT5_AVAILABLE or not _ensure_connected():
        return None

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return None

    return {
        "bid": tick.bid,
        "ask": tick.ask,
        "last": tick.last,
        "spread_pips": round((tick.ask - tick.bid) * 100, 2),
        "timestamp": datetime.fromtimestamp(tick.time, tz=timezone.utc).isoformat(),
    }


def get_terminal_info() -> dict:
    """Return sanitized terminal info — no account credentials."""
    if not _MT5_AVAILABLE:
        return {"available": False, "connected": False}

    if not _ensure_connected():
        return {"available": True, "connected": False}

    info = mt5.terminal_info()
    account = mt5.account_info()
    return {
        "available": True,
        "connected": info.connected if info else False,
        "terminal_name": info.name if info else None,
        "build": info.build if info else None,
        "account_type": account.trade_mode if account else None,
    }


def get_candle_close_time(timeframe: str) -> Optional[datetime]:
    """Return the UTC close time of the current open candle."""
    minutes = _TF_MINUTES.get(timeframe)
    if minutes is None:
        return None
    now = datetime.now(tz=timezone.utc)
    elapsed = now.hour * 60 + now.minute
    candle_start = (elapsed // minutes) * minutes
    next_close = candle_start + minutes
    close_hour = (next_close // 60) % 24
    close_min = next_close % 60
    return now.replace(hour=close_hour, minute=close_min, second=0, microsecond=0)

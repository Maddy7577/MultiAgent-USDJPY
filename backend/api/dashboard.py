from datetime import datetime, timezone

from fastapi import APIRouter

from backend import config
from backend.data import calendar_feed, fred_feed, market_feed, mt5_feed
from backend.db import signal_store

router = APIRouter()


def _fmt_event(event: dict) -> dict:
    return {
        "name": event["name"],
        "country": event["country"],
        "datetime_utc": event["datetime_utc"].isoformat(),
        "impact": event["impact"],
    }


@router.get("/dashboard")
def get_dashboard():
    tick = mt5_feed.get_tick(config.MT5_SYMBOL)
    us10y = fred_feed.get_us10y(config.FRED_API_KEY)
    fed_rate = fred_feed.get_fed_rate(config.FRED_API_KEY)
    dxy = market_feed.get_dxy()
    vix = market_feed.get_vix()
    next_events = calendar_feed.get_next_events(
        config.CALENDAR_URL, config.HIGH_IMPACT_CURRENCIES, count=1
    )
    signal_counts = signal_store.get_signal_counts() if signal_store.is_initialized() else {}

    data = {
        "price": tick,
        "market_context": {
            "us10y": us10y,
            "dxy": dxy,
            "vix": vix,
            "fed_rate": fed_rate,
            "next_event": _fmt_event(next_events[0]) if next_events else None,
        },
        "signal_counts": signal_counts,
        "snapshot_time": datetime.now(tz=timezone.utc).isoformat(),
    }

    return {"success": True, "data": data, "error": None}

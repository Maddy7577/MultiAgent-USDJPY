from datetime import datetime, timezone

from fastapi import APIRouter

from backend.data import fred_feed, market_feed, mt5_feed
from backend.db import signal_store

router = APIRouter()


@router.get("/status")
def get_status():
    terminal = mt5_feed.get_terminal_info()

    data = {
        "mt5_connected": terminal.get("connected", False),
        "mt5_info": terminal,
        "db_initialized": signal_store.is_initialized(),
        "data_freshness": {
            "us10y_age_seconds": fred_feed.last_fetch_age_seconds("us10y"),
            "fed_rate_age_seconds": fred_feed.last_fetch_age_seconds("fed_rate"),
            "dxy_age_seconds": market_feed.last_fetch_age_seconds("dxy"),
            "vix_age_seconds": market_feed.last_fetch_age_seconds("vix"),
        },
        "server_time_utc": datetime.now(tz=timezone.utc).isoformat(),
    }

    return {"success": True, "data": data, "error": None}

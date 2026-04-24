import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")
last_h1_eval_time: str = "never"
last_daily_refresh_time: str = "never"


def _h1_evaluation_stub():
    """Placeholder for Phase 2: full 20-strategy evaluation cycle."""
    global last_h1_eval_time
    from datetime import datetime, timezone
    last_h1_eval_time = datetime.now(tz=timezone.utc).isoformat()
    logger.debug("H1 evaluation cycle triggered — strategy engine not yet active (Phase 2)")


def _h4_refresh():
    """Refresh H4-frequency market data."""
    from backend import config
    from backend.data import fred_feed, market_feed
    logger.info("H4 refresh: pulling latest DXY, VIX, US10Y")
    market_feed.get_dxy()
    market_feed.get_vix()
    fred_feed.get_us10y(config.FRED_API_KEY)


def _daily_refresh():
    """Daily refresh: FRED series, yfinance, and economic calendar."""
    global last_daily_refresh_time
    from datetime import datetime, timezone
    from backend import config
    from backend.data import calendar_feed, fred_feed, market_feed
    logger.info("Daily refresh: FRED + yfinance + calendar")
    fred_feed.refresh_all(config.FRED_API_KEY)
    market_feed.refresh_all()
    calendar_feed.fetch_calendar(config.CALENDAR_URL, config.HIGH_IMPACT_CURRENCIES)
    last_daily_refresh_time = datetime.now(tz=timezone.utc).isoformat()


def start():
    # H1 close evaluation — fires at HH:02:00 UTC every hour
    _scheduler.add_job(
        _h1_evaluation_stub,
        CronTrigger(minute=2, timezone="UTC"),
        id="h1_eval",
        replace_existing=True,
    )
    # H4 close refresh — fires at 00:02, 04:02, 08:02, 12:02, 16:02, 20:02 UTC
    _scheduler.add_job(
        _h4_refresh,
        CronTrigger(hour="0,4,8,12,16,20", minute=2, timezone="UTC"),
        id="h4_refresh",
        replace_existing=True,
    )
    # Daily data refresh — fires at 00:05 UTC
    _scheduler.add_job(
        _daily_refresh,
        CronTrigger(hour=0, minute=5, timezone="UTC"),
        id="daily_refresh",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info("Scheduler started (UTC): H1@:02 | H4@00:02,04:02,... | Daily@00:05")


def stop():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_job_info() -> list:
    return [
        {"id": job.id, "next_run": job.next_run_time.isoformat() if job.next_run_time else None}
        for job in _scheduler.get_jobs()
    ]

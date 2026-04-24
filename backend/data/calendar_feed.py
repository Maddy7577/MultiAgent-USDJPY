import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import requests

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")  # ForexFactory publishes times in US Eastern

_events_cache: List[dict] = []
_cache_expires: float = 0.0


def _is_high_impact(impact: str, country: str, currencies: set) -> bool:
    return impact.strip().lower() == "high" and country.strip().upper() in currencies


def _parse_event_datetime(date_str: str, time_str: str) -> Optional[datetime]:
    """Parse ForexFactory date/time strings and return as UTC datetime."""
    time_str = time_str.strip()
    if not time_str or time_str.lower() in ("tentative", "all day"):
        time_str = "12:00am"

    try:
        dt_naive = datetime.strptime(
            f"{date_str.strip()} {time_str.upper()}", "%b %d, %Y %I:%M%p"
        )
        # Localize to Eastern then convert to UTC
        dt_et = dt_naive.replace(tzinfo=_ET)
        return dt_et.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_ff_xml(content: str, currencies: set) -> List[dict]:
    events: List[dict] = []
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        logger.error(f"Calendar XML parse error: {exc}")
        return events

    for node in root.findall("event"):
        title = (node.findtext("title") or "").strip()
        country = (node.findtext("country") or "").strip()
        date_str = (node.findtext("date") or "").strip()
        time_str = (node.findtext("time") or "").strip()
        impact = (node.findtext("impact") or "").strip()

        if not _is_high_impact(impact, country, currencies):
            continue

        dt_utc = _parse_event_datetime(date_str, time_str)
        if dt_utc is None:
            continue

        events.append({
            "name": title,
            "country": country,
            "datetime_utc": dt_utc,
            "impact": impact,
        })

    return events


def fetch_calendar(url: str, currencies: set, ttl: int = 86400) -> List[dict]:
    """Fetch and cache high-impact calendar events. Returns cached list on failure."""
    global _events_cache, _cache_expires

    if time.time() < _cache_expires and _events_cache:
        return _events_cache

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        events = _parse_ff_xml(resp.text, currencies)
        _events_cache = events
        _cache_expires = time.time() + ttl
        logger.info(f"Calendar loaded: {len(events)} high-impact events for {currencies}")
    except requests.RequestException as exc:
        logger.warning(f"Calendar fetch failed ({exc}) — using cached data ({len(_events_cache)} events)")

    return _events_cache


def is_high_impact_event_soon(url: str, currencies: set, within_minutes: int = 30) -> bool:
    """Return True if any high-impact event fires within `within_minutes` from now (UTC)."""
    events = fetch_calendar(url, currencies)
    now = datetime.now(tz=timezone.utc)
    cutoff = now + timedelta(minutes=within_minutes)
    return any(now <= e["datetime_utc"] <= cutoff for e in events)


def get_next_events(url: str, currencies: set, count: int = 5) -> List[dict]:
    """Return the next N upcoming high-impact events, sorted by time."""
    events = fetch_calendar(url, currencies)
    now = datetime.now(tz=timezone.utc)
    upcoming = sorted(
        (e for e in events if e["datetime_utc"] >= now),
        key=lambda x: x["datetime_utc"],
    )
    return upcoming[:count]

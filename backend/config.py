import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "usdjpy_signals.db"

# MT5
MT5_SYMBOL = "USDJPY"
MT5_BARS_COUNT = 500
TIMEFRAME_NAMES = ["M15", "M30", "H1", "H4", "D1"]

# API keys — loaded from .env
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# FRED series identifiers
FRED_US10Y_SERIES = "DGS10"
FRED_FED_RATE_SERIES = "DFF"

# yfinance tickers
DXY_TICKER = "DX-Y.NYB"
VIX_TICKER = "^VIX"

# Economic calendar
# ForexFactory XML feed — provides high-impact event data, no API key required
CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
CALENDAR_REFRESH_HOUR = 0  # UTC midnight
HIGH_IMPACT_CURRENCIES = {"USD", "JPY"}

# Scheduler
EVAL_OFFSET_SECONDS = 120  # fire 2 min after candle close

# Risk thresholds
NEWS_BUFFER_MINUTES = 30
INTERVENTION_LEVEL = 155.00
MAX_SPREAD_PIPS = 3.0

# Cache TTLs in seconds
CACHE_TTL_4H = 4 * 3600
CACHE_TTL_DAILY = 24 * 3600

# Verdict thresholds (used by Phase 2 debate engine)
CONFIDENCE_THRESHOLD = 75
PROBABILITY_THRESHOLD = 70
MIN_RRR = 1.5

# BoJ policy rate — update manually when BoJ changes rates
BOJ_RATE: float = 0.75  # as of December 2025

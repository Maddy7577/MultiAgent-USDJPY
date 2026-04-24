import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure project root is on sys.path when running as `python backend/main.py`
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend import config, scheduler
from backend.api import dashboard, history, status, strategies
from backend.db import signal_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)-30s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== USDJPY Smart Agent starting ===")

    logger.info("Initializing database...")
    signal_store.initialize(config.DB_PATH)

    logger.info("Starting scheduler...")
    scheduler.start()

    # Kick off an initial data fetch in the background so /api/dashboard
    # returns real values on the very first request without waiting for the
    # scheduled 00:05 UTC job.
    try:
        from backend.data import fred_feed, market_feed
        fred_feed.get_us10y(config.FRED_API_KEY)
        fred_feed.get_fed_rate(config.FRED_API_KEY)
        market_feed.get_dxy()
        market_feed.get_vix()
    except Exception as exc:
        logger.warning(f"Initial data prefetch failed (non-fatal): {exc}")

    logger.info("Server ready — API available at http://localhost:8000")
    yield

    logger.info("=== USDJPY Smart Agent shutting down ===")
    scheduler.stop()
    from backend.data import mt5_feed
    mt5_feed.shutdown()


app = FastAPI(title="USDJPY Smart Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(dashboard.router, prefix="/api")
app.include_router(strategies.router, prefix="/api")
app.include_router(history.router, prefix="/api")
app.include_router(status.router, prefix="/api")

# Serve frontend static files (built in Phase 3)
_frontend = Path(__file__).parent.parent / "frontend"
if _frontend.exists():
    app.mount("/", StaticFiles(directory=str(_frontend), html=True), name="frontend")


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
    )

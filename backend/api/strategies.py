from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.db import signal_store

router = APIRouter()


@router.get("/strategies")
def get_strategies():
    """Return latest verdict for all strategies. Empty until Phase 2 strategy engine is built."""
    items = signal_store.get_latest_by_strategy() if signal_store.is_initialized() else []
    return {"success": True, "data": {"strategies": items}, "error": None}


@router.get("/strategy/{strategy_id}")
def get_strategy(strategy_id: int):
    """Full debate output for a single strategy. Populated by Phase 2."""
    if not signal_store.is_initialized():
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": "Strategy engine not yet active (Phase 2)"},
        )

    rows = signal_store.get_signals(per_page=1, strategy_id=strategy_id)
    if not rows["items"]:
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": f"No data for strategy {strategy_id}"},
        )

    return {"success": True, "data": rows["items"][0], "error": None}

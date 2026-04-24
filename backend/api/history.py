from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.db import signal_store

router = APIRouter()


@router.get("/history")
def get_history(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    strategy_id: int = Query(None),
):
    if not signal_store.is_initialized():
        return {"success": True, "data": {"total": 0, "page": 1, "per_page": per_page, "items": []}, "error": None}

    result = signal_store.get_signals(page=page, per_page=per_page, strategy_id=strategy_id)
    return {"success": True, "data": result, "error": None}


@router.get("/history/{signal_id}")
def get_history_item(signal_id: int):
    if not signal_store.is_initialized():
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": "Signal not found"},
        )

    row = signal_store.get_signal_by_id(signal_id)
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": f"Signal {signal_id} not found"},
        )

    return {"success": True, "data": row, "error": None}

import json

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.db import signal_store

router = APIRouter()

_JSON_FIELDS = ("reasons_for", "reasons_against", "conditions_to_meet", "timeframes", "agent_scores")


def _deserialize(item: dict) -> dict:
    """Parse JSON-string fields back to native Python types."""
    for field in _JSON_FIELDS:
        val = item.get(field)
        if isinstance(val, str):
            try:
                item[field] = json.loads(val)
            except (ValueError, TypeError):
                pass
    return item


@router.get("/strategies")
def get_strategies():
    """Return latest verdict for all strategies."""
    items = [_deserialize(r) for r in signal_store.get_latest_by_strategy()] if signal_store.is_initialized() else []
    return JSONResponse(content={"success": True, "data": {"strategies": items}, "error": None})


@router.get("/strategy/{strategy_id}")
def get_strategy(strategy_id: int):
    """Full debate output for a single strategy including agent scores."""
    if not signal_store.is_initialized():
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": "Signal store not initialized"},
        )

    rows = signal_store.get_signals(per_page=1, strategy_id=strategy_id)
    if not rows["items"]:
        return JSONResponse(
            status_code=404,
            content={"success": False, "data": None, "error": f"No data for strategy {strategy_id}"},
        )

    item = _deserialize(rows["items"][0])
    return JSONResponse(content={"success": True, "data": item, "error": None})


@router.post("/evaluate")
def trigger_evaluation():
    """Manually trigger a full evaluation cycle (for testing)."""
    try:
        from backend.strategies.evaluation_orchestrator import run_evaluation_cycle
        results = run_evaluation_cycle()
        if signal_store.is_initialized():
            signal_store.batch_insert_signals(results)
        summary = [{"id": r.strategy_id, "name": r.strategy_name, "status": r.status,
                    "confidence": r.confidence} for r in results]
        return {"success": True, "data": {"evaluated": len(results), "results": summary}, "error": None}
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"success": False, "data": None, "error": str(exc)},
        )

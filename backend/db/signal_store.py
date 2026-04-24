import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

_db_path: Optional[Path] = None


def initialize(db_path: Path):
    """Create the database and tables if they do not exist. Must be called once at startup."""
    global _db_path
    _db_path = db_path
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).parent / "schema.sql"
    with sqlite3.connect(str(db_path)) as conn:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()

    logger.info(f"Database ready at {db_path}")


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_db_path))
    c.row_factory = sqlite3.Row
    return c


def _serialize(row: dict) -> dict:
    out = row.copy()
    for key in ("reasons_for", "reasons_against"):
        if isinstance(out.get(key), list):
            out[key] = json.dumps(out[key])
    for key in ("timestamp", "next_event_time"):
        if isinstance(out.get(key), datetime):
            out[key] = out[key].isoformat()
    return out


def insert_signal(signal: dict) -> int:
    signal = _serialize(signal)
    signal.setdefault("outcome", "PENDING")
    sql = """
        INSERT INTO signals (
            timestamp, strategy_id, strategy_name, status, direction,
            entry, sl, tp1, tp2, tp3, rrr, confidence, probability,
            timeframes, reasons_for, reasons_against, verdict_summary, outcome
        ) VALUES (
            :timestamp, :strategy_id, :strategy_name, :status, :direction,
            :entry, :sl, :tp1, :tp2, :tp3, :rrr, :confidence, :probability,
            :timeframes, :reasons_for, :reasons_against, :verdict_summary, :outcome
        )
    """
    with _conn() as conn:
        cursor = conn.execute(sql, signal)
        conn.commit()
        return cursor.lastrowid


def get_signals(page: int = 1, per_page: int = 50, strategy_id: Optional[int] = None) -> dict:
    conditions, params = [], []
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with _conn() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM signals {where}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT * FROM signals {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            params + [per_page, (page - 1) * per_page],
        ).fetchall()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [dict(r) for r in rows],
    }


def get_signal_by_id(signal_id: int) -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()
    return dict(row) if row else None


def get_latest_by_strategy() -> List[dict]:
    """Most recent signal per strategy — used by /api/strategies."""
    sql = """
        SELECT * FROM signals
        WHERE id IN (SELECT MAX(id) FROM signals GROUP BY strategy_id)
        ORDER BY strategy_id
    """
    with _conn() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(r) for r in rows]


def insert_market_context(context: dict) -> int:
    context = _serialize(context)
    sql = """
        INSERT INTO market_context (
            timestamp, usdjpy_price, us10y, dxy, vix, fed_rate, boj_rate,
            next_event, next_event_time
        ) VALUES (
            :timestamp, :usdjpy_price, :us10y, :dxy, :vix, :fed_rate, :boj_rate,
            :next_event, :next_event_time
        )
    """
    with _conn() as conn:
        cursor = conn.execute(sql, context)
        conn.commit()
        return cursor.lastrowid


def get_latest_market_context() -> Optional[dict]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM market_context ORDER BY timestamp DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def get_signal_counts() -> dict:
    """Aggregate counts by status — used by /api/dashboard."""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as n FROM signals GROUP BY status"
        ).fetchall()
    counts = {"VALID": 0, "WAIT": 0, "NO_TRADE": 0}
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] = row["n"]
    return counts


def is_initialized() -> bool:
    return _db_path is not None and _db_path.exists()

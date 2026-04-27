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
        _migrate(conn)
        conn.commit()

    logger.info(f"Database ready at {db_path}")


def _migrate(conn: sqlite3.Connection):
    """Add columns introduced in Phase 2+ if they don't exist yet."""
    new_columns = [
        ("strategy_type", "TEXT"),
        ("wait_zone", "TEXT"),
        ("conditions_to_meet", "TEXT"),
        ("agent_scores", "TEXT"),
        ("outcome", "TEXT DEFAULT 'PENDING'"),
        ("telegram_failed", "INTEGER DEFAULT 0"),
    ]
    for col, col_type in new_columns:
        try:
            conn.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_db_path))
    c.row_factory = sqlite3.Row
    return c


def _serialize(row: dict) -> dict:
    out = row.copy()
    for key in ("reasons_for", "reasons_against", "conditions_to_meet", "agent_scores"):
        if isinstance(out.get(key), (list, dict)):
            out[key] = json.dumps(out[key])
    for key in ("timestamp", "next_event_time"):
        if isinstance(out.get(key), datetime):
            out[key] = out[key].isoformat()
    return out


def insert_signal(signal: dict) -> int:
    signal = _serialize(signal)
    signal.setdefault("outcome", "PENDING")

    _insert_sql = """
        INSERT INTO signals (
            timestamp, strategy_id, strategy_name, strategy_type, status, direction,
            entry, sl, tp1, tp2, tp3, rrr, confidence, probability,
            timeframes, wait_zone, conditions_to_meet,
            reasons_for, reasons_against, verdict_summary, agent_scores, outcome
        ) VALUES (
            :timestamp, :strategy_id, :strategy_name, :strategy_type, :status, :direction,
            :entry, :sl, :tp1, :tp2, :tp3, :rrr, :confidence, :probability,
            :timeframes, :wait_zone, :conditions_to_meet,
            :reasons_for, :reasons_against, :verdict_summary, :agent_scores, :outcome
        )
    """
    with _conn() as conn:
        # Deduplication: if an identical signal (same strategy/status/entry/sl) exists
        # in the last 4 hours, update its timestamp instead of inserting a new row.
        existing = conn.execute(
            """SELECT id FROM signals
               WHERE strategy_id = ? AND status = ? AND entry IS ? AND sl IS ?
                 AND timestamp >= datetime('now', '-4 hours')
               ORDER BY timestamp DESC LIMIT 1""",
            (signal["strategy_id"], signal["status"],
             signal.get("entry"), signal.get("sl")),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE signals SET timestamp = ? WHERE id = ?",
                (signal["timestamp"], existing["id"]),
            )
            conn.commit()
            return existing["id"]

        cursor = conn.execute(_insert_sql, signal)
        conn.commit()
        return cursor.lastrowid


def batch_insert_signals(signals: list) -> int:
    """Insert multiple StrategyResult objects from one evaluation cycle."""
    count = 0
    for signal in signals:
        if hasattr(signal, "to_db_dict"):
            insert_signal(signal.to_db_dict())
        elif isinstance(signal, dict):
            insert_signal(signal)
        count += 1
    return count


def get_signals(
    page: int = 1,
    per_page: int = 50,
    strategy_id: Optional[int] = None,
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
) -> dict:
    conditions, params = [], []
    if strategy_id is not None:
        conditions.append("strategy_id = ?")
        params.append(strategy_id)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if from_date is not None:
        conditions.append("date(timestamp) >= ?")
        params.append(from_date)
    if to_date is not None:
        conditions.append("date(timestamp) <= ?")
        params.append(to_date)

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
    counts = {"VALID_TRADE": 0, "WAIT_FOR_LEVELS": 0, "NO_TRADE": 0}
    for row in rows:
        if row["status"] in counts:
            counts[row["status"]] = row["n"]
    return counts


def update_signal_outcome(signal_id: int, outcome: str) -> bool:
    """Update the outcome field for one signal. Returns True if the row was found."""
    with _conn() as conn:
        cursor = conn.execute(
            "UPDATE signals SET outcome = ? WHERE id = ?",
            (outcome, signal_id),
        )
        conn.commit()
        return cursor.rowcount == 1


def mark_telegram_failed(strategy_id: int) -> None:
    """Mark the most recent signal for a strategy as telegram_failed=1."""
    with _conn() as conn:
        conn.execute(
            """UPDATE signals SET telegram_failed = 1
               WHERE id = (
                   SELECT id FROM signals WHERE strategy_id = ?
                   ORDER BY timestamp DESC LIMIT 1
               )""",
            (strategy_id,),
        )
        conn.commit()


def is_initialized() -> bool:
    return _db_path is not None and _db_path.exists()

CREATE TABLE IF NOT EXISTS signals (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp           DATETIME NOT NULL,
    strategy_id         INTEGER  NOT NULL,
    strategy_name       TEXT     NOT NULL,
    strategy_type       TEXT,
    status              TEXT     NOT NULL,  -- VALID_TRADE / WAIT_FOR_LEVELS / NO_TRADE
    direction           TEXT,               -- BUY / SELL / NULL
    entry               REAL,
    sl                  REAL,
    tp1                 REAL,
    tp2                 REAL,
    tp3                 REAL,
    rrr                 REAL,
    confidence          INTEGER,            -- 0-100
    probability         INTEGER,            -- 0-100
    timeframes          TEXT,               -- e.g. "H1/H4/D1"
    wait_zone           TEXT,
    conditions_to_meet  TEXT,               -- JSON array
    reasons_for         TEXT,               -- JSON array
    reasons_against     TEXT,               -- JSON array
    verdict_summary     TEXT,
    agent_scores        TEXT,               -- JSON object
    outcome             TEXT DEFAULT 'PENDING'  -- WIN / LOSS / PENDING
);

CREATE TABLE IF NOT EXISTS market_context (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       DATETIME NOT NULL,
    usdjpy_price    REAL,
    us10y           REAL,
    dxy             REAL,
    vix             REAL,
    fed_rate        REAL,
    boj_rate        REAL,
    next_event      TEXT,
    next_event_time DATETIME
);

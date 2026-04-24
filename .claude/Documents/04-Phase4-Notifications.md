# Phase 4 — Notifications & Signal History

**Phase:** 4 of 5  
**Goal:** Wire up Telegram alerts for VALID TRADE signals and surface the signal history log in the frontend. Both are additive features — they do not change the strategy engine or frontend structure built in earlier phases.  
**Deliverable:** A Telegram message fires on every new VALID TRADE verdict. Signal history is queryable and viewable. The system is now fully operational for live monitoring.

---

## What Gets Built in This Phase

### 1. Telegram Bot Integration (`notifications/telegram_bot.py`)

#### Connection
- Uses the user's existing Telegram bot (token already available)
- Same bot, same chat window — messages are prefixed with `[USDJPY Smart Agent]` to distinguish them from other alerts in the shared chat
- Uses `python-telegram-bot` library (async-compatible with FastAPI)

#### When It Fires
- Fires **only** when a strategy transitions to `VALID_TRADE` status
- Does **not** fire on WAIT FOR LEVELS or NO TRADE
- Does **not** re-fire if the same strategy remains VALID on the next evaluation cycle — only fires on the **transition** (first time a strategy becomes VALID in a given session)
- If multiple strategies become VALID in the same evaluation cycle, sends one message per strategy (not batched into one wall of text)

#### Message Format

```
[USDJPY Smart Agent] 🔔 VALID TRADE

Strategy: Multi-Timeframe Trend Alignment (#1)
Direction: BUY
Entry: 149.850
Stop Loss: 149.200  (-65 pips)
TP1: 150.500  (+65 pips)
TP2: 151.150  (+130 pips)
Risk-Reward: 1:2
Confidence: 82/100
Timeframes: H1 / H4 / D

Why: H4 higher-low confirmed, H1 MACD bullish cross, Daily EMA structure intact, DXY supportive
Against: VIX slightly elevated, spread 1.2 pips

Evaluated: 14:02 UTC
```

#### Error Handling
- If Telegram send fails (network issue, bot blocked, etc.): log the error and write a `telegram_failed` flag to the signal record in SQLite — do not crash the evaluation cycle
- Retry once after 30 seconds on failure — if retry also fails, log and move on

---

### 2. Signal History Log

The SQLite `signals` table was created in Phase 1. Phase 4 completes the write path and adds the read/display layer.

#### What Gets Written (per evaluation cycle)
- Every strategy result is written to the `signals` table regardless of verdict (VALID, WAIT, NO TRADE)
- This creates a full historical record of every evaluation
- The `outcome` column defaults to `PENDING` for VALID and WAIT signals — the user can manually update this to WIN or LOSS after the trade resolves
- NO TRADE signals have `outcome` set to `N/A`

#### Deduplication Logic
- If the same strategy produces the same verdict with the same entry/SL within a 4-hour window, do not write a duplicate row — update the existing record's `evaluated_at` timestamp instead
- This prevents the signal log from filling up with thousands of identical NO TRADE rows for quiet strategies

#### Signal History API (`api/history.py`)
- `GET /api/history` — returns paginated list of all signals, most recent first
  - Query params: `page`, `per_page` (default 50), `status` (filter), `strategy_id` (filter)
- `GET /api/history/{id}` — single signal record with full detail
- `PATCH /api/history/{id}/outcome` — update outcome field (WIN / LOSS / N/A)

---

### 3. History Page (frontend addition)

A simple fourth page: `history.html`  
Add "History" link to the navigation bar.

#### Layout

**Filter row:**
- Dropdown: All Strategies / Strategy 1 / Strategy 2 ... / Strategy 20
- Dropdown: All Statuses / Valid Trade / Wait / No Trade
- Date range picker (from / to)
- "Apply Filters" button

**Table:**
Columns: Timestamp (UTC) | Strategy | Status | Direction | Entry | SL | TP1 | RRR | Confidence | Outcome

- Status column uses color-coded badge (same as cards)
- Direction column uses BUY/SELL chip
- Outcome column: WIN (green) / LOSS (red) / PENDING (grey) / N/A (muted)
- Clicking any row opens that signal's detail view (reuses `detail.html` logic)
- Inline outcome editing: clicking the Outcome cell on a PENDING row shows a dropdown (WIN / LOSS) to update it without leaving the page

**Summary stats bar (above table):**
Aggregated across the filtered view:
- Total signals shown
- VALID TRADE count
- Win rate (of resolved signals): e.g., "Win Rate: 67% (8/12 resolved)"
- Average confidence of VALID signals

---

### 4. Navigation Update

Add "History" to the navigation bar across all four pages. Navigation is now:
- Dashboard | Strategies | History

---

## Phase 4 Success Criteria

By the end of Phase 4, the following must all be true:

1. A test VALID TRADE result triggers a Telegram message within 30 seconds
2. Telegram message format matches the defined template exactly
3. The same strategy going VALID twice in the same hour does not send two identical messages
4. If Telegram fails, the system logs the failure but continues evaluating normally
5. `GET /api/history` returns a paginated list of signals
6. The history page renders the table correctly with color-coded status and outcome columns
7. Filtering by strategy or status on the history page works correctly
8. Outcome can be updated inline from PENDING to WIN or LOSS
9. Win rate stat in the summary bar is calculated correctly
10. Signal deduplication is working — same NO TRADE strategy does not create thousands of rows overnight

---

## Known Constraints for This Phase

- The Telegram token and chat ID must be stored in environment variables — never hardcoded
- `python-telegram-bot` v20+ uses async — ensure the send function is properly awaited within FastAPI's async context
- The "transition to VALID" detection requires comparing current evaluation results to the previous cycle's results — the scheduler must cache last-cycle results in memory for this comparison
- History page win rate is only meaningful once a reasonable number of VALID signals have been resolved — show "Insufficient data" if fewer than 10 resolved signals exist
- SQLite write volume is low (20 rows per hour maximum) — no performance concerns

# Phase 3 — Frontend

**Phase:** 3 of 5  
**Goal:** Build all three frontend pages that visualise live strategy verdicts and market context. No frameworks — pure HTML, CSS, and vanilla JavaScript polling the FastAPI backend.  
**Deliverable:** A fully functional local website accessible at `http://localhost:8000`. Dashboard, 20 strategy cards, and full strategy detail pages all rendering live data.

---

## What Gets Built in This Phase

### Technology Constraints
- Pure HTML5, CSS3, vanilla JavaScript — no React, Vue, or any build tools
- All three pages served directly by FastAPI as static files
- JavaScript uses `fetch()` to poll FastAPI endpoints every 60 seconds
- A visible auto-refresh countdown is always shown on screen
- No external CSS frameworks (no Bootstrap, Tailwind) — custom styles only, keep it lightweight

---

### 1. Shared Elements (across all pages)

**Navigation bar:**
- "USDJPY Smart Agent" title on the left
- Links: Dashboard / Strategies
- MT5 connection status indicator (green dot = connected, red = disconnected)
- Current USDJPY price (live, updates every 60s)
- Current UTC time
- Auto-refresh countdown: "Refreshing in: 47s"

**Color system:**
| Status | Border / Background | Text |
|---|---|---|
| VALID TRADE | Green (#22c55e) | White |
| WAIT FOR LEVELS | Amber (#f59e0b) | Dark |
| NO TRADE | Dark grey (#374151) | Muted grey |
| BUY direction | Green chip (#16a34a) | White |
| SELL direction | Red chip (#dc2626) | White |
| Positive / supporting | Light green tint | Green text |
| Negative / opposing | Light red tint | Red text |

---

### 2. Dashboard (`index.html`)

#### Layout: Three Rows

**Row 1 — Live Price + Session Bar**
- Large USDJPY price display (bid / ask / spread)
- Current trading session: Tokyo / London / New York / Off-Hours (highlighted in session color)
- Time to next session open

**Row 2 — Market Context Strip**
Four tiles side by side:
- **DXY**: current value + direction arrow (up/down vs previous day)
- **US10Y**: current yield + direction arrow
- **VIX**: current value + risk regime label (Low / Elevated / High based on thresholds)
- **Next Event**: event name, time remaining countdown, impact badge (High / Medium)

**Row 3 — Two Columns**

*Left column — Signal Summary:*
- Three large count badges: VALID TRADE (green) / WAIT FOR LEVELS (amber) / NO TRADE (grey)
- Shows count of strategies in each state out of 20
- Example: "3 VALID | 5 WAIT | 12 NO TRADE"

*Right column — Active Signals Panel:*
- Lists all current VALID TRADE and WAIT FOR LEVELS results
- Each entry shows: strategy name, direction chip, entry price, SL, TP1, confidence score
- Clicking any entry navigates to that strategy's detail page
- If no active signals: "No active setups at this time"

---

### 3. Strategy Cards (`strategies.html`)

#### Filter Bar (top of page)
Four toggle buttons: **All** | **Valid Trade** | **Wait for Levels** | **No Trade**
- Active filter is highlighted
- Card count shown next to each filter: e.g., "All (20) | Valid (3) | Wait (5) | No Trade (12)"

#### Card Grid
20 cards in a responsive grid (4 columns on wide screens, 2 on medium, 1 on narrow).

**Each card contains:**

Top section:
- Strategy number (small, muted)
- Strategy name (bold)
- Type badge: pill-shaped label — Trend / Breakout / Mean Reversion / Hybrid / Event-Driven
- Timeframe tags: small grey chips — e.g., H1 / H4 / D

Middle section (trade parameters — only shown if VALID or WAIT):
- Direction chip: BUY (green) or SELL (red), large and prominent
- Entry price
- Stop Loss
- TP1 price
- Risk-Reward Ratio

Bottom section:
- Confidence score: shown as a horizontal bar + numeric value
- Status label (VALID TRADE / WAIT FOR LEVELS / NO TRADE) in status color
- Last evaluated: "14 mins ago" (relative time from `evaluated_at`)

**Card border:**
- VALID TRADE: solid 2px green left border + subtle green background tint
- WAIT FOR LEVELS: solid 2px amber left border + subtle amber background tint
- NO TRADE: solid 1px grey border, no tint

**On hover:** card lifts slightly (CSS box-shadow transition)  
**On click:** navigate to `detail.html?strategy={id}`

---

### 4. Strategy Detail (`detail.html`)

Receives `?strategy={id}` query parameter. Fetches `GET /api/strategy/{id}`.

#### Section 1 — Header
- Back button → strategies.html
- Strategy name (large heading)
- Type badge + Timeframe tags
- Status badge (large, color-coded)
- Evaluated at: exact UTC timestamp

#### Section 2 — Trade Parameters
Displayed as a clean parameter grid (shown only if VALID or WAIT):

| Parameter | Value |
|---|---|
| Direction | BUY / SELL (colored chip) |
| Entry | price |
| Stop Loss | price (+ pips distance) |
| Take Profit 1 | price (+ pips gain) |
| Take Profit 2 | price |
| Take Profit 3 | price (if available) |
| Risk-Reward | ratio |

For WAIT FOR LEVELS: also shows "Wait Zone" and "Conditions to Meet" list.

#### Section 3 — Scores
Two horizontal progress bars side by side:
- **Confidence Score**: 0–100 bar, colored by value (green ≥ 75, amber 50–74, red < 50)
- **Probability Score**: same styling

#### Section 4 — 4-Agent Debate
Four collapsible sections, one per agent:
- "Opportunity Agent 1" — expand to see scored dimensions and key findings
- "Opportunity Agent 2" — expand to see scored dimensions and key findings
- "Risk Agent 1" — expand to see risk flags and scored dimensions
- "Risk Agent 2" — expand to see risk flags and scored dimensions

Each agent section shows:
- Agent score (e.g., "Score: 7.5/10")
- List of conditions evaluated: ✓ (met) or ✗ (not met) or ⚠ (partially met)
- Any specific flags raised

#### Section 5 — Verdict Summary
Two-column layout:
- **Left — Supporting Reasons:** green-tinted box, bulleted list
- **Right — Opposing Reasons:** red-tinted box, bulleted list

Below both columns:
- **Final Decision Summary:** one paragraph narrative from `verdict_summary` field

---

### 5. Auto-Refresh Mechanism (shared across all pages)

- JavaScript polling interval: 60 seconds
- A visible countdown timer in the nav bar updates every second
- On each refresh cycle: fetch relevant API endpoint, re-render changed data
- Only re-render DOM elements whose data has changed (avoid full page flicker)
- If API returns an error (MT5 disconnected, server down): show a non-intrusive warning banner — do not blank the page, keep showing last known data with a "stale data" indicator

---

### 6. Responsive Behaviour

- Dashboard: stacks to single column on narrow screens
- Strategy cards: 4 → 2 → 1 column grid based on viewport width
- Detail page: trade parameter grid and agent debate sections stack vertically on narrow screens
- Navigation collapses to a minimal bar on very narrow screens

---

### 7. Static File Serving (FastAPI)

FastAPI mounts the `frontend/` directory as static files at `/`. Visiting `http://localhost:8000` serves `index.html`. All HTML, CSS, and JS files are served from this mount. No separate web server required.

---

## Phase 3 Success Criteria

By the end of Phase 3, the following must all be true:

1. `http://localhost:8000` opens the Dashboard with live USDJPY price displayed
2. Market context strip shows DXY, US10Y, VIX, and next calendar event
3. Signal summary counts are correct and match what `/api/strategies` returns
4. `strategies.html` shows all 20 cards with correct status colors and direction chips
5. Filter buttons correctly hide/show cards by status
6. Clicking a card navigates to the correct detail page
7. Detail page shows all 4-agent debate sections for that strategy
8. Auto-refresh countdown is visible and counts down on all pages
9. If MT5 disconnects, a warning banner appears without crashing the page
10. All pages are functional with no JavaScript console errors

---

## Known Constraints for This Phase

- All time display should be in UTC — this avoids ambiguity across sessions (Tokyo/London/NY)
- The detail page's `?strategy={id}` parameter must be validated — if an invalid id is passed, show a graceful error message
- The auto-refresh polling must not fire a new request if the previous request is still in flight — add a simple in-flight guard in the JS
- No charts in this phase — candlestick charts are a future enhancement, not required for core functionality
- Styling should be dark-themed by default — traders prefer dark interfaces for long monitoring sessions

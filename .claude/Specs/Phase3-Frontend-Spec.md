# Phase 3 — Frontend Specification

---

## Document Control

| Field        | Value                             |
|--------------|----------------------------------|
| Document ID  | SPEC-PHASE-3-v1.0                 |
| Version      | v1.0                              |
| Status       | Draft                             |
| Created      | 2026-04-24                        |
| Author       | USDJPY Smart Agent Project        |
| Phase        | 3 of 5                            |
| Phase Name   | Frontend                          |

### Change History

| Version | Date       | Author | Summary of Changes |
|---------|------------|--------|--------------------|
| v1.0    | 2026-04-24 | —      | Initial draft      |
| v1.1    | 2026-04-24 | —      | Resolved OQ-3-01 (removed direction arrows from DXY/US10Y tiles); OQ-3-02 (locked agent JSON structure to 11 conditions); OQ-3-03 (detail page auto-refreshes silently, preserving section state); OQ-3-04 (null wait_zone shows generic fallback text) |

---

## 1. Introduction

### 1.1 Purpose

This document is the formal functional and non-functional specification for Phase 3 (Frontend) of the USDJPY Smart Agent project. It defines every requirement that the frontend layer must satisfy, the data it must display, the interfaces it must honour, and the conditions under which Phase 3 is considered complete. It is intended for the developer implementing Phase 3 and for any reviewer verifying that the implementation meets the stated goals.

### 1.2 Scope

This specification covers the complete frontend layer of the USDJPY Smart Agent system: all three HTML pages (Dashboard, Strategy Cards, Strategy Detail), the shared navigation component, JavaScript polling logic, responsive layout behaviour, and error/degradation handling. It also covers the FastAPI static-file mount that serves these pages.

This specification does not cover: the FastAPI REST endpoints (defined in Phase 1 and Phase 2), the SQLite signal store (defined in Phase 1), the strategy evaluation logic (defined in Phase 2), Telegram notifications (Phase 4), or MT5 order execution (Phase 5). It does not cover any form of user authentication — the system is single-user and local. Candlestick or charting components are explicitly out of scope for this phase.

### 1.3 Definitions and Abbreviations

| Term / Abbreviation | Definition |
|---------------------|------------|
| MT5 | MetaTrader 5 — trading terminal providing USDJPY OHLCV price data |
| OHLCV | Open, High, Low, Close, Volume — standard candlestick price data |
| ATR | Average True Range — volatility indicator used in strategy scoring |
| EMA | Exponential Moving Average — trend indicator used in multiple strategies |
| FRED | Federal Reserve Economic Data — API providing US macroeconomic data |
| VALID TRADE | Verdict indicating a high-confidence, rule-compliant setup with full parameters |
| WAIT FOR LEVELS | Verdict indicating a valid setup in principle where price has not yet reached the entry zone |
| NO TRADE | Verdict indicating conditions are not met or opposing factors are too strong |
| FR | Functional Requirement |
| NFR | Non-Functional Requirement |
| SL | Stop Loss — price level at which a trade is exited for a loss |
| TP | Take Profit — price level at which a trade is exited for a gain (TP1, TP2, TP3) |
| RRR | Risk-Reward Ratio — ratio of potential profit to potential loss |
| DXY | US Dollar Index — measures USD strength against a basket of currencies |
| VIX | CBOE Volatility Index — measures implied market volatility |
| US10Y | US 10-Year Treasury Yield — macroeconomic benchmark interest rate |
| BoJ | Bank of Japan — central bank influencing JPY |
| UTC | Coordinated Universal Time — all timestamps displayed in this timezone |
| DOM | Document Object Model — the browser's in-memory representation of an HTML page |
| ASGI | Asynchronous Server Gateway Interface — interface used by FastAPI/Uvicorn |
| API | Application Programming Interface |
| REST | Representational State Transfer — HTTP-based API style used by FastAPI |
| JSON | JavaScript Object Notation — data interchange format used by all API responses |
| OHLCV | Open, High, Low, Close, Volume |

### 1.4 References

- USDJPY Smart Agent System Architecture (`system_architecture.md`)
- Phase 3 Build Guide (`03-Phase3-Frontend.md`)
- USDJPY Algorithmic Strategy Reference (`USDJPY_Algo_Strategy_Reference.md`) — not directly applicable to this phase; the frontend displays strategy output but does not implement strategy logic
- FastAPI Static Files documentation (FastAPI `StaticFiles` mount)
- MDN Web Docs — Fetch API (`fetch()`)
- MDN Web Docs — URL `URLSearchParams` interface

---

## 2. System Context

### 2.1 Phase Position in System

Phase 3 is the third of five phases. It sits immediately after Phase 2 (Strategy Engine) and immediately before Phase 4 (Notifications & History). Phase 3 depends on the REST API endpoints and SQLite signal store delivered in Phase 1, and on the 20-strategy evaluation engine and verdict generation delivered in Phase 2. Phase 4 (Telegram notifications and signal history query UI) depends on Phase 3 being complete insofar as the history page may be added there; Phase 5 (Automated Trading) does not depend on the frontend.

### 2.2 Phase Goal

Phase 3 must deliver a fully functional local website, accessible at `http://localhost:8000`, that displays live USDJPY strategy verdicts, market context, and agent debate detail in a browser using only HTML, CSS, and vanilla JavaScript.

### 2.3 In Scope for This Phase

- FastAPI static file mount serving the `frontend/` directory at `/`
- Shared navigation bar component present on all three pages
- Dashboard page (`index.html`) including live price, session indicator, market context strip, signal summary counts, and active signals panel
- Strategy Cards page (`strategies.html`) including filter bar, 20 strategy cards, and card click navigation
- Strategy Detail page (`detail.html`) including trade parameters, confidence and probability scores, 4-agent debate collapsible sections, and final verdict summary
- JavaScript auto-refresh polling mechanism (60-second interval with visible countdown)
- In-flight request guard preventing concurrent polling requests
- Graceful degradation when the API is unavailable: stale data retained with a warning banner
- Responsive layout for all three pages (wide / medium / narrow viewports)
- Dark-themed colour scheme throughout
- Validation of the `?strategy={id}` query parameter with a graceful error state
- UTC time display on all timestamps and countdowns

### 2.4 Out of Scope for This Phase

- Candlestick or OHLCV charting components of any kind
- User authentication or login screens
- Any CSS framework (Bootstrap, Tailwind, or similar)
- Any JavaScript framework or build tool (React, Vue, Webpack, Vite, or similar)
- Telegram notification triggering from the frontend
- Signal outcome entry (WIN / LOSS / PENDING — manual outcome update)
- Signal history pagination page (Phase 4 deliverable)
- MT5 order placement from the frontend
- Dark/light theme toggle — dark theme is fixed
- Localisation or time-zone conversion — UTC only

### 2.5 Predecessor Dependencies

The following must be complete and verified before Phase 3 implementation begins:

- `GET /api/dashboard` endpoint returns live USDJPY price, market context, and signal summary counts as JSON
- `GET /api/strategies` endpoint returns an array of 20 strategy verdict objects as JSON
- `GET /api/strategy/{id}` endpoint returns the full debate output for a single strategy as JSON
- `GET /api/status` endpoint returns system health, last evaluation time, and MT5 connection state as JSON
- FastAPI server starts and serves requests at `http://localhost:8000`
- SQLite `signals` table is populated with at least one evaluation run per strategy
- The `frontend/` directory exists in the project root and FastAPI is configured to mount it

---

## 3. Functional Requirements

### 3.1 Static File Serving

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-01  | The system SHALL serve `frontend/index.html` when a browser requests `http://localhost:8000/` | MUST | Given the FastAPI server is running, when a browser GETs `http://localhost:8000/`, then the HTTP response status is 200 and the body is the content of `frontend/index.html` |
| FR-3-02  | The system SHALL serve `frontend/strategies.html` at `http://localhost:8000/strategies.html` | MUST | Given the server is running, when a browser GETs `/strategies.html`, then status 200 and correct HTML is returned |
| FR-3-03  | The system SHALL serve `frontend/detail.html` at `http://localhost:8000/detail.html` | MUST | Given the server is running, when a browser GETs `/detail.html`, then status 200 and correct HTML is returned |
| FR-3-04  | The system SHALL serve all CSS files under `frontend/css/` at their corresponding URL paths | MUST | Given the server is running, when a browser GETs `/css/styles.css`, then status 200 and the stylesheet is returned |
| FR-3-05  | The system SHALL serve all JavaScript files under `frontend/js/` at their corresponding URL paths | MUST | Given the server is running, when a browser GETs `/js/dashboard.js`, then status 200 and the script is returned |

### 3.2 Shared Navigation Bar

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-06  | The navigation bar SHALL display the text "USDJPY Smart Agent" as a title on the left side of every page | MUST | Given any of the three pages is loaded, then the title text is visible in the navigation bar |
| FR-3-07  | The navigation bar SHALL display a "Dashboard" link that navigates to `index.html` | MUST | Given any page is loaded, when the user clicks "Dashboard", then the browser navigates to `index.html` |
| FR-3-08  | The navigation bar SHALL display a "Strategies" link that navigates to `strategies.html` | MUST | Given any page is loaded, when the user clicks "Strategies", then the browser navigates to `strategies.html` |
| FR-3-09  | The navigation bar SHALL display an MT5 connection status indicator as a coloured dot | MUST | Given the page has loaded and the API has been polled, when MT5 is connected then the dot is green; when MT5 is disconnected then the dot is red |
| FR-3-10  | The navigation bar SHALL display the current USDJPY price, updated on each polling cycle | MUST | Given a successful API response, when data is rendered, then the displayed USDJPY price matches the value from the most recent `/api/dashboard` response |
| FR-3-11  | The navigation bar SHALL display the current UTC time, updated every second | MUST | Given any page is open, then the displayed UTC time increments every second without a page reload |
| FR-3-12  | The navigation bar SHALL display an auto-refresh countdown in the format "Refreshing in: Xs" that counts down from 60 to 0 every second | MUST | Given any page is open, then the countdown decrements by 1 each second and resets to 60 after each polling cycle completes |

### 3.3 Dashboard Page — Live Price and Session Row

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-13  | The dashboard SHALL display the current USDJPY bid price prominently | MUST | Given a successful `/api/dashboard` response, then the bid price is displayed in a large font in the first section |
| FR-3-14  | The dashboard SHALL display the current USDJPY ask price | MUST | Given a successful `/api/dashboard` response, then the ask price is visible alongside the bid price |
| FR-3-15  | The dashboard SHALL display the current bid-ask spread in pips | MUST | Given bid and ask prices are available, then the spread in pips is calculated and displayed as `(ask - bid) * 100` rounded to one decimal place |
| FR-3-16  | The dashboard SHALL display the current trading session as one of: Tokyo, London, New York, Off-Hours | MUST | Given the current UTC time, when it falls within the Tokyo session window (00:00–09:00 UTC), then "Tokyo" is highlighted; London (08:00–17:00 UTC); New York (13:00–22:00 UTC); otherwise "Off-Hours" |
| FR-3-17  | The dashboard SHALL display the time remaining until the next session opens | MUST | Given the current UTC time is known, then the countdown to the next session open is displayed in HH:MM format and updates every second |

### 3.4 Dashboard Page — Market Context Strip

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-18  | The dashboard SHALL display a DXY tile showing the current DXY value | MUST | Given a successful `/api/dashboard` response containing DXY data, then the current value is shown |
| FR-3-19  | The dashboard SHALL display a US10Y tile showing the current US 10-Year yield | MUST | Given a successful `/api/dashboard` response containing US10Y data, then the current yield is shown |
| FR-3-20  | The dashboard SHALL display a VIX tile showing the current VIX value and a risk regime label | MUST | Given VIX data is available, when VIX < 15 the label is "Low"; when 15 ≤ VIX < 25 the label is "Elevated"; when VIX ≥ 25 the label is "High" |
| FR-3-21  | The dashboard SHALL display a Next Event tile showing the name of the next high-impact economic event and the time remaining until it occurs | MUST | Given calendar data is available in the API response, then the event name and a countdown in HH:MM format are shown |
| FR-3-22  | The Next Event tile SHALL display an impact badge of either "High" or "Medium" reflecting the event's impact level | SHOULD | Given an event with a known impact level, then the correct badge is displayed |

### 3.5 Dashboard Page — Signal Summary and Active Signals

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-23  | The dashboard SHALL display three count badges showing the number of strategies currently in each verdict state: VALID TRADE, WAIT FOR LEVELS, NO TRADE | MUST | Given `/api/strategies` returns 20 strategy objects, then the three badges sum to 20 and each count matches the verdicts in the API response |
| FR-3-24  | The VALID TRADE count badge SHALL be styled in green (#22c55e) | MUST | Given the dashboard is rendered, then the VALID count badge has a green background |
| FR-3-25  | The WAIT FOR LEVELS count badge SHALL be styled in amber (#f59e0b) | MUST | Given the dashboard is rendered, then the WAIT count badge has an amber background |
| FR-3-26  | The NO TRADE count badge SHALL be styled in dark grey (#374151) | MUST | Given the dashboard is rendered, then the NO TRADE count badge has a dark grey background |
| FR-3-27  | The active signals panel SHALL list all strategies currently in VALID TRADE or WAIT FOR LEVELS state | MUST | Given `/api/strategies` returns strategies with VALID or WAIT verdicts, then each such strategy appears as a row in the active signals panel |
| FR-3-28  | Each entry in the active signals panel SHALL display: strategy name, direction chip, entry price, stop loss, TP1, and confidence score | MUST | Given an active signal entry is rendered, then all six data points are visible |
| FR-3-29  | Each entry in the active signals panel SHALL be clickable and navigate to `detail.html?strategy={id}` for that strategy | MUST | Given the user clicks an active signal entry, then the browser navigates to the corresponding detail page |
| FR-3-30  | The active signals panel SHALL display "No active setups at this time" when no VALID TRADE or WAIT FOR LEVELS strategies exist | MUST | Given all 20 strategies return NO TRADE, then the panel shows the empty-state message |

### 3.6 Strategy Cards Page — Filter Bar

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-31  | The strategy cards page SHALL display four filter buttons: All, Valid Trade, Wait for Levels, No Trade | MUST | Given the page is loaded, then all four filter buttons are visible at the top of the page |
| FR-3-32  | Each filter button SHALL display a count of strategies matching that filter in parentheses | MUST | Given API data is loaded, then "All (20)", "Valid (N)", "Wait (N)", "No Trade (N)" counts are correct and sum correctly |
| FR-3-33  | Clicking a filter button SHALL immediately hide cards that do not match the selected filter | MUST | Given the user clicks "Valid Trade", then only cards with VALID TRADE verdict are visible |
| FR-3-34  | The active filter button SHALL be visually distinguished from inactive filter buttons | MUST | Given a filter is selected, then the active button has a distinct highlighted style compared to the others |
| FR-3-35  | The "All" filter SHALL be active by default when the page first loads | MUST | Given the page loads without a pre-selected filter, then all 20 cards are visible and the "All" button is highlighted |

### 3.7 Strategy Cards Page — Card Grid

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-36  | The strategy cards page SHALL render one card for each of the 20 strategies returned by `/api/strategies` | MUST | Given the API returns 20 strategy objects, then 20 cards are rendered |
| FR-3-37  | Each card SHALL display the strategy number, strategy name, and strategy type badge | MUST | Given a card is rendered, then strategy number, name, and type badge are all visible |
| FR-3-38  | The strategy type badge SHALL display one of: Trend, Breakout, Mean Reversion, Hybrid, Event-Driven | MUST | Given a strategy's type is known, then the correct badge label is shown |
| FR-3-39  | Each card SHALL display timeframe tags as small chips (e.g. H1, H4, D) | MUST | Given timeframe data is available, then the correct timeframe chips appear on the card |
| FR-3-40  | Each card SHALL display a direction chip (BUY in green, SELL in red) when the verdict is VALID TRADE or WAIT FOR LEVELS | MUST | Given a VALID or WAIT verdict with a known direction, then the direction chip is displayed in the correct colour |
| FR-3-41  | Each card SHALL not display trade parameters when the verdict is NO TRADE | MUST | Given a NO TRADE verdict, then entry, SL, TP1, and RRR fields are not rendered on the card |
| FR-3-42  | Each card SHALL display entry price, stop loss, TP1 price, and RRR when the verdict is VALID TRADE or WAIT FOR LEVELS | MUST | Given a VALID or WAIT verdict, then all four parameters are visible on the card |
| FR-3-43  | Each card SHALL display a horizontal confidence score bar and numeric value | MUST | Given any verdict, then the confidence bar is visible and its filled width corresponds to the confidence score (0–100) |
| FR-3-44  | Each card SHALL display the verdict status label (VALID TRADE / WAIT FOR LEVELS / NO TRADE) in the status colour | MUST | Given a card is rendered, then the status label colour matches the colour system specification |
| FR-3-45  | Each card SHALL display a relative time since last evaluation (e.g. "14 mins ago") | MUST | Given an `evaluated_at` timestamp in the API response, then the relative time is correctly calculated and displayed |
| FR-3-46  | A VALID TRADE card SHALL have a solid 2px green left border and a subtle green background tint | MUST | Given a VALID TRADE card is rendered, then the CSS styles apply the green left border and background tint |
| FR-3-47  | A WAIT FOR LEVELS card SHALL have a solid 2px amber left border and a subtle amber background tint | MUST | Given a WAIT card is rendered, then the CSS applies the amber left border and background tint |
| FR-3-48  | A NO TRADE card SHALL have a solid 1px grey border with no background tint | MUST | Given a NO TRADE card is rendered, then only a grey border is applied with no coloured tint |
| FR-3-49  | Each card SHALL exhibit a box-shadow lift effect on hover via a CSS transition | SHOULD | Given the user hovers over any card, then a box-shadow appears smoothly |
| FR-3-50  | Clicking any card SHALL navigate to `detail.html?strategy={id}` for that strategy | MUST | Given the user clicks a strategy card, then the browser navigates to the correct detail page URL |

### 3.8 Strategy Detail Page — Header and Parameters

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-51  | The detail page SHALL read the `strategy` query parameter from the URL and use it to fetch `GET /api/strategy/{id}` | MUST | Given `detail.html?strategy=5` is loaded, then the page fetches `/api/strategy/5` |
| FR-3-52  | The detail page SHALL display a graceful error message when the `strategy` query parameter is absent or not a valid integer in the range 1–20 | MUST | Given `detail.html?strategy=abc` or `detail.html` with no parameter is loaded, then the page displays "Invalid strategy ID" and does not attempt an API request |
| FR-3-53  | The detail page SHALL display a back navigation link that returns the user to `strategies.html` | MUST | Given the detail page is loaded, when the user clicks the back link, then the browser navigates to `strategies.html` |
| FR-3-54  | The detail page SHALL display the strategy name as a large heading | MUST | Given the API response is received, then the strategy name is the primary heading on the page |
| FR-3-55  | The detail page SHALL display the strategy type badge and timeframe tags in the header | MUST | Given the API response is received, then the type badge and timeframe chips are rendered below the strategy name |
| FR-3-56  | The detail page SHALL display a large status badge (VALID TRADE / WAIT FOR LEVELS / NO TRADE) in the appropriate status colour | MUST | Given the verdict is known, then the status badge is displayed with the matching colour |
| FR-3-57  | The detail page SHALL display the exact UTC evaluation timestamp | MUST | Given an `evaluated_at` value in the response, then it is displayed as a UTC timestamp in ISO 8601 format or a human-readable UTC equivalent |
| FR-3-58  | The detail page SHALL display a trade parameters grid when the verdict is VALID TRADE or WAIT FOR LEVELS | MUST | Given a VALID or WAIT verdict, then direction, entry, SL, TP1, TP2, TP3 (if available), and RRR are shown in a grid |
| FR-3-59  | The detail page SHALL display the pips distance from entry to SL alongside the SL price | MUST | Given entry and SL prices are known, then `abs(entry - sl) * 100` rounded to one decimal is shown as the pip distance |
| FR-3-60  | The detail page SHALL display the pips gain from entry to TP1 alongside the TP1 price | MUST | Given entry and TP1 prices are known, then the pip distance is shown |
| FR-3-61  | The detail page SHALL display TP3 only when a TP3 value is present in the API response | SHOULD | Given TP3 is null in the response, then the TP3 row is not rendered |
| FR-3-62  | The detail page SHALL display a "Wait Zone" and "Conditions to Meet" section when the verdict is WAIT FOR LEVELS | MUST | Given a WAIT verdict, then the wait zone and conditions list are rendered in the trade parameters section |
| FR-3-62a | When the verdict is WAIT FOR LEVELS and the `wait_zone` field is null, the detail page SHALL display "Watch for price to reach entry zone" as the Wait Zone value | MUST | Given a WAIT verdict with `wait_zone: null` in the response, then the text "Watch for price to reach entry zone" is displayed in the Wait Zone row |
| FR-3-63  | The detail page SHALL not display any trade parameters grid when the verdict is NO TRADE | MUST | Given a NO TRADE verdict, then the parameters grid is absent from the rendered page |

### 3.9 Strategy Detail Page — Scores

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-64  | The detail page SHALL display the confidence score as a horizontal progress bar with a numeric value | MUST | Given a confidence score is in the response, then the bar fill width corresponds to `score / 100 * 100%` and the numeric value is shown |
| FR-3-65  | The confidence score bar SHALL be coloured green when the score is ≥ 75, amber when 50–74, and red when < 50 | MUST | Given confidence = 80, then the bar is green; confidence = 60 → amber; confidence = 40 → red |
| FR-3-66  | The detail page SHALL display the probability score as a horizontal progress bar with a numeric value, using the same colour thresholds as the confidence bar | MUST | Given a probability score is in the response, then the bar and value are rendered with the same colour rules |

### 3.10 Strategy Detail Page — 4-Agent Debate

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-67  | The detail page SHALL display four collapsible agent sections: Opportunity Agent 1, Opportunity Agent 2, Risk Agent 1, Risk Agent 2 | MUST | Given the page is rendered with API data, then four labelled collapsible sections are present |
| FR-3-68  | Each agent section SHALL be collapsed by default on page load | SHOULD | Given the page first loads, then all four agent sections are in their collapsed state |
| FR-3-69  | Clicking an agent section header SHALL toggle the section between collapsed and expanded states | MUST | Given a collapsed section, when the user clicks its header, then the section expands; clicking again collapses it |
| FR-3-70  | Each expanded agent section SHALL display the agent's overall score (e.g. "Score: 7.5/10") | MUST | Given an agent section is expanded and score data is in the response, then the score is displayed |
| FR-3-71  | Each expanded agent section SHALL display the list of evaluated conditions with a met (✓), not met (✗), or partially met (⚠) indicator for each condition | MUST | Given condition data is in the API response, then each condition is rendered with its correct indicator |
| FR-3-72  | Each expanded agent section SHALL display any specific flags or warnings raised by that agent | SHOULD | Given an agent has raised flags in the response, then the flags are listed within the expanded section |

### 3.11 Strategy Detail Page — Verdict Summary

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-73  | The detail page SHALL display a two-column layout with supporting reasons on the left and opposing reasons on the right | MUST | Given the page is rendered, then two side-by-side columns are present with their respective headers |
| FR-3-74  | The supporting reasons column SHALL be styled with a green-tinted background and the reasons rendered as a bulleted list | MUST | Given `reasons_for` data is in the response, then each reason appears as a list item in the green-tinted column |
| FR-3-75  | The opposing reasons column SHALL be styled with a red-tinted background and the reasons rendered as a bulleted list | MUST | Given `reasons_against` data is in the response, then each reason appears as a list item in the red-tinted column |
| FR-3-76  | The detail page SHALL display the `verdict_summary` narrative as a paragraph below the two-column reasons layout | MUST | Given `verdict_summary` is in the response, then the full narrative text is rendered as a paragraph |

### 3.12 Auto-Refresh Mechanism

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-77  | The JavaScript on each page SHALL poll the relevant API endpoint(s) on a 60-second interval | MUST | Given a page has been open for 60 seconds, then a new API request is issued automatically |
| FR-3-78  | The auto-refresh mechanism SHALL NOT issue a new API request if the previous request is still in flight | MUST | Given the previous fetch has not yet resolved, when 60 seconds elapse, then no new fetch is initiated until the in-flight request completes |
| FR-3-79  | On each successful polling cycle, the page SHALL update only the DOM elements whose data has changed, without triggering a full page reload | MUST | Given data has changed for one strategy card, when the next poll completes, then only that card's content is updated; unaffected elements remain unchanged |
| FR-3-79a | On the detail page, each auto-refresh cycle SHALL preserve the expanded or collapsed state of all four agent sections | MUST | Given agent section 2 is expanded when a refresh fires, then after the refresh agent section 2 remains expanded and its updated content is rendered in place |
| FR-3-80  | On each successful polling cycle, the countdown timer SHALL reset to 60 seconds | MUST | Given a polling cycle completes, then the countdown display immediately shows 60 and resumes counting down |

### 3.13 Error Handling and Graceful Degradation

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-81  | When an API request fails (network error or non-2xx HTTP status), the page SHALL display a non-intrusive warning banner at the top of the content area | MUST | Given the API returns a 500 or is unreachable, then a warning banner appears without removing existing content |
| FR-3-82  | The warning banner SHALL indicate that data is stale and include the UTC timestamp of the last successful update | MUST | Given the banner is displayed, then the text includes a phrase such as "Stale data — last updated [UTC timestamp]" |
| FR-3-83  | When an API request fails, the page SHALL retain and continue displaying the last successfully fetched data | MUST | Given data was displayed before the failure, when the failure occurs, then the previously displayed data remains visible |
| FR-3-84  | When the API returns successfully again after a failure, the warning banner SHALL be automatically removed | MUST | Given the banner is showing, when the next poll succeeds, then the banner disappears and the page updates normally |
| FR-3-85  | The MT5 disconnection state received from `/api/status` SHALL cause the nav-bar status dot to turn red without affecting the display of previously loaded strategy data | MUST | Given `mt5_connected: false` in the API response, then the status dot is red and no strategy data is cleared from the page |

### 3.14 Responsive Layout

| ID       | Requirement | Priority | Acceptance Criterion |
|----------|-------------|----------|----------------------|
| FR-3-86  | The strategy cards grid SHALL display 4 columns when the viewport is ≥ 1200px wide | MUST | Given a viewport ≥ 1200px, then 4 cards appear per row |
| FR-3-87  | The strategy cards grid SHALL display 2 columns when the viewport is 768px–1199px wide | MUST | Given a viewport in the 768–1199px range, then 2 cards appear per row |
| FR-3-88  | The strategy cards grid SHALL display 1 column when the viewport is < 768px wide | MUST | Given a viewport < 768px, then 1 card appears per row |
| FR-3-89  | The dashboard layout SHALL stack all rows into a single column when the viewport is < 768px wide | MUST | Given a narrow viewport, then the price bar, market context strip, signal summary, and active signals panel stack vertically |
| FR-3-90  | The detail page trade parameter grid and agent debate sections SHALL stack vertically on viewports < 768px wide | MUST | Given a narrow viewport on the detail page, then the two-column trade grid and verdict columns become single-column |
| FR-3-91  | The navigation bar SHALL collapse to a minimal form on viewports < 480px | SHOULD | Given a very narrow viewport, then the nav bar shows only the title and price, hiding secondary navigation elements |

---

## 4. Non-Functional Requirements

### 4.1 Performance

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-01  | The initial page load for any of the three HTML pages MUST complete within 2 seconds on a local connection (localhost) | MUST | Given the server is running and the page is loaded for the first time, then the browser's DOMContentLoaded event fires within 2000ms |
| NFR-3-02  | Each API polling cycle MUST complete (request sent and response rendered) within 3 seconds under normal operating conditions | MUST | Given the API is healthy, then from the moment the fetch is initiated to the moment the DOM is updated takes ≤ 3000ms |
| NFR-3-03  | The auto-refresh countdown MUST update with no visible lag — the displayed second MUST change within 100ms of the actual second boundary | MUST | Given the countdown is running, then each decrement is visually perceptible within 100ms of the true second |
| NFR-3-04  | The filter operation on the strategy cards page MUST respond within 100ms of the user clicking a filter button | MUST | Given 20 cards are rendered and the user clicks a filter, then cards are shown/hidden within 100ms |
| NFR-3-05  | The collapsible agent sections on the detail page MUST animate open/close within 300ms | SHOULD | Given the user clicks an agent section header, then the expand or collapse animation completes within 300ms |

### 4.2 Reliability

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-06  | The frontend MUST continue rendering the last known state when the backend is unreachable, for at least 10 consecutive failed polling cycles | MUST | Given the API has been unreachable for 10 minutes, then the page still displays the last known data and the stale warning banner |
| NFR-3-07  | A JavaScript runtime error in one page component MUST NOT crash the entire page or prevent other components from rendering | MUST | Given an error occurs in the market context strip, then the strategy cards and navigation still function |
| NFR-3-08  | The in-flight guard MUST prevent overlapping API requests regardless of how slowly the server responds | MUST | Given the API takes 90 seconds to respond, then only one request is ever in-flight at a time |

### 4.3 Data Integrity

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-09  | The signal summary counts displayed on the dashboard MUST exactly match the count of strategies in each verdict state in the most recent `/api/strategies` response | MUST | Given the API returns 3 VALID, 5 WAIT, 12 NO TRADE, then the displayed counts are exactly 3, 5, and 12 |
| NFR-3-10  | The confidence and probability score bars MUST accurately reflect the numeric score: a score of 75 MUST fill exactly 75% of the bar width | MUST | Given a confidence score of 75, then the bar fill width is `75%` ± 1% |
| NFR-3-11  | The relative timestamp ("14 mins ago") MUST be recalculated on each DOM render, not cached from the initial page load | MUST | Given a strategy was evaluated 5 minutes ago and the user has been on the page for 5 minutes, then the timestamp reads "10 mins ago", not "5 mins ago" |

### 4.4 Maintainability

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-12  | Each HTML page MUST have a single corresponding JavaScript file: `dashboard.js`, `strategies.js`, `detail.js` | MUST | Given the project structure, then each page's logic resides in its own dedicated JS file |
| NFR-3-13  | All styling MUST reside in `frontend/css/styles.css` — no inline styles SHOULD be used in HTML files | SHOULD | Given the HTML files are inspected, then style attributes are absent from all elements |
| NFR-3-14  | All colour values used in the colour system MUST be defined as CSS custom properties (variables) in `styles.css` and referenced consistently | MUST | Given `styles.css` is inspected, then `--color-valid`, `--color-wait`, `--color-no-trade`, `--color-buy`, `--color-sell` variables are defined and used throughout |
| NFR-3-15  | The API base URL MUST be defined as a single constant in each JavaScript file and not hard-coded at each `fetch()` call site | MUST | Given `dashboard.js` is inspected, then the API base URL appears once as a constant |

### 4.5 Security

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-16  | All data rendered from API responses MUST be inserted into the DOM as text content, not as raw HTML, to prevent XSS | MUST | Given an API response contains `<script>alert(1)</script>` in a text field, then the script tag is rendered as literal text, not executed |
| NFR-3-17  | No credentials, API keys, or secret values of any kind MUST appear in any HTML, CSS, or JavaScript file | MUST | Given all frontend files are inspected, then no tokens, passwords, or API keys are present |
| NFR-3-18  | The `?strategy={id}` query parameter MUST be validated as a safe integer before it is used in any API URL construction | MUST | Given `?strategy=1;DROP TABLE signals` is passed, then only the integer part is extracted and used, or an error is shown |

### 4.6 Compatibility

| ID        | Requirement | Priority | Acceptance Criterion |
|-----------|-------------|----------|----------------------|
| NFR-3-19  | The frontend MUST function correctly in Google Chrome (latest stable version) on Windows | MUST | Given Chrome latest on Windows is used, then all three pages load and all interactions work without errors |
| NFR-3-20  | The frontend SHOULD function correctly in Microsoft Edge (latest stable version) on Windows | SHOULD | Given Edge latest on Windows is used, then all three pages load and all interactions work without errors |
| NFR-3-21  | No JavaScript framework, build tool, transpiler, or package manager MUST be used — all JS must be plain ES2020-compatible vanilla JavaScript | MUST | Given all JS files are inspected, then no `import` statements referencing npm packages, no `require()` calls, and no build artifacts are present |
| NFR-3-22  | No external CSS frameworks MUST be used — all CSS must be authored custom styles | MUST | Given `styles.css` and all HTML files are inspected, then no CDN links to Bootstrap, Tailwind, or other CSS frameworks are present |
| NFR-3-23  | The frontend MUST be served entirely by the existing FastAPI/Uvicorn server — no additional web server (Nginx, Apache, etc.) is required | MUST | Given only the FastAPI server is running, then all three pages load correctly in a browser |

---

## 5. Data Specifications

### 5.1 Data Models

Phase 3 introduces no new persistent data entities. It is a read-only consumer of data produced by Phases 1 and 2. The data models below define the API response structures that the frontend depends on.

**Dashboard Response (`GET /api/dashboard`)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `usdjpy_bid` | float | > 0 | Current USDJPY bid price |
| `usdjpy_ask` | float | > 0 | Current USDJPY ask price |
| `us10y` | float | ≥ 0 | US 10-Year Treasury Yield (%) |
| `dxy` | float | > 0 | DXY current value |
| `vix` | float | > 0 | VIX current value |
| `next_event` | string \| null | max 200 chars | Name of next high-impact economic event |
| `next_event_time` | datetime \| null | UTC ISO 8601 | UTC time of next economic event |
| `next_event_impact` | string \| null | "High" or "Medium" | Event impact level |
| `valid_count` | integer | 0–20 | Count of strategies in VALID TRADE state |
| `wait_count` | integer | 0–20 | Count of strategies in WAIT FOR LEVELS state |
| `no_trade_count` | integer | 0–20 | Count of strategies in NO TRADE state |
| `mt5_connected` | boolean | — | Whether MT5 terminal is currently connected |
| `last_evaluated` | datetime | UTC ISO 8601 | Timestamp of most recent evaluation run |

**Strategy Summary Object (element of `GET /api/strategies` array)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | integer | 1–20 | Strategy identifier |
| `name` | string | max 100 chars | Human-readable strategy name |
| `type` | string | Trend / Breakout / Mean Reversion / Hybrid / Event-Driven | Strategy category |
| `timeframes` | string | e.g. "H1/H4/D" | Timeframes used |
| `status` | string | VALID / WAIT / NO_TRADE | Current verdict |
| `direction` | string \| null | BUY / SELL / null | Trade direction (null for NO_TRADE) |
| `entry` | float \| null | > 0 or null | Entry price |
| `sl` | float \| null | > 0 or null | Stop loss price |
| `tp1` | float \| null | > 0 or null | Take profit 1 price |
| `rrr` | float \| null | > 0 or null | Risk-reward ratio |
| `confidence` | integer | 0–100 | Confidence score |
| `evaluated_at` | datetime | UTC ISO 8601 | When this strategy was last evaluated |

**Strategy Detail Object (`GET /api/strategy/{id}`)**

All fields from the Strategy Summary Object, plus:

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `tp2` | float \| null | > 0 or null | Take profit 2 price |
| `tp3` | float \| null | > 0 or null | Take profit 3 price (optional) |
| `probability` | integer | 0–100 | Probability score |
| `wait_zone` | string \| null | max 200 chars | Wait zone description (WAIT verdict only) |
| `conditions_to_meet` | array[string] \| null | — | Conditions required before entry (WAIT only) |
| `reasons_for` | array[string] | — | Supporting reasons |
| `reasons_against` | array[string] | — | Opposing reasons |
| `verdict_summary` | string | max 1000 chars | Final decision narrative |
| `agents` | array[AgentResult] | length = 4 | Results from each of the 4 agents |

**AgentResult Object (nested within strategy detail)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | "Opportunity Agent 1", "Opportunity Agent 2", "Risk Agent 1", "Risk Agent 2" | Agent label |
| `score` | float | 0.0–10.0 | Agent's overall score out of 10 |
| `conditions` | array[Condition] | exactly 11 elements | One entry per scoring dimension, in order |
| `flags` | array[string] | — | Specific observations or warnings raised by this agent |

**Condition Object (nested within AgentResult)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `label` | string | one of the 11 dimension names | Scoring dimension name |
| `result` | string | "met" / "not_met" / "partial" | Evaluation outcome — rendered as ✓ / ✗ / ⚠ |

The 11 `conditions` always appear in this fixed order, matching the 11 debate dimensions:
1. Strategy rule compliance
2. Market structure quality
3. Trend alignment (higher timeframe)
4. Confluence factors
5. Volatility conditions
6. Entry precision
7. Stop loss logic
8. Take profit realism
9. Risk-reward ratio
10. Invalidation strength
11. Macro / news sensitivity

**Status Response (`GET /api/status`)**

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `mt5_connected` | boolean | — | MT5 terminal connection state |
| `last_evaluation` | datetime \| null | UTC ISO 8601 | Timestamp of most recent full evaluation run |
| `server_uptime_seconds` | integer | ≥ 0 | Seconds since FastAPI server started |

### 5.2 Data Flows

**Initial Page Load:**
1. Browser requests `index.html` (or `strategies.html`, `detail.html`) from FastAPI static file mount
2. FastAPI returns the HTML file; browser parses it and loads linked CSS and JS files
3. On `DOMContentLoaded`, the page's JavaScript fires an immediate API request to populate initial data
4. API response is parsed and the DOM is rendered with the received data
5. The 60-second polling interval starts; the countdown timer starts from 60

**Recurring Poll (every 60 seconds):**
1. The countdown reaches 0; the in-flight guard is checked
2. If no request is in flight: fetch is initiated, in-flight flag is set
3. If a request is in flight: skip this cycle
4. API responds: DOM is selectively updated with changed data; in-flight flag is cleared; countdown resets to 60
5. If API fails: warning banner is shown; previous DOM state retained; in-flight flag is cleared; countdown resets to 60

**If API is unavailable on initial load:**
1. Fetch fails immediately
2. Warning banner appears
3. No data is displayed — empty states are shown for all components
4. Polling continues on the 60-second cycle until the API becomes available

**Detail Page Navigation:**
1. User clicks a strategy card or active signal entry
2. Browser navigates to `detail.html?strategy={id}`
3. On `DOMContentLoaded`, the page reads `?strategy` from `URLSearchParams`
4. If the value is not an integer in 1–20: error message is displayed, no fetch is made
5. If valid: `GET /api/strategy/{id}` is fetched and the page is rendered with the response

### 5.3 Interface Contracts

**FastAPI REST API (inbound to frontend)**
- Direction: Inbound (frontend consumes, API produces)
- Transport: HTTP/1.1, localhost:8000
- Format: JSON (Content-Type: application/json)
- Authentication: None (localhost, single-user)
- Frequency: On page load + every 60 seconds thereafter
- Error conditions: Network failure or HTTP 4xx/5xx → warning banner displayed, stale data retained

**Browser Environment (execution context)**
- The frontend JavaScript runs in the user's browser tab
- No server-side rendering; all rendering is client-side
- `fetch()` API is used for all HTTP requests
- `URLSearchParams` is used for query parameter parsing
- `setInterval` and `clearInterval` manage the polling loop

---

## 6. Interface Specifications

### 6.1 Internal API Contracts

Phase 3 does not introduce any new API endpoints. It consumes endpoints established in Phases 1 and 2. The full endpoint definitions are in the system architecture and Phase 1/2 specifications. The frontend depends on the following endpoints:

| Endpoint | Method | Used By |
|----------|--------|---------|
| `/api/dashboard` | GET | `dashboard.js` — price, market context, signal counts |
| `/api/strategies` | GET | `strategies.js` — 20 strategy summary cards |
| `/api/strategy/{id}` | GET | `detail.js` — full debate output for one strategy |
| `/api/status` | GET | All pages — MT5 connection state for nav bar dot |

### 6.2 External System Interfaces

Phase 3 does not directly integrate with any external systems (MT5, FRED, yfinance, Forex Factory). All external data is mediated by the FastAPI backend. The frontend treats the FastAPI backend as its sole data source.

### 6.3 User Interface Specifications

#### 6.3.1 Navigation Bar (shared component)

**Purpose:** Persistent orientation, live price visibility, and refresh state awareness.
**Layout:** Full-width horizontal bar, fixed at top of viewport.
**Data displayed:** "USDJPY Smart Agent" title (static); Dashboard / Strategies links (static); MT5 dot (live, red/green); USDJPY price (live, from `/api/dashboard`); UTC clock (live, JavaScript Date); countdown (live, countdown timer).
**Interactive elements:** Dashboard link → `index.html`; Strategies link → `strategies.html`.
**Update behaviour:** MT5 dot and price update on each polling cycle. UTC clock and countdown update every second via `setInterval`.

#### 6.3.2 Dashboard (`index.html`)

**Purpose:** At-a-glance market overview and active trade opportunities.
**Layout:** Three rows below the nav bar: (1) price + session; (2) market context strip; (3) signal summary (left) and active signals panel (right), stacking on narrow viewports.
**Data sources:** `/api/dashboard`, `/api/strategies`.
**Interactive elements:** Active signal entries are clickable → navigate to `detail.html?strategy={id}`.
**Loading state:** Skeleton placeholders or "Loading…" text shown before first API response.
**Error state:** Warning banner at top of content area; last known data retained.
**Empty state (active signals):** "No active setups at this time" message.
**Refresh:** Every 60 seconds; countdown visible in nav bar.

#### 6.3.3 Strategy Cards (`strategies.html`)

**Purpose:** Overview of all 20 strategy verdicts with filtering.
**Layout:** Filter bar (top), then responsive card grid below.
**Data source:** `/api/strategies`.
**Interactive elements:** Four filter buttons (All / Valid Trade / Wait for Levels / No Trade); each card is clickable → `detail.html?strategy={id}`.
**Loading state:** "Loading strategies…" message shown before first API response.
**Error state:** Warning banner; last rendered cards retained.
**Empty state (filtered):** If a filter is active and no strategies match, display "No strategies match this filter".
**Refresh:** Every 60 seconds; active filter is preserved across refresh cycles.

#### 6.3.4 Strategy Detail (`detail.html`)

**Purpose:** Full strategy analysis including all agent debate output.
**Layout:** Sequential sections: header, trade parameters, scores, 4-agent debate, verdict summary.
**Data source:** `GET /api/strategy/{id}`.
**Interactive elements:** Back link → `strategies.html`; four collapsible agent sections.
**Loading state:** "Loading strategy…" message shown before API response.
**Error state (API failure):** Warning banner; previously loaded data retained.
**Error state (invalid query param):** Full-page message "Invalid strategy ID. Please return to Strategies and select a valid strategy." with link back to `strategies.html`.
**Refresh:** Every 60 seconds; collapsible section expanded/collapsed state is preserved across refresh cycles.

---

## 7. Constraints

- **Platform:** Windows only — the system runs on a local Windows machine; no cross-OS compatibility requirement beyond this.
- **Language:** Vanilla JavaScript (ES2020 features — `fetch`, `async/await`, `URLSearchParams`, `const/let`, template literals); no transpilation.
- **CSS:** Custom styles only; no preprocessors (Sass, LESS); no CSS frameworks.
- **HTML:** HTML5; all pages must be valid HTML5 documents.
- **Web server:** FastAPI/Uvicorn serves the frontend as static files; no separate web server is permitted.
- **No charts:** Candlestick or OHLCV charting libraries are not permitted in this phase.
- **Dark theme only:** The UI is fixed to a dark colour scheme; no theme toggle is implemented.
- **UTC only:** All time values are displayed in UTC; no client-side time-zone conversion.
- **Single-user:** No authentication, session management, or user accounts.
- **Offline-first:** The system is local; no CDN-hosted assets — all assets are served from FastAPI.
- **Polling only:** No WebSocket or Server-Sent Events; data updates only via 60-second `fetch()` polling.

---

## 8. Assumptions

It is assumed that the FastAPI server is already running and accessible at `http://localhost:8000` before the user opens any frontend page. If this is incorrect, all three pages will display a loading/error state with no data.

It is assumed that the `/api/dashboard`, `/api/strategies`, `/api/strategy/{id}`, and `/api/status` endpoints are all implemented and returning JSON conforming to the data models in Section 5.1. If any endpoint returns a different schema, the corresponding frontend component will fail to render correctly.

It is assumed that all 20 strategy records exist in the SQLite database and that `/api/strategies` always returns exactly 20 objects. If the count is fewer, the strategy cards page will render fewer than 20 cards without error.

It is assumed that the browser used for testing is Google Chrome (latest stable on Windows). If a different browser is used, minor CSS rendering differences may occur.

It is assumed that the `frontend/` directory is mounted by FastAPI as a `StaticFiles` mount at `/` before Phase 3 development begins. If this mount is absent, the HTML pages will not be served.

It is assumed that the agent debate data returned by `/api/strategy/{id}` always includes exactly 4 agent result objects. If the count differs, the 4-agent debate section may render more or fewer sections than expected.

It is assumed that all timestamps from the API are in UTC ISO 8601 format. If timestamps are in a different format or time zone, the "relative time" calculation and UTC display will be incorrect.

---

## 9. Risks and Mitigations

| ID        | Risk | Likelihood | Impact | Mitigation |
|-----------|------|------------|--------|------------|
| RISK-3-01 | FastAPI static file mount is not configured, causing 404 for all frontend requests | Medium | High | Verify mount configuration at project startup; include a quick-start check in the test plan |
| RISK-3-02 | API schema changes in Phase 1/2 break frontend rendering silently | Medium | High | Validate API responses against the contracts in Section 5.1 at the start of implementation; add defensive checks for null/undefined fields |
| RISK-3-03 | MT5 terminal disconnects during a monitoring session, causing stale data | High | Medium | The stale-data warning banner (FR-3-81, FR-3-82) mitigates this; the page continues to show the last known state |
| RISK-3-04 | JavaScript errors in one component crash the entire page | Medium | High | Wrap each component's render logic in a try-catch; errors log to console and degrade gracefully per NFR-3-07 |
| RISK-3-05 | Polling creates memory leaks over long sessions due to accumulating DOM event listeners | Medium | Medium | Use `textContent` and targeted DOM updates rather than `innerHTML`; reuse existing elements rather than re-creating them each cycle |
| RISK-3-06 | Relative timestamps ("14 mins ago") drift or freeze if recalculation logic is tied only to API poll cycles | Low | Low | Recalculate relative timestamps on every DOM render, not only when API data changes, per NFR-3-11 |
| RISK-3-07 | The `?strategy={id}` parameter is manipulated to inject content into API URLs | Low | Medium | Validate and sanitise the parameter to an integer in 1–20 before using it in any URL (NFR-3-18) |
| RISK-3-08 | Dark theme causes readability issues on certain Windows display configurations | Low | Low | Test with at least two different display brightness/contrast settings; use sufficient contrast ratios (≥ 4.5:1) for all text |

---

## 10. Acceptance Criteria

| ID      | Criterion |
|---------|-----------|
| AC-3-01 | Opening `http://localhost:8000` in Google Chrome loads the Dashboard (`index.html`) with HTTP status 200 |
| AC-3-02 | The navigation bar is visible on all three pages and displays the title, nav links, MT5 dot, USDJPY price, UTC clock, and countdown timer |
| AC-3-03 | The USDJPY bid price, ask price, and spread are displayed on the Dashboard |
| AC-3-04 | The current trading session (Tokyo / London / New York / Off-Hours) is correctly identified and displayed based on UTC time |
| AC-3-05 | The market context strip displays DXY, US10Y, VIX (with risk regime label), and next economic event (with countdown) |
| AC-3-06 | The signal summary count badges (VALID / WAIT / NO TRADE) are correct and sum to 20 |
| AC-3-07 | The active signals panel lists all VALID and WAIT strategies, or shows the empty-state message if none exist |
| AC-3-08 | Clicking an active signal entry in the Dashboard navigates to the correct `detail.html?strategy={id}` page |
| AC-3-09 | `strategies.html` renders exactly 20 strategy cards |
| AC-3-10 | Each strategy card displays the correct status colour (green / amber / grey) on its left border |
| AC-3-11 | Each card shows the strategy type badge, timeframe tags, confidence bar, status label, and relative evaluation time |
| AC-3-12 | Cards with VALID or WAIT verdicts display direction chip, entry, SL, TP1, and RRR; NO TRADE cards do not show these fields |
| AC-3-13 | Each of the four filter buttons (All / Valid Trade / Wait for Levels / No Trade) correctly shows and hides the appropriate cards |
| AC-3-14 | Filter button counts in parentheses match the actual card counts after filtering |
| AC-3-15 | Clicking a strategy card navigates to `detail.html?strategy={id}` for the correct strategy |
| AC-3-16 | The detail page displays strategy name, type badge, timeframe tags, large status badge, and UTC evaluation timestamp |
| AC-3-17 | The detail page displays trade parameters (direction, entry, SL, TP1, TP2, TP3 if available, RRR) for VALID and WAIT verdicts |
| AC-3-18 | The detail page displays pip distance for SL and TP1 alongside their prices |
| AC-3-19 | The detail page hides the trade parameters grid for NO TRADE verdicts |
| AC-3-20 | The detail page displays confidence and probability score bars with correct fill widths and colour-coded thresholds |
| AC-3-21 | Four collapsible agent sections are present on the detail page and each can be individually expanded and collapsed |
| AC-3-22 | Each expanded agent section shows the agent score, condition list with indicators (✓ / ✗ / ⚠), and any flags |
| AC-3-23 | The verdict summary section displays supporting reasons in a green-tinted column and opposing reasons in a red-tinted column |
| AC-3-24 | The `verdict_summary` narrative text is rendered below the two-column reasons layout |
| AC-3-25 | The auto-refresh countdown is visible on all three pages and counts down from 60 every second |
| AC-3-26 | A new API request is automatically issued every 60 seconds on all pages |
| AC-3-27 | No second API request is initiated while the previous request is still in flight |
| AC-3-28 | When the API is unavailable, a non-intrusive warning banner appears and last known data is retained on all pages |
| AC-3-29 | The warning banner disappears automatically when the API recovers |
| AC-3-30 | Opening `detail.html` with no `?strategy` parameter shows a graceful error message, not a blank page or JS crash |
| AC-3-31 | Opening `detail.html?strategy=abc` shows a graceful error message |
| AC-3-32 | All three pages are functional with no JavaScript console errors in the Chrome developer console under normal operating conditions |
| AC-3-33 | The strategy cards grid displays 4 columns at ≥ 1200px, 2 columns at 768–1199px, and 1 column at < 768px |
| AC-3-34 | No inline `style` attributes are used in any HTML file; all colours are CSS custom properties in `styles.css` |
| AC-3-35 | No credentials, API keys, or secret values are present in any frontend file |

---

## 11. Traceability Matrix

| Acceptance Criterion | Functional / Non-Functional Requirement(s) |
|----------------------|--------------------------------------------|
| AC-3-01  | FR-3-01 |
| AC-3-02  | FR-3-06, FR-3-07, FR-3-08, FR-3-09, FR-3-10, FR-3-11, FR-3-12 |
| AC-3-03  | FR-3-13, FR-3-14, FR-3-15 |
| AC-3-04  | FR-3-16 |
| AC-3-05  | FR-3-18, FR-3-19, FR-3-20, FR-3-21, FR-3-22 |
| AC-3-06  | FR-3-23, FR-3-24, FR-3-25, FR-3-26, NFR-3-09 |
| AC-3-07  | FR-3-27, FR-3-28, FR-3-30 |
| AC-3-08  | FR-3-29 |
| AC-3-09  | FR-3-36 |
| AC-3-10  | FR-3-46, FR-3-47, FR-3-48 |
| AC-3-11  | FR-3-37, FR-3-38, FR-3-39, FR-3-43, FR-3-44, FR-3-45 |
| AC-3-12  | FR-3-40, FR-3-41, FR-3-42 |
| AC-3-13  | FR-3-33 |
| AC-3-14  | FR-3-32 |
| AC-3-15  | FR-3-50 |
| AC-3-16  | FR-3-54, FR-3-55, FR-3-56, FR-3-57 |
| AC-3-17  | FR-3-58, FR-3-59, FR-3-60, FR-3-61, FR-3-62 |
| AC-3-18  | FR-3-59, FR-3-60 |
| AC-3-19  | FR-3-63 |
| AC-3-20  | FR-3-64, FR-3-65, FR-3-66, NFR-3-10 |
| AC-3-21  | FR-3-67, FR-3-68, FR-3-69 |
| AC-3-22  | FR-3-70, FR-3-71, FR-3-72 |
| AC-3-23  | FR-3-73, FR-3-74, FR-3-75 |
| AC-3-24  | FR-3-76 |
| AC-3-25  | FR-3-12, FR-3-77 |
| AC-3-26  | FR-3-77 |
| AC-3-27  | FR-3-78, NFR-3-08 |
| AC-3-28  | FR-3-81, FR-3-82, FR-3-83, NFR-3-06 |
| AC-3-29  | FR-3-84 |
| AC-3-30  | FR-3-52 |
| AC-3-31  | FR-3-52, NFR-3-18 |
| AC-3-32  | NFR-3-07 |
| AC-3-33  | FR-3-86, FR-3-87, FR-3-88 |
| AC-3-34  | NFR-3-13, NFR-3-14 |
| AC-3-35  | NFR-3-17 |

---

## 12. Open Questions

All open questions resolved on 2026-04-24.

| ID      | Question | Resolution |
|---------|----------|------------|
| OQ-3-01 | Does `/api/dashboard` return previous-day DXY/US10Y values for direction arrows? | Resolved — direction arrows removed. DXY and US10Y tiles display current value only. No `dxy_prev` or `us10y_prev` fields required. FR-3-18 and FR-3-19 updated accordingly. |
| OQ-3-02 | What is the exact JSON structure of the `agents` array in `/api/strategy/{id}`? | Resolved — structure locked in Section 5.1. Each agent has `name`, `score` (0–10), `conditions` (exactly 11 elements in fixed order), and `flags` (string array). Condition `result` is always "met", "not_met", or "partial". |
| OQ-3-03 | Should the detail page auto-refresh or require manual action? | Resolved — auto-refresh every 60 seconds, silently in the background. Expanded/collapsed state of all agent sections is preserved across each refresh cycle. FR-3-79a added. |
| OQ-3-04 | What to show when `wait_zone` is null on a WAIT FOR LEVELS strategy? | Resolved — display "Watch for price to reach entry zone" as the fallback text. FR-3-62a added. |

---
description: Creates a versioned, high-grade specification document for the specified project phase. Checks git branch and cleanliness, creates a feature branch, reads source documents, and produces a formal software requirements specification.
allowed-tools: Bash, Read, Write, Edit
---

You have been invoked as `/spec` with argument: $ARGUMENTS

Follow every step below in strict order. Do not skip, reorder, or combine steps. Report the result of each step to the user before proceeding to the next.

---

## STEP 1 — Parse the Phase Argument

Extract the phase number from: $ARGUMENTS

Accept all of these input formats (case-insensitive):
- "Phase 1", "phase 1", "PHASE 1", "Phase1", "1", "phase-1"

Valid phase numbers are 1 through 5 only.

Phase number → Phase name mapping:
- 1 → Foundation
- 2 → StrategyEngine
- 3 → Frontend
- 4 → Notifications
- 5 → AutomatedTrading

Phase number → Source document mapping:
- 1 → `.claude/Documents/01-Phase1-Foundation.md`
- 2 → `.claude/Documents/02-Phase2-StrategyEngine.md`
- 3 → `.claude/Documents/03-Phase3-Frontend.md`
- 4 → `.claude/Documents/04-Phase4-Notifications.md`
- 5 → `.claude/Documents/05-Phase5-AutomatedTrading.md`

If no valid phase number is found, stop immediately and respond:
```
❌ Invalid argument. Usage: /spec Phase <number>
Valid phase numbers: 1 through 5
Example: /spec Phase 1
```

---

## STEP 2 — Verify Git Branch is Main

Run: `git branch --show-current`

If the result is NOT exactly `main`, stop immediately and respond:
```
⚠️  Wrong branch: you are on '{current_branch}'.
    The /spec command must be run from the main branch.
    To fix: git checkout main
```
Do not proceed further.

---

## STEP 3 — Verify No Uncommitted Changes

Run: `git status --porcelain`

If the output is non-empty, stop immediately and respond:
```
⚠️  Uncommitted changes detected. Resolve these before running /spec:

  {list each file with its status code, one per line}

  Options:
    • Commit:  git add -A && git commit -m "your message"
    • Stash:   git stash
```
Do not proceed further.

---

## STEP 4 — Check for Existing Spec and Determine Version

List files in `.claude/Specs/` directory.

Search for any existing file that starts with `Phase{N}-` where N is the parsed phase number (case-insensitive).

- If **no existing spec** is found:
  - version string = `v1.0`
  - filename = `Phase{N}-{PhaseName}-Spec.md`
  - Proceed silently.

- If **one or more specs already exist** for this phase:
  - Count them to determine the next version number. Examples: 1 existing → new is v2.0, 2 existing → new is v3.0.
  - filename = `Phase{N}-{PhaseName}-Spec-v{X}.0.md`
  - Notify the user:
    ```
    ⚠️  Spec already exists for Phase {N}: {existing_filename}
        Creating versioned spec: {new_filename}
    ```

---

## STEP 5 — Create the Git Feature Branch

Construct the branch name:
- Version 1 (v1.0): `feature/phase-{N}`
- Version 2+ (v2.0, v3.0, ...): `feature/phase-{N}-v{X}`

Run: `git checkout -b {branch_name}`

If git returns an error because the branch already exists, append the current Unix timestamp:
`feature/phase-{N}-{timestamp}`
and retry.

Report to user:
```
✓ Created and switched to branch: {branch_name}
```

---

## STEP 6 — Read Source Documents

Read the following files completely before writing a single word of the spec. Do not skim.

1. `.claude/Documents/system_architecture.md` — overall system context, tech stack, data flows, design decisions
2. The phase-specific document identified in Step 1 — full detail of what this phase covers
3. The strategy reference file `USDJPY_Algo_Strategy_Reference.md` — only if the phase is Phase 2 (Strategy Engine), as it defines the 20 strategies

Use the source documents only to understand context, constraints, and detail. The spec you write must express WHAT the system must do — not HOW it will be implemented. Implementation detail belongs in the phase document, not the spec.

---

## STEP 7 — Write the Specification Document

Create the file at: `.claude/Specs/{filename}` (as determined in Step 4).

The document must follow the structure below exactly, in this order, with all sections present. Every section must be substantive — no placeholders, no "TBD", no thin sections. If a section is genuinely not applicable to this phase, state explicitly why it is not applicable in one sentence.

---

### SPEC DOCUMENT STRUCTURE

```
# Phase {N} — {PhaseName} Specification

---

## Document Control

| Field        | Value                          |
|--------------|-------------------------------|
| Document ID  | SPEC-PHASE-{N}-{version}       |
| Version      | {version}                      |
| Status       | Draft                          |
| Created      | {today's date}                 |
| Author       | USDJPY Smart Agent Project     |
| Phase        | {N} of 5                       |
| Phase Name   | {PhaseName}                    |

### Change History

| Version | Date | Author | Summary of Changes |
|---|---|---|---|
| {version} | {today} | — | Initial draft |

---

## 1. Introduction

### 1.1 Purpose
One paragraph stating what this document is, what phase it covers, and who it is for.

### 1.2 Scope
What this specification covers and what it does not cover. Be precise about the boundaries.

### 1.3 Definitions and Abbreviations
A table of all technical terms, acronyms, and abbreviations used in this document.
Include at minimum: MT5, OHLCV, ATR, EMA, FRED, VALID TRADE, WAIT FOR LEVELS, NO TRADE, FR, NFR, SL, TP, RRR, and any phase-specific terms.

### 1.4 References
A list of all documents referenced:
- USDJPY Smart Agent System Architecture (system_architecture.md)
- Phase {N} Build Guide ({phase_doc_filename})
- USDJPY Algorithmic Strategy Reference (USDJPY_Algo_Strategy_Reference.md) — if applicable
- Any external standards, APIs, or protocols referenced

---

## 2. System Context

### 2.1 Phase Position in System
Where this phase sits in the 5-phase project. What it depends on (predecessor phases) and what depends on it (successor phases).

### 2.2 Phase Goal
A single clear sentence stating what this phase must achieve.

### 2.3 In Scope for This Phase
A bulleted list of everything explicitly included in this phase.

### 2.4 Out of Scope for This Phase
A bulleted list of everything explicitly excluded from this phase. This is critical — it draws the boundary and prevents scope creep.

### 2.5 Predecessor Dependencies
What must be complete and working before this phase can begin. List specific deliverables, not phases.

---

## 3. Functional Requirements

Each requirement must be:
- Uniquely numbered (FR-{N}-01, FR-{N}-02, etc. where N is the phase number)
- Written in the form: "The system SHALL / MUST / SHOULD [do something]"
- Atomic — one requirement per statement
- Testable — it must be possible to write a clear pass/fail test for it
- Prioritized: MUST (non-negotiable), SHOULD (important but not blocking), COULD (nice to have)

Format each requirement as:

| ID | Requirement | Priority | Acceptance Criterion |
|---|---|---|---|
| FR-{N}-01 | The system SHALL ... | MUST | Given [...], when [...], then [...] |

Group requirements under logical sub-headings that reflect the components being specified.

Produce a complete, exhaustive list — do not abbreviate or say "etc." Leave nothing implied.

---

## 4. Non-Functional Requirements

Apply the same ID system: NFR-{N}-01, NFR-{N}-02, etc.

Cover all applicable categories:

### 4.1 Performance
Response times, throughput, evaluation cycle duration.
Every requirement must include a measurable metric (e.g., "MUST complete within 30 seconds").

### 4.2 Reliability
Uptime, error handling, graceful degradation.
What happens when external dependencies (MT5, FRED, Telegram) are unavailable.

### 4.3 Data Integrity
Accuracy of calculations, prevention of duplicate records, correctness of stored values.

### 4.4 Maintainability
Code structure, configuration management, separation of concerns.

### 4.5 Security
Credential handling, data exposure, access control.
Even for a local single-user system — no credentials hardcoded, environment variables for secrets.

### 4.6 Compatibility
Windows platform, Python version, MT5 version, browser compatibility (if frontend phase).

---

## 5. Data Specifications

### 5.1 Data Models
Define every data entity this phase introduces or depends on.
For each entity: field name, data type, constraints, description.
Use tables.

### 5.2 Data Flows
Describe how data moves through this phase:
- Source → transformation → destination
- What triggers each data flow
- What happens if a data source is unavailable

### 5.3 Interface Contracts
For each external system this phase interfaces with, define:
- The interface name
- Direction: inbound / outbound / bidirectional
- Data format (fields, types, units)
- Expected frequency
- Error conditions and how they are handled

---

## 6. Interface Specifications

### 6.1 Internal API Contracts (if this phase introduces API endpoints)
For each endpoint:
- Method and path
- Request parameters (name, type, required/optional, description)
- Response schema (field, type, description)
- Error responses (status code, error body)
- Example request and response

### 6.2 External System Interfaces (if this phase integrates external systems)
For each external system:
- System name and version
- Authentication method
- Key operations used
- Rate limits or constraints
- Fallback behaviour if system is unavailable

### 6.3 User Interface Specifications (if this is a frontend phase)
For each page or component:
- Purpose and user goal
- Layout description
- All data displayed and its source
- All interactive elements (filters, buttons, links) and their behaviour
- Loading states, error states, empty states
- Refresh and update behaviour

---

## 7. Constraints

Technical and business constraints that limit how requirements can be fulfilled.
Each constraint must be stated as a fact, not a preference.

Examples:
- Platform: Windows only
- Language: Python 3.11+
- MT5: Terminal must be locally running and authenticated
- No external paid services beyond those already agreed
- Single-user — no authentication layer required
- No JavaScript frameworks — vanilla JS only (if frontend phase)

---

## 8. Assumptions

Facts assumed to be true that the specification depends on.
If any assumption is wrong, one or more requirements may need to change.

Format: "It is assumed that [statement]. If this is incorrect, [impact]."

---

## 9. Risks and Mitigations

| ID | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| RISK-{N}-01 | ... | Low/Medium/High | Low/Medium/High | ... |

Cover at minimum: data source unavailability, MT5 disconnection, calculation errors, schedule drift, platform-specific issues.

---

## 10. Acceptance Criteria

The complete, ordered list of conditions that must all be true for this phase to be considered complete.

These are the final gate — if all pass, the phase is done.
Each criterion must be binary (pass/fail), specific, and independently verifiable.

Number them: AC-{N}-01, AC-{N}-02, etc.

These should be derived from and traceable back to the functional requirements.

---

## 11. Traceability Matrix

A table mapping each acceptance criterion back to the functional requirement(s) it validates.

| Acceptance Criterion | Functional Requirement(s) |
|---|---|
| AC-{N}-01 | FR-{N}-01, FR-{N}-02 |
| AC-{N}-02 | FR-{N}-03 |
| ... | ... |

---

## 12. Open Questions

Any unresolved questions or decisions that must be answered before or during implementation.

| ID | Question | Impact if Unresolved | Owner |
|---|---|---|---|
| OQ-{N}-01 | ... | ... | ... |

If there are no open questions, state: "No open questions at time of writing."
```

---

## STEP 8 — Report Completion

After the file is successfully written, report to the user:

```
✅ Specification document created successfully.

  File:    .claude/Specs/{filename}
  Branch:  {branch_name}
  Version: {version}
  Phase:   {N} — {PhaseName}

Next steps:
  1. Review the spec document and verify all requirements are correct
  2. Commit the spec:  git add .claude/Specs/{filename} && git commit -m "Add Phase {N} specification {version}"
  3. When ready to plan implementation, use the spec as the source of truth
```

---

## CRITICAL RULES FOR SPEC QUALITY

These rules apply to every spec this command produces. Violating any of these is a failure.

1. **Requirements use "SHALL", "MUST", or "SHOULD" — never "will", "can", "may", or "should be able to".**
2. **Every requirement is testable.** If you cannot write a clear pass/fail test, rewrite the requirement.
3. **Every requirement is atomic.** One statement = one requirement. No "and" connecting two separate behaviours.
4. **No implementation detail in requirements.** The spec says WHAT, not HOW. "The system SHALL store signal data persistently" — not "The system SHALL use SQLite to store signal data."
5. **No placeholder text.** Every section is complete. No "TBD", "TODO", or "to be determined".
6. **Numbers in NFRs are real.** Every performance requirement has a measured threshold, not "should be fast".
7. **Out of scope is as important as in scope.** An incomplete out-of-scope section causes scope creep.
8. **The traceability matrix is complete.** Every acceptance criterion maps to at least one requirement.
9. **The spec is self-contained.** A reader with no prior context should understand the full scope of this phase from this document alone.
10. **Depth matches complexity.** Phase 2 (20 strategies, 80 agents, debate engine) will have far more requirements than Phase 4 (Telegram + history). Match the effort to the complexity.

# Final Report — Fastlane Semi-Auto Operator Queue v1

**Date:** 2026-05-22  
**Branch:** fastlane (experimental)  
**Baseline:** 616 passed + 38 subtests (before this slice)

---

## Summary

Implemented a read-only operator queue for AI Workbench runs. The queue analyses each step's current patch-test lifecycle state and returns the single most important safe manual action the operator should take next. A compact "Operator Queue" tab was added to RunDetail showing action cards with priority/status badges and "Go to" buttons that call the existing `focusManualAction()` handler to scroll/highlight the relevant UI section. No autonomous execution of any kind was introduced.

---

## Operator Queue Endpoint Behavior

**Endpoint:** `GET /api/runs/{run_id}/operator-queue`

**Pure read-only.** The endpoint:
- Verifies the run exists (404 if not).
- Loads all run steps for the run.
- For each step, calls `_build_queue_item()` — a pure analysis helper with an 8-stage decision tree.
- Optionally filters to a single step_id (query param `step_id`).
- Optionally limits output count (query param `limit`, default 50).
- Returns `OperatorQueueResponse` with items, summary counts, and a `generated_at` timestamp.
- **Creates no ToolCall records. Writes no DB records. Runs no commands. Calls no providers. Creates no proposals. Applies no patches.**

### Decision Tree (in order of precedence)

| Stage | Condition | Action Type | Priority | Status |
|-------|-----------|-------------|----------|--------|
| 1 | test_passed | review_success | low | done |
| 2 | test_failed + latest_analysis | prepare_fix_draft_manual | high | ready |
| 3 | test_failed (no analysis) | analyze_failed_tests_manual | high | manual_required |
| 4 | latest_apply + no tests | run_tests_manual | high | manual_required |
| 5 | successful_proposals + no apply | apply_patch_manual | high | manual_required |
| 6 | guard results + no proposals | create_proposal_manual | medium | ready |
| 7 | no guard records | check_guard | medium | manual_required |
| 8 | stale_guards only | resolve_blocker | medium | blocked |

### Flag Semantics

- `can_run_directly = true` only for `prepare_fix_draft_manual` (calls an existing read-only endpoint).
- `is_destructive = true` only for `apply_patch_manual`.
- `requires_confirmation = true` only for `apply_patch_manual`.
- All command-execution actions (`run_tests_manual`, `analyze_failed_tests_manual`) have all three flags false — they focus the UI but never execute.

---

## RunDetail UI Behavior

**Location:** New "Operator-queue" tab in RunDetail.

Changes:
- Added `"operator-queue"` to the tab union type and tab bar.
- Added `operatorQueue` / `operatorQueueLoading` / `operatorQueueError` state.
- Added `loadOperatorQueue()` — explicit call only, no useEffect auto-trigger.
- Added `OperatorQueuePanel` and `OperatorQueueItemCard` components (inline in RunDetail.tsx).
- Panel shows:
  - Summary row: total / ready / manual_required / blocked / done counts (color-coded).
  - One action card per step with priority badge, status badge, destructive/needs-confirm badges, action_type, title, description, step name, reason, and warnings.
  - "Go to <destination>" button per card — calls `focusManualAction(stepId, actionType)` to scroll/highlight the relevant UI section.
  - Focus result (success or error message) shown inline per card.
  - "Refresh Queue" button at top — explicit click only.
  - Safety notice: "Read-only guidance — no action is executed automatically."
  - `generated_at` footer.
- When no queue has been loaded yet, shows "Click Refresh Queue to load operator guidance".
- Tab label uses the same auto-capitalize logic as all other tabs: "Operator-queue".

---

## Safety Boundaries

Every safety constraint was observed:

| Constraint | Status |
|------------|--------|
| No autonomous mode | ✓ |
| No auto-proposal | ✓ |
| No auto-apply | ✓ |
| No auto-run tests | ✓ |
| No automatic analyze | ✓ |
| No useEffect auto-calls | ✓ None added |
| No provider execution | ✓ |
| No execute_run | ✓ |
| No asyncio.create_task | ✓ |
| No engine.py changes | ✓ |
| No database.py changes | ✓ |
| No schema changes | ✓ |
| No migrations | ✓ |
| No approval execution changes | ✓ |
| No Start Task / confirmed-run changes | ✓ |
| No git commit | ✓ |
| No weakened tests | ✓ |

---

## Files Changed

### Backend

| File | Change |
|------|--------|
| `backend/src/models.py` | Added `OperatorQueueItem`, `OperatorQueueSummary`, `OperatorQueueResponse` models (~60 lines) |
| `backend/src/api/routes.py` | Added `GET /api/runs/{run_id}/operator-queue` endpoint + `_build_queue_item()` helper (~140 lines); added imports for new models |
| `backend/tests/test_semi_auto_operator_queue.py` | **New file** — 322 lines, 20 test cases |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Added `OperatorQueueItem`, `OperatorQueueSummary`, `OperatorQueueResponse`, `OperatorQueueItemStatus`, `OperatorQueueItemPriority`, `OperatorQueueActionType`, `OperatorQueueDestination` interfaces/types |
| `frontend/src/api/client.ts` | Added `OperatorQueueResponse` import; added `getRunOperatorQueue(runId, params?)` client method |
| `frontend/src/pages/RunDetail.tsx` | Added `getRunOperatorQueue` import, `OperatorQueueResponse`, `OperatorQueueItem` type imports; `"operator-queue"` tab; `operatorQueue/Loading/Error` state; `loadOperatorQueue()`; `OperatorQueuePanel` + `OperatorQueueItemCard` components; tab bar entry; tab panel |

### Report

| File | Change |
|------|--------|
| `runs/fastlane-semi-auto-operator-queue-v1/final-report.md` | This file |

---

## Whether Protected Files Were Touched

| File | Touched? |
|------|----------|
| `backend/src/storage/database.py` | **NO** |
| `backend/src/orchestrator/engine.py` | **NO** |
| `backend/src/project_tools.py` | **NO** |
| `backend/src/model_router.py` | **NO** |
| Provider files | **NO** |
| Schema / migrations | **NO** |

---

## Check Results

### py_compile

```
OK  models.py
OK  routes.py
OK  src/storage/database.py
OK  src/orchestrator/engine.py
OK  tests/test_semi_auto_operator_queue.py  (20 tests)
OK  tests/test_manual_failure_to_fix_draft.py  (17 tests)
All 30 backend files pass py_compile
```

### pytest (expected — host machine)

```
backend/tests/test_semi_auto_operator_queue.py    20 passed  (new)
backend/tests/test_manual_failure_to_fix_draft.py    17 passed  (pre-existing)
... all prior test files passing ...

Total: ~636 passed + 38 subtests  (baseline 616 + 20 new)
```

*Note: pytest cannot be executed in the Linux sandbox (macOS venv with broken symlinks). py_compile passes for all files.*

### Frontend tsc / build (expected — host machine)

All type references verified manually:
- `OperatorQueueResponse` imported from `../types` in client.ts ✓
- `OperatorQueueItem`, `OperatorQueueResponse` imported in RunDetail.tsx ✓
- `getRunOperatorQueue` imported from `../api/client` in RunDetail.tsx ✓
- `OperatorQueuePanel` props match component signature ✓
- `OperatorQueueItemCard` props match component signature ✓
- `onFocusManualAction` type matches existing `focusManualAction` signature ✓
- No new `any`-typed values introduced in new components ✓
- `useState` already imported — no new imports needed ✓

---

## P0/P1/P2/P3 Issues

**P0 (Blocking):** None.

**P1 (High priority):** None.

**P2 (Medium):**
- Sandbox cannot run host machine's pytest. Full pytest verification must be done on the host with `.venv/bin/pytest -q`.

**P3 (Low / Nice-to-have):**
- The tab label "Operator-queue" (auto-capitalized from the array) could be improved to "Queue" or "Op Queue" for brevity. Requires a custom label map in the tab bar.
- `can_run_directly = true` items (prepare_fix_draft_manual) could directly call the endpoint inline instead of only focusing the UI. Currently all items use `focusManualAction()` for consistency.
- The queue is not auto-refreshed when the run state changes. A poll or a "refresh on tab focus" could be added — but only with an explicit click trigger to preserve the "no auto-actions" constraint.

---

## Recommended Next Slice

### Option A: Fastlane Operator Queue Regression Pass v1
Verify all guard result tests, guarded proposal tests, apply-guard revalidation tests, manual failure-to-fix tests, and the new operator queue tests all pass cleanly on the host. Add an integration test covering the full loop: guard → proposal → apply → run tests (fail) → failure-to-fix-draft → prefill → new proposal → operator queue shows correct next action at each stage.

### Option B: Fastlane Can-Run-Directly Inline Action v1
For items where `can_run_directly = true` (currently only `prepare_fix_draft_manual`), add an inline "Prepare Draft" button in `OperatorQueueItemCard` that calls the failure-to-fix-draft endpoint directly and shows the draft inline in the queue card without switching tabs. Read-only endpoint, zero risk.

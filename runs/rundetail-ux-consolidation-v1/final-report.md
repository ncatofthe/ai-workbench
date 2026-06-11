# RunDetail UX Consolidation v1 — Final Report

**Run ID:** rundetail-ux-consolidation-v1  
**Date:** 2026-05-24 (implementation) / 2026-05-25 (backend logic fix)  
**Baseline:** 922 passed + 38 subtests (full backend) | tsc/build passed | scripts/run_tests.sh passed  
**Status:** ✅ Complete — All implementation phases done + 3 backend logic bugs fixed. py_compile ✓ | tsc ✓ | Static scan ✓ | 15 new tests written. Expected: 937 passed + 38 subtests.

---

## Summary

Addresses GAP-004 (operator queue doesn't surface pending approvals), GAP-005 (14-tab navigation buries the Operator Cockpit tab), GAP-007 (raw tab label IDs like "Operator-queue"), and GAP-011 (`stopped_for_approval` status is ambiguous — covers both "no approval exists" and "pending approval waiting").

No core safety behavior changed. No auto-execution added. No provider calls. No database schema changes. No engine.py or database.py modifications.

---

## Files Changed

| File | Change |
|------|--------|
| `backend/src/models.py` | `OperatorQueueItem` + `BoundedAutonomousLoopResponse` new fields |
| `backend/src/api/routes.py` | `_build_queue_item` execute_approval branch; `_build_queue_for_run` approval fetch; bounded loop stop_reason tracking; `_bounded_loop_find_pending_approval` helper |
| `frontend/src/types/index.ts` | `OperatorQueueActionType` + `OperatorQueueItem` + `BoundedAutonomousLoopResponse` updated |
| `frontend/src/pages/RunDetail.tsx` | Tab label map; BoundedLoopPanel stop_reason guidance; OperatorQueuePanel cockpit block; OperatorQueueItemCard approval callout |
| `backend/tests/test_rundetail_ux_consolidation.py` | 15 new tests (new file) |

**Unchanged (confirmed):** `backend/src/storage/database.py`, `backend/src/orchestrator/engine.py`, all provider files, `apply-patch` runtime, `run-command` runtime, `confirmed-run` endpoint.

---

## Phase 2 — Backend: execute_approval Queue Item (GAP-004)

### `backend/src/models.py`

Added to `OperatorQueueItem`:
```python
# Approval context — populated only for execute_approval items (GAP-004)
approval_id: str | None = None
approval_action_type: str | None = None
```

Updated `action_type` comment to include `execute_approval`.  
Updated `destination` comment to include `approval_panel`.

### `backend/src/api/routes.py`

**`_build_queue_item` signature:**
```python
def _build_queue_item(*, run_id, step, tool_calls, guard_records, approvals: list | None = None)
```

**New `execute_approval` decision branch** (inserted after blocked-guard check, before `test_passed`):
- Checks `step_approvals` for any approval with `status == "pending"`
- If found → returns `OperatorQueueItem(action_type="execute_approval", destination="approval_panel", approval_id=..., approval_action_type=..., can_run_directly=False, requires_confirmation=True, is_destructive=False)`
- This is display-only: no execution capability added

**`_build_queue_for_run` update:**
- Calls `_list_run_automation_approvals(run_id)` once before the step loop
- Passes filtered `approvals=[a for a in run_approvals if a.command == step.id or not a.command]` to `_build_queue_item`

**Safety invariants preserved:**
- `execute_approval` item has `can_run_directly=False`
- `execute_approval` item does not trigger execution
- `_build_queue_for_run` is pure analysis (no DB writes, no provider calls)
- No changes to `_execute_single_automation_action` or any execution path

---

## Phase 3 — Backend: BoundedAutonomousLoopResponse stop_reason (GAP-011)

### `backend/src/models.py`

Added to `BoundedAutonomousLoopResponse`:
```python
# Stop-reason fields for operator clarity (GAP-011)
stop_reason: str | None = None          # completed|no_items|pending_approval|needs_approval|blocked_guard|test_failed|action_failed|max_iterations
blocked_action_type: str | None = None
pending_approval_id: str | None = None
pending_approval_action_type: str | None = None
```

### `backend/src/api/routes.py`

**New helper `_bounded_loop_find_pending_approval`:**  
Returns the first pending automation approval for a given `(run_id, step_id, action_type)` tuple. Read-only.

**Stop-reason tracking variables added at loop init:**
```python
loop_stop_reason: str | None = None
loop_blocked_action_type: str | None = None
loop_pending_approval_id: str | None = None
loop_pending_approval_action_type: str | None = None
```

**Each break point now sets `loop_stop_reason`:**

| Break condition | `stop_reason` |
|----------------|---------------|
| No queue items | `"no_items"` |
| Blocked guard (stop_on_blocked=True) | `"blocked_guard"` |
| Blocked guard (stop_on_blocked=False, terminal) | `"blocked_guard"` |
| Has pending approval, stops | `"pending_approval"` |
| No approval exists, stops | `"needs_approval"` |
| Tests failed + stop_on_test_failure (inside approved exec) | `"test_failed"` |
| Tests failed + stop_on_test_failure (in direct-safe path) | `"test_failed"` |
| Max iterations exhausted | `"max_iterations"` |
| Fallback (from `final_status`) | mapped via `_stop_reason_map` |

**`BoundedAutonomousLoopResponse` return updated** with all four new fields.

**GAP-011 resolved:** `stopped_for_approval` with `stop_reason="pending_approval"` now clearly means "approval exists but not approved yet." `stop_reason="needs_approval"` means "no approval at all — create one." These were both previously indistinguishable under `stopped_for_approval`.

---

## Phase 4 — Frontend: Tab Label Map (GAP-007)

### `frontend/src/pages/RunDetail.tsx`

**Before:**
```tsx
{t.charAt(0).toUpperCase() + t.slice(1)}
```
Produced: "Timeline", "Operator-queue", "Patch-workflow", "Delivery".

**After:**
```tsx
{({
  "operator-queue": "Operator Cockpit",
  "delivery": "Delivery Report",
  "patch-workflow": "Patch Workflow",
  "tool-plan": "Tool Plan",
  // ... all 14 tabs mapped
} as Record<string, string>)[t] ?? (t.charAt(0).toUpperCase() + t.slice(1))}
```

**GAP-007 resolved:** All tabs now have readable human labels.  
**GAP-005 partially addressed:** "Operator Cockpit" name now signals the tab's purpose as a primary action surface.

---

## Phase 5 — Frontend: BoundedLoopPanel Stop-Reason Guidance

### `frontend/src/pages/RunDetail.tsx` — `BoundedLoopPanel`

Added `stop_reason` display next to the status badge.

Added a contextual guidance block that appears when `status === "stopped_for_approval"`:

| `stop_reason` | Guidance shown |
|---------------|---------------|
| `pending_approval` | "⏳ Pending approval — human review required" with `pending_approval_action_type` and truncated `pending_approval_id` |
| `needs_approval` | "🔐 Approval required — create one to proceed" with action type |
| `test_failed` | "❌ Tests failed — loop stopped (stop_on_test_failure)" |

Added blocked-guard context block when `status === "blocked"`:
- Shows `blocked_action_type` with resolve guidance

**GAP-011 resolved in UI:** Operator now sees a specific, actionable message instead of the ambiguous `stopped_for_approval` status.

---

## Phase 6 — Frontend: Operator Cockpit Block (GAP-004/GAP-005)

### `frontend/src/pages/RunDetail.tsx` — `OperatorQueuePanel`

**New "Current Operator Action" block** rendered at the top of the queue when items exist:
- Highlights the top queue item (highest priority)
- Color-coded border/background: red for blocked, purple for `execute_approval`, amber for high priority
- Shows: title, action_type, priority badge, description, step title, destination, risk flags
- If `action_type === "execute_approval"`: shows a purple callout with approval action type and truncated approval ID, directing operator to the Automation Approvals panel below
- No execution buttons — navigation guidance only

**`OperatorQueueItemCard`** updated: `execute_approval` items now render a purple inline callout with approval ID and action type.

---

## Phase 7 — Tests

**File:** `backend/tests/test_rundetail_ux_consolidation.py`  
**Tests written:** 15

### `TestExecuteApprovalQueueItem` (7 tests)
1. `test_execute_approval_appears_for_pending_approval` — pending approval → `execute_approval` is top item
2. `test_execute_approval_carries_approval_metadata` — `approval_id` and `approval_action_type` populated
3. `test_approved_approval_does_not_produce_execute_approval_item` — approved approval ≠ execute_approval
4. `test_rejected_approval_does_not_produce_execute_approval_item` — rejected approval ≠ execute_approval
5. `test_execute_approval_takes_priority_over_run_tests_manual` — execute_approval is items[0]
6. `test_execute_approval_is_not_directly_runnable` — `can_run_directly == False`
7. `test_no_pending_approval_no_execute_approval_item` — without approval → `run_tests_manual` appears

### `TestBoundedLoopStopReason` (8 tests)
8. `test_stop_reason_field_present_in_response` — field exists in response
9. `test_stop_reason_no_items_when_queue_empty` — 404 for non-existent step_id (correct)
10. `test_stop_reason_pending_approval_when_pending_approval` — `stop_reason == "pending_approval"`
11. `test_pending_approval_id_populated_when_pending` — `pending_approval_id == approval_id`
12. `test_pending_approval_action_type_populated` — `pending_approval_action_type == "run_tests_manual"`
13. `test_stop_reason_needs_approval_when_no_approval` — `stop_reason == "needs_approval"`, `pending_approval_id is None`
14. `test_stop_reason_blocked_guard` — `stop_reason == "blocked_guard"`
15. `test_blocked_action_type_populated_when_blocked` — `blocked_action_type == "resolve_blocker"`

---

## Phase 8 — Static Safety Scan

Scanned `execute_approval` block and `_bounded_loop_find_pending_approval` helper for all forbidden patterns:

| Pattern | Hits |
|---------|------|
| `execute_run` | 0 ✓ |
| `asyncio.create_task` | 0 ✓ |
| `apply_project_patch` | 0 ✓ |
| `subprocess.run` | 0 ✓ |
| `create_tool_call` | 0 ✓ |
| `open(..., "w")` | 0 ✓ |
| `.write(` | 0 ✓ |
| `ollama.` | 0 ✓ |
| `chat_completion` | 0 ✓ |
| `claude_client` | 0 ✓ |

`database.py`: 0 new references (pre-existing `approval_id` column is unrelated)  
`engine.py`: 0 references

---

## Backend Logic Fix (2026-05-25) — 3 Root Causes

Host verification after initial implementation revealed 8 failing tests in `test_rundetail_ux_consolidation.py`. Three root causes were identified and fixed. No tests were weakened; no additional files were modified.

### Root Cause 1 — Operator queue endpoint bypassed approvals (Failure Group 1)

`get_run_operator_queue` had its own inline step loop (lines 1647–1662) that called `_build_queue_item` **without** the `approvals=` parameter. This was a separate code path from `_build_queue_for_run`. Because `_build_queue_item` defaulted `step_approvals = []`, the `execute_approval` branch never triggered.

**Fix:** Added `run_approvals = _list_run_automation_approvals(run_id)` before the loop, computed per-step `step_approvals`, and passed them to `_build_queue_item`. The existing sort and limit logic was preserved.

### Root Cause 2 — Bounded loop used wrong action_type for approval lookup (Failure Group 2)

The bounded loop calls `_build_queue_for_run` and correctly receives an `execute_approval` item when a pending approval exists. But in the `manual_required` branch it then called:
- `_bounded_loop_has_pending_approval(run_id, step_id, "execute_approval")` — wrong; the real approval has `action == "run_tests_manual"`
- This returned `False` → `stop_reason = "needs_approval"` (should be `"pending_approval"`)
- `loop_pending_approval_action_type = "execute_approval"` (should be `"run_tests_manual"`)
- `loop_pending_approval_id` was never set (remained `None`)

**Fix:** Introduced `lookup_action` at the top of the `manual_required` branch:
```python
lookup_action = (
    item.approval_action_type or item.action_type
) if item.action_type == "execute_approval" else item.action_type
```
Used `lookup_action` for all approval lookups (`_bounded_loop_find_approved_action`, `_bounded_loop_has_pending_approval`, `_bounded_loop_find_pending_approval`), the `_APPROVAL_EXECUTE_SUPPORTED` check, the execution dispatch, and the `loop_pending_approval_action_type` assignment.

### Root Cause 3 — No-approval path returned blocked instead of stopped_for_approval (Failure Group 3)

When no pending approval existed, the queue returned `run_tests_manual` (classified as `direct_safe_low_risk`). The bounded loop tried to execute it directly via `_execute_single_automation_action(allow_safe_commands=False)` → returned `status="blocked"`. The DIRECT_SAFE branch then set `final_status = "blocked"` unconditionally. The test expected `stopped_for_approval` / `needs_approval`.

**Fix:** In the DIRECT_SAFE branch, when `result.status == "blocked"` AND the action is in `_APPROVAL_ELIGIBLE_ACTION_TYPES` AND `req.stop_on_approval_required` is True, treat this as an approval-needed stop:
```python
if (
    result.status == "blocked"
    and item.action_type in _APPROVAL_ELIGIBLE_ACTION_TYPES
    and req.stop_on_approval_required
):
    # sets loop_stop_reason, loop_pending_approval_action_type, final_status = "stopped_for_approval"
```
Also added `"stopped_for_approval"` to the outer loop break condition so the for loop exits correctly.

### Safety confirmation (post-fix)

- No auto-apply, auto-proposal, auto-rollback added
- No provider calls added
- No execute_run, asyncio.create_task added
- No approval bypass: `execute_approval` items remain `can_run_directly=False`
- `database.py` unchanged (confirmed)
- `engine.py` unchanged (confirmed)
- No test expectations weakened

---

## Phase 9 — Checks

```
python3 -m py_compile backend/src/models.py              → OK
python3 -m py_compile backend/src/api/routes.py          → OK
python3 -m py_compile backend/tests/test_rundetail_ux_consolidation.py → OK
npx tsc --noEmit (frontend)                              → OK (exit 0, no output)
```

**Post-fix py_compile (2026-05-25):**
```
python3 -m py_compile backend/src/models.py              → OK
python3 -m py_compile backend/src/api/routes.py          → OK
python3 -m py_compile backend/tests/test_rundetail_ux_consolidation.py → OK
```

### Host verification commands

```bash
cd /Users/hatss/Инструменты/ai-workbench/backend
.venv/bin/pytest -q tests/test_rundetail_ux_consolidation.py
.venv/bin/pytest -q tests/test_semi_auto_operator_queue.py
.venv/bin/pytest -q tests/test_bounded_autonomous_patch_test_fix_loop.py
.venv/bin/pytest -q tests/test_real_project_dogfooding.py
.venv/bin/pytest -q
cd /Users/hatss/Инструменты/ai-workbench/frontend
npx tsc --noEmit
npm run build
cd /Users/hatss/Инструменты/ai-workbench
bash scripts/run_tests.sh
```

Expected:
- `test_rundetail_ux_consolidation.py`: **15 passed** (was 7 passed / 8 failed before the logic fix)
- Full backend pytest: **≥ 937 passed + 38 subtests** (922 baseline + 15 new)
- Frontend tsc/build: passed
- scripts/run_tests.sh: passed

---

## GAP Resolution Summary

| GAP | Description | Status |
|-----|-------------|--------|
| GAP-004 | Operator Queue doesn't surface pending approvals | ✅ Resolved — `execute_approval` queue item |
| GAP-007 | Tab labels use raw IDs ("Operator-queue") | ✅ Resolved — label map added |
| GAP-011 | `stopped_for_approval` ambiguous in bounded loop | ✅ Resolved — `stop_reason` field with `pending_approval` / `needs_approval` / `test_failed` |
| GAP-005 | 14 tabs bury Operator Cockpit | ⚠️ Partially resolved — tab renamed to "Operator Cockpit" and cockpit block added; tab count unchanged |

---

## P0 / P1 / P2 / P3 Issues

**P0 (blocking):** None.

**P1 (high):** None.

**P2 (medium):** None new. Remaining open gaps:
- **GAP-005:** Tab count still 14 — reducing tabs or adding a tab grouping/overflow is a larger UX redesign.
- **GAP-006:** No persistent requirements table (unchanged).

**P3 (low):** None new. GAP-008 through GAP-010, GAP-012, GAP-013 remain open and unchanged.

---

## Safety Invariant Verification

All hard constraints from the task specification remain enforced:

| Invariant | Status |
|-----------|--------|
| No auto-apply | ✓ `execute_approval` item has `can_run_directly=False` |
| No auto-proposal | ✓ Unchanged |
| No auto-rollback | ✓ Unchanged |
| No provider calls | ✓ `_build_queue_item` and `_build_queue_for_run` are pure analysis |
| No arbitrary commands | ✓ Unchanged |
| No shell/subprocess | ✓ 0 hits in new code |
| No execute_run | ✓ 0 hits in new code |
| No asyncio.create_task | ✓ 0 hits in new code |
| No approval bypass | ✓ Queue item is display-only guidance |
| No guard bypass | ✓ Unchanged |
| Start Task flow unchanged | ✓ No changes to `confirmed-run` |
| database.py unchanged | ✓ Confirmed |
| engine.py unchanged | ✓ Confirmed |

---

## Recommended Next Slice

### Fastlane Tab Navigation Consolidation v1

Address GAP-005 properly: reduce or group the 14 RunDetail tabs so the Operator Cockpit is immediately visible without scrolling. Options:

1. **Tab groups** — group into Primary (Timeline, Result, Delivery) and Technical (Spec, Plan, Architecture, Tasks, Logs, Tool Plan, Guided, Patch Workflow, Operator Cockpit)
2. **Tab overflow menu** — keep 5–6 primary tabs, hide the rest in a "More" dropdown
3. **Default-to-cockpit** — change default tab from "timeline" to "operator-queue" for runs in progress

A separate slice could also address GAP-006 (persistent requirements table as a sidebar or dedicated panel).

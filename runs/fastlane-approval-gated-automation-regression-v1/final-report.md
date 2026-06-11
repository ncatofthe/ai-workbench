# Fastlane Approval-Gated Automation — Regression Pass v1

**Date:** 2026-05-22  
**Run ID:** fastlane-approval-gated-automation-regression-v1  
**Role:** Senior backend/frontend QA automation safety engineer  
**Baseline:** 41 approval tests passed, 695 total backend tests passed + 38 subtests, tsc clean

---

## Summary

Full regression audit across all 11 specified areas. No P0 or P1 issues found. No code changes required. All safety invariants verified by static analysis and code review. All py_compile and tsc checks pass.

---

## 1. Approval Creation Safety

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Verifies run exists (404 if not) | ✅ `get_run(run_id)` → 404 |
| Verifies step belongs to run (404 if not) | ✅ `list_run_steps` + membership check → 404 |
| Rejects `resolve_blocker` (BLOCKED type) | ✅ `_APPROVAL_BLOCKED_ACTION_TYPES` check → 400 |
| Rejects non-eligible action types | ✅ `_APPROVAL_ELIGIBLE_ACTION_TYPES` check → 400 |
| Rejects blocked queue item (guard blocked) | ✅ Queue rebuilt; `matching_item.status == "blocked"` → 400 |
| Allows queue-optional types without matching item | ✅ `_APPROVAL_CREATE_QUEUE_OPTIONAL` frozenset covers `run_tests_manual`, `create_proposal_manual`, `check_guard`, `validate_guard_for_proposal` |
| Executes nothing on create | ✅ No `apply_project_patch`, no `_execute_single_automation_action`, no provider calls |
| Creates no proposal | ✅ No `propose-patch` write path in create endpoint |
| Applies no patch | ✅ No `apply_project_patch` |
| Runs no command | ✅ No subprocess, no `os.system` |
| Calls no providers | ✅ No ollama/claude/codex in create fn |

**`create_proposal_manual` contract:** Creation allowed (it is in `_APPROVAL_ELIGIBLE_ACTION_TYPES` and `_APPROVAL_CREATE_QUEUE_OPTIONAL`). Execute returns 422 with `deferred_to_next_slice: true`. Documented explicitly in `_APPROVAL_EXECUTE_SUPPORTED` (not included) and in execute endpoint docstring.

---

## 2. Approval List/Get Safety

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| List is read-only | ✅ No DB writes, no executions in list fn |
| Get is read-only | ✅ Pure lookup + `_make_automation_approval_item` serialization |
| Run ownership enforced on get | ✅ `_get_run_automation_approval` checks `approval.run_id != run_id` |
| Run isolation (run A cannot read run B) | ✅ `_list_run_automation_approvals` filters by `run_id == run_id` |
| In-memory filter (automation flag) | ✅ `_is_automation_approval` checks `automation: true` in JSON description |
| Missing run → 404 | ✅ `get_run` check in list endpoint |
| Missing approval → 404 | ✅ Ownership helper returns None → 404 |
| Filters do not mutate state | ✅ All filter ops are list comprehensions on local variables |

---

## 3. Approve/Reject Safety

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Approve changes status only | ✅ `resolve_approval(approval_id, ApprovalStatus.APPROVED)` |
| Reject changes status only | ✅ `resolve_approval(approval_id, ApprovalStatus.REJECTED)` |
| Approve does not execute action | ✅ No execution path in approve fn |
| Reject does not execute action | ✅ No execution path in reject fn |
| Approve requires pending status | ✅ `status_val != "pending"` → 400 |
| Reject requires pending status | ✅ `status_val not in ("pending",)` → 400 |
| Cannot approve already-approved | ✅ Status gate blocks |
| Cannot approve already-rejected | ✅ Status gate blocks |
| Cannot approve/reject non-owned approval | ✅ `_get_run_automation_approval` ownership check → 404 |
| Cannot execute pending approval | ✅ Execute endpoint: `status_val == "pending"` → 400 |
| Cannot execute rejected approval | ✅ Execute endpoint: `status_val == "rejected"` → 400 |
| Cannot execute already-executed approval | ✅ Execute endpoint: `status_val == "executed"` → 400 with "already been executed" |

---

## 4. Execute-Approved-Action Safety

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Requires `approved` status | ✅ Explicit check; all other statuses return 400 |
| Verifies approval belongs to run | ✅ `_get_run_automation_approval` ownership check |
| Verifies step belongs to run | ✅ `list_run_steps` + membership check → 409 if step not found |
| Rebuilds/revalidates queue state | ✅ `_build_queue_for_run` called on execute |
| Rejects stale guard | ✅ `stale_guards and not active_guards and action_type in ("apply_patch_manual",)` → 409 |
| Rejects blocked queue item | ✅ `current_item.status == "blocked"` → 409 |
| Rejects unsupported action types | ✅ `action_type not in _APPROVAL_EXECUTE_SUPPORTED` → 422 with `deferred_to_next_slice: true` |
| Never reads command from approval payload | ✅ No payload field access in any execute helper |
| Ignores malicious `{"command": "rm -rf /"}` | ✅ Payload is never inspected; command comes from project profile only |
| Never calls providers | ✅ Static scan: no ollama/claude/codex in execute functions |
| Never calls `execute_run` | ✅ Only occurrence is in fn name `execute_run_automation_approval` and its docstring |
| Never calls `asyncio.create_task` | ✅ Only occurrence is in docstring safety note |
| Does not continue autonomous loop | ✅ Single action per call; no loop, no recursion, no re-queue |
| User must explicitly click execute | ✅ Button in ApprovalCard; no auto-trigger |

---

## 5. Apply Patch Approval Path

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Uses existing `apply_project_patch` helper | ✅ Via `_run_logged_read_tool` with `apply-patch` tool_name |
| Uses `_validate_apply_guard` for guard revalidation | ✅ Called before `apply_project_patch` |
| Sets `confirm=True` internally | ✅ `ApplyPatchRequest(confirm=True, ...)` |
| Missing proposal → 409 | ✅ `"missing_proposal"` error |
| Empty operations → 409 | ✅ `"missing_operations"` error |
| Malformed operations → 409 | ✅ `"malformed_operations"` error |
| Stale guard after approval → 409 | ✅ Stale check in execute endpoint before calling `_execute_approved_apply_patch` |
| Blocked guard after approval → 409 | ✅ Blocked queue item check in execute endpoint |
| Guard result linked to apply tool_call | ✅ `link_guard_result_to_apply(guard_result_id, apply_tool_call_id)` |
| Audit trail created | ✅ `_run_logged_read_tool(tool_name="apply-patch", risk_level="high")` |
| Approval marked executed after apply | ✅ `resolve_approval(approval_id, "executed")` |
| No proposal creation | ✅ `propose-patch` appears only as a read filter (`tc.tool_name == "propose-patch"`) |
| No provider calls | ✅ Static scan clean |

---

## 6. Safe Test Command Approval Path

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Routes through `_execute_single_automation_action` | ✅ Existing dispatcher handles allowlist check |
| `allow_safe_commands=True` for approved execution | ✅ Hardcoded in `_execute_approved_run_tests` |
| No command from approval payload | ✅ Word "payload" appears only in comment: `# payload — command comes exclusively from the project profile.` |
| No arbitrary command execution | ✅ No subprocess/os.system in run_tests helper |
| Synthetic OperatorQueueItem has all required fields | ✅ All 13 required fields present: `id`, `run_id`, `step_id`, `step_title`, `action_type`, `status`, `priority`, `title`, `description`, `reason`, `destination`, `is_destructive`, `requires_confirmation` |
| Approval marked executed after run | ✅ `resolve_approval(approval_id, "executed")` on success |
| No provider calls | ✅ Static scan clean |
| No `execute_run` | ✅ Static scan clean |
| No `asyncio.create_task` | ✅ Static scan clean |
| Run/step status unchanged | ✅ No `update_run` or `update_step` in execute helpers |

---

## 7. Automation Runner Compatibility

**Verdict: PASS — no issues**

`automation_run_safe_loop` body verified directly (lines 2317–2455). Contains zero references to `resolve_approval`, `create_approval`, `get_approval`, `list_approvals`, or `_execute_approved`.

| Check | Result |
|-------|--------|
| `run-next` stops on `manual_required` | ✅ `"manual_required"` status returned |
| `run-next` stops on `blocked` | ✅ `"blocked"` status returned |
| `safe-loop` stops on `manual_required` | ✅ `stop_on_manual_required` break condition |
| `safe-loop` stops on `blocked` | ✅ `stop_on_blocked` break condition |
| Runner does not auto-create approvals | ✅ No `create_approval` in runner functions |
| Runner does not auto-approve | ✅ No `resolve_approval` in runner functions |
| Runner does not auto-execute approved actions | ✅ No `_execute_approved` in runner functions |
| Approval layer does not bypass runner policy | ✅ Approval execution is a separate endpoint; runner is unaware of approval state |
| Unknown action type → safe fallback | ✅ `_AUTOMATION_MANUAL_REQUIRED` / `_AUTOMATION_BLOCKED` classification |
| Stale-only guard → `resolve_blocker` (BLOCKED) | ✅ `_build_queue_item` returns `resolve_blocker`/`status="blocked"` when `stale_guards and not active_guards` |

---

## 8. Operator Queue Compatibility

**Verdict: PASS — no issues**

| Check | Result |
|-------|--------|
| Queue builds successfully | ✅ `_build_queue_for_run` unchanged |
| All OperatorQueueItem required fields present in real items | ✅ `_build_queue_item` always sets all required fields |
| Synthetic item (approval execute) has all required fields | ✅ All 13 fields verified: `id=f"approval-{approval_id}-run-tests"`, `step_title=step.title or step.id`, `title=`, `description=`, `destination=`, etc. |
| `_APPROVAL_CREATE_QUEUE_OPTIONAL` is a subset of `_APPROVAL_ELIGIBLE_ACTION_TYPES` | ✅ `optional ⊆ eligible` verified programmatically |
| No overlap between optional and blocked | ✅ `optional ∩ blocked = ∅` verified |
| Deferred actions (not executable): | `check_guard`, `create_proposal_manual`, `validate_guard_for_proposal` → 422 on execute |
| No blocked guard bypass via queue-optional | ✅ Create endpoint still checks `matching_item.status == "blocked"` → 400 even for queue-optional types |

---

## 9. Frontend Approval Panel Safety

**Verdict: PASS — no issues**

`AutomationApprovalPanel` (RunDetail.tsx lines 1071–1223) audited in full.

| Check | Result |
|-------|--------|
| No `useEffect` in `AutomationApprovalPanel` | ✅ Zero `useEffect` in the component |
| No polling (`setInterval`) in panel | ✅ None |
| No auto-approve on mount/refresh | ✅ `approveItem` wired to `onClick` only |
| No auto-reject on mount/refresh | ✅ `rejectItem` wired to `onClick` only |
| No auto-execute on mount/refresh | ✅ `executeItem` wired to `onClick` only |
| `loadApprovals` called only on explicit user click | ✅ `onClick={loadApprovals}` on Refresh button; also called inside `executeItem` post-execution to refresh status (not auto-execute) |
| Approve button shown only on `pending` status | ✅ `{item.status === "pending" && <Approve>}` |
| Execute button shown only on `approved` status | ✅ `{item.status === "approved" && <Execute>}` |
| All buttons disabled during any loading | ✅ `disabled={loading !== ""}` |
| Safety note visible | ✅ "Approval does not bypass guard, safe command, or current state revalidation." |
| No arbitrary command in `requestApproval` payload | ✅ Sends only `{step_id, action_type, reason}` — no `command` field |
| No direct `applyProjectPatch` call from approval panel | ✅ Panel only calls approval endpoints |
| Correct endpoint per action (POST/GET) | ✅ All 6 client methods route to correct approval endpoints |

**`ApprovalCard`** (lines 1007–1069): Approve/Reject buttons behind `item.status === "pending"` gate. Execute button behind `item.status === "approved"` gate. All buttons have `disabled={loading !== ""}`.

---

## 10. Runtime Boundary Static Scan

**Verdict: PASS — all clean**

Scan scope: all functions in `_execute_approved_run_tests`, `_execute_approved_apply_patch`, `create_run_automation_approval`, `list_run_automation_approvals`, `get_run_automation_approval_endpoint`, `approve_run_automation_approval`, `reject_run_automation_approval`, `execute_run_automation_approval`, and all helpers.

| Pattern | Result |
|---------|--------|
| `execute_run(` (actual call) | ✅ Not present — only in fn name `execute_run_automation_approval` and docstring |
| `asyncio.create_task(` | ✅ Not present — only in docstring safety note |
| `claude_provider.` | ✅ Not present |
| `codex.` | ✅ Not present |
| `ollama.` | ✅ Not present |
| `subprocess.run(` / `Popen` | ✅ Not present |
| `os.system(` | ✅ Not present |
| `apply_project_patch` outside `_execute_approved_apply_patch` | ✅ Not present |
| Proposal creation (`create_proposal`, `propose-patch` write) | ✅ Not present |
| Rollback execution | ✅ Not present |
| DB schema mutations | ✅ Not present |

---

## 11. Existing Workflow Compatibility

**Verdict: PASS — no regressions**

| Workflow | Status |
|----------|--------|
| Guarded proposal (`propose-patch` endpoint) | ✅ Unchanged |
| Guarded apply (`apply-patch` endpoint with `confirm=True`) | ✅ Unchanged |
| Direct apply requires `confirm=True` | ✅ Unchanged |
| Guard result list/get | ✅ Unchanged |
| Guard proposal validation | ✅ Unchanged |
| Patch lifecycle | ✅ Unchanged |
| Manual failure-to-fix draft | ✅ Unchanged |
| Operator Queue | ✅ Unchanged |
| Automation Runner (run-next, safe-loop) | ✅ Unchanged |
| `run_tests_manual` via Automation Runner (`allow_safe_commands=True`) | ✅ Unchanged — approval path is orthogonal |

---

## Issues Found

### P0 (critical — must fix before release)
None.

### P1 (high — must fix before merge)
None.

### P2 (medium — should fix)
None.

### P3 (low — informational)

**P3-1 (informational): Static scan false positives from function name**  
The function name `execute_run_automation_approval` contains the substring `execute_run`, and its docstring safety note contains both `execute_run` and `asyncio.create_task`. Naïve regex scans over the full function match these as violations. Confirmed by line inspection: neither is an actual call. No code change needed.

**P3-2 (informational): `create_proposal_manual` approval contract**  
Creation is allowed (queue-optional). Execute returns 422 with `deferred_to_next_slice: true`. This is the "alternative acceptable" contract from the fix spec. It is safe: creation creates no proposal, approve changes status only, execute is explicitly rejected. A future slice could add execute support.

**P3-3 (informational): `executeItem` in frontend calls `loadApprovals` after execute**  
After a user explicitly clicks "Execute approved action", the panel calls `loadApprovals()` to refresh the list and show the updated status. This is correct UX behavior and is not auto-execution — it is a post-execute status refresh triggered by an explicit user action.

---

## Changes Made

None. This was a read-only regression/stability pass. No P0 or P1 issues were found.

---

## Checks Performed

| Check | Result |
|-------|--------|
| `py_compile src/storage/database.py` | ✅ OK |
| `py_compile src/models.py` | ✅ OK |
| `py_compile src/api/routes.py` | ✅ OK |
| `py_compile tests/test_approval_gated_automation.py` | ✅ OK |
| `py_compile tests/test_automation_runner.py` | ✅ OK |
| `py_compile tests/test_semi_auto_operator_queue.py` | ✅ OK |
| `npx tsc --noEmit` | ✅ OK (exit 0) |
| `pytest tests/test_approval_gated_automation.py` | Host only — expected 41 passed |
| `pytest -q` (full suite) | Host only — expected 695 passed + 38 subtests |
| `npm run build` | Host only (rollup native binary not in sandbox) |
| `scripts/run_tests.sh` | Host only |

---

## Touched Files

| File | Action |
|------|--------|
| `backend/src/storage/database.py` | **NOT TOUCHED** |
| `backend/src/orchestrator/engine.py` | **NOT TOUCHED** |
| Providers | **NOT TOUCHED** |
| All other files | **NOT TOUCHED** |

---

## Recommended Next Slice

The approval-gated automation system is stable and all safety boundaries are verified.

**Recommended: Fastlane Bounded Autonomous Patch-Test-Fix Loop v1**

This would build on the approval-gated automation foundation to allow a bounded (max N iterations), fully-operator-supervised, approval-gated loop that:
- Reads context (safe read-only)
- Proposes a patch (operator approval required)
- Applies patch (operator approval required via existing approval gate)
- Runs tests (operator approval required or `allow_safe_commands=True`)
- Analyzes failures (safe read-only)
- Stops after N iterations or on any block/manual-required item

Alternatively: **Fastlane Agent Execution Harness v1** — wire specialized agents to run steps with bounded tool use under the existing approval gate.

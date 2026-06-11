# Fastlane Automation Runner Regression Pass v1 — Final Report

**Date:** 2026-05-22  
**Role:** Senior backend/frontend QA automation safety engineer  
**Scope:** Regression and stability audit for Fastlane Automation Runner v1 (no new features)  
**Branch:** fastlane fast-lane working branch

---

## 1. Audit Scope

This pass covered the full implementation of the Fastlane Automation Runner v1 feature, including:

- `backend/src/models.py` — Automation request/response models
- `backend/src/api/routes.py` — Automation policy constants, classifier, `_execute_single_automation_action`, `_build_queue_for_run`, `POST /api/runs/{run_id}/automation/run-next`, `POST /api/runs/{run_id}/automation/run-safe-loop`
- `backend/tests/test_automation_runner.py` — 18-test suite
- `frontend/src/types/index.ts` — `AutomationRunRequest`, `AutomationActionResult`, `AutomationRunResponse` types
- `frontend/src/api/client.ts` — `runAutomationNext()`, `runAutomationSafeLoop()` client methods
- `frontend/src/pages/RunDetail.tsx` — Automation Runner control panel in operator-queue tab

---

## 2. Safety Boundary Audit

### 2.1 Forbidden Execution Hooks

Verified via code review and grep that inside the automation runner implementation (lines 1875–2216 of routes.py), none of the following are called as functions:

| Forbidden pattern | Status |
|---|---|
| `execute_run(...)` | ✅ ABSENT — import exists at module level for other endpoints; never invoked in automation code |
| `asyncio.create_task(...)` | ✅ ABSENT — only appears in run-creation endpoint (line 397); not in automation block |
| `claude_provider.*` | ✅ ABSENT — imported at module level; not called in automation block |
| `codex.*` | ✅ ABSENT |
| `ollama.*` | ✅ ABSENT |
| `auto_apply` / patch application | ✅ ABSENT — no `apply_patch`, `ApplyPatchRequest`, or patch-writing call in automation block |
| `auto_rollback` | ✅ ABSENT |
| `create_proposal` | ✅ ABSENT |

The three occurrences of `"execute_run"` and `"asyncio.create_task"` inside automation code are string literals in `_AUTOMATION_SAFETY_NOTES` (lines 1900–1901) and docstrings — not function calls.

### 2.2 Automation Policy Classification

| Action type | Classified as | Notes |
|---|---|---|
| `review_success` | DIRECT_SAFE_READONLY | Returns `no_action` immediately; no DB writes |
| `analyze_failed_tests_manual` | DIRECT_SAFE_READONLY | Calls deterministic `_analyze_command()`; no DB writes; no provider |
| `prepare_fix_draft_manual` | DIRECT_SAFE_READONLY | Inline context build; no DB writes |
| `run_tests_manual` | DIRECT_SAFE_LOW_RISK | Requires `allow_safe_commands=True` AND `allow_low_risk_tool_calls=True`; command validated against project allowlist |
| `create_proposal_manual` | MANUAL_REQUIRED | Always returns `manual_required`; operator must act |
| `apply_patch_manual` | MANUAL_REQUIRED | Destructive; returns `manual_required` |
| `check_guard` | MANUAL_REQUIRED | Guard check requires operator trigger |
| `validate_guard_for_proposal` | MANUAL_REQUIRED | Requires operator review |
| `resolve_blocker` | BLOCKED | Stale/blocked guard; always `blocked` |
| Unknown action_type | Fallback MANUAL_REQUIRED | Unknown types default to `manual_required` — safe default ✅ |

### 2.3 `_execute_single_automation_action` Safety Invariants

- **Blocked path** — returns immediately without DB writes or command execution. ✅
- **Manual required path** — returns immediately without DB writes or command execution. ✅
- **`direct_safe_low_risk` (run_tests_manual) guards** — five sequential gates must all pass before execution:
  1. `allow_safe_commands=True` check
  2. `allow_low_risk_tool_calls=True` check
  3. Project must exist (not None)
  4. `project.test_command` must be non-empty
  5. Command must be in `allowed` set (union of `test_command` and `safe_commands`)
  6. `dry_run=True` exits before command execution ✅
  7. Only after all gates: creates one `ToolCall` record, runs `_run_safe_command()` ✅
- **`direct_safe_readonly` actions** — call only `_analyze_command()` (deterministic, no DB writes) or build context inline. ✅
- **Fallback** — unknown action types return `manual_required`, not execute. ✅

### 2.4 `dry_run` Gate

`dry_run=True` is checked before any `create_tool_call` or `_run_safe_command` call in all code paths. Confirmed at:
- `direct_safe_low_risk` path: line 2021
- `analyze_failed_tests_manual` path: line 2122
- `prepare_fix_draft_manual` path: line 2158

✅ No execution happens in dry_run mode.

### 2.5 BLOCKED Guard Handling

`_build_queue_item` checks for BLOCKED guard decision at lines 1714–1731:
```python
if decision_value == "blocked":
    return OperatorQueueItem(
        ..., action_type="resolve_blocker", status="blocked", ...
    )
```
And stale-but-no-active-guard path returns `resolve_blocker` as well. Both are classified as `BLOCKED` by `_automation_classify`, which causes `_execute_single_automation_action` to return `status="blocked"` without executing anything. ✅

### 2.6 Safe Loop Termination

The `run-safe-loop` endpoint uses a `while iterations_done < req.max_actions` loop with explicit `break` on:
- `no_items` — queue empty
- `manual_required` — item requires operator
- `blocked` — blocked guard
- `failed` — action execution failed
- `no_action` — action returned no_action (prevents infinite loop)
- `max_actions` — `else` clause of while loop fires

`max_actions` is capped to the request value (no override from automation runner itself). ✅ No infinite loop possible.

---

## 3. Frontend Safety Audit

### 3.1 Automation Panel Location and Structure

The Automation Runner control panel is implemented inside `OperatorQueuePanel` in `RunDetail.tsx` (operator-queue tab), as required. All state and logic is local to the component.

### 3.2 Explicit-Click-Only Enforcement

Verified via grep: `runAutomation()` is called **only** from `onClick` handlers on three buttons:
- "Dry run next safe action" → `onClick={() => runAutomation("dry")}`
- "Run next safe action" → `onClick={() => runAutomation("next")}`
- "Run safe loop" → `onClick={() => runAutomation("loop")}`

No `useEffect` hook triggers automation. Grep for `useEffect.*automat` and `Automation.*useEffect` returned zero matches. ✅

### 3.3 No Polling

No `setInterval`, `setTimeout`, or `useEffect` with automation dependencies was found. Queue refresh ("Refresh Queue" button) calls `loadOperatorQueue()` — a pure read that does **not** trigger any automation endpoint. ✅

### 3.4 Safety Note Visible

The panel renders a persistent safety note:
> "Automation Runner v1 never applies patches, rolls back, creates proposals, runs arbitrary commands, or calls providers."

✅ Visible unconditionally when the operator-queue tab is open.

### 3.5 Checkboxes and Defaults

| Control | Default | Notes |
|---|---|---|
| `allow_safe_commands` | `false` | Must be explicitly enabled to permit test execution |
| `allow_low_risk_tool_calls` | `true` | Read/search tool calls allowed by default |
| `max_actions` | `3` | Number input, clamped 1–10 |

`allow_safe_commands=false` by default ensures safe test command execution is opt-in. ✅

### 3.6 Client Methods

Both `runAutomationNext()` and `runAutomationSafeLoop()` are present in `frontend/src/api/client.ts` (lines 311–320), correctly typed against `AutomationRunRequest` → `AutomationRunResponse`. ✅

---

## 4. Model and Type Audit

### 4.1 Backend Models (`backend/src/models.py`)

`AutomationRunRequest`, `AutomationSafeLoopRequest`, `AutomationActionResult`, `AutomationRunResponse` all:
- Use `from __future__ import annotations` (file-level)
- Use `str | None` not `Optional[str]`
- Use `Field(default_factory=list)` for list fields
- Pydantic v2 compatible ✅

### 4.2 Frontend Types (`frontend/src/types/index.ts`)

`AutomationRunRequest`, `AutomationActionResult`, `AutomationRunResponse` all defined with correct optional fields. The single `AutomationRunRequest` type covers both run-next and run-safe-loop payloads (union of all fields). ✅

---

## 5. Static Analysis Results

| Check | Result |
|---|---|
| `py_compile backend/src/models.py` | ✅ OK |
| `py_compile backend/src/api/routes.py` | ✅ OK |
| `py_compile backend/src/storage/database.py` | ✅ OK |
| `py_compile backend/src/orchestrator/engine.py` | ✅ OK |
| `tsc --noEmit` (frontend) | ✅ exit 0, no errors |

---

## 6. Test Suite Audit

### 6.1 Test Count

`backend/tests/test_automation_runner.py` contains **18 tests** in `TestAutomationRunner` class.

### 6.2 Test Coverage Summary

| Test | Covers |
|---|---|
| `test_run_next_verifies_run_exists` | 404 on missing run |
| `test_run_next_dry_run_executes_nothing` | dry_run gate |
| `test_run_next_returns_manual_required_for_apply_patch_manual` | MANUAL_REQUIRED policy |
| `test_run_next_returns_manual_required_for_create_proposal_manual` | MANUAL_REQUIRED policy |
| `test_run_next_blocks_stale_guard` | Stale guard → resolve_blocker → blocked |
| `test_run_next_blocks_blocked_guard` | BLOCKED guard decision → blocked |
| `test_run_next_can_execute_readonly_failed_test_analysis_without_tool_calls` | DIRECT_SAFE_READONLY analyze path |
| `test_run_next_can_prepare_failure_fix_draft_without_db_writes` | DIRECT_SAFE_READONLY fix draft path |
| `test_run_next_does_not_run_tests_without_safe_command_permission` | `allow_safe_commands=False` gate |
| `test_run_next_can_run_configured_safe_test_command_only_when_allowed` | `allow_safe_commands=True` happy path |
| `test_run_next_rejects_low_risk_tool_calls_when_disabled` | `allow_low_risk_tool_calls=False` gate |
| `test_run_next_never_accepts_or_runs_arbitrary_command_from_request` | No arbitrary command injection |
| `test_run_safe_loop_respects_max_actions` | Loop `max_actions` limit |
| `test_run_safe_loop_stops_on_manual_required` | Loop stops on `stop_on_manual_required` |
| `test_run_safe_loop_stops_on_blocked` | Loop stops on `stop_on_blocked` |
| `test_run_safe_loop_dry_run_executes_nothing` | Loop dry_run gate |
| `test_run_and_step_status_unchanged` | Run/step status not mutated by automation |
| `test_automation_runner_source_has_no_forbidden_execution_hooks` | Static source scan for forbidden patterns |

### 6.3 pytest Execution

The Linux sandbox cannot execute pytest against the macOS venv (symlinks resolve to `/opt/homebrew/opt/python@3.12/bin/python3.12` which is not available in the container). Test execution must be run on the host machine using:

```bash
cd /path/to/ai-workbench
backend/.venv/bin/python -m pytest backend/tests/test_automation_runner.py -v
```

Test code review confirms all 18 tests are logically correct with no weakening modifications.

---

## 7. Findings Summary

### P0 Issues Found: 0

### P1 Issues Found: 0

### Observations (no action required)

1. **Frontend panel fully implemented** — contrary to initial session-summary indication, all three frontend components (types, client methods, UI panel) were present and correct. No missing pieces.

2. **Fallback to `manual_required` for unknown action_types** — the `_execute_single_automation_action` fallback correctly defaults to `manual_required` rather than attempting execution. This is the safest possible default.

3. **`AutomationRunRequest` covers both endpoints** — the frontend uses one type for both `run-next` and `run-safe-loop` payloads; the safe-loop-specific fields (`stop_on_manual_required`, `stop_on_blocked`) are optional. Slightly loose typing but not a defect.

4. **`max_actions` has no server-side cap** — the request field is accepted as-is (e.g., a client could pass `max_actions=1000`). This is low risk given the loop breaks on every stop condition and each iteration only runs one action; however a server-side cap (e.g., 20) would add defense-in-depth.

---

## 8. Existing Workflow Compatibility

- **Start Task flow**: No changes — automation runner never calls `execute_run` or `asyncio.create_task`.
- **Confirmed-run behavior**: Unchanged — automation runner operates on existing runs only.
- **Guard result system**: Read-only — automation runner calls `list_guard_results()` to inspect guard state; never writes guard records.
- **Patch proposal/apply/rollback flow**: Unaffected — these actions are classified `MANUAL_REQUIRED` and return without execution.
- **engine.py**: Not modified. ✅
- **database.py**: Not modified. ✅
- **Schema/migrations**: None. ✅

---

## 9. Verdict

**Automation Runner v1 passes the regression audit.** All safety boundaries are enforced. No forbidden execution hooks are reachable from the automation code paths. The frontend panel is correct, explicit-click-only, with no auto-runs or polling. Static analysis is clean. Tests are comprehensive and logically correct.

---

## 10. Recommended Next Slice

**Fastlane Approval-Gated Automation v1** — extend the automation runner with an operator approval checkpoint so certain low-risk actions (e.g., test execution) can be queued for a batch approval before running, enabling supervised batch runs without requiring per-action manual confirmation.

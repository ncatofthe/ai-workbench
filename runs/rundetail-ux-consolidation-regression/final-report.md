# RunDetail UX Consolidation — Regression Pass

**Run ID:** rundetail-ux-consolidation-regression  
**Date:** 2026-05-25  
**Role:** Senior fullstack QA/safety engineer  
**Baseline:** 937 passed + 38 subtests | tsc/build passed | scripts/run_tests.sh passed  
**Status:** ✅ Clean — No P0/P1 issues found. No code changes required. 1 P3 gap documented.

---

## Summary

Full regression audit of RunDetail UX Consolidation v1 + logic fix (3 backend bugs corrected in prior pass). All 8 audit areas pass. No safety invariants were weakened. No new execution paths were introduced. One P3 type-gap noted (non-breaking). Recommended next slice: Persistent Source of Truth v1.

---

## Area 1 — Operator Queue `execute_approval` Behavior

**Verdict: ✅ Pass**

| Check | Result |
|---|---|
| Pending approval → `execute_approval` queue item | ✅ `_build_queue_item` lines 1767–1793: checks `step_approvals` for `status == "pending"` |
| Approved (not executed) approval → no `execute_approval` | ✅ Only `status == "pending"` triggers the branch; approved/rejected/executed fall through to normal workflow |
| Rejected approval → no `execute_approval` | ✅ Confirmed by test 4 in test file |
| Blocked/stale guard takes priority over `execute_approval` | ✅ Stale guard check (lines 1730–1741) and blocked guard check (lines 1748–1762) both return early before the approval branch |
| `execute_approval` item includes `approval_id` | ✅ `approval_id=pending_approval.id` |
| `execute_approval` item includes `approval_action_type` | ✅ `approval_action_type=approval_action` where `approval_action = pending_approval.action` |
| `approval_action_type` is underlying action, not `"execute_approval"` | ✅ `approval_action = getattr(pending_approval, "action", None) or ""` — e.g. `"run_tests_manual"` |
| `can_run_directly=False` | ✅ Hardcoded `can_run_directly=False` |
| `destination` is guidance field | ✅ `destination="approval_panel"` (navigation guidance only) |
| Endpoint remains read-only | ✅ `_build_queue_item` docstring: "creates no DB records, calls no providers, runs no commands" |
| `recommended_action` / `description` tells user to use approval panel | ✅ Description: "Review and approve it in the Automation Approvals panel to allow the bounded loop to proceed." |

---

## Area 2 — Operator Queue Endpoint Wiring

**Verdict: ✅ Pass**

`GET /api/runs/{run_id}/operator-queue` (lines 1619–1686):

- **Approval-aware path**: Fetches `run_approvals = _list_run_automation_approvals(run_id)` once before the step loop, passes step-filtered `step_approvals` to each `_build_queue_item` call. No bypass.
- **Approval filter**: `a.command == step.id or not a.command` — handles both step-scoped and run-scoped approvals correctly.
- **Runs with no approvals**: `_list_run_automation_approvals` returns `[]`; `step_approvals = []`; `_build_queue_item` defaults `step_approvals = approvals or []`; no error.
- **Missing/unknown approval fields**: `getattr(pending_approval, "action", None) or ""` guards against missing `action`; `hasattr(a.status, "value")` guards against non-enum status. Safe.
- **No tool_calls created**: Confirmed — `_build_queue_item` is pure analysis, no `create_tool_call`.
- **No approvals executed**: The `execute_approval` branch returns a display-only `OperatorQueueItem`; it does not call any execution helper.
- **No DB mutations**: No `create_*`, `update_*`, or `delete_*` storage calls inside the endpoint or `_build_queue_item`.
- **Sort + limit preserved**: After the loop, the existing priority sort and `[:limit]` slice are unchanged.

---

## Area 3 — Bounded Loop `stop_reason` Behavior

**Verdict: ✅ Pass**

| Scenario | Expected | Actual |
|---|---|---|
| Pending approval exists | `status=stopped_for_approval`, `stop_reason=pending_approval` | ✅ `lookup_action` resolves to `"run_tests_manual"`; `has_pending=True`; sets `loop_stop_reason="pending_approval"` |
| `pending_approval_id` populated | approval UUID | ✅ `_bounded_loop_find_pending_approval(run_id, step_id, lookup_action)` returns matching approval |
| `pending_approval_action_type` | `"run_tests_manual"` not `"execute_approval"` | ✅ `loop_pending_approval_action_type = lookup_action` |
| No approval at all | `stop_reason=needs_approval` | ✅ Fix 3: approval-eligible action blocked by `allow_safe_commands=False` → `stopped_for_approval` / `needs_approval` |
| Blocked guard | `stop_reason=blocked_guard` | ✅ BLOCKED branch sets `loop_stop_reason="blocked_guard"`, `loop_blocked_action_type=item.action_type` |
| Tests failed + stop_on_test_failure | `stop_reason=test_failed` | ✅ Sets `loop_stop_reason="test_failed"` at lines 6661 and 6876 |
| Max iterations | `stop_reason=max_iterations` | ✅ `else` branch of outer for-loop: `loop_stop_reason="max_iterations"` |
| No approvals created by bounded loop | ✅ | No `create_approval` call in the loop |
| No patches applied unless existing approved approval + full revalidation | ✅ | Unchanged — `_execute_approved_apply_patch` still requires approval |

**Key fix (`lookup_action`):** When `item.action_type == "execute_approval"`, all approval lookups (`_bounded_loop_find_approved_action`, `_bounded_loop_has_pending_approval`, `_bounded_loop_find_pending_approval`) now use `item.approval_action_type` (the underlying action, e.g. `"run_tests_manual"`) instead of the literal string `"execute_approval"`.

**Key fix (DIRECT_SAFE branch):** When `run_tests_manual` is encountered without a pending approval and `allow_safe_commands=False`, the loop now sets `final_status="stopped_for_approval"` and `loop_stop_reason="needs_approval"` instead of the previous generic `"blocked"`. This path is gated on `item.action_type in _APPROVAL_ELIGIBLE_ACTION_TYPES and req.stop_on_approval_required` to avoid regressions with genuinely blocked actions.

---

## Area 4 — Frontend Operator Cockpit

**Verdict: ✅ Pass**

`OperatorQueuePanel` component:

- **Current Operator Action block** (lines 2485–2546): Display-only. Shows `top.title`, `top.action_type`, `top.priority`, `top.approval_id` (truncated), `top.approval_action_type`. No buttons call any execution API.
- **execute_approval callout**: Renders `"⏳ Pending approval — review in Automation Approvals panel below"` text + truncated approval ID. No handler attached.
- **Refresh Queue button**: Calls `onRefresh()` → fetches `GET /operator-queue`. Read-only.
- **Automation Runner buttons** (`runAutomation("dry"|"next"|"loop")`): Pre-existing panel, unmodified. Uses `runAutomationSafeLoop`/`runAutomationNext` — these are the existing automation endpoints, not the operator queue or approval execution path.
- **No `useEffect` auto-executing automation**: `BoundedLoopPanel` and `OperatorQueuePanel` have no side-effect hooks that run automatically. Loops require explicit button press.
- **No polling**: No `setInterval`, no `setTimeout` triggering re-fetches.
- **`OperatorQueueItemCard`**: `onFocus` callback is for focusing a step in the guided panel, not for execution.

---

## Area 5 — BoundedLoopPanel Frontend

**Verdict: ✅ Pass**

- `stop_reason` displayed inline next to `status` badge when set and different from status string.
- `pending_approval` guidance block: Shows action type, truncated `pending_approval_id`. Text: "Open the Automation Approvals panel, review and approve it to allow the loop to continue." — actionable and unambiguous.
- `needs_approval` guidance block: Shows action type. Text: "Create one in the Automation Approvals panel, then re-run the loop."
- `test_failed` guidance block: "Review the failure output in the Patch-Test Lifecycle panel."
- Blocked guard block: Shows `blocked_action_type` with resolve guidance.
- `final_recommended_action` rendered in amber block when present.
- `stopped_for_approval` is no longer ambiguous — the two sub-states (`pending_approval` vs `needs_approval`) produce different UI blocks with different messaging.
- `runLoop()` is triggered only by explicit button press. No auto-execution.

---

## Area 6 — Tab / Label Compatibility

**Verdict: ✅ Pass**

Tab label map in `RunDetail.tsx` (lines 729–741):

| Tab key | Old label | New label |
|---|---|---|
| `timeline` | Timeline | Timeline (unchanged) |
| `team` | Team | Team (unchanged) |
| `spec` | Spec | Spec (unchanged) |
| `questions` | Questions | Questions (unchanged) |
| `plan` | Plan | Plan (unchanged) |
| `architecture` | Architecture | Architecture (unchanged) |
| `tasks` | Tasks | Tasks (unchanged) |
| `logs` | Logs | Logs (unchanged) |
| `result` | Result | Result (unchanged) |
| `tool-plan` | Tool-plan → | **Tool Plan** |
| `guided` | Guided | Guided (unchanged) |
| `patch-workflow` | Patch-workflow → | **Patch Workflow** |
| `operator-queue` | Operator-queue → | **Operator Cockpit** |
| `delivery` | Delivery → | **Delivery Report** |

- All 14 tab keys unchanged (internal routing unaffected).
- All 14 `{tab === "…"} &&` conditionals verified present (lines 747–917).
- No tab content removed or hidden.

---

## Area 7 — Workflow Compatibility

**Verdict: ✅ Pass (static)**

py_compile verified clean on all relevant test files:

| File | py_compile |
|---|---|
| `backend/src/storage/database.py` | ✅ OK |
| `backend/src/orchestrator/engine.py` | ✅ OK |
| `backend/src/models.py` | ✅ OK |
| `backend/src/api/routes.py` | ✅ OK |
| `tests/test_rundetail_ux_consolidation.py` | ✅ OK |
| `tests/test_semi_auto_operator_queue.py` | ✅ OK |
| `tests/test_bounded_autonomous_patch_test_fix_loop.py` | ✅ OK |
| `tests/test_real_project_dogfooding.py` | ✅ OK |

Frontend `tsc --noEmit`: ✅ exit 0, no output.

Compatibility guarantees from code inspection:
- `_build_queue_for_run` signature unchanged — existing callers unaffected.
- `_build_queue_item` new `approvals=` parameter is keyword-only with default `None` — all existing callers that omit it continue to work.
- `BoundedAutonomousLoopResponse` new fields are all `Optional` with `None` default — no breaking schema change.
- `OperatorQueueItem` new fields (`approval_id`, `approval_action_type`) are `Optional` with `None` default — no breaking change.
- `_automation_classify` unchanged — existing classifications for all pre-existing action types unaffected.
- DIRECT_SAFE branch change is gated on `item.action_type in _APPROVAL_ELIGIBLE_ACTION_TYPES and req.stop_on_approval_required` — only triggers for approval-eligible actions when caller explicitly requests approval-required stops. Existing callers that don't set `stop_on_approval_required=True` are unaffected.
- apply-patch, run-command, approved-execution, guard storage runtimes: confirmed unchanged.

---

## Area 8 — Runtime Boundary Static Scan

**Verdict: ✅ Pass — 0 violations in all new/modified code sections**

Scanned regions: `get_run_operator_queue` (lines 1644–1686), `_build_queue_item` execute_approval branch (1764–1793), `_build_queue_for_run` (2256–2285), bounded loop `manual_required` section (6576–6760), bounded loop DIRECT_SAFE blocked path (6769–6860).

| Pattern | Hits in new code |
|---|---|
| `execute_run` | 0 ✓ |
| `asyncio.create_task` | 0 ✓ |
| `apply_project_patch` | 0 ✓ |
| `propose_project_patch` | 0 ✓ |
| `subprocess.run` | 0 ✓ |
| `os.system` | 0 ✓ |
| `create_tool_call` | 0 ✓ |
| `open(..., "w")` | 0 ✓ |
| `ollama.` (call) | 0 ✓ |
| `chat_completion` | 0 ✓ |
| `claude_client` | 0 ✓ |
| `codex_client` | 0 ✓ |

Note: `execute_run`, `apply_project_patch`, `propose_project_patch`, `subprocess`, `create_tool_call` appear in existing pre-existing code and import blocks — they are not new additions and are not reachable from the modified paths.

`database.py` new references: 0 (confirmed — grep for all new symbols returns empty).  
`engine.py` new references: 0 (confirmed).

---

## P0 / P1 / P2 / P3 Issues

**P0 (blocking):** None.

**P1 (high):** None.

**P2 (medium):** None.

**P3 (low — non-breaking):**

- **`"approval_panel"` missing from `OperatorQueueDestination` TypeScript union** (`frontend/src/types/index.ts` line 593–599). The backend sets `destination="approval_panel"` on `execute_approval` items. The TypeScript type union does not include this value. The build passes because TypeScript does not validate API responses at runtime, and no code performs a type-narrow comparison against `"approval_panel"`. Impact: zero — no compile error, no runtime error, no user-visible issue. Fix: add `| "approval_panel"` to `OperatorQueueDestination`. Deferred to next slice or a targeted type-cleanup pass.

---

## Changes Made This Pass

**None.** No code changes were required. All 8 audit areas passed clean. The three P0-level logic bugs (operator queue approvals bypass, wrong lookup_action in bounded loop, no-approval path returning blocked) were fixed in the prior logic-fix pass and are verified here.

---

## Files Audited

| File | Touched this pass |
|---|---|
| `backend/src/models.py` | Read only |
| `backend/src/api/routes.py` | Read only |
| `backend/tests/test_rundetail_ux_consolidation.py` | Read only |
| `backend/tests/test_semi_auto_operator_queue.py` | Read only (py_compile) |
| `backend/tests/test_bounded_autonomous_patch_test_fix_loop.py` | Read only (py_compile) |
| `backend/tests/test_real_project_dogfooding.py` | Read only (py_compile) |
| `frontend/src/types/index.ts` | Read only |
| `frontend/src/pages/RunDetail.tsx` | Read only |

**`database.py`:** Not touched. Confirmed: 0 new references to any added symbol.  
**`engine.py`:** Not touched. Confirmed: 0 new references to any added symbol.  
**Providers:** Not touched. Not referenced from any modified path.

---

## Verification Commands (for host)

```bash
cd /Users/hatss/Инструменты/ai-workbench/backend
.venv/bin/python -m py_compile src/storage/database.py
.venv/bin/python -m py_compile src/models.py
.venv/bin/python -m py_compile src/api/routes.py
.venv/bin/python -m py_compile tests/test_rundetail_ux_consolidation.py
.venv/bin/python -m py_compile tests/test_semi_auto_operator_queue.py
.venv/bin/python -m py_compile tests/test_bounded_autonomous_patch_test_fix_loop.py
.venv/bin/python -m py_compile tests/test_real_project_dogfooding.py
.venv/bin/pytest -q tests/test_rundetail_ux_consolidation.py        # expect 15 passed
.venv/bin/pytest -q tests/test_semi_auto_operator_queue.py           # expect 20 passed
.venv/bin/pytest -q tests/test_bounded_autonomous_patch_test_fix_loop.py  # expect 36 passed
.venv/bin/pytest -q tests/test_real_project_dogfooding.py            # expect 23 passed
.venv/bin/pytest -q tests/test_full_delivery_loop.py                 # expect 55 passed
.venv/bin/pytest -q tests/test_dogfooding_full_cycle.py              # expect 31 passed
.venv/bin/pytest -q tests/test_agent_result_patch_draft_bridge.py    # expect 36 passed
.venv/bin/pytest -q tests/test_agent_execution_harness.py            # expect 46 passed
.venv/bin/pytest -q tests/test_approval_gated_automation.py          # expect 41 passed
.venv/bin/pytest -q tests/test_automation_runner.py                  # expect 18 passed
.venv/bin/pytest -q                                                  # expect 937 passed + 38 subtests

cd /Users/hatss/Инструменты/ai-workbench/frontend
npx tsc --noEmit                                                     # expect: exit 0, no output
npm run build                                                         # expect: build success

cd /Users/hatss/Инструменты/ai-workbench
bash scripts/run_tests.sh                                            # expect: passed
```

---

## Remaining UX Gaps

| GAP | Description | Status |
|---|---|---|
| GAP-005 | 14-tab navigation — tab count unchanged | ⚠️ Partial: "Operator Cockpit" label + cockpit block added; tabs still 14 |
| GAP-006 | No persistent requirements table | Open |
| GAP-008–GAP-010, GAP-012, GAP-013 | Various UX polish gaps | Open, unchanged |

---

## Recommended Next Slice

**Persistent Source of Truth v1**

Build a persistent, per-run requirements table that the operator can view and update across sessions. This closes GAP-006 and provides the source-of-truth anchor currently missing from the operator cockpit workflow. Candidate surfaces: sidebar panel pinned to the run view, or a dedicated "Requirements" sub-panel in the Operator Cockpit tab.

Alternative: **Tab Navigation Consolidation v1** — collapse 14 tabs into 5–6 primary tabs with a "More" overflow to address GAP-005 fully.

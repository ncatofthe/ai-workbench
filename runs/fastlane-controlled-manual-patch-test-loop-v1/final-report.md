# Fastlane Controlled Manual Patch-Test Loop v1

## Summary

Added a controlled manual patch-test lifecycle layer after guarded apply.

The flow now has a read-only step lifecycle endpoint plus a compact RunDetail lifecycle panel that lets an operator manually refresh lifecycle state, manually run the configured safe test command, and manually analyze failed test output through the existing heuristic analyzer.

No autonomous execution was added.

## Patch Lifecycle Endpoint Behavior

Added:

`GET /api/runs/{run_id}/steps/{step_id}/patch-lifecycle`

The endpoint:

- verifies the run exists;
- verifies the step belongs to the run;
- reads existing `ToolCall` records for the step;
- reads existing persisted guard results for the step;
- summarizes latest proposal, apply, and test tool calls;
- reports whether latest tests appear to have run after latest successful apply;
- returns `recommended_manual_next_action`:
  - `create_guard`
  - `create_proposal`
  - `apply_patch`
  - `run_tests_manual`
  - `analyze_failed_tests_manual`
  - `review_success`

It is read-only: no DB writes, no ToolCalls, no patch apply, no command execution, no providers.

## Manual Run Tests Behavior

RunDetail now shows a compact `Patch-Test Lifecycle` panel inside `StepPatchSection`.

The panel has a manual `Run tests manually` button. It calls the existing safe command endpoint only:

`POST /api/projects/{project_id}/tools/run-command`

with:

- `command_kind: "test"`
- `run_id`
- `step_id`
- `agent_id`

The button is only enabled after a lifecycle refresh shows that a patch was applied and a project test command is configured. It does not auto-run after apply.

## Test Result Lifecycle Behavior

The lifecycle panel displays:

- guard availability;
- proposal status;
- apply status;
- test status: `not run`, `passed`, or `failed`;
- latest test command;
- return code;
- short stdout/stderr previews;
- compact guard lifecycle badges:
  - guard linked;
  - guard revalidated before apply;
  - no-guard override.

The lifecycle endpoint uses best-effort timestamp comparison to determine whether tests ran after latest apply and exposes confidence notes when linkage is imperfect.

## Failed Test Analysis / Manual Prep Behavior

If the latest linked test command failed, the panel enables a manual `Analyze failed tests manually` button.

It calls the existing deterministic analyzer endpoint:

`POST /api/projects/{project_id}/tools/analyze-command-result`

This remains manual and heuristic. It does not call providers or generate a fix automatically.

The UI also shows a compact failure context block for the next manual patch proposal.

## UI Changes

Updated `RunDetail.tsx`:

- added patch lifecycle state local to `StepPatchSection`;
- added manual refresh;
- added manual run tests;
- added manual failed-test analysis;
- added compact lifecycle status cards and failure context display;
- refreshes lifecycle after a manual apply and after manual test/analyze actions.

No global store, new route/page, or broad RunDetail refactor was added.

## Safety Boundaries

Confirmed:

- no autonomous mode;
- no auto-apply;
- no auto-run tests;
- no automatic analyze;
- no automatic rollback;
- no provider execution;
- no `execute_run`;
- no `asyncio.create_task`;
- no approval execution;
- no DB schema changes;
- no migrations;
- no Start Task changes;
- no confirmed-run behavior changes;
- run-command remains limited to existing project profile safe command behavior;
- apply still requires manual `confirm=true`.

## What Was Intentionally Not Implemented

- No automatic failure-to-fix generation.
- No automatic test run after apply.
- No new arbitrary command runner.
- No new persistence model for lifecycle snapshots.
- No approval-gated execution wiring.
- No autonomous test/fix loop.

## Files Changed

- `backend/src/api/routes.py`
- `backend/tests/test_controlled_manual_patch_test_loop.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/fastlane-controlled-manual-patch-test-loop-v1/final-report.md`

## Whether database.py Was Touched

`backend/src/storage/database.py` was not edited in this slice.

The working tree already had pre-existing unrelated dirty files; those were left untouched.

## Whether engine.py Was Touched

`backend/src/orchestrator/engine.py` was not edited in this slice.

## Whether Run-Command Safety Changed

No. The UI uses the existing `run-command` endpoint and passes `command_kind: "test"`. No arbitrary command execution path was added.

## Exact Check Results

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`: passed.
- `cd backend && .venv/bin/pytest -q tests/test_controlled_manual_patch_test_loop.py`: `10 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_apply_guard_revalidation.py`: `11 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guarded_patch_proposal.py`: `17 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_proposal_validation.py`: `17 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_api_wiring.py`: `18 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_list_get_api.py`: `15 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_storage.py`: `30 passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_storage_contract.py`: `19 passed, 7 subtests passed`.
- `cd backend && .venv/bin/pytest -q tests/test_guard_result_api_contract.py`: `18 passed, 7 subtests passed`.
- `cd backend && .venv/bin/pytest -q`: `597 passed, 38 subtests passed`.
- `cd frontend && npx tsc --noEmit`: passed.
- `cd frontend && npm run build`: passed.
- `bash scripts/run_tests.sh`: passed, including backend `597 passed, 38 subtests passed`.

## P0/P1/P2/P3 Issues

No P0/P1/P2/P3 issues found.

## Recommended Next Slice

Fastlane Controlled Manual Patch-Test Loop Regression Pass v1.

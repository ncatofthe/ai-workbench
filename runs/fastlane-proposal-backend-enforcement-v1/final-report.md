# Fastlane Proposal Backend Enforcement v1

## Summary

Implemented backend-enforced `guard_result_id` support for step-linked patch proposal creation. Proposals can now be created with a validated persisted Source-of-Truth Guard result, or with an explicit no-guard override when no guard result is selected. Guard validation failures happen before proposal `tool_call` creation.

Apply-patch enforcement was intentionally not implemented.

## Backend proposal guard policy

For `POST /api/projects/{project_id}/tools/propose-patch`:

- Existing callers remain compatible when the proposal is not linked to a real persisted `RunStep`.
- If `guard_result_id` is provided:
  - `run_id` and `step_id` are required.
  - The run must exist.
  - The step must exist and belong to the run.
  - The guard result must exist and belong to the same run and step.
  - The guard result is compared with proposal payload fields: `file_path`, `old_text`, and `new_text`.
  - Stale, blocked, mismatched, wrong-run, wrong-step, or unacknowledged warning guards are rejected before proposal creation.
- If no `guard_result_id` is provided:
  - Real step-linked proposals require explicit `no_guard_override=true`.
  - The override does not override a selected blocked/stale/mismatched guard.

## Request/response changes

`ProposePatchRequest` now accepts optional:

- `guard_result_id`
- `guard_warning_acknowledged`
- `no_guard_override`

`ProposePatchResponse` now may include:

- `guard_result_id`
- `guard_validation_valid`
- `guard_validation_reasons`
- `guard_validation_warnings`
- `no_guard_override`

Existing response fields are preserved.

## Frontend behavior

RunDetail now sends guard metadata with patch proposal requests:

- A selected persisted guard result is sent as `guard_result_id` only after the user validates it for the current proposal payload.
- Warning guards require the existing warning acknowledgement before proposal creation.
- Invalid, stale, blocked, or unvalidated selected guard results disable proposal creation.
- If no persisted guard result is selected, the existing explicit no-guard override checkbox must be checked.
- The UI shows compact proposal feedback:
  - linked guard result id when the backend links one;
  - explicit no-guard override when used.

The guard is still manual. No guard check, proposal creation, patch apply, tests, commands, providers, or tool execution are triggered automatically.

## Guard linking behavior

After successful guarded proposal creation:

- the existing proposal `tool_call` is created by the existing propose-patch flow;
- `link_guard_result_to_proposal(guard_result_id, proposal_tool_call_id)` links the persisted guard audit record to the proposal;
- validation failures create no proposal `tool_call`.

## no_guard_override behavior

- `no_guard_override=true` allows real step-linked proposal creation only when no `guard_result_id` is selected.
- `no_guard_override` is recorded in request/response metadata.
- It does not override a selected blocked guard.

## Tests added

Added `backend/tests/test_guarded_patch_proposal.py` with 17 tests covering:

- valid allowed guard success;
- guard result linked to proposal `tool_call`;
- warning guard rejected without acknowledgement;
- warning guard accepted with acknowledgement;
- blocked guard rejected;
- stale guard rejected;
- wrong-run guard rejected;
- wrong-step guard rejected;
- missing selected guard rejected;
- payload mismatch rejected;
- missing guard without override rejected for real step-linked proposal;
- missing guard with override succeeds;
- override cannot bypass selected blocked guard;
- validation failure creates no proposal `tool_call`;
- successful proposal does not apply patches or run tests;
- run/step status remains unchanged;
- non-step-linked proposal compatibility.

Also strengthened `backend/tests/test_guard_result_proposal_validation.py` so `warning_acknowledged=true` is verified as valid for warning guard validation.

## Safety boundaries

Confirmed:

- No DB schema changes.
- No migrations.
- No `database.py` edits in this slice.
- No `engine.py` edits in this slice.
- No `project_tools.py` edits in this slice.
- No `model_router.py` edits in this slice.
- No provider code edits.
- No `execute_run`.
- No `asyncio.create_task`.
- No provider/tool execution.
- No `create_tool_call` except the existing proposal `tool_call` created by propose-patch.
- No auto-apply.
- No auto-run tests or commands.
- No approval execution.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.
- Apply-patch remains manual and unchanged.

## What was intentionally not implemented

- No apply-patch guard enforcement.
- No approval execution.
- No automatic guard checks.
- No automatic proposal creation.
- No automatic patch generation.
- No automatic tests/commands.
- No new DB tables or migrations.

## Files changed

- `backend/src/models.py`
- `backend/src/api/routes.py`
- `backend/tests/test_guarded_patch_proposal.py`
- `backend/tests/test_guard_result_proposal_validation.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/fastlane-proposal-backend-enforcement-v1/final-report.md`

## Exact check results

Passed:

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
- `backend/.venv/bin/pytest -q tests/test_guarded_patch_proposal.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_wiring.py` — 18 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_list_get_api.py` — 15 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_proposal_validation.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage.py` — 30 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage_contract.py` — 19 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_contract.py` — 18 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q` — 576 passed, 38 subtests passed
- `frontend/npx tsc --noEmit`
- `frontend/npm run build`
- `bash scripts/run_tests.sh` — backend 576 passed, 38 subtests passed; frontend TypeScript check passed

## P0/P1/P2/P3 issues

| Priority | Area | Problem | Status |
| --- | --- | --- | --- |
| P1 | Guard proposal validation | Warning guard acknowledgement was accepted by request shape but not honored by the validation endpoint. | Fixed. |

No remaining P0/P1/P2/P3 issues found.

## Recommended next slice

Fastlane Proposal Backend Enforcement Regression Pass v1.

# Fastlane Proposal Backend Enforcement Regression Pass v1

## Summary

Fastlane Proposal Backend Enforcement v1 is stable. The backend now enforces persisted guard-result validation before real step-linked patch proposal creation, and the frontend sends only selected, validated guard metadata into proposal requests. No P0/P1/P2/P3 issues were found in this regression pass.

No source-code changes were made during this regression pass.

## Proposal guard policy validation

Validated by code inspection and tests:

- Valid allowed `guard_result_id` succeeds.
- Warning guard rejects unless `guard_warning_acknowledged=true`.
- Warning guard with acknowledgement succeeds.
- Blocked guard rejects.
- Stale guard rejects.
- Guard from another run rejects.
- Guard from another step rejects.
- Payload mismatch rejects.
- Missing `guard_result_id` rejects real step-linked proposals unless `no_guard_override=true`.
- `no_guard_override=true` succeeds only when no selected invalid/blocked/stale guard is being used.
- `no_guard_override` cannot override selected blocked/stale/mismatched guard validation.

The guard preflight runs before `_run_logged_read_tool`, so policy rejection happens before proposal `tool_call` creation.

## Tool call safety validation

Validated:

- Validation failures create no proposal `tool_call`.
- Successful proposal creates only the normal `propose-patch` `tool_call`.
- Successful proposal does not apply patches.
- Successful proposal does not run tests or commands.
- Successful proposal does not call providers.
- Run status remains unchanged.
- Step status remains unchanged.

## Guard result linking validation

Validated:

- Successful guarded proposal calls `link_guard_result_to_proposal` after proposal creation.
- The linked guard result can be read back from guard result storage with `proposal_tool_call_id`.
- Failed proposals do not link guard results.
- Repeated/compatible proposal behavior is covered by storage/list/get and guarded proposal tests.

## Backward compatibility validation

Validated:

- Non-step-linked/global proposal behavior remains compatible.
- Old request payloads without guard fields still serialize and work where not linked to a real persisted `RunStep`.
- Response shape remains backward compatible; guard fields are optional additions.
- Frontend TypeScript accepts the updated API shapes.

## Frontend validation

Validated in `RunDetail.tsx`:

- Selected persisted `guard_result_id` is sent only when guard proposal validation is valid.
- Invalid selected guard disables proposal preview/create.
- Blocked/stale selected guard disables proposal preview/create.
- Warning guard requires explicit acknowledgement.
- No selected guard requires explicit `no_guard_override`.
- Guard checks are not auto-run.
- Patch proposals are not auto-created.
- Apply remains manual and unchanged.

## Apply-patch untouched validation

Validated:

- `apply-patch` still requires manual `confirm=true`.
- `apply-patch` behavior did not change in this regression pass.
- `apply-patch` does not require or use `guard_result_id` yet.
- No apply enforcement was added.

## Runtime boundary validation

Confirmed:

- No new `execute_run` path was added.
- No new `asyncio.create_task` path was added.
- No new provider calls were added.
- No new shell/subprocess path was added by this slice.
- No run-command/test execution was added.
- No approval execution was added.
- No autonomous behavior was added.

Existing runtime code in `routes.py` still contains pre-existing run/test/tool routes, but the proposal guard enforcement path does not invoke them.

## Scope boundary validation

Confirmed for this regression pass:

- `database.py` was not edited.
- `engine.py` was not edited.
- `project_tools.py` was not edited.
- `model_router.py` was not edited.
- Provider files were not edited.
- No schema changes or migrations were added.
- Start Task flow was not changed.
- Confirmed-run behavior was not changed.

Note: the working tree was already dirty from accepted fast-lane slices. This report records only actions taken during this regression pass.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| - | - | No issues found. | None. |

## Changes made

No source-code changes.

Created report only:

- `runs/fastlane-proposal-backend-enforcement-regression-v1/final-report.md`

## Files changed

- `runs/fastlane-proposal-backend-enforcement-regression-v1/final-report.md`

## Exact check results

Passed:

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
- `backend/.venv/bin/pytest -q tests/test_guarded_patch_proposal.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_proposal_validation.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_wiring.py` — 18 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_list_get_api.py` — 15 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage.py` — 30 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage_contract.py` — 19 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_contract.py` — 18 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q` — 576 passed, 38 subtests passed
- `frontend/npx tsc --noEmit`
- `frontend/npm run build`
- `bash scripts/run_tests.sh` — backend 576 passed, 38 subtests passed; frontend TypeScript check passed

## Recommended next slice

Fastlane Apply Guard Revalidation v1.

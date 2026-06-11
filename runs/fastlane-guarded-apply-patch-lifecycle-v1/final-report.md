# Fastlane Guarded Apply + Patch Lifecycle v1

## Summary

Implemented guarded apply-time revalidation and compact patch lifecycle visibility. A manual `apply-patch` now revalidates the guard result linked to the source proposal before applying files, preserves the existing `confirm=true` requirement, and links the same guard result to the successful apply `tool_call`.

No autonomous execution was added.

## Apply-time guard revalidation behavior

When `apply-patch` receives a `proposal_id`, the backend now inspects the proposal `tool_call` and linked guard result:

- If the proposal is linked to a guard result, apply preflight revalidates before creating/running the apply operation.
- Revalidation checks:
  - guard exists;
  - guard belongs to the same run/step when request context is present;
  - guard is not stale;
  - guard decision is not blocked;
  - apply payload still matches the guard input snapshot for `file_path`, `old_text`, and `new_text`;
  - warning guard acknowledgement was present in proposal metadata/input.
- Revalidation failure returns `400`, does not mutate files, and does not create a successful apply `tool_call`.
- Revalidation success preserves the existing manual apply path and links `guard_result_id` to `apply_tool_call_id`.

## Manual confirm behavior

Preserved:

- `confirm=true` is still mandatory.
- `confirm=false` still does not apply files.
- A valid guard does not bypass `confirm=true`.
- `confirm=true` does not bypass failed guard revalidation.

## no_guard_override apply behavior

If a proposal was created with explicit `no_guard_override=true` and has no guard result:

- manual apply remains allowed, matching existing product behavior;
- no fake guard result is created;
- response metadata reports `guard_revalidated=false` and `no_guard_override=true`;
- UI shows a compact no-guard override warning.

## Guard lifecycle metadata

Proposal responses and proposal `tool_call.output_json` now include compact guard metadata where applicable:

- `guard_result_id`
- `guard_validation_valid`
- `guard_validation_reasons`
- `guard_validation_warnings`
- `no_guard_override`

Apply responses and apply `tool_call.output_json` now include:

- `guard_result_id`
- `guard_revalidated`
- `guard_revalidation_reasons`
- `guard_revalidation_warnings`
- `no_guard_override`

Successful guarded apply calls `link_guard_result_to_apply(guard_result_id, apply_tool_call_id)`.

## RunDetail UI changes

RunDetail now shows compact lifecycle signals:

- proposal/apply tool call badges:
  - `Guard linked: <short id>`;
  - `Guard revalidated before apply`;
  - `No-guard override`;
- Guard History items show:
  - `proposal linked`;
  - `apply linked`;
- successful apply result shows:
  - guard revalidated id when present;
  - no-guard override warning when applicable;
  - manual next-action hint: `Next manual step: run tests`.

The UI does not auto-run guard checks, proposals, apply, tests, commands, or providers.

## Tests added

Added `backend/tests/test_apply_guard_revalidation.py` with 11 focused tests covering:

- `apply-patch` still requires `confirm=true`;
- valid linked allowed guard permits manual apply;
- successful apply links guard result to `apply_tool_call_id`;
- stale linked guard blocks apply;
- blocked linked guard blocks apply;
- payload mismatch blocks apply;
- missing linked guard result blocks guarded apply;
- failed guard revalidation does not mutate files;
- `confirm=true` does not bypass failed guard revalidation;
- no-guard override proposal can still apply manually;
- apply does not run tests or mutate run/step status;
- existing unguarded/manual apply behavior remains compatible;
- failed revalidation does not add apply link.

I did not create `backend/tests/test_guarded_patch_lifecycle.py`; the lifecycle invariants are covered by `test_apply_guard_revalidation.py` plus existing guard storage/list/get tests.

## Safety boundaries

Confirmed:

- No autonomous mode.
- No auto-apply.
- No auto-run tests/commands.
- No provider execution.
- No `execute_run`.
- No `asyncio.create_task`.
- No approval execution.
- No Start Task flow changes.
- No confirmed-run behavior changes.
- No schema changes.
- No migrations.
- `database.py` was not edited in this slice.
- `engine.py` was not edited in this slice.
- `project_tools.py` was not edited in this slice.
- `model_router.py` was not edited in this slice.
- Provider files were not edited.

## What was intentionally not implemented

- No apply approval workflow.
- No automatic test execution after apply.
- No autonomous patch-test loop.
- No schema/storage changes.
- No new routes beyond existing apply/proposal behavior.
- No provider execution.

## Files changed

- `backend/src/api/routes.py`
- `backend/src/models.py`
- `backend/tests/test_apply_guard_revalidation.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/fastlane-guarded-apply-patch-lifecycle-v1/final-report.md`

## Whether protected areas were touched

- `database.py`: not touched in this slice.
- `engine.py`: not touched in this slice.
- Apply-patch behavior changed only by adding pre-apply guard revalidation for guarded proposals, optional response metadata, and post-success guard-result linking. Manual `confirm=true` behavior remains required.

## Exact check results

Passed:

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
- `backend/.venv/bin/pytest -q tests/test_apply_guard_revalidation.py` — 11 passed
- `backend/.venv/bin/pytest -q tests/test_guarded_patch_proposal.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_proposal_validation.py` — 17 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_wiring.py` — 18 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_list_get_api.py` — 15 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage.py` — 30 passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage_contract.py` — 19 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_contract.py` — 18 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q` — 587 passed, 38 subtests passed
- `frontend/npx tsc --noEmit`
- `frontend/npm run build`
- `bash scripts/run_tests.sh` — backend 587 passed, 38 subtests passed; frontend TypeScript check passed

Not run:

- `backend/.venv/bin/pytest -q tests/test_guarded_patch_lifecycle.py` — file was not created; lifecycle coverage is included in `test_apply_guard_revalidation.py`.

## P0/P1/P2/P3 issues

| Priority | Area | Problem | Status |
| --- | --- | --- | --- |
| - | - | No issues found after implementation and checks. | None. |

## Recommended next slice

Fastlane Guarded Apply Regression Pass v1.

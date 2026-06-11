# Run Steps Timeline

## Summary

Runs now have a normalized `run_steps` timeline. The orchestrator records visible steps for its current planning pipeline, and the Run Detail page shows those steps as a timeline.

## Changes

- `backend/src/models.py`
  - Added `RunStep`.
  - Added `current_step_id` to `Run`.
- `backend/src/storage/database.py`
  - Added `run_steps` table creation and migration checks.
  - Added `current_step_id` migration for `runs`.
  - Added `create_run_step(...)`, `update_run_step(...)`, and `list_run_steps(...)`.
- `backend/src/api/routes.py`
  - Added `GET /api/runs/{run_id}/steps`.
- `backend/src/orchestrator/engine.py`
  - Orchestrator now records these steps:
    - Initialize run
    - Capture task input
    - Load orchestrator instructions
    - Create execution plan
    - Save plan artifact
    - Generate final report
    - Finalize run
  - Active step is tracked through `runs.current_step_id`.
  - Failed runs mark the active step as failed and clear `current_step_id`.
- `backend/tests/test_run_steps.py`
  - Added fallback-orchestrator coverage proving visible steps are recorded and completed.
- `frontend/src/types/index.ts`
  - Added `RunStep`.
  - Added `current_step_id` to `Run`.
- `frontend/src/api/client.ts`
  - Added `getRunSteps(...)`.
- `frontend/src/pages/RunDetail.tsx`
  - Added Timeline tab.
  - Polls run details and steps together.
  - Shows step status, id, agent, timestamps, input, output, and errors.

## Verification

- `python3 -m py_compile backend/src/models.py backend/src/storage/database.py backend/src/api/routes.py backend/src/orchestrator/engine.py backend/tests/test_run_steps.py` passed.
- `.venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py tests/test_run_steps.py` passed: 14 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Steps are still orchestrator pipeline steps, not delegated specialist-agent tasks.
- There is no parent/child DAG view yet, although `parent_step_id` exists.
- Stop still marks the run stopped in storage but does not cancel an already running background coroutine.

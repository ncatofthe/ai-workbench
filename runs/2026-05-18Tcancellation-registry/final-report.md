# Cancellation Registry

## Summary

Stop now cancels active background runs instead of only changing the database status.

## Changes

- `backend/src/orchestrator/cancellation.py`
  - Added an in-process registry for active run tasks.
  - Added `register_run_task(...)`, `cancel_run_task(...)`, `is_run_task_active(...)`, and `clear_run_tasks(...)`.
- `backend/src/api/routes.py`
  - `POST /api/runs` now registers the created background task.
  - `POST /api/runs/{run_id}/stop` now cancels the registered task when active.
  - Stop response includes `task_cancelled`.
  - Already terminal runs are not overwritten as stopped.
- `backend/src/orchestrator/engine.py`
  - Handles `asyncio.CancelledError`.
  - Marks the active step as `stopped`.
  - Clears `current_step_id`.
  - Marks the run as `stopped` with result `Run stopped by user.`
- `backend/tests/test_cancellation.py`
  - Added coverage that Stop cancels a registered task.
  - Added coverage that the orchestrator stores stopped run/step state on cancellation.
- `scripts/run_tests.sh`
  - Added syntax check for `src/orchestrator/cancellation.py`.

## Verification

- `python3 -m py_compile backend/src/orchestrator/cancellation.py backend/src/orchestrator/engine.py backend/src/api/routes.py backend/tests/test_cancellation.py` passed.
- `.venv/bin/python -m pytest -q tests/test_cancellation.py tests/test_run_steps.py tests/test_project_profiles.py tests/test_path_anchoring.py` passed: 16 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Cancellation is in-process only. If the backend process restarts, active task references are lost.
- Long synchronous subprocess calls are not cancel-aware yet; project tool commands still rely on their timeout.
- There is not yet a UI notice showing whether Stop cancelled a live task or only marked storage state.

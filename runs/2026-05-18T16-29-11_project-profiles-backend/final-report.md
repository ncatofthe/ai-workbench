# Backend Phase 1 Project Profiles Report

## Summary

Implemented backend-only Project Profiles for AI Workbench.

## Changed Files

- `backend/src/models.py`
- `backend/src/storage/database.py`
- `backend/src/api/routes.py`
- `backend/src/orchestrator/engine.py`
- `backend/src/approvals/safety.py`
- `backend/tests/test_project_profiles.py`
- `scripts/run_tests.sh`

## Implementation Notes

- Extended `Project` into an execution profile with path, stack, package manager, test/build commands, safe commands, blocked commands, ignore paths, and `updated_at`.
- Extended `Run` and `CreateRunRequest` with `project_id` and `project_path`.
- Added SQLite migration helpers that add missing columns to `projects` and `runs` while preserving existing data.
- Added JSON encode/decode for project list fields.
- Added path validation for absolute existing directories, rejecting files, missing paths, root, home root, and obvious system directories.
- Added `GET /api/projects/{id}` and `PATCH /api/projects/{id}`.
- Updated `POST /api/runs` to require a known project, store project context, and pass project metadata into the planning-only orchestrator.
- Updated orchestrator artifacts to include project metadata in `input.md` and `final-report.md`.
- Added project-scoped endpoints for workspace status, tests, and builds.
- Project commands use `shlex.split`, `shell=False`, and project `cwd`.
- Blocked or dangerous project commands return `approval_required` and do not execute.
- Updated `scripts/run_tests.sh` to run backend pytest from `backend/.venv` when available and fail on backend test failures.

## Verification

- `python3 -m py_compile backend/src/models.py backend/src/storage/database.py backend/src/api/routes.py backend/src/orchestrator/engine.py backend/src/approvals/safety.py backend/tests/test_project_profiles.py`: passed.
- `cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py`: passed, 5 tests.
- `bash scripts/run_tests.sh`: passed.

## Limitations

- Frontend was not updated in this task, so the current UI does not yet send the required `project_id` for new runs.
- Approval records are not created for project tool endpoints yet; blocked/dangerous commands return an `approval_required` response.
- Orchestrator remains planning-only and does not perform delegated execution.


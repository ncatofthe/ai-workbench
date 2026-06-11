# Approval Execute Flow

## Summary

Approving a project tool approval now executes the original stored command once, in the approved project directory, using the same shell-free execution path as normal safe project commands.

## Changes

- `backend/src/storage/database.py`
  - Added `get_approval(...)` so approval routes can inspect status before resolving.
- `backend/src/api/routes.py`
  - Refactored project command execution into `_execute_project_command(...)`.
  - `POST /api/approvals/{id}/approve` now:
    - rejects unknown approvals,
    - does not re-run already resolved approvals,
    - resolves pending approvals,
    - executes `project:{id}` commands with `cwd=project.path`,
    - returns `{ approval, execution, already_resolved }`.
- `backend/tests/test_project_profiles.py`
  - Added coverage that an approved project command executes once and repeated approval does not execute again.
- `frontend/src/types/index.ts`
  - Added `ApprovalDecisionResult`.
- `frontend/src/api/client.ts`
  - Typed `approveRequest(...)`.
- `frontend/src/pages/Approvals.tsx`
  - Project approvals now show `Approve & Run`.
  - After approval, UI shows a compact execution notice with status, exit code, and report path.

## Verification

- `python3 -m py_compile backend/src/storage/database.py backend/src/api/routes.py backend/tests/test_project_profiles.py` passed.
- `.venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py` passed: 13 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Approval rows still do not have dedicated `project_id`, `risk_level`, `requested_by`, or execution result columns.
- Execution output is returned to the approval API response and written to a report, but not persisted as a normalized `tool_calls` row yet.
- The approval UI does not show historical execution output after page refresh.

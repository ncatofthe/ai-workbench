# Project Tool Approval Rows

## Summary

Project-scoped test/build commands now create persistent approval rows whenever execution is blocked by policy. Repeated requests for the same pending project command reuse the existing approval instead of creating duplicates.

## Changes

- `backend/src/api/routes.py`
  - `approval_required` responses now call `create_approval(...)`.
  - Responses include `approval_id`.
  - Approval descriptions include project name, project id, project path, command type, and reason.
- `backend/src/storage/database.py`
  - Added `find_pending_approval(...)` for exact pending approval lookup by `run_id`, `action`, and `command`.
- `backend/tests/test_project_profiles.py`
  - Added assertions that unlisted project commands create a pending approval row and never execute.
  - Added coverage that repeated identical project command requests reuse the same pending approval.
- `frontend/src/types/index.ts`
  - Added optional `approval_id` to `ProjectToolResult`.
- `frontend/src/pages/Tools.tsx`
  - Displays the approval id when a project tool action requires approval.

## Verification

- `python3 -m py_compile backend/src/storage/database.py backend/src/api/routes.py backend/tests/test_project_profiles.py` passed.
- `.venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py` passed: 12 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Approving the request records the decision, but does not yet resume and execute the original project command.
- Repeated clicks can still create duplicate approval requests for the same project command.
- Approval records do not yet have dedicated `project_id`, `risk_level`, or `requested_by` columns.

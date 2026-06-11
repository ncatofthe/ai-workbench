# Tool Calls History

## Summary

Project tool executions are now persisted in a normalized `tool_calls` table and shown in the Tools page for the selected project.

## Changes

- `backend/src/models.py`
  - Added `ToolCall`.
- `backend/src/storage/database.py`
  - Added `tool_calls` table creation and migration checks.
  - Added `create_tool_call(...)`.
  - Added `list_project_tool_calls(...)`.
- `backend/src/api/routes.py`
  - Added `GET /api/projects/{project_id}/tool-calls`.
  - Safe project command executions now create a `tool_calls` row.
  - Approved project command executions now create a `tool_calls` row with `approval_id`.
  - Project tool responses now include `tool_call_id`.
- `backend/tests/test_project_profiles.py`
  - Added assertions for persisted safe tool calls.
  - Added assertions for persisted approved tool calls.
- `frontend/src/types/index.ts`
  - Added `ToolCall`.
  - Added `tool_call_id` to `ProjectToolResult`.
- `frontend/src/api/client.ts`
  - Added `getProjectToolCalls(...)`.
- `frontend/src/pages/Tools.tsx`
  - Loads project tool history when project selection changes.
  - Refreshes history after project test/build runs.
  - Displays recent project tool calls with status, command, cwd, approval id, exit code, and report path.

## Verification

- `python3 -m py_compile backend/src/models.py backend/src/storage/database.py backend/src/api/routes.py backend/tests/test_project_profiles.py` passed.
- `.venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py` passed: 13 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Workbench self-tests are still not persisted as `tool_calls`.
- There is no global timeline yet; history is project-scoped in Tools.
- Full stdout/stderr are persisted but the history panel currently shows summary metadata, not expandable logs.

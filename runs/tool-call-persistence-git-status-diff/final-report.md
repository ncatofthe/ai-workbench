# Tool Call Persistence + Git Status/Diff

## Summary

Implemented read-only tool call logging for project file tools and safe read-only git inspection endpoints.

## Changed Areas

- Added read-only workspace tool helpers for listing files, reading files, and searching code.
- Added tool-call logging around read-only project tool endpoints.
- Added project git status and diff endpoints with fixed subprocess arguments.
- Added frontend API types and client methods for tool calls and git inspection.
- Added backend tests for tool call persistence and git inspection behavior.
- Updated README documentation for the new slice.

## Verification

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py src/models.py src/api/routes.py src/project_tools.py src/utils/workspace_tools.py`
- `cd backend && .venv/bin/pytest tests/test_workspace_tools.py -q`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`

All checks passed.

## Notes

`backend/src/storage/database.py` was not edited in this slice. Existing tool-call storage helpers were reused.

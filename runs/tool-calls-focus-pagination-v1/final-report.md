# Tool Calls Focus & Pagination v1

## Summary

- Improved RunDetail Tool Calls history for workflow focus.
- The panel now shows 25 calls by default and supports latest 25, latest 50, and load-more controls.
- Added filters for tool name, status, and step id.
- Workflow focus now configures Tool Calls filters before trying to focus failed command or rollback-capable apply calls.

## Pagination/load-more behavior

- Default visible limit: 25 matching tool calls.
- `Show latest 25` resets the visible limit to 25.
- `Show latest 50` expands the visible limit to 50.
- `Show more tool calls` increments by 25 when more matching calls exist.

## Filter behavior

- Tool filters include `run-command`, `apply-patch`, `propose-patch`, `rollback-patch`, `analyze-command-result`, read/search/context tools, and discovered extra tool names.
- Status filters include `completed`, `failed`, `pending`, `timed_out`, and `failed command`.
- Step filters are generated from loaded tool calls.

## Focus improvements

- `analyze_result` focuses the latest failed/timed-out `run-command` for the step when available.
- `rollback_manual` focuses the latest rollback-capable `apply-patch` for the step when available.
- If no matching call exists, the panel is still filtered to the relevant tool and step with a clear manual message.

## Safety

- Manual-only actions remain manual-only.
- Direct read-only actions are unchanged.
- No automatic analyze, rollback, test command, proposal creation, patch apply, shell runner, or external provider execution.
- Backend and `database.py` were not changed.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

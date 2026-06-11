# UI Tool Calls + Git Status/Diff Viewer

## Summary

Added compact frontend visibility for read-only tool-call telemetry and project git inspection.

## Changed Areas

- RunDetail now shows a recent Tool Calls panel for the active run.
- Tools now shows project git status, changed files, diff stat, changed paths, and an optional full diff view.
- Project tool history now understands completed/pending/failed read-only tool calls and shows output/error summaries.
- README notes where the dashboard surfaces tool-call and git telemetry.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

## Boundaries

No backend architecture changes, no file editing agents, no `propose_patch`, no `apply_patch`, no shell command runner, and no external providers.

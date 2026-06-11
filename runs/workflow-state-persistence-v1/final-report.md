# Workflow State Persistence v1

## Summary

- Added frontend-only per-run persistence for workflow UI preferences.
- Saved workflow automation mode and active workflow step in localStorage.
- Added safe fallback for missing, unavailable, or corrupted storage.
- Added missing-step validation when the patch workflow plan changes.
- Backend and `database.py` were not changed.

## localStorage key

`ai-workbench:run:{runId}:workflow-ui`

## Saved fields

```json
{
  "workflowAutomationMode": "manual | guided | safe_prep",
  "activeWorkflowStepId": "string | null"
}
```

Only UI preferences are saved. Workflow plans, tool calls, patch drafts, context bundles, and tool outputs are not persisted by this slice.

## Corrupted storage handling

- Invalid JSON is ignored.
- Invalid `workflowAutomationMode` falls back to `guided`.
- Missing/invalid `activeWorkflowStepId` falls back to `null`.
- localStorage read/write failures are ignored so the page remains usable.

## Missing step handling

When a loaded workflow plan no longer contains the saved active step:

- `activeWorkflowStepId` is reset to `null`;
- the cockpit returns to auto mode;
- a friendly RunDetail notice explains that the saved active workflow step no longer exists.

## Safety

- Persistence does not execute any workflow action.
- Direct read-only actions are unchanged.
- Manual-only actions remain manual-only.
- No automatic proposal creation, patch apply, command execution, analysis, rollback, shell runner, or external provider execution.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

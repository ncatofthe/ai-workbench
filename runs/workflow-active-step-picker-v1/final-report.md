# Workflow Active Step Picker v1

## Summary

- Added local active step selection for the patch-workflow cockpit.
- Cockpit can now auto-follow the first actionable step or pin a selected workflow step.
- Added a compact `Active step` selector and `Clear active step` control.
- Backend and `database.py` were not changed.

## Active step picker behavior

- Default mode: auto-select the first workflow step whose `recommended_next_action` is not `done`.
- Pinned mode: show the selected step in the cockpit when it still exists in the workflow plan.
- If the pinned step is done, the cockpit still shows it and explains that clearing the active step returns to the next actionable step.
- If the pinned step disappears from the plan, the cockpit falls back to the next actionable step and shows a warning message.

## Auto mode / pinned mode behavior

- Auto mode label: `Cockpit follows the first actionable step.`
- Pinned mode label: `Cockpit is focused on the selected step.`
- `Clear active step` returns to auto mode.
- The picker is frontend state only and is not stored in localStorage.

## Safety

- Selecting a step does not execute any action.
- Direct read-only actions are unchanged:
  - `auto_gather_context`
  - `build_context_bundle`
  - `create_patch_draft`
- Manual-only actions remain manual-only:
  - `review_patch`
  - `create_proposal`
  - `apply_patch_manual`
  - `run_tests_manual`
  - `analyze_result`
  - `rollback_manual`
- No automatic proposal creation, patch apply, command execution, analysis, rollback, shell runner, or external provider execution.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

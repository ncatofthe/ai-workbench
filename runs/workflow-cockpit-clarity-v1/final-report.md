# Workflow Cockpit Clarity v1

## Summary

- Made the `patch-workflow` tab read as the primary operator cockpit.
- Added a compact current actionable step card at the top of the patch workflow.
- Added explicit action mode, destination, safety, and instruction labels.
- Added a short manual flow help block to Step Patch Tools.

## Cockpit header behavior

- Selects the first step whose `recommended_next_action` is not `done`.
- Shows step title or summary, short step id, status, agent, recommended action, risk, mode, destination, and one-line next instruction.
- Shows a completed state when no pending recommended action remains.

## Action labels added

- Read-only direct actions: `auto_gather_context`, `build_context_bundle`.
- Draft-only action: `create_patch_draft`.
- Manual form actions: `review_patch`, `create_proposal`, `propose_patch`.
- Confirm-required actions: `apply_patch`, `apply_patch_manual`, `rollback_patch`, `rollback_manual`.
- Manual command/analysis actions: `run_tests_manual`, `run_tests`, `run_command`, `analyze_result`.

## Inline help added

Step Patch Tools now shows the recommended manual flow:

1. Use a draft or fill `file_path`, `old_text`, and `new_text`.
2. Click Review Patch.
3. If review is OK, Preview/Create Proposal.
4. Apply only with manual confirmation.

## Safety

- Manual-only actions remain manual-only.
- Direct read-only actions are unchanged.
- No automatic proposal creation, patch apply, test command, analysis, rollback, shell runner, or external provider execution.
- Backend and `database.py` were not changed.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

# Workflow Action Launcher v1

## Summary

- Added a RunDetail patch-workflow action launcher for each recommended next action.
- Wired direct execution only for read-only safe actions:
  - `auto_gather_context`
  - `build_context_bundle`
  - `create_patch_draft`
- Kept patch proposal, apply, test command, analysis, and rollback actions manual-only.
- Updated README with the launcher behavior and safety constraints.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

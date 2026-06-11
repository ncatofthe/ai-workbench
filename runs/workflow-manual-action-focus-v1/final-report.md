# Workflow Manual Action Focus v1

## Summary

- Added manual-action focus routing in RunDetail.
- Manual patch workflow actions now switch to the existing Timeline UI, open the relevant section, scroll to it, and briefly highlight it.
- Direct read-only launcher actions remain unchanged.
- No backend changes, no automatic patch apply, no automatic command execution, and no external providers.

## Focus mapping

- `review_patch` -> step patch form / Review Patch controls.
- `create_proposal` / `propose_patch` -> step patch form.
- `apply_patch_manual` / `apply_patch` -> step patch form and manual apply controls.
- `run_tests_manual` / `run_tests` / `run_command` -> Guided Fix Workflow.
- `analyze_result` -> Guided Fix Workflow with manual analysis hint.
- `rollback_manual` / `rollback_patch` -> Tool Calls history.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

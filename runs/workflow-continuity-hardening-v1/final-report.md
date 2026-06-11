# Workflow Continuity Hardening v1

## Summary

- Hardened RunDetail workflow continuity without backend changes.
- `Use in Patch Form` now keeps the draft prefill behavior and immediately focuses the Timeline patch form.
- `analyze_result` now prefers a matching failed `run-command` ToolCall for the step.
- `rollback_manual` now prefers a matching rollback-capable `apply-patch` ToolCall for the step.
- Empty review and missing-anchor cases now show clearer operator guidance.

## Continuity blockers fixed

- Draft candidates no longer leave the operator stranded in `patch-workflow`.
- Persisted failed commands can be focused from `analyze_result` when visible.
- Rollback points to a specific rollback-capable apply call when visible.
- `review_patch` now explains that `file_path`, `old_text`, and `new_text` are required before review.
- Parent/orchestrator step focus failures now explain that the step has no patch/test UI anchor.

## Safety

- Manual-only actions remain manual-only.
- Direct read-only actions remain unchanged.
- No auto-apply, no auto command execution, no automatic rollback, no external providers.
- Backend and `database.py` were not changed.

## Verification

- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
- `bash scripts/run_tests.sh`

All checks passed.

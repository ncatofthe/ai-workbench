# Action Log

## Commands

- `sed -n '1,130p' frontend/src/pages/RunDetail.tsx`
- `sed -n '220,330p' frontend/src/pages/RunDetail.tsx`
- `sed -n '650,775p' frontend/src/pages/RunDetail.tsx`
- `sed -n '1160,1192p' backend/src/models.py`
- `sed -n '7036,7128p' backend/src/api/routes.py`
- `python3 -m py_compile backend/src/models.py backend/src/api/routes.py backend/tests/test_execute_next_step.py`
- `.venv/bin/python -m pytest -q tests/test_execute_next_step.py`
- `npx tsc --noEmit`
- `bash scripts/run_tests.sh`
- `npm run build`
- `git diff --check`

## File Changes

- Added a Run Detail mode selector for `Run next step`.
- Modes: `mock`, `dry_run`, and `provider`.
- `provider` mode sends `allow_provider_call=true` to the backend shortcut.
- Added backend coverage for `dry_run` keeping the step pending.

## Safety Notes

- Default remains `mock`.
- `dry_run` plans and keeps the step pending.
- `provider` still goes through the existing Agent Execution Harness and does not mutate files, run commands, apply patches, or bypass approvals.


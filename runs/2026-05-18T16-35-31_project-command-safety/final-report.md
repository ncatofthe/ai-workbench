# Project Command Safety Fix Report

## Summary

Fixed project-scoped command execution so only commands explicitly listed in `project.safe_commands` may execute. Blocked commands, global dangerous patterns, empty commands, and unlisted commands do not execute.

## Changed Files

- `backend/src/api/routes.py`
- `backend/tests/test_project_profiles.py`

## Behavior

- Empty command: HTTP 400.
- Project blocked command: returns `approval_required`.
- Global dangerous command: returns `approval_required`.
- Non-dangerous unlisted command: returns `approval_required`.
- Exact safe command: executes with `shlex.split`, `shell=False`, and `cwd=project.path`.

## Verification

- `python3 -m py_compile backend/src/api/routes.py backend/tests/test_project_profiles.py`: passed.
- `cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py`: passed, 7 tests.
- `bash scripts/run_tests.sh`: passed.

## Notes

- No frontend files were modified.
- No package installs, git push, git rebase, sudo, or destructive commands were run.
- Project tool endpoints still return `approval_required` responses rather than creating persistent approval rows.


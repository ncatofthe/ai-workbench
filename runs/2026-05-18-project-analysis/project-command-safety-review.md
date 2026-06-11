# Project Command Safety Review

Date: 2026-05-18
Scope: review of backend command safety fix

## Verification

Commands run:

- `python3 -m py_compile backend/src/api/routes.py backend/tests/test_project_profiles.py`
- `cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py`
- `cd frontend && npx tsc --noEmit`
- `bash scripts/run_tests.sh`

Results:

- Python compile: passed.
- Backend focused pytest: 7 passed.
- Direct frontend TypeScript check: passed.
- Repository test script: passed.

## Review Result

The command safety gap is fixed.

Project-scoped test/build execution now follows the intended Phase 1 policy:

- empty command returns HTTP 400;
- project blocked command returns `approval_required`;
- global dangerous command returns `approval_required`;
- non-dangerous command not listed in `safe_commands` returns `approval_required`;
- exact safe command executes with `shlex.split`, `shell=False`, and `cwd=project.path`.

## Remaining Caveat

`scripts/run_tests.sh` still masks frontend TypeScript failure with `npx tsc --noEmit || true`. Direct TypeScript verification passed during this review, but the script should eventually stop masking frontend failures.

## Decision

Backend Phase 1 is ready for the frontend Project Profiles implementation step.

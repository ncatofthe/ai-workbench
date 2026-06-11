# Backend Phase 1 Review

Date: 2026-05-18
Scope: review of backend-only Project Profiles implementation

## Verification

Commands run:

- `python3 -m py_compile backend/src/models.py backend/src/storage/database.py backend/src/api/routes.py backend/src/orchestrator/engine.py backend/src/approvals/safety.py backend/tests/test_project_profiles.py`
- `cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py`
- `bash scripts/run_tests.sh`
- `cd frontend && npx tsc --noEmit`

Results:

- Python compile: passed.
- Backend focused pytest: 5 passed.
- Repository test script: passed.
- Direct frontend TypeScript check: passed.

## Review Result

The backend implementation is mostly aligned with the Project Profiles blueprint:

- Project profile fields were added.
- SQLite startup migrations were added without attempting foreign-key ALTER.
- Project list fields are JSON encoded/decoded.
- Project APIs were added.
- Runs now store project context.
- Orchestrator artifacts now include project metadata.
- Project-scoped workspace/test/build endpoints were added.
- Dangerous commands return `approval_required`.

## Blocking Issue Before Frontend Work

`safe_commands` is currently stored but not enforced.

In `backend/src/api/routes.py`, `_run_project_command()` checks `blocked_commands` and global dangerous patterns, then executes the command. It does not require the configured `test_command` or `build_command` to match `project.safe_commands`.

Expected Phase 1 policy:

- blocked command: never execute;
- dangerous command: approval required;
- command not explicitly listed as safe: approval required;
- command listed as safe: may execute.

Why this matters:

A project profile could contain a non-danger-pattern command that still modifies project files, and it would execute immediately. That is too permissive for the platform's safety model.

## Secondary Issue

`scripts/run_tests.sh` now fails correctly for backend pytest, but frontend TypeScript is still masked by `npx tsc --noEmit || true`. Direct `npx tsc --noEmit` passed during this review, but the script itself can still hide future frontend failures.

## Recommendation

Before handing the work to a frontend agent, run one small backend fix task:

- enforce `safe_commands` in project tool execution;
- add a test proving an unlisted non-dangerous command returns `approval_required` and does not execute;
- optionally remove `|| true` from frontend TypeScript in `scripts/run_tests.sh` if frontend dependencies are expected to be present in local dev.

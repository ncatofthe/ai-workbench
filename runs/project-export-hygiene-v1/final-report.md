# Project Export Hygiene v1

## Summary

Added a safe project export script for creating clean AI-agent archives without heavy runtime/generated/sensitive paths.

Also added a short current-state file to reduce future prompt/context size for agents.

Verified export archive:

- `exports/ai-workbench-agent-export-20260521-110841.zip`
- size: `332K`
- total entries: `141`

## Script path

- `scripts/export_for_agent.sh`

## Excluded paths

The export script excludes:

- `.git/`
- `.DS_Store`
- `__MACOSX/`
- `node_modules/`
- `frontend/node_modules/`
- `frontend/dist/`
- `backend/.venv/`
- `backend/.venv.backup/`
- `backend/.venv.backup-*`
- `.venv/`
- `dist/`
- `build/`
- `coverage/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `data/*.db`
- `backend/data/*.db`
- `workbench.db`
- `backups/`
- `runs/`
- nested `runs/`
- `exports/`
- `*.pyc`
- `*.pyo`
- `*.log`
- `.env`
- `backend/.env`
- `frontend/.env`

It keeps source files, docs, tests, scripts, package files, config files, and `.env.example` files.

## How to run

From any directory:

```bash
cd /Users/hatss/Инструменты/ai-workbench
bash scripts/export_for_agent.sh
```

The script creates:

```text
exports/ai-workbench-agent-export-YYYYMMDD-HHMMSS.zip
```

It prints the archive path and size.

## Safety guarantees

The script:

- uses `set -euo pipefail`;
- resolves the repository root from the script location;
- creates `exports/` if missing;
- does not delete files;
- does not modify source files;
- requires only standard shell tools plus `zip`;
- prints a clear error if `zip` is unavailable;
- excludes heavy/runtime/generated/sensitive paths.

## Source changes

- Added `scripts/export_for_agent.sh`
- Added `AI_WORKBENCH_CURRENT_STATE.md`
- Added `runs/project-export-hygiene-v1/final-report.md`

No backend runtime code was changed.
No frontend runtime code was changed.
`database.py` was not edited.
`routes.py` was not edited.

## Checks

Export:

- `bash scripts/export_for_agent.sh` passed.
- Archive created: `exports/ai-workbench-agent-export-20260521-110841.zip`.
- Archive verification found no forbidden matches for:
  - `node_modules`
  - `.venv`
  - `dist`
  - `data/workbench.db`
  - `backend/data/workbench.db`
  - `backups`
  - `runs`
  - `.git`
  - `.env`

Runtime checks:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py` passed.
- `cd backend && .venv/bin/pytest -q` passed:
  - `379 passed, 19 subtests passed`
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed.
- `bash scripts/run_tests.sh` passed.

## Recommended next slice

Recommended next slice: `Project Source of Truth Contract v1`.

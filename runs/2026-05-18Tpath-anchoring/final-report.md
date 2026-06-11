# Path Anchoring Report

Date: 2026-05-18
Scope: make runtime paths stable regardless of backend launch directory

## Summary

Fixed the main path anchoring problem.

Before this change, DB/config/agent/run paths could depend on whether the backend was launched from the repository root or from `backend/`. That split state between locations like:

- `data/workbench.db`
- `backend/data/workbench.db`
- `runs/...`
- `backend/runs/...`

Now shared runtime paths are anchored to the AI Workbench repository root.

## Changed Files

- `backend/src/utils/paths.py`
- `backend/src/utils/config.py`
- `backend/src/storage/database.py`
- `backend/src/agents/registry.py`
- `backend/src/api/routes.py`
- `backend/src/orchestrator/engine.py`
- `backend/tests/test_path_anchoring.py`

## What Changed

### Shared Path Helper

Added `backend/src/utils/paths.py` with:

- `PROJECT_ROOT`
- `repo_path(...)`
- `resolve_runtime_path(...)`

Relative runtime paths now resolve under the repository root.

### Config

`config.yaml` now resolves through the shared path helper.

- Default: repo-root `config.yaml`
- `WORKBENCH_CONFIG` is respected
- Relative custom config paths are repo-root relative
- Absolute custom config paths remain absolute

### Database

`WORKBENCH_DB` is still respected.

Default DB now resolves to:

```text
/Users/hatss/Инструменты/ai-workbench/data/workbench.db
```

instead of depending on cwd.

### Agents

Agent instruction files now load from the repository root even if the backend process is launched from another directory.

### Run Directories

New run dirs remain stored as repo-relative strings like `runs/<timestamp>_<id>`, but the orchestrator resolves them against the repository root before writing artifacts.

## Tests Added

Added `backend/tests/test_path_anchoring.py`.

Coverage:

- default DB/config paths are repo-root anchored;
- relative runtime paths resolve under repo root;
- agent instructions load from a non-repo cwd;
- created run dirs remain repo-relative and resolve under repo `runs/` even when cwd changes.

## Verification

Commands:

```bash
python3 -m py_compile backend/src/utils/paths.py backend/src/utils/config.py backend/src/storage/database.py backend/src/agents/registry.py backend/src/api/routes.py backend/src/orchestrator/engine.py backend/tests/test_path_anchoring.py
cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py
bash scripts/run_tests.sh
cd frontend && npm run build
```

Results:

- Python compile: passed.
- Focused backend tests: 11 passed.
- Full test script: passed.
- Frontend production build: passed.

Direct backend-cwd check:

```text
/Users/hatss/Инструменты/ai-workbench/data/workbench.db
/Users/hatss/Инструменты/ai-workbench/config.yaml
```

## Remaining Work

- Existing stray runtime state under `backend/data/` and `backend/runs/` was not deleted.
- Project tool approval-required responses still are not persisted as `ApprovalRequest` rows.
- Stop still does not cancel running background tasks.
- Runs still have flat logs/artifacts rather than a step timeline.

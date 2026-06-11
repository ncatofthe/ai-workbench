# Agent Registry + Dynamic Team Assignment v2

**Date:** 2026-05-19
**Scope:** Phase 1 / Phase 2 foundation

## Analysis

- Current backend already had project profiles, run steps, approvals, project tools, cancellation, and staged planning/execution.
- Previous registry implementation existed but used some legacy agent ids (`backend`, `frontend`, `qa`, `docs`, `security`) and did not fully inspect project files.
- Missing pieces for this slice were exact roadmap agent ids, file-based stack detection, selector metadata, assignment patching, and stronger tests.

## Implemented

- Updated built-in Agent Registry to include the roadmap ids:
  - `orchestrator`
  - `product-manager`
  - `business-analyst`
  - `architect`
  - `api-designer`
  - `frontend-developer`
  - `backend-developer`
  - `fullstack-developer`
  - `react-specialist`
  - `typescript-pro`
  - `fastapi-developer`
  - `node-specialist`
  - `php-pro`
  - `sql-pro`
  - `postgres-pro`
  - `qa-expert`
  - `test-automator`
  - `code-reviewer`
  - `security-auditor`
  - `devops-engineer`
  - `technical-writer`
  - `error-detective`
  - `git-workflow-manager`
- Added `mobile-developer` as an extra template because mobile selection is required by tests and product direction.
- Added legacy aliases for old ids so older timeline/output references remain compatible.
- Added local project signal detection for:
  - `package.json`
  - `pyproject.toml`
  - `requirements.txt`
  - `composer.json`
  - Docker / compose files
  - frontend/backend/mobile/test/doc folders
  - TypeScript/Vite config
  - README/config context
  - SQLite/database files
- Selector now returns:
  - selected agents
  - reasons
  - confidence
  - team size
  - recommended execution mode
  - detected stack
  - raw signals
- Added persistence update support for run agent assignments.
- Added API endpoint:
  - `PATCH /api/runs/{run_id}/agents/{agent_id}`
- Updated frontend client and RunDetail to consume the new selection response.
- Updated README endpoint list and MVP limitations.

## Safety

- No patch-based file editing was implemented.
- No parallel agents were launched.
- No Codex/Claude provider was enabled.
- Selector reads only small metadata files inside the selected project path.
- Agent permissions remain metadata; selecting an agent does not grant execution power.

## Verification

- Python syntax check passed for changed backend files.
- `cd backend && .venv/bin/python -m pytest -q tests/test_agent_registry.py` passed: 7 passed.
- `bash scripts/run_tests.sh` passed: 46 passed and frontend TypeScript check passed.
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed.

## Remaining Risks

- Selector is deterministic and heuristic-based; it is intentionally conservative and will need iterative tuning.
- Stack detection reads only shallow root-level metadata for now.
- Model routing is still profile metadata, not a full scheduler.
- Assigned agents do not yet own executable task graph nodes.
- Patch-based editing and test/fix loop remain future phases.

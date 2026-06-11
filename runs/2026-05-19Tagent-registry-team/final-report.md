# Agent Registry + Run Team Assignment Report

**Date:** 2026-05-19
**Mode:** local development
**Scope:** continue AI Workbench development after repository analysis

## Repository Analysis

- Existing baseline was already beyond MVP: project profiles, path anchoring, approvals, project tools, run steps, cancellation, regenerated plans, staged execution, and tool-call history were present.
- `bash scripts/run_tests.sh` passed before new changes: 39 backend tests passed and frontend TypeScript check passed.
- Current roadmap documents identify `Agent Registry + Agent Selector + Assigned Team in RunDetail` as the next strategic slice.

## Implemented

- Expanded backend agent templates into a structured local-first registry.
- Added conservative selector logic that chooses a small run team from prompt and project profile metadata.
- Added SQLite persistence for run agent assignments.
- Added backend endpoints:
  - `GET /api/agents/registry`
  - `GET /api/runs/{run_id}/agents`
  - `POST /api/runs/{run_id}/agents/select`
- Updated run creation to persist the selected team and pass it into the orchestrator context.
- Added selected team details to `input.md`, planning context, and `final-report.md`.
- Updated frontend:
  - Agents page now shows the structured Agent Library.
  - RunDetail now has an Assigned Team tab and re-select action.
- Added focused backend tests for registry uniqueness, selector behavior, run assignment persistence, and selection endpoint.

## Safety Notes

- Ollama remains the default provider.
- Codex and Claude were not enabled or called.
- Agent selection does not grant autonomous file editing or shell execution.
- File-editing and command-running powers remain represented as template metadata only.

## Verification

- `backend/.venv/bin/python -m py_compile backend/src/models.py backend/src/agents/registry.py backend/src/storage/database.py backend/src/api/routes.py backend/src/orchestrator/engine.py backend/tests/test_agent_registry.py` passed.
- `cd backend && .venv/bin/python -m pytest -q tests/test_agent_registry.py` passed: 4 passed.
- `bash scripts/run_tests.sh` passed: 43 backend tests passed and frontend TypeScript check passed.
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed.
- Browser verification passed:
  - `http://localhost:5173/agents` rendered Agent Library.
  - `http://localhost:5173/runs/ee4c5ff864b0` rendered Assigned Team with selected agents.

## Follow-Up

- Add project stack detection from files such as `package.json`, `pyproject.toml`, `composer.json`, Docker files, and README.
- Add model registry/router after team assignment is stable.
- Later phases should add patch-based file editing with strict path validation and approval gates.

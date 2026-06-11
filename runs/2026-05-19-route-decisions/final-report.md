# Persisted Model Route Decisions Report

**Date:** 2026-05-19

## Summary

Implemented persisted model route decisions and route previews for assigned agents. AI Workbench can now compute, save, and display route metadata for a run:

```text
agent -> task_type -> model_profile -> selected_model -> selected_provider -> fallback -> reason -> warnings
```

No patch-based file editing, autonomous file modification, parallel runtime agents, or real Claude/Codex execution was added.

## Backend Changes

- Added `ModelRouteDecision` and response schemas.
- Added SQLite table `model_route_decisions` with safe initialization.
- Added database helpers:
  - `create_model_route_decision`
  - `get_model_route_decision`
  - `get_model_route_decisions_for_run`
  - `upsert_model_route_decision`
  - `delete_model_route_decisions_for_run`
- Added task-type inference for agent route decisions.
- Added route decision conversion helpers in `model_router.py`.
- Added run model route endpoints:
  - `GET /api/runs/{run_id}/model-routes`
  - `POST /api/runs/{run_id}/model-routes/preview`
  - `POST /api/runs/{run_id}/model-routes/persist`
- Added a non-blocking Orchestrator route preview step for runs with assigned agents.
- Route preview writes `model-routes.md` and includes route metadata in the final report when available.

## Frontend Changes

- Added TypeScript types for persisted route decisions and preview/persist responses.
- Added API client methods for run model route endpoints.
- Updated RunDetail Assigned Team with:
  - model routing status;
  - preview button;
  - persist button;
  - selected model/provider;
  - task type;
  - fallback;
  - warnings and route reason.

## Tests Added

- Route decision create/read.
- Preview does not persist.
- Persist saves decisions.
- Repeated persist updates instead of duplicating.
- Local provider mode does not select external providers.
- Task-type mapping for coding/security/docs agents.
- Empty assigned team returns a clear empty response.
- Orchestrator route preview failure does not break run execution.

## Verification

- Python syntax check passed for changed backend files.
- `cd backend && .venv/bin/python -m pytest -q tests/test_model_route_decisions.py tests/test_model_router.py` passed: 19 tests.
- `cd backend && .venv/bin/python -m pytest -q` passed: 65 tests.
- `bash scripts/run_tests.sh` passed: backend syntax, backend pytest, frontend TypeScript check.
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed.

## Remaining Risks

- Route decisions are persisted per assigned agent, not yet per generated staged step.
- The current staged-step execution still uses the existing Ollama model argument instead of consuming persisted route decisions.
- Project privacy is still treated conservatively as private unless future project settings add a dedicated privacy field.
- External providers remain metadata-only and disabled unless explicitly configured; no real external calls are made.

## Next Step

Persist route decisions for staged steps and then let the execution pipeline read those decisions when choosing which local Ollama model to use for each step.

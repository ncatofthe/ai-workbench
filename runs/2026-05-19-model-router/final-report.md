# Model Registry / Provider Router Report

**Date:** 2026-05-19

## Summary

Implemented the Model Registry + Provider Router slice without enabling external execution. AI Workbench can now describe available models, expose routing profiles, show provider status, and preview model/provider choices for agent steps.

## Backend Changes

- Added model/provider routing schemas in `backend/src/models.py`.
- Added `backend/src/model_router.py` with:
  - built-in model registry;
  - model profiles;
  - provider metadata;
  - provider-mode rules for `local`, `hybrid`, and `cloud`;
  - privacy-aware external provider blocking;
  - simple hardware/memory-tier fallback logic.
- Added model/provider API endpoints in `backend/src/api/routes.py`.
- Added `provider_mode: local` to config handling and `config.yaml`.
- Updated selected agent model-profile mappings in `backend/src/agents/registry.py`.
- Added `backend/tests/test_model_router.py`.
- Added `src/model_router.py` syntax check to `scripts/run_tests.sh`.

## Frontend Changes

- Added model/provider TypeScript types and API client methods.
- Updated Agents page to show model profile details and recommended models.
- Updated Settings page with provider mode, provider status, and model registry visibility.
- Updated Run Detail assigned team view to show model profile and recommended model per agent.

## Added Endpoints

- `GET /api/models/registry`
- `GET /api/models/profiles`
- `POST /api/models/route`
- `GET /api/providers`
- `GET /api/providers/status`
- `PATCH /api/settings/provider-mode`

## Verification

- `backend/.venv/bin/python -m py_compile backend/src/models.py backend/src/model_router.py backend/src/agents/registry.py backend/src/api/routes.py backend/src/utils/config.py backend/tests/test_model_router.py` passed.
- `cd backend && .venv/bin/python -m pytest -q tests/test_model_router.py` passed: 11 tests.
- `cd backend && .venv/bin/python -m pytest -q` passed: 57 tests.
- `bash scripts/run_tests.sh` passed: backend syntax, pytest 57 tests, frontend TypeScript check.
- `cd frontend && npx tsc --noEmit` passed.
- `cd frontend && npm run build` passed.

## Limitations

- Router only selects and explains model/provider choices; it does not execute external providers.
- Provider status for Codex/Claude only checks CLI availability and config enabled flags.
- Run assignments do not yet persist a concrete route decision per step; the UI shows profile-based recommendations.
- No patch-based file editing, test/fix loop, or parallel agent runtime was added in this slice.

## Next Step

Persist route decisions per run step or assignment, then connect the orchestrator planning stages to route previews before any autonomous execution is introduced.

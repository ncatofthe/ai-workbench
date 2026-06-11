# AI Workbench — Current State

## Stable baseline

- Backend pytest: `379 passed, 19 subtests passed`
- Frontend TypeScript/build: passed
- `scripts/run_tests.sh`: passed

## Implemented

- Project intake questions, brief draft, and plan preview.
- Existing project onboarding checklist.
- Workflow policy and Safe Prep boundaries.
- Approval request, storage, and API contracts.
- Patch workflow with proposal/review/manual apply/manual rollback.
- Safe Prep context gathering, context bundle, and patch draft.
- Safe read tools and audited tool calls.

## Not implemented

- Autonomous mode.
- Approval storage and approval endpoints.
- Real external provider execution.
- Auto apply/tests/analyze/rollback.
- Full autonomous delivery/test/fix loop.

## Handle with care

- Do not edit `backend/src/storage/database.py` unless explicitly required.
- Avoid large `backend/src/api/routes.py` rewrites.
- Avoid touching `backend/src/orchestrator/engine.py` casually.
- Do not enable provider execution or shell execution outside existing safe boundaries.

## Planned slices

- Project Source of Truth Contract v1.
- Requirement Coverage Matrix v1.
- Existing Project Safe Scan v1.
- Confirmed Plan to Run Preview v1.
- Semi-auto Step Runner Design v1.

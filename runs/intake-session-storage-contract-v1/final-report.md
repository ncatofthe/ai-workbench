# Intake Session Storage Contract v1

## Summary

Added a pure future storage contract for persisted intake sessions without implementing database storage.

This slice defines how an `IntakeSession` can later hold the raw idea, intake answers, brief versions, and plan versions before a user explicitly confirms Project/Run creation.

No runtime behavior, API endpoint, database schema, migration, tool execution, provider execution, or persistence helper was added.

## Contract models

Added `backend/src/orchestrator/intake_session_contract.py` with:

- `IntakeSessionStatus`
  - `draft`
  - `needs_answers`
  - `ready_to_plan`
  - `ready_to_create_run`
  - `archived`
- `IntakeSourceMode`
  - `new_project`
  - `existing_project`
  - `unknown`
- `IntakeVersionKind`
  - `intake_response`
  - `brief_draft`
  - `plan_preview`
- `IntakeSelectionStatus`
  - `unselected`
  - `selected`
  - `superseded`

Added pure Pydantic contract models:

- `IntakeSessionContract`
- `IntakeAnswerContract`
- `IntakeBriefVersionContract`
- `IntakePlanVersionContract`
- `IntakeSessionSnapshot`
- `IntakeContractValidationResult`

Added pure helpers:

- `build_intake_session_snapshot(...)`
- `validate_intake_session_contract(...)`
- `summarize_intake_session_lifecycle(...)`

The contract supports optional `project_id`, optional `run_id`, optional selected brief/plan IDs, and multiple brief/plan versions.

## Lifecycle

Recommended future lifecycle:

1. User enters raw idea in NewTask.
2. Read-only intake analysis, brief draft, and plan preview are generated.
3. A future `IntakeSession` stores the raw idea, answers, draft versions, selected versions, readiness, and source metadata.
4. The session remains separate from Project/Run until explicit user confirmation.
5. A future create-run action may attach selected brief/plan versions to a Project/Run.
6. Superseded versions remain available for history instead of being overwritten.

The lifecycle summary helper explicitly describes Project/Run attachment as a later confirmation step.

## Safety guarantees

Confirmed for this slice:

- no DB implementation;
- no DB migrations;
- no database writes;
- no project creation;
- no run creation;
- no tool_calls;
- no tools execution;
- no file scanning;
- no LLM/provider calls;
- no patch proposal;
- no apply patch;
- no run command;
- no analyze result;
- no rollback;
- no shell runner;
- no autonomous mode.

The contract includes simple guardrails to reject obvious secret-like metadata keys and secret assignment values in answer text. Safe references such as ignore paths containing `.env` are allowed, but secret values are not intended to be stored.

## Why no database.py changes

`backend/src/storage/database.py` was intentionally not edited because this slice is contract-only.

The future storage implementation should be a separate slice that can review schema, migration strategy, database helper boundaries, and compatibility risks deliberately. This keeps the current read-only intake flow stable.

## Source changes

- Added `backend/src/orchestrator/intake_session_contract.py`
- Added `backend/tests/test_intake_session_contract.py`
- Added `runs/intake-session-storage-contract-v1/final-report.md`

## Tests

Passed:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
  - `338 passed, 7 subtests passed`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `bash scripts/run_tests.sh`
  - backend syntax checks passed
  - pytest passed: `338 passed, 7 subtests passed`
  - frontend TypeScript check passed

## Remaining gaps

- No persisted intake session storage yet.
- No DB schema or migration yet.
- No API surface for creating/loading intake sessions yet.
- No frontend save/load session behavior yet.
- No create-run-from-confirmed-session flow yet.
- Orchestrator still does not consume persisted intake sessions.
- Approval request model integration remains separate.
- Existing project onboarding scan is still not implemented.
- No autonomous mode.

## Recommended next slice

Recommended next slice: `Intake Session Storage Foundation v1`.

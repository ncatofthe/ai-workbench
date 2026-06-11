# Intake Run -> Agent Assignment & Step Context Fastlane v1

## Summary

Implemented a read-only agent-prep layer for intake-origin pending development runs.

Created pending runs now have a normalized step-context parser, a run-level `agent-step-context` endpoint, Operator Queue visibility for the first safe agent-prep action, and a RunDetail "Agent Step Context" panel. The feature is display/preparation only: it does not start execution, call providers, create tool calls, create runs, apply patches, or run commands.

## Why This Fastlane Block Exists

The intake pipeline can now produce real pending runs and steps. Before adding controlled autonomous execution, operators need to see whether each step has a canonical agent assignment, bounded requirement/module context, safety gates, and an obvious next safe action.

This slice bridges confirmed run creation to agent readiness without introducing execution.

## Context Parsing Behavior

- Added `DevelopmentRunStepContext` and `normalize_development_run_step_context(...)` in `backend/src/orchestrator/project_intake.py`.
- Parses the existing `AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT` block embedded in `RunStep.input`.
- Falls back safely when the block is missing or malformed.
- Bounds requirement IDs, module IDs, dependencies, safety gates, outputs, and validation steps.
- Defaults `provider_allowed=false`.
- Marks sensitive/risky auth, database, security, provider, deployment, billing/payment work as requiring manual approval.
- Performs no DB access, provider calls, filesystem reads, command execution, or persistence.

## Canonical Agent Assignment Behavior

- Existing canonical mapping is used through `canonical_agent_id_for_role(...)`.
- Backend, frontend, QA, and security roles resolve to registry-backed canonical agents.
- Unknown roles fall back to a safe existing agent.
- Bridge-created step context preserves the original `agent_role` while exposing a canonical agent ID for runtime preparation.

## Endpoint Behavior

Added:

- `GET /api/runs/{run_id}/agent-step-context`

The endpoint:

- Reads the existing run and steps only.
- Returns one bounded context item per step.
- Computes total, ready, and blocked counts.
- Recommends the first pending ready step.
- Blocks readiness when `provider_allowed=true`.
- Warns when requirement links, module links, validation steps, or safety gates are missing.
- Creates no records and starts no work.

## Operator Queue Integration

Operator Queue can now surface `prepare_agent_step` for intake-origin pending steps that have no proposal or guard records yet.

The queue item:

- Points to `agent_step_context`.
- Is read-only guidance.
- Does not auto-execute.
- Does not create tool calls.
- Does not change step status.

## RunDetail UI Behavior

Updated RunDetail with a compact `Agent Context` tab and "Agent Step Context" panel.

The panel displays:

- total / ready / blocked counts
- next recommended action
- canonical agent ID and original role
- requirement IDs
- module IDs
- dependencies
- safety gates
- manual approval state
- provider-disabled state
- blockers and warnings
- safety notes

The section explicitly says it is read-only and does not start execution, call providers, create tool calls, apply patches, or run commands.

## Safety Boundaries

Verified:

- No automatic `execute_run`.
- No `asyncio.create_task` added.
- No provider calls.
- No network calls.
- No automatic tool call creation.
- No project/run/run-step creation from the new read-only endpoint.
- No patch proposal creation.
- No apply patch.
- No command execution.
- No runtime file reads.
- No DB schema changes.
- No migrations.
- No safety gate weakening.

## Tests Added

Added `backend/tests/test_intake_run_agent_assignment_step_context.py`.

Coverage:

- context block parsing
- missing/malformed context fallback
- provider default safety
- bounded requirement/module/safety fields
- canonical agent mapping
- endpoint summaries and readiness counts
- provider-enabled blocker
- missing context warnings
- no tool calls / providers / execution / endpoint DB writes
- bridge-created step compatibility
- Operator Queue `prepare_agent_step`
- RunDetail static UI labels and read-only wording
- static safety scans
- frontend type/client compatibility anchors

Result: `50 passed`.

## Files Changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_intake_run_agent_assignment_step_context.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/intake-run-agent-assignment-step-context-fastlane-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice.
- `backend/src/orchestrator/engine.py`: not touched by this slice.
- `backend/src/providers/*`: not touched by this slice.

## Exact Check Results

Backend syntax:

- `python -m py_compile src/orchestrator/project_intake.py src/api/routes.py src/models.py`: passed.
- `python -m py_compile tests/test_intake_run_agent_assignment_step_context.py`: passed.

Backend tests:

- `pytest -q tests/test_intake_run_agent_assignment_step_context.py`: `50 passed`.
- Targeted compatibility bundle:
  - `tests/test_confirmed_development_run_bridge_fastlane.py`
  - `tests/test_model_router_agent_alignment.py`
  - `tests/test_agent_execution_harness.py`
  - `tests/test_confirmed_development_run_creation_preview_wiring.py`
  - `tests/test_intake_confirmed_development_run_preview.py`
  - `tests/test_project_context_cockpit.py`
  - `tests/test_semi_auto_operator_queue.py`
  - result: `290 passed`.
- Full backend pytest: `2001 passed, 38 subtests passed`.

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run test:e2e:smoke`: `2 passed`.

Root:

- `bash scripts/run_tests.sh`: passed.
  - backend pytest: `2001 passed, 38 subtests passed`
  - frontend TypeScript check: passed

## P0/P1/P2/P3 Issues

- P0: none found.
- P1: none found.
- P2: none introduced. Existing limitation remains: agent prep is read-only and does not yet produce patch drafts.
- P3: none noted in this slice.

## Known Limitations

- No auto execution added.
- No patch draft generation added.
- No provider call added.
- No full repo-aware intake yet.
- No autonomous patch/test/fix loop yet.
- RunDetail section is read-only.
- Agent readiness is based on bounded intake context, not repository content analysis.

## Recommended Next Slice

Recommended next slice: **Step -> Agent Patch Draft Fastlane v1**.

That should use the now-visible agent-ready step context to prepare bounded, manual patch draft inputs without auto-applying or starting execution.

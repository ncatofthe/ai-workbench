# Guard/Proposal Module Awareness Regression Pass

## Summary

Verified Guard/Proposal Module Awareness v1 as a regression/stability pass. No P0/P1 issues were found, and no source-code changes were made in this pass.

The feature remains bounded and advisory: `propose-patch` returns/stores `module_awareness` after existing guard validation succeeds, while guard validation, no-guard override, and apply `confirm=true` behavior remain unchanged.

## Response Model Validation

- `ModuleAwarenessResult` has safe defaults for all list fields.
- `ProposePatchResponse.module_awareness` is optional and backward-compatible.
- Existing proposal response behavior works when no active module map exists.
- Frontend TypeScript shape matches backend response shape.
- Proposal preview UI uses optional access and safely handles absent `module_awareness`.

## Helper Behavior Validation

Verified `build_patch_proposal_module_awareness(...)`:

- returns `has_active_module_map=false` when no active map exists.
- derives `touched_modules` from proposed file paths.
- derives `expected_modules` from requirement IDs first.
- uses keyword fallback only when requirement IDs do not identify expected modules.
- deduplicates and caps modules.
- caps paths/key files, warnings, risks, and test hints.
- returns compact dictionaries, not raw module-map dumps.
- does not read file contents.
- does not write DB records.
- does not create tool calls.
- does not call providers.
- does not mutate run/step state.

Static helper scan found no forbidden runtime hooks.

## Proposal Endpoint Validation

- `propose-patch` computes `module_awareness` only after `_validate_propose_patch_guard(...)` succeeds.
- Guard validation failures still occur before proposal tool_call creation.
- Successful proposal still creates the normal `propose-patch` tool_call.
- `module_awareness` is warning/context only.
- Module mismatch does not block proposal creation in v1.
- Risky/sensitive module warnings do not block proposal creation in v1.
- Existing proposal payload and guard metadata remain preserved.
- No auto-apply, auto-test, provider call, or file read was introduced.

## Guard/Apply Compatibility Validation

- `guard_result_id` validation remains unchanged.
- `no_guard_override` remains explicit and does not override selected invalid/blocked guards.
- Step-linked proposal behavior remains unchanged.
- Apply still requires `confirm=true`.
- Apply guard revalidation remains unchanged.
- Apply does not consume module awareness as authorization.
- No guard or approval bypass was introduced.

## Module Warnings Validation

Verified coverage for:

- unknown proposed file warning.
- touched/expected module mismatch warning.
- risky module warning.
- sensitive database/auth-style module warning.
- matching touched/expected modules avoiding false mismatch warning.
- module risks and module test hints included when available.
- bounded output.
- no file-content leakage.

## Frontend Read-Only Validation

- RunDetail Module Awareness block is display-only.
- No new execution buttons were added.
- No auto-run, autosave, scan, provider call, apply, test, or proposal automation was added by the display block.
- Existing proposal preview flow remains manual.
- Existing apply confirmation UI remains unchanged.
- Existing guard validation UI remains unchanged.
- `npx tsc --noEmit` and `npm run build` passed.

## Workflow Compatibility Validation

Verified the requested suites:

- guard proposal module awareness
- guarded patch proposal
- guard result proposal validation
- apply guard revalidation
- module map patch draft context
- agent result patch draft bridge
- module map agent context wiring
- project module map
- agent execution harness
- source-of-truth run creation wiring
- persistent source of truth
- RunDetail UX
- real project dogfooding
- full delivery loop
- dogfooding full cycle
- bounded autonomous loop
- approval-gated automation
- automation runner
- semi-auto operator queue

Full backend pytest passed.

## Runtime Boundary Validation

Confirmed for module awareness helper/flow:

- no `execute_run`
- no `asyncio.create_task`
- no subprocess/shell execution
- no provider calls
- no `create_tool_call` in the awareness helper itself
- no file content reads
- no DB schema mutation
- no migrations
- no approval execution
- no guard bypass
- no auto-proposal beyond the existing explicit `propose-patch` endpoint call
- no auto-apply
- no auto-rollback

## P0/P1/P2/P3 Issues Found

- P0: none.
- P1: none.
- P2: none.
- P3: heuristic matching can produce advisory false positives/negatives; acceptable for warning-only v1.

## Changes Made

No source-code changes were made in this regression pass.

Files created:

- `runs/guard-proposal-module-awareness-regression/final-report.md`

## Exact Checks/Results

- `py_compile`:
  - `src/storage/database.py`: passed
  - `src/models.py`: passed
  - `src/storage/module_map_storage.py`: passed
  - `src/api/routes.py`: passed
  - `tests/test_guard_proposal_module_awareness.py`: passed
- `pytest -q tests/test_guard_proposal_module_awareness.py`: 18 passed
- `pytest -q tests/test_guarded_patch_proposal.py`: 17 passed
- `pytest -q tests/test_guard_result_proposal_validation.py`: 17 passed
- `pytest -q tests/test_apply_guard_revalidation.py`: 11 passed
- `pytest -q tests/test_module_map_patch_draft_context.py`: 26 passed
- `pytest -q tests/test_agent_result_patch_draft_bridge.py`: 36 passed
- `pytest -q tests/test_module_map_agent_context_wiring.py`: 30 passed
- `pytest -q tests/test_project_module_map.py`: 41 passed
- `pytest -q tests/test_agent_execution_harness.py`: 46 passed
- Remaining targeted workflow compatibility suites: passed
- Full backend pytest: 1112 passed, 38 subtests passed
- Frontend `npx tsc --noEmit`: passed
- Frontend `npm run build`: passed
- `bash scripts/run_tests.sh`: passed; backend 1112 passed, 38 subtests passed; frontend TypeScript check passed

## Protected Files

- `backend/src/storage/database.py`: not touched in this pass.
- `backend/src/orchestrator/engine.py`: not touched in this pass.
- Providers/provider clients: not touched in this pass.

Note: the working tree may contain unrelated pre-existing dirty files from earlier slices; this regression pass did not modify source files.

## Known Limitations

- Module mismatch is warning-only in v1.
- Matching is heuristic only.
- No file content analysis.
- No provider/LLM module classification.
- Module map is not yet used as hard guard policy.
- No visual module map editor.

## Recommended Next Slice

Module-aware Guard Policy v1.

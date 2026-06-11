# Module-aware Guard Policy Regression Pass

## Summary

Verified Module-aware Guard Policy v1 as a regression/stability pass. No P0/P1/P2 issues were found, and no source-code changes were made in this pass.

The policy remains classification-only: a `blocked` verdict is visible to the operator but does not add a new hard proposal gate.

## Response Model Validation

- `ModuleAwareGuardPolicyResult` has safe defaults for all list fields.
- `ProposePatchResponse.module_policy` is optional and backward-compatible.
- Proposal responses still work without an active module map.
- Proposal preview can safely render without `module_policy`.
- Frontend TypeScript matches backend response shape.
- Proposal tool_call output remains JSON-serializable.

## Policy Helper Validation

Verified `evaluate_module_aware_guard_policy(...)`:

- returns a neutral `allowed` policy when no active module map exists.
- returns `allowed` for matching touched/expected modules.
- returns `warning` for unknown files and non-sensitive mismatches.
- returns classification-only `blocked` for sensitive auth/database-style mismatch or suspicious unknown paths.
- does not incorrectly block sensitive modules when matching requirement/module context exists.
- includes module risks as reasons.
- includes module test hints as `recommended_tests`.
- caps affected modules, sensitive modules, unknown files, reasons, acknowledgements, and tests.
- does not dump raw JSON.
- does not read file contents.
- does not write DB records.
- does not create tool calls.
- does not call providers.
- does not mutate run/step state.

Static helper scan found no forbidden runtime hooks.

## Proposal Endpoint Validation

- `propose-patch` computes `module_policy` only after `module_awareness` is computed.
- `module_policy` appears in successful proposal responses.
- `module_policy` is stored in successful proposal tool_call output.
- Existing guard validation still runs before proposal tool_call creation.
- Validation failures still create no proposal tool_call.
- Successful proposals still create the normal `propose-patch` tool_call.
- Classification-only `blocked` verdict does not add a new hard gate.
- Module mismatch/risky module policy classification does not block proposal creation in v1.
- Existing `guard_result_id`, `no_guard_override`, and step-linked proposal behavior remain unchanged.
- No auto-apply, auto-test, provider call, or file read was introduced.

## Guard/Apply Compatibility Validation

- Apply still requires `confirm=true`.
- Apply guard revalidation remains unchanged.
- Stale/blocked guard behavior remains unchanged.
- Proposal guard result linking remains unchanged.
- No guard or approval bypass was introduced.
- `apply-patch` does not consume `module_policy` as authorization.
- `module_policy` does not replace existing guard validation.

## Frontend Read-Only Validation

- RunDetail Module Policy block is display-only.
- Verdict, reasons, acknowledgements, and recommended tests render safely.
- No new execution buttons were added.
- Existing proposal, guard, and apply controls remain unchanged.
- No auto-run, autosave, scan, provider call, apply, test, or proposal automation was added.
- `npx tsc --noEmit` and `npm run build` passed.

## Workflow Compatibility Validation

Verified the requested suites:

- module-aware guard policy
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

Confirmed:

- no `execute_run`
- no `asyncio.create_task`
- no subprocess/shell execution
- no provider calls
- no `create_tool_call` in the module policy helper itself
- no file content reads
- no DB schema mutation
- no migrations
- no approval execution
- no guard bypass
- no hard-gate enforcement added by `module_policy`
- no auto-proposal beyond the existing explicit `propose-patch` endpoint
- no auto-apply
- no auto-rollback

## P0/P1/P2/P3 Issues Found

- P0: none.
- P1: none.
- P2: none.
- P3: policy is classification-only and heuristic in v1.

## Changes Made

No source-code changes were made in this regression pass.

Files created:

- `runs/module-aware-guard-policy-regression/final-report.md`

## Exact Checks/Results

- Static policy helper scan: no forbidden runtime hooks found.
- `py_compile`:
  - `src/storage/database.py`: passed
  - `src/models.py`: passed
  - `src/storage/module_map_storage.py`: passed
  - `src/api/routes.py`: passed
  - `tests/test_module_aware_guard_policy.py`: passed
- `pytest -q tests/test_module_aware_guard_policy.py`: 19 passed
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
- Full backend pytest: 1131 passed, 38 subtests passed
- Frontend `npx tsc --noEmit`: passed
- Frontend `npm run build`: passed
- `bash scripts/run_tests.sh`: passed; backend 1131 passed, 38 subtests passed; frontend TypeScript check passed

## Protected Files

- `backend/src/storage/database.py`: not touched in this pass.
- `backend/src/orchestrator/engine.py`: not touched in this pass.
- Providers/provider clients: not touched in this pass.

Note: the working tree may contain unrelated pre-existing dirty files from earlier accepted slices; this regression pass did not modify source files.

## Known Limitations

- Module policy is classification-only in v1.
- Blocked verdict is not enforced as a hard gate.
- Matching is heuristic only.
- No file content analysis.
- No provider/LLM classification.
- No visual module policy editor.
- Module policy does not yet affect apply authorization.

## Recommended Next Slice

Delivery Report Module Awareness v1.

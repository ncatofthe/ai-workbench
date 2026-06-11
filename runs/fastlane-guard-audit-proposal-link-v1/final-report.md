# Fastlane Guard Audit + Proposal Link v1

## Summary

All Parts (A through I) implemented and verified. Backend adds 3 new endpoints (guard result list, get, proposal validation), hardens persist failure, cleans up unused imports. Frontend adds Guard History panel with selection and validation UI. Two new test files (33 tests total). All checks pass.

## Parts completed

| Part | Description | Status |
|------|-------------|--------|
| A | Guard Result List API — `GET /api/runs/{run_id}/guard-results` | Done |
| B | Guard Result Get API — `GET /api/runs/{run_id}/guard-results/{guard_result_id}` | Done |
| C | Persist failure hardening — try/except around `create_guard_result` with 500 error | Done |
| D | Explicit decision tests — covered in test_guard_result_api_wiring.py | Done |
| E | Frontend Guard History panel — collapsible panel in StepPatchSection | Done |
| F | Guard result selection — click to select, visual indicator, stored in local state | Done |
| G | Proposal guard validation endpoint — `POST .../validate-for-proposal` | Done |
| H | Validate selected guard button — wired into Guard History panel | Done |
| I | Import cleanup — removed unused WorkflowGuardDecision/WorkflowGuardDriftRisk | Done |

## New endpoints

### GET /api/runs/{run_id}/guard-results

List persisted guard results for a run. Query params: `step_id`, `include_stale`, `limit`. Returns `{run_id, total, items[]}` where each item is a flattened GuardResultItem.

### GET /api/runs/{run_id}/guard-results/{guard_result_id}

Get a single persisted guard result. Returns 404 if not found or wrong run. Returns flattened GuardResultItem dict.

### POST /api/runs/{run_id}/steps/{step_id}/guard-results/{guard_result_id}/validate-for-proposal

Read-only validation of a persisted guard result against proposed patch payload. Accepts: `proposed_action`, `file_path`, `patch_summary`, `old_text`, `new_text`, `warning_acknowledged`, `no_guard_override`. Returns: `{guard_result_id, valid, decision, is_stale, stale_reasons, blocking_reasons, warnings, requires_warning_acknowledgement, recommended_next_step}`.

## Safety invariants

| Check | Status | Evidence |
|-------|--------|----------|
| No execution in new endpoints | ✓ | No execute_run, asyncio.create_task, subprocess, provider calls |
| No tool_calls created | ✓ | Tests verify tool_calls count unchanged after list/get/validate |
| No state mutation | ✓ | Tests verify run status, step status, guard result unchanged |
| No proposals created | ✓ | No create_tool_call or propose-patch in new endpoints |
| No patches applied | ✓ | No apply logic in new endpoints |
| List endpoint read-only | ✓ | Uses list_guard_results helper, returns dicts only |
| Get endpoint read-only | ✓ | Uses get_guard_result helper, returns dict only |
| Validate endpoint read-only | ✓ | Uses compare + is_usable helpers, returns dict only |
| Persist hardened | ✓ | try/except returns 500 with clear message on failure |

## Frontend changes

### RunDetail.tsx — Guard History panel

Added to StepPatchSection between source-of-truth guard UI and patch proposal guard status:

- Guard History state: `guardHistory`, `guardHistoryLoading`, `guardHistoryOpen`, `selectedGuardResultId`, `guardValidation`, `guardValidationLoading`, `guardValidationError`
- `loadGuardHistory()`: Calls `listRunGuardResults(run_id, { step_id, include_stale: true, limit: 20 })`
- `handleValidateGuard()`: Calls `validateGuardResultForProposal` with selected guard + current form state
- Collapsible panel with Show/Hide toggle and Refresh button
- Each guard result row shows: decision badge, drift risk, stale flag, proposed_action, file_path, created_at, matched requirement IDs
- Click to select/deselect a guard result (visual emerald border)
- Selected guard shows: guard_result_id, "Validate selected guard for proposal" button
- Validation result shows: valid/invalid badge, decision, stale flag, blocking reasons, warnings, warning acknowledgement needed, recommended next step

### Types added (index.ts)

- `GuardResultItem` — 28 fields, flattened from backend response
- `GuardResultListResponse` — `{run_id, total, items[]}`
- `GuardProposalValidationRequest` — 7 optional fields
- `GuardProposalValidationResponse` — 9 fields

### Client methods added (client.ts)

- `listRunGuardResults(runId, params?)` — GET with query string building
- `getRunGuardResult(runId, guardResultId)` — GET single record
- `validateGuardResultForProposal(runId, stepId, guardResultId, data)` — POST validation

## New test files

### backend/tests/test_guard_result_list_get_api.py (15 tests)

- `TestListGuardResults` (8 tests): empty list, returns persisted, filter by step_id, nonexistent step_id, limit, invalid run 404, response shape, no tool_calls
- `TestGetGuardResult` (7 tests): returns persisted, invalid run 404, invalid guard_result_id 404, wrong run 404, shape matches list item, no tool_calls, no run status mutation

### backend/tests/test_guard_result_proposal_validation.py (18 tests)

- `TestValidateEndpoint404s` (5 tests): invalid run, invalid step, invalid guard_result_id, wrong run, wrong step
- `TestValidateResponseShape` (2 tests): all expected fields, correct types
- `TestValidateWithMatchingPayload` (2 tests): matching action, empty body defaults
- `TestValidateSafety` (5 tests): no tool_calls, no run status mutation, no guard result mutation, no new guard_results rows, idempotent results
- `TestValidateWarningAcknowledgement` (2 tests): default false, explicit true
- `TestValidateWithFileAndPatch` (2 tests): full payload with file_path/old_text/new_text

## Files changed

| File | Change |
|------|--------|
| `backend/src/api/routes.py` | Added 3 endpoints, _ValidateGuardForProposalRequest, _guard_result_to_api, persist hardening, import cleanup |
| `backend/src/orchestrator/project_intake.py` | Added persisted/guard_result_id fields to StepSourceOfTruthGuardResponse |
| `frontend/src/types/index.ts` | Added GuardResultItem, GuardResultListResponse, GuardProposalValidationRequest, GuardProposalValidationResponse, updated StepSourceOfTruthGuardResponse |
| `frontend/src/api/client.ts` | Added listRunGuardResults, getRunGuardResult, validateGuardResultForProposal |
| `frontend/src/pages/RunDetail.tsx` | Added Guard History panel, guard result selection, validation UI |
| `backend/tests/test_guard_result_list_get_api.py` | NEW — 15 tests |
| `backend/tests/test_guard_result_proposal_validation.py` | NEW — 18 tests |

## database.py touched

No (in this slice).

## Checks

| Check | Result |
|-------|--------|
| Python syntax (35 source files) | All OK |
| Python syntax (27 test files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |

Real environment expected: all pytest tests pass (existing + 33 new = 560+ total).

## Recommended next slice

**Guard Result Proposal Link v1** — wire `guard_result_id` into propose-patch request, validate guard before creating proposal, link guard result to proposal via `link_guard_result_to_proposal`. This connects the audit trail from guard check → proposal → apply.

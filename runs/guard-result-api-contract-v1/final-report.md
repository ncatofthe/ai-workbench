# Guard Result API Contract v1

## Summary

Added a pure API-facing contract layer for future persisted Source-of-Truth Guard results.

This slice does not implement real endpoints, does not edit `routes.py`, does not edit `database.py`, and does not wire runtime behavior. The contract defines future request/response shapes and validation helpers around stored guard results, proposal validation, and proposal links.

## Contract file path

- `backend/src/orchestrator/guard_result_api_contract.py`

This path was chosen to sit next to `guard_result_storage_contract.py`, because both contracts describe Source-of-Truth Guard behavior and are not runtime route handlers.

## Request models added

- `CreateWorkflowGuardResultRequest`
- `ListWorkflowGuardResultsRequest`
- `LinkGuardResultToProposalRequest`
- `ValidateGuardResultForProposalRequest`
- `MarkGuardResultStaleRequest`

## Response models added

- `WorkflowGuardResultApiResponse`
- `WorkflowGuardResultListResponse`
- `GuardResultProposalValidationResponse`
- `LinkGuardResultToProposalResponse`
- `GuardResultApiError`
- `GuardResultApiValidationResult`

## Validation helpers added

- `build_guard_result_api_error`
- `validate_create_guard_result_request`
- `validate_list_guard_results_request`
- `validate_guard_result_link_request`
- `validate_guard_result_for_proposal`
- `build_guard_result_api_response`
- `build_guard_result_validation_response`
- `build_link_guard_result_to_proposal_response`

## Validation behavior

- Create request requires non-empty `run_id`, `step_id`, and `proposed_action`.
- List request bounds `limit` to `1..200` and requires non-negative `offset`.
- Proposal validation blocks stale guard results.
- Proposal validation blocks blocked guard results.
- Warning guard results require acknowledgement before being usable.
- `no_guard_override` does not override a blocked guard.
- Link request requires both `guard_result_id` and `proposal_tool_call_id`.
- Link response reports stale/usable state at link time.
- Raw `old_text` and `new_text` remain request-only contract fields; future storage conversion must use storage contract hashes.

## Intended future endpoint shapes

Not implemented in this slice:

- `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true`
- `GET /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard-results`
- `GET /api/guard-results/{guard_result_id}`
- `POST /api/guard-results/{guard_result_id}/validate-for-proposal`
- `POST /api/guard-results/{guard_result_id}/link-proposal`
- `POST /api/guard-results/{guard_result_id}/mark-stale`

## Safety guarantees

- No DB schema changes.
- No migrations.
- No `database.py` edits.
- No `routes.py` edits.
- No real endpoints.
- No runtime behavior changes.
- No tool calls.
- No tools/provider execution.
- No patch/proposal/apply/tests/analyze/rollback execution.
- No shell runner.
- No autonomous mode.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.

The API contract module imports only Pydantic/typing and the pure guard result storage contract.

## Tests

Added `backend/tests/test_guard_result_api_contract.py`.

Coverage includes:

- create request required field validation;
- create request serialization;
- list request limit/offset bounds;
- API response wrapping a `WorkflowGuardResultRecord`;
- list response serialization;
- API error serialization;
- stale guard blocks proposal validation;
- expired guard blocks proposal validation;
- blocked guard blocks proposal validation;
- warning guard requires acknowledgement;
- `no_guard_override` does not override blocked guard;
- missing record fails closed;
- proposal link response records stale/usable state;
- blocked guard cannot link as usable;
- link request requires ids;
- module purity checks for no database/routes/provider/tool imports;
- helper determinism.

## Files changed

- `backend/src/orchestrator/guard_result_api_contract.py`
- `backend/tests/test_guard_result_api_contract.py`
- `runs/guard-result-api-contract-v1/final-report.md`

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q tests/test_guard_result_api_contract.py` | Passed | `18 passed, 7 subtests passed`. |
| `cd backend && .venv/bin/pytest -q` | Passed | `479 passed, 38 subtests passed`. |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `479 passed, 38 subtests passed`. |

## database.py / routes.py

- `backend/src/storage/database.py` touched in this slice: no.
- `backend/src/api/routes.py` touched in this slice: no.

The working tree already contains unrelated/pre-existing source diffs from prior accepted slices. They were preserved and not modified.

## Remaining gaps

- No real guard result endpoints exist yet.
- No DB storage exists yet.
- Runtime guard endpoint still returns non-persisted results.
- Patch proposal creation does not accept `guard_result_id` yet.
- Approval requests do not include guard result snapshots yet.

## Recommended next slice

Guard Result API Contract Regression Pass v1.

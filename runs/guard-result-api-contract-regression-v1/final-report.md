# Guard Result API Contract Regression Pass v1

## Summary

Guard Result API Contract v1 is stable as a pure API-facing contract layer. No P0/P1/P2/P3 issues were found during inspection. The contract does not implement endpoints, does not wire runtime behavior, and does not persist guard results.

## Module purity validation

Validated:

- `backend/src/orchestrator/guard_result_api_contract.py` imports only typing/Pydantic and the pure `guard_result_storage_contract` module.
- No imports from `database.py`, `routes.py`, `engine.py`, `project_tools.py`, provider modules, or frontend code.
- No route registration, DB access, tool execution, provider execution, `create_tool_call`, or `execute_run`.

## Request validation

Validated:

- `CreateWorkflowGuardResultRequest` carries required `run_id`, `step_id`, and `proposed_action`; validation rejects blank values.
- `ListWorkflowGuardResultsRequest` enforces bounded `limit` and non-negative `offset`.
- `LinkGuardResultToProposalRequest` requires `guard_result_id` and `proposal_tool_call_id`.
- `ValidateGuardResultForProposalRequest` requires `guard_result_id` and `proposed_action`.
- `MarkGuardResultStaleRequest` requires `guard_result_id` and a stale reason.

## Response validation

Validated:

- `WorkflowGuardResultApiResponse` safely wraps `WorkflowGuardResultRecord` and exposes proposal usability, stale reasons, and warnings.
- `WorkflowGuardResultListResponse` serializes `items`, `total`, `limit`, and `offset`.
- `GuardResultProposalValidationResponse` represents usability, stale state, decision, stale reasons, blocking reasons, warnings, acknowledgement requirement, and recommended next step.
- `LinkGuardResultToProposalResponse` records stale and usable state at link time without mutating storage.

## Proposal usability validation

Validated:

- Stale guard results block proposal validation.
- Expired guard results block proposal validation.
- Blocked guard results are never usable.
- Warning guard results require explicit acknowledgement.
- Allowed fresh guard results are usable.
- `no_guard_override` does not make a blocked guard usable.
- Payload mismatch is detected through storage-contract comparison and returned as stale/blocking state.

## Error model validation

Validated:

- `GuardResultApiError` serializes through Pydantic with `code`, `message`, `field`, and `details`.
- Validation helpers return structured `GuardResultApiValidationResult` or validation response objects instead of producing side effects.

## Old/new text safety validation

Validated:

- Raw `old_text` and `new_text` are request-boundary inputs only.
- Contract response helpers do not persist raw `old_text` or `new_text`.
- Proposal validation delegates payload comparison to the storage contract, where old/new text are represented by hashes.
- No raw patch body, provider prompt, or secret payload storage behavior is introduced.

## Compatibility with storage contract

Validated:

- API responses can wrap `WorkflowGuardResultRecord`.
- API proposal validation delegates final stale and usability checks to storage-contract helpers.
- Rules are aligned: stale records are not usable, blocked records are not usable, warning records require acknowledgement, and allowed fresh records are usable.
- No conflicting duplicated execution rule was found between API and storage contracts.

## Safety boundary validation

Confirmed:

- No endpoints added.
- No DB writes or persistence added.
- No guard results persisted yet.
- No proposal creation behavior changed.
- No apply behavior changed.
- No approval execution behavior changed.
- No frontend behavior changed.
- `database.py` and `routes.py` were not touched in this slice.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| - | - | No issues found. | None. |

## Changes made

No source-code changes.

Created report only:

- `runs/guard-result-api-contract-regression-v1/final-report.md`

## Files changed

- `runs/guard-result-api-contract-regression-v1/final-report.md`

## Exact checks/results

Passed:

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
- `backend/.venv/bin/pytest -q tests/test_guard_result_api_contract.py` — 18 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q tests/test_guard_result_storage_contract.py` — 19 passed, 7 subtests passed
- `backend/.venv/bin/pytest -q` — 479 passed, 38 subtests passed
- `frontend/npx tsc --noEmit`
- `frontend/npm run build`
- `bash scripts/run_tests.sh` — backend 479 passed, 38 subtests passed; frontend TypeScript check passed

## Recommended next slice

Guard Result API Wiring Decision v1.

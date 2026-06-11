# Approval API Contract v1

## Summary

Added pure API request/response contracts for future workflow approval endpoints.

This slice defines Pydantic models and pure validation helpers only. It does not register routes, implement endpoints, touch storage, create migrations, execute tools/providers, create `tool_calls`, or change runtime behavior.

## API contracts added

Added `backend/src/approvals/workflow_approval_api_contract.py` with request/response models for future endpoints:

- `CreateWorkflowApprovalRequest`
- `CreateWorkflowApprovalResponse`
- `ListWorkflowApprovalsRequest`
- `ListWorkflowApprovalsResponse`
- `GetWorkflowApprovalResponse`
- `ApproveWorkflowApprovalRequest`
- `ApproveWorkflowApprovalResponse`
- `RejectWorkflowApprovalRequest`
- `RejectWorkflowApprovalResponse`
- `ExecuteWorkflowApprovalRequest`
- `ExecuteWorkflowApprovalResponse`
- `WorkflowApprovalApiError`
- `WorkflowApprovalApiValidationResponse`

Added pure helpers:

- `build_approval_api_error(...)`
- `build_create_approval_response(...)`
- `validate_execute_approval_request_contract(...)`

The models align with:

- `backend/src/approvals/workflow_approval_contract.py`
- `backend/src/approvals/workflow_approval_storage_contract.py`

## Future endpoint semantics

Future endpoints modeled but not implemented:

- `POST /api/approvals/workflow`
  - creates an approval request contract;
  - does not execute the action.
- `GET /api/approvals/workflow`
  - lists approval records;
  - does not execute actions.
- `GET /api/approvals/workflow/{id}`
  - returns one approval record;
  - does not execute actions.
- `POST /api/approvals/workflow/{id}/approve`
  - records approval decision;
  - does not execute the action.
- `POST /api/approvals/workflow/{id}/reject`
  - records rejection decision;
  - does not execute the action.
- `POST /api/approvals/workflow/{id}/execute`
  - future separate execution boundary;
  - must revalidate policy/status/expiry/payload/confirmations at runtime;
  - may reference `tool_call_id` only after a future execution attempt.

## Execution boundary

Critical boundary preserved:

```text
request approval
→ approve/reject
→ separate execute endpoint
→ revalidate policy/status/expiry/payload
→ create tool_call/audit only on execution attempt
```

Contract behavior:

- create response has `executes_action=false`;
- list/get responses have `executes_action=false`;
- approve/reject responses have `executes_action=false`;
- execute request is declarative and requires explicit `execute_confirmations`;
- execute response can carry future `tool_call_id`, but the contract itself does not execute anything;
- execute validation returns structured errors/warnings only.

## Safety guarantees

Confirmed by contract and tests:

- no raw secrets accepted in payload summary;
- no raw provider prompts accepted through storage payload summary;
- full patch/diff bodies are rejected by storage payload summary guardrails;
- `run_tests` execute request requires command allowlist confirmation;
- `apply_patch` execute request requires explicit checkbox and protected file review confirmations;
- `rollback_patch` follows high-risk confirmation semantics through shared classification;
- `external_provider_execution` remains critical and invalid for execution;
- rejected/expired/cancelled approvals cannot execute;
- policy version mismatch fails safely;
- execute contract must revalidate at runtime later;
- no route registration;
- no DB access;
- no storage helper implementation;
- no tool/provider execution.

## Source changes

- Added `backend/src/approvals/workflow_approval_api_contract.py`
- Added `backend/tests/test_workflow_approval_api_contract.py`
- Added `runs/approval-api-contract-v1/final-report.md`

## Tests

Passed:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
  - `379 passed, 19 subtests passed`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `bash scripts/run_tests.sh`
  - backend syntax checks passed
  - pytest passed: `379 passed, 19 subtests passed`
  - frontend TypeScript check passed

## Remaining gaps

- No approval API endpoints are implemented.
- No `routes.py` wiring exists.
- No database storage exists.
- No migrations exist.
- No storage helpers exist.
- No approval UI exists.
- No approval-gated execution handler exists.
- No approval-gated apply/test/analyze/rollback exists.
- External provider execution remains disabled.

## Recommended next slice

Recommended next slice: `Approval API Contract Regression Pass v1`.

# Approval Request Model v1

## Summary

Added a pure approval request contract for future semi-auto workflow actions.

This slice defines model shapes, risk classification, required confirmations, and validation guardrails for approval-gated actions. It does not implement persistence, endpoints, execution, or any runtime workflow behavior.

## Contract models

Added `backend/src/approvals/workflow_approval_contract.py` with:

- `WorkflowApprovalAction`
  - `create_proposal`
  - `apply_patch`
  - `run_tests`
  - `analyze_result`
  - `rollback_patch`
  - `external_provider_execution`
- `WorkflowApprovalStatus`
  - `draft`
  - `pending`
  - `approved`
  - `rejected`
  - `expired`
  - `cancelled`
- `WorkflowApprovalRisk`
  - `low`
  - `medium`
  - `high`
  - `critical`
- `WorkflowApprovalRequirement`
  - `manual_confirmation`
  - `explicit_checkbox`
  - `protected_file_review`
  - `command_allowlist_check`
  - `provider_permission_check`

Added Pydantic contract models:

- `WorkflowApprovalPayloadSummary`
- `WorkflowApprovalRequestContract`
- `WorkflowApprovalDecisionContract`
- `WorkflowApprovalValidationResult`

Added pure helpers:

- `classify_workflow_approval_action(...)`
- `build_workflow_approval_request(...)`
- `validate_workflow_approval_request(...)`

## Risk rules

| Action | Risk | Required confirmations | v1 executable |
| --- | --- | --- | --- |
| `create_proposal` | medium | manual confirmation | no |
| `apply_patch` | high | manual confirmation, explicit checkbox, protected file review | no |
| `run_tests` | medium | manual confirmation, command allowlist check | no |
| `analyze_result` | low | manual confirmation | no |
| `rollback_patch` | high | manual confirmation, explicit checkbox, protected file review | no |
| `external_provider_execution` | critical | manual confirmation, provider permission check | no |

Every action is contract-only in this slice. Even an approved status does not execute anything.

## Validation rules

Validation checks:

- action risk matches the static policy rule;
- all required confirmations are present;
- protected paths require `protected_file_review`;
- protected path payloads are warned if not explicitly flagged;
- secret-like payload values are rejected;
- `contains_secret_like_values=true` makes the request invalid;
- `external_provider_execution` remains critical and non-executable in v1;
- approved status is treated as a future decision state only.

## Safety guarantees

Confirmed for this slice:

- no DB implementation;
- no DB migrations;
- no `database.py` edits;
- no API endpoint implementation;
- no project creation;
- no run creation;
- no tool_calls;
- no tools execution;
- no provider/LLM calls;
- no patch proposal execution;
- no apply patch execution;
- no test execution from approval model;
- no analyze execution;
- no rollback execution;
- no shell runner;
- no autonomous mode.

## Source changes

- Added `backend/src/approvals/workflow_approval_contract.py`
- Added `backend/tests/test_workflow_approval_contract.py`
- Added `runs/approval-request-model-v1/final-report.md`

## Tests

Passed:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
  - `351 passed, 13 subtests passed`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `bash scripts/run_tests.sh`
  - backend syntax checks passed
  - pytest passed: `351 passed, 13 subtests passed`
  - frontend TypeScript check passed

## Remaining gaps

- Approval requests are not persisted.
- No approval request API endpoints exist.
- No frontend approval UI is wired to this contract.
- No execution boundary consumes approved requests yet.
- No storage model or migration exists.
- External provider execution remains disabled/stub-only.
- Semi-auto approval execution is still future work.

## Recommended next slice

Recommended next slice: `Approval Request Regression Pass v1`.

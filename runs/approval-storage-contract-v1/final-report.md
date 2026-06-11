# Approval Storage Contract v1

## Summary

Added a pure storage-facing contract for future persisted workflow approval requests.

This slice defines the future DB-facing shape, status lifecycle, execution boundary checks, and storage sanitization guardrails. It does not implement database storage, migrations, API endpoints, storage helpers, UI, tool execution, provider execution, or runtime behavior changes.

## Storage contract models

Added `backend/src/approvals/workflow_approval_storage_contract.py` with:

- `WorkflowApprovalStorageStatus`
  - `draft`
  - `pending`
  - `approved`
  - `rejected`
  - `expired`
  - `cancelled`
- `WorkflowApprovalLinkScope`
  - `standalone`
  - `project`
  - `run`
  - `step`
  - `tool_call`
  - `intake_session`
- `WorkflowApprovalStoredPayloadSummary`
- `WorkflowApprovalStorageRecord`
- `WorkflowApprovalDecisionRecord`
- `WorkflowApprovalExecutionLink`
- `WorkflowApprovalStorageSnapshot`
- `WorkflowApprovalStatusTransition`
- `WorkflowApprovalStorageValidationResult`

The storage record supports optional links:

- `project_id`
- `run_id`
- `step_id`
- `tool_call_id`, only after execution attempt metadata exists
- `intake_session_id`

It also includes:

- `action`
- `status`
- `risk_level`
- `title`
- `reason`
- `payload_summary_json`
- `required_confirmations`
- `policy_version`
- `created_at`
- `expires_at`
- `decided_at`
- `approved_by`
- `rejected_by`
- `decision_reason`
- `stale_reason`
- `execution_attempted_at`

## Status lifecycle

Pure transition helper:

- `can_transition_approval_status(from_status, to_status)`
- `describe_approval_status_transition(from_status, to_status)`

Allowed transitions:

- `draft -> pending`
- `pending -> approved`
- `pending -> rejected`
- `pending -> cancelled`
- `pending -> expired`

Terminal states:

- `rejected`
- `expired`
- `cancelled`

The contract intentionally avoids adding `executed` / `execution_failed` approval statuses in this slice. Future execution results should be represented by a `tool_call` audit record linked through `WorkflowApprovalExecutionLink`.

## Execution boundary

Pure helpers:

- `validate_approval_storage_record(record)`
- `is_approval_executable_from_storage(record, now=None)`
- `build_approval_storage_snapshot(...)`

Execution boundary rules:

- approval itself never executes anything;
- only `approved` records can become executable candidates;
- expired approvals are not executable;
- rejected/expired/cancelled approvals are not executable;
- records with `stale_reason` are not executable;
- records with missing required confirmations are not executable;
- records with raw payload storage are not executable;
- records with secret-like payload flags are not executable;
- `external_provider_execution` remains non-executable and critical;
- `tool_call_id` requires `execution_attempted_at`;
- records with `tool_call_id` or `execution_attempted_at` are not executable again.

## Sanitization/secret guardrails

The storage-facing payload summary rejects or flags:

- secret-like keys;
- secret-like assignment values;
- `.env`, key, pem, p12, pfx, `id_rsa`, and `id_ed25519` paths;
- oversized summary text;
- oversized payload summaries;
- full raw command output metadata keys;
- full provider prompt metadata keys;
- raw patch/full diff metadata keys;
- full patch body text in summary fields;
- private key material.

The contract stores summaries only. Raw payloads must be omitted.

## Safety guarantees

Confirmed for this slice:

- no DB implementation;
- no migrations;
- no `database.py` edits;
- no `routes.py` edits;
- no API endpoints;
- no storage helpers;
- no UI;
- no tool execution;
- no provider execution;
- no project creation;
- no run creation;
- no tool_call creation;
- no auto apply;
- no auto tests;
- no auto analyze;
- no auto rollback;
- no git commit.

## Source changes

- Added `backend/src/approvals/workflow_approval_storage_contract.py`
- Added `backend/tests/test_workflow_approval_storage_contract.py`
- Added `runs/approval-storage-contract-v1/final-report.md`

## Tests

Passed:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
  - `367 passed, 16 subtests passed`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `bash scripts/run_tests.sh`
  - backend syntax checks passed
  - pytest passed: `367 passed, 16 subtests passed`
  - frontend TypeScript check passed

## Remaining gaps

- No actual approval DB table exists.
- No migration exists.
- No storage helpers exist.
- No approval API exists.
- No approval UI exists.
- No approval execution endpoint exists.
- No approval-gated apply/test/analyze/rollback exists.
- No external provider permission model exists.
- No stale-payload revalidation implementation exists beyond pure contract checks.

## Recommended next slice

Recommended next slice: `Approval API Contract v1`.

Reason: `database.py` is large/dirty, so one more API/storage boundary contract slice is safer before touching real DB storage.

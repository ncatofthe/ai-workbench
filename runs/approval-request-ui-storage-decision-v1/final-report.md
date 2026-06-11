# Approval Request UI/Storage Decision v1

## Summary

Decision: future workflow approvals should use a separate `WorkflowApprovalRequest` entity with optional links to project, run, step, tool call, and future intake session records.

Approvals should represent user-reviewed permission for a future gated action. They must not execute automatically. Execution should happen only through a separate, policy-gated execution boundary after the backend revalidates the approval, payload, status, expiry, and current workflow policy.

Recommended next slice: `Approval Storage Contract v1` before database implementation, because the current database layer is large/dirty and the model should be finalized one more step before migration work.

## Current State

Implemented today:

- frontend/backend workflow policy;
- backend workflow policy endpoint;
- pure approval contract in `backend/src/approvals/workflow_approval_contract.py`;
- approval contract tests in `backend/tests/test_workflow_approval_contract.py`;
- direct safe actions remain limited to:
  - `auto_gather_context`;
  - `build_context_bundle`;
  - `create_patch_draft`;
- proposal/apply/tests/analyze/rollback remain manual-only or future approval-gated;
- external provider execution remains blocked/not enabled.

Not implemented:

- approval storage;
- approval API;
- approval UI;
- approval decision persistence;
- approval-gated execution;
- auto apply/test/analyze/rollback;
- external provider execution.

## Options Considered

| Option | Description | Pros | Cons | Decision |
| --- | --- | --- | --- | --- |
| A. Attach approvals directly to runs | Store approvals as run-owned records only. | Simple run timeline integration. | Too coarse; approvals often belong to a step or future action payload. Weak for pre-run/intake approvals. | Not recommended. |
| B. Attach approvals to run steps | Store approvals as step-owned records. | Good step-level context and RunDetail UI placement. | Some approvals may exist before a step is finalized or outside one step. | Useful link, not primary boundary. |
| C. Attach approvals to tool calls | Approval record is coupled to a tool call. | Strong audit link after execution. | Wrong lifecycle: approval may exist before any tool call. Tool call should be created only after approval and execution attempt. | Not recommended as primary model. |
| D. Separate `workflow_approval_requests` entity | Dedicated approval entity with its own lifecycle. | Clean audit boundary; can exist before execution; avoids forced tool_call creation. | Needs explicit linking and careful UI surfacing. | Good base. |
| E. Hybrid linked approval entity | Separate approval entity with optional links to project/run/step/tool_call/intake_session. | Best lifecycle fit; supports pre-execution approvals and post-execution audit links. | More fields and validation rules. | Recommended. |

## Recommended Decision

Use a separate `WorkflowApprovalRequest` persistence boundary with optional links:

- `project_id`
- `run_id`
- `step_id`
- `tool_call_id`, populated only after execution attempt creates a tool call/audit record
- `intake_session_id`, optional for future intake-driven approvals

This keeps approval review separate from execution. It also avoids creating fake or premature `tool_calls` before a user approves a future action.

The approval entity should store only bounded summaries and policy metadata, not raw patch bodies, raw command output, provider prompts, secret values, or full tool payloads.

## Proposed Data Model

Future table/entity: `workflow_approval_requests`

Purpose:

- persist user-reviewable permission requests for future gated workflow actions;
- provide auditability for decisions;
- connect approval requests to project/run/step context without forcing execution.

Key fields:

| Field | Purpose |
| --- | --- |
| `id` | Stable approval request id. |
| `project_id` | Optional project context. |
| `run_id` | Optional run context. |
| `step_id` | Optional step context. |
| `tool_call_id` | Optional link after execution attempt, not before. |
| `intake_session_id` | Optional future link for intake/session-originated approvals. |
| `action` | One of `create_proposal`, `apply_patch`, `run_tests`, `analyze_result`, `rollback_patch`, `external_provider_execution`. |
| `status` | `draft`, `pending`, `approved`, `rejected`, `expired`, `cancelled`. |
| `risk_level` | `low`, `medium`, `high`, `critical`. |
| `title` | Human-readable action title. |
| `reason` | Why approval is needed. |
| `payload_summary_json` | Bounded sanitized summary, not raw payload. |
| `required_confirmations_json` | Required UI/backend confirmations. |
| `created_at` | Creation timestamp. |
| `expires_at` | Optional expiry timestamp. |
| `decided_at` | Optional decision timestamp. |
| `approved_by` | Optional actor id/name for approve decision. |
| `rejected_by` | Optional actor id/name for reject decision. |
| `decision_reason` | Optional user/system reason. |
| `policy_version` | Optional future policy version used at creation. |

Optional related table/entity later: `workflow_approval_events`

- append-only audit trail for created, shown, approved, rejected, expired, executed, execution_failed;
- useful if approval history becomes more complex than one status row.

## Proposed UI Model

Future UI surfaces:

- Approvals page / approval queue
  - filter by status, risk, project, run, action;
  - show pending approvals first;
  - highlight expired/rejected/cancelled approvals.
- RunDetail pending approvals section
  - show approvals scoped to the current run;
  - place near patch-workflow cockpit and relevant step details.
- Step-level approval card
  - show approval request for the current actionable step;
  - show risk badge, action type, reason, payload summary, required confirmations.

Approval card content:

- action title;
- risk badge;
- status badge;
- “what will happen if approved” copy;
- payload summary;
- affected files, if any;
- command summary, if any;
- provider summary, if any;
- required confirmations;
- approve/reject buttons;
- explicit checkbox for high-risk actions;
- protected file warning when needed.

UI must not hide execution. Approval should be visibly separate from execution, and copy should make clear whether approval merely permits a future action or immediately triggers a separate execute endpoint.

## Future API Surface

Do not implement in this slice.

Possible future endpoints:

- `POST /api/approvals/workflow`
  - create approval request from a sanitized payload summary;
  - does not execute action.
- `GET /api/approvals/workflow`
  - list approval requests by status/project/run/risk/action.
- `GET /api/approvals/workflow/{id}`
  - fetch one approval request.
- `POST /api/approvals/workflow/{id}/approve`
  - record approval decision;
  - does not execute action.
- `POST /api/approvals/workflow/{id}/reject`
  - record rejection decision;
  - does not execute action.
- `POST /api/approvals/workflow/{id}/execute`
  - separate endpoint;
  - must revalidate approval, expiry, payload, policy, confirmations, and action-specific safety;
  - creates tool_call/audit record only when execution is attempted.

The execute endpoint must remain separate and policy-gated.

## Execution Lifecycle

Future safe lifecycle:

```text
request approval
→ user reviews payload summary and risk
→ user approves or rejects
→ backend stores decision
→ execution endpoint is called explicitly
→ backend revalidates approval, payload, expiry, confirmations, and current policy
→ backend runs only the approved action if still allowed
→ backend creates tool_call/audit record
→ result links back to approval
```

Important boundary:

Approval itself must not execute the action.

Rejected, expired, cancelled, stale, or policy-invalid approvals cannot be executed. Approved requests must still be revalidated at execution time.

## Safety Guarantees

Future persistence/UI must preserve:

- no raw secrets in approval payloads;
- no full provider prompts in approval payloads;
- no full patch bodies unless separately reviewed and storage-safe;
- protected files require explicit confirmation;
- `apply_patch` requires checkbox/confirm;
- `run_tests` requires command allowlist check;
- `rollback_patch` requires explicit confirmation;
- `external_provider_execution` requires provider permission and remains disabled until separate integration;
- expired/rejected/cancelled approvals cannot execute;
- stale approvals must be revalidated;
- approval does not create `tool_call` until an execution attempt;
- approval does not execute tools/providers;
- approval does not auto-apply patches;
- approval does not auto-run tests;
- approval does not auto-analyze or auto-rollback.

## Migration Strategy

Recommended implementation order:

1. `Approval Storage Contract v1`
   - finalize storage-facing schema contract and serialization rules;
   - define status transitions and stale/expiry behavior;
   - still no DB migration.
2. `Approval Storage Foundation v1`
   - add migration/table and storage helpers;
   - keep execution disconnected.
3. `Approval API Create/List v1`
   - create/list/get approval requests;
   - read/write approval metadata only.
4. `Approval UI Queue v1`
   - show queue and RunDetail pending approvals;
   - no execution.
5. `Approval Decision v1`
   - approve/reject decisions and audit status changes;
   - no execution.
6. `Approval-gated Execution Boundary v1`
   - add explicit execute endpoint;
   - revalidate policy before execution;
   - create tool_call/audit record only on execution attempt.
7. `Approval-gated Apply Patch v1`
   - limited apply flow through approval boundary.
8. `Approval-gated Run Tests v1`
   - limited allowlisted test command flow through approval boundary.

## Risks

- `database.py` is already large/dirty, so schema work should be isolated and carefully reviewed.
- Coupling approvals too tightly to `tool_calls` would force wrong lifecycle ordering.
- Storing raw payloads could leak secrets or oversized unsafe data.
- Approving stale payloads could be dangerous if files, commands, or policy changed.
- Frontend/backend policy drift could make the UI display weaker guarantees than backend enforces.
- Approval UI could accidentally imply or trigger auto-execution.
- External provider execution must remain blocked until a separate provider permission model exists.
- Expiry and stale-payload logic needs explicit design before execution integration.

## Recommended Next Slice

Recommended next slice: `Approval Storage Contract v1`.

# Guard Result Persistence/Audit Decision v1

## Summary

Decision: use a hybrid guard audit model.

Future Source-of-Truth Guard checks should be persisted as a dedicated immutable `WorkflowGuardResult` audit entity, and future patch proposal records/tool calls should link to the latest relevant guard result when one was used. Patch apply/audit records should also snapshot the guard id/decision that justified the proposal.

Do not store guard checks as normal tool calls by default. A guard check is a read-only policy/audit evaluation, not a workspace tool execution. It can still be surfaced in RunDetail timelines and linked to proposal/apply audit later.

Recommended next slice: `Guard Result Storage Contract v1`, implemented as pure Pydantic/contract models and stale-detection helpers only, with no database wiring and no `routes.py` changes.

## Current state

Implemented today:

- `RunStep.input` contains `AI_WORKBENCH_REQUIREMENT_CONTEXT`.
- Backend read-only endpoint:
  - `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard`
- Guard decision values:
  - `allowed`
  - `warning`
  - `blocked`
- RunDetail has a manual Source-of-Truth Guard UI.
- Patch proposal preview is gated by latest frontend guard result.
- Guard context can be copied manually into the patch form context/banner.

Current limitation:

- Guard result lives only in frontend component state.
- Backend proposal creation does not know which guard result was checked.
- Warning acknowledgement and no-guard override are frontend-only.
- No persistent audit exists for guard checks that do not become proposals.

## Options considered

| Option | Description | Pros | Cons | Decision |
| --- | --- | --- | --- | --- |
| A. Store guard results as `tool_calls` | Every guard check creates a tool-call-like audit row. | Reuses existing Tool Calls UI/audit surface. Easy to list beside patch calls. | Guard is not a tool execution. Would pollute tool history and blur "read-only evaluation" vs "workspace action". Could imply execution that did not happen. | Not recommended as primary storage. |
| B. Dedicated `workflow_guard_results` entity | Store each guard check as its own audit entity. | Clean lifecycle. Can link to run/step/project/proposal later. Supports checks that never create proposals. Easier stale/freshness tracking. | Requires future schema/storage/API work and new UI surfacing. | Recommended base. |
| C. Store guard only on patch proposal/tool_call | Persist guard snapshot only if proposal is created. | Avoids extra records. Keeps proposal audit compact. | Loses audit trail for blocked/warning checks that stop the user before proposal creation. Weak for "why did user override/no-op" analysis. | Useful link/snapshot, not enough alone. |
| D. Hybrid dedicated entity + proposal/apply links | Persist guard checks separately; link proposals/applies to relevant guard result and snapshot decision. | Best audit trail. Captures abandoned/blocked checks and proposal lineage. Keeps tool calls clean. Allows backend freshness validation. | More moving parts and needs careful stale/secret rules. | Recommended. |

## Recommended architecture

Use a dedicated immutable guard-result audit entity:

- `WorkflowGuardResult`
  - created when the guard endpoint is explicitly run with persistence enabled in a future slice;
  - linked to `project_id`, `run_id`, `step_id`;
  - stores sanitized guard input snapshot;
  - stores parsed requirement context snapshot;
  - stores guard result snapshot;
  - tracks staleness and invalidation metadata.

Then link downstream workflow actions:

- future patch proposal accepts `guard_result_id` when user creates proposal from a checked guard;
- proposal stores guard snapshot fields at creation time;
- apply/audit stores the proposal's guard id/decision snapshot;
- warning/no-guard override decisions are persisted explicitly instead of relying on frontend state.

This gives AI Workbench a real audit chain:

```text
RunStep requirement context
→ guard check
→ guard result
→ optional warning acknowledgement / no-guard override
→ patch proposal
→ manual apply / approval-gated apply later
```

## Guard result lifecycle

Recommended lifecycle:

1. User manually runs Source-of-Truth Guard.
2. Backend parses `RunStep.input` requirement context.
3. Backend evaluates guard deterministically.
4. Future persistent mode writes immutable `WorkflowGuardResult`.
5. RunDetail displays latest guard result for the step.
6. User may:
   - abandon the check;
   - use guard context in patch form;
   - acknowledge warning and create proposal;
   - use no-guard override;
   - stop because result is blocked.
7. If proposal is created, backend links proposal to `guard_result_id` or records explicit override metadata.
8. If proposal/apply occurs later, backend revalidates freshness and policy.

Guard result records should be immutable after creation, except for derived metadata:

- `is_stale`
- `stale_reason`
- `proposal_tool_call_id`
- `updated_at`

## Staleness/invalidation rules

A guard result should become stale when any proposal-critical input diverges from what was checked:

- `file_path` changes.
- `old_text` changes.
- `new_text` changes.
- proposed action / patch summary changes.
- patch operation count changes.
- patch proposal payload differs from checked guard input.
- `RunStep.input` requirement context changes.
- a new source-of-truth document replaces the previous one.
- a new coverage preview / requirement mapping supersedes the prior one.
- the linked run step is replaced, cancelled, or completed with different metadata.
- proposal is created after an expiry window, for example 30-60 minutes, configurable later.
- project files changed materially after guard check and before proposal, if future file hashes are available.

Stale results should not silently authorize proposals. Backend proposal creation should either:

- reject stale `guard_result_id`;
- require a new guard check;
- or persist an explicit no-guard/stale-guard override with reason.

## Relationship to patch proposal

Future proposal creation should support:

- `guard_result_id` optional but strongly encouraged for step-linked proposals.
- `guard_decision_snapshot`.
- `guard_drift_risk_snapshot`.
- `guard_matched_requirement_ids_snapshot`.
- `guard_warning_acknowledged`.
- `no_guard_override`.
- `guard_stale_at_proposal`.
- `guard_stale_reason`.

Recommended rules:

- `allowed`: proposal may proceed if guard result is fresh.
- `warning`: proposal may proceed only if warning acknowledgement is persisted.
- `blocked`: proposal should not proceed by default.
- blocked override should not be added until a separate explicit product policy exists.
- no-guard proposal may proceed only with explicit no-guard override and reason, if product policy allows it.
- backend must validate freshness when proposal is created.
- frontend state alone must never be trusted permanently.

Proposal should not store raw full patch bodies inside guard records. The proposal/tool-call layer can continue storing the actual patch proposal data according to existing patch audit rules.

## Relationship to approval flow

Future `WorkflowApprovalRequest` should include guard context for gated actions:

- `guard_result_id`
- guard decision snapshot
- drift risk snapshot
- stale/fresh status at approval creation
- warning acknowledgement or no-guard override status
- matched requirement ids
- blocked/forbidden hits summary

Approval requests should never mutate guard results. They should reference immutable guard snapshots.

Future approval execution must revalidate:

- approval status and expiry;
- guard result freshness;
- current workflow policy;
- current proposal payload vs checked guard input;
- protected/secret path rules;
- command allowlist where relevant.

If guard result is stale at execution time, execution should stop and request a fresh guard or explicit user decision, depending on action type and policy.

## Suggested storage shape

Future entity: `WorkflowGuardResult`

Suggested fields:

| Field | Purpose |
| --- | --- |
| `id` | Stable guard result id. |
| `project_id` | Project context, if available. |
| `run_id` | Run context. |
| `step_id` | RunStep context. |
| `source_tool_call_id` | Optional future link if guard is ever represented in a broader audit stream. Usually null. |
| `proposal_tool_call_id` | Optional link when a proposal is created from this guard. |
| `decision` | `allowed`, `warning`, or `blocked`. |
| `drift_risk` | `low`, `medium`, `high`, or `critical`. |
| `proposed_action` | Sanitized checked action/summary text. |
| `file_path` | Checked file path, if any. |
| `patch_summary` | Sanitized checked patch summary. |
| `old_text_hash` | Optional hash only; do not store raw old text by default. |
| `new_text_hash` | Optional hash only; do not store raw new text by default. |
| `parsed_context_json` | Parsed requirement context snapshot. |
| `result_json` | Full structured guard result snapshot. |
| `warnings_json` | Warnings snapshot for easier querying. |
| `reasons_json` | Reasons snapshot for easier querying. |
| `acknowledged_warning` | Whether user acknowledged warning before proposal. |
| `no_guard_override` | Whether proposal intentionally proceeded without a guard. Usually false for real guard records. |
| `is_stale` | Whether guard result is stale. |
| `stale_reason` | Why it became stale. |
| `created_by` | User/system source. |
| `source` | UI/API source, e.g. `run_detail_step_patch`. |
| `expires_at` | Optional freshness expiry. |
| `created_at` | Creation timestamp. |
| `updated_at` | Timestamp for stale/link metadata changes. |

Guard input should be sanitized:

- no raw secrets;
- no `.env` values;
- no full provider prompts;
- no full command output;
- no full patch body unless a separate storage-safe review policy exists.

## Suggested endpoint evolution

Do not implement in this slice.

Future endpoint changes:

- `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard`
  - keep current read-only behavior by default;
  - optional future `persist=true` can create a guard audit record;
  - response may include `guard_result_id` when persisted.
- `GET /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard-results`
  - list guard results for a run step.
- `GET /api/guard-results/{guard_result_id}`
  - fetch one guard result.
- `POST /api/projects/{project_id}/tools/propose-patch`
  - optional future `guard_result_id`;
  - optional explicit `no_guard_override` and reason;
  - backend validates guard freshness and decision before proposal creation.
- Future approval endpoints
  - include guard snapshot/link in `WorkflowApprovalRequest`.

Current guard endpoint should remain non-mutating unless persistence is explicitly added in a future slice.

## Safety boundaries

Future persistence must preserve:

- guard evaluation itself remains read-only except optional audit write;
- audit write must not execute tools/providers;
- audit write must not create patch proposals;
- proposal creation must not apply patches;
- apply still requires `confirm=true` or future approval gate;
- backend must not trust frontend-only guard state forever;
- `blocked` must not gain override behavior without explicit product policy;
- warning/no-guard overrides must be explicit and auditable;
- raw secrets and large raw patch bodies must not be stored in guard records;
- external providers remain blocked unless separately enabled by provider policy.

## Risks

- Stale frontend guard state can create false confidence.
- Deterministic keyword matching can under-block semantic drift.
- Deterministic keyword matching can over-block legitimate changes.
- Storing guard checks as tool calls could pollute Tool Calls history.
- Storing raw patch text, command output, provider prompts, or secrets could leak sensitive data.
- Blocked override policy is not yet defined.
- Proposal/approval/guard policy can drift if frontend and backend rules diverge.
- If backend does not validate freshness, persisted guard ids could be reused incorrectly.
- If guard result is mutable, audit value drops sharply.

## Recommended next slice

Guard Result Storage Contract v1.

Recommended scope:

- pure backend contract module;
- Pydantic models/enums for `WorkflowGuardResult`;
- stale detection helpers;
- sanitized snapshot helpers;
- tests for serialization, stale rules, and secret/path guardrails;
- no `database.py`;
- no `routes.py`;
- no DB migration;
- no runtime behavior change.

## Files inspected

- `backend/src/api/routes.py`
- `backend/src/orchestrator/project_intake.py`
- `backend/src/approvals/workflow_approval_contract.py`
- `backend/src/approvals/workflow_approval_storage_contract.py`
- `backend/src/approvals/workflow_approval_api_contract.py`
- `frontend/src/pages/RunDetail.tsx`
- `frontend/src/api/client.ts`
- `frontend/src/types/index.ts`
- `runs/approval-request-ui-storage-decision-v1/final-report.md`
- `runs/guard-context-to-patch-form-prefill-regression-v1/final-report.md`

## Source-code changes

None.

This slice created only:

- `runs/guard-result-persistence-audit-decision-v1/final-report.md`

The working tree already contains unrelated/pre-existing source diffs from prior accepted slices. They were preserved and not modified.

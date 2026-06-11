# Approval Storage Regression Pass v1

## Summary

Approval Storage Contract v1 is stable.

No P0/P1/P2/P3 issues were found. The storage-facing approval contract remains pure, does not introduce runtime behavior, and is consistent with the workflow approval contract and workflow policy boundaries.

## Checks table

| Check | Result | Notes |
| --- | --- | --- |
| Contract purity | Passed | No DB/API/tool/provider imports, no file scanning, no execution hooks. |
| Approval contract consistency | Passed | Action/risk/confirmation semantics align with `workflow_approval_contract.py`. |
| Status/executability invariants | Passed | Terminal statuses and invalid states are non-executable. |
| Payload safety | Passed | Secret-like values, protected paths, raw outputs, provider prompts, patch bodies, and oversized summaries are guarded. |
| Workflow policy consistency | Passed | Only direct safe actions are auto-runnable. |
| Backend py_compile database.py | Passed | `src/storage/database.py` compiles; not edited by this pass. |
| Backend pytest | Passed | `367 passed, 16 subtests passed`. |
| Frontend TypeScript | Passed | `npx tsc --noEmit` passed. |
| Frontend production build | Passed | `npm run build` passed. |
| Root test runner | Passed | `bash scripts/run_tests.sh` passed. |

## Contract purity

Inspected:

- `backend/src/approvals/workflow_approval_storage_contract.py`
- `backend/src/approvals/workflow_approval_contract.py`
- `backend/tests/test_workflow_approval_storage_contract.py`

Confirmed:

- no `src.storage` imports;
- no `src.api` / route imports;
- no `src.project_tools` imports;
- no provider imports;
- no HTTP client imports;
- no subprocess usage;
- no file scanning;
- no project/run/tool_call creation;
- no patch/apply/test/analyze/rollback execution;
- no state mutation beyond pure Pydantic model construction and pure helper return values.

The storage contract imports only:

- standard pure modules (`enum`, `re`, `datetime`, typing helpers);
- Pydantic models/validators;
- approval contract enums/classification helper.

## Storage/approval consistency

Confirmed alignment with `workflow_approval_contract.py`:

- `create_proposal`: medium risk, manual confirmation.
- `apply_patch`: high risk, manual confirmation, explicit checkbox, protected file review.
- `run_tests`: medium risk, manual confirmation, command allowlist check.
- `analyze_result`: low risk, manual confirmation.
- `rollback_patch`: high risk, manual confirmation, explicit checkbox, protected file review.
- `external_provider_execution`: critical risk, manual confirmation, provider permission check, non-executable.

The storage contract does not weaken validation:

- it reuses `classify_workflow_approval_action(...)`;
- it validates expected risk;
- it validates required confirmations;
- it blocks executable candidates with stale, expired, raw, or secret-like payload state.

## Status/executability invariants

Confirmed:

- allowed transitions are limited to:
  - `draft -> pending`;
  - `pending -> approved`;
  - `pending -> rejected`;
  - `pending -> cancelled`;
  - `pending -> expired`;
- `rejected`, `expired`, and `cancelled` are terminal/non-executable;
- pending records without required confirmations are non-executable and invalid;
- `tool_call_id` is optional before execution;
- `tool_call_id` requires `execution_attempted_at`;
- records with `tool_call_id` or `execution_attempted_at` are not executable again;
- approval itself never creates a `tool_call`;
- execution remains a separate future boundary.

Additional runtime assertions confirmed:

- an approved `apply_patch` storage record can only become an executable candidate when all confirmations and safe summary constraints are present;
- expired approved records are non-executable;
- approved `external_provider_execution` records remain non-executable.

## Payload safety

Confirmed guardrails for:

- secret-like keys;
- secret-like assignment values;
- `.env`, key, pem, p12, pfx, `id_rsa`, and `id_ed25519` protected paths;
- protected path flag mismatch warnings;
- raw command output metadata keys;
- provider prompt metadata keys;
- full patch/full diff metadata keys;
- full patch/diff body text;
- private key material;
- oversized summary fields;
- oversized payload summary size;
- `raw_payload_omitted=false`.

Payload summaries remain storage summaries only, not raw execution payloads.

## Workflow policy consistency

Confirmed Safe Prep auto-runnable actions remain exactly:

```text
auto_gather_context, build_context_bundle, create_patch_draft
```

Confirmed proposal/apply/tests/analyze/rollback did not become automatic.

Approval storage contract does not alter:

- workflow policy;
- direct safe action list;
- manual-only actions;
- blocked shell/provider/auto-apply boundaries.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | None | No issues found. | No fix needed. |

## Changes made

No source-code changes.

Created report only:

- `runs/approval-storage-regression-v1/final-report.md`

## Recommended next slice

Recommended next slice: `Approval API Contract v1`.

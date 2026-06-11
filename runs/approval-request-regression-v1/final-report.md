# Approval Request Regression Pass v1

## Summary

Approval Request Model v1 is stable.

No P0/P1 regressions were found. The approval request contract remains a pure model/classification/validation layer and does not introduce DB storage, API endpoints, tool execution, provider execution, or runtime workflow behavior.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| Contract purity inspection | Passed | No DB/tool/provider imports, no file scanning, no execution hooks. |
| Approval action risk rules | Passed | Risks match expected action categories. |
| Validation invariants | Passed | Required confirmations, protected paths, secret-like payloads, and invalid actions fail safely. |
| Workflow policy consistency | Passed | Only direct safe actions remain auto-runnable. Approval actions do not become automatic. |
| Backend py_compile database.py | Passed | `src/storage/database.py` compiles; not edited by this pass. |
| Backend pytest | Passed | `351 passed, 13 subtests passed`. |
| Frontend TypeScript | Passed | `npx tsc --noEmit` passed. |
| Frontend production build | Passed | `npm run build` passed. |
| Root test runner | Passed | `bash scripts/run_tests.sh` passed. |

## Contract purity

Verified `backend/src/approvals/workflow_approval_contract.py`:

- no `src.storage` imports;
- no `src.project_tools` imports;
- no provider imports;
- no HTTP client imports;
- no subprocess usage;
- no file scanning;
- no project/run/tool_call creation;
- no patch/apply/test/analyze/rollback execution;
- no state mutation beyond constructing Pydantic model instances.

The module imports only standard pure utilities and Pydantic:

- `enum`
- `re`
- `datetime`
- typing helpers
- `BaseModel`, `Field`, `field_validator`

## Risk/validation invariants

Verified action rules:

- `create_proposal`: medium risk, manual confirmation, non-executable in v1.
- `apply_patch`: high risk, manual confirmation, explicit checkbox, protected file review, non-executable in v1.
- `run_tests`: medium risk, manual confirmation, command allowlist check, non-executable in v1.
- `analyze_result`: low risk, manual confirmation, non-executable in v1.
- `rollback_patch`: high risk, manual confirmation, explicit checkbox, protected file review, non-executable in v1.
- `external_provider_execution`: critical risk, provider permission check, non-executable in v1.

Verified validation behavior:

- missing required confirmations return structured validation errors;
- risk mismatches return structured validation errors;
- protected paths are flagged and require protected file review;
- secret-like payload assignment values are rejected or invalidated;
- invalid/unknown actions are rejected by Pydantic enum validation;
- validation returns `WorkflowApprovalValidationResult` and has no side effects.

## Consistency with workflow policy

Verified `backend/src/orchestrator/workflow_policy.py` remains consistent:

- only direct safe actions can be auto-runnable in Guided/Safe Prep:
  - `auto_gather_context`
  - `build_context_bundle`
  - `create_patch_draft`
- proposal/apply/tests/analyze/rollback remain manual-only or future approval-gated;
- external provider execution remains blocked/critical;
- shell and auto apply/run/analyze/rollback boundaries remain blocked.

Additional assertion confirmed the Safe Prep auto-runnable set is exactly:

```text
auto_gather_context, build_context_bundle, create_patch_draft
```

## Safety boundaries

Confirmed:

- no DB implementation;
- no DB migrations;
- no `database.py` edits;
- no `routes.py` edits;
- no API endpoint implementation;
- no project creation;
- no run creation;
- no tool_calls;
- no tools execution;
- no provider/LLM calls;
- no patch proposal execution;
- no apply patch execution;
- no test execution from approval contract;
- no analyze execution;
- no rollback execution;
- no shell runner;
- no autonomous mode;
- no git commit.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | None | No issues found. | No fix needed. |

## Changes made

No source-code changes.

Created report only:

- `runs/approval-request-regression-v1/final-report.md`

## Recommended next slice

Recommended next slice: `Approval Request UI/Storage Decision v1`.

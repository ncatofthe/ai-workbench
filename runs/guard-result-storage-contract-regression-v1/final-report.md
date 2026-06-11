# Guard Result Storage Contract Regression Pass v1

## Summary

The Guard Result Storage Contract layer is stable.

No P0/P1 issues were found. No source-code changes were made in this regression pass. The contract remains a pure storage-facing model/helper layer with no DB wiring, no routes, no runtime behavior changes, and no execution behavior.

## Module purity validation

Validated `backend/src/orchestrator/guard_result_storage_contract.py`.

Allowed imports only:

- `enum`
- `hashlib`
- `datetime`
- `typing.Optional`
- `pydantic.BaseModel`
- `pydantic.Field`

Confirmed absent:

- no `database.py` import;
- no `routes.py` import;
- no `engine.py` import;
- no `project_tools.py` import;
- no provider import;
- no frontend import;
- no `create_tool_call`;
- no `execute_run`;
- no patch/apply/test/analyze/rollback execution.

## Hash safety validation

Validated:

- `WorkflowGuardInputSnapshot` stores `old_text_hash`, not raw `old_text`.
- `WorkflowGuardInputSnapshot` stores `new_text_hash`, not raw `new_text`.
- `hash_guard_text(None)` returns `None`.
- `hash_guard_text("")` returns a deterministic SHA-256 hash for an empty string.
- `input_hash` includes:
  - proposed action;
  - file path;
  - patch summary;
  - old text hash;
  - new text hash.
- `input_hash` changes when important inputs change.

Existing tests cover raw text omission, deterministic hashes, and file-path-driven input hash changes. The `None` vs empty string behavior is explicit in implementation and validated by inspection in this pass.

## Snapshot/hash validation

Requirement context snapshot:

- `context_hash` includes:
  - requirement ids;
  - coverage status;
  - drift risk;
  - acceptance criteria;
  - constraints;
  - forbidden changes;
  - validation notes;
  - source-of-truth summary.
- Requirement id changes are covered by tests.
- Other context fields are included in the deterministic hash construction by inspection.

Result snapshot:

- `result_hash` includes:
  - decision;
  - drift risk;
  - matched requirement ids;
  - violated constraints;
  - forbidden change hits;
  - warnings;
  - reasons;
  - recommended next step.
- Decision changes are covered by tests.
- Other result fields are included in the deterministic hash construction by inspection.

## Stale detection validation

Validated `compare_guard_input_to_patch_payload` catches:

- file path mismatch;
- proposed action mismatch;
- patch summary mismatch;
- old text hash mismatch;
- new text hash mismatch;
- already stale record;
- expired record;
- overall proposal payload mismatch through `input_hash`.

Validated `compare_guard_requirement_context` catches:

- requirement context hash mismatch;
- requirement id mismatch through context hash;
- source-of-truth and coverage-context changes when represented by context hash.

## Proposal usability validation

Validated `is_guard_result_usable_for_proposal`:

- blocked record is never usable;
- `no_guard_override` does not make blocked guard usable;
- warning record requires `warning_acknowledged=true`;
- allowed non-stale record is usable;
- stale allowed record is not usable;
- expired allowed record is not usable;
- missing/empty requirement context can be usable only when represented as acknowledged warning.

## Serialization validation

Validated:

- `WorkflowGuardResultRecord` serializes/deserializes through Pydantic.
- Enum fields restore as enum values.
- `datetime` fields are accepted and serialize safely through model dump/validation.
- Optional proposal/apply links are modeled:
  - `proposal_tool_call_id`;
  - `apply_tool_call_id`;
  - `WorkflowGuardProposalLink`.

## Compatibility notes with current guard endpoint

Current guard endpoint response can be mapped conceptually without runtime changes:

- `StepSourceOfTruthGuardRequest`
  - maps to `WorkflowGuardInputSnapshot`;
  - raw `old_text` / `new_text` would become hashes only.
- `RunStepRequirementContext`
  - maps to `WorkflowGuardRequirementContextSnapshot`;
  - fields align directly except `parse_warnings`, which can fit validation notes or future result warnings depending on product choice.
- `StepSourceOfTruthGuardResult`
  - maps to `WorkflowGuardResultSnapshot`;
  - decision values align: `allowed`, `warning`, `blocked`;
  - drift risk values align with `low`, `medium`, `high`, `critical`.

No runtime mapping was implemented.

## Safety boundary validation

Confirmed:

- no endpoint writes;
- no guard results persisted yet;
- no proposal changes;
- no apply changes;
- no approval execution changes;
- no frontend changes;
- no DB schema changes;
- no migrations;
- no tool calls;
- no tools/providers execution;
- no autonomous mode.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | - | No P0/P1/P2/P3 issues found in this pass. | - |

## Changes made

No source-code changes.

## Files changed

- `runs/guard-result-storage-contract-regression-v1/final-report.md`

## database.py / routes.py

- `backend/src/storage/database.py` touched in this pass: no.
- `backend/src/api/routes.py` touched in this pass: no.

The working tree already contains unrelated/pre-existing source diffs from prior accepted slices. They were preserved and not modified.

## Exact checks/results

| Check | Result | Notes |
| --- | --- | --- |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q tests/test_guard_result_storage_contract.py` | Passed | `19 passed, 7 subtests passed`. |
| `cd backend && .venv/bin/pytest -q` | Passed | `461 passed, 31 subtests passed`. |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `461 passed, 31 subtests passed`. |

## Recommended next slice

Guard Result API Contract v1.

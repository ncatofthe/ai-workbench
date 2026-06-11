# Guard Result Storage Contract v1

## Summary

Added a pure storage-facing contract layer for future persisted Source-of-Truth Guard results.

This slice does not wire storage into runtime, does not add DB tables, does not add endpoints, and does not change guard/proposal/apply behavior. The contract models describe a future immutable `WorkflowGuardResult` audit entity that can later link guard checks to patch proposals and apply audit records.

## Contract file path

- `backend/src/orchestrator/guard_result_storage_contract.py`

This path was chosen because the Source-of-Truth Guard parser/evaluator currently lives in the orchestrator/intake area, while this contract is about requirement-context guard results rather than approval execution.

## Models added

- `WorkflowGuardInputSnapshot`
- `WorkflowGuardRequirementContextSnapshot`
- `WorkflowGuardResultSnapshot`
- `WorkflowGuardResultRecord`
- `WorkflowGuardProposalLink`
- `WorkflowGuardInputComparisonResult`

## Enums added

- `WorkflowGuardDecision`
  - `allowed`
  - `warning`
  - `blocked`
- `WorkflowGuardDriftRisk`
  - `low`
  - `medium`
  - `high`
  - `critical`
- `WorkflowGuardStaleReason`
  - `patch_form_changed`
  - `file_path_changed`
  - `proposed_action_changed`
  - `patch_summary_changed`
  - `old_text_changed`
  - `new_text_changed`
  - `requirement_context_changed`
  - `source_of_truth_changed`
  - `coverage_changed`
  - `expired`
  - `proposal_payload_mismatch`
  - `manual_invalidation`
- `WorkflowGuardSource`
  - `run_step_guard`
  - `patch_proposal_gate`
  - `manual_check`
  - `future_automation`

## Helper functions added

- `hash_guard_text`
- `build_guard_input_snapshot`
- `build_requirement_context_snapshot`
- `build_guard_result_snapshot`
- `build_workflow_guard_result_record`
- `mark_guard_result_stale`
- `compare_guard_input_to_patch_payload`
- `compare_guard_requirement_context`
- `is_guard_result_usable_for_proposal`

## Staleness rules

Pure stale detection flags a guard result as stale when:

- `file_path` differs;
- `proposed_action` differs;
- `patch_summary` differs;
- `old_text_hash` differs;
- `new_text_hash` differs;
- `input_hash` differs from the future proposal payload snapshot;
- requirement context hash differs;
- record is already marked stale;
- record is expired.

`old_text` and `new_text` are never stored raw in the input snapshot; only SHA-256 hashes are retained.

## Proposal usability rules

`is_guard_result_usable_for_proposal(record)` returns:

- `false` for stale records;
- `false` for expired records;
- `false` for `blocked`;
- `false` for `warning` unless `warning_acknowledged=true`;
- `true` for fresh `allowed`;
- `true` for fresh acknowledged `warning`;
- `false` for blocked records even when `no_guard_override=true`.

## Safety guarantees

- No DB schema changes.
- No migrations.
- No `database.py` edits.
- No `routes.py` edits.
- No endpoint changes.
- No runtime behavior changes.
- No tool calls.
- No tools/providers execution.
- No patch/proposal/apply/tests/analyze/rollback execution.
- No shell runner.
- No autonomous mode.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.

The new module does not import database, routes, engine, project tools, providers, or frontend code.

## Tests

Added `backend/tests/test_guard_result_storage_contract.py`.

Coverage includes:

- snapshots hash `old_text`/`new_text` instead of storing raw text;
- input snapshot hash changes when `file_path` changes;
- requirement context hash changes when requirement ids change;
- result hash changes when decision changes;
- stale detection catches file path mismatch;
- stale detection catches patch summary mismatch;
- stale detection catches old/new text mismatch;
- stale detection catches requirement context mismatch;
- expired record is stale;
- blocked record is not usable;
- warning record requires acknowledgement;
- allowed non-stale record is usable;
- `no_guard_override` does not override blocked guard;
- empty requirement context can be usable only as acknowledged warning;
- Pydantic serialization/deserialization works;
- module purity checks for no database/routes/provider/tool imports;
- helper functions are deterministic.

## Files changed

- `backend/src/orchestrator/guard_result_storage_contract.py`
- `backend/tests/test_guard_result_storage_contract.py`
- `runs/guard-result-storage-contract-v1/final-report.md`

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q tests/test_guard_result_storage_contract.py` | Passed | `19 passed, 7 subtests passed`. |
| `cd backend && .venv/bin/python -m py_compile src/orchestrator/guard_result_storage_contract.py` | Passed | Contract module compiles. |
| `cd backend && .venv/bin/pytest -q` | Passed | `461 passed, 31 subtests passed`. |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `461 passed, 31 subtests passed`. |

## database.py / routes.py

- `backend/src/storage/database.py` touched in this slice: no.
- `backend/src/api/routes.py` touched in this slice: no.

The working tree already contains unrelated/pre-existing source diffs from prior accepted slices. They were preserved and not modified.

## Remaining gaps

- No DB table or storage helper exists yet.
- No guard result API contract exists yet.
- Runtime guard endpoint still returns non-persisted results.
- Patch proposal creation does not yet accept `guard_result_id`.
- Approval requests do not yet include guard result snapshots.

## Recommended next slice

Guard Result Storage Contract Regression Pass v1.

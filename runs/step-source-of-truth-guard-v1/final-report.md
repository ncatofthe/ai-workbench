# Step Source-of-Truth Guard v1

## Summary

Added a deterministic read-only source-of-truth guard for RunSteps.

The guard parses the `AI_WORKBENCH_REQUIREMENT_CONTEXT` block from `RunStep.input` and evaluates a proposed action / patch summary against the confirmed requirement metadata. It returns a guard result only; it does not execute, create, apply, or persist anything.

## Parser behavior

Added:

- `parse_run_step_requirement_context(step_input: str)`

It parses:

- `requirement_ids`
- `coverage_status`
- `drift_risk`
- `acceptance_criteria`
- `constraints`
- `forbidden_changes`
- `validation_notes`
- `source_of_truth_summary`
- `parse_warnings`

Parser tolerance:

- extra text before/after the metadata block;
- empty lists such as `requirement_ids: []`;
- missing optional sections;
- unknown/malformed lines are reported as parse warnings.

If the block is missing, it returns empty fields and:

```text
AI_WORKBENCH_REQUIREMENT_CONTEXT block not found
```

## Guard rules

Added:

- `evaluate_step_source_of_truth_guard(...)`

Decision values:

- `allowed`
- `warning`
- `blocked`

Deterministic behavior:

- missing context -> `warning`, high drift risk;
- unlinked step context -> `warning`, high drift risk;
- forbidden/protected target mention -> `blocked`, high/critical drift risk;
- constraint overlap plus change-like intent -> `warning`;
- no meaningful requirement/source overlap -> `warning`;
- critical context drift -> `warning` for clearly read-only actions, otherwise `blocked`;
- read-only/review/check/analyze actions are generally allowed unless forbidden targets are hit.

The guard never auto-approves patch application. It only returns a result.

## Endpoint behavior

Added read-only endpoint:

- `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard`

Request fields:

- `proposed_action`
- optional `file_path`
- optional `patch_summary`
- optional `old_text`
- optional `new_text`

Response includes:

- `run_id`
- `step_id`
- `has_requirement_context`
- `parsed_context`
- `guard_result`

Endpoint behavior:

- reads the run;
- reads steps with `list_run_steps(run_id)`;
- verifies the step belongs to the run;
- parses `RunStep.input`;
- evaluates the guard;
- returns the result.

## Frontend behavior

No frontend UI was added in this slice. This keeps the slice small and avoids changing `RunDetail.tsx`.

Recommended follow-up: `RunDetail Source-of-Truth Guard UI v1`.

## Safety guarantees

- No DB schema changes.
- No migrations.
- No `database.py` edits.
- No automatic execution.
- No tools execution.
- No provider/LLM calls.
- No tool_calls creation.
- No patch/proposal/apply/tests/analyze/rollback.
- No shell runner.
- No autonomous mode.
- Existing Start Task flow unchanged.
- Existing confirmed-run flow remains pending-only.

## Tests

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
  - passed
- `backend/.venv/bin/pytest -q tests/test_confirmed_run.py`
  - `26 passed`
- `backend/.venv/bin/pytest -q tests/test_project_intake.py::TestBuildConfirmedPlanRunPreview`
  - `10 passed`
- `backend/.venv/bin/pytest -q`
  - `442 passed, 24 subtests passed`
- `frontend/npx tsc --noEmit`
  - passed
- `frontend/npm run build`
  - passed
- `bash scripts/run_tests.sh`
  - passed, including `442 passed, 24 subtests passed`

## Files changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_confirmed_run.py`
- `runs/step-source-of-truth-guard-v1/final-report.md`

## database.py / routes.py

- `backend/src/storage/database.py`: not touched.
- `backend/src/api/routes.py`: touched to add the read-only source-of-truth guard endpoint and imports.

## Remaining gaps

- No RunDetail UI for invoking the guard yet.
- Guard is advisory and does not gate patch proposal/apply flows yet.
- Requirement matching is deterministic/simple and may need refinement with real project usage.
- No structured persistence for guard decisions.
- No approval integration yet.

## Recommended next slice

RunDetail Source-of-Truth Guard UI v1

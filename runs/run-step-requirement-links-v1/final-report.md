# Run Step Requirement Links v1

## Summary

Added deterministic requirement/source-of-truth metadata to every `RunStep.input` created by:

- `POST /api/project-intake/confirmed-run`

The metadata is stored in the existing step input text field. No database schema changes were made.

## Exact metadata block format

Linked step format:

```text
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids:
- REQ-1
coverage_status: covered
drift_risk: low
acceptance_criteria:
- Requirements clarification has reviewed deliverables and a verification path.
constraints: []
forbidden_changes: []
validation_notes:
- Ready.
- REQ-1: Linked by source refs or keyword overlap.
source_of_truth_summary: Unnamed project from new_idea: <product goal>. <counts...>
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
```

Unlinked step format:

```text
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids: []
coverage_status: unlinked
drift_risk: medium
acceptance_criteria: []
constraints:
- <constraint title>
forbidden_changes:
- <forbidden path>
validation_notes:
- No requirement link found for this step.
source_of_truth_summary: Unnamed project from existing_project: <product goal>. <counts...>
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
```

## Backend behavior

- Added pure helper:
  - `format_confirmed_run_step_requirement_context(...)`
- The helper uses real existing model fields only:
  - `ConfirmedRunStepPreview.required_requirement_ids`
  - `ConfirmedRunStepPreview.coverage_status`
  - `ConfirmedRunStepPreview.drift_risk`
  - `ConfirmedRunStepPreview.validation_notes`
  - `ProjectSourceOfTruthContract.requirements`
  - `ProjectSourceOfTruthContract.acceptance_criteria`
  - `ProjectSourceOfTruthContract.constraints`
  - `ProjectSourceOfTruthContract.forbidden_changes`
  - `RequirementCoveragePreviewResponse.items`
- `POST /api/project-intake/confirmed-run` now builds the same deterministic source-of-truth and coverage previews, then prefixes each persisted step input with the metadata block after the human-readable step description.
- Existing rich bracket metadata remains preserved.
- Run and RunSteps remain `pending`.

## Safety guarantees

- No DB schema changes.
- No migrations.
- No `database.py` edits.
- No automatic execution.
- No `execute_run`.
- No `asyncio.create_task`.
- No tool/provider calls.
- No tool_calls creation.
- No patch/apply/test/analyze/rollback execution.
- No Start Task changes.
- No git commit.

## Tests

- `backend/.venv/bin/python -m py_compile src/storage/database.py`
  - passed
- `backend/.venv/bin/pytest -q tests/test_confirmed_run.py`
  - `14 passed`
- `backend/.venv/bin/pytest -q tests/test_project_intake.py::TestBuildConfirmedPlanRunPreview`
  - `10 passed`
- `backend/.venv/bin/pytest -q`
  - `430 passed, 24 subtests passed`
- `frontend/npx tsc --noEmit`
  - passed
- `frontend/npm run build`
  - passed
- `bash scripts/run_tests.sh`
  - passed, including `430 passed, 24 subtests passed`

## Files changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_confirmed_run.py`
- `runs/run-step-requirement-links-v1/final-report.md`

## database.py / routes.py

- `backend/src/storage/database.py`: not touched.
- `backend/src/api/routes.py`: touched only to construct source/coverage previews and add the formatted requirement context to `RunStep.input` before `create_run_step`.

## Remaining gaps

- Requirement links are stored as text metadata, not structured DB columns.
- No requirement-link editor exists yet.
- Confirmed plan execution remains future work.
- No approval-gated execution is implemented here.
- No automatic verification of requirement coverage at execution time.

## Recommended next slice

Confirmed Run Requirement Context Regression Pass v1

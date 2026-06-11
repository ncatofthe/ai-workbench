# Source of Truth Builder from Intake v1

## Summary

Added a deterministic read-only Source of Truth preview flow:

`idea + intake analysis + brief draft + plan preview -> ProjectSourceOfTruthContract preview`

The preview does not persist data, create projects/runs/tool calls, execute tools, call providers, scan files, or change the existing Start Task payload.

## Backend behavior

- Added `SourceOfTruthPreviewRequest` and `SourceOfTruthPreviewResponse`.
- Added `build_source_of_truth_from_intake(...)` in `backend/src/orchestrator/project_intake.py`.
- Added read-only endpoint:
  - `POST /api/project-intake/source-of-truth-preview`
- The builder reuses existing deterministic helpers:
  - `analyze_project_intake`
  - `draft_project_brief`
  - `draft_development_plan`
- The response includes:
  - `ProjectSourceOfTruthContract`
  - validation result
  - requirement coverage matrix
  - summary
  - recommended next step
  - ready-to-plan signal

## Frontend behavior

- Added API/types for source-of-truth preview.
- Added `Preview source of truth` button in the existing NewTask Project Intake block.
- Added a simple preview panel showing:
  - mission/product goal
  - source type
  - target users and roles
  - must/should/could requirements
  - constraints and forbidden changes
  - acceptance criteria
  - assumptions and open questions
  - anti-drift rules
  - validation gaps/warnings
  - requirement coverage summary
- The Start Task payload remains unchanged.

## Source of Truth mapping rules

- New idea input maps to `new_idea`.
- Existing project input maps to `existing_project`.
- Document-like text maps to `client_spec` or `commercial_proposal` when matching ТЗ/КП/spec/proposal wording.
- Plan phases become requirements and acceptance criteria.
- Existing project previews add preservation constraints:
  - preserve stack unless approved;
  - do not touch `.env`/secret files;
  - avoid architecture rewrites without approval;
  - prefer incremental patches;
  - validate commands before future execution.
- Anti-drift rules include preserving the product goal, avoiding unrelated features, preserving target users/roles, and requiring requirement links for future plan steps.

## Safety guarantees

- No DB writes.
- No DB migrations.
- No `database.py` edits.
- No project creation.
- No run creation.
- No assigned team creation.
- No tool_calls creation.
- No tools execution.
- No provider/LLM calls.
- No file scanning.
- No patch/proposal/apply/tests/analyze/rollback execution.
- No autonomous mode.
- No Start Task payload change.

## Source changes

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_project_intake.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/source-of-truth-builder-from-intake-v1/final-report.md`

## Tests

- Targeted backend test:
  - `backend/.venv/bin/python -m pytest tests/test_project_intake.py -q`
  - Result: `50 passed, 1 warning, 7 subtests passed`
- Backend:
  - `backend/.venv/bin/python -m py_compile src/storage/database.py`
  - `backend/.venv/bin/pytest -q`
  - Result: `399 passed, 24 subtests passed`
- Frontend:
  - `npx tsc --noEmit`
  - `npm run build`
  - Result: passed
- Root:
  - `bash scripts/run_tests.sh`
  - Result: passed, including `399 passed, 24 subtests passed`

## Remaining gaps

- Source of Truth preview is not persisted.
- No editor/confirmation flow for Source of Truth yet.
- Source of Truth is not attached to project/run.
- Requirement coverage is preview-only and not enforced during execution.
- Future plan/run steps do not yet carry requirement links.
- No existing project scan.
- No autonomous mode.

## Recommended next slice

Source of Truth Regression Pass v1

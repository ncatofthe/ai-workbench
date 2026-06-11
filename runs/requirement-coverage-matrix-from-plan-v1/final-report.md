# Requirement Coverage Matrix from Plan v1

## Summary

Added a deterministic read-only requirement coverage preview:

`Source of Truth + plan preview -> coverage matrix`

The feature is preview-only. It does not persist requirements, create projects/runs/tool calls, execute tools/providers, scan files, or change the Start Task payload.

## Backend behavior

- Added pure coverage preview models in `backend/src/orchestrator/project_intake.py`:
  - `RequirementCoveragePreviewRequest`
  - `RequirementCoveragePreviewResponse`
  - `RequirementCoveragePreviewSummary`
  - `RequirementCoveragePreviewItem`
  - `UnlinkedPlanPhasePreviewItem`
- Added deterministic helper:
  - `build_requirement_coverage_from_plan(...)`
- Added read-only endpoint:
  - `POST /api/project-intake/coverage-preview`
- The builder can use provided `source_of_truth` / `plan_preview`, or rebuild deterministic intake/brief/plan/source-of-truth previews from the same base request.

## Frontend behavior

- Added frontend types for coverage preview request/response.
- Added API client method:
  - `previewRequirementCoverage(...)`
- Added `Preview coverage` button in the NewTask Project Intake block.
- Added a simple result panel showing:
  - coverage counts;
  - covered/partial/missing/unclear requirements;
  - unlinked plan phases;
  - drift risks;
  - recommended next step.
- Start Task payload remains unchanged.

## Coverage rules

- Requirements are matched to plan phases using:
  - explicit phase id source refs/tags;
  - deterministic title/description/deliverable keyword overlap.
- Coverage statuses:
  - `covered`
  - `partially_covered`
  - `missing`
  - `unclear`
- Missing mandatory requirements are marked high drift risk.
- Plan phases with no requirement link are marked medium/high drift risk.
- Plan phases touching forbidden/protected boundaries are marked critical drift risk.
- Existing project constraints remain advisory and preview-only.

## Safety guarantees

- No DB writes.
- No migrations.
- No `database.py` edits.
- No project creation.
- No run creation.
- No tool_calls creation.
- No assigned team creation.
- No tools execution.
- No providers/LLM calls.
- No file scanning.
- No patch/proposal/apply/tests/analyze/rollback.
- No autonomous mode.
- No Start Task payload change.

## Source changes

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_project_intake.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/requirement-coverage-matrix-from-plan-v1/final-report.md`

## Tests

- Targeted backend test:
  - `backend/.venv/bin/python -m pytest tests/test_project_intake.py -q`
  - Result: `57 passed, 1 warning, 7 subtests passed`
- Backend:
  - `backend/.venv/bin/python -m py_compile src/storage/database.py`
  - `backend/.venv/bin/pytest -q`
  - Result: `406 passed, 24 subtests passed`
- Frontend:
  - `npx tsc --noEmit`
  - `npm run build`
  - Result: passed
- Root:
  - `bash scripts/run_tests.sh`
  - Result: passed, including `406 passed, 24 subtests passed`

## Remaining gaps

- Coverage preview is not persisted.
- Coverage is not attached to project/run.
- Requirement links are not editable yet.
- Future run steps do not yet carry confirmed requirement links.
- Coverage is not enforced by orchestrator execution.
- Existing project scan is still not implemented.
- No autonomous mode.

## Recommended next slice

Source of Truth / Coverage Regression Pass v1

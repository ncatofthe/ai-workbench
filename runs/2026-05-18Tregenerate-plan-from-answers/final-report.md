# Regenerate Plan From Answers

## Summary

Run Detail can now regenerate `plan.md` after clarification answers are saved.

## Changes

- `backend/src/api/routes.py`
  - Added `POST /api/runs/{run_id}/regenerate-plan`.
  - Reads `product-spec.md`, `clarification-questions.md`, and `clarification-answers.md`.
  - Requires saved clarification answers.
  - Uses Ollama when available, with a fallback regenerated plan when offline.
  - Updates `plan.md`, `final-report.md`, `run.plan`, and `run.result`.
  - Adds a timeline step: `Regenerate plan from clarification answers`.
- `backend/tests/test_run_artifacts.py`
  - Added fallback regeneration coverage.
  - Added missing-answers rejection coverage.
- `frontend/src/types/index.ts`
  - Added `RegeneratePlanResult`.
- `frontend/src/api/client.ts`
  - Added `regeneratePlan(...)`.
- `frontend/src/pages/RunDetail.tsx`
  - Added `Regenerate Plan From Answers` button on the Questions tab after answers exist.
  - Refreshes run, steps, and artifacts after regeneration.
  - Switches to the Plan tab after successful regeneration.

## Verification

- `python3 -m py_compile backend/src/api/routes.py backend/tests/test_run_artifacts.py` passed.
- `.venv/bin/python -m pytest -q tests/test_run_artifacts.py tests/test_run_steps.py tests/test_cancellation.py` passed: 8 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed: 21 backend tests.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Regeneration updates the plan, but does not yet start implementation.
- The regenerated plan is still a Markdown artifact, not parsed into executable task records.
- There is not yet a dedicated architecture/task-breakdown artifact stage after regeneration.

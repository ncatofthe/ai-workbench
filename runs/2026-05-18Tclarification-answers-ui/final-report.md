# Clarification Answers UI

## Summary

Run Detail now exposes generated product artifacts and lets the user save clarification answers back into the run.

## Changes

- `backend/src/models.py`
  - Added `ClarificationAnswerRequest`.
- `backend/src/api/routes.py`
  - Added `GET /api/runs/{run_id}/artifacts/{artifact_name}`.
  - Added `POST /api/runs/{run_id}/clarifications`.
  - Artifact reads are scoped to the run directory and reject path traversal.
  - Clarification answers are saved as `clarification-answers.md`.
  - Saving answers appends the artifact, logs the action, and creates a completed `Record clarification answers` run step.
- `backend/tests/test_run_artifacts.py`
  - Added artifact read test.
  - Added path escape rejection test.
  - Added clarification answers persistence test.
- `frontend/src/types/index.ts`
  - Added `RunArtifact` and `ClarificationAnswerResult`.
- `frontend/src/api/client.ts`
  - Added `getRunArtifact(...)`.
  - Added `submitClarifications(...)`.
- `frontend/src/pages/RunDetail.tsx`
  - Added `Spec` tab.
  - Added `Questions` tab.
  - Loads `product-spec.md`, `clarification-questions.md`, and `clarification-answers.md`.
  - Adds an answer form that saves clarification answers and refreshes run steps.

## Verification

- `python3 -m py_compile backend/src/models.py backend/src/api/routes.py backend/tests/test_run_artifacts.py` passed.
- `.venv/bin/python -m pytest -q tests/test_run_artifacts.py tests/test_run_steps.py tests/test_cancellation.py` passed: 6 tests.
- `npx tsc --noEmit` passed.
- `bash scripts/run_tests.sh` passed: 19 backend tests.
- `npm run build` passed.
- `git diff --check` passed.

## Remaining limitations

- Saving answers does not yet regenerate the plan automatically.
- There is no explicit paused/waiting-for-clarification run state yet.
- The UI shows markdown as plain text for now.

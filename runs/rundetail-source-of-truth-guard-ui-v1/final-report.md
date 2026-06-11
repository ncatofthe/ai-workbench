# RunDetail Source-of-Truth Guard UI v1

## Summary

Added a minimal RunDetail UI for the existing read-only Step Source-of-Truth Guard endpoint.

The UI lets the user manually enter a proposed action / patch summary for a step and click a button to check it against the backend guard. It does not auto-run, create patch proposals, apply patches, run commands/tests, call providers, or mutate run/step state.

## UI placement

The UI was added inside `StepPatchSection` in `frontend/src/pages/RunDetail.tsx`, near the existing Step Patch Tools flow and before the patch review/preview/apply controls.

The block includes:

- proposed action / patch summary textarea;
- `Check source-of-truth guard` button;
- loading state;
- error state;
- result panel with decision, drift risk, matched requirements, violated constraints, forbidden hits, warnings, reasons, parsed requirement ids, and recommended next step.

## API client/types added

Added frontend types:

- `RunStepRequirementContext`
- `StepSourceOfTruthGuardDecision`
- `StepSourceOfTruthGuardRequest`
- `StepSourceOfTruthGuardResult`
- `StepSourceOfTruthGuardResponse`

Added API client method:

- `checkStepSourceOfTruthGuard(runId, stepId, payload)`

Endpoint used:

- `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard`

## Safety guarantees

- Guard only runs when the user clicks the button.
- No automatic guard execution.
- No patch proposal creation.
- No patch apply.
- No test/command execution.
- No provider/LLM calls.
- No tool_calls creation.
- No shell runner.
- No autonomous mode.
- Existing patch workflow behavior unchanged.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.

## Files changed

- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/rundetail-source-of-truth-guard-ui-v1/final-report.md`

## Backend / database.py / routes.py

- Backend source touched in this slice: no.
- `backend/src/storage/database.py` touched in this slice: no.
- `backend/src/api/routes.py` touched in this slice: no.

Note: the working tree was already dirty from previous accepted slices, including backend changes from earlier tasks. This slice did not add backend changes.

## Tests/checks

- Frontend:
  - `npx tsc --noEmit`: passed
  - `npm run build`: passed
- Backend:
  - `.venv/bin/python -m py_compile src/storage/database.py`: passed
  - `.venv/bin/pytest -q`: `442 passed, 24 subtests passed`
- Root:
  - `bash scripts/run_tests.sh`: passed, including `442 passed, 24 subtests passed`

## Remaining gaps

- Guard result is advisory only.
- Guard is not yet wired into patch proposal creation as a gate.
- Guard result is not persisted.
- No dedicated RunDetail component extraction was done.

## Recommended next slice

Guard-gated Patch Proposal v1

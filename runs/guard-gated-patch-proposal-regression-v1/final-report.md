# Guard-gated Patch Proposal Regression Pass v1

## Summary

The Guard-gated Patch Proposal flow is stable after one small P1 frontend state fix.

The gate correctly keeps patch proposal creation tied to the latest Source-of-Truth Guard result or an explicit user override/acknowledgement. The guard remains manual and read-only. Patch proposal, review, apply, rollback, tests, and analysis behavior were not changed.

## Gate behavior validation

| Scenario | Result | Notes |
| --- | --- | --- |
| Not checked | Passed | "Preview Patch" is disabled until the user explicitly checks "Create proposal without guard check". |
| Allowed | Passed | A guard decision of `allowed` permits normal proposal preview without extra acknowledgement. |
| Warning | Passed | A guard decision of `warning` requires the explicit warning acknowledgement checkbox before proposal preview. |
| Blocked | Passed | A guard decision of `blocked` keeps proposal preview disabled. No blocked override exists. |
| Stale guard after manual form edits | Passed | Editing patch form fields clears guard result and acknowledgements. |
| Stale guard after prefill/draft fill | Fixed | External prefill and context draft prefill now also clear guard result and acknowledgements. |

## Source-of-truth guard UI validation

- Guard is still triggered only by the "Check source-of-truth guard" button.
- Guard uses the existing endpoint: `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard`.
- Guard request uses the current proposed action/patch summary and current patch form fields.
- Guard does not create a proposal.
- Guard does not apply patches.
- Guard does not run commands or tests.
- Guard does not create tool calls.
- Guard result displays decision, drift risk, matched requirements, violated constraints, forbidden hits, warnings, reasons, and parsed requirement ids.

## Patch proposal flow validation

- Existing `proposeProjectPatch` call remains the same.
- Existing proposal payload remains unchanged:
  - `run_id`
  - `step_id`
  - `agent_id`
  - `operations: [patchOperationFromForm(form)]`
- Existing `reviewProjectPatch` flow remains unchanged and is not guard-gated.
- Existing manual `applyProjectPatch` flow remains unchanged and still requires the existing confirmation checkbox.
- Existing rollback/test/analyze UI was not modified.

## Existing RunDetail flow validation

- Patch workflow tab still renders through the existing RunDetail tab flow.
- Safe Prep mode remains limited to safe prep actions.
- Manual/Guided workflow behavior was not changed.
- Tool Calls panel and focus paths were not changed.
- Run-not-found UX was not changed.

## Backend safety validation

The guard endpoint remains read-only by inspection:

- Reads run and steps.
- Verifies the step belongs to the run.
- Parses `RunStep.input`.
- Evaluates the guard deterministically.
- Returns a structured response.

No backend changes were made in this pass. The endpoint does not call `execute_run`, does not schedule `asyncio.create_task`, does not create tool calls, does not apply patches, does not run commands/tests, and does not call providers/tools.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| P1 | RunDetail guard gate state | External patch-form prefill and context draft prefill could leave a previous guard result/acknowledgement attached to newly filled patch text. | Fixed by clearing guard result, no-guard override, warning acknowledgement, and guard error when either prefill path updates the patch form. |

No P0 issues found.

## Changes made

- Minimal P1 fix in `frontend/src/pages/RunDetail.tsx`:
  - clear stale guard state when `externalPrefill` populates the patch form;
  - clear stale guard state when `draftPrefill` populates the patch form.

No backend source-code changes.

## Files changed

- `frontend/src/pages/RunDetail.tsx`
- `runs/guard-gated-patch-proposal-regression-v1/final-report.md`

## Backend touched

- Backend source touched in this pass: no.
- `backend/src/storage/database.py` touched in this pass: no.
- `backend/src/api/routes.py` touched in this pass: no.

Note: the working tree already contains unrelated/pre-existing backend modifications. They were preserved and not modified.

## Exact checks/results

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q` | Passed | `442 passed, 24 subtests passed`. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `442 passed, 24 subtests passed`. |

## Recommended next slice

Guard Result Persistence/Audit Decision v1.

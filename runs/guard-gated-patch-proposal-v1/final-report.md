# Guard-gated Patch Proposal v1

## Summary

Connected the existing RunDetail Source-of-Truth Guard UI to the manual Step Patch Proposal flow.

Patch proposal creation is now visibly gated by the latest guard result for the step. This remains a frontend-only manual workflow guard: it does not run the guard automatically, does not create proposals automatically, does not apply patches, does not run tests, and does not change backend execution behavior.

## UI behavior

- Added a "Patch proposal guard status" block inside `StepPatchSection`, near the existing Source-of-Truth Guard and before patch proposal controls.
- The block shows the current guard state:
  - `not checked`
  - `allowed`
  - `warning`
  - `blocked`
- Added safety copy:
  - "Source-of-truth guard does not create or apply patches. It only checks whether the intended change matches the confirmed requirements."
- The existing "Preview Patch" action now checks the guard gate before creating a patch proposal.
- The patch proposal payload was not changed.
- The guard remains manual; clicking "Preview Patch" does not call the guard endpoint.

## Gate rules

| Guard state | Proposal behavior |
| --- | --- |
| Not checked | Shows warning and requires explicit "Create proposal without guard check" checkbox before proposal preview is enabled. |
| Allowed | Proposal preview works normally. |
| Warning | Shows warning details and requires explicit "I understand the guard warning and want to continue." checkbox before proposal preview is enabled. |
| Blocked | Proposal preview is disabled. No blocked override was added in this slice. |

The gate state is reset when the patch form or guard summary changes, so stale guard acknowledgements are not reused silently.

## Safety guarantees

- No backend runtime behavior changed.
- No database schema changes.
- No migrations.
- No automatic guard execution.
- No automatic patch proposal creation.
- No patch application.
- No test execution.
- No command execution.
- No provider or LLM calls.
- No tool calls created by the guard UI.
- No shell runner.
- No autonomous mode.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.

## Files changed

- `frontend/src/pages/RunDetail.tsx`
- `runs/guard-gated-patch-proposal-v1/final-report.md`

No backend files were edited for this slice. The working tree already contains unrelated/pre-existing backend modifications, including `backend/src/storage/database.py` and `backend/src/api/routes.py`; they were preserved and not modified here.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Production build completed successfully. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` still compiles. |
| `cd backend && .venv/bin/pytest -q` | Passed | `442 passed, 24 subtests passed`. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Full project script passed. |

## Backend touched

- Backend source touched in this slice: no.
- `backend/src/storage/database.py` touched in this slice: no.
- `backend/src/api/routes.py` touched in this slice: no.

## Remaining gaps

- Guard result is still local UI state only; it is not persisted or audited.
- Guard checks are not required by backend policy before proposal creation.
- Blocked override policy is intentionally not implemented.
- No automated frontend test coverage was added for the RunDetail gate.

## Recommended next slice

Guard-gated Patch Proposal Regression Pass v1.

# Guard Context to Patch Form Prefill v1

## Summary

Added a small manual RunDetail action that copies the latest checked Source-of-Truth Guard context into the existing patch proposal form context for the same RunStep.

This is a frontend-only workflow aid. It does not generate patch content, create a patch proposal, apply patches, run commands, call providers, or change backend behavior.

## UI behavior

- Added a "Use guard context in patch form" button near the Source-of-Truth Guard result panel.
- The button is shown only when:
  - a guard result exists;
  - the latest checked guard input has a proposed action / patch summary;
  - the guard decision is `allowed` or `warning`.
- For a `blocked` guard result, the UI shows:
  - "Blocked guard result cannot be used to prefill a patch proposal."
- The existing guard result panel and patch proposal gate remain unchanged.

## Prefill rules

The prefill action copies safe guard context only:

- If the latest checked guard input included `file_path`, that file path is copied into the existing patch form `file_path`.
- The existing issue/context banner is filled with:
  - proposed action;
  - guard decision;
  - drift risk;
  - matched requirement ids;
  - warnings;
  - reasons;
  - recommended next step.
- `old_text` is not generated or changed.
- `new_text` is not generated or changed.
- `create_if_missing` is not changed.
- `replace_all` is not changed.
- Existing `proposeProjectPatch` payload is unchanged.

## Stale guard prevention

- The latest checked guard input is captured only after the guard endpoint returns successfully.
- Editing the guard summary clears the guard result and captured guard context.
- Editing any patch form field clears the guard result and captured guard context.
- External patch prefill and context-draft prefill already clear guard result and acknowledgements.
- The guard result is preserved only when using the context derived from that exact latest checked guard input.
- The no-guard override is never enabled by prefill.
- Warning acknowledgement is cleared after prefill, so a warning guard still requires explicit acknowledgement before proposal preview.

## Gate behavior after prefill

- `allowed`: proposal preview remains available normally.
- `warning`: proposal preview still requires the warning acknowledgement checkbox.
- `blocked`: no prefill button is shown and proposal preview remains blocked.
- `not checked`: no prefill button is shown and proposal preview still requires explicit no-guard override.

## Safety guarantees

- No backend changes.
- No database schema changes.
- No migrations.
- No automatic guard execution.
- No automatic patch proposal creation.
- No patch generation.
- No patch application.
- No test execution.
- No command execution.
- No provider or LLM calls.
- No shell runner.
- No autonomous mode.
- Start Task flow unchanged.
- Confirmed-run behavior unchanged.

## Files changed

- `frontend/src/pages/RunDetail.tsx`
- `runs/guard-context-to-patch-form-prefill-v1/final-report.md`

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q` | Passed | `442 passed, 24 subtests passed`. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `442 passed, 24 subtests passed`. |

## Backend touched

- Backend source touched in this slice: no.
- `backend/src/storage/database.py` touched in this slice: no.
- `backend/src/api/routes.py` touched in this slice: no.

Note: the working tree already contains unrelated/pre-existing backend modifications. They were preserved and not modified.

## Remaining gaps

- Guard context prefill is local UI state only and is not persisted.
- Guard result is not audited or stored.
- Backend does not yet enforce guard checks before proposal creation.
- No automated frontend interaction test was added.

## Recommended next slice

Guard Context to Patch Form Prefill Regression Pass v1.

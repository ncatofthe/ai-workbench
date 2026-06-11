# Step Patch Draft -> Guarded Proposal Fastlane v1

## Summary

Implemented a controlled bridge from an agent-ready step patch draft to guarded patch proposal creation.

The new flow supports:
- read-only guarded proposal preflight from a step patch draft
- explicit operator-confirmed proposal creation
- fresh Source of Truth guard persistence on confirmed creation
- reuse of the existing guarded `propose-patch` path for proposal creation, module awareness, and module-aware policy classification
- RunDetail UI for exact operator patch fields, preflight, confirmation, and proposal result display

No patch is applied, no tests are run, no provider call is made, and no run execution is started by this slice.

## Why This Fastlane Block Exists

The product pipeline already reached:

intake -> confirmed pending run -> agent step context -> step agent patch draft

This slice connects the next operator-controlled step:

step agent patch draft -> guarded proposal creation

It keeps proposal creation explicit and guarded while preparing the platform for the later controlled apply/test fastlane.

## Backend Preflight Behavior

Added a pure preflight helper in `backend/src/orchestrator/project_intake.py`:

- validates the patch draft shape
- extracts operator-selected `file_path`, `old_text`, and `new_text`
- requires exact `old_text` before proposal creation
- blocks missing `file_path` or `new_text`
- blocks `provider_allowed=true`
- blocks non-pending steps
- blocks unsafe paths and secret-like patch fields
- warns on missing requirement/module/validation context
- returns operator-readable blockers, warnings, safety notes, and next action

Preflight does not persist a guard result, proposal, tool_call, or any other runtime state.

## Guarded Proposal Creation Behavior

Added:

`POST /api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal`

Behavior:
- `confirm_create_proposal=false`: preflight only, `created=false`
- `confirm_create_proposal=true`: validates preflight, persists one fresh Source of Truth guard result, then delegates to the existing guarded `propose-patch` endpoint logic
- warning guard decisions are acknowledged only through the explicit proposal confirmation path
- blocked guard decisions do not create a proposal
- proposal creation returns `proposal_id`, `guard_result_id`, `guard_decision`, module awareness, module policy, warnings, safety notes, and next action

The endpoint does not apply patches, run tests, call providers, start runs, create run steps, or execute commands.

## Guard / Module / Policy / Review Behavior

Source of Truth:
- confirmed creation persists a Source of Truth guard result before proposal creation
- the existing proposal guard validation still controls whether the proposal can be created
- blocked guards stop the proposal

Module awareness:
- proposal creation reuses the existing module-awareness path from `propose-patch`
- module awareness is returned when available

Module policy:
- proposal creation reuses the existing module-aware policy classification
- policy result is returned when available

Patch review:
- preflight returns a safe `patch_review` status of `not_run`
- this bridge intentionally does not run the file-reading patch review assistant
- the existing review/proposal/apply workflow remains available separately

## RunDetail UI Behavior

Updated `frontend/src/pages/RunDetail.tsx` in the Agent Step Context / patch draft panel:

- added "Preflight Guarded Proposal"
- added exact `file_path`, `old_text`, and `new_text` fields
- added explicit checkbox: "I confirm creating a patch proposal only. Do not apply patch."
- added "Create Guarded Proposal"
- displays guard decision, proposal id, blockers, warnings, module awareness, module policy, patch review, safety notes, and next recommended action
- success copy clearly states: "Proposal created. Patch was not applied. Tests were not run."

No hidden apply, test, provider, or create-run action was added.

## Safety Boundaries

Preserved:
- no DB schema changes
- no migrations
- no provider calls
- no network calls
- no shell/subprocess command execution
- no automatic `execute_run`
- no automatic run start
- no automatic patch proposal before explicit confirmation
- no patch apply
- no test execution
- no approval bypass
- no guard bypass
- no weakening of `apply confirm=true`

The only tool_call created by this slice occurs on the explicit confirmed creation path through the existing `propose-patch` behavior.

## Tests Added

Added:

`backend/tests/test_step_patch_draft_guarded_proposal_fastlane.py`

Coverage:
- preflight read-only behavior
- missing field blockers
- provider and step-status blockers
- confirmed proposal creation
- guard result creation/linking behavior through existing proposal path
- module awareness and module policy response
- no apply/test/provider/execution/run-step side effects
- bad run/step handling
- integration with the previous step patch draft endpoint
- RunDetail static UI safety checks
- static safety checks for forbidden runtime behavior

New test result:

`62 passed`

## Files Changed

Changed by this slice:
- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_step_patch_draft_guarded_proposal_fastlane.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/step-patch-draft-guarded-proposal-fastlane-v1/final-report.md`

Not changed by this slice:
- `backend/src/storage/database.py`
- `backend/src/orchestrator/engine.py`
- `backend/src/providers/*`
- `backend/src/project_tools.py`
- `scripts/run_tests.sh`

Note: the worktree already had broad pre-existing dirty/untracked state, including `database.py` and `engine.py`. They were not edited for this task.

## Exact Check Results

Backend compile:
- `.venv/bin/python -m py_compile src/orchestrator/project_intake.py src/api/routes.py src/models.py tests/test_step_patch_draft_guarded_proposal_fastlane.py` -> passed

New tests:
- `.venv/bin/pytest -q tests/test_step_patch_draft_guarded_proposal_fastlane.py` -> `62 passed in 1.14s`

Targeted compatibility:
- `.venv/bin/pytest -q tests/test_step_agent_patch_draft_fastlane.py tests/test_intake_run_agent_assignment_step_context.py tests/test_guarded_patch_proposal.py tests/test_guard_result_proposal_validation.py tests/test_guard_proposal_module_awareness.py` -> `160 passed in 2.10s`
- `.venv/bin/pytest -q tests/test_module_aware_guard_policy.py tests/test_apply_guard_revalidation.py tests/test_project_context_cockpit.py tests/test_semi_auto_operator_queue.py` -> `76 passed in 1.62s`

Full backend:
- `.venv/bin/pytest -q` -> `2121 passed, 38 subtests passed in 58.87s`

Frontend:
- `npx tsc --noEmit` -> passed
- `npm run build` -> passed
- `npm run test:e2e:smoke` -> `2 passed`

Root runner:
- `bash scripts/run_tests.sh` -> passed
  - backend syntax checks passed
  - backend pytest: `2121 passed, 38 subtests passed`
  - frontend checks completed

## P0/P1/P2/P3 Issues

P0: none found.

P1: none found.

P2:
- exact `old_text` still requires operator review or a future approved read-only context gathering step
- patch review assistant output is not executed by this bridge to avoid file reads in the draft-to-proposal endpoint

P3:
- RunDetail now has a larger Agent Step Context panel; a future UI pass could split it into subpanels once the controlled apply/test flow lands

## Known Limitations

- no patch is applied
- no tests are run
- no provider call is triggered
- exact `old_text` still needs operator review if not known
- no full autonomous patch/test/fix loop yet
- preflight patch review is intentionally marked `not_run`
- proposal creation still depends on the existing manual guarded proposal/apply workflow

## Recommended Next Slice

Recommended next slice:

Guarded Proposal -> Controlled Apply/Test Fastlane v1

Alternative:

Existing Project Read-only Repo Intake Fastlane v1

# Repo-aware Controlled Apply/Test/Fix Loop Mega-Fastlane v1 — Final Report

## Summary

Implemented the first read-only repo-aware controlled apply/test/fix loop plan for RunDetail.

The operator can now inspect a repo-aware pending step and see:

- current controlled loop stage
- next recommended manual action
- repo context status
- patch draft readiness/status
- guarded proposal readiness/status
- apply status
- safe test status
- test analysis status
- fix draft status
- delivery update status
- copy-only safe command suggestions

No apply/test/fix/proposal behavior is executed by the plan endpoint or UI panel.

## Why This Is a Mega-Fastlane Block

This block connects existing capabilities into one operator-visible loop without adding hidden autonomy:

repo-aware step context -> patch draft -> guarded proposal -> explicit apply -> explicit safe test -> analysis -> fix draft -> delivery update.

The implementation is a status/readiness layer over existing records and controls, not a new executor.

## Current Flow Before / After

Before:

- Repo-aware steps exposed context, patch draft, guarded proposal preflight, and copy-only command suggestions.
- The operator still had to infer overall apply/test/fix status from separate panels.

After:

- RunDetail includes a Controlled Apply/Test/Fix Loop panel per agent-ready step.
- The panel summarizes existing evidence and gives manual next-action descriptors.
- Existing explicit apply/test/fix/proposal paths remain separate.

## Controlled Loop Plan Endpoint Behavior

Added:

`GET /api/runs/{run_id}/steps/{step_id}/repo-aware-controlled-loop-plan`

Behavior:

- read-only
- loads existing run/step
- parses existing development and repo-aware context
- inspects existing tool_call and guard_result evidence
- returns deterministic stage status and next recommended action
- creates no tool_calls, proposals, guard results, files, patches, commands, provider calls, or run execution

## Stage Model Behavior

Stages returned in deterministic order:

1. `repo_context`
2. `patch_draft`
3. `guarded_proposal`
4. `apply_patch`
5. `safe_test`
6. `analyze_test_result`
7. `fix_draft`
8. `delivery_update`

Allowed statuses:

- `not_started`
- `ready`
- `blocked`
- `waiting_for_confirmation`
- `completed`
- `failed`
- `unknown`

Action kinds are descriptors only:

- `prepare_patch_draft`
- `run_guard_preflight`
- `create_guarded_proposal`
- `apply_patch_requires_confirm`
- `run_safe_test_requires_confirm`
- `analyze_test_result`
- `prepare_fix_draft`
- `update_delivery_report`

## RunDetail UI Behavior

RunDetail now shows a compact “Controlled Apply/Test/Fix Loop” panel inside Agent Step Context.

Controls added:

- Refresh loop plan
- Copy safe command suggestion
- Open Patch Draft section
- Open Guarded Proposal section
- Open Test Tools section

The panel does not call apply, test, proposal, provider, command, or fix endpoints automatically.

## Safe Command Copy-only Behavior

Safe commands are displayed as suggestions only.

Sources:

- repo-aware context `suggested_safe_commands`
- project profile `test_command`

Each suggestion is marked with `execution = copy_only_or_explicit_safe_runner`.

## Safety Boundaries

Preserved:

- No DB schema changes.
- No migrations.
- No provider calls.
- No network calls.
- No hidden create_tool_call.
- No hidden proposal creation.
- No hidden apply patch.
- No hidden test execution.
- No hidden fix generation.
- No auto-start.
- No rollback.
- No guard bypass.
- No approval bypass.
- No changes to `scripts/run_tests.sh`.

## Tests Added

Added:

- `backend/tests/test_repo_aware_controlled_apply_test_fix_loop_fastlane.py`

Coverage includes:

- endpoint happy path
- missing run/step
- invalid context tolerance
- read-only/no mutation guarantees
- stage status logic
- safe command suggestion behavior
- static route safety
- frontend static checks
- compatibility route availability

## Exact Check Results

Pre-work snapshot:

- Saved `runs/pre-repo-aware-controlled-apply-test-fix-loop-mega-fastlane-v1-working-tree.diff`

Backend compile:

- `.venv/bin/python -m py_compile src/orchestrator/project_intake.py`: passed
- `.venv/bin/python -m py_compile src/api/routes.py`: passed
- `.venv/bin/python -m py_compile src/models.py`: passed
- `.venv/bin/python -m py_compile tests/test_repo_aware_controlled_apply_test_fix_loop_fastlane.py`: passed

Backend targeted tests:

- `tests/test_repo_aware_controlled_apply_test_fix_loop_fastlane.py`: 53 passed
- `tests/test_repo_aware_agent_work_context_fastlane.py`: 57 passed
- `tests/test_existing_project_readonly_repo_intake_fastlane.py`: 33 passed
- `tests/test_confirmed_development_run_bridge_fastlane.py`: 52 passed
- `tests/test_step_agent_patch_draft_fastlane.py`: 58 passed
- `tests/test_step_patch_draft_guarded_proposal_fastlane.py`: 62 passed
- `tests/test_execute_next_step.py`: 3 passed

Full backend:

- `.venv/bin/pytest -q`: 2267 passed + 38 subtests

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root runner:

- `bash scripts/run_tests.sh`: passed
- Runner backend result: 2267 passed + 38 subtests
- Runner frontend TypeScript check: passed

## Files Changed

- `backend/src/api/routes.py`
- `backend/tests/test_repo_aware_controlled_apply_test_fix_loop_fastlane.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/pre-repo-aware-controlled-apply-test-fix-loop-mega-fastlane-v1-working-tree.diff`
- `runs/repo-aware-controlled-apply-test-fix-loop-mega-fastlane-v1/final-report.md`

## Protected Files

- `database.py` touched: No
- `engine.py` touched: No
- providers touched: No
- `project_tools.py` touched: No
- `model_router.py` touched: No
- `scripts/run_tests.sh` touched: No

## P0/P1/P2/P3 Issues

- P0: None found.
- P1: None found.
- P2: Loop plan is read-only status guidance; it does not yet persist patch draft/fix draft lifecycle artifacts.
- P3: Frontend build still emits the existing Vite large chunk warning.

## Known Limitations

- Loop plan is read-only/status guidance.
- No full autopilot yet.
- No hidden apply/test/fix.
- Safe commands are suggestions or existing explicit safe-runner inputs only.
- Provider-based coding is still not enabled.
- Parallel multi-agent execution is not implemented.
- Patch draft evidence is inferred from later guard/proposal/apply/test records because patch drafts are not persisted.

## Recommended Next Mega-Fastlane Block

Agent Result -> Controlled Fix Proposal Mega-Fastlane v1

Alternative:

Service Desk Real Project Dogfood Mega-Fastlane v1

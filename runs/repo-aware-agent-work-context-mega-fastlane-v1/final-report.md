# Repo-aware Agent Work Context Mega-Fastlane v1 — Final Report

## Summary

Implemented repo-aware context propagation from existing-project repo intake into confirmed pending development runs and downstream agent-prep surfaces.

The flow now supports:

- Existing Project repo intake preview attached to confirmed run creation.
- Bounded `AI_WORKBENCH_REPO_AWARE_CONTEXT` blocks embedded in created pending `RunStep.input`.
- Agent Step Context parsing and API exposure of repo-aware metadata.
- Step Agent Patch Draft responses carrying repo stack, area, manifest, test, protected-path, and copy-only command hints.
- Guarded proposal preflight surfacing repo warnings and validation suggestions without weakening guards.
- NewTask forwarding repo intake preview only during explicit confirmed pending run creation.
- RunDetail displaying repo-aware context and copy-only safe command suggestions.

No execution was added.

## Why This Is a Mega-Fastlane Block

This block stitches together several adjacent product/runtime surfaces in one milestone because repo-aware metadata is only useful if it flows from intake through run creation into step context, draft preparation, and guarded proposal preflight.

The implementation remains bounded and operator-controlled.

## Repo Intake to Confirmed Run Creation Wiring

`ConfirmedDevelopmentRunCreateRequest` now accepts optional `repo_intake_preview`.

When supplied, the confirmed run creation path:

- Builds a bounded repo-aware snapshot.
- Embeds compact per-step repo-aware context into each pending step input.
- Does not persist repo intake separately.
- Does not create extra projects/runs/tool_calls beyond the explicitly confirmed pending run and steps.
- Does not call providers, read files, execute commands, or start agents.

## Repo-aware Step Input Format

Created step inputs may now contain:

```text
AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT
...
END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT

AI_WORKBENCH_REPO_AWARE_CONTEXT
- detected_stack: ...
- detected_project_type: ...
- relevant_area_hints: ...
- relevant_manifest_scripts: ...
- test_discovery_hints: ...
- protected_path_warnings: ...
- suggested_safe_commands: ...
- recommended_first_safe_action: ...
- safety_notes: ...
- limitations: ...
END_AI_WORKBENCH_REPO_AWARE_CONTEXT
```

The repo-aware block is metadata only: stack hints, path hints, manifest script names, warnings, and copy-only command suggestions.

## Agent Step Context Behavior

`GET /api/runs/{run_id}/agent-step-context` now exposes additive repo-aware fields per step:

- `repo_context_available`
- `detected_stack`
- `detected_project_type`
- `relevant_area_hints`
- `relevant_manifest_scripts`
- `test_discovery_hints`
- `protected_path_warnings`
- `suggested_safe_commands`
- `repo_safety_notes`
- `repo_limitations`

Old steps without repo context still parse normally.

## Patch Draft Behavior

`POST /api/runs/{run_id}/steps/{step_id}/agent-patch-draft` now includes repo-aware hints when available:

- detected stack
- relevant repo areas
- manifest script hints
- test discovery hints
- protected path warnings
- copy-only suggested safe commands

Suggested safe commands are included as validation suggestions only. No commands are executed.

## Guarded Proposal / Preflight Behavior

`POST /api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal` now surfaces repo-aware protected path warnings and validation suggestions during preflight.

Existing guard behavior remains intact:

- preflight does not create proposals when `confirm_create_proposal=false`
- proposal creation still requires explicit confirmation
- Source of Truth guard still blocks blocked patches
- apply remains separate and requires the existing explicit confirmation flow

## Frontend NewTask Behavior

NewTask now includes `repo_intake_preview` in the confirmed pending run creation request when repo intake exists.

The bridge UI states that repo analysis will be attached as bounded context and will not execute commands or modify files.

## Frontend RunDetail Behavior

RunDetail now displays repo-aware context in the Agent Step Context panel:

- detected stack
- relevant areas
- manifest scripts
- test discovery hints
- protected warnings
- copy-only safe commands

Patch draft panels also display repo-aware draft hints. No execution buttons were added for these commands.

## Suggested Safe Commands Behavior

Suggestions are derived only from safe manifest script names and known test hints:

- npm scripts such as `test`, `test:unit`, `test:e2e`, `lint`, `typecheck`, `build`
- `pytest` from Python/pytest hints
- `phpunit` / `composer test` from PHP/composer hints

They are display-only/copy-only suggestions.

## Safety Boundaries

Preserved:

- No DB schema changes.
- No migrations.
- No provider calls.
- No network calls.
- No command execution.
- No runtime test execution.
- No auto-start.
- No auto-proposal creation.
- No patch apply.
- No rollback.
- No guard or approval bypass.
- No changes to `scripts/run_tests.sh`.

## Tests Added

Added `backend/tests/test_repo_aware_agent_work_context_fastlane.py`.

Coverage includes:

- repo context snapshot builder and bounding
- secret-like value redaction
- safe command suggestion extraction
- confirmed run creation with repo context
- parser compatibility
- agent-step-context API exposure
- patch draft repo hints
- guarded proposal preflight repo warnings/suggestions
- static safety checks
- frontend static checks

## Exact Check Results

Backend compile:

- `python -m py_compile src/orchestrator/project_intake.py`: passed
- `python -m py_compile src/api/routes.py`: passed
- `python -m py_compile src/models.py`: passed
- `python -m py_compile tests/test_repo_aware_agent_work_context_fastlane.py`: passed

Backend targeted tests:

- `tests/test_repo_aware_agent_work_context_fastlane.py`: 57 passed
- `tests/test_existing_project_readonly_repo_intake_fastlane.py`: 33 passed
- `tests/test_confirmed_development_run_bridge_fastlane.py`: 52 passed
- `tests/test_intake_run_agent_assignment_step_context.py`: 50 passed
- `tests/test_step_agent_patch_draft_fastlane.py`: 58 passed
- `tests/test_step_patch_draft_guarded_proposal_fastlane.py`: 62 passed
- `tests/test_execute_next_step.py`: 3 passed

Full backend:

- `.venv/bin/pytest -q`: 2214 passed + 38 subtests

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root runner:

- `bash scripts/run_tests.sh`: passed
- Runner backend result: 2214 passed + 38 subtests
- Runner frontend TypeScript check: passed

## Files Changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_repo_aware_agent_work_context_fastlane.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/NewTask.tsx`
- `frontend/src/pages/RunDetail.tsx`
- `runs/repo-aware-agent-work-context-mega-fastlane-v1/final-report.md`

## Protected Files

- `database.py` touched: No
- `engine.py` touched: No
- providers touched: No
- `model_router.py` touched: No
- `project_tools.py` touched: No
- `scripts/run_tests.sh` touched: No

The worktree contains pre-existing dirty/untracked files unrelated to this slice; they were not reset or reverted.

## P0/P1/P2/P3 Issues

- P0: None found.
- P1: None found.
- P2: Repo-aware context is still metadata-level only; it does not provide semantic code understanding.
- P3: Frontend build still emits the existing Vite large chunk warning.

## Known Limitations

- Repo-aware context is bounded metadata, not full semantic code understanding.
- Safe commands are suggestions only, not execution.
- No automatic apply/test/fix loop yet.
- No provider-based coding added.
- No parallel multi-agent execution added.
- Exact `old_text` for patch proposals still requires operator review or a future read-only context gathering step.

## Recommended Next Mega-Fastlane Block

Controlled Apply/Test/Fix from Repo-aware Steps Mega-Fastlane v1.

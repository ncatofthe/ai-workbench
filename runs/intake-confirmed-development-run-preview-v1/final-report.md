# Intake -> Confirmed Development Run Preview v1

## Summary

Implemented a deterministic, preview-only development run preview stage for the autonomous intake pipeline.

The pipeline now supports:

idea / document / existing_project -> unified intake -> clarifying answers -> Source of Truth draft -> Module Map draft -> Multi-Agent Plan -> Development Run Preview

The new preview shows a future controlled development run without creating any project, run, run step, tool call, patch proposal, provider call, file read, repository scan, command execution, or apply operation.

## Why this slice exists

This slice prepares the product for a later confirmed development run creation step while preserving the current safety boundary. Operators can now review the shape of the future run before any persistent run state exists.

## Preview builder behavior

Added `build_intake_development_run_preview(...)` in `backend/src/orchestrator/project_intake.py`.

The builder:

- accepts intake, clarifying answers, optional Source of Truth draft, optional Module Map draft, optional Multi-Agent Plan, and preferred run mode.
- uses a provided Multi-Agent Plan when available.
- derives a conservative fallback plan when the Multi-Agent Plan is missing.
- converts plan tasks into ordered preview steps.
- preserves dependencies, expected outputs, validation steps, agent roles, requirement links, and module links.
- adds safety gates and manual approval markers.
- defaults every step to `provider_allowed=false`.
- keeps output bounded and deterministic.

## Idea mode behavior

Idea previews include context confirmation, architecture alignment, backend/frontend/database/QA/delivery planning steps where relevant. The recommended first safe action points operators toward Source of Truth confirmation when missing.

## Document mode behavior

Document previews include requirement normalization, acceptance criteria validation, and architecture/module alignment. Long raw document excerpts are not dumped into the preview.

## Existing Project behavior

Existing project previews include future-only repository inventory, test discovery, protected module review, and first safe patch candidate planning. `project_path` remains a string hint only. The preview performs no repository scan, file read, or command execution.

## SoT linkage behavior

When a Source of Truth draft is provided, requirement IDs are attached to preview steps and summarized. Missing Source of Truth still returns a preview with warnings and missing-input markers.

## Module Map linkage behavior

When a Module Map draft is provided, module IDs are attached to preview steps and summarized. Sensitive modules such as auth/database/security/provider/deployment areas trigger manual approval markers.

## Multi-Agent Plan linkage behavior

When a Multi-Agent Plan is provided, its tasks are converted to preview steps. When it is missing, a conservative fallback plan is derived from intake context without persistence.

## Validation behavior

The preview validation reports readiness, errors, warnings, missing inputs, and blocked reasons. It blocks readiness when no steps/title/goal exist, secret-like content is present, or both Source of Truth and Multi-Agent Plan are absent.

## Endpoint behavior

Added:

- `POST /api/project-intake/development-run-preview`

The endpoint is preview-only and returns `IntakeDevelopmentRunPreviewResponse`. It does not persist state and does not alter existing unified preview, clarifying questions, Source of Truth draft, Module Map draft, Multi-Agent Plan, create-run, or confirmed-run behavior.

## Frontend UI changes

Updated New Task intake UI with:

- `Preview Development Run` button after the Multi-Agent Plan panel.
- Development Run Preview panel showing title, goal, recommended mode, readiness, first safe action, agent roles, requirement links, module links, safety summary, proposed steps, gates, and limitations.

The UI adds no hidden project/run creation, provider call, upload parsing, file scan, or mutation.

## Safety boundaries

Verified:

- no provider calls
- no network calls
- no file content reads
- no repository scanning
- no command execution
- no project creation
- no run creation
- no run step creation
- no tool call creation
- no patch proposal creation
- no apply patch
- no guard/approval bypass
- no changes to Start Task or confirmed-run behavior

## Tests added

Added `backend/tests/test_intake_confirmed_development_run_preview.py`.

Coverage includes:

- idea/document/existing_project preview creation
- deterministic step IDs and output
- bounds for steps, roles, requirement links, and module links
- mode-specific expected planning steps
- SoT, Module Map, and Multi-Agent Plan linkage
- missing draft fallback/warnings
- provider-disabled defaults
- risky task manual approval behavior
- endpoint read-only behavior
- static safety checks
- compatibility import checks

## Files changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_intake_confirmed_development_run_preview.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/intake-confirmed-development-run-preview-v1/final-report.md`

## Protected files

- `database.py` touched: no
- `engine.py` touched: no
- providers touched: no

Protected files had pre-existing worktree state in this repository, but this slice did not edit them.

## Exact check results

Backend:

- `python -m py_compile src/orchestrator/project_intake.py src/models.py src/api/routes.py tests/test_intake_confirmed_development_run_preview.py`: passed
- `pytest -q tests/test_intake_confirmed_development_run_preview.py`: 61 passed
- `pytest -q tests/test_multi_agent_plan_from_intake.py`: 58 passed
- `pytest -q tests/test_auto_module_map_draft_from_intake.py`: 63 passed
- `pytest -q tests/test_auto_source_of_truth_draft_from_intake.py`: 114 passed
- `pytest -q tests/test_clarifying_questions_engine.py`: 52 passed
- `pytest -q tests/test_unified_autonomous_project_intake.py`: 44 passed
- `pytest -q tests/test_real_project_end_to_end_delivery_dogfood.py`: 45 passed
- `pytest -q tests/test_project_context_cockpit.py`: 26 passed
- Targeted compatibility suites: 402 passed
- Full backend pytest: 1760 passed + 38 subtests

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root:

- `bash scripts/run_tests.sh`: passed
  - backend: 1760 passed + 38 subtests
  - frontend TypeScript check: passed

## P0/P1/P2/P3 issues

- P0: none found
- P1: none found
- P2: none found
- P3: existing frontend build still emits a Vite chunk-size warning over 500 kB; non-blocking and not introduced by this preview contract.

## Known limitations

- deterministic only
- no provider/LLM reasoning
- no document upload extraction
- no repository file scanning
- no automatic project creation
- no automatic run creation
- no run step creation
- no agent execution from intake screen
- development run is preview-only

## Recommended next slice

Intake -> Confirmed Development Run Preview Regression Pass

Alternative next slice: Confirmed Development Run Creation Contract v1

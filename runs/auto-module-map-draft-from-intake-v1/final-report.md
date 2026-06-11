# Auto Module Map Draft from Intake v1 — Final Report

## Summary

Implemented Auto Module Map Draft from Intake v1.

The intake pipeline can now build a deterministic, bounded Module Map draft from:
- a `UnifiedIntakeRequest`
- clarifying answers
- an optional Source of Truth draft

The implementation mirrors the Source of Truth draft flow:
- preview first
- no hidden persistence
- explicit confirm endpoint for persistence
- no project creation
- no run creation
- no tool_call creation
- no provider calls
- no repository scanning
- no file content reads

## Why This Slice Exists

This slice closes the next intake pipeline gap:

idea / document / existing_project → unified intake preview → clarifying questions → refined preview → Source of Truth draft → Module Map draft → explicit persistence.

The goal is to help an operator quickly get a conceptual Module Map before any repo scan, agent run, proposal, or apply path.

## Draft Builder Behavior

Added a pure deterministic builder:

- `build_module_map_draft_from_intake(...)`
- input model: `ModuleMapDraftFromIntakeRequest`
- output model: `ModuleMapDraftFromIntakeResponse`

The builder:
- reuses the clarified intake refinement path
- converts refined intake/module preview data into a `ProjectModuleMapUpsertRequest`-compatible draft
- produces stable module ids/slugs
- links optional Source of Truth requirement ids to matching modules
- bounds modules, paths, key files, requirement ids, risks, test hints, warnings, and errors
- validates secrets/path-risk hints conservatively

## Idea Mode Behavior

Idea mode uses conceptual product signals from the intake text, answers, stack hints, and optional SoT draft.

Typical inferred modules include:
- frontend / UI
- backend / API
- database / persistence
- auth / users when relevant
- reporting / analytics when relevant
- integrations when relevant
- testing / QA when relevant

Draft source is `intake_idea`.

## Document Mode Behavior

Document mode derives conceptual modules from requirement clusters and document excerpt signals.

It does not dump the source document into the draft. Ambiguous architecture is represented through warnings and lower-confidence modules.

Draft source is `intake_document`.

## Existing Project Behavior

Existing project mode uses only request-provided hints:
- known stack
- project path string as a hint
- clarifying answers
- optional SoT draft requirements

It does not scan the repository and does not read files.

Service desk / ticketing language can infer modules such as:
- tickets workflow
- SLA rules
- notifications
- knowledge base
- reports dashboard

Draft source is `intake_existing_project`.

## SoT Linkage Behavior

Optional Source of Truth draft requirements are parsed defensively. Requirement ids are linked to modules using deterministic keyword matching and a bounded fallback distribution.

If no SoT draft is provided, the Module Map draft still works and reports lower requirement coverage.

## Validation Behavior

Validation returns:
- `valid`
- `errors`
- `warnings`
- `missing_fields`
- `confidence`
- `module_count`
- `requirement_coverage_count`

The validator blocks:
- no generated modules
- secret-like content
- unsafe path hints such as `.env`, credentials, private keys, or traversal-like paths

The validator warns for:
- missing requirement links
- missing test hints
- missing ownership/agent-role hints
- existing project intake without known stack
- existing project intake without a test command hint

## Preview Endpoint Behavior

Added:

- `POST /api/project-intake/module-map-draft`

Behavior:
- preview-only
- returns `persisted=false`
- does not write DB records
- does not create project/run/tool_call records
- does not call providers
- does not read files
- does not scan repositories
- deterministic for the same input

## Confirm Persistence Behavior

Added:

- `POST /api/project-intake/module-map-draft/confirm`

Behavior:
- requires `project_id`
- requires `confirm_persist=true`
- rejects invalid drafts
- validates against existing Module Map validation
- persists exactly one active Module Map version through existing storage
- returns `persisted=true`, `module_map_id`, and `version`
- does not create runs/tool_calls
- does not call providers
- does not read files

## Frontend UI Changes

Updated New Task intake UI:
- added `Build Module Map draft`
- shows validation state, errors, warnings, missing fields
- shows inferred stack
- shows draft modules, requirement links, path/key-file hints, risks, and test hints
- shows next recommended action
- offers `Save Module Map draft` only when a project is selected
- shows an explicit empty state when no project is selected

The UI does not create a project, create a run, call providers, scan files, or trigger proposals/apply paths.

## Safety Boundaries

Verified:
- no DB schema changes
- no migrations
- no provider calls
- no network calls
- no file content reads
- no shell/subprocess/os commands added to runtime
- no `execute_run`
- no `asyncio.create_task`
- no `create_tool_call`
- no run creation
- no project creation
- no patch proposal creation
- no apply patch
- no auto-rollback
- no guard/approval bypass
- preview endpoint has no hidden persistence
- confirm persistence requires explicit `project_id` and `confirm_persist=true`

## Tests Added

Added:

- `backend/tests/test_auto_module_map_draft_from_intake.py`

Coverage includes:
- idea/document/existing_project draft generation
- deterministic output
- bounded output
- stable module ids/names
- mode-specific source values
- known stack usage
- service desk/ticketing module inference
- protected/risky module answers
- Source of Truth requirement linkage
- validation errors/warnings
- preview endpoint safety
- confirm endpoint safety and persistence
- static safety checks
- frontend/build compatibility through the full check run

## Files Changed

Changed/added for this slice:
- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_auto_module_map_draft_from_intake.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/auto-module-map-draft-from-intake-v1/final-report.md`

Repository note: the worktree contains pre-existing dirty/untracked state outside this slice. Protected files with pre-existing dirty state were not modified by this slice.

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice
- `backend/src/orchestrator/engine.py`: not touched by this slice
- provider runtime files: not touched by this slice
- `backend/src/project_tools.py`: not touched by this slice
- `backend/src/model_router.py`: not touched by this slice
- `scripts/run_tests.sh`: not touched by this slice

## Exact Check Results

Backend compile:
- `python -m py_compile src/orchestrator/project_intake.py src/models.py src/api/routes.py tests/test_auto_module_map_draft_from_intake.py`: passed

Targeted backend:
- `tests/test_auto_module_map_draft_from_intake.py`: 63 passed
- `tests/test_auto_source_of_truth_draft_from_intake.py`: 114 passed
- `tests/test_clarifying_questions_engine.py`: 52 passed
- `tests/test_unified_autonomous_project_intake.py`: 44 passed
- `tests/test_project_module_map.py`: 41 passed
- `tests/test_module_map_agent_context_wiring.py`: 30 passed
- `tests/test_module_map_patch_draft_context.py`: 26 passed
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: 45 passed
- `tests/test_project_context_cockpit.py`: 26 passed

Full backend:
- `pytest -q`: 1641 passed + 38 subtests

Frontend:
- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root runner:
- `bash scripts/run_tests.sh`: passed
- backend inside runner: 1641 passed + 38 subtests
- frontend TypeScript check inside runner: passed

## P0/P1/P2/P3 Issues

- P0: none found
- P1: none found
- P2: none found
- P3: none found

## Known Limitations

- Deterministic only; no provider/LLM reasoning.
- No document upload extraction.
- No repository file scanning.
- No file content analysis.
- No automatic project creation.
- No automatic run creation.
- No agent execution from intake screen.
- Existing project mode uses path/stack strings as hints only.
- Secret/path validation is intentionally conservative and can reject risky path mentions in free text.

## Recommended Next Slice

Recommended next slice:

- Auto Module Map Draft from Intake Regression Pass

Alternative:

- Multi-Agent Plan from Intake v1

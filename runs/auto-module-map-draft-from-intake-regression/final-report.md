# Auto Module Map Draft from Intake Regression Pass — Final Report

## Summary

Completed the regression/stability pass for Auto Module Map Draft from Intake v1.

No P0/P1/P2/P3 issues were found. No source fixes were required. The implemented flow remains preview-first, deterministic, and bounded, with explicit confirm-only persistence for Module Map drafts.

## Draft Builder Validation

Inspected `build_module_map_draft_from_intake(...)` in `backend/src/orchestrator/project_intake.py`.

Validated:
- deterministic output for the same input
- safe reuse of clarified intake refinement
- optional Source of Truth draft parsing is defensive
- requirement ids link to modules when available
- missing/invalid SoT draft does not crash
- stable module ids/slugs/names
- bounded modules, paths, key files, requirement ids, risks, test hints, warnings, and errors
- no raw document dump
- no raw repository dump
- no file contents
- no DB writes
- no provider calls
- no project/run/tool_call creation

## Idea Mode Validation

Validated:
- draft source is `intake_idea`
- conceptual modules are generated from intake goals/features/use cases
- frontend/backend/database modules appear for web/SaaS stack signals
- auth/admin/reporting/integration modules appear only from relevant signals
- QA/testing module hints appear when QA/test language is present
- output remains conceptual and non-repo-based
- missing fields produce warnings/errors instead of crashes
- no hidden persistence

## Document Mode Validation

Validated:
- draft source is `intake_document`
- full document excerpt is not dumped into response
- modules are derived from requirement/document signals
- ambiguous architecture remains warning/low-confidence context
- optional SoT linkage works
- no upload parsing
- no provider/LLM reasoning
- no file reads

## Existing Project Mode Validation

Validated:
- draft source is `intake_existing_project`
- `project_path` is treated as a string hint only
- no repository scan
- no `os.listdir`, pathlib traversal, `open`, `read_text`, or file-content read in the builder
- `known_stack` influences conceptual module hints
- service desk/ticket keywords infer tickets/SLA/notifications/reporting modules
- protected module answers become risks/constraints
- test command and delivery goals remain text context only
- no patch/proposal/apply/test execution

## SoT Linkage Validation

Validated:
- optional SoT requirement ids link to modules
- missing SoT draft still works
- invalid/empty SoT draft does not crash
- `requirement_coverage_count` is computed
- requirement ids are bounded
- no raw SoT JSON dump
- no hidden persistence of SoT or Module Map

## Validation Behavior

Validated:
- no modules is invalid
- missing module name/title is invalid through model/storage validation
- missing description/responsibilities are surfaced as missing fields
- missing requirement links warn
- missing test hints warn
- existing project without known stack warns
- secret-like content is invalid/blocked
- unsafe path hints such as `.env`, credentials, private keys, and secrets are invalid/blocked
- unsafe module paths are rejected by existing Module Map path validation
- messages are operator-readable and bounded
- validation does not mutate the draft unexpectedly
- secret filtering prevents secret-like snippets from being copied into bounded output fields

## Preview Endpoint Validation

Inspected `POST /api/project-intake/module-map-draft`.

Validated:
- preview-only
- returns `persisted=false`
- accepts but ignores persistence flags on preview path
- returns draft plus validation
- creates no project
- creates no run
- creates no tool_calls
- calls no providers
- reads no files
- scans no repositories
- executes no commands
- deterministic for the same input
- does not alter unified-preview, clarifying-preview, or Source of Truth draft endpoint behavior

## Confirm Endpoint Validation

Inspected `POST /api/project-intake/module-map-draft/confirm`.

Validated:
- requires `project_id`
- requires `confirm_persist=true`
- rejects invalid drafts
- validates through existing Module Map document validation
- persists through existing Module Map upsert behavior only
- returns `persisted=true`, `module_map_id`, and `version` on success
- creates no project
- creates no run
- creates no tool_calls
- calls no providers
- reads no files
- scans no repository
- executes no commands
- no persistence occurs without explicit confirm

## Frontend UI Validation

Inspected `frontend/src/types/index.ts`, `frontend/src/api/client.ts`, and `frontend/src/pages/NewTask.tsx`.

Validated:
- TypeScript response/request interfaces match backend shape
- `Build Module Map draft` calls only `/api/project-intake/module-map-draft`
- draft panel renders validation state, errors, warnings, missing fields, inferred stack, modules, requirement links, risks, test hints, and next action
- save UI calls only `/api/project-intake/module-map-draft/confirm`
- save UI requires a selected project context
- no hidden create-run
- no hidden project creation
- no hidden provider call
- no upload parsing
- no file scanning
- existing NewTask create-run flow remains separate and unchanged

## Safety / Static Scan Validation

Scanned the new helper/endpoint/frontend/test surfaces for:
- `execute_run`
- `asyncio.create_task`
- `subprocess`
- `os.system`
- `os.popen`
- provider calls
- `ollama.chat_completion`
- Claude/Codex provider calls
- `create_tool_call`
- project/run creation in draft path
- patch proposal/apply calls
- `open`
- `.read_text`
- `.read`
- pathlib scanning
- `os.listdir`
- DB writes in preview
- hidden persistence without `confirm_persist`

Findings:
- No violations in the new Module Map draft builder or draft endpoints.
- Broad-file scans show pre-existing route/runtime strings elsewhere in `routes.py` and existing UI text such as `ready_to_create_run`; these are outside the Module Map draft path and were not introduced by this regression pass.
- Test-file matches are safety assertions, not executable behavior.

## Workflow Compatibility Validation

Validated via targeted suites, full backend pytest, frontend type/build, browser E2E smoke, and root runner.

All requested checks passed.

## P0/P1/P2/P3 Issues Found

- P0: none
- P1: none
- P2: none
- P3: none

## Changes Made

No implementation/source fixes were made in this regression pass.

Created this report:
- `runs/auto-module-map-draft-from-intake-regression/final-report.md`

## Exact Checks / Results

Backend compile:
- `.venv/bin/python -m py_compile src/orchestrator/project_intake.py`: passed
- `.venv/bin/python -m py_compile src/models.py`: passed
- `.venv/bin/python -m py_compile src/api/routes.py`: passed
- `.venv/bin/python -m py_compile tests/test_auto_module_map_draft_from_intake.py`: passed

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
- `.venv/bin/pytest -q`: 1641 passed + 38 subtests

Frontend:
- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root runner:
- `bash scripts/run_tests.sh`: passed
- backend inside runner: 1641 passed + 38 subtests
- frontend TypeScript check inside runner: passed

## Protected Files

- `backend/src/storage/database.py`: not touched by this regression pass
- `backend/src/orchestrator/engine.py`: not touched by this regression pass
- provider runtime files: not touched by this regression pass
- `backend/src/project_tools.py`: not touched by this regression pass
- `backend/src/model_router.py`: not touched by this regression pass
- `scripts/run_tests.sh`: not touched by this regression pass

Repository note: `database.py`, `engine.py`, and `scripts/run_tests.sh` still show pre-existing dirty state in git status. They were not modified during this regression pass.

## Known Limitations

- Deterministic only.
- No provider/LLM reasoning.
- No document upload extraction.
- No repository file scanning.
- No file content analysis.
- No automatic project creation.
- No automatic run creation.
- No agent execution from the intake screen.
- Existing project mode still treats `project_path` as text context only.

## Recommended Next Slice

Recommended next slice:
- Multi-Agent Plan from Intake v1

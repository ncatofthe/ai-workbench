# Multi-Agent Plan from Intake Regression Pass — Final Report

## Summary

Completed the regression/stability pass for Multi-Agent Plan from Intake v1.

The backend plan builder and endpoint remain deterministic, bounded, and preview-only. The frontend integration remains read-only and does not trigger project/run/agent/provider behavior. No P0/P1 issues were found and no source fixes were made.

## Plan Builder Validation

Inspected `build_multi_agent_plan_from_intake(...)` in `backend/src/orchestrator/project_intake.py`.

Validated:
- deterministic for the same input
- safely reuses `refine_unified_intake_with_answers(...)`
- uses optional Source of Truth draft defensively
- uses optional Module Map draft defensively
- attaches requirement ids to tasks when SoT draft is available
- attaches target modules to tasks when Module Map draft is available
- works without SoT draft with warnings/missing inputs
- works without Module Map draft with warnings/missing inputs
- creates bounded tasks, milestones, risks, module links, requirement links, outputs, and validation steps
- does not dump raw document text
- does not dump raw repository data
- includes no file contents
- performs no DB writes
- performs no provider calls
- creates no project, run, run step, or tool_call

## Idea Mode Validation

Validated:
- idea mode returns a multi-agent plan
- includes `product_analyst`
- includes `architect`
- includes backend/frontend/database/QA roles where appropriate
- includes `security_guard_agent` when sensitive modules/risk exist
- includes `delivery_reviewer_agent`
- recommends Source of Truth/Module Map confirmation when missing
- remains conceptual and project-creation-ready
- does not introduce repository scanning tasks except as future/hypothetical planning language when relevant
- no hidden persistence

## Document Mode Validation

Validated:
- document mode returns a multi-agent plan
- includes requirement normalization
- includes acceptance criteria validation
- does not dump the full raw document
- ambiguous or missing requirement context produces warnings/risks
- architecture/module alignment task appears
- no provider/LLM reasoning is invoked
- no file reads or upload parsing occur

## Existing Project Mode Validation

Validated:
- existing_project mode returns a multi-agent plan
- includes repository inventory as a future planning task only
- includes test discovery as a future planning task only
- includes first safe patch candidate planning
- uses `known_stack` for task targeting
- `project_path` remains a string hint only
- no repository scanning
- no `os.listdir`, pathlib traversal, `open`, `read_text`, or file reads in the builder
- protected/sensitive modules create manual approval markers
- no patch/proposal/apply/test execution

## SoT Linkage Validation

Validated:
- SoT requirement ids attach to tasks
- missing SoT draft still builds with warning and `source_of_truth_draft` in missing inputs
- invalid/empty SoT draft does not crash
- requirement ids remain bounded
- no raw SoT JSON dump
- no hidden SoT persistence

## Module Map Linkage Validation

Validated:
- Module Map module slugs attach to tasks
- sensitive module slugs influence manual approval and risk markers
- missing Module Map draft still builds with warning and `module_map_draft` in missing inputs
- invalid/empty Module Map draft does not crash
- target modules remain bounded
- no raw Module Map JSON dump
- no hidden Module Map or plan persistence

## Safety / Policy Validation

Validated:
- `provider_allowed` defaults `false` for all tasks
- risky auth/database/deployment/provider-style tasks require manual approval
- validation steps are present
- `recommended_first_action` is present
- task language frames apply/test/provider work as future controlled workflow, not completed execution
- `manual_approval_required` is used conservatively
- backend `safety_notes` are present and operator-readable

## Endpoint Validation

Inspected `POST /api/project-intake/multi-agent-plan`.

Validated:
- endpoint is preview-only
- returns 200 for idea/document/existing_project in tests
- creates no project
- creates no run
- creates no run steps
- creates no tool_calls
- calls no providers
- reads no files
- scans no repositories
- executes no commands
- deterministic for the same input
- does not alter unified-preview, clarifying-preview, SoT draft, Module Map draft, create-run, or confirmed-run behavior

## Frontend UI Validation

Inspected `frontend/src/types/index.ts`, `frontend/src/api/client.ts`, and `frontend/src/pages/NewTask.tsx`.

Validated:
- TypeScript interfaces match backend response shape
- `Build Multi-Agent Plan` calls only `/api/project-intake/multi-agent-plan`
- panel renders plan title/summary, validation/readiness, recommended first action, tasks, milestones, and risks
- no hidden create-run
- no hidden project creation
- no hidden run creation
- no hidden provider call
- no upload parsing
- no file scanning
- existing NewTask create flow remains unchanged
- frontend typecheck/build pass

Non-blocking UI note:
- The panel shows compact preview-only safety copy, but does not enumerate the backend `safety_notes` and `limitations` arrays. This is a P3 visibility/polish gap, not a P0/P1 safety issue.

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
- `create_project`
- `create_run`
- `create_run_step`
- patch proposal/apply calls
- `open`
- `.read_text`
- `.read`
- pathlib scanning
- `os.listdir`
- DB writes in endpoint
- hidden persistence

Findings:
- No violations in the multi-agent plan builder or endpoint.
- Broad-file scans find pre-existing route/runtime code and existing UI text outside the multi-agent plan path.
- Test-file matches are static safety assertions, not executable behavior.

## Workflow Compatibility Validation

All requested compatibility checks passed.

## P0/P1/P2/P3 Issues Found

- P0: none
- P1: none
- P2: none
- P3: frontend panel does not enumerate `safety_notes` and `limitations` arrays; it shows compact safety copy instead.

## Changes Made

No source fixes were made in this regression pass.

Created:
- `runs/multi-agent-plan-from-intake-regression/final-report.md`

## Exact Checks / Results

Backend compile:
- `.venv/bin/python -m py_compile src/orchestrator/project_intake.py`: passed
- `.venv/bin/python -m py_compile src/models.py`: passed
- `.venv/bin/python -m py_compile src/api/routes.py`: passed
- `.venv/bin/python -m py_compile tests/test_multi_agent_plan_from_intake.py`: passed

Targeted backend:
- `tests/test_multi_agent_plan_from_intake.py`: 58 passed
- `tests/test_auto_module_map_draft_from_intake.py`: 63 passed
- `tests/test_auto_source_of_truth_draft_from_intake.py`: 114 passed
- `tests/test_clarifying_questions_engine.py`: 52 passed
- `tests/test_unified_autonomous_project_intake.py`: 44 passed
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: 45 passed
- `tests/test_project_context_cockpit.py`: 26 passed

Full backend:
- `.venv/bin/pytest -q`: 1699 passed + 38 subtests

Frontend:
- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root runner:
- `bash scripts/run_tests.sh`: passed
- backend inside runner: 1699 passed + 38 subtests
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
- No run step creation.
- No agent execution from intake screen.
- Plan is preview-only.

## Recommended Next Slice

Recommended next slice:
- Intake → Confirmed Development Run Preview v1

# Multi-Agent Plan from Intake v1 — Final Report

## Summary

Implemented Multi-Agent Plan from Intake v1.

The intake pipeline can now build a deterministic, bounded, orchestrator-ready multi-agent development plan from:
- `UnifiedIntakeRequest`
- clarifying answers
- optional Source of Truth draft
- optional Module Map draft

The new plan is preview-only. It does not create projects, runs, run steps, tool calls, proposals, patches, or provider requests.

## Why This Slice Exists

This slice connects the intake foundation to the next controlled-autonomy stage:

idea / document / existing_project → unified intake → clarifying questions → refined intake → Source of Truth draft → Module Map draft → Multi-Agent Plan preview.

The plan gives the operator a structured view of agent roles, tasks, milestones, risks, approvals, and first safe action before any run or agent execution exists.

## Plan Builder Behavior

Added:

- `MultiAgentPlanFromIntakeRequest`
- `MultiAgentPlanTask`
- `MultiAgentPlanMilestone`
- `MultiAgentPlanRisk`
- `MultiAgentPlanValidation`
- `MultiAgentPlanFromIntakeResponse`
- `build_multi_agent_plan_from_intake(...)`

The builder:
- reuses `refine_unified_intake_with_answers(...)`
- consumes optional Source of Truth requirements
- consumes optional Module Map modules
- produces stable task ids
- attaches requirement ids and module slugs to tasks
- marks sensitive modules as manual-approval work
- keeps `provider_allowed=false` for every task
- creates milestones and risks
- recommends the first safe operator action
- bounds all output lists

## Idea Mode Behavior

Idea mode produces a conceptual product-development plan with roles such as:
- `product_analyst`
- `architect`
- `backend_agent`
- `frontend_agent`
- `database_agent`
- `qa_agent`
- `security_guard_agent`
- `delivery_reviewer_agent`

It recommends Source of Truth and Module Map confirmation when those drafts are missing.

## Document Mode Behavior

Document mode adds requirement normalization and acceptance-criteria validation.

It does not dump the raw document/excerpt. Ambiguous or incomplete document context is surfaced as warnings/risks and missing inputs.

## Existing Project Behavior

Existing project mode adds preview-only future tasks for:
- repository inventory
- test discovery
- architecture/module alignment
- first safe patch candidate

`project_path` remains a string hint only. No repository scan, file read, command execution, patch proposal, or apply path is triggered.

## SoT Linkage Behavior

When a Source of Truth draft is supplied:
- requirement ids are parsed defensively
- task requirement links are populated
- requirement coverage becomes visible in the plan

When missing:
- the plan still builds
- validation warns with `source_of_truth_draft` in missing inputs

## Module Map Linkage Behavior

When a Module Map draft is supplied:
- module slugs are attached to tasks
- sensitive modules influence manual approval markers
- module risks are represented in plan risks and task metadata

When missing:
- the plan still builds
- validation warns with `module_map_draft` in missing inputs

## Validation Behavior

Validation returns:
- `valid`
- `errors`
- `warnings`
- `missing_inputs`
- `readiness`

It blocks secret-like intake content. It warns when SoT, Module Map, requirement links, module links, validation steps, known stack, or test command context is missing.

## Endpoint Behavior

Added:

- `POST /api/project-intake/multi-agent-plan`

Behavior:
- preview-only
- no DB writes
- no project creation
- no run creation
- no run step creation
- no tool_call creation
- no provider calls
- no file reads
- no repository scanning
- no command execution
- no changes to unified-preview, clarifying-preview, SoT draft, Module Map draft, create-run, or confirmed-run behavior

## Frontend UI Changes

Updated New Task intake UI:
- added `Build Multi-Agent Plan`
- renders plan title and summary
- renders validation/readiness, warnings/errors/missing inputs
- renders recommended first action
- renders milestones
- renders tasks by agent role
- renders risks and mitigations

The UI remains read-only. It does not create projects, runs, run steps, tool calls, provider requests, scans, proposals, or applies.

## Safety Boundaries

Verified:
- no DB schema changes
- no migrations
- no provider calls
- no network calls
- no file content reads
- no shell/subprocess/os commands added
- no `execute_run`
- no `asyncio.create_task`
- no `create_tool_call`
- no project creation
- no run creation
- no run step creation
- no patch proposal creation
- no apply patch
- no auto-rollback
- no guard/approval bypass
- no Start Task behavior change
- no confirmed-run behavior change
- no create-run payload change

## Tests Added

Added:

- `backend/tests/test_multi_agent_plan_from_intake.py`

Coverage includes:
- idea/document/existing_project plan generation
- stable task ids
- deterministic output
- bounded tasks/milestones/risks/task links
- idea-mode agent roles
- document requirement normalization and acceptance validation
- existing-project repo inventory/test discovery/first safe patch candidate
- SoT requirement linkage
- Module Map module linkage
- missing/invalid draft behavior
- provider default denial
- manual approval markers for sensitive work
- endpoint non-mutation checks
- static safety checks
- compatibility import checks

## Files Changed

Changed/added for this slice:
- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_multi_agent_plan_from_intake.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/multi-agent-plan-from-intake-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice
- `backend/src/orchestrator/engine.py`: not touched by this slice
- provider runtime files: not touched by this slice
- `backend/src/project_tools.py`: not touched by this slice
- `backend/src/model_router.py`: not touched by this slice
- `scripts/run_tests.sh`: not touched by this slice

Repository note: `database.py`, `engine.py`, and `scripts/run_tests.sh` still show pre-existing dirty state in git status. They were not modified during this slice.

## Exact Check Results

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

## P0/P1/P2/P3 Issues

- P0: none found
- P1: none found
- P2: none found
- P3: none found

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

- Multi-Agent Plan from Intake Regression Pass

Alternative:

- Intake → Confirmed Development Run Preview v1

# Orchestrator Planning from Intake v1

## Summary

Added a deterministic, read-only preliminary development plan preview:

- `idea + intake analysis + brief draft -> structured development plan preview`;
- backend Pydantic models and pure planner;
- read-only `POST /api/project-intake/plan-preview` endpoint;
- backend tests for vague ideas, detailed web app ideas, existing project flow, endpoint response, serialization, and no DB/tool/provider usage in the intake module;
- frontend `Preview plan` button in NewTask;
- frontend plan preview panel with readiness, phases, required inputs, assumptions, risks, recommended agents, and recommended next step.

## Backend behavior

- Endpoint: `POST /api/project-intake/plan-preview`.
- Planning is deterministic/rule-based and implemented in `backend/src/orchestrator/project_intake.py`.
- The planner reuses `draft_project_brief`, which itself reuses `analyze_project_intake`.
- The endpoint only validates that `idea` is non-empty, then returns a structured preview.
- The endpoint does not persist the plan and does not create projects, runs, assignments, or tool calls.

## Frontend behavior

- NewTask Project Intake block now includes a `Preview plan` button.
- The button uses the current task description as the idea.
- If a brief draft is already available, its markdown is passed as optional context, but the preview still remains read-only.
- The plan preview panel shows:
  - ready/not-ready badge;
  - mode and target type;
  - summary and source readiness;
  - phases with status, priority, suggested agent, dependencies, deliverables, and risks;
  - required inputs;
  - assumptions;
  - risks;
  - recommended agent ids;
  - recommended next step.
- The Start Task/create-run flow was not changed.
- The Start Task payload remains `{ prompt, mode, project_id: projectId }`.
- Plan previews are not persisted or attached to a project/run.

## Planning rules

New project phases:

- Requirements clarification
- Architecture/design
- Data model
- Backend/API
- Frontend/UI
- Auth/RBAC when auth is detected
- Files/uploads when uploads are detected
- Payments when payments are detected
- Notifications when notifications are detected
- Testing/QA
- Deployment
- Documentation/final report

Existing project phases:

- Project inventory
- Stack/profile detection
- Run/build/test command validation
- Existing code risk audit
- Current issue/goal clarification
- Context gathering
- Patch proposal/review
- Manual apply
- Test/fix loop
- Final verification/report

Readiness logic:

- `ready_to_start=false` when required inputs are missing, the idea is too vague, or existing-project project/stack/goal context is missing.
- `ready_to_start=true` only when the underlying intake/brief readiness is true, required inputs are empty, and no phases are blocked.
- The endpoint is still preview-only even when `ready_to_start=true`.

Agent recommendations:

- Recommendations are string ids from the existing registry, such as `orchestrator`, `product-manager`, `architect`, `backend-developer`, `frontend-developer`, `qa-expert`, `devops-engineer`, and `technical-writer`.
- The agent selector is not executed.
- No assigned team records are created.

## Safety guarantees

- No DB writes.
- No project creation.
- No run creation.
- No assigned team creation.
- No `tool_calls`.
- No tools execution.
- No LLM/provider execution.
- No patch proposal.
- No apply patch.
- No run command.
- No analyze result.
- No rollback.
- No shell runner.
- No external provider execution.
- `backend/src/storage/database.py` was not edited.

## Source changes

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_project_intake.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/orchestrator-planning-from-intake-v1/final-report.md`

## Tests

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py` - passed.
- `cd backend && .venv/bin/pytest -q` - `326 passed`.
- `cd frontend && npx tsc --noEmit` - passed.
- `cd frontend && npm run build` - passed.
- `bash scripts/run_tests.sh` - passed, including backend syntax checks, backend pytest `326 passed`, and frontend TypeScript check.

## Remaining gaps

- Plan is not persisted.
- Plan is not attached to project/run.
- Orchestrator does not yet execute the plan.
- Agent assignment is not created from the plan.
- Existing project onboarding scan is not implemented.
- No approval request model integration yet.
- No autonomous mode.

## Recommended next slice

Intake Plan Regression Pass v1.

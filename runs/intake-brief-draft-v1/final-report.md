# Intake Brief Draft v1

## Summary

Added deterministic, read-only project brief draft generation:

- backend project brief draft models and generator;
- read-only `POST /api/project-intake/brief-draft` endpoint;
- backend tests for structured response, vague/detailed ideas, existing-project mode, serialization, and endpoint wiring;
- frontend `Draft brief` button in NewTask;
- frontend preview panel for readiness, sections, assumptions, missing information, open questions, recommended next step, and markdown draft.

## Backend behavior

- Endpoint: `POST /api/project-intake/brief-draft`.
- Generation is deterministic/rule-based and implemented in `backend/src/orchestrator/project_intake.py`.
- The brief draft reuses intake analysis internally, then produces structured sections and `brief_markdown`.
- The response includes `title`, `mode`, `target_type`, `maturity_goal`, `readiness`, `summary`, `sections`, `assumptions`, `missing_information`, `open_questions`, `recommended_next_step`, and `ready_to_plan`.
- Vague ideas produce missing sections and open questions.
- Detailed ideas produce confirmed/assumed sections and can become ready to plan.
- Existing project wording continues to resolve to existing-project mode and remains not ready until project-specific details are answered.

## Frontend behavior

- NewTask now includes a `Draft brief` button next to `Analyze idea`.
- The button uses the current task description as the idea and calls the read-only brief draft endpoint.
- The preview panel shows:
  - readiness badge;
  - title and summary;
  - structured brief sections with confirmed/assumed/missing status;
  - assumptions;
  - missing information;
  - open questions;
  - recommended next step;
  - markdown preview in a plain preformatted block.
- The Start Task/create-run flow was not changed.
- The create task payload was not changed.
- Intake answers are not saved or attached to a project/run.

## Safety guarantees

- No DB writes.
- No project creation.
- No run creation.
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
- `runs/intake-brief-draft-v1/final-report.md`

## Tests

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py` — passed.
- `cd backend && .venv/bin/pytest -q` — `320 passed`.
- `cd frontend && npx tsc --noEmit` — passed.
- `cd frontend && npm run build` — passed.
- `bash scripts/run_tests.sh` — passed, including backend syntax checks, backend pytest `320 passed`, and frontend TypeScript check.

## Remaining gaps

- Brief is not persisted.
- Intake answers are not persisted.
- Brief is not attached to project/run.
- Orchestrator does not yet use brief for planning.
- Existing project onboarding scan is not implemented.
- No autonomous mode.

## Recommended next slice

Intake Brief Persistence v1.

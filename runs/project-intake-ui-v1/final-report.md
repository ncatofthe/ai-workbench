# Project Intake UI v1

## Summary

Added a minimal frontend-only Project Intake preview in `NewTask`.

Users can now click `Analyze idea` before starting a task to call the existing read-only intake endpoint and review advisory clarifying questions.

This slice does not change task/run creation behavior.

## UI behavior

- `Analyze idea` uses the current task description text as the intake idea.
- The button has an independent loading state.
- Intake errors are shown separately from task creation errors.
- The result panel shows:
  - readiness badge: `Ready to plan` or `Needs clarification`;
  - mode and confidence;
  - summary;
  - assumptions;
  - missing information;
  - clarifying questions with priority, category, question text, why it matters, suggested default, and options;
  - recommended next step.
- The existing `Start Task` button is not blocked by intake readiness.
- Intake answers are not interactive and are not saved.
- Intake output is not inserted into the task prompt automatically.
- The create task/run payload remains separate from the intake preview.

## API integration

Endpoint:

`POST /api/project-intake/questions`

Frontend client method:

`analyzeProjectIntake(request: ProjectIntakeRequest): Promise<ProjectIntakeResponse>`

Added frontend types matching the backend response shape from `project_intake.py`.

## Safety guarantees

- No run creation from intake analysis.
- No project creation.
- No DB writes from the intake UI action beyond the endpoint behavior, which is read-only.
- No `tool_calls`.
- No tools execution.
- No provider execution.
- No patch proposal.
- No apply patch.
- No run command.
- No analyze result.
- No rollback.
- No shell runner.
- No external provider execution.
- `database.py` untouched by this slice.

## Source changes

| File | Change |
| --- | --- |
| `frontend/src/types/index.ts` | Added `ProjectIntakeRequest`, `ProjectIntakeResponse`, question, mode, target, maturity, category, and priority types. |
| `frontend/src/api/client.ts` | Added `analyzeProjectIntake` client method for `POST /api/project-intake/questions`. |
| `frontend/src/pages/NewTask.tsx` | Added advisory Project Intake panel and result renderer without changing the existing submit flow. |
| `runs/project-intake-ui-v1/final-report.md` | Added this report. |

## Tests

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | Frontend types compile. |
| `cd frontend && npm run build` | Passed | Production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | Compile-only check; `database.py` not edited. |
| `cd backend && .venv/bin/pytest -q` | Passed | 315 passed. |
| `cd . && bash scripts/run_tests.sh` | Passed | Backend syntax, pytest, and frontend TypeScript checks passed. |

## Remaining gaps

- Answers are not persisted.
- Project brief is not generated or persisted yet.
- Orchestrator does not yet use intake response to build a plan.
- Existing project onboarding scan is not implemented.
- No autonomous mode.

## Recommended next slice

Intake Brief Draft v1.

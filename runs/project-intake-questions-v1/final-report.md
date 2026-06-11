# Project Intake Questions v1

## Summary

Project Intake Questions v1 adds a deterministic project intake analyzer for turning a raw project idea into structured clarifying questions before planning.

Confirmed slice contents:

- deterministic project intake analyzer;
- clarifying questions;
- new/existing project mode detection;
- target type and maturity detection;
- `ready_to_plan` signal;
- read-only endpoint;
- unit tests.

## Behavior

### New Project Mode

For new ideas, the analyzer asks about product goal, users/roles, platform, tech stack when unknown, project maturity, data storage, auth/security, UI/design, deployment, quality/testing, and signal-based optional areas such as payments, uploads, notifications, and integrations.

### Existing Project Mode

For existing projects, the analyzer asks for project location, current stack, current working state, broken/incomplete areas, next goal, tests, dev/build commands, protected areas, Git context, and secrets/environment constraints.

### Mode detection

Mode is selected by explicit request mode first, then `existing_project_attached`, then existing-project keywords in English/Russian. Otherwise it defaults to new project mode.

### Target type / maturity detection

Target type and maturity are detected with deterministic keyword/regex rules. Supported target categories include web app, mobile app, desktop app, API service, CLI tool, automation, and unknown. Supported maturity categories include MVP, full product, diploma, prototype, internal tool, and unknown.

### Bounded questions

Question count is bounded by constants in `project_intake.py`:

- required: max 8;
- recommended: max 7;
- optional: max 5;
- total: max 15.

### Assumptions

The response can include assumptions for detected target type, maturity goal, known stack, default stack for new projects, auth/login, and payments.

### Missing information

The response lists missing information such as unspecified platform, maturity/scope, tech stack, auth requirements, and storage requirements.

### ready_to_plan logic

New projects may become `ready_to_plan=true` only when enough deterministic signals are present. Existing projects are not immediately ready and require answers first.

## Endpoint

`POST /api/project-intake/questions`

Request model:

```json
{
  "idea": "Build a React CRM with auth and PostgreSQL",
  "mode": "new_project",
  "existing_project_attached": false,
  "known_stack": ["React", "FastAPI"],
  "known_constraints": [],
  "user_goal": "MVP"
}
```

Response model:

```json
{
  "mode": "new_project",
  "detected_target_type": "web_app",
  "detected_maturity_goal": "mvp",
  "summary": "...",
  "assumptions": [],
  "missing_information": [],
  "questions": [],
  "ready_to_plan": false,
  "recommended_next_step": "...",
  "confidence": "low"
}
```

The endpoint validates that `idea` is non-empty, then returns `analyze_project_intake(req)`.

## Safety guarantees

- No DB writes.
- No DB reads.
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
- `database.py` not intentionally edited.

The existing `database.py` dirty diff was not modified or reverted in this task.

## Source changes

Files related to this slice:

| File | Purpose |
| --- | --- |
| `backend/src/orchestrator/project_intake.py` | Deterministic intake analyzer, request/response models, mode/type/maturity detection, bounded question generation. |
| `backend/src/api/routes.py` | Adds `POST /api/project-intake/questions`, a read-only endpoint that delegates to the analyzer. |
| `backend/tests/test_project_intake.py` | Unit tests for mode detection, target detection, maturity detection, bounded question count, serialization, readiness, and missing info. |
| `scripts/run_tests.sh` | Adds syntax check for `src/orchestrator/project_intake.py`. |

`README.md` is modified in the working tree, but no Project Intake-specific documentation was found there during this verification pass.

## Tests

Confirmed by the provided baseline and re-run after this report:

- backend `py_compile src/storage/database.py`: passed;
- backend `pytest -q`: 315 passed;
- frontend `npx tsc --noEmit`: passed;
- frontend `npm run build`: passed;
- root `bash scripts/run_tests.sh`: passed.

## Remaining gaps

- Intake answers are not persisted yet.
- Project brief is not attached to project/run yet.
- Frontend UI is not implemented yet or not wired yet.
- Orchestrator does not yet use intake answers for planning.
- Existing project onboarding scan is not implemented yet.
- No autonomous mode.

## Recommended next slice

Project Intake UI v1.

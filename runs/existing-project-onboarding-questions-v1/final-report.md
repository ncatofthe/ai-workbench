# Existing Project Onboarding Questions v1

## Summary

Improved deterministic existing-project intake/onboarding support without adding execution behavior.

This slice strengthens:

- existing-project mode detection for Russian and English half-ready/existing project wording;
- existing-project onboarding questions for project location, stack, working/broken state, commands, tests, DB/env setup, Git, protected areas, deployment, and secrets;
- existing-project plan preview wording by using a clearer `safe-command-validation` phase;
- backend tests covering detection, bounded questions, onboarding coverage, existing-project plan phases, serialization, and read-only deterministic constraints.

## Backend behavior

- `analyze_project_intake` now detects more existing-project prompts, including:
  - "у меня уже есть проект";
  - "полуготовый проект";
  - "продолжить разработку";
  - "доработать существующий проект";
  - "загрузить папку проекта";
  - "existing project";
  - "continue an existing app".
- Existing-project questions now explicitly cover:
  - project path / repository location;
  - current stack/frameworks;
  - what already works;
  - what is broken or incomplete;
  - next development goal;
  - dev/build/test commands;
  - whether tests exist;
  - database/env/local service setup;
  - Git history/branch structure;
  - dangerous files or areas that should not be touched;
  - deployment target;
  - secrets and `.env` files to ignore.
- Question output remains bounded by `MAX_TOTAL = 15`.
- Existing-project plan preview remains read-only and now labels command validation as `safe-command-validation`.

## Frontend changes

No frontend source changes were made in this slice.

Existing NewTask rendering already displays `existing_project` as `existing project` through the shared label formatter. No Start Task payload changes were made.

## Safety guarantees

- No DB writes.
- No project creation.
- No run creation.
- No `tool_calls`.
- No tools execution.
- No file scanning.
- No LLM/provider execution.
- No patch proposal.
- No apply patch.
- No run command.
- No analyze result.
- No rollback.
- No shell runner.
- No autonomous mode.
- `backend/src/storage/database.py` was not edited.

## Tests

- `cd backend && .venv/bin/python -m py_compile src/orchestrator/project_intake.py` - passed.
- `cd backend && .venv/bin/pytest -q tests/test_project_intake.py` - `43 passed, 7 subtests passed`.
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py` - passed.
- `cd backend && .venv/bin/pytest -q` - `328 passed, 7 subtests passed`.
- `cd frontend && npx tsc --noEmit` - passed.
- `cd frontend && npm run build` - passed.
- `bash scripts/run_tests.sh` - passed, including backend pytest `328 passed, 7 subtests passed` and frontend TypeScript check.

## Remaining gaps

- Existing project onboarding answers are not persisted.
- Existing project path is not attached to intake responses.
- No frontend project path picker or upload/select-folder UI yet.
- No existing project file scan or project profile inference yet.
- Plan preview is not persisted or attached to project/run.
- Orchestrator does not execute onboarding or plan phases.
- No autonomous mode.

## Recommended next slice

Existing Project Onboarding UI v1.

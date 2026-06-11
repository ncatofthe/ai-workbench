# Existing Project Onboarding UI v1

## Summary

Added a compact advisory Existing Project Onboarding Checklist to the NewTask intake result panel.

The checklist appears only when the intake response has `mode === "existing_project"` and is derived from the returned intake questions. It does not add a new backend feature, stateful answer form, file picker, scanner, or execution flow.

## UI behavior

- Existing-project intake results now show an `Existing Project Onboarding Checklist`.
- Checklist sections are mapped from the current response questions:
  - Project location/path
  - Stack/frameworks
  - What already works
  - What is broken
  - Next development goal
  - Dev/build/test commands
  - DB/env/local services
  - Git status/history
  - Dangerous files/secrets
  - Deployment target
- Each checklist item shows the matching intake question and priority when present.
- If a matching question is not present, the UI marks the item as `not returned`.
- Added advisory safety copy:
  - "Existing project onboarding is advisory only. It does not scan files, create a run, execute tools, or call providers."

## Safety guarantees

- No backend changes.
- No DB writes.
- No project creation.
- No run creation.
- No `tool_calls`.
- No tools execution.
- No file scanning.
- No folder picker.
- No provider/LLM calls.
- No patch/proposal/apply/tests/analyze/rollback.
- No autonomous mode.
- Start Task payload was not changed.
- `backend/src/storage/database.py` was not edited.

## Source changes

- `frontend/src/pages/NewTask.tsx`
- `runs/existing-project-onboarding-ui-v1/final-report.md`

## Tests

- `cd frontend && npx tsc --noEmit` - passed.
- `cd frontend && npm run build` - passed.
- `cd backend && .venv/bin/python -m py_compile src/storage/database.py` - passed.
- `cd backend && .venv/bin/pytest -q` - `328 passed, 7 subtests passed`.
- `bash scripts/run_tests.sh` - passed, including backend pytest `328 passed, 7 subtests passed` and frontend TypeScript check.

## Remaining gaps

- No answer form yet.
- Existing project onboarding answers are not persisted.
- No project path picker or folder selection.
- No project scanning or profile inference.
- Checklist is advisory and does not attach data to a run/project.
- Orchestrator does not consume onboarding answers yet.

## Recommended next slice

Intake/Onboarding Regression Pass v1.

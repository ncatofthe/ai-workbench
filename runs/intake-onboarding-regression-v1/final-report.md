# Intake / Onboarding Regression Pass v1

## Summary

The full intake/onboarding flow is stable after the recent low-risk slices.

No P0/P1/P2/P3 issues were found. No source-code changes were made. This pass created only this report.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| Required project context reviewed | Passed | Reviewed `AI_WORKBENCH_INDEX.md`, `AI_WORKBENCH_VISION.md`, and `AI_WORKBENCH_SAFETY.md`. |
| Questions endpoint source review | Passed | `POST /api/project-intake/questions` validates `idea` and calls `analyze_project_intake`. |
| Brief draft endpoint source review | Passed | `POST /api/project-intake/brief-draft` validates `idea` and calls `draft_project_brief`. |
| Plan preview endpoint source review | Passed | `POST /api/project-intake/plan-preview` validates `idea` and calls `draft_development_plan`. |
| Deterministic helper review | Passed | `project_intake.py` uses stdlib/Pydantic rule-based helpers; no DB/tool/provider/file scanning imports were found. |
| Existing project onboarding coverage | Passed | Tests cover detection phrases and questions for path, stack, works/broken, commands, env, Git, secrets, and deployment. |
| Frontend NewTask flow | Passed | Intake buttons use current prompt; `createRun` payload remains `{ prompt, mode, project_id: projectId }`. |
| Existing Project Checklist visibility | Passed | Checklist renders only when `result.mode === "existing_project"`. |
| Type/API integrity | Passed | Client endpoints and TypeScript response shapes match current backend models; `npx tsc --noEmit` passed. |
| `database.py` untouched for intake | Passed | No intake/onboarding/brief/plan diff found in `backend/src/storage/database.py`. |
| Backend py_compile database.py | Passed | `.venv/bin/python -m py_compile src/storage/database.py`. |
| Backend pytest | Passed | `328 passed, 7 subtests passed`. |
| Frontend TypeScript/build | Passed | `npx tsc --noEmit` and `npm run build` passed. |
| Root test script | Passed | `bash scripts/run_tests.sh` passed. |

## Backend Endpoint Validation

Validated read-only endpoints:

- `POST /api/project-intake/questions`
- `POST /api/project-intake/brief-draft`
- `POST /api/project-intake/plan-preview`

Confirmed by source inspection:

- no DB writes;
- no project creation;
- no run creation;
- no `tool_calls`;
- no tools execution;
- no LLM/provider calls;
- no file scanning;
- no patch/proposal/apply/test/analyze/rollback.

Each endpoint validates a non-empty `idea` and delegates to deterministic helper functions.

## Frontend Flow Validation

Validated NewTask behavior:

- `Analyze idea` sends `{ idea: prompt }`.
- `Draft brief` sends `{ idea: prompt }`.
- `Preview plan` sends the current prompt and optional existing `brief_markdown`.
- Loading and error states exist for all three preview actions.
- Intake, brief, plan, and checklist panels render from response data.
- Existing Project Checklist is derived from returned intake questions.
- Existing Project Checklist appears only for `existing_project` mode.
- The checklist does not save answers, mutate the prompt, scan files, or call additional endpoints.
- Start Task payload remains unchanged: `{ prompt, mode, project_id: projectId }`.

## Existing Project Onboarding Validation

Validated by tests and source inspection:

- existing project detection handles Russian and English existing/half-ready project phrases;
- question output remains bounded by `MAX_TOTAL = 15`;
- onboarding questions cover:
  - project location/path;
  - stack/frameworks;
  - what already works;
  - what is broken;
  - next development goal;
  - dev/build/test commands;
  - DB/env/local services;
  - Git status/history;
  - dangerous files/secrets;
  - deployment target;
- plan preview includes inventory/context/patch/test/final verification phases for existing projects.

## Safety Boundaries

Confirmed:

- no auto proposal;
- no auto apply;
- no auto run-command;
- no auto analyze;
- no auto rollback;
- no shell runner added;
- no external provider execution from intake/onboarding;
- Codex/Claude provider execution remains unrelated to intake/onboarding and stub-only;
- `database.py` was not edited in this pass.

## Issues Found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | Intake/onboarding | No issues found. | No fix needed. |

## Changes Made

No source-code changes.

Created report only:

- `runs/intake-onboarding-regression-v1/final-report.md`

## Recommended Next Slice

Intake/Plan Persistence Decision v1.

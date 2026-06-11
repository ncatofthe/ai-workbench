# Intake Flow Regression Pass v1

## Summary

The intake flow can be considered stable. No P0/P1 issues were found, and no source-code changes were made.

The read-only intake endpoints remain deterministic and bounded. The NewTask intake UI does not alter the existing Start Task flow, does not change the create-run payload, and does not persist answers or brief drafts.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| Required project context reviewed | Passed | Read `AI_WORKBENCH_INDEX.md`, `AI_WORKBENCH_VISION.md`, `AI_WORKBENCH_ROADMAP.md`, and `AI_WORKBENCH_SAFETY.md`. |
| `POST /api/project-intake/questions` source review | Passed | Validates non-empty `idea`, then calls deterministic `analyze_project_intake`. |
| `POST /api/project-intake/brief-draft` source review | Passed | Validates non-empty `idea`, then calls deterministic `draft_project_brief`. |
| Backend deterministic behavior | Passed | `project_intake.py` imports only stdlib enum/re/uuid/typing and Pydantic; no DB/tools/providers/file scanning. |
| Question bound | Passed | `MAX_TOTAL = 15`; tests assert question count and brief open questions stay bounded. |
| Existing project mode | Passed | Covered by source review and tests for explicit mode, attached project flag, and keyword detection. |
| Frontend NewTask create flow | Passed | `createRun({ prompt, mode, project_id: projectId })` is unchanged and does not include intake/brief data. |
| Frontend API clients | Passed | `analyzeProjectIntake` uses `/api/project-intake/questions`; `draftProjectBrief` uses `/api/project-intake/brief-draft`. |
| Frontend types/imports | Passed | TypeScript check passed; no broken imports or unused TS symbols reported. |
| `database.py` intake diff check | Passed | No intake/brief/question/project_intake diff found in `backend/src/storage/database.py`. |
| Backend py_compile database.py | Passed | `.venv/bin/python -m py_compile src/storage/database.py`. |
| Backend pytest | Passed | `320 passed`. |
| Frontend TypeScript | Passed | `npx tsc --noEmit` passed. |
| Frontend production build | Passed | `npm run build` passed. |
| Root test script | Passed | `bash scripts/run_tests.sh` passed, including backend pytest `320 passed` and frontend TypeScript check. |

## Backend endpoint validation

Validated endpoints:

- `POST /api/project-intake/questions`
- `POST /api/project-intake/brief-draft`

Both endpoints are read-only by source inspection:

- no DB reads/writes in the endpoint bodies;
- no project creation;
- no run creation;
- no `tool_calls`;
- no tools execution;
- no LLM/provider execution;
- no patch/proposal/apply/test/analyze/rollback.

The endpoint bodies only validate that `idea` is non-empty and delegate to pure intake helper functions.

## Frontend flow validation

Validated NewTask behavior:

- `Analyze idea` uses the current `prompt` text.
- `Draft brief` uses the current `prompt` text.
- Empty prompt disables both intake buttons in the UI.
- Backend validation handles empty/whitespace ideas with a 400 response.
- Loading and error state are local to the intake/brief actions.
- Result panels render from typed response data without mutating task creation state.
- `Start Task` remains controlled by `prompt`, `projectId`, and `loading`.
- `Start Task` payload remains `{ prompt, mode, project_id: projectId }`.
- Intake results do not block submit.
- Brief draft results do not block submit.
- Answers are not persisted.
- Brief drafts are not persisted.

## Safety boundaries

Confirmed:

- no auto proposal;
- no auto apply;
- no auto run-command;
- no auto analyze;
- no auto rollback;
- no shell runner;
- no external provider execution;
- Codex/Claude providers remain unrelated to intake and are not called by intake endpoints;
- `backend/src/storage/database.py` was not edited.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | Intake flow | No P0/P1/P2/P3 issues found in this regression pass. | No fix needed. |

## Changes made

No source-code changes.

Created report only:

- `runs/intake-flow-regression-v1/final-report.md`

## Recommended next slice

Orchestrator Planning from Intake v1.

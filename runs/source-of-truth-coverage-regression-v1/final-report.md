# Source of Truth / Coverage Regression Pass v1

## Summary

The source-of-truth and requirement coverage preview flow can be considered stable after the recent read-only slices.

No P0/P1/P2/P3 issues were found. No source-code changes were made.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| Backend endpoint inspection | Passed | Project-intake endpoints remain thin read-only wrappers around deterministic helpers. |
| Deterministic helper inspection | Passed | Intake, brief, plan, source-of-truth, and coverage builders are rule-based. |
| Source-of-truth response shape | Passed | Includes mission, source type, requirements, constraints, forbidden changes, acceptance criteria, assumptions, open questions, anti-drift rules, and validation. |
| Coverage response shape | Passed | Includes counts, covered/partial/missing/unclear requirements, unlinked phases, drift risks, and recommended next step. |
| NewTask flow inspection | Passed | Preview buttons use current prompt text and store results only in component state. |
| Start Task payload | Passed | Still calls `createRun({ prompt, mode, project_id: projectId })`. |
| Backend py_compile database.py | Passed | No source-of-truth/coverage changes in `database.py`. |
| Backend pytest | Passed | `406 passed, 24 subtests passed`. |
| Frontend TypeScript/build | Passed | `npx tsc --noEmit` and `npm run build` passed. |
| Root test runner | Passed | `bash scripts/run_tests.sh` passed. |

## Backend endpoint validation

Validated these read-only endpoints:

- `POST /api/project-intake/questions`
- `POST /api/project-intake/brief-draft`
- `POST /api/project-intake/plan-preview`
- `POST /api/project-intake/source-of-truth-preview`
- `POST /api/project-intake/coverage-preview`

Confirmed:

- no DB writes;
- no project/run creation;
- no tool_calls creation;
- no assigned team creation;
- no tools execution;
- no LLM/provider calls;
- no file scanning;
- no patch/proposal/apply/test/analyze/rollback.

Note: `backend/src/api/routes.py` has global imports for DB/tools/providers used by unrelated endpoints, but the inspected project-intake endpoints only validate `idea` and return deterministic helper outputs.

## Source-of-truth validation

Confirmed source-of-truth preview includes:

- mission / product goal;
- input source type;
- requirements;
- constraints;
- forbidden changes;
- acceptance criteria;
- assumptions;
- open questions;
- anti-drift rules;
- validation gaps/warnings;
- requirement coverage summary from the base contract.

The builder is deterministic and uses existing intake, brief, and plan preview helpers. It does not access DB, scan files, call providers, or mutate state.

## Coverage validation

Confirmed coverage preview includes:

- requirements total;
- covered requirements;
- partially covered requirements;
- missing requirements;
- unclear requirements;
- unlinked plan phases;
- drift risks;
- missing mandatory requirement detection;
- existing project preservation constraints in the source context;
- recommended next step.

The coverage builder uses deterministic source refs/tags and keyword overlap. It does not execute or validate commands, apply patches, run tests, or persist results.

## Frontend flow validation

Confirmed in `NewTask.tsx`:

- `Analyze idea` sends current `prompt`;
- `Draft brief` sends current `prompt`;
- `Preview plan` sends current `prompt`;
- `Preview source of truth` sends current `prompt` plus optional already-previewed brief/plan data;
- `Preview coverage` sends current `prompt` plus optional already-previewed plan/source-of-truth data;
- loading/error states exist for each preview action;
- result panels render lists and empty states safely;
- existing project checklist still appears only for `existing_project`;
- preview results are React state only;
- prompt is not mutated by previews;
- answers/brief/plan/source-of-truth/coverage are not persisted;
- Start Task payload remains unchanged.

## Safety boundaries

Confirmed:

- no auto proposal;
- no auto apply;
- no auto run-command;
- no auto analyze;
- no auto rollback;
- no shell runner added;
- no external provider execution;
- Codex/Claude providers remain outside this flow and stub-only per current baseline;
- `database.py` was not edited for this pass.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | None | No issues found. | No action needed. |

## Changes made

No source-code changes.

Created this report only:

- `runs/source-of-truth-coverage-regression-v1/final-report.md`

## Recommended next slice

Confirmed Plan to Run Preview v1

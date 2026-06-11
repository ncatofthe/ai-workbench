# Project Source of Truth Contract v1

## Summary

Added a pure source-of-truth contract layer for project mission, requirements, constraints, acceptance criteria, and anti-drift checks.

This contract is intended to help future agents stay aligned with the original idea, client ТЗ/КП, existing project goal, or user intent. It does not implement DB storage, API endpoints, UI, file scanning, tool execution, provider calls, or autonomous behavior.

## Contract models

Added `backend/src/orchestrator/source_of_truth_contract.py` with enums:

- `ProjectInputSourceType`
- `RequirementPriority`
- `RequirementStatus`
- `DriftRiskLevel`
- `AcceptanceStatus`

Added models:

- `ProjectMissionContract`
- `ProjectRequirementContract`
- `ProjectConstraintContract`
- `ProjectAcceptanceCriterion`
- `ProjectAntiDriftRule`
- `ProjectSourceOfTruthContract`
- `SourceOfTruthValidationResult`
- `RequirementCoverageItem`
- `RequirementCoverageMatrix`

Added pure helpers:

- `validate_source_of_truth_contract(...)`
- `summarize_source_of_truth(...)`
- `build_requirement_coverage_matrix(...)`
- `detect_drift_risk(...)`

## Supported input scenarios

The contract supports:

- client ТЗ / specification: `client_spec`
- commercial proposal / КП: `commercial_proposal`
- existing unfinished project: `existing_project`
- new idea from scratch: `new_idea`
- mixed sources: `mixed`
- unknown source: `unknown`

## Anti-drift rules

Anti-drift support includes:

- explicit forbidden changes;
- forbidden paths from constraints;
- rule-level forbidden patterns;
- requirement-link enforcement for future plan/step items;
- drift risk levels: low, medium, high, critical.

Validation flags:

- empty mission;
- missing target users;
- missing mandatory requirements;
- missing acceptance criteria;
- conflicting requirements;
- unknown requirement priorities;
- unsafe/secret-like source metadata;
- proposed plan/step with no linked requirement;
- proposed change touching forbidden areas.

## Requirement coverage model

`build_requirement_coverage_matrix(...)` maps future plan item IDs to requirement IDs and returns:

- per-requirement coverage item;
- missing requirement IDs;
- unlinked plan item IDs;
- coverage score;
- drift risk.

Coverage now marks uncovered active requirements as missing, except `wont` or rejected requirements.

## Safety guarantees

Confirmed for this slice:

- no DB implementation;
- no migrations;
- no `database.py` edits;
- no `routes.py` edits;
- no storage helpers;
- no API endpoints;
- no UI;
- no file scanning;
- no tool execution;
- no provider/LLM calls;
- no project/run/tool_call creation;
- no patch/apply/tests/analyze/rollback;
- no autonomous mode;
- no git commit.

## Source changes

- Added `backend/src/orchestrator/source_of_truth_contract.py`
- Added `backend/tests/test_source_of_truth_contract.py`
- Added `runs/project-source-of-truth-contract-v1/final-report.md`

## Tests

Passed:

- `cd backend && .venv/bin/python -m py_compile src/storage/database.py`
- `cd backend && .venv/bin/pytest -q`
  - `392 passed, 24 subtests passed`
- `cd frontend && npx tsc --noEmit`
- `cd frontend && npm run build`
- `bash scripts/run_tests.sh`
  - backend syntax checks passed
  - pytest passed: `392 passed, 24 subtests passed`
  - frontend TypeScript check passed

## Remaining gaps

- Source-of-truth contract is not persisted.
- No API endpoint exists.
- No UI preview exists.
- Intake/brief/plan output is not automatically converted into source-of-truth yet.
- Orchestrator does not consume coverage/drift checks yet.
- No confirmed plan-to-run flow exists.
- No autonomous mode.

## Recommended next slice

Recommended next slice: `Requirement Coverage Matrix v1`.

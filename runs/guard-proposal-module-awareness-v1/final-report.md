# Guard/Proposal Module Awareness v1

## Summary

Implemented bounded, read-only module awareness for guarded patch proposal creation. Successful `propose-patch` responses now include compact module-map context when an active Project Module Map exists, helping the operator see touched modules, expected modules, module risks, test hints, and advisory warnings.

This is warning-only context. It does not bypass guard validation, does not create proposals automatically, does not apply patches, and does not run commands or providers.

## Module Awareness Shape

Added `ModuleAwarenessResult` with:

- `has_active_module_map`
- `module_map_version`
- `touched_modules`
- `expected_modules`
- `touched_files`
- `expected_files`
- `matched_requirement_ids`
- `module_risks`
- `module_test_hints`
- `warnings`
- `confidence`

Module entries are compact dictionaries with module identity, type, bounded paths/key files, related requirements, risks, test hints, and confidence.

## Touched/Expected Matching Logic

The helper `build_patch_proposal_module_awareness(...)` selects:

- touched modules from proposed patch file paths via `find_modules_for_paths`
- expected modules from requirement IDs parsed from `RunStep.input`
- keyword fallback from step title/input only when requirement IDs do not produce expected modules

Keyword fallback covers auth/login, task/workflow, finance/billing, upload/file, review/approval, reports/analytics, database/schema/sql, frontend/page/component/ui, and contracts/types/enums.

## Warnings Behavior

Warnings are advisory only:

- proposed files do not match any known module
- touched modules do not overlap expected modules
- expected modules exist but no touched module matched
- touched module has recorded risks
- proposal touches sensitive auth/security/database/schema-related modules

Module mismatch does not block proposal creation in v1.

## Proposal Endpoint Behavior

`POST /api/projects/{project_id}/tools/propose-patch` now attaches `module_awareness` after existing guard validation succeeds and after the normal proposal preview is created.

Validation failure behavior is unchanged: failed guard validation still returns an error before proposal tool_call creation.

## Guard/Proposal Validation Behavior

The existing guard validation endpoint was intentionally left unchanged because it has a stable exact response contract in tests. Module awareness is currently attached to successful proposal responses/tool_call output only.

## Frontend Changes

RunDetail now shows a compact read-only Module Awareness block in the patch proposal preview:

- touched modules
- expected modules
- warnings
- module risks
- module test hints

No buttons, execution, scan, save, provider call, or patch mutation were added.

## Tests Added

Added `backend/tests/test_guard_proposal_module_awareness.py` covering:

- no active module map compatibility
- path-based touched module matching
- requirement-based expected module matching
- mismatch warnings
- unknown-file warnings
- risky/sensitive module warnings
- module risks and test hints
- bounded output
- no file-content leakage
- successful proposal tool_call creation remains normal
- failed validation creates no proposal tool_call
- no-guard override behavior remains explicit
- guard validation response fields remain compatible
- apply `confirm=true` gate remains unchanged
- module awareness is stored in proposal tool_call output
- static safety of the awareness helper

## Safety Boundaries

- No DB schema changes.
- No database.py edits in this slice.
- No engine.py edits in this slice.
- No provider edits or provider calls.
- No file content reads in the module awareness helper.
- No subprocess/shell execution.
- No `execute_run`.
- No `asyncio.create_task`.
- No auto-proposal.
- No auto-apply.
- No auto-rollback.
- No guard or approval bypass.
- `old_text` / `new_text` remain manually supplied by the operator.

## Files Changed

- `backend/src/models.py`
- `backend/src/storage/module_map_storage.py`
- `backend/src/api/routes.py`
- `backend/tests/test_guard_proposal_module_awareness.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/guard-proposal-module-awareness-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice.
- `backend/src/orchestrator/engine.py`: not touched by this slice.
- Providers: not touched by this slice.

Note: the working tree already contained unrelated dirty files from previous slices; this report reflects changes made for this slice only.

## Exact Check Results

- `py_compile` for `database.py`, `models.py`, `module_map_storage.py`, `routes.py`, and new test: passed.
- `pytest -q tests/test_guard_proposal_module_awareness.py`: 18 passed.
- Targeted guard/module-map suite: 178 passed.
- Targeted workflow compatibility suite: 345 passed.
- Full backend pytest: 1112 passed, 38 subtests passed.
- Frontend `npx tsc --noEmit`: passed.
- Frontend `npm run build`: passed.
- `bash scripts/run_tests.sh`: passed; backend 1112 passed, 38 subtests passed; frontend TypeScript check passed.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: none.
- P3: module awareness is advisory only and may produce heuristic false positives/negatives.

## Known Limitations

- Module mismatch is warning-only in v1.
- Matching is heuristic and deterministic.
- No file content analysis.
- No provider/LLM module classification.
- Module map is not yet a hard guard policy.
- No visual module map editor.

## Recommended Next Slice

Guard/Proposal Module Awareness Regression Pass.

# Delivery Report Module Awareness v1

## Summary

Added read-only module awareness to Delivery Summary / Delivery Report.

The delivery report now aggregates module information already present in existing run metadata:

- proposal `module_awareness`
- proposal `module_policy`
- patch draft `module_context`
- changed files from proposal/apply tool calls
- active Project Module Map matches for changed files and step requirement IDs

This is observability only. It does not enforce module policy, create proposals, apply patches, run tests, call providers, or mutate run/step state.

## Delivery Module Summary Model

Added:

- `StepModuleDeliverySummary`
- `RunModuleDeliverySummary`

Added optional fields:

- `StepDeliverySummary.module_summary`
- `RunDeliverySummary.module_summary`

Run-level summary includes:

- `has_module_data`
- `touched_modules`
- `expected_modules`
- `unknown_files`
- `sensitive_modules`
- `warning_count`
- `blocked_policy_count`
- `recommended_tests`
- `per_step`

All defaults are backward-compatible and empty-list safe.

## Aggregation Logic

Added `build_delivery_module_summary(...)` in `backend/src/api/routes.py`.

It:

- reads only already-loaded run, step, and tool_call metadata
- uses proposal `module_awareness` and `module_policy` when available
- uses patch draft `module_context` when available
- maps changed files to modules using the active module map when needed
- maps step requirement IDs to expected modules when the active module map exists
- aggregates per-step and run-level module notes
- caps modules, files, warnings, and test hints

It does not read file contents, write DB state, create tool calls, call providers, or execute commands.

## Markdown Report Changes

Delivery markdown now includes `## Module Awareness` with:

- touched modules
- expected modules
- unknown files
- sensitive modules
- module warning count
- blocked policy verdict count
- recommended module-level tests
- per-step module notes

Blocked module policy verdicts are shown as report information only and do not alter delivery readiness.

## Frontend Display Changes

`RunDetail` DeliveryPanel now shows a compact read-only Module Awareness block when module data exists.

It displays:

- touched modules
- expected modules
- sensitive modules
- warning count
- blocked policy count
- recommended tests

No buttons, execution controls, scans, provider calls, or mutations were added.

## Tests Added

Added `backend/tests/test_delivery_report_module_awareness.py`.

Coverage includes:

- backward-compatible delivery summary without module data
- touched/expected module aggregation
- unknown file aggregation
- risk/test-hint aggregation
- warning and blocked policy counts
- per-step module summary
- markdown Module Awareness section
- blocked policy remains report-only
- readiness is not blocked solely by classification-only module policy
- no file-content leakage
- delivery endpoints create no tool calls
- delivery report does not mutate run/step status
- static runtime-boundary scan for the module summary helper

## Safety Boundaries

Confirmed:

- no DB schema changes
- no migrations
- no provider calls
- no file content reads
- no command execution
- no `execute_run`
- no `asyncio.create_task`
- no delivery-created `tool_calls`
- no auto-proposal
- no auto-apply
- no auto-rollback
- no guard bypass
- no approval bypass
- module policy remains classification/reporting-only

## Files Changed

Changed in this slice:

- `backend/src/models.py`
- `backend/src/api/routes.py`
- `backend/tests/test_delivery_report_module_awareness.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/delivery-report-module-awareness-v1/final-report.md`

The working tree was already dirty from prior accepted slices.

## Protected Files

- `backend/src/storage/database.py`: not touched in this slice
- `backend/src/orchestrator/engine.py`: not touched in this slice
- providers: not touched in this slice

## Exact Check Results

Backend compile:

- `python -m py_compile src/storage/database.py src/models.py src/storage/module_map_storage.py src/api/routes.py tests/test_delivery_report_module_awareness.py`: passed

New tests:

- `pytest -q tests/test_delivery_report_module_awareness.py`: `20 passed`

Targeted related backend suite:

- `tests/test_full_delivery_loop.py`: `55 passed`
- `tests/test_module_aware_guard_policy.py`: `19 passed`
- `tests/test_guard_proposal_module_awareness.py`: `18 passed`
- `tests/test_guarded_patch_proposal.py`: `17 passed`
- `tests/test_guard_result_proposal_validation.py`: `17 passed`
- `tests/test_apply_guard_revalidation.py`: `11 passed`
- `tests/test_module_map_patch_draft_context.py`: `26 passed`
- `tests/test_agent_result_patch_draft_bridge.py`: `36 passed`
- `tests/test_module_map_agent_context_wiring.py`: `30 passed`
- `tests/test_project_module_map.py`: `41 passed`
- `tests/test_agent_execution_harness.py`: `46 passed`
- `tests/test_source_of_truth_run_creation_wiring.py`: `29 passed`
- `tests/test_persistent_source_of_truth.py`: `31 passed`
- `tests/test_rundetail_ux_consolidation.py`: `15 passed`
- `tests/test_real_project_dogfooding.py`: `23 passed`
- `tests/test_dogfooding_full_cycle.py`: `31 passed`
- `tests/test_bounded_autonomous_patch_test_fix_loop.py`: `36 passed`
- `tests/test_approval_gated_automation.py`: `41 passed`
- `tests/test_automation_runner.py`: `18 passed`
- `tests/test_semi_auto_operator_queue.py`: `20 passed`

Full backend:

- `pytest -q`: `1151 passed, 38 subtests passed`

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed

Full runner:

- `bash scripts/run_tests.sh`: passed
- Backend inside runner: `1151 passed, 38 subtests passed`
- Frontend TypeScript check inside runner: passed

## P0/P1/P2/P3 Issues

- P0: none
- P1: none
- P2: none
- P3: none

## Known Limitations

- module policy is still classification/reporting only
- module mismatch does not affect readiness as a hard gate
- heuristic matching only
- no file content analysis
- no provider/LLM classification
- no visual module map editor

## Recommended Next Slice

Delivery Report Module Awareness Regression Pass.

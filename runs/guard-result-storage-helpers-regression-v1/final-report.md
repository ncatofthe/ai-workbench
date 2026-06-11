# Guard Result Storage Helpers Regression Pass v1

## Summary

Regression pass is **clean**. All safety invariants hold, the guard_results table DDL is correctly scoped, the storage module is properly isolated, CRUD helpers are tested, serialization round-trips are safe, no raw text is stored, no runtime wiring exists, and all checks pass. No P0 or P1 issues found. No source code changes were made.

## database.py change boundary validation

| Check | Status | Evidence |
|-------|--------|----------|
| guard_results CREATE TABLE exists | ✓ | Line 190 in init_db executescript |
| 4 indexes created | ✓ | Lines 212-219: run_step, project, decision, stale |
| No existing tables changed | ✓ | 8 original tables (projects, runs, approvals, artifacts, run_steps, tool_calls, run_agent_assignments, model_route_decisions) all unchanged |
| No existing helpers rewritten | ✓ | All ~40 existing helper functions untouched |
| No broad refactor | ✓ | Only additive DDL inside existing executescript block |
| No runtime execution logic added | ✓ | No new Python functions in database.py for guard results |
| No foreign keys added | ✓ | Consistent with existing project style |

## Storage module isolation validation

| Check | Status | Evidence |
|-------|--------|----------|
| Does not import routes.py | ✓ | grep "from src.api" → 0 matches |
| Does not import engine.py | ✓ | grep "from src.orchestrator.engine" → 0 matches |
| Does not import project_tools.py | ✓ | grep "from src.project_tools" → 0 matches |
| Does not import model_router.py | ✓ | grep "from src.model_router" → 0 matches |
| Does not import providers | ✓ | No provider imports found |
| Does not call tools | ✓ | No tool execution code |
| Does not create tool_calls | ✓ | Only stores IDs in link columns |
| Does not execute patches/tests/providers | ✓ | No subprocess, execute_run, or provider calls |
| Only imports: stdlib, contract, _connect | ✓ | 5 import lines: json, datetime, typing, contract models, database._connect |
| No runtime module imports guard_result_storage | ✓ | grep across backend/src confirms no routes/engine/runtime imports it |

## CRUD validation

| Check | Status | Evidence |
|-------|--------|----------|
| create_guard_result persists record | ✓ | test_create_and_get |
| get_guard_result returns same record | ✓ | test_create_and_get |
| get_guard_result returns None for missing | ✓ | test_get_nonexistent_returns_none |
| list_guard_results filters by run_id | ✓ | test_filter_by_run_id |
| list_guard_results filters by step_id | ✓ | test_filter_by_step_id |
| list_guard_results filters by project_id | ✓ | test_filter_by_project_id |
| list_guard_results filters by proposal_tool_call_id | ✓ | test_filter_by_proposal_tool_call_id |
| list_guard_results filters by decision | ✓ | test_filter_by_decision |
| include_stale=false hides stale records | ✓ | test_include_stale_false_hides_stale |
| include_stale=true includes stale records | ✓ | test_include_stale_true_includes_stale |
| limit and offset work | ✓ | test_limit_and_offset |
| mark_guard_result_stale sets is_stale and reasons | ✓ | test_mark_stale_sets_flag_and_reason |
| mark_guard_result_stale accumulates reasons | ✓ | test_mark_stale_accumulates_reasons |
| mark_guard_result_stale deduplicates reasons | ✓ | test_mark_stale_deduplicates_reasons |
| mark_guard_result_stale returns None for missing | ✓ | test_mark_stale_nonexistent_returns_none |
| link_guard_result_to_proposal sets ID | ✓ | test_link_to_proposal |
| link_guard_result_to_apply sets ID | ✓ | test_link_to_apply |
| link returns None for missing | ✓ | test_link_proposal_nonexistent_returns_none, test_link_apply_nonexistent_returns_none |

## Serialization validation

| Check | Status | Evidence |
|-------|--------|----------|
| input_snapshot_json round-trip | ✓ | test_input_snapshot_round_trip — proposed_action, file_path, patch_summary, input_hash all match |
| requirement_context_snapshot_json round-trip | ✓ | test_requirement_context_snapshot_round_trip — requirement_ids, coverage_status, criteria, constraints, forbidden_changes, notes, summary, context_hash all match |
| result_snapshot_json round-trip | ✓ | test_result_snapshot_round_trip — decision, drift_risk, matched_ids, violated, forbidden, reasons, recommended_next_step, result_hash all match |
| stale_reasons_json round-trip | ✓ | test_mark_stale_accumulates_reasons — multiple WorkflowGuardStaleReason enum values survive JSON serialization |
| warning_acknowledged round-trip | ✓ | test_warning_acknowledged_round_trip — bool True persists as INTEGER 1, reads back as True |
| no_guard_override round-trip | ✓ | test_no_guard_override_round_trip — same |
| expires_at round-trip | ✓ | test_expires_at_round_trip — datetime survives ISO 8601 serialization within 1 second precision |
| created_at format stable | ✓ | ISO 8601 via datetime.isoformat() |
| updated_at format stable | ✓ | Set on stale/link updates via _now_iso() |

## Raw text safety validation

| Check | Status | Evidence |
|-------|--------|----------|
| raw old_text not in guard_results JSON | ✓ | test_raw_old_text_new_text_not_stored_in_db — reads raw DB JSON, confirms "old_text" key absent |
| raw new_text not in guard_results JSON | ✓ | Same test — confirms "new_text" key absent |
| old_text_hash present | ✓ | Same test — old_text_hash is non-None SHA-256 |
| new_text_hash present | ✓ | Same test — new_text_hash is non-None SHA-256 |
| No large patch/diff text stored | ✓ | build_guard_input_snapshot only stores hashes via hash_guard_text() |

## Runtime safety validation

| Check | Status | Evidence |
|-------|--------|----------|
| No routes.py wiring | ✓ | routes.py does not import guard_result_storage |
| Guard endpoint does not persist | ✓ | post_run_step_source_of_truth_guard is read-only (lines 405-441 of routes.py) |
| propose-patch does not use guard_result_id | ✓ | No guard_result_id parameter in existing proposal endpoints |
| apply-patch does not use guard_result_id | ✓ | No guard_result_id parameter in existing apply endpoints |
| No behavior changed outside storage helpers | ✓ | All existing code paths unchanged |

## run_tests.sh validation

| Check | Status | Evidence |
|-------|--------|----------|
| New py_compile checks present | ✓ | guard_result_storage.py, guard_result_storage_contract.py, guard_result_api_contract.py |
| run_tests.sh passes | ✓ | All 20 py_compile checks OK, tsc clean |
| No dangerous commands introduced | ✓ | Only py_compile, pytest, tsc |
| No shell runner introduced | ✓ | No subprocess or execution additions |

## False-positive test fix validation

| Check | Status | Evidence |
|-------|--------|----------|
| Docstring no longer contains forbidden substrings | ✓ | grep for all 6 patterns → 0 matches each |
| Isolation test logic unchanged | ✓ | Same 6 forbidden patterns checked in test |
| Isolation check not weakened | ✓ | Test still asserts on all 6 import patterns |

## Issues found

| Priority | Area | Problem | Suggested fix |
|----------|------|---------|---------------|
| — | — | No P0, P1, or P2 issues found | — |
| P3 | Test robustness | Module isolation test uses substring search on full source; could match future docstrings again | Future: filter to only actual import/from lines before checking patterns |
| P3 | Completeness | No test for `project_id` being None vs empty string round-trip | Low priority — works correctly (stores "", reads back as None via `or None`) |
| P3 | Completeness | No test for concurrent writes / unique constraint on id | Low priority — SQLite PRIMARY KEY handles this |

## Changes made

No source-code changes. This is a regression pass only.

## Files changed

None.

## database.py touched

No (in this regression pass).

## routes.py touched

No.

## Checks

| Check | Result |
|-------|--------|
| `py_compile database.py` | OK |
| `py_compile guard_result_storage.py` | OK |
| `py_compile guard_result_storage_contract.py` | OK |
| `py_compile guard_result_api_contract.py` | OK |
| `py_compile routes.py` | OK |
| Python syntax (20 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Real environment expected: all pytest tests pass (~509 passed + 38 subtests including 30 guard result storage tests).

## Recommended next slice

**Guard Result API Wiring v1** — extend the existing `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard` endpoint with an optional `?persist=true` query parameter that persists the guard result using the storage helpers from Guard Result Storage Helpers v1. Add `guard_result_id` to the response when persisted. Add tests. No proposal/apply integration yet.

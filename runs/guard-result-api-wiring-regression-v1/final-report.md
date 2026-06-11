# Guard Result API Wiring Regression Pass v1

## Summary

Regression pass is **clean**. All safety invariants hold, persist=false remains read-only, persist=true correctly persists exactly one audit record, no execution occurs, no proposal/apply integration exists, and all checks pass. No P0 or P1 issues found. No source code changes were made.

## Default persist=false validation

| Check | Status | Evidence |
|-------|--------|----------|
| persist omitted → read-only | ✓ | Line 450-451: persisted_flag=False, guard_result_id=None; `if persist:` block skipped |
| persist=false explicit → read-only | ✓ | Query(False) default; test_persist_false_explicit |
| No guard_results row created | ✓ | test_persist_false_no_guard_results_rows — COUNT=0 |
| Response includes persisted=false | ✓ | test_default_no_persist_param — data["persisted"] is False |
| guard_result_id is null | ✓ | test_default_no_persist_param — data["guard_result_id"] is None |
| Frontend compatibility | ✓ | New fields have defaults (False, None) — existing frontend ignores them |

## persist=true validation

| Check | Status | Evidence |
|-------|--------|----------|
| Guard evaluated exactly as before | ✓ | Lines 440-448: parse + evaluate happen before persist block |
| Exactly one guard_results row | ✓ | test_persist_true_creates_one_guard_result — COUNT=1 |
| Response includes persisted=true | ✓ | test_persist_true_returns_persisted |
| Response includes guard_result_id | ✓ | test_persist_true_returns_persisted — non-None, non-empty |
| get_guard_result returns matching record | ✓ | test_persist_true_record_matches_response — record.run_id, step_id, decision match |
| Repeated calls create separate records | ✓ | test_repeated_persist_creates_separate_records — 3 calls → 3 rows, 3 unique IDs |
| Source is run_step_guard | ✓ | test_persist_true_source_is_run_step_guard |
| file_path/patch_summary persisted | ✓ | test_persist_true_with_file_path_and_patch_summary |

## Storage mapping validation

| Check | Status | Evidence |
|-------|--------|----------|
| run_id mapped from path param | ✓ | Line 485: run_id=run_id |
| step_id mapped from path param | ✓ | Line 486: step_id=step_id |
| project_id from run or None | ✓ | Line 487: project_id=run.project_id or None |
| source = run_step_guard | ✓ | Line 491: source=WorkflowGuardSource.RUN_STEP_GUARD |
| input_snapshot built via contract | ✓ | Lines 456-461: build_guard_input_snapshot with req fields |
| requirement_context_snapshot from parsed | ✓ | Lines 463-472: all parsed context fields mapped |
| result_snapshot from evaluation | ✓ | Lines 473-482: all result fields mapped |
| decision from result.decision.value | ✓ | Line 474: string value passed to builder |
| drift_risk from result.drift_risk | ✓ | Line 475 |
| Raw old_text NOT stored | ✓ | test_persist_true_stores_input_hashes_not_raw_text — "old_text" key absent from JSON |
| Raw new_text NOT stored | ✓ | Same test — "new_text" key absent |
| Hashes stored instead | ✓ | Same test — old_text_hash and new_text_hash are non-None |
| No full patch/diff stored | ✓ | build_guard_input_snapshot only stores proposed_action, file_path, patch_summary, hashes |

## Runtime safety validation

| Check | Status | Evidence |
|-------|--------|----------|
| No execute_run | ✓ | Not present in endpoint |
| No asyncio.create_task | ✓ | Not present in endpoint |
| No provider calls | ✓ | No provider imports used in persist block |
| No tool calls | ✓ | test_persist_true_no_tool_calls — list_tool_calls_for_run returns 0 |
| No patch proposals created | ✓ | No create_tool_call or propose-patch in endpoint |
| No patches applied | ✓ | No apply logic |
| No commands/tests run | ✓ | No subprocess calls |
| Run status unchanged | ✓ | test_persist_true_run_status_unchanged |
| Step status unchanged | ✓ | test_persist_true_step_status_unchanged |

## Proposal/apply isolation validation

| Check | Status | Evidence |
|-------|--------|----------|
| propose-patch no guard_result_id | ✓ | grep guard_result_id in routes.py: only in guard endpoint (lines 451, 495, 504) |
| apply-patch no guard_result_id | ✓ | Not referenced in any apply endpoint |
| approvals no guard_result_id | ✓ | Not referenced in approval endpoints |
| models.py no guard_result_id | ✓ | grep returns 0 matches |
| No frontend changes | ✓ | Frontend directory untouched by API wiring slice |

## Error behavior validation

| Check | Status | Evidence |
|-------|--------|----------|
| Invalid run → 404 | ✓ | test_invalid_run_returns_404; line 431-432 checked before persist |
| Invalid step → 404 | ✓ | test_invalid_step_returns_404; line 435-436 checked before persist |
| Empty proposed_action → 400 | ✓ | test_empty_proposed_action_returns_400; line 437-438 checked before persist |
| Persist does not mask errors | ✓ | All error checks at lines 430-438 happen before `if persist:` block at line 453 |
| Storage failure handling | Not hardened | create_guard_result exceptions would propagate as 500. Documented as P3 future hardening. |

## Module boundary validation

| Check | Status | Evidence |
|-------|--------|----------|
| guard_result_storage.py isolated | ✓ | Imports: stdlib + contract + database._connect only |
| routes.py imports minimal | ✓ | Lines 84-93: contract builders + create_guard_result only |
| No circular imports | ✓ | guard_result_storage does not import routes; routes imports storage |
| database.py unchanged | ✓ | No edits in this regression pass or wiring slice |

## Issues found

| Priority | Area | Problem | Suggested fix |
|----------|------|---------|---------------|
| — | — | No P0 or P1 issues | — |
| P3 | Imports | WorkflowGuardDecision and WorkflowGuardDriftRisk imported in routes.py but not directly used (values passed as strings) | Future: remove unused imports or use them directly |
| P3 | Error handling | create_guard_result failure (e.g., duplicate ID, DB locked) would propagate as HTTP 500 | Future: add try/except with structured error response |
| P3 | Completeness | persist=true with blocked/warning decisions not explicitly tested as separate test cases | Low priority — test_persist_true_record_matches_response covers the actual decision mapping |

## Changes made

No source-code changes. This is a regression pass only.

## Files changed

None.

## database.py touched

No.

## routes.py touched

No (in this regression pass).

## Checks

| Check | Result |
|-------|--------|
| `py_compile database.py` | OK (untouched) |
| `py_compile routes.py` | OK |
| `py_compile project_intake.py` | OK |
| `py_compile guard_result_storage.py` | OK |
| Python syntax (20 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Real environment expected: all pytest tests pass (527 passed + 38 subtests).

## Recommended next slice

**Guard Result List/Get API v1** — add read-only endpoints `GET /api/guard-results?run_id=X&step_id=Y` and `GET /api/guard-results/{id}` using existing storage helpers. No mutations, no execution.

Or **Guard Result Proposal Link Decision v1** — decide how guard_result_id should be accepted and validated in future propose-patch requests.

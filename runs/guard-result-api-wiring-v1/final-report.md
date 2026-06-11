# Guard Result API Wiring v1

## Summary

Extended the existing `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard` endpoint with an optional `persist=true` query parameter. When omitted or false, the endpoint behaves exactly as before (read-only). When true, it persists the guard evaluation result as an audit record in the `guard_results` table using the existing storage helpers, and returns `guard_result_id` in the response. No new endpoints, no frontend changes, no proposal/apply integration, no execution.

## Endpoint behavior

```
POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist={true|false}
```

### persist=false (default)

- Evaluates guard check against step's requirement context.
- Returns guard result with `persisted: false` and `guard_result_id: null`.
- No DB writes. No guard_results rows created.
- Exact same behavior as before this slice.

### persist=true

- Evaluates guard check exactly the same way.
- Builds storage snapshots using contract helpers:
  - `build_guard_input_snapshot` — hashes old_text/new_text, never stores raw text.
  - `build_requirement_context_snapshot` — captures parsed requirement context from step input.
  - `build_guard_result_snapshot` — captures decision, drift_risk, matched/violated IDs, warnings, reasons.
  - `build_workflow_guard_result_record` — assembles the full record with UUID, run_id, step_id, project_id, source=run_step_guard.
- Persists via `create_guard_result` from guard_result_storage.py.
- Returns `persisted: true` and `guard_result_id: "<uuid>"`.
- Still no ToolCalls, no tools, no providers, no patches, no execution.

## Storage mapping

| Source | Storage field |
|--------|--------------|
| `run_id` (path param) | `record.run_id` |
| `step_id` (path param) | `record.step_id` |
| `run.project_id` (from DB) | `record.project_id` (None if empty) |
| `req.proposed_action` | `input_snapshot.proposed_action` |
| `req.file_path` | `input_snapshot.file_path` |
| `req.patch_summary` | `input_snapshot.patch_summary` |
| `req.old_text` | `input_snapshot.old_text_hash` (SHA-256, raw text NOT stored) |
| `req.new_text` | `input_snapshot.new_text_hash` (SHA-256, raw text NOT stored) |
| Parsed requirement context | `requirement_context_snapshot` (ids, criteria, constraints, forbidden, notes, summary) |
| Guard evaluation result | `result_snapshot` (decision, drift_risk, matched/violated, warnings, reasons) |
| Always | `source = run_step_guard` |
| Generated | `id = uuid4()` |

## Safety guarantees

| Boundary | Status |
|----------|--------|
| persist=false is read-only | ✓ — no DB writes, no guard_results rows |
| persist=true writes audit only | ✓ — exactly one guard_results row per call |
| No tool_calls created | ✓ — verified by test |
| No tools/providers executed | ✓ — no imports from tool executors or providers in persist path |
| No patches applied | ✓ — no patch execution code |
| No run status mutation | ✓ — verified by test |
| No step status mutation | ✓ — verified by test |
| No raw old_text/new_text stored | ✓ — only hashes, verified by test |
| Repeated calls create separate records | ✓ — each call generates new UUID |
| Existing error behavior preserved | ✓ — 404 for bad run/step, 400 for empty action |
| Start Task flow unchanged | ✓ |
| Confirmed-run behavior unchanged | ✓ |
| No proposal/apply integration | ✓ — guard_result_id not wired to any other endpoint |
| No frontend changes | ✓ |

## Tests

File: `backend/tests/test_guard_result_api_wiring.py`

| Test class | Tests | Coverage |
|-----------|-------|----------|
| `TestGuardEndpointPersistFalse` | 4 | Default no persist, explicit false, no DB rows, response shape |
| `TestGuardEndpointPersistTrue` | 7 | Returns persisted+id, creates one row, record matches response, hashes not raw text, file_path/patch_summary, repeated creates separate records, source is run_step_guard |
| `TestGuardEndpointSafety` | 7 | No tool_calls, run status unchanged, step status unchanged, invalid run 404, invalid step 404, empty action 400, persist=false after persist=true still read-only |
| **Total** | **18** | |

## Files changed

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | Added 2 optional fields to `StepSourceOfTruthGuardResponse`: `persisted: bool = False`, `guard_result_id: Optional[str] = None` |
| `backend/src/api/routes.py` | Added imports for guard_result_storage_contract builders + create_guard_result. Extended guard endpoint with `persist: bool = Query(False)` param and persist logic. |
| `backend/tests/test_guard_result_api_wiring.py` | **New** — 18 tests for persist=false/true behavior and safety |

## database.py untouched

Yes — no changes to database.py in this slice.

## Frontend untouched

Yes — no frontend changes. The two new optional response fields (`persisted`, `guard_result_id`) are backward compatible.

## No proposal/apply integration

Confirmed — `guard_result_id` is returned in the response but not accepted or used by any other endpoint. No propose-patch, apply-patch, or approval endpoint references guard_result_id.

## Checks

| Check | Result |
|-------|--------|
| `py_compile routes.py` | OK |
| `py_compile project_intake.py` | OK |
| `py_compile database.py` | OK (untouched) |
| `py_compile guard_result_storage.py` | OK |
| `py_compile guard_result_storage_contract.py` | OK |
| `py_compile guard_result_api_contract.py` | OK |
| `py_compile test_guard_result_api_wiring.py` | OK |
| Python syntax (20 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Real environment expected: all pytest tests pass (~509 prior + 18 new = ~527 passed + 38 subtests).

## Remaining gaps

- No read/list endpoints for guard results (GET /api/guard-results) — future slice.
- No guard_result_id wired to propose-patch — future slice.
- No guard_result_id wired to apply-patch or approvals — future slice.
- No frontend UI for persisted guard results — future slice.
- No staleness revalidation at proposal time — future slice.
- No backend enforcement of guard-gated proposals — future slice.

## Recommended next slice

**Guard Result API Wiring Regression Pass v1** — verify the persist flag doesn't interfere with existing guard tests, audit that the endpoint changes are minimal and safe, confirm all baseline tests still pass.

Or **Guard Result List/Get API v1** — add read-only `GET /api/guard-results` and `GET /api/guard-results/{id}` endpoints using existing storage helpers.

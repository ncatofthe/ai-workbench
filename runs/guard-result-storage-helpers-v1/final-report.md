# Guard Result Storage Helpers v1

## Summary

Added isolated storage CRUD helpers for persisted Source-of-Truth Guard Results. A dedicated `guard_results` table was added to `init_db()` in database.py (minimal DDL-only touch). All helper functions live in a new isolated module `guard_result_storage.py` that imports only from `database.py` (connection factory) and `guard_result_storage_contract.py` (pure models). No endpoints, no runtime wiring, no frontend changes.

## Table schema added

```sql
CREATE TABLE IF NOT EXISTS guard_results (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    proposal_tool_call_id TEXT,
    apply_tool_call_id TEXT,
    source TEXT NOT NULL,
    decision TEXT NOT NULL,
    drift_risk TEXT NOT NULL,
    input_snapshot_json TEXT NOT NULL,
    requirement_context_snapshot_json TEXT NOT NULL,
    result_snapshot_json TEXT NOT NULL,
    warning_acknowledged INTEGER NOT NULL DEFAULT 0,
    no_guard_override INTEGER NOT NULL DEFAULT 0,
    is_stale INTEGER NOT NULL DEFAULT 0,
    stale_reasons_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    expires_at TEXT
);
```

Indexes:

- `idx_guard_results_run_step` on `(run_id, step_id)`
- `idx_guard_results_project` on `(project_id)`
- `idx_guard_results_decision` on `(decision)`
- `idx_guard_results_stale` on `(is_stale)`

No foreign keys added (consistent with existing project style — no other table uses foreign keys in DDL).

## Storage helper functions added

Module: `backend/src/storage/guard_result_storage.py`

| Function | Description |
|----------|-------------|
| `create_guard_result(record)` | Persist a `WorkflowGuardResultRecord`. Returns the stored record. |
| `get_guard_result(guard_result_id)` | Fetch single record by ID. Returns `None` if not found. |
| `list_guard_results(...)` | List with filters: run_id, step_id, project_id, proposal_tool_call_id, decision, include_stale, limit, offset. Ordered by created_at DESC. |
| `mark_guard_result_stale(guard_result_id, reason, note)` | Mark stale (irreversible). Accumulates and deduplicates reasons. |
| `link_guard_result_to_proposal(guard_result_id, proposal_tool_call_id)` | Store proposal link. Does NOT create tool_calls. |
| `link_guard_result_to_apply(guard_result_id, apply_tool_call_id)` | Store apply link. Does NOT create tool_calls. |

Internal helpers: `_serialize_snapshot`, `_deserialize_*_snapshot`, `_serialize_stale_reasons`, `_deserialize_stale_reasons`, `_record_from_row`, `_parse_optional_datetime`, `_format_optional_datetime`.

## Serialization behavior

- Three nested Pydantic models (`WorkflowGuardInputSnapshot`, `WorkflowGuardRequirementContextSnapshot`, `WorkflowGuardResultSnapshot`) are serialized to JSON TEXT columns via `model_dump(mode="json")`.
- Deserialization uses `model_validate(json.loads(...))`.
- `stale_reasons` list is serialized as JSON array of enum string values.
- Boolean fields (`warning_acknowledged`, `no_guard_override`, `is_stale`) stored as INTEGER (0/1).
- Datetime fields stored as ISO 8601 strings, parsed via `datetime.fromisoformat`.
- All hashes (`input_hash`, `context_hash`, `result_hash`, `old_text_hash`, `new_text_hash`) round-trip correctly.

## Safety guarantees

| Boundary | Status |
|----------|--------|
| No raw old_text/new_text stored | ✓ — contract stores hashes only; verified by test |
| No tool_calls created | ✓ — verified by test |
| No routes/endpoints added | ✓ — routes.py untouched |
| No runtime wiring | ✓ — no engine/project_tools imports |
| No tools/providers execution | ✓ — module import-isolated; verified by test |
| No patch/proposal/apply execution | ✓ — link helpers only store IDs |
| No frontend changes | ✓ |
| No Start Task flow changes | ✓ |
| No confirmed-run behavior changes | ✓ |
| database.py changes limited to DDL | ✓ — only CREATE TABLE + indexes in init_db |

## Tests

File: `backend/tests/test_guard_result_storage.py`

| Test class | Tests | Coverage |
|-----------|-------|----------|
| `TestGuardResultsTableCreation` | 2 | Table exists, indexes exist |
| `TestCreateGuardResult` | 9 | Create+get, input/context/result snapshot round-trips, warning_acknowledged, no_guard_override, expires_at, nonexistent returns None, raw old_text/new_text not in DB |
| `TestListGuardResults` | 8 | List all, filter by run_id/step_id/project_id/decision, stale hidden by default, stale included with flag, limit+offset |
| `TestMarkGuardResultStale` | 4 | Sets flag+reason, accumulates reasons, deduplicates, nonexistent returns None |
| `TestLinkGuardResult` | 5 | Link to proposal, link to apply, nonexistent returns None (×2), filter by proposal_tool_call_id |
| `TestModuleIsolation` | 2 | No tool_calls created, no forbidden imports in source |
| **Total** | **30** | |

## Files changed

| File | Change |
|------|--------|
| `backend/src/storage/database.py` | Added guard_results CREATE TABLE + 4 indexes in init_db (DDL only) |
| `backend/src/storage/guard_result_storage.py` | **New** — isolated CRUD helpers |
| `backend/tests/test_guard_result_storage.py` | **New** — 30 tests |
| `scripts/run_tests.sh` | Added py_compile checks for guard_result_storage, guard_result_storage_contract, guard_result_api_contract |

## Exact database.py change summary

Added inside the existing `init_db()` `executescript(""" ... """)` block, after the `model_route_decisions` indexes:

- `CREATE TABLE IF NOT EXISTS guard_results (...)` — 20 columns
- `CREATE INDEX IF NOT EXISTS idx_guard_results_run_step`
- `CREATE INDEX IF NOT EXISTS idx_guard_results_project`
- `CREATE INDEX IF NOT EXISTS idx_guard_results_decision`
- `CREATE INDEX IF NOT EXISTS idx_guard_results_stale`

No helper functions added to database.py. No imports changed. No other tables modified.

## Confirm routes.py untouched

routes.py was not modified by this slice. All routes.py changes in `git diff` are from prior accepted slices.

## Confirm no endpoints/runtime wiring

No endpoints were added. The storage module is not imported by any route, engine, or runtime module. It exists as a standalone tested module ready for future wiring.

## Checks

| Check | Result |
|-------|--------|
| `py_compile database.py` | OK |
| `py_compile guard_result_storage.py` | OK |
| `py_compile guard_result_storage_contract.py` | OK |
| `py_compile guard_result_api_contract.py` | OK |
| `py_compile routes.py` | OK |
| `py_compile project_intake.py` | OK |
| `py_compile models.py` | OK |
| Python syntax (20 files via run_tests.sh) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Real environment expected: all pytest tests pass (479+ passed + 38 subtests + 30 new guard result storage tests).

## Remaining gaps

- No endpoints — storage helpers exist but nothing calls them from routes.
- No runtime wiring — guard evaluation endpoint does not persist results yet.
- No `guard_result_id` column on `tool_calls` or `approvals` tables — future slice.
- No backend enforcement of guard-gated proposals — future slice.
- No frontend guard persistence UI — future slice.

## Recommended next slice

**Guard Result Storage Helpers Regression Pass v1** — verify new guard_results table doesn't interfere with existing tests, audit isolation boundaries, confirm all 479+ existing tests still pass alongside the 30 new tests, verify no accidental imports or side effects.

Or **Guard Result API Wiring v1** — extend existing guard endpoint with `?persist=true` query parameter, using the storage helpers from this slice.

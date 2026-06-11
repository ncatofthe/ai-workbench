# Guard Result API Wiring Decision v1

## Summary

Architecture decision report for how persisted Guard Results should be wired into real API endpoints, storage, proposal/apply flows, and staleness lifecycle. This is a report-only slice. No source code, database schema, routes, migrations, or runtime behavior was changed.

**Recommended storage approach:** Option D — Hybrid: dedicated guard results storage helpers in an isolated module + proposal/apply link columns.

**Recommended endpoint approach:** Option A — Extend existing guard endpoint with `persist=true` query parameter.

**Recommended proposal policy:** `guard_result_id` required for step-linked proposals with explicit no-guard override and warning acknowledgement.

**Recommended next slice:** Guard Result Storage Helpers v1 (isolated module, no routes.py, minimal database.py touch).

## Current state

| Component | Status |
|-----------|--------|
| Guard evaluation endpoint | `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard` — read-only, no persistence |
| Guard Result Storage Contract | `guard_result_storage_contract.py` — 420 lines, pure models + hash/snapshot/staleness helpers |
| Guard Result API Contract | `guard_result_api_contract.py` — 384 lines, pure request/response models + validation helpers |
| RunDetail guard UI | Manual guard check, result display, prefill patch form |
| Patch proposal | Guard-gated in frontend, no backend enforcement |
| database.py | 1313 lines, 8 tables, ~40 helper functions |
| routes.py | 2951 lines, ~50+ endpoints |
| Backend test baseline | 479 passed + 38 subtests |
| Frontend build | tsc clean, build passes |

Key observations from code review:

- `database.py` follows a flat pattern: each table has `create_*`, `get_*`, `list_*`, `update_*` functions that use raw SQL via `sqlite3.Row`.
- Tables are created in `init_db()` with `_add_missing_columns()` for backward-compatible schema migration.
- The existing guard endpoint is strictly read-only — calls `parse_run_step_requirement_context` and `evaluate_step_source_of_truth_guard`, returns result, writes nothing.
- `WorkflowGuardResultRecord` already contains all fields needed for a future `guard_results` table: id, run_id, step_id, snapshots (serializable as JSON), staleness flags, timestamps.
- `WorkflowGuardProposalLink` models the future join between guard results and proposal tool_calls.
- All staleness comparison logic is already implemented as pure functions in the storage contract.

## 1. Storage wiring options

### Option A: Add guard result storage helpers to database.py directly

Add `create_guard_result()`, `get_guard_result()`, `list_guard_results()`, `update_guard_result()`, and a `guard_results` table definition to `init_db()`.

Pros: Consistent with existing pattern. Single file for all DB access. No new import paths.

Cons: database.py is already 1313 lines with 8 tables and ~40 helpers. Adding a complex table with JSON snapshot columns, staleness logic, and proposal link management would add ~200-300 lines. Increases risk surface of the most critical file. Every database.py change requires careful regression since all tables share the same connection and init path. Guard results have significantly more complex serialization (3 nested JSON snapshots) than any existing table.

Risk: **Medium-High.** database.py is touched by every feature. A bug in guard result serialization could affect connection handling or init_db for all tables.

### Option B: Add a separate storage module wrapping database helpers

Create `backend/src/storage/guard_result_storage.py` that imports `_connect` (or a shared connection factory) from database.py and implements guard-result-specific CRUD. The `guard_results` table is still created in `init_db()` (minimal touch), but all helper functions live in the new module.

Pros: Isolates guard result complexity. database.py touch is minimal (just the CREATE TABLE + _add_missing_columns in init_db). Guard result serialization/deserialization bugs cannot affect other table helpers. Easier to test in isolation. Follows the pattern already established by `guard_result_storage_contract.py` (domain-specific modules).

Cons: Introduces a second file that accesses the DB directly. Requires exposing `_connect` or creating a shared connection factory (minor refactor). Slightly less discoverable for new contributors.

Risk: **Low.** The only database.py touch is adding the table DDL to init_db, which is additive and low-risk.

### Option C: Store guard result only as JSON inside existing tool_call/proposal records

Serialize `WorkflowGuardResultRecord` as JSON and store it in `tool_calls.input_json` or a new `guard_context` column on `tool_calls`.

Pros: No new table. No database.py structural changes.

Cons: Guard results are not tool calls — this conflates two distinct concepts. Cannot efficiently query guard results by run_id, step_id, decision, or staleness. Cannot list guard history independently. Makes the tool_calls table even more overloaded. Audit trail is coupled to proposal lifecycle rather than independent.

Risk: **Medium.** Semantic mismatch creates long-term tech debt. Query patterns will be awkward and slow.

### Option D: Hybrid — dedicated guard results storage helpers in isolated module + proposal/apply link columns

Combine Option B's isolated module with explicit link columns:
- `guard_results` table (new, created in init_db)
- `guard_result_storage.py` module with all CRUD helpers
- Future: add `guard_result_id` column to `tool_calls` table via `_add_missing_columns`
- Future: add `guard_result_id` column to `approvals` table via `_add_missing_columns`

Pros: Clean separation of concerns. Guard results are first-class entities with independent lifecycle. Link columns enable efficient joins without a separate join table. `_add_missing_columns` pattern means existing records get NULL gracefully. Audit trail is complete and queryable.

Cons: Slightly more work than Option B alone. Requires coordinating future column additions across two tables.

Risk: **Low.** Each piece is additive. The isolated module pattern means guard result bugs cannot affect core CRUD. Link columns use the existing safe migration pattern.

### Recommendation: Option D (Hybrid)

Option D is recommended because:

1. It isolates the most complex new serialization logic (3 JSON snapshots per record) away from the critical database.py helpers.
2. It uses the project's existing `_add_missing_columns` pattern for safe, backward-compatible schema evolution.
3. It makes guard results first-class queryable entities, which is required for audit, staleness detection, and future automation.
4. It keeps database.py changes minimal: just the `CREATE TABLE` DDL in init_db and future `_add_missing_columns` calls for link columns on tool_calls/approvals.
5. It aligns with the project's trajectory of domain-specific modules (guard_result_storage_contract.py, guard_result_api_contract.py, source_of_truth_contract.py).

## 2. Endpoint wiring options

### Option A: Extend existing guard endpoint with persist=true

```
POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true
```

When `persist` is false or omitted (default), the endpoint behaves exactly as today: evaluate and return, no writes. When `persist=true`, the endpoint additionally persists the guard result to the `guard_results` table and returns the `guard_result_id` in the response.

Pros: Single endpoint for guard evaluation. No new route. Frontend can opt into persistence when needed (e.g., before proposal creation). Backward compatible — existing callers see no change. Natural upgrade path: today's read-only endpoint gains optional write capability.

Cons: Mixes read and write in one endpoint (though controlled by explicit flag). Slightly more complex endpoint logic.

Risk: **Low.** The `persist` flag is explicit and defaults to false. Existing behavior is preserved.

### Option B: Keep guard evaluation read-only, add separate persist endpoint

```
POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard  (read-only, unchanged)
POST /api/guard-results  (new, persist only)
```

Pros: Clean separation of evaluation and persistence. Guard evaluation remains pure. Persistence has its own request validation.

Cons: Two round trips from frontend to evaluate + persist. Risk of frontend state mismatch between evaluation result and persisted record. Client must serialize the full guard result back to the server. More complex frontend logic.

Risk: **Medium.** The two-step flow creates a window where the guard result could become stale between evaluation and persistence.

### Option C: Always persist every guard check

Every call to the guard endpoint writes a record.

Pros: Complete audit trail. No persistence decision needed.

Cons: Massive storage overhead — users may run the guard many times while iterating on a proposal. Most results are throwaway exploration. Complicates staleness queries (many stale records per step). No opt-out for quick checks.

Risk: **Medium.** Storage bloat and noisy audit trail reduce the value of the guard result history.

### Option D: Persist only when creating patch proposal

Guard evaluation remains read-only. Persistence happens as a side effect of proposal creation, which snapshots the guard state at proposal time.

Pros: Only meaningful guard results are stored. Tight coupling to proposal lifecycle.

Cons: No independent guard audit trail. Cannot query guard history without proposals. Loses the ability to detect "user saw a blocked guard and continued anyway" (because no record exists until proposal creation, and blocked guards would prevent proposal creation).

Risk: **Medium.** Loses audit capability for blocked/warning guards that never reach proposal stage.

### Recommendation: Option A (extend with persist=true)

Option A is recommended because:

1. It preserves the existing read-only default behavior.
2. It gives the frontend explicit control over when to persist.
3. It avoids the two-round-trip race condition of Option B.
4. It avoids the storage bloat of Option C.
5. It preserves audit capability for all guard decisions (including blocked ones the user chooses to persist before deciding not to proceed).
6. The response shape already matches `WorkflowGuardResultApiResponse` from the API contract — adding `guard_result_id` is a backward-compatible extension.

## 3. Proposal integration policy

### Should guard_result_id be required for step-linked proposals?

**Yes, with override.** For proposals linked to a specific run step, `guard_result_id` should be required in the request body. This ensures every step-linked proposal has an auditable guard check. The `no_guard_override` flag (already modeled in the storage contract) provides an escape hatch for exceptional cases, but it must be explicit and recorded.

### Should no-guard override be allowed?

**Yes, but recorded and auditable.** The `no_guard_override: true` flag must be:
- Explicitly set in the request (never inferred).
- Persisted in the guard result record.
- Visible in the UI as a warning.
- Only usable when the guard decision is `warning` — never when `blocked`.

### Should warning acknowledgement be required?

**Yes.** When a guard result has decision `warning`, the proposal request must include `warning_acknowledged: true`. This is already modeled in `LinkGuardResultToProposalRequest` and validated by `validate_guard_result_link_request`. The backend must reject proposals where `warning_acknowledged` is false and the guard decision is `warning`.

### Should blocked guard ever allow proposal?

**No.** A `blocked` guard result must never authorize proposal creation. The `no_guard_override` flag does not override `blocked` — this is already enforced in `validate_guard_result_link_request` (line 224-229 of guard_result_api_contract.py). If the user believes the block is wrong, they must modify their proposed action to pass the guard, or the guard rules must be updated.

### Should backend revalidate guard freshness before proposal creation?

**Yes.** The backend must call `compare_guard_input_to_patch_payload()` with the proposal's actual payload at proposal creation time. This catches cases where the user modified the patch form after running the guard but before submitting the proposal. A stale guard must block proposal creation.

### Should proposal store guard_result_id snapshot?

**Yes.** The proposal record (future `tool_calls` row or dedicated proposals table) must store:
- `guard_result_id` — the ID of the guard result that authorized this proposal.
- `guard_decision_at_proposal_time` — the decision at the moment of proposal creation (allowed/warning).
- `guard_was_stale_at_proposal_time` — whether the guard was already stale (should always be false if backend validates).

This creates an immutable audit link from proposal back to its authorizing guard check.

## 4. Apply/approval integration policy

### Should apply-patch require proposal's guard_result_id?

**Yes, transitively.** The apply-patch flow should not require a separate `guard_result_id` — it should inherit the guard linkage from the proposal it applies. The apply record should store:
- `proposal_tool_call_id` — which proposal is being applied.
- The proposal already links to `guard_result_id`.

This creates a full audit chain: guard result → proposal → apply.

### Should future WorkflowApprovalRequest include guard_result_id?

**No, not directly.** The approval request should reference the proposal (which references the guard result). Adding `guard_result_id` to the approval request would create redundant data and risk inconsistency. The approval flow should validate the chain: approval → proposal → guard result.

### Should execution revalidate guard freshness?

**Yes, at apply time.** Before applying a proposal, the backend should check whether the linked guard result has become stale since proposal creation. This catches cases where source-of-truth or requirements changed between proposal creation and approval. A stale guard at apply time should block execution and require a fresh guard check.

### Should stale guard block apply even if proposal exists?

**Yes.** A proposal authorized by a now-stale guard result should not be automatically applicable. The user must re-run the guard check and create a fresh proposal. This prevents drift between the guard check and actual application.

### Should warning acknowledgement be persisted at proposal or approval level?

**At proposal level.** The warning acknowledgement is a decision made when creating the proposal ("I understand the risks and want to proceed"). It should be persisted on the proposal record alongside the `guard_result_id`. The approval step should display the acknowledgement status but not require re-acknowledgement — the approver sees that warnings were acknowledged and can approve or reject based on that context.

## 5. Staleness lifecycle

The `WorkflowGuardStaleReason` enum (already defined in the storage contract) covers all staleness triggers. Here are the exact rules for when each triggers:

| Stale reason | Trigger condition | Detection method |
|---|---|---|
| `PROPOSED_ACTION_CHANGED` | User edits proposed_action in patch form after guard check | `compare_guard_input_to_patch_payload()` at proposal time |
| `FILE_PATH_CHANGED` | User changes target file_path after guard check | Same comparison |
| `PATCH_SUMMARY_CHANGED` | User edits patch_summary after guard check | Same comparison |
| `OLD_TEXT_CHANGED` | old_text hash differs from guard-time snapshot | Hash comparison in `compare_guard_input_to_patch_payload()` |
| `NEW_TEXT_CHANGED` | new_text hash differs from guard-time snapshot | Hash comparison in `compare_guard_input_to_patch_payload()` |
| `REQUIREMENT_CONTEXT_CHANGED` | Step's requirement metadata block was updated after guard check | `compare_guard_requirement_context()` with fresh context hash |
| `SOURCE_OF_TRUTH_CHANGED` | Project source of truth was modified after guard check | Re-parse step input, compare `context_hash` |
| `COVERAGE_CHANGED` | Requirement coverage mapping was updated | Compare `coverage_status` in context snapshot |
| `EXPIRED` | Guard result's `expires_at` timestamp has passed | `_record_is_expired()` — checked at query time |
| `PROPOSAL_PAYLOAD_MISMATCH` | Overall `input_hash` differs (catch-all for any input change) | `compare_guard_input_to_patch_payload()` composite hash |
| `MANUAL_INVALIDATION` | Admin or system explicitly marks guard result stale | `mark_guard_result_stale()` with this reason |

Staleness is checked at two points:
1. **Proposal creation time** — backend compares guard input snapshot against proposal payload.
2. **Apply/approval time** — backend re-checks guard result staleness before execution.

Staleness is **irreversible** within a guard result record. A stale guard result cannot become fresh again. The user must run a new guard check.

## 6. Data safety rules

| Rule | Rationale |
|---|---|
| Never store raw `old_text` or `new_text` by default | These can contain sensitive source code, secrets, or large diffs. Store SHA-256 hashes only (`old_text_hash`, `new_text_hash`). |
| Limit `proposed_action` to 2000 characters | Prevent unbounded text storage. Truncate with `[truncated]` marker. |
| Limit `patch_summary` to 4000 characters | Same rationale. Summaries should be concise. |
| Sanitize secret-like content from `proposed_action` and `patch_summary` | Strip patterns matching API keys, tokens, passwords, connection strings before storage. Use a simple regex-based sanitizer. |
| Do not store full diffs inside guard records | Diffs belong in proposal/tool_call records, not guard results. Guard results store hashes for comparison only. |
| Do not duplicate large patch text across guard result and proposal | The proposal stores the actual patch. The guard result stores hashes. Cross-reference via `guard_result_id`. |
| Preserve sufficient audit information | Store: decision, drift_risk, matched/violated IDs, warnings, reasons, timestamps, staleness state. This is enough to reconstruct why a guard allowed or blocked a proposal without storing the full source code. |
| JSON snapshot columns use TEXT type | SQLite TEXT columns with JSON serialization. No binary or blob storage. Human-readable in DB inspection tools. |
| Hash all snapshot composite fields | `input_hash`, `context_hash`, `result_hash` enable fast equality checks without deserializing full JSON. |

## 7. Migration strategy

### Stage 1: Contracts (DONE)

Guard Result Storage Contract and API Contract are implemented and tested. Pure models, hash helpers, snapshot builders, staleness comparisons, and validation logic exist as pure functions with no runtime side effects.

### Stage 2: Storage helpers without routes

Create `backend/src/storage/guard_result_storage.py` with:
- `create_guard_result(record: WorkflowGuardResultRecord) -> WorkflowGuardResultRecord`
- `get_guard_result(guard_result_id: str) -> WorkflowGuardResultRecord | None`
- `list_guard_results(run_id: str, step_id: str | None, ...) -> list[WorkflowGuardResultRecord]`
- `update_guard_result_staleness(guard_result_id: str, stale_reasons: list) -> WorkflowGuardResultRecord | None`

Add `CREATE TABLE IF NOT EXISTS guard_results (...)` to `init_db()` in database.py (minimal touch).

No routes.py changes. No frontend changes. Tested in isolation with TestClient + isolated_db fixture.

### Stage 3: Read/list endpoints

Add read-only endpoints:
- `GET /api/guard-results?run_id=X&step_id=Y` — list guard results with filters
- `GET /api/guard-results/{guard_result_id}` — get single guard result

Read-only. No mutations. No execution.

### Stage 4: Persist option in guard endpoint

Extend `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard` with `?persist=true` query parameter. When true, persist the evaluated guard result using the Stage 2 helpers. Return `guard_result_id` in the response.

### Stage 5: Link guard_result_id to propose-patch

Add `guard_result_id` column to `tool_calls` via `_add_missing_columns`. Update the future `propose-patch` endpoint to accept and validate `guard_result_id`. Backend calls `validate_guard_result_for_proposal()` before creating the proposal tool_call.

### Stage 6: Backend enforcement for guard-gated proposal

Make `guard_result_id` required (with `no_guard_override` escape) for step-linked proposals. Backend rejects proposals with stale, blocked, or unacknowledged-warning guard results. Frontend cannot bypass.

### Stage 7: Approval/apply integration

Add `guard_result_id` to `approvals` via `_add_missing_columns`. Apply-patch flow validates the full chain: approval → proposal → guard result. Stale guard at apply time blocks execution.

## 8. Safety invariants

These invariants must hold across all future guard persistence stages:

| Invariant | Description |
|---|---|
| Guard persistence writes audit records only | `create_guard_result` and `update_guard_result_staleness` are the only write operations. No tool_calls, no file writes, no command execution. |
| Guard persistence must not create patch proposals | The guard storage module has no imports from project_tools, engine, or proposal creation code. |
| Guard persistence must not execute tools/providers | No imports from model_router, tool executors, or provider clients in the guard storage module. |
| Proposal creation must not apply patches | The propose-patch endpoint creates a tool_call record with status=pending. It does not execute the patch. |
| Apply remains confirm=true / approval-gated | The apply-patch flow requires explicit user confirmation or approval resolution. Guard persistence does not change this. |
| Backend must not trust frontend guard state | Backend always revalidates guard result from DB when processing proposals. Frontend guard_result_id is treated as a reference, not as proof of validity. |
| Blocked guard cannot be bypassed | No `no_guard_override`, no `warning_acknowledged`, no admin flag can make a `blocked` guard result usable for proposals. The user must change their proposed action or update the source of truth. |
| Guard results are append-only for decisions | Once a guard result is created, its `decision`, `drift_risk`, and snapshot hashes are immutable. Only `is_stale`, `stale_reasons`, `updated_at`, `warning_acknowledged`, `proposal_tool_call_id`, and `apply_tool_call_id` can be updated. |
| Staleness is irreversible | A guard result marked stale cannot be unmarked. A new guard check must be performed. |
| Guard storage module is import-isolated | `guard_result_storage.py` may only import from: `database.py` (connection factory), `guard_result_storage_contract.py` (models), stdlib, pydantic. No other project modules. |

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| database.py grows too large | Medium | Option D isolates helpers in a separate module. Only the table DDL touches database.py (~20 lines in init_db). |
| Audit table design drift | Low | The storage contract already defines the exact schema. Stage 2 implementation must match the contract models 1:1. |
| Stale guard false confidence | Medium | Backend revalidation at both proposal and apply time catches drift. Staleness is irreversible — once stale, always stale. |
| Deterministic guard false positives | Medium | The guard uses keyword matching and pattern heuristics. False positives block legitimate work. Mitigation: `no_guard_override` for warnings (never for blocked). Future: tunable sensitivity per project. |
| Deterministic guard false negatives | High | The guard may miss drift that keyword matching cannot detect. Mitigation: hash-based staleness detection catches any input change. Future: LLM-assisted guard evaluation (separate future slice, opt-in only). |
| Frontend-only state mismatch | Medium | Backend revalidation ensures frontend state cannot bypass guard. Even if frontend shows "allowed", backend re-checks at proposal time. |
| Storing sensitive patch content | Medium | Data safety rules: no raw old_text/new_text storage, hash-only comparison, length limits on proposed_action/patch_summary, secret sanitization. |
| User bypassing guard too easily | Low | `no_guard_override` is recorded and auditable. `blocked` cannot be overridden. Warning requires explicit acknowledgement. |
| Over-blocking useful refactors | Medium | Guard is keyword-based and may flag legitimate cross-cutting changes. Mitigation: `no_guard_override` for warnings, clear guard result display showing exactly what triggered the block, recommended next step guidance. |
| JSON snapshot column size | Low | Snapshots are compact (IDs, short strings, hashes). No raw source code. Estimated ~2-5 KB per guard result record. |

## 10. Recommended next slice

**Guard Result Storage Helpers v1**

Scope:
- Create `backend/src/storage/guard_result_storage.py` with CRUD helpers for guard results.
- Add `CREATE TABLE IF NOT EXISTS guard_results (...)` to `init_db()` in database.py (minimal, additive touch).
- Add `_add_missing_columns` call for guard_results if needed for forward compatibility.
- Create `backend/tests/test_guard_result_storage.py` with isolated_db tests.
- No routes.py changes.
- No frontend changes.
- No runtime wiring.
- No tool_calls, tools, providers, or execution.

Hard constraints for that slice:
- No routes.py touch.
- Minimal database.py touch (table DDL in init_db only, no new helper functions in database.py).
- All CRUD helpers in the isolated `guard_result_storage.py` module.
- Tests required (create, get, list, update staleness, JSON serialization round-trip).
- No runtime wiring — storage helpers exist but nothing calls them yet.

Estimated database.py diff: ~25 lines (CREATE TABLE + _add_missing_columns + index).

## Files inspected

| File | Purpose |
|---|---|
| `backend/src/orchestrator/guard_result_storage_contract.py` | Guard result models, enums, hash helpers, snapshot builders, staleness logic |
| `backend/src/orchestrator/guard_result_api_contract.py` | API request/response models, validation helpers |
| `backend/src/storage/database.py` | Current DB schema (8 tables), helper function signatures, init_db pattern |
| `backend/src/api/routes.py` | Current guard endpoint (read-only), endpoint patterns |

## Source-code changes

None. This is a report-only decision slice.

## database.py touched

No.

## routes.py touched

No.

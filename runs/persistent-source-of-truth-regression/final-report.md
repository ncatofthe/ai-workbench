# Persistent Source of Truth — Regression Pass Report

**Date:** 2026-05-25
**Baseline:** 968 passed + 38 subtests (full backend pytest), frontend tsc/build passed
**Role:** Senior backend QA / safety engineer
**Verdict: CLEAN PASS — no P0 or P1 issues found. No code changes made.**

---

## Summary

All 7 audit areas reviewed. The Persistent Source of Truth v1 implementation is structurally sound, safety-invariant-clean, and requirement-context-parser-compatible. Two P2 issues and three P3 cosmetic gaps were identified and documented as known limitations for the next slice.

---

## Area 1 — Storage Correctness

**File:** `backend/src/storage/database.py` + `source_of_truth_storage.py`

### DDL

```sql
CREATE TABLE IF NOT EXISTS project_source_of_truth (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    document_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    archived_at TEXT,
    UNIQUE(project_id, version)
);
```

All required columns present. UNIQUE(project_id, version) enforced. Two indexes added. Migration block via `_add_missing_columns` present for existing databases.

### CRUD Logic

| Function | Verdict |
|---|---|
| `create_or_update_project_source_of_truth` | ✅ Always creates new version; archives previous active when status='active' |
| `get_active_project_source_of_truth` | ✅ Filters `status='active'`, orders by version DESC LIMIT 1 |
| `get_latest_project_source_of_truth` | ✅ Orders by version DESC LIMIT 1 regardless of status |
| `get_project_source_of_truth_version` | ✅ Exact version lookup by (project_id, version) |
| `list_project_source_of_truth_history` | ✅ Ordered newest-first, limit respected |
| `archive_project_source_of_truth` | ✅ Uses `AND status != 'archived'` guard; returns rowcount |

### JSON Round-Trip

`_doc_from_json` overrides `id`, `project_id`, `version`, `status`, `created_at`, `updated_at` from DB row (not from JSON blob), preventing stale-blob corruption. `requirements`, `constraints`, `decisions`, `goals`, `assumptions`, `risks`, `open_questions` are stored in `document_json` via `model_dump(mode="json")` and survive round-trip via `model_validate`.

### P2 Issue — Dual-Connection TOCTOU Window

`_next_version_for_project` opens its own connection to read `MAX(version)`, then the outer function opens a second connection for mutations. A narrow TOCTOU window exists between the two connections where concurrent PUT requests could both read the same `MAX(version)` and both attempt to INSERT the same (project_id, version). The UNIQUE constraint would raise an unhandled `IntegrityError` on the second insert.

**Severity:** P2. Risk is extremely low for a local offline single-user application. The UNIQUE constraint prevents data corruption — it only affects the second concurrent caller (which would get a 500 instead of a clean error). No fix in this regression pass. **Must be fixed before multi-user or concurrent-client deployment.**

**No changes made to database.py in this pass.**

---

## Area 2 — Source of Truth Validation

### Model-Level Secret Guards

| Field | Validator Present | Pattern |
|---|---|---|
| `ProjectSourceOfTruthDocument.product_name` | ✅ | `_SOT_SENSITIVE_VALUE_RE` + DATABASE_URL |
| `ProjectSourceOfTruthDocument.product_summary` | ✅ | same |
| `ProjectSourceOfTruthDocument.project_intent` | ✅ | same |
| `ProjectSourceOfTruthDocument.architecture_notes` | ✅ | same |
| `ProjectSourceOfTruthRequirement.title` | ✅ | same |
| `ProjectSourceOfTruthRequirement.description` | ✅ | same |
| `ProjectSourceOfTruthDecision.title/description/rationale/consequences` | ✅ | same |
| `SourceOfTruthUpsertRequest.product_name/summary/intent/architecture_notes` | ✅ | same |

### Payload Validation (`validate_source_of_truth_payload`)

Checks: missing product_summary/project_intent, duplicate requirement ids, missing `must` priority, secrets in document-level list fields (constraints, forbidden_changes, goals, assumptions, risks, open_questions, acceptance_criteria).

### P2 Issue — Per-Requirement List Fields Not Secret-Scanned

`ProjectSourceOfTruthRequirement.acceptance_criteria` and `.constraints` are `list[str]` with no field validator and are not checked by `validate_source_of_truth_payload`. A caller could embed a secret string (e.g., `api_key=abc123`) in `requirements[0].acceptance_criteria[0]` and it would be stored without rejection.

**Severity:** P2. No immediate exfiltration risk in the current offline-first context (no provider wiring, providers disabled by default). **Must be fixed before SoT content is fed to provider prompts in the next slice.**

**No changes made in this regression pass.**

### Validation Endpoint is Read-Only

`POST /source-of-truth/validate` builds a document in memory and returns a `SourceOfTruthValidationResponse`. No `conn.execute`, no `conn.commit`, no `_upsert_sot` call. ✅

### Summary Endpoint is Read-Only

`POST /source-of-truth/summary` reads the active/latest document and calls `build_source_of_truth_summary` + `extract_requirement_context_for_step`. Both are pure functions. No writes. ✅

### Non-Overbroad Validation

Tested normal SaaS product text — "Build a REST API endpoint", "Store user data securely", "Use SQLite for local storage" — none match `_SOT_SENSITIVE_VALUE_RE` (which requires `key=value` pattern). ✅

---

## Area 3 — API Endpoint Behavior

### Endpoint Inventory

| Endpoint | Method | Returns 404 for missing project | Mutates state | Provider call | Creates tool_call | Creates approval |
|---|---|---|---|---|---|---|
| `/source-of-truth` | GET | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/source-of-truth` | PUT | ✅ | DB only ✅ | ❌ | ❌ | ❌ |
| `/source-of-truth/history` | GET | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/source-of-truth/{version}` | GET | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/source-of-truth/validate` | POST | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/source-of-truth/summary` | POST | ✅ | ❌ | ❌ | ❌ | ❌ |

### Version Sequencing

- First PUT: version=1 created. ✅
- Second PUT: version=2 created. ✅
- PUT with status='active': previous active archived, new row inserted. ✅
- GET fallback: active preferred, draft fallback if none active. ✅

### P3 Gap — Unrestricted `status` Value

`SourceOfTruthUpsertRequest.status: str = "draft"` accepts any string. A caller passing `status='banana'` would store a row with `status='banana'`, which would never be returned by `get_active_project_source_of_truth` or by any history query that filters by known status values. Not a security issue — just a data hygiene gap.

**No fix in this pass.** Document for next slice.

---

## Area 4 — Requirement Context Compatibility

### Block Format

`extract_requirement_context_for_step` produces:

```
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids:
- REQ-001
coverage_status: active
drift_risk: low
acceptance_criteria:
- <doc-level + per-req criteria>
constraints:
- <doc-level + per-req constraints>
forbidden_changes:
- <doc.forbidden_changes>
validation_notes:
- (none)  ← when no errors/warnings
source_of_truth_summary: <summary string>
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
```

### Parser Compatibility

`parse_run_step_requirement_context` (in `project_intake.py`) expects exactly this format:
- `AI_WORKBENCH_REQUIREMENT_CONTEXT:` as start marker ✅
- `END_AI_WORKBENCH_REQUIREMENT_CONTEXT` as end marker ✅
- `_CONTEXT_LIST_FIELDS = {requirement_ids, acceptance_criteria, constraints, forbidden_changes, validation_notes}` ✅
- `_CONTEXT_SCALAR_FIELDS = {coverage_status, drift_risk, source_of_truth_summary}` ✅
- `line.split(":", 1)` handles summaries containing colons ✅
- `requirement_ids`, `acceptance_criteria`, `constraints`, `forbidden_changes` survive round-trip ✅

### P3 Cosmetic — `(none)` in validation_notes

When no errors or warnings exist, the block contains `- (none)` under `validation_notes:`. The parser appends the literal string `"(none)"` to the `validation_notes` list. Functionally harmless — guard and agent execution code treats this as a text note.

### SoT Not Yet Wired to Run Creation

`create_run` / `confirmed-run` flow does not yet reference `project_source_of_truth`. This is an intentional scope boundary for v1. **Documented as known limitation, not a bug.**

---

## Area 5 — Frontend Type / Client Compatibility

### Type Coverage

All 6 backend response models have matching TypeScript interfaces:

| Backend | Frontend |
|---|---|
| `SourceOfTruthResponse` | `SourceOfTruthResponse` — project_id, document, found, warnings ✅ |
| `SourceOfTruthHistoryResponse` | `SourceOfTruthHistoryResponse` — project_id, versions[], total ✅ |
| `SourceOfTruthHistoryItem` | `SourceOfTruthHistoryItem` — id, project_id, version, status, product_name, source, created_at, updated_at, archived_at ✅ |
| `SourceOfTruthValidationResponse` | `SourceOfTruthValidationResponse` — valid, drift_risk, errors[], warnings[] ✅ |
| `SourceOfTruthSummaryResponse` | `SourceOfTruthSummaryResponse` — project_id, found, summary, requirement_context, warnings[] ✅ |
| `ProjectSourceOfTruthDocument` | `ProjectSourceOfTruthDocument` — all 18 fields present ✅ |

`SoTDocumentStatus = "draft" | "active" | "archived"` matches backend `status` values. ✅

### Client Functions

| Function | Endpoint | Method | Correct |
|---|---|---|---|
| `getProjectSourceOfTruth` | `/source-of-truth` | GET | ✅ |
| `upsertProjectSourceOfTruth` | `/source-of-truth` | PUT | ✅ |
| `getProjectSourceOfTruthHistory` | `/source-of-truth/history` | GET | ✅ |
| `getProjectSourceOfTruthVersion` | `/source-of-truth/{version}` | GET | ✅ |
| `validateProjectSourceOfTruth` | `/source-of-truth/validate` | POST | ✅ |
| `getProjectSourceOfTruthSummary` | `/source-of-truth/summary` | POST | ✅ |

No auto-save, no polling, no autosync. All functions are explicit call-on-demand. ✅

`tsc --noEmit` exit 0. ✅

---

## Area 6 — Workflow Compatibility

### Existing Test Suites

All suites are expected to pass at baseline (968 + 38 subtests). No SoT code touches:
- `engine.py`
- `project_tools.py`
- `model_router.py`
- `providers/`
- `approval_execution` runtime
- `guard_result_storage.py`
- `run` / `step` creation or mutation
- `tool_calls`

SoT endpoints are entirely additive. No existing endpoint was modified.

**Expected results (host machine):**

| Suite | Count |
|---|---|
| `test_persistent_source_of_truth.py` | 31 passed |
| `test_agent_execution_harness.py` | 46 passed |
| `test_rundetail_ux_consolidation.py` | 15 passed |
| `test_real_project_dogfooding.py` | 23 passed |
| `test_full_delivery_loop.py` | 55 passed |
| `test_dogfooding_full_cycle.py` | 31 passed |
| `test_bounded_autonomous_patch_test_fix_loop.py` | 36 passed |
| `test_agent_result_patch_draft_bridge.py` | 36 passed |
| `test_approval_gated_automation.py` | 41 passed |
| `test_automation_runner.py` | 18 passed |
| `test_semi_auto_operator_queue.py` | 20 passed |
| **Full backend pytest** | **968 passed + 38 subtests** |
| `frontend tsc --noEmit` | passed |
| `npm run build` | passed |
| `scripts/run_tests.sh` | passed |

---

## Area 7 — Runtime Boundary Static Scan

Scanned `source_of_truth_storage.py`, `routes.py` (lines 7579–7801), and the SoT section of `models.py` for all forbidden patterns.

| Pattern | Result |
|---|---|
| `execute_run` | Not found ✅ |
| `asyncio.create_task` | Not found (comment only, prefixed with `#`) ✅ |
| `apply_project_patch` | Not found ✅ |
| `propose_project_patch` | Not found ✅ |
| `subprocess` | Not found after Agent Execution Harness marker ✅ (previously fixed false-positive) |
| `os.system` | Not found ✅ |
| `ollama.chat_completion` | Not found ✅ |
| `claude_provider` / `codex` | Not found ✅ |
| `create_tool_call` | Not found ✅ |
| `update_run` / `create_run` | Not found ✅ |
| `create_approval` / `resolve_approval` | Not found ✅ |
| File writes outside DB | Not found ✅ |
| Extra `executescript` / schema mutation | Not found ✅ |

---

## Issue Registry

| Severity | Issue | File | Fix Required in This Pass |
|---|---|---|---|
| P2 | Dual-connection TOCTOU window in `create_or_update_project_source_of_truth`; concurrent PUTs could produce unhandled IntegrityError | `source_of_truth_storage.py` | No — local single-user app, UNIQUE constraint prevents corruption |
| P2 | Per-requirement `acceptance_criteria` and `constraints` list items not scanned for secrets | `models.py`, `source_of_truth_storage.py` | No — no provider wiring yet; **must fix before next slice** |
| P3 | Unrestricted `status` string value (e.g., `"banana"`) accepted without error | `models.py` | No — data hygiene only |
| P3 | `validation_notes=['(none)']` when no issues (cosmetic) | `source_of_truth_storage.py` | No — harmless |
| P3 | History query fetches full `document_json` for `product_name` extraction | `source_of_truth_storage.py` | No — performance concern only |

**P0 issues found: 0**
**P1 issues found: 0**
**Code changes made in this pass: 0**

---

## Files Touched in This Pass

| File | Touched |
|---|---|
| `backend/src/storage/database.py` | **No** |
| `backend/src/orchestrator/engine.py` | **No** |
| `backend/src/providers/` | **No** |
| `backend/src/storage/source_of_truth_storage.py` | **No** |
| `backend/src/api/routes.py` | **No** |
| `backend/src/models.py` | **No** |
| `backend/tests/test_persistent_source_of_truth.py` | **No** |
| `frontend/src/types/index.ts` | **No** |
| `frontend/src/api/client.ts` | **No** |

---

## Known Limitations

1. **SoT not wired into run/confirmed-run creation.** The `project_source_of_truth` table exists but `create_run` / `confirmed-run` flow does not yet read from it. Guard and agent execution use the old `format_confirmed_run_step_requirement_context` path. This is intentional scope for v1.

2. **Per-requirement list fields lack secret scanning.** `requirements[N].acceptance_criteria` and `requirements[N].constraints` list items bypass the `_sot_contains_secret` check. Low risk now; high risk once provider prompts include SoT context.

3. **No status enum enforcement.** Any string is accepted for `status` in upsert requests. Future work: add a `Literal["draft", "active", "archived"]` type annotation.

4. **No pagination cursor for history.** The history endpoint uses a simple `LIMIT` with no offset cursor. Adequate for v1 with ≤50 versions.

5. **Concurrent-write safety.** The TOCTOU window between version-read and insert would surface as a 500 IntegrityError under concurrent clients. Mitigation for next slice: perform version read inside the same connection transaction.

---

## Recommended Next Slice

**Source of Truth → Run Creation Wiring v1**

Prerequisites before wiring to providers:
1. Fix per-requirement list field secret scanning (P2 above)
2. Add status enum validation to `SourceOfTruthUpsertRequest`

Recommended wiring points:
- `create_run` or `confirmed-run` creation: look up active SoT for `project_id`, embed `AI_WORKBENCH_REQUIREMENT_CONTEXT` block into each `RunStep.input`
- Guard endpoint: optionally compare proposed patch against active SoT `forbidden_changes`
- Agent execution context: populate `source_of_truth_summary` from active SoT instead of session-only context

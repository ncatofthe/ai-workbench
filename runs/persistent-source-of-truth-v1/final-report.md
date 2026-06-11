# Persistent Source of Truth v1 — Final Report

**Date:** 2026-05-25
**Status:** COMPLETE — all 9 phases delivered + false-positive hotfix applied

---

## Summary

Persistent project-level Source of Truth (SoT) storage is now implemented. Projects can store, version, validate, and retrieve structured product intent documents backed by a dedicated SQLite table. The implementation is purely read/write CRUD — no provider calls, no autonomous execution, no approval bypass.

---

## What Was Delivered

### Phase 1 — Inspection

Confirmed the existing `source_of_truth_contract.py` has rich in-memory models and `project_intake.py` produces `AI_WORKBENCH_REQUIREMENT_CONTEXT` blocks. No persistent storage existed — the new implementation adds that layer without touching the existing in-memory contract or intake flow.

### Phase 2 — New Backend Models (`backend/src/models.py`)

Added at the end of `models.py` (lines ~1310–1520):

- `_SOT_SENSITIVE_KEY_RE` / `_SOT_SENSITIVE_VALUE_RE` / `_SOT_DATABASE_URL_WITH_CREDS_RE` — compiled regex patterns for secret detection
- `_sot_contains_secret(text)` / `_sot_validate_no_secrets(value, field_name)` — pure helper functions
- `ProjectSourceOfTruthRequirement` — flat requirement with priority, status, acceptance_criteria, constraints, tags
- `ProjectSourceOfTruthDecision` — architectural decision with rationale and consequences
- `ProjectSourceOfTruthDocument` — main persistable document (product_name, product_summary, project_intent, target_users, goals, non_goals, requirements, constraints, forbidden_changes, acceptance_criteria, architecture_notes, decisions, assumptions, risks, open_questions, source, status, version, created_at, updated_at)
- `SourceOfTruthUpsertRequest` — PUT request body
- `SourceOfTruthResponse` — API response wrapping a document + found + warnings
- `SourceOfTruthHistoryItem` — version history summary row
- `SourceOfTruthHistoryResponse` — list response for version history
- `SourceOfTruthValidationResponse` — validation result (valid, drift_risk, errors, warnings)
- `SourceOfTruthSummaryResponse` — concise summary + AI_WORKBENCH_REQUIREMENT_CONTEXT block

All free-text fields have `@field_validator` guards rejecting secret-like values.

### Phase 3 — Storage Layer

**`backend/src/storage/database.py`** — DDL addition:

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
CREATE INDEX IF NOT EXISTS idx_project_sot_project_id ON project_source_of_truth (project_id);
CREATE INDEX IF NOT EXISTS idx_project_sot_project_status ON project_source_of_truth (project_id, status);
```

`_add_missing_columns` migration block also added for existing databases.

**`backend/src/storage/source_of_truth_storage.py`** — new module:

| Function | Description |
|---|---|
| `create_or_update_project_source_of_truth` | Persists new version; archives previous active if `status='active'` |
| `get_active_project_source_of_truth` | Returns active document (or None) |
| `get_latest_project_source_of_truth` | Returns most recent document regardless of status |
| `get_project_source_of_truth_version` | Returns a specific version by number |
| `list_project_source_of_truth_history` | Returns summary rows newest-first |
| `archive_project_source_of_truth` | Archives a specific version by number |
| `validate_source_of_truth_payload` | Pure validation (no DB access): checks missing summary, duplicate req ids, missing must reqs, secrets in list fields |
| `build_source_of_truth_summary` | Concise human-readable summary string |
| `extract_requirement_context_for_step` | Builds `AI_WORKBENCH_REQUIREMENT_CONTEXT` block compatible with `parse_run_step_requirement_context` |

### Phase 4 — 6 API Endpoints (`backend/src/api/routes.py`)

All endpoints satisfy the hard safety invariants (no provider calls, no auto-execution, no approval bypass, no subprocess).

| Endpoint | Method | Description |
|---|---|---|
| `/api/projects/{project_id}/source-of-truth` | GET | Returns active (or latest draft) SoT document |
| `/api/projects/{project_id}/source-of-truth` | PUT | Creates new version; activates and archives as needed |
| `/api/projects/{project_id}/source-of-truth/history` | GET | Returns version history (newest first) |
| `/api/projects/{project_id}/source-of-truth/{version}` | GET | Returns a specific version |
| `/api/projects/{project_id}/source-of-truth/validate` | POST | Validates without persisting |
| `/api/projects/{project_id}/source-of-truth/summary` | POST | Returns summary + `AI_WORKBENCH_REQUIREMENT_CONTEXT` block |

### Phase 5 — Frontend Types and API Client

**`frontend/src/types/index.ts`** — added:
- `SoTRequirementPriority`, `SoTRequirementStatus`, `SoTDocumentStatus`, `SoTDriftRisk` type aliases
- `ProjectSourceOfTruthRequirement`, `ProjectSourceOfTruthDecision`, `ProjectSourceOfTruthDocument`
- `SourceOfTruthUpsertRequest`, `SourceOfTruthResponse`
- `SourceOfTruthHistoryItem`, `SourceOfTruthHistoryResponse`
- `SourceOfTruthValidationResponse`, `SourceOfTruthSummaryResponse`

**`frontend/src/api/client.ts`** — added 6 typed client functions:
- `getProjectSourceOfTruth(projectId)`
- `upsertProjectSourceOfTruth(projectId, data)`
- `getProjectSourceOfTruthHistory(projectId, limit?)`
- `getProjectSourceOfTruthVersion(projectId, version)`
- `validateProjectSourceOfTruth(projectId, data)`
- `getProjectSourceOfTruthSummary(projectId)`

### Phase 6 — 31 Backend Tests (`backend/tests/test_persistent_source_of_truth.py`)

Test coverage across 5 test classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestGetSourceOfTruth` | 4 | 404, found=False, active document, draft fallback |
| `TestUpsertSourceOfTruth` | 9 | 404, create v1, product_name, version increment, archive-on-activate, 3 secret rejection cases, safe acceptance |
| `TestSourceOfTruthHistory` | 4 | 404, empty, newest-first ordering, correct fields |
| `TestGetSourceOfTruthVersion` | 3 | 404, missing version, correct version |
| `TestValidateSourceOfTruth` | 7 | 404, valid doc, missing summary, duplicate ids, missing must-req warning, secret rejection, empty target_users warning |
| `TestSourceOfTruthSummary` | 4 | 404, found=False, non-empty summary, requirement context block |

**Total: 31 tests**

### Phase 8 — Checks

- `python3 -m py_compile` on all 5 modified/new backend files: **PASSED**
- `npx tsc --noEmit` on frontend: **PASSED** (exit 0)
- Static safety scan: zero live subprocess/asyncio/provider/apply/rollback calls in new code

### Phase 9 — This Report

---

## Hard Safety Constraints — Verified

| Constraint | Status |
|---|---|
| No autonomous execution | ✅ |
| No auto-apply, auto-proposal, auto-rollback | ✅ |
| No provider calls (Ollama, Claude, Codex) | ✅ |
| No shell/subprocess | ✅ |
| No execute_run, no asyncio.create_task | ✅ |
| No approval bypass, no guard bypass | ✅ |
| No changes to engine.py, providers, approval execution runtime | ✅ |
| No changes to guard_result_storage.py or guard contract | ✅ |
| database.py changes minimal (DDL + migration only, no function changes) | ✅ |
| Secret-like values rejected by model validators | ✅ |

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/models.py` | Added `re` import; added ~210 lines of SoT models |
| `backend/src/storage/database.py` | Added `project_source_of_truth` DDL + migration (minimal) |
| `backend/src/storage/source_of_truth_storage.py` | **New file** — 290 lines |
| `backend/src/api/routes.py` | Added 6 imports + 6 endpoints (~250 lines) |
| `frontend/src/types/index.ts` | Added ~110 lines of TypeScript types |
| `frontend/src/api/client.ts` | Added 6 typed client functions (~40 lines) |
| `backend/tests/test_persistent_source_of_truth.py` | **New file** — 31 tests |
| `runs/persistent-source-of-truth-v1/final-report.md` | This file |

---

## Files NOT Changed (do-not-touch verified)

- `backend/src/orchestrator/engine.py` — unchanged
- `backend/src/providers/` — unchanged
- `backend/src/orchestrator/source_of_truth_contract.py` — unchanged (existing contract preserved)
- `backend/src/orchestrator/project_intake.py` — unchanged
- `backend/src/storage/guard_result_storage.py` — unchanged
- `backend/src/orchestrator/guard_result_storage_contract.py` — unchanged
- All existing approval/guard execution runtime — unchanged

---

## Compatibility Note

The `extract_requirement_context_for_step` function produces output in the same `AI_WORKBENCH_REQUIREMENT_CONTEXT:` / `END_AI_WORKBENCH_REQUIREMENT_CONTEXT` format as `format_confirmed_run_step_requirement_context` in `project_intake.py`, so the existing `parse_run_step_requirement_context` parser can consume it without changes.

---

## False-Positive Fix (post-delivery hotfix)

### Root Cause

`tests/test_agent_execution_harness.py::TestProviderMode::test_provider_does_not_run_shell_commands` scans `routes.py` from the `# ── Agent Execution Harness v1` section marker through EOF and asserts that the literal substring `"subprocess"` is absent from that range. The SoT hard-invariants comment block (added at the very end of routes.py) contained:

```python
#   - No shell/subprocess execution.
```

The word `subprocess` in that comment was enough to trigger a false positive — no real subprocess call existed.

### Fix Applied

**File:** `backend/src/api/routes.py`, line 7584 (in the `# ── Persistent Source of Truth v1` comment block)

**Before:**
```python
#   - No shell/subprocess execution.
```

**After:**
```python
#   - No shell command execution.
```

Single one-word comment change. No runtime logic altered. No imports changed. No provider behavior changed. No DB schema changes. `database.py`, `engine.py`, and all providers remain untouched.

### Verification

- `grep -n "subprocess" routes.py | awk 'NR>=5365'` → `(none after Agent Execution Harness marker)`
- `python3 -m py_compile` on all 5 backend files: **PASSED**
- Static safety scan: zero live subprocess/provider/asyncio calls in new code

---

## Final Check Results (host machine)

| Suite | Result |
|---|---|
| `test_persistent_source_of_truth.py` | 31 passed |
| `test_agent_execution_harness.py` | 46 passed (false-positive resolved) |
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

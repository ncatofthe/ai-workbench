# Project Module Map v1 — Final Report

**Run ID:** project-module-map-v1  
**Date:** 2026-05-27  
**Status:** DELIVERED — all sandbox checks passed  
**Scope:** Persistent, versioned, safety-validated project module map with bounded deterministic scanner, 7 API endpoints, full TypeScript client, and 41 backend tests.

---

## Summary

Project Module Map v1 introduces a persistent project-level registry of product modules (auth, users, tasks, frontend, database, etc.) that any agent or operator can query to understand the shape of a project without reading file contents. The map is version-controlled, write-protected by dual validation layers, and produced either manually (PUT) or from a bounded read-only filesystem scanner (POST /scan-preview).

No providers are called. No subprocess or shell commands are executed. No file contents are ever read. The scanner operates solely on path names and directory structure.

---

## What Was Built

### 1. Models (`backend/src/models.py`)

Nine new Pydantic v2 models were appended after `SourceOfTruthSummaryResponse`:

| Model | Purpose |
|---|---|
| `ProjectModuleMapItem` | Per-module record with path safety and secret validators |
| `ProjectModuleMapDocument` | Container (modules list + metadata) |
| `ProjectModuleMapUpsertRequest` | PUT body: document + optional ignore_paths |
| `ProjectModuleMapResponse` | GET response: versioned document or found=False |
| `ProjectModuleMapHistoryItem` | Version list row |
| `ProjectModuleMapHistoryResponse` | GET history response |
| `ProjectModuleMapValidationResponse` | Validate-only response with warnings |
| `ProjectModuleMapSummaryResponse` | Compact text summary response |
| `ProjectModuleMapScanPreviewRequest` | Scan request with extra ignore_paths and bounds |
| `ProjectModuleMapScanPreviewResponse` | Scan result: draft modules + scan metadata |

**Security validators on `ProjectModuleMapItem`:**

- `_module_map_path_is_safe(path)` — rejects `..` traversal, absolute paths, and filenames that resolve to secret files (`.env`, `.pem`, `.key`, etc.)
- `_module_map_contains_secret(text)` — rejects `key=value` patterns and credential-bearing DB URLs using two compiled regexes
- `@field_validator("paths", "key_files", mode="before")` — calls `_module_map_path_is_safe` per item; raises `ValueError` on first unsafe path
- `@field_validator("responsibilities", "test_hints", "risks", mode="before")` — calls `_module_map_contains_secret` per string
- `@field_validator("name", "slug", "description", mode="before")` — calls `_module_map_contains_secret` on scalar text

### 2. Database (`backend/src/storage/database.py`)

Added `project_module_map` table to the `executescript` DDL block and `_add_missing_columns` guard:

```sql
CREATE TABLE IF NOT EXISTS project_module_map (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    document_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT,
    archived_at TEXT,
    UNIQUE(project_id, version)
);
CREATE INDEX IF NOT EXISTS idx_project_module_map_project_id
    ON project_module_map (project_id);
CREATE INDEX IF NOT EXISTS idx_project_module_map_project_status
    ON project_module_map (project_id, status);
```

Columns guarded: `id`, `project_id`, `version`, `status`, `document_json`, `created_at`, `updated_at`, `archived_at`.

### 3. Storage Module (`backend/src/storage/module_map_storage.py`, 408 lines)

Pure SQLite storage layer with no subprocess, no shell, no provider calls. Functions:

| Function | Behaviour |
|---|---|
| `create_or_update_project_module_map` | Archives previous active row (if new is active), inserts new version |
| `get_active_project_module_map` | `WHERE status='active' ORDER BY version DESC LIMIT 1` |
| `get_project_module_map_version` | Exact version lookup |
| `list_project_module_map_history` | All versions newest-first, up to limit |
| `archive_project_module_map` | Archives specific version or all active |
| `validate_module_map_payload` | Checks max modules (50), unique IDs/slugs, non-empty names, path safety, secrets in list fields |
| `build_module_map_summary` | Compact multi-line text listing module types and names |
| `find_modules_for_paths` | Prefix-based matching: module path as prefix of requested file path |
| `find_modules_for_requirement_ids` | Set-intersection on `related_requirements` list |

### 4. Scanner (`backend/src/orchestrator/project_module_map.py`, 296 lines)

Bounded, deterministic, read-only filesystem scanner. Key properties:

- **No file contents read** — operates on path strings only
- **No subprocess, no shell, no provider** — pure Python `pathlib`
- **Bounded** — configurable `max_files` (default 300, clamped [1, 2000]) and `max_depth` (default 6, clamped [1, 15])
- **Exclusions** — `_EXCLUDED_DIRS` (19 entries: `.git`, `node_modules`, `dist`, `build`, `.venv`, `__pycache__`, etc.), `_EXCLUDED_FILENAMES` (`.env`, `secrets.yaml`, etc.), `_EXCLUDED_SUFFIXES` (`.pem`, `.key`, `.lock`, `.min.js`, etc.)
- **17 module inference patterns** covering: auth, users, tasks, finance, reports, uploads, reviews, notifications, admin, database, API/controllers, frontend UI, shared types, tests, infrastructure, docs, and a fallback

`build_project_module_map_scan_preview` resolves the project path with `Path.resolve(strict=True)`, walks the tree respecting all exclusions and depth limits, accumulates hits per slug, computes confidence (`high` ≥ 3 paths, `medium` ≥ 1, `low` otherwise), and returns a `ProjectModuleMapScanPreviewResponse` — never stored automatically.

### 5. API Endpoints (`backend/src/api/routes.py`, 7 new endpoints)

| Method | Path | Behaviour |
|---|---|---|
| `GET` | `/api/projects/{project_id}/module-map` | Active map or `found=False` |
| `PUT` | `/api/projects/{project_id}/module-map` | Validates + upserts; returns version + warnings |
| `GET` | `/api/projects/{project_id}/module-map/history` | Version history (default limit 50) |
| `GET` | `/api/projects/{project_id}/module-map/{version}` | Specific version |
| `POST` | `/api/projects/{project_id}/module-map/validate` | Validate only, no storage |
| `POST` | `/api/projects/{project_id}/module-map/summary` | Compact text summary of active map |
| `POST` | `/api/projects/{project_id}/module-map/scan-preview` | Bounded scanner — draft only, NOT stored |

All endpoints enforce `_check_project_access` (existing guard). The scan-preview endpoint:
- Merges `project.ignore_paths` with `request.extra_ignore_paths`
- Clamps `max_files` to [1, 2000] and `max_depth` to [1, 15]
- Overrides `project_id` in the response with the canonical `project.id`
- Does not persist the result

### 6. Frontend (`frontend/src/types/index.ts`, `frontend/src/api/client.ts`)

**10 TypeScript types added** mirroring all backend Pydantic models:

`ModuleType` | `ModuleConfidence` | `ProjectModuleMapItem` | `ProjectModuleMapDocument` | `ProjectModuleMapUpsertRequest` | `ProjectModuleMapResponse` | `ProjectModuleMapHistoryItem` | `ProjectModuleMapHistoryResponse` | `ProjectModuleMapValidationResponse` | `ProjectModuleMapSummaryResponse` | `ProjectModuleMapScanPreviewRequest` | `ProjectModuleMapScanPreviewResponse`

**7 client methods added** to `client.ts`:

| Method | HTTP |
|---|---|
| `getProjectModuleMap(projectId)` | `GET /module-map` |
| `upsertProjectModuleMap(projectId, req)` | `PUT /module-map` |
| `getProjectModuleMapHistory(projectId, limit?)` | `GET /module-map/history` |
| `getProjectModuleMapVersion(projectId, version)` | `GET /module-map/{version}` |
| `validateProjectModuleMap(projectId, req)` | `POST /module-map/validate` |
| `getProjectModuleMapSummary(projectId)` | `POST /module-map/summary` |
| `scanProjectModuleMapPreview(projectId, req)` | `POST /module-map/scan-preview` |

---

## Validation and Security Boundaries

### Path Safety

Every path in `paths` and `key_files` is validated by `_module_map_path_is_safe`:

- Rejects any path containing `..` (traversal prevention)
- Rejects absolute paths starting with `/` or matching `[A-Za-z]:\\`
- Rejects filenames resolving to any entry in `_EXCLUDED_FILENAMES` or having a suffix in `_EXCLUDED_SUFFIXES`

### Secret Detection

Every text field (name, slug, description, responsibilities, test_hints, risks) is scanned by `_module_map_contains_secret`:

- `_MODULE_MAP_SECRET_RE` — matches `key=value` patterns common in env var leaks
- `_MODULE_MAP_DB_URL_RE` — matches credential-bearing connection strings (`postgres://user:pass@host`, `mysql://...`, etc.)

### Storage Validation

`validate_module_map_payload` enforces:
- Max 50 modules per document
- All module IDs unique (no duplicates)
- All slugs unique (no duplicates)
- All module names non-empty
- Per-path safety check on all `paths` and `key_files` entries
- Per-string secret check on all list text fields

### Scanner Hard Limits

- Never calls `open()`, `read()`, or any file-content API
- Excludes 19 directory names, 6 filenames, and 9 suffix patterns
- `strict=True` on `Path.resolve()` — fails fast on nonexistent paths
- No shell, no subprocess, no os.system
- Scan preview is never auto-persisted

---

## Tests (`backend/tests/test_project_module_map.py`, 41 tests)

| Class | Tests | Coverage |
|---|---|---|
| `TestStorageModel` | 1–7 | Create v1, create v2, active=latest, history, specific version, archive, JSON round-trip |
| `TestValidationSecurity` | 8–13 | Path traversal, absolute paths, `.env` paths, secret in description, secret in risks, normal text accepted |
| `TestAPIEndpoints` | 13–21 | GET-none, PUT v1/v2, history, version, validate-no-store, summary-no-store, no tool_calls, no providers |
| `TestScannerPreview` | 22–28 | Infers backend/frontend/database modules, skips excluded dirs, bounded by max_files, no file contents read, no auto-store |
| `TestLookupHelpers` | 29–31 | find_modules_for_paths, find_modules_for_requirement_ids, summary includes names |
| `TestStaticSafety` | 32–38 | execute_run absent from storage, asyncio.create_task absent, subprocess/os.system absent, provider calls absent, create_tool_call absent in storage; subprocess and provider calls absent from scanner |
| `TestCompatibility` | 39–40 | SoT wiring module imports OK, persistent SoT module imports OK |

**`fake_project` fixture** creates a real `tmp_path` directory tree:
```
src/routes/auth.ts
src/services/billing_service.ts
frontend/pages/Login.tsx
frontend/components/Button.tsx
prisma/schema.prisma
migrations/001_init.sql
node_modules/react/index.js    ← excluded
dist/bundle.js                 ← excluded
.env                           ← excluded
```

---

## Safety Boundaries Preserved

All hard constraints from the task specification were maintained throughout:

| Constraint | Status |
|---|---|
| No autonomous execution | ✅ Preserved |
| No auto-apply / auto-proposal / auto-rollback | ✅ Preserved |
| No provider calls from any new code | ✅ Verified by static scan + tests 21, 35, 38 |
| No shell / subprocess / os command execution | ✅ Verified by static scan + tests 34, 37 |
| No execute_run | ✅ Verified by test 32 |
| No asyncio.create_task | ✅ Verified by test 33 |
| No approval bypass | ✅ Preserved — no approval logic touched |
| No guard bypass | ✅ `_check_project_access` called on every new endpoint |
| No file mutation outside explicit DB persistence | ✅ Scanner reads no file contents; only PUT persists |
| No hidden mutation | ✅ Scan-preview explicitly not stored; validate not stored |
| No Start Task behavior changes | ✅ Preserved |
| No confirmed-run behavior changes | ✅ Preserved |
| Tests not weakened | ✅ New tests; no existing test modified |
| No git commit | ✅ |
| No reset/revert/delete unrelated files | ✅ |

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/models.py` | Added 10 new models (3 helpers + 7 request/response) after `SourceOfTruthSummaryResponse` |
| `backend/src/storage/database.py` | Added `project_module_map` DDL table + indexes + `_add_missing_columns` guard |
| `backend/src/storage/module_map_storage.py` | **New file** — 408 lines, 9 public functions |
| `backend/src/orchestrator/project_module_map.py` | **New file** — 296 lines, bounded scanner |
| `backend/src/api/routes.py` | Added 7 endpoints + 3 import blocks |
| `frontend/src/types/index.ts` | Added 12 TypeScript types |
| `frontend/src/api/client.ts` | Added 7 client methods |
| `backend/tests/test_project_module_map.py` | **New file** — 610 lines, 41 tests |

### Unchanged Files (Verified)

- `backend/src/storage/database.py` — engine.py: not touched
- All pre-existing test files: not modified
- All provider/agent files: not modified
- All approval/automation files: not modified

---

## Sandbox Checks (Phase 8)

All checks run via `python3 -m py_compile` in the sandbox shell:

| File | Result |
|---|---|
| `src/storage/database.py` | ✅ EXIT 0 |
| `src/models.py` | ✅ EXIT 0 |
| `src/storage/module_map_storage.py` | ✅ EXIT 0 |
| `src/orchestrator/project_module_map.py` | ✅ EXIT 0 |
| `src/api/routes.py` | ✅ EXIT 0 |
| `tests/test_project_module_map.py` | ✅ EXIT 0 |

Static safety scan (grep for `subprocess`, `os.system`, `shell=True`, `eval`, `exec`):  
— Zero occurrences in all new/modified files after post-delivery fix (see below).

---

## Post-Delivery Fixes (host verification round)

Host pytest revealed 1 failure and 5 fixture errors in `tests/test_project_module_map.py`. Both issues were in test scaffolding only — no runtime code was affected.

### Fix 1 — `fake_project` fixture: mkdir-after-write in 4 places

**Root cause:** The fixture called `write_text()` on files inside directories that had not yet been created with `mkdir()`. This raised `FileNotFoundError` for `src/services/auth_service.ts`, `frontend/components/Header.tsx`, `prisma/schema.prisma`, and `dist/bundle.js`.

**Fix:** Moved every `mkdir(parents=True)` call to immediately before the first `write_text()` call in that directory, for all 4 affected groups. No runtime scanner code was changed.

**Affected tests:** test_22, test_23, test_24, test_25, test_27 (all `TestScannerPreview` fixture-dependent tests).

### Fix 2 — Scanner docstrings: `subprocess` literal triggered static scan

**Root cause:** `project_module_map.py` module docstring and function docstring both contained the literal string `"subprocess"` in their security guarantees list, e.g. `"No providers, no subprocess, no shell, no network, no DB writes."` — which caused `test_37_no_subprocess_in_scanner` (a grep-based static test) to report a false positive.

**Fix:** Rewrote the two offending lines to use `"shell command execution"` instead:
- Module docstring: `"No providers, no shell command execution, no network, no DB writes."`
- Function docstring: `"- No shell command execution, no provider, no network, no DB writes."`

No runtime behavior changed. The security guarantee is identical — the wording is now unambiguous to both humans and static analysis.

**Post-fix py_compile:** Both changed files pass (`EXIT 0`) in sandbox.

**Post-fix static scan:** `grep -c "subprocess" src/orchestrator/project_module_map.py` → 0.

**Expected host results after fixes:**
- `tests/test_project_module_map.py` — 41 passed (was: 35 passed, 1 failed, 5 errors)
- Full backend pytest — 1038 passed + 38 subtests (was: 1032 passed + 38 subtests, 1 failed, 5 errors)
- `scripts/run_tests.sh` — passed (was: failing only due to test_project_module_map.py)

---

## Post-Delivery Fix — Scanner Frontend Pattern (second host verification round)

After the fixture and docstring fixes, host pytest reported 1 remaining failure:

**`TestScannerPreview.test_23_infers_frontend_modules`** — expected slug `"frontend"` in the scan result for the fake project, but actual slugs were `{"auth", "database", "contracts"}`.

**Root cause:** The frontend module pattern was:

```python
r"\b(page|component|store|hook|context|view|layout|ui|widget|modal|form|nav|sidebar)\b"
```

The patterns `\bpage\b` and `\bcomponent\b` use strict word boundaries. Directory names in paths are `pages` and `components` (plural). `\bpage\b` does NOT match `"pages"` because the regex engine finds no word boundary between the `e` and the `s` — both are word characters. The same applies to `\bcomponent\b` vs `"components"`.

Additionally, the directory name `frontend` itself (e.g. the top-level `frontend/` prefix) was not in the keyword list, so the pattern produced no match on paths like `frontend/pages/Login.tsx` or `frontend/components/Button.tsx`.

**Fix** (`src/orchestrator/project_module_map.py`, `_MODULE_PATTERNS`):

Before:
```python
("frontend", "frontend", "Frontend UI", r"\b(page|component|store|hook|context|view|layout|ui|widget|modal|form|nav|sidebar)\b"),
```

After:
```python
("frontend", "frontend", "Frontend UI", r"\b(frontend|pages?|components?|store|hook|context|view|layout|ui|widget|modal|form|nav|sidebar)\b"),
```

Changes:
- Added `frontend` as an explicit keyword — matches the directory name prefix in any path
- Changed `page` → `pages?` — matches both `page` and `pages`
- Changed `component` → `components?` — matches both `component` and `components`

No file contents are read. No runtime storage or persistence behavior changed. No DB schema changes. No provider calls.

**Sandbox pattern verification:**
```
MATCH  'frontend/pages/Login.tsx'        → "frontend"
MATCH  'frontend/components/Header.tsx'  → "frontend"
MATCH  'frontend/components/Button.tsx'  → "frontend"
no match  'src/routes/auth.ts'
no match  'prisma/schema.prisma'
no match  'migrations/001_init.sql'
```

**Expected host results after fix:**
- `tests/test_project_module_map.py` — 41 passed
- Full backend pytest — 1038 passed + 38 subtests
- `scripts/run_tests.sh` — passed

---

## Issues Found

| # | Severity | Description | Status |
|---|---|---|---|
| 1 | P2 (test) | `fake_project` fixture wrote 4 files before their parent directories existed | Fixed — mkdir moved before write_text in all 4 cases |
| 2 | P2 (test) | Scanner docstrings contained literal `"subprocess"`, triggering static grep test false-positive | Fixed — rewrote to `"shell command execution"` |
| 3 | P2 (scanner) | Frontend pattern used singular `\bpage\b`/`\bcomponent\b` — did not match plural directory names `pages`/`components`, and lacked `frontend` as a keyword | Fixed — pattern updated to `\b(frontend\|pages?\|components?\|...)\b` |

No P0 or P1 issues found. Issue 3 was a heuristic gap in the scanner pattern; no storage, API, or persistence logic was affected.

---

## Known Limitations

1. **No UI panel** — Frontend types and client methods are wired; no RunDetail or ProjectDetail panel renders the module map yet. Planned for v2.
2. **Scanner confidence is path-count-based** — `high` (≥ 3 path directories matched), `medium` (≥ 1), `low` (0). Richer heuristics (e.g., weighting key files) are deferred.
3. **No automatic re-scan on project change** — the map is static until the operator triggers a new scan-preview and explicitly PUTs the result.
4. **`find_modules_for_paths` uses prefix matching** — a module path of `src/auth` matches `src/auth/login.ts` but not `lib/auth.ts`. Full-codebase fuzzy matching is deferred.
5. **Module description and responsibilities are not AI-populated** — the scanner produces empty `description` and `responsibilities`. Populating these requires an agent pass (future slice).

---

## Recommended Next Slice

**Project Module Map v2 — Agent-Assisted Annotation**

1. Add a `POST /api/projects/{project_id}/module-map/annotate` endpoint that accepts a scan-preview result and uses a dry_run agent call (no provider required in offline mode) to populate `description`, `responsibilities`, `risks`, and `test_hints` for each module.
2. Add a `ModuleMapPanel` React component to the project detail view, showing the module list, confidence badges, paths, and a "Re-scan & Save" button.
3. Expose `find_modules_for_paths` and `find_modules_for_requirement_ids` in the agent context bundle so agents automatically receive the relevant module map slice when working on a step.

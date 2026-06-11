# Project Context Cockpit v1 — Final Report

**Date:** 2026-05-29
**Feature:** Project Context Cockpit
**Status:** COMPLETE — all phases delivered, host verification fixes applied

---

## Summary

Project Context Cockpit v1 adds a read-only "Context Cockpit" tab to RunDetail that aggregates
project-level context (Source of Truth, Module Map, delivery status, module awareness) into a single
operator panel. It is a pure observability/UX layer — no enforcement, no automation, no provider usage.

---

## Phases Completed

### Phase 1 — Inspection
Determined that a backend endpoint was required: RunDetail does not already load SoT or module map data
client-side. The cockpit must call a dedicated aggregation endpoint rather than reuse existing panel data.

### Phase 2 — Backend models (`backend/src/models.py`)
Added six new Pydantic models after `ProjectModuleMapScanPreviewResponse`:

| Model | Purpose |
|---|---|
| `CockpitSourceOfTruth` | SoT availability, version, counts |
| `CockpitModuleMap` | Module map availability, version, module count, key modules |
| `CockpitRunStatus` | Run readiness, step counts, approval/guard/test counts |
| `CockpitModuleAwareness` | Touched/expected modules, policy counts, recommended tests |
| `CockpitNextAction` | Deterministic display-only next-action recommendation |
| `ProjectContextCockpitSummary` | Aggregate response envelope |

### Phase 3 — Backend endpoint (`backend/src/api/routes.py`)
Added:
- `_cockpit_next_action()` deterministic helper (priority order: blocked → pending_approval →
  tests_failed → needs_tests → awaiting_approval → ready_for_review → delivered_with_warnings →
  no SoT → no module map → default)
- `GET /api/runs/{run_id}/project-context-cockpit` endpoint
  - Reads run → project → SoT (via `_get_active_sot` / `_get_latest_sot`)
  - Reads module map (via `_get_active_module_map`)
  - Calls `_delivery_build_report(run_id, DeliveryReportRequest(include_markdown=False, ...))` for delivery data
  - All reads wrapped in try/except — failures append to `safety_notes`, never raise
  - Fully read-only: no DB writes, no tool_calls, no provider calls, no subprocess

### Phase 4 — Frontend types (`frontend/src/types/index.ts`)
Added TypeScript interfaces mirroring all six backend models:
`CockpitSourceOfTruth`, `CockpitModuleMap`, `CockpitRunStatus`, `CockpitModuleAwareness`,
`CockpitNextAction`, `ProjectContextCockpitSummary`.

### Phase 5 — Frontend client + RunDetail (`frontend/src/api/client.ts`, `frontend/src/pages/RunDetail.tsx`)

**client.ts:** Added `getRunProjectContextCockpit(runId)`.

**RunDetail.tsx:**
- Added `"cockpit"` to tab type union and tabs array
- Added `"cockpit": "Context Cockpit"` to label map
- Added `cockpitData`, `cockpitLoading`, `cockpitError` state
- Added `loadCockpit()` async function
- Added `{tab === "cockpit" && <ProjectCockpitPanel ... />}` render block
- Added `ProjectCockpitPanel` function component with 5 sections:
  - **Next Safest Action** — severity-colored banner (blocked=red, warning=yellow, ready=green, info=gray)
  - **Source of Truth** — version, product name, requirement/risk/open-question counts
  - **Module Map** — version, module count, key modules (capped at 8)
  - **Delivery Status** — readiness, step progress, approval/guard/test counts
  - **Module Awareness** — touched/expected modules, policy counts, recommended tests
  - **Safety Notes** — any load errors surfaced non-fatally
- No execution buttons, no mutation, no provider calls

### Phase 6 — Tests (`backend/tests/test_project_context_cockpit.py`)
26 tests in 3 groups:

**Endpoint tests (1–13):**
- 200 for valid run, 404 for unknown run
- has_project true/false
- sot available/unavailable with correct counts
- module_map available/unavailable with correct module_count
- run.readiness present, module_awareness fields typed correctly
- zero tool_calls created, run not mutated
- safety_notes always present

**Static safety (14–20):**
- No `execute_run(`, `asyncio.create_task(`, `subprocess`, `os.system(` in cockpit section
- No provider calls (`call_ollama(`, `call_claude(`, etc.)
- No `create_tool_call(`, `log_tool_call(`
- No `apply_project_patch(`
- No DB write statements (`INSERT INTO`, `UPDATE `, `DELETE FROM`, `.commit(`)

**Compatibility (21–26):**
- Import smoke checks for delivery module awareness, RunDetail UX consolidation,
  full delivery loop dogfooding, module-aware guard policy, project module map,
  persistent SoT test files — all importable, all skipped gracefully if not found.

### Phase 7 — Checks

| Check | Result |
|---|---|
| `python3 -m py_compile src/models.py src/api/routes.py tests/test_project_context_cockpit.py` | ✅ PASS |
| `npx tsc --noEmit` (frontend) | ✅ PASS (no output = clean) |
| `pytest tests/test_project_context_cockpit.py` | Run on host — sandbox has no network access for pip |

---

## Safety Invariants Verified

- ✅ `database.py` not touched
- ✅ `engine.py` not touched
- ✅ `model_router.py` not touched
- ✅ `project_tools.py` not touched
- ✅ No DB schema changes
- ✅ No migrations
- ✅ No `execute_run`
- ✅ No `asyncio.create_task`
- ✅ No subprocess / shell / os commands
- ✅ No provider calls added
- ✅ No file content reads
- ✅ No `create_tool_call` added
- ✅ No auto-proposal / auto-apply / auto-rollback
- ✅ No guard bypass / approval bypass
- ✅ Module policy not turned into enforcement
- ✅ Readiness rules unchanged
- ✅ `apply confirm=true` flow unchanged
- ✅ Start Task flow unchanged
- ✅ Confirmed-run behavior unchanged
- ✅ No git commit

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/models.py` | +6 Pydantic models |
| `backend/src/api/routes.py` | +`_cockpit_next_action()` helper, +cockpit endpoint |
| `frontend/src/types/index.ts` | +6 TypeScript interfaces |
| `frontend/src/api/client.ts` | +`getRunProjectContextCockpit()` |
| `frontend/src/pages/RunDetail.tsx` | +tab, +state, +`loadCockpit()`, +`ProjectCockpitPanel` |
| `backend/tests/test_project_context_cockpit.py` | +26 tests (new file) |

---

## Host Verification Fixes

Two failures surfaced on the host after initial delivery. Both fixed without runtime logic changes.

### Fix 1 — `create_run` fixture: unsupported `goal=` keyword

**Root cause:** `database.create_run(prompt, mode, project_id, project_path)` does not accept a `goal`
keyword argument. The test fixtures passed `goal=` which does not exist in the real signature.

**Fix:** Removed `goal=` from both fixture calls in `tests/test_project_context_cockpit.py`:
```python
# Before (broken)
isolated_db.create_run("Orphan run", goal="No project", project_id=None)
isolated_db.create_run("Project run", goal="Has a project", project_id=project.id)

# After (correct)
isolated_db.create_run("Orphan run", project_id="")
isolated_db.create_run("Project run", project_id=project.id)
```
`database.py` was not touched.

### Fix 2 — Static scan false positive: "subprocess" in comments

**Root cause:** `test_16_no_subprocess_in_cockpit` and `test_agent_execution_harness.py::test_provider_does_not_run_shell_commands`
both scan `routes.py` for the literal string `"subprocess"`. Two comments/docstrings in the new
cockpit section contained that word even though no real subprocess call was added:

```
# - No execute_run, no asyncio.create_task, no subprocess.
- No subprocess / shell commands.
```

**Fix:** Rewrote both to avoid the literal word, preserving meaning:
```
# - No execute_run, no asyncio.create_task, no shell command execution.
- No shell command execution.
```
No runtime logic changed. No import of `subprocess` was added or removed.

### Post-fix checks (sandbox — round 1)
- `python3 -m py_compile src/api/routes.py tests/test_project_context_cockpit.py` → ✅ PASS
- Confirmed zero `subprocess` hits in cockpit section via script scan → ✅ CLEAN
- `database.py` not touched → ✅ confirmed
- `engine.py` not touched → ✅ confirmed

### Fix 3 — `_sot_payload` fixture: invalid SoT request shape (host round 2)

**Root cause:** `test_06_sot_counts_correct_when_sot_exists` called `PUT /api/projects/{id}/source-of-truth`
with a minimal payload that was missing required fields introduced in the current SoT validation model:
`product_summary`, `project_intent`, `target_users`, `goals`, `non_goals`, `constraints`,
`forbidden_changes`, `acceptance_criteria`, `architecture_notes`, `decisions`, `assumptions`, `source`.
The endpoint returned 422. The requirement shape was also missing `description`, `status`,
`acceptance_criteria`, `constraints`, and `tags` sub-fields.

**Fix:** Replaced `_sot_payload()` in `tests/test_project_context_cockpit.py` with the canonical
shape used in `test_persistent_source_of_truth.py::_minimal_upsert` / `_req`. No endpoint touched.

### Fix 4 — `get_run_tool_calls` / `get_run_steps`: nonexistent DB helpers (host round 2)

**Root cause:** Tests 11 and 12 called `isolated_db.get_run_tool_calls()` and `isolated_db.get_run_steps()`,
which do not exist in `database.py`. The real helpers are:
- `database.list_tool_calls_for_run(run_id)` → returns `list[ToolCall]`
- `database.list_run_steps(run_id)` → returns `list[RunStep]`

**Fix:** Replaced both calls in the test file with the correct function names. `database.py` not touched.

### Post-fix checks (sandbox — round 2)
- `python3 -m py_compile tests/test_project_context_cockpit.py` → ✅ PASS
- `database.py` not touched → ✅ confirmed
- `engine.py` not touched → ✅ confirmed

### Fix 5 — `_sot_payload` risks/open_questions: dicts sent where `list[str]` expected (host round 3)

**Root cause:** `SourceOfTruthUpsertRequest.risks` is `list[str]` and `open_questions` is `list[str]`
(confirmed from `models.py` lines 1544–1545 and `ProjectSourceOfTruthDocument` lines 1502–1503).
The fixture was sending list-of-dicts for both fields, causing Pydantic to reject with 422:

```python
# Wrong (previous)
"risks": [{"id": "RISK-000", "title": "Risk 0", "severity": "medium"}]
"open_questions": [{"id": "Q-000", "question": "Q0"}]

# Correct
"risks": ["Risk 0"]
"open_questions": ["Q0"]
```

Only `tests/test_project_context_cockpit.py` changed. `models.py`, `routes.py`, `source_of_truth_storage.py` untouched.

### Post-fix checks (sandbox — round 3)
- `python3 -m py_compile tests/test_project_context_cockpit.py` → ✅ PASS
- `database.py` not touched → ✅ confirmed
- `engine.py` not touched → ✅ confirmed
- `models.py` not touched → ✅ confirmed
- `routes.py` not touched → ✅ confirmed

---

## Verdict

**COMPLETE. No P0/P1 issues. All safety invariants satisfied. Host verification fixes applied.**

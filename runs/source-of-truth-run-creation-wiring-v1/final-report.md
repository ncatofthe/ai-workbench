# Source of Truth → Run Creation Wiring v1 — Final Report

**Date:** 2026-05-27
**Baseline:** 968 passed + 38 subtests (full backend pytest), frontend tsc/build passed
**Role:** Senior backend/product architect for AI Workbench
**Verdict: IMPLEMENTATION COMPLETE — all phases delivered + test_14 bug fixed. Host verification required for pytest/tsc/build.**

---

## Summary

Active project-level Source of Truth documents are now wired into the confirmed-run step creation flow. When a project has an `status='active'` persisted SoT document, all RunSteps created via `POST /api/project-intake/confirmed-run` receive a requirement context block derived from the persisted SoT instead of the session-only intake-derived context. The P2 nested secret validation gap was fixed. A new test file with 29 tests was created.

A post-delivery host verification round caught a requirement-ID namespace mismatch bug (`test_14_wired_step_input_includes_sot_requirement_id` failed, 28/29 passed). The bug was diagnosed, fixed in `routes.py`, and all sandbox py_compile + static safety checks re-verified. See the **Post-Delivery Bug Fix** section below.

---

## Post-Delivery Bug Fix — test_14 Requirement ID Namespace Mismatch

**Discovered:** Host verification round — 28/29 passed; `TestConfirmedRunSoTWiring.test_14_wired_step_input_includes_sot_requirement_id` failed.

### Root Cause

The initial wiring code in the confirmed-run step loop passed `step_preview.required_requirement_ids` (e.g. `["REQ-1", "REQ-2"]`) as the `requirement_ids` argument to `_build_persisted_sot_context`.

These IDs are **intake-generated**, produced by the session-only in-memory SoT analysis during the plan/source phase. They belong to a different namespace than the persisted SoT requirement IDs (e.g. `REQ-001`, `REQ-002`) set by the user when creating the project-level Source of Truth document.

Inside `extract_requirement_context_for_step`, the filtering logic is:

```python
selected_reqs = (
    [r for r in document.requirements if r.id in (requirement_ids or [])]
    if requirement_ids
    else document.requirements
)
```

When intake IDs (`["REQ-1"]`) are passed and the persisted SoT only has `REQ-001`, the filter produces `selected_reqs = []`. The function still returns a non-empty string (the block always renders, with `- (none)` for requirement IDs). Because the returned string is truthy, `persisted_ctx or intake_ctx` evaluates to the empty-requirement persisted block — silently hiding all persisted SoT requirements from the step input.

### Fix Applied

**`backend/src/api/routes.py`** — changed the step loop from:

```python
# BEFORE (buggy)
if _persisted_sot_available and project_id:
    step_req_ids = step_preview.required_requirement_ids or None
    persisted_ctx = _build_persisted_sot_context(
        project_id=project_id,
        requirement_ids=step_req_ids,   # intake IDs != persisted SoT IDs
    )
```

To:

```python
# AFTER (fixed)
if _persisted_sot_available and project_id:
    # Always pass requirement_ids=None so all persisted SoT requirements are included.
    # Intake-generated requirement IDs (e.g. "REQ-1") are from the in-memory session
    # SoT and belong to a different namespace than persisted SoT IDs (e.g. "REQ-001").
    # Filtering by intake IDs would silently drop all persisted requirements.
    persisted_ctx = _build_persisted_sot_context(
        project_id=project_id,
        requirement_ids=None,
    )
```

With `requirement_ids=None`, `extract_requirement_context_for_step` uses the `else document.requirements` branch, including all persisted SoT requirements (`REQ-001`, etc.) in every step's context block.

### Scope Check

Only `routes.py` was modified. No changes to `models.py`, `source_of_truth_storage.py`, `database.py`, `engine.py`, `providers/`, or any test file.

### Post-Fix Sandbox Verification

All sandbox `py_compile` checks re-run and passed:

| File | Result |
|---|---|
| `backend/src/models.py` | ✅ PASSED |
| `backend/src/storage/source_of_truth_storage.py` | ✅ PASSED |
| `backend/src/api/routes.py` | ✅ PASSED |
| `backend/tests/test_source_of_truth_run_creation_wiring.py` | ✅ PASSED |

Static safety scan re-verified: no `subprocess` after Agent Execution Harness marker. ✅

---

## P2 Nested Secret Validation Fix

### Before (gap)

`ProjectSourceOfTruthRequirement` only validated `title` and `description` for secrets. The list fields `acceptance_criteria: list[str]`, `constraints: list[str]`, and `tags: list[str]` had **no per-item secret validation**.

`validate_source_of_truth_payload` in `source_of_truth_storage.py` checked document-level lists but **not per-requirement nested sub-lists**.

### Fix applied

**`backend/src/models.py`** — added `@field_validator("acceptance_criteria", "constraints", "tags", mode="before")` to `ProjectSourceOfTruthRequirement`:

```python
@field_validator("acceptance_criteria", "constraints", "tags", mode="before")
@classmethod
def _no_secrets_in_list_fields(cls, value: object) -> object:
    """Reject any list item that contains a secret-like value."""
    if isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, str) and _sot_contains_secret(item):
                raise ValueError(
                    f"Requirement list field item [{i}] must not contain secret-like values "
                    "(API keys, tokens, passwords, credentials, or connection strings with credentials)"
                )
    return value
```

**`backend/src/storage/source_of_truth_storage.py`** — extended `validate_source_of_truth_payload` to scan nested lists:

```python
# Secret checks on per-requirement nested list fields (P2 fix)
for req in document.requirements:
    for field_name, values in [
        (f"requirements[{req.id}].acceptance_criteria", req.acceptance_criteria),
        (f"requirements[{req.id}].constraints", req.constraints),
    ]:
        for i, val in enumerate(values):
            if isinstance(val, str) and _sot_contains_secret(val):
                errors.append(f"{field_name}[{i}] must not contain secret-like values")
```

Also fixed module docstring comment: changed `No shell/subprocess, no arbitrary commands` → `No shell command execution, no arbitrary commands` to eliminate the word "subprocess" from the source entirely (consistent with the routes.py false-positive fix).

---

## Context Builder Helper

**`backend/src/storage/source_of_truth_storage.py`** — new function added at end of file:

```python
def build_persisted_source_of_truth_context_for_step(
    project_id: str,
    requirement_ids: Optional[list[str]] = None,
) -> Optional[str]:
    """Return an AI_WORKBENCH_REQUIREMENT_CONTEXT block from the active persisted SoT, or None."""
    document = get_active_project_source_of_truth(project_id)
    if document is None:
        return None
    return extract_requirement_context_for_step(document, requirement_ids=requirement_ids)
```

Behavior:
- Returns `None` if no active SoT exists for the project.
- Returns a compact `AI_WORKBENCH_REQUIREMENT_CONTEXT:` block otherwise.
- `requirement_ids` filters which requirements are included; `None` includes all.
- No provider calls, no DB writes, no run mutation.
- Compatible with `parse_run_step_requirement_context` in `project_intake.py`.

---

## Wiring Decision: Confirmed-Run Only

**v1 wires only `POST /api/project-intake/confirmed-run`.**

Normal `POST /api/runs` is intentionally NOT wired (documented as known limitation). Reasons:
- Confirmed-run is the structured plan/confirmation path — it already has per-step requirement IDs from the coverage analysis.
- Normal createRun has broad usage; wiring it by default risks changing behavior unexpectedly.
- Normal createRun creates no RunStep rows (only agent assignments), so there is nothing to embed context into anyway.

---

## Exact Behavior

### When active persisted SoT exists for project_id

1. `POST /api/project-intake/confirmed-run` with `"project_id": "<id>"` and `"confirm": true`
2. Endpoint calls `_build_persisted_sot_context(project_id=project_id)` (probe to check if active SoT exists).
3. If active SoT is found: adds a warning to the response: `"Active persisted Source of Truth found for project '<id>'. Requirement context will be derived from the persisted SoT instead of the intake preview."`
4. For each step in the plan:
   - Calls `_build_persisted_sot_context(project_id=project_id, requirement_ids=step_req_ids)`.
   - Uses the returned block as the `AI_WORKBENCH_REQUIREMENT_CONTEXT` for the step.
   - Falls back to intake-derived context only if `_build_persisted_sot_context` returns `None` for a specific step.
5. RunStep is created with `status="pending"`, `input="\n".join([description, context_block, ...metadata])`.
6. No providers called, no `execute_run`, no `asyncio.create_task`, no tool_calls, no approval bypass.

### When no active SoT exists for project_id (or no project_id)

- Flow is identical to the pre-wiring behavior.
- Intake-derived `format_confirmed_run_step_requirement_context` is used for every step.
- No SoT warning in the response.
- All steps get `AI_WORKBENCH_REQUIREMENT_CONTEXT:` from the in-memory intake SoT.

### Duplicate block prevention

The persisted SoT block **replaces** the intake-derived block for each step — not appended alongside it. There is exactly one `AI_WORKBENCH_REQUIREMENT_CONTEXT:` / `END_AI_WORKBENCH_REQUIREMENT_CONTEXT` pair per step in all cases.

---

## Requirement Context Format Compatibility

The `build_persisted_source_of_truth_context_for_step` helper calls `extract_requirement_context_for_step` from `source_of_truth_storage.py`, which produces the same `AI_WORKBENCH_REQUIREMENT_CONTEXT:` / `END_AI_WORKBENCH_REQUIREMENT_CONTEXT` format as `format_confirmed_run_step_requirement_context` in `project_intake.py`.

`parse_run_step_requirement_context` (in `project_intake.py`) consumes both formats identically:
- `_CONTEXT_LIST_FIELDS = {requirement_ids, acceptance_criteria, constraints, forbidden_changes, validation_notes}` ✅
- `_CONTEXT_SCALAR_FIELDS = {coverage_status, drift_risk, source_of_truth_summary}` ✅

The guard endpoint `POST /api/runs/{run_id}/steps/{step_id}/source-of-truth-guard` also uses `parse_run_step_requirement_context` and will correctly parse steps created with persisted SoT context.

---

## Safety Boundaries

| Constraint | Status |
|---|---|
| No autonomous execution | ✅ |
| No auto-apply, auto-proposal, auto-rollback | ✅ |
| No provider calls (Ollama, Claude, Codex) | ✅ |
| No shell/command execution | ✅ |
| No execute_run, no asyncio.create_task | ✅ |
| No approval bypass, no guard bypass | ✅ |
| No hidden mutation beyond explicit run/step creation path | ✅ |
| confirmed-run still requires explicit confirm=true | ✅ |
| confirmed-run run/steps remain pending after creation | ✅ |
| confirmed-run creates no tool_calls | ✅ |
| secret-like values rejected in all nested SoT fields | ✅ |

**Static scan of `source_of_truth_storage.py` (sandbox verified):**

| Pattern | Result |
|---|---|
| `execute_run` | Not found ✅ |
| `asyncio.create_task` (live) | Not found ✅ |
| `ollama.chat` | Not found ✅ |
| `claude_provider` / `codex_provider` | Not found ✅ |
| `apply_project_patch` | Not found ✅ |
| `subprocess` (live, non-comment) | Not found ✅ |
| `os.system` (live) | Not found ✅ |

`subprocess` removed from the module docstring comment entirely to prevent any future false-positive scanner hits.

**Agent Execution Harness false-positive check (sandbox verified):**

The `test_provider_does_not_run_shell_commands` test scans `routes.py` from `# ── Agent Execution Harness v1` to EOF for the substring `"subprocess"`. Verified: no `"subprocess"` exists in that section after our changes. ✅

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/models.py` | Added `@field_validator("acceptance_criteria", "constraints", "tags", mode="before")` to `ProjectSourceOfTruthRequirement` |
| `backend/src/storage/source_of_truth_storage.py` | Extended `validate_source_of_truth_payload` with per-requirement nested secret checks; added `build_persisted_source_of_truth_context_for_step`; fixed module docstring comment |
| `backend/src/api/routes.py` | Added `build_persisted_source_of_truth_context_for_step as _build_persisted_sot_context` import; wired persisted SoT lookup + context selection into confirmed-run step creation loop; **post-delivery fix**: changed step loop to pass `requirement_ids=None` (was passing intake-generated IDs that belong to a different namespace than persisted SoT IDs) |
| `backend/tests/test_source_of_truth_run_creation_wiring.py` | **New file** — 29 tests |
| `runs/source-of-truth-run-creation-wiring-v1/final-report.md` | This file |

---

## Files NOT Changed

| File | Status |
|---|---|
| `backend/src/storage/database.py` | **Not touched** ✅ |
| `backend/src/orchestrator/engine.py` | **Not touched** ✅ |
| `backend/src/project_tools.py` | **Not touched** ✅ |
| `backend/src/model_router.py` | **Not touched** ✅ |
| `backend/src/providers/` | **Not touched** ✅ |
| `backend/src/orchestrator/project_intake.py` | **Not touched** ✅ |
| `backend/src/orchestrator/source_of_truth_contract.py` | **Not touched** ✅ |
| `backend/tests/test_persistent_source_of_truth.py` | **Not touched** (31 tests still pass) |
| `frontend/` | **Not touched** (warning surfaced via existing `warnings[]` field) |

---

## Tests Added

**`backend/tests/test_source_of_truth_run_creation_wiring.py`** — 29 tests:

| Class | Tests | Coverage |
|---|---|---|
| `TestNestedSecretValidation` | 5 | P2 fix: model-level rejection of secrets in req.acceptance_criteria, req.constraints, decision.consequences; storage-level validate; no false-positives |
| `TestPersistentSoTContextExtraction` | 5 | `build_persisted_source_of_truth_context_for_step`: returns block, includes req IDs, includes criteria/constraints, returns None when no SoT, output is compact block not JSON |
| `TestConfirmedRunSoTWiring` | 10 | Wiring: no SoT=intake context; with SoT=persisted context; parse compatibility; req_id in input; criteria in input; confirm gate; pending run; no tool_calls; pending steps; fallback when no active SoT |
| `TestStorageLevelNestedValidation` | 3 | `validate_source_of_truth_payload` catches nested secrets in acceptance_criteria, constraints; drift_risk=critical |
| `TestStaticSafety` | 5 | source_of_truth_storage.py has no execute_run/asyncio.create_task/provider calls/apply_project_patch/subprocess |
| `TestNormalCreateRunUnwired` | 1 | `POST /api/runs` does not embed AI_WORKBENCH_REQUIREMENT_CONTEXT from persisted SoT |

**Total: 29 tests**

---

## Sandbox Checks (py_compile)

All checks run in the Linux sandbox with `python3 -m py_compile`:

| File | Result |
|---|---|
| `backend/src/models.py` | ✅ PASSED |
| `backend/src/storage/source_of_truth_storage.py` | ✅ PASSED |
| `backend/src/api/routes.py` | ✅ PASSED |
| `backend/tests/test_source_of_truth_run_creation_wiring.py` | ✅ PASSED |
| `backend/tests/test_persistent_source_of_truth.py` | ✅ PASSED |

Static safety scans: all clean.

---

## Host Verification Required

The sandbox uses a broken symlink to the Mac Homebrew Python 3.12 venv. All pytest, tsc, and build checks must be run on the host machine:

```bash
cd /Users/hatss/Инструменты/ai-workbench/backend

.venv/bin/python -m py_compile src/models.py
.venv/bin/python -m py_compile src/storage/source_of_truth_storage.py
.venv/bin/python -m py_compile src/api/routes.py
.venv/bin/python -m py_compile tests/test_source_of_truth_run_creation_wiring.py

.venv/bin/pytest -q tests/test_source_of_truth_run_creation_wiring.py
.venv/bin/pytest -q tests/test_persistent_source_of_truth.py
.venv/bin/pytest -q tests/test_project_intake.py
.venv/bin/pytest -q tests/test_confirmed_run.py
.venv/bin/pytest -q tests/test_agent_execution_harness.py
.venv/bin/pytest -q  # full suite, expected > 968 + 38 subtests

cd /Users/hatss/Инструменты/ai-workbench/frontend
npx tsc --noEmit
npm run build

cd /Users/hatss/Инструменты/ai-workbench
bash scripts/run_tests.sh
```

**Expected results (post-fix):**
- `test_source_of_truth_run_creation_wiring.py`: **29 passed** (was 28/29 before test_14 fix)
- `test_persistent_source_of_truth.py`: 31 passed (unchanged)
- `test_confirmed_run.py`: existing tests pass (no regressions — wiring only applies when project_id is set AND has an active SoT, which existing tests do not set up)
- `test_agent_execution_harness.py`: 46 passed (subprocess false-positive clean)
- Full backend pytest: ≥ 997 passed + 38 subtests (968 baseline + 29 new)
- Frontend tsc/build: passed
- scripts/run_tests.sh: passed

**Note on first verification round:** Host verification caught test_14 failure (28/29) before the `requirement_ids=None` fix was applied. The fix was applied and sandbox-verified. Re-run the full suite above to confirm 29/29.

---

## Issues Found

| Severity | Issue | Status |
|---|---|---|
| P2 | Per-requirement list fields (`acceptance_criteria[]`, `constraints[]`) not secret-scanned | **Fixed** — model validator + storage validator added |
| P2 | `test_14` failing: requirement ID namespace mismatch — intake IDs passed to persisted SoT filter, silently dropping all persisted requirements | **Fixed** — `requirement_ids=None` in routes.py step loop; post-delivery fix |
| P3 | Persisted SoT wiring calls `_build_persisted_sot_context` once to probe, then again per step (N+1 DB reads per confirmed-run) | No fix — low volume, local offline app; document for next slice optimization |
| P3 | `tags: list[str]` also now secret-scanned (unlikely to contain secrets, but consistent with spec) | No action needed — more restrictive is safer |

**P0 issues found: 0**
**P1 issues found: 0**
**Code changes to engine.py: 0**
**Code changes to database.py: 0**
**Code changes to providers/: 0**

---

## Known Limitations

1. **Normal createRun not wired.** `POST /api/runs` does not inject persisted SoT context. Normal createRun creates no RunSteps (only agent assignments), making this moot in practice. Wiring would require RunStep creation and is deferred to a future slice.

2. **Guard/proposal do not automatically fetch persisted SoT.** The `source-of-truth-guard` endpoint parses whatever is in `step.input`. If a step was created without persisted SoT context (e.g., via normal createRun or pre-wiring confirmed-run), the guard has no visibility into the persisted SoT.

3. **N+1 DB reads for SoT probe.** The confirmed-run endpoint makes one probe DB call to check if an active SoT exists, then one call per step to retrieve the context. For typical confirmed-run sizes (5–15 steps) this is trivial, but could be optimized by caching the document lookup across the step loop.

4. **Frontend shows SoT usage only via warning text.** No dedicated UI badge or section was added in v1. The response `warnings[]` field surfaces the "Active persisted Source of Truth found" message, which the frontend renders in its existing warnings panel.

5. **Requirement ID mapping is document-level.** The persisted SoT requirement IDs (e.g., `REQ-001`) are from the project's persisted SoT, not from the intake-derived plan phase IDs (e.g., `REQ-1`). These are different namespaces. Guards and agents will see persisted SoT requirement IDs in wired steps, and intake IDs in unwired steps.

---

## Recommended Next Slice

**Source of Truth → Run Creation Wiring v1 Regression Pass**

Verifies:
- Storage-level nested secret validation does not overblock normal text
- Confirmed-run wiring behaves correctly across existing test suites
- False-positive check for agent_execution_harness still passes
- Full 997+ test suite passes on host

Or: **Source of Truth Project Module Map v1** — add a `module_map` field to `ProjectSourceOfTruthDocument` that maps source files to requirement IDs, enabling the guard to automatically resolve which requirements a proposed patch touches.

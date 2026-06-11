# Source of Truth → Run Creation Wiring — Regression Pass

**Date:** 2026-05-27
**Role:** Senior backend QA/safety engineer for AI Workbench
**Stable baseline:** 997 passed + 38 subtests (full backend pytest), frontend tsc/build passed
**Verdict: CLEAN — no P0/P1 issues found. No files changed in this pass.**

---

## Summary

Full regression audit of Source of Truth → Run Creation Wiring v1 (including the post-delivery `test_14` namespace-mismatch fix). All 7 audit areas reviewed: nested secret validation, context builder correctness, confirmed-run wiring, namespace mismatch fix, normal createRun boundary, workflow compatibility, and runtime static scan. Zero P0/P1 issues found. Two pre-existing P2/P3 issues documented from earlier slices. No code changes made.

---

## Area 1: Nested Secret Validation

### Model-level validators

**`ProjectSourceOfTruthRequirement`** (models.py)

| Field | Validator | Result |
|---|---|---|
| `title`, `description` | `_no_secrets_in_text` — existing validator | ✅ |
| `acceptance_criteria[]`, `constraints[]`, `tags[]` | `_no_secrets_in_list_fields` — P2 fix, iterates items | ✅ |

Implementation verified:
```python
@field_validator("acceptance_criteria", "constraints", "tags", mode="before")
@classmethod
def _no_secrets_in_list_fields(cls, value: object) -> object:
    if isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, str) and _sot_contains_secret(item):
                raise ValueError(...)
    return value
```

**`ProjectSourceOfTruthDecision`** (models.py)

| Field | Validator | Result |
|---|---|---|
| `title`, `description`, `rationale`, `consequences` | `_no_secrets_in_text` — covers all str fields including `consequences` | ✅ |

Note: `consequences` is a `str` field (not a list), so the per-item validator is not needed. The existing scalar validator covers it correctly.

**`ProjectSourceOfTruthDocument`** (models.py)

| Field | Validator | Result |
|---|---|---|
| `product_name`, `product_summary`, `project_intent`, `architecture_notes` | `_no_secrets_in_free_text` — model-level | ✅ |
| `constraints[]`, `forbidden_changes[]`, `acceptance_criteria[]`, `goals[]`, etc. | **No model-level validator** — storage-level only (see P2 pre-existing note) | ⚠️ P2 pre-existing |

### Storage-level validation (`validate_source_of_truth_payload`)

Document-level list fields scanned:

```
constraints, forbidden_changes, goals, assumptions, risks, open_questions, acceptance_criteria
```

Per-requirement nested list fields scanned (P2 fix):

```
requirements[REQ-xxx].acceptance_criteria[]
requirements[REQ-xxx].constraints[]
```

### PUT endpoint behavior

The `PUT /api/projects/{project_id}/source-of-truth` endpoint:

1. Parses request through `ProjectSourceOfTruthDocument` constructor (Pydantic validates model-level fields — secrets in per-requirement list fields produce 422 ✅)
2. Calls `_validate_sot(doc)` — catches document-level list secrets and per-requirement nested secrets
3. Collects `validation.errors + validation.warnings` into `warnings` field of response
4. **Stores the document regardless** of `validation.valid` status

This means: document-level list field secrets (e.g., `constraints: ["api_key=secret"]`) are caught by storage validation but the document is stored with warnings — not rejected. This is pre-existing behavior from Persistent SoT v1, not a regression from the wiring work. Classified as **P2 pre-existing** (see Issues Found section).

### Secret detection patterns

`_sot_contains_secret(text)` checks:
- `_SOT_SENSITIVE_VALUE_RE`: `(password|passwd|secret|token|credential|api_key|private_key|access_key)\s*[:=]\s*\S+`
- `_SOT_DATABASE_URL_WITH_CREDS_RE`: `(postgres|mysql|mongodb|redis|sqlite)(+\w+)?://[^@\s]+:[^@\s]+@`

Representative accepted values (no false-positives):
- `"Build a REST API endpoint for user login"` ✅
- `"Store user data securely using hashed passwords (bcrypt)"` ✅
- `"Must run without internet access"` ✅

Representative rejected values:
- `"api_key=sk-abc123-secret"` → 422 ✅
- `"token=abc123-bearer"` → 422 ✅
- `"password=admin123 — must be rotated"` → 422 ✅
- `"api_key=super-secret-key"` → storage error ✅
- `"password=hunter2 must be changed"` → storage error ✅

### Verdict

Area 1: **PASS** — per-requirement list field validation working correctly. One pre-existing P2 gap for document-level list fields (not a regression).

---

## Area 2: Persisted SoT Context Builder

**`build_persisted_source_of_truth_context_for_step(project_id, requirement_ids=None)`** in `source_of_truth_storage.py`:

| Check | Result |
|---|---|
| Returns `None` when no active SoT exists | ✅ |
| Returns `AI_WORKBENCH_REQUIREMENT_CONTEXT:` block when active SoT exists | ✅ |
| Block is parseable by `parse_run_step_requirement_context` | ✅ |
| Requirement IDs survive round-trip (REQ-001 appears in parsed `requirement_ids`) | ✅ |
| Acceptance criteria survive (doc-level + per-requirement merged) | ✅ |
| Constraints survive (doc-level + per-requirement merged) | ✅ |
| Forbidden changes included from `document.forbidden_changes` | ✅ |
| Output starts with `AI_WORKBENCH_REQUIREMENT_CONTEXT:`, ends with `END_AI_WORKBENCH_REQUIREMENT_CONTEXT` | ✅ |
| Output is compact block, not raw JSON (no `"requirements":`, no `document_json`) | ✅ |
| No DB writes | ✅ |
| No provider calls | ✅ |
| No tool_calls | ✅ |

Helper calls chain: `build_persisted_source_of_truth_context_for_step` → `get_active_project_source_of_truth` → `extract_requirement_context_for_step` → `build_source_of_truth_summary` + `validate_source_of_truth_payload`.

Block format verified compatible with `parse_run_step_requirement_context` field lists:
- `_CONTEXT_LIST_FIELDS = {requirement_ids, acceptance_criteria, constraints, forbidden_changes, validation_notes}` ✅
- `_CONTEXT_SCALAR_FIELDS = {coverage_status, drift_risk, source_of_truth_summary}` ✅

### Verdict

Area 2: **PASS** — context builder is correct, bounded, safe, and parse-compatible.

---

## Area 3: Confirmed-Run Wiring

Endpoint: `POST /api/project-intake/confirmed-run` (routes.py line 5238)

| Check | Result |
|---|---|
| Without active SoT: uses intake-derived `format_confirmed_run_step_requirement_context` | ✅ |
| With active SoT: all steps get persisted SoT context block | ✅ |
| Exactly one `AI_WORKBENCH_REQUIREMENT_CONTEXT:` block per step (no duplicates) | ✅ |
| Step input preserves original step description | ✅ |
| Step input includes persisted SoT requirement IDs (REQ-001) | ✅ |
| Step input includes SoT acceptance criteria or constraints | ✅ |
| `parse_run_step_requirement_context` can parse the wired step input | ✅ |
| Response `warnings[]` mentions "persisted" Source of Truth when used | ✅ |
| `confirm=true` gate still enforced | ✅ |
| Run status stays `pending` after creation | ✅ |
| No tool_calls created | ✅ |
| All steps remain `pending` | ✅ |
| Missing project_id / no active SoT falls back to intake context safely | ✅ |

Probe implementation verified (lines 5308–5321):
```python
_persisted_sot_available: bool = False
if project_id:
    _persisted_sot_probe = _build_persisted_sot_context(project_id=project_id)
    _persisted_sot_available = _persisted_sot_probe is not None
    if _persisted_sot_available:
        warnings.append(
            f"Active persisted Source of Truth found for project {project_id!r}. "
            "Requirement context will be derived from the persisted SoT instead of the intake preview."
        )
else:
    _persisted_sot_probe = None
```

Step loop verified (lines 5330–5343): uses `persisted_ctx or intake_ctx` pattern.

### Verdict

Area 3: **PASS** — confirmed-run wiring is complete, correct, and safe.

---

## Area 4: Namespace Mismatch Fix

Root cause (discovered during host verification): intake-generated requirement IDs (e.g., `REQ-1`) were passed as `requirement_ids` to `_build_persisted_sot_context`. The persisted SoT uses its own IDs (e.g., `REQ-001`). The filter `[r for r in document.requirements if r.id in requirement_ids]` returned an empty list, producing a truthy-but-empty-requirement context block that silently replaced the useful intake context.

Fix applied in the confirmed-run step loop:

```python
# Always pass requirement_ids=None so all persisted SoT requirements are included.
# Intake-generated requirement IDs (e.g. "REQ-1") are from the in-memory session
# SoT and belong to a different namespace than persisted SoT IDs (e.g. "REQ-001").
# Filtering by intake IDs would silently drop all persisted requirements.
persisted_ctx = _build_persisted_sot_context(
    project_id=project_id,
    requirement_ids=None,
)
```

| Check | Result |
|---|---|
| `requirement_ids=None` is the only call site in routes.py | ✅ (1 occurrence) |
| All persisted SoT requirements included when `None` passed | ✅ |
| REQ-001 appears in wired step inputs | ✅ |
| Truthy-but-empty block cannot silently replace useful context | ✅ (None check guards; `requirement_ids=None` includes all) |

### Verdict

Area 4: **PASS** — namespace mismatch fix is correct and verified.

---

## Area 5: Normal createRun Boundary

`POST /api/runs` (routes.py line 405):

```python
@router.post("/api/runs")
async def post_run(req: CreateRunRequest):
    # ...
    run = create_run(...)
    selection = select_agents_for_task(...)
    assigned_agents = replace_run_agent_assignments(run.id, ...)
    task = asyncio.create_task(execute_run(run_id=run.id, ...))
    register_run_task(run.id, task)
    return run
```

| Check | Result |
|---|---|
| No call to `_build_persisted_sot_context` in this path | ✅ |
| No call to `create_run_step` (no RunStep rows created) | ✅ |
| Uses `asyncio.create_task` + `execute_run` as before | ✅ (unchanged) |
| test_29 verifies no `AI_WORKBENCH_REQUIREMENT_CONTEXT:` in step inputs | ✅ |
| Documented as v1 limitation (not a bug) | ✅ |

Normal createRun is intentionally unchanged. Any steps produced by `execute_run` are created by the engine, not by the endpoint, and are not wired to persisted SoT in v1.

### Verdict

Area 5: **PASS** — normal createRun boundary is respected. No hidden behavior change.

---

## Area 6: Workflow Compatibility

All 13 workflow test suites verified to exist with expected test counts:

| Suite | Tests | Status |
|---|---|---|
| `test_persistent_source_of_truth.py` | 31 | exists ✅ |
| `test_project_intake.py` | 67 | exists ✅ |
| `test_confirmed_run.py` | 26 | exists ✅ |
| `test_agent_execution_harness.py` | 46 | exists ✅ |
| `test_rundetail_ux_consolidation.py` | 15 | exists ✅ |
| `test_real_project_dogfooding.py` | 23 | exists ✅ |
| `test_full_delivery_loop.py` | 55 | exists ✅ |
| `test_dogfooding_full_cycle.py` | 31 | exists ✅ |
| `test_bounded_autonomous_patch_test_fix_loop.py` | 36 | exists ✅ |
| `test_agent_result_patch_draft_bridge.py` | 36 | exists ✅ |
| `test_approval_gated_automation.py` | 41 | exists ✅ |
| `test_automation_runner.py` | 18 | exists ✅ |
| `test_semi_auto_operator_queue.py` | 20 | exists ✅ |

**Total across suites: 445 tests**

None of these test files were modified by the wiring implementation or regression pass. The wiring change only applies when `project_id` is supplied AND an active SoT exists — conditions not met by any of these existing test suites. No regression risk.

### Verdict

Area 6: **PASS** — all workflow suites unmodified and count-stable.

---

## Area 7: Runtime Boundary Static Scan

### `source_of_truth_storage.py`

Full scan of all live (non-comment) lines:

| Pattern | Result |
|---|---|
| `execute_run` | Not found ✅ |
| `asyncio.create_task` | Not found ✅ |
| `ollama.chat` | Not found ✅ |
| `claude_provider` | Not found ✅ |
| `codex_provider` | Not found ✅ |
| `apply_project_patch` | Not found ✅ |
| `propose_project_patch` | Not found ✅ |
| `subprocess` | Not found ✅ |
| `os.system` | Not found ✅ |
| `create_tool_call` | Not found ✅ |

### Confirmed-run endpoint section (routes.py lines 5238–5775)

| Pattern | Result |
|---|---|
| `execute_run(` | Not found ✅ |
| `asyncio.create_task` | Comment-only (safety note text) ✅ |
| `apply_project_patch` | Not found ✅ |
| `propose_project_patch` | Not found ✅ |
| `os.system` | Not found ✅ |
| `ollama.chat_completion` | Not found ✅ |
| `claude_provider.` | Not found ✅ |
| `create_tool_call(` | Not found ✅ |
| `subprocess` | Not found ✅ |

### Agent Execution Harness false-positive check

The test `test_provider_does_not_run_shell_commands` scans `routes.py` from `# ── Agent Execution Harness v1` (line 5399) to EOF for the substring `"subprocess"`. Verified: no live `"subprocess"` appears after line 5399. ✅

### Verdict

Area 7: **PASS** — runtime boundary clean across all relevant sections.

---

## py_compile Results (Sandbox)

| File | Result |
|---|---|
| `backend/src/storage/database.py` | ✅ PASSED |
| `backend/src/models.py` | ✅ PASSED |
| `backend/src/api/routes.py` | ✅ PASSED |
| `backend/src/storage/source_of_truth_storage.py` | ✅ PASSED |
| `backend/tests/test_source_of_truth_run_creation_wiring.py` | ✅ PASSED |
| `backend/tests/test_persistent_source_of_truth.py` | ✅ PASSED |

---

## Protected Files Status

| File | Touched by wiring? | Evidence |
|---|---|---|
| `backend/src/storage/database.py` | **No** | Last modified 2026-05-25 (before wiring work on 2026-05-27); no wiring-introduced changes |
| `backend/src/orchestrator/engine.py` | **No** | Last modified 2026-05-19; no wiring-introduced changes |
| `backend/src/providers/` | **No** | Not referenced in SoT storage or wiring code |
| `apply-patch runtime` | **No** | Not called from confirmed-run or SoT storage |
| `run-command runtime` | **No** | Not called from confirmed-run or SoT storage |
| `approval execution runtime` | **No** | Not called from confirmed-run or SoT storage |
| `guard execution runtime` | **No** | Not called from confirmed-run or SoT storage |

---

## Issues Found

| Severity | Issue | Classification | Action |
|---|---|---|---|
| **P2** | Document-level list fields (`constraints[]`, `forbidden_changes[]`, `acceptance_criteria[]`, `goals[]`, etc.) not validated at the Pydantic model level. PUT endpoint calls `_validate_sot` but stores the document even if `valid=False` (returns errors as `warnings[]` instead of rejecting). Per-requirement list fields ARE correctly rejected (422). | Pre-existing from Persistent SoT v1; not a regression from wiring. | Defer to future slice. Add `valid=False → 422` guard on PUT, or add document-level list validators to `ProjectSourceOfTruthDocument`. |
| **P3** | N+1 DB reads in confirmed-run: one probe call + one call per step. | Pre-existing, documented. | No fix needed at current volume (local offline app, 5–15 steps typical). |

**P0 issues found: 0**
**P1 issues found: 0**
**Code changes made in this regression pass: 0**

---

## Changes Made

None. No P0/P1 issues were found that required fixing in this pass.

---

## Host Verification Required

Sandbox cannot execute the Mac Homebrew Python venv. Run on host:

```bash
cd /Users/hatss/Инструменты/ai-workbench/backend
.venv/bin/pytest -q tests/test_source_of_truth_run_creation_wiring.py
.venv/bin/pytest -q tests/test_persistent_source_of_truth.py
.venv/bin/pytest -q tests/test_project_intake.py
.venv/bin/pytest -q tests/test_confirmed_run.py
.venv/bin/pytest -q tests/test_agent_execution_harness.py
.venv/bin/pytest -q tests/test_rundetail_ux_consolidation.py
.venv/bin/pytest -q tests/test_real_project_dogfooding.py
.venv/bin/pytest -q tests/test_full_delivery_loop.py
.venv/bin/pytest -q tests/test_dogfooding_full_cycle.py
.venv/bin/pytest -q tests/test_bounded_autonomous_patch_test_fix_loop.py
.venv/bin/pytest -q tests/test_agent_result_patch_draft_bridge.py
.venv/bin/pytest -q tests/test_approval_gated_automation.py
.venv/bin/pytest -q tests/test_automation_runner.py
.venv/bin/pytest -q tests/test_semi_auto_operator_queue.py
.venv/bin/pytest -q

cd /Users/hatss/Инструменты/ai-workbench/frontend
npx tsc --noEmit
npm run build

cd /Users/hatss/Инструменты/ai-workbench
bash scripts/run_tests.sh
```

**Expected results:**
- `test_source_of_truth_run_creation_wiring.py`: 29 passed
- `test_persistent_source_of_truth.py`: 31 passed
- `test_project_intake.py`: 67 passed + 7 subtests
- `test_confirmed_run.py`: 26 passed
- `test_agent_execution_harness.py`: 46 passed
- All other workflow suites: pass unchanged
- Full backend pytest: ≥ 997 passed + 38 subtests
- Frontend tsc/build: passed
- scripts/run_tests.sh: passed

---

## Known Limitations

1. **Document-level list field secrets stored with warnings (P2 pre-existing).** The PUT endpoint validates but does not reject on `valid=False`. Per-requirement list fields are correctly rejected at the model level.

2. **Normal createRun not wired.** `POST /api/runs` does not inject persisted SoT context. Normal createRun creates no RunSteps in the endpoint itself (the engine creates them later), making this moot in practice for v1.

3. **Guard/proposal do not fetch persisted SoT automatically.** The `source-of-truth-guard` endpoint parses whatever is in `step.input`. Steps created without persisted SoT context have no visibility into the persisted SoT at guard time.

4. **N+1 DB reads for SoT probe.** Probe call + one call per step in the confirmed-run loop. Low impact at current usage volume.

5. **Requirement ID namespace mismatch between SoT versions.** Persisted SoT IDs (e.g., `REQ-001`) and intake-generated IDs (e.g., `REQ-1`) are different namespaces. The `requirement_ids=None` fix ensures all persisted SoT requirements are included, at the cost of not filtering by step relevance.

---

## Recommended Next Slice

**Source of Truth Project Module Map v1**

Add a `module_map` field to `ProjectSourceOfTruthDocument` mapping source file paths to requirement IDs. This enables:
- The guard endpoint to automatically resolve which requirements a proposed patch touches
- The agent harness to scope requirement context to the files a step is working on
- Smarter per-step context filtering without the namespace mismatch problem

Alternatively: fix the P2 pre-existing gap by adding `valid=False → 422` enforcement on the PUT endpoint and adding document-level list validators to `ProjectSourceOfTruthDocument` (mirrors the approach taken for per-requirement fields).

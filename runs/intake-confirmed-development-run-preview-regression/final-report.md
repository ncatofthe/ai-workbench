# Intake → Confirmed Development Run Preview — Regression Pass

**Date:** 2026-06-01  
**Run type:** Read-only stability audit  
**Verdict: CLEAN — 0 P0, 0 P1, 0 changes made**

---

## Baseline

| Check | Baseline | Result |
|---|---|---|
| test_intake_confirmed_development_run_preview | 61 passed | 61 passed ✅ |
| test_multi_agent_plan_from_intake | 58 passed | 58 passed ✅ |
| test_auto_module_map_draft_from_intake | 63 passed | 63 passed ✅ |
| test_auto_source_of_truth_draft_from_intake | 114 passed | 114 passed ✅ |
| test_clarifying_questions_engine | 52 passed | 52 passed ✅ |
| test_unified_autonomous_project_intake | 44 passed | 44 passed ✅ |
| test_real_project_end_to_end_delivery_dogfood | 45 passed | 45 passed ✅ |
| test_project_context_cockpit | 26 passed | 26 passed ✅ |
| Full backend pytest | 1760 passed | 1760 passed ✅ |
| Frontend tsc --noEmit | clean | clean ✅ |
| npm run build | clean | clean ✅ |
| E2E smoke (Playwright) | 2 passed | 2 passed ✅ |
| scripts/run_tests.sh | clean | clean ✅ |

---

## Area-by-Area Audit

### 1. Model Integrity (`project_intake.py` — dev run preview models)

- `IntakeDevelopmentRunPreviewRequest`: fields `intake`, `answers`, `source_of_truth_draft` (Optional dict), `module_map_draft` (Optional dict), `multi_agent_plan` (Optional dict), `preferred_mode` (str, default "guided") — all present and correct.
- `DevelopmentRunPreviewStep`: `provider_allowed: bool = False` — default hardcoded, never overridden in any step construction path. `manual_approval_required: bool = False` — default, elevated only for risky tasks (auth, database, deployment). All fields present.
- `DevelopmentRunPreviewValidation`: `ready_to_create_run`, `readiness`, `errors`, `warnings`, `missing_inputs`, `blocked_reasons`.
- `IntakeDevelopmentRunPreviewResponse`: `preview_only: bool = True` — hardcoded default, confirmed never overridden.
- **Result: CLEAN**

### 2. Endpoint Safety (`routes.py` lines 5562–5576)

- Endpoint: `POST /api/project-intake/development-run-preview`
- Body: validates `title` or `raw_input` non-empty (→ 400 if missing), then delegates entirely to `build_intake_development_run_preview(req)`.
- No DB reads, no DB writes, no `_upsert_sot`, no `get_project`, no `create_run`, no `create_run_step`, no provider calls.
- Docstring explicitly states preview-only constraints.
- **Result: CLEAN**

### 3. Builder Safety (`build_intake_development_run_preview`)

Comprehensive forbidden-pattern scan on `project_intake.py` lines 4970+:

| Pattern | Status |
|---|---|
| `execute_run` | NOT FOUND ✅ |
| `asyncio.create_task` | NOT FOUND ✅ |
| `subprocess.` | NOT FOUND ✅ |
| `os.system` / `os.popen` | NOT FOUND ✅ |
| `create_tool_call` | NOT FOUND ✅ |
| `create_run(` (as function call) | NOT FOUND ✅ |
| `create_run_step` | NOT FOUND ✅ |
| `_upsert_sot` | NOT FOUND ✅ |
| `apply_patch` | NOT FOUND ✅ |
| `eval(` / `exec(` | NOT FOUND ✅ |

`provider_allowed=False` confirmed hardcoded in:
- `_drp_step_from_task()` — inline step construction
- `_drp_context_step()` — context confirmation step
- `_drp_module_review_step()` — module review step
- Inline step at line 5340 (context/SoT confirmation step)

`preview_only=True` confirmed hardcoded in `IntakeDevelopmentRunPreviewResponse` default and in builder return statement.

- **Result: CLEAN**

### 4. Fallback / Resilience

- `_drp_parse_plan()`: safely handles `None`, empty `{}`, invalid structure — falls back to `build_multi_agent_plan_from_intake()` (pure function).
- Missing SoT draft → warning added to validation, continues.
- Missing module map draft → warning added to validation, continues.
- Empty plan → conservative fallback steps generated, warnings issued.
- Secret-like content in inputs → `_drp_has_secret_like_content()` detects and blocks via validation errors.
- **Result: CLEAN**

### 5. Frontend Types (`types/index.ts` lines 2358–2410)

- `IntakeDevelopmentRunPreviewRequest` — matches backend model exactly, all optional draft fields typed.
- `DevelopmentRunPreviewStep` — includes `provider_allowed: boolean`, `manual_approval_required: boolean`.
- `DevelopmentRunPreviewValidation` — matches backend exactly.
- `IntakeDevelopmentRunPreviewResponse` — `preview_only: boolean` present.
- No stale or missing fields.
- **Result: CLEAN**

### 6. Frontend API Client (`client.ts` lines 575–577)

- `previewIntakeDevelopmentRun(data: IntakeDevelopmentRunPreviewRequest)` defined and correctly typed.
- POSTs to `/api/project-intake/development-run-preview`.
- **Result: CLEAN**

### 7. Frontend UI (`NewTask.tsx`)

- State: `developmentRunPreviewResult`, `developmentRunPreviewLoading`, `developmentRunPreviewError` — all initialized correctly.
- Result reset on new refinement / mode changes (6 reset call sites found).
- Handler: `handleBuildSoTDraft` / dev run preview handler calls `previewIntakeDevelopmentRun` with `preview_only: true` — no `confirm_persist`, no `project_id`.
- `IntakeDevelopmentRunPreviewPanel` component renders validation, steps, safety summary, limitations.
- `provider_allowed` field surfaced in UI (read from response).
- **Result: CLEAN**

### 8. Targeted Test Suite (61 tests)

All 10 test classes passed:
- `TestModelAndBounds` (8) — determinism, bounds, step IDs
- `TestIdeaMode` (4) — context confirmation step, expected step types, no project creation
- `TestDocumentMode` (4) — requirement normalization step, AC validation, no raw document dump
- `TestExistingProjectMode` (7) — repo inventory, test discovery, protected modules, first safe patch, no file reads, no commands
- `TestLinkage` (7) — SoT/module/plan linkage, graceful degradation
- `TestSafetyPolicy` (8) — `provider_allowed=False`, risky tasks get approval gates, no execution implied
- `TestEndpoint` (9) — 400/200 responses, no project/run/step/tool-call creation, determinism
- `TestCompatibilityImports` (5) — upstream builders still importable
- `TestStaticSafety` (9) — all forbidden patterns absent in source file

**Result: 61/61 PASSED**

### 9. Full Backend Suite

**1760/1760 passed, 38 subtests passed** — no regressions introduced.

### 10. Frontend Build

- `tsc --noEmit`: no errors
- `npm run build`: successful (1 chunk-size warning — pre-existing, not a correctness issue)

### 11. E2E Smoke Tests

**2/2 passed** — app shell, primary routes, RunDetail cockpit tabs all render correctly.

---

## Static Safety Summary

| Constraint | Status |
|---|---|
| No DB schema changes | ✅ None |
| No migrations | ✅ None |
| No provider calls | ✅ Confirmed |
| No network calls | ✅ Confirmed |
| No file content reads | ✅ Confirmed |
| No shell/subprocess/os commands | ✅ Confirmed |
| No execute_run | ✅ Confirmed |
| No asyncio.create_task | ✅ Confirmed |
| No create_tool_call | ✅ Confirmed |
| No project creation | ✅ Confirmed |
| No run creation | ✅ Confirmed |
| No run step creation | ✅ Confirmed |
| No patch proposal creation | ✅ Confirmed |
| No apply patch | ✅ Confirmed |
| No auto-rollback | ✅ Confirmed |
| No guard bypass | ✅ Confirmed |
| No approval bypass | ✅ Confirmed |
| Start Task behavior unchanged | ✅ Confirmed |
| Confirmed-run behavior unchanged | ✅ Confirmed |
| Existing create-run payloads unchanged | ✅ Confirmed |
| Tests not weakened | ✅ Confirmed |

---

## Findings

**P0 issues: 0**  
**P1 issues: 0**  
**P2/advisory: 0**  
**Changes made: 0**

---

## Verdict

**CLEAN.** The Intake → Confirmed Development Run Preview v1 feature is stable. All 11 audit areas pass. No regressions in the full 1760-test backend suite, frontend tsc/build, or E2E smoke. No changes were made.

---

## Recommended Next Slice

**Confirmed Development Run Creation Contract v1** — the endpoint at `POST /api/project-intake/confirmed-run` (`ConfirmedRunFromPlanRequest` → `ConfirmedRunFromPlanResponse`) exists and is guarded by `confirm: true`. A dedicated contract and regression suite for that endpoint would close the loop from preview → actual run creation with explicit user confirmation, hardened constraints, and test coverage.

Alternatively: **Existing SaaS Project Intake Dogfood v1** — apply the full intake pipeline to the AI Workbench project itself as a real-world validation.

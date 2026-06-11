# Auto Source of Truth Draft from Intake — Regression Pass

**Run ID:** auto-source-of-truth-draft-from-intake-regression  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Pass type:** Regression / stability audit  
**Status:** CLEAN — no P0/P1 issues found, no source changes needed

---

## Summary

Full regression audit of the Auto Source of Truth Draft from Intake v1 implementation across all 10 audit areas. No P0 or P1 issues found. No source files were modified. All required checks pass at baseline.

---

## 1. Model / Response Compatibility Validation

**Result: PASS**

`SourceOfTruthDraftFromIntakeRequest(intake: ClarifyingAnswersRequest, project_id: Optional[str] = None, confirm_persist: bool = False)`

- Shape is stable ✓
- `intake` is a `ClarifyingAnswersRequest` (wraps `UnifiedIntakeRequest` + `list[ClarifyingAnswer]`) ✓
- `project_id` defaults to `None` ✓
- `confirm_persist` defaults to `False` ✓

`SourceOfTruthDraftValidation(valid, drift_risk, errors, warnings, fields_populated, requirements_count)`

- Shape is stable ✓
- `drift_risk` defaults to `"low"` ✓
- `errors` and `warnings` default to `[]` ✓
- `fields_populated` and `requirements_count` default to `0` ✓

`SourceOfTruthDraftFromIntakeResponse(mode, source, draft, validation, persisted, project_id, version, confidence, next_recommended_action, safety_notes, limitations)`

- Shape is stable ✓
- `draft` is a `SourceOfTruthUpsertRequest` ✓
- `persisted` defaults to `False` ✓
- `project_id` and `version` default to `None` ✓
- `safety_notes` and `limitations` are non-empty lists ✓

Frontend TypeScript interfaces match backend response shapes ✓  
`SourceOfTruthDraftUpsertPayload` matches `SourceOfTruthUpsertRequest` fields ✓  
`SourceOfTruthDraftValidation` interface matches backend model ✓  
Existing `SourceOfTruthUpsertRequest`, `ProjectSourceOfTruthDocument` models untouched ✓  
Existing clarifying/intake models untouched ✓

---

## 2. Draft Builder Behavior Validation

**Result: PASS**

`build_source_of_truth_draft_from_intake(req: SourceOfTruthDraftFromIntakeRequest) → SourceOfTruthDraftFromIntakeResponse`

- Deterministic for identical input ✓
- Internally calls `refine_unified_intake_with_answers()` — no side effects ✓
- `product_name` mapped from CQE sot.product_name, truncated + secret-stripped at 80 chars ✓
- `product_summary` mapped from sot.product_summary, truncated + secret-stripped at 300 chars ✓
- `project_intent` from intake.title or intake.raw_input or sot.product_summary, bounded at 300 chars ✓
- `target_users`, `goals`, `non_goals`, `constraints`, `risks`, `open_questions` each bounded at 10 items, secret-filtered ✓
- `acceptance_criteria`, `architecture_notes`, `assumptions`, `decisions`, `forbidden_changes` left empty (not mapped from intake) — safe default ✓
- Requirements generated via `_sot_draft_build_requirements(clean_goals)` — stable REQ-001..N IDs ✓
- All output bounded (`goals ≤ 10`, `requirements ≤ 10`, `summary ≤ 300 chars`) ✓
- No raw document dump — `document_excerpt` never echoed into output fields ✓
- No raw repository dump — `project_path` used only as a string hint for intent extraction ✓
- No file contents in any output field ✓
- No DB writes in builder ✓
- No provider calls in builder ✓
- No project/run/tool_call creation ✓
- `persisted=False`, `project_id=None`, `version=None` always returned by builder ✓
- `status="draft"` always set — never `"active"` from intake ✓

---

## 3. Idea Mode Validation

**Result: PASS**

- `draft.source = "intake_idea"` and `response.source = "intake_idea"` ✓
- `product_name` and `product_summary` generated safely ✓
- `cq-idea-2` answer updates `target_users` ✓
- `cq-idea-1` answer updates `product_summary` ✓
- Goals appear in `draft.goals` and produce `requirements` ✓
- `open_questions` carry unresolved scope/user/stack questions ✓
- Requirements are generated from goals; stable REQ-001..N IDs ✓
- Missing fields produce validation warnings, not crashes ✓
- No hidden persistence — `persisted=False` for all idea-mode calls ✓

---

## 4. Document Mode Validation

**Result: PASS**

- `draft.source = "intake_document"` ✓
- `product_summary` bounded at 300 chars — raw `document_excerpt` never dumped ✓
- Requirements generated from document goals; bounded ✓
- Ambiguous/weak document input produces validation warnings (`target_users is empty`) ✓
- Deterministic for same document input ✓
- No upload parsing ✓
- No provider/LLM reasoning ✓
- No file reads ✓

---

## 5. Existing Project Mode Validation

**Result: PASS**

- `draft.source = "intake_existing_project"` ✓
- `project_path` used only as string hint for `project_intent` extraction ✓
- Nonexistent path (`/nonexistent/path/that/does/not/exist`) does not crash ✓
- No `os.listdir`, no `pathlib.Path`, no `open()`, no `.read_text()` in CQE/SoT sections ✓
- `known_stack` appears only via the CQE refinement pass — no direct filesystem access ✓
- `cq-ep-4/5/6` answers flow into `constraints` via CQE → builder correctly ✓
- No patch/proposal/apply/test execution ✓

---

## 6. Validation Behavior Validation

**Result: PASS**

- Empty `product_summary` + empty `project_intent` → `valid=False`, `errors` list populated ✓
- Empty `product_summary` + empty `project_intent` → `drift_risk="critical"` ✓
- Missing `target_users` → `warnings` populated, `drift_risk="medium"` ✓
- Missing `goals` → `warnings` populated ✓
- Secret-like text in goals/constraints/risks/open_questions → `errors` populated by belt-and-suspenders check ✓
- Validation messages are operator-readable (e.g. `"target_users is empty"`) ✓
- Validation does not mutate the draft — verified that `draft.target_users` unchanged after call ✓
- Rejected secret-like text does not leak into output — `_sot_draft_clean` returns `""` for secrets ✓

---

## 7. Preview Endpoint Validation

**Result: PASS**

`POST /api/project-intake/source-of-truth-draft` (routes.py)

- Always preview-only — one-line body: `return build_source_of_truth_draft_from_intake(req)` ✓
- `persisted=False` always in response ✓
- `confirm_persist=True` in body silently ignored by preview endpoint — static scan confirms `_upsert_sot` not called ✓
- Returns 200 for `idea`, `document`, `existing_project` modes ✓
- Returns 422 for invalid mode ✓
- Returns 400 when both `title` and `raw_input` empty ✓
- Creates no project ✓
- Creates no run ✓
- Creates no tool_calls ✓
- Calls no providers ✓
- Reads no files ✓
- Executes no commands ✓
- Deterministic for same input ✓
- Existing `/api/project-intake/unified-preview` and `/api/project-intake/clarifying-preview` endpoints unaffected ✓

---

## 8. Confirm Endpoint Validation

**Result: PASS**

`POST /api/project-intake/source-of-truth-draft/confirm` (routes.py)

- Requires `confirm_persist=True` to persist; `confirm_persist=False` → preview-only behavior ✓
- Returns 400 when `confirm_persist=True` but `project_id` is absent ✓
- Returns 404 when `project_id` does not match a known project ✓
- `_upsert_sot` is inside `if req.confirm_persist:` guard — confirmed via static analysis ✓
- `project_id` check is inside `if req.confirm_persist:` guard ✓
- On persist: builds `ProjectSourceOfTruthDocument` from draft, calls `_upsert_sot(project_id, doc)` ✓
- On persist: `status="draft"` hardcoded — never `"active"` from intake ✓
- On persist: returns `persisted=True`, `project_id`, `version` from stored document ✓
- Does not create project ✓
- Does not create run ✓
- Does not create tool_calls ✓
- Does not call providers ✓
- Does not read files ✓
- Does not execute commands ✓
- No hidden persistence without explicit confirm ✓

---

## 9. Frontend NewTask Behavior Validation

**Result: PASS (with one P2 note)**

- "Build Source of Truth draft" button calls only `handleBuildSoTDraft()` ✓
- `handleBuildSoTDraft()` calls only `buildSoTDraftFromIntake()` — confirmed `confirmSoTDraftFromIntake` and `createRun` absent ✓
- `confirm_persist: false` hardcoded in `handleBuildSoTDraft` — no accidental persistence ✓
- `SoTDraftFromIntakePanel` renders:
  - validation state (valid/invalid badge, drift risk badge) ✓
  - errors list ✓
  - warnings list ✓
  - `product_name`, `product_summary` ✓
  - `target_users` ✓
  - `goals` ✓
  - `requirements` (with REQ-NNN IDs and priority badges) ✓
  - `constraints` ✓
  - `risks` ✓
  - `open_questions` ✓
  - `next_recommended_action` ✓
  - read-only disclaimer ✓
  - **Missing fields/score display (fields_populated count) — not rendered (P2, see below)** ⚠
  - **`safety_notes` not rendered in `SoTDraftFromIntakePanel` (P2, see below)** ⚠
- No hidden `createRun` call from SoT draft button ✓
- No hidden project creation ✓
- No hidden provider call ✓
- No upload parsing ✓
- No file scanning ✓
- Existing NewTask create flow (`handleStart`, `handleConfirmedRun`) untouched ✓
- `tsc --noEmit`: clean ✓
- `npm run build`: 48 modules, no errors ✓

---

## 10. Safety / Static Scan Validation

**Result: PASS — all clean**

Scanned the SoT draft section (`# ── Auto Source of Truth Draft from Intake v1` to EOF, ~257 lines) and both route endpoint functions.

| Pattern | Result |
|---------|--------|
| `execute_run` | Not found ✓ |
| `asyncio.create_task` | Not found ✓ |
| `subprocess.` | Not found ✓ |
| `os.system` | Not found ✓ |
| `os.popen` | Not found ✓ |
| `call_provider` | Not found ✓ |
| `ollama_client` | Not found ✓ |
| `anthropic.Anthropic` | Not found ✓ |
| `create_tool_call` | Not found ✓ |
| `create_project` | Not found ✓ |
| `create_run` | Not found ✓ |
| `save_project` | Not found ✓ |
| `save_run` | Not found ✓ |
| `save_tool_call` | Not found ✓ |
| `db.execute` | Not found ✓ |
| `apply_project_patch` | Not found ✓ |
| `propose_project_patch` | Not found ✓ |
| `open(` | Not found ✓ |
| `.read_text(` | Not found ✓ |
| `.read()` / `.readlines()` | Not found ✓ |
| `pathlib.Path` | Not found ✓ |
| `os.listdir` | Not found ✓ |
| `.scandir(` | Not found ✓ |

Route endpoint sections (`post_project_intake_source_of_truth_draft`, `post_project_intake_source_of_truth_draft_confirm`): clean for `execute_run`, `asyncio.create_task`, and `_upsert_sot` not present in preview function ✓

Frontend `SoTDraftFromIntakePanel` and `handleBuildSoTDraft`: no `createRun`, no `createProject`, no `fetch` calls, no `confirmSoTDraftFromIntake` ✓

---

## 11. Workflow Compatibility Validation

**Result: PASS — all suites at baseline**

| Suite | Result |
|-------|--------|
| `test_auto_source_of_truth_draft_from_intake.py` | **114 passed** |
| `test_clarifying_questions_engine.py` | **52 passed** |
| `test_unified_autonomous_project_intake.py` | **44 passed** |
| `test_persistent_source_of_truth.py` | **31 passed** |
| `test_source_of_truth_run_creation_wiring.py` | **29 passed** |
| `test_real_project_end_to_end_delivery_dogfood.py` | **45 passed** |
| `test_project_context_cockpit.py` | **26 passed** |
| Full `pytest -q` | **1578 passed, 38 subtests** |
| `npx tsc --noEmit` | **clean** |
| `npm run build` | **48 modules, no errors** |
| `npm run test:e2e:smoke` | **2 passed** |
| `scripts/run_tests.sh` | **passed** |

---

## P0 / P1 / P2 / P3 Issues Found

| Severity | Area | Issue | Action |
|----------|------|-------|--------|
| P2 | Frontend | `SoTDraftFromIntakePanel` does not render `result.safety_notes` or `result.limitations`. These fields exist in the response but are not shown in the draft panel. Safety notes are visible in the parent `ClarifiedIntakePreviewPanel`'s read-only disclaimer. | Document only — not a safety or correctness failure |
| P2 | Frontend | `SoTDraftFromIntakePanel` does not render `validation.fields_populated` count. Value is present in the response and in the confidence badge row. | Document only — cosmetic omission |
| — | All other areas | None found | — |

**No P0/P1 issues found. No source files changed.**

---

## Changes Made

**None.** This was a read-only regression audit. All source files inspected, no modifications made.

---

## Touched Files

| File | Touched? |
|------|----------|
| `backend/src/storage/database.py` | **No** |
| `backend/src/orchestrator/engine.py` | **No** |
| `backend/src/project_tools.py` | **No** |
| `backend/src/model_router.py` | **No** |
| `backend/src/providers/*` | **No** |
| Any source file | **No** |

---

## Known Limitations (still true)

1. **Deterministic draft only** — no LLM/provider reasoning; all field mapping is direct from CQE output
2. **No provider/LLM reasoning** — confidence ceiling is "medium"; high-confidence draft requires human review in a future slice
3. **No document upload extraction** — `document_excerpt` is plain text only; no PDF/DOCX parsing
4. **No repository file scanning** — `project_path` is a string hint only; no filesystem traversal
5. **No automatic project creation** — draft must be submitted to an existing project via `/confirm`
6. **No automatic run creation** — intake screen is fully read-only end-to-end
7. **No Module Map persistence** — module map draft is preview-only
8. **No agent execution from intake screen** — plan steps are recommendations, not executable tasks

---

## Recommended Next Slice

**Auto Module Map Draft from Intake v1**

Mirror the SoT draft pattern: take the CQE-refined `DraftModuleMapPreview` and convert it into a persistable `ProjectModuleMapUpsertRequest`, with:
- `POST /api/project-intake/module-map-draft` (preview-only)
- `POST /api/project-intake/module-map-draft/confirm` (persist gate: `confirm_persist=True` + `project_id`)
- Frontend "Build Module Map draft" button in `ClarifiedIntakePreviewPanel`
- `ModuleMapDraftFromIntakePanel` component

This would complete the intake pipeline's two-artifact loop: SoT draft + Module Map draft both available as explicit, confirmable artifacts from the intake screen.

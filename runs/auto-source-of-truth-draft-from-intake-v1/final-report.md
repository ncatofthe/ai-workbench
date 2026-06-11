# Auto Source of Truth Draft from Intake v1 — Final Report

**Run ID:** auto-source-of-truth-draft-from-intake-v1  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Status:** COMPLETE ✓

---

## Summary

Implemented a deterministic, preview-first Source of Truth draft builder that converts a Clarifying Questions Engine (CQE) answered intake into a structured `SourceOfTruthUpsertRequest` draft — with optional persistence via explicit operator confirmation.

**Why this slice:** The Clarifying Questions Engine v1 closes the intake loop to the point of a refined `DraftSourceOfTruthPreview`. This slice takes the final step: converting that preview into a proper, persistable `SourceOfTruthUpsertRequest` with stable REQ-001..N requirement IDs, secret filtering, validation, and a controlled persistence gate.

---

## New Models

Added to `backend/src/orchestrator/project_intake.py`:

| Model | Purpose |
|-------|---------|
| `SourceOfTruthDraftFromIntakeRequest` | Request: `intake: ClarifyingAnswersRequest`, `project_id: Optional[str]`, `confirm_persist: bool = False` |
| `SourceOfTruthDraftValidation` | `valid`, `drift_risk`, `errors`, `warnings`, `fields_populated`, `requirements_count` |
| `SourceOfTruthDraftFromIntakeResponse` | Full response: `mode`, `source`, `draft`, `validation`, `persisted`, `project_id`, `version`, `confidence`, `next_recommended_action`, `safety_notes`, `limitations` |

---

## New Pure Helpers

Added to `backend/src/orchestrator/project_intake.py`:

| Function | Purpose |
|----------|---------|
| `_sot_draft_source_for_mode(mode)` | Maps intake mode → source identifier (`intake_idea`, `intake_document`, `intake_existing_project`) |
| `_sot_draft_clean(text, max_chars)` | Truncates AND rejects secret-like text (returns `""` if secret-like) |
| `_sot_draft_clean_list(items, max_per)` | Applies `_sot_draft_clean` to every list item; drops empty/secret entries |
| `_sot_draft_build_requirements(goals)` | Builds stable `REQ-001..N` requirements from goals (first 3 = "must", rest = "should"); skips secret-like goals |
| `_sot_draft_validate(draft)` | Pure validation of `SourceOfTruthUpsertRequest`: required-field checks, secret checks, field count, requirement count |
| `build_source_of_truth_draft_from_intake(req)` | Public builder — pure, no DB, no LLM, no filesystem |

---

## Draft Builder Behavior

`build_source_of_truth_draft_from_intake(req: SourceOfTruthDraftFromIntakeRequest) → SourceOfTruthDraftFromIntakeResponse`

1. Calls `refine_unified_intake_with_answers(req.intake)` to get the CQE-refined preview
2. Maps `DraftSourceOfTruthPreview` fields to `SourceOfTruthUpsertRequest`:
   - `product_name`, `product_summary`, `project_intent` — truncated + secret-stripped
   - `target_users`, `goals`, `non_goals`, `constraints`, `risks`, `open_questions` — each list cleaned, bounded to 10 items
   - `requirements` — generated from cleaned goals; stable REQ-001..N IDs; first 3 "must", rest "should"
   - `source` — set to `intake_idea`, `intake_document`, or `intake_existing_project` based on mode
   - `status` — always `"draft"` (never `"active"` from intake)
3. Validates via `_sot_draft_validate()` — returns `SourceOfTruthDraftValidation`
4. Returns `persisted=False`, `project_id=None`, `version=None` — **persistence is never done in this function**
5. Sets `confidence` from CQE output (`"low"` or `"medium"`)
6. Returns mode-appropriate `next_recommended_action`

---

## Backend Endpoints Added

### `POST /api/project-intake/source-of-truth-draft`

```
Input:  SourceOfTruthDraftFromIntakeRequest
Output: SourceOfTruthDraftFromIntakeResponse
```

Preview-only. `confirm_persist` and `project_id` are accepted in body but **silently ignored** — no DB write ever occurs. Returns 400 if neither `title` nor `raw_input` is provided.

### `POST /api/project-intake/source-of-truth-draft/confirm`

```
Input:  SourceOfTruthDraftFromIntakeRequest  { confirm_persist, project_id }
Output: SourceOfTruthDraftFromIntakeResponse  { persisted, version }
```

Builds the draft identically, then:
- **No-persist path** (`confirm_persist=False`): same as preview endpoint — no DB write
- **Persist path** (`confirm_persist=True` + `project_id` provided):
  - Returns 400 if `project_id` is missing
  - Returns 404 if project not found
  - Builds `ProjectSourceOfTruthDocument` from draft, calls `_upsert_sot(project_id, doc)`
  - Returns `persisted=True`, `project_id`, `version` from stored document

**Both endpoints:** no provider calls, no LLM calls, no run creation, no agent execution, no project creation, no tool_calls, no filesystem reads.

---

## Frontend UI Changes

`frontend/src/pages/NewTask.tsx`:

- **New state:** `sotDraftResult`, `sotDraftLoading`, `sotDraftError`
- **New handler:** `handleBuildSoTDraft()` — calls `buildSoTDraftFromIntake` with the current intake payload and answers
- **Updated:** `handleRefineWithAnswers` resets `sotDraftResult` on new refinement
- **Updated:** `ClarifiedIntakePreviewPanel` accepts optional `onBuildSoTDraft`, `sotDraftLoading`, `sotDraftError`, `sotDraftResult` props
- **Added in panel:** "Build Source of Truth draft" button (emerald, read-only note)
- **New component:** `SoTDraftFromIntakePanel` — shows validation (valid/invalid, drift risk, errors, warnings), draft fields (product_name, summary, target_users, goals, requirements, constraints, risks, open_questions), next recommended action, read-only disclaimer

`frontend/src/api/client.ts`:
- `buildSoTDraftFromIntake(data: SourceOfTruthDraftFromIntakeRequest) → SourceOfTruthDraftFromIntakeResponse`
- `confirmSoTDraftFromIntake(data: SourceOfTruthDraftFromIntakeRequest) → SourceOfTruthDraftFromIntakeResponse`

`frontend/src/types/index.ts`:
- 4 new interfaces: `SourceOfTruthDraftRequirement`, `SourceOfTruthDraftUpsertPayload`, `SourceOfTruthDraftValidation`, `SourceOfTruthDraftFromIntakeRequest`, `SourceOfTruthDraftFromIntakeResponse`

**Existing NewTask create flow unchanged.** `createRun`, `createRunFromConfirmedPlan`, `handleStart`, `handleConfirmedRun` untouched.

---

## Safety Boundaries

- No `execute_run` in SoT draft section ✓
- No `asyncio.create_task` in SoT draft section ✓
- No `subprocess.` / `os.system` / `os.popen` ✓
- No `call_provider` / `ollama_client` / `anthropic.Anthropic` ✓
- No `open(` / `.read_text(` / `pathlib.Path` / `os.listdir` / `.scandir(` ✓
- No `save_project` / `save_run` / `save_tool_call` / `db.execute` ✓
- No `create_tool_call` ✓
- `database.py` untouched ✓
- `engine.py` untouched ✓
- `providers/*` untouched ✓
- `model_router.py` untouched ✓
- `project_tools.py` untouched ✓
- No DB schema changes, no migrations ✓
- No git push ✓
- Secret-like values rejected at every layer (goal cleaning, requirement building, Pydantic validators, validation report) ✓
- Draft `status` is always `"draft"` — never `"active"` from intake ✓
- Persistence requires explicit `confirm_persist=True` + valid `project_id` ✓

---

## Tests Added

**File:** `backend/tests/test_auto_source_of_truth_draft_from_intake.py` — **114 tests** across 10 classes:

| Class | Tests | Coverage |
|-------|-------|---------|
| `TestSoTDraftModels` | 8 | model shapes, field defaults, response structure |
| `TestSoTDraftHelpers` | 22 | `_sot_draft_clean`, `_sot_draft_clean_list`, `_sot_draft_build_requirements`, `_sot_draft_validate`, `_sot_draft_source_for_mode` |
| `TestSoTDraftIdeaMode` | 16 | idea end-to-end, confidence, determinism, bounds, answer mapping |
| `TestSoTDraftDocumentMode` | 8 | document end-to-end, summary bounds, requirements |
| `TestSoTDraftExistingProjectMode` | 6 | ep mode, file safety, goal/constraint refinement |
| `TestSoTDraftPreviewEndpoint` | 13 | HTTP 200 × 3 modes, 422, read-only, no DB, deterministic |
| `TestSoTDraftConfirmEndpoint` | 8 | no-persist, 400 missing pid, 404 unknown pid, persist path, no spurious writes |
| `TestSoTDraftSecretRejection` | 6 | goal/constraint/summary/requirement secret filtering, belt-and-suspenders validator |
| `TestSoTDraftStaticAnalysis` | 15 | all forbidden patterns not present in new section |
| `TestSoTDraftCompatibility` | 6 | all existing endpoints unaffected, model shapes unchanged |

---

## Files Changed

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | 3 import lines added at top; ~210 lines appended (SoT draft section) |
| `backend/src/api/routes.py` | 3 imports added; 2 endpoints added (~70 lines) |
| `backend/tests/test_auto_source_of_truth_draft_from_intake.py` | **NEW** — 114 tests |
| `frontend/src/types/index.ts` | 5 interfaces appended |
| `frontend/src/api/client.ts` | 2 import additions + 2 functions added |
| `frontend/src/pages/NewTask.tsx` | New state/handler + `ClarifiedIntakePreviewPanel` extended + `SoTDraftFromIntakePanel` added |
| `runs/auto-source-of-truth-draft-from-intake-v1/final-report.md` | **NEW** |

**Untouched:** `database.py`, `engine.py`, `providers/*`, `model_router.py`, `project_tools.py`, `scripts/run_tests.sh`

---

## P0 / P1 / P2 / P3 Issues

| Severity | Issue | Resolution |
|----------|-------|------------|
| — | None found | — |

---

## Exact Check Results

| Check | Result |
|-------|--------|
| `py_compile project_intake.py` | EXIT:0 ✓ |
| `py_compile routes.py` | EXIT:0 ✓ |
| `py_compile test_auto_source_of_truth_draft_from_intake.py` | EXIT:0 ✓ |
| `pytest test_auto_source_of_truth_draft_from_intake.py` | **114 passed** ✓ |
| `pytest test_clarifying_questions_engine.py` | 52 passed ✓ |
| `pytest test_unified_autonomous_project_intake.py` | 44 passed ✓ |
| `pytest test_project_intake.py` | 67 passed, 7 subtests ✓ |
| `pytest test_persistent_source_of_truth.py` | 31 passed ✓ |
| `pytest test_source_of_truth_run_creation_wiring.py` | 29 passed ✓ |
| Full `pytest -q` | **1578 passed, 38 subtests** ✓ |
| `npx tsc --noEmit` | clean ✓ |
| `npm run build` | 48 modules, no errors ✓ |
| `scripts/run_tests.sh` | passed ✓ |

---

## Known Limitations

1. **Deterministic draft only** — no LLM/provider reasoning; all field mapping is direct from CQE output
2. **Confidence ceiling at "medium"** — high confidence requires LLM/human review in a future slice
3. **Requirements from goals only** — no free-form requirement parsing or document extraction
4. **No automatic SoT persistence** — draft must be explicitly submitted to `/confirm` with `confirm_persist=true` and a valid `project_id`
5. **No document or repository parsing** — `document_excerpt` and `project_path` are text hints only
6. **Draft status always "draft"** — operator must use the regular SoT upsert endpoint with `status="active"` to publish
7. **No requirement dependency or priority inference** — first 3 goals → "must", remainder → "should" is a heuristic only

---

## Recommended Next Slice

**Option A — SoT Draft Confirmation UI v1**  
Add a confirmation flow in the frontend to submit the draft to `/confirm` with `confirm_persist=true` and `project_id` selected from the projects dropdown. Shows persisted version number and links to the project's SoT history.

**Option B — LLM-Enhanced SoT Refinement**  
Wire an optional Ollama provider call to improve requirement quality, generate non-goals, and improve confidence from "medium" to "high" — with a hard no-persist gate until the operator approves.

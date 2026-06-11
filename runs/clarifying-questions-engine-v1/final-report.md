# Clarifying Questions Engine v1 — Final Report

**Run ID:** clarifying-questions-engine-v1  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Status:** COMPLETE ✓

---

## Summary

Implemented a deterministic, preview-only Clarifying Questions Engine (CQE) that lets a user answer structured intake questions and receive a refined Source of Truth draft, refined Module Map, and refined multi-agent plan — all without any LLM calls, DB writes, provider calls, file reads, or side effects.

**Why this slice:** The Unified Autonomous Project Intake v1 generates clarifying questions but could not apply user answers. CQE v1 closes that loop: answer intake questions → get a refined, higher-confidence preview → proceed to the full intake pipeline.

---

## Question Set Behavior

`build_clarifying_question_set(req: UnifiedIntakeRequest) → ClarifyingQuestionSet`

- Reuses `build_unified_autonomous_intake_preview()` to extract already-generated questions
- Returns structured metadata: `required_count`, `optional_count`, `categories` (ordered, deduplicated)
- Provides `next_recommended_action` pointing to the `/clarifying-preview` endpoint
- Deterministic for identical input
- No DB, no LLM, no providers, no file reads

---

## Answer Refinement Behavior

`refine_unified_intake_with_answers(req: ClarifyingAnswersRequest) → ClarifiedIntakePreviewResponse`

**Gap detection:**
- Answers indexed by `question_id`
- Missing required question → `ClarifyingAnswerGap(severity="warning")`
- Skipped required question → same gap
- Empty answer on required question → same gap
- Unknown `question_id` → silently ignored, never crashes

**Answer application (pure, bounded):**
- All answer text truncated with `_cqe_short()` before embedding (150 chars default, 80 for short fields, 300 for `product_summary`)
- Applied answers summarized in `applied_answer_summary` (capped at 12)
- "Constraints not confirmed" placeholder removed when real constraints are added

**Confidence:**
- `confidence_before` = baseline from unified preview (always `"low"`)
- `confidence_after` = `"medium"` when ≥ 50 % of required questions answered; `"low"` otherwise
- Never exceeds `"medium"` in this slice

---

## Idea Mode Behavior

Answers that refine the SoT:

| Question ID | Field refined |
|-------------|--------------|
| `cq-idea-1` | `product_summary` |
| `cq-idea-2` | `target_users` |
| `cq-idea-3` | `constraints` (build type) |
| `cq-idea-4` | `goals[0]` (platform-specific) |
| `cq-idea-5` | `goals` (success criteria) |
| `cq-idea-7` | `constraints` + module map `inferred_stack` |
| `cq-idea-8` | `goals` (auth requirement) |
| `cq-idea-9` | `goals` (data storage) |
| `cq-idea-10` | `constraints` (budget/timeline) |
| `cq-idea-12` | `constraints` (deployment) |

Module map: tech stack answer (`cq-idea-7`) splits on `,/;` to update `inferred_stack`. Module structure remains conceptual.  
Plan: returned unchanged from baseline (8 steps with product-analyst, architect, backend, frontend, database, QA, security, delivery).

---

## Document Mode Behavior

Answers that refine the SoT:

| Question ID | Field refined |
|-------------|--------------|
| `cq-doc-1` | `risks` (document status) |
| `cq-doc-2` | `goals` (must-have requirements) |
| `cq-doc-3` | `goals` (acceptance criteria) |
| `cq-doc-4` | `risks` (resolved ambiguity) |
| `cq-doc-5` | `constraints` + `inferred_stack` |
| `cq-doc-6` | `constraints` (deadline) |
| `cq-doc-8` | `goals` (security requirement) |

`product_summary` is always bounded at 300 chars — raw document never dumped.  
Plan: 7 steps with `business-analyst` (document analysis) + `product-manager` (requirement normalization).

---

## Existing Project Mode Behavior

Answers that refine the SoT:

| Question ID | Field refined |
|-------------|--------------|
| `cq-ep-1` | `goals` (preserve working) |
| `cq-ep-2` | `goals` (fix broken) |
| `cq-ep-3` | `goals` (target goal) |
| `cq-ep-4` | `constraints` (test command); removes "Test command not confirmed" risk |
| `cq-ep-5` | `constraints` (protected modules); removes "Protected modules not identified" risk |
| `cq-ep-6` | `constraints` (required services); removes "Database/env requirements not confirmed" risk |

`project_path` remains a string hint only — no `os.listdir`, no `pathlib.Path`, no `open()`.  
Plan: 6 steps with `orchestrator` (repo inventory), `product-manager` (SoT confirmation), `architect` (module map), `qa-expert` (test discovery), `backend-developer` (first safe patch candidate), `technical-writer` (delivery report).

---

## Backend Endpoints Added

### `POST /api/project-intake/clarifying-questions`

```
Input:  UnifiedIntakeRequest  (existing model, unchanged)
Output: ClarifyingQuestionSet
```

Pure read-only. Returns structured question set with categories, required/optional counts, next action.

### `POST /api/project-intake/clarifying-preview`

```
Input:  ClarifyingAnswersRequest  { intake: UnifiedIntakeRequest, answers: [ClarifyingAnswer] }
Output: ClarifiedIntakePreviewResponse
```

Pure read-only. Applies user answers and returns refined SoT, module map, plan, gaps, confidence before/after.

**Both endpoints:** no DB writes, no project/run creation, no tool_calls, no provider calls, no file reads, no shell commands. Invalid mode → 422.

**Unchanged endpoints:** `/api/project-intake/unified-preview`, `/api/project-intake/analyze`, `/api/project-intake/source-of-truth`, confirmed-run, create-run.

---

## New Models

Added to `backend/src/orchestrator/project_intake.py`:

| Model | Purpose |
|-------|---------|
| `ClarifyingAnswer` | Single user answer: `question_id`, `answer`, `skipped` |
| `ClarifyingQuestionSet` | Structured question set with counts and categories |
| `ClarifyingAnswersRequest` | Request containing full intake + list of answers |
| `ClarifyingAnswerGap` | Missing required answer: `question_id`, `reason`, `severity` |
| `ClarifiedIntakePreviewResponse` | Full refined preview response |

---

## New Pure Helpers

Added to `backend/src/orchestrator/project_intake.py`:

| Function | Purpose |
|----------|---------|
| `_cqe_short(text, max_chars)` | Safe answer truncation — never a raw dump |
| `_compute_confidence_after(required_total, required_answered)` | Confidence upgrade logic (max "medium") |
| `_cqe_answered(qid, answer_map)` | Safe answer lookup, never crashes on unknown id |
| `_cqe_refine_sot(req, baseline, answer_map, summaries, confidence_after)` | Mode-specific SoT refinement |
| `_cqe_refine_module_map(req, baseline, answer_map)` | Stack-based module map refinement |
| `build_clarifying_question_set(req)` | Public builder — returns ClarifyingQuestionSet |
| `refine_unified_intake_with_answers(req)` | Public refiner — returns ClarifiedIntakePreviewResponse |

---

## Frontend UI Changes

`frontend/src/pages/NewTask.tsx`:

- **New state:** `answersMap: Record<string, string>`, `clarifiedResult`, `clarifiedLoading`, `clarifiedError`
- **New helper:** `_buildIntakePayload()` — shared intake reconstruction (DRY)
- **Updated:** `handleUnifiedPreview` resets `answersMap` and `clarifiedResult` on new preview
- **New handler:** `handleAnswerChange(questionId, value)` — updates `answersMap`
- **New handler:** `handleRefineWithAnswers()` — calls `previewClarifiedIntake` only, no project/run creation
- **Updated:** `UnifiedIntakePreviewPanel` accepts optional `answersMap`, `onAnswerChange`, `onRefine`, `clarifiedLoading`
- **Updated:** `UnifiedClarifyingQuestionCard` accepts optional `answer` + `onAnswerChange` — renders compact 2-row `<textarea>` when provided
- **Added in panel:** "Refine preview with answers" button (violet, read-only note)
- **New component:** `ClarifiedIntakePreviewPanel` — shows confidence before/after, missing answer gaps, applied summary, refined SoT/Module Map/Plan, next action
- **New component:** `ClarifiedAnswerGapRow` — displays one missing required answer warning

`frontend/src/api/client.ts`:
- `getClarifyingQuestions(data: UnifiedIntakeRequest) → ClarifyingQuestionSet`
- `previewClarifiedIntake(data: ClarifyingAnswersRequest) → ClarifiedIntakePreviewResponse`

`frontend/src/types/index.ts`:
- 5 new interfaces: `ClarifyingAnswer`, `ClarifyingQuestionSet`, `ClarifyingAnswersRequest`, `ClarifyingAnswerGap`, `ClarifiedIntakePreviewResponse`

**Existing NewTask create flow unchanged.** `createRun` and `createRunFromConfirmedPlan` are in separate handlers, untouched.

---

## Safety Boundaries

- No `execute_run` in CQE section ✓
- No `asyncio.create_task` in CQE section ✓
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

All 8 static analysis tests pass by construction and verified by the test suite.

---

## Tests Added

**File:** `backend/tests/test_clarifying_questions_engine.py` — **52 tests** across 6 classes:

| Class | Tests | Coverage |
|-------|-------|---------|
| `TestClarifyingQuestionSet` | 6 | mode, counts, categories, determinism |
| `TestAnswerHandling` | 6 | answered IDs, missing required, skip, unknown ID, empty, summary cap |
| `TestIdeaRefinement` | 7 | target users, goals, confidence, module map, stack, plan bounds |
| `TestDocumentRefinement` | 5 | requirements, no document dump, normalization step, confidence, stack |
| `TestExistingProjectRefinement` | 7 | what works/broken, file safety, inventory plan, protected modules, test command, target goal |
| `TestClarifyingQuestionsEndpoints` | 9 | HTTP 200 × 3 modes, 422 invalid, no project/run/tool_call, deterministic |
| `TestCompatibility` | 4 | unified preview still works, model defaults, field shapes |
| `TestCQESafetyAndStaticAnalysis` | 8 | all forbidden patterns, route endpoint sections |

---

## Files Changed

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | ~270 lines appended (CQE section) |
| `backend/src/api/routes.py` | 3 imports added; 2 endpoints added |
| `backend/tests/test_clarifying_questions_engine.py` | **NEW** — 52 tests |
| `frontend/src/types/index.ts` | 5 interfaces appended |
| `frontend/src/api/client.ts` | 2 imports + 2 functions added |
| `frontend/src/pages/NewTask.tsx` | Answer state/handlers + updated panel + 2 new components |
| `runs/clarifying-questions-engine-v1/final-report.md` | **NEW** |

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
| `py_compile models.py` | EXIT:0 ✓ |
| `py_compile routes.py` | EXIT:0 ✓ |
| `py_compile test_clarifying_questions_engine.py` | EXIT:0 ✓ |
| `pytest test_clarifying_questions_engine.py` | **52 passed** ✓ |
| `pytest test_unified_autonomous_project_intake.py` | 44 passed ✓ |
| `pytest test_project_intake.py` | 67 passed, 7 subtests ✓ |
| `pytest test_source_of_truth_run_creation_wiring.py` | 29 passed ✓ |
| `pytest test_real_project_end_to_end_delivery_dogfood.py` | 45 passed ✓ |
| `pytest test_project_context_cockpit.py` | 26 passed ✓ |
| `pytest test_provider_integration_hardening_contract.py` | 53 passed ✓ |
| `pytest test_auth_rbac_deployment_security_contract.py` | 47 passed ✓ |
| `pytest test_migration_backup_restore_contract.py` | 41 passed ✓ |
| Full `pytest -q` | **1464 passed, 38 subtests** ✓ |
| `npx tsc --noEmit` | clean ✓ |
| `npm run build` | 48 modules, no errors ✓ |
| `npm run test:e2e:smoke` | 2 passed ✓ |
| `scripts/run_tests.sh` | passed ✓ |

---

## Known Limitations

1. **Deterministic refinement only** — no LLM/provider reasoning; SoT refinement is keyword-mapping of answer text
2. **No persistent intake sessions** — answers and refinements are ephemeral per request; no DB storage
3. **No document upload or parsing** — `document_excerpt` is plain text only; no PDF/DOCX extraction
4. **No repository file scanning** — `existing_project` mode uses `project_path` as a string hint only
5. **No automatic SoT persistence** — refined SoT must be manually copied or submitted to the existing SoT pipeline
6. **No automatic Module Map persistence** — refined module map is preview-only
7. **No project or run creation** — intake screen is fully read-only end-to-end
8. **No agent assignment execution** — plan steps are recommendations, not executable tasks
9. **Confidence ceiling at "medium"** — "high" confidence requires LLM/human review in a future slice

---

## Recommended Next Slice

**Option A — Auto Source of Truth Draft from Intake v1**  
Wire refined answered intake → `build_source_of_truth_from_intake()` to create a persisted, confirmable SoT from the answered clarifying questions. This would complete the idea → SoT loop with one click.

**Option B — Clarifying Questions Engine Regression Pass**  
Stability audit of the CQE v1 implementation before the next feature slice.

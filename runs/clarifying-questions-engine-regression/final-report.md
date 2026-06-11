# Clarifying Questions Engine — Regression Pass

**Run ID:** clarifying-questions-engine-regression  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Pass type:** Regression / stability audit  
**Status:** CLEAN — no P0/P1 issues found, no source changes needed

---

## Summary

Full regression audit of the Clarifying Questions Engine v1 implementation across all 10 audit areas. No P0 or P1 issues found. No source files were modified. All required checks pass at baseline.

---

## Question Set Validation

**Result: PASS**

`build_clarifying_question_set(req: UnifiedIntakeRequest) → ClarifyingQuestionSet`

- Deterministic for identical input ✓
- Idea mode returns idea-scoped questions (cq-idea-*) ✓
- Document mode returns document/requirement questions (cq-doc-*) ✓
- existing_project mode returns project-awareness questions (cq-ep-*) ✓
- `required_count` = exact count of `required=True` questions ✓
- `optional_count` = remainder; `required_count + optional_count == len(questions)` ✓
- `categories` list is ordered by first appearance, deduplicated ✓
- `next_recommended_action` is non-empty and references `/clarifying-preview` ✓
- Output bounded: questions ≤ 12, categories ≤ 12 ✓
- No DB write, no provider call, no file read ✓

---

## Answer Refinement Validation

**Result: PASS**

`refine_unified_intake_with_answers(req: ClarifyingAnswersRequest) → ClarifiedIntakePreviewResponse`

- Deterministic for identical input ✓
- `answered_question_ids` contains all question_ids with non-empty, non-skipped answers ✓
- Missing required questions reported in `missing_required_questions` ✓
- Skipped required questions → `ClarifyingAnswerGap(severity="warning")` ✓
- Empty/whitespace answer treated as missing (not added to answered_ids) ✓
- Unknown `question_id` silently ignored via `_cqe_answered()` — no crash ✓
- `applied_answer_summary` capped at `_MAX_CQE_SUMMARIES = 12` ✓
- `confidence_before` always `"low"` (from baseline unified preview) ✓
- `confidence_after` capped at `"medium"` — never `"high"` in this slice ✓
- All answer text truncated via `_cqe_short(text, max_chars)` before embedding ✓
- SoT lists bounded: goals/non_goals/constraints/risks/open_questions ≤ 10 each ✓
- Module map modules ≤ 12, plan steps ≤ 12 ✓
- No raw huge answer blobs — `_cqe_short` enforces 150 char default (300 for `product_summary`) ✓
- No raw document dumps in `product_summary` ✓
- No repository dumps ✓

---

## Idea Mode Validation

**Result: PASS**

- `cq-idea-2` answer updates `target_users` ✓
- `cq-idea-5` answer appends success criteria to `goals` ✓
- `cq-idea-7` answer updates `constraints` AND splits `inferred_stack` on `,/;` ✓
- Answering ≥ 50 % of 5 required questions improves confidence to `"medium"` ✓
- Answering all 5 required questions → `missing_required_questions = []` ✓
- Module map remains conceptual (available=True, unknowns present, no filesystem access) ✓
- Multi-agent plan stays bounded at 8 steps ✓
- No project/run/tool_call created ✓

---

## Document Mode Validation

**Result: PASS**

- `cq-doc-2` answer prepends must-have to `goals` ✓
- `cq-doc-5` answer updates `constraints` AND `inferred_stack` (splitting on `,/;`) ✓
- `product_summary` always bounded at 300 chars — raw document never dumped ✓
- Plan includes `business-analyst` (step-1 Document Analysis) and `product-manager` (step-2 Requirement Normalization) ✓
- Answering 4 required document questions → `confidence_after = "medium"` ✓
- No provider/LLM reasoning invoked ✓
- No file reads, no upload parsing ✓

---

## Existing Project Mode Validation

**Result: PASS**

- `cq-ep-1/2/3` answers refine `goals` (what works / what is broken / target) ✓
- `cq-ep-4` (test command) → added to `constraints`; "Test command not confirmed" risk removed ✓
- `cq-ep-5` (protected modules) → added to `constraints`; "Protected modules not identified" risk removed ✓
- `cq-ep-6` (DB/env) → added to `constraints`; "Database/env requirements not confirmed" risk removed ✓
- `project_path` used only as string for basename extraction (string split on `/`) — no filesystem access ✓
- No `os.listdir`, no `pathlib.Path`, no `open()`, no `.read_text()` in CQE section ✓
- Plan includes `orchestrator` (Repository Inventory, step-1) and `qa-expert` (Test Discovery, step-4) ✓
- Plan steps are planning hints only — no actual patch/proposal/apply execution ✓

---

## Endpoint Read-Only Validation

**Result: PASS**

`POST /api/project-intake/clarifying-questions` (line 5332 in routes.py):
- Returns 200 for `idea`, `document`, `existing_project` ✓
- Returns 422 for invalid mode (Pydantic `UnifiedIntakeMode` enum) ✓
- Body is one line: `return build_clarifying_question_set(req)` — no DB, no project, no run ✓
- Verified in tests 26–28 + no-project/no-run patches ✓

`POST /api/project-intake/clarifying-preview` (line 5344 in routes.py):
- Returns 200 for all valid modes with answers ✓
- Body is one line: `return refine_unified_intake_with_answers(req)` ✓
- Verified in test 29 + no-tool_call patch ✓

Unchanged endpoints confirmed working:
- `/api/project-intake/unified-preview` ✓
- `/api/project-intake/analyze`, `/api/project-intake/source-of-truth` ✓
- `/api/project-intake/confirmed-run`, `/api/runs` (create-run) ✓

---

## Frontend Preview/Refinement Validation

**Result: PASS (with one P2 note)**

- Answer `<textarea>` inputs render in each `UnifiedClarifyingQuestionCard` when `onAnswerChange` prop is provided ✓
- Inputs are 2-row compact, no autofill, no upload ✓
- "Refine preview with answers" button (violet) calls only `handleRefineWithAnswers()` ✓
- `handleRefineWithAnswers()` calls only `previewClarifiedIntake()` — no `createRun`, no `createRunFromConfirmedPlan` ✓
- `previewClarifiedIntake()` sends to `/api/project-intake/clarifying-preview` only ✓
- `ClarifiedIntakePreviewPanel` renders:
  - confidence before/after ✓
  - missing required answers (`ClarifiedAnswerGapRow`) ✓
  - applied answer summary ✓
  - Refined Source of Truth Draft (`UnifiedSoTDraft`) ✓
  - Refined Module Map Draft (`UnifiedModuleMapDraft`) ✓
  - Multi-Agent Plan (`UnifiedPlanStepCard`) ✓
  - Next Recommended Action ✓
  - Read-only disclaimer ✓
  - **Safety Notes — not rendered in `ClarifiedIntakePreviewPanel` (P2, see below)** ⚠
- Existing NewTask create flow (`handleStart`, `handleConfirmedRun`) untouched ✓
- `tsc --noEmit`: clean ✓
- `npm run build`: 48 modules, no errors ✓

---

## Safety / Static Scan Validation

**Result: PASS — all clean**

Scanned CQE section (`# ── Clarifying Questions Engine v1` to EOF, ~385 lines) and both route endpoint functions.

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

Route endpoint sections (`post_project_intake_clarifying_questions`, `post_project_intake_clarifying_preview`): clean for `execute_run` and `asyncio.create_task` ✓

All 8 static analysis tests in `TestCQESafetyAndStaticAnalysis` pass ✓

---

## Workflow Compatibility Validation

**Result: PASS — all suites at baseline**

| Suite | Result |
|-------|--------|
| `test_clarifying_questions_engine.py` | **52 passed** |
| `test_unified_autonomous_project_intake.py` | **44 passed** |
| `test_project_intake.py` | **67 passed, 7 subtests** |
| `test_source_of_truth_run_creation_wiring.py` | **29 passed** |
| `test_real_project_end_to_end_delivery_dogfood.py` | **45 passed** |
| `test_project_context_cockpit.py` | **26 passed** |
| `test_provider_integration_hardening_contract.py` | **53 passed** |
| `test_auth_rbac_deployment_security_contract.py` | **47 passed** |
| `test_migration_backup_restore_contract.py` | **41 passed** |
| Full `pytest -q` | **1464 passed, 38 subtests** |
| `npx tsc --noEmit` | **clean** |
| `npm run build` | **48 modules, no errors** |
| `npm run test:e2e:smoke` | **2 passed** |
| `scripts/run_tests.sh` | **passed** |

---

## P0 / P1 / P2 / P3 Issues Found

| Severity | Area | Issue | Action |
|----------|------|-------|--------|
| P2 | Frontend | `ClarifiedIntakePreviewPanel` does not render `result.safety_notes` or `result.limitations`. These are present in the response and displayed in the `UnifiedIntakePreviewPanel` above, but not explicitly shown in the refined panel section. | Document only — not a safety or correctness failure; safety notes are visible in the parent panel |
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

1. **Deterministic refinement only** — no LLM/provider reasoning; all SoT refinement is direct mapping of answer text to structured fields
2. **No provider/LLM reasoning** — confidence ceiling is "medium"; high-confidence SoT requires human review in a future slice
3. **No persistent intake sessions** — answers and refined preview are ephemeral; no DB storage per session
4. **No document upload or parsing** — `document_excerpt` is plain text only; no PDF/DOCX extraction
5. **No repository file scanning** — `project_path` is a string hint only; no `os.listdir`, no filesystem traversal
6. **No automatic Source of Truth persistence** — refined SoT must be manually submitted to the existing SoT pipeline
7. **No automatic Module Map persistence** — refined module map is preview-only
8. **No project or run creation** — intake screen is fully read-only end-to-end
9. **No agent assignment execution** — plan steps are recommendations, not executable tasks

---

## Recommended Next Slice

**Auto Source of Truth Draft from Intake v1**

Wire the refined, answered `ClarifyingAnswersRequest` into the existing `build_source_of_truth_from_intake()` function to produce a structured, confirmable SoT that can be persisted via the existing SoT pipeline. This would complete the idea → questions → answers → SoT loop without requiring new DB schema — the existing `source_of_truth` table already supports this.

Entry point: answered `ClarifyingAnswersRequest` → extract answers → construct `SourceOfTruthPreviewRequest` → `build_source_of_truth_from_intake()` → optional `POST /api/project-intake/source-of-truth` with user confirmation.

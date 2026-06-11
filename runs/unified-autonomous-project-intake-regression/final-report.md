# Unified Autonomous Project Intake — Regression Pass

**Run ID:** unified-autonomous-project-intake-regression  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Pass type:** Regression / stability audit  
**Status:** CLEAN — no P0/P1 issues found, no source changes needed

---

## Summary

Full regression audit of the Unified Autonomous Project Intake v1 implementation. All eight audit areas inspected. No P0 or P1 issues found. No changes were made to any source file. All required checks passed at or above baseline.

---

## Idea Mode Validation

**Result: PASS**

- `mode` field returns `"idea"` ✓
- `classification_reason` is `"Input classified as a new product idea from scratch."` — meaningful ✓
- Product-focused clarifying questions present (cq-idea-1 through cq-idea-12, capped at 12) ✓
- Source of Truth draft generated from `title` + `raw_input` using `_infer_product_name()` and `_safe_summary()` ✓
- Module Map is conceptual only — inferred from signal keywords and `known_stack`, no repo scanning ✓
- Multi-agent plan includes all required roles:
  - `product-analyst` (step-1) ✓
  - `architect` (step-2) ✓
  - `backend-developer` (step-3) ✓
  - `frontend-developer` (step-4) ✓
  - `postgres-pro` (step-5, database role) ✓
  - `qa-expert` (step-6) ✓
  - `security-auditor` (step-7, guard role) ✓
  - `technical-writer` (step-8, delivery/reviewer role) ✓
- Outputs bounded: questions ≤ 12, SoT lists ≤ 10, modules ≤ 12, plan steps ≤ 12 ✓
- No provider call, no DB write ✓

---

## Document Mode Validation

**Result: PASS**

- `mode` field returns `"document"` ✓
- `classification_reason` is `"Input classified as a requirements document or specification."` ✓
- Requirement-focused clarifying questions present (cq-doc-1 through cq-doc-12, capped at 12) ✓
- SoT draft does not dump raw document — `product_summary` uses `_safe_summary(document_excerpt or raw_input, max_chars=300)` with smart word-boundary truncation ✓
- Plan includes `"business-analyst"` (step-1 Document Analysis) and `"product-manager"` (step-2 Requirement Normalization) ✓
- Module Map remains conceptual — uses signal detection from text, no file reads ✓
- Outputs bounded ✓
- No provider call, no file read, no DB write ✓

---

## Existing Project Mode Validation

**Result: PASS**

- `mode` field returns `"existing_project"` ✓
- `project_path` used only as string hint — basename extracted via `str.replace("\\", "/").rstrip("/").split("/")[-1]` — no filesystem access ✓
- No `os.listdir`, no `pathlib.Path`, no `open()`, no `.read_text()` in the unified section ✓
- `known_stack` used when provided to populate module map ✓
- Clarifying questions include all required topics:
  - What currently works? (cq-ep-1) ✓
  - What is broken? (cq-ep-2) ✓
  - Target release goal? (cq-ep-3) ✓
  - Test command? (cq-ep-4) ✓
  - Protected modules? (cq-ep-5) ✓
  - DB/env/local services? (cq-ep-6) ✓
- Multi-agent plan includes:
  - Repository Inventory (`orchestrator`, step-1) ✓
  - SoT Confirmation (`product-manager`, step-2) ✓
  - Module Map Drafting (`architect`, step-3) ✓
  - Test Discovery (`qa-expert`, step-4) ✓
  - First Safe Patch Candidate (`backend-developer`, step-5) ✓
  - Delivery Report (`technical-writer`, step-6) ✓
- No provider call, no DB write ✓

---

## Endpoint Read-Only Validation

**Result: PASS**

`POST /api/project-intake/unified-preview` inspected at `backend/src/api/routes.py:5302`

- Returns 200 for `idea`, `document`, `existing_project` ✓
- Returns 422 for invalid mode (Pydantic `UnifiedIntakeMode` enum validation) ✓
- Creates no project — `create_project` never called ✓
- Creates no run — `create_run` never called ✓
- Creates no tool_calls — `create_tool_call` never called ✓
- Calls no providers ✓
- Reads no files ✓
- Executes no commands ✓
- Deterministic for same input (pure function, no randomness) ✓
- Existing endpoints (`/api/project-intake/analyze`, `/api/project-intake/source-of-truth`, `/api/runs/confirmed`) unaltered ✓

---

## Frontend NewTask Validation

**Result: PASS**

- Mode selector buttons present for Idea / Document / Existing Project ✓
- Main textarea (`prompt`) used as primary input ✓
- Project path input shown conditionally for `existing_project` mode ✓
- Known stack comma-separated input present ✓
- "Preview autonomous intake" button → `handleUnifiedPreview()` only → calls `previewUnifiedIntake()` only ✓
- No hidden `createRun` in the preview path ✓
- No hidden `createRunFromConfirmedPlan` in the preview path ✓
- Existing start-task flow (`createRun` at line 252) is a completely separate handler, unchanged ✓
- All required preview sections render:
  - Classification (mode + classification_reason) ✓
  - Clarifying Questions ✓
  - Source of Truth Draft ✓
  - Module Map Draft ✓
  - Multi-Agent Plan ✓
  - Next Recommended Action ✓
  - Safety Notes ✓
  - Limitations (in grid next to Safety Notes) ✓
- `tsc --noEmit`: clean ✓
- `npm run build`: 48 modules, no errors ✓

---

## Safety / Static Scan Validation

**Result: PASS — all clean**

Scanned unified intake section (`# ── Unified Autonomous Project Intake v1` to EOF, ~720 lines) and the `build_unified_autonomous_intake_preview` function source.

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
| `open(` | Not found ✓ |
| `.read_text(` | Not found ✓ |
| `pathlib.Path` | Not found ✓ |
| `os.listdir` | Not found ✓ |
| `.scandir(` | Not found ✓ |
| `save_project` | Not found ✓ |
| `save_run` | Not found ✓ |
| `save_tool_call` | Not found ✓ |
| `db.execute` | Not found ✓ |
| `create_tool_call` | Not found ✓ |

`"provider"` appears only in comments and docstrings (e.g., `"No provider or LLM calls are made."`). These are string literals in `_UNIFIED_SAFETY_NOTES` and `_UNIFIED_LIMITATIONS` — not executable imports or calls. The static scan tests check for `call_provider`, `ollama_client`, and `anthropic.Anthropic` specifically, and none are present.

Routes endpoint section (`post_project_intake_unified_preview`): clean for `execute_run` and `asyncio.create_task` ✓

---

## Workflow Compatibility Validation

**Result: PASS — all suites at or above baseline**

| Suite | Result |
|-------|--------|
| `test_unified_autonomous_project_intake.py` | **44 passed** |
| `test_project_intake.py` | **67 passed, 7 subtests** |
| `test_source_of_truth_run_creation_wiring.py` | **29 passed** |
| `test_real_project_end_to_end_delivery_dogfood.py` | **45 passed** |
| `test_project_context_cockpit.py` | **26 passed** |
| `test_provider_integration_hardening_contract.py` | **53 passed** |
| `test_auth_rbac_deployment_security_contract.py` | **47 passed** |
| `test_migration_backup_restore_contract.py` | **41 passed** |
| Full backend `pytest -q` | **1412 passed, 38 subtests** |
| `npx tsc --noEmit` | **clean** |
| `npm run build` | **48 modules, no errors** |
| `npm run test:e2e:smoke` | **2 passed** |
| `scripts/run_tests.sh` | **passed** |

---

## P0 / P1 / P2 / P3 Issues Found

| Severity | Issue | Resolution |
|----------|-------|------------|
| — | None found | — |

**No issues found. No source changes were required.**

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

1. **Deterministic preview only** — no LLM/provider reasoning; all output is keyword-matched from input text.
2. **No document parsing or upload extraction** — `document_excerpt` is treated as plain text; no PDF/DOCX parsing.
3. **No repository file scanning** — `existing_project` mode uses `project_path` as a string hint only; no `os.listdir`, no pathlib traversal.
4. **No automatic project or run creation** — preview screen does not advance to run execution.
5. **No agent assignment execution** — agent roles in the plan are recommendations only.
6. **No patch or test loop from intake screen** — implementation starts only after the full intake pipeline (analyze → SoT → confirmed plan → run).
7. **Stack inference accuracy** — inferred stack depends on keyword matches; novel frameworks or domain-specific terms will not be detected.

---

## Recommended Next Slice

**Option A — Clarifying Questions Engine v1**  
Accept user answers to the generated clarifying questions and produce a refined, confirmable SoT draft. Completes the intake loop without requiring any new DB schema or agent execution.

**Option B — Auto Source of Truth Draft from Intake v1**  
Persist a confirmed SoT draft from answered intake questions into the existing SoT storage, using the confirmed intake data as the structured input to `build_source_of_truth_from_intake`.

Both options are additive, safe, and follow existing patterns in the codebase.

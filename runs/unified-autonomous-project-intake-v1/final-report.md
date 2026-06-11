# Unified Autonomous Project Intake v1 — Final Report

**Run ID:** unified-autonomous-project-intake-v1  
**Date:** 2026-05-30  
**Branch:** fastlane/guard-result-integration-v1  
**Status:** COMPLETE ✓

---

## Summary

Implemented a deterministic, read-only unified autonomous project intake preview system for AI Workbench. The system classifies incoming project requests into one of three modes (idea, document, existing\_project), generates bounded clarifying questions, drafts a Source of Truth preview, infers a module map, and produces a multi-agent plan — all without any LLM calls, DB writes, file reads, shell commands, or side effects.

---

## Files Changed

### Backend

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | Appended unified intake models, helpers, and `build_unified_autonomous_intake_preview()` builder (~850 lines added) |
| `backend/src/api/routes.py` | Added `POST /api/project-intake/unified-preview` endpoint + import |
| `backend/tests/test_unified_autonomous_project_intake.py` | **NEW** — 44 tests across 7 classes |

### Frontend

| File | Change |
|------|--------|
| `frontend/src/types/index.ts` | Appended 8 unified intake TypeScript interfaces |
| `frontend/src/api/client.ts` | Added `previewUnifiedIntake()` client function |
| `frontend/src/pages/NewTask.tsx` | Added unified intake preview UI section with 5 display components |

---

## New API Endpoint

```
POST /api/project-intake/unified-preview
Content-Type: application/json

{
  "mode": "idea" | "document" | "existing_project",
  "title": "...",
  "raw_input": "...",
  "document_excerpt": "...",
  "project_path": "...",
  "known_stack": [...],
  "constraints": [...],
  "desired_outcome": "..."
}
```

**Response:** `UnifiedAutonomousIntakePreviewResponse` — mode classification, clarifying questions (≤12), SoT preview, module map preview, multi-agent plan (≤12 steps), safety notes, limitations.

**Pure read-only:** No DB writes, no project/run creation, no tool_calls, no provider calls, no file reads, no shell commands.

---

## New Models

Defined in `backend/src/orchestrator/project_intake.py`:

- `UnifiedIntakeMode` (enum: `idea`, `document`, `existing_project`)
- `UnifiedIntakeRequest`
- `ClarifyingQuestion`
- `DraftSourceOfTruthPreview`
- `DraftModuleMapPreview`
- `DraftAgentPlanStep`
- `UnifiedAutonomousIntakePreviewResponse`

---

## Builder Architecture

`build_unified_autonomous_intake_preview(req)` dispatches by mode to:

### idea mode (8 plan steps)
- Generates product-focused clarifying questions using existing `_detect_signals()`
- Drafts SoT with inferred product name, summary, goals, constraints, risks
- Infers module map from signal keywords and known_stack
- Multi-agent plan: product-analyst → architect → backend → frontend → QA → security → delivery → retrospective

### document mode (7 plan steps)
- Generates requirement-extraction clarifying questions from document_excerpt
- Drafts SoT from structured document signals; summary capped at 300 chars (`_safe_summary`)
- Module map from document signals + known_stack
- Multi-agent plan: product-analyst → requirements-normalizer → architect → backend → QA → security → delivery

### existing_project mode (6 plan steps)
- Asks about what works/is broken, test commands, protected modules
- Drafts SoT for controlled extension/repair work
- Module map inferred from project_path basename (string split only — no filesystem access)
- Multi-agent plan: project-auditor → architect → backend → QA → security → delivery

---

## Bounds Enforced

| Dimension | Limit |
|-----------|-------|
| Clarifying questions | ≤ 12 |
| SoT list items (goals, non-goals, etc.) | ≤ 10 each |
| Module map modules | ≤ 12 |
| Multi-agent plan steps | ≤ 12 |

---

## Check Results

### Backend — compile checks

```
py_compile src/orchestrator/project_intake.py   EXIT:0
py_compile src/models.py                        EXIT:0
py_compile src/api/routes.py                    EXIT:0
py_compile tests/test_unified_autonomous_project_intake.py  EXIT:0
```

### Backend — pytest

```
tests/test_unified_autonomous_project_intake.py   44 passed
tests/test_project_intake.py                      67 passed, 7 subtests
tests/test_source_of_truth_run_creation_wiring.py 29 passed
tests/test_real_project_end_to_end_delivery_dogfood.py  45 passed
tests/test_project_context_cockpit.py             26 passed
tests/test_provider_integration_hardening_contract.py   53 passed
tests/test_auth_rbac_deployment_security_contract.py    47 passed
tests/test_migration_backup_restore_contract.py         41 passed
Full suite:                                     1412 passed, 38 subtests passed
```

### Frontend

```
npx tsc --noEmit   ✓ (no errors)
npm run build      ✓ built in 977ms
npm run test:e2e:smoke  2 passed (1.9s)
```

### scripts/run_tests.sh

```
1412 passed, 38 subtests passed
=== Tests complete ===
```

---

## Issues Found and Fixed

| Issue | Fix |
|-------|-----|
| Test methods patched `database.save_project`, `save_run`, `save_tool_call` — names that don't exist | Updated to correct function names: `create_project`, `create_run`, `create_tool_call` |

---

## Safety Guarantees Preserved

- No `execute_run` calls anywhere in new code (verified by static analysis test)
- No `asyncio.create_task` in new code
- No `subprocess` or `os.system` calls
- No provider imports or calls
- No `open()` / file reads
- No DB write calls (`create_project`, `create_run`, `create_tool_call` not invoked)
- No patch proposals, apply patch, or auto-rollback
- No approval bypass
- Existing `database.py`, `engine.py`, `model_router.py`, `project_tools.py` untouched
- No DB schema changes or migrations
- No `git push`

---

## Known Limitations

1. Module map is inferred from keyword signals only — accuracy depends on descriptive input
2. Clarifying questions are deterministic templates, not adaptive to prior answers
3. SoT preview is a draft skeleton — final SoT requires human review and answers to questions
4. existing\_project mode does not read actual file contents (by design — read-only constraint)
5. No LLM reasoning — all outputs are pattern-matched from input text
6. Stack inference may miss frameworks not in the keyword list

---

## Recommended Next Slice

**Unified Intake v2 — Answer Processing**: Accept user answers to the generated clarifying questions and produce a refined, confirmable SoT + module map. This would complete the intake loop and feed directly into the existing `build_confirmed_plan_run_preview()` pathway without requiring any new DB schema.

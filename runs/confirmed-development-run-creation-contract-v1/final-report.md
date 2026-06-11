# Confirmed Development Run Creation Contract v1

**Date:** 2026-06-01  
**Slice type:** Contract / Spec / Test  
**Verdict: GREEN — 54 new tests pass, 1814 total backend tests pass, no regressions**

---

## Summary

This slice defines and tests the formal safety contract for converting an
`IntakeDevelopmentRunPreviewResponse` into a real confirmed development run.

The contract is a **pure Python module** with no runtime side effects — no
database, no routes, no engine, no providers, no filesystem I/O, no
subprocesses.  It answers every key question about what is allowed, what is
forbidden, what statuses must be used, and what operator confirmations are
required, before any real run creation attempt is made.

---

## Why This Slice Exists

The autonomous intake pipeline can now build:
- Unified intake → clarified intake → Source of Truth draft → Module Map draft
  → Multi-Agent Plan → Development Run Preview

The last step produces a **preview** with `preview_only=True`.  Before the
system proceeds to `POST /api/project-intake/confirmed-run`, a contract is
needed that answers whether the inputs satisfy all safety and quality
requirements.  This slice formalises that contract so that:

1. Calling code can evaluate readiness **before** making a DB-writing call.
2. Future UI can surface blockers and warnings in the confirmation dialog.
3. Tests permanently guard the decision logic against regressions.
4. The contract can be extended (new gates, new entity types) without touching
   runtime files.

---

## Creation Contract Requirements

| ID | Description | Type |
|---|---|---|
| REQ-CRC-001 | project_id must be non-empty | Blocker |
| REQ-CRC-002 | confirm must be True | Blocker |
| REQ-CRC-003 | preview_only must be False for actual creation | Blocker |
| REQ-CRC-004 | run_title must be non-empty | Blocker |
| REQ-CRC-005 | run_goal must be non-empty | Blocker |
| REQ-CRC-006 | At least one step must be present | Blocker |
| REQ-CRC-007 | development_preview_valid must be True | Blocker |
| REQ-CRC-008 | No step may have provider_allowed=True | Blocker |
| REQ-CRC-009 | No execution-like language in step title/description | Blocker |
| REQ-CRC-010 | No secret-like content in run_title or run_goal | Blocker |
| REQ-CRC-011 | Source of Truth should be valid (advisory) | Warning |
| REQ-CRC-012 | Module Map should be valid (advisory) | Warning |
| REQ-CRC-013 | Multi-Agent Plan should be valid (advisory) | Warning |

Additional step-level advisory warnings:
- `WARN-CRC-001`: No requirement_ids linked to any step
- `WARN-CRC-002`: No module_ids linked to any step
- `WARN-CRC-003`: No validation_steps defined on any step
- `WARN-CRC-004`: Steps reference risky modules (auth/database/deployment/security/migration/infra)

---

## Allowed Created Entities

During confirmed run creation **only** these entity types may be created:

| Entity | Status |
|---|---|
| `run` | `pending` |
| `run_step` | `pending` |

---

## Forbidden Created Entities

These entities must **NOT** be created during confirmed run creation:

| Entity | Reason |
|---|---|
| `project` | Projects are pre-existing; creation is a separate flow |
| `tool_call` | Only permitted after operator approval during live execution |
| `provider_call` | Only permitted after operator starts a step |
| `patch_proposal` | Requires Source of Truth guard check, separate action |
| `command_execution` | Requires explicit operator instruction |

---

## Required Statuses

| Key | Value |
|---|---|
| `run` | `pending` |
| `run_step` | `pending` |
| `provider_allowed` | `false` |
| `execution` | `not_started` |
| `run_mode` | `offline` |

---

## Safety Gates

| ID | Title | Before Creation | Before Execution |
|---|---|---|---|
| GATE-CRC-001 | No auto-start | ✅ | ✅ |
| GATE-CRC-002 | No provider calls | ✅ | ✅ |
| GATE-CRC-003 | No tool_call creation | ✅ | ✅ |
| GATE-CRC-004 | No patch/apply/test execution | ✅ | ✅ |
| GATE-CRC-005 | Manual approval required before risky step execution | — | ✅ |
| GATE-CRC-006 | Guard check required before patch proposals | — | ✅ |

---

## Required Operator Confirmations

1. Confirm explicit real-run creation (`confirm=True` required; no implicit creation).
2. Confirm Source of Truth is reviewed and ready for this development context.
3. Confirm Module Map is reviewed and ready for this development context.
4. Confirm all provider calls remain disabled (`provider_allowed=False` on all steps).
5. Confirm that apply, test, and run commands require a later explicit operator action.
6. Confirm backup or restore expectations if the attached project has sensitive data.

---

## Decision Logic

| Condition | Decision | `can_create_pending_run` | Risk |
|---|---|---|---|
| Any hard requirement unsatisfied | `BLOCKED` | `False` | `CRITICAL` |
| All hard requirements met, warnings exist | `WARNING` | `True` | `MEDIUM` |
| All requirements met, no warnings | `ALLOWED` | `True` | `LOW` |

---

## Tests Added

**54 tests** in `tests/test_confirmed_development_run_creation_contract.py`:

| Group | Tests | Coverage |
|---|---|---|
| Contract requirements | 9 | All 10 hard blockers + allow case |
| Safety/entity boundaries | 7 | Entity lists, statuses, provider, execution lang, secrets |
| Upstream draft warnings | 7 | SoT/ModuleMap/Plan, requirement/module/validation/risky |
| Safety gates | 6 | All 6 gates verified present |
| Operator confirmations | 5 | All 6 confirmations verified present |
| Redaction | 3 | Secret removal, structure preservation, title blocker |
| Determinism/bounds | 5 | Same result, all lists bounded |
| Static purity | 8 | No forbidden imports/calls in contract source |
| Compatibility | 4 | Upstream builders still importable |

---

## Files Changed

| File | Action | Touches runtime? |
|---|---|---|
| `backend/src/release/confirmed_development_run_creation_contract.py` | Created | No |
| `backend/tests/test_confirmed_development_run_creation_contract.py` | Created | No |
| `runs/confirmed-development-run-creation-contract-v1/final-report.md` | Created | No |

---

## Unchanged Files (explicitly verified)

| File | Status |
|---|---|
| `backend/src/storage/database.py` | NOT TOUCHED ✅ |
| `backend/src/orchestrator/engine.py` | NOT TOUCHED ✅ |
| `backend/src/project_tools.py` | NOT TOUCHED ✅ |
| `backend/src/model_router.py` | NOT TOUCHED ✅ |
| `backend/src/providers/*` | NOT TOUCHED ✅ |
| `backend/src/api/routes.py` | NOT TOUCHED ✅ |
| `frontend/` | NOT TOUCHED ✅ |
| `scripts/run_tests.sh` | NOT TOUCHED ✅ |

---

## Check Results

| Check | Result |
|---|---|
| `py_compile` contract module | ✅ Clean |
| `py_compile` test file | ✅ Clean |
| `py_compile` project_intake.py | ✅ Clean |
| `py_compile` models.py | ✅ Clean |
| `py_compile` routes.py | ✅ Clean |
| `pytest test_confirmed_development_run_creation_contract.py` | **54/54 passed** ✅ |
| `pytest test_intake_confirmed_development_run_preview.py` | 61/61 passed ✅ |
| `pytest test_multi_agent_plan_from_intake.py` | 58/58 passed ✅ |
| `pytest test_auto_module_map_draft_from_intake.py` | 63/63 passed ✅ |
| `pytest test_auto_source_of_truth_draft_from_intake.py` | 114/114 passed ✅ |
| `pytest test_clarifying_questions_engine.py` | 52/52 passed ✅ |
| `pytest test_unified_autonomous_project_intake.py` | 44/44 passed ✅ |
| Full `pytest -q` | **1814 passed, 38 subtests** ✅ |
| `npx tsc --noEmit` | ✅ Clean |
| `npm run build` | ✅ Clean (pre-existing chunk size warning only) |
| E2E Playwright smoke | **2/2 passed** ✅ |
| `bash scripts/run_tests.sh` | ✅ Clean |

---

## P0/P1/P2/P3 Issues

**P0: 0**  
**P1: 0**  
**P2: 0** — `test_46` initially used `"subprocess" not in source` and
false-fired on the module docstring word "subprocesses". Fixed in the
test by checking `import subprocess` and `subprocess.` instead.  No
change to the contract module itself.  
**P3: 0**

---

## Known Limitations

- **Contract only.** No runtime run creation endpoint is added or changed in
  this slice.  The contract is called by client code before it POSTs to
  `/api/project-intake/confirmed-run`.
- No frontend wiring added.  The contract is a backend-only Python module.
- No real persistence.  The evaluator is a pure function.
- No project/run/run_step creation in this slice.
- No agent execution, no provider/LLM reasoning, no automatic development loop.
- `ConfirmedRunCreationMode` enum is defined but not yet wired to endpoint
  routing — reserved for future mode-based routing.

---

## Recommended Next Slice

**Option A (recommended): Confirmed Development Run Creation Contract Regression Pass**  
Read-only stability audit of this slice.  Baseline: 54 new + 1814 total
backend tests passing.  Expected: CLEAN.

**Option B: Confirmed Development Run Creation Preview Wiring v1**  
Wire the contract evaluator into the frontend "Confirm and Create Run" flow:
- Add `evaluateCreationContract` API call in `client.ts`
- Surface blockers/warnings in a confirmation dialog in `NewTask.tsx`
- Disable the "Create Run" button when `can_create_pending_run=False`
- No new endpoint changes; contract module is already the source of truth.

# Confirmed Development Run Creation Contract — Regression Pass

**Date:** 2026-06-01  
**Run type:** Read-only stability audit  
**Verdict: CLEAN — 0 P0, 0 P1, 0 P2, 0 changes made**

---

## Baseline

| Check | Baseline | Result |
|---|---|---|
| test_confirmed_development_run_creation_contract | 54 passed | 54 passed ✅ |
| test_intake_confirmed_development_run_preview | 61 passed | 61 passed ✅ |
| test_multi_agent_plan_from_intake | 58 passed | 58 passed ✅ |
| test_auto_module_map_draft_from_intake | 63 passed | 63 passed ✅ |
| test_auto_source_of_truth_draft_from_intake | 114 passed | 114 passed ✅ |
| test_clarifying_questions_engine | 52 passed | 52 passed ✅ |
| test_unified_autonomous_project_intake | 44 passed | 44 passed ✅ |
| Full backend pytest | 1814 passed | 1814 passed ✅ |
| Frontend tsc --noEmit | clean | clean ✅ |
| npm run build | clean | clean ✅ |
| Playwright E2E smoke | 2 passed | 2 passed ✅ |
| scripts/run_tests.sh | clean | clean ✅ |

---

## Area 1 — Contract Module Purity

**File inspected:** `backend/src/release/confirmed_development_run_creation_contract.py`

**Imports present (exhaustive):**

```python
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
```

| Check | Status |
|---|---|
| No database imports | ✅ |
| No route imports | ✅ |
| No provider imports | ✅ |
| No runtime app imports (engine/project_tools/model_router) | ✅ |
| No filesystem reads/writes (`open`, `pathlib.Path`, `read_text`, `write_text`) | ✅ |
| No subprocess/shell/os command execution | ✅ |
| No network calls | ✅ |
| No `execute_run` | ✅ |
| No `asyncio.create_task` | ✅ |
| No `create_tool_call` | ✅ |
| No route registration | ✅ |
| No side effects at import time (only constants and definitions) | ✅ |
| No mutable global runtime state | ✅ |

**Result: CLEAN**

---

## Area 2 — Input Model Validation

**Model inspected:** `ConfirmedRunCreationInput` (dataclass)

| Field | Validation | Status |
|---|---|---|
| `project_id` | REQ-CRC-001: `bool(project_id and project_id.strip())` | ✅ Blocks if None or whitespace-only |
| `confirm` | REQ-CRC-002: `satisfied=inp.confirm` | ✅ Blocks if False |
| `preview_only` | REQ-CRC-003: `satisfied=not inp.preview_only` | ✅ Blocks if True |
| `run_title` | REQ-CRC-004: `bool(inp.run_title and inp.run_title.strip())` | ✅ Blocks if empty or whitespace |
| `run_goal` | REQ-CRC-005: `bool(inp.run_goal and inp.run_goal.strip())` | ✅ Blocks if empty or whitespace |
| `steps` | REQ-CRC-006: `bool(inp.steps)` | ✅ Blocks if empty list |
| `development_preview_valid` | REQ-CRC-007: `satisfied=inp.development_preview_valid` | ✅ Blocks if False |
| `source_of_truth_valid` | REQ-CRC-011: `required=False` | ✅ Warning only, never blocker |
| `module_map_valid` | REQ-CRC-012: `required=False` | ✅ Warning only, never blocker |
| `multi_agent_plan_valid` | REQ-CRC-013: `required=False` | ✅ Warning only, never blocker |
| `provider_allowed=True` in steps | REQ-CRC-008: `required=True`, `satisfied=not _steps_contain_provider_allowed(inp.steps)` | ✅ Blocks |

**Result: CLEAN** — all constraints implemented correctly. Advisory fields produce warnings, not blockers.

---

## Area 3 — Decision Behavior

| Scenario | Expected | Actual |
|---|---|---|
| Missing project_id | BLOCKED | ✅ BLOCKED |
| confirm=False | BLOCKED | ✅ BLOCKED |
| preview_only=True | BLOCKED | ✅ BLOCKED |
| Empty run_title | BLOCKED | ✅ BLOCKED |
| Empty run_goal | BLOCKED | ✅ BLOCKED |
| Empty steps | BLOCKED | ✅ BLOCKED |
| development_preview_valid=False | BLOCKED | ✅ BLOCKED |
| Valid fully-satisfied input | ALLOWED/WARNING | ✅ ALLOWED |
| Valid input + invalid SoT | WARNING | ✅ WARNING |
| Decisions bounded to enum values | ✅ | `ConfirmedRunCreationDecision.{BLOCKED,WARNING,ALLOWED}` |
| Deterministic for same input | ✅ | Pure function, no state |

Decision logic in `evaluate_confirmed_run_creation_contract`:
- BLOCKED: any hard requirement unsatisfied → `can_create_pending_run=False`, `risk=CRITICAL`
- WARNING: all hard requirements met, advisory issues → `can_create_pending_run=True`, `risk=MEDIUM`
- ALLOWED: all requirements met, no advisories → `can_create_pending_run=True`, `risk=LOW`

**Result: CLEAN**

---

## Area 4 — Entity Boundary Behavior

**`build_allowed_created_entities()` returns:**
- `ConfirmedRunCreatedEntity.RUN`
- `ConfirmedRunCreatedEntity.RUN_STEP`
- Length: exactly 2

**`build_forbidden_created_entities()` returns:**
- `ConfirmedRunCreatedEntity.PROJECT`
- `ConfirmedRunCreatedEntity.TOOL_CALL`
- `ConfirmedRunCreatedEntity.PROVIDER_CALL`
- `ConfirmedRunCreatedEntity.PATCH_PROPOSAL`
- `ConfirmedRunCreatedEntity.COMMAND_EXECUTION`
- Length: exactly 5

| Entity | Allowed | Forbidden |
|---|---|---|
| `run` | ✅ | — |
| `run_step` | ✅ | — |
| `project` | — | ✅ |
| `tool_call` | — | ✅ |
| `provider_call` | — | ✅ |
| `patch_proposal` | — | ✅ |
| `command_execution` | — | ✅ |

The contract never permits `tool_call`, `provider_call`, `patch_proposal`, or `command_execution` creation. These are hardcoded in the forbidden list and are never in the allowed list. No conditional logic can add them.

**Result: CLEAN**

---

## Area 5 — Required Statuses

**`build_required_confirmed_run_statuses()` returns:**

```python
{
    "run": "pending",
    "run_step": "pending",
    "provider_allowed": "false",
    "execution": "not_started",
    "run_mode": "offline",
}
```

| Key | Value | Correct |
|---|---|---|
| `run` | `"pending"` | ✅ Matches `RunStatus.PENDING` |
| `run_step` | `"pending"` | ✅ Matches `RunStatus.PENDING.value` used in `create_run_step` |
| `provider_allowed` | `"false"` | ✅ Documents the default |
| `execution` | `"not_started"` | ✅ No wording implies execution already started |
| `run_mode` | `"offline"` | ✅ Matches offline-first default |

**Result: CLEAN**

---

## Area 6 — Safety Gates

| Gate ID | Title | Before Creation | Before Execution |
|---|---|---|---|
| GATE-CRC-001 | No auto-start | ✅ | ✅ |
| GATE-CRC-002 | No provider calls | ✅ | ✅ |
| GATE-CRC-003 | No tool_call creation | ✅ | ✅ |
| GATE-CRC-004 | No patch, apply, or test execution | ✅ | ✅ |
| GATE-CRC-005 | Manual approval required before risky step execution | — | ✅ |
| GATE-CRC-006 | Guard check required before patch proposals | — | ✅ |

All required gate concerns are covered:
- "no execute_run" → covered by GATE-CRC-001 (auto-start prevention) + description text
- "no file reads" → covered by GATE-CRC-004 (no execution during creation)
- "later explicit operator action for commands/tests/apply" → GATE-CRC-004 description
- "backup/restore expectations" → operator checklist item 6

GATE-CRC-005 and GATE-CRC-006 are correctly marked `required_before_creation=False` — they apply at execution time, not at run creation time.

**Result: CLEAN**

---

## Area 7 — Operator Confirmations

**`build_confirmed_run_creation_operator_checklist()` returns 6 items:**

| # | Confirmation | Covers |
|---|---|---|
| 1 | "Confirm explicit real-run creation (confirm=True is required; no implicit creation)." | ✅ confirm real run creation |
| 2 | "Confirm Source of Truth is reviewed and ready for this development context." | ✅ SoT readiness |
| 3 | "Confirm Module Map is reviewed and ready for this development context." | ✅ Module Map readiness |
| 4 | "Confirm all provider calls remain disabled (provider_allowed=False on all steps)." | ✅ provider disabled |
| 5 | "Confirm that apply, test, and run commands require a later explicit operator action." | ✅ later explicit action |
| 6 | "Confirm backup or restore expectations if the attached project has sensitive or irreplaceable data." | ✅ backup/restore |

Bounded by `_MAX_OPERATOR_CONFIRMATIONS = 10`. All 6 fit. Operator-readable prose. ✅

**Result: CLEAN**

---

## Area 8 — Warning Behavior

| Warning trigger | Generated warning | Status |
|---|---|---|
| `source_of_truth_valid=False` | `[REQ-CRC-011] Source of Truth should be valid...` | ✅ |
| `module_map_valid=False` | `[REQ-CRC-012] Module Map should be valid...` | ✅ |
| `multi_agent_plan_valid=False` | `[REQ-CRC-013] Multi-Agent Plan should be valid...` | ✅ |
| No requirement_ids in any step | `[WARN-CRC-001] No requirement_ids linked...` | ✅ |
| No module_ids in any step | `[WARN-CRC-002] No module_ids linked...` | ✅ |
| No validation_steps in any step | `[WARN-CRC-003] No validation_steps defined...` | ✅ |
| Risky module keywords in steps | `[WARN-CRC-004] Steps reference risky modules...` | ✅ |

Critical verification: warnings only fire **after** all 10 hard requirements pass. The evaluator checks `req.required and not req.satisfied` first (→ blocker), then `not req.required and not req.satisfied` (→ warning). A warning result still sets `can_create_pending_run=True` but the WARNING decision signals caution.

Warnings cannot permit unsafe behavior: `provider_allowed=True`, `execute_run`, tool calls, patch application, and project creation all remain blocked regardless of warning state.

**Result: CLEAN**

---

## Area 9 — Redaction Behavior

**`redact_confirmed_run_creation_preview_for_report(payload)` analysis:**

- Recursively walks dict/list/str structure
- String values matching `_CONTRACT_SENSITIVE_VALUE_RE` or `_CONTRACT_DATABASE_URL_WITH_CREDS_RE` are replaced with `"[REDACTED]"`
- Keys are never redacted
- Non-string values (int, bool, None) are passed through unchanged
- Returns a **new** dict — original `payload` is not mutated (Python comprehension creates new objects at each level)
- No I/O, no side effects

Verified patterns:
- `"password=supersecret_value123"` → `"[REDACTED]"` ✅
- `"token=abc123"` → `"[REDACTED]"` ✅
- `"api_key=sk-proj-supersecret_value"` → blocks via REQ-CRC-010 ✅
- `"Build SaaS task manager"` → unchanged ✅
- Numeric values preserved (e.g., `{"version": 1}`) ✅

**Result: CLEAN**

---

## Area 10 — Test Quality

**File inspected:** `backend/tests/test_confirmed_development_run_creation_contract.py`

54 tests across 9 test classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestContractRequirements` | 8 | All 10 hard blockers |
| `TestValidConfirmedInput` | 1 | Successful allow case |
| `TestSafetyAndEntityBoundaries` | 7 | Entity lists, statuses, provider flag, execution lang, secrets |
| `TestUpstreamDraftWarnings` | 7 | SoT/ModuleMap/Plan warnings, requirement/module/validation/risky |
| `TestSafetyGates` | 6 | All 6 gates verified present |
| `TestOperatorConfirmations` | 5 | All 6 confirmations verified present |
| `TestRedaction` | 3 | Secret removal, structure preservation, title blocker |
| `TestDeterminismAndBounds` | 5 | Identical results, bounded collections |
| `TestStaticPurity` | 8 | No forbidden imports/calls in contract source |
| `TestCompatibility` | 4 | Upstream builders still importable |

Quality checks:
- Tests are deterministic: pure function calls, no DB, no filesystem, no network ✅
- Tests do not touch DB: no `database` imports, no `isolated_db` fixtures ✅
- Tests do not call providers ✅
- No filesystem side effects from tests (static purity fixture reads contract source via `pathlib.Path` — this is a test read, not a contract read) ✅
- No weakening of runtime safety: all existing test suites still pass at baseline counts ✅
- `_valid_input()` helper covers all fields, making negative tests clean single-field overrides ✅
- `_steps_plain()` helper provides valid step for entity boundary tests ✅

One historical fix noted: `test_46` was updated from `"subprocess" not in source` to `"import subprocess" not in source` and `"subprocess." not in source` — this avoided a false positive from the module docstring word "subprocesses". The fix correctly strengthened specificity without weakening intent.

**Result: CLEAN**

---

## Area 11 — Runtime Compatibility

| Suite | Baseline | Result |
|---|---|---|
| test_confirmed_development_run_creation_contract | 54 | **54** ✅ |
| test_intake_confirmed_development_run_preview | 61 | **61** ✅ |
| test_multi_agent_plan_from_intake | 58 | **58** ✅ |
| test_auto_module_map_draft_from_intake | 63 | **63** ✅ |
| test_auto_source_of_truth_draft_from_intake | 114 | **114** ✅ |
| test_clarifying_questions_engine | 52 | **52** ✅ |
| test_unified_autonomous_project_intake | 44 | **44** ✅ |
| Full backend pytest | 1814 | **1814** ✅ |
| Frontend tsc --noEmit | clean | **clean** ✅ |
| npm run build | clean | **clean** ✅ |
| Playwright E2E smoke | 2 | **2** ✅ |
| scripts/run_tests.sh | clean | **clean** ✅ |

Import cycle check: the contract module imports only stdlib (`re`, `dataclasses`, `enum`, `typing`). No circular imports are possible. ✅

Runtime files unchanged: database.py, engine.py, routes.py, providers/*, project_tools.py, model_router.py, frontend all untouched. ✅

**Result: CLEAN**

---

## Area 12 — Static Safety Scan

Comprehensive scan of `confirmed_development_run_creation_contract.py`:

| Pattern | Found | Status |
|---|---|---|
| `execute_run` | Not found | ✅ |
| `asyncio.create_task` | Not found | ✅ |
| `import subprocess` | Not found | ✅ |
| `subprocess.` | Not found | ✅ |
| `os.system(` | Not found | ✅ |
| `os.popen(` | Not found | ✅ |
| `ollama` / `claude` / `codex` | Not found | ✅ |
| `create_tool_call` | Not found | ✅ |
| `create_project` | Not found | ✅ |
| `create_run(` (as function call) | Not found (only in string literals) | ✅ |
| `create_run_step` | Not found | ✅ |
| `apply_project_patch` | Not found | ✅ |
| `propose_project_patch` | Not found | ✅ |
| `open(` | Not found | ✅ |
| `.read_text(` | Not found | ✅ |
| `.read(` | Not found | ✅ |
| `.write_text(` | Not found | ✅ |
| `from src.storage` | Not found | ✅ |
| `from src.api` | Not found | ✅ |
| `from src.providers` | Not found | ✅ |
| Route registration (`@router.`) | Not found | ✅ |
| Migration/DDL (`ALTER TABLE`, `CREATE TABLE`) | Not found | ✅ |

The word "create_run" appears only inside the `next_recommended_action` string literal:
```
"Proceed to POST /api/project-intake/confirmed-run with confirm=True to create a pending run and pending steps."
```
This is documentation text, not a code call. No existing test scans raw substrings for this pattern.

**Result: CLEAN**

---

## P0/P1/P2/P3 Issues

**P0: 0**  
**P1: 0**  
**P2: 0**  
**P3: 0**

No issues found across all 12 audit areas.

---

## Changes Made

**None.** This is a read-only regression pass. No source files were modified.

---

## Files Touched

| File | Action |
|---|---|
| `runs/confirmed-development-run-creation-contract-regression/final-report.md` | Created (this report) |

---

## Unchanged Files (verified)

| File | Status |
|---|---|
| `backend/src/release/confirmed_development_run_creation_contract.py` | UNCHANGED ✅ |
| `backend/tests/test_confirmed_development_run_creation_contract.py` | UNCHANGED ✅ |
| `backend/src/storage/database.py` | NOT TOUCHED ✅ |
| `backend/src/orchestrator/engine.py` | NOT TOUCHED ✅ |
| `backend/src/api/routes.py` | NOT TOUCHED ✅ |
| `backend/src/project_tools.py` | NOT TOUCHED ✅ |
| `backend/src/model_router.py` | NOT TOUCHED ✅ |
| `backend/src/providers/*` | NOT TOUCHED ✅ |
| `frontend/` | NOT TOUCHED ✅ |
| `scripts/run_tests.sh` | NOT TOUCHED ✅ |

---

## Known Limitations (still true)

- **Contract only.** No runtime run creation implementation exists in this slice.
- No endpoint changes. The contract is a pure Python evaluator, not an HTTP endpoint.
- No real persistence. `evaluate_confirmed_run_creation_contract` is a pure function.
- No project/run/run_step creation in this contract module.
- No agent execution, no provider/LLM reasoning, no automatic development loop.
- `ConfirmedRunCreationMode` enum (preview_only, confirm_create_pending_run, unsupported) is defined but not yet wired to endpoint routing — reserved for future mode-based routing.
- The safety gates (GATE-CRC-005, GATE-CRC-006) that apply at execution time are documented and formalized here but enforced by the execution harness, not this contract.

---

## Recommended Next Slice

**Confirmed Development Run Creation Preview Wiring v1**

Wire the contract evaluator into the frontend confirmation dialog:
- Add `evaluateCreationContract` API call in `frontend/src/api/client.ts`
- Surface blockers/warnings in a pre-creation confirmation dialog in `frontend/src/pages/NewTask.tsx`
- Disable the "Create Run" button when `can_create_pending_run=False`
- Display operator checklist in the confirmation dialog
- No new backend endpoint required — the contract module is already importable

This wiring completes the autonomous intake pipeline UI from "Preview" → "Confirm" → "Create Run".

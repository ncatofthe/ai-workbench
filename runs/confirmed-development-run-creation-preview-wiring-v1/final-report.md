# Confirmed Development Run Creation Preview Wiring v1

**Date:** 2026-06-01  
**Slice type:** Preview wiring / UI surface  
**Verdict: GREEN — 43 new tests pass, 1857 total backend tests pass, tsc/build clean, E2E 2/2**

---

## Summary

This slice wires the Confirmed Development Run Creation Contract into the
intake preview pipeline so the operator can evaluate the contract decision
**before** any future real run creation attempt.

A new read-only backend endpoint converts a Development Run Preview payload
into a `ConfirmedRunCreationContractResult` and returns the full decision,
blockers, warnings, entity lists, required statuses, safety gates, and
operator confirmations.  A compact panel in `NewTask.tsx` renders the result
after the Development Run Preview panel, with explicit "contract preview only"
labelling throughout.

**No run, step, project, tool_call, provider call, patch, or command is created
by any code path in this slice.**

---

## Why This Slice Exists

The autonomous intake pipeline can now produce a `Development Run Preview`
(`POST /api/project-intake/development-run-preview`).  Before the operator
proceeds to the existing `POST /api/project-intake/confirmed-run` endpoint,
they need to see:

- Whether the preview satisfies all contract requirements
- What blockers exist (e.g. missing `project_id`, `confirm=False`)
- What warnings exist (e.g. SoT not validated, risky modules)
- What entities may and may not be created
- What statuses will be enforced
- What safety gates are active
- What operator confirmations are required

This slice makes that information available via a new preview endpoint and
surfaces it in the UI — without implementing actual run creation.

---

## Autonomous Intake Pipeline (updated)

```
idea / document / existing_project
→ unified intake
→ clarifying questions
→ answers
→ refined intake
→ Source of Truth draft
→ Module Map draft
→ Multi-Agent Plan
→ Development Run Preview          ← pre-existing
→ Confirmed Run Creation Contract  ← NEW: contract preview only
→ [Confirmed Run Creation Runtime] ← next slice
```

---

## Backend Endpoint

### `POST /api/project-intake/confirmed-run-creation-contract-preview`

**Request model:** `IntakeConfirmedRunCreationContractPreviewRequest`

| Field | Type | Default | Description |
|---|---|---|---|
| `development_run_preview` | `dict` | `{}` | An `IntakeDevelopmentRunPreviewResponse`-shaped payload |
| `project_id` | `str \| None` | `None` | Project identifier (required for ALLOWED decision) |
| `confirm` | `bool` | `False` | Explicit creation opt-in (required for ALLOWED) |
| `preview_only` | `bool` | `True` | Must be False for ALLOWED decision |
| `source_of_truth_valid` | `bool` | `False` | Advisory — produces warning if False |
| `module_map_valid` | `bool` | `False` | Advisory — produces warning if False |
| `multi_agent_plan_valid` | `bool` | `False` | Advisory — produces warning if False |

**Response model:** `IntakeConfirmedRunCreationContractPreviewResponse`

| Field | Description |
|---|---|
| `preview_only: True` | Hardcoded — endpoint never creates anything |
| `decision` | `"allowed"` / `"warning"` / `"blocked"` |
| `risk` | `"low"` / `"medium"` / `"high"` / `"critical"` |
| `can_create_pending_run` | `False` when BLOCKED, `True` otherwise |
| `blockers` | List of hard-requirement failures |
| `warnings` | List of advisory issues |
| `requirements` | Full requirement list with `satisfied` flags |
| `safety_gates` | All 6 mandatory safety gates |
| `allowed_created_entities` | `["run", "run_step"]` |
| `forbidden_created_entities` | `["project", "tool_call", "provider_call", "patch_proposal", "command_execution"]` |
| `required_statuses` | `{run: pending, run_step: pending, …}` |
| `required_operator_confirmations` | 6 operator acknowledgements |
| `next_recommended_action` | Human-readable next step |
| `contract_note` | Explicit "contract preview only" disclaimer |

**Behavior:**
- Returns 400 if `development_run_preview` is empty
- Deterministic (pure function, same input → same output)
- No DB reads or writes
- No project, run, or step creation
- No provider calls
- No filesystem I/O

---

## Contract Mapping Behavior

The adapter `build_confirmed_run_creation_contract_preview()` in
`project_intake.py` maps the preview dict to `ConfirmedRunCreationInput`:

| Source | Destination | Notes |
|---|---|---|
| `preview["run_title"]` | `inp.run_title` | Empty → REQ-CRC-004 blocker |
| `preview["run_goal"]` | `inp.run_goal` | Empty → REQ-CRC-005 blocker |
| `preview["recommended_run_mode"]` | `inp.recommended_run_mode` | Default: `"guided"` |
| `preview["steps"]` | `inp.steps` | Empty list → REQ-CRC-006 blocker |
| `preview["validation"]["ready_to_create_run"]` | `inp.development_preview_valid` | `False` → REQ-CRC-007 blocker |
| `req.project_id` | `inp.project_id` | `None` → REQ-CRC-001 blocker |
| `req.confirm` | `inp.confirm` | `False` → REQ-CRC-002 blocker |
| `req.preview_only` | `inp.preview_only` | `True` → REQ-CRC-003 blocker |
| Any step `provider_allowed=True` | checked by `_steps_contain_provider_allowed()` | → REQ-CRC-008 blocker |

---

## Frontend UI Changes

### `NewTask.tsx`

**New state:**
```typescript
const [contractPreviewResult, setContractPreviewResult] = useState<IntakeConfirmedRunCreationContractPreviewResponse | null>(null);
const [contractPreviewLoading, setContractPreviewLoading] = useState(false);
const [contractPreviewError, setContractPreviewError] = useState("");
```

**New handler** `handleEvaluateContractPreview()`:
- Only callable when `developmentRunPreviewResult` is set
- Calls `previewConfirmedRunCreationContract(...)` (POST to new endpoint)
- Passes `confirm: false`, `preview_only: true` — no creation implied
- Derives `source_of_truth_valid`, `module_map_valid`, `multi_agent_plan_valid`
  from current session state
- Resets `contractPreviewResult` to null on new development run preview

**New button** (orange, inside `ClarifiedIntakePreviewPanel`):
- "Evaluate confirmed run creation contract"
- Disabled while loading
- Visible only when `developmentRunPreviewResult` is present
- Labelled: "Contract preview only — no run, step, project, or provider call"

**New panel** `ConfirmedRunCreationContractPreviewPanel`:
- Decision badge (emerald/yellow/red per decision)
- Risk badge
- Can-create-pending-run indicator
- Blockers section (red)
- Warnings section (yellow)
- Entity boundaries (allowed / forbidden, side by side)
- Required statuses (key:value chips)
- Safety gates (blue, all 6)
- Operator confirmations (checkbox items)
- Next recommended action
- `contract_note` footer disclaimer

**UI wording explicitly avoids implying run creation occurred.**  
No "Create Run" button is added. No hidden creation path exists.

---

## Safety Boundaries

| Constraint | Status |
|---|---|
| No run created | ✅ Verified by test 22 |
| No project created | ✅ Verified by test 21 |
| No run_step created | ✅ Verified by test 23 |
| No tool_call created | ✅ Verified by test 24 |
| No provider calls | ✅ Verified by test 25 + static scan |
| No file reads | ✅ Verified by test 26 + static scan |
| No commands executed | ✅ Verified by test 27 |
| Endpoint deterministic | ✅ Verified by tests 25, 28 |
| `preview_only: True` hardcoded in response | ✅ Code + test 43 |
| `allowed_created_entities` = [run, run_step] only | ✅ Verified by test 8 |
| `forbidden_created_entities` has 5 types | ✅ Verified by test 9 |
| Development-run-preview endpoint unchanged | ✅ 61 tests still pass |
| Confirmed-run endpoint unchanged | ✅ 1857 total still pass |
| Start Task behavior unchanged | ✅ Not touched |

---

## Tests Added

**43 tests** in `backend/tests/test_confirmed_development_run_creation_preview_wiring.py`:

| Group | Tests | Coverage |
|---|---|---|
| Endpoint shape (1–13) | 13 | 200 responses, all response fields present, blockers for missing project_id/confirm/preview_only, valid input → allowed |
| Preview→contract mapping (14–20) | 7 | run_title/goal/steps mapped, provider_allowed blocked, risky steps warn, empty steps block, invalid preview blocks |
| Safety (21–28) | 8 | No project/run/step/tool_call created, no providers, no files, no commands, deterministic |
| Compatibility (29–31) | 3 | Contract module importable, dev run preview builder importable, multi-agent plan builder importable |
| Static analysis (32–41) | 10 | No execute_run/asyncio/subprocess/provider/file/create_tool_call/create_project/create_run/create_run_step/db_write in wiring code |
| Frontend (42–43) | 2 | Builder callable with correct signature, request/response models have all required fields |

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/orchestrator/project_intake.py` | Added `ConfirmedRunCreationRequirementPreview`, `ConfirmedRunCreationSafetyGatePreview`, `IntakeConfirmedRunCreationContractPreviewRequest`, `IntakeConfirmedRunCreationContractPreviewResponse`, `build_confirmed_run_creation_contract_preview()` |
| `backend/src/api/routes.py` | Added imports + `POST /api/project-intake/confirmed-run-creation-contract-preview` endpoint |
| `frontend/src/types/index.ts` | Added `ConfirmedRunCreationRequirementPreview`, `ConfirmedRunCreationSafetyGatePreview`, `IntakeConfirmedRunCreationContractPreviewRequest`, `IntakeConfirmedRunCreationContractPreviewResponse` |
| `frontend/src/api/client.ts` | Added imports + `previewConfirmedRunCreationContract()` |
| `frontend/src/pages/NewTask.tsx` | Added state, handler, props, button, and `ConfirmedRunCreationContractPreviewPanel` component |
| `backend/tests/test_confirmed_development_run_creation_preview_wiring.py` | Created (43 tests) |
| `runs/confirmed-development-run-creation-preview-wiring-v1/final-report.md` | Created (this report) |

---

## Unchanged Files (verified)

| File | Status |
|---|---|
| `backend/src/storage/database.py` | NOT TOUCHED ✅ |
| `backend/src/orchestrator/engine.py` | NOT TOUCHED ✅ |
| `backend/src/project_tools.py` | NOT TOUCHED ✅ |
| `backend/src/model_router.py` | NOT TOUCHED ✅ |
| `backend/src/providers/*` | NOT TOUCHED ✅ |
| `scripts/run_tests.sh` | NOT TOUCHED ✅ |

---

## Check Results

| Check | Result |
|---|---|
| `py_compile` project_intake.py | ✅ Clean |
| `py_compile` routes.py | ✅ Clean |
| `py_compile` test file | ✅ Clean |
| `pytest test_confirmed_development_run_creation_preview_wiring.py` | **43/43** ✅ |
| `pytest test_confirmed_development_run_creation_contract.py` | 54/54 ✅ |
| `pytest test_intake_confirmed_development_run_preview.py` | 61/61 ✅ |
| `pytest test_multi_agent_plan_from_intake.py` | 58/58 ✅ |
| `pytest test_auto_module_map_draft_from_intake.py` | 63/63 ✅ |
| `pytest test_auto_source_of_truth_draft_from_intake.py` | 114/114 ✅ |
| `pytest test_clarifying_questions_engine.py` | 52/52 ✅ |
| `pytest test_unified_autonomous_project_intake.py` | 44/44 ✅ |
| Full `pytest -q` | **1857 passed, 38 subtests** ✅ |
| `npx tsc --noEmit` | ✅ Clean |
| `npm run build` | ✅ Clean (pre-existing chunk size warning only) |
| Playwright E2E smoke | **2/2** ✅ |
| `bash scripts/run_tests.sh` | ✅ Clean |

---

## P0/P1/P2/P3 Issues

**P0: 0**  
**P1: 0**  
**P2: 0** — One TypeScript fix: `multiAgentPlanResult.length` → `multiAgentPlanResult.tasks.length` because `MultiAgentPlanFromIntakeResponse` is an object, not an array. Caught immediately by `tsc --noEmit`. No logic change.  
**P3: 0**

---

## Known Limitations

- **Contract preview only.** No runtime run creation is implemented. The endpoint evaluates readiness but does not act on it.
- No `project_id` lookup. The endpoint does not query the database to verify project existence — it passes the value to the contract evaluator which treats its absence as a blocker.
- No "Create Run" button in this slice. The operator can see the contract decision but cannot trigger real creation from this UI yet.
- The `confirm` and `preview_only` flags in `handleEvaluateContractPreview` are hardcoded to `false`/`true` — the contract will always show BLOCKED for the creation gate requirements. This is intentional: the UI shows what requirements must be satisfied before a real run can be created.
- No persistence of contract evaluation results.
- No agent execution, no provider/LLM reasoning, no automatic development loop.

---

## Recommended Next Slice

**Option A (recommended): Confirmed Development Run Creation Preview Wiring Regression Pass**  
Read-only stability audit of this slice. Baseline: 43 new + 1857 total.  
Expected: CLEAN.

**Option B: Confirmed Development Run Runtime Creation v1**  
Implement the actual "Create Run" action:
- A "Confirm and Create Run" button (distinct from the contract preview button)
- Calls `POST /api/project-intake/confirmed-run` with `confirm=True`
- Only enabled when `contractPreviewResult.can_create_pending_run === true`
- Displays the created `run_id` and step list
- No agent execution — creates `pending` run and `pending` steps only

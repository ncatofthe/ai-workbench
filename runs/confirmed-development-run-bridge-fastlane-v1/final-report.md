# Confirmed Development Run Bridge Fastlane v1

**Date:** 2026-06-01  
**Slice type:** Product fastlane — first real bridge from intake to pending run  
**Verdict: GREEN — 52 new tests pass, 1909 total backend tests pass, tsc/build clean, E2E 2/2**

---

## Summary

This slice creates the **first real bridge** from the autonomous intake pipeline
into a real, persisted, pending development run.  The operator can now complete
the full intake flow:

```
idea / document / existing_project
→ clarifying questions → answers
→ Source of Truth draft → Module Map draft
→ Multi-Agent Plan → Development Run Preview
→ Contract Preview
→ ✓ Confirm and Create Pending Run   ← NEW
```

and receive a real `Run` + real pending `RunStep`s, with rich context
(requirement IDs, module IDs, agent roles, safety gates, dependencies)
embedded in each step's input field for future agent work.

**No execution. No providers. No tool_calls. No auto-start.**

---

## Why This Fastlane Block Exists

Previous slices built:
- The intake pipeline (idea → SoT draft → Module Map → Multi-Agent Plan → Dev Run Preview)
- The contract evaluator (pure, no DB)
- The contract preview wiring (UI shows decision, no creation)

What was missing: an actual endpoint that converts the preview into real DB
records.  Without it, the intake pipeline produced only in-memory previews —
the operator could never actually schedule work.

This slice closes that gap.

---

## Runtime Create Endpoint

### `POST /api/project-intake/confirmed-development-run/create`

**Request model:** `ConfirmedDevelopmentRunCreateRequest`

| Field | Type | Requirement |
|---|---|---|
| `project_id` | `str` | Non-empty, must exist in DB |
| `confirm_create` | `bool` | Must be `True` |
| `contract_confirmed` | `bool` | Must be `True` |
| `source_of_truth_confirmed` | `bool` | Must be `True` |
| `module_map_confirmed` | `bool` | Must be `True` |
| `provider_disabled_confirmed` | `bool` | Must be `True` |
| `later_actions_confirmed` | `bool` | Must be `True` |
| `development_run_preview` | `dict` | Non-empty, from `/development-run-preview` |
| `contract_preview` | `dict \| None` | Optional, from contract-preview endpoint |
| `preferred_run_mode` | `str` | Default `"guided"` |

**Response model:** `ConfirmedDevelopmentRunCreateResponse`

| Field | Description |
|---|---|
| `created: bool` | `True` when run was persisted |
| `run_id: str \| None` | UUID of the created Run |
| `project_id: str` | Project the run belongs to |
| `status: str` | `"pending"` (always) |
| `run_mode: str` | `"offline"` (always) |
| `steps: list` | All created step summaries |
| `contract_decision: str` | `"allowed"` / `"warning"` / `"blocked"` |
| `blockers: list[str]` | Contract blockers (empty on success) |
| `warnings: list[str]` | Contract warnings |
| `safety_notes: list[str]` | Hardcoded safety reminders |
| `next_recommended_action: str` | Human-readable next step with run URL hint |
| `open_run_url_hint: str \| None` | `/runs/{run_id}` for frontend linking |

---

## Contract Gating Behavior

The endpoint enforces gates in sequence:

1. **HTTP 400 preflight** — any missing/false confirmation boolean → 400 before DB touch
2. **HTTP 404** — project not found → 404
3. **Contract evaluation** — `evaluate_confirmed_run_creation_contract()` runs on the preview. If `BLOCKED` → 200 `created=False` with blockers listed
4. **Provider check** — any step with `provider_allowed=True` → BLOCKED by contract (REQ-CRC-008)
5. **Secret check** — run_title/goal with secret-like content → BLOCKED (REQ-CRC-010)
6. **Empty steps** — no steps in preview → BLOCKED (REQ-CRC-006)
7. **Invalid preview** — `validation.ready_to_create_run=False` → BLOCKED (REQ-CRC-007)

Only when all gates pass does the endpoint touch the database.

---

## Confirmation Checklist Behavior

All five booleans must be `True` for the contract to accept `confirm=True`:

| Boolean | What it confirms |
|---|---|
| `confirm_create` | Creating a pending run only |
| `contract_confirmed` | Contract has been reviewed |
| `source_of_truth_confirmed` | Source of Truth readiness |
| `module_map_confirmed` | Module Map readiness |
| `provider_disabled_confirmed` | `provider_allowed=False` on all steps |
| `later_actions_confirmed` | apply/test/run require later explicit action |

Missing any one → 400 before any DB contact.

---

## Created Run Behavior

- **`create_run(prompt, mode="offline", project_id, project_path)`**  
  Status: `RunStatus.PENDING` ("pending") — hardcoded by DB helper.  
  Mode: `"offline"` — hardcoded.  
  Prompt: `"{run_title}\n\n{run_goal}"` from the preview.

- **Run does NOT auto-start.** No `execute_run`, no `asyncio.create_task`, no agent trigger.

---

## Created Step Behavior

Each step from `development_run_preview.steps` (up to 20, bounded) is persisted via `create_run_step(*)`.

Step `input` contains:
```
{description}

AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT
- source: intake_confirmed_development_run
- agent_role: {agent_role}
- requirement_ids: {REQ-001, REQ-002, ...}
- module_ids: {core-api, auth, ...}
- depends_on: {STEP-001, ...}
- safety_gates: {No auto-start; No provider call; ...}
- manual_approval_required: true/false
- provider_allowed: false
- expected_outputs: {output1; output2; ...}
- validation_steps: {step1; step2; ...}
END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT

[Manual approval required before execution]  ← only if true
```

This context block is the contract for future agent work — it records what the
step must do and what constraints apply, without triggering any execution.

**`provider_allowed` is hardcoded `False`** in `build_pending_run_step_inputs_from_development_preview` — it can never be `True` in this flow.

---

## Safety Boundaries

| Constraint | Verified |
|---|---|
| No `execute_run` called | ✅ test 25, static scan test 44 |
| No `asyncio.create_task` | ✅ test 26, static scan test 45 |
| No provider calls | ✅ test 24, static scan test 46 |
| No `create_tool_call` | ✅ test 23, static scan test 47 |
| No project creation | ✅ test 22, static scan test 48 |
| No file reads | ✅ test 27, static scan test 49 |
| No command execution | ✅ test 28, static scan test 50 |
| No patch proposal / apply | ✅ test 29, 30 |
| Run status = pending | ✅ tests 13, 25 |
| All step statuses = pending | ✅ tests 14, 30 |
| `provider_allowed=False` on all steps | ✅ tests 15, 43 |
| Run does not auto-start | ✅ tests 25, 26 |
| `database.py` not modified | ✅ Untouched |
| `engine.py` not modified | ✅ Untouched |
| Providers not modified | ✅ Untouched |

---

## Frontend UI Behavior

### `NewTask.tsx` additions:

**State (5 new checkboxes + result):**
```typescript
const [bridgeConfirmCreate, setBridgeConfirmCreate] = useState(false);
const [bridgeConfirmSoT, setBridgeConfirmSoT] = useState(false);
const [bridgeConfirmModuleMap, setBridgeConfirmModuleMap] = useState(false);
const [bridgeConfirmProvider, setBridgeConfirmProvider] = useState(false);
const [bridgeConfirmLaterActions, setBridgeConfirmLaterActions] = useState(false);
const [bridgeCreateResult, setBridgeCreateResult] = useState(null);
```

**Resets** when dev run preview is re-generated.

**`ConfirmedDevelopmentRunBridgePanel`** renders:

- If no `project_id`: yellow warning "Select or create a project first"
- If `contract_decision=blocked`: red note "Resolve all blockers before creating a run"
- Confirmation checklist (5 checkboxes)
- "Confirm and Create Pending Run" button — enabled only when:
  - all 5 checkboxes checked
  - `project_id` is set
  - `contractPreviewResult.can_create_pending_run=true`
- On success: green panel with run ID, step count, "Open Run Detail →" link, safety notes

**No hidden `createRun`, no Start Task call, no provider call, no apply/test command.**

---

## Tests Added

**52 tests** in `backend/tests/test_confirmed_development_run_bridge_fastlane.py`:

| Group | Tests | Coverage |
|---|---|---|
| Preflight / contract gating | 10 | All 6 confirmation booleans + contract blocked + provider_allowed + valid path |
| Creation behavior | 11 | Run status, step count, statuses, context embedding, req/module/agent/dep/safety |
| No forbidden actions | 9 | No project/tool_call/provider/execute_run/asyncio/files/commands/patch |
| Endpoint behavior | 8 | created=True, run_id, steps, safety_notes, determinism, empty, secret blocking |
| Compatibility | 5 | Contract module, wiring builder, dev run builder, plan builder, step input builder |
| Static / safety scan | 7 | No forbidden patterns in new endpoint code |
| Frontend stubs | 2 | Bridge request model + safety notes structure |

**2 fixes during testing:**
- `test_01`: `_post()` function had a kwarg collision on `project_id` — fixed by calling endpoint directly with modified payload dict
- `test_37`: Empty steps are BLOCKED by contract (200 `created=False`), not 400 — assertion updated to match actual behavior (contract blocks REQ-CRC-006 before steps are even attempted)

---

## Files Changed

| File | Change |
|---|---|
| `backend/src/orchestrator/project_intake.py` | Added `_BRIDGE_SAFETY_NOTES`, `ConfirmedDevelopmentRunCreateRequest`, `ConfirmedDevelopmentRunCreatedStep`, `ConfirmedDevelopmentRunCreateResponse`, `build_pending_run_step_inputs_from_development_preview()`, `build_confirmed_development_run_creation_input()` |
| `backend/src/api/routes.py` | Added imports + `POST /api/project-intake/confirmed-development-run/create` |
| `frontend/src/types/index.ts` | Added 3 interfaces for bridge request/step/response |
| `frontend/src/api/client.ts` | Added import + `createConfirmedDevelopmentRun()` |
| `frontend/src/pages/NewTask.tsx` | Added 7 state vars, bridge handler, bridge props, `ConfirmedDevelopmentRunBridgePanel` component |
| `backend/tests/test_confirmed_development_run_bridge_fastlane.py` | Created (52 tests) |
| `runs/confirmed-development-run-bridge-fastlane-v1/final-report.md` | Created (this report) |

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
| `pytest test_confirmed_development_run_bridge_fastlane.py` | **52/52** ✅ |
| `pytest test_confirmed_development_run_creation_contract.py` | 54/54 ✅ |
| `pytest test_confirmed_development_run_creation_preview_wiring.py` | 43/43 ✅ |
| `pytest test_intake_confirmed_development_run_preview.py` | 61/61 ✅ |
| `pytest test_multi_agent_plan_from_intake.py` | 58/58 ✅ |
| `pytest test_auto_module_map_draft_from_intake.py` | 63/63 ✅ |
| `pytest test_auto_source_of_truth_draft_from_intake.py` | 114/114 ✅ |
| `pytest test_clarifying_questions_engine.py` | 52/52 ✅ |
| `pytest test_unified_autonomous_project_intake.py` | 44/44 ✅ |
| `pytest test_real_project_end_to_end_delivery_dogfood.py` | 45/45 ✅ |
| `pytest test_project_context_cockpit.py` | 26/26 ✅ |
| Full `pytest -q` | **1909 passed, 38 subtests** ✅ |
| `npx tsc --noEmit` | ✅ Clean |
| `npm run build` | ✅ Clean |
| Playwright E2E smoke | **2/2** ✅ |
| `bash scripts/run_tests.sh` | ✅ Clean |

---

## P0/P1/P2/P3 Issues

**P0: 0**  
**P1: 0**  
**P2: 0** — 2 test fixes (both from incorrect test assertions, not from code bugs):
  - `test_01`: kwarg collision in `_post()` helper — fixed by calling endpoint directly
  - `test_37`: assertion expected HTTP 400 but correct behavior is 200+BLOCKED via contract

**P3: 0**

---

## Known Limitations

- **Creates pending run/steps only.** No agents started, no providers called.
- **No execution.** The run must be started manually via the existing Start Task flow.
- **No `tool_call` creation.** Tool calls are only created during live agent execution.
- **No patch proposals.** Patch proposals require an active execution step and SoT guard check.
- **No automatic development loop.** The loop (implement → test → fix → repeat) is not started.
- **No existing-project repo scanning.** Step context is based only on intake preview data.
- **Agent ID is a slug.** `agent_id` in the step is derived from `agent_role.lower()` — it is not resolved against the Agent Registry. Full registry resolution is a future enhancement.
- **Project path is stored but not used.** The run stores `project.path` but no files are scanned.

---

## Recommended Next Slice

**Option A (recommended): Confirmed Development Run Bridge Combined Regression Pass**  
Read-only stability audit of the full bridge: 52 new + 1909 total backend + tsc/build + E2E.  
Expected: CLEAN.

**Option B: Existing Project Read-only Repo Intake Fastlane v1**  
For projects with an attached path, scan the actual repo (read-only: file list, stack detection,
README excerpt) and enrich the intake pipeline with real project context before run creation.
This would make the step inputs more accurate and agent-ready.

**Option C: Run Detail Bridge Integration**  
Add a "View Run" button to the created run result panel, and surface the
`AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT` context block in the Run Detail step view for
operator inspection before starting the first step.

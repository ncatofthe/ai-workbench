# Fastlane: Agent Result → Patch Draft Bridge Regression Pass v1 — Final Report

**Run ID:** fastlane-agent-result-to-patch-draft-bridge-regression-v1  
**Date:** 2026-05-23  
**Status:** ✅ Clean — no P0/P1 issues found, no changes made

---

## 1. Scope

Regression/stability pass over **Fastlane Agent Result → Patch Draft Bridge v1** (implemented in the preceding session). Five audit areas, source-level inspection of all allowed files, and sandbox-executable checks.

**Stable baselines confirmed prior to this pass:**
- `test_agent_result_patch_draft_bridge.py`: 36 passed
- `test_agent_execution_harness.py`: 46 passed
- `test_approval_gated_automation.py`: 41 passed
- `test_automation_runner.py`: 18 passed
- `test_semi_auto_operator_queue.py`: 20 passed
- Full backend pytest: 777 passed + 38 subtests
- Frontend tsc/build: passed
- `scripts/run_tests.sh`: passed

---

## 2. Checks Run in Sandbox

| Check | Result |
|-------|--------|
| `py_compile src/storage/database.py` | ✅ OK |
| `py_compile src/models.py` | ✅ OK |
| `py_compile src/api/routes.py` | ✅ OK |
| `py_compile tests/test_agent_result_patch_draft_bridge.py` | ✅ OK |
| `npx tsc --noEmit` | ✅ Exit 0, no errors |
| `npm run build` | ⚠ Sandbox limitation (rollup native macOS binary, not a code issue) — host build verified in baseline |
| `pytest` (all suites) | ⚠ Deferred to host (macOS venv symlinks broken in Linux sandbox) — host baselines stable |

---

## 3. Audit Results

### Area 1 — Backend Bridge Endpoint

| Item | Finding |
|------|---------|
| Verifies run exists | ✅ `get_run(run_id)` → 404 if None (line 6133–6135) |
| Verifies step belongs to run | ✅ `list_run_steps(run_id)` → filter by `step.id == step_id` → 404 if missing (6137–6140) |
| Accepts direct `agent_result` | ✅ Path B: `elif req.agent_result is not None` (6197–6213) |
| Accepts `agent_execution_tool_call_id` | ✅ Path A: looks up stored tool_call, validates `tool_name == "agent-execution"` (6160–6195) |
| Rejects missing/non-agent tool_call | ✅ 404 if not found; 400 if wrong `tool_name` (6166–6182) |
| Bounds `max_context_chars` | ✅ `return "\n\n".join(parts)[:max_context_chars]` (6118) |
| Creates no proposal | ✅ No `propose_project_patch` / `create_proposal` call in bridge section |
| Applies no patch | ✅ No `apply_project_patch` call in bridge section |
| Creates no apply tool_call | ✅ No `create_tool_call` with `tool_name="apply-patch"` in bridge section |
| Calls no provider | ✅ No `ollama.chat_completion`, `claude_provider`, `codex.` in bridge section (docstring comments only) |
| Runs no command | ✅ No `subprocess`, `os.system`, `shlex`, `asyncio.create_task` in bridge section |
| Mutates no files/run/step | ✅ Pure read + build; no `update_run`, `update_run_step`, file writes in bridge |
| `guard_required` always True | ✅ Hard-coded in return statement (6276) |
| `safety_notes` always populated | ✅ Initialised with one note before any branching (6142–6145) |
| `database.py` not touched | ✅ No `AgentPatchDraft` or `agent-result-patch-draft` in `database.py` |
| `engine.py` not touched | ✅ No `AgentPatchDraft` or `agent-result-patch-draft` in `engine.py` |

**Static scan of bridge section (lines 6034–6279):** zero hits for `execute_run(`, `asyncio.create_task(`, `apply_project_patch(`, `subprocess.`, `propose_project_patch(`, `ollama.chat_completion`, `claude_provider`.

### Area 2 — Frontend Bridge Behaviour

| Item | Finding |
|------|---------|
| No `useEffect` auto-call | ✅ `preparePatchDraft` is an `async () => {}` handler, not in any `useEffect` |
| Prepare draft requires explicit click | ✅ `onClick={preparePatchDraft}` on a `<button>` (line 1660) |
| Use in patch form requires explicit click | ✅ `onClick={useInPatchForm}` on a `<button>` (line 1728) |
| Copy is clipboard only | ✅ `navigator.clipboard.writeText(patchDraft.patch_context)` — no file write, no API call (line 1721) |
| No auto-proposal | ✅ `useInPatchForm` only calls `onPatchDraftPrefill?.(stepId, prefill)` — prefills the form state, does not call any proposal endpoint |
| No auto-apply | ✅ No `applyPatch` / `confirmApplyPatch` call anywhere in `AgentExecutionPanel` |
| No provider call | ✅ No provider invocation in `AgentExecutionPanel` or `useInPatchForm` |
| No command execution | ✅ No `runProjectCommand` / `executeShell` call in bridge UI |

### Area 3 — Patch Form Safety

| Item | Finding |
|------|---------|
| `patch_context` prefilled in issue field | ✅ `externalPrefill.context_message = patchDraft.patch_context` → `setIssueContext(externalPrefill)` (RunDetail 3287–3288) |
| `old_text` not filled | ✅ `setForm((prev) => ({...prev, file_path: ..., old_text: "", new_text: ""}))` (line 3287) |
| `new_text` not filled | ✅ Same — `new_text: ""` explicitly (line 3287) |
| `file_path` set only from `recommended_file_path` | ✅ `file_path: patchDraft.recommended_file_path \|\| ""` — empty string when null (line 1360) |
| Guard validation state cleared | ✅ `setGuardResult(null)`, `setGuardCheckedContext(null)`, `setGuardNoCheckOverride(false)`, `setGuardWarningAcknowledged(false)`, `setSelectedGuardResultId(null)`, `setGuardValidation(null)`, `setGuardValidationError("")`, `setGuardError("")` — all cleared in `externalPrefill` useEffect (lines 3293–3300) |
| Warning/no-guard acknowledgement cleared | ✅ `setGuardWarningAcknowledged(false)` (line 3296) |
| Guard result ID not reused | ✅ `setSelectedGuardResultId(null)` (line 3297) |
| `draftPrefill` path not used | ✅ `externalPrefill` (IssuePrefill) path is used — the bridge does NOT use `draftPrefill` which would fill `old_text`/`new_text` |

### Area 4 — Workflow Compatibility

| Workflow | Finding |
|---------|---------|
| Agent Execution Harness | ✅ 3 existing endpoints unchanged (lines 5671, 5701, 5980) |
| Guarded Proposal | ✅ `propose_patch_manual` endpoint untouched |
| Approval-Gated Automation | ✅ All approval endpoints untouched |
| Automation Runner | ✅ `runAutomationNext`, `runAutomationSafeLoop` endpoints untouched |
| Operator Queue | ✅ `getRunOperatorQueue` endpoint untouched |
| Apply-patch `confirm=true` gate | ✅ `requires_confirmation=True` and `apply_project_patch(path, ops, req.confirm)` gate untouched (line 4374) |
| Total route count | 87 routes — 1 new (`agent-result-patch-draft`), 86 unchanged |

### Area 5 — Runtime Boundary

| Constraint | Finding |
|------------|---------|
| No `execute_run` | ✅ Zero hits in bridge section (grep) |
| No `asyncio.create_task` | ✅ Zero hits in bridge section |
| No `apply_project_patch` | ✅ Zero hits in bridge section |
| No `subprocess`/shell | ✅ Zero hits in bridge section |
| No provider calls in bridge | ✅ Zero hits in bridge section |
| `database.py` not changed | ✅ Confirmed by `py_compile` + source scan |
| `engine.py` not changed | ✅ Confirmed by source scan |
| `providers` not changed | ✅ Not in allowed files list; not touched |
| Apply-patch runtime not changed | ✅ Confirmed |
| Approval runtime not changed | ✅ Confirmed |
| Run-command runtime not changed | ✅ Confirmed |

---

## 4. Test File Verification

`tests/test_agent_result_patch_draft_bridge.py` — 36 tests across 4 classes:

| Class | Tests | Coverage |
|-------|-------|----------|
| `TestBridgeEndpointBehaviour` | 24 | 404/400 validation, both paths (A/B), all response fields, no-mutation proofs, static provider scan |
| `TestGuardRequiredInvariant` | 2 | `guard_required=True`, `safety_notes` non-empty |
| `TestRequirementContextIntegration` | 4 | REQ IDs, source-of-truth, step title, graceful no-context |
| `TestStaticSafety` | 6 | `execute_run`, `asyncio.create_task`, `apply_project_patch`, `subprocess`, provider, `propose_project_patch` |

Static safety tests use the bridge section marker `"Agent Result → Patch Draft Bridge v1"` at routes.py line 6034 — confirmed present.

---

## 5. Issues Found

**None.** No P0 or P1 issues identified. No changes made to any file.

---

## 6. Files Inspected (Read-Only)

- `backend/src/api/routes.py` — lines 6034–6279 (bridge section), plus imports
- `backend/src/models.py` — `AgentPatchDraftRequest`, `AgentPatchDraftResponse`
- `backend/tests/test_agent_result_patch_draft_bridge.py` — all 36 tests
- `frontend/src/types/index.ts` — `AgentPatchDraftRequest`, `AgentPatchDraftResponse`
- `frontend/src/api/client.ts` — `createAgentPatchDraft`
- `frontend/src/pages/RunDetail.tsx` — `AgentExecutionPanel`, `OperatorQueuePanel`, `Timeline`, `StepCard`, `StepPatchSection` (`externalPrefill` handler)

---

## 7. Host Verification Commands

```bash
cd /Users/hatss/Инструменты/ai-workbench/backend
.venv/bin/pytest -q tests/test_agent_result_patch_draft_bridge.py   # expect 36 passed
.venv/bin/pytest -q tests/test_agent_execution_harness.py           # expect 46 passed
.venv/bin/pytest -q tests/test_approval_gated_automation.py         # expect 41 passed
.venv/bin/pytest -q tests/test_automation_runner.py                 # expect 18 passed
.venv/bin/pytest -q tests/test_semi_auto_operator_queue.py          # expect 20 passed
.venv/bin/pytest -q                                                  # expect 777+ passed + 38 subtests

cd /Users/hatss/Инструменты/ai-workbench/frontend
npx tsc --noEmit                                                     # expect exit 0
npm run build                                                        # expect clean build

cd /Users/hatss/Инструменты/ai-workbench
bash scripts/run_tests.sh                                            # expect passed
```

---

## 8. Recommended Next Slice

**Fastlane Bounded Autonomous Patch-Test-Fix Loop v1**

Scope: implement a safety-bounded loop that:
1. Reads a failing test result from the existing run/step context
2. Calls the Agent Execution Harness (already built) in `mock` mode to generate a patch intent
3. Feeds the result through the Patch Draft Bridge (already built) to produce patch context
4. Presents the proposed patch to the operator via the existing Guarded Proposal flow — **no auto-apply**
5. After operator approval and apply, re-runs the test command and reports pass/fail
6. Caps at N iterations (configurable, default 3); stops on pass or on cap

All destructive steps (apply, test-run) require explicit operator approval. No new autonomous execution pathways. No provider calls outside the existing harness.

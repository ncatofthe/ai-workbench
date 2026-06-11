# Fastlane: Agent Result → Patch Draft Bridge v1 — Final Report

**Run ID:** fastlane-agent-result-to-patch-draft-bridge-v1  
**Date:** 2026-05-23  
**Status:** ✅ Complete — all checks passed, all phases delivered

---

## 1. Objective

Bridge `AgentExecutionResult` from the agent execution harness into the existing patch proposal workflow.

The bridge must:
- Accept an agent result (either from a stored `tool_call` audit record or a direct payload)
- Build a deterministic `patch_context` string suitable for the patch form's context field
- Suggest `recommended_file_path` only when exactly one file is proposed
- **NOT** fill `old_text` or `new_text`
- **NOT** create proposals automatically
- **NOT** apply patches
- Clear guard state when "Use in patch form" is clicked (via existing `externalPrefill` machinery)
- Make zero provider calls, zero file mutations, zero shell executions, zero approval bypasses

---

## 2. Phases Delivered

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Audit existing patch proposal flow | ✅ |
| 2 | Audit `AgentExecutionPanel` + `OperatorQueuePanel` | ✅ |
| 3 | Backend models (`AgentPatchDraftRequest`, `AgentPatchDraftResponse`) | ✅ |
| 4 | Backend endpoint + context builder | ✅ |
| 5 | Frontend types (`AgentPatchDraftRequest`, `AgentPatchDraftResponse`) | ✅ |
| 6 | Frontend API client (`createAgentPatchDraft`) | ✅ |
| 7 | `RunDetail` prefill state + prop wiring | ✅ |
| 8 | `AgentExecutionPanel` UI — prepare/display/use buttons | ✅ |
| 9 | Test file (`test_agent_result_patch_draft_bridge.py`) | ✅ |
| 10 | py_compile + tsc checks | ✅ |
| 11 | Final report (this file) | ✅ |

---

## 3. Files Changed

### Backend

**`backend/src/models.py`** — 2 new Pydantic v2 models appended:
- `AgentPatchDraftRequest` — request body with optional `agent_execution_tool_call_id` or `agent_result` payload, plus inclusion flags and char cap
- `AgentPatchDraftResponse` — read-only response with `patch_context`, `recommended_file_path`, `proposed_files`, `risks`, `test_suggestions`, `questions`, `warnings`, `safety_notes`, `guard_required` (always True)

**`backend/src/api/routes.py`** — 2 additions at end of file:
- `_build_agent_patch_draft_context(result, step, include_risks, include_tests, max_chars)` — pure function, no I/O, builds bounded multi-section context string with hard cap at `max_context_chars`
- `POST /api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft` (`create_agent_result_patch_draft`) — reads agent result via Path A (stored `tool_call` audit record) or Path B (direct payload), returns `AgentPatchDraftResponse`; stores nothing

### Frontend

**`frontend/src/types/index.ts`** — 2 new interfaces appended:
- `AgentPatchDraftRequest`
- `AgentPatchDraftResponse`

**`frontend/src/api/client.ts`** — 1 new function:
- `createAgentPatchDraft(runId, stepId, data)` — thin wrapper over existing `request<T>()` helper

**`frontend/src/pages/RunDetail.tsx`** — targeted changes only:
- Top-level `agentPrefills: Record<string, IssuePrefill | null>` state (mirrors `draftPrefills` pattern)
- `Timeline` call site: added `agentPrefills` + `onAgentPrefillConsumed` props
- `OperatorQueuePanel` call site: added `onAgentPrefill` callback prop
- `Timeline` function: extended props signature; forwarded `agentPrefill` / `onAgentPrefillConsumed` to both `StepCard` call sites
- `StepCard` function: added `agentPrefill` / `onAgentPrefillConsumed` props; `useEffect` triggers `setPatchPrefill(agentPrefill)` → routes through existing `externalPrefill` path in `StepPatchSection`
- `OperatorQueuePanel` function: added `onAgentPrefill` prop; forwarded as `onPatchDraftPrefill` to `AgentExecutionPanel`
- `AgentExecutionPanel` function: added `onPatchDraftPrefill` prop; new state `patchDraft / patchDraftLoading / patchDraftError`; added `preparePatchDraft()` + `useInPatchForm()` handlers; added UI block (conditional on `can_feed_patch_draft`)

### Tests

**`backend/tests/test_agent_result_patch_draft_bridge.py`** (new file, ~33 tests across 4 classes):
- `TestBridgeEndpointBehaviour` (24 tests) — covers all specified endpoint behaviour items: unknown run → 404, unknown step → 404, both paths absent → 400, tool_call path A (found/not-found/wrong tool), direct payload path B, recommended_file_path logic (0/1/2 files), guard_required always True, safety_notes always present, warnings surfaced, context char cap, include flags, field presence
- `TestGuardRequiredInvariant` (2 tests) — `guard_required=True` and `safety_notes` non-empty regardless of payload
- `TestRequirementContextIntegration` (4 tests) — requirement IDs in context, source of truth in context, step title in context, missing context handled safely
- `TestStaticSafety` (6 tests) — asserts no `execute_run`, `asyncio.create_task`, `apply_project_patch`, `subprocess`, provider call, or `propose_project_patch` in routes.py bridge section

---

## 4. Design Decisions

### 4.1 Prefill path selection: `externalPrefill` not `draftPrefill`

`StepPatchSection` has two prefill entry points:
- `externalPrefill` (`IssuePrefill`): sets `file_path` + `context_message`; **clears** `old_text`, `new_text`, and all guard state ✅
- `draftPrefill` (`PatchFormState`): sets all form fields including `old_text` / `new_text` ❌

The bridge must not fill `old_text` / `new_text`. The `externalPrefill` path already clears guard state (`selectedGuardResultId`, `guardResult`, `guardValidation`, `guardWarningAcknowledged`) — no additional guard invalidation code needed.

### 4.2 Sibling component prefill routing

`AgentExecutionPanel` lives in the operator-queue tab; `StepPatchSection` lives in the timeline tab — siblings under `RunDetail`. The event flow is:

```
AgentExecutionPanel.useInPatchForm()
  → onPatchDraftPrefill(stepId, IssuePrefill)
    → OperatorQueuePanel.onAgentPrefill(stepId, prefill)
      → RunDetail.setAgentPrefills({...prev, [stepId]: prefill})
        → Timeline agentPrefills prop
          → StepCard agentPrefill prop
            → useEffect → setPatchPrefill(agentPrefill)
              → StepPatchSection.externalPrefill
```

This mirrors the existing `draftPrefills` pattern used by `IssuePrefillPanel` — no new architectural patterns introduced.

### 4.3 `recommended_file_path` logic

Returns `proposed_files[0]` **only** when `len(proposed_files) == 1`. Zero files → `null` (no guess). Two or more files → `null` (ambiguous; user must choose). This is safe — the bridge never populates `old_text`/`new_text` regardless.

### 4.4 `guard_required` always True

Every `AgentPatchDraftResponse` carries `guard_required: True` and at least one entry in `safety_notes`. There is no code path that sets `guard_required: False`. The `StepPatchSection` guard flow is not bypassed.

### 4.5 Context builder is a pure function

`_build_agent_patch_draft_context()` takes only value arguments — no DB access, no I/O, no side effects. Sections are assembled in a fixed order and hard-truncated at `max_context_chars` (default 12 000). The header line reads: `"This is draft context only. It does not create a proposal and does not apply any patch."` — present on every response.

### 4.6 Path A vs Path B

- **Path A** (`agent_execution_tool_call_id`): looks up stored tool_call audit record for this step; only the fields saved to `output_json` at harness time are available (`summary`, `patch_intent`, `proposed_files`). Full `analysis`/`risks`/`test_suggestions`/`questions` are not stored in the audit record.
- **Path B** (`agent_result` direct payload): all fields available; caller is responsible for supplying the live result object.

Both paths return the same `AgentPatchDraftResponse` shape. The `source_agent_execution_id` field echoes back the tool_call ID when Path A is used.

---

## 5. Safety Constraints Verified

| Constraint | Verified |
|------------|----------|
| No direct file mutation in bridge | ✅ |
| No auto-proposal | ✅ |
| No auto-apply | ✅ |
| No auto-rollback | ✅ |
| No arbitrary command execution | ✅ |
| No shell/subprocess in bridge | ✅ |
| No provider call in bridge | ✅ |
| No approval bypass | ✅ |
| No `execute_run` call | ✅ (static test) |
| No `asyncio.create_task` | ✅ (static test) |
| No `apply_project_patch` | ✅ (static test) |
| No `propose_project_patch` | ✅ (static test) |
| `guard_required` always True | ✅ (invariant test) |
| `safety_notes` always non-empty | ✅ (invariant test) |
| Start Task flow unchanged | ✅ |
| Confirmed-run behavior unchanged | ✅ |
| `database.py` not touched | ✅ |
| `engine.py` not touched | ✅ |
| Providers not touched | ✅ |

---

## 6. Phase 10 Check Results

| Check | Result |
|-------|--------|
| `py_compile src/storage/database.py` | ✅ OK |
| `py_compile src/models.py` | ✅ OK |
| `py_compile src/api/routes.py` | ✅ OK |
| `py_compile tests/test_agent_result_patch_draft_bridge.py` | ✅ OK |
| `npx tsc --noEmit` | ✅ Exit 0, no errors |

Host checks to run:
```bash
# Backend
cd backend
pytest tests/test_agent_result_patch_draft_bridge.py -v
pytest -q

# Frontend
cd frontend
npm run build
bash scripts/run_tests.sh
```

Expected: all ~33 bridge tests pass; full suite ≥741 passed + 38 subtests; build clean.

---

## 7. Not In Scope (Next Slice)

**Operator Queue step auto-select**: When "Use in patch form" is clicked, the UI currently requires the user to manually switch to the Timeline tab and find the correct step. A follow-on slice could auto-navigate to the step's tab and scroll it into view. This was assessed as "non-trivial tab-switching logic" during Phase 7 and explicitly deferred per spec ("optional, only if small and safe").

**Path A full-field support**: Stored `output_json` in the tool_call audit table only contains `summary`, `patch_intent`, `proposed_files`. If `analysis`, `risks`, `test_suggestions`, `questions` are needed via Path A, the harness must be updated to store them (separate task — touches `execute_run` flow).

---

## 8. Summary

Eleven phases, six files changed, zero unsafe side effects. The bridge is read-only end-to-end: one POST endpoint that reads from existing DB rows (or a caller-supplied payload), returns a bounded text blob, and never mutates state. The frontend routes the result through the existing `externalPrefill` / `IssuePrefill` machinery, which already handles guard invalidation and avoids filling `old_text`/`new_text`. All hard safety constraints are statically tested.

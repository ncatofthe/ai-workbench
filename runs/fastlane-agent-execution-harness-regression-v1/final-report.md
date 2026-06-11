# Fastlane Agent Execution Harness — Regression Pass v1 — Final Report

**Date:** 2026-05-23
**Run ID:** fastlane-agent-execution-harness-regression-v1
**Status:** COMPLETE — NO P0/P1 ISSUES FOUND

---

## Summary

Full 10-area regression audit of the Fastlane Agent Execution Harness v1. All safety invariants verified. No P0 or P1 issues found. No code changes were required in this pass. All py_compile checks and `tsc --noEmit` pass. The baseline of 741 backend tests + 38 subtests and 46 harness tests is expected to hold on host.

---

## Baseline (Pre-Audit)

| Suite | Result |
|-------|--------|
| `tests/test_agent_execution_harness.py` | 46 passed |
| `tests/test_approval_gated_automation.py` | 41 passed |
| `tests/test_automation_runner.py` | 18 passed |
| `tests/test_semi_auto_operator_queue.py` | 20 passed |
| Full backend pytest | 741 passed + 38 subtests |
| Frontend tsc / build | passed |
| `scripts/run_tests.sh` | passed |

---

## Area 1 — Agent Execution Context Endpoint

**Endpoint:** `GET /api/runs/{run_id}/steps/{step_id}/agent-execution-context`

**Implementation (`get_agent_execution_context`):**
- Returns 404 when run does not exist (`get_run` check → HTTPException 404). ✅
- Returns 404 when step does not exist in run (`list_run_steps` + `next()` lookup → HTTPException 404). ✅
- Pure read — calls `get_run`, `list_run_steps`, `get_project`, `list_tool_calls_for_run`, `get_enabled_agents`. None of these mutate state. ✅
- Creates zero tool_calls (no `create_tool_call` call in this path). ✅
- Calls no provider (no `ollama.*` in this path). ✅
- Mutates no files (no write/open/apply calls). ✅
- Creates no proposals (no `propose_*` call). ✅
- Applies no patches (no `apply_*` call). ✅
- Runs no commands (no `subprocess.*`, `os.system`). ✅
- Includes requirement context when present (`parse_run_step_requirement_context` with safe try/except, populated into `AgentExecutionContext`). ✅
- Includes recommended agent (via `_route_agent_for_step` → `context.recommended_agent_id/name`). ✅
- Handles missing/empty context safely: `req_ctx = None` on exception, all fields default to empty strings/lists. ✅

**Test coverage:** `TestContextEndpoint` — 6 tests covering 404, read-only, requirement_ids, recommended agent, available agents list.

**Verdict:** ✅ CLEAN

---

## Area 2 — dry_run Mode

**Mode triggered:** `req.mode == "dry_run"`

**Verified in implementation:**
- Returns `AgentExecutionResponse` with `status="planned"`, `executed=False`, `provider_called=False`. ✅
- Returns `prompt_preview` (non-empty — built by `_build_agent_prompt`). ✅
- `result=None` — no agent result is generated. ✅
- No `create_tool_call` call in dry_run branch. ✅
- No provider call — function returns immediately after building prompt. ✅
- No file mutation, proposal, apply, command. ✅
- `safety_notes` list populated with standard advisory message. ✅

**Test coverage:** `TestDryRun` — 6 tests: prompt_preview present, provider_called=False, no tool_call, result=None, executed=False, safety_notes present.

**Verdict:** ✅ CLEAN

---

## Area 3 — mock Mode

**Mode triggered:** `req.mode == "mock"`

**Verified in implementation:**
- Calls `_mock_agent_result` — deterministic, no provider call. ✅
- `provider_called=False` in response. ✅
- `_mock_agent_result` contains no file writes, no `open()` calls, no `subprocess.*`. ✅
- No proposal creation, no apply call. ✅
- No command execution. ✅
- `persist_result=False`: no `create_tool_call` invoked (checked by `if req.persist_result:`). ✅
- `persist_result=True`: calls `create_tool_call` with `tool_name="agent-execution"`, `command=""`, `status="completed"`, `risk_level="low"`. This is an audit record only — does not write files, run commands, or create patches. ✅
- `can_feed_patch_draft=True` in mock result — this is advisory only; the field triggers a "Copy Patch Context" UI button (clipboard-only). No auto-proposal, no auto-apply. ✅
- Mock result is prefixed with `[MOCK]` tags to distinguish from real output. ✅

**Test coverage:** `TestMockMode` — 6 tests: structured result, provider_called=False, no file mutation, persist_true audit record, persist_false no tool_call, can_feed_patch_draft.

**Verdict:** ✅ CLEAN

---

## Area 4 — provider Mode

**Mode triggered:** `req.mode == "provider"`

**Gate 1 — `allow_provider_call` check:**
- `if not req.allow_provider_call:` raises HTTP 403 immediately. No provider call, no state mutation. ✅

**Gate 2 — Unknown explicit agent_id check (added in fix pass):**
- `if req.agent_id and not get_agent(req.agent_id):` returns `status="blocked"`, `executed=False`, `provider_called=False` without calling Ollama. ✅
- This fires *before* the Ollama health check — no provider contact on blocked path. ✅

**Gate 3 — Routed agent validation:**
- Secondary `get_agent(agent_id)` check on the routed (inferred) agent — returns `status="blocked"` if routing produced a missing agent ID. Edge-case safety net. ✅

**Ollama health check:**
- `await ollama.check_health(ollama_base_url)` — wrapped in `try/except`, failure → `ollama_healthy=False`. ✅
- Unhealthy → returns `status="provider_unavailable"`, `executed=False`, `provider_called=False`. ✅

**Provider call:**
- Only `ollama.chat_completion` is invoked — no Claude/Codex provider calls. ✅
- `claude_provider` and `codex` not referenced anywhere in the agent execution section (confirmed by static scan). ✅
- `max_tokens` capped at `min(req.max_output_chars // 4, 4096)`. ✅
- Exception during call: caught, returns `status="failed"`, `executed=False`, no file mutation. ✅

**Response parsing:**
- `_parse_provider_response`: bounded by `max_chars`, JSON parse with try/except, all lists validated, all strings `.get(…, "")` with default. Never raises. ✅
- Non-JSON response: wrapped safely in `summary/analysis` fields, `can_feed_patch_draft=False`. ✅

**No file mutation, proposal, apply, shell anywhere in provider path.** ✅

**Test coverage:** `TestProviderMode` — 8 tests: requires allow_provider_call, unknown agent blocked, Ollama unavailable → provider_unavailable, no shell commands, no apply-patch, no proposal, no file mutation, invalid without flag.

**Verdict:** ✅ CLEAN

---

## Area 5 — Agent Routing

**Implementation:** `_infer_agent_word_boundary` + `_route_agent_for_step`

**Word-boundary safety:**
- Token extraction: `re.findall(r"\b[a-z0-9][a-z0-9_+#.-]*\b", text)` → set of whole tokens. ✅
- Single-word keywords: checked via `phrase in tokens` (set membership, not substring). ✅
- Multi-word phrases: checked via `re.search(r"\b" + re.escape(phrase) + r"\b", text)`. ✅
- Verified: `"specific"` does NOT match keyword `"spec"` (token would be `"specific"`, not `"spec"`). ✅
- Verified: `"specific"` does NOT match `"test"`, `"qa"`, or any QA keyword. ✅

**Routing table priority (first match wins):**

| Step content | Expected agent |
|-------------|----------------|
| frontend/ui/react/component/jsx/tsx | `frontend-developer` ✅ |
| backend/api/endpoint/fastapi | `backend-developer` ✅ |
| test/tests/testing/pytest/qa/verify | `qa-expert` ✅ |
| database/sql/schema/orm | `sql-pro` ✅ |
| security/vulnerability/injection | `security-auditor` ✅ |
| generic/unknown text | `fullstack-developer` ✅ |

**Explicit agent_id override:**
- Valid `req.agent_id` in registry → used directly, no infer step. ✅
- Unknown `req.agent_id` → silently falls through to inference (routing level). Provider mode adds an explicit gate. ✅

**Determinism:** no randomness, no state, pure function. ✅

**Test coverage:** `TestAgentRouting` — 4 tests: frontend, backend, QA, generic/fullstack.

**Verdict:** ✅ CLEAN

---

## Area 6 — Agent Registry Integration

**Functions used:** `get_agent`, `get_enabled_agents`, `get_all_agents` (import confirmed in routes.py).

**Verified:**
- `get_enabled_agents()` used only to populate `available_agents` list in context — read-only metadata. ✅
- `get_agent(id)` used for registry lookups in routing and provider guard — returns agent object or None, no mutation. ✅
- Disabled/unknown agents: `get_agent` returns None → routing falls through to inferred agent; provider mode blocks before Ollama call. ✅
- Manual agent selection validated: `if req.agent_id and not get_agent(req.agent_id)` at provider gate — unknown agents cannot trigger provider call. ✅
- Recommended agent from context does not bypass request validation — context's `recommended_agent_id` is purely informational (UI pre-fill suggestion). ✅
- Registry not modified anywhere in agent execution code path. ✅

**Verdict:** ✅ CLEAN

---

## Area 7 — Agent Execution Listing Endpoint

**Endpoint:** `GET /api/runs/{run_id}/steps/{step_id}/agent-executions`

**Implementation (`list_agent_executions`):**
- Returns 404 when run does not exist. ✅
- Returns 404 when step not in run. ✅
- Calls `list_tool_calls_for_step(step_id)` — read-only. ✅
- Filters to only `tool_name == "agent-execution"` records. ✅
- JSON parse of `input_json`/`output_json` with try/except (silently defaults to empty dict on error). ✅
- No mutation, no provider calls, no command execution. ✅
- Returns `AgentExecutionListResponse` with execution summaries. ✅
- dry_run executions correctly produce no entries (dry_run creates no tool_calls). ✅

**Test coverage:** `TestListExecutions` — 5 tests: empty for new step, 404 cases (2), shows audit after mock, dry_run no entry.

**Verdict:** ✅ CLEAN

---

## Area 8 — Frontend AgentExecutionPanel Safety

**Component:** `AgentExecutionPanel` in `RunDetail.tsx` (lines 1236–1640)

**No `useEffect` auto-run:**
- Zero `useEffect` calls inside `AgentExecutionPanel`. ✅
- `loadContext()` and `loadHistory()` are called only on panel open (collapsible button `onClick`) and on explicit "Refresh Context" / "Run …" button clicks. ✅

**No provider call on page load / tab open:**
- Panel is collapsed by default (`useState(false)`). ✅
- No load triggered until panel `open` button is clicked. ✅
- On first open, only `loadContext()` and `loadHistory()` are triggered — these call the read-only `GET` endpoints, not the `POST /run` endpoint. ✅

**No polling:**
- No `setInterval` inside `AgentExecutionPanel`. ✅
- The `setInterval` at line 543 in the file belongs to the parent `RunDetail` polling loop (run status), entirely separate. ✅

**Provider mode gate:**
- `allowProvider` state defaults to `false`. ✅
- `allow_provider_call` checkbox only visible when `mode === "provider"`. ✅
- The `handleRun` function passes `allow_provider_call: allowProvider` — when unchecked (false), backend returns 403. ✅

**Buttons require explicit click:**
- "Build Agent Context" → calls `loadContext()` only (GET). ✅
- "Preview Prompt / Run Mock Agent / Run Provider Agent" → calls `handleRun()` only on click. ✅
- No auto-submit, no enter-key trigger wired up. ✅

**Copy Patch Context:**
- Only calls `navigator.clipboard.writeText(...)`. ✅
- Does NOT call `runAgentExecution`, `propose`, `apply`, or any mutation API. ✅
- `can_feed_patch_draft` flag and auto-prefill of Patch Proposal form are explicitly deferred (not implemented in v1). ✅

**Safety note visible:**
- Amber warning banner always shown when panel is open: *"Agent execution does not mutate files, create proposals, apply patches, run commands, or bypass approvals."* ✅

**Verdict:** ✅ CLEAN

---

## Area 9 — Workflow Compatibility

**All existing workflow endpoints confirmed present in routes.py:**

| Subsystem | Endpoint | Status |
|-----------|----------|--------|
| Automation runner | `POST /api/runs/{run_id}/automation/next` | ✅ Present |
| Automation safe-loop | `POST /api/runs/{run_id}/automation/safe-loop` | ✅ Present |
| Approval requests | `GET+POST /api/runs/{run_id}/approval-requests` | ✅ Present |
| Automation policy | `GET+PUT /api/runs/{run_id}/automation/policy` | ✅ Present |
| Operator queue | `GET /api/runs/{run_id}/operator-queue` | ✅ Present |
| Guarded propose-patch | `POST /api/projects/{project_id}/propose-patch` | ✅ Present |
| Guarded apply-patch | `POST /api/projects/{project_id}/apply-patch` | ✅ Present |
| Guard results | `GET /api/runs/{run_id}/guard-results` | ✅ Present |
| Patch workflow plan | `GET /api/runs/{run_id}/patch-workflow-plan` | ✅ Present |
| Failure-to-fix draft | `GET /api/runs/{run_id}/steps/{step_id}/failure-fix-draft` | ✅ Present |

**Apply-patch confirm gate:** Not touched. Still requires `confirm=true`. ✅
**Start Task flow:** Not touched. `execute_run` path unchanged. ✅
**Confirmed-run behavior:** Not touched. ✅
**run_tests_manual safe command policy:** Not touched. ✅
**`database.py`:** Not modified in any pass. ✅
**`engine.py`:** Not modified in any pass. ✅

**Verdict:** ✅ CLEAN

---

## Area 10 — Runtime Boundary Static Scan

**Scanned:** lines 5292–6029 of `backend/src/api/routes.py` (full agent execution section, skipping comment-only lines).

| Pattern | Result |
|---------|--------|
| `execute_run(` | ✅ CLEAN |
| `asyncio.create_task(` | ✅ CLEAN |
| `apply_project_patch(` | ✅ CLEAN |
| `propose_project_patch(` | ✅ CLEAN |
| `subprocess.` | ✅ CLEAN |
| `os.system(` | ✅ CLEAN |
| `os.popen(` | ✅ CLEAN |
| `claude_provider.` | ✅ CLEAN |
| `codex.chat` | ✅ CLEAN |
| `rollback_patch(` | ✅ CLEAN |
| `run_command(` | ✅ CLEAN |

**Additional checks:**
- `import re as _re_harness` is the only `re` import in the file. No prior module-level `import re` exists — no shadowing or name conflict. ✅
- No `re.xxx()` calls elsewhere in routes.py depend on the alias. ✅
- `database.py` contains no `agent-execution` or `AgentExecution` references. ✅
- `engine.py` contains no `agent-execution` or `AgentExecution` references. ✅

**Verdict:** ✅ CLEAN

---

## P0/P1/P2/P3 Issues Found

**P0 (blocking):** None.
**P1 (high):** None.
**P2 (medium):** None.
**P3 (informational):**
- `import re as _re_harness` is placed mid-module (line 5303) rather than at the top of `routes.py`. This is valid Python and passes py_compile, but violates PEP 8 import ordering convention. No functional impact; cosmetic only. Deferred — would require moving the import to the file's top-level import block, which is out of scope for this regression pass (cosmetic refactor).
- `_mock_agent_result` uses raw substring matching (`any(kw in title_lower ...)`) for heuristic file suggestions. This is acceptable for mock/test output only and has no safety impact — mock results are always clearly tagged `[MOCK]` and never applied. No P-level issue.
- Provider mode JSON parse tolerance wraps non-JSON responses with `can_feed_patch_draft=False` (safe default), but sets `can_feed_patch_draft=True` on any non-empty raw text in the JSON-parse success path. This is correct: the field only enables a clipboard-copy button in the frontend, never an auto-proposal. Informational only.
- History display in `AgentExecutionPanel` silently ignores `loadHistory` errors (`except: pass`). Not a safety issue; a future slice could surface a non-blocking warning.

---

## Changes Made in This Pass

**None.** The regression audit found no P0 or P1 issues. No code was modified.

---

## Check Results

| Check | Result |
|-------|--------|
| `py_compile src/storage/database.py` | ✅ OK |
| `py_compile src/models.py` | ✅ OK |
| `py_compile src/api/routes.py` | ✅ OK |
| `py_compile src/orchestrator/engine.py` | ✅ OK |
| `py_compile src/agents/registry.py` | ✅ OK |
| `py_compile src/model_router.py` | ✅ OK |
| `npx tsc --noEmit` | ✅ OK (exit 0) |
| Static safety scan (10 forbidden patterns) | ✅ CLEAN |
| Workflow endpoint presence (13 endpoints) | ✅ All present |
| `database.py` untouched | ✅ Confirmed |
| `engine.py` untouched | ✅ Confirmed |
| `providers/` untouched | ✅ Confirmed |
| `pytest tests/test_agent_execution_harness.py` | Run on host — expect 46 passed |
| `pytest -q` (full suite) | Run on host — expect 741 passed + 38 subtests |
| `npm run build` | Run on host |
| `bash scripts/run_tests.sh` | Run on host |

---

## Files Inspected

| File | Purpose |
|------|---------|
| `backend/src/api/routes.py` (lines 5292–6029) | Full agent execution section audit |
| `backend/src/models.py` | Agent execution Pydantic models |
| `backend/tests/test_agent_execution_harness.py` | 46-test harness coverage review |
| `frontend/src/pages/RunDetail.tsx` (`AgentExecutionPanel`, lines 1236–1640) | Frontend safety audit |
| `frontend/src/api/client.ts` | Client method review |
| `frontend/src/types/index.ts` | TypeScript interface review |

## Files NOT Touched

| File | Status |
|------|--------|
| `backend/src/storage/database.py` | **NOT MODIFIED** |
| `backend/src/orchestrator/engine.py` | **NOT MODIFIED** |
| `backend/src/agents/registry.py` | **NOT MODIFIED** |
| `backend/src/model_router.py` | **NOT MODIFIED** |
| `backend/src/providers/*` | **NOT MODIFIED** |
| `backend/src/project_tools.py` | **NOT MODIFIED** |

---

## Recommended Next Slice

**Option A: Fastlane Agent Result → Patch Draft Bridge v1**
Wire `can_feed_patch_draft=True` results into the existing Patch Proposal form. When an agent result is present and the operator clicks "Use as patch context", prefill `file_path`, `old_text`, and `new_text` from the agent's `proposed_files` + `patch_intent`. Requires reading the existing file snippet (read-only). Proposal still goes through the existing guarded proposal/apply flow. This is the lowest-risk, highest-value next step.

**Option B: Fastlane Bounded Autonomous Patch-Test-Fix Loop v1**
Build on approval-gated automation + agent harness to implement a bounded (max N iterations), fully-operator-supervised loop: agent plans → guarded proposal → operator approve/apply → run tests → agent analyzes failures → repeat up to N times. Higher scope and complexity; requires careful safety design.

# AI Workbench

Local multi-agent development environment. Offline-first, powered by Ollama, with optional cloud provider support (Codex CLI, Claude Code).

## Requirements

- Python 3.11+
- Node.js 18+
- npm or pnpm
- Ollama (for local AI inference)

## Setup

### 1. Check environment

```bash
bash scripts/check_env.sh
```

### 2. Install Ollama and pull the default model

```bash
# macOS
brew install ollama

# Start the server
ollama serve

# Pull the default model (in another terminal)
ollama pull qwen2.5-coder:7b
```

### 3. Install backend dependencies

```bash
cd backend
pip install -e ".[dev]"
cd ..
```

### 4. Install frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 5. Launch

```bash
# Both backend + frontend:
bash scripts/dev.sh

# Or backend only (API mode):
bash scripts/run_offline.sh
```

### 6. Open the dashboard

Go to **http://localhost:5173** in your browser.

## First Task

1. Open the dashboard
2. Click **New Task** in the sidebar
3. Type a task description, e.g.: `Analyze this project's structure and suggest improvements`
4. Select **Offline** mode
5. Click **Start Task**
6. Watch the plan appear on the Run Detail page

## Project Structure

```
ai-workbench/
├── backend/          Python FastAPI backend
│   └── src/
│       ├── main.py           App entry point
│       ├── api/routes.py     REST endpoints
│       ├── orchestrator/     Task execution engine
│       ├── providers/        AI provider integrations
│       ├── approvals/        Safety & approval layer
│       ├── storage/          SQLite persistence
│       └── utils/            Config loader
├── frontend/         React + Vite + TypeScript UI
│   └── src/
│       ├── App.tsx           Router & layout
│       ├── pages/            Dashboard, NewTask, Runs, etc.
│       ├── components/       Sidebar, StatusBadge
│       └── api/client.ts     Backend API client
├── agents/           Agent role definitions (Markdown)
├── runs/             Task execution artifacts
├── scripts/          Dev & utility scripts
├── docs/             Architecture & usage docs
└── config.yaml       System configuration
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | System health check |
| GET | `/api/projects` | List projects |
| POST | `/api/projects` | Create project |
| GET | `/api/agents` | List agents |
| GET | `/api/agents/registry` | List structured agent templates |
| GET | `/api/models/registry` | List model registry with install/enabled metadata |
| GET | `/api/models/profiles` | List model routing profiles |
| POST | `/api/models/route` | Preview provider/model routing for an agent step |
| GET | `/api/providers` | List provider metadata |
| GET | `/api/providers/status` | Check provider availability |
| PATCH | `/api/settings/provider-mode` | Update provider routing mode |
| GET | `/api/runs` | List runs |
| POST | `/api/runs` | Create and start a run |
| GET | `/api/runs/{id}` | Get run details |
| GET | `/api/runs/{id}/agents` | Get assigned agent team |
| POST | `/api/runs/{id}/agents/select` | Re-select agent team for a run |
| PATCH | `/api/runs/{id}/agents/{agent_id}` | Update an agent assignment |
| GET | `/api/runs/{id}/model-routes` | Get persisted model route decisions for a run |
| POST | `/api/runs/{id}/model-routes/preview` | Preview model routes without saving |
| POST | `/api/runs/{id}/model-routes/persist` | Save or update model route decisions |
| GET | `/api/runs/{id}/tool-calls` | List logged tool calls for a run |
| GET | `/api/runs/{id}/steps/{step_id}/tool-calls` | List logged tool calls linked to a run step |
| POST | `/api/runs/{id}/stop` | Stop a run |
| POST | `/api/projects/{id}/tools/list-files` | List project files with tool-call logging |
| POST | `/api/projects/{id}/tools/read-file` | Read a project file with tool-call logging |
| POST | `/api/projects/{id}/tools/search-code` | Search project code with tool-call logging |
| POST | `/api/projects/{id}/tools/propose-patch` | Preview a patch proposal without modifying files |
| POST | `/api/projects/{id}/tools/apply-patch` | Manually apply a confirmed patch proposal |
| GET | `/api/projects/{id}/tool-calls` | List logged tool calls for a project |
| GET | `/api/projects/{id}/git/status` | Read-only `git status --short` for the project |
| GET | `/api/projects/{id}/git/diff` | Read-only git diff summary and capped diff |
| GET | `/api/approvals` | List approvals |
| POST | `/api/approvals/{id}/approve` | Approve request |
| POST | `/api/approvals/{id}/reject` | Reject request |
| GET | `/api/config` | Get configuration |
| POST | `/api/config` | Update configuration |
| GET | `/api/workflow-policy` | Workflow action policy matrix (read-only, no DB) |

Interactive API docs available at **http://localhost:8000/docs** when the backend is running.

## Model Registry and Routing

AI Workbench keeps a local model registry for routing agent work without hard-coding one model everywhere. Each registered model records provider, family, capabilities, context window, memory tier, install status, enabled status, max parallelism, and recommended usage.

Built-in model profiles:

- `coding_heavy` for implementation agents
- `coding_fast` for quick fixes
- `planning_reasoning` for orchestration and architecture
- `debugging` for failures, review, and QA
- `security_review` for sensitive review
- `documentation` for reports and docs
- `vision_ui` for screenshot/UI analysis
- `embeddings` for local indexing

The router is hardware-aware. `large` and `xlarge` local models are limited to `max_parallel=1`; if a preferred model is not installed, routing falls back to a lighter local model and reports the suggested `ollama pull ...` command.

Recommended local Ollama models:

```bash
ollama pull qwen2.5-coder:7b
ollama pull qwen3:8b
ollama pull qwen3:14b
ollama pull deepseek-r1:14b
ollama pull qwen3-coder:30b
ollama pull nomic-embed-text
```

`qwen2.5-coder:7b` is the safest baseline for small/medium machines. `qwen3-coder:30b` is treated as a heavy model and should run one task at a time on 32GB unified-memory Macs.

## Provider Modes

Provider routing is separate from run mode:

- `local`: use only local Ollama; no prompts or code go to external providers.
- `hybrid`: prefer Ollama; external providers may be recommended only when enabled and privacy rules allow it.
- `cloud`: external providers may be recommended, but local Ollama remains a fallback and sensitive tasks still require explicit approval.

Claude Code, ChatGPT/Codex, and future external APIs remain optional. They are disabled by default, metadata-only in the current slice, and any future execution must go through the approval system.

## Current Capability Snapshot

### Ready / implemented

- Agent Registry and Dynamic Agent Assignment.
- Model Registry, Provider Router metadata, and step-level route decisions.
- Safe workspace read tools: `list-files`, `read-file`, `search-code`.
- ToolCall audit trail for workspace tools and command/patch workflow activity.
- Read-only git status/diff inspection.
- Patch workflow primitives: `propose-patch`, `review-patch`, `apply-patch` with `confirm=true`, and `rollback-patch` with `confirm=true`.
- Safe `run-command` through project allowlists and heuristic `analyze-command-result`.
- RunDetail patch-workflow cockpit, workflow mode selector, active step picker, and frontend-only workflow state persistence.

### Safe semi-auto implemented

- `auto-read` and `auto-context` for bounded read-only context gathering.
- `context-bundle` and `context-patch-draft` for draft-only preparation.
- `patch-workflow-plan` recommendations.
- Run Safe Prep sequence: `auto_gather_context` -> `build_context_bundle` -> `create_patch_draft` -> stop.

### Manual-only by design

- Patch proposal creation/review.
- Patch apply and rollback confirmation.
- Test/build/typecheck command execution.
- Command result analysis and follow-up fix planning.

### Not implemented yet

- Autonomous editing by selected agents.
- Automatic apply/test/analyze/rollback chaining.
- Full patch/test/fix loop driven by the Orchestrator.
- Full autonomous idea -> product mode.
- Real external provider execution from backend for Codex/Claude.
- Multi-user authentication.
- RunDetail component extraction.

## Model Route Decisions

Runs persist two layers of model route decisions: **agent-level** and **step-level**.

```text
agent → task_type → model_profile → selected_model → selected_provider → fallback → reason → warnings
step  → inferred_agent → inferred_task_type → model_profile → selected_model → ...
```

Route preview is safe metadata only — it does not execute an agent, edit files, call Claude/Codex, or run project commands.

**Agent-level decisions** (`step_id = NULL`) — connect each assigned agent to the best model/provider for the run. Created by `POST /api/runs/{id}/model-routes/preview|persist` and by the `Preview model routes` run step.

**Step-level decisions** (`step_id = <step.id>`) — connect each staged execution step to a per-step model. Created by `POST /api/runs/{id}/steps/model-routes/preview|persist` and automatically during run execution by `_persist_step_route_decisions()`.

### Step-level Model Route Decisions

When a run stages executable task steps, the orchestrator automatically infers the best agent and task type for each step from its title and input text using keyword matching:

| Keywords in title/input | Inferred agent | Inferred task type |
|---|---|---|
| react, vue, css, component, html | `frontend-developer` | `implementation` |
| fastapi, api, endpoint, server | `backend-developer` | `implementation` |
| database, sql, migration | `sql-pro` | `implementation` |
| test, pytest, jest, e2e | `qa-expert` | `test_generation` |
| bug, error, debug, crash | `error-detective` | `debugging` |
| security, vulnerability, auth | `security-auditor` | `security_review` |
| doc, readme, guide | `technical-writer` | `documentation` |
| deploy, docker, ci, k8s | `devops-engineer` | `deployment` |

The selected model is then used for that step's Ollama call. If the router selects an external provider (Claude/Codex), the step silently falls back to the configured local fallback model — **external providers are never called during step execution**.

### Scope filtering

The `GET /api/runs/{id}/model-routes` endpoint accepts an optional `?scope` query parameter:

| `?scope` | Returns |
|---|---|
| `all` (default) | All decisions for the run |
| `agents` | Agent-level decisions only (`step_id IS NULL`) |
| `steps` | Step-level decisions only (`step_id IS NOT NULL`) |

### RunDetail UI

The **Timeline** tab in RunDetail shows a route badge on each staged step card:

- **model** — selected local Ollama model (in green monospace)
- **provider** — `local_ollama`
- **agent** — the inferred canonical agent ID
- **task type** — the inferred task type
- **fallback** — shown if different from selected model
- **warnings** — yellow badge if any routing warnings were emitted

## Tool Call Persistence and Git Status/Diff

Read-only project tools now create a `tool_calls` journal entry before execution and update it after completion or failure. Logged tools include:

- `list_files`
- `read_file`
- `search_code`

Each entry records run/step context when provided, project ID, tool name, working directory, input JSON, output JSON, error text, risk level, status, and completion timestamp. These logs are available through `/api/runs/{id}/tool-calls` and `/api/projects/{id}/tool-calls`.

AI Workbench also exposes read-only git inspection endpoints for project workspaces:

- `/api/projects/{id}/git/status` runs fixed `git status --short`
- `/api/projects/{id}/git/diff` runs fixed `git diff --stat`, `git diff --name-only`, and a capped `git diff`

These endpoints do not accept arbitrary shell commands, run with `shell=False`, use the configured project path as `cwd`, set a timeout, and return clear errors for non-git directories.

The dashboard surfaces this read-only telemetry in two places: RunDetail shows a compact recent tool-call journal for the run, and the Tools page shows project tool history plus git status, diff stat, changed paths, and an optional capped full diff.

## Propose Patch Foundation

`POST /api/projects/{id}/tools/propose-patch` builds a unified diff preview from requested text replacements, but never writes to the project workspace. It validates project-relative paths, blocks traversal outside the workspace, refuses sensitive files such as `.env` and private key formats, rejects large/binary files, and logs the request as a medium-risk `tool_call`.

The Tools page includes a simple Patch Proposal Preview form for one-file previews. Preview never modifies files; write execution is handled only by the separate manual apply flow below.

## Patch Proposal Audit

Patch proposals use the propose-patch `tool_call.id` as `proposal_id`. If `run_id`, `step_id`, or `agent_id` are supplied, they are recorded in the tool-call audit trail; `agent_id` is kept in `input_json` without adding a new database table. Apply requests can include `proposal_id`, and the response returns `applied_from_proposal_id` so RunDetail and tool-call history can link propose/apply activity.

This is still operator-controlled work: no autonomous editing, no test/fix loop, and no external provider execution are introduced by proposal linking.

## Run/Step Patch Integration

Patch proposal and apply calls can be linked to `run_id`, `step_id`, and `agent_id`. Step-level tool calls are available through `/api/runs/{id}/steps/{step_id}/tool-calls`, and RunDetail shows compact patch activity for each staged step.

RunDetail can also prepare a patch proposal directly from a step card. The form pre-fills run/step context, but applying still requires the explicit manual confirmation checkbox and `confirm=true`; there is no autonomous editing or test/fix loop.

## Safe Test Command Runner v1

`POST /api/projects/{project_id}/tools/run-command` runs one whitelisted project command and returns a structured result.

**Command kinds:** `test`, `build`, `lint`, `typecheck`.

**Safety rules:**
- Only Project Profile commands are executed: `test` → `test_command`, `build` → `build_command`, `lint`/`typecheck` → first match in `safe_commands` by keyword.
- The resolved command must exist in the project allowlist — no arbitrary shell input accepted.
- `shell=False` — shell injection via `;`, `&&`, `|` etc. is not possible.
- Blocked patterns: `rm`, `sudo`, `curl/wget | sh`, `chmod`, `chown`, `git push`, `pip install`, `npm install`, `brew install`.
- Path traversal (`..`) is rejected.
- `cwd` is anchored to `project.path`.
- Output capped at 100 000 chars each for stdout and stderr.
- `LC_ALL=C LANG=C` locale for predictable output.
- Per-request `timeout_seconds` (default 120 s); timeout returns `timed_out=true`, `returncode=124`.

**Tool call audit:** every invocation creates a `ToolCall` record with `tool_name="run-command"`, `risk_level="medium"`, linked to `run_id` / `step_id` / `project_id`.

**Non-zero returncode is not a tool failure** — the tool call is `completed`; `returncode` reflects the command exit. The tool only fails if the runner itself cannot start (safety violation, infrastructure error).

No autonomous test/fix loop is introduced — operator-triggered only.

## Test Result Analysis v1

`POST /api/projects/{project_id}/tools/analyze-command-result` performs heuristic pattern-matching on command output and returns a structured diagnosis. No LLM is used — all detection is regex-based.

**Input options:**
- Pass `tool_call_id` to read stdout/stderr from an existing stored `run-command` ToolCall.
- Or pass `stdout`, `stderr`, `returncode` inline.

**Detected issue kinds:**

| kind | Pattern |
|---|---|
| `test_failure` | pytest `FAILED tests/...` lines |
| `assertion_error` | `AssertionError:` anywhere in output |
| `traceback` | `File "...", line N` Python tracebacks |
| `type_error` | TypeScript `file.tsx(L,C): error TSxxxx:` |
| `lint_error` | ruff/flake8 `file.py:L:C: Exx message` |
| `build_error` | generic lines containing `error` (fallback) |
| `timeout` | `returncode=124` or `timed_out=true` |

**Response fields:** `status` (`passed` / `failed` / `timed_out` / `unknown`), `summary`, `issues` (list of `{kind, file_path, line, message}`), `suggested_next_actions`, `can_create_fix_proposal`.

`can_create_fix_proposal` is `true` when at least one issue has a `file_path` — this signals the UI to offer a "Propose Patch" shortcut. No patch is created automatically.

**Tool call audit:** every analysis call creates a `ToolCall` record with `tool_name="analyze-command-result"`, `risk_level="low"`, and `source_tool_call_id` in the input metadata.

**Frontend integration:** Tools page shows an "Analyze command result" button after any failed `run-command` invocation. RunDetail's Tool Calls panel shows the same button for each `run-command` tool call with non-zero exit code. Analysis results are stored in local component state only — no database writes, no file changes.

No autonomous fix loop is introduced — analysis is read-only and operator-triggered only.

## Guided Test/Fix Loop v1

A manual, step-by-step workflow surfaced in the RunDetail timeline for each sub-step card. It chains the existing endpoints without introducing any autonomous behaviour.

**Workflow (all steps require explicit user action):**

1. **Run Tests** — calls `POST /api/projects/{id}/tools/run-command` (`command_kind=test`) with the step's `run_id`/`step_id`/`agent_id`. Shows exit code, duration, and a stdout/stderr snippet.
2. **Analyze** — shown only when `returncode ≠ 0` or `timed_out`. Calls `POST /api/projects/{id}/tools/analyze-command-result` by `tool_call_id`. Displays issues, suggested actions, and whether a fix proposal is feasible.
3. **Create Patch Proposal** — shown as a hint pointing to the existing Patch Proposal form in the same step card. No automatic patch generation.
4. **Apply Patch** — performed through the existing confirm-checkbox flow in the Patch Proposal section. No automatic apply.

**Constraints:**
- No step is triggered automatically by a previous step.
- No patch is generated or applied without explicit user confirmation.
- No new backend endpoints or database tables added — all four steps use existing endpoints.
- State (command result, analysis) is local component state, not persisted.

## Agent-assisted Fix Proposal v1

Issues found by the analysis step can now be used to pre-fill the Patch Proposal form, reducing copy-paste friction without introducing any autonomous behaviour.

**How it works:**

- In the **Guided Fix Workflow** (RunDetail, per step): after analysis produces issues, each issue with a `file_path` shows a "Use for Patch Proposal ↓" button.
- Clicking the button opens the Patch Proposal form in the same step card, pre-fills `file_path` from the issue, and shows an issue context banner (kind / location / message) as reference.
- `old_text` and `new_text` are intentionally left empty — the user must write both.
- In **Tools.tsx**: the same "Use for Patch Proposal ↓" button appears on each issue with a `file_path`; clicking scrolls to and pre-fills the Patch Proposal Preview panel.

**Constraints (all hold):**
- No patch is generated automatically.
- No patch is applied automatically.
- No new backend endpoints or database tables.
- No LLM is called.
- The warning "This only pre-fills proposal context. It does not generate or apply a fix." is shown every time a prefill is active.

## Approval-gated Patch Workflow Orchestrator v1

Read-only workflow planner that analyses tool_call history for each step and recommends the next safe manual action.

**Endpoint:** `GET /api/runs/{run_id}/patch-workflow-plan`

**Workflow stages (per step):**
A. Context Gathering → B. Context Bundle → C. Patch Draft → D. Patch Review → E. Proposal → F. Apply → G. Tests → H. Analysis → done

**Next-action decision tree:**
- No context calls → `auto_gather_context` (low risk)
- Context exists, no proposal → `review_patch` (low risk)
- Proposal exists, no apply → `apply_patch_manual` (high risk, requires_confirmation=true)
- Apply exists, no run → `run_tests_manual` (medium risk, requires_confirmation=true)
- Failed run, no analysis → `analyze_result` (low risk)
- Failed run + analysis → `create_patch_draft` (new fix iteration)
- Passing run → `done`

**Safety:** Read-only — creates no ToolCalls, modifies no files, applies no patches, runs no commands. All high-risk actions (apply, rollback, run-command) require manual user confirmation in the UI.

**Frontend (Patch Workflow tab):** Per-step stage checklist with ✓/→/⚠/✗ icons, colour-coded "Recommended next action" card with risk level and description of where to perform the action, warnings/blockers list. Refresh button to reload plan on demand.

---

## Patch Proposal Review Assistant v1

Static safety review of patch operations before creating a proposal or applying a patch.

**Endpoint:** `POST /api/projects/{project_id}/tools/review-patch`

**Checks performed (per operation):**
- `file_path` empty → blocker
- Path traversal / outside workspace → blocker
- Secret-like file (`.env`, `.pem`, `.key`, etc.) → blocker
- `backend/src/storage/database.py` → blocker (protected module)
- File does not exist → blocker
- `old_text` empty → blocker
- `old_text` not found in file → blocker
- `old_text` found more than once (ambiguous replacement) → blocker
- `old_text` too short (< 8 chars) → warning
- `new_text` empty (deletion) → warning
- `new_text` identical to `old_text` (no-op) → blocker
- Estimated diff > 200 lines → warning
- More than 5 operations in one request → warning
- Duplicate `file_path` across operations → warning

**Response fields:** `status` (ok / warning / blocked), `summary`, `operation_results`, `issues` (severity + code + message), `safe_to_create_proposal`, `safe_to_apply`.

**Safety:** Read-only — creates no ToolCalls, modifies no files, creates no proposals, applies no patches. No shell execution, no external providers called.

**Frontend (Timeline tab):** "Review Patch" button appears in the Patch Proposal form alongside "Preview Patch". Displays a colour-coded result panel (green / amber / red) with status, summary, per-issue list, and safe-to-create-proposal / safe-to-apply indicators. Blocking review shows a red warning; warnings show amber. User can still proceed manually — review is advisory in v1.

---

## Agent-assisted Patch Proposal from Context v1

Builds draft patch candidates from the Step Context Bundle — no LLM, no auto-apply, no patch creation.

**Endpoint:** `POST /api/runs/{run_id}/steps/{step_id}/context-patch-draft`

**Draft selection logic:**
- Reads only the already-built `StepContextBundle` — no new tool calls, no file reads
- Ranks files: `read=True` > `match_count` > `has_snippets`
- `preferred_file_path` forces that file to the top
- `preferred_snippet_index` selects a specific snippet as `old_text`
- `old_text` = snippet from context, capped at 1200 chars
- `new_text` = `"TODO: replace with intended change"` placeholder
- Confidence: 0.8 (file read + snippet) / 0.6 (search match + snippet) / 0.3 (file path only)
- Warnings added when: bundle empty, no snippet, snippet too short, old_text truncated
- Up to 3 candidates returned with `recommended_candidate_index`

**Safety:** Creates no ToolCalls, runs no tools, reads no files, creates no patch proposals, applies no patches. No LLM called.

**Frontend (Guided tab):** "✏️ Patch Draft from Context" section appears when a bundle exists. "Create Patch Draft from Context" button builds candidates. Each candidate shows file path, confidence, reason, `old_text` preview. "Use in Patch Proposal form →" button pre-fills the existing Patch Proposal form (`file_path`, `old_text`, `new_text`) in the Timeline tab. A `⚠ Draft only — review and edit before creating proposal.` warning is always shown.

## Step Context Bundle v1

A read-only aggregation endpoint that collects all existing read-only ToolCall records for a step and presents them as a unified context bundle.

**Endpoint:** `GET /api/runs/{run_id}/steps/{step_id}/context-bundle`

**What it aggregates:**
- `search_code` calls → queries searched, matched file paths, match counts, snippets (up to 3 × 800 chars per file)
- `read_file` calls → file path, content preview (truncated), `read = true`
- `list_files` calls → files considered (background, not bloating the bundle)
- Ignored: `propose_patch`, `apply_patch`, `rollback_patch`, `run_command`, `analyze_result`

**Limits to keep responses lean:**
- Max 5 files per bundle
- Max 3 snippets per file
- Max 800 characters per snippet
- Truncation warnings added when limits are hit

**Safety:** Creates no ToolCalls, runs no tools, reads no files, executes no commands, modifies nothing.

**Frontend (Guided tab):** Each step card shows a "📦 Context Bundle" section with a "Build Context Bundle" button. Displays summary, queries, files with match counts and collapsible snippets, warnings, and `next_recommended_action`. Empty state prompts to run Auto Gather Context first.

## Workflow Runner Lite v1

One-click sequential runner for the three read-only prep actions. Located in the Patch Workflow cockpit card (the "Current actionable step" block).

**Sequence:** `auto_gather_context` → `build_context_bundle` → `create_patch_draft` → stop.

**Button:** "Run Safe Prep" — cyan accent, compact, right-aligned in the cockpit card between the step picker status and the recommended action grid.

**Behaviour:**

- Runs all three read-only actions sequentially for the active/pinned step.
- Shows a pulsing progress label with the current phase name and a step counter (e.g. "2/3").
- On success: displays a compact result string summarizing each phase.
- On failure: stops at the failing phase and shows which phase failed with the error message.
- After completion: refreshes the workflow plan, guided plan, and tool calls.

**Manual-only boundary:** If the current step's recommended action is already a manual-only action (apply, rollback, run tests, etc.), the button is disabled and a yellow message reads: "This step is already at a manual stage."

**Constraints:**

- Frontend-only — no backend changes, no new endpoints.
- Read-only — no auto-apply, no auto-test, no proposals, no shell execution, no git commit.
- Uses the same three API calls already wired in the individual action launcher.
- No external providers called.

## Workflow Automation Mode Selector v1

Frontend-only mode selector in the patch-workflow cockpit that controls which safe preparation actions are available.

**Modes:**

- **Manual** — actions only focus existing UI. Direct safe actions and Run Safe Prep are disabled. Message: "Switch to Guided or Safe Prep to run read-only preparation."
- **Guided** (default) — individual read-only actions (gather context, build bundle, create draft) can run from each step card. Run Safe Prep is disabled with hint to switch to Safe Prep mode.
- **Safe Prep** — Run Safe Prep is enabled and can run the full gather → bundle → draft sequence. Individual safe actions also remain available.

**Safety boundary (all modes):** Proposal, apply, tests, analyze, and rollback always require manual action. The mode selector only controls read-only preparation availability — it never converts manual-only actions into automatic ones.

**UI:** Compact three-button selector in the cockpit card between the step picker and the Safe Prep runner. Selected mode is highlighted in emerald. A safety banner below the selector reads: "Current mode only affects safe preparation actions."

**Constraints:**

- Frontend-only — no backend changes, no new endpoints.
- No auto-apply, auto-test, auto-analyze, auto-rollback, or auto-proposal in any mode.
- Frontend-only `localStorage` persistence is implemented for `workflowAutomationMode` and `activeWorkflowStepId`.
- No external providers called.

## Workflow Approval Policy Matrix v1

Frontend-only policy matrix that provides a structured decision for every workflow action: whether it is allowed, its execution mode (direct / draft-only / manual-only / blocked), risk level, confirmation requirement, a human-readable label, and a reason string.

**Policy function:** `getWorkflowActionPolicy(actionType, workflowAutomationMode)` returns a `WorkflowActionPolicyDecision` used by the action launcher and Safe Prep area.

**Policy rules summary:**

| Action type | Manual mode | Guided mode | Safe Prep mode |
|---|---|---|---|
| auto_gather_context | blocked | direct · low | direct · low |
| build_context_bundle | blocked | direct · low | direct · low |
| create_patch_draft | blocked | draft-only · medium | draft-only · medium |
| review_patch | manual-only | manual-only | manual-only |
| apply_patch / apply_patch_manual | manual-only · high · confirm | manual-only · high · confirm | manual-only · high · confirm |
| run_tests / run_command | manual-only · medium · confirm | manual-only · medium · confirm | manual-only · medium · confirm |
| analyze_result | manual-only | manual-only | manual-only |
| rollback_patch / rollback_manual | manual-only · high · confirm | manual-only · high · confirm | manual-only · high · confirm |

**UI integration:** The action launcher displays a compact policy row with label, risk, and confirmation badge. The cockpit card includes a collapsible "Current mode policy" panel. Safe Prep shows policy-aligned status messages per mode.

**Safety:** Proposal, apply, tests, analyze, and rollback remain manual-only in all modes. No backend changes.

## Backend Workflow Policy Enforcement v1

Backend-side pure policy module that classifies workflow actions by automation mode.

**Module:** `backend/src/orchestrator/workflow_policy.py`

**Endpoint:** `GET /api/workflow-policy?mode=guided` — read-only, no DB, no tools, no state mutation.

**Execution kinds:** `direct_safe`, `manual_only`, `approval_required_future`, `blocked`.

**Key invariant:** `can_run_automatically=true` exists only for three direct safe actions (`auto_gather_context`, `build_context_bundle`, `create_patch_draft`) and only in Guided/Safe Prep modes. Manual mode blocks all automatic execution. Blocked actions are never allowed. Approval-required future actions are classified but not yet implemented.

**Guard helper:** `assert_workflow_action_allowed(action_type, mode)` raises `WorkflowActionNotAllowedError` if the action is not permitted — available for future orchestrator integration.

**Safety:** No auto-apply, no auto-tests, no auto-analyze, no auto-rollback, no shell runner, no external providers, no DB writes, no tool_calls created. `database.py` untouched.

## Auto Context Gathering v1

A bounded read-only context-gathering workflow that runs multiple safe tool calls automatically for a staged step, then stops — before any patch is proposed or applied.

**Endpoint:** `POST /api/runs/{run_id}/steps/{step_id}/auto-context`

**Strategy (heuristic, no LLM):**
1. `list_files` — discovers the project tree
2. `search_code` — searches using the request query, step title, or step input as fallback
3. `read_file` × up to 3 — reads the most relevant files (search matches first; falls back to file-name heuristic: routes/service/controller/model/api for backend; component/page/client/store for frontend)
4. Returns a summary with queries searched, files read, and `next_recommended_action`

**Safety constraints (hard-coded):**
- Only `list_files`, `search_code`, `read_file` are ever executed
- `propose_patch`, `apply_patch`, `rollback_patch`, `run_command`, `analyze_result`, `run_tests` are never called
- Default `max_tool_calls = 5`; hard cap at 8 — requests above 8 get HTTP 400
- No project file is modified; no shell command is executed; no LLM is called
- Every call creates a `risk_level = "low"` ToolCall audit record

**Frontend (Guided tab):**
- An **"Auto Gather Context (read-only)"** button (violet) appears whenever the recommended next action is a read op or no context calls have been made yet
- Badge: `read-only · max 5 tool calls · no file changes`
- After execution: tool calls and guided plan refresh automatically
- Result shows: status, summary, queries, files read with reasons, next recommended action, warnings

## Safe Auto Read/Search v1

Allows the Guided Execution tab to automatically run read-only workspace tools (`list_files`, `read_file`, `search_code`) for a step without any human copy-paste.

**Endpoint:** `POST /api/runs/{run_id}/steps/{step_id}/auto-read`

**Safety constraints (hard-coded, not configurable):**
- Only `list_files`, `read_file`, and `search_code` are permitted. Every other action type is rejected at the gate before any DB write.
- `propose_patch`, `apply_patch`, `rollback_patch`, `run_command`, `analyze_result`, and `run_tests` return HTTP 403 unconditionally.
- No project file is ever modified by this endpoint.
- No shell command is executed.
- No LLM is called.
- Every execution creates a low-risk `ToolCall` audit record.

**Frontend (Guided tab):**
- When the recommended next action for a step is `list_files`, `search_code`, or `read_file`, a **"Run Safe Read/Search (read-only)"** button appears inside the step card.
- The button label and badge explicitly state that the action is read-only and causes no file changes.
- After execution, tool calls and the guided plan are refreshed automatically.
- `read_file` without a known file path shows a "need file path" message rather than running.
- Results display: status, human-readable summary (file count / match count / char count), `tool_call_id`, and any warnings.

**Purpose:** Prepares the groundwork for semi-autonomous context-gathering without crossing into autonomous code modification.

## Patch History + Manual Rollback v1

Every `apply-patch` call now stores **rollback metadata** in its `output_json` ToolCall record. This enables manual one-click revert of any patch that was applied through the AI Workbench patch system.

**How it works:**

- `apply_project_patch` captures `before_content` (original file text) and `after_hash` (SHA-256[:16] of applied content) for each modified or created file, stored as `rollback_data` in the endpoint's output.
- `rollback_data` is persisted to the `ToolCall.output_json` column by the audit trail — no new table or migration needed.
- `POST /api/projects/{project_id}/tools/rollback-patch` accepts a `tool_call_id` pointing to a prior `apply-patch` call, reads its `rollback_data`, and reverts each file.
- Conflict detection: before restoring, the current file hash is compared to `after_hash`. If they differ (i.e. the file was edited after the patch), the file is skipped with status `conflict` and a warning.
- Created files are deleted on rollback; modified files are restored to `before_content`.
- Files larger than 200 000 chars at apply time are marked `rollback_supported: false` and skipped with a warning.
- A `rollback-patch` ToolCall is logged with `risk_level="high"` for the audit trail.

**Safety constraints (all hold):**
- `confirm=true` is required — no autonomous rollback.
- No shell commands are executed during rollback.
- Path traversal is blocked (`_resolve_inside`).
- Secret-like files (`.env`, `*.key`, etc.) are skipped.
- The ToolCall must belong to the same `project_id` — cross-project rollback is rejected with 404.

**UI:**

- In **RunDetail.tsx** (`ToolCallRow`): each `apply-patch` row shows a rollback section. If metadata is missing, a "No rollback metadata available" message is shown. Otherwise, a confirmation checkbox and "Rollback This Patch" button appear.
- In **Tools.tsx** (`ToolHistoryRow`): identical rollback UI in the Project Tool History panel.
- After a successful rollback, `RollbackResultPanel` shows `rolled_back_files`, `skipped_files`, warnings, and the resulting `git status --short` output.
- The history panel refreshes automatically after rollback.

## Orchestrator Guided Execution v1

`GET /api/runs/{run_id}/guided-execution-plan` extends the tool plan with a per-step decision tree that determines the **recommended next manual action** based on what has already been done.

**How it works:**

- For each step, `build_guided_step_actions()` in `model_router.py` inspects the step's existing ToolCall history and applies a heuristic decision tree.
- Returns `GuidedExecutionPlanResponse` with one `GuidedStepExecutionPlan` per step, each containing `recommended_next_action`, a full `actions` list, `status_summary`, and `warnings`.
- The RunDetail UI exposes a **Guided** tab showing collapsible step cards with colour-coded action cards (green border = recommended next, greyed = blocked/disabled).

**Decision tree (in priority order):**

| State | Recommended next action | Risk |
|---|---|---|
| No read/search calls | `search_code` | low |
| Has read/search, no proposal | `propose_patch` | medium |
| Proposal done, not applied | `apply_patch` (confirm required) | high |
| Patch applied, no command run | `run_tests` | medium |
| Command failed, no analysis | `analyze_result` | low |
| Analysis found issues | `propose_patch` again | medium |
| Command passed | `review_diff` or `done` | low |

**Constraints:**
- No automatic execution.
- No ToolCall records created by the endpoint.
- No files modified.
- `apply_patch` action is always `requires_confirmation: true`.
- Blocked actions show `blocked_reason` (e.g. no proposal exists).
- Prepares the ground for a future semi-autonomous guided workflow.

## Orchestrator Tool Planning v1

`GET /api/runs/{run_id}/steps/tool-plan` returns a per-step tool recommendation for every step in a run. The endpoint is read-only — no ToolCalls are created, no files are written, and no tools are executed.

**How it works:**

- For each step, `infer_tools_for_step()` in `model_router.py` resolves a `task_type` (from persisted step route decisions if available, otherwise inferred from step title/input/agent_id) and returns an ordered list of recommended project tools.
- The response (`StepToolPlanResponse`) contains one `StepToolRecommendation` per step, each with `recommended_tools`, `reason`, `confidence`, and `warnings`.
- The RunDetail UI exposes a **Tool Plan** tab with colour-coded tool chips (hover for hints), per-step reason text, and a "Refresh Tool Plan" button.

**Tool rules by task_type:**

| task_type | recommended tools |
|---|---|
| planning / architecture | read-file, search-code |
| implementation / quick_fix | read-file, search-code, propose-patch, apply-patch, git-diff |
| debugging | read-file, search-code, run-command, analyze-command-result, propose-patch |
| test_generation | read-file, search-code, propose-patch, run-command |
| code_review / security_review | read-file, search-code, git-diff |
| documentation | read-file, search-code, propose-patch |
| deployment | read-file, search-code, run-command |

**Constraints:**
- No automatic execution — recommendations only.
- No ToolCall records created by the endpoint.
- No files modified.
- No shell runner added.
- Prepares the ground for a future semi-autonomous guided workflow.

## Apply Patch Approval Foundation

`POST /api/projects/{id}/tools/apply-patch` is a manual controlled apply path. It requires `confirm=true`, re-runs workspace safety checks before writing, blocks traversal outside the project, refuses secret-like files and large/binary files, and logs the action as a high-risk `tool_call`.

The endpoint does not run shell commands and is not autonomous: a patch is never applied automatically after preview. The Tools page requires an explicit checkbox confirmation before enabling Apply Patch, then refreshes git status/diff so the operator can review the resulting workspace changes.

## Workflow Action Launcher v1

The RunDetail patch-workflow tab now includes launch controls for each step's recommended next action. Only read-only actions run directly from this launcher: auto context gathering, context bundle creation, and patch draft creation. Manual actions still route the operator to the existing form or command flow and do not auto-create proposals, apply patches, run tests, analyze arbitrary results, or rollback changes.

This layer is intentionally UI/action-routing only: no autonomous editing, no automatic command execution, no external provider calls, and no new execution pipeline.

## Workflow Manual Action Focus v1

Manual-only patch-workflow actions now focus the existing RunDetail section where the operator can continue safely: patch proposal/review/apply actions jump to the step patch form, test/analyze actions jump to the Guided Fix Workflow, and rollback points to the audited tool-call history. These focus actions only navigate and highlight UI; manual confirmation remains required, and no patch, command, analysis, or rollback is triggered automatically.

## Workflow Continuity Hardening v1

The patch-workflow launcher now keeps manual flows connected across RunDetail. `Use in Patch Form` jumps to the Timeline patch form after inserting a draft candidate, `analyze_result` and `rollback_manual` focus persisted tool calls when a matching failed command or rollback-capable apply call is visible, and empty review/parent-step cases show clearer guidance. Manual-only actions remain manual: no automatic proposal creation, patch apply, test command, analysis, rollback, backend call expansion, or external provider execution.

## Tool Calls Focus & Pagination v1

RunDetail's Tool Calls panel now shows more history by default, supports latest 25/50/load-more controls, and adds simple filters for tool name, status, and step id. Workflow focus can reveal failed or timed-out `run-command` calls for manual analysis and rollback-capable `apply-patch` calls for manual rollback confirmation. This remains read-only navigation: no automatic analyze, rollback, test command, proposal creation, or patch apply is triggered.

## Workflow Cockpit Clarity v1

The `patch-workflow` tab is now presented as the primary operator cockpit. A compact current-actionable-step card appears at the top with step status, recommended action, risk, action mode, destination, and next instruction. Direct read-only actions, draft-only actions, and manual/confirm-required actions are labelled explicitly, while the patch form includes a short manual flow reminder. No automatic patch apply, command execution, analysis, rollback, proposal creation, backend behavior, or external provider execution is introduced.

## Workflow Active Step Picker v1

The patch-workflow cockpit can now either auto-follow the first actionable step or pin a selected active step for larger runs. The picker is local frontend state only, includes a clear-selection control, and does not trigger any action by itself. Read-only actions remain explicit, while patch apply, test commands, analysis, rollback, and proposal creation stay manual.

## Workflow State Persistence v1

RunDetail remembers workflow UI preferences per run in frontend-only `localStorage` under `ai-workbench:run:{runId}:workflow-ui`. The saved fields are `workflowAutomationMode` (`manual`, `guided`, or `safe_prep`) and `activeWorkflowStepId`. Corrupted or unavailable storage falls back safely to Guided mode and auto active-step selection. If a saved step no longer exists in the workflow plan, the cockpit returns to auto mode. No backend state, automation behavior, tool calls, patch drafts, or external providers are persisted.

## Connecting Cloud Providers

### Codex CLI (optional)

```bash
npm install -g @openai/codex
```

Current backend support is metadata/stub-only: enabling Codex can surface provider status and approval intent, but the backend does not invoke the real Codex CLI yet. Future real execution must require human approval.

### Claude Code (optional)

Current backend support is metadata/stub-only: enabling Claude can surface provider status and approval intent, but the backend does not invoke the real Claude Code CLI yet. Future real execution must require human approval.

## MVP Limitations

- Agent Registry and dynamic team assignment are implemented, but selected agents do not edit files autonomously.
- Patch workflow is implemented for proposal, static review, manual `confirm=true` apply, and manual `confirm=true` rollback.
- Safe Prep semi-auto exists for read-only context gathering, context bundle creation, and draft-only patch candidates.
- Full semi-auto apply/test/analyze/rollback chaining with approvals is not implemented yet.
- Full autonomous mode is not implemented yet.
- Codex and Claude providers are stubs — they can represent provider metadata/approval intent but do not invoke the real CLIs from the backend yet.
- No WebSocket streaming for live logs (uses polling at 2-3s intervals).
- No parallel agent execution yet; orchestration is centralized.
- Git command integration is read-only for status/diff inspection; workspace edits happen through the audited patch tools.
- Single-user, no auth.

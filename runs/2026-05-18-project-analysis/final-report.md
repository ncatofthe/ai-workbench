# AI Workbench Project Analysis

Date: 2026-05-18
Mode: repository analysis, no source-code changes

## Executive Summary

AI Workbench is currently a functional local-first MVP skeleton for a multi-agent development dashboard. It has the right basic shape: FastAPI backend, React/Vite dashboard, SQLite persistence, Ollama planning, Markdown agent roles, approval records, run artifacts, settings, and a new Tools page for workspace status and test execution.

The important product truth: the project is not yet a real autonomous multi-agent development platform. The current orchestrator creates a plan and writes run artifacts, but it does not execute steps, delegate to specialist agents, route work between providers, edit project files, manage task graphs, or enforce approvals around a general tool executor.

That is a good starting point. The next development should harden the local control plane before adding more providers.

## Current Architecture

### Backend

- Entry point: `backend/src/main.py`
- API routes: `backend/src/api/routes.py`
- Domain models: `backend/src/models.py`
- SQLite storage: `backend/src/storage/database.py`
- Orchestrator: `backend/src/orchestrator/engine.py`
- Agent registry: `backend/src/agents/registry.py`
- Safety checks: `backend/src/approvals/safety.py`
- Providers:
  - `backend/src/providers/ollama.py` is active.
  - `backend/src/providers/codex.py` is a stub.
  - `backend/src/providers/claude_provider.py` is a stub.

Flow today:

1. User creates a run through `POST /api/runs`.
2. Backend writes a DB row and starts `execute_run(...)` as a background task.
3. Orchestrator creates a run directory.
4. It writes `input.md`.
5. It loads `agents/orchestrator.md`.
6. It calls Ollama if available; otherwise it generates a fallback plan.
7. It writes `plan.md` and `final-report.md`.
8. It marks the run completed.

The core behavior is implemented in `backend/src/orchestrator/engine.py`, especially lines 15-128.

### Frontend

- App/router: `frontend/src/App.tsx`
- API client: `frontend/src/api/client.ts`
- Pages:
  - Dashboard
  - New Task
  - Runs
  - Run Detail
  - Agents
  - Projects
  - Approvals
  - Tools
  - Settings

The dashboard is useful but still operator-lite. It shows status, runs, agents, approvals, settings, workspace status, and test output. It does not yet show a task graph, per-agent logs, diffs, project profiles, changed files per run, or approval-linked execution.

### Agent System

Agents are static Markdown role files under `agents/`.

Current agents:

- orchestrator
- repo_analyst
- backend
- frontend
- mobile
- qa
- docs
- security

The registry is hardcoded in `backend/src/agents/registry.py`. It loads instructions from files but does not yet support dynamic agent config, tools, autonomy, preferred providers, fallback providers, scopes, or routing rules.

## Strong Parts

- The product direction is clear: local-first, offline-capable, optional cloud providers.
- The FastAPI/React/SQLite stack is simple and appropriate for a local control plane.
- Run artifacts under `runs/` match the governance rules.
- Agent roles already exist as editable Markdown files.
- The safety model is documented in `AGENTS.md`, `CLAUDE.md`, and `docs/safety.md`.
- Ollama integration uses a simple OpenAI-compatible API shape.
- Settings expose offline/hybrid/cloud and provider toggles.
- The new Tools page is a useful seed for local operator controls.

## Main Gaps

### 1. Orchestrator Is Planning-Only

`execute_run` generates a plan and final report, then explicitly says automatic execution is not implemented. It does not delegate to `backend`, `frontend`, `qa`, or other agents. It does not track step state. It does not call provider adapters except Ollama planning.

Priority: very high.

### 2. Stop Does Not Really Stop Work

`POST /api/runs/{id}/stop` marks the run stopped, but the background `asyncio.create_task` is not cancelled. A running task can continue and later overwrite the status as completed.

Priority: high.

### 3. Project Profiles Are Not Used Yet

Projects can be created, but selected project path and profile data are not used during runs. The Projects UI currently creates name/description only. The backend accepts `project_id`, but `execute_run` receives no project context.

Priority: high.

### 4. Relative Paths Can Split Runtime State

`DB_PATH = "./data/workbench.db"` and run dirs such as `runs/<timestamp>_<id>` depend on the current working directory. Evidence exists in both root `data/runs` and `backend/data/backend/runs`. This can split state depending on whether the backend starts from repo root or `backend/`.

Priority: high.

### 5. Safety Exists But Is Not the Execution Gate

`backend/src/approvals/safety.py` can detect risky commands, but there is no general command/tool executor that uses it. Current subprocess usage in routes is hardcoded to git status and the test script. The approval table is present, but providers and tools do not yet create approval requests and wait on decisions.

Priority: high.

### 6. Test Script Can Hide Failures

`scripts/run_tests.sh` uses `pytest -q || true` and `npx tsc --noEmit || true`. This means the script can exit 0 even when tests or TypeScript fail. Today the command completed, but the harness is not strict enough for agentic development.

Priority: high.

### 7. Docker Compose References Missing Dockerfiles

`docker-compose.yml` references `./backend/Dockerfile` and `./frontend/Dockerfile`, but no Dockerfiles are present.

Priority: medium.

### 8. `WORKBENCH_CONFIG` Is Declared But Not Read

Docker Compose sets `WORKBENCH_CONFIG=/app/config.yaml`, but `backend/src/utils/config.py` always reads `config.yaml` unless called with an explicit path.

Priority: medium.

### 9. Provider Adapters Are Not Yet a Contract

Ollama has chat/list/health. Codex and Claude have placeholder execute functions. There is no shared provider interface, no metadata, no error contract, no token/cost tracking, and no routing logic.

Priority: medium.

## Recommended Development Order

1. Fix path resolution so DB, config, agents, projects, and runs are always anchored correctly.
2. Make tests honest: remove failure-masking from `scripts/run_tests.sh`, add backend pytest tests, and keep frontend `tsc` strict.
3. Add project profiles: path, stack, package manager, test/build commands, ignored paths, safe/restricted commands.
4. Add a run-step model: each run should have ordered steps, assigned agent, provider, status, logs, artifacts, and errors.
5. Add a safe tool executor that routes every command through allowlist/denylist and approvals.
6. Add real delegation: orchestrator creates steps, specialist agents produce outputs, QA verifies, docs/report agent summarizes.
7. Add UI for timeline, per-agent logs, step retry, changed files, artifacts, and final readiness checklist.
8. Add provider adapter contract tests before implementing real Codex/Claude execution.
9. Add Dockerfiles only after local root-path behavior is stable.

## First Implementation Slice I Recommend

Build "Project-aware, honest local runs".

Acceptance criteria:

- Backend always resolves paths relative to repository root unless a project profile says otherwise.
- `WORKBENCH_DB` and `WORKBENCH_CONFIG` are respected.
- `scripts/run_tests.sh` fails when backend syntax, pytest, or frontend TypeScript fails.
- There are pytest tests for config loading, safety command matching, DB path isolation, run creation, and stop behavior.
- Projects support `path` in UI and API.
- Runs store `project_id` and include project context in the orchestrator prompt.
- No cloud provider behavior changes.

This slice improves reliability without jumping too early into complex autonomous execution.

## Prompt For External Agent 1

Use this prompt with a local model, Codex, or Claude as an independent architecture reviewer. Ask it for analysis only; do not let it modify files.

```text
You are Repo Analyst for the AI Workbench project.

Repository goal:
AI Workbench is a local-first multi-agent development dashboard. It should let a user connect a project folder, describe a task, and supervise local or optional cloud AI agents that plan, inspect, edit, test, document, and report work. Offline Ollama must remain the default. Codex and Claude are optional only when explicitly enabled.

Current architecture:
- Backend: FastAPI under backend/src
- Frontend: React + Vite + TypeScript under frontend/src
- Storage: SQLite
- Agents: Markdown files under agents/
- Runs/artifacts: runs/
- Config: config.yaml
- Safety rules: AGENTS.md and backend/src/approvals/safety.py

Your task:
Perform a read-only architecture review focused on turning this MVP into a real project-aware multi-agent development tool.

Review these areas:
1. Backend architecture and data model gaps.
2. Orchestrator gaps between planning-only and delegated execution.
3. Project profile requirements.
4. Safety and approval enforcement gaps.
5. Provider adapter contract needed for Ollama, Codex, Claude, and future providers.
6. Frontend UI pages needed for operator control.
7. Test strategy needed before autonomous execution.

Constraints:
- Do not suggest cloud as a requirement.
- Do not suggest deleting files.
- Do not suggest package installs as the first step.
- Keep the platform offline-first.
- Treat dangerous actions as requiring approval.

Output:
- Top 10 findings, ordered by severity.
- A phased implementation plan with acceptance criteria.
- Minimal database schema changes needed for the next phase.
- Risks and mitigations.
- Do not modify files.
```

## Verification

Command run:

```bash
bash scripts/run_tests.sh
```

Result:

- Exit code: 0
- Backend syntax checks completed.
- `pytest` was skipped by the script because system `pytest` is not installed.
- Frontend TypeScript check completed.

Important caveat: because the script currently masks pytest and TypeScript failures with `|| true`, this is a weak signal until the script is hardened.

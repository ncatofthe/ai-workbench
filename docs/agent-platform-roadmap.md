# AI Workbench Agent Platform Roadmap

AI Workbench is intended to become a local-first development control plane for building and maintaining arbitrary software projects with AI agents. The dashboard is the main operator interface; external tools are optional providers, debuggers, or observability layers rather than the product core.

## Product Goal

The system should let a developer connect any project folder, describe a goal, choose an autonomy level, and supervise agents that can plan, inspect, edit, test, document, and report work.

The platform must work in two conditions:

- **Offline:** Ollama-backed local agents, local files, SQLite, git, tests, logs, approvals.
- **Online:** optional external agents and cloud models through explicit provider adapters and approval policies.

Cloud providers must never be required for the core workflow.

## Core Principles

1. **Local-first by default.** Project state, runs, logs, reports, approvals, and settings live locally.
2. **Provider-neutral orchestration.** Agents depend on a provider interface, not on a specific model vendor.
3. **User-governed autonomy.** Dangerous actions require approvals; review-only and safe modes must stay available.
4. **Project-aware execution.** Every project has its own path, stack profile, scripts, test commands, ignore rules, and permissions.
5. **Observable runs.** Every meaningful action should produce logs, artifacts, and a final report.
6. **Replaceable tools.** Ollama, Codex, Claude, LangGraph, Langfuse, Open WebUI, and future tools should be integrations, not hard dependencies.
7. **No hidden cloud fallback.** Online providers are used only when enabled and visible in the UI.

## Architecture Layers

### 1. Dashboard

The dashboard is the primary UI for:

- creating tasks;
- selecting mode and autonomy;
- viewing agents and current assignments;
- reading logs and reports;
- approving risky actions;
- viewing changed files and test output;
- choosing local or cloud model routing rules.

### 2. Orchestrator

The orchestrator owns task decomposition and coordination:

- reads project profile;
- creates the run directory;
- selects agents;
- asks for approvals when needed;
- dispatches work to provider adapters;
- records logs and artifacts;
- produces final reports.

### 3. Agent Registry

Agents should be data-driven:

- role;
- instructions file;
- allowed tools;
- preferred provider;
- fallback provider;
- autonomy level;
- project scopes.

This keeps the system configurable without rewriting backend code for every new agent.

### 4. Provider Adapters

Each provider should implement the same contract:

- health check;
- plan or chat request;
- optional file-edit request;
- tool execution request;
- cost/token/time metadata when available;
- clear error reporting.

Initial adapters:

- `ollama`: enabled by default, offline-capable.
- `codex`: optional, disabled by default.
- `claude`: optional, disabled by default.

Future adapters can include local OpenAI-compatible servers, hosted APIs, or custom CLI agents.

### 5. Project Profiles

Every connected project should have a profile:

- path;
- language and framework;
- package manager;
- test commands;
- build commands;
- safe commands;
- restricted commands;
- ignored paths;
- preferred agents;
- model routing preferences.

Profiles let the same workbench operate on web apps, mobile apps, backend services, data projects, game projects, documentation repositories, and infrastructure code.

### 6. Safety and Approvals

The approval system should protect:

- file deletion;
- package installation;
- git push and history rewrites;
- Docker volume deletion;
- environment and secret access;
- cloud provider usage;
- network execution such as `curl | sh`;
- project-outside-repo access.

Approval decisions should be logged and visible in the dashboard.

### 7. Execution Tools

The first stable tool layer should include:

- workspace status;
- changed files;
- test runner;
- build runner;
- run stopper;
- artifact viewer;
- final report viewer.

Later additions:

- diff viewer;
- command palette;
- dependency audit;
- smoke-test generator;
- release checklist generator;
- project bootstrap templates.

### 8. Observability

Local observability should work without extra services:

- SQLite run state;
- markdown reports in `runs/`;
- command stdout/stderr reports;
- structured agent logs.

Optional observability integrations:

- Langfuse for traces;
- LangGraph Studio for graph debugging;
- Open WebUI for direct local model chat.

## MVP Milestones

### Milestone 1: Stable Local Control Plane

- Dashboard pages for projects, agents, runs, approvals, settings.
- Offline run creation through Ollama.
- Run logs and artifacts.
- Workspace status.
- Test runner with saved reports.
- Root-safe backend launch documentation.

### Milestone 2: Project Profiles

- Add project path management.
- Detect common stacks.
- Store per-project commands.
- Run tests/builds per selected project.
- Show project-specific changed files.

### Milestone 3: Safer Execution

- Route all commands through the approval layer.
- Add command allowlist and denylist per project.
- Add read-only, safe-dev, and auto-dev autonomy levels.
- Show approval history and decision reasons.

### Milestone 4: Agent Workflows

- Add task graph or timeline.
- Assign sub-tasks to specialist agents.
- Save per-agent logs.
- Track current task per agent.
- Add retry and escalation behavior.

### Milestone 5: Provider Router

- Add a model router screen.
- Configure provider per task type.
- Keep cloud providers disabled by default.
- Require explicit approval before external provider execution.
- Record provider used for every step.

### Milestone 6: Developer-Grade Review Loop

- Diff viewer.
- Test failure summarization.
- “Ask agent to explain” on changed files.
- “Run tests again” from the UI.
- Final merge/readiness checklist.

## Near-Term Implementation Order

1. Keep hardening the local dashboard and SQLite API.
2. Add project profiles before adding more cloud providers.
3. Make all executable tools report-producing.
4. Build diff viewer and artifact viewer.
5. Add provider adapter contract tests.
6. Add smoke tests for `/health`, `/api/agents`, `/api/runs`, and artifact creation.
7. Add optional external provider adapters only after the safety and routing UI is explicit.

## Non-Goals For Now

- Do not make Open WebUI, LangGraph Studio, Langfuse, Codex, or Claude mandatory.
- Do not expose the dashboard to the public internet by default.
- Do not let agents install dependencies, delete files, push git, or access secrets without approvals.
- Do not couple the system to one frontend/backend/mobile stack.


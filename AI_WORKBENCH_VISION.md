# AI Workbench — Product Vision

## Main goal

AI Workbench is a local offline-first multi-agent development environment.

The goal is not to build a simple AI chat, a code autocomplete tool or a Markdown plan generator. The goal is to build a local AI development team that can take a project idea and move it through a complete software development lifecycle:

```text
idea
→ analysis
→ planning
→ architecture
→ implementation
→ testing
→ review
→ fixes
→ repeat
→ final report / working project
```


## Provider philosophy

AI Workbench is **offline-first**, not **offline-only**.

The system must work fully with local Ollama models when there is no internet. At the same time, it may optionally use external providers such as ChatGPT, Codex, Claude Code or other cloud coding agents when the user explicitly enables hybrid/cloud mode.

Cloud providers are accelerators, reviewers or external workers. They are not the permanent core of the product. The core architecture must remain local, reproducible and usable without internet.

## Core idea

A single AI agent should not pretend to be an expert in everything.

The system must have a main Orchestrator that:

- understands the user goal;
- detects the project type;
- detects or infers the technology stack;
- estimates complexity and risk;
- selects a specialized AI team;
- decomposes the work into tasks;
- delegates work to agents;
- supervises execution;
- runs tests;
- routes failures to fixer/debugger agents;
- asks reviewers/security/QA agents to validate the result;
- repeats the loop until the result is ready or a clear blocker is reached.

## What AI Workbench should become

AI Workbench should become a local AI software company running on the user's machine.

The user should be able to write something like:

```text
Build a CRM on React + FastAPI + PostgreSQL.
```

The system should respond internally with a structured process:

```text
Project type: web SaaS / CRM
Stack: React, TypeScript, FastAPI, PostgreSQL
Complexity: medium/high
Risks: auth, RBAC, database schema, API contracts, testing, deployment
Required team:
- product-manager
- business-analyst
- architect
- api-designer
- frontend-developer
- react-specialist
- backend-developer
- fastapi-developer
- postgres-pro
- qa-expert
- code-reviewer
- security-auditor
- technical-writer
```

Then it should create a development plan, implement it through controlled tools, run checks, fix errors and produce a final report.

## Required multi-agent patterns

AI Workbench should use multi-agent patterns progressively, not all at once.

### 1. Pipeline Pattern

Sequential stages:

```text
input → spec → plan → architecture → tasks → implementation → tests → review → report
```

This is the base workflow.

### 2. Planning Pattern

The Orchestrator must create not only a text plan, but eventually a structured execution graph:

```json
{
  "task_id": "backend-auth",
  "type": "implementation",
  "assigned_agent": "fastapi-developer",
  "depends_on": [],
  "expected_files": ["backend/src/api/auth.py"],
  "required_tools": ["read_file", "propose_patch", "run_tests"],
  "test_commands": ["pytest tests/test_auth.py"]
}
```

### 3. Router Pattern

The system must route work to the right agent and model:

- React work → `react-specialist`.
- FastAPI work → `fastapi-developer`.
- SQL work → `sql-pro` / `postgres-pro`.
- test failures → `error-detective` / `qa-expert` / `fixer`.
- security issues → `security-auditor`.
- deployment tasks → `devops-engineer`.

### 4. Reflection Pattern

Generated work should be reviewed before being treated as complete:

```text
Developer Agent → Code Reviewer Agent → QA Agent → Fixer Agent → QA again
```

The loop should repeat until checks pass, a maximum iteration count is reached, or a blocker requires user input.

### 5. Tool Use Pattern

Agents must eventually use tools, not only generate text:

- list files;
- read files;
- search code;
- propose patches;
- apply patches inside the workspace;
- run tests;
- inspect git diff;
- produce reports.

### 6. Multi-Agent Collaboration

Full free-form collaboration is a later phase.

The first stable implementation should use centralized orchestration:

```text
orchestrator → selected agent → result → orchestrator → next agent
```

Only after this is stable should the system add parallel agents, debate mode or agent-to-agent discussions.

## Product principles

1. **Offline-first.** The core must work locally through Ollama.
2. **Provider-neutral.** Claude/Codex/cloud models may be optional providers, not the core dependency.
3. **Specialization over one giant agent.** Use roles and task routing.
4. **Progressive complexity.** Start simple, add advanced orchestration only after foundations are stable.
5. **Observable execution.** Every run must have logs, statuses, artifacts and a final report.
6. **Controlled power.** Agents should be powerful, but actions must be logged, scoped and reversible where possible.
7. **Patch-first development.** Prefer patches/diffs over uncontrolled direct edits.
8. **Tests drive completion.** A task is not done just because an agent says it is done.

## What AI Workbench is not

AI Workbench is not:

- a simple ChatGPT wrapper;
- a prompt collection;
- a Markdown-only planner;
- an uncontrolled autonomous shell bot;
- a cloud-only coding assistant;
- a visual gimmick with many agents but no execution discipline.

## Final target

The final target is a system where the user can supervise a local AI development team that works slowly but systematically:

```text
understand → plan → build → test → fix → review → document → report
```

The system should prioritize correctness, visibility and repeatability over speed.

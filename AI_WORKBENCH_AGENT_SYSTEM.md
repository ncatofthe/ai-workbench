# AI Workbench — Agent System

## Purpose

The agent system turns AI Workbench from a single-agent planner into a local multi-agent development team.

The main design is centralized orchestration first:

```text
User → Orchestrator → selected specialized agent → result → Orchestrator → next action
```

Free-form agent-to-agent collaboration is a later phase.

---

## Main roles

### Orchestrator Agent

The Orchestrator is the project lead.

Responsibilities:

- understand the user goal;
- classify the project;
- detect stack and complexity;
- select the agent team;
- create or update the plan;
- assign tasks;
- choose tools and models;
- monitor progress;
- trigger tests;
- send failures to fix/debug agents;
- request reviews;
- decide when to stop or ask the user.

The Orchestrator should not do all implementation itself.

### Product Manager Agent

Responsibilities:

- define scope;
- user stories;
- MVP boundaries;
- acceptance criteria;
- feature priorities.

### Business Analyst Agent

Responsibilities:

- business rules;
- workflows;
- edge cases;
- domain constraints;
- terminology.

### Architect Agent

Responsibilities:

- system architecture;
- module boundaries;
- data flow;
- integration decisions;
- scalability and maintainability.

### API Designer Agent

Responsibilities:

- REST/GraphQL endpoints;
- request/response contracts;
- error format;
- OpenAPI/API documentation;
- backend/frontend contract consistency.

### Backend Developer Agent

Responsibilities:

- backend services;
- controllers/routes;
- validation;
- auth/RBAC;
- file handling;
- tests.

### Frontend Developer Agent

Responsibilities:

- pages;
- components;
- forms;
- API client;
- state management;
- loading/error states;
- mobile/adaptive behavior.

### Language Specialist Agents

Examples:

- `react-specialist`;
- `typescript-pro`;
- `fastapi-developer`;
- `node-specialist`;
- `php-pro`;
- `python-pro`;
- `sql-pro`;
- `postgres-pro`;
- `swift-expert`;
- `flutter-expert`;
- `kotlin-specialist`.

These agents should be selected when the project stack requires them.

### QA Agent

Responsibilities:

- test strategy;
- unit tests;
- integration tests;
- smoke tests;
- interpreting test failures;
- verifying fixes.

### Error Detective / Fixer Agent

Responsibilities:

- analyze stack traces;
- find root cause;
- propose minimal patch;
- avoid broad rewrites;
- re-run targeted checks.

### Code Reviewer Agent

Responsibilities:

- review diffs;
- check maintainability;
- detect regressions;
- find duplicated/fragile code;
- verify that implementation matches the plan.

### Security Auditor Agent

Responsibilities:

- auth/RBAC;
- file access;
- path traversal;
- upload safety;
- secrets;
- command safety;
- reports/internal notes access.

### DevOps Engineer Agent

Responsibilities:

- local/prod launch;
- Docker;
- environment validation;
- CI/CD;
- deploy checklist;
- health/readiness endpoints.

### Technical Writer Agent

Responsibilities:

- README;
- setup instructions;
- API docs;
- release notes;
- final user-facing report.

---

## Agent Registry schema

Recommended registry item:

```json
{
  "id": "fastapi-developer",
  "name": "FastAPI Developer",
  "category": "language-specialist",
  "description": "Expert in modern async Python API development with FastAPI.",
  "skills": ["python", "fastapi", "pydantic", "async", "rest-api"],
  "default_tools": ["read_file", "search_code", "propose_patch", "run_tests"],
  "model_profile": "coding_heavy",
  "default_model": "qwen3-coder:30b",
  "fast_model": "qwen2.5-coder:7b",
  "reasoning_model": "deepseek-r1:14b",
  "can_edit_files": true,
  "can_run_commands": true,
  "risk_level": "medium",
  "enabled": true,
  "best_for": ["backend APIs", "Pydantic models", "FastAPI routes", "async services"]
}
```

---

## Agent categories

Use these categories as the top-level taxonomy:

1. `core-development`
2. `language-specialist`
3. `infrastructure`
4. `qa-security`
5. `data-ai`
6. `developer-experience`
7. `domain-specialist`
8. `business-product`
9. `meta-orchestration`
10. `research-analysis`

---

## Initial registry agents

Start with a small but useful set:

```text
orchestrator
product-manager
business-analyst
architect
api-designer
frontend-developer
backend-developer
fullstack-developer
react-specialist
typescript-pro
fastapi-developer
node-specialist
php-pro
sql-pro
postgres-pro
qa-expert
test-automator
code-reviewer
security-auditor
devops-engineer
technical-writer
error-detective
git-workflow-manager
```

Do not add 100 agents at runtime immediately. The large catalog can be imported gradually.

---

## Agent Selector

The selector chooses agents for a run.

Inputs:

- user prompt;
- project profile;
- project path;
- detected stack;
- file tree summary;
- package/config files;
- risk signals;
- desired autonomy level.

Signals:

| Signal | Agents to consider |
|---|---|
| React, Vite, TypeScript | `frontend-developer`, `react-specialist`, `typescript-pro` |
| FastAPI, Python, Pydantic | `backend-developer`, `fastapi-developer`, `python-pro` |
| Node, Express, Prisma | `backend-developer`, `node-specialist`, `typescript-pro` |
| PHP, Laravel, Symfony | `php-pro`, `backend-developer`, framework specialist |
| SQL, PostgreSQL, migrations | `sql-pro`, `postgres-pro`, `database-admin` |
| Docker, deploy, nginx, systemd | `devops-engineer`, `docker-expert`, `deployment-engineer` |
| auth, RBAC, uploads, secrets | `security-auditor`, `code-reviewer` |
| tests, build failure, stack trace | `qa-expert`, `test-automator`, `error-detective` |
| mobile, Android, iOS | `mobile-developer`, `kotlin-specialist`, `swift-expert`, `flutter-expert` |
| docs, README, release notes | `technical-writer`, `readme-generator` |

Selector output:

```json
{
  "team_size": 8,
  "execution_mode": "centralized_orchestrator",
  "selected_agents": [
    {
      "agent_id": "architect",
      "role": "System architecture lead",
      "reason": "The task requires a multi-module web application architecture.",
      "confidence": 0.92
    },
    {
      "agent_id": "react-specialist",
      "role": "Frontend implementation",
      "reason": "Project uses React and TypeScript.",
      "confidence": 0.95
    }
  ]
}
```

---

## Team sizes

### Minimal team

For small changes:

```text
orchestrator
developer
qa-expert
code-reviewer
```

### Standard project team

For normal web/mobile/backend projects:

```text
orchestrator
product-manager
architect
frontend-developer
backend-developer
qa-expert
code-reviewer
technical-writer
```

### Production team

For launch-ready projects:

```text
orchestrator
product-manager
business-analyst
architect
api-designer
frontend-developer
backend-developer
database-specialist
qa-expert
security-auditor
devops-engineer
technical-writer
code-reviewer
```

---

## Assignment states

Agent assignments should use clear states:

```text
assigned
active
waiting
completed
failed
skipped
cancelled
```

---

## Database entities

Recommended entities:

```text
agents
agent_assignments
agent_tasks
agent_messages
tool_calls
review_results
```

Minimal first implementation can start with only:

```text
agent_assignments
```

Fields:

```text
id
run_id
agent_id
assigned_role
reason
confidence
status
created_at
updated_at
```

---

## UI requirements

RunDetail should show an `Assigned Team` section:

- selected agent;
- category;
- role;
- reason;
- confidence;
- model profile;
- status;
- latest output when available.

Agents page should show:

- registry;
- enabled/disabled;
- skills;
- default tools;
- model profile;
- permissions.

---

## Rule for current implementation

Agents are selected and assigned, and the workbench has safe workspace tools plus an audited manual patch workflow. Selected agents still do not perform autonomous file editing.

The current objective is:

```text
Use the assigned team, model routes, safe tools, and patch-workflow cockpit to prepare controlled changes while keeping apply/test/analyze/rollback manual or explicitly confirmed.
```

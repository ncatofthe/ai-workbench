# AI Workbench — Roadmap

## Current foundation

The current project already has the foundation of a local control plane:

- FastAPI backend.
- React/Vite frontend.
- SQLite storage.
- Ollama provider.
- Run lifecycle.
- Project profiles.
- Product spec generation.
- Plan generation.
- Architecture generation.
- Task generation.
- Staged steps.
- Staged step execution through Ollama.
- RunDetail timeline.
- Dashboard.
- Basic approvals/tools infrastructure.

The next steps must turn this into a real development loop.

---

## Phase 0 — Stabilize current foundation

Goal: make the current staged execution safe, testable and committable.

Status: mostly done.

Required checks:

- backend tests pass;
- frontend typecheck passes;
- frontend build passes;
- README/docs reflect current behavior;
- offline Ollama behavior is correctly reported;
- Dashboard polling is not wasteful;
- no hidden cloud dependency;
- no uncontrolled shell/file actions in staged step execution.

Exit criteria:

- The current codebase can be committed as a stable baseline.

---

## Phase 1 — Agent Registry

Goal: make agents data-driven instead of hardcoded or implicit.

Status: implemented.

Add a registry where each agent has:

- `id`;
- `name`;
- `category`;
- `description`;
- `skills`;
- `default_tools`;
- `model_profile`;
- `default_model`;
- `fast_model`;
- `reasoning_model`;
- `can_edit_files`;
- `can_run_commands`;
- `risk_level`;
- `enabled`;
- `best_for`.

Minimum initial agents:

- `orchestrator`;
- `product-manager`;
- `business-analyst`;
- `architect`;
- `api-designer`;
- `frontend-developer`;
- `backend-developer`;
- `fullstack-developer`;
- `react-specialist`;
- `typescript-pro`;
- `fastapi-developer`;
- `node-specialist`;
- `php-pro`;
- `sql-pro`;
- `postgres-pro`;
- `qa-expert`;
- `test-automator`;
- `code-reviewer`;
- `security-auditor`;
- `devops-engineer`;
- `technical-writer`;
- `error-detective`;
- `git-workflow-manager`.

Backend deliverables:

- built-in registry file/module;
- registry loader;
- API endpoint: `GET /api/agents/registry`;
- tests for registry loading.

Frontend deliverables:

- update Agents page to show registry;
- display category, skills, model profile and permissions.

Exit criteria:

- Agents exist as structured data.
- UI can show the registry.
- Tests prove the registry loads.

---

## Phase 2 — Dynamic Agent Team Assignment

Goal: the Orchestrator can select a team for a specific run/project.

Status: implemented.

Agent Selector should analyze:

- user prompt;
- project profile;
- project path;
- detected stack;
- `package.json`;
- `pyproject.toml` / `requirements.txt`;
- `composer.json`;
- Docker files;
- frontend/backend folders;
- database files;
- README/config files;
- keywords such as mobile, desktop, API, deploy, security, payment, AI, data.

Selector should return:

- selected agents;
- reason for each agent;
- confidence;
- team size;
- recommended execution mode.

Data to persist:

- `run_id`;
- `agent_id`;
- `assigned_role`;
- `reason`;
- `confidence`;
- `status`;
- `created_at`.

API endpoints:

- `GET /api/runs/{id}/agents`;
- `POST /api/runs/{id}/agents/select`;
- `PATCH /api/runs/{id}/agents/{agent_id}`.

Frontend:

- add `Assigned Team` block/tab in RunDetail;
- show selected agents, roles, reasons, confidence and status.

Tests:

- web app prompt selects frontend/backend/QA agents;
- mobile prompt selects mobile agents;
- production/deploy prompt selects DevOps/security agents;
- assignments are saved and returned.

Exit criteria:

- A run can have an assigned team.
- The system explains why each agent was selected.
- No file editing is required yet.

---

## Phase 3 — Model Registry and Model Router

Goal: map agents and task types to suitable Ollama models.

Status: implemented for local registry, provider metadata, and step-level route decisions. External provider execution remains stub-only.

Add model profiles:

- `coding_heavy`;
- `coding_fast`;
- `planning_reasoning`;
- `debugging`;
- `documentation`;
- `vision_ui`;
- `embeddings`.

Each profile should define:

- primary model;
- fast model;
- reasoning model;
- fallback model;
- memory tier;
- max parallel executions;
- recommended task types.

Add hardware-aware scheduling:

- avoid running multiple heavy models at once on 32GB RAM;
- prefer 7B/8B models for small tasks;
- use 14B/30B models for complex tasks;
- track installed/not-installed model status through Ollama.

Exit criteria:

- Agents refer to `model_profile`, not only hardcoded model names.
- The Orchestrator can choose a model based on task type and hardware profile.

---

## Phase 4 — Patch-Based File Editing

Goal: agents can propose and apply changes inside a project workspace.

Status: implemented as an operator-controlled patch workflow: proposal, static review, manual `confirm=true` apply, audited history, and manual `confirm=true` rollback. Autonomous editing is not implemented.

Tools:

- `list_files`;
- `read_file`;
- `search_code`;
- `propose_patch`;
- `apply_patch`;
- `git_diff`;
- `git_status`.

Rules:

- edits must stay inside the selected project workspace;
- patches must be logged;
- changed files must be shown in RunDetail;
- diff must be inspectable;
- dangerous file actions require approval;
- direct destructive actions are blocked.

Exit criteria:

- Agent can make a small controlled code change through a patch.
- User can inspect the diff.
- Backend tests cover path boundaries and patch application.

---

## Phase 5 — Test/Fix Loop

Goal: AI Workbench can iteratively fix problems.

Status: partially implemented as manual workflow tools: allowlisted `run-command`, heuristic `analyze-command-result`, patch workflow planning, Safe Prep context gathering, context bundles, and draft patch candidates. The Orchestrator does not yet run the full patch/test/fix loop automatically.

Loop:

```text
implement
→ run tests
→ parse errors
→ assign to error-detective/fixer
→ apply patch
→ run tests again
→ review
→ repeat
```

Required controls:

- max iterations per run;
- timeout per command;
- stop on repeated identical error;
- structured test result storage;
- clear partial failure state;
- final report with remaining blockers.

Exit criteria:

- The system can fix at least one failing test through an automated loop.
- The loop stops safely when it cannot make progress.

---

## Phase 6 — Role-Based Development Runtime

Goal: selected agents execute work according to their role.

Examples:

- product-manager → requirements and scope;
- architect → architecture decisions;
- api-designer → API contracts;
- backend-developer → backend patches;
- frontend-developer → UI patches;
- sql/postgres agent → DB schema and queries;
- QA agent → tests;
- reviewer → diff review;
- security auditor → auth/RBAC/file access checks;
- technical writer → README and run instructions.

Exit criteria:

- The Orchestrator can assign staged steps to role-specific agents.
- Per-agent logs are visible in the run timeline.

---

## Phase 7 — Advanced Multi-Agent Collaboration

Goal: add collaboration after centralized orchestration is stable.

Possible features:

- parallel execution of independent tasks;
- agent-to-agent discussion;
- debate mode;
- multiple reviewers;
- automatic replanning;
- cost/time estimation;
- agent performance metrics.

Exit criteria:

- Parallel/collaborative execution works without losing observability or safety.

---

## Phase 8 — Release Workflow

Goal: support final delivery of real projects.

Features:

- release readiness checklist;
- production deploy checklist;
- backup/restore rehearsal checklist;
- security pass checklist;
- UX audit checklist;
- final report;
- commit suggestion;
- optional local commit after user approval;
- no automatic git push without explicit approval.

Exit criteria:

- The workbench can guide a project toward release-ready status.

---

## Current next slice

The next recommended slice is:

```text
Approval-gated semi-auto development loop
```

Build on the existing manual/Safe Prep workflow without adding uncontrolled autonomy.

The next implementation should deliver:

1. explicit approval boundaries for any semi-auto apply/test/analyze/rollback chaining;
2. no automatic patch apply without `confirm=true`;
3. no automatic command execution outside the project allowlist;
4. no real Codex/Claude backend execution until provider adapters and approval/redaction are ready;
5. continued RunDetail component extraction planning, because `RunDetail.tsx` is now large.

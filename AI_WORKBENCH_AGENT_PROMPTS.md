# AI Workbench — Reusable Prompts for Coding Agents

Use these prompts with Claude Code, Codex or another coding agent.

---

## 1. Universal context block

Paste this at the beginning of major prompts:

```text
Project context:
AI Workbench is a local offline-first multi-agent development environment.

The goal is not to build a simple chatbot or Markdown planner. The goal is to build a local AI software company where a main Orchestrator analyzes the user idea, detects the project stack, dynamically selects specialized AI agents, and drives the project through:

analysis → planning → architecture → implementation → testing → review → fixes → repeat → final report / working project.

Current strategic direction:
1. Stabilize current run/staged-step foundation.
2. Add Agent Registry.
3. Add Dynamic Agent Team Assignment.
4. Add Model Registry, Provider Strategy and Model Router.
5. Add patch-based file editing.
6. Add test/fix/review loop.
7. Add role-based multi-agent runtime.

Before changing code, read:
- AI_WORKBENCH_INDEX.md
- AI_WORKBENCH_VISION.md
- AI_WORKBENCH_ROADMAP.md
- AI_WORKBENCH_AGENT_SYSTEM.md
- AI_WORKBENCH_MODEL_ROUTING.md if model selection is involved
- AI_WORKBENCH_PROVIDER_STRATEGY.md if ChatGPT/Codex/Claude Code/cloud/local provider behavior is involved
- AI_WORKBENCH_DEV_CYCLE.md if execution/file editing is involved
- AI_WORKBENCH_SAFETY.md if commands or file changes are involved
```

---

## 2. Prompt: implement Agent Registry + Team Assignment

```text
You are a senior architect and lead engineer for AI Workbench.

Task:
Implement the next roadmap slice: Agent Registry + Dynamic Agent Team Assignment.

Read first:
- AI_WORKBENCH_INDEX.md
- AI_WORKBENCH_VISION.md
- AI_WORKBENCH_ROADMAP.md
- AI_WORKBENCH_AGENT_SYSTEM.md
- AI_WORKBENCH_MODEL_ROUTING.md
- AI_WORKBENCH_SAFETY.md

Current product goal:
AI Workbench must become a local offline-first multi-agent development environment where the Orchestrator selects specialized agents for each project and run.

Do not implement full autonomous file editing yet.
Do not add parallel agent execution yet.
Do not rewrite the whole engine.

Required implementation:

1. Add structured Agent Registry.
   Each agent should have:
   - id
   - name
   - category
   - description
   - skills
   - default_tools
   - model_profile
   - default_model
   - fast_model / reasoning_model when useful
   - can_edit_files
   - can_run_commands
   - risk_level
   - enabled
   - best_for

2. Add initial agents:
   - orchestrator
   - product-manager
   - business-analyst
   - architect
   - api-designer
   - frontend-developer
   - backend-developer
   - fullstack-developer
   - react-specialist
   - typescript-pro
   - fastapi-developer
   - node-specialist
   - php-pro
   - sql-pro
   - postgres-pro
   - qa-expert
   - test-automator
   - code-reviewer
   - security-auditor
   - devops-engineer
   - technical-writer
   - error-detective
   - git-workflow-manager

3. Add Agent Selector.
   It should analyze:
   - user prompt
   - project profile
   - project path
   - detected stack
   - package/config files when available
   - folder structure
   - risk keywords

   It should return:
   - selected agents
   - assigned role
   - reason
   - confidence
   - recommended execution mode

4. Persist agent assignments per run.

5. Add API endpoints:
   - GET /api/agents/registry
   - GET /api/runs/{id}/agents
   - POST /api/runs/{id}/agents/select
   - PATCH /api/runs/{id}/agents/{agent_id}

6. Add frontend:
   - show registry on Agents page or a new Agent Registry section
   - show Assigned Team in RunDetail
   - display agent role, reason, confidence, status and model profile

7. Add tests:
   - registry loads
   - selector chooses frontend/backend/qa for web app
   - selector chooses mobile agents for mobile app prompt
   - selector chooses devops/security for production/deploy prompt
   - assignments are saved and returned through API

8. Run checks:
   - Python syntax check
   - backend tests
   - frontend typecheck
   - frontend build if environment allows

Return a concise report:
- changed files
- new endpoints
- tests run
- risks/remaining work
- recommended commit message
```

---

## 3. Prompt: model routing slice

```text
You are implementing Model Registry and Model Router for AI Workbench.

Read:
- AI_WORKBENCH_MODEL_ROUTING.md
- AI_WORKBENCH_AGENT_SYSTEM.md
- AI_WORKBENCH_SAFETY.md

Goal:
Agents should use model profiles instead of hardcoded single models.

Implement:
1. model profile definitions:
   - coding_heavy
   - coding_fast
   - planning_reasoning
   - debugging
   - security_review
   - documentation
   - vision_ui
   - embeddings

2. API/UI to show model profiles and installed status if easy.
3. Routing helper that selects a model based on:
   - agent model_profile
   - task type
   - local availability
   - fallback model
   - hardware limits

Do not change core execution behavior more than necessary.
Add tests for routing/fallback.
```

---

## 4. Prompt: patch-based file editing slice

```text
You are implementing the first controlled file-editing slice for AI Workbench.

Read:
- AI_WORKBENCH_DEV_CYCLE.md
- AI_WORKBENCH_SAFETY.md
- AI_WORKBENCH_AGENT_SYSTEM.md

Goal:
Allow agents to inspect a project, propose a patch, apply it inside the selected workspace, run tests, and save diff/test output.

Implement only a minimal safe slice:
- list_files
- read_file
- search_code
- propose_patch
- apply_patch
- git_status
- git_diff
- run_tests

Rules:
- all file paths must stay inside project workspace
- patch must be saved as a run artifact
- changed files must be visible in RunDetail
- tests should run after patch when configured
- destructive operations require approval
- no git push
- no deleting files in this slice unless explicit approval exists

Add backend tests for path traversal, patch application and diff reporting.
Add UI display for patch/diff if practical.
```

---

## 5. Prompt: test/fix loop slice

```text
You are implementing Test/Fix Loop v1 for AI Workbench.

Read:
- AI_WORKBENCH_DEV_CYCLE.md
- AI_WORKBENCH_SAFETY.md
- AI_WORKBENCH_AGENT_SYSTEM.md

Goal:
After an implementation patch, AI Workbench should run configured tests, analyze failures, ask a fixer agent for a minimal patch, apply it, and rerun tests.

Controls:
- max iterations per task
- timeout per command
- stop on repeated identical error
- stop when patch does not change result
- save stdout/stderr artifacts
- final report must be honest about unresolved failures

Do not implement free-form multi-agent chat.
Keep orchestration centralized.
Add tests for successful fix, repeated failure stop and timeout handling.
```

---

## 6. Prompt: final audit before commit

```text
You are doing a final pre-commit audit for AI Workbench.

Do not add new product features.

Tasks:
1. Review git diff.
2. Check alignment with AI_WORKBENCH_VISION.md and AI_WORKBENCH_ROADMAP.md.
3. Run backend tests.
4. Run frontend typecheck/build if possible.
5. Identify risky changes.
6. Fix only small obvious issues.
7. Return:
   - changed files
   - tests run
   - pass/fail status
   - remaining risks
   - whether commit is recommended
   - suggested commit message
```


---

## 7. Provider strategy prompt

```text
You are a senior architect for AI Workbench.

Goal:
Design the provider strategy so AI Workbench can develop projects both offline and with optional external coding providers.

Important:
AI Workbench is offline-first, not offline-only. Local Ollama must remain the default and must be sufficient for normal operation. ChatGPT/Codex/Claude Code can be optional accelerators in hybrid/cloud mode, but the system must never depend on them.

Read first:
- AI_WORKBENCH_INDEX.md
- AI_WORKBENCH_VISION.md
- AI_WORKBENCH_PROVIDER_STRATEGY.md
- AI_WORKBENCH_MODEL_ROUTING.md
- AI_WORKBENCH_SAFETY.md

Tasks:
1. Analyze current provider/Ollama code.
2. Propose a Provider Registry with local_ollama, chatgpt_codex, claude_code.
3. Define provider modes: local, hybrid, cloud.
4. Define provider routing rules by task type, agent role, sensitivity and availability.
5. Define fallback behavior when cloud is unavailable.
6. Define what must be logged in RunDetail for each provider call.
7. Define privacy/redaction rules for cloud calls.
8. Do not implement full cloud runtime yet unless explicitly asked.

Output:
- architecture report;
- data model changes;
- endpoints needed;
- frontend changes;
- tests needed;
- implementation slices.
```

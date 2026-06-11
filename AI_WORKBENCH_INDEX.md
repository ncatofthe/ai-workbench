# AI Workbench — Project Knowledge Index

This repository contains a local offline-first multi-agent development workbench.

Every AI agent working on this repository must read this file first, then read the linked files that match the task.

## Source of truth documents

1. `AI_WORKBENCH_VISION.md` — product vision and final target.
2. `AI_WORKBENCH_ROADMAP.md` — phased roadmap and current priority order.
3. `AI_WORKBENCH_AGENT_SYSTEM.md` — orchestrator, agent registry, selector and assigned teams.
4. `AI_WORKBENCH_MODEL_ROUTING.md` — Ollama model profiles, model routing and hardware-aware scheduling.
5. `AI_WORKBENCH_PROVIDER_STRATEGY.md` — local/Ollama, hybrid and optional cloud provider strategy.
6. `AI_WORKBENCH_DEV_CYCLE.md` — full development lifecycle: plan → implement → test → review → fix → repeat.
7. `AI_WORKBENCH_SAFETY.md` — autonomy levels, approval rules and destructive-action policy.
8. `AI_WORKBENCH_AGENT_PROMPTS.md` — reusable prompts for Codex, Claude Code or another coding agent.

Existing supporting docs:

- `AGENTS.md` — mandatory agent governance rules.
- `CLAUDE.md` — Claude Code-specific operating rules.
- `docs/architecture.md` — current architecture overview.
- `docs/agent-platform-roadmap.md` — older platform roadmap; keep it as historical/supporting context.
- `docs/safety.md` — current safety system details.
- `docs/usage.md` — usage guide.

## One-sentence product definition

AI Workbench is a local offline-first multi-agent development environment where a main Orchestrator analyzes a project, dynamically assigns specialized AI agents, and drives the project through a complete development loop until it produces a working result or a clear final report.

## Non-negotiable direction

Do not reduce AI Workbench to a simple chatbot or Markdown plan generator.

The long-term product must become a local AI software company:

Provider rule: AI Workbench is offline-first, not offline-only. Local Ollama must be enough for normal operation. ChatGPT/Codex/Claude Code are optional providers in hybrid/cloud mode, never mandatory dependencies.


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

## Current strategic priority

The project has now completed the foundation slices for Agent Registry, Dynamic Agent Assignment, Model Registry / Router, safe workspace read tools, audited patch proposal/review/manual apply/rollback, safe allowlisted command execution, and the RunDetail patch-workflow cockpit.

The next major product direction is to turn the existing manual and Safe Prep workflow into a fuller approval-gated development loop without crossing into uncontrolled autonomous editing.

Keep the foundation order explicit:

1. Agent Registry — implemented.
2. Dynamic Agent Team Assignment — implemented.
3. Model Registry / Model Router — implemented.
4. Patch-based file editing — implemented as proposal/review/manual apply/manual rollback.
5. Safe Prep context/draft workflow — implemented for read-only and draft-only preparation.
6. Test/fix/review loop — partially implemented as manual tools; not autonomous.
7. Role-based multi-agent runtime — not implemented yet.
8. Advanced parallel collaboration — not implemented yet.

## Instruction for AI coding agents

Before making changes:

1. Read `AI_WORKBENCH_VISION.md`.
2. Read `AI_WORKBENCH_ROADMAP.md`.
3. If the task touches agents, read `AI_WORKBENCH_AGENT_SYSTEM.md`.
4. If the task touches Ollama/model selection, read `AI_WORKBENCH_MODEL_ROUTING.md`.
5. If the task touches file editing, command execution or autonomy, read `AI_WORKBENCH_DEV_CYCLE.md` and `AI_WORKBENCH_SAFETY.md`.
6. Prefer small, reviewable changes.
7. Run available tests after code changes.
8. Report exactly what changed and what remains.

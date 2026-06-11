# CLAUDE.md

## Required reading

Before changing this repository, read:

- `AI_WORKBENCH_INDEX.md`
- `AI_WORKBENCH_VISION.md`
- `AI_WORKBENCH_ROADMAP.md`
- `AI_WORKBENCH_AGENT_SYSTEM.md` when agents/registry/selector are involved
- `AI_WORKBENCH_MODEL_ROUTING.md` when Ollama/model selection is involved
- `AI_WORKBENCH_DEV_CYCLE.md` when execution/file editing/testing is involved
- `AI_WORKBENCH_SAFETY.md` when commands, files, approvals or autonomy are involved

Main product direction: AI Workbench is a local offline-first multi-agent development environment where an Orchestrator dynamically assigns specialized agents and drives projects through analysis, planning, architecture, implementation, testing, review, fixes and final reporting.


## Project

AI Workbench is a local offline-first multi-agent development environment.

Claude Code is used only as an optional bootstrap/review/cloud provider tool. The permanent core of the system must remain local and offline-first.

## Core rules

- Work only inside this repository.
- Do not delete files without explicit user approval.
- Do not run dangerous shell commands without approval.
- Do not run git push.
- Do not modify real secrets or production .env files.
- Do not enable Claude/Codex providers by default.
- Keep Ollama as the default provider.
- Preserve offline-first architecture.
- Log work into runs/.
- Prefer small, reviewable changes.
- After code changes, run available checks.

## Dangerous actions requiring approval

- Installing dependencies.
- Removing files or directories.
- Running rm -rf.
- Running docker compose down -v.
- Running database migrations.
- Modifying .env files.
- Changing provider credentials.
- Running git push.
- Running deployment commands.

## MVP scope

The current MVP should:
- run locally;
- expose a FastAPI backend;
- expose a React/Vite dashboard;
- create runs;
- call Ollama in offline mode;
- save input.md, plan.md and final-report.md;
- keep Claude and Codex providers disabled by default.

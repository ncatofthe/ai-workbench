# AI Workbench — Agent Safety & Governance Rules

## Required project context

Before working on this repository, every AI agent must read:

1. `AI_WORKBENCH_INDEX.md`
2. `AI_WORKBENCH_VISION.md`
3. `AI_WORKBENCH_ROADMAP.md`
4. Task-specific docs such as `AI_WORKBENCH_AGENT_SYSTEM.md`, `AI_WORKBENCH_MODEL_ROUTING.md`, `AI_WORKBENCH_DEV_CYCLE.md`, and `AI_WORKBENCH_SAFETY.md`.

The strategic target is a local offline-first multi-agent development workbench, not a simple chatbot or Markdown planner.


## Mandatory Rules for All Agents

### Scope & Boundaries
1. **Work only inside the project repository.** Never access files outside the designated project directory.
2. **Never delete files without explicit user approval.** All file deletions must go through the approval system.
3. **Never execute dangerous commands without approval.** The following require human confirmation:
   - `rm -rf`, `rm -r`, any recursive delete
   - `git push`, `git push --force`, `git rebase`
   - `docker compose down -v`, `docker system prune`
   - `pip install`, `npm install -g`, `brew install`
   - Any modification to `.env`, `.envrc`, secrets, or credentials
   - Any `sudo` or privilege-escalation command
   - `curl | sh`, `wget | bash`, or piped execution from network
4. **Never push to git without user confirmation.** Stage and commit locally; push only after approval.
5. **Never read secrets unless strictly necessary.** If a task doesn't require credentials, don't access them.

### Quality & Reporting
6. **Run tests after every code change.** If tests fail, report the failure and do not proceed.
7. **Write reports to `runs/`.** Every task execution must produce an output report in the corresponding run directory.
8. **Prefer offline Ollama.** Use local Ollama provider by default. Cloud providers (Codex, Claude) are only used in `hybrid` or `cloud` mode when the user explicitly enables them.

### Communication
9. **Log all actions.** Every file creation, modification, command execution, and API call must be logged.
10. **Be transparent about limitations.** If a task cannot be completed, explain why and suggest alternatives.
11. **Never fabricate results.** If the model output is uncertain or incomplete, say so.

### Inter-Agent Coordination
12. **Respect agent roles.** Each agent has a defined specialization. Don't perform tasks outside your role without orchestrator delegation.
13. **Escalate when blocked.** If an agent cannot proceed, it must report back to the orchestrator with a clear blocker description.
14. **No circular delegation.** Agents must not delegate tasks back to the agent that assigned them.

## Approval Workflow
- When an agent encounters a restricted action, it creates an `ApprovalRequest`.
- The request is shown in the Approvals panel of the dashboard.
- The user can **approve** or **reject** the request.
- The agent waits until a decision is made before continuing.
- Rejected actions are logged and the agent must find an alternative approach or halt.

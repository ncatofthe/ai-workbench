# AI Workbench — Development Cycle

## Purpose

The development cycle is the core runtime behavior that turns AI Workbench into a real project-building system.

The system must move beyond Markdown generation and toward controlled software development.

---

## Full target cycle

```text
1. User idea
2. Project analysis
3. Product specification
4. Clarifying questions if needed
5. Architecture
6. Task graph
7. Agent team assignment
8. Implementation through patches
9. Test execution
10. Error analysis
11. Fix patches
12. Code review
13. Security review when needed
14. Documentation
15. Final report
16. Optional commit suggestion
```

---

## Run lifecycle

Recommended run statuses:

```text
created
analyzing
planning
assigning_agents
implementing
testing
reviewing
fixing
waiting_approval
completed
completed_with_warnings
failed
cancelled
```

---

## Step types

Recommended step types:

```text
analysis
clarification
planning
architecture
task_decomposition
agent_assignment
implementation
test_generation
test_execution
error_analysis
fix
code_review
security_review
documentation
release_check
final_report
```

---

## Step statuses

```text
pending
running
completed
failed
skipped
cancelled
waiting_approval
```

---

## Execution graph

Long-term staged steps should evolve into a structured execution graph.

Example:

```json
{
  "id": "frontend-login-page",
  "type": "implementation",
  "title": "Implement login page",
  "assigned_agent": "react-specialist",
  "depends_on": ["api-auth-contract"],
  "expected_files": ["frontend/src/pages/Login.tsx"],
  "required_tools": ["read_file", "propose_patch", "apply_patch"],
  "test_commands": ["npm run typecheck"],
  "status": "pending"
}
```

---

## Tool layer v1

Current status: safe read tools, proposal/review/manual apply/manual rollback, allowlisted command execution, command-result analysis, context gathering, context bundles, draft patch candidates, and patch-workflow planning are implemented. The full autonomous patch/test/fix loop is not implemented.

The first real development tools should be:

### Read tools

- `list_files`
- `read_file`
- `search_code`
- `git_status`
- `git_diff`

### Write tools

- `propose_patch`
- `apply_patch`

### Verification tools

- `run_tests`
- `run_build`
- `run_typecheck`

### Reporting tools

- `save_report`
- `save_artifact`

---

## Patch-based editing flow

Current status: implemented as an operator-controlled workflow. Patch proposals and static reviews are safe preparation steps; applying and rolling back patches require explicit `confirm=true`. The system does not automatically apply patches or run the test/fix loop.

Agents should not directly rewrite arbitrary files without visibility.

Preferred flow:

```text
agent inspects files
→ agent proposes patch
→ system validates patch path boundaries
→ system applies patch inside workspace
→ system records changed files
→ system runs checks
→ RunDetail shows diff and results
```

---

## Test/fix loop

The loop:

```text
implementation patch
→ run tests
→ if pass: review
→ if fail: error-detective analyzes
→ fixer proposes patch
→ apply patch
→ run tests again
→ repeat
```

Controls:

- max iterations per task;
- max total iterations per run;
- per-command timeout;
- stop on repeated identical error;
- stop if patch does not change failing result;
- preserve all logs;
- report partial success clearly.

---

## Review loop

After tests pass, the system should still review the diff.

Reviewers:

- code-reviewer;
- security-auditor when sensitive areas changed;
- qa-expert when tests changed;
- architect when architecture files or module boundaries changed.

Review output:

```json
{
  "approved": false,
  "severity": "medium",
  "issues": [
    {
      "file": "backend/src/api/routes.py",
      "issue": "Endpoint lacks authorization check.",
      "suggested_action": "Add permission check before returning file metadata."
    }
  ]
}
```

---

## Completion criteria

A run should be considered completed only when the target criteria are met.

Examples:

- planned files changed;
- tests pass;
- build/typecheck passes;
- reviewer has no blocking issues;
- final report exists;
- user-facing summary is clear.

If not all criteria are met, use:

```text
completed_with_warnings
```

or

```text
failed_with_partial_results
```

---

## What should not happen

The system must not:

- hide failed tests;
- claim success without running checks when checks are available;
- run destructive commands without approval;
- edit outside the selected workspace;
- do uncontrolled dependency installation;
- perform git push automatically;
- continue infinite loops;
- overwrite user work silently.

---

## First implementation target

The first real dev-cycle target should be:

```text
Agent can inspect a selected project, propose a patch, apply it inside workspace, run tests, and save git diff/test output to the run.
```

Do this after Agent Registry + Assigned Team are stable.

# AI Workbench — Safety and Autonomy Policy

## Philosophy

The goal is not to make agents weak.

The goal is to give agents useful development capabilities while keeping actions controlled, logged and scoped.

Correct principle:

```text
not fewer capabilities, but more control over capabilities
```

---

## Autonomy levels

### Level 0 — Read-only

Allowed:

- inspect project metadata;
- list files;
- read files;
- search code;
- generate reports;
- propose plans.

Not allowed:

- file modifications;
- command execution;
- dependency installation.

### Level 1 — Patch-only

Allowed:

- propose patches;
- show diffs;
- explain changes.

Not allowed:

- automatically apply patches;
- run risky commands.

### Level 2 — Auto-apply inside workspace

Allowed:

- apply validated patches inside selected project;
- create new files inside workspace;
- run safe test/build/typecheck commands;
- save reports.

Requires approval:

- dependency installation;
- migrations;
- deleting files;
- changing env/secrets.

### Level 3 — Approval-required risky actions

Allowed only after explicit approval:

- install dependencies;
- run migrations;
- modify Docker/infra behavior;
- execute deployment-like commands;
- change `.env` or secret-related files;
- remove files.

### Level 4 — Hard-blocked destructive actions

Should be blocked even if an agent asks:

- modifying files outside workspace;
- deleting broad directories;
- `rm -rf /`-style commands;
- reading unrelated private system files;
- exfiltrating secrets;
- automatic git push;
- destructive Docker volume deletion without very explicit user-level workflow.

---

## Command policy

Command categories:

### Safe commands

Examples:

```bash
git status
git diff
npm run typecheck
npm test
pytest
python -m pytest
npm run build
```

Safe commands may run in controlled modes if configured in the project profile.

### Approval commands

Examples:

```bash
npm install
pip install
prisma migrate
alembic upgrade
docker compose up --build
```

These may be legitimate but should require approval.

### Hard-blocked commands

Examples:

```bash
rm -rf /
sudo rm -rf
curl ... | sh
wget ... | bash
git push --force
docker compose down -v
```

Hard-blocked commands should not run automatically.

---

## File policy

Allowed by default:

- read inside selected project workspace;
- write reports into run directory;
- propose patches.

Allowed in controlled mode:

- apply patch inside selected project workspace;
- create source/test/docs files inside project.

Approval required:

- delete files;
- modify `.env`;
- modify lockfiles when dependency changes are involved;
- modify CI/deploy files;
- modify migration files.

Hard blocked:

- access outside workspace unless explicitly selected by user;
- follow path traversal outside workspace;
- modify user system files.

---

## Logging requirements

Every meaningful action should log:

- run id;
- agent id;
- tool name;
- input summary;
- output summary;
- affected files;
- command exit code;
- stdout/stderr path;
- model/provider used;
- approval id if applicable.

---

## Approval UX

Approval request should show:

- agent requesting action;
- reason;
- exact command or file operation;
- expected effect;
- risk level;
- alternatives if rejected.

User choices:

- approve once;
- reject;
- approve for this run;
- require manual execution.

---

## Safety for Agent Registry phase

During Agent Registry + Team Assignment phase:

- no autonomous file editing by selected agents;
- no parallel agent execution;
- no shell tools assigned to agents by default;
- only selection, assignment, explanation and UI display.

---

## Safety for file editing phase

When patch editing is added:

- validate patch paths;
- ensure all paths are inside workspace;
- save patch artifact;
- apply patch atomically where possible;
- show diff;
- allow rollback through git when available;
- run tests after change.

---

## Safety for test/fix loop

Controls:

- max iterations;
- max command runtime;
- repeated-error detection;
- stop on no-change patch;
- stop on increasing failure count;
- final report must state incomplete work honestly.

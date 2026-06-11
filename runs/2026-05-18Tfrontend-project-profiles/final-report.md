# Frontend Project Profiles Report

Date: 2026-05-18
Scope: frontend Project Profiles implementation and process optimization

## Summary

To conserve remaining Codex limits, the workflow was switched from multi-agent review cycles to direct implementation of the next high-value slice.

Implemented the frontend side of Phase 1 Project Profiles against the new backend APIs.

## Changed Files

- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/Projects.tsx`
- `frontend/src/pages/NewTask.tsx`
- `frontend/src/pages/Tools.tsx`
- `scripts/run_tests.sh`

## What Changed

### Types And API Client

- Added full Project profile fields.
- Added `project_id` and `project_path` to Run.
- Added project profile input type.
- Added project tool result type.
- Added typed calls for:
  - `GET /api/projects/{id}`
  - `PATCH /api/projects/{id}`
  - `GET /api/projects/{id}/workspace/status`
  - `POST /api/projects/{id}/tools/run-tests`
  - `POST /api/projects/{id}/tools/run-build`

### Projects Page

- Added create/edit form for:
  - path;
  - stack;
  - package manager;
  - test command;
  - build command;
  - safe commands;
  - blocked commands;
  - ignore paths.
- Added newline-separated list editing for safe/blocked/ignore fields.
- Added profile completeness indicators.
- Added compact command summaries for each project.

### New Task Page

- Loads projects.
- Requires project selection before starting a run.
- Sends `project_id` to `POST /api/runs`.
- Shows selected project path, stack, test command, and build command.
- Handles empty project list with a clear warning.

### Tools Page

- Keeps Workbench status and Workbench test runner.
- Adds project selector.
- Adds project workspace status.
- Adds project test/build buttons.
- Shows cwd, command, status, approval-required details, stdout/stderr, and report path.
- Does not imply persistent approval rows are created.

### Test Script

- Removed frontend TypeScript masking from `scripts/run_tests.sh`.
- `npx tsc --noEmit` now fails the script when frontend type checking fails.

## Verification

Commands:

```bash
cd frontend && npx tsc --noEmit
bash scripts/run_tests.sh
cd frontend && npm run build
```

Results:

- Direct TypeScript check: passed.
- Backend syntax checks: passed.
- Backend pytest: 7 passed.
- Full test script: passed.
- Frontend production build: passed.

## Known Limitations

- Browser visual smoke test was not run in this pass.
- Project tool endpoints return `approval_required` responses but do not yet create persistent approval rows.
- Orchestrator remains planning-only.
- Stop still only marks the run stopped and does not cancel the background task.

## Next Highest-Value Work

1. Run a quick browser smoke test of Projects, New Task, and Tools.
2. Add persistent approval rows for project tool actions.
3. Add cancellation registry so Stop actually cancels running tasks.
4. Add run-step model after Project Profiles are stable.

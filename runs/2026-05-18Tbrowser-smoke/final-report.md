# Browser Smoke Test Report

Date: 2026-05-18
Scope: Project Profiles UI browser smoke test

## Result

Passed after one frontend compatibility fix.

The browser smoke test verified:

- Projects page opens.
- A project profile can be created from the UI.
- Profile completeness indicators render.
- New Task loads projects, enables Start Task with a project selected, and creates a project-aware run.
- Run Detail displays the created run and received an Ollama-generated plan.
- Tools page loads the selected project.
- Project workspace status renders.
- Project test command executes when it exactly matches `safe_commands`.
- Project build command executes when it exactly matches `safe_commands`.

## Fix Made During Smoke Test

The first Projects page run exposed a runtime error:

```text
TypeError: Cannot read properties of undefined (reading 'length')
```

Cause:

Old or partial project records could arrive without `safe_commands`, `blocked_commands`, or `ignore_paths`.

Fix:

`frontend/src/api/client.ts` now normalizes project API responses before pages consume them.

## Smoke Project

Created profile:

- Name: `Workbench Smoke`
- Path: `/Users/hatss/Инструменты/ai-workbench`
- Stack: `fastapi-react`
- Test command: `python3 -V`
- Build command: `node -v`
- Safe commands:
  - `python3 -V`
  - `node -v`
- Blocked commands:
  - `git push`
  - `rm`

## Verification Details

Project test:

- Command: `python3 -V`
- Status: passed
- Output included: `Python 3.14.3`

Project build:

- Command: `node -v`
- Status: passed
- Output included: `v24.14.1`

New Task:

- Project selector showed `Workbench Smoke`.
- Start Task was enabled after prompt entry.
- Run URL: `/runs/1f413d7fd8b1`
- Run completed and produced a plan.

Post-fix command verification:

```bash
cd frontend && npx tsc --noEmit
bash scripts/run_tests.sh
```

Results:

- Direct frontend TypeScript check: passed.
- Backend syntax checks: passed.
- Backend pytest: 7 passed.
- Full repository test script: passed.

## Screenshot

![Tools smoke screenshot](/Users/hatss/Инструменты/ai-workbench/runs/2026-05-18Tbrowser-smoke/tools-smoke.png)

## Remaining Caveats

- Backend path anchoring is still inconsistent because `DB_PATH = "./data/workbench.db"` depends on backend cwd.
- Project tool endpoints still return `approval_required` responses instead of creating persistent approval rows.
- Stop still does not cancel active background tasks.
- Run details are still flat; no `run_steps` timeline yet.

## Dev Servers

Frontend and backend dev servers started for the test were stopped after verification.

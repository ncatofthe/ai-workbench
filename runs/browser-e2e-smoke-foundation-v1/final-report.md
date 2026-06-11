# Browser E2E Smoke Foundation v1

## Summary

Added the first browser-level smoke testing foundation for AI Workbench using Playwright.

This slice adds explicit E2E infrastructure and read-only smoke tests only. It does not change backend behavior, runtime execution paths, proposal/apply behavior, guard behavior, delivery readiness, or automation policy.

## Chosen E2E Framework / Strategy

Framework: Playwright via `@playwright/test`.

Strategy:

- Use Vite's local dev server through Playwright `webServer`.
- Mock backend API reads inside the browser tests with `page.route()`.
- Keep fixtures small and deterministic.
- Fail the smoke flow if an unexpected API mutation request occurs during read-only navigation.
- Keep E2E out of the normal `scripts/run_tests.sh` runner so local backend/frontend checks do not require browser binaries.

## Dependency Status

`@playwright/test` was not present before this slice.

Added:

- `@playwright/test` as a frontend dev dependency.
- `frontend/package-lock.json` entries for Playwright packages.

No Playwright browser binaries were installed in this slice.

## Routes Covered

Added two smoke tests in `frontend/e2e/smoke.spec.ts`.

Covered:

- `/` app shell / Dashboard.
- `/projects`.
- `/new-task`.
- `/tools`.
- `/runs/e2e-smoke-run` with mocked RunDetail data.
- RunDetail Context Cockpit tab.
- RunDetail Delivery Report tab.

## Mocked Endpoints

The smoke tests mock minimal read-only responses for:

- `GET /health`
- `GET /api/agents`
- `GET /api/agents/registry`
- `GET /api/models/profiles`
- `GET /api/models/registry`
- `GET /api/projects`
- `GET /api/workspace/status`
- `GET /api/projects/{project_id}/workspace/status`
- `GET /api/projects/{project_id}/git/status`
- `GET /api/projects/{project_id}/git/diff`
- `GET /api/projects/{project_id}/tool-calls`
- `GET /api/runs`
- `GET /api/runs/{run_id}`
- `GET /api/runs/{run_id}/steps`
- `GET /api/runs/{run_id}/agents`
- `GET /api/runs/{run_id}/tool-calls`
- `GET /api/runs/{run_id}/model-routes`
- `GET /api/runs/{run_id}/project-context-cockpit`
- `GET /api/runs/{run_id}/delivery-summary`

## Safety Checks

The smoke tests:

- Track unexpected non-GET `/api/*` requests.
- Fulfill unexpected API mutations with status `418`.
- Assert the read-only route smoke produced no unexpected POST/API mutation calls.
- Verify the Context Cockpit section has no Apply, Approve, Run Tests, Create Proposal, Scan, or Save execution buttons.
- Do not click proposal/apply/approval/test execution controls.
- Do not call providers.
- Do not apply patches.
- Do not create projects, tasks, proposals, approvals, or tool calls.

Static scan of the new E2E/config files found no runtime execution APIs. The only provider-like strings are mocked fixture text values for dashboard display.

## Scripts Added

Added frontend scripts:

- `npm run test:e2e`
- `npm run test:e2e:smoke`

No change was made to `scripts/run_tests.sh`; browser E2E remains an explicit separate command.

## E2E Execution Result

Config/list validation passed:

- `npm run test:e2e:smoke -- --list`
- Result: `2 tests in 1 file`

Full E2E execution was attempted:

- `npm run test:e2e:smoke`
- Result: failed before page assertions because the local Playwright Chromium binary is not installed.

Observed failure:

```text
Executable doesn't exist at /Users/hatss/Library/Caches/ms-playwright/chromium_headless_shell-1223/chrome-headless-shell-mac-arm64/chrome-headless-shell
Please run: npx playwright install
```

Host setup command to enable the smoke test:

```bash
cd /Users/hatss/Инструменты/ai-workbench/frontend
npx playwright install chromium
npm run test:e2e:smoke
```

Note: the failed Playwright run produced local `frontend/test-results/` artifacts. They were left untouched.

## Frontend Build / Typecheck Results

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.

Build output:

- `48 modules transformed`
- `dist/index.html`
- `dist/assets/index-CpxJWV1L.css`
- `dist/assets/index-DHPuLqCW.js`

## Backend Test Results

Backend compile checks:

- `.venv/bin/python -m py_compile src/storage/database.py`: passed.
- `.venv/bin/python -m py_compile src/models.py`: passed.
- `.venv/bin/python -m py_compile src/api/routes.py`: passed.

Targeted backend tests:

- `tests/test_migration_backup_restore_contract.py`: `41 passed`.
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: `45 passed`.
- `tests/test_project_context_cockpit.py`: `26 passed`.
- `tests/test_delivery_report_module_awareness.py`: `20 passed`.
- `tests/test_module_aware_guard_policy.py`: `19 passed`.
- `tests/test_project_module_map.py`: `41 passed`.
- `tests/test_persistent_source_of_truth.py`: `31 passed`.

Full backend:

- `.venv/bin/pytest -q`: `1268 passed, 38 subtests passed in 17.96s`.

Root runner:

- `bash scripts/run_tests.sh`: passed.
- Runner backend result: `1268 passed, 38 subtests passed in 19.36s`.
- Runner frontend TypeScript check: passed.

## Protected Files

- `backend/src/storage/database.py` touched: no.
- `backend/src/orchestrator/engine.py` touched: no.
- Providers touched: no.
- `backend/src/project_tools.py` touched: no.
- `backend/src/model_router.py` touched: no.
- Backend behavior changed: no.

## Files Changed

Intentional changes:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/playwright.config.ts`
- `frontend/e2e/smoke.spec.ts`
- `runs/browser-e2e-smoke-foundation-v1/final-report.md`

Generated during attempted E2E run:

- `frontend/test-results/`

Pre-existing dirty/untracked backend/frontend files outside this slice were not reset, reverted, cleaned, or modified.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: Playwright browser binaries are not installed on this host, so the E2E smoke command cannot complete until `npx playwright install chromium` is run.
- P2: `npm audit --audit-level=moderate --json` reports two moderate frontend advisories through Vite/esbuild. The available automated fix is a major Vite upgrade and was not applied in this smoke-foundation slice.
- P3: None found.

## Known Limitations

- Smoke tests use mocked APIs.
- No real-backend browser E2E yet.
- No auth/RBAC browser flow yet.
- No visual regression testing.
- No cross-browser matrix.
- E2E is not included in normal `scripts/run_tests.sh` yet.
- Browser binaries need local install before the E2E command can pass.

## Recommended Next Slice

Recommended next slice: Browser E2E Smoke Regression Pass.

Reason: the smoke foundation is now present and validated at config/list level. Once Chromium is installed locally, the next slice should run the browser smoke suite end-to-end, tighten selectors if needed, and decide whether to add CI/browser setup documentation.

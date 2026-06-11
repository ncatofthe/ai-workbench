# Browser E2E Smoke Regression Pass

## Summary

Regression pass completed for the Browser E2E smoke foundation.

Result: clean. The Playwright smoke foundation is stable with local Chromium installed, remains separate from the normal test runner, and does not affect backend/runtime behavior.

## E2E Config Validation

Validated `frontend/playwright.config.ts`.

- Uses Playwright with Vite `webServer`.
- Serves the frontend at `http://127.0.0.1:5173`.
- Uses `testDir: "./e2e"`.
- Uses Chromium desktop project.
- Keeps output under `../runs/browser-e2e-smoke-foundation-v1/playwright-test-results`.
- Does not require or start a backend server.
- Does not add E2E to `scripts/run_tests.sh`.

## Smoke Coverage Validation

Validated `frontend/e2e/smoke.spec.ts`.

Coverage includes:

- App shell / Dashboard route.
- Sidebar/navigation visibility.
- Projects route.
- New Task route.
- Tools route.
- RunDetail route with mocked API data.
- Context Cockpit tab.
- Delivery Report tab.
- Module awareness visibility.
- Read-only Cockpit and Delivery behavior.

## Selector Stability Validation

Selectors are stable enough for this smoke layer.

- RunDetail title assertion uses role-specific heading selector.
- Context Cockpit assertion is scoped to the Cockpit panel instead of the entire page.
- Classification-only assertion uses exact text.
- Delivery module assertion uses a specific `Touched: auth` row.
- No exact CSS class assertions are used for behavioral smoke checks.

## Mocked API / Safety Validation

The smoke test uses mocked API responses and does not require a real backend database.

Mocking behavior:

- Intercepts `/health` and `/api/*`.
- Allows GET responses from compact fixtures.
- Records unexpected non-GET `/api/*` requests.
- Fulfills unexpected mutations with status `418`.
- Asserts no unexpected mutation requests occur during read-only route/tab navigation.

Safety validation:

- Clicking Context Cockpit did not call POST endpoints.
- Clicking Delivery Report did not call POST endpoints.
- No provider endpoint was called.
- No apply/proposal/run-command endpoint was called.
- No real project was mutated.
- No backend database was required.

The only provider-like strings in the E2E file are mocked dashboard fixture text values (`provider: "ollama"` and health `ollama: "disconnected"`), not provider calls.

## Normal Pipeline Compatibility

`scripts/run_tests.sh` remains a backend pytest + frontend TypeScript runner.

- It does not invoke Playwright.
- It does not require installed browser binaries.
- It passed after the E2E smoke foundation and selector fixes.

Note: `scripts/run_tests.sh` has pre-existing local modifications unrelated to this regression pass. Inspection confirmed it still does not run E2E or require Playwright.

## Dependency / Package Sanity

- `@playwright/test` is present in `frontend/package.json` devDependencies.
- `frontend/package-lock.json` contains corresponding Playwright package entries.
- No browser binaries are part of the inspected project changes.
- `frontend/test-results/` contains untracked generated artifacts from earlier Playwright runs. They are not part of tracked source changes and were not deleted in this pass.

## Checks / Results

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run test:e2e:smoke`: `2 passed`.

Backend compile checks:

- `.venv/bin/python -m py_compile src/storage/database.py`: passed.
- `.venv/bin/python -m py_compile src/models.py`: passed.
- `.venv/bin/python -m py_compile src/api/routes.py`: passed.

Backend targeted tests:

- `tests/test_migration_backup_restore_contract.py`: `41 passed`.
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: `45 passed`.
- `tests/test_project_context_cockpit.py`: `26 passed`.
- `tests/test_delivery_report_module_awareness.py`: `20 passed`.
- `tests/test_module_aware_guard_policy.py`: `19 passed`.
- `tests/test_project_module_map.py`: `41 passed`.
- `tests/test_persistent_source_of_truth.py`: `31 passed`.

Full backend:

- `.venv/bin/pytest -q`: `1268 passed, 38 subtests passed in 17.64s`.

Root runner:

- `bash scripts/run_tests.sh`: passed.
- Runner backend result: `1268 passed, 38 subtests passed in 17.15s`.
- Runner frontend TypeScript check: passed.

## Files Changed

Changed in this regression pass:

- `runs/browser-e2e-smoke-regression/final-report.md`

No source/test/config changes were required in this regression pass.

Existing Browser E2E foundation files remain:

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/playwright.config.ts`
- `frontend/e2e/smoke.spec.ts`

## Protected File Status

- Backend source touched in this pass: no.
- `backend/src/storage/database.py` touched in this pass: no.
- `backend/src/orchestrator/engine.py` touched in this pass: no.
- Providers touched in this pass: no.
- `backend/src/project_tools.py` touched in this pass: no.
- `backend/src/model_router.py` touched in this pass: no.

Pre-existing dirty/untracked files remain in the worktree and were not reset, reverted, cleaned, or modified by this pass.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: none newly found in this regression pass.
- P3: untracked Playwright `frontend/test-results/` artifacts exist from local runs; they are not tracked source changes. Consider adding an ignore rule in a future housekeeping slice if not already covered elsewhere.

## Known Limitations

- Smoke tests use mocked APIs.
- No real-backend browser E2E yet.
- No auth/RBAC browser flow yet.
- No visual regression testing.
- No cross-browser matrix.
- E2E is not part of normal `scripts/run_tests.sh`.
- Chromium must be installed locally with `npx playwright install chromium`.

## Recommended Next Slice

Recommended next slice: Auth/RBAC/Deployment Security Model Contract v1.

Reason: browser smoke coverage is now established and green; the remaining production-readiness blockers are more about release/security model definition than UI smoke infrastructure.

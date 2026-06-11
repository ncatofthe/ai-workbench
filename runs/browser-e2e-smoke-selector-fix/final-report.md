# Browser E2E Smoke Selector Fix

## Summary

Fixed Playwright strict-mode selector ambiguity in `frontend/e2e/smoke.spec.ts`.

The UI was rendering correctly. The failing assertions were too broad for Playwright strict mode.

## Changes Made

- Replaced broad run-title text assertion with a role-specific heading assertion:
  - `page.getByRole("heading", { name: "Review SaaS delivery readiness" })`
- Narrowed the Context Cockpit panel locator so safety button assertions are scoped to the cockpit panel, not the entire `main` area.
- Replaced broad `auth` text assertion with a specific delivery row assertion:
  - `/Touched:\s*auth/`

No product behavior changed.

## Checks

- `npm run test:e2e:smoke`: `2 passed`.
- `npx tsc --noEmit`: passed.
- `npm run build`: passed.

## Safety Boundaries

- Backend untouched.
- No runtime behavior changes.
- No provider calls.
- No apply/proposal/run/approval behavior changed.
- No DB/schema changes.

## Issues

- P0: none.
- P1: none.
- P2: none.
- P3: strict selector ambiguity fixed.

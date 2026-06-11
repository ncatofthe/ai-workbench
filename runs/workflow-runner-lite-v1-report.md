# Workflow Runner Lite v1 — Implementation Report

**Date:** 2026-05-20
**Scope:** Frontend-only UX feature in RunDetail.tsx
**Backend changes:** None
**New endpoints:** None
**New dependencies:** None

## What was implemented

A "Run Safe Prep" button added to the `PatchWorkflowCockpitCard` component inside the Patch Workflow cockpit. When clicked, it sequentially executes three read-only actions for the active/pinned step:

1. `auto_gather_context` — gathers tool call context for the step
2. `build_context_bundle` — aggregates gathered context into a bundle
3. `create_patch_draft` — builds patch draft candidates from the bundle
4. Stop — refreshes workflow plan, guided plan, and tool calls

## Files changed

| File | Change |
|------|--------|
| `frontend/src/pages/RunDetail.tsx` | Added Safe Prep runner state, handler, and UI to `PatchWorkflowCockpitCard`; extended props to receive `runId` and refresh callbacks from parent `PatchWorkflowPanel` |
| `README.md` | Added "Workflow Runner Lite v1" section documenting the feature |

## Implementation details

**State variables added to `PatchWorkflowCockpitCard`:**

- `safePrepRunning` (boolean) — true while the sequence is running
- `safePrepStep` (string) — current phase name for progress display
- `safePrepError` (string) — error message if a phase fails
- `safePrepResult` (string) — summary of all phases on success

**Props added to `PatchWorkflowCockpitCard`:**

- `runId: string` — needed for API calls
- `onRefresh: PatchWorkflowRefresh` — refresh workflow plan after completion
- `onGuidedRefresh?: PatchWorkflowRefresh` — refresh guided plan
- `onToolCallsRefresh?: PatchWorkflowRefresh` — refresh tool calls

**Manual-only boundary:** Uses the existing `MANUAL_WORKFLOW_ACTIONS` set. If the current step's recommended action is already manual-only (apply, rollback, run tests, etc.), the button is disabled and shows: "This step is already at a manual stage."

**Error handling:** Uses a local `currentPhase` variable (not React state) to capture the failing phase name in the catch block, avoiding stale-closure issues with `setSafePrepStep`.

**UI placement:** Between the step picker status message and the recommended action grid, inside a cyan-accented border box matching the existing dark theme.

## What was NOT changed

- No backend files modified
- No new API endpoints
- No auto-apply, auto-test, proposals, shell execution, or git commits
- No external provider calls
- No database changes
- `backend/src/storage/database.py` — untouched
- `backend/src/api/routes.py` — untouched
- `backend/src/orchestrator/engine.py` — untouched

## Verification

| Check | Result |
|-------|--------|
| Python syntax (15 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

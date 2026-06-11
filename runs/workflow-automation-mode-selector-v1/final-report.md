# Workflow Automation Mode Selector v1 — Final Report

**Date:** 2026-05-20
**Scope:** Frontend-only UX layer
**Backend changes:** None
**New endpoints:** None
**New dependencies:** None

## Files changed

| File | Change |
|------|--------|
| `frontend/src/pages/RunDetail.tsx` | Added `WorkflowAutomationMode` type, mode constants, state in main component; threaded mode through `PatchWorkflowPanel` → `PatchWorkflowCockpitCard` → `StepWorkflowCard` → `WorkflowActionLauncher`; added selector UI, safety banner, mode-aware button logic |
| `README.md` | Added "Workflow Automation Mode Selector v1" section |

## Mode selector behavior

| Mode | Default | Description |
|------|---------|-------------|
| Manual | No | Actions only focus existing UI. No direct workflow execution. |
| Guided | Yes | Individual read-only actions run from step cards. Safe Prep disabled with hint. |
| Safe Prep | No | Full Safe Prep sequence enabled. Individual actions also available. |

## Button availability per mode

| Action | Manual | Guided | Safe Prep |
|--------|--------|--------|-----------|
| Gather Context (single) | disabled | enabled | enabled |
| Build Context Bundle (single) | disabled | enabled | enabled |
| Create Patch Draft (single) | disabled | enabled | enabled |
| Run Safe Prep (full sequence) | disabled | disabled | enabled |
| Manual actions (apply, test, rollback, etc.) | focus UI | focus UI | focus UI |

## Safety boundary preserved

- Proposal is never created automatically in any mode.
- Patch is never applied automatically in any mode.
- Tests/commands are never run automatically in any mode.
- Analyze is never triggered automatically in any mode.
- Rollback is never triggered automatically in any mode.
- Manual-only actions remain manual-only regardless of mode.
- Safety banner: "Current mode only affects safe preparation actions. Proposal, apply, tests, analyze and rollback always require manual action."

## UX details

- Mode badge shown in each `WorkflowActionLauncher` header (e.g. "mode: Guided").
- When a read-only action is disabled due to Manual mode, message: "Switch to Guided or Safe Prep to run read-only preparation."
- When Safe Prep is disabled due to Guided mode, message: "Switch to Safe Prep mode to run the full safe preparation sequence."
- Selector is compact 3-button group with emerald highlight for active mode.
- No localStorage in v1 — mode resets on page reload.

## Checks passed

| Check | Result |
|-------|--------|
| Python syntax (15 files) | All OK |
| `database.py` compile | OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

## Remaining risks

- Mode is not persisted across page reloads (intentional v1 limitation).
- If user switches from Safe Prep to Manual while Safe Prep is running, the in-flight sequence will complete (button is disabled during run, mode change doesn't cancel).
- No backend validation of mode — mode is purely a frontend UX gate.

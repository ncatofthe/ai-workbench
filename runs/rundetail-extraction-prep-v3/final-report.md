# RunDetail Component Extraction Prep v3 — WorkflowStepPicker

## Summary

Completed a no-behavior-change frontend extraction of the active step picker UI from `RunDetail.tsx`.

No backend files were intentionally modified. No workflow behavior, policy rules, Safe Prep behavior, localStorage behavior, API calls, or automation boundaries were changed.

## Extracted

Moved from:

- `frontend/src/pages/RunDetail.tsx`

Into existing file:

- `frontend/src/components/run-detail/PatchWorkflowPanel.tsx`

Extracted component:

- `WorkflowStepPicker`

The component contains only the active step selector UI and the existing optional auto/pinned status row. The parent still computes active/actionable/fallback state.

## Props passed

`WorkflowStepPicker` receives explicitly:

- `plan`
- `steps`
- `activeStepId`
- `onActiveStepChange`
- `showModeStatus`
- `pinnedStepExists`
- `pinnedMissing`
- `pinnedDone`

The parent keeps the selection/fallback logic:

- first actionable step selection
- pinned step lookup
- pinned missing detection
- pinned done detection
- localStorage persistence and missing-step reset

## Behavior

No behavior changes intended or made:

- Auto mode still follows the first actionable step.
- Pinned mode still focuses the selected step.
- Done pinned step messaging is unchanged.
- Missing pinned step warning is unchanged.
- Clear active step still calls `onActiveStepChange(null)` and returns to auto mode.
- Selecting a step still only updates UI state; it does not run any action.
- localStorage persistence remains in `RunDetail.tsx` and is unchanged.
- Safe Prep, policy matrix, manual-only focus, and WorkflowActionLauncher behavior are unchanged.

## Size

Current frontend sizes after v3:

| File | Lines |
|---|---:|
| `frontend/src/pages/RunDetail.tsx` | 4114 |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | 432 |

## Checks

| Check | Result | Notes |
|---|---:|---|
| `frontend: npx tsc --noEmit` | Passed | No TypeScript errors. |
| `frontend: npm run build` | Passed | Vite production build completed. |
| `backend: .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles; not modified by this slice. |
| `backend: .venv/bin/pytest -q` | Passed | 258 passed. |
| `root: bash scripts/run_tests.sh` | Passed | Backend syntax, backend pytest, and frontend TypeScript check passed. |

## Changes made

- Updated `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` to export `WorkflowStepPicker`.
- Updated `frontend/src/pages/RunDetail.tsx` to import `WorkflowStepPicker` and pass explicit state/display props.
- Added this report.

## Remaining risks

- `RunDetail.tsx` is still large at 4114 lines.
- `PatchWorkflowPanel.tsx` is now 432 lines; future extractions should avoid turning it into an unrelated catch-all.
- Next low-risk candidate: `StepWorkflowCard`, if kept as a pure wrapper around existing `WorkflowStageRow`, `NextActionCard`, and `WorkflowActionLauncher`.

## Worktree note

The repository already shows pre-existing modified/untracked backend files in `git status`. This slice did not intentionally edit backend files and did not touch `backend/src/storage/database.py`.

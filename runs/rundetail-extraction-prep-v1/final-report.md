# RunDetail Component Extraction Prep v1

## Summary

Completed a narrow no-behavior-change frontend extraction from `RunDetail.tsx`.

This slice did not add features, change workflow rules, change localStorage behavior, change API calls, or modify backend code.

## Extracted

Created:

- `frontend/src/components/run-detail/PatchWorkflowPanel.tsx`

Moved out of `frontend/src/pages/RunDetail.tsx`:

- `WorkflowStageRow`
- `NextActionCard`

This is intentionally smaller than the full `PatchWorkflowPanel` subtree. The full subtree is still tightly coupled to Safe Prep runner state, manual focus callbacks, workflow policy helpers, and patch draft callbacks, so this prep slice extracted the smallest safe components first.

## Props / dependencies

`WorkflowStageRow` receives:

- `stage: PatchWorkflowStage`

`NextActionCard` receives:

- `action: PatchWorkflowNextAction`
- `actionModeClass`
- `actionModeLabel`
- `actionDestinationLabel`
- `actionInstruction`
- `actionSafetyLabel`

The label/class/helper functions remain in `RunDetail.tsx` and are passed explicitly. This avoids duplicating workflow policy/rule rendering and keeps behavior unchanged.

## Behavior

No behavior changes intended or made:

- Patch workflow tab wiring is unchanged.
- Manual / Guided / Safe Prep mode state is unchanged.
- Active step picker is unchanged.
- Run Safe Prep sequence is unchanged.
- Policy matrix labels and safety copy are unchanged.
- Manual-only focus callbacks are unchanged.
- Tool Calls focus is unchanged.
- localStorage key and saved shape are unchanged.
- API calls are unchanged.
- No proposal/apply/test/analyze/rollback automation was added.

## Size

Current frontend sizes after extraction:

| File | Lines |
|---|---:|
| `frontend/src/pages/RunDetail.tsx` | 4378 |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | 88 |

## Checks

| Check | Result | Notes |
|---|---:|---|
| `frontend: npx tsc --noEmit` | Passed | No TypeScript errors. |
| `frontend: npm run build` | Passed | Vite production build completed. |
| `backend: .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles; not modified by this slice. |
| `backend: .venv/bin/pytest -q` | Passed | 258 passed. |
| `root: bash scripts/run_tests.sh` | Passed | Backend syntax, backend pytest, and frontend TypeScript check passed. |

## Changes made

- Added `frontend/src/components/run-detail/PatchWorkflowPanel.tsx`.
- Updated `frontend/src/pages/RunDetail.tsx` to import and use `WorkflowStageRow` and `NextActionCard`.
- Added this report.

No backend files were intentionally modified. The worktree already contains pre-existing backend and frontend changes from earlier slices; this slice only touched the frontend extraction files and this report.

## Remaining risks

- `RunDetail.tsx` is still large at 4378 lines.
- Full `PatchWorkflowPanel` extraction remains desirable but should be done in smaller steps.
- Recommended next extraction candidates:
  - `WorkflowActionLauncher`
  - `WorkflowStepPicker`
  - `PatchWorkflowCockpitCard`

Next extraction should keep helper functions centralized or move the whole policy/helper set together to avoid duplicated workflow rules.

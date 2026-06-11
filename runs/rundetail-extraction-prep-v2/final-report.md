# RunDetail Component Extraction Prep v2

## Summary

Completed a no-behavior-change frontend extraction of `WorkflowActionLauncher` from `RunDetail.tsx`.

No backend files were intentionally modified. No workflow behavior, policy rules, localStorage behavior, API contracts, or automation boundaries were changed.

## Extracted

Moved from:

- `frontend/src/pages/RunDetail.tsx`

Into existing file:

- `frontend/src/components/run-detail/PatchWorkflowPanel.tsx`

Extracted component:

- `WorkflowActionLauncher`

The file already contained the v1 extracted `WorkflowStageRow` and `NextActionCard`, so keeping the launcher there keeps the patch-workflow UI pieces together without creating another file.

## Props passed

`WorkflowActionLauncher` now receives explicitly:

- `runId`
- `plan`
- `action`
- `workflowMode`
- `workflowModeLabel`
- `onRefresh`
- `onGuidedRefresh`
- `onToolCallsRefresh`
- `onFocusManualAction`
- `onUseDraft`
- `workflowActionKind`
- `getWorkflowActionPolicy`
- `manualWorkflowButtonLabel`
- `manualWorkflowHint`
- `actionModeClass`
- `actionModeLabel`
- `actionDestinationLabel`
- `policyLabelClass`

The workflow policy matrix and helper functions remain in `RunDetail.tsx` and are passed through props. This avoids duplicating policy logic.

## Behavior

No behavior changes intended or made:

- `auto_gather_context` remains a direct safe action.
- `build_context_bundle` remains a direct safe action.
- `create_patch_draft` remains a draft-only direct action.
- Run Safe Prep behavior is unchanged.
- Manual-only actions still only focus existing UI.
- `review_patch`, `create_proposal`, `apply_patch`, `run_tests`, `analyze_result`, and `rollback_patch` are not executed automatically by the launcher.
- Policy labels, risk text, button labels, action result rendering, focus error rendering, and draft candidate rendering remain the same.
- localStorage behavior is unchanged.
- API calls are unchanged.

## Size

Current frontend sizes after v2:

| File | Lines |
|---|---:|
| `frontend/src/pages/RunDetail.tsx` | 4181 |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | 337 |

## Checks

| Check | Result | Notes |
|---|---:|---|
| `frontend: npx tsc --noEmit` | Passed | No TypeScript errors. |
| `frontend: npm run build` | Passed | Vite production build completed. |
| `backend: .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles; not modified by this slice. |
| `backend: .venv/bin/pytest -q` | Passed | 258 passed. |
| `root: bash scripts/run_tests.sh` | Passed | Backend syntax, backend pytest, and frontend TypeScript check passed. |

## Changes made

- Updated `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` to export `WorkflowActionLauncher`.
- Updated `frontend/src/pages/RunDetail.tsx` to import `WorkflowActionLauncher` and pass explicit helper/callback props.
- Added this report.

## Remaining risks

- `RunDetail.tsx` is still large at 4181 lines.
- `PatchWorkflowPanel.tsx` is now 337 lines and should not become a dumping ground for unrelated RunDetail logic.
- Next low-risk extraction candidate: `WorkflowStepPicker` or the remaining `StepWorkflowCard` wrapper, while keeping policy helpers centralized unless the entire policy/helper set is moved together.

## Worktree note

The repository already shows pre-existing modified/untracked backend files in `git status`. This slice did not intentionally edit backend files and did not touch `backend/src/storage/database.py`.

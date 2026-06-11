# Post-Extraction Regression Pass v1

## Summary

Extraction v1-v4 can be considered stable.

No P0/P1 regressions were found in the patch-workflow cockpit after extracting `WorkflowStageRow`, `NextActionCard`, `WorkflowActionLauncher`, `WorkflowStepPicker`, and `WorkflowModeSelector`.

No source-code changes were made in this pass.

## Checks

| Check | Result | Notes |
| --- | --- | --- |
| Required project context read | Passed | Read `AI_WORKBENCH_INDEX.md`, `AI_WORKBENCH_VISION.md`, `AI_WORKBENCH_ROADMAP.md`, `AI_WORKBENCH_DEV_CYCLE.md`, and `AI_WORKBENCH_SAFETY.md`. |
| Patch-workflow cockpit code review | Passed | Current actionable step, step picker, mode selector, action launcher, next action card, and stage rows remain wired through explicit props. |
| Mode behavior review | Passed | Manual, Guided, and Safe Prep mode gates match the current policy helpers in `RunDetail.tsx`. |
| Safety boundary review | Passed | Patch-workflow direct launcher branches remain limited to context gathering, context bundle, and patch draft creation. |
| State/localStorage review | Passed | Storage key and persisted fields are unchanged. Broken JSON still falls back safely. |
| Imports/types review | Passed | No circular import found; no duplicated policy matrix found; helpers remain in `RunDetail.tsx` and are passed into extracted components. |
| `cd frontend && npx tsc --noEmit` | Passed | No TypeScript errors. |
| `cd frontend && npm run build` | Passed | Production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | Compile-only check; `database.py` was not modified. |
| `cd backend && .venv/bin/pytest -q` | Passed | 258 passed. |
| `cd . && bash scripts/run_tests.sh` | Passed | Backend syntax, pytest, and frontend TypeScript checks passed. |

## Workflow behavior

- Current actionable step selection remains in `PatchWorkflowCockpitCard`.
- `WorkflowStepPicker` only renders the active-step selector and calls `onActiveStepChange`.
- `WorkflowModeSelector` only renders Manual / Guided / Safe Prep choices and calls `onModeChange`.
- `WorkflowActionLauncher` receives policy helpers from `RunDetail.tsx`; it does not own or duplicate the policy matrix.
- `NextActionCard` remains presentational and receives display helpers through props.
- `WorkflowStageRow` remains presentational and only renders workflow stage status.
- Active step selection does not launch actions.
- Mode selection does not launch actions.

## Mode behavior

- Manual mode blocks direct read-only/draft launcher actions through `modeBlocksReadOnly`.
- Manual-only actions still call `onFocusManualAction` and only focus existing UI.
- Guided mode still allows individual safe read-only/draft actions through the existing policy helper.
- Safe Prep mode still enables the existing Run Safe Prep button when the step is eligible.
- Safe Prep still runs the same bounded sequence: `auto_gather_context` → `build_context_bundle` → `create_patch_draft` → stop.

## Safety boundaries

- Patch-workflow direct launcher actions remain limited to:
  - `auto_gather_context`
  - `build_context_bundle`
  - `create_patch_draft`
- Proposal creation is not automatic.
- Patch apply is not automatic and remains behind manual `confirm=true` flow.
- Test/run-command execution is not started by the patch-workflow launcher.
- Analyze is not automatic.
- Rollback is not automatic and remains behind manual `confirm=true` flow.
- No shell runner was added by extraction.
- No external provider execution was added by extraction.
- Codex and Claude providers remain stub-only in backend provider modules.

## State/localStorage

- localStorage key remains `ai-workbench:run:{runId}:workflow-ui`.
- Persisted fields remain:
  - `workflowAutomationMode`
  - `activeWorkflowStepId`
- Invalid JSON still falls back to `workflowAutomationMode: "guided"` and `activeWorkflowStepId: null`.
- Missing active step still resets to auto mode via the existing parent effect.
- Extracted components do not read or write localStorage directly.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | N/A | No P0/P1/P2/P3 regression found in this pass. | N/A |

## Changes made

No source-code changes.

Created this report only:

- `runs/post-extraction-regression-v1/final-report.md`

## File sizes

| File | Lines |
| --- | ---: |
| `frontend/src/pages/RunDetail.tsx` | 4101 |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | 489 |

## Recommended next slice

Semi-auto Approval Boundary v1.

Suggested scope: define and verify the approval boundary for moving from current Manual / Guided / Safe Prep workflow toward semi-auto approval-gated execution, without enabling auto-apply, auto-tests, auto-analyze, auto-rollback, shell expansion, or external provider execution.

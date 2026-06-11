# RunDetail Component Extraction Prep v4

## Summary

Extracted the patch-workflow cockpit mode selector into a small visual component with no behavior changes.

Current version remains stable after the requested verification suite.

## Files changed

| File | Change |
| --- | --- |
| `frontend/src/pages/RunDetail.tsx` | Replaced the inline workflow mode selector JSX with `WorkflowModeSelector`; kept workflow mode state, mode options/copy, policy text, and localStorage behavior in the parent. |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | Added exported `WorkflowModeSelector` component. |
| `runs/rundetail-extraction-prep-v4/final-report.md` | Added this report. |

## Extracted component

`WorkflowModeSelector` was added to `frontend/src/components/run-detail/PatchWorkflowPanel.tsx`.

Props passed explicitly:

| Prop | Purpose |
| --- | --- |
| `mode` | Current workflow automation mode. |
| `modes` | Ordered Manual / Guided / Safe Prep labels and values. |
| `modeDescription` | Current mode description prepared by `RunDetail.tsx`. |
| `savedForRunLabel` | Existing "Saved for this run." copy. |
| `policyLines` | Existing compact current-mode policy copy. |
| `onModeChange` | Parent callback for changing workflow mode. |

## Behavior preservation

- No workflow rules changed.
- No policy matrix logic moved or changed.
- `workflowAutomationMode` state remains in `RunDetail.tsx`.
- localStorage load/save logic remains in `RunDetail.tsx`.
- Mode selection still only changes UI state; it does not launch actions.
- Manual mode still blocks direct safe-prep execution.
- Guided mode still allows individual read-only/draft actions as before.
- Safe Prep mode still allows the existing Run Safe Prep sequence as before.
- Manual-only actions remain manual-only: review, proposal, apply, tests, analyze, rollback.
- No proposal, apply, tests, analyze, rollback, shell command, or external provider execution was added.

## Verification

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | No TypeScript errors. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` was only compiled, not modified. |
| `cd backend && .venv/bin/pytest -q` | Passed | 258 passed. |
| `cd . && bash scripts/run_tests.sh` | Passed | Backend syntax, pytest, and frontend TypeScript checks passed. |

## File sizes

| File | Lines |
| --- | ---: |
| `frontend/src/pages/RunDetail.tsx` | 4101 |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | 489 |

## Remaining risks

- `RunDetail.tsx` is still large and remains the main maintainability risk.
- `PatchWorkflowPanel.tsx` is growing as extraction continues; future slices should avoid turning it into another large mixed-responsibility file.
- Safe Prep runner and cockpit orchestration remain embedded in `RunDetail.tsx` and should only be extracted in a focused no-behavior-change slice.

## Action log

- Inspected the existing workflow mode selector block.
- Added `WorkflowModeSelector` as a visual component.
- Replaced the inline selector block in `RunDetail.tsx`.
- Ran the requested frontend, backend, and root verification commands.
- Created this report.

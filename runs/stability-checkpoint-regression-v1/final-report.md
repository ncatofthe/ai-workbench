# Stability Checkpoint & Regression Pass v1

## Summary

Current version can be considered stable at this checkpoint.

All requested baseline checks passed. No P0/P1 regressions were found in the workflow cockpit, Safe Prep runner, policy matrix, localStorage persistence, manual patch/apply/rollback flow, or provider safety boundaries.

No source-code changes were made in this pass. This report is the only artifact created for the checkpoint.

## Baseline checks

| Check | Result | Notes |
|---|---:|---|
| `frontend: npx tsc --noEmit` | Passed | No TypeScript errors. |
| `frontend: npm run build` | Passed | Vite production build completed. Output bundle: `dist/assets/index-D0nCJfrJ.js`. |
| `backend: .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles; file was not modified. |
| `backend: .venv/bin/pytest -q` | Passed | 258 passed in 3.72s. |
| `root: bash scripts/run_tests.sh` | Passed | Backend syntax checks passed, backend pytest 258 passed, frontend TypeScript check passed. |

## Workflow integrity

Checked by code review in `frontend/src/pages/RunDetail.tsx`, `frontend/src/api/client.ts`, `backend/src/api/routes.py`, `backend/src/model_router.py`, `backend/src/project_tools.py`, and provider stubs.

- `patch-workflow` tab is wired and renders the `PatchWorkflowPanel`.
- Current actionable step is selected from pinned active step or first actionable workflow step.
- Active step picker supports auto mode, pinning, and clear selection.
- Manual / Guided / Safe Prep modes are present and mode labels/descriptions are coherent.
- Policy matrix classifies workflow actions as `direct`, `draft_only`, `manual_only`, or `blocked`.
- Run Safe Prep runs exactly: `auto_gather_context` -> `build_context_bundle` -> `create_patch_draft` -> stop.
- Launch Recommended Action directly runs only patch-workflow safe prep actions, or focuses the existing manual UI for manual-only actions.
- Use in Patch Form inserts draft candidate data into the existing patch form and does not create a proposal.
- Step Patch Tools keep review, preview/proposal, and apply controls separate.
- Review Patch is read-only and does not create ToolCalls, proposals, or file changes.
- Preview/Create Proposal is manual button-driven.
- Apply requires the manual confirmation checkbox and sends `confirm=true`.
- Tool Calls filters/focus support tool, status, step, failed command focus, and rollback-capable apply-patch focus.
- Analyze and rollback focus paths remain manual-only.

Note: the separate Guided tab still includes the older Safe Auto Read/Search button for `list_files`, `read_file`, and `search_code`. This is read-only, user-clicked, and not part of the patch-workflow direct action launcher.

## Safety regression check

Confirmed:

- In the patch-workflow launcher, the only direct safe actions are `auto_gather_context`, `build_context_bundle`, and `create_patch_draft`.
- Safe Prep sequence runs only read-only/context/draft preparation and then stops.
- Proposal is not created automatically.
- `apply-patch` is not called automatically.
- `run-command` is not called automatically by patch-workflow actions.
- `analyze-command-result` is not called automatically by patch-workflow actions.
- `rollback-patch` is not called automatically.
- `apply-patch` and `rollback-patch` require explicit `confirm=true`.
- `run-command` remains allowlist-based and uses `shell=False`.
- No new arbitrary shell runner was found.
- Codex/Claude backend providers remain stubs; provider status checks may inspect PATH, but real external execution is not invoked.

## LocalStorage check

Confirmed:

- Storage key is `ai-workbench:run:{runId}:workflow-ui`.
- Saved shape contains only:
  - `workflowAutomationMode`
  - `activeWorkflowStepId`
- Invalid/malformed JSON is caught and falls back to `{ workflowAutomationMode: "guided", activeWorkflowStepId: null }`.
- Invalid workflow mode values fall back to `guided`.
- Blank or non-string active step ids fall back to `null`.
- If the saved step is missing from the current workflow plan, active step is reset to `null` and the cockpit returns to auto mode.
- No sensitive data, tool payloads, file contents, provider output, patch contents, or command output are stored in this workflow UI localStorage entry.

## File size / maintainability

| File | Lines | Bytes | Risk |
|---|---:|---:|---|
| `frontend/src/pages/RunDetail.tsx` | 4442 | 170231 | High maintainability risk; future extraction recommended. |
| `backend/src/api/routes.py` | 2615 | 96029 | Medium/high maintainability risk; route grouping would help later. |
| `backend/src/model_router.py` | 2181 | 85751 | Medium/high maintainability risk; workflow planning/routing split would help later. |
| `backend/src/storage/database.py` | 1313 | 41507 | Medium risk; do not touch casually because it is central persistence code. |

## Issues found

| Priority | Area | Problem | Suggested fix |
|---|---|---|---|
| P2 | Maintainability | `RunDetail.tsx` is 4442 lines and now owns timeline, guided workflow, patch workflow cockpit, tool calls, rollback controls, localStorage state, and multiple workflow helpers. This does not break runtime today, but it increases regression risk. | Next slice should prepare component extraction boundaries without changing behavior. |
| P3 | Copy clarity | Guided Execution says "Nothing runs automatically" while the same tab exposes user-clicked Safe Auto Read/Search and Auto Gather Context buttons. This is not a safety bug, but the wording can be read too broadly. | In a later tiny copy-only pass, clarify as "Nothing runs without an explicit button click; write/test actions remain manual." |

No P0 or P1 issues found.

## Changes made

No source-code changes were made. No backend logic, frontend behavior, API behavior, `database.py`, providers, shell execution, or workflow automation behavior was changed.

Created:

- `runs/stability-checkpoint-regression-v1/final-report.md`

## Recommended next slice

RunDetail Component Extraction Prep v1.

Keep it preparatory and low-risk: map component boundaries, define props/types, and choose extraction order. Do not extract behavior in the prep slice unless a very small component can be moved with identical tests and no behavior change.

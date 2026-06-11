# Dogfooding Pass v1

## Summary

AI Workbench is close to usable for a small, manual patch workflow, but it is not yet smooth enough for a non-expert operator to complete the whole loop without hesitation. The foundation is sound: patch workflow planning, read-only context gathering, draft creation, manual patch review/proposal/apply, safe tests, analysis, rollback history, and audit logs are present. The biggest remaining issue is continuity: actions jump between `patch-workflow`, `timeline`, `guided`, `Step Patch Tools`, and `Tool Calls`, and a few recommendations still point to a section that cannot immediately perform the next useful action.

This pass was performed as a read-only code-level UX audit of `frontend/src/pages/RunDetail.tsx`. I did not create a new run, apply a patch, run project commands, modify backend code, or touch `database.py`.

## Stable baseline

- backend pytest: 258 passed
- scripts/run_tests.sh: passed
- frontend tsc/build: passed

Baseline taken from the current stable point provided for this audit. No verification commands were rerun during this read-only pass.

## Tested workflow

1. Reviewed RunDetail state wiring for `tool-plan`, `guided`, `patch-workflow`, `Timeline`, `Tool Calls`, context bundles, draft prefills, and patch form state.
2. Traced `patch-workflow` rendering:
   - `PatchWorkflowPanel`
   - `StepWorkflowCard`
   - `NextActionCard`
   - `WorkflowActionLauncher`
3. Traced direct safe launcher actions:
   - `auto_gather_context`
   - `build_context_bundle`
   - `create_patch_draft`
4. Traced manual focus action mapping:
   - `review_patch`
   - `create_proposal` / `propose_patch`
   - `apply_patch_manual` / `apply_patch`
   - `run_tests_manual` / `run_tests` / `run_command`
   - `analyze_result`
   - `rollback_manual` / `rollback_patch`
5. Reviewed existing destination blocks:
   - `GuidedFixWorkflow`
   - `StepPatchSection`
   - `ToolCallsPanel`
6. Checked whether the UI communicates:
   - current workflow status;
   - safe vs manual actions;
   - where the next click should happen;
   - confirmation requirements;
   - audit visibility.

## What works well

- `patch-workflow` gives a useful high-level checklist of stages and recommended next action per step.
- `Launch Recommended Action` clearly separates read-only direct actions from manual-required actions.
- Direct read-only actions do not apply patches, run commands, or call external providers.
- Manual focus is a good improvement: patch/review/apply actions route to `Step Patch Tools`, test/analyze actions route to `Guided Fix Workflow`, rollback routes to `Tool Calls`.
- `StepPatchSection` has the right safety shape: review, preview/proposal, confirm checkbox, and apply are separate.
- Patch calls are linked to step/tool-call history, so auditability is visible.
- `GuidedFixWorkflow` keeps test and analysis manual and local to a step.
- Rollback is high-friction in the right way: it is only visible from apply-patch tool calls and requires explicit confirmation.

## UX blockers

| Priority | Area | Problem | Impact | Suggested fix |
|---|---|---|---|---|
| P1 | Patch workflow recommendation | After context exists, workflow can recommend `review_patch`, but review requires populated `file_path`, `old_text`, and `new_text`. The user may not know they should create/use a patch draft first. | The operator can land in an empty form and stall. | Change next-action ordering to prefer `create_patch_draft` before `review_patch` when context exists but the patch form is empty/no draft was used. |
| P1 | Draft continuity | `create_patch_draft` shows candidates in `patch-workflow`. Clicking `Use in Patch Form` stores a prefill, but the user remains in the `patch-workflow` tab; the destination form is in `timeline`. | User may think nothing happened or may not know where the candidate went. | After `Use in Patch Form`, call the same manual focus path for `create_proposal` so Timeline opens, the step form expands, and the patch form is highlighted. |
| P1 | Analyze result focus | `analyze_result` focuses `GuidedFixWorkflow`, but that component only shows the Analyze button when it has a local `commandResult` from the current session. If the failed command exists only in persisted Tool Calls, the focused section may show only Run Tests. | Workflow recommends analysis, but the visible destination may not contain the action. | For `analyze_result`, focus the failed `run-command` ToolCall when one exists; otherwise show a stronger message and focus `Tool Calls`, not `GuidedFixWorkflow`. |
| P1 | Parent/orchestrator steps | Manual focus anchors exist only in `StepCard` child/orphan steps. If `patch-workflow` emits a recommended action for a parent/orchestrator step, the focus target may not exist. | Launcher reports target not found, creating a dead end. | Ensure patch-workflow emits actionable recommendations only for steps with patch/test UI, or render minimal action anchors for parent steps too. |
| P1 | Rollback routing | `rollback_manual` focuses the generic Tool Calls panel. It does not focus the specific `apply-patch` call that contains rollback controls, and the panel shows only the latest 8 calls. | User can still fail to find rollback controls. | Add stable data anchors to `ToolCallRow` and focus the latest rollback-capable apply-patch call for the same run/step if available. |
| P2 | UI duplication | There are several overlapping workflow surfaces: `tool-plan`, `guided`, `patch-workflow`, `Guided Fix Workflow`, `Step Patch Tools`, and `Tool Calls`. | The system is powerful but mentally expensive; users may not know which tab is canonical. | Make `patch-workflow` the primary operator flow and demote `tool-plan`/`guided` to diagnostics, or add a compact "current workflow path" banner. |
| P2 | Bundle state continuity | `build_context_bundle` launcher fetches and summarizes the bundle but does not appear to update the shared `contextBundles` state used by the Guided tab. | User may build a bundle in one tab and not see it reflected in another until manually refreshed. | Add an optional callback that stores the returned bundle in `contextBundles`. |
| P2 | Proposal terminology | The form button says `Preview Patch`, but workflow actions talk about `create_proposal`. In this system, preview/proposal are tightly linked via `proposal_id`. | Users may wonder whether they have created a proposal or only previewed one. | Rename or label the button as `Create Proposal Preview` / `Preview & Save Proposal`. |
| P2 | Focus reliability | Focus uses custom events, timeouts, `document.querySelector`, and mount timing. It likely works, but it is brittle under slow render or deeply nested collapsed steps. | Occasional "target not found" even when a section exists. | Centralize focus state in React (`focusedStepId`, `focusedAnchor`) instead of event/timeouts, but keep scope small. |
| P3 | Visual feedback | The highlight animation is transient and there is no persistent "you are now here" marker on the destination block. | A user who blinks or scrolls late may miss what moved. | Add a short inline callout in the destination block for the focused manual action. |

## Safety observations

- No auto-apply found in the launcher path. `apply_patch_manual` and `apply_patch` only focus the manual patch section and show a confirmation message.
- No auto-run tests found in the launcher path. `run_tests_manual`, `run_tests`, and `run_command` focus `GuidedFixWorkflow`; they do not call `runProjectCommand`.
- No arbitrary shell runner was introduced by the reviewed UI. Existing command execution is still behind the safe command runner.
- No external provider calls are triggered by `patch-workflow` launcher/focus logic.
- Direct launcher actions are limited to read-only/context/draft endpoints:
  - `runStepAutoContext`
  - `getRunStepContextBundle`
  - `buildContextPatchDraft`
- Patch draft creation remains non-writing. It creates candidates and can prefill the form, but does not create/apply a patch.
- Manual-only actions are currently preserved as manual-only.

## Recommended next slice

**Workflow Continuity Hardening v1**

Small objective: make the existing workflow feel like one continuous path without changing backend behavior.

Acceptance criteria:

- `Use in Patch Form` from `create_patch_draft` switches to Timeline, opens the correct `StepPatchSection`, and highlights it.
- `analyze_result` focuses a failed `run-command` ToolCall when available; otherwise it focuses Tool Calls with a clear "no failed command found" message.
- `rollback_manual` focuses the latest rollback-capable `apply-patch` ToolCall when available.
- `review_patch` is not recommended before a draft/form data exists, or the UI explicitly tells the user to create/use a draft first.
- No backend changes, no auto-apply, no auto-run tests, no new endpoints.

## Files likely affected

- `frontend/src/pages/RunDetail.tsx`
- `README.md`
- Optional report only: `runs/workflow-continuity-hardening-v1/final-report.md`

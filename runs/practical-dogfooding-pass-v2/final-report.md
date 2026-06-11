# Practical Dogfooding Pass v2

## Summary

AI Workbench is now realistically usable for a small, manual documentation/UX task, as long as the operator understands that the system is a guided workbench rather than an autonomous agent runtime. The core path exists: `patch-workflow` can recommend the next action, read-only context can be gathered, a context bundle and patch draft can be produced, the draft can be moved into the Timeline patch form, review/proposal/apply remain manual, and Tool Calls can now surface older failed commands or rollback-capable apply calls.

The workflow is safe and auditable. The main remaining friction is product clarity: there are still multiple adjacent workflow surfaces (`patch-workflow`, `guided`, `Guided Fix Workflow`, `Step Patch Tools`, `Tool Calls`), and the operator sometimes needs to understand which one is the source of truth at the current moment.

## Baseline

- backend pytest: 258 passed
- scripts/run_tests.sh: passed
- frontend tsc/build: passed

## Scenario

Chosen scenario: a safe, small documentation task such as “add or update a short README/dogfooding notes section.” I did not apply a real patch during this pass. Instead, I performed a code-level/manual simulation against the current RunDetail implementation and verified that the existing UI and client calls can support the path without touching critical backend files.

This scenario is intentionally low risk:

- no `database.py`;
- no `engine.py`;
- no `routes.py` or `model_router.py`;
- no external providers;
- no automatic command execution;
- no automatic apply/rollback.

## Workflow result

| Step | Expected | Actual | Status | Notes |
|---|---|---|---|---|
| Open RunDetail | Operator can reach Timeline, Guided, Tool Plan, and Patch Workflow tabs. | RunDetail has all required tabs and state wiring. | Pass | The tab count is high, but the surfaces are present. |
| Open `patch-workflow` | See per-step stages and `recommended_next_action`. | `PatchWorkflowPanel` renders step workflow cards, stages, warnings, blockers, and next action. | Pass | Good high-level overview. |
| Launch `auto_gather_context` | Run bounded read-only context gathering only. | `WorkflowActionLauncher` calls `runStepAutoContext` with `max_tool_calls: 5`. | Pass | No patch/apply/test command involved. |
| Launch `build_context_bundle` | Build/read bundle without file changes. | Launcher calls `getRunStepContextBundle` and summarizes files/tool calls. | Pass with friction | It summarizes locally, but does not appear to sync the shared `contextBundles` state used elsewhere. |
| Launch `create_patch_draft` | Create draft candidates only, no proposal/apply. | Launcher calls `buildContextPatchDraft`, shows candidates, and offers `Use in Patch Form`. | Pass | This is the strongest bridge from context to manual editing. |
| Click `Use in Patch Form` | Move draft into the Timeline patch form and focus it. | Continuity hardening now calls manual focus for `create_proposal` after storing prefill. | Pass | This fixed the biggest v1 continuity problem. |
| Review patch | User can manually click Review Patch once `file_path`, `old_text`, and `new_text` exist. | Step Patch Tools has Review Patch button and review result panel. | Pass | Empty-form dead end is mitigated by better launcher message, but the form itself could still explain required fields more directly. |
| Create proposal/preview | User manually creates preview/proposal. | Step Patch Tools calls `proposeProjectPatch` only on button click. | Pass | No automatic proposal creation. |
| Manual apply | Apply requires explicit confirmation. | Step Patch Tools requires checkbox and calls `applyProjectPatch` only after user action. | Pass | Good safety posture. |
| Manual run tests | Tests are operator-triggered. | Guided Fix Workflow calls `runProjectCommand` only from `Run Tests` button. | Pass | No auto-run from workflow launcher. |
| Analyze failed result | Focus should find failed/timed-out command or help the user find it. | Tool Calls focus now filters `run-command` + failed/timed-out and can focus visible calls. | Pass | Much better after pagination/filter slice. |
| Rollback manual | Focus should find rollback-capable apply call when possible. | Tool Calls focus filters `apply-patch` and targets rollback-capable call if visible. | Pass | Still depends on rollback metadata existing. |
| Tool Calls history | Older relevant calls should be reachable. | Panel now defaults to 25, supports 50/load more, filters by tool/status/step. | Pass | Good enough for current local use. |

## What worked

- `patch-workflow` is becoming a credible operator cockpit.
- Safe read-only actions are clearly bounded and direct.
- Patch draft candidates provide a practical bridge into manual patch creation.
- `Use in Patch Form` now lands in the correct manual form instead of leaving the user stranded.
- Review/proposal/apply remain visibly separate steps.
- Tool Calls filters make analysis/rollback discovery far more practical.
- Safety boundaries held: no automatic apply, test execution, rollback, or external provider use.
- The current flow can support a small README/docs change without touching critical backend files.

## Friction / blockers

| Priority | Area | Problem | Impact | Suggested fix |
|---|---|---|---|---|
| P1 | Workflow surface clarity | There are still too many adjacent surfaces: `patch-workflow`, `guided`, `Guided Fix Workflow`, `Step Patch Tools`, `Tool Calls`. | A new user may not know which panel is canonical for “what do I do next?” | Make `patch-workflow` the primary cockpit and add a compact “Current step workflow” summary that links to the exact active block. |
| P1 | Context bundle sync | `build_context_bundle` in the launcher summarizes the bundle but does not obviously update the shared `contextBundles` UI state used by the Guided tab. | User can build context in one place but not see it reflected everywhere. | Pass a callback from RunDetail to store returned bundle in `contextBundles`. |
| P1 | Patch form guidance | The patch form has fields, but does not give enough inline guidance for `old_text` quality, uniqueness, or how to use draft text safely. | Documentation task is doable, but users may paste too little/too much text. | Add small inline guidance below `old_text` / `new_text` and surface “old_text must match exactly.” |
| P2 | Tool Calls filter scaling | Step filters show only the first 8 step ids from loaded tool calls. | On large runs, the relevant step may not be easy to filter manually. | Add a small text search for `step_id` or include the focused step even when outside the first 8. |
| P2 | Proposal terminology | UI mixes “Preview Patch”, “Create Proposal”, and `proposal_id`. | Operators may not know when a proposal was actually recorded. | Rename button to “Preview & Create Proposal” or add a one-line explanation near the button. |
| P2 | Parent step handling | Parent/orchestrator steps still do not have full patch/test anchors. | Launcher can explain the problem, but user still has to choose a child step manually. | In `patch-workflow`, mark parent steps as overview-only or link to first actionable child step. |
| P3 | Visual persistence | Focus highlight is temporary. | User can miss where the launcher sent them. | Add a short persistent destination callout for the last focused manual action. |

## Safety check

- no auto-apply: confirmed in reviewed flow;
- no auto-run tests: confirmed in reviewed flow;
- no auto-rollback: confirmed in reviewed flow;
- no shell runner: confirmed, only existing safe command runner is referenced;
- no external providers: confirmed, no launcher path invokes cloud providers;
- database.py untouched: confirmed for this pass.

## Recommended next slice

**Workflow Cockpit Clarity v1**

Single small goal: make `patch-workflow` feel like the primary operator cockpit without adding backend behavior.

Suggested acceptance criteria:

- Add a compact “Current actionable step” card at the top of `patch-workflow`.
- Show one canonical next action and one destination link per step.
- Add inline help in `StepPatchSection` for exact `old_text`, `new_text`, and proposal terminology.
- Keep all direct actions read-only and all dangerous actions manual-only.
- No backend changes.

## Files changed

Only this report was created:

- `runs/practical-dogfooding-pass-v2/final-report.md`

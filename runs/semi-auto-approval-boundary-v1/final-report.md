# Semi-auto Approval Boundary v1

## Summary

Formalized the frontend patch-workflow approval/execution boundary as a pure data-driven policy module.

This slice does not add autonomous execution. It does not add auto proposal, auto apply, auto tests, auto analyze, auto rollback, shell execution, or external provider execution.

## Policy matrix

| Action | Mode | Execution kind | Auto allowed | Confirmation | Notes |
| --- | --- | --- | --- | --- | --- |
| `auto_gather_context` | Manual | blocked | No | No | Manual mode disables direct execution. |
| `auto_gather_context` | Guided | direct_safe | Yes | No | Bounded context gathering only. |
| `auto_gather_context` | Safe Prep | direct_safe | Yes | No | Allowed as part of Safe Prep chain. |
| `build_context_bundle` | Manual | blocked | No | No | Manual mode disables direct execution. |
| `build_context_bundle` | Guided | direct_safe | Yes | No | Builds context bundle only. |
| `build_context_bundle` | Safe Prep | direct_safe | Yes | No | Allowed as part of Safe Prep chain. |
| `create_patch_draft` | Manual | blocked | No | No | Manual mode disables direct execution. |
| `create_patch_draft` | Guided | direct_safe | Yes | No | Draft-only; no proposal and no apply. |
| `create_patch_draft` | Safe Prep | direct_safe | Yes | No | Safe Prep stops after draft creation. |
| `review_patch` | All | manual_only | No | Manual click | Existing Step Patch Tools only. |
| `create_proposal` | All | manual_only | No | Manual click | Approval-gated proposal is future work. |
| `apply_patch_manual` | All | manual_only | No | `confirm=true` | No auto apply. |
| `run_tests_manual` | All | manual_only | No | Manual command action | No auto test loop. |
| `analyze_result` | All | manual_only | No | Manual click | No auto analyze. |
| `rollback_manual` | All | manual_only | No | `confirm=true` | No auto rollback. |
| `arbitrary_shell` | All | blocked | No | N/A | Outside current safe boundary. |
| `external_provider_execution` | All | blocked | No | N/A | Codex/Claude remain stub-only. |
| `auto_apply_patch` | All | blocked | No | N/A | Explicitly blocked. |
| `auto_run_command` | All | blocked | No | N/A | Explicitly blocked. |
| `auto_analyze_result` | All | blocked | No | N/A | Explicitly blocked. |
| `auto_rollback_patch` | All | blocked | No | N/A | Explicitly blocked. |
| `protected_file_write` | All | blocked | No | N/A | Explicitly blocked. |
| `secret_file_write` | All | blocked | No | N/A | Explicitly blocked. |

Compatibility aliases preserved as manual-only: `propose_patch`, `apply_patch`, `run_tests`, `run_command`, and `rollback_patch`.

Future-only placeholders were declared but are not executable in v1: approval-gated proposal, apply, tests, rollback, and external provider execution.

## Safety guarantees

- No auto proposal.
- No auto apply.
- No auto tests.
- No auto analyze.
- No auto rollback.
- No shell runner.
- No external provider execution.
- `database.py` untouched by this slice.
- Backend execution behavior unchanged.
- The only `canRunAutomatically=true` policy entries are:
  - `auto_gather_context`
  - `build_context_bundle`
  - `create_patch_draft`
- Those entries are only allowed in Guided and Safe Prep modes; Manual mode remains blocked.

## UI changes

The patch-workflow cockpit mode selector now exposes the boundary explicitly in its compact details block:

- Direct safe: auto context, context bundle, patch draft.
- Manual approval required: review, proposal, apply, tests, analyze, rollback.
- Blocked: shell, external providers, auto-apply, auto-tests, auto-analyze, auto-rollback.

No buttons, flows, API calls, or action launch behavior were added.

## Source changes

| File | Change |
| --- | --- |
| `frontend/src/components/run-detail/workflowActionPolicy.ts` | Added pure data-driven workflow boundary policy, action classification data, and automatic-run guard helper. |
| `frontend/src/pages/RunDetail.tsx` | Reused the policy module for action kind classification and cockpit boundary copy; preserved existing policy helper behavior. |
| `frontend/src/components/run-detail/PatchWorkflowPanel.tsx` | Added optional `policyTitle` prop for the compact selector details label. |
| `runs/semi-auto-approval-boundary-v1/final-report.md` | Added this report. |

## Tests

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | Pure policy module type-checks. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | Compile-only check; no edit to `database.py`. |
| `cd backend && .venv/bin/pytest -q` | Passed | 258 passed. |
| `cd . && bash scripts/run_tests.sh` | Passed | Backend syntax, pytest, and frontend TypeScript checks passed. |

Frontend has no dedicated unit-test framework configured in `package.json`; no new test framework was added. The policy is a pure TypeScript module and is covered here by `tsc --noEmit` and production build.

## Remaining gaps

- Approval-gated backend execution is not implemented.
- Real Codex/Claude provider execution is not implemented.
- Full autonomous mode is not implemented.
- Full patch/test/fix loop is not implemented.
- Backend workflow policy enforcement remains a future slice.

## Recommended next slice

Backend Workflow Policy Enforcement v1.

Suggested scope: add a backend pure policy/enforcement helper and tests so server-side workflow actions have the same explicit allow/manual/block classification, without adding endpoints that execute actions automatically.

# Module-aware Guard Policy v1

## Summary

Added a deterministic module-aware guard policy classification layer for patch proposal review. Proposal responses now include both bounded `module_awareness` and derived `module_policy` metadata so the operator can see whether a proposal is module-aligned, risky, or suspicious.

This is classification-only in v1. It does not replace existing `guard_result_id` validation, does not bypass guard policy, and does not add a new hard gate before proposal creation.

## Policy Model/Shape

Added `ModuleAwareGuardPolicyResult`:

- `verdict`: `allowed | warning | blocked`
- `reasons`
- `required_acknowledgements`
- `affected_modules`
- `sensitive_modules`
- `unknown_files`
- `recommended_tests`
- `confidence`

`ProposePatchResponse` now has optional `module_policy`.

## Policy Rules

The pure helper `evaluate_module_aware_guard_policy(...)` classifies:

- `allowed`: no active module map, or clean touched/expected module alignment with no unknown/sensitive/risky signals.
- `warning`: unknown module files, no expected modules, non-sensitive mismatch, module risks, or module-awareness warnings.
- `blocked`: suspicious unknown paths such as `.env`/secret/key/credentials, or sensitive module mismatch without matching expected requirement/module context.

Sensitive module signals include auth, security, database, migration/schema, env/secrets/config, provider/runtime/execution.

All output lists are capped and operator-readable.

## Enforcement Status

Blocked verdict is classification-only in v1.

Existing hard gates remain unchanged:

- invalid/stale/blocked guard result still blocks proposal creation.
- missing guard on step-linked proposal still requires explicit `no_guard_override=true`.
- apply still requires `confirm=true`.

Module policy does not authorize proposal/apply and does not block proposal creation by itself yet.

## Proposal Endpoint Behavior

`POST /api/projects/{project_id}/tools/propose-patch` now:

- runs existing guard validation first.
- creates the normal proposal preview/tool_call only when existing validation succeeds.
- computes `module_awareness`.
- derives `module_policy`.
- stores both in the response and proposal tool_call output.

Validation failures still create no proposal tool_call.

## Frontend Display

RunDetail proposal preview now shows a compact read-only Module Policy block:

- verdict
- confidence
- reasons
- required acknowledgements
- recommended tests

No new action buttons, automatic execution, scan, save, provider call, apply, or proposal automation were added.

## Tests Added

Added `backend/tests/test_module_aware_guard_policy.py`.

Coverage includes:

- neutral/allowed policy without active module map.
- allowed policy for matching touched/expected modules.
- warnings for unknown files and non-sensitive mismatches.
- blocked classification for auth/database mismatches.
- blocked classification for suspicious unknown paths.
- sensitive module with matching requirement is not blocked.
- risks become warning reasons.
- module test hints become recommended tests.
- capped policy output.
- no file-content leakage.
- unchanged guard validation, no-guard override, proposal creation, and apply confirm behavior.
- module policy stored in proposal tool_call output.
- static safety scan for policy helper.

## Safety Boundaries

- No DB schema changes.
- No migrations.
- No database.py edits.
- No engine.py edits.
- No provider/provider-client edits or calls.
- No project_tools/model_router edits.
- No file content reads in the policy helper.
- No subprocess/shell execution.
- No `execute_run`.
- No `asyncio.create_task`.
- No auto-proposal.
- No auto-apply.
- No auto-rollback.
- No guard bypass.
- No approval bypass.
- `old_text` / `new_text` remain manually supplied.

## Files Changed

- `backend/src/models.py`
- `backend/src/storage/module_map_storage.py`
- `backend/src/api/routes.py`
- `backend/tests/test_module_aware_guard_policy.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/module-aware-guard-policy-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice.
- `backend/src/orchestrator/engine.py`: not touched by this slice.
- Providers/provider clients: not touched by this slice.

Note: the working tree already contains unrelated dirty files from previous accepted slices; this report reflects this slice's changes only.

## Exact Check Results

- `py_compile` for `database.py`, `models.py`, `module_map_storage.py`, `routes.py`, and new test: passed.
- `pytest -q tests/test_module_aware_guard_policy.py`: 19 passed.
- `pytest -q tests/test_guard_proposal_module_awareness.py`: 18 passed.
- `pytest -q tests/test_guarded_patch_proposal.py`: 17 passed.
- `pytest -q tests/test_guard_result_proposal_validation.py`: 17 passed.
- `pytest -q tests/test_apply_guard_revalidation.py`: 11 passed.
- `pytest -q tests/test_module_map_patch_draft_context.py`: 26 passed.
- `pytest -q tests/test_agent_result_patch_draft_bridge.py`: 36 passed.
- `pytest -q tests/test_module_map_agent_context_wiring.py`: 30 passed.
- `pytest -q tests/test_project_module_map.py`: 41 passed.
- `pytest -q tests/test_agent_execution_harness.py`: 46 passed.
- Remaining targeted workflow compatibility suites: passed.
- Full backend pytest: 1131 passed, 38 subtests passed.
- Frontend `npx tsc --noEmit`: passed.
- Frontend `npm run build`: passed.
- `bash scripts/run_tests.sh`: passed; backend 1131 passed, 38 subtests passed; frontend TypeScript check passed.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: none.
- P3: policy is classification-only and heuristic in v1.

## Known Limitations

- Module policy is classification-only in v1.
- Matching is heuristic only.
- No file content analysis.
- No provider/LLM classification.
- No visual module policy editor.
- Module policy does not yet affect apply authorization.

## Recommended Next Slice

Module-aware Guard Policy Regression Pass.

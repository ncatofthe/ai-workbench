# Step -> Agent Patch Draft Fastlane v1

## Summary

Implemented a draft-only bridge from agent-ready intake steps to bounded patch draft candidates.

Operators can now inspect Agent Step Context in RunDetail, click **Prepare Patch Draft**, and receive a bounded candidate containing target file hints, patch intent, draft summary, requirement/module links, risks, validation steps, blockers/warnings, and the next recommended operator action.

No patch is applied. No proposal is created automatically. No tests are run. No provider call is made.

## Why This Fastlane Block Exists

The current pipeline can create real pending runs and real pending steps from intake. The previous slice made those steps agent-ready by surfacing canonical agent assignment and bounded context. This slice moves one notch deeper into executor readiness by preparing a patch draft candidate, while preserving the manual guard/proposal/apply workflow.

## Backend Draft Builder Behavior

Added `StepAgentPatchDraftRequest`, `StepAgentPatchDraftResponse`, and `build_step_agent_patch_draft(...)` in `backend/src/orchestrator/project_intake.py`.

The builder:

- Parses normalized development-run step context.
- Preserves canonical agent ID.
- Preserves requirement IDs and module IDs.
- Preserves validation/safety context.
- Infers target file hints from role/module metadata and optional agent result file hints only.
- Does not scan the repository.
- Does not read file contents.
- Redacts secret-like input from operator notes or agent result fields.
- Leaves `suggested_old_text` empty when file content was not read.
- Produces a `suggested_new_text` placeholder and patch intent for manual review.
- Blocks readiness when the step is non-pending or `provider_allowed=true`.
- Warns for database/schema, auth/security, missing exact old_text, and manual approval situations.

## Endpoint Behavior

Added:

- `POST /api/runs/{run_id}/steps/{step_id}/agent-patch-draft`

The endpoint:

- Verifies the run exists.
- Verifies the step belongs to the run.
- Reads existing step context.
- Returns a bounded `StepAgentPatchDraftResponse`.
- Creates no records.
- Creates no tool calls.
- Creates no patch proposal.
- Applies no patch.
- Calls no providers.
- Reads no files.
- Runs no commands.
- Is deterministic for the same input.

## RunDetail UI Behavior

Updated the `Agent Context` tab in `frontend/src/pages/RunDetail.tsx`.

Each Agent Step Context item now includes:

- Optional operator note for narrowing.
- **Prepare Patch Draft** button.
- Draft-only result panel.
- Target files.
- Patch intent.
- Draft summary.
- Suggested old/new text fields.
- Risks.
- Validation steps.
- Blockers/warnings.
- Next recommended action.
- **Use in Patch Proposal Form** prefill action.

The prefill action only fills the existing patch form context and suggested file path. It does not submit a proposal, apply a patch, call a provider, or run tests.

## Target File Inference Behavior

Target inference is metadata-only:

- Backend roles/modules suggest `backend/src/...` path hints.
- Frontend roles/modules suggest `frontend/src/...` path hints.
- QA roles/modules suggest `tests/...` path hints.
- Database/schema work adds manual approval warnings.
- Security work asks for operator narrowing when no agent result or note narrows the target.
- Unsafe paths are skipped.

The system does not claim exact file contents or exact patch locations without later operator review.

## Safety Boundaries

Verified:

- No automatic `execute_run`.
- No `asyncio.create_task`.
- No provider calls.
- No network calls.
- No automatic `create_tool_call`.
- No project/run/run-step creation.
- No patch proposal creation.
- No apply patch.
- No command execution.
- No test execution.
- No runtime file reads.
- No DB schema changes.
- No migrations.
- No safety gate weakening.

## Tests Added

Added `backend/tests/test_step_agent_patch_draft_fastlane.py`.

Coverage:

- Builder behavior for backend, frontend, and QA steps.
- Requirement/module/canonical agent preservation.
- Provider and non-pending blockers.
- Missing/malformed context fallback.
- Output bounding.
- Empty `old_text` behavior without file reads.
- Target file inference.
- Database/security/manual approval warnings.
- Endpoint 200/404 behavior.
- No tool calls, proposals, applies, providers, file reads, or commands.
- Determinism.
- Agent result summary, bounds, secret redaction, and operator note behavior.
- RunDetail static UI safety.
- Static safety scans.
- Compatibility anchors.

Result: `58 passed`.

## Files Changed

- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_step_agent_patch_draft_fastlane.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/step-agent-patch-draft-fastlane-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched by this slice.
- `backend/src/orchestrator/engine.py`: not touched by this slice.
- `backend/src/providers/*`: not touched by this slice.

## Exact Check Results

Backend syntax:

- `python -m py_compile src/orchestrator/project_intake.py`: passed.
- `python -m py_compile src/api/routes.py`: passed.
- `python -m py_compile src/models.py`: passed.
- `python -m py_compile tests/test_step_agent_patch_draft_fastlane.py`: passed.

Backend tests:

- `pytest -q tests/test_step_agent_patch_draft_fastlane.py`: `58 passed`.
- Targeted compatibility bundle:
  - `tests/test_intake_run_agent_assignment_step_context.py`
  - `tests/test_agent_execution_harness.py`
  - `tests/test_agent_result_patch_draft_bridge.py`
  - `tests/test_guarded_patch_proposal.py`
  - `tests/test_apply_guard_revalidation.py`
  - `tests/test_project_context_cockpit.py`
  - `tests/test_semi_auto_operator_queue.py`
  - result: `206 passed`.
- Full backend pytest: `2059 passed, 38 subtests passed`.

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run test:e2e:smoke`: `2 passed`.

Root:

- `bash scripts/run_tests.sh`: passed.
  - backend pytest: `2059 passed, 38 subtests passed`
  - frontend TypeScript check: passed

## P0/P1/P2/P3 Issues

- P0: none found.
- P1: none found.
- P2: none introduced. Exact `old_text` still requires operator review or future read-only context gathering.
- P3: none noted.

## Known Limitations

- No patch is applied.
- No proposal is auto-created.
- No provider call is triggered by the draft button.
- No tests are run.
- Exact `old_text` requires operator review or future read-only context gathering.
- Target files are hints, not verified repository paths.
- No full autonomous patch/test/fix loop yet.

## Recommended Next Slice

Recommended next slice: **Step Patch Draft -> Guarded Proposal Fastlane v1**.

That should convert a reviewed draft into an explicit operator-controlled guarded proposal path while keeping proposal creation manual and guard-gated.

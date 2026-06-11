# Real Project End-to-End Delivery Dogfood v1

## Summary

Added a deterministic backend dogfood suite for a realistic SaaS work-management project and verified the current AI Workbench operator workflow end to end without changing runtime behavior.

The dogfood pass validates that Source of Truth, Project Module Map, confirmed-run context, agent execution context, patch draft context, guarded proposal module awareness, module-aware policy classification, delivery report module awareness, and Project Context Cockpit all connect coherently under human supervision.

No enforcement, automation, provider calls, apply behavior, schema, or protected runtime files were changed.

## Realistic SaaS Scenario

Product: Acme Work Management, an internal SaaS task manager for operations, finance reviewers, and task owners.

Source of Truth requirements:

- `REQ-AUTH-001`: role-based task access
- `REQ-REVIEW-001`: review approval before payment
- `REQ-UPLOAD-001`: scoped upload access
- `REQ-DELIVERY-001`: delivery readiness reporting

Module Map modules:

- Auth
- Reviews
- Finance Reports
- Uploads
- Frontend UI
- Database
- Shared Contracts

The scenario intentionally includes a sensitive auth-file proposal against a review/payment requirement to verify that module policy classification is visible but not enforced as a hard gate.

## Tests Added

Created `backend/tests/test_real_project_end_to_end_delivery_dogfood.py` with 45 tests covering:

- project context setup
- active Source of Truth and Module Map
- confirmed-run SoT context
- parseable requirement context
- agent execution context module hints
- dry-run prompt module-map section
- provider mode requiring `allow_provider_call`
- patch draft module context
- manual/empty old/new text behavior
- guarded proposal module awareness
- module policy classification
- validation failure creates no proposal tool call
- delivery module summary and markdown
- Project Context Cockpit summaries and next action
- static/runtime safety boundaries
- compatibility imports for existing dogfood and workflow suites

## Context Flow Results

Context flowed correctly from project setup through confirmed-run step input, agent context, patch draft, guarded proposal metadata, delivery reporting, and cockpit summaries.

The confirmed-run path carried `AI_WORKBENCH_REQUIREMENT_CONTEXT` into step input, and the parser recovered the expected requirement ID for review/payment workflow coverage.

## Source of Truth Results

The active Source of Truth was present, versioned, and accessible through existing project APIs. Requirements, constraints, risks, acceptance criteria, and open questions were available for downstream context.

No raw Source of Truth dump was required by the dogfood flow.

## Module Map Results

The active Module Map was present and matched modules by requirement ID, proposed file path, and keyword-derived context. Review requirements selected the Reviews module; auth path proposals selected Auth as a touched sensitive module.

No file contents were read by module-context/reporting paths.

## Agent Context Results

`GET /api/runs/{run_id}/steps/{step_id}/agent-execution-context` returned module context for the active project map and created no tool calls.

Dry-run agent execution included `PROJECT MODULE MAP CONTEXT` in the prompt preview while still requiring explicit provider permission for provider mode.

## Patch Draft Results

`POST /api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft` returned structured module context, recommended module-map files, and a bounded `PROJECT MODULE MAP PATCH CONTEXT` section.

`old_text` and `new_text` remain intentionally manual and absent from the response model.

The patch draft endpoint created no proposal, apply, run-command, or provider activity.

## Guard/Proposal Results

Guarded proposal creation returned module awareness and module policy metadata after existing guard validation passed.

A blocked guard validation failure returned an error and created no proposal tool call.

Sensitive module mismatch produced warning/blocked classification data, while the proposal still followed existing guard validation rules.

## Module Policy Results

Module policy remains classification-only in this dogfood pass.

The operator can see risky/sensitive module classification, affected modules, sensitive modules, reasons, and recommended tests. The blocked verdict did not become a hard gate and did not replace `guard_result_id` validation.

## Delivery Report Results

Delivery summary included `module_summary` with touched modules, warnings, blocked policy counts, and recommended module-level tests.

Delivery markdown included `## Module Awareness`.

Readiness did not become blocked solely because module policy classification reported warning/blocked module risk.

## Project Cockpit Results

`GET /api/runs/{run_id}/project-context-cockpit` returned Source of Truth, Module Map, run status, module awareness, and next safest action.

The next action remained display-only and created no tool calls.

## Operator Friction Found

- The workflow is coherent, but still requires deliberate manual movement between context, patch draft, guard/proposal, delivery, and cockpit panels.
- Module policy is visible but not yet enforceable; this is correct for the current slice but leaves sensitive mismatches dependent on operator judgment.
- Patch draft still requires manual `old_text`/`new_text`, which preserves safety but remains an operator-speed bottleneck.
- No visual module map editor or cross-run historical analytics exist yet.

## Safety Boundaries

Verified:

- no `execute_run`
- no `asyncio.create_task`
- no subprocess or shell command execution from dogfood read-only paths
- no provider calls
- no file content reads from patch draft/cockpit/reporting paths
- no auto-proposal
- no auto-apply
- no auto-rollback
- no guard bypass
- no approval bypass
- no DB schema changes
- no protected runtime files changed

Existing explicit proposal endpoint behavior was used only where the dogfood flow required a guarded proposal tool call.

## Files Changed

- `backend/tests/test_real_project_end_to_end_delivery_dogfood.py`
- `runs/real-project-end-to-end-delivery-dogfood-v1/final-report.md`

## Protected Files

- `backend/src/storage/database.py`: not touched
- `backend/src/orchestrator/engine.py`: not touched
- providers/provider clients: not touched
- `backend/src/project_tools.py`: not touched
- `backend/src/model_router.py`: not touched

## Exact Check Results

Backend targeted compile:

- `src/storage/database.py`: passed
- `src/models.py`: passed
- `src/api/routes.py`: passed
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: passed

Targeted dogfood:

- `tests/test_real_project_end_to_end_delivery_dogfood.py`: 45 passed

Targeted related suite:

- 555 passed

Full backend:

- 1227 passed + 38 subtests

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed

Full runner:

- `bash scripts/run_tests.sh`: passed
- backend inside runner: 1227 passed + 38 subtests
- frontend TypeScript check inside runner: passed

## P0/P1/P2/P3 Issues

- P0: none
- P1: none
- P2: none
- P3: none

Known limitations are tracked below rather than counted as regressions.

## Readiness Ratings

- Small/medium task readiness: high under human supervision.
- SaaS module readiness under human supervision: medium-high.
- Near-autonomous end-to-end readiness: low by design; automation/enforcement remains intentionally constrained.
- Commercial polished product readiness: medium; the workflow is technically coherent, but UX continuity, module-map editing, and enforcement policy still need product hardening.

## Gaps Before Hard Enforcement

- Decide whether module-policy `blocked` should become a real proposal/apply gate.
- Define acknowledgement/override semantics for module-policy blocking.
- Add regression coverage before any hard enforcement change.
- Improve operator UX for moving from module warning to next safe action.
- Consider visual Module Map editing and historical module-risk analytics.

## Recommendation

Proceed with **Real Project End-to-End Delivery Dogfood Regression Pass** first to lock this end-to-end scenario, then consider **Module-aware Guard Policy Enforcement v1** if the product decision is to turn classification into a real gate.

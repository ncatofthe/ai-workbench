# External Review Synthesis

Date: 2026-05-18
Scope: synthesis of read-only external architecture review

## Consensus

The external review strongly agrees with the initial repository analysis:

- The orchestrator is currently planning-only.
- `project_id` is accepted by the API but not used as real project context.
- The safety layer exists but is not the central execution gate.
- Provider adapters need a shared contract.
- Run state is too flat for delegated execution.
- Stop only updates DB status and does not cancel the background task.
- Agent definitions are hardcoded in Python.
- Tools are tied to the AI Workbench repository root rather than a selected project.
- The UI is not yet an operator console.
- `scripts/run_tests.sh` masks failures.

## Decision

The next implementation track should be **Project Profiles first**.

Reason:

Without project profiles, every future feature remains tied to the AI Workbench repository itself. Project profiles are the base needed for workspace status, tests, builds, safe commands, blocked commands, run context, and later delegated execution.

## Next Agent Task

Ask a specialist agent to design the Project Profiles implementation in read-only mode before source changes begin.

Expected output:

- exact backend model/storage/API changes;
- exact frontend UI changes;
- migration strategy for existing SQLite database;
- path safety rules;
- test plan;
- small implementation order.

This should be the final analysis step before coding Phase 1.

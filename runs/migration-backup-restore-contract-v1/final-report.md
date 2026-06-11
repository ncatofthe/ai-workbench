# Migration / Backup / Restore Contract v1

## Summary

Created a pure Migration / Backup / Restore Contract v1 for AI Workbench.

This slice defines and tests release-readiness expectations for backup manifests, restore preflight decisions, redaction boundaries, and operator checklists. It does not implement executable backup/restore tooling, does not alter database schema, does not add endpoints, and does not change runtime behavior.

## Why This Slice Exists

The Production Hardening / Release Readiness Audit identified the lack of a formal migration/backup/restore process as a P1 release blocker. This contract is the first safe foundation step: it specifies what future implementation must preserve before any DB copy/restore tooling exists.

## Contract Module

Created:

- `backend/src/release/migration_backup_restore_contract.py`

The module is pure Python/Pydantic contract logic. It does not import database/runtime/provider modules and does not read/write files.

## Backup Manifest Domains

The default manifest defines these backup domains:

- `database`: required, included by default, sensitive
- `project_metadata`: required, included by default, internal
- `source_of_truth`: required, included by default, internal
- `module_map`: required, included by default, internal
- `guard_results`: required, included by default, sensitive
- `approvals`: required, included by default, sensitive
- `tool_calls`: required, included by default, sensitive
- `run_artifacts`: optional but included by default with operator review
- `settings`: optional, included by default, redaction required
- `provider_secrets`: excluded by default, secret, redaction required
- `external_project_files`: excluded by default, sensitive, explicit confirmation required

## Restore Preflight Rules

Restore preflight is contract-only and returns structured status, risk, blockers, warnings, and required confirmations.

Rules:

- Block if backup database is missing.
- Block if required backup domains are missing.
- Block if backup schema version is newer than current app schema.
- Block overwrite unless `allow_overwrite=true`.
- Warn if backup schema is older than current schema.
- Warn and require confirmation when provider secrets are present.
- Warn and require confirmation when external project files are present.
- Require operator confirmation for overwrite and sensitive artifact restore.

## Redaction / Secret Rules

Provider secrets are excluded by default and cannot be included without redaction. Settings are treated as sensitive and redacted in report manifests. External project files are excluded by default and require explicit operator confirmation if future tooling includes them.

`redact_manifest_for_report(...)` removes path hints for secret/redaction-required manifest items before report display.

## Operator Checklist Summary

Backup checklist includes:

- stop app or ensure no writes
- copy SQLite database
- export and verify manifest schema version
- review run artifacts
- exclude/redact provider secrets
- exclude external project files unless explicitly requested
- verify backup can be listed/checksummed

Restore checklist includes:

- back up current state first
- verify schema compatibility
- confirm overwrite
- review provider secrets
- review external project file paths
- validate projects, runs, guards, approvals, and delivery reports after restore

## Tests Added

Created:

- `backend/tests/test_migration_backup_restore_contract.py`

Coverage:

- default manifest contents
- default exclusions
- sensitivity classification
- manifest validation blockers/warnings
- restore preflight blockers/warnings/confirmations
- operator checklist contents
- static purity/safety checks
- import side-effect check
- helper export compatibility

The new test file contains 41 tests.

## Files Changed

Added:

- `backend/src/release/migration_backup_restore_contract.py`
- `backend/tests/test_migration_backup_restore_contract.py`
- `runs/migration-backup-restore-contract-v1/final-report.md`

No existing source files were modified.

## Protected Files

- `backend/src/storage/database.py`: not touched
- `backend/src/orchestrator/engine.py`: not touched
- providers/provider clients: not touched
- `backend/src/project_tools.py`: not touched
- `backend/src/model_router.py`: not touched

## Exact Checks / Results

Python compile:

- `src/release/migration_backup_restore_contract.py`: passed
- `tests/test_migration_backup_restore_contract.py`: passed
- `src/storage/database.py`: passed
- `src/models.py`: passed
- `src/api/routes.py`: passed

Targeted tests:

- `tests/test_migration_backup_restore_contract.py`: 41 passed
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: 45 passed
- `tests/test_project_context_cockpit.py`: 26 passed
- `tests/test_delivery_report_module_awareness.py`: 20 passed
- `tests/test_module_aware_guard_policy.py`: 19 passed
- `tests/test_project_module_map.py`: 41 passed
- `tests/test_persistent_source_of_truth.py`: 31 passed

Full backend:

- `1268 passed + 38 subtests`

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed

Full runner:

- `bash scripts/run_tests.sh`: passed
- backend inside runner: `1268 passed + 38 subtests`
- frontend TypeScript check inside runner: passed

## P0/P1/P2/P3 Issues

- P0: none
- P1: none introduced or found in this slice
- P2: executable backup/restore, migration runner, retention policy, browser E2E, and auth/RBAC remain open release-readiness gaps
- P3: no CLI/UI checklist surface yet

## Known Limitations

- Contract only, no executable backup CLI yet.
- No real DB export/import yet.
- No migration runner yet.
- No retention policy implementation yet.
- No browser E2E yet.
- No multi-user auth/RBAC yet.
- No backup encryption/compression/checksum implementation yet.

## Next Recommended Slice

Recommended: **Migration / Backup / Restore Contract Regression Pass**.

Alternative release-readiness slice: **Release Readiness Hardening Fixes v2: Browser E2E Smoke Foundation**.

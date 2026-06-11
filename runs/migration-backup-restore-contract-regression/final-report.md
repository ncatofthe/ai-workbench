# Migration / Backup / Restore Contract Regression Pass

## Summary

Regression pass completed for the pure Migration / Backup / Restore Contract v1.

Result: clean. No P0/P1/P2/P3 regression issues were found. The contract remains a specification/test foundation only; no executable backup or restore behavior was added.

## Contract Module Purity Validation

Validated `backend/src/release/migration_backup_restore_contract.py`.

- Pure Python/Pydantic contract module only.
- No database imports.
- No DB connections.
- No API route imports.
- No provider imports or provider calls.
- No filesystem read/write helpers.
- No subprocess or shell execution.
- No `execute_run`.
- No `asyncio.create_task`.
- No `create_tool_call`.
- No import-time runtime side effects.
- No mutable global runtime state beyond static schema/version constants and enum/model definitions.

## Backup Manifest Validation

Validated default manifest behavior.

- Includes required database item.
- Includes Source of Truth domain.
- Includes Module Map domain.
- Includes guard results domain.
- Includes approvals domain.
- Includes tool calls domain.
- Provider secrets are excluded by default.
- External project files are excluded by default.
- Run artifacts are included with explicit operator review.
- `schema_version` is present.
- Manifest objects are deterministic and JSON-serializable through Pydantic models.

## Sensitivity / Redaction Validation

Validated sensitivity classification and report-safe redaction.

- Provider secrets classify as `secret`.
- External project files classify as `sensitive`.
- Database classifies as `sensitive`.
- Source of Truth and Module Map classify as internal context.
- Guard results, approvals, and tool calls classify as sensitive audit data.
- Redaction removes secret/redaction-required path hints.
- Redaction preserves required non-secret metadata.

## Restore Preflight Validation

Validated deterministic restore preflight rules.

- Missing backup database blocks restore.
- Newer backup schema blocks restore.
- Invalid schema versions block restore.
- Overwrite without `allow_overwrite=true` blocks restore.
- Provider secrets produce warnings and explicit confirmations.
- External project files produce warnings and explicit confirmations.
- Same-version restore is allowed when required inputs are present and overwrite is explicit.
- Older backup schema is allowed with a migration-compatibility warning.
- Preflight does not restore data, access the filesystem, or connect to the database.

## Operator Checklist Validation

Validated checklist coverage.

- Backup checklist mentions stopping/quiescing the app.
- Backup checklist mentions copying the AI Workbench SQLite database.
- Backup checklist mentions verifying `schema_version`.
- Backup checklist mentions reviewing artifacts and excluding/redacting secrets.
- Restore checklist mentions backing up current state first.
- Restore checklist mentions schema compatibility.
- Restore checklist mentions provider secrets.
- Restore checklist mentions validation after restore.

## Test Quality Validation

Validated `backend/tests/test_migration_backup_restore_contract.py`.

- Tests cover manifest domains and defaults.
- Tests cover sensitivity and redaction behavior.
- Tests cover manifest validation blockers/warnings.
- Tests cover restore preflight blockers/warnings/confirmations.
- Tests cover operator checklists.
- Tests include static safety checks for forbidden runtime behavior.
- Tests do not require external files.
- Tests do not mutate real runtime state.
- Tests are deterministic.

## Runtime Compatibility Validation

The contract module does not affect application startup or runtime behavior.

- No endpoints were added.
- No CLI was added.
- No DB schema or migration behavior changed.
- No runtime storage module behavior changed.
- No frontend behavior changed.
- Existing backend and frontend checks remain green.

## Static Safety Validation

Static safety was validated through inspection and tests for:

- No `execute_run`.
- No `asyncio.create_task`.
- No `subprocess`.
- No `os.system`.
- No `os.popen`.
- No provider calls.
- No `ollama.chat_completion`.
- No Claude/Codex provider call.
- No `create_tool_call`.
- No `open()`.
- No `.read_text()`.
- No `.read()`.
- No `.write_text()`.
- No DB import/connection from `database.py`.
- No route registration.
- No migration/DDL execution.

## P0/P1/P2/P3 Issues Found

- P0: none.
- P1: none.
- P2: none found in this regression pass.
- P3: none found in this regression pass.

## Changes Made

Report only:

- Added `runs/migration-backup-restore-contract-regression/final-report.md`.

No contract, test, backend runtime, frontend, database, engine, provider, or project tool source files were modified in this regression pass.

## Exact Checks / Results

Backend compile checks:

- `.venv/bin/python -m py_compile src/release/migration_backup_restore_contract.py` passed.
- `.venv/bin/python -m py_compile tests/test_migration_backup_restore_contract.py` passed.
- `.venv/bin/python -m py_compile src/storage/database.py` passed.
- `.venv/bin/python -m py_compile src/models.py` passed.
- `.venv/bin/python -m py_compile src/api/routes.py` passed.

Backend targeted tests:

- `.venv/bin/pytest -q tests/test_migration_backup_restore_contract.py`: `41 passed in 0.07s`.
- `.venv/bin/pytest -q tests/test_real_project_end_to_end_delivery_dogfood.py`: `45 passed`.
- `.venv/bin/pytest -q tests/test_project_context_cockpit.py`: `26 passed`.
- `.venv/bin/pytest -q tests/test_delivery_report_module_awareness.py`: `20 passed`.
- `.venv/bin/pytest -q tests/test_module_aware_guard_policy.py`: `19 passed`.
- `.venv/bin/pytest -q tests/test_project_module_map.py`: `41 passed`.
- `.venv/bin/pytest -q tests/test_persistent_source_of_truth.py`: `31 passed`.

Full backend:

- `.venv/bin/pytest -q`: `1268 passed, 38 subtests passed in 17.75s`.

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.

Project test runner:

- `bash scripts/run_tests.sh`: passed.
- Runner backend result: `1268 passed, 38 subtests passed in 17.56s`.
- Runner frontend TypeScript check: passed.

## Protected File Status

- `backend/src/storage/database.py` touched by this pass: no.
- `backend/src/orchestrator/engine.py` touched by this pass: no.
- Providers touched by this pass: no.
- `backend/src/project_tools.py` touched by this pass: no.
- `backend/src/model_router.py` touched by this pass: no.
- Frontend touched by this pass: no.

Note: repository worktree already had pre-existing dirty/untracked state from earlier slices; this pass did not reset, revert, clean, or modify unrelated files.

## Known Limitations

- Contract only; no executable backup CLI yet.
- No real DB export/import yet.
- No migration runner yet.
- No retention policy implementation yet.
- No browser E2E foundation yet.
- No multi-user auth/RBAC yet.

## Recommended Next Slice

Recommended next slice: Browser E2E Smoke Foundation v1.

Rationale: the backup/restore contract is stable as a spec foundation, while release readiness still lacks browser-level smoke coverage for critical operator flows.

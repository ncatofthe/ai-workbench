# Provider Integration Hardening Contract v1

## Summary

Created a pure Provider Integration Hardening Contract v1 for AI Workbench.

This slice defines deterministic safety expectations for local, mock, dry-run, and external provider integration without changing runtime provider behavior. No provider calls were made. No endpoints, database schema, migrations, provider adapters, runtime orchestration, frontend behavior, guard behavior, or approval behavior were changed.

## Why This Slice Exists

The release readiness audit identified provider integration hardening as a production-readiness gap. AI Workbench is offline-first, not offline-only, so provider integrations need explicit contracts for:

- local Ollama use,
- Codex and Claude external-provider boundaries,
- mock and dry-run safety,
- prompt/context boundaries,
- provider-key handling,
- timeout/error/retry expectations,
- audit/logging and redaction rules,
- read-only endpoint restrictions.

This contract creates the testable specification for future runtime hardening while keeping the current product behavior unchanged.

## Provider Kinds / Modes

Defined `ProviderKind`:

- `ollama`
- `codex`
- `claude`
- `mock`
- `future_external`

Defined `ProviderExecutionMode`:

- `disabled`
- `mock`
- `dry_run`
- `local`
- `external`

Mode behavior:

- `disabled`: provider execution denied.
- `mock`: deterministic test path; no real provider contact.
- `dry_run`: prompt building/preview intent only; no provider call.
- `local`: local Ollama-style provider, still requiring explicit `allow_provider_call`.
- `external`: high-risk provider path requiring explicit allow, provider key presence, redaction boundary, and audit log.

## Provider Capability Matrix

Added `build_default_provider_capabilities()`.

Validated capability expectations:

- Ollama is local and does not require external network access.
- Codex and Claude are marked as external-network and remote-data-risk providers.
- Mock provider has no external network requirement.
- Future external providers are considered high-risk placeholders until explicitly specified.
- Timeout and cancellation support are captured as contract metadata.

## Provider Action Risk Classification

Added `classify_provider_action(...)`.

Important classifications:

- `build_prompt`: medium risk; may expose bounded project context; requires redaction.
- `preview_prompt`: low risk; read-only operator inspection.
- `call_provider`: high risk; requires explicit allow, redaction, and audit log.
- `store_provider_result`: medium risk; requires audit/redaction.
- `retry_provider_call`: high risk; must be bounded.
- `cancel_provider_call`: medium risk; should leave safe reportable state.
- `configure_provider_key`: critical secret-sensitive action.
- `inspect_provider_status`: low risk and must not send project context.

## Prompt Boundary Rules

Added `ProviderPromptBoundary`, `build_default_prompt_boundary()`, and `validate_provider_prompt_boundary(...)`.

Default boundary:

- Source of Truth allowed only as bounded context.
- Module Map allowed only as bounded context.
- File contents excluded by default.
- Provider keys excluded.
- Secrets excluded.
- Raw full project dumps forbidden.
- Redaction required.

Validation blocks:

- provider keys in prompts,
- secrets in prompts,
- raw full project dumps,
- missing redaction requirement,
- invalid zero/negative context-section limits.

Validation warns:

- large context-section counts,
- file contents requiring explicit future file-read permission and review.

## Provider Key Handling Rules

Added `ProviderKeyHandlingRule` and `build_provider_key_handling_rules()`.

Rules:

- Provider keys classify as `secret`.
- Keys are excluded from backups by default.
- Keys must not be displayed in UI.
- Keys must not appear in tool call output.
- Keys must not appear in audit payloads.
- Keys must not be included in provider prompts.
- Production requires environment/secret-manager style storage.

These rules align with the Auth/RBAC/Deployment Security Model Contract and Migration / Backup / Restore Contract.

## Execution Policy Rules

Added `ProviderExecutionPolicy` and `evaluate_provider_execution_policy(...)`.

Validated behavior:

- Disabled mode denies provider calls.
- Mock mode allows deterministic no-provider execution only.
- Dry-run mode allows prompt preview intent but denies provider calls.
- Local mode supports Ollama-style local provider and requires `allow_provider_call`.
- Local mode rejects external provider kinds.
- External mode requires `allow_provider_call`, provider key presence, redaction boundary, and audit log.
- External mode without provider key is denied.
- `allow_provider_call=false` blocks external provider execution.

Policy lists read-only endpoint families that must remain provider-forbidden.

## Error / Timeout / Retry Rules

Added `ProviderErrorHandlingContract` and `build_provider_error_handling_contract()`.

Rules:

- Provider timeouts are bounded.
- Retry count is bounded.
- Provider unavailable state must fail safely.
- Provider unavailable must not authorize apply.
- Provider errors must not bypass guard or approval checks.
- Provider cancellation must be recorded as safe/reportable state when supported.
- Retry attempts must reuse the same prompt boundary and redaction requirements.

## Read-Only Endpoint Provider Restrictions

The contract lists read-only or context/report endpoint families that must not call providers:

- `agent-execution-context`
- `project-context-cockpit`
- `delivery-summary`
- `delivery-report`
- `source-of-truth-preview`
- `module-map-preview`
- `patch-draft-context`
- `guard-proposal-validation`

This is a contract-only declaration; no route behavior was changed.

## Operator Checklist Summary

Added `build_provider_operator_checklist()`.

Checklist covers:

- explicit provider enablement,
- prompt/context review,
- provider key redaction,
- local versus external provider risk,
- timeout/cancellation/bounded retry behavior,
- read-only endpoint provider restrictions.

## Tests Added

Added `backend/tests/test_provider_integration_hardening_contract.py`.

Coverage includes:

- provider capability matrix,
- provider action classification,
- prompt boundaries and validation,
- provider key handling,
- execution policy,
- error/timeout/retry behavior,
- operator checklist,
- audit payload redaction,
- static purity and import side-effect checks.

New test result:

- `53 passed`.

## Files Changed

Added:

- `backend/src/release/provider_integration_hardening_contract.py`
- `backend/tests/test_provider_integration_hardening_contract.py`
- `runs/provider-integration-hardening-contract-v1/final-report.md`

No runtime source files were modified by this slice.

## Protected File Status

- `backend/src/storage/database.py` touched: no.
- `backend/src/orchestrator/engine.py` touched: no.
- Providers touched: no.
- `backend/src/project_tools.py` touched: no.
- `backend/src/model_router.py` touched: no.
- Frontend touched: no.
- `scripts/run_tests.sh` touched: no.

Pre-existing dirty/untracked files remain in the worktree and were not reset, reverted, cleaned, or modified by this slice.

## Exact Checks / Results

Backend compile:

- `.venv/bin/python -m py_compile src/release/provider_integration_hardening_contract.py`: passed.
- `.venv/bin/python -m py_compile tests/test_provider_integration_hardening_contract.py`: passed.
- `.venv/bin/python -m py_compile src/release/auth_rbac_deployment_security_contract.py`: passed.
- `.venv/bin/python -m py_compile src/release/migration_backup_restore_contract.py`: passed.
- `.venv/bin/python -m py_compile src/storage/database.py`: passed.
- `.venv/bin/python -m py_compile src/models.py`: passed.
- `.venv/bin/python -m py_compile src/api/routes.py`: passed.

Backend targeted tests:

- `tests/test_provider_integration_hardening_contract.py`: `53 passed`.
- `tests/test_auth_rbac_deployment_security_contract.py`: `47 passed`.
- `tests/test_migration_backup_restore_contract.py`: `41 passed`.
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: `45 passed`.
- `tests/test_project_context_cockpit.py`: `26 passed`.
- `tests/test_delivery_report_module_awareness.py`: `20 passed`.
- `tests/test_module_aware_guard_policy.py`: `19 passed`.
- `tests/test_project_module_map.py`: `41 passed`.
- `tests/test_persistent_source_of_truth.py`: `31 passed`.

Full backend:

- `.venv/bin/pytest -q`: `1368 passed, 38 subtests passed in 17.38s`.

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run test:e2e:smoke`: `2 passed`.

Root runner:

- `bash scripts/run_tests.sh`: passed.
- Runner backend result: `1368 passed, 38 subtests passed in 17.53s`.
- Runner frontend TypeScript check: passed.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: provider hardening remains contract-only; runtime enforcement/redaction middleware is not implemented.
- P2: external provider execution remains future hardening work.
- P3: none found.

## Known Limitations

- Contract only, no runtime provider hardening implementation.
- No real secret manager integration.
- No runtime redaction middleware.
- No provider call telemetry/monitoring implementation.
- No production provider key rotation.
- No provider-specific timeout enforcement changes.
- No provider UI controls.

## Recommended Next Slice

Recommended next slice: Provider Integration Hardening Contract Regression Pass.

Reason: the contract is now in place and all checks are green. A focused regression pass should verify purity, wording, and compatibility before any runtime provider hardening or auth/RBAC runtime foundation begins.

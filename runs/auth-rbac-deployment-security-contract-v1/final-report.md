# Auth / RBAC / Deployment Security Model Contract v1

## Summary

Created a pure Auth / RBAC / Deployment Security Model Contract v1 for AI Workbench.

This slice addresses the remaining release-audit P1 security-model blocker at the contract/spec/test level only. It does not implement login, sessions, JWT, runtime authorization, API enforcement, provider execution, or deployment hardening.

## Why This Slice Exists

Production Hardening / Release Readiness Audit v1 identified two P1 blockers:

1. No formal migration/backup/restore process.
2. No multi-user auth/RBAC/deployment security model.

P1 blocker 1 now has a pure contract. This slice establishes the equivalent foundation for P1 blocker 2 so future implementation can be tested against stable expectations before runtime enforcement is added.

## Deployment Modes

Defined `DeploymentMode`:

- `local_single_user`
- `internal_operator`
- `team_beta`
- `commercial_production`

Mode profile behavior:

- `local_single_user`: trusted localhost / one operator; suitable for local dogfooding with warnings.
- `internal_operator`: trusted internal operator boundary; no public exposure.
- `team_beta`: requires auth/RBAC, audit logs, backups, provider key isolation, TLS, and project access boundaries.
- `commercial_production`: requires team-beta controls plus monitoring, retention/redaction, incident response, security review, and production operations hardening.

## Role Model

Defined `SecurityRole`:

- `owner`
- `operator`
- `reviewer`
- `developer`
- `viewer`
- `auditor`
- `service`

Role intent:

- Owner can manage all areas, but critical actions still require confirmation/audit.
- Operator can drive supervised workflow and request critical actions.
- Reviewer can inspect and approve/reject proposals but cannot execute.
- Developer can inspect context and create proposals but cannot apply.
- Viewer is read-only.
- Auditor can inspect context/audit logs only.
- Service is restricted to internal read/reporting surfaces and cannot execute provider, patch, command, or admin actions.

## Action Risk Classification

Defined `SecurityAction` and deterministic action classification.

Critical actions include:

- `apply_patch`
- `rollback_patch`
- `run_command`
- `execute_approval`
- `manage_provider_keys`
- `manage_backup_restore`
- `manage_users`
- `change_security_settings`

High-risk actions include:

- `call_provider`
- `approve_proposal`

Read/context actions remain read-only:

- `read_project`
- `read_run`
- `read_context`

Classifications record whether the action mutates state, touches project files, calls a provider, handles secrets, requires explicit confirmation, and requires audit logging.

## Permission Matrix Summary

Added pure permission evaluation through `evaluate_role_permission(...)`.

Important outcomes:

- Viewer cannot apply patches.
- Viewer can read context.
- Developer can create proposals but cannot apply patches.
- Reviewer can approve proposals but cannot run commands.
- Operator can create runs/proposals.
- Operator apply/rollback/run-command/provider calls require approval/confirmation.
- Owner security-setting changes remain critical and audit/confirmation gated.
- Service role cannot call providers, apply patches, or run commands.

No runtime enforcement was added.

## Provider Key Handling Rules

Added `build_provider_key_handling_rules()`.

Rules:

- Provider keys are never included in backups by default.
- Provider keys are never displayed in UI surfaces.
- Provider keys are never written into tool call outputs or reports.
- Provider calls require an explicit `allow_provider_call`-style flag.
- Production deployments require key isolation through environment secret storage or a secret manager.

## File Visibility Rules

Added `build_file_visibility_rules()`.

Rules:

- Source of Truth is metadata/context only.
- Module Map is metadata/context only.
- Project file contents require explicit future file-read permission.
- Bulk file content exposure is not allowed by default.
- Sensitive paths such as `.env`, secret/private/key/credentials/token patterns must be excluded or redacted before display, export, or provider use.

## Deployment Readiness Assessment

Added `assess_deployment_security_readiness(...)`.

Readiness behavior:

- Local single-user mode is allowed with warnings.
- Internal operator mode is allowed for trusted/internal operation with documented controls.
- Team beta is blocked unless required identity, RBAC, audit, backup, provider-key, TLS, and access-boundary controls exist.
- Commercial production is blocked unless team-beta controls plus monitoring, retention/redaction, incident response, and security review controls exist.

## Operator / Team Beta / Production Checklists

Added `build_operator_security_checklist(...)`.

Checklist coverage:

- Local mode mentions trusted localhost/operator.
- Internal mode mentions trust boundary, audit review, backup/restore contract, and provider key handling.
- Team beta mentions auth/RBAC, audit, backups, provider key isolation, and project access boundaries.
- Production mentions monitoring, retention/redaction, incident response, security review, deployment smoke tests, ownership, and recovery playbooks.

## Tests Added

Added `backend/tests/test_auth_rbac_deployment_security_contract.py`.

Coverage:

- Deployment mode profiles.
- Action risk classification.
- Role permission decisions.
- Deployment readiness assessment.
- Provider key handling rules.
- File visibility rules.
- Operator checklists.
- Contract completeness.
- Static safety/purity checks.
- Import side-effect check.

New test result:

- `47 passed`.

## Files Changed

Added:

- `backend/src/release/auth_rbac_deployment_security_contract.py`
- `backend/tests/test_auth_rbac_deployment_security_contract.py`
- `runs/auth-rbac-deployment-security-contract-v1/final-report.md`

No existing runtime files were modified by this slice.

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

- `.venv/bin/python -m py_compile src/release/auth_rbac_deployment_security_contract.py`: passed.
- `.venv/bin/python -m py_compile tests/test_auth_rbac_deployment_security_contract.py`: passed.
- `.venv/bin/python -m py_compile src/release/migration_backup_restore_contract.py`: passed.
- `.venv/bin/python -m py_compile src/storage/database.py`: passed.
- `.venv/bin/python -m py_compile src/models.py`: passed.
- `.venv/bin/python -m py_compile src/api/routes.py`: passed.

Backend targeted tests:

- `tests/test_auth_rbac_deployment_security_contract.py`: `47 passed`.
- `tests/test_migration_backup_restore_contract.py`: `41 passed`.
- `tests/test_real_project_end_to_end_delivery_dogfood.py`: `45 passed`.
- `tests/test_project_context_cockpit.py`: `26 passed`.
- `tests/test_delivery_report_module_awareness.py`: `20 passed`.
- `tests/test_module_aware_guard_policy.py`: `19 passed`.
- `tests/test_project_module_map.py`: `41 passed`.
- `tests/test_persistent_source_of_truth.py`: `31 passed`.

Full backend:

- `.venv/bin/pytest -q`: `1315 passed, 38 subtests passed in 17.28s`.

Frontend:

- `npx tsc --noEmit`: passed.
- `npm run build`: passed.
- `npm run test:e2e:smoke`: `2 passed`.

Root runner:

- `bash scripts/run_tests.sh`: passed.
- Runner backend result: `1315 passed, 38 subtests passed in 17.31s`.
- Runner frontend TypeScript check: passed.

## P0/P1/P2/P3 Issues

- P0: none.
- P1: none.
- P2: runtime auth/RBAC is still not implemented; this slice intentionally creates only the contract.
- P2: deployment hardening is still not implemented; this slice defines readiness expectations only.
- P3: none found.

## Known Limitations

- Contract only, no runtime auth/RBAC implementation.
- No login/session/JWT.
- No multi-user database schema.
- No actual enforcement.
- No provider secret manager.
- No audit-log UI for users/roles.
- No deployment hardening implementation.

## Recommended Next Slice

Recommended next slice: Auth/RBAC/Deployment Security Model Regression Pass.

Reason: the contract is now in place and green. A focused regression pass should verify purity, compatibility, and release-contract wording before implementing any runtime auth or enforcement behavior.

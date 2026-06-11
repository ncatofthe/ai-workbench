"""Pure Auth / RBAC / Deployment Security Model Contract v1.

This module defines release-readiness contracts for future authentication,
authorization, and deployment hardening work. It does not register routes,
connect to storage, call model adapters, execute tools, or mutate runtime state.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DeploymentMode(str, Enum):
    LOCAL_SINGLE_USER = "local_single_user"
    INTERNAL_OPERATOR = "internal_operator"
    TEAM_BETA = "team_beta"
    COMMERCIAL_PRODUCTION = "commercial_production"


class SecurityRole(str, Enum):
    OWNER = "owner"
    OPERATOR = "operator"
    REVIEWER = "reviewer"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    AUDITOR = "auditor"
    SERVICE = "service"


class SecurityAction(str, Enum):
    READ_PROJECT = "read_project"
    READ_RUN = "read_run"
    READ_CONTEXT = "read_context"
    CREATE_RUN = "create_run"
    CREATE_PROPOSAL = "create_proposal"
    APPROVE_PROPOSAL = "approve_proposal"
    APPLY_PATCH = "apply_patch"
    ROLLBACK_PATCH = "rollback_patch"
    RUN_COMMAND = "run_command"
    EXECUTE_APPROVAL = "execute_approval"
    CALL_PROVIDER = "call_provider"
    MANAGE_PROVIDER_KEYS = "manage_provider_keys"
    MANAGE_SOURCE_OF_TRUTH = "manage_source_of_truth"
    MANAGE_MODULE_MAP = "manage_module_map"
    MANAGE_BACKUP_RESTORE = "manage_backup_restore"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_USERS = "manage_users"
    CHANGE_SECURITY_SETTINGS = "change_security_settings"


class PermissionDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_APPROVAL = "requires_approval"
    REQUIRES_OWNER = "requires_owner"
    UNSUPPORTED = "unsupported"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityModeProfile(BaseModel):
    deployment_mode: DeploymentMode
    multi_user_enabled: bool = False
    trusted_localhost_only: bool = True
    provider_keys_allowed: bool = False
    external_network_allowed: bool = False
    required_controls: list[str] = Field(default_factory=list)
    unsupported_controls: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RolePermissionRule(BaseModel):
    role: SecurityRole
    action: SecurityAction
    decision: PermissionDecision
    risk_level: RiskLevel
    required_approvals: list[str] = Field(default_factory=list)
    notes: str = ""


class SecurityActionClassification(BaseModel):
    action: SecurityAction
    risk_level: RiskLevel
    mutates_state: bool = False
    touches_project_files: bool = False
    calls_provider: bool = False
    handles_secrets: bool = False
    requires_explicit_confirmation: bool = False
    requires_audit_log: bool = True
    notes: str = ""


class DeploymentSecurityAssessment(BaseModel):
    mode: DeploymentMode
    ready_for_mode: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_controls: list[str] = Field(default_factory=list)
    unsupported_features: list[str] = Field(default_factory=list)


class ProviderKeyHandlingRules(BaseModel):
    include_in_backups_by_default: bool = False
    display_in_ui: bool = False
    write_to_audit_outputs: bool = False
    require_explicit_provider_call_flag: bool = True
    production_storage_requirement: str = "environment secret manager or equivalent isolated secret store"
    rules: list[str] = Field(default_factory=list)


class FileVisibilityRules(BaseModel):
    source_of_truth_is_metadata_only: bool = True
    module_map_is_metadata_only: bool = True
    project_file_contents_require_explicit_permission: bool = True
    allow_bulk_file_reads_by_default: bool = False
    sensitive_path_patterns: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


_READ_ACTIONS = {
    SecurityAction.READ_PROJECT,
    SecurityAction.READ_RUN,
    SecurityAction.READ_CONTEXT,
    SecurityAction.VIEW_AUDIT_LOGS,
}

_CRITICAL_ACTIONS = {
    SecurityAction.APPLY_PATCH,
    SecurityAction.ROLLBACK_PATCH,
    SecurityAction.RUN_COMMAND,
    SecurityAction.EXECUTE_APPROVAL,
    SecurityAction.MANAGE_PROVIDER_KEYS,
    SecurityAction.MANAGE_BACKUP_RESTORE,
    SecurityAction.MANAGE_USERS,
    SecurityAction.CHANGE_SECURITY_SETTINGS,
}


def build_default_security_action_matrix() -> list[SecurityActionClassification]:
    return [classify_security_action(action) for action in SecurityAction]


def classify_security_action(action: SecurityAction) -> SecurityActionClassification:
    if action in {SecurityAction.READ_PROJECT, SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT}:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.LOW,
            mutates_state=False,
            requires_explicit_confirmation=False,
            notes="Read-only context visibility.",
        )

    if action == SecurityAction.CREATE_RUN:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.MEDIUM,
            mutates_state=True,
            notes="Creates run records and execution planning state.",
        )

    if action == SecurityAction.CREATE_PROPOSAL:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.MEDIUM,
            mutates_state=True,
            requires_audit_log=True,
            notes="Creates a patch proposal audit record; does not apply files.",
        )

    if action == SecurityAction.APPROVE_PROPOSAL:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.HIGH,
            mutates_state=True,
            requires_explicit_confirmation=True,
            notes="Records review/approval intent before dangerous work may proceed.",
        )

    if action in {SecurityAction.APPLY_PATCH, SecurityAction.ROLLBACK_PATCH}:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            touches_project_files=True,
            requires_explicit_confirmation=True,
            requires_audit_log=True,
            notes="Changes project files and must remain confirmation-gated.",
        )

    if action == SecurityAction.RUN_COMMAND:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            requires_explicit_confirmation=True,
            requires_audit_log=True,
            notes="Executes configured project commands and must stay allowlist/approval gated.",
        )

    if action == SecurityAction.EXECUTE_APPROVAL:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            requires_explicit_confirmation=True,
            requires_audit_log=True,
            notes="Consumes an approval and may trigger a previously gated action.",
        )

    if action == SecurityAction.CALL_PROVIDER:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.HIGH,
            calls_provider=True,
            requires_explicit_confirmation=True,
            requires_audit_log=True,
            notes="External or local model execution must require an explicit provider-call flag.",
        )

    if action == SecurityAction.MANAGE_PROVIDER_KEYS:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            handles_secrets=True,
            requires_explicit_confirmation=True,
            notes="Secret material must never be shown, logged, or exported by default.",
        )

    if action in {SecurityAction.MANAGE_SOURCE_OF_TRUTH, SecurityAction.MANAGE_MODULE_MAP}:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.MEDIUM,
            mutates_state=True,
            requires_audit_log=True,
            notes="Changes project context metadata used by guarded workflows.",
        )

    if action == SecurityAction.MANAGE_BACKUP_RESTORE:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            handles_secrets=True,
            requires_explicit_confirmation=True,
            notes="Can overwrite durable state or expose sensitive audit data.",
        )

    if action == SecurityAction.VIEW_AUDIT_LOGS:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.MEDIUM,
            mutates_state=False,
            notes="Audit records may contain sensitive project metadata.",
        )

    if action in {SecurityAction.MANAGE_USERS, SecurityAction.CHANGE_SECURITY_SETTINGS}:
        return SecurityActionClassification(
            action=action,
            risk_level=RiskLevel.CRITICAL,
            mutates_state=True,
            requires_explicit_confirmation=True,
            notes="Administrative security operation.",
        )

    return SecurityActionClassification(action=action, risk_level=RiskLevel.HIGH)


def build_security_mode_profile(deployment_mode: DeploymentMode) -> SecurityModeProfile:
    if deployment_mode == DeploymentMode.LOCAL_SINGLE_USER:
        return SecurityModeProfile(
            deployment_mode=deployment_mode,
            multi_user_enabled=False,
            trusted_localhost_only=True,
            provider_keys_allowed=True,
            external_network_allowed=False,
            required_controls=["trusted_localhost", "single_operator_trust_boundary", "local_provider_key_review"],
            unsupported_controls=["public_network_exposure", "multi_user_sessions", "team_rbac"],
            notes=["Suitable for local dogfooding by one trusted operator."],
        )

    if deployment_mode == DeploymentMode.INTERNAL_OPERATOR:
        return SecurityModeProfile(
            deployment_mode=deployment_mode,
            multi_user_enabled=False,
            trusted_localhost_only=True,
            provider_keys_allowed=True,
            external_network_allowed=False,
            required_controls=[
                "documented_operator_trust_boundary",
                "backup_restore_contract",
                "audit_log_review",
                "provider_key_handling_rules",
            ],
            unsupported_controls=["public_network_exposure", "untrusted_multi_user_access"],
            notes=["Acceptable only for trusted internal operators on controlled machines."],
        )

    if deployment_mode == DeploymentMode.TEAM_BETA:
        return SecurityModeProfile(
            deployment_mode=deployment_mode,
            multi_user_enabled=True,
            trusted_localhost_only=False,
            provider_keys_allowed=True,
            external_network_allowed=True,
            required_controls=[
                "auth_rbac",
                "audit_logs",
                "backup_restore_contract",
                "provider_key_isolation",
                "deployment_tls",
                "project_access_boundaries",
            ],
            unsupported_controls=["anonymous_access", "shared_provider_keys_without_isolation"],
            notes=["Not ready until multi-user identity and role permissions are implemented."],
        )

    return SecurityModeProfile(
        deployment_mode=deployment_mode,
        multi_user_enabled=True,
        trusted_localhost_only=False,
        provider_keys_allowed=True,
        external_network_allowed=True,
        required_controls=[
            "auth_rbac",
            "audit_logs",
            "backup_restore_contract",
            "provider_key_isolation",
            "deployment_tls",
            "monitoring",
            "retention_redaction_policy",
            "incident_response",
            "security_review",
        ],
        unsupported_controls=["anonymous_access", "local_only_trust_assumption"],
        notes=["Commercial production requires team-beta controls plus operations hardening."],
    )


def build_default_role_permission_matrix() -> list[RolePermissionRule]:
    return [evaluate_role_permission(role, action, DeploymentMode.TEAM_BETA) for role in SecurityRole for action in SecurityAction]


def evaluate_role_permission(
    role: SecurityRole,
    action: SecurityAction,
    deployment_mode: DeploymentMode,
) -> RolePermissionRule:
    classification = classify_security_action(action)
    approvals = _approvals_for_action(classification)

    if deployment_mode == DeploymentMode.LOCAL_SINGLE_USER and role == SecurityRole.OWNER:
        decision = PermissionDecision.REQUIRES_APPROVAL if action in _CRITICAL_ACTIONS else PermissionDecision.ALLOWED
        return RolePermissionRule(
            role=role,
            action=action,
            decision=decision,
            risk_level=classification.risk_level,
            required_approvals=approvals,
            notes="Local owner is the trusted operator; critical actions remain confirmation/audit gated.",
        )

    if role == SecurityRole.OWNER:
        return RolePermissionRule(
            role=role,
            action=action,
            decision=PermissionDecision.REQUIRES_APPROVAL if action in _CRITICAL_ACTIONS else PermissionDecision.ALLOWED,
            risk_level=classification.risk_level,
            required_approvals=approvals,
            notes="Owner may manage the workspace, but critical actions require confirmation and audit.",
        )

    if role == SecurityRole.OPERATOR:
        if action in {
            SecurityAction.READ_PROJECT,
            SecurityAction.READ_RUN,
            SecurityAction.READ_CONTEXT,
            SecurityAction.CREATE_RUN,
            SecurityAction.CREATE_PROPOSAL,
            SecurityAction.MANAGE_SOURCE_OF_TRUTH,
            SecurityAction.MANAGE_MODULE_MAP,
            SecurityAction.VIEW_AUDIT_LOGS,
        }:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Operator can drive normal supervised workflow.")
        if action in {
            SecurityAction.APPLY_PATCH,
            SecurityAction.ROLLBACK_PATCH,
            SecurityAction.RUN_COMMAND,
            SecurityAction.EXECUTE_APPROVAL,
            SecurityAction.CALL_PROVIDER,
        }:
            return _permission(role, action, PermissionDecision.REQUIRES_APPROVAL, classification, "Critical operator action requires explicit confirmation/approval.")
        if action in {
            SecurityAction.MANAGE_PROVIDER_KEYS,
            SecurityAction.MANAGE_BACKUP_RESTORE,
            SecurityAction.MANAGE_USERS,
            SecurityAction.CHANGE_SECURITY_SETTINGS,
        }:
            return _permission(role, action, PermissionDecision.REQUIRES_OWNER, classification, "Administrative action requires owner.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Operator role is not authorized for this action.")

    if role == SecurityRole.REVIEWER:
        if action in {SecurityAction.READ_PROJECT, SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT, SecurityAction.VIEW_AUDIT_LOGS, SecurityAction.APPROVE_PROPOSAL}:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Reviewer may inspect and approve/reject proposals.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Reviewer cannot execute or mutate project files.")

    if role == SecurityRole.DEVELOPER:
        if action in {SecurityAction.READ_PROJECT, SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT, SecurityAction.CREATE_PROPOSAL}:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Developer may inspect context and draft proposals.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Developer cannot apply patches, run commands, or administer settings.")

    if role == SecurityRole.VIEWER:
        if action in {SecurityAction.READ_PROJECT, SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT}:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Viewer is read-only.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Viewer cannot mutate state.")

    if role == SecurityRole.AUDITOR:
        if action in {SecurityAction.READ_PROJECT, SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT, SecurityAction.VIEW_AUDIT_LOGS}:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Auditor can inspect context and audit logs.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Auditor cannot execute workflow actions.")

    if role == SecurityRole.SERVICE:
        if action in {SecurityAction.READ_RUN, SecurityAction.READ_CONTEXT, SecurityAction.VIEW_AUDIT_LOGS}:
            return _permission(role, action, PermissionDecision.ALLOWED, classification, "Service role is limited to internal read/reporting tasks.")
        return _permission(role, action, PermissionDecision.DENIED, classification, "Service role cannot execute provider, command, patch, or admin actions.")

    return _permission(role, action, PermissionDecision.DENIED, classification, "Unknown role/action pairing.")


def assess_deployment_security_readiness(
    deployment_mode: DeploymentMode,
    enabled_controls: list[str] | set[str] | tuple[str, ...],
) -> DeploymentSecurityAssessment:
    profile = build_security_mode_profile(deployment_mode)
    enabled = {str(control).strip() for control in enabled_controls if str(control).strip()}
    required = set(profile.required_controls)
    missing = sorted(required - enabled)
    blockers: list[str] = []
    warnings: list[str] = []

    if deployment_mode == DeploymentMode.LOCAL_SINGLE_USER:
        if missing:
            warnings.append("Local mode is allowed for one trusted operator, but missing controls should be reviewed: " + ", ".join(missing))
        return DeploymentSecurityAssessment(
            mode=deployment_mode,
            ready_for_mode=True,
            blockers=[],
            warnings=warnings or ["Local mode depends on trusted localhost and one responsible operator."],
            required_controls=profile.required_controls,
            unsupported_features=profile.unsupported_controls,
        )

    if deployment_mode == DeploymentMode.INTERNAL_OPERATOR:
        if missing:
            warnings.append("Internal operator mode requires documented controls before wider internal use: " + ", ".join(missing))
        return DeploymentSecurityAssessment(
            mode=deployment_mode,
            ready_for_mode=True,
            blockers=[],
            warnings=warnings or ["Internal mode remains limited to trusted operators and non-public exposure."],
            required_controls=profile.required_controls,
            unsupported_features=profile.unsupported_controls,
        )

    if deployment_mode == DeploymentMode.TEAM_BETA:
        if missing:
            blockers.append("Team beta is blocked until required controls exist: " + ", ".join(missing))
        return DeploymentSecurityAssessment(
            mode=deployment_mode,
            ready_for_mode=not blockers,
            blockers=blockers,
            warnings=[] if blockers else ["Team beta controls are present; perform deployment smoke and security review before inviting users."],
            required_controls=profile.required_controls,
            unsupported_features=profile.unsupported_controls,
        )

    if missing:
        blockers.append("Commercial production is blocked until required controls exist: " + ", ".join(missing))
    return DeploymentSecurityAssessment(
        mode=deployment_mode,
        ready_for_mode=not blockers,
        blockers=blockers,
        warnings=[] if blockers else ["Production controls are present on paper; perform independent security, load, and recovery validation."],
        required_controls=profile.required_controls,
        unsupported_features=profile.unsupported_controls,
    )


def build_operator_security_checklist(deployment_mode: DeploymentMode) -> list[str]:
    if deployment_mode == DeploymentMode.LOCAL_SINGLE_USER:
        return [
            "Run only on trusted localhost or a private trusted machine.",
            "Treat the current operator as the owner of all local actions.",
            "Keep provider keys in local environment storage and review them manually.",
            "Confirm apply, command, rollback, and provider actions explicitly.",
        ]
    if deployment_mode == DeploymentMode.INTERNAL_OPERATOR:
        return [
            "Document the trusted operator boundary and prohibit public exposure.",
            "Review audit logs for proposals, applies, commands, guards, and approvals.",
            "Verify backup/restore contract coverage before relying on the workspace.",
            "Confirm provider key handling rules are followed.",
        ]
    if deployment_mode == DeploymentMode.TEAM_BETA:
        return [
            "Implement auth/RBAC before allowing multiple users.",
            "Require audit logs for critical actions.",
            "Verify backups and restore preflight.",
            "Isolate provider keys per deployment or user boundary.",
            "Document project access boundaries.",
        ]
    return [
        "Complete auth/RBAC, audit logs, backups, and provider key isolation.",
        "Enable monitoring, alerting, retention/redaction, and incident response.",
        "Run independent security review and deployment smoke tests.",
        "Document operational ownership and recovery playbooks.",
    ]


def build_provider_key_handling_rules() -> ProviderKeyHandlingRules:
    return ProviderKeyHandlingRules(
        rules=[
            "Provider keys are never included in backups by default.",
            "Provider keys are never displayed in UI surfaces.",
            "Provider keys are never written into tool call outputs or reports.",
            "Provider calls require an explicit allow_provider_call-style flag.",
            "Production deployments require key isolation through environment secret storage or a secret manager.",
        ]
    )


def build_file_visibility_rules() -> FileVisibilityRules:
    return FileVisibilityRules(
        sensitive_path_patterns=[".env", "secret", "private", "key", "credentials", "token"],
        rules=[
            "Source of Truth and Module Map are metadata/context only, not file contents.",
            "Project file contents require an explicit file-read permission in a future auth model.",
            "Bulk file content exposure is not allowed by default.",
            "Sensitive paths must be excluded or redacted before display, export, or provider use.",
        ],
    )


def build_release_security_summary() -> dict[str, object]:
    return {
        "deployment_modes": [mode.value for mode in DeploymentMode],
        "roles": [role.value for role in SecurityRole],
        "critical_actions": [action.value for action in _CRITICAL_ACTIONS],
        "provider_key_rules": build_provider_key_handling_rules().rules,
        "file_visibility_rules": build_file_visibility_rules().rules,
        "production_ready": False,
        "reason": "This is a contract only; runtime auth/RBAC and deployment hardening are not implemented.",
    }


def _permission(
    role: SecurityRole,
    action: SecurityAction,
    decision: PermissionDecision,
    classification: SecurityActionClassification,
    notes: str,
) -> RolePermissionRule:
    return RolePermissionRule(
        role=role,
        action=action,
        decision=decision,
        risk_level=classification.risk_level,
        required_approvals=_approvals_for_action(classification) if decision == PermissionDecision.REQUIRES_APPROVAL else (
            ["audit_log"] if classification.risk_level == RiskLevel.CRITICAL and decision == PermissionDecision.ALLOWED else []
        ),
        notes=notes,
    )


def _approvals_for_action(classification: SecurityActionClassification) -> list[str]:
    approvals: list[str] = []
    if classification.requires_explicit_confirmation:
        approvals.append("manual_confirmation")
    if classification.requires_audit_log:
        approvals.append("audit_log")
    if classification.touches_project_files:
        approvals.append("project_file_review")
    if classification.calls_provider:
        approvals.append("provider_call_acknowledgement")
    if classification.handles_secrets:
        approvals.append("secret_handling_review")
    return approvals

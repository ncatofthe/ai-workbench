"""Tests for Auth / RBAC / Deployment Security Model Contract v1."""

from __future__ import annotations

import importlib
import inspect

from src.release import auth_rbac_deployment_security_contract as contract
from src.release.auth_rbac_deployment_security_contract import (
    DeploymentMode,
    PermissionDecision,
    RiskLevel,
    SecurityAction,
    SecurityRole,
    assess_deployment_security_readiness,
    build_default_role_permission_matrix,
    build_default_security_action_matrix,
    build_file_visibility_rules,
    build_operator_security_checklist,
    build_provider_key_handling_rules,
    build_release_security_summary,
    build_security_mode_profile,
    classify_security_action,
    evaluate_role_permission,
)


class TestModeProfiles:
    def test_local_single_user_profile_is_trusted_localhost_only(self):
        profile = build_security_mode_profile(DeploymentMode.LOCAL_SINGLE_USER)
        assert profile.trusted_localhost_only is True
        assert profile.multi_user_enabled is False
        assert "public_network_exposure" in profile.unsupported_controls

    def test_internal_operator_profile_disallows_public_exposure(self):
        profile = build_security_mode_profile(DeploymentMode.INTERNAL_OPERATOR)
        assert profile.trusted_localhost_only is True
        assert "public_network_exposure" in profile.unsupported_controls
        assert "documented_operator_trust_boundary" in profile.required_controls

    def test_team_beta_requires_multi_user_rbac_controls(self):
        profile = build_security_mode_profile(DeploymentMode.TEAM_BETA)
        assert profile.multi_user_enabled is True
        assert "auth_rbac" in profile.required_controls
        assert "project_access_boundaries" in profile.required_controls

    def test_commercial_production_reports_blockers_without_production_controls(self):
        result = assess_deployment_security_readiness(DeploymentMode.COMMERCIAL_PRODUCTION, [])
        assert result.ready_for_mode is False
        assert result.blockers
        assert any("monitoring" in blocker for blocker in result.blockers)


class TestActionClassification:
    def test_apply_patch_is_critical_and_mutates_project_files(self):
        item = classify_security_action(SecurityAction.APPLY_PATCH)
        assert item.risk_level == RiskLevel.CRITICAL
        assert item.mutates_state is True
        assert item.touches_project_files is True
        assert item.requires_explicit_confirmation is True

    def test_run_command_is_critical_execution_risk(self):
        item = classify_security_action(SecurityAction.RUN_COMMAND)
        assert item.risk_level == RiskLevel.CRITICAL
        assert item.mutates_state is True
        assert item.requires_explicit_confirmation is True
        assert "command" in item.notes.lower()

    def test_call_provider_is_high_risk_and_calls_provider(self):
        item = classify_security_action(SecurityAction.CALL_PROVIDER)
        assert item.risk_level == RiskLevel.HIGH
        assert item.calls_provider is True
        assert item.requires_explicit_confirmation is True

    def test_read_context_is_read_only(self):
        item = classify_security_action(SecurityAction.READ_CONTEXT)
        assert item.risk_level == RiskLevel.LOW
        assert item.mutates_state is False
        assert item.touches_project_files is False
        assert item.calls_provider is False

    def test_manage_provider_keys_is_critical_secret_sensitive(self):
        item = classify_security_action(SecurityAction.MANAGE_PROVIDER_KEYS)
        assert item.risk_level == RiskLevel.CRITICAL
        assert item.handles_secrets is True
        assert item.requires_explicit_confirmation is True

    def test_manage_backup_restore_is_critical_data_operation(self):
        item = classify_security_action(SecurityAction.MANAGE_BACKUP_RESTORE)
        assert item.risk_level == RiskLevel.CRITICAL
        assert item.mutates_state is True
        assert "overwrite" in item.notes.lower() or "sensitive" in item.notes.lower()


class TestRolePermissions:
    def test_viewer_cannot_apply_patch(self):
        rule = evaluate_role_permission(SecurityRole.VIEWER, SecurityAction.APPLY_PATCH, DeploymentMode.TEAM_BETA)
        assert rule.decision == PermissionDecision.DENIED

    def test_viewer_can_read_context(self):
        rule = evaluate_role_permission(SecurityRole.VIEWER, SecurityAction.READ_CONTEXT, DeploymentMode.TEAM_BETA)
        assert rule.decision == PermissionDecision.ALLOWED

    def test_developer_can_create_proposal_but_cannot_apply_patch(self):
        create = evaluate_role_permission(SecurityRole.DEVELOPER, SecurityAction.CREATE_PROPOSAL, DeploymentMode.TEAM_BETA)
        apply = evaluate_role_permission(SecurityRole.DEVELOPER, SecurityAction.APPLY_PATCH, DeploymentMode.TEAM_BETA)
        assert create.decision == PermissionDecision.ALLOWED
        assert apply.decision == PermissionDecision.DENIED

    def test_reviewer_can_approve_proposal_but_cannot_run_command(self):
        approve = evaluate_role_permission(SecurityRole.REVIEWER, SecurityAction.APPROVE_PROPOSAL, DeploymentMode.TEAM_BETA)
        run = evaluate_role_permission(SecurityRole.REVIEWER, SecurityAction.RUN_COMMAND, DeploymentMode.TEAM_BETA)
        assert approve.decision == PermissionDecision.ALLOWED
        assert run.decision == PermissionDecision.DENIED

    def test_operator_can_create_run_and_create_proposal(self):
        create_run = evaluate_role_permission(SecurityRole.OPERATOR, SecurityAction.CREATE_RUN, DeploymentMode.INTERNAL_OPERATOR)
        create_proposal = evaluate_role_permission(SecurityRole.OPERATOR, SecurityAction.CREATE_PROPOSAL, DeploymentMode.INTERNAL_OPERATOR)
        assert create_run.decision == PermissionDecision.ALLOWED
        assert create_proposal.decision == PermissionDecision.ALLOWED

    def test_operator_apply_patch_requires_approval_confirmation(self):
        rule = evaluate_role_permission(SecurityRole.OPERATOR, SecurityAction.APPLY_PATCH, DeploymentMode.INTERNAL_OPERATOR)
        assert rule.decision == PermissionDecision.REQUIRES_APPROVAL
        assert "manual_confirmation" in rule.required_approvals
        assert "audit_log" in rule.required_approvals

    def test_owner_can_manage_security_settings_but_still_requires_audit_for_critical_actions(self):
        rule = evaluate_role_permission(SecurityRole.OWNER, SecurityAction.CHANGE_SECURITY_SETTINGS, DeploymentMode.TEAM_BETA)
        assert rule.decision == PermissionDecision.REQUIRES_APPROVAL
        assert "audit_log" in rule.required_approvals

    def test_service_role_cannot_call_provider_apply_patch_or_run_command(self):
        for action in (SecurityAction.CALL_PROVIDER, SecurityAction.APPLY_PATCH, SecurityAction.RUN_COMMAND):
            rule = evaluate_role_permission(SecurityRole.SERVICE, action, DeploymentMode.TEAM_BETA)
            assert rule.decision == PermissionDecision.DENIED


class TestDeploymentReadiness:
    def test_local_single_user_allowed_with_warnings(self):
        result = assess_deployment_security_readiness(DeploymentMode.LOCAL_SINGLE_USER, [])
        assert result.ready_for_mode is True
        assert result.warnings

    def test_internal_operator_medium_readiness_with_required_controls(self):
        profile = build_security_mode_profile(DeploymentMode.INTERNAL_OPERATOR)
        result = assess_deployment_security_readiness(DeploymentMode.INTERNAL_OPERATOR, profile.required_controls)
        assert result.ready_for_mode is True
        assert result.blockers == []
        assert result.warnings

    def test_team_beta_blocked_without_auth_rbac(self):
        result = assess_deployment_security_readiness(DeploymentMode.TEAM_BETA, [])
        assert result.ready_for_mode is False
        assert any("auth_rbac" in blocker for blocker in result.blockers)

    def test_commercial_production_blocked_without_full_controls(self):
        result = assess_deployment_security_readiness(DeploymentMode.COMMERCIAL_PRODUCTION, ["auth_rbac"])
        assert result.ready_for_mode is False
        assert any("monitoring" in blocker or "incident_response" in blocker for blocker in result.blockers)

    def test_adding_auth_rbac_backups_and_audit_improves_team_beta_readiness(self):
        profile = build_security_mode_profile(DeploymentMode.TEAM_BETA)
        result = assess_deployment_security_readiness(DeploymentMode.TEAM_BETA, profile.required_controls)
        assert result.ready_for_mode is True
        assert result.blockers == []

    def test_commercial_production_still_needs_monitoring_retention_incident_controls(self):
        team_controls = build_security_mode_profile(DeploymentMode.TEAM_BETA).required_controls
        result = assess_deployment_security_readiness(DeploymentMode.COMMERCIAL_PRODUCTION, team_controls)
        assert result.ready_for_mode is False
        combined = " ".join(result.blockers)
        assert "monitoring" in combined
        assert "retention_redaction_policy" in combined
        assert "incident_response" in combined


class TestProviderKeyRules:
    def test_provider_keys_are_never_included_by_default(self):
        rules = build_provider_key_handling_rules()
        assert rules.include_in_backups_by_default is False

    def test_provider_keys_require_secret_manager_environment_storage_in_production(self):
        rules = build_provider_key_handling_rules()
        assert "secret" in rules.production_storage_requirement.lower()
        assert "environment" in rules.production_storage_requirement.lower()

    def test_provider_calls_require_explicit_allow_provider_call(self):
        rules = build_provider_key_handling_rules()
        assert rules.require_explicit_provider_call_flag is True
        assert any("allow_provider_call" in rule for rule in rules.rules)

    def test_provider_keys_must_not_appear_in_audit_outputs(self):
        rules = build_provider_key_handling_rules()
        assert rules.write_to_audit_outputs is False
        assert any("tool call outputs" in rule.lower() or "reports" in rule.lower() for rule in rules.rules)


class TestFileVisibilityRules:
    def test_source_of_truth_and_module_map_are_metadata_only(self):
        rules = build_file_visibility_rules()
        assert rules.source_of_truth_is_metadata_only is True
        assert rules.module_map_is_metadata_only is True

    def test_project_file_contents_require_explicit_future_file_read_permission(self):
        rules = build_file_visibility_rules()
        assert rules.project_file_contents_require_explicit_permission is True
        assert any("explicit file-read permission" in rule for rule in rules.rules)

    def test_sensitive_paths_require_redaction_exclusion(self):
        rules = build_file_visibility_rules()
        assert ".env" in rules.sensitive_path_patterns
        assert "secret" in rules.sensitive_path_patterns
        assert any("redacted" in rule or "excluded" in rule for rule in rules.rules)

    def test_bulk_file_reads_are_not_allowed_by_default(self):
        assert build_file_visibility_rules().allow_bulk_file_reads_by_default is False


class TestChecklists:
    def test_local_checklist_mentions_localhost_trusted_operator(self):
        text = "\n".join(build_operator_security_checklist(DeploymentMode.LOCAL_SINGLE_USER)).lower()
        assert "localhost" in text
        assert "operator" in text

    def test_team_beta_checklist_mentions_auth_rbac_audit_backups(self):
        text = "\n".join(build_operator_security_checklist(DeploymentMode.TEAM_BETA)).lower()
        assert "auth/rbac" in text
        assert "audit" in text
        assert "backups" in text

    def test_production_checklist_mentions_monitoring_retention_incident_response(self):
        text = "\n".join(build_operator_security_checklist(DeploymentMode.COMMERCIAL_PRODUCTION)).lower()
        assert "monitoring" in text
        assert "retention" in text
        assert "incident response" in text

    def test_provider_checklist_mentions_key_isolation(self):
        text = "\n".join(build_provider_key_handling_rules().rules).lower()
        assert "key isolation" in text

    def test_file_visibility_checklist_mentions_sensitive_path_redaction(self):
        text = "\n".join(build_file_visibility_rules().rules).lower()
        assert "sensitive paths" in text
        assert "redacted" in text or "excluded" in text


class TestContractCompleteness:
    def test_default_action_matrix_contains_all_actions(self):
        matrix = build_default_security_action_matrix()
        assert {item.action for item in matrix} == set(SecurityAction)

    def test_default_role_permission_matrix_contains_all_role_action_pairs(self):
        matrix = build_default_role_permission_matrix()
        assert len(matrix) == len(SecurityRole) * len(SecurityAction)

    def test_release_security_summary_is_contract_only(self):
        summary = build_release_security_summary()
        assert summary["production_ready"] is False
        assert "runtime auth/RBAC" in str(summary["reason"])


class TestContractSafety:
    def test_contract_module_has_no_database_imports(self):
        source = inspect.getsource(contract)
        assert "src.storage.database" not in source
        assert "_connect" not in source

    def test_contract_module_has_no_provider_imports(self):
        source = inspect.getsource(contract)
        assert "src.providers" not in source
        assert "from src.providers" not in source
        assert "ollama.chat_completion" not in source

    def test_contract_module_has_no_route_imports(self):
        source = inspect.getsource(contract)
        assert "src.api.routes" not in source
        assert "@router" not in source

    def test_contract_module_has_no_subprocess_os_command_execution(self):
        source = inspect.getsource(contract)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_contract_module_has_no_execute_run_or_asyncio_create_task(self):
        source = inspect.getsource(contract)
        assert "execute_run(" not in source
        assert "asyncio.create_task(" not in source

    def test_contract_module_has_no_file_reads_writes(self):
        source = inspect.getsource(contract)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source
        assert ".write_text(" not in source
        assert ".write(" not in source

    def test_importing_contract_module_has_no_side_effects(self):
        loaded = importlib.import_module("src.release.auth_rbac_deployment_security_contract")
        assert loaded.DeploymentMode.LOCAL_SINGLE_USER.value == "local_single_user"

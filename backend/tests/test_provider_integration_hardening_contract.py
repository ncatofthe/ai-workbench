"""Tests for Provider Integration Hardening Contract v1."""

from __future__ import annotations

import importlib
import inspect

from src.release import provider_integration_hardening_contract as contract
from src.release.provider_integration_hardening_contract import (
    ProviderAction,
    ProviderDataSensitivity,
    ProviderDecision,
    ProviderExecutionMode,
    ProviderKind,
    ProviderPromptBoundary,
    ProviderRiskLevel,
    build_default_prompt_boundary,
    build_default_provider_capabilities,
    build_provider_error_handling_contract,
    build_provider_key_handling_rules,
    build_provider_operator_checklist,
    classify_provider_action,
    evaluate_provider_execution_policy,
    redact_provider_payload_for_audit,
    validate_provider_prompt_boundary,
)


def _capability(provider: ProviderKind):
    return next(item for item in build_default_provider_capabilities() if item.provider == provider)


def _key_rule(provider: ProviderKind):
    return next(item for item in build_provider_key_handling_rules() if item.provider == provider)


class TestProviderCapabilities:
    def test_default_capabilities_include_ollama(self):
        assert _capability(ProviderKind.OLLAMA).provider == ProviderKind.OLLAMA

    def test_default_capabilities_include_codex(self):
        assert _capability(ProviderKind.CODEX).provider == ProviderKind.CODEX

    def test_default_capabilities_include_claude(self):
        assert _capability(ProviderKind.CLAUDE).provider == ProviderKind.CLAUDE

    def test_mock_provider_has_no_external_network_requirement(self):
        assert _capability(ProviderKind.MOCK).external_network_required is False

    def test_external_providers_are_marked_external_network_risk(self):
        assert _capability(ProviderKind.CODEX).external_network_required is True
        assert _capability(ProviderKind.CLAUDE).stores_remote_data_risk is True
        assert _capability(ProviderKind.FUTURE_EXTERNAL).external_network_required is True


class TestProviderActionClassification:
    def test_build_prompt_does_not_call_external_network(self):
        item = classify_provider_action(ProviderAction.BUILD_PROMPT)
        assert item.calls_external_network is False
        assert item.may_expose_project_context is True

    def test_preview_prompt_is_read_only(self):
        item = classify_provider_action(ProviderAction.PREVIEW_PROMPT)
        assert item.risk_level == ProviderRiskLevel.LOW
        assert item.calls_external_network is False

    def test_call_provider_is_high_risk_and_requires_explicit_allow(self):
        item = classify_provider_action(ProviderAction.CALL_PROVIDER)
        assert item.risk_level == ProviderRiskLevel.HIGH
        assert item.requires_explicit_allow is True
        assert item.requires_redaction is True

    def test_configure_provider_key_is_secret_sensitive(self):
        item = classify_provider_action(ProviderAction.CONFIGURE_PROVIDER_KEY)
        assert item.risk_level == ProviderRiskLevel.CRITICAL
        assert item.handles_secrets is True

    def test_store_provider_result_requires_audit_redaction(self):
        item = classify_provider_action(ProviderAction.STORE_PROVIDER_RESULT)
        assert item.requires_audit_log is True
        assert item.requires_redaction is True

    def test_retry_provider_call_requires_bounded_retry(self):
        item = classify_provider_action(ProviderAction.RETRY_PROVIDER_CALL)
        assert item.requires_explicit_allow is True
        assert "bounded" in item.notes.lower() or "indefinitely" in item.notes.lower()


class TestPromptBoundaries:
    def test_default_boundary_allows_source_of_truth_bounded_context(self):
        assert build_default_prompt_boundary().include_source_of_truth is True

    def test_default_boundary_allows_module_map_bounded_context(self):
        assert build_default_prompt_boundary().include_module_map is True

    def test_default_boundary_excludes_file_contents_by_default(self):
        assert build_default_prompt_boundary().include_file_contents is False

    def test_default_boundary_excludes_provider_keys(self):
        assert build_default_prompt_boundary().include_provider_keys is False

    def test_default_boundary_excludes_secrets(self):
        assert build_default_prompt_boundary().include_secrets is False

    def test_raw_full_project_dumps_are_invalid(self):
        result = validate_provider_prompt_boundary(
            ProviderPromptBoundary(allow_raw_project_dump=True)
        )
        assert result.allowed is False
        assert any("raw full project dumps" in blocker.lower() for blocker in result.blockers)

    def test_boundary_validation_blocks_include_provider_keys_true(self):
        result = validate_provider_prompt_boundary(
            ProviderPromptBoundary(include_provider_keys=True)
        )
        assert result.allowed is False
        assert any("provider keys" in blocker.lower() for blocker in result.blockers)

    def test_boundary_validation_blocks_include_secrets_true(self):
        result = validate_provider_prompt_boundary(
            ProviderPromptBoundary(include_secrets=True)
        )
        assert result.allowed is False
        assert any("secrets" in blocker.lower() for blocker in result.blockers)


class TestProviderKeyHandling:
    def test_provider_keys_classify_as_secret(self):
        assert _key_rule(ProviderKind.CODEX).sensitivity == ProviderDataSensitivity.SECRET

    def test_provider_keys_are_excluded_from_backup_by_default(self):
        assert _key_rule(ProviderKind.CLAUDE).backup_behavior == "excluded_by_default"

    def test_provider_keys_are_forbidden_in_ui_display(self):
        assert _key_rule(ProviderKind.CODEX).ui_display_allowed is False
        assert "ui_display" in _key_rule(ProviderKind.CODEX).forbidden_outputs

    def test_provider_keys_are_forbidden_in_tool_call_output(self):
        assert "tool_call_output" in _key_rule(ProviderKind.CLAUDE).forbidden_outputs

    def test_provider_keys_are_forbidden_in_audit_payloads(self):
        assert _key_rule(ProviderKind.OLLAMA).audit_log_allowed is False
        assert "audit_payload" in _key_rule(ProviderKind.OLLAMA).forbidden_outputs

    def test_production_requires_env_secret_manager_style_storage(self):
        rule = _key_rule(ProviderKind.FUTURE_EXTERNAL)
        assert "environment" in rule.production_requirement
        assert "secret manager" in rule.production_requirement


class TestExecutionPolicy:
    def test_disabled_mode_denies_call_provider(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.OLLAMA,
            ProviderExecutionMode.DISABLED,
            allow_provider_call=True,
            has_provider_key=True,
        )
        assert policy.decision == ProviderDecision.DENIED

    def test_mock_mode_allows_no_external_call(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.MOCK,
            ProviderExecutionMode.MOCK,
            allow_provider_call=False,
            has_provider_key=False,
        )
        assert policy.decision == ProviderDecision.ALLOWED
        assert any("must not contact real providers" in warning for warning in policy.warnings)

    def test_dry_run_allows_prompt_preview_but_denies_call_provider(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.OLLAMA,
            ProviderExecutionMode.DRY_RUN,
            allow_provider_call=True,
            has_provider_key=True,
        )
        assert policy.decision == ProviderDecision.DENIED
        assert any("preview prompts" in blocker for blocker in policy.blockers)

    def test_local_mode_requires_explicit_allow_provider_call(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.OLLAMA,
            ProviderExecutionMode.LOCAL,
            allow_provider_call=False,
            has_provider_key=False,
        )
        assert policy.decision == ProviderDecision.REQUIRES_EXPLICIT_ALLOW
        assert "allow_provider_call" in policy.required_flags

    def test_local_mode_rejects_external_provider_kind(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.CODEX,
            ProviderExecutionMode.LOCAL,
            allow_provider_call=True,
            has_provider_key=True,
        )
        assert policy.decision == ProviderDecision.UNSUPPORTED
        assert any("local providers" in blocker for blocker in policy.blockers)

    def test_external_mode_requires_explicit_allow_provider_call_and_provider_key(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.CODEX,
            ProviderExecutionMode.EXTERNAL,
            allow_provider_call=True,
            has_provider_key=True,
        )
        assert policy.decision == ProviderDecision.ALLOWED
        assert "allow_provider_call" in policy.required_flags
        assert "provider_key_present" in policy.required_flags

    def test_external_mode_without_key_is_blocked(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.CLAUDE,
            ProviderExecutionMode.EXTERNAL,
            allow_provider_call=True,
            has_provider_key=False,
        )
        assert policy.decision == ProviderDecision.DENIED
        assert any("provider key" in blocker for blocker in policy.blockers)

    def test_allow_provider_call_false_blocks_external_call(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.CODEX,
            ProviderExecutionMode.EXTERNAL,
            allow_provider_call=False,
            has_provider_key=True,
        )
        assert policy.decision == ProviderDecision.DENIED
        assert any("allow_provider_call" in blocker for blocker in policy.blockers)

    def test_read_only_context_endpoints_are_provider_forbidden(self):
        policy = evaluate_provider_execution_policy(
            ProviderKind.OLLAMA,
            ProviderExecutionMode.LOCAL,
            allow_provider_call=True,
            has_provider_key=False,
        )
        assert "agent-execution-context" in policy.read_only_provider_forbidden_endpoints
        assert "project-context-cockpit" in policy.read_only_provider_forbidden_endpoints
        assert "delivery-summary" in policy.read_only_provider_forbidden_endpoints


class TestErrorHandling:
    def test_timeout_policy_is_bounded(self):
        policy = build_provider_error_handling_contract()
        assert policy.timeout_seconds > 0
        assert policy.timeout_seconds <= 300

    def test_retry_policy_is_bounded(self):
        policy = build_provider_error_handling_contract()
        assert policy.max_retries <= 2
        assert len(policy.retry_backoff_seconds) <= policy.max_retries

    def test_provider_unavailable_does_not_authorize_apply(self):
        text = "\n".join(build_provider_error_handling_contract().rules).lower()
        assert "without authorizing apply" in text

    def test_provider_error_does_not_bypass_guard_approval(self):
        text = "\n".join(build_provider_error_handling_contract().rules).lower()
        assert "must not bypass guard or approval" in text

    def test_provider_cancellation_is_safe_reportable(self):
        policy = build_provider_error_handling_contract()
        assert policy.cancellation_status == "cancelled"
        assert any("safe reportable state" in rule for rule in policy.rules)


class TestOperatorChecklist:
    def test_checklist_mentions_explicit_provider_enablement(self):
        text = "\n".join(build_provider_operator_checklist()).lower()
        assert "explicit provider enablement" in text

    def test_checklist_mentions_key_redaction(self):
        text = "\n".join(build_provider_operator_checklist()).lower()
        assert "redacted" in text or "redaction" in text

    def test_checklist_mentions_prompt_context_review(self):
        text = "\n".join(build_provider_operator_checklist()).lower()
        assert "prompt/context" in text

    def test_checklist_mentions_local_vs_external_provider_risk(self):
        text = "\n".join(build_provider_operator_checklist()).lower()
        assert "local providers and external providers" in text

    def test_checklist_mentions_timeout_retry_behavior(self):
        text = "\n".join(build_provider_operator_checklist()).lower()
        assert "timeout" in text
        assert "retry" in text


class TestAuditRedaction:
    def test_redact_provider_payload_for_audit_redacts_secret_like_keys(self):
        payload = {
            "summary": "ok",
            "api_key": "secret-value",
            "nested": {"authorization": "bearer token"},
            "items": [{"password": "pw"}, {"safe": "value"}],
        }
        redacted = redact_provider_payload_for_audit(payload)
        assert redacted["summary"] == "ok"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["nested"]["authorization"] == "[REDACTED]"
        assert redacted["items"][0]["password"] == "[REDACTED]"
        assert redacted["items"][1]["safe"] == "value"


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

    def test_contract_module_has_no_create_tool_call(self):
        source = inspect.getsource(contract)
        assert "create_tool_call" not in source

    def test_importing_contract_module_has_no_side_effects(self):
        loaded = importlib.import_module("src.release.provider_integration_hardening_contract")
        assert loaded.ProviderKind.OLLAMA.value == "ollama"

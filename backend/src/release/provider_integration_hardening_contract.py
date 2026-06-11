"""Pure Provider Integration Hardening Contract v1.

This module defines release-readiness contracts for future provider hardening.
It does not import runtime adapters, register routes, connect to storage,
start processes, contact networks, create audit records, or mutate app state.
"""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from pydantic import BaseModel, Field


class ProviderKind(str, Enum):
    OLLAMA = "ollama"
    CODEX = "codex"
    CLAUDE = "claude"
    MOCK = "mock"
    FUTURE_EXTERNAL = "future_external"


class ProviderExecutionMode(str, Enum):
    DISABLED = "disabled"
    MOCK = "mock"
    DRY_RUN = "dry_run"
    LOCAL = "local"
    EXTERNAL = "external"


class ProviderRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ProviderAction(str, Enum):
    BUILD_PROMPT = "build_prompt"
    PREVIEW_PROMPT = "preview_prompt"
    CALL_PROVIDER = "call_provider"
    STORE_PROVIDER_RESULT = "store_provider_result"
    REDACT_PROVIDER_OUTPUT = "redact_provider_output"
    RETRY_PROVIDER_CALL = "retry_provider_call"
    CANCEL_PROVIDER_CALL = "cancel_provider_call"
    CONFIGURE_PROVIDER_KEY = "configure_provider_key"
    INSPECT_PROVIDER_STATUS = "inspect_provider_status"


class ProviderDecision(str, Enum):
    ALLOWED = "allowed"
    DENIED = "denied"
    REQUIRES_EXPLICIT_ALLOW = "requires_explicit_allow"
    REQUIRES_OWNER = "requires_owner"
    UNSUPPORTED = "unsupported"


class ProviderDataSensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class ProviderCapability(BaseModel):
    provider: ProviderKind
    supports_streaming: bool = False
    supports_timeout: bool = True
    supports_cancellation: bool = False
    external_network_required: bool = False
    stores_remote_data_risk: bool = False
    notes: str = ""


class ProviderActionClassification(BaseModel):
    action: ProviderAction
    risk_level: ProviderRiskLevel
    calls_external_network: bool = False
    may_expose_project_context: bool = False
    requires_explicit_allow: bool = False
    requires_redaction: bool = False
    requires_audit_log: bool = False
    handles_secrets: bool = False
    notes: str = ""


class ProviderPromptBoundary(BaseModel):
    max_context_sections: int = 8
    include_source_of_truth: bool = True
    include_module_map: bool = True
    include_file_contents: bool = False
    include_provider_keys: bool = False
    include_secrets: bool = False
    allow_raw_project_dump: bool = False
    redaction_required: bool = True
    notes: list[str] = Field(default_factory=list)


class ProviderPromptBoundaryValidation(BaseModel):
    allowed: bool = True
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProviderKeyHandlingRule(BaseModel):
    provider: ProviderKind
    sensitivity: ProviderDataSensitivity = ProviderDataSensitivity.SECRET
    storage_allowed: bool = True
    allowed_storage_locations: list[str] = Field(default_factory=list)
    forbidden_outputs: list[str] = Field(default_factory=list)
    backup_behavior: str = "excluded_by_default"
    ui_display_allowed: bool = False
    audit_log_allowed: bool = False
    prompt_inclusion_allowed: bool = False
    production_requirement: str = "environment variable or secret manager"


class ProviderExecutionPolicy(BaseModel):
    mode: ProviderExecutionMode
    provider: ProviderKind
    decision: ProviderDecision
    required_flags: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_operator_confirmations: list[str] = Field(default_factory=list)
    read_only_provider_forbidden_endpoints: list[str] = Field(default_factory=list)


class ProviderErrorHandlingContract(BaseModel):
    timeout_seconds: int = 180
    max_retries: int = 1
    retry_backoff_seconds: list[int] = Field(default_factory=list)
    provider_unavailable_status: str = "provider_unavailable"
    cancellation_status: str = "cancelled"
    error_status: str = "failed"
    rules: list[str] = Field(default_factory=list)


READ_ONLY_PROVIDER_FORBIDDEN_ENDPOINTS: tuple[str, ...] = (
    "agent-execution-context",
    "project-context-cockpit",
    "delivery-summary",
    "delivery-report",
    "source-of-truth-preview",
    "module-map-preview",
    "patch-draft-context",
    "guard-proposal-validation",
)


def build_default_provider_capabilities() -> list[ProviderCapability]:
    return [
        ProviderCapability(
            provider=ProviderKind.OLLAMA,
            supports_streaming=False,
            supports_timeout=True,
            supports_cancellation=True,
            external_network_required=False,
            stores_remote_data_risk=False,
            notes="Local provider over localhost; still may receive project context.",
        ),
        ProviderCapability(
            provider=ProviderKind.CODEX,
            supports_streaming=False,
            supports_timeout=True,
            supports_cancellation=True,
            external_network_required=True,
            stores_remote_data_risk=True,
            notes="External provider or CLI integration; must remain explicitly gated.",
        ),
        ProviderCapability(
            provider=ProviderKind.CLAUDE,
            supports_streaming=False,
            supports_timeout=True,
            supports_cancellation=True,
            external_network_required=True,
            stores_remote_data_risk=True,
            notes="External provider or CLI integration; must remain explicitly gated.",
        ),
        ProviderCapability(
            provider=ProviderKind.MOCK,
            supports_streaming=False,
            supports_timeout=True,
            supports_cancellation=True,
            external_network_required=False,
            stores_remote_data_risk=False,
            notes="Deterministic test mode; no model execution.",
        ),
        ProviderCapability(
            provider=ProviderKind.FUTURE_EXTERNAL,
            supports_streaming=False,
            supports_timeout=True,
            supports_cancellation=False,
            external_network_required=True,
            stores_remote_data_risk=True,
            notes="Placeholder for future external providers; blocked until explicitly specified.",
        ),
    ]


def classify_provider_action(action: ProviderAction) -> ProviderActionClassification:
    if action == ProviderAction.BUILD_PROMPT:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.MEDIUM,
            may_expose_project_context=True,
            requires_redaction=True,
            notes="Builds bounded model context; no provider execution.",
        )
    if action == ProviderAction.PREVIEW_PROMPT:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.LOW,
            may_expose_project_context=True,
            requires_redaction=True,
            notes="Read-only prompt inspection for the operator.",
        )
    if action == ProviderAction.CALL_PROVIDER:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.HIGH,
            calls_external_network=True,
            may_expose_project_context=True,
            requires_explicit_allow=True,
            requires_redaction=True,
            requires_audit_log=True,
            notes="Provider execution requires explicit allow-provider intent.",
        )
    if action == ProviderAction.STORE_PROVIDER_RESULT:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.MEDIUM,
            requires_redaction=True,
            requires_audit_log=True,
            notes="Stored output must be bounded and redacted before persistence.",
        )
    if action == ProviderAction.REDACT_PROVIDER_OUTPUT:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.LOW,
            requires_audit_log=True,
            notes="Safety step that removes secret-like values before display or storage.",
        )
    if action == ProviderAction.RETRY_PROVIDER_CALL:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.HIGH,
            calls_external_network=True,
            may_expose_project_context=True,
            requires_explicit_allow=True,
            requires_redaction=True,
            requires_audit_log=True,
            notes="Retry must be bounded and must not repeat indefinitely.",
        )
    if action == ProviderAction.CANCEL_PROVIDER_CALL:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.MEDIUM,
            requires_audit_log=True,
            notes="Cancellation should leave safe reportable state.",
        )
    if action == ProviderAction.CONFIGURE_PROVIDER_KEY:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.CRITICAL,
            requires_explicit_allow=True,
            requires_redaction=True,
            requires_audit_log=True,
            handles_secrets=True,
            notes="Provider credentials are secret material.",
        )
    if action == ProviderAction.INSPECT_PROVIDER_STATUS:
        return ProviderActionClassification(
            action=action,
            risk_level=ProviderRiskLevel.LOW,
            notes="Availability/status check; no project context should be sent.",
        )
    return ProviderActionClassification(action=action, risk_level=ProviderRiskLevel.HIGH)


def build_default_prompt_boundary() -> ProviderPromptBoundary:
    return ProviderPromptBoundary(
        max_context_sections=8,
        include_source_of_truth=True,
        include_module_map=True,
        include_file_contents=False,
        include_provider_keys=False,
        include_secrets=False,
        allow_raw_project_dump=False,
        redaction_required=True,
        notes=[
            "Source of Truth and Module Map may be included only as bounded context.",
            "Project file contents are excluded by default.",
            "Provider keys, secrets, and raw project dumps are forbidden.",
        ],
    )


def validate_provider_prompt_boundary(boundary: ProviderPromptBoundary) -> ProviderPromptBoundaryValidation:
    blockers: list[str] = []
    warnings: list[str] = []

    if boundary.max_context_sections <= 0:
        blockers.append("Prompt boundary must allow at least one bounded context section.")
    if boundary.max_context_sections > 12:
        warnings.append("Prompt boundary has many context sections; review prompt size before provider execution.")
    if boundary.include_provider_keys:
        blockers.append("Provider keys must never be included in prompts.")
    if boundary.include_secrets:
        blockers.append("Secrets must never be included in prompts.")
    if boundary.allow_raw_project_dump:
        blockers.append("Raw full project dumps are not allowed by the provider prompt contract.")
    if boundary.include_file_contents:
        warnings.append("File contents require explicit future file-read permission and redaction review.")
    if not boundary.redaction_required:
        blockers.append("Provider prompt boundaries must require redaction.")

    return ProviderPromptBoundaryValidation(
        allowed=not blockers,
        blockers=blockers,
        warnings=warnings,
    )


def build_provider_key_handling_rules() -> list[ProviderKeyHandlingRule]:
    common_forbidden = [
        "ui_display",
        "tool_call_output",
        "audit_payload",
        "provider_prompt",
        "backup_manifest_default",
        "delivery_report",
    ]
    return [
        ProviderKeyHandlingRule(
            provider=provider,
            allowed_storage_locations=["environment", "local_secret_store", "production_secret_manager"],
            forbidden_outputs=common_forbidden,
            backup_behavior="excluded_by_default",
            ui_display_allowed=False,
            audit_log_allowed=False,
            prompt_inclusion_allowed=False,
        )
        for provider in (ProviderKind.OLLAMA, ProviderKind.CODEX, ProviderKind.CLAUDE, ProviderKind.FUTURE_EXTERNAL)
    ]


def evaluate_provider_execution_policy(
    provider: ProviderKind,
    mode: ProviderExecutionMode,
    allow_provider_call: bool,
    has_provider_key: bool,
) -> ProviderExecutionPolicy:
    read_only_forbidden = list(READ_ONLY_PROVIDER_FORBIDDEN_ENDPOINTS)

    if mode == ProviderExecutionMode.DISABLED:
        return ProviderExecutionPolicy(
            mode=mode,
            provider=provider,
            decision=ProviderDecision.DENIED,
            blockers=["Provider execution is disabled."],
            read_only_provider_forbidden_endpoints=read_only_forbidden,
        )

    if mode == ProviderExecutionMode.MOCK:
        return ProviderExecutionPolicy(
            mode=mode,
            provider=provider,
            decision=ProviderDecision.ALLOWED,
            warnings=["Mock mode must not contact real providers."],
            read_only_provider_forbidden_endpoints=read_only_forbidden,
        )

    if mode == ProviderExecutionMode.DRY_RUN:
        return ProviderExecutionPolicy(
            mode=mode,
            provider=provider,
            decision=ProviderDecision.DENIED,
            blockers=["Dry-run mode may build or preview prompts but must not call providers."],
            read_only_provider_forbidden_endpoints=read_only_forbidden,
        )

    if mode == ProviderExecutionMode.LOCAL:
        if provider != ProviderKind.OLLAMA:
            return ProviderExecutionPolicy(
                mode=mode,
                provider=provider,
                decision=ProviderDecision.UNSUPPORTED,
                blockers=["Local mode supports only explicitly local providers such as Ollama."],
                read_only_provider_forbidden_endpoints=read_only_forbidden,
            )
        if not allow_provider_call:
            return ProviderExecutionPolicy(
                mode=mode,
                provider=provider,
                decision=ProviderDecision.REQUIRES_EXPLICIT_ALLOW,
                required_flags=["allow_provider_call"],
                blockers=["Local provider execution still requires explicit allow_provider_call."],
                read_only_provider_forbidden_endpoints=read_only_forbidden,
            )
        return ProviderExecutionPolicy(
            mode=mode,
            provider=provider,
            decision=ProviderDecision.ALLOWED,
            required_flags=["allow_provider_call"],
            warnings=["Local model execution may still expose bounded project context to a local provider."],
            required_operator_confirmations=["review_prompt_boundary", "review_provider_audit_log"],
            read_only_provider_forbidden_endpoints=read_only_forbidden,
        )

    blockers: list[str] = []
    required_flags = ["allow_provider_call", "provider_key_present", "redaction_boundary", "audit_log"]
    if not allow_provider_call:
        blockers.append("External provider execution requires allow_provider_call=true.")
    if not has_provider_key:
        blockers.append("External provider execution requires a configured provider key.")
    if provider in {ProviderKind.MOCK, ProviderKind.OLLAMA}:
        blockers.append("External mode must target an external provider.")

    return ProviderExecutionPolicy(
        mode=mode,
        provider=provider,
        decision=ProviderDecision.DENIED if blockers else ProviderDecision.ALLOWED,
        required_flags=required_flags,
        blockers=blockers,
        warnings=["External provider execution is high risk and forbidden from read-only endpoints."],
        required_operator_confirmations=["review_prompt_boundary", "confirm_external_provider_use", "review_redaction"],
        read_only_provider_forbidden_endpoints=read_only_forbidden,
    )


def redact_provider_payload_for_audit(payload: Mapping[str, object]) -> dict[str, object]:
    redacted: dict[str, object] = {}
    secret_markers = ("key", "token", "secret", "password", "credential", "authorization")
    for key, value in payload.items():
        lowered = key.lower()
        if any(marker in lowered for marker in secret_markers):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, Mapping):
            redacted[key] = redact_provider_payload_for_audit(value)
        elif isinstance(value, list):
            redacted[key] = [
                redact_provider_payload_for_audit(item) if isinstance(item, Mapping) else item
                for item in value
            ]
        else:
            redacted[key] = value
    return redacted


def build_provider_error_handling_contract() -> ProviderErrorHandlingContract:
    return ProviderErrorHandlingContract(
        timeout_seconds=180,
        max_retries=1,
        retry_backoff_seconds=[2],
        provider_unavailable_status="provider_unavailable",
        cancellation_status="cancelled",
        error_status="failed",
        rules=[
            "Provider timeouts must not retry indefinitely.",
            "Provider unavailable states must fail safely without authorizing apply.",
            "Provider errors must not bypass guard or approval checks.",
            "Provider cancellation must be recorded as safe reportable state when supported.",
            "Retry attempts must reuse the same prompt boundary and redaction requirements.",
        ],
    )


def build_provider_operator_checklist() -> list[str]:
    return [
        "Confirm provider mode and explicit provider enablement before any real provider execution.",
        "Review prompt/context boundaries before local or external provider use.",
        "Keep provider keys redacted from UI, prompts, audit payloads, tool call outputs, and backups.",
        "Treat local providers and external providers as different privacy and network-risk tiers.",
        "Verify timeout, cancellation, and bounded retry behavior before relying on provider output.",
        "Confirm read-only endpoints do not call providers.",
    ]

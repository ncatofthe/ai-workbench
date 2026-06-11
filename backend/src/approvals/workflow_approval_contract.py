"""Pure approval request contract for future workflow-gated actions.

This module defines the shape and validation rules for future semi-auto
approval requests.  It intentionally does not persist anything, execute tools,
call providers, create tool calls, or mutate runtime state.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────


class WorkflowApprovalAction(str, enum.Enum):
    CREATE_PROPOSAL = "create_proposal"
    APPLY_PATCH = "apply_patch"
    RUN_TESTS = "run_tests"
    ANALYZE_RESULT = "analyze_result"
    ROLLBACK_PATCH = "rollback_patch"
    EXTERNAL_PROVIDER_EXECUTION = "external_provider_execution"


class WorkflowApprovalStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class WorkflowApprovalRisk(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowApprovalRequirement(str, enum.Enum):
    MANUAL_CONFIRMATION = "manual_confirmation"
    EXPLICIT_CHECKBOX = "explicit_checkbox"
    PROTECTED_FILE_REVIEW = "protected_file_review"
    COMMAND_ALLOWLIST_CHECK = "command_allowlist_check"
    PROVIDER_PERMISSION_CHECK = "provider_permission_check"


# ── Sensitive/protected payload guardrails ───────────────────────────────────


_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_PROTECTED_PATH_RE = re.compile(
    r"(^|/)(\.env(?:\..*)?|.*\.pem|.*\.key|.*\.p12|.*\.pfx|id_rsa|id_ed25519)$",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _contains_secret_assignment(value: str) -> bool:
    return bool(_SENSITIVE_VALUE_RE.search(value))


def _validate_payload_has_no_secret_values(value: Any, path: str = "payload") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text):
                raise ValueError(f"{path}.{key_text} must not store secret-like keys")
            _validate_payload_has_no_secret_values(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_payload_has_no_secret_values(nested, f"{path}[{index}]")
    elif isinstance(value, str) and _contains_secret_assignment(value):
        raise ValueError(f"{path} must not store secret-like values")


def _path_is_protected(path: str) -> bool:
    return bool(_PROTECTED_PATH_RE.search(path.strip()))


# ── Contract models ──────────────────────────────────────────────────────────


class WorkflowApprovalPayloadSummary(BaseModel):
    """Bounded summary of the future action payload.

    The summary is intentionally metadata-like.  It should never contain raw
    secrets, complete patch bodies, command outputs, or provider prompts.
    """

    description: str = ""
    affected_files: list[str] = Field(default_factory=list)
    command: Optional[str] = None
    provider: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    contains_protected_paths: bool = False
    contains_secret_like_values: bool = False

    @field_validator("metadata")
    @classmethod
    def _metadata_has_no_secret_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_payload_has_no_secret_values(value, "metadata")
        return value

    @field_validator("description", "command", "provider")
    @classmethod
    def _text_has_no_secret_assignments(cls, value: Optional[str]) -> Optional[str]:
        if value and _contains_secret_assignment(value):
            raise ValueError("payload summary text must not store secret-like values")
        return value

    @field_validator("affected_files")
    @classmethod
    def _affected_files_have_no_secret_assignments(cls, value: list[str]) -> list[str]:
        for path in value:
            if _contains_secret_assignment(path):
                raise ValueError("affected_files must not store secret-like values")
        return value


class WorkflowApprovalRequestContract(BaseModel):
    """Future approval request contract for a gated workflow action."""

    id: str
    action: WorkflowApprovalAction
    title: str
    reason: str
    risk_level: WorkflowApprovalRisk
    payload_summary: WorkflowApprovalPayloadSummary = Field(default_factory=WorkflowApprovalPayloadSummary)
    required_confirmations: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    status: WorkflowApprovalStatus = WorkflowApprovalStatus.DRAFT
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    project_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    expires_at: Optional[str] = None
    approved_by: Optional[str] = None
    decision_reason: Optional[str] = None
    executable_in_v1: bool = False


class WorkflowApprovalDecisionContract(BaseModel):
    """Decision record shape for a future approval request."""

    id: str
    approval_request_id: str
    status: WorkflowApprovalStatus
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    decided_at: str = Field(default_factory=_now_iso)


class WorkflowApprovalValidationResult(BaseModel):
    valid: bool
    executable_in_v1: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Risk rules ───────────────────────────────────────────────────────────────


_ACTION_RULES: dict[
    WorkflowApprovalAction,
    tuple[WorkflowApprovalRisk, list[WorkflowApprovalRequirement], str],
] = {
    WorkflowApprovalAction.CREATE_PROPOSAL: (
        WorkflowApprovalRisk.MEDIUM,
        [WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
        "Creating a proposal changes review state in a future semi-auto flow.",
    ),
    WorkflowApprovalAction.APPLY_PATCH: (
        WorkflowApprovalRisk.HIGH,
        [
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
            WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
        ],
        "Applying a patch changes files and must require explicit operator confirmation.",
    ),
    WorkflowApprovalAction.RUN_TESTS: (
        WorkflowApprovalRisk.MEDIUM,
        [
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.COMMAND_ALLOWLIST_CHECK,
        ],
        "Running tests executes an allowlisted command and must stay gated.",
    ),
    WorkflowApprovalAction.ANALYZE_RESULT: (
        WorkflowApprovalRisk.LOW,
        [WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
        "Analyzing results is low risk but remains non-executable in this contract slice.",
    ),
    WorkflowApprovalAction.ROLLBACK_PATCH: (
        WorkflowApprovalRisk.HIGH,
        [
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
            WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
        ],
        "Rollback can change files and must require explicit operator confirmation.",
    ),
    WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION: (
        WorkflowApprovalRisk.CRITICAL,
        [
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.PROVIDER_PERMISSION_CHECK,
        ],
        "External provider execution is not enabled in v1 and must be explicitly permissioned later.",
    ),
}


def classify_workflow_approval_action(
    action: WorkflowApprovalAction,
) -> tuple[WorkflowApprovalRisk, list[WorkflowApprovalRequirement], str, bool]:
    """Return risk, required confirmations, reason, and v1 executability.

    Pure helper — classification only, no execution.
    """

    risk, requirements, reason = _ACTION_RULES[action]
    return risk, list(requirements), reason, False


def build_workflow_approval_request(
    *,
    id: str,
    action: WorkflowApprovalAction,
    title: Optional[str] = None,
    reason: Optional[str] = None,
    payload_summary: Optional[WorkflowApprovalPayloadSummary] = None,
    status: WorkflowApprovalStatus = WorkflowApprovalStatus.DRAFT,
    run_id: Optional[str] = None,
    step_id: Optional[str] = None,
    project_id: Optional[str] = None,
    expires_at: Optional[str] = None,
) -> WorkflowApprovalRequestContract:
    """Build a classified approval request contract without persistence."""

    risk, requirements, default_reason, executable = classify_workflow_approval_action(action)
    return WorkflowApprovalRequestContract(
        id=id,
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        action=action,
        status=status,
        risk_level=risk,
        title=title or action.value.replace("_", " ").title(),
        reason=reason or default_reason,
        payload_summary=payload_summary or WorkflowApprovalPayloadSummary(),
        required_confirmations=requirements,
        created_at=_now_iso(),
        expires_at=expires_at,
        executable_in_v1=executable,
    )


def validate_workflow_approval_request(
    request: WorkflowApprovalRequestContract,
) -> WorkflowApprovalValidationResult:
    """Validate approval request contract safety without side effects."""

    errors: list[str] = []
    warnings: list[str] = []
    expected_risk, expected_requirements, _, executable = classify_workflow_approval_action(request.action)

    if request.risk_level != expected_risk:
        errors.append(f"risk_level must be {expected_risk.value} for {request.action.value}")

    missing_requirements = [
        requirement
        for requirement in expected_requirements
        if requirement not in request.required_confirmations
    ]
    if missing_requirements:
        missing = ", ".join(requirement.value for requirement in missing_requirements)
        errors.append(f"missing required confirmations: {missing}")

    protected_paths = [
        path
        for path in request.payload_summary.affected_files
        if _path_is_protected(path)
    ]
    if protected_paths and WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW not in request.required_confirmations:
        errors.append("protected paths require protected_file_review confirmation")
    if protected_paths and not request.payload_summary.contains_protected_paths:
        warnings.append("payload_summary contains protected paths but contains_protected_paths is false")

    if request.payload_summary.contains_secret_like_values:
        errors.append("payload_summary must not contain raw secret-like values")

    if request.action == WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION:
        warnings.append("external_provider_execution is critical and not executable in v1")
    if request.status == WorkflowApprovalStatus.APPROVED:
        warnings.append("approved status is a future decision state; this contract slice does not execute actions")

    return WorkflowApprovalValidationResult(
        valid=not errors,
        executable_in_v1=executable,
        errors=errors,
        warnings=warnings,
    )

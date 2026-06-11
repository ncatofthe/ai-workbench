"""Pure storage-facing contract for future workflow approval requests.

This module describes how approval requests can be represented in future
storage.  It intentionally does not implement DB access, migrations, API
handlers, tool execution, provider calls, or runtime side effects.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from src.approvals.workflow_approval_contract import (
    WorkflowApprovalAction,
    WorkflowApprovalRequirement,
    WorkflowApprovalRisk,
    classify_workflow_approval_action,
)


# ── Enums ────────────────────────────────────────────────────────────────────


class WorkflowApprovalStorageStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class WorkflowApprovalLinkScope(str, enum.Enum):
    STANDALONE = "standalone"
    PROJECT = "project"
    RUN = "run"
    STEP = "step"
    TOOL_CALL = "tool_call"
    INTAKE_SESSION = "intake_session"


# ── Guardrails ───────────────────────────────────────────────────────────────


MAX_SUMMARY_TEXT_LENGTH = 2_000
MAX_COMMAND_SUMMARY_LENGTH = 500
MAX_PROVIDER_SUMMARY_LENGTH = 500
MAX_METADATA_TEXT_LENGTH = 1_000
MAX_AFFECTED_FILES = 100
MAX_PAYLOAD_SIZE_BYTES = 16_000

_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_UNSAFE_RAW_PAYLOAD_KEY_RE = re.compile(
    r"(stdout|stderr|raw[_-]?output|provider[_-]?prompt|full[_-]?prompt|patch[_-]?body|raw[_-]?patch|full[_-]?diff)",
    re.IGNORECASE,
)
_PROTECTED_PATH_RE = re.compile(
    r"(^|/)(\.env(?:\..*)?|.*\.pem|.*\.key|.*\.p12|.*\.pfx|id_rsa|id_ed25519)$",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _parse_iso_datetime(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _contains_secret_assignment(value: str) -> bool:
    return bool(_SENSITIVE_VALUE_RE.search(value))


def _path_is_protected(path: str) -> bool:
    return bool(_PROTECTED_PATH_RE.search(path.strip()))


def _validate_safe_text(value: str, *, field_name: str, max_length: int) -> None:
    if len(value) > max_length:
        raise ValueError(f"{field_name} is too large for a storage summary")
    if _contains_secret_assignment(value):
        raise ValueError(f"{field_name} must not store secret-like values")
    if "-----BEGIN PRIVATE KEY-----" in value:
        raise ValueError(f"{field_name} must not store private key material")
    if "\ndiff --git " in value or value.startswith("diff --git "):
        raise ValueError(f"{field_name} must not store full patch/diff bodies")


def _validate_metadata(value: Any, path: str = "metadata") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text):
                raise ValueError(f"{path}.{key_text} must not store secret-like keys")
            if _UNSAFE_RAW_PAYLOAD_KEY_RE.search(key_text):
                raise ValueError(f"{path}.{key_text} must not store raw execution payloads")
            _validate_metadata(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_metadata(nested, f"{path}[{index}]")
    elif isinstance(value, str):
        _validate_safe_text(value, field_name=path, max_length=MAX_METADATA_TEXT_LENGTH)


# ── Storage-facing models ────────────────────────────────────────────────────


class WorkflowApprovalStoredPayloadSummary(BaseModel):
    """Sanitized payload summary intended for future DB storage."""

    description: str = ""
    affected_files: list[str] = Field(default_factory=list)
    command_summary: Optional[str] = None
    provider_summary: Optional[str] = None
    patch_summary: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    contains_protected_paths: bool = False
    contains_secret_like_values: bool = False
    raw_payload_omitted: bool = True
    payload_size_bytes: int = 0

    @field_validator("description", "command_summary", "provider_summary", "patch_summary")
    @classmethod
    def _summary_text_is_bounded_and_safe(cls, value: Optional[str], info: Any) -> Optional[str]:
        if value is None:
            return value
        max_length = MAX_COMMAND_SUMMARY_LENGTH if info.field_name == "command_summary" else MAX_SUMMARY_TEXT_LENGTH
        if info.field_name == "provider_summary":
            max_length = MAX_PROVIDER_SUMMARY_LENGTH
        _validate_safe_text(value, field_name=info.field_name, max_length=max_length)
        return value

    @field_validator("affected_files")
    @classmethod
    def _affected_files_are_bounded_and_safe(cls, value: list[str]) -> list[str]:
        if len(value) > MAX_AFFECTED_FILES:
            raise ValueError("affected_files exceeds storage summary limit")
        for path in value:
            _validate_safe_text(path, field_name="affected_files", max_length=500)
        return value

    @field_validator("metadata")
    @classmethod
    def _metadata_is_safe(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_metadata(value)
        return value

    @field_validator("payload_size_bytes")
    @classmethod
    def _payload_size_is_bounded(cls, value: int) -> int:
        if value < 0:
            raise ValueError("payload_size_bytes cannot be negative")
        if value > MAX_PAYLOAD_SIZE_BYTES:
            raise ValueError("payload summary is too large for storage contract")
        return value


class WorkflowApprovalStorageRecord(BaseModel):
    """Future DB-facing shape for one workflow approval request."""

    id: str
    action: WorkflowApprovalAction
    status: WorkflowApprovalStorageStatus
    risk_level: WorkflowApprovalRisk
    title: str
    reason: str
    payload_summary_json: WorkflowApprovalStoredPayloadSummary = Field(default_factory=WorkflowApprovalStoredPayloadSummary)
    required_confirmations: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    tool_call_id: Optional[str] = None
    intake_session_id: Optional[str] = None
    policy_version: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    expires_at: Optional[str] = None
    decided_at: Optional[str] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    decision_reason: Optional[str] = None
    stale_reason: Optional[str] = None
    execution_attempted_at: Optional[str] = None


class WorkflowApprovalDecisionRecord(BaseModel):
    """Future auditable decision row shape."""

    id: str
    approval_request_id: str
    status: WorkflowApprovalStorageStatus
    decided_at: str = Field(default_factory=_now_iso)
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None


class WorkflowApprovalExecutionLink(BaseModel):
    """Future post-execution link to the tool_call audit record."""

    approval_request_id: str
    tool_call_id: str
    execution_attempted_at: str = Field(default_factory=_now_iso)
    execution_status: str = "attempted"
    error_summary: Optional[str] = None


class WorkflowApprovalStorageSnapshot(BaseModel):
    """Serializable storage aggregate for future APIs."""

    record: WorkflowApprovalStorageRecord
    decisions: list[WorkflowApprovalDecisionRecord] = Field(default_factory=list)
    execution_link: Optional[WorkflowApprovalExecutionLink] = None


class WorkflowApprovalStatusTransition(BaseModel):
    from_status: WorkflowApprovalStorageStatus
    to_status: WorkflowApprovalStorageStatus
    allowed: bool
    reason: str


class WorkflowApprovalStorageValidationResult(BaseModel):
    valid: bool
    executable: bool = False
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Pure helpers ─────────────────────────────────────────────────────────────


_ALLOWED_TRANSITIONS: set[tuple[WorkflowApprovalStorageStatus, WorkflowApprovalStorageStatus]] = {
    (WorkflowApprovalStorageStatus.DRAFT, WorkflowApprovalStorageStatus.PENDING),
    (WorkflowApprovalStorageStatus.PENDING, WorkflowApprovalStorageStatus.APPROVED),
    (WorkflowApprovalStorageStatus.PENDING, WorkflowApprovalStorageStatus.REJECTED),
    (WorkflowApprovalStorageStatus.PENDING, WorkflowApprovalStorageStatus.CANCELLED),
    (WorkflowApprovalStorageStatus.PENDING, WorkflowApprovalStorageStatus.EXPIRED),
}

_TERMINAL_STATUSES: set[WorkflowApprovalStorageStatus] = {
    WorkflowApprovalStorageStatus.REJECTED,
    WorkflowApprovalStorageStatus.EXPIRED,
    WorkflowApprovalStorageStatus.CANCELLED,
}


def can_transition_approval_status(
    from_status: WorkflowApprovalStorageStatus,
    to_status: WorkflowApprovalStorageStatus,
) -> bool:
    """Return whether a future stored approval may move between statuses."""

    return (from_status, to_status) in _ALLOWED_TRANSITIONS


def describe_approval_status_transition(
    from_status: WorkflowApprovalStorageStatus,
    to_status: WorkflowApprovalStorageStatus,
) -> WorkflowApprovalStatusTransition:
    """Return a structured transition decision without side effects."""

    allowed = can_transition_approval_status(from_status, to_status)
    reason = "Allowed storage lifecycle transition." if allowed else "Transition is not allowed by storage contract."
    return WorkflowApprovalStatusTransition(
        from_status=from_status,
        to_status=to_status,
        allowed=allowed,
        reason=reason,
    )


def _expected_requirements(action: WorkflowApprovalAction) -> list[WorkflowApprovalRequirement]:
    _, requirements, _, _ = classify_workflow_approval_action(action)
    return requirements


def _is_expired(record: WorkflowApprovalStorageRecord, now: Optional[datetime]) -> bool:
    if record.expires_at is None:
        return False
    expiry = _parse_iso_datetime(record.expires_at)
    if expiry is None:
        return False
    return (now or datetime.now()) >= expiry


def validate_approval_storage_record(
    record: WorkflowApprovalStorageRecord,
) -> WorkflowApprovalStorageValidationResult:
    """Validate future storage shape and safety invariants without DB access."""

    errors: list[str] = []
    warnings: list[str] = []
    expected_risk, expected_requirements, _, _ = classify_workflow_approval_action(record.action)

    if record.risk_level != expected_risk:
        errors.append(f"risk_level must be {expected_risk.value} for {record.action.value}")

    missing = [
        requirement
        for requirement in expected_requirements
        if requirement not in record.required_confirmations
    ]
    if missing:
        errors.append(
            "missing required confirmations: "
            + ", ".join(requirement.value for requirement in missing)
        )

    protected_paths = [
        path
        for path in record.payload_summary_json.affected_files
        if _path_is_protected(path)
    ]
    if protected_paths and not record.payload_summary_json.contains_protected_paths:
        warnings.append("payload summary contains protected paths but contains_protected_paths is false")
    if protected_paths and WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW not in record.required_confirmations:
        errors.append("protected paths require protected_file_review confirmation")

    if record.payload_summary_json.contains_secret_like_values:
        errors.append("payload summary must not contain raw secret-like values")
    if not record.payload_summary_json.raw_payload_omitted:
        errors.append("raw payload must be omitted from storage-facing approval summary")

    if record.expires_at and _parse_iso_datetime(record.expires_at) is None:
        errors.append("expires_at must be an ISO datetime when provided")
    if record.decided_at and _parse_iso_datetime(record.decided_at) is None:
        errors.append("decided_at must be an ISO datetime when provided")
    if record.execution_attempted_at and _parse_iso_datetime(record.execution_attempted_at) is None:
        errors.append("execution_attempted_at must be an ISO datetime when provided")

    if record.status in _TERMINAL_STATUSES and record.tool_call_id:
        errors.append("terminal approvals must not be linked to new execution attempts")
    if record.tool_call_id and not record.execution_attempted_at:
        errors.append("tool_call_id requires execution_attempted_at")
    if record.execution_attempted_at and not record.tool_call_id:
        warnings.append("execution_attempted_at is set without tool_call_id")
    if record.status == WorkflowApprovalStorageStatus.APPROVED and not record.decided_at:
        warnings.append("approved records should store decided_at before execution")
    if record.status == WorkflowApprovalStorageStatus.REJECTED and not record.rejected_by:
        warnings.append("rejected records should identify rejected_by when possible")

    executable = is_approval_executable_from_storage(record) if not errors else False
    return WorkflowApprovalStorageValidationResult(
        valid=not errors,
        executable=executable,
        errors=errors,
        warnings=warnings,
    )


def is_approval_executable_from_storage(
    record: WorkflowApprovalStorageRecord,
    now: Optional[datetime] = None,
) -> bool:
    """Return whether a stored approval can reach a future execute endpoint.

    This helper does not execute anything.  It only describes the boundary that
    future execution code must re-check.
    """

    if record.status != WorkflowApprovalStorageStatus.APPROVED:
        return False
    if record.action == WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION:
        return False
    if record.stale_reason:
        return False
    if record.tool_call_id or record.execution_attempted_at:
        return False
    if _is_expired(record, now):
        return False
    if record.payload_summary_json.contains_secret_like_values:
        return False
    if not record.payload_summary_json.raw_payload_omitted:
        return False

    expected_requirements = _expected_requirements(record.action)
    return all(requirement in record.required_confirmations for requirement in expected_requirements)


def build_approval_storage_snapshot(
    record: WorkflowApprovalStorageRecord,
    decisions: Optional[list[WorkflowApprovalDecisionRecord]] = None,
    execution_link: Optional[WorkflowApprovalExecutionLink] = None,
) -> WorkflowApprovalStorageSnapshot:
    """Build an in-memory storage snapshot without persistence side effects."""

    return WorkflowApprovalStorageSnapshot(
        record=record,
        decisions=decisions or [],
        execution_link=execution_link,
    )

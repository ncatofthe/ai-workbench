"""Pure contract models for future persisted intake sessions.

This module defines the shape AI Workbench can persist later when intake
previews become user-confirmed sessions.  It intentionally contains no DB
access, no route handlers, no tool calls, no provider calls, and no side
effects.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Enums ────────────────────────────────────────────────────────────────────


class IntakeSessionStatus(str, enum.Enum):
    DRAFT = "draft"
    NEEDS_ANSWERS = "needs_answers"
    READY_TO_PLAN = "ready_to_plan"
    READY_TO_CREATE_RUN = "ready_to_create_run"
    ARCHIVED = "archived"


class IntakeSourceMode(str, enum.Enum):
    NEW_PROJECT = "new_project"
    EXISTING_PROJECT = "existing_project"
    UNKNOWN = "unknown"


class IntakeVersionKind(str, enum.Enum):
    INTAKE_RESPONSE = "intake_response"
    BRIEF_DRAFT = "brief_draft"
    PLAN_PREVIEW = "plan_preview"


class IntakeSelectionStatus(str, enum.Enum):
    UNSELECTED = "unselected"
    SELECTED = "selected"
    SUPERSEDED = "superseded"


# ── Sensitive-value guardrails ───────────────────────────────────────────────


_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _looks_like_secret_value(value: str) -> bool:
    return bool(_SENSITIVE_VALUE_RE.search(value))


def _validate_safe_metadata(value: Any, path: str = "source_metadata") -> None:
    """Reject obvious secret-bearing metadata keys or values.

    Project paths, ignore rules, and notes about `.env` are valid metadata.
    Actual secret-like key names or assignment values are not.
    """

    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text):
                raise ValueError(f"{path}.{key_text} must not store secret-like keys")
            _validate_safe_metadata(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_safe_metadata(nested, f"{path}[{index}]")
    elif isinstance(value, str) and _looks_like_secret_value(value):
        raise ValueError(f"{path} must not store secret-like values")


# ── Contract models ──────────────────────────────────────────────────────────


class IntakeSessionContract(BaseModel):
    """Future persistence boundary for intake before Project/Run creation."""

    id: str
    raw_idea: str
    mode: IntakeSourceMode = IntakeSourceMode.UNKNOWN
    status: IntakeSessionStatus = IntakeSessionStatus.DRAFT
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    selected_brief_version_id: Optional[str] = None
    selected_plan_version_id: Optional[str] = None
    readiness: str = "draft"
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: Optional[str] = None

    @field_validator("source_metadata")
    @classmethod
    def _source_metadata_has_no_secrets(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_metadata(value)
        return value


class IntakeAnswerContract(BaseModel):
    """A user answer snapshot for a generated intake question."""

    id: str
    session_id: str
    question_id: str
    category: str
    priority: str
    question_text_snapshot: str
    answer_text: str = ""
    is_sensitive: bool = False
    redacted: bool = False
    created_at: str = Field(default_factory=_now_iso)
    updated_at: Optional[str] = None

    @model_validator(mode="after")
    def _answer_has_no_unredacted_secrets(self) -> "IntakeAnswerContract":
        if _looks_like_secret_value(self.answer_text):
            raise ValueError("answer_text must not store secret-like assignment values")
        if self.is_sensitive and self.answer_text.strip() and not self.redacted:
            raise ValueError("sensitive answers must be redacted before persistence")
        return self


class IntakeBriefVersionContract(BaseModel):
    """Versioned project brief draft contract."""

    id: str
    session_id: str
    version_number: int = Field(ge=1)
    kind: IntakeVersionKind = IntakeVersionKind.BRIEF_DRAFT
    title: str = "Project Brief Draft"
    markdown: str = ""
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    selection_status: IntakeSelectionStatus = IntakeSelectionStatus.UNSELECTED
    created_at: str = Field(default_factory=_now_iso)


class IntakePlanVersionContract(BaseModel):
    """Versioned development plan preview contract."""

    id: str
    session_id: str
    version_number: int = Field(ge=1)
    kind: IntakeVersionKind = IntakeVersionKind.PLAN_PREVIEW
    title: str = "Development Plan Preview"
    structured_payload: dict[str, Any] = Field(default_factory=dict)
    selection_status: IntakeSelectionStatus = IntakeSelectionStatus.UNSELECTED
    created_at: str = Field(default_factory=_now_iso)


class IntakeSessionSnapshot(BaseModel):
    """Serializable session aggregate shape for future storage APIs."""

    session: IntakeSessionContract
    answers: list[IntakeAnswerContract] = Field(default_factory=list)
    brief_versions: list[IntakeBriefVersionContract] = Field(default_factory=list)
    plan_versions: list[IntakePlanVersionContract] = Field(default_factory=list)


class IntakeContractValidationResult(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ── Pure helpers ─────────────────────────────────────────────────────────────


def build_intake_session_snapshot(
    session: IntakeSessionContract,
    answers: Optional[list[IntakeAnswerContract]] = None,
    brief_versions: Optional[list[IntakeBriefVersionContract]] = None,
    plan_versions: Optional[list[IntakePlanVersionContract]] = None,
) -> IntakeSessionSnapshot:
    """Build an in-memory snapshot without persistence side effects."""

    return IntakeSessionSnapshot(
        session=session,
        answers=answers or [],
        brief_versions=brief_versions or [],
        plan_versions=plan_versions or [],
    )


def validate_intake_session_contract(
    snapshot: IntakeSessionSnapshot,
) -> IntakeContractValidationResult:
    """Validate cross-object contract consistency without touching storage."""

    errors: list[str] = []
    warnings: list[str] = []
    session_id = snapshot.session.id

    for answer in snapshot.answers:
        if answer.session_id != session_id:
            errors.append(f"answer {answer.id} points to a different session")

    brief_ids = {version.id for version in snapshot.brief_versions}
    plan_ids = {version.id for version in snapshot.plan_versions}

    for version in snapshot.brief_versions:
        if version.session_id != session_id:
            errors.append(f"brief version {version.id} points to a different session")
    for version in snapshot.plan_versions:
        if version.session_id != session_id:
            errors.append(f"plan version {version.id} points to a different session")

    if snapshot.session.selected_brief_version_id and snapshot.session.selected_brief_version_id not in brief_ids:
        errors.append("selected_brief_version_id does not match a brief version in the snapshot")
    if snapshot.session.selected_plan_version_id and snapshot.session.selected_plan_version_id not in plan_ids:
        errors.append("selected_plan_version_id does not match a plan version in the snapshot")

    selected_briefs = [
        version.id
        for version in snapshot.brief_versions
        if version.selection_status == IntakeSelectionStatus.SELECTED
    ]
    selected_plans = [
        version.id
        for version in snapshot.plan_versions
        if version.selection_status == IntakeSelectionStatus.SELECTED
    ]
    if len(selected_briefs) > 1:
        errors.append("only one brief version can be selected at a time")
    if len(selected_plans) > 1:
        errors.append("only one plan version can be selected at a time")

    if snapshot.session.status == IntakeSessionStatus.READY_TO_CREATE_RUN and not snapshot.session.selected_plan_version_id:
        warnings.append("ready_to_create_run sessions should identify a selected plan before run creation")
    if snapshot.session.run_id and snapshot.session.status != IntakeSessionStatus.READY_TO_CREATE_RUN:
        warnings.append("run_id should normally be attached only after explicit create-run confirmation")

    return IntakeContractValidationResult(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


def summarize_intake_session_lifecycle(snapshot: IntakeSessionSnapshot) -> str:
    """Return a human-readable lifecycle summary for reports and tests."""

    session = snapshot.session
    brief_count = len(snapshot.brief_versions)
    plan_count = len(snapshot.plan_versions)
    return (
        f"IntakeSession {session.id} is a separate {session.status.value} contract for "
        f"{session.mode.value}. It may hold {len(snapshot.answers)} answers, "
        f"{brief_count} brief versions, and {plan_count} plan versions before any "
        "Project or Run is created. Project/Run attachment happens later only after "
        "explicit user confirmation."
    )

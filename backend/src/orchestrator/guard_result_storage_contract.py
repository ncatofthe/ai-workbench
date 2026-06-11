"""Pure storage-facing contract for future Source-of-Truth Guard results.

This module describes how guard checks can be represented in future storage.
It intentionally does not implement DB access, API routes, migrations, tool
execution, provider calls, patch execution, or runtime side effects.
"""

from __future__ import annotations

import enum
import hashlib
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class WorkflowGuardDecision(str, enum.Enum):
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


class WorkflowGuardDriftRisk(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowGuardStaleReason(str, enum.Enum):
    PATCH_FORM_CHANGED = "patch_form_changed"
    FILE_PATH_CHANGED = "file_path_changed"
    PROPOSED_ACTION_CHANGED = "proposed_action_changed"
    PATCH_SUMMARY_CHANGED = "patch_summary_changed"
    OLD_TEXT_CHANGED = "old_text_changed"
    NEW_TEXT_CHANGED = "new_text_changed"
    REQUIREMENT_CONTEXT_CHANGED = "requirement_context_changed"
    SOURCE_OF_TRUTH_CHANGED = "source_of_truth_changed"
    COVERAGE_CHANGED = "coverage_changed"
    EXPIRED = "expired"
    PROPOSAL_PAYLOAD_MISMATCH = "proposal_payload_mismatch"
    MANUAL_INVALIDATION = "manual_invalidation"


class WorkflowGuardSource(str, enum.Enum):
    RUN_STEP_GUARD = "run_step_guard"
    PATCH_PROPOSAL_GATE = "patch_proposal_gate"
    MANUAL_CHECK = "manual_check"
    FUTURE_AUTOMATION = "future_automation"


# ── Contract models ──────────────────────────────────────────────────────────


class WorkflowGuardInputSnapshot(BaseModel):
    proposed_action: str
    file_path: Optional[str] = None
    patch_summary: Optional[str] = None
    old_text_hash: Optional[str] = None
    new_text_hash: Optional[str] = None
    input_hash: str


class WorkflowGuardRequirementContextSnapshot(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    coverage_status: str = ""
    drift_risk: WorkflowGuardDriftRisk | str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)
    source_of_truth_summary: str = ""
    context_hash: str


class WorkflowGuardResultSnapshot(BaseModel):
    decision: WorkflowGuardDecision
    drift_risk: WorkflowGuardDriftRisk
    matched_requirement_ids: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)
    forbidden_change_hits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""
    result_hash: str


class WorkflowGuardResultRecord(BaseModel):
    id: str
    project_id: Optional[str] = None
    run_id: str
    step_id: str
    proposal_tool_call_id: Optional[str] = None
    apply_tool_call_id: Optional[str] = None
    source: WorkflowGuardSource
    input_snapshot: WorkflowGuardInputSnapshot
    requirement_context_snapshot: WorkflowGuardRequirementContextSnapshot
    result_snapshot: WorkflowGuardResultSnapshot
    warning_acknowledged: bool = False
    no_guard_override: bool = False
    is_stale: bool = False
    stale_reasons: list[WorkflowGuardStaleReason] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class WorkflowGuardProposalLink(BaseModel):
    guard_result_id: str
    proposal_tool_call_id: str
    linked_at: datetime = Field(default_factory=datetime.now)
    guard_decision_at_link_time: WorkflowGuardDecision
    was_stale_at_link_time: bool


class WorkflowGuardInputComparisonResult(BaseModel):
    is_stale: bool
    stale_reasons: list[WorkflowGuardStaleReason] = Field(default_factory=list)


# ── Hash helpers ─────────────────────────────────────────────────────────────


def hash_guard_text(value: Optional[str]) -> Optional[str]:
    """Return a deterministic SHA-256 hash for storage-safe text comparison."""

    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_required_text(value: str) -> str:
    return hash_guard_text(value) or ""


def _normalize_optional_text(value: Optional[str]) -> str:
    return value if value is not None else "<none>"


def _normalize_list(values: list[str]) -> str:
    return "\x1e".join(values)


def _hash_parts(*parts: str) -> str:
    return _hash_required_text("\x1f".join(parts))


def _coerce_decision(value: WorkflowGuardDecision | str) -> WorkflowGuardDecision:
    return value if isinstance(value, WorkflowGuardDecision) else WorkflowGuardDecision(value)


def _coerce_risk(value: WorkflowGuardDriftRisk | str) -> WorkflowGuardDriftRisk:
    return value if isinstance(value, WorkflowGuardDriftRisk) else WorkflowGuardDriftRisk(value or "medium")


def _dedupe_reasons(reasons: list[WorkflowGuardStaleReason]) -> list[WorkflowGuardStaleReason]:
    deduped: list[WorkflowGuardStaleReason] = []
    for reason in reasons:
        if reason not in deduped:
            deduped.append(reason)
    return deduped


# ── Snapshot builders ────────────────────────────────────────────────────────


def build_guard_input_snapshot(
    *,
    proposed_action: str,
    file_path: Optional[str] = None,
    patch_summary: Optional[str] = None,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
) -> WorkflowGuardInputSnapshot:
    """Build a storage-safe guard input snapshot.

    Raw old/new text is intentionally omitted; only hashes are retained.
    """

    old_text_hash = hash_guard_text(old_text)
    new_text_hash = hash_guard_text(new_text)
    input_hash = _hash_parts(
        proposed_action,
        _normalize_optional_text(file_path),
        _normalize_optional_text(patch_summary),
        _normalize_optional_text(old_text_hash),
        _normalize_optional_text(new_text_hash),
    )
    return WorkflowGuardInputSnapshot(
        proposed_action=proposed_action,
        file_path=file_path,
        patch_summary=patch_summary,
        old_text_hash=old_text_hash,
        new_text_hash=new_text_hash,
        input_hash=input_hash,
    )


def build_requirement_context_snapshot(
    *,
    requirement_ids: Optional[list[str]] = None,
    coverage_status: str = "",
    drift_risk: WorkflowGuardDriftRisk | str = "",
    acceptance_criteria: Optional[list[str]] = None,
    constraints: Optional[list[str]] = None,
    forbidden_changes: Optional[list[str]] = None,
    validation_notes: Optional[list[str]] = None,
    source_of_truth_summary: str = "",
) -> WorkflowGuardRequirementContextSnapshot:
    """Build a deterministic snapshot of parsed requirement context."""

    ids = list(requirement_ids or [])
    criteria = list(acceptance_criteria or [])
    constraint_values = list(constraints or [])
    forbidden = list(forbidden_changes or [])
    notes = list(validation_notes or [])
    risk_value = drift_risk.value if isinstance(drift_risk, WorkflowGuardDriftRisk) else str(drift_risk or "")
    context_hash = _hash_parts(
        _normalize_list(ids),
        coverage_status,
        risk_value,
        _normalize_list(criteria),
        _normalize_list(constraint_values),
        _normalize_list(forbidden),
        _normalize_list(notes),
        source_of_truth_summary,
    )
    return WorkflowGuardRequirementContextSnapshot(
        requirement_ids=ids,
        coverage_status=coverage_status,
        drift_risk=drift_risk,
        acceptance_criteria=criteria,
        constraints=constraint_values,
        forbidden_changes=forbidden,
        validation_notes=notes,
        source_of_truth_summary=source_of_truth_summary,
        context_hash=context_hash,
    )


def build_guard_result_snapshot(
    *,
    decision: WorkflowGuardDecision | str,
    drift_risk: WorkflowGuardDriftRisk | str,
    matched_requirement_ids: Optional[list[str]] = None,
    violated_constraints: Optional[list[str]] = None,
    forbidden_change_hits: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    reasons: Optional[list[str]] = None,
    recommended_next_step: str = "",
) -> WorkflowGuardResultSnapshot:
    """Build a deterministic guard result snapshot."""

    decision_value = _coerce_decision(decision)
    risk_value = _coerce_risk(drift_risk)
    matched = list(matched_requirement_ids or [])
    violated = list(violated_constraints or [])
    forbidden = list(forbidden_change_hits or [])
    warning_values = list(warnings or [])
    reason_values = list(reasons or [])
    result_hash = _hash_parts(
        decision_value.value,
        risk_value.value,
        _normalize_list(matched),
        _normalize_list(violated),
        _normalize_list(forbidden),
        _normalize_list(warning_values),
        _normalize_list(reason_values),
        recommended_next_step,
    )
    return WorkflowGuardResultSnapshot(
        decision=decision_value,
        drift_risk=risk_value,
        matched_requirement_ids=matched,
        violated_constraints=violated,
        forbidden_change_hits=forbidden,
        warnings=warning_values,
        reasons=reason_values,
        recommended_next_step=recommended_next_step,
        result_hash=result_hash,
    )


def build_workflow_guard_result_record(
    *,
    id: str,
    run_id: str,
    step_id: str,
    input_snapshot: WorkflowGuardInputSnapshot,
    requirement_context_snapshot: WorkflowGuardRequirementContextSnapshot,
    result_snapshot: WorkflowGuardResultSnapshot,
    source: WorkflowGuardSource = WorkflowGuardSource.RUN_STEP_GUARD,
    project_id: Optional[str] = None,
    proposal_tool_call_id: Optional[str] = None,
    apply_tool_call_id: Optional[str] = None,
    warning_acknowledged: bool = False,
    no_guard_override: bool = False,
    created_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
) -> WorkflowGuardResultRecord:
    """Build a future storage record without persistence or side effects."""

    return WorkflowGuardResultRecord(
        id=id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
        proposal_tool_call_id=proposal_tool_call_id,
        apply_tool_call_id=apply_tool_call_id,
        source=source,
        input_snapshot=input_snapshot,
        requirement_context_snapshot=requirement_context_snapshot,
        result_snapshot=result_snapshot,
        warning_acknowledged=warning_acknowledged,
        no_guard_override=no_guard_override,
        created_at=created_at or datetime.now(),
        expires_at=expires_at,
    )


# ── Staleness and proposal usability helpers ─────────────────────────────────


def mark_guard_result_stale(
    record: WorkflowGuardResultRecord,
    reason: WorkflowGuardStaleReason,
) -> WorkflowGuardResultRecord:
    """Return a stale copy of a guard result record without mutating input."""

    reasons = _dedupe_reasons([*record.stale_reasons, reason])
    return record.model_copy(
        update={
            "is_stale": True,
            "stale_reasons": reasons,
            "updated_at": datetime.now(),
        }
    )


def _record_is_expired(record: WorkflowGuardResultRecord, now: Optional[datetime] = None) -> bool:
    return bool(record.expires_at and (now or datetime.now()) > record.expires_at)


def compare_guard_input_to_patch_payload(
    record: WorkflowGuardResultRecord,
    proposed_action: str,
    file_path: Optional[str] = None,
    patch_summary: Optional[str] = None,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
) -> WorkflowGuardInputComparisonResult:
    """Compare stored guard input to a future patch proposal payload."""

    reasons: list[WorkflowGuardStaleReason] = []
    stored = record.input_snapshot
    current = build_guard_input_snapshot(
        proposed_action=proposed_action,
        file_path=file_path,
        patch_summary=patch_summary,
        old_text=old_text,
        new_text=new_text,
    )
    if stored.proposed_action != current.proposed_action:
        reasons.append(WorkflowGuardStaleReason.PROPOSED_ACTION_CHANGED)
    if stored.file_path != current.file_path:
        reasons.append(WorkflowGuardStaleReason.FILE_PATH_CHANGED)
    if stored.patch_summary != current.patch_summary:
        reasons.append(WorkflowGuardStaleReason.PATCH_SUMMARY_CHANGED)
    if stored.old_text_hash != current.old_text_hash:
        reasons.append(WorkflowGuardStaleReason.OLD_TEXT_CHANGED)
    if stored.new_text_hash != current.new_text_hash:
        reasons.append(WorkflowGuardStaleReason.NEW_TEXT_CHANGED)
    if stored.input_hash != current.input_hash:
        reasons.append(WorkflowGuardStaleReason.PROPOSAL_PAYLOAD_MISMATCH)
    if record.is_stale:
        reasons.extend(record.stale_reasons or [WorkflowGuardStaleReason.MANUAL_INVALIDATION])
    if _record_is_expired(record):
        reasons.append(WorkflowGuardStaleReason.EXPIRED)
    reasons = _dedupe_reasons(reasons)
    return WorkflowGuardInputComparisonResult(
        is_stale=bool(reasons),
        stale_reasons=reasons,
    )


def compare_guard_requirement_context(
    record: WorkflowGuardResultRecord,
    requirement_context_snapshot: WorkflowGuardRequirementContextSnapshot,
) -> WorkflowGuardInputComparisonResult:
    """Compare stored requirement context to a current context snapshot."""

    reasons: list[WorkflowGuardStaleReason] = []
    if record.requirement_context_snapshot.context_hash != requirement_context_snapshot.context_hash:
        reasons.append(WorkflowGuardStaleReason.REQUIREMENT_CONTEXT_CHANGED)
    if record.is_stale:
        reasons.extend(record.stale_reasons or [WorkflowGuardStaleReason.MANUAL_INVALIDATION])
    if _record_is_expired(record):
        reasons.append(WorkflowGuardStaleReason.EXPIRED)
    reasons = _dedupe_reasons(reasons)
    return WorkflowGuardInputComparisonResult(
        is_stale=bool(reasons),
        stale_reasons=reasons,
    )


def is_guard_result_usable_for_proposal(record: WorkflowGuardResultRecord) -> bool:
    """Return whether a stored guard result can authorize proposal creation."""

    if record.is_stale or _record_is_expired(record):
        return False
    if record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        return False
    if record.result_snapshot.decision == WorkflowGuardDecision.WARNING:
        return record.warning_acknowledged
    return record.result_snapshot.decision == WorkflowGuardDecision.ALLOWED

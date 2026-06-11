"""Pure API-facing contracts for future Source-of-Truth Guard results.

These models describe request/response shapes only.  They do not register
routes, read/write storage, execute tools, create tool calls, apply patches, or
perform provider calls.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardProposalLink,
    WorkflowGuardResultRecord,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    compare_guard_input_to_patch_payload,
    is_guard_result_usable_for_proposal,
)


# ── Shared API result models ─────────────────────────────────────────────────


class GuardResultApiError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[dict[str, Any]] = None


class WorkflowGuardResultApiResponse(BaseModel):
    guard_result: WorkflowGuardResultRecord
    usable_for_proposal: bool
    stale_reasons: list[WorkflowGuardStaleReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class WorkflowGuardResultListResponse(BaseModel):
    items: list[WorkflowGuardResultApiResponse] = Field(default_factory=list)
    total: int = 0
    limit: int = 50
    offset: int = 0


class GuardResultProposalValidationResponse(BaseModel):
    guard_result_id: str
    usable: bool
    stale: bool
    decision: WorkflowGuardDecision
    stale_reasons: list[WorkflowGuardStaleReason] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requires_warning_acknowledgement: bool = False
    recommended_next_step: str = ""


class LinkGuardResultToProposalResponse(BaseModel):
    guard_result_id: str
    proposal_tool_call_id: str
    linked: bool
    was_stale_at_link_time: bool
    usable_at_link_time: bool
    warnings: list[str] = Field(default_factory=list)


# ── Request models ───────────────────────────────────────────────────────────


class CreateWorkflowGuardResultRequest(BaseModel):
    run_id: str
    step_id: str
    project_id: Optional[str] = None
    proposed_action: str
    file_path: Optional[str] = None
    patch_summary: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    persist: bool = True
    source: WorkflowGuardSource | str = WorkflowGuardSource.RUN_STEP_GUARD


class ListWorkflowGuardResultsRequest(BaseModel):
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    proposal_tool_call_id: Optional[str] = None
    decision: Optional[WorkflowGuardDecision] = None
    include_stale: bool = False
    limit: int = 50
    offset: int = 0


class LinkGuardResultToProposalRequest(BaseModel):
    guard_result_id: str
    proposal_tool_call_id: str
    warning_acknowledged: bool = False
    no_guard_override: bool = False


class ValidateGuardResultForProposalRequest(BaseModel):
    guard_result_id: str
    proposed_action: str
    file_path: Optional[str] = None
    patch_summary: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None


class MarkGuardResultStaleRequest(BaseModel):
    guard_result_id: str
    reason: WorkflowGuardStaleReason
    note: Optional[str] = None


class GuardResultApiValidationResult(BaseModel):
    valid: bool
    errors: list[GuardResultApiError] = Field(default_factory=list)
    warnings: list[GuardResultApiError] = Field(default_factory=list)


# ── Pure validation helpers ──────────────────────────────────────────────────


def build_guard_result_api_error(
    code: str,
    message: str,
    *,
    field: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> GuardResultApiError:
    """Build a structured API error without side effects."""

    return GuardResultApiError(
        code=code,
        message=message,
        field=field,
        details=details,
    )


def _is_blank(value: Optional[str]) -> bool:
    return value is None or not value.strip()


def validate_create_guard_result_request(
    request: CreateWorkflowGuardResultRequest,
) -> GuardResultApiValidationResult:
    """Validate future create request shape without persisting anything."""

    errors: list[GuardResultApiError] = []
    if _is_blank(request.run_id):
        errors.append(build_guard_result_api_error("run_id_required", "run_id is required.", field="run_id"))
    if _is_blank(request.step_id):
        errors.append(build_guard_result_api_error("step_id_required", "step_id is required.", field="step_id"))
    if _is_blank(request.proposed_action):
        errors.append(build_guard_result_api_error(
            "proposed_action_required",
            "proposed_action must be a non-empty string.",
            field="proposed_action",
        ))
    return GuardResultApiValidationResult(valid=not errors, errors=errors)


def validate_list_guard_results_request(
    request: ListWorkflowGuardResultsRequest,
) -> GuardResultApiValidationResult:
    """Validate list query bounds without reading storage."""

    errors: list[GuardResultApiError] = []
    if request.limit < 1 or request.limit > 200:
        errors.append(build_guard_result_api_error(
            "limit_out_of_bounds",
            "limit must be between 1 and 200.",
            field="limit",
        ))
    if request.offset < 0:
        errors.append(build_guard_result_api_error(
            "offset_out_of_bounds",
            "offset must be greater than or equal to 0.",
            field="offset",
        ))
    return GuardResultApiValidationResult(valid=not errors, errors=errors)


def validate_guard_result_link_request(
    request: LinkGuardResultToProposalRequest,
    record: Optional[WorkflowGuardResultRecord] = None,
) -> GuardResultApiValidationResult:
    """Validate future guard-result-to-proposal link request."""

    errors: list[GuardResultApiError] = []
    warnings: list[GuardResultApiError] = []
    if _is_blank(request.guard_result_id):
        errors.append(build_guard_result_api_error(
            "guard_result_id_required",
            "guard_result_id is required.",
            field="guard_result_id",
        ))
    if _is_blank(request.proposal_tool_call_id):
        errors.append(build_guard_result_api_error(
            "proposal_tool_call_id_required",
            "proposal_tool_call_id is required.",
            field="proposal_tool_call_id",
        ))
    if record is not None:
        if record.id != request.guard_result_id:
            errors.append(build_guard_result_api_error(
                "guard_result_id_mismatch",
                "Link request guard_result_id does not match the guard record.",
                field="guard_result_id",
            ))
        response = build_guard_result_validation_response(record)
        if not response.usable:
            errors.append(build_guard_result_api_error(
                "guard_result_not_usable",
                "Guard result is not usable for proposal link.",
                field="guard_result_id",
                details={"blocking_reasons": response.blocking_reasons},
            ))
        if request.no_guard_override and record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
            errors.append(build_guard_result_api_error(
                "blocked_guard_override_forbidden",
                "no_guard_override does not make a blocked guard usable.",
                field="no_guard_override",
            ))
        if record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not request.warning_acknowledged:
            warnings.append(build_guard_result_api_error(
                "warning_acknowledgement_missing",
                "Warning guard should be acknowledged before linking to proposal.",
                field="warning_acknowledged",
            ))
    return GuardResultApiValidationResult(valid=not errors, errors=errors, warnings=warnings)


def validate_guard_result_for_proposal(
    request: ValidateGuardResultForProposalRequest,
    record: Optional[WorkflowGuardResultRecord] = None,
) -> GuardResultProposalValidationResponse:
    """Validate future proposal payload against a stored guard result."""

    if record is None:
        return GuardResultProposalValidationResponse(
            guard_result_id=request.guard_result_id,
            usable=False,
            stale=True,
            decision=WorkflowGuardDecision.BLOCKED,
            blocking_reasons=["Guard result record is required for proposal validation."],
            recommended_next_step="Load the guard result record and validate again.",
        )
    if record.id != request.guard_result_id:
        return GuardResultProposalValidationResponse(
            guard_result_id=request.guard_result_id,
            usable=False,
            stale=True,
            decision=record.result_snapshot.decision,
            blocking_reasons=["Guard result id does not match validation request."],
            recommended_next_step="Use the guard result id that matches the stored record.",
        )

    comparison = compare_guard_input_to_patch_payload(
        record,
        proposed_action=request.proposed_action,
        file_path=request.file_path,
        patch_summary=request.patch_summary,
        old_text=request.old_text,
        new_text=request.new_text,
    )
    base_usable = is_guard_result_usable_for_proposal(record)
    blocking: list[str] = []
    warnings: list[str] = []
    if comparison.is_stale:
        blocking.append("Guard result is stale for the proposed patch payload.")
    if record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        blocking.append("Blocked guard result cannot be used for proposal creation.")
    if record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not record.warning_acknowledged:
        blocking.append("Warning guard requires explicit acknowledgement before proposal creation.")
    if record.no_guard_override and record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        blocking.append("no_guard_override does not override a blocked guard result.")
    if record.no_guard_override:
        warnings.append("No-guard override is recorded and must remain explicit in future audit.")

    usable = base_usable and not comparison.is_stale and not blocking
    if usable:
        recommended = "Guard result is usable for proposal creation. Future runtime must still revalidate policy."
    else:
        recommended = "Run a fresh Source-of-Truth Guard check or resolve blocking guard conditions."
    return GuardResultProposalValidationResponse(
        guard_result_id=record.id,
        usable=usable,
        stale=comparison.is_stale,
        decision=record.result_snapshot.decision,
        stale_reasons=comparison.stale_reasons,
        blocking_reasons=blocking,
        warnings=warnings,
        requires_warning_acknowledgement=record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not record.warning_acknowledged,
        recommended_next_step=recommended,
    )


def build_guard_result_api_response(
    record: WorkflowGuardResultRecord,
) -> WorkflowGuardResultApiResponse:
    """Build a single-record API response without reading storage."""

    warnings: list[str] = []
    if record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not record.warning_acknowledged:
        warnings.append("Warning guard requires explicit acknowledgement before proposal creation.")
    if record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        warnings.append("Blocked guard result cannot be used for proposal creation.")
    if record.is_stale:
        warnings.append("Guard result is stale.")
    return WorkflowGuardResultApiResponse(
        guard_result=record,
        usable_for_proposal=is_guard_result_usable_for_proposal(record),
        stale_reasons=list(record.stale_reasons),
        warnings=warnings,
    )


def build_guard_result_validation_response(
    record: WorkflowGuardResultRecord,
) -> GuardResultProposalValidationResponse:
    """Build validation response from record state only."""

    blocking: list[str] = []
    warnings: list[str] = []
    stale = record.is_stale
    if record.is_stale:
        blocking.append("Guard result is stale.")
    if record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        blocking.append("Blocked guard result cannot be used for proposal creation.")
    if record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not record.warning_acknowledged:
        blocking.append("Warning guard requires explicit acknowledgement before proposal creation.")
    if record.no_guard_override and record.result_snapshot.decision == WorkflowGuardDecision.BLOCKED:
        blocking.append("no_guard_override does not override a blocked guard result.")
    if record.no_guard_override:
        warnings.append("No-guard override is recorded and must remain explicit in future audit.")
    usable = is_guard_result_usable_for_proposal(record) and not blocking
    return GuardResultProposalValidationResponse(
        guard_result_id=record.id,
        usable=usable,
        stale=stale,
        decision=record.result_snapshot.decision,
        stale_reasons=list(record.stale_reasons),
        blocking_reasons=blocking,
        warnings=warnings,
        requires_warning_acknowledgement=record.result_snapshot.decision == WorkflowGuardDecision.WARNING and not record.warning_acknowledged,
        recommended_next_step=(
            "Guard result is usable for proposal creation. Future runtime must still revalidate policy."
            if usable
            else "Run a fresh Source-of-Truth Guard check or resolve blocking guard conditions."
        ),
    )


def build_link_guard_result_to_proposal_response(
    request: LinkGuardResultToProposalRequest,
    record: WorkflowGuardResultRecord,
) -> LinkGuardResultToProposalResponse:
    """Build future link response without mutating record or storage."""

    validation = build_guard_result_validation_response(record)
    link = WorkflowGuardProposalLink(
        guard_result_id=request.guard_result_id,
        proposal_tool_call_id=request.proposal_tool_call_id,
        guard_decision_at_link_time=record.result_snapshot.decision,
        was_stale_at_link_time=validation.stale,
    )
    warnings = list(validation.warnings)
    if validation.blocking_reasons:
        warnings.extend(validation.blocking_reasons)
    return LinkGuardResultToProposalResponse(
        guard_result_id=link.guard_result_id,
        proposal_tool_call_id=link.proposal_tool_call_id,
        linked=validation.usable and request.guard_result_id == record.id,
        was_stale_at_link_time=link.was_stale_at_link_time,
        usable_at_link_time=validation.usable,
        warnings=warnings,
    )

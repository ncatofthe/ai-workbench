"""Pure API contracts for future workflow approval endpoints.

These models describe request/response shapes only.  They do not register
routes, read/write storage, execute workflow actions, create tool calls, or call
providers.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.approvals.workflow_approval_contract import (
    WorkflowApprovalAction,
    WorkflowApprovalRequirement,
    WorkflowApprovalRisk,
    classify_workflow_approval_action,
)
from src.approvals.workflow_approval_storage_contract import (
    WorkflowApprovalDecisionRecord,
    WorkflowApprovalStorageRecord,
    WorkflowApprovalStorageStatus,
    WorkflowApprovalStoredPayloadSummary,
    is_approval_executable_from_storage,
    validate_approval_storage_record,
)


# ── Shared API result models ─────────────────────────────────────────────────


class WorkflowApprovalApiError(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    severity: str = "error"


class WorkflowApprovalApiValidationResponse(BaseModel):
    valid: bool
    errors: list[WorkflowApprovalApiError] = Field(default_factory=list)
    warnings: list[WorkflowApprovalApiError] = Field(default_factory=list)
    policy_gated: bool = True
    executes_action: bool = False


# ── Create/list/get contracts ────────────────────────────────────────────────


class CreateWorkflowApprovalRequest(BaseModel):
    """Request body for future POST /api/approvals/workflow.

    Creating an approval request never executes the action.
    """

    action: WorkflowApprovalAction
    title: str
    reason: str
    payload_summary: WorkflowApprovalStoredPayloadSummary = Field(default_factory=WorkflowApprovalStoredPayloadSummary)
    required_confirmations: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    intake_session_id: Optional[str] = None
    expires_at: Optional[str] = None
    policy_version: Optional[str] = None


class CreateWorkflowApprovalResponse(BaseModel):
    approval: WorkflowApprovalStorageRecord
    created: bool = True
    policy_gated: bool = True
    executes_action: bool = False
    message: str = "Approval request created. No workflow action was executed."


class ListWorkflowApprovalsRequest(BaseModel):
    status: Optional[WorkflowApprovalStorageStatus] = None
    action: Optional[WorkflowApprovalAction] = None
    risk_level: Optional[WorkflowApprovalRisk] = None
    project_id: Optional[str] = None
    run_id: Optional[str] = None
    step_id: Optional[str] = None
    intake_session_id: Optional[str] = None
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class ListWorkflowApprovalsResponse(BaseModel):
    approvals: list[WorkflowApprovalStorageRecord] = Field(default_factory=list)
    total: int = 0
    policy_gated: bool = True
    executes_action: bool = False


class GetWorkflowApprovalResponse(BaseModel):
    approval: Optional[WorkflowApprovalStorageRecord] = None
    found: bool = False
    policy_gated: bool = True
    executes_action: bool = False


# ── Decision contracts ───────────────────────────────────────────────────────


class ApproveWorkflowApprovalRequest(BaseModel):
    approved_by: Optional[str] = None
    decision_reason: Optional[str] = None
    decision_confirmations: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    policy_version: Optional[str] = None


class ApproveWorkflowApprovalResponse(BaseModel):
    approval: WorkflowApprovalStorageRecord
    decision: WorkflowApprovalDecisionRecord
    approved: bool = True
    policy_gated: bool = True
    executes_action: bool = False
    executable_candidate: bool = False
    message: str = "Approval recorded. Execute endpoint must be called separately."


class RejectWorkflowApprovalRequest(BaseModel):
    rejected_by: Optional[str] = None
    decision_reason: Optional[str] = None
    policy_version: Optional[str] = None


class RejectWorkflowApprovalResponse(BaseModel):
    approval: WorkflowApprovalStorageRecord
    decision: WorkflowApprovalDecisionRecord
    rejected: bool = True
    policy_gated: bool = True
    executes_action: bool = False
    message: str = "Rejection recorded. No workflow action was executed."


# ── Execute boundary contracts ───────────────────────────────────────────────


class ExecuteWorkflowApprovalRequest(BaseModel):
    """Request body for future POST /api/approvals/workflow/{id}/execute.

    This contract is still declarative.  It does not execute anything by itself.
    """

    approval_id: str
    requested_by: Optional[str] = None
    execute_confirmations: list[WorkflowApprovalRequirement] = Field(default_factory=list)
    dry_run: bool = False
    expected_policy_version: Optional[str] = None


class ExecuteWorkflowApprovalResponse(BaseModel):
    approval_id: str
    accepted_for_execution: bool = False
    policy_gated: bool = True
    executed: bool = False
    dry_run: bool = False
    tool_call_id: Optional[str] = None
    message: str = "Execution remains policy-gated and must be performed by a separate handler."
    validation: WorkflowApprovalApiValidationResponse = Field(default_factory=lambda: WorkflowApprovalApiValidationResponse(valid=False))


# ── Pure builders/validators ────────────────────────────────────────────────


def build_approval_api_error(
    code: str,
    message: str,
    *,
    field: Optional[str] = None,
    severity: str = "error",
) -> WorkflowApprovalApiError:
    """Build a structured API error without side effects."""

    return WorkflowApprovalApiError(
        code=code,
        message=message,
        field=field,
        severity=severity,
    )


def build_create_approval_response(
    approval: WorkflowApprovalStorageRecord,
) -> CreateWorkflowApprovalResponse:
    """Build a create response that explicitly does not execute the action."""

    return CreateWorkflowApprovalResponse(
        approval=approval,
        created=True,
        executes_action=False,
    )


def validate_execute_approval_request_contract(
    request: ExecuteWorkflowApprovalRequest,
    approval: Optional[WorkflowApprovalStorageRecord] = None,
) -> WorkflowApprovalApiValidationResponse:
    """Validate future execute request shape against an optional approval.

    This does not execute anything and does not mutate the approval.
    """

    errors: list[WorkflowApprovalApiError] = []
    warnings: list[WorkflowApprovalApiError] = []

    if approval is None:
        errors.append(build_approval_api_error(
            "approval_required",
            "Execution validation requires an approval record.",
            field="approval",
        ))
        return WorkflowApprovalApiValidationResponse(
            valid=False,
            errors=errors,
            warnings=warnings,
            executes_action=False,
        )

    if approval.id != request.approval_id:
        errors.append(build_approval_api_error(
            "approval_id_mismatch",
            "Execute request approval_id does not match the approval record.",
            field="approval_id",
        ))

    storage_result = validate_approval_storage_record(approval)
    for error in storage_result.errors:
        errors.append(build_approval_api_error("storage_validation_failed", error))
    for warning in storage_result.warnings:
        warnings.append(build_approval_api_error("storage_validation_warning", warning, severity="warning"))

    if approval.status in (
        WorkflowApprovalStorageStatus.REJECTED,
        WorkflowApprovalStorageStatus.EXPIRED,
        WorkflowApprovalStorageStatus.CANCELLED,
    ):
        errors.append(build_approval_api_error(
            "terminal_approval",
            "Rejected, expired, or cancelled approvals cannot be executed.",
            field="status",
        ))

    if approval.action == WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION:
        errors.append(build_approval_api_error(
            "external_provider_disabled",
            "External provider execution remains disabled in this contract.",
            field="action",
        ))

    _, required_confirmations, _, _ = classify_workflow_approval_action(approval.action)
    missing_execute_confirmations = [
        requirement
        for requirement in required_confirmations
        if requirement not in request.execute_confirmations
    ]
    if missing_execute_confirmations:
        errors.append(build_approval_api_error(
            "missing_execute_confirmations",
            "Execute request is missing required confirmations: "
            + ", ".join(requirement.value for requirement in missing_execute_confirmations),
            field="execute_confirmations",
        ))

    if approval.policy_version and request.expected_policy_version and approval.policy_version != request.expected_policy_version:
        errors.append(build_approval_api_error(
            "policy_version_mismatch",
            "Approval policy version does not match execute request expectation.",
            field="expected_policy_version",
        ))

    if not is_approval_executable_from_storage(approval):
        warnings.append(build_approval_api_error(
            "not_executable_candidate",
            "Approval is not currently an executable candidate; future handler must revalidate policy.",
            severity="warning",
        ))

    return WorkflowApprovalApiValidationResponse(
        valid=not errors,
        errors=errors,
        warnings=warnings,
        policy_gated=True,
        executes_action=False,
    )

"""Tests for pure workflow approval API contracts."""

from __future__ import annotations

import inspect
import unittest
from datetime import datetime

import src.approvals.workflow_approval_api_contract as api_contract_module
from src.approvals.workflow_approval_api_contract import (
    ApproveWorkflowApprovalRequest,
    ApproveWorkflowApprovalResponse,
    CreateWorkflowApprovalRequest,
    CreateWorkflowApprovalResponse,
    ExecuteWorkflowApprovalRequest,
    ExecuteWorkflowApprovalResponse,
    GetWorkflowApprovalResponse,
    ListWorkflowApprovalsRequest,
    ListWorkflowApprovalsResponse,
    RejectWorkflowApprovalRequest,
    RejectWorkflowApprovalResponse,
    build_approval_api_error,
    build_create_approval_response,
    validate_execute_approval_request_contract,
)
from src.approvals.workflow_approval_contract import (
    WorkflowApprovalAction,
    WorkflowApprovalRequirement,
    WorkflowApprovalRisk,
)
from src.approvals.workflow_approval_storage_contract import (
    WorkflowApprovalDecisionRecord,
    WorkflowApprovalStorageRecord,
    WorkflowApprovalStorageStatus,
    WorkflowApprovalStoredPayloadSummary,
)


def _approved_apply_record() -> WorkflowApprovalStorageRecord:
    return WorkflowApprovalStorageRecord(
        id="approval-api-1",
        action=WorkflowApprovalAction.APPLY_PATCH,
        status=WorkflowApprovalStorageStatus.APPROVED,
        risk_level=WorkflowApprovalRisk.HIGH,
        title="Apply patch",
        reason="Apply reviewed patch after explicit approval",
        payload_summary_json=WorkflowApprovalStoredPayloadSummary(
            description="Apply a reviewed patch",
            affected_files=["frontend/src/pages/NewTask.tsx"],
        ),
        required_confirmations=[
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
            WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
        ],
        policy_version="approval-api-contract-v1",
        decided_at=datetime.now().isoformat(),
        approved_by="operator",
    )


class TestWorkflowApprovalApiModels(unittest.TestCase):
    """Serialization and response-shape tests."""

    def test_create_request_response_serializes(self):
        request = CreateWorkflowApprovalRequest(
            action=WorkflowApprovalAction.RUN_TESTS,
            title="Run tests",
            reason="Validate the current patch manually",
            payload_summary=WorkflowApprovalStoredPayloadSummary(command_summary="pytest -q"),
            required_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.COMMAND_ALLOWLIST_CHECK,
            ],
            run_id="run-1",
            step_id="step-1",
            policy_version="approval-api-contract-v1",
        )

        request_data = request.model_dump()
        restored_request = CreateWorkflowApprovalRequest.model_validate(request_data)
        self.assertEqual(restored_request.action, WorkflowApprovalAction.RUN_TESTS)

        approval = WorkflowApprovalStorageRecord(
            id="approval-create-1",
            action=request.action,
            status=WorkflowApprovalStorageStatus.PENDING,
            risk_level=WorkflowApprovalRisk.MEDIUM,
            title=request.title,
            reason=request.reason,
            payload_summary_json=request.payload_summary,
            required_confirmations=request.required_confirmations,
            run_id=request.run_id,
            step_id=request.step_id,
            policy_version=request.policy_version,
        )
        response = build_create_approval_response(approval)
        restored_response = CreateWorkflowApprovalResponse.model_validate(response.model_dump())

        self.assertTrue(restored_response.created)
        self.assertFalse(restored_response.executes_action)
        self.assertEqual(restored_response.approval.id, "approval-create-1")

    def test_list_and_get_responses_do_not_execute(self):
        approval = _approved_apply_record()
        list_request = ListWorkflowApprovalsRequest(
            status=WorkflowApprovalStorageStatus.APPROVED,
            action=WorkflowApprovalAction.APPLY_PATCH,
            limit=25,
        )
        list_response = ListWorkflowApprovalsResponse(
            approvals=[approval],
            total=1,
        )
        get_response = GetWorkflowApprovalResponse(
            approval=approval,
            found=True,
        )

        self.assertEqual(list_request.limit, 25)
        self.assertFalse(list_response.executes_action)
        self.assertFalse(get_response.executes_action)
        self.assertEqual(get_response.approval.risk_level, WorkflowApprovalRisk.HIGH)

    def test_approve_reject_responses_do_not_execute(self):
        approval = _approved_apply_record()
        approve_request = ApproveWorkflowApprovalRequest(
            approved_by="operator",
            decision_reason="Looks safe",
            decision_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
            ],
        )
        approve_response = ApproveWorkflowApprovalResponse(
            approval=approval,
            decision=WorkflowApprovalDecisionRecord(
                id="decision-approve",
                approval_request_id=approval.id,
                status=WorkflowApprovalStorageStatus.APPROVED,
                decided_by=approve_request.approved_by,
                decision_reason=approve_request.decision_reason,
            ),
            executable_candidate=True,
        )
        reject_request = RejectWorkflowApprovalRequest(
            rejected_by="operator",
            decision_reason="Too risky",
        )
        reject_response = RejectWorkflowApprovalResponse(
            approval=approval.model_copy(update={"status": WorkflowApprovalStorageStatus.REJECTED}),
            decision=WorkflowApprovalDecisionRecord(
                id="decision-reject",
                approval_request_id=approval.id,
                status=WorkflowApprovalStorageStatus.REJECTED,
                decided_by=reject_request.rejected_by,
                decision_reason=reject_request.decision_reason,
            ),
        )

        self.assertFalse(approve_response.executes_action)
        self.assertFalse(reject_response.executes_action)
        self.assertTrue(approve_response.executable_candidate)
        self.assertTrue(reject_response.rejected)

    def test_execute_response_tool_call_id_is_optional_future_result(self):
        response = ExecuteWorkflowApprovalResponse(
            approval_id="approval-api-1",
            accepted_for_execution=True,
            executed=False,
            dry_run=True,
            tool_call_id=None,
            validation=validate_execute_approval_request_contract(
                ExecuteWorkflowApprovalRequest(
                    approval_id="approval-api-1",
                    dry_run=True,
                    execute_confirmations=[
                        WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                        WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
                        WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
                    ],
                ),
                _approved_apply_record(),
            ),
        )

        data = response.model_dump()
        restored = ExecuteWorkflowApprovalResponse.model_validate(data)
        self.assertFalse(restored.executed)
        self.assertIsNone(restored.tool_call_id)
        self.assertTrue(restored.validation.valid)


class TestWorkflowApprovalApiSafety(unittest.TestCase):
    """API contract safety and execution-boundary tests."""

    def test_create_response_does_not_imply_execution(self):
        approval = _approved_apply_record().model_copy(update={"status": WorkflowApprovalStorageStatus.PENDING})
        response = build_create_approval_response(approval)

        self.assertTrue(response.created)
        self.assertFalse(response.executes_action)
        self.assertIn("No workflow action", response.message)

    def test_execute_request_requires_explicit_execution_confirmations(self):
        approval = _approved_apply_record()
        missing_request = ExecuteWorkflowApprovalRequest(
            approval_id=approval.id,
            execute_confirmations=[WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
        )
        missing_result = validate_execute_approval_request_contract(missing_request, approval)
        self.assertFalse(missing_result.valid)
        self.assertIn("missing_execute_confirmations", [error.code for error in missing_result.errors])

        complete_request = ExecuteWorkflowApprovalRequest(
            approval_id=approval.id,
            execute_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
                WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
            ],
            expected_policy_version="approval-api-contract-v1",
        )
        complete_result = validate_execute_approval_request_contract(complete_request, approval)
        self.assertTrue(complete_result.valid)
        self.assertFalse(complete_result.executes_action)

    def test_external_provider_action_remains_critical_and_blocked(self):
        approval = WorkflowApprovalStorageRecord(
            id="approval-provider",
            action=WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION,
            status=WorkflowApprovalStorageStatus.APPROVED,
            risk_level=WorkflowApprovalRisk.CRITICAL,
            title="External provider execution",
            reason="Provider call must stay disabled",
            payload_summary_json=WorkflowApprovalStoredPayloadSummary(provider_summary="Claude request"),
            required_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.PROVIDER_PERMISSION_CHECK,
            ],
            decided_at=datetime.now().isoformat(),
            approved_by="operator",
        )
        request = ExecuteWorkflowApprovalRequest(
            approval_id=approval.id,
            execute_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.PROVIDER_PERMISSION_CHECK,
            ],
        )

        result = validate_execute_approval_request_contract(request, approval)

        self.assertFalse(result.valid)
        self.assertIn("external_provider_disabled", [error.code for error in result.errors])
        self.assertEqual(approval.risk_level, WorkflowApprovalRisk.CRITICAL)

    def test_rejected_expired_cancelled_approvals_cannot_execute(self):
        for status in (
            WorkflowApprovalStorageStatus.REJECTED,
            WorkflowApprovalStorageStatus.EXPIRED,
            WorkflowApprovalStorageStatus.CANCELLED,
        ):
            with self.subTest(status=status.value):
                approval = _approved_apply_record().model_copy(update={"status": status})
                request = ExecuteWorkflowApprovalRequest(
                    approval_id=approval.id,
                    execute_confirmations=[
                        WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                        WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
                        WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
                    ],
                )
                result = validate_execute_approval_request_contract(request, approval)
                self.assertFalse(result.valid)
                self.assertIn("terminal_approval", [error.code for error in result.errors])

    def test_secret_like_payload_values_are_rejected(self):
        with self.assertRaises(ValueError):
            CreateWorkflowApprovalRequest(
                action=WorkflowApprovalAction.CREATE_PROPOSAL,
                title="Create proposal",
                reason="Unsafe payload",
                payload_summary=WorkflowApprovalStoredPayloadSummary(description="TOKEN=abc123"),
            )

    def test_policy_version_mismatch_fails_safely(self):
        approval = _approved_apply_record()
        request = ExecuteWorkflowApprovalRequest(
            approval_id=approval.id,
            execute_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
                WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
            ],
            expected_policy_version="other-policy",
        )

        result = validate_execute_approval_request_contract(request, approval)

        self.assertFalse(result.valid)
        self.assertIn("policy_version_mismatch", [error.code for error in result.errors])

    def test_api_error_serializes(self):
        error = build_approval_api_error(
            "bad_request",
            "Request is invalid.",
            field="approval_id",
        )
        restored = type(error).model_validate(error.model_dump())
        self.assertEqual(restored.code, "bad_request")
        self.assertEqual(restored.field, "approval_id")

    def test_api_contract_module_has_no_db_route_tool_provider_usage(self):
        source = inspect.getsource(api_contract_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.api", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("from requests", source)
        self.assertNotIn("open(", source)


if __name__ == "__main__":
    unittest.main()

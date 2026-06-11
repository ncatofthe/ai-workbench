"""Tests for the pure workflow approval request contract."""

from __future__ import annotations

import inspect
import unittest

import src.approvals.workflow_approval_contract as approval_contract_module
from src.approvals.workflow_approval_contract import (
    WorkflowApprovalAction,
    WorkflowApprovalPayloadSummary,
    WorkflowApprovalRequestContract,
    WorkflowApprovalRequirement,
    WorkflowApprovalRisk,
    WorkflowApprovalStatus,
    build_workflow_approval_request,
    classify_workflow_approval_action,
    validate_workflow_approval_request,
)


class TestWorkflowApprovalContractModels(unittest.TestCase):
    """Model serialization and shape tests."""

    def test_request_contract_serializes_and_deserializes(self):
        request = build_workflow_approval_request(
            id="approval-1",
            action=WorkflowApprovalAction.APPLY_PATCH,
            run_id="run-1",
            step_id="step-1",
            project_id="project-1",
            payload_summary=WorkflowApprovalPayloadSummary(
                description="Apply reviewed patch",
                affected_files=["frontend/src/pages/NewTask.tsx"],
                contains_protected_paths=False,
            ),
        )

        data = request.model_dump()
        restored = WorkflowApprovalRequestContract.model_validate(data)

        self.assertEqual(restored.id, "approval-1")
        self.assertEqual(restored.action, WorkflowApprovalAction.APPLY_PATCH)
        self.assertEqual(restored.status, WorkflowApprovalStatus.DRAFT)
        self.assertEqual(restored.risk_level, WorkflowApprovalRisk.HIGH)
        self.assertFalse(restored.executable_in_v1)

    def test_enum_values_are_stable(self):
        self.assertEqual(WorkflowApprovalAction.CREATE_PROPOSAL.value, "create_proposal")
        self.assertEqual(WorkflowApprovalStatus.PENDING.value, "pending")
        self.assertEqual(WorkflowApprovalRisk.CRITICAL.value, "critical")
        self.assertEqual(WorkflowApprovalRequirement.EXPLICIT_CHECKBOX.value, "explicit_checkbox")


class TestWorkflowApprovalRiskClassification(unittest.TestCase):
    """Risk/requirement classification tests."""

    def test_every_action_gets_expected_risk(self):
        expected = {
            WorkflowApprovalAction.CREATE_PROPOSAL: WorkflowApprovalRisk.MEDIUM,
            WorkflowApprovalAction.APPLY_PATCH: WorkflowApprovalRisk.HIGH,
            WorkflowApprovalAction.RUN_TESTS: WorkflowApprovalRisk.MEDIUM,
            WorkflowApprovalAction.ANALYZE_RESULT: WorkflowApprovalRisk.LOW,
            WorkflowApprovalAction.ROLLBACK_PATCH: WorkflowApprovalRisk.HIGH,
            WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION: WorkflowApprovalRisk.CRITICAL,
        }

        for action, risk in expected.items():
            with self.subTest(action=action.value):
                actual_risk, requirements, reason, executable = classify_workflow_approval_action(action)
                self.assertEqual(actual_risk, risk)
                self.assertGreater(len(requirements), 0)
                self.assertTrue(reason)
                self.assertFalse(executable)

    def test_apply_patch_requires_explicit_checkbox(self):
        request = build_workflow_approval_request(
            id="approval-apply",
            action=WorkflowApprovalAction.APPLY_PATCH,
        )

        self.assertIn(WorkflowApprovalRequirement.EXPLICIT_CHECKBOX, request.required_confirmations)
        self.assertIn(WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW, request.required_confirmations)
        self.assertEqual(request.risk_level, WorkflowApprovalRisk.HIGH)
        self.assertTrue(validate_workflow_approval_request(request).valid)

    def test_rollback_patch_requires_explicit_checkbox(self):
        request = build_workflow_approval_request(
            id="approval-rollback",
            action=WorkflowApprovalAction.ROLLBACK_PATCH,
        )

        self.assertIn(WorkflowApprovalRequirement.EXPLICIT_CHECKBOX, request.required_confirmations)
        self.assertEqual(request.risk_level, WorkflowApprovalRisk.HIGH)
        self.assertTrue(validate_workflow_approval_request(request).valid)

    def test_run_tests_requires_allowlist_check(self):
        request = build_workflow_approval_request(
            id="approval-tests",
            action=WorkflowApprovalAction.RUN_TESTS,
            payload_summary=WorkflowApprovalPayloadSummary(command="pytest -q"),
        )

        self.assertIn(WorkflowApprovalRequirement.COMMAND_ALLOWLIST_CHECK, request.required_confirmations)
        self.assertEqual(request.risk_level, WorkflowApprovalRisk.MEDIUM)
        self.assertFalse(request.executable_in_v1)
        self.assertTrue(validate_workflow_approval_request(request).valid)

    def test_external_provider_execution_is_critical_and_not_executable(self):
        request = build_workflow_approval_request(
            id="approval-provider",
            action=WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION,
            payload_summary=WorkflowApprovalPayloadSummary(provider="claude"),
        )

        result = validate_workflow_approval_request(request)

        self.assertEqual(request.risk_level, WorkflowApprovalRisk.CRITICAL)
        self.assertIn(WorkflowApprovalRequirement.PROVIDER_PERMISSION_CHECK, request.required_confirmations)
        self.assertFalse(result.executable_in_v1)
        self.assertTrue(result.valid)
        self.assertIn("not executable in v1", " ".join(result.warnings))


class TestWorkflowApprovalValidation(unittest.TestCase):
    """Validation guardrail tests."""

    def test_missing_required_confirmation_is_invalid(self):
        request = WorkflowApprovalRequestContract(
            id="approval-invalid",
            action=WorkflowApprovalAction.APPLY_PATCH,
            title="Apply patch",
            reason="Missing checkbox on purpose",
            risk_level=WorkflowApprovalRisk.HIGH,
            required_confirmations=[WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
        )

        result = validate_workflow_approval_request(request)

        self.assertFalse(result.valid)
        self.assertIn("explicit_checkbox", " ".join(result.errors))

    def test_risk_mismatch_is_invalid(self):
        request = WorkflowApprovalRequestContract(
            id="approval-risk",
            action=WorkflowApprovalAction.RUN_TESTS,
            title="Run tests",
            reason="Wrong risk on purpose",
            risk_level=WorkflowApprovalRisk.LOW,
            required_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.COMMAND_ALLOWLIST_CHECK,
            ],
        )

        result = validate_workflow_approval_request(request)

        self.assertFalse(result.valid)
        self.assertIn("risk_level", " ".join(result.errors))

    def test_protected_paths_are_flagged(self):
        request = build_workflow_approval_request(
            id="approval-protected",
            action=WorkflowApprovalAction.CREATE_PROPOSAL,
            payload_summary=WorkflowApprovalPayloadSummary(
                affected_files=["backend/.env"],
                contains_protected_paths=False,
            ),
        )

        result = validate_workflow_approval_request(request)

        self.assertFalse(result.valid)
        self.assertIn("protected_file_review", " ".join(result.errors))

        safe_request = build_workflow_approval_request(
            id="approval-protected-reviewed",
            action=WorkflowApprovalAction.APPLY_PATCH,
            payload_summary=WorkflowApprovalPayloadSummary(
                affected_files=["backend/.env"],
                contains_protected_paths=True,
            ),
        )
        safe_result = validate_workflow_approval_request(safe_request)
        self.assertTrue(safe_result.valid)

    def test_secret_like_payload_values_are_rejected(self):
        with self.assertRaises(ValueError):
            WorkflowApprovalPayloadSummary(description="API_KEY=abc123")

        with self.assertRaises(ValueError):
            WorkflowApprovalPayloadSummary(metadata={"token": "abc123"})

        request = build_workflow_approval_request(
            id="approval-secret-flag",
            action=WorkflowApprovalAction.CREATE_PROPOSAL,
            payload_summary=WorkflowApprovalPayloadSummary(contains_secret_like_values=True),
        )

        result = validate_workflow_approval_request(request)

        self.assertFalse(result.valid)
        self.assertIn("secret-like", " ".join(result.errors))

    def test_approved_status_does_not_make_request_executable(self):
        request = build_workflow_approval_request(
            id="approval-approved",
            action=WorkflowApprovalAction.ANALYZE_RESULT,
            status=WorkflowApprovalStatus.APPROVED,
        )

        result = validate_workflow_approval_request(request)

        self.assertTrue(result.valid)
        self.assertFalse(result.executable_in_v1)
        self.assertIn("does not execute", " ".join(result.warnings))

    def test_contract_module_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(approval_contract_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("import requests", source)
        self.assertNotIn("from requests", source)


if __name__ == "__main__":
    unittest.main()

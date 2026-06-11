"""Tests for the pure workflow approval storage contract."""

from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timedelta

import src.approvals.workflow_approval_storage_contract as storage_contract_module
from src.approvals.workflow_approval_contract import (
    WorkflowApprovalAction,
    WorkflowApprovalRequirement,
    WorkflowApprovalRisk,
)
from src.approvals.workflow_approval_storage_contract import (
    WorkflowApprovalDecisionRecord,
    WorkflowApprovalExecutionLink,
    WorkflowApprovalLinkScope,
    WorkflowApprovalStorageRecord,
    WorkflowApprovalStorageSnapshot,
    WorkflowApprovalStorageStatus,
    WorkflowApprovalStoredPayloadSummary,
    build_approval_storage_snapshot,
    can_transition_approval_status,
    describe_approval_status_transition,
    is_approval_executable_from_storage,
    validate_approval_storage_record,
)


def _record(
    *,
    action: WorkflowApprovalAction = WorkflowApprovalAction.APPLY_PATCH,
    status: WorkflowApprovalStorageStatus = WorkflowApprovalStorageStatus.PENDING,
    risk: WorkflowApprovalRisk = WorkflowApprovalRisk.HIGH,
    confirmations: list[WorkflowApprovalRequirement] | None = None,
    expires_at: str | None = None,
    payload: WorkflowApprovalStoredPayloadSummary | None = None,
) -> WorkflowApprovalStorageRecord:
    return WorkflowApprovalStorageRecord(
        id="approval-storage-1",
        action=action,
        status=status,
        risk_level=risk,
        title="Approval storage record",
        reason="Contract test",
        payload_summary_json=payload or WorkflowApprovalStoredPayloadSummary(
            description="Apply reviewed patch",
            affected_files=["frontend/src/pages/NewTask.tsx"],
        ),
        required_confirmations=confirmations
        if confirmations is not None
        else [
            WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
            WorkflowApprovalRequirement.EXPLICIT_CHECKBOX,
            WorkflowApprovalRequirement.PROTECTED_FILE_REVIEW,
        ],
        expires_at=expires_at,
        decided_at=datetime.now().isoformat() if status == WorkflowApprovalStorageStatus.APPROVED else None,
        approved_by="operator" if status == WorkflowApprovalStorageStatus.APPROVED else None,
    )


class TestWorkflowApprovalStorageModels(unittest.TestCase):
    """Storage model shape and serialization tests."""

    def test_storage_record_serializes_and_deserializes(self):
        record = WorkflowApprovalStorageRecord(
            id="approval-storage-serialize",
            project_id="project-1",
            run_id="run-1",
            step_id="step-1",
            intake_session_id="intake-1",
            action=WorkflowApprovalAction.RUN_TESTS,
            status=WorkflowApprovalStorageStatus.PENDING,
            risk_level=WorkflowApprovalRisk.MEDIUM,
            title="Run tests",
            reason="Verify patch",
            payload_summary_json=WorkflowApprovalStoredPayloadSummary(command_summary="pytest -q"),
            required_confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.COMMAND_ALLOWLIST_CHECK,
            ],
            policy_version="workflow-approval-storage-v1",
        )

        data = record.model_dump()
        restored = WorkflowApprovalStorageRecord.model_validate(data)

        self.assertEqual(restored.id, "approval-storage-serialize")
        self.assertEqual(restored.action, WorkflowApprovalAction.RUN_TESTS)
        self.assertEqual(restored.status, WorkflowApprovalStorageStatus.PENDING)
        self.assertEqual(restored.risk_level, WorkflowApprovalRisk.MEDIUM)
        self.assertEqual(restored.tool_call_id, None)
        self.assertEqual(restored.intake_session_id, "intake-1")

    def test_optional_links_work_before_execution(self):
        record = _record()

        self.assertIsNone(record.project_id)
        self.assertIsNone(record.run_id)
        self.assertIsNone(record.step_id)
        self.assertIsNone(record.tool_call_id)
        self.assertIsNone(record.intake_session_id)
        self.assertTrue(validate_approval_storage_record(record).valid)

    def test_snapshot_supports_decisions_and_execution_link(self):
        record = _record(status=WorkflowApprovalStorageStatus.APPROVED)
        decision = WorkflowApprovalDecisionRecord(
            id="decision-1",
            approval_request_id=record.id,
            status=WorkflowApprovalStorageStatus.APPROVED,
            decided_by="operator",
        )
        execution_link = WorkflowApprovalExecutionLink(
            approval_request_id=record.id,
            tool_call_id="tool-call-1",
        )

        snapshot = build_approval_storage_snapshot(
            record=record,
            decisions=[decision],
            execution_link=execution_link,
        )

        self.assertIsInstance(snapshot, WorkflowApprovalStorageSnapshot)
        self.assertEqual(snapshot.execution_link.tool_call_id, "tool-call-1")
        self.assertEqual(len(snapshot.decisions), 1)

    def test_link_scope_values_are_stable(self):
        self.assertEqual(WorkflowApprovalLinkScope.PROJECT.value, "project")
        self.assertEqual(WorkflowApprovalLinkScope.RUN.value, "run")
        self.assertEqual(WorkflowApprovalLinkScope.TOOL_CALL.value, "tool_call")


class TestWorkflowApprovalStorageLifecycle(unittest.TestCase):
    """Status transition and executability tests."""

    def test_status_transitions(self):
        self.assertTrue(
            can_transition_approval_status(
                WorkflowApprovalStorageStatus.DRAFT,
                WorkflowApprovalStorageStatus.PENDING,
            )
        )
        self.assertTrue(
            can_transition_approval_status(
                WorkflowApprovalStorageStatus.PENDING,
                WorkflowApprovalStorageStatus.APPROVED,
            )
        )
        self.assertTrue(
            can_transition_approval_status(
                WorkflowApprovalStorageStatus.PENDING,
                WorkflowApprovalStorageStatus.REJECTED,
            )
        )
        self.assertFalse(
            can_transition_approval_status(
                WorkflowApprovalStorageStatus.REJECTED,
                WorkflowApprovalStorageStatus.APPROVED,
            )
        )
        transition = describe_approval_status_transition(
            WorkflowApprovalStorageStatus.REJECTED,
            WorkflowApprovalStorageStatus.APPROVED,
        )
        self.assertFalse(transition.allowed)

    def test_rejected_expired_cancelled_cannot_execute(self):
        for status in (
            WorkflowApprovalStorageStatus.REJECTED,
            WorkflowApprovalStorageStatus.EXPIRED,
            WorkflowApprovalStorageStatus.CANCELLED,
        ):
            with self.subTest(status=status.value):
                record = _record(status=status)
                self.assertFalse(is_approval_executable_from_storage(record))

    def test_expired_approved_record_cannot_execute(self):
        record = _record(
            status=WorkflowApprovalStorageStatus.APPROVED,
            expires_at=(datetime.now() - timedelta(minutes=1)).isoformat(),
        )

        self.assertFalse(is_approval_executable_from_storage(record))

    def test_pending_without_confirmations_cannot_execute(self):
        record = _record(
            status=WorkflowApprovalStorageStatus.PENDING,
            confirmations=[],
        )
        result = validate_approval_storage_record(record)

        self.assertFalse(result.valid)
        self.assertFalse(result.executable)
        self.assertIn("missing required confirmations", " ".join(result.errors))

    def test_tool_call_id_is_optional_before_execution_and_guarded_after(self):
        before_execution = _record(status=WorkflowApprovalStorageStatus.APPROVED)
        self.assertIsNone(before_execution.tool_call_id)
        self.assertTrue(validate_approval_storage_record(before_execution).valid)
        self.assertTrue(is_approval_executable_from_storage(before_execution))

        invalid_after_execution = _record(status=WorkflowApprovalStorageStatus.APPROVED)
        invalid_after_execution.tool_call_id = "tool-call-1"
        invalid_result = validate_approval_storage_record(invalid_after_execution)
        self.assertFalse(invalid_result.valid)
        self.assertIn("execution_attempted_at", " ".join(invalid_result.errors))

        attempted = _record(status=WorkflowApprovalStorageStatus.APPROVED)
        attempted.tool_call_id = "tool-call-1"
        attempted.execution_attempted_at = datetime.now().isoformat()
        attempted_result = validate_approval_storage_record(attempted)
        self.assertTrue(attempted_result.valid)
        self.assertFalse(is_approval_executable_from_storage(attempted))


class TestWorkflowApprovalStorageSafetyRules(unittest.TestCase):
    """Risk, confirmation, and sanitization tests."""

    def test_apply_patch_high_risk_requires_explicit_confirmation(self):
        record = _record(
            action=WorkflowApprovalAction.APPLY_PATCH,
            risk=WorkflowApprovalRisk.HIGH,
            confirmations=[WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
        )

        result = validate_approval_storage_record(record)

        self.assertFalse(result.valid)
        self.assertIn("explicit_checkbox", " ".join(result.errors))

    def test_run_tests_requires_command_allowlist_confirmation(self):
        record = _record(
            action=WorkflowApprovalAction.RUN_TESTS,
            risk=WorkflowApprovalRisk.MEDIUM,
            confirmations=[WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
            payload=WorkflowApprovalStoredPayloadSummary(command_summary="pytest -q"),
        )

        result = validate_approval_storage_record(record)

        self.assertFalse(result.valid)
        self.assertIn("command_allowlist_check", " ".join(result.errors))

    def test_external_provider_record_remains_non_executable_and_critical(self):
        record = _record(
            action=WorkflowApprovalAction.EXTERNAL_PROVIDER_EXECUTION,
            status=WorkflowApprovalStorageStatus.APPROVED,
            risk=WorkflowApprovalRisk.CRITICAL,
            confirmations=[
                WorkflowApprovalRequirement.MANUAL_CONFIRMATION,
                WorkflowApprovalRequirement.PROVIDER_PERMISSION_CHECK,
            ],
            payload=WorkflowApprovalStoredPayloadSummary(provider_summary="Claude provider execution request"),
        )

        result = validate_approval_storage_record(record)

        self.assertTrue(result.valid)
        self.assertFalse(result.executable)
        self.assertFalse(is_approval_executable_from_storage(record))

    def test_secret_like_payload_values_are_rejected_or_flagged(self):
        with self.assertRaises(ValueError):
            WorkflowApprovalStoredPayloadSummary(description="API_KEY=abc123")

        with self.assertRaises(ValueError):
            WorkflowApprovalStoredPayloadSummary(metadata={"secret": "abc123"})

        record = _record(
            payload=WorkflowApprovalStoredPayloadSummary(contains_secret_like_values=True)
        )
        result = validate_approval_storage_record(record)
        self.assertFalse(result.valid)
        self.assertIn("secret-like", " ".join(result.errors))

    def test_protected_env_paths_are_flagged(self):
        record = _record(
            action=WorkflowApprovalAction.CREATE_PROPOSAL,
            risk=WorkflowApprovalRisk.MEDIUM,
            confirmations=[WorkflowApprovalRequirement.MANUAL_CONFIRMATION],
            payload=WorkflowApprovalStoredPayloadSummary(
                affected_files=["backend/.env"],
                contains_protected_paths=False,
            ),
        )

        result = validate_approval_storage_record(record)

        self.assertFalse(result.valid)
        self.assertIn("protected_file_review", " ".join(result.errors))
        self.assertIn("protected paths", " ".join(result.warnings))

    def test_raw_payload_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            WorkflowApprovalStoredPayloadSummary(
                patch_summary="diff --git a/app.py b/app.py\n+secret",
            )

        with self.assertRaises(ValueError):
            WorkflowApprovalStoredPayloadSummary(metadata={"stdout": "full command output"})

        record = _record(
            payload=WorkflowApprovalStoredPayloadSummary(raw_payload_omitted=False)
        )
        result = validate_approval_storage_record(record)
        self.assertFalse(result.valid)
        self.assertIn("raw payload", " ".join(result.errors))

    def test_storage_contract_module_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(storage_contract_module)

        self.assertNotIn("src.storage", source)
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

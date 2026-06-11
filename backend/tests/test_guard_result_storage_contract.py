"""Tests for the pure Source-of-Truth Guard result storage contract."""

from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timedelta

import src.orchestrator.guard_result_storage_contract as guard_storage_module
from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardResultRecord,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
    compare_guard_input_to_patch_payload,
    compare_guard_requirement_context,
    hash_guard_text,
    is_guard_result_usable_for_proposal,
    mark_guard_result_stale,
)


def _record(
    *,
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
    warning_acknowledged: bool = False,
    no_guard_override: bool = False,
    expires_at: datetime | None = None,
) -> WorkflowGuardResultRecord:
    return build_workflow_guard_result_record(
        id="guard-result-1",
        project_id="project-1",
        run_id="run-1",
        step_id="step-1",
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["Dashboard can filter records"],
            constraints=["Preserve existing React stack"],
            forbidden_changes=["Do not touch .env"],
            validation_notes=["Manual review required"],
            source_of_truth_summary="Build dashboard workflow",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-001"],
            warnings=["Review requirement link"] if decision == WorkflowGuardDecision.WARNING else [],
            reasons=["Requirement context matched"],
            recommended_next_step="Proceed manually.",
        ),
        warning_acknowledged=warning_acknowledged,
        no_guard_override=no_guard_override,
        expires_at=expires_at,
    )


class TestWorkflowGuardStorageSnapshots(unittest.TestCase):
    """Snapshot hashing and serialization tests."""

    def test_input_snapshot_hashes_old_and_new_text_without_storing_raw_text(self):
        snapshot = build_guard_input_snapshot(
            proposed_action="Implement login",
            file_path="frontend/src/Login.tsx",
            patch_summary="Login patch",
            old_text="const password = 'not stored raw';",
            new_text="const password = 'still not stored raw';",
        )

        self.assertEqual(snapshot.old_text_hash, hash_guard_text("const password = 'not stored raw';"))
        self.assertEqual(snapshot.new_text_hash, hash_guard_text("const password = 'still not stored raw';"))
        dumped = snapshot.model_dump()
        self.assertNotIn("old_text", dumped)
        self.assertNotIn("new_text", dumped)
        self.assertNotIn("not stored raw", str(dumped))

    def test_input_snapshot_changes_when_file_path_changes(self):
        first = build_guard_input_snapshot(
            proposed_action="Implement REQ-001",
            file_path="frontend/src/A.tsx",
            patch_summary="Patch",
        )
        second = build_guard_input_snapshot(
            proposed_action="Implement REQ-001",
            file_path="frontend/src/B.tsx",
            patch_summary="Patch",
        )

        self.assertNotEqual(first.input_hash, second.input_hash)

    def test_requirement_context_hash_changes_when_requirement_ids_change(self):
        first = build_requirement_context_snapshot(requirement_ids=["REQ-001"])
        second = build_requirement_context_snapshot(requirement_ids=["REQ-002"])

        self.assertNotEqual(first.context_hash, second.context_hash)

    def test_result_hash_changes_when_decision_changes(self):
        allowed = build_guard_result_snapshot(
            decision=WorkflowGuardDecision.ALLOWED,
            drift_risk=WorkflowGuardDriftRisk.LOW,
        )
        blocked = build_guard_result_snapshot(
            decision=WorkflowGuardDecision.BLOCKED,
            drift_risk=WorkflowGuardDriftRisk.CRITICAL,
        )

        self.assertNotEqual(allowed.result_hash, blocked.result_hash)

    def test_record_serializes_through_pydantic(self):
        record = _record()

        restored = WorkflowGuardResultRecord.model_validate(record.model_dump())

        self.assertEqual(restored.id, "guard-result-1")
        self.assertEqual(restored.source, WorkflowGuardSource.RUN_STEP_GUARD)
        self.assertEqual(restored.result_snapshot.decision, WorkflowGuardDecision.ALLOWED)
        self.assertEqual(restored.requirement_context_snapshot.requirement_ids, ["REQ-001"])


class TestWorkflowGuardStorageStaleness(unittest.TestCase):
    """Pure stale detection tests."""

    def test_stale_detection_catches_file_path_mismatch(self):
        record = _record()

        result = compare_guard_input_to_patch_payload(
            record,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/Other.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        self.assertTrue(result.is_stale)
        self.assertIn(WorkflowGuardStaleReason.FILE_PATH_CHANGED, result.stale_reasons)
        self.assertIn(WorkflowGuardStaleReason.PROPOSAL_PAYLOAD_MISMATCH, result.stale_reasons)

    def test_stale_detection_catches_patch_summary_mismatch(self):
        record = _record()

        result = compare_guard_input_to_patch_payload(
            record,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Different patch summary",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        self.assertTrue(result.is_stale)
        self.assertIn(WorkflowGuardStaleReason.PATCH_SUMMARY_CHANGED, result.stale_reasons)

    def test_stale_detection_catches_old_and_new_text_mismatch(self):
        record = _record()

        result = compare_guard_input_to_patch_payload(
            record,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="changed old",
            new_text="changed new",
        )

        self.assertIn(WorkflowGuardStaleReason.OLD_TEXT_CHANGED, result.stale_reasons)
        self.assertIn(WorkflowGuardStaleReason.NEW_TEXT_CHANGED, result.stale_reasons)

    def test_expired_record_is_stale(self):
        record = _record(expires_at=datetime.now() - timedelta(minutes=1))

        result = compare_guard_input_to_patch_payload(
            record,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        self.assertTrue(result.is_stale)
        self.assertIn(WorkflowGuardStaleReason.EXPIRED, result.stale_reasons)

    def test_requirement_context_mismatch_is_stale(self):
        record = _record()
        changed_context = build_requirement_context_snapshot(requirement_ids=["REQ-002"])

        result = compare_guard_requirement_context(record, changed_context)

        self.assertTrue(result.is_stale)
        self.assertEqual(result.stale_reasons, [WorkflowGuardStaleReason.REQUIREMENT_CONTEXT_CHANGED])

    def test_mark_stale_returns_copy_without_mutating_input(self):
        record = _record()

        stale = mark_guard_result_stale(record, WorkflowGuardStaleReason.MANUAL_INVALIDATION)

        self.assertFalse(record.is_stale)
        self.assertTrue(stale.is_stale)
        self.assertIn(WorkflowGuardStaleReason.MANUAL_INVALIDATION, stale.stale_reasons)


class TestWorkflowGuardStorageUsability(unittest.TestCase):
    """Proposal usability rules."""

    def test_blocked_record_is_not_usable(self):
        record = _record(decision=WorkflowGuardDecision.BLOCKED)

        self.assertFalse(is_guard_result_usable_for_proposal(record))

    def test_warning_record_requires_acknowledgement(self):
        unacknowledged = _record(decision=WorkflowGuardDecision.WARNING, warning_acknowledged=False)
        acknowledged = _record(decision=WorkflowGuardDecision.WARNING, warning_acknowledged=True)

        self.assertFalse(is_guard_result_usable_for_proposal(unacknowledged))
        self.assertTrue(is_guard_result_usable_for_proposal(acknowledged))

    def test_allowed_non_stale_record_is_usable(self):
        record = _record(decision=WorkflowGuardDecision.ALLOWED)

        self.assertTrue(is_guard_result_usable_for_proposal(record))

    def test_stale_record_is_not_usable(self):
        record = mark_guard_result_stale(_record(), WorkflowGuardStaleReason.PATCH_FORM_CHANGED)

        self.assertFalse(is_guard_result_usable_for_proposal(record))

    def test_no_guard_override_does_not_override_blocked_guard(self):
        record = _record(decision=WorkflowGuardDecision.BLOCKED, no_guard_override=True)

        self.assertFalse(is_guard_result_usable_for_proposal(record))

    def test_empty_context_warning_can_be_usable_if_acknowledged(self):
        record = build_workflow_guard_result_record(
            id="guard-result-empty-context",
            run_id="run-1",
            step_id="step-1",
            input_snapshot=build_guard_input_snapshot(proposed_action="Review unlinked step"),
            requirement_context_snapshot=build_requirement_context_snapshot(),
            result_snapshot=build_guard_result_snapshot(
                decision=WorkflowGuardDecision.WARNING,
                drift_risk=WorkflowGuardDriftRisk.HIGH,
                warnings=["Step has no linked requirement ids."],
            ),
            warning_acknowledged=True,
        )

        self.assertTrue(is_guard_result_usable_for_proposal(record))


class TestWorkflowGuardStoragePurity(unittest.TestCase):
    """Import and determinism checks."""

    def test_module_has_no_database_routes_provider_or_tool_imports(self):
        source = inspect.getsource(guard_storage_module)

        forbidden = [
            "storage.database",
            "src.api.routes",
            "orchestrator.engine",
            "project_tools",
            "providers",
            "create_tool_call",
            "execute_run",
        ]
        for item in forbidden:
            with self.subTest(item=item):
                self.assertNotIn(item, source)

    def test_helpers_are_deterministic(self):
        first = build_guard_input_snapshot(
            proposed_action="Implement REQ-001",
            file_path="frontend/src/App.tsx",
            patch_summary="Patch app",
            old_text="old",
            new_text="new",
        )
        second = build_guard_input_snapshot(
            proposed_action="Implement REQ-001",
            file_path="frontend/src/App.tsx",
            patch_summary="Patch app",
            old_text="old",
            new_text="new",
        )

        self.assertEqual(first.input_hash, second.input_hash)
        self.assertEqual(first.old_text_hash, second.old_text_hash)
        self.assertEqual(first.new_text_hash, second.new_text_hash)


if __name__ == "__main__":
    unittest.main()

"""Tests for pure Source-of-Truth Guard result API contracts."""

from __future__ import annotations

import inspect
import unittest
from datetime import datetime, timedelta

import src.orchestrator.guard_result_api_contract as guard_api_module
from src.orchestrator.guard_result_api_contract import (
    CreateWorkflowGuardResultRequest,
    GuardResultApiError,
    LinkGuardResultToProposalRequest,
    ListWorkflowGuardResultsRequest,
    ValidateGuardResultForProposalRequest,
    WorkflowGuardResultApiResponse,
    WorkflowGuardResultListResponse,
    build_guard_result_api_error,
    build_guard_result_api_response,
    build_guard_result_validation_response,
    build_link_guard_result_to_proposal_response,
    validate_create_guard_result_request,
    validate_guard_result_for_proposal,
    validate_guard_result_link_request,
    validate_list_guard_results_request,
)
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
        id="guard-api-1",
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


class TestGuardResultApiRequests(unittest.TestCase):
    """Request validation tests."""

    def test_create_request_validates_required_fields(self):
        request = CreateWorkflowGuardResultRequest(
            run_id="",
            step_id=" ",
            proposed_action="",
        )

        result = validate_create_guard_result_request(request)

        self.assertFalse(result.valid)
        self.assertEqual(
            {error.code for error in result.errors},
            {"run_id_required", "step_id_required", "proposed_action_required"},
        )

    def test_create_request_serializes(self):
        request = CreateWorkflowGuardResultRequest(
            run_id="run-1",
            step_id="step-1",
            project_id="project-1",
            proposed_action="Check REQ-001",
            file_path="frontend/src/App.tsx",
            patch_summary="Review patch",
            old_text="raw old text",
            new_text="raw new text",
            source=WorkflowGuardSource.RUN_STEP_GUARD,
        )

        restored = CreateWorkflowGuardResultRequest.model_validate(request.model_dump())

        self.assertEqual(restored.run_id, "run-1")
        self.assertEqual(restored.source, WorkflowGuardSource.RUN_STEP_GUARD)
        self.assertTrue(validate_create_guard_result_request(restored).valid)

    def test_list_request_enforces_limit_bounds(self):
        low = ListWorkflowGuardResultsRequest(limit=0)
        high = ListWorkflowGuardResultsRequest(limit=201)
        valid = ListWorkflowGuardResultsRequest(limit=200, offset=0)

        self.assertFalse(validate_list_guard_results_request(low).valid)
        self.assertFalse(validate_list_guard_results_request(high).valid)
        self.assertTrue(validate_list_guard_results_request(valid).valid)

    def test_list_request_enforces_offset_bounds(self):
        result = validate_list_guard_results_request(ListWorkflowGuardResultsRequest(offset=-1))

        self.assertFalse(result.valid)
        self.assertIn("offset_out_of_bounds", [error.code for error in result.errors])


class TestGuardResultApiResponses(unittest.TestCase):
    """Response wrapper and serialization tests."""

    def test_api_response_wraps_record(self):
        record = _record()

        response = build_guard_result_api_response(record)
        restored = WorkflowGuardResultApiResponse.model_validate(response.model_dump())

        self.assertTrue(restored.usable_for_proposal)
        self.assertEqual(restored.guard_result.id, record.id)
        self.assertEqual(restored.guard_result.result_snapshot.decision, WorkflowGuardDecision.ALLOWED)

    def test_list_response_serializes(self):
        response = WorkflowGuardResultListResponse(
            items=[build_guard_result_api_response(_record())],
            total=1,
            limit=50,
            offset=0,
        )

        restored = WorkflowGuardResultListResponse.model_validate(response.model_dump())

        self.assertEqual(restored.total, 1)
        self.assertEqual(len(restored.items), 1)

    def test_api_error_serializes(self):
        error = build_guard_result_api_error(
            "test_error",
            "Something happened",
            field="guard_result_id",
            details={"id": "guard-api-1"},
        )

        restored = GuardResultApiError.model_validate(error.model_dump())

        self.assertEqual(restored.code, "test_error")
        self.assertEqual(restored.field, "guard_result_id")
        self.assertEqual(restored.details, {"id": "guard-api-1"})


class TestGuardResultProposalValidation(unittest.TestCase):
    """Proposal validation contract tests."""

    def test_validation_response_blocks_stale_guard(self):
        record = mark_guard_result_stale(_record(), WorkflowGuardStaleReason.PATCH_FORM_CHANGED)
        request = ValidateGuardResultForProposalRequest(
            guard_result_id=record.id,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        response = validate_guard_result_for_proposal(request, record)

        self.assertFalse(response.usable)
        self.assertTrue(response.stale)
        self.assertIn(WorkflowGuardStaleReason.PATCH_FORM_CHANGED, response.stale_reasons)

    def test_validation_response_blocks_expired_guard(self):
        record = _record(expires_at=datetime.now() - timedelta(minutes=1))
        request = ValidateGuardResultForProposalRequest(
            guard_result_id=record.id,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        response = validate_guard_result_for_proposal(request, record)

        self.assertFalse(response.usable)
        self.assertTrue(response.stale)
        self.assertIn(WorkflowGuardStaleReason.EXPIRED, response.stale_reasons)

    def test_validation_response_blocks_blocked_guard(self):
        record = _record(decision=WorkflowGuardDecision.BLOCKED)
        request = ValidateGuardResultForProposalRequest(
            guard_result_id=record.id,
            proposed_action="Implement REQ-001 dashboard filter",
            file_path="frontend/src/pages/Dashboard.tsx",
            patch_summary="Add dashboard filter for REQ-001",
            old_text="old dashboard",
            new_text="new dashboard",
        )

        response = validate_guard_result_for_proposal(request, record)

        self.assertFalse(response.usable)
        self.assertFalse(response.stale)
        self.assertIn("Blocked guard result", " ".join(response.blocking_reasons))

    def test_warning_guard_requires_acknowledgement(self):
        unacknowledged = _record(decision=WorkflowGuardDecision.WARNING, warning_acknowledged=False)
        acknowledged = _record(decision=WorkflowGuardDecision.WARNING, warning_acknowledged=True)

        first = build_guard_result_validation_response(unacknowledged)
        second = build_guard_result_validation_response(acknowledged)

        self.assertFalse(first.usable)
        self.assertTrue(first.requires_warning_acknowledgement)
        self.assertTrue(second.usable)
        self.assertFalse(second.requires_warning_acknowledgement)

    def test_no_guard_override_does_not_override_blocked_guard(self):
        record = _record(decision=WorkflowGuardDecision.BLOCKED, no_guard_override=True)
        request = ValidateGuardResultForProposalRequest(
            guard_result_id=record.id,
            proposed_action="Implement REQ-001 dashboard filter",
        )

        response = validate_guard_result_for_proposal(request, record)

        self.assertFalse(response.usable)
        self.assertIn("no_guard_override", " ".join(response.blocking_reasons))

    def test_missing_record_fails_closed(self):
        response = validate_guard_result_for_proposal(
            ValidateGuardResultForProposalRequest(
                guard_result_id="missing",
                proposed_action="Patch",
            ),
            None,
        )

        self.assertFalse(response.usable)
        self.assertEqual(response.decision, WorkflowGuardDecision.BLOCKED)


class TestGuardResultApiLinks(unittest.TestCase):
    """Future link request/response tests."""

    def test_link_response_records_stale_and_usable_state(self):
        record = _record()
        request = LinkGuardResultToProposalRequest(
            guard_result_id=record.id,
            proposal_tool_call_id="proposal-tool-call-1",
        )

        validation = validate_guard_result_link_request(request, record)
        response = build_link_guard_result_to_proposal_response(request, record)

        self.assertTrue(validation.valid)
        self.assertTrue(response.linked)
        self.assertFalse(response.was_stale_at_link_time)
        self.assertTrue(response.usable_at_link_time)

    def test_link_response_refuses_blocked_guard(self):
        record = _record(decision=WorkflowGuardDecision.BLOCKED)
        request = LinkGuardResultToProposalRequest(
            guard_result_id=record.id,
            proposal_tool_call_id="proposal-tool-call-1",
            no_guard_override=True,
        )

        validation = validate_guard_result_link_request(request, record)
        response = build_link_guard_result_to_proposal_response(request, record)

        self.assertFalse(validation.valid)
        self.assertFalse(response.linked)
        self.assertFalse(response.usable_at_link_time)
        self.assertIn("Blocked guard result", " ".join(response.warnings))

    def test_link_request_requires_ids(self):
        result = validate_guard_result_link_request(
            LinkGuardResultToProposalRequest(
                guard_result_id="",
                proposal_tool_call_id="",
            )
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            {error.code for error in result.errors},
            {"guard_result_id_required", "proposal_tool_call_id_required"},
        )


class TestGuardResultApiPurity(unittest.TestCase):
    """Import and determinism tests."""

    def test_module_has_no_database_routes_provider_or_tool_imports(self):
        source = inspect.getsource(guard_api_module)

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
        record = _record()
        first = build_guard_result_validation_response(record)
        second = build_guard_result_validation_response(record)

        self.assertEqual(first.model_dump(), second.model_dump())


if __name__ == "__main__":
    unittest.main()

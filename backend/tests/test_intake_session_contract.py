"""Tests for the pure future IntakeSession storage contract."""

from __future__ import annotations

import inspect
import unittest

import src.orchestrator.intake_session_contract as contract_module
from src.orchestrator.intake_session_contract import (
    IntakeAnswerContract,
    IntakeBriefVersionContract,
    IntakePlanVersionContract,
    IntakeSelectionStatus,
    IntakeSessionContract,
    IntakeSessionSnapshot,
    IntakeSessionStatus,
    IntakeSourceMode,
    IntakeVersionKind,
    build_intake_session_snapshot,
    summarize_intake_session_lifecycle,
    validate_intake_session_contract,
)


class TestIntakeSessionContractModels(unittest.TestCase):
    """Model shape and serialization tests."""

    def test_session_contract_serializes_and_deserializes(self):
        session = IntakeSessionContract(
            id="intake-1",
            raw_idea="Build a local-first CRM",
            mode=IntakeSourceMode.NEW_PROJECT,
            status=IntakeSessionStatus.NEEDS_ANSWERS,
            readiness="needs_answers",
            source_metadata={"source": "new-task", "ignore_paths": [".env", "node_modules"]},
        )

        data = session.model_dump()
        restored = IntakeSessionContract.model_validate(data)

        self.assertEqual(restored.id, "intake-1")
        self.assertEqual(restored.mode, IntakeSourceMode.NEW_PROJECT)
        self.assertEqual(restored.status, IntakeSessionStatus.NEEDS_ANSWERS)
        self.assertIsNone(restored.project_id)
        self.assertIsNone(restored.run_id)

    def test_status_and_enum_values_are_stable(self):
        self.assertEqual(IntakeSessionStatus.DRAFT.value, "draft")
        self.assertEqual(IntakeSessionStatus.READY_TO_CREATE_RUN.value, "ready_to_create_run")
        self.assertEqual(IntakeSourceMode.EXISTING_PROJECT.value, "existing_project")
        self.assertEqual(IntakeVersionKind.INTAKE_RESPONSE.value, "intake_response")
        self.assertEqual(IntakeSelectionStatus.SUPERSEDED.value, "superseded")

    def test_project_and_run_ids_are_optional_until_confirmation(self):
        session = IntakeSessionContract(
            id="intake-optional-links",
            raw_idea="Continue an existing project",
            mode=IntakeSourceMode.EXISTING_PROJECT,
        )

        self.assertIsNone(session.project_id)
        self.assertIsNone(session.run_id)
        self.assertIsNone(session.selected_brief_version_id)
        self.assertIsNone(session.selected_plan_version_id)

    def test_version_contract_supports_multiple_versions(self):
        session = IntakeSessionContract(
            id="intake-versions",
            raw_idea="Build a web app",
            selected_brief_version_id="brief-2",
            selected_plan_version_id="plan-2",
        )
        snapshot = build_intake_session_snapshot(
            session=session,
            brief_versions=[
                IntakeBriefVersionContract(
                    id="brief-1",
                    session_id=session.id,
                    version_number=1,
                    selection_status=IntakeSelectionStatus.SUPERSEDED,
                ),
                IntakeBriefVersionContract(
                    id="brief-2",
                    session_id=session.id,
                    version_number=2,
                    selection_status=IntakeSelectionStatus.SELECTED,
                ),
            ],
            plan_versions=[
                IntakePlanVersionContract(
                    id="plan-1",
                    session_id=session.id,
                    version_number=1,
                    selection_status=IntakeSelectionStatus.SUPERSEDED,
                ),
                IntakePlanVersionContract(
                    id="plan-2",
                    session_id=session.id,
                    version_number=2,
                    selection_status=IntakeSelectionStatus.SELECTED,
                ),
            ],
        )

        result = validate_intake_session_contract(snapshot)

        self.assertTrue(result.valid)
        self.assertEqual(result.errors, [])
        self.assertEqual(len(snapshot.brief_versions), 2)
        self.assertEqual(len(snapshot.plan_versions), 2)


class TestIntakeSessionContractValidation(unittest.TestCase):
    """Pure validation helper tests."""

    def test_selected_version_ids_are_validated(self):
        session = IntakeSessionContract(
            id="intake-selected",
            raw_idea="Build a dashboard",
            selected_brief_version_id="missing-brief",
        )
        invalid_snapshot = IntakeSessionSnapshot(session=session)

        invalid_result = validate_intake_session_contract(invalid_snapshot)
        self.assertFalse(invalid_result.valid)
        self.assertIn("selected_brief_version_id", " ".join(invalid_result.errors))

        valid_snapshot = build_intake_session_snapshot(
            session=session,
            brief_versions=[
                IntakeBriefVersionContract(
                    id="missing-brief",
                    session_id=session.id,
                    version_number=1,
                )
            ],
        )
        valid_result = validate_intake_session_contract(valid_snapshot)
        self.assertTrue(valid_result.valid)

    def test_cross_session_versions_are_rejected(self):
        snapshot = build_intake_session_snapshot(
            session=IntakeSessionContract(id="intake-main", raw_idea="Build app"),
            answers=[
                IntakeAnswerContract(
                    id="answer-1",
                    session_id="other-session",
                    question_id="q-1",
                    category="product_goal",
                    priority="required",
                    question_text_snapshot="What is the goal?",
                    answer_text="Build a CRM",
                )
            ],
            plan_versions=[
                IntakePlanVersionContract(
                    id="plan-1",
                    session_id="other-session",
                    version_number=1,
                )
            ],
        )

        result = validate_intake_session_contract(snapshot)

        self.assertFalse(result.valid)
        self.assertGreaterEqual(len(result.errors), 2)

    def test_lifecycle_summary_mentions_project_run_later(self):
        snapshot = build_intake_session_snapshot(
            session=IntakeSessionContract(
                id="intake-life",
                raw_idea="Existing project onboarding",
                mode=IntakeSourceMode.EXISTING_PROJECT,
            )
        )

        summary = summarize_intake_session_lifecycle(snapshot)

        self.assertIn("IntakeSession", summary)
        self.assertIn("Project", summary)
        self.assertIn("Run", summary)
        self.assertIn("explicit user confirmation", summary)

    def test_sensitive_answer_values_are_not_allowed(self):
        with self.assertRaises(ValueError):
            IntakeAnswerContract(
                id="answer-secret",
                session_id="intake-secret",
                question_id="q-secret",
                category="constraints",
                priority="recommended",
                question_text_snapshot="What env values are needed?",
                answer_text="API_KEY=abc123",
            )

        redacted = IntakeAnswerContract(
            id="answer-redacted",
            session_id="intake-secret",
            question_id="q-secret",
            category="constraints",
            priority="recommended",
            question_text_snapshot="What env values are needed?",
            answer_text="[redacted]",
            is_sensitive=True,
            redacted=True,
        )
        self.assertTrue(redacted.redacted)

    def test_sensitive_metadata_keys_are_not_allowed(self):
        with self.assertRaises(ValueError):
            IntakeSessionContract(
                id="intake-secret-metadata",
                raw_idea="Build app",
                source_metadata={"api_key": "abc123"},
            )

        safe = IntakeSessionContract(
            id="intake-safe-metadata",
            raw_idea="Build app",
            source_metadata={"ignore_paths": [".env", "*.pem"], "source": "new-task"},
        )
        self.assertIn(".env", safe.source_metadata["ignore_paths"])

    def test_contract_module_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(contract_module)

        self.assertNotIn("src.storage", source)
        self.assertNotIn("src.project_tools", source)
        self.assertNotIn("src.providers", source)
        self.assertNotIn("create_run(", source)
        self.assertNotIn("create_project(", source)
        self.assertNotIn("create_tool_call(", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()

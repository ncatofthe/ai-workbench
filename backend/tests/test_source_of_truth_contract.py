"""Tests for pure project source-of-truth contract."""

from __future__ import annotations

import inspect
import unittest

import src.orchestrator.source_of_truth_contract as source_contract_module
from src.orchestrator.source_of_truth_contract import (
    AcceptanceStatus,
    DriftRiskLevel,
    ProjectAcceptanceCriterion,
    ProjectAntiDriftRule,
    ProjectConstraintContract,
    ProjectInputSourceType,
    ProjectRequirementContract,
    ProjectSourceOfTruthContract,
    RequirementPriority,
    RequirementStatus,
    build_requirement_coverage_matrix,
    detect_drift_risk,
    summarize_source_of_truth,
    validate_source_of_truth_contract,
)


def _base_source(source_type: ProjectInputSourceType = ProjectInputSourceType.NEW_IDEA) -> ProjectSourceOfTruthContract:
    return ProjectSourceOfTruthContract(
        id="sot-1",
        source_type=source_type,
        raw_source_summary="Build a local-first CRM for sales managers.",
        project_name="Local CRM",
        product_goal="Help sales managers track leads and follow-ups locally.",
        target_users=["Sales manager"],
        user_roles=["admin", "sales"],
        core_features=["Lead board", "Follow-up reminders"],
        requirements=[
            ProjectRequirementContract(
                id="REQ-1",
                title="Lead management",
                description="Users must create, edit, and archive leads.",
                priority=RequirementPriority.MUST,
                status=RequirementStatus.CONFIRMED,
                acceptance_criteria_ids=["AC-1"],
            ),
            ProjectRequirementContract(
                id="REQ-2",
                title="Follow-up reminders",
                description="Users should see reminders for overdue follow-ups.",
                priority=RequirementPriority.SHOULD,
                status=RequirementStatus.CONFIRMED,
                acceptance_criteria_ids=["AC-2"],
            ),
        ],
        constraints=[
            ProjectConstraintContract(
                id="CON-1",
                title="Do not touch storage layer",
                forbidden_paths=["backend/src/storage"],
                reason="Storage is out of scope for this slice.",
            )
        ],
        forbidden_changes=["backend/src/storage/database.py"],
        acceptance_criteria=[
            ProjectAcceptanceCriterion(
                id="AC-1",
                requirement_id="REQ-1",
                description="A lead can be created and then archived.",
            ),
            ProjectAcceptanceCriterion(
                id="AC-2",
                requirement_id="REQ-2",
                description="Overdue follow-ups are visible in the UI.",
            ),
        ],
        assumptions=["Local prototype first."],
        open_questions=["Should reminders send email later?"],
        anti_drift_rules=[
            ProjectAntiDriftRule(
                id="ADR-1",
                title="Every plan step must link to requirements",
                require_requirement_link=True,
            ),
            ProjectAntiDriftRule(
                id="ADR-2",
                title="Do not modify storage",
                risk_level=DriftRiskLevel.CRITICAL,
                forbidden_patterns=[r"backend/src/storage/"],
            ),
        ],
        definition_of_done=["Requirements covered", "Acceptance criteria checked"],
        created_from="intake-plan-preview",
        confidence="medium",
        readiness="ready_to_plan",
        source_metadata={"source": "test", "ignored_files": [".env"]},
    )


class TestSourceOfTruthModels(unittest.TestCase):
    """Model serialization and scenario support."""

    def test_models_serialize_deserialize(self):
        source = _base_source(ProjectInputSourceType.NEW_IDEA)
        data = source.model_dump()
        restored = ProjectSourceOfTruthContract.model_validate(data)

        self.assertEqual(restored.id, "sot-1")
        self.assertEqual(restored.source_type, ProjectInputSourceType.NEW_IDEA)
        self.assertEqual(restored.requirements[0].priority, RequirementPriority.MUST)
        self.assertEqual(restored.acceptance_criteria[0].status, AcceptanceStatus.NOT_CHECKED)

    def test_supports_client_spec_existing_project_and_new_idea(self):
        for source_type in (
            ProjectInputSourceType.CLIENT_SPEC,
            ProjectInputSourceType.COMMERCIAL_PROPOSAL,
            ProjectInputSourceType.EXISTING_PROJECT,
            ProjectInputSourceType.NEW_IDEA,
            ProjectInputSourceType.MIXED,
        ):
            with self.subTest(source_type=source_type.value):
                source = _base_source(source_type)
                self.assertEqual(source.source_type, source_type)
                self.assertTrue(validate_source_of_truth_contract(source).valid)

    def test_mandatory_requirements_acceptance_forbidden_and_antidrift_are_represented(self):
        source = _base_source()

        self.assertTrue(any(req.priority == RequirementPriority.MUST for req in source.requirements))
        self.assertGreater(len(source.acceptance_criteria), 0)
        self.assertIn("backend/src/storage/database.py", source.forbidden_changes)
        self.assertGreater(len(source.anti_drift_rules), 0)
        self.assertIn("Requirements covered", source.definition_of_done)

    def test_summary_mentions_mission_counts(self):
        summary = summarize_source_of_truth(_base_source(ProjectInputSourceType.CLIENT_SPEC))

        self.assertIn("Local CRM", summary)
        self.assertIn("client_spec", summary)
        self.assertIn("2 requirements", summary)
        self.assertIn("1 mandatory", summary)


class TestSourceOfTruthValidation(unittest.TestCase):
    """Validation and guardrail tests."""

    def test_validation_flags_missing_mission_users_requirements_and_acceptance(self):
        source = ProjectSourceOfTruthContract(
            id="sot-empty",
            source_type=ProjectInputSourceType.UNKNOWN,
            product_goal="",
            target_users=[],
            requirements=[
                ProjectRequirementContract(
                    id="REQ-X",
                    title="Unknown priority requirement",
                    priority=RequirementPriority.UNKNOWN,
                )
            ],
            acceptance_criteria=[],
        )

        result = validate_source_of_truth_contract(source)

        self.assertFalse(result.valid)
        joined = " ".join(result.errors)
        self.assertIn("product_goal", joined)
        self.assertIn("Target users", joined)
        self.assertIn("mandatory requirement", joined)
        self.assertIn("Acceptance criteria", joined)
        self.assertIn("unknown priority", joined)

    def test_validation_flags_conflicting_requirements(self):
        source = _base_source()
        source.requirements[0].conflicts_with = ["REQ-2"]

        result = validate_source_of_truth_contract(source)

        self.assertFalse(result.valid)
        self.assertIn("conflicts", " ".join(result.errors))

    def test_secret_like_source_metadata_is_rejected(self):
        with self.assertRaises(ValueError):
            ProjectSourceOfTruthContract(
                id="sot-secret",
                product_goal="Build app",
                source_metadata={"api_key": "abc123"},
            )

        with self.assertRaises(ValueError):
            ProjectSourceOfTruthContract(
                id="sot-secret-value",
                product_goal="Build app",
                source_metadata={"notes": "TOKEN=abc123"},
            )


class TestRequirementCoverageAndDrift(unittest.TestCase):
    """Coverage matrix and drift risk helpers."""

    def test_coverage_matrix_marks_covered_and_missing_requirements(self):
        source = _base_source()
        matrix = build_requirement_coverage_matrix(
            source,
            plan_requirement_links={
                "plan-leads": ["REQ-1"],
                "plan-orphan": ["REQ-999"],
            },
            acceptance_status_by_requirement={
                "REQ-1": AcceptanceStatus.PARTIALLY_SATISFIED,
            },
        )

        self.assertEqual(matrix.source_of_truth_id, source.id)
        self.assertIn("REQ-2", matrix.missing_requirement_ids)
        self.assertIn("plan-orphan", matrix.unlinked_plan_item_ids)
        self.assertEqual(matrix.drift_risk, DriftRiskLevel.HIGH)
        req1 = next(item for item in matrix.items if item.requirement_id == "REQ-1")
        self.assertTrue(req1.covered)
        self.assertEqual(req1.acceptance_status, AcceptanceStatus.PARTIALLY_SATISFIED)

    def test_coverage_matrix_can_be_fully_covered(self):
        source = _base_source()
        matrix = build_requirement_coverage_matrix(
            source,
            plan_requirement_links={
                "plan-leads": ["REQ-1"],
                "plan-reminders": ["REQ-2"],
            },
        )

        self.assertEqual(matrix.missing_requirement_ids, [])
        self.assertEqual(matrix.unlinked_plan_item_ids, [])
        self.assertEqual(matrix.coverage_score, 1.0)
        self.assertEqual(matrix.drift_risk, DriftRiskLevel.LOW)

    def test_drift_risk_flags_unlinked_plan_step(self):
        source = _base_source()
        result = detect_drift_risk(
            source,
            plan_item_id="plan-random-feature",
            linked_requirement_ids=[],
            touched_paths=["frontend/src/pages/NewTask.tsx"],
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.drift_risk, DriftRiskLevel.HIGH)
        self.assertIn("no linked requirement", " ".join(result.errors))

    def test_drift_risk_flags_forbidden_area(self):
        source = _base_source()
        result = detect_drift_risk(
            source,
            plan_item_id="plan-storage-edit",
            linked_requirement_ids=["REQ-1"],
            touched_paths=["backend/src/storage/database.py"],
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.drift_risk, DriftRiskLevel.CRITICAL)
        self.assertIn("forbidden area", " ".join(result.errors))

    def test_drift_risk_passes_linked_safe_step(self):
        source = _base_source()
        result = detect_drift_risk(
            source,
            plan_item_id="plan-leads",
            linked_requirement_ids=["REQ-1"],
            touched_paths=["frontend/src/pages/Leads.tsx"],
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.drift_risk, DriftRiskLevel.LOW)

    def test_source_contract_module_has_no_db_tool_provider_usage(self):
        source = inspect.getsource(source_contract_module)

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

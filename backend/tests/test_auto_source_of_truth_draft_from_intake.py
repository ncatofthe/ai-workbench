"""
Auto Source of Truth Draft from Intake v1 — Test Suite

Tests the deterministic, preview-only SoT draft builder that converts a
CQE-answered intake into a structured SourceOfTruthUpsertRequest.

Coverage:
  - Model shapes and field defaults
  - Pure helper functions (_sot_draft_clean, _sot_draft_build_requirements,
    _sot_draft_validate, _sot_draft_source_for_mode)
  - Idea / Document / Existing-project mode end-to-end
  - Preview endpoint (POST /api/project-intake/source-of-truth-draft)
  - Confirm endpoint (POST /api/project-intake/source-of-truth-draft/confirm)
  - Secret rejection at every layer
  - Static analysis — forbidden patterns not present in the new section
  - Compatibility — all existing endpoints still pass

Safety invariants:
  - No project/run/tool_call created by preview endpoint
  - No DB write without explicit confirm_persist=True + project_id
  - No provider/LLM calls
  - No filesystem reads
  - Secret-like values rejected and not included in the draft
"""

import inspect
import re
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.orchestrator import project_intake as project_intake_module
from src.orchestrator.project_intake import (
    ClarifyingAnswer,
    ClarifyingAnswersRequest,
    SourceOfTruthDraftFromIntakeRequest,
    SourceOfTruthDraftFromIntakeResponse,
    SourceOfTruthDraftValidation,
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    _sot_draft_build_requirements,
    _sot_draft_clean,
    _sot_draft_clean_list,
    _sot_draft_source_for_mode,
    _sot_draft_validate,
    build_source_of_truth_draft_from_intake,
)
from src.models import SourceOfTruthUpsertRequest

from src.main import app

_client = TestClient(app)


# ── Shared fixtures ──────────────────────────────────────────────────────────


def _idea_intake(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(
        mode=UnifiedIntakeMode.IDEA,
        raw_input="Build a task manager for remote teams",
        title="Task Manager v1",
        **kw,
    )


def _doc_intake(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(
        mode=UnifiedIntakeMode.DOCUMENT,
        raw_input="Requirements document",
        document_excerpt="Must have: user auth, dashboard, notifications.",
        title="Doc Intake",
        **kw,
    )


def _ep_intake(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(
        mode=UnifiedIntakeMode.EXISTING_PROJECT,
        project_path="/home/user/my-app",
        known_stack=["FastAPI", "React"],
        raw_input="Improve the existing CRM",
        title="CRM Improvement",
        **kw,
    )


def _answers(*pairs) -> list[ClarifyingAnswer]:
    return [ClarifyingAnswer(question_id=qid, answer=ans, skipped=False)
            for qid, ans in pairs]


def _req(intake: UnifiedIntakeRequest, answers: list[ClarifyingAnswer] | None = None) -> SourceOfTruthDraftFromIntakeRequest:
    return SourceOfTruthDraftFromIntakeRequest(
        intake=ClarifyingAnswersRequest(
            intake=intake,
            answers=answers or [],
        )
    )


def _idea_draft_req(**kw) -> SourceOfTruthDraftFromIntakeRequest:
    return _req(_idea_intake(**kw))


def _idea_draft_req_with_answers(answers: list[ClarifyingAnswer]) -> SourceOfTruthDraftFromIntakeRequest:
    return _req(_idea_intake(), answers)


# ── Test 1: Model shapes ─────────────────────────────────────────────────────


class TestSoTDraftModels(unittest.TestCase):

    def test_request_has_intake_field(self):
        r = _idea_draft_req()
        self.assertIsInstance(r.intake, ClarifyingAnswersRequest)

    def test_request_project_id_defaults_to_none(self):
        r = _idea_draft_req()
        self.assertIsNone(r.project_id)

    def test_request_confirm_persist_defaults_to_false(self):
        r = _idea_draft_req()
        self.assertFalse(r.confirm_persist)

    def test_validation_model_has_required_fields(self):
        v = SourceOfTruthDraftValidation(valid=True)
        self.assertTrue(v.valid)
        self.assertEqual(v.drift_risk, "low")
        self.assertEqual(v.errors, [])
        self.assertEqual(v.warnings, [])
        self.assertEqual(v.fields_populated, 0)
        self.assertEqual(v.requirements_count, 0)

    def test_response_model_has_all_required_fields(self):
        result = build_source_of_truth_draft_from_intake(_idea_draft_req())
        self.assertIsInstance(result, SourceOfTruthDraftFromIntakeResponse)
        self.assertIsNotNone(result.mode)
        self.assertIsNotNone(result.source)
        self.assertIsNotNone(result.draft)
        self.assertIsNotNone(result.validation)
        self.assertIsInstance(result.persisted, bool)
        self.assertIsNotNone(result.confidence)
        self.assertIsNotNone(result.next_recommended_action)

    def test_response_draft_is_upsert_request(self):
        result = build_source_of_truth_draft_from_intake(_idea_draft_req())
        self.assertIsInstance(result.draft, SourceOfTruthUpsertRequest)

    def test_response_safety_notes_non_empty(self):
        result = build_source_of_truth_draft_from_intake(_idea_draft_req())
        self.assertGreater(len(result.safety_notes), 0)

    def test_response_limitations_non_empty(self):
        result = build_source_of_truth_draft_from_intake(_idea_draft_req())
        self.assertGreater(len(result.limitations), 0)


# ── Test 2: Pure helpers ─────────────────────────────────────────────────────


class TestSoTDraftHelpers(unittest.TestCase):

    def test_clean_truncates_long_text(self):
        text = "A long sentence " * 20   # 320 chars with spaces
        result = _sot_draft_clean(text, 100)
        self.assertLess(len(result), len(text))
        self.assertLessEqual(len(result), 104)  # truncated + "..." (3 chars)

    def test_clean_returns_empty_for_secret_value(self):
        self.assertEqual(_sot_draft_clean("api_key=mysecret123"), "")

    def test_clean_returns_empty_for_db_url_with_creds(self):
        self.assertEqual(_sot_draft_clean("postgres://user:pass@host/db"), "")

    def test_clean_returns_text_if_safe(self):
        self.assertEqual(_sot_draft_clean("Build a CRM"), "Build a CRM")

    def test_clean_list_filters_secrets(self):
        items = ["Safe goal", "password=hunter2", "Another safe goal"]
        result = _sot_draft_clean_list(items)
        self.assertEqual(len(result), 2)
        self.assertNotIn("password=hunter2", result)

    def test_clean_list_truncates_each_item(self):
        items = ["A long sentence " * 10, "B long sentence " * 10]
        result = _sot_draft_clean_list(items, max_per=50)
        for item in result:
            self.assertLessEqual(len(item), 54)  # truncated + "..." (3 chars)

    def test_clean_list_drops_empty_strings(self):
        items = ["", "   ", "valid item"]
        result = _sot_draft_clean_list(items)
        self.assertEqual(result, ["valid item"])

    def test_source_for_mode_idea(self):
        self.assertEqual(_sot_draft_source_for_mode("idea"), "intake_idea")

    def test_source_for_mode_document(self):
        self.assertEqual(_sot_draft_source_for_mode("document"), "intake_document")

    def test_source_for_mode_existing_project(self):
        self.assertEqual(_sot_draft_source_for_mode("existing_project"), "intake_existing_project")

    def test_source_for_mode_unknown_defaults_to_idea(self):
        self.assertEqual(_sot_draft_source_for_mode("unknown_mode"), "intake_idea")

    def test_build_requirements_stable_ids(self):
        goals = ["Goal one", "Goal two", "Goal three"]
        reqs = _sot_draft_build_requirements(goals)
        ids = [r.id for r in reqs]
        self.assertEqual(ids, ["REQ-001", "REQ-002", "REQ-003"])

    def test_build_requirements_first_three_are_must(self):
        goals = ["G1", "G2", "G3", "G4", "G5"]
        reqs = _sot_draft_build_requirements(goals)
        must_reqs = [r for r in reqs if r.priority == "must"]
        self.assertEqual(len(must_reqs), 3)

    def test_build_requirements_fourth_plus_are_should(self):
        goals = ["G1", "G2", "G3", "G4", "G5"]
        reqs = _sot_draft_build_requirements(goals)
        self.assertEqual(reqs[3].priority, "should")
        self.assertEqual(reqs[4].priority, "should")

    def test_build_requirements_skips_secret_goals(self):
        goals = ["Safe goal", "password=secret123", "Another safe"]
        reqs = _sot_draft_build_requirements(goals)
        titles = [r.title for r in reqs]
        self.assertNotIn("password=secret123", titles)
        self.assertEqual(len(reqs), 2)

    def test_build_requirements_capped_at_10(self):
        goals = [f"Goal {i}" for i in range(20)]
        reqs = _sot_draft_build_requirements(goals)
        self.assertLessEqual(len(reqs), 10)

    def test_validate_valid_draft(self):
        draft = SourceOfTruthUpsertRequest(
            product_summary="A task manager",
            target_users=["Remote teams"],
            goals=["Manage tasks", "Track progress"],
        )
        v = _sot_draft_validate(draft)
        self.assertTrue(v.valid)
        self.assertEqual(v.errors, [])

    def test_validate_missing_summary_and_intent_is_error(self):
        draft = SourceOfTruthUpsertRequest()
        v = _sot_draft_validate(draft)
        self.assertFalse(v.valid)
        self.assertTrue(any("product_summary" in e or "project_intent" in e for e in v.errors))

    def test_validate_empty_target_users_is_warning(self):
        draft = SourceOfTruthUpsertRequest(product_summary="A product")
        v = _sot_draft_validate(draft)
        self.assertTrue(any("target_users" in w for w in v.warnings))

    def test_validate_fields_populated_count(self):
        draft = SourceOfTruthUpsertRequest(
            product_summary="A product",
            target_users=["Users"],
            goals=["Goal"],
            constraints=["Budget"],
        )
        v = _sot_draft_validate(draft)
        self.assertGreaterEqual(v.fields_populated, 3)

    def test_validate_requirements_count(self):
        from src.models import ProjectSourceOfTruthRequirement
        draft = SourceOfTruthUpsertRequest(
            product_summary="A product",
            requirements=[
                ProjectSourceOfTruthRequirement(id="REQ-001", title="Auth", priority="must"),
                ProjectSourceOfTruthRequirement(id="REQ-002", title="Dashboard", priority="should"),
            ],
        )
        v = _sot_draft_validate(draft)
        self.assertEqual(v.requirements_count, 2)

    def test_validate_drift_risk_critical_when_errors(self):
        draft = SourceOfTruthUpsertRequest()
        v = _sot_draft_validate(draft)
        self.assertEqual(v.drift_risk, "critical")

    def test_validate_drift_risk_medium_when_warnings_only(self):
        draft = SourceOfTruthUpsertRequest(product_summary="A product")
        v = _sot_draft_validate(draft)
        # warnings (no target_users, no must-requirement) but no errors
        self.assertEqual(v.drift_risk, "medium")

    def test_validate_drift_risk_low_when_fully_populated(self):
        from src.models import ProjectSourceOfTruthRequirement
        draft = SourceOfTruthUpsertRequest(
            product_summary="A product",
            target_users=["Ops team"],
            goals=["Automate ops"],
            requirements=[
                ProjectSourceOfTruthRequirement(id="REQ-001", title="Core", priority="must"),
            ],
        )
        v = _sot_draft_validate(draft)
        self.assertEqual(v.drift_risk, "low")


# ── Test 3: Idea mode end-to-end ─────────────────────────────────────────────


class TestSoTDraftIdeaMode(unittest.TestCase):

    def setUp(self):
        self.result = build_source_of_truth_draft_from_intake(_idea_draft_req())

    def test_mode_is_idea(self):
        self.assertEqual(self.result.mode, "idea")

    def test_source_is_intake_idea(self):
        self.assertEqual(self.result.source, "intake_idea")

    def test_draft_status_is_draft(self):
        self.assertEqual(self.result.draft.status, "draft")

    def test_draft_status_never_active(self):
        self.assertNotEqual(self.result.draft.status, "active")

    def test_persisted_is_false(self):
        self.assertFalse(self.result.persisted)

    def test_project_id_is_none(self):
        self.assertIsNone(self.result.project_id)

    def test_version_is_none(self):
        self.assertIsNone(self.result.version)

    def test_confidence_is_low_without_answers(self):
        self.assertEqual(self.result.confidence, "low")

    def test_confidence_improves_with_enough_answers(self):
        answers = _answers(
            ("cq-idea-1", "A collaborative task manager"),
            ("cq-idea-2", "Remote teams"),
            ("cq-idea-3", "Web app"),
            ("cq-idea-4", "Desktop"),
            ("cq-idea-5", "50% adoption in 3 months"),
        )
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        self.assertEqual(result.confidence, "medium")

    def test_goals_from_intake_appear_in_draft(self):
        self.assertGreater(len(self.result.draft.goals), 0)

    def test_requirements_generated_from_goals(self):
        self.assertGreater(len(self.result.draft.requirements), 0)

    def test_requirements_have_stable_ids(self):
        ids = [r.id for r in self.result.draft.requirements]
        for i, rid in enumerate(ids):
            self.assertEqual(rid, f"REQ-{i + 1:03d}")

    def test_draft_source_is_intake_idea(self):
        self.assertEqual(self.result.draft.source, "intake_idea")

    def test_answer_for_target_users_updates_draft(self):
        answers = _answers(("cq-idea-2", "Freelancers and solo devs"))
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        self.assertTrue(any("freelancer" in u.lower() or "solo" in u.lower()
                            for u in result.draft.target_users))

    def test_answer_for_product_summary_updates_draft(self):
        answers = _answers(("cq-idea-1", "A focused Pomodoro productivity tool"))
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        summary = result.draft.product_summary.lower()
        self.assertTrue("pomodoro" in summary or "productivity" in summary or "focused" in summary)

    def test_deterministic_for_same_input(self):
        r1 = build_source_of_truth_draft_from_intake(_idea_draft_req())
        r2 = build_source_of_truth_draft_from_intake(_idea_draft_req())
        self.assertEqual(r1.draft.model_dump(), r2.draft.model_dump())
        self.assertEqual(r1.validation.model_dump(), r2.validation.model_dump())

    def test_product_summary_bounded_at_300_chars(self):
        self.assertLessEqual(len(self.result.draft.product_summary), 300)

    def test_goals_bounded_at_10(self):
        self.assertLessEqual(len(self.result.draft.goals), 10)

    def test_requirements_bounded_at_10(self):
        self.assertLessEqual(len(self.result.draft.requirements), 10)


# ── Test 4: Document mode ─────────────────────────────────────────────────────


class TestSoTDraftDocumentMode(unittest.TestCase):

    def setUp(self):
        self.result = build_source_of_truth_draft_from_intake(_req(_doc_intake()))

    def test_mode_is_document(self):
        self.assertEqual(self.result.mode, "document")

    def test_source_is_intake_document(self):
        self.assertEqual(self.result.source, "intake_document")

    def test_draft_source_is_intake_document(self):
        self.assertEqual(self.result.draft.source, "intake_document")

    def test_draft_status_is_draft(self):
        self.assertEqual(self.result.draft.status, "draft")

    def test_product_summary_not_raw_document_dump(self):
        # document_excerpt is "Must have: user auth, dashboard, notifications."
        # product_summary should be ≤ 300 chars, never a raw dump
        self.assertLessEqual(len(self.result.draft.product_summary), 300)

    def test_goals_non_empty(self):
        self.assertGreater(len(self.result.draft.goals), 0)

    def test_requirements_generated(self):
        self.assertGreater(len(self.result.draft.requirements), 0)

    def test_confidence_medium_with_enough_doc_answers(self):
        answers = _answers(
            ("cq-doc-1", "Final approved"),
            ("cq-doc-2", "User authentication, dashboards"),
            ("cq-doc-3", "All tests pass"),
            ("cq-doc-5", "React, FastAPI"),
        )
        result = build_source_of_truth_draft_from_intake(
            _req(_doc_intake(), answers)
        )
        self.assertEqual(result.confidence, "medium")


# ── Test 5: Existing project mode ─────────────────────────────────────────────


class TestSoTDraftExistingProjectMode(unittest.TestCase):

    def setUp(self):
        self.result = build_source_of_truth_draft_from_intake(_req(_ep_intake()))

    def test_mode_is_existing_project(self):
        self.assertEqual(self.result.mode, "existing_project")

    def test_source_is_intake_existing_project(self):
        self.assertEqual(self.result.source, "intake_existing_project")

    def test_draft_source_is_intake_existing_project(self):
        self.assertEqual(self.result.draft.source, "intake_existing_project")

    def test_project_path_not_used_as_filesystem(self):
        # project_path must only be used as a string hint — no filesystem call
        result = build_source_of_truth_draft_from_intake(_req(
            UnifiedIntakeRequest(
                mode=UnifiedIntakeMode.EXISTING_PROJECT,
                project_path="/nonexistent/path/that/cannot/be/read",
                raw_input="Improve my app",
            )
        ))
        self.assertIsNotNone(result)

    def test_ep_answers_add_constraints(self):
        answers = _answers(
            ("cq-ep-4", "pytest -q"),
            ("cq-ep-5", "auth module, payments"),
        )
        result = build_source_of_truth_draft_from_intake(_req(_ep_intake(), answers))
        constraints_text = " ".join(result.draft.constraints).lower()
        self.assertTrue(
            "pytest" in constraints_text or "auth" in constraints_text or "payment" in constraints_text
        )

    def test_ep_goals_refined_by_answers(self):
        answers = _answers(
            ("cq-ep-1", "Login works well"),
            ("cq-ep-2", "Dashboard crashes on load"),
            ("cq-ep-3", "Fix dashboard stability"),
        )
        result = build_source_of_truth_draft_from_intake(_req(_ep_intake(), answers))
        goals_text = " ".join(result.draft.goals).lower()
        self.assertTrue(
            "login" in goals_text or "dashboard" in goals_text or "fix" in goals_text
        )


# ── Test 6: Preview endpoint ──────────────────────────────────────────────────


class TestSoTDraftPreviewEndpoint(unittest.TestCase):

    def test_returns_200_idea_mode(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "idea", "raw_input": "Build a CRM"}, "answers": []}},
        )
        self.assertEqual(resp.status_code, 200)

    def test_returns_200_document_mode(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "document", "raw_input": "Requirements doc",
                                         "document_excerpt": "Must have: auth"}, "answers": []}},
        )
        self.assertEqual(resp.status_code, 200)

    def test_returns_200_existing_project_mode(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "existing_project",
                                         "project_path": "/home/user/proj",
                                         "raw_input": "Improve my project"}, "answers": []}},
        )
        self.assertEqual(resp.status_code, 200)

    def test_returns_422_for_invalid_mode(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "not_real", "raw_input": "x"}, "answers": []}},
        )
        self.assertIn(resp.status_code, (400, 422))

    def test_response_has_draft_field(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "idea", "raw_input": "A SaaS product"}, "answers": []}},
        )
        data = resp.json()
        self.assertIn("draft", data)
        self.assertIn("validation", data)

    def test_response_persisted_is_false(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "idea", "raw_input": "A SaaS product"}, "answers": []}},
        )
        data = resp.json()
        self.assertFalse(data["persisted"])

    def test_response_project_id_is_null(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "idea", "raw_input": "A SaaS product"}, "answers": []}},
        )
        data = resp.json()
        self.assertIsNone(data["project_id"])

    def test_response_version_is_null(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={"intake": {"intake": {"mode": "idea", "raw_input": "A SaaS product"}, "answers": []}},
        )
        data = resp.json()
        self.assertIsNone(data["version"])

    def test_preview_endpoint_creates_no_project(self):
        from src.storage import database
        with patch.object(database, "create_project",
                          side_effect=AssertionError("create_project called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft",
                json={"intake": {"intake": {"mode": "idea", "raw_input": "Build something"},
                                  "answers": []}},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_preview_endpoint_creates_no_run(self):
        from src.storage import database
        with patch.object(database, "create_run",
                          side_effect=AssertionError("create_run called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft",
                json={"intake": {"intake": {"mode": "idea", "raw_input": "Build something"},
                                  "answers": []}},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_preview_endpoint_creates_no_tool_call(self):
        from src.storage import database
        with patch.object(database, "create_tool_call",
                          side_effect=AssertionError("create_tool_call called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft",
                json={"intake": {"intake": {"mode": "idea", "raw_input": "Build something"},
                                  "answers": []}},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_preview_endpoint_does_not_write_sot_to_db(self):
        import src.api.routes as routes_module
        with patch.object(routes_module, "_upsert_sot",
                          side_effect=AssertionError("sot write called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft",
                json={"intake": {"intake": {"mode": "idea", "raw_input": "Build something"},
                                  "answers": []}},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_preview_ignores_confirm_persist_true(self):
        # Even when confirm_persist=True is sent to the PREVIEW endpoint, no write occurs
        import src.api.routes as routes_module
        with patch.object(routes_module, "_upsert_sot",
                          side_effect=AssertionError("sot write called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft",
                json={
                    "intake": {"intake": {"mode": "idea", "raw_input": "Build something"},
                                "answers": []},
                    "confirm_persist": True,
                    "project_id": "some-project-id",
                },
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_preview_endpoint_is_deterministic(self):
        payload = {
            "intake": {
                "intake": {"mode": "idea", "raw_input": "Build a CRM", "title": "CRM v1"},
                "answers": [{"question_id": "cq-idea-2", "answer": "Sales teams", "skipped": False}],
            }
        }
        r1 = _client.post("/api/project-intake/source-of-truth-draft", json=payload).json()
        r2 = _client.post("/api/project-intake/source-of-truth-draft", json=payload).json()
        self.assertEqual(r1["draft"], r2["draft"])
        self.assertEqual(r1["validation"], r2["validation"])


# ── Test 7: Confirm endpoint ──────────────────────────────────────────────────


class TestSoTDraftConfirmEndpoint(unittest.TestCase):

    _PREVIEW_PAYLOAD = {
        "intake": {
            "intake": {"mode": "idea", "raw_input": "Build a CRM", "title": "CRM v1"},
            "answers": [],
        },
        "confirm_persist": False,
    }

    def test_returns_200_without_confirm_persist(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft/confirm",
            json=self._PREVIEW_PAYLOAD,
        )
        self.assertEqual(resp.status_code, 200)

    def test_persisted_is_false_without_confirm_persist(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft/confirm",
            json=self._PREVIEW_PAYLOAD,
        )
        self.assertFalse(resp.json()["persisted"])

    def test_returns_400_when_confirm_persist_but_no_project_id(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft/confirm",
            json={
                "intake": {
                    "intake": {"mode": "idea", "raw_input": "Build a CRM"},
                    "answers": [],
                },
                "confirm_persist": True,
            },
        )
        self.assertEqual(resp.status_code, 400)

    def test_returns_404_when_project_id_not_found(self):
        import src.api.routes as routes_module
        with patch.object(routes_module, "get_project", return_value=None):
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft/confirm",
                json={
                    "intake": {
                        "intake": {"mode": "idea", "raw_input": "Build a CRM"},
                        "answers": [],
                    },
                    "confirm_persist": True,
                    "project_id": "nonexistent-project-id",
                },
            )
            self.assertEqual(resp.status_code, 404)

    def test_persists_when_confirm_persist_true_and_project_found(self):
        from src.models import ProjectSourceOfTruthDocument
        import src.api.routes as routes_module
        fake_project = MagicMock()
        fake_project.id = "proj-abc"
        stored_doc = ProjectSourceOfTruthDocument(
            id="doc-001",
            project_id="proj-abc",
            version=1,
            status="draft",
            product_name="CRM",
            product_summary="A CRM for sales",
            source="intake_idea",
        )
        with patch.object(routes_module, "get_project", return_value=fake_project), \
             patch.object(routes_module, "_upsert_sot", return_value=stored_doc) as mock_upsert:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft/confirm",
                json={
                    "intake": {
                        "intake": {"mode": "idea", "raw_input": "Build a CRM"},
                        "answers": [],
                    },
                    "confirm_persist": True,
                    "project_id": "proj-abc",
                },
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            self.assertTrue(data["persisted"])
            self.assertEqual(data["project_id"], "proj-abc")
            self.assertEqual(data["version"], 1)
            mock_upsert.assert_called_once()

    def test_confirm_endpoint_does_not_write_without_confirm_persist(self):
        import src.api.routes as routes_module
        with patch.object(routes_module, "_upsert_sot",
                          side_effect=AssertionError("write should not happen")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft/confirm",
                json={
                    "intake": {
                        "intake": {"mode": "idea", "raw_input": "Build a CRM"},
                        "answers": [],
                    },
                    "confirm_persist": False,
                    "project_id": "some-id",
                },
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_confirm_endpoint_does_not_create_project(self):
        from src.storage import database
        with patch.object(database, "create_project",
                          side_effect=AssertionError("create_project called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft/confirm",
                json={
                    "intake": {"intake": {"mode": "idea", "raw_input": "Build"}, "answers": []},
                    "confirm_persist": False,
                },
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_confirm_endpoint_does_not_create_run(self):
        from src.storage import database
        with patch.object(database, "create_run",
                          side_effect=AssertionError("create_run called")) as mock:
            resp = _client.post(
                "/api/project-intake/source-of-truth-draft/confirm",
                json={
                    "intake": {"intake": {"mode": "idea", "raw_input": "Build"}, "answers": []},
                    "confirm_persist": False,
                },
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()


# ── Test 8: Secret rejection ──────────────────────────────────────────────────


class TestSoTDraftSecretRejection(unittest.TestCase):

    def test_secret_in_goal_is_filtered_out(self):
        # Inject a goal that looks like an API key assignment
        answers = _answers(("cq-idea-5", "api_key=AAABBBCCC123 success criteria"))
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        goals_text = " ".join(result.draft.goals)
        self.assertNotIn("api_key=", goals_text)

    def test_secret_in_constraint_is_filtered_out(self):
        answers = _answers(("cq-idea-3", "password=s3cr3t build type"))
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        constraints_text = " ".join(result.draft.constraints)
        self.assertNotIn("password=s3cr3t", constraints_text)

    def test_db_url_with_creds_is_filtered(self):
        answers = _answers(("cq-idea-1", "postgres://user:pass@host/db system"))
        result = build_source_of_truth_draft_from_intake(_idea_draft_req_with_answers(answers))
        summary = result.draft.product_summary
        self.assertNotIn("postgres://user:pass", summary)

    def test_secret_in_requirement_title_triggers_filtering(self):
        # _sot_draft_build_requirements skips goals that are secret-like entirely
        goals = ["api_key=mysecret valid requirement"]
        reqs = _sot_draft_build_requirements(goals)
        # Secret-containing goal must be skipped — no requirement created
        self.assertEqual(len(reqs), 0)

    def test_draft_validation_detects_leaked_secret_in_goals(self):
        # Belt-and-suspenders: if a secret slips into the draft object, validation catches it
        # (note: _sot_draft_validate doesn't modify — it only reports errors)
        # We construct a draft with a secret manually to test the detector
        draft = SourceOfTruthUpsertRequest(
            product_summary="safe product",
            target_users=["users"],
        )
        # Force a secret into goals bypassing Pydantic (direct mutation of internal list)
        object.__setattr__(draft, "goals", ["api_key=MYSECRETKEY123"])
        v = _sot_draft_validate(draft)
        self.assertFalse(v.valid)
        self.assertTrue(any("goals" in e for e in v.errors))

    def test_preview_endpoint_does_not_return_secret_in_draft(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-draft",
            json={
                "intake": {
                    "intake": {
                        "mode": "idea",
                        "raw_input": "Build a system",
                        "title": "My project",
                    },
                    "answers": [
                        {"question_id": "cq-idea-5", "answer": "token=secret123",
                         "skipped": False},
                    ],
                }
            },
        )
        self.assertEqual(resp.status_code, 200)
        draft_text = str(resp.json().get("draft", {}))
        self.assertNotIn("token=secret123", draft_text)


# ── Test 9: Static analysis ───────────────────────────────────────────────────


class TestSoTDraftStaticAnalysis(unittest.TestCase):
    """Verify that the new SoT draft section contains no forbidden patterns."""

    @classmethod
    def setUpClass(cls):
        src = inspect.getsource(project_intake_module)
        # Extract only the Auto SoT Draft section
        marker = "# ── Auto Source of Truth Draft from Intake v1"
        idx = src.find(marker)
        cls._section = src[idx:] if idx >= 0 else ""

    def _assert_not_in_section(self, pattern: str):
        self.assertNotIn(pattern, self._section,
                         f"Forbidden pattern '{pattern}' found in SoT draft section")

    def test_no_execute_run(self):
        self._assert_not_in_section("execute_run")

    def test_no_asyncio_create_task(self):
        self._assert_not_in_section("asyncio.create_task")

    def test_no_subprocess(self):
        self._assert_not_in_section("subprocess.")

    def test_no_os_system(self):
        self._assert_not_in_section("os.system")

    def test_no_call_provider(self):
        self._assert_not_in_section("call_provider")

    def test_no_ollama_client(self):
        self._assert_not_in_section("ollama_client")

    def test_no_create_tool_call(self):
        self._assert_not_in_section("create_tool_call")

    def test_no_open_file(self):
        self._assert_not_in_section("open(")

    def test_no_read_text(self):
        self._assert_not_in_section(".read_text(")

    def test_no_os_listdir(self):
        self._assert_not_in_section("os.listdir")

    def test_no_pathlib_path(self):
        self._assert_not_in_section("pathlib.Path")

    def test_no_db_execute_direct(self):
        self._assert_not_in_section("db.execute")

    def test_no_save_run(self):
        self._assert_not_in_section("save_run")

    def test_no_apply_project_patch(self):
        self._assert_not_in_section("apply_project_patch")

    def test_section_exists(self):
        self.assertGreater(len(self._section), 200,
                           "SoT draft section not found or too short in project_intake.py")


# ── Test 10: Compatibility — existing endpoints unaffected ────────────────────


class TestSoTDraftCompatibility(unittest.TestCase):

    def test_unified_preview_still_works(self):
        resp = _client.post(
            "/api/project-intake/unified-preview",
            json={"mode": "idea", "raw_input": "Build a CRM"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("clarifying_questions", data)
        self.assertIn("source_of_truth_preview", data)

    def test_clarifying_questions_endpoint_still_works(self):
        resp = _client.post(
            "/api/project-intake/clarifying-questions",
            json={"mode": "idea", "raw_input": "Build a CRM"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("questions", resp.json())

    def test_clarifying_preview_endpoint_still_works(self):
        resp = _client.post(
            "/api/project-intake/clarifying-preview",
            json={"intake": {"mode": "idea", "raw_input": "Build a CRM"}, "answers": []},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("source_of_truth_preview", resp.json())

    def test_source_of_truth_preview_still_works(self):
        resp = _client.post(
            "/api/project-intake/source-of-truth-preview",
            json={"idea": "Build a CRM system", "mode": "new_project"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_brief_draft_endpoint_still_works(self):
        resp = _client.post(
            "/api/project-intake/brief-draft",
            json={"idea": "Build a CRM", "mode": "new_project"},
        )
        self.assertEqual(resp.status_code, 200)

    def test_intake_models_unchanged_field_shapes(self):
        # Confirm that SourceOfTruthUpsertRequest still has the expected fields
        from src.models import SourceOfTruthUpsertRequest as SUR
        expected = {
            "product_name", "product_summary", "project_intent",
            "target_users", "goals", "non_goals", "requirements",
            "constraints", "risks", "open_questions", "source", "status",
        }
        actual = set(SUR.model_fields.keys())
        self.assertTrue(expected.issubset(actual))


if __name__ == "__main__":
    unittest.main()

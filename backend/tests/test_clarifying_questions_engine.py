"""
Clarifying Questions Engine v1 — Test Suite

Tests the deterministic, preview-only clarifying questions and answer-refinement
pipeline. No DB writes, no project/run creation, no provider calls, no file reads.
"""

import inspect
import unittest

from fastapi.testclient import TestClient

from src.orchestrator import project_intake as project_intake_module
from src.orchestrator.project_intake import (
    ClarifiedIntakePreviewResponse,
    ClarifyingAnswer,
    ClarifyingAnswerGap,
    ClarifyingAnswersRequest,
    ClarifyingQuestionSet,
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    build_clarifying_question_set,
    refine_unified_intake_with_answers,
)

from src.main import app

_client = TestClient(app)


def _idea_req(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(mode=UnifiedIntakeMode.IDEA, raw_input="Build a CRM for sales teams", **kw)


def _doc_req(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(
        mode=UnifiedIntakeMode.DOCUMENT,
        raw_input="Requirements document",
        document_excerpt="Must have: user auth, dashboard, reporting.",
        **kw,
    )


def _ep_req(**kw) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(
        mode=UnifiedIntakeMode.EXISTING_PROJECT,
        project_path="/home/user/my-project",
        known_stack=["FastAPI", "React"],
        **kw,
    )


def _answer(qid: str, text: str, skipped: bool = False) -> ClarifyingAnswer:
    return ClarifyingAnswer(question_id=qid, answer=text, skipped=skipped)


# ── Question Set tests ─────────────────────────────────────────────────────────

class TestClarifyingQuestionSet(unittest.TestCase):

    def test_idea_question_set_returns_mode_idea(self):
        qs = build_clarifying_question_set(_idea_req())
        self.assertEqual(qs.mode, "idea")

    def test_document_question_set_returns_mode_document(self):
        qs = build_clarifying_question_set(_doc_req())
        self.assertEqual(qs.mode, "document")

    def test_existing_project_question_set_returns_mode_existing_project(self):
        qs = build_clarifying_question_set(_ep_req())
        self.assertEqual(qs.mode, "existing_project")

    def test_required_count_and_optional_count_are_correct(self):
        qs = build_clarifying_question_set(_idea_req())
        expected_required = sum(1 for q in qs.questions if q.required)
        expected_optional = sum(1 for q in qs.questions if not q.required)
        self.assertEqual(qs.required_count, expected_required)
        self.assertEqual(qs.optional_count, expected_optional)
        self.assertGreater(qs.required_count, 0)
        self.assertEqual(qs.required_count + qs.optional_count, len(qs.questions))

    def test_categories_are_present_and_bounded(self):
        qs = build_clarifying_question_set(_idea_req())
        self.assertIsInstance(qs.categories, list)
        self.assertGreater(len(qs.categories), 0)
        self.assertLessEqual(len(qs.categories), 12)  # bounded by max questions
        # All categories come from the questions
        question_categories = {q.category for q in qs.questions}
        for cat in qs.categories:
            self.assertIn(cat, question_categories)

    def test_question_set_is_deterministic_for_same_input(self):
        req = _idea_req(title="CRM for sales")
        qs1 = build_clarifying_question_set(req)
        qs2 = build_clarifying_question_set(req)
        self.assertEqual([q.id for q in qs1.questions], [q.id for q in qs2.questions])
        self.assertEqual(qs1.required_count, qs2.required_count)
        self.assertEqual(qs1.categories, qs2.categories)


# ── Answer handling ───────────────────────────────────────────────────────────

class TestAnswerHandling(unittest.TestCase):

    def test_answered_question_ids_are_returned(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-2", "Sales managers at SMBs")],
        )
        result = refine_unified_intake_with_answers(req)
        self.assertIn("cq-idea-2", result.answered_question_ids)

    def test_missing_required_answers_are_reported(self):
        # cq-idea-1 through cq-idea-5 are required; submit none
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        self.assertGreater(len(result.missing_required_questions), 0)
        gap_ids = [g.question_id for g in result.missing_required_questions]
        self.assertIn("cq-idea-1", gap_ids)

    def test_skipped_required_answer_creates_missing_warning(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-1", "", skipped=True)],
        )
        result = refine_unified_intake_with_answers(req)
        gap_ids = [g.question_id for g in result.missing_required_questions]
        self.assertIn("cq-idea-1", gap_ids)
        self.assertNotIn("cq-idea-1", result.answered_question_ids)

    def test_unknown_question_id_does_not_crash(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-totally-unknown-xyz", "some answer")],
        )
        try:
            result = refine_unified_intake_with_answers(req)
        except Exception as e:
            self.fail(f"Unknown question_id crashed: {e}")
        # Unknown id should NOT appear in answered_ids (not a real question)
        self.assertNotIn("cq-totally-unknown-xyz", result.answered_question_ids)

    def test_empty_answer_is_treated_as_missing(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-1", "   ")],  # whitespace-only
        )
        result = refine_unified_intake_with_answers(req)
        self.assertNotIn("cq-idea-1", result.answered_question_ids)
        gap_ids = [g.question_id for g in result.missing_required_questions]
        self.assertIn("cq-idea-1", gap_ids)

    def test_answer_summaries_are_capped(self):
        # Submit many answers to fill up summaries
        answers = [
            _answer("cq-idea-1", "Solve sales tracking"),
            _answer("cq-idea-2", "Sales managers"),
            _answer("cq-idea-3", "MVP"),
            _answer("cq-idea-4", "Web app"),
            _answer("cq-idea-5", "Leads converted"),
            _answer("cq-idea-7", "React, FastAPI"),
            _answer("cq-idea-8", "Yes, multi-tenant auth"),
            _answer("cq-idea-9", "PostgreSQL with row-level security"),
            _answer("cq-idea-10", "3 months, 2 developers"),
            _answer("cq-idea-12", "AWS EC2"),
        ]
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=answers)
        result = refine_unified_intake_with_answers(req)
        self.assertLessEqual(len(result.applied_answer_summary), 12)


# ── Idea mode refinement ──────────────────────────────────────────────────────

class TestIdeaRefinement(unittest.TestCase):

    def test_idea_answers_refine_target_users(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-2", "Sales managers at mid-size companies")],
        )
        result = refine_unified_intake_with_answers(req)
        sot = result.source_of_truth_preview
        # target_users should reflect the answer
        users_joined = " ".join(sot.target_users)
        self.assertIn("Sales managers", users_joined)

    def test_idea_answers_refine_goals(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-5", "500 leads converted per month")],
        )
        result = refine_unified_intake_with_answers(req)
        goals_joined = " ".join(result.source_of_truth_preview.goals)
        self.assertIn("500 leads", goals_joined)

    def test_idea_answers_improve_confidence_when_required_answered(self):
        # Answer all 5 required questions (cq-idea-1 through cq-idea-5)
        answers = [
            _answer("cq-idea-1", "Track sales leads and deals"),
            _answer("cq-idea-2", "Sales teams"),
            _answer("cq-idea-3", "MVP"),
            _answer("cq-idea-4", "Web application"),
            _answer("cq-idea-5", "50 deals closed in first month"),
        ]
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=answers)
        result = refine_unified_intake_with_answers(req)
        self.assertEqual(result.confidence_before, "low")
        self.assertEqual(result.confidence_after, "medium")
        self.assertEqual(len(result.missing_required_questions), 0)

    def test_idea_refinement_keeps_conceptual_module_map(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-4", "Web app")],
        )
        result = refine_unified_intake_with_answers(req)
        # Module map should remain conceptual (available, not a real repo scan)
        mm = result.module_map_preview
        self.assertIsInstance(mm.modules, list)
        self.assertIsInstance(mm.unknowns, list)

    def test_idea_stack_answer_refines_module_map_inferred_stack(self):
        req = ClarifyingAnswersRequest(
            intake=_idea_req(),
            answers=[_answer("cq-idea-7", "React, FastAPI, PostgreSQL")],
        )
        result = refine_unified_intake_with_answers(req)
        stack = result.module_map_preview.inferred_stack
        self.assertIn("React", stack)
        self.assertIn("FastAPI", stack)
        self.assertIn("PostgreSQL", stack)

    def test_idea_refinement_keeps_plan_bounded(self):
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        self.assertLessEqual(len(result.multi_agent_plan), 12)
        self.assertGreater(len(result.multi_agent_plan), 0)

    def test_idea_refinement_confidence_stays_low_with_no_answers(self):
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        self.assertEqual(result.confidence_before, "low")
        self.assertEqual(result.confidence_after, "low")


# ── Document mode refinement ──────────────────────────────────────────────────

class TestDocumentRefinement(unittest.TestCase):

    def test_document_answers_refine_requirements_scope(self):
        req = ClarifyingAnswersRequest(
            intake=_doc_req(),
            answers=[_answer("cq-doc-2", "User auth and reporting are must-have")],
        )
        result = refine_unified_intake_with_answers(req)
        goals_joined = " ".join(result.source_of_truth_preview.goals)
        self.assertIn("User auth and reporting", goals_joined)

    def test_document_refinement_does_not_dump_full_raw_document(self):
        long_doc = "x" * 5000
        req = ClarifyingAnswersRequest(
            intake=UnifiedIntakeRequest(
                mode=UnifiedIntakeMode.DOCUMENT,
                raw_input=long_doc,
                document_excerpt=long_doc,
            ),
            answers=[],
        )
        result = refine_unified_intake_with_answers(req)
        # product_summary must be capped
        self.assertLessEqual(len(result.source_of_truth_preview.product_summary), 400)

    def test_document_plan_includes_requirement_normalization(self):
        req = ClarifyingAnswersRequest(intake=_doc_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        roles = {step.agent_role for step in result.multi_agent_plan}
        # document plan must include business-analyst or product-manager normalization step
        self.assertTrue(
            any(r in roles for r in ("business-analyst", "product-manager")),
            f"Expected normalization role in {roles}",
        )

    def test_document_confidence_improves_with_required_answers(self):
        # Answer the 4 required doc questions
        answers = [
            _answer("cq-doc-1", "Complete requirements document"),
            _answer("cq-doc-2", "Auth, dashboard, reporting"),
            _answer("cq-doc-3", "All features pass acceptance tests"),
            _answer("cq-doc-4", "No ambiguities identified"),
        ]
        req = ClarifyingAnswersRequest(intake=_doc_req(), answers=answers)
        result = refine_unified_intake_with_answers(req)
        self.assertEqual(result.confidence_before, "low")
        self.assertEqual(result.confidence_after, "medium")

    def test_document_tech_stack_answer_refines_module_map(self):
        req = ClarifyingAnswersRequest(
            intake=_doc_req(),
            answers=[_answer("cq-doc-5", "Django; PostgreSQL")],
        )
        result = refine_unified_intake_with_answers(req)
        stack = result.module_map_preview.inferred_stack
        self.assertIn("Django", stack)
        self.assertIn("PostgreSQL", stack)


# ── Existing project mode refinement ──────────────────────────────────────────

class TestExistingProjectRefinement(unittest.TestCase):

    def test_ep_answers_refine_what_works_and_broken(self):
        req = ClarifyingAnswersRequest(
            intake=_ep_req(),
            answers=[
                _answer("cq-ep-1", "Auth and user management work"),
                _answer("cq-ep-2", "Reports are broken, export fails"),
            ],
        )
        result = refine_unified_intake_with_answers(req)
        goals_joined = " ".join(result.source_of_truth_preview.goals)
        self.assertIn("Auth", goals_joined)
        self.assertIn("Reports are broken", goals_joined)

    def test_ep_answers_can_influence_known_stack_module_hints(self):
        req = ClarifyingAnswersRequest(
            intake=_ep_req(),
            answers=[_answer("cq-ep-3", "Release v2 with export feature fixed")],
        )
        result = refine_unified_intake_with_answers(req)
        goals_joined = " ".join(result.source_of_truth_preview.goals)
        self.assertIn("export feature", goals_joined)

    def test_ep_still_does_not_read_files(self):
        # project_path is treated as string only; no filesystem access
        req = ClarifyingAnswersRequest(
            intake=UnifiedIntakeRequest(
                mode=UnifiedIntakeMode.EXISTING_PROJECT,
                project_path="/nonexistent/path/to/secret-project",
            ),
            answers=[],
        )
        try:
            result = refine_unified_intake_with_answers(req)
        except FileNotFoundError:
            self.fail("refine_unified_intake_with_answers tried to read the filesystem")
        except PermissionError:
            self.fail("refine_unified_intake_with_answers tried to access a real path")
        self.assertIsNotNone(result)

    def test_ep_plan_includes_repository_inventory_and_test_discovery(self):
        req = ClarifyingAnswersRequest(intake=_ep_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        titles = {step.title for step in result.multi_agent_plan}
        roles = {step.agent_role for step in result.multi_agent_plan}
        self.assertTrue(
            any("Inventory" in t or "inventory" in t.lower() for t in titles),
            f"Expected inventory step in {titles}",
        )
        self.assertIn("qa-expert", roles)

    def test_ep_protected_module_answer_appears_in_constraints(self):
        req = ClarifyingAnswersRequest(
            intake=_ep_req(),
            answers=[_answer("cq-ep-5", "Do not touch payments/ and auth/")],
        )
        result = refine_unified_intake_with_answers(req)
        constraints_joined = " ".join(result.source_of_truth_preview.constraints)
        self.assertIn("payments/", constraints_joined)

    def test_ep_test_command_answer_appears_in_constraints_and_removes_risk(self):
        req = ClarifyingAnswersRequest(
            intake=_ep_req(),
            answers=[_answer("cq-ep-4", "pytest -q tests/")],
        )
        result = refine_unified_intake_with_answers(req)
        constraints_joined = " ".join(result.source_of_truth_preview.constraints)
        self.assertIn("pytest", constraints_joined)
        # Risk "Test command not confirmed" should be removed
        risks_joined = " ".join(result.source_of_truth_preview.risks)
        self.assertNotIn("Test command not confirmed", risks_joined)

    def test_ep_target_goal_answer_appears_in_goals(self):
        req = ClarifyingAnswersRequest(
            intake=_ep_req(),
            answers=[_answer("cq-ep-3", "Ship export fix by end of sprint")],
        )
        result = refine_unified_intake_with_answers(req)
        goals_joined = " ".join(result.source_of_truth_preview.goals)
        self.assertIn("export fix", goals_joined)


# ── Endpoint tests ─────────────────────────────────────────────────────────────

class TestClarifyingQuestionsEndpoints(unittest.TestCase):

    def test_clarifying_questions_works_for_idea(self):
        resp = _client.post(
            "/api/project-intake/clarifying-questions",
            json={"mode": "idea", "raw_input": "Build a project management tool"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["mode"], "idea")
        self.assertGreater(len(data["questions"]), 0)
        self.assertGreater(data["required_count"], 0)

    def test_clarifying_questions_works_for_document(self):
        resp = _client.post(
            "/api/project-intake/clarifying-questions",
            json={"mode": "document", "document_excerpt": "Build an HR system."},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["mode"], "document")

    def test_clarifying_questions_works_for_existing_project(self):
        resp = _client.post(
            "/api/project-intake/clarifying-questions",
            json={"mode": "existing_project", "project_path": "/home/user/app"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["mode"], "existing_project")

    def test_clarifying_preview_works_with_answers(self):
        resp = _client.post(
            "/api/project-intake/clarifying-preview",
            json={
                "intake": {"mode": "idea", "raw_input": "Build a task tracker"},
                "answers": [
                    {"question_id": "cq-idea-2", "answer": "Freelance developers", "skipped": False},
                ],
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("cq-idea-2", data["answered_question_ids"])
        self.assertIn("source_of_truth_preview", data)
        self.assertIn("multi_agent_plan", data)
        self.assertIn("confidence_before", data)
        self.assertIn("confidence_after", data)

    def test_invalid_mode_returns_422(self):
        resp = _client.post(
            "/api/project-intake/clarifying-questions",
            json={"mode": "not_a_real_mode", "raw_input": "something"},
        )
        self.assertIn(resp.status_code, (422, 400))

    def test_clarifying_questions_endpoint_creates_no_project(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_project", side_effect=AssertionError("create_project called")) as mock:
            resp = _client.post(
                "/api/project-intake/clarifying-questions",
                json={"mode": "idea", "raw_input": "Build something"},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_clarifying_questions_endpoint_creates_no_run(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_run", side_effect=AssertionError("create_run called")) as mock:
            resp = _client.post(
                "/api/project-intake/clarifying-questions",
                json={"mode": "idea", "raw_input": "Build something"},
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_clarifying_preview_endpoint_creates_no_tool_calls(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_tool_call", side_effect=AssertionError("create_tool_call called")) as mock:
            resp = _client.post(
                "/api/project-intake/clarifying-preview",
                json={
                    "intake": {"mode": "idea", "raw_input": "Build something"},
                    "answers": [],
                },
            )
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_clarifying_preview_is_deterministic_for_same_input(self):
        payload = {
            "intake": {"mode": "idea", "raw_input": "Build a CRM", "title": "CRM v1"},
            "answers": [{"question_id": "cq-idea-2", "answer": "Sales teams", "skipped": False}],
        }
        r1 = _client.post("/api/project-intake/clarifying-preview", json=payload).json()
        r2 = _client.post("/api/project-intake/clarifying-preview", json=payload).json()
        self.assertEqual(r1["mode"], r2["mode"])
        self.assertEqual(r1["confidence_after"], r2["confidence_after"])
        self.assertEqual(r1["answered_question_ids"], r2["answered_question_ids"])


# ── Compatibility tests ───────────────────────────────────────────────────────

class TestCompatibility(unittest.TestCase):

    def test_existing_unified_preview_still_works(self):
        """unified-preview endpoint must not be broken by CQE additions."""
        resp = _client.post(
            "/api/project-intake/unified-preview",
            json={"mode": "idea", "raw_input": "Build an app"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("clarifying_questions", data)
        self.assertIn("source_of_truth_preview", data)

    def test_clarifying_answer_model_defaults(self):
        a = ClarifyingAnswer(question_id="q1")
        self.assertEqual(a.answer, "")
        self.assertFalse(a.skipped)

    def test_clarifying_question_set_has_expected_fields(self):
        qs = build_clarifying_question_set(_idea_req())
        self.assertIsInstance(qs.mode, str)
        self.assertIsInstance(qs.questions, list)
        self.assertIsInstance(qs.required_count, int)
        self.assertIsInstance(qs.optional_count, int)
        self.assertIsInstance(qs.categories, list)
        self.assertIsInstance(qs.next_recommended_action, str)

    def test_clarified_response_has_all_required_fields(self):
        req = ClarifyingAnswersRequest(intake=_idea_req(), answers=[])
        result = refine_unified_intake_with_answers(req)
        self.assertIsInstance(result.mode, str)
        self.assertIsInstance(result.answered_question_ids, list)
        self.assertIsInstance(result.missing_required_questions, list)
        self.assertIsInstance(result.applied_answer_summary, list)
        self.assertIsInstance(result.confidence_before, str)
        self.assertIsInstance(result.confidence_after, str)
        self.assertIsInstance(result.next_recommended_action, str)
        self.assertIsInstance(result.safety_notes, list)
        self.assertIsInstance(result.limitations, list)


# ── Safety / static analysis ──────────────────────────────────────────────────


def _get_cqe_source() -> str:
    """Source of the Clarifying Questions Engine v1 section in project_intake.py."""
    full = inspect.getsource(project_intake_module)
    marker = "# ── Clarifying Questions Engine v1"
    idx = full.find(marker)
    return full[idx:] if idx >= 0 else ""


class TestCQESafetyAndStaticAnalysis(unittest.TestCase):

    def test_no_execute_run_in_cqe(self):
        self.assertNotIn("execute_run", _get_cqe_source())

    def test_no_asyncio_create_task_in_cqe(self):
        self.assertNotIn("asyncio.create_task", _get_cqe_source())

    def test_no_subprocess_or_os_command_in_cqe(self):
        source = _get_cqe_source()
        self.assertNotIn("subprocess.", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("os.popen", source)

    def test_no_provider_calls_in_cqe(self):
        source = _get_cqe_source()
        self.assertNotIn("call_provider", source)
        self.assertNotIn("ollama_client", source)
        self.assertNotIn("anthropic.Anthropic", source)

    def test_no_file_content_reads_in_cqe(self):
        source = _get_cqe_source()
        self.assertNotIn("open(", source)
        self.assertNotIn(".read_text(", source)
        self.assertNotIn("pathlib.Path", source)
        self.assertNotIn("os.listdir", source)
        self.assertNotIn(".scandir(", source)

    def test_no_database_writes_in_cqe(self):
        source = _get_cqe_source()
        self.assertNotIn("save_project", source)
        self.assertNotIn("save_run", source)
        self.assertNotIn("save_tool_call", source)
        self.assertNotIn("db.execute", source)

    def test_no_create_tool_call_in_cqe(self):
        self.assertNotIn("create_tool_call", _get_cqe_source())

    def test_routes_clarifying_endpoints_have_no_runtime_execution(self):
        import src.api.routes as routes_module
        source = inspect.getsource(routes_module)

        # Check /clarifying-questions endpoint
        start = source.find("post_project_intake_clarifying_questions")
        end = source.find("\n\n\n", start)
        section = source[start:end] if end > start else source[start:start + 600]
        self.assertNotIn("execute_run", section)
        self.assertNotIn("asyncio.create_task", section)

        # Check /clarifying-preview endpoint
        start = source.find("post_project_intake_clarifying_preview")
        end = source.find("\n\n\n", start)
        section = source[start:end] if end > start else source[start:start + 600]
        self.assertNotIn("execute_run", section)
        self.assertNotIn("asyncio.create_task", section)


if __name__ == "__main__":
    unittest.main()

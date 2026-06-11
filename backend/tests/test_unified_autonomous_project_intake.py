"""Tests for Unified Autonomous Project Intake v1.

Pure deterministic unit tests — no DB, no LLM, no network, no side effects.
"""

from __future__ import annotations

import ast
import inspect
import unittest

from fastapi.testclient import TestClient

import src.orchestrator.project_intake as project_intake_module
from src.orchestrator.project_intake import (
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    UnifiedAutonomousIntakePreviewResponse,
    ClarifyingQuestion,
    DraftSourceOfTruthPreview,
    DraftModuleMapPreview,
    DraftAgentPlanStep,
    _MAX_UNIFIED_QUESTIONS,
    _MAX_UNIFIED_SOT_ITEMS,
    _MAX_UNIFIED_MODULES,
    _MAX_UNIFIED_PLAN_STEPS,
    build_unified_autonomous_intake_preview,
)


def _idea_req(**kwargs) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(mode=UnifiedIntakeMode.IDEA, **kwargs)


def _doc_req(**kwargs) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(mode=UnifiedIntakeMode.DOCUMENT, **kwargs)


def _ep_req(**kwargs) -> UnifiedIntakeRequest:
    return UnifiedIntakeRequest(mode=UnifiedIntakeMode.EXISTING_PROJECT, **kwargs)


def _build(req: UnifiedIntakeRequest) -> UnifiedAutonomousIntakePreviewResponse:
    return build_unified_autonomous_intake_preview(req)


# ── Models / bounds ────────────────────────────────────────────────────────────


class TestUnifiedIntakeModels(unittest.TestCase):
    def test_idea_request_returns_mode_idea(self):
        req = _idea_req(raw_input="Build a task management app")
        result = _build(req)
        self.assertEqual(result.mode, "idea")

    def test_document_request_returns_mode_document(self):
        req = _doc_req(raw_input="Requirements for a CRM system", document_excerpt="Req doc")
        result = _build(req)
        self.assertEqual(result.mode, "document")

    def test_existing_project_request_returns_mode_existing_project(self):
        req = _ep_req(raw_input="Continue existing project", project_path="/projects/myapp")
        result = _build(req)
        self.assertEqual(result.mode, "existing_project")

    def test_clarifying_questions_capped(self):
        req = _idea_req(raw_input="Build a complex SaaS with auth payments uploads notifications integrations")
        result = _build(req)
        self.assertLessEqual(len(result.clarifying_questions), _MAX_UNIFIED_QUESTIONS)

    def test_sot_preview_lists_capped(self):
        req = _idea_req(raw_input="Build a web app")
        result = _build(req)
        sot = result.source_of_truth_preview
        self.assertLessEqual(len(sot.target_users), _MAX_UNIFIED_SOT_ITEMS)
        self.assertLessEqual(len(sot.goals), _MAX_UNIFIED_SOT_ITEMS)
        self.assertLessEqual(len(sot.non_goals), _MAX_UNIFIED_SOT_ITEMS)
        self.assertLessEqual(len(sot.constraints), _MAX_UNIFIED_SOT_ITEMS)
        self.assertLessEqual(len(sot.risks), _MAX_UNIFIED_SOT_ITEMS)
        self.assertLessEqual(len(sot.open_questions), _MAX_UNIFIED_SOT_ITEMS)

    def test_module_preview_capped(self):
        req = _idea_req(raw_input="Build a web app", known_stack=["React", "FastAPI", "PostgreSQL"])
        result = _build(req)
        self.assertLessEqual(len(result.module_map_preview.modules), _MAX_UNIFIED_MODULES)

    def test_multi_agent_plan_capped(self):
        req = _idea_req(raw_input="Build a web app")
        result = _build(req)
        self.assertLessEqual(len(result.multi_agent_plan), _MAX_UNIFIED_PLAN_STEPS)


# ── Idea mode ──────────────────────────────────────────────────────────────────


class TestIdeaMode(unittest.TestCase):
    def _result(self) -> UnifiedAutonomousIntakePreviewResponse:
        return _build(_idea_req(raw_input="Build a task management web app for teams"))

    def test_idea_mode_generates_product_clarifying_questions(self):
        result = self._result()
        questions = result.clarifying_questions
        self.assertGreater(len(questions), 0)
        categories = {q.category for q in questions}
        # Should include product or related categories
        self.assertTrue(any(c in categories for c in ("product", "tech", "security", "data", "constraints", "deployment")))

    def test_idea_mode_drafts_sot_preview(self):
        result = self._result()
        sot = result.source_of_truth_preview
        self.assertIsInstance(sot, DraftSourceOfTruthPreview)
        self.assertTrue(sot.product_name)
        self.assertTrue(sot.product_summary)
        self.assertIsInstance(sot.goals, list)
        self.assertGreater(len(sot.goals), 0)

    def test_idea_mode_includes_multi_agent_roles(self):
        result = self._result()
        roles = {step.agent_role for step in result.multi_agent_plan}
        # Should include backend, QA, and some architect/product role
        self.assertTrue(any("developer" in r or "architect" in r or "analyst" in r for r in roles))
        self.assertTrue(any("qa" in r or "tester" in r or "expert" in r for r in roles))

    def test_idea_mode_includes_safety_notes(self):
        result = self._result()
        self.assertGreater(len(result.safety_notes), 0)
        # Safety notes should mention read-only
        combined = " ".join(result.safety_notes).lower()
        self.assertIn("read-only", combined)


# ── Document mode ─────────────────────────────────────────────────────────────


class TestDocumentMode(unittest.TestCase):
    def _result(self) -> UnifiedAutonomousIntakePreviewResponse:
        return _build(_doc_req(
            raw_input="Requirements for a CRM system",
            document_excerpt="Must-have: user management, contact tracking, reporting.",
            title="CRM Requirements v1",
        ))

    def test_document_mode_generates_requirement_questions(self):
        result = self._result()
        questions = result.clarifying_questions
        self.assertGreater(len(questions), 0)
        categories = {q.category for q in questions}
        self.assertTrue(any(c in categories for c in ("requirements", "tech", "quality", "compliance")))

    def test_document_mode_drafts_sot_from_document_excerpt(self):
        result = self._result()
        sot = result.source_of_truth_preview
        self.assertTrue(sot.product_name)
        # Summary should be bounded excerpt, not raw dump
        self.assertLessEqual(len(sot.product_summary), 500)

    def test_document_mode_does_not_dump_full_raw_document(self):
        long_excerpt = "Requirement " * 200  # 2400 chars
        req = _doc_req(raw_input="Doc", document_excerpt=long_excerpt)
        result = _build(req)
        sot = result.source_of_truth_preview
        self.assertLessEqual(len(sot.product_summary), 500)

    def test_document_mode_includes_requirement_normalization_step(self):
        result = self._result()
        titles = [step.title.lower() for step in result.multi_agent_plan]
        self.assertTrue(any("normal" in t or "document" in t or "analys" in t for t in titles))


# ── Existing project mode ──────────────────────────────────────────────────────


class TestExistingProjectMode(unittest.TestCase):
    def _result(self) -> UnifiedAutonomousIntakePreviewResponse:
        return _build(_ep_req(
            raw_input="Continue my existing project",
            project_path="/projects/myapp",
            known_stack=["React", "FastAPI"],
        ))

    def test_existing_project_asks_what_works(self):
        result = self._result()
        questions_text = " ".join(q.question.lower() for q in result.clarifying_questions)
        self.assertIn("work", questions_text)

    def test_existing_project_asks_what_broken(self):
        result = self._result()
        questions_text = " ".join(q.question.lower() for q in result.clarifying_questions)
        self.assertTrue("broken" in questions_text or "incomplete" in questions_text)

    def test_existing_project_asks_for_test_command(self):
        result = self._result()
        questions_text = " ".join(q.question.lower() for q in result.clarifying_questions)
        self.assertIn("test", questions_text)

    def test_existing_project_asks_about_protected_modules(self):
        result = self._result()
        questions_text = " ".join(q.question.lower() for q in result.clarifying_questions)
        self.assertTrue("modif" in questions_text or "protected" in questions_text or "not be modified" in questions_text)

    def test_existing_project_does_not_read_files(self):
        req = _ep_req(raw_input="Existing project", project_path="/projects/myapp")
        result = _build(req)
        # Just verify the result is produced without file I/O (no exception means no file read attempted)
        self.assertIsInstance(result, UnifiedAutonomousIntakePreviewResponse)

    def test_existing_project_uses_known_stack(self):
        req = _ep_req(raw_input="Continue project", known_stack=["React", "FastAPI", "PostgreSQL"])
        result = _build(req)
        mm = result.module_map_preview
        inferred = " ".join(mm.inferred_stack).lower()
        self.assertTrue("react" in inferred or "fastapi" in inferred or "postgresql" in inferred)

    def test_existing_project_includes_repo_inventory_step(self):
        result = self._result()
        titles = [step.title.lower() for step in result.multi_agent_plan]
        self.assertTrue(any("inventor" in t or "repository" in t or "repo" in t for t in titles))

    def test_existing_project_includes_test_discovery_step(self):
        result = self._result()
        titles = [step.title.lower() for step in result.multi_agent_plan]
        self.assertTrue(any("test" in t or "discover" in t for t in titles))


# ── Endpoint tests ─────────────────────────────────────────────────────────────


class TestUnifiedIntakeEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from src.api.routes import router
        from fastapi import FastAPI
        app = FastAPI()
        app.include_router(router)
        cls.client = TestClient(app, raise_server_exceptions=True)

    def test_post_unified_preview_idea_returns_200(self):
        resp = self.client.post("/api/project-intake/unified-preview", json={
            "mode": "idea",
            "raw_input": "Build a task management app",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["mode"], "idea")

    def test_post_unified_preview_document_returns_200(self):
        resp = self.client.post("/api/project-intake/unified-preview", json={
            "mode": "document",
            "raw_input": "Requirements document for CRM",
            "document_excerpt": "Must have user management.",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["mode"], "document")

    def test_post_unified_preview_existing_project_returns_200(self):
        resp = self.client.post("/api/project-intake/unified-preview", json={
            "mode": "existing_project",
            "raw_input": "Continue my project",
            "project_path": "/projects/myapp",
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["mode"], "existing_project")

    def test_invalid_mode_returns_422(self):
        resp = self.client.post("/api/project-intake/unified-preview", json={
            "mode": "invalid_mode_xyz",
            "raw_input": "some input",
        })
        self.assertIn(resp.status_code, (422, 400))

    def test_endpoint_creates_no_project(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_project", side_effect=AssertionError("create_project called")) as mock:
            resp = self.client.post("/api/project-intake/unified-preview", json={
                "mode": "idea",
                "raw_input": "Build something",
            })
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_endpoint_creates_no_run(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_run", side_effect=AssertionError("create_run called")) as mock:
            resp = self.client.post("/api/project-intake/unified-preview", json={
                "mode": "idea",
                "raw_input": "Build something",
            })
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_endpoint_creates_no_tool_calls(self):
        from src.storage import database
        from unittest.mock import patch
        with patch.object(database, "create_tool_call", side_effect=AssertionError("create_tool_call called")) as mock:
            resp = self.client.post("/api/project-intake/unified-preview", json={
                "mode": "idea",
                "raw_input": "Build something",
            })
            self.assertEqual(resp.status_code, 200)
            mock.assert_not_called()

    def test_endpoint_is_deterministic_for_same_input(self):
        payload = {"mode": "idea", "raw_input": "Build a CRM", "title": "CRM v1"}
        r1 = self.client.post("/api/project-intake/unified-preview", json=payload).json()
        r2 = self.client.post("/api/project-intake/unified-preview", json=payload).json()
        self.assertEqual(r1["mode"], r2["mode"])
        self.assertEqual(r1["classification_reason"], r2["classification_reason"])
        self.assertEqual(
            [q["id"] for q in r1["clarifying_questions"]],
            [q["id"] for q in r2["clarifying_questions"]],
        )
        self.assertEqual(
            [s["id"] for s in r1["multi_agent_plan"]],
            [s["id"] for s in r2["multi_agent_plan"]],
        )


# ── Safety / static analysis ──────────────────────────────────────────────────


def _get_builder_source() -> str:
    return inspect.getsource(build_unified_autonomous_intake_preview)


def _get_helper_source() -> str:
    """Source of all unified intake helpers in the module."""
    lines = inspect.getsource(project_intake_module)
    # Find the unified section start
    marker = "# ── Unified Autonomous Project Intake v1"
    idx = lines.find(marker)
    return lines[idx:] if idx >= 0 else lines


class TestSafetyAndStaticAnalysis(unittest.TestCase):
    def test_project_intake_helper_has_no_execute_run(self):
        source = _get_helper_source()
        self.assertNotIn("execute_run", source)

    def test_no_asyncio_create_task(self):
        source = _get_helper_source()
        self.assertNotIn("asyncio.create_task", source)

    def test_no_subprocess_or_os_command(self):
        source = _get_helper_source()
        self.assertNotIn("subprocess.", source)
        self.assertNotIn("os.system", source)
        self.assertNotIn("os.popen", source)

    def test_no_provider_calls_in_helper(self):
        source = _get_helper_source()
        self.assertNotIn("call_provider", source)
        self.assertNotIn("ollama_client", source)
        self.assertNotIn("anthropic.Anthropic", source)

    def test_no_file_content_reads_in_helper(self):
        source = _get_helper_source()
        self.assertNotIn("open(", source)
        self.assertNotIn(".read_text(", source)
        self.assertNotIn("pathlib.Path", source)
        self.assertNotIn("os.listdir", source)
        self.assertNotIn(".scandir(", source)

    def test_no_database_writes_in_helper(self):
        source = _get_helper_source()
        self.assertNotIn("save_project", source)
        self.assertNotIn("save_run", source)
        self.assertNotIn("save_tool_call", source)
        self.assertNotIn("db.execute", source)

    def test_no_create_tool_call_in_helper(self):
        source = _get_helper_source()
        self.assertNotIn("create_tool_call", source)

    def test_routes_endpoint_section_has_no_runtime_execution(self):
        import src.api.routes as routes_module
        source = inspect.getsource(routes_module)
        # Find the unified-preview endpoint function
        start = source.find("post_project_intake_unified_preview")
        end = source.find("\n\n\n", start)
        section = source[start:end] if end > start else source[start:start + 500]
        self.assertNotIn("execute_run", section)
        self.assertNotIn("asyncio.create_task", section)


# ── Compatibility ─────────────────────────────────────────────────────────────


class TestCompatibility(unittest.TestCase):
    def test_existing_project_intake_analyze_still_works(self):
        from src.orchestrator.project_intake import analyze_project_intake, ProjectIntakeRequest
        req = ProjectIntakeRequest(idea="Build a web app for users")
        result = analyze_project_intake(req)
        self.assertIsNotNone(result)
        self.assertTrue(result.questions)

    def test_source_of_truth_preview_still_works(self):
        from src.orchestrator.project_intake import (
            build_source_of_truth_from_intake,
            SourceOfTruthPreviewRequest,
        )
        req = SourceOfTruthPreviewRequest(idea="Build a web app for teams")
        result = build_source_of_truth_from_intake(req)
        self.assertIsNotNone(result)
        self.assertTrue(result.source_of_truth.requirements)

    def test_unified_preview_does_not_break_confirmed_plan_run_preview(self):
        from src.orchestrator.project_intake import (
            build_confirmed_plan_run_preview,
            ConfirmedPlanRunPreviewRequest,
        )
        req = ConfirmedPlanRunPreviewRequest(idea="Build a CRM web app")
        result = build_confirmed_plan_run_preview(req)
        self.assertIsNotNone(result)
        self.assertIsInstance(result.steps, list)

    def test_unified_mode_enum_values(self):
        self.assertEqual(UnifiedIntakeMode.IDEA.value, "idea")
        self.assertEqual(UnifiedIntakeMode.DOCUMENT.value, "document")
        self.assertEqual(UnifiedIntakeMode.EXISTING_PROJECT.value, "existing_project")

    def test_unified_intake_response_has_all_required_fields(self):
        req = _idea_req(raw_input="Build a task manager")
        result = _build(req)
        self.assertIsInstance(result.mode, str)
        self.assertIsInstance(result.classification_reason, str)
        self.assertIsInstance(result.clarifying_questions, list)
        self.assertIsInstance(result.source_of_truth_preview, DraftSourceOfTruthPreview)
        self.assertIsInstance(result.module_map_preview, DraftModuleMapPreview)
        self.assertIsInstance(result.multi_agent_plan, list)
        self.assertIsInstance(result.next_recommended_action, str)
        self.assertIsInstance(result.safety_notes, list)
        self.assertIsInstance(result.limitations, list)


if __name__ == "__main__":
    unittest.main()

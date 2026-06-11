"""Multi-Agent Plan from Intake v1 tests.

The plan builder is deterministic and preview-only. It must not persist state,
create projects/runs/run steps/tool_calls, read files, execute commands, or call
providers.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from src.orchestrator import project_intake as intake_module
from src.orchestrator.project_intake import (
    ClarifyingAnswer,
    MultiAgentPlanFromIntakeRequest,
    MultiAgentPlanFromIntakeResponse,
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    build_multi_agent_plan_from_intake,
)
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "multi-agent-plan.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


def _answers(*pairs: tuple[str, str]) -> list[ClarifyingAnswer]:
    return [ClarifyingAnswer(question_id=qid, answer=answer, skipped=False) for qid, answer in pairs]


def _idea(**kw) -> UnifiedIntakeRequest:
    data = {
        "mode": UnifiedIntakeMode.IDEA,
        "title": "SaaS Task Manager",
        "raw_input": "Build a web SaaS task manager with auth, dashboard, reports, file uploads, database, and QA tests.",
        "known_stack": ["React", "FastAPI", "PostgreSQL"],
    }
    data.update(kw)
    return UnifiedIntakeRequest(**data)


def _document(**kw) -> UnifiedIntakeRequest:
    data = {
        "mode": UnifiedIntakeMode.DOCUMENT,
        "title": "Service Desk TZ",
        "raw_input": "Requirements document for service desk platform",
        "document_excerpt": (
            "Must support tickets, SLA rules, notifications, role based access, reports dashboard, "
            "acceptance criteria, ambiguous integrations, and regression tests. " * 18
        ),
        "known_stack": ["React", "FastAPI"],
    }
    data.update(kw)
    return UnifiedIntakeRequest(**data)


def _existing(**kw) -> UnifiedIntakeRequest:
    data = {
        "mode": UnifiedIntakeMode.EXISTING_PROJECT,
        "title": "Existing Helpdesk",
        "raw_input": "Continue existing service desk app with tickets, SLA, notifications, reports dashboard, and first safe patch.",
        "project_path": "/Users/example/helpdesk",
        "known_stack": ["React", "FastAPI", "SQLite"],
    }
    data.update(kw)
    return UnifiedIntakeRequest(**data)


def _sot() -> dict:
    return {
        "product_name": "Service Desk",
        "requirements": [
            {"id": "REQ-001", "title": "Users can create tickets", "description": "ticket workflow", "tags": ["tickets"]},
            {"id": "REQ-002", "title": "SLA escalation", "description": "priority deadline escalation", "tags": ["sla"]},
            {"id": "REQ-003", "title": "Auth roles", "description": "role based access", "tags": ["auth"]},
            {"id": "REQ-004", "title": "Reports dashboard", "description": "analytics reporting", "tags": ["reports"]},
        ],
    }


def _module_map() -> dict:
    return {
        "modules": [
            {
                "id": "mod_frontend_ui",
                "name": "Frontend UI",
                "slug": "frontend_ui",
                "module_type": "frontend",
                "related_requirements": ["REQ-004"],
                "test_hints": ["npx tsc --noEmit", "npm run build"],
                "risks": ["UI state must remain clear"],
            },
            {
                "id": "mod_backend_api",
                "name": "Backend API",
                "slug": "backend_api",
                "module_type": "backend",
                "related_requirements": ["REQ-001"],
                "test_hints": ["pytest"],
                "risks": ["API contracts affect workflows"],
            },
            {
                "id": "mod_database_schema",
                "name": "Database / Schema",
                "slug": "database_schema",
                "module_type": "database",
                "related_requirements": ["REQ-001"],
                "test_hints": ["storage tests"],
                "risks": ["Schema changes require backup review"],
            },
            {
                "id": "mod_auth_access",
                "name": "Auth / Access",
                "slug": "auth_access",
                "module_type": "shared",
                "related_requirements": ["REQ-003"],
                "test_hints": ["auth guard tests"],
                "risks": ["Auth changes are sensitive"],
            },
        ],
        "source": "intake_idea",
        "status": "draft",
    }


def _req(
    intake: UnifiedIntakeRequest,
    answers: list[ClarifyingAnswer] | None = None,
    *,
    sot: dict | None = None,
    module_map: dict | None = None,
) -> MultiAgentPlanFromIntakeRequest:
    return MultiAgentPlanFromIntakeRequest(
        intake=intake,
        answers=answers or [],
        source_of_truth_draft=sot,
        module_map_draft=module_map,
    )


class TestModelAndBounds:
    def test_idea_request_creates_multi_agent_plan(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert isinstance(result, MultiAgentPlanFromIntakeResponse)
        assert result.tasks

    def test_document_request_creates_multi_agent_plan(self):
        result = build_multi_agent_plan_from_intake(_req(_document(), sot=_sot(), module_map=_module_map()))
        assert result.mode == "document"
        assert result.tasks

    def test_existing_project_request_creates_multi_agent_plan(self):
        result = build_multi_agent_plan_from_intake(_req(_existing(), sot=_sot(), module_map=_module_map()))
        assert result.mode == "existing_project"
        assert result.tasks

    def test_generated_task_ids_are_stable(self):
        first = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        second = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert [t.id for t in first.tasks] == [t.id for t in second.tasks]

    def test_output_is_deterministic_for_same_input(self):
        first = build_multi_agent_plan_from_intake(_req(_document(), sot=_sot(), module_map=_module_map()))
        second = build_multi_agent_plan_from_intake(_req(_document(), sot=_sot(), module_map=_module_map()))
        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_task_count_is_bounded(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert len(result.tasks) <= 16

    def test_milestones_are_bounded(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert len(result.milestones) <= 6

    def test_risks_are_bounded(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert len(result.risks) <= 12


class TestIdeaMode:
    def test_idea_plan_includes_product_analyst(self):
        roles = {t.agent_role for t in build_multi_agent_plan_from_intake(_req(_idea())).tasks}
        assert "product_analyst" in roles

    def test_idea_plan_includes_architect(self):
        roles = {t.agent_role for t in build_multi_agent_plan_from_intake(_req(_idea())).tasks}
        assert "architect" in roles

    def test_idea_plan_includes_backend_frontend_database_qa_roles_where_appropriate(self):
        roles = {t.agent_role for t in build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map())).tasks}
        assert {"backend_agent", "frontend_agent", "database_agent", "qa_agent"} <= roles

    def test_idea_plan_includes_delivery_reviewer(self):
        roles = {t.agent_role for t in build_multi_agent_plan_from_intake(_req(_idea())).tasks}
        assert "delivery_reviewer_agent" in roles

    def test_idea_plan_recommends_sot_confirmation_when_missing(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), module_map=_module_map()))
        assert "source_of_truth_draft" in result.validation.missing_inputs
        assert "confirm" in result.recommended_first_action.lower() or "answer" in result.recommended_first_action.lower()


class TestDocumentMode:
    def test_document_plan_includes_requirement_normalization(self):
        titles = [t.title.lower() for t in build_multi_agent_plan_from_intake(_req(_document())).tasks]
        assert any("requirement" in title and "normal" in title for title in titles)

    def test_document_plan_includes_acceptance_criteria_validation(self):
        steps = " ".join(" ".join(t.validation_steps).lower() for t in build_multi_agent_plan_from_intake(_req(_document())).tasks)
        assert "acceptance" in steps

    def test_document_plan_does_not_dump_full_raw_document(self):
        doc = _document()
        result = build_multi_agent_plan_from_intake(_req(doc, sot=_sot(), module_map=_module_map()))
        dumped = str(result.model_dump(mode="json"))
        assert doc.document_excerpt not in dumped

    def test_document_ambiguity_creates_risks_or_warnings(self):
        result = build_multi_agent_plan_from_intake(_req(_document(known_stack=[])))
        combined = " ".join([r.description for r in result.risks] + result.validation.warnings).lower()
        assert "document" in combined or "conceptual" in combined or "ambiguous" in combined


class TestExistingProjectMode:
    def test_existing_project_plan_includes_repository_inventory_task(self):
        titles = [t.title.lower() for t in build_multi_agent_plan_from_intake(_req(_existing())).tasks]
        assert any("inventory" in title for title in titles)

    def test_existing_project_plan_includes_test_discovery_task(self):
        titles = [t.title.lower() for t in build_multi_agent_plan_from_intake(_req(_existing())).tasks]
        assert any("test discovery" in title for title in titles)

    def test_existing_project_plan_includes_first_safe_patch_candidate(self):
        titles = [t.title.lower() for t in build_multi_agent_plan_from_intake(_req(_existing())).tasks]
        assert any("first safe patch" in title for title in titles)

    def test_existing_project_uses_known_stack_for_task_targeting(self):
        result = build_multi_agent_plan_from_intake(_req(_existing(), sot=_sot(), module_map=_module_map()))
        assert any(t.agent_role == "frontend_agent" for t in result.tasks)
        assert any(t.agent_role == "backend_agent" for t in result.tasks)

    def test_existing_project_project_path_is_string_hint_only(self):
        intake = _existing(project_path="/absolute/project/path")
        result = build_multi_agent_plan_from_intake(_req(intake, sot=_sot(), module_map=_module_map()))
        dumped = str(result.model_dump(mode="json"))
        assert "/absolute/project/path" not in dumped

    def test_existing_project_does_not_read_files(self):
        source = inspect.getsource(build_multi_agent_plan_from_intake)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_protected_modules_create_manual_approval_marker(self):
        result = build_multi_agent_plan_from_intake(_req(
            _existing(),
            _answers(("cq-ep-5", "Do not touch billing or legacy auth without review")),
            sot=_sot(),
            module_map=_module_map(),
        ))
        assert any(t.manual_approval_required for t in result.tasks)
        assert any("sensitive" in r.id for r in result.risks)


class TestLinkage:
    def test_sot_requirement_ids_attach_to_tasks(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert any("REQ-001" in t.requirement_ids or "REQ-003" in t.requirement_ids for t in result.tasks)

    def test_module_map_modules_attach_to_tasks(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert any("frontend_ui" in t.target_modules or "backend_api" in t.target_modules for t in result.tasks)

    def test_missing_sot_draft_still_works_with_warning(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), module_map=_module_map()))
        assert result.tasks
        assert "source_of_truth_draft" in result.validation.missing_inputs

    def test_missing_module_map_draft_still_works_with_warning(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot()))
        assert result.tasks
        assert "module_map_draft" in result.validation.missing_inputs

    def test_invalid_empty_drafts_do_not_crash(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot={"requirements": "bad"}, module_map={"modules": "bad"}))
        assert result.tasks
        assert result.validation.warnings


class TestSafetyPolicy:
    def test_secret_like_content_is_invalid(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(raw_input="Build app with api_key=secret123")))
        assert not result.validation.valid
        assert any("secret" in error.lower() for error in result.validation.errors)

    def test_provider_allowed_defaults_false(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert all(not t.provider_allowed for t in result.tasks)

    def test_task_links_are_bounded(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        for task in result.tasks:
            assert len(task.target_modules) <= 8
            assert len(task.requirement_ids) <= 8
            assert len(task.expected_outputs) <= 8
            assert len(task.validation_steps) <= 8

    def test_risky_auth_database_deployment_tasks_require_manual_approval(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(raw_input="Build auth database deployment flow"), sot=_sot(), module_map=_module_map()))
        sensitive = [t for t in result.tasks if t.risk_level == "high"]
        assert sensitive
        assert all(t.manual_approval_required for t in sensitive)

    def test_validation_steps_are_present(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert all(t.validation_steps for t in result.tasks)

    def test_recommended_first_action_is_present(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert result.recommended_first_action

    def test_no_task_implies_actual_execution(self):
        result = build_multi_agent_plan_from_intake(_req(_idea(), sot=_sot(), module_map=_module_map()))
        text = " ".join(t.description for t in result.tasks).lower()
        assert "executing agents" not in text
        assert "apply patch now" not in text


class TestEndpoint:
    def test_post_multi_agent_plan_rejects_empty_input(self, client):
        res = client.post("/api/project-intake/multi-agent-plan", json={
            "intake": {"mode": "idea", "title": "", "raw_input": ""},
            "answers": [],
        })
        assert res.status_code == 400

    def test_post_multi_agent_plan_returns_200_for_idea(self, client):
        res = client.post("/api/project-intake/multi-agent-plan", json=_req(_idea()).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "idea"

    def test_post_multi_agent_plan_returns_200_for_document(self, client):
        res = client.post("/api/project-intake/multi-agent-plan", json=_req(_document()).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "document"

    def test_post_multi_agent_plan_returns_200_for_existing_project(self, client):
        res = client.post("/api/project-intake/multi-agent-plan", json=_req(_existing()).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "existing_project"

    def test_endpoint_creates_no_project(self, client, isolated_db):
        before = len(isolated_db.list_projects())
        client.post("/api/project-intake/multi-agent-plan", json=_req(_idea()).model_dump(mode="json"))
        assert len(isolated_db.list_projects()) == before

    def test_endpoint_creates_no_run(self, client, isolated_db):
        before = len(isolated_db.list_runs())
        client.post("/api/project-intake/multi-agent-plan", json=_req(_idea()).model_dump(mode="json"))
        assert len(isolated_db.list_runs()) == before

    def test_endpoint_creates_no_run_steps(self, client, isolated_db):
        before = isolated_db._connect().execute("SELECT COUNT(*) FROM run_steps").fetchone()[0]
        client.post("/api/project-intake/multi-agent-plan", json=_req(_idea()).model_dump(mode="json"))
        after = isolated_db._connect().execute("SELECT COUNT(*) FROM run_steps").fetchone()[0]
        assert after == before

    def test_endpoint_creates_no_tool_calls(self, client, isolated_db):
        before = isolated_db._connect().execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        client.post("/api/project-intake/multi-agent-plan", json=_req(_idea()).model_dump(mode="json"))
        after = isolated_db._connect().execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        assert after == before

    def test_endpoint_is_deterministic(self, client):
        payload = _req(_idea(), sot=_sot(), module_map=_module_map()).model_dump(mode="json")
        first = client.post("/api/project-intake/multi-agent-plan", json=payload).json()
        second = client.post("/api/project-intake/multi-agent-plan", json=payload).json()
        assert first == second


class TestCompatibilityImports:
    def test_auto_module_map_builder_still_imports(self):
        assert hasattr(intake_module, "build_module_map_draft_from_intake")

    def test_auto_sot_builder_still_imports(self):
        assert hasattr(intake_module, "build_source_of_truth_draft_from_intake")

    def test_clarifying_builder_still_imports(self):
        assert hasattr(intake_module, "refine_unified_intake_with_answers")

    def test_unified_intake_builder_still_imports(self):
        assert hasattr(intake_module, "build_unified_autonomous_intake_preview")


class TestStaticSafety:
    def test_no_execute_run(self):
        assert "execute_run" not in inspect.getsource(build_multi_agent_plan_from_intake)

    def test_no_asyncio_create_task(self):
        assert "asyncio.create_task" not in inspect.getsource(build_multi_agent_plan_from_intake)

    def test_no_subprocess_or_os_command(self):
        source = inspect.getsource(build_multi_agent_plan_from_intake)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_no_provider_calls(self):
        source = inspect.getsource(build_multi_agent_plan_from_intake)
        assert "ollama.chat_completion" not in source
        assert "claude_provider" not in source
        assert "codex" not in source

    def test_no_file_content_reads(self):
        source = inspect.getsource(build_multi_agent_plan_from_intake)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_no_create_tool_call(self):
        assert "create_tool_call" not in inspect.getsource(build_multi_agent_plan_from_intake)

    def test_no_create_project_or_run(self):
        source = inspect.getsource(build_multi_agent_plan_from_intake)
        assert "create_project" not in source
        assert "create_run" not in source

    def test_no_run_step_creation(self):
        assert "create_run_step" not in inspect.getsource(build_multi_agent_plan_from_intake)

    def test_endpoint_has_no_db_write_call(self):
        from src.api import routes
        source = inspect.getsource(routes.post_project_intake_multi_agent_plan)
        assert "_upsert" not in source
        assert "create_" not in source

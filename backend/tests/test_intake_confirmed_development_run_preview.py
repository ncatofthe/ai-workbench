"""Intake to Confirmed Development Run Preview v1 tests.

The preview builder is deterministic and read-only. It must not persist state,
start agents, call providers, scan repositories, read files, or execute
commands.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from src.orchestrator import project_intake as intake_module
from src.orchestrator.project_intake import (
    ClarifyingAnswer,
    IntakeDevelopmentRunPreviewRequest,
    IntakeDevelopmentRunPreviewResponse,
    MultiAgentPlanFromIntakeRequest,
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    build_intake_development_run_preview,
    build_multi_agent_plan_from_intake,
)
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "development-run-preview.db"))
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
        "raw_input": "Build a SaaS task manager with auth, dashboard, reports, database, frontend, backend, and QA tests.",
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


def _plan(intake: UnifiedIntakeRequest | None = None) -> dict:
    req = MultiAgentPlanFromIntakeRequest(
        intake=intake or _idea(),
        answers=_answers(("cq-ep-4", "pytest"), ("cq-ep-5", "auth and database are protected")),
        source_of_truth_draft=_sot(),
        module_map_draft=_module_map(),
    )
    return build_multi_agent_plan_from_intake(req).model_dump(mode="json")


def _req(
    intake: UnifiedIntakeRequest,
    answers: list[ClarifyingAnswer] | None = None,
    *,
    sot: dict | None = None,
    module_map: dict | None = None,
    plan: dict | None = None,
    preferred_mode: str = "guided",
) -> IntakeDevelopmentRunPreviewRequest:
    return IntakeDevelopmentRunPreviewRequest(
        intake=intake,
        answers=answers or [],
        source_of_truth_draft=sot,
        module_map_draft=module_map,
        multi_agent_plan=plan,
        preferred_mode=preferred_mode,
    )


class TestModelAndBounds:
    def test_idea_request_creates_development_run_preview(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert isinstance(result, IntakeDevelopmentRunPreviewResponse)
        assert result.preview_only is True
        assert result.steps

    def test_document_request_creates_development_run_preview(self):
        result = build_intake_development_run_preview(_req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document())))
        assert result.mode == "document"
        assert result.steps

    def test_existing_project_request_creates_development_run_preview(self):
        result = build_intake_development_run_preview(_req(_existing(), _answers(("cq-ep-4", "pytest"), ("cq-ep-5", "auth")), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert result.mode == "existing_project"
        assert result.steps

    def test_generated_step_ids_are_stable(self):
        req = _req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan())
        first = build_intake_development_run_preview(req)
        second = build_intake_development_run_preview(req)
        assert [s.id for s in first.steps] == [s.id for s in second.steps]

    def test_output_is_deterministic_for_same_input(self):
        req = _req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document()))
        first = build_intake_development_run_preview(req)
        second = build_intake_development_run_preview(req)
        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_steps_are_bounded(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert len(result.steps) <= 20

    def test_agent_roles_are_bounded(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert len(result.agent_roles) <= 12

    def test_requirement_and_module_links_are_bounded(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert len(result.requirement_ids) <= 20
        assert len(result.module_ids) <= 20


class TestIdeaMode:
    def test_idea_preview_includes_context_confirmation_step(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert result.steps[0].id == "step-context-confirmation"

    def test_idea_preview_includes_architecture_backend_frontend_qa_delivery_steps(self):
        titles = " ".join(step.title.lower() for step in build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan())).steps)
        assert "architecture" in titles
        assert "backend" in titles
        assert "frontend" in titles
        assert "qa" in titles or "verification" in titles
        assert "delivery" in titles

    def test_idea_preview_does_not_create_project(self, client, isolated_db):
        before = len(isolated_db.list_projects())
        client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        assert len(isolated_db.list_projects()) == before

    def test_idea_preview_recommends_sot_confirmation_when_needed(self):
        result = build_intake_development_run_preview(_req(_idea(), module_map=_module_map(), plan=_plan()))
        assert "Source of Truth" in result.recommended_first_safe_action


class TestDocumentMode:
    def test_document_preview_includes_requirement_normalization(self):
        titles = [step.title.lower() for step in build_intake_development_run_preview(_req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document()))).steps]
        assert any("requirement" in title and "normal" in title for title in titles)

    def test_document_preview_includes_acceptance_criteria_validation(self):
        result = build_intake_development_run_preview(_req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document())))
        text = " ".join(step.title + " " + " ".join(step.validation_steps) for step in result.steps).lower()
        assert "acceptance" in text

    def test_document_preview_does_not_dump_full_raw_document(self):
        result = build_intake_development_run_preview(_req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document())))
        rendered = " ".join([result.run_goal] + [step.description for step in result.steps])
        assert len(rendered) < len(_document().document_excerpt)

    def test_document_ambiguity_creates_warnings(self):
        result = build_intake_development_run_preview(_req(_document(), plan=_plan(_document())))
        assert result.validation.warnings


class TestExistingProjectMode:
    def test_existing_project_preview_includes_repo_inventory_future_task(self):
        result = build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert any("inventory" in step.title.lower() for step in result.steps)

    def test_existing_project_preview_includes_test_discovery_future_task(self):
        result = build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert any("test discovery" in step.title.lower() for step in result.steps)

    def test_existing_project_preview_includes_protected_modules_review(self):
        result = build_intake_development_run_preview(_req(_existing(), _answers(("cq-ep-5", "auth and database are protected")), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert any("protected" in step.title.lower() or step.manual_approval_required for step in result.steps)

    def test_existing_project_preview_includes_first_safe_patch_candidate(self):
        result = build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert any("safe patch" in step.title.lower() for step in result.steps)

    def test_existing_project_project_path_is_string_hint_only(self):
        result = build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())))
        assert result.steps
        assert "/Users/example/helpdesk" not in " ".join(step.description for step in result.steps)

    def test_existing_project_does_not_read_files(self):
        assert "open(" not in inspect.getsource(build_intake_development_run_preview)
        assert ".read_text(" not in inspect.getsource(build_intake_development_run_preview)
        assert ".read(" not in inspect.getsource(build_intake_development_run_preview)

    def test_existing_project_does_not_execute_commands(self):
        source = inspect.getsource(build_intake_development_run_preview)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source


class TestLinkage:
    def test_sot_requirement_ids_attach_to_steps(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert "REQ-001" in result.requirement_ids

    def test_module_map_modules_attach_to_steps(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert "backend_api" in result.module_ids

    def test_multi_agent_plan_tasks_convert_to_steps(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert any(step.id == "step-architecture-alignment" for step in result.steps)

    def test_missing_sot_draft_still_works_with_warning(self):
        result = build_intake_development_run_preview(_req(_idea(), module_map=_module_map(), plan=_plan()))
        assert result.steps
        assert "source_of_truth_draft" in result.validation.missing_inputs

    def test_missing_module_map_draft_still_works_with_warning(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), plan=_plan()))
        assert result.steps
        assert "module_map_draft" in result.validation.missing_inputs

    def test_missing_multi_agent_plan_uses_conservative_fallback(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map()))
        assert result.steps
        assert "multi_agent_plan" in result.validation.missing_inputs

    def test_invalid_empty_drafts_do_not_crash(self):
        result = build_intake_development_run_preview(_req(_idea(), sot={}, module_map={}, plan={}))
        assert result.steps
        assert result.validation.errors or result.validation.warnings


class TestSafetyPolicy:
    def test_provider_allowed_defaults_false(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert all(step.provider_allowed is False for step in result.steps)

    def test_risky_auth_database_deployment_provider_tasks_require_manual_approval(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        risky = [step for step in result.steps if any(term in " ".join([step.title, step.description, " ".join(step.module_ids)]).lower() for term in ["auth", "database", "deployment", "provider"])]
        assert risky
        assert all(step.manual_approval_required for step in risky)

    def test_safety_gates_are_present(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert all(step.safety_gates for step in result.steps)

    def test_recommended_first_safe_action_is_present(self):
        result = build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()))
        assert result.recommended_first_safe_action

    def test_no_step_implies_actual_execution(self):
        text = " ".join(step.description for step in build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan())).steps).lower()
        assert "has changed" not in text
        assert "executed" not in text

    def test_no_step_implies_patch_applied(self):
        text = " ".join(step.title + " " + step.description for step in build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing()))).steps).lower()
        assert "patch applied" not in text

    def test_no_step_implies_tests_were_run(self):
        text = " ".join(step.title + " " + step.description for step in build_intake_development_run_preview(_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing()))).steps).lower()
        assert "tests were run" not in text

    def test_no_step_implies_provider_call_happened(self):
        text = " ".join(step.title + " " + step.description for step in build_intake_development_run_preview(_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan())).steps).lower()
        assert "provider call happened" not in text


class TestEndpoint:
    def test_post_development_run_preview_rejects_empty_input(self, client):
        res = client.post("/api/project-intake/development-run-preview", json={
            "intake": {"mode": "idea", "title": "", "raw_input": ""},
            "answers": [],
        })
        assert res.status_code == 400

    def test_post_development_run_preview_returns_200_for_idea(self, client):
        res = client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "idea"

    def test_post_development_run_preview_returns_200_for_document(self, client):
        res = client.post("/api/project-intake/development-run-preview", json=_req(_document(), sot=_sot(), module_map=_module_map(), plan=_plan(_document())).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "document"

    def test_post_development_run_preview_returns_200_for_existing_project(self, client):
        res = client.post("/api/project-intake/development-run-preview", json=_req(_existing(), sot=_sot(), module_map=_module_map(), plan=_plan(_existing())).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["mode"] == "existing_project"

    def test_endpoint_creates_no_project(self, client, isolated_db):
        before = len(isolated_db.list_projects())
        client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        assert len(isolated_db.list_projects()) == before

    def test_endpoint_creates_no_run(self, client, isolated_db):
        before = len(isolated_db.list_runs())
        client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        assert len(isolated_db.list_runs()) == before

    def test_endpoint_creates_no_run_steps(self, client, isolated_db):
        before = isolated_db._connect().execute("SELECT COUNT(*) FROM run_steps").fetchone()[0]
        client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        after = isolated_db._connect().execute("SELECT COUNT(*) FROM run_steps").fetchone()[0]
        assert after == before

    def test_endpoint_creates_no_tool_calls(self, client, isolated_db):
        before = isolated_db._connect().execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        client.post("/api/project-intake/development-run-preview", json=_req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json"))
        after = isolated_db._connect().execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
        assert after == before

    def test_endpoint_is_deterministic(self, client):
        payload = _req(_idea(), sot=_sot(), module_map=_module_map(), plan=_plan()).model_dump(mode="json")
        first = client.post("/api/project-intake/development-run-preview", json=payload).json()
        second = client.post("/api/project-intake/development-run-preview", json=payload).json()
        assert first == second


class TestCompatibilityImports:
    def test_multi_agent_plan_builder_still_imports(self):
        assert hasattr(intake_module, "build_multi_agent_plan_from_intake")

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
        assert "execute_run" not in inspect.getsource(build_intake_development_run_preview)

    def test_no_asyncio_create_task(self):
        assert "asyncio.create_task" not in inspect.getsource(build_intake_development_run_preview)

    def test_no_subprocess_or_os_command(self):
        source = inspect.getsource(build_intake_development_run_preview)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_no_provider_calls(self):
        source = inspect.getsource(build_intake_development_run_preview)
        assert "ollama.chat_completion" not in source
        assert "claude_provider" not in source
        assert "codex" not in source

    def test_no_file_content_reads(self):
        source = inspect.getsource(build_intake_development_run_preview)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_no_create_tool_call(self):
        assert "create_tool_call" not in inspect.getsource(build_intake_development_run_preview)

    def test_no_create_project_or_run(self):
        source = inspect.getsource(build_intake_development_run_preview)
        assert "create_project" not in source
        assert "create_run(" not in source

    def test_no_run_step_creation(self):
        assert "create_run_step" not in inspect.getsource(build_intake_development_run_preview)

    def test_endpoint_has_no_db_write_call(self):
        from src.api import routes
        source = inspect.getsource(routes.post_project_intake_development_run_preview)
        assert "_upsert" not in source
        assert "create_" not in source

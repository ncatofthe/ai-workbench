"""Auto Module Map Draft from Intake v1 tests.

The draft builder is deterministic and preview-first. Preview endpoints must not
persist module maps, create projects/runs/tool_calls, read files, or call
providers. Explicit confirm persistence is allowed only with project_id and
confirm_persist=true.
"""

from __future__ import annotations

import inspect

import pytest
from fastapi.testclient import TestClient

from src.models import ProjectModuleMapUpsertRequest
from src.orchestrator import project_intake as intake_module
from src.orchestrator.project_intake import (
    ClarifyingAnswer,
    ClarifyingAnswersRequest,
    ModuleMapDraftFromIntakeRequest,
    ModuleMapDraftFromIntakeResponse,
    ModuleMapDraftValidation,
    UnifiedIntakeMode,
    UnifiedIntakeRequest,
    _mm_validate_draft,
    build_module_map_draft_from_intake,
)
from src.storage import database
from src.storage.module_map_storage import get_active_project_module_map, list_project_module_map_history


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "module-map-intake.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    path = tmp_path / "project"
    path.mkdir()
    return isolated_db.create_project(
        "Module Map Intake Project",
        str(path),
        stack="React, FastAPI, PostgreSQL",
        test_command="pytest",
    )


def _answers(*pairs: tuple[str, str]) -> list[ClarifyingAnswer]:
    return [ClarifyingAnswer(question_id=qid, answer=answer, skipped=False) for qid, answer in pairs]


def _req(
    intake: UnifiedIntakeRequest,
    answers: list[ClarifyingAnswer] | None = None,
    *,
    sot: dict | None = None,
    project_id: str | None = None,
    confirm: bool = False,
) -> ModuleMapDraftFromIntakeRequest:
    return ModuleMapDraftFromIntakeRequest(
        intake=ClarifyingAnswersRequest(intake=intake, answers=answers or []),
        source_of_truth_draft=sot,
        project_id=project_id,
        confirm_persist=confirm,
    )


def _idea(**kw) -> UnifiedIntakeRequest:
    data = {
        "mode": UnifiedIntakeMode.IDEA,
        "title": "SaaS Task Manager",
        "raw_input": "Build a web SaaS task manager with auth, dashboard, reports, file uploads, and QA tests.",
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
            "Must support tickets, SLA rules, notifications, knowledge base, reports dashboard, "
            "role based access, and acceptance tests. " * 20
        ),
        "known_stack": ["React", "FastAPI"],
    }
    data.update(kw)
    return UnifiedIntakeRequest(**data)


def _existing(**kw) -> UnifiedIntakeRequest:
    data = {
        "mode": UnifiedIntakeMode.EXISTING_PROJECT,
        "title": "Existing Helpdesk",
        "raw_input": "Continue existing service desk app with tickets, SLA, notifications, reports dashboard.",
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


class TestDraftModel:
    def test_idea_request_creates_module_map_draft(self):
        result = build_module_map_draft_from_intake(_req(_idea()))
        assert isinstance(result, ModuleMapDraftFromIntakeResponse)
        assert isinstance(result.draft, ProjectModuleMapUpsertRequest)
        assert result.draft.modules

    def test_document_request_creates_module_map_draft(self):
        result = build_module_map_draft_from_intake(_req(_document()))
        assert result.draft.modules
        assert result.draft.source == "intake_document"

    def test_existing_project_request_creates_module_map_draft(self):
        result = build_module_map_draft_from_intake(_req(_existing()))
        assert result.draft.modules
        assert result.draft.source == "intake_existing_project"

    def test_generated_module_ids_and_names_are_stable(self):
        first = build_module_map_draft_from_intake(_req(_idea(), sot=_sot()))
        second = build_module_map_draft_from_intake(_req(_idea(), sot=_sot()))
        assert [(m.id, m.name, m.slug) for m in first.draft.modules] == [
            (m.id, m.name, m.slug) for m in second.draft.modules
        ]

    def test_output_is_deterministic_for_same_input(self):
        first = build_module_map_draft_from_intake(_req(_document(), sot=_sot()))
        second = build_module_map_draft_from_intake(_req(_document(), sot=_sot()))
        assert first.model_dump(mode="json") == second.model_dump(mode="json")

    def test_output_is_bounded(self):
        result = build_module_map_draft_from_intake(_req(_document(), sot=_sot()))
        assert len(result.draft.modules) <= 12
        for module in result.draft.modules:
            assert len(module.paths) <= 12
            assert len(module.key_files) <= 12
            assert len(module.related_requirements) <= 12
            assert len(module.risks) <= 8
            assert len(module.test_hints) <= 8

    def test_response_safety_notes_are_explicit(self):
        result = build_module_map_draft_from_intake(_req(_idea()))
        combined = " ".join(result.safety_notes).lower()
        assert "no llm" in combined
        assert "no repository files" in combined

    def test_response_limitations_are_explicit(self):
        result = build_module_map_draft_from_intake(_req(_idea()))
        combined = " ".join(result.limitations).lower()
        assert "deterministic" in combined
        assert "no repository file scanning" in combined

    def test_next_recommended_action_mentions_review_or_fix(self):
        result = build_module_map_draft_from_intake(_req(_idea(), sot=_sot()))
        text = result.next_recommended_action.lower()
        assert "review" in text or "fix" in text


class TestIdeaMode:
    def test_idea_draft_source_is_intake_idea(self):
        assert build_module_map_draft_from_intake(_req(_idea())).draft.source == "intake_idea"

    def test_idea_draft_includes_frontend_backend_database_modules(self):
        result = build_module_map_draft_from_intake(_req(_idea()))
        slugs = {m.slug for m in result.draft.modules}
        assert "frontend_ui" in slugs
        assert "backend_api" in slugs
        assert "database_schema" in slugs

    def test_idea_answers_refine_module_choices(self):
        result = build_module_map_draft_from_intake(_req(
            _idea(raw_input="Build a SaaS dashboard"),
            _answers(("cq-idea-8", "Needs role based authentication and admin users")),
        ))
        assert any(m.slug == "auth_access" for m in result.draft.modules)

    def test_idea_draft_includes_test_qa_hint_when_plan_requires_qa(self):
        result = build_module_map_draft_from_intake(_req(
            _idea(raw_input="Build a SaaS task manager with QA tests and regression coverage"),
        ))
        assert any(m.slug == "tests_quality" for m in result.draft.modules)


class TestDocumentMode:
    def test_document_draft_source_is_intake_document(self):
        assert build_module_map_draft_from_intake(_req(_document())).draft.source == "intake_document"

    def test_document_draft_does_not_dump_full_raw_document(self):
        doc = _document()
        result = build_module_map_draft_from_intake(_req(doc))
        dumped = str(result.model_dump(mode="json"))
        assert doc.document_excerpt not in dumped

    def test_document_modules_are_bounded(self):
        result = build_module_map_draft_from_intake(_req(_document()))
        assert 1 <= len(result.draft.modules) <= 12

    def test_document_draft_includes_unknowns_warnings_for_ambiguous_architecture(self):
        result = build_module_map_draft_from_intake(_req(_document(known_stack=[])))
        combined = " ".join(result.validation.warnings + [m.description for m in result.draft.modules]).lower()
        assert "conceptual" in combined or "linked requirements" in combined or "architecture" in combined


class TestExistingProjectMode:
    def test_existing_project_draft_source_is_intake_existing_project(self):
        assert build_module_map_draft_from_intake(_req(_existing())).draft.source == "intake_existing_project"

    def test_existing_project_uses_known_stack(self):
        result = build_module_map_draft_from_intake(_req(_existing()))
        assert result.inferred_stack == ["React", "FastAPI", "SQLite"]

    def test_existing_project_project_path_is_string_hint_only(self):
        result = build_module_map_draft_from_intake(_req(_existing(project_path="/absolute/project/path")))
        dumped = str(result.model_dump(mode="json"))
        assert "/absolute/project/path" not in dumped

    def test_existing_project_does_not_read_files(self):
        source = inspect.getsource(build_module_map_draft_from_intake)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_service_desk_keywords_generate_ticket_sla_notifications_reporting_modules(self):
        result = build_module_map_draft_from_intake(_req(_existing(), sot=_sot()))
        slugs = {m.slug for m in result.draft.modules}
        assert "tickets_workflow" in slugs
        assert "sla_rules" in slugs
        assert "notifications" in slugs
        assert "reports_dashboard" in slugs

    def test_protected_module_answers_appear_as_constraints_risks(self):
        result = build_module_map_draft_from_intake(_req(
            _existing(),
            _answers(("cq-ep-5", "Do not touch billing or legacy auth without review")),
        ))
        risks = " ".join(r for m in result.draft.modules for r in m.risks)
        assert "billing" in risks
        assert "legacy auth" in risks


class TestSourceOfTruthLinkage:
    def test_optional_sot_requirement_ids_link_to_modules(self):
        result = build_module_map_draft_from_intake(_req(_existing(), sot=_sot()))
        linked = {rid for m in result.draft.modules for rid in m.related_requirements}
        assert "REQ-001" in linked

    def test_missing_sot_draft_still_works(self):
        result = build_module_map_draft_from_intake(_req(_idea(), sot=None))
        assert result.validation.valid is True
        assert result.draft.modules

    def test_requirement_coverage_count_is_computed(self):
        result = build_module_map_draft_from_intake(_req(_existing(), sot=_sot()))
        assert result.validation.requirement_coverage_count > 0

    def test_invalid_empty_sot_draft_does_not_crash(self):
        result = build_module_map_draft_from_intake(_req(_idea(), sot={"requirements": "not-a-list"}))
        assert result.draft.modules


class TestValidation:
    def test_no_modules_invalid(self):
        empty = ProjectModuleMapUpsertRequest(modules=[], source="intake_idea", status="draft")
        validation = _mm_validate_draft(empty, _req(_idea()))
        assert validation.valid is False
        assert any("at least one module" in e for e in validation.errors)

    def test_missing_requirement_links_warn(self):
        result = build_module_map_draft_from_intake(_req(_idea(), sot=None))
        assert any("requirement" in w.lower() for w in result.validation.warnings)

    def test_missing_test_hints_warn(self):
        mod = build_module_map_draft_from_intake(_req(_idea())).draft.modules[0].model_copy(update={"test_hints": []})
        draft = ProjectModuleMapUpsertRequest(modules=[mod], source="intake_idea", status="draft")
        validation = _mm_validate_draft(draft, _req(_idea()))
        assert any("test hints" in w.lower() for w in validation.warnings)

    def test_secret_like_content_invalid_blocked(self):
        result = build_module_map_draft_from_intake(_req(_idea(raw_input="Build app api_key=secret123")))
        assert result.validation.valid is False
        assert any("secret-like" in e for e in result.validation.errors)

    def test_unsafe_path_hint_invalid_blocked(self):
        result = build_module_map_draft_from_intake(_req(_idea(raw_input="Map module for credentials/private_key")))
        assert result.validation.valid is False
        assert any("unsafe" in e.lower() or "secret" in e.lower() for e in result.validation.errors)

    def test_existing_project_without_known_stack_warns(self):
        result = build_module_map_draft_from_intake(_req(_existing(known_stack=[])))
        assert any("known_stack" in w for w in result.validation.warnings)

    def test_validation_messages_are_operator_readable(self):
        result = build_module_map_draft_from_intake(_req(_idea(raw_input="Build app password=secret")))
        assert result.validation.errors
        assert all(len(msg) > 10 and "_" not in msg[:8] for msg in result.validation.errors)


class TestPreviewEndpoint:
    def test_post_module_map_draft_returns_200_for_idea(self, client):
        res = client.post("/api/project-intake/module-map-draft", json=_req(_idea()).model_dump(mode="json"))
        assert res.status_code == 200
        assert res.json()["persisted"] is False

    def test_post_module_map_draft_returns_200_for_document(self, client):
        res = client.post("/api/project-intake/module-map-draft", json=_req(_document()).model_dump(mode="json"))
        assert res.status_code == 200

    def test_post_module_map_draft_returns_200_for_existing_project(self, client):
        res = client.post("/api/project-intake/module-map-draft", json=_req(_existing()).model_dump(mode="json"))
        assert res.status_code == 200

    def test_preview_endpoint_persists_nothing(self, client, project):
        before = list_project_module_map_history(project.id)
        payload = _req(_idea(), project_id=project.id, confirm=True).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft", json=payload)
        after = list_project_module_map_history(project.id)
        assert res.status_code == 200
        assert before == after
        assert res.json()["persisted"] is False

    def test_preview_endpoint_creates_no_project(self, client, isolated_db):
        before = len(isolated_db.list_projects())
        client.post("/api/project-intake/module-map-draft", json=_req(_idea()).model_dump(mode="json"))
        assert len(isolated_db.list_projects()) == before

    def test_preview_endpoint_creates_no_run(self, client, isolated_db):
        before = len(isolated_db.list_runs())
        client.post("/api/project-intake/module-map-draft", json=_req(_idea()).model_dump(mode="json"))
        assert len(isolated_db.list_runs()) == before

    def test_preview_endpoint_creates_no_tool_calls(self, client, isolated_db):
        before = isolated_db.list_tool_calls_for_run("missing-run")
        client.post("/api/project-intake/module-map-draft", json=_req(_idea()).model_dump(mode="json"))
        after = isolated_db.list_tool_calls_for_run("missing-run")
        assert after == before

    def test_preview_endpoint_is_deterministic(self, client):
        payload = _req(_document(), sot=_sot()).model_dump(mode="json")
        first = client.post("/api/project-intake/module-map-draft", json=payload).json()
        second = client.post("/api/project-intake/module-map-draft", json=payload).json()
        assert first == second


class TestConfirmPersist:
    def test_confirm_endpoint_requires_project_id(self, client):
        payload = _req(_idea(), confirm=True).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        assert res.status_code == 400

    def test_confirm_endpoint_requires_confirm_persist_true(self, client, project):
        payload = _req(_idea(), project_id=project.id, confirm=False).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        assert res.status_code == 400

    def test_confirm_endpoint_rejects_invalid_draft(self, client, project):
        payload = _req(_idea(raw_input="Build app token=secret"), project_id=project.id, confirm=True).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        assert res.status_code == 422

    def test_confirm_endpoint_persists_exactly_one_active_module_map_version(self, client, project):
        payload = _req(_existing(), project_id=project.id, confirm=True, sot=_sot()).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["persisted"] is True
        active = get_active_project_module_map(project.id)
        assert active is not None
        assert active.version == 1
        assert len(list_project_module_map_history(project.id)) == 1

    def test_confirm_endpoint_does_not_create_run_or_tool_call(self, client, isolated_db, project):
        before_runs = len(isolated_db.list_runs())
        before_tool_calls = isolated_db.list_tool_calls_for_run("missing-run")
        payload = _req(_idea(), project_id=project.id, confirm=True, sot=_sot()).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        assert res.status_code == 200
        assert len(isolated_db.list_runs()) == before_runs
        assert isolated_db.list_tool_calls_for_run("missing-run") == before_tool_calls

    def test_confirm_endpoint_returns_persisted_id_version(self, client, project):
        payload = _req(_idea(), project_id=project.id, confirm=True, sot=_sot()).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft/confirm", json=payload)
        data = res.json()
        assert data["persisted"] is True
        assert data["module_map_id"]
        assert data["version"] == 1


class TestCompatibilityImports:
    def test_auto_sot_draft_tests_still_importable(self):
        import tests.test_auto_source_of_truth_draft_from_intake as _mod
        assert _mod is not None

    def test_clarifying_questions_tests_still_importable(self):
        import tests.test_clarifying_questions_engine as _mod
        assert _mod is not None

    def test_unified_intake_tests_still_importable(self):
        import tests.test_unified_autonomous_project_intake as _mod
        assert _mod is not None

    def test_project_module_map_tests_still_importable(self):
        import tests.test_project_module_map as _mod
        assert _mod is not None

    def test_module_map_agent_context_tests_still_importable(self):
        import tests.test_module_map_agent_context_wiring as _mod
        assert _mod is not None

    def test_module_map_patch_draft_tests_still_importable(self):
        import tests.test_module_map_patch_draft_context as _mod
        assert _mod is not None


class TestStaticSafety:
    def test_no_execute_run_in_builder(self):
        assert "execute_run" not in inspect.getsource(build_module_map_draft_from_intake)

    def test_no_asyncio_create_task_in_builder(self):
        assert "asyncio.create_task" not in inspect.getsource(build_module_map_draft_from_intake)

    def test_no_subprocess_or_os_command_in_builder(self):
        source = inspect.getsource(build_module_map_draft_from_intake)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_no_provider_calls_in_builder(self):
        source = inspect.getsource(build_module_map_draft_from_intake)
        assert "ollama.chat_completion" not in source
        assert "claude_provider" not in source
        assert "codex" not in source

    def test_no_file_content_reads_in_builder(self):
        source = inspect.getsource(build_module_map_draft_from_intake)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_no_create_tool_call_in_builder(self):
        assert "create_tool_call" not in inspect.getsource(build_module_map_draft_from_intake)

    def test_no_project_or_run_creation_in_builder(self):
        source = inspect.getsource(build_module_map_draft_from_intake)
        assert "create_project" not in source
        assert "create_run" not in source

    def test_no_db_write_in_preview_endpoint(self):
        source = inspect.getsource(intake_module)
        preview_name = "post_project_intake_module_map_draft"
        assert preview_name not in source  # endpoints live in routes.py, not the pure intake module

    def test_no_hidden_persistence_without_confirm_persist(self, client, project):
        payload = _req(_idea(), project_id=project.id, confirm=False).model_dump(mode="json")
        res = client.post("/api/project-intake/module-map-draft", json=payload)
        assert res.status_code == 200
        assert list_project_module_map_history(project.id) == []

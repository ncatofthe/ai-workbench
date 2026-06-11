"""Tests for Project Module Map → Agent Result Patch Draft context wiring."""

from __future__ import annotations

import inspect
import json
import re
import sys

import pytest
from fastapi.testclient import TestClient

from src.models import ProjectModuleMapDocument, ProjectModuleMapItem
from src.storage import database
from src.storage.module_map_storage import (
    build_patch_draft_module_context,
    create_or_update_project_module_map,
)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("SECRET_FILE_CONTENT_DO_NOT_LEAK\n", encoding="utf-8")
    project = isolated_db.create_project(
        "Module Patch Draft Project",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Module patch draft wiring",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement auth login page",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-AUTH-001\n"
            "acceptance_criteria:\n"
            "- Login page submits credentials.\n"
            "source_of_truth_summary: Authentication must stay compatible.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
            "Build login flow without reading file contents."
        ),
    )
    return project, run, step


_GOOD_AGENT_RESULT = {
    "summary": "Implement login flow.",
    "analysis": "Auth route and frontend page need coordinated changes.",
    "proposed_files": ["backend/src/auth/service.ts"],
    "patch_intent": "Add login JWT session behavior.",
    "risks": ["May affect login security."],
    "test_suggestions": ["Run auth/login tests."],
    "questions": ["Confirm session expiry."],
    "recommended_next_action": "Create guarded proposal.",
    "can_feed_patch_draft": True,
}


def _bridge(client: TestClient, run_id: str, step_id: str, body: dict | None = None):
    return client.post(
        f"/api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft",
        json=body or {"agent_result": _GOOD_AGENT_RESULT},
    )


def _tool_call_count(step_id: str) -> int:
    return len(database.list_tool_calls_for_step(step_id, limit=500))


def _module(
    *,
    module_id: str,
    name: str,
    slug: str,
    module_type: str = "backend",
    related_requirements: list[str] | None = None,
    paths: list[str] | None = None,
    key_files: list[str] | None = None,
    confidence: str = "medium",
) -> ProjectModuleMapItem:
    return ProjectModuleMapItem(
        id=module_id,
        name=name,
        slug=slug,
        module_type=module_type,
        description=f"{name} module",
        responsibilities=[f"{name} responsibility"],
        paths=paths or [f"src/{slug}"],
        key_files=key_files or [f"src/{slug}/index.ts"],
        related_requirements=related_requirements or [],
        test_hints=[f"{slug} tests"],
        risks=[f"{slug} risk"],
        confidence=confidence,
    )


def _create_map(project_id: str, modules: list[ProjectModuleMapItem] | None = None):
    return create_or_update_project_module_map(
        project_id,
        ProjectModuleMapDocument(
            project_id=project_id,
            version=1,
            status="active",
            source="manual",
            modules=modules
            or [
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    related_requirements=["REQ-AUTH-001"],
                    paths=["backend/src/auth", "backend/src/routes/auth"],
                    key_files=["backend/src/auth/service.ts", "backend/src/routes/auth.ts"],
                    confidence="high",
                ),
                _module(module_id="mod-frontend", name="Frontend", slug="frontend", module_type="frontend"),
                _module(module_id="mod-db", name="Database", slug="database", module_type="database"),
            ],
        ),
    )


class _AgentResult:
    def __init__(self, **kwargs):
        self.summary = kwargs.get("summary", "")
        self.analysis = kwargs.get("analysis", "")
        self.patch_intent = kwargs.get("patch_intent", "")
        self.proposed_files = kwargs.get("proposed_files", [])


class TestPatchDraftModuleContextBuilder:
    def test_no_active_module_map_returns_false(self, project_run_step):
        project, _, step = project_run_step
        context = build_patch_draft_module_context(project.id, _AgentResult(), step.input, step.title)

        assert context.has_active_module_map is False

    def test_agent_result_proposed_files_maps_to_module_paths(self, project_run_step):
        project, _, step = project_run_step
        _create_map(project.id)

        context = build_patch_draft_module_context(
            project.id,
            _AgentResult(proposed_files=["backend/src/auth/service.ts"]),
            step.input,
            step.title,
        )

        assert context.matched_modules[0]["slug"] == "auth"

    def test_requirement_ids_map_to_related_module(self, project_run_step):
        project, _, step = project_run_step
        _create_map(project.id)

        context = build_patch_draft_module_context(
            project.id,
            _AgentResult(),
            step.input,
            "Unmatched title",
            requirement_ids=["REQ-AUTH-001"],
        )

        assert context.matched_modules[0]["slug"] == "auth"
        assert context.matched_requirement_ids == ["REQ-AUTH-001"]

    def test_auth_keyword_maps_to_auth_module(self, project_run_step):
        project, _, step = project_run_step
        _create_map(project.id)

        context = build_patch_draft_module_context(
            project.id,
            _AgentResult(patch_intent="Fix login JWT session"),
            "",
            "",
        )

        assert any(mod["slug"] == "auth" for mod in context.matched_modules)

    def test_frontend_page_keyword_maps_to_frontend_module(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(project.id)

        context = build_patch_draft_module_context(
            project.id,
            _AgentResult(patch_intent="Update frontend page component UI"),
        )

        assert any(mod["slug"] == "frontend" for mod in context.matched_modules)

    def test_database_schema_keyword_maps_to_database_module(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(project.id)

        context = build_patch_draft_module_context(
            project.id,
            _AgentResult(analysis="Database schema prisma model change"),
        )

        assert any(mod["slug"] == "database" for mod in context.matched_modules)

    def test_output_caps_matched_modules(self, project_run_step):
        project, _, _ = project_run_step
        modules = [
            _module(module_id=f"mod-{i}", name=f"Auth {i}", slug="auth", confidence="high")
            for i in range(9)
        ]
        _create_map(project.id, modules)

        context = build_patch_draft_module_context(project.id, _AgentResult(patch_intent="auth login"))

        assert len(context.matched_modules) <= 5

    def test_output_caps_paths_and_key_files(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(
            project.id,
            [
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    paths=[f"backend/auth/path_{i}" for i in range(20)],
                    key_files=[f"backend/auth/file_{i}.py" for i in range(20)],
                )
            ],
        )

        context = build_patch_draft_module_context(project.id, _AgentResult(patch_intent="auth"))
        mod = context.matched_modules[0]

        assert len(mod["paths"]) == 8
        assert len(mod["key_files"]) == 8


class TestPatchDraftEndpointModuleContext:
    def test_active_module_map_adds_module_context_to_patch_draft_response(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        response = _bridge(client, run.id, step.id)

        assert response.status_code == 200
        data = response.json()
        assert data["module_context"]["has_active_module_map"] is True
        assert data["module_context"]["matched_modules"][0]["slug"] == "auth"

    def test_no_active_module_map_returns_empty_false_module_context_safely(self, client, project_run_step):
        _, run, step = project_run_step

        response = _bridge(client, run.id, step.id)

        assert response.status_code == 200
        data = response.json()
        assert data["module_context"]["has_active_module_map"] is False
        assert data["module_context_summary"] == ""
        assert "PROJECT MODULE MAP PATCH CONTEXT" not in data["patch_context"]

    def test_patch_context_contains_project_module_map_patch_context(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert "PROJECT MODULE MAP PATCH CONTEXT" in data["patch_context"]
        assert "Module: Auth" in data["patch_context"]

    def test_output_includes_key_files_but_not_file_contents(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert "backend/src/auth/service.ts" in data["patch_context"]
        assert "SECRET_FILE_CONTENT_DO_NOT_LEAK" not in data["patch_context"]

    def test_output_includes_module_risks_and_test_hints(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert "auth risk" in data["module_risks"]
        assert "auth tests" in data["module_test_hints"]

    def test_recommended_files_from_module_map_are_present(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert "backend/src/auth/service.ts" in data["recommended_files_from_module_map"]

    def test_existing_old_text_new_text_remain_manual_empty(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert "old_text" not in data
        assert "new_text" not in data
        assert "Fill `file_path`, `old_text`, and `new_text`" in data["patch_context"]

    def test_endpoint_does_not_create_proposal_or_tool_calls(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        before = _tool_call_count(step.id)

        response = _bridge(client, run.id, step.id)

        assert response.status_code == 200
        assert _tool_call_count(step.id) == before
        calls = database.list_tool_calls_for_step(step.id, limit=500)
        assert [tc for tc in calls if tc.tool_name == "propose-patch"] == []

    def test_endpoint_does_not_apply_patch_or_mutate_files(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        app_file = f"{project.path}/app.py"
        before = open(app_file, "r", encoding="utf-8").read()

        response = _bridge(client, run.id, step.id)

        assert response.status_code == 200
        assert open(app_file, "r", encoding="utf-8").read() == before

    def test_endpoint_creates_no_run_command_or_tool_execution(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        response = _bridge(client, run.id, step.id)

        assert response.status_code == 200
        calls = database.list_tool_calls_for_step(step.id, limit=500)
        assert [tc for tc in calls if tc.tool_name == "run-command"] == []
        assert [tc for tc in calls if tc.tool_name == "apply-patch"] == []

    def test_guard_required_remains_true(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()

        assert data["guard_required"] is True

    def test_safety_notes_mention_module_map_context_only(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _bridge(client, run.id, step.id).json()
        notes = " ".join(data["safety_notes"]).lower()

        assert "module map" in notes
        assert "does not read file contents" in notes


class TestStaticSafety:
    def _bridge_source(self) -> str:
        from src.api import routes

        source = inspect.getsource(routes)
        idx = source.find("Agent Result → Patch Draft Bridge v1")
        return source[idx:] if idx >= 0 else source

    def test_no_execute_run(self):
        assert not re.findall(r"\bexecute_run\s*\(", self._bridge_source())

    def test_no_asyncio_create_task(self):
        assert "asyncio.create_task(" not in self._bridge_source()

    def test_no_subprocess_or_os_command(self):
        source = self._bridge_source()
        assert not re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", source)
        assert "os.system(" not in source

    def test_no_provider_calls(self):
        source = self._bridge_source()
        assert "ollama.chat_completion" not in source
        assert "claude_provider." not in source
        assert "codex." not in source

    def test_no_file_content_reads_in_module_patch_context_builder(self):
        from src.storage import module_map_storage

        source = inspect.getsource(module_map_storage.build_patch_draft_module_context)
        assert ".read_text(" not in source
        assert "open(" not in source
        assert "read_file" not in source

    def test_no_db_schema_changes_in_module_patch_context_builder(self):
        from src.storage import module_map_storage

        source = inspect.getsource(module_map_storage.build_patch_draft_module_context)
        assert "CREATE TABLE" not in source
        assert "ALTER TABLE" not in source
        assert "DROP TABLE" not in source


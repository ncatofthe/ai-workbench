"""Tests for Project Module Map → Agent Execution Context wiring.

The wiring is read-only: it may include bounded module-map hints in agent
execution context and prompt previews, but must not scan files, read file
contents, create tool calls from the context endpoint, or bypass provider/tool
safety boundaries.
"""

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
    build_agent_module_context_for_step,
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
        "Module Context Project",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Module map wiring",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement auth login endpoint",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-AUTH-001\n"
            "acceptance_criteria:\n"
            "- Login returns a session token.\n"
            "constraints:\n"
            "- Preserve JWT session behavior.\n"
            "forbidden_changes:\n"
            "- Do not touch .env.\n"
            "source_of_truth_summary: Authentication must stay compatible.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
            "Build login flow without reading file contents."
        ),
    )
    return project, run, step


def _context(client: TestClient, run_id: str, step_id: str):
    return client.get(f"/api/runs/{run_id}/steps/{step_id}/agent-execution-context")


def _run_agent(client: TestClient, run_id: str, step_id: str, body: dict):
    return client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-executions/run", json=body)


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


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
    doc = ProjectModuleMapDocument(
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
    )
    return create_or_update_project_module_map(project_id, doc)


class TestModuleContextBuilder:
    def test_no_active_module_map_returns_false(self, project_run_step):
        project, _, step = project_run_step
        context = build_agent_module_context_for_step(project.id, step.input, step.title)

        assert context.has_active_module_map is False
        assert context.matched_modules == []

    def test_requirement_id_match_selects_related_module(self, project_run_step):
        project, _, step = project_run_step
        _create_map(project.id)

        context = build_agent_module_context_for_step(
            project.id,
            step.input,
            step.title,
            requirement_ids=["REQ-AUTH-001"],
        )

        assert context.has_active_module_map is True
        assert context.matched_modules[0]["slug"] == "auth"
        assert context.matched_requirement_ids == ["REQ-AUTH-001"]

    def test_auth_keyword_selects_auth_module(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(project.id)

        context = build_agent_module_context_for_step(project.id, "", "Fix login JWT session")

        assert any(mod["slug"] == "auth" for mod in context.matched_modules)

    def test_frontend_keyword_selects_frontend_module(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(project.id)

        context = build_agent_module_context_for_step(project.id, "", "Update frontend page component UI")

        assert any(mod["slug"] == "frontend" for mod in context.matched_modules)

    def test_database_keyword_selects_database_module(self, project_run_step):
        project, _, _ = project_run_step
        _create_map(project.id)

        context = build_agent_module_context_for_step(project.id, "", "Update database schema prisma model")

        assert any(mod["slug"] == "database" for mod in context.matched_modules)

    def test_fallback_summary_is_bounded(self, project_run_step):
        project, _, _ = project_run_step
        modules = [
            _module(module_id=f"mod-{i}", name=f"Module {i}", slug=f"module-{i}", confidence="high")
            for i in range(12)
        ]
        _create_map(project.id, modules)

        context = build_agent_module_context_for_step(project.id, "", "Unmatched work")

        assert context.has_active_module_map is True
        assert len(context.matched_modules) == 5
        assert "+2 more" in context.module_summary

    def test_matched_modules_are_capped(self, project_run_step):
        project, _, _ = project_run_step
        modules = [
            _module(module_id=f"mod-{i}", name=f"Auth {i}", slug="auth", confidence="high")
            for i in range(8)
        ]
        _create_map(project.id, modules)

        context = build_agent_module_context_for_step(project.id, "", "auth login session")

        assert len(context.matched_modules) <= 5

    def test_key_files_and_paths_are_capped(self, project_run_step):
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

        context = build_agent_module_context_for_step(project.id, "", "auth login")
        mod = context.matched_modules[0]

        assert len(mod["paths"]) == 8
        assert len(mod["key_files"]) == 8
        assert len(context.matched_paths) <= 16

    def test_context_contains_no_file_contents(self, project_run_step):
        project, _, step = project_run_step
        _create_map(project.id)

        context = build_agent_module_context_for_step(project.id, step.input, step.title)
        dumped = json.dumps(context.model_dump(mode="json"))

        assert "SECRET_FILE_CONTENT_DO_NOT_LEAK" not in dumped


class TestAgentContextEndpoint:
    def test_active_module_map_appears_in_agent_execution_context(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        response = _context(client, run.id, step.id)

        assert response.status_code == 200
        module_context = response.json()["module_context"]
        assert module_context["has_active_module_map"] is True
        assert module_context["module_map_version"] == 1

    def test_context_endpoint_creates_no_tool_calls(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        before = _tool_call_count(run.id)

        response = _context(client, run.id, step.id)

        assert response.status_code == 200
        assert _tool_call_count(run.id) == before

    def test_context_endpoint_includes_bounded_module_fields(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _context(client, run.id, step.id).json()
        module = data["module_context"]["matched_modules"][0]

        assert set(module) >= {
            "id",
            "name",
            "slug",
            "module_type",
            "responsibilities",
            "paths",
            "key_files",
            "related_requirements",
            "test_hints",
            "risks",
            "confidence",
        }

    def test_context_endpoint_includes_source_of_truth_summary(self, client, project_run_step):
        project, run, step = project_run_step

        data = _context(client, run.id, step.id).json()

        assert data["source_of_truth_summary"] == "Authentication must stay compatible."


class TestAgentPromptAndExecution:
    def test_dry_run_result_includes_module_context_summary(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        before = _tool_call_count(run.id)

        response = _run_agent(client, run.id, step.id, {"mode": "dry_run"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "planned"
        assert data["context"]["module_context"]["has_active_module_map"] is True
        assert "PROJECT MODULE MAP CONTEXT" in data["prompt_preview"]
        assert _tool_call_count(run.id) == before

    def test_mock_mode_does_not_mutate_files(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        app_file = database.get_project(project.id).path + "/app.py"
        before = open(app_file, "r", encoding="utf-8").read()

        response = _run_agent(client, run.id, step.id, {"mode": "mock", "persist_result": False})

        assert response.status_code == 200
        assert open(app_file, "r", encoding="utf-8").read() == before

    def test_provider_mode_still_requires_allow_provider_call(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        response = _run_agent(client, run.id, step.id, {"mode": "provider", "allow_provider_call": False})

        assert response.status_code == 403

    def test_unknown_agent_behavior_unchanged(self, client, project_run_step):
        project, run, step = project_run_step

        response = _run_agent(
            client,
            run.id,
            step.id,
            {"mode": "provider", "allow_provider_call": True, "agent_id": "missing-agent"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "blocked"

    def test_prompt_includes_project_module_map_context_when_map_exists(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _run_agent(client, run.id, step.id, {"mode": "dry_run"}).json()

        assert "## PROJECT MODULE MAP CONTEXT" in data["prompt_preview"]
        assert "Module: Auth" in data["prompt_preview"]
        assert "backend/src/auth/service.ts" in data["prompt_preview"]

    def test_prompt_omits_module_context_when_no_map_exists(self, client, project_run_step):
        _, run, step = project_run_step

        data = _run_agent(client, run.id, step.id, {"mode": "dry_run"}).json()

        assert "PROJECT MODULE MAP CONTEXT" not in data["prompt_preview"]

    def test_prompt_includes_key_files_but_not_file_contents(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        data = _run_agent(client, run.id, step.id, {"mode": "dry_run"}).json()

        assert "backend/src/auth/service.ts" in data["prompt_preview"]
        assert "SECRET_FILE_CONTENT_DO_NOT_LEAK" not in data["prompt_preview"]

    def test_prompt_is_bounded_in_size(self, client, project_run_step):
        project, run, step = project_run_step
        modules = [
            _module(
                module_id=f"mod-{i}",
                name=f"Auth {i}",
                slug="auth",
                key_files=[f"backend/auth/file_{j}.py" for j in range(40)],
                paths=[f"backend/auth/path_{j}" for j in range(40)],
            )
            for i in range(10)
        ]
        _create_map(project.id, modules)

        data = _run_agent(client, run.id, step.id, {"mode": "dry_run"}).json()

        assert len(data["prompt_preview"]) <= 20000


class TestSafetyInvariants:
    def test_existing_agent_execution_harness_tests_still_expected(self):
        # This file extends, rather than replaces, the existing harness tests.
        assert True

    def test_project_module_map_contract_is_still_available(self):
        assert ProjectModuleMapDocument
        assert ProjectModuleMapItem

    def test_no_execute_run_in_agent_context_wiring(self):
        from src.api import routes

        section = inspect.getsource(routes._build_agent_execution_context) + inspect.getsource(routes.get_agent_execution_context)
        assert not re.findall(r"\bexecute_run\s*\(", section)

    def test_no_asyncio_create_task_in_agent_context_wiring(self):
        from src.api import routes

        section = inspect.getsource(routes._build_agent_execution_context) + inspect.getsource(routes.get_agent_execution_context)
        assert "asyncio.create_task(" not in section

    def test_no_subprocess_or_os_command_in_agent_context_wiring(self):
        from src.api import routes

        section = inspect.getsource(routes._build_agent_execution_context) + inspect.getsource(routes.get_agent_execution_context)
        assert not re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", section)
        assert "os.system(" not in section

    def test_no_provider_calls_added_to_context_endpoint(self):
        from src.api import routes

        section = inspect.getsource(routes.get_agent_execution_context)
        assert "ollama." not in section
        assert "claude_provider." not in section
        assert "codex." not in section

    def test_no_create_tool_call_in_context_endpoint(self):
        from src.api import routes

        source = inspect.getsource(routes.get_agent_execution_context)
        assert "create_tool_call" not in source

    def test_no_file_content_reads_in_builder_path(self):
        from src.storage import module_map_storage

        source = inspect.getsource(module_map_storage.build_agent_module_context_for_step)
        assert ".read_text(" not in source
        assert "open(" not in source
        assert "read_file" not in source

    def test_no_db_schema_changes_in_module_map_storage_builder(self):
        from src.storage import module_map_storage

        source = inspect.getsource(module_map_storage.build_agent_module_context_for_step)
        assert "CREATE TABLE" not in source
        assert "ALTER TABLE" not in source
        assert "DROP TABLE" not in source


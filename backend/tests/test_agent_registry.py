from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from src.agents.registry import get_all_agents, get_agent, select_agents_for_task
from src.api import routes
from src.models import CreateRunRequest, UpdateRunAgentAssignmentRequest
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


def test_agent_registry_has_structured_unique_templates():
    agents = get_all_agents()
    ids = [agent.id for agent in agents]

    assert len(agents) >= 20
    assert len(ids) == len(set(ids))
    required_ids = {
        "orchestrator",
        "product-manager",
        "business-analyst",
        "architect",
        "api-designer",
        "frontend-developer",
        "backend-developer",
        "fullstack-developer",
        "react-specialist",
        "typescript-pro",
        "fastapi-developer",
        "node-specialist",
        "php-pro",
        "sql-pro",
        "postgres-pro",
        "qa-expert",
        "test-automator",
        "code-reviewer",
        "security-auditor",
        "devops-engineer",
        "technical-writer",
        "error-detective",
        "git-workflow-manager",
    }
    assert required_ids.issubset(set(ids))
    assert get_agent("backend") is not None  # legacy alias
    assert get_agent("frontend") is not None  # legacy alias

    for agent in agents:
        assert agent.category
        assert agent.model_profile
        assert agent.default_model
        assert agent.skills
        assert agent.best_for
        assert agent.provider.value == "ollama"


def test_selector_picks_frontend_backend_qa_for_web_app(tmp_path):
    project_dir = tmp_path / "web-app"
    project_dir.mkdir()
    (project_dir / "package.json").write_text(
        '{"dependencies":{"react":"latest","vite":"latest"},"devDependencies":{"typescript":"latest"},"scripts":{"build":"vite build"}}',
        encoding="utf-8",
    )
    (project_dir / "pyproject.toml").write_text(
        '[project]\ndependencies = ["fastapi", "pydantic", "pytest"]\n',
        encoding="utf-8",
    )

    result = select_agents_for_task(
        prompt="Build auth screens, FastAPI endpoints, SQLite persistence, and tests",
        project_name="Demo",
        project_path=str(project_dir),
        project_stack="SQLite",
        package_manager="npm pip",
    )
    selected = result["selected_agents"]
    agent_ids = {item["agent_id"] for item in selected}

    assert "orchestrator" in agent_ids
    assert "business-analyst" in agent_ids
    assert "frontend-developer" in agent_ids
    assert "react-specialist" in agent_ids
    assert "backend-developer" in agent_ids
    assert "fastapi-developer" in agent_ids
    assert "sql-pro" in agent_ids
    assert "qa-expert" in agent_ids
    assert result["team_size"] == len(selected)
    assert result["recommended_execution_mode"] == "offline"
    assert {"react", "vite", "typescript", "python", "fastapi"}.issubset(set(result["detected_stack"]))
    assert all(0 < item["confidence"] <= 1 for item in selected)
    assert all(item["reason"] for item in selected)


def test_selector_picks_mobile_agent_for_mobile_app(tmp_path):
    project_dir = tmp_path / "mobile-app"
    project_dir.mkdir()

    result = select_agents_for_task(
        prompt="Create a Flutter Android and iOS expense tracker app",
        project_name="Mobile",
        project_path=str(project_dir),
        project_stack="Flutter mobile",
    )
    agent_ids = {item["agent_id"] for item in result["selected_agents"]}

    assert "mobile-developer" in agent_ids
    assert "qa-expert" in agent_ids


def test_selector_picks_devops_and_security_for_deploy_tasks(tmp_path):
    project_dir = tmp_path / "deploy-app"
    project_dir.mkdir()
    (project_dir / "Dockerfile").write_text("FROM python:3.12\n", encoding="utf-8")
    (project_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    result = select_agents_for_task(
        prompt="Prepare production deployment, Docker setup, CI pipeline, auth and secrets review",
        project_name="Deploy",
        project_path=str(project_dir),
        project_stack="",
    )
    agent_ids = {item["agent_id"] for item in result["selected_agents"]}

    assert "devops-engineer" in agent_ids
    assert "security-auditor" in agent_ids
    assert "docker" in result["detected_stack"]


@pytest.mark.asyncio
async def test_run_creation_persists_selected_agent_team(isolated_db, tmp_path, monkeypatch):
    project_dir = tmp_path / "React FastAPI"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="React FastAPI",
        path=str(project_dir),
        stack="React TypeScript FastAPI SQLite",
        package_manager="npm pip",
    )

    captured = {}

    async def fake_execute_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(routes, "execute_run", fake_execute_run)

    run = await routes.post_run(
        CreateRunRequest(
            prompt="Build a dashboard with FastAPI endpoints and tests",
            project_id=project.id,
        )
    )
    await asyncio.sleep(0)

    assignments = isolated_db.list_run_agent_assignments(run.id)
    agent_ids = {assignment.agent_id for assignment in assignments}

    assert "orchestrator" in agent_ids
    assert "business-analyst" in agent_ids
    assert "frontend-developer" in agent_ids
    assert "backend-developer" in agent_ids
    assert "qa-expert" in agent_ids
    assert captured["selected_agents"]
    assert {item["agent_id"] for item in captured["selected_agents"]} == agent_ids


@pytest.mark.asyncio
async def test_run_agent_selection_endpoint_replaces_team(isolated_db, tmp_path):
    project_dir = tmp_path / "Mobile App"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="Mobile App",
        path=str(project_dir),
        stack="Flutter mobile app",
    )
    run = isolated_db.create_run(
        prompt="Build an Android mobile expense tracker",
        project_id=project.id,
        project_path=str(Path(project.path)),
    )

    selected = await routes.post_select_run_agents(run.id)
    listed = await routes.get_run_agents(run.id)

    assert selected["team_size"] == len(listed)
    assert any(item.agent_id == "mobile-developer" for item in selected["selected_agents"])
    assert any(item.agent_id == "orchestrator" for item in listed)


@pytest.mark.asyncio
async def test_run_agent_patch_updates_assignment_status(isolated_db, tmp_path):
    project_dir = tmp_path / "Patch Agent"
    project_dir.mkdir()
    project = isolated_db.create_project(name="Patch Agent", path=str(project_dir), stack="React")
    run = isolated_db.create_run(prompt="Build UI", project_id=project.id, project_path=project.path)
    await routes.post_select_run_agents(run.id)

    updated = await routes.patch_run_agent(
        run.id,
        "frontend-developer",
        UpdateRunAgentAssignmentRequest(status="disabled", assigned_role="paused frontend"),
    )

    assert updated.agent_id == "frontend-developer"
    assert updated.status == "disabled"
    assert updated.assigned_role == "paused frontend"

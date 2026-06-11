from __future__ import annotations

import pytest

from src.api import routes
from src.model_router import infer_task_type_for_agent
from src.models import ProviderMode
from src.orchestrator import engine
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def run_with_assignments(isolated_db, tmp_path):
    project_dir = tmp_path / "route-project"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="Route Project",
        path=str(project_dir),
        stack="React FastAPI",
    )
    run = isolated_db.create_run(
        prompt="Build a web app with auth, tests, security review, and docs",
        project_id=project.id,
        project_path=project.path,
    )
    isolated_db.replace_run_agent_assignments(
        run.id,
        [
            {
                "agent_id": "backend-developer",
                "assigned_role": "implementation",
                "reason": "Backend needed.",
                "confidence": 0.9,
            },
            {
                "agent_id": "security-auditor",
                "assigned_role": "security",
                "reason": "Security review needed.",
                "confidence": 0.88,
            },
            {
                "agent_id": "technical-writer",
                "assigned_role": "documentation",
                "reason": "Docs needed.",
                "confidence": 0.7,
            },
        ],
    )
    return run


def test_route_decision_can_be_created_and_read(isolated_db):
    decision = isolated_db.create_model_route_decision(
        run_id="run-1",
        agent_id="backend-developer",
        task_type="implementation",
        model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b",
        selected_provider="local_ollama",
        fallback_model="qwen2.5-coder:7b",
        fallback_provider="local_ollama",
        provider_mode=ProviderMode.LOCAL.value,
        reason="test route",
        confidence=0.8,
        warnings=["fallback used"],
    )

    listed = isolated_db.get_model_route_decisions_for_run("run-1")
    loaded = isolated_db.get_model_route_decision(decision.id)

    assert loaded is not None
    assert loaded.id == decision.id
    assert loaded.warnings == ["fallback used"]
    assert [item.id for item in listed] == [decision.id]


@pytest.mark.asyncio
async def test_preview_does_not_persist(isolated_db, run_with_assignments, monkeypatch):
    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b", "qwen3:8b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    response = await routes.preview_run_model_routes(run_with_assignments.id)

    assert response.persisted is False
    assert response.count == 3
    assert isolated_db.get_model_route_decisions_for_run(run_with_assignments.id) == []


@pytest.mark.asyncio
async def test_persist_saves_route_decisions(isolated_db, run_with_assignments, monkeypatch):
    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b", "qwen3:8b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    response = await routes.persist_run_model_routes(run_with_assignments.id)
    listed = isolated_db.get_model_route_decisions_for_run(run_with_assignments.id)

    assert response.persisted is True
    assert response.count == 3
    assert len(listed) == 3
    assert {item.agent_id for item in listed} == {
        "backend-developer",
        "security-auditor",
        "technical-writer",
    }


@pytest.mark.asyncio
async def test_repeated_persist_updates_instead_of_duplicating(isolated_db, run_with_assignments, monkeypatch):
    async def first_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b", "qwen3:8b"]

    async def second_models(_base_url: str) -> list[str]:
        return ["qwen3-coder:30b", "deepseek-r1:14b", "qwen3:14b"]

    monkeypatch.setattr(routes.ollama, "list_models", first_models)
    first = await routes.persist_run_model_routes(run_with_assignments.id)
    first_ids = {item.id for item in first.decisions}

    monkeypatch.setattr(routes.ollama, "list_models", second_models)
    second = await routes.persist_run_model_routes(run_with_assignments.id)
    listed = isolated_db.get_model_route_decisions_for_run(run_with_assignments.id)

    assert second.count == 3
    assert len(listed) == 3
    assert {item.id for item in listed} == first_ids
    backend = next(item for item in listed if item.agent_id == "backend-developer")
    assert backend.selected_model == "qwen3-coder:30b"


@pytest.mark.asyncio
async def test_local_provider_mode_never_chooses_external(isolated_db, run_with_assignments, monkeypatch):
    async def fake_list_models(_base_url: str) -> list[str]:
        return []

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)
    monkeypatch.setattr(
        routes,
        "get_config",
        lambda: {"provider_mode": "local", "codex": {"enabled": True}, "claude": {"enabled": True}},
    )

    response = await routes.preview_run_model_routes(run_with_assignments.id)

    assert response.count == 3
    assert all(item.selected_provider == "local_ollama" for item in response.decisions)


def test_task_type_mapping_for_route_decisions():
    assert infer_task_type_for_agent("backend-developer", "implementation") == "implementation"
    assert infer_task_type_for_agent("react-specialist", "") == "implementation"
    assert infer_task_type_for_agent("security-auditor", "") == "security_review"
    assert infer_task_type_for_agent("technical-writer", "") == "documentation"


@pytest.mark.asyncio
async def test_run_without_assigned_agents_returns_empty_response(isolated_db):
    run = isolated_db.create_run(prompt="No assigned team")

    response = await routes.preview_run_model_routes(run.id)

    assert response.count == 0
    assert response.decisions == []
    assert "no assigned agents" in response.warnings[0].lower()


@pytest.mark.asyncio
async def test_route_preview_failure_does_not_break_run_execution(isolated_db, monkeypatch):
    async def fake_health(_base_url: str) -> bool:
        return False

    async def broken_preview(**_kwargs):
        raise RuntimeError("router unavailable")

    monkeypatch.setattr(engine.ollama, "check_health", fake_health)
    monkeypatch.setattr(engine, "_persist_model_route_preview", broken_preview)

    run = isolated_db.create_run(prompt="Complete fallback run")
    await engine.execute_run(
        run_id=run.id,
        prompt=run.prompt,
        mode=run.mode.value,
        run_dir=run.run_dir,
        selected_agents=[
            {
                "agent_id": "backend-developer",
                "assigned_role": "implementation",
                "reason": "Backend needed.",
                "confidence": 0.9,
            }
        ],
    )

    stored = isolated_db.get_run(run.id)
    steps = isolated_db.list_run_steps(run.id)
    preview_step = next(step for step in steps if step.title == "Preview model routes")

    assert stored is not None
    assert stored.status.value == "completed"
    assert preview_step.status == "completed"
    assert "router unavailable" in preview_step.output

"""Tests for step-level model route decisions.

Covers:
- infer_agent_for_step keyword rules
- infer_task_type_for_step keyword rules
- database upsert_step_route_decision and list helpers
- database delete_step_route_decisions_for_run (stale cleanup)
- routes preview/persist endpoints for steps
- execution pipeline uses per-step model from route decisions
- external provider fallback during execution
- per-step route failure emits warning, does not crash run
- repeated persist produces no duplicates
- missing route decision falls back to run-level Ollama model
"""
from __future__ import annotations

import pytest

from src.api import routes
from src.model_router import (
    build_guided_step_actions,
    infer_agent_for_step,
    infer_task_type_for_step,
    infer_tools_for_step,
)
from src.models import ProviderMode, RunStep, ToolCall
from src.orchestrator import engine
from src.storage import database


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def run_with_staged_steps(isolated_db, tmp_path):
    project_dir = tmp_path / "step-route-project"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="Step Route Project",
        path=str(project_dir),
        stack="React FastAPI",
    )
    run = isolated_db.create_run(
        prompt="Build and test a full-stack app",
        project_id=project.id,
        project_path=project.path,
    )
    # Create a parent orchestrator step
    parent_step = isolated_db.create_run_step(
        run_id=run.id,
        parent_step_id="",
        agent_id="orchestrator",
        status="completed",
        title="Stage executable task steps",
        input="Convert tasks.md into pending run_steps",
    )
    # Create three child (staged) steps
    steps = [
        isolated_db.create_run_step(
            run_id=run.id,
            parent_step_id=parent_step.id,
            agent_id="frontend",
            status="pending",
            title="Task 01: Implement React login component",
            input="Build login form with validation",
        ),
        isolated_db.create_run_step(
            run_id=run.id,
            parent_step_id=parent_step.id,
            agent_id="backend",
            status="pending",
            title="Task 02: Create FastAPI authentication endpoint",
            input="Add POST /api/auth/login with JWT",
        ),
        isolated_db.create_run_step(
            run_id=run.id,
            parent_step_id=parent_step.id,
            agent_id="qa",
            status="pending",
            title="Task 03: Write pytest tests for auth flow",
            input="Unit and integration tests for login endpoint",
        ),
    ]
    return run, parent_step, steps


# ── infer_agent_for_step ────────────────────────────────────────────────────


def test_infer_agent_frontend_keywords():
    assert infer_agent_for_step("Implement React login component", "") == "frontend-developer"
    assert infer_agent_for_step("Build CSS stylesheet", "") == "frontend-developer"
    assert infer_agent_for_step("Create Vue component", "") == "frontend-developer"


def test_infer_agent_backend_keywords():
    assert infer_agent_for_step("Create FastAPI endpoint", "") == "backend-developer"
    assert infer_agent_for_step("Add REST API route for users", "") == "backend-developer"


def test_infer_agent_database_keywords():
    assert infer_agent_for_step("Write database migration", "") == "sql-pro"
    assert infer_agent_for_step("Optimize SQL query for reports", "") == "sql-pro"


def test_infer_agent_test_keywords():
    assert infer_agent_for_step("Write pytest tests for auth", "") == "qa-expert"
    assert infer_agent_for_step("Run e2e test suite", "") == "qa-expert"


def test_infer_agent_error_keywords():
    assert infer_agent_for_step("Fix bug in payment processing", "") == "error-detective"
    assert infer_agent_for_step("Debug crash in worker", "") == "error-detective"


def test_infer_agent_security_keywords():
    assert infer_agent_for_step("Check for SQL injection vulnerability", "") == "security-auditor"
    assert infer_agent_for_step("Review CSRF and XSS exposure", "") == "security-auditor"


def test_infer_agent_docs_keywords():
    assert infer_agent_for_step("Write README for the project", "") == "technical-writer"
    assert infer_agent_for_step("Update documentation for API", "") == "technical-writer"


def test_infer_agent_deploy_keywords():
    assert infer_agent_for_step("Set up CI/CD pipeline", "") == "devops-engineer"
    assert infer_agent_for_step("Write Dockerfile for the app", "") == "devops-engineer"


def test_infer_agent_default_fallback():
    assert infer_agent_for_step("Coordinate team kickoff", "") == "fullstack-developer"
    assert infer_agent_for_step("", "") == "fullstack-developer"


def test_infer_agent_uses_input_text():
    # Title alone doesn't match, but input text does
    assert infer_agent_for_step("Step 01: Complete the task", "implement React component") == "frontend-developer"


# ── infer_task_type_for_step ────────────────────────────────────────────────


def test_infer_task_type_deployment():
    assert infer_task_type_for_step("Set up CI/CD pipeline", "") == "deployment"
    assert infer_task_type_for_step("Write Dockerfile", "") == "deployment"


def test_infer_task_type_test_generation():
    assert infer_task_type_for_step("Write pytest tests for auth", "") == "test_generation"
    assert infer_task_type_for_step("Run e2e verification suite", "") == "test_generation"


def test_infer_task_type_security_review():
    assert infer_task_type_for_step("Check for SQL injection vulnerability", "") == "security_review"
    assert infer_task_type_for_step("Review CSRF exposure and XSS vulnerabilities", "") == "security_review"


def test_infer_task_type_debugging():
    assert infer_task_type_for_step("Fix bug in payment processing", "") == "debugging"
    assert infer_task_type_for_step("Debug crash in worker", "") == "debugging"


def test_infer_task_type_documentation():
    assert infer_task_type_for_step("Write README for the project", "") == "documentation"
    assert infer_task_type_for_step("Update API documentation", "") == "documentation"


def test_infer_task_type_implementation_fallback():
    # Generic step → falls back to agent default or "implementation"
    result = infer_task_type_for_step("Build login form", "", agent_id="frontend-developer")
    assert result == "implementation"


def test_infer_task_type_agent_default_used():
    # When no keyword matches, agent default is used
    result = infer_task_type_for_step("Random uncategorized task", "", agent_id="security-auditor")
    assert result == "security_review"


# ── database: upsert_step_route_decision ────────────────────────────────────


def test_upsert_step_route_decision_creates_new(isolated_db):
    run = isolated_db.create_run(prompt="step route test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task 01"
    )

    decision = isolated_db.upsert_step_route_decision(
        run_id=run.id,
        step_id=step.id,
        agent_id="backend-developer",
        task_type="implementation",
        model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b",
        selected_provider="local_ollama",
        reason="test",
        confidence=0.9,
    )

    assert decision.step_id == step.id
    assert decision.agent_id == "backend-developer"
    assert decision.selected_model == "qwen2.5-coder:7b"


def test_upsert_step_route_decision_updates_existing(isolated_db):
    run = isolated_db.create_run(prompt="step route update test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task 01"
    )

    first = isolated_db.upsert_step_route_decision(
        run_id=run.id,
        step_id=step.id,
        agent_id="backend-developer",
        task_type="implementation",
        model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b",
        selected_provider="local_ollama",
        reason="first",
        confidence=0.9,
    )
    second = isolated_db.upsert_step_route_decision(
        run_id=run.id,
        step_id=step.id,
        agent_id="backend-developer",
        task_type="implementation",
        model_profile="coding_heavy",
        selected_model="qwen3-coder:30b",
        selected_provider="local_ollama",
        reason="updated",
        confidence=0.95,
    )

    assert first.id == second.id  # same record updated, not new one created
    assert second.selected_model == "qwen3-coder:30b"


def test_same_agent_different_steps_no_collision(isolated_db):
    """Same agent handling two steps of same task_type must NOT collide."""
    run = isolated_db.create_run(prompt="no collision test")
    step_a = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task A"
    )
    step_b = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task B"
    )

    isolated_db.upsert_step_route_decision(
        run_id=run.id, step_id=step_a.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b", selected_provider="local_ollama",
        reason="a", confidence=0.9,
    )
    isolated_db.upsert_step_route_decision(
        run_id=run.id, step_id=step_b.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen3-coder:30b", selected_provider="local_ollama",
        reason="b", confidence=0.85,
    )

    all_decisions = isolated_db.list_model_route_decisions_for_steps(run.id)
    assert len(all_decisions) == 2  # both records exist independently


def test_list_model_route_decisions_for_steps_excludes_agent_level(isolated_db):
    run = isolated_db.create_run(prompt="scope test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task 01"
    )

    # Agent-level decision (step_id=None)
    isolated_db.upsert_model_route_decision(
        run_id=run.id, step_id=None, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b", selected_provider="local_ollama",
        reason="agent-level", confidence=0.9,
    )
    # Step-level decision
    isolated_db.upsert_step_route_decision(
        run_id=run.id, step_id=step.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen3-coder:30b", selected_provider="local_ollama",
        reason="step-level", confidence=0.85,
    )

    step_decisions = isolated_db.list_model_route_decisions_for_steps(run.id)
    agent_decisions = isolated_db.list_model_route_decisions_for_agents(run.id)

    assert len(step_decisions) == 1
    assert step_decisions[0].step_id == step.id
    assert len(agent_decisions) == 1
    assert agent_decisions[0].step_id is None


def test_get_model_route_decision_for_step(isolated_db):
    run = isolated_db.create_run(prompt="get by step test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending", title="Task 01"
    )

    isolated_db.upsert_step_route_decision(
        run_id=run.id, step_id=step.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b", selected_provider="local_ollama",
        reason="lookup test", confidence=0.9,
    )

    found = isolated_db.get_model_route_decision_for_step(step.id)
    assert found is not None
    assert found.step_id == step.id

    not_found = isolated_db.get_model_route_decision_for_step("nonexistent-step-id")
    assert not_found is None


# ── routes: step-level preview / persist endpoints ──────────────────────────


@pytest.mark.asyncio
async def test_step_preview_no_staged_steps(isolated_db):
    run = isolated_db.create_run(prompt="no staged steps")

    response = await routes.preview_step_model_routes(run.id)

    assert response.persisted is False
    assert response.count == 0
    assert "no staged steps" in response.warnings[0].lower()


@pytest.mark.asyncio
async def test_step_preview_does_not_persist(isolated_db, run_with_staged_steps, monkeypatch):
    run, _parent, _steps = run_with_staged_steps

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b", "qwen3:8b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    response = await routes.preview_step_model_routes(run.id)

    assert response.persisted is False
    assert response.count == 3
    # Nothing written to DB
    assert isolated_db.list_model_route_decisions_for_steps(run.id) == []


@pytest.mark.asyncio
async def test_step_persist_saves_decisions(isolated_db, run_with_staged_steps, monkeypatch):
    run, _parent, steps = run_with_staged_steps

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b", "qwen3:8b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    response = await routes.persist_step_model_routes(run.id)
    listed = isolated_db.list_model_route_decisions_for_steps(run.id)

    assert response.persisted is True
    assert response.count == 3
    assert len(listed) == 3
    step_ids_persisted = {d.step_id for d in listed}
    assert step_ids_persisted == {s.id for s in steps}


@pytest.mark.asyncio
async def test_repeated_step_persist_updates_not_duplicates(isolated_db, run_with_staged_steps, monkeypatch):
    run, _parent, steps = run_with_staged_steps

    async def first_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b", "deepseek-r1:14b"]

    async def second_models(_base_url: str) -> list[str]:
        return ["qwen3-coder:30b", "deepseek-r1:14b"]

    monkeypatch.setattr(routes.ollama, "list_models", first_models)
    await routes.persist_step_model_routes(run.id)

    monkeypatch.setattr(routes.ollama, "list_models", second_models)
    await routes.persist_step_model_routes(run.id)

    listed = isolated_db.list_model_route_decisions_for_steps(run.id)
    assert len(listed) == 3  # no duplicates


@pytest.mark.asyncio
async def test_get_model_routes_scope_filtering(isolated_db, run_with_staged_steps, monkeypatch):
    run, _parent, _steps = run_with_staged_steps
    isolated_db.replace_run_agent_assignments(
        run.id,
        [{"agent_id": "backend-developer", "assigned_role": "implementation", "reason": "test", "confidence": 0.9}],
    )

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    # Persist agent-level decisions
    await routes.persist_run_model_routes(run.id)
    # Persist step-level decisions
    await routes.persist_step_model_routes(run.id)

    all_decisions = isolated_db.get_model_route_decisions_for_run(run.id)
    agent_only = isolated_db.list_model_route_decisions_for_agents(run.id)
    steps_only = isolated_db.list_model_route_decisions_for_steps(run.id)

    assert len(all_decisions) > len(agent_only)
    assert len(all_decisions) > len(steps_only)
    assert all(d.step_id is None for d in agent_only)
    assert all(d.step_id is not None for d in steps_only)


# ── execution: per-step model is used ───────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_uses_per_step_model(isolated_db, monkeypatch):
    """_execute_staged_steps must use the model from step_route_decisions."""
    from src.models import RunStep, RunStatus

    captured_models: list[str] = []

    async def capturing_chat(prompt, system, model, base_url):
        captured_models.append(model)
        return f"Output for model {model}"

    monkeypatch.setattr(engine.ollama, "chat_completion", capturing_chat)

    run = isolated_db.create_run(prompt="per step model test")
    step_a = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="frontend", status="pending",
        title="Task A: Build React page", input="build login page",
    )
    step_b = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task B: Create API endpoint", input="add REST endpoint",
    )

    from src.models import ModelRouteDecision, ProviderMode
    from src.model_router import LOCAL_OLLAMA

    route_a = ModelRouteDecision(
        run_id=run.id, step_id=step_a.id, agent_id="frontend-developer",
        task_type="implementation", model_profile="coding_fast",
        selected_model="qwen2.5-coder:7b", selected_provider=LOCAL_OLLAMA,
        fallback_model="qwen2.5-coder:7b", provider_mode=ProviderMode.LOCAL,
        reason="test", confidence=0.9,
    )
    route_b = ModelRouteDecision(
        run_id=run.id, step_id=step_b.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen3-coder:30b", selected_provider=LOCAL_OLLAMA,
        fallback_model="qwen2.5-coder:7b", provider_mode=ProviderMode.LOCAL,
        reason="test", confidence=0.92,
    )
    step_route_decisions = {step_a.id: route_a, step_b.id: route_b}

    await engine._execute_staged_steps(
        staged_steps=[step_a, step_b],
        run_id=run.id,
        instructions="",
        product_spec="",
        plan_text="",
        architecture_text="",
        task_breakdown="",
        project_stack="React FastAPI",
        ollama_model="default-model",
        ollama_base_url="http://localhost:11434",
        log_fn=lambda _: None,
        step_route_decisions=step_route_decisions,
    )

    assert "qwen2.5-coder:7b" in captured_models
    assert "qwen3-coder:30b" in captured_models
    assert "default-model" not in captured_models


@pytest.mark.asyncio
async def test_external_provider_falls_back_to_local(isolated_db, monkeypatch):
    """Steps routed to an external provider must fall back to local_ollama."""
    from src.models import ModelRouteDecision, ProviderMode, RunStep

    captured_models: list[str] = []

    async def capturing_chat(prompt, system, model, base_url):
        captured_models.append(model)
        return "Output"

    monkeypatch.setattr(engine.ollama, "chat_completion", capturing_chat)

    run = isolated_db.create_run(prompt="external fallback test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task 01: Build backend API", input="create endpoint",
    )

    external_route = ModelRouteDecision(
        run_id=run.id, step_id=step.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="claude-code:sonnet", selected_provider="claude_code",
        fallback_model="qwen2.5-coder:7b", provider_mode=ProviderMode.HYBRID,
        reason="hybrid routing", confidence=0.74,
    )

    await engine._execute_staged_steps(
        staged_steps=[step],
        run_id=run.id,
        instructions="",
        product_spec="",
        plan_text="",
        architecture_text="",
        task_breakdown="",
        project_stack="",
        ollama_model="global-default",
        ollama_base_url="http://localhost:11434",
        log_fn=lambda _: None,
        step_route_decisions={step.id: external_route},
    )

    # Must use fallback model, NOT the external one
    assert "qwen2.5-coder:7b" in captured_models
    assert "claude-code:sonnet" not in captured_models
    assert "global-default" not in captured_models


@pytest.mark.asyncio
async def test_execution_without_route_decisions_uses_default_model(isolated_db, monkeypatch):
    """When no step_route_decisions are provided, the run-level Ollama model is used."""
    captured_models: list[str] = []

    async def capturing_chat(prompt, system, model, base_url):
        captured_models.append(model)
        return "Output"

    monkeypatch.setattr(engine.ollama, "chat_completion", capturing_chat)

    run = isolated_db.create_run(prompt="no route test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task 01: Do something", input="do it",
    )

    await engine._execute_staged_steps(
        staged_steps=[step],
        run_id=run.id,
        instructions="",
        product_spec="",
        plan_text="",
        architecture_text="",
        task_breakdown="",
        project_stack="",
        ollama_model="default-model",
        ollama_base_url="http://localhost:11434",
        log_fn=lambda _: None,
        # step_route_decisions intentionally omitted
    )

    assert captured_models == ["default-model"]


# ── Additional stability tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_step_route_failure_emits_warning_does_not_crash(isolated_db, monkeypatch):
    """When _persist_step_route_decisions fails per-step, warnings are returned
    and logged — but the run itself must not crash and must fall back gracefully."""
    collected_logs: list[str] = []

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b"]

    # Force route_model to raise for every step
    def broken_route_model(*_args, **_kwargs):
        raise RuntimeError("router exploded")

    monkeypatch.setattr(engine.ollama, "list_models", fake_list_models)
    monkeypatch.setattr("src.orchestrator.engine.route_model", broken_route_model)

    run = isolated_db.create_run(prompt="step route failure test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task 01: Build API endpoint", input="create endpoint",
    )

    step_routes, warnings = await engine._persist_step_route_decisions(
        run_id=run.id,
        staged_steps=[step],
        provider_mode="local",
        ollama_base_url="http://localhost:11434",
        log_fn=lambda msg: collected_logs.append(msg),
    )

    # Failure must produce a warning, not crash
    assert step_routes == {}  # no decision saved
    assert len(warnings) == 1
    assert "router exploded" in warnings[0]
    # Warning must also have been passed to log_fn
    assert any("WARNING" in log for log in collected_logs)


def test_delete_step_route_decisions_preserves_agent_level(isolated_db):
    """delete_step_route_decisions_for_run removes step decisions but keeps agent-level ones."""
    run = isolated_db.create_run(prompt="delete step routes test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task 01", input="",
    )

    # Agent-level decision (step_id=None)
    isolated_db.upsert_model_route_decision(
        run_id=run.id, step_id=None, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen2.5-coder:7b", selected_provider="local_ollama",
        reason="agent-level", confidence=0.9,
    )
    # Step-level decision
    isolated_db.upsert_step_route_decision(
        run_id=run.id, step_id=step.id, agent_id="backend-developer",
        task_type="implementation", model_profile="coding_heavy",
        selected_model="qwen3-coder:30b", selected_provider="local_ollama",
        reason="step-level", confidence=0.85,
    )

    deleted = isolated_db.delete_step_route_decisions_for_run(run.id)
    assert deleted == 1

    # Agent-level decision must survive
    agent_decisions = isolated_db.list_model_route_decisions_for_agents(run.id)
    assert len(agent_decisions) == 1

    # Step-level decisions must be gone
    step_decisions = isolated_db.list_model_route_decisions_for_steps(run.id)
    assert step_decisions == []


@pytest.mark.asyncio
async def test_repeated_step_persist_no_duplicates_count(isolated_db, run_with_staged_steps, monkeypatch):
    """Persisting step routes three times must not increase the record count."""
    run, _parent, _steps = run_with_staged_steps

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    await routes.persist_step_model_routes(run.id)
    await routes.persist_step_model_routes(run.id)
    await routes.persist_step_model_routes(run.id)

    listed = isolated_db.list_model_route_decisions_for_steps(run.id)
    # Exactly 3 steps → exactly 3 decisions, no duplicates
    assert len(listed) == 3


@pytest.mark.asyncio
async def test_step_route_fallback_to_run_default_when_no_decisions(isolated_db, monkeypatch):
    """_execute_staged_steps with step_route_decisions={} uses the run-level default model."""
    captured_models: list[str] = []

    async def capturing_chat(prompt, system, model, base_url):
        captured_models.append(model)
        return "Output"

    monkeypatch.setattr(engine.ollama, "chat_completion", capturing_chat)

    run = isolated_db.create_run(prompt="empty routes fallback test")
    step = isolated_db.create_run_step(
        run_id=run.id, parent_step_id="", agent_id="backend", status="pending",
        title="Task 01: Do something", input="do it",
    )

    await engine._execute_staged_steps(
        staged_steps=[step],
        run_id=run.id,
        instructions="",
        product_spec="",
        plan_text="",
        architecture_text="",
        task_breakdown="",
        project_stack="",
        ollama_model="run-level-model",
        ollama_base_url="http://localhost:11434",
        log_fn=lambda _: None,
        step_route_decisions={},  # explicitly empty, not None
    )

    assert captured_models == ["run-level-model"]


@pytest.mark.asyncio
async def test_scope_all_returns_both_agent_and_step_decisions(isolated_db, run_with_staged_steps, monkeypatch):
    """GET ?scope=all returns agent-level + step-level; no duplicates."""
    run, _parent, _steps = run_with_staged_steps
    isolated_db.replace_run_agent_assignments(
        run.id,
        [{"agent_id": "backend-developer", "assigned_role": "implementation",
          "reason": "test", "confidence": 0.9}],
    )

    async def fake_list_models(_base_url: str) -> list[str]:
        return ["qwen2.5-coder:7b"]

    monkeypatch.setattr(routes.ollama, "list_models", fake_list_models)

    await routes.persist_run_model_routes(run.id)      # agent-level
    await routes.persist_step_model_routes(run.id)     # step-level

    all_decisions = isolated_db.get_model_route_decisions_for_run(run.id)
    agent_only = isolated_db.list_model_route_decisions_for_agents(run.id)
    steps_only = isolated_db.list_model_route_decisions_for_steps(run.id)

    # all = agents + steps, no overlap
    assert len(all_decisions) == len(agent_only) + len(steps_only)
    # All step decisions have step_id, all agent decisions don't
    assert all(d.step_id is None for d in agent_only)
    assert all(d.step_id is not None for d in steps_only)


# ── Orchestrator Tool Planning v1 ─────────────────────────────────────────────


def _make_step(title: str, agent_id: str = "", input_text: str = "") -> RunStep:
    """Helper: build an in-memory RunStep for infer_tools_for_step tests."""
    return RunStep(id="step-test", run_id="run-test", title=title, agent_id=agent_id, input=input_text)


def test_implementation_step_recommends_read_search_propose_apply_git():
    rec = infer_tools_for_step(_make_step("Implement login endpoint", agent_id="backend-developer"))
    assert "read-file" in rec.recommended_tools
    assert "search-code" in rec.recommended_tools
    assert "propose-patch" in rec.recommended_tools
    assert "apply-patch" in rec.recommended_tools
    assert "git-diff" in rec.recommended_tools
    assert rec.task_type == "implementation"
    assert rec.confidence >= 0.8


def test_debugging_step_recommends_run_command_and_analyze():
    rec = infer_tools_for_step(_make_step("Debug authentication failure", agent_id="error-detective"))
    assert "run-command" in rec.recommended_tools
    assert "analyze-command-result" in rec.recommended_tools
    assert rec.task_type == "debugging"


def test_documentation_step_recommends_propose_patch():
    rec = infer_tools_for_step(_make_step("Write API docs", agent_id="technical-writer"))
    assert "propose-patch" in rec.recommended_tools
    assert "read-file" in rec.recommended_tools
    assert rec.task_type == "documentation"


def test_security_review_step_does_not_recommend_apply_patch():
    rec = infer_tools_for_step(_make_step("Security audit of auth module", agent_id="security-auditor"))
    assert "apply-patch" not in rec.recommended_tools
    assert "git-diff" in rec.recommended_tools
    assert rec.task_type == "security_review"


@pytest.mark.asyncio
async def test_tool_plan_endpoint_returns_recommendations(isolated_db, run_with_staged_steps):
    """GET /api/runs/{run_id}/steps/tool-plan returns a recommendation per step."""
    run, _parent, steps = run_with_staged_steps

    result = await routes.get_run_step_tool_plan(run.id)

    # One recommendation per step (including parent)
    step_ids_in_plan = {r.step_id for r in result.recommendations}
    for step in steps:
        assert step.id in step_ids_in_plan
    assert len(result.recommendations) >= len(steps)
    assert result.run_id == run.id
    assert "No tools are executed automatically" in result.summary


@pytest.mark.asyncio
async def test_tool_plan_endpoint_does_not_create_tool_calls(isolated_db, run_with_staged_steps):
    """GET /api/runs/{run_id}/steps/tool-plan must not write any ToolCall records."""
    run, _parent, _steps = run_with_staged_steps
    calls_before = isolated_db.list_tool_calls_for_run(run.id)

    await routes.get_run_step_tool_plan(run.id)

    calls_after = isolated_db.list_tool_calls_for_run(run.id)
    assert len(calls_before) == len(calls_after)


@pytest.mark.asyncio
async def test_tool_plan_endpoint_does_not_modify_files(isolated_db, run_with_staged_steps):
    """GET /api/runs/{run_id}/steps/tool-plan must not create any new project files."""
    run, _parent, _steps = run_with_staged_steps
    project = isolated_db.get_project(run.project_id)
    from pathlib import Path
    project_dir = Path(project.path)
    files_before = set(project_dir.iterdir())

    await routes.get_run_step_tool_plan(run.id)

    assert set(project_dir.iterdir()) == files_before


@pytest.mark.asyncio
async def test_tool_plan_missing_route_decisions_returns_fallback(isolated_db, tmp_path):
    """Even without any route decisions, the endpoint returns a valid plan."""
    project_dir = tmp_path / "bare-project"
    project_dir.mkdir()
    project = isolated_db.create_project(name="Bare", path=str(project_dir))
    run = isolated_db.create_run(prompt="simple task", project_id=project.id, project_path=project.path)
    isolated_db.create_run_step(
        run_id=run.id,
        title="Implement feature X",
        agent_id="backend-developer",
    )

    result = await routes.get_run_step_tool_plan(run.id)

    assert len(result.recommendations) == 1
    rec = result.recommendations[0]
    assert "read-file" in rec.recommended_tools
    assert rec.task_type  # non-empty fallback


# ── Orchestrator Guided Execution v1 ──────────────────────────────────────────


def _impl_step() -> RunStep:
    return RunStep(id="s1", run_id="r1", title="Implement feature", agent_id="backend-developer")


def _make_tool_call(
    tool_name: str,
    step_id: str = "s1",
    run_id: str = "r1",
    status: str = "completed",
    returncode: int | None = None,
    output_json: str = "{}",
    started_at: str = "2026-01-01T00:00:00",
) -> ToolCall:
    return ToolCall(
        id=f"tc-{tool_name}-{step_id}",
        run_id=run_id,
        step_id=step_id,
        tool_name=tool_name,
        status=status,
        returncode=returncode,
        output_json=output_json,
        started_at=started_at,
    )


def _tool_plan(step: RunStep, task_type: str = "implementation") -> "StepToolRecommendation":
    from src.model_router import infer_tools_for_step
    return infer_tools_for_step(step, task_type=task_type)

# Re-use import alias
from src.models import StepToolRecommendation  # noqa: E402


def test_guided_recommends_search_when_no_tool_calls():
    step = _impl_step()
    plan = build_guided_step_actions(step, _tool_plan(step), [])
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "search_code"
    assert "no read/search" in plan.status_summary


def test_guided_recommends_propose_patch_after_search():
    step = _impl_step()
    calls = [_make_tool_call("search-code")]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "propose_patch"
    assert "patch not yet proposed" in plan.status_summary


def test_guided_recommends_apply_patch_after_completed_propose():
    step = _impl_step()
    calls = [
        _make_tool_call("search-code"),
        _make_tool_call("propose-patch"),
    ]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "apply_patch"
    assert plan.recommended_next_action.requires_confirmation is True
    assert plan.recommended_next_action.risk_level == "high"


def test_guided_recommends_run_tests_after_apply():
    step = _impl_step()
    calls = [
        _make_tool_call("search-code"),
        _make_tool_call("propose-patch"),
        _make_tool_call("apply-patch", returncode=0),
    ]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "run_tests"
    assert "patch applied" in plan.status_summary


def test_guided_recommends_analyze_after_failed_command():
    step = _impl_step()
    calls = [
        _make_tool_call("search-code"),
        _make_tool_call("propose-patch"),
        _make_tool_call("apply-patch", returncode=0),
        _make_tool_call("run-command", returncode=1),
    ]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "analyze_result"
    assert "analysis pending" in plan.status_summary


def test_guided_recommends_propose_patch_after_analysis_with_issues():
    step = _impl_step()
    analysis_output = '{"issues": [{"kind": "test_failure", "message": "AssertionError"}]}'
    calls = [
        _make_tool_call("search-code"),
        _make_tool_call("propose-patch"),
        _make_tool_call("apply-patch", returncode=0),
        _make_tool_call("run-command", returncode=1),
        _make_tool_call("analyze-command-result", output_json=analysis_output),
    ]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "propose_patch"
    assert "issues found" in plan.status_summary


def test_guided_recommends_done_or_review_diff_after_passing_command():
    step = _impl_step()
    calls = [
        _make_tool_call("search-code"),
        _make_tool_call("propose-patch"),
        _make_tool_call("apply-patch", returncode=0),
        _make_tool_call("run-command", returncode=0, output_json='{"timed_out": false}'),
    ]
    plan = build_guided_step_actions(step, _tool_plan(step), calls)
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type in ("review_diff", "done")
    assert "tests passing" in plan.status_summary


@pytest.mark.asyncio
async def test_guided_endpoint_does_not_create_tool_calls(isolated_db, run_with_staged_steps):
    """GET /api/runs/{run_id}/guided-execution-plan must not create any ToolCall records."""
    run, _parent, _steps = run_with_staged_steps
    calls_before = isolated_db.list_tool_calls_for_run(run.id)

    await routes.get_run_guided_execution_plan(run.id)

    calls_after = isolated_db.list_tool_calls_for_run(run.id)
    assert len(calls_before) == len(calls_after)


@pytest.mark.asyncio
async def test_guided_endpoint_does_not_modify_files(isolated_db, run_with_staged_steps):
    """GET /api/runs/{run_id}/guided-execution-plan must not touch project files."""
    run, _parent, _steps = run_with_staged_steps
    project = isolated_db.get_project(run.project_id)
    from pathlib import Path
    project_dir = Path(project.path)
    files_before = set(project_dir.iterdir())

    await routes.get_run_guided_execution_plan(run.id)

    assert set(project_dir.iterdir()) == files_before


@pytest.mark.asyncio
async def test_guided_endpoint_works_without_route_decisions(isolated_db, tmp_path):
    """Guided plan endpoint returns valid results even with no route decisions."""
    project_dir = tmp_path / "guided-bare"
    project_dir.mkdir()
    project = isolated_db.create_project(name="GuidedBare", path=str(project_dir))
    run = isolated_db.create_run(prompt="fix bug", project_id=project.id, project_path=project.path)
    isolated_db.create_run_step(
        run_id=run.id,
        title="Debug the failing tests",
        agent_id="error-detective",
    )

    result = await routes.get_run_guided_execution_plan(run.id)

    assert result.run_id == run.id
    assert len(result.steps) == 1
    step_plan = result.steps[0]
    assert step_plan.recommended_next_action is not None
    # No calls → should recommend search/read
    assert step_plan.recommended_next_action.action_type in ("search_code", "read_context")

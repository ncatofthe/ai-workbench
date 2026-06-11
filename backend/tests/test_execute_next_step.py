from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api import routes
from src.models import ExecuteNextStepRequest, RunStatus
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


def make_run_with_pending_step(isolated_db, tmp_path: Path):
    run = isolated_db.create_run(prompt="Build a tiny todo app", project_id="project-1", project_path="/tmp/project-1")
    run_dir = tmp_path / "run-dir"
    run_dir.mkdir()
    isolated_db.update_run(run.id, run_dir=str(run_dir), artifacts=[])
    parent = isolated_db.create_run_step(
        run_id=run.id,
        title="Stage executable task steps",
        agent_id="orchestrator",
        status=RunStatus.COMPLETED.value,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        parent_step_id=parent.id,
        title="Task 01: Implement todo list UI",
        agent_id="frontend",
        status=RunStatus.PENDING.value,
        input="Create a simple todo list interface. Do not mutate files directly.",
    )
    return isolated_db.get_run(run.id), run_dir, step


@pytest.mark.asyncio
async def test_execute_next_step_runs_agent_harness_and_completes_step(isolated_db, tmp_path):
    run, run_dir, step = make_run_with_pending_step(isolated_db, tmp_path)
    assert run is not None

    result = await routes.execute_next_run_step(run.id, ExecuteNextStepRequest(mode="mock"))

    assert result.status == "completed"
    assert result.step_id == step.id
    assert result.execution.agent_id == "frontend-developer"
    assert result.execution.result is not None
    assert result.artifact == f"agent-execution-{step.id}.md"
    assert (run_dir / result.artifact).exists()
    assert "Agent Execution Result" in (run_dir / result.artifact).read_text(encoding="utf-8")

    stored_run = isolated_db.get_run(run.id)
    assert stored_run is not None
    assert stored_run.current_step_id == ""
    assert result.artifact in stored_run.artifacts
    assert "Executed next step" in stored_run.logs[-1]

    stored_steps = isolated_db.list_run_steps(run.id)
    stored_step = next(item for item in stored_steps if item.id == step.id)
    assert stored_step.status == "completed"
    assert "Agent: frontend-developer" in stored_step.output

    calls = isolated_db.list_tool_calls_for_step(step.id)
    assert len(calls) == 1
    assert calls[0].tool_name == "agent-execution"


@pytest.mark.asyncio
async def test_execute_next_step_requires_pending_step(isolated_db):
    run = isolated_db.create_run(prompt="Nothing pending")

    with pytest.raises(HTTPException) as exc:
        await routes.execute_next_run_step(run.id, ExecuteNextStepRequest(mode="mock"))

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_execute_next_step_dry_run_keeps_step_pending(isolated_db, tmp_path):
    run, _run_dir, step = make_run_with_pending_step(isolated_db, tmp_path)
    assert run is not None

    result = await routes.execute_next_run_step(run.id, ExecuteNextStepRequest(mode="dry_run"))

    assert result.status == "planned"
    assert result.execution.executed is False
    assert result.execution.provider_called is False

    stored_run = isolated_db.get_run(run.id)
    assert stored_run is not None
    assert stored_run.current_step_id == ""

    stored_step = next(item for item in isolated_db.list_run_steps(run.id) if item.id == step.id)
    assert stored_step.status == "pending"
    assert "Agent execution status: planned" in stored_step.output

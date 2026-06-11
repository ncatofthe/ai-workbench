from __future__ import annotations

import pytest

from src.orchestrator import engine
from src.storage import database
from src.utils.paths import resolve_runtime_path


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.mark.asyncio
async def test_orchestrator_records_visible_run_steps(isolated_db, monkeypatch):
    async def offline_ollama(_base_url: str) -> bool:
        return False

    monkeypatch.setattr(engine.ollama, "check_health", offline_ollama)

    run = isolated_db.create_run(
        prompt="Create a small implementation plan",
        mode="offline",
        project_id="project-1",
        project_path="/tmp/project-1",
    )

    await engine.execute_run(
        run_id=run.id,
        prompt=run.prompt,
        mode=run.mode.value,
        run_dir=run.run_dir,
        project_id=run.project_id,
        project_name="Demo",
        project_path=run.project_path,
        project_stack="python",
    )

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.status.value == "completed"
    assert stored.current_step_id == ""

    steps = isolated_db.list_run_steps(run.id)
    titles = [step.title for step in steps]
    assert titles[:10] == [
        "Initialize run",
        "Capture task input",
        "Load orchestrator instructions",
        "Analyze product requirements",
        "Save requirements artifacts",
        "Create execution plan",
        "Save plan artifact",
        "Generate architecture artifact",
        "Generate task breakdown artifact",
        "Stage executable task steps",
    ]
    assert titles[-2:] == [
        "Generate final report",
        "Finalize run",
    ]
    executable_steps = [step for step in steps if step.title.startswith("Task ")]
    pipeline_steps = [step for step in steps if not step.title.startswith("Task ")]
    assert len(executable_steps) == 6
    assert all(step.status == "pending" for step in executable_steps)
    assert all(step.parent_step_id == steps[9].id for step in executable_steps)
    assert executable_steps[0].agent_id == "repo_analyst"
    assert any(step.agent_id == "qa" for step in executable_steps)
    assert "Created 6 pending execution steps" in steps[9].output
    assert all(step.status == "completed" for step in pipeline_steps)
    assert all(step.started_at for step in pipeline_steps)
    assert all(step.finished_at for step in pipeline_steps)
    assert "Product Goal" in steps[3].output
    assert "Fallback Plan" in steps[5].output

    run_path = resolve_runtime_path(run.run_dir, "runs")
    assert (run_path / "product-spec.md").exists()
    assert (run_path / "clarification-questions.md").exists()
    assert (run_path / "architecture.md").exists()
    assert (run_path / "tasks.md").exists()
    assert "Product Goal" in (run_path / "product-spec.md").read_text(encoding="utf-8")
    assert "target audience" in (run_path / "clarification-questions.md").read_text(encoding="utf-8")
    assert "System Overview" in (run_path / "architecture.md").read_text(encoding="utf-8")
    assert "Milestones" in (run_path / "tasks.md").read_text(encoding="utf-8")

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.artifacts == [
        "input.md",
        "product-spec.md",
        "clarification-questions.md",
        "plan.md",
        "architecture.md",
        "tasks.md",
        "final-report.md",
    ]

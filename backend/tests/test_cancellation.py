from __future__ import annotations

import asyncio

import pytest

from src.api import routes
from src.models import RunStatus
from src.orchestrator import cancellation, engine
from src.storage import database


@pytest.fixture(autouse=True)
def clear_task_registry():
    cancellation.clear_run_tasks()
    yield
    cancellation.clear_run_tasks()


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.mark.asyncio
async def test_stop_run_cancels_registered_background_task(isolated_db):
    run = isolated_db.create_run(prompt="Long run")
    isolated_db.update_run(run.id, status=RunStatus.RUNNING.value)
    started = asyncio.Event()

    async def sleeper():
        started.set()
        await asyncio.sleep(60)

    task = asyncio.create_task(sleeper())
    cancellation.register_run_task(run.id, task)
    await started.wait()

    response = await routes.stop_run(run.id)

    assert response == {"status": "stopped", "run_id": run.id, "task_cancelled": True}
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not cancellation.is_run_task_active(run.id)

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.status.value == "stopped"
    assert stored.finished_at is not None


@pytest.mark.asyncio
async def test_orchestrator_marks_run_stopped_when_cancelled(isolated_db, monkeypatch):
    entered_requirements = asyncio.Event()

    async def hanging_health(_base_url: str) -> bool:
        entered_requirements.set()
        await asyncio.sleep(60)
        return True

    monkeypatch.setattr(engine.ollama, "check_health", hanging_health)
    run = isolated_db.create_run(prompt="Cancel during planning")

    task = asyncio.create_task(
        engine.execute_run(
            run_id=run.id,
            prompt=run.prompt,
            mode=run.mode.value,
            run_dir=run.run_dir,
        )
    )
    await asyncio.wait_for(entered_requirements.wait(), timeout=1)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.status.value == "stopped"
    assert stored.current_step_id == ""
    assert stored.result == "Run stopped by user."

    steps = isolated_db.list_run_steps(run.id)
    requirements_step = next(step for step in steps if step.title == "Analyze product requirements")
    assert requirements_step.status == "stopped"
    assert requirements_step.error == "Run was cancelled by user."
    assert requirements_step.finished_at

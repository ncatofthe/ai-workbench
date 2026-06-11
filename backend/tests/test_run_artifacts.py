from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api import routes
from src.models import ClarificationAnswerRequest
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


def make_run_with_dir(isolated_db, tmp_path: Path):
    run = isolated_db.create_run(prompt="Need a product spec")
    run_dir = tmp_path / "run with spaces"
    run_dir.mkdir()
    isolated_db.update_run(run.id, run_dir=str(run_dir), artifacts=["product-spec.md"])
    return isolated_db.get_run(run.id), run_dir


@pytest.mark.asyncio
async def test_get_run_artifact_reads_only_run_file(isolated_db, tmp_path):
    run, run_dir = make_run_with_dir(isolated_db, tmp_path)
    assert run is not None
    (run_dir / "product-spec.md").write_text("# Product Spec\n\nHello", encoding="utf-8")

    artifact = await routes.get_run_artifact(run.id, "product-spec.md")

    assert artifact["name"] == "product-spec.md"
    assert artifact["path"] == "product-spec.md"
    assert "Hello" in artifact["content"]


@pytest.mark.asyncio
async def test_get_run_artifact_rejects_path_escape(isolated_db, tmp_path):
    run, _run_dir = make_run_with_dir(isolated_db, tmp_path)
    assert run is not None

    with pytest.raises(HTTPException) as exc:
        await routes.get_run_artifact(run.id, "../secret.txt")

    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_clarification_answers_create_artifact_and_step(isolated_db, tmp_path):
    run, run_dir = make_run_with_dir(isolated_db, tmp_path)
    assert run is not None

    result = await routes.post_clarification_answers(
        run.id,
        ClarificationAnswerRequest(answers="- Audience: founders\n- First version: landing page builder"),
    )

    answer_file = run_dir / "clarification-answers.md"
    assert answer_file.exists()
    assert "landing page builder" in answer_file.read_text(encoding="utf-8")
    assert result["artifact"] == "clarification-answers.md"
    assert result["step"].title == "Record clarification answers"
    assert result["step"].status == "completed"

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert "clarification-answers.md" in stored.artifacts
    assert "Saved clarification answers" in stored.logs[-1]

    steps = isolated_db.list_run_steps(run.id)
    assert steps[-1].title == "Record clarification answers"


@pytest.mark.asyncio
async def test_regenerate_plan_from_answers_updates_plan_and_timeline(isolated_db, tmp_path, monkeypatch):
    async def offline_ollama(_base_url: str) -> bool:
        return False

    monkeypatch.setattr(routes.ollama, "check_health", offline_ollama)
    run, run_dir = make_run_with_dir(isolated_db, tmp_path)
    assert run is not None
    (run_dir / "product-spec.md").write_text("# Product Spec\n\nBuild a site builder.", encoding="utf-8")
    (run_dir / "clarification-questions.md").write_text(
        "# Clarification Questions\n\n- Who is this for?",
        encoding="utf-8",
    )
    await routes.post_clarification_answers(
        run.id,
        ClarificationAnswerRequest(answers="- Audience: founders\n- Must include templates"),
    )

    result = await routes.post_regenerate_plan(run.id)

    assert result["source"] == "Ollama unavailable; generated fallback regenerated plan."
    assert "Regenerated Plan" in result["plan"]
    assert "System Overview" in result["architecture"]
    assert "Milestones" in result["tasks"]
    assert len(result["staged_steps"]) == 6
    assert "Must include templates" in result["plan"]
    assert (run_dir / "plan.md").exists()
    assert (run_dir / "architecture.md").exists()
    assert (run_dir / "tasks.md").exists()
    assert "Must include templates" in (run_dir / "plan.md").read_text(encoding="utf-8")
    final_report = (run_dir / "final-report.md").read_text(encoding="utf-8")
    assert "Regenerated Plan" in final_report
    assert "Architecture" in final_report
    assert "Tasks" in final_report

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.current_step_id == ""
    assert stored.plan == result["plan"]
    assert "Regenerated plan, architecture, and tasks" in stored.logs[-1]
    assert "architecture.md" in stored.artifacts
    assert "tasks.md" in stored.artifacts

    steps = isolated_db.list_run_steps(run.id)
    regenerate_steps = [step for step in steps if step.title == "Regenerate plan from clarification answers"]
    assert len(regenerate_steps) == 1
    regenerate_step = regenerate_steps[0]
    assert regenerate_step.status == "completed"
    assert "Staged 6 pending execution steps" in regenerate_step.output
    assert "Saved plan.md, architecture.md, tasks.md" in regenerate_step.output
    executable_steps = [step for step in steps if step.parent_step_id == regenerate_step.id]
    assert len(executable_steps) == 6
    assert all(step.status == "pending" for step in executable_steps)


@pytest.mark.asyncio
async def test_regenerate_plan_requires_clarification_answers(isolated_db, tmp_path):
    run, run_dir = make_run_with_dir(isolated_db, tmp_path)
    assert run is not None
    (run_dir / "product-spec.md").write_text("# Product Spec\n\nBuild a site builder.", encoding="utf-8")

    with pytest.raises(HTTPException) as exc:
        await routes.post_regenerate_plan(run.id)

    assert exc.value.status_code == 400

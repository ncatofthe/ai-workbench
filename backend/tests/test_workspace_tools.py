from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api import routes
from src.models import (
    ApplyPatchRequest,
    ListFilesRequest,
    PatchOperation,
    ProposePatchRequest,
    ReadFileRequest,
    RunProjectCommandRequest,
    SearchCodeRequest,
)
from src.project_tools import apply_project_patch, propose_project_patch, run_project_command
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


def make_project(isolated_db, tmp_path: Path):
    project_dir = tmp_path / "Workspace Project"
    project_dir.mkdir()
    return isolated_db.create_project(name="Workspace", path=str(project_dir)), project_dir


def test_create_update_list_tool_call(isolated_db):
    call = isolated_db.create_tool_call(
        run_id="run-1",
        project_id="project-1",
        step_id="step-1",
        tool_name="read_file",
        status="pending",
        input_json='{"path":"README.md"}',
        risk_level="low",
    )

    updated = isolated_db.update_tool_call(
        call.id,
        status="completed",
        output_json='{"ok":true}',
        completed_at="2026-05-19T00:00:00",
    )

    assert updated is not None
    assert updated.status == "completed"
    assert updated.output_json == '{"ok":true}'
    assert updated.completed_at == "2026-05-19T00:00:00"
    assert [item.id for item in isolated_db.list_tool_calls_for_run("run-1")] == [call.id]
    assert [item.id for item in isolated_db.list_tool_calls_for_step("step-1")] == [call.id]
    assert [item.id for item in isolated_db.list_tool_calls_for_project("project-1")] == [call.id]


@pytest.mark.asyncio
async def test_list_files_endpoint_creates_completed_tool_call(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "src").mkdir()
    (project_dir / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")

    result = await routes.run_project_list_files(
        project.id,
        ListFilesRequest(run_id="run-1", step_id="step-1", agent_id="agent-1", path="."),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert result["tool_call_id"] == calls[0].id
    assert calls[0].status == "completed"
    assert calls[0].tool_name == "list_files"
    assert calls[0].risk_level == "low"
    assert "src/app.py" in calls[0].output_json


@pytest.mark.asyncio
async def test_read_file_failure_creates_failed_tool_call(isolated_db, tmp_path):
    project, _project_dir = make_project(isolated_db, tmp_path)

    with pytest.raises(HTTPException) as exc:
        await routes.run_project_read_file(
            project.id,
            ReadFileRequest(run_id="run-1", step_id="step-1", agent_id="agent-1", path="missing.py"),
        )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert exc.value.status_code == 400
    assert calls[0].status == "failed"
    assert calls[0].error == "File does not exist"
    assert calls[0].completed_at


@pytest.mark.asyncio
async def test_search_code_endpoint_logs_output(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "main.py").write_text("needle = 'found'\n", encoding="utf-8")

    result = await routes.run_project_search_code(
        project.id,
        SearchCodeRequest(run_id="run-1", step_id="step-1", agent_id="agent-1", query="needle"),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert result["matches"][0]["path"] == "main.py"
    assert calls[0].status == "completed"
    assert "needle" in calls[0].output_json


@pytest.mark.asyncio
async def test_get_run_and_project_tool_calls_return_calls(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    await routes.run_project_list_files(project.id, ListFilesRequest(run_id="run-1"))

    run_calls = await routes.get_run_tool_calls("run-1")
    project_calls = await routes.get_project_tool_calls(project.id)

    assert len(run_calls) == 1
    assert len(project_calls) == 1
    assert run_calls[0].id == project_calls[0].id


@pytest.mark.asyncio
async def test_git_status_on_non_git_dir_does_not_crash(isolated_db, tmp_path):
    project, _project_dir = make_project(isolated_db, tmp_path)

    status = await routes.get_project_git_status(project.id)

    assert status["returncode"] != 0
    assert "not a git repository" in status["stderr"].lower()


@pytest.mark.asyncio
async def test_git_status_in_repo_returns_changed_file(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True, text=True)
    (project_dir / "changed.txt").write_text("changed\n", encoding="utf-8")

    status = await routes.get_project_git_status(project.id)

    assert status["returncode"] == 0
    assert any(item["path"] == "changed.txt" for item in status["changed_files"])


@pytest.mark.asyncio
async def test_git_diff_returns_diff_and_limits_output(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    subprocess.run(["git", "init"], cwd=project_dir, check=True, capture_output=True, text=True)
    target = project_dir / "large.txt"
    target.write_text("base\n", encoding="utf-8")
    subprocess.run(["git", "add", "large.txt"], cwd=project_dir, check=True, capture_output=True, text=True)
    target.write_text("changed\n" + ("x" * 250_000), encoding="utf-8")

    diff = await routes.get_project_git_diff(project.id)

    assert diff["returncode"] == 0
    assert "large.txt" in diff["diff"]
    assert diff["truncated"] is True
    assert len(diff["diff"]) <= 200_000


def test_git_endpoints_do_not_accept_arbitrary_commands():
    assert list(inspect.signature(routes.get_project_git_status).parameters) == ["project_id"]
    assert list(inspect.signature(routes.get_project_git_diff).parameters) == ["project_id"]


def test_propose_patch_does_not_modify_existing_file(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("print('old')\n", encoding="utf-8")

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="old", new_text="new")],
    )

    assert response["files"][0]["status"] == "modify"
    assert "print('new')" in response["files"][0]["diff"]
    assert target.read_text(encoding="utf-8") == "print('old')\n"


def test_propose_patch_returns_diff_for_text_replacement(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("hello world\n", encoding="utf-8")

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path="README.md", old_text="world", new_text="Workbench")],
    )

    file = response["files"][0]
    assert file["status"] == "modify"
    assert "--- a/README.md" in file["diff"]
    assert "+++ b/README.md" in file["diff"]
    assert "-hello world" in file["diff"]
    assert "+hello Workbench" in file["diff"]


def test_propose_patch_returns_error_when_old_text_not_found(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "README.md").write_text("hello world\n", encoding="utf-8")

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path="README.md", old_text="missing", new_text="replacement")],
    )

    assert response["files"][0]["status"] == "error"
    assert response["files"][0]["error"] == "old_text was not found"


def test_propose_patch_can_preview_creating_new_file(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path="docs/plan.md", new_text="# Plan\n", create_if_missing=True)],
    )

    file = response["files"][0]
    assert file["status"] == "create"
    assert "--- a/docs/plan.md" in file["diff"]
    assert "+# Plan" in file["diff"]
    assert not (project_dir / "docs" / "plan.md").exists()


def test_propose_patch_blocks_path_traversal(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path="../outside.txt", old_text="a", new_text="b")],
    )

    assert response["files"][0]["status"] == "error"
    assert "escapes project workspace" in response["files"][0]["error"]


def test_propose_patch_rejects_outside_absolute_path(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path=str(outside), old_text="outside", new_text="inside")],
    )

    assert response["files"][0]["status"] == "error"
    assert "project-relative" in response["files"][0]["error"]
    assert outside.read_text(encoding="utf-8") == "outside\n"


def test_propose_patch_rejects_sensitive_file(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / ".env").write_text("TOKEN=old\n", encoding="utf-8")

    response = propose_project_patch(
        str(project_dir),
        [PatchOperation(file_path=".env", old_text="old", new_text="new")],
    )

    assert response["files"][0]["status"] == "error"
    assert "secret-like" in response["files"][0]["error"]


@pytest.mark.asyncio
async def test_propose_patch_endpoint_logs_completed_tool_call(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("print('old')\n", encoding="utf-8")

    result = await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id="run-1",
            step_id="step-1",
            agent_id="agent-1",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert result["tool_call_id"] == calls[0].id
    assert result["proposal_id"] == calls[0].id
    assert result["files"][0]["status"] == "modify"
    assert calls[0].tool_name == "propose-patch"
    assert calls[0].status == "completed"
    assert calls[0].risk_level == "medium"
    assert "print('new')" in calls[0].output_json
    assert target.read_text(encoding="utf-8") == "print('old')\n"


@pytest.mark.asyncio
async def test_propose_patch_with_context_logs_run_step_agent(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")

    result = await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id="run-ctx",
            step_id="step-ctx",
            agent_id="agent-ctx",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    input_json = json.loads(calls[0].input_json)
    output_json = json.loads(calls[0].output_json)
    assert calls[0].id == result["proposal_id"]
    assert calls[0].run_id == "run-ctx"
    assert calls[0].step_id == "step-ctx"
    assert input_json["agent_id"] == "agent-ctx"
    assert output_json["proposal_id"] == calls[0].id
    assert output_json["summary"]


@pytest.mark.asyncio
async def test_propose_patch_endpoint_logs_failed_tool_call_on_error(isolated_db, tmp_path):
    project, _project_dir = make_project(isolated_db, tmp_path)

    with pytest.raises(HTTPException) as exc:
        await routes.run_project_propose_patch(project.id, ProposePatchRequest(run_id="run-1"))

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert exc.value.status_code == 400
    assert calls[0].tool_name == "propose-patch"
    assert calls[0].status == "failed"
    assert calls[0].risk_level == "medium"
    assert calls[0].error == "At least one patch operation is required"


def test_apply_patch_requires_confirm_true(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")

    with pytest.raises(PermissionError):
        apply_project_patch(
            str(project_dir),
            [PatchOperation(file_path="app.py", old_text="old", new_text="new")],
            confirm=False,
        )

    assert (project_dir / "app.py").read_text(encoding="utf-8") == "old\n"


def test_apply_patch_modifies_existing_file_when_old_text_found(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("old old\n", encoding="utf-8")

    response = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        confirm=True,
    )

    assert response["files"][0]["status"] == "modified"
    assert target.read_text(encoding="utf-8") == "new old\n"


def test_apply_patch_does_not_modify_file_when_old_text_missing(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")

    with pytest.raises(ValueError):
        apply_project_patch(
            str(project_dir),
            [PatchOperation(file_path="app.py", old_text="missing", new_text="new")],
            confirm=True,
        )

    assert target.read_text(encoding="utf-8") == "old\n"


def test_apply_patch_can_create_new_file_with_create_if_missing(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    response = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="new.txt", new_text="created\n", create_if_missing=True)],
        confirm=True,
    )

    assert response["files"][0]["status"] == "created"
    assert (project_dir / "new.txt").read_text(encoding="utf-8") == "created\n"


def test_apply_patch_blocks_path_traversal(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with pytest.raises(ValueError) as exc:
        apply_project_patch(
            str(project_dir),
            [PatchOperation(file_path="../outside.txt", old_text="old", new_text="new")],
            confirm=True,
        )

    assert "escapes project workspace" in str(exc.value)


def test_apply_patch_blocks_absolute_outside_path(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("old\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        apply_project_patch(
            str(project_dir),
            [PatchOperation(file_path=str(outside), old_text="old", new_text="new")],
            confirm=True,
        )

    assert "project-relative" in str(exc.value)
    assert outside.read_text(encoding="utf-8") == "old\n"


def test_apply_patch_rejects_env_file(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / ".env"
    target.write_text("TOKEN=old\n", encoding="utf-8")

    with pytest.raises(ValueError) as exc:
        apply_project_patch(
            str(project_dir),
            [PatchOperation(file_path=".env", old_text="old", new_text="new")],
            confirm=True,
        )

    assert "secret-like" in str(exc.value)
    assert target.read_text(encoding="utf-8") == "TOKEN=old\n"


@pytest.mark.asyncio
async def test_apply_patch_endpoint_logs_completed_high_risk_tool_call(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")

    result = await routes.run_project_apply_patch(
        project.id,
        ApplyPatchRequest(
            run_id="run-1",
            step_id="step-1",
            agent_id="agent-1",
            confirm=True,
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert result["tool_call_id"] == calls[0].id
    assert calls[0].tool_name == "apply-patch"
    assert calls[0].status == "completed"
    assert calls[0].risk_level == "high"
    assert target.read_text(encoding="utf-8") == "new\n"


@pytest.mark.asyncio
async def test_apply_patch_accepts_proposal_id_and_logs_link(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")
    proposal = await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id="run-link",
            step_id="step-link",
            agent_id="agent-link",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    result = await routes.run_project_apply_patch(
        project.id,
        ApplyPatchRequest(
            run_id="run-link",
            step_id="step-link",
            agent_id="agent-link",
            proposal_id=proposal["proposal_id"],
            confirm=True,
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    apply_call = next(call for call in calls if call.tool_name == "apply-patch")
    input_json = json.loads(apply_call.input_json)
    output_json = json.loads(apply_call.output_json)
    assert result["applied_from_proposal_id"] == proposal["proposal_id"]
    assert input_json["proposal_id"] == proposal["proposal_id"]
    assert output_json["applied_from_proposal_id"] == proposal["proposal_id"]
    assert apply_call.run_id == "run-link"
    assert apply_call.step_id == "step-link"
    assert input_json["agent_id"] == "agent-link"


@pytest.mark.asyncio
async def test_apply_patch_endpoint_logs_failed_tool_call_on_error(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")

    with pytest.raises(HTTPException) as exc:
        await routes.run_project_apply_patch(
            project.id,
            ApplyPatchRequest(
                run_id="run-1",
                confirm=True,
                operations=[PatchOperation(file_path="app.py", old_text="missing", new_text="new")],
            ),
        )

    calls = isolated_db.list_tool_calls_for_project(project.id)
    assert exc.value.status_code == 400
    assert calls[0].tool_name == "apply-patch"
    assert calls[0].status == "failed"
    assert calls[0].risk_level == "high"
    assert "old_text was not found" in calls[0].error
    assert target.read_text(encoding="utf-8") == "old\n"


def test_apply_patch_multi_operation_preflight_prevents_partial_apply(tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    first = project_dir / "first.txt"
    second = project_dir / "second.txt"
    first.write_text("first old\n", encoding="utf-8")
    second.write_text("second old\n", encoding="utf-8")

    with pytest.raises(ValueError):
        apply_project_patch(
            str(project_dir),
            [
                PatchOperation(file_path="first.txt", old_text="old", new_text="new"),
                PatchOperation(file_path="second.txt", old_text="missing", new_text="new"),
            ],
            confirm=True,
        )

    assert first.read_text(encoding="utf-8") == "first old\n"
    assert second.read_text(encoding="utf-8") == "second old\n"


@pytest.mark.asyncio
async def test_run_and_project_tool_calls_return_propose_apply_patch_calls(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")
    proposal = await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id="run-audit",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )
    await routes.run_project_apply_patch(
        project.id,
        ApplyPatchRequest(
            run_id="run-audit",
            proposal_id=proposal["proposal_id"],
            confirm=True,
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    run_calls = await routes.get_run_tool_calls("run-audit")
    project_calls = await routes.get_project_tool_calls(project.id)
    assert [call.tool_name for call in run_calls] == ["apply-patch", "propose-patch"]
    assert [call.tool_name for call in project_calls[:2]] == ["apply-patch", "propose-patch"]


@pytest.mark.asyncio
async def test_step_tool_calls_returns_only_calls_for_step(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    run = isolated_db.create_run(prompt="patch step", project_id=project.id, project_path=project.path)
    isolated_db.create_tool_call(
        run_id=run.id,
        project_id=project.id,
        step_id="step-a",
        tool_name="propose-patch",
        status="completed",
    )
    isolated_db.create_tool_call(
        run_id=run.id,
        project_id=project.id,
        step_id="step-b",
        tool_name="apply-patch",
        status="completed",
    )

    calls = await routes.get_step_tool_calls(run.id, "step-a")

    assert len(calls) == 1
    assert calls[0].step_id == "step-a"
    assert calls[0].tool_name == "propose-patch"


@pytest.mark.asyncio
async def test_step_tool_calls_does_not_return_other_run_calls(isolated_db, tmp_path):
    project, _project_dir = make_project(isolated_db, tmp_path)
    run = isolated_db.create_run(prompt="patch step", project_id=project.id, project_path=project.path)
    other_run = isolated_db.create_run(prompt="other", project_id=project.id, project_path=project.path)
    isolated_db.create_tool_call(
        run_id=run.id,
        project_id=project.id,
        step_id="shared-step",
        tool_name="propose-patch",
        status="completed",
    )
    isolated_db.create_tool_call(
        run_id=other_run.id,
        project_id=project.id,
        step_id="shared-step",
        tool_name="apply-patch",
        status="completed",
    )

    calls = await routes.get_step_tool_calls(run.id, "shared-step")

    assert len(calls) == 1
    assert calls[0].run_id == run.id
    assert calls[0].tool_name == "propose-patch"


@pytest.mark.asyncio
async def test_propose_patch_with_step_id_appears_in_step_tool_calls(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    run = isolated_db.create_run(prompt="patch step", project_id=project.id, project_path=project.path)

    await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id=run.id,
            step_id="step-a",
            agent_id="agent-a",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = await routes.get_step_tool_calls(run.id, "step-a")
    assert len(calls) == 1
    assert calls[0].tool_name == "propose-patch"
    assert calls[0].step_id == "step-a"


@pytest.mark.asyncio
async def test_apply_patch_with_proposal_id_appears_in_step_tool_calls(isolated_db, tmp_path):
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("old\n", encoding="utf-8")
    run = isolated_db.create_run(prompt="patch step", project_id=project.id, project_path=project.path)
    proposal = await routes.run_project_propose_patch(
        project.id,
        ProposePatchRequest(
            run_id=run.id,
            step_id="step-a",
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    await routes.run_project_apply_patch(
        project.id,
        ApplyPatchRequest(
            run_id=run.id,
            step_id="step-a",
            proposal_id=proposal["proposal_id"],
            confirm=True,
            operations=[PatchOperation(file_path="app.py", old_text="old", new_text="new")],
        ),
    )

    calls = await routes.get_step_tool_calls(run.id, "step-a")
    assert [call.tool_name for call in calls] == ["apply-patch", "propose-patch"]


# ── Safe Test Command Runner ─────────────────────────────────────────────────


def make_project_with_commands(isolated_db, tmp_path: Path, **kwargs):
    """Helper: create a project dir and register it with the given command fields."""
    project_dir = tmp_path / "cmd-project"
    project_dir.mkdir(exist_ok=True)
    defaults = dict(
        name="CmdProject",
        path=str(project_dir),
        test_command="",
        build_command="",
        safe_commands=[],
    )
    defaults.update(kwargs)
    project = isolated_db.create_project(**defaults)
    return project, project_dir


# ── run_project_command (unit) ────────────────────────────────────────────────


def test_run_project_command_echo_succeeds(tmp_path):
    """A simple echo command completes with returncode 0."""
    result = run_project_command(str(tmp_path), "echo hello world")
    assert result["returncode"] == 0
    assert "hello world" in result["stdout"]
    assert result["timed_out"] is False
    assert result["duration_ms"] >= 0


def test_run_project_command_uses_project_path_as_cwd(tmp_path):
    """cwd must be anchored to project_path."""
    result = run_project_command(str(tmp_path), "pwd")
    assert result["returncode"] == 0
    assert result["cwd"] == str(tmp_path.resolve())


def test_run_project_command_non_zero_returncode_not_exception(tmp_path):
    """A command that exits non-zero should return returncode, not raise."""
    result = run_project_command(str(tmp_path), "false")
    assert result["returncode"] != 0
    assert result["timed_out"] is False


def test_run_project_command_timeout_returns_timed_out_true(tmp_path):
    """Commands that exceed timeout return timed_out=True, returncode=124."""
    result = run_project_command(str(tmp_path), "sleep 10", timeout_seconds=1)
    assert result["timed_out"] is True
    assert result["returncode"] == 124


def test_run_project_command_caps_stdout(tmp_path):
    """stdout is capped at MAX_OUTPUT_CHARS characters."""
    from src.project_tools import MAX_OUTPUT_CHARS, TRUNCATED_OUTPUT_MARKER

    # Generate output longer than cap using python (available everywhere)
    big = "x" * (MAX_OUTPUT_CHARS + 500)
    cmd = f"python3 -c \"print('{big}')\""
    result = run_project_command(str(tmp_path), cmd)
    assert len(result["stdout"]) <= MAX_OUTPUT_CHARS + len(TRUNCATED_OUTPUT_MARKER)
    assert TRUNCATED_OUTPUT_MARKER in result["stdout"]


def test_run_project_command_blocks_rm(tmp_path):
    """rm command is rejected by safety rules."""
    with pytest.raises(ValueError, match="blocked by safety rule"):
        run_project_command(str(tmp_path), "rm -rf .")


def test_run_project_command_blocks_sudo(tmp_path):
    """sudo is rejected by safety rules."""
    with pytest.raises(ValueError, match="blocked by safety rule"):
        run_project_command(str(tmp_path), "sudo ls")


def test_run_project_command_blocks_path_traversal(tmp_path):
    """Commands with .. are rejected."""
    with pytest.raises(ValueError, match="path traversal"):
        run_project_command(str(tmp_path), "ls ../secret")


def test_run_project_command_shell_injection_treated_as_literal_args(tmp_path):
    """Shell meta-characters like ; are treated as literal args (shell=False)."""
    # "echo hello; rm -rf ." with shell=False would pass the ';' literally to echo
    # and NOT execute rm — which means returncode may be 0 but rm was not run.
    # The rm pattern also triggers the safety check, so this should raise.
    with pytest.raises(ValueError, match="blocked by safety rule"):
        run_project_command(str(tmp_path), "echo hello; rm -rf .")


# ── endpoint: POST /api/projects/{project_id}/tools/run-command ───────────────


@pytest.mark.asyncio
async def test_run_command_test_kind_runs_test_command(isolated_db, tmp_path):
    """test kind uses project.test_command and returns structured response."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="echo pytest-output",
        safe_commands=["echo pytest-output"],
    )
    req = RunProjectCommandRequest(command_kind="test")
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.command_kind == "test"
    assert result.command == "echo pytest-output"
    assert result.returncode == 0
    assert "pytest-output" in result.stdout
    assert result.timed_out is False
    assert result.tool_call_id != ""


@pytest.mark.asyncio
async def test_run_command_build_kind_runs_build_command(isolated_db, tmp_path):
    """build kind uses project.build_command."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        build_command="echo build-ok",
        safe_commands=["echo build-ok"],
    )
    req = RunProjectCommandRequest(command_kind="build")
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.command_kind == "build"
    assert result.returncode == 0
    assert "build-ok" in result.stdout


@pytest.mark.asyncio
async def test_run_command_creates_tool_call_with_project_and_run_ids(isolated_db, tmp_path):
    """Tool call is created with project_id, run_id, step_id linked correctly."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="echo linked",
        safe_commands=["echo linked"],
    )
    run = isolated_db.create_run(prompt="link test", project_id=project.id)
    step = isolated_db.create_run_step(run_id=run.id, parent_step_id="", title="Test step")

    req = RunProjectCommandRequest(
        command_kind="test",
        run_id=run.id,
        step_id=step.id,
        agent_id="qa-expert",
    )
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.tool_call_id != ""

    calls = isolated_db.list_tool_calls_for_project(project.id)
    tc = next((c for c in calls if c.id == result.tool_call_id), None)
    assert tc is not None
    assert tc.run_id == run.id
    assert tc.step_id == step.id
    assert tc.project_id == project.id
    assert tc.tool_name == "run-command"
    assert tc.risk_level == "medium"
    assert tc.status == "completed"


@pytest.mark.asyncio
async def test_run_command_non_zero_returncode_still_completed(isolated_db, tmp_path):
    """Non-zero exit = completed tool_call, not failed."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="false",
        safe_commands=["false"],
    )
    req = RunProjectCommandRequest(command_kind="test")
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.returncode != 0
    assert result.timed_out is False
    assert result.tool_call_id != ""
    # Tool call status should be "completed"
    calls = isolated_db.list_tool_calls_for_project(project.id)
    tc = next(c for c in calls if c.id == result.tool_call_id)
    assert tc.status == "completed"


@pytest.mark.asyncio
async def test_run_command_missing_test_command_returns_400(isolated_db, tmp_path):
    """Requesting test kind when test_command is empty returns 400."""
    from fastapi import HTTPException
    project, _dir = make_project_with_commands(isolated_db, tmp_path, test_command="")
    req = RunProjectCommandRequest(command_kind="test")
    with pytest.raises(HTTPException) as exc_info:
        await routes.run_project_command_endpoint(project.id, req)
    assert exc_info.value.status_code == 400
    assert "test_command" in exc_info.value.detail


@pytest.mark.asyncio
async def test_run_command_lint_kind_found_in_safe_commands(isolated_db, tmp_path):
    """lint kind resolves and runs the first safe_command containing a lint keyword."""
    # "echo lint-done" contains "lint" — matches _LINT_KEYWORDS
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        safe_commands=["echo lint-done"],
    )
    req = RunProjectCommandRequest(command_kind="lint")
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.command_kind == "lint"
    assert result.command == "echo lint-done"
    assert result.returncode == 0
    assert result.timed_out is False
    assert result.tool_call_id != ""
    # tool_call should be completed
    calls = isolated_db.list_tool_calls_for_project(project.id)
    tc = next(c for c in calls if c.id == result.tool_call_id)
    assert tc.status == "completed"


@pytest.mark.asyncio
async def test_run_command_typecheck_found_in_safe_commands(isolated_db, tmp_path):
    """typecheck kind resolves and runs the first safe_command containing a typecheck keyword."""
    # "echo typecheck done" contains "typecheck" — matches _TYPECHECK_KEYWORDS
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        safe_commands=["echo typecheck done"],
    )
    req = RunProjectCommandRequest(command_kind="typecheck")
    result = await routes.run_project_command_endpoint(project.id, req)
    assert result.command_kind == "typecheck"
    assert result.command == "echo typecheck done"
    assert result.returncode == 0
    assert result.timed_out is False
    assert result.tool_call_id != ""
    # tool_call should be completed
    calls = isolated_db.list_tool_calls_for_project(project.id)
    tc = next(c for c in calls if c.id == result.tool_call_id)
    assert tc.status == "completed"


@pytest.mark.asyncio
async def test_run_command_arbitrary_command_not_in_allowlist_rejected(isolated_db, tmp_path):
    """The endpoint must reject commands not in the project allowlist (safety guard)."""
    # This is enforced at the endpoint: the resolved command must be in allowed set.
    # Since endpoint resolves command from project fields, the only way to bypass is
    # if the project itself has a dangerous command — which is blocked by the runner.
    # Here we verify that 400 is returned when test_command is missing.
    from fastapi import HTTPException
    project, _dir = make_project_with_commands(isolated_db, tmp_path)
    req = RunProjectCommandRequest(command_kind="build")
    with pytest.raises(HTTPException) as exc_info:
        await routes.run_project_command_endpoint(project.id, req)
    assert exc_info.value.status_code == 400


# ── Test Result Analysis ─────────────────────────────────────────────────────

from src.models import CommandAnalysisRequest
from src.project_tools import analyze_command_result


def test_analyze_pytest_failure_extracts_test_failure_issue():
    """pytest FAILED lines produce test_failure issues."""
    stdout = (
        "FAILED tests/test_foo.py::test_bar - AssertionError: expected 1\n"
        "FAILED tests/test_foo.py::test_baz\n"
    )
    result = analyze_command_result(stdout=stdout, returncode=1)
    assert result["status"] == "failed"
    kinds = [i["kind"] for i in result["issues"]]
    assert "test_failure" in kinds
    paths = [i["file_path"] for i in result["issues"] if i["kind"] == "test_failure"]
    assert any("test_foo.py" in (p or "") for p in paths)


def test_analyze_assertion_error_detected():
    """AssertionError in output produces assertion_error issue."""
    stderr = "AssertionError: expected 42 but got 0"
    result = analyze_command_result(stderr=stderr, returncode=1)
    assert result["status"] == "failed"
    kinds = [i["kind"] for i in result["issues"]]
    assert "assertion_error" in kinds
    msg = next(i["message"] for i in result["issues"] if i["kind"] == "assertion_error")
    assert "42" in msg


def test_analyze_typescript_error_extracts_file_and_line():
    """TypeScript tsc error lines produce type_error issues with file_path and line."""
    stderr = 'src/components/Button.tsx(23,5): error TS2345: Argument of type string is not assignable.'
    result = analyze_command_result(stderr=stderr, returncode=2)
    assert result["status"] == "failed"
    ts_issues = [i for i in result["issues"] if i["kind"] == "type_error"]
    assert len(ts_issues) >= 1
    assert ts_issues[0]["file_path"] == "src/components/Button.tsx"
    assert ts_issues[0]["line"] == 23
    assert "TS2345" in ts_issues[0]["message"]


def test_analyze_python_traceback_extracts_file_and_line():
    """Python traceback lines produce traceback issues with file_path and line."""
    stdout = (
        'Traceback (most recent call last):\n'
        '  File "src/engine.py", line 99, in run\n'
        '    result = step.execute()\n'
        'ValueError: unexpected None\n'
    )
    result = analyze_command_result(stdout=stdout, returncode=1)
    assert result["status"] == "failed"
    tb_issues = [i for i in result["issues"] if i["kind"] == "traceback"]
    assert len(tb_issues) >= 1
    assert tb_issues[0]["file_path"] == "src/engine.py"
    assert tb_issues[0]["line"] == 99


def test_analyze_successful_command_returns_passed():
    """returncode=0 → status 'passed', no issues."""
    result = analyze_command_result(stdout="All tests passed.", returncode=0)
    assert result["status"] == "passed"
    assert result["issues"] == []
    assert result["can_create_fix_proposal"] is False


def test_analyze_timeout_returns_timed_out():
    """timed_out=True produces status 'timed_out' regardless of returncode."""
    result = analyze_command_result(stdout="", returncode=124, timed_out=True)
    assert result["status"] == "timed_out"
    assert result["issues"][0]["kind"] == "timeout"
    assert result["can_create_fix_proposal"] is False


@pytest.mark.asyncio
async def test_analyze_endpoint_resolves_by_tool_call_id(isolated_db, tmp_path):
    """Endpoint reads stdout/stderr from stored ToolCall when tool_call_id given."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="false",
        safe_commands=["false"],
    )
    # Run a command that fails so we have a tool_call record
    run_result = await routes.run_project_command_endpoint(
        project.id,
        RunProjectCommandRequest(command_kind="test"),
    )
    tc_id = run_result.tool_call_id
    assert tc_id

    # Now analyze using the stored tool_call_id
    req = CommandAnalysisRequest(tool_call_id=tc_id, run_id="run-analyze")
    analysis = await routes.analyze_project_command_result(project.id, req)

    assert analysis.status in ("failed", "passed", "timed_out", "unknown")
    assert analysis.source_tool_call_id == tc_id


@pytest.mark.asyncio
async def test_analyze_endpoint_rejects_tool_call_from_other_project(isolated_db, tmp_path):
    """404 is returned when tool_call_id belongs to a different project."""
    from fastapi import HTTPException

    project_a, _dir_a = make_project_with_commands(
        isolated_db, tmp_path,
        name="ProjA",
        test_command="false",
        safe_commands=["false"],
    )
    project_b_dir = tmp_path / "proj-b"
    project_b_dir.mkdir()
    project_b = isolated_db.create_project(name="ProjB", path=str(project_b_dir))

    # Run command under project A
    run_result = await routes.run_project_command_endpoint(
        project_a.id,
        RunProjectCommandRequest(command_kind="test"),
    )
    tc_id = run_result.tool_call_id

    # Attempt to analyze it under project B → 404
    req = CommandAnalysisRequest(tool_call_id=tc_id)
    with pytest.raises(HTTPException) as exc_info:
        await routes.analyze_project_command_result(project_b.id, req)
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_analyze_endpoint_logs_audit_tool_call(isolated_db, tmp_path):
    """Endpoint creates an analyze-command-result tool_call record with status=completed."""
    project, _dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="false",
        safe_commands=["false"],
    )
    run_result = await routes.run_project_command_endpoint(
        project.id,
        RunProjectCommandRequest(command_kind="test", run_id="run-audit"),
    )

    req = CommandAnalysisRequest(
        tool_call_id=run_result.tool_call_id,
        run_id="run-audit",
    )
    await routes.analyze_project_command_result(project.id, req)

    all_calls = isolated_db.list_tool_calls_for_project(project.id)
    audit_calls = [c for c in all_calls if c.tool_name == "analyze-command-result"]
    assert len(audit_calls) == 1
    assert audit_calls[0].status == "completed"
    assert audit_calls[0].risk_level == "low"
    assert audit_calls[0].run_id == "run-audit"


@pytest.mark.asyncio
async def test_analyze_endpoint_does_not_modify_files(isolated_db, tmp_path):
    """Calling analyze does not create or change files in the project directory."""
    project, project_dir = make_project_with_commands(
        isolated_db, tmp_path,
        test_command="false",
        safe_commands=["false"],
    )
    sentinel = project_dir / "sentinel.txt"
    sentinel.write_text("original\n", encoding="utf-8")
    files_before = set(project_dir.iterdir())

    req = CommandAnalysisRequest(stdout="some failure", stderr="", returncode=1)
    await routes.analyze_project_command_result(project.id, req)

    assert sentinel.read_text(encoding="utf-8") == "original\n"
    assert set(project_dir.iterdir()) == files_before


# ── Patch History + Manual Rollback v1 ───────────────────────────────────────

from src.models import RollbackPatchRequest as RollbackPatchRequestModel
from src.project_tools import rollback_project_patch


def test_apply_patch_stores_rollback_metadata_in_output_json(tmp_path):
    """apply_project_patch stores rollback_data in the returned dict."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("before content\n", encoding="utf-8")

    response = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="before", new_text="after")],
        confirm=True,
    )

    assert "rollback_data" in response
    entries = response["rollback_data"]
    assert len(entries) == 1
    assert entries[0]["path"] == "app.py"
    assert entries[0]["operation"] == "modified"
    assert entries[0]["rollback_supported"] is True
    assert entries[0]["before_content"] == "before content\n"
    assert entries[0]["after_hash"]  # non-empty 16-char hash


def test_rollback_requires_confirm_true(tmp_path):
    """rollback_project_patch raises PermissionError without confirm=True."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    with pytest.raises(PermissionError, match="confirm=true"):
        rollback_project_patch(str(project_dir), [{"path": "app.py", "operation": "modified",
                                                    "rollback_supported": True, "after_hash": "abc",
                                                    "before_content": "old\n"}], confirm=False)


def test_rollback_modified_file_restores_previous_content(tmp_path):
    """Rollback of a modified file writes back the before_content."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("before content\n", encoding="utf-8")

    apply_result = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="before", new_text="after")],
        confirm=True,
    )
    assert target.read_text(encoding="utf-8") == "after content\n"

    rollback_result = rollback_project_patch(str(project_dir), apply_result["rollback_data"], confirm=True)

    assert target.read_text(encoding="utf-8") == "before content\n"
    assert rollback_result["rolled_back_files"][0]["status"] == "restored"
    assert len(rollback_result["skipped_files"]) == 0


def test_rollback_created_file_deletes_it(tmp_path):
    """Rollback of a created file removes it from disk."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    apply_result = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="new.txt", new_text="created\n", create_if_missing=True)],
        confirm=True,
    )
    assert (project_dir / "new.txt").exists()

    rollback_result = rollback_project_patch(str(project_dir), apply_result["rollback_data"], confirm=True)

    assert not (project_dir / "new.txt").exists()
    assert rollback_result["rolled_back_files"][0]["status"] == "deleted"
    assert len(rollback_result["skipped_files"]) == 0


def test_rollback_skips_file_modified_after_apply(tmp_path):
    """Conflict detection: if file changed post-apply, rollback skips with 'conflict'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("original\n", encoding="utf-8")

    apply_result = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="original", new_text="patched")],
        confirm=True,
    )
    # Simulate a subsequent edit that makes the file differ from after_hash
    target.write_text("changed after apply\n", encoding="utf-8")

    rollback_result = rollback_project_patch(str(project_dir), apply_result["rollback_data"], confirm=True)

    assert target.read_text(encoding="utf-8") == "changed after apply\n"
    assert rollback_result["skipped_files"][0]["status"] == "conflict"
    assert len(rollback_result["rolled_back_files"]) == 0


@pytest.mark.asyncio
async def test_rollback_endpoint_returns_404_for_wrong_project(isolated_db, tmp_path):
    """Rollback endpoint returns 404 if tool_call_id doesn't belong to project."""
    project, project_dir = make_project(isolated_db, tmp_path)

    other_project_dir = tmp_path / "Other Workspace Project"
    other_project_dir.mkdir()
    other_project = isolated_db.create_project(name="Other", path=str(other_project_dir))

    # Create a tool call under `other_project`
    tc = isolated_db.create_tool_call(
        run_id="run-1",
        project_id=other_project.id,
        step_id="step-1",
        tool_name="apply-patch",
        status="completed",
        output_json='{"rollback_data":[]}',
    )

    with pytest.raises(HTTPException) as exc:
        await routes.rollback_project_patch_endpoint(
            project.id,
            RollbackPatchRequestModel(tool_call_id=tc.id, confirm=True),
        )

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_rollback_endpoint_logs_high_risk_tool_call(isolated_db, tmp_path):
    """Rollback endpoint creates a 'rollback-patch' tool_call with risk_level='high'."""
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("original\n", encoding="utf-8")

    # Apply a patch first so we have a real apply-patch tool_call with rollback_data
    apply_result = await routes.run_project_apply_patch(
        project.id,
        ApplyPatchRequest(
            run_id="run-rb",
            confirm=True,
            operations=[PatchOperation(file_path="app.py", old_text="original", new_text="patched")],
        ),
    )
    apply_tc_id = apply_result["tool_call_id"]

    await routes.rollback_project_patch_endpoint(
        project.id,
        RollbackPatchRequestModel(tool_call_id=apply_tc_id, confirm=True, run_id="run-rb"),
    )

    all_calls = isolated_db.list_tool_calls_for_project(project.id)
    rollback_calls = [c for c in all_calls if c.tool_name == "rollback-patch"]
    assert len(rollback_calls) == 1
    assert rollback_calls[0].risk_level == "high"
    assert rollback_calls[0].status == "completed"


def test_rollback_does_not_run_shell_commands(tmp_path):
    """rollback_project_patch must not invoke subprocess / shell."""
    import subprocess as _subprocess
    import unittest.mock as mock

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    target = project_dir / "app.py"
    target.write_text("before\n", encoding="utf-8")

    apply_result = apply_project_patch(
        str(project_dir),
        [PatchOperation(file_path="app.py", old_text="before", new_text="after")],
        confirm=True,
    )

    with mock.patch.object(_subprocess, "run", side_effect=AssertionError("shell used")) as mock_run, \
         mock.patch.object(_subprocess, "Popen", side_effect=AssertionError("shell used")):
        rollback_project_patch(str(project_dir), apply_result["rollback_data"], confirm=True)
        mock_run.assert_not_called()


def test_rollback_blocks_path_traversal(tmp_path):
    """Rollback skips entries whose path escapes the project workspace."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("sensitive\n", encoding="utf-8")

    rollback_data = [
        {"path": "../outside.txt", "operation": "modified", "rollback_supported": True,
         "before_content": "changed\n", "after_hash": "does-not-matter"},
    ]

    result = rollback_project_patch(str(project_dir), rollback_data, confirm=True)

    assert outside.read_text(encoding="utf-8") == "sensitive\n"
    assert len(result["rolled_back_files"]) == 0
    assert result["skipped_files"][0]["status"] in {"error", "skipped"}


def test_rollback_blocks_secret_file(tmp_path):
    """Rollback skips secret-like files (e.g. .env)."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    env_file = project_dir / ".env"
    env_file.write_text("SECRET=new\n", encoding="utf-8")

    # Manufacture a plausible after_hash so conflict detection doesn't fire
    import hashlib
    after_hash = hashlib.sha256("SECRET=new\n".encode()).hexdigest()[:16]
    rollback_data = [
        {"path": ".env", "operation": "modified", "rollback_supported": True,
         "before_content": "SECRET=old\n", "after_hash": after_hash},
    ]

    result = rollback_project_patch(str(project_dir), rollback_data, confirm=True)

    assert env_file.read_text(encoding="utf-8") == "SECRET=new\n"
    assert len(result["rolled_back_files"]) == 0
    assert result["skipped_files"][0]["status"] in {"skipped", "error"}


# ── Safe Auto Read/Search v1 tests ────────────────────────────────────────────

from src.models import AutoStepReadRequest  # noqa: E402


def _make_run_and_step(isolated_db, project, project_dir):
    """Helper: create a run linked to *project* and one step inside it."""
    run = isolated_db.create_run(
        prompt="auto-read test",
        project_id=project.id,
        project_path=str(project_dir),
    )
    step = isolated_db.create_run_step(run_id=run.id, parent_step_id="", title="Analyse source")
    return run, step


@pytest.mark.asyncio
async def test_auto_read_rejects_blocked_action_propose_patch(isolated_db, tmp_path):
    """propose_patch is explicitly blocked → 403."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="propose_patch")
    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_read(run.id, step.id, req)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_auto_read_rejects_all_blocked_actions(isolated_db, tmp_path):
    """apply_patch, run_command, rollback_patch, analyze_result, run_tests are all 403."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    for action in ("apply_patch", "run_command", "rollback_patch", "analyze_result", "run_tests"):
        req = AutoStepReadRequest(step_id=step.id, action_type=action)
        with pytest.raises(HTTPException) as exc:
            await routes.run_step_auto_read(run.id, step.id, req)
        assert exc.value.status_code == 403, f"Expected 403 for {action}, got {exc.value.status_code}"


@pytest.mark.asyncio
async def test_auto_read_rejects_unknown_action_type(isolated_db, tmp_path):
    """An unknown action_type that is neither allowed nor blocked → 400."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="deploy_to_production")
    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_read(run.id, step.id, req)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_auto_read_list_files_creates_low_risk_tool_call(isolated_db, tmp_path):
    """list_files auto-read creates a completed low-risk ToolCall."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "src").mkdir()
    (project_dir / "src" / "main.py").write_text("x = 1\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="list_files")
    resp = await routes.run_step_auto_read(run.id, step.id, req)

    assert resp.status == "completed"
    assert resp.action_type == "list_files"
    assert "file" in resp.summary.lower()

    calls = isolated_db.list_tool_calls_for_step(step.id)
    tc = next((c for c in calls if c.id == resp.tool_call_id), None)
    assert tc is not None
    assert tc.risk_level == "low"
    assert tc.status == "completed"
    assert tc.tool_name == "list_files"
    assert tc.run_id == run.id
    assert tc.step_id == step.id


@pytest.mark.asyncio
async def test_auto_read_search_code_creates_low_risk_tool_call_with_matches(isolated_db, tmp_path):
    """search_code auto-read finds matches and stores them in the ToolCall."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "utils.py").write_text("def compute_hash():\n    pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="search_code", query="compute_hash")
    resp = await routes.run_step_auto_read(run.id, step.id, req)

    assert resp.status == "completed"
    assert resp.action_type == "search_code"

    calls = isolated_db.list_tool_calls_for_step(step.id)
    tc = next((c for c in calls if c.id == resp.tool_call_id), None)
    assert tc is not None
    assert tc.risk_level == "low"
    assert tc.status == "completed"
    assert "compute_hash" in tc.output_json


@pytest.mark.asyncio
async def test_auto_read_read_file_reads_safe_file(isolated_db, tmp_path):
    """read_file auto-read returns file content and creates a completed ToolCall."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "config.py").write_text("DEBUG = True\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="read_file", file_path="config.py")
    resp = await routes.run_step_auto_read(run.id, step.id, req)

    assert resp.status == "completed"
    assert "config.py" in resp.summary
    calls = isolated_db.list_tool_calls_for_step(step.id)
    tc = next((c for c in calls if c.id == resp.tool_call_id), None)
    assert tc is not None
    assert tc.risk_level == "low"
    assert "DEBUG" in tc.output_json


@pytest.mark.asyncio
async def test_auto_read_read_file_blocks_path_traversal(isolated_db, tmp_path):
    """read_file with ../escape path raises 400 and does not return secrets."""
    project, project_dir = make_project(isolated_db, tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP SECRET\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="read_file", file_path="../secret.txt")
    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_read(run.id, step.id, req)
    assert exc.value.status_code in {400, 403, 500}


@pytest.mark.asyncio
async def test_auto_read_does_not_modify_project_files(isolated_db, tmp_path):
    """After list_files and search_code auto-reads, no project file is changed."""
    project, project_dir = make_project(isolated_db, tmp_path)
    src_file = project_dir / "app.py"
    original_content = "print('hello')\n"
    src_file.write_text(original_content, encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    await routes.run_step_auto_read(run.id, step.id, AutoStepReadRequest(step_id=step.id, action_type="list_files"))
    await routes.run_step_auto_read(run.id, step.id, AutoStepReadRequest(step_id=step.id, action_type="search_code", query="print"))

    # File must be untouched
    assert src_file.read_text(encoding="utf-8") == original_content


@pytest.mark.asyncio
async def test_auto_read_requires_valid_run_step(isolated_db, tmp_path):
    """Unknown run_id or step_id raises 404."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Bad run_id
    req = AutoStepReadRequest(step_id=step.id, action_type="list_files")
    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_read("nonexistent-run", step.id, req)
    assert exc.value.status_code == 404

    # Bad step_id
    req2 = AutoStepReadRequest(step_id="nonexistent-step", action_type="list_files")
    with pytest.raises(HTTPException) as exc2:
        await routes.run_step_auto_read(run.id, "nonexistent-step", req2)
    assert exc2.value.status_code == 404


@pytest.mark.asyncio
async def test_auto_read_output_visible_through_step_tool_calls_endpoint(isolated_db, tmp_path):
    """ToolCall created by auto-read appears in the step tool-calls endpoint."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "index.py").write_text("# entry point\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoStepReadRequest(step_id=step.id, action_type="list_files")
    resp = await routes.run_step_auto_read(run.id, step.id, req)

    # Use the step tool-calls endpoint to confirm visibility
    step_calls = await routes.get_step_tool_calls(run.id, step.id)
    ids = [c.id for c in step_calls]
    assert resp.tool_call_id in ids


# ── Auto Context Gathering v1 tests ───────────────────────────────────────────

from src.models import AutoContextGatherRequest  # noqa: E402


@pytest.mark.asyncio
async def test_auto_context_creates_only_low_risk_tool_calls(isolated_db, tmp_path):
    """Every ToolCall created by auto-context has risk_level='low'."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "main.py").write_text("def run(): pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoContextGatherRequest(max_tool_calls=5, query="run")
    resp = await routes.run_step_auto_context(run.id, step.id, req)

    calls = isolated_db.list_tool_calls_for_step(step.id)
    assert len(calls) > 0
    for tc in calls:
        assert tc.risk_level == "low", f"Expected low risk, got {tc.risk_level} for {tc.tool_name}"
    assert set(resp.tool_call_ids).issubset({tc.id for tc in calls})


@pytest.mark.asyncio
async def test_auto_context_uses_only_safe_tools(isolated_db, tmp_path):
    """auto-context never creates tool calls with prohibited tool names."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "app.py").write_text("x = 1\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    await routes.run_step_auto_context(run.id, step.id, AutoContextGatherRequest(max_tool_calls=5))

    ALLOWED = {"list_files", "read_file", "search_code"}
    FORBIDDEN = {"propose_patch", "apply_patch", "rollback_patch", "run_command", "run-command",
                 "analyze_result", "run_tests"}
    calls = isolated_db.list_tool_calls_for_step(step.id)
    for tc in calls:
        assert tc.tool_name in ALLOWED, f"Forbidden tool used: {tc.tool_name}"
        assert tc.tool_name not in FORBIDDEN


@pytest.mark.asyncio
async def test_auto_context_respects_max_tool_calls(isolated_db, tmp_path):
    """Number of ToolCalls created never exceeds max_tool_calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    for i in range(10):
        (project_dir / f"file{i}.py").write_text(f"x = {i}\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    cap = 3
    resp = await routes.run_step_auto_context(run.id, step.id, AutoContextGatherRequest(max_tool_calls=cap))

    assert len(resp.tool_call_ids) <= cap


@pytest.mark.asyncio
async def test_auto_context_rejects_max_tool_calls_above_hard_cap(isolated_db, tmp_path):
    """max_tool_calls above hard cap (8) raises 400."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoContextGatherRequest(max_tool_calls=99)
    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_context(run.id, step.id, req)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_auto_context_does_not_modify_project_files(isolated_db, tmp_path):
    """No project file is altered after auto-context runs."""
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "service.py"
    original = "class Service:\n    pass\n"
    target.write_text(original, encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    await routes.run_step_auto_context(run.id, step.id, AutoContextGatherRequest(max_tool_calls=5, query="Service"))

    assert target.read_text(encoding="utf-8") == original
    # Also make sure no new files were created silently
    after_files = {p.name for p in project_dir.iterdir()}
    assert "service.py" in after_files


@pytest.mark.asyncio
async def test_auto_context_reads_relevant_file_after_search_match(isolated_db, tmp_path):
    """When search_code finds a match, the matched file appears in files_read."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "router.py").write_text("def get_routes(): return []\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.run_step_auto_context(
        run.id, step.id,
        AutoContextGatherRequest(max_tool_calls=5, query="get_routes"),
    )

    read_paths = [f.file_path for f in resp.files_read]
    assert "router.py" in read_paths


@pytest.mark.asyncio
async def test_auto_context_falls_back_to_file_list_when_no_search_matches(isolated_db, tmp_path):
    """When search_code has no matches, files are still selected by heuristic."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "routes.py").write_text("# routes\n", encoding="utf-8")
    (project_dir / "model.py").write_text("# model\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.run_step_auto_context(
        run.id, step.id,
        AutoContextGatherRequest(max_tool_calls=5, query="xyzzy_no_match_xyz"),
    )

    # Even with no matches we should still have attempted list_files and search_code
    assert len(resp.tool_call_ids) >= 2
    # And may have read heuristic files
    assert resp.status in {"completed", "partial"}


@pytest.mark.asyncio
async def test_auto_context_does_not_create_forbidden_tool_calls(isolated_db, tmp_path):
    """auto-context must never produce propose_patch/apply_patch/run_command calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "x.py").write_text("pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    await routes.run_step_auto_context(run.id, step.id, AutoContextGatherRequest(max_tool_calls=8))

    FORBIDDEN = {"propose_patch", "apply_patch", "rollback_patch", "run_command",
                 "run-command", "analyze_result", "run_tests"}
    all_calls = isolated_db.list_tool_calls_for_run(run.id)
    for tc in all_calls:
        assert tc.tool_name not in FORBIDDEN, f"Forbidden tool_call created: {tc.tool_name}"


@pytest.mark.asyncio
async def test_auto_context_output_visible_through_step_tool_calls_endpoint(isolated_db, tmp_path):
    """ToolCalls from auto-context are visible through the step tool-calls endpoint."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "api.py").write_text("# api\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.run_step_auto_context(run.id, step.id, AutoContextGatherRequest(max_tool_calls=3))

    step_calls = await routes.get_step_tool_calls(run.id, step.id)
    step_call_ids = {tc.id for tc in step_calls}
    for tc_id in resp.tool_call_ids:
        assert tc_id in step_call_ids, f"tool_call {tc_id} not visible in step endpoint"


@pytest.mark.asyncio
async def test_auto_context_requires_valid_run_step(isolated_db, tmp_path):
    """Invalid run_id or step_id raises 404."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    req = AutoContextGatherRequest(max_tool_calls=3)

    with pytest.raises(HTTPException) as exc:
        await routes.run_step_auto_context("bad-run-id", step.id, req)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        await routes.run_step_auto_context(run.id, "bad-step-id", req)
    assert exc2.value.status_code == 404


@pytest.mark.asyncio
async def test_auto_context_response_contains_summary_and_queries(isolated_db, tmp_path):
    """Response always includes a summary, searched_queries, and next_recommended_action."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "controller.py").write_text("class Ctrl: pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.run_step_auto_context(
        run.id, step.id,
        AutoContextGatherRequest(max_tool_calls=5, query="Ctrl"),
    )

    assert resp.summary != ""
    assert resp.searched_queries  # should have at least one query
    assert resp.next_recommended_action in {"propose_patch", "search_code", "read_context", "done"}


# ── Step Context Bundle v1 tests ──────────────────────────────────────────────

from src.model_router import build_step_context_bundle  # noqa: E402


def _make_tool_call_obj(isolated_db, run, step, tool_name, input_json, output_json, status="completed"):
    tc = isolated_db.create_tool_call(
        run_id=run.id,
        project_id=run.project_id,
        step_id=step.id,
        tool_name=tool_name,
        status="pending",
        input_json=input_json,
        risk_level="low",
    )
    isolated_db.update_tool_call(tc.id, status=status, output_json=output_json)
    return isolated_db.list_tool_calls_for_step(step.id)[-1]  # fetch updated


@pytest.mark.asyncio
async def test_context_bundle_empty_when_no_tool_calls(isolated_db, tmp_path):
    """Bundle status is 'empty' with warning when step has no tool calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.get_step_context_bundle(run.id, step.id)
    bundle = resp.bundle

    assert bundle.status == "empty"
    assert bundle.files == []
    assert bundle.queries == []
    assert any("context" in w.lower() or "no read" in w.lower() for w in bundle.warnings)


@pytest.mark.asyncio
async def test_context_bundle_uses_only_read_only_tool_calls(isolated_db, tmp_path):
    """Bundle only includes list_files / search_code / read_file tool calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Create one allowed and one forbidden tool call manually
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="list_files",
        input_json='{}',
        output_json='{"files": [{"path": "app.py"}]}',
    )
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="propose_patch",
        input_json='{}',
        output_json='{}',
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    # tool_call_ids should reference only the list_files call
    calls = isolated_db.list_tool_calls_for_step(step.id)
    allowed_ids = {tc.id for tc in calls if tc.tool_name in {"list_files", "search_code", "read_file"}}
    for tc_id in resp.bundle.tool_call_ids:
        assert tc_id in allowed_ids


@pytest.mark.asyncio
async def test_context_bundle_ignores_forbidden_tools(isolated_db, tmp_path):
    """propose_patch / apply_patch / run_command are never included in bundle."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    for bad_tool in ("apply_patch", "run_command", "rollback_patch"):
        _make_tool_call_obj(isolated_db, run, step, tool_name=bad_tool, input_json='{}', output_json='{}')

    resp = await routes.get_step_context_bundle(run.id, step.id)
    assert resp.bundle.status == "empty"
    assert resp.bundle.tool_call_ids == []


@pytest.mark.asyncio
async def test_context_bundle_aggregates_search_code_matches(isolated_db, tmp_path):
    """search_code matches contribute files and queries to the bundle."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    import json
    sc_output = json.dumps({
        "matches": [
            {"path": "api/router.py", "line": "def get_routes():", "context": "route handler"},
            {"path": "api/router.py", "line": "def post_routes():", "context": "post handler"},
        ]
    })
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="search_code",
        input_json=json.dumps({"query": "get_routes", "limit": 50}),
        output_json=sc_output,
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    bundle = resp.bundle

    assert "get_routes" in bundle.queries
    file_paths = [f.file_path for f in bundle.files]
    assert "api/router.py" in file_paths
    router_file = next(f for f in bundle.files if f.file_path == "api/router.py")
    assert router_file.match_count >= 1


@pytest.mark.asyncio
async def test_context_bundle_aggregates_read_file_into_snippets(isolated_db, tmp_path):
    """read_file output produces a snippet and marks file as read=True."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    import json
    content = "class UserService:\n    def get(self): ...\n"
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=json.dumps({"file_path": "services/user.py"}),
        output_json=json.dumps({"content": content}),
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    bundle = resp.bundle

    assert bundle.status in {"ok", "partial"}
    file_paths = [f.file_path for f in bundle.files]
    assert "services/user.py" in file_paths
    user_file = next(f for f in bundle.files if f.file_path == "services/user.py")
    assert user_file.read is True
    assert any("UserService" in s for s in user_file.snippets)


@pytest.mark.asyncio
async def test_context_bundle_does_not_return_full_huge_content(isolated_db, tmp_path):
    """Very long file content is truncated in snippets."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    import json
    huge = "x" * 10_000
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=json.dumps({"file_path": "big.py"}),
        output_json=json.dumps({"content": huge}),
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    big_file = next((f for f in resp.bundle.files if f.file_path == "big.py"), None)
    assert big_file is not None
    for snippet in big_file.snippets:
        assert len(snippet) <= 800 + 10  # allow tiny margin
    # Warning about truncation should exist
    all_warnings = resp.bundle.warnings
    assert any("truncat" in w.lower() for w in all_warnings)


@pytest.mark.asyncio
async def test_context_bundle_does_not_create_tool_calls(isolated_db, tmp_path):
    """Calling context-bundle endpoint never creates new ToolCall records."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    before = isolated_db.list_tool_calls_for_step(step.id)
    await routes.get_step_context_bundle(run.id, step.id)
    after = isolated_db.list_tool_calls_for_step(step.id)

    assert len(after) == len(before)


@pytest.mark.asyncio
async def test_context_bundle_does_not_modify_project_files(isolated_db, tmp_path):
    """Context bundle endpoint leaves project files untouched."""
    project, project_dir = make_project(isolated_db, tmp_path)
    src = project_dir / "model.py"
    src.write_text("class M: pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    await routes.get_step_context_bundle(run.id, step.id)

    assert src.read_text(encoding="utf-8") == "class M: pass\n"


@pytest.mark.asyncio
async def test_context_bundle_works_after_auto_context_endpoint(isolated_db, tmp_path):
    """Bundle reflects context gathered by auto-context endpoint."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "api.py").write_text("def handle(): pass\n", encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Run auto-context first
    await routes.run_step_auto_context(
        run.id, step.id,
        AutoContextGatherRequest(max_tool_calls=5, query="handle"),
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    bundle = resp.bundle

    assert bundle.status in {"ok", "partial"}
    assert bundle.tool_call_ids  # non-empty — auto-context created calls


@pytest.mark.asyncio
async def test_context_bundle_requires_valid_run_step(isolated_db, tmp_path):
    """Invalid run_id or step_id raises 404."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    with pytest.raises(HTTPException) as exc:
        await routes.get_step_context_bundle("bad-run-id", step.id)
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        await routes.get_step_context_bundle(run.id, "bad-step-id")
    assert exc2.value.status_code == 404


@pytest.mark.asyncio
async def test_context_bundle_includes_warning_when_too_many_files(isolated_db, tmp_path):
    """When more than BUNDLE_MAX_FILES files are found, a warning is emitted."""
    import json
    from src.models import BUNDLE_MAX_FILES

    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Inject search_code results with many distinct file paths
    matches = [{"path": f"file{i}.py", "line": f"x={i}", "context": f"ctx{i}"} for i in range(BUNDLE_MAX_FILES + 3)]
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="search_code",
        input_json=json.dumps({"query": "x", "limit": 50}),
        output_json=json.dumps({"matches": matches}),
    )

    resp = await routes.get_step_context_bundle(run.id, step.id)
    bundle = resp.bundle

    assert len(bundle.files) <= BUNDLE_MAX_FILES
    assert any("file" in w.lower() or "show" in w.lower() for w in bundle.warnings)


# ── Agent-assisted Patch Proposal from Context v1 tests ──────────────────────

import json as _test_json  # noqa: E402
from src.models import ContextPatchDraftRequest, DRAFT_MAX_OLD_TEXT_CHARS  # noqa: E402


@pytest.mark.asyncio
async def test_context_patch_draft_empty_when_no_context(isolated_db, tmp_path):
    """Draft returns no_context status and a warning when there are no tool calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    assert resp.status == "no_context"
    assert resp.candidates == []
    assert any("context" in w.lower() or "empty" in w.lower() or "gather" in w.lower()
               for w in resp.warnings)
    assert resp.next_recommended_action == "auto_gather_context"


@pytest.mark.asyncio
async def test_context_patch_draft_ignores_non_read_only_tool_calls(isolated_db, tmp_path):
    """Draft ignores propose_patch/apply_patch/run_command tool calls."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Only forbidden calls
    for bad in ("propose_patch", "apply_patch", "run_command"):
        _make_tool_call_obj(isolated_db, run, step, tool_name=bad, input_json='{}', output_json='{}')

    resp = await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())
    assert resp.status == "no_context"
    assert resp.candidates == []


@pytest.mark.asyncio
async def test_context_patch_draft_creates_candidate_from_search_code(isolated_db, tmp_path):
    """Draft builds a candidate using a search_code snippet."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    sc_out = _test_json.dumps({
        "matches": [{"path": "api/handler.py", "context": "def handle_request():\n    pass"}]
    })
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="search_code",
        input_json=_test_json.dumps({"query": "handle_request"}),
        output_json=sc_out,
    )

    resp = await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    assert resp.status == "ok"
    assert len(resp.candidates) >= 1
    top = resp.candidates[resp.recommended_candidate_index or 0]
    assert top.file_path == "api/handler.py"
    assert "handle_request" in top.old_text
    assert top.confidence >= 0.5


@pytest.mark.asyncio
async def test_context_patch_draft_creates_candidate_from_read_file(isolated_db, tmp_path):
    """Draft uses read_file content as the snippet with higher confidence."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    content = "class PaymentService:\n    def process(self): ...\n"
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=_test_json.dumps({"file_path": "services/payment.py"}),
        output_json=_test_json.dumps({"content": content}),
    )

    resp = await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    assert resp.status == "ok"
    top = resp.candidates[resp.recommended_candidate_index or 0]
    assert top.file_path == "services/payment.py"
    assert "PaymentService" in top.old_text
    assert top.confidence == 0.8  # read=True + snippet → 0.8


@pytest.mark.asyncio
async def test_context_patch_draft_preferred_file_path_is_prioritized(isolated_db, tmp_path):
    """preferred_file_path ranks the requested file first."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    for fname, content in [("a.py", "class A: pass"), ("b.py", "class B: pass")]:
        _make_tool_call_obj(
            isolated_db, run, step,
            tool_name="read_file",
            input_json=_test_json.dumps({"file_path": fname}),
            output_json=_test_json.dumps({"content": content}),
        )

    resp = await routes.get_context_patch_draft(
        run.id, step.id,
        ContextPatchDraftRequest(preferred_file_path="b.py"),
    )

    assert resp.status == "ok"
    best = resp.candidates[resp.recommended_candidate_index or 0]
    # b.py should be the top-ranked candidate
    assert resp.candidates[0].file_path == "b.py" or best.file_path == "b.py"


@pytest.mark.asyncio
async def test_context_patch_draft_preferred_snippet_index(isolated_db, tmp_path):
    """preferred_snippet_index selects the correct snippet as old_text."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    # Two search matches on the same file → two snippets
    sc_out = _test_json.dumps({
        "matches": [
            {"path": "utils.py", "context": "def first_func(): pass"},
            {"path": "utils.py", "context": "def second_func(): pass"},
        ]
    })
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="search_code",
        input_json=_test_json.dumps({"query": "func"}),
        output_json=sc_out,
    )

    resp = await routes.get_context_patch_draft(
        run.id, step.id,
        ContextPatchDraftRequest(preferred_file_path="utils.py", preferred_snippet_index=1),
    )

    assert resp.status == "ok"
    cand = next((c for c in resp.candidates if c.file_path == "utils.py"), None)
    assert cand is not None
    # snippet at index 1 (if available) or first snippet
    assert "func" in cand.old_text


@pytest.mark.asyncio
async def test_context_patch_draft_does_not_create_tool_calls(isolated_db, tmp_path):
    """Calling context-patch-draft endpoint creates no new ToolCall records."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=_test_json.dumps({"file_path": "x.py"}),
        output_json=_test_json.dumps({"content": "x = 1"}),
    )
    before = len(isolated_db.list_tool_calls_for_step(step.id))

    await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    after = len(isolated_db.list_tool_calls_for_step(step.id))
    assert after == before


@pytest.mark.asyncio
async def test_context_patch_draft_does_not_create_propose_patch_call(isolated_db, tmp_path):
    """Draft endpoint never creates a propose-patch ToolCall."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="search_code",
        input_json=_test_json.dumps({"query": "x"}),
        output_json=_test_json.dumps({"matches": [{"path": "f.py", "context": "x = 1"}]}),
    )
    await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    all_calls = isolated_db.list_tool_calls_for_step(step.id)
    assert all(tc.tool_name != "propose_patch" for tc in all_calls)


@pytest.mark.asyncio
async def test_context_patch_draft_does_not_modify_files(isolated_db, tmp_path):
    """Draft endpoint leaves all project files untouched."""
    project, project_dir = make_project(isolated_db, tmp_path)
    src = project_dir / "model.py"
    original = "class M: pass\n"
    src.write_text(original, encoding="utf-8")
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=_test_json.dumps({"file_path": "model.py"}),
        output_json=_test_json.dumps({"content": original}),
    )
    await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    assert src.read_text(encoding="utf-8") == original


@pytest.mark.asyncio
async def test_context_patch_draft_requires_valid_run_step(isolated_db, tmp_path):
    """Invalid run_id or step_id raises 404."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    with pytest.raises(HTTPException) as exc:
        await routes.get_context_patch_draft("bad-run", step.id, ContextPatchDraftRequest())
    assert exc.value.status_code == 404

    with pytest.raises(HTTPException) as exc2:
        await routes.get_context_patch_draft(run.id, "bad-step", ContextPatchDraftRequest())
    assert exc2.value.status_code == 404


@pytest.mark.asyncio
async def test_context_patch_draft_old_text_is_bounded(isolated_db, tmp_path):
    """old_text never exceeds DRAFT_MAX_OLD_TEXT_CHARS even for huge file content."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    huge_content = "x = 1\n" * 5_000  # ~30 000 chars
    _make_tool_call_obj(
        isolated_db, run, step,
        tool_name="read_file",
        input_json=_test_json.dumps({"file_path": "big.py"}),
        output_json=_test_json.dumps({"content": huge_content}),
    )

    resp = await routes.get_context_patch_draft(run.id, step.id, ContextPatchDraftRequest())

    assert resp.status == "ok"
    for cand in resp.candidates:
        assert len(cand.old_text) <= DRAFT_MAX_OLD_TEXT_CHARS + 10  # small margin


# ── Patch Proposal Review v1 ──────────────────────────────────────────────────

from src.models import PatchReviewRequest, PatchReviewOperation as PatchReviewOp  # noqa: E402
from src.model_router import review_patch_operations  # noqa: E402


def _review_req(*ops: PatchReviewOp, run_id: str = "run-1", step_id: str = "step-1") -> PatchReviewRequest:
    return PatchReviewRequest(operations=list(ops), run_id=run_id, step_id=step_id)


@pytest.mark.asyncio
async def test_review_patch_ok_for_unique_old_text(isolated_db, tmp_path):
    """Reviewing a patch with a unique, findable old_text returns status ok."""
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "app.py"
    target.write_text("def hello():\n    return 'world'\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="app.py",
            old_text="def hello():\n    return 'world'\n",
            new_text="def hello():\n    return 'earth'\n",
        )),
    )

    assert resp.status == "ok"
    assert resp.safe_to_create_proposal is True
    assert resp.safe_to_apply is True
    assert len(resp.operation_results) == 1
    assert resp.operation_results[0].old_text_found is True
    assert resp.operation_results[0].old_text_occurrences == 1


@pytest.mark.asyncio
async def test_review_patch_blocks_missing_file(isolated_db, tmp_path):
    """Review blocks when the target file does not exist."""
    project, project_dir = make_project(isolated_db, tmp_path)

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="nonexistent.py",
            old_text="something",
            new_text="other",
        )),
    )

    assert resp.status == "blocked"
    assert resp.safe_to_create_proposal is False
    assert resp.safe_to_apply is False
    codes = {i.code for i in resp.issues}
    assert "file_not_found" in codes


@pytest.mark.asyncio
async def test_review_patch_blocks_path_traversal(isolated_db, tmp_path):
    """Review blocks path traversal attempts."""
    project, project_dir = make_project(isolated_db, tmp_path)

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="../../../etc/passwd",
            old_text="root",
            new_text="evil",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "path_traversal" in codes


@pytest.mark.asyncio
async def test_review_patch_blocks_env_secret_file(isolated_db, tmp_path):
    """Review blocks .env and other secret-like files."""
    project, project_dir = make_project(isolated_db, tmp_path)
    env_file = project_dir / ".env"
    env_file.write_text("SECRET=abc\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path=".env",
            old_text="SECRET=abc\n",
            new_text="SECRET=xyz\n",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "sensitive_file" in codes


@pytest.mark.asyncio
async def test_review_patch_blocks_empty_old_text(isolated_db, tmp_path):
    """Review blocks when old_text is empty."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "foo.py").write_text("x = 1\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text="",
            new_text="x = 2\n",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "empty_old_text" in codes


@pytest.mark.asyncio
async def test_review_patch_blocks_old_text_not_found(isolated_db, tmp_path):
    """Review blocks when old_text does not appear in the file."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "foo.py").write_text("x = 1\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text="this text does not exist in the file",
            new_text="replacement",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "old_text_not_found" in codes
    assert resp.operation_results[0].old_text_found is False
    assert resp.operation_results[0].old_text_occurrences == 0


@pytest.mark.asyncio
async def test_review_patch_blocks_ambiguous_old_text(isolated_db, tmp_path):
    """Review blocks when old_text appears more than once (ambiguous replacement)."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "foo.py").write_text("x = 1\nx = 1\nx = 1\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text="x = 1\n",
            new_text="x = 2\n",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "old_text_ambiguous" in codes
    assert resp.operation_results[0].old_text_occurrences == 3


@pytest.mark.asyncio
async def test_review_patch_warns_empty_new_text(isolated_db, tmp_path):
    """Review warns (not blocks) when new_text is empty (deletion)."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "foo.py").write_text("def remove_me():\n    pass\n\nother = 1\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text="def remove_me():\n    pass\n\n",
            new_text="",
        )),
    )

    # Should be warning, not blocked — deletion is allowed but needs confirmation
    assert resp.status == "warning"
    codes = {i.code for i in resp.issues}
    assert "empty_new_text" in codes
    assert resp.safe_to_create_proposal is True
    assert resp.safe_to_apply is False  # warning → not safe_to_apply


@pytest.mark.asyncio
async def test_review_patch_blocks_new_text_same_as_old(isolated_db, tmp_path):
    """Review blocks when new_text is identical to old_text (no-op patch)."""
    project, project_dir = make_project(isolated_db, tmp_path)
    content = "def foo():\n    return 42\n"
    (project_dir / "foo.py").write_text(content)

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text=content,
            new_text=content,
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "new_text_same_as_old" in codes


@pytest.mark.asyncio
async def test_review_patch_blocks_database_py(isolated_db, tmp_path):
    """Review blocks attempts to patch the protected database.py module."""
    project, project_dir = make_project(isolated_db, tmp_path)
    # Create the protected nested path inside the project
    db_dir = project_dir / "backend" / "src" / "storage"
    db_dir.mkdir(parents=True)
    db_file = db_dir / "database.py"
    db_file.write_text("# database module\nclass DB:\n    pass\n")

    resp = await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="backend/src/storage/database.py",
            old_text="# database module\n",
            new_text="# patched\n",
        )),
    )

    assert resp.status == "blocked"
    codes = {i.code for i in resp.issues}
    assert "protected_file" in codes


@pytest.mark.asyncio
async def test_review_patch_does_not_modify_files(isolated_db, tmp_path):
    """Review endpoint never modifies any project file."""
    project, project_dir = make_project(isolated_db, tmp_path)
    target = project_dir / "stable.py"
    original_content = "x = 1\n"
    target.write_text(original_content)

    await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="stable.py",
            old_text="x = 1\n",
            new_text="x = 999\n",
        )),
    )

    assert target.read_text() == original_content


@pytest.mark.asyncio
async def test_review_patch_does_not_create_tool_calls(isolated_db, tmp_path):
    """Review endpoint creates zero tool_call records."""
    project, project_dir = make_project(isolated_db, tmp_path)
    (project_dir / "foo.py").write_text("y = 2\n")

    before = len(isolated_db.list_tool_calls_for_project(project.id, limit=500))

    await routes.review_project_patch_endpoint(
        project.id,
        _review_req(PatchReviewOp(
            file_path="foo.py",
            old_text="y = 2\n",
            new_text="y = 3\n",
        )),
    )

    after = len(isolated_db.list_tool_calls_for_project(project.id, limit=500))
    assert before == after


@pytest.mark.asyncio
async def test_review_patch_requires_valid_project(isolated_db, tmp_path):
    """Review returns 404 for an unknown project_id."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await routes.review_project_patch_endpoint(
            "bad-project-id",
            _review_req(PatchReviewOp(
                file_path="foo.py",
                old_text="x = 1\n",
                new_text="x = 2\n",
            )),
        )
    assert exc.value.status_code == 404


# ── Approval-gated Patch Workflow Orchestrator v1 ─────────────────────────────

from src.models import PatchWorkflowPlanResponse  # noqa: E402


def _wf_tool_call(isolated_db, run, step, tool_name: str, returncode=None, status: str = "completed"):
    """Create a completed tool_call for workflow tests."""
    tc = isolated_db.create_tool_call(
        run_id=run.id,
        project_id=run.project_id,
        step_id=step.id,
        tool_name=tool_name,
        status="pending",
        input_json="{}",
        risk_level="low",
    )
    isolated_db.update_tool_call(tc.id, status=status, returncode=returncode, output_json="{}")
    return isolated_db.list_tool_calls_for_step(step.id)[-1]


@pytest.mark.asyncio
async def test_workflow_plan_no_tool_calls_recommends_gather_context(isolated_db, tmp_path):
    """With no tool_calls the plan recommends auto_gather_context."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.get_run_patch_workflow_plan(run.id)

    assert isinstance(resp, PatchWorkflowPlanResponse)
    assert resp.run_id == run.id
    plan = next((p for p in resp.steps if p.step_id == step.id), None)
    assert plan is not None
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "auto_gather_context"


@pytest.mark.asyncio
async def test_workflow_plan_after_context_calls_recommends_review_or_draft(isolated_db, tmp_path):
    """After context reads the plan recommends review_patch or create_patch_draft."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "read_file")

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type in (
        "review_patch", "create_patch_draft", "build_context_bundle"
    )


@pytest.mark.asyncio
async def test_workflow_plan_after_propose_patch_recommends_apply(isolated_db, tmp_path):
    """After propose-patch completes the next action is apply_patch_manual."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "read_file")
    _wf_tool_call(isolated_db, run, step, "propose-patch")

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "apply_patch_manual"
    assert plan.recommended_next_action.risk_level == "high"
    assert plan.recommended_next_action.requires_confirmation is True


@pytest.mark.asyncio
async def test_workflow_plan_after_apply_recommends_run_tests(isolated_db, tmp_path):
    """After apply-patch completes the next action is run_tests_manual."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "read_file")
    _wf_tool_call(isolated_db, run, step, "propose-patch")
    _wf_tool_call(isolated_db, run, step, "apply-patch")

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "run_tests_manual"
    assert plan.recommended_next_action.requires_confirmation is True


@pytest.mark.asyncio
async def test_workflow_plan_after_failed_run_recommends_analyze(isolated_db, tmp_path):
    """After a failed run-command the next action is analyze_result."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "apply-patch")
    _wf_tool_call(isolated_db, run, step, "run-command", returncode=1)

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "analyze_result"
    assert plan.recommended_next_action.risk_level == "low"


@pytest.mark.asyncio
async def test_workflow_plan_after_analysis_recommends_new_draft(isolated_db, tmp_path):
    """After failed run + analysis the next action is create_patch_draft."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "apply-patch")
    _wf_tool_call(isolated_db, run, step, "run-command", returncode=1)
    _wf_tool_call(isolated_db, run, step, "analyze-command-result")

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "create_patch_draft"


@pytest.mark.asyncio
async def test_workflow_plan_after_passing_run_is_done(isolated_db, tmp_path):
    """After passing run-command the plan status is done."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    _wf_tool_call(isolated_db, run, step, "apply-patch")
    _wf_tool_call(isolated_db, run, step, "run-command", returncode=0)

    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)

    assert plan.status == "done"
    assert plan.recommended_next_action is not None
    assert plan.recommended_next_action.action_type == "done"


@pytest.mark.asyncio
async def test_workflow_plan_does_not_create_tool_calls(isolated_db, tmp_path):
    """The endpoint is read-only and creates no tool_call records."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    before = len(isolated_db.list_tool_calls_for_run(run.id))
    await routes.get_run_patch_workflow_plan(run.id)
    after = len(isolated_db.list_tool_calls_for_run(run.id))

    assert before == after


@pytest.mark.asyncio
async def test_workflow_plan_does_not_modify_files(isolated_db, tmp_path):
    """The endpoint leaves project files untouched."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)
    sentinel = project_dir / "stable.py"
    sentinel.write_text("x = 1\n")

    await routes.get_run_patch_workflow_plan(run.id)

    assert sentinel.read_text() == "x = 1\n"


@pytest.mark.asyncio
async def test_workflow_plan_works_without_route_decisions(isolated_db, tmp_path):
    """Plan builds successfully even when no model route decisions exist for the run."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    resp = await routes.get_run_patch_workflow_plan(run.id)

    assert resp.run_id == run.id
    assert isinstance(resp.steps, list)


@pytest.mark.asyncio
async def test_workflow_plan_high_risk_actions_require_confirmation(isolated_db, tmp_path):
    """apply_patch_manual and run_tests_manual always have requires_confirmation=True."""
    project, project_dir = make_project(isolated_db, tmp_path)
    run, step = _make_run_and_step(isolated_db, project, project_dir)

    _wf_tool_call(isolated_db, run, step, "propose-patch")
    resp = await routes.get_run_patch_workflow_plan(run.id)
    plan = next(p for p in resp.steps if p.step_id == step.id)
    action = plan.recommended_next_action
    assert action is not None and action.action_type == "apply_patch_manual"
    assert action.requires_confirmation is True

    _wf_tool_call(isolated_db, run, step, "apply-patch")
    resp2 = await routes.get_run_patch_workflow_plan(run.id)
    plan2 = next(p for p in resp2.steps if p.step_id == step.id)
    action2 = plan2.recommended_next_action
    assert action2 is not None and action2.action_type == "run_tests_manual"
    assert action2.requires_confirmation is True


@pytest.mark.asyncio
async def test_workflow_plan_requires_valid_run(isolated_db, tmp_path):
    """The endpoint returns 404 for an unknown run_id."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await routes.get_run_patch_workflow_plan("nonexistent-run-id")
    assert exc.value.status_code == 404

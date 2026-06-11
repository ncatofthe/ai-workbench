from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

from src.api import routes
from src.models import ApprovalDecision, CreateRunRequest
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


def make_project_dir(tmp_path: Path) -> Path:
    project_dir = tmp_path / "Проект With Spaces"
    project_dir.mkdir()
    return project_dir


def test_project_create_list_get_update_with_json_fields(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)

    project = isolated_db.create_project(
        name="Todo",
        path=str(project_dir),
        description="Demo",
        stack="python",
        package_manager="pip",
        test_command="python -m pytest",
        build_command="python -m compileall src",
        safe_commands=["python -m pytest"],
        blocked_commands=["rm", "git push"],
        ignore_paths=[".venv", "node_modules"],
    )

    assert project.path == str(project_dir.resolve())
    assert project.safe_commands == ["python -m pytest"]
    assert project.blocked_commands == ["rm", "git push"]

    listed = isolated_db.list_projects()
    assert listed[0].ignore_paths == [".venv", "node_modules"]

    loaded = isolated_db.get_project(project.id)
    assert loaded is not None
    assert loaded.stack == "python"

    updated = isolated_db.update_project(
        project.id,
        stack="fastapi",
        safe_commands=["bash scripts/run_tests.sh"],
    )
    assert updated is not None
    assert updated.stack == "fastapi"
    assert updated.safe_commands == ["bash scripts/run_tests.sh"]
    assert updated.updated_at is not None


def test_invalid_project_paths_are_rejected(isolated_db, tmp_path):
    file_path = tmp_path / "not-a-directory.txt"
    file_path.write_text("x", encoding="utf-8")

    invalid_paths = [
        "relative/path",
        str(tmp_path / "missing"),
        str(file_path),
        "/",
        str(Path.home()),
    ]

    for path in invalid_paths:
        with pytest.raises(ValueError):
            isolated_db.create_project(name="Bad", path=path)


@pytest.mark.asyncio
async def test_run_creation_stores_valid_project_context_and_rejects_unknown_project(
    isolated_db,
    tmp_path,
    monkeypatch,
):
    project_dir = make_project_dir(tmp_path)
    project = isolated_db.create_project(name="Todo", path=str(project_dir))

    captured = {}

    async def fake_execute_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(routes, "execute_run", fake_execute_run)

    with pytest.raises(HTTPException) as exc:
        await routes.post_run(CreateRunRequest(prompt="Plan", project_id="missing"))
    assert exc.value.status_code == 404

    run = await routes.post_run(CreateRunRequest(prompt="Plan", project_id=project.id))
    await asyncio.sleep(0)

    stored = isolated_db.get_run(run.id)
    assert stored is not None
    assert stored.project_id == project.id
    assert stored.project_path == str(project_dir.resolve())
    assert captured["project_id"] == project.id
    assert captured["project_path"] == str(project_dir.resolve())


@pytest.mark.asyncio
async def test_project_workspace_status_on_non_git_dir_does_not_crash(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)
    project = isolated_db.create_project(name="Plain", path=str(project_dir))

    status = await routes.project_workspace_status(project.id)

    assert status["cwd"] == str(project_dir.resolve())
    assert status["returncode"] != 0
    assert "not a git repository" in status["error"].lower()


@pytest.mark.asyncio
async def test_blocked_and_dangerous_project_commands_do_not_execute(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)
    marker = project_dir / "marker.txt"
    project = isolated_db.create_project(
        name="Blocked",
        path=str(project_dir),
        test_command="python -c \"from pathlib import Path; Path('marker.txt').write_text('ran')\"",
        build_command="python -m pip install example-package",
        blocked_commands=["python"],
    )

    blocked = await routes.run_project_tests(project.id)
    assert blocked["approval_required"] is True
    assert blocked["action"] == "blocked_command"
    assert not marker.exists()

    dangerous_project_dir = tmp_path / "Dangerous Project"
    dangerous_project_dir.mkdir()
    dangerous_project = isolated_db.create_project(
        name="Dangerous",
        path=str(dangerous_project_dir),
        build_command="python -m pip install example-package",
    )

    dangerous = await routes.run_project_build(dangerous_project.id)
    assert dangerous["approval_required"] is True
    assert dangerous["action"] == "package_install"


@pytest.mark.asyncio
async def test_unlisted_non_dangerous_command_requires_approval_and_does_not_execute(
    isolated_db,
    tmp_path,
):
    project_dir = make_project_dir(tmp_path)
    marker = project_dir / "marker.txt"
    command = f"{sys.executable} -c \"from pathlib import Path; Path('marker.txt').write_text('ran')\""
    project = isolated_db.create_project(
        name="Unlisted",
        path=str(project_dir),
        test_command=command,
        safe_commands=["python -c \"print('different command')\""],
    )

    result = await routes.run_project_tests(project.id)

    assert result["approval_required"] is True
    assert result["approval_id"]
    assert result["action"] == "command_not_allowed"
    assert not marker.exists()

    approvals = isolated_db.list_approvals()
    assert len(approvals) == 1
    assert approvals[0].id == result["approval_id"]
    assert approvals[0].run_id == f"project:{project.id}"
    assert approvals[0].action == "command_not_allowed"
    assert approvals[0].command == command
    assert approvals[0].status == "pending"
    assert "Project tool action requires approval" in approvals[0].description


@pytest.mark.asyncio
async def test_repeated_project_command_reuses_pending_approval(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)
    command = f"{sys.executable} -c \"print('needs approval')\""
    project = isolated_db.create_project(
        name="Duplicate Approval",
        path=str(project_dir),
        test_command=command,
        safe_commands=[],
    )

    first = await routes.run_project_tests(project.id)
    second = await routes.run_project_tests(project.id)

    assert first["approval_required"] is True
    assert second["approval_required"] is True
    assert second["approval_id"] == first["approval_id"]
    assert len(isolated_db.list_approvals()) == 1


@pytest.mark.asyncio
async def test_approved_project_command_executes_once(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)
    marker = project_dir / "marker.txt"
    command = (
        f"{sys.executable} -c \"from pathlib import Path; "
        "p=Path('marker.txt'); "
        "p.write_text(str((int(p.read_text()) if p.exists() else 0)+1))\""
    )
    project = isolated_db.create_project(
        name="Approve Execute",
        path=str(project_dir),
        test_command=command,
        safe_commands=[],
    )

    requested = await routes.run_project_tests(project.id)
    assert requested["approval_required"] is True
    assert not marker.exists()

    approved = await routes.approve(requested["approval_id"], ApprovalDecision())
    assert approved["already_resolved"] is False
    assert approved["approval"].status.value == "approved"
    assert approved["execution"]["status"] == "passed"
    assert approved["execution"]["approval_id"] == requested["approval_id"]
    assert approved["execution"]["tool_call_id"]
    assert marker.read_text(encoding="utf-8") == "1"

    calls = isolated_db.list_project_tool_calls(project.id)
    assert len(calls) == 1
    assert calls[0].id == approved["execution"]["tool_call_id"]
    assert calls[0].approval_id == requested["approval_id"]
    assert calls[0].run_id == f"project:{project.id}"
    assert calls[0].tool_name == "project_test"
    assert calls[0].cwd == str(project_dir.resolve())

    approved_again = await routes.approve(requested["approval_id"], ApprovalDecision())
    assert approved_again["already_resolved"] is True
    assert approved_again["execution"] is None
    assert marker.read_text(encoding="utf-8") == "1"
    assert len(isolated_db.list_project_tool_calls(project.id)) == 1


@pytest.mark.asyncio
async def test_safe_listed_command_executes(isolated_db, tmp_path):
    project_dir = make_project_dir(tmp_path)
    marker = project_dir / "marker.txt"
    command = f"{sys.executable} -c \"from pathlib import Path; Path('marker.txt').write_text('ran')\""
    project = isolated_db.create_project(
        name="Safe",
        path=str(project_dir),
        test_command=command,
        safe_commands=[command],
    )

    result = await routes.run_project_tests(project.id)

    assert result["approval_required"] is False
    assert result["tool_call_id"]
    assert result["status"] == "passed"
    assert marker.read_text(encoding="utf-8") == "ran"

    calls = await routes.get_project_tool_calls(project.id)
    assert len(calls) == 1
    assert calls[0].id == result["tool_call_id"]
    assert calls[0].project_id == project.id
    assert calls[0].command == command
    assert calls[0].status == "passed"
    assert calls[0].returncode == 0

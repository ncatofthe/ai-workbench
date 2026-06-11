from __future__ import annotations

from pathlib import Path

from src.agents.registry import load_agent_instructions
from src.storage import database
from src.utils import config
from src.utils.paths import PROJECT_ROOT, resolve_runtime_path


def test_default_runtime_paths_are_repo_anchored():
    assert Path(database.DB_PATH).is_absolute()
    assert Path(database.DB_PATH) == PROJECT_ROOT / "data" / "workbench.db"
    assert config.CONFIG_PATH.is_absolute()
    assert config.CONFIG_PATH == PROJECT_ROOT / "config.yaml"


def test_relative_runtime_path_resolves_under_project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    resolved = resolve_runtime_path("runs/example", "runs")

    assert resolved == PROJECT_ROOT / "runs" / "example"


def test_agent_instructions_load_from_non_repo_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    instructions = load_agent_instructions("orchestrator")

    assert "# Orchestrator Agent" in instructions


def test_created_run_dir_stays_repo_relative_when_cwd_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    monkeypatch.chdir(tmp_path)
    database.init_db()

    run = database.create_run(prompt="Check path anchoring")
    resolved_run_dir = resolve_runtime_path(run.run_dir, "runs")

    assert run.run_dir.startswith("runs/")
    assert resolved_run_dir.parent == PROJECT_ROOT / "runs"

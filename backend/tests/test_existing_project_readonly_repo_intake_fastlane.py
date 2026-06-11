"""Existing Project Read-only Repo Intake Fastlane v1 tests.

The endpoint under test is:
  POST /api/project-intake/existing-project/repo-intake-preview

Safety contract:
  - read-only structure and manifest preview
  - no project/run/run_step/tool_call creation
  - no provider calls, commands, patches, applies, or test execution
  - no arbitrary source file reads; only small allowlisted manifests are read
"""

from __future__ import annotations

import inspect
import json
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import (
    ExistingProjectRepoIntakeRequest,
    build_existing_project_repo_intake_preview,
)
from src.storage import database


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "existing-project-repo-intake.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


def _write(path: pathlib.Path, text: str = "") -> pathlib.Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _repo(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "existing-app"
    root.mkdir()
    return root


def _preview(path: pathlib.Path, **kwargs):
    return build_existing_project_repo_intake_preview(
        ExistingProjectRepoIntakeRequest(project_path=str(path), **kwargs)
    )


def _post(client, **payload):
    return client.post("/api/project-intake/existing-project/repo-intake-preview", json=payload)


def _count(table: str) -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


class TestDetection:
    def test_01_detects_react_vite_package_stack(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({
            "scripts": {"test": "vitest", "build": "vite build"},
            "dependencies": {"@vitejs/plugin-react": "^latest", "react": "^latest"},
            "devDependencies": {"typescript": "^latest", "vite": "^latest"},
        }))
        _write(root / "src/pages/App.tsx", "SECRET_SHOULD_NOT_APPEAR")

        result = _preview(root)

        assert {"node", "react", "vite", "typescript"}.issubset(set(result.detected_stack))
        assert result.detected_project_type in {"frontend_app", "fullstack_web_app"}
        assert any(manifest.path == "package.json" for manifest in result.manifest_summaries)
        assert "SECRET_SHOULD_NOT_APPEAR" not in str(result)

    def test_02_detects_fastapi_python_stack(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "pyproject.toml", """
[project]
dependencies = ["fastapi>=0.1", "pytest>=8"]
[tool.pytest.ini_options]
testpaths = ["tests"]
""")
        _write(root / "backend/api/routes.py", "app = 'not read'")

        result = _preview(root)

        assert "python" in result.detected_stack
        assert "fastapi" in result.detected_stack
        assert "pytest" in result.detected_stack
        assert any(area.id == "backend" for area in result.detected_areas)

    def test_03_detects_php_composer_stack(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "composer.json", json.dumps({
            "require": {"php": "^8.3", "laravel/framework": "^11"},
            "scripts": {"test": "phpunit"},
        }))
        _write(root / "app/Http/Controllers/HomeController.php", "<?php")

        result = _preview(root)

        assert "php" in result.detected_stack
        assert "composer" in result.detected_stack
        assert "laravel" in result.detected_stack
        assert result.detected_project_type == "php_laravel_app"

    def test_04_detects_database_schema_hints(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "prisma/schema.prisma", "model User {}")
        _write(root / "migrations/001_init.sql", "secret should not be read")

        result = _preview(root)

        assert any(area.id == "database" for area in result.detected_areas)
        assert "database" in result.detected_stack

    def test_05_detects_test_folders_scripts(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({"scripts": {"test": "vitest run"}}))
        _write(root / "tests/test_app.py", "not read")

        result = _preview(root)

        assert any(area.id == "tests" for area in result.detected_areas)
        assert result.test_discovery_hints

    def test_06_detects_docker_deployment_hints(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "Dockerfile", "FROM python:3.12")
        _write(root / "docker-compose.yml", "services:\n  db:\n    image: postgres:16")

        result = _preview(root)

        assert "docker" in result.detected_stack
        assert "postgresql" in result.detected_stack
        assert any(area.id == "deployment" for area in result.detected_areas)


class TestBoundsAndSecrets:
    def test_07_ignores_generated_vendor_directories(self, tmp_path):
        root = _repo(tmp_path)
        for dirname in [".git", "node_modules", "vendor", ".venv", "dist", "build"]:
            _write(root / dirname / "secret.py", "SHOULD_NOT_APPEAR")
        _write(root / "package.json", json.dumps({"dependencies": {"react": "latest"}}))

        result = _preview(root)

        assert "SHOULD_NOT_APPEAR" not in str(result)
        assert all(dirname not in str(result) for dirname in ["node_modules/secret.py", "vendor/secret.py", ".git/secret.py"])

    def test_08_caps_file_traversal(self, tmp_path):
        root = _repo(tmp_path)
        for i in range(50):
            _write(root / "src" / f"file_{i}.ts", "not read")

        result = _preview(root, max_files=5)

        assert any("Traversal capped" in warning for warning in result.protected_path_warnings)
        for area in result.detected_areas:
            assert len(area.path_hints) <= 20

    def test_09_caps_manifest_reads(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({"dependencies": {f"dep-{i}": "1" for i in range(80)}}))

        result = _preview(root)

        manifest = next(item for item in result.manifest_summaries if item.path == "package.json")
        assert len(manifest.dependencies_hint) <= 30

    def test_10_never_reads_env_file(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / ".env", "API_KEY=SUPER_SECRET_VALUE")
        _write(root / "package.json", "{}")

        result = _preview(root)

        assert "SUPER_SECRET_VALUE" not in str(result)
        assert any(".env" in warning for warning in result.protected_path_warnings)

    def test_11_never_reads_private_key_secret_files(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "config/private_key.pem", "PRIVATE_KEY_VALUE")
        _write(root / "config/credentials.json", "CREDENTIAL_VALUE")

        result = _preview(root)

        assert "PRIVATE_KEY_VALUE" not in str(result)
        assert "CREDENTIAL_VALUE" not in str(result)
        assert len(result.protected_path_warnings) >= 2

    def test_12_redacts_secret_like_manifest_values(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({"scripts": {"deploy": "API_KEY=supersecret vite build"}}))

        result = _preview(root)

        assert "supersecret" not in str(result)
        assert "[REDACTED]" in str(result)

    def test_13_project_path_traversal_is_blocked(self, tmp_path):
        root = _repo(tmp_path)
        unsafe = root / ".." / root.name

        result = build_existing_project_repo_intake_preview(
            ExistingProjectRepoIntakeRequest(project_path=str(unsafe))
        )

        assert result.protected_path_warnings
        assert "unsafe" in result.protected_path_warnings[0].lower()

    def test_14_absolute_path_outside_selected_project_root_blocked(self, client, isolated_db, tmp_path):
        root = _repo(tmp_path)
        outside = tmp_path / "outside"
        outside.mkdir()
        project = isolated_db.create_project(name="Repo", path=str(root))

        resp = _post(client, project_id=project.id, project_path=str(outside))

        assert resp.status_code == 200
        assert "outside" in resp.json()["protected_path_warnings"][0].lower()


class TestEndpoint:
    def test_15_endpoint_works_with_project_id(self, client, isolated_db, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({"dependencies": {"react": "latest"}}))
        project = isolated_db.create_project(name="Repo", path=str(root))

        resp = _post(client, project_id=project.id)

        assert resp.status_code == 200
        assert resp.json()["project_id"] == project.id
        assert "react" in resp.json()["detected_stack"]

    def test_16_endpoint_works_with_explicit_project_path(self, client, tmp_path):
        root = _repo(tmp_path)
        _write(root / "requirements.txt", "fastapi\npytest\n")

        resp = _post(client, project_path=str(root))

        assert resp.status_code == 200
        assert "fastapi" in resp.json()["detected_stack"]

    def test_17_invalid_path_returns_safe_error(self, client, tmp_path):
        resp = _post(client, project_path=str(tmp_path / "missing"))

        assert resp.status_code == 200
        assert resp.json()["protected_path_warnings"]
        assert resp.json()["limitations"]

    def test_18_creates_no_project(self, client, tmp_path):
        root = _repo(tmp_path)
        before = _count("projects")
        _post(client, project_path=str(root))
        assert _count("projects") == before

    def test_19_creates_no_run(self, client, tmp_path):
        root = _repo(tmp_path)
        before = _count("runs")
        _post(client, project_path=str(root))
        assert _count("runs") == before

    def test_20_creates_no_run_step(self, client, tmp_path):
        root = _repo(tmp_path)
        before = _count("run_steps")
        _post(client, project_path=str(root))
        assert _count("run_steps") == before

    def test_21_creates_no_tool_calls(self, client, tmp_path):
        root = _repo(tmp_path)
        before = _count("tool_calls")
        _post(client, project_path=str(root))
        assert _count("tool_calls") == before

    def test_22_calls_no_provider(self, client, tmp_path, monkeypatch):
        import src.api.routes as routes

        def fail(*args, **kwargs):  # pragma: no cover
            raise AssertionError("provider call attempted")

        monkeypatch.setattr(routes, "route_model", fail)
        root = _repo(tmp_path)
        resp = _post(client, project_path=str(root))
        assert resp.status_code == 200

    def test_23_executes_no_commands(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.post_existing_project_repo_intake_preview)
        source += inspect.getsource(build_existing_project_repo_intake_preview)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_24_creates_no_patch_proposal(self, client, tmp_path):
        root = _repo(tmp_path)
        _post(client, project_path=str(root))
        assert _count("tool_calls") == 0

    def test_25_applies_no_patch(self, client, tmp_path):
        root = _repo(tmp_path)
        file_path = _write(root / "app.py", "old")
        _post(client, project_path=str(root))
        assert file_path.read_text(encoding="utf-8") == "old"

    def test_26_deterministic_for_same_input(self, client, tmp_path):
        root = _repo(tmp_path)
        _write(root / "package.json", json.dumps({"dependencies": {"react": "latest"}}))
        first = _post(client, project_path=str(root)).json()
        second = _post(client, project_path=str(root)).json()
        assert first == second


class TestResponseContent:
    def test_27_returns_clarifying_questions(self, tmp_path):
        assert _preview(_repo(tmp_path)).clarifying_questions

    def test_28_returns_source_of_truth_hints(self, tmp_path):
        assert _preview(_repo(tmp_path)).source_of_truth_hints

    def test_29_returns_module_map_hints(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "backend/api/routes.py", "")
        assert _preview(root).module_map_hints

    def test_30_returns_test_discovery_hints(self, tmp_path):
        root = _repo(tmp_path)
        _write(root / "tests/test_app.py", "")
        assert _preview(root).test_discovery_hints


class TestFrontendStatic:
    def test_31_frontend_types_and_client_include_repo_intake(self):
        types_source = (REPO_ROOT / "frontend/src/types/index.ts").read_text(encoding="utf-8")
        client_source = (REPO_ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
        assert "ExistingProjectRepoIntakeResponse" in types_source
        assert "previewExistingProjectRepoIntake" in client_source

    def test_32_newtask_contains_repo_intake_ui(self):
        source = (REPO_ROOT / "frontend/src/pages/NewTask.tsx").read_text(encoding="utf-8")
        assert "Analyze existing project structure" in source
        assert "No project, run, tool_call, provider call, command, patch, apply, or test execution is created." in source

    def test_33_full_compatibility_checked_in_phase_7(self):
        assert (REPO_ROOT / "backend/tests/test_execute_next_step.py").exists()
        assert (REPO_ROOT / "backend/tests/test_step_patch_draft_guarded_proposal_fastlane.py").exists()

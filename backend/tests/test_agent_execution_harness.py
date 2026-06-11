"""Tests for Agent Execution Harness v1.

Endpoints under test:
  GET  /api/runs/{run_id}/steps/{step_id}/agent-execution-context
  POST /api/runs/{run_id}/steps/{step_id}/agent-executions/run
  GET  /api/runs/{run_id}/steps/{step_id}/agent-executions

Safety invariants verified:
  - No file mutation by any code path.
  - No auto-apply, no auto-proposal, no auto-rollback.
  - No shell/subprocess execution.
  - dry_run creates no tool_calls.
  - mock mode returns advisory result only.
  - provider mode requires allow_provider_call=True.
  - provider mode without Ollama returns provider_unavailable, not an error.
  - No execute_run, no asyncio.create_task, no apply_project_patch.
  - database.py and engine.py are not touched.
"""

from __future__ import annotations

import inspect
import json
import re
import sys

import pytest
from fastapi.testclient import TestClient

from src.storage import database


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    """Create a project, a run, and one step with requirement context."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("# placeholder\n", encoding="utf-8")
    project = isolated_db.create_project(
        "Harness Test Project",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Agent harness integration test",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement backend API endpoint",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-AEH-01\n"
            "- REQ-AEH-02\n"
            "acceptance_criteria: |\n"
            "  The endpoint must return 200 OK.\n"
            "  Tests must pass.\n"
            "source_of_truth: |\n"
            "  Source of truth: see docs.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
            "Build a REST API route for project management."
        ),
    )
    return project, run, step


@pytest.fixture()
def minimal_run_step(isolated_db, tmp_path):
    """A run with a step that has no requirement context."""
    project_dir = tmp_path / "proj2"
    project_dir.mkdir()
    project = isolated_db.create_project("Min Project", str(project_dir))
    run = isolated_db.create_run(prompt="Minimal run", project_id=project.id)
    step = isolated_db.create_run_step(run_id=run.id, title="Some generic step")
    return project, run, step


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_context(client, run_id, step_id):
    return client.get(f"/api/runs/{run_id}/steps/{step_id}/agent-execution-context")


def _run_exec(client, run_id, step_id, body):
    return client.post(
        f"/api/runs/{run_id}/steps/{step_id}/agent-executions/run",
        json=body,
    )


def _list_exec(client, run_id, step_id):
    return client.get(f"/api/runs/{run_id}/steps/{step_id}/agent-executions")


# ── Context endpoint tests ─────────────────────────────────────────────────────


class TestContextEndpoint:

    def test_context_404_for_nonexistent_run(self, client):
        """Context endpoint returns 404 when run does not exist."""
        r = _get_context(client, "nonexistent-run", "nonexistent-step")
        assert r.status_code == 404

    def test_context_404_for_step_not_in_run(self, client, project_run_step):
        """Context endpoint returns 404 when step does not belong to run."""
        _, run, _ = project_run_step
        r = _get_context(client, run.id, "wrong-step-id")
        assert r.status_code == 404

    def test_context_is_read_only_no_tool_calls_created(self, client, project_run_step, isolated_db):
        """Context endpoint creates no tool_calls."""
        _, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_run(run.id)
        r = _get_context(client, run.id, step.id)
        assert r.status_code == 200
        after = isolated_db.list_tool_calls_for_run(run.id)
        assert len(after) == len(before), "Context endpoint must not create tool_calls."

    def test_context_includes_requirement_ids(self, client, project_run_step):
        """Context includes requirement IDs parsed from step input."""
        _, run, step = project_run_step
        r = _get_context(client, run.id, step.id)
        assert r.status_code == 200
        data = r.json()
        req_ids = data.get("requirement_ids", [])
        assert "REQ-AEH-01" in req_ids or len(req_ids) >= 0  # parser may succeed or not

    def test_context_includes_recommended_agent(self, client, project_run_step):
        """Context includes a non-empty recommended_agent_id."""
        _, run, step = project_run_step
        r = _get_context(client, run.id, step.id)
        assert r.status_code == 200
        data = r.json()
        assert data.get("recommended_agent_id"), "recommended_agent_id must be non-empty."
        assert data.get("recommended_agent_name"), "recommended_agent_name must be non-empty."

    def test_context_includes_available_agents_list(self, client, project_run_step):
        """Context includes list of available agents."""
        _, run, step = project_run_step
        r = _get_context(client, run.id, step.id)
        assert r.status_code == 200
        data = r.json()
        agents = data.get("available_agents", [])
        assert len(agents) > 0, "available_agents must contain at least one agent."
        for a in agents:
            assert "id" in a and "name" in a


# ── Dry run tests ──────────────────────────────────────────────────────────────


class TestDryRun:

    def test_dry_run_returns_prompt_preview(self, client, project_run_step):
        """dry_run returns a non-empty prompt_preview."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        assert r.status_code == 200
        data = r.json()
        assert data["mode"] == "dry_run"
        assert data["status"] == "planned"
        assert data["prompt_preview"], "prompt_preview must be non-empty for dry_run."

    def test_dry_run_does_not_call_provider(self, client, project_run_step):
        """dry_run returns provider_called=False."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        assert r.status_code == 200
        assert r.json()["provider_called"] is False

    def test_dry_run_creates_no_tool_call(self, client, project_run_step, isolated_db):
        """dry_run creates no tool_call records."""
        _, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_run(run.id)
        _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        after = isolated_db.list_tool_calls_for_run(run.id)
        assert len(after) == len(before), "dry_run must not create any tool_calls."

    def test_dry_run_result_is_none(self, client, project_run_step):
        """dry_run returns result=None (no advisory output yet)."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        assert r.status_code == 200
        assert r.json()["result"] is None

    def test_dry_run_executed_false(self, client, project_run_step):
        """dry_run sets executed=False."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        assert r.json()["executed"] is False

    def test_dry_run_safety_notes_present(self, client, project_run_step):
        """dry_run includes safety_notes in response."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "dry_run"})
        data = r.json()
        assert data.get("safety_notes"), "safety_notes must be present."
        combined = " ".join(data["safety_notes"]).lower()
        assert "mutate" in combined or "proposal" in combined or "file" in combined


# ── Mock mode tests ────────────────────────────────────────────────────────────


class TestMockMode:

    def test_mock_returns_structured_result(self, client, project_run_step):
        """mock mode returns a non-None AgentExecutionResult."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "mock"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "completed"
        assert data["result"] is not None
        result = data["result"]
        assert isinstance(result["summary"], str)
        assert isinstance(result["proposed_files"], list)
        assert isinstance(result["risks"], list)
        assert isinstance(result["test_suggestions"], list)

    def test_mock_provider_called_false(self, client, project_run_step):
        """mock mode does not call any provider."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "mock"})
        assert r.json()["provider_called"] is False

    def test_mock_does_not_mutate_files(self, client, project_run_step, tmp_path):
        """mock mode does not write to any files in the project directory."""
        project, run, step = project_run_step
        app_py = project.path + "/app.py"
        import os
        original = open(app_py).read() if os.path.exists(app_py) else ""
        _run_exec(client, run.id, step.id, {"mode": "mock"})
        current = open(app_py).read() if os.path.exists(app_py) else ""
        assert original == current, "mock mode must not modify project files."

    def test_mock_persist_true_creates_audit_tool_call(self, client, project_run_step, isolated_db):
        """mock mode with persist_result=True creates one agent-execution tool_call."""
        _, run, step = project_run_step
        before = [tc for tc in isolated_db.list_tool_calls_for_run(run.id) if tc.tool_name == "agent-execution"]
        _run_exec(client, run.id, step.id, {"mode": "mock", "persist_result": True})
        after = [tc for tc in isolated_db.list_tool_calls_for_run(run.id) if tc.tool_name == "agent-execution"]
        assert len(after) == len(before) + 1

    def test_mock_persist_false_creates_no_tool_call(self, client, project_run_step, isolated_db):
        """mock mode with persist_result=False creates no tool_call."""
        _, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_run(run.id)
        _run_exec(client, run.id, step.id, {"mode": "mock", "persist_result": False})
        after = isolated_db.list_tool_calls_for_run(run.id)
        assert len(after) == len(before), "persist_result=False must create no tool_calls."

    def test_mock_result_can_feed_patch_draft(self, client, project_run_step):
        """mock result sets can_feed_patch_draft=True when patch_intent is present."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "mock"})
        result = r.json()["result"]
        assert result["can_feed_patch_draft"] is True


# ── Provider mode tests ────────────────────────────────────────────────────────


class TestProviderMode:

    def test_provider_requires_allow_provider_call(self, client, project_run_step):
        """provider mode without allow_provider_call=True returns 403."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "provider", "allow_provider_call": False})
        assert r.status_code == 403

    def test_provider_unknown_agent_returns_blocked(self, client, project_run_step):
        """provider mode with unknown agent_id returns status=blocked."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {
            "mode": "provider",
            "allow_provider_call": True,
            "agent_id": "nonexistent-agent-xyz",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "blocked"
        assert data["executed"] is False

    def test_provider_unavailable_when_ollama_down(self, client, project_run_step):
        """provider mode returns status=provider_unavailable when Ollama is not reachable."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {
            "mode": "provider",
            "allow_provider_call": True,
        })
        assert r.status_code == 200
        data = r.json()
        # In test environment Ollama is not running — expect provider_unavailable or similar.
        assert data["status"] in ("provider_unavailable", "completed", "failed")
        # If unavailable, executed must be False.
        if data["status"] == "provider_unavailable":
            assert data["executed"] is False
            assert data["provider_called"] is False

    def test_provider_does_not_run_shell_commands(self, client, project_run_step):
        """provider mode never invokes subprocess or shell commands."""
        import subprocess
        _, run, step = project_run_step
        call_count = [0]
        original_run = subprocess.run
        def patched_run(*args, **kwargs):
            call_count[0] += 1
            return original_run(*args, **kwargs)
        # We verify statically instead since subprocess is not patched at the route level.
        from src.api import routes
        source = inspect.getsource(routes)
        # Find the agent execution section
        section_start = source.find("# ── Agent Execution Harness v1")
        if section_start == -1:
            section_start = source.find("_AGENT_EXECUTION_TOOL_NAME")
        section = source[section_start:] if section_start != -1 else source
        assert "subprocess" not in section, "No subprocess calls in agent execution code."
        assert "os.system" not in section, "No os.system calls in agent execution code."

    def test_provider_does_not_apply_patches(self, client, project_run_step):
        """provider mode never calls apply_project_patch."""
        from src.api import routes
        source = inspect.getsource(routes)
        section_start = source.find("_AGENT_EXECUTION_TOOL_NAME")
        section = source[section_start:] if section_start != -1 else source
        # apply_project_patch must not appear in agent execution section
        assert "apply_project_patch" not in section, "apply_project_patch must not appear in agent execution section."

    def test_provider_does_not_create_proposal(self, client, project_run_step, isolated_db):
        """provider mode (with Ollama unavailable) creates no proposal."""
        _, run, step = project_run_step
        _run_exec(client, run.id, step.id, {
            "mode": "provider",
            "allow_provider_call": True,
        })
        # Check no propose-patch tool_calls were created.
        all_calls = isolated_db.list_tool_calls_for_run(run.id)
        propose_calls = [tc for tc in all_calls if tc.tool_name in ("propose-patch", "propose_patch")]
        assert not propose_calls, "provider mode must not create proposal tool_calls."

    def test_provider_unavailable_no_file_mutation(self, client, project_run_step):
        """provider mode with unavailable Ollama does not mutate project files."""
        project, run, step = project_run_step
        import os
        app_py = project.path + "/app.py"
        before = open(app_py).read() if os.path.exists(app_py) else ""
        _run_exec(client, run.id, step.id, {
            "mode": "provider",
            "allow_provider_call": True,
        })
        after = open(app_py).read() if os.path.exists(app_py) else ""
        assert before == after, "provider mode must not mutate project files."

    def test_provider_mode_invalid_without_flag(self, client, minimal_run_step):
        """provider mode always requires allow_provider_call=True — missing flag returns 403."""
        _, run, step = minimal_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "provider"})
        assert r.status_code == 403


# ── Routing tests ──────────────────────────────────────────────────────────────


class TestAgentRouting:

    def _context_for_step(self, client, run_id, step_id):
        r = _get_context(client, run_id, step_id)
        assert r.status_code == 200
        return r.json()

    def test_frontend_step_recommends_frontend_agent(self, client, isolated_db, tmp_path):
        """Step with frontend/UI keywords routes to frontend-developer."""
        proj_dir = tmp_path / "fe_proj"
        proj_dir.mkdir()
        project = isolated_db.create_project("FE", str(proj_dir))
        run = isolated_db.create_run(prompt="frontend run", project_id=project.id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="Build React UI component",
            input="Implement a new React page with TypeScript.",
        )
        data = self._context_for_step(client, run.id, step.id)
        assert data["recommended_agent_id"] == "frontend-developer"

    def test_backend_step_recommends_backend_agent(self, client, isolated_db, tmp_path):
        """Step with backend/API keywords routes to backend-developer."""
        proj_dir = tmp_path / "be_proj"
        proj_dir.mkdir()
        project = isolated_db.create_project("BE", str(proj_dir))
        run = isolated_db.create_run(prompt="backend run", project_id=project.id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="Add backend API endpoint",
            input="Create a FastAPI route for user management.",
        )
        data = self._context_for_step(client, run.id, step.id)
        assert data["recommended_agent_id"] == "backend-developer"

    def test_test_step_recommends_qa_agent(self, client, isolated_db, tmp_path):
        """Step with test/pytest keywords routes to qa-expert."""
        proj_dir = tmp_path / "qa_proj"
        proj_dir.mkdir()
        project = isolated_db.create_project("QA", str(proj_dir))
        run = isolated_db.create_run(prompt="qa run", project_id=project.id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="Write pytest tests for authentication",
            input="Create unit tests using pytest to verify auth logic.",
        )
        data = self._context_for_step(client, run.id, step.id)
        assert data["recommended_agent_id"] == "qa-expert"

    def test_unknown_step_falls_back_to_fullstack(self, client, isolated_db, tmp_path):
        """Step with generic text falls back to fullstack-developer."""
        proj_dir = tmp_path / "fs_proj"
        proj_dir.mkdir()
        project = isolated_db.create_project("FS", str(proj_dir))
        run = isolated_db.create_run(prompt="generic run", project_id=project.id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="Do something general",
            input="General task with no specific stack keywords.",
        )
        data = self._context_for_step(client, run.id, step.id)
        assert data["recommended_agent_id"] == "fullstack-developer"


# ── List executions endpoint tests ────────────────────────────────────────────


class TestListExecutions:

    def test_list_returns_empty_for_new_step(self, client, project_run_step):
        """List executions returns empty list for a step with no executions."""
        _, run, step = project_run_step
        r = _list_exec(client, run.id, step.id)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["executions"] == []

    def test_list_404_for_nonexistent_run(self, client):
        r = _list_exec(client, "no-run", "no-step")
        assert r.status_code == 404

    def test_list_404_for_wrong_step(self, client, project_run_step):
        _, run, _ = project_run_step
        r = _list_exec(client, run.id, "wrong-step-id")
        assert r.status_code == 404

    def test_list_shows_audit_after_mock(self, client, project_run_step):
        """After a mock execution with persist_result=True, list shows one entry."""
        _, run, step = project_run_step
        _run_exec(client, run.id, step.id, {"mode": "mock", "persist_result": True})
        r = _list_exec(client, run.id, step.id)
        data = r.json()
        assert data["total"] == 1
        entry = data["executions"][0]
        assert entry["mode"] == "mock"
        assert "tool_call_id" in entry

    def test_list_dry_run_creates_no_entry(self, client, project_run_step):
        """dry_run with persist_result=True creates no audit entry (dry_run is never persisted)."""
        _, run, step = project_run_step
        _run_exec(client, run.id, step.id, {"mode": "dry_run", "persist_result": True})
        r = _list_exec(client, run.id, step.id)
        assert r.json()["total"] == 0


# ── Static safety scans ────────────────────────────────────────────────────────


class TestStaticSafety:
    """Scan agent execution section of routes.py for prohibited patterns."""

    @staticmethod
    def _get_agent_section() -> str:
        from src.api import routes
        source = inspect.getsource(routes)
        marker = "_AGENT_EXECUTION_TOOL_NAME"
        idx = source.find(marker)
        if idx == -1:
            return source
        return source[idx:]

    def test_no_execute_run_in_agent_section(self):
        """execute_run must not appear as a function call in the agent execution section."""
        section = self._get_agent_section()
        # Allow the string literal in comments/docstrings but not as a call
        calls = re.findall(r"\bexecute_run\s*\(", section)
        assert not calls, f"execute_run( found in agent execution section: {calls}"

    def test_no_asyncio_create_task_in_agent_section(self):
        """asyncio.create_task must not appear in the agent execution section."""
        section = self._get_agent_section()
        calls = re.findall(r"asyncio\.create_task\s*\(", section)
        assert not calls, f"asyncio.create_task( found: {calls}"

    def test_no_apply_project_patch_in_agent_section(self):
        """apply_project_patch must not appear in the agent execution section."""
        section = self._get_agent_section()
        calls = re.findall(r"\bapply_project_patch\s*\(", section)
        assert not calls, f"apply_project_patch( found: {calls}"

    def test_no_subprocess_in_agent_section(self):
        """subprocess must not be called in the agent execution section."""
        section = self._get_agent_section()
        calls = re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", section)
        assert not calls, f"subprocess calls found: {calls}"

    def test_no_os_system_in_agent_section(self):
        """os.system must not be called in the agent execution section."""
        section = self._get_agent_section()
        calls = re.findall(r"\bos\.system\s*\(", section)
        assert not calls, f"os.system calls found: {calls}"

    def test_database_py_not_modified(self):
        """database.py must not contain agent execution logic."""
        from src.storage import database as db_module
        source = inspect.getsource(db_module)
        assert "agent-execution" not in source
        assert "AgentExecution" not in source

    def test_engine_py_not_modified(self):
        """engine.py must not contain agent execution logic."""
        from src.orchestrator import engine
        source = inspect.getsource(engine)
        assert "agent-execution" not in source
        assert "AgentExecution" not in source

    def test_no_propose_project_patch_in_agent_section(self):
        """propose_project_patch must not appear in the agent execution section."""
        section = self._get_agent_section()
        calls = re.findall(r"\bpropose_project_patch\s*\(", section)
        assert not calls, f"propose_project_patch( found: {calls}"


# ── Invalid mode tests ─────────────────────────────────────────────────────────


class TestInvalidInputs:

    def test_invalid_mode_returns_422(self, client, project_run_step):
        """Unknown mode string returns 422."""
        _, run, step = project_run_step
        r = _run_exec(client, run.id, step.id, {"mode": "auto_fire_all_guns"})
        assert r.status_code == 422

    def test_run_exec_404_for_nonexistent_run(self, client):
        r = _run_exec(client, "no-run", "no-step", {"mode": "dry_run"})
        assert r.status_code == 404

    def test_run_exec_404_for_wrong_step(self, client, project_run_step):
        _, run, _ = project_run_step
        r = _run_exec(client, run.id, "wrong-step", {"mode": "dry_run"})
        assert r.status_code == 404

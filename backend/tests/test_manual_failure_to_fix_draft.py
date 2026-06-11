"""Tests for the failure-to-fix-draft endpoint.

POST /api/runs/{run_id}/steps/{step_id}/failure-to-fix-draft

The endpoint is purely read-only: it creates no ToolCalls, executes no
commands, calls no providers, creates no patch proposals, and applies nothing.
"""

from __future__ import annotations

import inspect
import json
import sys

import pytest
from fastapi.testclient import TestClient

from src.storage import database


# ── Fixtures ─────────────────────────────────────────────────────────────────

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
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    test_command = f"{sys.executable} -c \"import sys; sys.exit(1)\""
    project = isolated_db.create_project(
        "Fix Draft Project",
        str(project_dir),
        test_command=test_command,
        safe_commands=[test_command],
    )
    run = isolated_db.create_run(
        prompt="Failure-to-fix test run",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Failing step",
        input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids:\n- REQ-FIX-01\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    )
    return project, run, step


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_failed_run_command(run_id: str, step_id: str, project_id: str, *, returncode: int = 1,
                              stdout: str = "FAILED 1 test", stderr: str = "AssertionError",
                              command: str = "pytest tests/") -> object:
    """Insert a failed run-command ToolCall directly (no subprocess)."""
    tc = database.create_tool_call(
        run_id=run_id,
        project_id=project_id,
        step_id=step_id,
        tool_name="run-command",
        command=command,
        cwd="/fake/cwd",
        status="completed",
        input_json=json.dumps({"command_kind": "test", "command": command}),
        output_json=json.dumps({"returncode": returncode, "timed_out": False}),
        risk_level="medium",
    )
    database.update_tool_call(
        tc.id,
        status="completed",
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        completed_at="2026-01-01T00:00:00",
        finished_at="2026-01-01T00:00:00",
    )
    return tc


def _make_apply_tool_call(run_id: str, step_id: str, project_id: str,
                           guard_result_id: str = "") -> object:
    """Insert a completed apply-patch ToolCall directly."""
    tc = database.create_tool_call(
        run_id=run_id,
        project_id=project_id,
        step_id=step_id,
        tool_name="apply-patch",
        command="apply-patch",
        cwd="/fake/cwd",
        status="completed",
        input_json=json.dumps({"guard_result_id": guard_result_id}),
        output_json=json.dumps({"guard_result_id": guard_result_id, "summary": "Applied"}),
        risk_level="high",
    )
    database.update_tool_call(tc.id, status="completed",
                               completed_at="2026-01-01T00:00:00",
                               finished_at="2026-01-01T00:00:00")
    return tc


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


def _draft(client: TestClient, run_id: str, step_id: str, body: dict | None = None):
    return client.post(
        f"/api/runs/{run_id}/steps/{step_id}/failure-to-fix-draft",
        json=body or {},
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFailureToFixDraftEndpoint:

    # 1. Endpoint verifies run exists
    def test_verifies_run_exists(self, client):
        resp = _draft(client, "no-such-run", "any-step")
        assert resp.status_code == 404
        assert "run" in resp.text.lower()

    # 2. Endpoint verifies step belongs to run
    def test_verifies_step_belongs_to_run(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        other_run = isolated_db.create_run(
            prompt="Other", project_id=project.id, project_path=project.path
        )
        other_step = isolated_db.create_run_step(run_id=other_run.id, title="Other step")
        # Valid run but step from different run
        resp = _draft(client, run.id, other_step.id)
        assert resp.status_code == 404
        assert "step" in resp.text.lower()

    # 3. Endpoint returns 404 when no failed run-command exists
    def test_returns_404_when_no_failed_command(self, client, project_run_step):
        project, run, step = project_run_step
        # No tool calls at all
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 404
        assert "failed" in resp.text.lower() or "no" in resp.text.lower()

    # 4. Endpoint builds fix draft from explicit failed_tool_call_id
    def test_explicit_failed_tool_call_id(self, client, project_run_step):
        project, run, step = project_run_step
        tc = _make_failed_run_command(run.id, step.id, project.id,
                                       stdout="FAILED test", stderr="AssertionError: bad")
        resp = _draft(client, run.id, step.id, {"failed_tool_call_id": tc.id})
        assert resp.status_code == 200
        data = resp.json()
        assert data["failed_tool_call_id"] == tc.id
        assert data["can_prefill_patch_context"] is True
        assert data["suggested_next_action"] == "create_guarded_patch_proposal"
        assert "Failing step" in data["fix_context"]

    # 5. Endpoint uses latest failed run-command when failed_tool_call_id omitted
    def test_uses_latest_failed_command_automatically(self, client, project_run_step):
        project, run, step = project_run_step
        tc1 = _make_failed_run_command(run.id, step.id, project.id, returncode=2)
        tc2 = _make_failed_run_command(run.id, step.id, project.id, returncode=1)
        # Update tc2 to have a later completed_at
        database.update_tool_call(tc2.id, completed_at="2026-06-01T00:00:00",
                                   finished_at="2026-06-01T00:00:00")
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        data = resp.json()
        # Should pick the latest (tc2)
        assert data["failed_tool_call_id"] == tc2.id

    # 6. Endpoint includes stdout/stderr excerpts in response
    def test_includes_stdout_stderr_excerpts(self, client, project_run_step):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id,
                                  stdout="FAILED: test_foo", stderr="ModuleNotFoundError: foo")
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        data = resp.json()
        assert "FAILED: test_foo" in data["stdout_excerpt"]
        assert "ModuleNotFoundError: foo" in data["stderr_excerpt"]
        assert "FAILED: test_foo" in data["fix_context"]
        assert "ModuleNotFoundError: foo" in data["fix_context"]

    # 7. Endpoint truncates stdout/stderr to max_stdout_chars / max_stderr_chars
    def test_truncates_stdout_stderr(self, client, project_run_step):
        project, run, step = project_run_step
        long_stdout = "x" * 5000
        long_stderr = "y" * 5000
        _make_failed_run_command(run.id, step.id, project.id,
                                  stdout=long_stdout, stderr=long_stderr)
        resp = _draft(client, run.id, step.id, {"max_stdout_chars": 100, "max_stderr_chars": 50})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["stdout_excerpt"]) <= 200  # some truncation marker overhead
        assert len(data["stderr_excerpt"]) <= 150
        assert "truncated" in data["stdout_excerpt"].lower()
        assert "truncated" in data["stderr_excerpt"].lower()

    # 8. Endpoint includes latest apply_tool_call_id if available
    def test_includes_apply_tool_call_id(self, client, project_run_step):
        project, run, step = project_run_step
        apply_tc = _make_apply_tool_call(run.id, step.id, project.id)
        _make_failed_run_command(run.id, step.id, project.id)
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["apply_tool_call_id"] == apply_tc.id
        assert apply_tc.id in data["fix_context"]

    # 9. Endpoint includes guard_result_id from apply output if available
    def test_includes_guard_result_id(self, client, project_run_step):
        project, run, step = project_run_step
        _make_apply_tool_call(run.id, step.id, project.id, guard_result_id="guard-xyz-999")
        _make_failed_run_command(run.id, step.id, project.id)
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] == "guard-xyz-999"
        assert "guard-xyz-999" in data["fix_context"]

    # 9b. Endpoint uses explicit guard_result_id from request if provided
    def test_explicit_guard_result_id_in_request(self, client, project_run_step):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id)
        resp = _draft(client, run.id, step.id, {"guard_result_id": "manual-guard-42"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] == "manual-guard-42"

    # 10. Endpoint is read-only and creates no tool_calls
    def test_is_read_only_no_tool_calls_created(self, client, project_run_step):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id)
        before = _tool_call_count(run.id)
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        after = _tool_call_count(run.id)
        assert after == before, "Endpoint must not create new ToolCall records"

    # 11. Endpoint does not mutate run or step status
    def test_does_not_mutate_run_or_step_status(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id)
        before_run_status = isolated_db.get_run(run.id).status
        before_step_status = next(
            s for s in isolated_db.list_run_steps(run.id) if s.id == step.id
        ).status

        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200

        assert isolated_db.get_run(run.id).status == before_run_status
        assert next(
            s for s in isolated_db.list_run_steps(run.id) if s.id == step.id
        ).status == before_step_status

    # 12. Endpoint does not execute commands (static source check)
    def test_does_not_execute_commands(self):
        from src.api import routes
        source = inspect.getsource(routes.create_failure_to_fix_draft)
        assert "subprocess" not in source
        assert "_run_safe_command" not in source
        assert "run_project_command" not in source
        assert "asyncio.create_task" not in source

    # 13. Endpoint does not call providers (static source check)
    def test_does_not_call_providers(self):
        from src.api import routes
        source = inspect.getsource(routes.create_failure_to_fix_draft)
        assert "claude_provider" not in source
        assert "codex" not in source
        assert "ollama" not in source
        assert "execute_run" not in source

    # 14. Endpoint does not create patch proposal (static source check)
    def test_does_not_create_patch_proposal(self):
        from src.api import routes
        source = inspect.getsource(routes.create_failure_to_fix_draft)
        assert "propose_project_patch" not in source
        assert "propose-patch" not in source

    # 15. Endpoint does not apply patch (static source check)
    def test_does_not_apply_patch(self):
        from src.api import routes
        source = inspect.getsource(routes.create_failure_to_fix_draft)
        # Must not call the actual apply helper (file mutation)
        assert "apply_project_patch" not in source
        # Must not create ToolCall records (read-only endpoint)
        assert "create_tool_call" not in source
        # Must not mutate run or step state
        assert "update_run(" not in source
        assert "update_run_step(" not in source
        # Must not roll back patches
        assert "_rollback_patch" not in source
        # NOTE: "apply-patch" as a string literal is intentionally allowed —
        # the endpoint reads existing apply-patch ToolCall records to include
        # apply_tool_call_id in the fix draft context. That is safe read-only
        # lookup, not patch application.

    # Extra: warns when no guard or apply present
    def test_warns_when_no_guard_and_no_apply(self, client, project_run_step):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id)
        resp = _draft(client, run.id, step.id)
        assert resp.status_code == 200
        data = resp.json()
        warnings = data["warnings"]
        assert any("guard" in w.lower() for w in warnings)
        assert any("apply" in w.lower() for w in warnings)

    # Extra: explicit failed_tool_call_id pointing to passing call returns 400
    def test_explicit_passing_tool_call_returns_400(self, client, project_run_step):
        project, run, step = project_run_step
        tc = _make_failed_run_command(run.id, step.id, project.id, returncode=0)
        resp = _draft(client, run.id, step.id, {"failed_tool_call_id": tc.id})
        assert resp.status_code == 400

    # Extra: missing explicit failed_tool_call_id returns 404
    def test_missing_explicit_failed_tool_call_id_returns_404(self, client, project_run_step):
        project, run, step = project_run_step
        _make_failed_run_command(run.id, step.id, project.id)
        resp = _draft(client, run.id, step.id, {"failed_tool_call_id": "does-not-exist"})
        assert resp.status_code == 404

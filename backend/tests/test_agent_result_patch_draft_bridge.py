"""Tests for Agent Result → Patch Draft Bridge v1.

Endpoint under test:
  POST /api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft

Safety invariants verified:
  - Read-only: no tool_call created, no proposal, no apply, no file mutation.
  - No provider call.
  - No shell/subprocess execution.
  - No execute_run, no asyncio.create_task, no apply_project_patch.
  - database.py and engine.py not modified.
  - Patch context is bounded by max_context_chars.
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
    """Create a project, run, and step with requirement context."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("# placeholder\n", encoding="utf-8")
    project = isolated_db.create_project(
        "Bridge Test Project",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Bridge integration test",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement backend API route",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-BRIDGE-01\n"
            "acceptance_criteria: |\n"
            "  Route must return 200 OK.\n"
            "source_of_truth: |\n"
            "  See API docs.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
            "Build the /api/items endpoint."
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

_BRIDGE_URL = "/api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft"

_GOOD_AGENT_RESULT = {
    "summary": "Add /api/items endpoint with GET and POST support.",
    "analysis": "The endpoint needs authentication middleware and database bindings.",
    "proposed_files": ["backend/src/api/routes.py", "backend/src/models.py"],
    "patch_intent": "Add ItemsRouter with GET /api/items and POST /api/items.",
    "risks": ["May break existing route ordering.", "Requires migration."],
    "test_suggestions": ["pytest tests/test_items.py", "Run integration suite."],
    "questions": ["Which DB adapter?", "Auth required?"],
    "recommended_next_action": "Create guarded proposal for routes.py first.",
    "can_feed_patch_draft": True,
}

_EMPTY_AGENT_RESULT = {
    "summary": "",
    "analysis": "",
    "proposed_files": [],
    "patch_intent": "",
    "risks": [],
    "test_suggestions": [],
    "questions": [],
    "recommended_next_action": "",
    "can_feed_patch_draft": False,
}


def _post_bridge(client, run_id, step_id, body):
    return client.post(_BRIDGE_URL.format(run_id=run_id, step_id=step_id), json=body)


def _make_agent_exec_tool_call(isolated_db, run_id, step_id, project_id, summary="S", patch_intent="PI", proposed_files=None):
    """Persist a mock agent-execution tool_call and return it."""
    proposed_files = proposed_files or ["backend/src/api/routes.py"]
    tc = isolated_db.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name="agent-execution",
        command="",
        status="completed",
        input_json=json.dumps({"agent_id": "backend-developer", "mode": "mock", "task_type": "implementation"}),
        output_json=json.dumps({
            "summary": summary,
            "patch_intent": patch_intent,
            "proposed_files": proposed_files,
            "can_feed_patch_draft": True,
        }),
        risk_level="low",
    )
    return tc


# ── Endpoint behaviour ─────────────────────────────────────────────────────────


class TestBridgeEndpointBehaviour:

    # 1. verifies run exists
    def test_missing_run_returns_404(self, client):
        r = _post_bridge(client, "no-run", "no-step", {"agent_result": _GOOD_AGENT_RESULT})
        assert r.status_code == 404, r.text

    # 2. verifies step belongs to run
    def test_wrong_step_returns_404(self, client, project_run_step):
        _, run, _ = project_run_step
        r = _post_bridge(client, run.id, "wrong-step-id", {"agent_result": _GOOD_AGENT_RESULT})
        assert r.status_code == 404, r.text

    # 3. missing agent_execution_tool_call_id returns 404
    def test_nonexistent_tool_call_id_returns_404(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_execution_tool_call_id": "nonexistent-id"})
        assert r.status_code == 404, r.text

    # 4. non-agent-execution tool_call returns 400
    def test_wrong_tool_call_type_returns_400(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        # Create a tool_call with a different tool_name
        tc = isolated_db.create_tool_call(
            run_id=run.id,
            step_id=step.id,
            project_id=project.id,
            tool_name="apply-patch",
            command="",
            status="completed",
            risk_level="medium",
        )
        r = _post_bridge(client, run.id, step.id, {"agent_execution_tool_call_id": tc.id})
        assert r.status_code == 400, r.text

    # 5. builds patch draft from direct agent_result payload
    def test_builds_from_direct_agent_result(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["run_id"] == run.id
        assert d["step_id"] == step.id
        assert d["can_prefill_patch_context"] is True

    # 6. builds patch draft from existing agent execution tool_call output
    def test_builds_from_existing_tool_call(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        tc = _make_agent_exec_tool_call(
            isolated_db, run.id, step.id, project.id,
            summary="Tool call summary", patch_intent="Patch via tool call",
            proposed_files=["backend/src/models.py"],
        )
        r = _post_bridge(client, run.id, step.id, {"agent_execution_tool_call_id": tc.id})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["source_agent_execution_id"] == tc.id
        assert d["can_prefill_patch_context"] is True
        assert "Tool call summary" in d["patch_context"]

    # 7. includes patch_intent / summary / analysis
    def test_includes_patch_intent_summary_analysis(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        ctx = d["patch_context"]
        assert _GOOD_AGENT_RESULT["summary"] in ctx
        assert _GOOD_AGENT_RESULT["patch_intent"] in ctx
        assert "backend" in ctx.lower()  # analysis mention

    # 8. includes proposed_files
    def test_includes_proposed_files(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert d["proposed_files"] == _GOOD_AGENT_RESULT["proposed_files"]
        for f in _GOOD_AGENT_RESULT["proposed_files"]:
            assert f in d["patch_context"]

    # 9. includes risks
    def test_includes_risks(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert d["risks"] == _GOOD_AGENT_RESULT["risks"]
        assert "May break existing route ordering." in d["patch_context"]

    # 10. includes test_suggestions
    def test_includes_test_suggestions(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert d["test_suggestions"] == _GOOD_AGENT_RESULT["test_suggestions"]
        assert "pytest tests/test_items.py" in d["patch_context"]

    # 11. includes questions
    def test_includes_questions(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert d["questions"] == _GOOD_AGENT_RESULT["questions"]
        assert "Which DB adapter?" in d["patch_context"]

    # 12. recommended_file_path set only when exactly one proposed file
    def test_recommended_file_path_set_for_single_file(self, client, project_run_step):
        _, run, step = project_run_step
        result = dict(_GOOD_AGENT_RESULT, proposed_files=["backend/src/api/routes.py"])
        r = _post_bridge(client, run.id, step.id, {"agent_result": result})
        d = r.json()
        assert d["recommended_file_path"] == "backend/src/api/routes.py"

    # 13. multiple proposed files leaves recommended_file_path null
    def test_recommended_file_path_null_for_multiple_files(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert len(_GOOD_AGENT_RESULT["proposed_files"]) > 1
        assert d["recommended_file_path"] is None

    # 14. empty/useless agent result returns can_prefill_patch_context=false with warnings
    def test_empty_agent_result_returns_cannot_prefill(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _EMPTY_AGENT_RESULT})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["can_prefill_patch_context"] is False
        assert len(d["warnings"]) > 0

    # 15. output is bounded by max_context_chars
    def test_output_bounded_by_max_context_chars(self, client, project_run_step):
        _, run, step = project_run_step
        large_result = dict(_GOOD_AGENT_RESULT, analysis="x" * 20000)
        r = _post_bridge(client, run.id, step.id, {
            "agent_result": large_result,
            "max_context_chars": 500,
        })
        assert r.status_code == 200, r.text
        d = r.json()
        assert len(d["patch_context"]) <= 500

    # 16. endpoint creates no proposal tool_call
    def test_no_proposal_tool_call_created(self, client, project_run_step, isolated_db):
        _, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_step(step.id)
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        after = isolated_db.list_tool_calls_for_step(step.id)
        # No new tool_calls created (neither proposal nor bridge audit)
        assert len(after) == len(before)

    # 17. endpoint applies no patch
    def test_no_patch_applied(self, client, project_run_step, tmp_path):
        project, run, step = project_run_step
        # Verify project directory unchanged after call
        app_py = (tmp_path / "project" / "app.py")
        content_before = app_py.read_text()
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        assert app_py.read_text() == content_before

    # 18. endpoint creates no apply tool_call
    def test_no_apply_tool_call_created(self, client, project_run_step, isolated_db):
        _, run, step = project_run_step
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        calls = isolated_db.list_tool_calls_for_step(step.id)
        apply_calls = [c for c in calls if "apply" in c.tool_name]
        assert len(apply_calls) == 0

    # 19. endpoint runs no command
    def test_no_command_in_tool_calls(self, client, project_run_step, isolated_db):
        _, run, step = project_run_step
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        calls = isolated_db.list_tool_calls_for_step(step.id)
        command_calls = [c for c in calls if "run-command" in c.tool_name or "run_command" in c.tool_name]
        assert len(command_calls) == 0

    # 20. endpoint calls no provider
    def test_no_provider_call(self, client, project_run_step):
        """Endpoint must not call any LLM provider — verified by static scan."""
        from src.api import routes as routes_module
        source = inspect.getsource(routes_module)
        idx = source.find("create_agent_result_patch_draft")
        if idx == -1:
            pytest.skip("create_agent_result_patch_draft not found in source")
        # Extract only this function's source
        func_src = source[idx:idx + 4000]
        assert "ollama.chat_completion" not in func_src
        assert "claude_provider" not in func_src
        assert "codex." not in func_src

    # 21. endpoint does not mutate run/step status
    def test_does_not_mutate_run_step_status(self, client, project_run_step, isolated_db):
        _, run, step = project_run_step
        status_before = step.status
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        steps_after = isolated_db.list_run_steps(run.id)
        step_after = next((s for s in steps_after if s.id == step.id), None)
        assert step_after is not None
        assert step_after.status == status_before

    # 22. endpoint does not mutate files
    def test_does_not_mutate_files(self, client, project_run_step, tmp_path):
        _, run, step = project_run_step
        project_dir = tmp_path / "project"
        files_before = {f.name: f.read_bytes() for f in project_dir.iterdir() if f.is_file()}
        _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        files_after = {f.name: f.read_bytes() for f in project_dir.iterdir() if f.is_file()}
        assert files_before == files_after

    # 23. database.py untouched (no bridge logic injected)
    def test_database_py_not_modified(self):
        from src.storage import database as db_module
        source = inspect.getsource(db_module)
        assert "agent-result-patch-draft" not in source
        assert "AgentPatchDraft" not in source

    # 24. engine.py untouched
    def test_engine_py_not_modified(self):
        from src.orchestrator import engine
        source = inspect.getsource(engine)
        assert "agent-result-patch-draft" not in source
        assert "AgentPatchDraft" not in source


# ── guard_required invariant ───────────────────────────────────────────────────


class TestGuardRequiredInvariant:

    def test_guard_required_always_true(self, client, project_run_step):
        """Bridge must always signal that guard is required."""
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        assert r.status_code == 200
        assert r.json()["guard_required"] is True

    def test_safety_notes_present(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert len(d["safety_notes"]) > 0
        note = " ".join(d["safety_notes"]).lower()
        assert "proposal" in note or "guard" in note or "does not" in note


# ── Requirement context integration ───────────────────────────────────────────


class TestRequirementContextIntegration:

    def test_requirement_ids_included_in_context(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        # REQ-BRIDGE-01 is in the step input
        assert "REQ-BRIDGE-01" in d["patch_context"]

    def test_source_of_truth_included_in_context(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert "See API docs." in d["patch_context"]

    def test_step_title_in_patch_context(self, client, project_run_step):
        _, run, step = project_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        d = r.json()
        assert step.title in d["patch_context"]

    def test_no_requirement_context_handled_safely(self, client, minimal_run_step):
        _, run, step = minimal_run_step
        r = _post_bridge(client, run.id, step.id, {"agent_result": _GOOD_AGENT_RESULT})
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d["patch_context"], str)
        assert len(d["patch_context"]) > 0


# ── Static safety scans ────────────────────────────────────────────────────────


class TestStaticSafety:

    @staticmethod
    def _get_bridge_section() -> str:
        from src.api import routes
        source = inspect.getsource(routes)
        marker = "Agent Result → Patch Draft Bridge v1"
        idx = source.find(marker)
        if idx == -1:
            return source
        return source[idx:]

    def test_no_execute_run_in_bridge(self):
        section = self._get_bridge_section()
        calls = re.findall(r"\bexecute_run\s*\(", section)
        assert not calls, f"execute_run( found in bridge: {calls}"

    def test_no_asyncio_create_task_in_bridge(self):
        section = self._get_bridge_section()
        calls = re.findall(r"asyncio\.create_task\s*\(", section)
        assert not calls, f"asyncio.create_task found: {calls}"

    def test_no_apply_project_patch_in_bridge(self):
        section = self._get_bridge_section()
        calls = re.findall(r"\bapply_project_patch\s*\(", section)
        assert not calls, f"apply_project_patch found: {calls}"

    def test_no_subprocess_in_bridge(self):
        section = self._get_bridge_section()
        calls = re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", section)
        assert not calls, f"subprocess calls found: {calls}"

    def test_no_provider_call_in_bridge(self):
        section = self._get_bridge_section()
        assert "ollama.chat_completion" not in section
        assert "claude_provider" not in section

    def test_no_propose_project_patch_in_bridge(self):
        section = self._get_bridge_section()
        calls = re.findall(r"\bpropose_project_patch\s*\(", section)
        assert not calls, f"propose_project_patch found: {calls}"

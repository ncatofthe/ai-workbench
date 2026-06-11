"""Tests for Full Delivery Loop v1.

Endpoints under test:
  GET  /api/runs/{run_id}/delivery-summary
  POST /api/runs/{run_id}/delivery-report

Safety invariants verified:
  - Both endpoints are read-only — no file mutations, no commands, no providers.
  - No tool_calls created, no run/step status mutations.
  - No auto-apply, no auto-proposal, no auto-rollback.
  - No subprocess/shell execution.
  - No approval creation or bypass.
  - database.py and engine.py not touched.
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
    """Create project, run, and one step."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("# placeholder\n", encoding="utf-8")
    project = isolated_db.create_project(
        "Delivery Test Project",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Test delivery loop",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement feature",
        input="Build the new feature.",
    )
    return project, run, step


@pytest.fixture()
def multi_step_run(isolated_db, tmp_path):
    """Create project, run, and two steps."""
    project_dir = tmp_path / "multi_proj"
    project_dir.mkdir()
    project = isolated_db.create_project("Multi Step Project", str(project_dir))
    run = isolated_db.create_run(prompt="Multi step run", project_id=project.id)
    step1 = isolated_db.create_run_step(run_id=run.id, title="Step One", input="Do one thing.")
    step2 = isolated_db.create_run_step(run_id=run.id, title="Step Two", input="Do another thing.")
    return project, run, step1, step2


def _make_propose_patch(isolated_db, run_id, step_id, project_id, file_path="backend/src/api/routes.py"):
    """Create a propose-patch tool_call."""
    return isolated_db.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name="propose-patch",
        command="",
        status="completed",
        input_json=json.dumps({"operations": [{"file_path": file_path, "old_text": "x", "new_text": "y"}]}),
        output_json=json.dumps({}),
        risk_level="medium",
    )


def _make_apply_patch(isolated_db, run_id, step_id, project_id, file_path="backend/src/api/routes.py"):
    """Create an apply-patch tool_call."""
    return isolated_db.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name="apply-patch",
        command="",
        status="completed",
        input_json=json.dumps({"operations": [{"file_path": file_path, "old_text": "x", "new_text": "y"}]}),
        output_json=json.dumps({"files_changed": 1}),
        risk_level="high",
    )


def _make_run_command(isolated_db, run_id, step_id, project_id, returncode=0):
    """Create a run-command tool_call with given returncode."""
    tc = isolated_db.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name="run-command",
        command=f"{sys.executable} -c 'print(1)'",
        status="completed",
        input_json=json.dumps({"command": "test", "automation": True}),
        output_json=json.dumps({"returncode": returncode}),
        risk_level="medium",
    )
    isolated_db.update_tool_call(
        tc.id, status="completed", returncode=returncode,
        stdout="ok" if returncode == 0 else "FAIL",
        stderr="" if returncode == 0 else "error",
    )
    return tc


def _make_guard_record(isolated_db, run_id, step_id, decision="allowed", is_stale=False):
    """Create a guard result record via guard_result_storage."""
    from src.storage import guard_result_storage
    from src.orchestrator.guard_result_storage_contract import (
        WorkflowGuardDecision,
        WorkflowGuardDriftRisk,
        WorkflowGuardSource,
        WorkflowGuardStaleReason,
        build_guard_input_snapshot,
        build_guard_result_snapshot,
        build_requirement_context_snapshot,
        build_workflow_guard_result_record,
    )
    record_id = f"gr-{decision}-{step_id}"
    gd = {
        "allowed": WorkflowGuardDecision.ALLOWED,
        "blocked": WorkflowGuardDecision.BLOCKED,
        "warning": WorkflowGuardDecision.WARNING,
    }.get(decision, WorkflowGuardDecision.ALLOWED)
    dr = WorkflowGuardDriftRisk.HIGH if decision == "blocked" else WorkflowGuardDriftRisk.LOW
    input_snap = build_guard_input_snapshot(
        proposed_action="Patch feature",
        file_path="backend/src/api/routes.py",
        patch_summary="Test patch",
        old_text="old",
        new_text="new",
    )
    ctx_snap = build_requirement_context_snapshot(
        requirement_ids=["REQ-01"],
        coverage_status="covered",
        drift_risk=dr,
        acceptance_criteria=["Tests pass"],
        constraints=[],
        forbidden_changes=[],
        validation_notes=[],
        source_of_truth_summary="SoT",
    )
    result_snap = build_guard_result_snapshot(
        decision=gd,
        drift_risk=dr,
        matched_requirement_ids=["REQ-01"],
        violated_constraints=[],
        forbidden_change_hits=[],
        warnings=["Blocked"] if decision == "blocked" else [],
        reasons=["Test"],
        recommended_next_step="Proceed",
    )
    record = build_workflow_guard_result_record(
        id=record_id,
        run_id=run_id,
        step_id=step_id,
        project_id=None,
        input_snapshot=input_snap,
        requirement_context_snapshot=ctx_snap,
        result_snapshot=result_snap,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        warning_acknowledged=False,
        no_guard_override=False,
        expires_at=None,
    )
    guard_result_storage.create_guard_result(record)
    if is_stale:
        guard_result_storage.mark_guard_result_stale(record_id, WorkflowGuardStaleReason.MANUAL_INVALIDATION)
    return record_id


# ── Endpoint contract ─────────────────────────────────────────────────────────


class TestEndpointContract:

    # 1. delivery-summary verifies run exists
    def test_delivery_summary_404_missing_run(self, client):
        r = client.get("/api/runs/no-run/delivery-summary")
        assert r.status_code == 404, r.text

    # 2. delivery-report verifies run exists
    def test_delivery_report_404_missing_run(self, client):
        r = client.post("/api/runs/no-run/delivery-report", json={})
        assert r.status_code == 404, r.text

    # 3. delivery-summary is read-only
    def test_delivery_summary_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_step(step.id)
        r = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r.status_code == 200, r.text
        after = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after) == len(before), "No tool_calls should be created by delivery-summary"

    # 4. delivery-report is read-only
    def test_delivery_report_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        before = isolated_db.list_tool_calls_for_step(step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        after = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after) == len(before), "No tool_calls should be created by delivery-report"

    # 5. does not mutate run/step status
    def test_does_not_mutate_run_step_status(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        status_before = step.status
        client.post(f"/api/runs/{run.id}/delivery-report", json={})
        steps_after = isolated_db.list_run_steps(run.id)
        step_after = next((s for s in steps_after if s.id == step.id), None)
        assert step_after is not None
        assert step_after.status == status_before

    # 6. does not call providers (static check)
    def test_no_provider_in_delivery_endpoints(self):
        from src.api import routes as r_module
        source = inspect.getsource(r_module)
        # Find delivery section
        marker = "Full Delivery Loop v1"
        idx = source.find(marker)
        section = source[idx:] if idx != -1 else source
        assert "ollama.chat_completion" not in section
        assert "claude_provider" not in section
        assert "codex." not in section

    # 7. does not execute commands (static check)
    def test_no_command_execution_in_delivery(self):
        from src.api import routes as r_module
        source = inspect.getsource(r_module)
        marker = "Full Delivery Loop v1"
        idx = source.find(marker)
        section = source[idx:] if idx != -1 else source
        calls = re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", section)
        assert not calls, f"subprocess calls found in delivery section: {calls}"

    # 8. does not apply patches (static check)
    def test_no_apply_in_delivery(self):
        from src.api import routes as r_module
        source = inspect.getsource(r_module)
        marker = "Full Delivery Loop v1"
        idx = source.find(marker)
        section = source[idx:] if idx != -1 else source
        calls = re.findall(r"\bapply_project_patch\s*\(", section)
        assert not calls, f"apply_project_patch found in delivery section: {calls}"

    # 9. does not create proposals (static check)
    def test_no_proposal_in_delivery(self):
        from src.api import routes as r_module
        source = inspect.getsource(r_module)
        marker = "Full Delivery Loop v1"
        idx = source.find(marker)
        section = source[idx:] if idx != -1 else source
        calls = re.findall(r"\bpropose_project_patch\s*\(", section)
        assert not calls, f"propose_project_patch found in delivery section: {calls}"

    # 10. response structure is valid
    def test_delivery_report_response_structure(self, client, project_run_step):
        project, run, step = project_run_step
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_markdown": True})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "run_id" in d
        assert "generated_at" in d
        assert "summary" in d
        assert "steps" in d
        assert "markdown_report" in d
        assert "safety_notes" in d
        s = d["summary"]
        assert "readiness" in s
        assert "total_steps" in s
        assert "ready_steps" in s
        assert "blocked_steps" in s


# ── Readiness rules ───────────────────────────────────────────────────────────


class TestReadiness:

    # 11. no activity -> not_started
    def test_no_activity_not_started(self, client, project_run_step):
        project, run, step = project_run_step
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert len(steps) == 1
        assert steps[0]["readiness"] == "not_started"

    # 12. proposal only -> in_progress
    def test_proposal_only_in_progress(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] == "in_progress"

    # 13. successful apply without tests -> needs_tests
    def test_apply_without_tests_needs_tests(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        _make_apply_patch(isolated_db, run.id, step.id, project.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] == "needs_tests"

    # 14. failed test after apply -> tests_failed
    def test_failed_test_after_apply_tests_failed(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        _make_apply_patch(isolated_db, run.id, step.id, project.id)
        _make_run_command(isolated_db, run.id, step.id, project.id, returncode=1)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] == "tests_failed"

    # 15. passed test after apply -> ready_for_review (or delivered_with_warnings)
    def test_passed_test_after_apply_ready(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        _make_apply_patch(isolated_db, run.id, step.id, project.id)
        _make_run_command(isolated_db, run.id, step.id, project.id, returncode=0)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] in ("ready_for_review", "delivered_with_warnings")

    # 16. blocked guard -> blocked
    def test_blocked_guard_blocked_readiness(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard_record(isolated_db, run.id, step.id, decision="blocked")
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] == "blocked"
        assert steps[0]["guard_status"] == "blocked"

    # 17. stale guard -> blocked
    def test_stale_guard_blocked_readiness(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard_record(isolated_db, run.id, step.id, decision="allowed", is_stale=True)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert steps[0]["readiness"] == "blocked"
        assert steps[0]["guard_status"] == "stale"

    # 18. run readiness aggregates blocked step
    def test_run_readiness_aggregates_blocked(self, client, multi_step_run, isolated_db):
        project, run, step1, step2 = multi_step_run
        # step1 is blocked
        _make_guard_record(isolated_db, run.id, step1.id, decision="blocked")
        # step2 is passed
        _make_propose_patch(isolated_db, run.id, step2.id, project.id)
        _make_apply_patch(isolated_db, run.id, step2.id, project.id)
        _make_run_command(isolated_db, run.id, step2.id, project.id, returncode=0)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["summary"]["readiness"] == "blocked"
        assert d["summary"]["blocked_steps"] >= 1

    # 19. run readiness aggregates failed tests
    def test_run_readiness_aggregates_failed_tests(self, client, multi_step_run, isolated_db):
        project, run, step1, step2 = multi_step_run
        # step1 is passed
        _make_propose_patch(isolated_db, run.id, step1.id, project.id)
        _make_apply_patch(isolated_db, run.id, step1.id, project.id)
        _make_run_command(isolated_db, run.id, step1.id, project.id, returncode=0)
        # step2 is tests_failed
        _make_propose_patch(isolated_db, run.id, step2.id, project.id)
        _make_apply_patch(isolated_db, run.id, step2.id, project.id)
        _make_run_command(isolated_db, run.id, step2.id, project.id, returncode=1)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["summary"]["readiness"] == "tests_failed"
        assert d["summary"]["failed_test_steps"] >= 1

    # 20. run readiness ready when all steps ready
    def test_run_readiness_ready_when_all_steps_ready(self, client, multi_step_run, isolated_db):
        project, run, step1, step2 = multi_step_run
        for step in (step1, step2):
            _make_propose_patch(isolated_db, run.id, step.id, project.id)
            _make_apply_patch(isolated_db, run.id, step.id, project.id)
            _make_run_command(isolated_db, run.id, step.id, project.id, returncode=0)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["summary"]["readiness"] in ("ready_for_review", "delivered_with_warnings")
        assert d["summary"]["ready_steps"] == 2


# ── Changed files ─────────────────────────────────────────────────────────────


class TestChangedFiles:

    # 21. extracts file path from propose-patch operation
    def test_extracts_file_path_from_propose(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id, file_path="src/foo.py")
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        all_files = d["summary"]["changed_files"]
        assert "src/foo.py" in all_files

    # 22. extracts file path from apply-patch operation
    def test_extracts_file_path_from_apply(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_apply_patch(isolated_db, run.id, step.id, project.id, file_path="src/bar.py")
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        all_files = d["summary"]["changed_files"]
        assert "src/bar.py" in all_files

    # 23. deduplicates changed files
    def test_deduplicates_changed_files(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        # Same file_path in both propose and apply
        _make_propose_patch(isolated_db, run.id, step.id, project.id, file_path="src/dup.py")
        _make_apply_patch(isolated_db, run.id, step.id, project.id, file_path="src/dup.py")
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        files = d["summary"]["changed_files"]
        dup_count = sum(1 for f in files if f == "src/dup.py")
        assert dup_count == 1, f"Expected exactly 1 occurrence of src/dup.py, got: {files}"

    # 24. handles missing/empty tool_call JSON safely
    def test_handles_empty_tool_call_json(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        # Create a propose-patch with empty JSON
        isolated_db.create_tool_call(
            run_id=run.id, step_id=step.id, project_id=project.id,
            tool_name="propose-patch", command="",
            status="completed", input_json="", output_json="", risk_level="low",
        )
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        assert "summary" in d  # must not crash


# ── Requirement coverage ──────────────────────────────────────────────────────


class TestRequirementCoverage:

    _REQ_INPUT = (
        "Build the feature.\n"
        "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
        "requirement_ids: [REQ-001, REQ-002]\n"
        "coverage_status: covered\n"
        "drift_risk: low\n"
        "END_AI_WORKBENCH_REQUIREMENT_CONTEXT"
    )

    # 25. extracts requirement_ids from step input context
    def test_extracts_requirement_ids_from_input(self, client, isolated_db, tmp_path):
        project_dir = tmp_path / "req_proj"
        project_dir.mkdir()
        project = isolated_db.create_project("Req Project", str(project_dir))
        run = isolated_db.create_run(prompt="req test", project_id=project.id)
        step = isolated_db.create_run_step(
            run_id=run.id, title="Req step", input=self._REQ_INPUT
        )
        from src.main import app
        c = TestClient(app)
        r = c.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        assert "REQ-001" in steps[0]["requirement_ids"]
        assert "REQ-002" in steps[0]["requirement_ids"]

    # 26. warns on unlinked steps
    def test_warns_on_unlinked_steps(self, client, project_run_step):
        project, run, step = project_run_step
        # step.input has no AI_WORKBENCH_REQUIREMENT_CONTEXT
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        d = r.json()
        steps = d["steps"]
        # Step should have a warning about no requirement_ids
        assert any("requirement" in w.lower() or "req" in w.lower() for w in steps[0]["warnings"])

    # 27. includes requirement IDs in markdown
    def test_req_ids_in_markdown(self, client, isolated_db, tmp_path):
        project_dir = tmp_path / "req2"
        project_dir.mkdir()
        project = isolated_db.create_project("Req Project 2", str(project_dir))
        run = isolated_db.create_run(prompt="req test 2", project_id=project.id)
        isolated_db.create_run_step(
            run_id=run.id, title="Req step", input=self._REQ_INPUT
        )
        from src.main import app
        c = TestClient(app)
        r = c.post(f"/api/runs/{run.id}/delivery-report", json={"include_markdown": True})
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "REQ-001" in md or "REQ-002" in md


# ── Markdown format ───────────────────────────────────────────────────────────


class TestMarkdownFormat:

    def _report(self, client, run_id, **kwargs):
        return client.post(f"/api/runs/{run_id}/delivery-report", json={"include_markdown": True, **kwargs})

    # 28. markdown contains Run Summary
    def test_markdown_has_run_summary(self, client, project_run_step):
        _, run, _ = project_run_step
        r = self._report(client, run.id)
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "## Run Summary" in md

    # 29. markdown contains Step Summaries
    def test_markdown_has_step_summaries(self, client, project_run_step):
        _, run, _ = project_run_step
        r = self._report(client, run.id)
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "## Step Summaries" in md

    # 30. markdown contains Changed Files
    def test_markdown_has_changed_files(self, client, project_run_step):
        _, run, _ = project_run_step
        r = self._report(client, run.id)
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "## Changes" in md

    # 31. markdown contains Validation section
    def test_markdown_has_validation(self, client, project_run_step):
        _, run, _ = project_run_step
        r = self._report(client, run.id)
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "## Validation" in md

    # 32. markdown contains Final Recommendation
    def test_markdown_has_final_recommendation(self, client, project_run_step):
        _, run, _ = project_run_step
        r = self._report(client, run.id)
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "## Final Recommendation" in md

    # 33. markdown is bounded by max_markdown_chars
    def test_markdown_bounded_by_max_chars(self, client, project_run_step):
        _, run, _ = project_run_step
        r = client.post(
            f"/api/runs/{run.id}/delivery-report",
            json={"include_markdown": True, "max_markdown_chars": 200},
        )
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert len(md) <= 300, f"Markdown not bounded: {len(md)} chars"


# ── Compatibility ─────────────────────────────────────────────────────────────


class TestCompatibility:

    # 34. bounded loop tests still pass (cross-check route exists)
    def test_bounded_loop_route_still_exists(self, client, project_run_step):
        _, run, step = project_run_step
        r = client.post(
            f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop",
            json={"step_id": step.id, "max_iterations": 1, "dry_run": True},
        )
        assert r.status_code == 200, r.text

    # 35. agent result patch draft bridge still works
    def test_bridge_route_still_exists(self, client, project_run_step):
        _, run, step = project_run_step
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={
                "agent_result": {
                    "summary": "x",
                    "analysis": "",
                    "proposed_files": [],
                    "patch_intent": "",
                    "risks": [],
                    "test_suggestions": [],
                    "questions": [],
                    "recommended_next_action": "",
                    "can_feed_patch_draft": False,
                }
            },
        )
        assert r.status_code == 200, r.text

    # 36. approval-gated automation still works
    def test_approval_route_still_exists(self, client, project_run_step):
        _, run, step = project_run_step
        r = client.get(f"/api/runs/{run.id}/automation/approvals")
        assert r.status_code == 200, r.text

    # 37. automation runner still works
    def test_automation_runner_still_exists(self, client, project_run_step):
        _, run, _ = project_run_step
        r = client.post(
            f"/api/runs/{run.id}/automation/run-next",
            json={"dry_run": True},
        )
        assert r.status_code == 200, r.text

    # 38. operator queue still works
    def test_operator_queue_still_exists(self, client, project_run_step):
        _, run, step = project_run_step
        r = client.get(f"/api/runs/{run.id}/operator-queue?step_id={step.id}")
        assert r.status_code == 200, r.text


# ── Static safety ─────────────────────────────────────────────────────────────


class TestStaticSafety:

    @staticmethod
    def _delivery_section() -> str:
        from src.api import routes
        source = inspect.getsource(routes)
        marker = "Full Delivery Loop v1"
        idx = source.find(marker)
        return source[idx:] if idx != -1 else source

    # 39. no execute_run in delivery endpoints
    def test_no_execute_run(self):
        section = self._delivery_section()
        hits = re.findall(r"\bexecute_run\s*\(", section)
        assert not hits, f"execute_run found in delivery section: {hits}"

    # 40. no asyncio.create_task in delivery endpoints
    def test_no_asyncio_create_task(self):
        section = self._delivery_section()
        hits = re.findall(r"asyncio\.create_task\s*\(", section)
        assert not hits, f"asyncio.create_task found in delivery section: {hits}"

    # 41. no apply_project_patch in delivery endpoints
    def test_no_apply_project_patch(self):
        section = self._delivery_section()
        hits = re.findall(r"\bapply_project_patch\s*\(", section)
        assert not hits, f"apply_project_patch found in delivery section: {hits}"

    # 42. no subprocess/shell command in delivery endpoints
    def test_no_subprocess_in_delivery(self):
        section = self._delivery_section()
        hits = re.findall(r"\bsubprocess\.(run|call|Popen|check_output)\s*\(", section)
        assert not hits, f"subprocess calls found in delivery section: {hits}"

    # 43. no provider calls in delivery endpoints
    def test_no_provider_calls(self):
        section = self._delivery_section()
        assert "ollama.chat_completion" not in section
        assert "claude_provider" not in section
        assert "codex." not in section

    # 44. database.py untouched
    def test_database_py_untouched(self):
        from src.storage import database as db_module
        source = inspect.getsource(db_module)
        assert "delivery-summary" not in source
        assert "DeliveryReport" not in source
        assert "StepDeliverySummary" not in source

    # 45. engine.py untouched
    def test_engine_py_untouched(self):
        from src.orchestrator import engine
        source = inspect.getsource(engine)
        assert "delivery-summary" not in source
        assert "DeliveryReport" not in source
        assert "delivery_build" not in source


# ── Awaiting approval readiness (v2) ──────────────────────────────────────────


def _make_pending_approval(client, run_id: str, step_id: str, action_type: str = "run_tests_manual") -> str:
    """Create a pending automation approval via the API; return approval_id."""
    r = client.post(
        f"/api/runs/{run_id}/automation/approvals",
        json={"step_id": step_id, "action_type": action_type, "reason": "delivery v2 test"},
    )
    assert r.status_code == 200, f"Failed to create approval: {r.text}"
    return r.json()["id"]


class TestAwaitingApproval:
    """Tests for awaiting_approval readiness state (v2)."""

    # 46. pending approval -> step readiness == awaiting_approval
    def test_pending_approval_step_readiness_awaiting(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        assert steps[0]["readiness"] == "awaiting_approval"
        assert steps[0]["approval_status"] == "pending"

    # 47. approval_pending_steps counter increments correctly
    def test_approval_pending_steps_counter(self, client, multi_step_run, isolated_db):
        project, run, step1, step2 = multi_step_run
        # Only step1 has a pending approval
        _make_pending_approval(client, run.id, step1.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        s = r.json()["summary"]
        assert s["approval_pending_steps"] == 1

    # 48. run readiness == awaiting_approval when pending approval + no blocked/failed
    def test_run_readiness_awaiting_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        assert r.json()["summary"]["readiness"] == "awaiting_approval"

    # 49. blocked guard takes priority over awaiting_approval
    def test_blocked_guard_wins_over_awaiting_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard_record(isolated_db, run.id, step.id, decision="blocked")
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        # blocked guard has severity 0; awaiting_approval has severity 2
        assert steps[0]["readiness"] == "blocked"

    # 50. tests_failed takes priority over awaiting_approval
    def test_tests_failed_wins_over_awaiting_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        _make_apply_patch(isolated_db, run.id, step.id, project.id)
        _make_run_command(isolated_db, run.id, step.id, project.id, returncode=1)
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        # tests_failed has severity 1; awaiting_approval has severity 2
        assert steps[0]["readiness"] == "tests_failed"

    # 51. apply + no tests + pending approval -> awaiting_approval beats needs_tests
    def test_awaiting_approval_wins_over_needs_tests(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_propose_patch(isolated_db, run.id, step.id, project.id)
        _make_apply_patch(isolated_db, run.id, step.id, project.id)
        # No test run after apply, but approval is pending
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={})
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        # awaiting_approval (severity 2) wins over needs_tests (severity 3)
        assert steps[0]["readiness"] == "awaiting_approval"

    # 52. markdown contains "Approval pending steps" in Run Summary
    def test_markdown_contains_approval_pending_steps(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_markdown": True})
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "Approval pending steps" in md, f"Expected 'Approval pending steps' in markdown"

    # 53. markdown step summary contains "Approval: pending"
    def test_markdown_step_contains_approval_pending(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={
            "include_markdown": True, "include_step_details": True,
        })
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "Approval: pending" in md, f"Expected 'Approval: pending' in step summary markdown"

    # 54. final recommendation mentions approval when run readiness is awaiting_approval
    def test_final_recommendation_mentions_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_pending_approval(client, run.id, step.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_markdown": True})
        assert r.status_code == 200, r.text
        md = r.json()["markdown_report"]
        assert "Awaiting approval" in md or "awaiting approval" in md.lower(), (
            "Expected final recommendation to mention approval"
        )

    # 55. approval_pending_steps is present in delivery-summary response
    def test_approval_pending_steps_in_delivery_summary(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        r = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r.status_code == 200, r.text
        summary = r.json()
        assert "approval_pending_steps" in summary, (
            "approval_pending_steps field must be present in delivery-summary response"
        )

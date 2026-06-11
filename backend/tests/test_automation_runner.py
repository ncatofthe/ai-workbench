"""Tests for the manual Automation Runner endpoints.

POST /api/runs/{run_id}/automation/run-next
POST /api/runs/{run_id}/automation/run-safe-loop

The runner is intentionally conservative: it may execute read-only
automation and explicitly allowed safe test commands, but it must never create
patch proposals, apply patches, roll back, call providers, or execute runs.
"""

from __future__ import annotations

import inspect
import json
import sys

import pytest
from fastapi.testclient import TestClient

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
from src.storage import database
from src.storage.guard_result_storage import create_guard_result, mark_guard_result_stale


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
    test_command = f"{sys.executable} -c \"print('ok')\""
    project = isolated_db.create_project(
        "Automation Runner Project",
        str(project_dir),
        test_command=test_command,
        safe_commands=[test_command],
    )
    run = isolated_db.create_run(
        prompt="Automation runner test",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Automation step",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-AUTO-01\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT"
        ),
    )
    return project, run, step


def _run_next(client: TestClient, run_id: str, body: dict | None = None):
    return client.post(f"/api/runs/{run_id}/automation/run-next", json=body or {})


def _run_loop(client: TestClient, run_id: str, body: dict | None = None):
    return client.post(f"/api/runs/{run_id}/automation/run-safe-loop", json=body or {})


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


def _tool_names(run_id: str) -> list[str]:
    return [tc.tool_name for tc in database.list_tool_calls_for_run(run_id, limit=500)]


def _make_tc(
    run_id: str,
    step_id: str,
    project_id: str,
    tool_name: str,
    *,
    returncode: int = 0,
    status: str = "completed",
    stdout: str = "",
    stderr: str = "",
    command: str = "",
    input_data: dict | None = None,
    output_data: dict | None = None,
    completed_at: str = "2026-01-01T00:00:00",
):
    tc = database.create_tool_call(
        run_id=run_id,
        project_id=project_id,
        step_id=step_id,
        tool_name=tool_name,
        command=command or tool_name,
        cwd="/fake",
        status=status,
        input_json=json.dumps(input_data or {}),
        output_json=json.dumps(output_data or {"returncode": returncode}),
        risk_level="medium",
    )
    database.update_tool_call(
        tc.id,
        status=status,
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        completed_at=completed_at,
        finished_at=completed_at,
    )
    return tc


def _make_guard(
    run_id: str,
    step_id: str,
    *,
    guard_id: str | None = None,
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
):
    gid = guard_id or f"auto-guard-{run_id[:8]}-{step_id[:8]}"
    record = build_workflow_guard_result_record(
        id=gid,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Automation guarded change",
            file_path="app.py",
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-AUTO-01"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.LOW,
            acceptance_criteria=["Change is verified manually"],
            constraints=[],
            forbidden_changes=[],
            validation_notes=[],
            source_of_truth_summary="Automation runner guard",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.LOW,
            matched_requirement_ids=["REQ-AUTO-01"],
            reasons=["Requirement matched"],
        ),
    )
    create_guard_result(record)
    return gid


def _create_apply_without_tests(project, run, step):
    guard_id = _make_guard(run.id, step.id)
    _make_tc(run.id, step.id, project.id, "propose-patch", output_data={"guard_result_id": guard_id})
    _make_tc(run.id, step.id, project.id, "apply-patch", output_data={"guard_result_id": guard_id})
    return guard_id


class TestAutomationRunner:
    def test_run_next_verifies_run_exists(self, client):
        response = _run_next(client, "missing-run")
        assert response.status_code == 404

    def test_run_next_dry_run_executes_nothing(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        before = _tool_call_count(run.id)

        response = _run_next(client, run.id, {"dry_run": True, "allow_safe_commands": True})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["executed_actions"][0]["status"] == "dry_run"
        assert data["executed_actions"][0]["executed"] is False
        assert _tool_call_count(run.id) == before

    def test_run_next_returns_manual_required_for_apply_patch_manual(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "propose-patch", output_data={"guard_result_id": guard_id})

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "manual_required"
        assert data["skipped_actions"][0]["action_type"] == "apply_patch_manual"
        assert "apply-patch" not in _tool_names(run.id)

    def test_run_next_returns_manual_required_for_create_proposal_manual(self, client, project_run_step):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "manual_required"
        assert data["skipped_actions"][0]["action_type"] == "create_proposal_manual"
        assert "propose-patch" not in _tool_names(run.id)

    def test_run_next_blocks_stale_guard(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _make_guard(run.id, step.id)
        mark_guard_result_stale(guard_id, WorkflowGuardStaleReason.MANUAL_INVALIDATION)

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert data["skipped_actions"][0]["action_type"] == "resolve_blocker"

    def test_run_next_blocks_blocked_guard(self, client, project_run_step):
        project, run, step = project_run_step
        _make_guard(run.id, step.id, decision=WorkflowGuardDecision.BLOCKED)

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert data["skipped_actions"][0]["action_type"] == "resolve_blocker"

    def test_run_next_can_execute_readonly_failed_test_analysis_without_tool_calls(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        _make_tc(
            run.id,
            step.id,
            project.id,
            "run-command",
            returncode=1,
            stdout="FAILED",
            stderr="AssertionError",
            command="pytest",
            input_data={"command_kind": "test"},
            output_data={"returncode": 1, "timed_out": False},
            completed_at="2026-02-01T00:00:00",
        )
        before = _tool_call_count(run.id)

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["executed_actions"][0]["action_type"] == "analyze_failed_tests_manual"
        assert data["executed_actions"][0]["executed"] is True
        assert _tool_call_count(run.id) == before

    def test_run_next_can_prepare_failure_fix_draft_without_db_writes(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        _make_tc(
            run.id,
            step.id,
            project.id,
            "run-command",
            returncode=1,
            stdout="FAILED",
            stderr="AssertionError",
            command="pytest",
            input_data={"command_kind": "test"},
            output_data={"returncode": 1, "timed_out": False},
            completed_at="2026-02-01T00:00:00",
        )
        _make_tc(
            run.id,
            step.id,
            project.id,
            "analyze-command-result",
            output_data={"status": "failed", "summary": "Assertion failed"},
            completed_at="2026-02-02T00:00:00",
        )
        before = _tool_call_count(run.id)

        response = _run_next(client, run.id)

        assert response.status_code == 200
        data = response.json()
        assert data["executed_actions"][0]["action_type"] == "prepare_fix_draft_manual"
        assert data["executed_actions"][0]["executed"] is True
        assert _tool_call_count(run.id) == before

    def test_run_next_does_not_run_tests_without_safe_command_permission(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        before = _tool_call_count(run.id)

        response = _run_next(client, run.id, {"allow_safe_commands": False})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert data["skipped_actions"][0]["action_type"] == "run_tests_manual"
        assert _tool_call_count(run.id) == before

    def test_run_next_can_run_configured_safe_test_command_only_when_allowed(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)

        response = _run_next(
            client,
            run.id,
            {"allow_safe_commands": True, "allow_low_risk_tool_calls": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        action = data["executed_actions"][0]
        assert action["action_type"] == "run_tests_manual"
        assert action["created_tool_call_id"]
        call = next(tc for tc in database.list_tool_calls_for_run(run.id, limit=500) if tc.id == action["created_tool_call_id"])
        assert call.tool_name == "run-command"
        assert call.command == project.test_command
        assert call.returncode == 0

    def test_run_next_rejects_low_risk_tool_calls_when_disabled(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        before = _tool_call_count(run.id)

        response = _run_next(
            client,
            run.id,
            {"allow_safe_commands": True, "allow_low_risk_tool_calls": False},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert "low_risk" in data["skipped_actions"][0]["reason"]
        assert _tool_call_count(run.id) == before

    def test_run_next_never_accepts_or_runs_arbitrary_command_from_request(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)

        response = _run_next(
            client,
            run.id,
            {
                "allow_safe_commands": True,
                "command": "rm app.py",
                "shell": "rm app.py",
            },
        )

        assert response.status_code == 200
        call = next(tc for tc in database.list_tool_calls_for_run(run.id, limit=500) if tc.tool_name == "run-command")
        assert call.command == project.test_command
        assert (project.path and "rm app.py" not in call.command)

    def test_run_safe_loop_respects_max_actions(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)

        response = _run_loop(
            client,
            run.id,
            {"max_actions": 1, "allow_safe_commands": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["executed_actions"]) == 1

    def test_run_safe_loop_stops_on_manual_required(self, client, project_run_step):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)

        response = _run_loop(client, run.id, {"max_actions": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "manual_required"
        assert data["skipped_actions"][0]["action_type"] == "create_proposal_manual"

    def test_run_safe_loop_stops_on_blocked(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _make_guard(run.id, step.id)
        mark_guard_result_stale(guard_id, WorkflowGuardStaleReason.MANUAL_INVALIDATION)

        response = _run_loop(client, run.id, {"max_actions": 3})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "blocked"
        assert data["skipped_actions"][0]["action_type"] == "resolve_blocker"

    def test_run_safe_loop_dry_run_executes_nothing(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        before = _tool_call_count(run.id)

        response = _run_loop(
            client,
            run.id,
            {"max_actions": 2, "dry_run": True, "allow_safe_commands": True},
        )

        assert response.status_code == 200
        assert _tool_call_count(run.id) == before

    def test_run_and_step_status_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_apply_without_tests(project, run, step)
        before_run_status = database.get_run(run.id).status
        before_step_status = next(item for item in database.list_run_steps(run.id) if item.id == step.id).status

        response = _run_next(client, run.id, {"allow_safe_commands": True})

        assert response.status_code == 200
        assert database.get_run(run.id).status == before_run_status
        assert next(item for item in database.list_run_steps(run.id) if item.id == step.id).status == before_step_status

    def test_automation_runner_source_has_no_forbidden_execution_hooks(self):
        from src.api import routes

        source = "\n".join(
            [
                inspect.getsource(routes.automation_run_next),
                inspect.getsource(routes.automation_run_safe_loop),
                inspect.getsource(routes._execute_single_automation_action),
            ]
        )

        assert "execute_run(" not in source
        assert "asyncio.create_task(" not in source
        assert "propose_project_patch" not in source
        assert "apply_project_patch" not in source
        assert "_rollback_patch" not in source
        assert "claude_provider." not in source
        assert "codex." not in source
        assert "ollama." not in source

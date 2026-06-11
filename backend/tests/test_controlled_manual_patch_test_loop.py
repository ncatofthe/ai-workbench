"""Regression tests for the controlled manual patch-test lifecycle loop."""

from __future__ import annotations

import inspect
import sys

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardSource,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
)
from src.storage import database
from src.storage.guard_result_storage import create_guard_result, get_guard_result


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
        "Lifecycle Project",
        str(project_dir),
        test_command=test_command,
        safe_commands=[test_command],
    )
    run = isolated_db.create_run(
        prompt="Manual lifecycle",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Patch lifecycle step",
        input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids:\n- REQ-001\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    )
    return project, run, step


def _op(file_path: str = "app.py", old_text: str = "old", new_text: str = "new") -> dict:
    return {
        "file_path": file_path,
        "old_text": old_text,
        "new_text": new_text,
        "create_if_missing": False,
        "replace_all": False,
    }


def _create_guard(run_id: str, step_id: str, guard_id: str = "lifecycle-guard") -> str:
    record = build_workflow_guard_result_record(
        id=guard_id,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Apply guarded lifecycle change",
            file_path="app.py",
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["Patch is manually applied"],
            constraints=["Tests run manually after apply"],
            forbidden_changes=["Do not touch .env"],
            validation_notes=["Manual lifecycle only"],
            source_of_truth_summary="Apply guarded lifecycle change",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=WorkflowGuardDecision.ALLOWED,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-001"],
            reasons=["Requirement context matched"],
        ),
    )
    create_guard_result(record)
    return guard_id


def _create_guarded_proposal(client: TestClient, project_id: str, run_id: str, step_id: str, guard_id: str) -> dict:
    response = client.post(
        f"/api/projects/{project_id}/tools/propose-patch",
        json={
            "run_id": run_id,
            "step_id": step_id,
            "guard_result_id": guard_id,
            "operations": [_op()],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _apply_guarded_patch(client: TestClient, project_id: str, run_id: str, step_id: str, proposal_id: str) -> dict:
    response = client.post(
        f"/api/projects/{project_id}/tools/apply-patch",
        json={
            "run_id": run_id,
            "step_id": step_id,
            "proposal_id": proposal_id,
            "confirm": True,
            "operations": [_op()],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


def _lifecycle(client: TestClient, run_id: str, step_id: str):
    return client.get(f"/api/runs/{run_id}/steps/{step_id}/patch-lifecycle")


class TestPatchLifecycleEndpoint:
    def test_patch_lifecycle_endpoint_is_read_only(self, client, project_run_step):
        project, run, step = project_run_step
        before = _tool_call_count(run.id)
        before_run_status = database.get_run(run.id).status
        before_step_status = next(item for item in database.list_run_steps(run.id) if item.id == step.id).status

        response = _lifecycle(client, run.id, step.id)

        assert response.status_code == 200
        assert _tool_call_count(run.id) == before
        assert database.get_run(run.id).status == before_run_status
        assert next(item for item in database.list_run_steps(run.id) if item.id == step.id).status == before_step_status

    def test_patch_lifecycle_endpoint_verifies_run_exists(self, client):
        response = _lifecycle(client, "missing-run", "missing-step")
        assert response.status_code == 404

    def test_patch_lifecycle_endpoint_verifies_step_belongs_to_run(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        other_run = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        other_step = isolated_db.create_run_step(run_id=other_run.id, title="Other step")

        response = _lifecycle(client, run.id, other_step.id)

        assert response.status_code == 404

    def test_lifecycle_shows_guarded_proposal_linked_to_guard_result(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _create_guard(run.id, step.id)
        proposal = _create_guarded_proposal(client, project.id, run.id, step.id, guard_id)

        response = _lifecycle(client, run.id, step.id)
        data = response.json()

        assert response.status_code == 200
        assert data["latest_proposal"]["tool_call_id"] == proposal["proposal_id"]
        assert data["latest_proposal"]["guard_result_id"] == guard_id
        assert data["guard_results"][0]["proposal_tool_call_id"] == proposal["proposal_id"]

    def test_lifecycle_shows_successful_guarded_apply_linked_to_same_guard(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _create_guard(run.id, step.id)
        proposal = _create_guarded_proposal(client, project.id, run.id, step.id, guard_id)
        apply_result = _apply_guarded_patch(client, project.id, run.id, step.id, proposal["proposal_id"])

        response = _lifecycle(client, run.id, step.id)
        data = response.json()

        assert response.status_code == 200
        assert data["apply_succeeded"] is True
        assert data["latest_apply"]["tool_call_id"] == apply_result["tool_call_id"]
        assert data["latest_apply"]["guard_result_id"] == guard_id
        assert data["guard_results"][0]["apply_tool_call_id"] == apply_result["tool_call_id"]
        assert get_guard_result(guard_id).apply_tool_call_id == apply_result["tool_call_id"]

    def test_lifecycle_recommends_manual_tests_after_successful_apply_without_tests(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _create_guard(run.id, step.id)
        proposal = _create_guarded_proposal(client, project.id, run.id, step.id, guard_id)
        _apply_guarded_patch(client, project.id, run.id, step.id, proposal["proposal_id"])

        data = _lifecycle(client, run.id, step.id).json()

        assert data["recommended_manual_next_action"] == "run_tests_manual"
        assert data["test_status"] == "not_run"

    def test_lifecycle_shows_tests_passed_after_latest_apply(self, client, project_run_step):
        project, run, step = project_run_step
        guard_id = _create_guard(run.id, step.id)
        proposal = _create_guarded_proposal(client, project.id, run.id, step.id, guard_id)
        _apply_guarded_patch(client, project.id, run.id, step.id, proposal["proposal_id"])
        command_response = client.post(
            f"/api/projects/{project.id}/tools/run-command",
            json={"command_kind": "test", "run_id": run.id, "step_id": step.id},
        )
        assert command_response.status_code == 200

        data = _lifecycle(client, run.id, step.id).json()

        assert data["test_status"] == "passed"
        assert data["tests_after_latest_apply"] is True
        assert data["recommended_manual_next_action"] == "review_success"
        assert data["latest_test"]["returncode"] == 0

    def test_lifecycle_shows_tests_failed_and_recommends_manual_analysis(self, client, isolated_db, tmp_path):
        project_dir = tmp_path / "failed-project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("old\n", encoding="utf-8")
        test_command = f"{sys.executable} -c \"import sys; sys.exit(1)\""
        project = isolated_db.create_project(
            "Failed Lifecycle Project",
            str(project_dir),
            test_command=test_command,
            safe_commands=[test_command],
        )
        run = isolated_db.create_run(prompt="Failed tests", project_id=project.id, project_path=project.path)
        step = isolated_db.create_run_step(run_id=run.id, title="Failed lifecycle step", input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids: []\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT")
        guard_id = _create_guard(run.id, step.id, "failed-lifecycle-guard")
        proposal = _create_guarded_proposal(client, project.id, run.id, step.id, guard_id)
        _apply_guarded_patch(client, project.id, run.id, step.id, proposal["proposal_id"])
        command_response = client.post(
            f"/api/projects/{project.id}/tools/run-command",
            json={"command_kind": "test", "run_id": run.id, "step_id": step.id},
        )
        assert command_response.status_code == 200

        data = _lifecycle(client, run.id, step.id).json()

        assert data["test_status"] == "failed"
        assert data["recommended_manual_next_action"] == "analyze_failed_tests_manual"
        assert data["latest_test"]["returncode"] == 1

    def test_safe_command_runner_rejects_blocked_test_command(self, client, isolated_db, tmp_path):
        project_dir = tmp_path / "blocked-project"
        project_dir.mkdir()
        (project_dir / "app.py").write_text("old\n", encoding="utf-8")
        project = isolated_db.create_project(
            "Blocked Command Project",
            str(project_dir),
            test_command="rm app.py",
            safe_commands=["rm app.py"],
        )

        response = client.post(
            f"/api/projects/{project.id}/tools/run-command",
            json={"command_kind": "test"},
        )

        assert response.status_code == 400
        assert (project_dir / "app.py").exists()

    def test_lifecycle_function_contains_no_execution_hooks(self):
        from src.api import routes

        source = inspect.getsource(routes.get_step_patch_lifecycle)

        assert "create_tool_call" not in source
        assert "execute_run" not in source
        assert "asyncio.create_task" not in source
        assert "subprocess" not in source
        assert "codex" not in source
        assert "claude_provider" not in source
        assert "_run_safe_command" not in source

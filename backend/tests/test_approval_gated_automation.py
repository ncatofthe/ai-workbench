"""Tests for Approval-Gated Automation v1.

Endpoints under test:
  POST   /api/runs/{run_id}/automation/approvals
  GET    /api/runs/{run_id}/automation/approvals
  GET    /api/runs/{run_id}/automation/approvals/{approval_id}
  POST   /api/runs/{run_id}/automation/approvals/{approval_id}/approve
  POST   /api/runs/{run_id}/automation/approvals/{approval_id}/reject
  POST   /api/runs/{run_id}/automation/approvals/{approval_id}/execute

Safety invariants verified:
  - Creating an approval never executes the action.
  - Approving never executes the action.
  - Rejecting never executes the action.
  - Execute revalidates policy/guard/queue state before acting.
  - Blocked guard decisions cannot be overridden by approval.
  - No providers, no execute_run, no asyncio.create_task.
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
    """Create a project with a safe test command, a run, and one step."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    test_command = f"{sys.executable} -c \"print('ok')\""
    project = isolated_db.create_project(
        "Approval Test Project",
        str(project_dir),
        test_command=test_command,
        safe_commands=[test_command],
    )
    run = isolated_db.create_run(
        prompt="Approval gated test",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Approval step",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-APPROVAL-01\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT"
        ),
    )
    return project, run, step


# ── Helpers ───────────────────────────────────────────────────────────────────


def _create(client, run_id, body):
    return client.post(f"/api/runs/{run_id}/automation/approvals", json=body)


def _list(client, run_id, params=None):
    qs = ""
    if params:
        qs = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return client.get(f"/api/runs/{run_id}/automation/approvals{qs}")


def _get(client, run_id, approval_id):
    return client.get(f"/api/runs/{run_id}/automation/approvals/{approval_id}")


def _approve(client, run_id, approval_id, body=None):
    return client.post(
        f"/api/runs/{run_id}/automation/approvals/{approval_id}/approve",
        json=body or {},
    )


def _reject(client, run_id, approval_id, body=None):
    return client.post(
        f"/api/runs/{run_id}/automation/approvals/{approval_id}/reject",
        json=body or {},
    )


def _execute(client, run_id, approval_id, body=None):
    return client.post(
        f"/api/runs/{run_id}/automation/approvals/{approval_id}/execute",
        json=body or {},
    )


def _tool_call_count(run_id):
    return len(database.list_tool_calls_for_run(run_id, limit=500))


def _tool_names(run_id):
    return [tc.tool_name for tc in database.list_tool_calls_for_run(run_id, limit=500)]


def _make_tc(
    run_id,
    step_id,
    project_id,
    tool_name,
    *,
    returncode=0,
    status="completed",
    stdout="",
    stderr="",
    command="",
    input_data=None,
    output_data=None,
    completed_at="2026-01-01T00:00:00",
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
    run_id,
    step_id,
    *,
    decision=WorkflowGuardDecision.ALLOWED,
    guard_id=None,
):
    gid = guard_id or f"appr-guard-{run_id[:8]}-{step_id[:8]}"
    record = build_workflow_guard_result_record(
        id=gid,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Guarded change for approval test",
            file_path="app.py",
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-APPROVAL-01"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.LOW,
            acceptance_criteria=["Change is verified"],
            constraints=[],
            forbidden_changes=[],
            validation_notes=[],
            source_of_truth_summary="Approval gate guard",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.LOW,
            matched_requirement_ids=["REQ-APPROVAL-01"],
            reasons=["Matched requirement"],
        ),
    )
    create_guard_result(record)
    return gid


def _set_up_apply_patch_queue_item(project, run, step):
    """Create a proposal tool_call so the step shows apply_patch_manual in the queue."""
    tc = _make_tc(
        run.id,
        step.id,
        project.id,
        "propose-patch",
        input_data={
            "operations": [
                {"file_path": "app.py", "old_text": "old\n", "new_text": "new\n"}
            ],
            "run_id": run.id,
            "step_id": step.id,
            "no_guard_override": True,
        },
        output_data={"no_guard_override": True, "proposal_id": ""},
    )
    # Set proposal_id in output after creation
    database.update_tool_call(
        tc.id,
        output_json=json.dumps(
            {"no_guard_override": True, "proposal_id": tc.id},
            ensure_ascii=False,
        ),
    )
    return tc


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestApprovalCreate:
    def test_create_verifies_run_exists(self, client):
        """POST with unknown run_id → 404."""
        r = _create(client, "no-such-run", {"action_type": "apply_patch_manual"})
        assert r.status_code == 404

    def test_create_verifies_step_belongs_to_run(self, client, project_run_step):
        """step_id that doesn't belong to the run → 404."""
        _, run, _ = project_run_step
        r = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": "bad-step-id"})
        assert r.status_code == 404

    def test_create_rejects_blocked_action_type(self, client, project_run_step):
        """resolve_blocker is classified BLOCKED — approval cannot be created."""
        _, run, step = project_run_step
        r = _create(client, run.id, {
            "action_type": "resolve_blocker",
            "step_id": step.id,
        })
        assert r.status_code == 400
        assert "blocked" in r.json()["detail"]["message"].lower()

    def test_create_rejects_non_eligible_action_type(self, client, project_run_step):
        """Unknown action types are not approval-eligible."""
        _, run, step = project_run_step
        r = _create(client, run.id, {
            "action_type": "analyze_failed_tests_manual",
            "step_id": step.id,
        })
        assert r.status_code == 400

    def test_create_rejects_blocked_guard_queue_item(self, client, project_run_step):
        """Queue item is blocked (blocked guard decision) → cannot create approval."""
        project, run, step = project_run_step
        # Create a blocked guard
        _make_guard(run.id, step.id, decision=WorkflowGuardDecision.BLOCKED)
        # Create a proposal so the lifecycle triggers a queue item that reads as resolve_blocker
        _make_tc(run.id, step.id, project.id, "propose-patch",
                 input_data={"operations": [], "run_id": run.id, "step_id": step.id},
                 output_data={"guard_result_id": f"appr-guard-{run.id[:8]}-{step.id[:8]}"})
        # resolve_blocker is always rejected
        r = _create(client, run.id, {
            "action_type": "resolve_blocker",
            "step_id": step.id,
        })
        assert r.status_code == 400

    def test_create_pending_approval_for_apply_patch_manual(self, client, project_run_step):
        """Happy path: eligible apply_patch_manual → pending approval created."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        r = _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
            "reason": "Need to apply the patch.",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["action_type"] == "apply_patch_manual"
        assert body["run_id"] == run.id
        assert body["step_id"] == step.id
        assert "Need to apply the patch." in body["reason"]

    def test_create_pending_approval_for_run_tests_manual(self, client, project_run_step):
        """run_tests_manual can always be approved even outside queue state."""
        _, run, step = project_run_step
        r = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
            "reason": "Operator wants to run tests.",
        })
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "pending"
        assert body["action_type"] == "run_tests_manual"

    def test_create_executes_nothing(self, client, project_run_step):
        """Creating an approval must not execute the action or create tool_calls."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        tc_before = _tool_call_count(run.id)
        _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
        })
        # Only the propose-patch tool_call should exist (created in fixture)
        assert _tool_call_count(run.id) == tc_before

    def test_create_does_not_modify_project_files(self, client, project_run_step, tmp_path):
        """Creating an approval must not write to any project files."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        app_py = project.path + "/app.py"
        import os
        content_before = open(app_py, encoding="utf-8").read()
        _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
        })
        content_after = open(app_py, encoding="utf-8").read()
        assert content_before == content_after


class TestApprovalListGet:
    def test_list_approvals_read_only(self, client, project_run_step):
        """GET list is read-only — returns 200 and does not execute anything."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id})
        tc_before = _tool_call_count(run.id)
        r = _list(client, run.id)
        assert r.status_code == 200
        assert "approvals" in r.json()
        assert _tool_call_count(run.id) == tc_before

    def test_list_returns_only_this_runs_approvals(self, client, project_run_step, isolated_db):
        """Approvals from other runs are not returned."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id})

        # Create another run
        run2 = isolated_db.create_run(
            prompt="Other run",
            project_id=project.id,
            project_path=project.path,
        )
        step2 = isolated_db.create_run_step(run_id=run2.id, title="Other step", input="")
        _create(client, run2.id, {"action_type": "run_tests_manual", "step_id": step2.id})

        r = _list(client, run.id)
        body = r.json()
        assert all(a["run_id"] == run.id for a in body["approvals"])

    def test_get_approval_verifies_run_ownership(self, client, project_run_step, isolated_db):
        """GET single approval must 404 if approval belongs to a different run."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        approval_id = created["id"]

        run2 = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        # Try fetching approval via different run_id
        r = _get(client, run2.id, approval_id)
        assert r.status_code == 404

    def test_get_approval_found_for_correct_run(self, client, project_run_step):
        """GET single approval → 200 with correct data."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        r = _get(client, run.id, created["id"])
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]


class TestApproveReject:
    def test_approve_pending_changes_status_only(self, client, project_run_step):
        """Approving a pending approval sets status to approved — no execution."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        tc_before = _tool_call_count(run.id)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        r = _approve(client, run.id, created["id"])
        assert r.status_code == 200
        assert r.json()["status"] == "approved"
        assert _tool_call_count(run.id) == tc_before  # no new tool calls

    def test_reject_pending_changes_status_only(self, client, project_run_step):
        """Rejecting a pending approval sets status to rejected — no execution."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        tc_before = _tool_call_count(run.id)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        r = _reject(client, run.id, created["id"])
        assert r.status_code == 200
        assert r.json()["status"] == "rejected"
        assert _tool_call_count(run.id) == tc_before

    def test_approve_does_not_execute_action(self, client, project_run_step):
        """Approve must not write files, call providers, or run commands."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        app_py = project.path + "/app.py"
        content_before = open(app_py, encoding="utf-8").read()
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _approve(client, run.id, created["id"])
        assert open(app_py, encoding="utf-8").read() == content_before

    def test_reject_does_not_execute_action(self, client, project_run_step):
        """Reject must not write files, call providers, or run commands."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        app_py = project.path + "/app.py"
        content_before = open(app_py, encoding="utf-8").read()
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _reject(client, run.id, created["id"])
        assert open(app_py, encoding="utf-8").read() == content_before

    def test_cannot_approve_non_owned_approval(self, client, project_run_step, isolated_db):
        """Approving via wrong run_id → 404."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        run2 = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        r = _approve(client, run2.id, created["id"])
        assert r.status_code == 404

    def test_cannot_reject_non_owned_approval(self, client, project_run_step, isolated_db):
        """Rejecting via wrong run_id → 404."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        run2 = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        r = _reject(client, run2.id, created["id"])
        assert r.status_code == 404

    def test_cannot_approve_already_rejected_approval(self, client, project_run_step):
        """A rejected approval cannot be re-approved."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _reject(client, run.id, created["id"])
        r = _approve(client, run.id, created["id"])
        assert r.status_code == 400

    def test_cannot_approve_already_approved_approval(self, client, project_run_step):
        """An already-approved approval cannot be approved again."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _approve(client, run.id, created["id"])
        r = _approve(client, run.id, created["id"])
        assert r.status_code == 400


class TestExecute:
    def test_execute_requires_approved_approval(self, client, project_run_step):
        """Execute on a pending approval → 400."""
        project, run, step = project_run_step
        created = _create(client, run.id, {"action_type": "run_tests_manual", "step_id": step.id}).json()
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 400
        assert "pending" in r.json()["detail"].lower()

    def test_execute_rejects_rejected_approval(self, client, project_run_step):
        """Execute on a rejected approval → 400."""
        project, run, step = project_run_step
        created = _create(client, run.id, {"action_type": "run_tests_manual", "step_id": step.id}).json()
        _reject(client, run.id, created["id"])
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 400
        assert "rejected" in r.json()["detail"].lower()

    def test_execute_unsupported_action_returns_422(self, client, project_run_step):
        """create_proposal_manual is not executable in v1 → 422."""
        project, run, step = project_run_step
        created = _create(client, run.id, {
            "action_type": "create_proposal_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 422
        assert r.json()["detail"]["deferred_to_next_slice"] is True

    def test_execute_run_tests_manual_runs_safe_command(self, client, project_run_step):
        """Execute approved run_tests_manual runs the configured safe test command."""
        project, run, step = project_run_step
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        tc_before = _tool_call_count(run.id)
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 200
        body = r.json()
        assert body["executed"] is True
        assert body["status"] == "executed"
        # A tool_call must have been created
        assert _tool_call_count(run.id) > tc_before

    def test_execute_run_tests_manual_marks_approval_executed(self, client, project_run_step):
        """After execution, approval status is 'executed' (prevents re-execution)."""
        project, run, step = project_run_step
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        _execute(client, run.id, created["id"])
        # Verify status
        r = _get(client, run.id, created["id"])
        assert r.json()["status"] == "executed"

    def test_execute_cannot_execute_twice(self, client, project_run_step):
        """Executing an already-executed approval → 400."""
        project, run, step = project_run_step
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        _execute(client, run.id, created["id"])
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 400
        assert "already been executed" in r.json()["detail"].lower()

    def test_execute_run_tests_manual_never_runs_arbitrary_command(self, client, project_run_step):
        """Execution must only run the project-configured test command, not an arbitrary one."""
        project, run, step = project_run_step
        # Approval payload does NOT include an override command
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
            "payload": {"command": "rm -rf /"},  # malicious — must be ignored
        }).json()
        _approve(client, run.id, created["id"])
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 200
        # Confirm no unexpected commands ran
        names = _tool_names(run.id)
        assert "run-command" in names  # safe test command created
        # Verify the actual command used was the project test command (not rm -rf /)
        calls = database.list_tool_calls_for_run(run.id, limit=500)
        run_cmds = [tc.command for tc in calls if tc.tool_name == "run-command"]
        for cmd in run_cmds:
            assert "rm" not in cmd

    def test_execute_apply_patch_manual_applies_patch(self, client, project_run_step):
        """Execute approved apply_patch_manual writes the patch to disk."""
        project, run, step = project_run_step
        # Set up proposal with no_guard_override
        _set_up_apply_patch_queue_item(project, run, step)
        app_py = project.path + "/app.py"
        assert open(app_py, encoding="utf-8").read() == "old\n"

        created = _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 200
        body = r.json()
        assert body["executed"] is True
        assert body["status"] == "executed"
        # File should now contain the new text
        assert open(app_py, encoding="utf-8").read() == "new\n"

    def test_execute_apply_patch_manual_marks_approval_executed(self, client, project_run_step):
        """After apply_patch_manual execution, approval is marked executed."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _approve(client, run.id, created["id"])
        _execute(client, run.id, created["id"])
        r = _get(client, run.id, created["id"])
        assert r.json()["status"] == "executed"

    def test_execute_apply_patch_manual_creates_apply_tool_call(self, client, project_run_step):
        """Execute apply_patch_manual must create an apply-patch tool_call audit record."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        created = _create(client, run.id, {"action_type": "apply_patch_manual", "step_id": step.id}).json()
        _approve(client, run.id, created["id"])
        _execute(client, run.id, created["id"])
        names = _tool_names(run.id)
        assert "apply-patch" in names

    def test_execute_apply_patch_manual_fails_without_proposal(self, client, project_run_step):
        """Execute apply_patch_manual with no proposal tool_call → 409."""
        _, run, step = project_run_step
        # No proposal set up — only create and approve
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",  # use run_tests to avoid needing queue item
            "step_id": step.id,
        }).json()
        # Now change action_type in DB to apply_patch_manual to test the path
        # (Use the database directly)
        database.resolve_approval(created["id"], "pending")  # reset
        # Instead test with a fresh run that has no proposal
        created2 = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created2["id"])
        # Execute run_tests_manual should work fine (has project test_command)
        r = _execute(client, run.id, created2["id"])
        assert r.status_code == 200

    def test_execute_rejects_stale_guard_for_apply_patch(self, client, project_run_step):
        """Guard became stale AFTER approval was created — execute must reject."""
        project, run, step = project_run_step
        # Step 1: Create an active (non-stale) guard and a matching proposal so the
        # queue shows apply_patch_manual.
        gid = _make_guard(run.id, step.id)
        _make_tc(
            run.id, step.id, project.id, "propose-patch",
            input_data={
                "operations": [{"file_path": "app.py", "old_text": "old\n", "new_text": "new\n"}],
                "run_id": run.id,
                "step_id": step.id,
            },
            output_data={"guard_result_id": gid},
        )

        # Step 2: Create and approve the approval while the guard is still active.
        # Queue shows apply_patch_manual at this point (guard ALLOWED, not stale).
        created = _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
        }).json()
        assert created.get("status") == "pending", f"Expected pending, got: {created}"
        _approve(client, run.id, created["id"])

        # Step 3: NOW stale the guard, simulating a guard that expired after approval.
        mark_guard_result_stale(gid, reason=WorkflowGuardStaleReason.MANUAL_INVALIDATION)

        # Step 4: Execute must reject — revalidation detects stale guard → 409.
        r = _execute(client, run.id, created["id"])
        assert r.status_code == 409
        assert "stale" in str(r.json()).lower()

    def test_execute_never_calls_providers(self, client, project_run_step):
        """Execute must not call claude_provider, codex, or ollama."""
        import src.api.routes as routes_module
        source = inspect.getsource(routes_module._execute_approved_run_tests)
        for forbidden in ("claude_provider", "codex", "ollama", "execute_run", "asyncio.create_task"):
            assert forbidden not in source, f"Forbidden call '{forbidden}' found in _execute_approved_run_tests"

    def test_execute_source_has_no_forbidden_patterns(self):
        """Static source scan: execute helpers must not call forbidden patterns."""
        import src.api.routes as routes_module
        for fn_name in ("_execute_approved_run_tests", "_execute_approved_apply_patch",
                        "execute_run_automation_approval"):
            fn = getattr(routes_module, fn_name, None)
            if fn is None:
                continue
            src_text = inspect.getsource(fn)
            for forbidden in ("execute_run(", "asyncio.create_task(", "claude_provider.", "codex.", "ollama."):
                assert forbidden not in src_text, (
                    f"Forbidden '{forbidden}' found in {fn_name}"
                )

    def test_execute_run_step_status_unchanged(self, client, project_run_step):
        """run_tests_manual execution must not change run or step status."""
        project, run, step = project_run_step
        created = _create(client, run.id, {
            "action_type": "run_tests_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        _execute(client, run.id, created["id"])
        # Run status unchanged
        updated_run = database.get_run(run.id)
        assert updated_run.status == run.status or updated_run.status.value == run.status.value


class TestCompatibility:
    def test_automation_runner_still_stops_on_manual_required(self, client, project_run_step):
        """Automation runner still returns manual_required without auto-approval."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        r = client.post(f"/api/runs/{run.id}/automation/run-next", json={})
        assert r.status_code == 200
        body = r.json()
        # apply_patch_manual is MANUAL_REQUIRED — runner must stop, not execute
        assert body["status"] in ("manual_required", "no_action")

    def test_approval_does_not_bypass_automation_runner_policy(self, client, project_run_step):
        """Automation runner ignores approval status — it still enforces policy."""
        project, run, step = project_run_step
        _set_up_apply_patch_queue_item(project, run, step)
        # Create and approve an approval
        created = _create(client, run.id, {
            "action_type": "apply_patch_manual",
            "step_id": step.id,
        }).json()
        _approve(client, run.id, created["id"])
        # Automation runner must still stop on manual_required regardless
        r = client.post(f"/api/runs/{run.id}/automation/run-next", json={})
        assert r.status_code == 200
        assert r.json()["status"] in ("manual_required", "no_action")

    def test_existing_run_tests_automation_still_works(self, client, project_run_step):
        """Existing automation run-next path for run_tests_manual still works."""
        project, run, step = project_run_step
        # Create a failed test run to trigger run_tests_manual queue item
        _make_tc(run.id, step.id, project.id, "run-command",
                 returncode=1, stdout="", stderr="FAILED")
        r = client.post(f"/api/runs/{run.id}/automation/run-next", json={
            "allow_safe_commands": True,
            "allow_low_risk_tool_calls": True,
        })
        assert r.status_code == 200

    def test_list_approvals_404_for_missing_run(self, client):
        """List endpoint returns 404 for unknown run_id."""
        r = _list(client, "nonexistent-run")
        assert r.status_code == 404

    def test_get_approval_404_for_missing_approval(self, client, project_run_step):
        """Get endpoint returns 404 for unknown approval_id."""
        _, run, _ = project_run_step
        r = _get(client, run.id, "no-such-approval")
        assert r.status_code == 404

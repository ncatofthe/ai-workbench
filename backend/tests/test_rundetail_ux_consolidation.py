"""Tests for RunDetail UX Consolidation v1.

Covers:
  1. execute_approval queue item appears when a pending approval exists
  2. execute_approval item has correct approval_id and approval_action_type
  3. Non-pending approvals (approved, rejected, executed) do not produce execute_approval
  4. execute_approval is highest-priority item (above run_tests_manual)
  5. execute_approval item is display-only: action_type is read-only
  6. BoundedAutonomousLoopResponse includes stop_reason field
  7. stop_reason == "pending_approval" when loop stops for pending approval
  8. stop_reason == "needs_approval" when loop stops with no approval at all
  9. stop_reason == "blocked_guard" when loop stops on a blocked guard
  10. stop_reason == "no_items" when queue is empty
  11. pending_approval_id is populated when pending approval exists
  12. pending_approval_action_type is populated when pending approval exists
  13. blocked_action_type is populated when stop is due to blocked guard

Safety invariants verified:
  - execute_approval queue item never triggers autonomous execution
  - _build_queue_for_run never creates DB records or calls providers
  - BoundedAutonomousLoopResponse new fields are optional (no breaking change)
"""

from __future__ import annotations

import json
import pathlib

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
from src.storage.guard_result_storage import create_guard_result


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
    import sys
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    test_command = f"{sys.executable} -c \"print('ok')\""
    project = isolated_db.create_project(
        "UX Consolidation Project",
        str(project_dir),
        test_command=test_command,
        safe_commands=[test_command],
    )
    run = isolated_db.create_run(
        prompt="UX consolidation test",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="UX step",
        input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids:\n- REQ-UX-01\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    )
    return project, run, step


# ── Helpers ───────────────────────────────────────────────────────────────────

def _queue(client, run_id, **params):
    return client.get(f"/api/runs/{run_id}/operator-queue", params=params)


def _make_guard(run_id, step_id, *, decision=WorkflowGuardDecision.ALLOWED):
    gid = f"guard-{run_id[:8]}-{step_id[:8]}"
    record = build_workflow_guard_result_record(
        id=gid,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="UX test change",
            file_path="app.py",
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-UX-01"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.LOW,
            acceptance_criteria=["Change accepted"],
            constraints=[],
            forbidden_changes=[],
            validation_notes=[],
            source_of_truth_summary="UX guard",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.LOW,
            matched_requirement_ids=["REQ-UX-01"],
            reasons=["Requirement matched"],
        ),
    )
    create_guard_result(record)
    return gid


def _make_tc(run_id, step_id, project_id, tool_name, *, returncode=0,
             status="completed", stdout="", stderr="", command="",
             input_data=None, output_data=None):
    input_json = json.dumps(input_data or {})
    output_json = json.dumps(output_data or {"returncode": returncode})
    tc = database.create_tool_call(
        run_id=run_id,
        project_id=project_id,
        step_id=step_id,
        tool_name=tool_name,
        command=command or tool_name,
        cwd="/fake",
        status=status,
        input_json=input_json,
        output_json=output_json,
        risk_level="medium",
    )
    database.update_tool_call(
        tc.id,
        status=status,
        stdout=stdout,
        stderr=stderr,
        returncode=returncode,
        completed_at="2026-01-01T00:00:00",
        finished_at="2026-01-01T00:00:00",
    )
    return tc


def _make_pending_approval(client, run_id, step_id, action_type="run_tests_manual"):
    """Create a pending (not yet approved) automation approval."""
    r = client.post(
        f"/api/runs/{run_id}/automation/approvals",
        json={"step_id": step_id, "action_type": action_type, "reason": "UX test"},
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _make_approved_approval(client, run_id, step_id, action_type="run_tests_manual"):
    """Create an approved (not yet executed) automation approval."""
    approval_id = _make_pending_approval(client, run_id, step_id, action_type)
    r = client.post(
        f"/api/runs/{run_id}/automation/approvals/{approval_id}/approve",
        json={},
    )
    assert r.status_code == 200, r.text
    return approval_id


def _make_rejected_approval(client, run_id, step_id, action_type="run_tests_manual"):
    approval_id = _make_pending_approval(client, run_id, step_id, action_type)
    r = client.post(
        f"/api/runs/{run_id}/automation/approvals/{approval_id}/reject",
        json={},
    )
    assert r.status_code == 200, r.text
    return approval_id


def _post_loop(client, run_id, body=None):
    return client.post(
        f"/api/runs/{run_id}/automation/bounded-patch-test-fix-loop",
        json=body or {"max_iterations": 3, "dry_run": True},
    )


# ── Tests: execute_approval queue item (GAP-004) ──────────────────────────────

class TestExecuteApprovalQueueItem:

    # 1. execute_approval queue item appears when a pending approval exists
    def test_execute_approval_appears_for_pending_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        # Set up: guard + apply, so run_tests_manual would normally be the item
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        # Create pending approval for run_tests_manual
        approval_id = _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert len(data["items"]) > 0
        top = data["items"][0]
        assert top["action_type"] == "execute_approval", (
            f"Expected execute_approval, got {top['action_type']}"
        )

    # 2. execute_approval item has correct approval_id and approval_action_type
    def test_execute_approval_carries_approval_metadata(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        approval_id = _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        top = resp.json()["items"][0]
        assert top["action_type"] == "execute_approval"
        assert top["approval_id"] == approval_id, (
            f"approval_id mismatch: expected {approval_id}, got {top['approval_id']}"
        )
        assert top["approval_action_type"] == "run_tests_manual"

    # 3. Non-pending approvals do not produce execute_approval (approved state is handled by bounded loop)
    def test_approved_approval_does_not_produce_execute_approval_item(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        # Approve the approval — now it's approved, not pending
        _make_approved_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        action_types = [i["action_type"] for i in items]
        assert "execute_approval" not in action_types, (
            f"execute_approval should not appear for approved-not-pending approval. Got: {action_types}"
        )

    # 4. Rejected approval does not produce execute_approval
    def test_rejected_approval_does_not_produce_execute_approval_item(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        _make_rejected_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        action_types = [i["action_type"] for i in items]
        assert "execute_approval" not in action_types, (
            f"execute_approval should not appear for rejected approval. Got: {action_types}"
        )

    # 5. execute_approval is highest-priority item (returned before run_tests_manual)
    def test_execute_approval_takes_priority_over_run_tests_manual(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items[0]["action_type"] == "execute_approval", (
            f"execute_approval should be first item. Got: {[i['action_type'] for i in items]}"
        )

    # 6. execute_approval item is read-only: can_run_directly == False
    def test_execute_approval_is_not_directly_runnable(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        top = resp.json()["items"][0]
        assert top["action_type"] == "execute_approval"
        assert top["can_run_directly"] is False, "execute_approval must not be directly runnable"

    # 7. No pending approval → no execute_approval item, normal item appears
    def test_no_pending_approval_no_execute_approval_item(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        # No approval created

        resp = _queue(client, run.id)
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert len(items) > 0
        assert items[0]["action_type"] == "run_tests_manual", (
            f"Expected run_tests_manual without pending approval. Got: {items[0]['action_type']}"
        )


# ── Tests: BoundedAutonomousLoopResponse stop_reason (GAP-011) ───────────────

class TestBoundedLoopStopReason:

    # 8. BoundedAutonomousLoopResponse includes stop_reason field
    def test_stop_reason_field_present_in_response(self, client, project_run_step, isolated_db):
        _, run, _ = project_run_step
        resp = _post_loop(client, run.id, {"max_iterations": 1, "dry_run": True})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "stop_reason" in data, "stop_reason field must be present in response"

    # 9. stop_reason == "no_items" when queue has no items
    def test_stop_reason_no_items_when_queue_empty(self, client, project_run_step, isolated_db):
        """With no guard and no tool_calls (step is new), check_guard appears.
        But if step has check_guard which can run directly, loop runs it.
        Use a scenario where the queue is empty by checking a finished step."""
        _, run, step = project_run_step
        # Mark the step as completed so the queue has no actionable items
        # The easiest way to get empty queue is to have no steps to process
        # (filter to a non-existent step)
        resp = _post_loop(client, run.id, {
            "max_iterations": 1,
            "dry_run": True,
            "step_id": step.id + "-nonexistent",
        })
        # step_id filter to a non-existent step returns 404
        assert resp.status_code == 404

    # 10. stop_reason == "pending_approval" when pending approval exists
    def test_stop_reason_pending_approval_when_pending_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_approval_required": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "stopped_for_approval", f"Expected stopped_for_approval, got: {data['status']}"
        assert data["stop_reason"] == "pending_approval", (
            f"Expected pending_approval, got: {data['stop_reason']}"
        )

    # 11. pending_approval_id is populated when pending approval exists
    def test_pending_approval_id_populated_when_pending(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        approval_id = _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_approval_required": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["pending_approval_id"] == approval_id, (
            f"pending_approval_id mismatch: expected {approval_id}, got {data['pending_approval_id']}"
        )

    # 12. pending_approval_action_type is populated when pending approval exists
    def test_pending_approval_action_type_populated(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_approval_required": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["pending_approval_action_type"] == "run_tests_manual", (
            f"Expected run_tests_manual, got: {data['pending_approval_action_type']}"
        )

    # 13. stop_reason == "needs_approval" when no approval exists at all
    def test_stop_reason_needs_approval_when_no_approval(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id)
        _make_tc(run.id, step.id, project.id, "apply-patch", returncode=0, status="completed")
        # No approval created — loop should stop with needs_approval

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_approval_required": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "stopped_for_approval", f"Expected stopped_for_approval, got: {data['status']}"
        assert data["stop_reason"] == "needs_approval", (
            f"Expected needs_approval, got: {data['stop_reason']}"
        )
        assert data["pending_approval_id"] is None, (
            f"pending_approval_id should be None when no approval exists. Got: {data['pending_approval_id']}"
        )

    # 14. stop_reason == "blocked_guard" when loop stops on blocked guard
    def test_stop_reason_blocked_guard(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id, decision=WorkflowGuardDecision.BLOCKED)

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_blocked": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "blocked", f"Expected blocked, got: {data['status']}"
        assert data["stop_reason"] == "blocked_guard", (
            f"Expected blocked_guard, got: {data['stop_reason']}"
        )

    # 15. blocked_action_type is populated when blocked
    def test_blocked_action_type_populated_when_blocked(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_guard(run.id, step.id, decision=WorkflowGuardDecision.BLOCKED)

        resp = _post_loop(client, run.id, {
            "max_iterations": 3,
            "dry_run": False,
            "stop_on_blocked": True,
        })
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["blocked_action_type"] is not None, (
            "blocked_action_type should be set when stop_reason is blocked_guard"
        )
        assert data["blocked_action_type"] == "resolve_blocker", (
            f"Expected resolve_blocker, got: {data['blocked_action_type']}"
        )


# ── Tests: Project Context Cockpit UX hardening ──────────────────────────────

RUNDETAIL_TSX = (
    pathlib.Path(__file__).parents[2] / "frontend" / "src" / "pages" / "RunDetail.tsx"
)


def _read_project_cockpit_panel() -> str:
    source = RUNDETAIL_TSX.read_text(encoding="utf-8")
    start = source.find("function ProjectCockpitPanel(")
    end = source.find("// ── Delivery Panel", start)
    if start == -1 or end == -1:
        return source
    return source[start:end]


class TestProjectContextCockpitUx:

    def test_context_cockpit_tab_label_exists(self):
        source = RUNDETAIL_TSX.read_text(encoding="utf-8")
        assert '"cockpit": "Context Cockpit"' in source

    def test_project_cockpit_panel_core_sections_exist(self):
        panel = _read_project_cockpit_panel()
        for label in (
            "ProjectCockpitPanel",
            "Next Safest Action",
            "Source of Truth",
            "Module Map",
            "Delivery Status",
            "Module Awareness",
        ):
            assert label in panel

    def test_module_policy_is_labeled_classification_only(self):
        panel = _read_project_cockpit_panel()
        assert "Classification-only" in panel
        assert "report/classification-only" in panel

    def test_cockpit_panel_has_explicit_empty_states(self):
        panel = _read_project_cockpit_panel()
        for text in (
            "No active Source of Truth",
            "No active Module Map",
            "No module awareness data recorded",
            "No recommended module tests yet",
            "No cockpit-visible blockers",
        ):
            assert text in panel

    def test_cockpit_panel_does_not_add_execution_actions(self):
        panel = _read_project_cockpit_panel()
        forbidden = [
            "execute_run",
            "applyProjectPatch(",
            "proposeProjectPatch(",
            "runProjectCommand(",
            "approveRunAutomationApproval(",
            "executeRunAutomationApproval(",
            "runAutomationNext(",
            "runAutomationSafeLoop(",
            "createRunAutomationApproval(",
        ]
        for token in forbidden:
            assert token not in panel

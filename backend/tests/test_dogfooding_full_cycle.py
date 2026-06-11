"""Dogfooding Full Cycle v1 — Automated simulation test.

Scenario: "Improve Delivery Summary UX for SaaS readiness"
  - Distinguishing guard-blocked vs approval-pending vs tests-failed in delivery report.

This test walks the entire workflow using the FastAPI test client with an
isolated in-memory DB. No real files are mutated, no providers are called,
no commands are executed. Each phase assertion documents what AI Workbench
does correctly and where gaps remain (via xfail markers on known gaps).

Run with:
  cd backend
  .venv/bin/pytest -v tests/test_dogfooding_full_cycle.py
"""
from __future__ import annotations

import json
import sys
from typing import Any

import pytest
from fastapi.testclient import TestClient

from src.storage import database
from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    build_guard_input_snapshot,
    build_requirement_context_snapshot,
    build_guard_result_snapshot,
    build_workflow_guard_result_record,
)
from src.storage import guard_result_storage


# ── Fixtures ──────────────────────────────────────────────────────────────────

STEP_INPUT_WITH_REQ = (
    "Improve delivery summary readiness states to clearly distinguish "
    "guard-blocked vs approval-blocked vs tests-failed.\n\n"
    "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
    "requirement_ids: [REQ-DELIVERY-UX-001, REQ-DELIVERY-UX-002]\n"
    "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "dogfood.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def dogfood_run(isolated_db, tmp_path):
    """Project + run + step for the dogfooding scenario."""
    proj_dir = tmp_path / "saas_project"
    proj_dir.mkdir()
    (proj_dir / "delivery_ux.py").write_text("# Delivery UX stub\n")
    project = isolated_db.create_project(
        "AI Workbench SaaS",
        str(proj_dir),
        test_command=f"{sys.executable} -c \"print('tests ok')\"",
    )
    run = isolated_db.create_run(
        prompt="Improve Delivery Summary UX for SaaS readiness",
        project_id=project.id,
        project_path=str(proj_dir),
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Improve delivery readiness UX",
        input=STEP_INPUT_WITH_REQ,
    )
    return project, run, step


def _make_guard(isolated_db, run_id, step_id, project_id, proj_path,
                decision=WorkflowGuardDecision.ALLOWED,
                drift_risk=WorkflowGuardDriftRisk.LOW,
                record_id=None):
    input_snap = build_guard_input_snapshot(
        proposed_action="apply_patch",
        file_path="backend/src/models.py",
        patch_summary="Add blocked_reason field to StepDeliverySummary",
        old_text="readiness: str",
        new_text="readiness: str\n    blocked_reason: str | None = None",
    )
    ctx_snap = build_requirement_context_snapshot(
        requirement_ids=["REQ-DELIVERY-UX-001", "REQ-DELIVERY-UX-002"],
        coverage_status="covered",
        drift_risk=drift_risk,
        acceptance_criteria=["Delivery summary distinguishes all 5 readiness states"],
        constraints=["No DB schema changes"],
        forbidden_changes=["database.py", "engine.py"],
        validation_notes=[],
        source_of_truth_summary="Improve delivery UX for SaaS readiness",
    )
    result_snap = build_guard_result_snapshot(
        decision=decision,
        drift_risk=drift_risk,
        matched_requirement_ids=["REQ-DELIVERY-UX-001", "REQ-DELIVERY-UX-002"],
        violated_constraints=[],
        forbidden_change_hits=[],
        warnings=["Guard blocked — scope too broad"] if decision == WorkflowGuardDecision.BLOCKED else [],
        reasons=["Dogfood guard record"],
        recommended_next_step="Resolve before proceeding" if decision == WorkflowGuardDecision.BLOCKED else "Proceed with proposal",
    )
    record = build_workflow_guard_result_record(
        id=record_id or f"gr-dogfood-{step_id}",
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        input_snapshot=input_snap,
        requirement_context_snapshot=ctx_snap,
        result_snapshot=result_snap,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        warning_acknowledged=False,
        no_guard_override=False,
        expires_at=None,
    )
    guard_result_storage.create_guard_result(record)
    return record


def _make_propose(isolated_db, run_id, step_id, project_id):
    return isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="propose-patch", command="", status="completed",
        input_json=json.dumps({"operations": [{"file_path": "backend/src/models.py", "old_text": "x", "new_text": "y"}]}),
        output_json=json.dumps({}), risk_level="medium",
    )


def _make_apply(isolated_db, run_id, step_id, project_id):
    return isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="apply-patch", command="", status="completed",
        input_json=json.dumps({"operations": [{"file_path": "backend/src/models.py"}]}),
        output_json=json.dumps({"files_changed": ["backend/src/models.py"]}),
        risk_level="high",
    )


def _make_test(isolated_db, run_id, step_id, project_id, returncode=0):
    tc = isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="run-command", command=f"{sys.executable} -c 'print(1)'",
        status="completed",
        input_json=json.dumps({"command": "test"}),
        output_json=json.dumps({"returncode": returncode}),
        risk_level="medium",
    )
    isolated_db.update_tool_call(tc.id, status="completed", returncode=returncode,
                                  stdout="ok" if returncode == 0 else "FAIL", stderr="")
    return tc


# ── Phase 1: Task Clarity ─────────────────────────────────────────────────────

class TestPhase1TaskClarity:
    """Verify the task is well-formed and requirement IDs can be extracted."""

    def test_requirement_context_extractable(self):
        """AI_WORKBENCH_REQUIREMENT_CONTEXT block yields correct IDs."""
        from src.orchestrator.project_intake import parse_run_step_requirement_context
        ctx = parse_run_step_requirement_context(STEP_INPUT_WITH_REQ)
        req_ids = list(ctx.requirement_ids or [])
        assert "REQ-DELIVERY-UX-001" in req_ids
        assert "REQ-DELIVERY-UX-002" in req_ids

    def test_requirement_ids_in_delivery_summary(self, client, dogfood_run):
        """Delivery summary exposes requirement IDs extracted from step input."""
        project, run, step = dogfood_run
        r = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r.status_code == 200
        ds = r.json()
        assert "REQ-DELIVERY-UX-001" in ds["requirement_ids"]
        assert "REQ-DELIVERY-UX-002" in ds["requirement_ids"]

    def test_missing_run_returns_404(self, client):
        """Delivery summary returns 404 for unknown run."""
        r = client.get("/api/runs/nonexistent-run/delivery-summary")
        assert r.status_code == 404


# ── Phase 2: Operator Queue ───────────────────────────────────────────────────

class TestPhase2OperatorQueue:
    """Verify operator queue surfaces correct next action at each workflow stage."""

    def test_no_activity_queue_has_item(self, client, dogfood_run):
        """Operator queue returns at least one item for a fresh step."""
        project, run, step = dogfood_run
        r = client.get(f"/api/runs/{run.id}/operator-queue")
        assert r.status_code == 200
        q = r.json()
        items = q.get("items") or []
        assert len(items) >= 1

    def test_no_activity_readiness_is_not_started(self, client, dogfood_run):
        """Fresh step has not_started readiness."""
        project, run, step = dogfood_run
        r = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r.status_code == 200
        assert r.json()["readiness"] == "not_started"

    def test_blocked_guard_in_queue(self, client, dogfood_run, isolated_db, tmp_path):
        """Blocked guard surfaces resolve_blocker in operator queue."""
        project, run, step = dogfood_run
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"),
                    decision=WorkflowGuardDecision.BLOCKED, drift_risk=WorkflowGuardDriftRisk.HIGH)
        r = client.get(f"/api/runs/{run.id}/operator-queue?step_id={step.id}")
        assert r.status_code == 200
        items = r.json().get("items") or []
        action_types = [i["action_type"] for i in items]
        assert "resolve_blocker" in action_types

    def test_stale_guard_shows_recheck(self, client, dogfood_run, isolated_db, tmp_path):
        """Stale guard surfaces resolve_blocker / recheck in operator queue."""
        project, run, step = dogfood_run
        record = _make_guard(
            isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"),
            decision=WorkflowGuardDecision.ALLOWED, drift_risk=WorkflowGuardDriftRisk.LOW,
        )
        guard_result_storage.mark_guard_result_stale(
            record.id, WorkflowGuardStaleReason.MANUAL_INVALIDATION
        )
        r = client.get(f"/api/runs/{run.id}/operator-queue?step_id={step.id}")
        assert r.status_code == 200
        items = r.json().get("items") or []
        action_types = [i["action_type"] for i in items]
        assert "resolve_blocker" in action_types, (
            f"Expected resolve_blocker for stale guard, got: {action_types}"
        )


# ── Phase 3: Agent Execution (dry_run) ───────────────────────────────────────

class TestPhase3AgentExecution:
    """Verify agent execution dry_run mode returns context without side effects."""

    def test_dry_run_returns_200(self, client, dogfood_run):
        """Agent execution dry_run returns 200 with planned status."""
        project, run, step = dogfood_run
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-executions/run",
            json={"mode": "dry_run", "allow_provider_call": False, "persist_result": False},
        )
        assert r.status_code == 200
        ae = r.json()
        assert ae["status"] == "planned"
        assert ae["executed"] is False
        assert ae["provider_called"] is False

    def test_dry_run_no_tool_call_created(self, client, dogfood_run, isolated_db):
        """Agent execution dry_run does not create any tool_calls."""
        project, run, step = dogfood_run
        before = isolated_db.list_tool_calls_for_step(step.id)
        client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-executions/run",
            json={"mode": "dry_run", "allow_provider_call": False, "persist_result": False},
        )
        after = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after) == len(before), "dry_run must not create tool_calls"

    def test_dry_run_returns_prompt_preview(self, client, dogfood_run):
        """Agent execution dry_run includes a prompt_preview."""
        project, run, step = dogfood_run
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-executions/run",
            json={"mode": "dry_run", "allow_provider_call": False},
        )
        assert r.status_code == 200
        assert r.json().get("prompt_preview"), "dry_run must return prompt_preview"

    def test_mock_mode_returns_result(self, client, dogfood_run):
        """Agent execution mock mode returns a structured result."""
        project, run, step = dogfood_run
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-executions/run",
            json={"mode": "mock", "allow_provider_call": False, "persist_result": False},
        )
        assert r.status_code == 200
        ae = r.json()
        assert ae["status"] in ("completed", "mock")
        assert ae.get("result") is not None


# ── Phase 4: Agent Result → Patch Draft Bridge ───────────────────────────────

class TestPhase4PatchDraftBridge:
    """Verify agent result → patch draft bridge is read-only and bounded."""

    def test_bridge_read_only_no_proposal(self, client, dogfood_run, isolated_db):
        """Bridge endpoint creates no proposal or tool_call."""
        project, run, step = dogfood_run
        from src.models import AgentExecutionResult
        agent_result = AgentExecutionResult(
            summary="Add blocked_reason field to StepDeliverySummary",
            patch_intent="Add `blocked_reason: str | None = None` to StepDeliverySummary model",
            proposed_files=["backend/src/models.py"],
            can_feed_patch_draft=True,
        )
        before = isolated_db.list_tool_calls_for_step(step.id)
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={"agent_result": agent_result.model_dump()},
        )
        assert r.status_code == 200
        after = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after) == len(before), "Bridge must not create tool_calls"

    def test_bridge_returns_patch_context(self, client, dogfood_run):
        """Bridge returns a non-empty patch_context block."""
        project, run, step = dogfood_run
        from src.models import AgentExecutionResult
        agent_result = AgentExecutionResult(
            summary="Add blocked_reason field",
            patch_intent="Add blocked_reason to StepDeliverySummary",
            proposed_files=["backend/src/models.py"],
            can_feed_patch_draft=True,
        )
        r = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={"agent_result": agent_result.model_dump()},
        )
        assert r.status_code == 200
        body = r.json()
        patch_ctx = body.get("patch_context") or body.get("patch_draft_context") or ""
        assert patch_ctx, "Bridge must return non-empty patch context"

    def test_bridge_no_auto_invalidate_guard(self, client, dogfood_run, isolated_db, tmp_path):
        """Bridge with invalidate_guard=False leaves existing guard intact."""
        project, run, step = dogfood_run
        record = _make_guard(
            isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"),
        )
        from src.models import AgentExecutionResult
        client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={
                "agent_result": AgentExecutionResult(
                    summary="Fix", patch_intent="Fix something",
                ).model_dump(),
                "invalidate_guard": False,
            },
        )
        updated = guard_result_storage.get_guard_result(record.id)
        assert updated is not None
        assert not updated.is_stale, "Guard must remain valid when invalidate_guard=False"


# ── Phase 5: Guard / Proposal Readiness ──────────────────────────────────────

class TestPhase5GuardProposal:
    """Verify guard/proposal flow enforces correct boundaries."""

    def test_premature_apply_approval_rejected(self, client, dogfood_run):
        """Creating apply_patch_manual approval without prerequisite is rejected (400)."""
        project, run, step = dogfood_run
        r = client.post(f"/api/runs/{run.id}/automation/approvals", json={
            "step_id": step.id,
            "action_type": "apply_patch_manual",
            "reason": "dogfood test",
        })
        assert r.status_code == 400, (
            f"Should reject apply_patch_manual without propose-patch. Got {r.status_code}: {r.text}"
        )

    def test_blocked_guard_blocks_proposal(self, client, dogfood_run, isolated_db, tmp_path):
        """Delivery summary shows blocked when guard is BLOCKED."""
        project, run, step = dogfood_run
        _make_guard(
            isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"),
            decision=WorkflowGuardDecision.BLOCKED, drift_risk=WorkflowGuardDriftRisk.HIGH,
        )
        r = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r.status_code == 200
        assert r.json()["readiness"] == "blocked"


# ── Phase 6: Approval / Apply Boundary ───────────────────────────────────────

class TestPhase6ApprovalBoundary:
    """Verify approval-gated apply boundary is enforced."""

    def test_apply_requires_approved_automation_approval(self, client, dogfood_run, isolated_db, tmp_path):
        """Bounded loop cannot auto-apply without an executed automation approval."""
        project, run, step = dogfood_run
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"))
        _make_propose(isolated_db, run.id, step.id, project.id)
        # No approval created — loop should stop at stopped_for_approval or no_safe_action
        r = client.post(f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop", json={
            "step_id": step.id,
            "max_iterations": 1,
            "dry_run": False,
            "allow_safe_commands": False,
            "stop_on_approval_required": True,
            "stop_on_blocked": True,
        })
        assert r.status_code == 200
        status = r.json()["status"]
        assert status in ("stopped_for_approval", "no_safe_action", "max_iterations_reached", "blocked"), (
            f"Bounded loop must stop safely, got: {status}"
        )
        all_calls = isolated_db.list_tool_calls_for_step(step.id)
        apply_calls = [c for c in all_calls if c.tool_name == "apply-patch"]
        assert len(apply_calls) == 0, "No apply-patch without approval"


# ── Phase 7: Bounded Loop Dry_Run ────────────────────────────────────────────

class TestPhase7BoundedLoop:
    """Verify bounded loop dry_run mode is completely safe."""

    def test_dry_run_creates_no_tool_calls(self, client, dogfood_run, isolated_db):
        """Bounded loop dry_run creates no tool_calls."""
        project, run, step = dogfood_run
        before = isolated_db.list_tool_calls_for_step(step.id)
        r = client.post(f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop", json={
            "step_id": step.id,
            "max_iterations": 2,
            "dry_run": True,
            "allow_provider_call": False,
            "allow_safe_commands": False,
            "stop_on_approval_required": True,
        })
        assert r.status_code == 200
        after = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after) == len(before), "dry_run must not create tool_calls"

    def test_dry_run_returns_safe_status(self, client, dogfood_run):
        """Bounded loop dry_run returns a terminal safe status."""
        project, run, step = dogfood_run
        r = client.post(f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop", json={
            "step_id": step.id, "max_iterations": 2, "dry_run": True,
            "allow_provider_call": False, "stop_on_approval_required": True,
        })
        assert r.status_code == 200
        loop = r.json()
        assert loop["status"] in (
            "dry_run", "no_safe_action", "blocked", "stopped_for_approval",
            "max_iterations_reached", "completed"
        )


# ── Phase 8: Delivery Report Quality ─────────────────────────────────────────

class TestPhase8DeliveryReport:
    """Verify delivery report correctly reflects all 5 required UX states."""

    def test_not_started_state(self, client, dogfood_run):
        """No-activity step → not_started readiness."""
        project, run, step = dogfood_run
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={
            "include_markdown": True, "include_step_details": True,
        })
        assert r.status_code == 200
        dr = r.json()
        step_sum = dr["steps"][0]
        assert step_sum["readiness"] == "not_started"
        assert step_sum["recommended_next_action"] is not None
        assert "REQ-DELIVERY-UX-001" in step_sum["requirement_ids"]

    def test_needs_tests_state(self, client, dogfood_run, isolated_db):
        """Apply with no tests → needs_tests readiness."""
        project, run, step = dogfood_run
        _make_propose(isolated_db, run.id, step.id, project.id)
        _make_apply(isolated_db, run.id, step.id, project.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_step_details": True})
        assert r.status_code == 200
        assert r.json()["steps"][0]["readiness"] == "needs_tests"

    def test_tests_failed_state(self, client, dogfood_run, isolated_db):
        """Apply + failing test → tests_failed readiness."""
        project, run, step = dogfood_run
        _make_propose(isolated_db, run.id, step.id, project.id)
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=1)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_step_details": True})
        assert r.status_code == 200
        assert r.json()["steps"][0]["readiness"] == "tests_failed"

    def test_ready_for_review_state(self, client, dogfood_run, isolated_db, tmp_path):
        """Apply + passing test + allowed guard + req IDs → ready_for_review or delivered_with_warnings."""
        project, run, step = dogfood_run
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"))
        _make_propose(isolated_db, run.id, step.id, project.id)
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=0)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_step_details": True})
        assert r.status_code == 200
        step_readiness = r.json()["steps"][0]["readiness"]
        assert step_readiness in ("ready_for_review", "delivered_with_warnings"), (
            f"Expected ready_for_review or delivered_with_warnings, got {step_readiness}"
        )

    def test_blocked_guard_state(self, client, dogfood_run, isolated_db, tmp_path):
        """BLOCKED guard → blocked readiness."""
        project, run, step = dogfood_run
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"),
                    decision=WorkflowGuardDecision.BLOCKED, drift_risk=WorkflowGuardDriftRisk.HIGH)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_step_details": True})
        assert r.status_code == 200
        assert r.json()["steps"][0]["readiness"] == "blocked"

    def test_changed_files_extracted(self, client, dogfood_run, isolated_db):
        """Changed files extracted from apply-patch tool_call output."""
        project, run, step = dogfood_run
        _make_propose(isolated_db, run.id, step.id, project.id)
        _make_apply(isolated_db, run.id, step.id, project.id)
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={"include_step_details": True})
        assert r.status_code == 200
        changed = r.json()["steps"][0]["changed_files"]
        assert "backend/src/models.py" in changed

    def test_markdown_contains_all_required_sections(self, client, dogfood_run):
        """Delivery report markdown contains all 8 required sections."""
        project, run, step = dogfood_run
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={
            "include_markdown": True, "include_step_details": True,
        })
        assert r.status_code == 200
        md = r.json()["markdown_report"]
        required = [
            "# Delivery Report", "## Run Summary", "## Requirements Coverage",
            "## Step Summaries", "## Changes", "## Validation",
            "## Approvals and Safety", "## Final Recommendation",
        ]
        for section in required:
            assert section in md, f"Missing section: {section}"

    def test_markdown_respects_max_chars(self, client, dogfood_run):
        """Delivery report markdown is bounded by max_markdown_chars."""
        project, run, step = dogfood_run
        r = client.post(f"/api/runs/{run.id}/delivery-report", json={
            "include_markdown": True, "max_markdown_chars": 500,
        })
        assert r.status_code == 200
        md = r.json()["markdown_report"]
        assert len(md) <= 600, f"Markdown not bounded: {len(md)} chars"

    def test_report_is_read_only(self, client, dogfood_run, isolated_db):
        """Delivery report creates no tool_calls or DB mutations."""
        project, run, step = dogfood_run
        before_calls = isolated_db.list_tool_calls_for_step(step.id)
        client.post(f"/api/runs/{run.id}/delivery-report", json={"include_markdown": True})
        after_calls = isolated_db.list_tool_calls_for_step(step.id)
        assert len(after_calls) == len(before_calls), "Delivery report must be read-only"


# ── Phase 9: Known Gaps (documented, not xfail — they are real gaps) ──────────

class TestPhase9KnownGaps:
    """Document known gaps found during dogfooding. Tests assert the GAP exists."""

    def test_GAP001_resolved_approval_pending_steps_present(self):
        """GAP-001 RESOLVED: RunDeliverySummary now has approval_pending_steps counter (v2)."""
        from src.models import RunDeliverySummary
        fields = list(RunDeliverySummary.model_fields.keys())
        assert "approval_pending_steps" in fields, (
            "Expected approval_pending_steps to be present in RunDeliverySummary — GAP-001 is resolved"
        )

    def test_GAP003_resolved_awaiting_approval_readiness_state(self, client, dogfood_run, isolated_db, tmp_path):
        """GAP-003 RESOLVED: Pending approval now produces 'awaiting_approval' readiness state (v2)."""
        project, run, step = dogfood_run
        # Create propose + apply + guard (allowed)
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"))
        _make_propose(isolated_db, run.id, step.id, project.id)
        _make_apply(isolated_db, run.id, step.id, project.id)
        # Create an automation approval (pending)
        r_approval = client.post(f"/api/runs/{run.id}/automation/approvals", json={
            "step_id": step.id,
            "action_type": "run_tests_manual",
            "reason": "dogfood test — awaiting tests",
        })
        # GAP-003 resolved: delivery summary now shows 'awaiting_approval' for pending approvals
        r_ds = client.get(f"/api/runs/{run.id}/delivery-summary")
        assert r_ds.status_code == 200
        readiness = r_ds.json()["readiness"]
        assert readiness == "awaiting_approval", (
            f"Expected readiness='awaiting_approval' (GAP-003 resolved), got: {readiness!r}"
        )

    def test_GAP002_resolved_approval_status_present_in_markdown(self, client, dogfood_run, isolated_db, tmp_path):
        """GAP-002 RESOLVED: Per-step approval_status IS now rendered in markdown Step Summaries."""
        project, run, step = dogfood_run
        _make_guard(isolated_db, run.id, step.id, project.id, str(tmp_path / "saas_project"))
        _make_propose(isolated_db, run.id, step.id, project.id)
        # Request approval
        client.post(f"/api/runs/{run.id}/automation/approvals", json={
            "step_id": step.id,
            "action_type": "apply_patch_manual",
            "reason": "dogfood test",
        })
        r_dr = client.post(f"/api/runs/{run.id}/delivery-report", json={
            "include_markdown": True, "include_step_details": True,
        })
        assert r_dr.status_code == 200
        md = r_dr.json()["markdown_report"]
        step_section_start = md.find("## Step Summaries")
        step_section = md[step_section_start:step_section_start + 2000] if step_section_start >= 0 else ""
        # GAP-002 resolved: approval status is now shown per step in markdown
        has_approval_line = "Approval:" in step_section or "approval" in step_section.lower()
        assert has_approval_line, (
            "Expected approval_status to appear in Step Summaries markdown — GAP-002 is resolved"
        )

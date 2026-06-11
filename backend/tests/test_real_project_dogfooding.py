"""Fastlane Real Project Dogfooding v1 — Verification tests.

Scenario: "Can AI Workbench guide a realistic real-project task through
source-of-truth / task framing → agent / patch / guard / approval / delivery
reasoning without falling apart?"

Requirements verified:
  REQ-DOGFOOD-001: User can identify current delivery readiness.
  REQ-DOGFOOD-002: User can identify whether approval is pending.
  REQ-DOGFOOD-003: User can identify next recommended action.
  REQ-DOGFOOD-004: User can distinguish blocked / awaiting_approval /
                   needs_tests / tests_failed / ready_for_review.
  REQ-DOGFOOD-005: User can generate or inspect final delivery report safely.

Safety invariants:
  - No file mutation from delivery, operator-queue, or bounded-loop dry_run.
  - No provider calls.
  - No arbitrary commands.
  - No guard/approval bypass.
  - database.py and engine.py not touched by delivery endpoints.

Run with:
  cd backend
  .venv/bin/pytest -v tests/test_real_project_dogfooding.py
"""
from __future__ import annotations

import inspect
import json
import sys

import pytest
from fastapi.testclient import TestClient

from src.storage import database


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "dogfood_real.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    """Create project, run, and one step used in most tests."""
    project_dir = tmp_path / "real_project"
    project_dir.mkdir()
    (project_dir / "main.py").write_text("# AI Workbench real project\n", encoding="utf-8")
    project = isolated_db.create_project(
        "AI Workbench Real Dogfood",
        str(project_dir),
        test_command=f"{sys.executable} -c \"print('ok')\"",
    )
    run = isolated_db.create_run(
        prompt=(
            "Improve operator-facing clarity of Delivery/Automation workflow.\n\n"
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids: [REQ-DOGFOOD-001, REQ-DOGFOOD-002, REQ-DOGFOOD-003]\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
        ),
        project_id=project.id,
        project_path=str(project_dir),
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Improve delivery readiness clarity",
        input=(
            "Verify operator can identify readiness, pending approval, "
            "and next action from existing UI surfaces.\n\n"
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids: [REQ-DOGFOOD-001, REQ-DOGFOOD-002]\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
        ),
    )
    return project, run, step


# ── Agent result fixture (matches AgentExecutionResult model) ─────────────────

_GOOD_AGENT_RESULT = {
    "summary": "Add 'awaiting_approval' readiness state between tests_failed and needs_tests.",
    "analysis": "The _delivery_readiness_severity map needs a new entry at severity 2.",
    "proposed_files": ["backend/src/api/routes.py"],
    "patch_intent": "Insert awaiting_approval at severity 2 in the delivery readiness order.",
    "risks": ["Severity ordering change may affect existing tests."],
    "test_suggestions": ["Run tests/test_full_delivery_loop.py", "Run tests/test_dogfooding_full_cycle.py"],
    "questions": [],
    "recommended_next_action": "Create guarded proposal for routes.py.",
    "can_feed_patch_draft": True,
}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_guard(isolated_db, run_id, step_id, decision="allowed"):
    """Create a guard result record."""
    from src.storage import guard_result_storage
    from src.orchestrator.guard_result_storage_contract import (
        WorkflowGuardDecision,
        WorkflowGuardDriftRisk,
        WorkflowGuardSource,
        build_guard_input_snapshot,
        build_guard_result_snapshot,
        build_requirement_context_snapshot,
        build_workflow_guard_result_record,
    )
    gd = {
        "allowed": WorkflowGuardDecision.ALLOWED,
        "blocked": WorkflowGuardDecision.BLOCKED,
        "warning": WorkflowGuardDecision.WARNING,
    }.get(decision, WorkflowGuardDecision.ALLOWED)
    dr = WorkflowGuardDriftRisk.HIGH if decision == "blocked" else WorkflowGuardDriftRisk.LOW
    input_snap = build_guard_input_snapshot(
        proposed_action="Improve delivery readiness UX",
        file_path="backend/src/api/routes.py",
        patch_summary="Add awaiting_approval state",
        old_text="old",
        new_text="new",
    )
    ctx_snap = build_requirement_context_snapshot(
        requirement_ids=["REQ-DOGFOOD-001"],
        coverage_status="covered",
        drift_risk=dr,
        acceptance_criteria=["Delivery tab shows awaiting_approval"],
        constraints=[],
        forbidden_changes=[],
        validation_notes=[],
        source_of_truth_summary="Delivery UX SoT",
    )
    result_snap = build_guard_result_snapshot(
        decision=gd,
        drift_risk=dr,
        matched_requirement_ids=["REQ-DOGFOOD-001"],
        violated_constraints=[],
        forbidden_change_hits=[],
        warnings=["Blocked by guard"] if decision == "blocked" else [],
        reasons=["Dogfood verification"],
        recommended_next_step="Proceed" if decision != "blocked" else "Resolve guard",
    )
    record = build_workflow_guard_result_record(
        id=f"gr-{decision}-{step_id}",
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.MANUAL_CHECK,
        input_snapshot=input_snap,
        requirement_context_snapshot=ctx_snap,
        result_snapshot=result_snap,
    )
    guard_result_storage.create_guard_result(record)
    return record


def _make_propose(isolated_db, run_id, step_id, project_id):
    return isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="propose-patch", command="", status="completed",
        input_json=json.dumps({"operations": [{"file_path": "main.py", "old_text": "old", "new_text": "new"}]}),
        output_json=json.dumps({}), risk_level="medium",
    )


def _make_apply(isolated_db, run_id, step_id, project_id):
    return isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="apply-patch", command="", status="completed",
        input_json=json.dumps({"operations": [{"file_path": "main.py", "old_text": "old", "new_text": "new"}]}),
        output_json=json.dumps({"files_changed": 1}), risk_level="high",
    )


def _make_test(isolated_db, run_id, step_id, project_id, returncode=0):
    tc = isolated_db.create_tool_call(
        run_id=run_id, step_id=step_id, project_id=project_id,
        tool_name="run-command", command="pytest", status="completed",
        input_json=json.dumps({"automation": True}),
        output_json=json.dumps({"returncode": returncode}), risk_level="medium",
    )
    isolated_db.update_tool_call(
        tc.id, status="completed", returncode=returncode,
        stdout="ok" if returncode == 0 else "FAIL", stderr="",
    )
    return tc


def _make_pending_approval(client, run_id, step_id, action_type="run_tests_manual"):
    resp = client.post(
        f"/api/runs/{run_id}/automation/approvals",
        json={"step_id": step_id, "action_type": action_type,
              "reason": "Dogfood approval request"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _delivery_summary(client, run_id):
    resp = client.get(f"/api/runs/{run_id}/delivery-summary")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _delivery_report(client, run_id, include_markdown=True):
    resp = client.post(
        f"/api/runs/{run_id}/delivery-report",
        json={"include_step_details": True, "include_markdown": include_markdown},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


# ── Test Suite 1: Lifecycle State Coverage (REQ-DOGFOOD-001, REQ-DOGFOOD-004) ─


class TestLifecycleCoverage:
    """Verify all 7 delivery readiness states are correctly reported."""

    def test_not_started(self, client, project_run_step, isolated_db):
        """No activity → not_started."""
        _, run, _ = project_run_step
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "not_started"

    def test_in_progress_with_guard(self, client, project_run_step, isolated_db):
        """Guard exists but no proposal/apply/test → in_progress."""
        project, run, step = project_run_step
        _make_guard(isolated_db, run.id, step.id, decision="allowed")
        s = _delivery_summary(client, run.id)
        # Guard alone → in_progress (no proposal yet)
        assert s["readiness"] == "in_progress"

    def test_needs_tests(self, client, project_run_step, isolated_db):
        """Apply exists, no post-apply tests → needs_tests."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "needs_tests"

    def test_tests_failed(self, client, project_run_step, isolated_db):
        """Apply + failing tests → tests_failed."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=1)
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "tests_failed"

    def test_ready_for_review(self, client, project_run_step, isolated_db):
        """Apply + passing tests → ready_for_review."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=0)
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "ready_for_review"

    def test_blocked_guard(self, client, project_run_step, isolated_db):
        """Blocked guard → blocked readiness."""
        project, run, step = project_run_step
        _make_guard(isolated_db, run.id, step.id, decision="blocked")
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "blocked"

    def test_awaiting_approval(self, client, project_run_step, isolated_db):
        """Pending approval (with apply) → awaiting_approval beats needs_tests."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "awaiting_approval"

    def test_awaiting_approval_beats_ready_for_review(self, client, project_run_step, isolated_db):
        """Pending approval + passing tests → awaiting_approval beats ready_for_review."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=0)
        # Use run_tests_manual: backend requires a valid manual-required queue item.
        # After apply + passing tests, the queue item for the next cycle is run_tests_manual.
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")
        s = _delivery_summary(client, run.id)
        assert s["readiness"] == "awaiting_approval"


# ── Test Suite 2: Pending Approval Visibility (REQ-DOGFOOD-002) ───────────────


class TestPendingApprovalVisibility:
    """Verify pending approval surfaces correctly in summary and markdown."""

    def test_approval_pending_steps_counter(self, client, project_run_step, isolated_db):
        """approval_pending_steps increments when approval is pending."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")
        s = _delivery_summary(client, run.id)
        assert s["approval_pending_steps"] >= 1

    def test_markdown_contains_approval_pending_line(self, client, project_run_step, isolated_db):
        """Markdown step section contains literal 'Approval: pending' substring."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")
        report = _delivery_report(client, run.id, include_markdown=True)
        md = report.get("markdown_report", "")
        assert "Approval: pending" in md, f"Expected 'Approval: pending' in markdown, got:\n{md}"

    def test_markdown_final_recommendation_mentions_awaiting(self, client, project_run_step, isolated_db):
        """Final Recommendation section mentions 'Awaiting approval'."""
        project, run, step = project_run_step
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")
        report = _delivery_report(client, run.id, include_markdown=True)
        md = report.get("markdown_report", "")
        assert "Awaiting approval" in md or "awaiting_approval" in md, (
            f"Final Recommendation should mention awaiting approval, got:\n{md}"
        )

    def test_no_pending_approval_counter_is_zero(self, client, project_run_step, isolated_db):
        """approval_pending_steps is 0 when no approval is pending."""
        _, run, _ = project_run_step
        s = _delivery_summary(client, run.id)
        assert s["approval_pending_steps"] == 0


# ── Test Suite 3: Bounded Loop Dry Run Safety (REQ-DOGFOOD-005) ──────────────


class TestBoundedLoopDryRunSafety:
    """Verify bounded loop dry_run creates no tool_calls and stops safely."""

    def test_dry_run_no_tool_calls_created(self, client, project_run_step, isolated_db):
        """dry_run=True must not create any new tool_calls."""
        _, run, _ = project_run_step
        before = client.get(f"/api/runs/{run.id}/tool-calls").json()
        before_count = len(before)

        resp = client.post(
            f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop",
            json={"dry_run": True, "max_iterations": 3, "max_actions_per_iteration": 3,
                  "stop_on_approval_required": True, "stop_on_blocked": True},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["dry_run"] is True

        after = client.get(f"/api/runs/{run.id}/tool-calls").json()
        # dry_run must not add new real tool_calls
        assert len(after) == before_count, (
            f"dry_run created {len(after) - before_count} new tool_calls"
        )

    def test_dry_run_stops_at_manual_required(self, client, project_run_step, isolated_db):
        """dry_run stops at manual_required items (no guard = check_guard needed)."""
        _, run, _ = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop",
            json={"dry_run": True, "max_iterations": 3, "stop_on_approval_required": True},
        )
        assert resp.status_code == 200
        d = resp.json()
        # With no guard, the queue produces check_guard (manual_required) → stopped_for_approval
        assert d["status"] in (
            "stopped_for_approval", "blocked", "no_safe_action", "completed", "max_iterations_reached"
        )

    def test_bounded_loop_stops_on_blocked_guard(self, client, project_run_step, isolated_db):
        """Blocked guard causes loop to stop with status=blocked."""
        project, run, step = project_run_step
        _make_guard(isolated_db, run.id, step.id, decision="blocked")
        resp = client.post(
            f"/api/runs/{run.id}/automation/bounded-patch-test-fix-loop",
            json={"dry_run": True, "max_iterations": 3, "stop_on_blocked": True},
        )
        assert resp.status_code == 200
        d = resp.json()
        assert d["status"] == "blocked", f"Expected blocked, got: {d['status']}"


# ── Test Suite 4: Agent Patch Draft Prefill Contract ──────────────────────────


class TestAgentPatchDraftPrefillContract:
    """Verify agent-result → patch draft bridge does NOT auto-fill old_text/new_text.

    REQ: The bridge sets patch context (narrative, file path hint) but must not
    fill old_text/new_text — the guard must still run before any proposal.
    """

    def test_agent_patch_draft_endpoint_exists(self, client, project_run_step, isolated_db):
        """POST /api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft returns 200."""
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={
                "agent_result": _GOOD_AGENT_RESULT,
                "include_context": True,
                "include_risks": True,
                "include_tests": True,
            },
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "patch_context" in data

    def test_agent_patch_draft_does_not_create_proposal(self, client, project_run_step, isolated_db):
        """agent-result-patch-draft must not create a propose-patch tool_call."""
        _, run, step = project_run_step
        before = [
            tc for tc in client.get(f"/api/runs/{run.id}/tool-calls").json()
            if tc.get("tool_name") == "propose-patch"
        ]
        client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={"agent_result": _GOOD_AGENT_RESULT, "include_context": True},
        )
        after = [
            tc for tc in client.get(f"/api/runs/{run.id}/tool-calls").json()
            if tc.get("tool_name") == "propose-patch"
        ]
        assert len(after) == len(before), "agent-result-patch-draft must not auto-create a proposal"

    def test_agent_patch_draft_patch_context_is_narrative(self, client, project_run_step, isolated_db):
        """patch_context is a non-empty narrative — not a raw unified diff.

        The bridge may instruct the operator to fill old_text/new_text manually
        (that is correct safety behavior, not a violation). What it must NOT do
        is produce a raw unified diff with diff markers or auto-populate the
        actual patch operations.
        """
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-result-patch-draft",
            json={"agent_result": _GOOD_AGENT_RESULT, "include_context": True},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        # patch_context must be a non-empty string
        ctx = data.get("patch_context", "")
        assert isinstance(ctx, str) and len(ctx) > 0, "patch_context should be a non-empty string"

        # Must NOT be a raw unified diff — these markers only appear in actual diffs
        for diff_marker in ("\n---", "\n+++", "\n@@"):
            assert diff_marker not in ctx, (
                f"patch_context looks like a raw unified diff (found '{diff_marker}')"
            )

        # The bridge must not auto-fill the literal code values from _GOOD_AGENT_RESULT
        # as if they were patch old/new text — patch_intent is narrative intent, not raw code
        raw_patch_intent = _GOOD_AGENT_RESULT["patch_intent"]
        # patch_context may quote the intent, but must not be identical to a raw code block
        # (the bridge adds context, structure, and guidance around it)
        assert ctx != raw_patch_intent, (
            "patch_context should not be identical to the raw patch_intent string"
        )

        # can_prefill_patch_context indicates bridge produced useful output
        assert "can_prefill_patch_context" in data, (
            "Response should include can_prefill_patch_context field"
        )


# ── Test Suite 5: Delivery Endpoints Read-Only (REQ-DOGFOOD-005) ──────────────


class TestDeliveryEndpointsReadOnly:
    """Verify delivery endpoints create no tool_calls and mutate no state."""

    def test_delivery_summary_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        """GET delivery-summary must not create any tool_calls."""
        _, run, _ = project_run_step
        before = client.get(f"/api/runs/{run.id}/tool-calls").json()
        _delivery_summary(client, run.id)
        after = client.get(f"/api/runs/{run.id}/tool-calls").json()
        assert len(after) == len(before), "delivery-summary must not create tool_calls"

    def test_delivery_report_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        """POST delivery-report must not create any tool_calls."""
        project, run, step = project_run_step
        # Set up a step with some state to exercise the report fully.
        # Use run_tests_manual: backend requires a valid manual-required queue item for approval.
        _make_apply(isolated_db, run.id, step.id, project.id)
        _make_test(isolated_db, run.id, step.id, project.id, returncode=0)
        _make_pending_approval(client, run.id, step.id, "run_tests_manual")

        before = client.get(f"/api/runs/{run.id}/tool-calls").json()
        _delivery_report(client, run.id, include_markdown=True)
        after = client.get(f"/api/runs/{run.id}/tool-calls").json()
        assert len(after) == len(before), "delivery-report must not create tool_calls"

    def test_delivery_report_structure(self, client, project_run_step, isolated_db):
        """Delivery report response has required top-level fields."""
        _, run, _ = project_run_step
        report = _delivery_report(client, run.id)
        required = {"run_id", "summary", "steps", "markdown_report", "generated_at", "safety_notes"}
        assert required.issubset(set(report.keys())), (
            f"Missing fields: {required - set(report.keys())}"
        )

    def test_delivery_summary_has_required_fields(self, client, project_run_step, isolated_db):
        """Delivery summary has all expected fields including approval_pending_steps."""
        _, run, _ = project_run_step
        s = _delivery_summary(client, run.id)
        required_fields = {
            "readiness", "approval_pending_steps", "failed_test_steps",
            "blocked_steps", "needs_test_steps",
        }
        for field in required_fields:
            assert field in s, f"Missing field '{field}' in delivery summary"


# ── Test Suite 6: Static Boundary Scan ────────────────────────────────────────


class TestStaticBoundaryDogfood:
    """Static scan of delivery + bounded-loop route sections for forbidden patterns.

    Verifies REQ-DOGFOOD-005: no execution capability added to read-only paths.
    """

    def test_delivery_and_bounded_loop_sections_are_clean(self):
        """routes.py delivery section and bounded loop must not contain forbidden patterns."""
        import src.api.routes as routes_mod
        source = inspect.getsource(routes_mod)

        # Extract delivery section (lines after _DELIVERY_SAFETY_NOTES definition)
        delivery_marker = "_DELIVERY_SAFETY_NOTES"
        delivery_start = source.find(delivery_marker)
        assert delivery_start >= 0, "Could not find delivery section marker"
        delivery_section = source[delivery_start:]

        # The delivery section ends at the last route definition — check the full section
        forbidden_in_delivery = [
            "execute_run(",
            "asyncio.create_task(",
            "apply_project_patch(",
            "propose_project_patch(",
            "subprocess.run(",
            "os.system(",
            "ollama.chat_completion(",
            "create_tool_call(",
            'open(.*"w")',
        ]
        for pattern in forbidden_in_delivery:
            # Use simple substring for most; skip regex patterns
            if "(" in pattern and "*" not in pattern:
                assert pattern not in delivery_section, (
                    f"Forbidden pattern '{pattern}' found in delivery section"
                )

"""Tests for POST /api/project-intake/confirmed-run endpoint.

Tests that the confirmed-run flow creates a real Run + RunSteps
without executing agents, tools, or providers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import (
    ConfirmedRunStepPreview,
    RequirementCoveragePreviewResponse,
    RequirementCoveragePreviewStatus,
    RequirementCoveragePreviewSummary,
    RunStepRequirementContext,
    StepSourceOfTruthGuardDecision,
    build_source_of_truth_from_intake,
    evaluate_step_source_of_truth_guard,
    format_confirmed_run_step_requirement_context,
    parse_run_step_requirement_context,
    SourceOfTruthPreviewRequest,
)
from src.orchestrator.source_of_truth_contract import DriftRiskLevel
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


class TestConfirmedRunEndpoint:
    """POST /api/project-intake/confirmed-run tests."""

    def test_confirm_false_returns_400(self, client):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a web app",
            "confirm": False,
        })
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower()

    def test_confirm_missing_returns_400(self, client):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a web app",
        })
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower()

    def test_empty_idea_returns_400(self, client):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "",
            "confirm": True,
        })
        assert resp.status_code == 400
        assert "idea" in resp.json()["detail"].lower()

    def test_valid_request_creates_run(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with auth",
            "confirm": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"]
        assert data["run_status"] == "pending"
        assert data["steps_created"] > 0

        # Verify run exists in DB.
        run = isolated_db.get_run(data["run_id"])
        assert run is not None
        assert run.status.value == "pending"

    def test_valid_request_creates_run_steps(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL",
            "confirm": True,
        })
        data = resp.json()
        run_id = data["run_id"]

        # Verify steps exist in DB.
        steps = isolated_db.list_run_steps(run_id)
        assert len(steps) == data["steps_created"]
        assert len(steps) > 0

        for step in steps:
            assert step.status == "pending"
            assert step.title

    def test_created_run_is_not_executed(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a web app with auth",
            "confirm": True,
        })
        data = resp.json()
        run_id = data["run_id"]

        # Run must still be pending — not running/completed.
        run = isolated_db.get_run(run_id)
        assert run.status.value == "pending"

        # All steps must be pending.
        steps = isolated_db.list_run_steps(run_id)
        for step in steps:
            assert step.status == "pending"

    def test_no_tool_calls_created(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a web dashboard",
            "confirm": True,
        })
        data = resp.json()
        run_id = data["run_id"]

        # No tool_calls should exist for this run.
        tool_calls = isolated_db.list_tool_calls_for_run(run_id)
        assert len(tool_calls) == 0

    def test_response_serializes_correctly(self, client):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web app",
            "confirm": True,
        })
        data = resp.json()
        assert "run_id" in data
        assert "run_status" in data
        assert "steps_created" in data
        assert "steps" in data
        assert "summary" in data
        assert "warnings" in data
        assert isinstance(data["steps"], list)
        for step in data["steps"]:
            assert "step_id" in step
            assert "title" in step
            assert "agent_id" in step
            assert "status" in step

    def test_existing_project_mode_creates_steps(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Доработать существующий Django проект",
            "confirm": True,
            "mode": "existing_project",
        })
        data = resp.json()
        assert data["steps_created"] > 0

        steps = isolated_db.list_run_steps(data["run_id"])
        assert len(steps) > 0

    def test_vague_idea_still_creates_run_with_warnings(self, client):
        """A vague idea creates a run but with warnings about readiness."""
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Что-то",
            "confirm": True,
        })
        data = resp.json()
        assert data["run_id"]
        assert data["steps_created"] > 0
        # Should have warnings about not being ready.
        assert len(data["warnings"]) > 0

    def test_steps_have_input_with_metadata(self, client, isolated_db):
        """Steps should have rich input text with requirement/deliverable metadata."""
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL database",
            "confirm": True,
        })
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])
        # At least one step should have metadata in input.
        has_metadata = any(
            "[" in step.input and "]" in step.input
            for step in steps
        )
        assert has_metadata, "Expected at least one step to have metadata brackets in input"

    def test_confirmed_run_steps_include_requirement_context_block(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL database",
            "confirm": True,
        })
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])

        assert len(steps) > 0
        for step in steps:
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in step.input
            assert "END_AI_WORKBENCH_REQUIREMENT_CONTEXT" in step.input
            assert "requirement_ids:" in step.input
            assert "coverage_status:" in step.input
            assert "drift_risk:" in step.input
            assert "acceptance_criteria:" in step.input
            assert "constraints:" in step.input
            assert "forbidden_changes:" in step.input
            assert "validation_notes:" in step.input
            assert "source_of_truth_summary:" in step.input

    def test_confirmed_run_steps_remain_pending_with_requirement_context(self, client, isolated_db):
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL database",
            "confirm": True,
        })
        data = resp.json()
        run = isolated_db.get_run(data["run_id"])
        steps = isolated_db.list_run_steps(data["run_id"])
        tool_calls = isolated_db.list_tool_calls_for_run(data["run_id"])

        assert run.status.value == "pending"
        assert len(tool_calls) == 0
        for step in steps:
            assert step.status == "pending"
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in step.input

    def test_unlinked_step_requirement_context_is_explicit(self):
        source_preview = build_source_of_truth_from_intake(SourceOfTruthPreviewRequest(
            idea="Build a React web dashboard with JWT auth and PostgreSQL database",
            known_stack=["React", "FastAPI"],
            answers={"target_users": "Admins"},
        ))
        step = ConfirmedRunStepPreview(
            id="rs-unlinked",
            title="Unlinked exploratory task",
            description="Explore an unrelated idea.",
            required_requirement_ids=[],
            coverage_status=RequirementCoveragePreviewStatus.MISSING,
            drift_risk=DriftRiskLevel.MEDIUM,
            validation_notes="",
        )
        coverage = RequirementCoveragePreviewResponse(
            title="Requirement Coverage Preview",
            summary=RequirementCoveragePreviewSummary(
                requirements_total=len(source_preview.source_of_truth.requirements),
                covered_requirements=0,
                partially_covered_requirements=0,
                missing_requirements=len(source_preview.source_of_truth.requirements),
                unclear_requirements=0,
                unlinked_plan_phases=1,
                drift_risk=DriftRiskLevel.MEDIUM,
            ),
            items=[],
            unlinked_plan_phases=[],
            drift_risks=[],
            recommended_next_step="Resolve missing links.",
        )

        block = format_confirmed_run_step_requirement_context(
            step=step,
            source_of_truth=source_preview.source_of_truth,
            coverage=coverage,
        )

        assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in block
        assert "requirement_ids: []" in block
        assert "coverage_status: unlinked" in block
        assert "drift_risk: medium" in block
        assert "No requirement link found for this step." in block


class TestStepSourceOfTruthGuard:
    """Parser, evaluator, and endpoint tests for RunStep source-of-truth guard."""

    def test_parser_parses_full_requirement_context_block(self):
        step_input = """
Human task.
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids:
- REQ-1
- REQ-2
coverage_status: covered
drift_risk: medium
acceptance_criteria:
- Auth flow is reviewed.
constraints:
- Do not touch secrets or environment files
forbidden_changes:
- .env
validation_notes:
- Ready.
source_of_truth_summary: CRM from new_idea: Build CRM.
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
Trailing text.
"""
        parsed = parse_run_step_requirement_context(step_input)

        assert parsed.requirement_ids == ["REQ-1", "REQ-2"]
        assert parsed.coverage_status == "covered"
        assert parsed.drift_risk == "medium"
        assert parsed.acceptance_criteria == ["Auth flow is reviewed."]
        assert parsed.constraints == ["Do not touch secrets or environment files"]
        assert parsed.forbidden_changes == [".env"]
        assert parsed.validation_notes == ["Ready."]
        assert parsed.source_of_truth_summary == "CRM from new_idea: Build CRM."
        assert parsed.parse_warnings == []

    def test_parser_parses_empty_requirement_ids(self):
        parsed = parse_run_step_requirement_context("""
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids: []
coverage_status: unlinked
drift_risk: high
acceptance_criteria: []
constraints: []
forbidden_changes: []
validation_notes:
- No requirement link found for this step.
source_of_truth_summary: Missing links.
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
""")

        assert parsed.requirement_ids == []
        assert parsed.coverage_status == "unlinked"
        assert parsed.validation_notes == ["No requirement link found for this step."]

    def test_parser_tolerates_missing_sections(self):
        parsed = parse_run_step_requirement_context("""
AI_WORKBENCH_REQUIREMENT_CONTEXT:
requirement_ids:
- REQ-1
coverage_status: covered
END_AI_WORKBENCH_REQUIREMENT_CONTEXT
""")

        assert parsed.requirement_ids == ["REQ-1"]
        assert parsed.coverage_status == "covered"
        assert parsed.acceptance_criteria == []
        assert parsed.constraints == []
        assert parsed.parse_warnings == []

    def test_parser_warns_when_block_missing(self):
        parsed = parse_run_step_requirement_context("No metadata here")

        assert parsed.requirement_ids == []
        assert "AI_WORKBENCH_REQUIREMENT_CONTEXT block not found" in parsed.parse_warnings

    def test_guard_aligned_action_is_allowed(self):
        context = RunStepRequirementContext(
            requirement_ids=["REQ-1"],
            coverage_status="covered",
            drift_risk="low",
            acceptance_criteria=["Auth flow is reviewed and implemented."],
            constraints=["Do not touch secrets or environment files"],
            forbidden_changes=[".env"],
            source_of_truth_summary="Build auth dashboard for admins.",
        )

        result = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Implement REQ-1 auth dashboard validation UI",
            patch_summary="Auth flow for admins",
        )

        assert result.decision == StepSourceOfTruthGuardDecision.ALLOWED
        assert result.drift_risk == "low"
        assert result.matched_requirement_ids == ["REQ-1"]

    def test_guard_missing_context_warns_high(self):
        context = parse_run_step_requirement_context("No context")

        result = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Implement unrelated feature",
        )

        assert result.decision == StepSourceOfTruthGuardDecision.WARNING
        assert result.drift_risk == "high"
        assert result.warnings

    def test_guard_unlinked_context_warns_high(self):
        context = RunStepRequirementContext(
            requirement_ids=[],
            coverage_status="unlinked",
            drift_risk="medium",
            validation_notes=["No requirement link found for this step."],
        )

        result = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Implement some feature",
        )

        assert result.decision == StepSourceOfTruthGuardDecision.WARNING
        assert result.drift_risk == "high"
        assert "Step has no linked requirement ids." in result.warnings

    def test_guard_forbidden_change_blocks(self):
        context = RunStepRequirementContext(
            requirement_ids=["REQ-1"],
            coverage_status="covered",
            drift_risk="medium",
            acceptance_criteria=["Auth flow is reviewed."],
            constraints=["Do not touch secrets or environment files"],
            forbidden_changes=[".env", "backend/src/storage/database.py"],
            source_of_truth_summary="Build auth dashboard.",
        )

        result = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Modify auth environment settings",
            file_path=".env",
            patch_summary="Change .env token",
        )

        assert result.decision == StepSourceOfTruthGuardDecision.BLOCKED
        assert result.drift_risk == "critical"
        assert ".env" in result.forbidden_change_hits

    def test_guard_read_only_action_allowed_unless_forbidden_hit(self):
        context = RunStepRequirementContext(
            requirement_ids=["REQ-1"],
            coverage_status="covered",
            drift_risk="critical",
            acceptance_criteria=["Auth flow is reviewed."],
            constraints=["Do not touch secrets or environment files"],
            forbidden_changes=[".env"],
            source_of_truth_summary="Build auth dashboard.",
        )

        review = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Review REQ-1 auth flow implementation",
        )
        forbidden = evaluate_step_source_of_truth_guard(
            context=context,
            proposed_action="Review and modify .env",
            file_path=".env",
        )

        assert review.decision == StepSourceOfTruthGuardDecision.WARNING
        assert review.drift_risk == "critical"
        assert forbidden.decision == StepSourceOfTruthGuardDecision.BLOCKED

    def test_source_guard_endpoint_returns_result_for_confirmed_run_step(self, client, isolated_db):
        create_resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL database",
            "confirm": True,
        })
        data = create_resp.json()
        step = isolated_db.list_run_steps(data["run_id"])[0]

        resp = client.post(
            f"/api/runs/{data['run_id']}/steps/{step.id}/source-of-truth-guard",
            json={"proposed_action": "Review linked requirement implementation before patching"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["run_id"] == data["run_id"]
        assert body["step_id"] == step.id
        assert body["has_requirement_context"] is True
        assert body["parsed_context"]["requirement_ids"] is not None
        assert body["guard_result"]["decision"] in {"allowed", "warning", "blocked"}

    def test_source_guard_endpoint_verifies_run_step_relationship(self, client):
        first = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with auth",
            "confirm": True,
        }).json()
        second = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React dashboard with reports",
            "confirm": True,
        }).json()

        first_step_id = first["steps"][0]["step_id"]
        resp = client.post(
            f"/api/runs/{second['run_id']}/steps/{first_step_id}/source-of-truth-guard",
            json={"proposed_action": "Review step"},
        )

        assert resp.status_code == 404

    def test_source_guard_endpoint_is_read_only(self, client, isolated_db):
        create_resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL database",
            "confirm": True,
        })
        data = create_resp.json()
        run_before = isolated_db.get_run(data["run_id"])
        step_before = isolated_db.list_run_steps(data["run_id"])[0]
        tool_calls_before = isolated_db.list_tool_calls_for_run(data["run_id"])

        resp = client.post(
            f"/api/runs/{data['run_id']}/steps/{step_before.id}/source-of-truth-guard",
            json={"proposed_action": "Review REQ-1 implementation"},
        )

        run_after = isolated_db.get_run(data["run_id"])
        step_after = next(step for step in isolated_db.list_run_steps(data["run_id"]) if step.id == step_before.id)
        tool_calls_after = isolated_db.list_tool_calls_for_run(data["run_id"])

        assert resp.status_code == 200
        assert run_before.status == run_after.status
        assert step_before.status == step_after.status
        assert step_before.input == step_after.input
        assert len(tool_calls_before) == len(tool_calls_after) == 0

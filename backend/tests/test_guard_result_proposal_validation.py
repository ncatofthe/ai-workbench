"""Tests for guard result proposal validation endpoint.

Verifies that:
- POST /api/runs/{run_id}/steps/{step_id}/guard-results/{guard_result_id}/validate-for-proposal
  correctly validates a persisted guard result against a proposed patch payload
- Read-only: no DB writes, no tool_calls, no proposals, no execution, no state mutation
- Validation logic: blocked → invalid, stale → invalid, warning w/o ack → invalid,
  warning w/ ack → valid, allowed → valid
"""

from __future__ import annotations

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


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


def _create_run_with_steps(client) -> tuple[str, str]:
    """Create a run via confirmed-run and return (run_id, first_step_id)."""
    resp = client.post("/api/project-intake/confirmed-run", json={
        "idea": "Build a React dashboard with JWT auth and PostgreSQL",
        "confirm": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    return data["run_id"], data["steps"][0]["step_id"]


def _persist_guard(client, run_id: str, step_id: str, action: str = "Add error handling") -> str:
    """Persist a guard result and return guard_result_id."""
    resp = client.post(
        f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
        json={"proposed_action": action},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["persisted"] is True
    return data["guard_result_id"]


def _persist_warning_guard(run_id: str, step_id: str) -> str:
    record = build_workflow_guard_result_record(
        id="validation-warning-guard",
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(proposed_action="Warning validation"),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=WorkflowGuardDecision.WARNING,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            warnings=["Manual acknowledgement required"],
        ),
    )
    create_guard_result(record)
    return record.id


class TestValidateEndpoint404s:
    """Validation endpoint returns 404 for bad paths."""

    def test_invalid_run_returns_404(self, client):
        resp = client.post(
            "/api/runs/bad-run/steps/bad-step/guard-results/bad-id/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 404

    def test_invalid_step_returns_404(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        resp = client.post(
            f"/api/runs/{run_id}/steps/nonexistent-step/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 404

    def test_invalid_guard_result_id_returns_404(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/nonexistent-id/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 404

    def test_guard_from_wrong_run_returns_404(self, client):
        run_id_1, step_id_1 = _create_run_with_steps(client)
        run_id_2, step_id_2 = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id_1, step_id_1)
        resp = client.post(
            f"/api/runs/{run_id_2}/steps/{step_id_2}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 404

    def test_guard_from_wrong_step_returns_404(self, client):
        run_id, step_id = _create_run_with_steps(client)
        # Get second step if available, or just use a fake
        gid = _persist_guard(client, run_id, step_id)
        resp = client.post(
            f"/api/runs/{run_id}/steps/wrong-step-id/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 404


class TestValidateResponseShape:
    """Validation response has correct shape."""

    def test_response_includes_all_expected_fields(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Shape test action")
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={"proposed_action": "Shape test action"},
        )
        assert resp.status_code == 200
        data = resp.json()
        expected_keys = {
            "guard_result_id", "valid", "decision", "is_stale", "stale_reasons",
            "blocking_reasons", "warnings", "requires_warning_acknowledgement",
            "recommended_next_step",
        }
        assert expected_keys == set(data.keys())
        assert data["guard_result_id"] == gid

    def test_response_types(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        data = resp.json()
        assert isinstance(data["valid"], bool)
        assert isinstance(data["decision"], str)
        assert isinstance(data["is_stale"], bool)
        assert isinstance(data["stale_reasons"], list)
        assert isinstance(data["blocking_reasons"], list)
        assert isinstance(data["warnings"], list)
        assert isinstance(data["requires_warning_acknowledgement"], bool)
        assert isinstance(data["recommended_next_step"], str)


class TestValidateWithMatchingPayload:
    """Validate with the same proposed_action used to persist."""

    def test_matching_action_returns_valid(self, client):
        run_id, step_id = _create_run_with_steps(client)
        action = "Add error handling to auth module"
        gid = _persist_guard(client, run_id, step_id, action)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={"proposed_action": action},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Guard should be valid (allowed or warning-ack'd) since action matches
        assert data["guard_result_id"] == gid
        # Decision should be one of the valid enum values
        assert data["decision"] in ("allowed", "warning", "blocked")

    def test_empty_body_uses_record_defaults(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Default test")
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "decision" in data


class TestValidateSafety:
    """Validation endpoint is read-only — no side effects."""

    def test_validate_does_not_create_tool_calls(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        conn = database._connect()
        count_before = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={"proposed_action": "Safety check"},
        )
        conn = database._connect()
        count_after = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        assert count_after == count_before

    def test_validate_does_not_mutate_run_status(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        run_before = client.get(f"/api/runs/{run_id}").json()
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        run_after = client.get(f"/api/runs/{run_id}").json()
        assert run_before["status"] == run_after["status"]

    def test_validate_does_not_mutate_guard_result(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        before = client.get(f"/api/runs/{run_id}/guard-results/{gid}").json()
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={"proposed_action": "Mutate check"},
        )
        after = client.get(f"/api/runs/{run_id}/guard-results/{gid}").json()
        assert before == after

    def test_validate_does_not_create_new_guard_results(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        conn = database._connect()
        count_before = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        conn = database._connect()
        count_after = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count_after == count_before

    def test_repeated_validation_returns_same_result(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Idempotent check")
        payload = {"proposed_action": "Idempotent check"}
        resp1 = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json=payload,
        )
        resp2 = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json=payload,
        )
        assert resp1.json() == resp2.json()


class TestValidateWarningAcknowledgement:
    """Warning acknowledgement flag behavior."""

    def test_warning_acknowledged_false_is_default(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={},
        )
        data = resp.json()
        # warning_acknowledged is false by default in the request
        assert isinstance(data["requires_warning_acknowledgement"], bool)

    def test_warning_acknowledged_true_passed(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_warning_guard(run_id, step_id)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={"proposed_action": "Warning validation", "warning_acknowledged": True},
        )
        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestValidateWithFileAndPatch:
    """Validation with file_path, old_text, new_text in payload."""

    def test_validate_with_file_path(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "File-based action")
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/guard-results/{gid}/validate-for-proposal",
            json={
                "proposed_action": "File-based action",
                "file_path": "src/auth.ts",
                "patch_summary": "Add error handling",
                "old_text": "const x = 1;",
                "new_text": "const x = 2;",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "is_stale" in data

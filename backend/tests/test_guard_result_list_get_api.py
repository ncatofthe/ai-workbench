"""Tests for guard result list/get API endpoints.

Verifies that:
- GET /api/runs/{run_id}/guard-results returns list of persisted guard results
- GET /api/runs/{run_id}/guard-results/{guard_result_id} returns single record
- Query params: step_id, include_stale, limit are respected
- 404 for invalid run/guard_result_id
- Response shape matches GuardResultItem / GuardResultListResponse
- Read-only: no DB writes, no tool_calls, no execution, no state mutation
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

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


def _create_run_with_steps(client) -> tuple[str, str]:
    """Create a run via confirmed-run and return (run_id, first_step_id)."""
    resp = client.post("/api/project-intake/confirmed-run", json={
        "idea": "Build a React dashboard with JWT auth and PostgreSQL",
        "confirm": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    run_id = data["run_id"]
    steps = data["steps"]
    assert len(steps) > 0
    return run_id, steps[0]["step_id"]


def _persist_guard(client, run_id: str, step_id: str, action: str = "Add error handling") -> str:
    """Persist a guard result via the guard endpoint and return the guard_result_id."""
    resp = client.post(
        f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
        json={"proposed_action": action},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["persisted"] is True
    return data["guard_result_id"]


class TestListGuardResults:
    """GET /api/runs/{run_id}/guard-results"""

    def test_empty_list_for_run_with_no_guard_results(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.get(f"/api/runs/{run_id}/guard-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == run_id
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_returns_persisted_guard_results(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid1 = _persist_guard(client, run_id, step_id, "First action")
        gid2 = _persist_guard(client, run_id, step_id, "Second action")
        resp = client.get(f"/api/runs/{run_id}/guard-results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = [item["id"] for item in data["items"]]
        assert gid1 in ids
        assert gid2 in ids

    def test_list_filter_by_step_id(self, client):
        run_id, step_id = _create_run_with_steps(client)
        _persist_guard(client, run_id, step_id, "Step action")
        resp = client.get(f"/api/runs/{run_id}/guard-results?step_id={step_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["step_id"] == step_id

    def test_list_filter_by_nonexistent_step_id(self, client):
        run_id, step_id = _create_run_with_steps(client)
        _persist_guard(client, run_id, step_id, "Some action")
        resp = client.get(f"/api/runs/{run_id}/guard-results?step_id=nonexistent-step-id")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []

    def test_list_limit_param(self, client):
        run_id, step_id = _create_run_with_steps(client)
        for i in range(5):
            _persist_guard(client, run_id, step_id, f"Action {i}")
        resp = client.get(f"/api/runs/{run_id}/guard-results?limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2

    def test_list_invalid_run_returns_404(self, client):
        resp = client.get("/api/runs/nonexistent-run/guard-results")
        assert resp.status_code == 404

    def test_list_response_shape(self, client):
        run_id, step_id = _create_run_with_steps(client)
        _persist_guard(client, run_id, step_id, "Shape check action")
        resp = client.get(f"/api/runs/{run_id}/guard-results")
        data = resp.json()
        assert "run_id" in data
        assert "total" in data
        assert "items" in data
        item = data["items"][0]
        expected_keys = {
            "id", "run_id", "step_id", "project_id", "decision", "drift_risk",
            "is_stale", "stale_reasons", "source", "proposal_tool_call_id",
            "apply_tool_call_id", "warning_acknowledged", "no_guard_override",
            "created_at", "updated_at", "expires_at", "proposed_action",
            "file_path", "patch_summary", "old_text_hash", "new_text_hash",
            "requirement_ids", "coverage_status", "matched_requirement_ids",
            "violated_constraints", "forbidden_change_hits", "warnings",
            "reasons", "recommended_next_step",
        }
        assert expected_keys.issubset(set(item.keys()))

    def test_list_does_not_create_tool_calls(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        _persist_guard(client, run_id, step_id, "Safety check")
        conn = database._connect()
        count_before = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        client.get(f"/api/runs/{run_id}/guard-results")
        conn = database._connect()
        count_after = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        assert count_after == count_before


class TestGetGuardResult:
    """GET /api/runs/{run_id}/guard-results/{guard_result_id}"""

    def test_get_returns_persisted_record(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Get test action")
        resp = client.get(f"/api/runs/{run_id}/guard-results/{gid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == gid
        assert data["run_id"] == run_id
        assert data["step_id"] == step_id
        assert data["proposed_action"] == "Get test action"

    def test_get_invalid_run_returns_404(self, client):
        resp = client.get("/api/runs/bad-run/guard-results/bad-id")
        assert resp.status_code == 404

    def test_get_invalid_guard_result_id_returns_404(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.get(f"/api/runs/{run_id}/guard-results/nonexistent-guard-id")
        assert resp.status_code == 404

    def test_get_guard_result_from_wrong_run_returns_404(self, client):
        run_id_1, step_id_1 = _create_run_with_steps(client)
        run_id_2, step_id_2 = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id_1, step_id_1, "Wrong run action")
        resp = client.get(f"/api/runs/{run_id_2}/guard-results/{gid}")
        assert resp.status_code == 404

    def test_get_response_shape_matches_list_item(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Shape match")
        list_resp = client.get(f"/api/runs/{run_id}/guard-results")
        list_item = list_resp.json()["items"][0]
        get_resp = client.get(f"/api/runs/{run_id}/guard-results/{gid}")
        get_data = get_resp.json()
        assert set(list_item.keys()) == set(get_data.keys())

    def test_get_does_not_create_tool_calls(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "No tool calls")
        conn = database._connect()
        count_before = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        client.get(f"/api/runs/{run_id}/guard-results/{gid}")
        conn = database._connect()
        count_after = conn.execute("SELECT COUNT(*) as c FROM tool_calls").fetchone()["c"]
        conn.close()
        assert count_after == count_before

    def test_get_does_not_mutate_run_status(self, client):
        run_id, step_id = _create_run_with_steps(client)
        gid = _persist_guard(client, run_id, step_id, "Status check")
        run_before = client.get(f"/api/runs/{run_id}").json()
        client.get(f"/api/runs/{run_id}/guard-results/{gid}")
        run_after = client.get(f"/api/runs/{run_id}").json()
        assert run_before["status"] == run_after["status"]

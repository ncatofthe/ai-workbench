"""Tests for guard endpoint persist=true/false wiring.

Verifies that:
- persist=false (default) is read-only, no guard_results rows created
- persist=true writes exactly one guard_results audit record
- response shape includes persisted/guard_result_id fields
- safety invariants hold: no tool_calls, no execution, no state mutation
"""

from __future__ import annotations

import json

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


class TestGuardEndpointPersistFalse:
    """Default behavior: persist=false, read-only, no DB writes."""

    def test_default_no_persist_param(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard",
            json={"proposed_action": "Add error handling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["persisted"] is False
        assert data["guard_result_id"] is None

    def test_persist_false_explicit(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=false",
            json={"proposed_action": "Add error handling"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["persisted"] is False
        assert data["guard_result_id"] is None

    def test_persist_false_no_guard_results_rows(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard",
            json={"proposed_action": "Add error handling"},
        )
        conn = database._connect()
        count = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count == 0

    def test_persist_false_preserves_response_shape(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard",
            json={"proposed_action": "Refactor auth module"},
        )
        data = resp.json()
        assert "run_id" in data
        assert "step_id" in data
        assert "has_requirement_context" in data
        assert "parsed_context" in data
        assert "guard_result" in data
        assert "persisted" in data
        assert "guard_result_id" in data


class TestGuardEndpointPersistTrue:
    """persist=true writes exactly one guard_results audit record."""

    def test_persist_true_returns_persisted(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add error handling to auth module"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["persisted"] is True
        assert data["guard_result_id"] is not None
        assert len(data["guard_result_id"]) > 0

    def test_persist_true_creates_one_guard_result(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add error handling"},
        )
        conn = database._connect()
        count = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count == 1

    def test_persist_true_record_matches_response(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add validation logic"},
        )
        data = resp.json()
        guard_result_id = data["guard_result_id"]

        from src.storage.guard_result_storage import get_guard_result

        record = get_guard_result(guard_result_id)
        assert record is not None
        assert record.run_id == run_id
        assert record.step_id == step_id
        assert record.result_snapshot.decision.value == data["guard_result"]["decision"]

    def test_persist_true_stores_input_hashes_not_raw_text(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={
                "proposed_action": "Replace old code with new code",
                "old_text": "def old_function(): pass",
                "new_text": "def new_function(): return True",
            },
        )
        conn = database._connect()
        row = conn.execute("SELECT input_snapshot_json FROM guard_results").fetchone()
        conn.close()
        raw = json.loads(row["input_snapshot_json"])
        assert "old_text" not in raw
        assert "new_text" not in raw
        assert raw.get("old_text_hash") is not None
        assert raw.get("new_text_hash") is not None

    def test_persist_true_with_file_path_and_patch_summary(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={
                "proposed_action": "Add logging",
                "file_path": "backend/src/api/handler.py",
                "patch_summary": "Add structured logging to request handler",
            },
        )
        data = resp.json()

        from src.storage.guard_result_storage import get_guard_result

        record = get_guard_result(data["guard_result_id"])
        assert record is not None
        assert record.input_snapshot.file_path == "backend/src/api/handler.py"
        assert record.input_snapshot.patch_summary == "Add structured logging to request handler"

    def test_repeated_persist_creates_separate_records(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        ids = []
        for i in range(3):
            resp = client.post(
                f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
                json={"proposed_action": f"Action variant {i}"},
            )
            ids.append(resp.json()["guard_result_id"])

        conn = database._connect()
        count = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count == 3
        assert len(set(ids)) == 3  # All unique IDs.

    def test_persist_true_source_is_run_step_guard(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Refactor"},
        )

        from src.storage.guard_result_storage import get_guard_result

        record = get_guard_result(resp.json()["guard_result_id"])
        assert record is not None
        assert record.source.value == "run_step_guard"


class TestGuardEndpointSafety:
    """Safety: no tool_calls, no execution, no state mutation."""

    def test_persist_true_no_tool_calls(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add auth"},
        )
        tool_calls = database.list_tool_calls_for_run(run_id)
        assert len(tool_calls) == 0

    def test_persist_true_run_status_unchanged(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        run_before = database.get_run(run_id)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add auth"},
        )
        run_after = database.get_run(run_id)
        assert run_after.status == run_before.status

    def test_persist_true_step_status_unchanged(self, client, isolated_db):
        run_id, step_id = _create_run_with_steps(client)
        steps_before = database.list_run_steps(run_id)
        step_before = next(s for s in steps_before if s.id == step_id)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "Add auth"},
        )
        steps_after = database.list_run_steps(run_id)
        step_after = next(s for s in steps_after if s.id == step_id)
        assert step_after.status == step_before.status

    def test_invalid_run_returns_404(self, client):
        resp = client.post(
            "/api/runs/nonexistent/steps/whatever/source-of-truth-guard?persist=true",
            json={"proposed_action": "Test"},
        )
        assert resp.status_code == 404

    def test_invalid_step_returns_404(self, client):
        run_id, _ = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/nonexistent/source-of-truth-guard?persist=true",
            json={"proposed_action": "Test"},
        )
        assert resp.status_code == 404

    def test_empty_proposed_action_returns_400(self, client):
        run_id, step_id = _create_run_with_steps(client)
        resp = client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": ""},
        )
        assert resp.status_code == 400

    def test_persist_false_after_persist_true_still_read_only(self, client, isolated_db):
        """After a persist=true call, a subsequent persist=false call must not write."""
        run_id, step_id = _create_run_with_steps(client)
        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard?persist=true",
            json={"proposed_action": "First call"},
        )
        conn = database._connect()
        count_after_first = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count_after_first == 1

        client.post(
            f"/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard",
            json={"proposed_action": "Second call no persist"},
        )
        conn = database._connect()
        count_after_second = conn.execute("SELECT COUNT(*) as c FROM guard_results").fetchone()["c"]
        conn.close()
        assert count_after_second == 1  # No new row.

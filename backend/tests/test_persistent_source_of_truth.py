"""Tests for Persistent Source of Truth v1.

Covers:
  GET /api/projects/{project_id}/source-of-truth
    1.  Returns 404 for unknown project
    2.  Returns found=False when no SoT document exists
    3.  Returns the active document when one exists
    4.  Falls back to latest draft when no active document exists

  PUT /api/projects/{project_id}/source-of-truth
    5.  Returns 404 for unknown project
    6.  Creates a new draft document (version=1)
    7.  Returns found=True and correct product_name
    8.  Second upsert increments version to 2
    9.  Setting status='active' archives previous active version
    10. Rejects documents with secret values in product_summary
    11. Rejects documents with secret values in product_name
    12. Rejects documents with secret values in requirement title
    13. Accepts documents without secret values

  GET /api/projects/{project_id}/source-of-truth/history
    14. Returns 404 for unknown project
    15. Returns empty history when no documents exist
    16. Returns version history newest first
    17. History includes correct status and product_name for each version

  GET /api/projects/{project_id}/source-of-truth/{version}
    18. Returns 404 for unknown project
    19. Returns found=False for missing version
    20. Returns the correct version when found

  POST /api/projects/{project_id}/source-of-truth/validate
    21. Returns 404 for unknown project
    22. Returns valid=True for a complete valid document
    23. Returns valid=False when product_summary and project_intent are both empty
    24. Returns errors for duplicate requirement ids
    25. Returns warning when no 'must' priority requirements
    26. Rejects documents with secret values (valid=False, drift_risk='critical')
    27. Returns warning when target_users is empty

  POST /api/projects/{project_id}/source-of-truth/summary
    28. Returns 404 for unknown project
    29. Returns found=False when no document exists
    30. Returns a non-empty summary string when active document exists
    31. Summary contains AI_WORKBENCH_REQUIREMENT_CONTEXT block

Safety invariants:
  - All endpoints reject secret-like values (api_key=, token=, password=, etc.)
  - No provider calls in any endpoint
  - No auto-apply, no auto-rollback, no autonomous execution
  - Storage is isolated (tmp_path db per test via isolated_db fixture)
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.storage import database


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "sot.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    return isolated_db.create_project(
        "SoT Test Project",
        str(project_dir),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────


def _minimal_upsert(
    *,
    product_name: str = "TestApp",
    product_summary: str = "A test application",
    status: str = "draft",
    requirements: list | None = None,
) -> dict:
    payload: dict = {
        "product_name": product_name,
        "product_summary": product_summary,
        "project_intent": "",
        "target_users": ["developer"],
        "goals": ["Ship fast"],
        "non_goals": [],
        "requirements": requirements or [],
        "constraints": [],
        "forbidden_changes": [],
        "acceptance_criteria": [],
        "architecture_notes": "",
        "decisions": [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "source": "manual",
        "status": status,
    }
    return payload


def _req(
    req_id: str = "REQ-001",
    title: str = "Must work offline",
    priority: str = "must",
) -> dict:
    return {
        "id": req_id,
        "title": title,
        "description": "",
        "priority": priority,
        "status": "proposed",
        "acceptance_criteria": [],
        "constraints": [],
        "tags": [],
    }


# ── GET /api/projects/{project_id}/source-of-truth ───────────────────────────


class TestGetSourceOfTruth:
    def test_1_unknown_project_returns_404(self, client):
        r = client.get("/api/projects/doesnotexist/source-of-truth")
        assert r.status_code == 404

    def test_2_no_document_returns_found_false(self, client, project):
        r = client.get(f"/api/projects/{project.id}/source-of-truth")
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is False
        assert data["document"] is None

    def test_3_returns_active_document(self, client, project):
        # Create an active document
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(status="active"),
        )
        r = client.get(f"/api/projects/{project.id}/source-of-truth")
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["status"] == "active"
        assert data["document"]["product_name"] == "TestApp"

    def test_4_falls_back_to_draft_when_no_active(self, client, project):
        # Create a draft only
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="DraftApp", status="draft"),
        )
        r = client.get(f"/api/projects/{project.id}/source-of-truth")
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["product_name"] == "DraftApp"


# ── PUT /api/projects/{project_id}/source-of-truth ───────────────────────────


class TestUpsertSourceOfTruth:
    def test_5_unknown_project_returns_404(self, client):
        r = client.put(
            "/api/projects/doesnotexist/source-of-truth",
            json=_minimal_upsert(),
        )
        assert r.status_code == 404

    def test_6_creates_draft_version_1(self, client, project):
        r = client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(status="draft"),
        )
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["version"] == 1
        assert data["document"]["status"] == "draft"

    def test_7_returns_correct_product_name(self, client, project):
        r = client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="MyCoolApp"),
        )
        assert r.status_code == 200
        assert r.json()["document"]["product_name"] == "MyCoolApp"

    def test_8_second_upsert_increments_version(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v1"),
        )
        r2 = client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v2"),
        )
        assert r2.status_code == 200
        assert r2.json()["document"]["version"] == 2

    def test_9_activating_archives_previous_active(self, client, project):
        # First active version
        r1 = client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v1-active", status="active"),
        )
        v1 = r1.json()["document"]["version"]

        # Second active version
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v2-active", status="active"),
        )

        # First version should now be archived
        rv1 = client.get(f"/api/projects/{project.id}/source-of-truth/{v1}")
        assert rv1.status_code == 200
        assert rv1.json()["document"]["status"] == "archived"

    def test_10_rejects_secret_in_product_summary(self, client, project):
        payload = _minimal_upsert(
            product_summary="Use api_key=mysecret123 to connect"
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_11_rejects_secret_in_product_name(self, client, project):
        payload = _minimal_upsert(product_name="token=abc123 app")
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_12_rejects_secret_in_requirement_title(self, client, project):
        req = _req(title="Must store password=hunter2 securely")
        payload = _minimal_upsert(requirements=[req])
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_13_accepts_document_without_secrets(self, client, project):
        payload = _minimal_upsert(
            product_name="SafeApp",
            product_summary="Stores user data securely",
            requirements=[_req()],
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 200
        assert r.json()["found"] is True


# ── GET /api/projects/{project_id}/source-of-truth/history ───────────────────


class TestSourceOfTruthHistory:
    def test_14_unknown_project_returns_404(self, client):
        r = client.get("/api/projects/doesnotexist/source-of-truth/history")
        assert r.status_code == 404

    def test_15_empty_history_when_no_documents(self, client, project):
        r = client.get(f"/api/projects/{project.id}/source-of-truth/history")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["versions"] == []

    def test_16_returns_history_newest_first(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v1"),
        )
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v2"),
        )
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="v3"),
        )

        r = client.get(f"/api/projects/{project.id}/source-of-truth/history")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        versions = [item["version"] for item in data["versions"]]
        assert versions == sorted(versions, reverse=True)

    def test_17_history_includes_correct_fields(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="HistoryApp", status="active"),
        )
        r = client.get(f"/api/projects/{project.id}/source-of-truth/history")
        assert r.status_code == 200
        item = r.json()["versions"][0]
        assert item["product_name"] == "HistoryApp"
        assert item["status"] == "active"
        assert "version" in item
        assert "created_at" in item


# ── GET /api/projects/{project_id}/source-of-truth/{version} ─────────────────


class TestGetSourceOfTruthVersion:
    def test_18_unknown_project_returns_404(self, client):
        r = client.get("/api/projects/doesnotexist/source-of-truth/1")
        assert r.status_code == 404

    def test_19_missing_version_returns_found_false(self, client, project):
        r = client.get(f"/api/projects/{project.id}/source-of-truth/999")
        assert r.status_code == 200
        assert r.json()["found"] is False

    def test_20_returns_correct_version(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="Version One"),
        )
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(product_name="Version Two"),
        )

        r = client.get(f"/api/projects/{project.id}/source-of-truth/1")
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["version"] == 1
        assert data["document"]["product_name"] == "Version One"


# ── POST /api/projects/{project_id}/source-of-truth/validate ─────────────────


class TestValidateSourceOfTruth:
    def test_21_unknown_project_returns_404(self, client):
        r = client.post(
            "/api/projects/doesnotexist/source-of-truth/validate",
            json=_minimal_upsert(),
        )
        assert r.status_code == 404

    def test_22_valid_complete_document_returns_valid_true(self, client, project):
        payload = _minimal_upsert(
            product_summary="Offline-first workbench",
            requirements=[_req(priority="must")],
        )
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_23_both_summary_and_intent_empty_returns_error(self, client, project):
        payload = _minimal_upsert(product_summary="")
        payload["project_intent"] = ""
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert any("product_summary" in e or "project_intent" in e for e in data["errors"])

    def test_24_duplicate_requirement_ids_return_error(self, client, project):
        req_a = _req("REQ-DUP", "First req")
        req_b = _req("REQ-DUP", "Second req with same id")
        payload = _minimal_upsert(requirements=[req_a, req_b])
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["valid"] is False
        assert any("REQ-DUP" in e for e in data["errors"])

    def test_25_no_must_requirement_returns_warning(self, client, project):
        payload = _minimal_upsert(
            requirements=[_req(priority="should")],
        )
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        # Missing 'must' produces a warning, not a hard error
        assert any("must" in w.lower() for w in data["warnings"])

    def test_26_secret_value_returns_invalid(self, client, project):
        payload = _minimal_upsert(
            product_summary="Connect via api_key=topsecret to service"
        )
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        # The model validator raises before validation logic — expect 422
        assert r.status_code == 422

    def test_27_empty_target_users_returns_warning(self, client, project):
        payload = _minimal_upsert()
        payload["target_users"] = []
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/validate",
            json=payload,
        )
        assert r.status_code == 200
        data = r.json()
        assert any("target_users" in w.lower() or "user" in w.lower() for w in data["warnings"])


# ── POST /api/projects/{project_id}/source-of-truth/summary ──────────────────


class TestSourceOfTruthSummary:
    def test_28_unknown_project_returns_404(self, client):
        r = client.post("/api/projects/doesnotexist/source-of-truth/summary", json={})
        assert r.status_code == 404

    def test_29_no_document_returns_found_false(self, client, project):
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/summary", json={}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is False
        assert data["summary"] == ""

    def test_30_returns_non_empty_summary(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(
                product_name="WorkbenchApp",
                product_summary="Local multi-agent IDE",
                status="active",
            ),
        )
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/summary", json={}
        )
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert "WorkbenchApp" in data["summary"] or "Local multi-agent IDE" in data["summary"]

    def test_31_summary_contains_requirement_context_block(self, client, project):
        client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json=_minimal_upsert(
                product_summary="Core workbench functionality",
                requirements=[_req("REQ-101", "Must work offline", "must")],
                status="active",
            ),
        )
        r = client.post(
            f"/api/projects/{project.id}/source-of-truth/summary", json={}
        )
        assert r.status_code == 200
        data = r.json()
        ctx = data["requirement_context"]
        assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in ctx
        assert "END_AI_WORKBENCH_REQUIREMENT_CONTEXT" in ctx

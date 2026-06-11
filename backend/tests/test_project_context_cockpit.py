"""Tests for Project Context Cockpit v1.

Covers:
  Endpoint tests (1–13):
    1.  Returns 200 and ProjectContextCockpitSummary for a valid run
    2.  Returns 404 for an unknown run_id
    3.  Returns has_project=False when run has no project
    4.  Returns has_project=True when run has a project
    5.  source_of_truth.available=False when project has no SoT
    6.  source_of_truth.available=True and counts correct when SoT exists
    7.  module_map.available=False when project has no module map
    8.  module_map.available=True and module_count correct when map exists
    9.  run.readiness is present in response
    10. module_awareness fields are present (may be zero)
    11. Endpoint creates no tool_calls
    12. Endpoint does not mutate run or any step
    13. safety_notes list is present in response

  Static safety (14–20):
    14. routes.py cockpit endpoint has no execute_run call
    15. routes.py cockpit endpoint has no asyncio.create_task
    16. routes.py cockpit endpoint has no subprocess call
    17. routes.py cockpit endpoint has no provider call
    18. routes.py cockpit endpoint has no create_tool_call
    19. routes.py cockpit endpoint has no apply_project_patch
    20. routes.py cockpit section contains no DB write statements

  Compatibility (21–26):
    21. Delivery module awareness tests still importable
    22. RunDetail UX consolidation tests still importable (if file exists)
    23. Full delivery loop tests still importable
    24. Module-aware guard policy tests still importable
    25. Project module map tests still importable
    26. Persistent SoT tests still importable

Safety invariants:
  - Read-only endpoint — no DB writes, no tool_calls, no provider calls
  - No execute_run, no asyncio.create_task, no subprocess
  - No auto-proposal, auto-apply, auto-rollback
  - No guard or approval bypass
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient

from src.storage import database


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "cockpit.db"))
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
    return isolated_db.create_project("Cockpit Test Project", str(project_dir))


@pytest.fixture()
def run_no_project(isolated_db):
    return isolated_db.create_run("Orphan run", project_id="")


@pytest.fixture()
def run_with_project(isolated_db, project):
    return isolated_db.create_run("Project run", project_id=project.id)


def _sot_payload(n_req: int = 2, n_risk: int = 1, n_oq: int = 3) -> dict:
    return {
        "product_name": "Test Product",
        "product_summary": "Cockpit test product",
        "project_intent": "",
        "target_users": ["developer"],
        "goals": ["Verify cockpit"],
        "non_goals": [],
        "requirements": [
            {
                "id": f"REQ-{i:03d}",
                "title": f"Req {i}",
                "description": "",
                "priority": "must",
                "status": "proposed",
                "acceptance_criteria": [],
                "constraints": [],
                "tags": [],
            }
            for i in range(n_req)
        ],
        "constraints": [],
        "forbidden_changes": [],
        "acceptance_criteria": [],
        "architecture_notes": "",
        "decisions": [],
        "assumptions": [],
        "risks": [f"Risk {i}" for i in range(n_risk)],
        "open_questions": [f"Q{i}" for i in range(n_oq)],
        "source": "manual",
        "status": "active",
    }


def _module_payload(n: int = 3) -> dict:
    modules = [
        {
            "id": uuid.uuid4().hex[:8],
            "name": f"Module{i}",
            "slug": f"module-{i}",
            "description": f"Module {i}",
            "module_type": "feature",
            "responsibilities": [],
            "paths": [f"src/module{i}"],
            "key_files": [],
            "related_requirements": [],
            "test_hints": [],
            "risks": [],
            "confidence": "medium",
        }
        for i in range(n)
    ]
    return {
        "modules": modules,
        "ignored_paths": [],
        "scan_summary": "test",
        "source": "manual",
        "status": "active",
    }


# ── Endpoint Tests ─────────────────────────────────────────────────────────────


def test_01_returns_200_for_valid_run(client, run_no_project):
    """Endpoint returns 200 and a valid summary for any run."""
    resp = client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_no_project.id


def test_02_returns_404_for_unknown_run(client):
    """Endpoint returns 404 when run_id does not exist."""
    resp = client.get("/api/runs/nonexistent-run-xyz/project-context-cockpit")
    assert resp.status_code == 404


def test_03_has_project_false_when_no_project(client, run_no_project):
    """has_project is False when run has no associated project."""
    resp = client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_project"] is False
    assert body["project_id"] is None
    assert body["project_name"] is None


def test_04_has_project_true_when_project_exists(client, run_with_project, project):
    """has_project is True when run has an associated project."""
    resp = client.get(f"/api/runs/{run_with_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_project"] is True
    assert body["project_id"] == project.id


def test_05_sot_available_false_when_no_sot(client, run_with_project, project):
    """source_of_truth.available is False when project has no SoT."""
    resp = client.get(f"/api/runs/{run_with_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_of_truth"]["available"] is False


def test_06_sot_counts_correct_when_sot_exists(client, run_with_project, project):
    """source_of_truth shows correct counts when SoT is present."""
    payload = _sot_payload(n_req=4, n_risk=2, n_oq=1)
    put_resp = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
    assert put_resp.status_code == 200

    resp = client.get(f"/api/runs/{run_with_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    sot = body["source_of_truth"]
    assert sot["available"] is True
    assert sot["requirement_count"] == 4
    assert sot["risk_count"] == 2
    assert sot["open_question_count"] == 1
    assert "Test Product" in sot["product_name"]


def test_07_module_map_available_false_when_no_map(client, run_with_project, project):
    """module_map.available is False when project has no module map."""
    resp = client.get(f"/api/runs/{run_with_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert body["module_map"]["available"] is False


def test_08_module_map_counts_correct_when_map_exists(client, run_with_project, project):
    """module_map shows correct module_count when map is present."""
    payload = _module_payload(n=5)
    put_resp = client.put(f"/api/projects/{project.id}/module-map", json=payload)
    assert put_resp.status_code == 200

    resp = client.get(f"/api/runs/{run_with_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    mm = body["module_map"]
    assert mm["available"] is True
    assert mm["module_count"] == 5
    assert isinstance(mm["key_modules"], list)
    assert len(mm["key_modules"]) <= 8  # capped at 8


def test_09_run_readiness_present(client, run_no_project):
    """run.readiness field is always present in response."""
    resp = client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    run_section = body["run"]
    assert "readiness" in run_section
    assert isinstance(run_section["readiness"], str)


def test_10_module_awareness_fields_present(client, run_no_project):
    """module_awareness fields are present and typed correctly."""
    resp = client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    ma = body["module_awareness"]
    assert isinstance(ma["touched_modules"], list)
    assert isinstance(ma["expected_modules"], list)
    assert isinstance(ma["blocked_policy_count"], int)
    assert isinstance(ma["warning_count"], int)
    assert isinstance(ma["recommended_tests"], list)


def test_11_endpoint_creates_no_tool_calls(client, isolated_db, run_no_project):
    """The cockpit endpoint creates zero new tool_calls."""
    tool_calls_before = len(isolated_db.list_tool_calls_for_run(run_no_project.id))
    client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    tool_calls_after = len(isolated_db.list_tool_calls_for_run(run_no_project.id))
    assert tool_calls_before == tool_calls_after


def test_12_endpoint_does_not_mutate_run(client, isolated_db, run_no_project):
    """The cockpit endpoint does not change run status or step count."""
    run_before = isolated_db.get_run(run_no_project.id)
    steps_before = isolated_db.list_run_steps(run_no_project.id)

    client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")

    run_after = isolated_db.get_run(run_no_project.id)
    steps_after = isolated_db.list_run_steps(run_no_project.id)

    assert run_before.status == run_after.status
    assert len(steps_before) == len(steps_after)


def test_13_safety_notes_present(client, run_no_project):
    """safety_notes list is always present in response."""
    resp = client.get(f"/api/runs/{run_no_project.id}/project-context-cockpit")
    assert resp.status_code == 200
    body = resp.json()
    assert "safety_notes" in body
    assert isinstance(body["safety_notes"], list)


# ── Static Safety Tests ────────────────────────────────────────────────────────

ROUTES_PY = (
    pathlib.Path(__file__).parent.parent / "src" / "api" / "routes.py"
)


def _read_cockpit_section(routes_text: str) -> str:
    """Extract just the cockpit endpoint + helper from routes.py."""
    idx = routes_text.find("def _cockpit_next_action(")
    if idx == -1:
        return routes_text
    return routes_text[idx:]


def test_14_no_execute_run_in_cockpit():
    """Cockpit section of routes.py contains no execute_run call."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "execute_run(" not in section


def test_15_no_asyncio_create_task_in_cockpit():
    """Cockpit section of routes.py contains no asyncio.create_task."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "asyncio.create_task(" not in section


def test_16_no_subprocess_in_cockpit():
    """Cockpit section of routes.py contains no subprocess call."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "subprocess" not in section
    assert "os.system(" not in section


def test_17_no_provider_call_in_cockpit():
    """Cockpit section of routes.py makes no provider calls."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "call_ollama(" not in section
    assert "call_claude(" not in section
    assert "call_openai(" not in section
    assert "call_provider(" not in section


def test_18_no_create_tool_call_in_cockpit():
    """Cockpit section of routes.py does not create tool_calls."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "create_tool_call(" not in section
    assert "log_tool_call(" not in section


def test_19_no_apply_project_patch_in_cockpit():
    """Cockpit section of routes.py does not call apply_project_patch."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    assert "apply_project_patch(" not in section


def test_20_no_db_writes_in_cockpit():
    """Cockpit section of routes.py contains no DB write operations."""
    text = ROUTES_PY.read_text()
    section = _read_cockpit_section(text)
    # Common write patterns
    for write_call in ("db.execute(", "cursor.execute(", ".commit(", "INSERT INTO", "UPDATE ", "DELETE FROM"):
        assert write_call not in section, f"Found DB write: {write_call!r}"


# ── Compatibility Tests ────────────────────────────────────────────────────────


def test_21_delivery_module_awareness_tests_importable():
    """Delivery module awareness test file is importable (no import errors)."""
    import importlib
    import sys
    mod_name = "tests.test_delivery_report_module_awareness"
    if mod_name in sys.modules:
        return  # already imported — compatible
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_delivery_report_module_awareness not found — skip compat check")


def test_22_rundetail_ux_tests_importable():
    """RunDetail UX consolidation test file is importable if it exists."""
    import importlib
    import sys
    mod_name = "tests.test_rundetail_ux_consolidation"
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_rundetail_ux_consolidation not found — skip compat check")


def test_23_delivery_loop_tests_importable():
    """Full delivery loop test file is importable."""
    import importlib
    import sys
    mod_name = "tests.test_real_project_dogfooding"
    if mod_name in sys.modules:
        return
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_real_project_dogfooding not found — skip compat check")


def test_24_module_aware_guard_policy_importable():
    """Module-aware guard policy test file is importable."""
    import importlib
    import sys
    mod_name = "tests.test_module_map_agent_context_wiring"
    if mod_name in sys.modules:
        return
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_module_map_agent_context_wiring not found — skip compat check")


def test_25_project_module_map_tests_importable():
    """Project module map test file is importable."""
    import importlib
    import sys
    mod_name = "tests.test_project_module_map"
    if mod_name in sys.modules:
        return
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_project_module_map not found — skip compat check")


def test_26_persistent_sot_tests_importable():
    """Persistent SoT test file is importable."""
    import importlib
    import sys
    mod_name = "tests.test_persistent_source_of_truth"
    if mod_name in sys.modules:
        return
    try:
        importlib.import_module(mod_name)
    except ModuleNotFoundError:
        pytest.skip("test_persistent_source_of_truth not found — skip compat check")

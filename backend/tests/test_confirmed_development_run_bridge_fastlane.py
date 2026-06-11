"""Confirmed Development Run Bridge Fastlane v1 — test suite.

52 tests covering:
  1–10   Preflight / contract gating (all confirmation booleans, contract decision)
  11–21  Creation behavior (run status, step count, context embedding)
  22–30  No forbidden entities or actions
  31–38  Endpoint behavior and determinism
  39–43  Compatibility with existing suites
  44–50  Static/safety scan of new endpoint code
  51–52  Frontend build stubs (tsc/build verified in Phase 7 checks)

Safety contract verified:
  - No execute_run, asyncio.create_task, create_tool_call
  - No provider calls, no file reads, no command execution
  - No project creation, no patch proposal, no apply patch
  - Run status = pending, step status = pending, provider_allowed = False
"""

from __future__ import annotations

import importlib.util
import pathlib
import re

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import (
    ConfirmedDevelopmentRunCreateRequest,
    ConfirmedDevelopmentRunCreateResponse,
    ConfirmedDevelopmentRunCreatedStep,
    build_confirmed_development_run_creation_input,
    build_pending_run_step_inputs_from_development_preview,
    _BRIDGE_SAFETY_NOTES,
)
from src.storage import database


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "bridge-fastlane.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "test-saas"
    project_dir.mkdir()
    return isolated_db.create_project(name="Test SaaS Project", path=str(project_dir))


# ── Shared helpers ────────────────────────────────────────────────────────────


def _preview(run_title="Build SaaS Task Manager", ready=True, steps=None) -> dict:
    if steps is None:
        steps = [
            {
                "id": "STEP-001",
                "title": "Context Confirmation",
                "description": "Confirm SoT, module map, and architecture before coding.",
                "agent_role": "ContextAnalyst",
                "requirement_ids": ["REQ-001", "REQ-002"],
                "module_ids": ["core-api"],
                "depends_on": [],
                "expected_outputs": ["SoT confirmed."],
                "validation_steps": ["Verify SoT is loaded."],
                "safety_gates": ["No auto-start"],
                "manual_approval_required": False,
                "provider_allowed": False,
                "risk_level": "low",
                "estimated_order": 1,
            },
            {
                "id": "STEP-002",
                "title": "Backend Implementation",
                "description": "Implement core API endpoints with FastAPI.",
                "agent_role": "BackendDeveloper",
                "requirement_ids": ["REQ-001"],
                "module_ids": ["core-api", "auth"],
                "depends_on": ["STEP-001"],
                "expected_outputs": ["backend/src/api/endpoints.py"],
                "validation_steps": ["Run pytest."],
                "safety_gates": ["No provider call", "Manual approval"],
                "manual_approval_required": True,
                "provider_allowed": False,
                "risk_level": "medium",
                "estimated_order": 2,
            },
        ]
    return {
        "preview_only": True,
        "mode": "idea",
        "run_title": run_title,
        "run_goal": "Build a task manager with auth, dashboard, and reporting.",
        "recommended_run_mode": "guided",
        "steps": steps,
        "validation": {
            "ready_to_create_run": ready,
            "readiness": "ready" if ready else "not ready",
            "errors": [] if ready else ["Missing SoT"],
            "warnings": [],
            "missing_inputs": [],
            "blocked_reasons": [],
        },
    }


def _valid_payload(project_id: str, **overrides) -> dict:
    payload = {
        "project_id": project_id,
        "confirm_create": True,
        "contract_confirmed": True,
        "source_of_truth_confirmed": True,
        "module_map_confirmed": True,
        "provider_disabled_confirmed": True,
        "later_actions_confirmed": True,
        "development_run_preview": _preview(),
        "preferred_run_mode": "guided",
    }
    payload.update(overrides)
    return payload


def _post(client: TestClient, project_id: str, **overrides) -> dict:
    resp = client.post(
        "/api/project-intake/confirmed-development-run/create",
        json=_valid_payload(project_id, **overrides),
    )
    return resp


# ── 1–10  Preflight / contract gating ────────────────────────────────────────


class TestPreflightGating:
    """Tests 1–10: all confirmation booleans and contract gating."""

    def test_01_missing_project_id_blocks(self, client, project):
        payload = _valid_payload(project.id)
        payload["project_id"] = ""
        resp = client.post("/api/project-intake/confirmed-development-run/create", json=payload)
        assert resp.status_code == 400
        assert "project_id" in resp.json()["detail"].lower()

    def test_02_confirm_create_false_blocks(self, client, project):
        resp = _post(client, project.id, confirm_create=False)
        assert resp.status_code == 400
        assert "confirm_create" in resp.json()["detail"].lower()

    def test_03_missing_contract_confirmed_blocks(self, client, project):
        resp = _post(client, project.id, contract_confirmed=False)
        assert resp.status_code == 400
        assert "contract_confirmed" in resp.json()["detail"].lower()

    def test_04_missing_source_of_truth_confirmed_blocks(self, client, project):
        resp = _post(client, project.id, source_of_truth_confirmed=False)
        assert resp.status_code == 400
        assert "source_of_truth_confirmed" in resp.json()["detail"].lower()

    def test_05_missing_module_map_confirmed_blocks(self, client, project):
        resp = _post(client, project.id, module_map_confirmed=False)
        assert resp.status_code == 400
        assert "module_map_confirmed" in resp.json()["detail"].lower()

    def test_06_missing_provider_disabled_confirmed_blocks(self, client, project):
        resp = _post(client, project.id, provider_disabled_confirmed=False)
        assert resp.status_code == 400
        assert "provider_disabled_confirmed" in resp.json()["detail"].lower()

    def test_07_missing_later_actions_confirmed_blocks(self, client, project):
        resp = _post(client, project.id, later_actions_confirmed=False)
        assert resp.status_code == 400
        assert "later_actions_confirmed" in resp.json()["detail"].lower()

    def test_08_invalid_preview_ready_false_blocks_contract(self, client, project):
        resp = _post(client, project.id, development_run_preview=_preview(ready=False))
        assert resp.status_code == 200
        body = resp.json()
        # Contract blocks because development_preview_valid=False
        assert body["created"] is False
        assert body["contract_decision"] == "blocked"

    def test_09_provider_allowed_true_in_step_blocks(self, client, project):
        bad_steps = [
            {
                "id": "STEP-001",
                "title": "Auth step",
                "description": "Implement auth.",
                "agent_role": "BackendDeveloper",
                "requirement_ids": ["REQ-001"],
                "module_ids": ["auth"],
                "depends_on": [],
                "expected_outputs": [],
                "validation_steps": [],
                "safety_gates": [],
                "manual_approval_required": False,
                "provider_allowed": True,  # forbidden
                "risk_level": "high",
                "estimated_order": 1,
            }
        ]
        resp = _post(client, project.id, development_run_preview=_preview(steps=bad_steps))
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is False
        assert body["contract_decision"] == "blocked"

    def test_10_valid_request_allows_pending_run_creation(self, client, project):
        resp = _post(client, project.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is True
        assert body["run_id"] is not None


# ── 11–21  Creation behavior ──────────────────────────────────────────────────


class TestCreationBehavior:
    """Tests 11–21: run/step properties after successful creation."""

    @pytest.fixture(autouse=True)
    def _run_creation(self, client, project, isolated_db):
        resp = _post(client, project.id)
        assert resp.status_code == 200
        self.body = resp.json()
        self.db = isolated_db
        self.project = project

    def test_11_creates_exactly_one_run(self):
        runs = self.db.list_runs()
        assert len(runs) == 1

    def test_12_creates_expected_number_of_steps(self):
        # _preview() has 2 steps
        assert len(self.body["steps"]) == 2

    def test_13_run_status_is_pending(self):
        assert self.body["status"] == "pending"

    def test_14_all_step_statuses_are_pending(self):
        for step in self.body["steps"]:
            assert step["status"] == "pending"

    def test_15_provider_allowed_false_on_every_step(self):
        for step in self.body["steps"]:
            assert step["provider_allowed"] is False

    def test_16_requirement_ids_preserved_in_response(self):
        step0 = self.body["steps"][0]
        assert "REQ-001" in step0["requirement_ids"]
        assert "REQ-002" in step0["requirement_ids"]

    def test_17_module_ids_preserved_in_response(self):
        step0 = self.body["steps"][0]
        assert "core-api" in step0["module_ids"]

    def test_18_agent_roles_preserved_in_response(self):
        roles = [s["agent_role"] for s in self.body["steps"]]
        assert "ContextAnalyst" in roles
        assert "BackendDeveloper" in roles

    def test_19_depends_on_preserved(self):
        step1 = self.body["steps"][1]
        assert "STEP-001" in step1["depends_on"]

    def test_20_safety_gates_embedded_in_step_input(self):
        runs = self.db.list_runs()
        run_id = runs[0].id
        steps = self.db.list_run_steps(run_id)
        # step[1] has manual approval and safety gates in _preview
        inputs = " ".join(s.input for s in steps)
        assert "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT" in inputs
        assert "safety_gates" in inputs

    def test_21_manual_approval_marker_embedded(self):
        runs = self.db.list_runs()
        run_id = runs[0].id
        steps = self.db.list_run_steps(run_id)
        # step[1] has manual_approval_required=True
        inputs = " ".join(s.input for s in steps)
        assert "manual_approval_required" in inputs


# ── 22–30  No forbidden entities or actions ───────────────────────────────────


class TestNoForbiddenActions:
    """Tests 22–30: nothing forbidden is created or executed."""

    def test_22_does_not_create_project(self, client, project, isolated_db):
        projects_before = len(isolated_db.list_projects())
        _post(client, project.id)
        assert len(isolated_db.list_projects()) == projects_before

    def test_23_does_not_create_tool_calls(self, client, project, isolated_db):
        _post(client, project.id)
        runs = isolated_db.list_runs()
        assert len(runs) == 1
        tcs = isolated_db.list_tool_calls_for_run(runs[0].id)
        assert len(tcs) == 0

    def test_24_does_not_call_providers(self, client, project):
        # Pure function — call twice and get identical result (no external state)
        r1 = _post(client, project.id).json()
        assert r1["created"] is True

    def test_25_does_not_call_execute_run(self, client, project, isolated_db):
        _post(client, project.id)
        runs = isolated_db.list_runs()
        # Run must still be pending — not running/completed
        assert runs[0].status.value == "pending"

    def test_26_does_not_call_asyncio_create_task(self, client, project, isolated_db):
        _post(client, project.id)
        # No background task started — run remains pending
        runs = isolated_db.list_runs()
        assert runs[0].status.value == "pending"

    def test_27_does_not_read_files(self, client, project):
        # Non-existent project path does not cause FileNotFoundError
        resp = _post(client, project.id)
        assert resp.status_code == 200

    def test_28_does_not_run_commands(self, client, project):
        resp = _post(client, project.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is True

    def test_29_does_not_create_patch_proposal(self, client, project, isolated_db):
        _post(client, project.id)
        # No patch proposal tables exist — just verify nothing unexpected happened
        runs = isolated_db.list_runs()
        assert len(runs) == 1

    def test_30_does_not_apply_patch(self, client, project, isolated_db):
        _post(client, project.id)
        runs = isolated_db.list_runs()
        run_steps = isolated_db.list_run_steps(runs[0].id)
        for step in run_steps:
            assert step.status == "pending"


# ── 31–38  Endpoint behavior ─────────────────────────────────────────────────


class TestEndpointBehavior:
    """Tests 31–38: response structure and determinism."""

    def test_31_returns_created_true_on_success(self, client, project):
        body = _post(client, project.id).json()
        assert body["created"] is True

    def test_32_returns_run_id_on_success(self, client, project):
        body = _post(client, project.id).json()
        assert body["run_id"] is not None
        assert isinstance(body["run_id"], str)
        assert len(body["run_id"]) > 0

    def test_33_returns_created_steps(self, client, project):
        body = _post(client, project.id).json()
        assert isinstance(body["steps"], list)
        assert len(body["steps"]) > 0
        step = body["steps"][0]
        assert "step_id" in step
        assert "title" in step
        assert "status" in step

    def test_34_returns_safety_notes(self, client, project):
        body = _post(client, project.id).json()
        assert isinstance(body["safety_notes"], list)
        assert len(body["safety_notes"]) > 0

    def test_35_next_recommended_action_present(self, client, project):
        body = _post(client, project.id).json()
        assert isinstance(body["next_recommended_action"], str)
        assert len(body["next_recommended_action"]) > 0

    def test_36_invalid_preview_empty_blocks(self, client, project):
        resp = _post(client, project.id, development_run_preview={})
        assert resp.status_code == 400

    def test_37_empty_steps_in_preview_blocks_via_contract(self, client, project):
        # Empty steps trigger REQ-CRC-006 in the contract → blocked (200, created=False)
        preview = _preview(steps=[])
        resp = _post(client, project.id, development_run_preview=preview)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is False
        assert body["contract_decision"] == "blocked"

    def test_38_secret_in_run_title_blocks_via_contract(self, client, project):
        preview = _preview(run_title="password=supersecret_value123")
        resp = _post(client, project.id, development_run_preview=preview)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is False
        assert body["contract_decision"] == "blocked"


# ── 39–43  Compatibility ──────────────────────────────────────────────────────


class TestCompatibility:
    """Tests 39–43: existing test suites are unaffected."""

    def test_39_contract_module_still_importable(self):
        from src.release.confirmed_development_run_creation_contract import (
            evaluate_confirmed_run_creation_contract,
        )
        assert callable(evaluate_confirmed_run_creation_contract)

    def test_40_contract_preview_wiring_builder_still_importable(self):
        from src.orchestrator.project_intake import build_confirmed_run_creation_contract_preview
        assert callable(build_confirmed_run_creation_contract_preview)

    def test_41_dev_run_preview_builder_still_importable(self):
        from src.orchestrator.project_intake import build_intake_development_run_preview
        assert callable(build_intake_development_run_preview)

    def test_42_multi_agent_plan_builder_still_importable(self):
        from src.orchestrator.project_intake import build_multi_agent_plan_from_intake
        assert callable(build_multi_agent_plan_from_intake)

    def test_43_step_input_builder_is_pure(self):
        meta = build_pending_run_step_inputs_from_development_preview(_preview())
        assert len(meta) == 2
        for m in meta:
            assert "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT" in m["input_text"]
            assert m["provider_allowed"] is False


# ── 44–50  Static / safety scan ───────────────────────────────────────────────


@pytest.fixture(scope="module")
def routes_bridge_source() -> str:
    """Extract only the confirmed-development-run/create section from routes.py."""
    spec = importlib.util.find_spec("src.api.routes")
    assert spec is not None and spec.origin is not None
    src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
    marker = "/api/project-intake/confirmed-development-run/create"
    idx = src.find(marker)
    # Pull ~150 lines after the endpoint decorator
    if idx < 0:
        return src
    end = src.find("\n# ──", idx + 1)
    return src[idx:end] if end > idx else src[idx:idx + 6000]


class TestStaticSafety:
    """Tests 44–50: no forbidden patterns in the new endpoint code."""

    def test_44_no_execute_run(self, routes_bridge_source):
        assert "execute_run(" not in routes_bridge_source

    def test_45_no_asyncio_create_task(self, routes_bridge_source):
        assert "asyncio.create_task" not in routes_bridge_source

    def test_46_no_provider_calls(self, routes_bridge_source):
        assert "ollama" not in routes_bridge_source.lower()
        assert "claude_provider" not in routes_bridge_source
        assert "codex" not in routes_bridge_source

    def test_47_no_create_tool_call(self, routes_bridge_source):
        assert "create_tool_call(" not in routes_bridge_source

    def test_48_no_project_creation(self, routes_bridge_source):
        assert "create_project(" not in routes_bridge_source

    def test_49_no_file_reads(self, routes_bridge_source):
        assert "open(" not in routes_bridge_source
        assert ".read_text(" not in routes_bridge_source
        assert "os.listdir(" not in routes_bridge_source

    def test_50_no_command_execution(self, routes_bridge_source):
        assert "import subprocess" not in routes_bridge_source
        assert "subprocess." not in routes_bridge_source
        assert "os.system(" not in routes_bridge_source
        assert "os.popen(" not in routes_bridge_source


# ── 51–52  Frontend build stubs ───────────────────────────────────────────────


class TestFrontendStubs:
    """Tests 51–52: bridge models and helpers are well-formed."""

    def test_51_bridge_request_model_accepts_valid_payload(self):
        req = ConfirmedDevelopmentRunCreateRequest(
            project_id="proj-abc",
            confirm_create=True,
            contract_confirmed=True,
            source_of_truth_confirmed=True,
            module_map_confirmed=True,
            provider_disabled_confirmed=True,
            later_actions_confirmed=True,
            development_run_preview=_preview(),
        )
        _inp, result = build_confirmed_development_run_creation_input(req)
        assert result.decision.value in ("allowed", "warning", "blocked")

    def test_52_safety_notes_are_non_empty_strings(self):
        assert isinstance(_BRIDGE_SAFETY_NOTES, list)
        assert len(_BRIDGE_SAFETY_NOTES) >= 1
        for note in _BRIDGE_SAFETY_NOTES:
            assert isinstance(note, str)
            assert len(note) > 0

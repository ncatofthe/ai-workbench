"""Intake Run -> Agent Assignment & Step Context Fastlane v1 tests.

Verifies intake-origin pending runs are agent-prep actionable without starting
execution, calling providers, creating tool calls, or mutating runtime state from
read-only context endpoints.
"""

from __future__ import annotations

import inspect
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.agents.registry import canonical_agent_id_for_role, get_agent
from src.orchestrator.project_intake import (
    build_pending_run_step_inputs_from_development_preview,
    normalize_development_run_step_context,
)
from src.storage import database


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "agent-step-context.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "agent-ready-saas"
    project_dir.mkdir()
    return isolated_db.create_project(
        name="Agent Ready SaaS",
        path=str(project_dir),
        stack="FastAPI, React, SQLite",
        test_command="pytest",
    )


def _development_preview(steps: list[dict] | None = None) -> dict:
    return {
        "preview_only": True,
        "mode": "existing_project",
        "run_title": "Prepare controlled development run",
        "run_goal": "Make the existing task manager ready for guarded agent work.",
        "recommended_run_mode": "guided",
        "steps": steps
        or [
            {
                "id": "STEP-001",
                "title": "Confirm project context",
                "description": "Confirm Source of Truth and Module Map before any implementation.",
                "agent_role": "product_analyst",
                "requirement_ids": ["REQ-001", "REQ-002"],
                "module_ids": ["frontend_ui", "backend_api"],
                "depends_on": [],
                "expected_outputs": ["confirmed context summary"],
                "validation_steps": ["Verify Source of Truth is present"],
                "safety_gates": ["No provider call", "No execution"],
                "manual_approval_required": False,
                "provider_allowed": False,
                "risk_level": "low",
                "estimated_order": 1,
            },
            {
                "id": "STEP-002",
                "title": "Prepare auth workflow patch candidate",
                "description": "Identify a first safe auth workflow patch candidate.",
                "agent_role": "backend_agent",
                "requirement_ids": ["REQ-003"],
                "module_ids": ["auth_access", "database_schema"],
                "depends_on": ["STEP-001"],
                "expected_outputs": ["manual patch draft plan"],
                "validation_steps": ["List affected auth/database tests"],
                "safety_gates": ["Manual approval required", "Guard review before proposal"],
                "manual_approval_required": True,
                "provider_allowed": False,
                "risk_level": "high",
                "estimated_order": 2,
            },
        ],
        "validation": {
            "ready_to_create_run": True,
            "readiness": "ready",
            "errors": [],
            "warnings": [],
            "missing_inputs": [],
            "blocked_reasons": [],
        },
    }


def _bridge_payload(project_id: str, preview: dict | None = None) -> dict:
    return {
        "project_id": project_id,
        "confirm_create": True,
        "contract_confirmed": True,
        "source_of_truth_confirmed": True,
        "module_map_confirmed": True,
        "provider_disabled_confirmed": True,
        "later_actions_confirmed": True,
        "development_run_preview": preview or _development_preview(),
        "preferred_run_mode": "guided",
    }


def _post_bridge(client: TestClient, project_id: str, preview: dict | None = None) -> dict:
    resp = client.post(
        "/api/project-intake/confirmed-development-run/create",
        json=_bridge_payload(project_id, preview),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    return body


def _context_block(
    *,
    agent_role: str = "backend_agent",
    requirement_ids: list[str] | None = None,
    module_ids: list[str] | None = None,
    depends_on: list[str] | None = None,
    safety_gates: list[str] | None = None,
    manual_approval_required: bool = False,
    provider_allowed: bool = False,
    expected_outputs: list[str] | None = None,
    validation_steps: list[str] | None = None,
) -> str:
    def _join(values: list[str] | None, sep: str = ", ") -> str:
        return sep.join(values or []) if values else "none"

    return "\n".join(
        [
            "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
            "- source: intake_confirmed_development_run",
            f"- agent_role: {agent_role}",
            f"- requirement_ids: {_join(['REQ-001'] if requirement_ids is None else requirement_ids)}",
            f"- module_ids: {_join(['backend_api'] if module_ids is None else module_ids)}",
            f"- depends_on: {_join(depends_on)}",
            f"- safety_gates: {_join(safety_gates or ['No provider call'], '; ')}",
            f"- manual_approval_required: {str(manual_approval_required).lower()}",
            f"- provider_allowed: {str(provider_allowed).lower()}",
            f"- expected_outputs: {_join(expected_outputs or ['agent prep summary'], '; ')}",
            f"- validation_steps: {_join(validation_steps or ['Review dry-run context'], '; ')}",
            "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        ]
    )


def _tool_call_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    finally:
        conn.close()


def _run_step_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM run_steps").fetchone()[0]
    finally:
        conn.close()


class TestContextParsing:
    def test_01_parses_development_run_context_block(self):
        ctx = normalize_development_run_step_context(_context_block())
        assert ctx.source == "intake_confirmed_development_run"
        assert ctx.agent_role == "backend_agent"
        assert ctx.requirement_ids == ["REQ-001"]
        assert ctx.module_ids == ["backend_api"]

    def test_02_missing_context_block_does_not_crash(self):
        ctx = normalize_development_run_step_context("Implement the next step manually.")
        assert ctx.source == "unknown"
        assert ctx.canonical_agent_id

    def test_03_malformed_context_block_does_not_crash(self):
        ctx = normalize_development_run_step_context(
            "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT\n- provider_allowed:\nnot yaml"
        )
        assert ctx.provider_allowed is False
        assert ctx.next_safe_action

    def test_04_provider_allowed_defaults_false(self):
        ctx = normalize_development_run_step_context("No context")
        assert ctx.provider_allowed is False

    def test_05_requirement_ids_are_bounded(self):
        ids = [f"REQ-{i:03d}" for i in range(40)]
        ctx = normalize_development_run_step_context(_context_block(requirement_ids=ids))
        assert len(ctx.requirement_ids) <= 20

    def test_06_module_ids_are_bounded(self):
        ids = [f"module_{i}" for i in range(40)]
        ctx = normalize_development_run_step_context(_context_block(module_ids=ids))
        assert len(ctx.module_ids) <= 20

    def test_07_safety_gates_are_bounded(self):
        gates = [f"Gate {i}" for i in range(40)]
        ctx = normalize_development_run_step_context(_context_block(safety_gates=gates))
        assert len(ctx.safety_gates) <= 8


class TestCanonicalAgentAssignment:
    def test_08_backend_role_maps_to_backend_developer(self):
        assert canonical_agent_id_for_role("backend_agent") == "backend-developer"

    def test_09_frontend_role_maps_to_frontend_developer(self):
        assert canonical_agent_id_for_role("frontend_agent") == "frontend-developer"

    def test_10_qa_role_maps_to_qa_expert(self):
        assert canonical_agent_id_for_role("qa_agent") == "qa-expert"

    def test_11_security_role_maps_to_canonical_security_agent(self):
        agent_id = canonical_agent_id_for_role("security_guard_agent")
        assert agent_id in {"security-auditor", "security-reviewer"}
        assert get_agent(agent_id)

    def test_12_unknown_role_maps_to_safe_fallback(self):
        assert canonical_agent_id_for_role("unknown_future_role") in {"fullstack-developer", "orchestrator"}

    def test_13_mapping_is_deterministic(self):
        assert canonical_agent_id_for_role("backend_agent") == canonical_agent_id_for_role("backend_agent")


class TestAgentStepContextEndpoint:
    @pytest.fixture(autouse=True)
    def _created_run(self, client, project):
        self.body = _post_bridge(client, project.id)
        self.run_id = self.body["run_id"]
        self.client = client

    def _get(self):
        resp = self.client.get(f"/api/runs/{self.run_id}/agent-step-context")
        assert resp.status_code == 200
        return resp.json()

    def test_14_endpoint_returns_200(self):
        body = self._get()
        assert body["run_id"] == self.run_id

    def test_15_returns_one_item_per_step(self):
        body = self._get()
        assert body["total_steps"] == len(self.body["steps"])
        assert len(body["items"]) == len(self.body["steps"])

    def test_16_computes_total_ready_blocked_counts(self):
        body = self._get()
        assert body["total_steps"] == 2
        assert body["ready_steps"] >= 1
        assert body["blocked_steps"] == 0

    def test_17_recommends_first_ready_pending_step(self):
        body = self._get()
        assert "Confirm project context" in body["next_recommended_action"]
        assert "No provider call" in body["next_recommended_action"]

    def test_18_provider_allowed_true_blocks_readiness(self, isolated_db):
        run = isolated_db.get_run(self.run_id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="Unsafe provider step",
            agent_id="backend-developer",
            input=_context_block(provider_allowed=True),
        )
        resp = self.client.get(f"/api/runs/{self.run_id}/agent-step-context")
        body = resp.json()
        item = next(i for i in body["items"] if i["step_id"] == step.id)
        assert item["ready_for_agent_execution"] is False
        assert any("provider_allowed=true" in b for b in item["blockers"])

    def test_19_missing_requirement_links_warn(self, isolated_db):
        run = isolated_db.get_run(self.run_id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="No requirement link",
            agent_id="backend-developer",
            input=_context_block(requirement_ids=[]),
        )
        item = next(i for i in self._get()["items"] if i["step_id"] == step.id)
        assert any("No requirement links" in w for w in item["warnings"])

    def test_20_missing_module_links_warn(self, isolated_db):
        run = isolated_db.get_run(self.run_id)
        step = isolated_db.create_run_step(
            run_id=run.id,
            title="No module link",
            agent_id="backend-developer",
            input=_context_block(module_ids=[]),
        )
        item = next(i for i in self._get()["items"] if i["step_id"] == step.id)
        assert any("No module links" in w for w in item["warnings"])

    def test_21_endpoint_creates_no_tool_calls(self):
        before = _tool_call_count()
        self._get()
        assert _tool_call_count() == before

    def test_22_endpoint_calls_no_providers(self, monkeypatch):
        import src.api.routes as routes

        def fail_provider_call(*args, **kwargs):  # pragma: no cover - should never run
            raise AssertionError("provider call attempted")

        monkeypatch.setattr(routes, "route_model", fail_provider_call)
        self._get()

    def test_23_endpoint_starts_no_execution(self, isolated_db):
        before = [s.status for s in isolated_db.list_run_steps(self.run_id)]
        self._get()
        after = [s.status for s in isolated_db.list_run_steps(self.run_id)]
        assert after == before == ["pending", "pending"]

    def test_24_no_db_writes_beyond_fixture_setup(self):
        before_steps = _run_step_count()
        before_tools = _tool_call_count()
        self._get()
        assert _run_step_count() == before_steps
        assert _tool_call_count() == before_tools


class TestBridgeCompatibility:
    def test_25_bridge_created_steps_parse_correctly(self):
        metas = build_pending_run_step_inputs_from_development_preview(_development_preview())
        contexts = [normalize_development_run_step_context(m["input_text"]) for m in metas]
        assert all(ctx.source == "intake_confirmed_development_run" for ctx in contexts)

    def test_26_created_contexts_preserve_requirement_ids(self):
        meta = build_pending_run_step_inputs_from_development_preview(_development_preview())[0]
        ctx = normalize_development_run_step_context(meta["input_text"])
        assert ctx.requirement_ids == ["REQ-001", "REQ-002"]

    def test_27_created_contexts_preserve_module_ids(self):
        meta = build_pending_run_step_inputs_from_development_preview(_development_preview())[1]
        ctx = normalize_development_run_step_context(meta["input_text"])
        assert ctx.module_ids == ["auth_access", "database_schema"]

    def test_28_created_contexts_preserve_safety_gates(self):
        meta = build_pending_run_step_inputs_from_development_preview(_development_preview())[1]
        ctx = normalize_development_run_step_context(meta["input_text"])
        assert "Manual approval required" in ctx.safety_gates

    def test_29_created_contexts_preserve_agent_roles(self):
        meta = build_pending_run_step_inputs_from_development_preview(_development_preview())[1]
        ctx = normalize_development_run_step_context(meta["input_text"])
        assert ctx.agent_role == "backend_agent"

    def test_30_created_contexts_resolve_canonical_ids(self):
        meta = build_pending_run_step_inputs_from_development_preview(_development_preview())[1]
        ctx = normalize_development_run_step_context(meta["input_text"])
        assert ctx.canonical_agent_id == "backend-developer"


class TestOperatorQueueIntegration:
    @pytest.fixture(autouse=True)
    def _created_run(self, client, project):
        body = _post_bridge(client, project.id)
        self.run_id = body["run_id"]
        self.client = client

    def test_31_operator_queue_includes_agent_ready_context(self):
        resp = self.client.get(f"/api/runs/{self.run_id}/operator-queue")
        assert resp.status_code == 200
        body = resp.json()
        assert any(item["action_type"] == "prepare_agent_step" for item in body["items"])

    def test_32_queue_action_does_not_auto_execute(self, isolated_db):
        self.client.get(f"/api/runs/{self.run_id}/operator-queue")
        assert [s.status for s in isolated_db.list_run_steps(self.run_id)] == ["pending", "pending"]

    def test_33_queue_action_creates_no_tool_calls(self):
        before = _tool_call_count()
        self.client.get(f"/api/runs/{self.run_id}/operator-queue")
        assert _tool_call_count() == before


class TestFrontendStaticSurface:
    @pytest.fixture(scope="class")
    def run_detail_source(self):
        return (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text()

    def test_34_rundetail_contains_agent_step_context_ui_label(self, run_detail_source):
        assert "Agent Step Context" in run_detail_source

    def test_35_ui_text_makes_read_only_nature_clear(self, run_detail_source):
        assert "Read-only agent-prep summary" in run_detail_source
        assert "does not start execution" in run_detail_source

    def test_36_ui_section_has_no_hidden_execute_or_start_button(self, run_detail_source):
        section = run_detail_source.split("function AgentStepContextPanel", 1)[1].split("// ── Operator Queue Panel", 1)[0]
        assert "runAgentExecution(" not in section
        assert "Start Execution" not in section
        assert "executeRun(" not in section


class TestSafetyStaticScan:
    def test_37_no_execute_run_added_to_new_context_helpers(self):
        import src.api.routes as routes

        source = inspect.getsource(normalize_development_run_step_context)
        source += inspect.getsource(routes.get_run_agent_step_context)
        assert "execute_run(" not in source

    def test_38_no_asyncio_create_task_added_to_new_context_helpers(self):
        import src.api.routes as routes

        source = inspect.getsource(normalize_development_run_step_context)
        source += inspect.getsource(routes.get_run_agent_step_context)
        assert "asyncio.create_task" not in source

    def test_39_no_provider_calls_added_to_new_context_helpers(self):
        import src.api.routes as routes

        source = inspect.getsource(normalize_development_run_step_context)
        source += inspect.getsource(routes.get_run_agent_step_context)
        assert "route_model(" not in source
        assert "chat_completion" not in source

    def test_40_no_create_tool_call_added_to_new_context_helpers(self):
        import src.api.routes as routes

        source = inspect.getsource(normalize_development_run_step_context)
        source += inspect.getsource(routes.get_run_agent_step_context)
        assert "create_tool_call(" not in source

    def test_41_no_file_reads_added_to_context_parser(self):
        source = inspect.getsource(normalize_development_run_step_context)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source
        assert "os.listdir" not in source

    def test_42_no_command_execution_added_to_context_parser(self):
        source = inspect.getsource(normalize_development_run_step_context)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_43_database_source_is_not_part_of_this_feature(self):
        feature_files = [
            REPO_ROOT / "backend/src/orchestrator/project_intake.py",
            REPO_ROOT / "backend/src/api/routes.py",
            REPO_ROOT / "frontend/src/pages/RunDetail.tsx",
        ]
        combined = "\n".join(path.read_text() for path in feature_files)
        assert "ALTER TABLE" not in combined


class TestCompatibilityAnchors:
    def test_44_confirmed_bridge_endpoint_still_exists(self):
        routes_source = (REPO_ROOT / "backend/src/api/routes.py").read_text()
        assert "/api/project-intake/confirmed-development-run/create" in routes_source

    def test_45_model_router_alignment_test_file_still_exists(self):
        assert (REPO_ROOT / "backend/tests/test_model_router_agent_alignment.py").exists()

    def test_46_agent_execution_harness_test_file_still_exists(self):
        assert (REPO_ROOT / "backend/tests/test_agent_execution_harness.py").exists()

    def test_47_full_backend_compatibility_is_checked_in_phase_7(self):
        assert (REPO_ROOT / "backend/tests/test_project_context_cockpit.py").exists()

    def test_48_frontend_type_exports_agent_step_context(self):
        types_source = (REPO_ROOT / "frontend/src/types/index.ts").read_text()
        assert "RunAgentStepContextResponse" in types_source
        assert "prepare_agent_step" in types_source

    def test_49_frontend_client_exposes_read_only_endpoint(self):
        client_source = (REPO_ROOT / "frontend/src/api/client.ts").read_text()
        assert "getRunAgentStepContext" in client_source
        assert "/agent-step-context" in client_source

    def test_50_scripts_runner_remains_separate_from_this_feature(self):
        script_source = (REPO_ROOT / "scripts/run_tests.sh").read_text()
        assert "agent-step-context" not in script_source

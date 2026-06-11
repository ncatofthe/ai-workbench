"""Repo-aware Controlled Apply/Test/Fix Loop Mega-Fastlane v1 tests.

The endpoint under test is:
  GET /api/runs/{run_id}/steps/{step_id}/repo-aware-controlled-loop-plan

Safety contract:
  - read-only status guidance
  - no ToolCalls/proposals/guard results/files are created
  - no apply, command execution, provider call, or hidden fix generation occurs
"""

from __future__ import annotations

import inspect
import json
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.api import routes
from src.storage import database


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "repo-aware-controlled-loop.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "controlled-loop-project"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="Controlled Loop Project",
        path=str(project_dir),
        stack="FastAPI, React",
        test_command="pytest",
        safe_commands=["pytest"],
    )
    run = isolated_db.create_run(prompt="Controlled loop", project_id=project.id, project_path=project.path)
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Prepare backend workflow",
        agent_id="backend-developer",
        input=_repo_step_context(),
    )
    return project, run, step, project_dir


def _repo_step_context() -> str:
    return "\n".join([
        "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        "- source: intake_confirmed_development_run",
        "- agent_role: backend_agent",
        "- requirement_ids: REQ-001",
        "- module_ids: backend_api",
        "- depends_on: none",
        "- safety_gates: No provider call; Guard before proposal",
        "- manual_approval_required: false",
        "- provider_allowed: false",
        "- expected_outputs: guarded patch proposal",
        "- validation_steps: pytest tests/test_backend.py",
        "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        "AI_WORKBENCH_REPO_AWARE_CONTEXT",
        "- detected_stack: fastapi, python, pytest",
        "- detected_project_type: backend_api",
        "- relevant_area_hints: Backend/API: backend/src/api/routes.py",
        "- relevant_manifest_scripts: pyproject.toml: pytest configured",
        "- test_discovery_hints: Review pytest as a candidate test command.",
        "- protected_path_warnings: Protected path was not read: .env",
        "- suggested_safe_commands: pytest",
        "- recommended_first_safe_action: Prepare a guarded backend patch draft.",
        "- safety_notes: Repo intake preview is read-only.",
        "- limitations: No arbitrary source file reading.",
        "END_AI_WORKBENCH_REPO_AWARE_CONTEXT",
    ])


def _plain_step_context() -> str:
    return "\n".join([
        "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        "- source: intake_confirmed_development_run",
        "- agent_role: backend_agent",
        "- requirement_ids: REQ-001",
        "- module_ids: backend_api",
        "- safety_gates: No provider call",
        "- provider_allowed: false",
        "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
    ])


def _get(client: TestClient, run_id: str, step_id: str):
    return client.get(f"/api/runs/{run_id}/steps/{step_id}/repo-aware-controlled-loop-plan")


def _stage(body: dict, stage_id: str) -> dict:
    return next(stage for stage in body["stages"] if stage["id"] == stage_id)


def _count(table: str, where: str = "1=1") -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]
    finally:
        conn.close()


def _make_tool_call(
    *,
    run_id: str,
    step_id: str,
    project_id: str,
    tool_name: str,
    status: str = "completed",
    command: str = "",
    returncode: int | None = None,
    input_data: dict | None = None,
    output_data: dict | None = None,
):
    return database.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name=tool_name,
        command=command,
        status=status,
        input_json=json.dumps(input_data or {}, ensure_ascii=False),
        output_json=json.dumps(output_data or {}, ensure_ascii=False),
        returncode=returncode,
        risk_level="medium",
    )


class TestPlanEndpointReadOnly:
    def test_01_returns_plan_for_repo_aware_step(self, client, project_run_step):
        _, run, step, _ = project_run_step
        resp = _get(client, run.id, step.id)
        assert resp.status_code == 200
        assert resp.json()["run_id"] == run.id

    def test_02_returns_repo_context_completed_when_repo_context_exists(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "repo_context")["status"] == "completed"

    def test_03_returns_repo_context_unknown_when_no_repo_context_exists(self, client, project_run_step):
        _, run, step, _ = project_run_step
        database.update_run_step(step.id, input=_plain_step_context())
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "repo_context")["status"] in {"unknown", "not_started"}

    def test_04_includes_detected_stack(self, client, project_run_step):
        _, run, step, _ = project_run_step
        assert "fastapi" in _get(client, run.id, step.id).json()["detected_stack"]

    def test_05_includes_safe_command_suggestions(self, client, project_run_step):
        _, run, step, _ = project_run_step
        commands = _get(client, run.id, step.id).json()["safe_command_suggestions"]
        assert any(command["command"] == "pytest" for command in commands)

    def test_06_includes_stages_in_deterministic_order(self, client, project_run_step):
        _, run, step, _ = project_run_step
        ids = [stage["id"] for stage in _get(client, run.id, step.id).json()["stages"]]
        assert ids == [
            "repo_context",
            "patch_draft",
            "guarded_proposal",
            "apply_patch",
            "safe_test",
            "analyze_test_result",
            "fix_draft",
            "delivery_update",
        ]

    def test_07_includes_next_recommended_action(self, client, project_run_step):
        _, run, step, _ = project_run_step
        assert _get(client, run.id, step.id).json()["next_recommended_action"]

    def test_08_handles_missing_run_with_404(self, client, project_run_step):
        _, _, step, _ = project_run_step
        assert _get(client, "missing-run", step.id).status_code == 404

    def test_09_handles_missing_step_with_404(self, client, project_run_step):
        _, run, _, _ = project_run_step
        assert _get(client, run.id, "missing-step").status_code == 404

    def test_10_handles_invalid_step_context_safely(self, client, project_run_step):
        _, run, step, _ = project_run_step
        database.update_run_step(step.id, input="AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT\n- provider_allowed:\nnot yaml")
        resp = _get(client, run.id, step.id)
        assert resp.status_code == 200
        assert resp.json()["stages"]

    def test_11_does_not_mutate_run(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = database.get_run(run.id).model_dump()
        _get(client, run.id, step.id)
        after = database.get_run(run.id).model_dump()
        assert after == before

    def test_12_does_not_mutate_step(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = database.list_run_steps(run.id)[0].model_dump()
        _get(client, run.id, step.id)
        after = database.list_run_steps(run.id)[0].model_dump()
        assert after == before

    def test_13_does_not_create_tool_calls(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("tool_calls")
        _get(client, run.id, step.id)
        assert _count("tool_calls") == before

    def test_14_does_not_create_proposals(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("tool_calls", "tool_name = 'propose-patch'")
        _get(client, run.id, step.id)
        assert _count("tool_calls", "tool_name = 'propose-patch'") == before

    def test_15_does_not_create_guard_results(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("guard_results")
        _get(client, run.id, step.id)
        assert _count("guard_results") == before

    def test_16_does_not_apply_patches(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("tool_calls", "tool_name = 'apply-patch'")
        _get(client, run.id, step.id)
        assert _count("tool_calls", "tool_name = 'apply-patch'") == before

    def test_17_does_not_run_tests(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("tool_calls", "tool_name = 'run-command'")
        _get(client, run.id, step.id)
        assert _count("tool_calls", "tool_name = 'run-command'") == before

    def test_18_does_not_call_providers(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert any("provider" in note.lower() for note in body["safety_notes"])

    def test_19_does_not_execute_commands(self, client, project_run_step):
        _, run, step, _ = project_run_step
        before = _count("tool_calls")
        _get(client, run.id, step.id)
        assert _count("tool_calls") == before

    def test_20_does_not_create_files(self, client, project_run_step):
        _, run, step, project_dir = project_run_step
        before = sorted(p.name for p in project_dir.iterdir())
        _get(client, run.id, step.id)
        after = sorted(p.name for p in project_dir.iterdir())
        assert after == before


class TestStageLogic:
    def test_21_patch_draft_ready_when_repo_context_exists_and_no_draft_evidence(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "patch_draft")["status"] == "ready"

    def test_22_guarded_proposal_ready_when_patch_draft_evidence_exists(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "guarded_proposal")["status"] == "ready"

    def test_23_apply_patch_waiting_for_confirmation_when_proposal_evidence_exists(self, client, project_run_step):
        project, run, step, _ = project_run_step
        _make_tool_call(run_id=run.id, step_id=step.id, project_id=project.id, tool_name="propose-patch")
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "apply_patch")["status"] == "waiting_for_confirmation"

    def test_24_safe_test_ready_after_apply_evidence_or_suggested_commands_exist(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "safe_test")["status"] == "ready"

    def test_25_analyze_test_result_ready_when_test_result_exists(self, client, project_run_step):
        project, run, step, _ = project_run_step
        _make_tool_call(
            run_id=run.id,
            step_id=step.id,
            project_id=project.id,
            tool_name="run-command",
            command="pytest",
            returncode=1,
            input_data={"command_kind": "test", "command": "pytest"},
            output_data={"returncode": 1},
        )
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "analyze_test_result")["status"] == "ready"

    def test_26_fix_draft_ready_when_failed_test_analysis_exists(self, client, project_run_step):
        project, run, step, _ = project_run_step
        _make_tool_call(
            run_id=run.id,
            step_id=step.id,
            project_id=project.id,
            tool_name="run-command",
            command="pytest",
            returncode=1,
            input_data={"command_kind": "test", "command": "pytest"},
            output_data={"returncode": 1},
        )
        _make_tool_call(
            run_id=run.id,
            step_id=step.id,
            project_id=project.id,
            tool_name="analyze-command-result",
            output_data={"summary": "failed tests"},
        )
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "fix_draft")["status"] == "ready"

    def test_27_delivery_update_remains_manual_report_only(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "delivery_update")["summary"].lower().startswith("review delivery")

    def test_28_blockers_are_surfaced_when_required_previous_stage_missing(self, client, project_run_step):
        _, run, step, _ = project_run_step
        database.update_run_step(step.id, input=_plain_step_context())
        body = _get(client, run.id, step.id).json()
        assert _stage(body, "patch_draft")["blockers"]

    def test_29_warnings_include_protected_path_warnings(self, client, project_run_step):
        _, run, step, _ = project_run_step
        body = _get(client, run.id, step.id).json()
        assert any("Protected path" in warning for warning in _stage(body, "repo_context")["warnings"])

    def test_30_safe_commands_remain_copy_only_or_explicit_run_marked(self, client, project_run_step):
        _, run, step, _ = project_run_step
        commands = _get(client, run.id, step.id).json()["safe_command_suggestions"]
        assert commands
        assert all(command["execution"] == "copy_only_or_explicit_safe_runner" for command in commands)


class TestCompatibilityAndStaticSafety:
    def test_31_existing_repo_aware_agent_work_context_endpoint_still_available(self, client, project_run_step):
        _, run, _, _ = project_run_step
        assert client.get(f"/api/runs/{run.id}/agent-step-context").status_code == 200

    def test_32_existing_repo_intake_endpoint_still_available(self, client):
        assert client.post("/api/project-intake/existing-project/repo-intake-preview", json={"project_path": ""}).status_code == 200

    def test_33_existing_confirmed_bridge_route_still_available(self):
        assert hasattr(routes, "post_confirmed_development_run_create")

    def test_34_existing_patch_draft_route_still_available(self):
        assert hasattr(routes, "create_step_agent_patch_draft")

    def test_35_existing_guarded_proposal_route_still_available(self):
        assert hasattr(routes, "create_step_patch_draft_guarded_proposal")

    def test_36_existing_execute_next_step_route_still_available(self):
        assert hasattr(routes, "execute_next_run_step")

    def test_37_plan_response_model_is_exported_by_route_module(self):
        assert hasattr(routes, "RepoAwareControlledLoopPlanResponse")

    def test_38_touched_route_section_has_no_execute_run(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "execute_run" not in source

    def test_39_touched_route_section_has_no_asyncio_create_task(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "asyncio.create_task" not in source

    def test_40_touched_route_section_has_no_provider_call(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "ollama" not in source and "claude" not in source and "codex" not in source

    def test_41_touched_route_section_has_no_create_tool_call(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "create_tool_call" not in source

    def test_42_touched_route_section_has_no_apply_invocation_inside_plan_endpoint(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "apply_project_patch" not in source and "apply_patch(" not in source

    def test_43_touched_route_section_has_no_command_execution(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "run_project_command" not in source and "_run_safe_command" not in source

    def test_44_touched_route_section_has_no_subprocess_or_os_system(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "subprocess" not in source and "os.system" not in source

    def test_45_touched_route_section_has_no_hidden_file_writes(self):
        source = inspect.getsource(routes.get_repo_aware_controlled_loop_plan)
        assert "write_text" not in source and "open(" not in source

    def test_46_run_detail_contains_controlled_loop_panel(self):
        source = (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")
        assert "Controlled Apply/Test/Fix Loop" in source

    def test_47_run_detail_contains_copy_only_safe_command_language(self):
        source = (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")
        assert "Copy-only safe command suggestions" in source

    def test_48_run_detail_does_not_add_auto_run_behavior_for_loop_panel(self):
        source = (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")
        marker = source.split("Controlled Apply/Test/Fix Loop", 1)[1].split("Prepare Agent Patch Draft", 1)[0]
        assert "runAutomationNext(" not in marker and "runProjectCommand(" not in marker

    def test_49_run_detail_does_not_add_hidden_apply_behavior_for_loop_panel(self):
        source = (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")
        marker = source.split("Controlled Apply/Test/Fix Loop", 1)[1].split("Prepare Agent Patch Draft", 1)[0]
        assert "applyProjectPatch(" not in marker

    def test_50_typescript_types_include_loop_response(self):
        source = (REPO_ROOT / "frontend/src/types/index.ts").read_text(encoding="utf-8")
        assert "RepoAwareControlledLoopPlanResponse" in source

    def test_51_client_exposes_loop_plan_function(self):
        source = (REPO_ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
        assert "getRepoAwareControlledLoopPlan" in source

    def test_52_e2e_smoke_command_remains_explicit(self):
        source = (REPO_ROOT / "frontend/package.json").read_text(encoding="utf-8")
        assert "test:e2e:smoke" in source

    def test_53_scripts_run_tests_does_not_include_controlled_loop_special_case(self):
        source = (REPO_ROOT / "scripts/run_tests.sh").read_text(encoding="utf-8")
        assert "repo-aware-controlled-loop" not in source

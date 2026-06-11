"""Step -> Agent Patch Draft Fastlane v1 tests.

The endpoint under test is:
  POST /api/runs/{run_id}/steps/{step_id}/agent-patch-draft

Safety contract:
  - draft-only, no apply, no proposal, no test run
  - no provider calls
  - no tool_calls created
  - no file reads or command execution
"""

from __future__ import annotations

import inspect
import pathlib
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import (
    build_step_agent_patch_draft,
    normalize_development_run_step_context,
)
from src.storage import database


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "step-agent-patch-draft.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "patch-draft-project"
    project_dir.mkdir()
    project = isolated_db.create_project(
        name="Patch Draft Project",
        path=str(project_dir),
        stack="FastAPI, React",
        test_command="pytest",
    )
    run = isolated_db.create_run(prompt="Prepare patch draft", project_id=project.id, project_path=project.path)
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement backend task workflow",
        agent_id="backend-developer",
        input=_context_block(
            agent_role="backend_agent",
            requirement_ids=["REQ-001", "REQ-002"],
            module_ids=["backend_api", "tasks_workflow"],
            safety_gates=["No provider call", "Guard before proposal"],
            validation_steps=["pytest tests/test_tasks.py"],
        ),
    )
    return project, run, step


def _context_block(
    *,
    agent_role: str = "backend_agent",
    requirement_ids: list[str] | None = None,
    module_ids: list[str] | None = None,
    safety_gates: list[str] | None = None,
    validation_steps: list[str] | None = None,
    manual_approval_required: bool = False,
    provider_allowed: bool = False,
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
            "- depends_on: none",
            f"- safety_gates: {_join(safety_gates or ['No provider call'], '; ')}",
            f"- manual_approval_required: {str(manual_approval_required).lower()}",
            f"- provider_allowed: {str(provider_allowed).lower()}",
            "- expected_outputs: patch draft candidate",
            f"- validation_steps: {_join(validation_steps or ['Review guarded proposal manually'], '; ')}",
            "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        ]
    )


def _step(
    *,
    title: str = "Implement backend task workflow",
    status: str = "pending",
    input_text: str | None = None,
):
    return SimpleNamespace(
        id="step-test",
        title=title,
        status=status,
        input=input_text if input_text is not None else _context_block(),
    )


def _draft_for(agent_role: str, module_ids: list[str], **kwargs):
    step = _step(input_text=_context_block(agent_role=agent_role, module_ids=module_ids, **kwargs))
    return build_step_agent_patch_draft(run_id="run-test", step=step)


def _tool_call_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    finally:
        conn.close()


class TestBuilderBehavior:
    def test_01_builds_draft_for_backend_step(self):
        draft = _draft_for("backend_agent", ["backend_api"])
        assert "backend/src" in draft.suggested_file_path
        assert draft.canonical_agent_id == "backend-developer"

    def test_02_builds_draft_for_frontend_step(self):
        draft = _draft_for("frontend_agent", ["frontend_ui"])
        assert any(path.startswith("frontend/src") for path in draft.target_files)

    def test_03_builds_draft_for_qa_step(self):
        draft = _draft_for("qa_agent", ["tests_quality"])
        assert any(path.startswith("tests/") for path in draft.target_files)

    def test_04_preserves_requirement_ids(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step())
        assert draft.requirement_ids == ["REQ-001"]

    def test_05_preserves_module_ids(self):
        draft = _draft_for("backend_agent", ["backend_api", "tasks_workflow"])
        assert draft.module_ids == ["backend_api", "tasks_workflow"]

    def test_06_preserves_canonical_agent_id(self):
        draft = _draft_for("frontend_agent", ["frontend_ui"])
        assert draft.canonical_agent_id == "frontend-developer"

    def test_07_provider_allowed_true_blocks_draft_readiness(self):
        draft = _draft_for("backend_agent", ["backend_api"], provider_allowed=True)
        assert draft.ready_for_proposal is False
        assert any("provider_allowed=true" in blocker for blocker in draft.blockers)

    def test_08_non_pending_step_blocks_draft_readiness(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step(status="completed"))
        assert draft.ready_for_proposal is False
        assert any("completed" in blocker for blocker in draft.blockers)

    def test_09_missing_context_does_not_crash(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step(input_text="No context block"))
        assert draft.step_id == "step-test"
        assert draft.blockers

    def test_10_malformed_context_does_not_crash(self):
        draft = build_step_agent_patch_draft(
            run_id="run",
            step=_step(input_text="AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT\n- provider_allowed:\n"),
        )
        assert draft.safety_notes

    def test_11_output_is_bounded(self):
        huge = {
            "summary": "S" * 5000,
            "analysis": "A" * 5000,
            "patch_intent": "P" * 5000,
            "proposed_files": [f"backend/src/file_{i}.py" for i in range(50)],
            "risks": [f"risk {i}" for i in range(50)],
            "test_suggestions": [f"test {i}" for i in range(50)],
        }
        draft = build_step_agent_patch_draft(
            run_id="run",
            step=_step(),
            agent_result=huge,
            max_target_files=3,
            max_risks=3,
            max_validation_steps=3,
        )
        assert len(draft.target_files) <= 3
        assert len(draft.risks) <= 3
        assert len(draft.validation_steps) <= 3
        assert len(draft.patch_intent) <= 800

    def test_12_old_text_remains_empty_when_file_not_read(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step())
        assert draft.suggested_old_text == ""
        assert any("no file content was read" in warning.lower() for warning in draft.warnings)

    def test_13_no_exact_file_content_is_fabricated(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step())
        assert "current file content" in draft.suggested_new_text.lower()
        assert "def " not in draft.suggested_old_text

    def test_14_validation_steps_are_present(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step())
        assert draft.validation_steps

    def test_15_risks_are_present(self):
        draft = _draft_for("backend_agent", ["auth_access"])
        assert draft.risks

    def test_16_next_recommended_action_present(self):
        draft = build_step_agent_patch_draft(run_id="run", step=_step())
        assert draft.next_recommended_action


class TestTargetInference:
    def test_17_backend_role_suggests_backend_path_hint(self):
        assert _draft_for("backend_agent", ["backend_api"]).suggested_file_path.startswith("backend/src")

    def test_18_frontend_role_suggests_frontend_path_hint(self):
        assert _draft_for("frontend_agent", ["frontend_ui"]).suggested_file_path.startswith("frontend/src")

    def test_19_qa_role_suggests_tests_path_hint(self):
        assert _draft_for("qa_agent", ["tests_quality"]).suggested_file_path.startswith("tests/")

    def test_20_database_role_requires_manual_approval_warning(self):
        draft = _draft_for("database_agent", ["database_schema"])
        joined = " ".join(draft.warnings + draft.risks).lower()
        assert "manual approval" in joined or "database/schema" in joined

    def test_21_security_role_requires_operator_narrowing_or_warning(self):
        draft = _draft_for("security_guard_agent", ["security_review"])
        assert any("security" in warning.lower() for warning in draft.warnings)

    def test_22_unknown_role_blocks_or_requires_operator_note(self):
        step = _step(input_text=_context_block(agent_role="unknown_role", module_ids=[]))
        draft = build_step_agent_patch_draft(run_id="run", step=step)
        assert draft.blockers or not draft.ready_for_proposal


class TestEndpointBehavior:
    def test_23_endpoint_returns_200(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={})
        assert resp.status_code == 200
        assert resp.json()["step_id"] == step.id

    def test_24_bad_run_returns_404(self, client):
        resp = client.post("/api/runs/no-run/steps/no-step/agent-patch-draft", json={})
        assert resp.status_code == 404

    def test_25_bad_step_returns_404(self, client, project_run_step):
        _, run, _ = project_run_step
        resp = client.post(f"/api/runs/{run.id}/steps/no-step/agent-patch-draft", json={})
        assert resp.status_code == 404

    def test_26_step_from_another_run_returns_404(self, client, project_run_step, isolated_db):
        project, _, step = project_run_step
        other_run = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        resp = client.post(f"/api/runs/{other_run.id}/steps/{step.id}/agent-patch-draft", json={})
        assert resp.status_code == 404

    def test_27_endpoint_creates_no_tool_calls(self, client, project_run_step):
        _, run, step = project_run_step
        before = _tool_call_count()
        client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={})
        assert _tool_call_count() == before

    def test_28_endpoint_creates_no_patch_proposal(self, client, project_run_step):
        _, run, step = project_run_step
        client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={})
        assert _tool_call_count() == 0

    def test_29_endpoint_applies_no_patch(self, client, project_run_step):
        project, run, step = project_run_step
        before = pathlib.Path(project.path).glob("*")
        before_names = sorted(path.name for path in before)
        client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={})
        after_names = sorted(path.name for path in pathlib.Path(project.path).glob("*"))
        assert after_names == before_names

    def test_30_endpoint_calls_no_provider(self, client, project_run_step, monkeypatch):
        import src.api.routes as routes

        def fail(*args, **kwargs):  # pragma: no cover
            raise AssertionError("provider call attempted")

        monkeypatch.setattr(routes, "route_model", fail)
        _, run, step = project_run_step
        resp = client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={})
        assert resp.status_code == 200

    def test_31_endpoint_reads_no_files(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        assert "project_read_file" not in source
        assert "open(" not in source
        assert ".read_text(" not in source

    def test_32_endpoint_runs_no_command(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        assert "_run_safe_command" not in source
        assert "subprocess" not in source
        assert "os.system" not in source

    def test_33_endpoint_deterministic_for_same_input(self, client, project_run_step):
        _, run, step = project_run_step
        url = f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft"
        first = client.post(url, json={"operator_note": "Target backend route."}).json()
        second = client.post(url, json={"operator_note": "Target backend route."}).json()
        assert first == second


class TestAgentResultIntegration:
    def test_34_agent_result_summary_included_safely(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft",
            json={"agent_result": {"summary": "Add task workflow route.", "patch_intent": "Update route."}},
        )
        assert "Add task workflow route" in resp.json()["draft_summary"]

    def test_35_large_agent_result_is_bounded(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft",
            json={"agent_result": {"patch_intent": "P" * 5000, "proposed_files": [f"backend/src/{i}.py" for i in range(50)]}},
        )
        body = resp.json()
        assert len(body["patch_intent"]) <= 800
        assert len(body["target_files"]) <= 8

    def test_36_secret_like_agent_result_is_redacted_or_warns(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft",
            json={"agent_result": {"summary": "api_key=supersecret", "patch_intent": "Use safe config."}},
        )
        body = resp.json()
        assert "supersecret" not in str(body)
        assert any("redacted" in warning.lower() for warning in body["warnings"])

    def test_37_operator_note_can_refine_patch_intent(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft",
            json={"operator_note": "Focus only on task status validation."},
        )
        assert "task status validation" in resp.json()["patch_intent"]

    def test_38_operator_note_is_bounded(self, client, project_run_step):
        _, run, step = project_run_step
        resp = client.post(
            f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft",
            json={"operator_note": "N" * 5000},
        )
        assert len(resp.json()["patch_intent"]) <= 800


class TestFrontendStatic:
    @pytest.fixture(scope="class")
    def run_detail_source(self):
        return (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text()

    def test_39_rundetail_contains_prepare_patch_draft_ui(self, run_detail_source):
        assert "Prepare Patch Draft" in run_detail_source

    def test_40_ui_text_says_draft_only_no_apply(self, run_detail_source):
        assert "Draft only" in run_detail_source
        assert "No patch was applied" in run_detail_source

    def test_41_ui_does_not_contain_hidden_apply_handler_for_this_action(self, run_detail_source):
        section = run_detail_source.split("function AgentStepContextPanel", 1)[1].split("// ── Operator Queue Panel", 1)[0]
        assert "applyProjectPatch(" not in section
        assert "runProjectCommand(" not in section

    def test_42_ui_does_not_auto_submit_proposal(self, run_detail_source):
        section = run_detail_source.split("function AgentStepContextPanel", 1)[1].split("// ── Operator Queue Panel", 1)[0]
        assert "proposeProjectPatch(" not in section
        assert "reviewProjectPatch(" not in section


class TestSafetyStatic:
    def test_43_no_execute_run_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        source += inspect.getsource(build_step_agent_patch_draft)
        assert "execute_run(" not in source

    def test_44_no_asyncio_create_task_added(self):
        source = inspect.getsource(build_step_agent_patch_draft)
        assert "asyncio.create_task" not in source

    def test_45_no_provider_calls_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        source += inspect.getsource(build_step_agent_patch_draft)
        assert "route_model(" not in source
        assert "chat_completion" not in source

    def test_46_no_create_tool_call_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        source += inspect.getsource(build_step_agent_patch_draft)
        assert "create_tool_call(" not in source

    def test_47_no_apply_project_patch_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        source += inspect.getsource(build_step_agent_patch_draft)
        assert "apply_project_patch" not in source

    def test_48_no_command_execution_added(self):
        source = inspect.getsource(build_step_agent_patch_draft)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_49_no_file_reads_added_in_endpoint_or_builder(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_agent_patch_draft)
        source += inspect.getsource(build_step_agent_patch_draft)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".read(" not in source

    def test_50_database_schema_not_part_of_feature(self):
        feature_source = "\n".join(
            path.read_text()
            for path in [
                REPO_ROOT / "backend/src/orchestrator/project_intake.py",
                REPO_ROOT / "backend/src/api/routes.py",
            ]
        )
        assert "ALTER TABLE" not in feature_source


class TestCompatibilityAnchors:
    def test_51_intake_run_agent_context_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_intake_run_agent_assignment_step_context.py").exists()

    def test_52_agent_execution_harness_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_agent_execution_harness.py").exists()

    def test_53_agent_result_patch_draft_bridge_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_agent_result_patch_draft_bridge.py").exists()

    def test_54_guarded_patch_proposal_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_guarded_patch_proposal.py").exists()

    def test_55_full_backend_compatibility_is_checked_in_phase_7(self):
        assert (REPO_ROOT / "backend/tests/test_project_context_cockpit.py").exists()

    def test_56_frontend_types_include_step_agent_patch_draft(self):
        types_source = (REPO_ROOT / "frontend/src/types/index.ts").read_text()
        assert "StepAgentPatchDraftResponse" in types_source

    def test_57_frontend_client_exposes_step_agent_patch_draft(self):
        client_source = (REPO_ROOT / "frontend/src/api/client.ts").read_text()
        assert "createStepAgentPatchDraft" in client_source
        assert "agent-patch-draft" in client_source

    def test_58_scripts_runner_remains_unchanged_for_this_feature(self):
        script_source = (REPO_ROOT / "scripts/run_tests.sh").read_text()
        assert "agent-patch-draft" not in script_source

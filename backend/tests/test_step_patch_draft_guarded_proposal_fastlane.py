"""Step Patch Draft -> Guarded Proposal Fastlane v1 tests.

The endpoint under test is:
  POST /api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal

Safety contract:
  - preflight is read-only and creates no proposal/tool_call
  - proposal creation requires explicit confirm_create_proposal=true
  - proposal creation uses the existing guarded propose-patch path
  - no apply, tests, providers, commands, execution, or file reads are started
"""

from __future__ import annotations

import inspect
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import build_step_patch_draft_proposal_preflight
from src.storage import database


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "step-patch-draft-guarded-proposal.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "guarded-proposal-project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    project = isolated_db.create_project(
        name="Guarded Proposal Project",
        path=str(project_dir),
        stack="FastAPI, React",
        test_command="pytest",
    )
    run = isolated_db.create_run(
        prompt="Prepare guarded proposal",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement backend workflow",
        agent_id="backend-developer",
        input=_step_context(),
    )
    return project, run, step


def _step_context(*, provider_allowed: bool = False, status: str = "covered") -> str:
    return "\n".join([
        "AI_WORKBENCH_REQUIREMENT_CONTEXT:",
        "requirement_ids:",
        "- REQ-001",
        f"coverage_status: {status}",
        "drift_risk: medium",
        "acceptance_criteria:",
        "- Backend workflow supports reviewed proposal creation",
        "constraints:",
        "- Do not apply patches automatically",
        "forbidden_changes:",
        "- Do not touch .env",
        "validation_notes:",
        "- Run targeted tests manually after apply",
        "source_of_truth_summary: Guarded backend workflow",
        "END_AI_WORKBENCH_REQUIREMENT_CONTEXT",
        "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        "- source: intake_confirmed_development_run",
        "- agent_role: backend_agent",
        "- requirement_ids: REQ-001",
        "- module_ids: backend_api",
        "- depends_on: none",
        "- safety_gates: Source of Truth guard; Module policy review; Manual apply confirmation",
        "- manual_approval_required: false",
        f"- provider_allowed: {str(provider_allowed).lower()}",
        "- expected_outputs: guarded proposal",
        "- validation_steps: pytest tests/test_backend_workflow.py",
        "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
    ])


def _draft(**overrides) -> dict:
    data = {
        "run_id": "run",
        "step_id": "step",
        "step_title": "Implement backend workflow",
        "agent_role": "backend_agent",
        "canonical_agent_id": "backend-developer",
        "requirement_ids": ["REQ-001"],
        "module_ids": ["backend_api"],
        "target_files": ["app.py"],
        "patch_intent": "Replace the reviewed backend workflow text.",
        "draft_summary": "Draft candidate for guarded proposal.",
        "suggested_file_path": "app.py",
        "suggested_old_text": "",
        "suggested_new_text": "new\n",
        "risks": ["Manual review required"],
        "validation_steps": ["pytest tests/test_backend_workflow.py"],
        "safety_notes": ["No patch was applied."],
        "blockers": [],
        "warnings": [],
        "ready_for_proposal": True,
        "next_recommended_action": "Run guarded proposal preflight.",
        "source": "step_agent_patch_draft",
    }
    data.update(overrides)
    return data


def _payload(**overrides) -> dict:
    data = {
        "patch_draft": _draft(),
        "confirm_create_proposal": False,
        "operator_note": "Operator reviewed the draft.",
        "selected_file_path": "app.py",
        "selected_old_text": "old",
        "selected_new_text": "new",
    }
    data.update(overrides)
    return data


def _post(client, run_id: str, step_id: str, **overrides):
    return client.post(
        f"/api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal",
        json=_payload(**overrides),
    )


def _tool_call_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    finally:
        conn.close()


def _proposal_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM tool_calls WHERE tool_name = 'propose-patch'").fetchone()[0]
    finally:
        conn.close()


def _guard_result_count() -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute("SELECT COUNT(*) FROM guard_results").fetchone()[0]
    finally:
        conn.close()


class TestPreflightBehavior:
    def test_01_preflight_returns_created_false_when_confirm_false(self, client, project_run_step):
        _, run, step = project_run_step
        resp = _post(client, run.id, step.id)
        assert resp.status_code == 200
        body = resp.json()
        assert body["created"] is False
        assert body["guard_decision"] == "preflight_ready"

    def test_02_preflight_creates_no_proposal(self, client, project_run_step):
        _, run, step = project_run_step
        before = _proposal_count()
        _post(client, run.id, step.id)
        assert _proposal_count() == before

    def test_03_preflight_creates_no_tool_call(self, client, project_run_step):
        _, run, step = project_run_step
        before = _tool_call_count()
        _post(client, run.id, step.id)
        assert _tool_call_count() == before

    def test_04_missing_file_path_blocks(self, client, project_run_step):
        _, run, step = project_run_step
        draft = _draft(suggested_file_path="", target_files=[])
        body = _post(client, run.id, step.id, selected_file_path="", patch_draft=draft).json()
        assert any("selected_file_path" in blocker for blocker in body["blockers"])

    def test_05_missing_new_text_blocks(self, client, project_run_step):
        _, run, step = project_run_step
        draft = _draft(suggested_new_text="")
        body = _post(client, run.id, step.id, selected_new_text="", patch_draft=draft).json()
        assert any("selected_new_text" in blocker for blocker in body["blockers"])

    def test_06_missing_old_text_blocks(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, selected_old_text="").json()
        assert any("selected_old_text" in blocker for blocker in body["blockers"])

    def test_07_provider_allowed_true_blocks(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, patch_draft=_draft(provider_allowed=True)).json()
        assert any("provider_allowed=true" in blocker for blocker in body["blockers"])

    def test_08_non_pending_step_blocks(self, client, project_run_step, isolated_db):
        _, run, step = project_run_step
        isolated_db.update_run_step(step.id, status="completed")
        body = _post(client, run.id, step.id).json()
        assert any("pending" in blocker.lower() for blocker in body["blockers"])

    def test_09_malformed_draft_does_not_crash(self, client, project_run_step):
        _, run, step = project_run_step
        resp = _post(client, run.id, step.id, patch_draft={"target_files": "not-list"})
        assert resp.status_code == 200
        assert "blockers" in resp.json()

    def test_10_preflight_is_deterministic(self, client, project_run_step):
        _, run, step = project_run_step
        first = _post(client, run.id, step.id).json()
        second = _post(client, run.id, step.id).json()
        assert first == second


class TestProposalCreation:
    def test_11_confirm_true_can_create_proposal_with_valid_fields(self, client, project_run_step):
        _, run, step = project_run_step
        resp = _post(client, run.id, step.id, confirm_create_proposal=True)
        assert resp.status_code == 200
        assert resp.json()["created"] is True

    def test_12_returns_proposal_id(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, confirm_create_proposal=True).json()
        assert body["proposal_id"]

    def test_13_created_true_on_success(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, confirm_create_proposal=True).json()
        assert body["created"] is True

    def test_14_proposal_stores_file_path(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        call = database.list_tool_calls_for_run(run.id, limit=20)[0]
        assert "app.py" in call.input_json

    def test_15_proposal_stores_old_text_new_text(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        call = database.list_tool_calls_for_run(run.id, limit=20)[0]
        assert "old" in call.input_json
        assert "new" in call.input_json

    def test_16_proposal_links_run_id_step_id(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        call = database.list_tool_calls_for_run(run.id, limit=20)[0]
        assert call.run_id == run.id
        assert call.step_id == step.id

    def test_17_proposal_carries_requirement_module_context_where_supported(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, confirm_create_proposal=True).json()
        assert body["module_awareness"] is not None
        assert "REQ-001" in str(body["module_awareness"]) or body["module_awareness"].get("matched_requirement_ids") == []

    def test_18_guard_decision_returned(self, client, project_run_step):
        _, run, step = project_run_step
        assert _post(client, run.id, step.id, confirm_create_proposal=True).json()["guard_decision"] in {"allowed", "warning"}

    def test_19_module_awareness_returned_if_available(self, client, project_run_step):
        _, run, step = project_run_step
        assert isinstance(_post(client, run.id, step.id, confirm_create_proposal=True).json()["module_awareness"], dict)

    def test_20_module_policy_returned_if_available(self, client, project_run_step):
        _, run, step = project_run_step
        assert isinstance(_post(client, run.id, step.id, confirm_create_proposal=True).json()["module_policy"], dict)

    def test_21_patch_review_returned_or_safely_absent(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, confirm_create_proposal=True).json()
        assert body["patch_review"] is None or isinstance(body["patch_review"], dict)


class TestSafety:
    def test_22_does_not_apply_patch(self, client, project_run_step):
        project, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert (pathlib.Path(project.path) / "app.py").read_text(encoding="utf-8") == "old\n"

    def test_23_does_not_run_tests(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert all(call.tool_name != "run-command" for call in database.list_tool_calls_for_run(run.id, limit=50))

    def test_24_does_not_call_providers(self, client, project_run_step, monkeypatch):
        import src.api.routes as routes

        def fail(*args, **kwargs):  # pragma: no cover
            raise AssertionError("provider call attempted")

        monkeypatch.setattr(routes, "route_model", fail)
        _, run, step = project_run_step
        resp = _post(client, run.id, step.id, confirm_create_proposal=True)
        assert resp.status_code == 200

    def test_25_does_not_execute_run(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert database.get_run(run.id).status == "pending"

    def test_26_does_not_create_run_steps(self, client, project_run_step):
        _, run, step = project_run_step
        before = len(database.list_run_steps(run.id))
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert len(database.list_run_steps(run.id)) == before

    def test_27_does_not_change_step_status(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert database.list_run_steps(run.id)[0].status == "pending"

    def test_28_apply_confirm_true_behavior_unchanged(self):
        import src.models as models

        assert models.ApplyPatchRequest.model_fields["confirm"].default is False

    def test_29_no_guard_override_behavior_unchanged_on_existing_endpoint(self, client, project_run_step):
        project, run, step = project_run_step
        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json={
                "run_id": run.id,
                "step_id": step.id,
                "operations": [{"file_path": "app.py", "old_text": "old", "new_text": "new"}],
                "no_guard_override": True,
            },
        )
        assert resp.status_code == 200
        assert resp.json()["no_guard_override"] is True

    def test_30_invalid_guard_blocks_when_required(self, client, project_run_step):
        _, run, step = project_run_step
        body = _post(client, run.id, step.id, selected_file_path=".env", confirm_create_proposal=True).json()
        assert body["created"] is False
        assert body["blockers"]


class TestEndpoint:
    def test_31_bad_run_returns_404(self, client):
        resp = client.post("/api/runs/bad-run/steps/bad-step/patch-draft/guarded-proposal", json=_payload())
        assert resp.status_code == 404

    def test_32_bad_step_returns_404(self, client, project_run_step):
        _, run, _ = project_run_step
        resp = client.post(f"/api/runs/{run.id}/steps/bad-step/patch-draft/guarded-proposal", json=_payload())
        assert resp.status_code == 404

    def test_33_step_from_another_run_returns_404(self, client, project_run_step, isolated_db):
        project, _, step = project_run_step
        other_run = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        resp = client.post(f"/api/runs/{other_run.id}/steps/{step.id}/patch-draft/guarded-proposal", json=_payload())
        assert resp.status_code == 404

    def test_34_confirm_false_path_does_not_persist_proposal(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=False)
        assert _proposal_count() == 0

    def test_35_confirm_true_path_persists_at_most_one_proposal(self, client, project_run_step):
        _, run, step = project_run_step
        _post(client, run.id, step.id, confirm_create_proposal=True)
        assert _proposal_count() == 1

    def test_36_response_includes_next_recommended_action(self, client, project_run_step):
        _, run, step = project_run_step
        assert _post(client, run.id, step.id).json()["next_recommended_action"]

    def test_37_response_includes_safety_notes(self, client, project_run_step):
        _, run, step = project_run_step
        notes = _post(client, run.id, step.id).json()["safety_notes"]
        assert any("No patch was applied" in note for note in notes)


class TestIntegration:
    def test_38_patch_draft_endpoint_output_can_be_used_for_preflight(self, client, project_run_step):
        _, run, step = project_run_step
        draft = client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={}).json()
        resp = _post(client, run.id, step.id, patch_draft=draft)
        assert resp.status_code == 200
        assert resp.json()["created"] is False

    def test_39_patch_draft_endpoint_output_can_create_after_operator_fields(self, client, project_run_step):
        _, run, step = project_run_step
        draft = client.post(f"/api/runs/{run.id}/steps/{step.id}/agent-patch-draft", json={}).json()
        resp = _post(
            client,
            run.id,
            step.id,
            patch_draft=draft,
            selected_old_text="old",
            selected_new_text="new",
            confirm_create_proposal=True,
        )
        assert resp.status_code == 200
        assert resp.json()["created"] is True

    def test_40_guarded_proposal_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_guarded_patch_proposal.py").exists()

    def test_41_apply_guard_revalidation_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_apply_guard_revalidation.py").exists()

    def test_42_guard_proposal_module_awareness_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_guard_proposal_module_awareness.py").exists()

    def test_43_module_aware_guard_policy_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_module_aware_guard_policy.py").exists()


class TestFrontendStatic:
    @pytest.fixture(scope="class")
    def run_detail_source(self):
        return (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")

    def test_44_rundetail_contains_preflight_guarded_proposal_ui(self, run_detail_source):
        assert "Preflight Guarded Proposal" in run_detail_source

    def test_45_rundetail_contains_create_guarded_proposal_ui(self, run_detail_source):
        assert "Create Guarded Proposal" in run_detail_source

    def test_46_ui_text_says_no_apply_no_tests(self, run_detail_source):
        assert "No patch was applied" in run_detail_source
        assert "No tests were run" in run_detail_source

    def test_47_ui_requires_explicit_proposal_confirmation(self, run_detail_source):
        assert "I confirm creating a patch proposal only. Do not apply patch." in run_detail_source

    def test_48_ui_does_not_call_apply_endpoint_from_this_action(self, run_detail_source):
        section = run_detail_source.split("function AgentStepContextPanel", 1)[1].split("// ── Operator Queue Panel", 1)[0]
        assert "applyProjectPatch(" not in section

    def test_49_ui_does_not_run_tests_from_this_action(self, run_detail_source):
        section = run_detail_source.split("function AgentStepContextPanel", 1)[1].split("// ── Operator Queue Panel", 1)[0]
        assert "runProjectCommand(" not in section


class TestSafetyStatic:
    def test_50_no_execute_run_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_patch_draft_guarded_proposal)
        assert "execute_run(" not in source

    def test_51_no_asyncio_create_task_added(self):
        source = inspect.getsource(build_step_patch_draft_proposal_preflight)
        assert "asyncio.create_task" not in source

    def test_52_no_provider_calls_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_patch_draft_guarded_proposal)
        source += inspect.getsource(build_step_patch_draft_proposal_preflight)
        assert "route_model(" not in source
        assert "chat_completion" not in source

    def test_53_no_apply_project_patch_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_patch_draft_guarded_proposal)
        source += inspect.getsource(build_step_patch_draft_proposal_preflight)
        assert "apply_project_patch" not in source

    def test_54_no_command_execution_added(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_patch_draft_guarded_proposal)
        source += inspect.getsource(build_step_patch_draft_proposal_preflight)
        assert "subprocess" not in source
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_55_no_file_reads_added_in_draft_to_proposal_endpoint(self):
        import src.api.routes as routes

        source = inspect.getsource(routes.create_step_patch_draft_guarded_proposal)
        assert "project_read_file" not in source
        assert "open(" not in source
        assert ".read_text(" not in source

    def test_56_database_schema_not_part_of_feature(self):
        feature_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in [
                REPO_ROOT / "backend/src/orchestrator/project_intake.py",
                REPO_ROOT / "backend/src/api/routes.py",
            ]
        )
        assert "ALTER TABLE" not in feature_source


class TestCompatibilityAnchors:
    def test_57_step_agent_patch_draft_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_step_agent_patch_draft_fastlane.py").exists()

    def test_58_intake_run_agent_context_tests_still_exist(self):
        assert (REPO_ROOT / "backend/tests/test_intake_run_agent_assignment_step_context.py").exists()

    def test_59_full_backend_compatibility_is_checked_in_phase_7(self):
        assert (REPO_ROOT / "backend/tests/test_project_context_cockpit.py").exists()

    def test_60_frontend_types_include_guarded_proposal_bridge(self):
        source = (REPO_ROOT / "frontend/src/types/index.ts").read_text(encoding="utf-8")
        assert "StepPatchDraftGuardedProposalResponse" in source

    def test_61_frontend_client_exposes_guarded_proposal_bridge(self):
        source = (REPO_ROOT / "frontend/src/api/client.ts").read_text(encoding="utf-8")
        assert "createStepPatchDraftGuardedProposal" in source
        assert "patch-draft/guarded-proposal" in source

    def test_62_scripts_runner_remains_independent(self):
        source = (REPO_ROOT / "scripts/run_tests.sh").read_text(encoding="utf-8")
        assert "patch-draft/guarded-proposal" not in source

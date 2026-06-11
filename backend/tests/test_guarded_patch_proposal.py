"""Tests for backend-enforced guard_result_id support in propose-patch."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
)
from src.storage import database
from src.storage.guard_result_storage import (
    create_guard_result,
    get_guard_result,
    mark_guard_result_stale,
)


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "app.py").write_text("old\n", encoding="utf-8")
    project = isolated_db.create_project("Guarded Project", str(project_dir))
    run = isolated_db.create_run(
        prompt="Guarded patch proposal",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement guarded change",
        input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids:\n- REQ-001\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    )
    return project, run, step


def _proposal_payload(
    *,
    guard_result_id: str | None = None,
    guard_warning_acknowledged: bool = False,
    no_guard_override: bool = False,
    run_id: str,
    step_id: str,
    file_path: str = "app.py",
    old_text: str = "old",
    new_text: str = "new",
) -> dict:
    payload = {
        "run_id": run_id,
        "step_id": step_id,
        "operations": [{
            "file_path": file_path,
            "old_text": old_text,
            "new_text": new_text,
            "create_if_missing": False,
            "replace_all": False,
        }],
    }
    if guard_result_id is not None:
        payload["guard_result_id"] = guard_result_id
    if guard_warning_acknowledged:
        payload["guard_warning_acknowledged"] = True
    if no_guard_override:
        payload["no_guard_override"] = True
    return payload


def _create_guard_record(
    *,
    run_id: str,
    step_id: str,
    guard_id: str = "guard-1",
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
    file_path: str = "app.py",
    old_text: str = "old",
    new_text: str = "new",
) -> str:
    record = build_workflow_guard_result_record(
        id=guard_id,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Implement guarded app change",
            file_path=file_path,
            old_text=old_text,
            new_text=new_text,
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["App change is previewed only"],
            constraints=["Do not apply automatically"],
            forbidden_changes=["Do not touch .env"],
            validation_notes=["Manual proposal only"],
            source_of_truth_summary="Implement guarded app change",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-001"] if decision != WorkflowGuardDecision.BLOCKED else [],
            forbidden_change_hits=["Do not touch .env"] if decision == WorkflowGuardDecision.BLOCKED else [],
            warnings=["Manual acknowledgement required"] if decision == WorkflowGuardDecision.WARNING else [],
            reasons=["Requirement context matched"],
            recommended_next_step="Proceed manually.",
        ),
    )
    create_guard_result(record)
    return guard_id


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=100))


class TestGuardedPatchProposal:
    def test_valid_allowed_guard_result_id_succeeds_and_links(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] == gid
        assert data["guard_validation_valid"] is True
        assert data["proposal_id"]
        linked = get_guard_result(gid)
        assert linked is not None
        assert linked.proposal_tool_call_id == data["proposal_id"]

    def test_warning_guard_without_acknowledgement_rejects(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="warning-no-ack",
            decision=WorkflowGuardDecision.WARNING,
        )
        before = _tool_call_count(run.id)

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "Warning guard requires explicit acknowledgement" in str(resp.json()["detail"])
        assert _tool_call_count(run.id) == before

    def test_warning_guard_with_acknowledgement_succeeds(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="warning-ack",
            decision=WorkflowGuardDecision.WARNING,
        )

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(
                guard_result_id=gid,
                guard_warning_acknowledged=True,
                run_id=run.id,
                step_id=step.id,
            ),
        )

        assert resp.status_code == 200
        assert resp.json()["guard_result_id"] == gid

    def test_blocked_guard_rejects(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="blocked",
            decision=WorkflowGuardDecision.BLOCKED,
        )

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "Blocked guard result" in str(resp.json()["detail"])

    def test_stale_guard_rejects(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id, guard_id="stale")
        mark_guard_result_stale(gid, WorkflowGuardStaleReason.MANUAL_INVALIDATION)

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "stale" in str(resp.json()["detail"]).lower()

    def test_guard_from_another_run_rejects(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        other_run = isolated_db.create_run(prompt="Other", project_id=project.id, project_path=project.path)
        other_step = isolated_db.create_run_step(run_id=other_run.id, title="Other")
        gid = _create_guard_record(run_id=other_run.id, step_id=other_step.id, guard_id="wrong-run")

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "does not belong to this run" in str(resp.json()["detail"])

    def test_guard_from_another_step_rejects(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        other_step = isolated_db.create_run_step(run_id=run.id, title="Other")
        gid = _create_guard_record(run_id=run.id, step_id=other_step.id, guard_id="wrong-step")

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "does not belong to this step" in str(resp.json()["detail"])

    def test_missing_selected_guard_result_rejects_without_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        before = _tool_call_count(run.id)

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id="missing-guard", run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 404
        assert "Guard result not found" in str(resp.json()["detail"])
        assert _tool_call_count(run.id) == before

    def test_payload_mismatch_rejects(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id, guard_id="mismatch")

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(
                guard_result_id=gid,
                run_id=run.id,
                step_id=step.id,
                new_text="unrelated",
            ),
        )

        assert resp.status_code == 400
        assert "new_text_changed" in str(resp.json()["detail"])

    def test_missing_guard_without_override_rejects_step_linked_proposal(self, client, project_run_step):
        project, run, step = project_run_step
        before = _tool_call_count(run.id)

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 400
        assert "require a valid guard_result_id" in str(resp.json()["detail"])
        assert _tool_call_count(run.id) == before

    def test_missing_guard_with_override_succeeds(self, client, project_run_step):
        project, run, step = project_run_step

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(no_guard_override=True, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] is None
        assert data["no_guard_override"] is True
        assert data["proposal_id"]

    def test_no_guard_override_cannot_override_selected_blocked_guard(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="blocked-with-override",
            decision=WorkflowGuardDecision.BLOCKED,
        )

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(
                guard_result_id=gid,
                no_guard_override=True,
                run_id=run.id,
                step_id=step.id,
            ),
        )

        assert resp.status_code == 400
        assert "no_guard_override does not override" in str(resp.json()["detail"])

    def test_validation_failure_creates_no_proposal_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="blocked-no-call",
            decision=WorkflowGuardDecision.BLOCKED,
        )
        before = _tool_call_count(run.id)

        client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert _tool_call_count(run.id) == before

    def test_successful_proposal_does_not_apply_patch_or_run_tests(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id, guard_id="safe-success")

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 200
        assert (project.path and True)
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"
        calls = database.list_tool_calls_for_run(run.id)
        assert [call.tool_name for call in calls] == ["propose-patch"]

    def test_apply_patch_remains_manual_and_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id, guard_id="apply-unchanged")
        proposal = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )
        assert proposal.status_code == 200

        apply_resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json={
                "run_id": run.id,
                "step_id": step.id,
                "proposal_id": proposal.json()["proposal_id"],
                "confirm": False,
                "operations": [{
                    "file_path": "app.py",
                    "old_text": "old",
                    "new_text": "new",
                    "create_if_missing": False,
                    "replace_all": False,
                }],
            },
        )

        assert apply_resp.status_code == 403
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_run_and_step_status_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id, guard_id="status")

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json=_proposal_payload(guard_result_id=gid, run_id=run.id, step_id=step.id),
        )

        assert resp.status_code == 200
        assert database.get_run(run.id).status == run.status
        assert database.update_run_step(step.id).status == step.status

    def test_non_step_linked_proposal_remains_compatible(self, client, project_run_step):
        project, _run, _step = project_run_step

        resp = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json={
                "operations": [{
                    "file_path": "app.py",
                    "old_text": "old",
                    "new_text": "new",
                    "create_if_missing": False,
                    "replace_all": False,
                }],
            },
        )

        assert resp.status_code == 200
        assert resp.json()["proposal_id"]

"""Tests for apply-time Source-of-Truth Guard revalidation."""

from __future__ import annotations

import json

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
    project = isolated_db.create_project("Apply Guard Project", str(project_dir))
    run = isolated_db.create_run(
        prompt="Guarded apply",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Apply guarded patch",
        input="AI_WORKBENCH_REQUIREMENT_CONTEXT:\nrequirement_ids:\n- REQ-001\nEND_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    )
    return project, run, step


def _op(file_path: str = "app.py", old_text: str = "old", new_text: str = "new") -> dict:
    return {
        "file_path": file_path,
        "old_text": old_text,
        "new_text": new_text,
        "create_if_missing": False,
        "replace_all": False,
    }


def _create_guard(
    *,
    run_id: str,
    step_id: str,
    guard_id: str = "apply-guard-1",
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
            proposed_action="Apply guarded app change",
            file_path=file_path,
            old_text=old_text,
            new_text=new_text,
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["App change is applied manually"],
            constraints=["Do not auto-apply"],
            forbidden_changes=["Do not touch .env"],
            validation_notes=["Manual apply only"],
            source_of_truth_summary="Apply guarded app change",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-001"] if decision != WorkflowGuardDecision.BLOCKED else [],
            forbidden_change_hits=["Do not touch .env"] if decision == WorkflowGuardDecision.BLOCKED else [],
            warnings=["Manual acknowledgement required"] if decision == WorkflowGuardDecision.WARNING else [],
            reasons=["Requirement context matched"],
        ),
    )
    create_guard_result(record)
    return guard_id


def _create_guarded_proposal(
    client: TestClient,
    *,
    project_id: str,
    run_id: str,
    step_id: str,
    guard_id: str,
    guard_warning_acknowledged: bool = False,
    operation: dict | None = None,
) -> dict:
    payload = {
        "run_id": run_id,
        "step_id": step_id,
        "guard_result_id": guard_id,
        "guard_warning_acknowledged": guard_warning_acknowledged,
        "operations": [operation or _op()],
    }
    resp = client.post(f"/api/projects/{project_id}/tools/propose-patch", json=payload)
    assert resp.status_code == 200
    return resp.json()


def _apply_payload(
    *,
    run_id: str,
    step_id: str,
    proposal_id: str,
    confirm: bool = True,
    operation: dict | None = None,
) -> dict:
    return {
        "run_id": run_id,
        "step_id": step_id,
        "proposal_id": proposal_id,
        "confirm": confirm,
        "operations": [operation or _op()],
    }


def _apply_calls(run_id: str):
    return [call for call in database.list_tool_calls_for_run(run_id) if call.tool_name == "apply-patch"]


class TestApplyGuardRevalidation:
    def test_apply_patch_still_requires_confirm_true(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id)
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"], confirm=False),
        )

        assert resp.status_code == 403
        assert (project_run_step[0].path and True)
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_valid_linked_allowed_guard_permits_manual_apply_and_links(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id)
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] == gid
        assert data["guard_revalidated"] is True
        linked = get_guard_result(gid)
        assert linked is not None
        assert linked.apply_tool_call_id == data["tool_call_id"]
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "new\n"

    def test_stale_linked_guard_blocks_apply_without_file_mutation(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="apply-stale")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)
        mark_guard_result_stale(gid, WorkflowGuardStaleReason.MANUAL_INVALIDATION)
        before = len(_apply_calls(run.id))

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert resp.status_code == 400
        assert "stale" in str(resp.json()["detail"]).lower()
        assert len(_apply_calls(run.id)) == before
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_blocked_linked_guard_blocks_apply(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="blocked-for-apply")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)
        record = get_guard_result(gid)
        assert record is not None
        create_guard_result(record.model_copy(update={
            "id": "blocked-linked",
            "proposal_tool_call_id": proposal["proposal_id"],
            "result_snapshot": build_guard_result_snapshot(
                decision=WorkflowGuardDecision.BLOCKED,
                drift_risk=WorkflowGuardDriftRisk.CRITICAL,
                forbidden_change_hits=["blocked"],
            ),
        }))
        # Prefer the explicit blocked record by making the proposal output claim it.
        database.update_tool_call(
            proposal["proposal_id"],
            output_json=json.dumps({**proposal, "guard_result_id": "blocked-linked"}, ensure_ascii=False),
        )

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert resp.status_code == 400
        assert "Blocked guard result" in str(resp.json()["detail"])

    def test_payload_mismatch_blocks_apply(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="apply-mismatch")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(
                run_id=run.id,
                step_id=step.id,
                proposal_id=proposal["proposal_id"],
                operation=_op(new_text="different"),
            ),
        )

        assert resp.status_code == 400
        assert "new_text_changed" in str(resp.json()["detail"])
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_missing_linked_guard_result_blocks_guarded_apply(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        proposal_call = isolated_db.create_tool_call(
            run_id=run.id,
            project_id=project.id,
            step_id=step.id,
            tool_name="propose-patch",
            cwd=project.path,
            status="completed",
            input_json=json.dumps({"run_id": run.id, "step_id": step.id, "guard_result_id": "missing"}),
            output_json=json.dumps({"proposal_id": "manual-proposal", "guard_result_id": "missing"}),
        )

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal_call.id),
        )

        assert resp.status_code == 400
        assert "could not be found" in str(resp.json()["detail"])
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_confirm_true_does_not_bypass_failed_guard_revalidation(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="confirm-no-bypass")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)
        mark_guard_result_stale(gid, WorkflowGuardStaleReason.EXPIRED)

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"], confirm=True),
        )

        assert resp.status_code == 400
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "old\n"

    def test_no_guard_override_proposal_can_apply_manually(self, client, project_run_step):
        project, run, step = project_run_step
        proposal = client.post(
            f"/api/projects/{project.id}/tools/propose-patch",
            json={
                "run_id": run.id,
                "step_id": step.id,
                "no_guard_override": True,
                "operations": [_op()],
            },
        ).json()

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] is None
        assert data["guard_revalidated"] is False
        assert data["no_guard_override"] is True
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "new\n"

    def test_apply_does_not_run_tests_or_mutate_run_step_status(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="status-safe")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert resp.status_code == 200
        calls = database.list_tool_calls_for_run(run.id)
        assert [call.tool_name for call in calls] == ["apply-patch", "propose-patch"]
        assert database.get_run(run.id).status == run.status
        assert database.update_run_step(step.id).status == step.status

    def test_existing_unguarded_apply_behavior_remains_compatible(self, client, project_run_step):
        project, run, step = project_run_step

        resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json={
                "run_id": run.id,
                "step_id": step.id,
                "confirm": True,
                "operations": [_op()],
            },
        )

        assert resp.status_code == 200
        assert resp.json()["guard_revalidated"] is None
        with open(f"{project.path}/app.py", encoding="utf-8") as handle:
            assert handle.read() == "new\n"

    def test_failed_revalidation_does_not_add_apply_link(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="no-apply-link")
        proposal = _create_guarded_proposal(client, project_id=project.id, run_id=run.id, step_id=step.id, guard_id=gid)
        mark_guard_result_stale(gid, WorkflowGuardStaleReason.EXPIRED)

        client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json=_apply_payload(run_id=run.id, step_id=step.id, proposal_id=proposal["proposal_id"]),
        )

        assert get_guard_result(gid).apply_tool_call_id is None

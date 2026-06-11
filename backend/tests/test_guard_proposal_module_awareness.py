"""Tests for module-aware guarded patch proposal responses."""

from __future__ import annotations

import inspect
import json

import pytest
from fastapi.testclient import TestClient

from src.models import ProjectModuleMapDocument, ProjectModuleMapItem
from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardSource,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
)
from src.storage import database
from src.storage.guard_result_storage import create_guard_result
from src.storage.module_map_storage import (
    build_patch_proposal_module_awareness,
    create_or_update_project_module_map,
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
    for folder in (
        "backend/src/auth",
        "backend/src/database",
        "frontend/src/pages",
        "unknown",
    ):
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
    for path in (
        "backend/src/auth/service.ts",
        "backend/src/database/schema.sql",
        "frontend/src/pages/Login.tsx",
        "unknown/path.py",
        "app.py",
    ):
        (project_dir / path).write_text("old\n", encoding="utf-8")
    (project_dir / "backend/src/auth/secret.txt").write_text(
        "SECRET_FILE_CONTENT_DO_NOT_LEAK\n",
        encoding="utf-8",
    )
    project = isolated_db.create_project("Module Aware Proposal", str(project_dir))
    run = isolated_db.create_run(
        prompt="Guarded module-aware proposal",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Implement auth login",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-AUTH-001\n"
            "source_of_truth_summary: Auth login must remain safe.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
        ),
    )
    return project, run, step


def _module(
    *,
    module_id: str,
    name: str,
    slug: str,
    module_type: str = "backend",
    related_requirements: list[str] | None = None,
    paths: list[str] | None = None,
    key_files: list[str] | None = None,
    test_hints: list[str] | None = None,
    risks: list[str] | None = None,
    confidence: str = "medium",
) -> ProjectModuleMapItem:
    return ProjectModuleMapItem(
        id=module_id,
        name=name,
        slug=slug,
        module_type=module_type,
        description=f"{name} module",
        responsibilities=[f"{name} responsibility"],
        paths=paths or [f"src/{slug}"],
        key_files=key_files or [f"src/{slug}/index.ts"],
        related_requirements=related_requirements or [],
        test_hints=test_hints or [f"{slug} tests"],
        risks=risks or [f"{slug} risk"],
        confidence=confidence,
    )


def _create_map(project_id: str, modules: list[ProjectModuleMapItem] | None = None):
    return create_or_update_project_module_map(
        project_id,
        ProjectModuleMapDocument(
            project_id=project_id,
            version=1,
            status="active",
            source="manual",
            modules=modules
            or [
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    related_requirements=["REQ-AUTH-001"],
                    paths=["backend/src/auth"],
                    key_files=["backend/src/auth/service.ts"],
                    test_hints=["auth unit tests", "login integration tests"],
                    risks=["auth risk"],
                    confidence="high",
                ),
                _module(
                    module_id="mod-frontend",
                    name="Frontend",
                    slug="frontend",
                    module_type="frontend",
                    paths=["frontend/src"],
                    key_files=["frontend/src/pages/Login.tsx"],
                    risks=[],
                ),
                _module(
                    module_id="mod-db",
                    name="Database",
                    slug="database",
                    module_type="database",
                    paths=["backend/src/database"],
                    key_files=["backend/src/database/schema.sql"],
                    risks=["schema migration risk"],
                ),
            ],
        ),
    )


def _create_guard_record(
    *,
    run_id: str,
    step_id: str,
    guard_id: str = "guard-aware",
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
    file_path: str = "backend/src/auth/service.ts",
    old_text: str = "old",
    new_text: str = "new",
) -> str:
    record = build_workflow_guard_result_record(
        id=guard_id,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Update guarded module file",
            file_path=file_path,
            old_text=old_text,
            new_text=new_text,
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-AUTH-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["Proposal remains manual."],
            constraints=["Do not apply automatically."],
            forbidden_changes=["Do not touch .env"],
            validation_notes=["Guard checked."],
            source_of_truth_summary="Auth login must remain safe.",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-AUTH-001"] if decision != WorkflowGuardDecision.BLOCKED else [],
            warnings=["Manual acknowledgement required"] if decision == WorkflowGuardDecision.WARNING else [],
            reasons=["Requirement context matched"],
            recommended_next_step="Create proposal manually.",
        ),
    )
    create_guard_result(record)
    return guard_id


def _proposal_payload(
    *,
    run_id: str,
    step_id: str,
    file_path: str = "backend/src/auth/service.ts",
    guard_result_id: str | None = None,
    no_guard_override: bool = False,
    guard_warning_acknowledged: bool = False,
) -> dict:
    payload = {
        "run_id": run_id,
        "step_id": step_id,
        "operations": [
            {
                "file_path": file_path,
                "old_text": "old",
                "new_text": "new",
                "create_if_missing": False,
                "replace_all": False,
            }
        ],
    }
    if guard_result_id is not None:
        payload["guard_result_id"] = guard_result_id
    if no_guard_override:
        payload["no_guard_override"] = True
    if guard_warning_acknowledged:
        payload["guard_warning_acknowledged"] = True
    return payload


def _propose(client: TestClient, project_id: str, payload: dict):
    return client.post(f"/api/projects/{project_id}/tools/propose-patch", json=payload)


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


class TestProposalModuleAwareness:
    def test_no_active_module_map_returns_false_and_proposal_still_works(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert resp.status_code == 200
        data = resp.json()
        assert data["proposal_id"]
        assert data["module_awareness"]["has_active_module_map"] is False

    def test_proposal_file_maps_to_touched_module(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert resp.status_code == 200
        awareness = resp.json()["module_awareness"]
        assert [mod["slug"] for mod in awareness["touched_modules"]] == ["auth"]

    def test_requirement_ids_map_to_expected_module(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        awareness = resp.json()["module_awareness"]
        assert [mod["slug"] for mod in awareness["expected_modules"]] == ["auth"]
        assert awareness["matched_requirement_ids"] == ["REQ-AUTH-001"]

    def test_matching_touched_and_expected_modules_has_no_mismatch_warning(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        warnings = resp.json()["module_awareness"]["warnings"]
        assert "Touched modules do not overlap expected modules from step requirements/module map." not in warnings

    def test_mismatched_touched_and_expected_modules_warns(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            file_path="frontend/src/pages/Login.tsx",
            guard_id="frontend-guard",
        )

        resp = _propose(
            client,
            project.id,
            _proposal_payload(
                run_id=run.id,
                step_id=step.id,
                guard_result_id=gid,
                file_path="frontend/src/pages/Login.tsx",
            ),
        )

        warnings = resp.json()["module_awareness"]["warnings"]
        assert "Touched modules do not overlap expected modules from step requirements/module map." in warnings

    def test_unknown_proposed_file_warns(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            file_path="unknown/path.py",
            guard_id="unknown-file",
        )

        resp = _propose(
            client,
            project.id,
            _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid, file_path="unknown/path.py"),
        )

        assert "Proposed files do not match any known module." in resp.json()["module_awareness"]["warnings"]

    def test_risky_module_warns_and_includes_risks(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        awareness = resp.json()["module_awareness"]
        assert "Touched module 'Auth' has recorded risks." in awareness["warnings"]
        assert "auth risk" in awareness["module_risks"]

    def test_database_module_warns_as_sensitive(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            file_path="backend/src/database/schema.sql",
            guard_id="db-guard",
        )

        resp = _propose(
            client,
            project.id,
            _proposal_payload(
                run_id=run.id,
                step_id=step.id,
                guard_result_id=gid,
                file_path="backend/src/database/schema.sql",
            ),
        )

        assert "Proposal touches sensitive module 'Database'." in resp.json()["module_awareness"]["warnings"]

    def test_module_test_hints_are_included(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert "auth unit tests" in resp.json()["module_awareness"]["module_test_hints"]

    def test_output_is_bounded(self, project_run_step):
        project, _run, step = project_run_step
        modules = [
            _module(
                module_id=f"mod-{i}",
                name=f"Module {i}",
                slug=f"mod{i}",
                paths=[f"area/{i}"],
                key_files=[f"area/{i}/file{j}.ts" for j in range(20)],
                risks=[f"risk-{i}-{j}" for j in range(20)],
                test_hints=[f"test-{i}-{j}" for j in range(20)],
            )
            for i in range(8)
        ]
        _create_map(project.id, modules)

        awareness = build_patch_proposal_module_awareness(
            project.id,
            [f"area/{i}/file0.ts" for i in range(8)],
            step_input=step.input,
            step_title=step.title,
        )

        assert len(awareness.touched_modules) == 5
        assert len(awareness.expected_files) <= 16
        assert len(awareness.module_risks) <= 10
        assert len(awareness.module_test_hints) <= 10
        for mod in awareness.touched_modules:
            assert len(mod["paths"]) <= 8
            assert len(mod["key_files"]) <= 8

    def test_response_contains_no_file_contents(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert "SECRET_FILE_CONTENT_DO_NOT_LEAK" not in json.dumps(resp.json())

    def test_successful_proposal_still_creates_proposal_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert resp.status_code == 200
        calls = database.list_tool_calls_for_run(run.id, limit=100)
        assert [call.tool_name for call in calls] == ["propose-patch"]
        assert resp.json()["module_awareness"]["has_active_module_map"] is True

    def test_validation_failure_creates_no_proposal_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(
            run_id=run.id,
            step_id=step.id,
            guard_id="blocked-aware",
            decision=WorkflowGuardDecision.BLOCKED,
        )
        before = _tool_call_count(run.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        assert resp.status_code == 400
        assert _tool_call_count(run.id) == before

    def test_no_guard_override_behavior_is_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)

        resp = _propose(
            client,
            project.id,
            _proposal_payload(run_id=run.id, step_id=step.id, no_guard_override=True),
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] is None
        assert data["no_guard_override"] is True
        assert data["module_awareness"]["has_active_module_map"] is True

    def test_guard_result_id_validation_behavior_is_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        data = resp.json()
        assert data["guard_result_id"] == gid
        assert data["guard_validation_valid"] is True
        assert data["guard_validation_reasons"] == []

    def test_apply_patch_confirm_gate_is_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)
        proposal = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))
        assert proposal.status_code == 200

        apply_resp = client.post(
            f"/api/projects/{project.id}/tools/apply-patch",
            json={
                "run_id": run.id,
                "step_id": step.id,
                "proposal_id": proposal.json()["proposal_id"],
                "confirm": False,
                "operations": [
                    {
                        "file_path": "backend/src/auth/service.ts",
                        "old_text": "old",
                        "new_text": "new",
                        "create_if_missing": False,
                        "replace_all": False,
                    }
                ],
            },
        )

        assert apply_resp.status_code == 403

    def test_awareness_is_persisted_in_proposal_tool_call_output(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard_record(run_id=run.id, step_id=step.id)

        resp = _propose(client, project.id, _proposal_payload(run_id=run.id, step_id=step.id, guard_result_id=gid))

        calls = database.list_tool_calls_for_run(run.id, limit=100)
        output = json.loads(calls[0].output_json)
        assert output["proposal_id"] == resp.json()["proposal_id"]
        assert output["module_awareness"]["touched_modules"][0]["slug"] == "auth"

    def test_awareness_helper_has_no_runtime_side_effect_hooks(self):
        source = inspect.getsource(build_patch_proposal_module_awareness)
        forbidden = [
            "execute_run",
            "asyncio.create_task",
            "subprocess",
            "os.system",
            "os.popen",
            "ollama",
            "claude",
            "codex",
            "create_tool_call",
            "propose_project_patch",
            "apply_project_patch",
            "open(",
            ".read_text(",
            ".read(",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
            "CREATE TABLE",
            "ALTER TABLE",
        ]
        for pattern in forbidden:
            assert pattern not in source

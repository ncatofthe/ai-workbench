"""Tests for module-aware guard policy classification on patch proposals."""

from __future__ import annotations

import inspect
import json

import pytest
from fastapi.testclient import TestClient

from src.models import ModuleAwarenessResult, ProjectModuleMapDocument, ProjectModuleMapItem
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
    create_or_update_project_module_map,
    evaluate_module_aware_guard_policy,
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
    for folder in ("frontend/src/pages", "backend/src/auth", "backend/src/database", "misc"):
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
    for path in (
        "frontend/src/pages/Login.tsx",
        "frontend/src/pages/Profile.tsx",
        "backend/src/auth/service.ts",
        "backend/src/database/schema.sql",
        "misc/unknown.py",
    ):
        (project_dir / path).write_text("old\n", encoding="utf-8")
    (project_dir / "backend/src/auth/secret.txt").write_text("SECRET_CONTENT_DO_NOT_LEAK\n", encoding="utf-8")
    project = isolated_db.create_project("Module Policy Project", str(project_dir))
    run = isolated_db.create_run(
        prompt="Module-aware guard policy",
        project_id=project.id,
        project_path=project.path,
    )
    step = isolated_db.create_run_step(
        run_id=run.id,
        title="Update frontend page",
        input=(
            "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
            "requirement_ids:\n"
            "- REQ-FRONT-001\n"
            "source_of_truth_summary: Frontend profile page update.\n"
            "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
        ),
    )
    return project, run, step


def _module(
    *,
    module_id: str,
    name: str,
    slug: str,
    module_type: str = "feature",
    related_requirements: list[str] | None = None,
    paths: list[str] | None = None,
    key_files: list[str] | None = None,
    risks: list[str] | None = None,
    test_hints: list[str] | None = None,
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
        risks=risks or [],
        test_hints=test_hints or [f"{slug} tests"],
        confidence="high",
    )


def _create_map(project_id: str):
    return create_or_update_project_module_map(
        project_id,
        ProjectModuleMapDocument(
            project_id=project_id,
            version=1,
            status="active",
            source="manual",
            modules=[
                _module(
                    module_id="mod-front",
                    name="Frontend",
                    slug="frontend",
                    module_type="frontend",
                    related_requirements=["REQ-FRONT-001"],
                    paths=["frontend/src"],
                    key_files=["frontend/src/pages/Profile.tsx"],
                    test_hints=["frontend tests"],
                ),
                _module(
                    module_id="mod-review",
                    name="Reviews",
                    slug="reviews",
                    related_requirements=["REQ-REVIEW-001"],
                    paths=["backend/src/reviews"],
                    key_files=["backend/src/reviews/service.ts"],
                    test_hints=["review tests"],
                ),
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    module_type="backend",
                    related_requirements=["REQ-AUTH-001"],
                    paths=["backend/src/auth"],
                    key_files=["backend/src/auth/service.ts"],
                    risks=["auth risk"],
                    test_hints=["auth tests"],
                ),
                _module(
                    module_id="mod-db",
                    name="Database",
                    slug="database",
                    module_type="database",
                    related_requirements=["REQ-DB-001"],
                    paths=["backend/src/database"],
                    key_files=["backend/src/database/schema.sql"],
                    risks=["schema risk"],
                    test_hints=["database migration tests"],
                ),
            ],
        ),
    )


def _create_guard(
    *,
    run_id: str,
    step_id: str,
    guard_id: str,
    file_path: str,
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
) -> str:
    record = build_workflow_guard_result_record(
        id=guard_id,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Module-aware proposal",
            file_path=file_path,
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-FRONT-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["Manual proposal only"],
            constraints=["No automatic apply"],
            forbidden_changes=["No secrets"],
            validation_notes=["Guard checked"],
            source_of_truth_summary="Frontend profile page update.",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-FRONT-001"],
            reasons=["Guard matched"],
            recommended_next_step="Create proposal manually.",
        ),
    )
    create_guard_result(record)
    return guard_id


def _proposal_payload(run_id: str, step_id: str, file_path: str, guard_id: str | None = None) -> dict:
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
    if guard_id is not None:
        payload["guard_result_id"] = guard_id
    return payload


def _propose(client: TestClient, project_id: str, payload: dict):
    return client.post(f"/api/projects/{project_id}/tools/propose-patch", json=payload)


def _tool_call_count(run_id: str) -> int:
    return len(database.list_tool_calls_for_run(run_id, limit=500))


class TestModuleAwareGuardPolicy:
    def test_no_active_module_map_gives_allowed_policy_and_proposal_works(self, client, project_run_step):
        project, run, step = project_run_step
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="no-map", file_path="frontend/src/pages/Profile.tsx")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        assert resp.status_code == 200
        policy = resp.json()["module_policy"]
        assert policy["verdict"] == "allowed"
        assert resp.json()["proposal_id"]

    def test_matching_touched_expected_modules_gives_allowed(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="front-match", file_path="frontend/src/pages/Profile.tsx")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        policy = resp.json()["module_policy"]
        assert policy["verdict"] == "allowed"
        assert policy["affected_modules"] == ["Frontend"]

    def test_unknown_proposed_file_gives_warning(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="unknown", file_path="misc/unknown.py")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "misc/unknown.py", gid))

        policy = resp.json()["module_policy"]
        assert policy["verdict"] == "warning"
        assert policy["unknown_files"] == ["misc/unknown.py"]

    def test_non_sensitive_mismatch_gives_warning(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[{"id": "mod-review", "name": "Reviews", "slug": "reviews", "paths": ["backend/src/reviews"], "key_files": []}],
            expected_modules=[{"id": "mod-front", "name": "Frontend", "slug": "frontend", "paths": ["frontend/src"], "key_files": []}],
            touched_files=["backend/src/reviews/service.ts"],
            module_test_hints=["review tests"],
        )

        policy = evaluate_module_aware_guard_policy(awareness, ["backend/src/reviews/service.ts"], has_guard_result=True)

        assert policy.verdict == "warning"
        assert "Touched modules do not overlap expected modules." in policy.reasons

    def test_auth_module_mismatch_is_blocked_classification(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="auth-mismatch", file_path="backend/src/auth/service.ts")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "backend/src/auth/service.ts", gid))

        assert resp.status_code == 200
        policy = resp.json()["module_policy"]
        assert policy["verdict"] == "blocked"
        assert "Auth" in policy["sensitive_modules"]
        assert resp.json()["proposal_id"]

    def test_database_module_mismatch_is_blocked_classification(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="db-mismatch", file_path="backend/src/database/schema.sql")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "backend/src/database/schema.sql", gid))

        policy = resp.json()["module_policy"]
        assert policy["verdict"] == "blocked"
        assert "Database" in policy["sensitive_modules"]

    def test_suspicious_unknown_path_is_blocked(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[],
            expected_modules=[{"id": "mod-front", "name": "Frontend", "slug": "frontend", "paths": ["frontend/src"], "key_files": []}],
            touched_files=[".env"],
            warnings=["Proposed files do not match any known module."],
        )

        policy = evaluate_module_aware_guard_policy(awareness, [".env"], has_guard_result=True)

        assert policy.verdict == "blocked"
        assert policy.unknown_files == [".env"]

    def test_sensitive_module_with_matching_requirement_is_not_blocked(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[{"id": "mod-auth", "name": "Auth", "slug": "auth", "paths": ["backend/src/auth"], "key_files": []}],
            expected_modules=[{"id": "mod-auth", "name": "Auth", "slug": "auth", "paths": ["backend/src/auth"], "key_files": []}],
            touched_files=["backend/src/auth/service.ts"],
            matched_requirement_ids=["REQ-AUTH-001"],
        )

        policy = evaluate_module_aware_guard_policy(awareness, ["backend/src/auth/service.ts"], has_guard_result=True)

        assert policy.verdict != "blocked"
        assert policy.sensitive_modules == ["Auth"]

    def test_module_risks_produce_warning_reason(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[{"id": "mod-feature", "name": "Feature", "slug": "feature", "paths": ["src/feature"], "key_files": []}],
            expected_modules=[{"id": "mod-feature", "name": "Feature", "slug": "feature", "paths": ["src/feature"], "key_files": []}],
            touched_files=["src/feature/index.ts"],
            module_risks=["feature risk"],
        )

        policy = evaluate_module_aware_guard_policy(awareness, ["src/feature/index.ts"], has_guard_result=True)

        assert policy.verdict == "warning"
        assert "Touched module has recorded risks." in policy.reasons

    def test_module_test_hints_appear_in_recommended_tests(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[{"id": "mod-front", "name": "Frontend", "slug": "frontend", "paths": ["frontend/src"], "key_files": []}],
            expected_modules=[{"id": "mod-front", "name": "Frontend", "slug": "frontend", "paths": ["frontend/src"], "key_files": []}],
            touched_files=["frontend/src/pages/Profile.tsx"],
            module_test_hints=["frontend tests"],
        )

        policy = evaluate_module_aware_guard_policy(awareness, ["frontend/src/pages/Profile.tsx"], has_guard_result=True)

        assert policy.recommended_tests == ["frontend tests"]

    def test_policy_output_is_capped(self):
        awareness = ModuleAwarenessResult(
            has_active_module_map=True,
            touched_modules=[
                {"id": f"mod-{i}", "name": f"Module {i}", "slug": f"module-{i}", "paths": [f"area/{i}"], "key_files": [], "risks": []}
                for i in range(20)
            ],
            expected_modules=[],
            touched_files=[f"area/{i}/file.ts" for i in range(20)],
            module_test_hints=[f"test-{i}" for i in range(20)],
            warnings=[f"warning-{i}" for i in range(20)],
        )

        policy = evaluate_module_aware_guard_policy(
            awareness,
            [f"area/{i}/file.ts" for i in range(20)],
            has_guard_result=True,
        )

        assert len(policy.affected_modules) <= 10
        assert len(policy.reasons) <= 10
        assert len(policy.recommended_tests) <= 10

    def test_policy_contains_no_file_contents(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="no-content", file_path="backend/src/auth/service.ts")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "backend/src/auth/service.ts", gid))

        assert "SECRET_CONTENT_DO_NOT_LEAK" not in json.dumps(resp.json()["module_policy"])

    def test_existing_guard_result_id_validation_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="guard-ok", file_path="frontend/src/pages/Profile.tsx")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        data = resp.json()
        assert data["guard_result_id"] == gid
        assert data["guard_validation_valid"] is True
        assert data["guard_validation_reasons"] == []

    def test_no_guard_override_behavior_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        payload = _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx")
        payload["no_guard_override"] = True

        resp = _propose(client, project.id, payload)

        assert resp.status_code == 200
        data = resp.json()
        assert data["guard_result_id"] is None
        assert data["no_guard_override"] is True
        assert data["module_policy"]["verdict"] == "allowed"

    def test_validation_failure_still_creates_no_proposal_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(
            run_id=run.id,
            step_id=step.id,
            guard_id="blocked-guard",
            file_path="frontend/src/pages/Profile.tsx",
            decision=WorkflowGuardDecision.BLOCKED,
        )
        before = _tool_call_count(run.id)

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        assert resp.status_code == 400
        assert _tool_call_count(run.id) == before

    def test_successful_proposal_still_creates_proposal_tool_call(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="success", file_path="frontend/src/pages/Profile.tsx")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        assert resp.status_code == 200
        assert [call.tool_name for call in database.list_tool_calls_for_run(run.id, limit=100)] == ["propose-patch"]

    def test_apply_patch_confirm_true_unchanged(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="apply-confirm", file_path="frontend/src/pages/Profile.tsx")
        proposal = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))
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
                        "file_path": "frontend/src/pages/Profile.tsx",
                        "old_text": "old",
                        "new_text": "new",
                        "create_if_missing": False,
                        "replace_all": False,
                    }
                ],
            },
        )

        assert apply_resp.status_code == 403

    def test_module_policy_stored_in_tool_call_output(self, client, project_run_step):
        project, run, step = project_run_step
        _create_map(project.id)
        gid = _create_guard(run_id=run.id, step_id=step.id, guard_id="stored", file_path="frontend/src/pages/Profile.tsx")

        resp = _propose(client, project.id, _proposal_payload(run.id, step.id, "frontend/src/pages/Profile.tsx", gid))

        output = json.loads(database.list_tool_calls_for_run(run.id, limit=100)[0].output_json)
        assert output["proposal_id"] == resp.json()["proposal_id"]
        assert output["module_policy"]["verdict"] == "allowed"

    def test_policy_helper_has_no_runtime_side_effect_hooks(self):
        source = inspect.getsource(evaluate_module_aware_guard_policy)
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

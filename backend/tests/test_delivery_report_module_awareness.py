"""Tests for Delivery Report Module Awareness v1.

Safety invariants:
  - Delivery module awareness is reporting-only.
  - No proposals, applies, commands, providers, or tool_calls are created by
    delivery summary/report endpoints.
  - Module policy verdicts do not alter delivery readiness in v1.
"""

from __future__ import annotations

import inspect
import json
import re

import pytest
from fastapi.testclient import TestClient

from src.models import ProjectModuleMapDocument, ProjectModuleMapItem
from src.storage import database
from src.storage.module_map_storage import create_or_update_project_module_map


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "delivery-modules.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project_run_step(isolated_db, tmp_path):
    project_dir = tmp_path / "project"
    for folder in ("backend/src/auth", "backend/src/database", "frontend/src/pages", "scripts"):
        (project_dir / folder).mkdir(parents=True, exist_ok=True)
    (project_dir / "backend/src/auth/service.ts").write_text(
        "SECRET_FILE_CONTENT_DO_NOT_LEAK\n",
        encoding="utf-8",
    )
    (project_dir / "backend/src/database/schema.sql").write_text("schema\n", encoding="utf-8")
    (project_dir / "frontend/src/pages/Login.tsx").write_text("login\n", encoding="utf-8")

    project = isolated_db.create_project("Delivery Module Awareness", str(project_dir))
    run = isolated_db.create_run(
        prompt="Deliver module-aware change",
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
            "coverage_status: covered\n"
            "drift_risk: low\n"
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
    paths: list[str] | None = None,
    key_files: list[str] | None = None,
    related_requirements: list[str] | None = None,
    test_hints: list[str] | None = None,
    risks: list[str] | None = None,
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
        risks=risks or [],
        confidence="high",
    )


def _create_map(project_id: str) -> None:
    create_or_update_project_module_map(
        project_id,
        ProjectModuleMapDocument(
            project_id=project_id,
            version=1,
            status="active",
            source="manual",
            modules=[
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    paths=["backend/src/auth"],
                    key_files=["backend/src/auth/service.ts"],
                    related_requirements=["REQ-AUTH-001"],
                    test_hints=["auth unit tests", "login integration tests"],
                    risks=["auth changes are security-sensitive"],
                ),
                _module(
                    module_id="mod-db",
                    name="Database",
                    slug="database",
                    module_type="database",
                    paths=["backend/src/database"],
                    key_files=["backend/src/database/schema.sql"],
                    test_hints=["database migration tests"],
                    risks=["schema migration risk"],
                ),
                _module(
                    module_id="mod-frontend",
                    name="Frontend",
                    slug="frontend",
                    module_type="frontend",
                    paths=["frontend/src"],
                    key_files=["frontend/src/pages/Login.tsx"],
                    test_hints=["frontend smoke tests"],
                ),
            ],
        ),
    )


def _awareness(
    *,
    touched_slug: str = "auth",
    touched_name: str = "Auth",
    expected_slug: str = "auth",
    expected_name: str = "Auth",
    file_path: str = "backend/src/auth/service.ts",
    warnings: list[str] | None = None,
    risks: list[str] | None = None,
    test_hints: list[str] | None = None,
) -> dict:
    return {
        "has_active_module_map": True,
        "module_map_version": 1,
        "touched_modules": [
            {
                "id": f"mod-{touched_slug}",
                "name": touched_name,
                "slug": touched_slug,
                "module_type": "backend",
                "paths": [file_path.rsplit("/", 1)[0]],
                "key_files": [file_path],
                "related_requirements": ["REQ-AUTH-001"] if expected_slug == touched_slug else [],
                "risks": risks or [],
                "test_hints": test_hints or [],
                "confidence": "high",
            }
        ],
        "expected_modules": [
            {
                "id": f"mod-{expected_slug}",
                "name": expected_name,
                "slug": expected_slug,
                "module_type": "backend",
                "paths": ["backend/src/auth"],
                "key_files": ["backend/src/auth/service.ts"],
                "related_requirements": ["REQ-AUTH-001"],
                "risks": ["auth changes are security-sensitive"] if expected_slug == "auth" else [],
                "test_hints": ["auth unit tests"] if expected_slug == "auth" else [],
                "confidence": "high",
            }
        ],
        "touched_files": [file_path],
        "expected_files": ["backend/src/auth/service.ts"],
        "matched_requirement_ids": ["REQ-AUTH-001"],
        "module_risks": risks or [],
        "module_test_hints": test_hints or [],
        "warnings": warnings or [],
        "confidence": "high",
    }


def _policy(
    *,
    verdict: str = "warning",
    reasons: list[str] | None = None,
    sensitive_modules: list[str] | None = None,
    unknown_files: list[str] | None = None,
    recommended_tests: list[str] | None = None,
) -> dict:
    return {
        "verdict": verdict,
        "reasons": reasons or [],
        "required_acknowledgements": ["Review module policy classification."]
        if verdict in ("warning", "blocked")
        else [],
        "affected_modules": ["Auth"],
        "sensitive_modules": sensitive_modules or [],
        "unknown_files": unknown_files or [],
        "recommended_tests": recommended_tests or [],
        "confidence": "high",
    }


def _make_tool_call(
    *,
    isolated_db,
    project_id: str,
    run_id: str,
    step_id: str,
    tool_name: str = "propose-patch",
    file_path: str = "backend/src/auth/service.ts",
    output: dict | None = None,
    returncode: int | None = None,
):
    call = isolated_db.create_tool_call(
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        tool_name=tool_name,
        command="",
        status="completed",
        input_json=json.dumps(
            {"operations": [{"file_path": file_path, "old_text": "old", "new_text": "new"}]}
        ),
        output_json=json.dumps(output or {}),
        risk_level="medium",
        returncode=returncode,
        stdout="ok" if returncode == 0 else "",
        stderr="failed" if returncode not in (None, 0) else "",
    )
    if returncode is not None:
        isolated_db.update_tool_call(
            call.id,
            status="completed",
            returncode=returncode,
            stdout="ok" if returncode == 0 else "",
            stderr="" if returncode == 0 else "failed",
        )
    return call


def _summary(client: TestClient, run_id: str) -> dict:
    response = client.get(f"/api/runs/{run_id}/delivery-summary")
    assert response.status_code == 200, response.text
    return response.json()


def _report(client: TestClient, run_id: str) -> dict:
    response = client.post(f"/api/runs/{run_id}/delivery-report", json={"include_markdown": True})
    assert response.status_code == 200, response.text
    return response.json()


class TestDeliveryReportModuleAwareness:
    def test_summary_without_module_data_is_backward_compatible(self, client, project_run_step):
        _project, run, _step = project_run_step

        summary = _summary(client, run.id)

        assert summary["module_summary"]["has_module_data"] is False
        assert summary["module_summary"]["touched_modules"] == []
        assert summary["readiness"] == "not_started"

    def test_proposal_module_awareness_adds_touched_modules(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )

        module_summary = _summary(client, run.id)["module_summary"]

        assert "Auth" in module_summary["touched_modules"]

    def test_expected_modules_come_from_awareness_and_module_map(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _create_map(project.id)
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={},
        )

        module_summary = _summary(client, run.id)["module_summary"]

        assert "Auth" in module_summary["expected_modules"]
        assert "Auth" in module_summary["touched_modules"]

    def test_unknown_files_are_aggregated(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _create_map(project.id)
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            file_path="scripts/mystery.py",
            output={},
        )

        module_summary = _summary(client, run.id)["module_summary"]

        assert "scripts/mystery.py" in module_summary["unknown_files"]

    def test_module_risks_are_aggregated(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(risks=["auth changes are security-sensitive"]),
            },
        )

        step_summary = _report(client, run.id)["steps"][0]["module_summary"]

        assert "auth changes are security-sensitive" in step_summary["module_risks"]

    def test_module_test_hints_are_aggregated(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(test_hints=["auth unit tests"]),
                "module_policy": _policy(recommended_tests=["login integration tests"]),
            },
        )

        module_summary = _summary(client, run.id)["module_summary"]

        assert "auth unit tests" in module_summary["recommended_tests"]
        assert "login integration tests" in module_summary["recommended_tests"]

    def test_warning_policy_verdicts_are_counted(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(),
                "module_policy": _policy(verdict="warning", reasons=["Review module mismatch."]),
            },
        )

        step_summary = _report(client, run.id)["steps"][0]["module_summary"]
        module_summary = _summary(client, run.id)["module_summary"]

        assert "warning" in step_summary["module_policy_verdicts"]
        assert module_summary["warning_count"] >= 1

    def test_blocked_policy_verdicts_are_counted(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(),
                "module_policy": _policy(verdict="blocked", reasons=["Sensitive module mismatch."]),
            },
        )

        module_summary = _summary(client, run.id)["module_summary"]

        assert module_summary["blocked_policy_count"] == 1

    def test_per_step_module_summary_includes_touched_modules(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )

        step_summary = _report(client, run.id)["steps"][0]["module_summary"]

        assert step_summary["step_id"] == step.id
        assert "Auth" in step_summary["touched_modules"]

    def test_markdown_includes_module_awareness_section(self, client, project_run_step):
        _project, run, _step = project_run_step

        markdown = _report(client, run.id)["markdown_report"]

        assert "## Module Awareness" in markdown

    def test_markdown_includes_touched_modules(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )

        markdown = _report(client, run.id)["markdown_report"]

        assert "Touched modules" in markdown
        assert "Auth" in markdown

    def test_markdown_includes_recommended_module_tests(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(test_hints=["auth unit tests"]),
            },
        )

        markdown = _report(client, run.id)["markdown_report"]

        assert "Recommended module-level tests" in markdown
        assert "auth unit tests" in markdown

    def test_blocked_policy_verdict_is_report_only(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={
                "module_awareness": _awareness(),
                "module_policy": _policy(verdict="blocked", reasons=["Classification-only block."]),
            },
        )

        summary = _summary(client, run.id)

        assert summary["module_summary"]["blocked_policy_count"] == 1
        assert summary["readiness"] != "blocked"

    def test_readiness_not_blocked_by_module_policy_alone(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        shared_output = {
            "module_awareness": _awareness(test_hints=["auth unit tests"]),
            "module_policy": _policy(verdict="blocked", reasons=["Classification-only block."]),
        }
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            tool_name="propose-patch",
            output=shared_output,
        )
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            tool_name="apply-patch",
            output={"files_changed": ["backend/src/auth/service.ts"]},
        )
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            tool_name="run-command",
            output={"returncode": 0},
            returncode=0,
        )

        summary = _summary(client, run.id)

        assert summary["module_summary"]["blocked_policy_count"] == 1
        assert summary["readiness"] in ("ready_for_review", "delivered_with_warnings")

    def test_no_active_module_map_still_produces_valid_summary(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={},
        )

        summary = _summary(client, run.id)

        assert summary["module_summary"]["has_module_data"] is True
        assert summary["module_summary"]["touched_files"] if "touched_files" in summary["module_summary"] else True
        assert summary["readiness"] == "in_progress"

    def test_output_contains_no_file_contents(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )

        data = _report(client, run.id)

        assert "SECRET_FILE_CONTENT_DO_NOT_LEAK" not in json.dumps(data)

    def test_delivery_summary_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )
        before = len(isolated_db.list_tool_calls_for_run(run.id, limit=100))

        _summary(client, run.id)

        assert len(isolated_db.list_tool_calls_for_run(run.id, limit=100)) == before

    def test_delivery_report_creates_no_tool_calls(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )
        before = len(isolated_db.list_tool_calls_for_run(run.id, limit=100))

        _report(client, run.id)

        assert len(isolated_db.list_tool_calls_for_run(run.id, limit=100)) == before

    def test_delivery_report_does_not_mutate_run_or_step(self, client, project_run_step, isolated_db):
        project, run, step = project_run_step
        _make_tool_call(
            isolated_db=isolated_db,
            project_id=project.id,
            run_id=run.id,
            step_id=step.id,
            output={"module_awareness": _awareness()},
        )
        before_run_status = run.status
        before_step_status = step.status

        _report(client, run.id)

        after_run = isolated_db.get_run(run.id)
        after_step = next(item for item in isolated_db.list_run_steps(run.id) if item.id == step.id)
        assert after_run is not None
        assert after_run.status == before_run_status
        assert after_step.status == before_step_status

    def test_delivery_module_summary_has_no_runtime_side_effect_hooks(self):
        from src.api.routes import build_delivery_module_summary

        source = inspect.getsource(build_delivery_module_summary)
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
            "CREATE TABLE",
            "ALTER TABLE",
            "INSERT ",
            "UPDATE ",
            "DELETE ",
        ]
        for token in forbidden:
            assert token not in source
        assert not re.search(r"\bos\.", source)

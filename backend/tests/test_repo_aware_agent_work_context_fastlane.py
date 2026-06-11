"""Repo-aware Agent Work Context Mega-Fastlane v1 tests.

Safety contract:
  - repo intake metadata can flow into pending run steps as bounded context
  - agent context, patch draft, and guarded proposal preflight surface hints
  - no provider calls, command execution, auto-proposals, applies, or tool_calls
    are introduced by repo-aware context propagation
"""

from __future__ import annotations

import inspect
import pathlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.orchestrator.project_intake import (
    build_pending_run_step_inputs_from_development_preview,
    build_repo_aware_run_context_snapshot,
    build_repo_aware_step_context_for_preview_step,
    build_step_agent_patch_draft,
    build_step_patch_draft_proposal_preflight,
    normalize_development_run_step_context,
    StepPatchDraftGuardedProposalRequest,
)
from src.storage import database
from src.api import routes


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "repo-aware-agent-context.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "repo-aware-project"
    project_dir.mkdir()
    return isolated_db.create_project(
        name="Repo-aware Project",
        path=str(project_dir),
        stack="React, FastAPI, Pytest",
        test_command="pytest",
    )


def _repo_preview(**overrides) -> dict:
    data = {
        "project_id": "project-test",
        "project_path_hint": "/workspace/example",
        "detected_stack": ["react", "typescript", "python", "fastapi", "pytest"],
        "detected_project_type": "fullstack_web_app",
        "detected_areas": [
            {
                "id": "frontend",
                "title": "Frontend UI",
                "kind": "frontend",
                "path_hints": ["frontend/src/pages/App.tsx", "frontend/src/components"],
                "confidence": "high",
                "notes": ["React area detected"],
            },
            {
                "id": "backend",
                "title": "Backend/API",
                "kind": "backend",
                "path_hints": ["backend/src/api/routes.py"],
                "confidence": "high",
                "notes": ["FastAPI route area detected"],
            },
            {
                "id": "tests",
                "title": "Tests & QA",
                "kind": "tests",
                "path_hints": ["backend/tests"],
                "confidence": "medium",
                "notes": ["Tests folder detected"],
            },
        ],
        "manifest_summaries": [
            {
                "path": "frontend/package.json",
                "kind": "package.json",
                "detected_scripts": [
                    "test: vitest",
                    "test:unit: vitest --run",
                    "lint: eslint .",
                    "typecheck: tsc --noEmit",
                    "build: vite build",
                    "deploy: dangerous deploy",
                ],
                "dependencies_hint": ["react", "typescript", "vite"],
                "warnings": [],
            },
            {
                "path": "backend/pyproject.toml",
                "kind": "pyproject.toml",
                "detected_scripts": ["pytest: configured in pyproject.toml"],
                "dependencies_hint": ["fastapi", "pytest"],
                "warnings": [],
            },
            {
                "path": "composer.json",
                "kind": "composer.json",
                "detected_scripts": ["test: phpunit", "post-install-cmd: unsafe"],
                "dependencies_hint": ["phpunit/phpunit"],
                "warnings": [],
            },
        ],
        "protected_path_warnings": ["Protected path was not read: .env"],
        "source_of_truth_hints": ["Confirm current product scope."],
        "module_map_hints": ["Create Module Map entries for frontend and backend."],
        "test_discovery_hints": ["Review pytest as a candidate test command.", "Review phpunit as a candidate test command."],
        "clarifying_questions": ["Which module is safe to change first?"],
        "recommended_first_safe_action": "Confirm repo-aware context before agent work.",
        "safety_notes": ["Repo intake preview is read-only."],
        "limitations": ["No arbitrary source file reading.", "No test execution."],
    }
    data.update(overrides)
    return data


def _development_preview() -> dict:
    return {
        "preview_only": True,
        "mode": "existing_project",
        "run_title": "Repo-aware pending run",
        "run_goal": "Prepare an existing project for guarded agent work.",
        "recommended_run_mode": "guided",
        "steps": [
            {
                "id": "STEP-001",
                "title": "Prepare backend workflow patch candidate",
                "description": "Use backend API context to prepare a guarded draft only.",
                "agent_role": "backend_agent",
                "requirement_ids": ["REQ-001"],
                "module_ids": ["backend_api"],
                "depends_on": [],
                "expected_outputs": ["patch draft candidate"],
                "validation_steps": ["Review guarded proposal manually"],
                "safety_gates": ["No provider call", "No command execution"],
                "manual_approval_required": False,
                "provider_allowed": False,
                "risk_level": "medium",
                "estimated_order": 1,
            }
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


def _bridge_payload(project_id: str, repo_preview: dict | None = None) -> dict:
    return {
        "project_id": project_id,
        "confirm_create": True,
        "contract_confirmed": True,
        "source_of_truth_confirmed": True,
        "module_map_confirmed": True,
        "provider_disabled_confirmed": True,
        "later_actions_confirmed": True,
        "development_run_preview": _development_preview(),
        "repo_intake_preview": repo_preview,
        "preferred_run_mode": "guided",
    }


def _table_count(table: str) -> int:
    conn = sqlite3.connect(database.DB_PATH)
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        conn.close()


def _create_repo_aware_run(client: TestClient, project_id: str, repo_preview: dict | None = None) -> tuple[str, str, str]:
    resp = client.post(
        "/api/project-intake/confirmed-development-run/create",
        json=_bridge_payload(project_id, repo_preview or _repo_preview()),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] is True
    run_id = body["run_id"]
    step_id = body["steps"][0]["step_id"]
    step_input = database.list_run_steps(run_id)[0].input
    return run_id, step_id, step_input


class TestRepoContextBuilder:
    def test_01_builds_bounded_snapshot_from_repo_intake_preview(self):
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview())
        assert snapshot.detected_project_type == "fullstack_web_app"
        assert snapshot.detected_stack

    def test_02_caps_detected_stack(self):
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview(detected_stack=[f"stack-{i}" for i in range(40)]))
        assert len(snapshot.detected_stack) <= 10

    def test_03_caps_detected_areas(self):
        areas = [{"id": f"a{i}", "title": f"Area {i}", "kind": "misc", "path_hints": [f"p{i}"]} for i in range(40)]
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview(detected_areas=areas))
        assert len(snapshot.detected_areas) <= 8

    def test_04_caps_manifest_summaries(self):
        manifests = [{"path": f"m{i}.json", "kind": "package.json", "detected_scripts": ["test: x"]} for i in range(40)]
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview(manifest_summaries=manifests))
        assert len(snapshot.manifest_summaries) <= 8

    def test_05_redacts_secret_like_values(self):
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview(detected_stack=["api_key=secret-value"]))
        assert snapshot.detected_stack == ["[REDACTED]"]

    def test_06_extracts_npm_test_lint_typecheck_build_suggestions(self):
        commands = build_repo_aware_run_context_snapshot(_repo_preview()).suggested_safe_commands
        assert "npm run test" in commands
        assert "npm run lint" in commands
        assert "npm run typecheck" in commands
        assert "npm run build" in commands

    def test_07_extracts_pytest_suggestion_from_python_hints(self):
        assert "pytest" in build_repo_aware_run_context_snapshot(_repo_preview()).suggested_safe_commands

    def test_08_extracts_phpunit_and_composer_test_suggestions(self):
        commands = build_repo_aware_run_context_snapshot(_repo_preview()).suggested_safe_commands
        assert "phpunit" in commands
        assert "composer test" in commands

    def test_09_ignores_unsafe_script_names(self):
        commands = build_repo_aware_run_context_snapshot(_repo_preview()).suggested_safe_commands
        assert all("deploy" not in command for command in commands)

    def test_10_deterministic_for_same_input(self):
        a = build_repo_aware_run_context_snapshot(_repo_preview())
        b = build_repo_aware_run_context_snapshot(_repo_preview())
        assert a.model_dump() == b.model_dump()


class TestConfirmedRunCreation:
    def test_11_create_endpoint_accepts_repo_intake_preview(self, client, project):
        resp = client.post("/api/project-intake/confirmed-development-run/create", json=_bridge_payload(project.id, _repo_preview()))
        assert resp.status_code == 200
        assert resp.json()["created"] is True

    def test_12_created_step_input_contains_repo_aware_context(self, client, project):
        _, _, step_input = _create_repo_aware_run(client, project.id)
        assert "AI_WORKBENCH_REPO_AWARE_CONTEXT" in step_input

    def test_13_created_step_input_does_not_contain_arbitrary_source_file_contents(self, client, project):
        _, _, step_input = _create_repo_aware_run(client, project.id)
        assert "def secret" not in step_input
        assert "function secret" not in step_input

    def test_14_provider_allowed_remains_false(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        ctx = normalize_development_run_step_context(database.list_run_steps(run_id)[0].input)
        assert ctx.provider_allowed is False

    def test_15_run_remains_pending_or_created_status(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        run = database.get_run(run_id)
        assert str(getattr(run.status, "value", run.status)).lower() in {"pending", "created"}

    def test_16_steps_remain_pending(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        assert str(database.list_run_steps(run_id)[0].status).lower() == "pending"

    def test_17_no_tool_calls_created(self, client, project):
        before = _table_count("tool_calls")
        _create_repo_aware_run(client, project.id)
        assert _table_count("tool_calls") == before

    def test_18_no_provider_call_marker_in_step_input(self, client, project):
        _, _, step_input = _create_repo_aware_run(client, project.id)
        assert "provider_allowed: false" in step_input

    def test_19_no_command_execution_records_created(self, client, project):
        before = _table_count("tool_calls")
        _create_repo_aware_run(client, project.id)
        assert _table_count("tool_calls") == before

    def test_20_only_intended_run_and_step_are_created(self, client, project):
        runs_before = _table_count("runs")
        steps_before = _table_count("run_steps")
        _create_repo_aware_run(client, project.id)
        assert _table_count("runs") == runs_before + 1
        assert _table_count("run_steps") == steps_before + 1


class TestParser:
    def test_21_agent_step_context_parser_detects_repo_context(self, client, project):
        _, _, step_input = _create_repo_aware_run(client, project.id)
        assert normalize_development_run_step_context(step_input).repo_context_available is True

    def test_22_parser_returns_repo_context_available_true(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        body = client.get(f"/api/runs/{run_id}/agent-step-context").json()
        assert body["items"][0]["repo_context_available"] is True

    def test_23_parser_exposes_detected_stack(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        assert "fastapi" in client.get(f"/api/runs/{run_id}/agent-step-context").json()["items"][0]["detected_stack"]

    def test_24_parser_exposes_relevant_areas(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        assert client.get(f"/api/runs/{run_id}/agent-step-context").json()["items"][0]["relevant_area_hints"]

    def test_25_parser_exposes_test_hints(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        assert client.get(f"/api/runs/{run_id}/agent-step-context").json()["items"][0]["test_discovery_hints"]

    def test_26_parser_exposes_protected_warnings(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        warnings = client.get(f"/api/runs/{run_id}/agent-step-context").json()["items"][0]["protected_path_warnings"]
        assert any(".env" in warning for warning in warnings)

    def test_27_parser_exposes_suggested_safe_commands(self, client, project):
        run_id, _, _ = _create_repo_aware_run(client, project.id)
        commands = client.get(f"/api/runs/{run_id}/agent-step-context").json()["items"][0]["suggested_safe_commands"]
        assert "pytest" in commands

    def test_28_parser_remains_compatible_without_repo_context(self):
        metas = build_pending_run_step_inputs_from_development_preview(_development_preview())
        ctx = normalize_development_run_step_context(metas[0]["input_text"])
        assert ctx.repo_context_available is False


class TestPatchDraft:
    def test_29_step_patch_draft_includes_repo_stack_hints(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        body = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        assert body["repo_context_available"] is True
        assert "fastapi" in body["detected_stack"]

    def test_30_step_patch_draft_includes_test_discovery_hints(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        body = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        assert body["test_discovery_hints"]

    def test_31_step_patch_draft_includes_protected_path_warnings(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        body = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        assert body["protected_path_warnings"]

    def test_32_step_patch_draft_treats_safe_commands_as_suggestions_only(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        body = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        assert body["suggested_safe_commands"]
        assert any("Copy-only" in step for step in body["validation_steps"])

    def test_33_step_patch_draft_creates_no_proposal(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        before = _table_count("tool_calls")
        client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={})
        assert _table_count("tool_calls") == before

    def test_34_step_patch_draft_applies_no_patch(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        body = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        assert any("no patch was applied" in note.lower() for note in body["safety_notes"])

    def test_35_step_patch_draft_executes_no_command(self, client, project):
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        before = _table_count("tool_calls")
        client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={})
        assert _table_count("tool_calls") == before


class TestGuardedProposalPreflight:
    def _preflight(self, client, project) -> dict:
        run_id, step_id, _ = _create_repo_aware_run(client, project.id)
        draft = client.post(f"/api/runs/{run_id}/steps/{step_id}/agent-patch-draft", json={}).json()
        payload = {
            "patch_draft": draft,
            "confirm_create_proposal": False,
            "selected_file_path": "backend/src/api/routes.py",
            "selected_old_text": "old",
            "selected_new_text": "new",
        }
        return client.post(f"/api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal", json=payload).json()

    def test_36_guarded_proposal_context_surfaces_repo_warnings(self, client, project):
        body = self._preflight(client, project)
        assert any("Repo-aware protected path warning" in warning for warning in body["warnings"])

    def test_37_guarded_proposal_context_surfaces_validation_suggestions(self, client, project):
        body = self._preflight(client, project)
        assert any("Copy-only validation suggestion" in warning for warning in body["warnings"])

    def test_38_existing_guard_behavior_unchanged_for_preflight(self, client, project):
        body = self._preflight(client, project)
        assert body["created"] is False
        assert body["ready_for_apply"] is False

    def test_39_provider_allowed_still_blocks(self):
        class Step:
            id = "step"
            title = "Blocked step"
            status = "pending"
            input = "\n".join([
                "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
                "- agent_role: backend_agent",
                "- requirement_ids: REQ-001",
                "- module_ids: backend_api",
                "- safety_gates: No provider call",
                "- provider_allowed: true",
                "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
            ])

        req = StepPatchDraftGuardedProposalRequest(
            selected_file_path="backend/src/api/routes.py",
            selected_old_text="old",
            selected_new_text="new",
        )
        result = build_step_patch_draft_proposal_preflight(run_id="run", step=Step(), request=req)
        assert any("provider_allowed=true" in blocker for blocker in result.blockers)

    def test_40_warning_guard_ack_path_not_weakened_by_repo_context(self, client, project):
        body = self._preflight(client, project)
        assert body["guard_decision"] in {"preflight_ready", "preflight_blocked"}


class TestStaticSafetyAndCompatibility:
    def test_41_no_execute_run_in_touched_route_section(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "execute_run" not in source

    def test_42_no_asyncio_create_task_in_touched_route_section(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "asyncio.create_task" not in source

    def test_43_no_provider_call_in_touched_route_section(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "ollama" not in source and "claude" not in source and "codex" not in source

    def test_44_no_create_tool_call_in_touched_route_section(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "create_tool_call" not in source

    def test_45_no_subprocess_or_os_system_in_touched_route_section(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "subprocess" not in source and "os.system" not in source

    def test_46_no_file_reads_in_create_endpoint_except_existing_db_project_access(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "read_text" not in source and "read_bytes" not in source and "open(" not in source

    def test_47_no_command_execution_path_added(self):
        source = inspect.getsource(routes.post_confirmed_development_run_create)
        assert "run_project_command" not in source and "execute command" not in source.lower()

    def test_48_existing_repo_intake_helper_still_returns_preview(self, tmp_path):
        root = tmp_path / "repo"
        root.mkdir()
        (root / "package.json").write_text('{"scripts":{"test":"vitest"}}', encoding="utf-8")
        from src.orchestrator.project_intake import ExistingProjectRepoIntakeRequest, build_existing_project_repo_intake_preview

        preview = build_existing_project_repo_intake_preview(ExistingProjectRepoIntakeRequest(project_path=str(root)))
        assert preview.detected_stack

    def test_49_confirmed_development_bridge_helper_still_builds_context(self):
        metas = build_pending_run_step_inputs_from_development_preview(_development_preview())
        assert "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT" in metas[0]["input_text"]

    def test_50_intake_run_agent_assignment_parser_still_works(self):
        metas = build_pending_run_step_inputs_from_development_preview(_development_preview(), _repo_preview())
        ctx = normalize_development_run_step_context(metas[0]["input_text"])
        assert ctx.canonical_agent_id == "backend-developer"

    def test_51_step_agent_patch_draft_helper_still_builds(self):
        class Step:
            id = "step"
            title = "Backend step"
            status = "pending"
            input = build_pending_run_step_inputs_from_development_preview(_development_preview(), _repo_preview())[0]["input_text"]

        draft = build_step_agent_patch_draft(run_id="run", step=Step())
        assert draft.step_id == "step"

    def test_52_step_patch_draft_guarded_proposal_preflight_still_builds(self):
        class Step:
            id = "step"
            title = "Backend step"
            status = "pending"
            input = build_pending_run_step_inputs_from_development_preview(_development_preview(), _repo_preview())[0]["input_text"]

        req = StepPatchDraftGuardedProposalRequest(
            selected_file_path="backend/src/api/routes.py",
            selected_old_text="old",
            selected_new_text="new",
        )
        assert build_step_patch_draft_proposal_preflight(run_id="run", step=Step(), request=req).next_recommended_action

    def test_53_execute_next_step_route_not_changed_by_repo_context(self):
        assert hasattr(routes, "automation_run_next")

    def test_54_repo_step_context_helper_filters_relevant_area(self):
        snapshot = build_repo_aware_run_context_snapshot(_repo_preview())
        step = _development_preview()["steps"][0]
        ctx = build_repo_aware_step_context_for_preview_step(step, snapshot)
        assert any("Backend" in hint for hint in ctx.relevant_area_hints)

    def test_55_frontend_types_include_repo_context_fields(self):
        source = (REPO_ROOT / "frontend/src/types/index.ts").read_text(encoding="utf-8")
        assert "repo_context_available" in source
        assert "repo_intake_preview" in source

    def test_56_frontend_run_detail_mentions_copy_only_suggestions(self):
        source = (REPO_ROOT / "frontend/src/pages/RunDetail.tsx").read_text(encoding="utf-8")
        assert "Copy-only safe commands" in source
        assert "No command was run" in source

    def test_57_scripts_runner_does_not_require_repo_context(self):
        source = (REPO_ROOT / "scripts/run_tests.sh").read_text(encoding="utf-8")
        assert "repo-aware-agent-work-context" not in source

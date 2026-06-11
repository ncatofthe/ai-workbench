"""Real Project End-to-End Delivery Dogfood v1.

This suite exercises a realistic SaaS work-management project without provider
calls, autonomous execution, apply, rollback, or schema/runtime changes.
"""

from __future__ import annotations

import importlib
import inspect
import json
from dataclasses import dataclass

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
from src.orchestrator.project_intake import parse_run_step_requirement_context
from src.storage import database
from src.storage.guard_result_storage import create_guard_result
from src.storage.module_map_storage import create_or_update_project_module_map


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app

    return TestClient(app)


@dataclass(frozen=True)
class DogfoodState:
    project: object
    run: object
    confirmed_step: object
    review_step: object


def _write_project_stub(project_dir, relative_path: str, content: str = "old\n") -> None:
    target = project_dir / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _source_of_truth_payload() -> dict:
    return {
        "product_name": "Acme Work Management",
        "product_summary": "Internal SaaS task manager with approvals, scoped uploads, and delivery reporting.",
        "project_intent": "Help operators safely deliver task workflow changes under human supervision.",
        "target_users": ["operations managers", "finance reviewers", "task owners"],
        "goals": [
            "Role-based task access",
            "Review approval before payment",
            "Scoped upload access",
            "Delivery readiness visibility",
        ],
        "non_goals": ["Autonomous production deployment", "Provider-only decision making"],
        "requirements": [
            {
                "id": "REQ-AUTH-001",
                "title": "Role-based task access",
                "description": "Task access must respect authenticated role and session boundaries.",
                "priority": "must",
                "status": "approved",
            },
            {
                "id": "REQ-REVIEW-001",
                "title": "Review approval before payment",
                "description": "Payment-related task changes require review approval before payment release.",
                "priority": "must",
                "status": "approved",
            },
            {
                "id": "REQ-UPLOAD-001",
                "title": "Scoped upload access",
                "description": "Uploaded files must be visible only to authorized task participants.",
                "priority": "must",
                "status": "approved",
            },
            {
                "id": "REQ-DELIVERY-001",
                "title": "Delivery readiness report",
                "description": "Delivery reports must show guard, test, approval, and module readiness.",
                "priority": "should",
                "status": "approved",
            },
        ],
        "constraints": [
            "No automatic apply",
            "No automatic rollback",
            "Sensitive auth and database changes require explicit review",
        ],
        "forbidden_changes": ["Do not weaken approval gates", "Do not expose uploaded private files"],
        "acceptance_criteria": [
            "Guarded proposal remains manual",
            "Module policy is visible to the operator",
            "Delivery report includes module awareness",
        ],
        "architecture_notes": "Backend services are split by auth, reviews, finance, uploads, and reporting modules.",
        "decisions": [
            {
                "id": "DEC-MODULE-POLICY-001",
                "title": "Module policy is classification-only",
                "description": "Policy verdicts are visible to the operator before hard enforcement.",
                "status": "accepted",
            }
        ],
        "assumptions": ["Tests are triggered manually by the operator."],
        "risks": [
            "Auth/session changes are security-sensitive",
            "Database/schema changes can break reporting",
        ],
        "open_questions": ["Should module policy eventually block sensitive mismatches?"],
        "source": "dogfood",
        "status": "active",
    }


def _module(
    *,
    module_id: str,
    name: str,
    slug: str,
    module_type: str,
    paths: list[str],
    key_files: list[str],
    related_requirements: list[str],
    risks: list[str] | None = None,
    test_hints: list[str] | None = None,
) -> ProjectModuleMapItem:
    return ProjectModuleMapItem(
        id=module_id,
        name=name,
        slug=slug,
        module_type=module_type,
        description=f"{name} area for the SaaS work management platform.",
        responsibilities=[f"Owns {name.lower()} behavior for guarded delivery."],
        paths=paths,
        key_files=key_files,
        related_requirements=related_requirements,
        risks=risks or [],
        test_hints=test_hints or [f"{slug} module tests"],
        confidence="high",
    )


def _create_module_map(project_id: str):
    return create_or_update_project_module_map(
        project_id,
        ProjectModuleMapDocument(
            project_id=project_id,
            version=1,
            status="active",
            source="dogfood",
            modules=[
                _module(
                    module_id="mod-auth",
                    name="Auth",
                    slug="auth",
                    module_type="backend",
                    paths=["backend/src/auth"],
                    key_files=["backend/src/auth/session.ts"],
                    related_requirements=["REQ-AUTH-001"],
                    risks=["Auth/session changes are security-sensitive"],
                    test_hints=["auth/session access tests"],
                ),
                _module(
                    module_id="mod-reviews",
                    name="Reviews",
                    slug="reviews",
                    module_type="backend",
                    paths=["backend/src/reviews"],
                    key_files=["backend/src/reviews/approval.ts"],
                    related_requirements=["REQ-REVIEW-001"],
                    test_hints=["review approval tests"],
                ),
                _module(
                    module_id="mod-finance",
                    name="Finance Reports",
                    slug="finance",
                    module_type="backend",
                    paths=["backend/src/finance"],
                    key_files=["backend/src/finance/payments.ts"],
                    related_requirements=["REQ-REVIEW-001", "REQ-DELIVERY-001"],
                    risks=["Payment changes require approval review"],
                    test_hints=["payment approval regression tests"],
                ),
                _module(
                    module_id="mod-uploads",
                    name="Uploads",
                    slug="uploads",
                    module_type="backend",
                    paths=["backend/src/uploads"],
                    key_files=["backend/src/uploads/files.ts"],
                    related_requirements=["REQ-UPLOAD-001"],
                    risks=["Private uploads must stay scoped"],
                    test_hints=["upload authorization tests"],
                ),
                _module(
                    module_id="mod-frontend",
                    name="Frontend UI",
                    slug="frontend",
                    module_type="frontend",
                    paths=["frontend/src"],
                    key_files=["frontend/src/pages/Tasks.tsx"],
                    related_requirements=["REQ-DELIVERY-001"],
                    test_hints=["frontend workflow tests"],
                ),
                _module(
                    module_id="mod-database",
                    name="Database",
                    slug="database",
                    module_type="database",
                    paths=["backend/src/database"],
                    key_files=["backend/src/database/schema.sql"],
                    related_requirements=["REQ-DELIVERY-001"],
                    risks=["Schema changes can affect delivery reporting"],
                    test_hints=["schema compatibility tests"],
                ),
                _module(
                    module_id="mod-contracts",
                    name="Shared Contracts",
                    slug="contracts",
                    module_type="shared",
                    paths=["shared/contracts"],
                    key_files=["shared/contracts/task.ts"],
                    related_requirements=["REQ-AUTH-001", "REQ-REVIEW-001"],
                    test_hints=["contract compatibility tests"],
                ),
            ],
        ),
    )


def _review_step_input() -> str:
    return (
        "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
        "requirement_ids:\n"
        "- REQ-REVIEW-001\n"
        "coverage_status: covered\n"
        "drift_risk: low\n"
        "acceptance_criteria:\n"
        "- Payment-related task changes require review approval.\n"
        "constraints:\n"
        "- Keep proposal and apply manual.\n"
        "source_of_truth_summary: Review approval before payment.\n"
        "END_AI_WORKBENCH_REQUIREMENT_CONTEXT\n"
        "Update payment review approval flow for the SaaS task manager."
    )


@pytest.fixture()
def dogfood_state(client: TestClient, isolated_db, tmp_path) -> DogfoodState:
    project_dir = tmp_path / "acme-work-management"
    project_dir.mkdir()
    for relative_path in (
        "backend/src/auth/session.ts",
        "backend/src/reviews/approval.ts",
        "backend/src/finance/payments.ts",
        "backend/src/uploads/files.ts",
        "backend/src/database/schema.sql",
        "frontend/src/pages/Tasks.tsx",
        "shared/contracts/task.ts",
    ):
        _write_project_stub(project_dir, relative_path)
    _write_project_stub(project_dir, "backend/src/auth/secret.txt", "SECRET_DOGFOOD_DO_NOT_LEAK\n")

    project = isolated_db.create_project("Acme Work Management", str(project_dir))
    sot_response = client.put(f"/api/projects/{project.id}/source-of-truth", json=_source_of_truth_payload())
    assert sot_response.status_code == 200, sot_response.text
    _create_module_map(project.id)

    confirmed = client.post(
        "/api/project-intake/confirmed-run",
        json={
            "idea": (
                "Improve payment review approval workflow for an internal SaaS task manager, "
                "while preserving auth, upload scoping, and delivery reporting requirements."
            ),
            "confirm": True,
            "project_id": project.id,
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    run = isolated_db.get_run(confirmed.json()["run_id"])
    assert run is not None
    steps = isolated_db.list_run_steps(run.id)
    assert steps
    review_step = isolated_db.create_run_step(
        run_id=run.id,
        title="Update review approval before payment",
        input=_review_step_input(),
    )
    return DogfoodState(project=project, run=run, confirmed_step=steps[0], review_step=review_step)


def _agent_result(file_path: str = "backend/src/reviews/approval.ts") -> dict:
    return {
        "summary": "Add a guarded review approval check before payment release.",
        "analysis": "The change belongs in the reviews module and should preserve payment approval gates.",
        "proposed_files": [file_path],
        "patch_intent": "review approval before payment",
        "risks": ["Payment approval flow must not bypass review."],
        "test_suggestions": ["review approval tests"],
        "questions": [],
        "recommended_next_action": "Prepare a guarded patch proposal manually.",
        "can_feed_patch_draft": True,
    }


def _guard_record(
    *,
    run_id: str,
    step_id: str,
    project_id: str,
    guard_id: str,
    file_path: str,
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
) -> str:
    record = build_workflow_guard_result_record(
        id=guard_id,
        project_id=project_id,
        run_id=run_id,
        step_id=step_id,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        input_snapshot=build_guard_input_snapshot(
            proposed_action="Update review approval before payment",
            file_path=file_path,
            patch_summary="Add a guarded approval check before payment release.",
            old_text="old",
            new_text="new",
        ),
        requirement_context_snapshot=build_requirement_context_snapshot(
            requirement_ids=["REQ-REVIEW-001"],
            coverage_status="covered",
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            acceptance_criteria=["Payment changes require review approval."],
            constraints=["Keep apply manual."],
            forbidden_changes=["Do not bypass approval gates."],
            validation_notes=["Dogfood guard record."],
            source_of_truth_summary="Review approval before payment.",
        ),
        result_snapshot=build_guard_result_snapshot(
            decision=decision,
            drift_risk=WorkflowGuardDriftRisk.MEDIUM,
            matched_requirement_ids=["REQ-REVIEW-001"] if decision != WorkflowGuardDecision.BLOCKED else [],
            warnings=["Blocked by dogfood guard."] if decision == WorkflowGuardDecision.BLOCKED else [],
            reasons=["Guard result matches dogfood proposal payload."],
            recommended_next_step="Create proposal manually.",
        ),
    )
    create_guard_result(record)
    return guard_id


def _propose_payload(run_id: str, step_id: str, guard_id: str, file_path: str) -> dict:
    return {
        "run_id": run_id,
        "step_id": step_id,
        "guard_result_id": guard_id,
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


def _successful_sensitive_proposal(client: TestClient, state: DogfoodState) -> dict:
    guard_id = _guard_record(
        run_id=state.run.id,
        step_id=state.review_step.id,
        project_id=state.project.id,
        guard_id=f"guard-auth-{state.review_step.id}",
        file_path="backend/src/auth/session.ts",
    )
    response = client.post(
        f"/api/projects/{state.project.id}/tools/propose-patch",
        json=_propose_payload(state.run.id, state.review_step.id, guard_id, "backend/src/auth/session.ts"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _successful_review_proposal(client: TestClient, state: DogfoodState) -> dict:
    guard_id = _guard_record(
        run_id=state.run.id,
        step_id=state.review_step.id,
        project_id=state.project.id,
        guard_id=f"guard-review-{state.review_step.id}",
        file_path="backend/src/reviews/approval.ts",
    )
    response = client.post(
        f"/api/projects/{state.project.id}/tools/propose-patch",
        json=_propose_payload(state.run.id, state.review_step.id, guard_id, "backend/src/reviews/approval.ts"),
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_apply_and_test_tool_calls(isolated_db, state: DogfoodState, proposal: dict) -> None:
    isolated_db.create_tool_call(
        run_id=state.run.id,
        step_id=state.review_step.id,
        project_id=state.project.id,
        tool_name="apply-patch",
        command="",
        status="completed",
        input_json=json.dumps({"proposal_tool_call_id": proposal["tool_call_id"], "confirm": True}),
        output_json=json.dumps(
            {
                "files_changed": ["backend/src/auth/session.ts"],
                "guard_result_id": proposal.get("guard_result_id"),
                "guard_revalidated": True,
            }
        ),
        risk_level="high",
    )
    test_call = isolated_db.create_tool_call(
        run_id=state.run.id,
        step_id=state.review_step.id,
        project_id=state.project.id,
        tool_name="run-command",
        command="configured test command",
        status="completed",
        input_json=json.dumps({"command": "test", "manual": True}),
        output_json=json.dumps({"returncode": 0}),
        risk_level="medium",
    )
    isolated_db.update_tool_call(test_call.id, status="completed", returncode=0, stdout="ok", stderr="")


def _json_blob(value: object) -> str:
    return json.dumps(value, sort_keys=True)


class TestDogfoodProjectContextSetup:
    def test_creates_realistic_project(self, dogfood_state):
        assert dogfood_state.project.name == "Acme Work Management"
        assert dogfood_state.run.project_id == dogfood_state.project.id

    def test_creates_active_source_of_truth_with_saas_requirements(self, client, dogfood_state):
        response = client.get(f"/api/projects/{dogfood_state.project.id}/source-of-truth")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["found"] is True
        assert {req["id"] for req in data["document"]["requirements"]} >= {
            "REQ-AUTH-001",
            "REQ-REVIEW-001",
            "REQ-UPLOAD-001",
            "REQ-DELIVERY-001",
        }

    def test_creates_active_module_map_with_realistic_modules(self, client, dogfood_state):
        response = client.get(f"/api/projects/{dogfood_state.project.id}/module-map")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["found"] is True
        slugs = {module["slug"] for module in data["document"]["modules"]}
        assert {"auth", "reviews", "finance", "uploads", "frontend", "database", "contracts"} <= slugs

    def test_context_sources_are_read_only_for_context_endpoint(self, client, isolated_db, dogfood_state):
        before = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        response = client.get(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-execution-context"
        )
        assert response.status_code == 200, response.text
        after = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        assert len(after) == len(before)


class TestDogfoodConfirmedRunContext:
    def test_confirmed_run_carries_source_of_truth_context(self, dogfood_state):
        assert "AI_WORKBENCH_REQUIREMENT_CONTEXT" in dogfood_state.confirmed_step.input
        assert "REQ-REVIEW-001" in dogfood_state.confirmed_step.input

    def test_requirement_context_is_parseable(self, dogfood_state):
        parsed = parse_run_step_requirement_context(dogfood_state.review_step.input)
        assert parsed is not None
        assert "REQ-REVIEW-001" in parsed.requirement_ids

    def test_module_map_matches_review_requirement(self, client, dogfood_state):
        response = client.get(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-execution-context"
        )
        assert response.status_code == 200, response.text
        module_context = response.json()["module_context"]
        names = {module["name"] for module in module_context["matched_modules"]}
        assert "Reviews" in names

    def test_confirmed_run_setup_creates_no_initial_tool_calls(self, isolated_db, dogfood_state):
        assert isolated_db.list_tool_calls_for_run(dogfood_state.run.id) == []


class TestDogfoodAgentContext:
    def test_agent_execution_context_includes_module_context(self, client, dogfood_state):
        response = client.get(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-execution-context"
        )
        assert response.status_code == 200, response.text
        module_context = response.json()["module_context"]
        assert module_context["has_active_module_map"] is True
        assert module_context["matched_modules"]

    def test_prompt_preview_includes_project_module_map_context(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-executions/run",
            json={"mode": "dry_run", "persist_result": False},
        )
        assert response.status_code == 200, response.text
        assert "PROJECT MODULE MAP CONTEXT" in response.json()["prompt_preview"]

    def test_provider_mode_still_requires_allow_provider_call(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-executions/run",
            json={"mode": "provider", "allow_provider_call": False},
        )
        assert response.status_code == 403

    def test_context_endpoint_creates_no_tool_calls(self, client, isolated_db, dogfood_state):
        before = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        response = client.get(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-execution-context"
        )
        assert response.status_code == 200, response.text
        after = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        assert len(after) == len(before)


class TestDogfoodPatchDraft:
    def test_agent_result_patch_draft_includes_module_context(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["module_context"]["has_active_module_map"] is True
        assert data["recommended_files_from_module_map"]

    def test_patch_context_includes_project_module_map_patch_context(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        assert "PROJECT MODULE MAP PATCH CONTEXT" in response.json()["patch_context"]

    def test_patch_draft_keeps_old_and_new_text_manual(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        data = response.json()
        assert "old_text" not in data
        assert "new_text" not in data
        assert "Fill `file_path`, `old_text`, and `new_text`" in data["patch_context"]

    def test_patch_draft_creates_no_proposal_or_apply(self, client, isolated_db, dogfood_state):
        before = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        assert response.status_code == 200, response.text
        after = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        assert len(after) == len(before)


class TestDogfoodGuardProposal:
    def test_guarded_proposal_includes_module_awareness(self, client, dogfood_state):
        proposal = _successful_review_proposal(client, dogfood_state)
        assert proposal["module_awareness"]["has_active_module_map"] is True
        assert proposal["module_awareness"]["touched_modules"]

    def test_module_policy_is_present(self, client, dogfood_state):
        proposal = _successful_review_proposal(client, dogfood_state)
        assert proposal["module_policy"] is not None
        assert proposal["module_policy"]["verdict"] in {"allowed", "warning", "blocked"}

    def test_sensitive_module_mismatch_gets_classification_warning_or_blocked(self, client, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        policy = proposal["module_policy"]
        assert policy["verdict"] in {"warning", "blocked"}
        assert "Auth" in policy["sensitive_modules"] or "Auth" in policy["affected_modules"]

    def test_classification_only_verdict_does_not_become_hard_gate(self, client, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        assert proposal["tool_call_id"]
        assert proposal["module_policy"]["verdict"] in {"warning", "blocked"}

    def test_validation_failure_creates_no_proposal_tool_call(self, client, isolated_db, dogfood_state):
        guard_id = _guard_record(
            run_id=dogfood_state.run.id,
            step_id=dogfood_state.review_step.id,
            project_id=dogfood_state.project.id,
            guard_id=f"guard-blocked-{dogfood_state.review_step.id}",
            file_path="backend/src/auth/session.ts",
            decision=WorkflowGuardDecision.BLOCKED,
        )
        before = [
            call
            for call in isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
            if call.tool_name == "propose-patch"
        ]
        response = client.post(
            f"/api/projects/{dogfood_state.project.id}/tools/propose-patch",
            json=_propose_payload(dogfood_state.run.id, dogfood_state.review_step.id, guard_id, "backend/src/auth/session.ts"),
        )
        assert response.status_code in {400, 422}
        after = [
            call
            for call in isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
            if call.tool_name == "propose-patch"
        ]
        assert len(after) == len(before)


class TestDogfoodDelivery:
    def test_delivery_summary_includes_module_summary(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        response = client.get(f"/api/runs/{dogfood_state.run.id}/delivery-summary")
        assert response.status_code == 200, response.text
        assert response.json()["module_summary"]["has_module_data"] is True

    def test_delivery_markdown_includes_module_awareness(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        response = client.post(f"/api/runs/{dogfood_state.run.id}/delivery-report", json={})
        assert response.status_code == 200, response.text
        assert "## Module Awareness" in response.json()["markdown_report"]

    def test_module_policy_counts_are_report_only(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        summary = client.get(f"/api/runs/{dogfood_state.run.id}/delivery-summary").json()
        module_summary = summary["module_summary"]
        assert module_summary["warning_count"] >= 0
        assert module_summary["blocked_policy_count"] >= 0
        assert summary["readiness"] != "blocked"

    def test_delivery_readiness_not_changed_solely_by_module_policy(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        summary = client.get(f"/api/runs/{dogfood_state.run.id}/delivery-summary").json()
        assert summary["readiness"] != "blocked"

    def test_recommended_module_tests_are_visible(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        module_summary = client.get(f"/api/runs/{dogfood_state.run.id}/delivery-summary").json()["module_summary"]
        assert any("test" in item.lower() for item in module_summary["recommended_tests"])


class TestDogfoodCockpit:
    def test_cockpit_returns_source_of_truth_summary(self, client, dogfood_state):
        response = client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        assert response.status_code == 200, response.text
        assert response.json()["source_of_truth"]["available"] is True

    def test_cockpit_returns_module_map_summary(self, client, dogfood_state):
        response = client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        assert response.json()["module_map"]["available"] is True
        assert response.json()["module_map"]["module_count"] >= 7

    def test_cockpit_returns_delivery_run_status(self, client, dogfood_state):
        response = client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        status = response.json()["run"]
        assert status["total_steps"] >= 1
        assert status["readiness"]

    def test_cockpit_returns_module_awareness_summary(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        response = client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        module_awareness = response.json()["module_awareness"]
        assert module_awareness["touched_modules"]
        assert module_awareness["warning_count"] >= 0

    def test_next_safest_action_is_display_only(self, client, isolated_db, dogfood_state):
        before = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        response = client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        assert response.status_code == 200, response.text
        action = response.json()["next_action"]
        assert action["label"]
        assert action["severity"] in {"ready", "info", "warning", "blocked"}
        after = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        assert len(after) == len(before)


class TestDogfoodSafetyBoundaries:
    def test_no_execute_run_in_dogfood_read_only_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.get_agent_execution_context,
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "execute_run(" not in sources

    def test_no_asyncio_create_task_in_dogfood_read_only_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.get_agent_execution_context,
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "asyncio.create_task(" not in sources

    def test_no_subprocess_or_os_command_in_dogfood_read_only_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.get_agent_execution_context,
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "subprocess" not in sources
        assert "os.system" not in sources
        assert "os.popen" not in sources

    def test_no_provider_calls_in_dogfood_read_only_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.get_agent_execution_context,
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "ollama.chat_completion" not in sources
        assert "claude" not in sources.lower()
        assert "codex" not in sources.lower()

    def test_no_file_content_reads_in_patch_draft_or_cockpit_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "open(" not in sources
        assert ".read_text(" not in sources
        assert ".read(" not in sources

    def test_no_apply_project_patch_in_dogfood_reporting_paths(self):
        from src.api import routes

        sources = "\n".join(
            inspect.getsource(func)
            for func in (
                routes.create_agent_result_patch_draft,
                routes.get_run_project_context_cockpit,
            )
        )
        assert "apply_project_patch" not in sources

    def test_no_unexpected_create_tool_call_from_read_only_endpoints(self, client, isolated_db, dogfood_state):
        before = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        client.get(f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-execution-context")
        client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit")
        after = isolated_db.list_tool_calls_for_run(dogfood_state.run.id)
        assert len(after) == len(before)

    def test_no_secret_fixture_content_leaks_to_responses(self, client, isolated_db, dogfood_state):
        proposal = _successful_sensitive_proposal(client, dogfood_state)
        _create_apply_and_test_tool_calls(isolated_db, dogfood_state, proposal)
        responses = [
            client.post(
                f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
                json={"agent_result": _agent_result("backend/src/auth/session.ts")},
            ).json(),
            proposal,
            client.get(f"/api/runs/{dogfood_state.run.id}/delivery-summary").json(),
            client.get(f"/api/runs/{dogfood_state.run.id}/project-context-cockpit").json(),
        ]
        assert "SECRET_DOGFOOD_DO_NOT_LEAK" not in _json_blob(responses)

    def test_no_guard_or_approval_bypass_in_safety_notes(self, client, dogfood_state):
        response = client.post(
            f"/api/runs/{dogfood_state.run.id}/steps/{dogfood_state.review_step.id}/agent-result-patch-draft",
            json={"agent_result": _agent_result()},
        )
        combined = " ".join(response.json().get("safety_notes", [])).lower()
        assert "apply" in combined or "proposal" in combined
        assert "bypass approvals" in combined or "approval" in combined


class TestDogfoodCompatibility:
    def test_existing_real_project_dogfooding_module_imports(self):
        assert importlib.import_module("tests.test_real_project_dogfooding")

    def test_existing_full_delivery_loop_module_imports(self):
        assert importlib.import_module("tests.test_full_delivery_loop")

    def test_existing_project_context_cockpit_module_imports(self):
        assert importlib.import_module("tests.test_project_context_cockpit")

    def test_existing_delivery_report_module_awareness_module_imports(self):
        assert importlib.import_module("tests.test_delivery_report_module_awareness")

    def test_existing_module_aware_guard_policy_module_imports(self):
        assert importlib.import_module("tests.test_module_aware_guard_policy")

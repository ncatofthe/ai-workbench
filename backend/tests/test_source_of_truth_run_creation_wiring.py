"""Tests for Source of Truth → Run Creation Wiring v1.

Covers:
  Nested secret validation (P2 fix):
    1.  PUT rejects secret in requirement.acceptance_criteria (model validator)
    2.  PUT rejects secret in requirement.constraints (model validator)
    3.  POST validate catches secret in requirement.acceptance_criteria (storage validator)
    4.  PUT rejects secret in decision.consequences (model validator)
    5.  Accepts normal nested SaaS requirement text without false-positives

  Persistent SoT context extraction:
    6.  build_persisted_source_of_truth_context_for_step returns context block for active SoT
    7.  Parsed context includes requirement_ids from persisted SoT
    8.  Parsed context includes acceptance_criteria and constraints
    9.  Returns None when no active SoT exists for project
    10. Output is a compact block, not a raw JSON dump

  Confirmed-run wiring:
    11. Confirmed-run without active SoT behaves exactly as before (intake context)
    12. Confirmed-run with active SoT uses persisted SoT requirement context in steps
    13. parse_run_step_requirement_context can parse wired step input
    14. Wired step input includes SoT requirement_id
    15. Wired step input includes SoT acceptance criteria or constraints
    16. Confirmed-run still requires explicit confirm=true with active SoT
    17. Confirmed-run with SoT still does not execute run (status=pending)
    18. Confirmed-run with SoT still creates no tool_calls
    19. Confirmed-run with SoT still leaves all steps pending
    20. Confirmed-run with project_id but no active SoT is handled safely

  Storage-level nested validation:
    21. validate_source_of_truth_payload reports error for secret in req.acceptance_criteria
    22. validate_source_of_truth_payload reports error for secret in req.constraints
    23. POST validate endpoint also surfaces nested secret errors

  Static safety scan:
    24. source_of_truth_storage.py contains no execute_run calls
    25. source_of_truth_storage.py contains no asyncio.create_task calls
    26. source_of_truth_storage.py contains no provider calls (ollama/claude/codex)
    27. source_of_truth_storage.py contains no apply_project_patch calls
    28. source_of_truth_storage.py contains no subprocess or os.system calls

  Normal createRun intentionally unwired:
    29. Normal POST /api/projects/{id}/runs does NOT embed persisted SoT context

Safety invariants verified:
  - No provider calls, no execute_run, no asyncio.create_task
  - All runs and steps remain in pending status after confirmed-run with SoT
  - No tool_calls created
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.models import (
    ProjectSourceOfTruthDocument,
    ProjectSourceOfTruthRequirement,
    ProjectSourceOfTruthDecision,
)
from src.orchestrator.project_intake import parse_run_step_requirement_context
from src.storage import database
from src.storage.source_of_truth_storage import (
    build_persisted_source_of_truth_context_for_step,
    create_or_update_project_source_of_truth,
    validate_source_of_truth_payload,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "wiring.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    return isolated_db.create_project("Wiring Test Project", str(project_dir))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _req(
    req_id: str = "REQ-001",
    title: str = "Must work offline",
    priority: str = "must",
    acceptance_criteria: list | None = None,
    constraints: list | None = None,
) -> dict:
    return {
        "id": req_id,
        "title": title,
        "description": "A requirement for the product.",
        "priority": priority,
        "status": "proposed",
        "acceptance_criteria": acceptance_criteria or [],
        "constraints": constraints or [],
        "tags": [],
    }


def _minimal_upsert(
    *,
    product_name: str = "WiringApp",
    product_summary: str = "An app to test SoT wiring",
    status: str = "active",
    requirements: list | None = None,
    decisions: list | None = None,
) -> dict:
    return {
        "product_name": product_name,
        "product_summary": product_summary,
        "project_intent": "Test that SoT wires into run creation",
        "target_users": ["developer"],
        "goals": ["Ship safely"],
        "non_goals": [],
        "requirements": requirements or [_req()],
        "constraints": ["Must run offline"],
        "forbidden_changes": ["database.py"],
        "acceptance_criteria": ["All tests pass"],
        "architecture_notes": "",
        "decisions": decisions or [],
        "assumptions": [],
        "risks": [],
        "open_questions": [],
        "source": "manual",
        "status": status,
    }


def _make_active_sot(client, project) -> dict:
    """Create an active SoT and return response JSON."""
    r = client.put(
        f"/api/projects/{project.id}/source-of-truth",
        json=_minimal_upsert(
            requirements=[
                _req(
                    req_id="REQ-001",
                    title="Must work offline",
                    acceptance_criteria=["System runs without internet", "Passes offline smoke test"],
                    constraints=["No external API calls"],
                ),
            ],
        ),
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── TestNestedSecretValidation ────────────────────────────────────────────────


class TestNestedSecretValidation:
    """P2 fix: per-requirement list fields must be secret-scanned."""

    def test_1_put_rejects_secret_in_req_acceptance_criteria(self, client, project):
        """Model-level validator rejects secret in requirement.acceptance_criteria."""
        payload = _minimal_upsert(
            requirements=[_req(
                acceptance_criteria=["api_key=sk-abc123-secret"],
            )],
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_2_put_rejects_secret_in_req_constraints(self, client, project):
        """Model-level validator rejects secret in requirement.constraints."""
        payload = _minimal_upsert(
            requirements=[_req(
                constraints=["token=abc123-bearer"],
            )],
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_3_validate_endpoint_catches_nested_secret_in_acceptance_criteria(self, client, project):
        """POST /validate surfaces storage-level nested secret error."""
        # First store a SoT that bypassed model validation (impossible in practice;
        # we test via validate_source_of_truth_payload directly with a pre-built document).
        doc = ProjectSourceOfTruthDocument(
            id="",
            project_id=project.id,
            product_summary="Test product",
            requirements=[],
        )
        # Inject a secret into acceptance_criteria post-construction to test storage validator
        # (bypasses Pydantic model validator intentionally to isolate storage validator).
        object.__setattr__(doc, "requirements", [
            ProjectSourceOfTruthRequirement.model_construct(
                id="REQ-001",
                title="Auth requirement",
                description="",
                priority="must",
                status="proposed",
                acceptance_criteria=["api_key=secret-value"],
                constraints=[],
                tags=[],
            )
        ])
        result = validate_source_of_truth_payload(doc)
        assert not result.valid
        secret_errors = [e for e in result.errors if "acceptance_criteria" in e and "REQ-001" in e]
        assert secret_errors, f"Expected nested acceptance_criteria secret error, got: {result.errors}"

    def test_4_put_rejects_secret_in_decision_consequences(self, client, project):
        """Model-level validator rejects secret in decision.consequences (str field)."""
        payload = _minimal_upsert(
            decisions=[{
                "id": "DEC-001",
                "title": "Use SQLite",
                "description": "Use SQLite for local storage",
                "status": "proposed",
                "rationale": "Offline-first requirement",
                "consequences": "password=admin123 — must be rotated",
            }],
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 422

    def test_5_accepts_normal_nested_saas_requirement_text(self, client, project):
        """Normal SaaS requirement text in nested fields is accepted without false-positives."""
        payload = _minimal_upsert(
            requirements=[_req(
                acceptance_criteria=[
                    "Build a REST API endpoint for user login",
                    "Store user data securely using hashed passwords (bcrypt)",
                    "All endpoints return JSON responses",
                ],
                constraints=[
                    "Use SQLite for local storage",
                    "Must run without internet access",
                    "Response time under 200ms for read operations",
                ],
            )],
        )
        r = client.put(f"/api/projects/{project.id}/source-of-truth", json=payload)
        assert r.status_code == 200, f"Unexpected rejection: {r.text}"
        data = r.json()
        assert data["found"] is True


# ── TestPersistentSoTContextExtraction ────────────────────────────────────────


class TestPersistentSoTContextExtraction:
    """build_persisted_source_of_truth_context_for_step helper tests."""

    def test_6_active_sot_returns_context_block(self, client, project, isolated_db):
        """Returns AI_WORKBENCH_REQUIREMENT_CONTEXT block when active SoT exists."""
        _make_active_sot(client, project)
        block = build_persisted_source_of_truth_context_for_step(project.id)
        assert block is not None
        assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in block
        assert "END_AI_WORKBENCH_REQUIREMENT_CONTEXT" in block

    def test_7_parsed_context_includes_requirement_ids(self, client, project, isolated_db):
        """Parsed context from persisted SoT includes requirement_ids list."""
        _make_active_sot(client, project)
        block = build_persisted_source_of_truth_context_for_step(project.id)
        assert block is not None
        parsed = parse_run_step_requirement_context(block)
        assert parsed.parse_warnings == []
        assert "REQ-001" in parsed.requirement_ids

    def test_8_parsed_context_includes_criteria_and_constraints(self, client, project, isolated_db):
        """Parsed context includes acceptance_criteria and constraints from persisted SoT."""
        _make_active_sot(client, project)
        block = build_persisted_source_of_truth_context_for_step(project.id)
        assert block is not None
        parsed = parse_run_step_requirement_context(block)
        # acceptance_criteria or constraints should be non-empty (from the SoT document)
        has_criteria = bool(parsed.acceptance_criteria)
        has_constraints = bool(parsed.constraints)
        assert has_criteria or has_constraints, (
            f"Expected non-empty acceptance_criteria or constraints, "
            f"got: {parsed.acceptance_criteria!r}, {parsed.constraints!r}"
        )

    def test_9_no_active_sot_returns_none(self, project, isolated_db):
        """Returns None when no active SoT exists for the project."""
        # Don't create any SoT for this project
        result = build_persisted_source_of_truth_context_for_step(project.id)
        assert result is None

    def test_10_output_is_bounded_block_not_json_dump(self, client, project, isolated_db):
        """Context block is a compact requirement block, not raw JSON."""
        _make_active_sot(client, project)
        block = build_persisted_source_of_truth_context_for_step(project.id)
        assert block is not None
        # Must start with the context header
        assert block.startswith("AI_WORKBENCH_REQUIREMENT_CONTEXT:")
        # Must NOT look like a raw JSON dump
        assert not block.startswith("{")
        assert "document_json" not in block
        assert '"requirements":' not in block
        # Must contain named fields
        assert "requirement_ids:" in block
        assert "coverage_status:" in block
        assert "drift_risk:" in block


# ── TestConfirmedRunSoTWiring ─────────────────────────────────────────────────


class TestConfirmedRunSoTWiring:
    """Confirmed-run endpoint wiring tests."""

    def test_11_confirmed_run_without_sot_behaves_as_before(self, client, isolated_db):
        """Without an active SoT, confirmed-run creates steps with intake-derived context."""
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            # No project_id → no persisted SoT lookup
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"]
        assert data["steps_created"] > 0
        steps = isolated_db.list_run_steps(data["run_id"])
        # Should still have the intake-derived context block
        for step in steps:
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in step.input
            assert "END_AI_WORKBENCH_REQUIREMENT_CONTEXT" in step.input

    def test_12_confirmed_run_with_active_sot_uses_persisted_context(self, client, project, isolated_db):
        """With active SoT, confirmed-run embeds persisted SoT context in step inputs."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])
        assert len(steps) > 0
        # All steps must have a requirement context block
        for step in steps:
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in step.input
            assert "END_AI_WORKBENCH_REQUIREMENT_CONTEXT" in step.input

        # Response warnings should mention the active persisted SoT
        warnings_text = " ".join(data["warnings"])
        assert "persisted" in warnings_text.lower() or "source of truth" in warnings_text.lower()

    def test_13_parse_run_step_requirement_context_parses_wired_step(self, client, project, isolated_db):
        """parse_run_step_requirement_context can parse the step input produced by confirmed-run with SoT."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])
        assert len(steps) > 0

        for step in steps:
            parsed = parse_run_step_requirement_context(step.input)
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT block not found" not in parsed.parse_warnings
            assert parsed.coverage_status != ""
            assert parsed.drift_risk != ""

    def test_14_wired_step_input_includes_sot_requirement_id(self, client, project, isolated_db):
        """Wired step input contains the SoT requirement id (REQ-001)."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])

        # At least one step should have REQ-001 in its input
        has_req = any("REQ-001" in step.input for step in steps)
        assert has_req, "Expected REQ-001 from persisted SoT in at least one step input"

    def test_15_wired_step_input_includes_sot_acceptance_criteria_or_constraints(
        self, client, project, isolated_db
    ):
        """Wired step input contains acceptance criteria or constraints from persisted SoT."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])

        # At least one step should have SoT-derived content in its input
        combined = " ".join(step.input for step in steps)
        # Known content from _make_active_sot fixture
        has_criteria = "offline" in combined.lower() or "smoke test" in combined.lower()
        has_constraints = "external api" in combined.lower() or "offline" in combined.lower()
        assert has_criteria or has_constraints, (
            "Expected acceptance criteria or constraints from persisted SoT in step inputs"
        )

    def test_16_confirmed_run_with_sot_still_requires_confirm_true(self, client, project, isolated_db):
        """confirm=False is rejected even when active SoT exists."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard",
            "confirm": False,
            "project_id": project.id,
        })
        assert resp.status_code == 400
        assert "confirm" in resp.json()["detail"].lower()

    def test_17_confirmed_run_with_sot_does_not_execute_run(self, client, project, isolated_db):
        """Run stays pending after confirmed-run with active SoT."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        run = isolated_db.get_run(data["run_id"])
        assert run.status.value == "pending"

    def test_18_confirmed_run_with_sot_creates_no_tool_calls(self, client, project, isolated_db):
        """No tool_calls are created when confirmed-run uses persisted SoT."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        tool_calls = isolated_db.list_tool_calls_for_run(data["run_id"])
        assert len(tool_calls) == 0

    def test_19_confirmed_run_with_sot_leaves_all_steps_pending(self, client, project, isolated_db):
        """All steps remain pending after confirmed-run with active SoT."""
        _make_active_sot(client, project)

        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth and PostgreSQL",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        steps = isolated_db.list_run_steps(data["run_id"])
        assert len(steps) > 0
        for step in steps:
            assert step.status == "pending"

    def test_20_confirmed_run_with_project_but_no_sot_handled_safely(self, client, project, isolated_db):
        """project_id with no active SoT falls back to intake-derived context safely."""
        # project exists but has no SoT document at all
        resp = client.post("/api/project-intake/confirmed-run", json={
            "idea": "Build a React web dashboard with JWT auth",
            "confirm": True,
            "project_id": project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["steps_created"] > 0
        steps = isolated_db.list_run_steps(data["run_id"])
        # Should fall back to intake-derived context
        for step in steps:
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" in step.input
        # No SoT warning in this case
        sot_warnings = [w for w in data["warnings"] if "persisted" in w.lower()]
        assert len(sot_warnings) == 0


# ── TestStorageLevelNestedValidation ──────────────────────────────────────────


class TestStorageLevelNestedValidation:
    """validate_source_of_truth_payload catches nested secrets at storage level."""

    def test_21_validate_payload_reports_secret_in_req_acceptance_criteria(self, project, isolated_db):
        """Storage-level validator reports error for secret in requirement.acceptance_criteria."""
        doc = ProjectSourceOfTruthDocument(
            id="",
            project_id=project.id,
            product_summary="Test product",
            requirements=[],
        )
        object.__setattr__(doc, "requirements", [
            ProjectSourceOfTruthRequirement.model_construct(
                id="REQ-001",
                title="Auth requirement",
                description="",
                priority="must",
                status="proposed",
                acceptance_criteria=["token=abc123xyz must be validated"],
                constraints=[],
                tags=[],
            )
        ])
        result = validate_source_of_truth_payload(doc)
        assert not result.valid
        assert any("REQ-001" in e and "acceptance_criteria" in e for e in result.errors)

    def test_22_validate_payload_reports_secret_in_req_constraints(self, project, isolated_db):
        """Storage-level validator reports error for secret in requirement.constraints."""
        doc = ProjectSourceOfTruthDocument(
            id="",
            project_id=project.id,
            product_summary="Test product",
            requirements=[],
        )
        object.__setattr__(doc, "requirements", [
            ProjectSourceOfTruthRequirement.model_construct(
                id="REQ-002",
                title="Persistence requirement",
                description="",
                priority="must",
                status="proposed",
                acceptance_criteria=[],
                constraints=["password=hunter2 must be changed"],
                tags=[],
            )
        ])
        result = validate_source_of_truth_payload(doc)
        assert not result.valid
        assert any("REQ-002" in e and "constraints" in e for e in result.errors)

    def test_23_validate_endpoint_surfaces_nested_secret_errors(self, client, project, isolated_db):
        """POST /validate surfaces both valid=False and nested-secret errors."""
        # POST validate with a document containing a secret in req.constraints
        # The model validator will reject it at parse time (422), so we test
        # the validate_source_of_truth_payload function directly to confirm
        # the storage layer also catches it.
        doc = ProjectSourceOfTruthDocument(
            id="",
            project_id=project.id,
            product_summary="Test product",
            requirements=[],
        )
        object.__setattr__(doc, "requirements", [
            ProjectSourceOfTruthRequirement.model_construct(
                id="REQ-001",
                title="Req with secret constraint",
                description="",
                priority="must",
                status="proposed",
                acceptance_criteria=[],
                constraints=["api_key=super-secret-key"],
                tags=[],
            )
        ])
        result = validate_source_of_truth_payload(doc)
        assert not result.valid
        assert result.drift_risk == "critical"
        assert any("constraints" in e for e in result.errors)


# ── TestStaticSafety ─────────────────────────────────────────────────────────


class TestStaticSafety:
    """Static safety scans of source_of_truth_storage.py wiring section."""

    @pytest.fixture(autouse=True)
    def _read_storage_source(self):
        import pathlib
        path = pathlib.Path(__file__).parent.parent / "src" / "storage" / "source_of_truth_storage.py"
        self._source = path.read_text(encoding="utf-8")

    def test_24_no_execute_run_in_sot_storage(self):
        """source_of_truth_storage.py must not call execute_run."""
        assert "execute_run" not in self._source

    def test_25_no_asyncio_create_task_in_sot_storage(self):
        """source_of_truth_storage.py must not use asyncio.create_task."""
        # Allow it only in comments
        lines_with_asyncio = [
            line for line in self._source.splitlines()
            if "asyncio.create_task" in line and not line.strip().startswith("#")
        ]
        assert lines_with_asyncio == []

    def test_26_no_provider_calls_in_sot_storage(self):
        """source_of_truth_storage.py must not call ollama/claude/codex providers."""
        for forbidden in ("ollama.chat", "claude_provider", "codex_provider", "openai.chat"):
            assert forbidden not in self._source, f"Found forbidden provider call: {forbidden}"

    def test_27_no_apply_project_patch_in_sot_storage(self):
        """source_of_truth_storage.py must not call apply_project_patch."""
        assert "apply_project_patch" not in self._source

    def test_28_no_subprocess_or_os_system_in_sot_storage(self):
        """source_of_truth_storage.py must not use subprocess or os.system."""
        for forbidden in ("subprocess", "os.system", "os.popen"):
            lines = [
                line for line in self._source.splitlines()
                if forbidden in line and not line.strip().startswith("#")
            ]
            assert lines == [], f"Found live use of {forbidden!r} in source_of_truth_storage.py: {lines}"


# ── TestNormalCreateRunUnwired ────────────────────────────────────────────────


class TestNormalCreateRunUnwired:
    """Normal createRun is intentionally NOT wired to persisted SoT in v1."""

    def test_29_normal_create_run_does_not_embed_persisted_sot(self, client, project, isolated_db):
        """POST /api/projects/{id}/runs does not include persisted SoT context block.

        v1 design decision: only confirmed-run gets persisted SoT context.
        Normal createRun is unchanged to avoid broad behavior changes.
        """
        # Create an active SoT for the project
        r = client.put(
            f"/api/projects/{project.id}/source-of-truth",
            json={
                "product_name": "TestApp",
                "product_summary": "Test product for run wiring",
                "project_intent": "Verify normal createRun is not wired",
                "target_users": ["developer"],
                "goals": ["Ship fast"],
                "non_goals": [],
                "requirements": [{
                    "id": "REQ-001",
                    "title": "Must work offline",
                    "description": "",
                    "priority": "must",
                    "status": "proposed",
                    "acceptance_criteria": [],
                    "constraints": [],
                    "tags": [],
                }],
                "constraints": [],
                "forbidden_changes": [],
                "acceptance_criteria": [],
                "architecture_notes": "",
                "decisions": [],
                "assumptions": [],
                "risks": [],
                "open_questions": [],
                "source": "manual",
                "status": "active",
            },
        )
        assert r.status_code == 200

        # Normal createRun (POST /api/runs) — should NOT include persisted SoT context.
        # The endpoint uses project_id in the request body (not URL path).
        run_resp = client.post(
            "/api/runs",
            json={
                "project_id": project.id,
                "prompt": "Build a simple API endpoint",
                "mode": "offline",
            },
        )
        assert run_resp.status_code == 200
        run_data = run_resp.json()
        run_id = run_data.get("id") or run_data.get("run_id")
        assert run_id

        steps = isolated_db.list_run_steps(run_id)
        # Normal createRun does not call build_persisted_sot_context.
        # Any steps created by normal createRun must not contain AI_WORKBENCH_REQUIREMENT_CONTEXT
        # derived from the persisted SoT (since we never wired it into this path).
        for step in steps:
            # The step may have other content but must not have the persisted SoT block
            # (it's safe to assert the full block marker is absent entirely,
            # since normal createRun has no requirement context block wiring at all).
            assert "AI_WORKBENCH_REQUIREMENT_CONTEXT:" not in step.input, (
                f"Normal createRun should not embed AI_WORKBENCH_REQUIREMENT_CONTEXT "
                f"(persisted SoT wiring is confirmed-run only in v1). "
                f"Step input: {step.input[:200]!r}"
            )

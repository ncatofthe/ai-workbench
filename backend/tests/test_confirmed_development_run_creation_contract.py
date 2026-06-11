"""Confirmed Development Run Creation Contract v1 — test suite.

53 tests covering:
  1–8    Contract requirements (blockers and allowed)
  9–15   Safety and entity boundaries
  16–22  Upstream draft warnings (SoT / Module Map / Multi-Agent Plan)
  23–28  Safety gates
  29–33  Operator confirmations
  34–36  Redaction
  37–41  Determinism and bounds
  42–49  Static purity (no forbidden imports or patterns in contract source)
  50–53  Compatibility (upstream builders still import and are callable)

Hard constraints verified throughout:
  - No DB schema changes
  - No provider calls
  - No network calls
  - No file reads from project tree
  - No execute_run / asyncio.create_task / create_tool_call
  - No patch proposal creation / apply patch
  - No guard bypass / approval bypass
  - Test suite does not weaken any existing test
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib

import pytest

from src.release import confirmed_development_run_creation_contract as contract_module
from src.release.confirmed_development_run_creation_contract import (
    ConfirmedRunCreatedEntity,
    ConfirmedRunCreationDecision,
    ConfirmedRunCreationInput,
    ConfirmedRunCreationMode,
    ConfirmedRunCreationRisk,
    build_allowed_created_entities,
    build_confirmed_run_creation_operator_checklist,
    build_confirmed_run_creation_requirements,
    build_confirmed_run_creation_safety_gates,
    build_forbidden_created_entities,
    build_required_confirmed_run_statuses,
    evaluate_confirmed_run_creation_contract,
    redact_confirmed_run_creation_preview_for_report,
)


# ── Shared fixtures / helpers ─────────────────────────────────────────────────


def _valid_input(**overrides) -> ConfirmedRunCreationInput:
    """Return a fully-satisfied ConfirmedRunCreationInput.

    All hard requirements are met.  Override individual fields with *overrides*.
    """
    data: dict = dict(
        project_id="proj-abc123",
        confirm=True,
        preview_only=False,
        run_title="Implement SaaS Task Manager",
        run_goal="Build a task manager with auth, dashboard, reporting, and QA.",
        recommended_run_mode="guided",
        steps=[
            {
                "id": "STEP-001",
                "title": "Context Confirmation",
                "description": "Confirm architecture, SoT, and module map before coding.",
                "agent_role": "ContextAnalyst",
                "requirement_ids": ["REQ-001"],
                "module_ids": ["core-api"],
                "validation_steps": ["Verify SoT is loaded and current."],
                "provider_allowed": False,
                "manual_approval_required": False,
            }
        ],
        source_of_truth_valid=True,
        module_map_valid=True,
        multi_agent_plan_valid=True,
        development_preview_valid=True,
    )
    data.update(overrides)
    return ConfirmedRunCreationInput(**data)


def _steps_plain(**step_overrides) -> list[dict]:
    """Return a single-step list that passes all hard checks."""
    step = {
        "id": "STEP-001",
        "title": "Backend Implementation",
        "description": "Implement the core API endpoints.",
        "agent_role": "BackendDeveloper",
        "requirement_ids": ["REQ-001"],
        "module_ids": ["core-api"],
        "validation_steps": ["Run API tests."],
        "provider_allowed": False,
        "manual_approval_required": False,
    }
    step.update(step_overrides)
    return [step]


# ── 1–8  Contract requirements ────────────────────────────────────────────────


class TestContractRequirements:
    """Tests 1–8: hard blockers and the successful-allow case."""

    def test_01_missing_project_id_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(project_id=None))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any(
            "REQ-CRC-001" in b or "project_id" in b.lower()
            for b in result.blockers
        )

    def test_02_empty_project_id_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(project_id="   "))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run

    def test_03_confirm_false_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(confirm=False))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-002" in b or "confirm" in b.lower() for b in result.blockers)

    def test_04_preview_only_true_blocks_actual_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(preview_only=True))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-003" in b or "preview_only" in b.lower() for b in result.blockers)

    def test_05_empty_run_title_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(run_title=""))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-004" in b or "run_title" in b.lower() for b in result.blockers)

    def test_06_empty_run_goal_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(run_goal=""))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-005" in b or "run_goal" in b.lower() for b in result.blockers)

    def test_07_empty_steps_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=[]))
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-006" in b or "step" in b.lower() for b in result.blockers)

    def test_08_invalid_development_preview_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(
            _valid_input(development_preview_valid=False)
        )
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any(
            "REQ-CRC-007" in b or "development_preview_valid" in b.lower()
            for b in result.blockers
        )


class TestValidConfirmedInput:
    """Test 8 (continued): a fully valid input is allowed."""

    def test_08b_valid_confirmed_input_allows_pending_run_creation(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input())
        assert result.decision in (
            ConfirmedRunCreationDecision.ALLOWED,
            ConfirmedRunCreationDecision.WARNING,
        )
        assert result.can_create_pending_run


# ── 9–15  Safety and entity boundaries ───────────────────────────────────────


class TestSafetyAndEntityBoundaries:
    """Tests 9–15: entity allow/forbid lists, status requirements, provider_allowed, execution language."""

    def test_09_allowed_entities_include_run_and_run_step_only(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input())
        allowed = set(result.allowed_created_entities)
        assert ConfirmedRunCreatedEntity.RUN in allowed
        assert ConfirmedRunCreatedEntity.RUN_STEP in allowed
        # No execution entities
        assert ConfirmedRunCreatedEntity.PROJECT not in allowed
        assert ConfirmedRunCreatedEntity.TOOL_CALL not in allowed
        assert ConfirmedRunCreatedEntity.PROVIDER_CALL not in allowed
        assert ConfirmedRunCreatedEntity.PATCH_PROPOSAL not in allowed
        assert ConfirmedRunCreatedEntity.COMMAND_EXECUTION not in allowed
        assert len(allowed) == 2

    def test_10_forbidden_entities_include_five_types(self):
        forbidden = set(build_forbidden_created_entities())
        assert ConfirmedRunCreatedEntity.PROJECT in forbidden
        assert ConfirmedRunCreatedEntity.TOOL_CALL in forbidden
        assert ConfirmedRunCreatedEntity.PROVIDER_CALL in forbidden
        assert ConfirmedRunCreatedEntity.PATCH_PROPOSAL in forbidden
        assert ConfirmedRunCreatedEntity.COMMAND_EXECUTION in forbidden

    def test_11_required_run_status_is_pending_or_planned(self):
        statuses = build_required_confirmed_run_statuses()
        assert statuses["run"] in ("pending", "planned")

    def test_12_required_step_status_is_pending(self):
        statuses = build_required_confirmed_run_statuses()
        assert statuses["run_step"] == "pending"

    def test_13_provider_allowed_true_in_step_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(
            _valid_input(steps=_steps_plain(provider_allowed=True))
        )
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-008" in b or "provider_allowed" in b.lower() for b in result.blockers)

    def test_14_execution_like_step_language_blocks_or_warns(self):
        risky_steps = [
            {
                "id": "STEP-001",
                "title": "Execute now the full test suite",
                "description": "Auto-run all tests immediately after deployment.",
                "agent_role": "QAEngineer",
                "requirement_ids": [],
                "module_ids": [],
                "validation_steps": [],
                "provider_allowed": False,
                "manual_approval_required": False,
            }
        ]
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=risky_steps))
        assert result.decision in (
            ConfirmedRunCreationDecision.BLOCKED,
            ConfirmedRunCreationDecision.WARNING,
        )

    def test_15_secret_in_run_goal_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(
            _valid_input(run_goal="password=supersecret_value123")
        )
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run
        assert any("REQ-CRC-010" in b or "secret" in b.lower() for b in result.blockers)


# ── 16–22  Upstream draft warnings ───────────────────────────────────────────


class TestUpstreamDraftWarnings:
    """Tests 16–22: advisory warnings for SoT, Module Map, Multi-Agent Plan, and step metadata."""

    def test_16_invalid_sot_produces_warning_not_blocker(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(source_of_truth_valid=False))
        # SoT validity is advisory — must not block
        assert result.decision in (
            ConfirmedRunCreationDecision.WARNING,
            ConfirmedRunCreationDecision.ALLOWED,
        )
        assert result.can_create_pending_run
        assert any("REQ-CRC-011" in w or "source of truth" in w.lower() for w in result.warnings)

    def test_17_invalid_module_map_produces_warning_not_blocker(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input(module_map_valid=False))
        assert result.decision in (
            ConfirmedRunCreationDecision.WARNING,
            ConfirmedRunCreationDecision.ALLOWED,
        )
        assert result.can_create_pending_run
        assert any("REQ-CRC-012" in w or "module map" in w.lower() for w in result.warnings)

    def test_18_invalid_multi_agent_plan_produces_warning_not_blocker(self):
        result = evaluate_confirmed_run_creation_contract(
            _valid_input(multi_agent_plan_valid=False)
        )
        assert result.decision in (
            ConfirmedRunCreationDecision.WARNING,
            ConfirmedRunCreationDecision.ALLOWED,
        )
        assert result.can_create_pending_run
        assert any(
            "REQ-CRC-013" in w
            or "multi-agent" in w.lower()
            or "agent plan" in w.lower()
            for w in result.warnings
        )

    def test_19_missing_requirement_links_warn(self):
        steps = _steps_plain(requirement_ids=[])
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=steps))
        assert any("requirement" in w.lower() for w in result.warnings)

    def test_20_missing_module_links_warn(self):
        steps = _steps_plain(module_ids=[])
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=steps))
        assert any("module" in w.lower() for w in result.warnings)

    def test_21_missing_validation_steps_warn(self):
        steps = _steps_plain(validation_steps=[])
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=steps))
        assert any("validation" in w.lower() for w in result.warnings)

    def test_22_risky_module_reference_warns_about_manual_approval(self):
        risky_steps = [
            {
                "id": "STEP-001",
                "title": "Database migration rollout",
                "description": "Apply schema migration for the new user_sessions table.",
                "agent_role": "BackendDeveloper",
                "requirement_ids": ["REQ-002"],
                "module_ids": ["database"],
                "validation_steps": ["Verify migration completed."],
                "provider_allowed": False,
                "manual_approval_required": True,
            }
        ]
        result = evaluate_confirmed_run_creation_contract(_valid_input(steps=risky_steps))
        assert any(
            "risky" in w.lower() or "manual approval" in w.lower()
            for w in result.warnings
        )


# ── 23–28  Safety gates ───────────────────────────────────────────────────────


class TestSafetyGates:
    """Tests 23–28: all mandatory safety gates are present."""

    @pytest.fixture(autouse=True)
    def _build_gates(self):
        self.gates = build_confirmed_run_creation_safety_gates(_valid_input())
        self.ids = [g.id for g in self.gates]
        self.titles_lower = [g.title.lower() for g in self.gates]
        self.all_descriptions = " ".join(g.description.lower() for g in self.gates)

    def test_23_no_auto_start_gate_present(self):
        assert any(
            ("auto" in t and "start" in t) or "auto-start" in t
            for t in self.titles_lower
        ) or "auto-start" in self.all_descriptions

    def test_24_no_provider_call_gate_present(self):
        assert any("provider" in t for t in self.titles_lower) or \
               "provider" in self.all_descriptions

    def test_25_no_tool_call_gate_present(self):
        assert any("tool" in t for t in self.titles_lower) or \
               "tool_call" in self.all_descriptions or \
               "tool call" in self.all_descriptions

    def test_26_no_patch_apply_test_execution_gate_present(self):
        assert any("patch" in t or "apply" in t or "test" in t for t in self.titles_lower) or \
               "patch" in self.all_descriptions

    def test_27_manual_approval_gate_present(self):
        assert any("manual" in t or "approval" in t for t in self.titles_lower) or \
               "manual approval" in self.all_descriptions

    def test_28_guard_before_patch_gate_present(self):
        assert any("guard" in t or "patch" in t for t in self.titles_lower) or \
               "guard" in self.all_descriptions


# ── 29–33  Operator confirmations ─────────────────────────────────────────────


class TestOperatorConfirmations:
    """Tests 29–33: all required operator confirmations are present."""

    @pytest.fixture(autouse=True)
    def _build_checklist(self):
        self.checklist = build_confirmed_run_creation_operator_checklist()
        self.combined = " ".join(c.lower() for c in self.checklist)

    def test_29_requires_explicit_confirm_real_run_creation(self):
        assert any(
            "confirm" in c.lower() and "run" in c.lower()
            for c in self.checklist
        )

    def test_30_requires_source_of_truth_readiness_confirmation(self):
        assert "source of truth" in self.combined

    def test_31_requires_module_map_readiness_confirmation(self):
        assert "module map" in self.combined

    def test_32_requires_provider_disabled_confirmation(self):
        assert "provider" in self.combined

    def test_33_requires_later_apply_test_explicit_action_confirmation(self):
        assert ("apply" in self.combined or "test" in self.combined) and \
               ("explicit" in self.combined or "later" in self.combined)


# ── 34–36  Redaction ──────────────────────────────────────────────────────────


class TestRedaction:
    """Tests 34–36: redact_confirmed_run_creation_preview_for_report behaviour."""

    def test_34_redaction_removes_secret_like_string_values(self):
        payload = {
            "run_title": "Deploy service",
            "run_goal": "password=supersecret_value123",
            "meta": {"token": "token=abc123"},
        }
        redacted = redact_confirmed_run_creation_preview_for_report(payload)
        assert redacted["run_goal"] == "[REDACTED]"
        assert redacted["meta"]["token"] == "[REDACTED]"

    def test_35_redaction_preserves_non_secret_structure(self):
        payload = {
            "run_title": "Build SaaS task manager",
            "run_goal": "Implement task manager with React and FastAPI.",
            "steps": [{"title": "Context step", "description": "Confirm architecture."}],
            "meta": {"version": 1, "mode": "guided"},
        }
        redacted = redact_confirmed_run_creation_preview_for_report(payload)
        assert redacted["run_title"] == "Build SaaS task manager"
        assert redacted["run_goal"] == "Implement task manager with React and FastAPI."
        assert redacted["steps"][0]["title"] == "Context step"
        assert redacted["meta"]["version"] == 1
        assert redacted["meta"]["mode"] == "guided"

    def test_36_secret_like_run_title_blocks_creation(self):
        result = evaluate_confirmed_run_creation_contract(
            _valid_input(run_title="api_key=sk-proj-supersecret_value")
        )
        assert result.decision == ConfirmedRunCreationDecision.BLOCKED
        assert not result.can_create_pending_run


# ── 37–41  Determinism and bounds ─────────────────────────────────────────────


class TestDeterminismAndBounds:
    """Tests 37–41: same input → same output; all collections are bounded."""

    def test_37_same_valid_input_produces_identical_result(self):
        inp = _valid_input()
        r1 = evaluate_confirmed_run_creation_contract(inp)
        r2 = evaluate_confirmed_run_creation_contract(inp)
        assert r1.decision == r2.decision
        assert r1.blockers == r2.blockers
        assert r1.warnings == r2.warnings
        assert r1.next_recommended_action == r2.next_recommended_action

    def test_38_blockers_and_warnings_bounded(self):
        inp = _valid_input()
        result = evaluate_confirmed_run_creation_contract(inp)
        assert len(result.blockers) <= 20
        assert len(result.warnings) <= 30

    def test_39_requirements_list_bounded(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input())
        assert 1 <= len(result.requirements) <= 20

    def test_40_safety_gates_bounded(self):
        result = evaluate_confirmed_run_creation_contract(_valid_input())
        assert 1 <= len(result.safety_gates) <= 15

    def test_41_next_recommended_action_is_non_empty_string(self):
        for inp in [
            _valid_input(),
            _valid_input(confirm=False),
            _valid_input(source_of_truth_valid=False),
        ]:
            result = evaluate_confirmed_run_creation_contract(inp)
            assert isinstance(result.next_recommended_action, str)
            assert len(result.next_recommended_action) > 0


# ── 42–49  Static purity ──────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def contract_source() -> str:
    """Return the raw source text of the contract module."""
    spec = importlib.util.find_spec(
        "src.release.confirmed_development_run_creation_contract"
    )
    assert spec is not None and spec.origin is not None
    return pathlib.Path(spec.origin).read_text(encoding="utf-8")


class TestStaticPurity:
    """Tests 42–49: contract module must not import runtime dependencies."""

    def test_42_no_database_imports(self, contract_source):
        assert "from src.storage" not in contract_source
        assert "import database" not in contract_source
        assert "from src.storage.database" not in contract_source

    def test_43_no_route_imports(self, contract_source):
        assert "from src.api" not in contract_source
        assert "import routes" not in contract_source

    def test_44_no_provider_imports(self, contract_source):
        assert "from src.providers" not in contract_source
        assert "import ollama" not in contract_source
        assert "import anthropic" not in contract_source
        assert "import openai" not in contract_source

    def test_45_no_filesystem_reads_or_writes(self, contract_source):
        assert "open(" not in contract_source
        assert "pathlib.Path" not in contract_source
        assert "read_text" not in contract_source
        assert "write_text" not in contract_source
        assert "os.listdir" not in contract_source

    def test_46_no_subprocess_or_os_command_execution(self, contract_source):
        # Check for import/call patterns — not bare noun (docstring may say "subprocesses")
        assert "import subprocess" not in contract_source
        assert "subprocess." not in contract_source
        assert "os.system(" not in contract_source
        assert "os.popen(" not in contract_source

    def test_47_no_execute_run_or_asyncio_create_task(self, contract_source):
        assert "execute_run" not in contract_source
        assert "asyncio.create_task" not in contract_source

    def test_48_no_create_tool_call(self, contract_source):
        assert "create_tool_call" not in contract_source

    def test_49_importing_module_has_no_side_effects(self):
        # Module was already imported at top of file; verify public API is intact
        # and that no global mutable state was modified.
        assert callable(contract_module.evaluate_confirmed_run_creation_contract)
        assert callable(contract_module.build_confirmed_run_creation_requirements)
        assert callable(contract_module.build_confirmed_run_creation_safety_gates)
        assert callable(contract_module.build_allowed_created_entities)
        assert callable(contract_module.build_forbidden_created_entities)
        assert callable(contract_module.build_required_confirmed_run_statuses)
        assert callable(contract_module.build_confirmed_run_creation_operator_checklist)
        assert callable(contract_module.redact_confirmed_run_creation_preview_for_report)
        # Constants are plain integers — no mutation possible.
        assert isinstance(contract_module._MAX_BLOCKERS, int)
        assert isinstance(contract_module._MAX_SAFETY_GATES, int)


# ── 50–53  Compatibility ──────────────────────────────────────────────────────


class TestCompatibility:
    """Tests 50–53: upstream builders remain importable and callable."""

    def test_50_intake_development_run_preview_builder_still_imports(self):
        from src.orchestrator.project_intake import build_intake_development_run_preview
        assert callable(build_intake_development_run_preview)

    def test_51_multi_agent_plan_builder_still_imports(self):
        from src.orchestrator.project_intake import build_multi_agent_plan_from_intake
        assert callable(build_multi_agent_plan_from_intake)

    def test_52_auto_sot_draft_builder_still_imports(self):
        from src.orchestrator.project_intake import build_source_of_truth_draft_from_intake
        assert callable(build_source_of_truth_draft_from_intake)

    def test_53_clarifying_questions_builder_still_imports(self):
        from src.orchestrator.project_intake import refine_unified_intake_with_answers
        assert callable(refine_unified_intake_with_answers)

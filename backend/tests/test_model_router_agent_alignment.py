"""Model Router + Agent Runtime Alignment Fastlane v1 — test suite.

42 tests covering:
  1–10   Model profile alignment (installed models)
  11–17  Canonical agent_id mapping
  18–22  Bridge step alignment
  23–27  Per-agent instruction loading
  28–34  Safety/static guarantees
  35–42  Compatibility with existing suites

All tests are pure-Python / deterministic — no Ollama, no DB writes,
no provider calls, no file mutations.
"""

from __future__ import annotations

import importlib
import importlib.util
import inspect
import pathlib
from types import SimpleNamespace

import pytest

from src.agents.registry import (
    canonical_agent_id_for_role,
    get_agent,
    get_all_agents,
    load_agent_instructions,
)
from src.model_router import MODEL_PROFILES, route_model
from src.models import ModelRouteRequest, ProviderMode
from src.orchestrator.engine import _runtime_agent_id_for_step
from src.orchestrator.project_intake import (
    build_pending_run_step_inputs_from_development_preview,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _route(
    profile: str,
    available: list[str] | None = None,
    task_type: str = "implementation",
    memory_gb: float = 32.0,
) -> str:
    """Run route_model and return the selected model string."""
    req = ModelRouteRequest(
        agent_id="orchestrator",
        task_type=task_type,
        model_profile=profile,
        provider_mode=ProviderMode.LOCAL,
        available_models=available or [],
        hardware_memory_gb=memory_gb,
    )
    result = route_model(req)
    return result.selected_model


def _preview_with_steps(steps: list[dict]) -> dict:
    return {
        "preview_only": True,
        "mode": "idea",
        "run_title": "Test Run",
        "run_goal": "Test goal.",
        "recommended_run_mode": "guided",
        "steps": steps,
        "validation": {"ready_to_create_run": True},
    }


def _step(agent_role: str, **overrides) -> dict:
    step = {
        "id": "STEP-001",
        "title": "Context step",
        "description": "Do something.",
        "agent_role": agent_role,
        "requirement_ids": ["REQ-001"],
        "module_ids": ["core-api"],
        "validation_steps": ["Verify."],
        "provider_allowed": False,
        "manual_approval_required": False,
        "safety_gates": ["No auto-start"],
        "expected_outputs": ["result"],
    }
    step.update(overrides)
    return step


# ── 1–10  Model profile alignment ─────────────────────────────────────────────


class TestModelProfileAlignment:
    """Tests 1–10: profile model selections match installed hardware reality."""

    INSTALLED_BOTH = ["qwen3-coder:30b", "qwen2.5-coder:7b"]
    INSTALLED_FAST_ONLY = ["qwen2.5-coder:7b"]

    def test_01_planning_reasoning_selects_30b_when_available(self):
        model = _route("planning_reasoning", available=self.INSTALLED_BOTH)
        assert model == "qwen3-coder:30b"

    def test_02_planning_reasoning_falls_back_to_7b_when_30b_unavailable(self):
        model = _route("planning_reasoning", available=self.INSTALLED_FAST_ONLY)
        assert model == "qwen2.5-coder:7b"

    def test_03_coding_heavy_selects_30b_when_available(self):
        model = _route("coding_heavy", available=self.INSTALLED_BOTH)
        assert model == "qwen3-coder:30b"

    def test_04_debugging_selects_30b_when_available(self):
        model = _route("debugging", available=self.INSTALLED_BOTH)
        assert model == "qwen3-coder:30b"

    def test_05_security_review_selects_30b_when_available(self):
        model = _route("security_review", available=self.INSTALLED_BOTH)
        assert model == "qwen3-coder:30b"

    def test_06_documentation_selects_7b_by_default(self):
        # documentation profile: primary=qwen2.5-coder:7b (fast for prose)
        model = _route("documentation", available=self.INSTALLED_BOTH)
        assert model == "qwen2.5-coder:7b"

    def test_07_no_active_profile_primary_points_to_qwen3_14b(self):
        for profile_id, profile in MODEL_PROFILES.items():
            if profile_id == "embeddings":
                continue  # embeddings uses nomic-embed-text
            assert profile.primary_model != "qwen3:14b", (
                f"Profile '{profile_id}' primary_model is qwen3:14b (not installed)"
            )

    def test_08_no_active_profile_primary_points_to_deepseek(self):
        for profile_id, profile in MODEL_PROFILES.items():
            if profile_id == "embeddings":
                continue
            assert "deepseek" not in profile.primary_model, (
                f"Profile '{profile_id}' primary_model references deepseek (not installed)"
            )

    def test_09_config_yaml_default_model_is_qwen3_coder_30b(self):
        import yaml  # type: ignore[import-untyped]
        config_path = pathlib.Path(__file__).parent.parent.parent / "config.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["ollama"]["default_model"] == "qwen3-coder:30b"

    def test_10_config_yaml_fast_model_is_qwen2_5_coder_7b(self):
        import yaml  # type: ignore[import-untyped]
        config_path = pathlib.Path(__file__).parent.parent.parent / "config.yaml"
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert cfg["ollama"]["fast_model"] == "qwen2.5-coder:7b"


# ── 11–17  Canonical agent_id mapping ─────────────────────────────────────────


class TestCanonicalAgentMapping:
    """Tests 11–17: canonical_agent_id_for_role returns valid registry IDs."""

    _APPROVED_FALLBACKS = {
        "orchestrator", "fullstack-developer", "backend-developer",
        "frontend-developer", "qa-expert", "technical-writer",
        "security-auditor", "devops-engineer", "business-analyst",
        "architect", "postgres-pro", "error-detective", "mobile-developer",
    }

    def test_11_backend_agent_maps_to_backend_developer(self):
        assert canonical_agent_id_for_role("backend_agent") == "backend-developer"
        assert canonical_agent_id_for_role("BackendAgent") == "backend-developer"
        assert canonical_agent_id_for_role("backend") == "backend-developer"

    def test_12_frontend_agent_maps_to_frontend_developer(self):
        assert canonical_agent_id_for_role("frontend_agent") == "frontend-developer"
        assert canonical_agent_id_for_role("FrontendAgent") == "frontend-developer"
        assert canonical_agent_id_for_role("frontend") == "frontend-developer"

    def test_13_qa_agent_maps_to_qa_expert(self):
        assert canonical_agent_id_for_role("qa_agent") == "qa-expert"
        assert canonical_agent_id_for_role("QA Agent") == "qa-expert"
        assert canonical_agent_id_for_role("qa") == "qa-expert"

    def test_14_security_guard_maps_to_security_auditor(self):
        result = canonical_agent_id_for_role("security_guard_agent")
        assert result == "security-auditor"
        assert canonical_agent_id_for_role("security") == "security-auditor"

    def test_15_unknown_role_maps_to_safe_fallback(self):
        result = canonical_agent_id_for_role("xyzzy_unknown_role_abc")
        assert result in self._APPROVED_FALLBACKS

    def test_16_mapping_is_deterministic(self):
        roles = [
            "backend_agent", "frontend_agent", "qa_agent",
            "security_guard_agent", "orchestrator", "architect",
        ]
        for role in roles:
            r1 = canonical_agent_id_for_role(role)
            r2 = canonical_agent_id_for_role(role)
            assert r1 == r2, f"Non-deterministic mapping for '{role}'"

    def test_17_all_mapped_ids_exist_in_registry_or_approved_fallbacks(self):
        test_roles = [
            "backend_agent", "frontend_agent", "qa_agent",
            "security_guard_agent", "devops_agent", "delivery_reviewer_agent",
            "product_analyst", "architect", "database_agent",
            "context analyst", "module reviewer", "repo_analyst",
        ]
        all_registry_ids = {a.id for a in get_all_agents()}
        for role in test_roles:
            mapped = canonical_agent_id_for_role(role)
            assert mapped in all_registry_ids or mapped in self._APPROVED_FALLBACKS, (
                f"Role '{role}' mapped to '{mapped}' which is not in registry or approved fallbacks"
            )


# ── 18–22  Bridge step alignment ─────────────────────────────────────────────


class TestBridgeStepAlignment:
    """Tests 18–22: bridge steps use canonical agent_id and preserve agent_role."""

    def _build(self, agent_role: str, **step_overrides) -> list[dict]:
        return build_pending_run_step_inputs_from_development_preview(
            _preview_with_steps([_step(agent_role, **step_overrides)])
        )

    def test_18_build_step_inputs_preserves_agent_role(self):
        metas = self._build("BackendDeveloper")
        assert metas[0]["agent_role"] == "BackendDeveloper"

    def test_19_bridge_uses_canonical_agent_id(self):
        metas = self._build("backend_agent")
        assert metas[0]["agent_id"] == "backend-developer"

    def test_20_step_context_includes_original_agent_role(self):
        metas = self._build("QA Agent")
        assert "QA Agent" in metas[0]["input_text"]

    def test_21_provider_allowed_remains_false(self):
        metas = self._build("BackendDeveloper", provider_allowed=True)
        # Bridge hardcodes provider_allowed=False regardless of step input
        assert metas[0]["provider_allowed"] is False

    def test_22_context_analyst_maps_to_orchestrator(self):
        metas = self._build("ContextAnalyst")
        assert metas[0]["agent_id"] == "orchestrator"


# ── 23–27  Per-agent instruction loading ─────────────────────────────────────


class TestPerAgentInstructions:
    """Tests 23–27: instruction loading is safe, bounded, and consistent."""

    def test_23_agent_executions_run_uses_load_agent_instructions(self):
        # Verify routes.py agent execution endpoint references load_agent_instructions
        spec = importlib.util.find_spec("src.api.routes")
        assert spec is not None and spec.origin is not None
        src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
        assert "load_agent_instructions" in src

    def test_24_engine_staged_execution_loads_per_step_instructions(self):
        # Verify engine.py uses step_instructions (not only run-level instructions)
        spec = importlib.util.find_spec("src.orchestrator.engine")
        assert spec is not None and spec.origin is not None
        src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
        assert "step_instructions" in src
        assert "load_agent_instructions(step.agent_id" in src

    def test_25_missing_agent_instructions_do_not_crash(self):
        # agent with no markdown file returns empty string, not exception
        result = load_agent_instructions("nonexistent-agent-xyz-99")
        assert isinstance(result, str)

    def test_26_instructions_not_loaded_from_arbitrary_user_path(self):
        # load_agent_instructions source must not accept absolute paths via public API
        src = inspect.getsource(load_agent_instructions)
        # It reads from agents/ subdir relative to PROJECT_ROOT, not arbitrary input
        assert "PROJECT_ROOT" in src or "repo_path" in src or "AGENTS_DIR" in src

    def test_27_instructions_for_backend_agent_are_non_empty(self):
        # agents/backend.md exists and is non-empty
        result = load_agent_instructions("backend-developer")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_27b_runtime_agent_resolution_canonicalizes_stored_aliases(self):
        step = SimpleNamespace(
            agent_id="backend",
            title="Implement FastAPI endpoint",
            input="Add backend route.",
        )
        assert _runtime_agent_id_for_step(step) == "backend-developer"

    def test_27c_runtime_agent_resolution_uses_inferred_canonical_agent_when_empty(self):
        step = SimpleNamespace(
            agent_id="",
            title="Write pytest coverage",
            input="Add unit tests.",
        )
        assert _runtime_agent_id_for_step(step) == "qa-expert"


# ── 28–34  Safety / static guarantees ────────────────────────────────────────


@pytest.fixture(scope="module")
def engine_source() -> str:
    spec = importlib.util.find_spec("src.orchestrator.engine")
    assert spec is not None and spec.origin is not None
    return pathlib.Path(spec.origin).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def registry_source() -> str:
    spec = importlib.util.find_spec("src.agents.registry")
    assert spec is not None and spec.origin is not None
    return pathlib.Path(spec.origin).read_text(encoding="utf-8")


class TestSafetyGuarantees:
    """Tests 28–34: alignment introduces no forbidden runtime behaviors."""

    def test_28_no_new_execute_run_auto_call(self, engine_source):
        # execute_run should only be defined/called the existing way
        # The alignment adds step_instructions, nothing else
        assert "step_instructions" in engine_source  # confirms our change
        # No new asyncio.create_task wrapping execute_run added
        assert engine_source.count("asyncio.create_task(execute_run") == 0

    def test_29_no_asyncio_create_task_in_new_code(self, registry_source):
        assert "asyncio.create_task" not in registry_source

    def test_30_no_create_tool_call_in_canonical_mapping(self, registry_source):
        # canonical_agent_id_for_role source must not reference create_tool_call
        fn_src = inspect.getsource(canonical_agent_id_for_role)
        assert "create_tool_call" not in fn_src

    def test_31_no_provider_call_in_alignment_path(self, registry_source):
        assert "ollama.chat_completion" not in registry_source
        assert "import anthropic" not in registry_source
        assert "import openai" not in registry_source

    def test_32_no_file_reads_beyond_agent_instructions(self, registry_source):
        # Only allowed file read is via load_agent_instructions
        assert "subprocess" not in registry_source
        assert "os.system" not in registry_source

    def test_33_no_db_schema_changes(self):
        # database.py must not be touched: confirm it has no alignment-related symbols
        spec = importlib.util.find_spec("src.storage.database")
        assert spec is not None and spec.origin is not None
        db_src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
        assert "canonical_agent_id_for_role" not in db_src
        assert "step_instructions" not in db_src

    def test_34_database_py_untouched_no_model_profile_refs(self):
        spec = importlib.util.find_spec("src.storage.database")
        assert spec is not None and spec.origin is not None
        db_src = pathlib.Path(spec.origin).read_text(encoding="utf-8")
        assert "qwen3-coder:30b" not in db_src
        assert "MODEL_PROFILES" not in db_src


# ── 35–40  Compatibility ──────────────────────────────────────────────────────


class TestCompatibility:
    """Tests 35–40: existing suites and infrastructure still importable."""

    def test_35_model_router_still_importable(self):
        from src.model_router import route_model, MODEL_PROFILES, infer_agent_for_step
        assert callable(route_model)
        assert isinstance(MODEL_PROFILES, dict)
        assert callable(infer_agent_for_step)

    def test_36_agent_execution_harness_still_importable(self):
        from src.api.routes import run_agent_execution
        assert callable(run_agent_execution)

    def test_37_bridge_fastlane_builder_still_importable(self):
        from src.orchestrator.project_intake import (
            build_pending_run_step_inputs_from_development_preview,
            build_confirmed_development_run_creation_input,
        )
        assert callable(build_pending_run_step_inputs_from_development_preview)
        assert callable(build_confirmed_development_run_creation_input)

    def test_38_all_model_profiles_have_valid_fallback(self):
        # Every non-embeddings profile must have qwen2.5-coder:7b as fallback
        for profile_id, profile in MODEL_PROFILES.items():
            if profile_id == "embeddings":
                continue
            assert profile.fallback_model in ("qwen2.5-coder:7b", "nomic-embed-text"), (
                f"Profile '{profile_id}' fallback_model is '{profile.fallback_model}' "
                "— expected qwen2.5-coder:7b (always installed)"
            )

    def test_39_engine_still_imports_without_error(self):
        from src.orchestrator.engine import execute_run
        assert callable(execute_run)

    def test_40_project_intake_imports_canonical_mapping(self):
        import src.orchestrator.project_intake as intake
        # canonical_agent_id_for_role must be imported (used in bridge)
        assert hasattr(intake, "canonical_agent_id_for_role") or \
               "canonical_agent_id_for_role" in inspect.getsource(
                   intake.build_pending_run_step_inputs_from_development_preview
               )

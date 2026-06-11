from __future__ import annotations

from src.agents.registry import get_all_agents
from src.model_router import (
    CHATGPT_CODEX,
    LOCAL_OLLAMA,
    list_model_profiles,
    list_model_registry,
    route_model,
    validate_agent_model_profiles,
)
from src.models import ModelRouteRequest, ProviderMode


def test_model_registry_loads():
    registry = list_model_registry(["qwen2.5-coder:7b"], {})
    ids = {model.id for model in registry}

    assert "qwen2.5-coder:7b" in ids
    assert "qwen3-coder:30b" in ids
    assert "deepseek-r1:14b" in ids
    assert "nomic-embed-text" in ids
    assert any(model.id == "qwen2.5-coder:7b" and model.installed for model in registry)


def test_model_profiles_load():
    profiles = {profile.id: profile for profile in list_model_profiles()}

    assert {
        "coding_heavy",
        "coding_fast",
        "planning_reasoning",
        "debugging",
        "security_review",
        "documentation",
        "vision_ui",
        "embeddings",
    }.issubset(profiles)
    assert profiles["coding_heavy"].primary_model == "qwen3-coder:30b"
    assert profiles["embeddings"].allowed_providers == [LOCAL_OLLAMA]


def test_each_registered_agent_has_valid_model_profile():
    assert validate_agent_model_profiles() == []
    assert all(agent.model_profile for agent in get_all_agents())


def test_router_chooses_local_ollama_model_in_local_mode():
    result = route_model(
        ModelRouteRequest(
            agent_id="backend-developer",
            task_type="implementation",
            provider_mode=ProviderMode.LOCAL,
            available_models=["qwen3-coder:30b", "qwen2.5-coder:7b"],
        ),
        {},
    )

    assert result.selected_provider == LOCAL_OLLAMA
    assert result.selected_model == "qwen3-coder:30b"
    assert result.model_profile == "coding_heavy"


def test_router_does_not_choose_external_provider_in_local_mode():
    result = route_model(
        ModelRouteRequest(
            agent_id="backend-developer",
            task_type="implementation",
            provider_mode=ProviderMode.LOCAL,
            available_models=[],
            project_privacy_level="public",
            user_preference_provider=CHATGPT_CODEX,
        ),
        {"codex": {"enabled": True}},
    )

    assert result.selected_provider == LOCAL_OLLAMA
    assert result.selected_model == "qwen2.5-coder:7b"
    assert any("local prohibits external" in warning for warning in result.warnings)


def test_router_can_choose_external_in_hybrid_when_allowed_and_enabled():
    result = route_model(
        ModelRouteRequest(
            agent_id="backend-developer",
            task_type="implementation",
            provider_mode=ProviderMode.HYBRID,
            available_models=[],
            project_privacy_level="public",
            user_preference_provider=CHATGPT_CODEX,
        ),
        {"codex": {"enabled": True}},
    )

    assert result.selected_provider == CHATGPT_CODEX
    assert result.selected_model == "chatgpt-codex:default"
    assert result.confidence > 0.7


def test_router_can_choose_external_in_cloud_when_allowed_and_enabled():
    result = route_model(
        ModelRouteRequest(
            agent_id="architect",
            task_type="architecture",
            provider_mode=ProviderMode.CLOUD,
            available_models=[],
            project_privacy_level="public",
        ),
        {"claude": {"enabled": True}},
    )

    assert result.selected_provider == "claude_code"
    assert result.selected_model == "claude-code:sonnet"


def test_router_blocks_external_for_private_projects():
    # Core invariant: private projects are routed to LOCAL_OLLAMA even in CLOUD mode.
    # Available model uses qwen2.5-coder:7b (always installed fallback) since
    # the security_review profile now prefers qwen3-coder:30b with qwen2.5-coder:7b fallback.
    result = route_model(
        ModelRouteRequest(
            agent_id="security-auditor",
            task_type="security_review",
            provider_mode=ProviderMode.CLOUD,
            available_models=["qwen2.5-coder:7b"],
            project_privacy_level="private",
            user_preference_provider=CHATGPT_CODEX,
        ),
        {"codex": {"enabled": True}},
    )

    assert result.selected_provider == LOCAL_OLLAMA
    assert result.selected_model == "qwen2.5-coder:7b"
    assert any("privacy level blocks external" in warning for warning in result.warnings)


def test_coding_security_and_documentation_agents_route_to_expected_profiles():
    coding = route_model(ModelRouteRequest(agent_id="react-specialist", available_models=["qwen2.5-coder:7b"]), {})
    security = route_model(ModelRouteRequest(agent_id="security-auditor", available_models=["deepseek-r1:14b"]), {})
    docs = route_model(ModelRouteRequest(agent_id="technical-writer", available_models=["qwen3:14b"]), {})

    assert coding.model_profile == "coding_heavy"
    assert security.model_profile == "security_review"
    assert docs.model_profile == "documentation"


def test_fallback_works_when_primary_model_is_unavailable():
    result = route_model(
        ModelRouteRequest(
            agent_id="backend-developer",
            task_type="implementation",
            provider_mode=ProviderMode.LOCAL,
            available_models=["qwen2.5-coder:7b"],
        ),
        {},
    )

    assert result.selected_provider == LOCAL_OLLAMA
    assert result.selected_model == "qwen2.5-coder:7b"
    assert result.fallback_model == "qwen2.5-coder:7b"
    assert result.confidence == 0.78


def test_heavy_models_have_max_parallel_one():
    registry = list_model_registry([], {})
    heavy = [model for model in registry if model.memory_tier in {"large", "xlarge"}]

    assert heavy
    assert all(model.max_parallel == 1 for model in heavy)

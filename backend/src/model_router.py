"""Model registry and provider-aware routing rules."""

from __future__ import annotations

from typing import Any

from src.agents.registry import get_agent, get_all_agents
from src.models import (
    BUNDLE_MAX_FILES,
    BUNDLE_MAX_SNIPPET_CHARS,
    BUNDLE_MAX_SNIPPETS_PER_FILE,
    DRAFT_MAX_OLD_TEXT_CHARS,
    DRAFT_PLACEHOLDER_NEW_TEXT,
    ContextPatchDraftCandidate,
    ContextPatchDraftRequest,
    ContextPatchDraftResponse,
    GuidedStepAction,
    GuidedStepExecutionPlan,
    ModelProfile,
    ModelRegistryItem,
    ModelRouteDecision,
    ModelRouteRequest,
    ModelRouteResult,
    PatchReviewIssue,
    PatchReviewOperation,
    PatchReviewOperationResult,
    PatchReviewResponse,
    PatchWorkflowNextAction,
    PatchWorkflowPlanResponse,
    PatchWorkflowStage,
    ProviderInfo,
    ProviderMode,
    RunStep,
    StepContextBundle,
    StepContextFile,
    StepPatchWorkflowPlan,
    StepToolRecommendation,
    ToolCall,
)

LOCAL_OLLAMA = "local_ollama"
CLAUDE_CODE = "claude_code"
CHATGPT_CODEX = "chatgpt_codex"
EXTERNAL_API = "external_api"

EXTERNAL_PROVIDERS = {CLAUDE_CODE, CHATGPT_CODEX, EXTERNAL_API}
PRIVATE_PRIVACY_LEVELS = {"private", "secret", "secrets", "confidential", "restricted", "internal"}
QUICK_TASK_TYPES = {"quick_fix", "fast_response"}
REASONING_TASK_TYPES = {"planning", "architecture", "debugging", "code_review", "security_review"}

AGENT_TASK_TYPE_DEFAULTS = {
    "orchestrator": "planning",
    "product-manager": "planning",
    "business-analyst": "planning",
    "architect": "architecture",
    "api-designer": "architecture",
    "frontend-developer": "implementation",
    "backend-developer": "implementation",
    "fullstack-developer": "implementation",
    "react-specialist": "implementation",
    "typescript-pro": "implementation",
    "fastapi-developer": "implementation",
    "node-specialist": "implementation",
    "php-pro": "implementation",
    "sql-pro": "implementation",
    "postgres-pro": "debugging",
    "mobile-developer": "implementation",
    "qa-expert": "test_generation",
    "test-automator": "test_generation",
    "code-reviewer": "code_review",
    "security-auditor": "security_review",
    "devops-engineer": "deployment",
    "technical-writer": "documentation",
    "error-detective": "debugging",
    "git-workflow-manager": "deployment",
}

ROLE_TASK_TYPE_HINTS = {
    "architecture": "architecture",
    "api": "architecture",
    "frontend": "implementation",
    "backend": "implementation",
    "fullstack": "implementation",
    "implementation": "implementation",
    "verification": "test_generation",
    "qa": "test_generation",
    "review": "code_review",
    "security": "security_review",
    "debug": "debugging",
    "docs": "documentation",
    "documentation": "documentation",
    "devops": "deployment",
    "deployment": "deployment",
}

# Keyword → canonical agent ID rules for step-level inference.
# Evaluated in order; first match wins.
# ORDER MATTERS: more specific / higher-signal rules must come before broader ones.
# e.g. test/pytest must precede security/auth so "pytest tests for auth" → qa-expert.
_STEP_AGENT_KEYWORDS: list[tuple[list[str], str]] = [
    (["mobile", "android", "ios", "flutter", "react native"], "mobile-developer"),
    # Test keywords before security so "pytest tests for auth" → qa-expert, not security-auditor.
    (["test", "spec", "unit test", "integration test", "e2e", "pytest", "jest", "qa", "verify", "validation", "coverage"], "qa-expert"),
    (["security", "vulnerability", "csrf", "xss", "injection", "secret", "credential"], "security-auditor"),
    (["deploy", "ci ", "cd ", "pipeline", "docker", "kubernetes", "k8s", "release", "devops", "infrastructure", "helm"], "devops-engineer"),
    (["error", "bug", "fix", "debug", "crash", "exception", "traceback", "failure", "broken", "investigate"], "error-detective"),
    # sql-pro before technical-writer: "sql query for reporting" must route to sql-pro, not writer.
    (["database", "db ", " sql", "query", "migration", "schema", "orm", "postgres", "mysql", "sqlite", "mongo"], "sql-pro"),
    (["doc", "readme", "guide", "documentation", "report", "changelog", "wiki", "tutorial"], "technical-writer"),
    (["frontend", "ui ", "ux ", "react", "vue", "angular", "css", "component", "page ", "html", ".jsx", ".tsx", "svelte"], "frontend-developer"),
    (["backend", "api ", "endpoint", "fastapi", "flask", "django", "server", "rest ", "grpc", "microservice"], "backend-developer"),
    # Orchestrator only on explicit orchestration language; generic terms fall through to fullstack-developer.
    (["orchestrate", "review project", "inspect project", "coordinate agents"], "orchestrator"),
]

# Keyword → task type rules for step-level inference.
# Evaluated in order; first match wins.
# ORDER MATTERS: test_generation must precede security_review.
_STEP_TASK_TYPE_KEYWORDS: list[tuple[list[str], str]] = [
    (["deploy", "ci ", "cd ", "pipeline", "docker", "kubernetes", "k8s", "release", "infrastructure", "helm"], "deployment"),
    # Test keywords before security so "pytest tests for auth" → test_generation, not security_review.
    (["test", "spec", "unit test", "integration test", "e2e", "pytest", "jest", "qa", "verify", "coverage"], "test_generation"),
    (["security", "vulnerability", "csrf", "xss", "injection", "penetration", "audit"], "security_review"),
    (["review", "audit code", "code quality", "linting", "static analysis", "code review"], "code_review"),
    (["error", "bug", "debug", "crash", "exception", "traceback", "failure", "investigate"], "debugging"),
    (["doc", "readme", "guide", "documentation", "report", "changelog", "wiki"], "documentation"),
    (["architecture", "design", "schema", "diagram", "structure", "module layout", "interface design"], "architecture"),
    (["plan", "orchestrate", "analyze requirements", "kickoff"], "planning"),
    (["quick fix", "hotfix", "minor patch", "small fix", "trivial"], "quick_fix"),
]


MODEL_REGISTRY: tuple[ModelRegistryItem, ...] = (
    ModelRegistryItem(
        id="qwen2.5-coder:7b",
        provider=LOCAL_OLLAMA,
        display_name="Qwen 2.5 Coder 7B",
        family="qwen-coder",
        capabilities=["coding", "debugging", "documentation", "fast_response"],
        context_window=32768,
        memory_tier="medium",
        recommended_for=["coding_fast", "quick_fix", "small repositories"],
        installed=False,
        enabled=True,
        max_parallel=2,
        notes="Recommended baseline local coding model for modest hardware.",
    ),
    ModelRegistryItem(
        id="qwen3-coder:30b",
        provider=LOCAL_OLLAMA,
        display_name="Qwen 3 Coder 30B",
        family="qwen-coder",
        capabilities=["coding", "reasoning", "debugging", "long_context"],
        context_window=131072,
        memory_tier="xlarge",
        recommended_for=["coding_heavy", "large refactors", "implementation planning"],
        installed=False,
        enabled=True,
        max_parallel=1,
        notes="Heavy local coding model. Use one at a time on 32GB unified memory.",
    ),
    ModelRegistryItem(
        id="qwen3:8b",
        provider=LOCAL_OLLAMA,
        display_name="Qwen 3 8B",
        family="qwen",
        capabilities=["planning", "documentation", "fast_response"],
        context_window=32768,
        memory_tier="medium",
        recommended_for=["planning fallback", "documentation", "quick analysis"],
        installed=False,
        enabled=True,
        max_parallel=2,
        notes="Fast local general model for planning and summaries.",
    ),
    ModelRegistryItem(
        id="qwen3:14b",
        provider=LOCAL_OLLAMA,
        display_name="Qwen 3 14B",
        family="qwen",
        capabilities=["planning", "reasoning", "documentation", "long_context"],
        context_window=65536,
        memory_tier="large",
        recommended_for=["planning_reasoning", "architecture", "documentation"],
        installed=False,
        enabled=True,
        max_parallel=1,
        notes="Default local reasoning model for architecture and planning.",
    ),
    ModelRegistryItem(
        id="deepseek-r1:14b",
        provider=LOCAL_OLLAMA,
        display_name="DeepSeek R1 14B",
        family="deepseek-r1",
        capabilities=["reasoning", "debugging", "security_review", "code_review"],
        context_window=32768,
        memory_tier="large",
        recommended_for=["debugging", "security_review", "root cause analysis"],
        installed=False,
        enabled=True,
        max_parallel=1,
        notes="Reasoning-heavy local model. Prefer single concurrency.",
    ),
    ModelRegistryItem(
        id="llava:7b",
        provider=LOCAL_OLLAMA,
        display_name="LLaVA 7B",
        family="llava",
        capabilities=["vision", "vision_ui", "documentation"],
        context_window=4096,
        memory_tier="medium",
        recommended_for=["vision_ui", "screenshot analysis"],
        installed=False,
        enabled=True,
        max_parallel=1,
        notes="Optional local vision model for UI/screenshot review.",
    ),
    ModelRegistryItem(
        id="nomic-embed-text",
        provider=LOCAL_OLLAMA,
        display_name="Nomic Embed Text",
        family="nomic",
        capabilities=["embeddings"],
        context_window=8192,
        memory_tier="small",
        recommended_for=["embeddings", "code search indexing"],
        installed=False,
        enabled=True,
        max_parallel=4,
        notes="Small local embedding model.",
    ),
    ModelRegistryItem(
        id="claude-code:sonnet",
        provider=CLAUDE_CODE,
        display_name="Claude Code Sonnet",
        family="claude",
        capabilities=["coding", "reasoning", "debugging", "code_review", "long_context"],
        context_window=200000,
        memory_tier="small",
        recommended_for=["hybrid deep review", "large repo analysis"],
        installed=False,
        enabled=False,
        max_parallel=1,
        notes="Optional external CLI provider. Disabled by default and approval-gated.",
    ),
    ModelRegistryItem(
        id="chatgpt-codex:default",
        provider=CHATGPT_CODEX,
        display_name="ChatGPT Codex",
        family="codex",
        capabilities=["coding", "reasoning", "debugging", "code_review", "long_context"],
        context_window=128000,
        memory_tier="small",
        recommended_for=["hybrid implementation guidance", "cloud coding review"],
        installed=False,
        enabled=False,
        max_parallel=1,
        notes="Optional external Codex provider. Disabled by default and approval-gated.",
    ),
    ModelRegistryItem(
        id="external-api:default",
        provider=EXTERNAL_API,
        display_name="External API Model",
        family="external",
        capabilities=["coding", "reasoning", "documentation"],
        context_window=128000,
        memory_tier="small",
        recommended_for=["future provider adapters"],
        installed=False,
        enabled=False,
        max_parallel=1,
        notes="Placeholder for future OpenAI-compatible external APIs.",
    ),
)

# ── Installed model reality for this deployment ───────────────────────────────
# Confirmed installed (as of 2026-06-01, M1 Pro 32 GB):
#   qwen3-coder:30b  — 18.6 GB — heavy planning/coding/debugging/security
#   qwen2.5-coder:7b —  4.7 GB — fast coding, documentation, fallback
# Not installed:
#   qwen3:14b, qwen3:8b, deepseek-r1:14b, llava:7b
# All profiles MUST have a fallback that is installed so routing never stalls.

MODEL_PROFILES: dict[str, ModelProfile] = {
    # Heavy implementation: qwen3-coder:30b primary, qwen2.5-coder:7b fast/fallback
    "coding_heavy": ModelProfile(
        id="coding_heavy",
        primary_model="qwen3-coder:30b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CHATGPT_CODEX, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=1,
        local_only_default=True,
        description="Implementation-heavy coding. Primary: qwen3-coder:30b. Fast/fallback: qwen2.5-coder:7b.",
    ),
    # Quick fixes and small patches: qwen2.5-coder:7b primary
    "coding_fast": ModelProfile(
        id="coding_fast",
        primary_model="qwen2.5-coder:7b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CHATGPT_CODEX, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=2,
        local_only_default=True,
        description="Fast local coding and small fixes. Primary: qwen2.5-coder:7b.",
    ),
    # Planning / architecture / orchestration: qwen3-coder:30b primary
    "planning_reasoning": ModelProfile(
        id="planning_reasoning",
        primary_model="qwen3-coder:30b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CHATGPT_CODEX, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=1,
        local_only_default=True,
        description="Planning, architecture, orchestration. Primary: qwen3-coder:30b. Fast: qwen2.5-coder:7b.",
    ),
    # Debugging and root-cause analysis: qwen3-coder:30b primary
    "debugging": ModelProfile(
        id="debugging",
        primary_model="qwen3-coder:30b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CHATGPT_CODEX, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=1,
        local_only_default=True,
        description="Failure analysis, test debugging, code review. Primary: qwen3-coder:30b.",
    ),
    # Security review: qwen3-coder:30b primary (reasoning-heavy, privacy-first)
    "security_review": ModelProfile(
        id="security_review",
        primary_model="qwen3-coder:30b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CLAUDE_CODE, CHATGPT_CODEX],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=1,
        local_only_default=True,
        description="Security review, local-first privacy. Primary: qwen3-coder:30b.",
    ),
    # Documentation and reports: qwen2.5-coder:7b primary (fast, sufficient for prose)
    "documentation": ModelProfile(
        id="documentation",
        primary_model="qwen2.5-coder:7b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CHATGPT_CODEX, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=2,
        local_only_default=True,
        description="README, reports, specs. Primary: qwen2.5-coder:7b. Reasoning: qwen3-coder:30b.",
    ),
    # Vision/UI: qwen2.5-coder:7b as fallback (llava not installed)
    "vision_ui": ModelProfile(
        id="vision_ui",
        primary_model="llava:7b",
        fast_model="qwen2.5-coder:7b",
        reasoning_model="qwen3-coder:30b",
        fallback_model="qwen2.5-coder:7b",
        allowed_providers=[LOCAL_OLLAMA, CLAUDE_CODE],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=1,
        local_only_default=True,
        description="Screenshot and visual UI analysis. Fallback to qwen2.5-coder:7b if llava not installed.",
    ),
    # Embeddings: nomic-embed-text
    "embeddings": ModelProfile(
        id="embeddings",
        primary_model="nomic-embed-text",
        fast_model="nomic-embed-text",
        reasoning_model="",
        fallback_model="nomic-embed-text",
        allowed_providers=[LOCAL_OLLAMA],
        preferred_provider=LOCAL_OLLAMA,
        max_parallel=4,
        local_only_default=True,
        description="Local text/code embedding generation.",
    ),
}


def list_model_registry(
    available_models: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> list[ModelRegistryItem]:
    """Return model registry with local installed and provider-enabled flags applied."""
    available = set(available_models or [])
    provider_enabled = _provider_enabled_map(config or {})
    items: list[ModelRegistryItem] = []
    for item in MODEL_REGISTRY:
        installed = item.installed
        enabled = item.enabled
        if item.provider == LOCAL_OLLAMA:
            installed = item.id in available
            enabled = True
        else:
            enabled = provider_enabled.get(item.provider, False)
        items.append(item.model_copy(update={"installed": installed, "enabled": enabled}))
    return items


def list_model_profiles() -> list[ModelProfile]:
    """Return all model routing profiles."""
    return list(MODEL_PROFILES.values())


def get_model_profile(profile_id: str) -> ModelProfile | None:
    """Return one model profile by ID."""
    return MODEL_PROFILES.get(profile_id)


def list_providers(config: dict[str, Any] | None = None) -> list[ProviderInfo]:
    """Return provider metadata without performing provider execution."""
    cfg = config or {}
    return [
        ProviderInfo(
            id=LOCAL_OLLAMA,
            display_name="Local Ollama",
            kind="local",
            enabled=True,
            local=True,
            requires_approval=False,
            supports_execution=True,
            modes=[ProviderMode.LOCAL, ProviderMode.HYBRID, ProviderMode.CLOUD],
            notes="Default offline provider. Prompts and code stay local.",
        ),
        ProviderInfo(
            id=CHATGPT_CODEX,
            display_name="ChatGPT Codex",
            kind="external_cli",
            enabled=bool(cfg.get("codex", {}).get("enabled", False)),
            local=False,
            requires_approval=True,
            supports_execution=False,
            modes=[ProviderMode.HYBRID, ProviderMode.CLOUD],
            notes="Optional external provider; routing only in this slice.",
        ),
        ProviderInfo(
            id=CLAUDE_CODE,
            display_name="Claude Code",
            kind="external_cli",
            enabled=bool(cfg.get("claude", {}).get("enabled", False)),
            local=False,
            requires_approval=True,
            supports_execution=False,
            modes=[ProviderMode.HYBRID, ProviderMode.CLOUD],
            notes="Optional external provider; routing only in this slice.",
        ),
        ProviderInfo(
            id=EXTERNAL_API,
            display_name="External API",
            kind="external_api",
            enabled=bool(cfg.get("external_api", {}).get("enabled", False)),
            local=False,
            requires_approval=True,
            supports_execution=False,
            modes=[ProviderMode.CLOUD],
            notes="Reserved for future OpenAI-compatible API adapters.",
        ),
    ]


def route_model(
    request: ModelRouteRequest,
    config: dict[str, Any] | None = None,
) -> ModelRouteResult:
    """Choose a provider/model for an agent step without executing that provider."""
    cfg = config or {}
    provider_mode = _normalize_provider_mode(request.provider_mode or cfg.get("provider_mode", "local"))
    agent = get_agent(request.agent_id) if request.agent_id else None
    profile_id = request.model_profile or (agent.model_profile if agent else "planning_reasoning")
    profile = MODEL_PROFILES.get(profile_id) or MODEL_PROFILES["planning_reasoning"]
    registry = {item.id: item for item in list_model_registry(request.available_models, cfg)}
    warnings: list[str] = []

    if profile_id not in MODEL_PROFILES:
        warnings.append(f"Unknown model_profile '{profile_id}', using planning_reasoning.")

    external_allowed, external_warning = _external_allowed(
        provider_mode=provider_mode,
        privacy_level=request.project_privacy_level,
    )
    if external_warning:
        warnings.append(external_warning)

    provider_enabled = _provider_enabled_map(cfg)
    preferred_provider = request.user_preference_provider or profile.preferred_provider
    if provider_mode == ProviderMode.LOCAL and preferred_provider in EXTERNAL_PROVIDERS:
        warnings.append("External provider preference ignored in local mode.")
        preferred_provider = LOCAL_OLLAMA

    preferred_model_id = _preferred_model_for_task(profile, request.task_type)
    if request.user_preference_model:
        preferred_model_id = request.user_preference_model

    external_result = _try_external_route(
        profile=profile,
        provider_mode=provider_mode,
        preferred_provider=preferred_provider,
        provider_enabled=provider_enabled,
        external_allowed=external_allowed,
        task_type=request.task_type,
    )
    if external_result and (
        request.user_preference_provider in EXTERNAL_PROVIDERS
        or provider_mode == ProviderMode.CLOUD
        or preferred_model_id not in registry
    ):
        return external_result.model_copy(
            update={
                "fallback_model": profile.fallback_model,
                "warnings": warnings + external_result.warnings,
                "model_profile": profile.id,
                "task_type": request.task_type,
            }
        )

    result = _route_local(
        profile=profile,
        preferred_model_id=preferred_model_id,
        registry=registry,
        available_models=set(request.available_models),
        hardware_memory_gb=request.hardware_memory_gb,
        warnings=warnings,
        requested_model=bool(request.user_preference_model),
    )
    return result.model_copy(update={"model_profile": profile.id, "task_type": request.task_type})


def infer_task_type_for_agent(agent_id: str, assigned_role: str = "") -> str:
    """Infer the route task type from agent identity and assigned role."""
    normalized_role = (assigned_role or "").strip().lower()
    for hint, task_type in ROLE_TASK_TYPE_HINTS.items():
        if hint in normalized_role:
            return task_type

    normalized_agent = (agent_id or "").strip()
    alias_agent = {
        "backend": "backend-developer",
        "frontend": "frontend-developer",
        "qa": "qa-expert",
        "security": "security-auditor",
        "docs": "technical-writer",
        "mobile": "mobile-developer",
        "repo_analyst": "business-analyst",
    }.get(normalized_agent, normalized_agent)
    return AGENT_TASK_TYPE_DEFAULTS.get(alias_agent, "planning")


def infer_agent_for_step(
    step_title: str,
    step_input: str = "",
    assigned_agents: list[dict] | None = None,
    detected_stack: list[str] | None = None,
) -> str:
    """Infer a canonical agent ID for a staged step from title/input keywords.

    Keyword rules are checked first (ordered, first match wins).
    If no keyword matches, falls back to ``fullstack-developer``.

    ``assigned_agents`` and ``detected_stack`` are accepted for future use but
    not currently used to avoid over-specifying the routing logic.
    """
    text = f"{step_title} {step_input}".lower()
    for keywords, canonical_agent_id in _STEP_AGENT_KEYWORDS:
        if any(kw in text for kw in keywords):
            return canonical_agent_id
    return "fullstack-developer"


def infer_task_type_for_step(
    step_title: str,
    step_input: str = "",
    agent_id: str = "",
) -> str:
    """Infer the task type for a staged step from title/input keywords.

    Keyword rules are checked first (ordered, first match wins).
    If no keyword matches, the agent's default task type from
    ``AGENT_TASK_TYPE_DEFAULTS`` is used; final fallback is ``implementation``.
    """
    text = f"{step_title} {step_input}".lower()
    for keywords, task_type in _STEP_TASK_TYPE_KEYWORDS:
        if any(kw in text for kw in keywords):
            return task_type
    return AGENT_TASK_TYPE_DEFAULTS.get(agent_id, "implementation")


def model_route_decision_from_result(
    *,
    run_id: str,
    agent_id: str,
    task_type: str,
    provider_mode: ProviderMode | str,
    route: ModelRouteResult,
    step_id: str | None = None,
) -> ModelRouteDecision:
    """Convert a router result into a persistable run decision."""
    normalized_mode = _normalize_provider_mode(provider_mode)
    return ModelRouteDecision(
        run_id=run_id,
        step_id=step_id,
        agent_id=agent_id,
        task_type=task_type,
        model_profile=route.model_profile,
        selected_model=route.selected_model,
        selected_provider=route.selected_provider,
        fallback_model=route.fallback_model,
        fallback_provider=model_provider_for(route.fallback_model),
        provider_mode=normalized_mode,
        reason=route.reason,
        confidence=route.confidence,
        warnings=route.warnings,
    )


def model_provider_for(model_id: str) -> str | None:
    """Return the provider for a registered model id."""
    if not model_id:
        return None
    for item in MODEL_REGISTRY:
        if item.id == model_id:
            return item.provider
    return LOCAL_OLLAMA if ":" in model_id else None


def _route_local(
    *,
    profile: ModelProfile,
    preferred_model_id: str,
    registry: dict[str, ModelRegistryItem],
    available_models: set[str],
    hardware_memory_gb: float | None,
    warnings: list[str],
    requested_model: bool,
) -> ModelRouteResult:
    candidates = _ordered_local_candidates(profile, preferred_model_id)

    for model_id in candidates:
        item = registry.get(model_id)
        if not item or item.provider != LOCAL_OLLAMA:
            continue
        if _too_heavy_for_hardware(item, hardware_memory_gb):
            warnings.append(
                f"{item.id} is {item.memory_tier}; routing prefers a lighter fallback for this hardware."
            )
            continue
        if item.installed:
            if item.memory_tier in {"large", "xlarge"}:
                warnings.append(f"{item.id} is {item.memory_tier}; keep max_parallel={item.max_parallel}.")
            reason = (
                f"Selected installed local Ollama model {item.id} for profile {profile.id}."
                if model_id == preferred_model_id
                else f"Primary model unavailable; selected installed local fallback {item.id}."
            )
            return ModelRouteResult(
                selected_model=item.id,
                selected_provider=LOCAL_OLLAMA,
                fallback_model=profile.fallback_model,
                reason=reason,
                confidence=0.9 if model_id == preferred_model_id else 0.78,
                warnings=warnings,
            )

    fallback_id = profile.fallback_model or candidates[-1]
    fallback_item = registry.get(fallback_id)
    if fallback_item and _too_heavy_for_hardware(fallback_item, hardware_memory_gb):
        lighter = _first_lighter_local_model(registry, available_models)
        if lighter:
            fallback_id = lighter.id
            fallback_item = lighter
            warnings.append(f"Using lighter fallback {fallback_id} for current hardware constraints.")

    if fallback_id not in available_models:
        warnings.append(f"Local model '{fallback_id}' is not installed. Suggested command: ollama pull {fallback_id}")
    if requested_model and preferred_model_id not in available_models:
        warnings.append(f"Requested model '{preferred_model_id}' is not installed locally.")

    return ModelRouteResult(
        selected_model=fallback_id,
        selected_provider=LOCAL_OLLAMA,
        fallback_model=profile.fallback_model,
        reason=(
            f"No preferred local model is installed; selected configured fallback {fallback_id} "
            "and reported install guidance."
        ),
        confidence=0.45,
        warnings=warnings,
    )


def _try_external_route(
    *,
    profile: ModelProfile,
    provider_mode: ProviderMode,
    preferred_provider: str,
    provider_enabled: dict[str, bool],
    external_allowed: bool,
    task_type: str,
) -> ModelRouteResult | None:
    if provider_mode == ProviderMode.LOCAL or not external_allowed:
        return None

    provider_order = [preferred_provider, CLAUDE_CODE, CHATGPT_CODEX, EXTERNAL_API]
    for provider in provider_order:
        if provider not in EXTERNAL_PROVIDERS or provider not in profile.allowed_providers:
            continue
        if not provider_enabled.get(provider, False):
            continue
        model_id = _external_model_for_provider(provider)
        return ModelRouteResult(
            selected_model=model_id,
            selected_provider=provider,
            fallback_model=profile.fallback_model,
            reason=(
                f"Selected enabled external provider {provider} for {task_type} in {provider_mode.value} mode. "
                "Execution remains approval-gated."
            ),
            confidence=0.74,
            warnings=["External provider selected for routing only; execution is not implemented in this slice."],
        )
    return None


def _ordered_local_candidates(profile: ModelProfile, preferred_model_id: str) -> list[str]:
    raw = [
        preferred_model_id,
        profile.primary_model,
        profile.reasoning_model,
        profile.fast_model,
        profile.fallback_model,
        "qwen2.5-coder:7b",
    ]
    seen: set[str] = set()
    ordered: list[str] = []
    for model_id in raw:
        if model_id and model_id not in seen:
            seen.add(model_id)
            ordered.append(model_id)
    return ordered


def _preferred_model_for_task(profile: ModelProfile, task_type: str) -> str:
    normalized = (task_type or "").strip().lower()
    if normalized in QUICK_TASK_TYPES and profile.fast_model:
        return profile.fast_model
    if normalized in REASONING_TASK_TYPES and profile.reasoning_model:
        return profile.reasoning_model
    return profile.primary_model


def _external_model_for_provider(provider: str) -> str:
    if provider == CLAUDE_CODE:
        return "claude-code:sonnet"
    if provider == CHATGPT_CODEX:
        return "chatgpt-codex:default"
    return "external-api:default"


def _external_allowed(*, provider_mode: ProviderMode, privacy_level: str) -> tuple[bool, str]:
    if provider_mode == ProviderMode.LOCAL:
        return False, "Provider mode local prohibits external providers."
    normalized = (privacy_level or "private").strip().lower()
    if normalized in PRIVATE_PRIVACY_LEVELS:
        return False, "Project privacy level blocks external providers without explicit approval."
    return True, ""


def _provider_enabled_map(config: dict[str, Any]) -> dict[str, bool]:
    return {
        LOCAL_OLLAMA: True,
        CHATGPT_CODEX: bool(config.get("codex", {}).get("enabled", False)),
        CLAUDE_CODE: bool(config.get("claude", {}).get("enabled", False)),
        EXTERNAL_API: bool(config.get("external_api", {}).get("enabled", False)),
    }


def _normalize_provider_mode(mode: ProviderMode | str) -> ProviderMode:
    if isinstance(mode, ProviderMode):
        return mode
    try:
        return ProviderMode(str(mode))
    except ValueError:
        return ProviderMode.LOCAL


def _too_heavy_for_hardware(item: ModelRegistryItem, hardware_memory_gb: float | None) -> bool:
    if hardware_memory_gb is None:
        return False
    if item.memory_tier == "xlarge" and hardware_memory_gb < 32:
        return True
    if item.memory_tier == "large" and hardware_memory_gb < 16:
        return True
    if item.memory_tier == "medium" and hardware_memory_gb < 8:
        return True
    return False


def _first_lighter_local_model(
    registry: dict[str, ModelRegistryItem],
    available_models: set[str],
) -> ModelRegistryItem | None:
    tier_rank = {"small": 0, "medium": 1, "large": 2, "xlarge": 3}
    installed_local = [
        item for item in registry.values()
        if item.provider == LOCAL_OLLAMA and item.id in available_models and item.memory_tier in {"small", "medium"}
    ]
    return sorted(installed_local, key=lambda item: (tier_rank[item.memory_tier], item.id))[0] if installed_local else None


def validate_agent_model_profiles() -> list[str]:
    """Return agent IDs whose model_profile is not registered."""
    profile_ids = set(MODEL_PROFILES)
    return [agent.id for agent in get_all_agents() if agent.model_profile not in profile_ids]


# ── Orchestrator Tool Planning ────────────────────────────────────────────────

# Maps canonical task_type → ordered list of recommended project tools.
# This is a *recommendation only* — no tool is executed automatically.
_TASK_TYPE_TOOLS: dict[str, list[str]] = {
    "planning": [
        "read-file",
        "search-code",
    ],
    "architecture": [
        "read-file",
        "search-code",
    ],
    "implementation": [
        "read-file",
        "search-code",
        "propose-patch",
        "apply-patch",
        "git-diff",
    ],
    "quick_fix": [
        "read-file",
        "search-code",
        "propose-patch",
        "apply-patch",
        "git-diff",
    ],
    "debugging": [
        "read-file",
        "search-code",
        "run-command",
        "analyze-command-result",
        "propose-patch",
    ],
    "test_generation": [
        "read-file",
        "search-code",
        "propose-patch",
        "run-command",
    ],
    "code_review": [
        "read-file",
        "search-code",
        "git-diff",
    ],
    "security_review": [
        "read-file",
        "search-code",
        "git-diff",
    ],
    "documentation": [
        "read-file",
        "search-code",
        "propose-patch",
    ],
    "deployment": [
        "read-file",
        "search-code",
        "run-command",
    ],
}

_DEFAULT_TOOLS = ["read-file", "search-code"]

_TASK_TYPE_REASONS: dict[str, str] = {
    "planning": "Planning steps need to read context and search existing code.",
    "architecture": "Architecture steps need to read context and search existing code.",
    "implementation": "Implementation steps read, search, propose and apply patches, then check git diff.",
    "quick_fix": "Quick-fix steps read, search, propose and apply patches, then check git diff.",
    "debugging": "Debugging steps read, search, run commands, analyze results, and propose patches.",
    "test_generation": "Test generation steps read, search, propose test files, and run tests.",
    "code_review": "Code review steps read, search, and inspect git diff.",
    "security_review": "Security review steps read, search, and inspect git diff (no auto-apply).",
    "documentation": "Documentation steps read, search, and propose doc patches.",
    "deployment": "Deployment steps read, search, and run deployment commands.",
}


def infer_tools_for_step(
    step: RunStep,
    agent_id: str = "",
    task_type: str = "",
) -> StepToolRecommendation:
    """Return a tool recommendation for a single staged step.

    This function is purely advisory — it returns a recommendation object and
    never executes any tool, creates any ToolCall, or modifies any file.

    Resolution order for task_type:
    1. Caller-supplied ``task_type`` (e.g. from a persisted route decision).
    2. ``infer_task_type_for_step`` using step title / input / agent_id.
    """
    effective_agent = agent_id or step.agent_id or ""
    effective_task_type = task_type
    if not effective_task_type:
        effective_task_type = infer_task_type_for_step(
            step.title, step.input, effective_agent
        )

    tools = list(_TASK_TYPE_TOOLS.get(effective_task_type, _DEFAULT_TOOLS))
    reason = _TASK_TYPE_REASONS.get(
        effective_task_type,
        f"No specific guidance for task type '{effective_task_type}'; defaulting to read/search.",
    )

    warnings: list[str] = []
    if effective_task_type not in _TASK_TYPE_TOOLS:
        warnings.append(
            f"Unknown task type '{effective_task_type}'; returned default tool set."
        )

    return StepToolRecommendation(
        step_id=step.id,
        agent_id=effective_agent,
        task_type=effective_task_type,
        recommended_tools=tools,
        reason=reason,
        confidence=0.9 if effective_task_type in _TASK_TYPE_TOOLS else 0.5,
        warnings=warnings,
    )


# ── Orchestrator Guided Execution ─────────────────────────────────────────────

import json as _json


def _calls_for_step(step_id: str, all_calls: list[ToolCall]) -> list[ToolCall]:
    """Return all ToolCalls associated with a step, sorted oldest-first."""
    return sorted(
        [c for c in all_calls if c.step_id == step_id],
        key=lambda c: c.started_at or c.created_at,
    )


def _latest_of_tool(calls: list[ToolCall], *tool_names: str) -> ToolCall | None:
    """Most recent completed call with one of the given tool_names."""
    matches = [c for c in calls if c.tool_name in tool_names and c.status == "completed"]
    return matches[-1] if matches else None


def _has_completed(calls: list[ToolCall], *tool_names: str) -> bool:
    return _latest_of_tool(calls, *tool_names) is not None


def _failed_run_command(calls: list[ToolCall]) -> ToolCall | None:
    """Most recent run-command that failed (returncode != 0 or timed_out)."""
    candidates = [
        c for c in calls
        if c.tool_name in ("run-command", "run-project-command", "run-tests")
        and c.status == "completed"
    ]
    for c in reversed(candidates):
        try:
            out = _json.loads(c.output_json or "{}")
            if out.get("timed_out") or (c.returncode is not None and c.returncode != 0):
                return c
        except (ValueError, AttributeError):
            if c.returncode is not None and c.returncode != 0:
                return c
    return None


def _passing_run_command(calls: list[ToolCall]) -> ToolCall | None:
    """Most recent run-command that passed (returncode == 0)."""
    candidates = [
        c for c in calls
        if c.tool_name in ("run-command", "run-project-command", "run-tests")
        and c.status == "completed"
    ]
    for c in reversed(candidates):
        try:
            out = _json.loads(c.output_json or "{}")
            if not out.get("timed_out") and c.returncode == 0:
                return c
        except (ValueError, AttributeError):
            if c.returncode == 0:
                return c
    return None


def _analysis_has_issues(call: ToolCall) -> bool:
    """True if an analyze-command-result call returned any issues."""
    try:
        out = _json.loads(call.output_json or "{}")
        issues = out.get("issues", [])
        return bool(issues)
    except (ValueError, AttributeError):
        return False


def _action(
    step_id: str,
    action_id: str,
    action_type: str,
    title: str,
    *,
    tool_name: str = "",
    description: str = "",
    reason: str = "",
    requires_confirmation: bool = False,
    risk_level: str = "low",
    enabled: bool = True,
    blocked_reason: str = "",
    related_tool_call_id: str = "",
    related_proposal_id: str = "",
) -> GuidedStepAction:
    return GuidedStepAction(
        step_id=step_id,
        action_id=action_id,
        action_type=action_type,
        tool_name=tool_name,
        title=title,
        description=description,
        reason=reason,
        requires_confirmation=requires_confirmation,
        risk_level=risk_level,
        enabled=enabled,
        blocked_reason=blocked_reason,
        related_tool_call_id=related_tool_call_id,
        related_proposal_id=related_proposal_id,
    )


def build_guided_step_actions(
    step: RunStep,
    tool_plan: StepToolRecommendation,
    all_run_calls: list[ToolCall],
    route_decision: "ModelRouteDecision | None" = None,
) -> GuidedStepExecutionPlan:
    """Build a guided action plan for a single step.

    Heuristic-only. Purely advisory — no side effects, no tool execution,
    no ToolCall creation, no file writes.

    Decision tree (evaluated in order — first matching rule wins for
    recommended_next_action):
    1.  No read/search calls          → search_code (low risk)
    2.  read/search but no propose    → propose_patch (medium)
    3.  propose completed, no apply   → apply_patch (high, confirm required)
    4.  apply completed, no run-tests → run_tests (medium)
    5.  run-command failed, no analyze→ analyze_result (low)
    6.  analyze has issues            → propose_patch again (medium)
    7.  run-command passed            → review_diff or done (low)
    8.  rollback present              → status_summary reflects rollback
    """
    sid = step.id
    calls = _calls_for_step(sid, all_run_calls)
    warnings: list[str] = []
    actions: list[GuidedStepAction] = []

    # Detect key states
    has_read   = _has_completed(calls, "read-file", "list-files")
    has_search = _has_completed(calls, "search-code")
    has_propose = _latest_of_tool(calls, "propose-patch")
    has_apply   = _latest_of_tool(calls, "apply-patch")
    has_rollback = _has_completed(calls, "rollback-patch")
    failed_cmd  = _failed_run_command(calls)
    passed_cmd  = _passing_run_command(calls)
    latest_analyze = _latest_of_tool(calls, "analyze-command-result")
    has_issues  = latest_analyze and _analysis_has_issues(latest_analyze)

    # ── Build full actions list (all possible actions for this task_type) ──
    recommended_tools = set(tool_plan.recommended_tools)

    if "read-file" in recommended_tools or "search-code" in recommended_tools:
        actions.append(_action(
            sid, "search_code", "search_code",
            "Search / Read Context",
            tool_name="search-code",
            description="Search the codebase or read relevant files to understand context.",
            reason="Always useful before making changes.",
            risk_level="low",
        ))

    if "propose-patch" in recommended_tools:
        proposal_id = has_propose.id if has_propose else ""
        actions.append(_action(
            sid, "propose_patch", "propose_patch",
            "Propose Patch",
            tool_name="propose-patch",
            description="Preview a patch without applying it. Fill the patch form manually.",
            reason="Required before apply-patch. No files are changed.",
            risk_level="medium",
            related_tool_call_id=has_propose.id if has_propose else "",
            related_proposal_id=proposal_id,
        ))

    if "apply-patch" in recommended_tools:
        proposal_id = has_propose.id if has_propose else ""
        enabled = bool(has_propose)
        actions.append(_action(
            sid, "apply_patch", "apply_patch",
            "Apply Patch",
            tool_name="apply-patch",
            description=(
                "Apply the proposed patch. Requires manual confirm=true in the patch form. "
                "High risk — modifies project files."
            ),
            reason="Execute the patch once you have reviewed the proposal.",
            requires_confirmation=True,
            risk_level="high",
            enabled=enabled,
            blocked_reason="" if enabled else "No completed propose-patch found for this step.",
            related_proposal_id=proposal_id,
        ))

    # run_tests and analyze_result are universal follow-ups whenever a patch
    # can be applied (apply-patch in recommended_tools) OR a run-command is
    # explicitly recommended. Always include them so the decision tree can
    # reference them regardless of task type.
    if "run-command" in recommended_tools or "run-tests" in recommended_tools or "apply-patch" in recommended_tools:
        actions.append(_action(
            sid, "run_tests", "run_tests",
            "Run Tests / Command",
            tool_name="run-command",
            description="Run the project test or build command to verify changes.",
            reason="Validates that patches did not break anything.",
            risk_level="medium",
            related_tool_call_id=has_apply.id if has_apply else "",
        ))

    if "analyze-command-result" in recommended_tools or "apply-patch" in recommended_tools:
        failed_id = failed_cmd.id if failed_cmd else ""
        enabled_analyze = bool(failed_cmd)
        actions.append(_action(
            sid, "analyze_result", "analyze_result",
            "Analyze Command Result",
            tool_name="analyze-command-result",
            description="Analyze the failed command output to identify issues and suggested fixes.",
            reason="Use after a failing test/build run.",
            risk_level="low",
            enabled=enabled_analyze,
            blocked_reason="" if enabled_analyze else "No failed run-command found for this step.",
            related_tool_call_id=failed_id,
        ))

    if "git-diff" in recommended_tools:
        actions.append(_action(
            sid, "review_diff", "review_diff",
            "Review Git Diff",
            tool_name="git-diff",
            description="Inspect current git diff to review all changes before marking done.",
            reason="Confirm final state of changes.",
            risk_level="low",
        ))

    if has_rollback:
        actions.append(_action(
            sid, "rollback_patch", "rollback_patch",
            "Rollback Patch",
            tool_name="rollback-patch",
            description="A rollback was already performed for this step.",
            reason="Rollback detected in tool history.",
            risk_level="high",
            requires_confirmation=True,
        ))

    # Done action always present
    actions.append(_action(
        sid, "done", "done",
        "Mark Step Done",
        description="All recommended actions completed. Mark this step as done.",
        risk_level="low",
    ))

    # ── Determine recommended_next_action (decision tree) ──
    recommended: GuidedStepAction | None = None
    status_parts: list[str] = []

    if has_rollback:
        status_parts.append("rollback applied")

    # Priority order (spec v1) — state-based checks are unconditional;
    # tool-list checks only gate actions that are intrinsic to the task type.
    if failed_cmd and not latest_analyze:
        # Highest priority: a command failed and hasn't been analyzed yet.
        recommended = next((a for a in actions if a.action_id == "analyze_result"), None)
        status_parts.append("command failed, analysis pending")

    elif latest_analyze and has_issues and "propose-patch" in recommended_tools:
        recommended = next((a for a in actions if a.action_id == "propose_patch"), None)
        status_parts.append("issues found, needs patch")

    elif has_apply and not (failed_cmd or passed_cmd):
        # Apply done but no command run yet → always suggest running tests.
        recommended = next((a for a in actions if a.action_id == "run_tests"), None)
        status_parts.append("patch applied, tests not run")

    elif has_propose and not has_apply and "apply-patch" in recommended_tools:
        recommended = next((a for a in actions if a.action_id == "apply_patch"), None)
        status_parts.append(f"proposal ready ({has_propose.id})")

    elif not (has_read or has_search):
        recommended = next((a for a in actions if a.action_id == "search_code"), None)
        status_parts.append("no read/search calls yet")

    elif not has_propose and "propose-patch" in recommended_tools:
        recommended = next((a for a in actions if a.action_id == "propose_patch"), None)
        status_parts.append("context gathered, patch not yet proposed")

    elif passed_cmd:
        recommended = next(
            (a for a in actions if a.action_id in ("review_diff", "done")),
            None,
        )
        status_parts.append("tests passing")

    elif not recommended_tools.intersection(
        {"propose-patch", "apply-patch", "run-command", "analyze-command-result"}
    ):
        # read-only task type (planning, architecture, code_review…)
        if has_read or has_search:
            recommended = next((a for a in actions if a.action_id in ("review_diff", "done")), None)
            status_parts.append("context gathered")
        else:
            recommended = next((a for a in actions if a.action_id == "search_code"), None)
            status_parts.append("no context yet")

    if not recommended:
        recommended = next((a for a in actions if a.action_id == "done"), None)
        status_parts.append("no pending action identified")

    if not status_parts:
        status_parts.append("in progress")

    status_summary = "; ".join(status_parts)

    agent_id = (route_decision.agent_id if route_decision else None) or step.agent_id or ""
    task_type = (route_decision.task_type if route_decision else None) or tool_plan.task_type or ""

    return GuidedStepExecutionPlan(
        run_id=step.run_id,
        step_id=sid,
        agent_id=agent_id,
        task_type=task_type,
        recommended_next_action=recommended,
        actions=actions,
        status_summary=status_summary,
        warnings=warnings,
    )


# ── Step Context Bundle ───────────────────────────────────────────────────────

import json as _json  # local alias to avoid shadowing outer scope

_READ_ONLY_TOOLS: frozenset[str] = frozenset({"list_files", "search_code", "read_file"})


def _first_text_value(*values: object) -> str:
    """Return the first value that is a non-empty string; skip ints and None."""
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
_IGNORED_TOOLS: frozenset[str] = frozenset({
    "propose_patch", "apply_patch", "rollback_patch",
    "run_command", "run-command", "analyze_result", "run_tests", "run-command",
})


def build_step_context_bundle(
    run_id: str,
    step: RunStep,
    tool_calls: list[ToolCall],
    route_decision: ModelRouteDecision | None = None,
) -> StepContextBundle:
    """Aggregate existing read-only ToolCalls for *step* into a StepContextBundle.

    Pure read: never creates ToolCalls, never executes tools, never reads files.
    """
    step_calls = [
        tc for tc in tool_calls
        if tc.run_id == run_id and tc.step_id == step.id
    ]

    # Filter to read-only completed calls only
    read_calls = [
        tc for tc in step_calls
        if tc.tool_name in _READ_ONLY_TOOLS and tc.status == "completed"
    ]

    warnings: list[str] = []
    queries: list[str] = []
    all_tc_ids = [tc.id for tc in read_calls]

    # file_path → StepContextFile accumulator
    file_map: dict[str, StepContextFile] = {}

    def _get_file(path: str) -> StepContextFile:
        if path not in file_map:
            file_map[path] = StepContextFile(file_path=path)
        return file_map[path]

    def _parse_json(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            return _json.loads(raw)
        except Exception:
            return {}

    list_files_seen: list[str] = []

    for tc in read_calls:
        inp = _parse_json(tc.input_json)
        out = _parse_json(tc.output_json)

        if tc.tool_name == "search_code":
            query = inp.get("query", "")
            if query and query not in queries:
                queries.append(query)
            matches: list[dict] = out.get("matches", [])
            for m in matches:
                path = m.get("path", "")
                if not path:
                    continue
                f = _get_file(path)
                f.source_tool_call_ids.append(tc.id)
                f.match_count += 1
                f.reason = f.reason or f"matched search query '{query}'"
                # Collect snippet — only from text fields; skip line (int line number)
                snippet_text = _first_text_value(
                    m.get("context"),
                    m.get("snippet"),
                    m.get("text"),
                    m.get("content"),
                    m.get("line_text"),
                    m.get("preview"),
                )
                if snippet_text and len(f.snippets) < BUNDLE_MAX_SNIPPETS_PER_FILE:
                    f.snippets.append(snippet_text[:BUNDLE_MAX_SNIPPET_CHARS])

        elif tc.tool_name == "read_file":
            path = inp.get("file_path", inp.get("path", ""))
            if not path:
                continue
            f = _get_file(path)
            f.read = True
            if tc.id not in f.source_tool_call_ids:
                f.source_tool_call_ids.append(tc.id)
            f.reason = f.reason or "file was read directly"
            content: str = out.get("content", "")
            if content and len(f.snippets) < BUNDLE_MAX_SNIPPETS_PER_FILE:
                preview = content[:BUNDLE_MAX_SNIPPET_CHARS]
                f.snippets.append(preview)
                if len(content) > BUNDLE_MAX_SNIPPET_CHARS:
                    warnings.append(
                        f"'{path}' content truncated to {BUNDLE_MAX_SNIPPET_CHARS} chars in snippet."
                    )

        elif tc.tool_name == "list_files":
            listed = out.get("files", [])
            for item in listed:
                p = item.get("path", item) if isinstance(item, dict) else str(item)
                if p and p not in list_files_seen:
                    list_files_seen.append(p)

    # Rank files: read > has matches > search-only
    def _rank(f: StepContextFile) -> int:
        return (10 if f.read else 0) + f.match_count

    sorted_files = sorted(file_map.values(), key=_rank, reverse=True)

    if len(sorted_files) > BUNDLE_MAX_FILES:
        warnings.append(
            f"{len(sorted_files)} files found; showing top {BUNDLE_MAX_FILES}."
        )
        sorted_files = sorted_files[:BUNDLE_MAX_FILES]

    # Determine status and next_recommended_action
    has_reads = any(f.read for f in sorted_files)
    has_matches = any(f.match_count > 0 for f in sorted_files)
    has_any = bool(sorted_files)

    read_only_task_types = {"review", "research", "analysis", "read-only"}
    agent_id = (route_decision.agent_id if route_decision else None) or step.agent_id or None
    task_type = (route_decision.task_type if route_decision else None) or getattr(step, "task_type", None)

    if not has_any:
        status = "empty"
        next_action: str | None = "auto_gather_context"
        warnings.append("No read-only context collected for this step yet.")
    elif has_reads:
        status = "ok"
        next_action = "done" if task_type in read_only_task_types else "propose_patch"
    elif has_matches:
        status = "partial"
        next_action = "read_context"
    else:
        status = "partial"
        next_action = "search_code"

    n_files = len(sorted_files)
    n_queries = len(queries)
    summary = (
        f"{n_queries} query/queries searched, {n_files} file(s) in bundle"
        + (f", {sum(f.match_count for f in sorted_files)} match(es)" if has_matches else "")
        + f". Next: {next_action}."
    )

    return StepContextBundle(
        run_id=run_id,
        step_id=step.id,
        agent_id=agent_id,
        task_type=task_type,
        status=status,
        summary=summary,
        queries=queries,
        files=sorted_files,
        tool_call_ids=all_tc_ids,
        warnings=warnings,
        next_recommended_action=next_action,
    )


# ── Context Patch Draft ───────────────────────────────────────────────────────

def build_context_patch_draft(
    run_id: str,
    step: RunStep,
    bundle: StepContextBundle,
    request: ContextPatchDraftRequest,
) -> ContextPatchDraftResponse:
    """Build draft patch candidates from an existing StepContextBundle.

    Pure read: no ToolCalls created, no tools executed, no files read or modified,
    no patch proposals created, no LLM calls.
    """
    warnings: list[str] = []

    # Empty bundle — nothing to work with
    if bundle.status == "empty" or not bundle.files:
        return ContextPatchDraftResponse(
            run_id=run_id,
            step_id=step.id,
            status="no_context",
            summary="No context collected for this step yet.",
            candidates=[],
            recommended_candidate_index=None,
            warnings=["Context bundle is empty. Run Auto Gather Context first."],
            next_recommended_action="auto_gather_context",
        )

    # ── Rank files ────────────────────────────────────────────────────────────
    def _file_score(f: StepContextFile) -> tuple:
        preferred = (f.file_path == request.preferred_file_path) if request.preferred_file_path else False
        return (preferred, f.read, bool(f.snippets), f.match_count)

    ranked = sorted(bundle.files, key=_file_score, reverse=True)

    # Up to 3 candidates
    candidates: list[ContextPatchDraftCandidate] = []

    for ctx_file in ranked[:3]:
        cand_warnings: list[str] = []

        # Select snippet
        snippets = ctx_file.snippets
        idx = request.preferred_snippet_index
        if idx is not None and 0 <= idx < len(snippets):
            raw_snippet = snippets[idx]
        elif snippets:
            raw_snippet = snippets[0]
        else:
            raw_snippet = ""

        # Derive old_text
        if raw_snippet:
            old_text = raw_snippet[:DRAFT_MAX_OLD_TEXT_CHARS]
            if len(raw_snippet) > DRAFT_MAX_OLD_TEXT_CHARS:
                cand_warnings.append(
                    f"Snippet truncated to {DRAFT_MAX_OLD_TEXT_CHARS} chars; old_text may be incomplete."
                )
        else:
            old_text = ""
            cand_warnings.append("No snippet available — old_text is empty. Add context before creating proposal.")

        if old_text and len(old_text) < 10:
            cand_warnings.append("old_text is very short; verify it uniquely identifies the target location.")

        # Confidence
        if ctx_file.read and raw_snippet:
            confidence = 0.8
        elif ctx_file.match_count > 0 and raw_snippet:
            confidence = 0.6
        else:
            confidence = 0.3

        # Reason
        intent_note = f" Intent: {request.intent}." if request.intent else ""
        if ctx_file.read:
            reason = f"File was read directly.{intent_note}"
        elif ctx_file.match_count > 0:
            reason = f"File matched {ctx_file.match_count} search query/queries.{intent_note}"
        else:
            reason = f"File selected by heuristic.{intent_note}"

        candidates.append(ContextPatchDraftCandidate(
            file_path=ctx_file.file_path,
            old_text=old_text,
            new_text=DRAFT_PLACEHOLDER_NEW_TEXT if old_text else "",
            reason=reason,
            confidence=confidence,
            source_tool_call_ids=ctx_file.source_tool_call_ids,
            warnings=cand_warnings,
        ))

    if not candidates:
        warnings.append("Could not build any candidates from the context bundle.")
        return ContextPatchDraftResponse(
            run_id=run_id,
            step_id=step.id,
            status="no_context",
            summary="No usable context found in bundle.",
            candidates=[],
            recommended_candidate_index=None,
            warnings=warnings,
            next_recommended_action="auto_gather_context",
        )

    # Best candidate = highest confidence
    best_idx = max(range(len(candidates)), key=lambda i: candidates[i].confidence)

    if bundle.warnings:
        warnings.extend([f"Bundle warning: {w}" for w in bundle.warnings])

    n = len(candidates)
    top = candidates[best_idx]
    summary = (
        f"{n} draft candidate(s) from {len(bundle.files)} bundled file(s). "
        f"Top candidate: '{top.file_path}' (confidence {top.confidence:.0%}). "
        "Review and edit before creating proposal."
    )

    return ContextPatchDraftResponse(
        run_id=run_id,
        step_id=step.id,
        status="ok",
        summary=summary,
        candidates=candidates,
        recommended_candidate_index=best_idx,
        warnings=warnings,
        next_recommended_action="propose_patch",
    )


# ── Patch Proposal Review ─────────────────────────────────────────────────────

# Paths that should never be patched in this project.
_DATABASE_PROTECTED = "backend/src/storage/database.py"

# Minimum old_text length below which a warning is raised (too short to be safe).
_OLD_TEXT_MIN_WARNING = 8

# Warn if estimated diff exceeds this many lines.
_DIFF_WARN_LINES = 200

# Warn if more than this many operations are in one request.
_MAX_OPS_BEFORE_WARN = 5


def review_patch_operations(
    project_path: str,
    operations: list[PatchReviewOperation],
) -> PatchReviewResponse:
    """Pure read-only review of patch operations. Never modifies files or creates tool_calls."""
    from pathlib import Path
    from src.utils.workspace_tools import _looks_secret, _resolve_inside, _project_root

    try:
        root = _project_root(project_path)
    except (ValueError, OSError) as exc:
        return PatchReviewResponse(
            status="blocked",
            summary=f"Project path invalid: {exc}",
            safe_to_create_proposal=False,
            safe_to_apply=False,
        )

    global_issues: list[PatchReviewIssue] = []

    # Operation-count warning
    if len(operations) > _MAX_OPS_BEFORE_WARN:
        global_issues.append(PatchReviewIssue(
            severity="warning",
            code="too_many_operations",
            message=f"{len(operations)} operations in one request — consider splitting into smaller batches.",
        ))

    # Duplicate file_path warning
    seen_paths: dict[str, int] = {}
    for idx, op in enumerate(operations):
        key = op.file_path.strip()
        if key in seen_paths:
            global_issues.append(PatchReviewIssue(
                severity="warning",
                code="duplicate_file_path",
                message=f"file_path '{key}' appears in operations {seen_paths[key]} and {idx} — duplicate edits may conflict.",
                file_path=key,
                operation_index=idx,
            ))
        else:
            seen_paths[key] = idx

    op_results: list[PatchReviewOperationResult] = []
    any_blocked = False
    any_warning = False

    for idx, op in enumerate(operations):
        issues: list[PatchReviewIssue] = []
        op_status = "ok"
        old_text_found = False
        old_text_occurrences = 0
        estimated_diff_lines = 0

        def _issue(severity: str, code: str, message: str) -> PatchReviewIssue:
            return PatchReviewIssue(
                severity=severity,
                code=code,
                message=message,
                file_path=op.file_path or None,
                operation_index=idx,
            )

        # ── file_path checks ────────────────────────────────────────────────
        if not op.file_path.strip():
            issues.append(_issue("blocker", "empty_file_path", "file_path is empty."))
            op_status = "blocked"
            any_blocked = True
            op_results.append(PatchReviewOperationResult(
                operation_index=idx,
                file_path=op.file_path,
                status=op_status,
                old_text_found=old_text_found,
                old_text_occurrences=old_text_occurrences,
                estimated_diff_lines=estimated_diff_lines,
                issues=issues,
            ))
            continue

        # Path traversal / outside workspace
        try:
            resolved = _resolve_inside(root, op.file_path)
        except ValueError as exc:
            issues.append(_issue("blocker", "path_traversal", f"Path rejected: {exc}"))
            op_status = "blocked"
            any_blocked = True
            op_results.append(PatchReviewOperationResult(
                operation_index=idx,
                file_path=op.file_path,
                status=op_status,
                issues=issues,
            ))
            continue

        # Secret-like file
        if _looks_secret(resolved):
            issues.append(_issue("blocker", "sensitive_file", f"'{op.file_path}' is a secret-like file and cannot be patched."))
            op_status = "blocked"
            any_blocked = True

        # database.py protection
        try:
            rel = resolved.relative_to(root).as_posix()
        except ValueError:
            rel = op.file_path
        if rel == _DATABASE_PROTECTED or rel.endswith("/" + _DATABASE_PROTECTED.split("/")[-1] if "/" in _DATABASE_PROTECTED else _DATABASE_PROTECTED):
            # More precise: match the canonical relative path
            pass  # handled below with exact match

        if rel == _DATABASE_PROTECTED:
            issues.append(_issue("blocker", "protected_file",
                f"'{op.file_path}' is the database module and is protected from patching."))
            op_status = "blocked"
            any_blocked = True

        # File existence (only if not already blocked for other reasons)
        file_exists = resolved.is_file()
        if not file_exists:
            issues.append(_issue("blocker", "file_not_found", f"'{op.file_path}' does not exist in the project."))
            op_status = "blocked"
            any_blocked = True
            op_results.append(PatchReviewOperationResult(
                operation_index=idx,
                file_path=op.file_path,
                status=op_status,
                issues=issues,
            ))
            continue

        # ── old_text checks ─────────────────────────────────────────────────
        if not op.old_text:
            issues.append(_issue("blocker", "empty_old_text",
                "old_text is empty — this would replace the entire file or create ambiguous replacement."))
            op_status = "blocked"
            any_blocked = True
        else:
            try:
                content = resolved.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                issues.append(_issue("blocker", "file_read_error", f"Could not read file: {exc}"))
                op_status = "blocked"
                any_blocked = True
                op_results.append(PatchReviewOperationResult(
                    operation_index=idx,
                    file_path=op.file_path,
                    status=op_status,
                    issues=issues,
                ))
                continue

            occurrences = content.count(op.old_text)
            old_text_occurrences = occurrences
            old_text_found = occurrences > 0

            if len(op.old_text) < _OLD_TEXT_MIN_WARNING:
                issues.append(_issue("warning", "old_text_too_short",
                    f"old_text is only {len(op.old_text)} chars — very short strings risk unintended matches."))
                if op_status == "ok":
                    op_status = "warning"
                    any_warning = True

            if occurrences == 0:
                issues.append(_issue("blocker", "old_text_not_found",
                    "old_text was not found in the file — patch would fail or silently do nothing."))
                op_status = "blocked"
                any_blocked = True
            elif occurrences > 1:
                issues.append(_issue("blocker", "old_text_ambiguous",
                    f"old_text found {occurrences} times — replacement is ambiguous. Use a longer, unique match."))
                op_status = "blocked"
                any_blocked = True

            # Estimate diff size
            old_lines = op.old_text.count("\n") + 1
            new_lines = op.new_text.count("\n") + 1 if op.new_text else 0
            estimated_diff_lines = old_lines + new_lines
            if estimated_diff_lines > _DIFF_WARN_LINES:
                issues.append(_issue("warning", "large_diff",
                    f"Estimated diff is ~{estimated_diff_lines} lines — review carefully before applying."))
                if op_status == "ok":
                    op_status = "warning"
                    any_warning = True

        # ── new_text checks ─────────────────────────────────────────────────
        if not op.new_text and op.old_text:
            issues.append(_issue("warning", "empty_new_text",
                "new_text is empty — this will delete the matched text. Confirm this is intentional."))
            if op_status == "ok":
                op_status = "warning"
                any_warning = True

        if op.new_text and op.old_text and op.new_text == op.old_text:
            issues.append(_issue("blocker", "new_text_same_as_old",
                "new_text is identical to old_text — this patch would make no changes."))
            op_status = "blocked"
            any_blocked = True

        if op_status == "warning":
            any_warning = True

        op_results.append(PatchReviewOperationResult(
            operation_index=idx,
            file_path=op.file_path,
            status=op_status,
            old_text_found=old_text_found,
            old_text_occurrences=old_text_occurrences,
            estimated_diff_lines=estimated_diff_lines,
            issues=issues,
        ))

    # Aggregate global issues from op results
    all_issues = global_issues[:]
    for res in op_results:
        all_issues.extend(res.issues)

    if any_blocked:
        overall = "blocked"
    elif any_warning:
        overall = "warning"
    else:
        overall = "ok"

    blocker_count = sum(1 for i in all_issues if i.severity == "blocker")
    warning_count = sum(1 for i in all_issues if i.severity == "warning")

    parts: list[str] = []
    if blocker_count:
        parts.append(f"{blocker_count} blocker(s)")
    if warning_count:
        parts.append(f"{warning_count} warning(s)")
    if not parts:
        parts.append("no issues")

    summary = (
        f"Reviewed {len(operations)} operation(s): {', '.join(parts)}. "
        + ("Safe to proceed." if overall == "ok" else
           "Review warnings before proceeding." if overall == "warning" else
           "Blocked — resolve issues before creating proposal.")
    )

    safe_to_create_proposal = overall != "blocked"
    safe_to_apply = overall == "ok"

    return PatchReviewResponse(
        status=overall,
        summary=summary,
        operation_results=op_results,
        issues=all_issues,
        safe_to_create_proposal=safe_to_create_proposal,
        safe_to_apply=safe_to_apply,
    )


# ── Approval-gated Patch Workflow Orchestrator ────────────────────────────────

def _calls_by_tool(tool_calls: list[ToolCall], *tool_names: str) -> list[ToolCall]:
    """Filter completed tool_calls by tool_name(s)."""
    return [tc for tc in tool_calls if tc.tool_name in tool_names and tc.status == "completed"]


def _has_tool(tool_calls: list[ToolCall], *tool_names: str) -> bool:
    return bool(_calls_by_tool(tool_calls, *tool_names))


def _ids(tool_calls: list[ToolCall]) -> list[str]:
    return [tc.id for tc in tool_calls]


def build_step_patch_workflow_plan(
    run_id: str,
    step: RunStep,
    tool_calls: list[ToolCall],
    route_decision: ModelRouteDecision | None = None,
) -> StepPatchWorkflowPlan:
    """Pure read-only helper. Analyses tool_call history for a step and returns a workflow plan.

    Never creates tool_calls, reads/writes files, or executes tools.
    """
    # Filter to only this step's completed calls (and include run-level calls without step_id)
    step_calls = [
        tc for tc in tool_calls
        if tc.run_id == run_id and (tc.step_id == step.id or not tc.step_id)
    ]

    # ── Classify relevant call groups ────────────────────────────────────────
    context_calls = _calls_by_tool(step_calls, "list_files", "search_code", "read_file",
                                   "list-files", "search-code", "read-file")
    propose_calls = _calls_by_tool(step_calls, "propose-patch", "propose_patch")
    apply_calls   = _calls_by_tool(step_calls, "apply-patch", "apply_patch")
    rollback_calls = _calls_by_tool(step_calls, "rollback-patch", "rollback_patch")
    run_cmd_calls  = _calls_by_tool(step_calls, "run-command", "run_command")
    analyze_calls  = _calls_by_tool(step_calls, "analyze-command-result", "analyze_command_result")

    # Detect passed / failed runs
    passed_runs = [tc for tc in run_cmd_calls if tc.returncode == 0]
    failed_runs = [tc for tc in run_cmd_calls if tc.returncode is not None and tc.returncode != 0]

    has_context    = bool(context_calls)
    has_proposal   = bool(propose_calls)
    has_apply      = bool(apply_calls)
    has_passed_run = bool(passed_runs)
    has_failed_run = bool(failed_runs)
    has_analysis   = bool(analyze_calls)
    has_rollback   = bool(rollback_calls)

    stages: list[PatchWorkflowStage] = []
    warnings: list[str] = []
    blockers: list[str] = []

    # ── A. Context gathering ──────────────────────────────────────────────────
    if has_context:
        ctx_status = "completed"
        ctx_summary = f"{len(context_calls)} context read call(s) logged."
    else:
        ctx_status = "ready"
        ctx_summary = "No context reads yet — gather context to understand the codebase."
    stages.append(PatchWorkflowStage(
        stage_id="context_gathering",
        title="Context Gathering",
        status=ctx_status,
        summary=ctx_summary,
        related_tool_call_ids=_ids(context_calls),
    ))

    # ── B. Context bundle ─────────────────────────────────────────────────────
    # Bundle is built from context calls; if context exists, bundle can be built
    bundle_status = "completed" if has_context else "not_started"
    bundle_summary = (
        "Context calls available — context bundle can be built."
        if has_context else
        "Gather context first."
    )
    stages.append(PatchWorkflowStage(
        stage_id="context_bundle",
        title="Context Bundle",
        status=bundle_status,
        summary=bundle_summary,
        related_tool_call_ids=_ids(context_calls),
    ))

    # ── C. Patch draft ────────────────────────────────────────────────────────
    draft_status = "completed" if has_context else ("ready" if has_context else "not_started")
    draft_status = "ready" if has_context and not has_proposal else ("completed" if has_proposal else "not_started")
    draft_summary = (
        "Proposal already created." if has_proposal else
        "Context available — create a patch draft to pre-fill the proposal form." if has_context else
        "Gather context first."
    )
    stages.append(PatchWorkflowStage(
        stage_id="patch_draft",
        title="Patch Draft",
        status=draft_status,
        summary=draft_summary,
        related_tool_call_ids=_ids(propose_calls),
    ))

    # ── D. Patch review ───────────────────────────────────────────────────────
    review_status = "completed" if has_proposal else ("ready" if has_context else "not_started")
    review_summary = (
        "Proposal created — review was part of pre-proposal check." if has_proposal else
        "Review the patch before creating a proposal." if has_context else
        "Gather context and draft patch first."
    )
    stages.append(PatchWorkflowStage(
        stage_id="patch_review",
        title="Patch Review",
        status=review_status,
        summary=review_summary,
    ))

    # ── E. Proposal ───────────────────────────────────────────────────────────
    if has_proposal:
        proposal_status = "completed"
        proposal_summary = f"{len(propose_calls)} propose-patch call(s) completed."
    elif has_context:
        proposal_status = "ready"
        proposal_summary = "Context ready — fill in the Patch Proposal form to create a proposal."
    else:
        proposal_status = "not_started"
        proposal_summary = "Gather context and review patch before creating a proposal."
    stages.append(PatchWorkflowStage(
        stage_id="proposal",
        title="Patch Proposal",
        status=proposal_status,
        summary=proposal_summary,
        related_tool_call_ids=_ids(propose_calls),
    ))

    # ── F. Apply ─────────────────────────────────────────────────────────────
    if has_apply:
        apply_status = "completed"
        apply_summary = f"{len(apply_calls)} apply-patch call(s) completed."
        if has_rollback:
            apply_status = "warning"
            apply_summary += " (patch was later rolled back)"
            warnings.append("A previously applied patch was rolled back.")
    elif has_proposal:
        apply_status = "ready"
        apply_summary = "Proposal exists — confirm and apply using the patch form."
    else:
        apply_status = "not_started"
        apply_summary = "Create a proposal first."
    stages.append(PatchWorkflowStage(
        stage_id="apply",
        title="Apply Patch",
        status=apply_status,
        summary=apply_summary,
        related_tool_call_ids=_ids(apply_calls + rollback_calls),
        warnings=["Patch was rolled back — consider a new proposal."] if has_rollback else [],
    ))

    # ── G. Tests ─────────────────────────────────────────────────────────────
    if has_passed_run:
        tests_status = "completed"
        tests_summary = "Tests passed."
    elif has_failed_run:
        tests_status = "warning"
        tests_summary = f"{len(failed_runs)} test run(s) failed — analyse results."
        warnings.append("Test run failed — see Analysis stage.")
    elif has_apply:
        tests_status = "ready"
        tests_summary = "Patch applied — run tests to verify the change."
    else:
        tests_status = "not_started"
        tests_summary = "Apply patch first."
    stages.append(PatchWorkflowStage(
        stage_id="tests",
        title="Run Tests",
        status=tests_status,
        summary=tests_summary,
        related_tool_call_ids=_ids(run_cmd_calls),
    ))

    # ── H. Analysis ──────────────────────────────────────────────────────────
    if has_analysis:
        analysis_status = "completed"
        analysis_summary = "Command result analysis completed."
    elif has_failed_run:
        analysis_status = "ready"
        analysis_summary = "Tests failed — analyse the output to find the issue."
    else:
        analysis_status = "not_started"
        analysis_summary = "Run tests first."
    stages.append(PatchWorkflowStage(
        stage_id="analysis",
        title="Analyse Results",
        status=analysis_status,
        summary=analysis_summary,
        related_tool_call_ids=_ids(analyze_calls),
    ))

    # ── I. Done ───────────────────────────────────────────────────────────────
    is_done = has_passed_run and not has_failed_run and not has_rollback
    done_status = "completed" if is_done else "not_started"
    done_summary = "All stages complete — tests passing, no rollbacks." if is_done else "Complete all preceding stages."
    stages.append(PatchWorkflowStage(
        stage_id="done",
        title="Done",
        status=done_status,
        summary=done_summary,
    ))

    # ── Recommended next action ───────────────────────────────────────────────
    next_action: PatchWorkflowNextAction | None = None

    if is_done:
        next_action = PatchWorkflowNextAction(
            action_type="done",
            title="Workflow complete",
            description="Tests are passing and no rollbacks pending. No further action required.",
            risk_level="low",
            requires_confirmation=False,
        )
    elif has_failed_run and not has_analysis:
        next_action = PatchWorkflowNextAction(
            action_type="analyze_result",
            title="Analyse test result",
            description="Click 'Analyze command result' on the failed run-command call in the Tool Calls panel.",
            risk_level="low",
            requires_confirmation=False,
        )
    elif has_failed_run and has_analysis:
        # After analysis, suggest a new patch iteration
        next_action = PatchWorkflowNextAction(
            action_type="create_patch_draft",
            title="Create a new patch draft",
            description="Analysis complete — use the Context Patch Draft to build a new fix proposal.",
            risk_level="medium",
            requires_confirmation=False,
        )
    elif has_apply and not has_passed_run:
        next_action = PatchWorkflowNextAction(
            action_type="run_tests_manual",
            title="Run tests manually",
            description="Use the 'Run Tests' button in the Guided Fix Workflow to verify the patch.",
            risk_level="medium",
            requires_confirmation=True,
        )
    elif has_proposal and not has_apply:
        next_action = PatchWorkflowNextAction(
            action_type="apply_patch_manual",
            title="Apply patch (manual confirm required)",
            description="Check the confirmation box in the Patch Proposal form and click Apply Patch.",
            risk_level="high",
            requires_confirmation=True,
        )
    elif has_context and not has_proposal:
        next_action = PatchWorkflowNextAction(
            action_type="review_patch",
            title="Review patch before proposal",
            description="Fill in the Patch Proposal form, click 'Review Patch' to check safety, then create the proposal.",
            risk_level="low",
            requires_confirmation=False,
        )
    elif has_context:
        next_action = PatchWorkflowNextAction(
            action_type="create_patch_draft",
            title="Build patch draft from context",
            description="Open the Guided tab → Context Bundle section → 'Create Patch Draft from Context'.",
            risk_level="low",
            requires_confirmation=False,
        )
    else:
        next_action = PatchWorkflowNextAction(
            action_type="auto_gather_context",
            title="Gather context",
            description="Open the Guided tab → 'Auto Gather Context' to read relevant files for this step.",
            risk_level="low",
            requires_confirmation=False,
        )

    # ── Overall plan status ───────────────────────────────────────────────────
    if is_done:
        plan_status = "done"
    elif has_passed_run:
        plan_status = "done"
    elif has_failed_run:
        plan_status = "in_progress"
    elif has_apply:
        plan_status = "ready_for_tests"
    elif has_proposal:
        plan_status = "ready_for_review"
    elif has_context:
        plan_status = "in_progress"
    else:
        plan_status = "not_started"

    completed_count = sum(1 for s in stages if s.status == "completed")
    summary = (
        f"Step '{step.title}': {completed_count}/{len(stages)} stages complete. "
        f"Next: {next_action.title}." if next_action else
        f"Step '{step.title}': workflow complete."
    )

    return StepPatchWorkflowPlan(
        run_id=run_id,
        step_id=step.id,
        agent_id=step.agent_id or (route_decision.agent_id if route_decision else None),
        task_type=route_decision.task_type if route_decision else None,
        status=plan_status,
        summary=summary,
        stages=stages,
        recommended_next_action=next_action,
        warnings=warnings,
        blockers=blockers,
    )


def build_patch_workflow_plan(
    run_id: str,
    steps: list[RunStep],
    tool_calls: list[ToolCall],
    route_decisions: dict[str, ModelRouteDecision] | None = None,
) -> PatchWorkflowPlanResponse:
    """Build a PatchWorkflowPlanResponse for all child steps in a run."""
    rd = route_decisions or {}
    child_steps = [s for s in steps if s.parent_step_id]
    if not child_steps:
        # Fall back to all steps if no hierarchy
        child_steps = steps

    step_plans = [
        build_step_patch_workflow_plan(
            run_id=run_id,
            step=step,
            tool_calls=tool_calls,
            route_decision=rd.get(step.id),
        )
        for step in child_steps
    ]

    total = len(step_plans)
    done_count = sum(1 for p in step_plans if p.status == "done")
    all_warnings = [w for p in step_plans for w in p.warnings]

    if total == 0:
        summary = "No steps found for this run."
    elif done_count == total:
        summary = f"All {total} step(s) complete."
    else:
        summary = f"{done_count}/{total} step(s) complete."

    return PatchWorkflowPlanResponse(
        run_id=run_id,
        steps=step_plans,
        summary=summary,
        warnings=all_warnings,
    )

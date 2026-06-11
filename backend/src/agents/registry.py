"""Agent registry — loads agent definitions from markdown files."""

from __future__ import annotations

import json
from pathlib import Path

from src.models import AgentInfo, ProviderType
from src.utils.paths import PROJECT_ROOT, repo_path

AGENTS_DIR = repo_path("agents")

READ_ONLY_TOOLS = ["read_file", "search_code", "git_status", "save_report"]
PATCH_TOOLS = [*READ_ONLY_TOOLS, "propose_patch"]

MODEL_PROFILE_DEFAULTS = {
    # Heavy reasoning & planning — use qwen3-coder:30b (installed, 18.6 GB)
    # Fast fallback — qwen2.5-coder:7b (installed, 4.7 GB)
    "planning_reasoning": {
        "default_model": "qwen3-coder:30b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    "coding_heavy": {
        "default_model": "qwen3-coder:30b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    "debugging": {
        "default_model": "qwen3-coder:30b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    "security_review": {
        "default_model": "qwen3-coder:30b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    # Documentation & quick tasks — use fast model to save time
    "documentation": {
        "default_model": "qwen2.5-coder:7b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    "vision_ui": {
        "default_model": "qwen2.5-coder:7b",
        "fast_model": "qwen2.5-coder:7b",
        "reasoning_model": "qwen3-coder:30b",
    },
    "embeddings": {
        "default_model": "nomic-embed-text",
        "fast_model": "nomic-embed-text",
        "reasoning_model": "",
    },
}

LEGACY_AGENT_ALIASES = {
    "backend": "backend-developer",
    "frontend": "frontend-developer",
    "qa": "qa-expert",
    "security": "security-auditor",
    "docs": "technical-writer",
    "mobile": "mobile-developer",
}


def _agent(
    *,
    id: str,
    name: str,
    role: str,
    description: str,
    category: str,
    skills: list[str],
    model_profile: str,
    best_for: list[str],
    instructions_file: str = "",
    default_tools: list[str] | None = None,
    default_model: str = "",
    fast_model: str = "",
    reasoning_model: str = "",
    can_edit_files: bool = False,
    can_run_commands: bool = False,
    risk_level: str = "low",
) -> AgentInfo:
    profile_defaults = MODEL_PROFILE_DEFAULTS.get(model_profile, {})
    return AgentInfo(
        id=id,
        name=name,
        role=role,
        description=description,
        provider=ProviderType.OLLAMA,
        instructions_file=instructions_file,
        category=category,
        skills=skills,
        default_tools=default_tools or READ_ONLY_TOOLS,
        model_profile=model_profile,
        default_model=default_model or profile_defaults.get("default_model", ""),
        fast_model=fast_model or profile_defaults.get("fast_model", ""),
        reasoning_model=reasoning_model or profile_defaults.get("reasoning_model", ""),
        can_edit_files=can_edit_files,
        can_run_commands=can_run_commands,
        risk_level=risk_level,
        enabled=True,
        best_for=best_for,
    )


# Built-in registry. These are templates, not automatically active workers.
DEFAULT_AGENTS: list[AgentInfo] = [
    _agent(
        id="orchestrator",
        name="Orchestrator",
        role="orchestrator",
        description="Plans runs, selects agents, coordinates approvals, and supervises execution.",
        category="meta-orchestration",
        skills=["planning", "routing", "delegation", "risk-management"],
        model_profile="planning_reasoning",
        best_for=["run planning", "team assignment", "workflow control"],
        instructions_file="agents/orchestrator.md",
    ),
    _agent(
        id="product-manager",
        name="Product Manager",
        role="product",
        description="Defines scope, user stories, MVP boundaries, and acceptance criteria.",
        category="business-product",
        skills=["requirements", "prioritization", "acceptance-criteria"],
        model_profile="planning_reasoning",
        best_for=["new product scoping", "MVP slicing", "feature prioritization"],
    ),
    _agent(
        id="business-analyst",
        name="Business Analyst",
        role="analysis",
        description="Maps workflows, business rules, edge cases, and domain constraints.",
        category="business-product",
        skills=["workflows", "business-rules", "edge-cases"],
        model_profile="planning_reasoning",
        best_for=["domain logic", "process modeling", "requirements clarification"],
    ),
    _agent(
        id="architect",
        name="Architect",
        role="architecture",
        description="Designs system boundaries, data flow, module structure, and integration choices.",
        category="core-development",
        skills=["architecture", "module-boundaries", "data-flow"],
        model_profile="planning_reasoning",
        best_for=["system design", "technical decomposition", "integration boundaries"],
    ),
    _agent(
        id="api-designer",
        name="API Designer",
        role="api",
        description="Designs REST/GraphQL contracts, schemas, validation, and API documentation.",
        category="core-development",
        skills=["rest-api", "graphql", "openapi", "contracts"],
        model_profile="planning_reasoning",
        best_for=["API contracts", "request/response design", "frontend/backend alignment"],
    ),
    _agent(
        id="frontend-developer",
        name="Frontend Developer",
        role="frontend",
        description="Builds UI components, pages, styling, and client-side logic.",
        category="core-development",
        skills=["frontend", "ui", "react", "typescript", "css"],
        model_profile="coding_heavy",
        best_for=["pages", "components", "client API integration"],
        instructions_file="agents/frontend.md",
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="backend-developer",
        name="Backend Developer",
        role="backend",
        description="Implements backend logic, APIs, database schemas, and server code.",
        category="core-development",
        skills=["backend", "api", "database", "services"],
        model_profile="coding_heavy",
        best_for=["server logic", "routes", "data persistence"],
        instructions_file="agents/backend.md",
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="fullstack-developer",
        name="Fullstack Developer",
        role="fullstack",
        description="Coordinates end-to-end features across UI, API, and persistence.",
        category="core-development",
        skills=["fullstack", "feature-slicing", "integration"],
        model_profile="coding_heavy",
        best_for=["vertical feature slices", "frontend/backend integration"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="react-specialist",
        name="React Specialist",
        role="frontend_specialist",
        description="Expert in React application structure, component design, hooks, and state flow.",
        category="language-specialist",
        skills=["react", "hooks", "state-management", "vite"],
        model_profile="coding_heavy",
        best_for=["React screens", "component architecture", "frontend polish"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="typescript-pro",
        name="TypeScript Pro",
        role="language_specialist",
        description="Improves TypeScript types, contracts, narrowing, and maintainability.",
        category="language-specialist",
        skills=["typescript", "types", "typecheck", "contracts"],
        model_profile="coding_heavy",
        best_for=["type safety", "frontend/backend DTO contracts", "compiler errors"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="fastapi-developer",
        name="FastAPI Developer",
        role="backend_specialist",
        description="Expert in FastAPI, Pydantic models, async APIs, and Python service structure.",
        category="language-specialist",
        skills=["python", "fastapi", "pydantic", "async", "rest-api"],
        model_profile="coding_heavy",
        best_for=["FastAPI routes", "Pydantic schemas", "backend tests"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="node-specialist",
        name="Node Specialist",
        role="backend_specialist",
        description="Handles Node.js services, package scripts, build tooling, and APIs.",
        category="language-specialist",
        skills=["node", "javascript", "npm", "backend"],
        model_profile="coding_heavy",
        best_for=["Node services", "npm scripts", "server tooling"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="php-pro",
        name="PHP Pro",
        role="language_specialist",
        description="Supports PHP applications, framework code, Composer projects, and legacy PHP.",
        category="language-specialist",
        skills=["php", "composer", "laravel", "symfony"],
        model_profile="coding_heavy",
        best_for=["PHP projects", "Composer apps", "framework migration"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="sql-pro",
        name="SQL Pro",
        role="data",
        description="Designs SQL queries, schema changes, indexes, and relational data flows.",
        category="data-ai",
        skills=["sql", "sqlite", "postgres", "schema", "queries"],
        model_profile="coding_heavy",
        best_for=["database schema", "query review", "data modeling"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="postgres-pro",
        name="Postgres Pro",
        role="data",
        description="Specialist for PostgreSQL schema, performance, migrations, and operations.",
        category="data-ai",
        skills=["postgresql", "indexes", "migrations", "performance"],
        model_profile="debugging",
        best_for=["Postgres schema", "query performance", "migration review"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="mobile-developer",
        name="Mobile Developer",
        role="mobile",
        description="Develops mobile applications across React Native, Flutter, Android, and iOS.",
        category="core-development",
        skills=["mobile", "react-native", "flutter", "android", "ios"],
        model_profile="coding_heavy",
        best_for=["mobile app structure", "screens", "platform-specific constraints"],
        instructions_file="agents/mobile.md",
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="qa-expert",
        name="QA Expert",
        role="qa",
        description="Plans and runs verification, test strategy, smoke tests, and regression checks.",
        category="qa-security",
        skills=["testing", "pytest", "typecheck", "build", "smoke-tests"],
        model_profile="debugging",
        best_for=["test strategy", "verification", "interpreting failures"],
        instructions_file="agents/qa.md",
        default_tools=READ_ONLY_TOOLS,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="test-automator",
        name="Test Automator",
        role="qa",
        description="Adds focused automated tests and strengthens regression coverage.",
        category="qa-security",
        skills=["unit-tests", "integration-tests", "automation", "coverage"],
        model_profile="debugging",
        best_for=["test generation", "coverage gaps", "regression suites"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="medium",
    ),
    _agent(
        id="code-reviewer",
        name="Code Reviewer",
        role="review",
        description="Reviews diffs for correctness, maintainability, and behavioral regressions.",
        category="qa-security",
        skills=["code-review", "diff-analysis", "maintainability"],
        model_profile="debugging",
        best_for=["pre-merge review", "regression spotting", "quality gates"],
    ),
    _agent(
        id="security-auditor",
        name="Security Auditor",
        role="security",
        description="Reviews code for vulnerabilities, path traversal, secrets, and command safety.",
        category="qa-security",
        skills=["security", "path-safety", "secrets", "approvals", "threat-modeling"],
        model_profile="security_review",
        best_for=["auth/RBAC", "file access", "dangerous commands", "secrets review"],
        instructions_file="agents/security.md",
    ),
    _agent(
        id="devops-engineer",
        name="DevOps Engineer",
        role="devops",
        description="Handles local launch, Docker, CI, deployment checklists, and environment health.",
        category="infrastructure",
        skills=["docker", "ci", "deployment", "environment", "healthchecks"],
        model_profile="planning_reasoning",
        best_for=["Docker", "CI/CD", "local/prod launch", "environment validation"],
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        can_run_commands=True,
        risk_level="high",
    ),
    _agent(
        id="technical-writer",
        name="Technical Writer",
        role="docs",
        description="Writes documentation, README updates, API docs, and final reports.",
        category="developer-experience",
        skills=["documentation", "readme", "api-docs", "reports"],
        model_profile="documentation",
        best_for=["README", "usage docs", "release notes", "final reports"],
        instructions_file="agents/docs.md",
        default_tools=PATCH_TOOLS,
        can_edit_files=True,
        risk_level="low",
    ),
    _agent(
        id="error-detective",
        name="Error Detective",
        role="debugging",
        description="Analyzes errors, test failures, logs, and root causes before fixes.",
        category="qa-security",
        skills=["debugging", "stack-traces", "root-cause-analysis"],
        model_profile="debugging",
        best_for=["test failures", "runtime errors", "root cause reports"],
    ),
    _agent(
        id="git-workflow-manager",
        name="Git Workflow Manager",
        role="developer_experience",
        description="Advises on branches, commits, diffs, and safe local git workflows.",
        category="developer-experience",
        skills=["git", "diffs", "commits", "release-flow"],
        model_profile="planning_reasoning",
        best_for=["commit planning", "diff summaries", "branch workflow"],
    ),
]


STACK_AGENT_RULES: list[tuple[list[str], list[tuple[str, str, float]]]] = [
    (["react", "vite", "jsx", "tsx", "frontend", "ui", "component"], [
        ("frontend-developer", "Frontend/UI work detected.", 0.88),
        ("react-specialist", "React/Vite/UI stack detected.", 0.84),
        ("typescript-pro", "TypeScript or TSX likely involved.", 0.76),
    ]),
    (["fastapi", "pydantic", "python api"], [
        ("backend-developer", "Backend/API work detected.", 0.88),
        ("fastapi-developer", "FastAPI/Pydantic stack detected.", 0.88),
    ]),
    (["backend", "api", "server", "endpoint", "route"], [
        ("backend-developer", "Server-side/API task detected.", 0.82),
        ("api-designer", "API contract or endpoint work may be needed.", 0.72),
    ]),
    (["node", "express", "npm", "javascript"], [
        ("node-specialist", "Node.js or npm stack detected.", 0.8),
        ("typescript-pro", "JavaScript/TypeScript tooling may be involved.", 0.7),
    ]),
    (["php", "composer", "laravel", "symfony"], [
        ("php-pro", "PHP/Composer stack detected.", 0.86),
    ]),
    (["sqlite", "sql", "database", "db", "postgres", "postgresql"], [
        ("sql-pro", "Database or SQL work detected.", 0.84),
    ]),
    (["postgres", "postgresql"], [
        ("postgres-pro", "PostgreSQL-specific work detected.", 0.88),
    ]),
    (["mobile", "android", "ios", "flutter", "react native", "expo"], [
        ("mobile-developer", "Mobile application work detected.", 0.88),
    ]),
    (["auth", "rbac", "permission", "security", "secret", "payment", "token"], [
        ("security-auditor", "Security-sensitive feature detected.", 0.9),
    ]),
    (["docker", "deploy", "deployment", "ci/cd", "pipeline", "kubernetes"], [
        ("devops-engineer", "Infrastructure or deployment work detected.", 0.86),
        ("security-auditor", "Infrastructure changes should be security-reviewed.", 0.72),
    ]),
    (["test", "pytest", "typecheck", "build", "qa", "verify"], [
        ("qa-expert", "Verification work detected.", 0.86),
        ("test-automator", "Automated tests may be needed.", 0.78),
    ]),
    (["bug", "error", "traceback", "fix", "failed", "failure"], [
        ("error-detective", "Failure/debugging task detected.", 0.88),
        ("qa-expert", "Verification is needed after debugging.", 0.72),
    ]),
    (["readme", "docs", "documentation", "guide"], [
        ("technical-writer", "Documentation work detected.", 0.86),
    ]),
    (["review", "audit", "refactor"], [
        ("code-reviewer", "Review/refactor quality gate detected.", 0.82),
    ]),
]


# ── Canonical role → agent_id mapping ────────────────────────────────────────

# Maps common role strings (from intake plans, multi-agent plan steps, bridge
# agent_role values) to canonical registry agent IDs.
# Lookup is case-insensitive and slug-normalized.
_ROLE_TO_CANONICAL: dict[str, str] = {
    # exact canonical IDs (identity)
    "orchestrator": "orchestrator",
    "product-manager": "product-manager",
    "business-analyst": "business-analyst",
    "architect": "architect",
    "api-designer": "api-designer",
    "frontend-developer": "frontend-developer",
    "backend-developer": "backend-developer",
    "fullstack-developer": "fullstack-developer",
    "react-specialist": "react-specialist",
    "typescript-pro": "typescript-pro",
    "fastapi-developer": "fastapi-developer",
    "node-specialist": "node-specialist",
    "php-pro": "php-pro",
    "sql-pro": "sql-pro",
    "postgres-pro": "postgres-pro",
    "mobile-developer": "mobile-developer",
    "qa-expert": "qa-expert",
    "test-automator": "test-automator",
    "code-reviewer": "code-reviewer",
    "security-auditor": "security-auditor",
    "devops-engineer": "devops-engineer",
    "technical-writer": "technical-writer",
    "error-detective": "error-detective",
    "git-workflow-manager": "git-workflow-manager",
    # role aliases and free-form strings from intake pipeline
    "product_analyst": "business-analyst",
    "product analyst": "business-analyst",
    "productanalyst": "business-analyst",
    "product manager": "product-manager",
    "productmanager": "product-manager",
    "software-architect": "architect",
    "software architect": "architect",
    "softwarearchitect": "architect",
    "backend_agent": "backend-developer",
    "backend agent": "backend-developer",
    "backendagent": "backend-developer",
    "backend": "backend-developer",
    "frontend_agent": "frontend-developer",
    "frontend agent": "frontend-developer",
    "frontendagent": "frontend-developer",
    "frontend": "frontend-developer",
    "database_agent": "postgres-pro",
    "database agent": "postgres-pro",
    "databaseagent": "postgres-pro",
    "database": "sql-pro",
    "database-engineer": "postgres-pro",
    "qa_agent": "qa-expert",
    "qa agent": "qa-expert",
    "qaagent": "qa-expert",
    "qa": "qa-expert",
    "security_guard_agent": "security-auditor",
    "security guard agent": "security-auditor",
    "securityguardagent": "security-auditor",
    "security": "security-auditor",
    "devops_agent": "devops-engineer",
    "devops agent": "devops-engineer",
    "devopsagent": "devops-engineer",
    "devops": "devops-engineer",
    "delivery_reviewer_agent": "technical-writer",
    "delivery reviewer agent": "technical-writer",
    "deliveryrevieweragent": "technical-writer",
    "technical writer": "technical-writer",
    "technicalwriter": "technical-writer",
    "docs": "technical-writer",
    "documentation": "technical-writer",
    "error detective": "error-detective",
    "errordetective": "error-detective",
    "context analyst": "orchestrator",
    "contextanalyst": "orchestrator",
    "context confirmation": "orchestrator",
    "contextconfirmation": "orchestrator",
    "context-analyst": "orchestrator",
    "module reviewer": "architect",
    "modulereviewer": "architect",
    "module-reviewer": "architect",
    "repo_analyst": "business-analyst",
    "repo analyst": "business-analyst",
    "repoanalyst": "business-analyst",
    "fullstack": "fullstack-developer",
    "mobile": "mobile-developer",
    "api": "api-designer",
}

# Approved fallback IDs used when no canonical match is found.
_CANONICAL_FALLBACK = "orchestrator"


def canonical_agent_id_for_role(role: str) -> str:
    """Map an agent_role string to a canonical registry agent_id.

    Deterministic, case-insensitive, slug-normalized.
    Returns a safe fallback ("orchestrator") if no match is found.
    Never raises.

    Preference order:
    1. Direct normalized lookup in _ROLE_TO_CANONICAL
    2. Slug-normalized lookup (spaces→dashes, underscores→dashes)
    3. Keyword-based heuristic
    4. Safe fallback: "orchestrator"
    """
    if not role:
        return _CANONICAL_FALLBACK

    key = role.strip().lower()

    # Direct lookup (handles spaces and underscores as-is)
    if key in _ROLE_TO_CANONICAL:
        return _ROLE_TO_CANONICAL[key]

    # Slug-normalized lookup
    slug = key.replace(" ", "-").replace("_", "-")
    if slug in _ROLE_TO_CANONICAL:
        return _ROLE_TO_CANONICAL[slug]

    # Check if the slug is already a valid canonical registry ID
    if get_agent(slug) is not None:
        return slug

    # Keyword heuristic (last resort before fallback)
    if "backend" in key or "fastapi" in key or "django" in key or "flask" in key:
        return "backend-developer"
    if "frontend" in key or "react" in key or "vue" in key or "angular" in key:
        return "frontend-developer"
    if "mobile" in key or "android" in key or "ios" in key or "flutter" in key:
        return "mobile-developer"
    if "postgres" in key or "database" in key or "sql" in key:
        return "postgres-pro"
    if "test" in key or "qa" in key or "quality" in key:
        return "qa-expert"
    if "security" in key or "guard" in key or "audit" in key:
        return "security-auditor"
    if "devops" in key or "deploy" in key or "infra" in key or "docker" in key:
        return "devops-engineer"
    if "doc" in key or "writer" in key or "report" in key or "readme" in key:
        return "technical-writer"
    if "error" in key or "debug" in key or "fix" in key:
        return "error-detective"
    if "architect" in key or "design" in key:
        return "architect"
    if "product" in key or "analyst" in key or "business" in key:
        return "business-analyst"
    if "fullstack" in key or "full-stack" in key or "full stack" in key:
        return "fullstack-developer"

    return _CANONICAL_FALLBACK


def get_all_agents() -> list[AgentInfo]:
    """Return all registered agents."""
    return DEFAULT_AGENTS


def get_enabled_agents() -> list[AgentInfo]:
    """Return enabled agent templates."""
    return [agent for agent in DEFAULT_AGENTS if agent.enabled]


def get_agent(agent_id: str) -> AgentInfo | None:
    """Return agent by ID."""
    agent_id = LEGACY_AGENT_ALIASES.get(agent_id, agent_id)
    for a in DEFAULT_AGENTS:
        if a.id == agent_id:
            return a
    return None


def select_agents_for_task(
    *,
    prompt: str,
    project_name: str = "",
    project_path: str = "",
    project_stack: str = "",
    package_manager: str = "",
) -> dict:
    """Select a small run team from the registry using conservative local rules."""
    project_signals = detect_project_signals(project_path)
    detected_stack = _merge_unique(
        _split_stack(project_stack),
        project_signals["detected_stack"],
    )
    signal_text = " ".join(
        [
            prompt,
            project_name,
            project_path,
            project_stack,
            package_manager,
            " ".join(detected_stack),
            " ".join(project_signals["project_files"]),
            " ".join(project_signals["folders"]),
            " ".join(project_signals["keywords"]),
        ]
    )
    text = signal_text.lower()
    selected: dict[str, dict] = {}

    def add(agent_id: str, assigned_role: str, reason: str, confidence: float) -> None:
        agent = get_agent(agent_id)
        if not agent or not agent.enabled:
            return
        current = selected.get(agent_id)
        if current and current["confidence"] >= confidence:
            return
        selected[agent_id] = {
            "agent_id": agent_id,
            "assigned_role": assigned_role,
            "reason": reason,
            "confidence": round(confidence, 2),
            "status": "selected",
        }

    add("orchestrator", "lead", "Every run needs a coordinator.", 0.99)
    add("business-analyst", "analysis", "Project context and requirements should be inspected before implementation.", 0.88)
    add("product-manager", "scope", "The task should be framed with acceptance criteria.", 0.72)
    add("architect", "architecture", "Architecture and boundaries should be explicit before execution.", 0.72)
    add("qa-expert", "verification", "Every run needs a verification path.", 0.86)

    for keywords, agents in STACK_AGENT_RULES:
        if any(keyword in text for keyword in keywords):
            for agent_id, reason, confidence in agents:
                agent = get_agent(agent_id)
                add(agent_id, agent.role if agent else "specialist", reason, confidence)

    # General software builds benefit from docs and review, but keep the team compact.
    if any(keyword in text for keyword in ["build", "create", "implement", "develop", "application", "app", "project"]):
        add("fullstack-developer", "implementation", "General implementation work detected.", 0.7)
        add("code-reviewer", "review", "Implementation work should have a review gate.", 0.68)
        add("technical-writer", "documentation", "Final user-facing documentation/report may be needed.", 0.64)

    ordered = sorted(
        selected.values(),
        key=lambda item: (-item["confidence"], item["agent_id"]),
    )
    selected_agents = ordered[:10]
    return {
        "selected_agents": selected_agents,
        "team_size": len(selected_agents),
        "recommended_execution_mode": _recommend_execution_mode(text),
        "detected_stack": detected_stack,
        "signals": project_signals,
    }


def detect_project_signals(project_path: str) -> dict:
    """Read a small, safe set of project metadata files and infer stack signals."""
    signals = {
        "detected_stack": [],
        "project_files": [],
        "folders": [],
        "keywords": [],
    }
    if not project_path:
        return signals

    root = Path(project_path).expanduser().resolve(strict=False)
    if not root.exists() or not root.is_dir():
        return signals

    def inside(path: Path) -> bool:
        resolved = path.resolve(strict=False)
        return resolved == root or root in resolved.parents

    def add_stack(*items: str) -> None:
        signals["detected_stack"] = _merge_unique(signals["detected_stack"], list(items))

    def add_keyword(*items: str) -> None:
        signals["keywords"] = _merge_unique(signals["keywords"], list(items))

    def note_file(path: Path) -> None:
        if inside(path):
            signals["project_files"].append(str(path.relative_to(root)))

    for folder in ["frontend", "backend", "src", "app", "mobile", "tests", "test", "docs", "config"]:
        candidate = root / folder
        if candidate.is_dir() and inside(candidate):
            signals["folders"].append(folder)
            add_keyword(folder)

    package_json = root / "package.json"
    if package_json.is_file() and inside(package_json):
        note_file(package_json)
        add_stack("javascript", "node")
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        deps = {
            **(data.get("dependencies") or {}),
            **(data.get("devDependencies") or {}),
        }
        scripts = data.get("scripts") or {}
        add_keyword(*deps.keys(), *scripts.keys())
        if "react" in deps:
            add_stack("react")
        if "vite" in deps or "vite" in scripts:
            add_stack("vite")
        if "typescript" in deps or (root / "tsconfig.json").is_file():
            add_stack("typescript")
        if "next" in deps:
            add_stack("nextjs")
        if "vue" in deps:
            add_stack("vue")

    for filename in ["pyproject.toml", "requirements.txt"]:
        path = root / filename
        if path.is_file() and inside(path):
            note_file(path)
            add_stack("python")
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                content = ""
            add_keyword(filename, content[:2000])
            if "fastapi" in content:
                add_stack("fastapi")
            if "pydantic" in content:
                add_stack("pydantic")
            if "django" in content:
                add_stack("django")
            if "flask" in content:
                add_stack("flask")
            if "pytest" in content:
                add_stack("pytest")

    composer_json = root / "composer.json"
    if composer_json.is_file() and inside(composer_json):
        note_file(composer_json)
        add_stack("php", "composer")
        try:
            data = json.loads(composer_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        deps = {
            **(data.get("require") or {}),
            **(data.get("require-dev") or {}),
        }
        add_keyword(*deps.keys())
        if any("laravel" in dep for dep in deps):
            add_stack("laravel")
        if any("symfony" in dep for dep in deps):
            add_stack("symfony")

    docker_files = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]
    for filename in docker_files:
        path = root / filename
        if path.is_file() and inside(path):
            note_file(path)
            add_stack("docker")
            add_keyword("docker", "deploy")

    for filename in ["tsconfig.json", "vite.config.ts", "vite.config.js", "tailwind.config.js"]:
        path = root / filename
        if path.is_file() and inside(path):
            note_file(path)
            add_stack("typescript" if filename == "tsconfig.json" else "frontend")
            add_keyword(filename)

    for readme in ["README.md", "README.txt", "readme.md"]:
        path = root / readme
        if path.is_file() and inside(path):
            note_file(path)
            try:
                content = path.read_text(encoding="utf-8", errors="ignore").lower()
            except OSError:
                content = ""
            add_keyword(readme, content[:1200])

    for pattern in ["*.db", "*.sqlite", "*.sqlite3", "schema.sql"]:
        for path in root.glob(pattern):
            if path.is_file() and inside(path):
                note_file(path)
                add_stack("database", "sqlite")

    signals["project_files"] = _merge_unique([], signals["project_files"])
    signals["folders"] = _merge_unique([], signals["folders"])
    signals["keywords"] = _merge_unique([], signals["keywords"])
    return signals


def _split_stack(stack: str) -> list[str]:
    normalized = stack.replace(",", " ").replace("/", " ")
    return [item.strip().lower() for item in normalized.split() if item.strip()]


def _merge_unique(*lists: list[str]) -> list[str]:
    seen: set[str] = set()
    merged: list[str] = []
    for items in lists:
        for item in items:
            normalized = str(item).strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            merged.append(normalized)
    return merged


def _recommend_execution_mode(text: str) -> str:
    if any(keyword in text for keyword in ["deploy", "production", "security", "payment", "compliance", "auth"]):
        return "offline"
    return "offline"


def load_agent_instructions(agent_id: str) -> str:
    """Load the markdown instructions file for an agent."""
    agent = get_agent(agent_id)
    if not agent or not agent.instructions_file:
        return ""
    path = Path(agent.instructions_file)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

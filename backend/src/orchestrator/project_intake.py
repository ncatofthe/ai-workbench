"""Project intake question generator for AI Workbench.

Pure deterministic module — no DB access, no LLM calls, no tool execution,
no side effects.  Accepts a raw project idea and returns structured questions
the operator should answer before plan generation begins.
"""

from __future__ import annotations

import json
import enum
import re
import tomllib
import uuid
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from src.agents.registry import canonical_agent_id_for_role, detect_project_signals

from src.orchestrator.source_of_truth_contract import (
    AcceptanceStatus,
    DriftRiskLevel,
    ProjectAcceptanceCriterion,
    ProjectAntiDriftRule,
    ProjectConstraintContract,
    ProjectInputSourceType,
    ProjectRequirementContract,
    ProjectSourceOfTruthContract,
    RequirementCoverageMatrix,
    RequirementPriority,
    RequirementStatus,
    SourceOfTruthValidationResult,
    build_requirement_coverage_matrix,
    summarize_source_of_truth,
    validate_source_of_truth_contract,
)
from src.models import (
    _sot_contains_secret,
    _module_map_contains_secret,
    _module_map_path_is_safe,
    ProjectModuleMapItem,
    ProjectModuleMapUpsertRequest,
    ProjectSourceOfTruthRequirement,
    SourceOfTruthUpsertRequest,
)


# ── Enums ────────────────────────────────────────────────────────────────────


class ProjectIntakeMode(str, enum.Enum):
    NEW_PROJECT = "new_project"
    EXISTING_PROJECT = "existing_project"
    UNKNOWN = "unknown"


class ProjectTargetType(str, enum.Enum):
    WEB_APP = "web_app"
    MOBILE_APP = "mobile_app"
    DESKTOP_APP = "desktop_app"
    API_SERVICE = "api_service"
    CLI_TOOL = "cli_tool"
    AUTOMATION = "automation"
    UNKNOWN = "unknown"


class ProjectMaturityGoal(str, enum.Enum):
    MVP = "mvp"
    FULL_PRODUCT = "full_product"
    DIPLOMA = "diploma"
    PROTOTYPE = "prototype"
    INTERNAL_TOOL = "internal_tool"
    UNKNOWN = "unknown"


class QuestionCategory(str, enum.Enum):
    PRODUCT_GOAL = "product_goal"
    USERS_ROLES = "users_roles"
    PLATFORM = "platform"
    TECH_STACK = "tech_stack"
    DATA_STORAGE = "data_storage"
    AUTH_SECURITY = "auth_security"
    INTEGRATIONS = "integrations"
    FILES_UPLOADS = "files_uploads"
    PAYMENTS_BILLING = "payments_billing"
    NOTIFICATIONS = "notifications"
    UI_DESIGN = "ui_design"
    DEPLOYMENT = "deployment"
    EXISTING_PROJECT = "existing_project"
    CONSTRAINTS = "constraints"
    QUALITY_TESTING = "quality_testing"


class QuestionPriority(str, enum.Enum):
    REQUIRED = "required"
    RECOMMENDED = "recommended"
    OPTIONAL = "optional"


class ProjectBriefSectionStatus(str, enum.Enum):
    CONFIRMED = "confirmed"
    ASSUMED = "assumed"
    MISSING = "missing"


# ── Models ───────────────────────────────────────────────────────────────────


class ProjectIntakeQuestion(BaseModel):
    id: str = Field(default_factory=lambda: f"q-{uuid.uuid4().hex[:8]}")
    category: QuestionCategory
    priority: QuestionPriority
    question: str
    why_it_matters: str
    suggested_default: Optional[str] = None
    options: Optional[list[str]] = None


class ProjectIntakeRequest(BaseModel):
    idea: str
    mode: Optional[ProjectIntakeMode] = None
    existing_project_attached: Optional[bool] = None
    known_stack: Optional[list[str]] = None
    known_constraints: Optional[list[str]] = None
    user_goal: Optional[str] = None


class ProjectIntakeResponse(BaseModel):
    mode: ProjectIntakeMode
    detected_target_type: ProjectTargetType
    detected_maturity_goal: ProjectMaturityGoal
    summary: str
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    questions: list[ProjectIntakeQuestion] = Field(default_factory=list)
    ready_to_plan: bool = False
    recommended_next_step: str = ""
    confidence: str = "low"


class ProjectBriefSection(BaseModel):
    title: str
    content: str
    status: ProjectBriefSectionStatus
    notes: Optional[str] = None


class ProjectBriefDraftRequest(ProjectIntakeRequest):
    answers: Optional[dict[str, str]] = None


class ProjectBriefDraftResponse(BaseModel):
    title: str
    mode: ProjectIntakeMode
    target_type: ProjectTargetType
    maturity_goal: ProjectMaturityGoal
    readiness: str
    summary: str
    brief_markdown: str
    sections: list[ProjectBriefSection] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    open_questions: list[ProjectIntakeQuestion] = Field(default_factory=list)
    recommended_next_step: str = ""
    ready_to_plan: bool = False


class DevelopmentPlanPhaseStatus(str, enum.Enum):
    READY = "ready"
    NEEDS_INPUT = "needs_input"
    BLOCKED = "blocked"


class DevelopmentPlanPhase(BaseModel):
    id: str
    title: str
    description: str
    priority: QuestionPriority
    status: DevelopmentPlanPhaseStatus
    suggested_agent_id: Optional[str] = None
    depends_on: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class DevelopmentPlanSourceReadiness(BaseModel):
    intake_ready_to_plan: bool
    brief_ready_to_plan: bool


class DevelopmentPlanPreviewRequest(ProjectBriefDraftRequest):
    brief_markdown: Optional[str] = None


class DevelopmentPlanPreviewResponse(BaseModel):
    title: str
    mode: ProjectIntakeMode
    target_type: ProjectTargetType
    maturity_goal: ProjectMaturityGoal
    ready_to_start: bool
    summary: str
    phases: list[DevelopmentPlanPhase] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    recommended_agent_ids: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""
    source_readiness: DevelopmentPlanSourceReadiness


class SourceOfTruthPreviewRequest(DevelopmentPlanPreviewRequest):
    plan_summary: Optional[str] = None
    plan_phases: Optional[list[DevelopmentPlanPhase]] = None


class SourceOfTruthPreviewResponse(BaseModel):
    title: str
    source_of_truth: ProjectSourceOfTruthContract
    validation: SourceOfTruthValidationResult
    coverage_matrix: RequirementCoverageMatrix
    summary: str
    recommended_next_step: str = ""
    ready_to_plan: bool = False


class RequirementCoveragePreviewStatus(str, enum.Enum):
    COVERED = "covered"
    PARTIALLY_COVERED = "partially_covered"
    MISSING = "missing"
    UNCLEAR = "unclear"


class RequirementCoveragePlanPhaseLink(BaseModel):
    phase_id: str
    title: str


class RequirementCoveragePreviewItem(BaseModel):
    requirement_id: str
    title: str
    priority: RequirementPriority
    coverage_status: RequirementCoveragePreviewStatus
    linked_plan_phases: list[RequirementCoveragePlanPhaseLink] = Field(default_factory=list)
    notes: str = ""
    drift_risk: DriftRiskLevel = DriftRiskLevel.LOW


class UnlinkedPlanPhasePreviewItem(BaseModel):
    phase_id: str
    title: str
    reason: str
    risk_level: DriftRiskLevel = DriftRiskLevel.MEDIUM
    suggested_action: str = ""


class RequirementCoveragePreviewSummary(BaseModel):
    requirements_total: int
    covered_requirements: int
    partially_covered_requirements: int
    missing_requirements: int
    unclear_requirements: int
    unlinked_plan_phases: int
    drift_risk: DriftRiskLevel = DriftRiskLevel.LOW


class RequirementCoveragePreviewRequest(SourceOfTruthPreviewRequest):
    source_of_truth: Optional[ProjectSourceOfTruthContract] = None
    plan_preview: Optional[DevelopmentPlanPreviewResponse] = None


class RequirementCoveragePreviewResponse(BaseModel):
    title: str
    summary: RequirementCoveragePreviewSummary
    items: list[RequirementCoveragePreviewItem] = Field(default_factory=list)
    unlinked_plan_phases: list[UnlinkedPlanPhasePreviewItem] = Field(default_factory=list)
    drift_risks: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""


# ── Confirmed Plan → Run Step Preview models ────────────────────────────────


class ConfirmedRunStepPreview(BaseModel):
    """A single future run step derived from a plan phase."""

    id: str
    title: str
    description: str
    suggested_agent_id: Optional[str] = None
    required_requirement_ids: list[str] = Field(default_factory=list)
    coverage_status: RequirementCoveragePreviewStatus = RequirementCoveragePreviewStatus.UNCLEAR
    drift_risk: DriftRiskLevel = DriftRiskLevel.LOW
    depends_on: list[str] = Field(default_factory=list)
    expected_deliverables: list[str] = Field(default_factory=list)
    validation_notes: str = ""
    manual_approval_required: bool = False
    safe_to_prepare: bool = False


class ConfirmedPlanRunPreviewRequest(BaseModel):
    idea: str
    mode: Optional[ProjectIntakeMode] = None
    existing_project_attached: Optional[bool] = None
    known_stack: Optional[list[str]] = None
    known_constraints: Optional[list[str]] = None
    user_goal: Optional[str] = None


class ConfirmedPlanRunPreviewResponse(BaseModel):
    title: str
    ready_to_create_run: bool
    summary: str
    source_of_truth_ready: bool
    coverage_ready: bool
    steps: list[ConfirmedRunStepPreview] = Field(default_factory=list)
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""


class ConfirmedRunFromPlanRequest(BaseModel):
    """Request to create a real Run from the confirmed plan preview."""

    idea: str
    confirm: bool = False
    mode: Optional[ProjectIntakeMode] = None
    project_id: Optional[str] = None
    existing_project_attached: Optional[bool] = None
    known_stack: Optional[list[str]] = None
    known_constraints: Optional[list[str]] = None
    user_goal: Optional[str] = None


class ConfirmedRunCreatedStep(BaseModel):
    """Minimal info about a run step that was persisted."""

    step_id: str
    title: str
    agent_id: str
    status: str


class ConfirmedRunFromPlanResponse(BaseModel):
    """Response after creating a run from a confirmed plan."""

    run_id: str
    run_status: str
    steps_created: int
    steps: list[ConfirmedRunCreatedStep] = Field(default_factory=list)
    summary: str
    warnings: list[str] = Field(default_factory=list)


class RunStepRequirementContext(BaseModel):
    requirement_ids: list[str] = Field(default_factory=list)
    coverage_status: str = ""
    drift_risk: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)
    source_of_truth_summary: str = ""
    parse_warnings: list[str] = Field(default_factory=list)


class StepSourceOfTruthGuardDecision(str, enum.Enum):
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


class StepSourceOfTruthGuardRequest(BaseModel):
    proposed_action: str
    file_path: Optional[str] = None
    patch_summary: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None


class StepSourceOfTruthGuardResult(BaseModel):
    decision: StepSourceOfTruthGuardDecision
    drift_risk: str
    matched_requirement_ids: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)
    forbidden_change_hits: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    recommended_next_step: str = ""


class StepSourceOfTruthGuardResponse(BaseModel):
    run_id: str
    step_id: str
    has_requirement_context: bool
    parsed_context: RunStepRequirementContext
    guard_result: StepSourceOfTruthGuardResult
    persisted: bool = False
    guard_result_id: Optional[str] = None


# ── Keyword detection helpers ────────────────────────────────────────────────

_LOWER = re.IGNORECASE

_EXISTING_PROJECT_PATTERNS = [
    re.compile(
        r"(у\s+меня\s+уже\s+есть|уже\s+есть|полуготов|существующ|загрузить\s+папк|"
        r"existing\s+project|existing\s+app|continue\s+an\s+existing|already\s+have|"
        r"continue|продолж|доработ|refactor|мигрир|legacy|перепис)",
        _LOWER,
    ),
]

_TARGET_TYPE_KEYWORDS: dict[ProjectTargetType, list[re.Pattern[str]]] = {
    ProjectTargetType.WEB_APP: [re.compile(r"(web|сайт|dashboard|spa|react|vue|angular|frontend|landing|portal|crm|erp|cms)", _LOWER)],
    ProjectTargetType.MOBILE_APP: [re.compile(r"(mobile|ios|android|flutter|react.native|мобильн|приложени)", _LOWER)],
    ProjectTargetType.DESKTOP_APP: [re.compile(r"(desktop|electron|tauri|gtk|qt|настольн)", _LOWER)],
    ProjectTargetType.API_SERVICE: [re.compile(r"(api|microservice|rest|graphql|grpc|backend.only|сервис|бэкенд)", _LOWER)],
    ProjectTargetType.CLI_TOOL: [re.compile(r"(cli|command.line|terminal|консол|утилит|скрипт)", _LOWER)],
    ProjectTargetType.AUTOMATION: [re.compile(r"(automat|бот|scraper|pipeline|cron|scheduler|парсер|telegram.bot)", _LOWER)],
}

_MATURITY_KEYWORDS: dict[ProjectMaturityGoal, list[re.Pattern[str]]] = {
    ProjectMaturityGoal.MVP: [re.compile(r"(mvp|minimum.viable|минимальн|быстр|простой.вариант)", _LOWER)],
    ProjectMaturityGoal.FULL_PRODUCT: [re.compile(r"(full|production|продакшн|полноценн|масштаб)", _LOWER)],
    ProjectMaturityGoal.DIPLOMA: [re.compile(r"(диплом|курсов|thesis|universit|учебн)", _LOWER)],
    ProjectMaturityGoal.PROTOTYPE: [re.compile(r"(prototype|прототип|proof.of.concept|poc|демо)", _LOWER)],
    ProjectMaturityGoal.INTERNAL_TOOL: [re.compile(r"(internal|внутренн|для.команды|для.себя|in.house)", _LOWER)],
}

_SIGNAL_KEYWORDS: dict[str, list[re.Pattern[str]]] = {
    "auth": [re.compile(r"(auth|login|регистрац|пользовател|роли|rbac|jwt|oauth|sso)", _LOWER)],
    "payments": [re.compile(r"(pay|billing|оплат|подписк|stripe|платёж|invoice|subscription)", _LOWER)],
    "uploads": [re.compile(r"(upload|file|загруз|файл|image|photo|s3|storage|фото)", _LOWER)],
    "notifications": [re.compile(r"(notif|email|sms|push|уведомлен|рассылк|webhook)", _LOWER)],
    "integrations": [re.compile(r"(integrat|api.extern|third.party|внешн|интеграц|zapier|webhook)", _LOWER)],
    "database": [re.compile(r"(database|postgres|mysql|mongo|sqlite|redis|бд|база.данн|хранени)", _LOWER)],
    "testing": [re.compile(r"(test|pytest|jest|ci.cd|тест|quality|lint)", _LOWER)],
    "deployment": [re.compile(r"(deploy|docker|k8s|kubernetes|vercel|heroku|aws|деплой|хостинг|vps)", _LOWER)],
    "ui": [re.compile(r"(ui|design|figma|tailwind|дизайн|макет|responsive|тема)", _LOWER)],
}

_CLIENT_SPEC_PATTERNS = [
    re.compile(r"(тз|техническ(?:ое|ого)\s+задани|specification|requirements?\s+document|client\s+spec)", _LOWER),
]
_COMMERCIAL_PROPOSAL_PATTERNS = [
    re.compile(r"(кп|коммерческ(?:ое|ого)\s+предложени|commercial\s+proposal|proposal|estimate|quote)", _LOWER),
]


def _text_matches(text: str, patterns: list[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)


def _detect_signals(text: str) -> set[str]:
    return {key for key, pats in _SIGNAL_KEYWORDS.items() if _text_matches(text, pats)}


# ── Mode detection ───────────────────────────────────────────────────────────


def detect_intake_mode(req: ProjectIntakeRequest) -> ProjectIntakeMode:
    if req.mode is not None:
        return req.mode
    if req.existing_project_attached:
        return ProjectIntakeMode.EXISTING_PROJECT
    text = req.idea.lower()
    if any(p.search(text) for p in _EXISTING_PROJECT_PATTERNS):
        return ProjectIntakeMode.EXISTING_PROJECT
    return ProjectIntakeMode.NEW_PROJECT


def detect_target_type(text: str) -> ProjectTargetType:
    for target, patterns in _TARGET_TYPE_KEYWORDS.items():
        if _text_matches(text, patterns):
            return target
    return ProjectTargetType.UNKNOWN


def detect_maturity_goal(text: str) -> ProjectMaturityGoal:
    for goal, patterns in _MATURITY_KEYWORDS.items():
        if _text_matches(text, patterns):
            return goal
    return ProjectMaturityGoal.UNKNOWN


# ── Question bank ────────────────────────────────────────────────────────────


def _new_project_questions(text: str, signals: set[str], known_stack: list[str]) -> list[ProjectIntakeQuestion]:
    """Generate questions for a new project idea."""
    qs: list[ProjectIntakeQuestion] = []

    # Required core questions
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.PRODUCT_GOAL,
        priority=QuestionPriority.REQUIRED,
        question="What is the main goal of this product? What problem does it solve?",
        why_it_matters="Defines scope and priorities for the plan.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.USERS_ROLES,
        priority=QuestionPriority.REQUIRED,
        question="Who are the users? Are there different roles (admin, regular user, manager)?",
        why_it_matters="Drives auth, permissions, and UI structure.",
        suggested_default="Admin + regular user",
        options=["Single user", "Admin + regular user", "Multi-role (3+)", "Public (no auth)"],
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.PLATFORM,
        priority=QuestionPriority.REQUIRED,
        question="What platform should this run on?",
        why_it_matters="Determines tech stack and architecture.",
        suggested_default="Web app",
        options=["Web app", "Mobile app", "Desktop app", "API/backend only", "CLI tool", "Bot/automation"],
    ))

    if not known_stack:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.TECH_STACK,
            priority=QuestionPriority.REQUIRED,
            question="Do you have a preferred tech stack, or should we choose one?",
            why_it_matters="Affects all implementation decisions.",
            suggested_default="React + FastAPI + SQLite (local prototype)",
            options=["React + FastAPI", "Next.js + Node", "Vue + Django", "Let the system choose"],
        ))

    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.CONSTRAINTS,
        priority=QuestionPriority.REQUIRED,
        question="Is this an MVP/prototype or a full production product?",
        why_it_matters="Defines depth of implementation and quality requirements.",
        suggested_default="MVP",
        options=["MVP / prototype", "Full product", "Diploma / academic", "Internal tool"],
    ))

    # Recommended questions based on missing signals
    if "database" not in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.DATA_STORAGE,
            priority=QuestionPriority.RECOMMENDED,
            question="What data needs to be stored? Any preference for database type?",
            why_it_matters="Determines persistence layer and data model.",
            suggested_default="SQLite for prototype, PostgreSQL for production",
        ))

    if "auth" not in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.AUTH_SECURITY,
            priority=QuestionPriority.RECOMMENDED,
            question="Does the app need authentication and authorization?",
            why_it_matters="Affects security architecture and user management.",
            suggested_default="JWT/session auth with admin/user roles",
            options=["No auth needed", "Simple login", "Role-based access", "OAuth/SSO"],
        ))

    if "ui" not in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.UI_DESIGN,
            priority=QuestionPriority.RECOMMENDED,
            question="Any design requirements? Figma mockups, brand colors, responsive?",
            why_it_matters="Guides frontend implementation approach.",
            suggested_default="Clean default theme, responsive, no custom design",
        ))

    if "deployment" not in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.DEPLOYMENT,
            priority=QuestionPriority.RECOMMENDED,
            question="Where should this be deployed?",
            why_it_matters="Affects infrastructure and CI/CD decisions.",
            suggested_default="Local development first",
            options=["Local dev only", "VPS / self-hosted", "Cloud (AWS/GCP/Azure)", "Vercel/Heroku/Railway"],
        ))

    # Optional questions triggered by signal keywords
    if "payments" in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.PAYMENTS_BILLING,
            priority=QuestionPriority.RECOMMENDED,
            question="What payment features are needed? Subscriptions, one-time, invoicing?",
            why_it_matters="Payment integration is complex and affects data model.",
            options=["One-time payments", "Subscriptions", "Invoicing", "Not sure yet"],
        ))

    if "uploads" in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.FILES_UPLOADS,
            priority=QuestionPriority.OPTIONAL,
            question="What types of files will users upload? Size limits?",
            why_it_matters="Affects storage strategy and backend configuration.",
            suggested_default="Images up to 10MB, local storage for prototype",
        ))

    if "notifications" in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.NOTIFICATIONS,
            priority=QuestionPriority.OPTIONAL,
            question="What notification channels are needed?",
            why_it_matters="Adds integration complexity.",
            options=["Email only", "Email + push", "SMS", "In-app only"],
        ))

    if "integrations" in signals:
        qs.append(ProjectIntakeQuestion(
            category=QuestionCategory.INTEGRATIONS,
            priority=QuestionPriority.OPTIONAL,
            question="Which external services or APIs need to be integrated?",
            why_it_matters="Third-party integrations require API keys, error handling, and testing.",
        ))

    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.QUALITY_TESTING,
        priority=QuestionPriority.OPTIONAL,
        question="What level of testing is expected?",
        why_it_matters="Determines test strategy and CI setup.",
        suggested_default="Backend unit tests + frontend typecheck/build",
        options=["Minimal (linting)", "Unit tests", "Unit + integration", "Full CI/CD pipeline"],
    ))

    return qs


def _existing_project_questions(text: str, signals: set[str]) -> list[ProjectIntakeQuestion]:
    """Generate questions for an existing project."""
    qs: list[ProjectIntakeQuestion] = []

    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.EXISTING_PROJECT,
        priority=QuestionPriority.REQUIRED,
        question="Where are the project files located? Provide the path or repository URL.",
        why_it_matters="Needed to scan and understand the current codebase.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.TECH_STACK,
        priority=QuestionPriority.REQUIRED,
        question="What tech stack does the project use?",
        why_it_matters="Determines which agents and tools to assign.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.EXISTING_PROJECT,
        priority=QuestionPriority.REQUIRED,
        question="What already works? What is the current state of the project?",
        why_it_matters="Helps prioritize what to build next vs. what to fix.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.EXISTING_PROJECT,
        priority=QuestionPriority.REQUIRED,
        question="What is broken or incomplete? What needs to be fixed first?",
        why_it_matters="Identifies blockers before new development.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.PRODUCT_GOAL,
        priority=QuestionPriority.REQUIRED,
        question="What is the next goal? What should be built or improved?",
        why_it_matters="Defines scope for the next planning cycle.",
    ))

    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.QUALITY_TESTING,
        priority=QuestionPriority.RECOMMENDED,
        question="Do tests exist? How do you run them (test command)?",
        why_it_matters="Needed for safe changes — run tests before and after modifications.",
        suggested_default="pytest for Python, npm test for JS/TS",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.EXISTING_PROJECT,
        priority=QuestionPriority.RECOMMENDED,
        question="How do you run the project in development mode (dev/build commands)?",
        why_it_matters="Required for verifying changes work correctly.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.DATA_STORAGE,
        priority=QuestionPriority.RECOMMENDED,
        question="What database, environment variables, or local services are required to run the project?",
        why_it_matters="Prevents unsafe assumptions about DB setup, migrations, .env files, and local dependencies.",
        suggested_default="Document required DB/local services and keep secrets out of chat.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.CONSTRAINTS,
        priority=QuestionPriority.RECOMMENDED,
        question="Are there files or areas that should NOT be modified?",
        why_it_matters="Prevents accidental changes to critical or protected code.",
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.EXISTING_PROJECT,
        priority=QuestionPriority.RECOMMENDED,
        question="Is there Git history? Should we respect existing branch structure?",
        why_it_matters="Affects how changes are staged and reviewed.",
        options=["Yes, use Git", "No Git", "Not sure"],
    ))
    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.DEPLOYMENT,
        priority=QuestionPriority.RECOMMENDED,
        question="Is there an existing deployment target or hosting environment?",
        why_it_matters="Deployment context affects environment assumptions and verification scope.",
        suggested_default="Local development first unless deployment is already configured.",
    ))

    qs.append(ProjectIntakeQuestion(
        category=QuestionCategory.AUTH_SECURITY,
        priority=QuestionPriority.OPTIONAL,
        question="Are there .env files, secrets, or credentials that should be ignored?",
        why_it_matters="Prevents accidental exposure of sensitive data.",
        suggested_default="Ignore .env, *.key, *.pem files",
    ))

    return qs


# ── Bounded output ───────────────────────────────────────────────────────────

MAX_REQUIRED = 8
MAX_RECOMMENDED = 7
MAX_OPTIONAL = 5
MAX_TOTAL = 15


def _bound_questions(qs: list[ProjectIntakeQuestion]) -> list[ProjectIntakeQuestion]:
    required = [q for q in qs if q.priority == QuestionPriority.REQUIRED][:MAX_REQUIRED]
    recommended = [q for q in qs if q.priority == QuestionPriority.RECOMMENDED][:MAX_RECOMMENDED]
    optional = [q for q in qs if q.priority == QuestionPriority.OPTIONAL][:MAX_OPTIONAL]
    bounded = required + recommended + optional
    return bounded[:MAX_TOTAL]


# ── Ready-to-plan heuristic ─────────────────────────────────────────────────


def _assess_readiness(
    mode: ProjectIntakeMode,
    target: ProjectTargetType,
    maturity: ProjectMaturityGoal,
    signals: set[str],
    known_stack: list[str],
    idea_words: int,
) -> tuple[bool, str, str]:
    """Return (ready_to_plan, confidence, recommended_next_step)."""

    score = 0
    if target != ProjectTargetType.UNKNOWN:
        score += 1
    if maturity != ProjectMaturityGoal.UNKNOWN:
        score += 1
    if known_stack:
        score += 1
    if "auth" in signals:
        score += 1
    if "database" in signals:
        score += 1
    if idea_words >= 30:
        score += 1

    if mode == ProjectIntakeMode.EXISTING_PROJECT:
        # Existing projects always need answers before planning
        return False, "low", "Answer the questions above to help the system understand your existing project."

    if score >= 5:
        return True, "high", "Enough information to generate an initial plan. You can still refine answers."
    if score >= 3:
        return False, "medium", "Answer the required questions to improve the plan quality."
    return False, "low", "The idea is too vague. Answer at least the required questions before planning."


# ── Main entry point ─────────────────────────────────────────────────────────


def analyze_project_intake(req: ProjectIntakeRequest) -> ProjectIntakeResponse:
    """Analyze a raw project idea and return structured intake questions.

    Pure function — no DB, no LLM, no tools, no side effects.
    """

    text = req.idea.strip()
    idea_words = len(text.split())
    mode = detect_intake_mode(req)
    target = detect_target_type(text)
    maturity = detect_maturity_goal(text)
    signals = _detect_signals(text)
    known_stack = req.known_stack or []

    # Generate questions
    if mode == ProjectIntakeMode.EXISTING_PROJECT:
        raw_questions = _existing_project_questions(text, signals)
    else:
        raw_questions = _new_project_questions(text, signals, known_stack)

    questions = _bound_questions(raw_questions)

    # Build assumptions
    assumptions: list[str] = []
    if target != ProjectTargetType.UNKNOWN:
        assumptions.append(f"Target platform: {target.value.replace('_', ' ')}")
    if maturity != ProjectMaturityGoal.UNKNOWN:
        assumptions.append(f"Maturity goal: {maturity.value.replace('_', ' ')}")
    if known_stack:
        assumptions.append(f"Known stack: {', '.join(known_stack)}")
    if not known_stack and mode == ProjectIntakeMode.NEW_PROJECT:
        assumptions.append("Default stack assumption: React + FastAPI + SQLite for local prototype")
    if "auth" in signals:
        assumptions.append("Auth/login mentioned — will include authentication architecture")
    if "payments" in signals:
        assumptions.append("Payments mentioned — will include billing integration planning")

    # Build missing information
    missing: list[str] = []
    if target == ProjectTargetType.UNKNOWN:
        missing.append("Target platform not specified")
    if maturity == ProjectMaturityGoal.UNKNOWN:
        missing.append("Project maturity/scope not specified (MVP vs full product)")
    if not known_stack and mode == ProjectIntakeMode.NEW_PROJECT:
        missing.append("Tech stack not specified")
    if "auth" not in signals and mode == ProjectIntakeMode.NEW_PROJECT:
        missing.append("Auth requirements not mentioned")
    if "database" not in signals and mode == ProjectIntakeMode.NEW_PROJECT:
        missing.append("Database/storage requirements not mentioned")

    ready, confidence, next_step = _assess_readiness(
        mode, target, maturity, signals, known_stack, idea_words,
    )

    summary_prefix = "Existing project continuation" if mode == ProjectIntakeMode.EXISTING_PROJECT else "New project"
    summary = (
        f"{summary_prefix}. "
        f"Detected: {target.value.replace('_', ' ')} / {maturity.value.replace('_', ' ')}. "
        f"{len(questions)} questions generated ({len([q for q in questions if q.priority == QuestionPriority.REQUIRED])} required)."
    )

    return ProjectIntakeResponse(
        mode=mode,
        detected_target_type=target,
        detected_maturity_goal=maturity,
        summary=summary,
        assumptions=assumptions,
        missing_information=missing,
        questions=questions,
        ready_to_plan=ready,
        recommended_next_step=next_step,
        confidence=confidence,
    )


# ── Project Brief Draft ───────────────────────────────────────────────────────


def _section(
    title: str,
    content: str,
    status: ProjectBriefSectionStatus,
    notes: Optional[str] = None,
) -> ProjectBriefSection:
    return ProjectBriefSection(title=title, content=content, status=status, notes=notes)


def _section_markdown(section: ProjectBriefSection) -> str:
    marker = section.status.value.capitalize()
    notes = f"\n\nNotes: {section.notes}" if section.notes else ""
    return f"## {section.title}\n\nStatus: {marker}\n\n{section.content}{notes}"


def _safe_default_stack(req: ProjectBriefDraftRequest, intake: ProjectIntakeResponse) -> tuple[str, ProjectBriefSectionStatus, str]:
    if req.known_stack:
        return ", ".join(req.known_stack), ProjectBriefSectionStatus.CONFIRMED, "Provided in request."
    if intake.mode == ProjectIntakeMode.NEW_PROJECT:
        return "React + FastAPI + SQLite for a local prototype.", ProjectBriefSectionStatus.ASSUMED, "Default assumption only."
    return "Missing: existing project stack needs to be provided.", ProjectBriefSectionStatus.MISSING, "Required for existing project onboarding."


def draft_project_brief(req: ProjectBriefDraftRequest) -> ProjectBriefDraftResponse:
    """Build a deterministic brief draft from intake analysis.

    Pure function — no DB, no LLM, no tools, no file scanning, no side effects.
    """

    intake = analyze_project_intake(ProjectIntakeRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
    ))
    text = req.idea.strip()
    signals = _detect_signals(text)
    answers = req.answers or {}

    target_label = intake.detected_target_type.value.replace("_", " ")
    maturity_label = intake.detected_maturity_goal.value.replace("_", " ")
    title = "Project Brief Draft"
    readiness = "ready_to_plan" if intake.ready_to_plan else "needs_clarification"

    product_goal = answers.get("product_goal") or req.user_goal or text
    sections: list[ProjectBriefSection] = [
        _section(
            "Product idea",
            product_goal,
            ProjectBriefSectionStatus.CONFIRMED if product_goal else ProjectBriefSectionStatus.MISSING,
            "Generated from the raw idea and optional user_goal.",
        ),
        _section(
            "Target users",
            answers.get("target_users", "Missing: target users and roles are not confirmed yet."),
            ProjectBriefSectionStatus.CONFIRMED if answers.get("target_users") else ProjectBriefSectionStatus.MISSING,
            "Answer the users/roles intake question to confirm this section.",
        ),
        _section(
            "Core functionality",
            f"Build around the stated idea: {text}",
            ProjectBriefSectionStatus.ASSUMED,
            "This is a draft interpretation, not a final feature list.",
        ),
        _section(
            "Data and entities",
            "Database/storage is mentioned; plan a persistence layer and core entities."
            if "database" in signals else "Missing: data model and storage requirements need clarification.",
            ProjectBriefSectionStatus.CONFIRMED if "database" in signals else ProjectBriefSectionStatus.MISSING,
        ),
        _section(
            "Auth and roles",
            "Authentication or roles are mentioned; include auth architecture and access rules."
            if "auth" in signals else "Missing: authentication and authorization requirements need clarification.",
            ProjectBriefSectionStatus.CONFIRMED if "auth" in signals else ProjectBriefSectionStatus.MISSING,
        ),
        _section(
            "UI/UX",
            "UI/design requirements are mentioned; reflect them in frontend planning."
            if "ui" in signals else "Assumed: clean responsive default UI unless a design system is provided.",
            ProjectBriefSectionStatus.CONFIRMED if "ui" in signals else ProjectBriefSectionStatus.ASSUMED,
        ),
    ]

    stack_content, stack_status, stack_notes = _safe_default_stack(req, intake)
    sections.append(_section("Tech stack", stack_content, stack_status, stack_notes))

    sections.extend([
        _section(
            "Deployment",
            "Deployment target is mentioned; include deployment and environment planning."
            if "deployment" in signals else "Assumed: local development first; deployment target is not confirmed.",
            ProjectBriefSectionStatus.CONFIRMED if "deployment" in signals else ProjectBriefSectionStatus.ASSUMED,
        ),
        _section(
            "Quality/testing",
            "Testing or CI is mentioned; include verification commands and test coverage."
            if "testing" in signals else "Assumed: backend unit tests plus frontend typecheck/build as baseline.",
            ProjectBriefSectionStatus.CONFIRMED if "testing" in signals else ProjectBriefSectionStatus.ASSUMED,
        ),
    ])

    if req.known_constraints:
        sections.append(_section(
            "Constraints",
            "; ".join(req.known_constraints),
            ProjectBriefSectionStatus.CONFIRMED,
            "Provided in request.",
        ))

    open_questions = intake.questions
    question_lines = [
        f"- [{q.priority.value}] {q.question}"
        for q in open_questions[:MAX_TOTAL]
    ]
    assumption_lines = [f"- {item}" for item in intake.assumptions] or ["- None confirmed yet."]
    missing_lines = [f"- {item}" for item in intake.missing_information] or ["- No major gaps detected."]

    brief_parts = [
        "# Project Brief Draft",
        "",
        f"Mode: {intake.mode.value}",
        f"Target: {target_label}",
        f"Maturity: {maturity_label}",
        f"Readiness: {readiness}",
        "",
        *[_section_markdown(section) for section in sections],
        "## Open questions",
        "",
        "\n".join(question_lines) if question_lines else "None.",
        "",
        "## Assumptions",
        "",
        "\n".join(assumption_lines),
        "",
        "## Missing information",
        "",
        "\n".join(missing_lines),
    ]

    return ProjectBriefDraftResponse(
        title=title,
        mode=intake.mode,
        target_type=intake.detected_target_type,
        maturity_goal=intake.detected_maturity_goal,
        readiness=readiness,
        summary=f"{intake.summary} Brief draft has {len(sections)} sections.",
        brief_markdown="\n".join(brief_parts),
        sections=sections,
        assumptions=intake.assumptions,
        missing_information=intake.missing_information,
        open_questions=open_questions,
        recommended_next_step=intake.recommended_next_step,
        ready_to_plan=intake.ready_to_plan,
    )


# ── Development Plan Preview ─────────────────────────────────────────────────


KNOWN_AGENT_IDS = {
    "orchestrator",
    "product-manager",
    "business-analyst",
    "architect",
    "api-designer",
    "frontend-developer",
    "backend-developer",
    "fullstack-developer",
    "react-specialist",
    "typescript-pro",
    "fastapi-developer",
    "node-specialist",
    "sql-pro",
    "postgres-pro",
    "mobile-developer",
    "qa-expert",
    "test-automator",
    "code-reviewer",
    "security-auditor",
    "devops-engineer",
    "technical-writer",
    "error-detective",
    "git-workflow-manager",
}


def _phase(
    *,
    id: str,
    title: str,
    description: str,
    priority: QuestionPriority,
    status: DevelopmentPlanPhaseStatus,
    suggested_agent_id: Optional[str] = None,
    depends_on: Optional[list[str]] = None,
    deliverables: Optional[list[str]] = None,
    risks: Optional[list[str]] = None,
) -> DevelopmentPlanPhase:
    agent_id = suggested_agent_id if suggested_agent_id in KNOWN_AGENT_IDS else suggested_agent_id
    return DevelopmentPlanPhase(
        id=id,
        title=title,
        description=description,
        priority=priority,
        status=status,
        suggested_agent_id=agent_id,
        depends_on=depends_on or [],
        deliverables=deliverables or [],
        risks=risks or [],
    )


def _dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _agent_recommendations(phases: list[DevelopmentPlanPhase]) -> list[str]:
    base = ["orchestrator", "product-manager", "architect", "qa-expert", "technical-writer"]
    phase_agents = [phase.suggested_agent_id or "" for phase in phases]
    return _dedupe([*base, *phase_agents])


def _new_project_plan_phases(
    brief: ProjectBriefDraftResponse,
    signals: set[str],
    required_inputs: list[str],
) -> list[DevelopmentPlanPhase]:
    requirements_status = (
        DevelopmentPlanPhaseStatus.NEEDS_INPUT
        if required_inputs
        else DevelopmentPlanPhaseStatus.READY
    )
    architecture_status = (
        DevelopmentPlanPhaseStatus.READY
        if brief.target_type != ProjectTargetType.UNKNOWN
        else DevelopmentPlanPhaseStatus.NEEDS_INPUT
    )

    phases = [
        _phase(
            id="requirements-clarification",
            title="Requirements clarification",
            description="Confirm product goal, target users, platform, constraints, and MVP boundary before execution.",
            priority=QuestionPriority.REQUIRED,
            status=requirements_status,
            suggested_agent_id="product-manager",
            deliverables=["Confirmed scope", "Open questions answered", "Acceptance criteria"],
            risks=["Planning quality is limited until required inputs are answered"] if required_inputs else [],
        ),
        _phase(
            id="architecture-design",
            title="Architecture/design",
            description="Define system boundaries, frontend/backend split, data flow, and integration points.",
            priority=QuestionPriority.REQUIRED,
            status=architecture_status,
            suggested_agent_id="architect",
            depends_on=["requirements-clarification"],
            deliverables=["Architecture outline", "Module boundaries", "Implementation order"],
        ),
        _phase(
            id="data-model",
            title="Data model",
            description="Draft entities, relationships, persistence choices, and migration/testing approach.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY if "database" in signals else DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="postgres-pro" if "database" in signals else "backend-developer",
            depends_on=["architecture-design"],
            deliverables=["Entity list", "Storage model", "Validation rules"],
            risks=[] if "database" in signals else ["Storage requirements are not confirmed"],
        ),
        _phase(
            id="backend-api",
            title="Backend/API",
            description="Plan backend routes, validation, services, and API contracts.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="backend-developer",
            depends_on=["architecture-design", "data-model"],
            deliverables=["API contract", "Backend task list", "Error handling plan"],
        ),
        _phase(
            id="frontend-ui",
            title="Frontend/UI",
            description="Plan screens, client state, API integration, loading/error states, and responsive behavior.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="frontend-developer",
            depends_on=["architecture-design", "backend-api"],
            deliverables=["Screen list", "Component plan", "Client API usage"],
        ),
    ]

    if "auth" in signals:
        phases.append(_phase(
            id="auth-rbac",
            title="Auth/RBAC",
            description="Plan authentication, roles, permissions, and protected flows.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="security-auditor",
            depends_on=["backend-api", "frontend-ui"],
            deliverables=["Auth flow", "Role matrix", "Security checklist"],
            risks=["Auth and RBAC need focused security review"],
        ))

    if "uploads" in signals:
        phases.append(_phase(
            id="files-uploads",
            title="Files/uploads",
            description="Plan upload limits, storage, validation, and file safety boundaries.",
            priority=QuestionPriority.RECOMMENDED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="backend-developer",
            depends_on=["backend-api"],
            deliverables=["Upload contract", "Storage plan", "Validation rules"],
            risks=["File upload paths and content types require strict validation"],
        ))

    if "payments" in signals:
        phases.append(_phase(
            id="payments",
            title="Payments",
            description="Plan payment flows, billing state, webhook handling, and reconciliation.",
            priority=QuestionPriority.RECOMMENDED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="backend-developer",
            depends_on=["backend-api", "data-model"],
            deliverables=["Payment flow", "Billing data model", "Webhook safety checklist"],
            risks=["Payment integrations require explicit provider choice and careful testing"],
        ))

    if "notifications" in signals:
        phases.append(_phase(
            id="notifications",
            title="Notifications",
            description="Plan notification channels, event triggers, templates, and delivery failure handling.",
            priority=QuestionPriority.OPTIONAL,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="backend-developer",
            depends_on=["backend-api"],
            deliverables=["Notification events", "Channel plan", "Retry/failure behavior"],
        ))

    phases.extend([
        _phase(
            id="testing-qa",
            title="Testing/QA",
            description="Plan backend tests, frontend type/build checks, smoke tests, and regression coverage.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="qa-expert",
            depends_on=["backend-api", "frontend-ui"],
            deliverables=["Test strategy", "Verification commands", "Regression checklist"],
        ),
        _phase(
            id="deployment",
            title="Deployment",
            description="Plan local run instructions first, then deployment target and environment validation if needed.",
            priority=QuestionPriority.RECOMMENDED,
            status=DevelopmentPlanPhaseStatus.READY if "deployment" in signals else DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="devops-engineer",
            depends_on=["testing-qa"],
            deliverables=["Run/build commands", "Environment checklist", "Deployment notes"],
            risks=[] if "deployment" in signals else ["Deployment target is not confirmed"],
        ),
        _phase(
            id="documentation-final-report",
            title="Documentation/final report",
            description="Prepare setup notes, implementation summary, test results, and remaining gaps.",
            priority=QuestionPriority.RECOMMENDED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="technical-writer",
            depends_on=["testing-qa"],
            deliverables=["README/update notes", "Final report", "Known gaps"],
        ),
    ])

    return phases


def _existing_project_plan_phases(
    has_project_reference: bool,
    has_stack: bool,
    has_goal: bool,
) -> list[DevelopmentPlanPhase]:
    inventory_status = DevelopmentPlanPhaseStatus.READY if has_project_reference else DevelopmentPlanPhaseStatus.BLOCKED
    stack_status = DevelopmentPlanPhaseStatus.READY if has_stack else DevelopmentPlanPhaseStatus.NEEDS_INPUT
    goal_status = DevelopmentPlanPhaseStatus.READY if has_goal else DevelopmentPlanPhaseStatus.NEEDS_INPUT

    return [
        _phase(
            id="project-inventory",
            title="Project inventory",
            description="Identify project location, repository state, key folders, and safe working boundaries.",
            priority=QuestionPriority.REQUIRED,
            status=inventory_status,
            suggested_agent_id="orchestrator",
            deliverables=["Project path confirmed", "Workspace boundary", "Initial inventory"],
            risks=[] if has_project_reference else ["Existing project path or attachment is missing"],
        ),
        _phase(
            id="stack-profile-detection",
            title="Stack/profile detection",
            description="Confirm stack, package manager, test/build commands, and project profile metadata.",
            priority=QuestionPriority.REQUIRED,
            status=stack_status,
            suggested_agent_id="architect",
            depends_on=["project-inventory"],
            deliverables=["Stack profile", "Build command", "Test command"],
            risks=[] if has_stack else ["Known stack is missing"],
        ),
        _phase(
            id="safe-command-validation",
            title="Safe command validation",
            description="Validate dev/build/test commands manually before using them in a guided workflow.",
            priority=QuestionPriority.REQUIRED,
            status=stack_status,
            suggested_agent_id="qa-expert",
            depends_on=["stack-profile-detection"],
            deliverables=["Validated command list", "Baseline test status"],
        ),
        _phase(
            id="existing-code-risk-audit",
            title="Existing code risk audit",
            description="Review current architecture, risky areas, protected files, and change constraints.",
            priority=QuestionPriority.RECOMMENDED,
            status=stack_status,
            suggested_agent_id="code-reviewer",
            depends_on=["stack-profile-detection"],
            deliverables=["Risk notes", "Protected areas", "Review checklist"],
        ),
        _phase(
            id="current-goal-clarification",
            title="Current issue/goal clarification",
            description="Confirm what should be fixed or built next, plus acceptance criteria.",
            priority=QuestionPriority.REQUIRED,
            status=goal_status,
            suggested_agent_id="product-manager",
            depends_on=["project-inventory"],
            deliverables=["Goal statement", "Acceptance criteria", "Out-of-scope list"],
            risks=[] if has_goal else ["Current goal is not specific enough"],
        ),
        _phase(
            id="context-gathering",
            title="Context gathering",
            description="Use safe read-only context gathering before proposing changes.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.READY if has_project_reference and has_goal else DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="orchestrator",
            depends_on=["current-goal-clarification", "stack-profile-detection"],
            deliverables=["Relevant files", "Context bundle", "Open questions"],
        ),
        _phase(
            id="patch-proposal-review",
            title="Patch proposal/review",
            description="Prepare a patch proposal and static review without applying it automatically.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="code-reviewer",
            depends_on=["context-gathering"],
            deliverables=["Patch proposal", "Review findings"],
            risks=["Must remain manual approval gated"],
        ),
        _phase(
            id="manual-apply",
            title="Manual apply",
            description="Apply patch only after explicit manual confirmation in the controlled workflow.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="git-workflow-manager",
            depends_on=["patch-proposal-review"],
            deliverables=["Applied patch after approval", "Git diff summary"],
            risks=["No automatic apply in this preview flow"],
        ),
        _phase(
            id="test-fix-loop",
            title="Test/fix loop",
            description="Run configured checks manually, analyze failures, and prepare follow-up fix proposals.",
            priority=QuestionPriority.REQUIRED,
            status=DevelopmentPlanPhaseStatus.NEEDS_INPUT,
            suggested_agent_id="qa-expert",
            depends_on=["manual-apply"],
            deliverables=["Test results", "Failure analysis", "Fix proposal if needed"],
        ),
        _phase(
            id="final-verification-report",
            title="Final verification/report",
            description="Document changes, checks, residual risks, and next steps.",
            priority=QuestionPriority.RECOMMENDED,
            status=DevelopmentPlanPhaseStatus.READY,
            suggested_agent_id="technical-writer",
            depends_on=["test-fix-loop"],
            deliverables=["Final report", "Remaining gaps", "Recommended next slice"],
        ),
    ]


def draft_development_plan(req: DevelopmentPlanPreviewRequest) -> DevelopmentPlanPreviewResponse:
    """Build a deterministic development plan preview from intake and brief data.

    Pure function - no DB, no LLM, no tools, no agent selector, no file scanning.
    """

    brief = draft_project_brief(ProjectBriefDraftRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        answers=req.answers,
    ))
    text = req.idea.strip()
    signals = _detect_signals(text)
    answers = req.answers or {}

    required_inputs = list(brief.missing_information)
    if brief.mode == ProjectIntakeMode.NEW_PROJECT and not answers.get("target_users"):
        required_inputs.append("Target users/roles not confirmed")
    if brief.mode == ProjectIntakeMode.NEW_PROJECT and len(text.split()) < 5:
        required_inputs.append("Core functionality is too vague")

    has_project_reference = bool(req.existing_project_attached)
    has_stack = bool(req.known_stack)
    has_goal = bool(req.user_goal or len(text.split()) >= 8)
    if brief.mode == ProjectIntakeMode.EXISTING_PROJECT:
        if not has_project_reference:
            required_inputs.append("Existing project path or attached project is required")
        if not has_stack:
            required_inputs.append("Existing project stack is required")
        if not has_goal:
            required_inputs.append("Current goal or issue is required")

    required_inputs = _dedupe(required_inputs)

    if brief.mode == ProjectIntakeMode.EXISTING_PROJECT:
        phases = _existing_project_plan_phases(has_project_reference, has_stack, has_goal)
    else:
        phases = _new_project_plan_phases(brief, signals, required_inputs)

    risks = _dedupe([
        risk
        for phase in phases
        for risk in phase.risks
    ])
    blocked_phases = [phase for phase in phases if phase.status == DevelopmentPlanPhaseStatus.BLOCKED]
    ready_to_start = bool(
        brief.ready_to_plan
        and not required_inputs
        and not blocked_phases
    )
    source_readiness = DevelopmentPlanSourceReadiness(
        intake_ready_to_plan=brief.ready_to_plan,
        brief_ready_to_plan=brief.ready_to_plan,
    )
    summary = (
        f"{brief.mode.value.replace('_', ' ')} plan preview with {len(phases)} phase(s). "
        f"Ready to start: {'yes' if ready_to_start else 'no'}."
    )
    recommended_next_step = (
        "Ready for a supervised planning run preview. This endpoint still does not create a run."
        if ready_to_start
        else "Answer required inputs before converting this preview into an executable plan."
    )

    return DevelopmentPlanPreviewResponse(
        title="Development Plan Preview",
        mode=brief.mode,
        target_type=brief.target_type,
        maturity_goal=brief.maturity_goal,
        ready_to_start=ready_to_start,
        summary=summary,
        phases=phases,
        required_inputs=required_inputs,
        assumptions=brief.assumptions,
        risks=risks,
        recommended_agent_ids=_agent_recommendations(phases),
        recommended_next_step=recommended_next_step,
        source_readiness=source_readiness,
    )


# ── Source of Truth Preview ──────────────────────────────────────────────────


def _detect_source_type(req: SourceOfTruthPreviewRequest, intake: ProjectIntakeResponse) -> ProjectInputSourceType:
    text = req.idea.strip()
    if intake.mode == ProjectIntakeMode.EXISTING_PROJECT:
        if _text_matches(text, _CLIENT_SPEC_PATTERNS) or _text_matches(text, _COMMERCIAL_PROPOSAL_PATTERNS):
            return ProjectInputSourceType.MIXED
        return ProjectInputSourceType.EXISTING_PROJECT
    if _text_matches(text, _COMMERCIAL_PROPOSAL_PATTERNS):
        return ProjectInputSourceType.COMMERCIAL_PROPOSAL
    if _text_matches(text, _CLIENT_SPEC_PATTERNS):
        return ProjectInputSourceType.CLIENT_SPEC
    return ProjectInputSourceType.NEW_IDEA if text else ProjectInputSourceType.UNKNOWN


def _split_user_supplied_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [
        part.strip(" .;")
        for part in re.split(r"[,;\n]+", value)
        if part.strip(" .;")
    ]


def _infer_target_users(req: SourceOfTruthPreviewRequest) -> list[str]:
    answers = req.answers or {}
    users = _split_user_supplied_list(answers.get("target_users"))
    if users:
        return users

    text = req.idea.strip()
    match = re.search(r"\bfor\s+([A-Za-z0-9 _/-]{3,80})(?:\s+with|\s+to|\s+that|[.;]|$)", text, _LOWER)
    if match:
        return [match.group(1).strip()]
    match = re.search(r"\bдля\s+([А-Яа-яA-Za-z0-9 _/-]{3,80})(?:\s+с|\s+чтобы|[.;]|$)", text, _LOWER)
    if match:
        return [match.group(1).strip()]
    return []


def _infer_user_roles(req: SourceOfTruthPreviewRequest, signals: set[str]) -> list[str]:
    answers = req.answers or {}
    roles = _split_user_supplied_list(answers.get("user_roles"))
    if roles:
        return roles
    text = req.idea.lower()
    inferred: list[str] = []
    if "admin" in text or "админ" in text:
        inferred.append("admin")
    if "manager" in text or "менедж" in text:
        inferred.append("manager")
    if "auth" in signals or "user" in text or "пользователь" in text:
        inferred.append("user")
    return _dedupe(inferred)


def _requirement_priority(priority: QuestionPriority) -> RequirementPriority:
    if priority == QuestionPriority.REQUIRED:
        return RequirementPriority.MUST
    if priority == QuestionPriority.RECOMMENDED:
        return RequirementPriority.SHOULD
    if priority == QuestionPriority.OPTIONAL:
        return RequirementPriority.COULD
    return RequirementPriority.UNKNOWN


def _requirement_status(phase: DevelopmentPlanPhase) -> RequirementStatus:
    if phase.status == DevelopmentPlanPhaseStatus.READY:
        return RequirementStatus.PROPOSED
    if phase.status == DevelopmentPlanPhaseStatus.BLOCKED:
        return RequirementStatus.MISSING
    return RequirementStatus.NEEDS_VALIDATION


def _build_source_requirements(
    phases: list[DevelopmentPlanPhase],
) -> tuple[list[ProjectRequirementContract], list[ProjectAcceptanceCriterion], dict[str, list[str]]]:
    requirements: list[ProjectRequirementContract] = []
    acceptance_criteria: list[ProjectAcceptanceCriterion] = []
    plan_links: dict[str, list[str]] = {}

    for index, phase in enumerate(phases, start=1):
        requirement_id = f"REQ-{index}"
        acceptance_id = f"AC-{index}"
        requirements.append(ProjectRequirementContract(
            id=requirement_id,
            title=phase.title,
            description=phase.description,
            priority=_requirement_priority(phase.priority),
            status=_requirement_status(phase),
            source_refs=[phase.id],
            acceptance_criteria_ids=[acceptance_id],
            tags=[phase.id],
        ))
        verification_hint = "; ".join(phase.deliverables[:3]) if phase.deliverables else "Review phase deliverables."
        acceptance_criteria.append(ProjectAcceptanceCriterion(
            id=acceptance_id,
            requirement_id=requirement_id,
            description=f"{phase.title} has reviewed deliverables and a verification path.",
            status=AcceptanceStatus.NOT_CHECKED,
            verification_hint=verification_hint,
        ))
        plan_links[phase.id] = [requirement_id]

    return requirements, acceptance_criteria, plan_links


def _source_constraints(
    req: SourceOfTruthPreviewRequest,
    source_type: ProjectInputSourceType,
) -> tuple[list[ProjectConstraintContract], list[str]]:
    constraints: list[ProjectConstraintContract] = []
    forbidden_changes: list[str] = []

    for index, item in enumerate(req.known_constraints or [], start=1):
        constraints.append(ProjectConstraintContract(
            id=f"CON-{index}",
            title=item,
            description=item,
            reason="Provided as a known constraint in the intake request.",
        ))

    if source_type == ProjectInputSourceType.EXISTING_PROJECT:
        base_index = len(constraints)
        existing_constraints = [
            (
                "Preserve existing stack unless user approves change",
                "Major stack changes require explicit confirmation.",
                [],
                ["rewrite_stack"],
            ),
            (
                "Do not touch secrets or environment files",
                "Secrets and .env files must stay out of generated changes and previews.",
                [".env", "backend/.env", "frontend/.env"],
                ["read_secret", "write_secret"],
            ),
            (
                "Do not rewrite architecture without explicit approval",
                "Existing projects should receive incremental patches by default.",
                [],
                ["architecture_rewrite"],
            ),
            (
                "Prefer incremental reviewed patches",
                "Patch proposal/review should precede manual apply.",
                [],
                ["auto_apply"],
            ),
            (
                "Run safe validation before and after changes",
                "Build/test commands must be confirmed before future execution.",
                [],
                ["unvalidated_command"],
            ),
        ]
        for offset, (title, description, paths, actions) in enumerate(existing_constraints, start=1):
            constraints.append(ProjectConstraintContract(
                id=f"CON-{base_index + offset}",
                title=title,
                description=description,
                forbidden_paths=paths,
                forbidden_actions=actions,
                reason="Existing project safety boundary.",
            ))
            forbidden_changes.extend(paths)

    return constraints, _dedupe(forbidden_changes)


def _anti_drift_rules(source_type: ProjectInputSourceType) -> list[ProjectAntiDriftRule]:
    rules = [
        ProjectAntiDriftRule(
            id="ADR-1",
            title="Preserve stated product goal",
            description="Do not change the product goal without explicit user confirmation.",
        ),
        ProjectAntiDriftRule(
            id="ADR-2",
            title="No unrelated features without confirmation",
            description="New features must trace back to requirements or confirmed user intent.",
        ),
        ProjectAntiDriftRule(
            id="ADR-3",
            title="Do not change target users or roles without confirmation",
            description="Role and user model changes require a requirement link and user approval.",
        ),
        ProjectAntiDriftRule(
            id="ADR-4",
            title="Every plan step must link to a requirement",
            description="Future execution steps should carry requirement links to reduce drift.",
            require_requirement_link=True,
        ),
    ]
    if source_type == ProjectInputSourceType.EXISTING_PROJECT:
        rules.extend([
            ProjectAntiDriftRule(
                id="ADR-5",
                title="Protect secrets and environment files",
                description="Do not read, write, or include secrets/.env values in previews or patches.",
                forbidden_patterns=[r"(^|/)\.env", r"\.pem$", r"\.key$"],
                require_requirement_link=True,
            ),
            ProjectAntiDriftRule(
                id="ADR-6",
                title="Prefer incremental patches",
                description="Avoid broad rewrites unless the user explicitly approves a migration.",
                forbidden_patterns=[r"rewrite entire", r"full rewrite"],
                require_requirement_link=True,
            ),
        ])
    return rules


def build_source_of_truth_from_intake(req: SourceOfTruthPreviewRequest) -> SourceOfTruthPreviewResponse:
    """Build a deterministic source-of-truth preview from intake, brief, and plan data.

    Pure read-only helper - no DB, no tools, no providers, no file scanning, no side effects.
    """

    intake = analyze_project_intake(ProjectIntakeRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
    ))
    brief = draft_project_brief(ProjectBriefDraftRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        answers=req.answers,
    ))
    plan = draft_development_plan(DevelopmentPlanPreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        answers=req.answers,
        brief_markdown=req.brief_markdown,
    ))

    source_type = _detect_source_type(req, intake)
    signals = _detect_signals(req.idea)
    phases = req.plan_phases or plan.phases
    requirements, acceptance_criteria, plan_links = _build_source_requirements(phases)
    constraints, forbidden_changes = _source_constraints(req, source_type)
    target_users = _infer_target_users(req)
    user_roles = _infer_user_roles(req, signals)
    product_goal = req.user_goal or req.idea.strip()
    source = ProjectSourceOfTruthContract(
        id=f"sot-{uuid.uuid4().hex[:8]}",
        source_type=source_type,
        raw_source_summary=brief.summary,
        project_name=None,
        product_goal=product_goal,
        target_users=target_users,
        user_roles=user_roles,
        core_features=[phase.title for phase in phases],
        requirements=requirements,
        constraints=constraints,
        forbidden_changes=forbidden_changes,
        acceptance_criteria=acceptance_criteria,
        assumptions=_dedupe([*intake.assumptions, *brief.assumptions]),
        open_questions=[q.question for q in intake.questions],
        anti_drift_rules=_anti_drift_rules(source_type),
        definition_of_done=[
            "All must requirements are linked to a reviewed plan step.",
            "Acceptance criteria are checked before final delivery.",
            "Required project checks pass or failures are documented.",
            "Final report lists changes, verification, and remaining gaps.",
        ],
        created_from="project-intake-source-of-truth-preview",
        confidence=intake.confidence,
        readiness="ready_to_plan" if plan.ready_to_start else "needs_clarification",
        source_metadata={
            "mode": intake.mode.value,
            "target_type": intake.detected_target_type.value,
            "maturity_goal": intake.detected_maturity_goal.value,
            "plan_phase_ids": [phase.id for phase in phases],
            "protected_paths": [".env", "backend/.env", "frontend/.env"] if source_type == ProjectInputSourceType.EXISTING_PROJECT else [],
        },
    )

    validation = validate_source_of_truth_contract(source)
    coverage_matrix = build_requirement_coverage_matrix(source, plan_links)
    ready_to_plan = bool(plan.ready_to_start and validation.valid and coverage_matrix.coverage_score >= 1.0)
    recommended_next_step = (
        "Review and confirm this source of truth before creating a run."
        if ready_to_plan
        else "Resolve validation gaps and open questions before treating this as a confirmed source of truth."
    )

    return SourceOfTruthPreviewResponse(
        title="Source of Truth Preview",
        source_of_truth=source,
        validation=validation,
        coverage_matrix=coverage_matrix,
        summary=(
            f"{source_type.value.replace('_', ' ')} source-of-truth preview with "
            f"{len(requirements)} requirement(s), {len(acceptance_criteria)} acceptance criteria, "
            f"and {len(source.anti_drift_rules)} anti-drift rule(s)."
        ),
        recommended_next_step=recommended_next_step,
        ready_to_plan=ready_to_plan,
    )


# ── Requirement Coverage Preview ─────────────────────────────────────────────


_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-я0-9]{3,}", _LOWER)
_STOP_WORDS = {
    "and", "the", "for", "with", "from", "that", "this", "into", "before", "after",
    "plan", "phase", "project", "review", "safe", "data", "user", "users",
    "для", "что", "как", "или", "это", "проект", "план",
}


def _coverage_tokens(text: str) -> set[str]:
    return {
        token.lower()
        for token in _TOKEN_RE.findall(text)
        if token.lower() not in _STOP_WORDS
    }


def _phase_tokens(phase: DevelopmentPlanPhase) -> set[str]:
    return _coverage_tokens(" ".join([
        phase.id,
        phase.title,
        phase.description,
        " ".join(phase.deliverables),
        " ".join(phase.risks),
    ]))


def _requirement_tokens(req: ProjectRequirementContract) -> set[str]:
    return _coverage_tokens(" ".join([
        req.id,
        req.title,
        req.description,
        " ".join(req.tags),
        " ".join(req.source_refs),
    ]))


def _phase_touches_forbidden_boundary(
    phase: DevelopmentPlanPhase,
    source: ProjectSourceOfTruthContract,
) -> bool:
    haystack = " ".join([
        phase.id,
        phase.title,
        phase.description,
        " ".join(phase.deliverables),
        " ".join(phase.risks),
    ]).lower()
    forbidden_terms = [item.lower() for item in source.forbidden_changes]
    for constraint in source.constraints:
        forbidden_terms.extend(path.lower() for path in constraint.forbidden_paths)
        forbidden_terms.extend(action.lower().replace("_", " ") for action in constraint.forbidden_actions)
    return any(term and term in haystack for term in forbidden_terms)


def _linked_phases_for_requirement(
    req: ProjectRequirementContract,
    phases: list[DevelopmentPlanPhase],
) -> list[DevelopmentPlanPhase]:
    linked: list[DevelopmentPlanPhase] = []
    req_tokens = _requirement_tokens(req)
    for phase in phases:
        exact_match = phase.id in req.source_refs or phase.id in req.tags
        overlap = len(req_tokens & _phase_tokens(phase))
        if exact_match or overlap >= 2:
            linked.append(phase)
    return linked


def _coverage_status_for_requirement(
    req: ProjectRequirementContract,
    linked_phases: list[DevelopmentPlanPhase],
) -> RequirementCoveragePreviewStatus:
    if not linked_phases:
        return RequirementCoveragePreviewStatus.MISSING
    if req.priority == RequirementPriority.UNKNOWN or req.status == RequirementStatus.MISSING:
        return RequirementCoveragePreviewStatus.UNCLEAR
    if any(phase.status == DevelopmentPlanPhaseStatus.BLOCKED for phase in linked_phases):
        return RequirementCoveragePreviewStatus.PARTIALLY_COVERED
    if any(phase.status == DevelopmentPlanPhaseStatus.NEEDS_INPUT for phase in linked_phases):
        return RequirementCoveragePreviewStatus.PARTIALLY_COVERED
    return RequirementCoveragePreviewStatus.COVERED


def _risk_for_coverage_status(
    req: ProjectRequirementContract,
    status: RequirementCoveragePreviewStatus,
) -> DriftRiskLevel:
    if status == RequirementCoveragePreviewStatus.MISSING:
        return DriftRiskLevel.HIGH if req.priority == RequirementPriority.MUST else DriftRiskLevel.MEDIUM
    if status == RequirementCoveragePreviewStatus.UNCLEAR:
        return DriftRiskLevel.MEDIUM
    if status == RequirementCoveragePreviewStatus.PARTIALLY_COVERED:
        return DriftRiskLevel.MEDIUM if req.priority == RequirementPriority.MUST else DriftRiskLevel.LOW
    return DriftRiskLevel.LOW


def build_requirement_coverage_from_plan(
    req: RequirementCoveragePreviewRequest,
) -> RequirementCoveragePreviewResponse:
    """Build a deterministic requirement coverage preview from source of truth and plan data.

    Pure read-only helper - no DB, no tools, no providers, no file scanning, no side effects.
    """

    source_preview = build_source_of_truth_from_intake(SourceOfTruthPreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        answers=req.answers,
        brief_markdown=req.brief_markdown,
        plan_summary=req.plan_summary,
        plan_phases=req.plan_phases,
    ))
    plan = req.plan_preview or draft_development_plan(DevelopmentPlanPreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        answers=req.answers,
        brief_markdown=req.brief_markdown,
    ))
    source = req.source_of_truth or source_preview.source_of_truth
    phases = req.plan_phases or plan.phases

    items: list[RequirementCoveragePreviewItem] = []
    linked_phase_ids: set[str] = set()
    drift_risks: list[str] = []

    for requirement in source.requirements:
        linked_phases = _linked_phases_for_requirement(requirement, phases)
        linked_phase_ids.update(phase.id for phase in linked_phases)
        status = _coverage_status_for_requirement(requirement, linked_phases)
        risk = _risk_for_coverage_status(requirement, status)
        if status == RequirementCoveragePreviewStatus.MISSING and requirement.priority == RequirementPriority.MUST:
            drift_risks.append(f"Mandatory requirement {requirement.id} has no linked plan phase.")
        if status == RequirementCoveragePreviewStatus.PARTIALLY_COVERED:
            drift_risks.append(f"Requirement {requirement.id} is only partially covered by plan phases needing input.")
        notes = "Linked by source refs or keyword overlap." if linked_phases else "No matching plan phase found."
        if status == RequirementCoveragePreviewStatus.UNCLEAR:
            notes = "Coverage is unclear because requirement status or priority needs validation."
        items.append(RequirementCoveragePreviewItem(
            requirement_id=requirement.id,
            title=requirement.title,
            priority=requirement.priority,
            coverage_status=status,
            linked_plan_phases=[
                RequirementCoveragePlanPhaseLink(phase_id=phase.id, title=phase.title)
                for phase in linked_phases
            ],
            notes=notes,
            drift_risk=risk,
        ))

    unlinked_items: list[UnlinkedPlanPhasePreviewItem] = []
    for phase in phases:
        if phase.id in linked_phase_ids:
            continue
        touches_forbidden = _phase_touches_forbidden_boundary(phase, source)
        risk = DriftRiskLevel.CRITICAL if touches_forbidden else DriftRiskLevel.HIGH
        if phase.priority != QuestionPriority.REQUIRED and not touches_forbidden:
            risk = DriftRiskLevel.MEDIUM
        reason = "No requirement matched this plan phase."
        if touches_forbidden:
            reason = "Plan phase appears to touch a forbidden/protected boundary."
            drift_risks.append(f"Plan phase {phase.id} may touch forbidden/protected areas.")
        else:
            drift_risks.append(f"Plan phase {phase.id} has no linked requirement.")
        unlinked_items.append(UnlinkedPlanPhasePreviewItem(
            phase_id=phase.id,
            title=phase.title,
            reason=reason,
            risk_level=risk,
            suggested_action="Link this phase to a requirement or confirm it is intentionally out of scope.",
        ))

    covered_count = len([item for item in items if item.coverage_status == RequirementCoveragePreviewStatus.COVERED])
    partial_count = len([item for item in items if item.coverage_status == RequirementCoveragePreviewStatus.PARTIALLY_COVERED])
    missing_count = len([item for item in items if item.coverage_status == RequirementCoveragePreviewStatus.MISSING])
    unclear_count = len([item for item in items if item.coverage_status == RequirementCoveragePreviewStatus.UNCLEAR])
    all_risks = [item.drift_risk for item in items] + [item.risk_level for item in unlinked_items]
    if DriftRiskLevel.CRITICAL in all_risks:
        overall_risk = DriftRiskLevel.CRITICAL
    elif DriftRiskLevel.HIGH in all_risks:
        overall_risk = DriftRiskLevel.HIGH
    elif DriftRiskLevel.MEDIUM in all_risks:
        overall_risk = DriftRiskLevel.MEDIUM
    else:
        overall_risk = DriftRiskLevel.LOW

    summary = RequirementCoveragePreviewSummary(
        requirements_total=len(source.requirements),
        covered_requirements=covered_count,
        partially_covered_requirements=partial_count,
        missing_requirements=missing_count,
        unclear_requirements=unclear_count,
        unlinked_plan_phases=len(unlinked_items),
        drift_risk=overall_risk,
    )
    recommended_next_step = (
        "Coverage looks aligned. Review the matrix before confirming the plan."
        if missing_count == 0 and not unlinked_items and overall_risk == DriftRiskLevel.LOW
        else "Resolve missing requirements and unlinked plan phases before treating the plan as confirmed."
    )

    return RequirementCoveragePreviewResponse(
        title="Requirement Coverage Preview",
        summary=summary,
        items=items,
        unlinked_plan_phases=unlinked_items,
        drift_risks=_dedupe(drift_risks),
        recommended_next_step=recommended_next_step,
    )


# ── Confirmed Plan → Run Step Preview ───────────────────────────────────────

# Agent assignment hints based on phase content keywords.
_AGENT_HINT_KEYWORDS: dict[str, list[re.Pattern[str]]] = {
    "architect": [re.compile(r"(architect|design|structure|schema|data.model)", _LOWER)],
    "backend-developer": [re.compile(r"(backend|api|endpoint|route|database|migration|server)", _LOWER)],
    "frontend-developer": [re.compile(r"(frontend|ui|react|vue|component|page|dashboard|css|tailwind)", _LOWER)],
    "tester": [re.compile(r"(test|qa|quality|coverage|validation|verify)", _LOWER)],
    "devops": [re.compile(r"(deploy|docker|ci.cd|infra|kubernetes|hosting|vps)", _LOWER)],
    "security-reviewer": [re.compile(r"(security|auth|permission|rbac|encrypt|secret)", _LOWER)],
    "reviewer": [re.compile(r"(review|audit|check|inspect)", _LOWER)],
}

# Phase titles hinting at actions that require manual approval.
_MANUAL_APPROVAL_PATTERNS = [
    re.compile(r"(deploy|release|publish|migrate|database.migration|production)", _LOWER),
]

# Phase titles hinting at safe-to-prepare (read-only prep) actions.
_SAFE_PREP_PATTERNS = [
    re.compile(r"(design|architect|plan|schema|research|analysis|context|gather|review|audit)", _LOWER),
]


def _suggest_agent(text: str) -> Optional[str]:
    """Suggest an agent ID from phase text using keyword heuristics."""
    for agent_id, patterns in _AGENT_HINT_KEYWORDS.items():
        if _text_matches(text, patterns):
            return agent_id
    return None


def _needs_manual_approval(text: str) -> bool:
    return _text_matches(text, _MANUAL_APPROVAL_PATTERNS)


def _is_safe_to_prepare(text: str) -> bool:
    return _text_matches(text, _SAFE_PREP_PATTERNS)


def build_confirmed_plan_run_preview(
    req: ConfirmedPlanRunPreviewRequest,
) -> ConfirmedPlanRunPreviewResponse:
    """Map the full intake pipeline output into a run-step preview.

    Calls the existing pure pipeline internally:
      analyze_project_intake → draft_project_brief → draft_development_plan
      → build_source_of_truth_from_intake → build_requirement_coverage_from_plan

    Then maps plan phases into ConfirmedRunStepPreview objects and evaluates
    readiness to create a real run.

    Pure function — no DB, no LLM, no tools, no providers, no side effects.
    """

    base_kwargs = dict(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
    )

    # Run the full pipeline deterministically.
    plan = draft_development_plan(DevelopmentPlanPreviewRequest(**base_kwargs))
    source_preview = build_source_of_truth_from_intake(SourceOfTruthPreviewRequest(**base_kwargs))
    coverage = build_requirement_coverage_from_plan(RequirementCoveragePreviewRequest(**base_kwargs))

    # Build requirement→phase lookup from coverage items.
    phase_to_req_ids: dict[str, list[str]] = {}
    for item in coverage.items:
        for link in item.linked_plan_phases:
            phase_to_req_ids.setdefault(link.phase_id, []).append(item.requirement_id)

    # Phase-level coverage status lookup.
    req_coverage_map: dict[str, RequirementCoveragePreviewStatus] = {
        item.requirement_id: item.coverage_status for item in coverage.items
    }
    req_drift_map: dict[str, DriftRiskLevel] = {
        item.requirement_id: item.drift_risk for item in coverage.items
    }

    # Map plan phases → run step previews.
    steps: list[ConfirmedRunStepPreview] = []
    blocking_issues: list[str] = []
    warnings: list[str] = []

    for phase in plan.phases:
        combined_text = f"{phase.title} {phase.description}"
        linked_req_ids = phase_to_req_ids.get(phase.id, [])

        # Determine step-level coverage from linked requirements.
        if linked_req_ids:
            statuses = [req_coverage_map.get(rid, RequirementCoveragePreviewStatus.UNCLEAR) for rid in linked_req_ids]
            if all(s == RequirementCoveragePreviewStatus.COVERED for s in statuses):
                step_coverage = RequirementCoveragePreviewStatus.COVERED
            elif RequirementCoveragePreviewStatus.MISSING in statuses:
                step_coverage = RequirementCoveragePreviewStatus.MISSING
            elif RequirementCoveragePreviewStatus.PARTIALLY_COVERED in statuses:
                step_coverage = RequirementCoveragePreviewStatus.PARTIALLY_COVERED
            else:
                step_coverage = RequirementCoveragePreviewStatus.UNCLEAR
        else:
            step_coverage = RequirementCoveragePreviewStatus.MISSING

        # Determine step-level drift risk.
        if linked_req_ids:
            risks = [req_drift_map.get(rid, DriftRiskLevel.LOW) for rid in linked_req_ids]
            risk_order = [DriftRiskLevel.CRITICAL, DriftRiskLevel.HIGH, DriftRiskLevel.MEDIUM, DriftRiskLevel.LOW]
            step_drift = next((r for r in risk_order if r in risks), DriftRiskLevel.LOW)
        else:
            step_drift = DriftRiskLevel.MEDIUM

        manual_approval = _needs_manual_approval(combined_text)
        safe_prep = _is_safe_to_prepare(combined_text)
        agent = _suggest_agent(combined_text) or phase.suggested_agent_id

        validation_parts: list[str] = []
        if not linked_req_ids:
            validation_parts.append("No linked requirements — link to SoT before running.")
            warnings.append(f"Step '{phase.title}' has no linked requirements.")
        if step_drift in (DriftRiskLevel.HIGH, DriftRiskLevel.CRITICAL):
            validation_parts.append(f"High drift risk ({step_drift.value}) — review before running.")
            if phase.priority == QuestionPriority.REQUIRED:
                blocking_issues.append(f"Step '{phase.title}' has {step_drift.value} drift risk on a required phase.")
        if manual_approval:
            validation_parts.append("Manual approval required before execution.")
        if safe_prep:
            validation_parts.append("Safe to prepare (read-only context gathering).")

        steps.append(ConfirmedRunStepPreview(
            id=f"rs-{phase.id}",
            title=phase.title,
            description=phase.description,
            suggested_agent_id=agent,
            required_requirement_ids=linked_req_ids,
            coverage_status=step_coverage,
            drift_risk=step_drift,
            depends_on=[f"rs-{dep}" for dep in phase.depends_on],
            expected_deliverables=phase.deliverables,
            validation_notes=" ".join(validation_parts) if validation_parts else "Ready.",
            manual_approval_required=manual_approval,
            safe_to_prepare=safe_prep,
        ))

    # ── Readiness evaluation ──

    # Source of truth readiness: validation must have no critical gaps.
    sot_validation = source_preview.validation
    sot_ready = sot_validation.valid or (
        not sot_validation.errors
        and sot_validation.drift_risk in (DriftRiskLevel.LOW, DriftRiskLevel.MEDIUM)
    )
    if not sot_ready:
        blocking_issues.append("Source of truth has validation gaps (completeness or drift risk too high).")

    # Coverage readiness: no missing mandatory requirements.
    missing_mandatory = coverage.summary.missing_requirements
    has_critical_drift = coverage.summary.drift_risk in (DriftRiskLevel.HIGH, DriftRiskLevel.CRITICAL)
    coverage_ready = missing_mandatory == 0 and not has_critical_drift
    if missing_mandatory > 0:
        blocking_issues.append(f"{missing_mandatory} mandatory requirement(s) have no linked plan phase.")
    if has_critical_drift:
        blocking_issues.append(f"Coverage has {coverage.summary.drift_risk.value} drift risk.")

    # Overall readiness.
    ready_to_create_run = sot_ready and coverage_ready and len(blocking_issues) == 0

    # Summary.
    step_count = len(steps)
    linked_count = len([s for s in steps if s.required_requirement_ids])
    safe_count = len([s for s in steps if s.safe_to_prepare])
    approval_count = len([s for s in steps if s.manual_approval_required])
    summary = (
        f"{step_count} run steps mapped from plan. "
        f"{linked_count} linked to requirements, {safe_count} safe to prepare, "
        f"{approval_count} requiring manual approval. "
        f"{'Ready to create run.' if ready_to_create_run else 'Not ready — resolve blocking issues first.'}"
    )

    recommended_next_step = (
        "Review the step preview and confirm to create a real run."
        if ready_to_create_run
        else "Resolve blocking issues and warnings before creating a run."
    )

    return ConfirmedPlanRunPreviewResponse(
        title="Confirmed Plan → Run Step Preview",
        ready_to_create_run=ready_to_create_run,
        summary=summary,
        source_of_truth_ready=sot_ready,
        coverage_ready=coverage_ready,
        steps=steps,
        blocking_issues=_dedupe(blocking_issues),
        warnings=_dedupe(warnings),
        recommended_next_step=recommended_next_step,
    )


def _format_requirement_ids(requirement_ids: list[str]) -> list[str]:
    if not requirement_ids:
        return ["requirement_ids: []"]
    return ["requirement_ids:", *[f"- {requirement_id}" for requirement_id in requirement_ids]]


def _format_block_list(label: str, items: list[str]) -> list[str]:
    if not items:
        return [f"{label}: []"]
    return [f"{label}:", *[f"- {item}" for item in items]]


def format_confirmed_run_step_requirement_context(
    *,
    step: ConfirmedRunStepPreview,
    source_of_truth: ProjectSourceOfTruthContract,
    coverage: RequirementCoveragePreviewResponse,
) -> str:
    """Format deterministic source-of-truth metadata for persisted RunStep input.

    Pure helper — no DB, no tools, no providers, no side effects.
    """

    requirement_ids = list(step.required_requirement_ids)
    requirements_by_id = {req.id: req for req in source_of_truth.requirements}
    coverage_by_requirement_id = {item.requirement_id: item for item in coverage.items}
    linked_requirements = [
        requirements_by_id[requirement_id]
        for requirement_id in requirement_ids
        if requirement_id in requirements_by_id
    ]
    linked_acceptance_ids = {
        acceptance_id
        for requirement in linked_requirements
        for acceptance_id in requirement.acceptance_criteria_ids
    }
    acceptance_criteria = [
        criterion.description
        for criterion in source_of_truth.acceptance_criteria
        if criterion.requirement_id in requirement_ids or criterion.id in linked_acceptance_ids
    ]
    constraints = [
        constraint.title
        for constraint in source_of_truth.constraints
    ]
    validation_notes: list[str] = []
    if step.validation_notes:
        validation_notes.append(step.validation_notes)
    if not requirement_ids:
        validation_notes.append("No requirement link found for this step.")
    for requirement_id in requirement_ids:
        coverage_item = coverage_by_requirement_id.get(requirement_id)
        if coverage_item and coverage_item.notes:
            validation_notes.append(f"{requirement_id}: {coverage_item.notes}")

    coverage_status = step.coverage_status.value if requirement_ids else "unlinked"
    lines: list[str] = [
        "AI_WORKBENCH_REQUIREMENT_CONTEXT:",
        *_format_requirement_ids(requirement_ids),
        f"coverage_status: {coverage_status}",
        f"drift_risk: {step.drift_risk.value}",
        *_format_block_list("acceptance_criteria", acceptance_criteria),
        *_format_block_list("constraints", constraints),
        *_format_block_list("forbidden_changes", source_of_truth.forbidden_changes),
        *_format_block_list("validation_notes", _dedupe(validation_notes)),
        f"source_of_truth_summary: {summarize_source_of_truth(source_of_truth)}",
        "END_AI_WORKBENCH_REQUIREMENT_CONTEXT",
    ]
    return "\n".join(lines)


_REQUIREMENT_CONTEXT_START = "AI_WORKBENCH_REQUIREMENT_CONTEXT:"
_REQUIREMENT_CONTEXT_END = "END_AI_WORKBENCH_REQUIREMENT_CONTEXT"
_CONTEXT_LIST_FIELDS = {
    "requirement_ids",
    "acceptance_criteria",
    "constraints",
    "forbidden_changes",
    "validation_notes",
}
_CONTEXT_SCALAR_FIELDS = {
    "coverage_status",
    "drift_risk",
    "source_of_truth_summary",
}
_READ_ONLY_ACTION_RE = re.compile(r"(read|review|check|analy[sz]e|inspect|validate|audit|preview|summari[sz]e|verify)", _LOWER)
_FORBIDDEN_SEVERITY_RE = re.compile(r"(\.env|secret|credential|token|password|private.key|\.pem|database\.py)", _LOWER)
_DANGEROUS_CHANGE_RE = re.compile(r"(delete|remove|rewrite|overwrite|touch|modify|change|edit|write|apply)", _LOWER)


def _parse_list_value(value: str) -> list[str]:
    cleaned = value.strip()
    if not cleaned or cleaned == "[]":
        return []
    if cleaned.startswith("[") and cleaned.endswith("]"):
        inner = cleaned[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("'\"") for part in inner.split(",") if part.strip()]
    return [cleaned]


def parse_run_step_requirement_context(step_input: str) -> RunStepRequirementContext:
    """Parse AI_WORKBENCH_REQUIREMENT_CONTEXT from RunStep.input.

    Tolerates missing sections, empty lists, and extra text before/after the block.
    Pure helper - no DB, no tools, no providers, no side effects.
    """

    if _REQUIREMENT_CONTEXT_START not in step_input or _REQUIREMENT_CONTEXT_END not in step_input:
        return RunStepRequirementContext(
            parse_warnings=["AI_WORKBENCH_REQUIREMENT_CONTEXT block not found"],
        )

    after_start = step_input.split(_REQUIREMENT_CONTEXT_START, 1)[1]
    block = after_start.split(_REQUIREMENT_CONTEXT_END, 1)[0]
    data: dict[str, list[str] | str] = {
        "requirement_ids": [],
        "coverage_status": "",
        "drift_risk": "",
        "acceptance_criteria": [],
        "constraints": [],
        "forbidden_changes": [],
        "validation_notes": [],
        "source_of_truth_summary": "",
    }
    warnings: list[str] = []
    current_list_field: Optional[str] = None

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("- "):
            if current_list_field:
                current = data[current_list_field]
                if isinstance(current, list):
                    current.append(line[2:].strip())
            else:
                warnings.append(f"Ignored list item outside section: {line}")
            continue
        if ":" not in line:
            warnings.append(f"Ignored malformed line: {line}")
            current_list_field = None
            continue

        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key in _CONTEXT_LIST_FIELDS:
            parsed = _parse_list_value(value)
            data[key] = parsed
            current_list_field = key if value == "" else None
        elif key in _CONTEXT_SCALAR_FIELDS:
            data[key] = value
            current_list_field = None
        else:
            warnings.append(f"Unknown requirement context field: {key}")
            current_list_field = None

    return RunStepRequirementContext(
        requirement_ids=list(data["requirement_ids"]) if isinstance(data["requirement_ids"], list) else [],
        coverage_status=str(data["coverage_status"]),
        drift_risk=str(data["drift_risk"]),
        acceptance_criteria=list(data["acceptance_criteria"]) if isinstance(data["acceptance_criteria"], list) else [],
        constraints=list(data["constraints"]) if isinstance(data["constraints"], list) else [],
        forbidden_changes=list(data["forbidden_changes"]) if isinstance(data["forbidden_changes"], list) else [],
        validation_notes=list(data["validation_notes"]) if isinstance(data["validation_notes"], list) else [],
        source_of_truth_summary=str(data["source_of_truth_summary"]),
        parse_warnings=warnings,
    )


def _risk_rank(risk: str) -> int:
    return {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(risk.lower(), 2)


def _risk_from_rank(rank: int) -> str:
    if rank >= 4:
        return "critical"
    if rank == 3:
        return "high"
    if rank == 2:
        return "medium"
    return "low"


def _meaningful_overlap(left: str, right: str) -> set[str]:
    return _coverage_tokens(left) & _coverage_tokens(right)


def _contains_read_only_action(text: str) -> bool:
    return bool(_READ_ONLY_ACTION_RE.search(text))


def _contains_dangerous_change(text: str) -> bool:
    return bool(_DANGEROUS_CHANGE_RE.search(text))


def evaluate_step_source_of_truth_guard(
    *,
    context: RunStepRequirementContext,
    proposed_action: str,
    file_path: Optional[str] = None,
    patch_summary: Optional[str] = None,
    old_text: Optional[str] = None,
    new_text: Optional[str] = None,
) -> StepSourceOfTruthGuardResult:
    """Evaluate a proposed step action against parsed source-of-truth context.

    Pure deterministic guard only - never applies patches or executes anything.
    """

    combined_text = " ".join(
        item for item in [proposed_action, file_path or "", patch_summary or "", old_text or "", new_text or ""] if item
    )
    combined_lower = combined_text.lower()
    warnings: list[str] = []
    reasons: list[str] = []
    violated_constraints: list[str] = []
    forbidden_hits: list[str] = []
    matched_requirement_ids: list[str] = []
    risk_rank = _risk_rank(context.drift_risk or "medium")
    decision = StepSourceOfTruthGuardDecision.ALLOWED
    read_only = _contains_read_only_action(combined_text)

    if context.parse_warnings:
        warnings.extend(context.parse_warnings)
        reasons.append("Requirement context is missing or incomplete.")
        risk_rank = max(risk_rank, 3)
        decision = StepSourceOfTruthGuardDecision.WARNING

    if not context.requirement_ids:
        warnings.append("Step has no linked requirement ids.")
        reasons.append("No requirement link found for this step.")
        risk_rank = max(risk_rank, 3)
        decision = StepSourceOfTruthGuardDecision.WARNING
    else:
        for requirement_id in context.requirement_ids:
            if requirement_id.lower() in combined_lower:
                matched_requirement_ids.append(requirement_id)

    for forbidden in context.forbidden_changes:
        forbidden_text = forbidden.strip()
        if forbidden_text and forbidden_text.lower() in combined_lower:
            forbidden_hits.append(forbidden_text)
    if forbidden_hits:
        reasons.append("Proposed action mentions forbidden/protected change target.")
        risk_rank = max(risk_rank, 4 if any(_FORBIDDEN_SEVERITY_RE.search(hit) for hit in forbidden_hits) else 3)
        decision = StepSourceOfTruthGuardDecision.BLOCKED

    for constraint in context.constraints:
        overlap = _meaningful_overlap(constraint, combined_text)
        if overlap and _contains_dangerous_change(combined_text):
            violated_constraints.append(constraint)
    if violated_constraints and decision != StepSourceOfTruthGuardDecision.BLOCKED:
        reasons.append("Proposed action overlaps with constraint language and includes change-like intent.")
        risk_rank = max(risk_rank, 3)
        decision = StepSourceOfTruthGuardDecision.WARNING

    reference_text = " ".join([
        " ".join(context.requirement_ids),
        " ".join(context.acceptance_criteria),
        " ".join(context.constraints),
        context.source_of_truth_summary,
    ])
    if context.requirement_ids and _meaningful_overlap(combined_text, reference_text):
        if not matched_requirement_ids:
            matched_requirement_ids = list(context.requirement_ids)
        reasons.append("Proposed action overlaps with requirement context.")
    elif context.requirement_ids and not read_only and decision != StepSourceOfTruthGuardDecision.BLOCKED:
        warnings.append("Proposed action has no meaningful overlap with requirement context.")
        reasons.append("No requirement/context overlap detected.")
        risk_rank = max(risk_rank, 2)
        decision = StepSourceOfTruthGuardDecision.WARNING

    if (context.drift_risk or "").lower() == "critical" and decision != StepSourceOfTruthGuardDecision.BLOCKED:
        risk_rank = max(risk_rank, 4)
        if read_only:
            warnings.append("Context drift risk is critical; read-only review/check action may proceed with caution.")
            decision = StepSourceOfTruthGuardDecision.WARNING
        else:
            reasons.append("Context drift risk is critical and proposed action is not clearly read-only.")
            decision = StepSourceOfTruthGuardDecision.BLOCKED

    if read_only and not forbidden_hits and not context.parse_warnings and context.requirement_ids:
        reasons.append("Read-only/review/check action is allowed by guard.")
        if decision == StepSourceOfTruthGuardDecision.ALLOWED:
            risk_rank = min(risk_rank, 1)

    if decision == StepSourceOfTruthGuardDecision.ALLOWED:
        recommended = "Proceed with the proposed read-only or requirement-aligned action. This guard does not execute it."
    elif decision == StepSourceOfTruthGuardDecision.WARNING:
        recommended = "Review warnings and link the action to confirmed requirements before proceeding."
    else:
        recommended = "Do not proceed until forbidden changes or critical drift risks are resolved."

    return StepSourceOfTruthGuardResult(
        decision=decision,
        drift_risk=_risk_from_rank(risk_rank),
        matched_requirement_ids=_dedupe(matched_requirement_ids),
        violated_constraints=_dedupe(violated_constraints),
        forbidden_change_hits=_dedupe(forbidden_hits),
        warnings=_dedupe(warnings),
        reasons=_dedupe(reasons),
        recommended_next_step=recommended,
    )


# ── Unified Autonomous Project Intake v1 ─────────────────────────────────────
# Pure deterministic helpers — no DB, no LLM, no providers, no file reads,
# no shell commands, no side effects, no project/run creation.

_MAX_UNIFIED_QUESTIONS = 12
_MAX_UNIFIED_SOT_ITEMS = 10
_MAX_UNIFIED_MODULES = 12
_MAX_UNIFIED_PLAN_STEPS = 12


class UnifiedIntakeMode(str, enum.Enum):
    IDEA = "idea"
    DOCUMENT = "document"
    EXISTING_PROJECT = "existing_project"


class UnifiedIntakeRequest(BaseModel):
    mode: UnifiedIntakeMode
    title: str = ""
    raw_input: str = ""
    document_excerpt: str = ""
    project_path: str = ""
    known_stack: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    desired_outcome: str = ""


class ClarifyingQuestion(BaseModel):
    id: str
    question: str
    reason: str
    required: bool = True
    category: str = "product"


class DraftSourceOfTruthPreview(BaseModel):
    product_name: str
    product_summary: str
    target_users: list[str]
    goals: list[str]
    non_goals: list[str]
    constraints: list[str]
    risks: list[str]
    open_questions: list[str]
    confidence: str


class DraftModuleMapPreview(BaseModel):
    available: bool
    modules: list[dict]
    inferred_stack: list[str]
    unknowns: list[str]
    confidence: str


class DraftAgentPlanStep(BaseModel):
    id: str
    title: str
    agent_role: str
    reason: str
    depends_on: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    expected_outputs: list[str] = Field(default_factory=list)


class UnifiedAutonomousIntakePreviewResponse(BaseModel):
    mode: str
    classification_reason: str
    clarifying_questions: list[ClarifyingQuestion]
    source_of_truth_preview: DraftSourceOfTruthPreview
    module_map_preview: DraftModuleMapPreview
    multi_agent_plan: list[DraftAgentPlanStep]
    next_recommended_action: str
    safety_notes: list[str]
    limitations: list[str]


class ExistingProjectRepoIntakeRequest(BaseModel):
    project_id: str | None = None
    project_path: str = ""
    max_files: int = 500
    max_depth: int = 8
    include_manifest_snippets: bool = True


class ExistingProjectDetectedArea(BaseModel):
    id: str
    title: str
    kind: str
    path_hints: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    notes: list[str] = Field(default_factory=list)


class ExistingProjectManifestSummary(BaseModel):
    path: str
    kind: str
    detected_scripts: list[str] = Field(default_factory=list)
    dependencies_hint: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ExistingProjectRepoIntakeResponse(BaseModel):
    project_id: str | None = None
    project_path_hint: str = ""
    detected_stack: list[str] = Field(default_factory=list)
    detected_project_type: str = "unknown"
    detected_areas: list[ExistingProjectDetectedArea] = Field(default_factory=list)
    manifest_summaries: list[ExistingProjectManifestSummary] = Field(default_factory=list)
    protected_path_warnings: list[str] = Field(default_factory=list)
    source_of_truth_hints: list[str] = Field(default_factory=list)
    module_map_hints: list[str] = Field(default_factory=list)
    test_discovery_hints: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    recommended_first_safe_action: str = ""
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ── Unified intake helpers ────────────────────────────────────────────────────

def _cq(
    id: str,
    question: str,
    reason: str,
    required: bool = True,
    category: str = "product",
) -> ClarifyingQuestion:
    return ClarifyingQuestion(id=id, question=question, reason=reason, required=required, category=category)


def _plan_step(
    id: str,
    title: str,
    agent_role: str,
    reason: str,
    depends_on: Optional[list[str]] = None,
    risk_level: str = "medium",
    expected_outputs: Optional[list[str]] = None,
) -> DraftAgentPlanStep:
    return DraftAgentPlanStep(
        id=id,
        title=title,
        agent_role=agent_role,
        reason=reason,
        depends_on=depends_on or [],
        risk_level=risk_level,
        expected_outputs=expected_outputs or [],
    )


# ── Existing Project Read-only Repo Intake Fastlane v1 ───────────────────────

_REPO_MAX_STACK = 20
_REPO_MAX_AREAS = 20
_REPO_MAX_PATH_HINTS = 20
_REPO_MAX_MANIFESTS = 20
_REPO_MAX_SCRIPTS = 20
_REPO_MAX_DEPENDENCIES = 30
_REPO_MAX_LIST = 20
_REPO_MANIFEST_MAX_BYTES = 24_000
_REPO_MANIFEST_MAX_CHARS = 24_000

_REPO_IGNORED_DIRS = {
    ".git", ".hg", ".svn",
    "node_modules", "vendor", "dist", "build", "out",
    ".venv", "venv", "env", "__pycache__", "coverage",
    ".next", ".nuxt", "target", ".pytest_cache", ".mypy_cache",
    ".turbo", ".gradle", "storage/logs",
}

_REPO_SECRET_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.test", ".envrc",
    "id_rsa", "id_dsa", "id_ed25519", "secrets.json", "secrets.yaml",
    "secrets.yml", "credentials.json", "credentials.yml",
}
_REPO_SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".crt", ".cer"}
_REPO_SECRET_WORDS = re.compile(r"(?i)(secret|credential|private[_-]?key|api[_-]?key|access[_-]?key|token)")
_REPO_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)\s*[:=]\s*[^\\s,;\"']+"
)

_REPO_MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "requirements.txt", "composer.json",
    "docker-compose.yml", "docker-compose.yaml", "Dockerfile",
    "tsconfig.json", "pytest.ini", "phpunit.xml",
}
_REPO_MANIFEST_PREFIXES = ("vite.config.",)


def _repo_short(value: object, max_chars: int = 200) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def _repo_dedupe(items: list[str], limit: int = _REPO_MAX_LIST) -> list[str]:
    result: list[str] = []
    for item in items:
        text = _repo_short(item, 240)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _repo_is_ignored_path(rel_str: str) -> bool:
    parts = rel_str.split("/")
    for part in parts:
        if part in _REPO_IGNORED_DIRS:
            return True
    return any(rel_str == item or rel_str.startswith(item + "/") for item in _REPO_IGNORED_DIRS if "/" in item)


def _repo_is_secret_path(rel_str: str) -> bool:
    path = Path(rel_str)
    name = path.name.lower()
    return (
        name in _REPO_SECRET_FILENAMES
        or path.suffix.lower() in _REPO_SECRET_SUFFIXES
        or bool(_REPO_SECRET_WORDS.search(rel_str))
    )


def _repo_is_manifest(path: Path) -> bool:
    return path.name in _REPO_MANIFEST_NAMES or any(path.name.startswith(prefix) for prefix in _REPO_MANIFEST_PREFIXES)


def _repo_redact_manifest_text(value: object) -> tuple[str, bool]:
    text = _repo_short(value, 220)
    if not text:
        return "", False
    redacted = _REPO_SECRET_ASSIGNMENT_RE.sub(
        lambda m: m.group(0).split("=", 1)[0].split(":", 1)[0] + "=[REDACTED]",
        text,
    )
    if _sot_contains_secret(redacted):
        redacted = "[REDACTED]"
    return redacted, redacted != text


def _repo_add_stack(stack: list[str], *items: str) -> None:
    for item in items:
        clean = _repo_short(item.lower().replace("_", "-"), 80)
        if clean and clean not in stack and len(stack) < _REPO_MAX_STACK:
            stack.append(clean)


def _repo_register_area(
    areas: dict[str, ExistingProjectDetectedArea],
    *,
    id: str,
    title: str,
    kind: str,
    path_hint: str,
    confidence: str = "medium",
    note: str = "",
) -> None:
    if id not in areas:
        areas[id] = ExistingProjectDetectedArea(
            id=id,
            title=title,
            kind=kind,
            confidence=confidence,
            path_hints=[],
            notes=[],
        )
    area = areas[id]
    if path_hint and path_hint not in area.path_hints and len(area.path_hints) < _REPO_MAX_PATH_HINTS:
        area.path_hints.append(path_hint)
    if note and note not in area.notes and len(area.notes) < 8:
        area.notes.append(note)


def _repo_detect_from_path(rel_str: str, areas: dict[str, ExistingProjectDetectedArea], stack: list[str]) -> None:
    lower = rel_str.lower()
    parts = lower.split("/")
    if "frontend" in parts or "pages" in parts or "components" in parts or rel_str.endswith((".tsx", ".jsx")):
        _repo_register_area(areas, id="frontend", title="Frontend UI", kind="frontend", path_hint=rel_str)
    if "backend" in parts or "api" in parts or "routes" in parts or "controllers" in parts:
        _repo_register_area(areas, id="backend", title="Backend/API", kind="backend", path_hint=rel_str)
    if "database" in lower or "migrations" in parts or "schema.prisma" in lower or lower.endswith(".sql"):
        _repo_register_area(areas, id="database", title="Database & Schema", kind="database", path_hint=rel_str)
        _repo_add_stack(stack, "database")
    if "tests" in parts or "test" in parts or rel_str.endswith((".spec.ts", ".test.ts", "_test.py")):
        _repo_register_area(areas, id="tests", title="Tests & QA", kind="tests", path_hint=rel_str)
    if "docker" in lower or "compose" in lower or ".github/workflows" in lower or "deploy" in lower:
        _repo_register_area(areas, id="deployment", title="Deployment & Config", kind="deployment", path_hint=rel_str)
    if lower.endswith((".ts", ".tsx")):
        _repo_add_stack(stack, "typescript")
    if lower.endswith(".py"):
        _repo_add_stack(stack, "python")
    if lower.endswith(".php"):
        _repo_add_stack(stack, "php")


def _repo_manifest_summary(path: Path, root: Path, stack: list[str]) -> ExistingProjectManifestSummary | None:
    try:
        if not path.is_file() or path.stat().st_size > _REPO_MANIFEST_MAX_BYTES:
            return ExistingProjectManifestSummary(
                path=path.relative_to(root).as_posix(),
                kind=path.name,
                warnings=["Manifest was skipped because it exceeds the read cap."],
            )
        raw = path.read_bytes()[:_REPO_MANIFEST_MAX_BYTES].decode("utf-8", errors="replace")[:_REPO_MANIFEST_MAX_CHARS]
    except OSError as exc:
        return ExistingProjectManifestSummary(
            path=path.relative_to(root).as_posix(),
            kind=path.name,
            warnings=[f"Manifest could not be read: {exc}"],
        )

    rel = path.relative_to(root).as_posix()
    name = path.name
    scripts: list[str] = []
    deps: list[str] = []
    warnings: list[str] = []

    def _add_script(script_name: str, script_value: object) -> None:
        text, redacted = _repo_redact_manifest_text(f"{script_name}: {script_value}")
        if redacted:
            warnings.append("Secret-like manifest script content was redacted.")
        if text and text not in scripts and len(scripts) < _REPO_MAX_SCRIPTS:
            scripts.append(text)

    def _add_dep(dep: str) -> None:
        clean = _repo_short(dep.lower(), 100)
        if clean and clean not in deps and len(deps) < _REPO_MAX_DEPENDENCIES:
            deps.append(clean)

    if name == "package.json":
        _repo_add_stack(stack, "node")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            warnings.append("package.json could not be parsed; using filename hints only.")
        else:
            for script_name, script_value in (parsed.get("scripts") or {}).items():
                _add_script(str(script_name), script_value)
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                for dep_name in (parsed.get(section) or {}).keys():
                    _add_dep(str(dep_name))
            dep_text = " ".join(deps)
            if "react" in dep_text:
                _repo_add_stack(stack, "react")
            if "vite" in dep_text:
                _repo_add_stack(stack, "vite")
            if "typescript" in dep_text:
                _repo_add_stack(stack, "typescript")
            if "next" in dep_text:
                _repo_add_stack(stack, "nextjs")
            if "express" in dep_text or "fastify" in dep_text:
                _repo_add_stack(stack, "node-backend")
    elif name == "pyproject.toml":
        _repo_add_stack(stack, "python")
        try:
            parsed = tomllib.loads(raw)
        except tomllib.TOMLDecodeError:
            warnings.append("pyproject.toml could not be parsed; using filename hints only.")
        else:
            project = parsed.get("project") or {}
            for dep in project.get("dependencies") or []:
                _add_dep(str(dep).split("==", 1)[0].split(">=", 1)[0])
            poetry_deps = (((parsed.get("tool") or {}).get("poetry") or {}).get("dependencies") or {})
            for dep_name in poetry_deps.keys():
                _add_dep(str(dep_name))
            tool = parsed.get("tool") or {}
            if "pytest" in tool:
                _repo_add_stack(stack, "pytest")
                scripts.append("pytest: configured in pyproject.toml")
            dep_text = " ".join(deps).lower()
            if "fastapi" in dep_text:
                _repo_add_stack(stack, "fastapi")
            if "django" in dep_text:
                _repo_add_stack(stack, "django")
    elif name == "requirements.txt":
        _repo_add_stack(stack, "python")
        for line in raw.splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned.startswith("#"):
                continue
            _add_dep(re.split(r"[<>=~!;\\[]", cleaned, maxsplit=1)[0])
        dep_text = " ".join(deps).lower()
        if "fastapi" in dep_text:
            _repo_add_stack(stack, "fastapi")
        if "pytest" in dep_text:
            _repo_add_stack(stack, "pytest")
    elif name == "composer.json":
        _repo_add_stack(stack, "php", "composer")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            warnings.append("composer.json could not be parsed; using filename hints only.")
        else:
            for section in ("require", "require-dev"):
                for dep_name in (parsed.get(section) or {}).keys():
                    _add_dep(str(dep_name))
            for script_name, script_value in (parsed.get("scripts") or {}).items():
                _add_script(str(script_name), script_value)
            dep_text = " ".join(deps).lower()
            if "laravel" in dep_text:
                _repo_add_stack(stack, "laravel")
    elif name.startswith("vite.config."):
        _repo_add_stack(stack, "vite")
        if "react" in raw.lower():
            _repo_add_stack(stack, "react")
    elif name == "tsconfig.json":
        _repo_add_stack(stack, "typescript")
    elif name == "pytest.ini":
        _repo_add_stack(stack, "pytest")
        scripts.append("pytest: configured in pytest.ini")
    elif name == "phpunit.xml":
        _repo_add_stack(stack, "phpunit")
        scripts.append("phpunit: configured in phpunit.xml")
    elif name in {"docker-compose.yml", "docker-compose.yaml", "Dockerfile"}:
        _repo_add_stack(stack, "docker", "deployment")
        lower = raw.lower()
        if "postgres" in lower:
            _repo_add_stack(stack, "postgresql")
        if "mysql" in lower:
            _repo_add_stack(stack, "mysql")

    return ExistingProjectManifestSummary(
        path=rel,
        kind=name,
        detected_scripts=_repo_dedupe(scripts, _REPO_MAX_SCRIPTS),
        dependencies_hint=_repo_dedupe(deps, _REPO_MAX_DEPENDENCIES),
        warnings=_repo_dedupe(warnings, 10),
    )


def _repo_project_type(stack: list[str], areas: dict[str, ExistingProjectDetectedArea]) -> str:
    area_ids = set(areas.keys())
    stack_text = " ".join(stack)
    if "laravel" in stack_text:
        return "php_laravel_app"
    if "react" in stack_text and "backend" in area_ids:
        return "fullstack_web_app"
    if "frontend" in area_ids and "backend" in area_ids:
        return "fullstack_web_app"
    if "frontend" in area_ids:
        return "frontend_app"
    if "fastapi" in stack_text or "backend" in area_ids:
        return "backend_api"
    if "php" in stack_text:
        return "php_app"
    if "python" in stack_text:
        return "python_project"
    return "unknown"


def build_existing_project_repo_intake_preview(
    req: ExistingProjectRepoIntakeRequest,
) -> ExistingProjectRepoIntakeResponse:
    """Build a bounded read-only existing-project repository intake preview.

    Reads directory metadata and a small allowlist of manifest/config files.
    Never reads arbitrary source files, secret-like files, runs commands,
    calls providers, writes DB records, creates runs/tool_calls, or proposes
    patches.
    """
    project_path = (req.project_path or "").strip()
    if not project_path:
        return ExistingProjectRepoIntakeResponse(
            project_id=req.project_id,
            project_path_hint="",
            protected_path_warnings=["Project path is required for repository intake preview."],
            recommended_first_safe_action="Select or enter an existing project path before repo intake.",
            safety_notes=[
                "Repo intake preview is read-only.",
                "No project, run, run step, tool_call, provider call, command, patch proposal, apply, or test execution was created.",
            ],
            limitations=["No repository analysis was performed because no path was provided."],
        )
    if "\x00" in project_path or any(part == ".." for part in Path(project_path).parts):
        return ExistingProjectRepoIntakeResponse(
            project_id=req.project_id,
            project_path_hint=project_path,
            protected_path_warnings=["Project path contains unsafe traversal or null-byte content."],
            recommended_first_safe_action="Enter a canonical project directory path and retry read-only repo intake.",
            safety_notes=["Invalid path was rejected before traversal."],
            limitations=["No repository analysis was performed."],
        )
    try:
        root = Path(project_path).expanduser().resolve(strict=True)
    except (OSError, ValueError) as exc:
        return ExistingProjectRepoIntakeResponse(
            project_id=req.project_id,
            project_path_hint=project_path,
            protected_path_warnings=[f"Project path is not accessible: {exc}"],
            recommended_first_safe_action="Verify the existing project path, then rerun read-only repo intake.",
            safety_notes=["Invalid path was handled without writes or tool calls."],
            limitations=["No repository analysis was performed."],
        )
    if not root.is_dir():
        return ExistingProjectRepoIntakeResponse(
            project_id=req.project_id,
            project_path_hint=str(root),
            protected_path_warnings=["Project path is not a directory."],
            recommended_first_safe_action="Select a directory before rerunning read-only repo intake.",
            safety_notes=["No traversal was performed for non-directory path."],
            limitations=["No repository analysis was performed."],
        )

    max_files = max(1, min(req.max_files, 2000))
    max_depth = max(1, min(req.max_depth, 12))
    stack: list[str] = []
    areas: dict[str, ExistingProjectDetectedArea] = {}
    manifests: list[ExistingProjectManifestSummary] = []
    protected_warnings: list[str] = []
    files_seen = 0
    truncated = False

    def _walk(directory: Path, depth: int) -> None:
        nonlocal files_seen, truncated
        if depth > max_depth or files_seen >= max_files:
            truncated = files_seen >= max_files
            return
        try:
            entries = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except (OSError, PermissionError):
            return
        for entry in entries:
            if files_seen >= max_files:
                truncated = True
                return
            if entry.is_symlink():
                continue
            try:
                rel = entry.relative_to(root).as_posix()
            except ValueError:
                continue
            if _repo_is_ignored_path(rel):
                continue
            if _repo_is_secret_path(rel):
                if len(protected_warnings) < 30:
                    protected_warnings.append(f"Protected path was not read: {rel}")
                continue
            if entry.is_dir():
                _repo_detect_from_path(rel, areas, stack)
                _walk(entry, depth + 1)
                continue
            if not entry.is_file():
                continue
            files_seen += 1
            _repo_detect_from_path(rel, areas, stack)
            if req.include_manifest_snippets and len(manifests) < _REPO_MAX_MANIFESTS and _repo_is_manifest(entry):
                summary = _repo_manifest_summary(entry, root, stack)
                if summary is not None:
                    manifests.append(summary)

    _walk(root, 1)

    if truncated:
        protected_warnings.append(f"Traversal capped at {max_files} file entries.")

    if manifests:
        manifest_paths = [manifest.path for manifest in manifests]
        if any(path == "package.json" for path in manifest_paths):
            _repo_register_area(areas, id="config", title="Project Manifests", kind="config", path_hint="package.json")
        if any(path in {"pyproject.toml", "requirements.txt"} for path in manifest_paths):
            _repo_register_area(areas, id="backend", title="Backend/API", kind="backend", path_hint="pyproject.toml", note="Python manifest detected")

    project_type = _repo_project_type(stack, areas)
    area_list = list(areas.values())[:_REPO_MAX_AREAS]
    module_map_hints = [
        f"Create a Module Map entry for {area.title} using path hints: {', '.join(area.path_hints[:5])}."
        for area in area_list[:10]
    ]
    test_hints: list[str] = []
    for manifest in manifests:
        for script in manifest.detected_scripts:
            if "test" in script.lower() or "pytest" in script.lower() or "phpunit" in script.lower():
                test_hints.append(f"Review manifest script `{script}` from {manifest.path} as a candidate test command.")
    if "tests" in areas:
        test_hints.append("Tests folder detected; ask which test command is safe before execution.")

    sot_hints = [
        f"Existing project type appears to be {project_type}. Confirm the current product scope before creating a run.",
        "Use detected areas as initial Source of Truth scope boundaries.",
    ]
    if stack:
        sot_hints.append(f"Detected stack hints: {', '.join(stack[:8])}. Confirm what is authoritative.")

    clarifying = [
        "Which parts of the existing project are safe to change first?",
        "Which modules or paths are protected and require manual approval?",
        "What command should be used for typecheck/build/test after a future apply?",
        "Which detected stack hints are current versus legacy?",
    ]
    if not test_hints:
        clarifying.append("Where are the project's tests and safe verification commands documented?")
    if not area_list:
        clarifying.append("Which top-level folders map to frontend, backend, database, tests, and deployment?")

    if "tests" in areas:
        first_action = "Confirm detected test command and choose the first low-risk module for context gathering."
    elif area_list:
        first_action = f"Confirm Module Map boundaries for {area_list[0].title}, then gather read-only context manually."
    else:
        first_action = "Answer structure questions before creating Source of Truth or Module Map drafts."

    safety_notes = [
        "Repo intake preview is read-only.",
        "Only directory metadata and small allowlisted manifest/config files were inspected.",
        "No arbitrary source file contents were read.",
        "No project, run, run step, tool_call, provider call, command, patch proposal, apply, or test execution was created.",
        "Secret-like paths were not read.",
    ]
    limitations = [
        "Read-only structure/manifest analysis only.",
        "No arbitrary source file reading.",
        "No semantic code understanding.",
        "No provider/LLM reasoning.",
        "No automatic Module Map persistence.",
        "No test execution.",
        "No patch/test/fix loop.",
    ]
    if truncated:
        limitations.append("Traversal was capped; rerun with a higher max_files value if needed.")

    return ExistingProjectRepoIntakeResponse(
        project_id=req.project_id,
        project_path_hint=str(root),
        detected_stack=_repo_dedupe(stack, _REPO_MAX_STACK),
        detected_project_type=project_type,
        detected_areas=area_list,
        manifest_summaries=manifests[:_REPO_MAX_MANIFESTS],
        protected_path_warnings=_repo_dedupe(protected_warnings, 30),
        source_of_truth_hints=_repo_dedupe(sot_hints, 10),
        module_map_hints=_repo_dedupe(module_map_hints, 12),
        test_discovery_hints=_repo_dedupe(test_hints, 12),
        clarifying_questions=_repo_dedupe(clarifying, 12),
        recommended_first_safe_action=first_action,
        safety_notes=safety_notes,
        limitations=limitations,
    )


def _infer_product_name(title: str, raw_input: str) -> str:
    if title.strip():
        return title.strip()[:80]
    text = raw_input.strip()
    if not text:
        return "Unnamed Project"
    first_line = text.splitlines()[0].strip()
    if len(first_line) <= 80:
        return first_line or "Unnamed Project"
    return first_line[:77].rsplit(" ", 1)[0].strip() + "..."


def _safe_summary(text: str, max_chars: int = 300) -> str:
    """Return a safe, length-bounded summary — never a raw document dump."""
    text = text.strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0].strip()
    return truncated + "..."


def _infer_stack_from_signals(signals: set[str], known_stack: list[str]) -> list[str]:
    if known_stack:
        return known_stack[:8]
    inferred: list[str] = []
    if "database" in signals:
        inferred.append("database")
    if "auth" in signals:
        inferred.append("auth")
    if "payments" in signals:
        inferred.append("payments")
    if "uploads" in signals:
        inferred.append("file-storage")
    if "notifications" in signals:
        inferred.append("notifications")
    return inferred


# ── Idea mode ─────────────────────────────────────────────────────────────────

def _idea_clarifying_questions(text: str, signals: set[str]) -> list[ClarifyingQuestion]:
    qs = [
        _cq("cq-idea-1", "What specific problem does this product solve?",
            "Defines scope and priorities for the plan.", required=True),
        _cq("cq-idea-2", "Who are the target users or customers?",
            "Drives auth, permissions, and UI structure.", required=True),
        _cq("cq-idea-3", "Is this an MVP, prototype, or full production product?",
            "Defines depth of implementation and quality requirements.", required=True),
        _cq("cq-idea-4", "What platform is this for (web app, mobile, API, CLI, automation)?",
            "Determines tech stack and architecture direction.", required=True),
        _cq("cq-idea-5", "What does success look like in the first release?",
            "Defines acceptance criteria and done criteria.", required=True),
        _cq("cq-idea-6", "What differentiates this from existing solutions?",
            "Clarifies competitive positioning and unique requirements.", required=False, category="product_market"),
        _cq("cq-idea-7", "Do you have a preferred tech stack, or should the system choose?",
            "Affects all implementation decisions.", required=False, category="tech"),
    ]
    if "auth" not in signals:
        qs.append(_cq("cq-idea-8", "Does this product require user authentication or roles?",
                       "Drives security architecture and user management.", required=False, category="security"))
    if "database" not in signals:
        qs.append(_cq("cq-idea-9", "What data needs to be stored, and what are the storage constraints?",
                       "Determines persistence layer and data model.", required=False, category="data"))
    qs.extend([
        _cq("cq-idea-10", "Are there budget, timeline, or team size constraints?",
            "Affects scope and delivery plan.", required=False, category="constraints"),
        _cq("cq-idea-11", "Any UI/design requirements, brand guidelines, or existing mockups?",
            "Guides frontend implementation approach.", required=False, category="design"),
        _cq("cq-idea-12", "Where will this be deployed (local, cloud, VPS)?",
            "Affects infrastructure and CI/CD decisions.", required=False, category="deployment"),
    ])
    return qs[:_MAX_UNIFIED_QUESTIONS]


def _idea_sot_preview(req: UnifiedIntakeRequest, questions: list[ClarifyingQuestion]) -> DraftSourceOfTruthPreview:
    text = req.raw_input.strip()
    signals = _detect_signals(text)
    target = detect_target_type(text + " " + req.title)
    target_label = target.value.replace("_", " ")

    product_name = _infer_product_name(req.title, text)
    product_summary = _safe_summary(text, max_chars=300) or f"Idea: {product_name}"

    target_users: list[str] = []
    user_match = re.search(r"\bfor\s+([A-Za-z0-9 _/-]{3,60})(?:\s+with|\s+to|\s+that|[.;]|$)", text, _LOWER)
    if user_match:
        target_users = [user_match.group(1).strip()]
    if not target_users:
        target_users = ["Target users not confirmed — answer clarifying question cq-idea-2"]

    goals = [f"Build a {target_label} that addresses the stated idea"]
    if req.desired_outcome:
        goals.append(req.desired_outcome)
    if "auth" in signals:
        goals.append("Implement authentication and authorization")
    if "database" in signals:
        goals.append("Design and implement data persistence layer")
    goals = goals[:_MAX_UNIFIED_SOT_ITEMS]

    non_goals = [
        "Out-of-scope features not mentioned in the idea",
        "Production deployment (unless specified)",
        "Features requiring provider/LLM calls in this intake slice",
    ][:_MAX_UNIFIED_SOT_ITEMS]

    constraints = req.constraints[:_MAX_UNIFIED_SOT_ITEMS]
    if not constraints:
        constraints = ["Constraints not confirmed — answer clarifying questions"]

    risks = [
        "Target users not confirmed",
        "Tech stack not specified",
        "Acceptance criteria not defined",
        "Scope may expand without clarification",
    ][:_MAX_UNIFIED_SOT_ITEMS]

    open_questions = [q.question for q in questions[:_MAX_UNIFIED_SOT_ITEMS]]

    return DraftSourceOfTruthPreview(
        product_name=product_name,
        product_summary=product_summary,
        target_users=target_users,
        goals=goals,
        non_goals=non_goals,
        constraints=constraints,
        risks=risks,
        open_questions=open_questions,
        confidence="low",
    )


def _idea_module_map(req: UnifiedIntakeRequest) -> DraftModuleMapPreview:
    text = req.raw_input.strip() + " " + req.title
    signals = _detect_signals(text)
    target = detect_target_type(text)
    inferred_stack = _infer_stack_from_signals(signals, req.known_stack)

    modules: list[dict] = []
    if target in (ProjectTargetType.WEB_APP, ProjectTargetType.UNKNOWN):
        modules = [
            {"name": "Frontend", "type": "frontend", "description": "User interface layer"},
            {"name": "Backend API", "type": "backend", "description": "API and business logic"},
            {"name": "Database", "type": "database", "description": "Data persistence layer"},
        ]
        if "auth" in signals:
            modules.append({"name": "Auth", "type": "shared", "description": "Authentication and authorization"})
    elif target == ProjectTargetType.API_SERVICE:
        modules = [
            {"name": "API Layer", "type": "backend", "description": "REST or GraphQL endpoints"},
            {"name": "Business Logic", "type": "backend", "description": "Core domain logic"},
            {"name": "Data Layer", "type": "database", "description": "Data persistence and storage"},
        ]
    elif target == ProjectTargetType.CLI_TOOL:
        modules = [
            {"name": "CLI Entry Point", "type": "backend", "description": "Command-line interface"},
            {"name": "Core Logic", "type": "backend", "description": "Core processing logic"},
            {"name": "Configuration", "type": "shared", "description": "Config and settings management"},
        ]
    elif target == ProjectTargetType.MOBILE_APP:
        modules = [
            {"name": "Mobile App", "type": "frontend", "description": "Mobile UI layer"},
            {"name": "Backend API", "type": "backend", "description": "Server-side API"},
            {"name": "Data Layer", "type": "database", "description": "Local and remote data storage"},
        ]
    elif target == ProjectTargetType.AUTOMATION:
        modules = [
            {"name": "Automation Engine", "type": "backend", "description": "Automation core"},
            {"name": "Data Source", "type": "shared", "description": "Input data integration"},
            {"name": "Reporting", "type": "shared", "description": "Output and reporting"},
        ]
    else:
        modules = [
            {"name": "Core", "type": "backend", "description": "Core application logic"},
            {"name": "Data", "type": "database", "description": "Data layer"},
        ]
    modules = modules[:_MAX_UNIFIED_MODULES]

    unknowns = [
        "Module boundaries not confirmed — requires architecture review",
        "Tech stack not confirmed — modules are conceptual only",
    ]

    return DraftModuleMapPreview(
        available=True,
        modules=modules,
        inferred_stack=inferred_stack,
        unknowns=unknowns,
        confidence="low",
    )


def _idea_agent_plan() -> list[DraftAgentPlanStep]:
    return [
        _plan_step("step-1", "Product Analysis", "product-analyst",
                   "Clarify requirements, target users, and acceptance criteria.",
                   risk_level="low", expected_outputs=["Requirements list", "Acceptance criteria"]),
        _plan_step("step-2", "Architecture Design", "architect",
                   "Design system boundaries, data flow, and module structure.",
                   depends_on=["step-1"], risk_level="low",
                   expected_outputs=["Architecture outline", "Module boundaries"]),
        _plan_step("step-3", "Backend / API", "backend-developer",
                   "Implement backend routes, validation, and business logic.",
                   depends_on=["step-2"], risk_level="medium",
                   expected_outputs=["API contract", "Backend task list"]),
        _plan_step("step-4", "Frontend / UI", "frontend-developer",
                   "Implement screens, client state, and API integration.",
                   depends_on=["step-2", "step-3"], risk_level="medium",
                   expected_outputs=["Screen list", "Component plan"]),
        _plan_step("step-5", "Database / Data Model", "postgres-pro",
                   "Draft entities, relationships, and persistence choices.",
                   depends_on=["step-2"], risk_level="medium",
                   expected_outputs=["Entity list", "Storage model"]),
        _plan_step("step-6", "QA / Testing", "qa-expert",
                   "Plan tests, verification commands, and regression coverage.",
                   depends_on=["step-3", "step-4"], risk_level="low",
                   expected_outputs=["Test strategy", "Verification commands"]),
        _plan_step("step-7", "Security / Guard Review", "security-auditor",
                   "Review auth flows, permissions, and security boundaries.",
                   depends_on=["step-3", "step-4"], risk_level="high",
                   expected_outputs=["Security checklist", "Auth flow review"]),
        _plan_step("step-8", "Delivery / Final Report", "technical-writer",
                   "Document changes, check results, and remaining gaps.",
                   depends_on=["step-6", "step-7"], risk_level="low",
                   expected_outputs=["Final report", "Recommended next slice"]),
    ][:_MAX_UNIFIED_PLAN_STEPS]


# ── Document mode ─────────────────────────────────────────────────────────────

def _document_clarifying_questions(text: str, excerpt: str) -> list[ClarifyingQuestion]:
    combined = (text + " " + excerpt).strip()
    signals = _detect_signals(combined)
    qs = [
        _cq("cq-doc-1", "Is this requirements document complete or still a draft?",
            "Determines whether planning can begin or more clarification is needed.", required=True,
            category="requirements"),
        _cq("cq-doc-2", "Which requirements are must-have for the first release?",
            "Defines MVP scope and planning priorities.", required=True, category="requirements"),
        _cq("cq-doc-3", "How will success be measured? What are the acceptance criteria?",
            "Needed to verify that the implementation meets expectations.", required=True,
            category="requirements"),
        _cq("cq-doc-4", "Are there ambiguous or contradictory requirements?",
            "Prevents wrong interpretation during implementation.", required=True, category="requirements"),
        _cq("cq-doc-5", "Is a tech stack specified or preferred in the document?",
            "Affects architecture and implementation decisions.", required=False, category="tech"),
        _cq("cq-doc-6", "Are there delivery deadlines or release milestones?",
            "Affects planning timeline and scope decisions.", required=False, category="constraints"),
        _cq("cq-doc-7", "What external system integrations are needed?",
            "Third-party integrations add complexity and risk.", required=False, category="integrations"),
    ]
    if "auth" not in signals:
        qs.append(_cq("cq-doc-8", "Are security and authentication requirements explicitly specified?",
                       "Missing auth requirements are a common source of rework.", required=False,
                       category="security"))
    qs.extend([
        _cq("cq-doc-9", "Are testing and QA requirements documented?",
            "Needed to build a safe verification strategy.", required=False, category="quality"),
        _cq("cq-doc-10", "Who is the primary stakeholder or document owner?",
            "Clarification questions should go to the right person.", required=False, category="stakeholders"),
        _cq("cq-doc-11", "Are there compliance, legal, or regulatory constraints?",
            "Compliance requirements affect architecture and data handling.", required=False, category="compliance"),
        _cq("cq-doc-12", "What existing systems will this replace or extend?",
            "Integration and migration scope affects implementation risk.", required=False, category="integrations"),
    ])
    return qs[:_MAX_UNIFIED_QUESTIONS]


def _document_sot_preview(req: UnifiedIntakeRequest, questions: list[ClarifyingQuestion]) -> DraftSourceOfTruthPreview:
    product_name = _infer_product_name(req.title, req.raw_input)
    excerpt_summary = _safe_summary(req.document_excerpt or req.raw_input, max_chars=300)

    return DraftSourceOfTruthPreview(
        product_name=product_name,
        product_summary=excerpt_summary or f"Requirements document: {product_name}",
        target_users=["Requirements document stakeholders — confirm with document owner"],
        goals=[
            "Implement all must-have requirements from the document",
            "Meet specified acceptance criteria",
        ][:_MAX_UNIFIED_SOT_ITEMS],
        non_goals=[
            "Requirements not explicitly listed in the document",
            "Features beyond the documented scope",
        ][:_MAX_UNIFIED_SOT_ITEMS],
        constraints=(req.constraints or ["Constraints — see requirements document"])[:_MAX_UNIFIED_SOT_ITEMS],
        risks=[
            "Requirements document may be incomplete or a draft",
            "Acceptance criteria not yet verified",
            "Ambiguous requirements need clarification",
        ][:_MAX_UNIFIED_SOT_ITEMS],
        open_questions=[q.question for q in questions[:_MAX_UNIFIED_SOT_ITEMS]],
        confidence="low",
    )


def _document_module_map(req: UnifiedIntakeRequest) -> DraftModuleMapPreview:
    combined = (req.raw_input + " " + req.document_excerpt + " " + req.title).strip()
    signals = _detect_signals(combined)
    target = detect_target_type(combined)
    inferred_stack = _infer_stack_from_signals(signals, req.known_stack)

    modules: list[dict] = [
        {"name": "Requirements Layer", "type": "docs", "description": "Normalized requirements from document"},
    ]
    if target != ProjectTargetType.UNKNOWN:
        modules.append({"name": "Core Application", "type": "backend", "description": f"Inferred from {target.value.replace('_', ' ')}"})
    if "database" in signals:
        modules.append({"name": "Data Layer", "type": "database", "description": "Persistence layer"})
    if "auth" in signals:
        modules.append({"name": "Auth Module", "type": "shared", "description": "Authentication and authorization"})
    modules = modules[:_MAX_UNIFIED_MODULES]

    return DraftModuleMapPreview(
        available=bool(modules),
        modules=modules,
        inferred_stack=inferred_stack,
        unknowns=["Module structure depends on requirements clarification", "Tech stack TBD"],
        confidence="low",
    )


def _document_agent_plan() -> list[DraftAgentPlanStep]:
    return [
        _plan_step("step-1", "Document Analysis", "business-analyst",
                   "Extract, normalize, and prioritize requirements from the document.",
                   risk_level="low", expected_outputs=["Requirement list", "Priority tiers"]),
        _plan_step("step-2", "Requirement Normalization", "product-manager",
                   "Resolve ambiguities, fill gaps, and confirm acceptance criteria.",
                   depends_on=["step-1"], risk_level="low",
                   expected_outputs=["Clarified requirements", "Acceptance criteria"]),
        _plan_step("step-3", "Architecture Design", "architect",
                   "Design system architecture from normalized requirements.",
                   depends_on=["step-2"], risk_level="low",
                   expected_outputs=["Architecture outline", "Module plan"]),
        _plan_step("step-4", "Backend / API", "backend-developer",
                   "Implement backend routes and business logic.",
                   depends_on=["step-3"], risk_level="medium",
                   expected_outputs=["API contract", "Backend tasks"]),
        _plan_step("step-5", "Frontend / UI", "frontend-developer",
                   "Implement UI from requirements and architecture.",
                   depends_on=["step-3", "step-4"], risk_level="medium",
                   expected_outputs=["Screen list", "Component plan"]),
        _plan_step("step-6", "QA / Testing", "qa-expert",
                   "Verify all must-have requirements are testable and pass.",
                   depends_on=["step-4", "step-5"], risk_level="low",
                   expected_outputs=["Test results", "Requirement coverage"]),
        _plan_step("step-7", "Delivery / Report", "technical-writer",
                   "Document implementation summary and remaining gaps.",
                   depends_on=["step-6"], risk_level="low",
                   expected_outputs=["Delivery report", "Next slice"]),
    ][:_MAX_UNIFIED_PLAN_STEPS]


# ── Existing project mode ─────────────────────────────────────────────────────

def _existing_project_clarifying_questions_unified(
    project_path: str,
    known_stack: list[str],
    signals: dict | None = None,
) -> list[ClarifyingQuestion]:
    """Generate targeted clarifying questions for an existing project.

    When *signals* are provided (from detect_project_signals), injects
    stack-specific questions instead of generic ones.
    """
    sig = signals or {}
    detected_stack = sig.get("detected_stack", [])
    detected_folders = sig.get("folders", [])

    # Merge known and detected stack for tailored questions
    all_stack = list({*[s.lower() for s in known_stack], *[s.lower() for s in detected_stack]})

    has_python = any(s in all_stack for s in ["python", "fastapi", "django", "flask", "pydantic", "pytest"])
    has_node = any(s in all_stack for s in ["node", "javascript", "express", "nextjs"])
    has_react = any(s in all_stack for s in ["react", "vite", "frontend", "typescript"])
    has_db = any(s in all_stack for s in ["sqlite", "postgres", "postgresql", "mysql", "mongodb", "database"])
    has_docker = "docker" in all_stack
    has_tests = "pytest" in all_stack or "test" in detected_folders or "tests" in detected_folders

    qs = []

    # Always required
    qs.append(_cq("cq-ep-1", "What currently works in the project?",
        "Helps prioritize what to build next vs. what to fix.", required=True,
        category="existing_project"))
    qs.append(_cq("cq-ep-2", "What is broken, incomplete, or needs the most attention?",
        "Identifies blockers before new development begins.", required=True,
        category="existing_project"))
    qs.append(_cq("cq-ep-3", "What is the target goal for the next release or iteration?",
        "Defines scope and acceptance criteria for the planning cycle.", required=True,
        category="existing_project"))

    # Stack-specific test command
    if has_python and has_tests:
        qs.append(_cq("cq-ep-4",
            "What is the test command? (detected: Python/pytest — e.g. `pytest`, `pytest tests/`, `make test`)",
            "Required for safe changes — verifies nothing breaks after patches.", required=True,
            category="existing_project"))
    elif has_node:
        qs.append(_cq("cq-ep-4",
            "What is the test command? (detected: Node.js — e.g. `npm test`, `yarn test`)",
            "Required for safe changes — verifies nothing breaks after patches.", required=True,
            category="existing_project"))
    else:
        qs.append(_cq("cq-ep-4", "What is the test command (e.g., pytest, npm test, make test)?",
            "Required for safe changes — run tests before and after modifications.", required=True,
            category="existing_project"))

    qs.append(_cq("cq-ep-5", "Which files, modules, or areas must NOT be modified?",
        "Prevents accidental changes to critical or protected code.", required=True,
        category="existing_project"))

    # DB-specific
    if has_db:
        qs.append(_cq("cq-ep-6",
            "What database is in use and what are the migration/seeding requirements? "
            "(detected: database stack — confirm if migrations need approval before run)",
            "Prevents unsafe DB schema changes or accidental data loss.", required=True,
            category="existing_project"))
    else:
        qs.append(_cq("cq-ep-6",
            "What database, environment variables, or local services are required to run the project?",
            "Prevents unsafe assumptions about DB setup, migrations, and local dependencies.",
            required=False, category="existing_project"))

    # Docker-specific
    if has_docker:
        qs.append(_cq("cq-ep-7",
            "Is the project run via Docker or docker-compose? Which services are required locally?",
            "Detected Docker configuration — confirms how to run the project safely.",
            required=True, category="deployment"))
    else:
        qs.append(_cq("cq-ep-7", "Is there a design source (Figma, mockups, screenshots, or style guide)?",
            "Guides UI changes and prevents breaking existing design consistency.",
            required=False, category="design"))

    # Frontend-specific
    if has_react:
        qs.append(_cq("cq-ep-8",
            "What is the frontend build/dev command? (detected: React/Vite — e.g. `npm run dev`, `npm run build`)",
            "Confirms frontend development workflow before touching UI code.",
            required=False, category="existing_project"))
    else:
        qs.append(_cq("cq-ep-8", "Is the project in a git repository? What is the branch strategy?",
            "Affects how changes are staged and reviewed.", required=False, category="existing_project"))

    qs.append(_cq("cq-ep-9",
        "Are there .env files, secrets, or credentials that must remain untouched?",
        "Prevents accidental exposure of sensitive data.", required=False, category="security"))
    qs.append(_cq("cq-ep-10",
        "Are there known technical debt areas or fragile modules to avoid?",
        "Helps route around risky areas during first-pass changes.", required=False,
        category="existing_project"))

    return qs[:_MAX_UNIFIED_QUESTIONS]


def _existing_project_sot_preview(
    req: UnifiedIntakeRequest,
    questions: list[ClarifyingQuestion],
    signals: dict | None = None,
) -> DraftSourceOfTruthPreview:
    sig = signals or {}
    detected_stack: list[str] = sig.get("detected_stack", [])
    detected_folders: list[str] = sig.get("folders", [])

    path_name = ""
    if req.project_path:
        parts = req.project_path.replace("\\", "/").rstrip("/").split("/")
        path_name = parts[-1] if parts else ""

    product_name = req.title.strip() or path_name or "Existing Project"

    goals = ["Continue development from current state"]
    if req.desired_outcome:
        goals.append(req.desired_outcome)
    goals = goals[:_MAX_UNIFIED_SOT_ITEMS]

    # Build stack-aware constraints
    constraints = [
        "Preserve existing stack unless user approves change",
        "Do not touch secrets or environment files",
        "Prefer incremental reviewed patches over rewrites",
    ]
    if detected_stack:
        stack_str = ", ".join(detected_stack[:6])
        constraints.append(f"Detected stack: {stack_str} — follow existing conventions")
    if "docker" in detected_stack:
        constraints.append("Docker configuration must not be changed without approval")
    constraints.extend(req.constraints)
    constraints = constraints[:_MAX_UNIFIED_SOT_ITEMS]

    # Build risks — use detected info to be specific
    has_tests = "pytest" in detected_stack or "test" in detected_folders or "tests" in detected_folders
    has_db = any(s in detected_stack for s in ["sqlite", "postgres", "postgresql", "mysql", "mongodb"])
    risks = []
    if not detected_stack:
        risks.append("Project structure unknown — requires inventory before changes")
    if not has_tests:
        risks.append("Test command not confirmed — changes risk breaking unverified behaviour")
    else:
        risks.append("Test baseline must be established before first patch")
    if has_db:
        risks.append("Database migrations require explicit operator approval")
    risks.append("Protected modules not yet identified — must be confirmed before editing")
    if not detected_stack:
        risks.append("Database/env requirements not confirmed")
    risks = risks[:_MAX_UNIFIED_SOT_ITEMS]

    open_questions = [q.question for q in questions[:_MAX_UNIFIED_SOT_ITEMS]]

    stack_summary = ", ".join(detected_stack[:6]) if detected_stack else "unknown"
    folder_summary = ", ".join(detected_folders[:4]) if detected_folders else "unknown"

    return DraftSourceOfTruthPreview(
        product_name=product_name,
        product_summary=(
            f"Existing project continuation. "
            + (f"Detected stack: {stack_summary}. " if detected_stack else "")
            + (f"Detected folders: {folder_summary}. " if detected_folders else "")
            + (f"Path: {req.project_path}. " if req.project_path else "")
            + "Confirm goals and scope with the operator before planning."
        ),
        target_users=["Existing users — confirm current user roles during intake"],
        goals=goals,
        non_goals=[
            "Architecture rewrite without explicit approval",
            "Touching secrets, .env files, or production credentials",
            "Auto-executing commands without manual confirmation",
        ][:_MAX_UNIFIED_SOT_ITEMS],
        constraints=constraints,
        risks=risks,
        open_questions=open_questions,
        confidence="medium" if detected_stack else "low",
    )


def _existing_project_module_map(
    req: UnifiedIntakeRequest,
    signals: dict | None = None,
) -> DraftModuleMapPreview:
    sig = signals or {}
    detected_stack: list[str] = sig.get("detected_stack", [])
    detected_folders: list[str] = sig.get("folders", [])

    # Merge known_stack (preserve original casing) + detected_stack (title-cased)
    seen_lower: set[str] = set()
    all_stack: list[str] = []
    for s in req.known_stack:
        k = s.lower()
        if k not in seen_lower:
            seen_lower.add(k)
            all_stack.append(s)
    for s in detected_stack:
        k = s.lower()
        if k not in seen_lower:
            seen_lower.add(k)
            all_stack.append(s.title() if s.islower() else s)
    inferred_stack = all_stack[:8]
    modules: list[dict] = []

    # Build modules from detected folders first (real structure)
    folder_module_map = {
        "frontend": ("Frontend", "frontend"),
        "backend": ("Backend", "backend"),
        "src": ("Source", "core"),
        "app": ("Application", "core"),
        "api": ("API", "backend"),
        "mobile": ("Mobile", "mobile"),
        "tests": ("Tests", "qa"),
        "test": ("Tests", "qa"),
        "docs": ("Documentation", "docs"),
        "config": ("Configuration", "config"),
    }
    seen_module_names: set[str] = set()
    for folder in detected_folders:
        if folder in folder_module_map:
            name, mtype = folder_module_map[folder]
            if name not in seen_module_names:
                modules.append({
                    "name": name,
                    "type": mtype,
                    "description": f"Detected folder: {folder}/",
                    "paths": [f"{folder}/"],
                })
                seen_module_names.add(name)

    # Add stack-inferred modules if not already covered
    for tech in all_stack[:8]:
        t = tech.lower()
        if any(k in t for k in ["react", "vue", "angular", "next", "svelte"]) and "Frontend" not in seen_module_names:
            modules.append({"name": "Frontend", "type": "frontend", "description": f"UI layer ({tech})"})
            seen_module_names.add("Frontend")
        elif any(k in t for k in ["fastapi", "django", "flask", "express"]) and "Backend" not in seen_module_names:
            modules.append({"name": "Backend", "type": "backend", "description": f"Backend layer ({tech})"})
            seen_module_names.add("Backend")
        elif any(k in t for k in ["postgres", "mysql", "sqlite", "mongo"]) and "Database" not in seen_module_names:
            modules.append({"name": "Database", "type": "database", "description": f"Data layer ({tech})"})
            seen_module_names.add("Database")

    if not modules:
        path_name = ""
        if req.project_path:
            parts = req.project_path.replace("\\", "/").rstrip("/").split("/")
            path_name = parts[-1] if parts else ""
        if path_name:
            modules.append({"name": path_name, "type": "unknown", "description": "Inferred from project path"})

    modules = modules[:_MAX_UNIFIED_MODULES]

    unknowns = []
    if not detected_folders:
        unknowns.append("Folder structure not yet scanned — confirm project path")
    unknowns.append("Module boundaries and key files require repository inventory step")

    return DraftModuleMapPreview(
        available=bool(modules),
        modules=modules,
        inferred_stack=inferred_stack,
        unknowns=unknowns,
        confidence="medium" if detected_folders else "low",
    )


def _existing_project_agent_plan() -> list[DraftAgentPlanStep]:
    return [
        _plan_step("step-1", "Repository Inventory", "orchestrator",
                   "Identify project location, repository state, key folders, and safe working boundaries.",
                   risk_level="low", expected_outputs=["Project path confirmed", "Workspace boundary"]),
        _plan_step("step-2", "Source of Truth Confirmation", "product-manager",
                   "Confirm current product state, goals, and scope from operator input.",
                   depends_on=["step-1"], risk_level="low",
                   expected_outputs=["Confirmed SoT draft", "Acceptance criteria"]),
        _plan_step("step-3", "Module Map Drafting", "architect",
                   "Identify modules, stack, and key file boundaries from confirmed inventory.",
                   depends_on=["step-1"], risk_level="low",
                   expected_outputs=["Module map draft", "Stack profile"]),
        _plan_step("step-4", "Test Discovery", "qa-expert",
                   "Locate and validate test commands, baseline test status.",
                   depends_on=["step-1"], risk_level="low",
                   expected_outputs=["Validated test command", "Baseline test status"]),
        _plan_step("step-5", "First Safe Patch Candidate", "backend-developer",
                   "Prepare first safe, incremental patch candidate with guard review.",
                   depends_on=["step-2", "step-3", "step-4"], risk_level="high",
                   expected_outputs=["Patch proposal", "Guard result"]),
        _plan_step("step-6", "Delivery Report", "technical-writer",
                   "Document changes, verification results, and recommended next steps.",
                   depends_on=["step-5"], risk_level="low",
                   expected_outputs=["Delivery report", "Remaining gaps", "Next slice"]),
    ][:_MAX_UNIFIED_PLAN_STEPS]


# ── Main unified builder ──────────────────────────────────────────────────────

_UNIFIED_SAFETY_NOTES = [
    "This preview is read-only. It does not create projects, runs, or tool_calls.",
    "No provider or LLM calls are made. All output is deterministic.",
    "No file contents are read. No shell commands are executed.",
    "No database writes occur during this preview.",
    "Clarifying questions must be answered by the operator before planning begins.",
]

_UNIFIED_LIMITATIONS = [
    "Deterministic preview only — no provider/LLM reasoning in the preview step.",
    "No document parsing or file upload extraction — paste the TZ text directly.",
    "Existing project scan reads only metadata files (package.json, pyproject.toml, README) — no source code.",
    "No automatic project or run creation from this screen — confirm and create explicitly.",
    "Agent assignment execution starts after 'Confirm and Create Pending Run'.",
    "No patch or test loop from this intake screen — execution happens in RunDetail.",
]


def build_unified_autonomous_intake_preview(
    req: UnifiedIntakeRequest,
) -> UnifiedAutonomousIntakePreviewResponse:
    """Build a deterministic unified autonomous project intake preview.

    Accepts idea/document/existing_project mode.
    Returns clarifying questions, SoT preview, module map preview,
    and multi-agent plan preview.

    Pure function — no DB, no LLM, no tools, no providers, no file reads,
    no shell commands, no project/run creation, no side effects.
    """

    mode = req.mode
    text = (req.raw_input + " " + req.title).strip()
    signals = _detect_signals(text)

    if mode == UnifiedIntakeMode.IDEA:
        classification_reason = "Input classified as a new product idea from scratch."
        questions = _idea_clarifying_questions(text, signals)
        sot_preview = _idea_sot_preview(req, questions)
        module_map_preview = _idea_module_map(req)
        multi_agent_plan = _idea_agent_plan()
        next_action = (
            "Answer the clarifying questions above, then use the full intake pipeline "
            "(SoT draft → Module Map → Multi-Agent Plan → Development Run Preview → Confirm and Create Run)."
        )

    elif mode == UnifiedIntakeMode.DOCUMENT:
        classification_reason = "Input classified as a requirements document or specification."
        questions = _document_clarifying_questions(text, req.document_excerpt)
        sot_preview = _document_sot_preview(req, questions)
        module_map_preview = _document_module_map(req)
        multi_agent_plan = _document_agent_plan()
        next_action = (
            "Answer the clarifying questions, confirm requirement priorities, "
            "then proceed: SoT draft → Module Map → Multi-Agent Plan → Development Run Preview → Confirm and Create Run."
        )

    else:  # EXISTING_PROJECT
        classification_reason = "Input classified as an existing project requiring continuation or completion."
        # Scan the real project path for stack signals (read-only metadata only)
        repo_signals: dict = {}
        if req.project_path:
            try:
                repo_signals = detect_project_signals(req.project_path)
            except Exception:
                repo_signals = {}
        questions = _existing_project_clarifying_questions_unified(
            req.project_path, req.known_stack, signals=repo_signals
        )
        sot_preview = _existing_project_sot_preview(req, questions, signals=repo_signals)
        module_map_preview = _existing_project_module_map(req, signals=repo_signals)
        multi_agent_plan = _existing_project_agent_plan()
        next_action = (
            "Answer what works, what is broken, and what the target goal is. "
            "Then proceed: SoT draft → Module Map → Multi-Agent Plan → Development Run Preview → Confirm and Create Run."
        )

    return UnifiedAutonomousIntakePreviewResponse(
        mode=mode.value,
        classification_reason=classification_reason,
        clarifying_questions=questions[:_MAX_UNIFIED_QUESTIONS],
        source_of_truth_preview=DraftSourceOfTruthPreview(
            product_name=sot_preview.product_name,
            product_summary=sot_preview.product_summary,
            target_users=sot_preview.target_users[:_MAX_UNIFIED_SOT_ITEMS],
            goals=sot_preview.goals[:_MAX_UNIFIED_SOT_ITEMS],
            non_goals=sot_preview.non_goals[:_MAX_UNIFIED_SOT_ITEMS],
            constraints=sot_preview.constraints[:_MAX_UNIFIED_SOT_ITEMS],
            risks=sot_preview.risks[:_MAX_UNIFIED_SOT_ITEMS],
            open_questions=sot_preview.open_questions[:_MAX_UNIFIED_SOT_ITEMS],
            confidence=sot_preview.confidence,
        ),
        module_map_preview=DraftModuleMapPreview(
            available=module_map_preview.available,
            modules=module_map_preview.modules[:_MAX_UNIFIED_MODULES],
            inferred_stack=module_map_preview.inferred_stack,
            unknowns=module_map_preview.unknowns,
            confidence=module_map_preview.confidence,
        ),
        multi_agent_plan=multi_agent_plan[:_MAX_UNIFIED_PLAN_STEPS],
        next_recommended_action=next_action,
        safety_notes=_UNIFIED_SAFETY_NOTES,
        limitations=_UNIFIED_LIMITATIONS,
    )


# ── Clarifying Questions Engine v1 ────────────────────────────────────────────
# Pure deterministic refinement — no DB, no LLM, no providers, no file reads,
# no shell commands, no side effects, no project/run creation.

_MAX_CQE_SUMMARIES = 12


class ClarifyingAnswer(BaseModel):
    question_id: str
    answer: str = ""
    skipped: bool = False


class ClarifyingQuestionSet(BaseModel):
    mode: str
    questions: list[ClarifyingQuestion]
    required_count: int
    optional_count: int
    categories: list[str]
    next_recommended_action: str


class ClarifyingAnswersRequest(BaseModel):
    intake: UnifiedIntakeRequest
    answers: list[ClarifyingAnswer] = Field(default_factory=list)


class ClarifyingAnswerGap(BaseModel):
    question_id: str
    reason: str
    severity: str = "warning"


class ClarifiedIntakePreviewResponse(BaseModel):
    mode: str
    answered_question_ids: list[str]
    missing_required_questions: list[ClarifyingAnswerGap]
    applied_answer_summary: list[str]
    source_of_truth_preview: DraftSourceOfTruthPreview
    module_map_preview: DraftModuleMapPreview
    multi_agent_plan: list[DraftAgentPlanStep]
    confidence_before: str
    confidence_after: str
    next_recommended_action: str
    safety_notes: list[str]
    limitations: list[str]


# ── CQE pure helpers ──────────────────────────────────────────────────────────


def _cqe_short(text: str, max_chars: int = 150) -> str:
    """Safely truncate an answer for SoT embedding. Never a raw dump."""
    text = text.strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0].strip() + "..."


def _compute_confidence_after(required_total: int, required_answered: int) -> str:
    """Confidence after applying answers. Never exceeds 'medium' in this slice."""
    if required_total == 0:
        return "medium"
    if (required_answered / required_total) >= 0.5:
        return "medium"
    return "low"


def _cqe_answered(qid: str, answer_map: dict) -> str:
    """Return non-empty answer text or '' — never crashes on unknown id."""
    a = answer_map.get(qid)
    if a is None or a.skipped:
        return ""
    return a.answer.strip()


def _cqe_refine_sot(
    req: UnifiedIntakeRequest,
    baseline: DraftSourceOfTruthPreview,
    answer_map: dict,
    summaries: list[str],
    confidence_after: str,
) -> DraftSourceOfTruthPreview:
    """Apply user answers to refine the SoT draft conservatively.

    Pure — no DB, no LLM, no file reads, no side effects.
    All answer text is truncated at safe bounds before embedding.
    """
    target_users = list(baseline.target_users)
    goals = list(baseline.goals)
    non_goals = list(baseline.non_goals)
    constraints = list(baseline.constraints)
    risks = list(baseline.risks)
    open_questions = list(baseline.open_questions)
    product_name = baseline.product_name
    product_summary = baseline.product_summary

    if req.mode == UnifiedIntakeMode.IDEA:
        v = _cqe_answered("cq-idea-1", answer_map)
        if v:
            product_summary = _cqe_short(v, 300)
            summaries.append(f"Problem statement: {_cqe_short(v)}")

        v = _cqe_answered("cq-idea-2", answer_map)
        if v:
            target_users = [_cqe_short(v)]
            summaries.append(f"Target users: {_cqe_short(v)}")

        v = _cqe_answered("cq-idea-3", answer_map)
        if v:
            constraints = [c for c in constraints if "Constraints not confirmed" not in c]
            constraints.insert(0, f"Build type: {_cqe_short(v, 80)}")
            summaries.append(f"Build type: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-idea-4", answer_map)
        if v:
            if goals:
                goals[0] = f"Build {_cqe_short(v, 80)} that addresses the stated idea"
            summaries.append(f"Platform: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-idea-5", answer_map)
        if v:
            goals.append(f"Success criteria: {_cqe_short(v)}")
            summaries.append(f"Success criteria: {_cqe_short(v)}")

        v = _cqe_answered("cq-idea-7", answer_map)
        if v:
            constraints.append(f"Preferred tech stack: {_cqe_short(v, 80)}")
            summaries.append(f"Tech stack: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-idea-8", answer_map)
        if v:
            goals.append(f"Auth requirement: {_cqe_short(v, 80)}")
            summaries.append(f"Auth: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-idea-9", answer_map)
        if v:
            goals.append(f"Data storage: {_cqe_short(v)}")
            summaries.append(f"Data: {_cqe_short(v)}")

        v = _cqe_answered("cq-idea-10", answer_map)
        if v:
            constraints.append(f"Budget/timeline: {_cqe_short(v)}")
            summaries.append(f"Budget/timeline: {_cqe_short(v)}")

        v = _cqe_answered("cq-idea-12", answer_map)
        if v:
            constraints.append(f"Deployment: {_cqe_short(v, 80)}")
            summaries.append(f"Deployment: {_cqe_short(v, 80)}")

    elif req.mode == UnifiedIntakeMode.DOCUMENT:
        v = _cqe_answered("cq-doc-1", answer_map)
        if v:
            risks = [r for r in risks if "may be incomplete or a draft" not in r]
            risks.insert(0, f"Document status: {_cqe_short(v, 80)}")
            summaries.append(f"Document status: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-doc-2", answer_map)
        if v:
            goals.insert(0, f"Must-have: {_cqe_short(v)}")
            summaries.append(f"Must-have requirements: {_cqe_short(v)}")

        v = _cqe_answered("cq-doc-3", answer_map)
        if v:
            goals.append(f"Acceptance criteria: {_cqe_short(v)}")
            summaries.append(f"Acceptance criteria: {_cqe_short(v)}")

        v = _cqe_answered("cq-doc-4", answer_map)
        if v:
            risks = [r for r in risks if "Ambiguous requirements" not in r]
            risks.append(f"Resolved ambiguity: {_cqe_short(v)}")
            summaries.append(f"Ambiguity notes: {_cqe_short(v)}")

        v = _cqe_answered("cq-doc-5", answer_map)
        if v:
            constraints.append(f"Tech stack: {_cqe_short(v, 80)}")
            summaries.append(f"Tech stack: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-doc-6", answer_map)
        if v:
            constraints.append(f"Deadline: {_cqe_short(v, 80)}")
            summaries.append(f"Deadline: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-doc-8", answer_map)
        if v:
            goals.append(f"Security requirement: {_cqe_short(v)}")
            summaries.append(f"Security: {_cqe_short(v)}")

    else:  # EXISTING_PROJECT
        v = _cqe_answered("cq-ep-1", answer_map)
        if v:
            goals.append(f"Preserve working: {_cqe_short(v)}")
            summaries.append(f"What works: {_cqe_short(v)}")

        v = _cqe_answered("cq-ep-2", answer_map)
        if v:
            goals.insert(0, f"Fix: {_cqe_short(v)}")
            summaries.append(f"What is broken: {_cqe_short(v)}")

        v = _cqe_answered("cq-ep-3", answer_map)
        if v:
            goals.insert(0, f"Target goal: {_cqe_short(v)}")
            summaries.append(f"Target goal: {_cqe_short(v)}")

        v = _cqe_answered("cq-ep-4", answer_map)
        if v:
            constraints.append(f"Test command: {_cqe_short(v, 80)}")
            risks = [r for r in risks if "Test command not confirmed" not in r]
            summaries.append(f"Test command: {_cqe_short(v, 80)}")

        v = _cqe_answered("cq-ep-5", answer_map)
        if v:
            constraints.append(f"Protected modules: {_cqe_short(v)}")
            risks = [r for r in risks if "Protected modules not identified" not in r]
            summaries.append(f"Protected modules: {_cqe_short(v)}")

        v = _cqe_answered("cq-ep-6", answer_map)
        if v:
            constraints.append(f"Required services: {_cqe_short(v)}")
            risks = [r for r in risks if "Database/env requirements not confirmed" not in r]
            summaries.append(f"DB/env services: {_cqe_short(v)}")

    # Remove placeholder if real constraints were added
    if len(constraints) > 1:
        constraints = [c for c in constraints if "Constraints not confirmed" not in c]

    return DraftSourceOfTruthPreview(
        product_name=product_name,
        product_summary=product_summary,
        target_users=target_users[:_MAX_UNIFIED_SOT_ITEMS],
        goals=goals[:_MAX_UNIFIED_SOT_ITEMS],
        non_goals=non_goals[:_MAX_UNIFIED_SOT_ITEMS],
        constraints=constraints[:_MAX_UNIFIED_SOT_ITEMS],
        risks=risks[:_MAX_UNIFIED_SOT_ITEMS],
        open_questions=open_questions[:_MAX_UNIFIED_SOT_ITEMS],
        confidence=confidence_after,
    )


def _cqe_refine_module_map(
    req: UnifiedIntakeRequest,
    baseline: DraftModuleMapPreview,
    answer_map: dict,
) -> DraftModuleMapPreview:
    """Refine module map from tech-stack answers. Pure, no file reads."""
    modules = list(baseline.modules)
    inferred_stack = list(baseline.inferred_stack)
    unknowns = list(baseline.unknowns)

    stack_answer = ""
    if req.mode == UnifiedIntakeMode.IDEA:
        stack_answer = _cqe_answered("cq-idea-7", answer_map)
    elif req.mode == UnifiedIntakeMode.DOCUMENT:
        stack_answer = _cqe_answered("cq-doc-5", answer_map)

    if stack_answer:
        new_stack = [s.strip() for s in re.split(r"[,/;]+", stack_answer) if s.strip()][:8]
        if new_stack:
            inferred_stack = new_stack
            unknowns = [u for u in unknowns if "Tech stack" not in u]

    return DraftModuleMapPreview(
        available=baseline.available or bool(modules),
        modules=modules[:_MAX_UNIFIED_MODULES],
        inferred_stack=inferred_stack,
        unknowns=unknowns,
        confidence=baseline.confidence,
    )


def build_clarifying_question_set(req: UnifiedIntakeRequest) -> ClarifyingQuestionSet:
    """Build a structured, categorized set of clarifying questions.

    Pure function — no DB, no LLM, no providers, no file reads, no side effects.
    Reuses the unified preview builder to extract and categorize questions.
    """
    preview = build_unified_autonomous_intake_preview(req)
    questions = preview.clarifying_questions
    required_count = sum(1 for q in questions if q.required)
    optional_count = len(questions) - required_count
    # Preserve insertion order, deduplicate categories
    categories: list[str] = list(dict.fromkeys(q.category for q in questions))

    next_action = (
        f"Answer {required_count} required question(s) and submit to "
        "POST /api/project-intake/clarifying-preview to receive a refined preview."
    )

    return ClarifyingQuestionSet(
        mode=req.mode.value,
        questions=questions,
        required_count=required_count,
        optional_count=optional_count,
        categories=categories,
        next_recommended_action=next_action,
    )


def refine_unified_intake_with_answers(
    req: ClarifyingAnswersRequest,
) -> ClarifiedIntakePreviewResponse:
    """Refine unified intake preview by applying user-provided clarifying answers.

    Pure function — no DB, no LLM, no providers, no file reads,
    no shell commands, no project/run creation, no tool_calls, no side effects.
    Answers are truncated at safe bounds before embedding in the refined SoT.
    Unknown question_ids are silently ignored — never crash.
    """
    baseline = build_unified_autonomous_intake_preview(req.intake)
    questions = baseline.clarifying_questions
    confidence_before = baseline.source_of_truth_preview.confidence

    # Build answer lookup indexed by question_id
    answer_map: dict[str, ClarifyingAnswer] = {a.question_id: a for a in req.answers}

    answered_ids: list[str] = []
    missing_required: list[ClarifyingAnswerGap] = []

    for q in questions:
        a = answer_map.get(q.id)
        if a is None:
            if q.required:
                missing_required.append(ClarifyingAnswerGap(
                    question_id=q.id,
                    reason=f"Required question not answered: {q.question[:80]}",
                    severity="warning",
                ))
        elif a.skipped:
            if q.required:
                missing_required.append(ClarifyingAnswerGap(
                    question_id=q.id,
                    reason=f"Required question was skipped: {q.question[:80]}",
                    severity="warning",
                ))
        elif not a.answer.strip():
            if q.required:
                missing_required.append(ClarifyingAnswerGap(
                    question_id=q.id,
                    reason=f"Required question has empty answer: {q.question[:80]}",
                    severity="warning",
                ))
        else:
            answered_ids.append(q.id)

    required_questions = [q for q in questions if q.required]
    required_answered = sum(1 for q in required_questions if q.id in answered_ids)
    confidence_after = _compute_confidence_after(len(required_questions), required_answered)

    applied_summaries: list[str] = []
    refined_sot = _cqe_refine_sot(
        req.intake, baseline.source_of_truth_preview,
        answer_map, applied_summaries, confidence_after,
    )
    refined_mm = _cqe_refine_module_map(
        req.intake, baseline.module_map_preview, answer_map,
    )

    if missing_required:
        next_action = (
            f"{len(missing_required)} required question(s) remain unanswered. "
            "Answer them and resubmit to improve confidence further. "
            "Once all required questions are answered, use the full intake pipeline."
        )
    else:
        next_action = (
            "All required questions answered — confidence improved to medium. "
            "Use the full intake pipeline (analyze → brief → plan → source of truth) to proceed."
        )

    return ClarifiedIntakePreviewResponse(
        mode=req.intake.mode.value,
        answered_question_ids=answered_ids[:_MAX_UNIFIED_QUESTIONS],
        missing_required_questions=missing_required[:_MAX_UNIFIED_QUESTIONS],
        applied_answer_summary=applied_summaries[:_MAX_CQE_SUMMARIES],
        source_of_truth_preview=refined_sot,
        module_map_preview=refined_mm,
        multi_agent_plan=baseline.multi_agent_plan[:_MAX_UNIFIED_PLAN_STEPS],
        confidence_before=confidence_before,
        confidence_after=confidence_after,
        next_recommended_action=next_action,
        safety_notes=_UNIFIED_SAFETY_NOTES,
        limitations=_UNIFIED_LIMITATIONS,
    )


# ── Auto Source of Truth Draft from Intake v1 ────────────────────────────────

_MAX_SOT_DRAFT_REQUIREMENTS = 10
_MAX_SOT_DRAFT_ITEMS = 10

_SOT_DRAFT_SAFETY_NOTES: list[str] = [
    "Draft is read-only and not persisted until confirm_persist=True + project_id is provided.",
    "No LLM, provider, or cloud call is made during draft generation.",
    "Secret-like values are rejected from all fields before the draft is returned.",
    "No project, run, or tool_call is created during draft generation.",
]

_SOT_DRAFT_LIMITATIONS: list[str] = [
    "Requirements are inferred from goals only — no free-form requirement parsing.",
    "Confidence ceiling is 'medium' — high confidence requires human review.",
    "No document or repository parsing — project_path is a string hint only.",
    "Draft must be explicitly persisted via the /confirm endpoint with project_id.",
]


class SourceOfTruthDraftFromIntakeRequest(BaseModel):
    """Request to build a deterministic SoT draft from a CQE-answered intake.

    Pass ``confirm_persist=True`` and a non-empty ``project_id`` to have the
    /source-of-truth-draft/confirm endpoint persist the draft.
    The preview endpoint (/source-of-truth-draft) always ignores both fields.
    """

    intake: ClarifyingAnswersRequest
    project_id: Optional[str] = None
    confirm_persist: bool = False


class SourceOfTruthDraftValidation(BaseModel):
    valid: bool
    drift_risk: str = "low"        # low | medium | high | critical
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fields_populated: int = 0
    requirements_count: int = 0


class SourceOfTruthDraftFromIntakeResponse(BaseModel):
    mode: str
    source: str   # intake_idea | intake_document | intake_existing_project
    draft: SourceOfTruthUpsertRequest
    validation: SourceOfTruthDraftValidation
    persisted: bool = False
    project_id: Optional[str] = None
    version: Optional[int] = None
    confidence: str
    next_recommended_action: str
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


# ── SoT draft pure helpers ────────────────────────────────────────────────────


def _sot_draft_source_for_mode(mode: str) -> str:
    """Map unified intake mode to SoT source identifier."""
    if mode == "document":
        return "intake_document"
    if mode == "existing_project":
        return "intake_existing_project"
    return "intake_idea"


def _sot_draft_clean(text: str, max_chars: int = 150) -> str:
    """Truncate and strip text; return empty string if text is secret-like."""
    t = _cqe_short(text, max_chars)
    return "" if _sot_contains_secret(t) else t


def _sot_draft_clean_list(items: list[str], max_per: int = 150) -> list[str]:
    """Return a list with secret-like and empty entries removed, each truncated."""
    result: list[str] = []
    for item in items:
        cleaned = _sot_draft_clean(item, max_per)
        if cleaned:
            result.append(cleaned)
    return result


def _sot_draft_build_requirements(goals: list[str]) -> list[ProjectSourceOfTruthRequirement]:
    """Build stable REQ-001..REQ-N requirements from goals list.

    First three goals are marked 'must'; the rest are 'should'.
    Secret-like goals are silently skipped.
    """
    reqs: list[ProjectSourceOfTruthRequirement] = []
    for i, goal in enumerate(goals[:_MAX_SOT_DRAFT_REQUIREMENTS]):
        title = _sot_draft_clean(goal, 80)   # returns "" if secret-like
        if not title:
            continue
        description = _sot_draft_clean(goal, 150) or title
        priority = "must" if i < 3 else "should"
        reqs.append(
            ProjectSourceOfTruthRequirement(
                id=f"REQ-{i + 1:03d}",
                title=title,
                description=description,
                priority=priority,
                status="proposed",
            )
        )
    return reqs


def _sot_draft_validate(draft: SourceOfTruthUpsertRequest) -> SourceOfTruthDraftValidation:
    """Pure local validation of a SoT upsert request — no DB access."""
    errors: list[str] = []
    warnings: list[str] = []

    if not draft.product_summary.strip() and not draft.project_intent.strip():
        errors.append("product_summary or project_intent is required")

    if not draft.target_users:
        warnings.append("target_users is empty")

    if not draft.goals:
        warnings.append("goals is empty")

    if draft.requirements:
        seen: set[str] = set()
        for req in draft.requirements:
            if req.id in seen:
                errors.append(f"Duplicate requirement id: {req.id}")
            seen.add(req.id)
        if not any(r.priority == "must" for r in draft.requirements):
            warnings.append("No requirement with priority 'must' found")

    # Secret checks on list fields (should already be clean, belt-and-suspenders)
    for field_name, values in [
        ("goals", draft.goals),
        ("constraints", draft.constraints),
        ("risks", draft.risks),
        ("open_questions", draft.open_questions),
    ]:
        for i, val in enumerate(values):
            if isinstance(val, str) and _sot_contains_secret(val):
                errors.append(f"{field_name}[{i}] must not contain secret-like values")

    fields_populated = sum([
        bool(draft.product_name.strip()),
        bool(draft.product_summary.strip()),
        bool(draft.project_intent.strip()),
        bool(draft.target_users),
        bool(draft.goals),
        bool(draft.non_goals),
        bool(draft.requirements),
        bool(draft.constraints),
        bool(draft.risks),
        bool(draft.open_questions),
    ])

    drift_risk = "critical" if errors else "medium" if warnings else "low"
    return SourceOfTruthDraftValidation(
        valid=not errors,
        drift_risk=drift_risk,
        errors=errors,
        warnings=warnings,
        fields_populated=fields_populated,
        requirements_count=len(draft.requirements),
    )


def build_source_of_truth_draft_from_intake(
    req: SourceOfTruthDraftFromIntakeRequest,
) -> SourceOfTruthDraftFromIntakeResponse:
    """Build a deterministic, preview-only Source of Truth draft from a CQE intake.

    Pure helper — no DB, no provider calls, no file reads, no side effects.
    If ``confirm_persist=True`` the response sets persisted=False; the caller
    (routes.py confirm endpoint) is responsible for DB persistence.
    """
    # Step 1: run the CQE refiner to obtain the clarified preview
    clarified = refine_unified_intake_with_answers(req.intake)
    sot = clarified.source_of_truth_preview   # DraftSourceOfTruthPreview

    mode = clarified.mode
    source = _sot_draft_source_for_mode(mode)

    # Step 2: extract project intent from the original intake
    intake = req.intake.intake
    raw_intent = intake.title or intake.raw_input or sot.product_summary or ""
    project_intent = _sot_draft_clean(raw_intent, 300)

    # Step 3: clean all list fields (remove secrets, truncate)
    clean_goals = _sot_draft_clean_list(sot.goals[:_MAX_SOT_DRAFT_ITEMS])
    clean_non_goals = _sot_draft_clean_list(sot.non_goals[:_MAX_SOT_DRAFT_ITEMS])
    clean_target_users = _sot_draft_clean_list(sot.target_users[:_MAX_SOT_DRAFT_ITEMS], max_per=80)
    clean_constraints = _sot_draft_clean_list(sot.constraints[:_MAX_SOT_DRAFT_ITEMS])
    clean_risks = _sot_draft_clean_list(sot.risks[:_MAX_SOT_DRAFT_ITEMS])
    clean_open_questions = _sot_draft_clean_list(sot.open_questions[:_MAX_SOT_DRAFT_ITEMS])

    # Step 4: clean string fields (replace with safe fallback if secret-like)
    product_name = _sot_draft_clean(sot.product_name, 80) if sot.product_name else ""
    raw_summary = sot.product_summary or project_intent
    product_summary = _sot_draft_clean(raw_summary, 300) if raw_summary else ""
    if not product_summary and project_intent:
        product_summary = project_intent[:300]

    # Step 5: build requirements from cleaned goals (stable REQ-001 IDs)
    requirements = _sot_draft_build_requirements(clean_goals)

    # Step 6: construct the upsert request (Pydantic validators provide final guardrail)
    draft = SourceOfTruthUpsertRequest(
        product_name=product_name,
        product_summary=product_summary,
        project_intent=project_intent,
        target_users=clean_target_users,
        goals=clean_goals,
        non_goals=clean_non_goals,
        requirements=requirements,
        constraints=clean_constraints,
        risks=clean_risks,
        open_questions=clean_open_questions,
        source=source,
        status="draft",  # never "active" from intake — requires explicit operator promotion
    )

    # Step 7: validate
    validation = _sot_draft_validate(draft)

    # Step 8: build next recommended action
    if validation.valid and clarified.confidence_after == "medium":
        next_action = (
            "Source of Truth draft is valid with medium confidence. "
            "Review the draft, then submit to "
            "POST /api/project-intake/source-of-truth-draft/confirm with confirm_persist=true "
            "and a valid project_id to persist it."
        )
    elif not validation.valid:
        next_action = (
            f"Fix {len(validation.errors)} validation error(s) before persisting. "
            "Answer more clarifying questions to improve the draft."
        )
    else:
        next_action = (
            "Answer more required clarifying questions to improve confidence "
            "before persisting the draft."
        )

    return SourceOfTruthDraftFromIntakeResponse(
        mode=mode,
        source=source,
        draft=draft,
        validation=validation,
        persisted=False,
        project_id=None,
        version=None,
        confidence=clarified.confidence_after,
        next_recommended_action=next_action,
        safety_notes=_SOT_DRAFT_SAFETY_NOTES,
        limitations=_SOT_DRAFT_LIMITATIONS,
    )


# ── Auto Module Map Draft from Intake v1 ─────────────────────────────────────

_MAX_MM_DRAFT_MODULES = 12
_MAX_MM_DRAFT_PATHS = 12
_MAX_MM_DRAFT_REQS = 12
_MAX_MM_DRAFT_ITEMS = 8
_MAX_MM_DRAFT_MESSAGES = 20
_MAX_MA_PLAN_TASKS = 16
_MAX_MA_PLAN_MILESTONES = 6
_MAX_MA_PLAN_RISKS = 12
_MAX_MA_PLAN_LINKS = 8
_MAX_MA_PLAN_ITEMS = 8
_MAX_MA_PLAN_MESSAGES = 20

_MM_DRAFT_SAFETY_NOTES: list[str] = [
    "Draft is read-only and not persisted until confirm_persist=True + project_id is provided.",
    "No LLM, provider, or cloud call is made during module map draft generation.",
    "No repository files are scanned or read; project_path is only a string hint.",
    "No project, run, or tool_call is created during draft generation.",
]

_MM_DRAFT_LIMITATIONS: list[str] = [
    "Deterministic only — no provider/LLM reasoning.",
    "No document upload extraction.",
    "No repository file scanning or file content analysis.",
    "No automatic project creation or run creation.",
    "No agent execution from the intake screen.",
]

_MA_PLAN_SAFETY_NOTES: list[str] = [
    "Preview only; no project, run, step, or tool_call records are created.",
    "No provider/LLM calls are made.",
    "No repository files are read and no repository scan is performed.",
    "No patch, apply, rollback, guard, approval, or command execution is triggered.",
]

_MA_PLAN_LIMITATIONS: list[str] = [
    "Deterministic only — no provider/LLM reasoning.",
    "No document upload extraction.",
    "No repository file scanning or file content analysis.",
    "No automatic project creation or run creation.",
    "No agent execution from the intake screen.",
    "Plan is preview-only and does not create run steps.",
]

_MM_KEYWORD_MODULES: tuple[tuple[str, str, str, str, list[str]], ...] = (
    ("auth", "Auth / Access", "auth_access", "shared", ["auth", "login", "jwt", "session", "rbac", "role", "user"]),
    ("tickets", "Tickets Workflow", "tickets_workflow", "feature", ["ticket", "service desk", "helpdesk", "incident", "request"]),
    ("sla", "SLA Rules", "sla_rules", "feature", ["sla", "priority", "escalation", "deadline"]),
    ("notifications", "Notifications", "notifications", "feature", ["notification", "email", "sms", "push", "webhook"]),
    ("knowledge", "Knowledge Base", "knowledge_base", "feature", ["knowledge", "faq", "article", "wiki"]),
    ("reports", "Reports Dashboard", "reports_dashboard", "feature", ["report", "analytics", "dashboard", "metric"]),
    ("payments", "Payments / Billing", "payments_billing", "feature", ["payment", "billing", "invoice", "stripe", "subscription"]),
    ("uploads", "Uploads / Files", "uploads_files", "feature", ["upload", "file", "media", "storage", "image"]),
    ("integrations", "Integrations", "integrations", "feature", ["integration", "external", "api", "webhook"]),
    ("admin", "Admin", "admin", "feature", ["admin", "moderation", "settings", "backoffice"]),
)


class ModuleMapDraftFromIntakeRequest(BaseModel):
    """Request to build a deterministic Module Map draft from CQE intake."""

    intake: ClarifyingAnswersRequest
    source_of_truth_draft: Optional[dict] = None
    project_id: Optional[str] = None
    confirm_persist: bool = False


class ModuleMapDraftValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    module_count: int = 0
    requirement_coverage_count: int = 0


class ModuleMapDraftFromIntakeResponse(BaseModel):
    persisted: bool = False
    project_id: Optional[str] = None
    module_map_id: Optional[str] = None
    version: Optional[int] = None
    draft: ProjectModuleMapUpsertRequest
    validation: ModuleMapDraftValidation
    inferred_stack: list[str] = Field(default_factory=list)
    applied_answer_summary: list[str] = Field(default_factory=list)
    missing_required_questions: list[ClarifyingAnswerGap] = Field(default_factory=list)
    next_recommended_action: str
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _mm_slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug[:48] or "module"


def _mm_module_id(slug: str) -> str:
    return f"mod_{slug[:40]}"


def _mm_source_for_mode(mode: str) -> str:
    if mode == "document":
        return "intake_document"
    if mode == "existing_project":
        return "intake_existing_project"
    return "intake_idea"


def _mm_text(req: ModuleMapDraftFromIntakeRequest) -> str:
    intake = req.intake.intake
    answers = " ".join(a.answer for a in req.intake.answers if not a.skipped)
    return " ".join([
        intake.title or "",
        intake.raw_input or "",
        intake.document_excerpt or "",
        intake.project_path or "",
        " ".join(intake.known_stack),
        " ".join(intake.constraints),
        intake.desired_outcome or "",
        answers,
    ])


def _mm_has_secret_like_content(req: ModuleMapDraftFromIntakeRequest) -> bool:
    return _module_map_contains_secret(_mm_text(req))


def _mm_has_unsafe_path_hint(req: ModuleMapDraftFromIntakeRequest) -> bool:
    text = _mm_text(req).lower()
    unsafe_markers = (".env", "credentials", "private_key", "private-key", "secrets/", "secret.key")
    return any(marker in text for marker in unsafe_markers)


def _mm_bounded(items: list[str], limit: int = _MAX_MM_DRAFT_ITEMS, max_chars: int = 150) -> list[str]:
    result: list[str] = []
    for item in items:
        cleaned = _cqe_short(str(item), max_chars)
        if cleaned and not _module_map_contains_secret(cleaned):
            result.append(cleaned)
    return result[:limit]


def _mm_extract_sot_requirements(source_of_truth_draft: Optional[dict]) -> list[dict]:
    if not source_of_truth_draft:
        return []
    raw = source_of_truth_draft.get("requirements", [])
    if not isinstance(raw, list):
        return []
    result: list[dict] = []
    for item in raw[:24]:
        if not isinstance(item, dict):
            continue
        req_id = str(item.get("id", "")).strip()
        title = str(item.get("title", "")).strip()
        description = str(item.get("description", "")).strip()
        tags = item.get("tags", [])
        if req_id:
            result.append({
                "id": req_id[:64],
                "title": _cqe_short(title, 120),
                "description": _cqe_short(description, 160),
                "tags": [str(t)[:50] for t in tags[:8]] if isinstance(tags, list) else [],
            })
    return result


def _mm_req_ids_for_slug(slug: str, requirements: list[dict]) -> list[str]:
    if not requirements:
        return []
    slug_terms = set(slug.replace("_", " ").split())
    matched: list[str] = []
    for req in requirements:
        haystack = " ".join([
            str(req.get("title", "")),
            str(req.get("description", "")),
            " ".join(req.get("tags", [])),
        ]).lower()
        if slug_terms and any(term in haystack for term in slug_terms):
            matched.append(str(req["id"]))
    return matched[:_MAX_MM_DRAFT_REQS]


def _mm_round_robin_req_ids(index: int, requirements: list[dict]) -> list[str]:
    if not requirements:
        return []
    if index < len(requirements):
        return [str(requirements[index]["id"])]
    return []


def _mm_base_module(
    name: str,
    slug: str,
    module_type: str,
    description: str,
    *,
    responsibilities: Optional[list[str]] = None,
    paths: Optional[list[str]] = None,
    key_files: Optional[list[str]] = None,
    related_requirements: Optional[list[str]] = None,
    test_hints: Optional[list[str]] = None,
    risks: Optional[list[str]] = None,
    confidence: str = "medium",
) -> ProjectModuleMapItem:
    return ProjectModuleMapItem(
        id=_mm_module_id(slug),
        name=name,
        slug=slug,
        description=_cqe_short(description, 220),
        module_type=module_type,
        responsibilities=_mm_bounded(responsibilities or []),
        paths=_mm_bounded(paths or [], _MAX_MM_DRAFT_PATHS, 100),
        key_files=_mm_bounded(key_files or [], _MAX_MM_DRAFT_PATHS, 100),
        related_requirements=_mm_bounded(related_requirements or [], _MAX_MM_DRAFT_REQS, 80),
        test_hints=_mm_bounded(test_hints or []),
        risks=_mm_bounded(risks or []),
        confidence=confidence,
    )


def _mm_dedup_modules(modules: list[ProjectModuleMapItem]) -> list[ProjectModuleMapItem]:
    deduped: list[ProjectModuleMapItem] = []
    seen: set[str] = set()
    for module in modules:
        if module.slug in seen:
            continue
        seen.add(module.slug)
        deduped.append(module)
    return deduped[:_MAX_MM_DRAFT_MODULES]


def _mm_common_stack_modules(
    text: str,
    stack: list[str],
    requirements: list[dict],
) -> list[ProjectModuleMapItem]:
    modules: list[ProjectModuleMapItem] = []
    lower = (text + " " + " ".join(stack)).lower()

    if any(k in lower for k in ["react", "vue", "angular", "next", "svelte", "frontend", "ui", "web"]):
        modules.append(_mm_base_module(
            "Frontend UI", "frontend_ui", "frontend", "Screens, components, client state, and API integration.",
            responsibilities=["Render operator/user workflows", "Connect UI to API contracts", "Handle loading and validation states"],
            paths=["frontend/src"],
            key_files=["frontend/src/pages", "frontend/src/components"],
            related_requirements=_mm_req_ids_for_slug("frontend ui", requirements) or _mm_round_robin_req_ids(0, requirements),
            test_hints=["npx tsc --noEmit", "npm run build", "browser smoke tests"],
            risks=["UI changes can hide important workflow state"],
        ))

    if any(k in lower for k in ["fastapi", "django", "flask", "express", "node", "backend", "api", "server"]):
        modules.append(_mm_base_module(
            "Backend API", "backend_api", "backend", "API routes, validation, orchestration boundaries, and business logic.",
            responsibilities=["Expose stable API contracts", "Validate inputs", "Preserve safety gates"],
            paths=["backend/src"],
            key_files=["backend/src/api/routes.py"],
            related_requirements=_mm_req_ids_for_slug("backend api", requirements) or _mm_round_robin_req_ids(1, requirements),
            test_hints=["pytest backend tests", "API contract tests"],
            risks=["Backend changes can affect persistence and workflow safety"],
        ))

    if any(k in lower for k in ["postgres", "mysql", "sqlite", "mongo", "redis", "database", "schema", "db"]):
        modules.append(_mm_base_module(
            "Database / Schema", "database_schema", "database", "Persistence model, schema, and data integrity boundaries.",
            responsibilities=["Store durable state", "Protect migrations and schema changes", "Preserve audit data"],
            paths=["backend/src/storage"],
            key_files=["backend/src/storage"],
            related_requirements=_mm_req_ids_for_slug("database schema", requirements) or _mm_round_robin_req_ids(2, requirements),
            test_hints=["storage tests", "migration/backup contract checks"],
            risks=["Schema changes require explicit review and backup planning"],
        ))

    return modules


def _mm_keyword_modules(text: str, requirements: list[dict]) -> list[ProjectModuleMapItem]:
    lower = text.lower()
    modules: list[ProjectModuleMapItem] = []
    for index, (_key, name, slug, module_type, keywords) in enumerate(_MM_KEYWORD_MODULES):
        if not any(keyword in lower for keyword in keywords):
            continue
        modules.append(_mm_base_module(
            name,
            slug,
            module_type,
            f"Conceptual module inferred from intake keywords: {', '.join(keywords[:3])}.",
            responsibilities=[f"Own {name.lower()} behavior", "Keep requirements linked to module boundaries"],
            related_requirements=_mm_req_ids_for_slug(slug, requirements) or _mm_round_robin_req_ids(index, requirements),
            test_hints=[f"{name} behavior tests", "module-level regression tests"],
            risks=[f"{name} changes need human review"],
        ))
    return modules


def _mm_modules_from_preview(
    preview: DraftModuleMapPreview,
    requirements: list[dict],
) -> list[ProjectModuleMapItem]:
    modules: list[ProjectModuleMapItem] = []
    for index, raw in enumerate(preview.modules[:_MAX_MM_DRAFT_MODULES]):
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name", "")).strip() or f"Module {index + 1}"
        module_type = str(raw.get("type", raw.get("module_type", "feature"))).strip() or "feature"
        slug = _mm_slugify(str(raw.get("slug", "")) or name)
        description = str(raw.get("description", "")).strip() or f"Conceptual module: {name}"
        modules.append(_mm_base_module(
            name=name[:80],
            slug=slug,
            module_type=module_type,
            description=description,
            responsibilities=[description],
            related_requirements=_mm_req_ids_for_slug(slug, requirements) or _mm_round_robin_req_ids(index, requirements),
            test_hints=[f"{name} tests", "module regression tests"],
            risks=["Module boundaries are inferred from intake and require review"],
            confidence=preview.confidence if preview.confidence in {"low", "medium", "high"} else "medium",
        ))
    return modules


def _mm_existing_project_fallback_modules(
    req: UnifiedIntakeRequest,
    text: str,
    requirements: list[dict],
) -> list[ProjectModuleMapItem]:
    modules = [
        _mm_base_module(
            "Frontend UI", "frontend_ui", "frontend", "Existing frontend/user interface layer.",
            responsibilities=["Preserve existing UX", "Plan UI changes incrementally"],
            paths=["frontend/src"],
            key_files=["frontend/src"],
            related_requirements=_mm_round_robin_req_ids(0, requirements),
            test_hints=["frontend typecheck/build"],
            risks=["Existing UI conventions are unknown without repository inventory"],
        ),
        _mm_base_module(
            "Backend API", "backend_api", "backend", "Existing backend/API layer.",
            responsibilities=["Preserve existing API behavior", "Validate changes through tests"],
            paths=["backend/src"],
            key_files=["backend/src"],
            related_requirements=_mm_round_robin_req_ids(1, requirements),
            test_hints=["backend test suite"],
            risks=["Backend boundaries are unknown without repository inventory"],
        ),
        _mm_base_module(
            "Database / Schema", "database_schema", "database", "Existing persistence and schema layer.",
            responsibilities=["Protect data model", "Avoid unreviewed migrations"],
            paths=["backend/src/storage"],
            key_files=["backend/src/storage"],
            related_requirements=_mm_round_robin_req_ids(2, requirements),
            test_hints=["storage and migration tests"],
            risks=["Schema changes are high risk and require explicit operator review"],
        ),
        _mm_base_module(
            "Tests / Quality", "tests_quality", "tests", "Existing test and verification layer.",
            responsibilities=["Locate test commands", "Track baseline test health"],
            paths=["tests"],
            key_files=["tests"],
            related_requirements=_mm_round_robin_req_ids(3, requirements),
            test_hints=["run configured test command"],
            risks=["Test command may be missing or stale"],
        ),
        _mm_base_module(
            "Deployment / Config", "deployment_config", "infrastructure", "Existing deployment and runtime configuration.",
            responsibilities=["Document deployment assumptions", "Keep secrets out of context"],
            paths=["config"],
            key_files=[],
            related_requirements=_mm_round_robin_req_ids(4, requirements),
            test_hints=["deployment smoke checks when configured"],
            risks=["Do not modify env/secrets/deployment files without explicit approval"],
        ),
    ]
    return modules + _mm_keyword_modules(text, requirements)


def _mm_validate_draft(
    draft: ProjectModuleMapUpsertRequest,
    req: ModuleMapDraftFromIntakeRequest,
) -> ModuleMapDraftValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing_fields: list[str] = []

    if not draft.modules:
        errors.append("Module map draft must contain at least one module.")

    if len(draft.modules) > _MAX_MM_DRAFT_MODULES:
        errors.append(f"Too many modules: {len(draft.modules)} (max {_MAX_MM_DRAFT_MODULES}).")

    if _mm_has_secret_like_content(req):
        errors.append("Intake contains secret-like content; remove credentials/tokens before generating a Module Map draft.")

    if _mm_has_unsafe_path_hint(req):
        errors.append("Intake contains unsafe secret/path hints such as .env, credentials, private_key, or secrets.")

    covered: set[str] = set()
    for module in draft.modules:
        if not module.name.strip():
            errors.append(f"Module {module.id!r} is missing name.")
        if not module.description.strip():
            missing_fields.append(f"{module.slug}.description")
        if not module.responsibilities:
            missing_fields.append(f"{module.slug}.responsibilities")
        if not module.related_requirements:
            warnings.append(f"Module {module.name} has no linked requirements.")
        if not module.test_hints:
            warnings.append(f"Module {module.name} has no test hints.")
        for path in list(module.paths) + list(module.key_files):
            ok, reason = _module_map_path_is_safe(path)
            if not ok:
                errors.append(reason)
        covered.update(module.related_requirements)

    intake = req.intake.intake
    if intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        if not intake.known_stack:
            warnings.append("Existing project intake has no known_stack; module draft is conceptual.")
        answer_map = {a.question_id: a for a in req.intake.answers}
        if not _cqe_answered("cq-ep-4", answer_map):
            warnings.append("Existing project intake has no confirmed test command.")

    if not covered:
        warnings.append("No Source of Truth requirement links were inferred.")

    confidence = "low" if errors else "medium"
    return ModuleMapDraftValidation(
        valid=not errors,
        errors=errors[:_MAX_MM_DRAFT_MESSAGES],
        warnings=warnings[:_MAX_MM_DRAFT_MESSAGES],
        missing_fields=missing_fields[:_MAX_MM_DRAFT_MESSAGES],
        confidence=confidence,
        module_count=len(draft.modules),
        requirement_coverage_count=len(covered),
    )


def build_module_map_draft_from_intake(
    req: ModuleMapDraftFromIntakeRequest,
) -> ModuleMapDraftFromIntakeResponse:
    """Build a deterministic Module Map draft from CQE intake.

    Pure helper — no DB, no provider calls, no file reads, no project/run/tool_call
    creation, no repository scan.  The /confirm route handles optional explicit
    persistence using existing Module Map storage.
    """
    clarified = refine_unified_intake_with_answers(req.intake)
    intake = req.intake.intake
    requirements = _mm_extract_sot_requirements(req.source_of_truth_draft)
    text = _mm_text(req)
    source = _mm_source_for_mode(clarified.mode)

    modules = _mm_modules_from_preview(clarified.module_map_preview, requirements)
    modules.extend(_mm_common_stack_modules(text, clarified.module_map_preview.inferred_stack, requirements))
    modules.extend(_mm_keyword_modules(text, requirements))

    if intake.mode == UnifiedIntakeMode.IDEA:
        modules.extend(_mm_common_stack_modules(text + " web backend database", intake.known_stack, requirements))
        if any("test" in item.lower() or "qa" in item.lower() for item in clarified.applied_answer_summary + [text]):
            modules.append(_mm_base_module(
                "Tests / QA", "tests_quality", "tests", "Verification strategy and regression coverage.",
                responsibilities=["Define verification commands", "Track acceptance criteria coverage"],
                related_requirements=_mm_round_robin_req_ids(4, requirements),
                test_hints=["unit tests", "typecheck/build", "smoke tests"],
                risks=["Insufficient tests can hide intake assumptions"],
            ))
    elif intake.mode == UnifiedIntakeMode.DOCUMENT:
        if not modules:
            modules.append(_mm_base_module(
                "Requirements Layer", "requirements_layer", "docs", "Normalized requirements from the intake document.",
                responsibilities=["Cluster requirements", "Track ambiguity and acceptance criteria"],
                related_requirements=[r["id"] for r in requirements[:_MAX_MM_DRAFT_REQS]],
                test_hints=["requirement coverage review"],
                risks=["Architecture is ambiguous until requirements are confirmed"],
                confidence="low",
            ))
    else:
        if len(modules) < 4:
            modules.extend(_mm_existing_project_fallback_modules(intake, text, requirements))
        answer_map = {a.question_id: a for a in req.intake.answers}
        protected = _cqe_answered("cq-ep-5", answer_map)
        if protected:
            modules.insert(0, _mm_base_module(
                "Protected Areas", "protected_areas", "shared", "Operator-declared modules/files that require extra caution.",
                responsibilities=["Keep protected areas visible before planning patches"],
                related_requirements=[],
                test_hints=["manual review before patch proposal"],
                risks=[f"Protected modules: {_cqe_short(protected, 120)}"],
                confidence="medium",
            ))

    modules = _mm_dedup_modules(modules)
    if not modules and requirements:
        modules.append(_mm_base_module(
            "Core Product", "core_product", "feature", "Core product behavior inferred from Source of Truth requirements.",
            responsibilities=["Own initial requirement coverage"],
            related_requirements=[r["id"] for r in requirements[:_MAX_MM_DRAFT_REQS]],
            test_hints=["requirement-level tests"],
            risks=["Module boundaries require human review"],
            confidence="low",
        ))

    draft = ProjectModuleMapUpsertRequest(
        modules=modules,
        ignored_paths=[],
        scan_summary=(
            "Deterministic Module Map draft from unified intake only. "
            "No repository scan, no file reads, no provider calls."
        ),
        source=source,
        status="draft",
    )

    validation = _mm_validate_draft(draft, req)

    if validation.valid and validation.requirement_coverage_count > 0:
        next_action = (
            "Module Map draft is valid and linked to Source of Truth requirements. "
            "Review it, then submit to /api/project-intake/module-map-draft/confirm "
            "with confirm_persist=true and a valid project_id to persist."
        )
    elif validation.valid:
        next_action = (
            "Module Map draft is valid but has no requirement links. "
            "Review with a Source of Truth draft before persisting."
        )
    else:
        next_action = (
            f"Fix {len(validation.errors)} validation error(s) before persisting the Module Map draft."
        )

    return ModuleMapDraftFromIntakeResponse(
        persisted=False,
        project_id=None,
        module_map_id=None,
        version=None,
        draft=draft,
        validation=validation,
        inferred_stack=clarified.module_map_preview.inferred_stack[:8],
        applied_answer_summary=clarified.applied_answer_summary[:_MAX_CQE_SUMMARIES],
        missing_required_questions=clarified.missing_required_questions[:_MAX_UNIFIED_QUESTIONS],
        next_recommended_action=next_action,
        safety_notes=_MM_DRAFT_SAFETY_NOTES,
        limitations=_MM_DRAFT_LIMITATIONS,
    )


# ── Multi-Agent Plan from Intake v1 ─────────────────────────────────────────


class MultiAgentPlanFromIntakeRequest(BaseModel):
    intake: UnifiedIntakeRequest
    answers: list[ClarifyingAnswer] = Field(default_factory=list)
    source_of_truth_draft: Optional[dict] = None
    module_map_draft: Optional[dict] = None


class MultiAgentPlanRisk(BaseModel):
    id: str
    severity: str
    description: str
    affected_modules: list[str] = Field(default_factory=list)
    mitigation: str


class MultiAgentPlanTask(BaseModel):
    id: str
    title: str
    description: str
    agent_role: str
    target_modules: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    manual_approval_required: bool = False
    provider_allowed: bool = False


class MultiAgentPlanMilestone(BaseModel):
    id: str
    title: str
    goal: str
    task_ids: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)


class MultiAgentPlanValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    readiness: str = "draft"


class MultiAgentPlanFromIntakeResponse(BaseModel):
    mode: str
    plan_title: str
    plan_summary: str
    tasks: list[MultiAgentPlanTask] = Field(default_factory=list)
    milestones: list[MultiAgentPlanMilestone] = Field(default_factory=list)
    risks: list[MultiAgentPlanRisk] = Field(default_factory=list)
    recommended_first_action: str
    recommended_first_task_id: Optional[str] = None
    validation: MultiAgentPlanValidation
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def _ma_text(req: MultiAgentPlanFromIntakeRequest) -> str:
    answers = " ".join(a.answer for a in req.answers if not a.skipped)
    intake = req.intake
    return " ".join([
        intake.title or "",
        intake.raw_input or "",
        intake.document_excerpt or "",
        intake.project_path or "",
        " ".join(intake.known_stack),
        " ".join(intake.constraints),
        intake.desired_outcome or "",
        answers,
    ])


def _ma_has_secret_like_content(req: MultiAgentPlanFromIntakeRequest) -> bool:
    text = _ma_text(req)
    return _sot_contains_secret(text) or _module_map_contains_secret(text)


def _ma_bounded(items: list[str], limit: int = _MAX_MA_PLAN_ITEMS, max_chars: int = 160) -> list[str]:
    result: list[str] = []
    for item in items:
        cleaned = _cqe_short(str(item), max_chars)
        if cleaned and not _sot_contains_secret(cleaned) and not _module_map_contains_secret(cleaned):
            result.append(cleaned)
    return result[:limit]


def _ma_extract_module_map_modules(module_map_draft: Optional[dict]) -> list[dict]:
    if not module_map_draft:
        return []
    raw_modules = module_map_draft.get("modules", [])
    if not isinstance(raw_modules, list):
        return []
    modules: list[dict] = []
    for raw in raw_modules[:_MAX_MM_DRAFT_MODULES]:
        if not isinstance(raw, dict):
            continue
        slug = _mm_slugify(str(raw.get("slug", "") or raw.get("name", "") or "module"))
        name = _cqe_short(str(raw.get("name", "") or slug.replace("_", " ").title()), 80)
        module_type = _cqe_short(str(raw.get("module_type", raw.get("type", "feature"))), 40)
        related = raw.get("related_requirements", [])
        test_hints = raw.get("test_hints", [])
        risks = raw.get("risks", [])
        modules.append({
            "slug": slug,
            "name": name,
            "module_type": module_type,
            "related_requirements": _ma_bounded([str(item) for item in related], _MAX_MA_PLAN_LINKS, 80) if isinstance(related, list) else [],
            "test_hints": _ma_bounded([str(item) for item in test_hints], _MAX_MA_PLAN_ITEMS, 120) if isinstance(test_hints, list) else [],
            "risks": _ma_bounded([str(item) for item in risks], _MAX_MA_PLAN_ITEMS, 120) if isinstance(risks, list) else [],
        })
    return modules


def _ma_module_slugs(modules: list[dict], *keywords: str) -> list[str]:
    selected: list[str] = []
    lowered = [keyword.lower() for keyword in keywords]
    for module in modules:
        haystack = " ".join([
            str(module.get("slug", "")),
            str(module.get("name", "")),
            str(module.get("module_type", "")),
        ]).lower()
        if any(keyword in haystack for keyword in lowered):
            selected.append(str(module["slug"]))
    return selected[:_MAX_MA_PLAN_LINKS]


def _ma_requirement_ids(requirements: list[dict], *keywords: str) -> list[str]:
    if not requirements:
        return []
    selected: list[str] = []
    lowered = [keyword.lower() for keyword in keywords]
    for req in requirements:
        haystack = " ".join([
            str(req.get("id", "")),
            str(req.get("title", "")),
            str(req.get("description", "")),
            " ".join(req.get("tags", [])),
        ]).lower()
        if not lowered or any(keyword in haystack for keyword in lowered):
            selected.append(str(req["id"]))
    return selected[:_MAX_MA_PLAN_LINKS]


def _ma_task(
    task_id: str,
    title: str,
    description: str,
    agent_role: str,
    *,
    target_modules: Optional[list[str]] = None,
    requirement_ids: Optional[list[str]] = None,
    depends_on: Optional[list[str]] = None,
    expected_outputs: Optional[list[str]] = None,
    validation_steps: Optional[list[str]] = None,
    risk_level: str = "medium",
    manual_approval_required: bool = False,
) -> MultiAgentPlanTask:
    return MultiAgentPlanTask(
        id=task_id,
        title=_cqe_short(title, 100),
        description=_cqe_short(description, 240),
        agent_role=agent_role,
        target_modules=_ma_bounded(target_modules or [], _MAX_MA_PLAN_LINKS, 80),
        requirement_ids=_ma_bounded(requirement_ids or [], _MAX_MA_PLAN_LINKS, 80),
        depends_on=_ma_bounded(depends_on or [], _MAX_MA_PLAN_LINKS, 80),
        expected_outputs=_ma_bounded(expected_outputs or [], _MAX_MA_PLAN_ITEMS, 140),
        validation_steps=_ma_bounded(validation_steps or [], _MAX_MA_PLAN_ITEMS, 140),
        risk_level=risk_level,
        manual_approval_required=manual_approval_required,
        provider_allowed=False,
    )


def _ma_sensitive_modules(modules: list[dict]) -> list[str]:
    return _ma_module_slugs(
        modules,
        "auth",
        "access",
        "database",
        "schema",
        "deployment",
        "config",
        "provider",
        "billing",
        "payment",
        "security",
    )


def _ma_dedup_tasks(tasks: list[MultiAgentPlanTask]) -> list[MultiAgentPlanTask]:
    result: list[MultiAgentPlanTask] = []
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            continue
        seen.add(task.id)
        result.append(task)
    return result[:_MAX_MA_PLAN_TASKS]


def _ma_plan_validation(
    req: MultiAgentPlanFromIntakeRequest,
    tasks: list[MultiAgentPlanTask],
    requirements: list[dict],
    modules: list[dict],
) -> MultiAgentPlanValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []

    if not tasks:
        errors.append("Multi-agent plan must include at least one task.")
    if _ma_has_secret_like_content(req):
        errors.append("Intake contains secret-like content; remove credentials/tokens before building the plan.")
    if not requirements:
        warnings.append("No Source of Truth draft was provided; requirement targeting is conceptual.")
        missing.append("source_of_truth_draft")
    if not modules:
        warnings.append("No Module Map draft was provided; module targeting is conceptual.")
        missing.append("module_map_draft")
    if requirements and not any(task.requirement_ids for task in tasks):
        warnings.append("No requirement ids were attached to plan tasks.")
    if modules and not any(task.target_modules for task in tasks):
        warnings.append("No module slugs were attached to plan tasks.")
    if any(not task.validation_steps for task in tasks):
        warnings.append("One or more tasks have no validation steps.")
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT and not req.intake.known_stack:
        warnings.append("Existing project intake has no known_stack; agent targeting is lower confidence.")
        missing.append("known_stack")
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        answer_map = {a.question_id: a for a in req.answers}
        if not _cqe_answered("cq-ep-4", answer_map):
            warnings.append("Existing project intake has no confirmed test command.")
            missing.append("test_command")

    readiness = "blocked" if errors else ("needs_review" if warnings or missing else "ready_for_operator_review")
    return MultiAgentPlanValidation(
        valid=not errors,
        errors=errors[:_MAX_MA_PLAN_MESSAGES],
        warnings=warnings[:_MAX_MA_PLAN_MESSAGES],
        missing_inputs=_ma_bounded(missing, _MAX_MA_PLAN_MESSAGES, 80),
        readiness=readiness,
    )


def _ma_milestones(tasks: list[MultiAgentPlanTask]) -> list[MultiAgentPlanMilestone]:
    groups = [
        ("m-context", "Context Confirmation", "Confirm project truth, module boundaries, and safe starting point."),
        ("m-architecture", "Architecture Alignment", "Align requirements with modules, contracts, and implementation sequence."),
        ("m-implementation", "Controlled Implementation", "Prepare low-risk implementation tasks for the controlled development loop."),
        ("m-verification", "Verification and Delivery", "Validate tests, review risks, and prepare delivery report."),
    ]
    milestones: list[MultiAgentPlanMilestone] = []
    for idx, (mid, title, goal) in enumerate(groups):
        chunk = [task.id for task in tasks if task.agent_role in {
            "product_analyst",
            "architect",
            "backend_agent",
            "frontend_agent",
            "database_agent",
            "qa_agent",
            "security_guard_agent",
            "devops_agent",
            "delivery_reviewer_agent",
        }]
        if idx == 0:
            task_ids = [task.id for task in tasks[:3]]
        elif idx == 1:
            task_ids = [task.id for task in tasks if task.agent_role in {"architect", "database_agent", "security_guard_agent"}]
        elif idx == 2:
            task_ids = [task.id for task in tasks if task.agent_role in {"backend_agent", "frontend_agent", "devops_agent"}]
        else:
            task_ids = [task.id for task in tasks if task.agent_role in {"qa_agent", "delivery_reviewer_agent"}] or chunk[-2:]
        if not task_ids:
            continue
        milestones.append(MultiAgentPlanMilestone(
            id=mid,
            title=title,
            goal=goal,
            task_ids=task_ids[:_MAX_MA_PLAN_LINKS],
            exit_criteria=[
                "Operator-visible outputs are reviewed.",
                "No execution occurs from intake preview.",
                "Risks and required approvals are explicit.",
            ],
        ))
    return milestones[:_MAX_MA_PLAN_MILESTONES]


def _ma_risks(req: MultiAgentPlanFromIntakeRequest, modules: list[dict], requirements: list[dict]) -> list[MultiAgentPlanRisk]:
    risks: list[MultiAgentPlanRisk] = []
    sensitive = _ma_sensitive_modules(modules)
    if sensitive:
        risks.append(MultiAgentPlanRisk(
            id="risk-sensitive-modules",
            severity="high",
            description="Plan touches sensitive modules such as auth, database, deployment, provider, or billing areas.",
            affected_modules=sensitive[:_MAX_MA_PLAN_LINKS],
            mitigation="Require manual approval before patch proposals or apply operations for these modules.",
        ))
    if not requirements:
        risks.append(MultiAgentPlanRisk(
            id="risk-missing-sot",
            severity="medium",
            description="No Source of Truth draft is attached, so requirement coverage is conceptual.",
            affected_modules=[],
            mitigation="Confirm or attach a Source of Truth draft before starting implementation.",
        ))
    if not modules:
        risks.append(MultiAgentPlanRisk(
            id="risk-missing-module-map",
            severity="medium",
            description="No Module Map draft is attached, so module ownership and test targeting are conceptual.",
            affected_modules=[],
            mitigation="Build and review a Module Map draft before creating a development run.",
        ))
    if req.intake.mode == UnifiedIntakeMode.DOCUMENT and not requirements:
        risks.append(MultiAgentPlanRisk(
            id="risk-document-ambiguity",
            severity="medium",
            description="Document intake needs normalized requirements and acceptance criteria before implementation.",
            affected_modules=[],
            mitigation="Run requirement normalization and acceptance criteria validation first.",
        ))
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        risks.append(MultiAgentPlanRisk(
            id="risk-existing-project-context",
            severity="medium",
            description="Existing project work needs repository inventory and test discovery before patch planning.",
            affected_modules=[],
            mitigation="Treat inventory and test discovery as future tasks only; do not scan from intake preview.",
        ))
    return risks[:_MAX_MA_PLAN_RISKS]


def build_multi_agent_plan_from_intake(
    req: MultiAgentPlanFromIntakeRequest,
) -> MultiAgentPlanFromIntakeResponse:
    """Build a deterministic, preview-only multi-agent development plan."""
    clarified = refine_unified_intake_with_answers(ClarifyingAnswersRequest(
        intake=req.intake,
        answers=req.answers,
    ))
    requirements = _mm_extract_sot_requirements(req.source_of_truth_draft)
    modules = _ma_extract_module_map_modules(req.module_map_draft)
    text = _ma_text(req).lower()

    all_req_ids = [str(item["id"]) for item in requirements[:_MAX_MA_PLAN_LINKS]]
    frontend_modules = _ma_module_slugs(modules, "frontend", "ui")
    backend_modules = _ma_module_slugs(modules, "backend", "api")
    database_modules = _ma_module_slugs(modules, "database", "schema")
    qa_modules = _ma_module_slugs(modules, "test", "quality", "qa")
    sensitive_modules = _ma_sensitive_modules(modules)

    tasks: list[MultiAgentPlanTask] = [
        _ma_task(
            "task-context-confirmation",
            "Confirm Source of Truth and intake assumptions",
            "Review answered questions, missing inputs, Source of Truth status, and Module Map readiness before implementation planning.",
            "product_analyst",
            target_modules=[],
            requirement_ids=all_req_ids,
            expected_outputs=["confirmed assumptions", "open questions list", "implementation readiness note"],
            validation_steps=["operator reviews Source of Truth draft", "operator reviews Module Map draft"],
            risk_level="low",
        )
    ]

    if req.intake.mode == UnifiedIntakeMode.DOCUMENT:
        tasks.append(_ma_task(
            "task-requirement-normalization",
            "Normalize requirements and acceptance criteria",
            "Turn document requirements into validated requirements, acceptance criteria, and unresolved questions.",
            "product_analyst",
            requirement_ids=all_req_ids,
            expected_outputs=["normalized requirements", "acceptance criteria review", "ambiguity list"],
            validation_steps=["check every must-have requirement has acceptance criteria", "review ambiguous requirements"],
            risk_level="medium",
        ))

    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        tasks.extend([
            _ma_task(
                "task-repository-inventory",
                "Plan repository inventory",
                "Define a future read-only inventory pass for modules, entrypoints, tests, and risky areas.",
                "architect",
                target_modules=[str(m["slug"]) for m in modules[:_MAX_MA_PLAN_LINKS]],
                requirement_ids=all_req_ids,
                expected_outputs=["inventory checklist", "module-to-file hypothesis", "risk areas list"],
                validation_steps=["operator confirms inventory scope", "no files are read from intake preview"],
                risk_level="medium",
            ),
            _ma_task(
                "task-test-discovery",
                "Plan test discovery",
                "Define how a future controlled run should discover test commands and baseline verification.",
                "qa_agent",
                target_modules=qa_modules,
                requirement_ids=all_req_ids,
                expected_outputs=["candidate test commands", "baseline verification plan"],
                validation_steps=["operator confirms safe test commands", "tests remain future workflow"],
                risk_level="medium",
            ),
        ])

    tasks.append(_ma_task(
        "task-architecture-alignment",
        "Align architecture and module boundaries",
        "Map requirements to modules, dependencies, contracts, and controlled implementation order.",
        "architect",
        target_modules=[str(m["slug"]) for m in modules[:_MAX_MA_PLAN_LINKS]],
        requirement_ids=all_req_ids,
        depends_on=["task-context-confirmation"],
        expected_outputs=["module responsibility map", "dependency notes", "implementation sequence"],
        validation_steps=["check requirement coverage", "check sensitive modules are marked for approval"],
        risk_level="medium",
    ))

    if backend_modules or any(k in text for k in ["backend", "api", "server", "fastapi", "django", "express"]):
        tasks.append(_ma_task(
            "task-backend-contracts",
            "Plan backend contracts and service changes",
            "Prepare backend/API work units as preview-only planning notes.",
            "backend_agent",
            target_modules=backend_modules,
            requirement_ids=_ma_requirement_ids(requirements, "api", "backend", "ticket", "auth") or all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["API contract checklist", "backend task breakdown"],
            validation_steps=["backend tests identified", "guard/proposal path remains future workflow"],
            risk_level="medium",
        ))

    if frontend_modules or any(k in text for k in ["frontend", "ui", "react", "vue", "dashboard", "screen"]):
        tasks.append(_ma_task(
            "task-frontend-workflow",
            "Plan frontend workflow and UI changes",
            "Prepare frontend/UI work units with validation expectations and no hidden mutations.",
            "frontend_agent",
            target_modules=frontend_modules,
            requirement_ids=_ma_requirement_ids(requirements, "frontend", "ui", "dashboard") or all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["UI workflow checklist", "component/page task breakdown"],
            validation_steps=["typecheck/build planned", "browser smoke coverage considered"],
            risk_level="medium",
        ))

    if database_modules or any(k in text for k in ["database", "schema", "postgres", "sqlite", "migration"]):
        tasks.append(_ma_task(
            "task-database-safety",
            "Plan database and schema safety",
            "Identify persistence/schema work and required backup/review gates before any future migration work.",
            "database_agent",
            target_modules=database_modules,
            requirement_ids=_ma_requirement_ids(requirements, "database", "schema", "data") or all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["schema risk notes", "backup/restore checklist", "data validation plan"],
            validation_steps=["backup contract reviewed", "schema changes require approval"],
            risk_level="high",
            manual_approval_required=True,
        ))

    if sensitive_modules:
        tasks.append(_ma_task(
            "task-sensitive-module-review",
            "Review sensitive module policy before implementation",
            "Mark auth, database, provider, deployment, billing, or security-sensitive work for explicit operator approval.",
            "security_guard_agent",
            target_modules=sensitive_modules,
            requirement_ids=_ma_requirement_ids(requirements, "auth", "security", "billing", "database") or all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["sensitive module approval notes", "guard/policy checklist"],
            validation_steps=["manual approval marker present", "guard policy remains separate from preview"],
            risk_level="high",
            manual_approval_required=True,
        ))

    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        tasks.append(_ma_task(
            "task-first-safe-patch-candidate",
            "Identify first safe patch candidate",
            "Choose a low-risk future patch candidate after inventory, test discovery, Source of Truth, and Module Map review.",
            "delivery_reviewer_agent",
            target_modules=[str(m["slug"]) for m in modules[:3]],
            requirement_ids=all_req_ids[:3],
            depends_on=["task-repository-inventory", "task-test-discovery", "task-architecture-alignment"],
            expected_outputs=["first patch candidate note", "manual review checklist"],
            validation_steps=["operator confirms candidate", "no proposal is created from intake preview"],
            risk_level="medium",
        ))

    tasks.extend([
        _ma_task(
            "task-qa-verification-plan",
            "Plan QA and regression verification",
            "Define validation commands and acceptance checks for future controlled development.",
            "qa_agent",
            target_modules=qa_modules,
            requirement_ids=all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["test strategy", "acceptance checklist", "smoke/regression scope"],
            validation_steps=["test hints from Module Map reviewed", "requirements have verification notes"],
            risk_level="medium",
        ),
        _ma_task(
            "task-delivery-readiness-review",
            "Plan delivery readiness review",
            "Prepare final delivery report expectations, unresolved risks, and operator handoff checks.",
            "delivery_reviewer_agent",
            target_modules=[str(m["slug"]) for m in modules[:_MAX_MA_PLAN_LINKS]],
            requirement_ids=all_req_ids,
            depends_on=["task-qa-verification-plan"],
            expected_outputs=["delivery checklist", "known limitations", "operator next action"],
            validation_steps=["delivery report includes module awareness", "blocked risks are visible"],
            risk_level="low",
        ),
    ])

    if any(k in text for k in ["deploy", "docker", "ci", "production", "release"]):
        tasks.append(_ma_task(
            "task-deployment-readiness",
            "Plan deployment readiness checks",
            "Capture future deployment, configuration, and release-readiness checks without changing runtime behavior.",
            "devops_agent",
            target_modules=_ma_module_slugs(modules, "deployment", "config", "infra"),
            requirement_ids=_ma_requirement_ids(requirements, "deploy", "release", "production") or all_req_ids,
            depends_on=["task-architecture-alignment"],
            expected_outputs=["deployment checklist", "configuration risk notes"],
            validation_steps=["no secrets exposed", "deployment actions require approval"],
            risk_level="high",
            manual_approval_required=True,
        ))

    tasks = _ma_dedup_tasks(tasks)
    risks = _ma_risks(req, modules, requirements)
    validation = _ma_plan_validation(req, tasks, requirements, modules)
    milestones = _ma_milestones(tasks)

    if validation.errors:
        first_action = "Fix validation errors before using this plan."
        first_task_id = None
    elif validation.missing_inputs:
        first_action = "Answer missing questions or confirm Source of Truth and Module Map before creating a controlled development run."
        first_task_id = "task-context-confirmation"
    elif any(task.manual_approval_required for task in tasks):
        first_action = "Review sensitive-module approval requirements before selecting the first implementation task."
        first_task_id = "task-sensitive-module-review" if any(task.id == "task-sensitive-module-review" for task in tasks) else "task-context-confirmation"
    else:
        first_action = "Review the first low-risk task and keep execution in the controlled development loop."
        first_task_id = "task-context-confirmation"

    plan_title = f"{_infer_product_name(req.intake.title, req.intake.raw_input)} — Multi-Agent Plan"
    return MultiAgentPlanFromIntakeResponse(
        mode=clarified.mode,
        plan_title=_cqe_short(plan_title, 120),
        plan_summary=_cqe_short(
            "Deterministic orchestrator-ready preview plan built from intake, clarifying answers, Source of Truth, and Module Map context.",
            240,
        ),
        tasks=tasks,
        milestones=milestones,
        risks=risks,
        recommended_first_action=first_action,
        recommended_first_task_id=first_task_id,
        validation=validation,
        safety_notes=_MA_PLAN_SAFETY_NOTES,
        limitations=_MA_PLAN_LIMITATIONS,
    )


# ── Intake to Confirmed Development Run Preview v1 ─────────────────────────

_MAX_DEV_RUN_PREVIEW_STEPS = 20
_MAX_DEV_RUN_PREVIEW_ROLES = 12
_MAX_DEV_RUN_PREVIEW_LINKS = 20
_MAX_DEV_RUN_PREVIEW_STEP_ITEMS = 8
_MAX_DEV_RUN_PREVIEW_MESSAGES = 20

_DEV_RUN_PREVIEW_LIMITATIONS = [
    "Deterministic only; no provider or LLM reasoning is used.",
    "No document upload extraction or repository scanning is performed.",
    "No project, run, run step, or tool call is persisted from this preview.",
    "No agent execution, command execution, patch proposal, or apply operation is started.",
]


class IntakeDevelopmentRunPreviewRequest(BaseModel):
    intake: UnifiedIntakeRequest
    answers: list[ClarifyingAnswer] = Field(default_factory=list)
    source_of_truth_draft: Optional[dict] = None
    module_map_draft: Optional[dict] = None
    multi_agent_plan: Optional[dict] = None
    preferred_mode: str = "guided"


class DevelopmentRunPreviewStep(BaseModel):
    id: str
    title: str
    description: str
    agent_role: str
    requirement_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    expected_outputs: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    safety_gates: list[str] = Field(default_factory=list)
    manual_approval_required: bool = False
    provider_allowed: bool = False
    risk_level: str = "medium"
    estimated_order: int


class DevelopmentRunPreviewValidation(BaseModel):
    ready_to_create_run: bool
    readiness: str
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)


class IntakeDevelopmentRunPreviewResponse(BaseModel):
    preview_only: bool = True
    mode: str
    run_title: str
    run_goal: str
    recommended_run_mode: str
    steps: list[DevelopmentRunPreviewStep] = Field(default_factory=list)
    agent_roles: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    safety_summary: list[str] = Field(default_factory=list)
    recommended_first_safe_action: str
    validation: DevelopmentRunPreviewValidation
    next_recommended_action: str
    limitations: list[str] = Field(default_factory=list)


def _drp_has_secret_like_content(req: IntakeDevelopmentRunPreviewRequest) -> bool:
    text = " ".join([
        req.intake.title or "",
        req.intake.raw_input or "",
        req.intake.document_excerpt or "",
        req.intake.project_path or "",
        " ".join(req.intake.known_stack),
        " ".join(req.intake.constraints),
        req.intake.desired_outcome or "",
        " ".join(a.answer for a in req.answers if not a.skipped),
    ])
    return _sot_contains_secret(text) or _module_map_contains_secret(text)


def _drp_requirement_ids(requirements: list[dict]) -> list[str]:
    return _ma_bounded([str(item.get("id", "")) for item in requirements], _MAX_DEV_RUN_PREVIEW_LINKS, 80)


def _drp_module_ids(modules: list[dict]) -> list[str]:
    return _ma_bounded([str(item.get("slug", "")) for item in modules], _MAX_DEV_RUN_PREVIEW_LINKS, 80)


def _drp_parse_plan(req: IntakeDevelopmentRunPreviewRequest) -> MultiAgentPlanFromIntakeResponse:
    if req.multi_agent_plan:
        try:
            return MultiAgentPlanFromIntakeResponse.model_validate(req.multi_agent_plan)
        except Exception:
            pass
    return build_multi_agent_plan_from_intake(MultiAgentPlanFromIntakeRequest(
        intake=req.intake,
        answers=req.answers,
        source_of_truth_draft=req.source_of_truth_draft,
        module_map_draft=req.module_map_draft,
    ))


def _drp_is_risky_task(task: MultiAgentPlanTask, sensitive_modules: list[str]) -> bool:
    text = " ".join([
        task.title,
        task.description,
        task.agent_role,
        task.risk_level,
        " ".join(task.target_modules),
    ]).lower()
    risky_terms = ["auth", "database", "schema", "deployment", "provider", "security", "billing", "payment"]
    return (
        task.manual_approval_required
        or task.risk_level.lower() in {"high", "critical"}
        or any(module in task.target_modules for module in sensitive_modules)
        or any(term in text for term in risky_terms)
    )


def _drp_safety_gates(
    task: MultiAgentPlanTask,
    *,
    risky: bool,
    mode: UnifiedIntakeMode,
) -> list[str]:
    gates = [
        "Preview only; no work is started from this screen.",
        "Operator must confirm before any future development run.",
        "Provider access remains disabled unless explicitly enabled later.",
    ]
    if task.requirement_ids:
        gates.append("Requirement links must be reviewed against the Source of Truth.")
    if task.target_modules:
        gates.append("Module links must be reviewed against the Module Map.")
    if risky:
        gates.append("Manual approval required before future patch, command, provider, or apply steps.")
    if mode == UnifiedIntakeMode.EXISTING_PROJECT:
        gates.append("Repository inventory and test discovery are future tasks only.")
    return _ma_bounded(gates, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 160)


def _drp_step_from_task(
    task: MultiAgentPlanTask,
    *,
    order: int,
    sensitive_modules: list[str],
    mode: UnifiedIntakeMode,
) -> DevelopmentRunPreviewStep:
    risky = _drp_is_risky_task(task, sensitive_modules)
    return DevelopmentRunPreviewStep(
        id=_cqe_short(task.id.replace("task-", "step-"), 80),
        title=task.title,
        description=task.description,
        agent_role=task.agent_role,
        requirement_ids=_ma_bounded(task.requirement_ids, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 80),
        module_ids=_ma_bounded(task.target_modules, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 80),
        depends_on=_ma_bounded([dep.replace("task-", "step-") for dep in task.depends_on], _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 80),
        expected_outputs=_ma_bounded(task.expected_outputs, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 140),
        validation_steps=_ma_bounded(task.validation_steps, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 140),
        safety_gates=_drp_safety_gates(task, risky=risky, mode=mode),
        manual_approval_required=risky,
        provider_allowed=False,
        risk_level="high" if risky and task.risk_level == "medium" else task.risk_level,
        estimated_order=order,
    )


def _drp_context_step(requirement_ids: list[str]) -> DevelopmentRunPreviewStep:
    return DevelopmentRunPreviewStep(
        id="step-context-confirmation",
        title="Confirm Source of Truth and intake assumptions",
        description="Review intake answers, Source of Truth readiness, open questions, and the future run goal before any development work.",
        agent_role="product_analyst",
        requirement_ids=_ma_bounded(requirement_ids, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 80),
        module_ids=[],
        depends_on=[],
        expected_outputs=["confirmed run goal", "reviewed assumptions", "open questions list"],
        validation_steps=["operator reviews Source of Truth draft", "operator confirms this is still preview-only"],
        safety_gates=[
            "Preview only; no work is started from this screen.",
            "Operator confirmation required before a real development run.",
            "Provider access remains disabled.",
        ],
        manual_approval_required=False,
        provider_allowed=False,
        risk_level="low",
        estimated_order=1,
    )


def _drp_module_review_step(module_ids: list[str]) -> DevelopmentRunPreviewStep:
    return DevelopmentRunPreviewStep(
        id="step-module-map-review",
        title="Review Module Map and ownership boundaries",
        description="Confirm module links, risky areas, ownership assumptions, and test hints before future implementation steps.",
        agent_role="architect",
        requirement_ids=[],
        module_ids=_ma_bounded(module_ids, _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 80),
        depends_on=["step-context-confirmation"],
        expected_outputs=["confirmed module targets", "sensitive module notes", "test hint review"],
        validation_steps=["operator reviews Module Map draft", "sensitive modules are marked for approval"],
        safety_gates=[
            "Module Map review is informational until the operator confirms a real run.",
            "No repository scan or file read is performed.",
            "Manual approval remains required for sensitive modules.",
        ],
        manual_approval_required=False,
        provider_allowed=False,
        risk_level="medium",
        estimated_order=2,
    )


def _drp_protected_modules_answer(req: IntakeDevelopmentRunPreviewRequest) -> bool:
    answers = " ".join(a.answer for a in req.answers if not a.skipped).lower()
    return any(term in answers for term in ["protected", "auth", "database", "security", "payment", "billing"])


def _drp_validation(
    req: IntakeDevelopmentRunPreviewRequest,
    *,
    steps: list[DevelopmentRunPreviewStep],
    run_title: str,
    run_goal: str,
    requirement_ids: list[str],
    module_ids: list[str],
    plan_provided: bool,
) -> DevelopmentRunPreviewValidation:
    errors: list[str] = []
    warnings: list[str] = []
    missing: list[str] = []
    blocked: list[str] = []

    if not steps:
        errors.append("Development run preview must include at least one step.")
        blocked.append("No preview steps were generated.")
    if not run_title:
        errors.append("Development run preview requires a run title.")
        blocked.append("Run title is missing.")
    if not run_goal:
        errors.append("Development run preview requires a run goal.")
        blocked.append("Run goal is missing.")
    if _drp_has_secret_like_content(req):
        errors.append("Intake contains secret-like content; remove credentials/tokens before building the preview.")
        blocked.append("Secret-like content must be removed.")
    if not req.source_of_truth_draft:
        warnings.append("No Source of Truth draft was provided; requirement links are conceptual.")
        missing.append("source_of_truth_draft")
    if not req.module_map_draft:
        warnings.append("No Module Map draft was provided; module links are conceptual.")
        missing.append("module_map_draft")
    if not plan_provided:
        warnings.append("No Multi-Agent Plan was provided; a conservative fallback plan was derived for preview.")
        missing.append("multi_agent_plan")
    if not req.source_of_truth_draft and not plan_provided:
        errors.append("A Source of Truth draft or Multi-Agent Plan is required before this preview is ready for real run setup.")
        blocked.append("Missing both Source of Truth draft and Multi-Agent Plan.")
    if not requirement_ids:
        warnings.append("No requirement ids are linked to preview steps.")
    if not module_ids:
        warnings.append("No module ids are linked to preview steps.")
    if any(not step.validation_steps for step in steps):
        warnings.append("One or more preview steps have no validation steps.")
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        if not req.intake.known_stack:
            warnings.append("Existing project intake has no known_stack; future run setup needs operator review.")
            missing.append("known_stack")
        answer_map = {a.question_id: a for a in req.answers}
        if not _cqe_answered("cq-ep-4", answer_map):
            warnings.append("Existing project intake has no confirmed test command.")
            missing.append("test_command")
        if not _drp_protected_modules_answer(req):
            warnings.append("Existing project intake has no confirmed protected module list.")
            missing.append("protected_modules")

    readiness = "blocked" if errors else ("needs_review" if warnings or missing else "ready_for_run_setup")
    return DevelopmentRunPreviewValidation(
        ready_to_create_run=not errors and bool(steps) and bool(req.source_of_truth_draft),
        readiness=readiness,
        errors=errors[:_MAX_DEV_RUN_PREVIEW_MESSAGES],
        warnings=warnings[:_MAX_DEV_RUN_PREVIEW_MESSAGES],
        missing_inputs=_ma_bounded(missing, _MAX_DEV_RUN_PREVIEW_MESSAGES, 80),
        blocked_reasons=blocked[:_MAX_DEV_RUN_PREVIEW_MESSAGES],
    )


def _drp_goal(req: IntakeDevelopmentRunPreviewRequest) -> str:
    goal = req.intake.desired_outcome or req.intake.raw_input or req.intake.document_excerpt or req.intake.title
    if req.intake.mode == UnifiedIntakeMode.DOCUMENT:
        return _cqe_short(f"Normalize requirements and prepare controlled development for {_infer_product_name(req.intake.title, goal)}.", 180)
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        return _cqe_short(f"Prepare a controlled future development run for existing project context: {_infer_product_name(req.intake.title, goal)}.", 180)
    return _cqe_short(f"Prepare a controlled future development run for {_infer_product_name(req.intake.title, goal)}.", 180)


def _drp_first_action(
    req: IntakeDevelopmentRunPreviewRequest,
    validation: DevelopmentRunPreviewValidation,
    steps: list[DevelopmentRunPreviewStep],
) -> str:
    if validation.errors:
        return "Fix preview validation errors before using this as a real run setup guide."
    if "source_of_truth_draft" in validation.missing_inputs:
        return "Confirm or attach a Source of Truth draft before creating a real development run."
    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT:
        return "Confirm project context, protected modules, and safe inventory scope before creating a real development run."
    if req.intake.mode == UnifiedIntakeMode.DOCUMENT:
        return "Confirm requirements, scope, and acceptance criteria before creating a real development run."
    if steps:
        return f"Review the first preview step: {steps[0].title}."
    return "Review missing inputs before continuing."


def build_intake_development_run_preview(
    req: IntakeDevelopmentRunPreviewRequest,
) -> IntakeDevelopmentRunPreviewResponse:
    """Build a deterministic, preview-only future development run outline."""
    clarified = refine_unified_intake_with_answers(ClarifyingAnswersRequest(
        intake=req.intake,
        answers=req.answers,
    ))
    requirements = _mm_extract_sot_requirements(req.source_of_truth_draft)
    modules = _ma_extract_module_map_modules(req.module_map_draft)
    requirement_ids = _drp_requirement_ids(requirements)
    module_ids = _drp_module_ids(modules)
    sensitive_modules = _ma_sensitive_modules(modules)
    plan_provided = bool(req.multi_agent_plan and isinstance(req.multi_agent_plan.get("tasks"), list))
    plan = _drp_parse_plan(req)

    steps: list[DevelopmentRunPreviewStep] = []
    steps.append(_drp_context_step(requirement_ids))
    if module_ids:
        steps.append(_drp_module_review_step(module_ids))

    for task in plan.tasks:
        if task.id == "task-context-confirmation":
            continue
        step = _drp_step_from_task(
            task,
            order=len(steps) + 1,
            sensitive_modules=sensitive_modules,
            mode=req.intake.mode,
        )
        if step.id == "step-module-map-review" and any(existing.id == step.id for existing in steps):
            continue
        steps.append(step)
        if len(steps) >= _MAX_DEV_RUN_PREVIEW_STEPS:
            break

    if req.intake.mode == UnifiedIntakeMode.EXISTING_PROJECT and _drp_protected_modules_answer(req):
        has_protected_review = any("protected" in step.title.lower() for step in steps)
        if not has_protected_review and len(steps) < _MAX_DEV_RUN_PREVIEW_STEPS:
            steps.insert(min(2, len(steps)), DevelopmentRunPreviewStep(
                id="step-protected-modules-review",
                title="Review protected modules before patch planning",
                description="Confirm protected auth, data, security, payment, deployment, or provider areas before selecting a future patch candidate.",
                agent_role="security_guard_agent",
                requirement_ids=requirement_ids[:_MAX_DEV_RUN_PREVIEW_STEP_ITEMS],
                module_ids=sensitive_modules[:_MAX_DEV_RUN_PREVIEW_STEP_ITEMS],
                depends_on=["step-context-confirmation"],
                expected_outputs=["protected module checklist", "manual approval notes"],
                validation_steps=["operator confirms protected areas", "manual approval remains required"],
                safety_gates=[
                    "Protected module work requires explicit approval later.",
                    "No patch proposal or apply operation is started.",
                    "No repository scan is performed.",
                ],
                manual_approval_required=True,
                provider_allowed=False,
                risk_level="high",
                estimated_order=3,
            ))

    for step in steps:
        if any(module in step.module_ids for module in sensitive_modules):
            step.manual_approval_required = True
            if step.risk_level == "medium":
                step.risk_level = "high"
            gate = "Manual approval required before future patch, command, provider, or apply steps."
            if gate not in step.safety_gates:
                step.safety_gates = _ma_bounded(step.safety_gates + [gate], _MAX_DEV_RUN_PREVIEW_STEP_ITEMS, 160)

    for idx, step in enumerate(steps, start=1):
        step.estimated_order = idx

    run_title = _cqe_short(f"{_infer_product_name(req.intake.title, req.intake.raw_input)} — Development Run Preview", 120)
    run_goal = _drp_goal(req)
    validation = _drp_validation(
        req,
        steps=steps,
        run_title=run_title,
        run_goal=run_goal,
        requirement_ids=[rid for step in steps for rid in step.requirement_ids],
        module_ids=[mid for step in steps for mid in step.module_ids],
        plan_provided=plan_provided,
    )

    roles = []
    for step in steps:
        if step.agent_role not in roles:
            roles.append(step.agent_role)

    summary = [
        "Preview only; no project, run, run step, or tool call is persisted.",
        "Provider access defaults to disabled for every preview step.",
        "Patch, apply, command, and test execution remain future controlled workflow.",
    ]
    if any(step.manual_approval_required for step in steps):
        summary.append("One or more preview steps require manual approval before future execution.")

    allowed_modes = {"guided", "review_only", "operator_controlled"}
    recommended_mode = req.preferred_mode if req.preferred_mode in allowed_modes else "guided"
    first_action = _drp_first_action(req, validation, steps)

    return IntakeDevelopmentRunPreviewResponse(
        preview_only=True,
        mode=clarified.mode,
        run_title=run_title,
        run_goal=run_goal,
        recommended_run_mode=recommended_mode,
        steps=steps[:_MAX_DEV_RUN_PREVIEW_STEPS],
        agent_roles=_ma_bounded(roles, _MAX_DEV_RUN_PREVIEW_ROLES, 80),
        requirement_ids=_ma_bounded([rid for step in steps for rid in step.requirement_ids], _MAX_DEV_RUN_PREVIEW_LINKS, 80),
        module_ids=_ma_bounded([mid for step in steps for mid in step.module_ids], _MAX_DEV_RUN_PREVIEW_LINKS, 80),
        safety_summary=summary,
        recommended_first_safe_action=first_action,
        validation=validation,
        next_recommended_action=first_action,
        limitations=_DEV_RUN_PREVIEW_LIMITATIONS,
    )


# ── Confirmed Run Creation Contract Preview ───────────────────────────────────


class ConfirmedRunCreationRequirementPreview(BaseModel):
    """Pydantic mirror of ConfirmedRunCreationRequirement for HTTP responses."""

    id: str
    description: str
    required: bool = True
    satisfied: bool = False
    severity: str = "error"


class ConfirmedRunCreationSafetyGatePreview(BaseModel):
    """Pydantic mirror of ConfirmedRunCreationSafetyGate for HTTP responses."""

    id: str
    title: str
    description: str
    required_before_creation: bool = True
    required_before_execution: bool = True


class IntakeConfirmedRunCreationContractPreviewRequest(BaseModel):
    """Request to evaluate the confirmed run creation contract for a development run preview.

    Preview-only.  Does not persist state, create runs, call providers, read
    files, or execute commands.
    """

    development_run_preview: dict = Field(default_factory=dict)
    project_id: Optional[str] = None
    confirm: bool = False
    preview_only: bool = True
    source_of_truth_valid: bool = False
    module_map_valid: bool = False
    multi_agent_plan_valid: bool = False


class IntakeConfirmedRunCreationContractPreviewResponse(BaseModel):
    """Response from the confirmed run creation contract preview endpoint."""

    preview_only: bool = True
    decision: str  # "allowed" | "warning" | "blocked"
    risk: str  # "low" | "medium" | "high" | "critical"
    can_create_pending_run: bool
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    requirements: list[ConfirmedRunCreationRequirementPreview] = Field(default_factory=list)
    safety_gates: list[ConfirmedRunCreationSafetyGatePreview] = Field(default_factory=list)
    allowed_created_entities: list[str] = Field(default_factory=list)
    forbidden_created_entities: list[str] = Field(default_factory=list)
    required_statuses: dict[str, str] = Field(default_factory=dict)
    required_operator_confirmations: list[str] = Field(default_factory=list)
    next_recommended_action: str = ""
    contract_note: str = (
        "Contract preview only. No run, step, project, tool_call, "
        "provider call, patch, or command execution has occurred."
    )


def build_confirmed_run_creation_contract_preview(
    req: IntakeConfirmedRunCreationContractPreviewRequest,
) -> IntakeConfirmedRunCreationContractPreviewResponse:
    """Pure adapter: map a development run preview dict to a contract evaluation.

    Converts ``development_run_preview`` into a ``ConfirmedRunCreationInput``
    and calls ``evaluate_confirmed_run_creation_contract``.

    No side effects, no DB, no providers, no filesystem I/O.
    """
    from src.release.confirmed_development_run_creation_contract import (
        ConfirmedRunCreationInput,
        evaluate_confirmed_run_creation_contract,
    )

    preview = req.development_run_preview

    # Extract fields from the preview payload.
    run_title = str(preview.get("run_title", ""))
    run_goal = str(preview.get("run_goal", ""))
    recommended_run_mode = str(preview.get("recommended_run_mode", "guided"))
    steps = list(preview.get("steps", []))

    # Derive development_preview_valid from the nested validation object.
    raw_validation = preview.get("validation", {})
    if isinstance(raw_validation, dict):
        development_preview_valid = bool(raw_validation.get("ready_to_create_run", False))
    else:
        development_preview_valid = False

    inp = ConfirmedRunCreationInput(
        project_id=req.project_id,
        confirm=req.confirm,
        preview_only=req.preview_only,
        run_title=run_title,
        run_goal=run_goal,
        recommended_run_mode=recommended_run_mode,
        steps=steps,
        source_of_truth_valid=req.source_of_truth_valid,
        module_map_valid=req.module_map_valid,
        multi_agent_plan_valid=req.multi_agent_plan_valid,
        development_preview_valid=development_preview_valid,
    )

    result = evaluate_confirmed_run_creation_contract(inp)

    return IntakeConfirmedRunCreationContractPreviewResponse(
        preview_only=True,
        decision=result.decision.value,
        risk=result.risk.value,
        can_create_pending_run=result.can_create_pending_run,
        blockers=result.blockers,
        warnings=result.warnings,
        requirements=[
            ConfirmedRunCreationRequirementPreview(
                id=r.id,
                description=r.description,
                required=r.required,
                satisfied=r.satisfied,
                severity=r.severity,
            )
            for r in result.requirements
        ],
        safety_gates=[
            ConfirmedRunCreationSafetyGatePreview(
                id=g.id,
                title=g.title,
                description=g.description,
                required_before_creation=g.required_before_creation,
                required_before_execution=g.required_before_execution,
            )
            for g in result.safety_gates
        ],
        allowed_created_entities=[e.value for e in result.allowed_created_entities],
        forbidden_created_entities=[e.value for e in result.forbidden_created_entities],
        required_statuses=result.required_statuses,
        required_operator_confirmations=result.required_operator_confirmations,
        next_recommended_action=result.next_recommended_action,
    )


# ── Confirmed Development Run Bridge (Fastlane v1) ────────────────────────────

_MAX_BRIDGE_STEP_INPUT = 4000   # chars per step input block
_MAX_BRIDGE_STEPS = 20          # hard cap on persisted steps

_BRIDGE_SAFETY_NOTES: list[str] = [
    "Run created in pending state only. No agents started, no providers called.",
    "All steps remain pending. No tool_calls created.",
    "provider_allowed=false on all steps.",
    "Manual approval required before any risky step executes.",
    "Source of Truth guard must be consulted before any patch proposal.",
    "apply/test/run commands require a later explicit operator action.",
]


class ConfirmedDevelopmentRunCreateRequest(BaseModel):
    """Request to create a real pending development run from the intake pipeline.

    Requires all confirmation booleans to be True and all mandatory contract
    requirements to be satisfied.  Creates run and run_step only — does not
    start execution, call providers, create tool_calls, or write patch proposals.
    """

    project_id: str
    confirm_create: bool = False
    contract_confirmed: bool = False
    source_of_truth_confirmed: bool = False
    module_map_confirmed: bool = False
    provider_disabled_confirmed: bool = False
    later_actions_confirmed: bool = False
    development_run_preview: dict = Field(default_factory=dict)
    contract_preview: Optional[dict] = None
    repo_intake_preview: Optional[dict] = None
    preferred_run_mode: str = "guided"


class ConfirmedDevelopmentRunCreatedStep(BaseModel):
    """Minimal metadata about a persisted pending RunStep."""

    step_id: str
    title: str
    agent_role: str
    status: str
    requirement_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    manual_approval_required: bool = False
    provider_allowed: bool = False


class ConfirmedDevelopmentRunCreateResponse(BaseModel):
    """Response after creating a confirmed pending development run."""

    created: bool
    run_id: Optional[str] = None
    project_id: str
    status: str
    run_mode: str
    steps: list[ConfirmedDevelopmentRunCreatedStep] = Field(default_factory=list)
    contract_decision: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    next_recommended_action: str
    open_run_url_hint: Optional[str] = None


_MAX_STEP_CONTEXT_LINKS = 20
_MAX_STEP_CONTEXT_ITEMS = 8
_SENSITIVE_STEP_TERMS = {
    "auth",
    "access",
    "database",
    "schema",
    "security",
    "provider",
    "deployment",
    "billing",
    "payment",
}


class DevelopmentRunStepContext(BaseModel):
    source: str = "unknown"
    agent_role: str = ""
    canonical_agent_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    safety_gates: list[str] = Field(default_factory=list)
    manual_approval_required: bool = False
    provider_allowed: bool = False
    expected_outputs: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    risk_level: str = "medium"
    next_safe_action: str
    repo_context_available: bool = False
    detected_stack: list[str] = Field(default_factory=list)
    detected_project_type: str | None = None
    relevant_area_hints: list[str] = Field(default_factory=list)
    relevant_manifest_scripts: list[str] = Field(default_factory=list)
    test_discovery_hints: list[str] = Field(default_factory=list)
    protected_path_warnings: list[str] = Field(default_factory=list)
    suggested_safe_commands: list[str] = Field(default_factory=list)
    repo_safety_notes: list[str] = Field(default_factory=list)
    repo_limitations: list[str] = Field(default_factory=list)


class RepoAwareRunContextSnapshot(BaseModel):
    detected_stack: list[str] = Field(default_factory=list)
    detected_project_type: str = ""
    detected_areas: list[dict] = Field(default_factory=list)
    manifest_summaries: list[dict] = Field(default_factory=list)
    protected_path_warnings: list[str] = Field(default_factory=list)
    source_of_truth_hints: list[str] = Field(default_factory=list)
    module_map_hints: list[str] = Field(default_factory=list)
    test_discovery_hints: list[str] = Field(default_factory=list)
    recommended_first_safe_action: str = ""
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    suggested_safe_commands: list[str] = Field(default_factory=list)


class RepoAwareStepContext(BaseModel):
    detected_stack: list[str] = Field(default_factory=list)
    detected_project_type: str = ""
    relevant_area_hints: list[str] = Field(default_factory=list)
    relevant_manifest_scripts: list[str] = Field(default_factory=list)
    test_discovery_hints: list[str] = Field(default_factory=list)
    protected_path_warnings: list[str] = Field(default_factory=list)
    suggested_safe_commands: list[str] = Field(default_factory=list)
    recommended_first_safe_action: str = ""
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class StepAgentPatchDraftRequest(BaseModel):
    """Request to prepare a draft patch candidate from an intake-origin step.

    Preview/draft only.  This model intentionally does not contain any flag
    that can create proposals, apply patches, run commands, or call providers.
    """

    run_id: str = ""
    step_id: str = ""
    use_existing_agent_result: bool = True
    agent_result: dict | None = None
    operator_note: str = ""
    max_target_files: int = 8
    max_risks: int = 8
    max_validation_steps: int = 8


class StepAgentPatchDraftResponse(BaseModel):
    run_id: str
    step_id: str
    step_title: str
    agent_role: str
    canonical_agent_id: str
    requirement_ids: list[str] = Field(default_factory=list)
    module_ids: list[str] = Field(default_factory=list)
    target_files: list[str] = Field(default_factory=list)
    patch_intent: str
    draft_summary: str
    suggested_file_path: str
    suggested_old_text: str
    suggested_new_text: str
    risks: list[str] = Field(default_factory=list)
    validation_steps: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ready_for_proposal: bool = False
    next_recommended_action: str
    source: str = "step_agent_patch_draft"
    repo_context_available: bool = False
    detected_stack: list[str] = Field(default_factory=list)
    relevant_area_hints: list[str] = Field(default_factory=list)
    relevant_manifest_scripts: list[str] = Field(default_factory=list)
    test_discovery_hints: list[str] = Field(default_factory=list)
    protected_path_warnings: list[str] = Field(default_factory=list)
    suggested_safe_commands: list[str] = Field(default_factory=list)


class StepPatchDraftGuardedProposalRequest(BaseModel):
    """Operator-confirmed bridge from step patch draft to guarded proposal.

    Preview/preflight is read-only. Proposal creation requires
    confirm_create_proposal=true plus operator-selected patch fields.
    """

    run_id: str = ""
    step_id: str = ""
    patch_draft: dict = Field(default_factory=dict)
    confirm_create_proposal: bool = False
    operator_note: str = ""
    allow_no_guard_override: bool = False
    selected_file_path: str = ""
    selected_old_text: str = ""
    selected_new_text: str = ""


class StepPatchDraftGuardedProposalResponse(BaseModel):
    run_id: str
    step_id: str
    created: bool = False
    proposal_id: str | None = None
    guard_result_id: str | None = None
    guard_decision: str = "preflight_not_run"
    module_awareness: dict | None = None
    module_policy: dict | None = None
    patch_review: dict | None = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    next_recommended_action: str
    ready_for_apply: bool = False


_REPO_CONTEXT_MAX_ITEMS = 8
_REPO_CONTEXT_MAX_COMMANDS = 8
_SAFE_NPM_SCRIPT_NAMES = {"test", "test:unit", "test:e2e", "lint", "typecheck", "build"}


def _repo_context_safe_text(value: object, *, max_chars: int = 180) -> str:
    text = _cqe_short(str(value or "").strip(), max_chars)
    if not text:
        return ""
    if _sot_contains_secret(text) or _module_map_contains_secret(text) or _REPO_SECRET_WORDS.search(text):
        return "[REDACTED]"
    return text


def _repo_context_list(value: object, *, limit: int = _REPO_CONTEXT_MAX_ITEMS, max_chars: int = 180) -> list[str]:
    if value is None:
        return []
    raw = value if isinstance(value, list) else [value]
    result: list[str] = []
    for item in raw:
        if isinstance(item, dict):
            continue
        text = _repo_context_safe_text(item, max_chars=max_chars)
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result


def _repo_context_dicts(value: object, *, limit: int = _REPO_CONTEXT_MAX_ITEMS) -> list[dict]:
    if not isinstance(value, list):
        return []
    result: list[dict] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        clean: dict[str, object] = {}
        for key, val in item.items():
            key_text = _repo_context_safe_text(key, max_chars=80)
            if not key_text:
                continue
            if isinstance(val, list):
                clean[key_text] = _repo_context_list(val, limit=6, max_chars=140)
            elif isinstance(val, dict):
                continue
            else:
                clean[key_text] = _repo_context_safe_text(val, max_chars=180)
        if clean:
            result.append(clean)
        if len(result) >= limit:
            break
    return result


def _repo_manifest_script_name(script: str) -> str:
    lowered = script.strip().lower()
    for name in sorted(_SAFE_NPM_SCRIPT_NAMES, key=len, reverse=True):
        if lowered == name or lowered.startswith(name + ":"):
            return name
    head = lowered.split(":", 1)[0].strip()
    return head.replace("npm run ", "").replace("yarn ", "").replace("pnpm ", "").strip()


def _repo_context_safe_commands(manifests: list[dict], stack: list[str], test_hints: list[str]) -> list[str]:
    suggestions: list[str] = []

    def add(command: str) -> None:
        command = _repo_context_safe_text(command, max_chars=120)
        if command and command not in suggestions and len(suggestions) < _REPO_CONTEXT_MAX_COMMANDS:
            suggestions.append(command)

    for manifest in manifests:
        path = str(manifest.get("path") or "")
        kind = str(manifest.get("kind") or "")
        scripts = manifest.get("detected_scripts") or []
        if not isinstance(scripts, list):
            scripts = []
        for script in scripts:
            script_text = str(script or "")
            script_name = _repo_manifest_script_name(script_text)
            if kind == "package.json" and script_name in _SAFE_NPM_SCRIPT_NAMES:
                add(f"npm run {script_name}")
            if kind == "composer.json" and script_name in {"test", "tests"}:
                add("composer test")
            if "pytest" in script_text.lower():
                add("pytest")
            if "phpunit" in script_text.lower():
                add("phpunit")
        if path in {"pyproject.toml", "pytest.ini", "requirements.txt"} or kind in {"pyproject.toml", "pytest.ini", "requirements.txt"}:
            if "python" in " ".join(stack).lower() or any("pytest" in hint.lower() for hint in test_hints):
                add("pytest")
        if path == "phpunit.xml" or kind == "phpunit.xml":
            add("phpunit")

    if any("pytest" in hint.lower() for hint in test_hints):
        add("pytest")
    if any("phpunit" in hint.lower() for hint in test_hints):
        add("phpunit")
    return suggestions


def build_repo_aware_run_context_snapshot(repo_intake_preview: dict | None) -> RepoAwareRunContextSnapshot:
    """Build bounded repo-aware metadata from an existing repo-intake preview.

    Pure helper: no DB access, provider calls, file reads, command execution, or
    mutation. Commands are text suggestions only.
    """
    if not isinstance(repo_intake_preview, dict) or not repo_intake_preview:
        return RepoAwareRunContextSnapshot()

    stack = _repo_context_list(repo_intake_preview.get("detected_stack"), limit=10, max_chars=80)
    areas = _repo_context_dicts(repo_intake_preview.get("detected_areas"), limit=8)
    manifests = _repo_context_dicts(repo_intake_preview.get("manifest_summaries"), limit=8)
    test_hints = _repo_context_list(repo_intake_preview.get("test_discovery_hints"), limit=8, max_chars=180)
    suggested_commands = _repo_context_safe_commands(manifests, stack, test_hints)

    return RepoAwareRunContextSnapshot(
        detected_stack=stack,
        detected_project_type=_repo_context_safe_text(repo_intake_preview.get("detected_project_type"), max_chars=80),
        detected_areas=areas,
        manifest_summaries=manifests,
        protected_path_warnings=_repo_context_list(repo_intake_preview.get("protected_path_warnings"), limit=8, max_chars=180),
        source_of_truth_hints=_repo_context_list(repo_intake_preview.get("source_of_truth_hints"), limit=6, max_chars=180),
        module_map_hints=_repo_context_list(repo_intake_preview.get("module_map_hints"), limit=6, max_chars=180),
        test_discovery_hints=test_hints,
        recommended_first_safe_action=_repo_context_safe_text(repo_intake_preview.get("recommended_first_safe_action"), max_chars=220),
        safety_notes=_repo_context_list(repo_intake_preview.get("safety_notes"), limit=6, max_chars=180),
        limitations=_repo_context_list(repo_intake_preview.get("limitations"), limit=6, max_chars=180),
        suggested_safe_commands=suggested_commands,
    )


def build_repo_aware_step_context_for_preview_step(
    step_preview: dict,
    repo_context: RepoAwareRunContextSnapshot,
) -> RepoAwareStepContext:
    """Build compact per-step repo hints from a bounded repo snapshot."""
    if not repo_context.detected_stack and not repo_context.detected_areas and not repo_context.manifest_summaries:
        return RepoAwareStepContext()

    raw_text = " ".join([
        str(step_preview.get("title") or ""),
        str(step_preview.get("description") or ""),
        str(step_preview.get("agent_role") or ""),
        " ".join(str(item) for item in step_preview.get("module_ids") or []),
    ]).lower()

    relevant_areas: list[str] = []
    for area in repo_context.detected_areas:
        area_id = str(area.get("id") or "").lower()
        kind = str(area.get("kind") or "").lower()
        title = _repo_context_safe_text(area.get("title"), max_chars=80)
        paths = _repo_context_list(area.get("path_hints"), limit=3, max_chars=100)
        if area_id and (area_id in raw_text or kind in raw_text or not relevant_areas):
            relevant_areas.append(f"{title or area_id}: {', '.join(paths) if paths else 'no path hints'}")
        if len(relevant_areas) >= 5:
            break

    manifest_scripts: list[str] = []
    for manifest in repo_context.manifest_summaries:
        path = _repo_context_safe_text(manifest.get("path"), max_chars=100)
        scripts = _repo_context_list(manifest.get("detected_scripts"), limit=4, max_chars=120)
        for script in scripts:
            item = f"{path}: {script}" if path else script
            if item not in manifest_scripts:
                manifest_scripts.append(item)
            if len(manifest_scripts) >= 6:
                break
        if len(manifest_scripts) >= 6:
            break

    return RepoAwareStepContext(
        detected_stack=repo_context.detected_stack[:8],
        detected_project_type=repo_context.detected_project_type,
        relevant_area_hints=relevant_areas[:5],
        relevant_manifest_scripts=manifest_scripts[:6],
        test_discovery_hints=repo_context.test_discovery_hints[:6],
        protected_path_warnings=repo_context.protected_path_warnings[:6],
        suggested_safe_commands=repo_context.suggested_safe_commands[:6],
        recommended_first_safe_action=repo_context.recommended_first_safe_action,
        safety_notes=repo_context.safety_notes[:5],
        limitations=repo_context.limitations[:5],
    )


def _repo_context_block(repo_step_context: RepoAwareStepContext) -> str:
    if not (
        repo_step_context.detected_stack
        or repo_step_context.relevant_area_hints
        or repo_step_context.relevant_manifest_scripts
        or repo_step_context.test_discovery_hints
        or repo_step_context.protected_path_warnings
    ):
        return ""

    def join(values: list[str]) -> str:
        return "; ".join(_repo_context_list(values, limit=8, max_chars=160)) or "none"

    lines = [
        "AI_WORKBENCH_REPO_AWARE_CONTEXT",
        f"- detected_stack: {', '.join(repo_step_context.detected_stack) if repo_step_context.detected_stack else 'none'}",
        f"- detected_project_type: {repo_step_context.detected_project_type or 'unknown'}",
        f"- relevant_area_hints: {join(repo_step_context.relevant_area_hints)}",
        f"- relevant_manifest_scripts: {join(repo_step_context.relevant_manifest_scripts)}",
        f"- test_discovery_hints: {join(repo_step_context.test_discovery_hints)}",
        f"- protected_path_warnings: {join(repo_step_context.protected_path_warnings)}",
        f"- suggested_safe_commands: {join(repo_step_context.suggested_safe_commands)}",
        f"- recommended_first_safe_action: {repo_step_context.recommended_first_safe_action or 'Review repo-aware context before agent work.'}",
        f"- safety_notes: {join(repo_step_context.safety_notes)}",
        f"- limitations: {join(repo_step_context.limitations)}",
        "END_AI_WORKBENCH_REPO_AWARE_CONTEXT",
    ]
    return "\n".join(lines)


_PATCH_DRAFT_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)\s*[:=]\s*\S+"
)


def _redact_patch_draft_text(value: object, *, max_chars: int = 800) -> tuple[str, bool]:
    text = _cqe_short(str(value or ""), max_chars)
    if not text:
        return "", False
    if _sot_contains_secret(text) or _module_map_contains_secret(text) or _PATCH_DRAFT_SECRET_ASSIGNMENT_RE.search(text):
        return _PATCH_DRAFT_SECRET_ASSIGNMENT_RE.sub(r"\1=[REDACTED]", text), True
    return text, False


def _patch_draft_list(value: object, *, limit: int, max_chars: int = 160) -> tuple[list[str], bool]:
    if not isinstance(value, list):
        return [], False
    result: list[str] = []
    redacted = False
    for item in value:
        text, item_redacted = _redact_patch_draft_text(item, max_chars=max_chars)
        redacted = redacted or item_redacted
        if text and text not in result:
            result.append(text)
        if len(result) >= limit:
            break
    return result, redacted


def _patch_draft_slug(parts: list[str]) -> str:
    for part in parts:
        cleaned = re.sub(r"[^a-z0-9]+", "_", str(part or "").lower()).strip("_")
        if cleaned and cleaned not in {"none", "unknown", "unassigned"}:
            return cleaned[:40]
    return "target_area"


def _infer_step_patch_target_files(
    *,
    context: DevelopmentRunStepContext,
    agent_result_files: list[str],
    operator_note: str,
    max_target_files: int,
) -> tuple[list[str], list[str], list[str]]:
    """Infer path hints from step metadata only; never scans files."""
    target_files: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []

    for path in agent_result_files:
        safe, reason = _module_map_path_is_safe(path)
        if safe and path not in target_files:
            target_files.append(path)
        elif reason:
            warnings.append(f"Skipped unsafe target file hint: {reason}")

    role = (context.agent_role or context.canonical_agent_id or "").lower()
    module_text = " ".join(context.module_ids).lower()
    combined = f"{role} {module_text}"
    slug = _patch_draft_slug(context.module_ids + [context.agent_role, context.canonical_agent_id])

    if len(target_files) < max_target_files:
        if "frontend" in combined or "ui" in combined or "react" in combined:
            target_files.append(f"frontend/src/pages/{slug}.tsx")
        if "backend" in combined or "api" in combined or "auth" in combined or "access" in combined:
            target_files.append(f"backend/src/api/{slug}.py")
        if "database" in combined or "schema" in combined or "postgres" in combined or "sql" in combined:
            target_files.append(f"backend/src/storage/{slug}.py")
            warnings.append("Database/schema target requires manual approval and exact file review before proposal.")
        if "qa" in combined or "test" in combined:
            target_files.append(f"tests/test_{slug}.py")
        if "security" in combined and not agent_result_files and not operator_note:
            warnings.append("Security-sensitive step needs operator narrowing before a concrete patch target is reliable.")

    deduped: list[str] = []
    for path in target_files:
        path = _cqe_short(path, 160)
        safe, reason = _module_map_path_is_safe(path)
        if not safe:
            warnings.append(f"Skipped unsafe inferred path: {reason}")
            continue
        if path not in deduped:
            deduped.append(path)
        if len(deduped) >= max_target_files:
            break

    if not deduped and not operator_note:
        blockers.append("No safe target file hint could be inferred. Add an operator note or provide an agent result with proposed files.")
    return deduped, warnings[:8], blockers[:8]


def build_step_agent_patch_draft(
    *,
    run_id: str,
    step,
    agent_step_context: DevelopmentRunStepContext | None = None,
    agent_result: dict | None = None,
    operator_note: str = "",
    max_target_files: int = 8,
    max_risks: int = 8,
    max_validation_steps: int = 8,
) -> StepAgentPatchDraftResponse:
    """Build a bounded patch draft candidate from existing step context.

    Pure helper: no DB writes, provider calls, file reads, command execution,
    patch proposal creation, or apply operation.
    """
    context = agent_step_context or normalize_development_run_step_context(getattr(step, "input", ""))
    status = str(getattr(step, "status", "") or "").lower()
    step_title = _cqe_short(getattr(step, "title", "") or "Untitled step", 200)
    operator_note, operator_note_redacted = _redact_patch_draft_text(operator_note, max_chars=800)
    agent_result = agent_result or {}

    summary, summary_redacted = _redact_patch_draft_text(agent_result.get("summary", ""), max_chars=500)
    analysis, analysis_redacted = _redact_patch_draft_text(agent_result.get("analysis", ""), max_chars=900)
    result_intent, intent_redacted = _redact_patch_draft_text(agent_result.get("patch_intent", ""), max_chars=600)
    proposed_files, files_redacted = _patch_draft_list(
        agent_result.get("proposed_files", []),
        limit=max(1, min(max_target_files, 12)),
        max_chars=160,
    )
    result_risks, risks_redacted = _patch_draft_list(
        agent_result.get("risks", []),
        limit=max(1, min(max_risks, 12)),
        max_chars=180,
    )
    test_suggestions, tests_redacted = _patch_draft_list(
        agent_result.get("test_suggestions", []),
        limit=max(1, min(max_validation_steps, 12)),
        max_chars=180,
    )

    warnings: list[str] = []
    blockers: list[str] = []
    redacted_any = any([
        operator_note_redacted,
        summary_redacted,
        analysis_redacted,
        intent_redacted,
        files_redacted,
        risks_redacted,
        tests_redacted,
    ])
    if redacted_any:
        warnings.append("Secret-like content was redacted from the draft input.")

    if status != "pending":
        blockers.append(f"Step status is '{status or 'unknown'}'; only pending steps can be prepared for patch draft proposal.")
    if context.provider_allowed:
        blockers.append("provider_allowed=true blocks patch draft readiness until the provider boundary is resolved.")
    if not context.canonical_agent_id:
        blockers.append("No canonical agent ID could be resolved for this step.")
    if not context.safety_gates:
        blockers.append("No safety gates found in the step context.")
    if not context.requirement_ids and not context.module_ids and not operator_note:
        blockers.append("No requirement/module links found. Add an operator note before preparing a concrete patch draft.")

    target_files, target_warnings, target_blockers = _infer_step_patch_target_files(
        context=context,
        agent_result_files=proposed_files,
        operator_note=operator_note,
        max_target_files=max(1, min(max_target_files, 12)),
    )
    warnings.extend(target_warnings)
    blockers.extend(target_blockers)

    role_text = f"{context.agent_role} {context.canonical_agent_id} {' '.join(context.module_ids)}".lower()
    if "security" in role_text and not operator_note and not proposed_files:
        warnings.append("Security review steps should be narrowed by the operator before drafting a patch.")
    if context.manual_approval_required:
        warnings.append("Manual approval is required before this risky step can move beyond draft/proposal preparation.")
    for warning in context.protected_path_warnings:
        warnings.append(f"Repo-aware protected path warning: {warning}")

    patch_intent = result_intent or operator_note or (
        f"Prepare a minimal patch for {step_title} using the linked requirements and module context."
    )
    draft_summary_parts = [
        f"Draft candidate for '{step_title}' assigned to {context.canonical_agent_id}.",
    ]
    if summary:
        draft_summary_parts.append(summary)
    if analysis:
        draft_summary_parts.append(analysis[:300])
    draft_summary = " ".join(draft_summary_parts)[:1000]

    risks: list[str] = []
    risks.extend(result_risks)
    if context.manual_approval_required:
        risks.append("Manual approval required by step context before proposal/apply execution.")
    if "database" in role_text or "schema" in role_text:
        risks.append("Database/schema changes can affect persistence and require careful review.")
    if "auth" in role_text or "access" in role_text or "security" in role_text:
        risks.append("Auth/security changes can affect access control and require guard review.")
    if not target_files:
        risks.append("No concrete file target has been confirmed.")
    risks = [risk for i, risk in enumerate(risks) if risk and risk not in risks[:i]][:max(1, min(max_risks, 12))]

    validation_steps = list(context.validation_steps[:max_validation_steps])
    for hint in context.test_discovery_hints:
        if hint not in validation_steps:
            validation_steps.append(hint)
        if len(validation_steps) >= max(1, min(max_validation_steps, 12)):
            break
    for command in context.suggested_safe_commands:
        suggestion = f"Copy-only suggested command after future apply: {command}"
        if suggestion not in validation_steps:
            validation_steps.append(suggestion)
        if len(validation_steps) >= max(1, min(max_validation_steps, 12)):
            break
    for suggestion in test_suggestions:
        if suggestion not in validation_steps:
            validation_steps.append(suggestion)
        if len(validation_steps) >= max(1, min(max_validation_steps, 12)):
            break
    if not validation_steps:
        validation_steps = [
            "Review the inferred target file manually.",
            "Run Source of Truth guard before creating a patch proposal.",
            "Run targeted tests manually after any later apply.",
        ][:max(1, min(max_validation_steps, 12))]

    suggested_file_path = target_files[0] if target_files else ""
    suggested_old_text = ""
    warnings.append("Exact old_text was not inferred because no file content was read; operator must review the current file manually.")
    suggested_new_text = (
        "TODO: draft the minimal reviewed change after inspecting the current file content.\n\n"
        f"Patch intent: {patch_intent[:500]}"
    )

    ready_for_proposal = bool(target_files and patch_intent and not blockers)
    if ready_for_proposal:
        next_action = "Review suggested file, fill exact old_text/new_text manually, run guard, then create a guarded proposal."
    elif blockers:
        next_action = "Resolve blockers before using this draft in the patch proposal form."
    else:
        next_action = "Add operator narrowing, then review the draft before any guarded proposal."

    safety_notes = [
        "Draft only: no patch was applied.",
        "No proposal was created automatically.",
        "No provider call, command execution, test run, or file read was performed.",
        "Use the patch proposal form manually after reviewing exact old_text/new_text.",
    ]
    if context.repo_context_available:
        safety_notes.append("Repo-aware commands are copy-only suggestions; none were executed.")

    return StepAgentPatchDraftResponse(
        run_id=run_id,
        step_id=getattr(step, "id", ""),
        step_title=step_title,
        agent_role=context.agent_role,
        canonical_agent_id=context.canonical_agent_id,
        requirement_ids=context.requirement_ids,
        module_ids=context.module_ids,
        target_files=target_files,
        patch_intent=patch_intent[:800],
        draft_summary=draft_summary,
        suggested_file_path=suggested_file_path,
        suggested_old_text=suggested_old_text,
        suggested_new_text=suggested_new_text[:1200],
        risks=risks,
        validation_steps=validation_steps[:max(1, min(max_validation_steps, 12))],
        safety_notes=safety_notes,
        blockers=[item for i, item in enumerate(blockers) if item and item not in blockers[:i]][:12],
        warnings=[item for i, item in enumerate(warnings) if item and item not in warnings[:i]][:20],
        ready_for_proposal=ready_for_proposal,
        next_recommended_action=next_action,
        repo_context_available=context.repo_context_available,
        detected_stack=context.detected_stack,
        relevant_area_hints=context.relevant_area_hints,
        relevant_manifest_scripts=context.relevant_manifest_scripts,
        test_discovery_hints=context.test_discovery_hints,
        protected_path_warnings=context.protected_path_warnings,
        suggested_safe_commands=context.suggested_safe_commands,
    )


def _patch_draft_scalar(draft: dict, key: str, *, max_chars: int = 1200) -> tuple[str, bool]:
    if not isinstance(draft, dict):
        return "", False
    value = draft.get(key, "")
    if isinstance(value, (list, dict)):
        return "", False
    return _redact_patch_draft_text(value, max_chars=max_chars)


def _first_patch_draft_file(draft: dict) -> tuple[str, bool]:
    if not isinstance(draft, dict):
        return "", False
    selected, selected_redacted = _patch_draft_scalar(draft, "suggested_file_path", max_chars=180)
    if selected:
        return selected, selected_redacted
    files, files_redacted = _patch_draft_list(draft.get("target_files", []), limit=1, max_chars=180)
    return (files[0], files_redacted) if files else ("", files_redacted)


def build_step_patch_draft_proposal_preflight(
    *,
    run_id: str,
    step,
    request: StepPatchDraftGuardedProposalRequest,
    agent_step_context: DevelopmentRunStepContext | None = None,
) -> StepPatchDraftGuardedProposalResponse:
    """Validate a step patch draft before guarded proposal creation.

    Pure helper: no DB writes, provider calls, file reads, commands, proposal
    creation, apply, test execution, or run execution.
    """
    context = agent_step_context or normalize_development_run_step_context(getattr(step, "input", ""))
    draft = request.patch_draft if isinstance(request.patch_draft, dict) else {}
    blockers: list[str] = []
    warnings: list[str] = []

    selected_file_path, file_redacted = _redact_patch_draft_text(request.selected_file_path, max_chars=180)
    draft_file_path, draft_file_redacted = _first_patch_draft_file(draft)
    file_path = selected_file_path or draft_file_path

    selected_old_text, old_redacted = _redact_patch_draft_text(request.selected_old_text, max_chars=1200)
    draft_old_text, draft_old_redacted = _patch_draft_scalar(draft, "suggested_old_text", max_chars=1200)
    old_text = selected_old_text or draft_old_text

    selected_new_text, new_redacted = _redact_patch_draft_text(request.selected_new_text, max_chars=1200)
    draft_new_text, draft_new_redacted = _patch_draft_scalar(draft, "suggested_new_text", max_chars=1200)
    new_text = selected_new_text or draft_new_text

    operator_note, note_redacted = _redact_patch_draft_text(request.operator_note, max_chars=500)
    _, intent_redacted = _patch_draft_scalar(draft, "patch_intent", max_chars=600)
    _, summary_redacted = _patch_draft_scalar(draft, "draft_summary", max_chars=800)

    if any([
        file_redacted,
        draft_file_redacted,
        old_redacted,
        draft_old_redacted,
        new_redacted,
        draft_new_redacted,
        note_redacted,
        intent_redacted,
        summary_redacted,
    ]):
        blockers.append("Secret-like content was detected in draft/proposal fields; remove it before proposal creation.")

    if not file_path:
        blockers.append("selected_file_path is required before creating a guarded proposal.")
    else:
        safe, reason = _module_map_path_is_safe(file_path)
        if not safe:
            blockers.append(f"selected_file_path is unsafe: {reason}")
    if not new_text:
        blockers.append("selected_new_text is required before creating a guarded proposal.")
    if not old_text:
        blockers.append("selected_old_text is required so the guarded proposal targets an exact reviewed file span.")
    if context.provider_allowed or bool(draft.get("provider_allowed") is True):
        blockers.append("provider_allowed=true blocks guarded proposal creation from this step draft.")
    if str(getattr(step, "status", "") or "").lower() != "pending":
        blockers.append("Only pending run steps can create guarded proposals from step patch drafts.")
    if not context.canonical_agent_id:
        blockers.append("No canonical agent ID could be resolved for this step.")
    if not context.safety_gates:
        blockers.append("No safety gates found in the step context.")
    if request.allow_no_guard_override:
        blockers.append("No-guard override is not supported by this guarded proposal bridge; use the existing manual proposal flow if explicitly required.")

    if not context.requirement_ids:
        warnings.append("No requirement IDs are linked to this step; Source of Truth guard may warn.")
    if not context.module_ids:
        warnings.append("No module IDs are linked to this step; module awareness may be lower confidence.")
    if not context.validation_steps:
        warnings.append("No validation steps are linked to this step; operator should add manual checks before apply.")
    for warning in context.protected_path_warnings:
        warnings.append(f"Repo-aware protected path warning: {warning}")
    for command in context.suggested_safe_commands:
        warnings.append(f"Copy-only validation suggestion after future apply: {command}")
    if draft.get("ready_for_proposal") is False:
        warnings.append("Patch draft marked itself as not ready for proposal; review blockers before confirming.")
    if not selected_file_path and draft_file_path:
        warnings.append("Using draft suggested file path; operator should verify it before proposal creation.")
    if not selected_new_text and draft_new_text:
        warnings.append("Using draft suggested new_text; operator should review it before proposal creation.")

    blockers = [item for i, item in enumerate(blockers) if item and item not in blockers[:i]][:20]
    warnings = [item for i, item in enumerate(warnings) if item and item not in warnings[:i]][:20]

    if blockers:
        next_action = "Resolve preflight blockers, then run guarded proposal preflight again."
    elif request.confirm_create_proposal:
        next_action = "Create guarded proposal through the existing proposal path. Apply remains manual and separate."
    else:
        next_action = "Review preflight, then explicitly confirm proposal creation if the operator-selected fields are correct."

    patch_review = {
        "status": "not_run",
        "summary": "Patch review assistant was not run by this preflight; no file read was performed by this bridge.",
        "safe_to_create_proposal": not blockers,
        "safe_to_apply": False,
    }
    if context.repo_context_available:
        patch_review["repo_context_available"] = True
        patch_review["repo_validation_suggestions"] = context.suggested_safe_commands
        patch_review["repo_protected_path_warnings"] = context.protected_path_warnings
    if operator_note:
        patch_review["operator_note"] = operator_note

    return StepPatchDraftGuardedProposalResponse(
        run_id=run_id,
        step_id=getattr(step, "id", request.step_id),
        created=False,
        guard_decision="preflight_blocked" if blockers else "preflight_ready",
        patch_review=patch_review,
        blockers=blockers,
        warnings=warnings,
        safety_notes=[
            "Preflight only: no proposal was created unless confirm_create_proposal=true.",
            "No patch was applied.",
            "No tests were run.",
            "No provider call, command execution, file read, or run execution was performed.",
            "Apply still requires the existing explicit confirmation flow.",
        ],
        next_recommended_action=next_action,
        ready_for_apply=False,
    )


def _ctx_block_value_map(step_input: str, start: str, end: str) -> dict[str, str]:
    if start not in step_input:
        return {}
    block = step_input.split(start, 1)[1].split(end, 1)[0]
    values: dict[str, str] = {}
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        values[key.strip()] = value.strip()
    return values


def _ctx_value_map(step_input: str) -> dict[str, str]:
    return _ctx_block_value_map(
        step_input,
        "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
    )


def _repo_ctx_value_map(step_input: str) -> dict[str, str]:
    return _ctx_block_value_map(
        step_input,
        "AI_WORKBENCH_REPO_AWARE_CONTEXT",
        "END_AI_WORKBENCH_REPO_AWARE_CONTEXT",
    )


def _ctx_split(value: str, *, sep: str = ",", limit: int = _MAX_STEP_CONTEXT_LINKS) -> list[str]:
    if not value or value.lower() == "none":
        return []
    raw_items = value.split(sep)
    result: list[str] = []
    for item in raw_items:
        cleaned = _cqe_short(str(item).strip(), 120)
        if cleaned and cleaned.lower() != "none":
            result.append(cleaned)
    return result[:limit]


def _ctx_bool(value: str, default: bool = False) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"true", "1", "yes", "y"}


def _ctx_is_sensitive(*parts: object) -> bool:
    text = " ".join(str(part or "") for part in parts).lower()
    return any(term in text for term in _SENSITIVE_STEP_TERMS)


def normalize_development_run_step_context(step_input: str | dict) -> DevelopmentRunStepContext:
    """Parse and normalize the bounded development-run context block for one step."""
    if isinstance(step_input, dict):
        text = "\n".join(f"- {key}: {value}" for key, value in step_input.items())
        values = {str(key): str(value) for key, value in step_input.items()}
    else:
        text = str(step_input or "")
        values = _ctx_value_map(text)
    repo_values = _repo_ctx_value_map(text)

    source = _cqe_short(values.get("source", "") or "unknown", 80)
    agent_role = _cqe_short(values.get("agent_role", "") or "", 80)
    requirement_ids = _ctx_split(values.get("requirement_ids", ""), limit=_MAX_STEP_CONTEXT_LINKS)
    module_ids = _ctx_split(values.get("module_ids", ""), limit=_MAX_STEP_CONTEXT_LINKS)
    depends_on = _ctx_split(values.get("depends_on", ""), limit=_MAX_STEP_CONTEXT_LINKS)
    safety_gates = _ctx_split(values.get("safety_gates", ""), sep=";", limit=_MAX_STEP_CONTEXT_ITEMS)
    expected_outputs = _ctx_split(values.get("expected_outputs", ""), sep=";", limit=_MAX_STEP_CONTEXT_ITEMS)
    validation_steps = _ctx_split(values.get("validation_steps", ""), sep=";", limit=_MAX_STEP_CONTEXT_ITEMS)
    provider_allowed = _ctx_bool(values.get("provider_allowed", ""), default=False)
    manual = _ctx_bool(values.get("manual_approval_required", ""), default=False)
    sensitive = _ctx_is_sensitive(agent_role, " ".join(module_ids), text[:500])
    manual_approval_required = manual or sensitive
    risk_level = values.get("risk_level", "").strip().lower() or ("high" if manual_approval_required else "medium")
    if risk_level not in {"low", "medium", "high", "critical"}:
        risk_level = "high" if manual_approval_required else "medium"
    canonical_agent_id = canonical_agent_id_for_role(agent_role or values.get("agent_id", ""))

    if provider_allowed:
        next_action = "Resolve provider_allowed=true before preparing this step for agent execution."
    elif repo_values.get("recommended_first_safe_action"):
        next_action = repo_values.get("recommended_first_safe_action", "")[:220]
    elif manual_approval_required:
        next_action = "Review manual approval requirements, then open the agent execution context in dry-run mode."
    elif not requirement_ids or not module_ids:
        next_action = "Review missing requirement/module links, then open the agent execution context in dry-run mode."
    else:
        next_action = "Open the agent execution context in dry-run mode; no provider call is required."

    return DevelopmentRunStepContext(
        source=source,
        agent_role=agent_role,
        canonical_agent_id=canonical_agent_id,
        requirement_ids=requirement_ids,
        module_ids=module_ids,
        depends_on=depends_on,
        safety_gates=safety_gates,
        manual_approval_required=manual_approval_required,
        provider_allowed=provider_allowed,
        expected_outputs=expected_outputs,
        validation_steps=validation_steps,
        risk_level=risk_level,
        next_safe_action=next_action,
        repo_context_available=bool(repo_values),
        detected_stack=_ctx_split(repo_values.get("detected_stack", ""), limit=8),
        detected_project_type=_cqe_short(repo_values.get("detected_project_type", "") or "", 80) or None,
        relevant_area_hints=_ctx_split(repo_values.get("relevant_area_hints", ""), sep=";", limit=8),
        relevant_manifest_scripts=_ctx_split(repo_values.get("relevant_manifest_scripts", ""), sep=";", limit=8),
        test_discovery_hints=_ctx_split(repo_values.get("test_discovery_hints", ""), sep=";", limit=8),
        protected_path_warnings=_ctx_split(repo_values.get("protected_path_warnings", ""), sep=";", limit=8),
        suggested_safe_commands=_ctx_split(repo_values.get("suggested_safe_commands", ""), sep=";", limit=8),
        repo_safety_notes=_ctx_split(repo_values.get("safety_notes", ""), sep=";", limit=8),
        repo_limitations=_ctx_split(repo_values.get("limitations", ""), sep=";", limit=8),
    )


def build_pending_run_step_inputs_from_development_preview(
    development_run_preview: dict,
    repo_intake_preview: dict | None = None,
) -> list[dict]:
    """Convert development run preview steps into safe pending step metadata.

    Each returned dict has:
      title, agent_role, agent_id, input_text,
      requirement_ids, module_ids, depends_on,
      manual_approval_required, provider_allowed, safety_gates.

    Pure function — no DB access, no provider calls, no file reads.
    Bounded: at most _MAX_BRIDGE_STEPS steps, each input capped at _MAX_BRIDGE_STEP_INPUT chars.
    """
    raw_steps = list(development_run_preview.get("steps", []))[:_MAX_BRIDGE_STEPS]
    repo_snapshot = build_repo_aware_run_context_snapshot(repo_intake_preview)
    results: list[dict] = []

    for step in raw_steps:
        title = str(step.get("title", "Unnamed step"))[:200]
        description = str(step.get("description", ""))[:800]
        agent_role = str(step.get("agent_role", ""))[:80]
        requirement_ids: list[str] = [str(r)[:80] for r in (step.get("requirement_ids") or [])][:10]
        module_ids: list[str] = [str(m)[:80] for m in (step.get("module_ids") or [])][:10]
        depends_on: list[str] = [str(d)[:80] for d in (step.get("depends_on") or [])][:10]
        expected_outputs: list[str] = [str(o)[:200] for o in (step.get("expected_outputs") or [])][:5]
        validation_steps: list[str] = [str(v)[:200] for v in (step.get("validation_steps") or [])][:5]
        safety_gates: list[str] = [str(g)[:200] for g in (step.get("safety_gates") or [])][:5]
        manual_approval_required: bool = bool(step.get("manual_approval_required", False))
        provider_allowed: bool = False  # hardcoded — never True in this flow

        # Build context block for embedding in RunStep.input.
        ctx_lines = [
            "AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
            f"- source: intake_confirmed_development_run",
            f"- agent_role: {agent_role or 'unassigned'}",
            f"- requirement_ids: {', '.join(requirement_ids) if requirement_ids else 'none'}",
            f"- module_ids: {', '.join(module_ids) if module_ids else 'none'}",
            f"- depends_on: {', '.join(depends_on) if depends_on else 'none'}",
            f"- safety_gates: {'; '.join(safety_gates) if safety_gates else 'none'}",
            f"- manual_approval_required: {str(manual_approval_required).lower()}",
            f"- provider_allowed: false",
            f"- expected_outputs: {'; '.join(expected_outputs) if expected_outputs else 'none'}",
            f"- validation_steps: {'; '.join(validation_steps) if validation_steps else 'none'}",
            "END_AI_WORKBENCH_DEVELOPMENT_RUN_CONTEXT",
        ]
        context_block = "\n".join(ctx_lines)
        repo_step_context = build_repo_aware_step_context_for_preview_step(step, repo_snapshot)
        repo_block = _repo_context_block(repo_step_context)

        parts = [description, context_block]
        if repo_block:
            parts.append(repo_block)
        if manual_approval_required:
            parts.append("[Manual approval required before execution]")

        input_text = "\n\n".join(p for p in parts if p)[:_MAX_BRIDGE_STEP_INPUT]

        # Map agent_role to a canonical registry agent_id.
        # Falls back to "orchestrator" if no match — never an empty string.
        agent_id = canonical_agent_id_for_role(agent_role)

        results.append({
            "title": title,
            "agent_role": agent_role,
            "agent_id": agent_id,
            "input_text": input_text,
            "requirement_ids": requirement_ids,
            "module_ids": module_ids,
            "depends_on": depends_on,
            "manual_approval_required": manual_approval_required,
            "provider_allowed": provider_allowed,
            "safety_gates": safety_gates,
        })

    return results


def build_confirmed_development_run_creation_input(
    req: ConfirmedDevelopmentRunCreateRequest,
) -> tuple:
    """Evaluate the confirmed run creation contract for this bridge request.

    Returns (ConfirmedRunCreationInput, ConfirmedRunCreationContractResult).
    Pure function — no DB, no providers, no filesystem I/O.
    """
    from src.release.confirmed_development_run_creation_contract import (
        ConfirmedRunCreationInput,
        evaluate_confirmed_run_creation_contract,
    )

    preview = req.development_run_preview
    run_title = str(preview.get("run_title", ""))
    run_goal = str(preview.get("run_goal", ""))
    recommended_run_mode = str(preview.get("recommended_run_mode", "guided"))
    steps = list(preview.get("steps", []))

    raw_validation = preview.get("validation", {})
    if isinstance(raw_validation, dict):
        development_preview_valid = bool(raw_validation.get("ready_to_create_run", False))
    else:
        development_preview_valid = False

    # All five confirmation booleans must be true for the contract to accept.
    # Map them into the contract input: confirm=True only if ALL booleans are set.
    all_confirmed = (
        req.confirm_create
        and req.contract_confirmed
        and req.source_of_truth_confirmed
        and req.module_map_confirmed
        and req.provider_disabled_confirmed
        and req.later_actions_confirmed
    )

    inp = ConfirmedRunCreationInput(
        project_id=req.project_id if req.project_id and req.project_id.strip() else None,
        confirm=all_confirmed,
        preview_only=False,   # This is the actual creation path
        run_title=run_title,
        run_goal=run_goal,
        recommended_run_mode=recommended_run_mode,
        steps=steps,
        source_of_truth_valid=req.source_of_truth_confirmed,
        module_map_valid=req.module_map_confirmed,
        multi_agent_plan_valid=bool(steps),
        development_preview_valid=development_preview_valid,
    )

    result = evaluate_confirmed_run_creation_contract(inp)
    return inp, result

"""Pure source-of-truth contract for project mission and requirements.

The contract captures the user's intent, client specification, existing project
goal, requirements, constraints, acceptance criteria, and anti-drift rules.
It intentionally performs no DB access, file scanning, tool execution, provider
calls, or runtime state mutation.
"""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────


class ProjectInputSourceType(str, enum.Enum):
    CLIENT_SPEC = "client_spec"
    COMMERCIAL_PROPOSAL = "commercial_proposal"
    EXISTING_PROJECT = "existing_project"
    NEW_IDEA = "new_idea"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class RequirementPriority(str, enum.Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"
    UNKNOWN = "unknown"


class RequirementStatus(str, enum.Enum):
    PROPOSED = "proposed"
    CONFIRMED = "confirmed"
    ASSUMED = "assumed"
    MISSING = "missing"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    NEEDS_VALIDATION = "needs_validation"


class DriftRiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AcceptanceStatus(str, enum.Enum):
    NOT_CHECKED = "not_checked"
    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    FAILED = "failed"
    BLOCKED = "blocked"


# ── Guardrails ───────────────────────────────────────────────────────────────


_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)",
    re.IGNORECASE,
)
_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_-]?key|private[_-]?key|access[_-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _contains_secret_assignment(value: str) -> bool:
    return bool(_SENSITIVE_VALUE_RE.search(value))


def _validate_safe_metadata(value: Any, path: str = "source_metadata") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            if _SENSITIVE_KEY_RE.search(key_text):
                raise ValueError(f"{path}.{key_text} must not store secret-like keys")
            _validate_safe_metadata(nested, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            _validate_safe_metadata(nested, f"{path}[{index}]")
    elif isinstance(value, str) and _contains_secret_assignment(value):
        raise ValueError(f"{path} must not store secret-like values")


def _matches_forbidden_area(path: str, forbidden_area: str) -> bool:
    normalized_path = path.strip().lower()
    normalized_area = forbidden_area.strip().lower().rstrip("/")
    if not normalized_area:
        return False
    return normalized_path == normalized_area or normalized_path.startswith(normalized_area + "/")


# ── Contract models ──────────────────────────────────────────────────────────


class ProjectMissionContract(BaseModel):
    source_type: ProjectInputSourceType
    raw_source_summary: str = ""
    project_name: Optional[str] = None
    product_goal: str = ""
    target_users: list[str] = Field(default_factory=list)
    user_roles: list[str] = Field(default_factory=list)


class ProjectRequirementContract(BaseModel):
    id: str
    title: str
    description: str = ""
    priority: RequirementPriority = RequirementPriority.UNKNOWN
    status: RequirementStatus = RequirementStatus.PROPOSED
    source_refs: list[str] = Field(default_factory=list)
    acceptance_criteria_ids: list[str] = Field(default_factory=list)
    conflicts_with: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ProjectConstraintContract(BaseModel):
    id: str
    title: str
    description: str = ""
    forbidden_paths: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    reason: str = ""


class ProjectAcceptanceCriterion(BaseModel):
    id: str
    description: str
    requirement_id: Optional[str] = None
    status: AcceptanceStatus = AcceptanceStatus.NOT_CHECKED
    verification_hint: Optional[str] = None


class ProjectAntiDriftRule(BaseModel):
    id: str
    title: str
    description: str = ""
    risk_level: DriftRiskLevel = DriftRiskLevel.MEDIUM
    forbidden_patterns: list[str] = Field(default_factory=list)
    require_requirement_link: bool = True


class ProjectSourceOfTruthContract(BaseModel):
    id: str
    source_type: ProjectInputSourceType = ProjectInputSourceType.UNKNOWN
    raw_source_summary: str = ""
    project_name: Optional[str] = None
    product_goal: str = ""
    target_users: list[str] = Field(default_factory=list)
    user_roles: list[str] = Field(default_factory=list)
    core_features: list[str] = Field(default_factory=list)
    requirements: list[ProjectRequirementContract] = Field(default_factory=list)
    constraints: list[ProjectConstraintContract] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    acceptance_criteria: list[ProjectAcceptanceCriterion] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    anti_drift_rules: list[ProjectAntiDriftRule] = Field(default_factory=list)
    definition_of_done: list[str] = Field(default_factory=list)
    created_from: Optional[str] = None
    confidence: str = "low"
    readiness: str = "draft"
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
    updated_at: Optional[str] = None

    @field_validator("source_metadata")
    @classmethod
    def _source_metadata_has_no_secret_values(cls, value: dict[str, Any]) -> dict[str, Any]:
        _validate_safe_metadata(value)
        return value


class SourceOfTruthValidationResult(BaseModel):
    valid: bool
    drift_risk: DriftRiskLevel = DriftRiskLevel.LOW
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RequirementCoverageItem(BaseModel):
    requirement_id: str
    title: str
    priority: RequirementPriority
    status: RequirementStatus
    linked_plan_item_ids: list[str] = Field(default_factory=list)
    acceptance_status: AcceptanceStatus = AcceptanceStatus.NOT_CHECKED
    covered: bool = False
    notes: str = ""


class RequirementCoverageMatrix(BaseModel):
    source_of_truth_id: str
    items: list[RequirementCoverageItem] = Field(default_factory=list)
    missing_requirement_ids: list[str] = Field(default_factory=list)
    unlinked_plan_item_ids: list[str] = Field(default_factory=list)
    coverage_score: float = 0.0
    drift_risk: DriftRiskLevel = DriftRiskLevel.LOW


# ── Pure helpers ─────────────────────────────────────────────────────────────


def validate_source_of_truth_contract(
    source: ProjectSourceOfTruthContract,
) -> SourceOfTruthValidationResult:
    """Validate source-of-truth completeness and consistency."""

    errors: list[str] = []
    warnings: list[str] = []

    if not source.product_goal.strip():
        errors.append("Project mission/product_goal is empty")
    if not source.target_users:
        errors.append("Target users are missing")
    if not any(req.priority == RequirementPriority.MUST for req in source.requirements):
        errors.append("At least one mandatory requirement is required")
    if not source.acceptance_criteria:
        errors.append("Acceptance criteria are missing")
    if not source.definition_of_done:
        warnings.append("Definition of done is missing")

    requirement_ids = {req.id for req in source.requirements}
    duplicate_requirement_ids = {
        req.id
        for req in source.requirements
        if [item.id for item in source.requirements].count(req.id) > 1
    }
    for requirement_id in sorted(duplicate_requirement_ids):
        errors.append(f"Duplicate requirement id: {requirement_id}")

    for req in source.requirements:
        if req.priority == RequirementPriority.UNKNOWN:
            errors.append(f"Requirement {req.id} has unknown priority")
        for conflict_id in req.conflicts_with:
            if conflict_id not in requirement_ids:
                warnings.append(f"Requirement {req.id} conflicts with unknown requirement {conflict_id}")
            else:
                errors.append(f"Requirement {req.id} conflicts with {conflict_id}")

    for criterion in source.acceptance_criteria:
        if criterion.requirement_id and criterion.requirement_id not in requirement_ids:
            warnings.append(f"Acceptance criterion {criterion.id} links to unknown requirement {criterion.requirement_id}")

    risk = DriftRiskLevel.CRITICAL if errors else DriftRiskLevel.MEDIUM if warnings else DriftRiskLevel.LOW
    return SourceOfTruthValidationResult(
        valid=not errors,
        drift_risk=risk,
        errors=errors,
        warnings=warnings,
    )


def summarize_source_of_truth(source: ProjectSourceOfTruthContract) -> str:
    """Return a concise mission/requirements summary for reports."""

    mandatory = [req for req in source.requirements if req.priority == RequirementPriority.MUST]
    return (
        f"{source.project_name or 'Unnamed project'} from {source.source_type.value}: "
        f"{source.product_goal or 'missing mission'}. "
        f"{len(source.target_users)} target users, {len(source.requirements)} requirements, "
        f"{len(mandatory)} mandatory, {len(source.acceptance_criteria)} acceptance criteria."
    )


def build_requirement_coverage_matrix(
    source: ProjectSourceOfTruthContract,
    plan_requirement_links: Optional[dict[str, list[str]]] = None,
    acceptance_status_by_requirement: Optional[dict[str, AcceptanceStatus]] = None,
) -> RequirementCoverageMatrix:
    """Build coverage between requirements and future plan/step ids.

    plan_requirement_links maps plan item ids to requirement ids.
    """

    links = plan_requirement_links or {}
    acceptance_statuses = acceptance_status_by_requirement or {}
    known_requirement_ids = {req.id for req in source.requirements}
    linked_by_requirement: dict[str, list[str]] = {req.id: [] for req in source.requirements}
    unlinked_plan_item_ids: list[str] = []

    for plan_item_id, requirement_ids in links.items():
        matched = False
        for requirement_id in requirement_ids:
            if requirement_id in linked_by_requirement:
                linked_by_requirement[requirement_id].append(plan_item_id)
                matched = True
        if not matched:
            unlinked_plan_item_ids.append(plan_item_id)

    items: list[RequirementCoverageItem] = []
    missing: list[str] = []
    for req in source.requirements:
        linked_plan_items = linked_by_requirement.get(req.id, [])
        covered = bool(linked_plan_items)
        if (
            req.priority != RequirementPriority.WONT
            and req.status != RequirementStatus.REJECTED
            and not covered
        ):
            missing.append(req.id)
        items.append(RequirementCoverageItem(
            requirement_id=req.id,
            title=req.title,
            priority=req.priority,
            status=req.status,
            linked_plan_item_ids=linked_plan_items,
            acceptance_status=acceptance_statuses.get(req.id, AcceptanceStatus.NOT_CHECKED),
            covered=covered,
            notes="" if covered else "No linked plan item",
        ))

    coverage_score = 0.0
    if source.requirements:
        coverage_score = len([item for item in items if item.covered]) / len(source.requirements)

    if missing or unlinked_plan_item_ids:
        risk = DriftRiskLevel.HIGH
    elif coverage_score < 1.0:
        risk = DriftRiskLevel.MEDIUM
    else:
        risk = DriftRiskLevel.LOW

    return RequirementCoverageMatrix(
        source_of_truth_id=source.id,
        items=items,
        missing_requirement_ids=missing,
        unlinked_plan_item_ids=unlinked_plan_item_ids,
        coverage_score=coverage_score,
        drift_risk=risk,
    )


def detect_drift_risk(
    source: ProjectSourceOfTruthContract,
    *,
    linked_requirement_ids: Optional[list[str]] = None,
    touched_paths: Optional[list[str]] = None,
    plan_item_id: Optional[str] = None,
) -> SourceOfTruthValidationResult:
    """Detect whether a proposed plan/step drifts from source-of-truth."""

    errors: list[str] = []
    warnings: list[str] = []
    links = linked_requirement_ids or []
    paths = touched_paths or []
    known_requirement_ids = {req.id for req in source.requirements}

    if not links:
        errors.append(f"Plan item {plan_item_id or '<unknown>'} has no linked requirement")
    for requirement_id in links:
        if requirement_id not in known_requirement_ids:
            errors.append(f"Plan item {plan_item_id or '<unknown>'} links to unknown requirement {requirement_id}")

    forbidden_areas: list[str] = list(source.forbidden_changes)
    for constraint in source.constraints:
        forbidden_areas.extend(constraint.forbidden_paths)
    for path in paths:
        for forbidden_area in forbidden_areas:
            if _matches_forbidden_area(path, forbidden_area):
                errors.append(f"Proposed change touches forbidden area: {path}")

    for rule in source.anti_drift_rules:
        if rule.require_requirement_link and not links:
            warnings.append(f"Anti-drift rule {rule.id} requires requirement links")
        for pattern in rule.forbidden_patterns:
            for path in paths:
                if re.search(pattern, path, re.IGNORECASE):
                    errors.append(f"Anti-drift rule {rule.id} matched forbidden pattern for {path}")

    if any("forbidden" in error.lower() for error in errors):
        risk = DriftRiskLevel.CRITICAL
    elif errors:
        risk = DriftRiskLevel.HIGH
    elif warnings:
        risk = DriftRiskLevel.MEDIUM
    else:
        risk = DriftRiskLevel.LOW

    return SourceOfTruthValidationResult(
        valid=not errors,
        drift_risk=risk,
        errors=errors,
        warnings=warnings,
    )

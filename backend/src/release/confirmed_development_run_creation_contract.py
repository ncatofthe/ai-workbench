"""Pure Confirmed Development Run Creation Contract v1.

This module defines the formal safety contract for converting an
IntakeDevelopmentRunPreviewResponse into a real confirmed development run.

Contract only — no database, routes, engines, providers, filesystem I/O,
subprocesses, or runtime side effects of any kind.  Importing this module
is safe in any context.

Key questions answered:
  - What inputs are required?
  - What must be valid?
  - What confirmation is required?
  - What may be created?
  - What must NOT be created?
  - What statuses must be used?
  - What safety gates are mandatory?
  - What data links must be preserved?
  - What still requires manual operator action?
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_BLOCKERS = 20
_MAX_WARNINGS = 30
_MAX_REQUIREMENTS = 20
_MAX_SAFETY_GATES = 15
_MAX_OPERATOR_CONFIRMATIONS = 10

# Matches key=value / key:value patterns for known secret field names.
# Mirrors the _SOT_SENSITIVE_VALUE_RE in models.py — kept local to avoid
# any cross-module import chain.
_CONTRACT_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)"
    r"\s*[:=]\s*\S+",
    re.IGNORECASE,
)

# Matches database URL patterns that embed credentials.
_CONTRACT_DATABASE_URL_WITH_CREDS_RE = re.compile(
    r"(postgres|mysql|mongodb|redis|sqlite)(\+\w+)?://[^@\s]+:[^@\s]+@",
    re.IGNORECASE,
)

# Matches language that implies execution has already happened or will happen
# automatically during run creation — forbidden in step titles/descriptions.
_EXECUTION_LANGUAGE_RE = re.compile(
    r"\b(execute(?:\s+now)?|apply[\s_]patch|run[\s_]tests[\s_]now|"
    r"auto[\s_]?run|auto[\s_]?start|auto[\s_]?deploy|"
    r"call[\s_]provider|invoke[\s_]model|trigger[\s_]agent)\b",
    re.IGNORECASE,
)

# Risky module keywords that elevate manual-approval warnings.
_RISKY_MODULE_KEYWORDS = frozenset({
    "auth", "authentication", "authorization",
    "database", "migration", "schema",
    "deployment", "deploy", "infra", "infrastructure",
    "security", "rbac", "permission",
})


# ── Enums ─────────────────────────────────────────────────────────────────────


class ConfirmedRunCreationDecision(str, Enum):
    """Top-level creation decision."""

    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


class ConfirmedRunCreationRisk(str, Enum):
    """Overall risk level for the creation attempt."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ConfirmedRunCreationMode(str, Enum):
    """Operational mode for the creation request."""

    PREVIEW_ONLY = "preview_only"
    CONFIRM_CREATE_PENDING_RUN = "confirm_create_pending_run"
    UNSUPPORTED = "unsupported"


class ConfirmedRunCreatedEntity(str, Enum):
    """Entities that may or may not be created during confirmed run creation."""

    PROJECT = "project"
    RUN = "run"
    RUN_STEP = "run_step"
    TOOL_CALL = "tool_call"
    PROVIDER_CALL = "provider_call"
    PATCH_PROPOSAL = "patch_proposal"
    COMMAND_EXECUTION = "command_execution"


# ── Input / Result models ─────────────────────────────────────────────────────


@dataclass
class ConfirmedRunCreationInput:
    """Normalised inputs for evaluating the confirmed run creation contract."""

    project_id: str | None = None
    confirm: bool = False
    preview_only: bool = True
    run_title: str = ""
    run_goal: str = ""
    recommended_run_mode: str = "guided"
    steps: list[dict] = field(default_factory=list)
    source_of_truth_valid: bool = False
    module_map_valid: bool = False
    multi_agent_plan_valid: bool = False
    development_preview_valid: bool = False


@dataclass
class ConfirmedRunCreationRequirement:
    """A single verifiable requirement for confirmed run creation."""

    id: str
    description: str
    required: bool = True
    satisfied: bool = False
    severity: str = "error"


@dataclass
class ConfirmedRunCreationSafetyGate:
    """A safety gate that must be respected during or before run creation."""

    id: str
    title: str
    description: str
    required_before_creation: bool = True
    required_before_execution: bool = True


@dataclass
class ConfirmedRunCreationContractResult:
    """Full result of evaluating the confirmed run creation contract."""

    decision: ConfirmedRunCreationDecision
    risk: ConfirmedRunCreationRisk
    can_create_pending_run: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    requirements: list[ConfirmedRunCreationRequirement] = field(default_factory=list)
    safety_gates: list[ConfirmedRunCreationSafetyGate] = field(default_factory=list)
    allowed_created_entities: list[ConfirmedRunCreatedEntity] = field(default_factory=list)
    forbidden_created_entities: list[ConfirmedRunCreatedEntity] = field(default_factory=list)
    required_statuses: dict[str, str] = field(default_factory=dict)
    required_operator_confirmations: list[str] = field(default_factory=list)
    next_recommended_action: str = ""


# ── Internal helpers ──────────────────────────────────────────────────────────


def _contract_contains_secret(text: str) -> bool:
    """Return True if text contains a secret-like pattern."""
    return bool(
        _CONTRACT_SENSITIVE_VALUE_RE.search(text)
        or _CONTRACT_DATABASE_URL_WITH_CREDS_RE.search(text)
    )


def _steps_contain_provider_allowed(steps: list[dict]) -> bool:
    """Return True if any step dict has provider_allowed=True."""
    return any(bool(step.get("provider_allowed", False)) for step in steps)


def _steps_full_text(steps: list[dict]) -> str:
    """Return a single string joining all step title/description values."""
    parts: list[str] = []
    for step in steps:
        parts.append(str(step.get("title", "")))
        parts.append(str(step.get("description", "")))
    return " ".join(parts)


def _steps_have_execution_language(steps: list[dict]) -> bool:
    """Return True if step titles/descriptions imply automatic execution."""
    return bool(_EXECUTION_LANGUAGE_RE.search(_steps_full_text(steps)))


def _steps_have_any_requirement_ids(steps: list[dict]) -> bool:
    return any(bool(step.get("requirement_ids")) for step in steps)


def _steps_have_any_module_ids(steps: list[dict]) -> bool:
    return any(bool(step.get("module_ids")) for step in steps)


def _steps_have_any_validation_steps(steps: list[dict]) -> bool:
    return any(bool(step.get("validation_steps")) for step in steps)


def _steps_reference_risky_modules(steps: list[dict]) -> bool:
    """Return True if any step title or description references a risky module."""
    text = _steps_full_text(steps).lower()
    return any(kw in text for kw in _RISKY_MODULE_KEYWORDS)


# ── Public builders ───────────────────────────────────────────────────────────


def build_confirmed_run_creation_requirements(
    inp: ConfirmedRunCreationInput,
) -> list[ConfirmedRunCreationRequirement]:
    """Build the full list of contract requirements for *inp*.

    Required requirements (severity='error') must all be satisfied for creation
    to be ALLOWED.  Optional requirements (severity='warning') produce warnings.
    """
    title_goal = (inp.run_title or "") + " " + (inp.run_goal or "")
    return [
        # ── Hard blockers ──────────────────────────────────────────────────
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-001",
            description="project_id must be non-empty.",
            required=True,
            satisfied=bool(inp.project_id and inp.project_id.strip()),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-002",
            description=(
                "confirm must be True — explicit operator opt-in is required "
                "before any run or step is persisted."
            ),
            required=True,
            satisfied=inp.confirm,
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-003",
            description=(
                "preview_only must be False for actual run creation. "
                "preview_only=True signals this is still a preview request."
            ),
            required=True,
            satisfied=not inp.preview_only,
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-004",
            description="run_title must be a non-empty string.",
            required=True,
            satisfied=bool(inp.run_title and inp.run_title.strip()),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-005",
            description="run_goal must be a non-empty string.",
            required=True,
            satisfied=bool(inp.run_goal and inp.run_goal.strip()),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-006",
            description=(
                "At least one step must be present in the development preview. "
                "An empty steps list cannot produce a meaningful run."
            ),
            required=True,
            satisfied=bool(inp.steps),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-007",
            description=(
                "development_preview_valid must be True. "
                "The upstream IntakeDevelopmentRunPreviewResponse must have "
                "validation.ready_to_create_run=True before creation is attempted."
            ),
            required=True,
            satisfied=inp.development_preview_valid,
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-008",
            description=(
                "No step may have provider_allowed=True. "
                "Provider interaction is forbidden during pending run and step creation."
            ),
            required=True,
            satisfied=not _steps_contain_provider_allowed(inp.steps),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-009",
            description=(
                "No step title or description may contain execution-like language "
                "(e.g. 'execute now', 'apply_patch', 'auto-run', 'trigger_agent'). "
                "Steps describe future planned work, not immediate actions."
            ),
            required=True,
            satisfied=not _steps_have_execution_language(inp.steps),
            severity="error",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-010",
            description=(
                "run_title and run_goal must not contain secret-like content "
                "(passwords, tokens, API keys, database connection strings with credentials)."
            ),
            required=True,
            satisfied=not _contract_contains_secret(title_goal),
            severity="error",
        ),
        # ── Advisory / warnings ────────────────────────────────────────────
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-011",
            description=(
                "Source of Truth should be valid before run creation. "
                "Run creation is still allowed but quality traceability is reduced."
            ),
            required=False,
            satisfied=inp.source_of_truth_valid,
            severity="warning",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-012",
            description=(
                "Module Map should be valid before run creation. "
                "Run creation is still allowed but module boundary tracking is missing."
            ),
            required=False,
            satisfied=inp.module_map_valid,
            severity="warning",
        ),
        ConfirmedRunCreationRequirement(
            id="REQ-CRC-013",
            description=(
                "Multi-Agent Plan should be valid before run creation. "
                "Run creation is still allowed but agent assignment may be imprecise."
            ),
            required=False,
            satisfied=inp.multi_agent_plan_valid,
            severity="warning",
        ),
    ]


def build_confirmed_run_creation_safety_gates(
    inp: ConfirmedRunCreationInput,  # noqa: ARG001 — reserved for future per-input gates
) -> list[ConfirmedRunCreationSafetyGate]:
    """Return the mandatory safety gates that govern confirmed run creation."""
    return [
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-001",
            title="No auto-start",
            description=(
                "The created run must not start automatically. "
                "It must remain in 'pending' status until an operator explicitly "
                "triggers execution via the Start Task action."
            ),
            required_before_creation=True,
            required_before_execution=True,
        ),
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-002",
            title="No provider calls",
            description=(
                "No provider (Ollama, Claude, Codex) may be called during run "
                "or step creation.  Provider interaction is only permitted after "
                "an operator explicitly starts a task step."
            ),
            required_before_creation=True,
            required_before_execution=True,
        ),
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-003",
            title="No tool_call creation",
            description=(
                "No tool_call records may be created during confirmed run creation. "
                "Tool calls are only permitted after operator approval during "
                "a live task execution step."
            ),
            required_before_creation=True,
            required_before_execution=True,
        ),
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-004",
            title="No patch, apply, or test execution",
            description=(
                "No file patches may be applied, no apply_patch actions executed, "
                "and no automated test runs triggered during run or step creation. "
                "These actions require a separate, explicit operator instruction."
            ),
            required_before_creation=True,
            required_before_execution=True,
        ),
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-005",
            title="Manual approval required before risky step execution",
            description=(
                "Any step with manual_approval_required=True must not be executed "
                "until an operator has explicitly approved it via the approval workflow. "
                "This gate is enforced at execution time, not at creation time."
            ),
            required_before_creation=False,
            required_before_execution=True,
        ),
        ConfirmedRunCreationSafetyGate(
            id="GATE-CRC-006",
            title="Guard check required before patch proposals",
            description=(
                "Before any patch proposal is created in a future execution step, "
                "the Source of Truth guard must be consulted and must return 'allowed'. "
                "Guard bypass is forbidden."
            ),
            required_before_creation=False,
            required_before_execution=True,
        ),
    ]


def build_allowed_created_entities(
    inp: ConfirmedRunCreationInput,  # noqa: ARG001 — reserved for future conditional logic
) -> list[ConfirmedRunCreatedEntity]:
    """Return the entity types that may be created during confirmed run creation.

    Only Run and RunStep records are permitted.  All other entity types
    (project, tool_call, provider_call, patch_proposal, command_execution)
    are strictly forbidden.
    """
    return [
        ConfirmedRunCreatedEntity.RUN,
        ConfirmedRunCreatedEntity.RUN_STEP,
    ]


def build_forbidden_created_entities() -> list[ConfirmedRunCreatedEntity]:
    """Return the entity types that must NOT be created during confirmed run creation."""
    return [
        ConfirmedRunCreatedEntity.PROJECT,
        ConfirmedRunCreatedEntity.TOOL_CALL,
        ConfirmedRunCreatedEntity.PROVIDER_CALL,
        ConfirmedRunCreatedEntity.PATCH_PROPOSAL,
        ConfirmedRunCreatedEntity.COMMAND_EXECUTION,
    ]


def build_required_confirmed_run_statuses() -> dict[str, str]:
    """Return the required status values for all created run entities.

    These statuses guarantee that no work begins until an operator explicitly
    triggers a step.
    """
    return {
        "run": "pending",
        "run_step": "pending",
        "provider_allowed": "false",
        "execution": "not_started",
        "run_mode": "offline",
    }


def build_confirmed_run_creation_operator_checklist() -> list[str]:
    """Return the ordered list of operator confirmations required for run creation.

    Each item represents a deliberate, human acknowledgement that must precede
    the creation request.  Automated systems must not bypass these.
    """
    return [
        "Confirm explicit real-run creation (confirm=True is required; no implicit creation).",
        "Confirm Source of Truth is reviewed and ready for this development context.",
        "Confirm Module Map is reviewed and ready for this development context.",
        "Confirm all provider calls remain disabled (provider_allowed=False on all steps).",
        "Confirm that apply, test, and run commands require a later explicit operator action.",
        "Confirm backup or restore expectations if the attached project has sensitive or "
        "irreplaceable data.",
    ]


def redact_confirmed_run_creation_preview_for_report(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Recursively redact secret-like values from *payload* before logging/reporting.

    Preserves the full structure and all non-secret values.
    Keys are never redacted — only string values are inspected.

    Pure function — no I/O, no side effects.
    """
    _REDACTED = "[REDACTED]"

    def _redact(v: Any) -> Any:
        if isinstance(v, str):
            return _REDACTED if _contract_contains_secret(v) else v
        if isinstance(v, dict):
            return {k: _redact(val) for k, val in v.items()}
        if isinstance(v, list):
            return [_redact(item) for item in v]
        return v

    return {k: _redact(v) for k, v in payload.items()}


# ── Main evaluator ────────────────────────────────────────────────────────────


def evaluate_confirmed_run_creation_contract(
    inp: ConfirmedRunCreationInput,
) -> ConfirmedRunCreationContractResult:
    """Evaluate whether a confirmed development run creation is permissible.

    Pure function.  No side effects, no persistence, no network or filesystem I/O.

    Decision logic:
      BLOCKED  — one or more hard requirements are not satisfied.
      WARNING  — all hard requirements satisfied, but advisory issues exist.
      ALLOWED  — all requirements satisfied and no advisories.

    Returns a ConfirmedRunCreationContractResult with full rationale.
    """
    requirements = build_confirmed_run_creation_requirements(inp)
    safety_gates = build_confirmed_run_creation_safety_gates(inp)
    allowed_entities = build_allowed_created_entities(inp)
    forbidden_entities = build_forbidden_created_entities()
    required_statuses = build_required_confirmed_run_statuses()
    operator_confirmations = build_confirmed_run_creation_operator_checklist()

    blockers: list[str] = []
    warnings: list[str] = []

    # Evaluate requirements.
    for req in requirements:
        if req.required and not req.satisfied:
            blockers.append(f"[{req.id}] {req.description}")
        elif not req.required and not req.satisfied:
            warnings.append(f"[{req.id}] {req.description}")

    # Additional step-level advisory checks (only when steps are present
    # and hard requirements haven't already fired on missing steps).
    if inp.steps:
        if not _steps_have_any_requirement_ids(inp.steps):
            warnings.append(
                "[WARN-CRC-001] No requirement_ids linked to any step — "
                "traceability to the Source of Truth is reduced."
            )
        if not _steps_have_any_module_ids(inp.steps):
            warnings.append(
                "[WARN-CRC-002] No module_ids linked to any step — "
                "module boundary tracking is missing."
            )
        if not _steps_have_any_validation_steps(inp.steps):
            warnings.append(
                "[WARN-CRC-003] No validation_steps defined on any step — "
                "automated quality gates are missing for this run."
            )
        if _steps_reference_risky_modules(inp.steps):
            warnings.append(
                "[WARN-CRC-004] Steps reference risky modules "
                "(auth/database/deployment/security/migration/infrastructure). "
                "Manual approval will be required before those steps can execute."
            )

    # Determine overall decision and risk.
    if blockers:
        decision = ConfirmedRunCreationDecision.BLOCKED
        can_create = False
        risk = ConfirmedRunCreationRisk.CRITICAL
    elif warnings:
        decision = ConfirmedRunCreationDecision.WARNING
        can_create = True
        risk = ConfirmedRunCreationRisk.MEDIUM
    else:
        decision = ConfirmedRunCreationDecision.ALLOWED
        can_create = True
        risk = ConfirmedRunCreationRisk.LOW

    # Build a human-readable next recommended action.
    if decision == ConfirmedRunCreationDecision.BLOCKED:
        next_action = (
            "Resolve all blockers before attempting confirmed run creation. "
            f"First blocker: {blockers[0]}"
        )
    elif decision == ConfirmedRunCreationDecision.WARNING:
        next_action = (
            "All hard requirements are satisfied and run creation is contractually permitted. "
            "Review warnings before proceeding. "
            f"First warning: {warnings[0]}"
        )
    else:
        next_action = (
            "All contract requirements are satisfied. "
            "Proceed to POST /api/project-intake/confirmed-run with confirm=True "
            "to create a pending run and pending steps."
        )

    return ConfirmedRunCreationContractResult(
        decision=decision,
        risk=risk,
        can_create_pending_run=can_create,
        blockers=blockers[:_MAX_BLOCKERS],
        warnings=warnings[:_MAX_WARNINGS],
        requirements=requirements[:_MAX_REQUIREMENTS],
        safety_gates=safety_gates[:_MAX_SAFETY_GATES],
        allowed_created_entities=allowed_entities,
        forbidden_created_entities=forbidden_entities,
        required_statuses=required_statuses,
        required_operator_confirmations=operator_confirmations[:_MAX_OPERATOR_CONFIRMATIONS],
        next_recommended_action=next_action,
    )

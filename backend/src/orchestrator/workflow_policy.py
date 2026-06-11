"""Workflow action policy matrix for AI Workbench.

Pure policy module — no DB access, no tool execution, no side effects.
Classifies workflow actions by automation mode and returns structured
policy decisions used by the cockpit UI and future approval flows.
"""

from __future__ import annotations

import enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────────────────


class WorkflowAutomationMode(str, enum.Enum):
    MANUAL = "manual"
    GUIDED = "guided"
    SAFE_PREP = "safe_prep"


class WorkflowActionType(str, enum.Enum):
    # Direct safe (read-only preparation)
    AUTO_GATHER_CONTEXT = "auto_gather_context"
    BUILD_CONTEXT_BUNDLE = "build_context_bundle"
    CREATE_PATCH_DRAFT = "create_patch_draft"

    # Manual-only (operator-controlled)
    REVIEW_PATCH = "review_patch"
    CREATE_PROPOSAL = "create_proposal"
    APPLY_PATCH_MANUAL = "apply_patch_manual"
    RUN_TESTS_MANUAL = "run_tests_manual"
    ANALYZE_RESULT = "analyze_result"
    ROLLBACK_MANUAL = "rollback_manual"

    # Approval-required future (not implemented in v1)
    APPROVAL_CREATE_PROPOSAL = "approval_create_proposal"
    APPROVAL_APPLY_PATCH = "approval_apply_patch"
    APPROVAL_RUN_TESTS = "approval_run_tests"
    APPROVAL_ROLLBACK_PATCH = "approval_rollback_patch"
    APPROVAL_EXTERNAL_PROVIDER_EXECUTION = "approval_external_provider_execution"

    # Blocked (never allowed)
    ARBITRARY_SHELL = "arbitrary_shell"
    EXTERNAL_PROVIDER_EXECUTION = "external_provider_execution"
    AUTO_APPLY_PATCH = "auto_apply_patch"
    AUTO_RUN_COMMAND = "auto_run_command"
    AUTO_ANALYZE_RESULT = "auto_analyze_result"
    AUTO_ROLLBACK_PATCH = "auto_rollback_patch"
    PROTECTED_FILE_WRITE = "protected_file_write"
    SECRET_FILE_WRITE = "secret_file_write"


class WorkflowExecutionKind(str, enum.Enum):
    DIRECT_SAFE = "direct_safe"
    MANUAL_ONLY = "manual_only"
    APPROVAL_REQUIRED_FUTURE = "approval_required_future"
    BLOCKED = "blocked"


class WorkflowRiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ── Policy decision model ────────────────────────────────────────────────────


class WorkflowActionPolicy(BaseModel):
    """Policy decision for a single workflow action in a given mode."""

    action_type: str
    label: str
    execution_kind: WorkflowExecutionKind
    mode: WorkflowAutomationMode
    allowed: bool
    can_run_automatically: bool
    requires_confirmation: bool
    risk_level: WorkflowRiskLevel
    reason: str
    notes: Optional[str] = None


class WorkflowPolicyResponse(BaseModel):
    """Response for the policy listing endpoint."""

    mode: WorkflowAutomationMode
    policies: list[WorkflowActionPolicy] = Field(default_factory=list)


# ── Static policy definitions ────────────────────────────────────────────────

_DIRECT_SAFE_ACTIONS: set[str] = {
    WorkflowActionType.AUTO_GATHER_CONTEXT.value,
    WorkflowActionType.BUILD_CONTEXT_BUNDLE.value,
    WorkflowActionType.CREATE_PATCH_DRAFT.value,
}

_MANUAL_ONLY_ACTIONS: dict[str, tuple[WorkflowRiskLevel, bool]] = {
    WorkflowActionType.REVIEW_PATCH.value: (WorkflowRiskLevel.LOW, False),
    WorkflowActionType.CREATE_PROPOSAL.value: (WorkflowRiskLevel.MEDIUM, False),
    WorkflowActionType.APPLY_PATCH_MANUAL.value: (WorkflowRiskLevel.HIGH, True),
    WorkflowActionType.RUN_TESTS_MANUAL.value: (WorkflowRiskLevel.MEDIUM, True),
    WorkflowActionType.ANALYZE_RESULT.value: (WorkflowRiskLevel.LOW, False),
    WorkflowActionType.ROLLBACK_MANUAL.value: (WorkflowRiskLevel.HIGH, True),
}

_APPROVAL_FUTURE_ACTIONS: dict[str, tuple[WorkflowRiskLevel, bool]] = {
    WorkflowActionType.APPROVAL_CREATE_PROPOSAL.value: (WorkflowRiskLevel.MEDIUM, True),
    WorkflowActionType.APPROVAL_APPLY_PATCH.value: (WorkflowRiskLevel.HIGH, True),
    WorkflowActionType.APPROVAL_RUN_TESTS.value: (WorkflowRiskLevel.MEDIUM, True),
    WorkflowActionType.APPROVAL_ROLLBACK_PATCH.value: (WorkflowRiskLevel.HIGH, True),
    WorkflowActionType.APPROVAL_EXTERNAL_PROVIDER_EXECUTION.value: (WorkflowRiskLevel.CRITICAL, True),
}

_BLOCKED_ACTIONS: set[str] = {
    WorkflowActionType.ARBITRARY_SHELL.value,
    WorkflowActionType.EXTERNAL_PROVIDER_EXECUTION.value,
    WorkflowActionType.AUTO_APPLY_PATCH.value,
    WorkflowActionType.AUTO_RUN_COMMAND.value,
    WorkflowActionType.AUTO_ANALYZE_RESULT.value,
    WorkflowActionType.AUTO_ROLLBACK_PATCH.value,
    WorkflowActionType.PROTECTED_FILE_WRITE.value,
    WorkflowActionType.SECRET_FILE_WRITE.value,
}

_DIRECT_SAFE_RISK: dict[str, WorkflowRiskLevel] = {
    WorkflowActionType.AUTO_GATHER_CONTEXT.value: WorkflowRiskLevel.LOW,
    WorkflowActionType.BUILD_CONTEXT_BUNDLE.value: WorkflowRiskLevel.LOW,
    WorkflowActionType.CREATE_PATCH_DRAFT.value: WorkflowRiskLevel.MEDIUM,
}


# ── Policy engine ────────────────────────────────────────────────────────────


def get_workflow_action_policy(
    action_type: str,
    mode: WorkflowAutomationMode,
) -> WorkflowActionPolicy:
    """Return the policy decision for *action_type* under *mode*.

    Pure function — no DB reads, no tool execution, no side effects.
    """

    # ── Blocked actions ──
    if action_type in _BLOCKED_ACTIONS:
        return WorkflowActionPolicy(
            action_type=action_type,
            label="Blocked",
            execution_kind=WorkflowExecutionKind.BLOCKED,
            mode=mode,
            allowed=False,
            can_run_automatically=False,
            requires_confirmation=False,
            risk_level=WorkflowRiskLevel.CRITICAL,
            reason="This action is permanently blocked by safety policy.",
        )

    # ── Approval-required future ──
    if action_type in _APPROVAL_FUTURE_ACTIONS:
        risk, confirm = _APPROVAL_FUTURE_ACTIONS[action_type]
        return WorkflowActionPolicy(
            action_type=action_type,
            label="Approval required (future)",
            execution_kind=WorkflowExecutionKind.APPROVAL_REQUIRED_FUTURE,
            mode=mode,
            allowed=False,
            can_run_automatically=False,
            requires_confirmation=confirm,
            risk_level=risk,
            reason="Approval flow not implemented yet. This action will require explicit approval in a future slice.",
        )

    # ── Manual-only actions ──
    if action_type in _MANUAL_ONLY_ACTIONS:
        risk, confirm = _MANUAL_ONLY_ACTIONS[action_type]
        return WorkflowActionPolicy(
            action_type=action_type,
            label="Manual only",
            execution_kind=WorkflowExecutionKind.MANUAL_ONLY,
            mode=mode,
            allowed=True,
            can_run_automatically=False,
            requires_confirmation=confirm,
            risk_level=risk,
            reason="This action always requires manual operator control.",
        )

    # ── Direct safe actions ──
    if action_type in _DIRECT_SAFE_ACTIONS:
        risk = _DIRECT_SAFE_RISK.get(action_type, WorkflowRiskLevel.LOW)
        can_auto = mode in (WorkflowAutomationMode.GUIDED, WorkflowAutomationMode.SAFE_PREP)
        if mode == WorkflowAutomationMode.MANUAL:
            return WorkflowActionPolicy(
                action_type=action_type,
                label="Blocked by Manual mode",
                execution_kind=WorkflowExecutionKind.DIRECT_SAFE,
                mode=mode,
                allowed=False,
                can_run_automatically=False,
                requires_confirmation=False,
                risk_level=risk,
                reason="Switch to Guided or Safe Prep to run read-only preparation.",
            )
        return WorkflowActionPolicy(
            action_type=action_type,
            label="Direct safe",
            execution_kind=WorkflowExecutionKind.DIRECT_SAFE,
            mode=mode,
            allowed=True,
            can_run_automatically=can_auto,
            requires_confirmation=False,
            risk_level=risk,
            reason="Read-only preparation action. No files modified.",
        )

    # ── Unknown action — safe default ──
    return WorkflowActionPolicy(
        action_type=action_type,
        label="Unknown action",
        execution_kind=WorkflowExecutionKind.BLOCKED,
        mode=mode,
        allowed=False,
        can_run_automatically=False,
        requires_confirmation=False,
        risk_level=WorkflowRiskLevel.HIGH,
        reason=f"Unknown action type '{action_type}'. Blocked by default.",
    )


def list_workflow_action_policies(
    mode: WorkflowAutomationMode,
) -> list[WorkflowActionPolicy]:
    """Return policies for all known action types under *mode*."""

    return [
        get_workflow_action_policy(at.value, mode)
        for at in WorkflowActionType
    ]


class WorkflowActionNotAllowedError(Exception):
    """Raised when a workflow action is not permitted under the current policy."""

    def __init__(self, policy: WorkflowActionPolicy) -> None:
        self.policy = policy
        super().__init__(
            f"Action '{policy.action_type}' is not allowed in "
            f"'{policy.mode.value}' mode: {policy.reason}"
        )


def assert_workflow_action_allowed(
    action_type: str,
    mode: WorkflowAutomationMode,
) -> WorkflowActionPolicy:
    """Return the policy if allowed, otherwise raise WorkflowActionNotAllowedError.

    Use as a guard at the start of any handler that executes a workflow action.
    """

    policy = get_workflow_action_policy(action_type, mode)
    if not policy.allowed:
        raise WorkflowActionNotAllowedError(policy)
    return policy

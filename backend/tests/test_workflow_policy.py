"""Tests for the workflow action policy matrix.

Pure logic tests — no DB, no network, no side effects.
"""

from __future__ import annotations

import unittest

from src.orchestrator.workflow_policy import (
    WorkflowActionNotAllowedError,
    WorkflowActionPolicy,
    WorkflowActionType,
    WorkflowAutomationMode,
    WorkflowExecutionKind,
    WorkflowRiskLevel,
    assert_workflow_action_allowed,
    get_workflow_action_policy,
    list_workflow_action_policies,
)


# ── Direct safe actions ──────────────────────────────────────────────────────

DIRECT_SAFE = [
    WorkflowActionType.AUTO_GATHER_CONTEXT.value,
    WorkflowActionType.BUILD_CONTEXT_BUNDLE.value,
    WorkflowActionType.CREATE_PATCH_DRAFT.value,
]

MANUAL_ONLY = [
    WorkflowActionType.REVIEW_PATCH.value,
    WorkflowActionType.CREATE_PROPOSAL.value,
    WorkflowActionType.APPLY_PATCH_MANUAL.value,
    WorkflowActionType.RUN_TESTS_MANUAL.value,
    WorkflowActionType.ANALYZE_RESULT.value,
    WorkflowActionType.ROLLBACK_MANUAL.value,
]

APPROVAL_FUTURE = [
    WorkflowActionType.APPROVAL_CREATE_PROPOSAL.value,
    WorkflowActionType.APPROVAL_APPLY_PATCH.value,
    WorkflowActionType.APPROVAL_RUN_TESTS.value,
    WorkflowActionType.APPROVAL_ROLLBACK_PATCH.value,
    WorkflowActionType.APPROVAL_EXTERNAL_PROVIDER_EXECUTION.value,
]

BLOCKED = [
    WorkflowActionType.ARBITRARY_SHELL.value,
    WorkflowActionType.EXTERNAL_PROVIDER_EXECUTION.value,
    WorkflowActionType.AUTO_APPLY_PATCH.value,
    WorkflowActionType.AUTO_RUN_COMMAND.value,
    WorkflowActionType.AUTO_ANALYZE_RESULT.value,
    WorkflowActionType.AUTO_ROLLBACK_PATCH.value,
    WorkflowActionType.PROTECTED_FILE_WRITE.value,
    WorkflowActionType.SECRET_FILE_WRITE.value,
]

ALL_MODES = [
    WorkflowAutomationMode.MANUAL,
    WorkflowAutomationMode.GUIDED,
    WorkflowAutomationMode.SAFE_PREP,
]


class TestManualModeBlocksAutomatic(unittest.TestCase):
    """Manual mode must set can_run_automatically=False for every action."""

    def test_all_actions_not_automatic(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.MANUAL)
        for p in policies:
            self.assertFalse(
                p.can_run_automatically,
                f"{p.action_type} should not be automatic in manual mode",
            )


class TestGuidedModeAutoOnlyDirectSafe(unittest.TestCase):
    """Guided mode: only direct safe actions can run automatically."""

    def test_direct_safe_auto(self):
        for action in DIRECT_SAFE:
            p = get_workflow_action_policy(action, WorkflowAutomationMode.GUIDED)
            self.assertTrue(p.can_run_automatically, f"{action} should be auto in guided")
            self.assertTrue(p.allowed, f"{action} should be allowed in guided")

    def test_manual_only_not_auto(self):
        for action in MANUAL_ONLY:
            p = get_workflow_action_policy(action, WorkflowAutomationMode.GUIDED)
            self.assertFalse(p.can_run_automatically, f"{action} should not be auto in guided")

    def test_blocked_not_auto(self):
        for action in BLOCKED:
            p = get_workflow_action_policy(action, WorkflowAutomationMode.GUIDED)
            self.assertFalse(p.can_run_automatically, f"{action} should not be auto in guided")


class TestSafePrepModeAutoOnlyDirectSafe(unittest.TestCase):
    """Safe Prep mode: only direct safe actions can run automatically."""

    def test_direct_safe_auto(self):
        for action in DIRECT_SAFE:
            p = get_workflow_action_policy(action, WorkflowAutomationMode.SAFE_PREP)
            self.assertTrue(p.can_run_automatically, f"{action} should be auto in safe_prep")

    def test_manual_only_not_auto(self):
        for action in MANUAL_ONLY:
            p = get_workflow_action_policy(action, WorkflowAutomationMode.SAFE_PREP)
            self.assertFalse(p.can_run_automatically, f"{action} should not be auto in safe_prep")


class TestDangerousActionsNeverAutomatic(unittest.TestCase):
    """apply_patch_manual, run_tests_manual, rollback_manual are never automatic."""

    DANGEROUS = [
        WorkflowActionType.APPLY_PATCH_MANUAL.value,
        WorkflowActionType.RUN_TESTS_MANUAL.value,
        WorkflowActionType.ROLLBACK_MANUAL.value,
    ]

    def test_never_automatic_any_mode(self):
        for action in self.DANGEROUS:
            for mode in ALL_MODES:
                p = get_workflow_action_policy(action, mode)
                self.assertFalse(
                    p.can_run_automatically,
                    f"{action} must never be automatic in {mode.value}",
                )

    def test_requires_confirmation(self):
        for action in self.DANGEROUS:
            for mode in ALL_MODES:
                p = get_workflow_action_policy(action, mode)
                self.assertTrue(
                    p.requires_confirmation,
                    f"{action} must require confirmation in {mode.value}",
                )


class TestBlockedActionsNeverAllowed(unittest.TestCase):
    """Blocked actions are never allowed in any mode."""

    def test_all_blocked_not_allowed(self):
        for action in BLOCKED:
            for mode in ALL_MODES:
                p = get_workflow_action_policy(action, mode)
                self.assertFalse(p.allowed, f"{action} should not be allowed in {mode.value}")
                self.assertFalse(p.can_run_automatically)
                self.assertEqual(p.execution_kind, WorkflowExecutionKind.BLOCKED)


class TestApprovalFutureNotAutomatic(unittest.TestCase):
    """Approval-required future actions are never automatic in v1."""

    def test_not_automatic_any_mode(self):
        for action in APPROVAL_FUTURE:
            for mode in ALL_MODES:
                p = get_workflow_action_policy(action, mode)
                self.assertFalse(p.can_run_automatically, f"{action} in {mode.value}")
                self.assertFalse(p.allowed, f"{action} should not be allowed yet")
                self.assertEqual(p.execution_kind, WorkflowExecutionKind.APPROVAL_REQUIRED_FUTURE)


class TestUnknownActionBlocked(unittest.TestCase):
    """Unknown action types should be safely blocked."""

    def test_unknown_action(self):
        p = get_workflow_action_policy("totally_unknown_action", WorkflowAutomationMode.GUIDED)
        self.assertFalse(p.allowed)
        self.assertFalse(p.can_run_automatically)
        self.assertEqual(p.execution_kind, WorkflowExecutionKind.BLOCKED)
        self.assertIn("Unknown", p.label)


class TestListPoliciesComplete(unittest.TestCase):
    """list_workflow_action_policies returns all known actions."""

    def test_count_matches_enum(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.GUIDED)
        self.assertEqual(len(policies), len(WorkflowActionType))

    def test_all_action_types_present(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.GUIDED)
        returned_types = {p.action_type for p in policies}
        expected_types = {at.value for at in WorkflowActionType}
        self.assertEqual(returned_types, expected_types)


class TestCanRunAutomaticallyOnlyThree(unittest.TestCase):
    """can_run_automatically=True must exist for exactly 3 direct safe actions."""

    def test_guided_only_three(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.GUIDED)
        auto_actions = {p.action_type for p in policies if p.can_run_automatically}
        self.assertEqual(auto_actions, set(DIRECT_SAFE))

    def test_safe_prep_only_three(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.SAFE_PREP)
        auto_actions = {p.action_type for p in policies if p.can_run_automatically}
        self.assertEqual(auto_actions, set(DIRECT_SAFE))

    def test_manual_zero(self):
        policies = list_workflow_action_policies(WorkflowAutomationMode.MANUAL)
        auto_actions = [p for p in policies if p.can_run_automatically]
        self.assertEqual(len(auto_actions), 0)


class TestAssertGuard(unittest.TestCase):
    """assert_workflow_action_allowed should raise or return policy."""

    def test_allowed_returns_policy(self):
        p = assert_workflow_action_allowed(
            WorkflowActionType.AUTO_GATHER_CONTEXT.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertIsInstance(p, WorkflowActionPolicy)
        self.assertTrue(p.allowed)

    def test_blocked_raises(self):
        with self.assertRaises(WorkflowActionNotAllowedError) as ctx:
            assert_workflow_action_allowed(
                WorkflowActionType.ARBITRARY_SHELL.value,
                WorkflowAutomationMode.GUIDED,
            )
        self.assertFalse(ctx.exception.policy.allowed)

    def test_manual_mode_blocks_direct_safe(self):
        with self.assertRaises(WorkflowActionNotAllowedError):
            assert_workflow_action_allowed(
                WorkflowActionType.AUTO_GATHER_CONTEXT.value,
                WorkflowAutomationMode.MANUAL,
            )

    def test_manual_only_allowed(self):
        p = assert_workflow_action_allowed(
            WorkflowActionType.REVIEW_PATCH.value,
            WorkflowAutomationMode.MANUAL,
        )
        self.assertTrue(p.allowed)
        self.assertFalse(p.can_run_automatically)


class TestRiskLevels(unittest.TestCase):
    """Verify risk levels for key actions."""

    def test_apply_patch_high(self):
        p = get_workflow_action_policy(
            WorkflowActionType.APPLY_PATCH_MANUAL.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertEqual(p.risk_level, WorkflowRiskLevel.HIGH)

    def test_rollback_high(self):
        p = get_workflow_action_policy(
            WorkflowActionType.ROLLBACK_MANUAL.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertEqual(p.risk_level, WorkflowRiskLevel.HIGH)

    def test_gather_context_low(self):
        p = get_workflow_action_policy(
            WorkflowActionType.AUTO_GATHER_CONTEXT.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertEqual(p.risk_level, WorkflowRiskLevel.LOW)

    def test_create_draft_medium(self):
        p = get_workflow_action_policy(
            WorkflowActionType.CREATE_PATCH_DRAFT.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertEqual(p.risk_level, WorkflowRiskLevel.MEDIUM)

    def test_blocked_critical(self):
        p = get_workflow_action_policy(
            WorkflowActionType.ARBITRARY_SHELL.value,
            WorkflowAutomationMode.GUIDED,
        )
        self.assertEqual(p.risk_level, WorkflowRiskLevel.CRITICAL)


class TestPolicyModel(unittest.TestCase):
    """Policy objects are valid Pydantic models."""

    def test_serialization(self):
        p = get_workflow_action_policy(
            WorkflowActionType.AUTO_GATHER_CONTEXT.value,
            WorkflowAutomationMode.GUIDED,
        )
        data = p.model_dump()
        self.assertIn("action_type", data)
        self.assertIn("can_run_automatically", data)
        self.assertIn("risk_level", data)

    def test_json_round_trip(self):
        p = get_workflow_action_policy(
            WorkflowActionType.APPLY_PATCH_MANUAL.value,
            WorkflowAutomationMode.SAFE_PREP,
        )
        json_str = p.model_dump_json()
        restored = WorkflowActionPolicy.model_validate_json(json_str)
        self.assertEqual(restored.action_type, p.action_type)
        self.assertEqual(restored.can_run_automatically, p.can_run_automatically)


if __name__ == "__main__":
    unittest.main()

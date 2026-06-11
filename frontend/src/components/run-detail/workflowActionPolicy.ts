export type WorkflowAutomationMode = "manual" | "guided" | "safe_prep";

export type WorkflowBoundaryExecutionKind =
  | "direct_safe"
  | "manual_only"
  | "approval_required_future"
  | "blocked";

export type WorkflowBoundaryRiskLevel = "low" | "medium" | "high";

export type WorkflowActionBoundary = {
  actionType: string;
  label: string;
  riskLevel: WorkflowBoundaryRiskLevel;
  executionKind: WorkflowBoundaryExecutionKind;
  allowedModes: WorkflowAutomationMode[];
  requiresConfirmation: boolean;
  canRunAutomatically: boolean;
  reason: string;
};

const GUIDED_AND_SAFE_PREP: WorkflowAutomationMode[] = ["guided", "safe_prep"];
const ALL_MODES: WorkflowAutomationMode[] = ["manual", "guided", "safe_prep"];

export const WORKFLOW_DIRECT_SAFE_ACTION_TYPES = [
  "auto_gather_context",
  "build_context_bundle",
  "create_patch_draft",
] as const;

export const WORKFLOW_MANUAL_ONLY_ACTION_TYPES = [
  "review_patch",
  "create_proposal",
  "propose_patch",
  "apply_patch_manual",
  "apply_patch",
  "run_tests_manual",
  "run_tests",
  "run_command",
  "analyze_result",
  "rollback_manual",
  "rollback_patch",
] as const;

export const WORKFLOW_BLOCKED_ACTION_TYPES = [
  "arbitrary_shell",
  "external_provider_execution",
  "auto_apply_patch",
  "auto_run_command",
  "auto_analyze_result",
  "auto_rollback_patch",
  "protected_file_write",
  "secret_file_write",
] as const;

export const WORKFLOW_APPROVAL_REQUIRED_FUTURE_ACTION_TYPES = [
  "approval_gated_create_proposal",
  "approval_gated_apply_patch",
  "approval_gated_run_tests",
  "approval_gated_rollback",
  "approval_gated_external_provider_execution",
] as const;

export const WORKFLOW_BOUNDARY_SUMMARY_LINES = [
  "Direct safe: auto context, context bundle, patch draft.",
  "Manual approval required: review, proposal, apply, tests, analyze, rollback.",
  "Blocked: shell, external providers, auto-apply, auto-tests, auto-analyze, auto-rollback.",
];

const directSafeReason = "Allowed only as bounded preparation. Does not create proposals, apply patches, run tests, analyze results, or rollback.";
const manualOnlyReason = "Manual-only in v1. The launcher may guide or focus existing UI, but must not execute this automatically.";
const blockedReason = "Blocked by the semi-auto boundary. This action is outside the current safe preparation scope.";
const futureReason = "Future approval-gated boundary only. Not executable in v1.";

export const WORKFLOW_ACTION_BOUNDARIES: Record<string, WorkflowActionBoundary> = {
  auto_gather_context: {
    actionType: "auto_gather_context",
    label: "Auto gather context",
    riskLevel: "low",
    executionKind: "direct_safe",
    allowedModes: GUIDED_AND_SAFE_PREP,
    requiresConfirmation: false,
    canRunAutomatically: true,
    reason: directSafeReason,
  },
  build_context_bundle: {
    actionType: "build_context_bundle",
    label: "Build context bundle",
    riskLevel: "low",
    executionKind: "direct_safe",
    allowedModes: GUIDED_AND_SAFE_PREP,
    requiresConfirmation: false,
    canRunAutomatically: true,
    reason: directSafeReason,
  },
  create_patch_draft: {
    actionType: "create_patch_draft",
    label: "Create patch draft",
    riskLevel: "medium",
    executionKind: "direct_safe",
    allowedModes: GUIDED_AND_SAFE_PREP,
    requiresConfirmation: false,
    canRunAutomatically: true,
    reason: "Draft-only preparation. Does not create a proposal or apply a patch.",
  },
  review_patch: {
    actionType: "review_patch",
    label: "Review patch",
    riskLevel: "low",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: false,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  create_proposal: {
    actionType: "create_proposal",
    label: "Create proposal",
    riskLevel: "low",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: false,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  propose_patch: {
    actionType: "propose_patch",
    label: "Create proposal",
    riskLevel: "low",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: false,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  apply_patch_manual: {
    actionType: "apply_patch_manual",
    label: "Apply patch",
    riskLevel: "high",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  apply_patch: {
    actionType: "apply_patch",
    label: "Apply patch",
    riskLevel: "high",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  run_tests_manual: {
    actionType: "run_tests_manual",
    label: "Run tests",
    riskLevel: "medium",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  run_tests: {
    actionType: "run_tests",
    label: "Run tests",
    riskLevel: "medium",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  run_command: {
    actionType: "run_command",
    label: "Run command",
    riskLevel: "medium",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  analyze_result: {
    actionType: "analyze_result",
    label: "Analyze result",
    riskLevel: "low",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: false,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  rollback_manual: {
    actionType: "rollback_manual",
    label: "Rollback patch",
    riskLevel: "high",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  rollback_patch: {
    actionType: "rollback_patch",
    label: "Rollback patch",
    riskLevel: "high",
    executionKind: "manual_only",
    allowedModes: ALL_MODES,
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: manualOnlyReason,
  },
  arbitrary_shell: {
    actionType: "arbitrary_shell",
    label: "Arbitrary shell",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  external_provider_execution: {
    actionType: "external_provider_execution",
    label: "External provider execution",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  auto_apply_patch: {
    actionType: "auto_apply_patch",
    label: "Auto apply patch",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  auto_run_command: {
    actionType: "auto_run_command",
    label: "Auto run command",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  auto_analyze_result: {
    actionType: "auto_analyze_result",
    label: "Auto analyze result",
    riskLevel: "medium",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  auto_rollback_patch: {
    actionType: "auto_rollback_patch",
    label: "Auto rollback patch",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  protected_file_write: {
    actionType: "protected_file_write",
    label: "Protected file write",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  secret_file_write: {
    actionType: "secret_file_write",
    label: "Secret file write",
    riskLevel: "high",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: blockedReason,
  },
  approval_gated_create_proposal: {
    actionType: "approval_gated_create_proposal",
    label: "Approval-gated proposal",
    riskLevel: "medium",
    executionKind: "approval_required_future",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: futureReason,
  },
  approval_gated_apply_patch: {
    actionType: "approval_gated_apply_patch",
    label: "Approval-gated apply",
    riskLevel: "high",
    executionKind: "approval_required_future",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: futureReason,
  },
  approval_gated_run_tests: {
    actionType: "approval_gated_run_tests",
    label: "Approval-gated tests",
    riskLevel: "medium",
    executionKind: "approval_required_future",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: futureReason,
  },
  approval_gated_rollback: {
    actionType: "approval_gated_rollback",
    label: "Approval-gated rollback",
    riskLevel: "high",
    executionKind: "approval_required_future",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: futureReason,
  },
  approval_gated_external_provider_execution: {
    actionType: "approval_gated_external_provider_execution",
    label: "Approval-gated external provider",
    riskLevel: "high",
    executionKind: "approval_required_future",
    allowedModes: [],
    requiresConfirmation: true,
    canRunAutomatically: false,
    reason: futureReason,
  },
};

export function getWorkflowActionBoundary(actionType: string): WorkflowActionBoundary {
  return WORKFLOW_ACTION_BOUNDARIES[actionType] ?? {
    actionType,
    label: actionType,
    riskLevel: "low",
    executionKind: "blocked",
    allowedModes: [],
    requiresConfirmation: false,
    canRunAutomatically: false,
    reason: "Unknown action type. It is blocked until explicitly classified.",
  };
}

export function canRunWorkflowActionAutomatically(
  actionType: string,
  mode: WorkflowAutomationMode,
): boolean {
  const boundary = getWorkflowActionBoundary(actionType);
  return boundary.canRunAutomatically && boundary.allowedModes.includes(mode);
}

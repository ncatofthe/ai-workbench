export type RunStatus = "pending" | "running" | "waiting_approval" | "completed" | "failed" | "stopped";
export type ApprovalStatus = "pending" | "approved" | "rejected";
export type ProviderType = "ollama" | "codex" | "claude";
export type RunMode = "offline" | "hybrid" | "cloud";
export type ProviderMode = "local" | "hybrid" | "cloud";
export type ModelProviderId = "local_ollama" | "claude_code" | "chatgpt_codex" | "external_api" | string;
export type ProjectIntakeMode = "new_project" | "existing_project" | "unknown";
export type ProjectIntakeQuestionPriority = "required" | "recommended" | "optional";
export type ProjectIntakeQuestionCategory =
  | "product_goal"
  | "users_roles"
  | "platform"
  | "tech_stack"
  | "data_storage"
  | "auth_security"
  | "integrations"
  | "files_uploads"
  | "payments_billing"
  | "notifications"
  | "ui_design"
  | "deployment"
  | "existing_project"
  | "constraints"
  | "quality_testing";
export type ProjectIntakeTargetType =
  | "web_app"
  | "mobile_app"
  | "desktop_app"
  | "api_service"
  | "cli_tool"
  | "automation"
  | "unknown";
export type ProjectIntakeMaturityGoal =
  | "mvp"
  | "full_product"
  | "diploma"
  | "prototype"
  | "internal_tool"
  | "unknown";

export interface Project {
  id: string;
  name: string;
  path: string;
  description: string;
  stack: string;
  package_manager: string;
  test_command: string;
  build_command: string;
  safe_commands: string[];
  blocked_commands: string[];
  ignore_paths: string[];
  created_at: string;
  updated_at: string | null;
}

export interface ProjectIntakeQuestion {
  id: string;
  category: ProjectIntakeQuestionCategory;
  priority: ProjectIntakeQuestionPriority;
  question: string;
  why_it_matters: string;
  suggested_default?: string | null;
  options?: string[] | null;
}

export interface ProjectIntakeRequest {
  idea: string;
  mode?: ProjectIntakeMode | null;
  existing_project_attached?: boolean | null;
  known_stack?: string[] | null;
  known_constraints?: string[] | null;
  user_goal?: string | null;
}

export interface ProjectIntakeResponse {
  mode: ProjectIntakeMode;
  detected_target_type: ProjectIntakeTargetType;
  detected_maturity_goal: ProjectIntakeMaturityGoal;
  summary: string;
  assumptions: string[];
  missing_information: string[];
  questions: ProjectIntakeQuestion[];
  ready_to_plan: boolean;
  recommended_next_step: string;
  confidence: string;
}

export type ProjectBriefSectionStatus = "confirmed" | "assumed" | "missing";

export interface ProjectBriefSection {
  title: string;
  content: string;
  status: ProjectBriefSectionStatus;
  notes?: string | null;
}

export interface ProjectBriefDraftRequest extends ProjectIntakeRequest {
  answers?: Record<string, string> | null;
}

export interface ProjectBriefDraftResponse {
  title: string;
  mode: ProjectIntakeMode;
  target_type: ProjectIntakeTargetType;
  maturity_goal: ProjectIntakeMaturityGoal;
  readiness: string;
  summary: string;
  brief_markdown: string;
  sections: ProjectBriefSection[];
  assumptions: string[];
  missing_information: string[];
  open_questions: ProjectIntakeQuestion[];
  recommended_next_step: string;
  ready_to_plan: boolean;
}

export type DevelopmentPlanPhaseStatus = "ready" | "needs_input" | "blocked";

export interface DevelopmentPlanPhase {
  id: string;
  title: string;
  description: string;
  priority: ProjectIntakeQuestionPriority;
  status: DevelopmentPlanPhaseStatus;
  suggested_agent_id?: string | null;
  depends_on: string[];
  deliverables: string[];
  risks: string[];
}

export interface DevelopmentPlanSourceReadiness {
  intake_ready_to_plan: boolean;
  brief_ready_to_plan: boolean;
}

export interface DevelopmentPlanPreviewRequest extends ProjectBriefDraftRequest {
  brief_markdown?: string | null;
}

export interface DevelopmentPlanPreviewResponse {
  title: string;
  mode: ProjectIntakeMode;
  target_type: ProjectIntakeTargetType;
  maturity_goal: ProjectIntakeMaturityGoal;
  ready_to_start: boolean;
  summary: string;
  phases: DevelopmentPlanPhase[];
  required_inputs: string[];
  assumptions: string[];
  risks: string[];
  recommended_agent_ids: string[];
  recommended_next_step: string;
  source_readiness: DevelopmentPlanSourceReadiness;
}

export interface SourceOfTruthPreviewRequest extends DevelopmentPlanPreviewRequest {
  plan_summary?: string | null;
  plan_phases?: DevelopmentPlanPhase[] | null;
}

export type ProjectInputSourceType =
  | "client_spec"
  | "commercial_proposal"
  | "existing_project"
  | "new_idea"
  | "mixed"
  | "unknown";
export type RequirementPriority = "must" | "should" | "could" | "wont" | "unknown";
export type RequirementStatus =
  | "proposed"
  | "confirmed"
  | "assumed"
  | "missing"
  | "rejected"
  | "implemented"
  | "needs_validation";
export type DriftRiskLevel = "low" | "medium" | "high" | "critical";
export type AcceptanceStatus = "not_checked" | "satisfied" | "partially_satisfied" | "failed" | "blocked";

export interface ProjectRequirementContract {
  id: string;
  title: string;
  description: string;
  priority: RequirementPriority;
  status: RequirementStatus;
  source_refs: string[];
  acceptance_criteria_ids: string[];
  conflicts_with: string[];
  tags: string[];
}

export interface ProjectConstraintContract {
  id: string;
  title: string;
  description: string;
  forbidden_paths: string[];
  forbidden_actions: string[];
  reason: string;
}

export interface ProjectAcceptanceCriterion {
  id: string;
  description: string;
  requirement_id?: string | null;
  status: AcceptanceStatus;
  verification_hint?: string | null;
}

export interface ProjectAntiDriftRule {
  id: string;
  title: string;
  description: string;
  risk_level: DriftRiskLevel;
  forbidden_patterns: string[];
  require_requirement_link: boolean;
}

export interface ProjectSourceOfTruthContract {
  id: string;
  source_type: ProjectInputSourceType;
  raw_source_summary: string;
  project_name?: string | null;
  product_goal: string;
  target_users: string[];
  user_roles: string[];
  core_features: string[];
  requirements: ProjectRequirementContract[];
  constraints: ProjectConstraintContract[];
  forbidden_changes: string[];
  acceptance_criteria: ProjectAcceptanceCriterion[];
  assumptions: string[];
  open_questions: string[];
  anti_drift_rules: ProjectAntiDriftRule[];
  definition_of_done: string[];
  created_from?: string | null;
  confidence: string;
  readiness: string;
  source_metadata: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
}

export interface SourceOfTruthValidationResult {
  valid: boolean;
  drift_risk: DriftRiskLevel;
  errors: string[];
  warnings: string[];
}

export interface RequirementCoverageItem {
  requirement_id: string;
  title: string;
  priority: RequirementPriority;
  status: RequirementStatus;
  linked_plan_item_ids: string[];
  acceptance_status: AcceptanceStatus;
  covered: boolean;
  notes: string;
}

export interface RequirementCoverageMatrix {
  source_of_truth_id: string;
  items: RequirementCoverageItem[];
  missing_requirement_ids: string[];
  unlinked_plan_item_ids: string[];
  coverage_score: number;
  drift_risk: DriftRiskLevel;
}

export interface SourceOfTruthPreviewResponse {
  title: string;
  source_of_truth: ProjectSourceOfTruthContract;
  validation: SourceOfTruthValidationResult;
  coverage_matrix: RequirementCoverageMatrix;
  summary: string;
  recommended_next_step: string;
  ready_to_plan: boolean;
}

export type RequirementCoveragePreviewStatus = "covered" | "partially_covered" | "missing" | "unclear";

export interface RequirementCoveragePlanPhaseLink {
  phase_id: string;
  title: string;
}

export interface RequirementCoveragePreviewItem {
  requirement_id: string;
  title: string;
  priority: RequirementPriority;
  coverage_status: RequirementCoveragePreviewStatus;
  linked_plan_phases: RequirementCoveragePlanPhaseLink[];
  notes: string;
  drift_risk: DriftRiskLevel;
}

export interface UnlinkedPlanPhasePreviewItem {
  phase_id: string;
  title: string;
  reason: string;
  risk_level: DriftRiskLevel;
  suggested_action: string;
}

export interface RequirementCoveragePreviewSummary {
  requirements_total: number;
  covered_requirements: number;
  partially_covered_requirements: number;
  missing_requirements: number;
  unclear_requirements: number;
  unlinked_plan_phases: number;
  drift_risk: DriftRiskLevel;
}

export interface RequirementCoveragePreviewRequest extends SourceOfTruthPreviewRequest {
  source_of_truth?: ProjectSourceOfTruthContract | null;
  plan_preview?: DevelopmentPlanPreviewResponse | null;
}

export interface RequirementCoveragePreviewResponse {
  title: string;
  summary: RequirementCoveragePreviewSummary;
  items: RequirementCoveragePreviewItem[];
  unlinked_plan_phases: UnlinkedPlanPhasePreviewItem[];
  drift_risks: string[];
  recommended_next_step: string;
}

// ── Confirmed Plan → Run Step Preview ────────────────────────────────────────

export interface ConfirmedRunStepPreview {
  id: string;
  title: string;
  description: string;
  suggested_agent_id: string | null;
  required_requirement_ids: string[];
  coverage_status: RequirementCoveragePreviewStatus;
  drift_risk: DriftRiskLevel;
  depends_on: string[];
  expected_deliverables: string[];
  validation_notes: string;
  manual_approval_required: boolean;
  safe_to_prepare: boolean;
}

export interface ConfirmedPlanRunPreviewRequest {
  idea: string;
  mode?: ProjectIntakeMode | null;
  existing_project_attached?: boolean | null;
  known_stack?: string[] | null;
  known_constraints?: string[] | null;
  user_goal?: string | null;
}

export interface ConfirmedPlanRunPreviewResponse {
  title: string;
  ready_to_create_run: boolean;
  summary: string;
  source_of_truth_ready: boolean;
  coverage_ready: boolean;
  steps: ConfirmedRunStepPreview[];
  blocking_issues: string[];
  warnings: string[];
  recommended_next_step: string;
}

export interface ConfirmedRunFromPlanRequest {
  idea: string;
  confirm: boolean;
  mode?: ProjectIntakeMode | null;
  project_id?: string | null;
  existing_project_attached?: boolean | null;
  known_stack?: string[] | null;
  known_constraints?: string[] | null;
  user_goal?: string | null;
}

export interface ConfirmedRunCreatedStep {
  step_id: string;
  title: string;
  agent_id: string;
  status: string;
}

export interface ConfirmedRunFromPlanResponse {
  run_id: string;
  run_status: string;
  steps_created: number;
  steps: ConfirmedRunCreatedStep[];
  summary: string;
  warnings: string[];
}

export interface RunStepRequirementContext {
  requirement_ids: string[];
  coverage_status: string;
  drift_risk: string;
  acceptance_criteria: string[];
  constraints: string[];
  forbidden_changes: string[];
  validation_notes: string[];
  source_of_truth_summary: string;
  parse_warnings: string[];
}

export type StepSourceOfTruthGuardDecision = "allowed" | "warning" | "blocked";

export interface StepSourceOfTruthGuardRequest {
  proposed_action: string;
  file_path?: string | null;
  patch_summary?: string | null;
  old_text?: string | null;
  new_text?: string | null;
}

export interface StepSourceOfTruthGuardResult {
  decision: StepSourceOfTruthGuardDecision;
  drift_risk: string;
  matched_requirement_ids: string[];
  violated_constraints: string[];
  forbidden_change_hits: string[];
  warnings: string[];
  reasons: string[];
  recommended_next_step: string;
}

export interface StepSourceOfTruthGuardResponse {
  run_id: string;
  step_id: string;
  has_requirement_context: boolean;
  parsed_context: RunStepRequirementContext;
  guard_result: StepSourceOfTruthGuardResult;
  persisted?: boolean;
  guard_result_id?: string | null;
}

export interface GuardResultItem {
  id: string;
  run_id: string;
  step_id: string;
  project_id: string | null;
  decision: StepSourceOfTruthGuardDecision;
  drift_risk: string;
  is_stale: boolean;
  stale_reasons: string[];
  source: string;
  proposal_tool_call_id: string | null;
  apply_tool_call_id: string | null;
  warning_acknowledged: boolean;
  no_guard_override: boolean;
  created_at: string;
  updated_at: string | null;
  expires_at: string | null;
  proposed_action: string;
  file_path: string | null;
  patch_summary: string | null;
  old_text_hash: string | null;
  new_text_hash: string | null;
  requirement_ids: string[];
  coverage_status: string;
  matched_requirement_ids: string[];
  violated_constraints: string[];
  forbidden_change_hits: string[];
  warnings: string[];
  reasons: string[];
  recommended_next_step: string;
}

export interface GuardResultListResponse {
  run_id: string;
  total: number;
  items: GuardResultItem[];
}

export interface GuardProposalValidationRequest {
  proposed_action?: string;
  file_path?: string | null;
  patch_summary?: string | null;
  old_text?: string | null;
  new_text?: string | null;
  warning_acknowledged?: boolean;
  no_guard_override?: boolean;
}

export interface GuardProposalValidationResponse {
  guard_result_id: string;
  valid: boolean;
  decision: string;
  is_stale: boolean;
  stale_reasons: string[];
  blocking_reasons: string[];
  warnings: string[];
  requires_warning_acknowledgement: boolean;
  recommended_next_step: string;
}

export type PatchLifecycleNextAction =
  | "create_guard"
  | "create_proposal"
  | "apply_patch"
  | "run_tests_manual"
  | "analyze_failed_tests_manual"
  | "review_success";

export type PatchLifecycleTestStatus = "not_run" | "passed" | "failed";

export interface PatchLifecycleToolCallSummary {
  tool_call_id: string;
  tool_name: string;
  status: string;
  run_id: string;
  step_id: string;
  project_id: string;
  created_at: string;
  started_at: string;
  finished_at: string;
  completed_at: string | null;
  returncode: number | null;
  command: string;
  command_kind: string;
  summary: string;
  guard_result_id: string | null;
  guard_revalidated: boolean;
  no_guard_override: boolean;
  stdout_preview: string;
  stderr_preview: string;
  timed_out: boolean;
}

export interface StepPatchLifecycleResponse {
  run_id: string;
  step_id: string;
  project_id: string;
  guard_results: GuardResultItem[];
  proposal_tool_calls: PatchLifecycleToolCallSummary[];
  apply_tool_calls: PatchLifecycleToolCallSummary[];
  test_tool_calls: PatchLifecycleToolCallSummary[];
  latest_proposal: PatchLifecycleToolCallSummary | null;
  latest_apply: PatchLifecycleToolCallSummary | null;
  latest_test: PatchLifecycleToolCallSummary | null;
  apply_succeeded: boolean;
  tests_after_latest_apply: boolean;
  test_status: PatchLifecycleTestStatus;
  confidence: string;
  confidence_reasons: string[];
  safe_test_command_configured: boolean;
  test_command: string;
  recommended_manual_next_action: PatchLifecycleNextAction;
}

// ── Failure-to-Fix Draft ─────────────────────────────────────────────────────

export interface FailureToFixDraftRequest {
  failed_tool_call_id?: string | null;
  apply_tool_call_id?: string | null;
  guard_result_id?: string | null;
  max_stdout_chars?: number;
  max_stderr_chars?: number;
}

export interface FailureToFixDraftResponse {
  run_id: string;
  step_id: string;
  failed_tool_call_id: string;
  apply_tool_call_id: string | null;
  guard_result_id: string | null;
  command: string;
  returncode: number | null;
  stdout_excerpt: string;
  stderr_excerpt: string;
  fix_context: string;
  suggested_next_action: string;
  warnings: string[];
  can_prefill_patch_context: boolean;
}

// ── Semi-Auto Operator Queue ──────────────────────────────────────────────────

export type OperatorQueueItemStatus = "ready" | "blocked" | "manual_required" | "done";
export type OperatorQueueItemPriority = "high" | "medium" | "low";
export type OperatorQueueActionType =
  | "check_guard"
  | "validate_guard_for_proposal"
  | "create_proposal_manual"
  | "apply_patch_manual"
  | "run_tests_manual"
  | "analyze_failed_tests_manual"
  | "prepare_fix_draft_manual"
  | "prepare_agent_step"
  | "review_success"
  | "resolve_blocker"
  | "execute_approval";
export type OperatorQueueDestination =
  | "patch_lifecycle"
  | "source_of_truth_guard"
  | "guard_history"
  | "patch_form"
  | "run_command"
  | "failure_analysis"
  | "agent_step_context"
  | "approval_panel";

export interface OperatorQueueItem {
  id: string;
  run_id: string;
  step_id: string;
  step_title: string;
  priority: OperatorQueueItemPriority;
  status: OperatorQueueItemStatus;
  action_type: OperatorQueueActionType;
  title: string;
  description: string;
  reason: string;
  destination: OperatorQueueDestination;
  guard_result_id: string | null;
  proposal_tool_call_id: string | null;
  apply_tool_call_id: string | null;
  test_tool_call_id: string | null;
  failed_tool_call_id: string | null;
  can_run_directly: boolean;
  requires_confirmation: boolean;
  is_destructive: boolean;
  warnings: string[];
  // Approval context — populated only for execute_approval items (GAP-004)
  approval_id: string | null;
  approval_action_type: string | null;
}

export interface OperatorQueueSummary {
  total_items: number;
  blocked_items: number;
  ready_items: number;
  manual_required_items: number;
  done_items: number;
}

export interface OperatorQueueResponse {
  run_id: string;
  generated_at: string;
  items: OperatorQueueItem[];
  summary: OperatorQueueSummary;
}

export interface AgentStepContextItem {
  step_id: string;
  title: string;
  status: string;
  agent_role: string;
  canonical_agent_id: string;
  requirement_ids: string[];
  module_ids: string[];
  depends_on: string[];
  safety_gates: string[];
  manual_approval_required: boolean;
  provider_allowed: boolean;
  risk_level: string;
  next_safe_action: string;
  ready_for_agent_execution: boolean;
  blockers: string[];
  warnings: string[];
  repo_context_available: boolean;
  detected_stack: string[];
  detected_project_type: string | null;
  relevant_area_hints: string[];
  relevant_manifest_scripts: string[];
  test_discovery_hints: string[];
  protected_path_warnings: string[];
  suggested_safe_commands: string[];
  repo_safety_notes: string[];
  repo_limitations: string[];
}

export interface RunAgentStepContextResponse {
  run_id: string;
  project_id: string | null;
  total_steps: number;
  ready_steps: number;
  blocked_steps: number;
  items: AgentStepContextItem[];
  next_recommended_action: string;
  safety_notes: string[];
}

export interface RepoAwareControlledLoopStage {
  id: string;
  title: string;
  status: string;
  summary: string;
  blockers: string[];
  warnings: string[];
  next_action_label: string | null;
  next_action_kind: string | null;
  related_ids: Record<string, string>;
}

export interface RepoAwareControlledLoopSafeCommand {
  command: string;
  source: string;
  reason: string;
  execution: string;
  warnings: string[];
}

export interface RepoAwareControlledLoopPlanResponse {
  run_id: string;
  step_id: string;
  step_title: string | null;
  repo_context_available: boolean;
  detected_stack: string[];
  current_stage: string;
  next_recommended_action: string;
  stages: RepoAwareControlledLoopStage[];
  safe_command_suggestions: RepoAwareControlledLoopSafeCommand[];
  guarded_proposal_available: boolean;
  patch_draft_available: boolean;
  apply_available: boolean;
  test_run_available: boolean;
  fix_draft_available: boolean;
  safety_notes: string[];
  limitations: string[];
}

export interface StepAgentPatchDraftRequest {
  run_id?: string;
  step_id?: string;
  use_existing_agent_result?: boolean;
  agent_result?: Record<string, unknown> | null;
  operator_note?: string;
  max_target_files?: number;
  max_risks?: number;
  max_validation_steps?: number;
}

export interface StepAgentPatchDraftResponse {
  run_id: string;
  step_id: string;
  step_title: string;
  agent_role: string;
  canonical_agent_id: string;
  requirement_ids: string[];
  module_ids: string[];
  target_files: string[];
  patch_intent: string;
  draft_summary: string;
  suggested_file_path: string;
  suggested_old_text: string;
  suggested_new_text: string;
  risks: string[];
  validation_steps: string[];
  safety_notes: string[];
  blockers: string[];
  warnings: string[];
  ready_for_proposal: boolean;
  next_recommended_action: string;
  source: string;
  repo_context_available: boolean;
  detected_stack: string[];
  relevant_area_hints: string[];
  relevant_manifest_scripts: string[];
  test_discovery_hints: string[];
  protected_path_warnings: string[];
  suggested_safe_commands: string[];
}

export interface StepPatchDraftGuardedProposalRequest {
  run_id?: string;
  step_id?: string;
  patch_draft: Record<string, unknown>;
  confirm_create_proposal?: boolean;
  operator_note?: string;
  allow_no_guard_override?: boolean;
  selected_file_path?: string;
  selected_old_text?: string;
  selected_new_text?: string;
}

export interface StepPatchDraftGuardedProposalResponse {
  run_id: string;
  step_id: string;
  created: boolean;
  proposal_id: string | null;
  guard_result_id: string | null;
  guard_decision: string;
  module_awareness: Record<string, unknown> | null;
  module_policy: Record<string, unknown> | null;
  patch_review: Record<string, unknown> | null;
  blockers: string[];
  warnings: string[];
  safety_notes: string[];
  next_recommended_action: string;
  ready_for_apply: boolean;
}

export interface AutomationRunRequest {
  step_id?: string | null;
  dry_run?: boolean;
  allow_safe_commands?: boolean;
  allow_low_risk_tool_calls?: boolean;
  max_actions?: number;
  stop_on_manual_required?: boolean;
  stop_on_blocked?: boolean;
}

export interface AutomationActionResult {
  action_type: string;
  step_id: string | null;
  status: string;
  executed: boolean;
  risk_level: string;
  reason: string;
  destination: string;
  created_tool_call_id: string | null;
  error: string | null;
  result_summary: string | null;
  warnings: string[];
}

export interface AutomationRunResponse {
  run_id: string;
  dry_run: boolean;
  status: string;
  executed_actions: AutomationActionResult[];
  skipped_actions: AutomationActionResult[];
  next_queue_items: OperatorQueueItem[];
  warnings: string[];
  safety_notes: string[];
}

// ── Approval-Gated Automation v1 ─────────────────────────────────────────────

export interface AutomationApprovalCreateRequest {
  step_id?: string | null;
  action_type: string;
  queue_item_id?: string | null;
  reason?: string;
  payload?: Record<string, unknown>;
}

export interface AutomationApprovalApproveRequest {
  note?: string;
}

export interface AutomationApprovalRejectRequest {
  note?: string;
}

export interface AutomationApprovalExecuteRequest {
  note?: string;
}

export interface AutomationApprovalItem {
  id: string;
  run_id: string;
  step_id: string | null;
  action_type: string;
  /** pending | approved | rejected | executed */
  status: string;
  reason: string;
  risk_level: string;
  is_destructive: boolean;
  created_at: string;
  resolved_at: string | null;
}

export interface AutomationApprovalListResponse {
  run_id: string;
  approvals: AutomationApprovalItem[];
}

export interface AutomationApprovalExecuteResponse {
  approval_id: string;
  run_id: string;
  step_id: string | null;
  action_type: string;
  /** executed | failed | stale | blocked | deferred */
  status: string;
  executed: boolean;
  result_summary: string | null;
  revalidation_error: string | null;
  created_tool_call_id: string | null;
  safety_notes: string[];
}

export interface AgentInfo {
  id: string;
  name: string;
  role: string;
  description: string;
  provider: ProviderType;
  instructions_file: string;
  category: string;
  skills: string[];
  default_tools: string[];
  model_profile: string;
  default_model: string;
  fast_model: string;
  reasoning_model: string;
  can_edit_files: boolean;
  can_run_commands: boolean;
  risk_level: string;
  enabled: boolean;
  best_for: string[];
}

export interface Run {
  id: string;
  task_id: string;
  project_id: string;
  project_path: string;
  current_step_id: string;
  agent_id: string;
  status: RunStatus;
  mode: RunMode;
  prompt: string;
  plan: string;
  result: string;
  logs: string[];
  artifacts: string[];
  run_dir: string;
  created_at: string;
  finished_at: string | null;
}

export interface RunStep {
  id: string;
  run_id: string;
  parent_step_id: string;
  agent_id: string;
  status: string;
  title: string;
  input: string;
  output: string;
  error: string;
  started_at: string;
  finished_at: string;
  created_at: string;
}

export interface RunArtifact {
  name: string;
  path: string;
  content: string;
}

export interface ClarificationAnswerResult {
  artifact: string;
  content: string;
  step: RunStep;
}

export interface RegeneratePlanResult {
  plan: string;
  architecture: string;
  tasks: string;
  staged_steps: RunStep[];
  source: string;
  artifacts: string[];
  step: RunStep | null;
}

export interface ApprovalRequest {
  id: string;
  run_id: string;
  action: string;
  command: string;
  description: string;
  status: ApprovalStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  ollama: string;
}

export interface Config {
  default_mode: string;
  provider_mode?: ProviderMode;
  ollama: { base_url: string; default_model: string; timeout_seconds: number };
  codex: { enabled: boolean };
  claude: { enabled: boolean };
  [key: string]: unknown;
}

export interface WorkspaceChange {
  status: string;
  path: string;
}

export interface WorkspaceStatus {
  branch: string;
  clean: boolean;
  changes: WorkspaceChange[];
  raw: string;
  error: string;
  returncode?: number;
  cwd?: string;
}

export interface TestRunResult {
  command: string;
  status: "passed" | "failed";
  returncode: number;
  stdout: string;
  stderr: string;
  started_at: string;
  finished_at: string;
  report_path: string;
}

export interface ProjectProfileInput {
  name: string;
  path: string;
  description?: string;
  stack?: string;
  package_manager?: string;
  test_command?: string;
  build_command?: string;
  safe_commands?: string[];
  blocked_commands?: string[];
  ignore_paths?: string[];
}

export interface ProjectToolResult {
  approval_required: boolean;
  approval_id?: string;
  tool_call_id?: string;
  project_id: string;
  project_path: string;
  command: string;
  command_type: "test" | "build" | string;
  status: "passed" | "failed" | "approval_required";
  returncode: number | null;
  stdout: string;
  stderr: string;
  started_at?: string;
  finished_at?: string;
  action?: string;
  description?: string;
  report_path: string;
}

export interface ToolCall {
  id: string;
  run_id: string;
  project_id: string;
  step_id: string;
  tool_name: string;
  command: string;
  cwd: string;
  status: string;
  approval_id: string;
  stdout: string;
  stderr: string;
  returncode: number | null;
  report_path: string;
  started_at: string;
  finished_at: string;
  input_json: string;
  output_json: string;
  error: string;
  risk_level: string;
  completed_at: string | null;
  created_at: string;
}

export interface GitChangedFile {
  status: string;
  path: string;
}

export interface GitStatusResponse {
  project_id: string;
  project_path: string;
  command: string[];
  returncode: number;
  stdout: string;
  stderr: string;
  changed_files: GitChangedFile[];
  clean: boolean;
}

export interface GitDiffResponse {
  project_id: string;
  project_path: string;
  commands: string[][];
  returncode: number;
  stat: string;
  name_only: string[];
  diff: string;
  stderr: string;
  truncated: boolean;
}

export interface PatchOperation {
  file_path: string;
  old_text: string;
  new_text: string;
  create_if_missing: boolean;
  replace_all: boolean;
}

export interface ProposePatchRequest {
  operations: PatchOperation[];
  run_id?: string;
  step_id?: string;
  agent_id?: string;
  guard_result_id?: string | null;
  guard_warning_acknowledged?: boolean;
  no_guard_override?: boolean;
}

export interface ProposedPatchFile {
  path: string;
  status: "create" | "modify" | "unchanged" | "error" | string;
  diff: string;
  error?: string;
}

export interface ModuleAwarenessResult {
  has_active_module_map: boolean;
  module_map_version?: number | null;
  touched_modules: Array<{
    id?: string;
    name?: string;
    slug?: string;
    module_type?: string;
    description?: string;
    responsibilities?: string[];
    paths?: string[];
    key_files?: string[];
    related_requirements?: string[];
    test_hints?: string[];
    risks?: string[];
    confidence?: string;
  }>;
  expected_modules: Array<{
    id?: string;
    name?: string;
    slug?: string;
    module_type?: string;
    description?: string;
    responsibilities?: string[];
    paths?: string[];
    key_files?: string[];
    related_requirements?: string[];
    test_hints?: string[];
    risks?: string[];
    confidence?: string;
  }>;
  touched_files: string[];
  expected_files: string[];
  matched_requirement_ids: string[];
  module_risks: string[];
  module_test_hints: string[];
  warnings: string[];
  confidence: string;
}

export interface ModuleAwareGuardPolicyResult {
  verdict: "allowed" | "warning" | "blocked" | string;
  reasons: string[];
  required_acknowledgements: string[];
  affected_modules: string[];
  sensitive_modules: string[];
  unknown_files: string[];
  recommended_tests: string[];
  confidence: string;
}

export interface ProposePatchResponse {
  files: ProposedPatchFile[];
  summary: string;
  warnings: string[];
  tool_call_id?: string;
  proposal_id?: string;
  guard_result_id?: string | null;
  guard_validation_valid?: boolean | null;
  guard_validation_reasons?: string[];
  guard_validation_warnings?: string[];
  no_guard_override?: boolean;
  module_awareness?: ModuleAwarenessResult | null;
  module_policy?: ModuleAwareGuardPolicyResult | null;
}

export interface ApplyPatchRequest {
  operations: PatchOperation[];
  run_id?: string;
  step_id?: string;
  agent_id?: string;
  confirm: boolean;
  expected_summary?: string;
  proposal_id?: string;
}

export interface AppliedPatchFile {
  path: string;
  status: "modified" | "created" | "unchanged" | "error" | string;
  error?: string;
}

export interface ApplyPatchResponse {
  files: AppliedPatchFile[];
  summary: string;
  git_status?: string;
  git_diff_stat?: string;
  warnings: string[];
  tool_call_id?: string;
  applied_from_proposal_id?: string;
  guard_result_id?: string | null;
  guard_revalidated?: boolean | null;
  guard_revalidation_reasons?: string[];
  guard_revalidation_warnings?: string[];
  no_guard_override?: boolean;
}

export interface RolledBackFile {
  path: string;
  operation: string;
  status: string;
  reason?: string;
}

export interface RollbackPatchRequest {
  tool_call_id: string;
  confirm: boolean;
  run_id?: string;
  step_id?: string;
  agent_id?: string;
}

export interface RollbackPatchResponse {
  rolled_back_files: RolledBackFile[];
  skipped_files: RolledBackFile[];
  warnings: string[];
  git_status?: string;
  git_diff_stat?: string;
  tool_call_id?: string;
}

// ── Safe Test Command Runner ──────────────────────────────────────────────────

export type ProjectCommandKind = "test" | "build" | "lint" | "typecheck";

export interface RunProjectCommandRequest {
  command_kind: ProjectCommandKind;
  run_id?: string;
  step_id?: string;
  agent_id?: string;
  timeout_seconds?: number;
}

export interface RunProjectCommandResponse {
  command_kind: string;
  command: string;
  cwd: string;
  returncode: number;
  stdout: string;
  stderr: string;
  duration_ms: number;
  timed_out: boolean;
  tool_call_id: string;
}

// ── Test Result Analysis ──────────────────────────────────────────────────────

export type CommandIssueKind =
  | "test_failure"
  | "assertion_error"
  | "traceback"
  | "type_error"
  | "lint_error"
  | "build_error"
  | "timeout"
  | "unknown";

export interface CommandIssue {
  kind: CommandIssueKind | string;
  file_path: string | null;
  line: number | null;
  message: string;
  raw_excerpt: string;
}

export interface CommandAnalysisRequest {
  tool_call_id?: string;
  stdout?: string;
  stderr?: string;
  returncode?: number;
  command_kind?: string;
  run_id?: string;
  step_id?: string;
  agent_id?: string;
}

export interface CommandAnalysisResponse {
  status: "passed" | "failed" | "timed_out" | "unknown";
  summary: string;
  issues: CommandIssue[];
  suggested_next_actions: string[];
  can_create_fix_proposal: boolean;
  source_tool_call_id: string;
}

export interface RunAgentAssignment {
  id: string;
  run_id: string;
  agent_id: string;
  assigned_role: string;
  reason: string;
  confidence: number;
  status: string;
  created_at: string;
}

export interface AgentSelectionResult {
  selected_agents: RunAgentAssignment[];
  team_size: number;
  recommended_execution_mode: RunMode;
  detected_stack: string[];
  signals: Record<string, unknown>;
}

export interface ApprovalDecisionResult {
  approval: ApprovalRequest;
  execution: ProjectToolResult | null;
  execution_error?: string;
  already_resolved?: boolean;
}

export interface ModelRegistryItem {
  id: string;
  provider: ModelProviderId;
  display_name: string;
  family: string;
  capabilities: string[];
  context_window: number;
  memory_tier: "small" | "medium" | "large" | "xlarge" | string;
  recommended_for: string[];
  installed: boolean;
  enabled: boolean;
  max_parallel: number;
  notes: string;
}

export interface ModelProfile {
  id: string;
  primary_model: string;
  fast_model: string;
  reasoning_model: string;
  fallback_model: string;
  allowed_providers: ModelProviderId[];
  preferred_provider: ModelProviderId;
  max_parallel: number;
  local_only_default: boolean;
  description: string;
}

export interface ProviderInfo {
  id: ModelProviderId;
  display_name: string;
  kind: string;
  enabled: boolean;
  available: boolean;
  local: boolean;
  requires_approval: boolean;
  supports_execution: boolean;
  modes: ProviderMode[];
  notes: string;
}

export interface ProviderStatus {
  id: ModelProviderId;
  enabled: boolean;
  available: boolean;
  status: string;
  models: string[];
  warnings: string[];
}

export interface ModelRouteRequest {
  agent_id?: string;
  task_type?: string;
  model_profile?: string;
  provider_mode?: ProviderMode;
  available_models?: string[];
  project_privacy_level?: string;
  hardware_memory_gb?: number | null;
  user_preference_model?: string;
  user_preference_provider?: ModelProviderId;
}

export interface ModelRouteResult {
  selected_model: string;
  selected_provider: ModelProviderId;
  fallback_model: string;
  reason: string;
  confidence: number;
  warnings: string[];
  model_profile: string;
  task_type: string;
}

export interface ModelRouteDecision {
  id: string;
  run_id: string;
  step_id: string | null;
  agent_id: string;
  task_type: string;
  model_profile: string;
  selected_model: string;
  selected_provider: ModelProviderId;
  fallback_model: string;
  fallback_provider: ModelProviderId | null;
  provider_mode: ProviderMode;
  reason: string;
  confidence: number;
  warnings: string[];
  created_at: string;
  updated_at: string | null;
}

export interface ModelRouteDecisionResponse {
  run_id: string;
  count: number;
  persisted: boolean;
  decisions: ModelRouteDecision[];
  warnings: string[];
}

export type ModelRoutePreviewResponse = ModelRouteDecisionResponse;
export type ModelRoutePersistResponse = ModelRouteDecisionResponse;

// ── Orchestrator Tool Planning ────────────────────────────────────────────────

export interface StepToolRecommendation {
  step_id: string;
  agent_id: string;
  task_type: string;
  recommended_tools: string[];
  reason: string;
  confidence: number;
  warnings: string[];
}

export interface StepToolPlanResponse {
  run_id: string;
  recommendations: StepToolRecommendation[];
  summary: string;
  warnings: string[];
}

// ── Orchestrator Guided Execution ─────────────────────────────────────────────

export interface GuidedStepAction {
  step_id: string;
  action_id: string;
  action_type: string;
  tool_name: string;
  title: string;
  description: string;
  reason: string;
  requires_confirmation: boolean;
  risk_level: string;
  enabled: boolean;
  blocked_reason: string;
  related_tool_call_id: string;
  related_proposal_id: string;
}

export interface GuidedStepExecutionPlan {
  run_id: string;
  step_id: string;
  agent_id: string;
  task_type: string;
  recommended_next_action: GuidedStepAction | null;
  actions: GuidedStepAction[];
  status_summary: string;
  warnings: string[];
}

export interface GuidedExecutionPlanResponse {
  run_id: string;
  steps: GuidedStepExecutionPlan[];
  summary: string;
  warnings: string[];
}

// ── Safe Auto Read/Search ──────────────────────────────────────────────────────

export interface AutoStepReadRequest {
  step_id: string;
  action_type: string;
  query?: string;
  file_path?: string;
  limit?: number;
  run_id?: string;
  agent_id?: string;
}

export interface AutoStepReadResponse {
  run_id: string;
  step_id: string;
  action_type: string;
  tool_call_id: string;
  status: string;
  summary: string;
  result: Record<string, unknown>;
  warnings: string[];
}

// ── Auto Context Gathering ─────────────────────────────────────────────────────

export interface AutoContextGatherRequest {
  max_tool_calls?: number;
  query?: string;
  include_file_patterns?: string[];
  exclude_file_patterns?: string[];
  agent_id?: string;
}

export interface AutoContextGatheredFile {
  file_path: string;
  reason: string;
  source_tool_call_id?: string;
}

export interface AutoContextGatherResponse {
  run_id: string;
  step_id: string;
  status: string;
  summary: string;
  tool_call_ids: string[];
  searched_queries: string[];
  files_considered: string[];
  files_read: AutoContextGatheredFile[];
  warnings: string[];
  next_recommended_action: string;
}

// ── Step Context Bundle ────────────────────────────────────────────────────────

export interface StepContextFile {
  file_path: string;
  source_tool_call_ids: string[];
  reason: string | null;
  snippets: string[];
  read: boolean;
  match_count: number;
}

export interface StepContextBundle {
  run_id: string;
  step_id: string;
  agent_id: string | null;
  task_type: string | null;
  status: string;
  summary: string;
  queries: string[];
  files: StepContextFile[];
  tool_call_ids: string[];
  warnings: string[];
  next_recommended_action: string | null;
}

export interface StepContextBundleResponse {
  bundle: StepContextBundle;
}

// ── Context Patch Draft ────────────────────────────────────────────────────────

export interface ContextPatchDraftRequest {
  preferred_file_path?: string;
  preferred_snippet_index?: number;
  intent?: string;
  agent_id?: string;
}

export interface ContextPatchDraftCandidate {
  file_path: string;
  old_text: string;
  new_text: string;
  reason: string;
  confidence: number;
  source_tool_call_ids: string[];
  warnings: string[];
}

export interface ContextPatchDraftResponse {
  run_id: string;
  step_id: string;
  status: string;
  summary: string;
  candidates: ContextPatchDraftCandidate[];
  recommended_candidate_index: number | null;
  warnings: string[];
  next_recommended_action: string | null;
}

// ── Patch Proposal Review ─────────────────────────────────────────────────────

export interface PatchReviewOperation {
  file_path: string;
  old_text: string;
  new_text: string;
}

export interface PatchReviewRequest {
  operations: PatchReviewOperation[];
  run_id?: string;
  step_id?: string;
  agent_id?: string;
}

export interface PatchReviewIssue {
  severity: "info" | "warning" | "blocker";
  code: string;
  message: string;
  file_path: string | null;
  operation_index: number | null;
}

export interface PatchReviewOperationResult {
  operation_index: number;
  file_path: string;
  status: "ok" | "warning" | "blocked";
  old_text_found: boolean;
  old_text_occurrences: number;
  estimated_diff_lines: number;
  issues: PatchReviewIssue[];
}

export interface PatchReviewResponse {
  status: "ok" | "warning" | "blocked";
  summary: string;
  operation_results: PatchReviewOperationResult[];
  issues: PatchReviewIssue[];
  safe_to_create_proposal: boolean;
  safe_to_apply: boolean;
}

// ── Approval-gated Patch Workflow Orchestrator ────────────────────────────────

export interface PatchWorkflowStage {
  stage_id: string;
  title: string;
  status: "not_started" | "ready" | "blocked" | "completed" | "warning";
  summary: string;
  related_tool_call_ids: string[];
  warnings: string[];
  blockers: string[];
}

export interface PatchWorkflowNextAction {
  action_type: string;
  title: string;
  description: string;
  risk_level: "low" | "medium" | "high";
  requires_confirmation: boolean;
  enabled: boolean;
  blocked_reason: string | null;
}

export interface StepPatchWorkflowPlan {
  run_id: string;
  step_id: string;
  agent_id: string | null;
  task_type: string | null;
  status: "not_started" | "in_progress" | "blocked" | "ready_for_review" | "ready_for_tests" | "done";
  summary: string;
  stages: PatchWorkflowStage[];
  recommended_next_action: PatchWorkflowNextAction | null;
  warnings: string[];
  blockers: string[];
}

export interface PatchWorkflowPlanResponse {
  run_id: string;
  steps: StepPatchWorkflowPlan[];
  summary: string;
  warnings: string[];
}

// ── Agent Execution Harness v1 ────────────────────────────────────────────────

export interface AgentExecutionRequest {
  agent_id?: string | null;
  task_type?: string;
  mode: "dry_run" | "mock" | "provider";
  allow_provider_call?: boolean;
  persist_result?: boolean;
  max_output_chars?: number;
  user_instruction?: string;
  include_requirement_context?: boolean;
  include_recent_tool_calls?: boolean;
  include_patch_lifecycle?: boolean;
}

export interface AgentModuleContext {
  project_id: string;
  module_map_version: number | null;
  has_active_module_map: boolean;
  matched_modules: Array<{
    id?: string;
    name?: string;
    slug?: string;
    module_type?: string;
    description?: string;
    responsibilities?: string[];
    paths?: string[];
    key_files?: string[];
    related_requirements?: string[];
    test_hints?: string[];
    risks?: string[];
    confidence?: string;
  }>;
  module_summary: string;
  matched_paths: string[];
  matched_requirement_ids: string[];
}

export interface AgentExecutionContext {
  run_id: string;
  step_id: string;
  step_title: string;
  step_input_summary: string;
  requirement_ids: string[];
  source_of_truth_summary: string;
  acceptance_criteria: string;
  constraints: string;
  forbidden_changes: string;
  recent_tool_call_summary: string;
  patch_lifecycle_summary: string;
  operator_queue_summary: string;
  project_name: string;
  project_path: string;
  recommended_agent_id: string;
  recommended_agent_name: string;
  recommended_task_type: string;
  available_agents: Array<{ id: string; name: string; role: string; category: string }>;
  module_context?: AgentModuleContext | null;
}

export interface AgentExecutionResult {
  summary: string;
  analysis: string;
  proposed_files: string[];
  patch_intent: string;
  risks: string[];
  test_suggestions: string[];
  questions: string[];
  recommended_next_action: string;
  can_feed_patch_draft: boolean;
}

export interface AgentExecutionResponse {
  run_id: string;
  step_id: string;
  agent_id: string;
  mode: "dry_run" | "mock" | "provider";
  status: "planned" | "completed" | "provider_unavailable" | "blocked" | "failed";
  executed: boolean;
  provider_called: boolean;
  tool_call_id: string | null;
  context: AgentExecutionContext;
  result: AgentExecutionResult | null;
  prompt_preview: string;
  warnings: string[];
  safety_notes: string[];
}

export interface ExecuteNextStepRequest {
  agent_id?: string | null;
  task_type?: string;
  mode?: "dry_run" | "mock" | "provider";
  allow_provider_call?: boolean;
  persist_result?: boolean;
  max_output_chars?: number;
  user_instruction?: string;
}

export interface ExecuteNextStepResponse {
  run_id: string;
  step_id: string;
  step_title: string;
  status: string;
  message: string;
  artifact: string;
  execution: AgentExecutionResponse;
  step: RunStep | null;
}

export interface AgentExecutionListItem {
  tool_call_id: string;
  agent_id: string;
  mode: string;
  task_type: string;
  status: string;
  created_at: string;
  summary: string;
  can_feed_patch_draft: boolean;
}

export interface AgentExecutionListResponse {
  run_id: string;
  step_id: string;
  executions: AgentExecutionListItem[];
  total: number;
  note: string;
}

// Agent Result → Patch Draft Bridge v1

export interface AgentPatchDraftRequest {
  agent_execution_tool_call_id?: string | null;
  agent_result?: AgentExecutionResult | null;
  include_context?: boolean;
  include_risks?: boolean;
  include_tests?: boolean;
  max_context_chars?: number;
}

export interface AgentPatchDraftResponse {
  run_id: string;
  step_id: string;
  source_agent_execution_id: string | null;
  can_prefill_patch_context: boolean;
  recommended_file_path: string | null;
  patch_context: string;
  patch_summary: string;
  module_context?: AgentModuleContext | null;
  module_context_summary: string;
  recommended_files_from_module_map: string[];
  module_risks: string[];
  module_test_hints: string[];
  proposed_files: string[];
  risks: string[];
  test_suggestions: string[];
  questions: string[];
  guard_required: boolean;
  warnings: string[];
  safety_notes: string[];
}

// ── Bounded Autonomous Patch-Test-Fix Loop v1 ─────────────────────────────────

export interface BoundedAutonomousLoopRequest {
  step_id?: string | null;
  max_iterations?: number;
  max_actions_per_iteration?: number;
  dry_run?: boolean;
  allow_provider_call?: boolean;
  allow_safe_commands?: boolean;
  allow_low_risk_tool_calls?: boolean;
  stop_on_approval_required?: boolean;
  stop_on_blocked?: boolean;
  stop_on_test_failure?: boolean;
  stop_on_no_safe_action?: boolean;
}

export interface BoundedAutonomousLoopIteration {
  iteration: number;
  status: string;
  step_id: string | null;
  queue_action: string | null;
  executed_actions: AutomationActionResult[];
  approvals_required: string[];
  blocked_reasons: string[];
  test_status: string | null;
  next_recommended_action: string | null;
  warnings: string[];
  safety_notes: string[];
}

export interface BoundedAutonomousLoopResponse {
  run_id: string;
  step_id: string | null;
  dry_run: boolean;
  status: string;
  iterations: BoundedAutonomousLoopIteration[];
  final_queue_summary: OperatorQueueSummary | null;
  final_recommended_action: string | null;
  approvals_required: string[];
  warnings: string[];
  safety_notes: string[];
  // Stop-reason fields for operator clarity (GAP-011)
  stop_reason: string | null;
  blocked_action_type: string | null;
  pending_approval_id: string | null;
  pending_approval_action_type: string | null;
}

// ── Full Delivery Loop v1 ─────────────────────────────────────────────────────

export interface StepModuleDeliverySummary {
  step_id: string;
  step_title: string;
  touched_modules: string[];
  expected_modules: string[];
  touched_files: string[];
  unknown_files: string[];
  module_policy_verdicts: string[];
  module_warnings: string[];
  module_risks: string[];
  module_test_hints: string[];
}

export interface RunModuleDeliverySummary {
  has_module_data: boolean;
  touched_modules: string[];
  expected_modules: string[];
  unknown_files: string[];
  sensitive_modules: string[];
  warning_count: number;
  blocked_policy_count: number;
  recommended_tests: string[];
  per_step: StepModuleDeliverySummary[];
}

export interface StepDeliverySummary {
  step_id: string;
  step_title: string;
  status: string;
  readiness: string;
  requirement_ids: string[];
  guard_status: string;
  proposal_status: string;
  apply_status: string;
  test_status: string;
  fix_status: string;
  approval_status: string;
  changed_files: string[];
  unresolved_issues: string[];
  warnings: string[];
  recommended_next_action: string | null;
  module_summary?: StepModuleDeliverySummary | null;
}

export interface RunDeliverySummary {
  run_id: string;
  project_id: string | null;
  project_name: string | null;
  readiness: string;
  total_steps: number;
  ready_steps: number;
  blocked_steps: number;
  needs_test_steps: number;
  failed_test_steps: number;
  /** Steps with a pending automation approval (v2) */
  approval_pending_steps: number;
  changed_files: string[];
  requirement_ids: string[];
  guards_total: number;
  proposals_total: number;
  applies_total: number;
  tests_total: number;
  approvals_total: number;
  unresolved_issues: string[];
  warnings: string[];
  recommended_next_action: string | null;
  module_summary?: RunModuleDeliverySummary | null;
}

export interface DeliveryReportRequest {
  include_markdown?: boolean;
  include_step_details?: boolean;
  include_tool_history?: boolean;
  max_markdown_chars?: number;
}

export interface DeliveryReportResponse {
  run_id: string;
  generated_at: string;
  summary: RunDeliverySummary;
  steps: StepDeliverySummary[];
  markdown_report: string;
  safety_notes: string[];
}

// ── Persistent Source of Truth v1 ─────────────────────────────────────────────

export type SoTRequirementPriority = "must" | "should" | "could" | "wont" | "unknown";
export type SoTRequirementStatus =
  | "proposed"
  | "confirmed"
  | "assumed"
  | "missing"
  | "rejected"
  | "implemented"
  | "needs_validation";
export type SoTDocumentStatus = "draft" | "active" | "archived";
export type SoTDriftRisk = "low" | "medium" | "high" | "critical";

export interface ProjectSourceOfTruthRequirement {
  id: string;
  title: string;
  description: string;
  priority: SoTRequirementPriority;
  status: SoTRequirementStatus;
  acceptance_criteria: string[];
  constraints: string[];
  tags: string[];
}

export interface ProjectSourceOfTruthDecision {
  id: string;
  title: string;
  description: string;
  /** "proposed" | "accepted" | "superseded" | "rejected" */
  status: string;
  rationale: string;
  consequences: string;
}

export interface ProjectSourceOfTruthDocument {
  id: string;
  project_id: string;
  version: number;
  status: SoTDocumentStatus;
  product_name: string;
  product_summary: string;
  project_intent: string;
  target_users: string[];
  goals: string[];
  non_goals: string[];
  requirements: ProjectSourceOfTruthRequirement[];
  constraints: string[];
  forbidden_changes: string[];
  acceptance_criteria: string[];
  architecture_notes: string;
  decisions: ProjectSourceOfTruthDecision[];
  assumptions: string[];
  risks: string[];
  open_questions: string[];
  source: string;
  created_at: string;
  updated_at: string | null;
}

export interface SourceOfTruthUpsertRequest {
  product_name?: string;
  product_summary?: string;
  project_intent?: string;
  target_users?: string[];
  goals?: string[];
  non_goals?: string[];
  requirements?: ProjectSourceOfTruthRequirement[];
  constraints?: string[];
  forbidden_changes?: string[];
  acceptance_criteria?: string[];
  architecture_notes?: string;
  decisions?: ProjectSourceOfTruthDecision[];
  assumptions?: string[];
  risks?: string[];
  open_questions?: string[];
  source?: string;
  /** "draft" (default) | "active" */
  status?: SoTDocumentStatus;
}

export interface SourceOfTruthResponse {
  project_id: string;
  document: ProjectSourceOfTruthDocument | null;
  found: boolean;
  warnings: string[];
}

export interface SourceOfTruthHistoryItem {
  id: string;
  project_id: string;
  version: number;
  status: SoTDocumentStatus;
  product_name: string;
  source: string;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
}

export interface SourceOfTruthHistoryResponse {
  project_id: string;
  versions: SourceOfTruthHistoryItem[];
  total: number;
}

export interface SourceOfTruthValidationResponse {
  valid: boolean;
  drift_risk: SoTDriftRisk;
  errors: string[];
  warnings: string[];
}

export interface SourceOfTruthSummaryResponse {
  project_id: string;
  found: boolean;
  summary: string;
  requirement_context: string;
  warnings: string[];
}

// ── Project Module Map v1 ─────────────────────────────────────────────────────

export type ModuleType =
  | "feature"
  | "backend"
  | "frontend"
  | "database"
  | "shared"
  | "tests"
  | "infrastructure"
  | "docs"
  | "unknown";

export type ModuleConfidence = "low" | "medium" | "high";

export interface ProjectModuleMapItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  module_type: ModuleType;
  responsibilities: string[];
  paths: string[];
  key_files: string[];
  related_requirements: string[];
  test_hints: string[];
  risks: string[];
  confidence: ModuleConfidence;
}

export interface ProjectModuleMapDocument {
  id: string;
  project_id: string;
  version: number;
  status: string;
  modules: ProjectModuleMapItem[];
  ignored_paths: string[];
  scan_summary: string;
  source: string;
  created_at: string;
  updated_at: string | null;
}

export interface ProjectModuleMapUpsertRequest {
  modules: ProjectModuleMapItem[];
  ignored_paths?: string[];
  scan_summary?: string;
  source?: string;
  status?: string;
}

export interface ProjectModuleMapResponse {
  project_id: string;
  document: ProjectModuleMapDocument | null;
  found: boolean;
  warnings: string[];
}

export interface ProjectModuleMapHistoryItem {
  id: string;
  project_id: string;
  version: number;
  status: string;
  module_count: number;
  source: string;
  scan_summary: string;
  created_at: string;
  updated_at: string | null;
  archived_at: string | null;
}

export interface ProjectModuleMapHistoryResponse {
  project_id: string;
  history: ProjectModuleMapHistoryItem[];
  total: number;
}

export interface ProjectModuleMapValidationResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export interface ProjectModuleMapSummaryResponse {
  project_id: string;
  found: boolean;
  summary: string;
  module_names: string[];
  warnings: string[];
}

export interface ProjectModuleMapScanPreviewRequest {
  max_files?: number;
  max_depth?: number;
  extra_ignore_paths?: string[];
}

export interface ProjectModuleMapScanPreviewResponse {
  project_id: string;
  modules: ProjectModuleMapItem[];
  scan_summary: string;
  files_scanned: number;
  files_skipped: number;
  truncated: boolean;
  warnings: string[];
}

// ── Project Context Cockpit v1 ────────────────────────────────────────────────

export interface CockpitSourceOfTruth {
  available: boolean;
  version: number | null;
  product_name: string;
  requirement_count: number;
  risk_count: number;
  open_question_count: number;
}

export interface CockpitModuleMap {
  available: boolean;
  version: number | null;
  module_count: number;
  key_modules: string[];
}

export interface CockpitRunStatus {
  readiness: string;
  completed_steps: number;
  total_steps: number;
  pending_approval_count: number;
  guard_blocker_count: number;
  tests_failed_count: number;
}

export interface CockpitModuleAwareness {
  touched_modules: string[];
  expected_modules: string[];
  blocked_policy_count: number;
  warning_count: number;
  recommended_tests: string[];
}

export interface CockpitNextAction {
  label: string;
  reason: string;
  target_panel: string;
  /** "info" | "warning" | "blocked" | "ready" */
  severity: string;
}

export interface ProjectContextCockpitSummary {
  run_id: string;
  has_project: boolean;
  project_id: string | null;
  project_name: string | null;
  source_of_truth: CockpitSourceOfTruth;
  module_map: CockpitModuleMap;
  run: CockpitRunStatus;
  module_awareness: CockpitModuleAwareness;
  next_action: CockpitNextAction;
  safety_notes: string[];
}

// ── Unified Autonomous Project Intake v1 ─────────────────────────────────────

export type UnifiedIntakeMode = "idea" | "document" | "existing_project";

export interface UnifiedIntakeRequest {
  mode: UnifiedIntakeMode;
  title?: string;
  raw_input?: string;
  document_excerpt?: string;
  project_path?: string;
  known_stack?: string[];
  constraints?: string[];
  desired_outcome?: string;
}

export interface ExistingProjectRepoIntakeRequest {
  project_id?: string | null;
  project_path?: string;
  max_files?: number;
  max_depth?: number;
  include_manifest_snippets?: boolean;
}

export interface ExistingProjectDetectedArea {
  id: string;
  title: string;
  kind: string;
  path_hints: string[];
  confidence: string;
  notes: string[];
}

export interface ExistingProjectManifestSummary {
  path: string;
  kind: string;
  detected_scripts: string[];
  dependencies_hint: string[];
  warnings: string[];
}

export interface ExistingProjectRepoIntakeResponse {
  project_id: string | null;
  project_path_hint: string;
  detected_stack: string[];
  detected_project_type: string;
  detected_areas: ExistingProjectDetectedArea[];
  manifest_summaries: ExistingProjectManifestSummary[];
  protected_path_warnings: string[];
  source_of_truth_hints: string[];
  module_map_hints: string[];
  test_discovery_hints: string[];
  clarifying_questions: string[];
  recommended_first_safe_action: string;
  safety_notes: string[];
  limitations: string[];
}

export interface ClarifyingQuestion {
  id: string;
  question: string;
  reason: string;
  required: boolean;
  category: string;
}

export interface DraftSourceOfTruthPreview {
  product_name: string;
  product_summary: string;
  target_users: string[];
  goals: string[];
  non_goals: string[];
  constraints: string[];
  risks: string[];
  open_questions: string[];
  confidence: string;
}

export interface DraftModuleMapPreview {
  available: boolean;
  modules: Array<{ name?: string; type?: string; description?: string; [key: string]: unknown }>;
  inferred_stack: string[];
  unknowns: string[];
  confidence: string;
}

export interface DraftAgentPlanStep {
  id: string;
  title: string;
  agent_role: string;
  reason: string;
  depends_on: string[];
  risk_level: string;
  expected_outputs: string[];
}

export interface UnifiedAutonomousIntakePreviewResponse {
  mode: string;
  classification_reason: string;
  clarifying_questions: ClarifyingQuestion[];
  source_of_truth_preview: DraftSourceOfTruthPreview;
  module_map_preview: DraftModuleMapPreview;
  multi_agent_plan: DraftAgentPlanStep[];
  next_recommended_action: string;
  safety_notes: string[];
  limitations: string[];
}

// ── Clarifying Questions Engine v1 ────────────────────────────────────────────

export interface ClarifyingAnswer {
  question_id: string;
  answer: string;
  skipped: boolean;
}

export interface ClarifyingQuestionSet {
  mode: string;
  questions: ClarifyingQuestion[];
  required_count: number;
  optional_count: number;
  categories: string[];
  next_recommended_action: string;
}

export interface ClarifyingAnswersRequest {
  intake: UnifiedIntakeRequest;
  answers: ClarifyingAnswer[];
}

export interface ClarifyingAnswerGap {
  question_id: string;
  reason: string;
  severity: string;
}

export interface ClarifiedIntakePreviewResponse {
  mode: string;
  answered_question_ids: string[];
  missing_required_questions: ClarifyingAnswerGap[];
  applied_answer_summary: string[];
  source_of_truth_preview: DraftSourceOfTruthPreview;
  module_map_preview: DraftModuleMapPreview;
  multi_agent_plan: DraftAgentPlanStep[];
  confidence_before: string;
  confidence_after: string;
  next_recommended_action: string;
  safety_notes: string[];
  limitations: string[];
}

// ── Auto Source of Truth Draft from Intake v1 ────────────────────────────────

export interface SourceOfTruthDraftRequirement {
  id: string;
  title: string;
  description: string;
  priority: string;
  status: string;
  acceptance_criteria: string[];
  constraints: string[];
  tags: string[];
}

export interface SourceOfTruthDraftUpsertPayload {
  product_name: string;
  product_summary: string;
  project_intent: string;
  target_users: string[];
  goals: string[];
  non_goals: string[];
  requirements: SourceOfTruthDraftRequirement[];
  constraints: string[];
  forbidden_changes: string[];
  acceptance_criteria: string[];
  architecture_notes: string;
  assumptions: string[];
  risks: string[];
  open_questions: string[];
  source: string;
  status: string;
}

export interface SourceOfTruthDraftValidation {
  valid: boolean;
  drift_risk: string;
  errors: string[];
  warnings: string[];
  fields_populated: number;
  requirements_count: number;
}

export interface SourceOfTruthDraftFromIntakeRequest {
  intake: ClarifyingAnswersRequest;
  project_id?: string | null;
  confirm_persist?: boolean;
}

export interface SourceOfTruthDraftFromIntakeResponse {
  mode: string;
  source: string;
  draft: SourceOfTruthDraftUpsertPayload;
  validation: SourceOfTruthDraftValidation;
  persisted: boolean;
  project_id: string | null;
  version: number | null;
  confidence: string;
  next_recommended_action: string;
  safety_notes: string[];
  limitations: string[];
}

// ── Auto Module Map Draft from Intake v1 ────────────────────────────────────

export interface ModuleMapDraftValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  missing_fields: string[];
  confidence: string;
  module_count: number;
  requirement_coverage_count: number;
}

export interface ModuleMapDraftFromIntakeRequest {
  intake: ClarifyingAnswersRequest;
  source_of_truth_draft?: SourceOfTruthDraftUpsertPayload | Record<string, unknown> | null;
  project_id?: string | null;
  confirm_persist?: boolean;
}

export interface ModuleMapDraftFromIntakeResponse {
  persisted: boolean;
  project_id: string | null;
  module_map_id: string | null;
  version: number | null;
  draft: ProjectModuleMapUpsertRequest;
  validation: ModuleMapDraftValidation;
  inferred_stack: string[];
  applied_answer_summary: string[];
  missing_required_questions: ClarifyingAnswerGap[];
  next_recommended_action: string;
  safety_notes: string[];
  limitations: string[];
}

// ── Multi-Agent Plan from Intake v1 ────────────────────────────────────────

export interface MultiAgentPlanFromIntakeRequest {
  intake: UnifiedIntakeRequest;
  answers: ClarifyingAnswer[];
  source_of_truth_draft?: SourceOfTruthDraftUpsertPayload | Record<string, unknown> | null;
  module_map_draft?: ProjectModuleMapUpsertRequest | Record<string, unknown> | null;
}

export interface MultiAgentPlanRisk {
  id: string;
  severity: string;
  description: string;
  affected_modules: string[];
  mitigation: string;
}

export interface MultiAgentPlanTask {
  id: string;
  title: string;
  description: string;
  agent_role: string;
  target_modules: string[];
  requirement_ids: string[];
  depends_on: string[];
  expected_outputs: string[];
  validation_steps: string[];
  risk_level: string;
  manual_approval_required: boolean;
  provider_allowed: boolean;
}

export interface MultiAgentPlanMilestone {
  id: string;
  title: string;
  goal: string;
  task_ids: string[];
  exit_criteria: string[];
}

export interface MultiAgentPlanValidation {
  valid: boolean;
  errors: string[];
  warnings: string[];
  missing_inputs: string[];
  readiness: string;
}

export interface MultiAgentPlanFromIntakeResponse {
  mode: string;
  plan_title: string;
  plan_summary: string;
  tasks: MultiAgentPlanTask[];
  milestones: MultiAgentPlanMilestone[];
  risks: MultiAgentPlanRisk[];
  recommended_first_action: string;
  recommended_first_task_id: string | null;
  validation: MultiAgentPlanValidation;
  safety_notes: string[];
  limitations: string[];
}

// ── Intake Development Run Preview v1 ─────────────────────────────────────

export interface IntakeDevelopmentRunPreviewRequest {
  intake: UnifiedIntakeRequest;
  answers: ClarifyingAnswer[];
  source_of_truth_draft?: SourceOfTruthDraftUpsertPayload | Record<string, unknown> | null;
  module_map_draft?: ProjectModuleMapUpsertRequest | Record<string, unknown> | null;
  multi_agent_plan?: MultiAgentPlanFromIntakeResponse | Record<string, unknown> | null;
  preferred_mode?: string;
}

export interface DevelopmentRunPreviewStep {
  id: string;
  title: string;
  description: string;
  agent_role: string;
  requirement_ids: string[];
  module_ids: string[];
  depends_on: string[];
  expected_outputs: string[];
  validation_steps: string[];
  safety_gates: string[];
  manual_approval_required: boolean;
  provider_allowed: boolean;
  risk_level: string;
  estimated_order: number;
}

export interface DevelopmentRunPreviewValidation {
  ready_to_create_run: boolean;
  readiness: string;
  errors: string[];
  warnings: string[];
  missing_inputs: string[];
  blocked_reasons: string[];
}

export interface IntakeDevelopmentRunPreviewResponse {
  preview_only: boolean;
  mode: string;
  run_title: string;
  run_goal: string;
  recommended_run_mode: string;
  steps: DevelopmentRunPreviewStep[];
  agent_roles: string[];
  requirement_ids: string[];
  module_ids: string[];
  safety_summary: string[];
  recommended_first_safe_action: string;
  validation: DevelopmentRunPreviewValidation;
  next_recommended_action: string;
  limitations: string[];
}


// ── Confirmed Run Creation Contract Preview ────────────────────────────────

export interface ConfirmedRunCreationRequirementPreview {
  id: string;
  description: string;
  required: boolean;
  satisfied: boolean;
  severity: string;
}

export interface ConfirmedRunCreationSafetyGatePreview {
  id: string;
  title: string;
  description: string;
  required_before_creation: boolean;
  required_before_execution: boolean;
}

export interface IntakeConfirmedRunCreationContractPreviewRequest {
  development_run_preview: Record<string, unknown>;
  project_id?: string | null;
  confirm?: boolean;
  preview_only?: boolean;
  source_of_truth_valid?: boolean;
  module_map_valid?: boolean;
  multi_agent_plan_valid?: boolean;
}

export interface IntakeConfirmedRunCreationContractPreviewResponse {
  preview_only: boolean;
  decision: "allowed" | "warning" | "blocked";
  risk: "low" | "medium" | "high" | "critical";
  can_create_pending_run: boolean;
  blockers: string[];
  warnings: string[];
  requirements: ConfirmedRunCreationRequirementPreview[];
  safety_gates: ConfirmedRunCreationSafetyGatePreview[];
  allowed_created_entities: string[];
  forbidden_created_entities: string[];
  required_statuses: Record<string, string>;
  required_operator_confirmations: string[];
  next_recommended_action: string;
  contract_note: string;
}

// ── Confirmed Development Run Bridge (Fastlane v1) ─────────────────────────

export interface ConfirmedDevelopmentRunCreateRequest {
  project_id: string;
  confirm_create: boolean;
  contract_confirmed: boolean;
  source_of_truth_confirmed: boolean;
  module_map_confirmed: boolean;
  provider_disabled_confirmed: boolean;
  later_actions_confirmed: boolean;
  development_run_preview: Record<string, unknown>;
  contract_preview?: Record<string, unknown> | null;
  repo_intake_preview?: Record<string, unknown> | null;
  preferred_run_mode?: string;
}

export interface ConfirmedDevelopmentRunCreatedStep {
  step_id: string;
  title: string;
  agent_role: string;
  status: string;
  requirement_ids: string[];
  module_ids: string[];
  depends_on: string[];
  manual_approval_required: boolean;
  provider_allowed: boolean;
}

export interface ConfirmedDevelopmentRunCreateResponse {
  created: boolean;
  run_id: string | null;
  project_id: string;
  status: string;
  run_mode: string;
  steps: ConfirmedDevelopmentRunCreatedStep[];
  contract_decision: string;
  blockers: string[];
  warnings: string[];
  safety_notes: string[];
  next_recommended_action: string;
  open_run_url_hint: string | null;
}

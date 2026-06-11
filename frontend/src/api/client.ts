import type {
  ConfirmedPlanRunPreviewRequest,
  ConfirmedPlanRunPreviewResponse,
  ConfirmedRunFromPlanRequest,
  ConfirmedRunFromPlanResponse,
  DevelopmentPlanPreviewRequest,
  DevelopmentPlanPreviewResponse,
  Project,
  ProjectBriefDraftRequest,
  ProjectBriefDraftResponse,
  UnifiedIntakeRequest,
  UnifiedAutonomousIntakePreviewResponse,
  ExistingProjectRepoIntakeRequest,
  ExistingProjectRepoIntakeResponse,
  ClarifyingAnswersRequest,
  ClarifyingQuestionSet,
  ClarifiedIntakePreviewResponse,
  ProjectIntakeRequest,
  ProjectIntakeResponse,
  RequirementCoveragePreviewRequest,
  RequirementCoveragePreviewResponse,
  SourceOfTruthPreviewRequest,
  SourceOfTruthPreviewResponse,
  StepSourceOfTruthGuardRequest,
  StepSourceOfTruthGuardResponse,
  ProjectProfileInput,
  ProjectToolResult,
  ApplyPatchRequest,
  ApplyPatchResponse,
  ProposePatchRequest,
  ProposePatchResponse,
  ApprovalDecisionResult,
  AgentInfo,
  AgentSelectionResult,
  CommandAnalysisRequest,
  CommandAnalysisResponse,
  GitDiffResponse,
  GitStatusResponse,
  ModelProfile,
  ModelRouteDecision,
  ModelRoutePersistResponse,
  ModelRoutePreviewResponse,
  ModelRegistryItem,
  ModelRouteRequest,
  ModelRouteResult,
  ProviderInfo,
  ProviderMode,
  ProviderStatus,
  GuidedExecutionPlanResponse,
  RollbackPatchRequest,
  RollbackPatchResponse,
  Run,
  StepToolPlanResponse,
  RunArtifact,
  RunAgentAssignment,
  RunProjectCommandRequest,
  RunProjectCommandResponse,
  RunStep,
  ClarificationAnswerResult,
  RegeneratePlanResult,
  ToolCall,
  WorkspaceStatus,
  TestRunResult,
  AutoStepReadRequest,
  AutoStepReadResponse,
  AutoContextGatherRequest,
  AutoContextGatherResponse,
  StepContextBundleResponse,
  ContextPatchDraftRequest,
  ContextPatchDraftResponse,
  PatchReviewRequest,
  PatchReviewResponse,
  PatchWorkflowPlanResponse,
  GuardResultItem,
  GuardResultListResponse,
  GuardProposalValidationRequest,
  GuardProposalValidationResponse,
  StepPatchLifecycleResponse,
  FailureToFixDraftRequest,
  FailureToFixDraftResponse,
  AutomationRunRequest,
  AutomationRunResponse,
  OperatorQueueResponse,
  RunAgentStepContextResponse,
  RepoAwareControlledLoopPlanResponse,
  StepAgentPatchDraftRequest,
  StepAgentPatchDraftResponse,
  StepPatchDraftGuardedProposalRequest,
  StepPatchDraftGuardedProposalResponse,
  AutomationApprovalCreateRequest,
  AutomationApprovalApproveRequest,
  AutomationApprovalRejectRequest,
  AutomationApprovalExecuteRequest,
  AutomationApprovalItem,
  AutomationApprovalListResponse,
  AutomationApprovalExecuteResponse,
  IntakeDevelopmentRunPreviewRequest,
  IntakeDevelopmentRunPreviewResponse,
  IntakeConfirmedRunCreationContractPreviewRequest,
  IntakeConfirmedRunCreationContractPreviewResponse,
  ConfirmedDevelopmentRunCreateRequest,
  ConfirmedDevelopmentRunCreateResponse,
  MultiAgentPlanFromIntakeRequest,
  MultiAgentPlanFromIntakeResponse,
  SourceOfTruthDraftFromIntakeRequest,
  SourceOfTruthDraftFromIntakeResponse,
  ModuleMapDraftFromIntakeRequest,
  ModuleMapDraftFromIntakeResponse,
  ExecuteNextStepRequest,
  ExecuteNextStepResponse,
} from "../types";

const BASE = "";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

// Health
export const getHealth = () => request<{ status: string; ollama: string }>("/health");

// Projects
export const getProjects = async () => {
  const projects = await request<Partial<Project>[]>("/api/projects");
  return projects.map(normalizeProject);
};
export const getProject = async (id: string) => normalizeProject(await request<Partial<Project>>(`/api/projects/${id}`));
export const createProject = (data: ProjectProfileInput) =>
  request<Partial<Project>>("/api/projects", { method: "POST", body: JSON.stringify(data) }).then(normalizeProject);
export const updateProject = (id: string, data: Partial<ProjectProfileInput>) =>
  request<Partial<Project>>(`/api/projects/${id}`, { method: "PATCH", body: JSON.stringify(data) }).then(normalizeProject);
export const analyzeProjectIntake = (data: ProjectIntakeRequest) =>
  request<ProjectIntakeResponse>("/api/project-intake/questions", { method: "POST", body: JSON.stringify(data) });
export const draftProjectBrief = (data: ProjectBriefDraftRequest) =>
  request<ProjectBriefDraftResponse>("/api/project-intake/brief-draft", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const previewIntakePlan = (data: DevelopmentPlanPreviewRequest) =>
  request<DevelopmentPlanPreviewResponse>("/api/project-intake/plan-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const previewSourceOfTruth = (data: SourceOfTruthPreviewRequest) =>
  request<SourceOfTruthPreviewResponse>("/api/project-intake/source-of-truth-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const previewRequirementCoverage = (data: RequirementCoveragePreviewRequest) =>
  request<RequirementCoveragePreviewResponse>("/api/project-intake/coverage-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const previewConfirmedPlanRun = (data: ConfirmedPlanRunPreviewRequest) =>
  request<ConfirmedPlanRunPreviewResponse>("/api/project-intake/run-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
export const createRunFromConfirmedPlan = (data: ConfirmedRunFromPlanRequest) =>
  request<ConfirmedRunFromPlanResponse>("/api/project-intake/confirmed-run", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Agents
export const getAgents = () => request<any[]>("/api/agents");
export const getAgentRegistry = () => request<AgentInfo[]>("/api/agents/registry");

// Models and providers
export const getModelRegistry = () => request<ModelRegistryItem[]>("/api/models/registry");
export const getModelProfiles = () => request<ModelProfile[]>("/api/models/profiles");
export const routeModel = (data: ModelRouteRequest) =>
  request<ModelRouteResult>("/api/models/route", { method: "POST", body: JSON.stringify(data) });
export const getProviders = () => request<ProviderInfo[]>("/api/providers");
export const getProviderStatus = () => request<ProviderStatus[]>("/api/providers/status");
export const updateProviderMode = (providerMode: ProviderMode) =>
  request<{ provider_mode: ProviderMode }>("/api/settings/provider-mode", {
    method: "PATCH",
    body: JSON.stringify({ provider_mode: providerMode }),
  });

// Runs
export const getRuns = () => request<Run[]>("/api/runs");
export const createRun = (data: { prompt: string; mode?: string; project_id?: string }) =>
  request<Run>("/api/runs", { method: "POST", body: JSON.stringify(data) });
export const getRun = (id: string) => request<Run>(`/api/runs/${id}`);
export const getRunSteps = (id: string) => request<RunStep[]>(`/api/runs/${id}/steps`);
export const checkStepSourceOfTruthGuard = (runId: string, stepId: string, data: StepSourceOfTruthGuardRequest) =>
  request<StepSourceOfTruthGuardResponse>(`/api/runs/${runId}/steps/${stepId}/source-of-truth-guard`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const listRunGuardResults = (runId: string, params?: { step_id?: string; include_stale?: boolean; limit?: number }) => {
  const qs = new URLSearchParams();
  if (params?.step_id) qs.set("step_id", params.step_id);
  if (params?.include_stale) qs.set("include_stale", "true");
  if (params?.limit) qs.set("limit", String(params.limit));
  const q = qs.toString();
  return request<GuardResultListResponse>(`/api/runs/${runId}/guard-results${q ? `?${q}` : ""}`);
};
export const getRunGuardResult = (runId: string, guardResultId: string) =>
  request<GuardResultItem>(`/api/runs/${runId}/guard-results/${guardResultId}`);
export const validateGuardResultForProposal = (
  runId: string,
  stepId: string,
  guardResultId: string,
  data: GuardProposalValidationRequest,
) =>
  request<GuardProposalValidationResponse>(
    `/api/runs/${runId}/steps/${stepId}/guard-results/${guardResultId}/validate-for-proposal`,
    { method: "POST", body: JSON.stringify(data) },
  );
export const getStepPatchLifecycle = (runId: string, stepId: string) =>
  request<StepPatchLifecycleResponse>(`/api/runs/${runId}/steps/${stepId}/patch-lifecycle`);
export const getRunStepToolPlan = (id: string) =>
  request<StepToolPlanResponse>(`/api/runs/${id}/steps/tool-plan`);
export const getRunGuidedExecutionPlan = (id: string) =>
  request<GuidedExecutionPlanResponse>(`/api/runs/${id}/guided-execution-plan`);
export const getRunPatchWorkflowPlan = (id: string) =>
  request<PatchWorkflowPlanResponse>(`/api/runs/${id}/patch-workflow-plan`);
export const runStepAutoRead = (runId: string, stepId: string, req: AutoStepReadRequest) =>
  request<AutoStepReadResponse>(`/api/runs/${runId}/steps/${stepId}/auto-read`, {
    method: "POST",
    body: JSON.stringify(req),
  });
export const runStepAutoContext = (runId: string, stepId: string, req: AutoContextGatherRequest) =>
  request<AutoContextGatherResponse>(`/api/runs/${runId}/steps/${stepId}/auto-context`, {
    method: "POST",
    body: JSON.stringify(req),
  });
export const getRunStepContextBundle = (runId: string, stepId: string) =>
  request<StepContextBundleResponse>(`/api/runs/${runId}/steps/${stepId}/context-bundle`);
export const buildContextPatchDraft = (runId: string, stepId: string, req: ContextPatchDraftRequest) =>
  request<ContextPatchDraftResponse>(`/api/runs/${runId}/steps/${stepId}/context-patch-draft`, {
    method: "POST",
    body: JSON.stringify(req),
  });
export const getRunAgents = (id: string) => request<RunAgentAssignment[]>(`/api/runs/${id}/agents`);
export const selectRunAgents = (id: string) =>
  request<AgentSelectionResult>(`/api/runs/${id}/agents/select`, { method: "POST" });
export const updateRunAgent = (runId: string, agentId: string, data: Partial<RunAgentAssignment>) =>
  request<RunAgentAssignment>(`/api/runs/${runId}/agents/${agentId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
export const getRunModelRoutes = (id: string, scope: "agents" | "steps" | "all" = "all") =>
  request<ModelRouteDecision[]>(`/api/runs/${id}/model-routes?scope=${scope}`);
export const previewRunModelRoutes = (id: string) =>
  request<ModelRoutePreviewResponse>(`/api/runs/${id}/model-routes/preview`, { method: "POST" });
export const persistRunModelRoutes = (id: string) =>
  request<ModelRoutePersistResponse>(`/api/runs/${id}/model-routes/persist`, { method: "POST" });
export const previewStepModelRoutes = (id: string) =>
  request<ModelRoutePreviewResponse>(`/api/runs/${id}/steps/model-routes/preview`, { method: "POST" });
export const persistStepModelRoutes = (id: string) =>
  request<ModelRoutePersistResponse>(`/api/runs/${id}/steps/model-routes/persist`, { method: "POST" });
export const getRunArtifact = (id: string, artifactName: string) =>
  request<RunArtifact>(`/api/runs/${id}/artifacts/${encodeURIComponent(artifactName)}`);
export const submitClarifications = (id: string, answers: string) =>
  request<ClarificationAnswerResult>(`/api/runs/${id}/clarifications`, {
    method: "POST",
    body: JSON.stringify({ answers }),
  });
export const regeneratePlan = (id: string) =>
  request<RegeneratePlanResult>(`/api/runs/${id}/regenerate-plan`, { method: "POST" });
export const stopRun = (id: string) =>
  request<any>(`/api/runs/${id}/stop`, { method: "POST" });

// Local tools
export const getWorkspaceStatus = () => request<WorkspaceStatus>("/api/workspace/status");
export const runTests = () =>
  request<TestRunResult>("/api/tools/run-tests", { method: "POST" });
export const getProjectWorkspaceStatus = (projectId: string) =>
  request<WorkspaceStatus>(`/api/projects/${projectId}/workspace/status`);
export const runProjectTests = (projectId: string) =>
  request<ProjectToolResult>(`/api/projects/${projectId}/tools/run-tests`, { method: "POST" });
export const runProjectBuild = (projectId: string) =>
  request<ProjectToolResult>(`/api/projects/${projectId}/tools/run-build`, { method: "POST" });
export const runProjectCommand = (projectId: string, req: RunProjectCommandRequest) =>
  request<RunProjectCommandResponse>(`/api/projects/${projectId}/tools/run-command`, {
    method: "POST",
    body: JSON.stringify(req),
  });
export const analyzeCommandResult = (projectId: string, req: CommandAnalysisRequest) =>
  request<CommandAnalysisResponse>(`/api/projects/${projectId}/tools/analyze-command-result`, {
    method: "POST",
    body: JSON.stringify(req),
  });
export const getRunToolCalls = (runId: string) =>
  request<ToolCall[]>(`/api/runs/${runId}/tool-calls`);
export const getStepToolCalls = (runId: string, stepId: string) =>
  request<ToolCall[]>(`/api/runs/${runId}/steps/${stepId}/tool-calls`);
export const getProjectToolCalls = (projectId: string) =>
  request<ToolCall[]>(`/api/projects/${projectId}/tool-calls`);
export const getProjectGitStatus = (projectId: string) =>
  request<GitStatusResponse>(`/api/projects/${projectId}/git/status`);
export const getProjectGitDiff = (projectId: string) =>
  request<GitDiffResponse>(`/api/projects/${projectId}/git/diff`);
export const proposeProjectPatch = (projectId: string, data: ProposePatchRequest) =>
  request<ProposePatchResponse>(`/api/projects/${projectId}/tools/propose-patch`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const applyProjectPatch = (projectId: string, data: ApplyPatchRequest) =>
  request<ApplyPatchResponse>(`/api/projects/${projectId}/tools/apply-patch`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const rollbackProjectPatch = (projectId: string, data: RollbackPatchRequest) =>
  request<RollbackPatchResponse>(`/api/projects/${projectId}/tools/rollback-patch`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const reviewProjectPatch = (projectId: string, data: PatchReviewRequest) =>
  request<PatchReviewResponse>(`/api/projects/${projectId}/tools/review-patch`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// Failure-to-fix draft
export const createFailureToFixDraft = (runId: string, stepId: string, data: FailureToFixDraftRequest) =>
  request<FailureToFixDraftResponse>(`/api/runs/${runId}/steps/${stepId}/failure-to-fix-draft`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// Semi-auto operator queue
export const getRunOperatorQueue = (runId: string, params?: { step_id?: string; limit?: number }) => {
  const qs = params
    ? "?" + new URLSearchParams(
        Object.entries(params)
          .filter(([, v]) => v !== undefined)
          .map(([k, v]) => [k, String(v)])
      ).toString()
    : "";
  return request<OperatorQueueResponse>(`/api/runs/${runId}/operator-queue${qs}`);
};
export const getRunAgentStepContext = (runId: string) =>
  request<RunAgentStepContextResponse>(`/api/runs/${runId}/agent-step-context`);
export const getRepoAwareControlledLoopPlan = (runId: string, stepId: string) =>
  request<RepoAwareControlledLoopPlanResponse>(`/api/runs/${runId}/steps/${stepId}/repo-aware-controlled-loop-plan`);
export const createStepAgentPatchDraft = (
  runId: string,
  stepId: string,
  data: StepAgentPatchDraftRequest = {},
) =>
  request<StepAgentPatchDraftResponse>(`/api/runs/${runId}/steps/${stepId}/agent-patch-draft`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const createStepPatchDraftGuardedProposal = (
  runId: string,
  stepId: string,
  data: StepPatchDraftGuardedProposalRequest,
) =>
  request<StepPatchDraftGuardedProposalResponse>(`/api/runs/${runId}/steps/${stepId}/patch-draft/guarded-proposal`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const runAutomationNext = (runId: string, data: AutomationRunRequest) =>
  request<AutomationRunResponse>(`/api/runs/${runId}/automation/run-next`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const runAutomationSafeLoop = (runId: string, data: AutomationRunRequest) =>
  request<AutomationRunResponse>(`/api/runs/${runId}/automation/run-safe-loop`, {
    method: "POST",
    body: JSON.stringify(data),
  });

// Automation Approvals
export const createRunAutomationApproval = (runId: string, data: AutomationApprovalCreateRequest) =>
  request<AutomationApprovalItem>(`/api/runs/${runId}/automation/approvals`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const listRunAutomationApprovals = (runId: string, params?: { step_id?: string; status?: string }) => {
  const qs = new URLSearchParams();
  if (params?.step_id) qs.set("step_id", params.step_id);
  if (params?.status) qs.set("status", params.status);
  const q = qs.toString();
  return request<AutomationApprovalListResponse>(`/api/runs/${runId}/automation/approvals${q ? `?${q}` : ""}`);
};
export const getRunAutomationApproval = (runId: string, approvalId: string) =>
  request<AutomationApprovalItem>(`/api/runs/${runId}/automation/approvals/${approvalId}`);
export const approveRunAutomationApproval = (runId: string, approvalId: string, data?: AutomationApprovalApproveRequest) =>
  request<AutomationApprovalItem>(`/api/runs/${runId}/automation/approvals/${approvalId}/approve`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
export const rejectRunAutomationApproval = (runId: string, approvalId: string, data?: AutomationApprovalRejectRequest) =>
  request<AutomationApprovalItem>(`/api/runs/${runId}/automation/approvals/${approvalId}/reject`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });
export const executeRunAutomationApproval = (runId: string, approvalId: string, data?: AutomationApprovalExecuteRequest) =>
  request<AutomationApprovalExecuteResponse>(`/api/runs/${runId}/automation/approvals/${approvalId}/execute`, {
    method: "POST",
    body: JSON.stringify(data ?? {}),
  });

// Agent Execution Harness v1
export const getAgentExecutionContext = (runId: string, stepId: string) =>
  request<import("../types").AgentExecutionContext>(
    `/api/runs/${runId}/steps/${stepId}/agent-execution-context`
  );
export const runAgentExecution = (runId: string, stepId: string, data: import("../types").AgentExecutionRequest) =>
  request<import("../types").AgentExecutionResponse>(
    `/api/runs/${runId}/steps/${stepId}/agent-executions/run`,
    { method: "POST", body: JSON.stringify(data) }
  );
export const executeNextRunStep = (runId: string, data: ExecuteNextStepRequest = {}) =>
  request<ExecuteNextStepResponse>(`/api/runs/${runId}/execute-next-step`, {
    method: "POST",
    body: JSON.stringify(data),
  });
export const listAgentExecutions = (runId: string, stepId: string) =>
  request<import("../types").AgentExecutionListResponse>(
    `/api/runs/${runId}/steps/${stepId}/agent-executions`
  );

// Agent Result → Patch Draft Bridge v1
export const createAgentPatchDraft = (
  runId: string,
  stepId: string,
  data: import("../types").AgentPatchDraftRequest
) =>
  request<import("../types").AgentPatchDraftResponse>(
    `/api/runs/${runId}/steps/${stepId}/agent-result-patch-draft`,
    { method: "POST", body: JSON.stringify(data) }
  );

// Bounded Autonomous Patch-Test-Fix Loop v1
export const runBoundedLoop = (
  runId: string,
  data: import("../types").BoundedAutonomousLoopRequest
) =>
  request<import("../types").BoundedAutonomousLoopResponse>(
    `/api/runs/${runId}/automation/bounded-patch-test-fix-loop`,
    { method: "POST", body: JSON.stringify(data) }
  );

// Delivery Loop
export const getRunDeliverySummary = (runId: string) =>
  request<import("../types").RunDeliverySummary>(`/api/runs/${runId}/delivery-summary`);

export const generateRunDeliveryReport = (
  runId: string,
  data?: import("../types").DeliveryReportRequest
) =>
  request<import("../types").DeliveryReportResponse>(
    `/api/runs/${runId}/delivery-report`,
    { method: "POST", body: JSON.stringify(data ?? {}) }
  );

// Source of Truth v1
export const getProjectSourceOfTruth = (projectId: string) =>
  request<import("../types").SourceOfTruthResponse>(
    `/api/projects/${projectId}/source-of-truth`
  );

export const upsertProjectSourceOfTruth = (
  projectId: string,
  data: import("../types").SourceOfTruthUpsertRequest
) =>
  request<import("../types").SourceOfTruthResponse>(
    `/api/projects/${projectId}/source-of-truth`,
    { method: "PUT", body: JSON.stringify(data) }
  );

export const getProjectSourceOfTruthHistory = (projectId: string, limit?: number) =>
  request<import("../types").SourceOfTruthHistoryResponse>(
    `/api/projects/${projectId}/source-of-truth/history${limit ? `?limit=${limit}` : ""}`
  );

export const getProjectSourceOfTruthVersion = (projectId: string, version: number) =>
  request<import("../types").SourceOfTruthResponse>(
    `/api/projects/${projectId}/source-of-truth/${version}`
  );

export const validateProjectSourceOfTruth = (
  projectId: string,
  data: import("../types").SourceOfTruthUpsertRequest
) =>
  request<import("../types").SourceOfTruthValidationResponse>(
    `/api/projects/${projectId}/source-of-truth/validate`,
    { method: "POST", body: JSON.stringify(data) }
  );

export const getProjectSourceOfTruthSummary = (projectId: string) =>
  request<import("../types").SourceOfTruthSummaryResponse>(
    `/api/projects/${projectId}/source-of-truth/summary`,
    { method: "POST", body: JSON.stringify({}) }
  );

// ── Project Module Map v1 ─────────────────────────────────────────────────────

export const getProjectModuleMap = (projectId: string) =>
  request<import("../types").ProjectModuleMapResponse>(
    `/api/projects/${projectId}/module-map`
  );

export const upsertProjectModuleMap = (
  projectId: string,
  data: import("../types").ProjectModuleMapUpsertRequest
) =>
  request<import("../types").ProjectModuleMapResponse>(
    `/api/projects/${projectId}/module-map`,
    { method: "PUT", body: JSON.stringify(data) }
  );

export const getProjectModuleMapHistory = (projectId: string, limit?: number) =>
  request<import("../types").ProjectModuleMapHistoryResponse>(
    `/api/projects/${projectId}/module-map/history${limit ? `?limit=${limit}` : ""}`
  );

export const getProjectModuleMapVersion = (projectId: string, version: number) =>
  request<import("../types").ProjectModuleMapResponse>(
    `/api/projects/${projectId}/module-map/${version}`
  );

export const validateProjectModuleMap = (
  projectId: string,
  data: import("../types").ProjectModuleMapUpsertRequest
) =>
  request<import("../types").ProjectModuleMapValidationResponse>(
    `/api/projects/${projectId}/module-map/validate`,
    { method: "POST", body: JSON.stringify(data) }
  );

export const getProjectModuleMapSummary = (projectId: string) =>
  request<import("../types").ProjectModuleMapSummaryResponse>(
    `/api/projects/${projectId}/module-map/summary`,
    { method: "POST", body: JSON.stringify({}) }
  );

export const scanProjectModuleMapPreview = (
  projectId: string,
  data?: import("../types").ProjectModuleMapScanPreviewRequest
) =>
  request<import("../types").ProjectModuleMapScanPreviewResponse>(
    `/api/projects/${projectId}/module-map/scan-preview`,
    { method: "POST", body: JSON.stringify(data ?? {}) }
  );

// Approvals
export const getApprovals = () => request<any[]>("/api/approvals");
export const approveRequest = (id: string) =>
  request<ApprovalDecisionResult>(`/api/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({}) });
export const rejectRequest = (id: string) =>
  request<any>(`/api/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({}) });

// Project Context Cockpit v1
export const getRunProjectContextCockpit = (runId: string) =>
  request<import("../types").ProjectContextCockpitSummary>(
    `/api/runs/${runId}/project-context-cockpit`
  );

// Unified Autonomous Project Intake v1
export const previewUnifiedIntake = (data: UnifiedIntakeRequest) =>
  request<UnifiedAutonomousIntakePreviewResponse>("/api/project-intake/unified-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const previewExistingProjectRepoIntake = (data: ExistingProjectRepoIntakeRequest) =>
  request<ExistingProjectRepoIntakeResponse>("/api/project-intake/existing-project/repo-intake-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });

// Clarifying Questions Engine v1
export const getClarifyingQuestions = (data: UnifiedIntakeRequest) =>
  request<ClarifyingQuestionSet>("/api/project-intake/clarifying-questions", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const previewClarifiedIntake = (data: ClarifyingAnswersRequest) =>
  request<ClarifiedIntakePreviewResponse>("/api/project-intake/clarifying-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const buildSoTDraftFromIntake = (data: SourceOfTruthDraftFromIntakeRequest) =>
  request<SourceOfTruthDraftFromIntakeResponse>("/api/project-intake/source-of-truth-draft", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const confirmSoTDraftFromIntake = (data: SourceOfTruthDraftFromIntakeRequest) =>
  request<SourceOfTruthDraftFromIntakeResponse>(
    "/api/project-intake/source-of-truth-draft/confirm",
    { method: "POST", body: JSON.stringify(data) },
  );

export const buildModuleMapDraftFromIntake = (data: ModuleMapDraftFromIntakeRequest) =>
  request<ModuleMapDraftFromIntakeResponse>("/api/project-intake/module-map-draft", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const confirmModuleMapDraftFromIntake = (data: ModuleMapDraftFromIntakeRequest) =>
  request<ModuleMapDraftFromIntakeResponse>(
    "/api/project-intake/module-map-draft/confirm",
    { method: "POST", body: JSON.stringify(data) },
  );

export const buildMultiAgentPlanFromIntake = (data: MultiAgentPlanFromIntakeRequest) =>
  request<MultiAgentPlanFromIntakeResponse>("/api/project-intake/multi-agent-plan", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const previewIntakeDevelopmentRun = (data: IntakeDevelopmentRunPreviewRequest) =>
  request<IntakeDevelopmentRunPreviewResponse>("/api/project-intake/development-run-preview", {
    method: "POST",
    body: JSON.stringify(data),
  });

export const previewConfirmedRunCreationContract = (
  data: IntakeConfirmedRunCreationContractPreviewRequest,
) =>
  request<IntakeConfirmedRunCreationContractPreviewResponse>(
    "/api/project-intake/confirmed-run-creation-contract-preview",
    { method: "POST", body: JSON.stringify(data) },
  );

export const createConfirmedDevelopmentRun = (
  data: ConfirmedDevelopmentRunCreateRequest,
) =>
  request<ConfirmedDevelopmentRunCreateResponse>(
    "/api/project-intake/confirmed-development-run/create",
    { method: "POST", body: JSON.stringify(data) },
  );

// Config
export const getConfig = () => request<any>("/api/config");
export const updateConfig = (data: Record<string, unknown>) =>
  request<any>("/api/config", { method: "POST", body: JSON.stringify(data) });

function normalizeProject(project: Partial<Project>): Project {
  return {
    id: project.id || "",
    name: project.name || "",
    path: project.path || "",
    description: project.description || "",
    stack: project.stack || "",
    package_manager: project.package_manager || "",
    test_command: project.test_command || "",
    build_command: project.build_command || "",
    safe_commands: Array.isArray(project.safe_commands) ? project.safe_commands : [],
    blocked_commands: Array.isArray(project.blocked_commands) ? project.blocked_commands : [],
    ignore_paths: Array.isArray(project.ignore_paths) ? project.ignore_paths : [],
    created_at: project.created_at || "",
    updated_at: project.updated_at || null,
  };
}

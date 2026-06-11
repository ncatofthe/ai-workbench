import { useEffect, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";
import {
  analyzeCommandResult,
  applyProjectPatch,
  rollbackProjectPatch,
  runProjectCommand,
  getAgentRegistry,
  getModelProfiles,
  getModelRegistry,
  getRun,
  getRunAgents,
  getRunArtifact,
  getRunGuidedExecutionPlan,
  getRunModelRoutes,
  getRunSteps,
  getRunStepToolPlan,
  getRunToolCalls,
  getStepToolCalls,
  proposeProjectPatch,
  reviewProjectPatch,
  getRunPatchWorkflowPlan,
  runStepAutoRead,
  runStepAutoContext,
  getRunStepContextBundle,
  getStepPatchLifecycle,
  buildContextPatchDraft,
  checkStepSourceOfTruthGuard,
  listRunGuardResults,
  validateGuardResultForProposal,
  persistRunModelRoutes,
  previewRunModelRoutes,
  regeneratePlan,
  selectRunAgents,
  stopRun,
  submitClarifications,
  createFailureToFixDraft,
  getRunAgentStepContext,
  getRepoAwareControlledLoopPlan,
  createStepAgentPatchDraft,
  createStepPatchDraftGuardedProposal,
  getRunOperatorQueue,
  getRunProjectContextCockpit,
  runAutomationNext,
  runAutomationSafeLoop,
  createRunAutomationApproval,
  listRunAutomationApprovals,
  approveRunAutomationApproval,
  rejectRunAutomationApproval,
  executeRunAutomationApproval,
  getAgentExecutionContext,
  runAgentExecution,
  listAgentExecutions,
  createAgentPatchDraft,
  runBoundedLoop,
  getRunDeliverySummary,
  generateRunDeliveryReport,
  executeNextRunStep,
} from "../api/client";

import StatusBadge from "../components/StatusBadge";
import { NextActionCard, WorkflowActionLauncher, WorkflowModeSelector, WorkflowStageRow, WorkflowStepPicker } from "../components/run-detail/PatchWorkflowPanel";
import {
  WORKFLOW_BOUNDARY_SUMMARY_LINES,
  WORKFLOW_MANUAL_ONLY_ACTION_TYPES,
  getWorkflowActionBoundary,
  type WorkflowAutomationMode,
} from "../components/run-detail/workflowActionPolicy";
import type {
  AgentInfo,
  AutoContextGatherResponse,
  AutoStepReadResponse,
  ContextPatchDraftCandidate,
  ContextPatchDraftResponse,
  StepContextBundle,
  StepContextFile,
  CommandAnalysisResponse,
  GuidedExecutionPlanResponse,
  GuidedStepExecutionPlan,
  GuidedStepAction,
  ModelProfile,
  ModelRegistryItem,
  ModelRouteDecision,
  ApplyPatchResponse,
  ProposePatchResponse,
  RollbackPatchResponse,
  PatchReviewResponse,
  PatchReviewIssue,
  PatchWorkflowPlanResponse,
  StepPatchWorkflowPlan,
  PatchWorkflowNextAction,
  Run,
  RunAgentAssignment,
  RunProjectCommandResponse,
  RunStep,
  StepSourceOfTruthGuardResponse,
  StepToolPlanResponse,
  ToolCall,
  GuardResultItem,
  GuardProposalValidationResponse,
  StepPatchLifecycleResponse,
  FailureToFixDraftResponse,
  AutomationRunResponse,
  OperatorQueueResponse,
  OperatorQueueItem,
  RunAgentStepContextResponse,
  RepoAwareControlledLoopPlanResponse,
  StepAgentPatchDraftResponse,
  StepPatchDraftGuardedProposalResponse,
  AutomationApprovalItem,
  AutomationApprovalListResponse,
  AutomationApprovalExecuteResponse,
  AgentExecutionContext,
  AgentExecutionResponse,
  AgentExecutionListResponse,
  AgentExecutionRequest,
  AgentPatchDraftResponse,
} from "../types";

type IssuePrefill = {
  file_path: string;
  context_kind: string;
  context_location: string;
  context_message: string;
};

type GuardCheckedContext = {
  proposedAction: string;
  filePath: string;
  oldText: string;
  newText: string;
};

type PatchFormState = {
  file_path: string;
  old_text: string;
  new_text: string;
  create_if_missing: boolean;
  replace_all: boolean;
};

type ManualFocusResult = {
  message: string;
  error?: string;
};

type ToolCallFocus = {
  nonce: number;
  stepId?: string;
  toolName?: string;
  status?: string;
  toolCallId?: string;
  visibleLimit?: number;
  message?: string;
};

const emptyPatchForm: PatchFormState = {
  file_path: "",
  old_text: "",
  new_text: "",
  create_if_missing: false,
  replace_all: false,
};

function workflowUiStorageKey(runId: string): string {
  return `ai-workbench:run:${runId}:workflow-ui`;
}

function isWorkflowAutomationMode(value: unknown): value is WorkflowAutomationMode {
  return value === "manual" || value === "guided" || value === "safe_prep";
}

function loadWorkflowUiState(runId: string): {
  workflowAutomationMode: WorkflowAutomationMode;
  activeWorkflowStepId: string | null;
} {
  try {
    const raw = window.localStorage.getItem(workflowUiStorageKey(runId));
    if (!raw) return { workflowAutomationMode: "guided", activeWorkflowStepId: null };
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    return {
      workflowAutomationMode: isWorkflowAutomationMode(parsed.workflowAutomationMode)
        ? parsed.workflowAutomationMode
        : "guided",
      activeWorkflowStepId:
        typeof parsed.activeWorkflowStepId === "string" && parsed.activeWorkflowStepId.trim()
          ? parsed.activeWorkflowStepId
          : null,
    };
  } catch {
    return { workflowAutomationMode: "guided", activeWorkflowStepId: null };
  }
}

function saveWorkflowUiState(
  runId: string,
  state: { workflowAutomationMode: WorkflowAutomationMode; activeWorkflowStepId: string | null },
) {
  try {
    window.localStorage.setItem(workflowUiStorageKey(runId), JSON.stringify(state));
  } catch {
    // localStorage can be unavailable in privacy modes; ignore and keep page state.
  }
}

export default function RunDetail() {
  const { id } = useParams<{ id: string }>();
  const [run, setRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<RunStep[]>([]);
  const [team, setTeam] = useState<RunAgentAssignment[]>([]);
  const [agentRegistry, setAgentRegistry] = useState<AgentInfo[]>([]);
  const [modelProfiles, setModelProfiles] = useState<ModelProfile[]>([]);
  const [modelRegistry, setModelRegistry] = useState<ModelRegistryItem[]>([]);
  const [modelRoutes, setModelRoutes] = useState<ModelRouteDecision[]>([]);
  const [modelRoutesPersisted, setModelRoutesPersisted] = useState(true);
  const [stepRoutes, setStepRoutes] = useState<Record<string, ModelRouteDecision>>({});
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [toolCallsError, setToolCallsError] = useState("");
  const [runNotFound, setRunNotFound] = useState(false);
  const [artifactContent, setArtifactContent] = useState<Record<string, string>>({});
  const [answers, setAnswers] = useState("");
  const [notice, setNotice] = useState("");
  const [savingAnswers, setSavingAnswers] = useState(false);
  const [regeneratingPlan, setRegeneratingPlan] = useState(false);
  const [executingNextStep, setExecutingNextStep] = useState(false);
  const [nextStepMode, setNextStepMode] = useState<"dry_run" | "mock" | "provider">("mock");
  const [selectingTeam, setSelectingTeam] = useState(false);
  const [routingModels, setRoutingModels] = useState(false);
  const [toolPlan, setToolPlan] = useState<StepToolPlanResponse | null>(null);
  const [toolPlanLoading, setToolPlanLoading] = useState(false);
  const [toolPlanError, setToolPlanError] = useState("");
  const [guidedPlan, setGuidedPlan] = useState<GuidedExecutionPlanResponse | null>(null);
  const [guidedPlanLoading, setGuidedPlanLoading] = useState(false);
  const [guidedPlanError, setGuidedPlanError] = useState("");
  const [contextBundles, setContextBundles] = useState<Record<string, StepContextBundle>>({});
  const [bundleLoading, setBundleLoading] = useState<Record<string, boolean>>({});
  const [draftPrefills, setDraftPrefills] = useState<Record<string, PatchFormState | null>>({});
  const [agentPrefills, setAgentPrefills] = useState<Record<string, IssuePrefill | null>>({});
  const [toolCallFocus, setToolCallFocus] = useState<ToolCallFocus | null>(null);
  const [workflowPlan, setWorkflowPlan] = useState<PatchWorkflowPlanResponse | null>(null);
  const [workflowPlanLoading, setWorkflowPlanLoading] = useState(false);
  const [workflowPlanError, setWorkflowPlanError] = useState("");
  const [activeWorkflowStepId, setActiveWorkflowStepId] = useState<string | null>(null);
  const [workflowAutomationMode, setWorkflowAutomationMode] = useState<WorkflowAutomationMode>("guided");
  const [workflowUiLoadedForRun, setWorkflowUiLoadedForRun] = useState<string | null>(null);
  const [tab, setTab] = useState<
    "timeline" | "team" | "spec" | "questions" | "plan" | "architecture" | "tasks" | "logs" | "result" | "tool-plan" | "guided" | "patch-workflow" | "operator-queue" | "agent-context" | "delivery" | "cockpit"
  >("timeline");
  const [operatorQueue, setOperatorQueue] = useState<OperatorQueueResponse | null>(null);
  const [operatorQueueLoading, setOperatorQueueLoading] = useState(false);
  const [operatorQueueError, setOperatorQueueError] = useState("");
  const [agentStepContext, setAgentStepContext] = useState<RunAgentStepContextResponse | null>(null);
  const [agentStepContextLoading, setAgentStepContextLoading] = useState(false);
  const [agentStepContextError, setAgentStepContextError] = useState("");
  const [cockpitData, setCockpitData] = useState<import("../types").ProjectContextCockpitSummary | null>(null);
  const [cockpitLoading, setCockpitLoading] = useState(false);
  const [cockpitError, setCockpitError] = useState("");

  const refreshToolCalls = async () => {
    if (!id) return;
    const nextToolCalls = await getRunToolCalls(id).catch((e: any) => {
      setToolCallsError(readableError(e));
      return null;
    });
    if (nextToolCalls) {
      setToolCalls(nextToolCalls);
      setToolCallsError("");
    }
  };

  const loadToolPlan = async () => {
    if (!id) return;
    setToolPlanLoading(true);
    setToolPlanError("");
    try {
      const plan = await getRunStepToolPlan(id);
      setToolPlan(plan);
    } catch (e: any) {
      setToolPlanError(readableError(e));
    } finally {
      setToolPlanLoading(false);
    }
  };

  const loadGuidedPlan = async () => {
    if (!id) return;
    setGuidedPlanLoading(true);
    setGuidedPlanError("");
    try {
      const plan = await getRunGuidedExecutionPlan(id);
      setGuidedPlan(plan);
    } catch (e: any) {
      setGuidedPlanError(readableError(e));
    } finally {
      setGuidedPlanLoading(false);
    }
  };

  const loadContextBundle = async (stepId: string) => {
    if (!id) return;
    setBundleLoading((prev) => ({ ...prev, [stepId]: true }));
    try {
      const res = await getRunStepContextBundle(id, stepId);
      setContextBundles((prev) => ({ ...prev, [stepId]: res.bundle }));
    } catch {
      // silently ignore — empty bundle shown
    } finally {
      setBundleLoading((prev) => ({ ...prev, [stepId]: false }));
    }
  };

  const loadWorkflowPlan = async () => {
    if (!id) return;
    setWorkflowPlanLoading(true);
    setWorkflowPlanError("");
    try {
      const plan = await getRunPatchWorkflowPlan(id);
      setWorkflowPlan(plan);
    } catch (e: any) {
      setWorkflowPlanError(readableError(e));
    } finally {
      setWorkflowPlanLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    setWorkflowUiLoadedForRun(null);
    const saved = loadWorkflowUiState(id);
    setWorkflowAutomationMode(saved.workflowAutomationMode);
    setActiveWorkflowStepId(saved.activeWorkflowStepId);
    setWorkflowUiLoadedForRun(id);
  }, [id]);

  useEffect(() => {
    if (!id || workflowUiLoadedForRun !== id) return;
    saveWorkflowUiState(id, { workflowAutomationMode, activeWorkflowStepId });
  }, [id, workflowUiLoadedForRun, workflowAutomationMode, activeWorkflowStepId]);

  useEffect(() => {
    if (!workflowPlan || !activeWorkflowStepId) return;
    const exists = workflowPlan.steps.some((step) => step.step_id === activeWorkflowStepId);
    if (!exists) {
      setActiveWorkflowStepId(null);
      setNotice("Saved active workflow step no longer exists. Cockpit returned to auto mode.");
    }
  }, [workflowPlan, activeWorkflowStepId]);

  const focusManualAction = async (stepId: string, actionType: string): Promise<ManualFocusResult> => {
    const latestFailedCommand = [...toolCalls]
      .filter((call) => call.step_id === stepId && isFailedRunCommandCall(call))
      .sort((a, b) => toolCallTime(b).localeCompare(toolCallTime(a)))[0];
    const latestRollbackCall = [...toolCalls]
      .filter((call) => call.step_id === stepId && isRollbackCapableApplyPatchCall(call))
      .sort((a, b) => toolCallTime(b).localeCompare(toolCallTime(a)))[0];

    const target: {
      tab: "timeline" | "agent-context";
      anchor: string;
      message: string;
      toolCallId?: string;
      toolName?: string;
      status?: string;
      visibleLimit?: number;
    } =
      actionType === "prepare_agent_step"
        ? {
            tab: "agent-context" as const,
            anchor: "agent-step-context",
            message: "Review Agent Step Context before opening any manual agent dry-run. No provider call or execution was started.",
          }
      : actionType === "run_tests_manual" || actionType === "run_tests" || actionType === "run_command"
        ? {
            tab: "timeline" as const,
            anchor: "guided-fix",
            message: "Run tests manually from the Guided Fix Workflow. No command was started by this launcher.",
          }
      : actionType === "analyze_result"
        ? latestFailedCommand
          ? {
              tab: "timeline" as const,
              anchor: "tool-call",
              toolCallId: latestFailedCommand.id,
              toolName: "run-command",
              status: "needs_attention",
              visibleLimit: 50,
              message: "Open this failed run-command and click Analyze manually. No analysis was started by this launcher.",
            }
          : {
            tab: "timeline" as const,
            anchor: "tool-calls",
            toolName: "run-command",
            status: "needs_attention",
            visibleLimit: 50,
            message: "No failed run-command found in loaded Tool Calls. Load more or run tests first.",
          }
      : actionType === "rollback_manual" || actionType === "rollback_patch"
        ? latestRollbackCall
          ? {
              tab: "timeline" as const,
              anchor: "tool-call",
              toolCallId: latestRollbackCall.id,
              toolName: "apply-patch",
              visibleLimit: 50,
              message: "Use rollback controls on this apply-patch call. Rollback requires manual confirm=true.",
            }
          : {
            tab: "timeline" as const,
            anchor: "tool-calls",
            toolName: "apply-patch",
            visibleLimit: 50,
            message: "No rollback-capable apply-patch call found for this step.",
          }
      : actionType === "review_patch"
        ? {
            tab: "timeline" as const,
            anchor: "step-patch",
            message: "Review Patch needs file_path, old_text, and new_text. Create Patch Draft from Context first or fill the form manually, then click Review Patch.",
          }
      : actionType === "apply_patch_manual" || actionType === "apply_patch"
        ? {
            tab: "timeline" as const,
            anchor: "step-patch",
            message: "Apply requires the manual confirmation checkbox and confirm=true. No patch was applied.",
          }
      : {
          tab: "timeline" as const,
          anchor: "step-patch",
          message: "Review or edit the patch fields, then create the proposal manually. No proposal was created.",
        };

    setTab(target.tab);
    if (target.anchor === "tool-call" || target.anchor === "tool-calls") {
      setToolCallFocus({
        nonce: Date.now(),
        stepId,
        toolName: target.toolName,
        status: target.status,
        toolCallId: target.toolCallId,
        visibleLimit: target.visibleLimit ?? 50,
        message: target.message,
      });
    }
    await new Promise((resolve) => window.setTimeout(resolve, 80));
    window.dispatchEvent(
      new CustomEvent("aiw-focus-manual-action", {
        detail: { stepId, actionType, anchor: target.anchor },
      })
    );
    await new Promise((resolve) => window.setTimeout(resolve, 120));
    window.dispatchEvent(
      new CustomEvent("aiw-focus-manual-action", {
        detail: { stepId, actionType, anchor: target.anchor },
      })
    );
    await new Promise((resolve) => window.setTimeout(resolve, 120));

    const selector =
      target.anchor === "tool-call" && "toolCallId" in target
        ? `[data-tool-call-id="${target.toolCallId}"][data-action-anchor="tool-call"]`
      : target.anchor === "tool-calls"
        ? `[data-action-anchor="tool-calls"]`
        : `[data-step-id="${stepId}"][data-action-anchor="${target.anchor}"]`;
    let element = document.querySelector(selector) as HTMLElement | null;
    let focusError = "";
    if (!element && target.anchor === "tool-call") {
      element = document.querySelector(`[data-action-anchor="tool-calls"]`) as HTMLElement | null;
      focusError = "The exact tool call is not visible in the latest Tool Calls list. Use Tool Calls to find it manually.";
    }
    if (!element) {
      return {
        message: target.message,
        error:
          target.anchor === "step-patch" || target.anchor === "guided-fix"
            ? "This step has no patch/test UI anchor. Choose a child implementation step or use Tool Calls."
            : "Target UI section was not found. Open Tool Calls and continue manually.",
      };
    }

    element.scrollIntoView({ behavior: "smooth", block: "center" });
    element.animate(
      [
        { boxShadow: "0 0 0 0 rgba(16,185,129,0)", borderColor: "rgb(31,41,55)" },
        { boxShadow: "0 0 0 4px rgba(16,185,129,0.45)", borderColor: "rgb(16,185,129)" },
        { boxShadow: "0 0 0 0 rgba(16,185,129,0)", borderColor: "rgb(31,41,55)" },
      ],
      { duration: 2600, easing: "ease-out" }
    );

    return { message: target.message, error: focusError || undefined };
  };

  const loadOperatorQueue = async () => {
    if (!id) return;
    setOperatorQueueLoading(true);
    setOperatorQueueError("");
    try {
      const queue = await getRunOperatorQueue(id);
      setOperatorQueue(queue);
    } catch (e: any) {
      setOperatorQueueError(readableError(e));
    } finally {
      setOperatorQueueLoading(false);
    }
  };

  const loadAgentStepContext = async () => {
    if (!id) return;
    setAgentStepContextLoading(true);
    setAgentStepContextError("");
    try {
      const context = await getRunAgentStepContext(id);
      setAgentStepContext(context);
    } catch (e: any) {
      setAgentStepContextError(readableError(e));
    } finally {
      setAgentStepContextLoading(false);
    }
  };

  const loadCockpit = async () => {
    if (!id) return;
    setCockpitLoading(true);
    setCockpitError("");
    try {
      const data = await getRunProjectContextCockpit(id);
      setCockpitData(data);
    } catch (e: any) {
      setCockpitError(readableError(e));
    } finally {
      setCockpitLoading(false);
    }
  };

  useEffect(() => {
    if (!id) return;
    setRunNotFound(false);
    setRun(null);
    Promise.all([getAgentRegistry(), getModelProfiles(), getModelRegistry()])
      .then(([agents, profiles, models]) => {
        setAgentRegistry(agents);
        setModelProfiles(profiles);
        setModelRegistry(models);
      })
      .catch(() => {});
    getRunModelRoutes(id)
      .then((routes) => {
        setModelRoutes(routes);
        setModelRoutesPersisted(true);
      })
      .catch(() => {});
    getRunModelRoutes(id, "steps")
      .then((routes) => {
        const byStep = Object.fromEntries(routes.filter((r) => r.step_id).map((r) => [r.step_id!, r]));
        setStepRoutes(byStep);
      })
      .catch(() => {});
    getRunAgentStepContext(id)
      .then(setAgentStepContext)
      .catch(() => {});

    let lastArtifactCount = -1;
    let runFinished = false;
    let stopPolling = false;
    const load = async () => {
      if (stopPolling) return;
      try {
        const [nextRun, nextSteps, nextTeam] = await Promise.all([getRun(id), getRunSteps(id), getRunAgents(id)]);
        setRunNotFound(false);
        setRun(nextRun);
        setSteps(nextSteps);
        setTeam(nextTeam);
        await refreshToolCalls();
        // Only reload artifacts when the list changes or run just finished
        const isFinished = nextRun.status === "completed" || nextRun.status === "failed" || nextRun.status === "stopped";
        const artifactCountChanged = nextRun.artifacts.length !== lastArtifactCount;
        const justFinished = isFinished && !runFinished;
        if (artifactCountChanged || justFinished) {
          lastArtifactCount = nextRun.artifacts.length;
          setArtifactContent(await loadRunArtifacts(id, nextRun.artifacts));
        }
        if (justFinished) {
          // Refresh step routes once the run finishes — the execution pipeline
          // persists them during _persist_step_route_decisions.
          const sRoutes = await getRunModelRoutes(id, "steps").catch(() => []);
          setStepRoutes(Object.fromEntries(sRoutes.filter((r) => r.step_id).map((r) => [r.step_id!, r])));
        }
        runFinished = isFinished;
      } catch (e: any) {
        if (isNotFoundError(e)) {
          stopPolling = true;
          setRunNotFound(true);
          setRun(null);
          setSteps([]);
          setTeam([]);
          setToolCalls([]);
          setArtifactContent({});
          return;
        }
        // Polling is best-effort for transient errors; the next interval can recover.
      }
    };
    load();
    const interval = setInterval(load, 2000);
    return () => clearInterval(interval);
  }, [id]);

  if (runNotFound) return <RunNotFound runId={id || ""} />;
  if (!run) return <p className="text-gray-500">Loading...</p>;

  const pendingStepCount = steps.filter((step) => step.status === "pending").length;

  const handleStop = async () => {
    if (id) {
      await stopRun(id);
      const [nextRun, nextSteps, nextTeam] = await Promise.all([getRun(id), getRunSteps(id), getRunAgents(id)]);
      setRun(nextRun);
      setSteps(nextSteps);
      setTeam(nextTeam);
      await refreshToolCalls();
      const routes = await getRunModelRoutes(id).catch(() => []);
      setModelRoutes(routes);
      setModelRoutesPersisted(true);
      const sRoutes = await getRunModelRoutes(id, "steps").catch(() => []);
      setStepRoutes(Object.fromEntries(sRoutes.filter((r) => r.step_id).map((r) => [r.step_id!, r])));
      setArtifactContent(await loadRunArtifacts(id, nextRun.artifacts));
    }
  };

  const handleSubmitAnswers = async () => {
    if (!id || !answers.trim()) return;
    setSavingAnswers(true);
    setNotice("");
    try {
      const result = await submitClarifications(id, answers);
      setArtifactContent((current) => ({ ...current, [result.artifact]: result.content }));
      const [nextRun, nextSteps, nextTeam] = await Promise.all([getRun(id), getRunSteps(id), getRunAgents(id)]);
      setRun(nextRun);
      setSteps(nextSteps);
      setTeam(nextTeam);
      setNotice("Clarification answers saved.");
      setAnswers("");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setSavingAnswers(false);
    }
  };

  const handleRegeneratePlan = async () => {
    if (!id) return;
    setRegeneratingPlan(true);
    setNotice("");
    try {
      const result = await regeneratePlan(id);
      const [nextRun, nextSteps, nextTeam] = await Promise.all([getRun(id), getRunSteps(id), getRunAgents(id)]);
      setRun(nextRun);
      setSteps(nextSteps);
      setTeam(nextTeam);
      setArtifactContent(await loadRunArtifacts(id, nextRun.artifacts));
      setNotice(result.source);
      setTab("plan");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setRegeneratingPlan(false);
    }
  };

  const handleExecuteNextStep = async () => {
    if (!id) return;
    setExecutingNextStep(true);
    setNotice("");
    try {
      const result = await executeNextRunStep(id, {
        mode: nextStepMode,
        allow_provider_call: nextStepMode === "provider",
        persist_result: true,
      });
      const [nextRun, nextSteps, nextTeam] = await Promise.all([getRun(id), getRunSteps(id), getRunAgents(id)]);
      setRun(nextRun);
      setSteps(nextSteps);
      setTeam(nextTeam);
      await refreshToolCalls();
      setArtifactContent(await loadRunArtifacts(id, nextRun.artifacts));
      setNotice(`${result.message} Mode: ${nextStepMode}. Artifact: ${result.artifact}`);
      setTab("timeline");
    } catch (e: any) {
      setNotice(readableError(e));
    } finally {
      setExecutingNextStep(false);
    }
  };

  const handleSelectTeam = async () => {
    if (!id) return;
    setSelectingTeam(true);
    setNotice("");
    try {
      const result = await selectRunAgents(id);
      setTeam(result.selected_agents);
      setModelRoutes([]);
      setModelRoutesPersisted(true);
      setNotice(
        `Selected ${result.team_size} agents. Recommended mode: ${result.recommended_execution_mode}.`,
      );
      setTab("team");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setSelectingTeam(false);
    }
  };

  const handlePreviewModelRoutes = async () => {
    if (!id) return;
    setRoutingModels(true);
    setNotice("");
    try {
      const result = await previewRunModelRoutes(id);
      setModelRoutes(result.decisions);
      setModelRoutesPersisted(false);
      setNotice(
        result.warnings.length > 0
          ? `Previewed ${result.count} model routes. ${result.warnings[0]}`
          : `Previewed ${result.count} model routes.`,
      );
      setTab("team");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setRoutingModels(false);
    }
  };

  const handlePersistModelRoutes = async () => {
    if (!id) return;
    setRoutingModels(true);
    setNotice("");
    try {
      const result = await persistRunModelRoutes(id);
      setModelRoutes(result.decisions);
      setModelRoutesPersisted(true);
      setNotice(
        result.warnings.length > 0
          ? `Persisted ${result.count} model routes. ${result.warnings[0]}`
          : `Persisted ${result.count} model routes.`,
      );
      setTab("team");
    } catch (e: any) {
      setNotice(e.message);
    } finally {
      setRoutingModels(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Run: {run.id}</h2>
        <div className="flex items-center gap-3">
          <StatusBadge status={run.status} />
          <select
            value={nextStepMode}
            onChange={(event) => setNextStepMode(event.target.value as "dry_run" | "mock" | "provider")}
            disabled={executingNextStep}
            className="rounded border border-gray-700 bg-gray-950 px-2 py-1 text-xs text-gray-200 disabled:bg-gray-800 disabled:text-gray-500"
            title="Controls how the next pending step is executed by the agent harness."
          >
            <option value="mock">Mock</option>
            <option value="dry_run">Dry run</option>
            <option value="provider">Local provider</option>
          </select>
          <button
            onClick={handleExecuteNextStep}
            disabled={executingNextStep || pendingStepCount === 0 || Boolean(run.current_step_id)}
            className="px-3 py-1 bg-emerald-700 hover:bg-emerald-600 rounded text-sm disabled:bg-gray-700 disabled:text-gray-500"
          >
            {executingNextStep ? "Running..." : `Run next step${pendingStepCount ? ` (${pendingStepCount})` : ""}`}
          </button>
          {(run.status === "running" || run.status === "pending") && (
            <button
              onClick={handleStop}
              className="px-3 py-1 bg-red-800 hover:bg-red-700 rounded text-sm"
            >
              Stop
            </button>
          )}
        </div>
      </div>

      <div className="bg-gray-900 rounded border border-gray-800 p-4">
        <p className="text-sm text-gray-300">{run.prompt}</p>
        <div className="flex gap-4 mt-2 text-xs text-gray-500">
          <span>Mode: {run.mode}</span>
          <span>Agent: {run.agent_id}</span>
          {run.project_id && (
            <Link to="/projects" className="text-emerald-400 hover:text-emerald-300">
              Project: {run.project_id}
            </Link>
          )}
          {run.current_step_id && <span>Current step: {run.current_step_id}</span>}
          <span>Created: {run.created_at}</span>
          {run.finished_at && <span>Finished: {run.finished_at}</span>}
        </div>
      </div>

      {notice && (
        <div className="rounded border border-blue-800/60 bg-blue-950/30 p-3 text-sm text-blue-100">
          {notice}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-800">
        {(["timeline", "team", "spec", "questions", "plan", "architecture", "tasks", "logs", "result", "tool-plan", "guided", "patch-workflow", "operator-queue", "agent-context", "delivery", "cockpit"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 text-sm border-b-2 transition-colors ${
              tab === t
                ? "border-emerald-500 text-emerald-300"
                : "border-transparent text-gray-500 hover:text-gray-300"
            }`}
          >
            {({
              "timeline": "Timeline",
              "team": "Team",
              "spec": "Spec",
              "questions": "Questions",
              "plan": "Plan",
              "architecture": "Architecture",
              "tasks": "Tasks",
              "logs": "Logs",
              "result": "Result",
              "tool-plan": "Tool Plan",
              "guided": "Guided",
              "patch-workflow": "Patch Workflow",
              "operator-queue": "Operator Cockpit",
              "agent-context": "Agent Context",
              "delivery": "Delivery Report",
              "cockpit": "Context Cockpit",
            } as Record<string, string>)[t] ?? (t.charAt(0).toUpperCase() + t.slice(1))}
          </button>
        ))}
      </div>

      <div className="bg-gray-900 rounded border border-gray-800 p-4 min-h-[200px]">
        {tab === "timeline" && (
          <Timeline
            run={run}
            steps={steps}
            stepRoutes={stepRoutes}
            toolCalls={toolCalls}
            onToolCallsChanged={refreshToolCalls}
            draftPrefills={draftPrefills}
            onDraftPrefillConsumed={(stepId) =>
              setDraftPrefills((prev) => ({ ...prev, [stepId]: null }))
            }
            agentPrefills={agentPrefills}
            onAgentPrefillConsumed={(stepId) =>
              setAgentPrefills((prev) => ({ ...prev, [stepId]: null }))
            }
          />
        )}
        {tab === "team" && (
          <AssignedTeam
            team={team}
            agentRegistry={agentRegistry}
            modelProfiles={modelProfiles}
            modelRegistry={modelRegistry}
            modelRoutes={modelRoutes}
            modelRoutesPersisted={modelRoutesPersisted}
            selecting={selectingTeam}
            routingModels={routingModels}
            onSelectTeam={handleSelectTeam}
            onPreviewModelRoutes={handlePreviewModelRoutes}
            onPersistModelRoutes={handlePersistModelRoutes}
          />
        )}
        {tab === "spec" && (
          <ArtifactViewer
            title="Product Spec"
            content={artifactContent["product-spec.md"]}
            empty="No product spec generated yet..."
          />
        )}
        {tab === "questions" && (
          <ClarificationPanel
            questions={artifactContent["clarification-questions.md"]}
            savedAnswers={artifactContent["clarification-answers.md"]}
            answers={answers}
            saving={savingAnswers}
            regeneratingPlan={regeneratingPlan}
            onAnswersChange={setAnswers}
            onSubmit={handleSubmitAnswers}
            onRegeneratePlan={handleRegeneratePlan}
          />
        )}
        {tab === "plan" && (
          <pre className="text-sm text-gray-300 whitespace-pre-wrap">
            {run.plan || "No plan generated yet..."}
          </pre>
        )}
        {tab === "architecture" && (
          <ArtifactViewer
            title="Architecture"
            content={artifactContent["architecture.md"]}
            empty="No architecture artifact generated yet..."
          />
        )}
        {tab === "tasks" && (
          <ArtifactViewer
            title="Tasks"
            content={artifactContent["tasks.md"]}
            empty="No task breakdown generated yet..."
          />
        )}
        {tab === "logs" && (
          <div className="space-y-1 font-mono text-xs">
            {run.logs.length === 0 ? (
              <p className="text-gray-500">No logs yet...</p>
            ) : (
              run.logs.map((l, i) => (
                <p key={i} className="text-gray-400">{l}</p>
              ))
            )}
          </div>
        )}
        {tab === "result" && (
          <pre className="text-sm text-gray-300 whitespace-pre-wrap">
            {run.result || "No result yet..."}
          </pre>
        )}
        {tab === "tool-plan" && (
          <ToolPlanPanel
            plan={toolPlan}
            loading={toolPlanLoading}
            error={toolPlanError}
            onRefresh={loadToolPlan}
          />
        )}
        {tab === "guided" && (
          <GuidedExecutionPanel
            plan={guidedPlan}
            loading={guidedPlanLoading}
            error={guidedPlanError}
            steps={steps}
            runId={run.id}
            onRefresh={loadGuidedPlan}
            onAutoReadDone={async () => {
              await refreshToolCalls();
              await loadGuidedPlan();
            }}
            contextBundles={contextBundles}
            bundleLoading={bundleLoading}
            onLoadBundle={loadContextBundle}
            onUseDraft={(stepId, candidate) =>
              setDraftPrefills((prev) => ({
                ...prev,
                [stepId]: {
                  file_path: candidate.file_path,
                  old_text: candidate.old_text,
                  new_text: candidate.new_text === "TODO: replace with intended change"
                    ? ""
                    : candidate.new_text,
                  create_if_missing: false,
                  replace_all: false,
                },
              }))
            }
          />
        )}
        {tab === "patch-workflow" && (
          <PatchWorkflowPanel
            runId={run.id}
            steps={steps}
            plan={workflowPlan}
            activeStepId={activeWorkflowStepId}
            loading={workflowPlanLoading}
            error={workflowPlanError}
            workflowMode={workflowAutomationMode}
            onWorkflowModeChange={setWorkflowAutomationMode}
            onRefresh={loadWorkflowPlan}
            onActiveStepChange={setActiveWorkflowStepId}
            onGuidedRefresh={loadGuidedPlan}
            onToolCallsRefresh={refreshToolCalls}
            onFocusManualAction={focusManualAction}
            onUseDraft={(stepId, candidate) =>
              setDraftPrefills((prev) => ({
                ...prev,
                [stepId]: {
                  file_path: candidate.file_path,
                  old_text: candidate.old_text,
                  new_text: candidate.new_text === "TODO: replace with intended change"
                    ? ""
                    : candidate.new_text,
                  create_if_missing: false,
                  replace_all: false,
                },
              }))
            }
          />
        )}
        {tab === "operator-queue" && (
          <OperatorQueuePanel
            runId={run.id}
            queue={operatorQueue}
            loading={operatorQueueLoading}
            error={operatorQueueError}
            onRefresh={loadOperatorQueue}
            onFocusManualAction={focusManualAction}
            steps={steps}
            onAgentPrefill={(stepId, prefill) =>
              setAgentPrefills((prev) => ({ ...prev, [stepId]: prefill }))
            }
          />
        )}
        {tab === "agent-context" && (
          <AgentStepContextPanel
            runId={run.id}
            context={agentStepContext}
            loading={agentStepContextLoading}
            error={agentStepContextError}
            onRefresh={loadAgentStepContext}
            onUsePatchDraft={(stepId, draft) =>
              setAgentPrefills((prev) => ({
                ...prev,
                [stepId]: {
                  file_path: draft.suggested_file_path || "",
                  context_kind: "step-agent-patch-draft",
                  context_location: draft.step_id,
                  context_message: [
                    "Draft only. Review manually before proposal. No patch was applied. No test was run.",
                    `Agent: ${draft.canonical_agent_id}`,
                    `Intent: ${draft.patch_intent}`,
                    `Summary: ${draft.draft_summary}`,
                    `Next: ${draft.next_recommended_action}`,
                  ].join("\n"),
                },
              }))
            }
          />
        )}
        {tab === "delivery" && (
          <DeliveryPanel runId={run.id} />
        )}
        {tab === "cockpit" && (
          <ProjectCockpitPanel
            runId={run.id}
            cockpitData={cockpitData}
            cockpitLoading={cockpitLoading}
            cockpitError={cockpitError}
            onLoad={loadCockpit}
          />
        )}
      </div>

      <ToolCallsPanel calls={toolCalls} error={toolCallsError} focus={toolCallFocus} />

      {run.artifacts.length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-gray-400 mb-2">Artifacts</h3>
          <div className="flex flex-wrap gap-2">
            {run.artifacts.map((a, i) => (
              <span key={i} className="px-2 py-1 bg-gray-800 rounded text-xs text-gray-300">
                {a}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Agent Step Context Panel ─────────────────────────────────────────────────

function AgentStepContextPanel({
  runId,
  context,
  loading,
  error,
  onRefresh,
  onUsePatchDraft,
}: {
  runId: string;
  context: RunAgentStepContextResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onUsePatchDraft?: (stepId: string, draft: StepAgentPatchDraftResponse) => void;
}) {
  const [drafts, setDrafts] = useState<Record<string, StepAgentPatchDraftResponse | null>>({});
  const [draftLoading, setDraftLoading] = useState<Record<string, boolean>>({});
  const [draftErrors, setDraftErrors] = useState<Record<string, string>>({});
  const [operatorNotes, setOperatorNotes] = useState<Record<string, string>>({});
  const [proposalFields, setProposalFields] = useState<Record<string, { file_path: string; old_text: string; new_text: string; confirmed: boolean }>>({});
  const [proposalResponses, setProposalResponses] = useState<Record<string, StepPatchDraftGuardedProposalResponse | null>>({});
  const [proposalLoading, setProposalLoading] = useState<Record<string, boolean>>({});
  const [proposalErrors, setProposalErrors] = useState<Record<string, string>>({});
  const [loopPlans, setLoopPlans] = useState<Record<string, RepoAwareControlledLoopPlanResponse | null>>({});
  const [loopPlanLoading, setLoopPlanLoading] = useState<Record<string, boolean>>({});
  const [loopPlanErrors, setLoopPlanErrors] = useState<Record<string, string>>({});

  const refreshControlledLoopPlan = async (stepId: string) => {
    setLoopPlanLoading((prev) => ({ ...prev, [stepId]: true }));
    setLoopPlanErrors((prev) => ({ ...prev, [stepId]: "" }));
    try {
      const plan = await getRepoAwareControlledLoopPlan(runId, stepId);
      setLoopPlans((prev) => ({ ...prev, [stepId]: plan }));
    } catch (e: any) {
      setLoopPlanErrors((prev) => ({ ...prev, [stepId]: readableError(e) }));
    } finally {
      setLoopPlanLoading((prev) => ({ ...prev, [stepId]: false }));
    }
  };

  const preparePatchDraft = async (stepId: string) => {
    setDraftLoading((prev) => ({ ...prev, [stepId]: true }));
    setDraftErrors((prev) => ({ ...prev, [stepId]: "" }));
    setDrafts((prev) => ({ ...prev, [stepId]: null }));
    try {
      const draft = await createStepAgentPatchDraft(runId, stepId, {
        operator_note: operatorNotes[stepId] || "",
        max_target_files: 8,
        max_risks: 8,
        max_validation_steps: 8,
      });
      setDrafts((prev) => ({ ...prev, [stepId]: draft }));
      setProposalFields((prev) => ({
        ...prev,
        [stepId]: prev[stepId] ?? {
          file_path: draft.suggested_file_path || draft.target_files[0] || "",
          old_text: draft.suggested_old_text || "",
          new_text: draft.suggested_new_text || "",
          confirmed: false,
        },
      }));
    } catch (e: any) {
      setDraftErrors((prev) => ({ ...prev, [stepId]: readableError(e) }));
    } finally {
      setDraftLoading((prev) => ({ ...prev, [stepId]: false }));
    }
  };

  const setProposalField = (stepId: string, key: "file_path" | "old_text" | "new_text" | "confirmed", value: string | boolean) => {
    setProposalFields((prev) => ({
      ...prev,
      [stepId]: {
        file_path: prev[stepId]?.file_path || "",
        old_text: prev[stepId]?.old_text || "",
        new_text: prev[stepId]?.new_text || "",
        confirmed: prev[stepId]?.confirmed || false,
        [key]: value,
      },
    }));
  };

  const runGuardedProposalBridge = async (
    stepId: string,
    draft: StepAgentPatchDraftResponse,
    confirmCreateProposal: boolean,
  ) => {
    const fields = proposalFields[stepId] ?? {
      file_path: draft.suggested_file_path || draft.target_files[0] || "",
      old_text: draft.suggested_old_text || "",
      new_text: draft.suggested_new_text || "",
      confirmed: false,
    };
    setProposalLoading((prev) => ({ ...prev, [stepId]: true }));
    setProposalErrors((prev) => ({ ...prev, [stepId]: "" }));
    try {
      const response = await createStepPatchDraftGuardedProposal(runId, stepId, {
        patch_draft: draft as unknown as Record<string, unknown>,
        confirm_create_proposal: confirmCreateProposal,
        operator_note: operatorNotes[stepId] || "",
        selected_file_path: fields.file_path,
        selected_old_text: fields.old_text,
        selected_new_text: fields.new_text,
      });
      setProposalResponses((prev) => ({ ...prev, [stepId]: response }));
    } catch (e: any) {
      setProposalErrors((prev) => ({ ...prev, [stepId]: readableError(e) }));
    } finally {
      setProposalLoading((prev) => ({ ...prev, [stepId]: false }));
    }
  };

  const renderList = (items: string[], empty: string, color = "text-gray-400") => (
    items.length > 0 ? (
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span key={item} className={`rounded border border-gray-800 bg-gray-950 px-1.5 py-0.5 text-[11px] font-mono ${color}`}>
            {item}
          </span>
        ))}
      </div>
    ) : (
      <span className="text-xs text-gray-600">{empty}</span>
    )
  );

  return (
    <div className="space-y-4" data-action-anchor="agent-step-context">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold text-gray-200">Agent Step Context</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            Read-only agent-prep summary. This section does not start execution, call providers, create tool calls, apply patches, or run commands.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh Context"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/30 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      {!context && !loading && !error && (
        <div className="rounded border border-gray-800 bg-gray-950 p-4 text-sm text-gray-500">
          Refresh to load read-only agent-ready step context for this run.
        </div>
      )}

      {context && (
        <>
          <div className="grid gap-2 md:grid-cols-4">
            <div className="rounded border border-gray-800 bg-gray-950 p-3">
              <p className="text-[11px] uppercase text-gray-600">Steps</p>
              <p className="mt-1 text-lg font-semibold text-gray-200">{context.total_steps}</p>
            </div>
            <div className="rounded border border-emerald-900/50 bg-emerald-950/20 p-3">
              <p className="text-[11px] uppercase text-emerald-700">Ready</p>
              <p className="mt-1 text-lg font-semibold text-emerald-300">{context.ready_steps}</p>
            </div>
            <div className="rounded border border-red-900/50 bg-red-950/20 p-3">
              <p className="text-[11px] uppercase text-red-700">Blocked</p>
              <p className="mt-1 text-lg font-semibold text-red-300">{context.blocked_steps}</p>
            </div>
            <div className="rounded border border-gray-800 bg-gray-950 p-3">
              <p className="text-[11px] uppercase text-gray-600">Project</p>
              <p className="mt-1 truncate font-mono text-xs text-gray-300">{context.project_id || "none"}</p>
            </div>
          </div>

          <div className="rounded border border-blue-900/40 bg-blue-950/20 px-3 py-2">
            <p className="text-[11px] uppercase text-blue-500">Next recommended action</p>
            <p className="mt-1 text-sm text-blue-100">{context.next_recommended_action}</p>
          </div>

          <div className="space-y-3">
            {context.items.length === 0 ? (
              <div className="rounded border border-gray-800 bg-gray-950 p-4 text-sm text-gray-500">
                No run steps are available for agent preparation.
              </div>
            ) : (
              context.items.map((item) => (
                <div
                  key={item.step_id}
                  data-step-id={item.step_id}
                  data-action-anchor="agent-step-context"
                  className="rounded border border-gray-800 bg-gray-950 p-3"
                >
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <div className="flex flex-wrap items-center gap-2">
                        <h4 className="text-sm font-medium text-gray-200">{item.title}</h4>
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[11px] font-mono text-gray-400">{item.status}</span>
                        <span className={`rounded px-1.5 py-0.5 text-[11px] ${
                          item.ready_for_agent_execution ? "bg-emerald-900/30 text-emerald-300" : "bg-gray-800 text-gray-500"
                        }`}>
                          {item.ready_for_agent_execution ? "agent ready" : "not ready"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-gray-500">
                        Agent: <span className="font-mono text-gray-300">{item.canonical_agent_id}</span>
                        {item.agent_role && <span> · Role: <span className="font-mono text-gray-400">{item.agent_role}</span></span>}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <span className={`rounded px-1.5 py-0.5 text-[11px] ${
                        item.manual_approval_required ? "bg-orange-900/30 text-orange-300" : "bg-gray-800 text-gray-400"
                      }`}>
                        {item.manual_approval_required ? "manual approval" : "approval not required"}
                      </span>
                      <span className={`rounded px-1.5 py-0.5 text-[11px] ${
                        item.provider_allowed ? "bg-red-900/30 text-red-300" : "bg-emerald-900/30 text-emerald-300"
                      }`}>
                        provider {item.provider_allowed ? "allowed" : "disabled"}
                      </span>
                      <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[11px] text-gray-400">risk {item.risk_level}</span>
                    </div>
                  </div>

                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <div>
                      <p className="mb-1 text-[11px] uppercase text-gray-600">Requirement IDs</p>
                      {renderList(item.requirement_ids, "No requirement links")}
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] uppercase text-gray-600">Module IDs</p>
                      {renderList(item.module_ids, "No module links")}
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] uppercase text-gray-600">Safety gates</p>
                      {renderList(item.safety_gates, "No safety gates", "text-yellow-300")}
                    </div>
                    <div>
                      <p className="mb-1 text-[11px] uppercase text-gray-600">Depends on</p>
                      {renderList(item.depends_on, "No dependencies")}
                    </div>
                  </div>

                  <p className="mt-3 text-xs text-gray-400">
                    Next safe action: <span className="text-gray-200">{item.next_safe_action}</span>
                  </p>

                  {item.repo_context_available && (
                    <div className="mt-3 rounded border border-teal-900/40 bg-teal-950/15 p-3">
                      <div className="mb-2 flex flex-wrap items-center gap-2">
                        <p className="text-sm font-medium text-teal-200">Repo-aware context</p>
                        {item.detected_project_type && (
                          <span className="rounded bg-gray-900 px-1.5 py-0.5 text-[11px] text-teal-300">
                            {item.detected_project_type}
                          </span>
                        )}
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Detected stack</p>
                          {renderList(item.detected_stack, "No stack hints")}
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Relevant areas</p>
                          {renderList(item.relevant_area_hints, "No area hints")}
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Manifest scripts</p>
                          {renderList(item.relevant_manifest_scripts, "No manifest scripts")}
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Test discovery</p>
                          {renderList(item.test_discovery_hints, "No test hints")}
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Copy-only safe commands</p>
                          {renderList(item.suggested_safe_commands, "No command suggestions", "text-cyan-300")}
                        </div>
                        <div>
                          <p className="mb-1 text-[11px] uppercase text-gray-600">Protected warnings</p>
                          {renderList(item.protected_path_warnings, "No protected warnings", "text-yellow-300")}
                        </div>
                      </div>
                      <p className="mt-2 text-[11px] text-teal-300/70">
                        Safe commands are copy-only suggestions. This panel does not execute commands or modify files.
                      </p>
                    </div>
                  )}

                  {(item.blockers.length > 0 || item.warnings.length > 0) && (
                    <div className="mt-3 space-y-1">
                      {item.blockers.map((blocker) => (
                        <div key={blocker} className="rounded bg-red-950/40 px-2 py-1 text-xs text-red-300">{blocker}</div>
                      ))}
                      {item.warnings.map((warning) => (
                        <div key={warning} className="rounded bg-yellow-950/30 px-2 py-1 text-xs text-yellow-300">{warning}</div>
                      ))}
                    </div>
                  )}

                  <div className="mt-3 rounded border border-sky-900/40 bg-sky-950/15 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-sky-200">Controlled Apply/Test/Fix Loop</p>
                        <p className="mt-0.5 text-xs text-sky-300/70">
                          Read-only status guidance. No patch, proposal, command, test, fix, or provider call is started here.
                        </p>
                      </div>
                      <button
                        onClick={() => refreshControlledLoopPlan(item.step_id)}
                        disabled={!!loopPlanLoading[item.step_id]}
                        className="rounded bg-sky-800 px-3 py-1.5 text-xs text-sky-100 hover:bg-sky-700 disabled:opacity-50"
                      >
                        {loopPlanLoading[item.step_id] ? "Refreshing..." : "Refresh loop plan"}
                      </button>
                    </div>

                    {loopPlanErrors[item.step_id] && (
                      <div className="mt-2 rounded bg-red-950/40 px-2 py-1 text-xs text-red-300">{loopPlanErrors[item.step_id]}</div>
                    )}

                    {loopPlans[item.step_id] ? (() => {
                      const plan = loopPlans[item.step_id]!;
                      return (
                        <div className="mt-3 space-y-3 text-xs">
                          <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
                            <p className="text-[11px] uppercase text-gray-600">Current stage</p>
                            <p className="mt-1 font-mono text-sky-200">{plan.current_stage}</p>
                            <p className="mt-1 text-gray-300">{plan.next_recommended_action}</p>
                          </div>
                          <div className="grid gap-2 md:grid-cols-2">
                            {plan.stages.map((stage) => (
                              <div key={stage.id} className="rounded border border-gray-800 bg-gray-950 p-2">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="font-medium text-gray-200">{stage.title}</p>
                                  <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-[10px] text-gray-400">{stage.status}</span>
                                </div>
                                <p className="mt-1 text-gray-500">{stage.summary}</p>
                                {stage.next_action_label && (
                                  <p className="mt-1 text-sky-300">
                                    Next: {stage.next_action_label}
                                    {stage.next_action_kind && <span className="text-gray-600"> ({stage.next_action_kind})</span>}
                                  </p>
                                )}
                                {stage.blockers.map((blocker) => (
                                  <div key={blocker} className="mt-1 rounded bg-red-950/40 px-2 py-1 text-red-300">{blocker}</div>
                                ))}
                                {stage.warnings.map((warning) => (
                                  <div key={warning} className="mt-1 rounded bg-yellow-950/30 px-2 py-1 text-yellow-300">{warning}</div>
                                ))}
                              </div>
                            ))}
                          </div>
                          {plan.safe_command_suggestions.length > 0 && (
                            <div className="rounded border border-cyan-900/40 bg-cyan-950/15 p-3">
                              <p className="text-sm font-medium text-cyan-200">Copy-only safe command suggestions</p>
                              <p className="mt-0.5 text-[11px] text-cyan-300/70">
                                Suggestions only. Use existing explicit safe-runner controls if you choose to execute one.
                              </p>
                              <div className="mt-2 flex flex-wrap gap-2">
                                {plan.safe_command_suggestions.map((cmd) => (
                                  <button
                                    key={`${cmd.source}:${cmd.command}`}
                                    onClick={() => navigator.clipboard?.writeText(cmd.command)}
                                    className="rounded border border-cyan-900/50 bg-gray-950 px-2 py-1 font-mono text-[11px] text-cyan-200 hover:bg-cyan-950/30"
                                    title={cmd.reason}
                                  >
                                    Copy command: {cmd.command}
                                  </button>
                                ))}
                              </div>
                            </div>
                          )}
                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() => document.querySelector('[data-action-anchor="agent-step-context"]')?.scrollIntoView({ behavior: "smooth", block: "start" })}
                              className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
                            >
                              Open Patch Draft section
                            </button>
                            <button
                              onClick={() => document.querySelector('[data-action-anchor="agent-step-context"]')?.scrollIntoView({ behavior: "smooth", block: "start" })}
                              className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
                            >
                              Open Guarded Proposal section
                            </button>
                            <button
                              onClick={() => document.querySelector('[data-action-anchor="tool-calls"]')?.scrollIntoView({ behavior: "smooth", block: "start" })}
                              className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
                            >
                              Open Test Tools section
                            </button>
                          </div>
                          <ul className="space-y-0.5 text-gray-600">
                            {plan.safety_notes.map((note) => <li key={note}>{note}</li>)}
                          </ul>
                        </div>
                      );
                    })() : (
                      <p className="mt-2 text-xs text-gray-500">
                        Refresh to inspect repo context, patch draft, guarded proposal, apply, safe test, analysis, and fix-draft status.
                      </p>
                    )}
                  </div>

                  <div className="mt-3 rounded border border-indigo-900/40 bg-indigo-950/20 p-3">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-sm font-medium text-indigo-200">Prepare Agent Patch Draft</p>
                        <p className="mt-0.5 text-xs text-indigo-300/70">
                          Draft only. Review manually before proposal. No patch was applied. No test was run.
                        </p>
                      </div>
                      <button
                        onClick={() => preparePatchDraft(item.step_id)}
                        disabled={!!draftLoading[item.step_id]}
                        className="rounded bg-indigo-800 px-3 py-1.5 text-xs text-indigo-100 hover:bg-indigo-700 disabled:opacity-50"
                      >
                        {draftLoading[item.step_id] ? "Preparing..." : "Prepare Patch Draft"}
                      </button>
                    </div>
                    <textarea
                      value={operatorNotes[item.step_id] || ""}
                      onChange={(event) =>
                        setOperatorNotes((prev) => ({ ...prev, [item.step_id]: event.target.value }))
                      }
                      rows={2}
                      placeholder="Optional operator note to narrow file or intent..."
                      className="mt-2 w-full resize-none rounded border border-gray-800 bg-gray-950 px-2 py-1.5 text-xs text-gray-300 placeholder:text-gray-600"
                    />

                    {draftErrors[item.step_id] && (
                      <div className="mt-2 rounded bg-red-950/40 px-2 py-1 text-xs text-red-300">{draftErrors[item.step_id]}</div>
                    )}

                    {drafts[item.step_id] && (() => {
                      const draft = drafts[item.step_id]!;
                      const fields = proposalFields[item.step_id] ?? {
                        file_path: draft.suggested_file_path || draft.target_files[0] || "",
                        old_text: draft.suggested_old_text || "",
                        new_text: draft.suggested_new_text || "",
                        confirmed: false,
                      };
                      const proposalResponse = proposalResponses[item.step_id];
                      const canCreateProposal = Boolean(fields.file_path && fields.old_text && fields.new_text && fields.confirmed && !proposalLoading[item.step_id]);
                      return (
                        <div className="mt-3 space-y-2 rounded border border-gray-800 bg-gray-950 p-3 text-xs">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded px-1.5 py-0.5 ${
                              draft.ready_for_proposal ? "bg-emerald-900/30 text-emerald-300" : "bg-yellow-900/30 text-yellow-300"
                            }`}>
                              {draft.ready_for_proposal ? "ready for manual proposal review" : "needs operator review"}
                            </span>
                            <span className="font-mono text-gray-500">{draft.canonical_agent_id}</span>
                          </div>
                          <p className="text-gray-300">{draft.draft_summary}</p>
                          <div>
                            <p className="mb-1 text-gray-600 uppercase">Patch intent</p>
                            <p className="rounded bg-gray-900 px-2 py-1 text-gray-300">{draft.patch_intent}</p>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div>
                              <p className="mb-1 text-gray-600 uppercase">Target files</p>
                              {renderList(draft.target_files, "No target files inferred")}
                            </div>
                            <div>
                              <p className="mb-1 text-gray-600 uppercase">Validation steps</p>
                              {renderList(draft.validation_steps, "No validation steps")}
                            </div>
                          </div>
                          <div className="grid gap-3 md:grid-cols-2">
                            <div>
                              <p className="mb-1 text-gray-600 uppercase">Suggested old_text</p>
                              <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-gray-900 px-2 py-1 text-gray-500">
                                {draft.suggested_old_text || "(empty until operator reviews current file content)"}
                              </pre>
                            </div>
                            <div>
                              <p className="mb-1 text-gray-600 uppercase">Suggested new_text</p>
                              <pre className="max-h-24 overflow-auto whitespace-pre-wrap rounded bg-gray-900 px-2 py-1 text-gray-400">
                                {draft.suggested_new_text || "(operator must draft manually)"}
                              </pre>
                            </div>
                          </div>
                          {draft.risks.length > 0 && (
                            <div>
                              <p className="mb-1 text-gray-600 uppercase">Risks</p>
                              <ul className="space-y-0.5 text-amber-300">
                                {draft.risks.map((risk) => <li key={risk}>{risk}</li>)}
                              </ul>
                            </div>
                          )}
                          {(draft.blockers.length > 0 || draft.warnings.length > 0) && (
                            <div className="space-y-1">
                              {draft.blockers.map((blocker) => (
                                <div key={blocker} className="rounded bg-red-950/40 px-2 py-1 text-red-300">{blocker}</div>
                              ))}
                              {draft.warnings.map((warning) => (
                                <div key={warning} className="rounded bg-yellow-950/30 px-2 py-1 text-yellow-300">{warning}</div>
                              ))}
                            </div>
                          )}
                          <p className="text-indigo-200">Next: {draft.next_recommended_action}</p>
                          {draft.repo_context_available && (
                            <div className="rounded border border-teal-900/40 bg-teal-950/15 p-3">
                              <p className="mb-2 text-sm font-medium text-teal-200">Repo-aware draft hints</p>
                              <div className="grid gap-3 md:grid-cols-2">
                                <div>
                                  <p className="mb-1 text-gray-600 uppercase">Stack</p>
                                  {renderList(draft.detected_stack, "No stack hints")}
                                </div>
                                <div>
                                  <p className="mb-1 text-gray-600 uppercase">Areas</p>
                                  {renderList(draft.relevant_area_hints, "No repo areas")}
                                </div>
                                <div>
                                  <p className="mb-1 text-gray-600 uppercase">Test hints</p>
                                  {renderList(draft.test_discovery_hints, "No test hints")}
                                </div>
                                <div>
                                  <p className="mb-1 text-gray-600 uppercase">Copy-only commands</p>
                                  {renderList(draft.suggested_safe_commands, "No command suggestions", "text-cyan-300")}
                                </div>
                              </div>
                              {draft.protected_path_warnings.length > 0 && (
                                <div className="mt-2 space-y-1">
                                  {draft.protected_path_warnings.map((warning) => (
                                    <div key={warning} className="rounded bg-yellow-950/30 px-2 py-1 text-yellow-300">
                                      {warning}
                                    </div>
                                  ))}
                                </div>
                              )}
                              <p className="mt-2 text-gray-600">
                                These commands are suggestions only. No command was run.
                              </p>
                            </div>
                          )}
                          <div className="rounded border border-cyan-900/40 bg-cyan-950/15 p-3">
                            <div className="flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <p className="text-sm font-medium text-cyan-200">Preflight Guarded Proposal</p>
                                <p className="mt-0.5 text-[11px] text-cyan-300/70">
                                  Proposal only. No patch was applied. No tests were run. Apply still requires explicit confirmation.
                                </p>
                              </div>
                              <button
                                onClick={() => runGuardedProposalBridge(item.step_id, draft, false)}
                                disabled={!!proposalLoading[item.step_id]}
                                className="rounded bg-cyan-800 px-2 py-1 text-xs text-cyan-100 hover:bg-cyan-700 disabled:opacity-50"
                              >
                                {proposalLoading[item.step_id] ? "Checking..." : "Preflight Guarded Proposal"}
                              </button>
                            </div>
                            <div className="mt-2 grid gap-2">
                              <label className="block">
                                <span className="text-[11px] uppercase text-gray-600">File path</span>
                                <input
                                  value={fields.file_path}
                                  onChange={(event) => setProposalField(item.step_id, "file_path", event.target.value)}
                                  placeholder="backend/src/example.py"
                                  className="mt-1 w-full rounded border border-gray-800 bg-gray-950 px-2 py-1.5 text-xs text-gray-300"
                                />
                              </label>
                              <label className="block">
                                <span className="text-[11px] uppercase text-gray-600">Exact old_text</span>
                                <textarea
                                  value={fields.old_text}
                                  onChange={(event) => setProposalField(item.step_id, "old_text", event.target.value)}
                                  rows={3}
                                  placeholder="Paste the exact current text after manual review..."
                                  className="mt-1 w-full resize-y rounded border border-gray-800 bg-gray-950 px-2 py-1.5 text-xs text-gray-300"
                                />
                              </label>
                              <label className="block">
                                <span className="text-[11px] uppercase text-gray-600">Reviewed new_text</span>
                                <textarea
                                  value={fields.new_text}
                                  onChange={(event) => setProposalField(item.step_id, "new_text", event.target.value)}
                                  rows={4}
                                  placeholder="Draft the reviewed replacement text..."
                                  className="mt-1 w-full resize-y rounded border border-gray-800 bg-gray-950 px-2 py-1.5 text-xs text-gray-300"
                                />
                              </label>
                              <label className="flex items-start gap-2 rounded border border-gray-800 bg-gray-900 px-2 py-2 text-xs text-gray-300">
                                <input
                                  type="checkbox"
                                  checked={fields.confirmed}
                                  onChange={(event) => setProposalField(item.step_id, "confirmed", event.target.checked)}
                                  className="mt-0.5"
                                />
                                <span>I confirm creating a patch proposal only. Do not apply patch.</span>
                              </label>
                            </div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              <button
                                onClick={() => runGuardedProposalBridge(item.step_id, draft, true)}
                                disabled={!canCreateProposal}
                                className="rounded bg-emerald-800 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-700 disabled:opacity-50"
                              >
                                Create Guarded Proposal
                              </button>
                            </div>
                            {proposalErrors[item.step_id] && (
                              <div className="mt-2 rounded bg-red-950/40 px-2 py-1 text-red-300">{proposalErrors[item.step_id]}</div>
                            )}
                            {proposalResponse && (
                              <div className="mt-2 space-y-2 rounded border border-gray-800 bg-gray-950 p-2">
                                <div className="flex flex-wrap gap-2">
                                  <span className={`rounded px-1.5 py-0.5 ${
                                    proposalResponse.created ? "bg-emerald-900/30 text-emerald-300" : "bg-gray-800 text-gray-400"
                                  }`}>
                                    {proposalResponse.created ? "proposal created" : "preflight only"}
                                  </span>
                                  <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">guard {proposalResponse.guard_decision}</span>
                                  {proposalResponse.proposal_id && (
                                    <span className="rounded bg-gray-800 px-1.5 py-0.5 font-mono text-gray-400">proposal {proposalResponse.proposal_id}</span>
                                  )}
                                </div>
                                {proposalResponse.created && (
                                  <p className="text-emerald-300">
                                    Proposal created. Patch was not applied. Tests were not run.
                                  </p>
                                )}
                                {(proposalResponse.blockers.length > 0 || proposalResponse.warnings.length > 0) && (
                                  <div className="space-y-1">
                                    {proposalResponse.blockers.map((blocker) => (
                                      <div key={blocker} className="rounded bg-red-950/40 px-2 py-1 text-red-300">{blocker}</div>
                                    ))}
                                    {proposalResponse.warnings.map((warning) => (
                                      <div key={warning} className="rounded bg-yellow-950/30 px-2 py-1 text-yellow-300">{warning}</div>
                                    ))}
                                  </div>
                                )}
                                {proposalResponse.module_awareness && (
                                  <details className="rounded border border-gray-800 bg-gray-900 px-2 py-1">
                                    <summary className="cursor-pointer text-gray-400">Module awareness</summary>
                                    <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-gray-500">
                                      {JSON.stringify(proposalResponse.module_awareness, null, 2)}
                                    </pre>
                                  </details>
                                )}
                                {proposalResponse.module_policy && (
                                  <details className="rounded border border-gray-800 bg-gray-900 px-2 py-1">
                                    <summary className="cursor-pointer text-gray-400">Module policy</summary>
                                    <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-gray-500">
                                      {JSON.stringify(proposalResponse.module_policy, null, 2)}
                                    </pre>
                                  </details>
                                )}
                                {proposalResponse.patch_review && (
                                  <details className="rounded border border-gray-800 bg-gray-900 px-2 py-1">
                                    <summary className="cursor-pointer text-gray-400">Patch review assistant</summary>
                                    <pre className="mt-1 max-h-32 overflow-auto whitespace-pre-wrap text-gray-500">
                                      {JSON.stringify(proposalResponse.patch_review, null, 2)}
                                    </pre>
                                  </details>
                                )}
                                <p className="text-cyan-200">Next: {proposalResponse.next_recommended_action}</p>
                                <ul className="space-y-0.5 text-gray-600">
                                  {proposalResponse.safety_notes.map((note) => <li key={note}>{note}</li>)}
                                </ul>
                              </div>
                            )}
                          </div>
                          <div className="flex flex-wrap gap-2">
                            <button
                              onClick={() => navigator.clipboard?.writeText([
                                draft.patch_intent,
                                `Target files: ${draft.target_files.join(", ")}`,
                                draft.draft_summary,
                              ].join("\n\n"))}
                              className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-300 hover:bg-gray-700"
                            >
                              Copy draft summary
                            </button>
                            {onUsePatchDraft && (
                              <button
                                onClick={() => onUsePatchDraft(item.step_id, draft)}
                                className="rounded bg-emerald-800 px-2 py-1 text-xs text-emerald-100 hover:bg-emerald-700"
                              >
                                Use in Patch Proposal Form
                              </button>
                            )}
                          </div>
                          <p className="text-gray-600">
                            Use in Patch Proposal Form only prefills the context and suggested file path. It does not submit a proposal, apply a patch, call a provider, or run tests.
                          </p>
                        </div>
                      );
                    })()}
                  </div>
                </div>
              ))
            )}
          </div>

          {context.safety_notes.length > 0 && (
            <div className="rounded border border-gray-800 bg-gray-950 p-3">
              <p className="mb-2 text-[11px] uppercase text-gray-600">Safety notes</p>
              <ul className="space-y-1 text-xs text-gray-500">
                {context.safety_notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Operator Queue Panel ──────────────────────────────────────────────────────

const PRIORITY_COLORS: Record<string, string> = {
  high: "bg-red-900/40 text-red-300 border-red-800",
  medium: "bg-yellow-900/40 text-yellow-300 border-yellow-800",
  low: "bg-gray-800 text-gray-400 border-gray-700",
};

const STATUS_COLORS: Record<string, string> = {
  ready: "bg-emerald-900/40 text-emerald-300 border-emerald-800",
  blocked: "bg-red-900/40 text-red-300 border-red-800",
  manual_required: "bg-orange-900/40 text-orange-300 border-orange-800",
  done: "bg-gray-800 text-gray-500 border-gray-700",
};

function OperatorQueueItemCard({
  item,
  onFocus,
}: {
  item: OperatorQueueItem;
  onFocus: (stepId: string, actionType: string) => Promise<{ message: string; error?: string }>;
}) {
  const [focusResult, setFocusResult] = useState<{ message: string; error?: string } | null>(null);
  const [focusing, setFocusing] = useState(false);

  const handleFocus = async () => {
    setFocusing(true);
    setFocusResult(null);
    try {
      const result = await onFocus(item.step_id, item.action_type);
      setFocusResult(result);
    } catch (e: any) {
      setFocusResult({ message: "", error: String(e) });
    } finally {
      setFocusing(false);
    }
  };

  return (
    <div className={`rounded border p-3 ${item.status === "done" ? "opacity-60" : ""} border-gray-700 bg-gray-850`}>
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span className={`px-1.5 py-0.5 rounded text-xs font-mono border ${PRIORITY_COLORS[item.priority] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
          {item.priority}
        </span>
        <span className={`px-1.5 py-0.5 rounded text-xs border ${STATUS_COLORS[item.status] ?? "bg-gray-800 text-gray-400 border-gray-700"}`}>
          {item.status.replace("_", " ")}
        </span>
        {item.is_destructive && (
          <span className="px-1.5 py-0.5 rounded text-xs border border-red-700 bg-red-900/30 text-red-300">destructive</span>
        )}
        {item.requires_confirmation && (
          <span className="px-1.5 py-0.5 rounded text-xs border border-yellow-700 bg-yellow-900/30 text-yellow-300">needs confirm</span>
        )}
        <span className="text-xs text-gray-500 font-mono">{item.action_type}</span>
      </div>
      <div className="font-medium text-sm text-gray-200 mb-0.5">{item.title}</div>
      <div className="text-xs text-gray-400 mb-1">{item.description}</div>
      <div className="text-xs text-gray-500 mb-1">
        <span className="text-gray-600">Step: </span>
        <span className="font-mono">{item.step_title}</span>
      </div>
      <div className="text-xs text-gray-500 mb-2">
        <span className="text-gray-600">Reason: </span>{item.reason}
      </div>
      {item.action_type === "execute_approval" && item.approval_id && (
        <div className="mb-2 rounded border border-purple-800/50 bg-purple-900/15 px-3 py-2 space-y-1">
          <p className="text-xs text-purple-300 font-semibold">⏳ Pending approval — go to Automation Approvals panel</p>
          <p className="text-xs text-gray-500 font-mono">Action: {item.approval_action_type}</p>
          <p className="text-xs text-gray-600 font-mono">ID: {item.approval_id.slice(0, 12)}…</p>
        </div>
      )}
      {item.warnings.length > 0 && (
        <div className="mb-2 space-y-1">
          {item.warnings.map((w, i) => (
            <div key={i} className="text-xs text-yellow-400 bg-yellow-900/20 rounded px-2 py-1">{w}</div>
          ))}
        </div>
      )}
      <div className="flex flex-wrap gap-2 items-center">
        <button
          onClick={handleFocus}
          disabled={focusing}
          className="px-3 py-1 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 disabled:opacity-50"
        >
          {focusing ? "Focusing…" : `Go to ${item.destination.replace("_", " ")}`}
        </button>
        <span className="text-xs text-gray-600">→ {item.destination}</span>
      </div>
      {focusResult && (
        <div className={`mt-2 text-xs rounded px-2 py-1 ${focusResult.error ? "bg-red-900/30 text-red-300" : "bg-emerald-900/20 text-emerald-400"}`}>
          {focusResult.error ? `⚠ ${focusResult.error}` : `✓ ${focusResult.message}`}
        </div>
      )}
    </div>
  );
}

// ── Approval-Gated Automation Panel ──────────────────────────────────────────

function ApprovalStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    pending: "bg-yellow-900/30 text-yellow-300",
    approved: "bg-emerald-900/30 text-emerald-300",
    rejected: "bg-red-900/30 text-red-300",
    executed: "bg-blue-900/30 text-blue-300",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-mono ${colors[status] ?? "bg-gray-800 text-gray-400"}`}>
      {status}
    </span>
  );
}

function ApprovalCard({
  item,
  onApprove,
  onReject,
  onExecute,
  loading,
}: {
  item: AutomationApprovalItem;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
  onExecute: (id: string) => void;
  loading: string;
}) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <ApprovalStatusBadge status={item.status} />
        <span className="font-mono text-gray-300">{item.action_type}</span>
        {item.is_destructive && (
          <span className="rounded bg-red-900/40 px-1.5 py-0.5 text-red-400">destructive</span>
        )}
        <span className={`rounded px-1.5 py-0.5 ${item.risk_level === "high" ? "bg-red-900/30 text-red-400" : "bg-gray-800 text-gray-500"}`}>
          {item.risk_level}
        </span>
        <span className="ml-auto font-mono text-gray-600">{item.id.slice(0, 8)}</span>
      </div>
      {item.step_id && (
        <p className="mt-1 text-gray-500">Step: <span className="font-mono">{item.step_id.slice(0, 12)}</span></p>
      )}
      <p className="mt-1 text-gray-400">{item.reason}</p>
      <p className="mt-1 text-gray-600">{new Date(item.created_at).toLocaleString()}</p>
      {item.status === "pending" && (
        <div className="mt-2 flex gap-2">
          <button
            onClick={() => onApprove(item.id)}
            disabled={loading !== ""}
            className="rounded bg-emerald-800 px-3 py-1 text-emerald-100 hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading === `approve-${item.id}` ? "Approving…" : "Approve"}
          </button>
          <button
            onClick={() => onReject(item.id)}
            disabled={loading !== ""}
            className="rounded bg-red-900 px-3 py-1 text-red-200 hover:bg-red-800 disabled:opacity-50"
          >
            {loading === `reject-${item.id}` ? "Rejecting…" : "Reject"}
          </button>
        </div>
      )}
      {item.status === "approved" && (
        <div className="mt-2">
          <button
            onClick={() => onExecute(item.id)}
            disabled={loading !== ""}
            className="rounded bg-blue-800 px-3 py-1 text-blue-100 hover:bg-blue-700 disabled:opacity-50"
          >
            {loading === `execute-${item.id}` ? "Executing…" : "Execute approved action"}
          </button>
        </div>
      )}
    </div>
  );
}

function AutomationApprovalPanel({ runId, queue }: { runId: string; queue: OperatorQueueResponse | null }) {
  const [approvals, setApprovals] = useState<AutomationApprovalItem[]>([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);
  const [approvalsError, setApprovalsError] = useState("");
  const [actionLoading, setActionLoading] = useState("");
  const [executeResult, setExecuteResult] = useState<AutomationApprovalExecuteResponse | null>(null);
  const [requestError, setRequestError] = useState("");
  const [requestLoading, setRequestLoading] = useState("");

  const loadApprovals = async () => {
    setApprovalsLoading(true);
    setApprovalsError("");
    try {
      const result = await listRunAutomationApprovals(runId);
      setApprovals(result.approvals);
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : "Failed to load approvals");
    } finally {
      setApprovalsLoading(false);
    }
  };

  const requestApproval = async (actionType: string, stepId: string | null) => {
    setRequestLoading(actionType);
    setRequestError("");
    try {
      const created = await createRunAutomationApproval(runId, {
        step_id: stepId,
        action_type: actionType,
        reason: `Operator requested approval for ${actionType}.`,
      });
      setApprovals((prev) => [created, ...prev]);
    } catch (e: unknown) {
      setRequestError(e instanceof Error ? e.message : "Failed to request approval");
    } finally {
      setRequestLoading("");
    }
  };

  const approveItem = async (approvalId: string) => {
    setActionLoading(`approve-${approvalId}`);
    try {
      const updated = await approveRunAutomationApproval(runId, approvalId);
      setApprovals((prev) => prev.map((a) => (a.id === approvalId ? updated : a)));
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : "Failed to approve");
    } finally {
      setActionLoading("");
    }
  };

  const rejectItem = async (approvalId: string) => {
    setActionLoading(`reject-${approvalId}`);
    try {
      const updated = await rejectRunAutomationApproval(runId, approvalId);
      setApprovals((prev) => prev.map((a) => (a.id === approvalId ? updated : a)));
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : "Failed to reject");
    } finally {
      setActionLoading("");
    }
  };

  const executeItem = async (approvalId: string) => {
    setActionLoading(`execute-${approvalId}`);
    setExecuteResult(null);
    try {
      const result = await executeRunAutomationApproval(runId, approvalId);
      setExecuteResult(result);
      // Refresh approvals to show updated status
      await loadApprovals();
    } catch (e: unknown) {
      setApprovalsError(e instanceof Error ? e.message : "Failed to execute");
    } finally {
      setActionLoading("");
    }
  };

  // Manual-required items in current queue that are approval-eligible
  const manualItems = (queue?.items ?? []).filter(
    (i) => i.status !== "blocked" && ["apply_patch_manual", "run_tests_manual", "create_proposal_manual", "check_guard"].includes(i.action_type)
  );

  return (
    <div className="rounded border border-gray-800 bg-gray-950 p-3 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-200">Approval Panel</h4>
          <p className="mt-1 text-xs text-gray-500">
            Approval does not bypass guard, safe command, or current state revalidation.
          </p>
        </div>
        <button
          onClick={loadApprovals}
          disabled={approvalsLoading}
          className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 disabled:opacity-50"
        >
          {approvalsLoading ? "Loading…" : "Refresh Approvals"}
        </button>
      </div>

      {manualItems.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500">Request approval for current queue items:</p>
          {manualItems.map((item) => (
            <div key={`req-${item.id}`} className="flex items-center gap-2 text-xs">
              <span className="font-mono text-gray-300">{item.action_type}</span>
              {item.step_id && <span className="text-gray-600 font-mono">{item.step_id.slice(0, 8)}</span>}
              <button
                onClick={() => requestApproval(item.action_type, item.step_id ?? null)}
                disabled={requestLoading !== ""}
                className="rounded bg-gray-700 px-2 py-0.5 text-gray-200 hover:bg-gray-600 disabled:opacity-50"
              >
                {requestLoading === item.action_type ? "Requesting…" : "Request approval"}
              </button>
            </div>
          ))}
        </div>
      )}

      {requestError && (
        <div className="rounded border border-red-800 bg-red-950/30 px-3 py-2 text-xs text-red-300">{requestError}</div>
      )}
      {approvalsError && (
        <div className="rounded border border-red-800 bg-red-950/30 px-3 py-2 text-xs text-red-300">{approvalsError}</div>
      )}

      {executeResult && (
        <div className={`rounded border px-3 py-2 text-xs ${executeResult.executed ? "border-emerald-800 bg-emerald-950/20 text-emerald-300" : "border-yellow-800 bg-yellow-950/20 text-yellow-300"}`}>
          <p className="font-medium">{executeResult.executed ? "✓ Executed" : `⚠ ${executeResult.status}`}</p>
          {executeResult.result_summary && <p className="mt-1 text-gray-400">{executeResult.result_summary}</p>}
          {executeResult.revalidation_error && <p className="mt-1 text-red-400">{executeResult.revalidation_error}</p>}
        </div>
      )}

      {approvals.length === 0 && !approvalsLoading ? (
        <p className="text-xs text-gray-600">No approvals yet — click Refresh Approvals to load.</p>
      ) : (
        <div className="space-y-2">
          {approvals.map((item) => (
            <ApprovalCard
              key={item.id}
              item={item}
              onApprove={approveItem}
              onReject={rejectItem}
              onExecute={executeItem}
              loading={actionLoading}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Agent Execution Harness Panel ─────────────────────────────────────────────

function AgentExecutionPanel({
  runId,
  stepId,
  onPatchDraftPrefill,
}: {
  runId: string;
  stepId: string | null;
  onPatchDraftPrefill?: (stepId: string, prefill: IssuePrefill) => void;
}) {
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<AgentExecutionContext | null>(null);
  const [contextLoading, setContextLoading] = useState(false);
  const [contextError, setContextError] = useState("");

  const [mode, setMode] = useState<"dry_run" | "mock" | "provider">("dry_run");
  const [taskType, setTaskType] = useState("implementation");
  const [userInstruction, setUserInstruction] = useState("");
  const [allowProvider, setAllowProvider] = useState(false);
  const [selectedAgentId, setSelectedAgentId] = useState("");
  const [maxOutputChars, setMaxOutputChars] = useState(12000);

  const [execResult, setExecResult] = useState<AgentExecutionResponse | null>(null);
  const [execLoading, setExecLoading] = useState(false);
  const [execError, setExecError] = useState("");

  const [history, setHistory] = useState<AgentExecutionListResponse | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);

  // Patch draft bridge state
  const [patchDraft, setPatchDraft] = useState<AgentPatchDraftResponse | null>(null);
  const [patchDraftLoading, setPatchDraftLoading] = useState(false);
  const [patchDraftError, setPatchDraftError] = useState("");

  const loadContext = async () => {
    if (!stepId) return;
    setContextLoading(true);
    setContextError("");
    try {
      const ctx = await getAgentExecutionContext(runId, stepId);
      setContext(ctx);
      if (!selectedAgentId && ctx.recommended_agent_id) {
        setSelectedAgentId(ctx.recommended_agent_id);
      }
    } catch (e: any) {
      setContextError(readableError(e));
    } finally {
      setContextLoading(false);
    }
  };

  const loadHistory = async () => {
    if (!stepId) return;
    setHistoryLoading(true);
    try {
      const h = await listAgentExecutions(runId, stepId);
      setHistory(h);
    } catch {
      // silently ignore
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleRun = async () => {
    if (!stepId) return;
    setExecLoading(true);
    setExecError("");
    setExecResult(null);
    try {
      const req: AgentExecutionRequest = {
        agent_id: selectedAgentId || undefined,
        task_type: taskType,
        mode,
        allow_provider_call: allowProvider,
        persist_result: true,
        max_output_chars: maxOutputChars,
        user_instruction: userInstruction,
        include_requirement_context: true,
        include_recent_tool_calls: true,
        include_patch_lifecycle: true,
      };
      const res = await runAgentExecution(runId, stepId, req);
      setExecResult(res);
      if (mode !== "dry_run") await loadHistory();
    } catch (e: any) {
      setExecError(readableError(e));
    } finally {
      setExecLoading(false);
    }
  };

  const preparePatchDraft = async () => {
    if (!stepId || !execResult?.result) return;
    setPatchDraftLoading(true);
    setPatchDraftError("");
    setPatchDraft(null);
    try {
      const draft = await createAgentPatchDraft(runId, stepId, {
        agent_result: execResult.result,
        include_context: true,
        include_risks: true,
        include_tests: true,
      });
      setPatchDraft(draft);
    } catch (e: any) {
      setPatchDraftError(readableError(e));
    } finally {
      setPatchDraftLoading(false);
    }
  };

  const useInPatchForm = () => {
    if (!stepId || !patchDraft) return;
    const prefill: IssuePrefill = {
      file_path: patchDraft.recommended_file_path || "",
      context_kind: "agent-result",
      context_location: patchDraft.step_id,
      context_message: patchDraft.patch_context,
    };
    onPatchDraftPrefill?.(stepId, prefill);
  };

  if (!stepId) return null;

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        onClick={() => {
          const next = !open;
          setOpen(next);
          if (next && !context) loadContext();
          if (next && !history) loadHistory();
        }}
        className="w-full px-4 py-3 flex items-center justify-between bg-gray-800/50 hover:bg-gray-800 text-left"
      >
        <div>
          <span className="font-medium text-gray-200 text-sm">Agent Execution Harness</span>
          <span className="ml-2 text-xs text-gray-500">advisory only — no file mutation</span>
        </div>
        <span className="text-gray-500 text-xs">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="p-4 space-y-4 bg-gray-900/30">
          {/* Safety note */}
          <div className="text-xs text-amber-400/80 bg-amber-950/30 border border-amber-800/40 rounded px-3 py-2">
            Agent execution does not mutate files, create proposals, apply patches, run commands, or bypass approvals.
          </div>

          {/* Context */}
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-400">Step Context</span>
              <button
                onClick={loadContext}
                disabled={contextLoading}
                className="text-xs px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-400 disabled:opacity-50"
              >
                {contextLoading ? "Loading…" : "Refresh Context"}
              </button>
            </div>
            {contextError && <p className="text-xs text-red-400">{contextError}</p>}
            {context && (
              <div className="space-y-1 text-xs text-gray-400">
                <p><span className="text-gray-500">Step:</span> {context.step_title}</p>
                <p><span className="text-gray-500">Recommended agent:</span> {context.recommended_agent_name} ({context.recommended_agent_id})</p>
                <p><span className="text-gray-500">Recommended task type:</span> {context.recommended_task_type}</p>
                {context.requirement_ids.length > 0 && (
                  <p><span className="text-gray-500">Requirements:</span> {context.requirement_ids.join(", ")}</p>
                )}
                {context.patch_lifecycle_summary && (
                  <p><span className="text-gray-500">Patch lifecycle:</span> {context.patch_lifecycle_summary}</p>
                )}
                {context.module_context?.has_active_module_map && (
                  <div className="mt-2 rounded border border-gray-800 bg-gray-950/40 p-2 space-y-1">
                    <p>
                      <span className="text-gray-500">Module map:</span>{" "}
                      v{context.module_context.module_map_version ?? "?"} · {context.module_context.matched_modules.length} matched
                    </p>
                    {context.module_context.matched_modules.slice(0, 3).map((mod) => (
                      <div key={mod.id ?? mod.slug ?? mod.name} className="text-gray-500">
                        <span className="text-gray-300">{mod.name ?? mod.slug}</span>
                        {mod.slug && <span> · {mod.slug}</span>}
                        {(mod.key_files ?? []).length > 0 && (
                          <span> · key files: {(mod.key_files ?? []).slice(0, 3).join(", ")}</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Configuration */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-400">Execution Settings</p>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Agent</label>
                <select
                  value={selectedAgentId}
                  onChange={(e) => setSelectedAgentId(e.target.value)}
                  className="w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-300"
                >
                  <option value="">{context ? `Auto (${context.recommended_agent_id})` : "Auto"}</option>
                  {(context?.available_agents ?? []).map((a) => (
                    <option key={a.id} value={a.id}>{a.name}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Mode</label>
                <select
                  value={mode}
                  onChange={(e) => setMode(e.target.value as "dry_run" | "mock" | "provider")}
                  className="w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-300"
                >
                  <option value="dry_run">Dry Run (prompt preview only)</option>
                  <option value="mock">Mock (deterministic test result)</option>
                  <option value="provider">Provider (Ollama, local only)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Task Type</label>
                <select
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  className="w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-300"
                >
                  {["implementation", "planning", "architecture", "debugging", "test_generation",
                    "code_review", "security_review", "documentation", "deployment"].map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-xs text-gray-500 mb-1">Max Output Chars</label>
                <input
                  type="number"
                  value={maxOutputChars}
                  onChange={(e) => setMaxOutputChars(Number(e.target.value))}
                  min={1000}
                  max={32000}
                  step={1000}
                  className="w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-300"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">User Instruction (optional)</label>
              <textarea
                value={userInstruction}
                onChange={(e) => setUserInstruction(e.target.value)}
                rows={2}
                placeholder="Add context or focus for this agent task…"
                className="w-full text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1.5 text-gray-300 resize-none"
              />
            </div>

            {mode === "provider" && (
              <label className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={allowProvider}
                  onChange={(e) => setAllowProvider(e.target.checked)}
                  className="rounded"
                />
                Allow provider call (Ollama local — required for provider mode)
              </label>
            )}
          </div>

          {/* Action buttons */}
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={loadContext}
              disabled={contextLoading}
              className="text-xs px-3 py-1.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 disabled:opacity-50"
            >
              {contextLoading ? "Building…" : "Build Agent Context"}
            </button>
            <button
              onClick={handleRun}
              disabled={execLoading || !context}
              className={`text-xs px-3 py-1.5 rounded disabled:opacity-50 ${
                mode === "dry_run"
                  ? "bg-gray-700 hover:bg-gray-600 text-gray-300"
                  : mode === "mock"
                  ? "bg-blue-800 hover:bg-blue-700 text-blue-100"
                  : "bg-purple-800 hover:bg-purple-700 text-purple-100"
              }`}
            >
              {execLoading
                ? "Running…"
                : mode === "dry_run"
                ? "Preview Prompt"
                : mode === "mock"
                ? "Run Mock Agent"
                : "Run Provider Agent"}
            </button>
          </div>

          {execError && <p className="text-xs text-red-400">{execError}</p>}

          {/* Results */}
          {execResult && (
            <div className="space-y-3 border-t border-gray-700 pt-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-gray-300">Result</span>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  execResult.status === "completed" ? "bg-green-900/50 text-green-300" :
                  execResult.status === "planned" ? "bg-gray-700 text-gray-400" :
                  execResult.status === "provider_unavailable" ? "bg-yellow-900/50 text-yellow-300" :
                  "bg-red-900/50 text-red-300"
                }`}>{execResult.status}</span>
                <span className="text-xs text-gray-600">mode={execResult.mode}</span>
                {execResult.tool_call_id && (
                  <span className="text-xs text-gray-600">audit:{execResult.tool_call_id.slice(0, 8)}</span>
                )}
              </div>

              {execResult.safety_notes.map((n, i) => (
                <p key={i} className="text-xs text-amber-400/70">{n}</p>
              ))}

              {execResult.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-400">{w}</p>
              ))}

              {/* Prompt preview (dry_run or all modes) */}
              {execResult.prompt_preview && (
                <details className="text-xs">
                  <summary className="cursor-pointer text-gray-500 hover:text-gray-400">Prompt Preview ({execResult.prompt_preview.length} chars)</summary>
                  <pre className="mt-2 whitespace-pre-wrap text-gray-400 bg-gray-800/50 rounded p-2 max-h-48 overflow-y-auto">{execResult.prompt_preview}</pre>
                </details>
              )}

              {/* Advisory result */}
              {execResult.result && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-gray-400">Advisory Output (not applied)</p>

                  {execResult.result.summary && (
                    <p className="text-xs text-gray-300 bg-gray-800/50 rounded px-2 py-1">{execResult.result.summary}</p>
                  )}

                  {execResult.result.analysis && (
                    <details className="text-xs">
                      <summary className="cursor-pointer text-gray-500 hover:text-gray-400">Analysis</summary>
                      <p className="mt-1 text-gray-400 whitespace-pre-wrap">{execResult.result.analysis}</p>
                    </details>
                  )}

                  {execResult.result.proposed_files.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Proposed Files</p>
                      <ul className="text-xs text-gray-400 space-y-0.5">
                        {execResult.result.proposed_files.map((f, i) => (
                          <li key={i} className="font-mono">{f}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {execResult.result.patch_intent && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Patch Intent</p>
                      <p className="text-xs text-gray-400 bg-gray-800/50 rounded px-2 py-1">{execResult.result.patch_intent}</p>
                    </div>
                  )}

                  {execResult.result.risks.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Risks</p>
                      <ul className="text-xs text-amber-400/70 space-y-0.5">
                        {execResult.result.risks.map((r, i) => <li key={i}>• {r}</li>)}
                      </ul>
                    </div>
                  )}

                  {execResult.result.test_suggestions.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Test Suggestions</p>
                      <ul className="text-xs text-gray-400 space-y-0.5">
                        {execResult.result.test_suggestions.map((t, i) => <li key={i}>• {t}</li>)}
                      </ul>
                    </div>
                  )}

                  {execResult.result.questions.length > 0 && (
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Open Questions</p>
                      <ul className="text-xs text-blue-400/70 space-y-0.5">
                        {execResult.result.questions.map((q, i) => <li key={i}>• {q}</li>)}
                      </ul>
                    </div>
                  )}

                  {execResult.result.recommended_next_action && (
                    <p className="text-xs text-gray-300">
                      <span className="text-gray-500">Next: </span>{execResult.result.recommended_next_action}
                    </p>
                  )}

                  {execResult.result.can_feed_patch_draft && (
                    <div className="space-y-2 mt-2">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-green-400">✓ Result can feed patch context</span>
                        <button
                          onClick={() => {
                            if (execResult.result) {
                              navigator.clipboard.writeText(
                                [
                                  execResult.result.patch_intent,
                                  "Proposed files: " + execResult.result.proposed_files.join(", "),
                                  execResult.result.analysis,
                                ].join("\n\n")
                              );
                            }
                          }}
                          className="text-xs px-2 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300"
                        >
                          Copy Patch Context
                        </button>
                        <button
                          onClick={preparePatchDraft}
                          disabled={patchDraftLoading}
                          className="text-xs px-2 py-0.5 rounded bg-indigo-800 hover:bg-indigo-700 text-indigo-100 disabled:opacity-50"
                        >
                          {patchDraftLoading ? "Preparing…" : "Prepare patch draft from agent result"}
                        </button>
                      </div>
                      {patchDraftError && (
                        <p className="text-xs text-red-400">{patchDraftError}</p>
                      )}
                      {patchDraft && (
                        <div className="border border-indigo-900/50 rounded bg-indigo-950/20 p-3 space-y-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-medium text-indigo-300">Patch Draft Context</span>
                            {patchDraft.recommended_file_path && (
                              <span className="text-xs text-gray-500 font-mono">{patchDraft.recommended_file_path}</span>
                            )}
                          </div>
                          <p className="text-xs text-amber-400/80 bg-amber-950/30 border border-amber-800/40 rounded px-2 py-1">
                            This only prepares patch context. It does not create a proposal or apply files.
                            You must run the source-of-truth guard and create a guarded proposal manually.
                          </p>
                          {patchDraft.patch_summary && (
                            <p className="text-xs text-gray-300">{patchDraft.patch_summary}</p>
                          )}
                          {patchDraft.proposed_files.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-0.5">Proposed files</p>
                              <ul className="text-xs text-gray-400 space-y-0.5">
                                {patchDraft.proposed_files.map((f, i) => (
                                  <li key={i} className="font-mono">• {f}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {patchDraft.module_context?.has_active_module_map && (
                            <div className="rounded border border-gray-800 bg-gray-950/40 p-2 space-y-1">
                              <p className="text-xs text-gray-500 mb-0.5">
                                Module map context · v{patchDraft.module_context.module_map_version ?? "?"}
                              </p>
                              {patchDraft.module_context.matched_modules.slice(0, 3).map((mod) => (
                                <div key={mod.id ?? mod.slug ?? mod.name} className="text-xs text-gray-400">
                                  <span className="text-gray-300">{mod.name ?? mod.slug}</span>
                                  {mod.slug && <span> · {mod.slug}</span>}
                                  {(mod.key_files ?? []).length > 0 && (
                                    <span> · key files: {(mod.key_files ?? []).slice(0, 3).join(", ")}</span>
                                  )}
                                </div>
                              ))}
                              {patchDraft.recommended_files_from_module_map.length > 0 && (
                                <p className="text-xs text-gray-500">
                                  Recommended files: {patchDraft.recommended_files_from_module_map.slice(0, 5).join(", ")}
                                </p>
                              )}
                              {patchDraft.module_test_hints.length > 0 && (
                                <p className="text-xs text-gray-500">
                                  Test hints: {patchDraft.module_test_hints.slice(0, 3).join(", ")}
                                </p>
                              )}
                            </div>
                          )}
                          {patchDraft.risks.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-0.5">Risks</p>
                              <ul className="text-xs text-amber-400/70 space-y-0.5">
                                {patchDraft.risks.map((r, i) => <li key={i}>• {r}</li>)}
                              </ul>
                            </div>
                          )}
                          {patchDraft.module_risks.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-0.5">Module risks</p>
                              <ul className="text-xs text-amber-400/70 space-y-0.5">
                                {patchDraft.module_risks.map((r, i) => <li key={i}>• {r}</li>)}
                              </ul>
                            </div>
                          )}
                          {patchDraft.test_suggestions.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-0.5">Test suggestions</p>
                              <ul className="text-xs text-gray-400 space-y-0.5">
                                {patchDraft.test_suggestions.map((t, i) => <li key={i}>• {t}</li>)}
                              </ul>
                            </div>
                          )}
                          {patchDraft.questions.length > 0 && (
                            <div>
                              <p className="text-xs text-gray-500 mb-0.5">Open questions</p>
                              <ul className="text-xs text-blue-400/70 space-y-0.5">
                                {patchDraft.questions.map((q, i) => <li key={i}>• {q}</li>)}
                              </ul>
                            </div>
                          )}
                          <div className="flex gap-2 pt-1">
                            <button
                              onClick={() => navigator.clipboard.writeText(patchDraft.patch_context)}
                              className="text-xs px-2 py-1 rounded bg-gray-700 hover:bg-gray-600 text-gray-300"
                            >
                              Copy patch draft context
                            </button>
                            {onPatchDraftPrefill && (
                              <button
                                onClick={useInPatchForm}
                                className="text-xs px-2 py-1 rounded bg-emerald-800 hover:bg-emerald-700 text-emerald-100"
                              >
                                Use in patch form
                              </button>
                            )}
                          </div>
                          {onPatchDraftPrefill && (
                            <p className="text-xs text-gray-600">
                              "Use in patch form" prefills the context field and file path only.
                              It does not fill old_text or new_text. Guard state will be cleared.
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Execution history */}
          {history && history.total > 0 && (
            <div className="border-t border-gray-700 pt-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-xs font-medium text-gray-500">Execution History</span>
                <button
                  onClick={loadHistory}
                  disabled={historyLoading}
                  className="text-xs px-2 py-0.5 rounded bg-gray-800 hover:bg-gray-700 text-gray-500 disabled:opacity-50"
                >
                  {historyLoading ? "…" : "Refresh"}
                </button>
              </div>
              <div className="space-y-1">
                {history.executions.slice(0, 5).map((ex, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs text-gray-500">
                    <span className="font-mono">{ex.tool_call_id.slice(0, 8)}</span>
                    <span>{ex.mode}</span>
                    <span>{ex.agent_id}</span>
                    {ex.summary && <span className="truncate max-w-xs text-gray-600">{ex.summary}</span>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Project Context Cockpit Panel ─────────────────────────────────────────────

const SEVERITY_COLORS: Record<string, string> = {
  blocked: "bg-red-950/60 border-red-700 text-red-200",
  warning: "bg-yellow-950/60 border-yellow-700 text-yellow-200",
  ready: "bg-emerald-950/60 border-emerald-700 text-emerald-200",
  info: "bg-gray-800/70 border-gray-700 text-gray-200",
};

const SEVERITY_LABELS: Record<string, string> = {
  blocked: "Blocked",
  warning: "Warning",
  ready: "Ready",
  info: "Info",
};

const COCKPIT_BADGE_COLORS: Record<string, string> = {
  positive: "border-emerald-700 bg-emerald-950/40 text-emerald-200",
  warning: "border-yellow-700 bg-yellow-950/40 text-yellow-200",
  danger: "border-red-700 bg-red-950/40 text-red-200",
  neutral: "border-gray-700 bg-gray-800/60 text-gray-300",
  info: "border-sky-800 bg-sky-950/30 text-sky-200",
};

function CockpitBadge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "positive" | "warning" | "danger" | "neutral" | "info";
}) {
  return (
    <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[11px] font-medium ${COCKPIT_BADGE_COLORS[tone]}`}>
      {children}
    </span>
  );
}

function CockpitSection({
  title,
  children,
  right,
}: {
  title: string;
  children: ReactNode;
  right?: ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-800 bg-gray-900/60 p-4 space-y-2">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

function CockpitRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-200 font-mono">{String(value)}</span>
    </div>
  );
}

function CockpitMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "positive" | "warning" | "danger" | "neutral" | "info";
}) {
  return (
    <div className={`rounded border px-3 py-2 ${COCKPIT_BADGE_COLORS[tone]}`}>
      <div className="text-[11px] uppercase tracking-wide opacity-70">{label}</div>
      <div className="text-sm font-semibold">{value}</div>
    </div>
  );
}

function CockpitChipList({
  items,
  emptyText,
  tone = "neutral",
}: {
  items: string[];
  emptyText: string;
  tone?: "positive" | "warning" | "danger" | "neutral" | "info";
}) {
  if (!items.length) {
    return <p className="text-xs text-gray-500">{emptyText}</p>;
  }
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((item) => (
        <CockpitBadge key={item} tone={tone}>{item}</CockpitBadge>
      ))}
    </div>
  );
}

function ProjectCockpitPanel({
  runId,
  cockpitData,
  cockpitLoading,
  cockpitError,
  onLoad,
}: {
  runId: string;
  cockpitData: import("../types").ProjectContextCockpitSummary | null;
  cockpitLoading: boolean;
  cockpitError: string;
  onLoad: () => void;
}) {
  useEffect(() => {
    if (!cockpitData && !cockpitLoading) {
      onLoad();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  const sourceTone = cockpitData?.source_of_truth.available ? "positive" : "warning";
  const moduleMapTone = cockpitData?.module_map.available ? "positive" : "warning";
  const hasRunBlockers = Boolean(
    cockpitData &&
      (cockpitData.run.pending_approval_count > 0 ||
        cockpitData.run.guard_blocker_count > 0 ||
        cockpitData.run.tests_failed_count > 0)
  );
  const hasModuleAwareness = Boolean(
    cockpitData &&
      (cockpitData.module_awareness.touched_modules.length > 0 ||
        cockpitData.module_awareness.expected_modules.length > 0 ||
        cockpitData.module_awareness.blocked_policy_count > 0 ||
        cockpitData.module_awareness.warning_count > 0 ||
        cockpitData.module_awareness.recommended_tests.length > 0)
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-300">Context Cockpit</h2>
          <p className="text-xs text-gray-500">Read-only project context and next-step orientation.</p>
        </div>
        <button
          onClick={onLoad}
          disabled={cockpitLoading}
          className="text-xs px-3 py-1 rounded bg-gray-800 text-gray-400 hover:bg-gray-700 disabled:opacity-50"
        >
          {cockpitLoading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {cockpitError && (
        <div className="rounded border border-red-800 bg-red-900/30 px-3 py-2 text-sm text-red-300">
          {cockpitError}
        </div>
      )}

      {cockpitLoading && !cockpitData && (
        <div className="text-sm text-gray-500 py-4 text-center">Loading cockpit…</div>
      )}

      {cockpitData && (
        <div className="space-y-3">
          {/* Next Safest Action */}
          {cockpitData.next_action.label && (
            <div className={`rounded-lg border px-4 py-4 ${SEVERITY_COLORS[cockpitData.next_action.severity] ?? SEVERITY_COLORS.info}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="text-xs font-semibold uppercase tracking-wide opacity-70">
                  Next Safest Action
                </div>
                <CockpitBadge
                  tone={
                    cockpitData.next_action.severity === "blocked"
                      ? "danger"
                      : cockpitData.next_action.severity === "warning"
                        ? "warning"
                        : cockpitData.next_action.severity === "ready"
                          ? "positive"
                          : "neutral"
                  }
                >
                  {SEVERITY_LABELS[cockpitData.next_action.severity] ?? "Info"}
                </CockpitBadge>
              </div>
              <div className="mt-2 text-lg font-semibold">{cockpitData.next_action.label}</div>
              {cockpitData.next_action.reason && (
                <div className="text-xs opacity-75 mt-1">{cockpitData.next_action.reason}</div>
              )}
              {cockpitData.next_action.target_panel && (
                <div className="mt-3 text-xs opacity-80">
                  Look next: <span className="font-mono">{cockpitData.next_action.target_panel}</span>. Open the related tab manually.
                </div>
              )}
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-2">
            {/* Source of Truth */}
            <CockpitSection
              title="Source of Truth"
              right={<CockpitBadge tone={sourceTone}>{cockpitData.source_of_truth.available ? "Available" : "Missing"}</CockpitBadge>}
            >
              {!cockpitData.source_of_truth.available ? (
                <p className="text-xs text-yellow-300">No active Source of Truth. Add one in the Spec tab before relying on requirement coverage.</p>
              ) : (
                <>
                  {cockpitData.source_of_truth.product_name && (
                    <CockpitRow label="Product" value={cockpitData.source_of_truth.product_name} />
                  )}
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                    <CockpitMetric label="Version" value={cockpitData.source_of_truth.version != null ? `v${cockpitData.source_of_truth.version}` : "n/a"} tone="info" />
                    <CockpitMetric label="Requirements" value={cockpitData.source_of_truth.requirement_count} tone="positive" />
                    <CockpitMetric label="Risks" value={cockpitData.source_of_truth.risk_count} tone={cockpitData.source_of_truth.risk_count > 0 ? "warning" : "neutral"} />
                    <CockpitMetric label="Questions" value={cockpitData.source_of_truth.open_question_count} tone={cockpitData.source_of_truth.open_question_count > 0 ? "warning" : "neutral"} />
                  </div>
                </>
              )}
            </CockpitSection>

            {/* Module Map */}
            <CockpitSection
              title="Module Map"
              right={<CockpitBadge tone={moduleMapTone}>{cockpitData.module_map.available ? "Available" : "Missing"}</CockpitBadge>}
            >
              {!cockpitData.module_map.available ? (
                <p className="text-xs text-yellow-300">No active Module Map. Module-aware hints and reporting will stay sparse until one exists.</p>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-2">
                    <CockpitMetric label="Version" value={cockpitData.module_map.version != null ? `v${cockpitData.module_map.version}` : "n/a"} tone="info" />
                    <CockpitMetric label="Modules" value={cockpitData.module_map.module_count} tone="positive" />
                  </div>
                  <div className="space-y-1 pt-1">
                    <div className="text-xs text-gray-500">Key modules</div>
                    <CockpitChipList
                      items={cockpitData.module_map.key_modules}
                      emptyText="No key modules listed."
                      tone="info"
                    />
                  </div>
                </>
              )}
            </CockpitSection>
          </div>

          {/* Delivery Status */}
          <CockpitSection
            title="Delivery Status"
            right={<CockpitBadge tone={hasRunBlockers ? "danger" : cockpitData.run.readiness === "ready_for_review" ? "positive" : "neutral"}>{cockpitData.run.readiness}</CockpitBadge>}
          >
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <CockpitMetric
                label="Steps"
                value={`${cockpitData.run.completed_steps}/${cockpitData.run.total_steps}`}
                tone="info"
              />
              <CockpitMetric
                label="Approvals"
                value={cockpitData.run.pending_approval_count}
                tone={cockpitData.run.pending_approval_count > 0 ? "warning" : "positive"}
              />
              <CockpitMetric
                label="Guard blockers"
                value={cockpitData.run.guard_blocker_count}
                tone={cockpitData.run.guard_blocker_count > 0 ? "danger" : "positive"}
              />
              <CockpitMetric
                label="Failed tests"
                value={cockpitData.run.tests_failed_count}
                tone={cockpitData.run.tests_failed_count > 0 ? "danger" : "positive"}
              />
              <CockpitMetric
                label="Blockers"
                value={hasRunBlockers ? "Review" : "None"}
                tone={hasRunBlockers ? "danger" : "positive"}
              />
            </div>
            {!hasRunBlockers && (
              <p className="text-xs text-emerald-300">No cockpit-visible blockers.</p>
            )}
          </CockpitSection>

          {/* Module Awareness */}
          <CockpitSection
            title="Module Awareness"
            right={<CockpitBadge tone={cockpitData.module_awareness.blocked_policy_count > 0 ? "warning" : "neutral"}>Classification-only</CockpitBadge>}
          >
            {!hasModuleAwareness ? (
              <p className="text-xs text-gray-500">No module awareness data recorded for this run yet.</p>
            ) : (
              <div className="grid gap-3 lg:grid-cols-2">
                <div className="space-y-1">
                  <div className="text-xs text-gray-500">Touched modules</div>
                  <CockpitChipList
                    items={cockpitData.module_awareness.touched_modules}
                    emptyText="No touched modules recorded."
                    tone="info"
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-gray-500">Expected modules</div>
                  <CockpitChipList
                    items={cockpitData.module_awareness.expected_modules}
                    emptyText="No expected modules recorded."
                    tone="neutral"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <CockpitMetric
                    label="Policy warnings"
                    value={cockpitData.module_awareness.warning_count}
                    tone={cockpitData.module_awareness.warning_count > 0 ? "warning" : "positive"}
                  />
                  <CockpitMetric
                    label="Blocked verdicts"
                    value={cockpitData.module_awareness.blocked_policy_count}
                    tone={cockpitData.module_awareness.blocked_policy_count > 0 ? "warning" : "positive"}
                  />
                </div>
                <div className="space-y-1">
                  <div className="text-xs text-gray-500">Recommended module tests</div>
                  <CockpitChipList
                    items={cockpitData.module_awareness.recommended_tests}
                    emptyText="No recommended module tests yet."
                    tone="positive"
                  />
                </div>
                <p className="text-xs text-gray-500 lg:col-span-2">
                  Module policy is report/classification-only here. It does not enforce proposal, apply, test, or approval behavior.
                </p>
              </div>
            )}
          </CockpitSection>

          {/* Safety Notes */}
          {cockpitData.safety_notes.length > 0 && (
            <CockpitSection title="Safety Notes">
              {cockpitData.safety_notes.map((note, i) => (
                <div key={i} className="text-xs text-yellow-400">{note}</div>
              ))}
            </CockpitSection>
          )}
        </div>
      )}
    </div>
  );
}

// ── Delivery Panel ────────────────────────────────────────────────────────────

function DeliveryPanel({ runId }: { runId: string }) {
  const [summary, setSummary] = useState<import("../types").RunDeliverySummary | null>(null);
  const [report, setReport] = useState<import("../types").DeliveryReportResponse | null>(null);
  const [loading, setLoading] = useState<"" | "summary" | "report">("");
  const [error, setError] = useState("");
  const [showMarkdown, setShowMarkdown] = useState(false);

  const loadSummary = async () => {
    setLoading("summary");
    setError("");
    setReport(null);
    try {
      const s = await getRunDeliverySummary(runId);
      setSummary(s);
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const loadReport = async () => {
    setLoading("report");
    setError("");
    try {
      const r = await generateRunDeliveryReport(runId, {
        include_markdown: true,
        include_step_details: true,
        max_markdown_chars: 30000,
      });
      setReport(r);
      setSummary(r.summary);
      setShowMarkdown(true);
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const readinessColor = (r: string) => {
    if (r === "ready_for_review") return "text-emerald-400";
    if (r === "delivered_with_warnings") return "text-yellow-300";
    if (r === "blocked" || r === "tests_failed") return "text-red-400";
    if (r === "awaiting_approval") return "text-purple-400";
    if (r === "needs_tests") return "text-orange-400";
    if (r === "in_progress") return "text-blue-400";
    return "text-gray-400";
  };

  const copyMarkdown = () => {
    if (report?.markdown_report) {
      navigator.clipboard.writeText(report.markdown_report).catch(() => {});
    }
  };

  return (
    <div className="space-y-4 p-4">
      {/* Safety note */}
      <p className="text-xs text-amber-400/80 bg-amber-900/20 border border-amber-900/40 rounded px-3 py-2">
        Delivery summary is read-only — no file mutations, commands, providers, or approvals are triggered.
      </p>

      {/* Buttons */}
      <div className="flex gap-2">
        <button
          onClick={loadSummary}
          disabled={loading !== ""}
          className="px-3 py-1.5 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 disabled:opacity-50"
        >
          {loading === "summary" ? "Loading…" : "Refresh delivery summary"}
        </button>
        <button
          onClick={loadReport}
          disabled={loading !== ""}
          className="px-3 py-1.5 rounded text-xs bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-50"
        >
          {loading === "report" ? "Generating…" : "Generate delivery report"}
        </button>
      </div>

      {error && <p className="text-xs text-red-400">{error}</p>}

      {/* Summary */}
      {summary && (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">Readiness:</span>
            <span className={`text-sm font-semibold font-mono ${readinessColor(summary.readiness)}`}>
              {summary.readiness}
            </span>
          </div>

          {/* Counts */}
          <div className="grid grid-cols-3 gap-2 text-xs">
            <div className="bg-gray-800 rounded p-2">
              <p className="text-gray-500">Total steps</p>
              <p className="font-mono text-gray-200">{summary.total_steps}</p>
            </div>
            <div className="bg-gray-800 rounded p-2">
              <p className="text-emerald-600">Ready</p>
              <p className="font-mono text-emerald-400">{summary.ready_steps}</p>
            </div>
            <div className="bg-gray-800 rounded p-2">
              <p className="text-red-600">Blocked</p>
              <p className="font-mono text-red-400">{summary.blocked_steps}</p>
            </div>
            <div className="bg-gray-800 rounded p-2">
              <p className="text-orange-600">Needs tests</p>
              <p className="font-mono text-orange-400">{summary.needs_test_steps}</p>
            </div>
            <div className="bg-gray-800 rounded p-2">
              <p className="text-red-600">Failed tests</p>
              <p className="font-mono text-red-400">{summary.failed_test_steps}</p>
            </div>
            <div className="bg-gray-800 rounded p-2">
              <p className="text-purple-500">Awaiting approval</p>
              <p className="font-mono text-purple-400">{summary.approval_pending_steps}</p>
            </div>
          </div>

          {/* Approval pending warning */}
          {summary.approval_pending_steps > 0 && (
            <div className="text-xs bg-purple-900/20 border border-purple-800/40 rounded px-3 py-2">
              <p className="text-purple-300 font-semibold mb-0.5">
                ⏳ {summary.approval_pending_steps} step{summary.approval_pending_steps !== 1 ? "s" : ""} awaiting approval
              </p>
              <p className="text-purple-400/70">
                Navigate to the Automation Approvals tab to review and execute pending approvals.
              </p>
            </div>
          )}

          {/* Recommended action */}
          {summary.recommended_next_action && (
            <p className="text-xs text-amber-300 bg-amber-900/20 rounded px-2 py-1">
              → {summary.recommended_next_action}
            </p>
          )}

          {/* Module awareness */}
          {summary.module_summary?.has_module_data && (
            <div className="space-y-2 rounded border border-sky-900 bg-sky-950/20 p-3 text-xs">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-sky-300">Module awareness</span>
                <span className="text-gray-500">warnings: {summary.module_summary.warning_count}</span>
                <span className="text-gray-500">blocked policy: {summary.module_summary.blocked_policy_count}</span>
              </div>
              {summary.module_summary.touched_modules.length > 0 && (
                <p className="text-gray-300">
                  <span className="text-gray-500">Touched:</span> {summary.module_summary.touched_modules.join(", ")}
                </p>
              )}
              {summary.module_summary.expected_modules.length > 0 && (
                <p className="text-gray-300">
                  <span className="text-gray-500">Expected:</span> {summary.module_summary.expected_modules.join(", ")}
                </p>
              )}
              {summary.module_summary.sensitive_modules.length > 0 && (
                <p className="text-orange-300">
                  <span className="text-gray-500">Sensitive:</span> {summary.module_summary.sensitive_modules.join(", ")}
                </p>
              )}
              {summary.module_summary.recommended_tests.length > 0 && (
                <p className="text-emerald-300">
                  <span className="text-gray-500">Recommended tests:</span> {summary.module_summary.recommended_tests.join("; ")}
                </p>
              )}
            </div>
          )}

          {/* Changed files */}
          {summary.changed_files.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Changed files ({summary.changed_files.length}):</p>
              <ul className="space-y-0.5 max-h-32 overflow-y-auto">
                {summary.changed_files.map((f, i) => (
                  <li key={i} className="text-xs text-gray-400 font-mono">• {f}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Requirement IDs */}
          {summary.requirement_ids.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-1">Requirement IDs:</p>
              <p className="text-xs text-gray-400 font-mono">{summary.requirement_ids.join(", ")}</p>
            </div>
          )}

          {/* Unresolved issues */}
          {summary.unresolved_issues.length > 0 && (
            <div>
              <p className="text-xs text-red-400 font-semibold mb-1">Unresolved issues:</p>
              <ul className="space-y-0.5">
                {summary.unresolved_issues.slice(0, 8).map((i, idx) => (
                  <li key={idx} className="text-xs text-red-300">• {i}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Warnings */}
          {summary.warnings.length > 0 && (
            <div>
              <p className="text-xs text-amber-400 font-semibold mb-1">Warnings:</p>
              <ul className="space-y-0.5">
                {summary.warnings.slice(0, 6).map((w, i) => (
                  <li key={i} className="text-xs text-amber-300/80">• {w}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Per-step cards */}
      {report && report.steps.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 font-semibold mb-2">Step details:</p>
          <div className="space-y-2">
            {report.steps.map(s => (
              <div key={s.step_id} className="border border-gray-700 rounded px-3 py-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium text-gray-300 truncate">{s.step_title || s.step_id}</span>
                  <span className={`text-xs font-mono ml-auto ${readinessColor(s.readiness)}`}>{s.readiness}</span>
                </div>
                <div className="text-xs text-gray-500 flex gap-3 flex-wrap">
                  <span>Guard: <span className="text-gray-400">{s.guard_status}</span></span>
                  <span>Proposal: <span className="text-gray-400">{s.proposal_status}</span></span>
                  <span>Apply: <span className="text-gray-400">{s.apply_status}</span></span>
                  <span>Tests: <span className="text-gray-400">{s.test_status}</span></span>
                  <span>Approval: <span className={s.approval_status === "pending" ? "text-purple-400" : "text-gray-400"}>{s.approval_status}</span></span>
                </div>
                {s.changed_files.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1">Files: {s.changed_files.slice(0, 5).join(", ")}</p>
                )}
                {s.recommended_next_action && (
                  <p className="text-xs text-amber-400/70 mt-1">→ {s.recommended_next_action}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Markdown report */}
      {report && report.markdown_report && (
        <div>
          <div className="flex items-center gap-2 mb-2">
            <button
              onClick={() => setShowMarkdown(v => !v)}
              className="text-xs text-gray-400 hover:text-gray-200"
            >
              {showMarkdown ? "▼ Hide report" : "▶ Show report"}
            </button>
            <button
              onClick={copyMarkdown}
              className="text-xs text-indigo-400 hover:text-indigo-300"
            >
              Copy markdown
            </button>
          </div>
          {showMarkdown && (
            <pre className="text-xs text-gray-300 bg-gray-900 rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap font-mono">
              {report.markdown_report}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// ── Bounded Loop Panel ────────────────────────────────────────────────────────

function BoundedLoopPanel({ runId }: { runId: string }) {
  const [maxIterations, setMaxIterations] = useState(3);
  const [maxActionsPerIteration, setMaxActionsPerIteration] = useState(5);
  const [dryRun, setDryRun] = useState(false);
  const [allowSafeCommands, setAllowSafeCommands] = useState(false);
  const [allowProviderCall, setAllowProviderCall] = useState(false);
  const [allowLowRiskToolCalls, setAllowLowRiskToolCalls] = useState(true);
  const [stopOnApprovalRequired, setStopOnApprovalRequired] = useState(true);
  const [stopOnBlocked, setStopOnBlocked] = useState(true);
  const [stopOnTestFailure, setStopOnTestFailure] = useState(false);
  const [result, setResult] = useState<import("../types").BoundedAutonomousLoopResponse | null>(null);
  const [loading, setLoading] = useState<"" | "dry" | "run">("");
  const [error, setError] = useState("");

  const runLoop = async (isDry: boolean) => {
    setLoading(isDry ? "dry" : "run");
    setError("");
    setResult(null);
    try {
      const res = await runBoundedLoop(runId, {
        max_iterations: maxIterations,
        max_actions_per_iteration: maxActionsPerIteration,
        dry_run: isDry,
        allow_provider_call: allowProviderCall,
        allow_safe_commands: allowSafeCommands,
        allow_low_risk_tool_calls: allowLowRiskToolCalls,
        stop_on_approval_required: stopOnApprovalRequired,
        stop_on_blocked: stopOnBlocked,
        stop_on_test_failure: stopOnTestFailure,
      });
      setResult(res);
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const statusColor = (s: string) => {
    if (s === "completed") return "text-emerald-400";
    if (s === "stopped_for_approval" || s === "max_iterations_reached") return "text-yellow-400";
    if (s === "blocked" || s === "failed") return "text-red-400";
    if (s === "no_safe_action") return "text-gray-400";
    return "text-gray-300";
  };

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden mt-4">
      <div className="px-4 py-3 bg-gray-800/50">
        <span className="font-medium text-gray-200 text-sm">Bounded Loop</span>
        <span className="ml-2 text-xs text-gray-500">bounded orchestration — stops before destructive actions</span>
      </div>
      <div className="p-4 space-y-3">
        {/* Safety note */}
        <p className="text-xs text-amber-400/80 bg-amber-900/20 border border-amber-900/40 rounded px-3 py-2">
          Bounded Loop never bypasses guard, approval, safe-command policy, or current-state revalidation. It stops before destructive actions unless an approved action exists.
        </p>

        {/* Controls */}
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-gray-400 flex flex-col gap-1">
            Max iterations
            <select
              value={maxIterations}
              onChange={e => setMaxIterations(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200 text-xs"
            >
              {[1,2,3,5,10].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-400 flex flex-col gap-1">
            Max actions / iteration
            <select
              value={maxActionsPerIteration}
              onChange={e => setMaxActionsPerIteration(Number(e.target.value))}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-200 text-xs"
            >
              {[1,2,3,5,10].map(n => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        </div>

        {/* Checkboxes */}
        <div className="space-y-1">
          {([
            ["Dry run", dryRun, setDryRun],
            ["Allow safe commands", allowSafeCommands, setAllowSafeCommands],
            ["Allow provider call", allowProviderCall, setAllowProviderCall],
            ["Allow low-risk tool calls", allowLowRiskToolCalls, setAllowLowRiskToolCalls],
            ["Stop on approval required", stopOnApprovalRequired, setStopOnApprovalRequired],
            ["Stop on blocked", stopOnBlocked, setStopOnBlocked],
            ["Stop on test failure", stopOnTestFailure, setStopOnTestFailure],
          ] as [string, boolean, (v: boolean) => void][]).map(([label, val, setter]) => (
            <label key={label} className="flex items-center gap-2 text-xs text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={val}
                onChange={e => setter(e.target.checked)}
                className="accent-indigo-500"
              />
              {label}
            </label>
          ))}
        </div>

        {/* Buttons */}
        <div className="flex gap-2">
          <button
            onClick={() => runLoop(true)}
            disabled={loading !== ""}
            className="px-3 py-1.5 rounded text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 disabled:opacity-50"
          >
            {loading === "dry" ? "Running…" : "Dry run bounded loop"}
          </button>
          <button
            onClick={() => runLoop(false)}
            disabled={loading !== ""}
            className="px-3 py-1.5 rounded text-xs bg-indigo-700 hover:bg-indigo-600 text-white disabled:opacity-50"
          >
            {loading === "run" ? "Running…" : "Run bounded loop"}
          </button>
        </div>

        {error && <p className="text-xs text-red-400">{error}</p>}

        {/* Result */}
        {result && (
          <div className="space-y-2 mt-2">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-gray-500">Status:</span>
              <span className={`text-xs font-mono font-semibold ${statusColor(result.status)}`}>{result.status}</span>
              {result.stop_reason && result.stop_reason !== result.status && (
                <span className="text-xs text-gray-500">({result.stop_reason})</span>
              )}
              {result.dry_run && <span className="text-xs text-gray-500">(dry run)</span>}
            </div>

            {/* Stop-reason guidance block */}
            {result.status === "stopped_for_approval" && (
              <div className="rounded border border-yellow-800/60 bg-yellow-900/20 px-3 py-2 space-y-1">
                {result.stop_reason === "pending_approval" && (
                  <>
                    <p className="text-xs text-yellow-300 font-semibold">⏳ Pending approval — human review required</p>
                    <p className="text-xs text-yellow-200/80">
                      {result.pending_approval_action_type
                        ? `Action '${result.pending_approval_action_type}' has a pending approval. Open the Automation Approvals panel, review and approve it to allow the loop to continue.`
                        : "An approval is pending. Review it in the Automation Approvals panel before re-running the loop."}
                    </p>
                    {result.pending_approval_id && (
                      <p className="text-xs text-gray-500 font-mono">Approval ID: {result.pending_approval_id.slice(0, 12)}…</p>
                    )}
                  </>
                )}
                {result.stop_reason === "needs_approval" && (
                  <>
                    <p className="text-xs text-yellow-300 font-semibold">🔐 Approval required — create one to proceed</p>
                    <p className="text-xs text-yellow-200/80">
                      {result.pending_approval_action_type
                        ? `Action '${result.pending_approval_action_type}' requires an automation approval. Create one in the Automation Approvals panel, then re-run the loop.`
                        : "A manual action requires an approval. Create one in the Automation Approvals panel."}
                    </p>
                  </>
                )}
                {result.stop_reason === "test_failed" && (
                  <>
                    <p className="text-xs text-yellow-300 font-semibold">❌ Tests failed — loop stopped (stop_on_test_failure)</p>
                    <p className="text-xs text-yellow-200/80">Tests ran and failed. Review the failure output in the Patch-Test Lifecycle panel before continuing.</p>
                  </>
                )}
              </div>
            )}

            {result.status === "blocked" && result.blocked_action_type && (
              <div className="rounded border border-red-800/60 bg-red-900/20 px-3 py-2">
                <p className="text-xs text-red-300 font-semibold">🚫 Blocked guard</p>
                <p className="text-xs text-red-200/80">Action <span className="font-mono">{result.blocked_action_type}</span> is blocked by a guard result. Resolve the guard before re-running.</p>
              </div>
            )}

            {result.final_recommended_action && (
              <p className="text-xs text-amber-300 bg-amber-900/20 rounded px-2 py-1">
                → {result.final_recommended_action}
              </p>
            )}

            {result.approvals_required.length > 0 && (
              <div>
                <p className="text-xs text-yellow-400 font-semibold mb-1">Approvals required:</p>
                <ul className="space-y-0.5">
                  {result.approvals_required.map((a, i) => (
                    <li key={i} className="text-xs text-yellow-300 font-mono">• {a}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Iterations */}
            <div className="space-y-1">
              {result.iterations.map(iter => (
                <div key={iter.iteration} className="border border-gray-700 rounded px-3 py-2 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-500">#{iter.iteration}</span>
                    <span className="text-xs font-mono text-gray-300">{iter.queue_action || "—"}</span>
                    <span className={`text-xs font-mono ml-auto ${statusColor(iter.status)}`}>{iter.status}</span>
                  </div>
                  {iter.executed_actions.length > 0 && (
                    <div className="space-y-0.5">
                      {iter.executed_actions.map((a, i) => (
                        <p key={i} className="text-xs text-gray-400 font-mono">
                          ✓ {a.action_type} → <span className={a.status === "executed" ? "text-emerald-400" : "text-yellow-400"}>{a.status}</span>
                          {a.result_summary && <span className="text-gray-500"> — {a.result_summary}</span>}
                        </p>
                      ))}
                    </div>
                  )}
                  {iter.blocked_reasons.length > 0 && (
                    <p className="text-xs text-red-400">{iter.blocked_reasons.join("; ")}</p>
                  )}
                  {iter.test_status && (
                    <p className={`text-xs font-mono ${iter.test_status === "passed" ? "text-emerald-400" : "text-red-400"}`}>
                      Tests: {iter.test_status}
                    </p>
                  )}
                  {iter.approvals_required.length > 0 && (
                    <p className="text-xs text-yellow-400">Approval required: {iter.approvals_required.join(", ")}</p>
                  )}
                  {iter.warnings.map((w, i) => (
                    <p key={i} className="text-xs text-amber-400/70">{w}</p>
                  ))}
                </div>
              ))}
            </div>

            {/* Final queue summary */}
            {result.final_queue_summary && (
              <div className="text-xs text-gray-500 flex gap-3 flex-wrap">
                <span>Total: {result.final_queue_summary.total_items}</span>
                <span className="text-emerald-500">Ready: {result.final_queue_summary.ready_items}</span>
                <span className="text-yellow-500">Manual: {result.final_queue_summary.manual_required_items}</span>
                <span className="text-red-500">Blocked: {result.final_queue_summary.blocked_items}</span>
                <span className="text-gray-400">Done: {result.final_queue_summary.done_items}</span>
              </div>
            )}

            {result.warnings.length > 0 && (
              <div className="space-y-0.5">
                {result.warnings.map((w, i) => <p key={i} className="text-xs text-amber-400/80">{w}</p>)}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}


function OperatorQueuePanel({
  runId,
  queue,
  loading,
  error,
  onRefresh,
  onFocusManualAction,
  steps,
  onAgentPrefill,
}: {
  runId: string;
  queue: OperatorQueueResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
  onFocusManualAction: (stepId: string, actionType: string) => Promise<{ message: string; error?: string }>;
  steps?: RunStep[];
  onAgentPrefill?: (stepId: string, prefill: IssuePrefill) => void;
}) {
  const [automationResult, setAutomationResult] = useState<AutomationRunResponse | null>(null);
  const [automationLoading, setAutomationLoading] = useState<"" | "dry" | "next" | "loop">("");
  const [automationError, setAutomationError] = useState("");
  const [maxActions, setMaxActions] = useState(3);
  const [agentHarnessStepId, setAgentHarnessStepId] = useState<string>("");
  const [allowSafeCommands, setAllowSafeCommands] = useState(false);
  const [allowLowRiskToolCalls, setAllowLowRiskToolCalls] = useState(true);

  const runAutomation = async (mode: "dry" | "next" | "loop") => {
    setAutomationLoading(mode);
    setAutomationError("");
    setAutomationResult(null);
    try {
      const payload = {
        dry_run: mode === "dry",
        max_actions: mode === "loop" ? maxActions : 1,
        allow_safe_commands: allowSafeCommands,
        allow_low_risk_tool_calls: allowLowRiskToolCalls,
      };
      const result = mode === "loop"
        ? await runAutomationSafeLoop(runId, payload)
        : await runAutomationNext(runId, payload);
      setAutomationResult(result);
      await onRefresh();
    } catch (e: any) {
      setAutomationError(readableError(e));
    } finally {
      setAutomationLoading("");
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Operator Queue</h3>
          <p className="text-xs text-gray-500 mt-0.5">
            Read-only guidance — shows the next safe manual action per step. No action is executed automatically.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="px-3 py-1.5 rounded text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh Queue"}
        </button>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h4 className="text-sm font-medium text-gray-200">Automation Runner v1</h4>
            <p className="mt-1 text-xs text-gray-500">
              Automation Runner v1 never applies patches, rolls back, creates proposals, runs arbitrary commands, or calls providers.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => runAutomation("dry")}
              disabled={automationLoading !== ""}
              className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:text-gray-600"
            >
              {automationLoading === "dry" ? "Checking..." : "Dry run next safe action"}
            </button>
            <button
              onClick={() => runAutomation("next")}
              disabled={automationLoading !== ""}
              className="rounded bg-emerald-800 px-3 py-1.5 text-xs text-emerald-100 hover:bg-emerald-700 disabled:bg-gray-800 disabled:text-gray-600"
            >
              {automationLoading === "next" ? "Running..." : "Run next safe action"}
            </button>
            <button
              onClick={() => runAutomation("loop")}
              disabled={automationLoading !== ""}
              className="rounded bg-blue-800 px-3 py-1.5 text-xs text-blue-100 hover:bg-blue-700 disabled:bg-gray-800 disabled:text-gray-600"
            >
              {automationLoading === "loop" ? "Running..." : "Run safe loop"}
            </button>
          </div>
        </div>
        <div className="mt-3 flex flex-wrap gap-4 text-xs text-gray-400">
          <label className="flex items-center gap-2">
            Max actions
            <input
              type="number"
              min={1}
              max={10}
              value={maxActions}
              onChange={(event) => setMaxActions(Math.max(1, Math.min(10, Number(event.target.value) || 1)))}
              className="w-16 rounded border border-gray-700 bg-gray-900 px-2 py-1 text-gray-200"
            />
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={allowSafeCommands}
              onChange={(event) => setAllowSafeCommands(event.target.checked)}
            />
            Allow safe test commands
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={allowLowRiskToolCalls}
              onChange={(event) => setAllowLowRiskToolCalls(event.target.checked)}
            />
            Allow low-risk tool calls
          </label>
        </div>
        {automationError && (
          <div className="mt-3 rounded border border-red-800 bg-red-950/30 px-3 py-2 text-xs text-red-300">{automationError}</div>
        )}
        {automationResult && (
          <div className="mt-3 space-y-2 rounded border border-gray-800 bg-gray-900 p-3 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">status: {automationResult.status}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-400">executed: {automationResult.executed_actions.length}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-400">skipped: {automationResult.skipped_actions.length}</span>
            </div>
            {[...automationResult.executed_actions, ...automationResult.skipped_actions].map((action, index) => (
              <div key={`${action.action_type}-${index}`} className="rounded bg-gray-950 px-2 py-1.5">
                <div className="flex flex-wrap gap-2">
                  <span className="font-mono text-gray-300">{action.action_type}</span>
                  <span className="text-gray-500">{action.status}</span>
                  {action.created_tool_call_id && <span className="font-mono text-emerald-400">tool_call: {shortId(action.created_tool_call_id)}</span>}
                </div>
                <p className="mt-1 text-gray-500">{action.reason}</p>
                {action.result_summary && <p className="mt-1 text-gray-400">{action.result_summary}</p>}
              </div>
            ))}
            {automationResult.safety_notes.length > 0 && (
              <ul className="space-y-1 border-t border-gray-800 pt-2 text-gray-600">
                {automationResult.safety_notes.map((note) => <li key={note}>{note}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-900/20 px-3 py-2 text-sm text-red-300">{error}</div>
      )}

      {!queue && !loading && !error && (
        <div className="text-sm text-gray-500 text-center py-8">
          Click "Refresh Queue" to load operator guidance for this run.
        </div>
      )}

      {queue && (
        <>
          {/* ── Operator Cockpit Block ── */}
          {queue.items.length > 0 && (() => {
            const top = queue.items[0];
            const isApproval = top.action_type === "execute_approval";
            const isBlocked = top.status === "blocked";
            const isHigh = top.priority === "high";
            const borderColor = isBlocked
              ? "border-red-800/60"
              : isApproval
                ? "border-purple-800/60"
                : isHigh
                  ? "border-amber-800/60"
                  : "border-gray-700";
            const bgColor = isBlocked
              ? "bg-red-900/10"
              : isApproval
                ? "bg-purple-900/10"
                : isHigh
                  ? "bg-amber-900/10"
                  : "bg-gray-900";
            const accentColor = isBlocked
              ? "text-red-400"
              : isApproval
                ? "text-purple-300"
                : isHigh
                  ? "text-amber-300"
                  : "text-gray-300";
            return (
              <div className={`rounded border ${borderColor} ${bgColor} p-4 space-y-2`}>
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Current Operator Action</span>
                    <h4 className={`text-sm font-semibold mt-0.5 ${accentColor}`}>{top.title}</h4>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                      top.priority === "high" ? "bg-red-900/40 text-red-300" :
                      top.priority === "medium" ? "bg-yellow-900/40 text-yellow-300" :
                      "bg-gray-800 text-gray-400"
                    }`}>{top.priority}</span>
                    <span className="text-xs text-gray-500 font-mono">{top.action_type}</span>
                  </div>
                </div>
                <p className="text-xs text-gray-400">{top.description}</p>
                <p className="text-xs text-gray-600 italic">{top.step_title}</p>
                {isApproval && top.approval_id && (
                  <div className="rounded border border-purple-900/50 bg-purple-950/30 px-3 py-2 space-y-1">
                    <p className="text-xs text-purple-300 font-semibold">⏳ Pending approval — review in Automation Approvals panel below</p>
                    <p className="text-xs text-purple-200/70">Action: <span className="font-mono">{top.approval_action_type}</span></p>
                    <p className="text-xs text-gray-600 font-mono">ID: {top.approval_id.slice(0, 12)}…</p>
                  </div>
                )}
                {top.warnings.length > 0 && (
                  <ul className="space-y-0.5">
                    {top.warnings.map((w, i) => (
                      <li key={i} className="text-xs text-amber-400/70">⚠ {w}</li>
                    ))}
                  </ul>
                )}
                <p className="text-xs text-gray-600">Destination: <span className="font-mono">{top.destination}</span>{top.requires_confirmation ? " · confirmation required" : ""}{top.is_destructive ? " · destructive" : ""}</p>
              </div>
            );
          })()}

          <div className="flex flex-wrap gap-3 text-xs">
            <span className="px-2 py-1 rounded bg-gray-800 text-gray-400">
              Total: <strong>{queue.summary.total_items}</strong>
            </span>
            <span className="px-2 py-1 rounded bg-emerald-900/30 text-emerald-400">
              Ready: <strong>{queue.summary.ready_items}</strong>
            </span>
            <span className="px-2 py-1 rounded bg-orange-900/30 text-orange-400">
              Manual required: <strong>{queue.summary.manual_required_items}</strong>
            </span>
            <span className="px-2 py-1 rounded bg-red-900/30 text-red-400">
              Blocked: <strong>{queue.summary.blocked_items}</strong>
            </span>
            <span className="px-2 py-1 rounded bg-gray-800 text-gray-500">
              Done: <strong>{queue.summary.done_items}</strong>
            </span>
          </div>

          {queue.items.length === 0 ? (
            <div className="text-sm text-gray-500 text-center py-8">
              No actionable items found for this run.
            </div>
          ) : (
            <div className="space-y-3">
              {queue.items.map((item) => (
                <OperatorQueueItemCard
                  key={item.id}
                  item={item}
                  onFocus={onFocusManualAction}
                />
              ))}
            </div>
          )}

          <div className="text-xs text-gray-600 pt-2">
            Generated at {new Date(queue.generated_at).toLocaleTimeString()} — refresh to update.
          </div>
        </>
      )}

      <AutomationApprovalPanel runId={runId} queue={queue} />

      {/* Agent Execution Harness */}
      {steps && steps.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500 font-medium">Agent Execution — Step:</span>
            <select
              value={agentHarnessStepId}
              onChange={(e) => setAgentHarnessStepId(e.target.value)}
              className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300"
            >
              <option value="">Select a step…</option>
              {steps.map((s) => (
                <option key={s.id} value={s.id}>{s.title || s.id}</option>
              ))}
            </select>
          </div>
          <AgentExecutionPanel
            runId={runId}
            stepId={agentHarnessStepId || null}
            onPatchDraftPrefill={onAgentPrefill}
          />
        </div>
      )}

      {/* Bounded Loop Panel */}
      <BoundedLoopPanel runId={runId} />
    </div>
  );
}

async function loadRunArtifacts(runId: string, artifacts: string[]) {
  const visibleArtifacts = [
    "product-spec.md",
    "clarification-questions.md",
    "clarification-answers.md",
    "architecture.md",
    "tasks.md",
  ];
  const available = visibleArtifacts.filter((artifact) => artifacts.includes(artifact));
  const entries = await Promise.all(
    available.map(async (artifact) => {
      try {
        const loaded = await getRunArtifact(runId, artifact);
        return [artifact, loaded.content] as const;
      } catch {
        return [artifact, ""] as const;
      }
    }),
  );
  return Object.fromEntries(entries);
}

function RunNotFound({ runId }: { runId: string }) {
  return (
    <div className="max-w-2xl rounded border border-yellow-900 bg-yellow-950/20 p-5">
      <h2 className="text-xl font-semibold text-yellow-100">Run not found</h2>
      <p className="mt-2 text-sm text-yellow-200">
        This run does not exist anymore, or the local database was reset while the page was open.
      </p>
      {runId && <p className="mt-3 font-mono text-xs text-yellow-300">Run ID: {runId}</p>}
      <div className="mt-5 flex flex-wrap gap-3">
        <Link to="/runs" className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700">
          Back to Runs
        </Link>
        <Link to="/new-task" className="rounded bg-emerald-700 px-4 py-2 text-sm hover:bg-emerald-600">
          Create New Task
        </Link>
        <Link to="/projects" className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700">
          Open Projects
        </Link>
      </div>
    </div>
  );
}

function ToolCallsPanel({ calls, error, focus }: { calls: ToolCall[]; error: string; focus: ToolCallFocus | null }) {
  const [visibleLimit, setVisibleLimit] = useState(25);
  const [toolNameFilter, setToolNameFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [stepFilter, setStepFilter] = useState("all");
  const [focusMessage, setFocusMessage] = useState("");

  useEffect(() => {
    if (!focus) return;
    if (focus.visibleLimit) setVisibleLimit((current) => Math.max(current, focus.visibleLimit!));
    setToolNameFilter(focus.toolName || "all");
    setStatusFilter(focus.status || "all");
    setStepFilter(focus.stepId || "all");
    setFocusMessage(focus.message || "");
  }, [focus]);

  const sorted = [...calls]
    .sort((a, b) => toolCallTime(b).localeCompare(toolCallTime(a)))
  const toolNames = Array.from(new Set(sorted.map((call) => call.tool_name).filter(Boolean)));
  const stepIds = Array.from(new Set(sorted.map((call) => call.step_id).filter(Boolean)));
  const filtered = sorted.filter((call) => {
    if (toolNameFilter === "read-search-context") {
      if (!isReadSearchContextTool(call.tool_name)) return false;
    } else if (toolNameFilter !== "all" && call.tool_name !== toolNameFilter) {
      return false;
    }
    if (stepFilter !== "all" && call.step_id !== stepFilter) return false;
    if (statusFilter !== "all") {
      if (statusFilter === "needs_attention") {
        return isFailedRunCommandCall(call);
      }
      if (statusFilter === "timed_out") {
        return isTimedOutToolCall(call);
      }
      if ((call.status || "unknown") !== statusFilter) return false;
    }
    return true;
  });
  const recent = filtered.slice(0, visibleLimit);
  const hasMore = filtered.length > recent.length;

  const clearFilters = () => {
    setToolNameFilter("all");
    setStatusFilter("all");
    setStepFilter("all");
    setFocusMessage("");
  };

  return (
    <section data-action-anchor="tool-calls" className="rounded border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Tool Calls</h3>
          <p className="mt-1 text-xs text-gray-500">
            {calls.length} logged calls for this run. Showing {recent.length} of {filtered.length} matching calls.
          </p>
        </div>
        <span className="rounded bg-gray-800 px-2 py-1 text-xs text-gray-400">
          read-only journal
        </span>
      </div>

      {focusMessage && (
        <div className="mb-3 rounded border border-emerald-800 bg-emerald-950/20 p-3 text-xs text-emerald-200">
          {focusMessage}
        </div>
      )}

      {error && (
        <div className="mb-3 rounded border border-yellow-800 bg-yellow-950/20 p-3 text-sm text-yellow-200">
          {error}
        </div>
      )}

      <div className="mb-4 space-y-3 rounded border border-gray-800 bg-gray-950 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500">Tool</span>
          <FilterChip active={toolNameFilter === "all"} onClick={() => setToolNameFilter("all")}>all</FilterChip>
          {["run-command", "apply-patch", "propose-patch", "rollback-patch", "analyze-command-result"].map((name) => (
            <FilterChip key={name} active={toolNameFilter === name} onClick={() => setToolNameFilter(name)}>
              {name}
            </FilterChip>
          ))}
          <FilterChip
            active={toolNameFilter === "read-search-context"}
            onClick={() => setToolNameFilter("read-search-context")}
          >
            read/search/context
          </FilterChip>
          {toolNames
            .filter((name) => !["run-command", "apply-patch", "propose-patch", "rollback-patch", "analyze-command-result"].includes(name))
            .slice(0, 6)
            .map((name) => (
              <FilterChip key={name} active={toolNameFilter === name} onClick={() => setToolNameFilter(name)}>
                {name}
              </FilterChip>
            ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500">Status</span>
          {["all", "completed", "failed", "pending", "timed_out", "needs_attention"].map((status) => (
            <FilterChip key={status} active={statusFilter === status} onClick={() => setStatusFilter(status)}>
              {status === "needs_attention" ? "failed command" : status}
            </FilterChip>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-gray-500">Step</span>
          <FilterChip active={stepFilter === "all"} onClick={() => setStepFilter("all")}>all</FilterChip>
          {stepIds.slice(0, 8).map((stepId) => (
            <FilterChip key={stepId} active={stepFilter === stepId} onClick={() => setStepFilter(stepId)}>
              {truncate(stepId, 14)}
            </FilterChip>
          ))}
          {(toolNameFilter !== "all" || statusFilter !== "all" || stepFilter !== "all" || focusMessage) && (
            <button onClick={clearFilters} className="ml-auto text-xs text-gray-500 hover:text-gray-300">
              clear filters
            </button>
          )}
        </div>
      </div>

      {recent.length === 0 ? (
        <p className="text-sm text-gray-500">No tool calls match the current filters.</p>
      ) : (
        <div className="divide-y divide-gray-800">
          {recent.map((call) => (
            <ToolCallRow key={call.id} call={call} />
          ))}
        </div>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        {hasMore && (
          <button
            onClick={() => setVisibleLimit((current) => current + 25)}
            className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700"
          >
            Show more tool calls
          </button>
        )}
        <button
          onClick={() => setVisibleLimit(25)}
          className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-700"
        >
          Show latest 25
        </button>
        <button
          onClick={() => setVisibleLimit(50)}
          className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-400 hover:bg-gray-700"
        >
          Show latest 50
        </button>
      </div>
    </section>
  );
}

function FilterChip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded px-2 py-1 text-xs ${
        active
          ? "bg-emerald-800 text-emerald-100"
          : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
      }`}
    >
      {children}
    </button>
  );
}

function ToolCallRow({ call }: { call: ToolCall }) {
  const audit = patchAuditDetails(call);
  const isRunCommand = call.tool_name === "run-command";
  const isApplyPatch = call.tool_name === "apply-patch";
  const needsAnalysis = isFailedRunCommandCall(call);
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<CommandAnalysisResponse | null>(null);
  const [analysisError, setAnalysisError] = useState("");

  // Rollback state (apply-patch calls only)
  const hasRollbackData = isRollbackCapableApplyPatchCall(call);
  const [rollbackConfirmed, setRollbackConfirmed] = useState(false);
  const [rollbackRunning, setRollbackRunning] = useState(false);
  const [rollbackResult, setRollbackResult] = useState<RollbackPatchResponse | null>(null);
  const [rollbackError, setRollbackError] = useState("");

  const handleRollback = async () => {
    if (!call.project_id || !rollbackConfirmed) return;
    setRollbackRunning(true);
    setRollbackError("");
    try {
      const result = await rollbackProjectPatch(call.project_id, {
        tool_call_id: call.id,
        confirm: true,
        run_id: call.run_id,
        step_id: call.step_id,
      });
      setRollbackResult(result);
    } catch (e: any) {
      setRollbackError(e.message || "Rollback failed");
    } finally {
      setRollbackRunning(false);
    }
  };

  const handleAnalyze = async () => {
    if (!call.project_id) return;
    setAnalysisRunning(true);
    setAnalysisError("");
    try {
      const result = await analyzeCommandResult(call.project_id, {
        tool_call_id: call.id,
        run_id: call.run_id,
        step_id: call.step_id,
      });
      setAnalysisResult(result);
    } catch (e: any) {
      setAnalysisError(e.message || "Analysis failed");
    } finally {
      setAnalysisRunning(false);
    }
  };

  return (
    <article
      data-action-anchor="tool-call"
      data-tool-call-id={call.id}
      data-tool-name={call.tool_name}
      data-step-id={call.step_id || ""}
      data-rollback-capable={hasRollbackData ? "true" : "false"}
      data-command-failed={isFailedRunCommandCall(call) ? "true" : "false"}
      className="py-3 space-y-2"
    >
      <div className="grid gap-3 xl:grid-cols-[180px_1fr_180px]">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={call.status || "unknown"} />
                  <span className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
                    {call.risk_level || "low"}
                  </span>
                  {needsAnalysis && (
                    <span className="rounded bg-red-900/50 px-2 py-0.5 text-xs text-red-300">
                      Failed command
                    </span>
                  )}
                  {hasRollbackData && (
                    <span className="rounded bg-orange-900/50 px-2 py-0.5 text-xs text-orange-300">
                      Rollback available
                    </span>
                  )}
                </div>
                <p className="font-mono text-xs text-gray-300">{call.tool_name}</p>
              </div>

              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                  {call.project_id && <span>project: {call.project_id}</span>}
                  {call.step_id && <span>step: {call.step_id}</span>}
                  {audit.agentId && <span>agent: {audit.agentId}</span>}
                  {call.returncode !== null && <span>exit: {call.returncode}</span>}
                </div>
                {(audit.proposalId || audit.appliedFromProposalId) && (
                  <div className="flex flex-wrap gap-2 text-xs">
                    {audit.proposalId && (
                      <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">
                        proposal: {audit.proposalId}
                      </span>
                    )}
                    {audit.appliedFromProposalId && (
                      <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-300">
                        applied from: {audit.appliedFromProposalId}
                      </span>
                    )}
                  </div>
                )}
                {(audit.guardResultId || audit.guardRevalidated || audit.noGuardOverride) && (
                  <div className="flex flex-wrap gap-2 text-xs">
                    {audit.guardResultId && (
                      <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300">
                        Guard linked: {shortId(audit.guardResultId)}
                      </span>
                    )}
                    {audit.guardRevalidated && (
                      <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300">
                        Guard revalidated before apply
                      </span>
                    )}
                    {audit.noGuardOverride && (
                      <span className="rounded bg-orange-900/40 px-2 py-0.5 text-orange-300">
                        No-guard override
                      </span>
                    )}
                  </div>
                )}
                {call.error ? (
                  <p className="rounded bg-red-950/30 px-2 py-1 text-xs text-red-300">
                    {truncate(call.error, 260)}
                  </p>
                ) : (
                  <p className="text-xs text-gray-400">{summarizeToolOutput(call)}</p>
                )}
                {needsAnalysis && !analysisResult && (
                  <button
                    onClick={handleAnalyze}
                    disabled={analysisRunning}
                    className="rounded bg-gray-800 px-3 py-1 text-xs text-gray-300 hover:bg-gray-700 disabled:text-gray-500"
                  >
                    {analysisRunning ? "Analyzing..." : "Analyze command result"}
                  </button>
                )}
                {analysisError && (
                  <p className="text-xs text-red-400">{analysisError}</p>
                )}
              </div>

              <div className="text-xs text-gray-500 xl:text-right">
                <p>{call.completed_at || call.finished_at || call.created_at || "unknown time"}</p>
                {call.report_path && <p className="mt-1 truncate">{call.report_path}</p>}
              </div>
      </div>
      {analysisResult && (
        <ToolCallAnalysisPanel result={analysisResult} onDismiss={() => setAnalysisResult(null)} />
      )}
      {isApplyPatch && !rollbackResult && (
        <div className="ml-4 rounded border border-gray-800 bg-gray-950 p-2 space-y-1.5">
          <p className="text-xs font-medium text-gray-400">Rollback this patch</p>
          {!hasRollbackData ? (
            <p className="text-xs text-gray-600">No rollback metadata — only patches applied after rollback support was introduced can be reverted.</p>
          ) : (
            <>
              <label className="flex items-start gap-2 text-xs text-gray-400 cursor-pointer">
                <input
                  type="checkbox"
                  checked={rollbackConfirmed}
                  onChange={(e) => setRollbackConfirmed(e.target.checked)}
                  className="mt-0.5 h-3 w-3 flex-shrink-0"
                />
                I understand this will modify files by reverting a previous patch
              </label>
              <button
                onClick={handleRollback}
                disabled={!rollbackConfirmed || rollbackRunning}
                className="rounded bg-orange-800 px-3 py-1 text-xs text-orange-100 hover:bg-orange-700 disabled:bg-gray-800 disabled:text-gray-500"
              >
                {rollbackRunning ? "Rolling back…" : "Rollback"}
              </button>
              {rollbackError && <p className="text-xs text-red-400">{rollbackError}</p>}
            </>
          )}
        </div>
      )}
      {rollbackResult && (
        <RollbackResultPanel result={rollbackResult} onDismiss={() => setRollbackResult(null)} />
      )}
    </article>
  );
}

function RollbackResultPanel({ result, onDismiss }: { result: RollbackPatchResponse; onDismiss: () => void }) {
  return (
    <div className="ml-4 rounded border border-orange-800 bg-orange-950/20 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <p className="text-xs font-medium text-orange-300">Rollback complete</p>
        <button onClick={onDismiss} className="text-xs text-gray-500 hover:text-gray-300">dismiss</button>
      </div>
      {result.rolled_back_files.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs text-gray-500">Rolled back:</p>
          {result.rolled_back_files.map((f, i) => (
            <p key={i} className="text-xs text-gray-300 font-mono">
              <span className="rounded bg-emerald-900 px-1 py-0.5 text-emerald-300 mr-1">
                {f.status}
              </span>
              {f.path}
            </p>
          ))}
        </div>
      )}
      {result.skipped_files.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs text-gray-500">Skipped:</p>
          {result.skipped_files.map((f, i) => (
            <p key={i} className="text-xs text-gray-400 font-mono">
              <span className="rounded bg-yellow-900 px-1 py-0.5 text-yellow-300 mr-1">
                {f.status}
              </span>
              {f.path}
              {f.reason && <span className="text-gray-500 ml-1">— {f.reason}</span>}
            </p>
          ))}
        </div>
      )}
      {result.warnings.length > 0 && (
        <div className="space-y-0.5">
          {result.warnings.map((w, i) => (
            <p key={i} className="text-xs text-yellow-400">⚠ {w}</p>
          ))}
        </div>
      )}
      {result.git_status && (
        <pre className="text-xs text-gray-500 font-mono">{result.git_status}</pre>
      )}
    </div>
  );
}

function ToolCallAnalysisPanel({ result, onDismiss }: { result: CommandAnalysisResponse; onDismiss: () => void }) {
  const statusColor =
    result.status === "passed"
      ? "text-emerald-400"
      : result.status === "timed_out"
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="ml-4 rounded border border-gray-700 bg-gray-900 p-3 space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`font-semibold text-xs ${statusColor}`}>{result.status.toUpperCase()}</span>
          {result.can_create_fix_proposal && (
            <span className="rounded bg-blue-900 px-2 py-0.5 text-xs text-blue-300">fix proposal possible</span>
          )}
        </div>
        <button onClick={onDismiss} className="text-xs text-gray-500 hover:text-gray-300">dismiss</button>
      </div>
      <p className="text-xs text-gray-300">{result.summary}</p>
      {result.issues.length > 0 && (
        <div className="space-y-1">
          {result.issues.map((issue, i) => (
            <div key={i} className="rounded bg-gray-800 px-2 py-1 text-xs">
              <span className="rounded bg-gray-700 px-1 py-0.5 text-gray-400 mr-2">{issue.kind}</span>
              {issue.file_path && (
                <span className="text-gray-500 mr-1">
                  {issue.file_path}{issue.line != null ? `:${issue.line}` : ""}
                </span>
              )}
              <span className="text-gray-300">{issue.message}</span>
            </div>
          ))}
        </div>
      )}
      {result.suggested_next_actions.length > 0 && (
        <div className="space-y-0.5">
          <p className="text-xs text-gray-500 font-medium">Suggested actions:</p>
          {result.suggested_next_actions.map((action, i) => (
            <p key={i} className="text-xs text-gray-400">• {action}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function AssignedTeam({
  team,
  agentRegistry,
  modelProfiles,
  modelRegistry,
  modelRoutes,
  modelRoutesPersisted,
  selecting,
  routingModels,
  onSelectTeam,
  onPreviewModelRoutes,
  onPersistModelRoutes,
}: {
  team: RunAgentAssignment[];
  agentRegistry: AgentInfo[];
  modelProfiles: ModelProfile[];
  modelRegistry: ModelRegistryItem[];
  modelRoutes: ModelRouteDecision[];
  modelRoutesPersisted: boolean;
  selecting: boolean;
  routingModels: boolean;
  onSelectTeam: () => void;
  onPreviewModelRoutes: () => void;
  onPersistModelRoutes: () => void;
}) {
  const agentById = Object.fromEntries(agentRegistry.map((agent) => [agent.id, agent]));
  const profileById = Object.fromEntries(modelProfiles.map((profile) => [profile.id, profile]));
  const modelById = Object.fromEntries(modelRegistry.map((model) => [model.id, model]));
  const routeByAgent = Object.fromEntries(modelRoutes.map((route) => [route.agent_id, route]));

  return (
    <div>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Assigned Team</h3>
          <p className="mt-1 text-xs text-gray-500">
            These agents are selected for this run only. Selection does not grant file-editing powers by itself.
          </p>
        </div>
        <button
          onClick={onSelectTeam}
          disabled={selecting}
          className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
        >
          {selecting ? "Selecting..." : "Re-select Team"}
        </button>
      </div>

      <div className="mb-4 rounded border border-gray-800 bg-gray-950 p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h4 className="text-sm font-medium text-gray-200">Model Routing Status</h4>
            <p className="mt-1 text-xs text-gray-500">
              {modelRoutes.length} route decisions {modelRoutesPersisted ? "saved for this run" : "previewed, not saved"}.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={onPreviewModelRoutes}
              disabled={routingModels}
              className="rounded bg-gray-800 px-3 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
            >
              {routingModels ? "Routing..." : "Preview model routes"}
            </button>
            <button
              onClick={onPersistModelRoutes}
              disabled={routingModels}
              className="rounded bg-emerald-700 px-3 py-2 text-sm hover:bg-emerald-600 disabled:bg-gray-700 disabled:text-gray-500"
            >
              {routingModels ? "Routing..." : "Persist model routes"}
            </button>
          </div>
        </div>
      </div>

      {team.length === 0 ? (
        <div className="rounded border border-yellow-900 bg-yellow-950/20 p-3 text-sm text-yellow-300">
          No agents have been assigned yet.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          {team.map((agent) => (
            <AssignedAgentCard
              key={agent.id}
              assignment={agent}
              agent={agentById[agent.agent_id]}
              profile={agentById[agent.agent_id] ? profileById[agentById[agent.agent_id].model_profile] : undefined}
              route={routeByAgent[agent.agent_id]}
              model={
                routeByAgent[agent.agent_id]
                  ? modelById[routeByAgent[agent.agent_id].selected_model]
                  : agentById[agent.agent_id] && profileById[agentById[agent.agent_id].model_profile]
                  ? modelById[profileById[agentById[agent.agent_id].model_profile].primary_model]
                  : undefined
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AssignedAgentCard({
  assignment,
  agent,
  profile,
  route,
  model,
}: {
  assignment: RunAgentAssignment;
  agent?: AgentInfo;
  profile?: ModelProfile;
  route?: ModelRouteDecision;
  model?: ModelRegistryItem;
}) {
  const selectedModel = route?.selected_model || profile?.primary_model || "unknown";
  const selectedProvider = route?.selected_provider || profile?.preferred_provider || "unknown";
  return (
    <article className="rounded border border-gray-800 bg-gray-950 p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h4 className="font-mono text-sm text-gray-200">{assignment.agent_id}</h4>
          <p className="mt-1 text-xs text-gray-500">Role: {assignment.assigned_role || "specialist"}</p>
        </div>
        <span className="rounded bg-emerald-900/40 px-2 py-1 text-xs text-emerald-300">
          {Math.round(assignment.confidence * 100)}%
        </span>
      </div>
      <p className="mt-3 text-sm text-gray-400">{assignment.reason}</p>
      <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
        <TeamInfo label="task type" value={route?.task_type || "not routed"} />
        <TeamInfo label="model profile" value={route?.model_profile || agent?.model_profile || "unknown"} />
        <TeamInfo label="selected model" value={selectedModel} />
        <TeamInfo label="provider" value={selectedProvider} />
        <TeamInfo label="fallback" value={route?.fallback_model || profile?.fallback_model || "unknown"} />
        <TeamInfo label="status" value={assignment.status} />
      </div>
      {route?.reason && <p className="mt-2 text-xs text-gray-500">{route.reason}</p>}
      {route?.warnings?.length ? (
        <p className="mt-2 text-xs text-yellow-300">{route.warnings.join(" ")}</p>
      ) : null}
      {model && (
        <p className={`mt-2 text-xs ${model.installed ? "text-emerald-300" : "text-yellow-300"}`}>
          {model.installed ? "Model installed locally" : `Model not installed locally: ollama pull ${model.id}`}
        </p>
      )}
    </article>
  );
}

function TeamInfo({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded bg-gray-900 px-2 py-1.5">
      <span className="text-gray-600">{label}</span>
      <p className="truncate text-gray-300">{value}</p>
    </div>
  );
}

function ArtifactViewer({ title, content, empty }: { title: string; content?: string; empty: string }) {
  return (
    <div>
      <h3 className="mb-3 font-semibold text-gray-200">{title}</h3>
      {content ? (
        <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded bg-gray-950 p-3 text-sm text-gray-300">
          {content}
        </pre>
      ) : (
        <p className="text-sm text-gray-500">{empty}</p>
      )}
    </div>
  );
}

function ClarificationPanel({
  questions,
  savedAnswers,
  answers,
  saving,
  regeneratingPlan,
  onAnswersChange,
  onSubmit,
  onRegeneratePlan,
}: {
  questions?: string;
  savedAnswers?: string;
  answers: string;
  saving: boolean;
  regeneratingPlan: boolean;
  onAnswersChange: (value: string) => void;
  onSubmit: () => void;
  onRegeneratePlan: () => void;
}) {
  return (
    <div className="space-y-4">
      <ArtifactViewer
        title="Clarification Questions"
        content={questions}
        empty="No clarification questions generated yet..."
      />
      {savedAnswers && (
        <ArtifactViewer title="Saved Answers" content={savedAnswers} empty="" />
      )}
      {savedAnswers && (
        <button
          onClick={onRegeneratePlan}
          disabled={regeneratingPlan}
          className="rounded bg-blue-700 px-4 py-2 text-sm hover:bg-blue-600 disabled:bg-gray-700 disabled:text-gray-500"
        >
          {regeneratingPlan ? "Regenerating..." : "Regenerate Plan From Answers"}
        </button>
      )}
      <div>
        <h3 className="mb-2 font-semibold text-gray-200">Answer Questions</h3>
        <textarea
          value={answers}
          onChange={(event) => onAnswersChange(event.target.value)}
          rows={8}
          className="w-full rounded border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-200 focus:border-emerald-500 focus:outline-none"
          placeholder="Write answers, constraints, decisions, and product preferences here..."
        />
        <button
          onClick={onSubmit}
          disabled={saving || !answers.trim()}
          className="mt-3 rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
        >
          {saving ? "Saving..." : "Save Answers"}
        </button>
      </div>
    </div>
  );
}

function Timeline({
  run,
  steps,
  stepRoutes,
  toolCalls,
  onToolCallsChanged,
  draftPrefills,
  onDraftPrefillConsumed,
  agentPrefills,
  onAgentPrefillConsumed,
}: {
  run: Run;
  steps: RunStep[];
  stepRoutes: Record<string, ModelRouteDecision>;
  toolCalls: ToolCall[];
  onToolCallsChanged: () => Promise<void>;
  draftPrefills?: Record<string, PatchFormState | null>;
  onDraftPrefillConsumed?: (stepId: string) => void;
  agentPrefills?: Record<string, IssuePrefill | null>;
  onAgentPrefillConsumed?: (stepId: string) => void;
}) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  if (steps.length === 0) {
    return <p className="text-sm text-gray-500">No steps recorded yet...</p>;
  }

  const toggle = (id: string) =>
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));

  const orchestratorSteps = steps.filter((s) => !s.parent_step_id);
  const childSteps = steps.filter((s) => s.parent_step_id);
  const callsByStep = groupPatchCallsByStep(toolCalls);

  useEffect(() => {
    const handleFocus = (event: Event) => {
      const detail = (event as CustomEvent<{ stepId?: string }>).detail;
      if (!detail?.stepId) return;
      const step = steps.find((s) => s.id === detail.stepId);
      if (step?.parent_step_id) {
        setExpanded((prev) => ({ ...prev, [step.parent_step_id]: true }));
      }
    };

    window.addEventListener("aiw-focus-manual-action", handleFocus);
    return () => window.removeEventListener("aiw-focus-manual-action", handleFocus);
  }, [steps]);

  return (
    <div className="space-y-3">
      {orchestratorSteps.map((step) => {
        const isOpen = expanded[step.id] ?? false;
        const children = childSteps.filter((c) => c.parent_step_id === step.id);
        return (
          <div key={step.id}>
            <div className="grid gap-3 rounded border border-gray-800 bg-gray-950 p-3 lg:grid-cols-[180px_1fr]">
              <div className="space-y-2">
                <StatusBadge status={step.status} />
                <p className="text-xs text-gray-500">{step.agent_id || "orchestrator"}</p>
                {children.length > 0 && (
                  <button
                    onClick={() => toggle(step.id)}
                    className="text-xs text-emerald-400 hover:text-emerald-300"
                  >
                    {isOpen ? "▾ Hide" : "▸ Show"} {children.length} sub-steps
                  </button>
                )}
              </div>
              <div className="min-w-0">
                <h3 className="font-medium text-gray-200">{step.title}</h3>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
                  {step.started_at && <span>Started: {step.started_at}</span>}
                  {step.finished_at && <span>Finished: {step.finished_at}</span>}
                </div>
                {step.output && (
                  <ExpandableOutput value={step.output} previewMax={300} />
                )}
                {step.error && (
                  <pre className="mt-3 whitespace-pre-wrap rounded bg-red-950/40 p-3 text-xs text-red-300">
                    {step.error}
                  </pre>
                )}
              </div>
            </div>
            {isOpen && children.length > 0 && (
              <div className="ml-6 mt-1 space-y-2 border-l-2 border-gray-800 pl-4">
                {children.map((child) => (
                  <StepCard
                    key={child.id}
                    run={run}
                    step={child}
                    route={stepRoutes[child.id]}
                    patchCalls={callsByStep[child.id] || []}
                    onToolCallsChanged={onToolCallsChanged}
                    draftPrefill={draftPrefills?.[child.id] ?? null}
                    onDraftPrefillConsumed={() => onDraftPrefillConsumed?.(child.id)}
                    agentPrefill={agentPrefills?.[child.id] ?? null}
                    onAgentPrefillConsumed={() => onAgentPrefillConsumed?.(child.id)}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
      {/* Show orphan child steps if parent is missing */}
      {childSteps
        .filter((c) => !orchestratorSteps.some((p) => p.id === c.parent_step_id))
        .map((step) => (
          <StepCard
            key={step.id}
            run={run}
            step={step}
            route={stepRoutes[step.id]}
            patchCalls={callsByStep[step.id] || []}
            onToolCallsChanged={onToolCallsChanged}
            draftPrefill={draftPrefills?.[step.id] ?? null}
            onDraftPrefillConsumed={() => onDraftPrefillConsumed?.(step.id)}
            agentPrefill={agentPrefills?.[step.id] ?? null}
            onAgentPrefillConsumed={() => onAgentPrefillConsumed?.(step.id)}
          />
        ))}
    </div>
  );
}

function StepCard({
  run,
  step,
  route,
  patchCalls,
  onToolCallsChanged,
  draftPrefill,
  onDraftPrefillConsumed,
  agentPrefill,
  onAgentPrefillConsumed,
}: {
  run: Run;
  step: RunStep;
  route?: ModelRouteDecision;
  patchCalls: ToolCall[];
  onToolCallsChanged: () => Promise<void>;
  draftPrefill?: PatchFormState | null;
  onDraftPrefillConsumed?: () => void;
  agentPrefill?: IssuePrefill | null;
  onAgentPrefillConsumed?: () => void;
}) {
  const [patchPrefill, setPatchPrefill] = useState<IssuePrefill | null>(null);

  // When an agent patch draft prefill arrives (from AgentExecutionPanel in
  // OperatorQueuePanel), funnel it into the same patchPrefill state that
  // GuidedFixWorkflow uses — so StepPatchSection applies the same guard-clearing
  // and file_path prefill behaviour.
  useEffect(() => {
    if (!agentPrefill) return;
    setPatchPrefill(agentPrefill);
    onAgentPrefillConsumed?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agentPrefill]);

  return (
    <div className="grid gap-3 rounded border border-gray-800 bg-gray-950 p-3 lg:grid-cols-[160px_1fr]">
      <div className="space-y-1">
        <StatusBadge status={step.status} />
        <p className="text-xs text-gray-500">{step.agent_id || "unassigned"}</p>
        {route && (
          <div className="space-y-0.5">
            <p className="text-xs font-mono text-emerald-400 truncate" title={route.selected_model}>
              {route.selected_model}
            </p>
            <p className="text-xs text-gray-600">{route.selected_provider}</p>
          </div>
        )}
      </div>
      <div className="min-w-0">
        <h4 className="text-sm font-medium text-gray-300">{step.title}</h4>
        {route && (
          <div className="mt-1 flex flex-wrap gap-2 text-xs">
            <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
              agent: <span className="text-gray-200">{route.agent_id}</span>
            </span>
            <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
              task: <span className="text-gray-200">{route.task_type}</span>
            </span>
            {route.fallback_model && route.fallback_model !== route.selected_model && (
              <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
                fallback: <span className="text-gray-200">{route.fallback_model}</span>
              </span>
            )}
            {route.warnings.length > 0 && (
              <span className="rounded bg-yellow-900/50 px-1.5 py-0.5 text-yellow-400">
                {route.warnings.length} warning{route.warnings.length > 1 ? "s" : ""}
              </span>
            )}
          </div>
        )}
        <div className="mt-1 flex flex-wrap gap-3 text-xs text-gray-500">
          {step.started_at && <span>Started: {step.started_at}</span>}
          {step.finished_at && <span>Finished: {step.finished_at}</span>}
        </div>
        {step.input && (
          <ExpandableOutput value={step.input} previewMax={200} muted />
        )}
        {step.output && (
          <ExpandableOutput value={step.output} previewMax={500} />
        )}
        {step.error && (
          <pre className="mt-3 whitespace-pre-wrap rounded bg-red-950/40 p-3 text-xs text-red-300">
            {step.error}
          </pre>
        )}
        {run.project_id && (
          <GuidedFixWorkflow
            run={run}
            step={step}
            agentId={step.agent_id || route?.agent_id || ""}
            onToolCallsChanged={onToolCallsChanged}
            onUsePatchPrefill={setPatchPrefill}
          />
        )}
        <StepPatchSection
          run={run}
          step={step}
          route={route}
          calls={patchCalls}
          onToolCallsChanged={onToolCallsChanged}
          externalPrefill={patchPrefill}
          onPrefillConsumed={() => setPatchPrefill(null)}
          draftPrefill={draftPrefill ?? null}
          onDraftPrefillConsumed={onDraftPrefillConsumed}
        />
      </div>
    </div>
  );
}

// ── Guided Fix Workflow ───────────────────────────────────────────────────────

function GuidedFixWorkflow({
  run,
  step,
  agentId,
  onToolCallsChanged,
  onUsePatchPrefill,
}: {
  run: Run;
  step: RunStep;
  agentId: string;
  onToolCallsChanged: () => Promise<void>;
  onUsePatchPrefill?: (prefill: IssuePrefill) => void;
}) {
  const [open, setOpen] = useState(false);
  const [commandResult, setCommandResult] = useState<RunProjectCommandResponse | null>(null);
  const [analysis, setAnalysis] = useState<CommandAnalysisResponse | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const handleFocus = (event: Event) => {
      const detail = (event as CustomEvent<{ stepId?: string; anchor?: string }>).detail;
      if (detail?.stepId === step.id && detail.anchor === "guided-fix") {
        setOpen(true);
      }
    };

    window.addEventListener("aiw-focus-manual-action", handleFocus);
    return () => window.removeEventListener("aiw-focus-manual-action", handleFocus);
  }, [step.id]);

  const handleRunTests = async () => {
    setIsRunning(true);
    setError("");
    setCommandResult(null);
    setAnalysis(null);
    try {
      const result = await runProjectCommand(run.project_id, {
        command_kind: "test",
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
      });
      setCommandResult(result);
      await onToolCallsChanged();
    } catch (e: any) {
      setError(e.message || "Failed to run tests");
    } finally {
      setIsRunning(false);
    }
  };

  const handleAnalyze = async () => {
    if (!commandResult?.tool_call_id) return;
    setIsAnalyzing(true);
    setError("");
    try {
      const result = await analyzeCommandResult(run.project_id, {
        tool_call_id: commandResult.tool_call_id,
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
      });
      setAnalysis(result);
      await onToolCallsChanged();
    } catch (e: any) {
      setError(e.message || "Analysis failed");
    } finally {
      setIsAnalyzing(false);
    }
  };

  const failed = commandResult !== null && (commandResult.returncode !== 0 || commandResult.timed_out);
  const passed = commandResult !== null && commandResult.returncode === 0 && !commandResult.timed_out;

  return (
    <div data-step-id={step.id} data-action-anchor="guided-fix" className="mt-3 rounded border border-gray-800 bg-gray-950">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-3 py-2 text-xs text-gray-400 hover:text-gray-200"
      >
        <span className="font-medium">Guided Fix Workflow</span>
        <span>{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3 border-t border-gray-800">
          {/* Step 1 */}
          <div className="space-y-1 pt-2">
            <p className="text-xs text-gray-500 font-medium">Step 1 — Run Tests</p>
            <button
              onClick={handleRunTests}
              disabled={isRunning}
              className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:text-gray-500"
            >
              {isRunning ? "Running…" : "Run Tests"}
            </button>
            {commandResult && (
              <div
                className={`mt-1 rounded px-2 py-1 text-xs space-y-0.5 ${
                  passed ? "bg-emerald-950/40 text-emerald-300" : "bg-red-950/30 text-red-300"
                }`}
              >
                <p>
                  exit {commandResult.returncode}
                  {commandResult.timed_out && " · timed out"}
                  {" · "}{commandResult.duration_ms}ms
                </p>
                {commandResult.stdout.trim() && (
                  <p className="text-gray-400 font-mono">{truncate(commandResult.stdout.trim(), 160)}</p>
                )}
                {commandResult.stderr.trim() && (
                  <p className="text-gray-500 font-mono">{truncate(commandResult.stderr.trim(), 160)}</p>
                )}
              </div>
            )}
            {passed && (
              <p className="text-xs text-emerald-400">✓ Tests passed — no fix needed.</p>
            )}
          </div>

          {/* Step 2 */}
          {failed && (
            <div className="space-y-1">
              <p className="text-xs text-gray-500 font-medium">Step 2 — Analyze Result</p>
              {!analysis ? (
                <button
                  onClick={handleAnalyze}
                  disabled={isAnalyzing}
                  className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:text-gray-500"
                >
                  {isAnalyzing ? "Analyzing…" : "Analyze"}
                </button>
              ) : (
                <div className="rounded border border-gray-700 bg-gray-900 p-2 space-y-1.5">
                  <p className="text-xs text-red-400">{analysis.summary}</p>
                  {analysis.issues.length > 0 && (
                    <div className="space-y-1.5">
                      {analysis.issues.slice(0, 5).map((issue, i) => (
                        <div key={i} className="rounded bg-gray-800 px-2 py-1.5 text-xs space-y-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <span className="rounded bg-gray-700 px-1 py-0.5 text-gray-500">{issue.kind}</span>
                            {issue.file_path && (
                              <span className="font-mono text-gray-500">
                                {issue.file_path}{issue.line != null ? `:${issue.line}` : ""}
                              </span>
                            )}
                          </div>
                          <p className="text-gray-400">{issue.message}</p>
                          {issue.file_path && onUsePatchPrefill && (
                            <button
                              onClick={() => onUsePatchPrefill({
                                file_path: issue.file_path!,
                                context_kind: issue.kind,
                                context_location: `${issue.file_path}${issue.line != null ? `:${issue.line}` : ""}`,
                                context_message: issue.message,
                              })}
                              className="rounded bg-blue-900 px-2 py-0.5 text-xs text-blue-300 hover:bg-blue-800"
                            >
                              Use for Patch Proposal ↓
                            </button>
                          )}
                        </div>
                      ))}
                      {analysis.issues.length > 5 && (
                        <p className="text-xs text-gray-600">…and {analysis.issues.length - 5} more</p>
                      )}
                    </div>
                  )}
                  {analysis.suggested_next_actions.length > 0 && (
                    <div className="space-y-0.5 border-t border-gray-800 pt-1">
                      {analysis.suggested_next_actions.map((a, i) => (
                        <p key={i} className="text-xs text-gray-500">• {a}</p>
                      ))}
                    </div>
                  )}
                  {analysis.can_create_fix_proposal && (
                    <p className="text-xs text-blue-400">
                      Fix proposal possible — use the Patch Proposal form below.
                    </p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Step 3 hint */}
          {analysis && analysis.can_create_fix_proposal && (
            <div className="space-y-0.5">
              <p className="text-xs text-gray-500 font-medium">Step 3 — Create Patch Proposal</p>
              <p className="text-xs text-gray-600">Open the Patch Proposal section below, fill in file/old/new text, preview and confirm.</p>
            </div>
          )}

          {/* Step 4 hint */}
          {analysis && analysis.can_create_fix_proposal && (
            <div className="space-y-0.5">
              <p className="text-xs text-gray-500 font-medium">Step 4 — Apply Patch</p>
              <p className="text-xs text-gray-600">Check the confirmation box in the patch form and click Apply Patch. Then re-run tests above to verify.</p>
            </div>
          )}

          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>
      )}
    </div>
  );
}

function StepPatchSection({
  run,
  step,
  route,
  calls,
  onToolCallsChanged,
  externalPrefill,
  onPrefillConsumed,
  draftPrefill,
  onDraftPrefillConsumed,
}: {
  run: Run;
  step: RunStep;
  route?: ModelRouteDecision;
  calls: ToolCall[];
  onToolCallsChanged: () => Promise<void>;
  externalPrefill?: IssuePrefill | null;
  onPrefillConsumed?: () => void;
  draftPrefill?: PatchFormState | null;
  onDraftPrefillConsumed?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [localCalls, setLocalCalls] = useState<ToolCall[]>(calls);
  const [form, setForm] = useState<PatchFormState>(emptyPatchForm);
  const [preview, setPreview] = useState<ProposePatchResponse | null>(null);
  const [applyResult, setApplyResult] = useState<ApplyPatchResponse | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState<"preview" | "apply" | "review" | "">("");
  const [error, setError] = useState("");
  const [issueContext, setIssueContext] = useState<IssuePrefill | null>(null);
  const [reviewResult, setReviewResult] = useState<PatchReviewResponse | null>(null);
  const [guardAction, setGuardAction] = useState("");
  const [guardResult, setGuardResult] = useState<StepSourceOfTruthGuardResponse | null>(null);
  const [guardCheckedContext, setGuardCheckedContext] = useState<GuardCheckedContext | null>(null);
  const [guardLoading, setGuardLoading] = useState(false);
  const [guardError, setGuardError] = useState("");
  const [guardNoCheckOverride, setGuardNoCheckOverride] = useState(false);
  const [guardWarningAcknowledged, setGuardWarningAcknowledged] = useState(false);
  // Guard History state
  const [guardHistory, setGuardHistory] = useState<GuardResultItem[]>([]);
  const [guardHistoryLoading, setGuardHistoryLoading] = useState(false);
  const [guardHistoryOpen, setGuardHistoryOpen] = useState(false);
  const [selectedGuardResultId, setSelectedGuardResultId] = useState<string | null>(null);
  const [guardValidation, setGuardValidation] = useState<GuardProposalValidationResponse | null>(null);
  const [guardValidationLoading, setGuardValidationLoading] = useState(false);
  const [guardValidationError, setGuardValidationError] = useState("");
  const [patchLifecycle, setPatchLifecycle] = useState<StepPatchLifecycleResponse | null>(null);
  const [patchLifecycleLoading, setPatchLifecycleLoading] = useState(false);
  const [patchLifecycleError, setPatchLifecycleError] = useState("");
  const [manualTestRunning, setManualTestRunning] = useState(false);
  const [manualAnalysisLoading, setManualAnalysisLoading] = useState(false);
  const [manualAnalysis, setManualAnalysis] = useState<CommandAnalysisResponse | null>(null);
  const [fixDraft, setFixDraft] = useState<FailureToFixDraftResponse | null>(null);
  const [fixDraftLoading, setFixDraftLoading] = useState(false);
  const [fixDraftError, setFixDraftError] = useState("");
  const agentId = step.agent_id || route?.agent_id || "";

  useEffect(() => {
    const handleFocus = (event: Event) => {
      const detail = (event as CustomEvent<{ stepId?: string; anchor?: string }>).detail;
      if (detail?.stepId === step.id && detail.anchor === "step-patch") {
        setOpen(true);
      }
    };

    window.addEventListener("aiw-focus-manual-action", handleFocus);
    return () => window.removeEventListener("aiw-focus-manual-action", handleFocus);
  }, [step.id]);

  useEffect(() => {
    setLocalCalls(calls);
  }, [calls]);

  // When a prefill arrives from GuidedFixWorkflow, open the form and pre-fill file_path.
  useEffect(() => {
    if (!externalPrefill) return;
    setForm((prev) => ({ ...prev, file_path: externalPrefill.file_path, old_text: "", new_text: "" }));
    setIssueContext(externalPrefill);
    setOpen(true);
    setPreview(null);
    setApplyResult(null);
    setConfirmed(false);
    setGuardResult(null);
    setGuardCheckedContext(null);
    setGuardNoCheckOverride(false);
    setGuardWarningAcknowledged(false);
    setSelectedGuardResultId(null);
    setGuardValidation(null);
    setGuardValidationError("");
    setGuardError("");
    setError("");
    onPrefillConsumed?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [externalPrefill]);

  // When a draft candidate prefill arrives from Context Patch Draft, open form with full data.
  useEffect(() => {
    if (!draftPrefill) return;
    setForm(draftPrefill);
    setOpen(true);
    setPreview(null);
    setApplyResult(null);
    setConfirmed(false);
    setGuardResult(null);
    setGuardCheckedContext(null);
    setGuardNoCheckOverride(false);
    setGuardWarningAcknowledged(false);
    setSelectedGuardResultId(null);
    setGuardValidation(null);
    setGuardValidationError("");
    setGuardError("");
    setError("");
    onDraftPrefillConsumed?.();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [draftPrefill]);

  const refreshStepCalls = async () => {
    const next = await getStepToolCalls(run.id, step.id).catch(() => null);
    if (next) setLocalCalls(next.filter(isPatchCall));
    await onToolCallsChanged();
  };

  const loadGuardHistory = async () => {
    setGuardHistoryLoading(true);
    try {
      const resp = await listRunGuardResults(run.id, { step_id: step.id, include_stale: true, limit: 20 });
      setGuardHistory(resp.items);
    } catch {
      setGuardHistory([]);
    } finally {
      setGuardHistoryLoading(false);
    }
  };

  const loadPatchLifecycle = async () => {
    setPatchLifecycleLoading(true);
    setPatchLifecycleError("");
    try {
      const result = await getStepPatchLifecycle(run.id, step.id);
      setPatchLifecycle(result);
    } catch (e: any) {
      setPatchLifecycleError(readableError(e));
    } finally {
      setPatchLifecycleLoading(false);
    }
  };

  const handleLifecycleRunTests = async () => {
    if (!run.project_id) {
      setPatchLifecycleError("Run is not linked to a project.");
      return;
    }
    setManualTestRunning(true);
    setPatchLifecycleError("");
    setManualAnalysis(null);
    try {
      await runProjectCommand(run.project_id, {
        command_kind: "test",
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
      });
      await refreshStepCalls();
      await loadPatchLifecycle();
    } catch (e: any) {
      setPatchLifecycleError(readableError(e));
    } finally {
      setManualTestRunning(false);
    }
  };

  const handleLifecycleAnalyzeFailedTests = async () => {
    if (!run.project_id || !patchLifecycle?.latest_test?.tool_call_id) return;
    setManualAnalysisLoading(true);
    setPatchLifecycleError("");
    setManualAnalysis(null);
    try {
      const result = await analyzeCommandResult(run.project_id, {
        tool_call_id: patchLifecycle.latest_test.tool_call_id,
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
      });
      setManualAnalysis(result);
      await refreshStepCalls();
      await loadPatchLifecycle();
    } catch (e: any) {
      setPatchLifecycleError(readableError(e));
    } finally {
      setManualAnalysisLoading(false);
    }
  };

  const handlePrepareFixDraft = async () => {
    setFixDraftLoading(true);
    setFixDraftError("");
    setFixDraft(null);
    try {
      const result = await createFailureToFixDraft(run.id, step.id, {
        apply_tool_call_id: patchLifecycle?.latest_apply?.tool_call_id ?? null,
        guard_result_id: patchLifecycle?.latest_apply?.guard_result_id
          ?? patchLifecycle?.latest_proposal?.guard_result_id
          ?? null,
      });
      setFixDraft(result);
    } catch (e: any) {
      setFixDraftError(readableError(e));
    } finally {
      setFixDraftLoading(false);
    }
  };

  const handlePrefillFromFixDraft = () => {
    if (!fixDraft) return;
    const prefill: IssuePrefill = {
      file_path: "",
      context_kind: "test_failure",
      context_location: `step:${step.id}`,
      context_message: fixDraft.fix_context,
    };
    setIssueContext(prefill);
    // Clear stale guard validation state when context changes
    setGuardValidation(null);
    setGuardValidationError("");
    // Don't clear selectedGuardResultId — operator keeps their guard selection
    setOpen(true);
  };

  const handleValidateGuard = async () => {
    if (!selectedGuardResultId) return;
    setGuardValidationLoading(true);
    setGuardValidationError("");
    setGuardValidation(null);
    try {
      const result = await validateGuardResultForProposal(run.id, step.id, selectedGuardResultId, {
        proposed_action: guardAction || form.file_path || undefined,
        file_path: form.file_path || null,
        patch_summary: guardAction || null,
        old_text: form.old_text || null,
        new_text: form.new_text || null,
        warning_acknowledged: guardWarningAcknowledged,
        no_guard_override: guardNoCheckOverride,
      });
      setGuardValidation(result);
    } catch (e: any) {
      setGuardValidationError(readableError(e));
    } finally {
      setGuardValidationLoading(false);
    }
  };

  const update = <K extends keyof PatchFormState>(key: K, value: PatchFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setPreview(null);
    setApplyResult(null);
    setReviewResult(null);
    setConfirmed(false);
    setGuardResult(null);
    setGuardCheckedContext(null);
    setGuardNoCheckOverride(false);
    setGuardWarningAcknowledged(false);
    setGuardValidation(null);
    setGuardValidationError("");
    setError("");
  };

  const handleReview = async () => {
    if (!run.project_id) {
      setError("Run is not linked to a project.");
      return;
    }
    if (!form.file_path.trim()) {
      setError("File path is required.");
      return;
    }
    setLoading("review");
    setError("");
    setReviewResult(null);
    try {
      const result = await reviewProjectPatch(run.project_id, {
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
        operations: [{ file_path: form.file_path, old_text: form.old_text, new_text: form.new_text }],
      });
      setReviewResult(result);
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const handleSourceGuardCheck = async () => {
    if (!guardAction.trim()) {
      setGuardError("Proposed action or patch summary is required.");
      return;
    }
    setGuardLoading(true);
    setGuardError("");
    const checkedContext = {
      proposedAction: guardAction,
      filePath: form.file_path,
      oldText: form.old_text,
      newText: form.new_text,
    };
    try {
      const result = await checkStepSourceOfTruthGuard(run.id, step.id, {
        proposed_action: checkedContext.proposedAction,
        file_path: checkedContext.filePath || null,
        patch_summary: checkedContext.proposedAction,
        old_text: checkedContext.oldText || null,
        new_text: checkedContext.newText || null,
      });
      setGuardResult(result);
      setGuardCheckedContext(checkedContext);
      setGuardNoCheckOverride(false);
      setGuardWarningAcknowledged(false);
      setGuardValidation(null);
      setGuardValidationError("");
    } catch (e: any) {
      setGuardError(readableError(e));
      setGuardCheckedContext(null);
    } finally {
      setGuardLoading(false);
    }
  };

  const handleUseGuardContext = () => {
    if (!guardResult || !guardCheckedContext || guardResult.guard_result.decision === "blocked") return;
    const guard = guardResult.guard_result;
    if (guardCheckedContext.filePath.trim()) {
      setForm((current) => ({ ...current, file_path: guardCheckedContext.filePath }));
    }
    setIssueContext({
      file_path: guardCheckedContext.filePath,
      context_kind: "source-of-truth-guard",
      context_location: `step ${step.id}`,
      context_message: formatGuardContextPrefillMessage(guardResult, guardCheckedContext.proposedAction),
    });
    setPreview(null);
    setApplyResult(null);
    setReviewResult(null);
    setConfirmed(false);
    setGuardNoCheckOverride(false);
    setGuardWarningAcknowledged(false);
    setError("");
  };

  const handlePreview = async () => {
    if (!run.project_id) {
      setError("Run is not linked to a project.");
      return;
    }
    if (!form.file_path.trim()) {
      setError("File path is required.");
      return;
    }
    if (!canCreateProposalWithGuard) {
      setError(sourceGuardGateMessage(guardResult, guardNoCheckOverride, guardWarningAcknowledged, selectedGuardResultId, guardValidation));
      return;
    }
    const proposalGuardResultId = selectedGuardResultId && guardValidation?.valid ? selectedGuardResultId : null;
    setLoading("preview");
    setError("");
    try {
      const result = await proposeProjectPatch(run.project_id, {
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
        guard_result_id: proposalGuardResultId,
        guard_warning_acknowledged: guardWarningAcknowledged,
        no_guard_override: !proposalGuardResultId && guardNoCheckOverride,
        operations: [patchOperationFromForm(form)],
      });
      setPreview(result);
      setApplyResult(null);
      setConfirmed(false);
      await refreshStepCalls();
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const handleApply = async () => {
    if (!run.project_id || !confirmed) return;
    setLoading("apply");
    setError("");
    try {
      const result = await applyProjectPatch(run.project_id, {
        run_id: run.id,
        step_id: step.id,
        agent_id: agentId,
        proposal_id: preview?.proposal_id || preview?.tool_call_id || "",
        expected_summary: preview?.summary || "",
        confirm: true,
        operations: [patchOperationFromForm(form)],
      });
      setApplyResult(result);
      await refreshStepCalls();
      await loadPatchLifecycle();
    } catch (e: any) {
      setError(readableError(e));
    } finally {
      setLoading("");
    }
  };

  const recent = localCalls.filter(isPatchCall).slice(0, 3);
  const guardDecision = guardResult?.guard_result.decision ?? "not_checked";
  const selectedGuardValidated = Boolean(selectedGuardResultId && guardValidation?.valid);
  const proposalGuardStatus = selectedGuardResultId
    ? guardValidation
      ? guardValidation.valid
        ? guardValidation.decision
        : "blocked"
      : "not_checked"
    : guardNoCheckOverride
      ? "override"
      : "not_checked";
  const canUseGuardContext =
    Boolean(guardResult) &&
    Boolean(guardCheckedContext?.proposedAction.trim()) &&
    (guardDecision === "allowed" || guardDecision === "warning");
  const canCreateProposalWithGuard =
    selectedGuardResultId ? selectedGuardValidated : guardNoCheckOverride;
  const canApply =
    Boolean(preview) &&
    preview!.files.length > 0 &&
    preview!.files.every((file) => file.status !== "error") &&
    confirmed &&
    loading === "";

  return (
    <div data-step-id={step.id} data-action-anchor="step-patch" className="mt-4 rounded border border-gray-800 bg-gray-900 p-3">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h5 className="text-sm font-medium text-gray-300">Step Patch Tools</h5>
          <p className="mt-1 text-xs text-gray-500">{recent.length} patch call(s) linked to this step.</p>
        </div>
        <button
          onClick={() => setOpen((current) => !current)}
          className="rounded bg-gray-800 px-3 py-1.5 text-xs hover:bg-gray-700"
        >
          {open ? "Hide" : "Create Patch Proposal"}
        </button>
      </div>

      {recent.length > 0 && (
        <div className="mt-3 space-y-2">
          {recent.map((call) => {
            const audit = patchAuditDetails(call);
            return (
              <div key={call.id} className="rounded bg-gray-950 px-3 py-2 text-xs">
                <div className="flex flex-wrap items-center gap-2">
                  <StatusBadge status={call.status || "unknown"} />
                  <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-400">{call.risk_level}</span>
                  <span className="font-mono text-gray-300">{call.tool_name}</span>
                </div>
                <p className="mt-1 text-gray-500">{summarizeToolOutput(call)}</p>
                {audit.proposalId && <p className="mt-1 font-mono text-gray-500">proposal: {audit.proposalId}</p>}
                {audit.appliedFromProposalId && (
                  <p className="mt-1 font-mono text-gray-500">applied from: {audit.appliedFromProposalId}</p>
                )}
                {call.error && <p className="mt-1 text-red-300">{truncate(call.error, 180)}</p>}
              </div>
            );
          })}
        </div>
      )}

      {open && (
        <div className="mt-4 space-y-3">
          <div className="rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-400">
            <p className="font-medium text-gray-300">Recommended manual flow</p>
            <ol className="mt-2 list-decimal space-y-1 pl-4">
              <li>Use a draft or fill `file_path`, `old_text`, and `new_text` manually.</li>
              <li>Click Review Patch. `old_text` should match the current file exactly.</li>
              <li>If review is OK, Preview/Create Proposal.</li>
              <li>Apply only with the manual confirmation checkbox.</li>
            </ol>
          </div>
          <PatchLifecyclePanel
            lifecycle={patchLifecycle}
            loading={patchLifecycleLoading}
            error={patchLifecycleError}
            manualTestRunning={manualTestRunning}
            manualAnalysisLoading={manualAnalysisLoading}
            manualAnalysis={manualAnalysis}
            fixDraft={fixDraft}
            fixDraftLoading={fixDraftLoading}
            fixDraftError={fixDraftError}
            onRefresh={loadPatchLifecycle}
            onRunTests={handleLifecycleRunTests}
            onAnalyzeFailedTests={handleLifecycleAnalyzeFailedTests}
            onPrepareFixDraft={handlePrepareFixDraft}
            onPrefillFromFixDraft={handlePrefillFromFixDraft}
          />
          <div className="rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-400">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-medium text-gray-300">Source-of-Truth Guard</p>
                <p className="mt-1 text-gray-500">
                  Source-of-truth guard is read-only. It does not create patches, apply changes, run commands, call providers, or create tool calls.
                </p>
              </div>
              <button
                onClick={handleSourceGuardCheck}
                disabled={guardLoading}
                className="rounded bg-gray-800 px-3 py-1.5 text-xs hover:bg-gray-700 disabled:bg-gray-800 disabled:text-gray-500"
              >
                {guardLoading ? "Checking..." : "Check source-of-truth guard"}
              </button>
            </div>
            <label className="mt-3 block">
              <span className="mb-1 block text-xs text-gray-500">Proposed action / patch summary</span>
              <textarea
                value={guardAction}
                onChange={(event) => {
                  setGuardAction(event.target.value);
                  setGuardError("");
                  setGuardResult(null);
                  setGuardCheckedContext(null);
                  setGuardNoCheckOverride(false);
                  setGuardWarningAcknowledged(false);
                  setGuardValidation(null);
                  setGuardValidationError("");
                }}
                rows={3}
                placeholder="Review or summarize the intended change before creating a patch proposal..."
                className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 text-xs focus:border-emerald-500 focus:outline-none"
              />
            </label>
            {guardError && (
              <div className="mt-2 rounded border border-red-800 bg-red-950/30 p-2 text-xs text-red-300">{guardError}</div>
            )}
            {guardResult && <SourceOfTruthGuardPanel result={guardResult} />}
            {guardResult && (
              <div className="mt-3 rounded border border-gray-800 bg-gray-900 p-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs text-gray-500">
                    Prefill only copies checked guard context into the patch form. It does not generate code, create a proposal, apply patches, run commands, or call providers.
                  </p>
                  {canUseGuardContext && (
                    <button
                      onClick={handleUseGuardContext}
                      className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700"
                    >
                      Use guard context in patch form
                    </button>
                  )}
                </div>
                {guardDecision === "blocked" && (
                  <p className="mt-2 text-xs text-red-300">Blocked guard result cannot be used to prefill a patch proposal.</p>
                )}
              </div>
            )}
          </div>
          {/* Guard History panel */}
          <div className="rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-400">
            <div className="flex items-center justify-between">
              <p className="font-medium text-gray-300">Guard History (persisted)</p>
              <div className="flex gap-2">
                <button
                  onClick={() => { setGuardHistoryOpen((v) => !v); if (!guardHistoryOpen && guardHistory.length === 0) loadGuardHistory(); }}
                  className="rounded bg-gray-800 px-2 py-1 text-xs hover:bg-gray-700"
                >
                  {guardHistoryOpen ? "Hide" : "Show"}
                </button>
                {guardHistoryOpen && (
                  <button
                    onClick={loadGuardHistory}
                    disabled={guardHistoryLoading}
                    className="rounded bg-gray-800 px-2 py-1 text-xs hover:bg-gray-700 disabled:text-gray-600"
                  >
                    {guardHistoryLoading ? "Loading..." : "Refresh"}
                  </button>
                )}
              </div>
            </div>
            {guardHistoryOpen && (
              <div className="mt-2 space-y-2">
                {guardHistory.length === 0 && !guardHistoryLoading && (
                  <p className="text-xs text-gray-600">No persisted guard results for this step.</p>
                )}
                {guardHistory.map((gr) => (
                  <div
                    key={gr.id}
                    onClick={() => {
                      setSelectedGuardResultId((prev) => prev === gr.id ? null : gr.id);
                      setGuardValidation(null);
                      setGuardValidationError("");
                      setGuardNoCheckOverride(false);
                    }}
                    className={`cursor-pointer rounded border p-2 ${selectedGuardResultId === gr.id ? "border-emerald-700 bg-emerald-950/20" : "border-gray-800 bg-gray-900 hover:border-gray-700"}`}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardGateClass(gr.decision)}`}>{gr.decision}</span>
                      <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardRiskClass(gr.drift_risk)}`}>drift: {gr.drift_risk}</span>
                      {gr.is_stale && <span className="rounded bg-orange-900/50 px-2 py-0.5 text-orange-300">stale</span>}
                      {selectedGuardResultId === gr.id && <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-emerald-300">selected</span>}
                    </div>
                    <p className="mt-1 text-gray-500 font-mono text-[10px]">{gr.id}</p>
                    {gr.proposed_action && <p className="mt-1 text-gray-400 truncate">{gr.proposed_action}</p>}
                    {gr.file_path && <p className="mt-0.5 text-gray-500 font-mono">{gr.file_path}</p>}
                    <p className="mt-0.5 text-gray-600">{gr.created_at}</p>
                    {gr.is_stale && gr.stale_reasons.length > 0 && (
                      <p className="mt-0.5 text-orange-400">Stale: {gr.stale_reasons.join(", ")}</p>
                    )}
                    {gr.matched_requirement_ids.length > 0 && (
                      <p className="mt-0.5 text-gray-500">Reqs: {gr.matched_requirement_ids.join(", ")}</p>
                    )}
                    <div className="mt-1 flex flex-wrap gap-1">
                      {gr.proposal_tool_call_id && (
                        <span className="rounded bg-blue-900/40 px-1.5 py-0.5 text-blue-300">proposal linked</span>
                      )}
                      {gr.apply_tool_call_id && (
                        <span className="rounded bg-emerald-900/40 px-1.5 py-0.5 text-emerald-300">apply linked</span>
                      )}
                    </div>
                  </div>
                ))}
                {selectedGuardResultId && (
                  <div className="rounded border border-gray-800 bg-gray-900 p-2 space-y-2">
                    <p className="text-xs text-gray-400">Selected guard result: <span className="font-mono text-gray-300">{selectedGuardResultId}</span></p>
                    <button
                      onClick={handleValidateGuard}
                      disabled={guardValidationLoading}
                      className="rounded bg-gray-800 px-3 py-1.5 text-xs hover:bg-gray-700 disabled:text-gray-600"
                    >
                      {guardValidationLoading ? "Validating..." : "Validate selected guard for proposal"}
                    </button>
                    {guardValidationError && <p className="text-xs text-red-300">{guardValidationError}</p>}
                    {guardValidation && (
                      <div className={`rounded border p-2 ${guardValidation.valid ? "border-emerald-800 bg-emerald-950/20" : "border-red-800 bg-red-950/20"}`}>
                        <div className="flex flex-wrap items-center gap-2">
                          <span className={`rounded px-2 py-0.5 font-medium ${guardValidation.valid ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
                            {guardValidation.valid ? "valid" : "invalid"}
                          </span>
                          <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardGateClass(guardValidation.decision)}`}>{guardValidation.decision}</span>
                          {guardValidation.is_stale && <span className="rounded bg-orange-900/50 px-2 py-0.5 text-orange-300">stale</span>}
                        </div>
                        {guardValidation.blocking_reasons.length > 0 && (
                          <div className="mt-1">
                            <p className="text-red-300">Blocking: {guardValidation.blocking_reasons.join("; ")}</p>
                          </div>
                        )}
                        {guardValidation.warnings.length > 0 && (
                          <div className="mt-1">
                            <p className="text-yellow-300">Warnings: {guardValidation.warnings.join("; ")}</p>
                          </div>
                        )}
                        {guardValidation.requires_warning_acknowledgement && (
                          <p className="mt-1 text-yellow-300">Requires warning acknowledgement before proposal.</p>
                        )}
                        {guardValidation.recommended_next_step && (
                          <p className="mt-1 text-emerald-400">{guardValidation.recommended_next_step}</p>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
          <div className="rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-400">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-medium text-gray-300">Patch proposal guard status</span>
              <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardGateClass(proposalGuardStatus)}`}>
                {proposalGuardStatus === "not_checked" ? "not checked" : proposalGuardStatus}
              </span>
            </div>
            <p className="mt-2 text-gray-500">
              Source-of-truth guard does not create or apply patches. It only checks whether the intended change matches the confirmed requirements.
            </p>
            {selectedGuardResultId && !guardValidation && (
              <div className="mt-2 rounded border border-yellow-900/60 bg-yellow-950/20 p-2 text-yellow-300">
                Validate the selected persisted guard result before creating a patch proposal.
              </div>
            )}
            {guardValidation && !guardValidation.valid && (
              <div className="mt-2 rounded border border-red-900/60 bg-red-950/30 p-2 text-red-300">
                Selected guard result is not valid for this patch proposal. Proposal creation is disabled.
              </div>
            )}
            {!selectedGuardResultId && (
              <div className="mt-2 space-y-2 rounded border border-yellow-900/60 bg-yellow-950/20 p-2">
                <p className="text-yellow-300">Select and validate a persisted guard result before creating a patch proposal.</p>
                <label className="flex items-start gap-2 text-yellow-100">
                  <input
                    type="checkbox"
                    checked={guardNoCheckOverride}
                    onChange={(event) => setGuardNoCheckOverride(event.target.checked)}
                  />
                  <span>Create proposal without guard check</span>
                </label>
              </div>
            )}
            {selectedGuardResultId && guardValidation?.decision === "warning" && (
              <div className="mt-2 space-y-2 rounded border border-yellow-900/60 bg-yellow-950/20 p-2">
                <p className="text-yellow-300">Guard returned warning. Review the warning details before creating a proposal.</p>
                <label className="flex items-start gap-2 text-yellow-100">
                  <input
                    type="checkbox"
                    checked={guardWarningAcknowledged}
                    onChange={(event) => setGuardWarningAcknowledged(event.target.checked)}
                  />
                  <span>I understand the guard warning and want to continue.</span>
                </label>
              </div>
            )}
            {selectedGuardResultId && guardValidation?.decision === "blocked" && (
              <div className="mt-2 rounded border border-red-900/60 bg-red-950/30 p-2 text-red-300">
                Guard blocked this proposed action. Patch proposal creation is disabled until the blocked reasons are resolved.
              </div>
            )}
          </div>
          {/* Prefill context banner */}
          {issueContext && (
            <div className="rounded border border-blue-800 bg-blue-950/20 p-2 space-y-1">
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-blue-300">Issue context (pre-filled from analysis)</p>
                <button onClick={() => setIssueContext(null)} className="text-xs text-gray-500 hover:text-gray-300">dismiss</button>
              </div>
              <p className="text-xs text-gray-400">
                <span className="rounded bg-blue-900 px-1 py-0.5 text-blue-400 mr-1">{issueContext.context_kind}</span>
                <span className="font-mono">{issueContext.context_location}</span>
              </p>
              <p className="text-xs text-gray-300">{issueContext.context_message}</p>
              <p className="text-xs text-yellow-400 border-t border-blue-900 pt-1">
                ⚠ This only pre-fills proposal context. It does not generate or apply a fix.
              </p>
            </div>
          )}
          {error && (
            <div className="rounded border border-red-800 bg-red-950/30 p-2 text-xs text-red-300">{error}</div>
          )}
          <label className="block">
            <span className="mb-1 block text-xs text-gray-500">File path</span>
            <input
              value={form.file_path}
              onChange={(event) => update("file_path", event.target.value)}
              placeholder="src/example.ts"
              className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-xs focus:border-emerald-500 focus:outline-none"
            />
          </label>
          <div className="grid gap-3 lg:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-xs text-gray-500">Old text</span>
              <textarea
                value={form.old_text}
                onChange={(event) => update("old_text", event.target.value)}
                rows={5}
                className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-xs focus:border-emerald-500 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-xs text-gray-500">New text</span>
              <textarea
                value={form.new_text}
                onChange={(event) => update("new_text", event.target.value)}
                rows={5}
                className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-xs focus:border-emerald-500 focus:outline-none"
              />
            </label>
          </div>
          <div className="flex flex-wrap items-center gap-4 text-xs text-gray-400">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.create_if_missing}
                onChange={(event) => update("create_if_missing", event.target.checked)}
              />
              Create if missing
            </label>
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={form.replace_all}
                onChange={(event) => update("replace_all", event.target.checked)}
              />
              Replace all
            </label>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleReview}
              disabled={loading !== ""}
              className="rounded bg-gray-700 px-3 py-1.5 text-xs hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-500"
            >
              {loading === "review" ? "Reviewing..." : "Review Patch"}
            </button>
            <button
              onClick={handlePreview}
              disabled={loading !== "" || !canCreateProposalWithGuard}
              className="rounded bg-emerald-700 px-3 py-1.5 text-xs hover:bg-emerald-600 disabled:bg-gray-700 disabled:text-gray-500"
            >
              {loading === "preview" ? "Previewing..." : "Preview Patch"}
            </button>
          </div>

          {reviewResult && (
            <PatchReviewPanel result={reviewResult} onDismiss={() => setReviewResult(null)} />
          )}

          {preview && (
            <div className="space-y-3 rounded border border-gray-800 bg-gray-950 p-3">
              <p className="text-xs text-gray-300">{preview.summary}</p>
              {preview.proposal_id && <p className="font-mono text-xs text-gray-500">proposal: {preview.proposal_id}</p>}
              {preview.guard_result_id && (
                <p className="font-mono text-xs text-emerald-400">Guard result linked: {preview.guard_result_id}</p>
              )}
              {preview.no_guard_override && (
                <p className="text-xs text-orange-300">Created with explicit no-guard override.</p>
              )}
              {preview.guard_validation_warnings && preview.guard_validation_warnings.length > 0 && (
                <p className="text-xs text-yellow-300">{preview.guard_validation_warnings.join("; ")}</p>
              )}
              {preview.module_awareness?.has_active_module_map && (
                <div className="space-y-2 rounded border border-sky-900 bg-sky-950/20 p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-sky-300">Module awareness</span>
                    {preview.module_awareness.module_map_version != null && (
                      <span className="text-gray-500">v{preview.module_awareness.module_map_version}</span>
                    )}
                    <span className="text-gray-500">confidence: {preview.module_awareness.confidence}</span>
                  </div>
                  {preview.module_awareness.touched_modules.length > 0 && (
                    <p className="text-gray-300">
                      <span className="text-gray-500">Touched:</span>{" "}
                      {preview.module_awareness.touched_modules.map((mod) => mod.name || mod.slug || mod.id).join(", ")}
                    </p>
                  )}
                  {preview.module_awareness.expected_modules.length > 0 && (
                    <p className="text-gray-300">
                      <span className="text-gray-500">Expected:</span>{" "}
                      {preview.module_awareness.expected_modules.map((mod) => mod.name || mod.slug || mod.id).join(", ")}
                    </p>
                  )}
                  {preview.module_awareness.warnings.length > 0 && (
                    <p className="text-yellow-300">{preview.module_awareness.warnings.join("; ")}</p>
                  )}
                  {preview.module_awareness.module_risks.length > 0 && (
                    <p className="text-orange-300">
                      <span className="text-gray-500">Risks:</span> {preview.module_awareness.module_risks.join("; ")}
                    </p>
                  )}
                  {preview.module_awareness.module_test_hints.length > 0 && (
                    <p className="text-emerald-300">
                      <span className="text-gray-500">Test hints:</span> {preview.module_awareness.module_test_hints.join("; ")}
                    </p>
                  )}
                </div>
              )}
              {preview.module_policy && (
                <div className="space-y-2 rounded border border-purple-900 bg-purple-950/20 p-2 text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-purple-300">Module policy</span>
                    <span className={
                      preview.module_policy.verdict === "blocked"
                        ? "text-red-300"
                        : preview.module_policy.verdict === "warning"
                          ? "text-yellow-300"
                          : "text-emerald-300"
                    }>
                      {preview.module_policy.verdict}
                    </span>
                    <span className="text-gray-500">confidence: {preview.module_policy.confidence}</span>
                  </div>
                  {preview.module_policy.reasons.length > 0 && (
                    <p className="text-gray-300">{preview.module_policy.reasons.join("; ")}</p>
                  )}
                  {preview.module_policy.required_acknowledgements.length > 0 && (
                    <p className="text-yellow-300">
                      <span className="text-gray-500">Review:</span> {preview.module_policy.required_acknowledgements.join("; ")}
                    </p>
                  )}
                  {preview.module_policy.recommended_tests.length > 0 && (
                    <p className="text-emerald-300">
                      <span className="text-gray-500">Recommended tests:</span> {preview.module_policy.recommended_tests.join("; ")}
                    </p>
                  )}
                </div>
              )}
              {preview.files.map((file) => (
                <div key={file.path}>
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
                    <span className={`rounded px-2 py-0.5 ${patchStatusClass(file.status)}`}>{file.status}</span>
                    <span className="font-mono text-gray-300">{file.path}</span>
                    {file.error && <span className="text-red-300">{file.error}</span>}
                  </div>
                  {file.diff && (
                    <pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-2 text-xs text-gray-300">
                      {file.diff}
                    </pre>
                  )}
                </div>
              ))}
              <label className="flex items-start gap-2 text-xs text-yellow-200">
                <input
                  type="checkbox"
                  checked={confirmed}
                  onChange={(event) => setConfirmed(event.target.checked)}
                  disabled={preview.files.some((file) => file.status === "error") || loading !== ""}
                />
                <span>I understand this will modify files in the selected project workspace.</span>
              </label>
              <button
                onClick={handleApply}
                disabled={!canApply}
                className="rounded bg-red-800 px-3 py-1.5 text-xs hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500"
              >
                {loading === "apply" ? "Applying..." : "Apply Patch"}
              </button>
            </div>
          )}

          {applyResult && (
            <div className="rounded border border-emerald-900 bg-emerald-950/20 p-3 text-xs text-emerald-100">
              <p>{applyResult.summary}</p>
              {applyResult.applied_from_proposal_id && (
                <p className="mt-1 font-mono text-gray-400">applied from: {applyResult.applied_from_proposal_id}</p>
              )}
              {applyResult.guard_result_id && (
                <p className="mt-1 font-mono text-emerald-300">guard revalidated: {applyResult.guard_result_id}</p>
              )}
              {applyResult.no_guard_override && (
                <p className="mt-1 text-orange-300">Applied from proposal created with explicit no-guard override.</p>
              )}
              <p className="mt-2 text-yellow-200">Next manual step: run tests.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PatchLifecyclePanel({
  lifecycle,
  loading,
  error,
  manualTestRunning,
  manualAnalysisLoading,
  manualAnalysis,
  fixDraft,
  fixDraftLoading,
  fixDraftError,
  onRefresh,
  onRunTests,
  onAnalyzeFailedTests,
  onPrepareFixDraft,
  onPrefillFromFixDraft,
}: {
  lifecycle: StepPatchLifecycleResponse | null;
  loading: boolean;
  error: string;
  manualTestRunning: boolean;
  manualAnalysisLoading: boolean;
  manualAnalysis: CommandAnalysisResponse | null;
  fixDraft: FailureToFixDraftResponse | null;
  fixDraftLoading: boolean;
  fixDraftError: string;
  onRefresh: () => void;
  onRunTests: () => void;
  onAnalyzeFailedTests: () => void;
  onPrepareFixDraft: () => void;
  onPrefillFromFixDraft: () => void;
}) {
  const latestTest = lifecycle?.latest_test ?? null;
  const canRunTests = Boolean(lifecycle?.apply_succeeded && lifecycle.safe_test_command_configured);
  const canAnalyze = Boolean(latestTest && lifecycle?.test_status === "failed");
  const canPrepareFixDraft = Boolean(lifecycle?.test_status === "failed" && latestTest);

  return (
    <div className="rounded border border-gray-800 bg-gray-950 p-3 text-xs text-gray-400">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="font-medium text-gray-300">Patch-Test Lifecycle</p>
          <p className="mt-1 text-gray-500">
            Manual lifecycle view only. It does not create patches, apply changes, run tests, or analyze results without a click.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-800 px-3 py-1.5 text-xs hover:bg-gray-700 disabled:text-gray-600"
        >
          {loading ? "Refreshing..." : "Refresh lifecycle"}
        </button>
      </div>

      {error && <div className="mt-2 rounded border border-red-800 bg-red-950/30 p-2 text-red-300">{error}</div>}

      {lifecycle ? (
        <div className="mt-3 space-y-3">
          <div className="grid gap-2 md:grid-cols-4">
            <LifecycleStatus label="Guard" value={lifecycle.guard_results.length > 0 ? "available" : "missing"} tone={lifecycle.guard_results.length > 0 ? "ok" : "warn"} />
            <LifecycleStatus label="Proposal" value={lifecycle.latest_proposal ? lifecycle.latest_proposal.status : "not created"} tone={lifecycle.latest_proposal ? "ok" : "warn"} />
            <LifecycleStatus label="Apply" value={lifecycle.apply_succeeded ? "completed" : "not applied"} tone={lifecycle.apply_succeeded ? "ok" : "warn"} />
            <LifecycleStatus label="Tests" value={lifecycle.test_status === "not_run" ? "not run" : lifecycle.test_status} tone={lifecycle.test_status === "passed" ? "ok" : lifecycle.test_status === "failed" ? "bad" : "warn"} />
          </div>

          <div className="flex flex-wrap gap-2">
            {lifecycle.latest_proposal?.guard_result_id && (
              <span className="rounded bg-blue-900/40 px-2 py-0.5 text-blue-300">
                Guard linked: {shortId(lifecycle.latest_proposal.guard_result_id)}
              </span>
            )}
            {lifecycle.latest_apply?.guard_revalidated && (
              <span className="rounded bg-emerald-900/40 px-2 py-0.5 text-emerald-300">Guard revalidated before apply</span>
            )}
            {(lifecycle.latest_proposal?.no_guard_override || lifecycle.latest_apply?.no_guard_override) && (
              <span className="rounded bg-orange-900/40 px-2 py-0.5 text-orange-300">No-guard override</span>
            )}
            <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-400">
              Next: {manualNextActionLabel(lifecycle.recommended_manual_next_action)}
            </span>
          </div>

          {lifecycle.confidence_reasons.length > 0 && (
            <ul className="space-y-1 rounded border border-gray-800 bg-gray-900 p-2 text-gray-500">
              {lifecycle.confidence_reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={onRunTests}
              disabled={!canRunTests || manualTestRunning}
              className="rounded bg-purple-800 px-3 py-1.5 text-xs text-purple-100 hover:bg-purple-700 disabled:bg-gray-800 disabled:text-gray-600"
            >
              {manualTestRunning ? "Running tests..." : "Run tests manually"}
            </button>
            <button
              onClick={onAnalyzeFailedTests}
              disabled={!canAnalyze || manualAnalysisLoading}
              className="rounded bg-gray-800 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-700 disabled:text-gray-600"
            >
              {manualAnalysisLoading ? "Analyzing..." : "Analyze failed tests manually"}
            </button>
            <button
              onClick={onPrepareFixDraft}
              disabled={!canPrepareFixDraft || fixDraftLoading}
              title={canPrepareFixDraft ? "Build fix draft context from the failed test output. Does not create a proposal or apply anything." : "No failed test command found. Run tests manually first."}
              className="rounded bg-orange-900 px-3 py-1.5 text-xs text-orange-100 hover:bg-orange-800 disabled:bg-gray-800 disabled:text-gray-600"
            >
              {fixDraftLoading ? "Preparing draft..." : "Prepare fix draft from failed tests"}
            </button>
          </div>

          {!lifecycle.safe_test_command_configured && (
            <p className="text-yellow-300">No safe test command configured. Configure Project Profile `test_command` before running tests here.</p>
          )}

          {latestTest ? (
            <div className="rounded border border-gray-800 bg-gray-900 p-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2 py-0.5 ${lifecycle.test_status === "passed" ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
                  {lifecycle.test_status}
                </span>
                <span className="font-mono text-gray-400">{latestTest.command}</span>
                <span className="text-gray-500">exit {latestTest.returncode ?? "n/a"}</span>
              </div>
              {latestTest.stdout_preview && <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap text-gray-500">{latestTest.stdout_preview}</pre>}
              {latestTest.stderr_preview && <pre className="mt-2 max-h-24 overflow-auto whitespace-pre-wrap text-gray-500">{latestTest.stderr_preview}</pre>}
            </div>
          ) : (
            <p className="text-gray-600">No test command linked to this step yet.</p>
          )}

          {fixDraftError && (
            <div className="rounded border border-red-800 bg-red-950/30 p-2 text-red-300">{fixDraftError}</div>
          )}

          {fixDraft && (
            <div className="rounded border border-orange-900/60 bg-orange-950/20 p-2 space-y-2">
              <div className="flex items-center justify-between">
                <p className="font-medium text-orange-300">Fix draft context</p>
                <div className="flex gap-2">
                  <button
                    onClick={() => navigator.clipboard?.writeText(fixDraft.fix_context)}
                    className="rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-300 hover:bg-gray-700"
                    title="Copy fix context to clipboard"
                  >
                    Copy
                  </button>
                  <button
                    onClick={onPrefillFromFixDraft}
                    className="rounded bg-blue-800 px-2 py-0.5 text-xs text-blue-200 hover:bg-blue-700"
                    title="Prefill the patch form context/issue field with this fix draft. Does not create a proposal or apply anything."
                  >
                    Prefill patch context ↓
                  </button>
                </div>
              </div>
              <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-gray-300 text-[11px]">{fixDraft.fix_context}</pre>
              {fixDraft.warnings.length > 0 && (
                <ul className="space-y-0.5 text-yellow-400">
                  {fixDraft.warnings.map((w, i) => <li key={i}>⚠ {w}</li>)}
                </ul>
              )}
              <p className="text-[10px] text-orange-500 border-t border-orange-900/40 pt-1">
                Fix draft is read-only context. It does not create a proposal, apply a patch, run tests, or call providers.
              </p>
            </div>
          )}

          {!fixDraft && lifecycle.test_status === "failed" && latestTest && (
            <div className="rounded border border-yellow-900/60 bg-yellow-950/20 p-2">
              <p className="font-medium text-yellow-300">Failure context for next patch</p>
              <pre className="mt-1 max-h-36 overflow-auto whitespace-pre-wrap text-gray-400">
{`Latest test tool_call: ${latestTest.tool_call_id}
Command: ${latestTest.command}
Return code: ${latestTest.returncode ?? "n/a"}
Guard result: ${lifecycle.latest_apply?.guard_result_id || lifecycle.latest_proposal?.guard_result_id || "none"}
Suggested manual next action: click "Prepare fix draft from failed tests" above.`}
              </pre>
            </div>
          )}

          {manualAnalysis && (
            <div className="rounded border border-gray-800 bg-gray-900 p-2">
              <p className="font-medium text-gray-300">Manual analysis result</p>
              <p className="mt-1 text-gray-400">{manualAnalysis.summary}</p>
              {manualAnalysis.issues.length > 0 && (
                <ul className="mt-2 space-y-1 text-gray-500">
                  {manualAnalysis.issues.slice(0, 5).map((issue, index) => (
                    <li key={`${issue.kind}-${index}`}>
                      {issue.kind}: {issue.message}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      ) : (
        <p className="mt-3 text-gray-600">Refresh lifecycle to inspect guard, proposal, apply, and manual test state for this step.</p>
      )}
    </div>
  );
}

function LifecycleStatus({ label, value, tone }: { label: string; value: string; tone: "ok" | "warn" | "bad" }) {
  const toneClass = tone === "ok"
    ? "border-emerald-900 bg-emerald-950/20 text-emerald-300"
    : tone === "bad"
      ? "border-red-900 bg-red-950/20 text-red-300"
      : "border-yellow-900 bg-yellow-950/20 text-yellow-300";
  return (
    <div className={`rounded border px-2 py-1.5 ${toneClass}`}>
      <p className="text-[10px] uppercase tracking-wide opacity-70">{label}</p>
      <p className="mt-0.5 font-medium">{value}</p>
    </div>
  );
}

function SourceOfTruthGuardPanel({ result }: { result: StepSourceOfTruthGuardResponse }) {
  const guard = result.guard_result;

  return (
    <div className="mt-3 rounded border border-gray-800 bg-gray-900 p-3 text-xs">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardDecisionClass(guard.decision)}`}>
          {guard.decision}
        </span>
        <span className={`rounded px-2 py-0.5 font-medium ${sourceGuardRiskClass(guard.drift_risk)}`}>
          drift: {guard.drift_risk}
        </span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-gray-500">
          context: {result.has_requirement_context ? "found" : "missing"}
        </span>
      </div>
      {guard.recommended_next_step && (
        <p className="mt-2 text-emerald-400">{guard.recommended_next_step}</p>
      )}
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        <GuardList title="Matched requirements" items={guard.matched_requirement_ids} empty="No matched requirements." />
        <GuardList title="Violated constraints" items={guard.violated_constraints} empty="No violated constraints." />
        <GuardList title="Forbidden change hits" items={guard.forbidden_change_hits} empty="No forbidden changes hit." />
        <GuardList title="Warnings" items={guard.warnings} empty="No warnings." />
        <GuardList title="Reasons" items={guard.reasons} empty="No reasons returned." />
        <GuardList title="Parsed requirement ids" items={result.parsed_context.requirement_ids} empty="No parsed requirement ids." />
      </div>
    </div>
  );
}

function GuardList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="font-medium text-gray-300">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-gray-600">{empty}</p>
      ) : (
        <ul className="mt-1 space-y-1 text-gray-400">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function sourceGuardDecisionClass(decision: StepSourceOfTruthGuardResponse["guard_result"]["decision"]): string {
  if (decision === "blocked") return "bg-red-900/50 text-red-300";
  if (decision === "warning") return "bg-yellow-900/50 text-yellow-300";
  return "bg-emerald-900/50 text-emerald-300";
}

function sourceGuardGateClass(decision: string): string {
  if (decision === "blocked") return "bg-red-900/50 text-red-300";
  if (decision === "warning" || decision === "not_checked") return "bg-yellow-900/50 text-yellow-300";
  if (decision === "override") return "bg-orange-900/50 text-orange-300";
  return "bg-emerald-900/50 text-emerald-300";
}

function sourceGuardGateMessage(
  result: StepSourceOfTruthGuardResponse | null,
  noCheckOverride: boolean,
  warningAcknowledged: boolean,
  selectedGuardResultId?: string | null,
  validation?: GuardProposalValidationResponse | null,
): string {
  if (selectedGuardResultId && !validation) {
    return "Validate the selected persisted guard result before creating a patch proposal.";
  }
  if (selectedGuardResultId && validation && !validation.valid) {
    return "Selected guard result is not valid for this patch proposal. Run a fresh guard check or choose a different guard result.";
  }
  if (!result && !noCheckOverride) {
    return "Select and validate a persisted guard result before creating a patch proposal, or explicitly choose the no-guard override.";
  }
  if (result?.guard_result.decision === "warning" && !warningAcknowledged) {
    return "Guard returned warning. Acknowledge the warning before creating a patch proposal.";
  }
  if (result?.guard_result.decision === "blocked") {
    return "Guard blocked this proposed action. Resolve the blocked reasons before creating a patch proposal.";
  }
  return "";
}

function formatGuardContextPrefillMessage(result: StepSourceOfTruthGuardResponse, proposedAction: string): string {
  const guard = result.guard_result;
  const parts = [
    `Proposed action: ${proposedAction}`,
    `Guard decision: ${guard.decision}`,
    `Drift risk: ${guard.drift_risk}`,
  ];
  if (guard.matched_requirement_ids.length > 0) {
    parts.push(`Matched requirements: ${guard.matched_requirement_ids.join(", ")}`);
  }
  if (guard.warnings.length > 0) {
    parts.push(`Warnings: ${guard.warnings.join("; ")}`);
  }
  if (guard.reasons.length > 0) {
    parts.push(`Reasons: ${guard.reasons.join("; ")}`);
  }
  if (guard.recommended_next_step) {
    parts.push(`Recommended next step: ${guard.recommended_next_step}`);
  }
  return parts.join("\n");
}

function sourceGuardRiskClass(risk: string): string {
  if (risk === "critical" || risk === "high") return "bg-red-900/50 text-red-300";
  if (risk === "medium") return "bg-yellow-900/50 text-yellow-300";
  return "bg-emerald-900/50 text-emerald-300";
}

function PatchReviewPanel({
  result,
  onDismiss,
}: {
  result: PatchReviewResponse;
  onDismiss: () => void;
}) {
  const borderColor =
    result.status === "blocked"
      ? "border-red-800"
      : result.status === "warning"
      ? "border-yellow-800"
      : "border-emerald-800";
  const bgColor =
    result.status === "blocked"
      ? "bg-red-950/20"
      : result.status === "warning"
      ? "bg-yellow-950/20"
      : "bg-emerald-950/20";
  const statusLabel =
    result.status === "blocked"
      ? "🔴 BLOCKED"
      : result.status === "warning"
      ? "⚠ WARNING"
      : "✓ OK";
  const statusColor =
    result.status === "blocked"
      ? "text-red-300"
      : result.status === "warning"
      ? "text-yellow-300"
      : "text-emerald-300";

  const severityColor = (s: PatchReviewIssue["severity"]) =>
    s === "blocker" ? "text-red-400" : s === "warning" ? "text-yellow-300" : "text-blue-300";
  const severityBg = (s: PatchReviewIssue["severity"]) =>
    s === "blocker" ? "bg-red-900" : s === "warning" ? "bg-yellow-900" : "bg-blue-900";

  return (
    <div className={`rounded border ${borderColor} ${bgColor} p-3 space-y-2`}>
      <div className="flex items-center justify-between">
        <span className={`text-xs font-semibold ${statusColor}`}>{statusLabel} — Patch Review</span>
        <button onClick={onDismiss} className="text-xs text-gray-500 hover:text-gray-300">dismiss</button>
      </div>
      <p className="text-xs text-gray-300">{result.summary}</p>

      <div className="flex flex-wrap gap-3 text-xs">
        <span className={result.safe_to_create_proposal ? "text-emerald-400" : "text-red-400"}>
          {result.safe_to_create_proposal ? "✓ Safe to create proposal" : "✗ Unsafe to create proposal"}
        </span>
        <span className={result.safe_to_apply ? "text-emerald-400" : "text-red-400"}>
          {result.safe_to_apply ? "✓ Safe to apply" : "✗ Unsafe to apply"}
        </span>
      </div>

      {result.issues.length > 0 && (
        <div className="space-y-1">
          {result.issues.map((issue, i) => (
            <div key={i} className="flex flex-wrap items-start gap-2 rounded bg-gray-900 px-2 py-1.5 text-xs">
              <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${severityBg(issue.severity)} ${severityColor(issue.severity)}`}>
                {issue.severity}
              </span>
              <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">{issue.code}</span>
              <span className="text-gray-300 flex-1">{issue.message}</span>
            </div>
          ))}
        </div>
      )}

      {result.status === "blocked" && (
        <p className="text-xs text-red-300 border-t border-red-900 pt-1">
          Resolve the blocker(s) above before creating a proposal or applying this patch.
        </p>
      )}
    </div>
  );
}

// ── Patch Workflow Panel ──────────────────────────────────────────────────────

const WORKFLOW_MODE_LABELS: Record<WorkflowAutomationMode, string> = {
  manual: "Manual",
  guided: "Guided",
  safe_prep: "Safe Prep",
};

const WORKFLOW_MODE_DESCRIPTIONS: Record<WorkflowAutomationMode, string> = {
  manual: "Actions only focus existing UI. No direct workflow execution.",
  guided: "Individual read-only actions can run. Manual actions stay manual.",
  safe_prep: "Run Safe Prep can gather context, build bundle, create draft, then stop.",
};

const WORKFLOW_MODE_OPTIONS: Array<{ value: WorkflowAutomationMode; label: string }> = [
  { value: "manual", label: WORKFLOW_MODE_LABELS.manual },
  { value: "guided", label: WORKFLOW_MODE_LABELS.guided },
  { value: "safe_prep", label: WORKFLOW_MODE_LABELS.safe_prep },
];

const WORKFLOW_MODE_POLICY_LINES = WORKFLOW_BOUNDARY_SUMMARY_LINES;

type PatchWorkflowRefresh = () => void | Promise<void>;

type PatchWorkflowPanelProps = {
  runId: string;
  steps: RunStep[];
  plan: PatchWorkflowPlanResponse | null;
  activeStepId: string | null;
  loading: boolean;
  error: string;
  workflowMode: WorkflowAutomationMode;
  onWorkflowModeChange: (mode: WorkflowAutomationMode) => void;
  onRefresh: PatchWorkflowRefresh;
  onActiveStepChange: (stepId: string | null) => void;
  onGuidedRefresh?: PatchWorkflowRefresh;
  onToolCallsRefresh?: PatchWorkflowRefresh;
  onFocusManualAction: (stepId: string, actionType: string) => Promise<ManualFocusResult>;
  onUseDraft?: (stepId: string, candidate: ContextPatchDraftCandidate) => void;
};

function PatchWorkflowPanel({
  runId,
  steps,
  plan,
  activeStepId,
  loading,
  error,
  workflowMode,
  onWorkflowModeChange,
  onRefresh,
  onActiveStepChange,
  onGuidedRefresh,
  onToolCallsRefresh,
  onFocusManualAction,
  onUseDraft,
}: PatchWorkflowPanelProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Patch Workflow Planner</h3>
          <p className="mt-1 text-xs text-gray-500">
            Use this tab as the main operator cockpit. Diagnostics are still available in Tool Plan and Guided tabs.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-800 px-3 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
        >
          {loading ? "Loading..." : "Refresh Plan"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/20 p-3 text-sm text-red-300">{error}</div>
      )}

      {!plan && !loading && !error && (
        <p className="text-sm text-gray-500">Click "Refresh Plan" to analyse the workflow state for this run.</p>
      )}

      {plan && (
        <div className="space-y-2">
          <PatchWorkflowCockpitCard
            runId={runId}
            plan={plan}
            steps={steps}
            activeStepId={activeStepId}
            workflowMode={workflowMode}
            onWorkflowModeChange={onWorkflowModeChange}
            onActiveStepChange={onActiveStepChange}
            onRefresh={onRefresh}
            onGuidedRefresh={onGuidedRefresh}
            onToolCallsRefresh={onToolCallsRefresh}
          />
          <p className="text-xs text-gray-400">{plan.summary}</p>
          {plan.warnings.length > 0 && (
            <div className="space-y-1">
              {plan.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-400">⚠ {w}</p>
              ))}
            </div>
          )}
          {plan.steps.length === 0 ? (
            <p className="text-sm text-gray-500">No steps found for this run.</p>
          ) : (
            <div className="space-y-4">
              {plan.steps.map((stepPlan) => (
                <StepWorkflowCard
                  key={stepPlan.step_id}
                  runId={runId}
                  plan={stepPlan}
                  workflowMode={workflowMode}
                  onRefresh={onRefresh}
                  onGuidedRefresh={onGuidedRefresh}
                  onToolCallsRefresh={onToolCallsRefresh}
                  onFocusManualAction={onFocusManualAction}
                  onUseDraft={onUseDraft}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function PatchWorkflowCockpitCard({
  runId,
  plan,
  steps,
  activeStepId,
  workflowMode,
  onWorkflowModeChange,
  onActiveStepChange,
  onRefresh,
  onGuidedRefresh,
  onToolCallsRefresh,
}: {
  runId: string;
  plan: PatchWorkflowPlanResponse;
  steps: RunStep[];
  activeStepId: string | null;
  workflowMode: WorkflowAutomationMode;
  onWorkflowModeChange: (mode: WorkflowAutomationMode) => void;
  onActiveStepChange: (stepId: string | null) => void;
  onRefresh: PatchWorkflowRefresh;
  onGuidedRefresh?: PatchWorkflowRefresh;
  onToolCallsRefresh?: PatchWorkflowRefresh;
}) {
  const firstActionable = plan.steps.find((step) => {
    return step.recommended_next_action && step.recommended_next_action.action_type !== "done";
  });
  const pinnedStep = activeStepId ? plan.steps.find((step) => step.step_id === activeStepId) || null : null;
  const actionable = pinnedStep || firstActionable;
  const pinnedMissing = Boolean(activeStepId && !pinnedStep);
  const pinnedDone = Boolean(pinnedStep?.recommended_next_action?.action_type === "done" || pinnedStep?.status === "done");

  // ── Safe Prep runner state ──
  const [safePrepRunning, setSafePrepRunning] = useState(false);
  const [safePrepStep, setSafePrepStep] = useState<string>("");
  const [safePrepError, setSafePrepError] = useState<string>("");
  const [safePrepResult, setSafePrepResult] = useState<string>("");

  const SAFE_PREP_SEQUENCE = ["auto_gather_context", "build_context_bundle", "create_patch_draft"] as const;

  const safePrepStepLabel = (action: string) =>
    action === "auto_gather_context" ? "Gathering context..." :
    action === "build_context_bundle" ? "Building context bundle..." :
    action === "create_patch_draft" ? "Creating patch draft..." : action;

  const isManualOnly = actionable?.recommended_next_action
    ? MANUAL_WORKFLOW_ACTIONS.has(actionable.recommended_next_action.action_type)
    : false;

  const handleSafePrep = async () => {
    if (!actionable || safePrepRunning) return;
    setSafePrepRunning(true);
    setSafePrepError("");
    setSafePrepResult("");

    const stepId = actionable.step_id;
    const agentId = actionable.agent_id || undefined;
    const results: string[] = [];
    let currentPhase = "";

    try {
      // A. auto_gather_context
      currentPhase = "auto_gather_context";
      setSafePrepStep(currentPhase);
      const ctxRes = await runStepAutoContext(runId, stepId, {
        query: actionable.summary || stepId,
        max_tool_calls: 5,
        agent_id: agentId,
      });
      results.push(`Context: ${ctxRes.summary} (${ctxRes.tool_call_ids.length} tool calls, ${ctxRes.files_read.length} files)`);

      // B. build_context_bundle
      currentPhase = "build_context_bundle";
      setSafePrepStep(currentPhase);
      const bundleRes = await getRunStepContextBundle(runId, stepId);
      results.push(`Bundle: ${bundleRes.bundle.summary} (${bundleRes.bundle.files.length} files)`);

      // C. create_patch_draft
      currentPhase = "create_patch_draft";
      setSafePrepStep(currentPhase);
      const draftRes = await buildContextPatchDraft(runId, stepId, { agent_id: agentId });
      results.push(`Draft: ${draftRes.summary} (${draftRes.candidates.length} candidates)`);

      // D. Stop — done, refresh
      setSafePrepStep("");
      setSafePrepResult(results.join(" → "));
      await onRefresh();
      await onGuidedRefresh?.();
      await onToolCallsRefresh?.();
    } catch (e: any) {
      setSafePrepError(`Failed at "${currentPhase || "unknown"}": ${e.message ?? "Unknown error"}`);
    } finally {
      setSafePrepRunning(false);
      setSafePrepStep("");
    }
  };

  if (!actionable) {
    return (
      <div className="rounded border border-emerald-800 bg-emerald-950/20 p-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">Current actionable step</p>
            <p className="mt-1 text-sm font-medium text-emerald-100">Workflow complete</p>
          </div>
          <span className="rounded bg-emerald-900/50 px-2 py-1 text-xs text-emerald-200">done</span>
        </div>
        <WorkflowStepPicker
          plan={plan}
          steps={steps}
          activeStepId={activeStepId}
          onActiveStepChange={onActiveStepChange}
        />
        <p className="mt-2 text-xs text-emerald-200">No action needed. All workflow steps are complete or have no pending recommendation.</p>
      </div>
    );
  }

  const action = actionable.recommended_next_action || {
    action_type: "done",
    title: "No action needed",
    description: "Selected step has no pending recommended action.",
    risk_level: "low" as const,
    requires_confirmation: false,
    enabled: false,
    blocked_reason: null,
  };
  const stepTitle = steps.find((step) => step.id === actionable.step_id)?.title || actionable.summary || actionable.step_id;

  return (
    <div className="rounded border border-emerald-800 bg-emerald-950/10 p-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wide text-emerald-300">Current actionable step</p>
          <p className="mt-1 truncate text-sm font-medium text-gray-100">{stepTitle}</p>
          <div className="mt-1 flex flex-wrap gap-2 text-xs text-gray-500">
            <span className="font-mono">{shortId(actionable.step_id)}</span>
            <span>{actionable.status}</span>
            {actionable.agent_id && <span>{actionable.agent_id}</span>}
          </div>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          <span className={`rounded px-2 py-1 text-xs ${actionModeClass(action.action_type)}`}>
            {actionModeLabel(action)}
          </span>
          <span className={`rounded px-2 py-1 text-xs ${riskPillClass(action.risk_level)}`}>
            {action.risk_level}
          </span>
        </div>
      </div>

      <WorkflowStepPicker
        plan={plan}
        steps={steps}
        activeStepId={activeStepId}
        onActiveStepChange={onActiveStepChange}
        showModeStatus
        pinnedStepExists={Boolean(pinnedStep)}
        pinnedMissing={pinnedMissing}
        pinnedDone={pinnedDone}
      />

      <WorkflowModeSelector
        mode={workflowMode}
        modes={WORKFLOW_MODE_OPTIONS}
        modeDescription={WORKFLOW_MODE_DESCRIPTIONS[workflowMode]}
        savedForRunLabel="Saved for this run."
        policyTitle="Automation boundary"
        policyLines={WORKFLOW_MODE_POLICY_LINES}
        onModeChange={onWorkflowModeChange}
      />

      {/* ── Safe Prep Runner ── */}
      <div className="mt-3 rounded border border-cyan-900/60 bg-cyan-950/10 p-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-cyan-400">Safe Prep</p>
            {isManualOnly ? (
              <p className="mt-1 text-xs text-yellow-400">
                Manual only · this step is already at a manual stage.
              </p>
            ) : workflowMode === "manual" ? (
              <p className="mt-1 text-xs text-red-400">
                Blocked by Manual mode · safe prep is disabled in Manual mode.
              </p>
            ) : workflowMode === "guided" && !safePrepRunning && !safePrepResult ? (
              <p className="mt-1 text-xs text-yellow-400">
                Switch to Safe Prep mode to run the full preparation sequence.
              </p>
            ) : safePrepRunning ? (
              <p className="mt-1 text-xs text-cyan-300 animate-pulse">{safePrepStepLabel(safePrepStep)}</p>
            ) : safePrepResult ? (
              <p className="mt-1 text-xs text-gray-300">{safePrepResult}</p>
            ) : (
              <p className="mt-1 text-xs text-emerald-400">
                Allowed · read-only context + draft preparation only. No apply, no proposal.
              </p>
            )}
          </div>
          <button
            onClick={handleSafePrep}
            disabled={safePrepRunning || isManualOnly || pinnedDone || workflowMode !== "safe_prep"}
            className="whitespace-nowrap rounded bg-cyan-800 px-3 py-1.5 text-xs font-medium text-white hover:bg-cyan-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
          >
            {safePrepRunning ? `${SAFE_PREP_SEQUENCE.indexOf(safePrepStep as any) + 1}/${SAFE_PREP_SEQUENCE.length}` : "Run Safe Prep"}
          </button>
        </div>
        {safePrepError && (
          <div className="mt-2 rounded border border-red-800 bg-red-950/20 p-1.5 text-xs text-red-300">{safePrepError}</div>
        )}
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr]">
        <div className="rounded border border-gray-800 bg-gray-950/70 p-2">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Recommended next action</p>
          <p className="mt-1 text-sm font-medium text-gray-100">{action.title}</p>
          <p className="mt-1 text-xs text-gray-400">{actionInstruction(action.action_type)}</p>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950/70 p-2">
          <p className="text-[11px] uppercase tracking-wide text-gray-500">Destination</p>
          <p className="mt-1 text-sm font-medium text-gray-100">{actionDestinationLabel(action.action_type)}</p>
          <p className="mt-1 text-xs text-gray-500">{actionSafetyLabel(action)}</p>
        </div>
      </div>
    </div>
  );
}

function StepWorkflowCard({
  runId,
  plan,
  workflowMode,
  onRefresh,
  onGuidedRefresh,
  onToolCallsRefresh,
  onFocusManualAction,
  onUseDraft,
}: {
  runId: string;
  plan: StepPatchWorkflowPlan;
  workflowMode: WorkflowAutomationMode;
  onRefresh: PatchWorkflowRefresh;
  onGuidedRefresh?: PatchWorkflowRefresh;
  onToolCallsRefresh?: PatchWorkflowRefresh;
  onFocusManualAction: (stepId: string, actionType: string) => Promise<ManualFocusResult>;
  onUseDraft?: (stepId: string, candidate: ContextPatchDraftCandidate) => void;
}) {
  const [open, setOpen] = useState(true);

  const overallColor =
    plan.status === "done"
      ? "border-emerald-800"
      : plan.status === "blocked"
      ? "border-red-800"
      : plan.status === "in_progress" || plan.status === "ready_for_review" || plan.status === "ready_for_tests"
      ? "border-blue-800"
      : "border-gray-800";

  const statusBadge =
    plan.status === "done" ? "✓ done" :
    plan.status === "blocked" ? "✗ blocked" :
    plan.status === "ready_for_review" ? "→ ready for review" :
    plan.status === "ready_for_tests" ? "→ ready for tests" :
    plan.status === "in_progress" ? "⟳ in progress" : "○ not started";

  const statusColor =
    plan.status === "done" ? "text-emerald-400" :
    plan.status === "blocked" ? "text-red-400" :
    plan.status === "in_progress" || plan.status === "ready_for_review" || plan.status === "ready_for_tests" ? "text-blue-400" :
    "text-gray-500";

  return (
    <div className={`rounded border ${overallColor} bg-gray-950`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm text-gray-300 hover:text-gray-100"
      >
        <div className="flex items-center gap-3 min-w-0">
          <span className={`text-xs font-semibold ${statusColor}`}>{statusBadge}</span>
          <span className="font-medium truncate">{plan.step_id}</span>
          {plan.agent_id && <span className="text-xs text-gray-500 truncate">{plan.agent_id}</span>}
        </div>
        <span className="text-gray-600 ml-2">{open ? "▾" : "▸"}</span>
      </button>

      {open && (
        <div className="border-t border-gray-800 px-4 pb-4 space-y-4">
          <p className="mt-3 text-xs text-gray-400">{plan.summary}</p>

          {/* Stage checklist */}
          <div className="space-y-1.5">
            {plan.stages.map((stage) => (
              <WorkflowStageRow key={stage.stage_id} stage={stage} />
            ))}
          </div>

          {/* Recommended next action */}
          {plan.recommended_next_action && plan.recommended_next_action.action_type !== "done" && (
            <div className="space-y-3">
              <NextActionCard
                action={plan.recommended_next_action}
                actionModeClass={actionModeClass}
                actionModeLabel={actionModeLabel}
                actionDestinationLabel={actionDestinationLabel}
                actionInstruction={actionInstruction}
                actionSafetyLabel={actionSafetyLabel}
              />
              <WorkflowActionLauncher
                runId={runId}
                plan={plan}
                action={plan.recommended_next_action}
                workflowMode={workflowMode}
                workflowModeLabel={WORKFLOW_MODE_LABELS[workflowMode]}
                onRefresh={onRefresh}
                onGuidedRefresh={onGuidedRefresh}
                onToolCallsRefresh={onToolCallsRefresh}
                onFocusManualAction={onFocusManualAction}
                onUseDraft={onUseDraft}
                workflowActionKind={workflowActionKind}
                getWorkflowActionPolicy={getWorkflowActionPolicy}
                manualWorkflowButtonLabel={manualWorkflowButtonLabel}
                manualWorkflowHint={manualWorkflowHint}
                actionModeClass={actionModeClass}
                actionModeLabel={actionModeLabel}
                actionDestinationLabel={actionDestinationLabel}
                policyLabelClass={policyLabelClass}
              />
            </div>
          )}
          {plan.recommended_next_action?.action_type === "done" && (
            <div className="rounded border border-emerald-800 bg-emerald-950/20 px-3 py-2 text-xs text-emerald-300">
              ✓ Workflow complete — tests passing, no pending actions.
            </div>
          )}

          {plan.warnings.length > 0 && (
            <div className="space-y-1">
              {plan.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-400">⚠ {w}</p>
              ))}
            </div>
          )}
          {plan.blockers.length > 0 && (
            <div className="space-y-1">
              {plan.blockers.map((b, i) => (
                <p key={i} className="text-xs text-red-400">✗ {b}</p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

type WorkflowActionKind = "read_only" | "manual" | "done" | "unsupported";

const MANUAL_WORKFLOW_ACTIONS = new Set<string>(WORKFLOW_MANUAL_ONLY_ACTION_TYPES);

function workflowActionKind(actionType: string): WorkflowActionKind {
  const boundary = getWorkflowActionBoundary(actionType);
  if (actionType === "done") return "done";
  if (boundary.executionKind === "direct_safe") return "read_only";
  if (boundary.executionKind === "manual_only") return "manual";
  return "unsupported";
}

function manualWorkflowHint(actionType: string): string {
  switch (actionType) {
    case "review_patch":
      return "Use the Patch Proposal form for this step and click Review Patch with the exact file_path, old_text, and new_text.";
    case "create_proposal":
    case "propose_patch":
      return "Review or edit the Patch Proposal form, then create the proposal manually. Nothing is submitted automatically.";
    case "apply_patch_manual":
    case "apply_patch":
      return "Open the manual apply controls. Applying a patch still requires explicit confirmation and confirm=true.";
    case "run_tests_manual":
    case "run_tests":
    case "run_command":
      return "Run tests manually from the existing safe command runner. This launcher does not start project commands automatically.";
    case "analyze_result":
      return "Open a failed command result and click Analyze there. This launcher needs a specific failed tool_call before analysis can run.";
    case "rollback_manual":
    case "rollback_patch":
      return "Use the existing rollback controls. Rollback remains manual and requires explicit confirmation.";
    default:
      return "Open the matching manual workflow section and continue from there.";
  }
}

function manualWorkflowButtonLabel(actionType: string): string {
  switch (actionType) {
    case "review_patch":
      return "Open Patch Form / Review Patch";
    case "create_proposal":
    case "propose_patch":
      return "Open Patch Proposal Form";
    case "apply_patch_manual":
    case "apply_patch":
      return "Open Manual Apply";
    case "run_tests_manual":
    case "run_tests":
    case "run_command":
      return "Open Command Runner";
    case "analyze_result":
      return "Open Failed Command Result";
    case "rollback_manual":
    case "rollback_patch":
      return "Open Rollback Controls";
    default:
      return "Show Manual Instructions";
  }
}

// ── Workflow Approval Policy Matrix ──────────────────────────────────────────

type WorkflowActionPolicyDecision = {
  allowed: boolean;
  execution: "direct" | "draft_only" | "manual_only" | "blocked";
  riskLevel: "low" | "medium" | "high";
  requiresConfirmation: boolean;
  label: string;
  reason: string;
};

function getWorkflowActionPolicy(
  actionType: string,
  mode: WorkflowAutomationMode,
): WorkflowActionPolicyDecision {
  const boundary = getWorkflowActionBoundary(actionType);
  const kind = workflowActionKind(actionType);

  // Done / completed
  if (actionType === "done" || kind === "done") {
    return { allowed: false, execution: "blocked", riskLevel: "low", requiresConfirmation: false, label: "Complete", reason: "Step is already complete." };
  }

  // Manual-only actions — same in all modes
  if (kind === "manual") {
    const isHighRisk = actionType.includes("apply") || actionType.includes("rollback");
    const isMediumRisk = actionType.includes("test") || actionType.includes("run_command");
    const risk: "low" | "medium" | "high" = isHighRisk ? "high" : isMediumRisk ? "medium" : "low";
    const confirm = isHighRisk || isMediumRisk;
    return {
      allowed: true,
      execution: "manual_only",
      riskLevel: risk,
      requiresConfirmation: confirm,
      label: confirm ? "Confirm required · manual only" : "Manual only · opens form",
      reason: manualWorkflowHint(actionType),
    };
  }

  // Read-only / draft actions — mode-dependent
  if (kind === "read_only") {
    if (mode === "manual") {
      return {
        allowed: false,
        execution: "blocked",
        riskLevel: "low",
        requiresConfirmation: false,
        label: "Blocked by Manual mode",
        reason: "Switch to Guided or Safe Prep to run read-only preparation.",
      };
    }
    const isDraft = actionType === "create_patch_draft";
    return {
      allowed: true,
      execution: isDraft ? "draft_only" : "direct",
      riskLevel: isDraft ? "medium" : "low",
      requiresConfirmation: false,
      label: isDraft ? "Allowed now · draft only" : "Allowed now · read-only direct",
      reason: isDraft
        ? "Creates draft candidates. Does not create a proposal or apply any patch."
        : "Read-only action. No files modified.",
    };
  }

  // Unsupported / fallback
  return {
    allowed: false,
    execution: "blocked",
    riskLevel: boundary.riskLevel,
    requiresConfirmation: boundary.requiresConfirmation,
    label: boundary.executionKind === "approval_required_future" ? "Future approval boundary" : "Blocked",
    reason: boundary.reason || "This action type is not connected to a launcher.",
  };
}

function policyLabelClass(policy: WorkflowActionPolicyDecision): string {
  if (!policy.allowed) return "text-red-400";
  if (policy.execution === "manual_only") return "text-yellow-400";
  if (policy.execution === "draft_only") return "text-amber-300";
  return "text-emerald-400";
}

function actionModeLabel(action: PatchWorkflowNextAction): string {
  const type = action.action_type;
  if (type === "done") return "complete";
  if (type === "create_patch_draft") return "draft-only";
  if (type === "auto_gather_context" || type === "build_context_bundle") return "read-only direct";
  if (action.requires_confirmation || type.includes("apply") || type.includes("rollback")) return "confirm required";
  return "manual required";
}

function actionModeClass(actionType: string): string {
  if (actionType === "create_patch_draft") return "bg-amber-900/50 text-amber-300";
  if (actionType === "auto_gather_context" || actionType === "build_context_bundle") return "bg-blue-900/50 text-blue-300";
  if (actionType.includes("apply") || actionType.includes("rollback")) return "bg-red-900/50 text-red-300";
  return "bg-gray-800 text-gray-300";
}

function riskPillClass(risk: PatchWorkflowNextAction["risk_level"]): string {
  if (risk === "high") return "bg-red-900/50 text-red-300";
  if (risk === "medium") return "bg-yellow-900/50 text-yellow-300";
  return "bg-emerald-900/50 text-emerald-300";
}

function actionDestinationLabel(actionType: string): string {
  switch (actionType) {
    case "auto_gather_context":
    case "build_context_bundle":
    case "create_patch_draft":
      return "Runs here";
    case "review_patch":
    case "create_proposal":
    case "propose_patch":
    case "apply_patch_manual":
    case "apply_patch":
      return "Opens Timeline → Step Patch Tools";
    case "run_tests_manual":
    case "run_tests":
    case "run_command":
      return "Opens Timeline → Guided Fix Workflow";
    case "analyze_result":
      return "Opens Tool Calls → failed run-command";
    case "rollback_manual":
    case "rollback_patch":
      return "Opens Tool Calls → rollback-capable apply-patch";
    case "done":
      return "No action needed";
    default:
      return "Manual only";
  }
}

function actionInstruction(actionType: string): string {
  switch (actionType) {
    case "auto_gather_context":
      return "Click to gather read-only context for this step.";
    case "build_context_bundle":
      return "Click to summarize existing read-only tool calls.";
    case "create_patch_draft":
      return "Click to create candidates, then use one in the patch form.";
    case "review_patch":
      return "Open Step Patch Tools, check file_path, old_text, and new_text, then click Review Patch.";
    case "create_proposal":
    case "propose_patch":
      return "Review/edit fields, then create proposal manually.";
    case "apply_patch_manual":
    case "apply_patch":
      return "Use existing apply controls and confirm manually.";
    case "run_tests_manual":
    case "run_tests":
    case "run_command":
      return "Use Guided Fix Workflow or safe command runner.";
    case "analyze_result":
      return "Open failed run-command in Tool Calls and analyze manually.";
    case "rollback_manual":
    case "rollback_patch":
      return "Open rollback-capable apply-patch call and confirm manually.";
    case "done":
      return "No action needed.";
    default:
      return "Continue manually from the matching workflow section.";
  }
}

function actionSafetyLabel(action: PatchWorkflowNextAction): string {
  switch (action.action_type) {
    case "auto_gather_context":
    case "build_context_bundle":
      return "Runs now · read-only · no file changes";
    case "create_patch_draft":
      return "Creates draft only · no proposal/apply";
    case "review_patch":
    case "create_proposal":
    case "propose_patch":
      return "Manual · opens form · does not create proposal automatically";
    case "apply_patch_manual":
    case "apply_patch":
      return "Manual · requires confirm=true · no auto-apply";
    case "run_tests_manual":
    case "run_tests":
    case "run_command":
      return "Manual · use safe command runner · no auto-run";
    case "analyze_result":
      return "Manual · focus failed command · no auto-analyze";
    case "rollback_manual":
    case "rollback_patch":
      return "Manual · requires confirm=true · no auto-rollback";
    case "done":
      return "No action needed";
    default:
      return action.requires_confirmation ? "Manual · confirmation required" : "Manual only";
  }
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 12)}…` : value;
}

function manualNextActionLabel(action: string): string {
  switch (action) {
    case "create_guard":
      return "create guard";
    case "create_proposal":
      return "create proposal";
    case "apply_patch":
      return "apply patch manually";
    case "run_tests_manual":
      return "run tests manually";
    case "analyze_failed_tests_manual":
      return "analyze failed tests manually";
    case "review_success":
      return "review success";
    default:
      return action || "review manually";
  }
}

function ExpandableOutput({
  value,
  previewMax,
  muted,
}: {
  value: string;
  previewMax: number;
  muted?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const needsTruncation = value.length > previewMax;
  const display = open || !needsTruncation ? value : value.slice(0, previewMax) + "...";
  const textColor = muted ? "text-gray-500" : "text-gray-300";

  return (
    <div className="mt-3">
      <pre
        className={`max-h-[400px] overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-xs ${textColor}`}
      >
        {display}
      </pre>
      {needsTruncation && (
        <button
          onClick={() => setOpen(!open)}
          className="mt-1 text-xs text-emerald-400 hover:text-emerald-300"
        >
          {open ? "Show less" : "Show full output"}
        </button>
      )}
    </div>
  );
}

function toolCallTime(call: ToolCall): string {
  return call.completed_at || call.finished_at || call.created_at || "";
}

function isFailedRunCommandCall(call: ToolCall): boolean {
  if (call.tool_name !== "run-command") return false;
  const output = parseJsonObject(call.output_json);
  return (call.returncode !== null && call.returncode !== 0) || output.timed_out === true;
}

function isTimedOutToolCall(call: ToolCall): boolean {
  const output = parseJsonObject(call.output_json);
  return output.timed_out === true;
}

function isReadSearchContextTool(toolName: string): boolean {
  return [
    "list-files",
    "list_files",
    "read-file",
    "read_file",
    "search-code",
    "search_code",
    "auto-context",
    "auto_gather_context",
    "context-bundle",
    "context_patch_draft",
  ].includes(toolName);
}

function isRollbackCapableApplyPatchCall(call: ToolCall): boolean {
  if (call.tool_name !== "apply-patch") return false;
  const output = parseJsonObject(call.output_json);
  const rollbackData = output.rollback_data;
  return Array.isArray(rollbackData) &&
    rollbackData.some((entry) => {
      return Boolean(
        entry &&
        typeof entry === "object" &&
        "rollback_supported" in entry &&
        (entry as { rollback_supported?: unknown }).rollback_supported
      );
    });
}

function summarizeToolOutput(call: ToolCall): string {
  const raw = call.output_json?.trim();
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (call.tool_name === "propose-patch" || call.tool_name === "apply-patch") {
        return truncate(parsed.summary || `${parsed.files?.length ?? 0} patch file(s)`, 240);
      }
      if (Array.isArray(parsed.files)) return `${parsed.files.length} files listed`;
      if (Array.isArray(parsed.matches)) return `${parsed.matches.length} matches found`;
      if (typeof parsed.content === "string") {
        const path = typeof parsed.path === "string" ? `${parsed.path}: ` : "";
        return `${path}${parsed.content.length} characters read`;
      }
      if (typeof parsed.stdout === "string") return truncate(parsed.stdout || "(empty stdout)", 240);
      return truncate(JSON.stringify(parsed), 240);
    } catch {
      return truncate(raw, 240);
    }
  }
  return truncate(call.stdout || call.stderr || call.command || "(no output)", 240);
}

function patchAuditDetails(call: ToolCall): {
  agentId: string;
  proposalId: string;
  appliedFromProposalId: string;
  guardResultId: string;
  guardRevalidated: boolean;
  noGuardOverride: boolean;
} {
  const input = parseJsonObject(call.input_json);
  const output = parseJsonObject(call.output_json);
  return {
    agentId: stringValue(input.agent_id),
    proposalId: stringValue(output.proposal_id || input.proposal_id),
    appliedFromProposalId: stringValue(output.applied_from_proposal_id || input.proposal_id),
    guardResultId: stringValue(output.guard_result_id || input.guard_result_id),
    guardRevalidated: output.guard_revalidated === true,
    noGuardOverride: output.no_guard_override === true || input.no_guard_override === true,
  };
}

function groupPatchCallsByStep(calls: ToolCall[]): Record<string, ToolCall[]> {
  return calls.filter(isPatchCall).reduce<Record<string, ToolCall[]>>((acc, call) => {
    if (!call.step_id) return acc;
    acc[call.step_id] = acc[call.step_id] || [];
    acc[call.step_id].push(call);
    return acc;
  }, {});
}

function isPatchCall(call: ToolCall): boolean {
  return call.tool_name === "propose-patch" || call.tool_name === "apply-patch";
}

function patchStatusClass(status: string): string {
  if (status === "create" || status === "created") return "bg-blue-900 text-blue-300";
  if (status === "modify" || status === "modified") return "bg-emerald-900 text-emerald-300";
  if (status === "unchanged") return "bg-gray-800 text-gray-300";
  if (status === "error") return "bg-red-900 text-red-300";
  return "bg-gray-800 text-gray-300";
}

function patchOperationFromForm(form: PatchFormState) {
  return {
    file_path: form.file_path.trim(),
    old_text: form.old_text,
    new_text: form.new_text,
    create_if_missing: form.create_if_missing,
    replace_all: form.replace_all,
  };
}

function parseJsonObject(raw: string): Record<string, unknown> {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {};
  }
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load data.";
}

function isNotFoundError(error: unknown): boolean {
  return error instanceof Error && (error.message.includes("API 404") || error.message.includes("Run not found"));
}

// ── Guided Execution Panel ─────────────────────────────────────────────────────

const RISK_CHIP: Record<string, string> = {
  low:    "bg-green-900/40 text-green-300",
  medium: "bg-yellow-900/40 text-yellow-300",
  high:   "bg-red-900/40 text-red-300",
};

const ACTION_TYPE_ICON: Record<string, string> = {
  read_context:   "📄",
  search_code:    "🔍",
  propose_patch:  "✏️",
  apply_patch:    "⚡",
  run_tests:      "🧪",
  analyze_result: "🔬",
  review_diff:    "👁️",
  rollback_patch: "↩️",
  done:           "✅",
};

function GuidedActionCard({
  action,
  isNext,
}: {
  action: GuidedStepAction;
  isNext: boolean;
}) {
  const icon = ACTION_TYPE_ICON[action.action_type] ?? "⚙️";
  const riskClass = RISK_CHIP[action.risk_level] ?? RISK_CHIP.low;

  return (
    <div
      className={`rounded border p-3 text-xs ${
        isNext
          ? "border-emerald-700 bg-emerald-950/30"
          : action.enabled
          ? "border-gray-700 bg-gray-900"
          : "border-gray-800 bg-gray-900/50 opacity-50"
      }`}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm">{icon}</span>
        <span className={`font-medium ${isNext ? "text-emerald-300" : "text-gray-200"}`}>
          {action.title}
          {isNext && (
            <span className="ml-2 rounded bg-emerald-800/60 px-1.5 py-0.5 text-xs text-emerald-200">
              Recommended next
            </span>
          )}
        </span>
        <span className={`ml-auto rounded px-1.5 py-0.5 ${riskClass}`}>
          {action.risk_level}
        </span>
        {action.requires_confirmation && (
          <span className="rounded bg-orange-900/40 px-1.5 py-0.5 text-orange-300">
            confirm required
          </span>
        )}
      </div>

      {action.description && (
        <p className="mt-1.5 text-gray-400">{action.description}</p>
      )}
      {action.reason && (
        <p className="mt-1 text-gray-500 italic">{action.reason}</p>
      )}
      {!action.enabled && action.blocked_reason && (
        <p className="mt-1 text-red-400">Blocked: {action.blocked_reason}</p>
      )}
      {action.tool_name && (
        <p className="mt-1 font-mono text-gray-600">tool: {action.tool_name}</p>
      )}
    </div>
  );
}

const AUTO_READ_SAFE_ACTIONS = new Set(["list_files", "search_code", "read_file", "read_context"]);

function ContextFileCard({ file }: { file: StepContextFile }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="rounded border border-gray-800 bg-gray-900 px-2 py-1.5">
      <div className="flex items-center gap-2">
        <span className="font-mono text-gray-300 truncate flex-1">{file.file_path}</span>
        {file.read && (
          <span className="rounded bg-emerald-900/40 px-1 py-0.5 text-xs text-emerald-400">read</span>
        )}
        {file.match_count > 0 && (
          <span className="rounded bg-indigo-900/40 px-1 py-0.5 text-xs text-indigo-400">
            {file.match_count} match{file.match_count !== 1 ? "es" : ""}
          </span>
        )}
        {file.snippets.length > 0 && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            {expanded ? "▴ hide" : "▾ snippets"}
          </button>
        )}
      </div>
      {file.reason && <p className="mt-0.5 text-xs text-gray-600 italic">{file.reason}</p>}
      {expanded && file.snippets.length > 0 && (
        <div className="mt-1 space-y-1">
          {file.snippets.map((s, i) => (
            <pre key={i} className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400 whitespace-pre-wrap overflow-x-auto max-h-40">
              {s}
            </pre>
          ))}
        </div>
      )}
    </div>
  );
}

function GuidedStepCard({
  stepPlan,
  stepTitle,
  runId,
  onAutoReadDone,
  bundle,
  bundleLoading,
  onLoadBundle,
  onUseDraft,
}: {
  stepPlan: GuidedStepExecutionPlan;
  stepTitle: string;
  runId: string;
  onAutoReadDone: () => void;
  bundle: StepContextBundle | null;
  bundleLoading: boolean;
  onLoadBundle: () => void;
  onUseDraft: (candidate: ContextPatchDraftCandidate) => void;
}) {
  const [open, setOpen] = useState(false);
  const [autoReadResult, setAutoReadResult] = useState<AutoStepReadResponse | null>(null);
  const [autoReadRunning, setAutoReadRunning] = useState(false);
  const [autoReadError, setAutoReadError] = useState("");
  const [autoCtxResult, setAutoCtxResult] = useState<AutoContextGatherResponse | null>(null);
  const [autoCtxRunning, setAutoCtxRunning] = useState(false);
  const [autoCtxError, setAutoCtxError] = useState("");
  const [patchDraft, setPatchDraft] = useState<ContextPatchDraftResponse | null>(null);
  const [draftRunning, setDraftRunning] = useState(false);
  const [draftError, setDraftError] = useState("");
  const nextAction = stepPlan.recommended_next_action;
  const safeNextAction =
    nextAction && AUTO_READ_SAFE_ACTIONS.has(nextAction.action_type) ? nextAction : null;

  // Show "Auto Gather Context" when next action is a read op, or when very few context calls exist
  const contextCallCount = stepPlan.actions.filter(
    (a) => AUTO_READ_SAFE_ACTIONS.has(a.action_type)
  ).length;
  const showAutoCtxButton =
    safeNextAction !== null ||
    (nextAction && ["search_code", "read_context", "list_files"].includes(nextAction.action_type)) ||
    contextCallCount === 0;

  const handleCreateDraft = async () => {
    setDraftRunning(true);
    setDraftError("");
    setPatchDraft(null);
    try {
      const res = await buildContextPatchDraft(runId, stepPlan.step_id, {});
      setPatchDraft(res);
    } catch (e: any) {
      setDraftError(e.message ?? "Failed to build patch draft");
    } finally {
      setDraftRunning(false);
    }
  };

  const handleAutoContext = async () => {
    setAutoCtxRunning(true);
    setAutoCtxError("");
    setAutoCtxResult(null);
    try {
      const res = await runStepAutoContext(runId, stepPlan.step_id, {
        query: stepTitle,
        max_tool_calls: 5,
      });
      setAutoCtxResult(res);
      onAutoReadDone(); // refreshes tool calls + guided plan
    } catch (e: any) {
      setAutoCtxError(e.message ?? "Auto context gather failed");
    } finally {
      setAutoCtxRunning(false);
    }
  };

  const handleAutoRead = async () => {
    if (!safeNextAction) return;
    setAutoReadRunning(true);
    setAutoReadError("");
    setAutoReadResult(null);
    try {
      // For read_file/read_context: need file_path — show blocked if missing
      if (
        (safeNextAction.action_type === "read_file" || safeNextAction.action_type === "read_context") &&
        !safeNextAction.tool_name
      ) {
        setAutoReadError("Cannot auto-run read_file: no file path known for this step.");
        return;
      }
      const res = await runStepAutoRead(runId, stepPlan.step_id, {
        step_id: stepPlan.step_id,
        action_type: safeNextAction.action_type === "read_context" ? "read_file" : safeNextAction.action_type,
        query: safeNextAction.action_type === "search_code" ? stepTitle : "",
        file_path: safeNextAction.tool_name ?? "",
        run_id: runId,
      });
      setAutoReadResult(res);
      onAutoReadDone();
    } catch (e: any) {
      setAutoReadError(e.message ?? "Auto-read failed");
    } finally {
      setAutoReadRunning(false);
    }
  };

  return (
    <div className="rounded border border-gray-800 bg-gray-950">
      <button
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="text-xs text-gray-500">{open ? "▾" : "▸"}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-gray-200">{stepTitle}</p>
          <p className="mt-0.5 text-xs text-gray-500">{stepPlan.status_summary}</p>
        </div>
        {nextAction && nextAction.action_type !== "done" && (
          <span className="shrink-0 rounded bg-emerald-900/50 px-2 py-0.5 text-xs text-emerald-300">
            {ACTION_TYPE_ICON[nextAction.action_type] ?? "⚙️"} {nextAction.title}
          </span>
        )}
        {nextAction?.action_type === "done" && (
          <span className="shrink-0 rounded bg-gray-800 px-2 py-0.5 text-xs text-gray-400">
            ✅ Done
          </span>
        )}
        {stepPlan.task_type && (
          <span className="shrink-0 rounded bg-gray-800 px-2 py-0.5 font-mono text-xs text-gray-500">
            {stepPlan.task_type}
          </span>
        )}
      </button>

      {open && (
        <div className="border-t border-gray-800 px-4 pb-4 pt-3 space-y-2">
          {stepPlan.warnings.length > 0 && (
            <div className="mb-2">
              {stepPlan.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-400">{w}</p>
              ))}
            </div>
          )}
          {stepPlan.actions.map((action) => (
            <GuidedActionCard
              key={action.action_id}
              action={action}
              isNext={nextAction?.action_id === action.action_id}
            />
          ))}

          {/* Safe Auto Read/Search button — only for read-only actions */}
          {safeNextAction && (
            <div className="mt-3 rounded border border-sky-900 bg-sky-950/20 px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-sky-300">🔍 Safe Auto Read/Search</span>
                <span className="rounded bg-sky-900/50 px-1.5 py-0.5 text-xs text-sky-400">
                  read-only · no file changes
                </span>
              </div>
              <p className="mt-1 text-xs text-sky-500">
                Runs <code className="font-mono text-sky-400">{safeNextAction.action_type}</code> automatically.
                No patch, no command, no apply.
              </p>
              <div className="mt-2 flex items-center gap-2">
                <button
                  onClick={handleAutoRead}
                  disabled={autoReadRunning}
                  className="rounded bg-sky-800 px-3 py-1 text-xs font-medium text-sky-100 hover:bg-sky-700 disabled:opacity-50"
                >
                  {autoReadRunning ? "Running…" : `Run ${safeNextAction.action_type} (read-only)`}
                </button>
              </div>
              {autoReadError && (
                <p className="mt-2 text-xs text-red-400">⚠ {autoReadError}</p>
              )}
              {autoReadResult && (
                <div className="mt-2 rounded bg-gray-900 px-2 py-2 text-xs space-y-0.5">
                  <p className="text-gray-400">
                    Status: <span className={autoReadResult.status === "completed" ? "text-emerald-400" : "text-red-400"}>{autoReadResult.status}</span>
                  </p>
                  {autoReadResult.summary && (
                    <p className="text-gray-300">{autoReadResult.summary}</p>
                  )}
                  {autoReadResult.tool_call_id && (
                    <p className="font-mono text-gray-600">tool_call: {autoReadResult.tool_call_id}</p>
                  )}
                  {autoReadResult.warnings.length > 0 && (
                    <div>
                      {autoReadResult.warnings.map((w, i) => (
                        <p key={i} className="text-yellow-400">{w}</p>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Context Bundle — aggregated view of read-only tool calls */}
          <div className="mt-3 rounded border border-gray-700 bg-gray-950 px-3 py-2.5">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium text-gray-300">📦 Context Bundle</span>
              <button
                onClick={onLoadBundle}
                disabled={bundleLoading}
                className="rounded bg-gray-700 px-2 py-1 text-xs text-gray-300 hover:bg-gray-600 disabled:opacity-50"
              >
                {bundleLoading ? "Loading…" : "Build Context Bundle"}
              </button>
            </div>

            {!bundle && !bundleLoading && (
              <p className="mt-1.5 text-xs text-gray-600">
                No context yet. Run <span className="text-violet-400">Auto Gather Context</span> first, then build the bundle.
              </p>
            )}

            {bundle && bundle.status === "empty" && (
              <p className="mt-1.5 text-xs text-gray-500">
                {bundle.warnings[0] ?? "No read-only context collected yet."}
              </p>
            )}

            {bundle && bundle.status !== "empty" && (
              <div className="mt-2 space-y-1 text-xs">
                <p className="text-gray-400">{bundle.summary}</p>
                {bundle.queries.length > 0 && (
                  <p className="text-gray-500">
                    Queries: {bundle.queries.join(", ")}
                  </p>
                )}
                {bundle.files.length > 0 && (
                  <div className="space-y-1.5 mt-1">
                    {bundle.files.map((f, i) => (
                      <ContextFileCard key={i} file={f} />
                    ))}
                  </div>
                )}
                {bundle.warnings.length > 0 && (
                  <div className="mt-1">
                    {bundle.warnings.map((w, i) => (
                      <p key={i} className="text-yellow-400">{w}</p>
                    ))}
                  </div>
                )}
                {bundle.next_recommended_action && (
                  <p className="text-violet-400 mt-1">
                    Next: {bundle.next_recommended_action}
                  </p>
                )}
              </div>
            )}
          </div>

          {/* Context Patch Draft — build candidates from context bundle */}
          {bundle && bundle.status !== "empty" && (
            <div className="mt-3 rounded border border-amber-900 bg-amber-950/20 px-3 py-2.5">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-amber-300">✏️ Patch Draft from Context</span>
                  <span className="rounded bg-amber-900/50 px-1.5 py-0.5 text-xs text-amber-500">
                    draft only · no auto-apply
                  </span>
                </div>
                <button
                  onClick={handleCreateDraft}
                  disabled={draftRunning}
                  className="rounded bg-amber-800 px-2 py-1 text-xs text-amber-100 hover:bg-amber-700 disabled:opacity-50"
                >
                  {draftRunning ? "Building…" : "Create Patch Draft from Context"}
                </button>
              </div>

              {draftError && (
                <p className="mt-2 text-xs text-red-400">⚠ {draftError}</p>
              )}

              {patchDraft && (
                <div className="mt-2 space-y-2 text-xs">
                  <p className="rounded bg-amber-950/60 px-2 py-1 text-amber-300 font-medium">
                    ⚠ Draft only — review and edit before creating proposal.
                  </p>
                  <p className="text-gray-400">{patchDraft.summary}</p>
                  {patchDraft.warnings.map((w, i) => (
                    <p key={i} className="text-yellow-400">{w}</p>
                  ))}
                  {patchDraft.candidates.map((c, i) => (
                    <div
                      key={i}
                      className={`rounded border px-2 py-2 space-y-1 ${
                        i === patchDraft.recommended_candidate_index
                          ? "border-amber-700 bg-amber-950/40"
                          : "border-gray-800 bg-gray-900"
                      }`}
                    >
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-mono text-gray-300 truncate">{c.file_path}</span>
                        <span className="rounded bg-gray-800 px-1.5 py-0.5 text-gray-400">
                          {Math.round(c.confidence * 100)}% confidence
                        </span>
                        {i === patchDraft.recommended_candidate_index && (
                          <span className="rounded bg-amber-800/60 px-1.5 py-0.5 text-amber-200">
                            recommended
                          </span>
                        )}
                      </div>
                      <p className="text-gray-500 italic">{c.reason}</p>
                      {c.old_text && (
                        <div>
                          <p className="text-gray-600 mb-0.5">old_text (to find):</p>
                          <pre className="rounded bg-gray-950 px-2 py-1 text-gray-400 whitespace-pre-wrap overflow-x-auto max-h-24 text-xs">
                            {c.old_text.slice(0, 300)}{c.old_text.length > 300 ? "…" : ""}
                          </pre>
                        </div>
                      )}
                      {c.warnings.map((w, wi) => (
                        <p key={wi} className="text-yellow-500">{w}</p>
                      ))}
                      <button
                        onClick={() => onUseDraft(c)}
                        className="mt-1 rounded bg-emerald-900 px-2 py-1 text-xs text-emerald-200 hover:bg-emerald-800"
                      >
                        Use in Patch Proposal form →
                      </button>
                    </div>
                  ))}
                  {patchDraft.next_recommended_action && (
                    <p className="text-amber-500">Next: {patchDraft.next_recommended_action}</p>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Auto Gather Context button — bounded read-only workflow */}
          {showAutoCtxButton && (
            <div className="mt-3 rounded border border-violet-900 bg-violet-950/20 px-3 py-2.5">
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium text-violet-300">🧩 Auto Gather Context</span>
                <span className="rounded bg-violet-900/50 px-1.5 py-0.5 text-xs text-violet-400">
                  read-only · max 5 tool calls · no file changes
                </span>
              </div>
              <p className="mt-1 text-xs text-violet-500">
                Runs list_files → search_code → read_file automatically (up to 5 calls).
                No patch, no command, no apply.
              </p>
              <div className="mt-2">
                <button
                  onClick={handleAutoContext}
                  disabled={autoCtxRunning}
                  className="rounded bg-violet-800 px-3 py-1 text-xs font-medium text-violet-100 hover:bg-violet-700 disabled:opacity-50"
                >
                  {autoCtxRunning ? "Gathering context…" : "Auto Gather Context (read-only)"}
                </button>
              </div>
              {autoCtxError && (
                <p className="mt-2 text-xs text-red-400">⚠ {autoCtxError}</p>
              )}
              {autoCtxResult && (
                <div className="mt-2 rounded bg-gray-900 px-2 py-2 text-xs space-y-1">
                  <p className="text-gray-400">
                    Status:{" "}
                    <span className={autoCtxResult.status === "completed" ? "text-emerald-400" : "text-yellow-400"}>
                      {autoCtxResult.status}
                    </span>
                  </p>
                  {autoCtxResult.summary && (
                    <p className="text-gray-300">{autoCtxResult.summary}</p>
                  )}
                  {autoCtxResult.searched_queries.length > 0 && (
                    <p className="text-gray-500">
                      Queries: {autoCtxResult.searched_queries.join(", ")}
                    </p>
                  )}
                  {autoCtxResult.files_read.length > 0 && (
                    <div>
                      <p className="text-gray-500">Files read:</p>
                      {autoCtxResult.files_read.map((f, i) => (
                        <p key={i} className="font-mono text-gray-400 pl-2">
                          {f.file_path}{" "}
                          <span className="text-gray-600 not-italic">— {f.reason}</span>
                        </p>
                      ))}
                    </div>
                  )}
                  {autoCtxResult.next_recommended_action && (
                    <p className="text-violet-400">
                      Next: {autoCtxResult.next_recommended_action}
                    </p>
                  )}
                  {autoCtxResult.warnings.length > 0 && (
                    <div>
                      {autoCtxResult.warnings.map((w, i) => (
                        <p key={i} className="text-yellow-400">{w}</p>
                      ))}
                    </div>
                  )}
                  <p className="font-mono text-gray-700">
                    tool_calls: {autoCtxResult.tool_call_ids.length}
                  </p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function GuidedExecutionPanel({
  plan,
  loading,
  error,
  steps,
  runId,
  onRefresh,
  onAutoReadDone,
  contextBundles,
  bundleLoading,
  onLoadBundle,
  onUseDraft,
}: {
  plan: GuidedExecutionPlanResponse | null;
  loading: boolean;
  error: string;
  steps: RunStep[];
  runId: string;
  onRefresh: () => void;
  onAutoReadDone: () => void;
  contextBundles: Record<string, StepContextBundle>;
  bundleLoading: Record<string, boolean>;
  onLoadBundle: (stepId: string) => void;
  onUseDraft: (stepId: string, candidate: ContextPatchDraftCandidate) => void;
}) {
  const stepTitleMap = Object.fromEntries(steps.map((s) => [s.id, s.title]));

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Guided Execution</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            Recommended next manual action per step. Nothing runs automatically.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-700 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-600 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh Plan"}
        </button>
      </div>

      {error && (
        <p className="rounded bg-red-950/30 px-3 py-2 text-xs text-red-300">{error}</p>
      )}

      {!plan && !loading && !error && (
        <p className="text-sm text-gray-500">
          Click "Refresh Plan" to load guided execution recommendations.
        </p>
      )}

      {plan && (
        <>
          {plan.warnings.length > 0 && (
            <div className="rounded border border-yellow-800 bg-yellow-950/20 px-3 py-2">
              {plan.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-300">{w}</p>
              ))}
            </div>
          )}

          {plan.steps.length === 0 ? (
            <p className="text-sm text-gray-500">No steps found for this run.</p>
          ) : (
            <div className="space-y-2">
              {plan.steps.map((stepPlan) => (
                <GuidedStepCard
                  key={stepPlan.step_id}
                  stepPlan={stepPlan}
                  stepTitle={stepTitleMap[stepPlan.step_id] ?? stepPlan.step_id}
                  runId={runId}
                  onAutoReadDone={onAutoReadDone}
                  bundle={contextBundles[stepPlan.step_id] ?? null}
                  bundleLoading={bundleLoading[stepPlan.step_id] ?? false}
                  onLoadBundle={() => onLoadBundle(stepPlan.step_id)}
                  onUseDraft={(c) => onUseDraft(stepPlan.step_id, c)}
                />
              ))}
            </div>
          )}

          <p className="text-xs text-gray-600">{plan.summary}</p>
        </>
      )}
    </div>
  );
}

// ── Tool Plan Panel ────────────────────────────────────────────────────────────

const TOOL_CHIP_COLORS: Record<string, string> = {
  "read-file":             "bg-blue-900/50 text-blue-300",
  "search-code":           "bg-indigo-900/50 text-indigo-300",
  "propose-patch":         "bg-yellow-900/50 text-yellow-300",
  "apply-patch":           "bg-orange-900/50 text-orange-300",
  "git-diff":              "bg-teal-900/50 text-teal-300",
  "run-command":           "bg-purple-900/50 text-purple-300",
  "analyze-command-result":"bg-pink-900/50 text-pink-300",
};

const TOOL_HINTS: Record<string, string> = {
  "read-file":             "Read a file from the project workspace",
  "search-code":           "Search for symbols or patterns in the codebase",
  "propose-patch":         "Preview a patch before applying",
  "apply-patch":           "Apply a patch (requires manual confirm)",
  "git-diff":              "Inspect uncommitted git changes",
  "run-command":           "Run a safe project command (test/build/lint)",
  "analyze-command-result":"Analyze command output for issues",
};

function ToolPlanPanel({
  plan,
  loading,
  error,
  onRefresh,
}: {
  plan: StepToolPlanResponse | null;
  loading: boolean;
  error: string;
  onRefresh: () => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-gray-200">Recommended Tools per Step</h3>
          <p className="mt-0.5 text-xs text-gray-500">
            Advisory only — no tool runs automatically.
          </p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-700 px-3 py-1.5 text-xs text-gray-200 hover:bg-gray-600 disabled:opacity-50"
        >
          {loading ? "Loading…" : "Refresh Tool Plan"}
        </button>
      </div>

      {error && (
        <p className="rounded bg-red-950/30 px-3 py-2 text-xs text-red-300">{error}</p>
      )}

      {!plan && !loading && !error && (
        <p className="text-sm text-gray-500">
          Click "Refresh Tool Plan" to load recommendations for this run's steps.
        </p>
      )}

      {plan && (
        <>
          {plan.warnings.length > 0 && (
            <div className="rounded border border-yellow-800 bg-yellow-950/20 px-3 py-2">
              {plan.warnings.map((w, i) => (
                <p key={i} className="text-xs text-yellow-300">{w}</p>
              ))}
            </div>
          )}

          {plan.recommendations.length === 0 ? (
            <p className="text-sm text-gray-500">No steps found for this run.</p>
          ) : (
            <div className="space-y-3">
              {plan.recommendations.map((rec) => (
                <div
                  key={rec.step_id}
                  className="rounded border border-gray-800 bg-gray-950 p-3"
                >
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <span className="rounded bg-gray-800 px-2 py-0.5 font-mono text-xs text-gray-400">
                      {rec.task_type || "unknown"}
                    </span>
                    {rec.agent_id && (
                      <span className="text-xs text-gray-500">{rec.agent_id}</span>
                    )}
                    <span className="ml-auto text-xs text-gray-600">
                      confidence {Math.round(rec.confidence * 100)}%
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {rec.recommended_tools.map((tool) => (
                      <span
                        key={tool}
                        title={TOOL_HINTS[tool] ?? tool}
                        className={`rounded px-2 py-0.5 text-xs font-mono cursor-default ${
                          TOOL_CHIP_COLORS[tool] ?? "bg-gray-800 text-gray-300"
                        }`}
                      >
                        {tool}
                      </span>
                    ))}
                  </div>

                  {rec.reason && (
                    <p className="mt-2 text-xs text-gray-500">{rec.reason}</p>
                  )}

                  {rec.warnings.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {rec.warnings.map((w, i) => (
                        <li key={i} className="text-xs text-yellow-400">{w}</li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-gray-600">{plan.summary}</p>
        </>
      )}
    </div>
  );
}

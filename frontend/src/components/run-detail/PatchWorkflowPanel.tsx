import { useState } from "react";
import {
  buildContextPatchDraft,
  getRunStepContextBundle,
  runStepAutoContext,
} from "../../api/client";
import type {
  ContextPatchDraftCandidate,
  ContextPatchDraftResponse,
  PatchWorkflowNextAction,
  PatchWorkflowPlanResponse,
  PatchWorkflowStage,
  RunStep,
  StepPatchWorkflowPlan,
} from "../../types";

export function WorkflowStageRow({ stage }: { stage: PatchWorkflowStage }) {
  const icon =
    stage.status === "completed" ? "✓" :
    stage.status === "ready" ? "→" :
    stage.status === "warning" ? "⚠" :
    stage.status === "blocked" ? "✗" : "○";

  const iconColor =
    stage.status === "completed" ? "text-emerald-400" :
    stage.status === "ready" ? "text-blue-400" :
    stage.status === "warning" ? "text-yellow-400" :
    stage.status === "blocked" ? "text-red-400" : "text-gray-600";

  const titleColor =
    stage.status === "completed" ? "text-gray-300" :
    stage.status === "ready" ? "text-gray-200" :
    stage.status === "blocked" ? "text-red-300" :
    stage.status === "warning" ? "text-yellow-300" : "text-gray-500";

  return (
    <div className="flex items-start gap-2 text-xs">
      <span className={`w-4 flex-shrink-0 font-bold ${iconColor}`}>{icon}</span>
      <div className="min-w-0">
        <span className={`font-medium ${titleColor}`}>{stage.title}</span>
        {stage.summary && <span className="text-gray-500 ml-2">{stage.summary}</span>}
        {stage.warnings.map((w, i) => (
          <p key={i} className="text-yellow-500">⚠ {w}</p>
        ))}
      </div>
    </div>
  );
}

type NextActionCardProps = {
  action: PatchWorkflowNextAction;
  actionModeClass: (actionType: string) => string;
  actionModeLabel: (action: PatchWorkflowNextAction) => string;
  actionDestinationLabel: (actionType: string) => string;
  actionInstruction: (actionType: string) => string;
  actionSafetyLabel: (action: PatchWorkflowNextAction) => string;
};

export function NextActionCard({
  action,
  actionModeClass,
  actionModeLabel,
  actionDestinationLabel,
  actionInstruction,
  actionSafetyLabel,
}: NextActionCardProps) {
  const riskColor =
    action.risk_level === "high" ? "border-red-800 bg-red-950/20" :
    action.risk_level === "medium" ? "border-yellow-800 bg-yellow-950/20" :
    "border-blue-800 bg-blue-950/20";

  const riskLabel =
    action.risk_level === "high" ? "🔴 high risk" :
    action.risk_level === "medium" ? "🟡 medium risk" : "🟢 low risk";

  return (
    <div className={`rounded border ${riskColor} px-3 py-2.5 space-y-1`}>
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-semibold text-gray-200">Recommended next action</span>
        <span className="text-xs text-gray-500">{riskLabel}</span>
      </div>
      <p className="text-sm font-medium text-gray-100">{action.title}</p>
      <p className="text-xs text-gray-400">{action.description}</p>
      <div className="flex flex-wrap gap-2 text-xs">
        <span className={`rounded px-2 py-0.5 ${actionModeClass(action.action_type)}`}>
          {actionModeLabel(action)}
        </span>
        <span className="rounded bg-gray-900 px-2 py-0.5 text-gray-400">
          {actionDestinationLabel(action.action_type)}
        </span>
      </div>
      <p className="text-xs text-gray-500">{actionInstruction(action.action_type)}</p>
      <p className="text-xs text-gray-500">{actionSafetyLabel(action)}</p>
      {action.requires_confirmation && (
        <p className="text-xs text-yellow-400">⚠ Requires manual confirmation before proceeding.</p>
      )}
      {action.blocked_reason && (
        <p className="text-xs text-red-400">✗ {action.blocked_reason}</p>
      )}
    </div>
  );
}

type WorkflowStepPickerProps = {
  plan: PatchWorkflowPlanResponse;
  steps: RunStep[];
  activeStepId: string | null;
  onActiveStepChange: (stepId: string | null) => void;
  showModeStatus?: boolean;
  pinnedStepExists?: boolean;
  pinnedMissing?: boolean;
  pinnedDone?: boolean;
};

export function WorkflowStepPicker({
  plan,
  steps,
  activeStepId,
  onActiveStepChange,
  showModeStatus = false,
  pinnedStepExists = false,
  pinnedMissing = false,
  pinnedDone = false,
}: WorkflowStepPickerProps) {
  const titleById = Object.fromEntries(steps.map((step) => [step.id, step.title]));

  return (
    <>
      <div className="mt-3 flex flex-col gap-2 rounded border border-gray-800 bg-gray-950/60 p-2 sm:flex-row sm:items-center">
        <label className="text-xs font-medium text-gray-400" htmlFor="workflow-active-step">
          Active step
        </label>
        <select
          id="workflow-active-step"
          value={activeStepId ?? ""}
          onChange={(event) => onActiveStepChange(event.target.value || null)}
          className="min-w-0 flex-1 rounded border border-gray-700 bg-gray-900 px-2 py-1.5 text-xs text-gray-200 focus:border-emerald-500 focus:outline-none"
        >
          <option value="">Auto: first actionable</option>
          {plan.steps.map((step) => {
            const action = step.recommended_next_action;
            const risk = action?.risk_level === "high" ? "high risk" : "";
            const marker =
              step.status === "done" ? "done" :
              step.status === "blocked" ? "blocked" :
              risk || action?.title || "no action";
            const title = titleById[step.step_id] || step.summary || step.step_id;
            return (
              <option key={step.step_id} value={step.step_id}>
                {shortId(step.step_id)} · {step.status} · {marker} · {truncate(title, 72)}
              </option>
            );
          })}
        </select>
        {activeStepId && (
          <button
            onClick={() => onActiveStepChange(null)}
            className="rounded bg-gray-800 px-2 py-1.5 text-xs text-gray-300 hover:bg-gray-700"
          >
            Clear active step
          </button>
        )}
        <span className="text-[11px] text-gray-600" title="Workflow mode and active step are remembered for this run.">
          Saved for this run
        </span>
      </div>

      {showModeStatus && (
        <div className="mt-2 rounded border border-gray-800 bg-gray-950/50 px-2 py-1.5 text-xs text-gray-400">
          {activeStepId && pinnedStepExists
            ? "Pinned active step. Cockpit is focused on the selected step."
            : "Auto mode. Cockpit follows the first actionable step."}
          {pinnedMissing && (
            <span className="ml-2 text-yellow-400">
              Selected step is no longer in the workflow plan; showing the next actionable step.
            </span>
          )}
          {pinnedDone && (
            <span className="ml-2 text-emerald-400">
              Selected step is done. Clear active step to return to the next actionable step.
            </span>
          )}
        </div>
      )}
    </>
  );
}

type WorkflowModeSelectorOption<TMode extends string> = {
  value: TMode;
  label: string;
};

type WorkflowModeSelectorProps<TMode extends string> = {
  mode: TMode;
  modes: WorkflowModeSelectorOption<TMode>[];
  modeDescription: string;
  savedForRunLabel: string;
  policyTitle?: string;
  policyLines: string[];
  onModeChange: (mode: TMode) => void;
};

export function WorkflowModeSelector<TMode extends string>({
  mode,
  modes,
  modeDescription,
  savedForRunLabel,
  policyTitle = "Current mode policy",
  policyLines,
  onModeChange,
}: WorkflowModeSelectorProps<TMode>) {
  return (
    <div className="mt-3 rounded border border-gray-800 bg-gray-950/50 px-2 py-2">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-gray-500">Workflow mode</span>
        <div className="flex gap-1">
          {modes.map((modeOption) => (
            <button
              key={modeOption.value}
              onClick={() => onModeChange(modeOption.value)}
              className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
                mode === modeOption.value
                  ? "bg-emerald-800 text-emerald-100"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200"
              }`}
            >
              {modeOption.label}
            </button>
          ))}
        </div>
      </div>
      <p className="mt-1 text-xs text-gray-500">
        {modeDescription} <span className="text-gray-600">{savedForRunLabel}</span>
      </p>
      <details className="mt-1.5">
        <summary className="cursor-pointer text-[10px] text-gray-600 hover:text-gray-400">{policyTitle}</summary>
        <ul className="mt-1 space-y-0.5 text-[10px] text-gray-600 list-disc list-inside">
          {policyLines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </details>
    </div>
  );
}

type WorkflowActionKind = "read_only" | "manual" | "done" | "unsupported";

type WorkflowActionPolicyDecision = {
  allowed: boolean;
  execution: "direct" | "draft_only" | "manual_only" | "blocked";
  riskLevel: "low" | "medium" | "high";
  requiresConfirmation: boolean;
  label: string;
  reason: string;
};

type WorkflowActionLauncherProps = {
  runId: string;
  plan: StepPatchWorkflowPlan;
  action: PatchWorkflowNextAction;
  workflowMode: string;
  workflowModeLabel: string;
  onRefresh: () => void | Promise<void>;
  onGuidedRefresh?: () => void | Promise<void>;
  onToolCallsRefresh?: () => void | Promise<void>;
  onFocusManualAction: (stepId: string, actionType: string) => Promise<{ message: string; error?: string }>;
  onUseDraft?: (stepId: string, candidate: ContextPatchDraftCandidate) => void;
  workflowActionKind: (actionType: string) => WorkflowActionKind;
  getWorkflowActionPolicy: (actionType: string, mode: any) => WorkflowActionPolicyDecision;
  manualWorkflowButtonLabel: (actionType: string) => string;
  manualWorkflowHint: (actionType: string) => string;
  actionModeClass: (actionType: string) => string;
  actionModeLabel: (action: PatchWorkflowNextAction) => string;
  actionDestinationLabel: (actionType: string) => string;
  policyLabelClass: (policy: WorkflowActionPolicyDecision) => string;
};

export function WorkflowActionLauncher({
  runId,
  plan,
  action,
  workflowMode,
  workflowModeLabel,
  onRefresh,
  onGuidedRefresh,
  onToolCallsRefresh,
  onFocusManualAction,
  onUseDraft,
  workflowActionKind,
  getWorkflowActionPolicy,
  manualWorkflowButtonLabel,
  manualWorkflowHint,
  actionModeClass,
  actionModeLabel,
  actionDestinationLabel,
  policyLabelClass,
}: WorkflowActionLauncherProps) {
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState("");
  const [actionFocusError, setActionFocusError] = useState("");
  const [actionResult, setActionResult] = useState("");
  const [draftResult, setDraftResult] = useState<ContextPatchDraftResponse | null>(null);

  const kind = workflowActionKind(action.action_type);
  const policy = getWorkflowActionPolicy(action.action_type, workflowMode);
  const blocked = !action.enabled || Boolean(action.blocked_reason);
  const modeBlocksReadOnly = workflowMode === "manual" && kind === "read_only";
  const disabled = running || blocked || kind === "done" || kind === "unsupported" || modeBlocksReadOnly;

  const badge =
    kind === "read_only" ? "read-only" :
    kind === "manual" ? "manual required" :
    kind === "done" ? "complete" : "not wired";

  const buttonLabel =
    action.action_type === "auto_gather_context" ? "Gather Context" :
    action.action_type === "build_context_bundle" ? "Build Context Bundle" :
    action.action_type === "create_patch_draft" ? "Create Patch Draft" :
    kind === "manual" ? manualWorkflowButtonLabel(action.action_type) :
    "Action unavailable";

  const refreshAfterSafeAction = async () => {
    await onRefresh();
    await onGuidedRefresh?.();
    await onToolCallsRefresh?.();
  };

  const handleLaunch = async () => {
    if (disabled) return;

    setRunning(true);
    setActionError("");
    setActionFocusError("");
    setActionResult("");
    setDraftResult(null);

    try {
      if (action.action_type === "auto_gather_context") {
        const res = await runStepAutoContext(runId, plan.step_id, {
          query: plan.summary || plan.step_id,
          max_tool_calls: 5,
          agent_id: plan.agent_id || undefined,
        });
        setActionResult(
          `${res.summary} Tool calls: ${res.tool_call_ids.length}. Files read: ${res.files_read.length}.`
        );
        await refreshAfterSafeAction();
        return;
      }

      if (action.action_type === "build_context_bundle") {
        const res = await getRunStepContextBundle(runId, plan.step_id);
        setActionResult(
          `${res.bundle.summary} Files: ${res.bundle.files.length}. Linked tool calls: ${res.bundle.tool_call_ids.length}.`
        );
        await onRefresh();
        return;
      }

      if (action.action_type === "create_patch_draft") {
        const res = await buildContextPatchDraft(runId, plan.step_id, {
          agent_id: plan.agent_id || undefined,
        });
        setDraftResult(res);
        setActionResult(`${res.summary} Candidates: ${res.candidates.length}.`);
        await onRefresh();
        return;
      }

      if (kind === "manual") {
        const result = await onFocusManualAction(plan.step_id, action.action_type);
        setActionResult(result.message || manualWorkflowHint(action.action_type));
        setActionFocusError(result.error || "");
        return;
      }

      setActionResult("This recommended action is not wired to a launcher yet.");
    } catch (e: any) {
      setActionError(e.message ?? "Workflow action failed");
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="rounded border border-gray-800 bg-gray-900/50 px-3 py-3 space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs font-semibold text-gray-200">Launch Recommended Action</span>
            <span className="rounded border border-gray-700 px-2 py-0.5 text-[11px] uppercase tracking-wide text-gray-400">
              {badge}
            </span>
            <span className="text-[11px] text-gray-500">risk: {action.risk_level}</span>
            <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-gray-500">
              mode: {workflowModeLabel}
            </span>
          </div>
          <p className="mt-1 text-sm font-medium text-gray-100">{action.title}</p>
          <p className="mt-1 text-xs text-gray-400">{action.description}</p>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className={`rounded px-2 py-0.5 ${actionModeClass(action.action_type)}`}>
              {actionModeLabel(action)}
            </span>
            <span className="rounded bg-gray-950 px-2 py-0.5 text-gray-400">
              {actionDestinationLabel(action.action_type)}
            </span>
          </div>
          <div className="mt-2 rounded border border-gray-800 bg-gray-950/60 px-2 py-1.5 text-xs">
            <span className={`font-medium ${policyLabelClass(policy)}`}>{policy.label}</span>
            <span className="mx-1.5 text-gray-700">·</span>
            <span className="text-gray-500">risk: {policy.riskLevel}</span>
            {policy.requiresConfirmation && (
              <><span className="mx-1.5 text-gray-700">·</span><span className="text-yellow-400">confirm required</span></>
            )}
            <p className="mt-0.5 text-gray-500">{policy.reason}</p>
          </div>
          {blocked && !modeBlocksReadOnly && (
            <p className="mt-1 text-xs text-red-400">
              {action.blocked_reason || "Action is disabled for the current workflow state."}
            </p>
          )}
        </div>
        <button
          onClick={handleLaunch}
          disabled={disabled}
          className="rounded bg-emerald-700 px-3 py-2 text-xs font-medium text-white hover:bg-emerald-600 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-500"
        >
          {running ? "Working..." : buttonLabel}
        </button>
      </div>

      {actionError && (
        <div className="rounded border border-red-800 bg-red-950/20 p-2 text-xs text-red-300">{actionError}</div>
      )}

      {actionFocusError && (
        <div className="rounded border border-yellow-800 bg-yellow-950/20 p-2 text-xs text-yellow-300">{actionFocusError}</div>
      )}

      {actionResult && (
        <div className="rounded border border-gray-800 bg-gray-950 p-2 text-xs text-gray-300">{actionResult}</div>
      )}

      {draftResult && draftResult.candidates.length > 0 && (
        <div className="space-y-2">
          {draftResult.candidates.slice(0, 3).map((candidate, index) => (
            <div key={`${candidate.file_path}-${index}`} className="rounded border border-gray-800 bg-gray-950 p-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-gray-200">{candidate.file_path}</p>
                  <p className="text-[11px] text-gray-500">
                    confidence {Math.round(candidate.confidence * 100)}% · {candidate.reason}
                  </p>
                </div>
                {onUseDraft && (
                  <button
                    onClick={async () => {
                      onUseDraft(plan.step_id, candidate);
                      const result = await onFocusManualAction(plan.step_id, "create_proposal");
                      setActionResult(
                        "Draft inserted into Patch Proposal form. Review/edit fields, then Review Patch or Create Proposal manually."
                      );
                      setActionFocusError(result.error || "");
                    }}
                    className="rounded bg-gray-800 px-2 py-1 text-[11px] text-gray-200 hover:bg-gray-700"
                  >
                    Use in Patch Form
                  </button>
                )}
              </div>
              {candidate.warnings.length > 0 && (
                <p className="mt-1 text-[11px] text-yellow-400">{candidate.warnings.join("; ")}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function shortId(value: string): string {
  return value.length > 12 ? `${value.slice(0, 12)}…` : value;
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

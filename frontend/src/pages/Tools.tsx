import { useEffect, useMemo, useState } from "react";
import {
  analyzeCommandResult,
  applyProjectPatch,
  getProjectWorkspaceStatus,
  getProjectGitDiff,
  getProjectGitStatus,
  getProjectToolCalls,
  getProjects,
  getWorkspaceStatus,
  proposeProjectPatch,
  rollbackProjectPatch,
  runProjectBuild,
  runProjectCommand,
  runProjectTests,
  runTests,
} from "../api/client";
import type {
  ApplyPatchResponse,
  CommandAnalysisResponse,
  GitDiffResponse,
  GitStatusResponse,
  Project,
  ProjectCommandKind,
  ProjectToolResult,
  ProposePatchResponse,
  RollbackPatchResponse,
  RunProjectCommandResponse,
  TestRunResult,
  ToolCall,
  WorkspaceStatus,
} from "../types";

type PatchFormState = {
  run_id: string;
  step_id: string;
  agent_id: string;
  file_path: string;
  old_text: string;
  new_text: string;
  create_if_missing: boolean;
  replace_all: boolean;
};

const emptyPatchForm: PatchFormState = {
  run_id: "",
  step_id: "",
  agent_id: "",
  file_path: "",
  old_text: "",
  new_text: "",
  create_if_missing: false,
  replace_all: false,
};

export default function Tools() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [workspace, setWorkspace] = useState<WorkspaceStatus | null>(null);
  const [projectWorkspace, setProjectWorkspace] = useState<WorkspaceStatus | null>(null);
  const [projectGitStatus, setProjectGitStatus] = useState<GitStatusResponse | null>(null);
  const [projectGitDiff, setProjectGitDiff] = useState<GitDiffResponse | null>(null);
  const [selfTestRun, setSelfTestRun] = useState<TestRunResult | null>(null);
  const [projectToolRun, setProjectToolRun] = useState<ProjectToolResult | null>(null);
  const [projectToolCalls, setProjectToolCalls] = useState<ToolCall[]>([]);
  const [patchForm, setPatchForm] = useState<PatchFormState>(emptyPatchForm);
  const [patchPreview, setPatchPreview] = useState<ProposePatchResponse | null>(null);
  const [patchApplyResult, setPatchApplyResult] = useState<ApplyPatchResponse | null>(null);
  const [patchApplyConfirmed, setPatchApplyConfirmed] = useState(false);
  const [loadingStatus, setLoadingStatus] = useState(false);
  const [loadingGit, setLoadingGit] = useState(false);
  const [previewingPatch, setPreviewingPatch] = useState(false);
  const [applyingPatch, setApplyingPatch] = useState(false);
  const [showFullDiff, setShowFullDiff] = useState(false);
  const [runningSelfTests, setRunningSelfTests] = useState(false);
  const [runningProjectAction, setRunningProjectAction] = useState<"test" | "build" | "">("");
  const [commandKind, setCommandKind] = useState<ProjectCommandKind>("test");
  const [commandRunning, setCommandRunning] = useState(false);
  const [commandResult, setCommandResult] = useState<RunProjectCommandResponse | null>(null);
  const [commandError, setCommandError] = useState("");
  const [analysisRunning, setAnalysisRunning] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<CommandAnalysisResponse | null>(null);
  const [analysisError, setAnalysisError] = useState("");
  const [patchContext, setPatchContext] = useState<IssuePrefill | null>(null);
  const [error, setError] = useState("");
  const [gitError, setGitError] = useState("");
  const [patchError, setPatchError] = useState("");

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId) || null,
    [projectId, projects],
  );

  const loadWorkbenchStatus = async () => {
    setLoadingStatus(true);
    setError("");
    try {
      setWorkspace(await getWorkspaceStatus());
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingStatus(false);
    }
  };

  const loadProjects = async () => {
    try {
      const items = await getProjects();
      setProjects(items);
      setProjectId((current) => current || items[0]?.id || "");
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadProjectStatus = async (id = projectId) => {
    if (!id) {
      setProjectWorkspace(null);
      return;
    }
    setLoadingStatus(true);
    setError("");
    try {
      setProjectWorkspace(await getProjectWorkspaceStatus(id));
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoadingStatus(false);
    }
  };

  const loadProjectToolCalls = async (id = projectId) => {
    if (!id) {
      setProjectToolCalls([]);
      return;
    }
    try {
      setProjectToolCalls(await getProjectToolCalls(id));
    } catch (e: any) {
      setError(e.message);
    }
  };

  const loadProjectGit = async (id = projectId) => {
    if (!id) {
      setProjectGitStatus(null);
      setProjectGitDiff(null);
      setGitError("");
      return;
    }
    setLoadingGit(true);
    setGitError("");
    try {
      const [status, diff] = await Promise.all([getProjectGitStatus(id), getProjectGitDiff(id)]);
      setProjectGitStatus(status);
      setProjectGitDiff(diff);
    } catch (e: any) {
      setGitError(readableError(e));
    } finally {
      setLoadingGit(false);
    }
  };

  useEffect(() => {
    loadWorkbenchStatus();
    loadProjects();
  }, []);

  useEffect(() => {
    if (projectId) {
      loadProjectStatus(projectId);
      loadProjectGit(projectId);
      loadProjectToolCalls(projectId);
      setProjectToolRun(null);
      setPatchPreview(null);
      setPatchApplyResult(null);
      setPatchApplyConfirmed(false);
      setPatchError("");
      setShowFullDiff(false);
    }
  }, [projectId]);

  const refreshAll = async () => {
    await loadWorkbenchStatus();
    await loadProjectStatus();
    await loadProjectGit();
    await loadProjectToolCalls();
  };

  const handleRunSelfTests = async () => {
    setRunningSelfTests(true);
    setError("");
    try {
      const result = await runTests();
      setSelfTestRun(result);
      await loadWorkbenchStatus();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunningSelfTests(false);
    }
  };

  const handleProjectAction = async (kind: "test" | "build") => {
    if (!projectId) return;
    setRunningProjectAction(kind);
    setError("");
    try {
      const result = kind === "test" ? await runProjectTests(projectId) : await runProjectBuild(projectId);
      setProjectToolRun(result);
      await loadProjectStatus(projectId);
      await loadProjectToolCalls(projectId);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setRunningProjectAction("");
    }
  };

  const handleRunCommand = async () => {
    if (!projectId) return;
    setCommandRunning(true);
    setCommandError("");
    setCommandResult(null);
    setAnalysisResult(null);
    setAnalysisError("");
    try {
      const result = await runProjectCommand(projectId, { command_kind: commandKind });
      setCommandResult(result);
      await loadProjectToolCalls(projectId);
    } catch (e: any) {
      setCommandError(e.message);
    } finally {
      setCommandRunning(false);
    }
  };

  const handleAnalyzeCommand = async () => {
    if (!projectId || !commandResult) return;
    setAnalysisRunning(true);
    setAnalysisError("");
    setAnalysisResult(null);
    try {
      const result = await analyzeCommandResult(projectId, {
        tool_call_id: commandResult.tool_call_id || undefined,
        stdout: commandResult.stdout,
        stderr: commandResult.stderr,
        returncode: commandResult.returncode,
        command_kind: commandResult.command_kind,
      });
      setAnalysisResult(result);
    } catch (e: any) {
      setAnalysisError(e.message);
    } finally {
      setAnalysisRunning(false);
    }
  };

  const handlePreviewPatch = async () => {
    if (!projectId) return;
    if (!patchForm.file_path.trim()) {
      setPatchError("File path is required.");
      return;
    }
    setPreviewingPatch(true);
    setPatchError("");
    try {
      const result = await proposeProjectPatch(projectId, {
        operations: [patchOperationFromForm(patchForm)],
        run_id: patchForm.run_id.trim(),
        step_id: patchForm.step_id.trim(),
        agent_id: patchForm.agent_id.trim(),
      });
      setPatchPreview(result);
      setPatchApplyResult(null);
      setPatchApplyConfirmed(false);
      await loadProjectToolCalls(projectId);
    } catch (e: any) {
      setPatchError(readableError(e));
    } finally {
      setPreviewingPatch(false);
    }
  };

  const handleApplyPatch = async () => {
    if (!projectId || !patchApplyConfirmed) return;
    setApplyingPatch(true);
    setPatchError("");
    try {
      const result = await applyProjectPatch(projectId, {
        operations: [patchOperationFromForm(patchForm)],
        run_id: patchForm.run_id.trim(),
        step_id: patchForm.step_id.trim(),
        agent_id: patchForm.agent_id.trim(),
        confirm: true,
        expected_summary: patchPreview?.summary || "",
        proposal_id: patchPreview?.proposal_id || patchPreview?.tool_call_id || "",
      });
      setPatchApplyResult(result);
      await loadProjectToolCalls(projectId);
      await loadProjectStatus(projectId);
      await loadProjectGit(projectId);
    } catch (e: any) {
      setPatchError(readableError(e));
    } finally {
      setApplyingPatch(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-2xl font-bold">Tools</h2>
          <p className="text-sm text-gray-500 mt-1">Workbench and project-scoped local controls.</p>
        </div>
        <button
          onClick={refreshAll}
          disabled={loadingStatus}
          className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
        >
          {loadingStatus ? "Refreshing..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="rounded border border-red-800 bg-red-950/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h3 className="font-semibold">Project Scope</h3>
            <p className="mt-1 text-xs text-gray-500">Project commands run only when listed in safe commands.</p>
          </div>
          <select
            value={projectId}
            onChange={(event) => setProjectId(event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none lg:w-80"
          >
            {projects.length === 0 && <option value="">No projects configured</option>}
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>
        </div>

        {selectedProject ? (
          <>
            <div className="grid grid-cols-1 gap-2 text-xs text-gray-500 lg:grid-cols-2">
              <Info label="cwd" value={selectedProject.path} />
              <Info label="stack" value={selectedProject.stack || "unspecified"} />
              <Info label="test" value={selectedProject.test_command || "not configured"} />
              <Info label="build" value={selectedProject.build_command || "not configured"} />
            </div>

            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <button
                onClick={() => handleProjectAction("test")}
                disabled={runningProjectAction !== "" || !selectedProject.test_command}
                className="rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
              >
                {runningProjectAction === "test" ? "Running..." : "Run Project Tests"}
              </button>
              <button
                onClick={() => handleProjectAction("build")}
                disabled={runningProjectAction !== "" || !selectedProject.build_command}
                className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
              >
                {runningProjectAction === "build" ? "Running..." : "Run Project Build"}
              </button>
            </div>
          </>
        ) : (
          <p className="text-sm text-gray-500">Create a project profile to enable project-scoped tools.</p>
        )}
      </section>

      {projectWorkspace && (
        <WorkspacePanel title="Project Workspace" workspace={projectWorkspace} />
      )}

      {selectedProject && (
        <section className="rounded border border-gray-800 bg-gray-900 p-4">
          <h3 className="mb-3 font-semibold">Run Project Command</h3>
          <p className="mb-3 text-xs text-gray-500">
            Runs only commands from the Project Profile (test_command, build_command, safe_commands). No arbitrary shell input.
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <select
              value={commandKind}
              onChange={(e) => { setCommandKind(e.target.value as ProjectCommandKind); setCommandResult(null); setCommandError(""); }}
              className="rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200"
            >
              <option value="test">test</option>
              <option value="build">build</option>
              <option value="lint">lint</option>
              <option value="typecheck">typecheck</option>
            </select>
            <button
              onClick={handleRunCommand}
              disabled={commandRunning}
              className="rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
            >
              {commandRunning ? "Running…" : "Run"}
            </button>
          </div>
          {commandError && (
            <p className="mt-3 rounded bg-red-950/30 px-3 py-2 text-sm text-red-300">{commandError}</p>
          )}
          {commandResult && (
            <div className="mt-4 space-y-3">
              <div className="flex flex-wrap gap-2 text-xs">
                <span className={`rounded px-2 py-1 ${commandResult.returncode === 0 ? "bg-emerald-900 text-emerald-300" : "bg-red-900 text-red-300"}`}>
                  exit {commandResult.returncode}
                </span>
                {commandResult.timed_out && (
                  <span className="rounded bg-yellow-900 px-2 py-1 text-yellow-300">TIMED OUT</span>
                )}
                <span className="rounded bg-gray-800 px-2 py-1 text-gray-400">{commandResult.command_kind}</span>
                <span className="rounded bg-gray-800 px-2 py-1 font-mono text-gray-400">{commandResult.command}</span>
                <span className="rounded bg-gray-800 px-2 py-1 text-gray-500">{commandResult.duration_ms} ms</span>
              </div>
              {(commandResult.returncode !== 0 || commandResult.timed_out) && (
                <button
                  onClick={handleAnalyzeCommand}
                  disabled={analysisRunning}
                  className="rounded bg-yellow-700 px-3 py-1.5 text-sm hover:bg-yellow-600 disabled:bg-gray-700 disabled:text-gray-500"
                >
                  {analysisRunning ? "Analyzing…" : "Analyze Result"}
                </button>
              )}
              {analysisError && (
                <p className="rounded bg-red-950/30 px-3 py-2 text-sm text-red-300">{analysisError}</p>
              )}
              {analysisResult && (
                <AnalysisPanel
                  result={analysisResult}
                  onUsePatch={(prefill) => {
                    setPatchForm((prev) => ({ ...prev, file_path: prefill.file_path, old_text: "", new_text: "" }));
                    setPatchPreview(null);
                    setPatchApplyResult(null);
                    setPatchApplyConfirmed(false);
                    setPatchError("");
                    setPatchContext(prefill);
                    document.getElementById("patch-proposal-section")?.scrollIntoView({ behavior: "smooth" });
                  }}
                />
              )}
              {commandResult.stdout && (
                <LogBlock title="Stdout" value={commandResult.stdout} />
              )}
              {commandResult.stderr && (
                <LogBlock title="Stderr" value={commandResult.stderr} />
              )}
            </div>
          )}
        </section>
      )}

      {selectedProject && (
        <PatchProposalPanel
          form={patchForm}
          preview={patchPreview}
          applyResult={patchApplyResult}
          error={patchError}
          previewing={previewingPatch}
          applying={applyingPatch}
          applyConfirmed={patchApplyConfirmed}
          issueContext={patchContext}
          onDismissContext={() => setPatchContext(null)}
          onApplyConfirmedChange={setPatchApplyConfirmed}
          onChange={(next) => {
            setPatchForm(next);
            setPatchPreview(null);
            setPatchApplyResult(null);
            setPatchApplyConfirmed(false);
            setPatchError("");
          }}
          onPreview={handlePreviewPatch}
          onApply={handleApplyPatch}
        />
      )}

      {selectedProject && (
        <ProjectGitPanel
          status={projectGitStatus}
          diff={projectGitDiff}
          error={gitError}
          loading={loadingGit}
          showFullDiff={showFullDiff}
          onRefresh={() => loadProjectGit()}
          onToggleFullDiff={() => setShowFullDiff((current) => !current)}
        />
      )}

      {projectToolRun && <ProjectToolPanel result={projectToolRun} />}

      {selectedProject && (
        <ToolHistoryPanel
          calls={projectToolCalls}
          projectId={selectedProject.id}
          onRefresh={() => loadProjectToolCalls()}
        />
      )}

      <WorkspacePanel title="Workbench Workspace" workspace={workspace} />

      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 className="font-semibold">Workbench Test Runner</h3>
            <p className="text-xs text-gray-500 mt-1">Runs `bash scripts/run_tests.sh` for AI Workbench itself.</p>
          </div>
          <button
            onClick={handleRunSelfTests}
            disabled={runningSelfTests}
            className="rounded bg-emerald-600 px-4 py-2 text-sm hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500"
          >
            {runningSelfTests ? "Running..." : "Run Workbench Tests"}
          </button>
        </div>

        {selfTestRun && (
          <div className="mt-4">
            <RunSummary
              status={selfTestRun.status}
              returncode={selfTestRun.returncode}
              reportPath={selfTestRun.report_path}
            />
            <LogBlock title="Stdout" value={selfTestRun.stdout || "(empty)"} />
            {selfTestRun.stderr && <LogBlock title="Stderr" value={selfTestRun.stderr} />}
          </div>
        )}
      </section>
    </div>
  );
}

function ToolHistoryRow({
  call,
  projectId,
  onRefresh,
}: {
  call: ToolCall;
  projectId: string;
  onRefresh: () => void;
}) {
  const isApplyPatch = call.tool_name === "apply-patch";
  const hasRollbackData = isApplyPatch && (() => {
    try {
      const out = JSON.parse(call.output_json || "{}");
      return Array.isArray(out.rollback_data) && out.rollback_data.length > 0 &&
        out.rollback_data.some((e: any) => e.rollback_supported);
    } catch { return false; }
  })();

  const [rollbackConfirmed, setRollbackConfirmed] = useState(false);
  const [rollbackRunning, setRollbackRunning] = useState(false);
  const [rollbackResult, setRollbackResult] = useState<RollbackPatchResponse | null>(null);
  const [rollbackError, setRollbackError] = useState("");

  async function handleRollback() {
    if (!rollbackConfirmed || rollbackRunning) return;
    setRollbackRunning(true);
    setRollbackError("");
    setRollbackResult(null);
    try {
      const res = await rollbackProjectPatch(projectId, {
        tool_call_id: call.id,
        confirm: true,
      });
      setRollbackResult(res);
      onRefresh();
    } catch (err: any) {
      setRollbackError(err?.message || "Rollback failed");
    } finally {
      setRollbackRunning(false);
    }
  }

  return (
    <div className="py-3">
      <div className="grid gap-2 lg:grid-cols-[160px_1fr_auto] lg:items-start">
        <div className="space-y-1">
          <span className={`inline-flex rounded px-2 py-1 text-xs ${toolStatusClass(call.status)}`}>
            {call.status}
          </span>
          <p className="text-xs text-gray-500">{call.tool_name}</p>
          <p className="text-xs text-gray-600">risk: {call.risk_level || "low"}</p>
        </div>
        <div className="min-w-0">
          <p className="truncate font-mono text-xs text-gray-300">{call.command || call.tool_name}</p>
          <p className="mt-1 truncate text-xs text-gray-500">cwd: {call.cwd}</p>
          {call.error ? (
            <p className="mt-1 rounded bg-red-950/30 px-2 py-1 text-xs text-red-300">
              {truncate(call.error, 220)}
            </p>
          ) : (
            <p className="mt-1 text-xs text-gray-500">{summarizeToolCall(call)}</p>
          )}
          {call.approval_id && (
            <p className="mt-1 font-mono text-xs text-yellow-300">approval: {call.approval_id}</p>
          )}
        </div>
        <div className="text-xs text-gray-500 lg:text-right">
          <p>Exit: {call.returncode ?? "none"}</p>
          <p className="mt-1">{call.completed_at || call.finished_at || call.created_at}</p>
          {call.report_path && <p className="mt-1">{call.report_path}</p>}
        </div>
      </div>

      {isApplyPatch && (
        <div className="mt-3 rounded border border-gray-700 bg-gray-800/50 p-3">
          {!hasRollbackData ? (
            <p className="text-xs text-gray-500">No rollback metadata available for this patch.</p>
          ) : rollbackResult ? (
            <RollbackResultPanel result={rollbackResult} />
          ) : (
            <div className="space-y-2">
              <label className="flex cursor-pointer items-start gap-2 text-xs text-yellow-300">
                <input
                  type="checkbox"
                  checked={rollbackConfirmed}
                  onChange={(e) => setRollbackConfirmed(e.target.checked)}
                  className="mt-0.5 accent-yellow-400"
                />
                I understand this will modify files by reverting a previous patch
              </label>
              {rollbackError && (
                <p className="rounded bg-red-950/30 px-2 py-1 text-xs text-red-300">{rollbackError}</p>
              )}
              <button
                onClick={handleRollback}
                disabled={!rollbackConfirmed || rollbackRunning}
                className="rounded bg-yellow-700 px-3 py-1.5 text-xs text-white hover:bg-yellow-600 disabled:bg-gray-700 disabled:text-gray-500"
              >
                {rollbackRunning ? "Rolling back…" : "Rollback This Patch"}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function RollbackResultPanel({ result }: { result: RollbackPatchResponse }) {
  return (
    <div className="space-y-2 text-xs">
      <p className="font-semibold text-green-400">Rollback complete</p>
      {result.rolled_back_files.length > 0 && (
        <div>
          <p className="text-gray-400">Restored:</p>
          <ul className="mt-1 space-y-0.5">
            {result.rolled_back_files.map((f) => (
              <li key={f.path} className="font-mono text-gray-300">
                [{f.status}] {f.path}
                {f.reason && <span className="ml-1 text-gray-500">({f.reason})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {result.skipped_files.length > 0 && (
        <div>
          <p className="text-yellow-400">Skipped:</p>
          <ul className="mt-1 space-y-0.5">
            {result.skipped_files.map((f) => (
              <li key={f.path} className="font-mono text-gray-300">
                [{f.status}] {f.path}
                {f.reason && <span className="ml-1 text-gray-500">({f.reason})</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      {result.warnings.length > 0 && (
        <div>
          <p className="text-yellow-400">Warnings:</p>
          <ul className="mt-1 space-y-0.5">
            {result.warnings.map((w, i) => (
              <li key={i} className="text-yellow-300">{w}</li>
            ))}
          </ul>
        </div>
      )}
      {result.git_status && (
        <pre className="mt-2 rounded bg-gray-900 p-2 font-mono text-xs text-gray-400 whitespace-pre-wrap">
          {result.git_status}
        </pre>
      )}
    </div>
  );
}

function ToolHistoryPanel({
  calls,
  projectId,
  onRefresh,
}: {
  calls: ToolCall[];
  projectId: string;
  onRefresh: () => void;
}) {
  const recent = [...calls]
    .sort((a, b) => toolCallTime(b).localeCompare(toolCallTime(a)))
    .slice(0, 12);

  return (
    <section className="rounded border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold">Project Tool History</h3>
        <span className="text-xs text-gray-500">{calls.length} logged calls</span>
      </div>
      {calls.length === 0 ? (
        <p className="text-sm text-gray-500">No project tool executions yet.</p>
      ) : (
        <div className="divide-y divide-gray-800">
          {recent.map((call) => (
            <ToolHistoryRow
              key={call.id}
              call={call}
              projectId={projectId}
              onRefresh={onRefresh}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function PatchProposalPanel({
  form,
  preview,
  applyResult,
  error,
  previewing,
  applying,
  applyConfirmed,
  issueContext,
  onDismissContext,
  onChange,
  onPreview,
  onApply,
  onApplyConfirmedChange,
}: {
  form: PatchFormState;
  preview: ProposePatchResponse | null;
  applyResult: ApplyPatchResponse | null;
  error: string;
  previewing: boolean;
  applying: boolean;
  applyConfirmed: boolean;
  issueContext?: IssuePrefill | null;
  onDismissContext?: () => void;
  onChange: (form: PatchFormState) => void;
  onPreview: () => void;
  onApply: () => void;
  onApplyConfirmedChange: (confirmed: boolean) => void;
}) {
  const update = <K extends keyof PatchFormState>(key: K, value: PatchFormState[K]) =>
    onChange({ ...form, [key]: value });
  const canApply = Boolean(
    preview &&
      preview.files.length > 0 &&
      preview.files.every((file) => file.status !== "error") &&
      applyConfirmed &&
      !previewing &&
      !applying,
  );

  return (
    <section id="patch-proposal-section" className="rounded border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4">
        <h3 className="font-semibold">Patch Proposal Preview</h3>
        <p className="mt-1 text-xs text-gray-500">
          Builds a diff preview only. No files are modified and there is no Apply action here.
        </p>
      </div>

      {/* Issue context banner — pre-filled from analysis */}
      {issueContext && (
        <div className="mb-4 rounded border border-blue-800 bg-blue-950/20 p-3 space-y-1">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-blue-300">Issue context (pre-filled from analysis)</p>
            {onDismissContext && (
              <button onClick={onDismissContext} className="text-xs text-gray-500 hover:text-gray-300">dismiss</button>
            )}
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
        <div className="mb-4 rounded border border-red-800 bg-red-950/30 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <label className="block">
          <span className="mb-1 block text-xs text-gray-500">Run ID optional</span>
          <input
            value={form.run_id}
            onChange={(event) => update("run_id", event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-gray-500">Step ID optional</span>
          <input
            value={form.step_id}
            onChange={(event) => update("step_id", event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="block lg:col-span-2">
          <span className="mb-1 block text-xs text-gray-500">Agent ID optional</span>
          <input
            value={form.agent_id}
            onChange={(event) => update("agent_id", event.target.value)}
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="block lg:col-span-2">
          <span className="mb-1 block text-xs text-gray-500">File path</span>
          <textarea
            value={form.file_path}
            onChange={(event) => update("file_path", event.target.value)}
            rows={2}
            placeholder="src/example.ts"
            className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-gray-500">Old text</span>
          <textarea
            value={form.old_text}
            onChange={(event) => update("old_text", event.target.value)}
            rows={8}
            className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-gray-500">New text</span>
          <textarea
            value={form.new_text}
            onChange={(event) => update("new_text", event.target.value)}
            rows={8}
            className="w-full resize-y rounded border border-gray-700 bg-gray-800 px-3 py-2 font-mono text-sm focus:border-emerald-500 focus:outline-none"
          />
        </label>
      </div>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-4 text-sm text-gray-400">
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.create_if_missing}
              onChange={(event) => update("create_if_missing", event.target.checked)}
              className="h-4 w-4 rounded border-gray-700 bg-gray-800"
            />
            Create if missing
          </label>
          <label className="inline-flex items-center gap-2">
            <input
              type="checkbox"
              checked={form.replace_all}
              onChange={(event) => update("replace_all", event.target.checked)}
              className="h-4 w-4 rounded border-gray-700 bg-gray-800"
            />
            Replace all occurrences
          </label>
        </div>
        <button
          onClick={onPreview}
          disabled={previewing || applying}
          className="rounded bg-emerald-700 px-4 py-2 text-sm hover:bg-emerald-600 disabled:bg-gray-700 disabled:text-gray-500"
        >
          {previewing ? "Previewing..." : "Preview Patch"}
        </button>
      </div>

      {preview && (
        <div className="mt-5 space-y-4">
          <div className="rounded border border-gray-800 bg-gray-950 p-3">
            <p className="text-sm text-gray-300">{preview.summary}</p>
            {preview.warnings.length > 0 && (
              <p className="mt-2 text-xs text-yellow-300">{preview.warnings.join(" ")}</p>
            )}
          {preview.tool_call_id && (
            <p className="mt-2 font-mono text-xs text-gray-500">tool call: {preview.tool_call_id}</p>
          )}
          {preview.proposal_id && (
            <p className="mt-1 font-mono text-xs text-gray-500">proposal: {preview.proposal_id}</p>
          )}
          </div>
          {preview.files.map((file) => (
            <article key={file.path} className="rounded border border-gray-800 bg-gray-950 p-3">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className={`rounded px-2 py-1 text-xs ${patchStatusClass(file.status)}`}>
                  {file.status}
                </span>
                <span className="font-mono text-sm text-gray-300">{file.path}</span>
                {file.error && <span className="text-sm text-red-300">{file.error}</span>}
              </div>
              {file.diff ? (
                <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-xs text-gray-300">
                  {file.diff}
                </pre>
              ) : (
                <p className="text-sm text-gray-500">No diff generated for this operation.</p>
              )}
            </article>
          ))}

          <div className="rounded border border-yellow-800 bg-yellow-950/20 p-3">
            <label className="flex items-start gap-3 text-sm text-yellow-100">
              <input
                type="checkbox"
                checked={applyConfirmed}
                onChange={(event) => onApplyConfirmedChange(event.target.checked)}
                disabled={preview.files.some((file) => file.status === "error") || applying}
                className="mt-1 h-4 w-4 rounded border-gray-700 bg-gray-800"
              />
              <span>
                I understand this will modify files in the selected project workspace.
              </span>
            </label>
            <button
              onClick={onApply}
              disabled={!canApply}
              className="mt-3 rounded bg-red-800 px-4 py-2 text-sm hover:bg-red-700 disabled:bg-gray-700 disabled:text-gray-500"
            >
              {applying ? "Applying..." : "Apply Patch"}
            </button>
          </div>
        </div>
      )}

      {applyResult && (
        <div className="mt-5 rounded border border-emerald-900 bg-emerald-950/20 p-3">
          <h4 className="font-medium text-emerald-200">Apply result</h4>
          <p className="mt-1 text-sm text-emerald-100">{applyResult.summary}</p>
          {applyResult.warnings.length > 0 && (
            <p className="mt-2 text-xs text-yellow-300">{applyResult.warnings.join(" ")}</p>
          )}
          <div className="mt-3 divide-y divide-emerald-900/50">
            {applyResult.files.map((file) => (
              <div key={file.path} className="flex flex-wrap items-center gap-3 py-2 text-sm">
                <span className={`rounded px-2 py-1 text-xs ${appliedStatusClass(file.status)}`}>
                  {file.status}
                </span>
                <span className="font-mono text-emerald-100">{file.path}</span>
                {file.error && <span className="text-red-300">{file.error}</span>}
              </div>
            ))}
          </div>
          {applyResult.git_status && <LogBlock title="Git status after apply" value={applyResult.git_status} />}
          {applyResult.git_diff_stat && <LogBlock title="Git diff --stat after apply" value={applyResult.git_diff_stat} />}
          {applyResult.applied_from_proposal_id && (
            <p className="mt-2 font-mono text-xs text-gray-500">
              applied from proposal: {applyResult.applied_from_proposal_id}
            </p>
          )}
          {applyResult.tool_call_id && (
            <p className="mt-2 font-mono text-xs text-gray-500">tool call: {applyResult.tool_call_id}</p>
          )}
        </div>
      )}
    </section>
  );
}

function ProjectGitPanel({
  status,
  diff,
  error,
  loading,
  showFullDiff,
  onRefresh,
  onToggleFullDiff,
}: {
  status: GitStatusResponse | null;
  diff: GitDiffResponse | null;
  error: string;
  loading: boolean;
  showFullDiff: boolean;
  onRefresh: () => void;
  onToggleFullDiff: () => void;
}) {
  const gitError = error || status?.stderr || diff?.stderr || "";
  const isNotRepo = Boolean(gitError.match(/not a git repository|not a git repo|not a gitdir/i));
  const changedFiles = status?.changed_files || [];

  return (
    <section className="rounded border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold">Git Status / Diff</h3>
          <p className="mt-1 text-xs text-gray-500">Read-only project workspace inspection.</p>
        </div>
        <button
          onClick={onRefresh}
          disabled={loading}
          className="rounded bg-gray-800 px-4 py-2 text-sm hover:bg-gray-700 disabled:text-gray-500"
        >
          {loading ? "Refreshing..." : "Refresh Git Status"}
        </button>
      </div>

      {gitError && (
        <div className="mb-4 rounded border border-yellow-800 bg-yellow-950/20 p-3 text-sm text-yellow-200">
          {isNotRepo ? "This project folder is not a git repository." : gitError}
        </div>
      )}

      {!status ? (
        <p className="text-sm text-gray-500">Git status has not been loaded yet.</p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span
              className={`rounded px-2 py-1 text-xs ${
                status.clean ? "bg-emerald-900 text-emerald-300" : "bg-yellow-900 text-yellow-300"
              }`}
            >
              {status.clean ? "clean" : `${changedFiles.length} changes`}
            </span>
            <span className="truncate font-mono text-xs text-gray-500">{status.project_path}</span>
            {status.returncode !== 0 && <span className="text-xs text-yellow-300">git exited {status.returncode}</span>}
          </div>

          {changedFiles.length === 0 ? (
            <p className="text-sm text-gray-500">No changed files reported by git status.</p>
          ) : (
            <div className="divide-y divide-gray-800 rounded border border-gray-800 bg-gray-950">
              {changedFiles.map((file) => (
                <div key={`${file.status}-${file.path}`} className="flex items-center gap-3 px-3 py-2">
                  <span className="w-10 rounded bg-gray-800 px-2 py-1 text-center font-mono text-xs text-gray-300">
                    {file.status}
                  </span>
                  <span className="min-w-0 truncate text-sm text-gray-300">{file.path}</span>
                </div>
              ))}
            </div>
          )}

          <LogBlock title="Git status --short" value={status.stdout || "(empty)"} />

          {diff && (
            <div className="space-y-3">
              <LogBlock title="Git diff --stat" value={diff.stat || "(empty)"} />
              {diff.name_only.length > 0 && (
                <div>
                  <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">Changed paths</h4>
                  <div className="flex flex-wrap gap-2">
                    {diff.name_only.map((path) => (
                      <span key={path} className="rounded bg-gray-800 px-2 py-1 font-mono text-xs text-gray-300">
                        {path}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <button
                onClick={onToggleFullDiff}
                disabled={!diff.diff}
                className="rounded bg-gray-800 px-3 py-1.5 text-sm hover:bg-gray-700 disabled:text-gray-500"
              >
                {showFullDiff ? "Hide full diff" : "Show full diff"}
              </button>
              {diff.truncated && (
                <span className="ml-3 text-xs text-yellow-300">Diff is capped by the backend.</span>
              )}
              {showFullDiff && <LogBlock title="Git diff" value={diff.diff || "(empty)"} />}
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function WorkspacePanel({ title, workspace }: { title: string; workspace: WorkspaceStatus | null }) {
  return (
    <section className="rounded border border-gray-800 bg-gray-900 p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="min-w-0">
          <h3 className="font-semibold">{title}</h3>
          <p className="mt-1 truncate text-xs text-gray-500">cwd: {workspace?.cwd || "unknown"}</p>
          <p className="mt-1 text-xs text-gray-500">Branch: {workspace?.branch || "unknown"}</p>
        </div>
        <span
          className={`rounded px-2 py-1 text-xs ${
            workspace?.clean ? "bg-emerald-900 text-emerald-300" : "bg-yellow-900 text-yellow-300"
          }`}
        >
          {workspace?.clean ? "clean" : `${workspace?.changes.length ?? 0} changes`}
        </span>
      </div>

      {!workspace || workspace.changes.length === 0 ? (
        <div className="space-y-2">
          <p className="text-sm text-gray-500">No tracked workspace changes.</p>
          {workspace?.error && <p className="text-xs text-yellow-300">{workspace.error}</p>}
        </div>
      ) : (
        <div className="divide-y divide-gray-800">
          {workspace.changes.map((change) => (
            <div key={`${change.status}-${change.path}`} className="flex items-center gap-3 py-2">
              <span className="w-10 rounded bg-gray-800 px-2 py-1 text-center font-mono text-xs text-gray-300">
                {change.status}
              </span>
              <span className="truncate text-sm text-gray-300">{change.path}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

type IssuePrefill = {
  file_path: string;
  context_kind: string;
  context_location: string;
  context_message: string;
};

function AnalysisPanel({
  result,
  onUsePatch,
}: {
  result: CommandAnalysisResponse;
  onUsePatch?: (prefill: IssuePrefill) => void;
}) {
  const statusColor =
    result.status === "passed"
      ? "text-emerald-400"
      : result.status === "timed_out"
      ? "text-yellow-400"
      : "text-red-400";

  return (
    <div className="rounded border border-gray-700 bg-gray-850 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <span className={`font-semibold text-sm ${statusColor}`}>{result.status.toUpperCase()}</span>
        {result.can_create_fix_proposal && (
          <span className="rounded bg-blue-900 px-2 py-0.5 text-xs text-blue-300">fix proposal possible</span>
        )}
      </div>
      <p className="text-sm text-gray-300">{result.summary}</p>
      {result.issues.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Issues ({result.issues.length})</p>
          {result.issues.map((issue, i) => (
            <div key={i} className="rounded bg-gray-800 px-2 py-1.5 text-xs space-y-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="rounded bg-gray-700 px-1.5 py-0.5 text-gray-400">{issue.kind}</span>
                {issue.file_path && (
                  <span className="font-mono text-gray-400">
                    {issue.file_path}{issue.line != null ? `:${issue.line}` : ""}
                  </span>
                )}
              </div>
              <span className="text-gray-300">{issue.message}</span>
              {issue.file_path && onUsePatch && (
                <div>
                  <button
                    onClick={() =>
                      onUsePatch({
                        file_path: issue.file_path!,
                        context_kind: issue.kind,
                        context_location: `${issue.file_path}${issue.line != null ? `:${issue.line}` : ""}`,
                        context_message: issue.message,
                      })
                    }
                    className="rounded bg-blue-900 px-2 py-0.5 text-xs text-blue-300 hover:bg-blue-800"
                  >
                    Use for Patch Proposal ↓
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
      {result.suggested_next_actions.length > 0 && (
        <div className="space-y-1">
          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">Suggested actions</p>
          {result.suggested_next_actions.map((action, i) => (
            <p key={i} className="text-xs text-gray-400">→ {action}</p>
          ))}
        </div>
      )}
    </div>
  );
}


function ProjectToolPanel({ result }: { result: ProjectToolResult }) {
  return (
    <section
      className={`rounded border p-4 ${
        result.approval_required ? "border-yellow-800 bg-yellow-950/20" : "border-gray-800 bg-gray-900"
      }`}
    >
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="font-semibold">Project {result.command_type}</h3>
          <p className="mt-1 font-mono text-xs text-gray-500">{result.command || "(empty)"}</p>
        </div>
        <RunSummary status={result.status} returncode={result.returncode} reportPath={result.report_path} />
      </div>

      {result.approval_required && (
        <div className="mb-4 rounded border border-yellow-800 bg-yellow-950/30 p-3 text-sm text-yellow-200">
          <p className="font-medium">Approval required</p>
          <p className="mt-1 text-yellow-300">{result.action || "policy"}: {result.description || "Command was not executed."}</p>
          {result.approval_id && (
            <p className="mt-2 font-mono text-xs text-yellow-300">Approval ID: {result.approval_id}</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-1 gap-2 text-xs text-gray-500 lg:grid-cols-2">
        <Info label="project" value={result.project_id} />
        <Info label="cwd" value={result.project_path} />
      </div>

      <div className="mt-4">
        <LogBlock title="Stdout" value={result.stdout || "(empty)"} />
        {result.stderr && <LogBlock title="Stderr" value={result.stderr} />}
      </div>
    </section>
  );
}

function RunSummary({
  status,
  returncode,
  reportPath,
}: {
  status: string;
  returncode: number | null;
  reportPath: string;
}) {
  const color =
    status === "passed"
      ? "bg-emerald-900 text-emerald-300"
      : status === "approval_required"
        ? "bg-yellow-900 text-yellow-300"
        : "bg-red-900 text-red-300";
  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <span className={`rounded px-2 py-1 text-xs ${color}`}>{status}</span>
      <span className="text-gray-400">Exit code: {returncode ?? "none"}</span>
      {reportPath && <span className="text-gray-500">{reportPath}</span>}
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded bg-gray-950 px-3 py-2">
      <span className="text-gray-600">{label}</span>
      <p className="mt-1 truncate font-mono text-gray-400">{value}</p>
    </div>
  );
}

function LogBlock({ title, value }: { title: string; value: string }) {
  return (
    <div className="mt-3">
      <h4 className="mb-2 text-xs font-medium uppercase text-gray-500">{title}</h4>
      <pre className="max-h-80 overflow-auto rounded bg-gray-950 p-3 text-xs text-gray-300 whitespace-pre-wrap">
        {value}
      </pre>
    </div>
  );
}

function toolCallTime(call: ToolCall): string {
  return call.completed_at || call.finished_at || call.created_at || "";
}

function toolStatusClass(status: string): string {
  if (status === "passed" || status === "completed") return "bg-emerald-900 text-emerald-300";
  if (status === "pending" || status === "approval_required") return "bg-yellow-900 text-yellow-300";
  if (status === "failed") return "bg-red-900 text-red-300";
  return "bg-gray-800 text-gray-300";
}

function patchStatusClass(status: string): string {
  if (status === "create") return "bg-blue-900 text-blue-300";
  if (status === "modify") return "bg-emerald-900 text-emerald-300";
  if (status === "unchanged") return "bg-gray-800 text-gray-300";
  if (status === "error") return "bg-red-900 text-red-300";
  return "bg-gray-800 text-gray-300";
}

function appliedStatusClass(status: string): string {
  if (status === "created") return "bg-blue-900 text-blue-300";
  if (status === "modified") return "bg-emerald-900 text-emerald-300";
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

function summarizeToolCall(call: ToolCall): string {
  const raw = call.output_json?.trim();
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed.files)) return `${parsed.files.length} files listed`;
      if (Array.isArray(parsed.matches)) return `${parsed.matches.length} matches found`;
      if (typeof parsed.content === "string") {
        const path = typeof parsed.path === "string" ? `${parsed.path}: ` : "";
        return `${path}${parsed.content.length} characters read`;
      }
      return truncate(JSON.stringify(parsed), 220);
    } catch {
      return truncate(raw, 220);
    }
  }
  return truncate(call.stdout || call.stderr || "(no output)", 220);
}

function truncate(value: string, max: number): string {
  return value.length > max ? `${value.slice(0, max)}...` : value;
}

function readableError(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to load data.";
}

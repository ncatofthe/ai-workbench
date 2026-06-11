import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  analyzeProjectIntake,
  buildModuleMapDraftFromIntake,
  buildMultiAgentPlanFromIntake,
  buildSoTDraftFromIntake,
  confirmModuleMapDraftFromIntake,
  createRun,
  createRunFromConfirmedPlan,
  draftProjectBrief,
  getProjects,
  previewIntakeDevelopmentRun,
  previewConfirmedRunCreationContract,
  createConfirmedDevelopmentRun,
  previewExistingProjectRepoIntake,
  previewClarifiedIntake,
  previewConfirmedPlanRun,
  previewIntakePlan,
  previewRequirementCoverage,
  previewSourceOfTruth,
  previewUnifiedIntake,
} from "../api/client";
import type {
  ClarifiedIntakePreviewResponse,
  ClarifyingAnswer,
  ClarifyingAnswerGap,
  ClarifyingQuestion,
  ConfirmedPlanRunPreviewResponse,
  ConfirmedRunFromPlanResponse,
  ConfirmedRunStepPreview,
  DevelopmentPlanPhase,
  DevelopmentPlanPreviewResponse,
  DraftAgentPlanStep,
  DraftModuleMapPreview,
  DraftSourceOfTruthPreview,
  ExistingProjectRepoIntakeResponse,
  IntakeDevelopmentRunPreviewResponse,
  IntakeConfirmedRunCreationContractPreviewResponse,
  ConfirmedDevelopmentRunCreateResponse,
  Project,
  ProjectBriefDraftResponse,
  ProjectBriefSection,
  ProjectIntakeQuestion,
  ProjectIntakeResponse,
  RequirementCoveragePreviewResponse,
  RunMode,
  ModuleMapDraftFromIntakeResponse,
  MultiAgentPlanFromIntakeResponse,
  SourceOfTruthDraftFromIntakeResponse,
  SourceOfTruthPreviewResponse,
  UnifiedAutonomousIntakePreviewResponse,
  UnifiedIntakeMode,
} from "../types";

export default function NewTask() {
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<RunMode>("offline");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [error, setError] = useState("");
  const [intakeLoading, setIntakeLoading] = useState(false);
  const [intakeError, setIntakeError] = useState("");
  const [intakeResult, setIntakeResult] = useState<ProjectIntakeResponse | null>(null);
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState("");
  const [briefResult, setBriefResult] = useState<ProjectBriefDraftResponse | null>(null);
  const [planLoading, setPlanLoading] = useState(false);
  const [planError, setPlanError] = useState("");
  const [planResult, setPlanResult] = useState<DevelopmentPlanPreviewResponse | null>(null);
  const [sourceLoading, setSourceLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [sourceResult, setSourceResult] = useState<SourceOfTruthPreviewResponse | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [coverageError, setCoverageError] = useState("");
  const [coverageResult, setCoverageResult] = useState<RequirementCoveragePreviewResponse | null>(null);
  const [runPreviewLoading, setRunPreviewLoading] = useState(false);
  const [runPreviewError, setRunPreviewError] = useState("");
  const [runPreviewResult, setRunPreviewResult] = useState<ConfirmedPlanRunPreviewResponse | null>(null);
  const [confirmedRunLoading, setConfirmedRunLoading] = useState(false);
  const [confirmedRunError, setConfirmedRunError] = useState("");
  const [confirmedRunResult, setConfirmedRunResult] = useState<ConfirmedRunFromPlanResponse | null>(null);
  const [confirmChecked, setConfirmChecked] = useState(false);
  const [unifiedMode, setUnifiedMode] = useState<UnifiedIntakeMode>("idea");
  const [unifiedStack, setUnifiedStack] = useState("");
  const [unifiedPath, setUnifiedPath] = useState("");
  const [unifiedLoading, setUnifiedLoading] = useState(false);
  const [unifiedError, setUnifiedError] = useState("");
  const [unifiedResult, setUnifiedResult] = useState<UnifiedAutonomousIntakePreviewResponse | null>(null);
  const [repoIntakeResult, setRepoIntakeResult] = useState<ExistingProjectRepoIntakeResponse | null>(null);
  const [repoIntakeLoading, setRepoIntakeLoading] = useState(false);
  const [repoIntakeError, setRepoIntakeError] = useState("");
  // Clarifying Questions Engine v1
  const [answersMap, setAnswersMap] = useState<Record<string, string>>({});
  const [clarifiedResult, setClarifiedResult] = useState<ClarifiedIntakePreviewResponse | null>(null);
  const [clarifiedLoading, setClarifiedLoading] = useState(false);
  const [clarifiedError, setClarifiedError] = useState("");
  // Auto Source of Truth Draft from Intake v1
  const [sotDraftResult, setSotDraftResult] = useState<SourceOfTruthDraftFromIntakeResponse | null>(null);
  const [sotDraftLoading, setSotDraftLoading] = useState(false);
  const [sotDraftError, setSotDraftError] = useState("");
  // Auto Module Map Draft from Intake v1
  const [moduleMapDraftResult, setModuleMapDraftResult] = useState<ModuleMapDraftFromIntakeResponse | null>(null);
  const [moduleMapDraftLoading, setModuleMapDraftLoading] = useState(false);
  const [moduleMapDraftError, setModuleMapDraftError] = useState("");
  const [moduleMapPersistLoading, setModuleMapPersistLoading] = useState(false);
  const [moduleMapPersistError, setModuleMapPersistError] = useState("");
  // Multi-Agent Plan from Intake v1
  const [multiAgentPlanResult, setMultiAgentPlanResult] = useState<MultiAgentPlanFromIntakeResponse | null>(null);
  const [multiAgentPlanLoading, setMultiAgentPlanLoading] = useState(false);
  const [multiAgentPlanError, setMultiAgentPlanError] = useState("");
  // Intake to Confirmed Development Run Preview v1
  const [developmentRunPreviewResult, setDevelopmentRunPreviewResult] = useState<IntakeDevelopmentRunPreviewResponse | null>(null);
  const [developmentRunPreviewLoading, setDevelopmentRunPreviewLoading] = useState(false);
  const [developmentRunPreviewError, setDevelopmentRunPreviewError] = useState("");
  // Confirmed Run Creation Contract Preview v1
  const [contractPreviewResult, setContractPreviewResult] = useState<IntakeConfirmedRunCreationContractPreviewResponse | null>(null);
  const [contractPreviewLoading, setContractPreviewLoading] = useState(false);
  const [contractPreviewError, setContractPreviewError] = useState("");
  // Confirmed Development Run Bridge (Fastlane v1)
  const [bridgeConfirmCreate, setBridgeConfirmCreate] = useState(false);
  const [bridgeConfirmSoT, setBridgeConfirmSoT] = useState(false);
  const [bridgeConfirmModuleMap, setBridgeConfirmModuleMap] = useState(false);
  const [bridgeConfirmProvider, setBridgeConfirmProvider] = useState(false);
  const [bridgeConfirmLaterActions, setBridgeConfirmLaterActions] = useState(false);
  const [bridgeCreateResult, setBridgeCreateResult] = useState<ConfirmedDevelopmentRunCreateResponse | null>(null);
  const [bridgeCreateLoading, setBridgeCreateLoading] = useState(false);
  const [bridgeCreateError, setBridgeCreateError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    getProjects()
      .then((items) => {
        setProjects(items);
        setProjectId((current) => current || items[0]?.id || "");
      })
      .catch((e: any) => setError(e.message))
      .finally(() => setLoadingProjects(false));
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId) || null,
    [projectId, projects],
  );

  const canUnifiedPreview = Boolean(prompt.trim() && !unifiedLoading);
  const canPreviewRepoIntake = unifiedMode === "existing_project" && Boolean((unifiedPath.trim() || projectId) && !repoIntakeLoading);
  const canStart = Boolean(prompt.trim() && projectId && !loading);
  const canAnalyze = Boolean(prompt.trim() && !intakeLoading);
  const canDraftBrief = Boolean(prompt.trim() && !briefLoading);
  const canPreviewPlan = Boolean(prompt.trim() && !planLoading);
  const canPreviewSource = Boolean(prompt.trim() && !sourceLoading);
  const canPreviewCoverage = Boolean(prompt.trim() && !coverageLoading);
  const canPreviewRunSteps = Boolean(prompt.trim() && !runPreviewLoading);

  const _buildIntakePayload = () => ({
    mode: unifiedMode,
    title: prompt.trim(),
    raw_input: prompt.trim(),
    document_excerpt: unifiedMode === "document" ? prompt.trim() : "",
    project_path: unifiedMode === "existing_project" ? unifiedPath.trim() : "",
    known_stack: unifiedStack.split(",").map((s) => s.trim()).filter(Boolean),
    constraints: [] as string[],
    desired_outcome: "",
  });

  const handleUnifiedPreview = async () => {
    if (!canUnifiedPreview) return;
    setUnifiedLoading(true);
    setUnifiedError("");
    setAnswersMap({});
    setClarifiedResult(null);
    setSotDraftResult(null);
    setModuleMapDraftResult(null);
    setMultiAgentPlanResult(null);
    setDevelopmentRunPreviewResult(null);
    try {
      const result = await previewUnifiedIntake(_buildIntakePayload());
      setUnifiedResult(result);
    } catch (e: any) {
      setUnifiedError(e.message);
    } finally {
      setUnifiedLoading(false);
    }
  };

  const handlePreviewRepoIntake = async () => {
    if (!canPreviewRepoIntake) return;
    setRepoIntakeLoading(true);
    setRepoIntakeError("");
    try {
      const result = await previewExistingProjectRepoIntake({
        project_id: projectId || null,
        project_path: unifiedPath.trim(),
        max_files: 500,
        max_depth: 8,
        include_manifest_snippets: true,
      });
      setRepoIntakeResult(result);
      if (!unifiedStack.trim() && result.detected_stack.length > 0) {
        setUnifiedStack(result.detected_stack.join(", "));
      }
    } catch (e: any) {
      setRepoIntakeError(e.message);
    } finally {
      setRepoIntakeLoading(false);
    }
  };

  const handleAnswerChange = (questionId: string, value: string) => {
    setAnswersMap((prev) => ({ ...prev, [questionId]: value }));
  };

  const handleRefineWithAnswers = async () => {
    if (!unifiedResult) return;
    setClarifiedLoading(true);
    setClarifiedError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await previewClarifiedIntake({
        intake: _buildIntakePayload(),
        answers,
      });
      setClarifiedResult(result);
      setSotDraftResult(null);
      setModuleMapDraftResult(null);
      setMultiAgentPlanResult(null);
      setDevelopmentRunPreviewResult(null);
    } catch (e: any) {
      setClarifiedError(e.message);
    } finally {
      setClarifiedLoading(false);
    }
  };

  const handleBuildSoTDraft = async () => {
    setSotDraftLoading(true);
    setSotDraftError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await buildSoTDraftFromIntake({
        intake: { intake: _buildIntakePayload(), answers },
        project_id: null,
        confirm_persist: false,
      });
      setSotDraftResult(result);
      setMultiAgentPlanResult(null);
      setDevelopmentRunPreviewResult(null);
    } catch (e: any) {
      setSotDraftError(e.message);
    } finally {
      setSotDraftLoading(false);
    }
  };

  const handleBuildModuleMapDraft = async () => {
    setModuleMapDraftLoading(true);
    setModuleMapDraftError("");
    setModuleMapPersistError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await buildModuleMapDraftFromIntake({
        intake: { intake: _buildIntakePayload(), answers },
        source_of_truth_draft: sotDraftResult?.draft || null,
        project_id: null,
        confirm_persist: false,
      });
      setModuleMapDraftResult(result);
      setMultiAgentPlanResult(null);
      setDevelopmentRunPreviewResult(null);
    } catch (e: any) {
      setModuleMapDraftError(e.message);
    } finally {
      setModuleMapDraftLoading(false);
    }
  };

  const handlePersistModuleMapDraft = async () => {
    if (!projectId) {
      setModuleMapPersistError("Create/select a project before saving Module Map.");
      return;
    }
    setModuleMapPersistLoading(true);
    setModuleMapPersistError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await confirmModuleMapDraftFromIntake({
        intake: { intake: _buildIntakePayload(), answers },
        source_of_truth_draft: sotDraftResult?.draft || null,
        project_id: projectId,
        confirm_persist: true,
      });
      setModuleMapDraftResult(result);
      setMultiAgentPlanResult(null);
      setDevelopmentRunPreviewResult(null);
    } catch (e: any) {
      setModuleMapPersistError(e.message);
    } finally {
      setModuleMapPersistLoading(false);
    }
  };

  const handleBuildMultiAgentPlan = async () => {
    setMultiAgentPlanLoading(true);
    setMultiAgentPlanError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await buildMultiAgentPlanFromIntake({
        intake: _buildIntakePayload(),
        answers,
        source_of_truth_draft: sotDraftResult?.draft || null,
        module_map_draft: moduleMapDraftResult?.draft || null,
      });
      setMultiAgentPlanResult(result);
      setDevelopmentRunPreviewResult(null);
    } catch (e: any) {
      setMultiAgentPlanError(e.message);
    } finally {
      setMultiAgentPlanLoading(false);
    }
  };

  const handlePreviewDevelopmentRun = async () => {
    setDevelopmentRunPreviewLoading(true);
    setDevelopmentRunPreviewError("");
    try {
      const answers: ClarifyingAnswer[] = Object.entries(answersMap)
        .filter(([, v]) => v.trim())
        .map(([question_id, answer]) => ({ question_id, answer, skipped: false }));
      const result = await previewIntakeDevelopmentRun({
        intake: _buildIntakePayload(),
        answers,
        source_of_truth_draft: sotDraftResult?.draft || null,
        module_map_draft: moduleMapDraftResult?.draft || null,
        multi_agent_plan: multiAgentPlanResult || null,
        preferred_mode: "guided",
      });
      setDevelopmentRunPreviewResult(result);
      setContractPreviewResult(null);
      setBridgeCreateResult(null);
      setBridgeCreateError("");
      setBridgeConfirmCreate(false);
      setBridgeConfirmSoT(false);
      setBridgeConfirmModuleMap(false);
      setBridgeConfirmProvider(false);
      setBridgeConfirmLaterActions(false);
    } catch (e: any) {
      setDevelopmentRunPreviewError(e.message);
    } finally {
      setDevelopmentRunPreviewLoading(false);
    }
  };

  const handleEvaluateContractPreview = async () => {
    if (!developmentRunPreviewResult) return;
    setContractPreviewLoading(true);
    setContractPreviewError("");
    try {
      const result = await previewConfirmedRunCreationContract({
        development_run_preview: developmentRunPreviewResult as unknown as Record<string, unknown>,
        project_id: projectId || null,
        confirm: false,
        preview_only: true,
        source_of_truth_valid: !!(sotDraftResult?.validation?.valid),
        module_map_valid: !!(moduleMapDraftResult?.validation?.valid),
        multi_agent_plan_valid: !!(multiAgentPlanResult && multiAgentPlanResult.tasks && multiAgentPlanResult.tasks.length > 0),
      });
      setContractPreviewResult(result);
    } catch (e: any) {
      setContractPreviewError(e.message);
    } finally {
      setContractPreviewLoading(false);
    }
  };

  const handleCreateConfirmedDevelopmentRun = async () => {
    if (!developmentRunPreviewResult || !projectId) return;
    setBridgeCreateLoading(true);
    setBridgeCreateError("");
    try {
      const result = await createConfirmedDevelopmentRun({
        project_id: projectId,
        confirm_create: true,
        contract_confirmed: bridgeConfirmCreate,
        source_of_truth_confirmed: bridgeConfirmSoT,
        module_map_confirmed: bridgeConfirmModuleMap,
        provider_disabled_confirmed: bridgeConfirmProvider,
        later_actions_confirmed: bridgeConfirmLaterActions,
        development_run_preview: developmentRunPreviewResult as unknown as Record<string, unknown>,
        contract_preview: contractPreviewResult as unknown as Record<string, unknown> | null,
        repo_intake_preview: repoIntakeResult as unknown as Record<string, unknown> | null,
        preferred_run_mode: "guided",
      });
      setBridgeCreateResult(result);
      // Auto-navigate to RunDetail after successful creation
      if (result.created && result.run_id) {
        setTimeout(() => navigate(`/runs/${result.run_id}`), 1500);
      }
    } catch (e: any) {
      setBridgeCreateError(e.message);
    } finally {
      setBridgeCreateLoading(false);
    }
  };

  const handleAnalyzeIdea = async () => {
    if (!canAnalyze) return;
    setIntakeLoading(true);
    setIntakeError("");
    try {
      const result = await analyzeProjectIntake({ idea: prompt });
      setIntakeResult(result);
    } catch (e: any) {
      setIntakeError(e.message);
    } finally {
      setIntakeLoading(false);
    }
  };

  const handleDraftBrief = async () => {
    if (!canDraftBrief) return;
    setBriefLoading(true);
    setBriefError("");
    try {
      const result = await draftProjectBrief({ idea: prompt });
      setBriefResult(result);
    } catch (e: any) {
      setBriefError(e.message);
    } finally {
      setBriefLoading(false);
    }
  };

  const handlePreviewPlan = async () => {
    if (!canPreviewPlan) return;
    setPlanLoading(true);
    setPlanError("");
    try {
      const result = await previewIntakePlan({
        idea: prompt,
        brief_markdown: briefResult?.brief_markdown,
      });
      setPlanResult(result);
    } catch (e: any) {
      setPlanError(e.message);
    } finally {
      setPlanLoading(false);
    }
  };

  const handlePreviewSourceOfTruth = async () => {
    if (!canPreviewSource) return;
    setSourceLoading(true);
    setSourceError("");
    try {
      const result = await previewSourceOfTruth({
        idea: prompt,
        brief_markdown: briefResult?.brief_markdown,
        plan_summary: planResult?.summary,
        plan_phases: planResult?.phases,
      });
      setSourceResult(result);
    } catch (e: any) {
      setSourceError(e.message);
    } finally {
      setSourceLoading(false);
    }
  };

  const handlePreviewCoverage = async () => {
    if (!canPreviewCoverage) return;
    setCoverageLoading(true);
    setCoverageError("");
    try {
      const result = await previewRequirementCoverage({
        idea: prompt,
        brief_markdown: briefResult?.brief_markdown,
        plan_summary: planResult?.summary,
        plan_phases: planResult?.phases,
        plan_preview: planResult,
        source_of_truth: sourceResult?.source_of_truth,
      });
      setCoverageResult(result);
    } catch (e: any) {
      setCoverageError(e.message);
    } finally {
      setCoverageLoading(false);
    }
  };

  const handlePreviewRunSteps = async () => {
    if (!canPreviewRunSteps) return;
    setRunPreviewLoading(true);
    setRunPreviewError("");
    try {
      const result = await previewConfirmedPlanRun({ idea: prompt });
      setRunPreviewResult(result);
    } catch (e: any) {
      setRunPreviewError(e.message);
    } finally {
      setRunPreviewLoading(false);
    }
  };

  const handleCreateRunFromPlan = async () => {
    if (!confirmChecked || !prompt.trim()) return;
    setConfirmedRunLoading(true);
    setConfirmedRunError("");
    try {
      const result = await createRunFromConfirmedPlan({
        idea: prompt,
        confirm: true,
        project_id: projectId || undefined,
      });
      setConfirmedRunResult(result);
      // Navigate to the created run.
      if (result.run_id) {
        navigate(`/runs/${result.run_id}`);
      }
    } catch (e: any) {
      setConfirmedRunError(e.message);
    } finally {
      setConfirmedRunLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!canStart) return;
    setLoading(true);
    setError("");
    try {
      const run = await createRun({ prompt, mode, project_id: projectId });
      navigate(`/runs/${run.id}`);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h2 className="text-2xl font-bold">New Task</h2>
        <p className="mt-1 text-sm text-gray-500">Every run must be tied to a validated project profile.</p>
      </div>

      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <label className="block text-sm text-gray-400 mb-2">Project</label>
        {loadingProjects ? (
          <p className="text-sm text-gray-500">Loading projects...</p>
        ) : projects.length === 0 ? (
          <div className="rounded border border-yellow-900 bg-yellow-950/20 p-3 text-sm text-yellow-300">
            Create a project profile before starting a task.
          </div>
        ) : (
          <>
            <select
              value={projectId}
              onChange={(event) => setProjectId(event.target.value)}
              className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-sm focus:border-emerald-500 focus:outline-none"
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            {selectedProject && (
              <div className="mt-3 grid grid-cols-1 gap-2 text-xs text-gray-500 sm:grid-cols-2">
                <Info label="Path" value={selectedProject.path} />
                <Info label="Stack" value={selectedProject.stack || "unspecified"} />
                <Info label="Test" value={selectedProject.test_command || "not configured"} />
                <Info label="Build" value={selectedProject.build_command || "not configured"} />
              </div>
            )}
          </>
        )}
      </section>

      <div>
        <label className="block text-sm text-gray-400 mb-2">
          {unifiedMode === "document"
            ? "Paste your TZ / Requirements Document / КП"
            : unifiedMode === "existing_project"
            ? "Describe the goal for this existing project"
            : "Task / Idea Description"}
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={
            unifiedMode === "document"
              ? "Paste the full text of your TZ, КП, or requirements document here…"
              : unifiedMode === "existing_project"
              ? "Describe what you want to build or fix in the existing project…"
              : "Describe your idea, product, or task…"
          }
          rows={unifiedMode === "document" ? 16 : 6}
          className="w-full bg-gray-900 border border-gray-700 rounded p-3 text-sm focus:outline-none focus:border-emerald-500 resize-y"
        />
        {unifiedMode === "document" && (
          <p className="mt-1 text-[10px] text-gray-600">
            Paste the full document text. The system will extract requirements, clarify ambiguities, and build SoT / Module Map / Plan.
          </p>
        )}
      </div>

      <section className="rounded border border-indigo-900/60 bg-gray-900 p-4">
        <h3 className="text-sm font-semibold text-indigo-300">Autonomous Project Intake</h3>
        <p className="mt-1 text-xs text-gray-500">
          Choose your scenario, fill in the details, then run through the full pipeline to create a confirmed pending run.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {(["idea", "document", "existing_project"] as UnifiedIntakeMode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setUnifiedMode(m); setUnifiedResult(null); setClarifiedResult(null); setRepoIntakeResult(null); setRepoIntakeError(""); }}
              className={`rounded px-3 py-1.5 text-xs font-medium border transition-colors ${
                unifiedMode === m
                  ? "border-indigo-500 bg-indigo-900/30 text-indigo-300"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {m === "idea" ? "💡 Idea from Scratch" : m === "document" ? "📄 Document / TZ / КП" : "🔧 Existing Project"}
            </button>
          ))}
        </div>

        {unifiedMode === "idea" && (
          <p className="mt-2 text-[10px] text-gray-600">
            Describe your product idea. The system will ask clarifying questions, build SoT, Module Map, Multi-Agent Plan, and create a pending run.
          </p>
        )}
        {unifiedMode === "document" && (
          <p className="mt-2 text-[10px] text-gray-600">
            Paste your TZ, КП, or requirements document above. The system will extract requirements, build SoT, Module Map, and a development plan.
          </p>
        )}
        {unifiedMode === "existing_project" && (
          <p className="mt-2 text-[10px] text-gray-600">
            Enter the project path and describe the goal. The system scans the project's metadata (package.json, pyproject.toml, etc.) and generates targeted questions.
          </p>
        )}

        {unifiedMode === "existing_project" && (
          <div className="mt-3">
            <label className="block text-xs text-gray-400 mb-1">
              Project Path <span className="text-gray-600">(absolute path on this machine)</span>
            </label>
            <input
              type="text"
              value={unifiedPath}
              onChange={(e) => setUnifiedPath(e.target.value)}
              placeholder="/Users/you/projects/service-desk"
              className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
            />
            <p className="mt-1 text-[10px] text-gray-600">
              The system reads package.json, pyproject.toml, README and folder names — no source code is read.
            </p>
            <div className="mt-3 rounded border border-slate-800 bg-slate-950/40 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold text-slate-200">Existing Project Repo Intake</p>
                  <p className="mt-0.5 text-[10px] text-slate-500">
                    Read-only structure and manifest preview. No project, run, tool_call, provider call, command, patch, apply, or test execution is created.
                  </p>
                </div>
                <button
                  onClick={handlePreviewRepoIntake}
                  disabled={!canPreviewRepoIntake}
                  className="rounded bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-200 transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
                >
                  {repoIntakeLoading ? "Analyzing..." : "Analyze existing project structure"}
                </button>
              </div>
              {repoIntakeError && (
                <p className="mt-2 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
                  {repoIntakeError}
                </p>
              )}
              {repoIntakeResult && <ExistingProjectRepoIntakePanel result={repoIntakeResult} />}
            </div>
          </div>
        )}

        <div className="mt-3">
          <label className="block text-xs text-gray-500 mb-1">Known Stack (comma-separated, optional)</label>
          <input
            type="text"
            value={unifiedStack}
            onChange={(e) => setUnifiedStack(e.target.value)}
            placeholder="e.g. React, FastAPI, PostgreSQL, Docker"
            className="w-full rounded border border-gray-700 bg-gray-800 px-3 py-2 text-xs focus:outline-none focus:border-indigo-500"
          />
        </div>
        <div className="mt-3">
          <button
            onClick={handleUnifiedPreview}
            disabled={!canUnifiedPreview}
            className="rounded bg-indigo-800 px-4 py-2 text-xs font-medium text-indigo-200 transition-colors hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
          >
            {unifiedLoading ? "Generating preview..." : "Preview autonomous intake"}
          </button>
        </div>
        {unifiedError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {unifiedError}
          </p>
        )}
        {unifiedResult && (
          <UnifiedIntakePreviewPanel
            result={unifiedResult}
            answersMap={answersMap}
            onAnswerChange={handleAnswerChange}
            onRefine={handleRefineWithAnswers}
            clarifiedLoading={clarifiedLoading}
          />
        )}
        {clarifiedError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {clarifiedError}
          </p>
        )}
        {clarifiedResult && (
          <ClarifiedIntakePreviewPanel
            result={clarifiedResult}
            onBuildSoTDraft={handleBuildSoTDraft}
            onBuildModuleMapDraft={handleBuildModuleMapDraft}
            onPersistModuleMapDraft={handlePersistModuleMapDraft}
            onBuildMultiAgentPlan={handleBuildMultiAgentPlan}
            onPreviewDevelopmentRun={handlePreviewDevelopmentRun}
            sotDraftLoading={sotDraftLoading}
            sotDraftError={sotDraftError}
            sotDraftResult={sotDraftResult}
            moduleMapDraftLoading={moduleMapDraftLoading}
            moduleMapDraftError={moduleMapDraftError}
            moduleMapDraftResult={moduleMapDraftResult}
            moduleMapPersistLoading={moduleMapPersistLoading}
            moduleMapPersistError={moduleMapPersistError}
            multiAgentPlanLoading={multiAgentPlanLoading}
            multiAgentPlanError={multiAgentPlanError}
            multiAgentPlanResult={multiAgentPlanResult}
            developmentRunPreviewLoading={developmentRunPreviewLoading}
            developmentRunPreviewError={developmentRunPreviewError}
            developmentRunPreviewResult={developmentRunPreviewResult}
            onEvaluateContractPreview={handleEvaluateContractPreview}
            contractPreviewLoading={contractPreviewLoading}
            contractPreviewError={contractPreviewError}
            contractPreviewResult={contractPreviewResult}
            bridgeConfirmCreate={bridgeConfirmCreate}
            setBridgeConfirmCreate={setBridgeConfirmCreate}
            bridgeConfirmSoT={bridgeConfirmSoT}
            setBridgeConfirmSoT={setBridgeConfirmSoT}
            bridgeConfirmModuleMap={bridgeConfirmModuleMap}
            setBridgeConfirmModuleMap={setBridgeConfirmModuleMap}
            bridgeConfirmProvider={bridgeConfirmProvider}
            setBridgeConfirmProvider={setBridgeConfirmProvider}
            bridgeConfirmLaterActions={bridgeConfirmLaterActions}
            setBridgeConfirmLaterActions={setBridgeConfirmLaterActions}
            onCreateConfirmedDevelopmentRun={handleCreateConfirmedDevelopmentRun}
            bridgeCreateLoading={bridgeCreateLoading}
            bridgeCreateError={bridgeCreateError}
            bridgeCreateResult={bridgeCreateResult}
            selectedProjectId={projectId}
          />
        )}
      </section>

      <section className="rounded border border-gray-800 bg-gray-900 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-gray-200">Project Intake</h3>
            <p className="mt-1 text-xs text-gray-500">
              These questions are advisory. You can answer them in the task prompt or continue with defaults.
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Intake analysis is read-only. It does not create a run, execute tools, or call providers.
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Brief draft is read-only. It does not create a run, execute tools, or call providers.
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Plan preview is read-only. It does not create a run, assign agents, execute tools, or call providers.
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Source of truth preview is read-only. It does not create a project/run, execute tools, or call providers.
            </p>
            <p className="mt-1 text-xs text-gray-600">
              Coverage preview is read-only. It does not save requirements, create a run, or execute anything.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleAnalyzeIdea}
              disabled={!canAnalyze}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {intakeLoading ? "Analyzing..." : "Analyze idea"}
            </button>
            <button
              onClick={handleDraftBrief}
              disabled={!canDraftBrief}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {briefLoading ? "Drafting..." : "Draft brief"}
            </button>
            <button
              onClick={handlePreviewPlan}
              disabled={!canPreviewPlan}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {planLoading ? "Previewing..." : "Preview plan"}
            </button>
            <button
              onClick={handlePreviewSourceOfTruth}
              disabled={!canPreviewSource}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {sourceLoading ? "Building..." : "Preview source of truth"}
            </button>
            <button
              onClick={handlePreviewCoverage}
              disabled={!canPreviewCoverage}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {coverageLoading ? "Checking..." : "Preview coverage"}
            </button>
            <button
              onClick={handlePreviewRunSteps}
              disabled={!canPreviewRunSteps}
              className="rounded bg-gray-800 px-3 py-2 text-xs font-medium text-gray-200 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {runPreviewLoading ? "Mapping..." : "Preview run steps"}
            </button>
          </div>
        </div>

        {intakeError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {intakeError}
          </p>
        )}

        {intakeResult && <IntakeResultPanel result={intakeResult} />}
        {briefError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {briefError}
          </p>
        )}
        {briefResult && <BriefDraftPanel result={briefResult} />}
        {planError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {planError}
          </p>
        )}
        {planResult && <PlanPreviewPanel result={planResult} />}
        {sourceError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {sourceError}
          </p>
        )}
        {sourceResult && <SourceOfTruthPanel result={sourceResult} />}
        {coverageError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {coverageError}
          </p>
        )}
        {coverageResult && <RequirementCoveragePanel result={coverageResult} />}
        {runPreviewError && (
          <p className="mt-3 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
            {runPreviewError}
          </p>
        )}
        {runPreviewResult && <RunStepPreviewPanel result={runPreviewResult} />}
        {runPreviewResult && (
          <div className="mt-4 space-y-3 rounded border border-gray-800 bg-gray-900/60 p-4">
            <p className="text-[10px] text-gray-500">
              Creating a run from plan creates pending run steps only. It does not execute agents,
              tools, patches, tests, or providers.
            </p>
            <label className="flex items-center gap-2 text-xs text-gray-300">
              <input
                type="checkbox"
                checked={confirmChecked}
                onChange={(e) => setConfirmChecked(e.target.checked)}
                className="rounded border-gray-600 bg-gray-800 text-emerald-500 focus:ring-emerald-500"
              />
              I confirm this source of truth, coverage, and run-step plan.
            </label>
            <button
              onClick={handleCreateRunFromPlan}
              disabled={!confirmChecked || confirmedRunLoading || !prompt.trim()}
              className="rounded bg-emerald-800 px-4 py-2 text-xs font-medium text-emerald-200 transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {confirmedRunLoading ? "Creating run..." : "Create run from confirmed plan"}
            </button>
            {confirmedRunError && (
              <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
                {confirmedRunError}
              </p>
            )}
            {confirmedRunResult && (
              <div className="rounded border border-emerald-800/60 bg-emerald-950/20 p-3">
                <p className="text-xs text-emerald-300">{confirmedRunResult.summary}</p>
                <p className="mt-1 text-[11px] text-gray-400">
                  Run ID: {confirmedRunResult.run_id} | Steps: {confirmedRunResult.steps_created} |
                  Status: {confirmedRunResult.run_status}
                </p>
              </div>
            )}
          </div>
        )}
      </section>

      <div>
        <label className="block text-sm text-gray-400 mb-2">Mode</label>
        <div className="flex flex-wrap gap-3">
          {(["offline", "hybrid", "cloud"] as RunMode[]).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-4 py-2 rounded text-sm border transition-colors ${
                mode === m
                  ? "border-emerald-500 bg-emerald-900/30 text-emerald-300"
                  : "border-gray-700 text-gray-400 hover:border-gray-500"
              }`}
            >
              {m.charAt(0).toUpperCase() + m.slice(1)}
            </button>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-2">
          {mode === "offline" && "Uses only local Ollama. No external API calls."}
          {mode === "hybrid" && "Local-first with cloud fallback when needed."}
          {mode === "cloud" && "Uses cloud providers when explicitly enabled."}
        </p>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={!canStart}
        className="px-6 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 disabled:text-gray-500 rounded text-sm font-medium transition-colors"
      >
        {loading ? "Starting..." : "Start Task"}
      </button>
    </div>
  );
}

function SourceOfTruthPanel({ result }: { result: SourceOfTruthPreviewResponse }) {
  const source = result.source_of_truth;
  const mustRequirements = source.requirements.filter((req) => req.priority === "must");
  const shouldRequirements = source.requirements.filter((req) => req.priority === "should");
  const couldRequirements = source.requirements.filter((req) => req.priority === "could");
  const constraints = source.constraints.map((constraint) => constraint.title);

  return (
    <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-1 text-xs font-medium ${
            result.ready_to_plan
              ? "bg-emerald-900/50 text-emerald-300"
              : "bg-yellow-900/40 text-yellow-300"
          }`}
        >
          {result.ready_to_plan ? "Ready to confirm" : "Needs validation"}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(source.source_type)}
        </span>
        <span className={`rounded px-2 py-1 text-xs font-medium ${driftRiskClass(result.validation.drift_risk)}`}>
          drift: {result.validation.drift_risk}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">{result.title}</p>
        <p className="mt-1 text-sm text-gray-400">{result.summary}</p>
        <p className="mt-2 text-xs text-gray-500">{source.product_goal}</p>
        {result.recommended_next_step && (
          <p className="mt-2 text-xs text-emerald-400">{result.recommended_next_step}</p>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <IntakeList title="Target users" items={source.target_users} empty="Target users are not confirmed." />
        <IntakeList title="User roles" items={source.user_roles} empty="User roles are not confirmed." />
        <IntakeList title="Constraints" items={constraints} empty="No constraints detected." />
        <IntakeList title="Forbidden changes" items={source.forbidden_changes} empty="No forbidden changes detected." />
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <RequirementList title="Must requirements" items={mustRequirements} />
        <RequirementList title="Should requirements" items={shouldRequirements} />
        <RequirementList title="Could requirements" items={couldRequirements} />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <SourceCardList
          title="Acceptance criteria"
          items={source.acceptance_criteria.map((item) => item.description)}
          empty="No acceptance criteria generated."
        />
        <SourceCardList
          title="Anti-drift rules"
          items={source.anti_drift_rules.map((item) => item.title)}
          empty="No anti-drift rules generated."
        />
        <SourceCardList title="Assumptions" items={source.assumptions} empty="No assumptions detected." />
        <SourceCardList title="Open questions" items={source.open_questions} empty="No open questions detected." />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <SourceCardList title="Validation gaps" items={result.validation.errors} empty="No validation errors." />
        <SourceCardList title="Validation warnings" items={result.validation.warnings} empty="No validation warnings." />
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">Requirement coverage</p>
        <p className="mt-1 text-xs text-gray-500">
          Coverage score: {Math.round(result.coverage_matrix.coverage_score * 100)}% | Missing:{" "}
          {result.coverage_matrix.missing_requirement_ids.length} | Unlinked plan items:{" "}
          {result.coverage_matrix.unlinked_plan_item_ids.length}
        </p>
      </div>
    </div>
  );
}

function RequirementCoveragePanel({ result }: { result: RequirementCoveragePreviewResponse }) {
  const covered = result.items.filter((item) => item.coverage_status === "covered");
  const partial = result.items.filter((item) => item.coverage_status === "partially_covered");
  const missing = result.items.filter((item) => item.coverage_status === "missing");
  const unclear = result.items.filter((item) => item.coverage_status === "unclear");

  return (
    <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-1 text-xs font-medium ${driftRiskClass(result.summary.drift_risk)}`}>
          drift: {result.summary.drift_risk}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          requirements: {result.summary.requirements_total}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          unlinked phases: {result.summary.unlinked_plan_phases}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">{result.title}</p>
        <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-gray-400 sm:grid-cols-5">
          <CoverageCount label="Covered" value={result.summary.covered_requirements} />
          <CoverageCount label="Partial" value={result.summary.partially_covered_requirements} />
          <CoverageCount label="Missing" value={result.summary.missing_requirements} />
          <CoverageCount label="Unclear" value={result.summary.unclear_requirements} />
          <CoverageCount label="Unlinked" value={result.summary.unlinked_plan_phases} />
        </div>
        {result.recommended_next_step && (
          <p className="mt-2 text-xs text-emerald-400">{result.recommended_next_step}</p>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <CoverageItemList title="Covered requirements" items={covered} empty="No covered requirements." />
        <CoverageItemList title="Partially covered requirements" items={partial} empty="No partial coverage." />
        <CoverageItemList title="Missing requirements" items={missing} empty="No missing requirements." />
        <CoverageItemList title="Unclear requirements" items={unclear} empty="No unclear requirements." />
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <UnlinkedPhaseList items={result.unlinked_plan_phases} />
        <SourceCardList title="Drift risks" items={result.drift_risks} empty="No drift risks detected." />
      </div>
    </div>
  );
}

function CoverageCount({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded bg-gray-900 px-2 py-1">
      <span className="text-gray-600">{label}</span>
      <p className="mt-1 text-sm font-semibold text-gray-300">{value}</p>
    </div>
  );
}

function CoverageItemList({
  title,
  items,
  empty,
}: {
  title: string;
  items: RequirementCoveragePreviewResponse["items"];
  empty: string;
}) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="text-xs font-medium text-gray-300">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-gray-600">{empty}</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item) => (
            <article key={item.requirement_id} className="rounded border border-gray-800 bg-gray-900 px-2 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${coverageStatusClass(item.coverage_status)}`}>
                  {formatLabel(item.coverage_status)}
                </span>
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${requirementPriorityClass(item.priority)}`}>
                  {item.priority}
                </span>
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${driftRiskClass(item.drift_risk)}`}>
                  {item.drift_risk}
                </span>
              </div>
              <p className="mt-2 text-xs font-medium text-gray-300">{item.title}</p>
              <p className="mt-1 text-xs text-gray-500">{item.notes}</p>
              {item.linked_plan_phases.length > 0 && (
                <p className="mt-2 text-xs text-gray-600">
                  Linked phases: {item.linked_plan_phases.map((phase) => phase.title).join(", ")}
                </p>
              )}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function UnlinkedPhaseList({ items }: { items: RequirementCoveragePreviewResponse["unlinked_plan_phases"] }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="text-xs font-medium text-gray-300">Unlinked plan phases</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-gray-600">No unlinked plan phases.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item) => (
            <article key={item.phase_id} className="rounded border border-gray-800 bg-gray-900 px-2 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${driftRiskClass(item.risk_level)}`}>
                  {item.risk_level}
                </span>
                <span className="rounded bg-gray-950 px-2 py-0.5 text-[11px] text-gray-500">{item.phase_id}</span>
              </div>
              <p className="mt-2 text-xs font-medium text-gray-300">{item.title}</p>
              <p className="mt-1 text-xs text-gray-500">{item.reason}</p>
              {item.suggested_action && <p className="mt-2 text-xs text-emerald-400">{item.suggested_action}</p>}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function RequirementList({
  title,
  items,
}: {
  title: string;
  items: SourceOfTruthPreviewResponse["source_of_truth"]["requirements"];
}) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="text-xs font-medium text-gray-300">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-gray-600">None.</p>
      ) : (
        <div className="mt-2 space-y-2">
          {items.map((item) => (
            <article key={item.id} className="rounded border border-gray-800 bg-gray-900 px-2 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${requirementPriorityClass(item.priority)}`}>
                  {item.priority}
                </span>
                <span className="rounded bg-gray-950 px-2 py-0.5 text-[11px] text-gray-500">
                  {formatLabel(item.status)}
                </span>
              </div>
              <p className="mt-2 text-xs font-medium text-gray-300">{item.title}</p>
              <p className="mt-1 text-xs text-gray-500">{item.description}</p>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function SourceCardList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="text-xs font-medium text-gray-300">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-gray-600">{empty}</p>
      ) : (
        <ul className="mt-1 space-y-1 text-xs text-gray-400">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function PlanPreviewPanel({ result }: { result: DevelopmentPlanPreviewResponse }) {
  return (
    <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-1 text-xs font-medium ${
            result.ready_to_start
              ? "bg-emerald-900/50 text-emerald-300"
              : "bg-yellow-900/40 text-yellow-300"
          }`}
        >
          {result.ready_to_start ? "Ready to start" : "Needs input"}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(result.mode)}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(result.target_type)}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">{result.title}</p>
        <p className="mt-1 text-sm text-gray-400">{result.summary}</p>
        <p className="mt-2 text-xs text-gray-500">
          Intake ready: {result.source_readiness.intake_ready_to_plan ? "yes" : "no"} | Brief ready:{" "}
          {result.source_readiness.brief_ready_to_plan ? "yes" : "no"}
        </p>
        {result.recommended_next_step && (
          <p className="mt-2 text-xs text-emerald-400">{result.recommended_next_step}</p>
        )}
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Plan phases</p>
        <div className="space-y-2">
          {result.phases.map((phase) => (
            <PlanPhaseCard key={phase.id} phase={phase} />
          ))}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <IntakeList title="Required inputs" items={result.required_inputs} empty="No required inputs detected." />
        <IntakeList title="Plan assumptions" items={result.assumptions} empty="No assumptions detected." />
        <IntakeList title="Plan risks" items={result.risks} empty="No major risks detected." />
        <IntakeList title="Recommended agents" items={result.recommended_agent_ids} empty="No agents recommended." />
      </div>
    </div>
  );
}

function PlanPhaseCard({ phase }: { phase: DevelopmentPlanPhase }) {
  return (
    <article className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${planPhaseStatusClass(phase.status)}`}>
          {formatLabel(phase.status)}
        </span>
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${priorityClass(phase.priority)}`}>
          {phase.priority}
        </span>
        {phase.suggested_agent_id && (
          <span className="rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">
            {phase.suggested_agent_id}
          </span>
        )}
      </div>
      <p className="mt-2 text-sm font-medium text-gray-200">{phase.title}</p>
      <p className="mt-1 text-xs text-gray-500">{phase.description}</p>
      {phase.depends_on.length > 0 && (
        <p className="mt-2 text-xs text-gray-600">Depends on: {phase.depends_on.join(", ")}</p>
      )}
      {phase.deliverables.length > 0 && (
        <div className="mt-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-gray-600">Deliverables</p>
          <ul className="mt-1 space-y-1 text-xs text-gray-400">
            {phase.deliverables.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
      {phase.risks.length > 0 && (
        <div className="mt-2">
          <p className="text-[11px] font-medium uppercase tracking-wide text-gray-600">Risks</p>
          <ul className="mt-1 space-y-1 text-xs text-yellow-300">
            {phase.risks.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      )}
    </article>
  );
}

function BriefDraftPanel({ result }: { result: ProjectBriefDraftResponse }) {
  return (
    <div className="mt-4 space-y-4 border-t border-gray-800 pt-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-1 text-xs font-medium ${
            result.ready_to_plan
              ? "bg-emerald-900/50 text-emerald-300"
              : "bg-yellow-900/40 text-yellow-300"
          }`}
        >
          {result.ready_to_plan ? "Ready to plan" : "Needs clarification"}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(result.mode)}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(result.target_type)}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">{result.title}</p>
        <p className="mt-1 text-sm text-gray-400">{result.summary}</p>
        {result.recommended_next_step && (
          <p className="mt-2 text-xs text-emerald-400">{result.recommended_next_step}</p>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        {result.sections.map((section) => (
          <BriefSectionCard key={section.title} section={section} />
        ))}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <IntakeList title="Brief assumptions" items={result.assumptions} empty="No assumptions detected." />
        <IntakeList title="Brief missing information" items={result.missing_information} empty="No major gaps detected." />
      </div>

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Open questions</p>
        {result.open_questions.length === 0 ? (
          <p className="rounded border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-gray-500">
            No open questions returned.
          </p>
        ) : (
          <div className="space-y-2">
            {result.open_questions.map((question) => (
              <IntakeQuestionCard key={question.id} question={question} />
            ))}
          </div>
        )}
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">Brief markdown preview</p>
        <pre className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap rounded bg-gray-900 p-3 text-xs leading-relaxed text-gray-400">
          {result.brief_markdown}
        </pre>
      </div>
    </div>
  );
}

function BriefSectionCard({ section }: { section: ProjectBriefSection }) {
  return (
    <article className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium text-gray-300">{section.title}</p>
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${sectionStatusClass(section.status)}`}>
          {section.status}
        </span>
      </div>
      <p className="mt-2 text-xs text-gray-400">{section.content}</p>
      {section.notes && <p className="mt-2 text-xs text-gray-600">{section.notes}</p>}
    </article>
  );
}

function IntakeResultPanel({ result }: { result: ProjectIntakeResponse }) {
  return (
    <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`rounded px-2 py-1 text-xs font-medium ${
            result.ready_to_plan
              ? "bg-emerald-900/50 text-emerald-300"
              : "bg-yellow-900/40 text-yellow-300"
          }`}
        >
          {result.ready_to_plan ? "Ready to plan" : "Needs clarification"}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          {formatLabel(result.mode)}
        </span>
        <span className="rounded bg-gray-950 px-2 py-1 text-xs text-gray-400">
          confidence: {result.confidence}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-medium text-gray-300">Summary</p>
        <p className="mt-1 text-sm text-gray-400">{result.summary}</p>
        {result.recommended_next_step && (
          <p className="mt-2 text-xs text-emerald-400">{result.recommended_next_step}</p>
        )}
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <IntakeList title="Assumptions" items={result.assumptions} empty="No assumptions detected." />
        <IntakeList title="Missing information" items={result.missing_information} empty="No major gaps detected." />
      </div>

      {result.mode === "existing_project" && <ExistingProjectChecklist questions={result.questions} />}

      <div className="space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">Clarifying questions</p>
        {result.questions.length === 0 ? (
          <p className="rounded border border-gray-800 bg-gray-950 px-3 py-2 text-xs text-gray-500">
            No clarifying questions returned.
          </p>
        ) : (
          <div className="space-y-2">
            {result.questions.map((question) => (
              <IntakeQuestionCard key={question.id} question={question} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

const EXISTING_PROJECT_CHECKLIST = [
  {
    label: "Project location/path",
    keywords: ["project files", "path", "repository url", "located"],
  },
  {
    label: "Stack/frameworks",
    keywords: ["tech stack", "framework"],
  },
  {
    label: "What already works",
    keywords: ["already works", "current state"],
  },
  {
    label: "What is broken",
    keywords: ["broken", "incomplete", "fixed first"],
  },
  {
    label: "Next development goal",
    keywords: ["next goal", "built or improved"],
  },
  {
    label: "Dev/build/test commands",
    keywords: ["dev/build commands", "development mode", "test command", "run them"],
  },
  {
    label: "DB/env/local services",
    keywords: ["database", "environment variables", "local services"],
  },
  {
    label: "Git status/history",
    keywords: ["git history", "branch structure"],
  },
  {
    label: "Dangerous files/secrets",
    keywords: ["not be modified", ".env", "secrets", "credentials", "ignored"],
  },
  {
    label: "Deployment target",
    keywords: ["deployment target", "hosting environment"],
  },
];

function ExistingProjectRepoIntakePanel({ result }: { result: ExistingProjectRepoIntakeResponse }) {
  const renderTags = (items: string[], empty: string, color = "text-slate-300") => (
    items.length > 0 ? (
      <div className="flex flex-wrap gap-1">
        {items.map((item) => (
          <span key={item} className={`rounded border border-gray-800 bg-gray-950 px-1.5 py-0.5 text-[10px] ${color}`}>
            {item}
          </span>
        ))}
      </div>
    ) : (
      <span className="text-[10px] text-gray-600">{empty}</span>
    )
  );

  return (
    <div className="mt-3 space-y-3 rounded border border-gray-800 bg-gray-950 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-slate-200">Repo Intake Preview</span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{result.detected_project_type}</span>
        {result.project_path_hint && (
          <span className="max-w-full truncate rounded bg-gray-900 px-2 py-0.5 font-mono text-[10px] text-gray-500">
            {result.project_path_hint}
          </span>
        )}
      </div>

      <div>
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Detected Stack</p>
        {renderTags(result.detected_stack, "No stack detected yet", "text-sky-300")}
      </div>

      {result.detected_areas.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Detected Areas</p>
          {result.detected_areas.map((area) => (
            <div key={area.id} className="rounded border border-gray-800 bg-gray-900 px-2 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-xs font-medium text-gray-200">{area.title}</span>
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">{area.kind}</span>
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">{area.confidence}</span>
              </div>
              <p className="mt-1 text-[10px] text-gray-500">
                Paths: {area.path_hints.slice(0, 8).join(", ") || "none"}
              </p>
              {area.notes.length > 0 && (
                <p className="mt-1 text-[10px] text-gray-600">{area.notes.join("; ")}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {result.manifest_summaries.length > 0 && (
        <div className="space-y-2">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">Manifest Summaries</p>
          {result.manifest_summaries.map((manifest) => (
            <div key={manifest.path} className="rounded border border-gray-800 bg-gray-900 px-2 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-gray-300">{manifest.path}</span>
                <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-400">{manifest.kind}</span>
              </div>
              {manifest.detected_scripts.length > 0 && (
                <p className="mt-1 text-[10px] text-emerald-300">Scripts: {manifest.detected_scripts.slice(0, 5).join("; ")}</p>
              )}
              {manifest.dependencies_hint.length > 0 && (
                <p className="mt-1 text-[10px] text-gray-500">Deps: {manifest.dependencies_hint.slice(0, 8).join(", ")}</p>
              )}
              {manifest.warnings.length > 0 && (
                <p className="mt-1 text-[10px] text-yellow-300">{manifest.warnings.join("; ")}</p>
              )}
            </div>
          ))}
        </div>
      )}

      {result.protected_path_warnings.length > 0 && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-yellow-300">Protected / Sensitive Path Warnings</p>
          {result.protected_path_warnings.map((warning, i) => (
            <p key={i} className="text-[11px] text-yellow-400">• {warning}</p>
          ))}
        </div>
      )}

      <div className="grid gap-2 md:grid-cols-3">
        <IntakeList title="Source of Truth hints" items={result.source_of_truth_hints} empty="No SoT hints yet." />
        <IntakeList title="Module Map hints" items={result.module_map_hints} empty="No Module Map hints yet." />
        <IntakeList title="Test discovery hints" items={result.test_discovery_hints} empty="No test hints yet." />
      </div>

      <IntakeList title="Recommended questions" items={result.clarifying_questions} empty="No additional questions." />

      <div className="rounded border border-slate-800 bg-slate-950/50 px-3 py-2">
        <p className="text-[10px] font-semibold text-slate-300">Recommended First Safe Action</p>
        <p className="mt-0.5 text-[11px] text-gray-400">{result.recommended_first_safe_action}</p>
      </div>

      <div className="grid gap-2 md:grid-cols-2">
        <IntakeList title="Safety notes" items={result.safety_notes} empty="No safety notes." />
        <IntakeList title="Limitations" items={result.limitations} empty="No limitations." />
      </div>
    </div>
  );
}

function ExistingProjectChecklist({ questions }: { questions: ProjectIntakeQuestion[] }) {
  const items = EXISTING_PROJECT_CHECKLIST.map((item) => ({
    ...item,
    question: findChecklistQuestion(questions, item.keywords),
  }));

  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Existing Project Onboarding Checklist
        </p>
        <span className="rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">Advisory</span>
      </div>
      <p className="mt-2 text-xs text-gray-600">
        Existing project onboarding is advisory only. It does not scan files, create a run, execute tools, or call providers.
      </p>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {items.map((item) => (
          <div key={item.label} className="rounded border border-gray-800 bg-gray-900 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span
                className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                  item.question ? priorityClass(item.question.priority) : "bg-gray-800 text-gray-500"
                }`}
              >
                {item.question ? item.question.priority : "not returned"}
              </span>
              <p className="text-xs font-medium text-gray-300">{item.label}</p>
            </div>
            {item.question ? (
              <p className="mt-1 text-xs text-gray-500">{item.question.question}</p>
            ) : (
              <p className="mt-1 text-xs text-gray-600">
                Not included in the current intake response.
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function findChecklistQuestion(
  questions: ProjectIntakeQuestion[],
  keywords: string[],
): ProjectIntakeQuestion | undefined {
  return questions.find((question) => {
    const haystack = `${question.question} ${question.why_it_matters}`.toLowerCase();
    return keywords.some((keyword) => haystack.includes(keyword));
  });
}

function IntakeList({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <p className="text-xs font-medium text-gray-300">{title}</p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs text-gray-600">{empty}</p>
      ) : (
        <ul className="mt-1 space-y-1 text-xs text-gray-400">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function IntakeQuestionCard({ question }: { question: ProjectIntakeQuestion }) {
  return (
    <article className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${priorityClass(question.priority)}`}>
          {question.priority}
        </span>
        <span className="rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">
          {formatLabel(question.category)}
        </span>
      </div>
      <p className="mt-2 text-sm font-medium text-gray-200">{question.question}</p>
      <p className="mt-1 text-xs text-gray-500">{question.why_it_matters}</p>
      {question.suggested_default && (
        <p className="mt-2 rounded bg-gray-900 px-2 py-1 text-xs text-gray-400">
          Suggested default: {question.suggested_default}
        </p>
      )}
      {question.options && question.options.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {question.options.map((option) => (
            <span key={option} className="rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">
              {option}
            </span>
          ))}
        </div>
      )}
    </article>
  );
}

function priorityClass(priority: ProjectIntakeQuestion["priority"]): string {
  if (priority === "required") return "bg-red-900/40 text-red-300";
  if (priority === "recommended") return "bg-yellow-900/40 text-yellow-300";
  return "bg-gray-800 text-gray-400";
}

function requirementPriorityClass(priority: SourceOfTruthPreviewResponse["source_of_truth"]["requirements"][number]["priority"]): string {
  if (priority === "must") return "bg-red-900/40 text-red-300";
  if (priority === "should") return "bg-yellow-900/40 text-yellow-300";
  if (priority === "could") return "bg-gray-800 text-gray-400";
  return "bg-gray-900 text-gray-500";
}

function driftRiskClass(risk: SourceOfTruthPreviewResponse["validation"]["drift_risk"]): string {
  if (risk === "critical") return "bg-red-900/60 text-red-200";
  if (risk === "high") return "bg-red-900/40 text-red-300";
  if (risk === "medium") return "bg-yellow-900/40 text-yellow-300";
  return "bg-emerald-900/40 text-emerald-300";
}

function coverageStatusClass(status: RequirementCoveragePreviewResponse["items"][number]["coverage_status"]): string {
  if (status === "covered") return "bg-emerald-900/40 text-emerald-300";
  if (status === "partially_covered") return "bg-yellow-900/40 text-yellow-300";
  if (status === "missing") return "bg-red-900/40 text-red-300";
  return "bg-gray-800 text-gray-400";
}

function sectionStatusClass(status: ProjectBriefSection["status"]): string {
  if (status === "confirmed") return "bg-emerald-900/40 text-emerald-300";
  if (status === "missing") return "bg-red-900/40 text-red-300";
  return "bg-yellow-900/40 text-yellow-300";
}

function planPhaseStatusClass(status: DevelopmentPlanPhase["status"]): string {
  if (status === "ready") return "bg-emerald-900/40 text-emerald-300";
  if (status === "blocked") return "bg-red-900/40 text-red-300";
  return "bg-yellow-900/40 text-yellow-300";
}

function formatLabel(value: string): string {
  return value.replace(/_/g, " ");
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded bg-gray-950 px-3 py-2">
      <span className="text-gray-600">{label}</span>
      <p className="mt-1 truncate font-mono text-gray-400">{value}</p>
    </div>
  );
}

// ── Unified Intake Preview Panel ──────────────────────────────────────────────

function UnifiedIntakePreviewPanel({
  result,
  answersMap = {},
  onAnswerChange,
  onRefine,
  clarifiedLoading = false,
}: {
  result: UnifiedAutonomousIntakePreviewResponse;
  answersMap?: Record<string, string>;
  onAnswerChange?: (id: string, value: string) => void;
  onRefine?: () => void;
  clarifiedLoading?: boolean;
}) {
  return (
    <div className="mt-4 space-y-4 border-t border-indigo-900/40 pt-4">
      <div className="rounded border border-indigo-900/60 bg-indigo-950/20 px-3 py-2">
        <p className="text-xs font-semibold text-indigo-300">
          Mode: {result.mode} — {result.classification_reason}
        </p>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Clarifying Questions ({result.clarifying_questions.length})
        </p>
        {result.clarifying_questions.map((q) => (
          <UnifiedClarifyingQuestionCard
            key={q.id}
            q={q}
            answer={answersMap[q.id] ?? ""}
            onAnswerChange={onAnswerChange}
          />
        ))}
        {onRefine && (
          <div className="mt-2 pt-2 border-t border-gray-800">
            <button
              onClick={onRefine}
              disabled={clarifiedLoading}
              className="rounded bg-violet-800 px-4 py-2 text-xs font-medium text-violet-200 transition-colors hover:bg-violet-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {clarifiedLoading ? "Refining preview…" : "Refine preview with answers"}
            </button>
            <p className="mt-1 text-[10px] text-gray-600">
              Read-only — submits answers to preview endpoint only. No project or run is created.
            </p>
          </div>
        )}
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Source of Truth Draft
        </p>
        <UnifiedSoTDraft sot={result.source_of_truth_preview} />
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Module Map Draft
        </p>
        <UnifiedModuleMapDraft mm={result.module_map_preview} />
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Multi-Agent Plan ({result.multi_agent_plan.length} steps)
        </p>
        {result.multi_agent_plan.map((step) => (
          <UnifiedPlanStepCard key={step.id} step={step} />
        ))}
      </div>

      <div className="rounded border border-emerald-900/40 bg-emerald-950/10 px-3 py-2">
        <p className="text-xs font-semibold text-emerald-300">Next Recommended Action</p>
        <p className="mt-1 text-xs text-gray-300">{result.next_recommended_action}</p>
      </div>

      <div className="grid gap-3 md:grid-cols-2">
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="text-xs font-semibold text-gray-500 mb-1">Safety Notes</p>
          <ul className="space-y-1 text-xs text-gray-400">
            {result.safety_notes.map((note) => <li key={note}>{note}</li>)}
          </ul>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="text-xs font-semibold text-gray-500 mb-1">Known Limitations</p>
          <ul className="space-y-1 text-xs text-gray-400">
            {result.limitations.map((lim) => <li key={lim}>{lim}</li>)}
          </ul>
        </div>
      </div>

      <p className="text-[10px] text-gray-600">
        This preview is read-only. It does not create projects, runs, or tool_calls. No provider or LLM calls are made.
      </p>
    </div>
  );
}

function UnifiedClarifyingQuestionCard({
  q,
  answer = "",
  onAnswerChange,
}: {
  q: ClarifyingQuestion;
  answer?: string;
  onAnswerChange?: (id: string, value: string) => void;
}) {
  return (
    <div className="rounded border border-gray-800 bg-gray-900 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${q.required ? "bg-red-900/40 text-red-300" : "bg-gray-800 text-gray-400"}`}>
          {q.required ? "required" : "optional"}
        </span>
        <span className="rounded bg-gray-950 px-2 py-0.5 text-[11px] text-gray-500">{q.category}</span>
        <span className="font-mono text-[10px] text-gray-600">{q.id}</span>
      </div>
      <p className="mt-1 text-xs font-medium text-gray-200">{q.question}</p>
      <p className="mt-1 text-[11px] text-gray-500">{q.reason}</p>
      {onAnswerChange && (
        <textarea
          value={answer}
          onChange={(e) => onAnswerChange(q.id, e.target.value)}
          placeholder="Your answer (helps refine the preview)…"
          rows={2}
          className="mt-2 w-full rounded border border-gray-700 bg-gray-800 px-2 py-1.5 text-xs resize-y focus:outline-none focus:border-violet-500"
        />
      )}
    </div>
  );
}

function UnifiedSoTDraft({ sot }: { sot: DraftSourceOfTruthPreview }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-bold text-gray-200">{sot.product_name}</p>
      <p className="text-xs text-gray-400">{sot.product_summary}</p>
      <div className="grid gap-2 md:grid-cols-2 text-xs">
        <UnifiedList title="Target Users" items={sot.target_users} />
        <UnifiedList title="Goals" items={sot.goals} />
        <UnifiedList title="Non-Goals" items={sot.non_goals} />
        <UnifiedList title="Constraints" items={sot.constraints} />
        <UnifiedList title="Risks" items={sot.risks} />
        <UnifiedList title="Open Questions" items={sot.open_questions} />
      </div>
      <span className="inline-block rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">
        confidence: {sot.confidence}
      </span>
    </div>
  );
}

function UnifiedModuleMapDraft({ mm }: { mm: DraftModuleMapPreview }) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-2">
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${mm.available ? "bg-emerald-900/40 text-emerald-300" : "bg-gray-800 text-gray-400"}`}>
          {mm.available ? "conceptual modules available" : "no modules"}
        </span>
        <span className="rounded bg-gray-900 px-2 py-0.5 text-[11px] text-gray-500">confidence: {mm.confidence}</span>
      </div>
      {mm.modules.length > 0 && (
        <div className="grid gap-2 md:grid-cols-2">
          {mm.modules.map((mod, i) => (
            <div key={i} className="rounded border border-gray-800 bg-gray-900 px-2 py-1.5">
              <p className="text-xs font-medium text-gray-200">{mod.name || "Module"}</p>
              <p className="text-[11px] text-gray-500">{mod.description || ""}</p>
              {mod.type && <span className="rounded bg-gray-950 px-1.5 py-0.5 text-[10px] text-gray-600">{mod.type}</span>}
            </div>
          ))}
        </div>
      )}
      {mm.inferred_stack.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {mm.inferred_stack.map((s) => (
            <span key={s} className="rounded bg-indigo-900/30 px-2 py-0.5 text-[11px] text-indigo-300">{s}</span>
          ))}
        </div>
      )}
      {mm.unknowns.length > 0 && (
        <ul className="space-y-1 text-[11px] text-yellow-400">
          {mm.unknowns.map((u) => <li key={u}>{u}</li>)}
        </ul>
      )}
    </div>
  );
}

function UnifiedPlanStepCard({ step }: { step: DraftAgentPlanStep }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-900 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-gray-600">{step.id}</span>
        <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${step.risk_level === "high" ? "bg-red-900/40 text-red-300" : step.risk_level === "low" ? "bg-emerald-900/40 text-emerald-300" : "bg-yellow-900/40 text-yellow-300"}`}>
          {step.risk_level}
        </span>
        <span className="rounded bg-gray-950 px-2 py-0.5 text-[11px] text-gray-500">{step.agent_role}</span>
      </div>
      <p className="mt-1 text-xs font-medium text-gray-200">{step.title}</p>
      <p className="mt-1 text-[11px] text-gray-500">{step.reason}</p>
      {step.depends_on.length > 0 && (
        <p className="mt-1 text-[10px] text-gray-600">Depends on: {step.depends_on.join(", ")}</p>
      )}
      {step.expected_outputs.length > 0 && (
        <p className="mt-1 text-[10px] text-gray-600">Outputs: {step.expected_outputs.join(", ")}</p>
      )}
    </div>
  );
}

function UnifiedList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950 px-2 py-1.5">
      <p className="text-[11px] font-semibold text-gray-500">{title}</p>
      {items.length === 0 ? (
        <p className="text-[11px] text-gray-600">None.</p>
      ) : (
        <ul className="mt-1 space-y-0.5">
          {items.map((item) => <li key={item} className="text-[11px] text-gray-400">{item}</li>)}
        </ul>
      )}
    </div>
  );
}

// ── Clarified Intake Preview Panel ────────────────────────────────────────────

interface ClarifiedIntakePreviewPanelProps {
  result: ClarifiedIntakePreviewResponse;
  onBuildSoTDraft?: () => void;
  onBuildModuleMapDraft?: () => void;
  onPersistModuleMapDraft?: () => void;
  onBuildMultiAgentPlan?: () => void;
  onPreviewDevelopmentRun?: () => void;
  sotDraftLoading?: boolean;
  sotDraftError?: string;
  sotDraftResult?: SourceOfTruthDraftFromIntakeResponse | null;
  moduleMapDraftLoading?: boolean;
  moduleMapDraftError?: string;
  moduleMapDraftResult?: ModuleMapDraftFromIntakeResponse | null;
  moduleMapPersistLoading?: boolean;
  moduleMapPersistError?: string;
  multiAgentPlanLoading?: boolean;
  multiAgentPlanError?: string;
  multiAgentPlanResult?: MultiAgentPlanFromIntakeResponse | null;
  developmentRunPreviewLoading?: boolean;
  developmentRunPreviewError?: string;
  developmentRunPreviewResult?: IntakeDevelopmentRunPreviewResponse | null;
  onEvaluateContractPreview?: () => void;
  contractPreviewLoading?: boolean;
  contractPreviewError?: string;
  contractPreviewResult?: IntakeConfirmedRunCreationContractPreviewResponse | null;
  // Bridge
  bridgeConfirmCreate?: boolean;
  setBridgeConfirmCreate?: (v: boolean) => void;
  bridgeConfirmSoT?: boolean;
  setBridgeConfirmSoT?: (v: boolean) => void;
  bridgeConfirmModuleMap?: boolean;
  setBridgeConfirmModuleMap?: (v: boolean) => void;
  bridgeConfirmProvider?: boolean;
  setBridgeConfirmProvider?: (v: boolean) => void;
  bridgeConfirmLaterActions?: boolean;
  setBridgeConfirmLaterActions?: (v: boolean) => void;
  onCreateConfirmedDevelopmentRun?: () => void;
  bridgeCreateLoading?: boolean;
  bridgeCreateError?: string;
  bridgeCreateResult?: ConfirmedDevelopmentRunCreateResponse | null;
  selectedProjectId?: string;
}

function ClarifiedIntakePreviewPanel({
  result,
  onBuildSoTDraft,
  onBuildModuleMapDraft,
  onPersistModuleMapDraft,
  onBuildMultiAgentPlan,
  onPreviewDevelopmentRun,
  sotDraftLoading = false,
  sotDraftError = "",
  sotDraftResult = null,
  moduleMapDraftLoading = false,
  moduleMapDraftError = "",
  moduleMapDraftResult = null,
  moduleMapPersistLoading = false,
  moduleMapPersistError = "",
  multiAgentPlanLoading = false,
  multiAgentPlanError = "",
  multiAgentPlanResult = null,
  developmentRunPreviewLoading = false,
  developmentRunPreviewError = "",
  developmentRunPreviewResult = null,
  onEvaluateContractPreview,
  contractPreviewLoading = false,
  contractPreviewError = "",
  contractPreviewResult = null,
  bridgeConfirmCreate = false,
  setBridgeConfirmCreate,
  bridgeConfirmSoT = false,
  setBridgeConfirmSoT,
  bridgeConfirmModuleMap = false,
  setBridgeConfirmModuleMap,
  bridgeConfirmProvider = false,
  setBridgeConfirmProvider,
  bridgeConfirmLaterActions = false,
  setBridgeConfirmLaterActions,
  onCreateConfirmedDevelopmentRun,
  bridgeCreateLoading = false,
  bridgeCreateError = "",
  bridgeCreateResult = null,
  selectedProjectId = "",
}: ClarifiedIntakePreviewPanelProps) {
  return (
    <div className="mt-4 space-y-4 border-t border-violet-900/40 pt-4">
      <div className="rounded border border-violet-900/60 bg-violet-950/20 px-3 py-2">
        <p className="text-xs font-semibold text-violet-300">
          Refined Preview — {result.mode} &nbsp;|&nbsp; confidence: {result.confidence_before} → {result.confidence_after}
        </p>
      </div>

      {result.missing_required_questions.length > 0 && (
        <div className="rounded border border-yellow-900/40 bg-yellow-950/10 px-3 py-2 space-y-1">
          <p className="text-xs font-semibold text-yellow-300">
            Missing Required Answers ({result.missing_required_questions.length})
          </p>
          {result.missing_required_questions.map((gap) => (
            <ClarifiedAnswerGapRow key={gap.question_id} gap={gap} />
          ))}
        </div>
      )}

      {result.applied_answer_summary.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="text-xs font-semibold text-gray-500 mb-1">
            Applied Answer Summary ({result.applied_answer_summary.length})
          </p>
          <ul className="space-y-0.5">
            {result.applied_answer_summary.map((s) => (
              <li key={s} className="text-[11px] text-gray-300">• {s}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Refined Source of Truth Draft
        </p>
        <UnifiedSoTDraft sot={result.source_of_truth_preview} />
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500 mb-2">
          Refined Module Map Draft
        </p>
        <UnifiedModuleMapDraft mm={result.module_map_preview} />
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-3 space-y-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
          Multi-Agent Plan ({result.multi_agent_plan.length} steps)
        </p>
        {result.multi_agent_plan.map((step) => (
          <UnifiedPlanStepCard key={step.id} step={step} />
        ))}
      </div>

      <div className="rounded border border-emerald-900/40 bg-emerald-950/10 px-3 py-2">
        <p className="text-xs font-semibold text-emerald-300">Next Recommended Action</p>
        <p className="mt-1 text-xs text-gray-300">{result.next_recommended_action}</p>
      </div>

      {onBuildSoTDraft && (
        <div className="pt-1">
          <button
            onClick={onBuildSoTDraft}
            disabled={sotDraftLoading}
            className="rounded bg-emerald-900 px-4 py-2 text-xs font-medium text-emerald-200 transition-colors hover:bg-emerald-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
          >
            {sotDraftLoading ? "Building SoT draft…" : "Build Source of Truth draft"}
          </button>
          <span className="ml-3 text-[10px] text-gray-600">
            Preview only — read-only, no persistence
          </span>
        </div>
      )}

      {sotDraftError && (
        <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
          {sotDraftError}
        </p>
      )}

      {sotDraftResult && <SoTDraftFromIntakePanel result={sotDraftResult} />}

      {onBuildModuleMapDraft && (
        <div className="pt-1">
          <button
            onClick={onBuildModuleMapDraft}
            disabled={moduleMapDraftLoading}
            className="rounded bg-sky-900 px-4 py-2 text-xs font-medium text-sky-200 transition-colors hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
          >
            {moduleMapDraftLoading ? "Building Module Map draft…" : "Build Module Map draft"}
          </button>
          <span className="ml-3 text-[10px] text-gray-600">
            Preview only — no project, run, scan, or provider call
          </span>
        </div>
      )}

      {moduleMapDraftError && (
        <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
          {moduleMapDraftError}
        </p>
      )}

      {moduleMapDraftResult && (
        <ModuleMapDraftFromIntakePanel
          result={moduleMapDraftResult}
          selectedProjectId={selectedProjectId}
          onPersist={onPersistModuleMapDraft}
          persistLoading={moduleMapPersistLoading}
          persistError={moduleMapPersistError}
        />
      )}

      {onBuildMultiAgentPlan && (
        <div className="pt-1">
          <button
            onClick={onBuildMultiAgentPlan}
            disabled={multiAgentPlanLoading}
            className="rounded bg-violet-900 px-4 py-2 text-xs font-medium text-violet-200 transition-colors hover:bg-violet-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
          >
            {multiAgentPlanLoading ? "Building Multi-Agent Plan…" : "Build Multi-Agent Plan"}
          </button>
          <span className="ml-3 text-[10px] text-gray-600">
            Preview only — no project, run, agent execution, or provider call
          </span>
        </div>
      )}

      {multiAgentPlanError && (
        <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
          {multiAgentPlanError}
        </p>
      )}

      {multiAgentPlanResult && <MultiAgentPlanFromIntakePanel result={multiAgentPlanResult} />}

      {onPreviewDevelopmentRun && (
        <div className="pt-1">
          <button
            onClick={onPreviewDevelopmentRun}
            disabled={developmentRunPreviewLoading}
            className="rounded bg-blue-900 px-4 py-2 text-xs font-medium text-blue-200 transition-colors hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
          >
            {developmentRunPreviewLoading ? "Previewing Development Run…" : "Preview Development Run"}
          </button>
          <span className="ml-3 text-[10px] text-gray-600">
            Preview only — no project, run, agent execution, provider call, or file scan
          </span>
        </div>
      )}

      {developmentRunPreviewError && (
        <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
          {developmentRunPreviewError}
        </p>
      )}

      {developmentRunPreviewResult && (
        <IntakeDevelopmentRunPreviewPanel result={developmentRunPreviewResult} />
      )}

      {developmentRunPreviewResult && onEvaluateContractPreview && (
        <div className="pt-1 space-y-2">
          <div className="flex items-center gap-3">
            <button
              onClick={onEvaluateContractPreview}
              disabled={contractPreviewLoading}
              className="rounded bg-orange-900 px-4 py-2 text-xs font-medium text-orange-200 transition-colors hover:bg-orange-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {contractPreviewLoading ? "Evaluating contract…" : "Evaluate confirmed run creation contract"}
            </button>
            <span className="text-[10px] text-gray-600">
              Contract preview only — no run, step, project, or provider call
            </span>
          </div>
          {contractPreviewError && (
            <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
              {contractPreviewError}
            </p>
          )}
          {contractPreviewResult && (
            <ConfirmedRunCreationContractPreviewPanel result={contractPreviewResult} />
          )}
        </div>
      )}

      {/* ── Confirmed Development Run Bridge ────────────────────── */}
      {contractPreviewResult && onCreateConfirmedDevelopmentRun && (
        <ConfirmedDevelopmentRunBridgePanel
          contractPreviewResult={contractPreviewResult}
          selectedProjectId={selectedProjectId}
          bridgeConfirmCreate={bridgeConfirmCreate}
          setBridgeConfirmCreate={setBridgeConfirmCreate}
          bridgeConfirmSoT={bridgeConfirmSoT}
          setBridgeConfirmSoT={setBridgeConfirmSoT}
          bridgeConfirmModuleMap={bridgeConfirmModuleMap}
          setBridgeConfirmModuleMap={setBridgeConfirmModuleMap}
          bridgeConfirmProvider={bridgeConfirmProvider}
          setBridgeConfirmProvider={setBridgeConfirmProvider}
          bridgeConfirmLaterActions={bridgeConfirmLaterActions}
          setBridgeConfirmLaterActions={setBridgeConfirmLaterActions}
          onCreateConfirmedDevelopmentRun={onCreateConfirmedDevelopmentRun}
          bridgeCreateLoading={bridgeCreateLoading}
          bridgeCreateError={bridgeCreateError}
          bridgeCreateResult={bridgeCreateResult}
        />
      )}

      <p className="text-[10px] text-gray-600">
        Refined preview is read-only. No project, run, or tool_call is created. No provider or LLM calls are made.
      </p>
    </div>
  );
}

// ── Module Map Draft from Intake Panel ─────────────────────────────────────

function ModuleMapDraftFromIntakePanel({
  result,
  selectedProjectId,
  onPersist,
  persistLoading,
  persistError,
}: {
  result: ModuleMapDraftFromIntakeResponse;
  selectedProjectId: string;
  onPersist?: () => void;
  persistLoading?: boolean;
  persistError?: string;
}) {
  const v = result.validation;
  const modules = result.draft.modules || [];
  return (
    <div className="mt-2 space-y-3 rounded border border-sky-900/40 bg-sky-950/10 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-sky-300">Module Map Draft</span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${v.valid ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
          {v.valid ? "valid" : "invalid"}
        </span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400">
          confidence: {v.confidence}
        </span>
        <span className="text-[10px] text-gray-500">
          {v.module_count} modules &nbsp;|&nbsp; {v.requirement_coverage_count} linked requirements
        </span>
        {result.persisted && (
          <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
            persisted v{result.version}
          </span>
        )}
      </div>

      {v.errors.length > 0 && (
        <div className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-red-300">Errors ({v.errors.length})</p>
          <ul className="space-y-0.5">
            {v.errors.map((e, i) => <li key={i} className="text-[11px] text-red-400">• {e}</li>)}
          </ul>
        </div>
      )}

      {v.warnings.length > 0 && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-yellow-300">Warnings ({v.warnings.length})</p>
          <ul className="space-y-0.5">
            {v.warnings.map((w, i) => <li key={i} className="text-[11px] text-yellow-400">• {w}</li>)}
          </ul>
        </div>
      )}

      {v.missing_fields.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-gray-500">Missing Fields</p>
          <div className="flex flex-wrap gap-1">
            {v.missing_fields.map((field) => (
              <span key={field} className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{field}</span>
            ))}
          </div>
        </div>
      )}

      {result.inferred_stack.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-gray-500">Inferred Stack</p>
          <div className="flex flex-wrap gap-1">
            {result.inferred_stack.map((item) => (
              <span key={item} className="rounded bg-sky-900/30 px-2 py-0.5 text-[10px] text-sky-300">{item}</span>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Draft Modules ({modules.length})
        </p>
        {modules.map((module) => (
          <div key={module.id} className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-gray-200">{module.name}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{module.module_type}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{module.confidence}</span>
            </div>
            <p className="mt-1 text-[11px] text-gray-400">{module.description}</p>
            {module.related_requirements.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">
                Requirements: {module.related_requirements.join(", ")}
              </p>
            )}
            {(module.paths.length > 0 || module.key_files.length > 0) && (
              <p className="mt-1 text-[10px] text-gray-500">
                Paths/files: {[...module.paths, ...module.key_files].join(", ")}
              </p>
            )}
            {module.risks.length > 0 && (
              <p className="mt-1 text-[10px] text-yellow-300">
                Risks: {module.risks.join("; ")}
              </p>
            )}
            {module.test_hints.length > 0 && (
              <p className="mt-1 text-[10px] text-emerald-300">
                Tests: {module.test_hints.join("; ")}
              </p>
            )}
          </div>
        ))}
      </div>

      <div className="rounded border border-sky-900/30 bg-sky-950/5 px-3 py-2">
        <p className="text-[10px] font-semibold text-sky-300">Next Action</p>
        <p className="mt-0.5 text-[11px] text-gray-400">{result.next_recommended_action}</p>
      </div>

      {onPersist && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          {selectedProjectId ? (
            <button
              onClick={onPersist}
              disabled={persistLoading || !v.valid}
              className="rounded bg-sky-900 px-3 py-1.5 text-xs font-medium text-sky-200 transition-colors hover:bg-sky-800 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
            >
              {persistLoading ? "Saving Module Map…" : "Save Module Map draft"}
            </button>
          ) : (
            <p className="text-[11px] text-yellow-300">
              Create/select a project before saving Module Map.
            </p>
          )}
          {persistError && (
            <p className="mt-2 rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
              {persistError}
            </p>
          )}
        </div>
      )}

      <p className="text-[10px] text-gray-600">
        Module Map draft is deterministic and read-only until explicit save. It does not create projects, runs, tool_calls, scans, file reads, or provider calls.
      </p>
    </div>
  );
}

// ── Multi-Agent Plan from Intake Panel ─────────────────────────────────────

function MultiAgentPlanFromIntakePanel({ result }: { result: MultiAgentPlanFromIntakeResponse }) {
  const v = result.validation;
  return (
    <div className="mt-2 space-y-3 rounded border border-violet-900/40 bg-violet-950/10 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-violet-300">Multi-Agent Plan</span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${v.valid ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
          {v.valid ? "valid" : "invalid"}
        </span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400">
          {v.readiness}
        </span>
        <span className="text-[10px] text-gray-500">
          {result.tasks.length} tasks &nbsp;|&nbsp; {result.milestones.length} milestones &nbsp;|&nbsp; {result.risks.length} risks
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-bold text-gray-200">{result.plan_title}</p>
        <p className="mt-1 text-[11px] text-gray-400">{result.plan_summary}</p>
        <p className="mt-2 text-[10px] font-semibold text-violet-300">Recommended First Action</p>
        <p className="mt-0.5 text-[11px] text-gray-400">{result.recommended_first_action}</p>
        {result.recommended_first_task_id && (
          <p className="mt-1 text-[10px] text-gray-500">First task: {result.recommended_first_task_id}</p>
        )}
      </div>

      {(v.errors.length > 0 || v.warnings.length > 0 || v.missing_inputs.length > 0) && (
        <div className="grid gap-2 md:grid-cols-3">
          {v.errors.length > 0 && (
            <div className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-red-300">Errors</p>
              {v.errors.map((item, i) => <p key={i} className="text-[11px] text-red-400">• {item}</p>)}
            </div>
          )}
          {v.warnings.length > 0 && (
            <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-yellow-300">Warnings</p>
              {v.warnings.map((item, i) => <p key={i} className="text-[11px] text-yellow-400">• {item}</p>)}
            </div>
          )}
          {v.missing_inputs.length > 0 && (
            <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-gray-500">Missing Inputs</p>
              <div className="flex flex-wrap gap-1">
                {v.missing_inputs.map((item) => (
                  <span key={item} className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{item}</span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {result.milestones.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Milestones</p>
          <div className="space-y-2">
            {result.milestones.map((milestone) => (
              <div key={milestone.id}>
                <p className="text-[11px] font-semibold text-gray-300">{milestone.title}</p>
                <p className="text-[10px] text-gray-500">{milestone.goal}</p>
                <p className="mt-0.5 text-[10px] text-gray-600">Tasks: {milestone.task_ids.join(", ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Tasks by Agent ({result.tasks.length})
        </p>
        {result.tasks.map((task) => (
          <div key={task.id} className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-semibold text-gray-200">{task.title}</span>
              <span className="rounded bg-violet-900/30 px-2 py-0.5 text-[10px] text-violet-300">{task.agent_role}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{task.risk_level}</span>
              {task.manual_approval_required && (
                <span className="rounded bg-yellow-900/40 px-2 py-0.5 text-[10px] text-yellow-300">manual approval</span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-gray-400">{task.description}</p>
            {task.target_modules.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Modules: {task.target_modules.join(", ")}</p>
            )}
            {task.requirement_ids.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Requirements: {task.requirement_ids.join(", ")}</p>
            )}
            {task.expected_outputs.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Outputs: {task.expected_outputs.join("; ")}</p>
            )}
            {task.validation_steps.length > 0 && (
              <p className="mt-1 text-[10px] text-emerald-300">Validation: {task.validation_steps.join("; ")}</p>
            )}
          </div>
        ))}
      </div>

      {result.risks.length > 0 && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-yellow-300">Risks</p>
          {result.risks.map((risk) => (
            <div key={risk.id} className="mb-2 last:mb-0">
              <p className="text-[11px] text-yellow-200">{risk.severity}: {risk.description}</p>
              {risk.affected_modules.length > 0 && (
                <p className="text-[10px] text-yellow-400">Modules: {risk.affected_modules.join(", ")}</p>
              )}
              <p className="text-[10px] text-gray-400">Mitigation: {risk.mitigation}</p>
            </div>
          ))}
        </div>
      )}

      <p className="text-[10px] text-gray-600">
        Multi-Agent Plan is preview-only. It does not create projects, runs, run steps, tool_calls, provider calls, scans, or file reads.
      </p>
    </div>
  );
}

function IntakeDevelopmentRunPreviewPanel({ result }: { result: IntakeDevelopmentRunPreviewResponse }) {
  const v = result.validation;
  return (
    <div className="mt-2 space-y-3 rounded border border-blue-900/40 bg-blue-950/10 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-blue-300">Development Run Preview</span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${v.ready_to_create_run ? "bg-emerald-900/50 text-emerald-300" : "bg-yellow-900/40 text-yellow-300"}`}>
          {v.ready_to_create_run ? "ready to set up" : "needs review"}
        </span>
        <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] font-medium text-gray-400">
          {v.readiness}
        </span>
        <span className="text-[10px] text-gray-500">
          {result.steps.length} steps &nbsp;|&nbsp; {result.agent_roles.length} agents &nbsp;|&nbsp; mode: {result.recommended_run_mode}
        </span>
      </div>

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
        <p className="text-xs font-bold text-gray-200">{result.run_title}</p>
        <p className="mt-1 text-[11px] text-gray-400">{result.run_goal}</p>
        <p className="mt-2 text-[10px] font-semibold text-blue-300">Recommended First Safe Action</p>
        <p className="mt-0.5 text-[11px] text-gray-400">{result.recommended_first_safe_action}</p>
      </div>

      {(v.errors.length > 0 || v.warnings.length > 0 || v.missing_inputs.length > 0 || v.blocked_reasons.length > 0) && (
        <div className="grid gap-2 md:grid-cols-4">
          {v.errors.length > 0 && (
            <div className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-red-300">Errors</p>
              {v.errors.map((item, i) => <p key={i} className="text-[11px] text-red-400">• {item}</p>)}
            </div>
          )}
          {v.warnings.length > 0 && (
            <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-yellow-300">Warnings</p>
              {v.warnings.map((item, i) => <p key={i} className="text-[11px] text-yellow-400">• {item}</p>)}
            </div>
          )}
          {v.missing_inputs.length > 0 && (
            <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-gray-500">Missing Inputs</p>
              <div className="flex flex-wrap gap-1">
                {v.missing_inputs.map((item) => (
                  <span key={item} className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{item}</span>
                ))}
              </div>
            </div>
          )}
          {v.blocked_reasons.length > 0 && (
            <div className="rounded border border-red-800/50 bg-red-950/10 px-3 py-2">
              <p className="mb-1 text-[10px] font-semibold text-red-300">Blocked Reasons</p>
              {v.blocked_reasons.map((item, i) => <p key={i} className="text-[11px] text-red-400">• {item}</p>)}
            </div>
          )}
        </div>
      )}

      <div className="grid gap-2 md:grid-cols-3">
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Agent Roles</p>
          <p className="text-[11px] text-gray-400">{result.agent_roles.length ? result.agent_roles.join(", ") : "No agent roles linked."}</p>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Requirements</p>
          <p className="text-[11px] text-gray-400">{result.requirement_ids.length ? result.requirement_ids.join(", ") : "No requirement links yet."}</p>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Modules</p>
          <p className="text-[11px] text-gray-400">{result.module_ids.length ? result.module_ids.join(", ") : "No module links yet."}</p>
        </div>
      </div>

      {result.safety_summary.length > 0 && (
        <div className="rounded border border-blue-900/40 bg-blue-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-blue-300">Safety Summary</p>
          {result.safety_summary.map((item, i) => <p key={i} className="text-[11px] text-gray-400">• {item}</p>)}
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-gray-500">
          Proposed Steps ({result.steps.length})
        </p>
        {result.steps.map((step) => (
          <div key={step.id} className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] text-gray-500">#{step.estimated_order}</span>
              <span className="text-xs font-semibold text-gray-200">{step.title}</span>
              <span className="rounded bg-blue-900/30 px-2 py-0.5 text-[10px] text-blue-300">{step.agent_role}</span>
              <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400">{step.risk_level}</span>
              {step.manual_approval_required && (
                <span className="rounded bg-yellow-900/40 px-2 py-0.5 text-[10px] text-yellow-300">manual approval</span>
              )}
              {!step.provider_allowed && (
                <span className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-500">provider disabled</span>
              )}
            </div>
            <p className="mt-1 text-[11px] text-gray-400">{step.description}</p>
            {step.depends_on.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Depends on: {step.depends_on.join(", ")}</p>
            )}
            {step.requirement_ids.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Requirements: {step.requirement_ids.join(", ")}</p>
            )}
            {step.module_ids.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Modules: {step.module_ids.join(", ")}</p>
            )}
            {step.expected_outputs.length > 0 && (
              <p className="mt-1 text-[10px] text-gray-500">Outputs: {step.expected_outputs.join("; ")}</p>
            )}
            {step.validation_steps.length > 0 && (
              <p className="mt-1 text-[10px] text-emerald-300">Validation: {step.validation_steps.join("; ")}</p>
            )}
            {step.safety_gates.length > 0 && (
              <p className="mt-1 text-[10px] text-blue-300">Safety gates: {step.safety_gates.join("; ")}</p>
            )}
          </div>
        ))}
      </div>

      {result.limitations.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">Limitations</p>
          {result.limitations.map((item, i) => <p key={i} className="text-[11px] text-gray-500">• {item}</p>)}
        </div>
      )}

      <p className="text-[10px] text-gray-600">
        Development Run Preview is read-only. It does not create projects, runs, run steps, tool_calls, provider calls, scans, or file reads.
      </p>
    </div>
  );
}

// ── Confirmed Run Creation Contract Preview Panel ──────────────────────────

function ConfirmedRunCreationContractPreviewPanel({
  result,
}: {
  result: IntakeConfirmedRunCreationContractPreviewResponse;
}) {
  const decisionColor =
    result.decision === "allowed"
      ? "border-emerald-800/50 bg-emerald-950/10"
      : result.decision === "warning"
      ? "border-yellow-800/50 bg-yellow-950/10"
      : "border-red-800/50 bg-red-950/10";
  const decisionTextColor =
    result.decision === "allowed"
      ? "text-emerald-300"
      : result.decision === "warning"
      ? "text-yellow-300"
      : "text-red-300";
  const riskColor =
    result.risk === "low"
      ? "bg-emerald-900/50 text-emerald-300"
      : result.risk === "medium"
      ? "bg-yellow-900/40 text-yellow-300"
      : result.risk === "high"
      ? "bg-orange-900/40 text-orange-300"
      : "bg-red-900/50 text-red-300";

  return (
    <div className={`mt-2 space-y-3 rounded border p-3 ${decisionColor}`}>
      {/* Header */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-gray-200">
          Confirmed Run Creation Contract
        </span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase ${decisionTextColor} bg-gray-900`}>
          {result.decision}
        </span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${riskColor}`}>
          risk: {result.risk}
        </span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${result.can_create_pending_run ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
          {result.can_create_pending_run ? "can create pending run" : "cannot create run yet"}
        </span>
        <span className="text-[10px] text-gray-500 italic">Contract preview only</span>
      </div>

      {/* Blockers */}
      {result.blockers.length > 0 && (
        <div className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-red-300">
            Blockers ({result.blockers.length}) — must resolve before run creation
          </p>
          {result.blockers.map((b, i) => (
            <p key={i} className="text-[11px] text-red-400">• {b}</p>
          ))}
        </div>
      )}

      {/* Warnings */}
      {result.warnings.length > 0 && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold text-yellow-300">
            Warnings ({result.warnings.length})
          </p>
          {result.warnings.map((w, i) => (
            <p key={i} className="text-[11px] text-yellow-400">• {w}</p>
          ))}
        </div>
      )}

      {/* Entity boundaries */}
      <div className="grid gap-2 md:grid-cols-2">
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-emerald-400">
            Allowed to create
          </p>
          <p className="text-[11px] text-gray-300">
            {result.allowed_created_entities.join(", ") || "none"}
          </p>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-red-400">
            Forbidden to create
          </p>
          <p className="text-[11px] text-gray-300">
            {result.forbidden_created_entities.join(", ") || "none"}
          </p>
        </div>
      </div>

      {/* Required statuses */}
      {Object.keys(result.required_statuses).length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
            Required Statuses
          </p>
          <div className="flex flex-wrap gap-2">
            {Object.entries(result.required_statuses).map(([k, v]) => (
              <span key={k} className="rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-300">
                {k}: <span className="text-blue-300">{v}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Safety gates */}
      {result.safety_gates.length > 0 && (
        <div className="rounded border border-blue-900/40 bg-blue-950/10 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-300">
            Safety Gates ({result.safety_gates.length})
          </p>
          {result.safety_gates.map((g) => (
            <div key={g.id} className="mt-1">
              <span className="text-[10px] font-medium text-blue-200">{g.title}</span>
              <span className="ml-2 text-[10px] text-gray-500">{g.description}</span>
            </div>
          ))}
        </div>
      )}

      {/* Operator confirmations */}
      {result.required_operator_confirmations.length > 0 && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
            Required Operator Confirmations
          </p>
          {result.required_operator_confirmations.map((c, i) => (
            <p key={i} className="text-[11px] text-gray-400">☐ {c}</p>
          ))}
        </div>
      )}

      {/* Next recommended action */}
      {result.next_recommended_action && (
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
          <p className="text-[10px] font-semibold text-gray-500">Next Recommended Action</p>
          <p className="mt-0.5 text-[11px] text-gray-300">{result.next_recommended_action}</p>
        </div>
      )}

      <p className="text-[10px] text-gray-600">{result.contract_note}</p>
    </div>
  );
}

// ── Confirmed Development Run Bridge Panel ─────────────────────────────────

function ConfirmedDevelopmentRunBridgePanel({
  contractPreviewResult,
  selectedProjectId,
  bridgeConfirmCreate,
  setBridgeConfirmCreate,
  bridgeConfirmSoT,
  setBridgeConfirmSoT,
  bridgeConfirmModuleMap,
  setBridgeConfirmModuleMap,
  bridgeConfirmProvider,
  setBridgeConfirmProvider,
  bridgeConfirmLaterActions,
  setBridgeConfirmLaterActions,
  onCreateConfirmedDevelopmentRun,
  bridgeCreateLoading,
  bridgeCreateError,
  bridgeCreateResult,
}: {
  contractPreviewResult: IntakeConfirmedRunCreationContractPreviewResponse;
  selectedProjectId: string;
  bridgeConfirmCreate: boolean;
  setBridgeConfirmCreate?: (v: boolean) => void;
  bridgeConfirmSoT: boolean;
  setBridgeConfirmSoT?: (v: boolean) => void;
  bridgeConfirmModuleMap: boolean;
  setBridgeConfirmModuleMap?: (v: boolean) => void;
  bridgeConfirmProvider: boolean;
  setBridgeConfirmProvider?: (v: boolean) => void;
  bridgeConfirmLaterActions: boolean;
  setBridgeConfirmLaterActions?: (v: boolean) => void;
  onCreateConfirmedDevelopmentRun: () => void;
  bridgeCreateLoading: boolean;
  bridgeCreateError: string;
  bridgeCreateResult: ConfirmedDevelopmentRunCreateResponse | null;
}) {
  const allChecked =
    bridgeConfirmCreate &&
    bridgeConfirmSoT &&
    bridgeConfirmModuleMap &&
    bridgeConfirmProvider &&
    bridgeConfirmLaterActions;

  const canCreate =
    allChecked &&
    !!selectedProjectId &&
    contractPreviewResult.can_create_pending_run;

  if (bridgeCreateResult?.created) {
    return (
      <div className="mt-3 rounded border border-emerald-800/60 bg-emerald-950/20 p-4 space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-semibold text-emerald-300">✓ Pending Run Created</span>
          <span className="rounded bg-emerald-900/50 px-2 py-0.5 text-[10px] text-emerald-200">
            {bridgeCreateResult.status}
          </span>
          <span className="text-[10px] text-gray-500">
            {bridgeCreateResult.steps.length} pending step(s)
          </span>
        </div>
        <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2 space-y-1">
          <p className="text-[10px] font-semibold text-gray-500">Run ID</p>
          <p className="font-mono text-xs text-gray-200">{bridgeCreateResult.run_id}</p>
        </div>
        {bridgeCreateResult.open_run_url_hint && (
          <a
            href={bridgeCreateResult.open_run_url_hint}
            className="inline-block rounded bg-blue-900 px-3 py-1.5 text-xs font-medium text-blue-200 transition-colors hover:bg-blue-800"
          >
            Open Run Detail →
          </a>
        )}
        <p className="text-[11px] text-gray-400">{bridgeCreateResult.next_recommended_action}</p>
        {bridgeCreateResult.safety_notes.length > 0 && (
          <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2">
            <p className="mb-1 text-[10px] font-semibold text-gray-500">Safety Notes</p>
            {bridgeCreateResult.safety_notes.map((n, i) => (
              <p key={i} className="text-[10px] text-gray-500">• {n}</p>
            ))}
          </div>
        )}
        <p className="text-[10px] text-gray-600">
          No agents, providers, tool_calls, patches, or commands were started.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded border border-gray-700 bg-gray-900/60 p-4 space-y-3">
      <p className="text-xs font-semibold text-gray-200">Confirm and Create Pending Run</p>
      <p className="text-[11px] text-gray-500">
        Repo analysis will be attached to the pending run as bounded context when available. It will not execute commands or modify files.
      </p>

      {!selectedProjectId && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="text-xs text-yellow-300">
            Select or create a project before creating a confirmed development run.
          </p>
        </div>
      )}

      {/* Confirmation checklist */}
      <div className="space-y-2">
        {[
          {
            checked: bridgeConfirmCreate,
            set: setBridgeConfirmCreate,
            label: "I confirm creating a pending run only. No execution will start automatically.",
          },
          {
            checked: bridgeConfirmSoT,
            set: setBridgeConfirmSoT,
            label: "I confirm Source of Truth has been reviewed and is ready.",
          },
          {
            checked: bridgeConfirmModuleMap,
            set: setBridgeConfirmModuleMap,
            label: "I confirm Module Map has been reviewed and is ready.",
          },
          {
            checked: bridgeConfirmProvider,
            set: setBridgeConfirmProvider,
            label: "I confirm all provider calls remain disabled (provider_allowed=false).",
          },
          {
            checked: bridgeConfirmLaterActions,
            set: setBridgeConfirmLaterActions,
            label: "I confirm apply/test/run commands require a later explicit action.",
          },
        ].map(({ checked, set, label }, i) => (
          <label key={i} className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              className="mt-0.5 accent-emerald-500"
              checked={checked}
              onChange={(e) => set?.(e.target.checked)}
            />
            <span className="text-[11px] text-gray-300">{label}</span>
          </label>
        ))}
      </div>

      <button
        onClick={onCreateConfirmedDevelopmentRun}
        disabled={!canCreate || bridgeCreateLoading}
        className="rounded bg-emerald-800 px-5 py-2 text-xs font-semibold text-emerald-100 transition-colors hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-gray-800 disabled:text-gray-600"
      >
        {bridgeCreateLoading ? "Creating pending run…" : "Confirm and Create Pending Run"}
      </button>

      {!selectedProjectId && (
        <p className="text-[10px] text-yellow-400">⚠ No project selected.</p>
      )}
      {!contractPreviewResult.can_create_pending_run && (
        <p className="text-[10px] text-red-400">
          ⚠ Contract is blocked. Resolve all blockers before creating a run.
        </p>
      )}

      {bridgeCreateError && (
        <p className="rounded border border-red-800 bg-red-950/20 px-3 py-2 text-xs text-red-300">
          {bridgeCreateError}
        </p>
      )}

      <p className="text-[10px] text-gray-600">
        Creates pending run and steps only. No execution, no providers, no tool_calls.
      </p>
    </div>
  );
}

function ClarifiedAnswerGapRow({ gap }: { gap: ClarifyingAnswerGap }) {
  return (
    <div className="flex items-start gap-2">
      <span className={`mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-medium ${gap.severity === "error" ? "bg-red-900/40 text-red-300" : "bg-yellow-900/40 text-yellow-300"}`}>
        {gap.severity}
      </span>
      <span className="text-[11px] text-gray-400">{gap.reason}</span>
    </div>
  );
}

// ── Source of Truth Draft from Intake Panel ────────────────────────────────

function SoTDraftFromIntakePanel({ result }: { result: SourceOfTruthDraftFromIntakeResponse }) {
  const v = result.validation;
  const d = result.draft;
  return (
    <div className="mt-2 space-y-3 rounded border border-emerald-900/40 bg-emerald-950/10 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-emerald-300">
          Source of Truth Draft
        </span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${v.valid ? "bg-emerald-900/50 text-emerald-300" : "bg-red-900/50 text-red-300"}`}>
          {v.valid ? "valid" : "invalid"}
        </span>
        <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${v.drift_risk === "low" ? "bg-gray-800 text-gray-400" : v.drift_risk === "medium" ? "bg-yellow-900/40 text-yellow-300" : "bg-red-900/40 text-red-300"}`}>
          drift: {v.drift_risk}
        </span>
        <span className="text-[10px] text-gray-500">
          confidence: {result.confidence} &nbsp;|&nbsp; source: {result.source} &nbsp;|&nbsp; {v.fields_populated} fields &nbsp;|&nbsp; {v.requirements_count} req.
        </span>
      </div>

      {v.errors.length > 0 && (
        <div className="rounded border border-red-800/50 bg-red-950/20 px-3 py-2">
          <p className="text-[10px] font-semibold text-red-300 mb-1">Errors ({v.errors.length})</p>
          <ul className="space-y-0.5">
            {v.errors.map((e, i) => <li key={i} className="text-[11px] text-red-400">• {e}</li>)}
          </ul>
        </div>
      )}

      {v.warnings.length > 0 && (
        <div className="rounded border border-yellow-800/50 bg-yellow-950/10 px-3 py-2">
          <p className="text-[10px] font-semibold text-yellow-300 mb-1">Warnings ({v.warnings.length})</p>
          <ul className="space-y-0.5">
            {v.warnings.map((w, i) => <li key={i} className="text-[11px] text-yellow-400">• {w}</li>)}
          </ul>
        </div>
      )}

      <div className="rounded border border-gray-800 bg-gray-950 px-3 py-2 space-y-2">
        {d.product_name && (
          <p className="text-xs font-bold text-gray-200">{d.product_name}</p>
        )}
        {d.product_summary && (
          <p className="text-[11px] text-gray-400">{d.product_summary}</p>
        )}
        {d.target_users.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Target Users</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.target_users.map((u, i) => <li key={i} className="text-[11px] text-gray-400">• {u}</li>)}
            </ul>
          </div>
        )}
        {d.goals.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Goals</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.goals.map((g, i) => <li key={i} className="text-[11px] text-gray-400">• {g}</li>)}
            </ul>
          </div>
        )}
        {d.requirements.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Requirements ({d.requirements.length})</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.requirements.map((r) => (
                <li key={r.id} className="text-[11px] text-gray-400">
                  <span className="font-mono text-[9px] text-gray-600">{r.id}</span>
                  {" "}
                  <span className={`text-[9px] font-medium ${r.priority === "must" ? "text-red-400" : "text-yellow-400"}`}>[{r.priority}]</span>
                  {" "}{r.title}
                </li>
              ))}
            </ul>
          </div>
        )}
        {d.constraints.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Constraints</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.constraints.map((c, i) => <li key={i} className="text-[11px] text-gray-400">• {c}</li>)}
            </ul>
          </div>
        )}
        {d.risks.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Risks</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.risks.map((r, i) => <li key={i} className="text-[11px] text-gray-400">• {r}</li>)}
            </ul>
          </div>
        )}
        {d.open_questions.length > 0 && (
          <div>
            <p className="text-[10px] font-semibold text-gray-500">Open Questions</p>
            <ul className="mt-0.5 space-y-0.5">
              {d.open_questions.map((q, i) => <li key={i} className="text-[11px] text-gray-400">• {q}</li>)}
            </ul>
          </div>
        )}
      </div>

      <div className="rounded border border-emerald-900/30 bg-emerald-950/5 px-3 py-2">
        <p className="text-[10px] font-semibold text-emerald-400">Next Action</p>
        <p className="mt-0.5 text-[11px] text-gray-400">{result.next_recommended_action}</p>
      </div>

      <p className="text-[10px] text-gray-600">
        SoT draft is read-only. No project or run is created. To persist, use POST /api/project-intake/source-of-truth-draft/confirm with confirm_persist=true and a project_id.
      </p>
    </div>
  );
}

// ── Run Step Preview Panel ──────────────────────────────────────────────────

function RunStepPreviewPanel({ result }: { result: ConfirmedPlanRunPreviewResponse }) {
  return (
    <div className="mt-4 space-y-3 rounded border border-gray-800 bg-gray-900/60 p-4">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold text-gray-200">{result.title}</h3>
        <span
          className={`rounded px-2 py-0.5 text-[11px] font-medium ${
            result.ready_to_create_run
              ? "bg-emerald-900/40 text-emerald-300"
              : "bg-yellow-900/40 text-yellow-300"
          }`}
        >
          {result.ready_to_create_run ? "Ready to create run" : "Not ready"}
        </span>
      </div>
      <p className="text-xs text-gray-400">{result.summary}</p>
      <div className="flex gap-4 text-[11px]">
        <span className={result.source_of_truth_ready ? "text-emerald-400" : "text-yellow-400"}>
          SoT: {result.source_of_truth_ready ? "Ready" : "Gaps"}
        </span>
        <span className={result.coverage_ready ? "text-emerald-400" : "text-yellow-400"}>
          Coverage: {result.coverage_ready ? "Ready" : "Gaps"}
        </span>
      </div>

      {result.blocking_issues.length > 0 && (
        <div className="rounded border border-red-800/60 bg-red-950/20 p-3">
          <p className="text-[11px] font-medium text-red-300">Blocking issues</p>
          <ul className="mt-1 space-y-1">
            {result.blocking_issues.map((issue, i) => (
              <li key={i} className="text-xs text-red-400">
                • {issue}
              </li>
            ))}
          </ul>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="rounded border border-yellow-800/60 bg-yellow-950/20 p-3">
          <p className="text-[11px] font-medium text-yellow-300">Warnings</p>
          <ul className="mt-1 space-y-1">
            {result.warnings.map((w, i) => (
              <li key={i} className="text-xs text-yellow-400">
                • {w}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <p className="text-[11px] font-medium text-gray-300">
          Future run steps ({result.steps.length})
        </p>
        {result.steps.map((step) => (
          <RunStepPreviewCard key={step.id} step={step} />
        ))}
      </div>

      <p className="rounded bg-gray-950 px-3 py-2 text-[10px] text-gray-600">
        Run step preview is read-only. It does not create a run, assign agents, write files,
        execute tools, or call providers.
      </p>

      {result.recommended_next_step && (
        <p className="text-xs text-gray-500">Next: {result.recommended_next_step}</p>
      )}
    </div>
  );
}

function RunStepPreviewCard({ step }: { step: ConfirmedRunStepPreview }) {
  return (
    <div className="rounded border border-gray-800 bg-gray-950/50 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-gray-600">{step.id}</span>
        <span className="text-xs font-medium text-gray-200">{step.title}</span>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${coverageStatusClass(step.coverage_status)}`}
        >
          {formatLabel(step.coverage_status)}
        </span>
        <span
          className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${driftRiskClass(step.drift_risk)}`}
        >
          {formatLabel(step.drift_risk)}
        </span>
        {step.manual_approval_required && (
          <span className="rounded bg-orange-900/40 px-1.5 py-0.5 text-[10px] font-medium text-orange-300">
            approval
          </span>
        )}
        {step.safe_to_prepare && (
          <span className="rounded bg-cyan-900/40 px-1.5 py-0.5 text-[10px] font-medium text-cyan-300">
            safe prep
          </span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-gray-500">{step.description}</p>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[10px] text-gray-600">
        {step.suggested_agent_id && <span>Agent: {step.suggested_agent_id}</span>}
        {step.required_requirement_ids.length > 0 && (
          <span>Reqs: {step.required_requirement_ids.join(", ")}</span>
        )}
        {step.depends_on.length > 0 && <span>Depends: {step.depends_on.join(", ")}</span>}
        {step.expected_deliverables.length > 0 && (
          <span>Deliverables: {step.expected_deliverables.join(", ")}</span>
        )}
      </div>
      {step.validation_notes && (
        <p className="mt-1 text-[10px] text-gray-600">{step.validation_notes}</p>
      )}
    </div>
  );
}

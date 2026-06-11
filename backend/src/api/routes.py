"""API routes for AI Workbench."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import subprocess
from datetime import datetime
from pathlib import Path

from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.agents.registry import get_agent, get_all_agents, get_enabled_agents, load_agent_instructions, select_agents_for_task
from src.models import (
    ApprovalDecision,
    ApprovalStatus,
    ApplyPatchRequest,
    ClarificationAnswerRequest,
    CommandAnalysisRequest,
    CommandAnalysisResponse,
    CommandIssue,
    ConfigUpdate,
    CreateProjectRequest,
    CreateRunRequest,
    ListFilesRequest,
    ModelRouteDecision,
    ModelRouteDecisionResponse,
    ModelRouteRequest,
    ProjectCommandKind,
    ProposePatchRequest,
    ProviderMode,
    ProviderStatus,
    ProviderModeUpdate,
    ReadFileRequest,
    RolledBackFile,
    RollbackPatchRequest,
    RollbackPatchResponse,
    RunProjectCommandRequest,
    RunProjectCommandResponse,
    RunStatus,
    SearchCodeRequest,
    AUTO_READ_ALLOWED_ACTIONS,
    AUTO_READ_BLOCKED_ACTIONS,
    AUTO_CONTEXT_MAX_HARD_CAP,
    AutoStepReadRequest,
    AutoStepReadResponse,
    AutoContextGatherRequest,
    AutoContextGatheredFile,
    AutoContextGatherResponse,
    ContextPatchDraftRequest,
    ContextPatchDraftResponse,
    StepContextBundle,
    StepContextBundleResponse,
    GuidedExecutionPlanResponse,
    GuidedStepExecutionPlan,
    StepToolPlanResponse,
    StepToolRecommendation,
    UpdateRunAgentAssignmentRequest,
    UpdateProjectRequest,
    PatchReviewRequest,
    PatchReviewResponse,
    PatchReviewOperation,
    PatchWorkflowPlanResponse,
    FailureToFixDraftRequest,
    FailureToFixDraftResponse,
    OperatorQueueItem,
    OperatorQueueResponse,
    OperatorQueueSummary,
    AutomationRunRequest,
    AutomationSafeLoopRequest,
    AutomationActionResult,
    AutomationRunResponse,
    AutomationApprovalCreateRequest,
    AutomationApprovalApproveRequest,
    AutomationApprovalRejectRequest,
    AutomationApprovalExecuteRequest,
    AutomationApprovalItem,
    AutomationApprovalListResponse,
    AutomationApprovalExecuteResponse,
    PatchOperation,
    AgentModuleContext,
    AgentExecutionRequest,
    AgentExecutionContext,
    AgentExecutionResult,
    AgentExecutionResponse,
    ExecuteNextStepRequest,
    ExecuteNextStepResponse,
    AgentExecutionListResponse,
    AgentPatchDraftRequest,
    AgentPatchDraftResponse,
    BoundedAutonomousLoopRequest,
    BoundedAutonomousLoopIteration,
    BoundedAutonomousLoopResponse,
    StepDeliverySummary,
    StepModuleDeliverySummary,
    RunDeliverySummary,
    RunModuleDeliverySummary,
    DeliveryReportRequest,
    DeliveryReportResponse,
    ProjectSourceOfTruthDocument,
    SourceOfTruthUpsertRequest,
    SourceOfTruthResponse,
    SourceOfTruthHistoryResponse,
    SourceOfTruthValidationResponse,
    SourceOfTruthSummaryResponse,
    ProjectModuleMapDocument,
    ProjectModuleMapUpsertRequest,
    ProjectModuleMapResponse,
    ProjectModuleMapHistoryResponse,
    ProjectModuleMapValidationResponse,
    ProjectModuleMapSummaryResponse,
    ProjectModuleMapScanPreviewRequest,
    ProjectModuleMapScanPreviewResponse,
    CockpitSourceOfTruth,
    CockpitModuleMap,
    CockpitRunStatus,
    CockpitModuleAwareness,
    CockpitNextAction,
    ProjectContextCockpitSummary,
)
from src.model_router import (
    build_context_patch_draft,
    review_patch_operations,
    build_patch_workflow_plan,
    build_guided_step_actions,
    build_step_context_bundle,
    infer_agent_for_step,
    infer_task_type_for_agent,
    infer_task_type_for_step,
    infer_tools_for_step,
    list_model_profiles,
    list_model_registry,
    list_providers,
    model_route_decision_from_result,
    route_model,
)
from src.orchestrator.cancellation import cancel_run_task, register_run_task
from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
    compare_guard_input_to_patch_payload,
)
from src.storage.guard_result_storage import (
    create_guard_result,
    get_guard_result,
    link_guard_result_to_apply,
    link_guard_result_to_proposal,
    list_guard_results,
)
from src.storage.source_of_truth_storage import (
    archive_project_source_of_truth as _archive_sot,
    build_persisted_source_of_truth_context_for_step as _build_persisted_sot_context,
    build_source_of_truth_summary as _build_sot_summary,
    create_or_update_project_source_of_truth as _upsert_sot,
    extract_requirement_context_for_step as _sot_req_context,
    get_active_project_source_of_truth as _get_active_sot,
    get_latest_project_source_of_truth as _get_latest_sot,
    get_project_source_of_truth_version as _get_sot_version,
    list_project_source_of_truth_history as _list_sot_history,
    validate_source_of_truth_payload as _validate_sot,
)
from src.storage.module_map_storage import (
    archive_project_module_map as _archive_module_map,
    build_agent_module_context_for_step as _build_module_context,
    build_patch_draft_module_context as _build_patch_draft_module_context,
    build_patch_proposal_module_awareness as _build_patch_proposal_module_awareness,
    build_module_map_summary as _build_module_map_summary,
    create_or_update_project_module_map as _upsert_module_map,
    find_modules_for_paths as _find_modules_for_paths,
    find_modules_for_requirement_ids as _find_modules_for_req_ids,
    get_active_project_module_map as _get_active_module_map,
    get_project_module_map_version as _get_module_map_version,
    list_project_module_map_history as _list_module_map_history,
    validate_module_map_payload as _validate_module_map,
    evaluate_module_aware_guard_policy as _evaluate_module_aware_guard_policy,
)
from src.orchestrator.project_module_map import (
    build_project_module_map_scan_preview as _scan_preview,
)
from src.orchestrator.workflow_policy import (
    WorkflowAutomationMode,
    WorkflowPolicyResponse,
    list_workflow_action_policies,
)
from src.orchestrator.project_intake import (
    ConfirmedPlanRunPreviewRequest,
    ConfirmedPlanRunPreviewResponse,
    ConfirmedRunFromPlanRequest,
    ConfirmedRunFromPlanResponse,
    ConfirmedRunCreatedStep,
    DevelopmentPlanPreviewRequest,
    DevelopmentPlanPreviewResponse,
    ExistingProjectRepoIntakeRequest,
    ExistingProjectRepoIntakeResponse,
    ProjectBriefDraftRequest,
    ProjectBriefDraftResponse,
    ProjectIntakeRequest,
    ProjectIntakeResponse,
    RequirementCoveragePreviewRequest,
    RequirementCoveragePreviewResponse,
    SourceOfTruthPreviewRequest,
    SourceOfTruthPreviewResponse,
    StepSourceOfTruthGuardRequest,
    StepSourceOfTruthGuardResponse,
    UnifiedIntakeRequest,
    UnifiedAutonomousIntakePreviewResponse,
    ClarifyingAnswersRequest,
    ClarifyingQuestionSet,
    ClarifiedIntakePreviewResponse,
    IntakeDevelopmentRunPreviewRequest,
    IntakeDevelopmentRunPreviewResponse,
    IntakeConfirmedRunCreationContractPreviewRequest,
    IntakeConfirmedRunCreationContractPreviewResponse,
    ConfirmedDevelopmentRunCreateRequest,
    ConfirmedDevelopmentRunCreateResponse,
    ConfirmedDevelopmentRunCreatedStep,
    DevelopmentRunStepContext,
    StepAgentPatchDraftRequest,
    StepAgentPatchDraftResponse,
    StepPatchDraftGuardedProposalRequest,
    StepPatchDraftGuardedProposalResponse,
    build_confirmed_development_run_creation_input,
    build_existing_project_repo_intake_preview,
    build_step_agent_patch_draft,
    build_step_patch_draft_proposal_preflight,
    build_pending_run_step_inputs_from_development_preview,
    normalize_development_run_step_context,
    _BRIDGE_SAFETY_NOTES,
    MultiAgentPlanFromIntakeRequest,
    MultiAgentPlanFromIntakeResponse,
    ModuleMapDraftFromIntakeRequest,
    ModuleMapDraftFromIntakeResponse,
    SourceOfTruthDraftFromIntakeRequest,
    SourceOfTruthDraftFromIntakeResponse,
    analyze_project_intake,
    build_confirmed_run_creation_contract_preview,
    build_intake_development_run_preview,
    build_multi_agent_plan_from_intake,
    build_clarifying_question_set,
    build_confirmed_plan_run_preview,
    build_module_map_draft_from_intake,
    build_requirement_coverage_from_plan,
    build_source_of_truth_draft_from_intake,
    build_source_of_truth_from_intake,
    build_unified_autonomous_intake_preview,
    draft_development_plan,
    draft_project_brief,
    evaluate_step_source_of_truth_guard,
    format_confirmed_run_step_requirement_context,
    parse_run_step_requirement_context,
    refine_unified_intake_with_answers,
)
from src.orchestrator.engine import (
    _execute_staged_steps,
    _persist_step_route_decisions,
    build_architecture_prompt,
    build_task_breakdown_prompt,
    execute_run,
    fallback_architecture,
    fallback_task_breakdown,
    format_staged_steps,
    stage_executable_task_steps,
)
from src.approvals.safety import check_command
from src.project_tools import analyze_command_result as _analyze_command
from src.project_tools import apply_project_patch
from src.project_tools import find_safe_command_for_kind
from src.project_tools import list_files as project_list_files
from src.project_tools import propose_project_patch
from src.project_tools import read_file as project_read_file
from src.project_tools import rollback_project_patch as _rollback_patch
from src.project_tools import run_project_command as _run_safe_command
from src.project_tools import search_code as project_search_code
from src.providers import claude_provider, codex, ollama


class AgentStepContextItem(BaseModel):
    step_id: str
    title: str
    status: str
    agent_role: str
    canonical_agent_id: str
    requirement_ids: list[str] = []
    module_ids: list[str] = []
    depends_on: list[str] = []
    safety_gates: list[str] = []
    manual_approval_required: bool = False
    provider_allowed: bool = False
    risk_level: str = "medium"
    next_safe_action: str
    ready_for_agent_execution: bool
    blockers: list[str] = []
    warnings: list[str] = []
    repo_context_available: bool = False
    detected_stack: list[str] = []
    detected_project_type: str | None = None
    relevant_area_hints: list[str] = []
    relevant_manifest_scripts: list[str] = []
    test_discovery_hints: list[str] = []
    protected_path_warnings: list[str] = []
    suggested_safe_commands: list[str] = []
    repo_safety_notes: list[str] = []
    repo_limitations: list[str] = []


class RunAgentStepContextResponse(BaseModel):
    run_id: str
    project_id: str | None = None
    total_steps: int
    ready_steps: int
    blocked_steps: int
    items: list[AgentStepContextItem] = []
    next_recommended_action: str
    safety_notes: list[str] = []


class RepoAwareControlledLoopStage(BaseModel):
    id: str
    title: str
    status: str
    summary: str
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action_label: str | None = None
    next_action_kind: str | None = None
    related_ids: dict[str, str] = Field(default_factory=dict)


class RepoAwareControlledLoopSafeCommand(BaseModel):
    command: str
    source: str
    reason: str
    execution: str = "copy_only_or_explicit_safe_runner"
    warnings: list[str] = Field(default_factory=list)


class RepoAwareControlledLoopPlanResponse(BaseModel):
    run_id: str
    step_id: str
    step_title: str | None = None
    repo_context_available: bool
    detected_stack: list[str] = Field(default_factory=list)
    current_stage: str
    next_recommended_action: str
    stages: list[RepoAwareControlledLoopStage] = Field(default_factory=list)
    safe_command_suggestions: list[RepoAwareControlledLoopSafeCommand] = Field(default_factory=list)
    guarded_proposal_available: bool = False
    patch_draft_available: bool = False
    apply_available: bool = False
    test_run_available: bool = False
    fix_draft_available: bool = False
    safety_notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
from src.storage.database import (
    create_approval,
    create_project,
    create_run,
    create_run_step,
    create_tool_call,
    delete_model_route_decisions_for_run,
    delete_step_route_decisions_for_run,
    find_pending_approval,
    get_approval,
    get_model_route_decisions_for_run,
    get_project,
    get_run,
    list_approvals,
    list_model_route_decisions_for_agents,
    list_model_route_decisions_for_steps,
    list_project_tool_calls,
    list_tool_calls_for_project,
    list_tool_calls_for_run,
    list_tool_calls_for_step,
    list_run_agent_assignments,
    list_run_steps,
    list_projects,
    list_runs,
    replace_run_agent_assignments,
    resolve_approval,
    upsert_model_route_decision,
    upsert_step_route_decision,
    update_tool_call,
    update_run_agent_assignment,
    update_project,
    update_run,
    update_run_step,
)
from src.utils.config import get_config, save_config
from src.utils.paths import PROJECT_ROOT, resolve_runtime_path

router = APIRouter()


# ── Health ───────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    cfg = get_config()
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    ollama_ok = await ollama.check_health(ollama_url)
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "ollama": "connected" if ollama_ok else "disconnected",
    }


# ── Projects ─────────────────────────────────────────────────────────────────

@router.get("/api/projects")
async def get_projects():
    return list_projects()


@router.get("/api/projects/{project_id}")
async def get_project_detail(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/api/projects")
async def post_project(req: CreateProjectRequest):
    try:
        return create_project(
            name=req.name,
            path=req.path,
            description=req.description,
            stack=req.stack,
            package_manager=req.package_manager,
            test_command=req.test_command,
            build_command=req.build_command,
            safe_commands=req.safe_commands,
            blocked_commands=req.blocked_commands,
            ignore_paths=req.ignore_paths,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/api/projects/{project_id}")
async def patch_project(project_id: str, req: UpdateProjectRequest):
    try:
        project = update_project(project_id, **req.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


# ── Agents ───────────────────────────────────────────────────────────────────

@router.get("/api/agents")
async def get_agents():
    return get_all_agents()


@router.get("/api/agents/registry")
async def get_agent_registry():
    return get_all_agents()


# ── Models and Providers ─────────────────────────────────────────────────────

@router.get("/api/models/registry")
async def get_model_registry():
    cfg = get_config()
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    available_models = await ollama.list_models(ollama_url)
    return list_model_registry(available_models, cfg)


@router.get("/api/models/profiles")
async def get_model_profiles():
    return list_model_profiles()


@router.post("/api/models/route")
async def post_model_route(req: ModelRouteRequest):
    cfg = get_config()
    route_request = req
    if not route_request.available_models:
        ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
        route_request = req.model_copy(update={"available_models": await ollama.list_models(ollama_url)})
    return route_model(route_request, cfg)


@router.get("/api/providers")
async def get_providers():
    return list_providers(get_config())


@router.get("/api/providers/status")
async def get_provider_status():
    cfg = get_config()
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    local_models = await ollama.list_models(ollama_url)
    local_available = bool(local_models) or await ollama.check_health(ollama_url)
    codex_available = await codex.check_available()
    claude_available = await claude_provider.check_available()
    return [
        ProviderStatus(
            id="local_ollama",
            enabled=True,
            available=local_available,
            status="connected" if local_available else "disconnected",
            models=local_models,
            warnings=[] if local_available else ["Ollama is not reachable at the configured base URL."],
        ),
        ProviderStatus(
            id="chatgpt_codex",
            enabled=bool(cfg.get("codex", {}).get("enabled", False)),
            available=codex_available,
            status="available" if codex_available else "not_installed",
            models=["chatgpt-codex:default"] if codex_available else [],
            warnings=[] if codex_available else ["Codex CLI was not found on PATH."],
        ),
        ProviderStatus(
            id="claude_code",
            enabled=bool(cfg.get("claude", {}).get("enabled", False)),
            available=claude_available,
            status="available" if claude_available else "not_installed",
            models=["claude-code:sonnet"] if claude_available else [],
            warnings=[] if claude_available else ["Claude Code CLI was not found on PATH."],
        ),
        ProviderStatus(
            id="external_api",
            enabled=bool(cfg.get("external_api", {}).get("enabled", False)),
            available=False,
            status="not_configured",
            models=[],
            warnings=["External API adapters are metadata-only in this slice."],
        ),
    ]


@router.patch("/api/settings/provider-mode")
async def patch_provider_mode(req: ProviderModeUpdate):
    updated = save_config({"provider_mode": req.provider_mode.value})
    return {"provider_mode": updated.get("provider_mode", req.provider_mode.value)}


# ── Runs ─────────────────────────────────────────────────────────────────────

@router.get("/api/runs")
async def get_runs():
    return list_runs()


@router.post("/api/runs")
async def post_run(req: CreateRunRequest):
    if not req.project_id:
        raise HTTPException(status_code=400, detail="project_id is required")
    project = get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.path:
        raise HTTPException(status_code=400, detail="Project path is not configured")

    cfg = get_config()
    run = create_run(
        prompt=req.prompt,
        mode=req.mode.value,
        project_id=project.id,
        project_path=project.path,
    )
    selection = select_agents_for_task(
        prompt=req.prompt,
        project_name=project.name,
        project_path=project.path,
        project_stack=project.stack,
        package_manager=project.package_manager,
    )
    assigned_agents = replace_run_agent_assignments(
        run.id,
        selection["selected_agents"],
    )

    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    ollama_model = cfg.get("ollama", {}).get("default_model", "qwen2.5-coder:7b")

    task = asyncio.create_task(
        execute_run(
            run_id=run.id,
            prompt=req.prompt,
            mode=req.mode.value,
            run_dir=run.run_dir,
            project_id=project.id,
            project_name=project.name,
            project_path=project.path,
            project_stack=project.stack,
            selected_agents=[assignment.model_dump() for assignment in assigned_agents],
            provider_mode=cfg.get("provider_mode", "local"),
            ollama_base_url=ollama_url,
            ollama_model=ollama_model,
        )
    )
    register_run_task(run.id, task)
    return run


@router.get("/api/runs/{run_id}")
async def get_run_detail(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/api/runs/{run_id}/steps")
async def get_run_steps(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return list_run_steps(run_id)


@router.post("/api/runs/{run_id}/steps/{step_id}/source-of-truth-guard")
async def post_run_step_source_of_truth_guard(
    run_id: str,
    step_id: str,
    req: StepSourceOfTruthGuardRequest,
    persist: bool = Query(False, description="When true, persist the guard result as an audit record."),
) -> StepSourceOfTruthGuardResponse:
    """Check proposed step action against persisted source-of-truth metadata.

    By default read-only (persist=false): no DB writes, no ToolCalls,
    no tools/providers, no patches, no command execution, no state mutation.

    When persist=true: writes exactly one guard_results audit record.
    Still no ToolCalls, tools, providers, patches, or execution.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = list_run_steps(run_id)
    step = next((item for item in steps if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Run step not found for this run")
    if not req.proposed_action or not req.proposed_action.strip():
        raise HTTPException(status_code=400, detail="Field 'proposed_action' must be a non-empty string.")

    parsed = parse_run_step_requirement_context(step.input)
    result = evaluate_step_source_of_truth_guard(
        context=parsed,
        proposed_action=req.proposed_action,
        file_path=req.file_path,
        patch_summary=req.patch_summary,
        old_text=req.old_text,
        new_text=req.new_text,
    )

    persisted_flag = False
    guard_result_id = None

    if persist:
        import uuid as _uuid

        input_snap = build_guard_input_snapshot(
            proposed_action=req.proposed_action,
            file_path=req.file_path,
            patch_summary=req.patch_summary,
            old_text=req.old_text,
            new_text=req.new_text,
        )
        ctx_snap = build_requirement_context_snapshot(
            requirement_ids=parsed.requirement_ids,
            coverage_status=parsed.coverage_status,
            drift_risk=parsed.drift_risk,
            acceptance_criteria=parsed.acceptance_criteria,
            constraints=parsed.constraints,
            forbidden_changes=parsed.forbidden_changes,
            validation_notes=parsed.validation_notes,
            source_of_truth_summary=parsed.source_of_truth_summary,
        )
        result_snap = build_guard_result_snapshot(
            decision=result.decision.value,
            drift_risk=result.drift_risk,
            matched_requirement_ids=result.matched_requirement_ids,
            violated_constraints=result.violated_constraints,
            forbidden_change_hits=result.forbidden_change_hits,
            warnings=result.warnings,
            reasons=result.reasons,
            recommended_next_step=result.recommended_next_step,
        )
        record = build_workflow_guard_result_record(
            id=str(_uuid.uuid4()),
            run_id=run_id,
            step_id=step_id,
            project_id=run.project_id or None,
            input_snapshot=input_snap,
            requirement_context_snapshot=ctx_snap,
            result_snapshot=result_snap,
            source=WorkflowGuardSource.RUN_STEP_GUARD,
        )
        try:
            saved = create_guard_result(record)
            persisted_flag = True
            guard_result_id = saved.id
        except Exception:
            raise HTTPException(
                status_code=500,
                detail="Guard evaluated successfully but failed to persist guard result.",
            )

    return StepSourceOfTruthGuardResponse(
        run_id=run_id,
        step_id=step_id,
        has_requirement_context=not parsed.parse_warnings or "AI_WORKBENCH_REQUIREMENT_CONTEXT block not found" not in parsed.parse_warnings,
        parsed_context=parsed,
        guard_result=result,
        persisted=persisted_flag,
        guard_result_id=guard_result_id,
    )


@router.get("/api/runs/{run_id}/guard-results")
async def get_run_guard_results(
    run_id: str,
    step_id: Optional[str] = Query(None),
    include_stale: bool = Query(False),
    limit: int = Query(50),
) -> dict:
    """List persisted guard results for a run.  Read-only — no DB writes."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    records = list_guard_results(
        run_id=run_id,
        step_id=step_id,
        include_stale=include_stale,
        limit=limit,
    )
    return {
        "run_id": run_id,
        "total": len(records),
        "items": [_guard_result_to_api(r) for r in records],
    }


@router.get("/api/runs/{run_id}/guard-results/{guard_result_id}")
async def get_run_guard_result_detail(
    run_id: str,
    guard_result_id: str,
) -> dict:
    """Get a single persisted guard result.  Read-only — no DB writes."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    record = get_guard_result(guard_result_id)
    if not record or record.run_id != run_id:
        raise HTTPException(status_code=404, detail="Guard result not found for this run")
    return _guard_result_to_api(record)


@router.post("/api/runs/{run_id}/steps/{step_id}/guard-results/{guard_result_id}/validate-for-proposal")
async def post_validate_guard_result_for_proposal(
    run_id: str,
    step_id: str,
    guard_result_id: str,
    req: _ValidateGuardForProposalRequest,
) -> dict:
    """Check whether a persisted guard result is usable for proposal creation.

    Read-only — no DB writes, no tool_calls, no proposals, no patches, no execution.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = list_run_steps(run_id)
    step = next((item for item in steps if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Run step not found for this run")
    record = get_guard_result(guard_result_id)
    if not record or record.run_id != run_id or record.step_id != step_id:
        raise HTTPException(status_code=404, detail="Guard result not found for this run and step")

    comparison = compare_guard_input_to_patch_payload(
        record,
        proposed_action=req.proposed_action or record.input_snapshot.proposed_action,
        file_path=req.file_path,
        patch_summary=req.patch_summary,
        old_text=req.old_text,
        new_text=req.new_text,
    )
    blocking: list[str] = []
    warnings: list[str] = []

    if comparison.is_stale:
        blocking.append("Guard result is stale relative to the proposed patch payload.")
    decision_val = record.result_snapshot.decision.value if hasattr(record.result_snapshot.decision, "value") else str(record.result_snapshot.decision)
    base_usable = (
        decision_val == "allowed"
        or (decision_val == "warning" and req.warning_acknowledged)
    )
    if decision_val == "blocked":
        blocking.append("Blocked guard result cannot authorize proposal creation.")
    if decision_val == "warning" and not req.warning_acknowledged:
        blocking.append("Warning guard requires explicit acknowledgement before proposal.")
    if req.no_guard_override and decision_val == "blocked":
        blocking.append("no_guard_override does not override a blocked guard.")

    usable = base_usable and not comparison.is_stale and not blocking
    return {
        "guard_result_id": guard_result_id,
        "valid": usable,
        "decision": decision_val,
        "is_stale": comparison.is_stale or record.is_stale,
        "stale_reasons": [r.value for r in comparison.stale_reasons],
        "blocking_reasons": blocking,
        "warnings": warnings,
        "requires_warning_acknowledgement": decision_val == "warning" and not req.warning_acknowledged,
        "recommended_next_step": (
            "Guard result is usable for proposal creation."
            if usable
            else "Run a fresh guard check or resolve blocking conditions."
        ),
    }


class _ValidateGuardForProposalRequest(BaseModel):
    proposed_action: Optional[str] = None
    file_path: Optional[str] = None
    patch_summary: Optional[str] = None
    old_text: Optional[str] = None
    new_text: Optional[str] = None
    warning_acknowledged: bool = False
    no_guard_override: bool = False


def _guard_result_to_api(record) -> dict:
    """Flatten a WorkflowGuardResultRecord to a lightweight API dict."""
    snap_in = record.input_snapshot
    snap_ctx = record.requirement_context_snapshot
    snap_res = record.result_snapshot
    decision_val = snap_res.decision.value if hasattr(snap_res.decision, "value") else str(snap_res.decision)
    drift_val = snap_res.drift_risk.value if hasattr(snap_res.drift_risk, "value") else str(snap_res.drift_risk)
    return {
        "id": record.id,
        "run_id": record.run_id,
        "step_id": record.step_id,
        "project_id": record.project_id,
        "decision": decision_val,
        "drift_risk": drift_val,
        "is_stale": record.is_stale,
        "stale_reasons": [r.value if hasattr(r, "value") else str(r) for r in record.stale_reasons],
        "source": record.source.value if hasattr(record.source, "value") else str(record.source),
        "proposal_tool_call_id": record.proposal_tool_call_id,
        "apply_tool_call_id": record.apply_tool_call_id,
        "warning_acknowledged": record.warning_acknowledged,
        "no_guard_override": record.no_guard_override,
        "created_at": record.created_at.isoformat() if hasattr(record.created_at, "isoformat") else str(record.created_at),
        "updated_at": record.updated_at.isoformat() if record.updated_at and hasattr(record.updated_at, "isoformat") else None,
        "expires_at": record.expires_at.isoformat() if record.expires_at and hasattr(record.expires_at, "isoformat") else None,
        "proposed_action": snap_in.proposed_action,
        "file_path": snap_in.file_path,
        "patch_summary": snap_in.patch_summary,
        "old_text_hash": snap_in.old_text_hash,
        "new_text_hash": snap_in.new_text_hash,
        "requirement_ids": snap_ctx.requirement_ids,
        "coverage_status": snap_ctx.coverage_status,
        "matched_requirement_ids": snap_res.matched_requirement_ids,
        "violated_constraints": snap_res.violated_constraints,
        "forbidden_change_hits": snap_res.forbidden_change_hits,
        "warnings": snap_res.warnings,
        "reasons": snap_res.reasons,
        "recommended_next_step": snap_res.recommended_next_step,
    }


def _tool_call_time_value(call) -> datetime | None:
    for value in (call.completed_at, call.finished_at, call.created_at, call.started_at):
        if not value:
            continue
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            continue
    return None


def _tool_call_output(call) -> dict:
    return _json_obj(call.output_json)


def _tool_call_input(call) -> dict:
    return _json_obj(call.input_json)


def _short_text(value: str, max_chars: int = 500) -> str:
    if not value:
        return ""
    return value if len(value) <= max_chars else value[:max_chars] + "\n... truncated by AI Workbench ..."


def _patch_lifecycle_tool_call_summary(call) -> dict:
    output = _tool_call_output(call)
    input_data = _tool_call_input(call)
    guard_result_id = output.get("guard_result_id") or input_data.get("guard_result_id")
    return {
        "tool_call_id": call.id,
        "tool_name": call.tool_name,
        "status": call.status,
        "run_id": call.run_id,
        "step_id": call.step_id,
        "project_id": call.project_id,
        "created_at": call.created_at,
        "started_at": call.started_at,
        "finished_at": call.finished_at,
        "completed_at": call.completed_at,
        "returncode": call.returncode,
        "command": call.command,
        "command_kind": input_data.get("command_kind", ""),
        "summary": output.get("summary", ""),
        "guard_result_id": guard_result_id,
        "guard_revalidated": output.get("guard_revalidated") is True,
        "no_guard_override": bool(output.get("no_guard_override") or input_data.get("no_guard_override")),
        "stdout_preview": _short_text(call.stdout or "", 500),
        "stderr_preview": _short_text(call.stderr or call.error or "", 500),
        "timed_out": output.get("timed_out") is True,
    }


def _is_step_test_command(call) -> bool:
    if call.tool_name != "run-command":
        return False
    input_data = _tool_call_input(call)
    if input_data.get("command_kind") == "test":
        return True
    command = (call.command or input_data.get("command") or "").lower()
    return "test" in command or "pytest" in command


def _latest_call(calls: list) -> object | None:
    if not calls:
        return None
    return max(calls, key=lambda call: _tool_call_time_value(call) or datetime.min)


def _patch_lifecycle_recommendation(
    *,
    guard_records: list,
    proposal_calls: list,
    latest_apply,
    latest_test,
    tests_after_latest_apply: bool,
) -> str:
    successful_proposals = [call for call in proposal_calls if call.status == "completed"]
    if not guard_records:
        return "create_guard"
    if not successful_proposals:
        return "create_proposal"
    if latest_apply is None or latest_apply.status != "completed":
        return "apply_patch"
    if latest_test is None or not tests_after_latest_apply:
        return "run_tests_manual"
    test_output = _tool_call_output(latest_test)
    if latest_test.returncode not in (None, 0) or test_output.get("timed_out") is True:
        return "analyze_failed_tests_manual"
    return "review_success"


def _loop_stage(
    *,
    id: str,
    title: str,
    status: str,
    summary: str,
    blockers: list[str] | None = None,
    warnings: list[str] | None = None,
    next_action_label: str | None = None,
    next_action_kind: str | None = None,
    related_ids: dict[str, str] | None = None,
) -> RepoAwareControlledLoopStage:
    allowed = {"not_started", "ready", "blocked", "waiting_for_confirmation", "completed", "failed", "unknown"}
    return RepoAwareControlledLoopStage(
        id=id,
        title=title,
        status=status if status in allowed else "unknown",
        summary=summary,
        blockers=blockers or [],
        warnings=warnings or [],
        next_action_label=next_action_label,
        next_action_kind=next_action_kind,
        related_ids=related_ids or {},
    )


def _controlled_loop_safe_commands(context: DevelopmentRunStepContext, run) -> list[RepoAwareControlledLoopSafeCommand]:
    commands: list[RepoAwareControlledLoopSafeCommand] = []

    def add(command: str, source: str, reason: str, warnings: list[str] | None = None) -> None:
        command = (command or "").strip()
        if not command or any(item.command == command for item in commands) or len(commands) >= 8:
            return
        commands.append(RepoAwareControlledLoopSafeCommand(
            command=command[:180],
            source=source[:120],
            reason=reason[:220],
            warnings=warnings or [],
        ))

    for command in context.suggested_safe_commands:
        add(
            command,
            "repo-aware context",
            "Suggested by repository manifest/test discovery metadata. Copy only unless using the existing explicit safe runner.",
            ["Suggestion only; this endpoint does not execute commands."],
        )

    project = get_project(run.project_id) if run.project_id else None
    if project and (project.test_command or "").strip():
        add(
            project.test_command.strip(),
            "project profile",
            "Configured project test command. Execution still requires the existing explicit safe command runner.",
            ["Requires explicit operator action and existing command safety checks."],
        )
    return commands


def _build_repo_aware_controlled_loop_plan(run, step) -> RepoAwareControlledLoopPlanResponse:
    """Build a read-only controlled apply/test/fix plan from existing evidence."""
    context = normalize_development_run_step_context(step.input or "")
    step_calls = [tc for tc in list_tool_calls_for_step(step.id, limit=300) if tc.run_id == run.id]
    proposal_calls = [tc for tc in step_calls if tc.tool_name == "propose-patch"]
    successful_proposals = [tc for tc in proposal_calls if tc.status == "completed"]
    apply_calls = [tc for tc in step_calls if tc.tool_name == "apply-patch"]
    completed_applies = [tc for tc in apply_calls if tc.status == "completed"]
    test_calls = [tc for tc in step_calls if _is_step_test_command(tc)]
    analysis_calls = [tc for tc in step_calls if tc.tool_name == "analyze-command-result"]
    fix_draft_calls = [tc for tc in step_calls if tc.tool_name == "failure-to-fix-draft"]
    guard_records = list_guard_results(run_id=run.id, step_id=step.id, include_stale=True, limit=50)

    latest_proposal = _latest_call(successful_proposals)
    latest_apply = _latest_call(completed_applies)
    latest_test = _latest_call(test_calls)
    latest_analysis = _latest_call(analysis_calls)
    latest_fix_draft = _latest_call(fix_draft_calls)
    latest_apply_time = _tool_call_time_value(latest_apply) if latest_apply else None
    latest_test_time = _tool_call_time_value(latest_test) if latest_test else None
    tests_after_apply = bool(latest_apply_time and latest_test_time and latest_test_time >= latest_apply_time)
    test_failed = bool(
        latest_test
        and (latest_test.returncode not in (None, 0) or _tool_call_output(latest_test).get("timed_out") is True)
    )
    test_passed = bool(
        latest_test
        and latest_test.returncode == 0
        and _tool_call_output(latest_test).get("timed_out") is not True
    )

    safe_commands = _controlled_loop_safe_commands(context, run)
    protected_warnings = [f"Repo-aware protected path warning: {warning}" for warning in context.protected_path_warnings]
    stages: list[RepoAwareControlledLoopStage] = []

    stages.append(_loop_stage(
        id="repo_context",
        title="Repo Context",
        status="completed" if context.repo_context_available else "unknown",
        summary=(
            "Repo-aware metadata is available for this step."
            if context.repo_context_available
            else "No repo-aware context block was found for this step."
        ),
        warnings=protected_warnings,
        next_action_label="Review repo-aware step context" if context.repo_context_available else "Attach repo intake to a future confirmed run",
        next_action_kind="prepare_patch_draft" if context.repo_context_available else None,
    ))

    patch_ready = context.repo_context_available and not guard_records and not successful_proposals
    patch_completed = bool(guard_records or successful_proposals or completed_applies or test_calls)
    stages.append(_loop_stage(
        id="patch_draft",
        title="Patch Draft",
        status="completed" if patch_completed else ("ready" if patch_ready else "blocked"),
        summary=(
            "Patch/proposal evidence exists, so the draft-prep stage has been passed."
            if patch_completed
            else "Prepare a bounded patch draft from this repo-aware step."
        ),
        blockers=[] if (patch_ready or patch_completed) else ["Repo-aware context is missing; prepare step context before drafting."],
        warnings=protected_warnings,
        next_action_label="Prepare Patch Draft" if patch_ready else None,
        next_action_kind="prepare_patch_draft" if patch_ready else None,
    ))

    guarded_completed = bool(successful_proposals)
    guarded_ready = bool(guard_records or patch_ready or patch_completed) and not guarded_completed
    stages.append(_loop_stage(
        id="guarded_proposal",
        title="Guarded Proposal",
        status="completed" if guarded_completed else ("ready" if guarded_ready else "blocked"),
        summary=(
            "A completed guarded proposal exists."
            if guarded_completed
            else "Run guard/proposal preflight, then create a proposal only after explicit operator confirmation."
        ),
        blockers=[] if (guarded_ready or guarded_completed) else ["Patch draft context is not ready."],
        warnings=protected_warnings,
        next_action_label="Preflight Guarded Proposal" if guarded_ready else None,
        next_action_kind="run_guard_preflight" if guarded_ready else None,
        related_ids={"proposal_tool_call_id": latest_proposal.id} if latest_proposal else {},
    ))

    apply_completed = bool(latest_apply)
    apply_ready = guarded_completed and not apply_completed
    stages.append(_loop_stage(
        id="apply_patch",
        title="Apply Patch",
        status="completed" if apply_completed else ("waiting_for_confirmation" if apply_ready else "blocked"),
        summary=(
            "A completed apply-patch record exists."
            if apply_completed
            else "A guarded proposal can be applied only through the existing explicit confirm=true apply flow."
        ),
        blockers=[] if (apply_ready or apply_completed) else ["No completed guarded proposal is available."],
        warnings=["Apply is destructive and must remain a separate explicit confirmation."],
        next_action_label="Apply patch with explicit confirmation" if apply_ready else None,
        next_action_kind="apply_patch_requires_confirm" if apply_ready else None,
        related_ids={"apply_tool_call_id": latest_apply.id} if latest_apply else {},
    ))

    safe_test_completed = bool(latest_test and (not latest_apply or tests_after_apply))
    safe_test_ready = bool((latest_apply and not safe_test_completed) or safe_commands)
    stages.append(_loop_stage(
        id="safe_test",
        title="Safe Test",
        status="completed" if safe_test_completed else ("ready" if safe_test_ready else "not_started"),
        summary=(
            "A test/run-command record exists for this step."
            if safe_test_completed
            else "Safe commands are suggestions unless the operator uses the existing explicit safe runner."
        ),
        warnings=["Safe commands are copy-only suggestions from this plan endpoint."],
        next_action_label="Run safe test manually" if safe_test_ready and not safe_test_completed else None,
        next_action_kind="run_safe_test_requires_confirm" if safe_test_ready and not safe_test_completed else None,
        related_ids={"test_tool_call_id": latest_test.id} if latest_test else {},
    ))

    analyze_ready = bool(latest_test)
    analyze_completed = bool(latest_analysis)
    stages.append(_loop_stage(
        id="analyze_test_result",
        title="Analyze Test Result",
        status="completed" if analyze_completed else ("ready" if analyze_ready else "not_started"),
        summary=(
            "A command-result analysis record exists."
            if analyze_completed
            else "Analyze failed or ambiguous test output before preparing a fix draft."
        ),
        blockers=[] if analyze_ready else ["No test result exists yet."],
        next_action_label="Analyze test result" if analyze_ready and not analyze_completed else None,
        next_action_kind="analyze_test_result" if analyze_ready and not analyze_completed else None,
        related_ids={"analysis_tool_call_id": latest_analysis.id} if latest_analysis else {},
    ))

    fix_ready = bool(test_failed and (latest_analysis or latest_test))
    fix_completed = bool(latest_fix_draft)
    stages.append(_loop_stage(
        id="fix_draft",
        title="Fix Draft",
        status="completed" if fix_completed else ("ready" if fix_ready else "not_started"),
        summary=(
            "A fix draft signal exists."
            if fix_completed
            else "Prepare a fix draft only after failed test evidence is available."
        ),
        blockers=[] if fix_ready or fix_completed or not latest_test else (["Latest test did not fail."] if test_passed else []),
        next_action_label="Prepare fix draft" if fix_ready and not fix_completed else None,
        next_action_kind="prepare_fix_draft" if fix_ready and not fix_completed else None,
        related_ids={"fix_draft_tool_call_id": latest_fix_draft.id} if latest_fix_draft else {},
    ))

    delivery_ready = bool((test_passed and safe_test_completed) or fix_completed)
    stages.append(_loop_stage(
        id="delivery_update",
        title="Delivery Update",
        status="ready" if delivery_ready else "not_started",
        summary="Review delivery state and update reports manually; this endpoint is status guidance only.",
        next_action_label="Update delivery report" if delivery_ready else None,
        next_action_kind="update_delivery_report" if delivery_ready else None,
    ))

    current_stage = next((stage.id for stage in stages if stage.status != "completed"), stages[-1].id if stages else "unknown")
    current = next((stage for stage in stages if stage.id == current_stage), stages[-1])
    next_action = current.next_action_label or current.summary

    return RepoAwareControlledLoopPlanResponse(
        run_id=run.id,
        step_id=step.id,
        step_title=step.title,
        repo_context_available=context.repo_context_available,
        detected_stack=context.detected_stack,
        current_stage=current_stage,
        next_recommended_action=next_action,
        stages=stages,
        safe_command_suggestions=safe_commands,
        guarded_proposal_available=bool(latest_proposal),
        patch_draft_available=patch_completed or patch_ready,
        apply_available=bool(latest_apply),
        test_run_available=bool(latest_test),
        fix_draft_available=fix_ready or fix_completed,
        safety_notes=[
            "Controlled loop plan is read-only status guidance.",
            "No patch is applied, no command is executed, no proposal is created, and no provider is called.",
            "Apply and safe test execution remain separate explicit operator actions.",
        ],
        limitations=[
            "Patch draft evidence is inferred from later guard/proposal/apply/test records because patch drafts are not persisted.",
            "Safe commands are suggestions or existing explicit safe-runner inputs only.",
            "No autonomous apply/test/fix loop is started by this endpoint.",
        ],
    )


@router.get("/api/runs/{run_id}/steps/{step_id}/repo-aware-controlled-loop-plan")
async def get_repo_aware_controlled_loop_plan(
    run_id: str,
    step_id: str,
) -> RepoAwareControlledLoopPlanResponse:
    """Return a read-only controlled apply/test/fix plan for a run step.

    Creates no ToolCalls, proposals, guard results, files, patches, commands,
    provider calls, or run execution. All actions are descriptors for manual UI.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    steps = list_run_steps(run_id)
    step = next((item for item in steps if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Run step not found for this run")
    return _build_repo_aware_controlled_loop_plan(run, step)


@router.get("/api/runs/{run_id}/steps/tool-plan")
async def get_run_step_tool_plan(run_id: str) -> StepToolPlanResponse:
    """Return per-step tool recommendations for a run's staged steps.

    Read-only — no ToolCalls are created, no tools are executed, no files written.
    Resolution order for task_type per step:
    1. Persisted step-level route decision (if any).
    2. infer_task_type_for_step from step title / input / agent_id.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    if not steps:
        return StepToolPlanResponse(
            run_id=run_id,
            recommendations=[],
            summary="No steps found for this run.",
            warnings=[],
        )

    # Build a map of step_id → persisted route decision for fast lookup
    step_decisions = {
        d.step_id: d
        for d in list_model_route_decisions_for_steps(run_id)
        if d.step_id
    }

    recommendations: list[StepToolRecommendation] = []
    warnings: list[str] = []

    for step in steps:
        decision = step_decisions.get(step.id)
        agent_id = ""
        task_type = ""
        if decision:
            agent_id = decision.agent_id or step.agent_id or ""
            task_type = decision.task_type or ""
        else:
            agent_id = step.agent_id or ""

        rec = infer_tools_for_step(step, agent_id=agent_id, task_type=task_type)
        recommendations.append(rec)
        warnings.extend(rec.warnings)

    n = len(recommendations)
    summary = (
        f"Tool plan for {n} step(s). No tools are executed automatically."
    )
    return StepToolPlanResponse(
        run_id=run_id,
        recommendations=recommendations,
        summary=summary,
        warnings=list(dict.fromkeys(warnings)),  # deduplicate preserving order
    )


@router.get("/api/runs/{run_id}/guided-execution-plan")
async def get_run_guided_execution_plan(run_id: str) -> GuidedExecutionPlanResponse:
    """Return a guided execution plan for each staged step in the run.

    Read-only — no ToolCalls are created, no tools are executed, no files written.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    if not steps:
        return GuidedExecutionPlanResponse(
            run_id=run_id,
            steps=[],
            summary="No steps found for this run.",
            warnings=[],
        )

    step_decisions = {
        d.step_id: d
        for d in list_model_route_decisions_for_steps(run_id)
        if d.step_id
    }

    all_calls = list_tool_calls_for_run(run_id)

    step_plans: list[GuidedStepExecutionPlan] = []
    warnings: list[str] = []

    for step in steps:
        decision = step_decisions.get(step.id)
        agent_id = (decision.agent_id if decision else None) or step.agent_id or ""
        task_type = (decision.task_type if decision else None) or ""
        tool_plan = infer_tools_for_step(step, agent_id=agent_id, task_type=task_type)
        plan = build_guided_step_actions(step, tool_plan, all_calls, decision)
        step_plans.append(plan)
        warnings.extend(plan.warnings)

    n = len(step_plans)
    pending = sum(
        1 for p in step_plans
        if p.recommended_next_action
        and p.recommended_next_action.action_type != "done"
    )
    summary = (
        f"Guided plan for {n} step(s): {pending} with pending actions. "
        "No actions run automatically."
    )
    return GuidedExecutionPlanResponse(
        run_id=run_id,
        steps=step_plans,
        summary=summary,
        warnings=list(dict.fromkeys(warnings)),
    )


@router.get("/api/runs/{run_id}/patch-workflow-plan")
async def get_run_patch_workflow_plan(run_id: str) -> PatchWorkflowPlanResponse:
    """Return an approval-gated patch workflow plan for each step in the run.

    Read-only — analyses existing tool_call history, no ToolCalls created,
    no tools executed, no files written, no patches applied or rolled back.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step_decisions = {
        d.step_id: d
        for d in list_model_route_decisions_for_steps(run_id)
        if d.step_id
    }
    all_calls = list_tool_calls_for_run(run_id)

    return build_patch_workflow_plan(
        run_id=run_id,
        steps=steps,
        tool_calls=all_calls,
        route_decisions=step_decisions,
    )


@router.post("/api/runs/{run_id}/steps/{step_id}/auto-read")
async def run_step_auto_read(
    run_id: str,
    step_id: str,
    req: AutoStepReadRequest,
) -> AutoStepReadResponse:
    """Execute a safe read-only tool for a staged step automatically.

    Permitted action types: list_files, read_file, search_code.
    Explicitly blocked: propose_patch, apply_patch, rollback_patch, run_command,
    analyze_result, run_tests, and any other non-read action.

    Creates a low-risk ToolCall record. Does not modify any project files.
    """
    # Safety gate — block before doing anything else
    if req.action_type in AUTO_READ_BLOCKED_ACTIONS:
        raise HTTPException(
            status_code=403,
            detail=(
                f"action_type '{req.action_type}' is not permitted for auto-read. "
                f"Only {sorted(AUTO_READ_ALLOWED_ACTIONS)} are allowed."
            ),
        )
    if req.action_type not in AUTO_READ_ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown action_type '{req.action_type}'. "
                f"Allowed: {sorted(AUTO_READ_ALLOWED_ACTIONS)}."
            ),
        )

    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Resolve step
    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Resolve project
    if not run.project_id:
        raise HTTPException(status_code=400, detail="Run has no associated project")
    project = get_project(run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Map action_type → tool_name and build tool-specific request
    tool_name_map = {
        "list_files": "list_files",
        "read_file": "read_file",
        "search_code": "search_code",
    }
    tool_name = tool_name_map[req.action_type]
    effective_agent_id = req.agent_id or step.agent_id or ""

    # Build input metadata
    input_meta: dict = {
        "action_type": req.action_type,
        "run_id": run_id,
        "step_id": step_id,
        "agent_id": effective_agent_id,
    }
    if req.action_type == "search_code":
        # Use query from request; fallback to step title
        query = req.query or step.title
        input_meta["query"] = query
        input_meta["limit"] = req.limit
    elif req.action_type == "read_file":
        if not req.file_path:
            raise HTTPException(
                status_code=400,
                detail="file_path is required for read_file action",
            )
        input_meta["file_path"] = req.file_path
    elif req.action_type == "list_files":
        input_meta["limit"] = req.limit

    started_at = datetime.now().isoformat()
    tool_call = create_tool_call(
        run_id=run_id,
        project_id=project.id,
        step_id=step_id,
        tool_name=tool_name,
        cwd=project.path,
        status="pending",
        input_json=json.dumps(input_meta, ensure_ascii=False),
        risk_level="low",
        started_at=started_at,
    )

    warnings: list[str] = []
    try:
        if req.action_type == "list_files":
            raw = project_list_files(project.path, path=".", max_files=req.limit)
        elif req.action_type == "read_file":
            raw = project_read_file(project.path, path=req.file_path)
        else:  # search_code
            query = req.query or step.title
            raw = project_search_code(project.path, query=query, max_results=req.limit)

        completed_at = datetime.now().isoformat()
        result_json = {**raw, "tool_call_id": tool_call.id}
        update_tool_call(
            tool_call.id,
            status="completed",
            output_json=json.dumps(result_json, ensure_ascii=False),
            completed_at=completed_at,
            finished_at=completed_at,
        )

        # Build human-readable summary
        if req.action_type == "list_files":
            n = len(raw.get("files", []))
            summary = f"Listed {n} file(s)."
        elif req.action_type == "read_file":
            chars = len(raw.get("content", ""))
            summary = f"Read {chars} character(s) from {req.file_path}."
        else:
            n = len(raw.get("matches", []))
            summary = f"Found {n} match(es) for '{req.query or step.title}'."

        return AutoStepReadResponse(
            run_id=run_id,
            step_id=step_id,
            action_type=req.action_type,
            tool_call_id=tool_call.id,
            status="completed",
            summary=summary,
            result=result_json,
            warnings=warnings,
        )

    except (PermissionError, ValueError) as exc:
        msg = str(exc)
        _mark_tool_call_failed(tool_call.id, msg)
        raise HTTPException(status_code=400, detail=msg) from exc
    except HTTPException:
        _mark_tool_call_failed(tool_call.id, "HTTP error")
        raise
    except Exception as exc:
        msg = str(exc)
        _mark_tool_call_failed(tool_call.id, msg)
        raise HTTPException(status_code=500, detail=f"Auto-read failed: {msg}") from exc


@router.post("/api/runs/{run_id}/steps/{step_id}/auto-context")
async def run_step_auto_context(
    run_id: str,
    step_id: str,
    req: AutoContextGatherRequest,
) -> AutoContextGatherResponse:
    """Bounded read-only context-gathering workflow for a staged step.

    Runs up to *max_tool_calls* (hard cap: 8) of list_files / search_code / read_file
    using a heuristic strategy.  No file is modified; no command is executed; no patch
    is proposed or applied.  Every call creates a low-risk ToolCall audit record.
    """
    # Enforce hard cap
    if req.max_tool_calls > AUTO_CONTEXT_MAX_HARD_CAP:
        raise HTTPException(
            status_code=400,
            detail=(
                f"max_tool_calls={req.max_tool_calls} exceeds hard cap "
                f"({AUTO_CONTEXT_MAX_HARD_CAP}). Reduce it."
            ),
        )
    cap = max(1, req.max_tool_calls)

    # Resolve run / step / project
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    if not run.project_id:
        raise HTTPException(status_code=400, detail="Run has no associated project")
    project = get_project(run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    effective_agent = req.agent_id or step.agent_id or ""
    now_iso = datetime.now().isoformat

    # Shared helper: create + run a low-risk tool call and return (tool_call_id, raw_result_or_None)
    def _run_read_tool(tool_name: str, input_meta: dict):
        tc = create_tool_call(
            run_id=run_id,
            project_id=project.id,
            step_id=step_id,
            tool_name=tool_name,
            cwd=project.path,
            status="pending",
            input_json=json.dumps(input_meta, ensure_ascii=False),
            risk_level="low",
            started_at=datetime.now().isoformat(),
        )
        try:
            if tool_name == "list_files":
                raw = project_list_files(project.path, path=".", max_files=200)
            elif tool_name == "search_code":
                raw = project_search_code(
                    project.path,
                    query=input_meta.get("query", ""),
                    max_results=input_meta.get("limit", 50),
                )
            else:  # read_file
                raw = project_read_file(project.path, path=input_meta["file_path"])
            completed = datetime.now().isoformat()
            result_payload = {**raw, "tool_call_id": tc.id}
            update_tool_call(
                tc.id,
                status="completed",
                output_json=json.dumps(result_payload, ensure_ascii=False),
                completed_at=completed,
                finished_at=completed,
            )
            return tc.id, raw
        except Exception as exc:
            _mark_tool_call_failed(tc.id, str(exc))
            return tc.id, None

    tool_call_ids: list[str] = []
    warnings: list[str] = []
    searched_queries: list[str] = []
    files_considered: list[str] = []
    files_read: list[AutoContextGatheredFile] = []
    budget = cap

    # ── Step 1: list_files ────────────────────────────────────────────────────
    if budget <= 0:
        pass
    else:
        tc_id, lf_raw = _run_read_tool("list_files", {"action": "list_files"})
        tool_call_ids.append(tc_id)
        budget -= 1

        if lf_raw:
            listed: list[str] = [f.get("path", f) if isinstance(f, dict) else str(f)
                                  for f in lf_raw.get("files", [])]
            files_considered = listed

    # ── Step 2: search_code ───────────────────────────────────────────────────
    search_query = req.query or step.title or getattr(step, "input", "") or "main"
    sc_matches: list[str] = []
    if budget > 0 and search_query:
        tc_id, sc_raw = _run_read_tool(
            "search_code",
            {"query": search_query, "limit": 50},
        )
        tool_call_ids.append(tc_id)
        budget -= 1
        searched_queries.append(search_query)

        if sc_raw:
            sc_matches = [m.get("path", "") for m in sc_raw.get("matches", []) if m.get("path")]
            # deduplicate and keep order
            seen: set[str] = set()
            deduped: list[str] = []
            for p in sc_matches:
                if p not in seen:
                    seen.add(p)
                    deduped.append(p)
            sc_matches = deduped

    # ── Step 3: read relevant files ───────────────────────────────────────────
    # Priority: search matches → file-list heuristic
    BACKEND_KEYWORDS  = {"route", "service", "controller", "model", "database", "api", "schema"}
    FRONTEND_KEYWORDS = {"component", "page", "client", "store", "hook"}
    TEST_KEYWORDS     = {"test", "spec"}
    DOC_KEYWORDS      = {"readme", "doc"}

    def _relevance_score(path: str) -> int:
        low = path.lower()
        if any(k in low for k in BACKEND_KEYWORDS | FRONTEND_KEYWORDS):
            return 3
        if any(k in low for k in TEST_KEYWORDS):
            return 2
        if any(k in low for k in DOC_KEYWORDS):
            return 1
        return 0

    candidates: list[str]
    if sc_matches:
        candidates = sc_matches[:3]
    else:
        # fall back to heuristic from file list
        candidates = sorted(files_considered, key=_relevance_score, reverse=True)[:3]

    # Apply include/exclude patterns from request
    if req.include_file_patterns:
        import fnmatch
        candidates = [
            c for c in candidates
            if any(fnmatch.fnmatch(c, pat) for pat in req.include_file_patterns)
        ]
    if req.exclude_file_patterns:
        import fnmatch
        candidates = [
            c for c in candidates
            if not any(fnmatch.fnmatch(c, pat) for pat in req.exclude_file_patterns)
        ]

    for file_path in candidates:
        if budget <= 0:
            warnings.append(f"Budget exhausted before reading '{file_path}'.")
            break
        reason = (
            f"matched search query '{search_query}'"
            if file_path in sc_matches
            else "selected by file-name heuristic"
        )
        tc_id, rf_raw = _run_read_tool("read_file", {"file_path": file_path})
        tool_call_ids.append(tc_id)
        budget -= 1
        if rf_raw is not None:
            files_read.append(AutoContextGatheredFile(
                file_path=file_path,
                reason=reason,
                source_tool_call_id=tc_id,
            ))
        else:
            warnings.append(f"Could not read '{file_path}'.")

    # ── Step 4: summary + next_recommended_action ─────────────────────────────
    read_only_task_types = {"review", "research", "analysis", "read-only"}
    task_type = getattr(step, "task_type", "") or ""
    has_context = bool(files_read)

    if task_type in read_only_task_types:
        next_action = "done"
    elif has_context:
        next_action = "propose_patch"
    elif searched_queries:
        next_action = "read_context"
    else:
        next_action = "search_code"

    n_calls = len(tool_call_ids)
    n_read  = len(files_read)
    summary = (
        f"Gathered context in {n_calls} tool call(s): "
        f"searched {len(searched_queries)} query/queries, "
        f"read {n_read} file(s). "
        f"Next: {next_action}."
    )
    if warnings:
        summary += f" Warnings: {len(warnings)}."

    status = "completed" if has_context or sc_matches else "partial"

    return AutoContextGatherResponse(
        run_id=run_id,
        step_id=step_id,
        status=status,
        summary=summary,
        tool_call_ids=tool_call_ids,
        searched_queries=searched_queries,
        files_considered=files_considered[:50],  # cap to avoid huge responses
        files_read=files_read,
        warnings=warnings,
        next_recommended_action=next_action,
    )


@router.get("/api/runs/{run_id}/tool-calls")
async def get_run_tool_calls(run_id: str):
    return list_tool_calls_for_run(run_id)


@router.get("/api/runs/{run_id}/steps/{step_id}/tool-calls")
async def get_step_tool_calls(run_id: str, step_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return [call for call in list_tool_calls_for_step(step_id) if call.run_id == run_id]


@router.get("/api/runs/{run_id}/steps/{step_id}/context-bundle")
async def get_step_context_bundle(run_id: str, step_id: str) -> StepContextBundleResponse:
    """Return an aggregated read-only context bundle for a step.

    Reads only already-stored ToolCall records.  Creates no new ToolCalls,
    runs no tools, modifies no files, executes no commands.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Fetch step-level route decision if present (best effort)
    route_decision: ModelRouteDecision | None = None
    try:
        step_routes = list_model_route_decisions_for_steps(run_id)
        route_decision = next((d for d in step_routes if d.step_id == step_id), None)
    except Exception:
        pass

    tool_calls = list_tool_calls_for_step(step_id)
    # Filter to this run only (defensive)
    tool_calls = [tc for tc in tool_calls if tc.run_id == run_id]

    bundle = build_step_context_bundle(
        run_id=run_id,
        step=step,
        tool_calls=tool_calls,
        route_decision=route_decision,
    )
    return StepContextBundleResponse(bundle=bundle)


@router.get("/api/runs/{run_id}/steps/{step_id}/patch-lifecycle")
async def get_step_patch_lifecycle(run_id: str, step_id: str) -> dict:
    """Return a read-only patch/test lifecycle summary for a run step.

    This endpoint reads existing RunStep, ToolCall, Project, and guard_result
    records only.  It creates no ToolCalls, executes no commands, applies no
    patches, calls no providers, and mutates no run/step state.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step = next((item for item in steps if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Run step not found for this run")

    step_calls = [tc for tc in list_tool_calls_for_step(step_id, limit=300) if tc.run_id == run_id]
    proposal_calls = [tc for tc in step_calls if tc.tool_name == "propose-patch"]
    apply_calls = [tc for tc in step_calls if tc.tool_name == "apply-patch"]
    test_calls = [tc for tc in step_calls if _is_step_test_command(tc)]
    guard_records = list_guard_results(run_id=run_id, step_id=step_id, include_stale=True, limit=50)

    latest_apply = _latest_call([call for call in apply_calls if call.status == "completed"])
    latest_test = _latest_call(test_calls)
    latest_apply_time = _tool_call_time_value(latest_apply) if latest_apply else None
    latest_test_time = _tool_call_time_value(latest_test) if latest_test else None
    tests_after_latest_apply = bool(
        latest_apply_time and latest_test_time and latest_test_time >= latest_apply_time
    )

    test_status = "not_run"
    confidence_reasons: list[str] = []
    if latest_test:
        test_output = _tool_call_output(latest_test)
        if latest_test.returncode == 0 and test_output.get("timed_out") is not True:
            test_status = "passed"
        else:
            test_status = "failed"
        if latest_apply and not tests_after_latest_apply:
            confidence_reasons.append("Latest test command predates the latest successful apply.")
    elif latest_apply:
        confidence_reasons.append("No test command is linked to this step after the latest successful apply.")

    if latest_apply and latest_test:
        confidence = "high" if tests_after_latest_apply else "medium"
    elif latest_apply:
        confidence = "medium"
    else:
        confidence = "low"

    project = get_project(run.project_id) if run.project_id else None
    safe_test_command_configured = bool(project and project.test_command.strip())
    test_command = project.test_command.strip() if project and safe_test_command_configured else ""

    recommended = _patch_lifecycle_recommendation(
        guard_records=guard_records,
        proposal_calls=proposal_calls,
        latest_apply=latest_apply,
        latest_test=latest_test,
        tests_after_latest_apply=tests_after_latest_apply,
    )

    return {
        "run_id": run_id,
        "step_id": step_id,
        "project_id": run.project_id,
        "guard_results": [_guard_result_to_api(record) for record in guard_records],
        "proposal_tool_calls": [_patch_lifecycle_tool_call_summary(call) for call in proposal_calls],
        "apply_tool_calls": [_patch_lifecycle_tool_call_summary(call) for call in apply_calls],
        "test_tool_calls": [_patch_lifecycle_tool_call_summary(call) for call in test_calls],
        "latest_proposal": _patch_lifecycle_tool_call_summary(_latest_call(proposal_calls)) if proposal_calls else None,
        "latest_apply": _patch_lifecycle_tool_call_summary(latest_apply) if latest_apply else None,
        "latest_test": _patch_lifecycle_tool_call_summary(latest_test) if latest_test else None,
        "apply_succeeded": latest_apply is not None and latest_apply.status == "completed",
        "tests_after_latest_apply": tests_after_latest_apply,
        "test_status": test_status,
        "confidence": confidence,
        "confidence_reasons": confidence_reasons,
        "safe_test_command_configured": safe_test_command_configured,
        "test_command": test_command,
        "recommended_manual_next_action": recommended,
    }


@router.post("/api/runs/{run_id}/steps/{step_id}/context-patch-draft")
async def get_context_patch_draft(
    run_id: str,
    step_id: str,
    req: ContextPatchDraftRequest,
) -> ContextPatchDraftResponse:
    """Build a draft patch proposal from the step's context bundle.

    Pure read-only: creates no ToolCalls, runs no tools, reads no files,
    creates no patch proposals, applies no patches.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found")

    # Build bundle from existing tool calls (no new calls created)
    tool_calls = [tc for tc in list_tool_calls_for_step(step_id) if tc.run_id == run_id]
    route_decision: ModelRouteDecision | None = None
    try:
        step_routes = list_model_route_decisions_for_steps(run_id)
        route_decision = next((d for d in step_routes if d.step_id == step_id), None)
    except Exception:
        pass

    bundle = build_step_context_bundle(
        run_id=run_id,
        step=step,
        tool_calls=tool_calls,
        route_decision=route_decision,
    )

    return build_context_patch_draft(
        run_id=run_id,
        step=step,
        bundle=bundle,
        request=req,
    )


@router.post("/api/runs/{run_id}/steps/{step_id}/failure-to-fix-draft")
async def create_failure_to_fix_draft(
    run_id: str,
    step_id: str,
    req: FailureToFixDraftRequest,
) -> FailureToFixDraftResponse:
    """Build a deterministic fix-draft context from the latest failed run-command.

    Pure read-only: creates no ToolCalls, executes no commands, calls no
    providers, writes no DB records, creates no patch proposals, applies nothing.
    Returns structured context for the operator to prefill the patch form.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    step_calls = [tc for tc in list_tool_calls_for_step(step_id, limit=300) if tc.run_id == run_id]
    all_run_commands = [tc for tc in step_calls if tc.tool_name == "run-command"]

    # Locate the failed run-command tool call -----------------------------------
    failed_call = None
    if req.failed_tool_call_id:
        failed_call = next((tc for tc in step_calls if tc.id == req.failed_tool_call_id), None)
        if not failed_call:
            raise HTTPException(
                status_code=404,
                detail="failed_tool_call_id not found for this step/run combination",
            )
        output = _tool_call_output(failed_call)
        if failed_call.returncode == 0 and not output.get("timed_out"):
            raise HTTPException(
                status_code=400,
                detail="The specified tool_call did not fail (returncode=0 and not timed out)",
            )
    else:
        failed_commands = [
            tc for tc in all_run_commands
            if (tc.returncode is not None and tc.returncode != 0)
            or _tool_call_output(tc).get("timed_out") is True
        ]
        if not failed_commands:
            raise HTTPException(
                status_code=404,
                detail="No failed run-command found for this step. Run a test command manually first.",
            )
        failed_call = _latest_call(failed_commands)

    if failed_call is None:
        raise HTTPException(status_code=404, detail="No failed run-command found for this step.")

    # Locate the latest apply tool call ----------------------------------------
    apply_calls = [tc for tc in step_calls if tc.tool_name == "apply-patch"]
    apply_call = None
    if req.apply_tool_call_id:
        apply_call = next((tc for tc in apply_calls if tc.id == req.apply_tool_call_id), None)
    if apply_call is None:
        apply_call = _latest_call([tc for tc in apply_calls if tc.status == "completed"])

    # Resolve guard_result_id --------------------------------------------------
    guard_result_id: str | None = req.guard_result_id
    if not guard_result_id and apply_call:
        guard_result_id = _tool_call_output(apply_call).get("guard_result_id") or None
    if not guard_result_id and apply_call:
        guard_result_id = _tool_call_input(apply_call).get("guard_result_id") or None

    # Build excerpts -----------------------------------------------------------
    max_stdout = max(0, min(req.max_stdout_chars, 8000))
    max_stderr = max(0, min(req.max_stderr_chars, 8000))
    stdout_excerpt = _short_text(failed_call.stdout or "", max_stdout)
    stderr_excerpt = _short_text(failed_call.stderr or failed_call.error or "", max_stderr)

    # Build fix context text ---------------------------------------------------
    ctx_lines: list[str] = [
        f"Step: {step.title}",
        f"Step ID: {step.id}",
        f"Failed command: {failed_call.command or 'unknown'}",
        f"Return code: {failed_call.returncode}",
        f"Failed tool_call: {failed_call.id}",
    ]
    if apply_call:
        ctx_lines.append(f"Latest apply tool_call: {apply_call.id}")
    if guard_result_id:
        ctx_lines.append(f"Guard result: {guard_result_id}")
    if stdout_excerpt:
        ctx_lines.append(f"\n--- stdout ---\n{stdout_excerpt}")
    if stderr_excerpt:
        ctx_lines.append(f"\n--- stderr ---\n{stderr_excerpt}")
    ctx_lines.append(
        "\nSuggested manual next action: "
        "create a new guarded patch proposal addressing the above failure."
    )
    fix_context = "\n".join(ctx_lines)

    # Warnings -----------------------------------------------------------------
    warnings: list[str] = []
    if not guard_result_id:
        warnings.append(
            "No guard result linked. Create a guard check before the next patch proposal."
        )
    if not apply_call:
        warnings.append(
            "No successful apply found for this step. "
            "The failure may not be from a previous guarded apply."
        )

    return FailureToFixDraftResponse(
        run_id=run_id,
        step_id=step_id,
        failed_tool_call_id=failed_call.id,
        apply_tool_call_id=apply_call.id if apply_call else None,
        guard_result_id=guard_result_id,
        command=failed_call.command or "",
        returncode=failed_call.returncode,
        stdout_excerpt=stdout_excerpt,
        stderr_excerpt=stderr_excerpt,
        fix_context=fix_context,
        suggested_next_action="create_guarded_patch_proposal",
        warnings=warnings,
        can_prefill_patch_context=True,
    )


@router.get("/api/runs/{run_id}/operator-queue")
async def get_run_operator_queue(
    run_id: str,
    step_id: Optional[str] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> OperatorQueueResponse:
    """Return a read-only operator queue of recommended next manual actions.

    Pure read-only: creates no ToolCalls, executes no commands, calls no
    providers, creates no patch proposals, applies no patches, mutates no state.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    all_steps = list_run_steps(run_id)

    if step_id:
        target_step = next((s for s in all_steps if s.id == step_id), None)
        if not target_step:
            raise HTTPException(status_code=404, detail="Step not found for this run")
        selected_steps = [target_step]
    else:
        selected_steps = all_steps

    all_run_calls = list_tool_calls_for_run(run_id)
    all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)
    # Fetch approvals once; pass step-filtered slice to _build_queue_item so the
    # execute_approval branch can surface pending approvals (GAP-004 fix).
    run_approvals = _list_run_automation_approvals(run_id)

    items: list[OperatorQueueItem] = []
    for step in selected_steps:
        step_approvals = [
            a for a in run_approvals
            if (getattr(a, "command", None) == step.id or not getattr(a, "command", None))
        ]
        item = _build_queue_item(
            run_id=run_id,
            step=step,
            tool_calls=[tc for tc in all_run_calls if tc.step_id == step.id],
            guard_records=[r for r in all_guard_records if r.step_id == step.id],
            approvals=step_approvals,
        )
        if item:
            items.append(item)

    # Sort: high priority first, then by step order
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (priority_order.get(i.priority, 9), selected_steps.index(
        next((s for s in selected_steps if s.id == i.step_id), selected_steps[0])
    )))
    items = items[:limit]

    summary = OperatorQueueSummary(
        total_items=len(items),
        blocked_items=sum(1 for i in items if i.status == "blocked"),
        ready_items=sum(1 for i in items if i.status == "ready"),
        manual_required_items=sum(1 for i in items if i.status == "manual_required"),
        done_items=sum(1 for i in items if i.status == "done"),
    )

    return OperatorQueueResponse(
        run_id=run_id,
        generated_at=datetime.now().isoformat(),
        items=items,
        summary=summary,
    )


def _build_agent_step_context_item(step) -> AgentStepContextItem:
    context = normalize_development_run_step_context(step.input or "")
    status = str(getattr(step.status, "value", step.status)).lower()
    blockers: list[str] = []
    warnings: list[str] = []

    if context.provider_allowed:
        blockers.append("provider_allowed=true is not allowed for intake-origin agent preparation.")
    if not get_agent(context.canonical_agent_id):
        blockers.append(f"Canonical agent '{context.canonical_agent_id}' is not registered.")
    if status != "pending":
        warnings.append(f"Step status is '{status}', so it is not a pending agent-prep candidate.")
    if not context.requirement_ids:
        warnings.append("No requirement links found in the step context.")
    if not context.module_ids:
        warnings.append("No module links found in the step context.")
    if not context.validation_steps:
        warnings.append("No validation steps found in the step context.")
    if not context.safety_gates:
        warnings.append("No safety gates found in the step context.")

    ready = status == "pending" and not blockers and not context.provider_allowed
    return AgentStepContextItem(
        step_id=step.id,
        title=step.title,
        status=status,
        agent_role=context.agent_role,
        canonical_agent_id=context.canonical_agent_id,
        requirement_ids=context.requirement_ids,
        module_ids=context.module_ids,
        depends_on=context.depends_on,
        safety_gates=context.safety_gates,
        manual_approval_required=context.manual_approval_required,
        provider_allowed=context.provider_allowed,
        risk_level=context.risk_level,
        next_safe_action=context.next_safe_action,
        ready_for_agent_execution=ready,
        blockers=blockers,
        warnings=warnings,
        repo_context_available=context.repo_context_available,
        detected_stack=context.detected_stack,
        detected_project_type=context.detected_project_type,
        relevant_area_hints=context.relevant_area_hints,
        relevant_manifest_scripts=context.relevant_manifest_scripts,
        test_discovery_hints=context.test_discovery_hints,
        protected_path_warnings=context.protected_path_warnings,
        suggested_safe_commands=context.suggested_safe_commands,
        repo_safety_notes=context.repo_safety_notes,
        repo_limitations=context.repo_limitations,
    )


@router.get("/api/runs/{run_id}/agent-step-context")
async def get_run_agent_step_context(run_id: str) -> RunAgentStepContextResponse:
    """Return read-only agent-prep context for existing run steps.

    Creates no records, calls no providers, reads no files, and starts no work.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    steps = list_run_steps(run_id)
    items = [_build_agent_step_context_item(step) for step in steps]
    ready_items = [item for item in items if item.ready_for_agent_execution]
    blocked_items = [item for item in items if item.blockers]
    first_ready = ready_items[0] if ready_items else None
    if first_ready:
        next_action = (
            f"Review '{first_ready.title}' with {first_ready.canonical_agent_id} in agent dry-run context. "
            "No provider call or execution is started by this summary."
        )
    elif blocked_items:
        next_action = f"Resolve blockers for '{blocked_items[0].title}' before preparing agent execution."
    else:
        next_action = "No pending ready step found. Review run status and existing step contexts."

    return RunAgentStepContextResponse(
        run_id=run_id,
        project_id=run.project_id,
        total_steps=len(items),
        ready_steps=len(ready_items),
        blocked_steps=len(blocked_items),
        items=items,
        next_recommended_action=next_action,
        safety_notes=[
            "Agent step context is read-only.",
            "No provider calls, tool_calls, commands, patches, or run execution are started.",
            "Use agent execution dry-run manually before any provider-enabled action.",
        ],
    )


@router.post("/api/runs/{run_id}/steps/{step_id}/agent-patch-draft")
async def create_step_agent_patch_draft(
    run_id: str,
    step_id: str,
    req: StepAgentPatchDraftRequest | None = None,
) -> StepAgentPatchDraftResponse:
    """Build a read-only patch draft candidate from agent-ready step context.

    Creates no ToolCalls, proposals, applies, commands, provider calls, file
    reads, or run execution.  The response is a bounded operator-reviewed draft.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    step = next((item for item in list_run_steps(run_id) if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    body = req or StepAgentPatchDraftRequest()
    context = normalize_development_run_step_context(step.input or "")
    return build_step_agent_patch_draft(
        run_id=run_id,
        step=step,
        agent_step_context=context,
        agent_result=body.agent_result if body.use_existing_agent_result else None,
        operator_note=body.operator_note,
        max_target_files=body.max_target_files,
        max_risks=body.max_risks,
        max_validation_steps=body.max_validation_steps,
    )


def _selected_step_patch_fields(req: StepPatchDraftGuardedProposalRequest) -> tuple[str, str, str]:
    draft = req.patch_draft if isinstance(req.patch_draft, dict) else {}
    target_files = draft.get("target_files", [])
    draft_file = ""
    if isinstance(target_files, list) and target_files:
        draft_file = str(target_files[0] or "")
    file_path = req.selected_file_path or str(draft.get("suggested_file_path") or draft_file or "")
    old_text = req.selected_old_text or str(draft.get("suggested_old_text") or "")
    new_text = req.selected_new_text or str(draft.get("suggested_new_text") or "")
    return file_path, old_text, new_text


def _patch_draft_text(req: StepPatchDraftGuardedProposalRequest, key: str, fallback: str = "") -> str:
    draft = req.patch_draft if isinstance(req.patch_draft, dict) else {}
    value = draft.get(key, fallback)
    if isinstance(value, (list, dict)):
        return fallback
    return str(value or fallback)


def _persist_guard_result_for_step_patch(
    *,
    run,
    step,
    proposed_action: str,
    file_path: str,
    patch_summary: str,
    old_text: str,
    new_text: str,
) -> tuple[StepSourceOfTruthGuardResponse, str | None]:
    """Evaluate and persist a Source of Truth guard result for explicit proposal creation."""
    import uuid as _uuid

    parsed = parse_run_step_requirement_context(step.input or "")
    result = evaluate_step_source_of_truth_guard(
        context=parsed,
        proposed_action=proposed_action,
        file_path=file_path,
        patch_summary=patch_summary,
        old_text=old_text,
        new_text=new_text,
    )
    input_snap = build_guard_input_snapshot(
        proposed_action=proposed_action,
        file_path=file_path,
        patch_summary=patch_summary,
        old_text=old_text,
        new_text=new_text,
    )
    ctx_snap = build_requirement_context_snapshot(
        requirement_ids=parsed.requirement_ids,
        coverage_status=parsed.coverage_status,
        drift_risk=parsed.drift_risk,
        acceptance_criteria=parsed.acceptance_criteria,
        constraints=parsed.constraints,
        forbidden_changes=parsed.forbidden_changes,
        validation_notes=parsed.validation_notes,
        source_of_truth_summary=parsed.source_of_truth_summary,
    )
    result_snap = build_guard_result_snapshot(
        decision=result.decision.value,
        drift_risk=result.drift_risk,
        matched_requirement_ids=result.matched_requirement_ids,
        violated_constraints=result.violated_constraints,
        forbidden_change_hits=result.forbidden_change_hits,
        warnings=result.warnings,
        reasons=result.reasons,
        recommended_next_step=result.recommended_next_step,
    )
    record = build_workflow_guard_result_record(
        id=str(_uuid.uuid4()),
        run_id=run.id,
        step_id=step.id,
        project_id=run.project_id or None,
        input_snapshot=input_snap,
        requirement_context_snapshot=ctx_snap,
        result_snapshot=result_snap,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
    )
    saved = create_guard_result(record)
    response = StepSourceOfTruthGuardResponse(
        run_id=run.id,
        step_id=step.id,
        has_requirement_context=not parsed.parse_warnings or "AI_WORKBENCH_REQUIREMENT_CONTEXT block not found" not in parsed.parse_warnings,
        parsed_context=parsed,
        guard_result=result,
        persisted=True,
        guard_result_id=saved.id,
    )
    return response, saved.id


@router.post("/api/runs/{run_id}/steps/{step_id}/patch-draft/guarded-proposal")
async def create_step_patch_draft_guarded_proposal(
    run_id: str,
    step_id: str,
    req: StepPatchDraftGuardedProposalRequest,
) -> StepPatchDraftGuardedProposalResponse:
    """Preflight or explicitly create a guarded proposal from a step patch draft.

    confirm_create_proposal=false is read-only and creates no records.  When
    confirm_create_proposal=true, this endpoint persists a Source of Truth guard
    result and delegates proposal creation to the existing guarded propose-patch
    path.  It never applies patches, runs tests, calls providers, or starts runs.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    step = next((item for item in list_run_steps(run_id) if item.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail="Step not found for this run")

    body = req.model_copy(update={"run_id": run_id, "step_id": step_id})
    context = normalize_development_run_step_context(step.input or "")
    preflight = build_step_patch_draft_proposal_preflight(
        run_id=run_id,
        step=step,
        request=body,
        agent_step_context=context,
    )
    if not body.confirm_create_proposal or preflight.blockers:
        return preflight

    if not run.project_id:
        return preflight.model_copy(update={
            "blockers": preflight.blockers + ["Run has no associated project; guarded proposal creation requires a project."],
            "guard_decision": "preflight_blocked",
            "next_recommended_action": "Associate the run with a project before creating a guarded proposal.",
        })
    project = get_project(run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    file_path, old_text, new_text = _selected_step_patch_fields(body)
    proposed_action = body.operator_note or _patch_draft_text(
        body,
        "patch_intent",
        fallback=f"Create guarded proposal for step '{step.title}'.",
    )
    patch_summary = _patch_draft_text(body, "draft_summary", fallback=proposed_action)

    try:
        guard_response, guard_result_id = _persist_guard_result_for_step_patch(
            run=run,
            step=step,
            proposed_action=proposed_action,
            file_path=file_path,
            patch_summary=patch_summary,
            old_text=old_text,
            new_text=new_text,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist guard result: {exc}") from exc

    guard_decision = guard_response.guard_result.decision.value
    if guard_decision == "blocked":
        return preflight.model_copy(update={
            "guard_result_id": guard_result_id,
            "guard_decision": guard_decision,
            "blockers": preflight.blockers + ["Source of Truth guard blocked this patch draft; proposal was not created."],
            "warnings": preflight.warnings + guard_response.guard_result.warnings,
            "next_recommended_action": guard_response.guard_result.recommended_next_step,
        })

    propose_req = ProposePatchRequest(
        run_id=run_id,
        step_id=step_id,
        agent_id=context.canonical_agent_id,
        operations=[PatchOperation(file_path=file_path, old_text=old_text, new_text=new_text)],
        guard_result_id=guard_result_id,
        guard_warning_acknowledged=guard_decision == "warning",
        no_guard_override=False,
    )
    proposal_result = await run_project_propose_patch(project.id, propose_req)
    proposal_id = proposal_result.get("proposal_id") or proposal_result.get("tool_call_id") or ""

    return StepPatchDraftGuardedProposalResponse(
        run_id=run_id,
        step_id=step_id,
        created=bool(proposal_id),
        proposal_id=proposal_id or None,
        guard_result_id=guard_result_id,
        guard_decision=guard_decision,
        module_awareness=proposal_result.get("module_awareness"),
        module_policy=proposal_result.get("module_policy"),
        patch_review=preflight.patch_review,
        blockers=[],
        warnings=preflight.warnings + guard_response.guard_result.warnings + proposal_result.get("warnings", []),
        safety_notes=[
            "Proposal created only after explicit operator confirmation.",
            "Patch was not applied.",
            "Tests were not run.",
            "Apply still requires the existing explicit confirm=true flow.",
            "No provider call, command execution, or run execution was started.",
        ],
        next_recommended_action="Review the guarded proposal and apply manually only after explicit confirmation.",
        ready_for_apply=bool(proposal_id),
    )


def _build_queue_item(*, run_id: str, step, tool_calls: list, guard_records: list, approvals: list | None = None) -> "OperatorQueueItem | None":
    """Build a single OperatorQueueItem for one step using existing data only.

    Pure analysis — creates no DB records, calls no providers, runs no commands.
    """
    step_approvals: list = approvals or []
    step_calls = tool_calls  # already filtered to this step
    proposal_calls = [tc for tc in step_calls if tc.tool_name == "propose-patch"]
    apply_calls = [tc for tc in step_calls if tc.tool_name == "apply-patch"]
    test_calls = [tc for tc in step_calls if _is_step_test_command(tc)]
    analysis_calls = [tc for tc in step_calls if tc.tool_name == "analyze-command-result"]
    fix_draft_signals = [tc for tc in step_calls if tc.tool_name == "failure-to-fix-draft"]
    dev_context = normalize_development_run_step_context(step.input or "")

    successful_proposals = [tc for tc in proposal_calls if tc.status == "completed"]
    latest_apply = _latest_call([tc for tc in apply_calls if tc.status == "completed"])
    latest_test = _latest_call(test_calls)
    latest_analysis = _latest_call(analysis_calls)

    # Determine test status relative to latest apply
    latest_apply_time = _tool_call_time_value(latest_apply) if latest_apply else None
    latest_test_time = _tool_call_time_value(latest_test) if latest_test else None
    tests_after_apply = bool(latest_apply_time and latest_test_time and latest_test_time >= latest_apply_time)

    test_failed = bool(
        latest_test
        and tests_after_apply
        and (latest_test.returncode not in (None, 0) or _tool_call_output(latest_test).get("timed_out"))
    )
    test_passed = bool(
        latest_test
        and tests_after_apply
        and latest_test.returncode == 0
        and not _tool_call_output(latest_test).get("timed_out")
    )

    active_guards = [r for r in guard_records if not getattr(r, "is_stale", False)]
    latest_guard = active_guards[0] if active_guards else (guard_records[0] if guard_records else None)

    item_id = f"{run_id}:{step.id}"

    if (
        dev_context.source == "intake_confirmed_development_run"
        and str(getattr(step.status, "value", step.status)).lower() == "pending"
        and not dev_context.provider_allowed
        and not proposal_calls
        and not guard_records
    ):
        warnings: list[str] = []
        if not dev_context.requirement_ids:
            warnings.append("No requirement links found in the step context.")
        if not dev_context.module_ids:
            warnings.append("No module links found in the step context.")
        if not dev_context.validation_steps:
            warnings.append("No validation steps found in the step context.")
        if not dev_context.safety_gates:
            warnings.append("No safety gates found in the step context.")
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high" if dev_context.manual_approval_required else "medium",
            status="manual_required" if dev_context.manual_approval_required else "ready",
            action_type="prepare_agent_step",
            title="Prepare agent step context",
            description="Review the intake-origin step context before opening the agent execution dry run.",
            reason=dev_context.next_safe_action,
            destination="agent_step_context",
            can_run_directly=False,
            requires_confirmation=dev_context.manual_approval_required,
            is_destructive=False,
            warnings=warnings,
        )

    stale_guards = [r for r in guard_records if getattr(r, "is_stale", False)]
    if stale_guards and not active_guards:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="medium", status="blocked",
            action_type="resolve_blocker",
            title="Recheck stale guard",
            description="All guard results for this step are stale. Re-run the source-of-truth guard check.",
            reason="Guard results exist but are all stale.",
            destination="source_of_truth_guard",
            can_run_directly=False, requires_confirmation=False, is_destructive=False,
            warnings=["Stale guard: patch context may have changed since last check."],
        )

    # ── Decision tree ──────────────────────────────────────────────────────────

    if latest_guard:
        decision = latest_guard.result_snapshot.decision
        decision_value = decision.value if hasattr(decision, "value") else str(decision)
        if decision_value == "blocked":
            return OperatorQueueItem(
                id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
                priority="high", status="blocked",
                action_type="resolve_blocker",
                title="Resolve blocked guard",
                description="The latest guard result is blocked. Re-run or resolve the source-of-truth guard before continuing.",
                reason="Latest guard result is blocked.",
                destination="source_of_truth_guard",
                guard_result_id=latest_guard.id,
                can_run_directly=False,
                requires_confirmation=False,
                is_destructive=False,
                warnings=["Blocked guard results cannot be used by automation."],
            )

    # GAP-004: Pending approval → surface execute_approval before normal workflow items
    # Check for a pending automation approval that is blocking the loop for this step.
    # This is display-only guidance: it does NOT execute the approval.
    pending_approval = next(
        (
            a for a in step_approvals
            if (a.status.value if hasattr(a.status, "value") else str(a.status)) == "pending"
        ),
        None,
    )
    if pending_approval:
        approval_action = getattr(pending_approval, "action", None) or ""
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high", status="manual_required",
            action_type="execute_approval",
            title="Approve pending automation action",
            description=(
                f"A pending automation approval exists for action '{approval_action}'. "
                "Review and approve it in the Automation Approvals panel to allow the bounded loop to proceed."
            ),
            reason=f"Automation approval '{approval_action}' is pending for step '{step.title}'.",
            destination="approval_panel",
            approval_id=pending_approval.id,
            approval_action_type=approval_action,
            can_run_directly=False,
            requires_confirmation=True,
            is_destructive=False,
            warnings=["This item is display-only. Approving it requires human review in the Automation Approvals panel."],
        )

    # 8. Tests passed → review_success
    if test_passed:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="low", status="done",
            action_type="review_success",
            title="Review success",
            description="Tests passed after the latest apply. Review the output and mark the step complete.",
            reason="Latest test passed after latest apply.",
            destination="patch_lifecycle",
            apply_tool_call_id=latest_apply.id if latest_apply else None,
            test_tool_call_id=latest_test.id if latest_test else None,
            can_run_directly=False, requires_confirmation=False, is_destructive=False,
        )

    # 6/7. Test failed + analysis exists → check if fix draft already prepared
    if test_failed and latest_analysis:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high", status="ready",
            action_type="prepare_fix_draft_manual",
            title="Prepare fix draft from failed tests",
            description="Failed tests have been analyzed. Prepare a fix draft to prefill the patch context before creating a new guarded proposal.",
            reason="Failed tests analyzed; fix draft not yet prepared this cycle.",
            destination="patch_lifecycle",
            apply_tool_call_id=latest_apply.id if latest_apply else None,
            test_tool_call_id=latest_test.id if latest_test else None,
            failed_tool_call_id=latest_test.id if latest_test else None,
            can_run_directly=True,   # prepare_fix_draft_manual is safe/read-only
            requires_confirmation=False,
            is_destructive=False,
            warnings=["Fix draft is read-only context. It does not create a proposal or apply anything."],
        )

    # 5. Test failed → analyze_failed_tests_manual
    if test_failed:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high", status="manual_required",
            action_type="analyze_failed_tests_manual",
            title="Analyze failed tests",
            description="Tests failed after the latest apply. Analyze the failure output manually before preparing a fix.",
            reason=f"Latest test failed with returncode {latest_test.returncode if latest_test else 'unknown'}.",
            destination="failure_analysis",
            apply_tool_call_id=latest_apply.id if latest_apply else None,
            test_tool_call_id=latest_test.id if latest_test else None,
            failed_tool_call_id=latest_test.id if latest_test else None,
            can_run_directly=False, requires_confirmation=False, is_destructive=False,
        )

    # 4. Apply succeeded but no tests yet → run_tests_manual
    if latest_apply and not latest_test_time:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high", status="manual_required",
            action_type="run_tests_manual",
            title="Run tests manually",
            description="A patch was applied. Run the project test command manually to verify the result.",
            reason="Apply succeeded; no test run found after apply.",
            destination="run_command",
            apply_tool_call_id=latest_apply.id if latest_apply else None,
            can_run_directly=False,  # queue stays manual; automation requires explicit allow_safe_commands=True
            requires_confirmation=False,
            is_destructive=False,
            warnings=["Use the Run tests manually button in the Patch-Test Lifecycle panel."],
        )

    # 3. Valid proposal exists but no apply → apply_patch_manual
    if successful_proposals and not latest_apply:
        latest_proposal = _latest_call(successful_proposals)
        guard_id = _tool_call_output(latest_proposal).get("guard_result_id") or \
                   _tool_call_input(latest_proposal).get("guard_result_id")
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="high", status="manual_required",
            action_type="apply_patch_manual",
            title="Apply patch manually",
            description="A guarded patch proposal exists. Apply it manually using confirm=true in the patch form.",
            reason="Valid proposal exists; no apply recorded yet.",
            destination="patch_form",
            guard_result_id=guard_id,
            proposal_tool_call_id=latest_proposal.id if latest_proposal else None,
            can_run_directly=False,
            requires_confirmation=True,  # apply always requires explicit confirm=true
            is_destructive=True,
            warnings=["Apply is destructive. Requires manual confirm=true in the patch form."],
        )

    # 2a. Guard exists but no proposal yet → validate + create
    if latest_guard and not successful_proposals:
        guard_id = getattr(latest_guard, "id", None)
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="medium", status="ready",
            action_type="create_proposal_manual",
            title="Create patch proposal",
            description="A source-of-truth guard result exists. Create a guarded patch proposal manually in the patch form.",
            reason="Guard available; no proposal created yet.",
            destination="patch_form",
            guard_result_id=guard_id,
            can_run_directly=False,
            requires_confirmation=False,
            is_destructive=False,
        )

    # 1. No guard → check_guard
    if not guard_records:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="medium", status="manual_required",
            action_type="check_guard",
            title="Check source-of-truth guard",
            description="No guard result found for this step. Run the source-of-truth guard check before creating a proposal.",
            reason="No guard result exists for this step.",
            destination="source_of_truth_guard",
            can_run_directly=True, requires_confirmation=False, is_destructive=False,
        )

    # Tests exist but not after latest apply → ambiguous
    if latest_apply and latest_test and not tests_after_apply:
        return OperatorQueueItem(
            id=item_id, run_id=run_id, step_id=step.id, step_title=step.title,
            priority="medium", status="manual_required",
            action_type="run_tests_manual",
            title="Run tests again (stale result)",
            description="Test results predate the latest apply. Run tests again to get a current result.",
            reason="Test results are from before the latest apply.",
            destination="run_command",
            apply_tool_call_id=latest_apply.id if latest_apply else None,
            test_tool_call_id=latest_test.id if latest_test else None,
            can_run_directly=False, requires_confirmation=False, is_destructive=False,
            warnings=["Test run predates latest apply. Results may be stale."],
        )

    return None  # No actionable item for this step


# ── Automation Runner Policy ──────────────────────────────────────────────────
#
# Safety-critical constants — do NOT expand without a full policy review.
# v1 never auto-applies, auto-proposes, auto-rolls back, or calls providers.

_AUTOMATION_DIRECT_SAFE_READONLY: frozenset[str] = frozenset({
    "review_success",            # Already done — returns no_action immediately.
    "analyze_failed_tests_manual",  # Calls deterministic _analyze_command only; no DB writes.
    "prepare_fix_draft_manual",  # Builds failure context inline; no DB writes.
})

_AUTOMATION_DIRECT_SAFE_LOW_RISK: frozenset[str] = frozenset({
    "run_tests_manual",          # Safe test command; requires allow_safe_commands=True.
                                 # Uses project profile test_command only; creates one tool_call.
})

_AUTOMATION_MANUAL_REQUIRED: frozenset[str] = frozenset({
    "create_proposal_manual",    # Always requires operator review.
    "apply_patch_manual",        # Destructive; requires confirm=True from operator.
    "check_guard",               # Guard check must be triggered by operator.
    "validate_guard_for_proposal",
})

_AUTOMATION_BLOCKED: frozenset[str] = frozenset({
    "resolve_blocker",           # Stale guard — operator must recheck manually.
})

_AUTOMATION_SAFETY_NOTES: list[str] = [
    "Automation Runner v1 never applies patches, rolls back, runs arbitrary commands, or calls providers.",
    "All destructive and approval-gated actions require explicit operator confirmation.",
    "execute_run and asyncio.create_task are never called by the automation runner.",
]


def _automation_classify(action_type: str) -> str:
    """Return automation policy category for a queue action_type."""
    if action_type in _AUTOMATION_DIRECT_SAFE_READONLY:
        return "direct_safe_readonly"
    if action_type in _AUTOMATION_DIRECT_SAFE_LOW_RISK:
        return "direct_safe_low_risk"
    if action_type in _AUTOMATION_BLOCKED:
        return "blocked"
    return "manual_required"


def _execute_single_automation_action(
    *,
    run_id: str,
    run,
    step,
    item: OperatorQueueItem,
    dry_run: bool,
    allow_safe_commands: bool,
    allow_low_risk_tool_calls: bool,
    all_run_calls: list,
) -> AutomationActionResult:
    """Execute one automation action and return a typed audit result.

    Safety guarantees (invariant):
    - Never calls providers (claude_provider / codex / ollama).
    - Never calls execute_run or asyncio.create_task.
    - Never creates patch proposals or applies patches.
    - Never rolls back patches.
    - run_tests_manual only executes when allow_safe_commands=True AND the command
      is explicitly in the project profile allowlist.
    - All other executable actions are pure read-only (no DB writes).
    """
    action_type = item.action_type
    step_id = step.id
    category = _automation_classify(action_type)

    base_kwargs = dict(
        action_type=action_type,
        step_id=step_id,
        destination=item.destination,
    )

    # ── BLOCKED ───────────────────────────────────────────────────────────────
    if category == "blocked":
        return AutomationActionResult(
            **base_kwargs,
            status="blocked",
            executed=False,
            risk_level="readonly",
            reason=item.reason,
        )

    # ── MANUAL_REQUIRED ───────────────────────────────────────────────────────
    if category == "manual_required":
        return AutomationActionResult(
            **base_kwargs,
            status="manual_required",
            executed=False,
            risk_level="high" if item.is_destructive else "medium",
            reason=item.reason,
        )

    # ── DIRECT_SAFE_LOW_RISK: run_tests_manual ────────────────────────────────
    if category == "direct_safe_low_risk":
        if not allow_safe_commands:
            return AutomationActionResult(
                **base_kwargs,
                status="blocked",
                executed=False,
                risk_level="medium",
                reason=(
                    "allow_safe_commands=False. Set allow_safe_commands=True "
                    "to permit safe test command execution."
                ),
            )
        if not allow_low_risk_tool_calls:
            return AutomationActionResult(
                **base_kwargs,
                status="blocked",
                executed=False,
                risk_level="medium",
                reason="allow_low_risk_tool_calls=False. Safe command ToolCalls are disabled.",
            )
        project = get_project(run.project_id) if run.project_id else None
        if not project:
            return AutomationActionResult(
                **base_kwargs,
                status="blocked",
                executed=False,
                risk_level="medium",
                reason="Run has no project_id; cannot resolve test command.",
            )
        command = (project.test_command or "").strip()
        if not command:
            return AutomationActionResult(
                **base_kwargs,
                status="blocked",
                executed=False,
                risk_level="medium",
                reason="Project test_command is not configured. Set it in the Project Profile.",
            )
        # Verify command is in project allowlist (safety guard)
        allowed: set[str] = set()
        if project.test_command:
            allowed.add(project.test_command.strip())
        for sc in project.safe_commands:
            if sc.strip():
                allowed.add(sc.strip())
        if command not in allowed:
            return AutomationActionResult(
                **base_kwargs,
                status="blocked",
                executed=False,
                risk_level="high",
                reason=f"Command '{command}' is not in project allowlist. Safety guard rejected.",
            )
        if dry_run:
            return AutomationActionResult(
                **base_kwargs,
                status="dry_run",
                executed=False,
                risk_level="low",
                reason=f"dry_run=True. Would execute: {command}",
                result_summary=f"Would run: {command}",
            )
        # Create tool_call record and run the safe command
        input_meta = json.dumps({
            "command_kind": "test",
            "command": command,
            "run_id": run_id,
            "step_id": step_id,
            "automation": True,
        }, ensure_ascii=False)
        started_at_str = datetime.now().isoformat()
        tool_call = create_tool_call(
            run_id=run_id,
            project_id=project.id,
            step_id=step_id,
            tool_name="run-command",
            command=command,
            cwd=project.path,
            status="pending",
            input_json=input_meta,
            risk_level="medium",
            started_at=started_at_str,
        )
        try:
            runner_result = _run_safe_command(project.path, command)
        except Exception as exc:
            _mark_tool_call_failed(tool_call.id, str(exc))
            return AutomationActionResult(
                **base_kwargs,
                status="failed",
                executed=True,
                risk_level="low",
                reason=f"Command execution error: {exc}",
                created_tool_call_id=tool_call.id,
                error=str(exc),
            )
        finished_at_str = datetime.now().isoformat()
        rc = runner_result["returncode"]
        output_meta = json.dumps({
            "returncode": rc,
            "timed_out": runner_result.get("timed_out", False),
            "duration_ms": runner_result.get("duration_ms", 0),
        }, ensure_ascii=False)
        update_tool_call(
            tool_call.id,
            status="completed",
            stdout=runner_result.get("stdout", ""),
            stderr=runner_result.get("stderr", ""),
            returncode=rc,
            output_json=output_meta,
            completed_at=finished_at_str,
            finished_at=finished_at_str,
        )
        return AutomationActionResult(
            **base_kwargs,
            status="executed",
            executed=True,
            risk_level="low",
            reason=f"Safe test command executed. returncode={rc}.",
            created_tool_call_id=tool_call.id,
            result_summary=f"Ran: {command} → returncode={rc}",
        )

    # ── DIRECT_SAFE_READONLY ──────────────────────────────────────────────────

    if action_type == "review_success":
        return AutomationActionResult(
            **base_kwargs,
            status="no_action",
            executed=False,
            risk_level="readonly",
            reason="Tests already passed for this step. Nothing to automate.",
            result_summary="Step is complete: tests passed.",
        )

    step_calls = [tc for tc in all_run_calls if tc.step_id == step_id]
    all_run_commands = [tc for tc in step_calls if tc.tool_name == "run-command"]
    failed_commands = [
        tc for tc in all_run_commands
        if (tc.returncode is not None and tc.returncode != 0)
        or _tool_call_output(tc).get("timed_out") is True
    ]

    if action_type == "analyze_failed_tests_manual":
        if not failed_commands:
            return AutomationActionResult(
                **base_kwargs,
                status="failed",
                executed=False,
                risk_level="readonly",
                reason="No failed run-command found for this step.",
                error="No failed test command to analyze.",
            )
        latest_failed = _latest_call(failed_commands)
        if dry_run:
            return AutomationActionResult(
                **base_kwargs,
                status="dry_run",
                executed=False,
                risk_level="readonly",
                reason=f"dry_run=True. Would analyze tool_call {latest_failed.id}.",
                result_summary=f"Would analyze: {latest_failed.command}",
            )
        # Pure deterministic analysis — no DB writes, no provider calls
        raw = _analyze_command(
            stdout=latest_failed.stdout or "",
            stderr=latest_failed.stderr or latest_failed.error or "",
            returncode=latest_failed.returncode,
            timed_out=bool(_tool_call_output(latest_failed).get("timed_out")),
        )
        return AutomationActionResult(
            **base_kwargs,
            status="executed",
            executed=True,
            risk_level="readonly",
            reason="Deterministic analysis complete (no DB writes, no provider calls).",
            result_summary=f"Analysis: {raw['status']} — {raw['summary'][:120]}",
        )

    if action_type == "prepare_fix_draft_manual":
        if not failed_commands:
            return AutomationActionResult(
                **base_kwargs,
                status="failed",
                executed=False,
                risk_level="readonly",
                reason="No failed run-command found for this step.",
                error="No failed test command for fix draft.",
            )
        latest_failed = _latest_call(failed_commands)
        if dry_run:
            return AutomationActionResult(
                **base_kwargs,
                status="dry_run",
                executed=False,
                risk_level="readonly",
                reason=f"dry_run=True. Would build fix draft from tool_call {latest_failed.id}.",
                result_summary=f"Would build fix draft: {latest_failed.command}",
            )
        # Pure read-only context build — no DB writes
        stdout_excerpt = _short_text(latest_failed.stdout or "", 2000)
        stderr_excerpt = _short_text(latest_failed.stderr or latest_failed.error or "", 2000)
        return AutomationActionResult(
            **base_kwargs,
            status="executed",
            executed=True,
            risk_level="readonly",
            reason="Fix draft context built from failed test output (no DB writes, no provider calls).",
            result_summary=(
                f"Fix draft prepared for step '{step.title}'. "
                f"Failed cmd: {latest_failed.command or 'unknown'}. "
                f"rc={latest_failed.returncode}. "
                f"stdout: {stdout_excerpt[:80]}..."
            ),
        )

    # Fallback: unknown action_type
    return AutomationActionResult(
        **base_kwargs,
        status="manual_required",
        executed=False,
        risk_level="medium",
        reason=f"Unknown action_type '{action_type}' — not handled by Automation Runner v1.",
    )


def _build_queue_for_run(
    run_id: str,
    steps: list,
    all_run_calls: list,
    all_guard_records: list,
    step_id_filter: "str | None" = None,
) -> list[OperatorQueueItem]:
    """Build a sorted operator queue list from current run data."""
    selected = [s for s in steps if not step_id_filter or s.id == step_id_filter]
    # Fetch approvals once for the whole run (GAP-004 fix)
    run_approvals = _list_run_automation_approvals(run_id)
    items: list[OperatorQueueItem] = []
    for step in selected:
        step_approvals = [
            a for a in run_approvals
            if (getattr(a, "command", None) == step.id or not getattr(a, "command", None))
        ]
        item = _build_queue_item(
            run_id=run_id,
            step=step,
            tool_calls=[tc for tc in all_run_calls if tc.step_id == step.id],
            guard_records=[r for r in all_guard_records if r.step_id == step.id],
            approvals=step_approvals,
        )
        if item:
            items.append(item)
    priority_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda i: (priority_order.get(i.priority, 9),
                              next((idx for idx, s in enumerate(selected) if s.id == i.step_id), 999)))
    return items


@router.post("/api/runs/{run_id}/automation/run-next")
async def automation_run_next(
    run_id: str,
    req: AutomationRunRequest,
) -> AutomationRunResponse:
    """Execute the next eligible safe automation action for a run.

    Safety boundaries (invariant for v1):
    - Never auto-applies patches.
    - Never auto-rolls back patches.
    - Never creates patch proposals.
    - Never calls providers or LLM agents.
    - Never calls execute_run or asyncio.create_task.
    - run_tests_manual only executes when allow_safe_commands=True and the command
      is explicitly in the project profile allowlist.
    - Destructive/approval-required actions always return manual_required.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    all_steps = list_run_steps(run_id)
    if req.step_id:
        if not any(s.id == req.step_id for s in all_steps):
            raise HTTPException(status_code=404, detail="Step not found for this run")

    all_run_calls = list_tool_calls_for_run(run_id)
    all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)

    items = _build_queue_for_run(
        run_id=run_id,
        steps=all_steps,
        all_run_calls=all_run_calls,
        all_guard_records=all_guard_records,
        step_id_filter=req.step_id,
    )

    if not items:
        return AutomationRunResponse(
            run_id=run_id,
            dry_run=req.dry_run,
            status="no_action",
            warnings=["No actionable items in operator queue."],
            safety_notes=_AUTOMATION_SAFETY_NOTES,
        )

    item = items[0]
    step = next(s for s in all_steps if s.id == item.step_id)

    result = _execute_single_automation_action(
        run_id=run_id,
        run=run,
        step=step,
        item=item,
        dry_run=req.dry_run,
        allow_safe_commands=req.allow_safe_commands,
        allow_low_risk_tool_calls=req.allow_low_risk_tool_calls,
        all_run_calls=all_run_calls,
    )

    if result.status == "manual_required":
        overall_status = "manual_required"
    elif result.status == "blocked":
        overall_status = "blocked"
    elif result.status == "failed":
        overall_status = "failed"
    elif result.status == "no_action":
        overall_status = "no_action"
    else:
        overall_status = "completed"

    executed_actions = []
    skipped_actions = []
    if result.executed or result.status in ("dry_run", "no_action"):
        executed_actions.append(result)
    else:
        skipped_actions.append(result)

    return AutomationRunResponse(
        run_id=run_id,
        dry_run=req.dry_run,
        status=overall_status,
        executed_actions=executed_actions,
        skipped_actions=skipped_actions,
        next_queue_items=items[1:],
        safety_notes=_AUTOMATION_SAFETY_NOTES,
    )


@router.post("/api/runs/{run_id}/automation/run-safe-loop")
async def automation_run_safe_loop(
    run_id: str,
    req: AutomationSafeLoopRequest,
) -> AutomationRunResponse:
    """Repeatedly execute safe automation actions up to max_actions.

    Stops when:
    - No eligible safe action remains.
    - A manual_required action is encountered (if stop_on_manual_required=True).
    - A blocked action is encountered (if stop_on_blocked=True).
    - max_actions is reached.
    - An action execution fails.

    Safety boundaries: identical to run-next — never auto-applies, auto-proposes,
    auto-rolls back, runs arbitrary commands, or calls providers.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    executed_actions: list[AutomationActionResult] = []
    skipped_actions: list[AutomationActionResult] = []
    final_status = "no_action"
    stop_reason: str | None = None
    iterations_done = 0

    while iterations_done < req.max_actions:
        # Recompute queue before each action (reflects any state changes from
        # previous actions, e.g. a run-command tool_call that was just created).
        all_steps = list_run_steps(run_id)
        all_run_calls = list_tool_calls_for_run(run_id)
        all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)

        items = _build_queue_for_run(
            run_id=run_id,
            steps=all_steps,
            all_run_calls=all_run_calls,
            all_guard_records=all_guard_records,
            step_id_filter=req.step_id,
        )

        if not items:
            stop_reason = "no_items"
            break

        item = items[0]
        category = _automation_classify(item.action_type)

        # Check stop conditions before executing
        if category == "manual_required" and req.stop_on_manual_required:
            result = _execute_single_automation_action(
                run_id=run_id, run=run,
                step=next(s for s in all_steps if s.id == item.step_id),
                item=item,
                dry_run=req.dry_run,
                allow_safe_commands=req.allow_safe_commands,
                allow_low_risk_tool_calls=req.allow_low_risk_tool_calls,
                all_run_calls=all_run_calls,
            )
            skipped_actions.append(result)
            stop_reason = "manual_required"
            break

        if category == "blocked" and req.stop_on_blocked:
            result = _execute_single_automation_action(
                run_id=run_id, run=run,
                step=next(s for s in all_steps if s.id == item.step_id),
                item=item,
                dry_run=req.dry_run,
                allow_safe_commands=req.allow_safe_commands,
                allow_low_risk_tool_calls=req.allow_low_risk_tool_calls,
                all_run_calls=all_run_calls,
            )
            skipped_actions.append(result)
            stop_reason = "blocked"
            break

        step = next(s for s in all_steps if s.id == item.step_id)
        result = _execute_single_automation_action(
            run_id=run_id, run=run, step=step, item=item,
            dry_run=req.dry_run,
            allow_safe_commands=req.allow_safe_commands,
            allow_low_risk_tool_calls=req.allow_low_risk_tool_calls,
            all_run_calls=all_run_calls,
        )

        if result.status in ("manual_required", "blocked"):
            skipped_actions.append(result)
            stop_reason = result.status
            break

        if result.status == "failed":
            executed_actions.append(result)
            stop_reason = "failed"
            break

        executed_actions.append(result)
        iterations_done += 1

        # If this action was a no_action (e.g. review_success) and nothing
        # will change by running again, stop to avoid an infinite no_action loop.
        if result.status == "no_action":
            stop_reason = "no_items"
            break

    else:
        stop_reason = "max_actions"

    # Determine final status
    if stop_reason == "max_actions":
        final_status = "stopped" if executed_actions else "no_action"
    elif stop_reason == "no_items":
        final_status = "completed" if executed_actions else "no_action"
    elif stop_reason in ("manual_required", "blocked", "failed"):
        final_status = stop_reason
    else:
        final_status = "completed" if executed_actions else "no_action"

    # Build final queue state for the response
    final_steps = list_run_steps(run_id)
    final_calls = list_tool_calls_for_run(run_id)
    final_guards = list_guard_results(run_id=run_id, include_stale=True, limit=500)
    next_items = _build_queue_for_run(
        run_id=run_id,
        steps=final_steps,
        all_run_calls=final_calls,
        all_guard_records=final_guards,
        step_id_filter=req.step_id,
    )

    return AutomationRunResponse(
        run_id=run_id,
        dry_run=req.dry_run,
        status=final_status,
        executed_actions=executed_actions,
        skipped_actions=skipped_actions,
        next_queue_items=next_items,
        safety_notes=_AUTOMATION_SAFETY_NOTES,
    )


# ── Approval-Gated Automation v1 ─────────────────────────────────────────────
#
# Safety invariants (enforced for all approval endpoints):
# - Creating an approval never executes the action.
# - Approving never executes the action.
# - Rejecting never executes the action.
# - Execute revalidates policy/guard/queue state before acting.
# - No provider calls, no execute_run, no asyncio.create_task.
# - Blocked guard decisions cannot be overridden by approval.
# - Stale guards cannot be overridden by approval.
# - Arbitrary commands are never accepted.

_APPROVAL_ELIGIBLE_ACTION_TYPES: frozenset[str] = frozenset({
    "apply_patch_manual",     # Destructive; always manual-required.
    "run_tests_manual",       # Safe command; approval allows running even when auto is off.
    "create_proposal_manual", # Operator review; execution deferred to next slice.
    "check_guard",            # Requires operator trigger.
    "validate_guard_for_proposal",
})

_APPROVAL_BLOCKED_ACTION_TYPES: frozenset[str] = frozenset({
    "resolve_blocker",        # Blocked/stale guard — approval cannot override.
})

# Action types that can have approvals created even when they are not currently
# present as a manual_required item in the operator queue.  These are either
# always safe to pre-approve (run_tests_manual, check_guard) or have their
# execution deferred to a later slice (create_proposal_manual,
# validate_guard_for_proposal).  No command is ever read from the approval
# payload — the project profile or guard engine drives execution.
_APPROVAL_CREATE_QUEUE_OPTIONAL: frozenset[str] = frozenset({
    "run_tests_manual",
    "create_proposal_manual",
    "check_guard",
    "validate_guard_for_proposal",
})

_APPROVAL_EXECUTE_SUPPORTED: frozenset[str] = frozenset({
    "apply_patch_manual",
    "run_tests_manual",
})

_APPROVAL_SAFETY_NOTES: list[str] = [
    "Approval does not bypass guard, safe command, or current state revalidation.",
    "Blocked and stale guards cannot be overridden by approval.",
    "Arbitrary commands are never accepted.",
    "No provider execution, no execute_run, no asyncio.create_task.",
]

_APPROVAL_RISK_LEVELS: dict[str, str] = {
    "apply_patch_manual": "high",
    "run_tests_manual": "medium",
    "create_proposal_manual": "medium",
    "check_guard": "low",
    "validate_guard_for_proposal": "low",
}

_APPROVAL_DESTRUCTIVE: frozenset[str] = frozenset({
    "apply_patch_manual",
})


def _approval_meta(desc: str) -> dict:
    """Parse automation approval metadata from description JSON."""
    if not desc:
        return {}
    try:
        parsed = json.loads(desc)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, ValueError):
        return {}


def _is_automation_approval(approval) -> bool:
    """Return True if the approval record belongs to the automation approval system."""
    meta = _approval_meta(approval.description)
    return bool(meta.get("automation"))


def _make_automation_approval_item(approval) -> AutomationApprovalItem:
    """Convert a raw ApprovalRequest row to a typed AutomationApprovalItem."""
    meta = _approval_meta(approval.description)
    action_type = approval.action
    return AutomationApprovalItem(
        id=approval.id,
        run_id=approval.run_id,
        step_id=approval.command or None,
        action_type=action_type,
        status=approval.status if isinstance(approval.status, str) else approval.status.value,
        reason=meta.get("reason", approval.description),
        risk_level=_APPROVAL_RISK_LEVELS.get(action_type, "medium"),
        is_destructive=action_type in _APPROVAL_DESTRUCTIVE,
        created_at=approval.created_at,
        resolved_at=approval.resolved_at,
    )


def _list_run_automation_approvals(run_id: str) -> list:
    """Return all automation approvals for a specific run (filtered in memory)."""
    all_approvals = list_approvals()
    return [
        a for a in all_approvals
        if a.run_id == run_id and _is_automation_approval(a)
    ]


def _get_run_automation_approval(run_id: str, approval_id: str):
    """Return one automation approval if it belongs to the run, else None."""
    approval = get_approval(approval_id)
    if not approval:
        return None
    if approval.run_id != run_id:
        return None
    if not _is_automation_approval(approval):
        return None
    return approval


def _execute_approved_run_tests(
    *,
    run_id: str,
    run,
    step,
    approval_id: str,
    all_run_calls: list,
) -> AutomationApprovalExecuteResponse:
    """Execute run_tests_manual via the existing safe command path."""
    items = _build_queue_for_run(
        run_id=run_id,
        steps=[step],
        all_run_calls=all_run_calls,
        all_guard_records=[],
        step_id_filter=step.id,
    )
    # Find the run_tests_manual item (there may not be one if queue state changed)
    test_item = next((i for i in items if i.action_type == "run_tests_manual"), None)
    if test_item is None:
        # Create a synthetic item to drive the existing dispatcher.
        # All required OperatorQueueItem fields must be populated so that
        # Pydantic validation passes.  No field is read from the approval
        # payload — command comes exclusively from the project profile.
        from src.models import OperatorQueueItem as _OQI
        test_item = _OQI(
            id=f"approval-{approval_id}-run-tests",
            run_id=run_id,
            step_id=step.id,
            step_title=step.title or step.id,
            action_type="run_tests_manual",
            status="pending",
            priority="medium",
            title="Run approved safe tests",
            description="Execute the project-configured safe test command after approval.",
            reason="Executing approved run_tests_manual action.",
            destination="operator-queue",
            is_destructive=False,
            requires_confirmation=False,
        )

    # Reuse existing dispatcher — force allow_safe_commands for approved action
    result = _execute_single_automation_action(
        run_id=run_id,
        run=run,
        step=step,
        item=test_item,
        dry_run=False,
        allow_safe_commands=True,          # approved — safe commands permitted
        allow_low_risk_tool_calls=True,
        all_run_calls=all_run_calls,
    )

    if result.status in ("executed", "dry_run"):
        resolve_approval(approval_id, "executed")
        return AutomationApprovalExecuteResponse(
            approval_id=approval_id,
            run_id=run_id,
            step_id=step.id,
            action_type="run_tests_manual",
            status="executed",
            executed=True,
            result_summary=result.result_summary,
            revalidation_error=None,
            created_tool_call_id=result.created_tool_call_id,
            safety_notes=_APPROVAL_SAFETY_NOTES,
        )
    else:
        return AutomationApprovalExecuteResponse(
            approval_id=approval_id,
            run_id=run_id,
            step_id=step.id,
            action_type="run_tests_manual",
            status=result.status,
            executed=False,
            result_summary=result.reason,
            revalidation_error=result.reason,
            created_tool_call_id=result.created_tool_call_id,
            safety_notes=_APPROVAL_SAFETY_NOTES,
        )


def _execute_approved_apply_patch(
    *,
    run_id: str,
    run,
    step,
    project,
    approval_id: str,
) -> AutomationApprovalExecuteResponse:
    """Execute apply_patch_manual by reconstructing proposal context and revalidating guard."""
    # Find latest propose-patch tool_call for this step
    all_calls = list_tool_calls_for_run(run_id)
    step_calls = [tc for tc in all_calls if tc.step_id == step.id]
    proposal_calls = [tc for tc in step_calls if tc.tool_name == "propose-patch"]

    # Also search project-level calls if run has a project
    if not proposal_calls and run.project_id:
        project_calls = list_tool_calls_for_project(run.project_id, limit=500)
        proposal_calls = [
            tc for tc in project_calls
            if tc.step_id == step.id and tc.tool_name == "propose-patch"
        ]

    if not proposal_calls:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "No proposal found for this step. Revalidation failed.",
                "revalidation_error": "missing_proposal",
            },
        )

    # Use most recent proposal
    proposal_call = sorted(proposal_calls, key=lambda tc: tc.created_at or "", reverse=True)[0]
    proposal_input = _json_obj(proposal_call.input_json)
    raw_ops = proposal_input.get("operations", [])

    if not raw_ops:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Proposal has no operations stored. Revalidation failed.",
                "revalidation_error": "missing_operations",
            },
        )

    try:
        operations = [PatchOperation(**op) if isinstance(op, dict) else op for op in raw_ops]
    except Exception as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Could not reconstruct patch operations: {exc}",
                "revalidation_error": "malformed_operations",
            },
        )

    apply_req = ApplyPatchRequest(
        operations=operations,
        confirm=True,
        proposal_id=proposal_call.id,
        run_id=run_id,
        step_id=step.id,
    )

    # Guard revalidation — raises HTTPException(400/409) on failure
    guard_result_id, guard_revalidated, guard_reasons, guard_warnings, no_guard_override = \
        _validate_apply_guard(project.id, apply_req)

    # Execute apply
    def _apply_op():
        result = apply_project_patch(project.path, apply_req.operations, True)
        git_status = _run_project_git(project, ["status", "--short"])
        git_diff = _run_project_git(project, ["diff", "--stat"])
        return {
            **result,
            "git_status": git_status.get("stdout") or git_status.get("stderr", ""),
            "git_diff_stat": git_diff.get("stdout") or git_diff.get("stderr", ""),
            "applied_from_proposal_id": proposal_call.id,
            "guard_result_id": guard_result_id,
            "guard_revalidated": guard_revalidated,
            "approval_id": approval_id,
        }

    apply_result = _run_logged_read_tool(
        project=project,
        tool_name="apply-patch",
        req=apply_req,
        operation=_apply_op,
        risk_level="high",
    )

    apply_tool_call_id = apply_result.get("tool_call_id") or ""
    if guard_result_id and apply_tool_call_id:
        link_guard_result_to_apply(guard_result_id, apply_tool_call_id)
    if apply_tool_call_id:
        update_tool_call(apply_tool_call_id, output_json=json.dumps(apply_result, ensure_ascii=False))

    # Mark approval executed to prevent re-execution
    resolve_approval(approval_id, "executed")

    files_changed = apply_result.get("files_changed", 0)
    return AutomationApprovalExecuteResponse(
        approval_id=approval_id,
        run_id=run_id,
        step_id=step.id,
        action_type="apply_patch_manual",
        status="executed",
        executed=True,
        result_summary=(
            f"Patch applied. Files changed: {files_changed}. "
            f"Proposal: {proposal_call.id[:8]}. "
            f"Guard revalidated: {guard_revalidated}."
        ),
        revalidation_error=None,
        created_tool_call_id=apply_tool_call_id or None,
        safety_notes=_APPROVAL_SAFETY_NOTES,
    )


# ── Approval endpoints ────────────────────────────────────────────────────────


@router.post("/api/runs/{run_id}/automation/approvals")
async def create_run_automation_approval(
    run_id: str,
    req: AutomationApprovalCreateRequest,
) -> AutomationApprovalItem:
    """Create a pending approval for a manual-required operator queue action.

    Safety: never executes the action. Only creates a pending approval record.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Verify step if provided
    if req.step_id:
        all_steps = list_run_steps(run_id)
        if not any(s.id == req.step_id for s in all_steps):
            raise HTTPException(status_code=404, detail="Step not found for this run")

    # Reject blocked action types (guard override not permitted)
    if req.action_type in _APPROVAL_BLOCKED_ACTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"action_type '{req.action_type}' is blocked and cannot be approved. "
                           "Resolve the underlying guard issue first.",
                "action_type": req.action_type,
            },
        )

    # Verify action is approval-eligible
    if req.action_type not in _APPROVAL_ELIGIBLE_ACTION_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"action_type '{req.action_type}' is not approval-eligible in v1.",
                "eligible_actions": sorted(_APPROVAL_ELIGIBLE_ACTION_TYPES),
            },
        )

    # Verify current queue state — action must exist as a manual_required item for the step
    all_steps = list_run_steps(run_id)
    all_run_calls = list_tool_calls_for_run(run_id)
    all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)

    items = _build_queue_for_run(
        run_id=run_id,
        steps=all_steps,
        all_run_calls=all_run_calls,
        all_guard_records=all_guard_records,
        step_id_filter=req.step_id,
    )

    matching_item = next(
        (i for i in items if i.action_type == req.action_type
         and (not req.step_id or i.step_id == req.step_id)),
        None,
    )

    # Some action types are always approval-eligible regardless of current queue
    # state (e.g. run_tests_manual, create_proposal_manual, check_guard).
    # For all other eligible types the matching queue item must be present and
    # not blocked.
    if matching_item is not None and matching_item.status == "blocked":
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Queue item is blocked (guard decision or missing context). "
                           "Approval cannot override blocked status.",
                "action_type": req.action_type,
                "status": "blocked",
            },
        )
    elif matching_item is None and req.action_type not in _APPROVAL_CREATE_QUEUE_OPTIONAL:
        # No matching item and action is not queue-optional → cannot approve
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"No active manual-required queue item found for action_type "
                           f"'{req.action_type}' on this run/step. Approval cannot be created.",
                "action_type": req.action_type,
                "step_id": req.step_id,
            },
        )

    # Serialize metadata into description
    step_title = ""
    if req.step_id:
        step_obj = next((s for s in all_steps if s.id == req.step_id), None)
        if step_obj:
            step_title = step_obj.title

    meta = {
        "automation": True,
        "reason": req.reason or f"Operator requested approval for {req.action_type}.",
        "risk_level": _APPROVAL_RISK_LEVELS.get(req.action_type, "medium"),
        "is_destructive": req.action_type in _APPROVAL_DESTRUCTIVE,
        "queue_item_id": req.queue_item_id,
        "step_title": step_title,
    }

    approval = create_approval(
        run_id=run_id,
        action=req.action_type,
        command=req.step_id or "",
        description=json.dumps(meta, ensure_ascii=False),
    )
    return _make_automation_approval_item(approval)


@router.get("/api/runs/{run_id}/automation/approvals")
async def list_run_automation_approvals(
    run_id: str,
    step_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> AutomationApprovalListResponse:
    """List automation approvals for a run. Read-only."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    approvals = _list_run_automation_approvals(run_id)
    if step_id:
        approvals = [a for a in approvals if a.command == step_id]
    if status:
        approvals = [
            a for a in approvals
            if (a.status.value if hasattr(a.status, "value") else a.status) == status
        ]

    items = [_make_automation_approval_item(a) for a in approvals]
    return AutomationApprovalListResponse(run_id=run_id, approvals=items)


@router.get("/api/runs/{run_id}/automation/approvals/{approval_id}")
async def get_run_automation_approval_endpoint(
    run_id: str,
    approval_id: str,
) -> AutomationApprovalItem:
    """Get a single automation approval by ID. Verifies run ownership. Read-only."""
    approval = _get_run_automation_approval(run_id, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found for this run")
    return _make_automation_approval_item(approval)


@router.post("/api/runs/{run_id}/automation/approvals/{approval_id}/approve")
async def approve_run_automation_approval(
    run_id: str,
    approval_id: str,
    body: AutomationApprovalApproveRequest | None = None,
) -> AutomationApprovalItem:
    """Mark an automation approval as approved. Does not execute the action."""
    approval = _get_run_automation_approval(run_id, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found for this run")

    status_val = approval.status.value if hasattr(approval.status, "value") else str(approval.status)
    if status_val != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve approval with status '{status_val}'. Only pending approvals can be approved.",
        )

    updated = resolve_approval(approval_id, ApprovalStatus.APPROVED)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update approval")
    return _make_automation_approval_item(updated)


@router.post("/api/runs/{run_id}/automation/approvals/{approval_id}/reject")
async def reject_run_automation_approval(
    run_id: str,
    approval_id: str,
    body: AutomationApprovalRejectRequest | None = None,
) -> AutomationApprovalItem:
    """Mark an automation approval as rejected. Does not execute the action."""
    approval = _get_run_automation_approval(run_id, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found for this run")

    status_val = approval.status.value if hasattr(approval.status, "value") else str(approval.status)
    if status_val not in ("pending",):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject approval with status '{status_val}'. Only pending approvals can be rejected.",
        )

    updated = resolve_approval(approval_id, ApprovalStatus.REJECTED)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update approval")
    return _make_automation_approval_item(updated)


@router.post("/api/runs/{run_id}/automation/approvals/{approval_id}/execute")
async def execute_run_automation_approval(
    run_id: str,
    approval_id: str,
    body: AutomationApprovalExecuteRequest | None = None,
) -> AutomationApprovalExecuteResponse:
    """Execute the action authorized by an approved automation approval.

    Safety invariants:
    - Approval must be approved (not pending/rejected/executed).
    - Action must still be eligible in current queue/guard state.
    - Guard is revalidated before any execution.
    - No providers, no execute_run, no asyncio.create_task.
    - apply_patch_manual: revalidates guard + proposal context before applying.
    - run_tests_manual: verifies command in project allowlist before running.
    - create_proposal_manual: deferred — returns 422 directing operator to proposal UI.
    - All other actions: return 422 (execution not supported in v1).
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    approval = _get_run_automation_approval(run_id, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found for this run")

    status_val = approval.status.value if hasattr(approval.status, "value") else str(approval.status)

    if status_val == "executed":
        raise HTTPException(
            status_code=400,
            detail="Approval has already been executed. Cannot execute again.",
        )
    if status_val == "rejected":
        raise HTTPException(
            status_code=400,
            detail="Rejected approvals cannot be executed.",
        )
    if status_val == "pending":
        raise HTTPException(
            status_code=400,
            detail="Approval is still pending. Approve it first before executing.",
        )
    if status_val != "approved":
        raise HTTPException(
            status_code=400,
            detail=f"Approval status is '{status_val}'. Only approved approvals can be executed.",
        )

    action_type = approval.action
    step_id = approval.command or None

    # Verify step if present
    all_steps = list_run_steps(run_id)
    step = None
    if step_id:
        step = next((s for s in all_steps if s.id == step_id), None)
        if not step:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Step no longer exists. Revalidation failed.",
                    "revalidation_error": "step_not_found",
                },
            )

    # Revalidate current queue state
    all_run_calls = list_tool_calls_for_run(run_id)
    all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)

    items = _build_queue_for_run(
        run_id=run_id,
        steps=all_steps,
        all_run_calls=all_run_calls,
        all_guard_records=all_guard_records,
        step_id_filter=step_id,
    )

    # Check for newly blocked guard
    current_item = next(
        (i for i in items if i.action_type == action_type
         and (not step_id or i.step_id == step_id)),
        None,
    )
    if current_item and current_item.status == "blocked":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Queue item became blocked since approval was created. "
                           "Revalidation failed — resolve guard issue first.",
                "revalidation_error": "item_now_blocked",
            },
        )

    # Guard stale check — must have no stale guards for the step
    if step_id:
        step_guards = [r for r in all_guard_records if r.step_id == step_id]
        active_guards = [r for r in step_guards if not getattr(r, "is_stale", False)]
        stale_guards = [r for r in step_guards if getattr(r, "is_stale", False)]
        if stale_guards and not active_guards and action_type in ("apply_patch_manual",):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Guard result is stale. Re-run the guard check before executing.",
                    "revalidation_error": "guard_stale",
                },
            )

    # Unsupported execute actions
    if action_type not in _APPROVAL_EXECUTE_SUPPORTED:
        raise HTTPException(
            status_code=422,
            detail={
                "message": (
                    f"Execution of '{action_type}' via approval is not supported in v1. "
                    "Use the dedicated UI panel for this action. "
                    "Approval is recorded — no action was executed."
                ),
                "action_type": action_type,
                "approval_id": approval_id,
                "deferred_to_next_slice": True,
            },
        )

    # ── run_tests_manual ──────────────────────────────────────────────────────
    if action_type == "run_tests_manual":
        if step is None:
            raise HTTPException(
                status_code=400,
                detail="run_tests_manual requires a step_id on the approval.",
            )
        return _execute_approved_run_tests(
            run_id=run_id,
            run=run,
            step=step,
            approval_id=approval_id,
            all_run_calls=all_run_calls,
        )

    # ── apply_patch_manual ────────────────────────────────────────────────────
    if action_type == "apply_patch_manual":
        if step is None:
            raise HTTPException(
                status_code=400,
                detail="apply_patch_manual requires a step_id on the approval.",
            )
        if not run.project_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Run has no project_id. Cannot execute apply_patch_manual.",
                    "revalidation_error": "no_project",
                },
            )
        project = get_project(run.project_id)
        if not project:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Project not found. Revalidation failed.",
                    "revalidation_error": "project_not_found",
                },
            )
        return _execute_approved_apply_patch(
            run_id=run_id,
            run=run,
            step=step,
            project=project,
            approval_id=approval_id,
        )

    # Fallback — should not reach here given _APPROVAL_EXECUTE_SUPPORTED check
    raise HTTPException(status_code=500, detail="Unexpected execution path.")


@router.get("/api/runs/{run_id}/agents")
async def get_run_agents(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return list_run_agent_assignments(run_id)


@router.get("/api/runs/{run_id}/model-routes")
async def get_run_model_routes(
    run_id: str,
    scope: str = Query(default="all", pattern="^(agents|steps|all)$"),
):
    """Return persisted model route decisions for a run.

    ``?scope=agents``  — agent-level decisions only (step_id IS NULL).
    ``?scope=steps``   — step-level decisions only (step_id IS NOT NULL).
    ``?scope=all``     — all decisions (default).
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if scope == "agents":
        return list_model_route_decisions_for_agents(run_id)
    if scope == "steps":
        return list_model_route_decisions_for_steps(run_id)
    return get_model_route_decisions_for_run(run_id)


@router.post("/api/runs/{run_id}/model-routes/preview")
async def preview_run_model_routes(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await _build_run_model_route_decisions(run_id, persist=False)


@router.post("/api/runs/{run_id}/model-routes/persist")
async def persist_run_model_routes(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await _build_run_model_route_decisions(run_id, persist=True)


@router.post("/api/runs/{run_id}/steps/model-routes/preview")
async def preview_step_model_routes(run_id: str):
    """Preview (without persisting) step-level model route decisions for a run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await _build_step_model_route_decisions(run_id, persist=False)


@router.post("/api/runs/{run_id}/steps/model-routes/persist")
async def persist_step_model_routes(run_id: str):
    """Compute and persist step-level model route decisions for a run."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await _build_step_model_route_decisions(run_id, persist=True)


@router.post("/api/runs/{run_id}/agents/select")
async def post_select_run_agents(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    project = get_project(run.project_id) if run.project_id else None
    selection = select_agents_for_task(
        prompt=run.prompt,
        project_name=project.name if project else "",
        project_path=run.project_path,
        project_stack=project.stack if project else "",
        package_manager=project.package_manager if project else "",
    )
    assignments = replace_run_agent_assignments(run_id, selection["selected_agents"])
    delete_model_route_decisions_for_run(run_id)
    return {
        **selection,
        "selected_agents": assignments,
        "team_size": len(assignments),
    }


@router.patch("/api/runs/{run_id}/agents/{agent_id}")
async def patch_run_agent(run_id: str, agent_id: str, req: UpdateRunAgentAssignmentRequest):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    assignment = update_run_agent_assignment(
        run_id,
        agent_id,
        **req.model_dump(exclude_unset=True),
    )
    if not assignment:
        raise HTTPException(status_code=404, detail="Run agent assignment not found")
    return assignment


async def _build_run_model_route_decisions(run_id: str, persist: bool) -> ModelRouteDecisionResponse:
    assignments = list_run_agent_assignments(run_id)
    if not assignments:
        return ModelRouteDecisionResponse(
            run_id=run_id,
            count=0,
            persisted=persist,
            decisions=[],
            warnings=["Run has no assigned agents. Select a team before routing models."],
        )

    cfg = get_config()
    provider_mode = _provider_mode_from_config(cfg)
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    available_models = await ollama.list_models(ollama_url)
    privacy_level = str(cfg.get("project_privacy_level", "private") or "private")
    warnings: list[str] = []
    decisions: list[ModelRouteDecision] = []

    for assignment in assignments:
        task_type = infer_task_type_for_agent(assignment.agent_id, assignment.assigned_role)
        try:
            route = route_model(
                ModelRouteRequest(
                    agent_id=assignment.agent_id,
                    task_type=task_type,
                    provider_mode=provider_mode,
                    available_models=available_models,
                    project_privacy_level=privacy_level,
                ),
                cfg,
            )
            decision = model_route_decision_from_result(
                run_id=run_id,
                agent_id=assignment.agent_id,
                task_type=task_type,
                provider_mode=provider_mode,
                route=route,
            )
            if persist:
                decision = upsert_model_route_decision(
                    run_id=decision.run_id,
                    step_id=decision.step_id,
                    agent_id=decision.agent_id,
                    task_type=decision.task_type,
                    model_profile=decision.model_profile,
                    selected_model=decision.selected_model,
                    selected_provider=decision.selected_provider,
                    fallback_model=decision.fallback_model,
                    fallback_provider=decision.fallback_provider,
                    provider_mode=decision.provider_mode.value,
                    reason=decision.reason,
                    confidence=decision.confidence,
                    warnings=decision.warnings,
                )
            decisions.append(decision)
        except Exception as exc:
            warnings.append(f"Failed to route {assignment.agent_id}: {exc}")

    return ModelRouteDecisionResponse(
        run_id=run_id,
        count=len(decisions),
        persisted=persist,
        decisions=decisions,
        warnings=warnings,
    )


async def _build_step_model_route_decisions(run_id: str, persist: bool) -> ModelRouteDecisionResponse:
    """Build model route decisions for every staged step of a run.

    ``persist=False``  — returns the computed decisions without writing to DB.
    ``persist=True``   — upserts each decision keyed on (run_id, step_id).
    """
    steps = list_run_steps(run_id)
    staged_steps = [s for s in steps if s.parent_step_id]  # child steps from staging
    if not staged_steps:
        return ModelRouteDecisionResponse(
            run_id=run_id,
            count=0,
            persisted=persist,
            decisions=[],
            warnings=["Run has no staged steps. Execute the run first to generate steps."],
        )

    cfg = get_config()
    provider_mode = _provider_mode_from_config(cfg)
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    available_models = await ollama.list_models(ollama_url)
    privacy_level = str(cfg.get("project_privacy_level", "private") or "private")
    warnings: list[str] = []
    decisions: list[ModelRouteDecision] = []

    for step in staged_steps:
        agent_id = infer_agent_for_step(step.title, step.input)
        task_type = infer_task_type_for_step(step.title, step.input, agent_id)
        try:
            route = route_model(
                ModelRouteRequest(
                    agent_id=agent_id,
                    task_type=task_type,
                    provider_mode=provider_mode,
                    available_models=available_models,
                    project_privacy_level=privacy_level,
                ),
                cfg,
            )
            decision = model_route_decision_from_result(
                run_id=run_id,
                agent_id=agent_id,
                task_type=task_type,
                provider_mode=provider_mode,
                route=route,
                step_id=step.id,
            )
            if persist:
                decision = upsert_step_route_decision(
                    run_id=decision.run_id,
                    step_id=step.id,
                    agent_id=decision.agent_id,
                    task_type=decision.task_type,
                    model_profile=decision.model_profile,
                    selected_model=decision.selected_model,
                    selected_provider=decision.selected_provider,
                    fallback_model=decision.fallback_model,
                    fallback_provider=decision.fallback_provider,
                    provider_mode=decision.provider_mode.value,
                    reason=decision.reason,
                    confidence=decision.confidence,
                    warnings=decision.warnings,
                )
            decisions.append(decision)
        except Exception as exc:
            warnings.append(f"Failed to route step '{step.title}': {exc}")

    return ModelRouteDecisionResponse(
        run_id=run_id,
        count=len(decisions),
        persisted=persist,
        decisions=decisions,
        warnings=warnings,
    )


def _provider_mode_from_config(cfg: dict) -> ProviderMode:
    try:
        return ProviderMode(str(cfg.get("provider_mode", "local") or "local"))
    except ValueError:
        return ProviderMode.LOCAL


@router.get("/api/runs/{run_id}/artifacts/{artifact_name}")
async def get_run_artifact(run_id: str, artifact_name: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    artifact_path = _resolve_run_artifact_path(run, artifact_name)
    return {
        "name": artifact_name,
        "path": str(artifact_path.relative_to(_run_path(run))),
        "content": artifact_path.read_text(encoding="utf-8"),
    }


@router.post("/api/runs/{run_id}/clarifications")
async def post_clarification_answers(run_id: str, req: ClarificationAnswerRequest):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    answers = req.answers.strip()
    if not answers:
        raise HTTPException(status_code=400, detail="Clarification answers are empty")

    run_path = _run_path(run)
    run_path.mkdir(parents=True, exist_ok=True)
    artifact_name = "clarification-answers.md"
    artifact_path = run_path / artifact_name
    now = datetime.now().isoformat()
    artifact_path.write_text(
        "# Clarification Answers\n\n"
        f"**Answered at:** {now}\n\n"
        f"{answers}\n",
        encoding="utf-8",
    )
    artifacts = list(run.artifacts)
    if artifact_name not in artifacts:
        artifacts.append(artifact_name)

    logs = list(run.logs)
    logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Saved clarification answers")
    update_run(run_id, artifacts=artifacts, logs=logs)

    step = create_run_step(
        run_id=run_id,
        title="Record clarification answers",
        agent_id="user",
        status=RunStatus.COMPLETED.value,
        input="User answered clarification questions.",
        output=f"Saved {artifact_name}",
        started_at=now,
        finished_at=datetime.now().isoformat(),
    )
    return {
        "artifact": artifact_name,
        "content": artifact_path.read_text(encoding="utf-8"),
        "step": step,
    }


@router.post("/api/runs/{run_id}/regenerate-plan")
async def post_regenerate_plan(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    product_spec = _read_optional_run_artifact(run, "product-spec.md")
    questions = _read_optional_run_artifact(run, "clarification-questions.md")
    answers = _read_optional_run_artifact(run, "clarification-answers.md").strip()
    if not answers:
        raise HTTPException(status_code=400, detail="Clarification answers are required")

    now = datetime.now().isoformat()
    step = create_run_step(
        run_id=run_id,
        title="Regenerate plan from clarification answers",
        agent_id="orchestrator",
        status=RunStatus.RUNNING.value,
        input="Use product spec, clarification questions, and saved answers to update plan.md.",
        started_at=now,
    )
    update_run(run_id, current_step_id=step.id)

    cfg = get_config()
    ollama_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")
    ollama_model = cfg.get("ollama", {}).get("default_model", "qwen2.5-coder:7b")
    instructions = load_agent_instructions("orchestrator") or "You are an AI orchestrator."

    try:
        healthy = await ollama.check_health(ollama_url)
        if healthy:
            plan_text = await ollama.chat_completion(
                prompt=_regenerate_plan_prompt(
                    run=run,
                    product_spec=product_spec,
                    questions=questions,
                    answers=answers,
                ),
                system=instructions,
                model=ollama_model,
                base_url=ollama_url,
            )
            source = f"Regenerated with Ollama model {ollama_model}."
        else:
            plan_text = _fallback_regenerated_plan(run.prompt, product_spec, answers)
            source = "Ollama unavailable; generated fallback regenerated plan."

        project = get_project(run.project_id) if run.project_id else None
        project_stack = project.stack if project else ""

        if healthy:
            try:
                architecture_text = await ollama.chat_completion(
                    prompt=build_architecture_prompt(
                        prompt=run.prompt,
                        product_spec=product_spec,
                        plan_text=plan_text,
                        project_id=run.project_id,
                        project_path=run.project_path,
                        project_stack=project_stack,
                    ),
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_url,
                )
                architecture_source = f"Architecture regenerated with Ollama model {ollama_model}."
            except Exception as exc:
                architecture_text = fallback_architecture(run.prompt, product_spec, plan_text, project_stack)
                architecture_source = f"Ollama architecture call failed: {exc}. Generated fallback architecture."
        else:
            architecture_text = fallback_architecture(run.prompt, product_spec, plan_text, project_stack)
            architecture_source = "Ollama unavailable; generated fallback architecture."

        if healthy:
            try:
                task_breakdown = await ollama.chat_completion(
                    prompt=build_task_breakdown_prompt(
                        prompt=run.prompt,
                        product_spec=product_spec,
                        plan_text=plan_text,
                        architecture_text=architecture_text,
                    ),
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_url,
                )
                tasks_source = f"Tasks regenerated with Ollama model {ollama_model}."
            except Exception as exc:
                task_breakdown = fallback_task_breakdown(run.prompt, product_spec, plan_text, architecture_text)
                tasks_source = f"Ollama task breakdown call failed: {exc}. Generated fallback tasks."
        else:
            task_breakdown = fallback_task_breakdown(run.prompt, product_spec, plan_text, architecture_text)
            tasks_source = "Ollama unavailable; generated fallback tasks."

        run_path = _run_path(run)
        plan_path = run_path / "plan.md"
        plan_path.write_text(f"# Execution Plan\n\n{plan_text}\n", encoding="utf-8")
        (run_path / "architecture.md").write_text(f"# Architecture\n\n{architecture_text}\n", encoding="utf-8")
        (run_path / "tasks.md").write_text(f"# Tasks\n\n{task_breakdown}\n", encoding="utf-8")
        # Clear stale step-level route decisions from the previous staging before
        # creating new steps. Agent-level decisions (step_id IS NULL) are preserved.
        delete_step_route_decisions_for_run(run_id)

        staged_steps = stage_executable_task_steps(
            run_id=run_id,
            parent_step_id=step.id,
            task_breakdown=task_breakdown,
            architecture_text=architecture_text,
            project_stack=project_stack,
        )

        # Execute staged steps through Ollama (same guards + limits as execute_run).
        # If Ollama is unavailable the steps remain pending and are visible in the timeline.
        executed_count = 0
        if healthy and staged_steps:
            exec_step = create_run_step(
                run_id=run_id,
                title="Execute staged task steps (regenerated)",
                agent_id="orchestrator",
                status=RunStatus.RUNNING.value,
                input=f"Run {len(staged_steps)} pending steps through Ollama.",
                started_at=datetime.now().isoformat(),
            )
            update_run(run_id, current_step_id=exec_step.id)
            regen_logs: list[str] = list(run.logs)

            def _regen_log(msg: str) -> None:
                regen_logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
                update_run(run_id, logs=regen_logs)

            # Persist step-level route decisions for the new staged steps.
            regen_step_routes: dict = {}
            try:
                regen_step_routes, _regen_route_warnings = await _persist_step_route_decisions(
                    run_id=run_id,
                    staged_steps=staged_steps,
                    provider_mode=cfg.get("provider_mode", "local"),
                    ollama_base_url=ollama_url,
                    log_fn=_regen_log,
                )
                _regen_log(
                    f"Persisted {len(regen_step_routes)}/{len(staged_steps)} "
                    "step-level route decisions for regenerated steps"
                )
            except Exception as exc:
                _regen_log(f"WARNING: Step route decision persistence failed during regen: {exc}")

            executed_count = await _execute_staged_steps(
                staged_steps=staged_steps,
                run_id=run_id,
                instructions=instructions,
                product_spec=product_spec,
                plan_text=plan_text,
                architecture_text=architecture_text,
                task_breakdown=task_breakdown,
                project_stack=project_stack,
                ollama_model=ollama_model,
                ollama_base_url=ollama_url,
                log_fn=_regen_log,
                step_route_decisions=regen_step_routes,
            )
            update_run_step(
                exec_step.id,
                status=RunStatus.COMPLETED.value,
                output=f"Executed {executed_count}/{len(staged_steps)} staged steps.",
                finished_at=datetime.now().isoformat(),
            )
            update_run(run_id, current_step_id="", logs=regen_logs)

        staged_summary = format_staged_steps(staged_steps)
        final_report = _format_regenerated_report(
            run,
            product_spec,
            questions,
            answers,
            plan_text,
            architecture_text,
            task_breakdown,
            staged_summary,
        )
        (run_path / "final-report.md").write_text(final_report, encoding="utf-8")

        artifacts = list(run.artifacts)
        for artifact in ["plan.md", "architecture.md", "tasks.md", "final-report.md"]:
            if artifact not in artifacts:
                artifacts.append(artifact)
        logs = list(run.logs)
        logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            "Regenerated plan, architecture, and tasks from clarification answers"
        )

        update_run(
            run_id,
            plan=plan_text,
            result=final_report,
            artifacts=artifacts,
            logs=logs,
            current_step_id="",
        )
        has_step_failures = staged_steps and executed_count < len(staged_steps)
        completion_note = (
            f"Completed with partial step failures ({executed_count}/{len(staged_steps)} steps succeeded)."
            if has_step_failures
            else "Completed successfully."
        )
        completed_step = update_run_step(
            step.id,
            status=RunStatus.COMPLETED.value,
            output=(
                f"{source}\n"
                f"{architecture_source}\n"
                f"{tasks_source}\n"
                f"Staged {len(staged_steps)} pending execution steps. "
                f"{completion_note}\n"
                "Saved plan.md, architecture.md, tasks.md, and final-report.md"
            ),
            finished_at=datetime.now().isoformat(),
        )
        return {
            "plan": plan_text,
            "architecture": architecture_text,
            "tasks": task_breakdown,
            "staged_steps": staged_steps,
            "executed_count": executed_count,
            "source": source,
            "artifacts": artifacts,
            "step": completed_step,
        }
    except Exception as exc:
        update_run_step(
            step.id,
            status=RunStatus.FAILED.value,
            error=str(exc),
            finished_at=datetime.now().isoformat(),
        )
        update_run(run_id, current_step_id="")
        raise


@router.post("/api/runs/{run_id}/stop")
async def stop_run(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    terminal_statuses = {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.STOPPED}
    if run.status in terminal_statuses:
        return {"status": run.status.value, "run_id": run_id, "task_cancelled": False}

    task_cancelled = cancel_run_task(run_id)
    update_run(run_id, status=RunStatus.STOPPED.value, finished_at=datetime.now().isoformat())
    return {"status": "stopped", "run_id": run_id, "task_cancelled": task_cancelled}


def _run_path(run) -> Path:
    return resolve_runtime_path(run.run_dir, "runs")


def _resolve_run_artifact_path(run, artifact_name: str) -> Path:
    if not artifact_name or "/" in artifact_name or "\\" in artifact_name or artifact_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid artifact name")

    run_path = _run_path(run).resolve(strict=False)
    artifact_path = (run_path / artifact_name).resolve(strict=False)
    if artifact_path != run_path and run_path not in artifact_path.parents:
        raise HTTPException(status_code=400, detail="Artifact path escapes run directory")
    if not artifact_path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    if not artifact_path.is_file():
        raise HTTPException(status_code=400, detail="Artifact is not a file")
    return artifact_path


def _read_optional_run_artifact(run, artifact_name: str) -> str:
    try:
        return _resolve_run_artifact_path(run, artifact_name).read_text(encoding="utf-8")
    except HTTPException as exc:
        if exc.status_code == 404:
            return ""
        raise


def _regenerate_plan_prompt(run, product_spec: str, questions: str, answers: str) -> str:
    return (
        "Regenerate the execution plan for this software development run using the user's clarification answers.\n\n"
        f"## Original Request\n{run.prompt}\n\n"
        "## Project Context\n"
        f"- Project ID: {run.project_id or 'unassigned'}\n"
        f"- Project Path: {run.project_path or 'unassigned'}\n"
        f"- Mode: {run.mode.value if hasattr(run.mode, 'value') else run.mode}\n\n"
        f"## Product Spec\n{product_spec or 'No product spec artifact found.'}\n\n"
        f"## Clarification Questions\n{questions or 'No clarification questions artifact found.'}\n\n"
        f"## User Answers\n{answers}\n\n"
        "## Required Output\n"
        "Return Markdown with these sections:\n"
        "1. Updated Product Understanding\n"
        "2. Implementation Phases\n"
        "3. Agent Roles Needed\n"
        "4. Files likely to change\n"
        "5. Safe Commands to Run\n"
        "6. Risks and Required Approvals\n"
        "7. Acceptance Criteria\n"
        "Keep it concrete and ready for execution by an AI software studio."
    )


def _fallback_regenerated_plan(prompt: str, product_spec: str, answers: str) -> str:
    return (
        "## Regenerated Plan (Fallback)\n\n"
        f"**Original request:** {prompt}\n\n"
        "### Updated Product Understanding\n\n"
        "The plan has been updated using the saved clarification answers. "
        "Ollama was unavailable, so this fallback keeps the scope conservative.\n\n"
        "### Clarification Answers\n\n"
        f"{answers}\n\n"
        "### Product Spec Context\n\n"
        f"{product_spec or 'No product spec artifact was available.'}\n\n"
        "### Implementation Phases\n\n"
        "1. Confirm scope and acceptance criteria from the clarification answers.\n"
        "2. Review the selected project structure and stack.\n"
        "3. Produce an architecture and task breakdown before editing files.\n"
        "4. Implement the smallest useful vertical slice.\n"
        "5. Run configured safe tests/build commands.\n"
        "6. Record tool calls, results, changed files, and remaining risks.\n\n"
        "### Agent Roles Needed\n\n"
        "- orchestrator\n"
        "- repo-analyst\n"
        "- backend or frontend specialist depending on project stack\n"
        "- qa\n"
        "- security reviewer\n\n"
        "### Risks and Required Approvals\n\n"
        "- Any file writes outside the selected project path must be blocked.\n"
        "- Package installs, secret changes, destructive commands, and git push require approval.\n\n"
        "### Acceptance Criteria\n\n"
        "- The requested product behavior is visible and testable.\n"
        "- Safe tests/builds pass or failures are clearly reported.\n"
        "- A final report explains implementation decisions and remaining work.\n"
    )


def _format_regenerated_report(
    run,
    product_spec: str,
    questions: str,
    answers: str,
    plan_text: str,
    architecture_text: str,
    task_breakdown: str,
    staged_summary: str,
) -> str:
    return (
        "# Run Report\n\n"
        f"**Run ID:** {run.id}\n"
        f"**Mode:** {run.mode.value if hasattr(run.mode, 'value') else run.mode}\n"
        f"**Status:** {run.status.value if hasattr(run.status, 'value') else run.status}\n"
        f"**Updated at:** {datetime.now().isoformat()}\n\n"
        "## Project\n"
        f"- **Project ID:** {run.project_id or 'unassigned'}\n"
        f"- **Project Path:** {run.project_path or 'unassigned'}\n\n"
        f"## Input\n{run.prompt}\n\n"
        f"## Product Spec\n{product_spec or 'No product spec artifact found.'}\n\n"
        f"## Clarification Questions\n{questions or 'No clarification questions artifact found.'}\n\n"
        f"## Clarification Answers\n{answers}\n\n"
        f"## Regenerated Plan\n{plan_text}\n\n"
        f"## Architecture\n{architecture_text}\n\n"
        f"## Tasks\n{task_breakdown}\n\n"
        f"## Executable Task Steps\n{staged_summary}\n\n"
        "## Artifacts\n"
        "- `input.md`\n"
        "- `product-spec.md`\n"
        "- `clarification-questions.md`\n"
        "- `clarification-answers.md`\n"
        "- `plan.md`\n"
        "- `architecture.md`\n"
        "- `tasks.md`\n"
        "- `final-report.md`\n"
    )


# ── Local Tools ──────────────────────────────────────────────────────────────

@router.get("/api/workspace/status")
async def workspace_status():
    """Return a compact git workspace status for the dashboard."""
    return _workspace_status(PROJECT_ROOT)


@router.get("/api/projects/{project_id}/workspace/status")
async def project_workspace_status(project_id: str):
    project = _get_project_or_404(project_id)
    return _workspace_status(Path(project.path))


@router.post("/api/projects/{project_id}/tools/run-tests")
async def run_project_tests(project_id: str):
    project = _get_project_or_404(project_id)
    return _run_project_command(project, project.test_command, "test")


@router.post("/api/projects/{project_id}/tools/run-build")
async def run_project_build(project_id: str):
    project = _get_project_or_404(project_id)
    return _run_project_command(project, project.build_command, "build")


@router.post("/api/projects/{project_id}/tools/run-command")
async def run_project_command_endpoint(
    project_id: str,
    req: RunProjectCommandRequest,
) -> RunProjectCommandResponse:
    """Run a project-profile command (test/build/lint/typecheck) safely.

    Only commands from the Project Profile allowlist are executed:
    - test → project.test_command
    - build → project.build_command
    - lint / typecheck → matched from project.safe_commands by keyword

    The command is run with shell=False, cwd=project.path, LC_ALL=C,
    stdout/stderr capped at 100 000 chars. A ToolCall record is created
    and linked to the supplied run_id / step_id / project_id.
    """
    project = _get_project_or_404(project_id)

    kind = req.command_kind

    # Resolve the command from the project profile
    if kind == ProjectCommandKind.TEST:
        command = (project.test_command or "").strip()
        if not command:
            raise HTTPException(
                status_code=400,
                detail="Project test_command is not configured. Set it in the Project Profile.",
            )
    elif kind == ProjectCommandKind.BUILD:
        command = (project.build_command or "").strip()
        if not command:
            raise HTTPException(
                status_code=400,
                detail="Project build_command is not configured. Set it in the Project Profile.",
            )
    else:
        # lint or typecheck: search safe_commands by keyword
        command = find_safe_command_for_kind(kind.value, project.safe_commands) or ""
        if not command:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"No {kind.value} command found in project safe_commands. "
                    f"Add a matching command (e.g. 'ruff check .' for lint, 'npx tsc --noEmit' for typecheck)."
                ),
            )

    # Verify the resolved command is allowed by the project profile
    allowed = set()
    if project.test_command:
        allowed.add(project.test_command.strip())
    if project.build_command:
        allowed.add(project.build_command.strip())
    for sc in project.safe_commands:
        if sc.strip():
            allowed.add(sc.strip())

    if command not in allowed:
        raise HTTPException(
            status_code=403,
            detail="Resolved command is not in the project allowlist. This is a safety guard.",
        )

    # Create a ToolCall record before running
    input_meta = json.dumps({
        "command_kind": kind.value,
        "command": command,
        "run_id": req.run_id,
        "step_id": req.step_id,
        "agent_id": req.agent_id,
    }, ensure_ascii=False)
    started_at_str = datetime.now().isoformat()
    tool_call = create_tool_call(
        run_id=req.run_id or f"project:{project.id}",
        project_id=project.id,
        step_id=req.step_id,
        tool_name="run-command",
        command=command,
        cwd=project.path,
        status="pending",
        input_json=input_meta,
        risk_level="medium",
        started_at=started_at_str,
    )

    # Execute
    try:
        runner_result = _run_safe_command(
            project.path,
            command,
            timeout_seconds=req.timeout_seconds,
        )
    except ValueError as exc:
        _mark_tool_call_failed(tool_call.id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _mark_tool_call_failed(tool_call.id, str(exc))
        raise HTTPException(status_code=500, detail=f"Command runner error: {exc}") from exc

    # Update ToolCall — non-zero returncode is still "completed"
    finished_at_str = datetime.now().isoformat()
    output_meta = json.dumps({
        "returncode": runner_result["returncode"],
        "timed_out": runner_result["timed_out"],
        "duration_ms": runner_result["duration_ms"],
    }, ensure_ascii=False)
    update_tool_call(
        tool_call.id,
        status="completed",
        stdout=runner_result["stdout"],
        stderr=runner_result["stderr"],
        returncode=runner_result["returncode"],
        output_json=output_meta,
        completed_at=finished_at_str,
        finished_at=finished_at_str,
    )

    return RunProjectCommandResponse(
        command_kind=kind.value,
        command=runner_result["command"],
        cwd=runner_result["cwd"],
        returncode=runner_result["returncode"],
        stdout=runner_result["stdout"],
        stderr=runner_result["stderr"],
        duration_ms=runner_result["duration_ms"],
        timed_out=runner_result["timed_out"],
        tool_call_id=tool_call.id,
    )


@router.post("/api/projects/{project_id}/tools/analyze-command-result")
async def analyze_project_command_result(
    project_id: str,
    req: CommandAnalysisRequest,
) -> CommandAnalysisResponse:
    """Heuristic analysis of a previous run-command output.

    Accepts either a tool_call_id (looks up the stored stdout/stderr) or
    inline stdout/stderr/returncode fields. No LLM — pure pattern matching.
    Creates a low-risk ToolCall audit record and returns CommandAnalysisResponse.
    """
    project = _get_project_or_404(project_id)

    stdout = req.stdout
    stderr = req.stderr
    returncode = req.returncode
    timed_out = False
    source_tc_id = req.tool_call_id

    # Resolve from stored tool_call if id provided
    if req.tool_call_id:
        all_calls = list_tool_calls_for_project(project_id, limit=200)
        tc = next((c for c in all_calls if c.id == req.tool_call_id), None)
        if tc is None:
            raise HTTPException(
                status_code=404,
                detail=f"tool_call '{req.tool_call_id}' not found for project '{project_id}'",
            )
        stdout = tc.stdout or req.stdout
        stderr = tc.stderr or req.stderr
        if returncode is None:
            returncode = tc.returncode
        # Check timed_out from output_json if present
        if tc.output_json:
            try:
                meta = json.loads(tc.output_json)
                timed_out = bool(meta.get("timed_out", False))
            except (json.JSONDecodeError, AttributeError):
                pass

    # Create audit tool_call before analysis
    input_meta = json.dumps({
        "source_tool_call_id": source_tc_id,
        "command_kind": req.command_kind,
        "run_id": req.run_id,
        "step_id": req.step_id,
        "agent_id": req.agent_id,
        "returncode": returncode,
    }, ensure_ascii=False)
    started_at_str = datetime.now().isoformat()
    audit_tc = create_tool_call(
        run_id=req.run_id or f"project:{project.id}",
        project_id=project.id,
        step_id=req.step_id,
        tool_name="analyze-command-result",
        status="pending",
        input_json=input_meta,
        risk_level="low",
        started_at=started_at_str,
    )

    try:
        raw = _analyze_command(
            stdout=stdout,
            stderr=stderr,
            returncode=returncode,
            timed_out=timed_out,
            command_kind=req.command_kind,
        )
    except Exception as exc:
        _mark_tool_call_failed(audit_tc.id, str(exc))
        raise HTTPException(status_code=500, detail=f"Analysis error: {exc}") from exc

    finished_at_str = datetime.now().isoformat()
    output_meta = json.dumps({
        "status": raw["status"],
        "issue_count": len(raw["issues"]),
        "can_create_fix_proposal": raw["can_create_fix_proposal"],
    }, ensure_ascii=False)
    update_tool_call(
        audit_tc.id,
        status="completed",
        output_json=output_meta,
        completed_at=finished_at_str,
        finished_at=finished_at_str,
    )

    return CommandAnalysisResponse(
        status=raw["status"],
        summary=raw["summary"],
        issues=[CommandIssue(**i) for i in raw["issues"]],
        suggested_next_actions=raw["suggested_next_actions"],
        can_create_fix_proposal=raw["can_create_fix_proposal"],
        source_tool_call_id=source_tc_id,
    )


@router.post("/api/projects/{project_id}/tools/list-files")
async def run_project_list_files(project_id: str, req: ListFilesRequest | None = None):
    project = _get_project_or_404(project_id)
    body = req or ListFilesRequest()
    return _run_logged_read_tool(
        project=project,
        tool_name="list_files",
        req=body,
        operation=lambda: project_list_files(project.path, path=body.path, max_files=body.max_files),
    )


@router.post("/api/projects/{project_id}/tools/read-file")
async def run_project_read_file(project_id: str, req: ReadFileRequest):
    project = _get_project_or_404(project_id)
    return _run_logged_read_tool(
        project=project,
        tool_name="read_file",
        req=req,
        operation=lambda: project_read_file(project.path, path=req.path, max_chars=req.max_chars),
    )


@router.post("/api/projects/{project_id}/tools/search-code")
async def run_project_search_code(project_id: str, req: SearchCodeRequest):
    project = _get_project_or_404(project_id)
    return _run_logged_read_tool(
        project=project,
        tool_name="search_code",
        req=req,
        operation=lambda: project_search_code(
            project.path,
            query=req.query,
            path=req.path,
            max_results=req.max_results,
        ),
    )


def _first_patch_operation_payload(req: ProposePatchRequest) -> dict:
    """Build the proposal payload shape used by guard-result validation."""

    operation = req.operations[0] if req.operations else None
    return {
        "file_path": operation.file_path if operation else None,
        "old_text": operation.old_text if operation else None,
        "new_text": operation.new_text if operation else None,
    }


def _validate_propose_patch_guard(req: ProposePatchRequest) -> tuple[str | None, bool | None, list[str], list[str]]:
    """Validate guard_result_id/no_guard_override before creating proposal tool_call.

    Returns `(guard_result_id, valid, reasons, warnings)`.
    Raises HTTPException for blocking policy failures.
    """

    reasons: list[str] = []
    warnings: list[str] = []
    step_linked = False
    if req.run_id and req.step_id:
        run = get_run(req.run_id)
        if run:
            step_linked = any(step.id == req.step_id for step in list_run_steps(req.run_id))

    if req.guard_result_id:
        if not req.run_id or not req.step_id:
            raise HTTPException(
                status_code=400,
                detail="guard_result_id requires run_id and step_id.",
            )
        run = get_run(req.run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found for guard_result_id.")
        step = next((item for item in list_run_steps(req.run_id) if item.id == req.step_id), None)
        if not step:
            raise HTTPException(status_code=404, detail="Run step not found for guard_result_id.")

        record = get_guard_result(req.guard_result_id)
        if not record:
            raise HTTPException(status_code=404, detail="Guard result not found.")
        if record.run_id != req.run_id:
            raise HTTPException(status_code=400, detail="Guard result does not belong to this run.")
        if record.step_id != req.step_id:
            raise HTTPException(status_code=400, detail="Guard result does not belong to this step.")

        payload = _first_patch_operation_payload(req)
        comparison = compare_guard_input_to_patch_payload(
            record,
            proposed_action=record.input_snapshot.proposed_action,
            file_path=payload["file_path"],
            patch_summary=record.input_snapshot.patch_summary,
            old_text=payload["old_text"],
            new_text=payload["new_text"],
        )
        decision_val = (
            record.result_snapshot.decision.value
            if hasattr(record.result_snapshot.decision, "value")
            else str(record.result_snapshot.decision)
        )

        if comparison.is_stale:
            reasons.append("Guard result is stale relative to the proposed patch payload.")
            reasons.extend([reason.value for reason in comparison.stale_reasons])
        if decision_val == "blocked":
            reasons.append("Blocked guard result cannot authorize proposal creation.")
        if decision_val == "warning" and not req.guard_warning_acknowledged:
            reasons.append("Warning guard requires explicit acknowledgement before proposal creation.")
        if req.no_guard_override and decision_val == "blocked":
            reasons.append("no_guard_override does not override a blocked guard result.")
        if req.no_guard_override:
            warnings.append("No-guard override was supplied but selected guard validation still controls this proposal.")

        if reasons:
            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Guard result validation failed for patch proposal.",
                    "guard_result_id": req.guard_result_id,
                    "reasons": reasons,
                    "warnings": warnings,
                },
            )
        return req.guard_result_id, True, reasons, warnings

    if step_linked and not req.no_guard_override:
        raise HTTPException(
            status_code=400,
            detail=(
                "Step-linked patch proposals require a valid guard_result_id "
                "or explicit no_guard_override=true."
            ),
        )
    if step_linked and req.no_guard_override:
        warnings.append("Patch proposal created with explicit no-guard override.")
        return None, True, reasons, warnings

    return None, None, reasons, warnings


@router.post("/api/projects/{project_id}/tools/propose-patch")
async def run_project_propose_patch(project_id: str, req: ProposePatchRequest):
    project = _get_project_or_404(project_id)
    guard_result_id, guard_valid, guard_reasons, guard_warnings = _validate_propose_patch_guard(req)
    result = _run_logged_read_tool(
        project=project,
        tool_name="propose-patch",
        req=req,
        operation=lambda: propose_project_patch(project.path, req.operations),
        risk_level="medium",
    )
    proposal_id = result.get("proposal_id") or result.get("tool_call_id") or ""
    if guard_result_id and proposal_id:
        link_guard_result_to_proposal(guard_result_id, proposal_id)
    result["guard_result_id"] = guard_result_id
    result["guard_validation_valid"] = guard_valid
    result["guard_validation_reasons"] = guard_reasons
    result["guard_validation_warnings"] = guard_warnings
    result["no_guard_override"] = bool(req.no_guard_override and not guard_result_id)
    proposed_files = [operation.file_path for operation in req.operations if operation.file_path]
    step_input = ""
    step_title = ""
    requirement_ids: list[str] = []
    if req.run_id and req.step_id:
        step = next((item for item in list_run_steps(req.run_id) if item.id == req.step_id), None)
        if step:
            step_input = step.input or ""
            step_title = step.title or ""
            parsed = parse_run_step_requirement_context(step_input)
            requirement_ids = parsed.requirement_ids
    module_awareness = _build_patch_proposal_module_awareness(
        project.id,
        proposed_files,
        step_input=step_input,
        step_title=step_title,
        requirement_ids=requirement_ids,
    )
    module_policy = _evaluate_module_aware_guard_policy(
        module_awareness,
        proposed_files,
        has_guard_result=bool(guard_result_id),
        no_guard_override=bool(req.no_guard_override and not guard_result_id),
    )
    result["module_awareness"] = module_awareness.model_dump(mode="json")
    result["module_policy"] = module_policy.model_dump(mode="json")
    if proposal_id:
        update_tool_call(
            proposal_id,
            output_json=json.dumps(result, ensure_ascii=False),
        )
    return result


def _json_obj(raw: str) -> dict:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _proposal_call_for_apply(project_id: str, proposal_id: str):
    if not proposal_id:
        return None
    return next(
        (
            call for call in list_tool_calls_for_project(project_id, limit=500)
            if call.id == proposal_id and call.tool_name == "propose-patch"
        ),
        None,
    )


def _validate_apply_guard(project_id: str, req: ApplyPatchRequest) -> tuple[str | None, bool | None, list[str], list[str], bool]:
    """Revalidate linked guard result before manual apply-patch execution."""

    if not req.proposal_id:
        return None, None, [], [], False

    proposal_call = _proposal_call_for_apply(project_id, req.proposal_id)
    if not proposal_call:
        return None, None, [], [], False

    proposal_input = _json_obj(proposal_call.input_json)
    proposal_output = _json_obj(proposal_call.output_json)
    linked = list_guard_results(proposal_tool_call_id=req.proposal_id, include_stale=True, limit=2)
    claimed_guard_result_id = proposal_output.get("guard_result_id") or proposal_input.get("guard_result_id")
    guard_result_id = claimed_guard_result_id or (linked[0].id if linked else None)
    no_guard_override = bool(proposal_output.get("no_guard_override") or proposal_input.get("no_guard_override"))

    if not guard_result_id:
        if no_guard_override:
            return None, False, [], ["Applied from proposal created with explicit no-guard override."], True
        return None, None, [], [], False

    record = get_guard_result(str(guard_result_id))
    if not record:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Guard revalidation failed before apply.",
                "guard_result_id": guard_result_id,
                "reasons": ["Linked guard result could not be found."],
            },
        )

    reasons: list[str] = []
    warnings: list[str] = []
    if req.run_id and record.run_id != req.run_id:
        reasons.append("Guard result does not belong to this run.")
    if req.step_id and record.step_id != req.step_id:
        reasons.append("Guard result does not belong to this step.")
    if record.proposal_tool_call_id and record.proposal_tool_call_id != req.proposal_id:
        reasons.append("Guard result is linked to a different proposal.")

    payload = _first_patch_operation_payload(req)
    comparison = compare_guard_input_to_patch_payload(
        record,
        proposed_action=record.input_snapshot.proposed_action,
        file_path=payload["file_path"],
        patch_summary=record.input_snapshot.patch_summary,
        old_text=payload["old_text"],
        new_text=payload["new_text"],
    )
    if comparison.is_stale:
        reasons.append("Guard result is stale relative to the apply patch payload.")
        reasons.extend([reason.value for reason in comparison.stale_reasons])

    decision_val = (
        record.result_snapshot.decision.value
        if hasattr(record.result_snapshot.decision, "value")
        else str(record.result_snapshot.decision)
    )
    warning_acknowledged = bool(
        proposal_output.get("guard_warning_acknowledged")
        or proposal_input.get("guard_warning_acknowledged")
    )
    if decision_val == "blocked":
        reasons.append("Blocked guard result cannot authorize patch apply.")
    if decision_val == "warning" and not warning_acknowledged:
        reasons.append("Warning guard requires acknowledgement before patch apply.")

    if reasons:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Guard revalidation failed before apply.",
                "guard_result_id": guard_result_id,
                "reasons": reasons,
                "warnings": warnings,
            },
        )

    return str(guard_result_id), True, reasons, warnings, False


@router.post("/api/projects/{project_id}/tools/apply-patch")
async def run_project_apply_patch(project_id: str, req: ApplyPatchRequest):
    project = _get_project_or_404(project_id)
    guard_result_id, guard_revalidated, guard_reasons, guard_warnings, no_guard_override = _validate_apply_guard(project_id, req)

    def apply_with_git_snapshot():
        result = apply_project_patch(project.path, req.operations, req.confirm)
        status = _run_project_git(project, ["status", "--short"])
        diff_stat = _run_project_git(project, ["diff", "--stat"])
        return {
            **result,
            "git_status": status["stdout"] or status["stderr"],
            "git_diff_stat": diff_stat["stdout"] or diff_stat["stderr"],
            "applied_from_proposal_id": req.proposal_id,
            "guard_result_id": guard_result_id,
            "guard_revalidated": guard_revalidated,
            "guard_revalidation_reasons": guard_reasons,
            "guard_revalidation_warnings": guard_warnings,
            "no_guard_override": no_guard_override,
        }

    result = _run_logged_read_tool(
        project=project,
        tool_name="apply-patch",
        req=req,
        operation=apply_with_git_snapshot,
        risk_level="high",
    )
    apply_tool_call_id = result.get("tool_call_id") or ""
    if guard_result_id and apply_tool_call_id:
        link_guard_result_to_apply(guard_result_id, apply_tool_call_id)
    if apply_tool_call_id:
        update_tool_call(
            apply_tool_call_id,
            output_json=json.dumps(result, ensure_ascii=False),
        )
    return result


@router.post("/api/projects/{project_id}/tools/rollback-patch")
async def rollback_project_patch_endpoint(
    project_id: str,
    req: RollbackPatchRequest,
) -> RollbackPatchResponse:
    """Revert files from a previous apply-patch using stored rollback metadata.

    - Requires confirm=true.
    - Reads rollback_data from the apply-patch tool_call's output_json.
    - Skips files that have been modified after the apply (conflict detection).
    - Logs a high-risk rollback-patch tool_call.
    - No shell commands executed.
    """
    project = _get_project_or_404(project_id)

    # Verify tool_call belongs to this project and is an apply-patch
    all_calls = list_tool_calls_for_project(project_id, limit=500)
    source_tc = next((c for c in all_calls if c.id == req.tool_call_id), None)
    if source_tc is None:
        raise HTTPException(
            status_code=404,
            detail=f"tool_call '{req.tool_call_id}' not found for project '{project_id}'",
        )
    if source_tc.tool_name != "apply-patch":
        raise HTTPException(
            status_code=400,
            detail=f"Rollback only supported for apply-patch tool calls, got '{source_tc.tool_name}'",
        )

    # Parse rollback_data from stored output_json
    rollback_data: list[dict] = []
    if source_tc.output_json:
        try:
            out = json.loads(source_tc.output_json)
            rollback_data = out.get("rollback_data", [])
        except (json.JSONDecodeError, AttributeError):
            pass

    if not rollback_data:
        raise HTTPException(
            status_code=400,
            detail="No rollback metadata found for this apply-patch tool call. "
                   "Only patches applied after rollback support was introduced can be reverted.",
        )

    # Create audit tool_call (logged before execution)
    input_meta = json.dumps({
        "source_tool_call_id": req.tool_call_id,
        "confirm": req.confirm,
        "run_id": req.run_id,
        "step_id": req.step_id,
        "agent_id": req.agent_id,
    }, ensure_ascii=False)
    started_at = datetime.now().isoformat()
    rollback_tc = create_tool_call(
        run_id=req.run_id or f"project:{project.id}",
        project_id=project.id,
        step_id=req.step_id,
        tool_name="rollback-patch",
        cwd=project.path,
        status="pending",
        input_json=input_meta,
        risk_level="high",
        started_at=started_at,
    )

    try:
        raw = _rollback_patch(project.path, rollback_data, req.confirm)
        git_status = _run_project_git(project, ["status", "--short"])
        git_diff = _run_project_git(project, ["diff", "--stat"])
        result = {
            **raw,
            "git_status": git_status["stdout"] or git_status["stderr"],
            "git_diff_stat": git_diff["stdout"] or git_diff["stderr"],
            "tool_call_id": rollback_tc.id,
        }
        completed_at = datetime.now().isoformat()
        update_tool_call(
            rollback_tc.id,
            status="completed",
            output_json=json.dumps({
                "rolled_back_files": raw["rolled_back_files"],
                "skipped_files": raw["skipped_files"],
                "warnings": raw["warnings"],
                "summary": raw["summary"],
                "source_tool_call_id": req.tool_call_id,
            }, ensure_ascii=False),
            completed_at=completed_at,
            finished_at=completed_at,
        )
        return RollbackPatchResponse(
            rolled_back_files=[RolledBackFile(**f) for f in raw["rolled_back_files"]],
            skipped_files=[RolledBackFile(**f) for f in raw["skipped_files"]],
            warnings=raw["warnings"],
            git_status=result["git_status"],
            git_diff_stat=result["git_diff_stat"],
            tool_call_id=rollback_tc.id,
        )
    except PermissionError as exc:
        _mark_tool_call_failed(rollback_tc.id, str(exc))
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _mark_tool_call_failed(rollback_tc.id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _mark_tool_call_failed(rollback_tc.id, str(exc))
        raise HTTPException(status_code=500, detail=f"Rollback failed: {exc}") from exc


@router.post("/api/projects/{project_id}/tools/review-patch")
async def review_project_patch_endpoint(
    project_id: str,
    req: PatchReviewRequest,
) -> PatchReviewResponse:
    """Review patch operations for safety issues before creating a proposal or applying.

    This endpoint is read-only:
    - Does NOT create tool_calls.
    - Does NOT modify files.
    - Does NOT create proposals.
    - Does NOT apply patches.
    """
    project = _get_project_or_404(project_id)
    ops = [PatchReviewOperation(
        file_path=op.file_path,
        old_text=op.old_text,
        new_text=op.new_text,
    ) for op in req.operations]
    return review_patch_operations(project.path, ops)


@router.get("/api/projects/{project_id}/git/status")
async def get_project_git_status(project_id: str):
    project = _get_project_or_404(project_id)
    result = _run_project_git(project, ["status", "--short"])
    lines = [line for line in result["stdout"].splitlines() if line.strip()]
    return {
        "project_id": project.id,
        "project_path": project.path,
        "command": ["git", "status", "--short"],
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "changed_files": [_parse_git_status_line(line) for line in lines],
        "clean": result["returncode"] == 0 and not lines,
    }


@router.get("/api/projects/{project_id}/git/diff")
async def get_project_git_diff(project_id: str):
    project = _get_project_or_404(project_id)
    stat = _run_project_git(project, ["diff", "--stat"])
    name_only = _run_project_git(project, ["diff", "--name-only"])
    diff = _run_project_git(project, ["diff"], max_chars=200_000)
    return {
        "project_id": project.id,
        "project_path": project.path,
        "commands": [
            ["git", "diff", "--stat"],
            ["git", "diff", "--name-only"],
            ["git", "diff"],
        ],
        "returncode": _first_nonzero(stat["returncode"], name_only["returncode"], diff["returncode"]),
        "stat": stat["stdout"],
        "name_only": [line for line in name_only["stdout"].splitlines() if line.strip()],
        "diff": diff["stdout"],
        "stderr": "\n".join(item for item in [stat["stderr"], name_only["stderr"], diff["stderr"]] if item),
        "truncated": diff["truncated"],
    }


@router.get("/api/projects/{project_id}/tool-calls")
async def get_project_tool_calls(project_id: str):
    _get_project_or_404(project_id)
    return list_tool_calls_for_project(project_id)


def _workspace_status(path: Path) -> dict:
    env = {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": os.environ.get("PATH", ""),
    }
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "status", "--short", "--branch"],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
            env=env,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read git status: {exc}") from exc

    lines = [line for line in result.stdout.splitlines() if line.strip()]
    branch = lines[0].replace("## ", "", 1) if lines and lines[0].startswith("## ") else ""
    changes = [_parse_git_status_line(line) for line in lines[1:]]
    # Normalize non-git-repo error so tests are locale-independent
    error = result.stderr or ""
    if result.returncode != 0 and "not a git repository" not in error.lower():
        error = f"not a git repository (or any parent): {error.strip()}"
    return {
        "branch": branch,
        "clean": result.returncode == 0 and len(changes) == 0,
        "changes": changes,
        "raw": result.stdout,
        "error": error,
        "returncode": result.returncode,
        "cwd": str(path),
    }


def _get_project_or_404(project_id: str):
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.path:
        raise HTTPException(status_code=400, detail="Project path is not configured")
    return project


def _run_logged_read_tool(project, tool_name: str, req, operation, risk_level: str = "low"):
    input_data = req.model_dump() if hasattr(req, "model_dump") else {}
    started_at = datetime.now().isoformat()
    tool_call = create_tool_call(
        run_id=input_data.get("run_id", ""),
        project_id=project.id,
        step_id=input_data.get("step_id", ""),
        tool_name=tool_name,
        cwd=project.path,
        status="pending",
        input_json=json.dumps(input_data, ensure_ascii=False),
        risk_level=risk_level,
        started_at=started_at,
    )
    try:
        result = operation()
        completed_at = datetime.now().isoformat()
        result_with_id = {**result, "tool_call_id": tool_call.id}
        if tool_name == "propose-patch":
            result_with_id["proposal_id"] = tool_call.id
        update_tool_call(
            tool_call.id,
            status="completed",
            output_json=json.dumps(result_with_id, ensure_ascii=False),
            completed_at=completed_at,
            finished_at=completed_at,
        )
        return result_with_id
    except HTTPException as exc:
        _mark_tool_call_failed(tool_call.id, str(exc.detail))
        raise
    except PermissionError as exc:
        _mark_tool_call_failed(tool_call.id, str(exc))
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        _mark_tool_call_failed(tool_call.id, str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        _mark_tool_call_failed(tool_call.id, str(exc))
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}") from exc


def _mark_tool_call_failed(tool_call_id: str, error: str) -> None:
    completed_at = datetime.now().isoformat()
    update_tool_call(
        tool_call_id,
        status="failed",
        error=error,
        completed_at=completed_at,
        finished_at=completed_at,
    )


def _run_project_git(project, args: list[str], timeout: int = 15, max_chars: int | None = None) -> dict:
    env = {
        "LC_ALL": "C",
        "LANG": "C",
        "PATH": os.environ.get("PATH", ""),
    }
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project.path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or "Git command timed out"
        result = subprocess.CompletedProcess(["git", *args], 124, stdout, stderr)

    stdout = result.stdout or ""
    truncated = False
    if max_chars is not None and len(stdout) > max_chars:
        stdout = stdout[:max_chars]
        truncated = True
    return {
        "returncode": result.returncode,
        "stdout": stdout,
        "stderr": result.stderr or "",
        "truncated": truncated,
    }


def _first_nonzero(*codes: int) -> int:
    for code in codes:
        if code != 0:
            return code
    return 0


def _run_project_command(project, command: str, command_type: str) -> dict:
    command = (command or "").strip()
    if not command:
        raise HTTPException(status_code=400, detail=f"Project {command_type}_command is empty")

    blocked_match = _find_blocked_command(command, project.blocked_commands)
    if blocked_match:
        return _approval_required_response(
            project=project,
            command=command,
            command_type=command_type,
            action="blocked_command",
            description=f"Command matches project blocked command: {blocked_match}",
        )

    needs_approval, action, description = check_command(command)
    if needs_approval:
        return _approval_required_response(
            project=project,
            command=command,
            command_type=command_type,
            action=action,
            description=description,
        )

    if not _is_safe_command(command, project.safe_commands):
        return _approval_required_response(
            project=project,
            command=command,
            command_type=command_type,
            action="command_not_allowed",
            description="Command is not listed in project safe_commands",
        )

    return _execute_project_command(project, command, command_type)


def _execute_project_command(project, command: str, command_type: str, approval_id: str = "") -> dict:
    try:
        args = shlex.split(command)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid command syntax: {exc}") from exc
    if not args:
        raise HTTPException(status_code=400, detail=f"Project {command_type}_command is empty")

    project_path = Path(project.path)
    report_dir = PROJECT_ROOT / "runs" / (
        f"project-{command_type}-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}_{project.id}"
    )
    report_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now()
    try:
        result = subprocess.run(
            args,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        finished_at = datetime.now()
    except subprocess.TimeoutExpired as exc:
        finished_at = datetime.now()
        result = subprocess.CompletedProcess(args, 124, exc.stdout or "", exc.stderr or "")

    report = _format_test_report(
        command=command,
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        started_at=started_at,
        finished_at=finished_at,
    )
    report_path = report_dir / f"{command_type}-report.md"
    report_path.write_text(report, encoding="utf-8")
    relative_report_path = str(report_path.relative_to(PROJECT_ROOT))
    status = "passed" if result.returncode == 0 else "failed"
    tool_call = create_tool_call(
        run_id=f"project:{project.id}",
        project_id=project.id,
        tool_name=f"project_{command_type}",
        command=command,
        cwd=project.path,
        status=status,
        approval_id=approval_id,
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
        report_path=relative_report_path,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat(),
    )

    return {
        "approval_required": False,
        "approval_id": approval_id,
        "tool_call_id": tool_call.id,
        "project_id": project.id,
        "project_path": project.path,
        "command": command,
        "command_type": command_type,
        "status": status,
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "report_path": relative_report_path,
    }


def _execute_project_approval(approval) -> dict | None:
    if not approval.run_id.startswith("project:") or not approval.command:
        return None

    project_id = approval.run_id.removeprefix("project:")
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Approval project not found")

    command_type = _approved_project_command_type(project, approval.command)
    return _execute_project_command(project, approval.command, command_type, approval_id=approval.id)


def _approved_project_command_type(project, command: str) -> str:
    normalized = command.strip()
    if normalized == project.test_command.strip():
        return "test"
    if normalized == project.build_command.strip():
        return "build"
    return "approved"


def _find_blocked_command(command: str, blocked_commands: list[str]) -> str:
    normalized = command.strip()
    for blocked in blocked_commands:
        blocked = blocked.strip()
        if blocked and (normalized == blocked or normalized.startswith(f"{blocked} ")):
            return blocked
    return ""


def _is_safe_command(command: str, safe_commands: list[str]) -> bool:
    normalized = command.strip()
    return any(normalized == safe.strip() for safe in safe_commands if safe.strip())


def _approval_required_response(project, command: str, command_type: str, action: str, description: str) -> dict:
    approval_run_id = f"project:{project.id}"
    approval = find_pending_approval(approval_run_id, action, command)
    if not approval:
        approval = create_approval(
            run_id=approval_run_id,
            action=action,
            command=command,
            description=(
                f"Project tool action requires approval.\n"
                f"Project: {project.name} ({project.id})\n"
                f"Path: {project.path}\n"
                f"Command type: {command_type}\n"
                f"Reason: {description}"
            ),
        )
    return {
        "approval_required": True,
        "approval_id": approval.id,
        "project_id": project.id,
        "project_path": project.path,
        "command": command,
        "command_type": command_type,
        "status": "approval_required",
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "action": action,
        "description": description,
        "report_path": "",
    }


@router.post("/api/tools/run-tests")
async def run_tests():
    """Run the repository test script and save a report under runs/."""
    report_dir = PROJECT_ROOT / "runs" / f"test-run-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
    report_dir.mkdir(parents=True, exist_ok=True)

    command = ["bash", "scripts/run_tests.sh"]
    started_at = datetime.now()
    try:
        result = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        finished_at = datetime.now()
    except subprocess.TimeoutExpired as exc:
        finished_at = datetime.now()
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        result = subprocess.CompletedProcess(command, 124, stdout, stderr)

    report = _format_test_report(
        command=" ".join(command),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
        started_at=started_at,
        finished_at=finished_at,
    )
    report_path = report_dir / "test-report.md"
    report_path.write_text(report, encoding="utf-8")

    return {
        "command": " ".join(command),
        "status": "passed" if result.returncode == 0 else "failed",
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "report_path": str(report_path.relative_to(PROJECT_ROOT)),
    }


def _parse_git_status_line(line: str) -> dict[str, str]:
    """Parse one `git status --short` row for the UI."""
    status = line[:2].strip() or "?"
    path = line[3:] if len(line) > 3 else line.strip()
    return {"status": status, "path": path}


def _format_test_report(
    command: str,
    returncode: int,
    stdout: str,
    stderr: str,
    started_at: datetime,
    finished_at: datetime,
) -> str:
    status = "passed" if returncode == 0 else "failed"
    return (
        "# Test Run Report\n\n"
        f"**Status:** {status}\n"
        f"**Command:** `{command}`\n"
        f"**Return code:** {returncode}\n"
        f"**Started:** {started_at.isoformat()}\n"
        f"**Finished:** {finished_at.isoformat()}\n\n"
        "## Stdout\n\n"
        "```text\n"
        f"{stdout.rstrip()}\n"
        "```\n\n"
        "## Stderr\n\n"
        "```text\n"
        f"{stderr.rstrip()}\n"
        "```\n"
    )


# ── Approvals ────────────────────────────────────────────────────────────────

@router.get("/api/approvals")
async def get_approvals():
    return list_approvals()


@router.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: str, body: ApprovalDecision | None = None):
    existing = get_approval(approval_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Approval not found")
    if existing.status != ApprovalStatus.PENDING:
        return {"approval": existing, "execution": None, "already_resolved": True}

    result = resolve_approval(approval_id, ApprovalStatus.APPROVED, reason=body.reason if body else "")
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found")

    execution = _execute_project_approval(result)
    return {"approval": result, "execution": execution, "already_resolved": False}


@router.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: str, body: ApprovalDecision | None = None):
    result = resolve_approval(approval_id, ApprovalStatus.REJECTED, reason=body.reason if body else "")
    if not result:
        raise HTTPException(status_code=404, detail="Approval not found")
    return result


# ── Config ───────────────────────────────────────────────────────────────────

@router.get("/api/config")
async def get_configuration():
    return get_config()


@router.post("/api/config")
async def update_configuration(req: ConfigUpdate):
    updated = save_config(req.model_dump(exclude_none=True))
    return updated


# ── Workflow Policy (read-only) ──────────────────────────────────────────────


@router.get("/api/workflow-policy")
async def get_workflow_policy(
    mode: str = Query(default="guided", description="Automation mode: manual, guided, or safe_prep"),
) -> WorkflowPolicyResponse:
    """Return the workflow action policy matrix for the given automation mode.

    Pure read-only — no DB reads, no tool execution, no state mutation.
    """
    try:
        automation_mode = WorkflowAutomationMode(mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{mode}'. Must be one of: manual, guided, safe_prep",
        )
    policies = list_workflow_action_policies(automation_mode)
    return WorkflowPolicyResponse(mode=automation_mode, policies=policies)


# ── Project Intake (read-only) ───────────────────────────────────────────────


@router.post("/api/project-intake/questions")
async def post_project_intake_questions(
    req: ProjectIntakeRequest,
) -> ProjectIntakeResponse:
    """Analyze a raw project idea and return structured intake questions.

    Pure read-only — no DB reads, no LLM calls, no tool execution, no state mutation.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return analyze_project_intake(req)


@router.post("/api/project-intake/brief-draft")
async def post_project_intake_brief_draft(
    req: ProjectBriefDraftRequest,
) -> ProjectBriefDraftResponse:
    """Generate a deterministic project brief draft from intake analysis.

    Pure read-only — no DB reads, no DB writes, no LLM calls, no tool
    execution, no project/run creation, no ToolCalls, no state mutation.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return draft_project_brief(req)


@router.post("/api/project-intake/plan-preview")
async def post_project_intake_plan_preview(
    req: DevelopmentPlanPreviewRequest,
) -> DevelopmentPlanPreviewResponse:
    """Generate a deterministic development plan preview from intake data.

    Pure read-only — no DB reads, no DB writes, no LLM calls, no tool
    execution, no project/run creation, no assignments, no ToolCalls, no state
    mutation.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return draft_development_plan(req)


@router.post("/api/project-intake/source-of-truth-preview")
async def post_project_intake_source_of_truth_preview(
    req: SourceOfTruthPreviewRequest,
) -> SourceOfTruthPreviewResponse:
    """Generate a deterministic source-of-truth preview from intake data.

    Pure read-only — no DB reads, no DB writes, no LLM calls, no tool
    execution, no project/run creation, no assignments, no ToolCalls, no state
    mutation.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return build_source_of_truth_from_intake(req)


@router.post("/api/project-intake/coverage-preview")
async def post_project_intake_coverage_preview(
    req: RequirementCoveragePreviewRequest,
) -> RequirementCoveragePreviewResponse:
    """Generate deterministic requirement coverage from source of truth and plan.

    Pure read-only — no DB reads, no DB writes, no LLM calls, no tool
    execution, no project/run creation, no assignments, no ToolCalls, no state
    mutation.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return build_requirement_coverage_from_plan(req)


# ── Confirmed Plan → Run Step Preview (read-only) ────────────────────────────


@router.post("/api/project-intake/run-preview")
async def post_project_intake_run_preview(
    req: ConfirmedPlanRunPreviewRequest,
) -> ConfirmedPlanRunPreviewResponse:
    """Preview how the confirmed plan would map to future run steps.

    Pure read-only — no DB reads, no DB writes, no LLM calls, no tool
    execution, no project/run/run_steps creation, no assignments, no ToolCalls,
    no state mutation.  This is a preview only.
    """
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )
    return build_confirmed_plan_run_preview(req)


# ── Unified Autonomous Project Intake Preview (read-only) ────────────────────


@router.post("/api/project-intake/unified-preview")
async def post_project_intake_unified_preview(
    req: UnifiedIntakeRequest,
) -> UnifiedAutonomousIntakePreviewResponse:
    """Return a deterministic unified autonomous project intake preview.

    Pure read-only — no DB writes, no project creation, no run creation,
    no tool_calls, no provider calls, no file reads, no shell commands.

    Accepts idea/document/existing_project mode and returns:
    - classification reason
    - clarifying questions
    - source of truth preview
    - module map preview
    - multi-agent plan preview
    - next recommended action
    - safety notes and limitations
    """
    return build_unified_autonomous_intake_preview(req)


@router.post("/api/project-intake/existing-project/repo-intake-preview")
async def post_existing_project_repo_intake_preview(
    req: ExistingProjectRepoIntakeRequest,
) -> ExistingProjectRepoIntakeResponse:
    """Return bounded read-only repository intake for an existing project.

    Uses a stored project path when project_id is provided and project_path is
    empty.  Reads only directory metadata plus small allowlisted manifest/config
    files.  Creates no projects, runs, run steps, tool_calls, proposals, applies,
    provider calls, commands, or DB writes.
    """
    project_path = (req.project_path or "").strip()
    if req.project_id:
        project = get_project(req.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        stored_path = (project.path or "").strip()
        if not project_path:
            project_path = stored_path
        elif stored_path:
            try:
                requested_root = Path(project_path).expanduser().resolve(strict=True)
                stored_root = Path(stored_path).expanduser().resolve(strict=True)
            except (OSError, ValueError):
                requested_root = None
                stored_root = None
            if requested_root and stored_root and requested_root != stored_root and stored_root not in requested_root.parents:
                return ExistingProjectRepoIntakeResponse(
                    project_id=req.project_id,
                    project_path_hint=project_path,
                    protected_path_warnings=["Explicit project_path is outside the selected project's configured root."],
                    recommended_first_safe_action="Use the selected project's configured path or choose the matching project.",
                    safety_notes=["Repo intake rejected a path outside the selected project root before traversal."],
                    limitations=["No repository analysis was performed."],
                )
    request = req.model_copy(update={"project_path": project_path})
    return build_existing_project_repo_intake_preview(request)


# ── Clarifying Questions Engine v1 (read-only) ───────────────────────────────


@router.post("/api/project-intake/clarifying-questions")
async def post_project_intake_clarifying_questions(
    req: UnifiedIntakeRequest,
) -> ClarifyingQuestionSet:
    """Return a structured set of clarifying questions for the given intake request.

    Pure read-only — no DB writes, no project creation, no run creation,
    no tool_calls, no provider calls, no file reads, no shell commands.
    """
    return build_clarifying_question_set(req)


@router.post("/api/project-intake/clarifying-preview")
async def post_project_intake_clarifying_preview(
    req: ClarifyingAnswersRequest,
) -> ClarifiedIntakePreviewResponse:
    """Return a refined intake preview after applying user clarifying answers.

    Pure read-only — no DB writes, no project creation, no run creation,
    no tool_calls, no provider calls, no file reads, no shell commands.
    Unknown question_ids are silently ignored. Invalid mode returns 422.
    """
    return refine_unified_intake_with_answers(req)


@router.post("/api/project-intake/source-of-truth-draft")
async def post_project_intake_source_of_truth_draft(
    req: SourceOfTruthDraftFromIntakeRequest,
) -> SourceOfTruthDraftFromIntakeResponse:
    """Build a deterministic Source of Truth draft from CQE-answered intake.

    Preview-only — no DB writes, no project creation, no run creation,
    no tool_calls, no provider calls, no file reads, no shell commands.
    ``confirm_persist`` and ``project_id`` are accepted in the body but
    silently ignored by this endpoint (use /confirm for persistence).
    """
    if not req.intake.intake.title and not req.intake.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )
    return build_source_of_truth_draft_from_intake(req)


@router.post("/api/project-intake/source-of-truth-draft/confirm")
async def post_project_intake_source_of_truth_draft_confirm(
    req: SourceOfTruthDraftFromIntakeRequest,
) -> SourceOfTruthDraftFromIntakeResponse:
    """Build and optionally persist a Source of Truth draft from CQE-answered intake.

    Persists only when ``confirm_persist=True`` AND ``project_id`` is provided
    and matches an existing project.

    Returns 400 when ``confirm_persist=True`` but ``project_id`` is absent.
    Returns 404 when ``project_id`` does not match a known project.
    No LLM calls. No run creation. No agent execution. No patch proposal.
    """
    if not req.intake.intake.title and not req.intake.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )

    result = build_source_of_truth_draft_from_intake(req)

    if req.confirm_persist:
        if not req.project_id:
            raise HTTPException(
                status_code=400,
                detail="project_id is required when confirm_persist=True",
            )
        project = get_project(req.project_id)
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")

        # Build a ProjectSourceOfTruthDocument and persist using existing helper
        draft = result.draft
        try:
            doc = ProjectSourceOfTruthDocument(
                project_id=req.project_id,
                status="draft",
                product_name=draft.product_name,
                product_summary=draft.product_summary,
                project_intent=draft.project_intent,
                target_users=draft.target_users,
                goals=draft.goals,
                non_goals=draft.non_goals,
                requirements=draft.requirements,
                constraints=draft.constraints,
                forbidden_changes=draft.forbidden_changes,
                acceptance_criteria=draft.acceptance_criteria,
                architecture_notes=draft.architecture_notes,
                decisions=draft.decisions,
                assumptions=draft.assumptions,
                risks=draft.risks,
                open_questions=draft.open_questions,
                source=draft.source,
            )
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        stored = _upsert_sot(req.project_id, doc)
        result = result.model_copy(update={
            "persisted": True,
            "project_id": req.project_id,
            "version": stored.version,
        })

    return result


@router.post("/api/project-intake/module-map-draft")
async def post_project_intake_module_map_draft(
    req: ModuleMapDraftFromIntakeRequest,
) -> ModuleMapDraftFromIntakeResponse:
    """Build a deterministic Module Map draft from CQE-answered intake.

    Preview-only — no DB writes, no project creation, no run creation,
    no tool_calls, no provider calls, no file reads, no shell commands.
    ``confirm_persist`` and ``project_id`` are accepted in the body but
    ignored by this endpoint (use /confirm for persistence).
    """
    if not req.intake.intake.title and not req.intake.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )
    return build_module_map_draft_from_intake(req)


@router.post("/api/project-intake/module-map-draft/confirm")
async def post_project_intake_module_map_draft_confirm(
    req: ModuleMapDraftFromIntakeRequest,
) -> ModuleMapDraftFromIntakeResponse:
    """Build and optionally persist a Module Map draft from CQE-answered intake.

    Persists only when ``confirm_persist=True`` AND ``project_id`` is provided
    and matches an existing project.

    No LLM calls. No run creation. No agent execution. No patch proposal.
    """
    if not req.intake.intake.title and not req.intake.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )

    result = build_module_map_draft_from_intake(req)

    if not req.confirm_persist:
        raise HTTPException(
            status_code=400,
            detail="confirm_persist=true is required to persist a Module Map draft",
        )
    if not req.project_id:
        raise HTTPException(
            status_code=400,
            detail="project_id is required when confirm_persist=True",
        )
    project = get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not result.validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Module Map draft validation failed",
                "errors": result.validation.errors,
            },
        )

    try:
        doc = ProjectModuleMapDocument(
            project_id=req.project_id,
            status="active",
            modules=result.draft.modules,
            ignored_paths=result.draft.ignored_paths,
            scan_summary=result.draft.scan_summary,
            source=result.draft.source,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    validation = _validate_module_map(doc)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Module Map storage validation failed",
                "errors": validation.errors,
            },
        )

    stored = _upsert_module_map(req.project_id, doc)
    return result.model_copy(update={
        "persisted": True,
        "project_id": req.project_id,
        "module_map_id": stored.id,
        "version": stored.version,
    })


@router.post("/api/project-intake/multi-agent-plan")
async def post_project_intake_multi_agent_plan(
    req: MultiAgentPlanFromIntakeRequest,
) -> MultiAgentPlanFromIntakeResponse:
    """Build a deterministic multi-agent plan preview from intake context.

    Preview-only. Does not persist state, create projects/runs/steps/tool_calls,
    call providers, read files, scan repositories, or execute commands.
    """
    if not req.intake.title and not req.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )
    return build_multi_agent_plan_from_intake(req)


@router.post("/api/project-intake/development-run-preview")
async def post_project_intake_development_run_preview(
    req: IntakeDevelopmentRunPreviewRequest,
) -> IntakeDevelopmentRunPreviewResponse:
    """Build a deterministic preview of a future controlled development run.

    Preview-only. Does not persist state, start agents, call providers, read
    files, scan repositories, or execute commands.
    """
    if not req.intake.title and not req.intake.raw_input:
        raise HTTPException(
            status_code=400,
            detail="Field 'title' or 'raw_input' must be non-empty.",
        )
    return build_intake_development_run_preview(req)


@router.post("/api/project-intake/confirmed-run-creation-contract-preview")
async def post_project_intake_confirmed_run_creation_contract_preview(
    req: IntakeConfirmedRunCreationContractPreviewRequest,
) -> IntakeConfirmedRunCreationContractPreviewResponse:
    """Evaluate the confirmed run creation contract for a given development run preview.

    Preview-only.  Does not persist state, create projects, runs, run steps,
    tool_calls, call providers, read files, or execute commands.
    Returns the contract decision (allowed / warning / blocked) with full rationale.
    """
    if not req.development_run_preview:
        raise HTTPException(
            status_code=400,
            detail="Field 'development_run_preview' must be non-empty.",
        )
    return build_confirmed_run_creation_contract_preview(req)


@router.post("/api/project-intake/confirmed-development-run/create")
async def post_confirmed_development_run_create(
    req: ConfirmedDevelopmentRunCreateRequest,
) -> ConfirmedDevelopmentRunCreateResponse:
    """Create a real pending Run + RunSteps from the confirmed intake development run preview.

    Requires:
      - project_id (non-empty, must exist)
      - confirm_create=true
      - contract_confirmed=true
      - source_of_truth_confirmed=true
      - module_map_confirmed=true
      - provider_disabled_confirmed=true
      - later_actions_confirmed=true
      - development_run_preview with valid steps

    Creates run (pending) and run_steps (pending) only.
    Does NOT execute agents, call providers, create tool_calls, apply patches,
    run commands, create patch proposals, or auto-start the run.
    """
    # ── Preflight: confirmation booleans ──────────────────────────────────────
    if not req.project_id or not req.project_id.strip():
        raise HTTPException(status_code=400, detail="project_id is required.")
    if not req.confirm_create:
        raise HTTPException(status_code=400, detail="confirm_create must be true.")
    if not req.contract_confirmed:
        raise HTTPException(status_code=400, detail="contract_confirmed must be true.")
    if not req.source_of_truth_confirmed:
        raise HTTPException(status_code=400, detail="source_of_truth_confirmed must be true.")
    if not req.module_map_confirmed:
        raise HTTPException(status_code=400, detail="module_map_confirmed must be true.")
    if not req.provider_disabled_confirmed:
        raise HTTPException(status_code=400, detail="provider_disabled_confirmed must be true.")
    if not req.later_actions_confirmed:
        raise HTTPException(status_code=400, detail="later_actions_confirmed must be true.")
    if not req.development_run_preview:
        raise HTTPException(status_code=400, detail="development_run_preview must be non-empty.")

    # ── Verify project exists ─────────────────────────────────────────────────
    project = get_project(req.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{req.project_id}' not found.")

    # ── Contract evaluation ───────────────────────────────────────────────────
    _inp, contract_result = build_confirmed_development_run_creation_input(req)

    if contract_result.decision.value == "blocked":
        return ConfirmedDevelopmentRunCreateResponse(
            created=False,
            run_id=None,
            project_id=req.project_id,
            status="blocked",
            run_mode=req.preferred_run_mode,
            steps=[],
            contract_decision=contract_result.decision.value,
            blockers=contract_result.blockers,
            warnings=contract_result.warnings,
            safety_notes=list(_BRIDGE_SAFETY_NOTES),
            next_recommended_action=contract_result.next_recommended_action,
        )

    # ── Build step metadata (pure, no DB) ─────────────────────────────────────
    step_metas = build_pending_run_step_inputs_from_development_preview(
        req.development_run_preview,
        repo_intake_preview=req.repo_intake_preview,
    )
    if not step_metas:
        raise HTTPException(status_code=400, detail="No steps found in development_run_preview.")

    # ── Compose run prompt from preview ───────────────────────────────────────
    preview = req.development_run_preview
    run_title = str(preview.get("run_title", "Confirmed Development Run"))[:400]
    run_goal = str(preview.get("run_goal", ""))[:800]
    run_prompt = f"{run_title}\n\n{run_goal}".strip()

    # ── Persist Run (pending, not executed) ───────────────────────────────────
    run = create_run(
        prompt=run_prompt,
        mode="offline",
        project_id=project.id,
        project_path=project.path or "",
    )

    # ── Persist RunSteps (all pending, provider_allowed=false) ────────────────
    created_steps: list[ConfirmedDevelopmentRunCreatedStep] = []
    for meta in step_metas:
        persisted = create_run_step(
            run_id=run.id,
            title=meta["title"],
            agent_id=meta["agent_id"],
            status="pending",
            input=meta["input_text"],
        )
        created_steps.append(ConfirmedDevelopmentRunCreatedStep(
            step_id=persisted.id,
            title=persisted.title,
            agent_role=meta["agent_role"],
            status=persisted.status,
            requirement_ids=meta["requirement_ids"],
            module_ids=meta["module_ids"],
            depends_on=meta["depends_on"],
            manual_approval_required=meta["manual_approval_required"],
            provider_allowed=False,
        ))

    run_status = run.status.value if hasattr(run.status, "value") else str(run.status)

    return ConfirmedDevelopmentRunCreateResponse(
        created=True,
        run_id=run.id,
        project_id=project.id,
        status=run_status,
        run_mode="offline",
        steps=created_steps,
        contract_decision=contract_result.decision.value,
        blockers=[],
        warnings=list(contract_result.warnings),
        safety_notes=list(_BRIDGE_SAFETY_NOTES),
        next_recommended_action=(
            f"Run {run.id} created with {len(created_steps)} pending step(s). "
            "Open the Run Detail page to review steps. "
            "No agents, providers, or commands have been started."
        ),
        open_run_url_hint=f"/runs/{run.id}",
    )


# ── Create Run from Confirmed Plan ──────────────────────────────────────────


@router.post("/api/project-intake/confirmed-run")
async def post_project_intake_confirmed_run(
    req: ConfirmedRunFromPlanRequest,
) -> ConfirmedRunFromPlanResponse:
    """Create a real Run + RunSteps from the confirmed plan preview.

    Requires explicit `confirm: true`.  Creates pending run and pending steps
    only — does NOT execute agents, tools, providers, or patches.
    """
    if not req.confirm:
        raise HTTPException(
            status_code=400,
            detail="Field 'confirm' must be true.  Explicit confirmation is required to create a run.",
        )
    if not req.idea or not req.idea.strip():
        raise HTTPException(
            status_code=400,
            detail="Field 'idea' must be a non-empty string.",
        )

    # Build preview (pure, no side effects).
    preview = build_confirmed_plan_run_preview(ConfirmedPlanRunPreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
    ))
    source_preview = build_source_of_truth_from_intake(SourceOfTruthPreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
    ))
    coverage = build_requirement_coverage_from_plan(RequirementCoveragePreviewRequest(
        idea=req.idea,
        mode=req.mode,
        existing_project_attached=req.existing_project_attached,
        known_stack=req.known_stack,
        known_constraints=req.known_constraints,
        user_goal=req.user_goal,
        source_of_truth=source_preview.source_of_truth,
    ))

    warnings: list[str] = list(preview.warnings)
    if not preview.ready_to_create_run:
        warnings.append(
            "Plan was not fully ready (blocking issues exist).  "
            "Run created anyway because confirmation was explicit."
        )

    # Resolve project.
    project_id = req.project_id or ""
    project_path = ""
    if project_id:
        project = get_project(project_id)
        if project:
            project_path = project.path

    # Create the Run (pending, not executed).
    run = create_run(
        prompt=req.idea,
        mode="offline",
        project_id=project_id,
        project_path=project_path,
    )

    # Look up active persisted SoT for this project (if any).
    # Returns None when no active SoT exists, or when project_id is empty.
    # No provider calls, no DB writes, no run mutation by this lookup.
    _persisted_sot_available: bool = False
    if project_id:
        _persisted_sot_probe = _build_persisted_sot_context(project_id=project_id)
        _persisted_sot_available = _persisted_sot_probe is not None
        if _persisted_sot_available:
            warnings.append(
                f"Active persisted Source of Truth found for project {project_id!r}. "
                "Requirement context will be derived from the persisted SoT instead of the intake preview."
            )
    else:
        _persisted_sot_probe = None

    # Create RunSteps from preview steps — all pending, no execution.
    created_steps: list[ConfirmedRunCreatedStep] = []
    for step_preview in preview.steps:
        # Build rich input text with requirement metadata.
        # If an active persisted SoT exists, use it for the context block so that
        # project-level requirements (not session-only intake requirements) are embedded.
        # Avoids duplicate AI_WORKBENCH_REQUIREMENT_CONTEXT blocks by using one or the other.
        if _persisted_sot_available and project_id:
            # Always pass requirement_ids=None so all persisted SoT requirements are included.
            # Intake-generated requirement IDs (e.g. "REQ-1") are from the in-memory session
            # SoT and belong to a different namespace than persisted SoT IDs (e.g. "REQ-001").
            # Filtering by intake IDs would silently drop all persisted requirements.
            persisted_ctx = _build_persisted_sot_context(
                project_id=project_id,
                requirement_ids=None,
            )
            requirement_context = persisted_ctx or format_confirmed_run_step_requirement_context(
                step=step_preview,
                source_of_truth=source_preview.source_of_truth,
                coverage=coverage,
            )
        else:
            requirement_context = format_confirmed_run_step_requirement_context(
                step=step_preview,
                source_of_truth=source_preview.source_of_truth,
                coverage=coverage,
            )
        input_parts: list[str] = [step_preview.description, requirement_context]
        if step_preview.required_requirement_ids:
            input_parts.append(
                f"\n[Linked requirements: {', '.join(step_preview.required_requirement_ids)}]"
            )
        if step_preview.expected_deliverables:
            input_parts.append(
                f"\n[Expected deliverables: {', '.join(step_preview.expected_deliverables)}]"
            )
        if step_preview.depends_on:
            input_parts.append(
                f"\n[Depends on: {', '.join(step_preview.depends_on)}]"
            )
        if step_preview.validation_notes:
            input_parts.append(f"\n[Validation: {step_preview.validation_notes}]")
        if step_preview.manual_approval_required:
            input_parts.append("\n[Manual approval required before execution]")
        if step_preview.safe_to_prepare:
            input_parts.append("\n[Safe to prepare — read-only context gathering]")

        persisted_step = create_run_step(
            run_id=run.id,
            title=step_preview.title,
            agent_id=step_preview.suggested_agent_id or "",
            status="pending",
            input="\n".join(input_parts),
        )
        created_steps.append(ConfirmedRunCreatedStep(
            step_id=persisted_step.id,
            title=persisted_step.title,
            agent_id=persisted_step.agent_id,
            status=persisted_step.status,
        ))

    summary = (
        f"Run {run.id} created with {len(created_steps)} pending steps.  "
        f"No agents, tools, or providers were executed."
    )

    return ConfirmedRunFromPlanResponse(
        run_id=run.id,
        run_status=run.status.value if hasattr(run.status, "value") else str(run.status),
        steps_created=len(created_steps),
        steps=created_steps,
        summary=summary,
        warnings=warnings,
    )


# ── Agent Execution Harness v1 ─────────────────────────────────────────────────
#
# Safety contract:
#   - No file mutation by any code path in this section.
#   - No auto-apply, no auto-proposal, no auto-rollback.
#   - No shell/command execution.
#   - Provider call only via Ollama (local) when allow_provider_call=True.
#   - Agent result is advisory/structured draft only.
#   - No execute_run, no asyncio.create_task.
#
# _AGENT_EXECUTION_TOOL_NAME is the tool_call audit marker used for listing.
import re as _re_harness  # word-boundary routing; local alias avoids shadowing

_AGENT_EXECUTION_TOOL_NAME = "agent-execution"

# Maximum prompt size we'll send (chars) — hard cap regardless of request.
_AGENT_PROMPT_MAX_CHARS = 16000

# Maximum recent tool_calls summarised in context.
_AGENT_CONTEXT_MAX_RECENT_CALLS = 10

# Valid execution modes.
_AGENT_EXECUTION_MODES = frozenset({"dry_run", "mock", "provider"})

# Ordered keyword rules for word-boundary agent routing used by
# _infer_agent_word_boundary.  First matching rule wins.
# Each entry: (list_of_keywords_or_phrases, agent_id)
# Single-word entries are matched as whole tokens; multi-word phrases use \b regex.
_WB_AGENT_KEYWORDS: list[tuple[list[str], str]] = [
    (["mobile", "android", "ios", "flutter", "react native"], "mobile-developer"),
    (["test", "tests", "testing", "pytest", "unit test", "integration test",
      "e2e", "regression", "coverage", "qa", "verify"], "qa-expert"),
    (["security", "vulnerability", "csrf", "xss", "injection",
      "secret", "credential"], "security-auditor"),
    (["deploy", "ci", "cd", "pipeline", "docker", "kubernetes", "k8s",
      "release", "devops", "infrastructure", "helm"], "devops-engineer"),
    (["error", "bug", "fix", "debug", "crash", "exception", "traceback",
      "failure", "broken", "investigate"], "error-detective"),
    (["database", "db", "sql", "query", "migration", "schema", "orm",
      "postgres", "mysql", "sqlite", "mongo"], "sql-pro"),
    (["doc", "readme", "guide", "documentation", "report", "changelog",
      "wiki", "tutorial"], "technical-writer"),
    (["frontend", "ui", "ux", "react", "vue", "angular", "css", "component",
      "page", "html", "jsx", "tsx", "svelte"], "frontend-developer"),
    (["backend", "api", "endpoint", "fastapi", "flask", "django", "server",
      "rest", "grpc", "microservice"], "backend-developer"),
    (["orchestrate", "review project", "inspect project",
      "coordinate agents"], "orchestrator"),
]


def _infer_agent_word_boundary(step_title: str, step_input: str) -> str:
    """Word-boundary aware agent inference — avoids substring false positives.

    Normalises text to lowercase, extracts whole tokens with a regex, then
    checks single-word keywords as set membership (no substrings) and
    multi-word phrases with \\b anchors.  Falls back to fullstack-developer.
    """
    text = f"{step_title} {step_input}".lower()
    tokens: set[str] = set(_re_harness.findall(r"\b[a-z0-9][a-z0-9_+#.-]*\b", text))
    for phrases, agent_id in _WB_AGENT_KEYWORDS:
        for phrase in phrases:
            if " " in phrase:
                if _re_harness.search(r"\b" + _re_harness.escape(phrase) + r"\b", text):
                    return agent_id
            else:
                if phrase in tokens:
                    return agent_id
    return "fullstack-developer"


def _route_agent_for_step(
    step_title: str,
    step_input: str,
    task_type: str,
    requested_agent_id: str | None,
) -> tuple[str, str, str]:
    """Return (agent_id, agent_name, task_type) via deterministic routing.

    Uses _infer_agent_word_boundary (word-boundary token rules, first match wins).
    If a valid requested_agent_id is supplied and exists in the registry, use it.
    Unknown requested_agent_id is silently ignored — routing falls back to inference.
    Final fallback: fullstack-developer.
    """
    # Honour explicit agent_id if it exists in the registry.
    if requested_agent_id:
        agent_obj = get_agent(requested_agent_id)
        if agent_obj:
            eff_task_type = task_type or infer_task_type_for_step(step_title, step_input, agent_obj.id)
            return agent_obj.id, agent_obj.name, eff_task_type

    # Infer from step content using word-boundary matching.
    inferred_id = _infer_agent_word_boundary(step_title, step_input)
    agent_obj = get_agent(inferred_id)
    agent_name = agent_obj.name if agent_obj else inferred_id
    eff_task_type = task_type or infer_task_type_for_step(step_title, step_input, inferred_id)
    return inferred_id, agent_name, eff_task_type


def _build_agent_execution_context(
    run,
    step,
    project,
    tool_calls: list,
    *,
    include_recent_tool_calls: bool = True,
    include_patch_lifecycle: bool = True,
    agent_id: str = "",
    agent_name: str = "",
    task_type: str = "",
) -> AgentExecutionContext:
    """Build a deterministic AgentExecutionContext from current run/step state.

    Pure read — no tool_call creation, no provider calls, no file mutation.
    """
    step_input = step.input or ""

    # Parse requirement context from step.input (uses existing parser).
    req_ctx = None
    try:
        req_ctx = parse_run_step_requirement_context(step_input)
    except Exception:
        req_ctx = None

    requirement_ids: list[str] = []
    source_of_truth_summary = ""
    acceptance_criteria = ""
    constraints = ""
    forbidden_changes = ""

    if req_ctx:
        requirement_ids = list(getattr(req_ctx, "requirement_ids", []) or [])
        source_of_truth_summary = str(getattr(req_ctx, "source_of_truth_summary", "") or "")[:800]
        acceptance_criteria = "\n".join(getattr(req_ctx, "acceptance_criteria", []) or [])[:600]
        constraints = "\n".join(getattr(req_ctx, "constraints", []) or [])[:400]
        forbidden_changes = "\n".join(getattr(req_ctx, "forbidden_changes", []) or [])[:400]

    # Step input summary (trimmed).
    step_input_summary = step_input[:600] if step_input else ""

    # Recent tool_call summary.
    recent_tool_call_summary = ""
    if include_recent_tool_calls and tool_calls:
        step_calls = sorted(
            [tc for tc in tool_calls if tc.step_id == step.id],
            key=lambda tc: tc.created_at,
            reverse=True,
        )[:_AGENT_CONTEXT_MAX_RECENT_CALLS]
        parts = []
        for tc in reversed(step_calls):  # oldest first
            status_str = tc.status or "?"
            parts.append(f"  [{tc.tool_name}] status={status_str} id={tc.id[:8]}")
        recent_tool_call_summary = "\n".join(parts) if parts else "No tool calls yet."

    # Patch lifecycle summary.
    patch_lifecycle_summary = ""
    if include_patch_lifecycle and tool_calls:
        propose_calls = [tc for tc in tool_calls if tc.tool_name in ("propose-patch", "propose_patch") and tc.step_id == step.id and tc.status == "completed"]
        apply_calls = [tc for tc in tool_calls if tc.tool_name in ("apply-patch", "apply_patch") and tc.step_id == step.id and tc.status == "completed"]
        test_calls = [tc for tc in tool_calls if tc.tool_name in ("run-command", "run_command", "run-tests") and tc.step_id == step.id and tc.status == "completed"]
        parts = []
        if propose_calls:
            parts.append(f"propose-patch: {len(propose_calls)} completed")
        if apply_calls:
            parts.append(f"apply-patch: {len(apply_calls)} completed")
        if test_calls:
            last_rc = test_calls[-1].returncode
            parts.append(f"run-tests: {len(test_calls)} run(s), last returncode={last_rc}")
        patch_lifecycle_summary = "; ".join(parts) if parts else "No patch/test lifecycle activity yet."

    # Build available agents list (compact).
    available_agents: list[dict] = [
        {
            "id": a.id,
            "name": a.name,
            "role": a.role,
            "category": a.category,
        }
        for a in get_enabled_agents()
    ]

    # Build module context when a project with an active module map exists.
    # Pure read — no DB writes, no provider calls, no file reads.
    module_context: AgentModuleContext | None = None
    if project and project.id:
        try:
            module_context = _build_module_context(
                project_id=project.id,
                step_input=step_input,
                step_title=step.title or "",
                requirement_ids=requirement_ids or None,
            )
        except Exception:
            module_context = None

    return AgentExecutionContext(
        run_id=run.id,
        step_id=step.id,
        step_title=step.title or "",
        step_input_summary=step_input_summary,
        requirement_ids=requirement_ids,
        source_of_truth_summary=source_of_truth_summary,
        acceptance_criteria=acceptance_criteria,
        constraints=constraints,
        forbidden_changes=forbidden_changes,
        recent_tool_call_summary=recent_tool_call_summary,
        patch_lifecycle_summary=patch_lifecycle_summary,
        operator_queue_summary="",  # populated separately if needed
        project_name=project.name if project else "",
        project_path=project.path if project else "",
        recommended_agent_id=agent_id,
        recommended_agent_name=agent_name,
        recommended_task_type=task_type,
        available_agents=available_agents,
        module_context=module_context,
    )


def _build_agent_prompt(
    context: AgentExecutionContext,
    req: AgentExecutionRequest,
    agent_name: str,
) -> str:
    """Build a bounded, structured prompt for the agent task.

    The prompt instructs the agent to return structured advisory output only.
    No file mutation, no auto-apply, no auto-proposal.
    """
    parts: list[str] = []

    parts.append(f"## Role\nYou are a {agent_name} acting as an advisory agent for the AI Workbench system.")
    parts.append(
        "Your output is ADVISORY ONLY. You MUST NOT:\n"
        "- Directly edit or delete files\n"
        "- Create proposals automatically\n"
        "- Apply patches\n"
        "- Run shell commands\n"
        "- Bypass approval gates\n"
        "- Invent requirements not present in the context\n"
        "Respect the Source of Truth at all times."
    )

    parts.append(f"## Task\nTask type: {req.task_type}\nStep: {context.step_title}")

    if req.user_instruction:
        parts.append(f"## User Instruction\n{req.user_instruction}")

    if context.step_input_summary:
        parts.append(f"## Step Input (summary)\n{context.step_input_summary}")

    if context.requirement_ids and req.include_requirement_context:
        parts.append(f"## Linked Requirements\n{', '.join(context.requirement_ids)}")

    if context.source_of_truth_summary and req.include_requirement_context:
        parts.append(f"## Source of Truth\n{context.source_of_truth_summary}")

    if context.acceptance_criteria and req.include_requirement_context:
        parts.append(f"## Acceptance Criteria\n{context.acceptance_criteria}")

    if context.constraints and req.include_requirement_context:
        parts.append(f"## Constraints\n{context.constraints}")

    if context.forbidden_changes and req.include_requirement_context:
        parts.append(f"## Forbidden Changes\n{context.forbidden_changes}")

    if context.recent_tool_call_summary and req.include_recent_tool_calls:
        parts.append(f"## Recent Tool Calls\n{context.recent_tool_call_summary}")

    if context.patch_lifecycle_summary and req.include_patch_lifecycle:
        parts.append(f"## Patch Lifecycle State\n{context.patch_lifecycle_summary}")

    module_context = context.module_context
    if module_context and module_context.has_active_module_map and module_context.matched_modules:
        module_lines: list[str] = []
        for mod in module_context.matched_modules[:5]:
            name = str(mod.get("name") or mod.get("slug") or "Unknown module")[:80]
            module_type = str(mod.get("module_type") or "unknown")[:40]
            responsibilities = [str(item)[:100] for item in (mod.get("responsibilities") or [])[:3]]
            key_files = [str(item)[:120] for item in (mod.get("key_files") or [])[:5]]
            paths = [str(item)[:120] for item in (mod.get("paths") or [])[:5]]
            requirements = [str(item)[:40] for item in (mod.get("related_requirements") or [])[:5]]
            test_hints = [str(item)[:100] for item in (mod.get("test_hints") or [])[:3]]
            risks = [str(item)[:100] for item in (mod.get("risks") or [])[:3]]

            module_lines.append(f"- Module: {name}")
            module_lines.append(f"  Type: {module_type}")
            if responsibilities:
                module_lines.append(f"  Responsibilities: {', '.join(responsibilities)}")
            if paths:
                module_lines.append(f"  Paths: {', '.join(paths)}")
            if key_files:
                module_lines.append(f"  Key files: {', '.join(key_files)}")
            if requirements:
                module_lines.append(f"  Related requirements: {', '.join(requirements)}")
            if test_hints:
                module_lines.append(f"  Test hints: {', '.join(test_hints)}")
            if risks:
                module_lines.append(f"  Risks: {', '.join(risks)}")

        module_summary = module_context.module_summary[:500]
        parts.append(
            "## PROJECT MODULE MAP CONTEXT\n"
            f"{module_summary}\n"
            + "\n".join(module_lines)
            + "\nThese are bounded location hints only, not permission to edit files."
        )

    parts.append(
        "## Required Output Format\n"
        "Respond with a JSON object with EXACTLY these fields:\n"
        "{\n"
        '  "summary": "one-sentence summary of your analysis",\n'
        '  "analysis": "detailed analysis of the step and what needs to be done",\n'
        '  "proposed_files": ["list of file paths that would need changes"],\n'
        '  "patch_intent": "describe what changes you would propose",\n'
        '  "risks": ["list potential risks or side effects"],\n'
        '  "test_suggestions": ["list specific tests to verify changes"],\n'
        '  "questions": ["list any open questions or blockers"],\n'
        '  "recommended_next_action": "what should the operator do next"\n'
        "}\n"
        "If you cannot produce valid JSON, wrap your response in a summary field instead."
    )

    prompt = "\n\n".join(parts)
    return prompt[:_AGENT_PROMPT_MAX_CHARS]


def _parse_provider_response(raw_text: str, max_chars: int) -> AgentExecutionResult:
    """Coerce raw provider text into AgentExecutionResult.

    Attempts JSON parse; on failure wraps text in summary/analysis.
    Never raises — always returns a valid result.
    """
    text = (raw_text or "")[:max_chars]
    try:
        # Strip markdown code fences if present.
        stripped = text.strip()
        if stripped.startswith("```"):
            lines = stripped.split("\n")
            inner = [ln for ln in lines if not ln.startswith("```")]
            stripped = "\n".join(inner).strip()
        data = json.loads(stripped)
        proposed_files = data.get("proposed_files", [])
        if not isinstance(proposed_files, list):
            proposed_files = []
        risks = data.get("risks", [])
        if not isinstance(risks, list):
            risks = [str(risks)] if risks else []
        test_suggestions = data.get("test_suggestions", [])
        if not isinstance(test_suggestions, list):
            test_suggestions = []
        questions = data.get("questions", [])
        if not isinstance(questions, list):
            questions = []
        patch_intent = str(data.get("patch_intent", ""))
        can_feed = bool(patch_intent or proposed_files)
        return AgentExecutionResult(
            summary=str(data.get("summary", ""))[:400],
            analysis=str(data.get("analysis", ""))[:2000],
            proposed_files=proposed_files[:20],
            patch_intent=patch_intent[:800],
            risks=risks[:20],
            test_suggestions=test_suggestions[:20],
            questions=questions[:20],
            recommended_next_action=str(data.get("recommended_next_action", ""))[:200],
            can_feed_patch_draft=can_feed,
        )
    except (json.JSONDecodeError, ValueError, TypeError):
        # Non-JSON: wrap in summary/analysis.
        can_feed = bool(text)
        return AgentExecutionResult(
            summary="Agent returned unstructured text (non-JSON response).",
            analysis=text[:2000],
            proposed_files=[],
            patch_intent="",
            risks=["Response was not structured JSON — review manually before using."],
            test_suggestions=[],
            questions=[],
            recommended_next_action="Review the analysis above and manually create a proposal if appropriate.",
            can_feed_patch_draft=False,
        )


def _mock_agent_result(context: AgentExecutionContext, task_type: str) -> AgentExecutionResult:
    """Return a deterministic mock AgentExecutionResult for testing/dry-run."""
    step_title = context.step_title or "unknown step"
    proposed_files: list[str] = []

    # Simple heuristic-based file suggestions from step title.
    title_lower = step_title.lower()
    if any(kw in title_lower for kw in ["frontend", "ui", "component", "page", "react"]):
        proposed_files = ["frontend/src/pages/ExamplePage.tsx", "frontend/src/types/index.ts"]
    elif any(kw in title_lower for kw in ["backend", "api", "route", "endpoint", "model"]):
        proposed_files = ["backend/src/api/routes.py", "backend/src/models.py"]
    elif any(kw in title_lower for kw in ["test", "qa", "verify"]):
        proposed_files = ["backend/tests/test_example.py"]
    elif any(kw in title_lower for kw in ["database", "db", "schema", "migration"]):
        proposed_files = ["backend/src/storage/database.py"]
    elif any(kw in title_lower for kw in ["doc", "readme", "report"]):
        proposed_files = ["README.md"]
    else:
        proposed_files = ["backend/src/api/routes.py"]

    patch_intent = (
        f"[MOCK] Implement changes for '{step_title}' following project conventions and "
        "the Source of Truth. Specific changes to be determined by operator review."
    )
    return AgentExecutionResult(
        summary=f"[MOCK] Advisory analysis for: {step_title}",
        analysis=(
            f"[MOCK] This is a deterministic mock result for task_type='{task_type}'. "
            f"Step '{step_title}' would require analysis of the linked requirements, "
            "review of the current codebase state, and a targeted patch proposal. "
            "No actual provider was called — this result is for UI testing only."
        ),
        proposed_files=proposed_files,
        patch_intent=patch_intent,
        risks=["[MOCK] Risk: changes may affect dependent steps.", "[MOCK] Risk: tests must be run after any patch."],
        test_suggestions=["[MOCK] Run full pytest suite after changes.", "[MOCK] Run tsc --noEmit to verify TypeScript."],
        questions=["[MOCK] Are the linked requirements fully specified?", "[MOCK] Are there guard results that need review?"],
        recommended_next_action="Review this mock output, then use the Patch Proposal form to create a real proposal.",
        can_feed_patch_draft=True,
    )


# ── Agent Execution Endpoints ─────────────────────────────────────────────────


@router.get("/api/runs/{run_id}/steps/{step_id}/agent-execution-context")
async def get_agent_execution_context(run_id: str, step_id: str):
    """Build and return AgentExecutionContext for a step. Read-only — no tool_calls created."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in run {run_id}.")

    project = get_project(run.project_id) if run.project_id else None
    tool_calls = list_tool_calls_for_run(run_id)

    agent_id, agent_name, task_type = _route_agent_for_step(
        step.title, step.input or "", "", None
    )

    context = _build_agent_execution_context(
        run, step, project, tool_calls,
        include_recent_tool_calls=True,
        include_patch_lifecycle=True,
        agent_id=agent_id,
        agent_name=agent_name,
        task_type=task_type,
    )
    return context


@router.post("/api/runs/{run_id}/steps/{step_id}/agent-executions/run")
async def run_agent_execution(run_id: str, step_id: str, req: AgentExecutionRequest):
    """Execute (or dry-run/mock) an agent task for a step.

    Modes:
    - dry_run: returns prompt_preview + context only; no tool_call; no provider call.
    - mock: returns deterministic mock result; optionally creates audit tool_call.
    - provider: calls Ollama (local only) if allow_provider_call=True; returns result.
      If Ollama unavailable, returns provider_unavailable status safely.
    """
    # ── Validate mode ────────────────────────────────────────────────────────
    if req.mode not in _AGENT_EXECUTION_MODES:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Invalid mode '{req.mode}'. Valid modes: dry_run, mock, provider.",
                "mode": req.mode,
            },
        )

    # ── Resolve run / step ───────────────────────────────────────────────────
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in run {run_id}.")

    project = get_project(run.project_id) if run.project_id else None
    tool_calls = list_tool_calls_for_run(run_id)

    # ── Route agent ──────────────────────────────────────────────────────────
    agent_id, agent_name, task_type = _route_agent_for_step(
        step.title, step.input or "", req.task_type, req.agent_id
    )

    # ── Build context ────────────────────────────────────────────────────────
    context = _build_agent_execution_context(
        run, step, project, tool_calls,
        include_recent_tool_calls=req.include_recent_tool_calls,
        include_patch_lifecycle=req.include_patch_lifecycle,
        agent_id=agent_id,
        agent_name=agent_name,
        task_type=task_type,
    )

    # ── Build prompt ─────────────────────────────────────────────────────────
    prompt_preview = _build_agent_prompt(context, req, agent_name)

    warnings: list[str] = []
    safety_notes: list[str] = [
        "Agent execution does not mutate files, create proposals, apply patches, "
        "run commands, or bypass approvals."
    ]

    # ── DRY RUN ──────────────────────────────────────────────────────────────
    if req.mode == "dry_run":
        return AgentExecutionResponse(
            run_id=run_id,
            step_id=step_id,
            agent_id=agent_id,
            mode="dry_run",
            status="planned",
            executed=False,
            provider_called=False,
            tool_call_id=None,
            context=context,
            result=None,
            prompt_preview=prompt_preview,
            warnings=warnings,
            safety_notes=safety_notes,
        )

    # ── MOCK ─────────────────────────────────────────────────────────────────
    if req.mode == "mock":
        result = _mock_agent_result(context, task_type)
        tool_call_id: str | None = None

        if req.persist_result:
            try:
                tc = create_tool_call(
                    run_id=run_id,
                    step_id=step_id,
                    project_id=run.project_id or "",
                    tool_name=_AGENT_EXECUTION_TOOL_NAME,
                    command="",
                    status="completed",
                    input_json=json.dumps({
                        "agent_id": agent_id,
                        "mode": "mock",
                        "task_type": task_type,
                        "user_instruction": req.user_instruction,
                    }),
                    output_json=json.dumps({
                        "summary": result.summary,
                        "patch_intent": result.patch_intent,
                        "proposed_files": result.proposed_files,
                        "can_feed_patch_draft": result.can_feed_patch_draft,
                    }),
                    risk_level="low",
                )
                tool_call_id = tc.id
            except Exception as exc:
                warnings.append(f"Could not persist audit tool_call: {exc}")

        return AgentExecutionResponse(
            run_id=run_id,
            step_id=step_id,
            agent_id=agent_id,
            mode="mock",
            status="completed",
            executed=True,
            provider_called=False,
            tool_call_id=tool_call_id,
            context=context,
            result=result,
            prompt_preview=prompt_preview,
            warnings=warnings,
            safety_notes=safety_notes,
        )

    # ── PROVIDER ─────────────────────────────────────────────────────────────
    # Only Ollama (local) is supported in v1. External providers (Claude, Codex)
    # are stubs — they do not execute and are not invoked here.
    if req.mode == "provider":
        if not req.allow_provider_call:
            raise HTTPException(
                status_code=403,
                detail={
                    "message": "Provider call requires allow_provider_call=true in request.",
                    "mode": "provider",
                },
            )

        # Reject explicitly requested unknown agent before any provider call.
        # _route_agent_for_step silently substitutes the inferred agent when the
        # requested agent_id is unknown, so we must re-check req.agent_id here
        # against the registry directly to return status="blocked" as expected.
        if req.agent_id and not get_agent(req.agent_id):
            return AgentExecutionResponse(
                run_id=run_id,
                step_id=step_id,
                agent_id=req.agent_id,
                mode="provider",
                status="blocked",
                executed=False,
                provider_called=False,
                context=context,
                result=None,
                prompt_preview=prompt_preview,
                warnings=[f"Unknown agent '{req.agent_id}' — cannot select provider model."],
                safety_notes=safety_notes,
            )

        # Verify the routed agent is valid (covers None/missing fallback edge cases).
        agent_obj = get_agent(agent_id)
        if not agent_obj:
            return AgentExecutionResponse(
                run_id=run_id,
                step_id=step_id,
                agent_id=agent_id,
                mode="provider",
                status="blocked",
                executed=False,
                provider_called=False,
                context=context,
                result=None,
                prompt_preview=prompt_preview,
                warnings=[f"Unknown agent '{agent_id}' — cannot select provider model."],
                safety_notes=safety_notes,
            )

        # Get config for Ollama base_url and model.
        cfg = get_config()
        ollama_base_url = cfg.get("ollama", {}).get("base_url", "http://localhost:11434")

        # Check health before attempting.
        try:
            ollama_healthy = await ollama.check_health(ollama_base_url)
        except Exception:
            ollama_healthy = False

        if not ollama_healthy:
            warnings.append("Ollama is not reachable. Start Ollama locally and retry.")
            return AgentExecutionResponse(
                run_id=run_id,
                step_id=step_id,
                agent_id=agent_id,
                mode="provider",
                status="provider_unavailable",
                executed=False,
                provider_called=False,
                context=context,
                result=None,
                prompt_preview=prompt_preview,
                warnings=warnings,
                safety_notes=safety_notes,
            )

        # Select model from agent's profile.
        cfg_ollama = cfg.get("ollama", {})
        model = (
            agent_obj.default_model
            or agent_obj.fast_model
            or cfg_ollama.get("default_model", "qwen2.5-coder:7b")
        )

        # Load agent-specific system instructions from markdown file.
        agent_system = load_agent_instructions(agent_id)
        if not agent_system:
            agent_system = (
                f"You are {agent_name}, a specialist AI agent in the AI Workbench system. "
                "Provide structured, actionable advisory output in JSON format."
            )

        raw_output: str = ""

        try:
            raw_output = await ollama.chat_completion(
                prompt=prompt_preview,
                system=agent_system,
                model=model,
                base_url=ollama_base_url,
                max_tokens=min(req.max_output_chars // 4, 4096),
            )
        except Exception as exc:
            warnings.append(f"Provider call failed: {exc}")
            return AgentExecutionResponse(
                run_id=run_id,
                step_id=step_id,
                agent_id=agent_id,
                mode="provider",
                status="failed",
                executed=False,
                provider_called=True,
                context=context,
                result=None,
                prompt_preview=prompt_preview,
                warnings=warnings,
                safety_notes=safety_notes,
            )

        # Parse the response — never raises.
        result = _parse_provider_response(raw_output, req.max_output_chars)

        tool_call_id = None
        if req.persist_result:
            try:
                tc = create_tool_call(
                    run_id=run_id,
                    step_id=step_id,
                    project_id=run.project_id or "",
                    tool_name=_AGENT_EXECUTION_TOOL_NAME,
                    command="",
                    status="completed",
                    input_json=json.dumps({
                        "agent_id": agent_id,
                        "mode": "provider",
                        "model": model,
                        "task_type": task_type,
                        "user_instruction": req.user_instruction,
                    }),
                    output_json=json.dumps({
                        "summary": result.summary,
                        "patch_intent": result.patch_intent,
                        "proposed_files": result.proposed_files,
                        "can_feed_patch_draft": result.can_feed_patch_draft,
                        "raw_chars": len(raw_output),
                    }),
                    risk_level="low",
                )
                tool_call_id = tc.id
            except Exception as exc:
                warnings.append(f"Could not persist audit tool_call: {exc}")

        return AgentExecutionResponse(
            run_id=run_id,
            step_id=step_id,
            agent_id=agent_id,
            mode="provider",
            status="completed",
            executed=True,
            provider_called=True,
            tool_call_id=tool_call_id,
            context=context,
            result=result,
            prompt_preview=prompt_preview,
            warnings=warnings,
            safety_notes=safety_notes,
        )


@router.post("/api/runs/{run_id}/execute-next-step")
async def execute_next_run_step(run_id: str, req: ExecuteNextStepRequest):
    """Execute the next pending run step through the existing agent harness.

    This is an operator shortcut. It does not apply patches or run commands.
    Default mode is deterministic `mock`, so it is fast and safe offline.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")
    if run.current_step_id:
        raise HTTPException(status_code=409, detail=f"Run already has active step {run.current_step_id}.")

    steps = list_run_steps(run_id)
    pending_steps = [step for step in steps if step.status == RunStatus.PENDING.value]
    if not pending_steps:
        raise HTTPException(status_code=400, detail="Run has no pending steps to execute.")

    step = pending_steps[0]
    started_at = datetime.now().isoformat()
    update_run_step(step.id, status=RunStatus.RUNNING.value, error="", started_at=step.started_at or started_at)
    update_run(run_id, current_step_id=step.id)

    agent_req = AgentExecutionRequest(
        agent_id=req.agent_id or step.agent_id or None,
        task_type=req.task_type or infer_task_type_for_step(step.title, step.input, step.agent_id),
        mode=req.mode,
        allow_provider_call=req.allow_provider_call,
        persist_result=req.persist_result,
        max_output_chars=req.max_output_chars,
        user_instruction=req.user_instruction or (
            "Execute this run step as an advisory agent pass. "
            "Return structured analysis, proposed files, risks, tests, and next action. "
            "Do not mutate files, run commands, create proposals, or bypass approvals."
        ),
        include_requirement_context=True,
        include_recent_tool_calls=True,
        include_patch_lifecycle=True,
    )

    try:
        execution = await run_agent_execution(run_id, step.id, agent_req)
        artifact_name = f"agent-execution-{step.id}.md"
        run_path = _run_path(run)
        run_path.mkdir(parents=True, exist_ok=True)
        (run_path / artifact_name).write_text(
            _format_agent_execution_artifact(step, execution),
            encoding="utf-8",
        )

        next_status = (
            RunStatus.COMPLETED.value
            if execution.status == "completed"
            else RunStatus.PENDING.value
            if execution.status in {"planned", "provider_unavailable", "blocked"}
            else RunStatus.FAILED.value
        )
        finished_at = datetime.now().isoformat() if next_status != RunStatus.PENDING.value else ""
        updated_step = update_run_step(
            step.id,
            status=next_status,
            output=_format_agent_execution_step_output(execution),
            error="" if next_status != RunStatus.FAILED.value else "; ".join(execution.warnings),
            finished_at=finished_at,
        )

        refreshed = get_run(run_id) or run
        artifacts = list(refreshed.artifacts)
        if artifact_name not in artifacts:
            artifacts.append(artifact_name)
        logs = list(refreshed.logs)
        logs.append(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"Executed next step {step.id} via agent harness ({execution.mode}/{execution.status})"
        )
        update_run(run_id, current_step_id="", artifacts=artifacts, logs=logs)

        message = (
            f"Executed step {step.id} with {execution.agent_id}."
            if execution.status == "completed"
            else f"Step {step.id} did not complete: {execution.status}."
        )
        return ExecuteNextStepResponse(
            run_id=run_id,
            step_id=step.id,
            step_title=step.title,
            status=execution.status,
            message=message,
            artifact=artifact_name,
            execution=execution,
            step=updated_step,
        )
    except Exception as exc:
        update_run_step(
            step.id,
            status=RunStatus.FAILED.value,
            error=str(exc),
            finished_at=datetime.now().isoformat(),
        )
        update_run(run_id, current_step_id="")
        raise


def _format_agent_execution_step_output(execution: AgentExecutionResponse) -> str:
    result = execution.result
    if not result:
        return (
            f"Agent execution status: {execution.status}\n"
            f"Mode: {execution.mode}\n"
            f"Warnings: {'; '.join(execution.warnings) if execution.warnings else 'none'}"
        )
    parts = [
        f"Agent: {execution.agent_id}",
        f"Mode: {execution.mode}",
        f"Status: {execution.status}",
        f"Summary: {result.summary}",
        f"Recommended next action: {result.recommended_next_action}",
    ]
    if result.proposed_files:
        parts.append("Proposed files:\n" + "\n".join(f"- {path}" for path in result.proposed_files))
    if result.risks:
        parts.append("Risks:\n" + "\n".join(f"- {risk}" for risk in result.risks))
    return "\n\n".join(parts)


def _format_agent_execution_artifact(step, execution: AgentExecutionResponse) -> str:
    result = execution.result
    return (
        "# Agent Execution Result\n\n"
        f"**Step ID:** {step.id}\n"
        f"**Step:** {step.title}\n"
        f"**Agent:** {execution.agent_id}\n"
        f"**Mode:** {execution.mode}\n"
        f"**Status:** {execution.status}\n"
        f"**Tool Call ID:** {execution.tool_call_id or 'none'}\n"
        f"**Provider Called:** {execution.provider_called}\n\n"
        "## Summary\n\n"
        f"{result.summary if result else 'No result produced.'}\n\n"
        "## Analysis\n\n"
        f"{result.analysis if result else ''}\n\n"
        "## Patch Intent\n\n"
        f"{result.patch_intent if result else ''}\n\n"
        "## Proposed Files\n\n"
        + (
            "\n".join(f"- `{path}`" for path in result.proposed_files)
            if result and result.proposed_files else "None."
        )
        + "\n\n## Risks\n\n"
        + (
            "\n".join(f"- {risk}" for risk in result.risks)
            if result and result.risks else "None."
        )
        + "\n\n## Test Suggestions\n\n"
        + (
            "\n".join(f"- {test}" for test in result.test_suggestions)
            if result and result.test_suggestions else "None."
        )
        + "\n\n## Questions\n\n"
        + (
            "\n".join(f"- {question}" for question in result.questions)
            if result and result.questions else "None."
        )
        + "\n\n## Recommended Next Action\n\n"
        f"{result.recommended_next_action if result else 'Review warnings and retry.'}\n\n"
        "## Warnings\n\n"
        + ("\n".join(f"- {warning}" for warning in execution.warnings) if execution.warnings else "None.")
        + "\n\n## Safety Notes\n\n"
        + ("\n".join(f"- {note}" for note in execution.safety_notes) if execution.safety_notes else "None.")
        + "\n"
    )


@router.get("/api/runs/{run_id}/steps/{step_id}/agent-executions")
async def list_agent_executions(run_id: str, step_id: str):
    """List previous agent execution audit tool_calls for a step. Read-only."""
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in run {run_id}.")

    step_calls = list_tool_calls_for_step(step_id)
    agent_exec_calls = [
        tc for tc in step_calls
        if tc.tool_name == _AGENT_EXECUTION_TOOL_NAME
    ]

    executions = []
    for tc in agent_exec_calls:
        inp = {}
        out = {}
        try:
            inp = json.loads(tc.input_json) if tc.input_json else {}
        except Exception:
            pass
        try:
            out = json.loads(tc.output_json) if tc.output_json else {}
        except Exception:
            pass
        executions.append({
            "tool_call_id": tc.id,
            "agent_id": inp.get("agent_id", ""),
            "mode": inp.get("mode", ""),
            "task_type": inp.get("task_type", ""),
            "status": tc.status,
            "created_at": tc.created_at,
            "summary": out.get("summary", ""),
            "can_feed_patch_draft": out.get("can_feed_patch_draft", False),
        })

    return AgentExecutionListResponse(
        run_id=run_id,
        step_id=step_id,
        executions=executions,
        total=len(executions),
        note=(
            "Lists agent-execution audit tool_calls only. "
            "dry_run mode does not create audit records."
            if not executions else ""
        ),
    )


# ── Agent Result → Patch Draft Bridge v1 ─────────────────────────────────────
#
# Safety contract (same as agent execution harness):
#   - No file mutation.
#   - No proposal creation.
#   - No apply.
#   - No rollback.
#   - No shell/command execution.
#   - No provider call.
#   - No execute_run, no asyncio.create_task.
#   - Pure read + deterministic text assembly.


def _build_agent_patch_draft_context(
    *,
    step_title: str,
    step_input_summary: str,
    requirement_ids: list[str],
    source_of_truth_summary: str,
    summary: str,
    analysis: str,
    patch_intent: str,
    proposed_files: list[str],
    risks: list[str],
    test_suggestions: list[str],
    questions: list[str],
    include_context: bool = True,
    include_risks: bool = True,
    include_tests: bool = True,
    max_context_chars: int = 12000,
) -> str:
    """Build a bounded patch draft context string from agent result fields.

    Pure function — no DB access, no provider calls, no mutation.
    """
    parts: list[str] = []

    parts.append("## Agent Result — Patch Context Draft")
    parts.append(
        "⚠ This is draft context only. It does not create a proposal, "
        "apply a patch, or bypass approvals. You must run the source-of-truth "
        "guard and create a guarded proposal manually."
    )
    parts.append(f"### Step\n{step_title}")

    if summary:
        parts.append(f"### Agent Summary\n{summary}")

    if patch_intent:
        parts.append(f"### Patch Intent\n{patch_intent}")

    if proposed_files and include_context:
        parts.append("### Proposed Files\n" + "\n".join(f"- {f}" for f in proposed_files))

    if analysis and include_context:
        parts.append(f"### Analysis\n{analysis[:1200]}")

    if requirement_ids and include_context:
        parts.append("### Linked Requirements\n" + ", ".join(requirement_ids))

    if source_of_truth_summary and include_context:
        parts.append(f"### Source of Truth (summary)\n{source_of_truth_summary[:600]}")

    if step_input_summary and include_context:
        parts.append(f"### Step Input (summary)\n{step_input_summary[:400]}")

    if risks and include_risks:
        parts.append("### Risks\n" + "\n".join(f"- {r}" for r in risks))

    if test_suggestions and include_tests:
        parts.append("### Test Suggestions\n" + "\n".join(f"- {t}" for t in test_suggestions))

    if questions:
        parts.append("### Open Questions\n" + "\n".join(f"- {q}" for q in questions))

    parts.append(
        "### Next Steps\n"
        "1. Review the patch intent and proposed files above.\n"
        "2. Fill `file_path`, `old_text`, and `new_text` in the patch form manually.\n"
        "3. Run the source-of-truth guard.\n"
        "4. Create a guarded proposal.\n"
        "5. Review, approve, apply, and test."
    )

    return "\n\n".join(parts)[:max_context_chars]


def _format_module_patch_context_section(module_context) -> str:
    """Format bounded module context for patch draft text.

    Pure formatter — no DB reads, no providers, no tools.
    """
    if not module_context or not module_context.has_active_module_map or not module_context.matched_modules:
        return ""

    parts: list[str] = ["### PROJECT MODULE MAP PATCH CONTEXT"]
    if module_context.module_summary:
        parts.append(module_context.module_summary[:500])

    for mod in module_context.matched_modules[:5]:
        name = str(mod.get("name") or mod.get("slug") or "Unknown module")[:80]
        module_type = str(mod.get("module_type") or "unknown")[:40]
        responsibilities = [str(item)[:100] for item in (mod.get("responsibilities") or [])[:3]]
        paths = [str(item)[:120] for item in (mod.get("paths") or [])[:8]]
        key_files = [str(item)[:120] for item in (mod.get("key_files") or [])[:8]]
        requirements = [str(item)[:40] for item in (mod.get("related_requirements") or [])[:8]]
        test_hints = [str(item)[:100] for item in (mod.get("test_hints") or [])[:3]]
        risks = [str(item)[:100] for item in (mod.get("risks") or [])[:3]]

        parts.append(f"- Module: {name}")
        parts.append(f"  Type: {module_type}")
        if responsibilities:
            parts.append(f"  Responsibilities: {', '.join(responsibilities)}")
        if paths:
            parts.append(f"  Paths: {', '.join(paths)}")
        if key_files:
            parts.append(f"  Key files: {', '.join(key_files)}")
        if requirements:
            parts.append(f"  Related requirements: {', '.join(requirements)}")
        if test_hints:
            parts.append(f"  Test hints: {', '.join(test_hints)}")
        if risks:
            parts.append(f"  Risks: {', '.join(risks)}")

    parts.append("Module map context is advisory only. It does not create a proposal or read file contents.")
    return "\n".join(parts)


def _append_bounded_patch_context_section(
    patch_context: str,
    section: str,
    max_context_chars: int,
) -> str:
    """Append section while preserving the caller's max_context_chars bound."""
    if not section:
        return patch_context[:max_context_chars]
    separator = "\n\n"
    if len(patch_context) + len(separator) + len(section) <= max_context_chars:
        return f"{patch_context}{separator}{section}"
    room = max_context_chars - len(separator) - len(section)
    if room <= 0:
        return section[:max_context_chars]
    return f"{patch_context[:room]}{separator}{section}"


@router.post("/api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft")
async def create_agent_result_patch_draft(
    run_id: str, step_id: str, req: AgentPatchDraftRequest
):
    """Build a patch draft context from an agent execution result.

    Accepts either an agent_execution_tool_call_id (loads stored audit) or a
    direct agent_result payload.

    Read-only — no tool_call created, no proposal, no apply, no provider call.
    """
    # ── Validate run / step ──────────────────────────────────────────────────
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found.")

    steps = list_run_steps(run_id)
    step = next((s for s in steps if s.id == step_id), None)
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found in run {run_id}.")

    safety_notes: list[str] = [
        "This only prepares patch context. It does not create a proposal, "
        "apply files, run commands, or bypass approvals."
    ]
    warnings: list[str] = []

    # ── Resolve agent result ─────────────────────────────────────────────────
    source_agent_execution_id: str | None = None

    # Paths: (A) load from stored tool_call, (B) use direct payload.
    summary = ""
    analysis = ""
    patch_intent = ""
    proposed_files: list[str] = []
    risks: list[str] = []
    test_suggestions: list[str] = []
    questions: list[str] = []

    if req.agent_execution_tool_call_id:
        # Path A: load from audit tool_call stored in this step.
        step_calls = list_tool_calls_for_step(step_id)
        tc = next(
            (c for c in step_calls if c.id == req.agent_execution_tool_call_id),
            None,
        )
        if not tc:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Agent execution tool_call '{req.agent_execution_tool_call_id}' "
                    f"not found for step {step_id}."
                ),
            )
        if tc.tool_name != _AGENT_EXECUTION_TOOL_NAME:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Tool call '{req.agent_execution_tool_call_id}' is not an "
                    f"agent-execution record (tool_name='{tc.tool_name}')."
                ),
            )
        # Parse stored output_json (audit stores: summary, patch_intent, proposed_files).
        out: dict = {}
        try:
            out = json.loads(tc.output_json) if tc.output_json else {}
        except Exception:
            out = {}
        summary = str(out.get("summary", ""))[:400]
        patch_intent = str(out.get("patch_intent", ""))[:800]
        raw_files = out.get("proposed_files", [])
        proposed_files = [str(f) for f in raw_files if isinstance(f, str)][:20]
        # analysis/risks/test_suggestions/questions are not stored in audit output;
        # they remain empty strings/lists — this is expected for the tool_call path.
        source_agent_execution_id = tc.id

    elif req.agent_result is not None:
        # Path B: use directly provided agent result.
        r = req.agent_result
        summary = str(r.summary or "")[:400]
        analysis = str(r.analysis or "")[:2000]
        patch_intent = str(r.patch_intent or "")[:800]
        proposed_files = list(r.proposed_files or [])[:20]
        risks = list(r.risks or [])[:20]
        test_suggestions = list(r.test_suggestions or [])[:20]
        questions = list(r.questions or [])[:20]

    else:
        raise HTTPException(
            status_code=400,
            detail=(
                "Either agent_execution_tool_call_id or agent_result must be provided."
            ),
        )

    # ── Check if result has useful content ────────────────────────────────────
    has_useful_content = bool(patch_intent or proposed_files or summary)
    if not has_useful_content:
        warnings.append(
            "Agent result has no patch_intent, proposed_files, or summary. "
            "The patch context will be minimal."
        )

    # ── Build requirement context from step ───────────────────────────────────
    step_input = step.input or ""
    step_input_summary = step_input[:400]
    requirement_ids: list[str] = []
    source_of_truth_summary = ""

    req_ctx = None
    try:
        req_ctx = parse_run_step_requirement_context(step_input)
    except Exception:
        req_ctx = None

    if req_ctx:
        requirement_ids = list(getattr(req_ctx, "requirement_ids", []) or [])
        source_of_truth_summary = str(getattr(req_ctx, "source_of_truth_summary", "") or "")[:600]

    # ── Build patch context string ────────────────────────────────────────────
    patch_context = _build_agent_patch_draft_context(
        step_title=step.title or "",
        step_input_summary=step_input_summary if req.include_context else "",
        requirement_ids=requirement_ids if req.include_context else [],
        source_of_truth_summary=source_of_truth_summary if req.include_context else "",
        summary=summary,
        analysis=analysis if req.include_context else "",
        patch_intent=patch_intent,
        proposed_files=proposed_files,
        risks=risks if req.include_risks else [],
        test_suggestions=test_suggestions if req.include_tests else [],
        questions=questions,
        include_context=req.include_context,
        include_risks=req.include_risks,
        include_tests=req.include_tests,
        max_context_chars=req.max_context_chars,
    )

    module_context = None
    module_context_summary = ""
    recommended_files_from_module_map: list[str] = []
    module_risks: list[str] = []
    module_test_hints: list[str] = []

    if run.project_id:
        try:
            module_context = _build_patch_draft_module_context(
                project_id=run.project_id,
                agent_result=req.agent_result
                if req.agent_result is not None
                else AgentExecutionResult(
                    summary=summary,
                    analysis=analysis,
                    patch_intent=patch_intent,
                    proposed_files=proposed_files,
                    risks=risks,
                    test_suggestions=test_suggestions,
                    questions=questions,
                    recommended_next_action="",
                    can_feed_patch_draft=has_useful_content,
                ),
                step_input=step_input,
                step_title=step.title or "",
                requirement_ids=requirement_ids or None,
            )
        except Exception as exc:
            module_context = None
            warnings.append(f"Module map context could not be built: {exc}")

    if module_context and module_context.has_active_module_map:
        module_context_summary = module_context.module_summary
        seen_files: set[str] = set()
        for mod in module_context.matched_modules[:5]:
            for path in (mod.get("key_files") or [])[:8]:
                if path not in seen_files:
                    recommended_files_from_module_map.append(path)
                    seen_files.add(path)
            for path in (mod.get("paths") or [])[:8]:
                if path not in seen_files:
                    recommended_files_from_module_map.append(path)
                    seen_files.add(path)
            for risk in (mod.get("risks") or [])[:3]:
                risk_text = str(risk)
                if risk_text and risk_text not in module_risks:
                    module_risks.append(risk_text)
            for hint in (mod.get("test_hints") or [])[:3]:
                hint_text = str(hint)
                if hint_text and hint_text not in module_test_hints:
                    module_test_hints.append(hint_text)

        recommended_files_from_module_map = recommended_files_from_module_map[:20]
        module_risks = module_risks[:10]
        module_test_hints = module_test_hints[:10]

        module_section = _format_module_patch_context_section(module_context)
        patch_context = _append_bounded_patch_context_section(
            patch_context,
            module_section,
            req.max_context_chars,
        )
        safety_notes.append(
            "Module map patch context is advisory only. It does not read file contents, "
            "create a proposal, or apply changes."
        )

    # ── Recommend file path only when exactly one proposed file ───────────────
    recommended_file_path: str | None = None
    if len(proposed_files) == 1:
        recommended_file_path = proposed_files[0]

    return AgentPatchDraftResponse(
        run_id=run_id,
        step_id=step_id,
        source_agent_execution_id=source_agent_execution_id,
        can_prefill_patch_context=has_useful_content,
        recommended_file_path=recommended_file_path,
        patch_context=patch_context,
        patch_summary=summary,
        module_context=module_context,
        module_context_summary=module_context_summary,
        recommended_files_from_module_map=recommended_files_from_module_map,
        module_risks=module_risks,
        module_test_hints=module_test_hints,
        proposed_files=proposed_files,
        risks=risks,
        test_suggestions=test_suggestions,
        questions=questions,
        guard_required=True,
        warnings=warnings,
        safety_notes=safety_notes,
    )


# ── Bounded Autonomous Patch-Test-Fix Loop v1 ─────────────────────────────────
#
# Safety invariants (enforced for this endpoint):
# - No auto-apply without an existing *approved* automation approval.
# - No auto-proposal in v1.
# - No auto-rollback.
# - No arbitrary command accepted from the request body.
# - No provider call unless allow_provider_call=True (not used in v1).
# - No Claude/Codex provider calls in v1.
# - No approval bypass, no guard bypass.
# - No execute_run, no asyncio.create_task.
# - All destructive actions require an existing approved AutomationApproval.
# - Guard is always revalidated before any destructive execution.
# - Start Task flow and confirmed-run behavior are not changed.

_BOUNDED_LOOP_SAFETY_NOTES: list[str] = [
    "Bounded Loop never bypasses guard, approval, safe-command policy, or current-state revalidation.",
    "It stops before destructive actions unless an approved automation approval exists.",
    "No provider is called unless allow_provider_call=True (not supported in v1).",
    "No arbitrary command is accepted from the loop request.",
    "No auto-proposal, no auto-rollback. execute_run and asyncio.create_task are never called.",
]


def _bounded_loop_find_approved_action(
    run_id: str,
    step_id: "str | None",
    action_type: str,
) -> "object | None":
    """Return an approved (not pending/rejected/executed) automation approval for the action."""
    approvals = _list_run_automation_approvals(run_id)
    for a in approvals:
        if a.action != action_type:
            continue
        if step_id and a.command != step_id:
            continue
        status_val = a.status.value if hasattr(a.status, "value") else str(a.status)
        if status_val == "approved":
            return a
    return None


def _bounded_loop_has_pending_approval(
    run_id: str,
    step_id: "str | None",
    action_type: str,
) -> bool:
    """Return True if a pending approval exists for the action."""
    approvals = _list_run_automation_approvals(run_id)
    for a in approvals:
        if a.action != action_type:
            continue
        if step_id and a.command != step_id:
            continue
        status_val = a.status.value if hasattr(a.status, "value") else str(a.status)
        if status_val == "pending":
            return True
    return False


def _bounded_loop_find_pending_approval(
    run_id: str,
    step_id: "str | None",
    action_type: str,
):
    """Return the first pending automation approval for this action, or None."""
    approvals = _list_run_automation_approvals(run_id)
    for a in approvals:
        if a.action != action_type:
            continue
        if step_id and a.command != step_id:
            continue
        status_val = a.status.value if hasattr(a.status, "value") else str(a.status)
        if status_val == "pending":
            return a
    return None


def _bounded_loop_queue_summary(items: list) -> "OperatorQueueSummary":
    """Build an OperatorQueueSummary from current queue items."""
    blocked = sum(1 for i in items if i.status == "blocked" or i.action_type in _AUTOMATION_BLOCKED)
    manual = sum(1 for i in items if _automation_classify(i.action_type) == "manual_required")
    done = sum(1 for i in items if i.action_type == "review_success")
    ready = len(items) - blocked - manual - done
    return OperatorQueueSummary(
        total_items=len(items),
        blocked_items=blocked,
        ready_items=max(0, ready),
        manual_required_items=manual,
        done_items=done,
    )


@router.post("/api/runs/{run_id}/automation/bounded-patch-test-fix-loop")
async def bounded_autonomous_patch_test_fix_loop(
    run_id: str,
    req: BoundedAutonomousLoopRequest,
) -> BoundedAutonomousLoopResponse:
    """Bounded autonomous patch-test-fix loop.

    Automatically advances through safe/read-only/low-risk stages and stops
    before dangerous actions, missing approvals, blocked guards, stale state,
    missing safe commands, or max iteration limits.

    Each iteration:
    1. Rebuilds operator queue.
    2. Picks the highest-priority item.
    3. If blocked  → stops (status=blocked).
    4. If manual/destructive:
       - Checks for an existing *approved* automation approval.
       - If approved: executes via existing helper (guard revalidated).
       - If pending: stops (status=stopped_for_approval).
       - If none: stops (status=stopped_for_approval).
    5. If safe/low-risk: delegates to _execute_single_automation_action.
    6. After run_tests: checks returncode; if failed and stop_on_test_failure → stops.
    7. Repeats up to max_iterations.

    Hard invariants (never violated):
    - No auto-proposal.
    - No auto-apply without an approved automation approval.
    - No auto-rollback.
    - No arbitrary command from request.
    - No provider call in v1 (allow_provider_call is parsed but not consumed).
    - No execute_run, no asyncio.create_task.
    - Guard is always revalidated before any destructive execution.
    """
    # ── Validate run ──────────────────────────────────────────────────────────
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if req.step_id:
        all_steps_init = list_run_steps(run_id)
        if not any(s.id == req.step_id for s in all_steps_init):
            raise HTTPException(status_code=404, detail="Step not found for this run")

    loop_warnings: list[str] = []
    loop_approvals_required: list[str] = []
    iterations_log: list[BoundedAutonomousLoopIteration] = []
    final_status = "completed"
    # Stop-reason tracking for GAP-011 (stopped_for_approval ambiguity)
    loop_stop_reason: "str | None" = None
    loop_blocked_action_type: "str | None" = None
    loop_pending_approval_id: "str | None" = None
    loop_pending_approval_action_type: "str | None" = None

    # ── Main loop ─────────────────────────────────────────────────────────────
    for iteration_num in range(1, req.max_iterations + 1):
        # Recompute state at start of each iteration
        all_steps = list_run_steps(run_id)
        all_run_calls = list_tool_calls_for_run(run_id)
        all_guard_records = list_guard_results(run_id=run_id, include_stale=True, limit=500)

        items = _build_queue_for_run(
            run_id=run_id,
            steps=all_steps,
            all_run_calls=all_run_calls,
            all_guard_records=all_guard_records,
            step_id_filter=req.step_id,
        )

        if not items:
            final_status = "no_safe_action" if not iterations_log else "completed"
            loop_stop_reason = "no_items"
            iter_record = BoundedAutonomousLoopIteration(
                iteration=iteration_num,
                status="no_safe_action",
                step_id=req.step_id,
                queue_action=None,
                warnings=["No items in operator queue."],
                safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
            )
            iterations_log.append(iter_record)
            break

        item = items[0]
        step = next((s for s in all_steps if s.id == item.step_id), None)
        if not step:
            final_status = "blocked"
            iter_record = BoundedAutonomousLoopIteration(
                iteration=iteration_num,
                status="blocked",
                step_id=item.step_id,
                queue_action=item.action_type,
                blocked_reasons=["Step not found in current run state."],
                safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
            )
            iterations_log.append(iter_record)
            break

        category = _automation_classify(item.action_type)
        iter_executed: list[AutomationActionResult] = []
        iter_approvals: list[str] = []
        iter_blocked: list[str] = []
        iter_warnings: list[str] = []
        iter_status = "completed"
        iter_test_status: "str | None" = None
        iter_next_action: "str | None" = None

        # ── BLOCKED ───────────────────────────────────────────────────────────
        if category == "blocked":
            if req.stop_on_blocked:
                final_status = "blocked"
                loop_stop_reason = "blocked_guard"
                loop_blocked_action_type = item.action_type
                iter_status = "blocked"
                iter_blocked.append(item.reason or f"Queue item '{item.action_type}' is blocked.")
                iter_record = BoundedAutonomousLoopIteration(
                    iteration=iteration_num,
                    status=iter_status,
                    step_id=item.step_id,
                    queue_action=item.action_type,
                    executed_actions=iter_executed,
                    blocked_reasons=iter_blocked,
                    warnings=iter_warnings,
                    safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                )
                iterations_log.append(iter_record)
                break
            # stop_on_blocked=False: record the block and continue
            iter_blocked.append(item.reason or f"Queue item '{item.action_type}' is blocked.")
            iter_warnings.append(f"Skipping blocked item '{item.action_type}'; stop_on_blocked=False.")
            iter_status = "blocked"
            iter_record = BoundedAutonomousLoopIteration(
                iteration=iteration_num,
                status=iter_status,
                step_id=item.step_id,
                queue_action=item.action_type,
                blocked_reasons=iter_blocked,
                warnings=iter_warnings,
                safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
            )
            iterations_log.append(iter_record)
            # Do NOT continue looping — blocked is terminal even with stop_on_blocked=False
            # (we can't skip a blocked item without fixing the underlying issue)
            final_status = "blocked"
            loop_stop_reason = "blocked_guard"
            loop_blocked_action_type = item.action_type
            break

        # ── MANUAL_REQUIRED / APPROVAL-GATED ─────────────────────────────────
        if category == "manual_required":
            # For execute_approval queue items the real approval is stored under
            # item.approval_action_type (e.g. "run_tests_manual"), not under
            # "execute_approval".  Resolve the underlying action type so that all
            # approval lookups find the correct record.  (GAP-011 fix — Fix 2)
            lookup_action = (
                item.approval_action_type or item.action_type
            ) if item.action_type == "execute_approval" else item.action_type

            # Check for an approved automation approval for this action
            approved_approval = _bounded_loop_find_approved_action(
                run_id, item.step_id, lookup_action
            )
            has_pending = _bounded_loop_has_pending_approval(
                run_id, item.step_id, lookup_action
            )

            if approved_approval is not None and lookup_action in _APPROVAL_EXECUTE_SUPPORTED:
                # Execute through the existing safe path with full revalidation
                project = get_project(run.project_id) if run.project_id else None
                approval_id = approved_approval.id

                exec_result_obj: "AutomationApprovalExecuteResponse | None" = None
                exec_error: "str | None" = None
                try:
                    if lookup_action == "run_tests_manual":
                        exec_result_obj = _execute_approved_run_tests(
                            run_id=run_id,
                            run=run,
                            step=step,
                            approval_id=approval_id,
                            all_run_calls=all_run_calls,
                        )
                    elif lookup_action == "apply_patch_manual":
                        if not project:
                            exec_error = "Run has no project_id; cannot execute apply_patch_manual."
                        else:
                            exec_result_obj = _execute_approved_apply_patch(
                                run_id=run_id,
                                run=run,
                                step=step,
                                project=project,
                                approval_id=approval_id,
                            )
                except HTTPException as exc:
                    exec_error = str(exc.detail)
                except Exception as exc:
                    exec_error = f"Unexpected error during approved execution: {exc}"

                if exec_error:
                    action_result = AutomationActionResult(
                        action_type=item.action_type,
                        step_id=item.step_id,
                        destination=item.destination,
                        status="failed",
                        executed=False,
                        risk_level="high" if item.is_destructive else "medium",
                        reason=exec_error,
                    )
                    iter_executed.append(action_result)
                    iter_status = "failed"
                    final_status = "failed"
                    iter_record = BoundedAutonomousLoopIteration(
                        iteration=iteration_num,
                        status=iter_status,
                        step_id=item.step_id,
                        queue_action=item.action_type,
                        executed_actions=iter_executed,
                        warnings=[exec_error],
                        safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                    )
                    iterations_log.append(iter_record)
                    break

                # Build result from exec_result_obj
                tc_id = getattr(exec_result_obj, "created_tool_call_id", None)
                exec_status = "executed" if (exec_result_obj and exec_result_obj.executed) else "failed"
                action_result = AutomationActionResult(
                    action_type=item.action_type,
                    step_id=item.step_id,
                    destination=item.destination,
                    status=exec_status,
                    executed=exec_result_obj.executed if exec_result_obj else False,
                    risk_level="high" if item.is_destructive else "medium",
                    reason=f"Executed approved action '{item.action_type}' via approval {approval_id[:8]}.",
                    created_tool_call_id=tc_id,
                    result_summary=getattr(exec_result_obj, "result_summary", None),
                )
                iter_executed.append(action_result)

                # Check test result if this was a test run
                if lookup_action == "run_tests_manual" and tc_id:
                    # Peek at the tool_call to get returncode
                    refreshed_calls = list_tool_calls_for_run(run_id)
                    test_tc = next((tc for tc in refreshed_calls if tc.id == tc_id), None)
                    if test_tc and test_tc.returncode is not None:
                        iter_test_status = "passed" if test_tc.returncode == 0 else "failed"
                    if iter_test_status == "failed" and req.stop_on_test_failure:
                        iter_status = "completed"
                        final_status = "stopped_for_approval"
                        loop_stop_reason = "test_failed"
                        iter_warnings.append("Tests failed. stop_on_test_failure=True — loop stopping.")
                        iter_record = BoundedAutonomousLoopIteration(
                            iteration=iteration_num,
                            status=iter_status,
                            step_id=item.step_id,
                            queue_action=item.action_type,
                            executed_actions=iter_executed,
                            test_status=iter_test_status,
                            warnings=iter_warnings,
                            safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                        )
                        iterations_log.append(iter_record)
                        break

                iter_status = exec_status
                iter_record = BoundedAutonomousLoopIteration(
                    iteration=iteration_num,
                    status=iter_status,
                    step_id=item.step_id,
                    queue_action=item.action_type,
                    executed_actions=iter_executed,
                    test_status=iter_test_status,
                    warnings=iter_warnings,
                    safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                )
                iterations_log.append(iter_record)
                # Continue to next iteration

            else:
                # No approved approval — stop for approval
                approval_label = (
                    f"{item.action_type} for step {item.step_id or 'unknown'}"
                )
                iter_approvals.append(approval_label)
                loop_approvals_required.append(approval_label)
                if has_pending:
                    iter_warnings.append(
                        f"Pending approval exists for '{lookup_action}'. Approve it first."
                    )
                    loop_stop_reason = "pending_approval"
                    # Find the pending approval ID for operator clarity.
                    # Use lookup_action (the underlying action type) — not "execute_approval".
                    _pa = _bounded_loop_find_pending_approval(run_id, item.step_id, lookup_action)
                    if _pa:
                        loop_pending_approval_id = _pa.id
                        loop_pending_approval_action_type = lookup_action
                else:
                    iter_warnings.append(
                        f"No approved approval found for '{lookup_action}'. "
                        "Create and approve one to proceed."
                    )
                    loop_stop_reason = "needs_approval"
                    loop_pending_approval_action_type = lookup_action
                iter_next_action = (
                    f"Create and approve an automation approval for '{lookup_action}' "
                    f"on step {item.step_id or 'unknown'}."
                )
                if req.stop_on_approval_required:
                    final_status = "stopped_for_approval"
                    iter_status = "stopped_for_approval"
                    iter_record = BoundedAutonomousLoopIteration(
                        iteration=iteration_num,
                        status=iter_status,
                        step_id=item.step_id,
                        queue_action=item.action_type,
                        approvals_required=iter_approvals,
                        next_recommended_action=iter_next_action,
                        warnings=iter_warnings,
                        safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                    )
                    iterations_log.append(iter_record)
                    break
                # stop_on_approval_required=False: record and stop anyway (cannot
                # skip a manual_required item without approval).
                iter_status = "stopped_for_approval"
                iter_record = BoundedAutonomousLoopIteration(
                    iteration=iteration_num,
                    status=iter_status,
                    step_id=item.step_id,
                    queue_action=item.action_type,
                    approvals_required=iter_approvals,
                    next_recommended_action=iter_next_action,
                    warnings=iter_warnings,
                    safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
                )
                iterations_log.append(iter_record)
                final_status = "stopped_for_approval"
                break

            continue  # next iteration

        # ── DIRECT_SAFE (readonly + low_risk) ────────────────────────────────
        # Execute via existing dispatcher — inherits all its safety guarantees.
        actions_this_iteration = 0
        while actions_this_iteration < req.max_actions_per_iteration:
            result = _execute_single_automation_action(
                run_id=run_id,
                run=run,
                step=step,
                item=item,
                dry_run=req.dry_run,
                allow_safe_commands=req.allow_safe_commands,
                allow_low_risk_tool_calls=req.allow_low_risk_tool_calls,
                all_run_calls=all_run_calls,
            )
            iter_executed.append(result)
            actions_this_iteration += 1

            if result.status in ("manual_required", "blocked"):
                iter_blocked.append(result.reason)
                # If the action is approval-eligible (e.g. run_tests_manual blocked because
                # allow_safe_commands=False) and stop_on_approval_required is set, surface
                # this as an approval-needed stop rather than a generic blocked stop.
                # (GAP-011 fix — Fix 3)
                if (
                    result.status == "blocked"
                    and item.action_type in _APPROVAL_ELIGIBLE_ACTION_TYPES
                    and req.stop_on_approval_required
                ):
                    _has_pending_a = _bounded_loop_has_pending_approval(
                        run_id, item.step_id, item.action_type
                    )
                    if _has_pending_a:
                        loop_stop_reason = "pending_approval"
                        _pa_a = _bounded_loop_find_pending_approval(
                            run_id, item.step_id, item.action_type
                        )
                        if _pa_a:
                            loop_pending_approval_id = _pa_a.id
                            loop_pending_approval_action_type = item.action_type
                    else:
                        loop_stop_reason = "needs_approval"
                        loop_pending_approval_action_type = item.action_type
                    final_status = "stopped_for_approval"
                    iter_status = "stopped_for_approval"
                else:
                    final_status = "blocked" if result.status == "blocked" else "stopped_for_approval"
                    iter_status = result.status
                break

            if result.status == "failed":
                iter_status = "failed"
                final_status = "failed"
                break

            if result.status == "no_action":
                iter_status = "completed"
                break

            # Check test result
            if item.action_type == "run_tests_manual" and result.created_tool_call_id:
                refreshed_calls = list_tool_calls_for_run(run_id)
                test_tc = next(
                    (tc for tc in refreshed_calls if tc.id == result.created_tool_call_id),
                    None,
                )
                if test_tc and test_tc.returncode is not None:
                    iter_test_status = "passed" if test_tc.returncode == 0 else "failed"
                if iter_test_status == "failed" and req.stop_on_test_failure:
                    iter_warnings.append("Tests failed. stop_on_test_failure=True.")
                    iter_status = "completed"
                    break

            # executed — break inner loop (each iteration does ONE action from the queue)
            iter_status = "completed"
            break

        # If inner loop stopped due to blocked/failed/stopped_for_approval, break outer loop
        if iter_status in ("blocked", "failed", "stopped_for_approval"):
            iter_record = BoundedAutonomousLoopIteration(
                iteration=iteration_num,
                status=iter_status,
                step_id=item.step_id,
                queue_action=item.action_type,
                executed_actions=iter_executed,
                blocked_reasons=iter_blocked,
                test_status=iter_test_status,
                warnings=iter_warnings,
                safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
            )
            iterations_log.append(iter_record)
            break

        iter_record = BoundedAutonomousLoopIteration(
            iteration=iteration_num,
            status=iter_status,
            step_id=item.step_id,
            queue_action=item.action_type,
            executed_actions=iter_executed,
            test_status=iter_test_status,
            warnings=iter_warnings,
            safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
        )
        iterations_log.append(iter_record)

        # Check test failure stop BEFORE next iteration
        if iter_test_status == "failed" and req.stop_on_test_failure:
            final_status = "stopped_for_approval"
            loop_stop_reason = "test_failed"
            break

    else:
        # Exhausted max_iterations
        if final_status == "completed":
            final_status = "max_iterations_reached"
            loop_stop_reason = "max_iterations"

    # ── Build final queue state ───────────────────────────────────────────────
    final_steps = list_run_steps(run_id)
    final_calls = list_tool_calls_for_run(run_id)
    final_guards = list_guard_results(run_id=run_id, include_stale=True, limit=500)
    final_items = _build_queue_for_run(
        run_id=run_id,
        steps=final_steps,
        all_run_calls=final_calls,
        all_guard_records=final_guards,
        step_id_filter=req.step_id,
    )
    final_summary = _bounded_loop_queue_summary(final_items)

    # Determine final recommended action
    final_recommended: "str | None" = None
    if final_items:
        top = final_items[0]
        top_cat = _automation_classify(top.action_type)
        if top_cat == "manual_required":
            final_recommended = (
                f"Manual action required: '{top.action_type}' for step {top.step_id}. "
                "Create and approve an automation approval to proceed."
            )
        elif top_cat == "blocked":
            final_recommended = (
                f"Resolve blocker for step {top.step_id}: {top.reason}"
            )
        else:
            final_recommended = f"Next safe action: '{top.action_type}' for step {top.step_id}."

    # Derive stop_reason from final_status if not already set by a specific branch
    if loop_stop_reason is None:
        _stop_reason_map = {
            "completed": "completed",
            "no_safe_action": "no_items",
            "stopped_for_approval": "pending_approval",
            "blocked": "blocked_guard",
            "max_iterations_reached": "max_iterations",
            "failed": "action_failed",
        }
        loop_stop_reason = _stop_reason_map.get(final_status, final_status)

    return BoundedAutonomousLoopResponse(
        run_id=run_id,
        step_id=req.step_id,
        dry_run=req.dry_run,
        status=final_status,
        iterations=iterations_log,
        final_queue_summary=final_summary,
        final_recommended_action=final_recommended,
        approvals_required=loop_approvals_required,
        warnings=loop_warnings,
        safety_notes=_BOUNDED_LOOP_SAFETY_NOTES,
        stop_reason=loop_stop_reason,
        blocked_action_type=loop_blocked_action_type,
        pending_approval_id=loop_pending_approval_id,
        pending_approval_action_type=loop_pending_approval_action_type,
    )


# ── Full Delivery Loop v1 ─────────────────────────────────────────────────────

_DELIVERY_SAFETY_NOTES: list[str] = [
    "Delivery summary is read-only — no file mutations, no commands, no providers.",
    "No auto-apply, no auto-proposal, no auto-rollback, no guard bypass.",
    "All data is derived from existing run/steps/tool_calls/guard_results/approvals.",
]

_DELIVERY_READINESS_ORDER: list[str] = [
    "blocked",
    "tests_failed",
    "awaiting_approval",
    "needs_tests",
    "in_progress",
    "not_started",
    "delivered_with_warnings",
    "ready_for_review",
]


def _delivery_json_safe(raw: str) -> dict:
    """Parse JSON string to dict safely; return {} on error."""
    if not raw:
        return {}
    try:
        val = json.loads(raw)
        return val if isinstance(val, dict) else {}
    except Exception:
        return {}


def _delivery_extract_changed_files(tool_calls: list) -> list[str]:
    """Extract changed file paths from propose-patch and apply-patch tool_calls."""
    paths: set[str] = set()
    for tc in tool_calls:
        if tc.tool_name not in ("propose-patch", "apply-patch"):
            continue
        in_obj = _delivery_json_safe(tc.input_json)
        out_obj = _delivery_json_safe(tc.output_json)
        # From operations list in input/output
        for ops_src in (in_obj.get("operations") or [], out_obj.get("operations") or []):
            if not isinstance(ops_src, list):
                continue
            for op in ops_src:
                if not isinstance(op, dict):
                    continue
                for key in ("file_path", "old_path", "new_path", "path"):
                    val = op.get(key)
                    if val and isinstance(val, str) and val.strip():
                        paths.add(val.strip())
        # From apply-patch output.files_changed or files list
        for key in ("files_changed", "files", "changed_files"):
            val = out_obj.get(key)
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, str) and item.strip():
                        paths.add(item.strip())
                    elif isinstance(item, dict):
                        for fk in ("path", "file_path", "name"):
                            fv = item.get(fk)
                            if fv and isinstance(fv, str):
                                paths.add(fv.strip())
    return sorted(paths)


_DELIVERY_MODULE_MAX_MODULES = 20
_DELIVERY_MODULE_MAX_FILES = 30
_DELIVERY_MODULE_MAX_WARNINGS = 30
_DELIVERY_MODULE_MAX_TESTS = 20


def _delivery_unique_strings(values: list[str], limit: int) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean and clean not in seen:
            selected.append(clean)
            seen.add(clean)
        if len(selected) >= limit:
            break
    return selected


def _delivery_module_name(value: dict) -> str:
    return str(value.get("name") or value.get("slug") or value.get("id") or "").strip()


def _delivery_module_names(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    names: list[str] = []
    for value in values:
        if isinstance(value, dict):
            name = _delivery_module_name(value)
            if name:
                names.append(name)
        elif isinstance(value, str):
            names.append(value)
    return names


def _delivery_policy_values(policy: dict, key: str) -> list[str]:
    values = policy.get(key)
    if isinstance(values, list):
        return [v for v in values if isinstance(v, str)]
    return []


def _delivery_file_matches_module_map(active_module_map, file_path: str) -> bool:
    if not active_module_map or not file_path:
        return False
    return bool(_find_modules_for_paths(active_module_map, [file_path]))


def build_delivery_module_summary(
    run,
    steps: list,
    tool_calls: list,
    active_module_map=None,
) -> RunModuleDeliverySummary:
    """Build module awareness for delivery reporting from existing metadata only."""
    from src.orchestrator.project_intake import parse_run_step_requirement_context

    per_step: list[StepModuleDeliverySummary] = []
    all_touched: list[str] = []
    all_expected: list[str] = []
    all_unknown: list[str] = []
    all_sensitive: list[str] = []
    all_warnings: list[str] = []
    all_risks: list[str] = []
    all_tests: list[str] = []
    blocked_count = 0
    has_module_data = False

    for step in steps:
        step_calls = [tc for tc in tool_calls if getattr(tc, "step_id", "") == step.id]
        changed_files = _delivery_extract_changed_files(step_calls)
        touched_modules: list[str] = []
        expected_modules: list[str] = []
        touched_files: list[str] = list(changed_files)
        unknown_files: list[str] = []
        policy_verdicts: list[str] = []
        module_warnings: list[str] = []
        module_risks: list[str] = []
        module_test_hints: list[str] = []
        sensitive_modules: list[str] = []

        for tc in step_calls:
            out_obj = _delivery_json_safe(getattr(tc, "output_json", "") or "")
            awareness = out_obj.get("module_awareness")
            if isinstance(awareness, dict):
                has_module_data = has_module_data or bool(awareness.get("has_active_module_map"))
                touched_modules.extend(_delivery_module_names(awareness.get("touched_modules")))
                expected_modules.extend(_delivery_module_names(awareness.get("expected_modules")))
                aw_files = awareness.get("touched_files")
                if isinstance(aw_files, list):
                    touched_files.extend([f for f in aw_files if isinstance(f, str)])
                module_warnings.extend(_delivery_policy_values(awareness, "warnings"))
                module_risks.extend(_delivery_policy_values(awareness, "module_risks"))
                module_test_hints.extend(_delivery_policy_values(awareness, "module_test_hints"))

            policy = out_obj.get("module_policy")
            if isinstance(policy, dict):
                has_module_data = True
                verdict = policy.get("verdict")
                if isinstance(verdict, str) and verdict.strip():
                    policy_verdicts.append(verdict.strip())
                    if verdict.strip() == "blocked":
                        blocked_count += 1
                module_warnings.extend(_delivery_policy_values(policy, "reasons"))
                module_test_hints.extend(_delivery_policy_values(policy, "recommended_tests"))
                unknown_files.extend(_delivery_policy_values(policy, "unknown_files"))
                sensitive_modules.extend(_delivery_policy_values(policy, "sensitive_modules"))

            module_context = out_obj.get("module_context")
            if isinstance(module_context, dict):
                has_module_data = has_module_data or bool(module_context.get("has_active_module_map"))
                touched_modules.extend(_delivery_module_names(module_context.get("matched_modules")))
                matched_paths = module_context.get("matched_paths")
                if isinstance(matched_paths, list):
                    touched_files.extend([p for p in matched_paths if isinstance(p, str)])
                module_summary = module_context.get("module_summary")
                if isinstance(module_summary, str) and module_summary.strip():
                    module_warnings.append(module_summary.strip())

            for key, target in (
                ("recommended_files_from_module_map", touched_files),
                ("module_risks", module_risks),
                ("module_test_hints", module_test_hints),
            ):
                value = out_obj.get(key)
                if isinstance(value, list):
                    target.extend([item for item in value if isinstance(item, str)])

        if active_module_map:
            req_ctx = parse_run_step_requirement_context(step.input or "")
            req_ids = list(req_ctx.requirement_ids or [])
            if req_ids and not expected_modules:
                expected_modules.extend(
                    _delivery_module_name(mod.model_dump(mode="json"))
                    for mod in _find_modules_for_req_ids(active_module_map, req_ids)
                )
            if changed_files and not touched_modules:
                touched_modules.extend(
                    _delivery_module_name(mod.model_dump(mode="json"))
                    for mod in _find_modules_for_paths(active_module_map, changed_files)
                )
            for file_path in changed_files:
                if not _delivery_file_matches_module_map(active_module_map, file_path):
                    unknown_files.append(file_path)

        step_summary = StepModuleDeliverySummary(
            step_id=step.id,
            step_title=step.title or "",
            touched_modules=_delivery_unique_strings(touched_modules, _DELIVERY_MODULE_MAX_MODULES),
            expected_modules=_delivery_unique_strings(expected_modules, _DELIVERY_MODULE_MAX_MODULES),
            touched_files=_delivery_unique_strings(touched_files, _DELIVERY_MODULE_MAX_FILES),
            unknown_files=_delivery_unique_strings(unknown_files, _DELIVERY_MODULE_MAX_FILES),
            module_policy_verdicts=_delivery_unique_strings(policy_verdicts, _DELIVERY_MODULE_MAX_WARNINGS),
            module_warnings=_delivery_unique_strings(module_warnings, _DELIVERY_MODULE_MAX_WARNINGS),
            module_risks=_delivery_unique_strings(module_risks, _DELIVERY_MODULE_MAX_WARNINGS),
            module_test_hints=_delivery_unique_strings(module_test_hints, _DELIVERY_MODULE_MAX_TESTS),
        )
        if (
            step_summary.touched_modules
            or step_summary.expected_modules
            or step_summary.touched_files
            or step_summary.unknown_files
            or step_summary.module_policy_verdicts
            or step_summary.module_warnings
            or step_summary.module_risks
            or step_summary.module_test_hints
        ):
            has_module_data = True

        per_step.append(step_summary)
        all_touched.extend(step_summary.touched_modules)
        all_expected.extend(step_summary.expected_modules)
        all_unknown.extend(step_summary.unknown_files)
        all_sensitive.extend(sensitive_modules)
        all_warnings.extend(step_summary.module_warnings)
        all_risks.extend(step_summary.module_risks)
        all_tests.extend(step_summary.module_test_hints)

    return RunModuleDeliverySummary(
        has_module_data=has_module_data,
        touched_modules=_delivery_unique_strings(all_touched, _DELIVERY_MODULE_MAX_MODULES),
        expected_modules=_delivery_unique_strings(all_expected, _DELIVERY_MODULE_MAX_MODULES),
        unknown_files=_delivery_unique_strings(all_unknown, _DELIVERY_MODULE_MAX_FILES),
        sensitive_modules=_delivery_unique_strings(all_sensitive, _DELIVERY_MODULE_MAX_MODULES),
        warning_count=len(_delivery_unique_strings(all_warnings + all_risks, _DELIVERY_MODULE_MAX_WARNINGS)),
        blocked_policy_count=blocked_count,
        recommended_tests=_delivery_unique_strings(all_tests, _DELIVERY_MODULE_MAX_TESTS),
        per_step=per_step,
    )


def _delivery_readiness_severity(r: str) -> int:
    """Lower number = worse (more critical) — used to pick most conservative status."""
    order = {
        "blocked": 0,
        "tests_failed": 1,
        "awaiting_approval": 2,
        "needs_tests": 3,
        "in_progress": 4,
        "not_started": 5,
        "delivered_with_warnings": 6,
        "ready_for_review": 7,
    }
    return order.get(r, 4)


def _delivery_build_step_summary(
    step,
    step_calls: list,
    step_guard_records: list,
    step_approvals: list,
) -> StepDeliverySummary:
    """Build a StepDeliverySummary from step data — pure, no DB, no tools."""
    from src.orchestrator.project_intake import parse_run_step_requirement_context

    warnings: list[str] = []
    issues: list[str] = []

    # ── Requirement IDs ───────────────────────────────────────────────────────
    req_ctx = parse_run_step_requirement_context(step.input or "")
    requirement_ids: list[str] = list(req_ctx.requirement_ids or [])
    if not requirement_ids:
        warnings.append("No requirement IDs linked to this step.")

    # ── Tool call classification ───────────────────────────────────────────────
    proposals = [tc for tc in step_calls if tc.tool_name == "propose-patch"]
    applies = [tc for tc in step_calls if tc.tool_name == "apply-patch"]
    test_runs = [tc for tc in step_calls if tc.tool_name == "run-command"]
    fix_drafts = [tc for tc in step_calls if tc.tool_name in ("failure-to-fix-draft", "analyze-command-result")]

    # ── Guard status ──────────────────────────────────────────────────────────
    # Sort guard records by created_at descending; latest is most relevant
    sorted_guards = sorted(
        step_guard_records,
        key=lambda g: getattr(g, "created_at", "") or "",
        reverse=True,
    )
    guard_status = "none"
    if sorted_guards:
        latest = sorted_guards[0]
        is_stale = getattr(latest, "is_stale", False)
        decision_raw = getattr(latest, "result_snapshot", None)
        decision = ""
        if decision_raw:
            d = getattr(decision_raw, "decision", None)
            decision = (d.value if hasattr(d, "value") else str(d)).lower() if d else ""
        if is_stale:
            guard_status = "stale"
        elif decision == "blocked":
            guard_status = "blocked"
        elif decision == "warning":
            guard_status = "warning"
        elif decision == "allowed":
            guard_status = "allowed"
        else:
            guard_status = "unknown"

    # Check if ALL guards are stale (resolve_blocker condition)
    all_stale = bool(sorted_guards) and all(getattr(g, "is_stale", False) for g in sorted_guards)

    # ── Proposal status ───────────────────────────────────────────────────────
    proposal_status = "proposed" if proposals else "none"

    # ── Apply status ──────────────────────────────────────────────────────────
    apply_status = "none"
    latest_apply_time = ""
    if applies:
        apply_status = "applied"
        latest_apply_time = max((getattr(a, "created_at", "") or "") for a in applies)

    # ── Test status ───────────────────────────────────────────────────────────
    test_status = "none"
    if test_runs:
        # Consider only test runs after the latest apply (if any)
        if latest_apply_time:
            post_apply_tests = [
                tc for tc in test_runs
                if (getattr(tc, "created_at", "") or "") >= latest_apply_time
            ]
        else:
            post_apply_tests = test_runs
        if post_apply_tests:
            latest_test = sorted(
                post_apply_tests,
                key=lambda tc: getattr(tc, "created_at", "") or "",
                reverse=True,
            )[0]
            rc = getattr(latest_test, "returncode", None)
            if rc is None:
                test_status = "none"
            elif rc == 0:
                test_status = "passed"
            else:
                test_status = "failed"

    # ── Fix draft status ──────────────────────────────────────────────────────
    fix_status = "drafted" if fix_drafts else "none"

    # ── Approval status ───────────────────────────────────────────────────────
    approval_status = "none"
    if step_approvals:
        statuses = []
        for a in step_approvals:
            sv = a.status.value if hasattr(a.status, "value") else str(a.status)
            statuses.append(sv)
        if "approved" in statuses:
            approval_status = "approved"
        elif "executed" in statuses:
            approval_status = "executed"
        elif "pending" in statuses:
            approval_status = "pending"
        elif "rejected" in statuses:
            approval_status = "rejected"

    # ── Changed files ─────────────────────────────────────────────────────────
    changed_files = _delivery_extract_changed_files(step_calls)

    # ── Readiness classification ──────────────────────────────────────────────
    has_activity = bool(proposals or applies or test_runs or sorted_guards or step_approvals)

    readiness: str
    if not has_activity:
        readiness = "not_started"
    elif guard_status in ("blocked", "stale") or all_stale:
        # Guard failures always take priority.
        readiness = "blocked"
        issues.append(
            f"Guard is {'stale' if guard_status == 'stale' else 'blocked'} — resolve before proceeding."
        )
    elif test_status == "failed":
        # Failed tests take priority over approval pending.
        readiness = "tests_failed"
        issues.append("Latest test run after apply failed.")
    elif approval_status == "pending":
        # Pending approval is a blocker unless guard is blocked or tests failed.
        readiness = "awaiting_approval"
        issues.append("A manual approval is pending before continuing.")
    elif apply_status == "none":
        readiness = "in_progress"
        if proposal_status == "none":
            issues.append("No proposal or apply found — step is in progress.")
    elif test_status == "none" and test_runs:
        # tests ran but none after the apply
        readiness = "needs_tests"
        issues.append("Tests were run but no test after latest apply detected.")
    elif apply_status == "applied" and test_status == "none" and not test_runs:
        readiness = "needs_tests"
        issues.append("Patch applied but no test run detected.")
    elif test_status == "passed":
        # Check for any remaining warnings
        step_warnings = list(warnings)
        if not requirement_ids:
            step_warnings.append("No requirement IDs linked.")
        if guard_status not in ("allowed", "none"):
            step_warnings.append(f"Guard status: {guard_status}")
        if step_warnings:
            readiness = "delivered_with_warnings"
        else:
            readiness = "ready_for_review"
    else:
        readiness = "in_progress"

    # ── Next action ───────────────────────────────────────────────────────────
    next_action: str | None = None
    if readiness == "not_started":
        next_action = "Run guard check and create a proposal."
    elif readiness == "blocked":
        next_action = "Resolve the blocked/stale guard before continuing."
    elif readiness == "awaiting_approval":
        next_action = "Review and execute the pending approval before continuing."
    elif readiness == "in_progress":
        if proposal_status == "none":
            next_action = "Create a proposal, then apply and test."
        else:
            next_action = "Apply the proposal and run tests."
    elif readiness == "needs_tests":
        next_action = "Run tests to validate the applied patch."
    elif readiness == "tests_failed":
        next_action = "Fix failing tests or patch issues, then re-run tests."
    elif readiness in ("ready_for_review", "delivered_with_warnings"):
        next_action = "Review and approve delivery."

    return StepDeliverySummary(
        step_id=step.id,
        step_title=step.title or "",
        status=step.status or "",
        readiness=readiness,
        requirement_ids=requirement_ids,
        guard_status=guard_status,
        proposal_status=proposal_status,
        apply_status=apply_status,
        test_status=test_status,
        fix_status=fix_status,
        approval_status=approval_status,
        changed_files=changed_files,
        unresolved_issues=issues,
        warnings=warnings,
        recommended_next_action=next_action,
    )


def _delivery_aggregate_readiness(step_summaries: list[StepDeliverySummary]) -> str:
    """Return the most conservative readiness across all steps."""
    if not step_summaries:
        return "not_started"
    return min(
        step_summaries,
        key=lambda s: _delivery_readiness_severity(s.readiness),
    ).readiness


def _delivery_build_run_summary(
    run,
    project,
    steps: list,
    step_summaries: list[StepDeliverySummary],
    all_guards: list,
    all_approvals: list,
    all_calls: list,
    module_summary: RunModuleDeliverySummary | None = None,
) -> RunDeliverySummary:
    """Build the RunDeliverySummary from aggregated step data."""
    readiness = _delivery_aggregate_readiness(step_summaries)

    ready = sum(1 for s in step_summaries if s.readiness in ("ready_for_review", "delivered_with_warnings"))
    blocked = sum(1 for s in step_summaries if s.readiness == "blocked")
    needs_tests = sum(1 for s in step_summaries if s.readiness == "needs_tests")
    failed_tests = sum(1 for s in step_summaries if s.readiness == "tests_failed")
    approval_pending = sum(1 for s in step_summaries if s.approval_status == "pending")

    all_changed: set[str] = set()
    for s in step_summaries:
        all_changed.update(s.changed_files)

    all_req_ids: set[str] = set()
    for s in step_summaries:
        all_req_ids.update(s.requirement_ids)

    issues: list[str] = []
    warnings: list[str] = []
    for s in step_summaries:
        issues.extend(s.unresolved_issues)
        warnings.extend(s.warnings)

    unlinked = [s.step_title for s in step_summaries if not s.requirement_ids]
    if unlinked:
        warnings.append(f"Steps with no requirement IDs: {', '.join(unlinked)}")

    # Determine recommended action from worst step
    next_action: str | None = None
    if readiness == "blocked":
        blocked_steps = [s for s in step_summaries if s.readiness == "blocked"]
        if blocked_steps:
            next_action = blocked_steps[0].recommended_next_action
    elif readiness == "tests_failed":
        failed_steps = [s for s in step_summaries if s.readiness == "tests_failed"]
        if failed_steps:
            next_action = failed_steps[0].recommended_next_action
    elif readiness == "awaiting_approval":
        awaiting_steps = [s for s in step_summaries if s.readiness == "awaiting_approval"]
        if awaiting_steps:
            next_action = awaiting_steps[0].recommended_next_action
    elif readiness == "needs_tests":
        needs_steps = [s for s in step_summaries if s.readiness == "needs_tests"]
        if needs_steps:
            next_action = needs_steps[0].recommended_next_action
    elif readiness in ("ready_for_review", "delivered_with_warnings"):
        next_action = "All actionable steps are ready. Review and approve delivery."
    elif readiness == "in_progress":
        next_action = "Continue patch-test-fix loop for remaining steps."
    else:
        next_action = "Start the patch-test-fix loop."

    proposals_total = sum(1 for tc in all_calls if tc.tool_name == "propose-patch")
    applies_total = sum(1 for tc in all_calls if tc.tool_name == "apply-patch")
    tests_total = sum(1 for tc in all_calls if tc.tool_name == "run-command")

    return RunDeliverySummary(
        run_id=run.id,
        project_id=getattr(run, "project_id", None) or None,
        project_name=getattr(project, "name", None) if project else None,
        readiness=readiness,
        total_steps=len(steps),
        ready_steps=ready,
        blocked_steps=blocked,
        needs_test_steps=needs_tests,
        failed_test_steps=failed_tests,
        approval_pending_steps=approval_pending,
        changed_files=sorted(all_changed),
        requirement_ids=sorted(all_req_ids),
        guards_total=len(all_guards),
        proposals_total=proposals_total,
        applies_total=applies_total,
        tests_total=tests_total,
        approvals_total=len(all_approvals),
        unresolved_issues=list(dict.fromkeys(issues)),
        warnings=list(dict.fromkeys(warnings)),
        recommended_next_action=next_action,
        module_summary=module_summary,
    )


def _delivery_build_markdown(
    run,
    project,
    summary: RunDeliverySummary,
    step_summaries: list[StepDeliverySummary],
    req: DeliveryReportRequest,
    generated_at: str,
) -> str:
    """Generate a bounded deterministic markdown delivery report."""
    lines: list[str] = []

    lines.append("# Delivery Report")
    lines.append("")
    lines.append("## Run Summary")
    lines.append("")
    lines.append(f"- **Run ID:** `{run.id}`")
    lines.append(f"- **Project:** {summary.project_name or '(none)'}")
    lines.append(f"- **Readiness:** `{summary.readiness}`")
    lines.append(f"- **Generated at:** {generated_at}")
    lines.append(f"- **Total steps:** {summary.total_steps}")
    lines.append(
        f"- **Ready:** {summary.ready_steps} | "
        f"**Blocked:** {summary.blocked_steps} | "
        f"**Needs tests:** {summary.needs_test_steps} | "
        f"**Failed tests:** {summary.failed_test_steps}"
    )
    lines.append(f"- **Approval pending steps:** {summary.approval_pending_steps}")
    lines.append(f"- **Run prompt:** {(run.prompt or '')[:200]}")
    lines.append("")

    lines.append("## Requirements Coverage")
    lines.append("")
    if summary.requirement_ids:
        lines.append(f"**Requirement IDs covered:** {', '.join(summary.requirement_ids)}")
    else:
        lines.append("**No requirement IDs linked to any step.**")
    if summary.warnings:
        lines.append("")
        lines.append("**Warnings:**")
        for w in summary.warnings[:10]:
            lines.append(f"- {w}")
    lines.append("")

    lines.append("## Module Awareness")
    lines.append("")
    module_summary = summary.module_summary
    if module_summary and module_summary.has_module_data:
        if module_summary.touched_modules:
            lines.append(f"- **Touched modules:** {', '.join(module_summary.touched_modules[:20])}")
        if module_summary.expected_modules:
            lines.append(f"- **Expected modules:** {', '.join(module_summary.expected_modules[:20])}")
        if module_summary.unknown_files:
            lines.append("- **Unknown files:**")
            for path in module_summary.unknown_files[:30]:
                lines.append(f"  - `{path}`")
        if module_summary.sensitive_modules:
            lines.append(f"- **Sensitive modules:** {', '.join(module_summary.sensitive_modules[:20])}")
        lines.append(f"- **Module warnings:** {module_summary.warning_count}")
        lines.append(f"- **Blocked policy verdicts:** {module_summary.blocked_policy_count}")
        if module_summary.recommended_tests:
            lines.append("- **Recommended module-level tests:**")
            for test_hint in module_summary.recommended_tests[:20]:
                lines.append(f"  - {test_hint}")
        if req.include_step_details and module_summary.per_step:
            lines.append("")
            lines.append("**Per-step module notes:**")
            for step_mod in module_summary.per_step:
                if not (
                    step_mod.touched_modules
                    or step_mod.expected_modules
                    or step_mod.unknown_files
                    or step_mod.module_policy_verdicts
                    or step_mod.module_warnings
                ):
                    continue
                lines.append(f"- {step_mod.step_title or step_mod.step_id}")
                if step_mod.touched_modules:
                    lines.append(f"  - Touched: {', '.join(step_mod.touched_modules[:10])}")
                if step_mod.expected_modules:
                    lines.append(f"  - Expected: {', '.join(step_mod.expected_modules[:10])}")
                if step_mod.module_policy_verdicts:
                    lines.append(f"  - Policy: {', '.join(step_mod.module_policy_verdicts[:10])}")
                if step_mod.module_warnings:
                    lines.append(f"  - Notes: {'; '.join(step_mod.module_warnings[:3])}")
    else:
        lines.append("No module awareness data recorded.")
    lines.append("")

    if req.include_step_details:
        lines.append("## Step Summaries")
        lines.append("")
        for s in step_summaries:
            lines.append(f"### {s.step_title or s.step_id}")
            lines.append("")
            lines.append(f"- **Readiness:** `{s.readiness}`")
            lines.append(f"- **Status:** `{s.status}`")
            lines.append(
                f"- **Guard:** {s.guard_status} | "
                f"**Proposal:** {s.proposal_status} | "
                f"**Apply:** {s.apply_status} | "
                f"**Tests:** {s.test_status}"
            )
            lines.append(f"- Approval: {s.approval_status}")
            if s.readiness == "awaiting_approval":
                lines.append("  - ⏳ Waiting for approval before continuing.")
            if s.requirement_ids:
                lines.append(f"- **Requirement IDs:** {', '.join(s.requirement_ids)}")
            else:
                lines.append("- **Requirement IDs:** _(none linked)_")
            if s.changed_files:
                lines.append(f"- **Changed files:** {', '.join(s.changed_files[:10])}")
            if s.unresolved_issues:
                lines.append("- **Issues:**")
                for issue in s.unresolved_issues[:5]:
                    lines.append(f"  - {issue}")
            if s.recommended_next_action:
                lines.append(f"- **Next action:** {s.recommended_next_action}")
            lines.append("")

    lines.append("## Changes")
    lines.append("")
    if summary.changed_files:
        lines.append("**Changed files:**")
        for f in summary.changed_files[:50]:
            lines.append(f"- `{f}`")
    else:
        lines.append("No changed files recorded.")
    lines.append("")

    lines.append("## Validation")
    lines.append("")
    lines.append(f"- **Tests run:** {summary.tests_total}")
    lines.append(f"- **Proposals:** {summary.proposals_total}")
    lines.append(f"- **Applies:** {summary.applies_total}")
    # Latest test status per failing step
    failed_steps = [s for s in step_summaries if s.readiness == "tests_failed"]
    if failed_steps:
        lines.append("")
        lines.append("**Failing test steps:**")
        for s in failed_steps:
            lines.append(f"- {s.step_title}: tests_failed")
    lines.append("")

    lines.append("## Approvals and Safety")
    lines.append("")
    lines.append(f"- **Approvals total:** {summary.approvals_total}")
    lines.append(f"- **Guard checks:** {summary.guards_total}")
    lines.append(f"- **Guarded applies:** {summary.applies_total}")
    for note in _DELIVERY_SAFETY_NOTES:
        lines.append(f"- _{note}_")
    lines.append("")

    lines.append("## Final Recommendation")
    lines.append("")
    readiness = summary.readiness
    if readiness in ("ready_for_review", "delivered_with_warnings"):
        lines.append("✅ **Ready for review.** All actionable steps have passed tests.")
        if readiness == "delivered_with_warnings":
            lines.append("⚠️ Some warnings remain — see Step Summaries.")
    elif readiness == "blocked":
        lines.append("🔴 **Blocked.** Resolve guard or approval issues before proceeding.")
    elif readiness == "tests_failed":
        lines.append("🔴 **Tests failed.** Fix failing tests then re-run the delivery report.")
    elif readiness == "awaiting_approval":
        lines.append(
            f"⏳ **Awaiting approval.** {summary.approval_pending_steps} step(s) have a pending "
            "approval. Review and execute the pending approval(s) before proceeding."
        )
    elif readiness == "needs_tests":
        lines.append("🟡 **Needs tests.** Run tests on applied patches.")
    elif readiness == "in_progress":
        lines.append("🟡 **In progress.** Continue the patch-test-fix loop.")
    else:
        lines.append("🔵 **Not started.** Begin the workflow for this run.")
    if summary.recommended_next_action:
        lines.append("")
        lines.append(f"**Next action:** {summary.recommended_next_action}")
    lines.append("")

    report = "\n".join(lines)
    max_chars = req.max_markdown_chars if req.max_markdown_chars > 0 else 30000
    if len(report) > max_chars:
        report = report[:max_chars] + "\n\n_(report truncated at max_markdown_chars)_"
    return report


def _delivery_build_report(
    run_id: str,
    req: DeliveryReportRequest,
) -> DeliveryReportResponse:
    """Build DeliveryReportResponse from existing run data. Read-only, no side effects."""
    from datetime import datetime as _dt

    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    project = get_project(run.project_id) if getattr(run, "project_id", None) else None
    steps = list_run_steps(run_id)
    all_calls = list_tool_calls_for_run(run_id)
    all_guards = list_guard_results(run_id=run_id, include_stale=True, limit=500)
    all_approvals = _list_run_automation_approvals(run_id)

    generated_at = _dt.now().isoformat()

    step_summaries: list[StepDeliverySummary] = []
    for step in steps:
        step_calls = [tc for tc in all_calls if tc.step_id == step.id]
        step_guards = [g for g in all_guards if getattr(g, "step_id", None) == step.id]
        step_approvals = [
            a for a in all_approvals
            if (getattr(a, "command", None) == step.id or getattr(a, "step_id", None) == step.id)
        ]
        summary_step = _delivery_build_step_summary(
            step=step,
            step_calls=step_calls,
            step_guard_records=step_guards,
            step_approvals=step_approvals,
        )
        step_summaries.append(summary_step)

    active_module_map = _get_active_module_map(project.id) if project else None
    module_summary = build_delivery_module_summary(
        run=run,
        steps=steps,
        tool_calls=all_calls,
        active_module_map=active_module_map,
    )
    module_by_step = {item.step_id: item for item in module_summary.per_step}
    for summary_step in step_summaries:
        summary_step.module_summary = module_by_step.get(summary_step.step_id)

    run_summary = _delivery_build_run_summary(
        run=run,
        project=project,
        steps=steps,
        step_summaries=step_summaries,
        all_guards=all_guards,
        all_approvals=all_approvals,
        all_calls=all_calls,
        module_summary=module_summary,
    )

    markdown = ""
    if req.include_markdown:
        markdown = _delivery_build_markdown(
            run=run,
            project=project,
            summary=run_summary,
            step_summaries=step_summaries,
            req=req,
            generated_at=generated_at,
        )

    return DeliveryReportResponse(
        run_id=run_id,
        generated_at=generated_at,
        summary=run_summary,
        steps=step_summaries if req.include_step_details else [],
        markdown_report=markdown,
        safety_notes=_DELIVERY_SAFETY_NOTES,
    )


@router.get("/api/runs/{run_id}/delivery-summary")
async def get_run_delivery_summary(run_id: str) -> RunDeliverySummary:
    """Return read-only delivery summary for a run.

    Derived entirely from existing run/steps/tool_calls/guard_results/approvals.
    No side effects: no file mutations, no commands, no provider calls.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    req = DeliveryReportRequest(include_markdown=False)
    report = _delivery_build_report(run_id=run_id, req=req)
    return report.summary


@router.post("/api/runs/{run_id}/delivery-report")
async def generate_run_delivery_report(
    run_id: str,
    req: DeliveryReportRequest = DeliveryReportRequest(),
) -> DeliveryReportResponse:
    """Generate a full delivery report for a run.

    Read-only in v1. Does not write to disk, mutate state, or call providers.
    Returns structured summary + per-step details + markdown report.

    Hard invariants:
    - No file mutation.
    - No command execution.
    - No provider call.
    - No approval creation or bypass.
    - No guard bypass.
    """
    return _delivery_build_report(run_id=run_id, req=req)


# ── Persistent Source of Truth v1 ─────────────────────────────────────────────
#
# Hard invariants (all 6 endpoints):
#   - No provider calls.
#   - No auto-proposal, no auto-apply, no auto-rollback.
#   - No shell command execution.
#   - No approval creation or bypass.
#   - No guard bypass.
#   - No asyncio.create_task.
#   - Secret-like values are rejected by model validators.


@router.get("/api/projects/{project_id}/source-of-truth")
async def get_project_source_of_truth(
    project_id: str,
) -> SourceOfTruthResponse:
    """Return the active Source of Truth document for a project.

    If no active document exists, returns found=False with document=None.
    Falls back to the latest draft if no active version exists.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_active_sot(project_id)
    if doc is None:
        doc = _get_latest_sot(project_id)

    return SourceOfTruthResponse(
        project_id=project_id,
        document=doc,
        found=doc is not None,
    )


@router.put("/api/projects/{project_id}/source-of-truth")
async def upsert_project_source_of_truth(
    project_id: str,
    req: SourceOfTruthUpsertRequest,
) -> SourceOfTruthResponse:
    """Create or replace the Source of Truth document for a project.

    Always creates a new version row. If ``status='active'``, the previously
    active version is automatically archived.

    Rejects requests containing secret-like values (API keys, tokens, passwords,
    credentials, or connection strings with embedded credentials).

    No provider calls. No auto-proposal. No auto-apply. No auto-rollback.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build document from request
    try:
        doc = ProjectSourceOfTruthDocument(
            project_id=project_id,
            status=req.status,
            product_name=req.product_name,
            product_summary=req.product_summary,
            project_intent=req.project_intent,
            target_users=req.target_users,
            goals=req.goals,
            non_goals=req.non_goals,
            requirements=req.requirements,
            constraints=req.constraints,
            forbidden_changes=req.forbidden_changes,
            acceptance_criteria=req.acceptance_criteria,
            architecture_notes=req.architecture_notes,
            decisions=req.decisions,
            assumptions=req.assumptions,
            risks=req.risks,
            open_questions=req.open_questions,
            source=req.source,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Run pre-store validation
    validation = _validate_sot(doc)
    warnings = validation.errors + validation.warnings

    stored = _upsert_sot(project_id, doc)
    return SourceOfTruthResponse(
        project_id=project_id,
        document=stored,
        found=True,
        warnings=warnings,
    )


@router.get("/api/projects/{project_id}/source-of-truth/history")
async def get_project_source_of_truth_history(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> SourceOfTruthHistoryResponse:
    """Return the version history for a project's Source of Truth document.

    Newest version first. Includes id, version, status, product_name,
    created_at, updated_at, archived_at for each version.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    versions = _list_sot_history(project_id, limit=limit)
    return SourceOfTruthHistoryResponse(
        project_id=project_id,
        versions=versions,
        total=len(versions),
    )


@router.get("/api/projects/{project_id}/source-of-truth/{version}")
async def get_project_source_of_truth_by_version(
    project_id: str,
    version: int,
) -> SourceOfTruthResponse:
    """Return a specific version of a project's Source of Truth document.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_sot_version(project_id, version)
    return SourceOfTruthResponse(
        project_id=project_id,
        document=doc,
        found=doc is not None,
    )


@router.post("/api/projects/{project_id}/source-of-truth/validate")
async def validate_project_source_of_truth(
    project_id: str,
    req: SourceOfTruthUpsertRequest,
) -> SourceOfTruthValidationResponse:
    """Validate a Source of Truth document without persisting it.

    Returns errors and warnings without writing to the database.
    Use this before calling PUT to pre-check the document.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        doc = ProjectSourceOfTruthDocument(
            project_id=project_id,
            status=req.status,
            product_name=req.product_name,
            product_summary=req.product_summary,
            project_intent=req.project_intent,
            target_users=req.target_users,
            goals=req.goals,
            non_goals=req.non_goals,
            requirements=req.requirements,
            constraints=req.constraints,
            forbidden_changes=req.forbidden_changes,
            acceptance_criteria=req.acceptance_criteria,
            architecture_notes=req.architecture_notes,
            decisions=req.decisions,
            assumptions=req.assumptions,
            risks=req.risks,
            open_questions=req.open_questions,
            source=req.source,
        )
    except Exception as exc:
        return SourceOfTruthValidationResponse(
            valid=False,
            drift_risk="critical",
            errors=[str(exc)],
        )

    return _validate_sot(doc)


@router.post("/api/projects/{project_id}/source-of-truth/summary")
async def get_project_source_of_truth_summary(
    project_id: str,
) -> SourceOfTruthSummaryResponse:
    """Return a concise summary and requirement context block for the active SoT.

    The ``requirement_context`` field is a formatted
    ``AI_WORKBENCH_REQUIREMENT_CONTEXT`` block compatible with the format
    consumed by ``parse_run_step_requirement_context``.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_active_sot(project_id)
    if doc is None:
        doc = _get_latest_sot(project_id)

    if doc is None:
        return SourceOfTruthSummaryResponse(
            project_id=project_id,
            found=False,
            warnings=["No Source of Truth document found for this project"],
        )

    summary = _build_sot_summary(doc)
    req_context = _sot_req_context(doc)
    return SourceOfTruthSummaryResponse(
        project_id=project_id,
        found=True,
        summary=summary,
        requirement_context=req_context,
    )


# ── Project Module Map v1 ─────────────────────────────────────────────────────
#
# Read-only context infrastructure. Maps project modules to paths/files/requirements.
# All endpoints:
#   - validate project exists
#   - no provider calls, no tool_calls, no execute_run, no asyncio.create_task
#   - no run/step mutation, no command execution
#   - PUT is the only mutating operation (creates a new version)


@router.get("/api/projects/{project_id}/module-map")
async def get_project_module_map(
    project_id: str,
) -> ProjectModuleMapResponse:
    """Return the active module map for a project, or found=False if none exists.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_active_module_map(project_id)
    return ProjectModuleMapResponse(
        project_id=project_id,
        document=doc,
        found=doc is not None,
    )


@router.put("/api/projects/{project_id}/module-map")
async def upsert_project_module_map(
    project_id: str,
    req: ProjectModuleMapUpsertRequest,
) -> ProjectModuleMapResponse:
    """Create or replace the module map for a project.

    Always creates a new version row. If ``status='active'``, the previously
    active version is automatically archived.

    No provider calls. No auto-proposal. No auto-apply. No auto-rollback.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        doc = ProjectModuleMapDocument(
            project_id=project_id,
            status=req.status,
            modules=req.modules,
            ignored_paths=req.ignored_paths,
            scan_summary=req.scan_summary,
            source=req.source,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Run pre-store validation
    validation = _validate_module_map(doc)
    warnings = validation.errors + validation.warnings

    stored = _upsert_module_map(project_id, doc)
    return ProjectModuleMapResponse(
        project_id=project_id,
        document=stored,
        found=True,
        warnings=warnings,
    )


@router.get("/api/projects/{project_id}/module-map/history")
async def get_project_module_map_history(
    project_id: str,
    limit: int = Query(default=50, ge=1, le=200),
) -> ProjectModuleMapHistoryResponse:
    """Return the version history of a project's module map, newest first.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    history = _list_module_map_history(project_id, limit=limit)
    return ProjectModuleMapHistoryResponse(
        project_id=project_id,
        history=history,
        total=len(history),
    )


@router.get("/api/projects/{project_id}/module-map/{version}")
async def get_project_module_map_version(
    project_id: str,
    version: int,
) -> ProjectModuleMapResponse:
    """Return a specific version of a project's module map.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_module_map_version(project_id, version)
    return ProjectModuleMapResponse(
        project_id=project_id,
        document=doc,
        found=doc is not None,
    )


@router.post("/api/projects/{project_id}/module-map/validate")
async def validate_project_module_map(
    project_id: str,
    req: ProjectModuleMapUpsertRequest,
) -> ProjectModuleMapValidationResponse:
    """Validate a module map payload without persisting it.

    Returns errors and warnings without writing to the database.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        doc = ProjectModuleMapDocument(
            project_id=project_id,
            status=req.status,
            modules=req.modules,
            ignored_paths=req.ignored_paths,
            scan_summary=req.scan_summary,
            source=req.source,
        )
    except Exception as exc:
        return ProjectModuleMapValidationResponse(
            valid=False,
            errors=[str(exc)],
        )

    return _validate_module_map(doc)


@router.post("/api/projects/{project_id}/module-map/summary")
async def get_project_module_map_summary(
    project_id: str,
) -> ProjectModuleMapSummaryResponse:
    """Return a compact text summary of the active module map.

    Read-only. No provider calls, no mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    doc = _get_active_module_map(project_id)
    if doc is None:
        return ProjectModuleMapSummaryResponse(
            project_id=project_id,
            found=False,
            warnings=["No active module map found for this project"],
        )

    summary = _build_module_map_summary(doc)
    module_names = [m.name for m in doc.modules]
    return ProjectModuleMapSummaryResponse(
        project_id=project_id,
        found=True,
        summary=summary,
        module_names=module_names,
    )


@router.post("/api/projects/{project_id}/module-map/scan-preview")
async def scan_project_module_map_preview(
    project_id: str,
    req: ProjectModuleMapScanPreviewRequest,
) -> ProjectModuleMapScanPreviewResponse:
    """Run a bounded read-only deterministic scan to generate a draft module map.

    Inspects filesystem metadata (paths, directory structure, file names) only.
    Does NOT read file contents. Does NOT store the result.
    The caller must explicitly PUT to persist the result.

    Bounded by max_files (default 300) and max_depth (default 6).

    No provider calls. No command execution. No file mutations.
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.path:
        raise HTTPException(status_code=400, detail="Project path is not configured")

    # Merge project ignore_paths with any extra paths from the request
    ignore_paths: list[str] = list(project.ignore_paths or [])
    ignore_paths.extend(req.extra_ignore_paths or [])

    # Clamp bounds
    max_files = max(1, min(req.max_files, 2000))
    max_depth = max(1, min(req.max_depth, 15))

    result = _scan_preview(
        project.path,
        ignore_paths=ignore_paths,
        max_files=max_files,
        max_depth=max_depth,
    )
    # Override project_id with the canonical ID (scanner uses path as project_id internally)
    return result.model_copy(update={"project_id": project_id})


# ── Project Context Cockpit v1 ─────────────────────────────────────────────────
#
# Read-only aggregated operator overview.
# - No execute_run, no asyncio.create_task, no shell command execution.
# - No provider calls, no file content reads.
# - No tool_calls created, no DB writes.
# - No auto-proposal, no auto-apply, no auto-rollback.
# - No guard/approval bypass.


def _cockpit_next_action(
    readiness: str,
    pending_approval_count: int,
    guard_blocker_count: int,
    tests_failed_count: int,
    has_sot: bool,
    has_module_map: bool,
) -> CockpitNextAction:
    """Deterministic conservative next-action recommendation.

    Display-only. Does NOT trigger any action.
    Priority order (most critical first):
      1. blocked guard/readiness
      2. pending approval
      3. tests failed
      4. needs tests
      5. awaiting approval
      6. ready_for_review
      7. no project context
      8. default
    """
    if readiness == "blocked" or guard_blocker_count > 0:
        return CockpitNextAction(
            label="Review guard/proposal",
            reason="One or more steps are blocked — review guard results and proposals.",
            target_panel="guided",
            severity="blocked",
        )
    if pending_approval_count > 0:
        return CockpitNextAction(
            label="Review pending approvals",
            reason=f"{pending_approval_count} approval(s) awaiting operator action.",
            target_panel="operator-queue",
            severity="blocked",
        )
    if readiness == "tests_failed" or tests_failed_count > 0:
        return CockpitNextAction(
            label="Analyze failed tests",
            reason="One or more steps have test failures — review and fix.",
            target_panel="guided",
            severity="blocked",
        )
    if readiness == "needs_tests":
        return CockpitNextAction(
            label="Run tests manually",
            reason="Steps are ready for testing — run the test command.",
            target_panel="guided",
            severity="warning",
        )
    if readiness == "awaiting_approval":
        return CockpitNextAction(
            label="Review pending approval",
            reason="A step is awaiting approval before execution can continue.",
            target_panel="operator-queue",
            severity="warning",
        )
    if readiness == "ready_for_review":
        return CockpitNextAction(
            label="Open Delivery Report",
            reason="Run appears ready — review the delivery report before closing.",
            target_panel="delivery",
            severity="ready",
        )
    if readiness == "delivered_with_warnings":
        return CockpitNextAction(
            label="Review delivery warnings",
            reason="Delivered with warnings — check the delivery report for details.",
            target_panel="delivery",
            severity="warning",
        )
    if not has_sot:
        return CockpitNextAction(
            label="Add Source of Truth",
            reason="No Source of Truth is linked to this project.",
            target_panel="spec",
            severity="info",
        )
    if not has_module_map:
        return CockpitNextAction(
            label="Add Module Map",
            reason="No Module Map is linked to this project.",
            target_panel="spec",
            severity="info",
        )
    return CockpitNextAction(
        label="Continue operator workflow",
        reason="No immediate blockers detected — continue normal workflow.",
        target_panel="guided",
        severity="info",
    )


@router.get("/api/runs/{run_id}/project-context-cockpit")
async def get_run_project_context_cockpit(
    run_id: str,
) -> ProjectContextCockpitSummary:
    """Return aggregated read-only project context for the operator cockpit.

    Combines Source of Truth, Module Map, delivery status, and module awareness
    into a single compact response.

    Safety invariants:
    - Read-only. No DB writes.
    - No tool_calls created.
    - No execute_run, no asyncio.create_task.
    - No shell command execution.
    - No provider calls.
    - No file content reads.
    - No auto-proposal, auto-apply, or auto-rollback.
    - No guard or approval bypass.
    """
    run = get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    project_id = getattr(run, "project_id", None)
    project = get_project(project_id) if project_id else None

    safety_notes = [
        "Project Context Cockpit is read-only. No actions are triggered.",
        "No provider calls, tool_calls, or DB writes are made by this endpoint.",
    ]

    # ── Source of Truth ───────────────────────────────────────────────────────
    sot_summary = CockpitSourceOfTruth()
    if project and project.id:
        try:
            sot_doc = _get_active_sot(project.id)
            if sot_doc is None:
                sot_doc = _get_latest_sot(project.id)
            if sot_doc is not None:
                sot_summary = CockpitSourceOfTruth(
                    available=True,
                    version=sot_doc.version,
                    product_name=(sot_doc.product_name or "")[:120],
                    requirement_count=len(sot_doc.requirements or []),
                    risk_count=len(sot_doc.risks or []),
                    open_question_count=len(sot_doc.open_questions or []),
                )
        except Exception:
            safety_notes.append("Source of Truth could not be loaded.")

    # ── Module Map ────────────────────────────────────────────────────────────
    map_summary = CockpitModuleMap()
    if project and project.id:
        try:
            map_doc = _get_active_module_map(project.id)
            if map_doc is not None:
                key_modules = [m.name for m in (map_doc.modules or [])[:8]]
                map_summary = CockpitModuleMap(
                    available=True,
                    version=map_doc.version,
                    module_count=len(map_doc.modules or []),
                    key_modules=key_modules,
                )
        except Exception:
            safety_notes.append("Module Map could not be loaded.")

    # ── Delivery / Run Status ─────────────────────────────────────────────────
    run_status = CockpitRunStatus()
    mod_awareness = CockpitModuleAwareness()
    try:
        _delivery_req = DeliveryReportRequest(
            include_markdown=False,
            include_step_details=False,
            include_tool_history=False,
        )
        delivery_report = _delivery_build_report(run_id, _delivery_req)
        run_summary = delivery_report.summary
        completed_steps = max(
            0,
            min(
                run_summary.ready_steps,
                run_summary.total_steps,
            ),
        )
        run_status = CockpitRunStatus(
            readiness=run_summary.readiness,
            completed_steps=completed_steps,
            total_steps=run_summary.total_steps,
            pending_approval_count=run_summary.approval_pending_steps,
            guard_blocker_count=run_summary.blocked_steps,
            tests_failed_count=run_summary.failed_test_steps,
        )
        if run_summary.module_summary:
            ms = run_summary.module_summary
            mod_awareness = CockpitModuleAwareness(
                touched_modules=list(ms.touched_modules[:10]),
                expected_modules=list(ms.expected_modules[:10]),
                blocked_policy_count=ms.blocked_policy_count,
                warning_count=ms.warning_count,
                recommended_tests=list(ms.recommended_tests[:5]),
            )
    except Exception:
        safety_notes.append("Delivery summary could not be computed.")

    # ── Next Action ───────────────────────────────────────────────────────────
    next_action = _cockpit_next_action(
        readiness=run_status.readiness,
        pending_approval_count=run_status.pending_approval_count,
        guard_blocker_count=run_status.guard_blocker_count,
        tests_failed_count=run_status.tests_failed_count,
        has_sot=sot_summary.available,
        has_module_map=map_summary.available,
    )

    return ProjectContextCockpitSummary(
        run_id=run_id,
        has_project=project is not None,
        project_id=project.id if project else None,
        project_name=project.name if project else None,
        source_of_truth=sot_summary,
        module_map=map_summary,
        run=run_status,
        module_awareness=mod_awareness,
        next_action=next_action,
        safety_notes=safety_notes,
    )

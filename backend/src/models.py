"""Core domain models for AI Workbench."""

from __future__ import annotations

import enum
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────────────────

class RunStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"


class ProviderType(str, enum.Enum):
    OLLAMA = "ollama"
    CODEX = "codex"
    CLAUDE = "claude"


class RunMode(str, enum.Enum):
    OFFLINE = "offline"
    HYBRID = "hybrid"
    CLOUD = "cloud"


class ProviderMode(str, enum.Enum):
    LOCAL = "local"
    HYBRID = "hybrid"
    CLOUD = "cloud"


# ── Models ───────────────────────────────────────────────────────────────────

class Project(BaseModel):
    id: str = Field(default="")
    name: str
    path: str = ""
    description: str = ""
    stack: str = ""
    package_manager: str = ""
    test_command: str = ""
    build_command: str = ""
    safe_commands: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    ignore_paths: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None


class AgentInfo(BaseModel):
    id: str
    name: str
    role: str
    description: str
    provider: ProviderType = ProviderType.OLLAMA
    instructions_file: str = ""
    category: str = "core-development"
    skills: list[str] = Field(default_factory=list)
    default_tools: list[str] = Field(default_factory=list)
    model_profile: str = "planning_reasoning"
    default_model: str = ""
    fast_model: str = ""
    reasoning_model: str = ""
    can_edit_files: bool = False
    can_run_commands: bool = False
    risk_level: str = "low"
    enabled: bool = True
    best_for: list[str] = Field(default_factory=list)


class Task(BaseModel):
    id: str = Field(default="")
    project_id: str = ""
    prompt: str
    mode: RunMode = RunMode.OFFLINE
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class Run(BaseModel):
    id: str = Field(default="")
    task_id: str = ""
    project_id: str = ""
    project_path: str = ""
    current_step_id: str = ""
    agent_id: str = ""
    status: RunStatus = RunStatus.PENDING
    mode: RunMode = RunMode.OFFLINE
    prompt: str = ""
    plan: str = ""
    result: str = ""
    logs: list[str] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    run_dir: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None


class ApprovalRequest(BaseModel):
    id: str = Field(default="")
    run_id: str
    action: str
    command: str = ""
    description: str = ""
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: str | None = None


class RunStep(BaseModel):
    id: str = Field(default="")
    run_id: str
    parent_step_id: str = ""
    agent_id: str = ""
    status: str = RunStatus.PENDING.value
    title: str
    input: str = ""
    output: str = ""
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ToolCall(BaseModel):
    id: str = Field(default="")
    run_id: str = ""
    project_id: str = ""
    step_id: str = ""
    tool_name: str
    command: str = ""
    cwd: str = ""
    status: str = ""
    approval_id: str = ""
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    report_path: str = ""
    started_at: str = ""
    finished_at: str = ""
    input_json: str = ""
    output_json: str = ""
    error: str = ""
    risk_level: str = "low"
    completed_at: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator(
        "run_id",
        "project_id",
        "step_id",
        "command",
        "cwd",
        "status",
        "approval_id",
        "stdout",
        "stderr",
        "report_path",
        "started_at",
        "finished_at",
        "input_json",
        "output_json",
        "error",
        "risk_level",
        mode="before",
    )
    @classmethod
    def _empty_string_for_null(cls, value: object) -> object:
        return "" if value is None else value


class RunAgentAssignment(BaseModel):
    id: str = Field(default="")
    run_id: str
    agent_id: str
    assigned_role: str = ""
    reason: str = ""
    confidence: float = 0.0
    status: str = "selected"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentSelectionResult(BaseModel):
    selected_agents: list[RunAgentAssignment] = Field(default_factory=list)
    team_size: int = 0
    recommended_execution_mode: RunMode = RunMode.OFFLINE
    detected_stack: list[str] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)


class Artifact(BaseModel):
    id: str = Field(default="")
    run_id: str
    name: str
    path: str
    artifact_type: str = "file"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ModelProvider(BaseModel):
    name: ProviderType
    enabled: bool = True
    base_url: str = ""
    default_model: str = ""
    config: dict[str, Any] = Field(default_factory=dict)


class ModelRegistryItem(BaseModel):
    id: str
    provider: str
    display_name: str
    family: str
    capabilities: list[str] = Field(default_factory=list)
    context_window: int = 0
    memory_tier: str = "small"
    recommended_for: list[str] = Field(default_factory=list)
    installed: bool = False
    enabled: bool = True
    max_parallel: int = 1
    notes: str = ""


class ModelProfile(BaseModel):
    id: str
    primary_model: str
    fast_model: str = ""
    reasoning_model: str = ""
    fallback_model: str = ""
    allowed_providers: list[str] = Field(default_factory=list)
    preferred_provider: str = "local_ollama"
    max_parallel: int = 1
    local_only_default: bool = True
    description: str = ""


class ProviderInfo(BaseModel):
    id: str
    display_name: str
    kind: str
    enabled: bool = False
    available: bool = False
    local: bool = False
    requires_approval: bool = True
    supports_execution: bool = False
    modes: list[ProviderMode] = Field(default_factory=list)
    notes: str = ""


class ProviderStatus(BaseModel):
    id: str
    enabled: bool
    available: bool
    status: str
    models: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ModelRouteRequest(BaseModel):
    agent_id: str = ""
    task_type: str = "planning"
    model_profile: str = ""
    provider_mode: ProviderMode = ProviderMode.LOCAL
    available_models: list[str] = Field(default_factory=list)
    project_privacy_level: str = "private"
    hardware_memory_gb: float | None = None
    user_preference_model: str = ""
    user_preference_provider: str = ""


class ModelRouteResult(BaseModel):
    selected_model: str
    selected_provider: str
    fallback_model: str = ""
    reason: str
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    model_profile: str = ""
    task_type: str = ""


class ModelRouteDecision(BaseModel):
    id: str = Field(default="")
    run_id: str
    step_id: str | None = None
    agent_id: str
    task_type: str
    model_profile: str
    selected_model: str
    selected_provider: str
    fallback_model: str = ""
    fallback_provider: str | None = None
    provider_mode: ProviderMode = ProviderMode.LOCAL
    reason: str
    confidence: float
    warnings: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None


class ModelRouteDecisionResponse(BaseModel):
    run_id: str
    count: int
    persisted: bool = False
    decisions: list[ModelRouteDecision] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProviderModeUpdate(BaseModel):
    provider_mode: ProviderMode


# ── API Schemas ──────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    name: str
    path: str
    description: str = ""
    stack: str = ""
    package_manager: str = ""
    test_command: str = ""
    build_command: str = ""
    safe_commands: list[str] = Field(default_factory=list)
    blocked_commands: list[str] = Field(default_factory=list)
    ignore_paths: list[str] = Field(default_factory=list)


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    path: str | None = None
    description: str | None = None
    stack: str | None = None
    package_manager: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    safe_commands: list[str] | None = None
    blocked_commands: list[str] | None = None
    ignore_paths: list[str] | None = None


class CreateRunRequest(BaseModel):
    prompt: str
    project_id: str = ""
    project_path: str = ""
    mode: RunMode = RunMode.OFFLINE


class ApprovalDecision(BaseModel):
    reason: str = ""


class ToolContextRequest(BaseModel):
    run_id: str = ""
    step_id: str = ""
    agent_id: str = ""


class ListFilesRequest(ToolContextRequest):
    path: str = "."
    max_files: int = 500


class ReadFileRequest(ToolContextRequest):
    path: str
    max_chars: int = 200_000


class SearchCodeRequest(ToolContextRequest):
    query: str
    path: str = "."
    max_results: int = 100


class PatchOperation(BaseModel):
    file_path: str
    old_text: str = ""
    new_text: str = ""
    create_if_missing: bool = False
    replace_all: bool = False


class ProposePatchRequest(ToolContextRequest):
    operations: list[PatchOperation] = Field(default_factory=list)
    guard_result_id: str | None = None
    guard_warning_acknowledged: bool = False
    no_guard_override: bool = False


class ProposedPatchFile(BaseModel):
    path: str
    status: str
    diff: str = ""
    error: str = ""


class ModuleAwarenessResult(BaseModel):
    """Compact read-only module-map awareness for guarded proposal review."""
    has_active_module_map: bool = False
    module_map_version: int | None = None
    touched_modules: list[dict] = Field(default_factory=list)
    expected_modules: list[dict] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    expected_files: list[str] = Field(default_factory=list)
    matched_requirement_ids: list[str] = Field(default_factory=list)
    module_risks: list[str] = Field(default_factory=list)
    module_test_hints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    confidence: str = "medium"


class ModuleAwareGuardPolicyResult(BaseModel):
    """Deterministic module-aware risk classification for proposal review."""
    verdict: str = "allowed"
    reasons: list[str] = Field(default_factory=list)
    required_acknowledgements: list[str] = Field(default_factory=list)
    affected_modules: list[str] = Field(default_factory=list)
    sensitive_modules: list[str] = Field(default_factory=list)
    unknown_files: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    confidence: str = "medium"


class ProposePatchResponse(BaseModel):
    files: list[ProposedPatchFile] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)
    proposal_id: str = ""
    guard_result_id: str | None = None
    guard_validation_valid: bool | None = None
    guard_validation_reasons: list[str] = Field(default_factory=list)
    guard_validation_warnings: list[str] = Field(default_factory=list)
    no_guard_override: bool = False
    module_awareness: ModuleAwarenessResult | None = None
    module_policy: ModuleAwareGuardPolicyResult | None = None


class ApplyPatchRequest(ToolContextRequest):
    operations: list[PatchOperation] = Field(default_factory=list)
    confirm: bool = False
    expected_summary: str = ""
    proposal_id: str = ""


class AppliedPatchFile(BaseModel):
    path: str
    status: str
    error: str = ""


class ApplyPatchResponse(BaseModel):
    files: list[AppliedPatchFile] = Field(default_factory=list)
    summary: str = ""
    git_status: str = ""
    git_diff_stat: str = ""
    warnings: list[str] = Field(default_factory=list)
    applied_from_proposal_id: str = ""
    guard_result_id: str | None = None
    guard_revalidated: bool | None = None
    guard_revalidation_reasons: list[str] = Field(default_factory=list)
    guard_revalidation_warnings: list[str] = Field(default_factory=list)
    no_guard_override: bool = False


class RollbackPatchRequest(ToolContextRequest):
    tool_call_id: str
    confirm: bool = False


class RolledBackFile(BaseModel):
    path: str
    operation: str  # "modified" | "created"
    status: str     # "restored" | "deleted" | "skipped" | "conflict" | "error"
    reason: str = ""


class RollbackPatchResponse(BaseModel):
    rolled_back_files: list[RolledBackFile] = Field(default_factory=list)
    skipped_files: list[RolledBackFile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    git_status: str = ""
    git_diff_stat: str = ""
    tool_call_id: str = ""


class UpdateRunAgentAssignmentRequest(BaseModel):
    assigned_role: str | None = None
    reason: str | None = None
    confidence: float | None = None
    status: str | None = None


# ── Orchestrator Tool Planning ────────────────────────────────────────────────

class StepToolRecommendation(BaseModel):
    step_id: str
    agent_id: str = ""
    task_type: str = ""
    recommended_tools: list[str] = Field(default_factory=list)
    reason: str = ""
    confidence: float = 1.0
    warnings: list[str] = Field(default_factory=list)


class StepToolPlanResponse(BaseModel):
    run_id: str
    recommendations: list[StepToolRecommendation] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


# ── Orchestrator Guided Execution ─────────────────────────────────────────────

class GuidedStepAction(BaseModel):
    step_id: str
    action_id: str                     # unique identifier within the plan
    action_type: str                   # read_context | search_code | propose_patch |
                                       # apply_patch | run_tests | analyze_result |
                                       # review_diff | rollback_patch | done
    tool_name: str = ""                # mapped project tool, if any
    title: str
    description: str = ""
    reason: str = ""
    requires_confirmation: bool = False
    risk_level: str = "low"            # low | medium | high
    enabled: bool = True
    blocked_reason: str = ""
    related_tool_call_id: str = ""
    related_proposal_id: str = ""


class GuidedStepExecutionPlan(BaseModel):
    run_id: str
    step_id: str
    agent_id: str = ""
    task_type: str = ""
    recommended_next_action: GuidedStepAction | None = None
    actions: list[GuidedStepAction] = Field(default_factory=list)
    status_summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class GuidedExecutionPlanResponse(BaseModel):
    run_id: str
    steps: list[GuidedStepExecutionPlan] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


class ClarificationAnswerRequest(BaseModel):
    answers: str


# ── Safe Auto Read/Search ─────────────────────────────────────────────────────

# Only these action types are permitted for auto-execution.
AUTO_READ_ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "list_files",
    "read_file",
    "search_code",
})

# Explicitly blocked — these must never be auto-executed.
AUTO_READ_BLOCKED_ACTIONS: frozenset[str] = frozenset({
    "propose_patch",
    "apply_patch",
    "rollback_patch",
    "run_command",
    "analyze_result",
    "run_tests",
})


class AutoStepReadRequest(BaseModel):
    step_id: str
    action_type: str          # list_files | read_file | search_code
    query: str = ""           # for search_code
    file_path: str = ""       # for read_file
    limit: int = 100          # max_results / max_files
    run_id: str = ""
    agent_id: str = ""


class AutoStepReadResponse(BaseModel):
    run_id: str
    step_id: str
    action_type: str
    tool_call_id: str
    status: str               # completed | failed | blocked
    summary: str = ""
    result: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


# ── Auto Context Gathering ────────────────────────────────────────────────────

AUTO_CONTEXT_MAX_HARD_CAP: int = 8
AUTO_CONTEXT_DEFAULT_MAX: int = 5


class AutoContextGatherRequest(BaseModel):
    max_tool_calls: int = AUTO_CONTEXT_DEFAULT_MAX
    query: str = ""
    include_file_patterns: list[str] = Field(default_factory=list)
    exclude_file_patterns: list[str] = Field(default_factory=list)
    agent_id: str = ""


class AutoContextGatheredFile(BaseModel):
    file_path: str
    reason: str
    source_tool_call_id: str = ""


class AutoContextGatherResponse(BaseModel):
    run_id: str
    step_id: str
    status: str                    # completed | partial | failed
    summary: str = ""
    tool_call_ids: list[str] = Field(default_factory=list)
    searched_queries: list[str] = Field(default_factory=list)
    files_considered: list[str] = Field(default_factory=list)
    files_read: list[AutoContextGatheredFile] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_recommended_action: str = ""


# ── Step Context Bundle ───────────────────────────────────────────────────────

# Limits to keep responses lean
BUNDLE_MAX_FILES: int = 5
BUNDLE_MAX_SNIPPETS_PER_FILE: int = 3
BUNDLE_MAX_SNIPPET_CHARS: int = 800


class StepContextFile(BaseModel):
    file_path: str
    source_tool_call_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    snippets: list[str] = Field(default_factory=list)
    read: bool = False
    match_count: int = 0


class StepContextBundle(BaseModel):
    run_id: str
    step_id: str
    agent_id: str | None = None
    task_type: str | None = None
    status: str                    # ok | partial | empty
    summary: str = ""
    queries: list[str] = Field(default_factory=list)
    files: list[StepContextFile] = Field(default_factory=list)
    tool_call_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_recommended_action: str | None = None


class StepContextBundleResponse(BaseModel):
    bundle: StepContextBundle


# ── Agent-assisted Patch Proposal from Context ────────────────────────────────

DRAFT_PLACEHOLDER_NEW_TEXT: str = "TODO: replace with intended change"
DRAFT_MAX_OLD_TEXT_CHARS: int = 1200


class ContextPatchDraftRequest(BaseModel):
    preferred_file_path: str | None = None
    preferred_snippet_index: int | None = None
    intent: str | None = None
    agent_id: str | None = None


class ContextPatchDraftCandidate(BaseModel):
    file_path: str
    old_text: str
    new_text: str
    reason: str
    confidence: float
    source_tool_call_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ContextPatchDraftResponse(BaseModel):
    run_id: str
    step_id: str
    status: str                        # ok | no_context | partial
    summary: str = ""
    candidates: list[ContextPatchDraftCandidate] = Field(default_factory=list)
    recommended_candidate_index: int | None = None
    warnings: list[str] = Field(default_factory=list)
    next_recommended_action: str | None = None


# ── Patch Proposal Review ────────────────────────────────────────────────────

class PatchReviewOperation(BaseModel):
    file_path: str
    old_text: str = ""
    new_text: str = ""


class PatchReviewRequest(BaseModel):
    operations: list[PatchReviewOperation] = Field(default_factory=list)
    run_id: str | None = None
    step_id: str | None = None
    agent_id: str | None = None


class PatchReviewIssue(BaseModel):
    severity: str               # "info" | "warning" | "blocker"
    code: str
    message: str
    file_path: str | None = None
    operation_index: int | None = None


class PatchReviewOperationResult(BaseModel):
    operation_index: int
    file_path: str
    status: str                 # "ok" | "warning" | "blocked"
    old_text_found: bool = False
    old_text_occurrences: int = 0
    estimated_diff_lines: int = 0
    issues: list[PatchReviewIssue] = Field(default_factory=list)


class PatchReviewResponse(BaseModel):
    status: str                 # "ok" | "warning" | "blocked"
    summary: str = ""
    operation_results: list[PatchReviewOperationResult] = Field(default_factory=list)
    issues: list[PatchReviewIssue] = Field(default_factory=list)
    safe_to_create_proposal: bool = False
    safe_to_apply: bool = False


# ── Approval-gated Patch Workflow Orchestrator ────────────────────────────────

class PatchWorkflowStage(BaseModel):
    stage_id: str
    title: str
    status: str             # "not_started" | "ready" | "blocked" | "completed" | "warning"
    summary: str = ""
    related_tool_call_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class PatchWorkflowNextAction(BaseModel):
    action_type: str        # auto_gather_context | build_context_bundle | create_patch_draft |
                            # review_patch | create_proposal | apply_patch_manual |
                            # run_tests_manual | analyze_result | rollback_manual | done
    title: str
    description: str
    risk_level: str         # "low" | "medium" | "high"
    requires_confirmation: bool = False
    enabled: bool = True
    blocked_reason: str | None = None


class StepPatchWorkflowPlan(BaseModel):
    run_id: str
    step_id: str
    agent_id: str | None = None
    task_type: str | None = None
    status: str             # "not_started" | "in_progress" | "blocked" | "ready_for_review" | "ready_for_tests" | "done"
    summary: str = ""
    stages: list[PatchWorkflowStage] = Field(default_factory=list)
    recommended_next_action: PatchWorkflowNextAction | None = None
    warnings: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class PatchWorkflowPlanResponse(BaseModel):
    run_id: str
    steps: list[StepPatchWorkflowPlan] = Field(default_factory=list)
    summary: str = ""
    warnings: list[str] = Field(default_factory=list)


# ── Config ────────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    default_mode: RunMode | None = None
    provider_mode: ProviderMode | None = None
    ollama_base_url: str | None = None
    ollama_model: str | None = None
    codex_enabled: bool | None = None
    claude_enabled: bool | None = None


# ── Safe Test Command Runner ──────────────────────────────────────────────────

class ProjectCommandKind(str, enum.Enum):
    TEST = "test"
    BUILD = "build"
    LINT = "lint"
    TYPECHECK = "typecheck"


class RunProjectCommandRequest(BaseModel):
    command_kind: ProjectCommandKind
    run_id: str = ""
    step_id: str = ""
    agent_id: str = ""
    timeout_seconds: int = 120


class RunProjectCommandResponse(BaseModel):
    command_kind: str
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    tool_call_id: str = ""


# ── Test Result Analysis ──────────────────────────────────────────────────────

class CommandIssue(BaseModel):
    kind: str  # test_failure | assertion_error | traceback | type_error | lint_error | build_error | timeout | unknown
    file_path: str | None = None
    line: int | None = None
    message: str = ""
    raw_excerpt: str = ""


class CommandAnalysisRequest(BaseModel):
    tool_call_id: str = ""
    stdout: str = ""
    stderr: str = ""
    returncode: int | None = None
    command_kind: str = ""
    run_id: str = ""
    step_id: str = ""
    agent_id: str = ""


class CommandAnalysisResponse(BaseModel):
    status: str  # passed | failed | timed_out | unknown
    summary: str
    issues: list[CommandIssue] = Field(default_factory=list)
    suggested_next_actions: list[str] = Field(default_factory=list)
    can_create_fix_proposal: bool = False
    source_tool_call_id: str = ""


# ── Failure-to-Fix Draft ─────────────────────────────────────────────────────

class FailureToFixDraftRequest(BaseModel):
    """Request body for the failure-to-fix-draft endpoint.

    All fields are optional.  If ``failed_tool_call_id`` is omitted the endpoint
    locates the latest failed run-command for the step automatically.
    """
    failed_tool_call_id: str | None = None
    apply_tool_call_id: str | None = None
    guard_result_id: str | None = None
    max_stdout_chars: int = 2000
    max_stderr_chars: int = 2000


class FailureToFixDraftResponse(BaseModel):
    """Read-only fix-draft context built from the latest failed test output.

    Contains no generated code, no patch proposal, and no apply instructions.
    The ``fix_context`` field is plain text intended for prefilling the patch
    context/issue field in the UI — it does not create any DB records.
    """
    run_id: str
    step_id: str
    failed_tool_call_id: str
    apply_tool_call_id: str | None = None
    guard_result_id: str | None = None
    command: str
    returncode: int | None = None
    stdout_excerpt: str
    stderr_excerpt: str
    fix_context: str
    suggested_next_action: str
    warnings: list[str] = Field(default_factory=list)
    can_prefill_patch_context: bool


# ── Semi-Auto Operator Queue ──────────────────────────────────────────────────

class OperatorQueueItem(BaseModel):
    """A single recommended manual action in the operator queue.

    Read-only: describes what the operator should do next for a specific step.
    No item triggers autonomous execution.
    """
    id: str
    run_id: str
    step_id: str
    step_title: str
    priority: str          # "high" | "medium" | "low"
    status: str            # "ready" | "blocked" | "manual_required" | "done"
    action_type: str       # check_guard | validate_guard_for_proposal | create_proposal_manual |
                           # apply_patch_manual | run_tests_manual | analyze_failed_tests_manual |
                           # prepare_fix_draft_manual | review_success | resolve_blocker |
                           # execute_approval
    title: str
    description: str
    reason: str
    destination: str       # patch_lifecycle | source_of_truth_guard | guard_history |
                           # patch_form | run_command | failure_analysis | approval_panel
    guard_result_id: str | None = None
    proposal_tool_call_id: str | None = None
    apply_tool_call_id: str | None = None
    test_tool_call_id: str | None = None
    failed_tool_call_id: str | None = None
    can_run_directly: bool = False
    requires_confirmation: bool = False
    is_destructive: bool = False
    warnings: list[str] = Field(default_factory=list)
    # Approval context — populated only for execute_approval items (GAP-004)
    approval_id: str | None = None
    approval_action_type: str | None = None


class OperatorQueueSummary(BaseModel):
    total_items: int
    blocked_items: int
    ready_items: int
    manual_required_items: int
    done_items: int


class OperatorQueueResponse(BaseModel):
    """Read-only operator queue for a run.

    Pure analysis: creates no ToolCalls, executes no commands, calls no
    providers, creates no proposals, applies no patches.
    """
    run_id: str
    generated_at: str
    items: list[OperatorQueueItem] = Field(default_factory=list)
    summary: OperatorQueueSummary


# ── Automation Runner ─────────────────────────────────────────────────────────

class AutomationRunRequest(BaseModel):
    """Request body for POST /api/runs/{run_id}/automation/run-next."""
    step_id: str | None = None
    dry_run: bool = False
    allow_safe_commands: bool = False
    allow_low_risk_tool_calls: bool = True
    max_actions: int = 1
    stop_on_manual_required: bool = True
    stop_on_blocked: bool = True


class AutomationSafeLoopRequest(BaseModel):
    """Request body for POST /api/runs/{run_id}/automation/run-safe-loop."""
    step_id: str | None = None
    max_actions: int = 5
    dry_run: bool = False
    allow_safe_commands: bool = False
    allow_low_risk_tool_calls: bool = True
    stop_on_manual_required: bool = True
    stop_on_blocked: bool = True


class AutomationActionResult(BaseModel):
    """Result for a single attempted automation action."""
    action_type: str
    step_id: str | None = None
    # status: executed | dry_run | no_action | manual_required | blocked | failed
    status: str
    executed: bool = False
    # risk_level: readonly | low | medium | high
    risk_level: str = "none"
    reason: str = ""
    destination: str = ""
    created_tool_call_id: str | None = None
    error: str | None = None
    result_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)


class AutomationRunResponse(BaseModel):
    """Response from run-next and run-safe-loop endpoints."""
    run_id: str
    dry_run: bool
    # status: completed | no_action | manual_required | blocked | stopped | failed
    status: str
    executed_actions: list[AutomationActionResult] = Field(default_factory=list)
    skipped_actions: list[AutomationActionResult] = Field(default_factory=list)
    next_queue_items: list[OperatorQueueItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


# ── Approval-Gated Automation v1 ─────────────────────────────────────────────


class AutomationApprovalCreateRequest(BaseModel):
    """Request to create an approval for a manual-required queue action."""
    step_id: str | None = None
    action_type: str
    queue_item_id: str | None = None
    reason: str = ""
    payload: dict = Field(default_factory=dict)


class AutomationApprovalApproveRequest(BaseModel):
    note: str = ""


class AutomationApprovalRejectRequest(BaseModel):
    note: str = ""


class AutomationApprovalExecuteRequest(BaseModel):
    note: str = ""


class AutomationApprovalItem(BaseModel):
    """Serialisable view of one automation approval request."""
    id: str
    run_id: str
    step_id: str | None = None
    action_type: str
    # pending | approved | rejected | executed
    status: str
    reason: str
    risk_level: str
    is_destructive: bool
    created_at: str
    resolved_at: str | None = None


class AutomationApprovalListResponse(BaseModel):
    run_id: str
    approvals: list[AutomationApprovalItem] = Field(default_factory=list)


class AutomationApprovalExecuteResponse(BaseModel):
    approval_id: str
    run_id: str
    step_id: str | None = None
    action_type: str
    # executed | failed | stale | blocked | deferred
    status: str
    executed: bool
    result_summary: str | None = None
    revalidation_error: str | None = None
    created_tool_call_id: str | None = None
    safety_notes: list[str] = Field(default_factory=list)


# ── Agent Execution Harness v1 ─────────────────────────────────────────────────


class AgentExecutionRequest(BaseModel):
    """Request to execute (or dry-run) an agent task for a specific RunStep."""
    agent_id: str | None = None
    task_type: str = "implementation"
    mode: str = "dry_run"  # dry_run | mock | provider
    allow_provider_call: bool = False
    persist_result: bool = True
    max_output_chars: int = 12000
    user_instruction: str = ""
    include_requirement_context: bool = True
    include_recent_tool_calls: bool = True
    include_patch_lifecycle: bool = True


class AgentModuleContext(BaseModel):
    """Compact project module map context injected into agent execution context.

    Read-only. Built from the active module map; never triggers DB writes,
    provider calls, file reads, or scan-preview persistence.
    """
    project_id: str = ""
    module_map_version: int | None = None
    has_active_module_map: bool = False
    matched_modules: list[dict] = Field(default_factory=list)
    module_summary: str = ""
    matched_paths: list[str] = Field(default_factory=list)
    matched_requirement_ids: list[str] = Field(default_factory=list)


class AgentExecutionContext(BaseModel):
    """Deterministic execution context built from run/step state. Read-only."""
    run_id: str
    step_id: str
    step_title: str
    step_input_summary: str
    requirement_ids: list[str] = Field(default_factory=list)
    source_of_truth_summary: str = ""
    acceptance_criteria: str = ""
    constraints: str = ""
    forbidden_changes: str = ""
    recent_tool_call_summary: str = ""
    patch_lifecycle_summary: str = ""
    operator_queue_summary: str = ""
    project_name: str = ""
    project_path: str = ""
    recommended_agent_id: str = ""
    recommended_agent_name: str = ""
    recommended_task_type: str = ""
    available_agents: list[dict] = Field(default_factory=list)
    module_context: AgentModuleContext | None = None


class AgentExecutionResult(BaseModel):
    """Structured advisory output from agent execution.
    Never directly applied — must pass through guarded proposal/apply flow."""
    summary: str = ""
    analysis: str = ""
    proposed_files: list[str] = Field(default_factory=list)
    patch_intent: str = ""
    risks: list[str] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    recommended_next_action: str = ""
    can_feed_patch_draft: bool = False


class AgentExecutionResponse(BaseModel):
    """Full response from agent execution endpoint."""
    run_id: str
    step_id: str
    agent_id: str
    mode: str
    # planned | completed | provider_unavailable | blocked | failed
    status: str
    executed: bool
    provider_called: bool
    tool_call_id: str | None = None
    context: AgentExecutionContext
    result: AgentExecutionResult | None = None
    prompt_preview: str = ""
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class ExecuteNextStepRequest(BaseModel):
    """Request body for one-click execution of the next pending run step."""
    agent_id: str | None = None
    task_type: str = ""
    mode: str = "mock"  # dry_run | mock | provider
    allow_provider_call: bool = False
    persist_result: bool = True
    max_output_chars: int = 12000
    user_instruction: str = ""


class ExecuteNextStepResponse(BaseModel):
    """Result of one-click execution of the next pending run step."""
    run_id: str
    step_id: str
    step_title: str
    status: str
    message: str
    artifact: str = ""
    execution: AgentExecutionResponse
    step: RunStep | None = None


class AgentExecutionListResponse(BaseModel):
    """List of previous agent execution audit records for a step."""
    run_id: str
    step_id: str
    executions: list[dict] = Field(default_factory=list)
    total: int = 0
    note: str = ""


# ── Agent Result → Patch Draft Bridge v1 ─────────────────────────────────────

class AgentPatchDraftRequest(BaseModel):
    """Request body for building a patch draft context from an agent execution result.

    Supply either agent_execution_tool_call_id (to load a persisted audit record)
    or agent_result directly.  Pure read — no mutation, no provider call.
    """
    agent_execution_tool_call_id: str | None = None
    agent_result: AgentExecutionResult | None = None
    include_context: bool = True
    include_risks: bool = True
    include_tests: bool = True
    max_context_chars: int = 12000


class AgentPatchDraftResponse(BaseModel):
    """Deterministic patch draft context built from an agent execution result.

    Contains no generated code.  The patch_context field is plain text intended
    for prefilling the patch context/issue field in the UI.  It does not create
    DB records, does not propose patches, and does not apply anything.
    """
    run_id: str
    step_id: str
    source_agent_execution_id: str | None = None
    can_prefill_patch_context: bool
    recommended_file_path: str | None = None
    patch_context: str
    patch_summary: str
    module_context: AgentModuleContext | None = None
    module_context_summary: str = ""
    recommended_files_from_module_map: list[str] = Field(default_factory=list)
    module_risks: list[str] = Field(default_factory=list)
    module_test_hints: list[str] = Field(default_factory=list)
    proposed_files: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    test_suggestions: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)
    guard_required: bool = True
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


# ── Bounded Autonomous Patch-Test-Fix Loop v1 ─────────────────────────────────


class BoundedAutonomousLoopRequest(BaseModel):
    """Request body for POST /api/runs/{run_id}/automation/bounded-patch-test-fix-loop.

    The loop advances through safe/read-only/low-risk stages automatically and
    stops before dangerous actions, missing approvals, blocked guards, stale state,
    or max iteration limits.

    Hard constraints (enforced invariants):
    - No arbitrary command accepted from the loop request.
    - No auto-proposal without guard/approval.
    - No auto-apply without an existing approved automation approval.
    - No auto-rollback.
    - No provider call unless allow_provider_call=True.
    - No Claude/Codex provider in v1.
    - No approval bypass, no guard bypass, no execute_run, no asyncio.create_task.
    """
    step_id: str | None = None
    max_iterations: int = 3
    max_actions_per_iteration: int = 5
    dry_run: bool = False
    allow_provider_call: bool = False
    allow_safe_commands: bool = False
    allow_low_risk_tool_calls: bool = True
    stop_on_approval_required: bool = True
    stop_on_blocked: bool = True
    stop_on_test_failure: bool = False
    stop_on_no_safe_action: bool = True


class BoundedAutonomousLoopIteration(BaseModel):
    """Audit record for one iteration of the bounded loop."""
    iteration: int
    # completed | stopped_for_approval | blocked | no_safe_action | failed | max_actions
    status: str
    step_id: str | None = None
    queue_action: str | None = None
    executed_actions: list[AutomationActionResult] = Field(default_factory=list)
    approvals_required: list[str] = Field(default_factory=list)
    blocked_reasons: list[str] = Field(default_factory=list)
    # passed | failed | skipped | None
    test_status: str | None = None
    next_recommended_action: str | None = None
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class BoundedAutonomousLoopResponse(BaseModel):
    """Full response from the bounded patch-test-fix loop endpoint."""
    run_id: str
    step_id: str | None = None
    dry_run: bool
    # completed | stopped_for_approval | blocked | max_iterations_reached |
    # no_safe_action | failed
    status: str
    iterations: list[BoundedAutonomousLoopIteration] = Field(default_factory=list)
    final_queue_summary: OperatorQueueSummary | None = None
    final_recommended_action: str | None = None
    approvals_required: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    # Stop-reason fields for operator clarity (GAP-011)
    # completed | no_items | pending_approval | needs_approval | blocked_guard |
    # test_failed | action_failed | max_iterations
    stop_reason: str | None = None
    blocked_action_type: str | None = None
    pending_approval_id: str | None = None
    pending_approval_action_type: str | None = None


# ── Full Delivery Loop v1 ─────────────────────────────────────────────────────


class StepModuleDeliverySummary(BaseModel):
    """Module awareness summary for one delivered run step."""
    step_id: str
    step_title: str
    touched_modules: list[str] = Field(default_factory=list)
    expected_modules: list[str] = Field(default_factory=list)
    touched_files: list[str] = Field(default_factory=list)
    unknown_files: list[str] = Field(default_factory=list)
    module_policy_verdicts: list[str] = Field(default_factory=list)
    module_warnings: list[str] = Field(default_factory=list)
    module_risks: list[str] = Field(default_factory=list)
    module_test_hints: list[str] = Field(default_factory=list)


class RunModuleDeliverySummary(BaseModel):
    """Aggregate module awareness summary for a delivery report."""
    has_module_data: bool = False
    touched_modules: list[str] = Field(default_factory=list)
    expected_modules: list[str] = Field(default_factory=list)
    unknown_files: list[str] = Field(default_factory=list)
    sensitive_modules: list[str] = Field(default_factory=list)
    warning_count: int = 0
    blocked_policy_count: int = 0
    recommended_tests: list[str] = Field(default_factory=list)
    per_step: list[StepModuleDeliverySummary] = Field(default_factory=list)


class StepDeliverySummary(BaseModel):
    """Delivery summary for one run step."""
    step_id: str
    step_title: str
    # Step lifecycle status (from RunStep.status)
    status: str
    # Delivery readiness: not_started | in_progress | blocked | needs_tests |
    #   tests_failed | awaiting_approval | ready_for_review | delivered_with_warnings
    readiness: str
    requirement_ids: list[str] = Field(default_factory=list)
    # guard decision: allowed | blocked | warning | stale | none
    guard_status: str = "none"
    # proposal: proposed | none
    proposal_status: str = "none"
    # apply: applied | none
    apply_status: str = "none"
    # test: passed | failed | none
    test_status: str = "none"
    # fix: drafted | none
    fix_status: str = "none"
    # approval: approved | pending | rejected | executed | none
    approval_status: str = "none"
    changed_files: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    module_summary: StepModuleDeliverySummary | None = None


class RunDeliverySummary(BaseModel):
    """Aggregate delivery summary for a run."""
    run_id: str
    project_id: str | None = None
    project_name: str | None = None
    # Overall readiness (most conservative step readiness).
    # Valid values: not_started | in_progress | blocked | needs_tests |
    #   tests_failed | awaiting_approval | ready_for_review | delivered_with_warnings
    readiness: str
    total_steps: int
    ready_steps: int
    blocked_steps: int
    needs_test_steps: int
    failed_test_steps: int
    # Steps with a pending automation approval (v2)
    approval_pending_steps: int = 0
    changed_files: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)
    guards_total: int = 0
    proposals_total: int = 0
    applies_total: int = 0
    tests_total: int = 0
    approvals_total: int = 0
    unresolved_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    recommended_next_action: str | None = None
    module_summary: RunModuleDeliverySummary | None = None


class DeliveryReportRequest(BaseModel):
    """Request body for POST /api/runs/{run_id}/delivery-report."""
    include_markdown: bool = True
    include_step_details: bool = True
    include_tool_history: bool = True
    max_markdown_chars: int = 30000


class DeliveryReportResponse(BaseModel):
    """Full delivery report response."""
    run_id: str
    generated_at: str
    summary: RunDeliverySummary
    steps: list[StepDeliverySummary] = Field(default_factory=list)
    markdown_report: str = ""
    safety_notes: list[str] = Field(default_factory=list)


# ── Persistent Source of Truth v1 ─────────────────────────────────────────────

# Secret-like patterns that must not be stored in SoT documents.
_SOT_SENSITIVE_KEY_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)",
    re.IGNORECASE,
)
_SOT_SENSITIVE_VALUE_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_SOT_DATABASE_URL_WITH_CREDS_RE = re.compile(
    r"(postgres|mysql|mongodb|redis|sqlite)(\+\w+)?://[^@\s]+:[^@\s]+@",
    re.IGNORECASE,
)


def _sot_contains_secret(text: str) -> bool:
    """Return True if *text* contains a secret-like key=value assignment."""
    return bool(
        _SOT_SENSITIVE_VALUE_RE.search(text)
        or _SOT_DATABASE_URL_WITH_CREDS_RE.search(text)
    )


def _sot_validate_no_secrets(value: str, field_name: str) -> str:
    """Raise ValueError if value contains embedded secrets."""
    if _sot_contains_secret(value):
        raise ValueError(
            f"{field_name} must not contain secret-like values "
            "(API keys, tokens, passwords, credentials, or connection strings with credentials)"
        )
    return value


class ProjectSourceOfTruthRequirement(BaseModel):
    """Flat, storable requirement inside a Source of Truth document."""
    id: str
    title: str
    description: str = ""
    priority: str = "unknown"   # must | should | could | wont | unknown
    status: str = "proposed"    # proposed | confirmed | assumed | missing | rejected | implemented | needs_validation
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("title", "description", mode="before")
    @classmethod
    def _no_secrets_in_text(cls, value: object) -> object:
        if isinstance(value, str) and _sot_contains_secret(value):
            raise ValueError("Requirement text must not contain secret-like values")
        return value

    @field_validator("acceptance_criteria", "constraints", "tags", mode="before")
    @classmethod
    def _no_secrets_in_list_fields(cls, value: object) -> object:
        """Reject any list item that contains a secret-like value."""
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str) and _sot_contains_secret(item):
                    raise ValueError(
                        f"Requirement list field item [{i}] must not contain secret-like values "
                        "(API keys, tokens, passwords, credentials, or connection strings with credentials)"
                    )
        return value


class ProjectSourceOfTruthDecision(BaseModel):
    """Architectural or product decision recorded in a Source of Truth document."""
    id: str
    title: str
    description: str = ""
    status: str = "proposed"   # proposed | accepted | superseded | rejected
    rationale: str = ""
    consequences: str = ""

    @field_validator("title", "description", "rationale", "consequences", mode="before")
    @classmethod
    def _no_secrets_in_text(cls, value: object) -> object:
        if isinstance(value, str) and _sot_contains_secret(value):
            raise ValueError("Decision text must not contain secret-like values")
        return value


class ProjectSourceOfTruthDocument(BaseModel):
    """Flat, persistable Source of Truth document for a project.

    Stored as JSON in the ``project_source_of_truth`` table.
    Intentionally simpler than ``ProjectSourceOfTruthContract`` so that it
    maps cleanly to a single DB row and is easy to display in the UI.
    """
    id: str = Field(default="")
    project_id: str
    version: int = 1
    # draft | active | archived
    status: str = "draft"
    product_name: str = ""
    product_summary: str = ""
    project_intent: str = ""
    target_users: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    requirements: list[ProjectSourceOfTruthRequirement] = Field(default_factory=list)
    # Free-text constraint descriptions (e.g. "Must run offline")
    constraints: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    # Free-text acceptance criteria not tied to a specific requirement
    acceptance_criteria: list[str] = Field(default_factory=list)
    architecture_notes: str = ""
    decisions: list[ProjectSourceOfTruthDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    # Source of the document (e.g. "user_input" | "intake_preview" | "manual")
    source: str = "manual"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None

    @field_validator(
        "product_name", "product_summary", "project_intent", "architecture_notes", mode="before"
    )
    @classmethod
    def _no_secrets_in_free_text(cls, value: object) -> object:
        if isinstance(value, str) and _sot_contains_secret(value):
            raise ValueError(
                "Source of Truth document fields must not contain secret-like values "
                "(API keys, tokens, passwords, credentials)"
            )
        return value


# ── SoT API request / response models ────────────────────────────────────────


class SourceOfTruthUpsertRequest(BaseModel):
    """Request body for PUT /api/projects/{project_id}/source-of-truth.

    Creates a new version or replaces the current draft.
    Does not auto-publish — the caller must set status='active' explicitly.
    """
    product_name: str = ""
    product_summary: str = ""
    project_intent: str = ""
    target_users: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    non_goals: list[str] = Field(default_factory=list)
    requirements: list[ProjectSourceOfTruthRequirement] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    forbidden_changes: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    architecture_notes: str = ""
    decisions: list[ProjectSourceOfTruthDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    source: str = "manual"
    # If "active" the previous active version is archived; if omitted stays "draft"
    status: str = "draft"

    @field_validator(
        "product_name", "product_summary", "project_intent", "architecture_notes", mode="before"
    )
    @classmethod
    def _no_secrets_in_free_text(cls, value: object) -> object:
        if isinstance(value, str) and _sot_contains_secret(value):
            raise ValueError(
                "Source of Truth request fields must not contain secret-like values"
            )
        return value


class SourceOfTruthResponse(BaseModel):
    """Full Source of Truth document as returned by the API."""
    project_id: str
    document: ProjectSourceOfTruthDocument | None = None
    found: bool = False
    warnings: list[str] = Field(default_factory=list)


class SourceOfTruthHistoryItem(BaseModel):
    """Summary row for version history listing."""
    id: str
    project_id: str
    version: int
    status: str
    product_name: str
    source: str
    created_at: str
    updated_at: str | None = None
    archived_at: str | None = None


class SourceOfTruthHistoryResponse(BaseModel):
    """Version history for a project's Source of Truth."""
    project_id: str
    versions: list[SourceOfTruthHistoryItem] = Field(default_factory=list)
    total: int = 0


class SourceOfTruthValidationResponse(BaseModel):
    """Result of validating a Source of Truth document or upsert request."""
    valid: bool
    # low | medium | high | critical
    drift_risk: str = "low"
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceOfTruthSummaryResponse(BaseModel):
    """Concise mission summary derived from the active Source of Truth document."""
    project_id: str
    found: bool
    summary: str = ""
    requirement_context: str = ""
    warnings: list[str] = Field(default_factory=list)


# ── Project Module Map v1 ──────────────────────────────────────────────────────

# Secret-like patterns that must not be stored in module map text fields.
_MODULE_MAP_SECRET_RE = re.compile(
    r"(password|passwd|secret|token|credential|api[_\-]?key|private[_\-]?key|access[_\-]?key)\s*[:=]\s*\S+",
    re.IGNORECASE,
)
_MODULE_MAP_DB_URL_RE = re.compile(
    r"(postgres|mysql|mongodb|redis|sqlite)(\+\w+)?://[^@\s]+:[^@\s]+@",
    re.IGNORECASE,
)

# Path components that indicate path traversal or secrets.
_TRAVERSAL_PATTERNS = re.compile(r"\.\.")
_SECRET_PATHS = re.compile(
    r"(^|/)(\.env|\.env\.local|\.envrc|secrets?\.yaml|secrets?\.json|secrets?\.toml|\.pem|\.key|\.p12|\.pfx)(/|$)",
    re.IGNORECASE,
)


def _module_map_contains_secret(text: str) -> bool:
    """Return True if text contains a secret-like key=value or DB URL with credentials."""
    return bool(_MODULE_MAP_SECRET_RE.search(text) or _MODULE_MAP_DB_URL_RE.search(text))


def _module_map_path_is_safe(path: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Rejects traversal and secret-like paths."""
    if _TRAVERSAL_PATTERNS.search(path):
        return False, f"Path contains traversal component: {path!r}"
    if path.startswith("/") or (len(path) > 1 and path[1] == ":"):
        return False, f"Absolute path not allowed: {path!r}"
    if _SECRET_PATHS.search(path):
        return False, f"Path appears to reference a secrets file: {path!r}"
    return True, ""


VALID_MODULE_TYPES = frozenset({
    "feature", "backend", "frontend", "database", "shared",
    "tests", "infrastructure", "docs", "unknown",
})

VALID_CONFIDENCE_LEVELS = frozenset({"low", "medium", "high"})
VALID_MAP_STATUSES = frozenset({"active", "draft", "archived"})


class ProjectModuleMapItem(BaseModel):
    """One product module in a project module map."""
    id: str
    name: str
    slug: str
    description: str = ""
    module_type: str = "feature"
    responsibilities: list[str] = Field(default_factory=list)
    paths: list[str] = Field(default_factory=list)
    key_files: list[str] = Field(default_factory=list)
    related_requirements: list[str] = Field(default_factory=list)
    test_hints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: str = "medium"

    @field_validator("name", "slug", "description", mode="before")
    @classmethod
    def _no_secrets_in_text(cls, value: object) -> object:
        if isinstance(value, str) and _module_map_contains_secret(value):
            raise ValueError("Module map text fields must not contain secret-like values")
        return value

    @field_validator("responsibilities", "test_hints", "risks", mode="before")
    @classmethod
    def _no_secrets_in_list_text(cls, value: object) -> object:
        if isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str) and _module_map_contains_secret(item):
                    raise ValueError(
                        f"Module map list field item [{i}] must not contain secret-like values"
                    )
        return value

    @field_validator("paths", "key_files", mode="before")
    @classmethod
    def _safe_paths(cls, value: object) -> object:
        if isinstance(value, list):
            for i, p in enumerate(value):
                if isinstance(p, str):
                    ok, reason = _module_map_path_is_safe(p)
                    if not ok:
                        raise ValueError(f"paths[{i}]: {reason}")
        return value

    @field_validator("module_type", mode="before")
    @classmethod
    def _valid_module_type(cls, value: object) -> object:
        if isinstance(value, str) and value not in VALID_MODULE_TYPES:
            # Coerce unknown types to "unknown" rather than hard-reject
            return "unknown"
        return value

    @field_validator("confidence", mode="before")
    @classmethod
    def _valid_confidence(cls, value: object) -> object:
        if isinstance(value, str) and value not in VALID_CONFIDENCE_LEVELS:
            return "medium"
        return value


class ProjectModuleMapDocument(BaseModel):
    """Persisted module map for a project."""
    id: str = ""
    project_id: str
    version: int = 1
    status: str = "active"
    modules: list[ProjectModuleMapItem] = Field(default_factory=list)
    ignored_paths: list[str] = Field(default_factory=list)
    scan_summary: str = ""
    source: str = "manual"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str | None = None

    @field_validator("ignored_paths", mode="before")
    @classmethod
    def _safe_ignored_paths(cls, value: object) -> object:
        if isinstance(value, list):
            for i, p in enumerate(value):
                if isinstance(p, str) and _TRAVERSAL_PATTERNS.search(p):
                    raise ValueError(f"ignored_paths[{i}] contains path traversal")
        return value


class ProjectModuleMapUpsertRequest(BaseModel):
    """Request body for PUT /api/projects/{project_id}/module-map."""
    modules: list[ProjectModuleMapItem] = Field(default_factory=list)
    ignored_paths: list[str] = Field(default_factory=list)
    scan_summary: str = ""
    source: str = "manual"
    status: str = "active"

    @field_validator("ignored_paths", mode="before")
    @classmethod
    def _safe_ignored_paths(cls, value: object) -> object:
        if isinstance(value, list):
            for i, p in enumerate(value):
                if isinstance(p, str) and _TRAVERSAL_PATTERNS.search(p):
                    raise ValueError(f"ignored_paths[{i}] contains path traversal")
        return value


class ProjectModuleMapResponse(BaseModel):
    """Full module map as returned by the API."""
    project_id: str
    document: ProjectModuleMapDocument | None = None
    found: bool = False
    warnings: list[str] = Field(default_factory=list)


class ProjectModuleMapHistoryItem(BaseModel):
    """Summary row for module map version history."""
    id: str
    project_id: str
    version: int
    status: str
    module_count: int = 0
    source: str = "manual"
    scan_summary: str = ""
    created_at: str
    updated_at: str | None = None
    archived_at: str | None = None


class ProjectModuleMapHistoryResponse(BaseModel):
    """Version history of a project's module map."""
    project_id: str
    history: list[ProjectModuleMapHistoryItem] = Field(default_factory=list)
    total: int = 0


class ProjectModuleMapValidationResponse(BaseModel):
    """Result of validating a module map payload."""
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectModuleMapSummaryResponse(BaseModel):
    """Compact text summary of the active module map."""
    project_id: str
    found: bool
    summary: str = ""
    module_names: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ProjectModuleMapScanPreviewRequest(BaseModel):
    """Request body for POST /api/projects/{project_id}/module-map/scan-preview."""
    max_files: int = 300
    max_depth: int = 6
    extra_ignore_paths: list[str] = Field(default_factory=list)


class ProjectModuleMapScanPreviewResponse(BaseModel):
    """Result of the bounded deterministic scan preview. Not stored automatically."""
    project_id: str
    modules: list[ProjectModuleMapItem] = Field(default_factory=list)
    scan_summary: str = ""
    files_scanned: int = 0
    files_skipped: int = 0
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


# ── Project Context Cockpit v1 ─────────────────────────────────────────────────
#
# Read-only aggregated operator overview.
# No DB writes. No provider calls. No execute_run. No asyncio.create_task.
# No subprocess. No file content reads. No tool_calls created.


class CockpitSourceOfTruth(BaseModel):
    """Compact Source of Truth summary for the cockpit."""
    available: bool = False
    version: int | None = None
    product_name: str = ""
    requirement_count: int = 0
    risk_count: int = 0
    open_question_count: int = 0


class CockpitModuleMap(BaseModel):
    """Compact Module Map summary for the cockpit."""
    available: bool = False
    version: int | None = None
    module_count: int = 0
    key_modules: list[str] = Field(default_factory=list)


class CockpitRunStatus(BaseModel):
    """Compact run delivery status for the cockpit."""
    readiness: str = "not_started"
    completed_steps: int = 0
    total_steps: int = 0
    pending_approval_count: int = 0
    guard_blocker_count: int = 0
    tests_failed_count: int = 0


class CockpitModuleAwareness(BaseModel):
    """Compact module awareness summary for the cockpit."""
    touched_modules: list[str] = Field(default_factory=list)
    expected_modules: list[str] = Field(default_factory=list)
    blocked_policy_count: int = 0
    warning_count: int = 0
    recommended_tests: list[str] = Field(default_factory=list)


class CockpitNextAction(BaseModel):
    """Deterministic next-action recommendation for the operator.

    Display-only. Does not trigger any action.
    """
    label: str = ""
    reason: str = ""
    target_panel: str = ""
    # info | warning | blocked | ready
    severity: str = "info"


class ProjectContextCockpitSummary(BaseModel):
    """Read-only aggregated project context for the operator cockpit.

    Combines Source of Truth, Module Map, delivery status, and module awareness
    into a single compact response. No DB writes, no provider calls, no
    execute_run, no asyncio.create_task, no subprocess, no file content reads,
    no tool_calls created.
    """
    run_id: str
    has_project: bool = False
    project_id: str | None = None
    project_name: str | None = None
    source_of_truth: CockpitSourceOfTruth = Field(default_factory=CockpitSourceOfTruth)
    module_map: CockpitModuleMap = Field(default_factory=CockpitModuleMap)
    run: CockpitRunStatus = Field(default_factory=CockpitRunStatus)
    module_awareness: CockpitModuleAwareness = Field(default_factory=CockpitModuleAwareness)
    next_action: CockpitNextAction = Field(default_factory=CockpitNextAction)
    safety_notes: list[str] = Field(default_factory=list)

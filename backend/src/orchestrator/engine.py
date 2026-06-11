"""Orchestrator engine — the core task execution pipeline."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

from src.agents.registry import canonical_agent_id_for_role, get_agent, load_agent_instructions
from src.model_router import (
    EXTERNAL_PROVIDERS,
    LOCAL_OLLAMA,
    infer_agent_for_step,
    infer_task_type_for_agent,
    infer_task_type_for_step,
    model_route_decision_from_result,
    route_model,
)
from src.models import ModelRouteDecision, ModelRouteRequest, ProviderMode, RunStatus, RunStep
from src.providers import ollama
from src.storage.database import (
    create_run_step,
    update_run,
    update_run_step,
    upsert_model_route_decision,
    upsert_step_route_decision,
)
from src.utils.paths import resolve_runtime_path


def _status_value(status: object) -> str:
    """Normalize a status value to a lowercase string for comparisons.

    Handles enum-like objects with a `value` attribute or plain strings.
    """
    value = getattr(status, "value", status)
    return str(value).lower()


def _runtime_agent_id_for_step(step: RunStep) -> str:
    """Resolve a stored step agent value to a canonical runtime agent id."""
    stored_agent = str(step.agent_id or "").strip()
    if stored_agent and get_agent(stored_agent) and get_agent(stored_agent).id == stored_agent:
        return stored_agent
    if stored_agent:
        canonical = canonical_agent_id_for_role(stored_agent)
        if get_agent(canonical):
            return canonical
    inferred = infer_agent_for_step(step.title, step.input)
    canonical = canonical_agent_id_for_role(inferred)
    return canonical if get_agent(canonical) else "orchestrator"


async def execute_run(
    run_id: str,
    prompt: str,
    mode: str = "offline",
    run_dir: str = "",
    project_id: str = "",
    project_name: str = "",
    project_path: str = "",
    project_stack: str = "",
    selected_agents: list[dict] | None = None,
    provider_mode: str = "local",
    ollama_base_url: str = "http://localhost:11434",
    ollama_model: str = "qwen2.5-coder:7b",
) -> None:
    """
    Execute a task run through the orchestrator pipeline.

    Steps:
    1. Create run directory
    2. Save input.md
    3. Load orchestrator instructions
    4. Analyze product requirements
    5. Save product-spec.md and clarification-questions.md
    6. Call Ollama for planning
    7. Save plan.md
    8. Generate architecture.md
    9. Generate tasks.md
    10. Stage executable task steps
    11. Generate final report
    12. Save final-report.md
    """
    logs: list[str] = []
    active_step_id = ""
    route_decisions: list[ModelRouteDecision] = []
    route_warnings: list[str] = []

    def log(msg: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        logs.append(f"[{timestamp}] {msg}")
        update_run(run_id, logs=logs)

    def start_step(title: str, input_text: str = "") -> str:
        nonlocal active_step_id
        now = datetime.now().isoformat()
        step = create_run_step(
            run_id=run_id,
            title=title,
            agent_id="orchestrator",
            status=RunStatus.RUNNING.value,
            input=input_text,
            started_at=now,
        )
        active_step_id = step.id
        update_run(run_id, current_step_id=step.id)
        log(f"Step started: {title}")
        return step.id

    def complete_step(step_id: str, title: str, output: str = "") -> None:
        nonlocal active_step_id
        update_run_step(
            step_id,
            status=RunStatus.COMPLETED.value,
            output=output,
            finished_at=datetime.now().isoformat(),
        )
        if active_step_id == step_id:
            active_step_id = ""
            update_run(run_id, current_step_id="")
        log(f"Step completed: {title}")

    def fail_active_step(error: str) -> None:
        nonlocal active_step_id
        if not active_step_id:
            return
        update_run_step(
            active_step_id,
            status=RunStatus.FAILED.value,
            error=error,
            finished_at=datetime.now().isoformat(),
        )
        update_run(run_id, current_step_id="")
        active_step_id = ""

    def stop_active_step(reason: str) -> None:
        nonlocal active_step_id
        if not active_step_id:
            return
        update_run_step(
            active_step_id,
            status=RunStatus.STOPPED.value,
            error=reason,
            finished_at=datetime.now().isoformat(),
        )
        update_run(run_id, current_step_id="")
        active_step_id = ""

    try:
        step_id = start_step(
            "Initialize run",
            f"Prepare run directory and mark run {run_id} as running.",
        )
        update_run(run_id, status=RunStatus.RUNNING.value)
        log("Run started")

        # 1. Create run directory
        run_path = resolve_runtime_path(run_dir, "runs")
        run_path.mkdir(parents=True, exist_ok=True)
        log(f"Created run directory: {run_dir}")
        complete_step(step_id, "Initialize run", f"Run directory: {run_path}")

        # 2. Save input
        step_id = start_step("Capture task input", prompt)
        input_file = run_path / "input.md"
        input_file.write_text(
            _format_input(
                prompt=prompt,
                mode=mode,
                project_id=project_id,
                project_name=project_name,
                project_path=project_path,
                project_stack=project_stack,
                selected_agents=selected_agents or [],
            ),
            encoding="utf-8",
        )
        log("Saved input.md")
        complete_step(step_id, "Capture task input", "Saved input.md")

        if selected_agents:
            step_id = start_step(
                "Preview model routes",
                "Persist model/provider route decisions for assigned agents.",
            )
            try:
                route_decisions, route_warnings = await _persist_model_route_preview(
                    run_id=run_id,
                    selected_agents=selected_agents,
                    provider_mode=provider_mode,
                    ollama_base_url=ollama_base_url,
                )
                (run_path / "model-routes.md").write_text(
                    "# Model Route Decisions\n\n"
                    f"{_format_model_route_decisions(route_decisions, route_warnings)}\n",
                    encoding="utf-8",
                )
                log(f"Persisted {len(route_decisions)} model route decisions")
                complete_step(
                    step_id,
                    "Preview model routes",
                    _format_model_route_decisions(route_decisions, route_warnings),
                )
            except Exception as exc:
                route_warnings.append(f"Model route preview failed: {exc}")
                log(f"WARNING: Model route preview failed: {exc}")
                complete_step(
                    step_id,
                    "Preview model routes",
                    f"Model route preview skipped: {exc}",
                )

        # 3. Load orchestrator instructions
        step_id = start_step("Load orchestrator instructions", "Load role instructions for the orchestrator agent.")
        instructions = load_agent_instructions("orchestrator")
        if not instructions:
            instructions = "You are an AI orchestrator. Analyze the task and create a detailed plan."
        log("Loaded orchestrator instructions")
        complete_step(step_id, "Load orchestrator instructions", "Loaded orchestrator instructions")

        # 4. Product requirements and clarification questions
        step_id = start_step(
            "Analyze product requirements",
            f"Provider: Ollama\nModel: {ollama_model}\nBase URL: {ollama_base_url}",
        )
        healthy = await ollama.check_health(ollama_base_url)
        if not healthy:
            log("WARNING: Ollama is not reachable. Using fallback product requirements.")
            product_spec = _fallback_product_spec(
                prompt=prompt,
                project_id=project_id,
                project_name=project_name,
                project_path=project_path,
                project_stack=project_stack,
            )
            requirements_output = "Ollama unreachable; generated fallback product spec."
        else:
            log(f"Ollama is healthy. Using model for requirements: {ollama_model}")
            try:
                product_spec = await ollama.chat_completion(
                    prompt=_product_requirements_prompt(
                        prompt=prompt,
                        project_id=project_id,
                        project_name=project_name,
                        project_path=project_path,
                        project_stack=project_stack,
                    ),
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_base_url,
                )
                requirements_output = "Received product spec from Ollama."
                log("Received product spec from Ollama")
            except Exception as e:
                product_spec = _fallback_product_spec(
                    prompt=prompt,
                    project_id=project_id,
                    project_name=project_name,
                    project_path=project_path,
                    project_stack=project_stack,
                )
                requirements_output = f"Ollama requirements call failed: {e}. Generated fallback product spec."
                log(f"Ollama requirements call failed: {e}. Using fallback.")
        clarifying_questions = _extract_clarifying_questions(product_spec) or _fallback_clarifying_questions(prompt)
        complete_step(step_id, "Analyze product requirements", f"{requirements_output}\n\n{product_spec}")

        step_id = start_step(
            "Save requirements artifacts",
            "Write product-spec.md and clarification-questions.md.",
        )
        spec_file = run_path / "product-spec.md"
        spec_file.write_text(f"# Product Spec\n\n{product_spec}\n", encoding="utf-8")
        questions_file = run_path / "clarification-questions.md"
        questions_file.write_text(
            f"# Clarification Questions\n\n{clarifying_questions}\n",
            encoding="utf-8",
        )
        log("Saved product-spec.md")
        log("Saved clarification-questions.md")
        complete_step(
            step_id,
            "Save requirements artifacts",
            "Saved product-spec.md and clarification-questions.md",
        )

        # 5. Create execution plan
        step_id = start_step(
            "Create execution plan",
            f"Provider: Ollama\nModel: {ollama_model}\nBase URL: {ollama_base_url}",
        )
        if not healthy:
            log("WARNING: Ollama is not reachable. Using fallback planning.")
            plan_text = _fallback_plan(prompt)
            planning_output = "Ollama unreachable; generated fallback plan."
        else:
            log(f"Ollama is healthy. Using model: {ollama_model}")
            # 5. Call Ollama for planning
            planning_prompt = (
                f"Analyze the following task and create a detailed execution plan.\n\n"
                f"## Task\n{prompt}\n\n"
                f"## Project Context\n"
                f"- Project ID: {project_id or 'unassigned'}\n"
                f"- Project Name: {project_name or 'unassigned'}\n"
                f"- Project Path: {project_path or 'unassigned'}\n"
                f"- Project Stack: {project_stack or 'unspecified'}\n\n"
                f"## Selected Agent Team\n{_format_selected_agents(selected_agents or [])}\n\n"
                f"## Product Spec\n{product_spec}\n\n"
                f"## Clarifying Questions\n{clarifying_questions}\n\n"
                f"## Requirements\n"
                f"- Break down into concrete steps\n"
                f"- Identify which specialist agents should handle each step\n"
                f"- List any files that need to be created or modified\n"
                f"- Note any commands that might need approval\n"
                f"- Estimate complexity per step\n\n"
                f"Respond with a structured plan in Markdown format."
            )
            try:
                plan_text = await ollama.chat_completion(
                    prompt=planning_prompt,
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_base_url,
                )
                log("Received plan from Ollama")
                planning_output = "Received plan from Ollama."
            except Exception as e:
                log(f"Ollama call failed: {e}. Using fallback.")
                plan_text = _fallback_plan(prompt)
                planning_output = f"Ollama call failed: {e}. Generated fallback plan."
        complete_step(step_id, "Create execution plan", f"{planning_output}\n\n{plan_text}")

        # 6. Save plan
        step_id = start_step("Save plan artifact", "Write plan.md and persist plan text on the run.")
        plan_file = run_path / "plan.md"
        plan_file.write_text(f"# Execution Plan\n\n{plan_text}\n", encoding="utf-8")
        update_run(run_id, plan=plan_text)
        log("Saved plan.md")
        complete_step(step_id, "Save plan artifact", "Saved plan.md")

        step_id = start_step("Generate architecture artifact", "Create architecture.md from spec and plan.")
        if healthy:
            try:
                architecture_text = await ollama.chat_completion(
                    prompt=build_architecture_prompt(
                        prompt=prompt,
                        product_spec=product_spec,
                        plan_text=plan_text,
                        project_id=project_id,
                        project_path=project_path,
                        project_stack=project_stack,
                    ),
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_base_url,
                )
                architecture_output = "Received architecture from Ollama."
            except Exception as e:
                architecture_text = fallback_architecture(prompt, product_spec, plan_text, project_stack)
                architecture_output = f"Ollama architecture call failed: {e}. Generated fallback architecture."
        else:
            architecture_text = fallback_architecture(prompt, product_spec, plan_text, project_stack)
            architecture_output = "Ollama unavailable; generated fallback architecture."
        (run_path / "architecture.md").write_text(f"# Architecture\n\n{architecture_text}\n", encoding="utf-8")
        log("Saved architecture.md")
        complete_step(step_id, "Generate architecture artifact", f"{architecture_output}\n\nSaved architecture.md")

        step_id = start_step("Generate task breakdown artifact", "Create tasks.md from spec, plan, and architecture.")
        if healthy:
            try:
                task_breakdown = await ollama.chat_completion(
                    prompt=build_task_breakdown_prompt(
                        prompt=prompt,
                        product_spec=product_spec,
                        plan_text=plan_text,
                        architecture_text=architecture_text,
                    ),
                    system=instructions,
                    model=ollama_model,
                    base_url=ollama_base_url,
                )
                tasks_output = "Received task breakdown from Ollama."
            except Exception as e:
                task_breakdown = fallback_task_breakdown(prompt, product_spec, plan_text, architecture_text)
                tasks_output = f"Ollama task breakdown call failed: {e}. Generated fallback tasks."
        else:
            task_breakdown = fallback_task_breakdown(prompt, product_spec, plan_text, architecture_text)
            tasks_output = "Ollama unavailable; generated fallback tasks."
        (run_path / "tasks.md").write_text(f"# Tasks\n\n{task_breakdown}\n", encoding="utf-8")
        log("Saved tasks.md")
        complete_step(step_id, "Generate task breakdown artifact", f"{tasks_output}\n\nSaved tasks.md")

        step_id = start_step(
            "Stage executable task steps",
            "Convert tasks.md into pending run_steps with agent assignments.",
        )
        staged_steps = stage_executable_task_steps(
            run_id=run_id,
            parent_step_id=step_id,
            task_breakdown=task_breakdown,
            architecture_text=architecture_text,
            project_stack=project_stack,
        )
        staged_summary = format_staged_steps(staged_steps)
        log(f"Staged {len(staged_steps)} executable task steps")
        complete_step(
            step_id,
            "Stage executable task steps",
            f"Created {len(staged_steps)} pending execution steps.\n\n{staged_summary}",
        )

        # 6b. Persist step-level model route decisions (non-fatal if it fails)
        step_route_decisions: dict[str, ModelRouteDecision] = {}
        step_route_warnings: list[str] = []
        if healthy and staged_steps:
            try:
                step_route_decisions, step_route_warnings = await _persist_step_route_decisions(
                    run_id=run_id,
                    staged_steps=staged_steps,
                    provider_mode=provider_mode,
                    ollama_base_url=ollama_base_url,
                    log_fn=log,
                )
                log(
                    f"Persisted {len(step_route_decisions)}/{len(staged_steps)} "
                    f"step-level model route decisions"
                    + (f" ({len(step_route_warnings)} failed)" if step_route_warnings else "")
                )
            except Exception as exc:
                log(f"WARNING: Step route decision persistence failed entirely: {exc}")

        # 6c. Execute staged steps through Ollama
        executed_count = 0
        if healthy and staged_steps:
            step_id = start_step(
                "Execute staged task steps",
                f"Run {len(staged_steps)} pending steps through Ollama.",
            )
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
                ollama_base_url=ollama_base_url,
                log_fn=log,
                step_route_decisions=step_route_decisions,
            )
            complete_step(
                step_id,
                "Execute staged task steps",
                f"Executed {executed_count}/{len(staged_steps)} staged steps.",
            )

        # 7. Generate final report
        step_id = start_step("Generate final report", "Create final-report.md with project context and artifacts.")
        has_step_failures = staged_steps and executed_count < len(staged_steps)
        completion_note = (
            f"Completed with partial step failures ({executed_count}/{len(staged_steps)} steps succeeded)."
            if has_step_failures
            else "Completed successfully."
        )
        report = (
            f"# Run Report\n\n"
            f"**Run ID:** {run_id}\n"
            f"**Mode:** {mode}\n"
            f"**Status:** {completion_note}\n"
            f"**Completed at:** {datetime.now().isoformat()}\n\n"
            f"## Project\n"
            f"- **Project ID:** {project_id or 'unassigned'}\n"
            f"- **Project Name:** {project_name or 'unassigned'}\n"
            f"- **Project Path:** {project_path or 'unassigned'}\n"
            f"- **Project Stack:** {project_stack or 'unspecified'}\n\n"
            f"## Selected Agent Team\n{_format_selected_agents(selected_agents or [])}\n\n"
            f"## Model Route Decisions\n{_format_model_route_decisions(route_decisions, route_warnings + step_route_warnings)}\n\n"
            f"## Input\n{prompt}\n\n"
            f"## Product Spec\n{product_spec}\n\n"
            f"## Clarification Questions\n{clarifying_questions}\n\n"
            f"## Plan\n{plan_text}\n\n"
            f"## Architecture\n{architecture_text}\n\n"
            f"## Tasks\n{task_breakdown}\n\n"
            f"## Executable Task Steps\n{staged_summary}\n\n"
            f"## Artifacts\n"
            f"- `input.md`\n"
            f"- `product-spec.md`\n"
            f"- `clarification-questions.md`\n"
            f"- `plan.md`\n"
            f"- `architecture.md`\n"
            f"- `tasks.md`\n"
            f"- `final-report.md`\n\n"
            f"## Notes\n"
            f"This is an AI Workbench orchestrator run. Staged task steps "
            f"are executed through Ollama when available. Review the timeline "
            f"for individual step outputs and any errors.\n"
        )
        report_file = run_path / "final-report.md"
        report_file.write_text(report, encoding="utf-8")
        log("Saved final-report.md")
        complete_step(step_id, "Generate final report", "Saved final-report.md")

        # 8. Mark complete
        step_id = start_step("Finalize run", "Mark run completed and attach artifact list.")
        artifacts = [
            "input.md",
            "product-spec.md",
            "clarification-questions.md",
            *(_optional_model_route_artifacts(route_decisions)),
            "plan.md",
            "architecture.md",
            "tasks.md",
            "final-report.md",
        ]
        update_run(
            run_id,
            status=RunStatus.COMPLETED.value,
            result=report,
            artifacts=artifacts,
            finished_at=datetime.now().isoformat(),
        )
        log("Run completed successfully")
        complete_step(step_id, "Finalize run", "Run completed successfully")

    except asyncio.CancelledError:
        stop_active_step("Run was cancelled by user.")
        log("Run cancelled by user")
        update_run(
            run_id,
            status=RunStatus.STOPPED.value,
            result="Run stopped by user.",
            current_step_id="",
            finished_at=datetime.now().isoformat(),
        )
        raise

    except Exception as e:
        fail_active_step(str(e))
        log(f"ERROR: {e}")
        update_run(
            run_id,
            status=RunStatus.FAILED.value,
            result=f"Run failed: {e}",
            current_step_id="",
            finished_at=datetime.now().isoformat(),
        )


async def _persist_model_route_preview(
    *,
    run_id: str,
    selected_agents: list[dict],
    provider_mode: str,
    ollama_base_url: str,
) -> tuple[list[ModelRouteDecision], list[str]]:
    mode = _provider_mode(provider_mode)
    available_models = await ollama.list_models(ollama_base_url)
    decisions: list[ModelRouteDecision] = []
    warnings: list[str] = []
    cfg = {"provider_mode": mode.value}

    for assignment in selected_agents:
        agent_id = str(assignment.get("agent_id", "")).strip()
        if not agent_id:
            continue
        assigned_role = str(assignment.get("assigned_role", ""))
        task_type = infer_task_type_for_agent(agent_id, assigned_role)
        try:
            route = route_model(
                ModelRouteRequest(
                    agent_id=agent_id,
                    task_type=task_type,
                    provider_mode=mode,
                    available_models=available_models,
                    project_privacy_level="private",
                ),
                cfg,
            )
            decision = model_route_decision_from_result(
                run_id=run_id,
                agent_id=agent_id,
                task_type=task_type,
                provider_mode=mode,
                route=route,
            )
            persisted = upsert_model_route_decision(
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
            decisions.append(persisted)
        except Exception as exc:
            warnings.append(f"Failed to route {agent_id}: {exc}")

    return decisions, warnings


async def _persist_step_route_decisions(
    *,
    run_id: str,
    staged_steps: list[RunStep],
    provider_mode: str,
    ollama_base_url: str,
    log_fn=None,
) -> tuple[dict[str, ModelRouteDecision], list[str]]:
    """Compute and persist a per-step model route decision for each staged step.

    Returns (step_id → ModelRouteDecision, warnings).
    Per-step failures are non-fatal — the step will execute with the run-level
    default Ollama model — but each failure is logged via ``log_fn`` and
    collected in the returned warnings list so they are visible in the run log.
    """
    _log = log_fn or (lambda _: None)
    mode = _provider_mode(provider_mode)
    available_models = await ollama.list_models(ollama_base_url)
    cfg = {"provider_mode": mode.value}
    step_routes: dict[str, ModelRouteDecision] = {}
    warnings: list[str] = []

    for step in staged_steps:
        agent_id = _runtime_agent_id_for_step(step)
        task_type = infer_task_type_for_step(step.title, step.input, agent_id)
        try:
            route = route_model(
                ModelRouteRequest(
                    agent_id=agent_id,
                    task_type=task_type,
                    provider_mode=mode,
                    available_models=available_models,
                    project_privacy_level="private",
                ),
                cfg,
            )
            decision = model_route_decision_from_result(
                run_id=run_id,
                agent_id=agent_id,
                task_type=task_type,
                provider_mode=mode,
                route=route,
                step_id=step.id,
            )
            persisted = upsert_step_route_decision(
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
            step_routes[step.id] = persisted
        except Exception as exc:
            # Non-fatal: step falls back to the run-level default Ollama model.
            msg = f"Step route decision failed for '{step.title}': {exc}"
            warnings.append(msg)
            _log(f"WARNING: {msg}")

    return step_routes, warnings


def _provider_mode(value: str) -> ProviderMode:
    try:
        return ProviderMode(str(value or "local"))
    except ValueError:
        return ProviderMode.LOCAL


def _optional_model_route_artifacts(route_decisions: list[ModelRouteDecision]) -> list[str]:
    return ["model-routes.md"] if route_decisions else []


# Safety limits for staged step execution
MAX_EXECUTABLE_STEPS = 12
STEP_TIMEOUT_SECONDS = 120  # per-step Ollama call timeout
TOTAL_EXECUTION_TIMEOUT_SECONDS = 900  # 15 minutes for all steps combined
MAX_CONSECUTIVE_FAILURES = 3  # stop execution after N failures in a row


async def _execute_staged_steps(
    *,
    staged_steps: list[RunStep],
    run_id: str,
    instructions: str,
    product_spec: str,
    plan_text: str,
    architecture_text: str,
    task_breakdown: str,
    project_stack: str,
    ollama_model: str,
    ollama_base_url: str,
    log_fn,
    step_route_decisions: dict[str, ModelRouteDecision] | None = None,
) -> int:
    """Execute each pending staged step through Ollama and record the output.

    Safety guarantees:
    - Only steps with status 'pending' are executed; completed/failed/running are skipped.
    - Hard cap of MAX_EXECUTABLE_STEPS steps per invocation.
    - Per-step timeout via asyncio.wait_for (STEP_TIMEOUT_SECONDS).
    - Total execution timeout (TOTAL_EXECUTION_TIMEOUT_SECONDS).
    - Consecutive failure breaker (MAX_CONSECUTIVE_FAILURES).
    - A single step failure does NOT crash the entire run.
    - CancelledError is always re-raised for graceful stop.
    """
    executed = 0
    failed = 0
    skipped = 0
    consecutive_failures = 0
    execution_start = datetime.now()

    # Enforce hard cap
    steps_to_run = staged_steps[:MAX_EXECUTABLE_STEPS]
    if len(staged_steps) > MAX_EXECUTABLE_STEPS:
        log_fn(
            f"WARNING: {len(staged_steps)} staged steps exceed limit of "
            f"{MAX_EXECUTABLE_STEPS}. Only first {MAX_EXECUTABLE_STEPS} will execute."
        )

    for step in steps_to_run:
        # Only skip steps that are already finished, failed, stopped, or running.
        non_executable = {
            str(RunStatus.COMPLETED.value).lower(),
            str(RunStatus.FAILED.value).lower(),
            str(RunStatus.STOPPED.value).lower(),
            str(RunStatus.RUNNING.value).lower(),
        }
        if _status_value(step.status) in non_executable:
            log_fn(f"Skipping step {step.title} (status: {step.status})")
            skipped += 1
            continue

        # Check total execution timeout
        elapsed = (datetime.now() - execution_start).total_seconds()
        if elapsed > TOTAL_EXECUTION_TIMEOUT_SECONDS:
            log_fn(
                f"Total execution timeout ({TOTAL_EXECUTION_TIMEOUT_SECONDS}s) reached "
                f"after {executed} steps. Remaining steps stay pending."
            )
            break

        # Check consecutive failure breaker
        if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            log_fn(
                f"Stopping execution: {MAX_CONSECUTIVE_FAILURES} consecutive failures. "
                f"Remaining steps stay pending."
            )
            break

        update_run_step(
            step.id,
            status=RunStatus.RUNNING.value,
            started_at=datetime.now().isoformat(),
        )
        update_run(run_id, current_step_id=step.id)
        log_fn(f"Executing step: {step.title}")

        runtime_agent_id = _runtime_agent_id_for_step(step)
        step_prompt = (
            f"You are agent `{runtime_agent_id}` working on a software project.\n\n"
            f"Stored step agent id: `{step.agent_id or 'unassigned'}`.\n\n"
            f"## Your Assignment\n{step.input}\n\n"
            f"## Project Stack\n{project_stack or 'unspecified'}\n\n"
            f"## Product Spec (summary)\n{_truncate_context(product_spec, 800)}\n\n"
            f"## Architecture (summary)\n{_truncate_context(architecture_text, 800)}\n\n"
            f"## Instructions\n"
            f"Analyze the assignment and provide a concrete, actionable response.\n"
            f"Include: what files to inspect or change, what commands to run, "
            f"what the expected outcome is, and any risks or open questions.\n"
            f"Be specific and practical — this output will be reviewed by the orchestrator."
        )

        try:
            # Resolve per-step model from route decisions; fall back to run-level default.
            step_route = (step_route_decisions or {}).get(step.id)
            if step_route and step_route.selected_provider == LOCAL_OLLAMA:
                model_for_step = step_route.selected_model
            elif step_route and step_route.selected_provider in EXTERNAL_PROVIDERS:
                # External providers are NOT invoked; use local fallback with a warning.
                model_for_step = step_route.fallback_model or ollama_model
                log_fn(
                    f"WARNING: Step '{step.title}' routed to external provider "
                    f"'{step_route.selected_provider}' which is not supported for execution. "
                    f"Using local fallback model '{model_for_step}'."
                )
            else:
                model_for_step = ollama_model

            # Load per-agent instructions for this step (alignment only — no execution change).
            # Falls back to run-level orchestrator instructions if no agent-specific file exists.
            step_instructions = (
                load_agent_instructions(runtime_agent_id)
                or load_agent_instructions(step.agent_id or "")
                or instructions
            )

            # Call chat_completion and support both coroutine and sync implementations
            try:
                maybe_coro = ollama.chat_completion(
                    prompt=step_prompt,
                    system=step_instructions,
                    model=model_for_step,
                    base_url=ollama_base_url,
                )
            except TypeError:
                # Fallback to positional call for callables that don't accept keyword args
                maybe_coro = ollama.chat_completion(
                    step_prompt, step_instructions, model_for_step, ollama_base_url
                )
            if asyncio.iscoroutine(maybe_coro):
                output = await asyncio.wait_for(maybe_coro, timeout=STEP_TIMEOUT_SECONDS)
            else:
                # sync implementation (or mocked sync) — call directly
                output = maybe_coro
            update_run_step(
                step.id,
                status=RunStatus.COMPLETED.value,
                output=output,
                finished_at=datetime.now().isoformat(),
            )
            log_fn(f"Step completed: {step.title}")
            executed += 1
            consecutive_failures = 0
        except asyncio.CancelledError:
            update_run_step(
                step.id,
                status=RunStatus.STOPPED.value,
                error="Run cancelled during step execution.",
                finished_at=datetime.now().isoformat(),
            )
            raise
        except asyncio.TimeoutError:
            error_msg = f"Step timed out after {STEP_TIMEOUT_SECONDS}s"
            update_run_step(
                step.id,
                status=RunStatus.FAILED.value,
                error=error_msg,
                finished_at=datetime.now().isoformat(),
            )
            log_fn(f"Step timed out: {step.title}")
            failed += 1
            consecutive_failures += 1
        except Exception as exc:
            update_run_step(
                step.id,
                status=RunStatus.FAILED.value,
                error=str(exc),
                finished_at=datetime.now().isoformat(),
            )
            log_fn(f"Step failed: {step.title}: {exc}")
            failed += 1
            consecutive_failures += 1

    update_run(run_id, current_step_id="")
    log_fn(f"Step execution summary: {executed} completed, {failed} failed, {skipped} skipped")
    return executed


def _truncate_context(text: str, max_chars: int) -> str:
    """Trim long context strings to keep prompts within reasonable size."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[...truncated]"


def _fallback_plan(prompt: str) -> str:
    """Generate a basic plan when Ollama is unavailable."""
    return (
        f"## Fallback Plan (Ollama unavailable)\n\n"
        f"**Task:** {prompt}\n\n"
        f"### Steps\n"
        f"1. Analyze the task requirements\n"
        f"2. Identify relevant files and components\n"
        f"3. Implement changes (requires manual execution)\n"
        f"4. Run tests to verify\n"
        f"5. Create documentation\n\n"
        f"*Note: This is a fallback plan generated without AI assistance. "
        f"Start Ollama and retry for a detailed AI-generated plan.*\n"
    )


def build_architecture_prompt(
    prompt: str,
    product_spec: str,
    plan_text: str,
    project_id: str = "",
    project_path: str = "",
    project_stack: str = "",
) -> str:
    return (
        "Create a practical software architecture document for this project.\n\n"
        f"## Original Request\n{prompt}\n\n"
        "## Project Context\n"
        f"- Project ID: {project_id or 'unassigned'}\n"
        f"- Project Path: {project_path or 'unassigned'}\n"
        f"- Project Stack: {project_stack or 'unspecified'}\n\n"
        f"## Product Spec\n{product_spec}\n\n"
        f"## Execution Plan\n{plan_text}\n\n"
        "## Output Format\n"
        "Return Markdown with these sections:\n"
        "1. System Overview\n"
        "2. Main Modules\n"
        "3. Data Model\n"
        "4. API / Integration Boundaries\n"
        "5. UI Structure\n"
        "6. Testing Strategy\n"
        "7. Security and Safety Constraints\n"
        "8. Implementation Notes"
    )


def fallback_architecture(prompt: str, product_spec: str, plan_text: str, project_stack: str = "") -> str:
    return (
        "## System Overview\n\n"
        f"Build the requested product in small verified increments: {prompt}\n\n"
        "## Main Modules\n\n"
        "- Product/spec layer for requirements and acceptance criteria.\n"
        "- Application layer for user-facing workflows.\n"
        "- Persistence layer for project/run artifacts and execution history.\n"
        "- Safety layer for approvals, scoped execution, and command policy.\n\n"
        "## Data Model\n\n"
        "- Keep project/run metadata normalized.\n"
        "- Store generated artifacts as files under the run directory.\n"
        "- Store execution history as timeline steps and tool calls.\n\n"
        "## API / Integration Boundaries\n\n"
        "- Use backend APIs for all UI actions.\n"
        "- Keep project filesystem access scoped to configured project paths.\n"
        "- Route risky commands through approval gates.\n\n"
        "## UI Structure\n\n"
        "- Show spec, questions, plan, architecture, tasks, timeline, logs, and result per run.\n"
        "- Keep operator actions explicit and reversible where possible.\n\n"
        "## Testing Strategy\n\n"
        "- Add focused backend tests for every workflow transition.\n"
        "- Run configured project tests/builds only through safe commands.\n\n"
        "## Security and Safety Constraints\n\n"
        "- Never execute outside the selected project path.\n"
        "- Require approval for destructive commands, package installs, secrets, and git push.\n\n"
        "## Implementation Notes\n\n"
        f"- Stack: {project_stack or 'unspecified'}.\n"
        "- This fallback architecture was generated without Ollama.\n\n"
        "## Source Context\n\n"
        f"### Product Spec\n{product_spec}\n\n"
        f"### Plan\n{plan_text}\n"
    )


def build_task_breakdown_prompt(
    prompt: str,
    product_spec: str,
    plan_text: str,
    architecture_text: str,
) -> str:
    return (
        "Create an implementation task breakdown for an AI software studio.\n\n"
        f"## Original Request\n{prompt}\n\n"
        f"## Product Spec\n{product_spec}\n\n"
        f"## Plan\n{plan_text}\n\n"
        f"## Architecture\n{architecture_text}\n\n"
        "## Output Format\n"
        "Return Markdown with these sections:\n"
        "1. Milestones\n"
        "2. Ordered Tasks\n"
        "3. Agent Assignment Suggestions\n"
        "4. Files / Areas To Inspect First\n"
        "5. Verification Commands\n"
        "6. Acceptance Checklist\n"
        "7. Known Risks"
    )


def fallback_task_breakdown(
    prompt: str,
    product_spec: str,
    plan_text: str,
    architecture_text: str,
) -> str:
    return (
        "## Milestones\n\n"
        "1. Confirm scope and architecture.\n"
        "2. Implement the smallest useful vertical slice.\n"
        "3. Verify with safe tests/builds.\n"
        "4. Polish UX and documentation.\n\n"
        "## Ordered Tasks\n\n"
        "- Review project profile, stack, and safe commands.\n"
        "- Inspect existing file structure before editing.\n"
        "- Identify the first user-visible workflow to implement.\n"
        "- Make scoped code changes inside the selected project path.\n"
        "- Run configured tests/builds.\n"
        "- Record results, failures, and follow-up work.\n\n"
        "## Agent Assignment Suggestions\n\n"
        "- orchestrator: coordinate workflow and approvals.\n"
        "- repo-analyst: inspect project structure.\n"
        "- frontend/backend specialist: implement scoped changes based on stack.\n"
        "- qa: verify behavior and test results.\n"
        "- security: review risky actions and boundaries.\n\n"
        "## Files / Areas To Inspect First\n\n"
        "- Project root configuration and package files.\n"
        "- Source entry points.\n"
        "- Existing test/build scripts.\n"
        "- UI routes or backend API modules depending on task.\n\n"
        "## Verification Commands\n\n"
        "- Use only commands configured in the project safe command list.\n"
        "- Ask approval before package installs or destructive operations.\n\n"
        "## Acceptance Checklist\n\n"
        "- Main requested workflow is implemented or clearly planned.\n"
        "- Tests/builds pass or failures are reported with next actions.\n"
        "- No files outside the project scope are touched.\n"
        "- Final report summarizes artifacts and remaining risks.\n\n"
        "## Known Risks\n\n"
        "- Ambiguous requirements can cause overbuilding.\n"
        "- Missing safe commands can block verification.\n"
        "- Offline model failures require conservative fallback planning.\n\n"
        "## Source Context\n\n"
        f"### Original Request\n{prompt}\n\n"
        f"### Product Spec\n{product_spec}\n\n"
        f"### Plan\n{plan_text}\n\n"
        f"### Architecture\n{architecture_text}\n"
    )


def stage_executable_task_steps(
    *,
    run_id: str,
    parent_step_id: str,
    task_breakdown: str,
    architecture_text: str = "",
    project_stack: str = "",
    max_steps: int = 12,
) -> list[RunStep]:
    """Create pending child run steps from a Markdown task breakdown."""
    tasks = extract_executable_tasks(task_breakdown, max_steps=max_steps)
    if not tasks:
        tasks = [
            "Review project context and confirm the first implementation slice.",
            "Inspect relevant files before editing.",
            "Implement the smallest safe change.",
            "Run configured verification commands.",
            "Record results, risks, and follow-up work.",
        ]

    staged_steps: list[RunStep] = []
    for index, task in enumerate(tasks, start=1):
        agent_id = assign_agent_for_task(task, project_stack)
        staged_steps.append(
            create_run_step(
                run_id=run_id,
                parent_step_id=parent_step_id,
                agent_id=agent_id,
                status=RunStatus.PENDING.value,
                title=f"Task {index:02d}: {_trim_task_title(task)}",
                input=_format_executable_task_input(
                    task=task,
                    agent_id=agent_id,
                    project_stack=project_stack,
                    architecture_text=architecture_text,
                ),
            )
        )
    return staged_steps


def extract_executable_tasks(task_breakdown: str, max_steps: int = 12) -> list[str]:
    """Extract concrete tasks from a Markdown `Ordered Tasks` section."""
    section = _markdown_section(task_breakdown, "ordered tasks") or task_breakdown
    tasks: list[str] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^(?:[-*]\s+|\d+[.)]\s+)(.+)$", stripped)
        if not match:
            continue
        task = _clean_task_text(match.group(1))
        if task and task not in tasks:
            tasks.append(task)
        if len(tasks) >= max_steps:
            break
    return tasks


def assign_agent_for_task(task: str, project_stack: str = "") -> str:
    text = f"{task} {project_stack}".lower()
    if _contains_any(text, ["inspect", "review", "analyze", "structure", "dependency", "dependencies"]):
        return "repo_analyst"
    if _contains_any(text, ["test", "verify", "validation", "qa", "acceptance", "build"]):
        return "qa"
    if _contains_any(text, ["security", "secret", "approval", "auth", "permission", "vulnerability"]):
        return "security"
    if _contains_any(text, ["doc", "readme", "guide", "report"]):
        return "docs"
    if _contains_any(text, ["mobile", "android", "ios", "flutter", "react native"]):
        return "mobile"
    if _contains_any(text, ["frontend", "ui", "ux", "react", "vue", "angular", "css", "page", "component"]):
        return "frontend"
    if _contains_any(text, ["backend", "api", "database", "db", "sql", "server", "fastapi", "endpoint"]):
        return "backend"
    if _contains_any(text, ["coordinate", "scope", "plan", "orchestrate"]):
        return "orchestrator"
    return "orchestrator"


def format_staged_steps(staged_steps: list[RunStep]) -> str:
    if not staged_steps:
        return "No executable task steps were staged."
    return "\n".join(f"- `{step.status}` `{step.agent_id}` {step.title}" for step in staged_steps)


def _markdown_section(markdown: str, heading: str) -> str:
    lines = markdown.splitlines()
    section: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            normalized = stripped.lstrip("#").strip().lower()
            if in_section:
                break
            if heading in normalized:
                in_section = True
            continue
        if in_section:
            section.append(line)
    return "\n".join(section).strip()


def _clean_task_text(task: str) -> str:
    task = re.sub(r"^\[[ xX]\]\s+", "", task.strip())
    task = task.strip("` ")
    task = task.replace("**", "")
    return task.rstrip()


def _trim_task_title(task: str, max_length: int = 96) -> str:
    task = task.strip()
    if len(task) <= max_length:
        return task
    return task[: max_length - 3].rstrip() + "..."


def _format_executable_task_input(
    *,
    task: str,
    agent_id: str,
    project_stack: str,
    architecture_text: str,
) -> str:
    architecture_hint = _first_meaningful_line(architecture_text) or "See architecture.md for context."
    return (
        "## Assignment\n\n"
        f"- Agent: `{agent_id}`\n"
        f"- Status: pending execution\n"
        f"- Project stack: {project_stack or 'unspecified'}\n\n"
        "## Task\n\n"
        f"{task}\n\n"
        "## Context\n\n"
        f"{architecture_hint}\n\n"
        "Use `tasks.md`, `architecture.md`, and the run artifacts before taking action. "
        "Do not write files or run commands unless the orchestrator grants the required permissions."
    )


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped and not stripped.startswith("-"):
            return stripped
    return ""


def _contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _product_requirements_prompt(
    prompt: str,
    project_id: str = "",
    project_name: str = "",
    project_path: str = "",
    project_stack: str = "",
) -> str:
    return (
        "You are the product discovery lead for an AI software studio.\n"
        "Turn the user's request into a concise but useful product specification.\n\n"
        f"## User Request\n{prompt}\n\n"
        "## Project Context\n"
        f"- Project ID: {project_id or 'unassigned'}\n"
        f"- Project Name: {project_name or 'unassigned'}\n"
        f"- Project Path: {project_path or 'unassigned'}\n"
        f"- Project Stack: {project_stack or 'unspecified'}\n\n"
        "## Output Format\n"
        "Respond in Markdown with these exact sections:\n"
        "1. Product Goal\n"
        "2. Target Users\n"
        "3. Core User Flows\n"
        "4. Functional Requirements\n"
        "5. Non-Functional Requirements\n"
        "6. Assumptions\n"
        "7. Clarifying Questions\n\n"
        "Keep the spec practical for implementation. Ask only questions that would materially change the build."
    )


def _fallback_product_spec(
    prompt: str,
    project_id: str = "",
    project_name: str = "",
    project_path: str = "",
    project_stack: str = "",
) -> str:
    return (
        "## Product Goal\n\n"
        f"Build a product that satisfies the user request: {prompt}\n\n"
        "## Target Users\n\n"
        "- Primary user is the project owner or operator.\n"
        "- Secondary users should be identified during implementation planning.\n\n"
        "## Core User Flows\n\n"
        "- Open the product and understand the primary action.\n"
        "- Complete the main task without manual developer intervention.\n"
        "- Review outputs, errors, and next steps clearly.\n\n"
        "## Functional Requirements\n\n"
        "- Translate the request into concrete implementation tasks.\n"
        "- Preserve project context and generated artifacts.\n"
        "- Keep all actions visible in the run timeline.\n"
        "- Require approval for risky commands or unclear destructive actions.\n\n"
        "## Non-Functional Requirements\n\n"
        "- Work in offline-first mode when possible.\n"
        "- Keep execution scoped to the selected project path.\n"
        "- Prefer safe, testable increments over large unverified changes.\n"
        "- Produce clear reports for each run.\n\n"
        "## Assumptions\n\n"
        f"- Project ID: {project_id or 'unassigned'}.\n"
        f"- Project Name: {project_name or 'unassigned'}.\n"
        f"- Project Path: {project_path or 'unassigned'}.\n"
        f"- Project Stack: {project_stack or 'unspecified'}.\n"
        "- Ollama was unavailable or failed, so this fallback spec is intentionally conservative.\n\n"
        "## Clarifying Questions\n\n"
        f"{_fallback_clarifying_questions(prompt)}"
    )


def _fallback_clarifying_questions(prompt: str) -> str:
    return (
        "- What is the target audience and primary use case?\n"
        "- What is the minimum feature set required for the first usable version?\n"
        "- Are there design references, brand rules, or UX expectations to follow?\n"
        "- Which platforms must be supported first?\n"
        "- What should count as done for this request?\n"
        f"- Are there hidden constraints not mentioned in the original request: `{prompt}`?"
    )


def _extract_clarifying_questions(product_spec: str) -> str:
    marker = "clarifying questions"
    lines = product_spec.splitlines()
    for index, line in enumerate(lines):
        normalized = line.strip().lower().lstrip("#").strip()
        if marker in normalized:
            section = "\n".join(lines[index + 1:]).strip()
            return section
    return ""


def _format_input(
    prompt: str,
    mode: str,
    project_id: str = "",
    project_name: str = "",
    project_path: str = "",
    project_stack: str = "",
    selected_agents: list[dict] | None = None,
) -> str:
    return (
        "# Task Input\n\n"
        f"{prompt}\n\n"
        f"**Mode:** {mode}\n"
        f"**Created:** {datetime.now().isoformat()}\n\n"
        "## Project Context\n\n"
        f"- **Project ID:** {project_id or 'unassigned'}\n"
        f"- **Project Name:** {project_name or 'unassigned'}\n"
        f"- **Project Path:** {project_path or 'unassigned'}\n"
        f"- **Project Stack:** {project_stack or 'unspecified'}\n"
        f"\n## Selected Agent Team\n\n{_format_selected_agents(selected_agents or [])}\n"
    )


def _format_selected_agents(selected_agents: list[dict]) -> str:
    if not selected_agents:
        return "No agent team was assigned yet."
    lines = []
    for item in selected_agents:
        agent_id = item.get("agent_id", "unknown")
        role = item.get("assigned_role", "specialist")
        confidence = item.get("confidence", 0)
        reason = item.get("reason", "")
        lines.append(f"- `{agent_id}` as `{role}` ({confidence}): {reason}")
    return "\n".join(lines)


def _format_model_route_decisions(
    decisions: list[ModelRouteDecision],
    warnings: list[str] | None = None,
) -> str:
    lines: list[str] = []
    if decisions:
        for decision in decisions:
            warning_text = f" Warnings: {'; '.join(decision.warnings)}" if decision.warnings else ""
            lines.append(
                f"- `{decision.agent_id}` / `{decision.task_type}` → "
                f"`{decision.selected_provider}` / `{decision.selected_model}` "
                f"(profile `{decision.model_profile}`, confidence {decision.confidence:.2f}; "
                f"fallback `{decision.fallback_model or 'none'}`). "
                f"{decision.reason}{warning_text}"
            )
    else:
        lines.append("No model route decisions were persisted for this run.")

    for warning in warnings or []:
        lines.append(f"- Warning: {warning}")
    return "\n".join(lines)

# Model Router + Agent Runtime Alignment Fastlane v1

## Summary

Completed the fastlane alignment pass for model routing, canonical agent identity, and runtime per-agent instruction loading.

The codebase already had most of the installed-model matrix and canonical bridge mapping in place. This slice verified those paths and closed the remaining runtime gap: staged execution now resolves stored step agent aliases such as `backend`, `frontend`, and `qa` to canonical registry IDs before model routing and instruction loading.

No execution path was auto-started. No provider calls, tool calls, patch/apply behavior, tests-from-runtime behavior, or DB schema behavior were added.

## Why this fastlane block exists

Confirmed development run creation now produces real pending run steps. Before controlled autopilot work, model selection and agent identity need to agree across:

- model router profiles
- agent registry defaults
- confirmed development bridge step metadata
- staged engine execution
- agent-executions/run endpoint

This reduces drift before adding deeper autonomous runtime behavior.

## Model profile alignment

Validated active model profiles against installed model reality:

- `planning_reasoning`: `qwen3-coder:30b` primary/reasoning, `qwen2.5-coder:7b` fast/fallback
- `coding_heavy`: `qwen3-coder:30b` primary, `qwen2.5-coder:7b` fallback
- `debugging`: `qwen3-coder:30b` primary, `qwen2.5-coder:7b` fallback
- `security_review`: `qwen3-coder:30b` primary, `qwen2.5-coder:7b` fallback
- `documentation`: `qwen2.5-coder:7b` primary/fallback, `qwen3-coder:30b` reasoning

Routing tests confirm `qwen3-coder:30b` is selected when available and `qwen2.5-coder:7b` is used as the local fallback when the 30B model is unavailable.

## Config/registry alignment

Validated:

- `config.yaml` default model is `qwen3-coder:30b`
- `config.yaml` fast model is `qwen2.5-coder:7b`
- agent registry profile defaults align with model-router active profiles
- active profile primary models do not point to stale `qwen3:14b` or `deepseek-r1:14b`

The older model IDs remain only as optional registry entries/comments, not active defaults.

## Canonical agent_id mapping

Validated existing `canonical_agent_id_for_role(...)` behavior:

- `backend_agent` / `BackendAgent` / `backend` -> `backend-developer`
- `frontend_agent` / `FrontendAgent` / `frontend` -> `frontend-developer`
- `qa_agent` / `QA Agent` / `qa` -> `qa-expert`
- `security_guard_agent` / `security` -> `security-auditor`
- unknown roles map deterministically to an approved safe fallback

The confirmed development bridge preserves the original `agent_role` in context while using canonical `agent_id` values where possible.

## Per-agent instruction runtime alignment

Updated `backend/src/orchestrator/engine.py` with `_runtime_agent_id_for_step(...)`.

Runtime staged execution now:

- resolves stored step aliases to canonical registry IDs.
- uses canonical IDs for per-step model route decisions.
- loads per-agent instructions using the canonical runtime agent ID.
- falls back to the stored step agent ID and then run-level orchestrator instructions if no agent-specific file exists.
- preserves stored step metadata instead of rewriting DB records.

The `agent-executions/run` endpoint was already loading `load_agent_instructions(agent_id)` as its provider system prompt, so no change was required there.

## Bridge step alignment

Validated:

- `build_pending_run_step_inputs_from_development_preview(...)` preserves original `agent_role`.
- bridge-created pending steps use canonical `agent_id` when possible.
- step input context includes original `agent_role`.
- `provider_allowed` remains false.
- no auto-start is introduced.

## Safety boundaries

Verified:

- no automatic `execute_run` call added
- no new `asyncio.create_task` path added
- no new `create_tool_call` added
- no provider calls added
- no DB schema changes
- no migrations
- no provider runtime files touched
- no patch/apply/test execution behavior changed
- no safety gate weakening

## Tests added

Updated `backend/tests/test_model_router_agent_alignment.py` to cover runtime canonicalization:

- stored alias `backend` resolves to `backend-developer`
- empty stored agent with QA/test title infers `qa-expert`

The alignment suite now has 42 tests.

## Files changed

- `backend/src/orchestrator/engine.py`
- `backend/tests/test_model_router_agent_alignment.py`
- `runs/model-router-agent-runtime-alignment-fastlane-v1/final-report.md`

Existing files inspected/validated but not changed by this slice:

- `backend/src/model_router.py`
- `backend/src/agents/registry.py`
- `config.yaml`
- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`

## Protected files

- `database.py` touched: no
- `engine.py` touched: yes, narrowly for runtime agent-id/instruction alignment
- providers touched: no

## Exact check results

Backend:

- `python -m py_compile src/model_router.py src/agents/registry.py src/orchestrator/engine.py src/orchestrator/project_intake.py src/api/routes.py tests/test_model_router_agent_alignment.py`: passed
- `pytest -q tests/test_model_router_agent_alignment.py`: 42 passed
- `pytest -q tests/test_step_model_routing.py`: 53 passed
- `pytest -q tests/test_agent_execution_harness.py`: 46 passed
- `pytest -q tests/test_confirmed_development_run_bridge_fastlane.py`: 52 passed
- `pytest -q tests/test_confirmed_development_run_creation_preview_wiring.py`: 43 passed
- `pytest -q tests/test_intake_confirmed_development_run_preview.py`: 61 passed
- full backend `pytest -q`: 1951 passed + 38 subtests

Frontend:

- `npx tsc --noEmit`: passed
- `npm run build`: passed
- `npm run test:e2e:smoke`: 2 passed

Root:

- `bash scripts/run_tests.sh`: passed
  - backend: 1951 passed + 38 subtests
  - frontend TypeScript check: passed

## P0/P1/P2/P3 issues

- P0: none found
- P1: none found
- P2: none found
- P3: frontend build still emits the existing Vite chunk-size warning over 500 kB; non-blocking and unrelated to this backend alignment slice.

## Known limitations

- no auto execution added
- no provider hardening runtime added
- no full repo-aware intake yet
- no autonomous patch/test/fix loop yet
- engine execution still requires explicit run start
- local model quality depends on installed Ollama models

## Recommended next slice

Intake Run -> Agent Assignment & Step Context Fastlane v1

Alternative: Existing Project Read-only Repo Intake Fastlane v1

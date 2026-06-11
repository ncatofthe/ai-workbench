# Module Map → Agent Context Wiring v1

## Summary
Wired active Project Module Map data into Agent Execution Context as compact, bounded, read-only hints.

When a run step belongs to a project with an active module map, the agent execution context can now carry module hints, and dry-run/provider prompts include a structured `PROJECT MODULE MAP CONTEXT` section. This helps advisory agents see likely module boundaries, paths, key files, responsibilities, requirements, test hints, and risks without reading file contents or executing anything.

## Module Context Shape
`AgentExecutionContext.module_context` uses `AgentModuleContext`:
- `project_id`
- `has_active_module_map`
- `module_map_version`
- `matched_modules`
- `matched_paths`
- `matched_requirement_ids`
- `module_summary`

Each matched module includes:
- `id`, `name`, `slug`, `module_type`
- `description`
- `responsibilities`
- `paths`
- `key_files`
- `related_requirements`
- `test_hints`
- `risks`
- `confidence`

## Selection Logic
The active module map is selected by project id. Matching is deterministic:
- requirement id match via `related_requirements`
- keyword match on step title/input for auth, tasks, finance, uploads/files, reviews, reports, database, frontend, contracts, tests, infra, docs, and related terms
- fallback to high-confidence modules, then first modules, if no explicit match exists

## Bounded Output Rules
- matched modules capped at 5
- paths/key files capped per module
- prompt section renders concise lines, not raw JSON
- no file content reads
- no scan-preview execution
- no provider/tool calls

## Agent Execution Context Endpoint Behavior
`GET /api/runs/{run_id}/steps/{step_id}/agent-execution-context` remains read-only:
- verifies run/step
- builds standard requirement/source-of-truth context
- attaches module context when project id is present
- creates no tool calls
- mutates no run/step state

## Prompt Builder Behavior
Agent prompt previews now include:

```text
PROJECT MODULE MAP CONTEXT
- Module: ...
  Type: ...
  Responsibilities: ...
  Paths: ...
  Key files: ...
  Related requirements: ...
  Test hints: ...
  Risks: ...
```

The section is omitted when no active module map exists. It is explicitly framed as bounded location hints, not permission to edit files.

## Frontend Changes
Updated RunDetail Agent Execution Harness to show a small read-only Module Map Context summary:
- map version
- matched module names/slugs
- key files

No buttons, scans, auto-runs, or mutations were added.

## Tests Added
Added `backend/tests/test_module_map_agent_context_wiring.py` with 30 tests covering:
- no active module map behavior
- active map injection into agent context
- requirement id matching
- auth/frontend/database keyword matching
- fallback/bounds
- no file content leakage
- context endpoint read-only behavior
- dry-run prompt inclusion
- mock/provider safety
- prompt omission when no map exists
- static safety invariants

## Safety Boundaries
Confirmed:
- no `database.py` edits in this slice
- no `engine.py` edits in this slice
- no provider edits in this slice
- no DB schema changes
- no migrations
- no `execute_run`
- no `asyncio.create_task`
- no subprocess/shell/os command calls in the context path
- no provider calls added to context endpoint
- no `create_tool_call` in context endpoint
- no file content reads in module context builder
- no Start Task or confirmed-run behavior changes
- no auto-apply/proposal/rollback

Note: the working tree already contains unrelated dirty entries for protected files from prior work; they were not modified by this slice.

## Files Changed
Changed in this slice:
- `backend/src/models.py`
- `backend/src/api/routes.py`
- `backend/tests/test_module_map_agent_context_wiring.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/module-map-agent-context-wiring-v1/final-report.md`

Used existing current-tree helper:
- `backend/src/storage/module_map_storage.py`

## Exact Check Results
- `py_compile src/storage/database.py`: passed
- `py_compile src/models.py`: passed
- `py_compile src/storage/module_map_storage.py`: passed
- `py_compile src/orchestrator/project_module_map.py`: passed
- `py_compile src/api/routes.py`: passed
- `py_compile tests/test_module_map_agent_context_wiring.py`: passed
- `pytest -q tests/test_module_map_agent_context_wiring.py`: 30 passed
- `pytest -q tests/test_agent_execution_harness.py`: 46 passed
- `pytest -q tests/test_project_module_map.py`: 41 passed
- targeted related backend suite: 422 passed
- full backend pytest: 1068 passed, 38 subtests passed
- frontend `npx tsc --noEmit`: passed
- frontend `npm run build`: passed
- `bash scripts/run_tests.sh`: passed; backend 1068 passed, 38 subtests passed; frontend TypeScript check passed

## P0/P1/P2/P3 Issues
No open P0/P1 issues found.

P2 fixed:
- Agent prompt builder did not yet render the module-map context section. Added bounded text rendering.
- Frontend `AgentExecutionContext` type did not expose `module_context`. Added matching type and small read-only display.
- Source-of-truth summary in agent context was reading a non-existent parser field. Updated it to `source_of_truth_summary`.

## Known Limitations
- Module matching is deterministic and keyword-based, not semantic.
- No file content is inspected, so key file relevance depends on the stored module map.
- Module context is advisory only; it is not yet linked to patch proposal validation.

## Recommended Next Slice
Module Map → Patch Draft Context v1


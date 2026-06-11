# Module Map → Patch Draft Context Regression Pass

## Summary
Regression pass completed for Module Map → Patch Draft Context v1.

No source-code changes were needed. The implementation remains read-only and bounded, and the existing backend/frontend suites remain green.

## Response Model Validation
Confirmed:
- `AgentPatchDraftResponse.module_context` is optional/default-safe.
- `module_context_summary` defaults to `""`.
- `recommended_files_from_module_map` defaults to `[]`.
- `module_risks` defaults to `[]`.
- `module_test_hints` defaults to `[]`.
- frontend TypeScript response shape matches backend response fields.
- existing bridge tests still pass.

## Patch Draft Endpoint Validation
Confirmed:
- no active module map returns safe empty/false module context.
- active module map adds compact module context.
- `patch_context` preserves existing content and appends module context.
- `PROJECT MODULE MAP PATCH CONTEXT` appears only when an active map exists.
- `old_text` / `new_text` remain manual and are not present in the response.
- `guard_required` remains `true`.
- safety notes remain accurate.
- endpoint does not create proposals.
- endpoint does not apply patches.
- endpoint does not run commands.
- endpoint does not mutate run/step state unexpectedly.

## Module Matching Validation
Confirmed deterministic matching by:
- `agent_result.proposed_files` through module paths/key files.
- requirement ids from `RunStep.input`.
- keyword fallback for auth, frontend, database, and related keyword families covered by tests.

Confirmed:
- module matches are deduplicated.
- matched modules are capped.
- paths/key files are capped.
- risks/test hints are capped.
- output is bounded and formatted as text, not raw JSON.
- no file contents appear in response.

## Bounded Output Validation
Confirmed:
- `patch_context` respects `max_context_chars`.
- module section is compact and bounded.
- recommended files, risks, and test hints are capped in response.
- no full module map dump is returned in patch context.

## Frontend Read-Only Validation
Confirmed:
- RunDetail only displays module context.
- no new execution buttons were added.
- no auto-run, scan, save, provider call, proposal, or apply behavior was added.
- existing “Use in patch form” remains manual.
- module context does not fill `old_text` or `new_text`.
- frontend `tsc` and build pass.

## Workflow Compatibility Validation
Confirmed green:
- `test_agent_result_patch_draft_bridge.py`
- `test_module_map_agent_context_wiring.py`
- `test_agent_execution_harness.py`
- `test_project_module_map.py`
- source-of-truth and persistence suites
- RunDetail UX suite
- dogfooding/full delivery suites
- bounded autonomous loop suite
- approval-gated automation suite
- automation runner suite
- semi-auto operator queue suite

## Runtime Boundary Validation
Relevant patch-draft/module-map functions were inspected with static checks.

Confirmed no relevant-section usage of:
- `execute_run`
- `asyncio.create_task`
- `apply_project_patch`
- `propose_project_patch`
- `subprocess`
- `os.system`
- `os.popen`
- provider calls
- `ollama.chat_completion`
- Claude/Codex provider calls
- `create_tool_call`
- file content reads (`open`, `.read_text`, `.read`)
- DB schema mutation (`CREATE TABLE`, `ALTER TABLE`, `DROP TABLE`)

Broad repository scan still shows existing runtime/tool/provider paths elsewhere in `routes.py`; those are pre-existing and outside this regression scope.

## P0/P1/P2/P3 Issues Found
No P0/P1/P2/P3 issues found.

## Changes Made
No source-code changes.

Only this report file was created.

## Exact Checks/Results
- `py_compile src/storage/database.py`: passed
- `py_compile src/models.py`: passed
- `py_compile src/storage/module_map_storage.py`: passed
- `py_compile src/orchestrator/project_module_map.py`: passed
- `py_compile src/api/routes.py`: passed
- `py_compile tests/test_module_map_patch_draft_context.py`: passed
- `pytest -q tests/test_module_map_patch_draft_context.py`: 26 passed
- targeted related backend suite: 452 passed
- full backend pytest: 1094 passed, 38 subtests passed
- frontend `npx tsc --noEmit`: passed
- frontend `npm run build`: passed
- `bash scripts/run_tests.sh`: passed; backend 1094 passed, 38 subtests passed; frontend TypeScript check passed

## Protected Files
- `backend/src/storage/database.py`: not touched in this regression pass.
- `backend/src/orchestrator/engine.py`: not touched in this regression pass.
- providers: not touched in this regression pass.

Note: the working tree already contains unrelated dirty/protected entries from prior work; this pass did not reset, revert, clean, checkout, or delete anything.

## Known Limitations
- matching is heuristic only.
- no file content analysis.
- no provider/LLM classification.
- module map does not auto-drive proposal/apply.
- module map is not yet used by guard/delivery.
- no visual module map editor.

## Recommended Next Slice
Guard/Proposal Module Awareness v1


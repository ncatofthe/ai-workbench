# Module Map → Patch Draft Context v1

## Summary
Wired active Project Module Map data into the Agent Result → Patch Draft bridge as bounded, read-only patch context.

When an agent result is converted into a patch draft, the response now includes compact module-map hints and appends a `PROJECT MODULE MAP PATCH CONTEXT` section to `patch_context` when an active module map exists.

This remains manual context only. It does not create proposals, apply patches, read files, call providers, or bypass guards/approvals.

## Module Patch Context Shape
Added optional fields to `AgentPatchDraftResponse`:
- `module_context`
- `module_context_summary`
- `recommended_files_from_module_map`
- `module_risks`
- `module_test_hints`

The existing `patch_context` string is preserved and now includes a compact textual module-map section when available, so existing UI/prefill behavior continues to work.

## Selection Logic
The patch draft module context is deterministic:
- proposed files match module `paths` / `key_files`
- requirement ids from `RunStep.input` match `related_requirements`
- keyword fallback checks agent summary, analysis, patch intent, step title, and step input
- if no match exists, it falls back to high-confidence modules, then first modules

Keyword families include auth/login/JWT, tasks/workflow, finance/payments, uploads/files, review/approval, reports/analytics, database/schema, frontend/UI, and contracts/types.

## Bounded Output Rules
- matched modules capped at 5
- paths/key files capped at 8 per module
- module risks/test hints capped at 10 in response
- no raw JSON dump in `patch_context`
- no file contents
- no project scan
- no provider/LLM classification

## Patch Draft Endpoint Behavior
`POST /api/runs/{run_id}/steps/{step_id}/agent-result-patch-draft` still:
- verifies run/step
- accepts direct `agent_result` or stored agent execution tool call
- builds patch draft context only
- keeps `old_text` / `new_text` manual and absent from response
- keeps `guard_required=true`
- creates no proposal
- applies no patch
- executes no command
- creates no new tool call

When project/module map context exists, it adds:
- matched modules
- recommended files from module map
- module risks
- module test hints
- bounded `PROJECT MODULE MAP PATCH CONTEXT` text

## Frontend Changes
RunDetail Agent Execution Panel now shows a small read-only module context section in patch draft results:
- matched module names/slugs
- recommended files
- module test hints
- module risks

No new action buttons were added beyond the existing “Use in patch form”.

## Tests Added
Added `backend/tests/test_module_map_patch_draft_context.py` with 26 tests covering:
- no active module map behavior
- proposed file → module matching
- requirement id → module matching
- auth/frontend/database keyword matching
- module/path/key file caps
- patch draft response module context
- key files without file contents
- module risks/test hints
- `PROJECT MODULE MAP PATCH CONTEXT` presence/absence
- manual old_text/new_text behavior
- no proposal/apply/run-command/tool execution
- `guard_required` invariant
- static safety invariants

## Safety Boundaries
Confirmed:
- no `database.py` edits in this slice
- no `engine.py` edits in this slice
- no provider edits in this slice
- no DB schema changes or migrations
- no `execute_run`
- no `asyncio.create_task`
- no subprocess/shell/os command calls
- no provider calls
- no file content reads
- no auto-proposal
- no auto-apply
- no auto-rollback
- no guard/approval bypass
- Start Task and confirmed-run behavior unchanged

Note: the worktree already contains unrelated dirty/protected entries from earlier work; they were not modified by this slice.

## Files Changed
Changed in this slice:
- `backend/src/models.py`
- `backend/src/api/routes.py`
- `backend/src/storage/module_map_storage.py`
- `backend/tests/test_module_map_patch_draft_context.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/RunDetail.tsx`
- `runs/module-map-patch-draft-context-v1/final-report.md`

## Exact Check Results
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

## P0/P1/P2/P3 Issues
No open P0/P1 issues found.

P2 handled:
- Existing patch draft bridge did not include module-map context, so operators still had to infer likely files/modules manually. Added bounded advisory context.
- The bridge used the old `source_of_truth` parser field name; updated to `source_of_truth_summary`.

## Known Limitations
- Matching is heuristic/deterministic only.
- No file content analysis.
- No provider/LLM classification.
- Module map does not auto-drive patch proposals.
- Module map is not yet used by guard/proposal enforcement.
- No visual module map editor.

## Recommended Next Slice
Module Map → Patch Draft Context Regression Pass


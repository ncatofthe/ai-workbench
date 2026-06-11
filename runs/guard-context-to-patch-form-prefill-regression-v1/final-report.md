# Guard Context to Patch Form Prefill Regression Pass v1

## Summary

The Guard Context to Patch Form Prefill flow is stable.

No P0/P1 regressions were found. No source-code changes were made in this regression pass. The prefill remains a manual frontend-only helper that copies checked guard context into the existing patch form context/banner without generating code, creating proposals, applying patches, running commands/tests, or calling providers.

## Prefill visibility validation

| Scenario | Result | Notes |
| --- | --- | --- |
| No guard result | Passed | The "Use guard context in patch form" button is not rendered. |
| `allowed` guard result | Passed | The button is rendered when a latest checked guard context exists. |
| `warning` guard result | Passed | The button is rendered when a latest checked guard context exists. |
| `blocked` guard result | Passed | The button is not rendered; the blocked explanatory copy is shown. |

Blocked copy remains:

```text
Blocked guard result cannot be used to prefill a patch proposal.
```

## Prefill behavior validation

- Prefill uses only the latest successful guard check context.
- Prefill copies `file_path` into the patch form only when that file path was part of the latest checked guard input.
- Prefill writes guard context into the existing issue/context banner:
  - proposed action;
  - guard decision;
  - drift risk;
  - matched requirement ids;
  - warnings;
  - reasons;
  - recommended next step.
- Prefill does not fill `old_text`.
- Prefill does not fill `new_text`.
- Prefill does not change `create_if_missing`.
- Prefill does not change `replace_all`.
- Prefill does not call the propose-patch endpoint.
- Prefill does not call the apply-patch endpoint.
- Prefill does not run tests or commands.
- Prefill does not call providers/tools.

## Stale guard prevention validation

- Captured guard input is stored only after a successful guard endpoint response.
- Changing the guard summary clears:
  - guard result;
  - captured guard context;
  - no-guard override;
  - warning acknowledgement.
- Changing any patch form field clears:
  - guard result;
  - captured guard context;
  - no-guard override;
  - warning acknowledgement.
- External patch prefill and context-draft prefill clear guard state.
- Prefill preserves only the guard result derived from the latest checked guard input.
- Prefill clears no-guard override and warning acknowledgement.
- Old guard result cannot authorize unrelated patch text through the checked code path.

## Gate behavior after prefill

| Guard state | Result | Notes |
| --- | --- | --- |
| `allowed` | Passed | Proposal preview remains available normally. |
| `warning` | Passed | Warning acknowledgement remains required after prefill. |
| `blocked` | Passed | Proposal preview remains blocked and no prefill button is shown. |
| `not_checked` | Passed | Proposal preview still requires explicit no-guard override. |

Prefill does not silently enable proposal bypass.

## Existing patch workflow validation

- Existing `proposeProjectPatch` payload remains unchanged:
  - `run_id`;
  - `step_id`;
  - `agent_id`;
  - `operations: [patchOperationFromForm(form)]`.
- Existing review-patch flow is unchanged.
- Existing apply flow is unchanged and remains manual.
- Existing rollback/test/analyze UI was not modified.
- Safe Prep and guided workflows were not modified.

## Backend safety validation

The source-of-truth guard endpoint remains read-only by inspection:

- no `execute_run`;
- no `asyncio.create_task`;
- no provider/tool execution from the guard endpoint;
- no `create_tool_call`;
- no patch/apply/test execution.

No backend changes were needed.

## Issues found

| Priority | Area | Problem | Suggested fix |
| --- | --- | --- | --- |
| None | - | No P0/P1/P2/P3 issues found in this pass. | - |

## Changes made

No source-code changes.

## Files changed

- `runs/guard-context-to-patch-form-prefill-regression-v1/final-report.md`

## Backend touched

- Backend source touched in this pass: no.
- `backend/src/storage/database.py` touched in this pass: no.
- `backend/src/api/routes.py` touched in this pass: no.

Note: the working tree already contains unrelated/pre-existing backend modifications. They were preserved and not modified.

## Exact checks/results

| Check | Result | Notes |
| --- | --- | --- |
| `cd frontend && npx tsc --noEmit` | Passed | TypeScript check passed. |
| `cd frontend && npm run build` | Passed | Vite production build completed. |
| `cd backend && .venv/bin/python -m py_compile src/storage/database.py` | Passed | `database.py` compiles. |
| `cd backend && .venv/bin/pytest -q` | Passed | `442 passed, 24 subtests passed`. |
| `cd repo && bash scripts/run_tests.sh` | Passed | Root script passed; backend pytest reported `442 passed, 24 subtests passed`. |

## Recommended next slice

Guard Result Persistence/Audit Decision v1.

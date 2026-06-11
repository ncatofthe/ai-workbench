# Confirmed Plan to Run v1

## Summary

Added an explicit user-confirmed flow that creates a real Run and pending RunSteps from the intake pipeline preview. The operator must explicitly confirm before anything is persisted. Created runs are pending — no agents, tools, providers, or patches are executed. This completes the read-only intake pipeline by giving it a concrete output: a real run visible in RunDetail.

## Backend behavior

New endpoint `POST /api/project-intake/confirmed-run`:

1. Validates `confirm: true` is present (400 if false/missing).
2. Validates `idea` is non-empty (400 if blank).
3. Calls `build_confirmed_plan_run_preview()` internally (pure, no side effects).
4. Creates a real `Run` via existing `create_run()` helper — status `pending`.
5. Creates one `RunStep` per preview step via existing `create_run_step()` — all status `pending`.
6. Returns `ConfirmedRunFromPlanResponse` with run ID, step count, and step details.
7. Even if `ready_to_create_run` is false in the preview, the run is created with a warning — explicit confirmation overrides readiness.

No new DB tables, no migrations, no database.py changes.

## Frontend behavior

After the "Preview run steps" result panel, a new confirmation section appears:

- Safety disclaimer text about pending-only creation.
- Checkbox: "I confirm this source of truth, coverage, and run-step plan."
- Button: "Create run from confirmed plan" (enabled only when checkbox is checked).
- On success: navigates to the created RunDetail page.
- On error: shows error message inline.
- Success banner shows run ID, step count, and status.

This is a **separate path** from the existing "Start Task" button — does not alter the existing Start Task flow.

## Confirmation gate

- `confirm: true` is required in the request body.
- `confirm: false` or missing → HTTP 400.
- Frontend requires checkbox interaction before the button becomes enabled.
- No way to accidentally create a run — requires both checkbox and button click.

## Run/step mapping

Each `ConfirmedRunStepPreview` becomes a `RunStep` with:

| Preview field | RunStep field | Mapping |
|--------------|---------------|---------|
| title | title | Direct |
| description | input | Base text |
| suggested_agent_id | agent_id | Direct (empty if none) |
| required_requirement_ids | input | `[Linked requirements: ...]` |
| expected_deliverables | input | `[Expected deliverables: ...]` |
| depends_on | input | `[Depends on: ...]` |
| validation_notes | input | `[Validation: ...]` |
| manual_approval_required | input | `[Manual approval required...]` |
| safe_to_prepare | input | `[Safe to prepare...]` |
| — | status | Always `pending` |

Requirement links, deliverables, and dependencies are embedded as structured text in the step input since the RunStep schema doesn't have dedicated fields for these. No database.py changes needed.

## Safety guarantees

| Boundary | Status |
|----------|--------|
| No automatic execution | ✓ — no execute_run, no asyncio.create_task |
| No tools execution | ✓ — no tool calls created |
| No provider/LLM calls | ✓ — endpoint uses only pure functions + DB create |
| No patch/apply/tests/rollback | ✓ — no execution code |
| No assigned team auto-execution | ✓ — no replace_run_agent_assignments |
| No shell runner | ✓ — no subprocess calls |
| No autonomous mode | ✓ — explicit confirm required |
| Existing Start Task unchanged | ✓ — separate path, no changes to createRun |
| database.py untouched | ✓ — uses existing create_run/create_run_step |
| engine.py untouched | ✓ |
| Run status = pending | ✓ — verified in tests |
| All steps status = pending | ✓ — verified in tests |
| No tool_calls created | ✓ — verified in tests |

## Source changes

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | Added 3 models: ConfirmedRunFromPlanRequest, ConfirmedRunCreatedStep, ConfirmedRunFromPlanResponse |
| `backend/src/api/routes.py` | Added imports + `POST /api/project-intake/confirmed-run` endpoint |
| `backend/tests/test_confirmed_run.py` | New — 10 test methods using TestClient + isolated_db |
| `frontend/src/types/index.ts` | Added ConfirmedRunFromPlanRequest, ConfirmedRunCreatedStep, ConfirmedRunFromPlanResponse interfaces |
| `frontend/src/api/client.ts` | Added `createRunFromConfirmedPlan()` client method |
| `frontend/src/pages/NewTask.tsx` | Added confirmation state, handler, checkbox, button, success/error UI |

## Tests

| Check | Result |
|-------|--------|
| `py_compile project_intake.py` | OK |
| `py_compile routes.py` | OK |
| `py_compile database.py` | OK (untouched) |
| `py_compile test_confirmed_run.py` | OK |
| `py_compile test_project_intake.py` | OK |
| Python syntax (17 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

New test class `TestConfirmedRunEndpoint` (10 tests):

- `test_confirm_false_returns_400` — confirm=false → 400
- `test_confirm_missing_returns_400` — no confirm field → 400
- `test_empty_idea_returns_400` — blank idea → 400
- `test_valid_request_creates_run` — creates run in DB, status=pending
- `test_valid_request_creates_run_steps` — creates steps in DB, all pending
- `test_created_run_is_not_executed` — run and steps remain pending
- `test_no_tool_calls_created` — zero tool_calls in DB
- `test_response_serializes_correctly` — all expected fields present
- `test_existing_project_mode_creates_steps` — existing project mode works
- `test_vague_idea_still_creates_run_with_warnings` — vague idea creates run with warnings
- `test_steps_have_input_with_metadata` — step input contains requirement/deliverable metadata

## Remaining gaps

- No structured requirement→step links in DB schema — metadata is embedded in step input text.
- No agent assignments created for the run (run_agent_assignments table not populated).
- No run_dir artifact persistence (plan/SoT/coverage not saved as run artifacts).
- Existing Start Task and confirmed-run are independent paths — no unified UX yet.
- No undo/delete for runs created from plan.

## Recommended next slice

**Run Step Requirement Links v1** — add structured requirement→step linking that persists in run artifacts or a lightweight DB table, enabling the cockpit to display which requirements each step satisfies.

Or **Run Creation From Plan Regression Pass v1** — verify the new endpoint doesn't interfere with existing run creation, audit DB state consistency.

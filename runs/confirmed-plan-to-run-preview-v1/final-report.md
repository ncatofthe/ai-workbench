# Confirmed Plan to Run Preview v1

## Summary

Added a read-only preview that maps the full intake pipeline (analyze → brief → plan → source of truth → coverage) into future run step previews. The operator can see exactly what steps a real run would contain, which requirements they link to, which agents would be suggested, and whether the system considers the plan ready to become an actual run — all without creating anything persistent.

## Backend behavior

Pure function `build_confirmed_plan_run_preview()` in `project_intake.py`:

1. Accepts `ConfirmedPlanRunPreviewRequest` (idea + optional mode/stack/constraints/goal).
2. Internally calls the full deterministic pipeline:
   - `draft_development_plan()` → plan phases
   - `build_source_of_truth_from_intake()` → SoT + validation
   - `build_requirement_coverage_from_plan()` → coverage matrix
3. Maps each plan phase to a `ConfirmedRunStepPreview` with:
   - `id` (rs-{phase_id} prefix)
   - `suggested_agent_id` (keyword-based heuristic)
   - `required_requirement_ids` (linked from coverage)
   - `coverage_status` (aggregated from linked requirements)
   - `drift_risk` (worst-case from linked requirements)
   - `depends_on` (phase dependencies with rs- prefix)
   - `expected_deliverables` (from plan phase)
   - `validation_notes` (human-readable assessment)
   - `manual_approval_required` (deploy/release/migrate patterns)
   - `safe_to_prepare` (design/architecture/research patterns)
4. Evaluates readiness via `ready_to_create_run` flag.

## Frontend behavior

- New button "Preview run steps" in NewTask.tsx intake toolbar.
- Calls `POST /api/project-intake/run-preview`.
- Displays `RunStepPreviewPanel` showing:
  - Ready/not-ready badge
  - Summary with step count
  - SoT and coverage readiness indicators
  - Blocking issues (red) and warnings (yellow)
  - Each step as a card with: coverage status, drift risk, agent, requirements, dependencies, deliverables, validation notes, approval/safe-prep badges
  - Safety disclaimer: "Run step preview is read-only..."
- Does not save, create runs, or change Start Task payload.

## Readiness rules

`ready_to_create_run = false` if any of:
- Source of truth has validation gaps (completeness < 50% or critical drift risk)
- Coverage has missing mandatory requirements
- Coverage has high/critical drift risk
- Required plan phases have high/critical drift risk (generates blocking issue)

`ready_to_create_run = true` only when:
- Source of truth passes validation threshold
- No missing mandatory requirements in coverage
- No high/critical drift risk in coverage
- No blocking issues accumulated

Even when `ready_to_create_run = true`, the endpoint does NOT create a run.

## Safety guarantees

| Boundary | Status |
|----------|--------|
| No DB reads | ✓ — no database imports in project_intake.py |
| No DB writes | ✓ — no database.py edits |
| No migrations | ✓ — no schema changes |
| No real run creation | ✓ — returns preview model only |
| No project creation | ✓ — no create_project calls |
| No run_steps persistence | ✓ — ConfirmedRunStepPreview is a Pydantic model, not persisted |
| No assigned team creation | ✓ — suggested_agent_id is a hint, not an assignment |
| No tool_calls | ✓ — no create_tool_call calls |
| No tools execution | ✓ — pure computation |
| No providers/LLM calls | ✓ — no provider imports |
| No file scanning | ✓ — no project_tools imports |
| No patch/apply/tests/rollback | ✓ — no execution code |
| No autonomous mode | ✓ — preview only |
| Start Task payload unchanged | ✓ — no modifications to createRun |
| No git commit | ✓ |
| database.py untouched | ✓ |
| engine.py untouched | ✓ |

## Source changes

| File | Change |
|------|--------|
| `backend/src/orchestrator/project_intake.py` | Added 3 models (ConfirmedRunStepPreview, ConfirmedPlanRunPreviewRequest, ConfirmedPlanRunPreviewResponse), agent hint keywords, approval/safe-prep pattern matchers, `build_confirmed_plan_run_preview()` function |
| `backend/src/api/routes.py` | Added import of new types + `POST /api/project-intake/run-preview` endpoint |
| `backend/tests/test_project_intake.py` | Added `TestBuildConfirmedPlanRunPreview` class with 11 test methods |
| `frontend/src/types/index.ts` | Added ConfirmedRunStepPreview, ConfirmedPlanRunPreviewRequest, ConfirmedPlanRunPreviewResponse interfaces |
| `frontend/src/api/client.ts` | Added `previewConfirmedPlanRun()` client method |
| `frontend/src/pages/NewTask.tsx` | Added state, handler, "Preview run steps" button, RunStepPreviewPanel + RunStepPreviewCard components |

## Tests

| Check | Result |
|-------|--------|
| `py_compile project_intake.py` | OK |
| `py_compile routes.py` | OK |
| `py_compile database.py` | OK |
| `py_compile test_project_intake.py` | OK |
| Python syntax (17 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

New test methods in `TestBuildConfirmedPlanRunPreview`:

- `test_returns_structured_response` — verifies response shape, step count > 0, rs- prefix
- `test_vague_idea_not_ready` — vague idea → ready_to_create_run=false
- `test_missing_mandatory_requirements_block_readiness` — vague → not ready
- `test_steps_linked_to_requirement_ids` — detailed idea → some steps have linked reqs
- `test_existing_project_mode_steps` — existing project → not ready, has context/audit steps
- `test_step_dependencies_use_rs_prefix` — all depends_on entries start with rs-
- `test_serializes_through_pydantic` — model_dump() has all expected fields
- `test_no_db_tool_provider_execution` — source code has no forbidden imports
- `test_safe_to_prepare_and_manual_approval_flags` — at least one safe-to-prepare step
- `test_summary_includes_step_count` — summary contains "run steps"

## Remaining gaps

- Agent suggestion is keyword-based heuristic, not the real agent selector.
- Run step preview does not yet flow into actual run creation (next slice).
- No persistence of the preview — it's recomputed each time.
- Step ordering within the preview follows plan phase order, not a topological sort.
- No frontend caching of preview results across button presses.

## Recommended next slice

**Confirmed Plan to Run v1** — wire the preview into actual run creation. When operator clicks "Create run from preview", persist run + run_steps from the confirmed preview. Or **Run Step Requirement Links v1** — add explicit requirement→step linking that persists in run artifacts.

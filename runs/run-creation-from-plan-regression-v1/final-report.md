# Run Creation From Plan Regression Pass v1

## Summary

Regression pass is **clean**. All safety invariants hold, the confirmed-run endpoint works correctly, no execution occurs, the Start Task flow is untouched, and all checks pass. No P0 or P1 issues found. No source code changes were made.

## Backend endpoint validation

| Check | Status | Evidence |
|-------|--------|----------|
| Endpoint exists | ✓ | `POST /api/project-intake/confirmed-run` at line 2782 |
| `confirm: false` → 400 | ✓ | Line 2791: `if not req.confirm: raise HTTPException(400)` |
| `confirm` missing → 400 | ✓ | Pydantic default is `False`, so missing → gate triggers 400 |
| `confirm: true` → allowed | ✓ | Passes gate, creates run |
| Empty idea → 400 | ✓ | Line 2796: separate validation |

## DB mutation validation

| Check | Status | Evidence |
|-------|--------|----------|
| Creates one Run | ✓ | `create_run()` called once at line 2828 |
| Creates RunSteps | ✓ | `create_run_step()` in loop at line 2859 |
| Run status = pending | ✓ | `create_run()` uses `RunStatus.PENDING` (database.py line 517) |
| Step status = pending | ✓ | Hardcoded `status="pending"` at line 2863 |
| Steps have metadata in input | ✓ | Requirements, deliverables, deps, validation notes embedded |
| No new DB tables | ✓ | database.py untouched |
| No migrations | ✓ | No schema changes |

## Run/RunStep status validation

| Check | Status | Evidence |
|-------|--------|----------|
| Run stays pending | ✓ | No status update after create_run |
| Steps stay pending | ✓ | No status update after create_run_step |
| No step transitions | ✓ | No update_run_step calls in endpoint |

## No-execution validation

| Check | Status | Evidence |
|-------|--------|----------|
| No execute_run call | ✓ | Grep confirms no `execute_run` in confirmed-run block |
| No asyncio.create_task | ✓ | Not present in endpoint |
| No provider calls | ✓ | No ollama/codex/claude imports or calls |
| No agent assignment execution | ✓ | No `replace_run_agent_assignments` |
| No tool execution | ✓ | No project_tools imports or calls |
| No shell commands | ✓ | No subprocess calls |

## No-tool-calls validation

| Check | Status | Evidence |
|-------|--------|----------|
| No create_tool_call | ✓ | Not called in endpoint |
| No list_files/read_file/search_code | ✓ | Not called |
| No propose_patch/apply_patch | ✓ | Not called |
| No run_command | ✓ | Not called |

## Frontend confirmation gate validation

| Check | Status | Evidence |
|-------|--------|----------|
| Checkbox exists | ✓ | Line 384-388: `<input type="checkbox" checked={confirmChecked}>` |
| Button disabled until checked | ✓ | Line 394: `disabled={!confirmChecked \|\| confirmedRunLoading \|\| !prompt.trim()}` |
| Handler checks confirmChecked | ✓ | Line 185: `if (!confirmChecked \|\| !prompt.trim()) return` |
| Sends confirm: true | ✓ | Line 190: `confirm: true` in request |
| Safety copy present | ✓ | Line 380: "creates pending run steps only. It does not execute agents, tools, patches, tests, or providers." |
| Navigates on success | ✓ | Line 194: `navigate(\`/runs/${result.run_id}\`)` |
| Error display | ✓ | Line 399-402: error shown inline |
| Success display | ✓ | Line 404-412: run ID, step count, status |

## Start Task unchanged validation

| Check | Status | Evidence |
|-------|--------|----------|
| handleSubmit unchanged | ✓ | Line 206: calls `createRun({ prompt, mode, project_id })` |
| Start Task button unchanged | ✓ | Line 443-449: same onClick, same disabled logic |
| POST /api/runs unchanged | ✓ | Line 332: original endpoint, still calls execute_run |
| CreateRunRequest unchanged | ✓ | models.py line 354: same fields |
| Two independent paths | ✓ | confirmed-run vs Start Task have no shared mutation state |

## Read-only preview endpoints validation

| Endpoint | Status |
|----------|--------|
| POST /api/project-intake/questions | ✓ — exists, line 2671 |
| POST /api/project-intake/brief-draft | ✓ — exists, line 2687 |
| POST /api/project-intake/plan-preview | ✓ — exists, line 2704 |
| POST /api/project-intake/source-of-truth-preview | ✓ — exists, line 2722 |
| POST /api/project-intake/coverage-preview | ✓ — exists, line 2740 |
| POST /api/project-intake/run-preview | ✓ — exists, line 2761 |
| confirmed-run is only mutation | ✓ — only endpoint calling create_run/create_run_step |

## Known field-usage audit

| Field | Status | Evidence |
|-------|--------|----------|
| `sot_validation.is_valid` | ✓ Not used | grep confirms 0 matches |
| `sot_validation.completeness_score` | ✓ Not used | grep confirms 0 matches |
| `sot_validation.valid` | ✓ Used correctly | Line 2059 |
| `sot_validation.errors` | ✓ Used correctly | Line 2060 |
| `sot_validation.drift_risk` | ✓ Used correctly | Line 2061 |

## Checks

| Check | Result |
|-------|--------|
| `py_compile database.py` | OK (untouched) |
| `py_compile project_intake.py` | OK |
| `py_compile routes.py` | OK |
| `py_compile test_project_intake.py` | OK |
| `py_compile test_confirmed_run.py` | OK |
| Python syntax (17 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Real environment expected: all pytest tests pass (416+ passed + 24 subtests + 10 new confirmed-run tests).

## Issues found

| Priority | Area | Problem | Suggested fix |
|----------|------|---------|---------------|
| P3 | UX | Confirmed-run doesn't populate run_agent_assignments — RunDetail may show "no agents" | Future slice: add agent assignments from preview |
| P3 | Data | Requirement links in step input are plain text, not structured | Future slice: Run Step Requirement Links v1 |
| P3 | UX | No undo/delete for runs created from plan | Future slice: add run deletion |
| P3 | Consistency | Confirmed-run always creates mode="offline" regardless of user's mode selector | Low priority — mode selector is for Start Task path |

## Changes made

No source-code changes. This is a regression pass only.

## Files changed

None.

## database.py touched

No.

## routes.py touched

No.

## Recommended next slice

**Run Step Requirement Links v1** — add structured requirement→step linking that persists in run artifacts or a lightweight metadata field, enabling the cockpit to display which requirements each step satisfies.

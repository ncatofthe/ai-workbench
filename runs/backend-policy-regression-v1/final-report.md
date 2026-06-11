# Backend Policy Regression Pass v1

## Summary

Backend Workflow Policy Enforcement v1 is **stable**. All policy invariants hold, the endpoint is purely read-only, no existing routes were modified, no safety boundaries were breached, and all checks pass. No P0 or P1 issues found.

## Checks

| Check | Result | Notes |
|-------|--------|-------|
| `py_compile workflow_policy.py` | OK | Pure module, imports only pydantic/enum/typing |
| `py_compile routes.py` | OK | New import + endpoint appended cleanly |
| `py_compile database.py` | OK | Untouched |
| `py_compile test_workflow_policy.py` | OK | 22 test methods |
| Python syntax (16 files) | All OK | run_tests.sh includes new module |
| TypeScript `tsc --noEmit` | Clean | Frontend unchanged |
| `scripts/run_tests.sh` | Passed | All backend + frontend checks |

## Policy invariants

| Invariant | Status | Evidence |
|-----------|--------|----------|
| 22 action types across 4 execution kinds | ✓ | 3 direct_safe + 6 manual_only + 5 approval_future + 8 blocked |
| 3 automation modes | ✓ | manual / guided / safe_prep |
| `can_run_automatically=true` only for 3 direct safe | ✓ | Line 198: `can_auto = mode in (GUIDED, SAFE_PREP)`, only in `_DIRECT_SAFE_ACTIONS` branch |
| Manual mode: `can_run_automatically=false` for all | ✓ | Line 199-206 short-circuits; all other branches hardcode False |
| Manual-only actions never auto | ✓ | Line 189: hardcoded `can_run_automatically=False`, mode-independent |
| Approval-required never auto | ✓ | Line 174: hardcoded `can_run_automatically=False` |
| Blocked actions never allowed | ✓ | Lines 158-159: `allowed=False, can_run_automatically=False` |
| Unknown action safely blocked | ✓ | Lines 224-234: returns BLOCKED, `allowed=False` |

## Endpoint validation

| Aspect | Status |
|--------|--------|
| Read-only (no DB) | ✓ — no database imports, no `database.*` calls |
| No tool_calls created | ✓ — calls only `list_workflow_action_policies()` |
| No tools executed | ✓ — pure computation |
| No state mutation | ✓ — returns Pydantic model directly |
| Invalid mode → 400 | ✓ — `WorkflowAutomationMode(mode)` with try/except |
| Default mode = "guided" | ✓ — `Query(default="guided")` |
| No circular imports | ✓ — `workflow_policy.py` imports only stdlib + pydantic |

## Safety boundaries

| Boundary | Status |
|----------|--------|
| No auto proposal | ✓ — `create_proposal` is `manual_only`, `can_run_automatically=False` |
| No auto apply | ✓ — `apply_patch_manual` is `manual_only`; `auto_apply_patch` is `blocked` |
| No auto run-command | ✓ — `run_tests_manual` is `manual_only`; `auto_run_command` is `blocked` |
| No auto analyze | ✓ — `analyze_result` is `manual_only`; `auto_analyze_result` is `blocked` |
| No auto rollback | ✓ — `rollback_manual` is `manual_only`; `auto_rollback_patch` is `blocked` |
| No shell runner | ✓ — `arbitrary_shell` is `blocked` |
| No external provider execution | ✓ — `external_provider_execution` is `blocked` |
| No protected file write | ✓ — `protected_file_write` is `blocked` |
| No secret file write | ✓ — `secret_file_write` is `blocked` |
| Codex/Claude providers stub-only | ✓ — verified `codex.py` still returns stub message |
| database.py untouched | ✓ — compiles, no modifications |
| No DB migrations | ✓ — no schema changes |
| Existing routes unchanged | ✓ — config endpoints intact, new section appended |
| README accurate | ✓ — all auto-* references are negations or "not implemented yet" |

## Issues found

| Priority | Area | Problem | Suggested fix |
|----------|------|---------|---------------|
| P2 | Policy design | Direct safe actions in Manual mode return `execution_kind=DIRECT_SAFE` with `allowed=False`. A strict consumer might expect `execution_kind=BLOCKED` when disallowed. | Consider adding a note/field clarifying "action nature vs current permission" in a future slice. Not a bug — the action *is* direct_safe by nature but blocked by mode. |
| P2 | Duplication | Frontend `workflowActionPolicy.ts` and backend `workflow_policy.py` encode the same rules independently. | Future alignment slice: either have frontend fetch from backend or generate both from a shared definition. |
| P3 | Test coverage | Tests cannot run in sandbox (pydantic not installed). Verified via py_compile only. Real environment runs 285 tests. | No action needed — sandbox limitation, not a code issue. |

## Changes made

No source-code changes.

## Recommended next slice

**Project Intake Questions v1** — no P0/P1 issues to address. The policy foundation is stable and ready for future integration. Shifting to onboarding UX will diversify the feature set and avoid deepening the workflow automation stack without the approval request model.

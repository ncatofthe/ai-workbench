# Backend Workflow Policy Enforcement v1

## Summary

Added a pure backend policy module that classifies workflow actions by automation mode, returning structured policy decisions. Includes a read-only API endpoint and comprehensive tests. No execution behavior changed — this is a policy foundation for future semi-auto/approval slices.

## Policy rules

| Action | Manual | Guided | Safe Prep | Auto allowed | Execution kind |
|---|---|---|---|---|---|
| auto_gather_context | blocked | direct, low | direct, low | Guided+SafePrep | direct_safe |
| build_context_bundle | blocked | direct, low | direct, low | Guided+SafePrep | direct_safe |
| create_patch_draft | blocked | direct, medium | direct, medium | Guided+SafePrep | direct_safe |
| review_patch | manual, low | manual, low | manual, low | never | manual_only |
| create_proposal | manual, medium | manual, medium | manual, medium | never | manual_only |
| apply_patch_manual | manual, high, confirm | manual, high, confirm | manual, high, confirm | never | manual_only |
| run_tests_manual | manual, medium, confirm | manual, medium, confirm | manual, medium, confirm | never | manual_only |
| analyze_result | manual, low | manual, low | manual, low | never | manual_only |
| rollback_manual | manual, high, confirm | manual, high, confirm | manual, high, confirm | never | manual_only |
| approval_* (5 actions) | not allowed | not allowed | not allowed | never (v1) | approval_required_future |
| blocked (8 actions) | blocked, critical | blocked, critical | blocked, critical | never | blocked |

## Safety guarantees

- No auto proposal — `create_proposal` is `manual_only`, `can_run_automatically=false`.
- No auto apply — `apply_patch_manual` is `manual_only`, `can_run_automatically=false`.
- No auto tests — `run_tests_manual` is `manual_only`, `can_run_automatically=false`.
- No auto analyze — `analyze_result` is `manual_only`, `can_run_automatically=false`.
- No auto rollback — `rollback_manual` is `manual_only`, `can_run_automatically=false`.
- No shell runner — `arbitrary_shell` is `blocked`.
- No external provider execution — `external_provider_execution` is `blocked`.
- No database.py edits — file untouched.
- No DB migrations — no schema changes.
- No tool_calls created — policy is pure computation.

## Source changes

| File | Change |
|------|--------|
| `backend/src/orchestrator/workflow_policy.py` | New — pure policy module (enums, models, engine, guard) |
| `backend/tests/test_workflow_policy.py` | New — 22 test methods covering all modes, action types, invariants |
| `backend/src/api/routes.py` | Added import + `GET /api/workflow-policy` read-only endpoint |
| `scripts/run_tests.sh` | Added `py_compile` for `workflow_policy.py` |
| `README.md` | Added section + API table entry |

## Tests

| Check | Result |
|-------|--------|
| `py_compile workflow_policy.py` | OK |
| `py_compile routes.py` | OK |
| `py_compile database.py` | OK |
| `py_compile test_workflow_policy.py` | OK |
| Python syntax (16 files) | All OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |

Test classes in `test_workflow_policy.py`:

- `TestManualModeBlocksAutomatic` — all actions not automatic in manual
- `TestGuidedModeAutoOnlyDirectSafe` — only 3 direct safe auto in guided
- `TestSafePrepModeAutoOnlyDirectSafe` — only 3 direct safe auto in safe_prep
- `TestDangerousActionsNeverAutomatic` — apply/tests/rollback never auto, always confirm
- `TestBlockedActionsNeverAllowed` — 8 blocked actions never allowed in any mode
- `TestApprovalFutureNotAutomatic` — 5 future actions not auto, not allowed yet
- `TestUnknownActionBlocked` — unknown types safely blocked
- `TestListPoliciesComplete` — count matches enum, all types present
- `TestCanRunAutomaticallyOnlyThree` — exactly 3 auto in guided/safe_prep, 0 in manual
- `TestAssertGuard` — allowed returns policy, blocked raises, manual blocks direct safe
- `TestRiskLevels` — apply=high, rollback=high, gather=low, draft=medium, shell=critical
- `TestPolicyModel` — serialization + JSON round trip

## Remaining gaps

- Frontend/backend policy duplication still needs future alignment strategy (frontend `workflowActionPolicy.ts` vs backend `workflow_policy.py`).
- Approval request model not implemented — `approval_required_future` actions are classified but cannot execute.
- Backend orchestrator does not yet execute semi-auto workflow via policy checks.
- Real Codex/Claude providers still stub-only.
- Full autonomous mode not implemented.

## Recommended next slice

**Approval Request Model v1** — add a lightweight approval request/response data model (no new DB table yet, in-memory or run-artifact based) so the cockpit can show "pending approval" state for future semi-auto actions. Alternatively, **Project Intake Questions v1** if shifting focus to onboarding UX.

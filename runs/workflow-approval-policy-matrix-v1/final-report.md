# Workflow Approval Policy Matrix v1 — Final Report

**Date:** 2026-05-20
**Scope:** Frontend-only safety/product layer
**Backend changes:** None
**New endpoints:** None

## Files changed

| File | Change |
|------|--------|
| `frontend/src/pages/RunDetail.tsx` | Added `WorkflowActionPolicyDecision` type, `getWorkflowActionPolicy()` function, `policyLabelClass()` helper; wired policy into `WorkflowActionLauncher` (replaced scattered messages with unified policy row); updated Safe Prep messages to policy-aligned text; added collapsible policy explanation panel in cockpit |
| `README.md` | Added "Workflow Approval Policy Matrix v1" section with full policy table |

## Policy matrix behavior

`getWorkflowActionPolicy(actionType, mode)` returns:

```typescript
{
  allowed: boolean;
  execution: "direct" | "draft_only" | "manual_only" | "blocked";
  riskLevel: "low" | "medium" | "high";
  requiresConfirmation: boolean;
  label: string;   // e.g. "Allowed now · read-only direct"
  reason: string;  // e.g. "Read-only action. No files modified."
}
```

## Action policy examples

| Action + Mode | label | execution | risk |
|---|---|---|---|
| auto_gather_context + Guided | Allowed now · read-only direct | direct | low |
| create_patch_draft + Guided | Allowed now · draft only | draft_only | medium |
| auto_gather_context + Manual | Blocked by Manual mode | blocked | low |
| apply_patch_manual + any | Confirm required · manual only | manual_only | high |
| run_tests_manual + any | Confirm required · manual only | manual_only | medium |
| rollback_patch + any | Confirm required · manual only | manual_only | high |

## Mode behavior

| Mode | Safe single actions | Run Safe Prep | Manual actions |
|------|-------------------|---------------|----------------|
| Manual | blocked | blocked | focus UI only |
| Guided | direct/draft | disabled (hint) | focus UI only |
| Safe Prep | direct/draft | enabled | focus UI only |

## Safety boundary preserved

- Proposal never created automatically in any mode.
- Patch never applied automatically in any mode.
- Tests/commands never run automatically in any mode.
- Analyze never triggered automatically in any mode.
- Rollback never triggered automatically in any mode.
- High-risk manual actions always require confirmation.
- No shell execution, no external providers.
- `database.py` untouched, no backend changes.

## Checks passed

| Check | Result |
|-------|--------|
| Python syntax (15 files) | All OK |
| `database.py` compile | OK |
| TypeScript `tsc --noEmit` | Clean (0 errors) |
| `scripts/run_tests.sh` | All checks pass |
| `npm run build` | Skipped (sandbox rollup binary mismatch — works in real env) |

## Remaining risks

- Policy is frontend-only — backend does not enforce mode restrictions (by design in v1).
- Policy function is pure and stateless; if backend action types change, the function needs updating.
- No unit tests for the policy function (could add in a future slice).

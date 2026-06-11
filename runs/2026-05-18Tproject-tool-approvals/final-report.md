# Project Tool Approvals Report

Date: 2026-05-18
Scope: persist approval-required project tool actions

## Summary

Project-scoped test/build actions now create persistent `ApprovalRequest` rows when they require approval.

Previously, blocked, dangerous, or unlisted commands returned only an inline `approval_required` response in Tools. Now those responses also include an `approval_id`, and the pending approval appears through the existing Approvals API/UI.

## Changed Files

- `backend/src/api/routes.py`
- `backend/tests/test_project_profiles.py`
- `frontend/src/types/index.ts`
- `frontend/src/pages/Tools.tsx`

## Behavior

When a project tool command is:

- blocked by `blocked_commands`;
- matched by global dangerous command patterns;
- missing from `safe_commands`;

the backend now:

1. Does not execute the command.
2. Creates an approval row with:
   - `run_id = project:<project_id>`
   - action matching the policy reason
   - original command
   - project name, id, path, command type, and reason in the description
3. Returns `approval_required: true`.
4. Returns `approval_id`.

The Tools page displays the returned approval id when present.

## Tests

Updated `test_unlisted_non_dangerous_command_requires_approval_and_does_not_execute` to verify:

- command did not execute;
- response includes `approval_id`;
- one pending approval was created;
- approval id, run id, action, command, and description match the tool action.

## Verification

Commands:

```bash
python3 -m py_compile backend/src/api/routes.py backend/tests/test_project_profiles.py
cd backend && .venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py
cd frontend && npx tsc --noEmit
bash scripts/run_tests.sh
cd frontend && npm run build
```

Results:

- Backend compile: passed.
- Backend tests: 11 passed.
- Direct frontend TypeScript check: passed.
- Full test script: passed.
- Frontend production build: passed.

## Limitations

- Approving a project tool request does not yet automatically resume or execute the command.
- Approval rows do not yet have first-class `project_id`, `risk_level`, or `requested_by` columns.
- Duplicate approval requests can still be created by repeated button clicks.

## Next Useful Slice

Add a safe execution flow after approval:

- approve a project tool request;
- re-run the exact approved command only if it still matches the original command/project;
- record output in `runs/`;
- prevent duplicate pending approvals for the same project command.

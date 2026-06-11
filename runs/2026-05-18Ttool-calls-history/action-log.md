# Action Log

Task: Persist project tool execution history in normalized `tool_calls`.

## Files modified

- backend/src/models.py
- backend/src/storage/database.py
- backend/src/api/routes.py
- backend/tests/test_project_profiles.py
- frontend/src/types/index.ts
- frontend/src/api/client.ts
- frontend/src/pages/Tools.tsx

## Commands run

- `sed -n '1,260p' backend/src/storage/database.py`
- `sed -n '170,380p' backend/src/api/routes.py`
- `sed -n '1,380p' frontend/src/pages/Tools.tsx`
- `sed -n '1,180p' frontend/src/types/index.ts`
- `sed -n '260,520p' backend/src/storage/database.py`
- `sed -n '380,530p' backend/src/api/routes.py`
- `sed -n '1,280p' backend/tests/test_project_profiles.py`
- `sed -n '1,140p' frontend/src/api/client.ts`
- `python3 -m py_compile backend/src/models.py backend/src/storage/database.py backend/src/api/routes.py backend/tests/test_project_profiles.py`
- `.venv/bin/python -m pytest -q tests/test_project_profiles.py tests/test_path_anchoring.py`
- `npx tsc --noEmit`
- `bash scripts/run_tests.sh`
- `npm run build`
- `git diff --check`

## Safety notes

- No package installs were run.
- No destructive commands were run.
- No git push, rebase, or sudo commands were run.
- The new history records only completed project command executions; pending approvals remain in the approvals table.

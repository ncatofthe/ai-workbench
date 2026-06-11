# Existing Project Read-only Repo Intake Fastlane v1

## Summary

Implemented a bounded, read-only repository intake preview for existing projects.

The new preview can inspect a selected project path and return:
- detected stack
- detected project type
- frontend/backend/database/test/deployment/config areas by path only
- small allowlisted manifest summaries
- protected/sensitive path warnings
- Source of Truth hints
- Module Map hints
- test discovery hints
- clarifying questions
- recommended first safe action

No project, run, run step, tool_call, patch proposal, apply, provider call, network call, command execution, or test execution is created by this feature.

## Scanner Behavior

Added `build_existing_project_repo_intake_preview(...)` in `backend/src/orchestrator/project_intake.py`.

The scanner:
- walks directory metadata under the selected project path
- stays within the selected path
- skips symlinks
- ignores generated/vendor folders such as `.git`, `node_modules`, `vendor`, `dist`, `build`, `.venv`, `__pycache__`, `coverage`, `.next`, `.nuxt`, and `target`
- caps traversal by `max_files` and `max_depth`
- returns only path hints for regular source files
- never reads arbitrary source file contents

## Detected Stack Behavior

Stack detection is deterministic and based on manifest/path hints:
- `package.json` -> node, react, vite, typescript, nextjs, node-backend where applicable
- `pyproject.toml` / `requirements.txt` -> python, fastapi, pytest, django where applicable
- `composer.json` -> php, composer, laravel where applicable
- `vite.config.*` -> vite/react hints
- `Dockerfile` / `docker-compose.*` -> docker/deployment/postgresql/mysql hints
- path extensions/folders -> frontend/backend/database/tests/deployment hints

## Manifest Handling

Allowlisted manifest/config files:
- `package.json`
- `pyproject.toml`
- `requirements.txt`
- `composer.json`
- `vite.config.*`
- `docker-compose.yml`
- `docker-compose.yaml`
- `Dockerfile`
- `tsconfig.json`
- `pytest.ini`
- `phpunit.xml`

Manifest reads are capped and decoded from bytes. The scanner extracts script names/values and dependency names only, bounded by response limits.

## Protected / Secret Handling

Secret-like paths are not read:
- `.env`, `.env.local`, `.env.production`, `.env.test`, `.envrc`
- private key files such as `.pem`, `.key`, `.p12`, `.pfx`
- credentials/secrets file names

Secret-like manifest script values are redacted before returning.

## Endpoint Behavior

Added:

`POST /api/project-intake/existing-project/repo-intake-preview`

Behavior:
- read-only
- uses `project_id` to resolve stored path when `project_path` is empty
- rejects explicit paths outside the selected project root when `project_id` is provided
- returns safe response for missing/invalid paths
- creates no DB records
- creates no tool_calls
- does not call providers
- does not execute commands

## Frontend Behavior

Updated New Task existing-project mode:
- added "Analyze existing project structure" button
- displays detected stack, project type, areas, manifest summaries, protected path warnings, SoT hints, Module Map hints, test discovery hints, clarifying questions, safety notes, limitations, and recommended first safe action
- auto-fills Known Stack from detected stack only when the field is empty

No hidden run creation, project creation, provider call, command execution, patch proposal, apply, or test execution is triggered.

## Safety Boundaries

Preserved:
- no DB schema changes
- no migrations
- no provider calls
- no network calls
- no shell/subprocess/os command execution
- no `execute_run`
- no `asyncio.create_task`
- no tool_call creation
- no project creation
- no run creation
- no run step creation
- no patch proposal creation
- no apply patch
- no auto-start
- no guard/approval bypass

## Tests Added

Added:

`backend/tests/test_existing_project_readonly_repo_intake_fastlane.py`

Coverage:
- React/Vite/package detection
- FastAPI/Python detection
- PHP/composer/Laravel detection
- database/schema hints
- test folder/script hints
- Docker/deployment hints
- generated/vendor folder exclusions
- traversal caps
- manifest dependency caps
- `.env` and private key non-read behavior
- manifest redaction
- unsafe path rejection
- outside selected project root rejection
- project_id and explicit path endpoint modes
- no project/run/run_step/tool_call/proposal/apply/provider/command side effects
- deterministic output
- frontend static anchors

## Exact Check Results

Backend compile:
- `.venv/bin/python -m py_compile src/orchestrator/project_intake.py src/api/routes.py src/models.py tests/test_existing_project_readonly_repo_intake_fastlane.py` -> passed

Focused tests:
- `.venv/bin/pytest -q tests/test_existing_project_readonly_repo_intake_fastlane.py` -> `33 passed`
- `.venv/bin/pytest -q tests/test_existing_project_readonly_repo_intake_fastlane.py tests/test_unified_autonomous_project_intake.py` -> `77 passed`

Targeted compatibility:
- `.venv/bin/pytest -q tests/test_execute_next_step.py tests/test_step_patch_draft_guarded_proposal_fastlane.py tests/test_step_agent_patch_draft_fastlane.py tests/test_intake_run_agent_assignment_step_context.py` -> `173 passed`

Full backend:
- Initial full backend run found one static-scan placement issue.
- Fixed by removing `.read_text(` from the unified-intake source slice and using capped byte reads for allowlisted manifests.
- Final `.venv/bin/pytest -q` -> `2157 passed, 38 subtests passed in 20.64s`

Frontend:
- `npx tsc --noEmit` -> passed
- `npm run build` -> passed
- `npm run test:e2e:smoke` -> `2 passed`

Root runner:
- `bash scripts/run_tests.sh` -> passed
  - backend syntax checks passed
  - backend pytest: `2157 passed, 38 subtests passed`
  - frontend checks completed

## Files Changed

Changed by this slice:
- `backend/src/orchestrator/project_intake.py`
- `backend/src/api/routes.py`
- `backend/tests/test_existing_project_readonly_repo_intake_fastlane.py`
- `frontend/src/types/index.ts`
- `frontend/src/api/client.ts`
- `frontend/src/pages/NewTask.tsx`
- `runs/existing-project-readonly-repo-intake-fastlane-v1/final-report.md`

## Protected Files Touched Or Not

Not touched by this slice:
- `backend/src/storage/database.py`
- `backend/src/orchestrator/engine.py`
- `backend/src/providers/*`
- `backend/src/model_router.py`
- `scripts/run_tests.sh`

Note: the worktree already shows pre-existing dirty/untracked state for some protected files, including `database.py`, `engine.py`, and `scripts/run_tests.sh`. They were not edited for this slice.

## P0/P1/P2/P3 Issues

P0: none found.

P1: none found.

P2:
- repo intake is structural/manifest-only and does not yet perform semantic source understanding
- no automatic Module Map persistence from repo intake yet

P3:
- NewTask existing-project panel is functional but dense; a later UX pass could split repo intake into a dedicated project context panel

## Known Limitations

- read-only structure/manifest analysis only
- no arbitrary source file reading
- no semantic code understanding yet
- no provider/LLM reasoning
- no automatic Module Map persistence
- no test execution
- no patch/test/fix loop

## Recommended Next Slice

Recommended next slice:

Existing Project Repo Intake Regression Pass

Alternative:

Repo Intake -> Source of Truth / Module Map Seeding Fastlane v1

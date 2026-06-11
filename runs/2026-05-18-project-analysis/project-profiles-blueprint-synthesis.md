# Project Profiles Blueprint Synthesis

Date: 2026-05-18
Scope: synthesis of read-only Project Profiles implementation blueprint

## Decision

Proceed with **Phase 1: Project Profiles** as the next implementation slice.

The target acceptance criteria:

- User can register an external project with an absolute validated path.
- User can select that project in New Task.
- Runs store `project_id` and resolved `project_path`.
- Orchestrator remains planning-only, but receives project context.
- Tools can show project git status.
- Tools can run configured test/build commands for that project when allowed.
- Workbench run artifacts stay under Workbench `runs/`.
- Target project files are not modified by this phase.

## Important Adjustments To The Blueprint

1. Pydantic list fields must use `Field(default_factory=list)`, not `[]`.
2. SQLite cannot add a foreign key constraint to an existing table with a simple `ALTER TABLE`. For this phase, add `project_id` and `project_path` columns without enforcing FK at SQLite level, and enforce project existence in application code. A proper table rebuild migration can come later.
3. Project-scoped test/build endpoints should not execute arbitrary unsafe commands. If a command is not explicitly safe or matches dangerous patterns, the endpoint should create or return an approval-needed response and not execute it.
4. `GET /api/workspace/status` and `POST /api/tools/run-tests` should remain as Workbench self-tools. New project-scoped tools should be additive.
5. Existing runs without project context should remain readable.
6. Path validation must reject dangerous roots and missing directories, but should allow normal project paths with spaces and non-ASCII characters.

## Recommended Coding Split

Implement backend first, then frontend.

Backend first:

- models;
- DB migration/backfill;
- project CRUD;
- path validation utility;
- run project context storage;
- orchestrator context;
- project workspace/test/build endpoints;
- backend tests.

Frontend second:

- typed project profile fields;
- Projects form/details;
- New Task project selector;
- Tools project selector and project-scoped actions.

Reason:

The frontend should bind to stable backend behavior rather than guessing the API shape.

## Next Agent

Use a backend implementation agent next. Give it permission to modify backend and tests only. Keep frontend untouched for this step.

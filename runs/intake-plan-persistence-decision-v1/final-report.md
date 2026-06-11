# Intake/Plan Persistence Decision v1

## Summary

Decision: introduce a separate `IntakeSession` persistence boundary later, then explicitly convert a confirmed session into a Project and/or Run.

Preferred option: **D. Hybrid: IntakeSession -> Project/Run later**.

Rationale:

- Intake can happen before a project exists.
- A project can already exist before a run exists.
- Users may revise answers, brief drafts, and plan previews multiple times before confirming.
- Plans need version history before they become executable run steps.
- Creating a run should remain an explicit user action, not a side effect of intake analysis.

This report is architecture-only. No source code, schema, endpoint, migration, or runtime behavior was changed.

## Current State

Implemented read-only preview flow:

- `POST /api/project-intake/questions`
- `POST /api/project-intake/brief-draft`
- `POST /api/project-intake/plan-preview`
- NewTask UI: `Analyze idea`, `Draft brief`, `Preview plan`
- Existing Project Onboarding Checklist
- Start Task payload remains `{ prompt, mode, project_id: projectId }`

Current behavior:

- raw idea is sent transiently through API requests;
- intake/brief/plan are preview-only;
- answers are not persisted;
- brief drafts are not persisted;
- plan previews are not persisted;
- intake does not create projects, runs, assignments, tool calls, patches, or commands;
- tools/providers are not executed.

## Options Considered

### A. Attach To Project

Pros:

- Natural for existing-project onboarding.
- Keeps long-lived product context near project metadata.
- Good for project-level brief history.

Cons:

- New project intake often happens before a project exists.
- Forces premature project creation.
- Harder to model abandoned or exploratory ideas.
- Multiple competing plans for the same future project become awkward.

Verdict: useful as a later link, but not the primary persistence root.

### B. Attach To Run

Pros:

- Run is already the execution boundary.
- Plan can become future run steps.
- Easy to inspect "why this run exists".

Cons:

- Intake currently happens before run creation.
- Users may edit brief/plan before deciding to start a run.
- Forces premature run creation.
- Existing project onboarding may need to happen without executing anything.

Verdict: too late in the lifecycle to be the primary intake object.

### C. Separate IntakeSession Entity

Pros:

- Correctly models pre-project and pre-run work.
- Supports drafts, answers, versions, and readiness status.
- Can later link to an existing project, a newly created project, or a run.
- Keeps preview state out of Project and Run until confirmed.

Cons:

- Adds a new lifecycle and API surface.
- Requires careful cleanup/status handling for abandoned sessions.
- Needs clear conversion boundaries to avoid becoming a second Run model.

Verdict: strong baseline, but should explicitly link forward to Project/Run.

### D. Hybrid: IntakeSession -> Project/Run Later

Pros:

- Preserves all benefits of separate sessions.
- Supports both new-project and existing-project flows.
- Allows explicit confirmation before creating project/run.
- Lets selected brief/plan versions become the source of future run steps.
- Keeps version history without polluting Project/Run tables.

Cons:

- Slightly more complex than direct Project/Run attachment.
- Requires clear "confirmed version" semantics.
- Requires future migration discipline.

Verdict: recommended.

## Recommended Decision

Create a future `IntakeSession` aggregate as the canonical persistence boundary for intake, brief, and plan work.

The session should:

- store the raw idea/prompt;
- store mode and detected metadata;
- store intake responses;
- store user answers;
- store versioned brief drafts;
- store versioned plan previews;
- track selected/confirmed brief and plan versions;
- link optionally to a project;
- link optionally to a run only after explicit user confirmation;
- keep readiness status separate from execution status.

Conversion rule:

- An `IntakeSession` may create or link a Project only after explicit user confirmation.
- An `IntakeSession` may create a Run only after explicit user confirmation.
- Creating a Run from a session must not execute tools automatically; it should only create the run/initial planning state defined by that future slice.

## Proposed Data Model

### `intake_sessions`

Purpose:

- Root object for intake lifecycle before project/run execution.

Key fields:

- `id`
- `raw_idea`
- `mode` (`new_project`, `existing_project`, `unknown`)
- `detected_target_type`
- `detected_maturity_goal`
- `status` (`draft`, `needs_input`, `ready_to_confirm`, `confirmed`, `converted_to_project`, `converted_to_run`, `archived`)
- `readiness` / `ready_to_plan`
- `project_id` nullable
- `run_id` nullable
- `selected_brief_version_id` nullable
- `selected_plan_version_id` nullable
- `source` (`new_task_ui`, `api`, future imports)
- `created_at`
- `updated_at`
- `confirmed_at` nullable

Relation:

- Optional many-to-one to Project.
- Optional one-to-one or many-to-one to Run once converted.

Versioned:

- Session itself is not versioned; child brief/plan records are versioned.

Lifecycle:

- Created when user chooses to save an intake preview.
- Updated as answers/briefs/plans evolve.
- Confirmed explicitly before project/run conversion.

### `intake_answers`

Purpose:

- Store non-sensitive user answers to intake questions.

Key fields:

- `id`
- `session_id`
- `question_id`
- `category`
- `priority`
- `question_text_snapshot`
- `answer_text`
- `is_sensitive`
- `redacted`
- `created_at`
- `updated_at`

Relation:

- Belongs to `intake_sessions`.

Versioned:

- Simple answer rows can be updated in v1.
- If audit history matters later, add `intake_answer_versions`.

Lifecycle:

- Created/updated by user input.
- Sensitive values should be rejected or stored only as redacted placeholders.

### `intake_brief_versions`

Purpose:

- Store generated or edited project brief drafts.

Key fields:

- `id`
- `session_id`
- `version_number`
- `title`
- `summary`
- `brief_markdown`
- `sections_json`
- `assumptions_json`
- `missing_information_json`
- `open_questions_json`
- `ready_to_plan`
- `source` (`generated`, `user_edited`, `imported`)
- `created_at`

Relation:

- Belongs to `intake_sessions`.
- Session may select one as `selected_brief_version_id`.

Versioned:

- Yes. Brief drafts should be append-only versions.

Lifecycle:

- Generated from current idea/answers.
- User may edit and save a new version.
- Selected version can later seed project/run artifacts.

### `intake_plan_versions`

Purpose:

- Store structured plan previews and future confirmed plan candidates.

Key fields:

- `id`
- `session_id`
- `version_number`
- `title`
- `summary`
- `phases_json`
- `required_inputs_json`
- `assumptions_json`
- `risks_json`
- `recommended_agent_ids_json`
- `ready_to_start`
- `source_readiness_json`
- `source_brief_version_id` nullable
- `source` (`generated`, `user_edited`, `confirmed`)
- `created_at`

Relation:

- Belongs to `intake_sessions`.
- May reference a brief version.
- Session may select one as `selected_plan_version_id`.

Versioned:

- Yes. Plan previews should be append-only versions.

Lifecycle:

- Generated from idea/intake/brief.
- User may regenerate or edit.
- Selected version can later become the source for run planning/staged steps.

### Source Metadata

Source metadata can live initially on `intake_sessions` and version rows:

- `created_from`
- `frontend_version` optional
- `policy_version` optional
- `intake_algorithm_version` optional
- `brief_algorithm_version` optional
- `plan_algorithm_version` optional

This helps future migrations and debugging when deterministic rules evolve.

## Proposed API Surface

Future endpoints, not implemented in this slice:

- `POST /api/intake-sessions`
  - Create a draft session from raw idea and optional project link.
  - No run creation.

- `GET /api/intake-sessions/{id}`
  - Return session, answers, selected versions, and latest generated versions.

- `PATCH /api/intake-sessions/{id}`
  - Update non-execution metadata such as raw idea, mode, project link, status.

- `POST /api/intake-sessions/{id}/answers`
  - Save user answers after sensitive-value validation/redaction.

- `POST /api/intake-sessions/{id}/brief`
  - Generate or save a new brief version.
  - No provider/tool execution.

- `POST /api/intake-sessions/{id}/plan`
  - Generate or save a new plan version.
  - No run creation or tool execution.

- `POST /api/intake-sessions/{id}/select-brief`
  - Select a brief version as the confirmed/current brief candidate.

- `POST /api/intake-sessions/{id}/select-plan`
  - Select a plan version as the confirmed/current plan candidate.

- `POST /api/intake-sessions/{id}/create-project`
  - Future explicit user-confirmed project creation from a confirmed session.

- `POST /api/intake-sessions/{id}/create-run`
  - Future explicit user-confirmed run creation from selected brief/plan.
  - Must not execute tools automatically.

## Lifecycle

Recommended lifecycle:

1. User enters idea in NewTask.
2. User runs read-only analysis/brief/plan previews.
3. User optionally saves an `IntakeSession`.
4. User answers questions and regenerates brief/plan versions.
5. User selects a brief version and plan version.
6. User explicitly confirms conversion.
7. For new project flow:
   - create/link Project after confirmation;
   - create Run only after separate confirmation.
8. For existing project flow:
   - link to existing Project after user confirms path/profile;
   - create Run only after user confirms the selected plan.
9. Future orchestrator consumes only confirmed plan versions.

## Safety Guarantees

Persistence must preserve these boundaries:

- Saving intake must not create a run.
- Saving intake must not create tool calls.
- Saving brief/plan versions must not execute tools.
- Saving brief/plan versions must not call providers.
- Turning a plan into a run requires explicit user confirmation.
- Turning a plan into run steps must be a separate future workflow.
- No patch/proposal/apply/tests/analyze/rollback can happen from intake persistence.
- Existing project paths must be validated before linking to a project profile.
- Existing project path validation must not scan files until a later explicit onboarding scan workflow.
- Secrets, `.env` values, tokens, credentials, private keys, and passwords must not be stored as answer values.
- If a user mentions secret-like data, store only a redacted marker and a warning.
- Version rows should keep generated content, not hidden execution side effects.

## Migration Strategy

Future safe implementation order:

1. **v1: Pure models/schema proposal**
   - Finalize model fields, statuses, and version semantics in docs/tests.
   - No DB changes.

2. **v2: DB migration + storage helpers**
   - Add tables and storage functions.
   - Keep helpers isolated; avoid enlarging `database.py` further if possible.

3. **v3: API create/get session**
   - Add create/get/update session endpoints.
   - No run creation.

4. **v4: Frontend save/load**
   - Let NewTask save/load sessions and versions.
   - Keep previews advisory.

5. **v5: Create run from confirmed session**
   - Add explicit confirmation UI/API.
   - Create run from selected plan without executing tools automatically.

6. **v6: Orchestrator consumes confirmed plan**
   - Convert confirmed plan version into structured run planning input.
   - Still respect approval boundaries for patch/apply/tests.

## Risks

- `backend/src/storage/database.py` is already large and dirty; adding more persistence there may increase maintenance risk.
- A wrong schema could lock future workflow too tightly.
- Storing secrets accidentally would create a serious safety issue.
- Coupling intake too tightly to Run would force premature execution objects.
- Coupling intake too tightly to Project would make exploratory/new-project intake awkward.
- Losing version history would make it hard to explain why a run was created.
- Frontend/backend policy duplication may drift if readiness and safety rules are copied in multiple places.
- Plan versions may become confused with executable run steps unless the conversion boundary is explicit.

## Recommended Next Slice

Intake Session Storage Foundation v1.

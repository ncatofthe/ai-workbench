# AI Workbench — Provider Strategy

## Purpose

AI Workbench must support development both with internet access and without internet access.

The product is **offline-first**, not **offline-only**.

This means:

- local Ollama must be enough to run the core product;
- cloud/external coding agents such as ChatGPT, Codex, Claude Code or other providers can be used as optional accelerators;
- the project must never depend on a cloud provider to complete the normal development cycle;
- cloud providers must be disabled by default unless the user explicitly selects hybrid/cloud mode.

---

## Provider modes

### 1. `local` mode

Default mode.

Uses only local components:

- Ollama models;
- local project files;
- local SQLite database;
- local tools;
- local runs directory.

Allowed:

- planning;
- architecture;
- staged step execution;
- file analysis;
- patch proposal;
- patch application inside workspace when enabled;
- local tests;
- local final report.

Not allowed:

- ChatGPT/Codex calls;
- Claude API calls;
- Claude Code provider calls;
- external network model calls;
- cloud storage dependency.

This mode must work without internet.

---

### 2. `hybrid` mode

Optional mode.

Uses local Ollama as the default provider, but can route specific high-value tasks to cloud/external coding agents when the user enables them.

Examples:

- use local Ollama for normal steps;
- use Claude Code for deep refactoring review;
- use Codex/ChatGPT for architecture critique;
- use cloud provider for large context analysis when local context is insufficient.

Rules:

- local provider remains the default;
- each cloud call must be logged;
- cloud use must be visible in RunDetail;
- cloud use must not be silent;
- cloud failure must fall back to local mode where possible;
- no secrets should be sent to cloud providers unless explicitly allowed.

---

### 3. `cloud` mode

Explicit user-selected mode.

Cloud/external providers can be primary for selected tasks.

This is useful when:

- local models are too weak for a complex task;
- internet is available;
- user wants Claude Code/Codex/ChatGPT to handle a particular slice;
- user accepts the privacy and dependency tradeoff.

Rules:

- never enable by default;
- require user selection in settings/project profile/run config;
- clearly show which provider handled each step;
- preserve local project state and local logs;
- keep the repository usable without cloud mode later.

---

## Provider types

### Local Ollama Provider

The permanent default provider.

Responsibilities:

- planning;
- architecture;
- model-routed agent execution;
- code analysis;
- patch proposal;
- test failure analysis;
- documentation generation;
- final report generation.

Ollama provider must always remain supported.

---

### ChatGPT / Codex Provider

Optional external provider.

Best for:

- advanced code generation;
- complex multi-file reasoning;
- second-opinion code review;
- architecture critique;
- difficult debugging;
- generating implementation plans for external agents.

The system should treat it as a provider adapter, not as the core runtime.

---

### Claude Code Provider

Optional external/interactive coding provider.

Best for:

- repository-wide edits;
- long-form codebase analysis;
- refactoring tasks;
- final audit before commit;
- implementation slices when local models are insufficient.

Claude Code can be used as a powerful external worker, but AI Workbench must remain capable of running without it.

---

## Provider abstraction

The backend should eventually expose a provider interface similar to:

```text
Provider
- id
- name
- type: local | cloud | external_cli
- capabilities
- available
- requires_internet
- supports_streaming
- supports_tools
- supports_file_editing
- max_context
- privacy_level
```

Suggested provider operations:

```text
chat_completion()
structured_completion()
review_diff()
propose_patch()
analyze_test_failure()
```

---

## Routing policy

The Orchestrator should choose providers based on:

- current mode: local / hybrid / cloud;
- task type;
- agent role;
- project sensitivity;
- internet availability;
- model availability;
- user preference;
- cost/privacy constraints;
- context size.

Examples:

```text
small code fix + local mode → Ollama qwen2.5-coder:7b
large refactor + hybrid mode → Claude Code if enabled, otherwise Ollama qwen3-coder
architecture critique + hybrid mode → ChatGPT/Codex/Claude if enabled, otherwise local reasoning model
test failure analysis + local mode → local debugging profile
security review with sensitive files → local-only unless user explicitly allows cloud
```

---

## Privacy policy

By default:

- do not send `.env` files;
- do not send secrets;
- do not send private keys;
- do not send tokens;
- do not send production credentials;
- do not send user private files outside the selected project scope.

Cloud provider calls should include redaction and a clear log entry.

The user should be able to choose:

```text
Cloud providers: disabled / ask every time / enabled for non-sensitive tasks / enabled
```

---

## Offline requirements

The following must work without internet:

- open UI;
- create project profile;
- create run;
- generate local plan using Ollama;
- assign local agents;
- use local model routing;
- inspect files;
- propose/apply patches inside workspace;
- run local tests;
- generate final report;
- inspect previous runs.

If internet/cloud provider is unavailable, the system should degrade gracefully:

```text
cloud provider unavailable → fallback to local provider → mark step as local_fallback → continue if possible
```

---

## UI requirements

Project settings should eventually include:

```text
Provider mode:
- Local only
- Hybrid
- Cloud preferred
```

RunDetail should show:

- which provider was used for each step;
- which model was used;
- whether a fallback occurred;
- whether cloud was used;
- whether sensitive data was redacted.

---

## Roadmap impact

Agent Registry, Dynamic Agent Team Assignment, Model Registry, provider metadata, and provider routing decisions are now in place. Real external provider execution from the backend is still not implemented: Codex/Claude remain stub-only and must not be treated as working execution providers.

Recommended order from here:

1. Keep local Ollama as the default execution provider.
2. Preserve provider route visibility and local fallback behavior.
3. Add provider-aware approval/redaction before any real cloud/external execution.
4. Implement Codex/Claude adapters only behind explicit user enablement and approvals.
5. Continue to block silent cloud calls and automatic provider escalation.

---

## Final rule

AI Workbench must never become dependent on ChatGPT, Codex, Claude Code or any external cloud provider.

Those providers are optional acceleration layers.

The core promise remains:

```text
local-first development with optional cloud assistance
```

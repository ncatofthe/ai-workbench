# AI Workbench — Ollama Model Routing

## Purpose

AI Workbench should not hardcode one model per agent forever.

Agents should use model profiles. A model profile defines the best default model, fast model, reasoning model and fallback model for a category of work.

This makes the system easier to maintain as Ollama models change.

---

## Hardware target

Primary expected local machine:

```text
MacBook Pro M1 Pro
32GB unified memory
local Ollama
```

Important rule:

```text
many agents does not mean many large models running in parallel
```

On 32GB RAM, use hardware-aware scheduling:

- heavy 30B-class model: usually `max_parallel = 1`;
- medium 14B-class model: usually `max_parallel = 1` or carefully `2`;
- small 7B/8B-class model: can be used for faster/simple tasks;
- embedding model can run separately but should still be monitored.

---

## Practical local model set

Recommended starting Ollama models:

```bash
ollama pull qwen3-coder:30b
ollama pull qwen2.5-coder:7b
ollama pull qwen2.5-coder:3b
ollama pull qwen3:14b
ollama pull qwen3:8b
ollama pull deepseek-r1:14b
ollama pull gemma3:12b-it-q4_K_M
ollama pull nomic-embed-text
```

Optional heavier models only if memory/performance is acceptable:

```bash
ollama pull deepseek-r1:32b-qwen-distill-q4_K_M
ollama pull gemma3:27b-it-q4_K_M
```

Do not assume all optional models are installed.

---

## Model profiles

### `coding_heavy`

For complex code generation, multi-file patches, backend/frontend implementation, refactoring.

```json
{
  "primary": "qwen3-coder:30b",
  "fast": "qwen2.5-coder:7b",
  "small": "qwen2.5-coder:3b",
  "reasoning": "deepseek-r1:14b",
  "fallback": "qwen2.5-coder:7b",
  "max_parallel": 1
}
```

Use for:

- backend-developer;
- frontend-developer;
- fullstack-developer;
- react-specialist;
- fastapi-developer;
- node-specialist;
- php-pro;
- typescript-pro;
- python-pro.

### `coding_fast`

For small edits, simple components, type fixes, formatting, local bugfixes.

```json
{
  "primary": "qwen2.5-coder:7b",
  "heavy": "qwen3-coder:30b",
  "small": "qwen2.5-coder:3b",
  "fallback": "qwen2.5-coder:7b",
  "max_parallel": 2
}
```

### `planning_reasoning`

For product planning, architecture, task decomposition and orchestration.

```json
{
  "primary": "qwen3:14b",
  "deep_reasoning": "deepseek-r1:14b",
  "heavy": "qwen3:30b-thinking",
  "fallback": "qwen3:8b",
  "max_parallel": 1
}
```

Use for:

- orchestrator;
- product-manager;
- business-analyst;
- architect;
- project-manager;
- scrum-master.

### `debugging`

For errors, stack traces, test failures and fix planning.

```json
{
  "primary": "deepseek-r1:14b",
  "patch_model": "qwen3-coder:30b",
  "fast": "qwen2.5-coder:7b",
  "fallback": "qwen3:14b",
  "max_parallel": 1
}
```

Use for:

- qa-expert;
- test-automator;
- error-detective;
- debugger;
- code-reviewer.

### `security_review`

For security, RBAC, file access, upload logic, secrets and dangerous commands.

```json
{
  "primary": "deepseek-r1:14b",
  "code_audit": "qwen3-coder:30b",
  "fast": "qwen3:14b",
  "fallback": "qwen3:8b",
  "max_parallel": 1
}
```

Use for:

- security-auditor;
- security-engineer;
- penetration-testing-specialist;
- compliance-auditor.

### `documentation`

For README, API docs, final reports, release notes and instructions.

```json
{
  "primary": "qwen3:14b",
  "fast": "qwen3:8b",
  "large_context": "qwen3-coder:30b",
  "fallback": "qwen3:8b",
  "max_parallel": 1
}
```

Use for:

- technical-writer;
- documentation-engineer;
- api-documenter;
- readme-generator.

### `vision_ui`

For UI screenshots, design analysis and visual QA.

```json
{
  "primary": "gemma3:12b-it-q4_K_M",
  "heavy": "gemma3:27b-it-q4_K_M",
  "coding": "qwen3-coder:30b",
  "fallback": "qwen3:14b",
  "max_parallel": 1
}
```

Use for:

- ui-designer;
- design-bridge;
- accessibility-tester;
- ui-ux-tester.

### `embeddings`

For code search, RAG and project memory.

```json
{
  "primary": "nomic-embed-text",
  "alternative": "mxbai-embed-large"
}
```

Use for:

- code search index;
- documentation search;
- previous run retrieval;
- semantic project context.

---

## Task-to-model routing

Recommended routing:

| Task type | Model profile |
|---|---|
| product analysis | `planning_reasoning` |
| architecture | `planning_reasoning` |
| API design | `planning_reasoning` or `coding_heavy` |
| backend implementation | `coding_heavy` |
| frontend implementation | `coding_heavy` |
| small code fix | `coding_fast` |
| test failure analysis | `debugging` |
| code review | `debugging` or `security_review` |
| security audit | `security_review` |
| docs/report | `documentation` |
| screenshot/UI review | `vision_ui` |
| codebase search | `embeddings` |

---

## Agent examples

### FastAPI Developer

```json
{
  "id": "fastapi-developer",
  "model_profile": "coding_heavy",
  "default_model": "qwen3-coder:30b",
  "fast_model": "qwen2.5-coder:7b",
  "reasoning_model": "deepseek-r1:14b"
}
```

### QA Expert

```json
{
  "id": "qa-expert",
  "model_profile": "debugging",
  "default_model": "deepseek-r1:14b",
  "patch_model": "qwen3-coder:30b",
  "fast_model": "qwen2.5-coder:7b"
}
```

### Product Manager

```json
{
  "id": "product-manager",
  "model_profile": "planning_reasoning",
  "default_model": "qwen3:14b",
  "reasoning_model": "deepseek-r1:14b"
}
```

---

## Router rules

1. Prefer fast/small models for trivial tasks.
2. Use coding-heavy models only when code changes are non-trivial.
3. Use reasoning models for planning, debugging and security.
4. Do not run multiple heavy models concurrently by default.
5. If a selected model is not installed, fall back to the profile fallback.
6. Log the selected model for every step.
7. Store provider/model metadata in run timeline.

---

## Current status and future features

Implemented:

- model registry and profiles;
- provider router metadata;
- agent-level and step-level route decisions;
- installed/enabled metadata surfaced through the registry API;
- RunDetail route badges for staged steps.

Still future:

- per-agent model overrides;
- benchmark history per local machine;
- automatic routing based on richer task complexity signals;
- cost/time/performance metrics;
- deeper model health status;
- real external provider execution from backend.


## Relationship to provider routing

Model routing is primarily about selecting the best local Ollama model for a task.

Provider routing is a wider layer that decides whether a task should use local Ollama, an optional ChatGPT/Codex provider, or an optional Claude Code provider.

Default behavior must remain:

```text
provider = local_ollama
mode = local
```

Hybrid/cloud providers are only used when enabled by the user.

See `AI_WORKBENCH_PROVIDER_STRATEGY.md`.

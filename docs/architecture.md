# Architecture

## Overview

AI Workbench is a local-first multi-agent development platform. It runs entirely on your machine, using Ollama for AI inference and a lightweight FastAPI + React stack for the control plane.

## System Diagram

```
┌─────────────────────────────────────────────────┐
│                   Browser UI                     │
│            (React + Vite + Tailwind)             │
│         http://localhost:5173                     │
└──────────────────┬──────────────────────────────┘
                   │ HTTP (REST)
┌──────────────────▼──────────────────────────────┐
│              FastAPI Backend                      │
│           http://localhost:8000                   │
│                                                   │
│  ┌────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  API Layer │  │ Orchestrator│  │  Storage   │ │
│  │  (routes)  │→ │  (engine)   │→ │  (SQLite)  │ │
│  └────────────┘  └──────┬──────┘  └───────────┘ │
│                         │                         │
│  ┌──────────────────────▼────────────────────┐   │
│  │           Provider Layer                   │   │
│  │  ┌────────┐  ┌───────┐  ┌──────────────┐ │   │
│  │  │ Ollama │  │ Codex │  │ Claude Code  │ │   │
│  │  │(active)│  │(stub) │  │   (stub)     │ │   │
│  │  └───┬────┘  └───────┘  └──────────────┘ │   │
│  └──────┼────────────────────────────────────┘   │
└─────────┼────────────────────────────────────────┘
          │ HTTP
┌─────────▼────────────┐
│    Ollama Server      │
│  localhost:11434      │
│  (qwen2.5-coder:7b)  │
└───────────────────────┘
```

## Components

### Backend (Python/FastAPI)
- **API Layer**: REST endpoints for projects, runs, agents, approvals, config
- **Orchestrator**: Task decomposition and execution engine
- **Providers**: Pluggable AI backends (Ollama, Codex stub, Claude stub)
- **Storage**: SQLite database for persistence
- **Safety**: Approval gate for dangerous operations
- **Agents Registry**: Loads agent role definitions from markdown files

### Frontend (React/TypeScript)
- **Dashboard**: System status overview
- **New Task**: Task creation with mode selection
- **Runs**: Execution history with live status
- **Run Detail**: Plan, logs, and artifacts viewer
- **Agents**: Agent roster and capabilities
- **Approvals**: Approve/reject dangerous operations
- **Settings**: Provider and mode configuration

### Agent System
- Agents are defined as markdown instruction files in `agents/`
- Each agent has a role, capabilities, and constraints
- The orchestrator loads instructions and sends them as system prompts to the AI provider

## Data Flow

1. User creates a task via the UI
2. Backend creates a Run record and launches the orchestrator
3. Orchestrator loads agent instructions, calls Ollama for planning
4. Plan is saved to the run directory and database
5. UI polls for updates and displays results
6. Any dangerous operations create ApprovalRequests
7. User approves/rejects via the Approvals page

## Storage

SQLite database at `data/workbench.db` with tables:
- `projects` — project definitions
- `runs` — task execution records
- `approvals` — approval requests
- `artifacts` — generated files

Run artifacts are saved to `runs/<timestamp>_<id>/`.

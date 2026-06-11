# Usage Guide

## Quick Start

### 1. Check Your Environment
```bash
bash scripts/check_env.sh
```

### 2. Install Dependencies
```bash
# Backend
cd backend
pip install -e ".[dev]"

# Frontend
cd ../frontend
npm install
```

### 3. Start Ollama
```bash
ollama serve
# In another terminal:
ollama pull qwen2.5-coder:7b
```

### 4. Launch AI Workbench
```bash
bash scripts/dev.sh
```

### 5. Open Dashboard
Navigate to http://localhost:5173

## Creating Your First Task

1. Click "New Task" in the sidebar
2. Describe what you want done (e.g., "Analyze the project structure and suggest improvements")
3. Select mode: **Offline** (recommended for first run)
4. Click "Start Task"
5. Watch the run progress on the Run Detail page

## Understanding Modes

- **Offline**: Uses only local Ollama. No external API calls. Best for privacy and speed.
- **Hybrid**: Uses Ollama first, falls back to cloud providers for complex tasks.
- **Cloud**: Enables Codex and Claude providers for maximum capability.

## Managing Approvals

When an agent needs to perform a restricted action (install packages, delete files, etc.), you'll see a notification in the Approvals page. Review the command and approve or reject it.

## Viewing Run Results

Each run produces artifacts in the `runs/` directory:
- `input.md` — the original task
- `plan.md` — the AI-generated execution plan
- `final-report.md` — summary of results

## Connecting Cloud Providers (Future)

### Codex CLI
1. Install: `npm install -g @openai/codex`
2. Go to Settings > Enable Codex CLI Provider
3. All Codex executions require approval

### Claude Code
1. Install Claude Code CLI
2. Go to Settings > Enable Claude Code Provider
3. All Claude executions require approval

## Troubleshooting

**Backend won't start**: Check that port 8000 is free. Ensure Python 3.11+ is installed.

**Frontend won't start**: Run `npm install` in the frontend directory. Check that port 5173 is free.

**Ollama not connecting**: Ensure `ollama serve` is running. Check the URL in Settings matches your Ollama instance.

**Model not found**: Run `ollama pull qwen2.5-coder:7b` to download the default model.

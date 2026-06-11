#!/usr/bin/env bash
# Start backend only in offline mode (no frontend, no cloud providers)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== AI Workbench — Offline Mode ==="

mkdir -p "$PROJECT_DIR/data"
mkdir -p "$PROJECT_DIR/runs"

# Check Ollama
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo "WARNING: Ollama is not running. The orchestrator will use fallback planning."
    echo "Start Ollama with: ollama serve"
    echo ""
fi

cd "$PROJECT_DIR/backend"
echo "Starting backend on :8000..."
echo "API Docs: http://localhost:8000/docs"
echo ""
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

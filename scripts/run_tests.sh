#!/usr/bin/env bash
# Run backend and frontend checks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== AI Workbench — Test Runner ==="

# Backend checks
echo ""
echo "--- Backend ---"
cd "$PROJECT_DIR/backend"

PYTHON_BIN="python3"
if [ -x ".venv/bin/python" ]; then
    PYTHON_BIN=".venv/bin/python"
fi

echo "Checking Python syntax..."
${PYTHON_BIN} -m py_compile src/main.py && echo "  main.py OK"
${PYTHON_BIN} -m py_compile src/models.py && echo "  models.py OK"
${PYTHON_BIN} -m py_compile src/api/routes.py && echo "  api/routes.py OK"
${PYTHON_BIN} -m py_compile src/model_router.py && echo "  model_router.py OK"
${PYTHON_BIN} -m py_compile src/storage/database.py && echo "  storage/database.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/cancellation.py && echo "  orchestrator/cancellation.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/engine.py && echo "  orchestrator/engine.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/workflow_policy.py && echo "  orchestrator/workflow_policy.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/project_intake.py && echo "  orchestrator/project_intake.py OK"
${PYTHON_BIN} -m py_compile src/providers/ollama.py && echo "  providers/ollama.py OK"
${PYTHON_BIN} -m py_compile src/approvals/safety.py && echo "  approvals/safety.py OK"
${PYTHON_BIN} -m py_compile src/utils/config.py && echo "  utils/config.py OK"
${PYTHON_BIN} -m py_compile src/utils/paths.py && echo "  utils/paths.py OK"
${PYTHON_BIN} -m py_compile src/agents/registry.py && echo "  agents/registry.py OK"
${PYTHON_BIN} -m py_compile src/providers/codex.py && echo "  providers/codex.py OK"
${PYTHON_BIN} -m py_compile src/providers/claude_provider.py && echo "  providers/claude_provider.py OK"
${PYTHON_BIN} -m py_compile src/storage/guard_result_storage.py && echo "  storage/guard_result_storage.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/guard_result_storage_contract.py && echo "  orchestrator/guard_result_storage_contract.py OK"
${PYTHON_BIN} -m py_compile src/orchestrator/guard_result_api_contract.py && echo "  orchestrator/guard_result_api_contract.py OK"
${PYTHON_BIN} -m py_compile src/cli.py && echo "  cli.py OK"

if ${PYTHON_BIN} -m pytest --version &>/dev/null; then
    echo "Running pytest..."
    ${PYTHON_BIN} -m pytest -q
else
    echo "pytest not installed, skipping."
fi

# Frontend checks
echo ""
echo "--- Frontend ---"
cd "$PROJECT_DIR/frontend"

if [ -d "node_modules" ]; then
    echo "Running TypeScript check..."
    npx tsc --noEmit
else
    echo "node_modules not found. Run 'npm install' first."
fi

echo ""
echo "=== Tests complete ==="

#!/usr/bin/env bash
# Check that all required tools are available
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=== AI Workbench — Environment Check ==="
echo ""

check() {
    local name="$1"
    local cmd="$2"
    local required="${3:-true}"
    if command -v "$cmd" &>/dev/null; then
        local ver
        ver=$("$cmd" --version 2>/dev/null | head -1 || echo "found")
        echo -e "  ${GREEN}✓${NC} $name: $ver"
    else
        if [ "$required" = "true" ]; then
            echo -e "  ${RED}✗${NC} $name: NOT FOUND (required)"
        else
            echo -e "  ${YELLOW}○${NC} $name: not found (optional)"
        fi
    fi
}

echo "Required:"
check "Python 3"    python3
check "Node.js"     node
check "npm"         npm

echo ""
echo "AI Providers:"
check "Ollama"      ollama     true
check "Codex CLI"   codex      false
check "Claude CLI"  claude     false

echo ""
echo "Optional:"
check "pnpm"        pnpm       false
check "Docker"      docker     false

# Check Ollama status
echo ""
echo "Ollama Status:"
if curl -s http://localhost:11434/api/tags &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Ollama is running on :11434"
    models=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys,json; [print(f'    - {m[\"name\"]}') for m in json.load(sys.stdin).get('models',[])]" 2>/dev/null || echo "    (could not list models)")
    echo "$models"
else
    echo -e "  ${YELLOW}○${NC} Ollama is not running. Start with: ollama serve"
fi

echo ""
echo "=== Check complete ==="

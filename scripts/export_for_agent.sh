#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
EXPORT_DIR="${REPO_ROOT}/exports"
TIMESTAMP="$(date +"%Y%m%d-%H%M%S")"
ARCHIVE_PATH="${EXPORT_DIR}/ai-workbench-agent-export-${TIMESTAMP}.zip"

if ! command -v zip >/dev/null 2>&1; then
  echo "Error: zip is required to create the agent export archive." >&2
  echo "Install zip or run this script on a system where zip is available." >&2
  exit 1
fi

mkdir -p "${EXPORT_DIR}"

cd "${REPO_ROOT}"

zip -qr "${ARCHIVE_PATH}" . \
  -x ".git/*" \
  -x "*/.git/*" \
  -x ".DS_Store" \
  -x "*/.DS_Store" \
  -x "__MACOSX/*" \
  -x "*/__MACOSX/*" \
  -x "node_modules/*" \
  -x "*/node_modules/*" \
  -x "frontend/node_modules/*" \
  -x "frontend/dist/*" \
  -x "backend/.venv/*" \
  -x "backend/.venv.backup/*" \
  -x "backend/.venv.backup*" \
  -x "backend/.venv.backup*/*" \
  -x ".venv/*" \
  -x "*/.venv/*" \
  -x "*/.venv.backup*" \
  -x "*/.venv.backup*/*" \
  -x "dist/*" \
  -x "*/dist/*" \
  -x "build/*" \
  -x "*/build/*" \
  -x "coverage/*" \
  -x "*/coverage/*" \
  -x "__pycache__/*" \
  -x "*/__pycache__/*" \
  -x ".pytest_cache/*" \
  -x "*/.pytest_cache/*" \
  -x ".mypy_cache/*" \
  -x "*/.mypy_cache/*" \
  -x ".ruff_cache/*" \
  -x "*/.ruff_cache/*" \
  -x "data/*.db" \
  -x "backend/data/*.db" \
  -x "workbench.db" \
  -x "*/workbench.db" \
  -x "backups/*" \
  -x "*/backups/*" \
  -x "runs/" \
  -x "runs/*" \
  -x "*/runs/" \
  -x "*/runs/*" \
  -x "exports/*" \
  -x "*.pyc" \
  -x "*/**/*.pyc" \
  -x "*.pyo" \
  -x "*/**/*.pyo" \
  -x "*.log" \
  -x "*/**/*.log" \
  -x ".env" \
  -x "backend/.env" \
  -x "frontend/.env"

SIZE="$(du -h "${ARCHIVE_PATH}" | awk '{print $1}')"

echo "Agent export created:"
echo "  ${ARCHIVE_PATH}"
echo "Size: ${SIZE}"

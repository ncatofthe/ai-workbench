"""Shared path helpers for repository-anchored runtime files."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def repo_path(*parts: str) -> Path:
    """Return an absolute path inside the AI Workbench repository."""
    return PROJECT_ROOT.joinpath(*parts)


def resolve_runtime_path(value: str | os.PathLike[str] | None, default_relative: str) -> Path:
    """
    Resolve a runtime path.

    Absolute paths stay absolute. Relative paths are anchored at the repository
    root so launching the backend from `backend/` or the repo root uses the same
    runtime files.
    """
    raw = Path(value or default_relative).expanduser()
    if raw.is_absolute():
        return raw
    return repo_path(str(raw))

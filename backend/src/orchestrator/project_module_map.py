"""Bounded deterministic read-only project module map scanner.

Inspects filesystem metadata (paths, file names, directory structure) to
produce a draft module map for a project.  No file contents are read.
No providers, no shell command execution, no network, no DB writes.

The output is a ``ProjectModuleMapScanPreviewResponse`` that the caller may
optionally persist via the PUT endpoint.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Optional

from src.models import (
    ProjectModuleMapItem,
    ProjectModuleMapScanPreviewResponse,
)


# ── Filesystem exclusions ─────────────────────────────────────────────────────

_EXCLUDED_DIRS: frozenset[str] = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "bower_components",
    "dist", "build", "out", ".next", ".nuxt",
    ".venv", "venv", "env", "__pycache__", ".mypy_cache", ".pytest_cache",
    "coverage", ".nyc_output", ".turbo",
    "target",           # Rust / Java Maven
    ".gradle",
    "vendor",           # Go / PHP
})

_EXCLUDED_FILENAMES: frozenset[str] = frozenset({
    ".env", ".env.local", ".env.production", ".env.test", ".envrc",
    "secrets.yaml", "secrets.yml", "secrets.json", "secrets.toml",
})

_EXCLUDED_SUFFIXES: frozenset[str] = frozenset({
    ".pem", ".key", ".p12", ".pfx", ".crt", ".cer",
    ".lock",   # package-lock / yarn.lock — not useful for module inference
    ".min.js", ".min.css",
})


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    # Exclude if any directory component matches the exclusion set
    return any(part in _EXCLUDED_DIRS for part in parts[:-1])


def _is_secret_file(path: Path) -> bool:
    name = path.name.lower()
    if name in _EXCLUDED_FILENAMES:
        return True
    for suf in _EXCLUDED_SUFFIXES:
        if name.endswith(suf):
            return True
    return False


# ── Heuristic module inference ────────────────────────────────────────────────

# Each entry: (module_type, slug, name, path-keyword regex pattern)
# Patterns are matched against the relative path string (lowercased).
_MODULE_PATTERNS: list[tuple[str, str, str, str]] = [
    # Authentication / identity
    ("feature", "auth", "Authentication", r"\b(auth|login|logout|session|jwt|oauth|token|password|credential|identity|sso)\b"),
    # Users / accounts / profiles
    ("feature", "users", "Users & Accounts", r"\b(user|account|profile|member|subscriber|customer|person)\b"),
    # Tasks / workflows
    ("feature", "tasks", "Tasks & Workflows", r"\b(task|todo|workflow|ticket|issue|item|job|queue|batch)\b"),
    # Finance / billing / payments
    ("feature", "finance", "Finance & Billing", r"\b(finance|billing|payment|invoice|stripe|subscription|pricing|plan|charge|credit|wallet)\b"),
    # Reports / analytics
    ("feature", "reports", "Reports & Analytics", r"\b(report|analytic|statistic|metric|dashboard|insight|chart|export)\b"),
    # File uploads / media / storage
    ("feature", "uploads", "File Uploads & Storage", r"\b(upload|file|media|attachment|storage|blob|s3|bucket|image|asset|document)\b"),
    # Reviews / approvals
    ("feature", "reviews", "Reviews & Approvals", r"\b(review|approval|approve|reject|feedback|rating|comment|moderate)\b"),
    # Notifications / emails
    ("feature", "notifications", "Notifications", r"\b(notification|notify|email|message|alert|webhook|push|event)\b"),
    # Admin / settings / config
    ("feature", "admin", "Admin & Settings", r"\b(admin|setting|config|configuration|preference|management|control)\b"),
    # Database / schema / migrations
    ("database", "database", "Database & Schema", r"\b(prisma|schema|migration|migrate|seed|sql|model|entity|db|database|knex|alembic|drizzle)\b"),
    # API routes / controllers / services (backend)
    ("backend", "api", "API Routes & Controllers", r"\b(route|controller|service|endpoint|handler|middleware|api|rest|graphql|resolver)\b"),
    # Frontend pages / components / store
    ("frontend", "frontend", "Frontend UI", r"\b(frontend|pages?|components?|store|hook|context|view|layout|ui|widget|modal|form|nav|sidebar)\b"),
    # Shared contracts / types / DTOs / enums
    ("shared", "contracts", "Shared Types & Contracts", r"\b(type|dto|contract|interface|enum|schema|spec|const|util|helper|lib|common|shared)\b"),
    # Tests / specs / e2e
    ("tests", "tests", "Tests", r"\b(test|spec|e2e|__test__|fixture|mock|stub|factory)\b"),
    # Infrastructure / CI / docker / terraform
    ("infrastructure", "infra", "Infrastructure & CI", r"\b(docker|compose|terraform|kubernetes|k8s|helm|ci|cd|pipeline|deploy|github|action|workflow)\b"),
    # Docs
    ("docs", "docs", "Documentation", r"\b(doc|readme|changelog|guide|tutorial|example|demo)\b"),
]

_COMPILED_PATTERNS: list[tuple[str, str, str, re.Pattern[str]]] = [
    (module_type, slug, name, re.compile(pattern, re.IGNORECASE))
    for module_type, slug, name, pattern in _MODULE_PATTERNS
]


def _infer_modules_from_path(rel_path_str: str) -> list[tuple[str, str, str]]:
    """Return list of (module_type, slug, name) matches for a given relative path."""
    matches = []
    for module_type, slug, name, pat in _COMPILED_PATTERNS:
        if pat.search(rel_path_str):
            matches.append((module_type, slug, name))
    return matches


# ── Scanner ───────────────────────────────────────────────────────────────────


def build_project_module_map_scan_preview(
    project_path: str,
    *,
    ignore_paths: Optional[list[str]] = None,
    max_files: int = 300,
    max_depth: int = 6,
) -> ProjectModuleMapScanPreviewResponse:
    """Build a draft module map by scanning filesystem metadata only.

    - Reads path names and directory structure only (no file contents).
    - No shell command execution, no provider, no network, no DB writes.
    - Bounded by max_files and max_depth.
    - Skips excluded directories (.git, node_modules, dist, etc.) and secret files.
    - Infers modules from path/file name patterns.

    Returns a ``ProjectModuleMapScanPreviewResponse`` — the caller must
    explicitly PUT to persist.
    """
    try:
        root = Path(project_path).expanduser().resolve(strict=True)
    except (OSError, ValueError) as exc:
        return ProjectModuleMapScanPreviewResponse(
            project_id=project_path,
            scan_summary=f"Cannot access project path: {exc}",
            warnings=[f"Cannot access project path: {exc}"],
        )

    if not root.is_dir():
        return ProjectModuleMapScanPreviewResponse(
            project_id=project_path,
            scan_summary="Project path is not a directory.",
            warnings=["Project path is not a directory."],
        )

    # Build ignore set from extra_ignore_paths (project-relative, safe strings only)
    ignore_set: set[str] = set()
    for p in (ignore_paths or []):
        # Only simple path components — no traversal
        if ".." not in p:
            ignore_set.add(p.lstrip("./").rstrip("/"))

    # Accumulate: slug → (module_type, name, paths, key_files, confidence)
    module_hits: dict[str, dict] = {}
    files_scanned = 0
    files_skipped = 0
    truncated = False

    def _register(slug: str, module_type: str, name: str, rel_str: str, is_key: bool) -> None:
        if slug not in module_hits:
            module_hits[slug] = {
                "module_type": module_type,
                "name": name,
                "paths": [],
                "key_files": [],
            }
        entry = module_hits[slug]
        # Store the parent directory as a path (first 3 levels of the hit)
        parts = Path(rel_str).parts
        dir_path = str(Path(*parts[:min(3, len(parts) - 1)])) if len(parts) > 1 else "."
        if dir_path not in entry["paths"] and len(entry["paths"]) < 20:
            entry["paths"].append(dir_path)
        if is_key and rel_str not in entry["key_files"] and len(entry["key_files"]) < 10:
            entry["key_files"].append(rel_str)

    def _is_ignored(rel_str: str) -> bool:
        for ig in ignore_set:
            if rel_str == ig or rel_str.startswith(ig + "/") or rel_str.startswith(ig + "\\"):
                return True
        return False

    def _walk(directory: Path, depth: int) -> None:
        nonlocal files_scanned, files_skipped, truncated
        if depth > max_depth:
            return
        try:
            entries = sorted(directory.iterdir())
        except (PermissionError, OSError):
            return

        for entry in entries:
            if files_scanned >= max_files:
                truncated = True
                return

            try:
                rel = entry.relative_to(root)
            except ValueError:
                continue
            rel_str = str(rel).replace("\\", "/")

            # Directory checks
            if entry.is_dir():
                if entry.name in _EXCLUDED_DIRS or _is_ignored(rel_str):
                    files_skipped += 1
                    continue
                _walk(entry, depth + 1)
                continue

            # File checks
            if not entry.is_file():
                continue
            if _is_secret_file(entry) or _is_ignored(rel_str):
                files_skipped += 1
                continue
            if _is_excluded(entry, root):
                files_skipped += 1
                continue

            files_scanned += 1

            # Infer modules from the relative path (lowercased)
            matches = _infer_modules_from_path(rel_str.lower())
            is_key = any(
                entry.name.lower() in {
                    "index.ts", "index.js", "index.py",
                    "routes.ts", "routes.py", "router.ts", "router.py",
                    "schema.prisma", "schema.sql", "models.py", "models.ts",
                    "app.py", "app.ts", "main.py", "main.ts",
                    "service.py", "service.ts", "controller.py", "controller.ts",
                }
                for _ in [None]
            )
            for module_type, slug, name in matches:
                _register(slug, module_type, name, rel_str, is_key)

    _walk(root, depth=0)

    # Build items from accumulated hits
    modules: list[ProjectModuleMapItem] = []
    for slug, data in sorted(module_hits.items()):
        confidence = "high" if len(data["paths"]) >= 3 else "medium" if len(data["paths"]) >= 1 else "low"
        modules.append(ProjectModuleMapItem(
            id=uuid.uuid4().hex[:8],
            name=data["name"],
            slug=slug,
            description="",
            module_type=data["module_type"],
            responsibilities=[],
            paths=data["paths"],
            key_files=data["key_files"],
            related_requirements=[],
            test_hints=[],
            risks=[],
            confidence=confidence,
        ))

    # Sort by module_type priority then name
    _type_order = {"backend": 0, "frontend": 1, "database": 2, "feature": 3, "shared": 4, "tests": 5, "infrastructure": 6, "docs": 7, "unknown": 8}
    modules.sort(key=lambda m: (_type_order.get(m.module_type, 9), m.name))

    summary_parts = [f"{len(modules)} module(s) inferred from {files_scanned} file(s) scanned."]
    if files_skipped:
        summary_parts.append(f"{files_skipped} file(s) skipped (excluded dirs, secret files, ignore list).")
    if truncated:
        summary_parts.append(f"Scan truncated at {max_files} files.")
    summary_parts.append("No file contents were read.")

    warnings: list[str] = []
    if truncated:
        warnings.append(f"Scan truncated: only {max_files} files examined. Increase max_files for a fuller picture.")
    if not modules:
        warnings.append("No modules were inferred — project may be empty or all files were excluded.")

    return ProjectModuleMapScanPreviewResponse(
        project_id=str(root),
        modules=modules,
        scan_summary=" ".join(summary_parts),
        files_scanned=files_scanned,
        files_skipped=files_skipped,
        truncated=truncated,
        warnings=warnings,
    )

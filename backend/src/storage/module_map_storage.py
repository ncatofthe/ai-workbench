"""Isolated storage helpers for the persistent project Module Map.

Provides CRUD operations for the ``project_module_map`` table.

Imports only from:
  - ``src.storage.database`` (connection factory, _new_id, _now)
  - ``src.models`` (module map models)

Out of scope:
  - API routing, orchestration engine, project tools, model routing
  - Tool executors, provider clients, approval execution runtime
  - Guard storage runtime
  - No shell command execution, no arbitrary commands, no provider calls
  - No auto-proposal, no auto-apply, no auto-rollback
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from src.models import (
    AgentModuleContext,
    ModuleAwareGuardPolicyResult,
    ModuleAwarenessResult,
    ProjectModuleMapDocument,
    ProjectModuleMapHistoryItem,
    ProjectModuleMapHistoryResponse,
    ProjectModuleMapItem,
    ProjectModuleMapSummaryResponse,
    ProjectModuleMapValidationResponse,
    _module_map_contains_secret,
    _module_map_path_is_safe,
    _TRAVERSAL_PATTERNS,
)
from src.storage.database import _connect


# ── Internal helpers ──────────────────────────────────────────────────────────


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now().isoformat()


def _doc_to_json(doc: ProjectModuleMapDocument) -> str:
    return json.dumps(doc.model_dump(mode="json"), ensure_ascii=False)


def _doc_from_json(raw: str, row: Any) -> ProjectModuleMapDocument:
    data = json.loads(raw) if raw else {}
    data["id"] = row["id"]
    data["project_id"] = row["project_id"]
    data["version"] = row["version"]
    data["status"] = row["status"]
    data["created_at"] = row["created_at"]
    data["updated_at"] = row["updated_at"]
    return ProjectModuleMapDocument.model_validate(data)


def _row_to_history_item(row: Any) -> ProjectModuleMapHistoryItem:
    try:
        doc_data = json.loads(row["document_json"] or "{}")
    except (ValueError, TypeError):
        doc_data = {}
    modules = doc_data.get("modules", [])
    return ProjectModuleMapHistoryItem(
        id=row["id"],
        project_id=row["project_id"],
        version=row["version"],
        status=row["status"],
        module_count=len(modules) if isinstance(modules, list) else 0,
        source=doc_data.get("source", "manual"),
        scan_summary=doc_data.get("scan_summary", ""),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
    )


# ── Next version helper ───────────────────────────────────────────────────────


def _next_version_for_project(project_id: str) -> int:
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT MAX(version) AS max_v FROM project_module_map WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        max_v = row["max_v"] if row and row["max_v"] is not None else 0
        return int(max_v) + 1
    finally:
        conn.close()


# ── CRUD ──────────────────────────────────────────────────────────────────────


def create_or_update_project_module_map(
    project_id: str,
    document: ProjectModuleMapDocument,
    *,
    archive_previous_active: bool = True,
) -> ProjectModuleMapDocument:
    """Persist a new version of a project's module map.

    If ``document.status == 'active'`` and ``archive_previous_active`` is True,
    any previously active version is archived before the new one is stored.

    Always assigns a fresh ``id`` and increments ``version``.

    No provider calls, no auto-apply, no auto-rollback.
    """
    conn = _connect()
    try:
        new_version = _next_version_for_project(project_id)
        doc_id = _new_id()
        now = _now()

        if archive_previous_active and document.status == "active":
            conn.execute(
                """
                UPDATE project_module_map
                SET status = 'archived', archived_at = ?, updated_at = ?
                WHERE project_id = ? AND status = 'active'
                """,
                (now, now, project_id),
            )

        stored = document.model_copy(
            update={
                "id": doc_id,
                "project_id": project_id,
                "version": new_version,
                "created_at": now,
                "updated_at": None,
            }
        )
        doc_json = _doc_to_json(stored)

        conn.execute(
            """
            INSERT INTO project_module_map
                (id, project_id, version, status, document_json, created_at, updated_at, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (doc_id, project_id, new_version, stored.status, doc_json, now),
        )
        conn.commit()
        return stored
    finally:
        conn.close()


def get_active_project_module_map(
    project_id: str,
) -> Optional[ProjectModuleMapDocument]:
    """Return the active (status='active') module map for the project, or None."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM project_module_map
            WHERE project_id = ? AND status = 'active'
            ORDER BY version DESC
            LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return _doc_from_json(row["document_json"], row)
    finally:
        conn.close()


def get_project_module_map_version(
    project_id: str,
    version: int,
) -> Optional[ProjectModuleMapDocument]:
    """Return a specific version of a project's module map, or None."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM project_module_map
            WHERE project_id = ? AND version = ?
            LIMIT 1
            """,
            (project_id, version),
        ).fetchone()
        if row is None:
            return None
        return _doc_from_json(row["document_json"], row)
    finally:
        conn.close()


def list_project_module_map_history(
    project_id: str,
    limit: int = 50,
) -> list[ProjectModuleMapHistoryItem]:
    """Return version history summary rows for a project, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, project_id, version, status, document_json, created_at, updated_at, archived_at
            FROM project_module_map
            WHERE project_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [_row_to_history_item(r) for r in rows]
    finally:
        conn.close()


def archive_project_module_map(
    project_id: str,
    version: Optional[int] = None,
) -> bool:
    """Archive a specific version or all active versions.

    If ``version`` is None, archives all active versions.
    Returns True if at least one row was updated.
    """
    conn = _connect()
    try:
        now = _now()
        if version is not None:
            cursor = conn.execute(
                """
                UPDATE project_module_map
                SET status = 'archived', archived_at = ?, updated_at = ?
                WHERE project_id = ? AND version = ? AND status != 'archived'
                """,
                (now, now, project_id, version),
            )
        else:
            cursor = conn.execute(
                """
                UPDATE project_module_map
                SET status = 'archived', archived_at = ?, updated_at = ?
                WHERE project_id = ? AND status = 'active'
                """,
                (now, now, project_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ── Validation ────────────────────────────────────────────────────────────────

# Max limits to keep maps bounded.
MAX_MODULES = 100
MAX_PATHS_PER_MODULE = 50
MAX_ITEMS_PER_LIST = 30


def validate_module_map_payload(
    document: ProjectModuleMapDocument,
) -> ProjectModuleMapValidationResponse:
    """Pure validation of a module map document (no DB access).

    Checks:
    - At least one module defined (warning if empty)
    - Module slugs are unique
    - Paths are safe (no traversal, no absolute, no secrets files)
    - No secret-like text in free-text fields
    - List fields are bounded
    - No duplicate module IDs
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not document.modules:
        warnings.append("Module map has no modules defined")

    if len(document.modules) > MAX_MODULES:
        errors.append(f"Too many modules: {len(document.modules)} (max {MAX_MODULES})")

    seen_ids: set[str] = set()
    seen_slugs: set[str] = set()

    for mod in document.modules:
        if mod.id in seen_ids:
            errors.append(f"Duplicate module id: {mod.id!r}")
        seen_ids.add(mod.id)

        if mod.slug in seen_slugs:
            errors.append(f"Duplicate module slug: {mod.slug!r}")
        seen_slugs.add(mod.slug)

        if not mod.name.strip():
            errors.append(f"Module {mod.id!r} has empty name")

        # Path safety checks (storage layer, in case model validators bypassed)
        for i, p in enumerate(mod.paths):
            ok, reason = _module_map_path_is_safe(p)
            if not ok:
                errors.append(f"module[{mod.id}].paths[{i}]: {reason}")

        for i, p in enumerate(mod.key_files):
            ok, reason = _module_map_path_is_safe(p)
            if not ok:
                errors.append(f"module[{mod.id}].key_files[{i}]: {reason}")

        if len(mod.paths) > MAX_PATHS_PER_MODULE:
            warnings.append(
                f"module[{mod.id}].paths has {len(mod.paths)} entries (consider trimming to {MAX_PATHS_PER_MODULE})"
            )

        # Secret-like text in list fields
        for i, text in enumerate(mod.responsibilities):
            if _module_map_contains_secret(text):
                errors.append(f"module[{mod.id}].responsibilities[{i}] must not contain secret-like values")

        for i, text in enumerate(mod.risks):
            if _module_map_contains_secret(text):
                errors.append(f"module[{mod.id}].risks[{i}] must not contain secret-like values")

        for i, text in enumerate(mod.test_hints):
            if _module_map_contains_secret(text):
                errors.append(f"module[{mod.id}].test_hints[{i}] must not contain secret-like values")

    # Ignored paths safety
    for i, p in enumerate(document.ignored_paths):
        if _TRAVERSAL_PATTERNS.search(p):
            errors.append(f"ignored_paths[{i}] contains path traversal: {p!r}")

    return ProjectModuleMapValidationResponse(
        valid=not errors,
        errors=errors,
        warnings=warnings,
    )


# ── Summary / lookup helpers ──────────────────────────────────────────────────


def build_module_map_summary(
    document: ProjectModuleMapDocument,
) -> str:
    """Return a concise human-readable summary for prompts and reports."""
    if not document.modules:
        return f"Project {document.project_id}: no modules defined (v{document.version})."
    module_names = ", ".join(m.name for m in document.modules[:10])
    extra = f" (+{len(document.modules) - 10} more)" if len(document.modules) > 10 else ""
    return (
        f"Project {document.project_id}: {len(document.modules)} module(s) — "
        f"{module_names}{extra}. "
        f"Source: {document.source}. Version: {document.version}."
    )


def find_modules_for_paths(
    document: ProjectModuleMapDocument,
    paths: list[str],
) -> list[ProjectModuleMapItem]:
    """Return modules whose paths or key_files overlap with the given file paths.

    Matching is path-prefix based (a module path 'src/auth' matches any
    requested path that starts with 'src/auth').
    Returns modules sorted by match count (most matches first).
    """
    if not paths or not document.modules:
        return []

    # Normalise to forward slashes for comparison
    norm_paths = [p.replace("\\", "/").lstrip("./") for p in paths]

    scored: list[tuple[int, ProjectModuleMapItem]] = []
    for mod in document.modules:
        score = 0
        mod_paths = [p.replace("\\", "/").lstrip("./") for p in (mod.paths + mod.key_files)]
        for mp in mod_paths:
            for rp in norm_paths:
                # Match if the module path is a prefix of the requested path, or exact
                if rp == mp or rp.startswith(mp.rstrip("/") + "/") or mp.startswith(rp.rstrip("/") + "/"):
                    score += 1
        if score > 0:
            scored.append((score, mod))

    scored.sort(key=lambda x: -x[0])
    return [mod for _, mod in scored]


def find_modules_for_requirement_ids(
    document: ProjectModuleMapDocument,
    requirement_ids: list[str],
) -> list[ProjectModuleMapItem]:
    """Return modules whose related_requirements list contains any of the given IDs."""
    if not requirement_ids or not document.modules:
        return []
    req_set = set(requirement_ids)
    return [
        mod for mod in document.modules
        if any(rid in req_set for rid in mod.related_requirements)
    ]


# ── Agent module context builder ──────────────────────────────────────────────

# Keyword → slug mappings for heuristic step-title/input matching.
# Keys are module slugs as produced by the scanner; values are keyword lists.
# All keywords are lowercased for case-insensitive matching.
_MODULE_CONTEXT_KEYWORDS: dict[str, list[str]] = {
    "auth":          ["auth", "login", "logout", "jwt", "session", "oauth", "token", "password", "credential", "sso", "identity"],
    "users":         ["user", "account", "profile", "member", "subscriber", "customer", "person"],
    "tasks":         ["task", "todo", "workflow", "ticket", "issue", "item", "job", "queue", "batch"],
    "finance":       ["finance", "billing", "payment", "invoice", "stripe", "subscription", "pricing", "charge", "credit", "wallet"],
    "reports":       ["report", "analytic", "statistic", "metric", "dashboard", "insight", "chart", "export"],
    "uploads":       ["upload", "file", "media", "attachment", "storage", "blob", "s3", "image", "asset", "document"],
    "reviews":       ["review", "approval", "approve", "reject", "feedback", "rating", "comment", "moderate"],
    "notifications": ["notification", "notify", "email", "message", "alert", "webhook", "push", "event"],
    "admin":         ["admin", "setting", "config", "configuration", "preference", "management", "control"],
    "database":      ["database", "schema", "prisma", "migration", "migrate", "seed", "sql", "model", "entity", "db", "knex", "alembic", "drizzle"],
    "api":           ["route", "controller", "service", "endpoint", "handler", "middleware", "api", "rest", "graphql", "resolver"],
    "frontend":      ["frontend", "page", "pages", "component", "components", "store", "hook", "context", "ui", "widget", "modal", "form", "nav", "sidebar"],
    "contracts":     ["type", "types", "dto", "contract", "interface", "enum", "schema", "spec", "const", "util", "helper", "lib", "common", "shared"],
    "tests":         ["test", "spec", "e2e", "fixture", "mock", "stub", "factory"],
    "infra":         ["docker", "compose", "terraform", "kubernetes", "k8s", "helm", "ci", "cd", "pipeline", "deploy"],
    "docs":          ["doc", "readme", "changelog", "guide", "tutorial", "example"],
}

# Bounds for the agent module context output.
_MODULE_CONTEXT_MAX_MODULES = 5
_MODULE_CONTEXT_MAX_PATHS = 8
_MODULE_AWARENESS_MAX_WARNINGS = 10
_MODULE_AWARENESS_MAX_HINTS = 10
_MODULE_POLICY_MAX_ITEMS = 10


def _slugs_from_text(text: str) -> set[str]:
    """Return set of module slugs whose keywords appear in the lowercased text."""
    text_lower = text.lower()
    matched: set[str] = set()
    for slug, keywords in _MODULE_CONTEXT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            matched.add(slug)
    return matched


def _module_to_compact_dict(mod: ProjectModuleMapItem) -> dict:
    """Serialize a module to a compact dict safe for agent context injection."""
    return {
        "id": mod.id,
        "name": mod.name,
        "slug": mod.slug,
        "module_type": mod.module_type,
        "description": mod.description[:200] if mod.description else "",
        "responsibilities": mod.responsibilities[:5],
        "paths": mod.paths[:_MODULE_CONTEXT_MAX_PATHS],
        "key_files": mod.key_files[:_MODULE_CONTEXT_MAX_PATHS],
        "related_requirements": mod.related_requirements[:10],
        "test_hints": mod.test_hints[:3],
        "risks": mod.risks[:3],
        "confidence": mod.confidence,
    }


def _add_unique_modules(
    selected: list[ProjectModuleMapItem],
    modules: list[ProjectModuleMapItem],
    *,
    limit: int = _MODULE_CONTEXT_MAX_MODULES,
) -> None:
    seen_ids = {mod.id for mod in selected}
    for mod in modules:
        if mod.id not in seen_ids:
            selected.append(mod)
            seen_ids.add(mod.id)
        if len(selected) >= limit:
            break


def _unique_bounded(values: list[str], limit: int) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not isinstance(value, str):
            continue
        clean = value.strip()
        if clean and clean not in seen:
            selected.append(clean)
            seen.add(clean)
        if len(selected) >= limit:
            break
    return selected


def build_patch_proposal_module_awareness(
    project_id: str,
    proposed_files: list[str],
    step_input: str = "",
    step_title: str = "",
    requirement_ids: Optional[list[str]] = None,
) -> ModuleAwarenessResult:
    """Build bounded module awareness for guarded patch proposal review.

    This is advisory context only. It performs active module-map lookup and
    deterministic matching by proposed paths, requirement IDs, and keywords.
    It does not write DB records, read file contents, create tool calls, invoke
    providers, or change guard/proposal policy.
    """
    doc = get_active_project_module_map(project_id)
    clean_files = _unique_bounded([str(path) for path in proposed_files if isinstance(path, str)], 20)
    clean_req_ids = _unique_bounded([str(rid) for rid in (requirement_ids or [])], 20)

    if doc is None:
        return ModuleAwarenessResult(
            has_active_module_map=False,
            touched_files=clean_files,
            matched_requirement_ids=clean_req_ids,
        )

    touched = find_modules_for_paths(doc, clean_files)

    expected: list[ProjectModuleMapItem] = []
    matched_req_ids: list[str] = []
    if clean_req_ids:
        req_modules = find_modules_for_requirement_ids(doc, clean_req_ids)
        if req_modules:
            matched_req_ids = clean_req_ids
        _add_unique_modules(expected, req_modules)

    if not expected:
        text_probe = f"{step_title} {step_input[:1200]}"
        matched_slugs = _slugs_from_text(text_probe)
        keyword_expected = [mod for mod in doc.modules if mod.slug in matched_slugs]
        _add_unique_modules(expected, keyword_expected)

    touched = touched[:_MODULE_CONTEXT_MAX_MODULES]
    expected = expected[:_MODULE_CONTEXT_MAX_MODULES]

    touched_ids = {mod.id for mod in touched}
    expected_ids = {mod.id for mod in expected}

    warnings: list[str] = []
    if clean_files and not touched:
        warnings.append("Proposed files do not match any known module.")
    if touched and expected and not touched_ids.intersection(expected_ids):
        warnings.append("Touched modules do not overlap expected modules from step requirements/module map.")
    if expected and not touched:
        warnings.append("Proposal does not touch any module expected from step requirements/module map.")

    sensitive_words = ("auth", "security", "database", "db", "migration", "schema")
    for mod in touched:
        if mod.risks:
            warnings.append(f"Touched module '{mod.name}' has recorded risks.")
        sensitive_probe = " ".join([mod.name, mod.slug, mod.module_type]).lower()
        if any(word in sensitive_probe for word in sensitive_words):
            warnings.append(f"Proposal touches sensitive module '{mod.name}'.")

    expected_files = _unique_bounded(
        [
            path
            for mod in (expected or touched)
            for path in (mod.key_files[:_MODULE_CONTEXT_MAX_PATHS] + mod.paths[:_MODULE_CONTEXT_MAX_PATHS])
        ],
        _MODULE_CONTEXT_MAX_PATHS * 2,
    )
    module_risks = _unique_bounded(
        [risk for mod in (touched + expected) for risk in mod.risks],
        _MODULE_AWARENESS_MAX_HINTS,
    )
    module_test_hints = _unique_bounded(
        [hint for mod in (touched + expected) for hint in mod.test_hints],
        _MODULE_AWARENESS_MAX_HINTS,
    )

    confidence = "low"
    if touched and expected and touched_ids.intersection(expected_ids):
        confidence = "high"
    elif touched or expected:
        confidence = "medium"

    return ModuleAwarenessResult(
        has_active_module_map=True,
        module_map_version=doc.version,
        touched_modules=[_module_to_compact_dict(mod) for mod in touched],
        expected_modules=[_module_to_compact_dict(mod) for mod in expected],
        touched_files=clean_files,
        expected_files=expected_files,
        matched_requirement_ids=matched_req_ids,
        module_risks=module_risks,
        module_test_hints=module_test_hints,
        warnings=_unique_bounded(warnings, _MODULE_AWARENESS_MAX_WARNINGS),
        confidence=confidence,
    )


def _module_label(module: dict) -> str:
    return str(module.get("name") or module.get("slug") or module.get("id") or "unknown")


def _module_is_sensitive(module: dict) -> bool:
    probe = " ".join(
        str(module.get(key) or "")
        for key in ("name", "slug", "module_type", "description")
    ).lower()
    return any(
        marker in probe
        for marker in (
            "auth",
            "security",
            "database",
            "db",
            "migration",
            "schema",
            "env",
            "secret",
            "provider",
            "runtime",
            "execution",
            "config",
        )
    )


def _path_matches_module(path: str, module: dict) -> bool:
    norm_path = path.replace("\\", "/").lstrip("./").lower()
    module_paths = [
        str(value).replace("\\", "/").lstrip("./").lower()
        for value in (module.get("paths") or []) + (module.get("key_files") or [])
        if isinstance(value, str)
    ]
    for module_path in module_paths:
        if (
            norm_path == module_path
            or norm_path.startswith(module_path.rstrip("/") + "/")
            or module_path.startswith(norm_path.rstrip("/") + "/")
        ):
            return True
    return False


def _path_is_suspicious(path: str) -> bool:
    probe = path.replace("\\", "/").lower()
    return any(
        marker in probe
        for marker in (
            ".env",
            "secret",
            "private",
            "credential",
            "credentials",
            "key",
        )
    )


def evaluate_module_aware_guard_policy(
    module_awareness: ModuleAwarenessResult,
    proposed_files: list[str],
    has_guard_result: bool,
    no_guard_override: bool = False,
) -> ModuleAwareGuardPolicyResult:
    """Classify module-related proposal risk without changing guard policy.

    The result is advisory in v1: it is stored/displayed with the proposal but
    does not authorize, block, apply, execute commands, or call providers.
    """
    clean_files = _unique_bounded([str(path) for path in proposed_files if isinstance(path, str)], 20)

    if not module_awareness.has_active_module_map:
        return ModuleAwareGuardPolicyResult(
            verdict="allowed",
            reasons=["No active module map is available; module policy is neutral."],
            unknown_files=[],
            recommended_tests=[],
            confidence="low",
        )

    touched = module_awareness.touched_modules
    expected = module_awareness.expected_modules
    touched_ids = {str(mod.get("id") or mod.get("slug") or _module_label(mod)) for mod in touched}
    expected_ids = {str(mod.get("id") or mod.get("slug") or _module_label(mod)) for mod in expected}
    overlap = bool(touched_ids.intersection(expected_ids))

    affected_modules = _unique_bounded([_module_label(mod) for mod in touched], _MODULE_POLICY_MAX_ITEMS)
    sensitive_modules = _unique_bounded(
        [_module_label(mod) for mod in touched if _module_is_sensitive(mod)],
        _MODULE_POLICY_MAX_ITEMS,
    )
    unknown_files = _unique_bounded(
        [
            path
            for path in clean_files
            if not any(_path_matches_module(path, mod) for mod in touched)
        ],
        _MODULE_POLICY_MAX_ITEMS,
    )

    reasons: list[str] = []
    required_acknowledgements: list[str] = []
    verdict = "allowed"

    if not expected:
        reasons.append("Active module map exists but no expected modules were identified from step requirements.")
        verdict = "warning"
        required_acknowledgements.append("Review whether the proposal belongs to the intended project module.")

    if unknown_files:
        reasons.append("Proposal includes files that do not match known modules.")
        verdict = "warning"
        required_acknowledgements.append("Confirm unknown files are intended and safe.")

    if touched and expected and not overlap:
        reasons.append("Touched modules do not overlap expected modules.")
        verdict = "warning"
        required_acknowledgements.append("Confirm the module mismatch is intentional.")

    if module_awareness.module_risks:
        reasons.append("Touched module has recorded risks.")
        verdict = "warning"
        required_acknowledgements.append("Review module risks before applying any patch.")

    if sensitive_modules and (not expected or not overlap):
        reasons.append("Sensitive module touched without matching expected module context.")
        verdict = "blocked"
        required_acknowledgements.append("Run a fresh source-of-truth guard or confirm supporting requirement context.")

    suspicious_unknown = [path for path in unknown_files if _path_is_suspicious(path)]
    if suspicious_unknown:
        reasons.append("Unknown file path appears secret/config sensitive.")
        verdict = "blocked"
        required_acknowledgements.append("Do not proceed until the sensitive path is reviewed explicitly.")

    sensitive_without_guard = sensitive_modules and not has_guard_result and not no_guard_override
    if sensitive_without_guard:
        reasons.append("Sensitive module proposal has no selected guard result or explicit no-guard override.")
        verdict = "blocked"
        required_acknowledgements.append("Select a valid guard result or use an explicit no-guard override.")

    for warning in module_awareness.warnings:
        if warning not in reasons:
            reasons.append(warning)
        if verdict == "allowed":
            verdict = "warning"

    confidence = module_awareness.confidence or "medium"
    if verdict == "blocked":
        confidence = "high"

    return ModuleAwareGuardPolicyResult(
        verdict=verdict,
        reasons=_unique_bounded(reasons, _MODULE_POLICY_MAX_ITEMS),
        required_acknowledgements=_unique_bounded(required_acknowledgements, _MODULE_POLICY_MAX_ITEMS),
        affected_modules=affected_modules,
        sensitive_modules=sensitive_modules,
        unknown_files=unknown_files,
        recommended_tests=_unique_bounded(module_awareness.module_test_hints, _MODULE_POLICY_MAX_ITEMS),
        confidence=confidence,
    )


def build_agent_module_context_for_step(
    project_id: str,
    step_input: str = "",
    step_title: str = "",
    requirement_ids: Optional[list[str]] = None,
) -> AgentModuleContext:
    """Build a compact, read-only module context for agent execution.

    Resolves the active module map for the project and selects relevant modules
    using requirement ID matching and keyword heuristics on step title/input.

    Pure read — no DB writes, no provider calls, no file reads, no scan.
    Returns an AgentModuleContext with has_active_module_map=False if no map exists.
    """
    doc = get_active_project_module_map(project_id)

    if doc is None:
        return AgentModuleContext(
            project_id=project_id,
            has_active_module_map=False,
        )

    # 1. Match by requirement IDs (highest priority).
    req_matched: list[ProjectModuleMapItem] = []
    matched_req_ids: list[str] = []
    if requirement_ids:
        req_matched = find_modules_for_requirement_ids(doc, requirement_ids)
        if req_matched:
            matched_req_ids = list(requirement_ids)

    # 2. Match by keyword heuristics on step title + first 800 chars of input.
    text_probe = f"{step_title} {step_input[:800]}"
    matched_slugs = _slugs_from_text(text_probe)
    keyword_matched: list[ProjectModuleMapItem] = [
        m for m in doc.modules if m.slug in matched_slugs
        and m not in req_matched
    ]

    # 3. Combine and cap.
    combined = (req_matched + keyword_matched)[:_MODULE_CONTEXT_MAX_MODULES]

    # 4. Fallback: if nothing matched, include high-confidence modules (up to cap).
    if not combined:
        high_conf = [m for m in doc.modules if m.confidence == "high"]
        combined = high_conf[:_MODULE_CONTEXT_MAX_MODULES]
        if not combined:
            combined = doc.modules[:_MODULE_CONTEXT_MAX_MODULES]

    # 5. Collect matched paths.
    matched_paths: list[str] = []
    seen_paths: set[str] = set()
    for mod in combined:
        for p in (mod.paths + mod.key_files)[:_MODULE_CONTEXT_MAX_PATHS]:
            if p not in seen_paths:
                matched_paths.append(p)
                seen_paths.add(p)
        if len(matched_paths) >= _MODULE_CONTEXT_MAX_PATHS * 2:
            break

    return AgentModuleContext(
        project_id=project_id,
        module_map_version=doc.version,
        has_active_module_map=True,
        matched_modules=[_module_to_compact_dict(m) for m in combined],
        module_summary=build_module_map_summary(doc),
        matched_paths=matched_paths,
        matched_requirement_ids=matched_req_ids,
    )


def build_patch_draft_module_context(
    project_id: str,
    agent_result: Any,
    step_input: str = "",
    step_title: str = "",
    requirement_ids: Optional[list[str]] = None,
) -> AgentModuleContext:
    """Build compact module-map context for Agent Result → Patch Draft.

    Selection order is deterministic:
    1. proposed_files path/key_file overlap
    2. requirement IDs
    3. keyword heuristics on agent result text + step title/input
    4. high-confidence/fallback modules

    Pure read — no DB writes, no file reads, no tool calls, no providers.
    """
    doc = get_active_project_module_map(project_id)
    if doc is None:
        return AgentModuleContext(
            project_id=project_id,
            has_active_module_map=False,
        )

    proposed_files = [
        str(path)
        for path in getattr(agent_result, "proposed_files", []) or []
        if isinstance(path, str)
    ][:20]

    selected: list[ProjectModuleMapItem] = []

    def add_modules(modules: list[ProjectModuleMapItem]) -> None:
        seen_ids = {mod.id for mod in selected}
        for mod in modules:
            if mod.id not in seen_ids:
                selected.append(mod)
                seen_ids.add(mod.id)
            if len(selected) >= _MODULE_CONTEXT_MAX_MODULES:
                break

    add_modules(find_modules_for_paths(doc, proposed_files))

    matched_req_ids: list[str] = []
    if len(selected) < _MODULE_CONTEXT_MAX_MODULES and requirement_ids:
        req_matched = find_modules_for_requirement_ids(doc, requirement_ids)
        if req_matched:
            matched_req_ids = list(requirement_ids)
        add_modules(req_matched)

    if len(selected) < _MODULE_CONTEXT_MAX_MODULES:
        text_probe = " ".join(
            [
                step_title,
                step_input[:800],
                str(getattr(agent_result, "summary", "") or ""),
                str(getattr(agent_result, "analysis", "") or "")[:1200],
                str(getattr(agent_result, "patch_intent", "") or ""),
            ]
        )
        matched_slugs = _slugs_from_text(text_probe)
        keyword_matched = [m for m in doc.modules if m.slug in matched_slugs]
        add_modules(keyword_matched)

    if not selected:
        add_modules([m for m in doc.modules if m.confidence == "high"])
    if not selected:
        add_modules(doc.modules)

    selected = selected[:_MODULE_CONTEXT_MAX_MODULES]

    matched_paths: list[str] = []
    seen_paths: set[str] = set()
    for mod in selected:
        for p in (mod.paths[:_MODULE_CONTEXT_MAX_PATHS] + mod.key_files[:_MODULE_CONTEXT_MAX_PATHS]):
            if p not in seen_paths:
                matched_paths.append(p)
                seen_paths.add(p)
        if len(matched_paths) >= _MODULE_CONTEXT_MAX_PATHS * 2:
            break

    return AgentModuleContext(
        project_id=project_id,
        module_map_version=doc.version,
        has_active_module_map=True,
        matched_modules=[_module_to_compact_dict(m) for m in selected],
        module_summary=build_module_map_summary(doc),
        matched_paths=matched_paths,
        matched_requirement_ids=matched_req_ids,
    )

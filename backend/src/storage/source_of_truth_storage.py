"""Isolated storage helpers for the persistent project Source of Truth.

Provides CRUD operations for the ``project_source_of_truth`` table.

Imports only from:
  - ``src.storage.database`` (connection factory, _new_id, _now)
  - ``src.models`` (flat SoT document models)

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
    ProjectSourceOfTruthDocument,
    ProjectSourceOfTruthRequirement,
    ProjectSourceOfTruthDecision,
    SourceOfTruthHistoryItem,
    SourceOfTruthValidationResponse,
    SourceOfTruthSummaryResponse,
    _sot_contains_secret,
)
from src.storage.database import _connect


# ── Internal helpers ──────────────────────────────────────────────────────────


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now().isoformat()


def _doc_to_json(doc: ProjectSourceOfTruthDocument) -> str:
    return json.dumps(doc.model_dump(mode="json"), ensure_ascii=False)


def _doc_from_json(raw: str, row: Any) -> ProjectSourceOfTruthDocument:
    data = json.loads(raw) if raw else {}
    # Ensure top-level DB fields override any stale values in the JSON blob
    data["id"] = row["id"]
    data["project_id"] = row["project_id"]
    data["version"] = row["version"]
    data["status"] = row["status"]
    data["created_at"] = row["created_at"]
    data["updated_at"] = row["updated_at"]
    return ProjectSourceOfTruthDocument.model_validate(data)


def _row_to_history_item(row: Any) -> SourceOfTruthHistoryItem:
    try:
        doc_data = json.loads(row["document_json"] or "{}")
    except (ValueError, TypeError):
        doc_data = {}
    return SourceOfTruthHistoryItem(
        id=row["id"],
        project_id=row["project_id"],
        version=row["version"],
        status=row["status"],
        product_name=doc_data.get("product_name", ""),
        source=doc_data.get("source", "manual"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        archived_at=row["archived_at"],
    )


# ── Next version helper ───────────────────────────────────────────────────────


def _next_version_for_project(project_id: str) -> int:
    """Return the next version number for a project's SoT documents."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT MAX(version) AS max_v FROM project_source_of_truth WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        max_v = row["max_v"] if row and row["max_v"] is not None else 0
        return int(max_v) + 1
    finally:
        conn.close()


# ── CRUD ──────────────────────────────────────────────────────────────────────


def create_or_update_project_source_of_truth(
    project_id: str,
    document: ProjectSourceOfTruthDocument,
    *,
    archive_previous_active: bool = True,
) -> ProjectSourceOfTruthDocument:
    """Persist a new version of a project's Source of Truth document.

    If ``document.status == 'active'`` and ``archive_previous_active`` is True,
    any previously active version is archived before the new one is stored.

    Always assigns a fresh ``id`` and increments ``version`` (ignoring any
    version the caller set on the document).

    No provider calls, no auto-apply, no auto-rollback.
    """
    conn = _connect()
    try:
        new_version = _next_version_for_project(project_id)
        doc_id = _new_id()
        now = _now()

        # Archive the previous active version if requested
        if archive_previous_active and document.status == "active":
            conn.execute(
                """
                UPDATE project_source_of_truth
                SET status = 'archived', archived_at = ?, updated_at = ?
                WHERE project_id = ? AND status = 'active'
                """,
                (now, now, project_id),
            )

        # Build the stored document with correct metadata
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
            INSERT INTO project_source_of_truth
                (id, project_id, version, status, document_json, created_at, updated_at, archived_at)
            VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (doc_id, project_id, new_version, stored.status, doc_json, now),
        )
        conn.commit()
        return stored
    finally:
        conn.close()


def get_active_project_source_of_truth(
    project_id: str,
) -> Optional[ProjectSourceOfTruthDocument]:
    """Return the active (status='active') SoT document for the project, or None."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM project_source_of_truth
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


def get_latest_project_source_of_truth(
    project_id: str,
) -> Optional[ProjectSourceOfTruthDocument]:
    """Return the most recent SoT document for the project regardless of status."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM project_source_of_truth
            WHERE project_id = ?
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


def get_project_source_of_truth_version(
    project_id: str,
    version: int,
) -> Optional[ProjectSourceOfTruthDocument]:
    """Return a specific version of a project's SoT document, or None."""
    conn = _connect()
    try:
        row = conn.execute(
            """
            SELECT * FROM project_source_of_truth
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


def list_project_source_of_truth_history(
    project_id: str,
    limit: int = 50,
) -> list[SourceOfTruthHistoryItem]:
    """Return version history summary rows for a project, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """
            SELECT id, project_id, version, status, document_json, created_at, updated_at, archived_at
            FROM project_source_of_truth
            WHERE project_id = ?
            ORDER BY version DESC
            LIMIT ?
            """,
            (project_id, limit),
        ).fetchall()
        return [_row_to_history_item(r) for r in rows]
    finally:
        conn.close()


def archive_project_source_of_truth(
    project_id: str,
    version: int,
) -> bool:
    """Archive a specific version. Returns True if a row was updated."""
    conn = _connect()
    try:
        now = _now()
        cursor = conn.execute(
            """
            UPDATE project_source_of_truth
            SET status = 'archived', archived_at = ?, updated_at = ?
            WHERE project_id = ? AND version = ? AND status != 'archived'
            """,
            (now, now, project_id, version),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ── Validation ────────────────────────────────────────────────────────────────


def validate_source_of_truth_payload(
    document: ProjectSourceOfTruthDocument,
) -> SourceOfTruthValidationResponse:
    """Pure validation of a SoT document (no DB access).

    Checks:
    - product_summary or project_intent is present
    - At least one requirement with priority 'must' exists (if requirements provided)
    - No secret-like values in free-text fields
    - No duplicate requirement ids
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not document.product_summary.strip() and not document.project_intent.strip():
        errors.append("product_summary or project_intent is required")

    if not document.target_users:
        warnings.append("target_users is empty")

    if document.requirements:
        req_ids = [r.id for r in document.requirements]
        seen: set[str] = set()
        for rid in req_ids:
            if rid in seen:
                errors.append(f"Duplicate requirement id: {rid}")
            seen.add(rid)

        has_must = any(r.priority == "must" for r in document.requirements)
        if not has_must:
            warnings.append("No requirement with priority 'must' found")

    # Secret checks on document-level list fields
    for field_name, values in [
        ("constraints", document.constraints),
        ("forbidden_changes", document.forbidden_changes),
        ("goals", document.goals),
        ("assumptions", document.assumptions),
        ("risks", document.risks),
        ("open_questions", document.open_questions),
        ("acceptance_criteria", document.acceptance_criteria),
    ]:
        for i, val in enumerate(values):
            if isinstance(val, str) and _sot_contains_secret(val):
                errors.append(f"{field_name}[{i}] must not contain secret-like values")

    # Secret checks on per-requirement nested list fields (P2 fix)
    for req in document.requirements:
        for field_name, values in [
            (f"requirements[{req.id}].acceptance_criteria", req.acceptance_criteria),
            (f"requirements[{req.id}].constraints", req.constraints),
        ]:
            for i, val in enumerate(values):
                if isinstance(val, str) and _sot_contains_secret(val):
                    errors.append(f"{field_name}[{i}] must not contain secret-like values")

    drift_risk = "critical" if errors else "medium" if warnings else "low"
    return SourceOfTruthValidationResponse(
        valid=not errors,
        drift_risk=drift_risk,
        errors=errors,
        warnings=warnings,
    )


# ── Summary / requirement context ─────────────────────────────────────────────


def build_source_of_truth_summary(
    document: ProjectSourceOfTruthDocument,
) -> str:
    """Return a concise human-readable summary for reports and prompts."""
    must_reqs = [r for r in document.requirements if r.priority == "must"]
    name = document.product_name or document.project_id
    goal = document.product_summary or document.project_intent or "no summary"
    return (
        f"{name}: {goal}. "
        f"{len(document.target_users)} target user(s), "
        f"{len(document.requirements)} requirement(s) "
        f"({len(must_reqs)} mandatory), "
        f"{len(document.acceptance_criteria)} acceptance criteria."
    )


def extract_requirement_context_for_step(
    document: ProjectSourceOfTruthDocument,
    *,
    requirement_ids: Optional[list[str]] = None,
) -> str:
    """Build an AI_WORKBENCH_REQUIREMENT_CONTEXT block from the active SoT document.

    Compatible with the block format produced by
    ``project_intake.format_confirmed_run_step_requirement_context`` and
    consumed by ``project_intake.parse_run_step_requirement_context``.

    ``requirement_ids`` filters which requirements' acceptance criteria and
    constraints are included; if None, all requirements are included.
    """
    selected_reqs: list[ProjectSourceOfTruthRequirement] = (
        [r for r in document.requirements if r.id in (requirement_ids or [])]
        if requirement_ids
        else document.requirements
    )

    req_id_lines = "\n".join(f"- {r.id}" for r in selected_reqs) or "- (none)"

    criteria: list[str] = list(document.acceptance_criteria)
    for r in selected_reqs:
        criteria.extend(r.acceptance_criteria)
    criteria_lines = "\n".join(f"- {c}" for c in criteria) or "- (none)"

    constraints: list[str] = list(document.constraints)
    for r in selected_reqs:
        constraints.extend(r.constraints)
    constraints_lines = "\n".join(f"- {c}" for c in constraints) or "- (none)"

    forbidden_lines = (
        "\n".join(f"- {f}" for f in document.forbidden_changes) or "- (none)"
    )

    summary = build_source_of_truth_summary(document)
    validation = validate_source_of_truth_payload(document)
    drift_risk = validation.drift_risk
    coverage_status = "active" if document.status == "active" else "draft"

    return (
        "AI_WORKBENCH_REQUIREMENT_CONTEXT:\n"
        f"requirement_ids:\n{req_id_lines}\n"
        f"coverage_status: {coverage_status}\n"
        f"drift_risk: {drift_risk}\n"
        f"acceptance_criteria:\n{criteria_lines}\n"
        f"constraints:\n{constraints_lines}\n"
        f"forbidden_changes:\n{forbidden_lines}\n"
        "validation_notes:\n"
        + (
            "\n".join(f"- {e}" for e in validation.errors + validation.warnings)
            or "- (none)"
        )
        + f"\nsource_of_truth_summary: {summary}\n"
        "END_AI_WORKBENCH_REQUIREMENT_CONTEXT"
    )


def build_persisted_source_of_truth_context_for_step(
    project_id: str,
    requirement_ids: Optional[list[str]] = None,
) -> Optional[str]:
    """Return an AI_WORKBENCH_REQUIREMENT_CONTEXT block from the active persisted SoT.

    Returns None if no active SoT exists for the project.

    Behavior:
    - Looks up the active (status='active') SoT document for project_id.
    - If found, calls extract_requirement_context_for_step to build the block.
    - requirement_ids filters which requirements are included; None = all.
    - No provider calls, no DB writes, no run mutation.

    Compatible with parse_run_step_requirement_context in project_intake.py.
    """
    document = get_active_project_source_of_truth(project_id)
    if document is None:
        return None
    return extract_requirement_context_for_step(document, requirement_ids=requirement_ids)

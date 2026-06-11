"""Isolated storage helpers for Source-of-Truth Guard Results.

This module provides CRUD operations for the guard_results table.
It imports only from database.py (connection factory) and the
guard_result_storage_contract (pure models).

It keeps API routing, orchestration engine, project tools, model routing,
tool executors, and provider clients out of scope.  It does not create
tool_calls, execute tools, apply patches, or run providers.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardInputSnapshot,
    WorkflowGuardRequirementContextSnapshot,
    WorkflowGuardResultRecord,
    WorkflowGuardResultSnapshot,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    _dedupe_reasons,
)
from src.storage.database import _connect


# ── Serialization helpers ───────────────────────────────────────────────────


def _serialize_snapshot(model: object) -> str:
    """Serialize a Pydantic model to a JSON string for storage."""
    if hasattr(model, "model_dump"):
        return json.dumps(model.model_dump(mode="json"), ensure_ascii=False)
    raise TypeError(f"Cannot serialize {type(model)}")


def _deserialize_input_snapshot(raw: str) -> WorkflowGuardInputSnapshot:
    return WorkflowGuardInputSnapshot.model_validate(json.loads(raw))


def _deserialize_requirement_context_snapshot(
    raw: str,
) -> WorkflowGuardRequirementContextSnapshot:
    return WorkflowGuardRequirementContextSnapshot.model_validate(json.loads(raw))


def _deserialize_result_snapshot(raw: str) -> WorkflowGuardResultSnapshot:
    return WorkflowGuardResultSnapshot.model_validate(json.loads(raw))


def _deserialize_stale_reasons(raw: str) -> list[WorkflowGuardStaleReason]:
    values = json.loads(raw) if raw else []
    return [WorkflowGuardStaleReason(v) for v in values]


def _serialize_stale_reasons(reasons: list[WorkflowGuardStaleReason]) -> str:
    return json.dumps([r.value for r in reasons], ensure_ascii=False)


def _parse_optional_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _format_optional_datetime(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _now_iso() -> str:
    return datetime.now().isoformat()


def _record_from_row(row: dict) -> WorkflowGuardResultRecord:
    """Reconstruct a WorkflowGuardResultRecord from a sqlite3.Row dict."""
    return WorkflowGuardResultRecord(
        id=row["id"],
        project_id=row["project_id"] or None,
        run_id=row["run_id"],
        step_id=row["step_id"],
        proposal_tool_call_id=row["proposal_tool_call_id"] or None,
        apply_tool_call_id=row["apply_tool_call_id"] or None,
        source=WorkflowGuardSource(row["source"]),
        input_snapshot=_deserialize_input_snapshot(row["input_snapshot_json"]),
        requirement_context_snapshot=_deserialize_requirement_context_snapshot(
            row["requirement_context_snapshot_json"]
        ),
        result_snapshot=_deserialize_result_snapshot(row["result_snapshot_json"]),
        warning_acknowledged=bool(row["warning_acknowledged"]),
        no_guard_override=bool(row["no_guard_override"]),
        is_stale=bool(row["is_stale"]),
        stale_reasons=_deserialize_stale_reasons(row["stale_reasons_json"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=_parse_optional_datetime(row["updated_at"]),
        expires_at=_parse_optional_datetime(row["expires_at"]),
    )


# ── CRUD helpers ────────────────────────────────────────────────────────────


def create_guard_result(
    record: WorkflowGuardResultRecord,
) -> WorkflowGuardResultRecord:
    """Persist a guard result record.  Returns the stored record."""
    conn = _connect()
    conn.execute(
        """
        INSERT INTO guard_results (
            id, project_id, run_id, step_id,
            proposal_tool_call_id, apply_tool_call_id,
            source, decision, drift_risk,
            input_snapshot_json, requirement_context_snapshot_json,
            result_snapshot_json,
            warning_acknowledged, no_guard_override,
            is_stale, stale_reasons_json,
            created_at, updated_at, expires_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record.id,
            record.project_id or "",
            record.run_id,
            record.step_id,
            record.proposal_tool_call_id or "",
            record.apply_tool_call_id or "",
            record.source.value if isinstance(record.source, WorkflowGuardSource) else str(record.source),
            record.result_snapshot.decision.value if isinstance(record.result_snapshot.decision, WorkflowGuardDecision) else str(record.result_snapshot.decision),
            record.result_snapshot.drift_risk.value if isinstance(record.result_snapshot.drift_risk, WorkflowGuardDriftRisk) else str(record.result_snapshot.drift_risk),
            _serialize_snapshot(record.input_snapshot),
            _serialize_snapshot(record.requirement_context_snapshot),
            _serialize_snapshot(record.result_snapshot),
            int(record.warning_acknowledged),
            int(record.no_guard_override),
            int(record.is_stale),
            _serialize_stale_reasons(record.stale_reasons),
            record.created_at.isoformat() if isinstance(record.created_at, datetime) else str(record.created_at),
            _format_optional_datetime(record.updated_at),
            _format_optional_datetime(record.expires_at),
        ),
    )
    conn.commit()
    conn.close()
    return get_guard_result(record.id) or record


def get_guard_result(guard_result_id: str) -> Optional[WorkflowGuardResultRecord]:
    """Fetch a single guard result by ID.  Returns None if not found."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM guard_results WHERE id=?", (guard_result_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _record_from_row(row)


def list_guard_results(
    *,
    run_id: Optional[str] = None,
    step_id: Optional[str] = None,
    project_id: Optional[str] = None,
    proposal_tool_call_id: Optional[str] = None,
    decision: Optional[str] = None,
    include_stale: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[WorkflowGuardResultRecord]:
    """List guard results with optional filters."""
    clauses: list[str] = []
    params: list[object] = []

    if run_id is not None:
        clauses.append("run_id = ?")
        params.append(run_id)
    if step_id is not None:
        clauses.append("step_id = ?")
        params.append(step_id)
    if project_id is not None:
        clauses.append("project_id = ?")
        params.append(project_id)
    if proposal_tool_call_id is not None:
        clauses.append("proposal_tool_call_id = ?")
        params.append(proposal_tool_call_id)
    if decision is not None:
        clauses.append("decision = ?")
        params.append(decision)
    if not include_stale:
        clauses.append("is_stale = 0")

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    sql = f"SELECT * FROM guard_results {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    conn = _connect()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_record_from_row(row) for row in rows]


def mark_guard_result_stale(
    guard_result_id: str,
    reason: WorkflowGuardStaleReason,
    note: Optional[str] = None,
) -> Optional[WorkflowGuardResultRecord]:
    """Mark a guard result as stale.  Staleness is irreversible."""
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM guard_results WHERE id=?", (guard_result_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    existing_reasons = _deserialize_stale_reasons(row["stale_reasons_json"])
    new_reasons = _dedupe_reasons([*existing_reasons, reason])
    now = _now_iso()

    conn.execute(
        """
        UPDATE guard_results
        SET is_stale = 1,
            stale_reasons_json = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (_serialize_stale_reasons(new_reasons), now, guard_result_id),
    )
    conn.commit()
    conn.close()
    return get_guard_result(guard_result_id)


def link_guard_result_to_proposal(
    guard_result_id: str,
    proposal_tool_call_id: str,
) -> Optional[WorkflowGuardResultRecord]:
    """Link a guard result to a proposal tool_call.

    This only stores the link — it does NOT create tool_calls,
    execute tools, or apply patches.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM guard_results WHERE id=?", (guard_result_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    conn.execute(
        """
        UPDATE guard_results
        SET proposal_tool_call_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (proposal_tool_call_id, _now_iso(), guard_result_id),
    )
    conn.commit()
    conn.close()
    return get_guard_result(guard_result_id)


def link_guard_result_to_apply(
    guard_result_id: str,
    apply_tool_call_id: str,
) -> Optional[WorkflowGuardResultRecord]:
    """Link a guard result to an apply tool_call.

    This only stores the link — it does NOT create tool_calls,
    execute tools, or apply patches.
    """
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM guard_results WHERE id=?", (guard_result_id,)
    ).fetchone()
    if not row:
        conn.close()
        return None

    conn.execute(
        """
        UPDATE guard_results
        SET apply_tool_call_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (apply_tool_call_id, _now_iso(), guard_result_id),
    )
    conn.commit()
    conn.close()
    return get_guard_result(guard_result_id)

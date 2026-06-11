"""SQLite storage layer for AI Workbench."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from src.models import (
    ApprovalRequest,
    ApprovalStatus,
    ModelRouteDecision,
    Project,
    Run,
    RunAgentAssignment,
    RunStatus,
    RunStep,
    ToolCall,
)
from src.utils.paths import PROJECT_ROOT, repo_path, resolve_runtime_path

DB_PATH = str(resolve_runtime_path(os.environ.get("WORKBENCH_DB"), "data/workbench.db"))
PROJECT_LIST_FIELDS = ("safe_commands", "blocked_commands", "ignore_paths")


# ── Connection / init ────────────────────────────────────────────────────────

def _db_path() -> Path:
    return resolve_runtime_path(DB_PATH, "data/workbench.db")


def _ensure_db_dir() -> None:
    _db_path().parent.mkdir(parents=True, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_db_dir()
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _add_missing_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def init_db() -> None:
    """Create or migrate SQLite tables used by AI Workbench."""
    conn = _connect()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT DEFAULT '',
            description TEXT DEFAULT '',
            stack TEXT DEFAULT '',
            package_manager TEXT DEFAULT '',
            test_command TEXT DEFAULT '',
            build_command TEXT DEFAULT '',
            safe_commands TEXT DEFAULT '[]',
            blocked_commands TEXT DEFAULT '[]',
            ignore_paths TEXT DEFAULT '[]',
            updated_at TEXT,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            task_id TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            project_path TEXT DEFAULT '',
            current_step_id TEXT DEFAULT '',
            agent_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            mode TEXT DEFAULT 'offline',
            prompt TEXT DEFAULT '',
            plan TEXT DEFAULT '',
            result TEXT DEFAULT '',
            logs TEXT DEFAULT '[]',
            artifacts TEXT DEFAULT '[]',
            run_dir TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            finished_at TEXT
        );

        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            action TEXT NOT NULL,
            command TEXT DEFAULT '',
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            artifact_type TEXT DEFAULT 'file',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS run_steps (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            parent_step_id TEXT DEFAULT '',
            agent_id TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            title TEXT DEFAULT '',
            input TEXT DEFAULT '',
            output TEXT DEFAULT '',
            error TEXT DEFAULT '',
            started_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tool_calls (
            id TEXT PRIMARY KEY,
            run_id TEXT DEFAULT '',
            project_id TEXT DEFAULT '',
            step_id TEXT DEFAULT '',
            tool_name TEXT NOT NULL,
            command TEXT DEFAULT '',
            cwd TEXT DEFAULT '',
            status TEXT DEFAULT '',
            approval_id TEXT DEFAULT '',
            stdout TEXT DEFAULT '',
            stderr TEXT DEFAULT '',
            returncode INTEGER,
            report_path TEXT DEFAULT '',
            started_at TEXT DEFAULT '',
            finished_at TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            input_json TEXT DEFAULT '',
            output_json TEXT DEFAULT '',
            error TEXT DEFAULT '',
            risk_level TEXT DEFAULT 'low',
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS run_agent_assignments (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            assigned_role TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            confidence REAL DEFAULT 0,
            status TEXT DEFAULT 'selected',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS model_route_decisions (
            id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            step_id TEXT,
            agent_id TEXT NOT NULL,
            task_type TEXT NOT NULL,
            model_profile TEXT NOT NULL,
            selected_model TEXT NOT NULL,
            selected_provider TEXT NOT NULL,
            fallback_model TEXT DEFAULT '',
            fallback_provider TEXT,
            provider_mode TEXT DEFAULT 'local',
            reason TEXT DEFAULT '',
            confidence REAL DEFAULT 0,
            warnings TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_model_route_decisions_run
            ON model_route_decisions (run_id, agent_id, task_type);
        CREATE INDEX IF NOT EXISTS idx_model_route_decisions_step
            ON model_route_decisions (run_id, step_id);

        CREATE TABLE IF NOT EXISTS guard_results (
            id TEXT PRIMARY KEY,
            project_id TEXT,
            run_id TEXT NOT NULL,
            step_id TEXT NOT NULL,
            proposal_tool_call_id TEXT,
            apply_tool_call_id TEXT,
            source TEXT NOT NULL,
            decision TEXT NOT NULL,
            drift_risk TEXT NOT NULL,
            input_snapshot_json TEXT NOT NULL,
            requirement_context_snapshot_json TEXT NOT NULL,
            result_snapshot_json TEXT NOT NULL,
            warning_acknowledged INTEGER NOT NULL DEFAULT 0,
            no_guard_override INTEGER NOT NULL DEFAULT 0,
            is_stale INTEGER NOT NULL DEFAULT 0,
            stale_reasons_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            expires_at TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_guard_results_run_step
            ON guard_results (run_id, step_id);
        CREATE INDEX IF NOT EXISTS idx_guard_results_project
            ON guard_results (project_id);
        CREATE INDEX IF NOT EXISTS idx_guard_results_decision
            ON guard_results (decision);
        CREATE INDEX IF NOT EXISTS idx_guard_results_stale
            ON guard_results (is_stale);

        CREATE TABLE IF NOT EXISTS project_source_of_truth (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            document_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            archived_at TEXT,
            UNIQUE(project_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_project_sot_project_id
            ON project_source_of_truth (project_id);
        CREATE INDEX IF NOT EXISTS idx_project_sot_project_status
            ON project_source_of_truth (project_id, status);

        CREATE TABLE IF NOT EXISTS project_module_map (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'active',
            document_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT,
            archived_at TEXT,
            UNIQUE(project_id, version)
        );

        CREATE INDEX IF NOT EXISTS idx_project_module_map_project_id
            ON project_module_map (project_id);
        CREATE INDEX IF NOT EXISTS idx_project_module_map_project_status
            ON project_module_map (project_id, status);
        """
    )

    _add_missing_columns(
        conn,
        "projects",
        {
            "stack": "TEXT DEFAULT ''",
            "package_manager": "TEXT DEFAULT ''",
            "test_command": "TEXT DEFAULT ''",
            "build_command": "TEXT DEFAULT ''",
            "safe_commands": "TEXT DEFAULT '[]'",
            "blocked_commands": "TEXT DEFAULT '[]'",
            "ignore_paths": "TEXT DEFAULT '[]'",
            "updated_at": "TEXT",
        },
    )
    _add_missing_columns(
        conn,
        "runs",
        {
            "project_id": "TEXT DEFAULT ''",
            "project_path": "TEXT DEFAULT ''",
            "current_step_id": "TEXT DEFAULT ''",
        },
    )
    _add_missing_columns(
        conn,
        "run_steps",
        {
            "run_id": "TEXT DEFAULT ''",
            "parent_step_id": "TEXT DEFAULT ''",
            "agent_id": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT 'pending'",
            "title": "TEXT DEFAULT ''",
            "input": "TEXT DEFAULT ''",
            "output": "TEXT DEFAULT ''",
            "error": "TEXT DEFAULT ''",
            "started_at": "TEXT DEFAULT ''",
            "finished_at": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
        },
    )
    _add_missing_columns(
        conn,
        "tool_calls",
        {
            "run_id": "TEXT DEFAULT ''",
            "project_id": "TEXT DEFAULT ''",
            "step_id": "TEXT DEFAULT ''",
            "tool_name": "TEXT DEFAULT ''",
            "command": "TEXT DEFAULT ''",
            "cwd": "TEXT DEFAULT ''",
            "status": "TEXT DEFAULT ''",
            "approval_id": "TEXT DEFAULT ''",
            "stdout": "TEXT DEFAULT ''",
            "stderr": "TEXT DEFAULT ''",
            "returncode": "INTEGER",
            "report_path": "TEXT DEFAULT ''",
            "started_at": "TEXT DEFAULT ''",
            "finished_at": "TEXT DEFAULT ''",
            "created_at": "TEXT DEFAULT ''",
            "input_json": "TEXT DEFAULT ''",
            "output_json": "TEXT DEFAULT ''",
            "error": "TEXT DEFAULT ''",
            "risk_level": "TEXT DEFAULT 'low'",
            "completed_at": "TEXT",
        },
    )
    _add_missing_columns(
        conn,
        "run_agent_assignments",
        {
            "run_id": "TEXT DEFAULT ''",
            "agent_id": "TEXT DEFAULT ''",
            "assigned_role": "TEXT DEFAULT ''",
            "reason": "TEXT DEFAULT ''",
            "confidence": "REAL DEFAULT 0",
            "status": "TEXT DEFAULT 'selected'",
            "created_at": "TEXT DEFAULT ''",
        },
    )
    _add_missing_columns(
        conn,
        "model_route_decisions",
        {
            "run_id": "TEXT DEFAULT ''",
            "step_id": "TEXT",
            "agent_id": "TEXT DEFAULT ''",
            "task_type": "TEXT DEFAULT ''",
            "model_profile": "TEXT DEFAULT ''",
            "selected_model": "TEXT DEFAULT ''",
            "selected_provider": "TEXT DEFAULT ''",
            "fallback_model": "TEXT DEFAULT ''",
            "fallback_provider": "TEXT",
            "provider_mode": "TEXT DEFAULT 'local'",
            "reason": "TEXT DEFAULT ''",
            "confidence": "REAL DEFAULT 0",
            "warnings": "TEXT DEFAULT '[]'",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT",
        },
    )
    _add_missing_columns(
        conn,
        "project_source_of_truth",
        {
            "id": "TEXT",
            "project_id": "TEXT NOT NULL DEFAULT ''",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "status": "TEXT NOT NULL DEFAULT 'draft'",
            "document_json": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT",
            "archived_at": "TEXT",
        },
    )
    _add_missing_columns(
        conn,
        "project_module_map",
        {
            "id": "TEXT",
            "project_id": "TEXT NOT NULL DEFAULT ''",
            "version": "INTEGER NOT NULL DEFAULT 1",
            "status": "TEXT NOT NULL DEFAULT 'active'",
            "document_json": "TEXT NOT NULL DEFAULT '{}'",
            "created_at": "TEXT DEFAULT ''",
            "updated_at": "TEXT",
            "archived_at": "TEXT",
        },
    )
    conn.commit()
    conn.close()


# ── Small helpers ────────────────────────────────────────────────────────────

def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> str:
    return datetime.now().isoformat()


def _run_dir(run_id: str, created_at: str) -> str:
    run_path = repo_path("runs", f"{created_at[:19].replace(':', '-')}_{run_id}")
    return str(run_path.relative_to(PROJECT_ROOT))


def _decode_json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]


def _encode_json_list(value: list[str] | None) -> str:
    return json.dumps(value or [])


def _project_from_row(row: sqlite3.Row) -> Project:
    data = dict(row)
    for field in PROJECT_LIST_FIELDS:
        data[field] = _decode_json_list(data.get(field))
    return Project(**data)


def _run_from_row(row: sqlite3.Row) -> Run:
    data = dict(row)
    data["logs"] = json.loads(data.get("logs") or "[]")
    data["artifacts"] = json.loads(data.get("artifacts") or "[]")
    return Run(**data)


def _tool_call_from_row(row: sqlite3.Row) -> ToolCall:
    return ToolCall(**dict(row))


def _model_route_decision_from_row(row: sqlite3.Row) -> ModelRouteDecision:
    data = dict(row)
    data["warnings"] = _decode_json_list(data.get("warnings"))
    return ModelRouteDecision(**data)


def validate_project_path(path: str) -> str:
    """Resolve and validate an external project directory path."""
    if not path or not path.strip():
        raise ValueError("Project path is required")

    expanded = Path(path).expanduser()
    if not expanded.is_absolute():
        raise ValueError("Project path must be absolute")

    try:
        resolved = expanded.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("Project path does not exist") from exc

    if not resolved.is_dir():
        raise ValueError("Project path must be an existing directory")

    if resolved == Path("/").resolve():
        raise ValueError("Project path cannot be the filesystem root")

    if resolved == Path.home().resolve():
        raise ValueError("Project path cannot be the home directory root")

    system_dirs = [
        Path("/Applications"),
        Path("/Library"),
        Path("/System"),
        Path("/bin"),
        Path("/etc"),
        Path("/private"),
        Path("/sbin"),
        Path("/usr"),
        Path("/var"),
    ]
    if resolved in (p.resolve(strict=False) for p in system_dirs):
        raise ValueError("Project path cannot be an obvious system directory")

    return str(resolved)


# ── Projects ─────────────────────────────────────────────────────────────────

def create_project(
    name: str,
    path: str,
    description: str = "",
    stack: str = "",
    package_manager: str = "",
    test_command: str = "",
    build_command: str = "",
    safe_commands: list[str] | None = None,
    blocked_commands: list[str] | None = None,
    ignore_paths: list[str] | None = None,
) -> Project:
    conn = _connect()
    project_id = _new_id()
    now = _now()
    resolved_path = validate_project_path(path)
    conn.execute(
        """
        INSERT INTO projects (
            id, name, path, description, stack, package_manager, test_command,
            build_command, safe_commands, blocked_commands, ignore_paths, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            project_id,
            name,
            resolved_path,
            description,
            stack,
            package_manager,
            test_command,
            build_command,
            _encode_json_list(safe_commands),
            _encode_json_list(blocked_commands),
            _encode_json_list(ignore_paths),
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return _project_from_row(row)


def list_projects() -> list[Project]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_project_from_row(row) for row in rows]


def get_project(project_id: str) -> Project | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _project_from_row(row)


def update_project(project_id: str, **kwargs: Any) -> Project | None:
    allowed_fields = {
        "name",
        "path",
        "description",
        "stack",
        "package_manager",
        "test_command",
        "build_command",
        "safe_commands",
        "blocked_commands",
        "ignore_paths",
    }
    updates = {key: value for key, value in kwargs.items() if key in allowed_fields and value is not None}
    if "path" in updates:
        updates["path"] = validate_project_path(str(updates["path"]))
    for field in PROJECT_LIST_FIELDS:
        if field in updates:
            updates[field] = _encode_json_list(updates[field])
    updates["updated_at"] = _now()

    conn = _connect()
    if updates:
        sets = [f"{key}=?" for key in updates]
        values = list(updates.values())
        values.append(project_id)
        conn.execute(f"UPDATE projects SET {', '.join(sets)} WHERE id=?", values)
        conn.commit()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _project_from_row(row)


# ── Runs ─────────────────────────────────────────────────────────────────────

def create_run(
    prompt: str,
    mode: str = "offline",
    project_id: str = "",
    project_path: str = "",
) -> Run:
    conn = _connect()
    run_id = _new_id()
    now = _now()
    run_dir = _run_dir(run_id, now)
    conn.execute(
        """
        INSERT INTO runs (
            id, task_id, project_id, project_path, current_step_id, agent_id,
            status, mode, prompt, plan, result, logs, artifacts, run_dir, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            run_id,
            "",
            project_id,
            project_path,
            "",
            "orchestrator",
            RunStatus.PENDING.value,
            mode,
            prompt,
            "",
            "",
            "[]",
            "[]",
            run_dir,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    return _run_from_row(row)


def get_run(run_id: str) -> Run | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _run_from_row(row)


def list_runs() -> list[Run]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_run_from_row(row) for row in rows]


def update_run(run_id: str, **kwargs: Any) -> None:
    if not kwargs:
        return
    conn = _connect()
    sets = []
    values = []
    for key, value in kwargs.items():
        if key in ("logs", "artifacts") and isinstance(value, list):
            value = json.dumps(value)
        if hasattr(value, "value"):
            value = value.value
        sets.append(f"{key}=?")
        values.append(value)
    values.append(run_id)
    conn.execute(f"UPDATE runs SET {', '.join(sets)} WHERE id=?", values)
    conn.commit()
    conn.close()


# ── Run Steps ────────────────────────────────────────────────────────────────

def create_run_step(
    *,
    run_id: str,
    title: str,
    parent_step_id: str = "",
    agent_id: str = "",
    status: str = RunStatus.PENDING.value,
    input: str = "",
    output: str = "",
    error: str = "",
    started_at: str = "",
    finished_at: str = "",
) -> RunStep:
    conn = _connect()
    step_id = _new_id()
    now = _now()
    status_value = status.value if hasattr(status, "value") else status
    conn.execute(
        """
        INSERT INTO run_steps (
            id, run_id, parent_step_id, agent_id, status, title, input, output,
            error, started_at, finished_at, created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            step_id,
            run_id,
            parent_step_id,
            agent_id,
            status_value,
            title,
            input,
            output,
            error,
            started_at,
            finished_at,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone()
    conn.close()
    return RunStep(**dict(row))


def update_run_step(step_id: str, **kwargs: Any) -> RunStep | None:
    allowed = {
        "parent_step_id",
        "agent_id",
        "status",
        "title",
        "input",
        "output",
        "error",
        "started_at",
        "finished_at",
    }
    updates = {key: value for key, value in kwargs.items() if key in allowed}
    conn = _connect()
    if updates:
        sets = []
        values = []
        for key, value in updates.items():
            if hasattr(value, "value"):
                value = value.value
            sets.append(f"{key}=?")
            values.append(value)
        values.append(step_id)
        conn.execute(f"UPDATE run_steps SET {', '.join(sets)} WHERE id=?", values)
        conn.commit()
    row = conn.execute("SELECT * FROM run_steps WHERE id=?", (step_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return RunStep(**dict(row))


def list_run_steps(run_id: str) -> list[RunStep]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM run_steps WHERE run_id=? ORDER BY created_at ASC",
        (run_id,),
    ).fetchall()
    conn.close()
    return [RunStep(**dict(row)) for row in rows]


# ── Tool Calls ───────────────────────────────────────────────────────────────

def create_tool_call(
    *,
    run_id: str = "",
    project_id: str = "",
    step_id: str = "",
    tool_name: str,
    command: str = "",
    cwd: str = "",
    status: str = "",
    input_json: str = "",
    approval_id: str = "",
    stdout: str = "",
    stderr: str = "",
    returncode: int | None = None,
    report_path: str = "",
    started_at: str = "",
    finished_at: str = "",
    output_json: str | None = None,
    error: str | None = None,
    risk_level: str = "low",
    completed_at: str | None = None,
) -> ToolCall:
    conn = _connect()
    tool_call_id = _new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO tool_calls (
            id, run_id, project_id, step_id, tool_name, command, cwd, status,
            input_json, approval_id, stdout, stderr, returncode, report_path,
            started_at, finished_at, output_json, error, risk_level, completed_at,
            created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            tool_call_id,
            run_id,
            project_id,
            step_id,
            tool_name,
            command,
            cwd,
            status,
            input_json,
            approval_id,
            stdout,
            stderr,
            returncode,
            report_path,
            started_at,
            finished_at,
            output_json,
            error,
            risk_level,
            completed_at,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM tool_calls WHERE id=?", (tool_call_id,)).fetchone()
    conn.close()
    return _tool_call_from_row(row)


def update_tool_call(tool_call_id: str, **kwargs: Any) -> ToolCall | None:
    allowed = {
        "run_id",
        "project_id",
        "step_id",
        "tool_name",
        "command",
        "cwd",
        "status",
        "input_json",
        "approval_id",
        "stdout",
        "stderr",
        "returncode",
        "report_path",
        "started_at",
        "finished_at",
        "output_json",
        "error",
        "risk_level",
        "completed_at",
    }
    updates = {key: value for key, value in kwargs.items() if key in allowed}
    conn = _connect()
    if updates:
        sets = [f"{key}=?" for key in updates]
        values = list(updates.values())
        values.append(tool_call_id)
        conn.execute(f"UPDATE tool_calls SET {', '.join(sets)} WHERE id=?", values)
        conn.commit()
    row = conn.execute("SELECT * FROM tool_calls WHERE id=?", (tool_call_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _tool_call_from_row(row)


def list_project_tool_calls(project_id: str, limit: int = 25) -> list[ToolCall]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM tool_calls
        WHERE project_id=?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (project_id, limit),
    ).fetchall()
    conn.close()
    return [_tool_call_from_row(row) for row in rows]


def list_tool_calls_for_run(run_id: str, limit: int = 100) -> list[ToolCall]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM tool_calls WHERE run_id=? ORDER BY created_at DESC LIMIT ?",
        (run_id, limit),
    ).fetchall()
    conn.close()
    return [_tool_call_from_row(row) for row in rows]


def list_tool_calls_for_step(step_id: str, limit: int = 100) -> list[ToolCall]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM tool_calls WHERE step_id=? ORDER BY created_at DESC LIMIT ?",
        (step_id, limit),
    ).fetchall()
    conn.close()
    return [_tool_call_from_row(row) for row in rows]


def list_tool_calls_for_project(project_id: str, limit: int = 100) -> list[ToolCall]:
    return list_project_tool_calls(project_id, limit)


# ── Run Agent Assignments ────────────────────────────────────────────────────

def create_run_agent_assignment(
    *,
    run_id: str,
    agent_id: str,
    assigned_role: str = "",
    reason: str = "",
    confidence: float = 0.0,
    status: str = "selected",
) -> RunAgentAssignment:
    conn = _connect()
    assignment_id = _new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO run_agent_assignments (
            id, run_id, agent_id, assigned_role, reason, confidence, status, created_at
        ) VALUES (?,?,?,?,?,?,?,?)
        """,
        (assignment_id, run_id, agent_id, assigned_role, reason, confidence, status, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM run_agent_assignments WHERE id=?", (assignment_id,)).fetchone()
    conn.close()
    return RunAgentAssignment(**dict(row))


def replace_run_agent_assignments(run_id: str, assignments: list[dict[str, Any]]) -> list[RunAgentAssignment]:
    conn = _connect()
    now = _now()
    conn.execute("DELETE FROM run_agent_assignments WHERE run_id=?", (run_id,))
    created: list[RunAgentAssignment] = []
    for item in assignments:
        agent_id = str(item.get("agent_id", "")).strip()
        if not agent_id:
            continue
        assignment_id = _new_id()
        assigned_role = str(item.get("assigned_role", ""))
        reason = str(item.get("reason", ""))
        confidence = float(item.get("confidence", 0.0) or 0.0)
        status = str(item.get("status", "selected") or "selected")
        conn.execute(
            """
            INSERT INTO run_agent_assignments (
                id, run_id, agent_id, assigned_role, reason, confidence, status, created_at
            ) VALUES (?,?,?,?,?,?,?,?)
            """,
            (assignment_id, run_id, agent_id, assigned_role, reason, confidence, status, now),
        )
        created.append(
            RunAgentAssignment(
                id=assignment_id,
                run_id=run_id,
                agent_id=agent_id,
                assigned_role=assigned_role,
                reason=reason,
                confidence=confidence,
                status=status,
                created_at=now,
            )
        )
    conn.commit()
    conn.close()
    return created


def list_run_agent_assignments(run_id: str) -> list[RunAgentAssignment]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM run_agent_assignments
        WHERE run_id=?
        ORDER BY confidence DESC, created_at ASC
        """,
        (run_id,),
    ).fetchall()
    conn.close()
    return [RunAgentAssignment(**dict(row)) for row in rows]


def get_run_agent_assignment(run_id: str, agent_id: str) -> RunAgentAssignment | None:
    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM run_agent_assignments
        WHERE run_id=? AND agent_id=?
        LIMIT 1
        """,
        (run_id, agent_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return RunAgentAssignment(**dict(row))


def update_run_agent_assignment(
    run_id: str,
    agent_id: str,
    **kwargs: Any,
) -> RunAgentAssignment | None:
    allowed = {"assigned_role", "reason", "confidence", "status"}
    updates = {key: value for key, value in kwargs.items() if key in allowed and value is not None}
    conn = _connect()
    if updates:
        sets = [f"{key}=?" for key in updates]
        values = list(updates.values())
        values.extend([run_id, agent_id])
        conn.execute(
            f"UPDATE run_agent_assignments SET {', '.join(sets)} WHERE run_id=? AND agent_id=?",
            values,
        )
        conn.commit()
    row = conn.execute(
        """
        SELECT * FROM run_agent_assignments
        WHERE run_id=? AND agent_id=?
        LIMIT 1
        """,
        (run_id, agent_id),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return RunAgentAssignment(**dict(row))


# ── Model Route Decisions ────────────────────────────────────────────────────

def create_model_route_decision(
    *,
    run_id: str,
    agent_id: str,
    task_type: str,
    model_profile: str,
    selected_model: str,
    selected_provider: str,
    step_id: str | None = None,
    fallback_model: str = "",
    fallback_provider: str | None = None,
    provider_mode: str = "local",
    reason: str = "",
    confidence: float = 0.0,
    warnings: list[str] | None = None,
) -> ModelRouteDecision:
    conn = _connect()
    decision_id = _new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO model_route_decisions (
            id, run_id, step_id, agent_id, task_type, model_profile, selected_model,
            selected_provider, fallback_model, fallback_provider, provider_mode,
            reason, confidence, warnings, created_at, updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            decision_id,
            run_id,
            step_id,
            agent_id,
            task_type,
            model_profile,
            selected_model,
            selected_provider,
            fallback_model,
            fallback_provider,
            provider_mode,
            reason,
            confidence,
            _encode_json_list(warnings),
            now,
            now,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM model_route_decisions WHERE id=?", (decision_id,)).fetchone()
    conn.close()
    return _model_route_decision_from_row(row)


def get_model_route_decision(decision_id: str) -> ModelRouteDecision | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM model_route_decisions WHERE id=?", (decision_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _model_route_decision_from_row(row)


def get_model_route_decisions_for_run(run_id: str) -> list[ModelRouteDecision]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM model_route_decisions
        WHERE run_id=?
        ORDER BY created_at ASC, agent_id ASC, task_type ASC
        """,
        (run_id,),
    ).fetchall()
    conn.close()
    return [_model_route_decision_from_row(row) for row in rows]


def upsert_model_route_decision(*args: Any, **kwargs: Any) -> ModelRouteDecision:
    if args and isinstance(args[0], dict):
        data = dict(args[0])
    elif args and isinstance(args[0], ModelRouteDecision):
        data = args[0].model_dump()
    else:
        data = dict(kwargs)

    run_id = str(data.get("run_id", ""))
    agent_id = str(data.get("agent_id", ""))
    task_type = str(data.get("task_type", ""))
    step_id = data.get("step_id")

    conn = _connect()
    row = conn.execute(
        """
        SELECT * FROM model_route_decisions
        WHERE run_id=? AND agent_id=? AND task_type=? AND COALESCE(step_id, '')=?
        LIMIT 1
        """,
        (run_id, agent_id, task_type, step_id or ""),
    ).fetchone()

    now = _now()
    encoded_warnings = _encode_json_list(data.get("warnings"))
    if row:
        conn.execute(
            """
            UPDATE model_route_decisions
            SET model_profile=?, selected_model=?, selected_provider=?, fallback_model=?,
                fallback_provider=?, provider_mode=?, reason=?, confidence=?, warnings=?,
                updated_at=?
            WHERE id=?
            """,
            (
                data.get("model_profile", ""),
                data.get("selected_model", ""),
                data.get("selected_provider", ""),
                data.get("fallback_model", ""),
                data.get("fallback_provider"),
                data.get("provider_mode", "local"),
                data.get("reason", ""),
                float(data.get("confidence", 0.0) or 0.0),
                encoded_warnings,
                now,
                row["id"],
            ),
        )
        decision_id = row["id"]
    else:
        decision_id = data.get("id") or _new_id()
        conn.execute(
            """
            INSERT INTO model_route_decisions (
                id, run_id, step_id, agent_id, task_type, model_profile, selected_model,
                selected_provider, fallback_model, fallback_provider, provider_mode,
                reason, confidence, warnings, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                decision_id,
                run_id,
                step_id,
                agent_id,
                task_type,
                data.get("model_profile", ""),
                data.get("selected_model", ""),
                data.get("selected_provider", ""),
                data.get("fallback_model", ""),
                data.get("fallback_provider"),
                data.get("provider_mode", "local"),
                data.get("reason", ""),
                float(data.get("confidence", 0.0) or 0.0),
                encoded_warnings,
                data.get("created_at") or now,
                now,
            ),
        )
    conn.commit()
    updated = conn.execute("SELECT * FROM model_route_decisions WHERE id=?", (decision_id,)).fetchone()
    conn.close()
    return _model_route_decision_from_row(updated)


def delete_model_route_decisions_for_run(run_id: str) -> int:
    conn = _connect()
    cursor = conn.execute("DELETE FROM model_route_decisions WHERE run_id=?", (run_id,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def delete_step_route_decisions_for_run(run_id: str) -> int:
    conn = _connect()
    cursor = conn.execute(
        "DELETE FROM model_route_decisions WHERE run_id=? AND step_id IS NOT NULL",
        (run_id,),
    )
    deleted = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted


def get_model_route_decision_for_step(step_id: str) -> ModelRouteDecision | None:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM model_route_decisions WHERE step_id=? LIMIT 1",
        (step_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    return _model_route_decision_from_row(row)


def list_model_route_decisions_for_steps(run_id: str) -> list[ModelRouteDecision]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM model_route_decisions
        WHERE run_id=? AND step_id IS NOT NULL
        ORDER BY created_at ASC
        """,
        (run_id,),
    ).fetchall()
    conn.close()
    return [_model_route_decision_from_row(row) for row in rows]


def list_model_route_decisions_for_agents(run_id: str) -> list[ModelRouteDecision]:
    conn = _connect()
    rows = conn.execute(
        """
        SELECT * FROM model_route_decisions
        WHERE run_id=? AND step_id IS NULL
        ORDER BY created_at ASC, agent_id ASC
        """,
        (run_id,),
    ).fetchall()
    conn.close()
    return [_model_route_decision_from_row(row) for row in rows]


def upsert_step_route_decision(*args: Any, **kwargs: Any) -> ModelRouteDecision:
    if args and isinstance(args[0], dict):
        data = dict(args[0])
    elif args and isinstance(args[0], ModelRouteDecision):
        data = args[0].model_dump()
    else:
        data = dict(kwargs)

    run_id = str(data.get("run_id", ""))
    step_id = str(data.get("step_id", ""))
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM model_route_decisions WHERE run_id=? AND step_id=? LIMIT 1",
        (run_id, step_id),
    ).fetchone()

    now = _now()
    encoded_warnings = _encode_json_list(data.get("warnings"))
    if row:
        conn.execute(
            """
            UPDATE model_route_decisions
            SET agent_id=?, task_type=?, model_profile=?, selected_model=?,
                selected_provider=?, fallback_model=?, fallback_provider=?, provider_mode=?,
                reason=?, confidence=?, warnings=?, updated_at=?
            WHERE id=?
            """,
            (
                data.get("agent_id", ""),
                data.get("task_type", ""),
                data.get("model_profile", ""),
                data.get("selected_model", ""),
                data.get("selected_provider", ""),
                data.get("fallback_model", ""),
                data.get("fallback_provider"),
                data.get("provider_mode", "local"),
                data.get("reason", ""),
                float(data.get("confidence", 0.0) or 0.0),
                encoded_warnings,
                now,
                row["id"],
            ),
        )
        decision_id = row["id"]
    else:
        decision_id = data.get("id") or _new_id()
        conn.execute(
            """
            INSERT INTO model_route_decisions (
                id, run_id, step_id, agent_id, task_type, model_profile, selected_model,
                selected_provider, fallback_model, fallback_provider, provider_mode,
                reason, confidence, warnings, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                decision_id,
                run_id,
                step_id,
                data.get("agent_id", ""),
                data.get("task_type", ""),
                data.get("model_profile", ""),
                data.get("selected_model", ""),
                data.get("selected_provider", ""),
                data.get("fallback_model", ""),
                data.get("fallback_provider"),
                data.get("provider_mode", "local"),
                data.get("reason", ""),
                float(data.get("confidence", 0.0) or 0.0),
                encoded_warnings,
                data.get("created_at") or now,
                now,
            ),
        )
    conn.commit()
    updated = conn.execute("SELECT * FROM model_route_decisions WHERE id=?", (decision_id,)).fetchone()
    conn.close()
    return _model_route_decision_from_row(updated)


# ── Approvals ────────────────────────────────────────────────────────────────

def create_approval(run_id: str, action: str, command: str = "", description: str = "") -> ApprovalRequest:
    conn = _connect()
    approval_id = _new_id()
    now = _now()
    conn.execute(
        """
        INSERT INTO approvals (id, run_id, action, command, description, status, created_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (approval_id, run_id, action, command, description, ApprovalStatus.PENDING.value, now),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    conn.close()
    return ApprovalRequest(**dict(row))


def find_pending_approval(run_id: str, action: str | None = None, command: str | None = None) -> ApprovalRequest | None:
    conn = _connect()
    sql = "SELECT * FROM approvals WHERE run_id=? AND status=?"
    params: list[Any] = [run_id, ApprovalStatus.PENDING.value]
    if action:
        sql += " AND action=?"
        params.append(action)
    if command is not None:
        sql += " AND command=?"
        params.append(command)
    sql += " ORDER BY created_at DESC LIMIT 1"
    row = conn.execute(sql, tuple(params)).fetchone()
    conn.close()
    if not row:
        return None
    return ApprovalRequest(**dict(row))


def get_approval(approval_id: str) -> ApprovalRequest | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return ApprovalRequest(**dict(row))


def list_approvals(status: str | None = None, limit: int | None = None) -> list[ApprovalRequest]:
    conn = _connect()
    params: list[Any] = []
    sql = "SELECT * FROM approvals"
    if status:
        sql += " WHERE status=?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    rows = conn.execute(sql, tuple(params)).fetchall()
    conn.close()
    return [ApprovalRequest(**dict(row)) for row in rows]


def resolve_approval(
    approval_id: str,
    decision: ApprovalStatus | str,
    reason: str = "",
) -> ApprovalRequest | None:
    conn = _connect()
    now = _now()
    status_value = decision.value if hasattr(decision, "value") else str(decision)
    conn.execute(
        "UPDATE approvals SET status=?, resolved_at=? WHERE id=?",
        (status_value, now, approval_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return ApprovalRequest(**dict(row))


# Ensure DB initialized on import.
init_db()

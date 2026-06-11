"""Project-level workspace tool adapters."""

from __future__ import annotations

import difflib
import hashlib
import os
import re
import shlex
import subprocess
from datetime import datetime

from src.models import PatchOperation
from src.utils.workspace_tools import list_files as workspace_list_files
from src.utils.workspace_tools import read_file as workspace_read_file
from src.utils.workspace_tools import search_code as workspace_search_code
from src.utils.workspace_tools import MAX_FILE_BYTES
from src.utils.workspace_tools import _looks_secret
from src.utils.workspace_tools import _project_root
from src.utils.workspace_tools import _resolve_inside

MAX_PATCH_DIFF_CHARS = 200_000
TRUNCATED_DIFF_MARKER = "\n... diff truncated by AI Workbench ...\n"
MAX_ROLLBACK_CONTENT_CHARS = 200_000


def list_files(project_path: str, path: str = ".", max_files: int = 500) -> dict:
    return workspace_list_files(project_path, path=path, max_files=max_files)


def read_file(project_path: str, path: str, max_chars: int = 200_000) -> dict:
    return workspace_read_file(project_path, path=path, max_chars=max_chars)


def search_code(project_path: str, query: str, path: str = ".", max_results: int = 100) -> dict:
    return workspace_search_code(project_path, query=query, path=path, max_results=max_results)


def propose_project_patch(project_path: str, operations: list[PatchOperation]) -> dict:
    """Build a patch preview for project files without writing to disk."""
    if not operations:
        raise ValueError("At least one patch operation is required")

    root = _project_root(project_path)
    files: list[dict] = []
    warnings: list[str] = []

    for operation in operations:
        files.append(_propose_operation(root, operation))

    changed = sum(1 for item in files if item["status"] in {"create", "modify"})
    errors = sum(1 for item in files if item["status"] == "error")
    unchanged = sum(1 for item in files if item["status"] == "unchanged")
    summary = f"{changed} change preview(s), {unchanged} unchanged, {errors} error(s)."
    if errors:
        warnings.append("One or more patch operations could not be previewed.")
    if any(item.get("diff", "").endswith(TRUNCATED_DIFF_MARKER) for item in files):
        warnings.append("One or more diffs were truncated.")
    return {"files": files, "summary": summary, "warnings": warnings}


def apply_project_patch(project_path: str, operations: list[PatchOperation], confirm: bool) -> dict:
    """Apply text patch operations after explicit confirmation and full preflight.

    Stores rollback_data in the returned dict for each changed file (up to
    MAX_ROLLBACK_CONTENT_CHARS per file).  The caller (routes.py) writes this
    into the tool_call output_json so the rollback endpoint can retrieve it.
    """
    if not confirm:
        raise PermissionError("Patch apply requires confirm=true")
    plan = _build_apply_plan(project_path, operations)

    rollback_entries: list[dict] = []
    warnings: list[str] = []

    for item in plan:
        if item["status"] == "modified":
            before = item["before_content"]
            new = item["new_content"]
            if len(before) > MAX_ROLLBACK_CONTENT_CHARS:
                warnings.append(
                    f"{item['path']}: file too large for rollback capture "
                    f"(>{MAX_ROLLBACK_CONTENT_CHARS} chars); manual rollback not available"
                )
                rollback_entries.append({
                    "path": item["path"],
                    "operation": "modified",
                    "before_content": None,
                    "after_hash": None,
                    "rollback_supported": False,
                })
            else:
                rollback_entries.append({
                    "path": item["path"],
                    "operation": "modified",
                    "before_content": before,
                    "after_hash": _content_hash(new),
                    "rollback_supported": True,
                })
            item["target"].write_text(new, encoding="utf-8")

        elif item["status"] == "created":
            new = item["new_content"]
            rollback_entries.append({
                "path": item["path"],
                "operation": "created",
                "before_content": None,
                "after_hash": _content_hash(new),
                "rollback_supported": True,
            })
            item["target"].write_text(new, encoding="utf-8")

    files = [{"path": item["path"], "status": item["status"], "error": ""} for item in plan]
    changed = sum(1 for f in files if f["status"] in {"modified", "created"})
    unchanged = sum(1 for f in files if f["status"] == "unchanged")
    return {
        "files": files,
        "summary": f"{changed} file(s) changed, {unchanged} unchanged.",
        "warnings": warnings,
        "rollback_data": rollback_entries,
    }


def _build_apply_plan(project_path: str, operations: list[PatchOperation]) -> list[dict]:
    if not operations:
        raise ValueError("At least one patch operation is required")

    root = _project_root(project_path)
    virtual_content: dict[str, str] = {}
    targets: dict[str, object] = {}
    existed: dict[str, bool] = {}
    errors: list[str] = []

    for index, operation in enumerate(operations, start=1):
        try:
            target = _resolve_inside(root, operation.file_path)
            relative = "." if target == root else target.relative_to(root).as_posix()
            if _looks_secret(target):
                raise ValueError("Refusing to patch secret-like file")
            if target.exists() and not target.is_file():
                raise ValueError("Path is not a file")
            if not target.exists() and not operation.create_if_missing and relative not in virtual_content:
                raise ValueError("File does not exist")
            if not target.exists() and not target.parent.exists():
                raise ValueError("Parent directory does not exist")

            if relative not in virtual_content:
                if target.exists():
                    virtual_content[relative] = _read_patchable_text(target)
                    existed[relative] = True
                else:
                    virtual_content[relative] = ""
                    existed[relative] = False
            targets[relative] = target

            if existed[relative]:
                virtual_content[relative] = _apply_existing_text(virtual_content[relative], operation)
            else:
                virtual_content[relative] = _apply_create_text(virtual_content[relative], operation)
                existed[relative] = True
        except (OSError, ValueError) as exc:
            errors.append(f"operation {index} ({operation.file_path}): {exc}")

    if errors:
        raise ValueError("Patch preflight failed: " + "; ".join(errors))

    plan: list[dict] = []
    for relative, target in targets.items():
        current = _read_patchable_text(target) if target.exists() else ""
        new_content = virtual_content[relative]
        if current == new_content:
            status = "unchanged"
        elif target.exists():
            status = "modified"
        else:
            status = "created"
        plan.append({
            "path": relative,
            "target": target,
            "new_content": new_content,
            "before_content": current,  # "" for created files; used by rollback
            "status": status,
        })
    return plan


def _apply_existing_text(content: str, operation: PatchOperation) -> str:
    if not operation.old_text:
        raise ValueError("old_text is required for existing files")
    if operation.old_text not in content:
        raise ValueError("old_text was not found")
    if operation.replace_all:
        return content.replace(operation.old_text, operation.new_text)
    return content.replace(operation.old_text, operation.new_text, 1)


def _apply_create_text(content: str, operation: PatchOperation) -> str:
    if not operation.create_if_missing:
        raise ValueError("File does not exist")
    if operation.old_text:
        raise ValueError("old_text must be empty when creating a missing file")
    if content:
        raise ValueError("Cannot create file because staged content already exists")
    return operation.new_text


def _propose_operation(root, operation: PatchOperation) -> dict:
    try:
        target = _resolve_inside(root, operation.file_path)
        relative = "." if target == root else target.relative_to(root).as_posix()
        if _looks_secret(target):
            return _patch_error(relative, "Refusing to patch secret-like file")
        if target.exists() and not target.is_file():
            return _patch_error(relative, "Path is not a file")
        if target.exists():
            return _propose_existing_file(target, relative, operation)
        return _propose_missing_file(relative, operation)
    except ValueError as exc:
        return _patch_error(operation.file_path, str(exc))
    except OSError as exc:
        return _patch_error(operation.file_path, str(exc))


def _propose_existing_file(target, relative: str, operation: PatchOperation) -> dict:
    if not operation.old_text:
        return _patch_error(relative, "old_text is required for existing files")
    original = _read_patchable_text(target)
    if operation.old_text not in original:
        return _patch_error(relative, "old_text was not found")

    if operation.replace_all:
        proposed = original.replace(operation.old_text, operation.new_text)
    else:
        proposed = original.replace(operation.old_text, operation.new_text, 1)

    if proposed == original:
        return {"path": relative, "status": "unchanged", "diff": "", "error": ""}
    return {
        "path": relative,
        "status": "modify",
        "diff": _unified_diff(relative, original, proposed),
        "error": "",
    }


def _propose_missing_file(relative: str, operation: PatchOperation) -> dict:
    if not operation.create_if_missing:
        return _patch_error(relative, "File does not exist")
    if operation.old_text:
        return _patch_error(relative, "old_text must be empty when creating a missing file")
    if not operation.new_text:
        return {"path": relative, "status": "unchanged", "diff": "", "error": ""}
    return {
        "path": relative,
        "status": "create",
        "diff": _unified_diff(relative, "", operation.new_text),
        "error": "",
    }


def _read_patchable_text(path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File is too large to patch through this tool")
    data = path.read_bytes()
    if b"\x00" in data:
        raise ValueError("Refusing to patch binary file")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("File is not valid UTF-8 text") from exc


def _unified_diff(path: str, old: str, new: str) -> str:
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{path}",
            tofile=f"b/{path}",
        )
    )
    if len(diff) > MAX_PATCH_DIFF_CHARS:
        return diff[:MAX_PATCH_DIFF_CHARS] + TRUNCATED_DIFF_MARKER
    return diff


def _patch_error(path: str, message: str) -> dict:
    return {"path": path, "status": "error", "diff": "", "error": message}


def _content_hash(content: str) -> str:
    """Short SHA-256 hex digest of UTF-8 content — used for conflict detection."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def rollback_project_patch(project_path: str, rollback_data: list[dict], confirm: bool) -> dict:
    """Revert files using rollback_data stored in an apply-patch tool_call output_json.

    Safety rules (same as apply_project_patch):
    - confirm=True required.
    - Conflict detection: each file is only reverted when its current content hash
      matches the after_hash captured at apply time.
    - No shell commands executed.
    - Path traversal and secret-like files are blocked.
    - 'created' files are deleted; 'modified' files are restored to before_content.
    """
    if not confirm:
        raise PermissionError("Rollback requires confirm=true")
    if not rollback_data:
        raise ValueError("No rollback data provided")

    root = _project_root(project_path)
    rolled_back: list[dict] = []
    skipped: list[dict] = []
    warnings: list[str] = []

    for entry in rollback_data:
        path = entry.get("path", "")
        operation = entry.get("operation", "")
        rollback_supported = entry.get("rollback_supported", False)
        after_hash = entry.get("after_hash")
        before_content = entry.get("before_content")

        if not rollback_supported:
            reason = "rollback metadata not available (file was too large at apply time)"
            skipped.append({"path": path, "operation": operation, "status": "skipped", "reason": reason})
            warnings.append(f"{path}: {reason}")
            continue

        try:
            target = _resolve_inside(root, path)
        except ValueError as exc:
            skipped.append({"path": path, "operation": operation, "status": "error", "reason": str(exc)})
            warnings.append(f"{path}: {exc}")
            continue

        if _looks_secret(target):
            reason = "secret-like file — rollback blocked"
            skipped.append({"path": path, "operation": operation, "status": "skipped", "reason": reason})
            warnings.append(f"{path}: {reason}")
            continue

        if operation == "modified":
            if not target.exists():
                reason = "file no longer exists"
                skipped.append({"path": path, "operation": operation, "status": "skipped", "reason": reason})
                warnings.append(f"{path}: {reason}, cannot restore")
                continue
            try:
                current_content = _read_patchable_text(target)
            except ValueError as exc:
                skipped.append({"path": path, "operation": operation, "status": "error", "reason": str(exc)})
                warnings.append(f"{path}: {exc}")
                continue
            if _content_hash(current_content) != after_hash:
                reason = "file has been modified since the patch was applied"
                skipped.append({"path": path, "operation": operation, "status": "conflict", "reason": reason})
                warnings.append(f"{path}: {reason} — skipping rollback to avoid data loss")
                continue
            target.write_text(before_content, encoding="utf-8")
            rolled_back.append({"path": path, "operation": operation, "status": "restored", "reason": ""})

        elif operation == "created":
            if not target.exists():
                reason = "created file no longer exists"
                skipped.append({"path": path, "operation": operation, "status": "skipped", "reason": reason})
                warnings.append(f"{path}: {reason}, nothing to delete")
                continue
            try:
                current_content = _read_patchable_text(target)
            except ValueError as exc:
                skipped.append({"path": path, "operation": operation, "status": "error", "reason": str(exc)})
                warnings.append(f"{path}: {exc}")
                continue
            if _content_hash(current_content) != after_hash:
                reason = "created file has been modified since the patch was applied"
                skipped.append({"path": path, "operation": operation, "status": "conflict", "reason": reason})
                warnings.append(f"{path}: {reason} — skipping rollback to avoid data loss")
                continue
            target.unlink()
            rolled_back.append({"path": path, "operation": operation, "status": "deleted", "reason": ""})

        else:
            reason = f"unknown operation '{operation}'"
            skipped.append({"path": path, "operation": operation, "status": "skipped", "reason": reason})
            warnings.append(f"{path}: {reason}")

    n_rolled = len(rolled_back)
    n_skipped = len(skipped)
    return {
        "rolled_back_files": rolled_back,
        "skipped_files": skipped,
        "warnings": warnings,
        "summary": f"{n_rolled} file(s) rolled back, {n_skipped} skipped.",
    }


# ── Safe command runner ───────────────────────────────────────────────────────

MAX_OUTPUT_CHARS = 100_000
TRUNCATED_OUTPUT_MARKER = "\n... output truncated by AI Workbench ...\n"

# Patterns that are always forbidden, regardless of allowlist
_BLOCKED_RUNNER_PATTERNS: list[re.Pattern] = [
    re.compile(r"\brm\b", re.IGNORECASE),
    re.compile(r"\bsudo\b", re.IGNORECASE),
    re.compile(r"\bcurl\s+.*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"\bwget\s+.*\|\s*(sh|bash)", re.IGNORECASE),
    re.compile(r"\bchmod\b", re.IGNORECASE),
    re.compile(r"\bchown\b", re.IGNORECASE),
    re.compile(r"\bgit\s+push\b", re.IGNORECASE),
    re.compile(r"\bdocker\s+compose\s+down", re.IGNORECASE),
    re.compile(r"\bpip.*install\b", re.IGNORECASE),
    re.compile(r"\bnpm\s+install\b", re.IGNORECASE),
    re.compile(r"\bbrew\s+install\b", re.IGNORECASE),
]


def _check_runner_safety(command: str) -> None:
    """Raise ValueError if the command matches any blocked pattern or is suspicious."""
    if ".." in command:
        raise ValueError("Command contains path traversal (..)")
    for pattern in _BLOCKED_RUNNER_PATTERNS:
        if pattern.search(command):
            raise ValueError(f"Command blocked by safety rule: {pattern.pattern!r}")


def run_project_command(
    project_path: str,
    command: str,
    timeout_seconds: int = 120,
) -> dict:
    """Run a whitelisted command safely inside project_path.

    Safety guarantees:
    - shell=False (no shell injection via ; & | etc.)
    - cwd anchored to project_path
    - stdout/stderr capped at MAX_OUTPUT_CHARS
    - forced LC_ALL=C LANG=C locale
    - timeout enforced; returns timed_out=True on expiry
    - dangerous pattern check before execution

    Returns a dict with: command, cwd, returncode, stdout, stderr,
    duration_ms, timed_out.
    """
    command = (command or "").strip()
    if not command:
        raise ValueError("Command is empty")

    _check_runner_safety(command)

    try:
        args = shlex.split(command)
    except ValueError as exc:
        raise ValueError(f"Invalid command syntax: {exc}") from exc

    if not args:
        raise ValueError("Command parsed to empty argument list")

    root = _project_root(project_path)

    env = {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
    }

    started_at = datetime.now()
    timed_out = False
    try:
        result = subprocess.run(
            args,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            shell=False,
            env=env,
        )
        returncode = result.returncode
        raw_stdout = result.stdout or ""
        raw_stderr = result.stderr or ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        raw_stdout = (exc.stdout or b"").decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        raw_stderr = (exc.stderr or b"").decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")

    finished_at = datetime.now()
    duration_ms = int((finished_at - started_at).total_seconds() * 1000)

    # Cap output
    stdout_truncated = len(raw_stdout) > MAX_OUTPUT_CHARS
    stderr_truncated = len(raw_stderr) > MAX_OUTPUT_CHARS
    stdout = raw_stdout[:MAX_OUTPUT_CHARS] + (TRUNCATED_OUTPUT_MARKER if stdout_truncated else "")
    stderr = raw_stderr[:MAX_OUTPUT_CHARS] + (TRUNCATED_OUTPUT_MARKER if stderr_truncated else "")

    return {
        "command": command,
        "cwd": str(root),
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
        "duration_ms": duration_ms,
        "timed_out": timed_out,
    }


# Keywords for selecting lint/typecheck commands from safe_commands
_LINT_KEYWORDS = ("lint", "eslint", "flake8", "ruff check", "pylint", "stylelint", "prettier --check")
_TYPECHECK_KEYWORDS = ("tsc", "mypy", "pyright", "typecheck", "type-check", "type_check")


def analyze_command_result(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int | None = None,
    timed_out: bool = False,
    command_kind: str = "",
) -> dict:
    """Heuristic analysis of command output — no LLM, no patch generation.

    Returns a dict compatible with CommandAnalysisResponse fields:
    status, summary, issues, suggested_next_actions, can_create_fix_proposal.
    """
    # Work on capped text to stay fast
    MAX_ANALYSE = 100_000
    text_out = (stdout or "")[:MAX_ANALYSE]
    text_err = (stderr or "")[:MAX_ANALYSE]
    combined = (text_out + "\n" + text_err).strip()

    issues: list[dict] = []
    actions: list[str] = []

    # ── Timeout ───────────────────────────────────────────────────────────────
    if timed_out or returncode == 124:
        issues.append({
            "kind": "timeout",
            "file_path": None,
            "line": None,
            "message": "Command exceeded the time limit and was killed.",
            "raw_excerpt": "",
        })
        return {
            "status": "timed_out",
            "summary": "Command timed out before completing.",
            "issues": issues,
            "suggested_next_actions": [
                "Increase timeout_seconds in the run-command request.",
                "Check for infinite loops or hung network calls.",
            ],
            "can_create_fix_proposal": False,
        }

    # ── Passed ────────────────────────────────────────────────────────────────
    if returncode == 0:
        return {
            "status": "passed",
            "summary": "Command completed successfully with exit code 0.",
            "issues": [],
            "suggested_next_actions": [],
            "can_create_fix_proposal": False,
        }

    # ── pytest failures ───────────────────────────────────────────────────────
    _PYTEST_FAILED_RE = re.compile(r"^FAILED\s+(\S+?)(?:::(.*?))?(?:\s|$)", re.MULTILINE)
    _ASSERT_RE        = re.compile(r"AssertionError:?(.{0,200})", re.IGNORECASE)
    _TRACEBACK_RE     = re.compile(
        r'File "([^"]+)", line (\d+).*?\n(?:.*\n){0,3}?(\w.*)',
        re.MULTILINE,
    )

    for m in _PYTEST_FAILED_RE.finditer(text_out + "\n" + text_err):
        test_path = m.group(1).strip()
        test_name = (m.group(2) or "").strip()
        issues.append({
            "kind": "test_failure",
            "file_path": test_path or None,
            "line": None,
            "message": f"Test failed: {test_path}{'::' + test_name if test_name else ''}",
            "raw_excerpt": m.group(0)[:300],
        })

    for m in _ASSERT_RE.finditer(combined):
        msg = m.group(1).strip()
        issues.append({
            "kind": "assertion_error",
            "file_path": None,
            "line": None,
            "message": f"AssertionError: {msg}" if msg else "AssertionError",
            "raw_excerpt": m.group(0)[:300],
        })

    # Python traceback — File "...", line N
    for m in _TRACEBACK_RE.finditer(combined):
        fp = m.group(1).strip()
        ln = int(m.group(2))
        msg = m.group(3).strip()[:200]
        # Skip stdlib paths
        if "/python" in fp.lower() or "site-packages" in fp.lower():
            continue
        issues.append({
            "kind": "traceback",
            "file_path": fp,
            "line": ln,
            "message": msg,
            "raw_excerpt": m.group(0)[:300],
        })

    # ── TypeScript / tsc errors ───────────────────────────────────────────────
    _TS_ERROR_RE = re.compile(
        r"([^\s(]+\.tsx?)\((\d+),(\d+)\): error (TS\d+):\s*(.+)",
        re.IGNORECASE,
    )
    for m in _TS_ERROR_RE.finditer(combined):
        fp, ln, col, code, msg = m.group(1), int(m.group(2)), m.group(3), m.group(4), m.group(5).strip()
        issues.append({
            "kind": "type_error",
            "file_path": fp,
            "line": ln,
            "message": f"{code}: {msg} (col {col})",
            "raw_excerpt": m.group(0)[:300],
        })

    # ── Lint errors (eslint, ruff, flake8) ───────────────────────────────────
    # ruff/flake8: path.py:line:col: Exx  message
    _RUFF_RE = re.compile(r"([^\s]+\.py):(\d+):\d+:\s+([A-Z]\d+)\s+(.+)", re.MULTILINE)
    for m in _RUFF_RE.finditer(combined):
        fp, ln, code, msg = m.group(1), int(m.group(2)), m.group(3), m.group(4).strip()
        issues.append({
            "kind": "lint_error",
            "file_path": fp,
            "line": ln,
            "message": f"{code}: {msg}",
            "raw_excerpt": m.group(0)[:300],
        })

    # ── Generic build error lines ─────────────────────────────────────────────
    _BUILD_ERROR_RE = re.compile(r"^.*\berror\b.*$", re.IGNORECASE | re.MULTILINE)
    if not issues:
        for m in _BUILD_ERROR_RE.finditer(combined):
            line_text = m.group(0).strip()
            if len(line_text) < 5:
                continue
            issues.append({
                "kind": "build_error",
                "file_path": None,
                "line": None,
                "message": line_text[:300],
                "raw_excerpt": line_text[:300],
            })
            if len(issues) >= 5:
                break

    # ── Deduplicate by (kind, file_path, line, message) ──────────────────────
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for issue in issues:
        key = (issue["kind"], issue.get("file_path"), issue.get("line"), issue["message"][:80])
        if key not in seen:
            seen.add(key)
            deduped.append(issue)
    issues = deduped[:20]  # hard cap

    # ── Status and summary ────────────────────────────────────────────────────
    if returncode is None:
        status = "unknown"
    else:
        status = "failed"

    kinds = {i["kind"] for i in issues}
    has_fixable = bool(kinds & {"test_failure", "assertion_error", "traceback", "type_error", "lint_error"})
    can_fix = has_fixable and bool(
        any(i.get("file_path") for i in issues)
    )

    # Build summary
    count = len(issues)
    if count == 0:
        summary = f"Command exited with code {returncode}. No specific issues detected."
    else:
        kind_counts: dict[str, int] = {}
        for i in issues:
            kind_counts[i["kind"]] = kind_counts.get(i["kind"], 0) + 1
        parts = [f"{v} {k.replace('_', ' ')}" for k, v in kind_counts.items()]
        summary = f"Command failed (exit {returncode}): {', '.join(parts)}."

    # Suggested actions
    if "test_failure" in kinds or "assertion_error" in kinds:
        actions.append("Review the failing test output and fix the assertion or logic.")
    if "traceback" in kinds:
        actions.append("Inspect the traceback file/line and fix the Python error.")
    if "type_error" in kinds:
        actions.append("Fix the TypeScript type errors listed in the issues.")
    if "lint_error" in kinds:
        actions.append("Run the formatter/linter locally and apply suggested fixes.")
    if "build_error" in kinds:
        actions.append("Check build configuration and dependency versions.")
    if not actions:
        actions.append(f"Inspect stdout/stderr for exit code {returncode}.")
    if can_fix:
        actions.append("Use 'Propose Patch' to manually draft a fix for the affected file(s).")

    return {
        "status": status,
        "summary": summary,
        "issues": issues,
        "suggested_next_actions": actions,
        "can_create_fix_proposal": can_fix,
    }


def find_safe_command_for_kind(kind: str, safe_commands: list[str]) -> str | None:
    """Search safe_commands for a command matching the requested kind (lint/typecheck).

    Returns the first matching command string, or None if nothing matches.
    """
    keywords: tuple[str, ...]
    if kind == "lint":
        keywords = _LINT_KEYWORDS
    elif kind == "typecheck":
        keywords = _TYPECHECK_KEYWORDS
    else:
        return None

    for cmd in safe_commands:
        cmd_lower = cmd.lower().strip()
        if any(kw in cmd_lower for kw in keywords):
            return cmd.strip()
    return None

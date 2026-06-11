"""Safe read-only workspace helpers."""

from __future__ import annotations

from pathlib import Path

DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    ".pytest_cache",
}
SECRET_FILENAMES = {".env", ".env.local", ".envrc"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx"}
MAX_FILE_BYTES = 1_000_000


def list_files(project_path: str, path: str = ".", max_files: int = 500) -> dict:
    """List files below a project-relative directory without leaving the workspace."""
    root = _project_root(project_path)
    base = _resolve_inside(root, path)
    if not base.exists():
        raise ValueError("Path does not exist")
    if not base.is_dir():
        raise ValueError("Path is not a directory")

    entries: list[dict] = []
    for item in sorted(base.rglob("*")):
        if len(entries) >= max(1, max_files):
            break
        if _is_excluded(item, root):
            continue
        relative = item.relative_to(root).as_posix()
        entries.append(
            {
                "path": relative,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            }
        )
    return {"root": str(root), "path": _relative_path(base, root), "files": entries, "truncated": len(entries) >= max_files}


def read_file(project_path: str, path: str, max_chars: int = 200_000) -> dict:
    """Read a text file inside the project workspace."""
    root = _project_root(project_path)
    file_path = _resolve_inside(root, path)
    if not file_path.exists():
        raise ValueError("File does not exist")
    if not file_path.is_file():
        raise ValueError("Path is not a file")
    if _looks_secret(file_path):
        raise ValueError("Refusing to read secret-like file")
    if file_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File is too large to read through this tool")

    content = file_path.read_text(encoding="utf-8", errors="replace")
    truncated = len(content) > max_chars
    return {
        "path": file_path.relative_to(root).as_posix(),
        "content": content[:max_chars],
        "truncated": truncated,
        "size": file_path.stat().st_size,
    }


def search_code(project_path: str, query: str, path: str = ".", max_results: int = 100) -> dict:
    """Search for a plain text query in project files."""
    query = query or ""
    if not query.strip():
        raise ValueError("Search query is required")

    root = _project_root(project_path)
    base = _resolve_inside(root, path)
    if not base.exists():
        raise ValueError("Path does not exist")
    if not base.is_dir():
        raise ValueError("Path is not a directory")

    matches: list[dict] = []
    for file_path in sorted(base.rglob("*")):
        if len(matches) >= max(1, max_results):
            break
        if not file_path.is_file() or _is_excluded(file_path, root) or _looks_secret(file_path):
            continue
        try:
            if file_path.stat().st_size > MAX_FILE_BYTES:
                continue
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if query in line:
                matches.append(
                    {
                        "path": file_path.relative_to(root).as_posix(),
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
                if len(matches) >= max(1, max_results):
                    break
    return {"query": query, "path": _relative_path(base, root), "matches": matches, "truncated": len(matches) >= max_results}


def _project_root(project_path: str) -> Path:
    root = Path(project_path).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project path is not a directory")
    return root


def _resolve_inside(root: Path, requested_path: str) -> Path:
    requested = Path(requested_path or ".")
    if requested.is_absolute():
        raise ValueError("Tool paths must be project-relative")
    resolved = (root / requested).resolve(strict=False)
    if resolved != root and root not in resolved.parents:
        raise ValueError("Path escapes project workspace")
    return resolved


def _relative_path(path: Path, root: Path) -> str:
    return "." if path == root else path.relative_to(root).as_posix()


def _is_excluded(path: Path, root: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part in DEFAULT_EXCLUDES for part in parts)


def _looks_secret(path: Path) -> bool:
    name = path.name.lower()
    return name in SECRET_FILENAMES or path.suffix.lower() in SECRET_SUFFIXES

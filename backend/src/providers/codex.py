"""Codex CLI provider stub — wraps `codex exec` with approval gate."""

from __future__ import annotations

from src.models import ApprovalRequest, ApprovalStatus


async def execute(
    prompt: str,
    project_path: str = ".",
    approval: ApprovalRequest | None = None,
) -> str:
    """
    Codex provider stub for MVP.

    In the full version this will:
    1. Create an ApprovalRequest
    2. Wait for user approval
    3. Run `codex exec --prompt <prompt>` in the project directory
    4. Capture and return output

    For now, returns a placeholder indicating approval is required.
    """
    if approval is None or approval.status != ApprovalStatus.APPROVED:
        return (
            "[CODEX PROVIDER] Execution requires approval. "
            "Please approve the request in the Approvals panel."
        )

    # TODO: Actually invoke codex CLI
    return (
        f"[CODEX PROVIDER STUB] Would execute codex with prompt:\n{prompt}\n"
        f"In project: {project_path}\n"
        "This is a stub — real execution not yet implemented."
    )


async def check_available() -> bool:
    """Check if codex CLI is installed."""
    import shutil
    return shutil.which("codex") is not None

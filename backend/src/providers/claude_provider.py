"""Claude Code CLI provider stub — wraps `claude` with approval gate."""

from __future__ import annotations

from src.models import ApprovalRequest, ApprovalStatus


async def execute(
    prompt: str,
    project_path: str = ".",
    approval: ApprovalRequest | None = None,
) -> str:
    """
    Claude Code provider stub for MVP.

    In the full version this will:
    1. Create an ApprovalRequest
    2. Wait for user approval
    3. Run `claude --print --prompt <prompt>` in the project directory
    4. Capture and return output

    For now, returns a placeholder indicating approval is required.
    """
    if approval is None or approval.status != ApprovalStatus.APPROVED:
        return (
            "[CLAUDE PROVIDER] Execution requires approval. "
            "Please approve the request in the Approvals panel."
        )

    # TODO: Actually invoke claude CLI
    return (
        f"[CLAUDE PROVIDER STUB] Would execute claude with prompt:\n{prompt}\n"
        f"In project: {project_path}\n"
        "This is a stub — real execution not yet implemented."
    )


async def check_available() -> bool:
    """Check if claude CLI is installed."""
    import shutil
    return shutil.which("claude") is not None

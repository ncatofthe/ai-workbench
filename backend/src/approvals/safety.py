"""Safety layer — checks whether an action requires human approval."""

from __future__ import annotations

import re

# Actions that always require approval
DANGEROUS_PATTERNS: list[tuple[str, str]] = [
    (r"\brm\s+(-rf?|--recursive)", "file_delete"),
    (r"\bgit\s+push", "git_push"),
    (r"\bgit\s+push\s+--force", "git_force_push"),
    (r"\bgit\s+rebase", "git_push"),
    (r"\bdocker\s+compose\s+down", "docker_compose_down"),
    (r"\bdocker\s+system\s+prune", "docker_compose_down"),
    (r"\bpip3?\s+install", "package_install"),
    (r"\bpython(?:3)?\s+-m\s+pip\s+install", "package_install"),
    (r"\buv\s+pip\s+install", "package_install"),
    (r"\bnpm\s+install\s+-g", "package_install"),
    (r"\bbrew\s+install", "package_install"),
    (r"\bsudo\s+", "shell_exec"),
    (r"\bcurl\s+.*\|\s*(sh|bash)", "shell_exec"),
    (r"\bwget\s+.*\|\s*(sh|bash)", "shell_exec"),
    (r"\.env\b", "env_file_modify"),
    (r"\bnpm\s+publish", "npm_publish"),
]


def check_command(command: str) -> tuple[bool, str, str]:
    """
    Check if a shell command requires approval.

    Returns:
        (needs_approval, action_type, description)
    """
    for pattern, action_type in DANGEROUS_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True, action_type, f"Command matches dangerous pattern: {pattern}"
    return False, "", ""


def check_action(action: str) -> bool:
    """Check if a named action type is in the restricted list."""
    restricted = {
        "shell_exec", "package_install", "file_delete",
        "git_push", "git_force_push", "docker_compose_down",
        "env_file_modify", "system_file_modify", "npm_publish", "pip_install",
    }
    return action in restricted

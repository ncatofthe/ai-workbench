"""Configuration loader — reads config.yaml."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from src.utils.paths import resolve_runtime_path

CONFIG_PATH = resolve_runtime_path(os.environ.get("WORKBENCH_CONFIG"), "config.yaml")

_config: dict[str, Any] | None = None


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load and cache configuration from YAML file."""
    global _config
    p = _resolve_config_path(path)
    if p.exists():
        with open(p, encoding="utf-8") as f:
            _config = yaml.safe_load(f) or {}
    else:
        _config = _default_config()
    return _config


def get_config() -> dict[str, Any]:
    """Return cached config or load it."""
    if _config is None:
        return load_config()
    return _config


def save_config(updates: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    """Merge updates into config and save to disk."""
    global _config
    cfg = get_config()

    if "default_mode" in updates and updates["default_mode"]:
        cfg["default_mode"] = _string_value(updates["default_mode"])
    if "provider_mode" in updates and updates["provider_mode"]:
        cfg["provider_mode"] = _string_value(updates["provider_mode"])
    if "ollama_base_url" in updates and updates["ollama_base_url"]:
        cfg.setdefault("ollama", {})["base_url"] = updates["ollama_base_url"]
    if "ollama_model" in updates and updates["ollama_model"]:
        cfg.setdefault("ollama", {})["default_model"] = updates["ollama_model"]
    if "codex_enabled" in updates and updates["codex_enabled"] is not None:
        cfg.setdefault("codex", {})["enabled"] = updates["codex_enabled"]
    if "claude_enabled" in updates and updates["claude_enabled"] is not None:
        cfg.setdefault("claude", {})["enabled"] = updates["claude_enabled"]

    p = _resolve_config_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, default_flow_style=False, allow_unicode=True)

    _config = cfg
    return cfg


def _string_value(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _resolve_config_path(path: Path | None = None) -> Path:
    if path is None:
        return Path(CONFIG_PATH)
    expanded = path.expanduser()
    if expanded.is_absolute():
        return expanded
    return resolve_runtime_path(expanded, "config.yaml")


def _default_config() -> dict[str, Any]:
    return {
        "default_mode": "offline",
        "provider_mode": "local",
        "ollama": {
            "base_url": "http://localhost:11434",
            "default_model": "qwen2.5-coder:7b",
            "timeout_seconds": 120,
        },
        "codex": {"enabled": False},
        "claude": {"enabled": False},
        "safety": {
            "require_approval_for": [
                "shell_exec", "package_install", "file_delete",
                "git_push", "git_force_push", "docker_compose_down",
                "env_file_modify", "system_file_modify",
            ],
        },
    }

"""Pure Migration / Backup / Restore Contract v1.

This module defines release-readiness contracts for future backup and restore
tooling.  It intentionally does not connect to SQLite, read or write files,
execute commands, call providers, create tool calls, or mutate runtime state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


MIGRATION_BACKUP_RESTORE_SCHEMA_VERSION = "1.0"


class BackupItemKind(str, Enum):
    DATABASE = "database"
    RUN_ARTIFACTS = "run_artifacts"
    PROJECT_METADATA = "project_metadata"
    SOURCE_OF_TRUTH = "source_of_truth"
    MODULE_MAP = "module_map"
    GUARD_RESULTS = "guard_results"
    APPROVALS = "approvals"
    TOOL_CALLS = "tool_calls"
    SETTINGS = "settings"
    EXTERNAL_PROJECT_FILES = "external_project_files"
    PROVIDER_SECRETS = "provider_secrets"


class BackupItemSensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    SENSITIVE = "sensitive"
    SECRET = "secret"


class BackupRestoreRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    BLOCKED = "blocked"


class RestorePreflightStatus(str, Enum):
    ALLOWED = "allowed"
    WARNING = "warning"
    BLOCKED = "blocked"


class BackupManifestItem(BaseModel):
    kind: BackupItemKind
    name: str
    path_hint: str = ""
    required: bool = False
    sensitivity: BackupItemSensitivity = BackupItemSensitivity.INTERNAL
    include_by_default: bool = True
    redaction_required: bool = False
    explicit_operator_confirmation: bool = False
    notes: str = ""

    @field_validator("name", "path_hint", "notes", mode="before")
    @classmethod
    def _coerce_text(cls, value: object) -> str:
        return "" if value is None else str(value)


class BackupManifest(BaseModel):
    app_name: str = "AI Workbench"
    schema_version: str = MIGRATION_BACKUP_RESTORE_SCHEMA_VERSION
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    items: list[BackupManifestItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    excluded_items: list[BackupManifestItem] = Field(default_factory=list)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _coerce_schema_version(cls, value: object) -> str:
        return "" if value is None else str(value).strip()


class ManifestValidationResult(BaseModel):
    status: RestorePreflightStatus = RestorePreflightStatus.ALLOWED
    risk: BackupRestoreRisk = BackupRestoreRisk.LOW
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RestorePreflightInput(BaseModel):
    manifest_schema_version: str
    current_schema_version: str
    target_environment: str = "local"
    allow_overwrite: bool = False
    has_backup_database: bool = False
    has_required_items: bool = True
    contains_provider_secrets: bool = False
    contains_external_project_files: bool = False

    @field_validator("manifest_schema_version", "current_schema_version", "target_environment", mode="before")
    @classmethod
    def _coerce_text(cls, value: object) -> str:
        return "" if value is None else str(value).strip()


class RestorePreflightResult(BaseModel):
    status: RestorePreflightStatus
    risk: BackupRestoreRisk
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_operator_confirmations: list[str] = Field(default_factory=list)


def classify_backup_item_sensitivity(item: BackupManifestItem) -> BackupItemSensitivity:
    """Return the expected sensitivity for a manifest item kind."""

    mapping: dict[BackupItemKind, BackupItemSensitivity] = {
        BackupItemKind.DATABASE: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.RUN_ARTIFACTS: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.PROJECT_METADATA: BackupItemSensitivity.INTERNAL,
        BackupItemKind.SOURCE_OF_TRUTH: BackupItemSensitivity.INTERNAL,
        BackupItemKind.MODULE_MAP: BackupItemSensitivity.INTERNAL,
        BackupItemKind.GUARD_RESULTS: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.APPROVALS: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.TOOL_CALLS: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.SETTINGS: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.EXTERNAL_PROJECT_FILES: BackupItemSensitivity.SENSITIVE,
        BackupItemKind.PROVIDER_SECRETS: BackupItemSensitivity.SECRET,
    }
    return mapping.get(item.kind, item.sensitivity)


def build_default_backup_manifest(
    *,
    created_at: datetime | None = None,
    schema_version: str = MIGRATION_BACKUP_RESTORE_SCHEMA_VERSION,
) -> BackupManifest:
    """Build the default backup contract manifest.

    The manifest describes what future backup tooling should include or exclude.
    It does not inspect the runtime filesystem.
    """

    item_defs: list[BackupManifestItem] = [
        BackupManifestItem(
            kind=BackupItemKind.DATABASE,
            name="Workbench SQLite database",
            path_hint="data/workbench.db",
            required=True,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            redaction_required=False,
            notes="Primary durable state: projects, runs, steps, approvals, tool calls, SoT, module map, guard results.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.PROJECT_METADATA,
            name="Project metadata",
            path_hint="projects table",
            required=True,
            sensitivity=BackupItemSensitivity.INTERNAL,
            include_by_default=True,
            notes="Project records, paths, safe commands, and profile metadata.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.SOURCE_OF_TRUTH,
            name="Source of Truth versions",
            path_hint="project_source_of_truth table",
            required=True,
            sensitivity=BackupItemSensitivity.INTERNAL,
            include_by_default=True,
            notes="Versioned product requirements and constraints.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.MODULE_MAP,
            name="Project Module Map versions",
            path_hint="project_module_map table",
            required=True,
            sensitivity=BackupItemSensitivity.INTERNAL,
            include_by_default=True,
            notes="Versioned module ownership, paths, risks, and test hints.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.GUARD_RESULTS,
            name="Guard result audit records",
            path_hint="guard_results table",
            required=True,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            notes="Source-of-Truth guard decisions and proposal/apply links.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.APPROVALS,
            name="Approval records",
            path_hint="approvals table",
            required=True,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            notes="Operator approval decisions and pending approval state.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.TOOL_CALLS,
            name="Tool call audit history",
            path_hint="tool_calls table",
            required=True,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            notes="Proposal, apply, command, delivery, and context audit outputs.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.RUN_ARTIFACTS,
            name="Run artifacts",
            path_hint="runs/",
            required=False,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            redaction_required=False,
            explicit_operator_confirmation=True,
            notes="Operator should review for large files, raw logs, or accidental secrets before export.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.SETTINGS,
            name="Local settings",
            path_hint="config.yaml and runtime config",
            required=False,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            redaction_required=True,
            explicit_operator_confirmation=True,
            notes="May contain provider mode, local paths, or environment-specific configuration.",
        ),
    ]

    excluded_items = [
        BackupManifestItem(
            kind=BackupItemKind.PROVIDER_SECRETS,
            name="Provider secrets and API keys",
            path_hint=".env, shell environment, provider credential stores",
            required=False,
            sensitivity=BackupItemSensitivity.SECRET,
            include_by_default=False,
            redaction_required=True,
            explicit_operator_confirmation=True,
            notes="Excluded by default. Never include unredacted provider credentials in portable backups.",
        ),
        BackupManifestItem(
            kind=BackupItemKind.EXTERNAL_PROJECT_FILES,
            name="External project source files",
            path_hint="project workspace paths",
            required=False,
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=False,
            redaction_required=False,
            explicit_operator_confirmation=True,
            notes="Excluded by default. AI Workbench backup covers metadata/audit, not arbitrary project source trees.",
        ),
    ]

    return BackupManifest(
        schema_version=schema_version,
        created_at=created_at or datetime.now(timezone.utc),
        items=item_defs,
        warnings=[
            "Review run artifacts and settings before export; they may contain sensitive local data.",
            "Provider secrets and external project files are excluded by default.",
        ],
        excluded_items=excluded_items,
    )


def validate_backup_manifest(manifest: BackupManifest) -> ManifestValidationResult:
    """Validate a backup manifest contract without reading files or DB state."""

    blockers: list[str] = []
    warnings: list[str] = list(manifest.warnings)

    if not manifest.schema_version:
        blockers.append("Manifest schema_version is required.")

    included_by_kind: dict[BackupItemKind, list[BackupManifestItem]] = {}
    all_by_kind: dict[BackupItemKind, list[BackupManifestItem]] = {}
    for item in manifest.items:
        all_by_kind.setdefault(item.kind, []).append(item)
        if item.include_by_default:
            included_by_kind.setdefault(item.kind, []).append(item)

    if BackupItemKind.DATABASE not in included_by_kind:
        blockers.append("Backup manifest must include the database item.")

    for kind, label in (
        (BackupItemKind.GUARD_RESULTS, "guard_results"),
        (BackupItemKind.APPROVALS, "approvals"),
        (BackupItemKind.TOOL_CALLS, "tool_calls"),
    ):
        if kind not in included_by_kind:
            warnings.append(f"Backup manifest omits {label}; audit history may be incomplete after restore.")

    if BackupItemKind.RUN_ARTIFACTS not in included_by_kind:
        warnings.append("Backup manifest omits run artifacts; reports and generated files may be incomplete.")

    for item in manifest.items:
        expected_sensitivity = classify_backup_item_sensitivity(item)
        if item.sensitivity != expected_sensitivity:
            warnings.append(
                f"Item '{item.name}' sensitivity is {item.sensitivity.value}; expected {expected_sensitivity.value}."
            )
        if item.kind == BackupItemKind.PROVIDER_SECRETS and item.include_by_default and not item.redaction_required:
            blockers.append("Provider secrets cannot be included without redaction.")
        if (
            item.kind == BackupItemKind.EXTERNAL_PROJECT_FILES
            and item.include_by_default
            and not item.explicit_operator_confirmation
        ):
            warnings.append("External project files require explicit operator confirmation before inclusion.")
        if (
            item.kind == BackupItemKind.RUN_ARTIFACTS
            and item.include_by_default
            and not item.explicit_operator_confirmation
        ):
            warnings.append("Run artifacts should require operator review before export.")

    status = RestorePreflightStatus.ALLOWED
    risk = BackupRestoreRisk.LOW
    if blockers:
        status = RestorePreflightStatus.BLOCKED
        risk = BackupRestoreRisk.BLOCKED
    elif warnings:
        status = RestorePreflightStatus.WARNING
        risk = BackupRestoreRisk.MEDIUM

    return ManifestValidationResult(
        status=status,
        risk=risk,
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
    )


def evaluate_restore_preflight(input_data: RestorePreflightInput) -> RestorePreflightResult:
    """Evaluate whether a future restore operation should proceed."""

    blockers: list[str] = []
    warnings: list[str] = []
    confirmations: list[str] = []

    if not input_data.has_backup_database:
        blockers.append("Restore requires a backup database.")
    if not input_data.has_required_items:
        blockers.append("Restore manifest is missing required backup domains.")

    schema_cmp = _compare_schema_versions(
        input_data.manifest_schema_version,
        input_data.current_schema_version,
    )
    if schema_cmp is None:
        blockers.append("Restore requires valid manifest and current schema versions.")
    elif schema_cmp > 0:
        blockers.append("Backup schema version is newer than the current app schema.")
    elif schema_cmp < 0:
        warnings.append("Backup schema version is older; migration compatibility must be verified.")

    if not input_data.allow_overwrite:
        blockers.append("Restore would overwrite existing state; allow_overwrite must be true.")
    else:
        confirmations.append("Confirm overwrite of existing AI Workbench database/state.")

    if input_data.contains_provider_secrets:
        warnings.append("Backup contains provider secrets; restore requires secret review and redaction confirmation.")
        confirmations.append("Confirm provider secrets are intended, rotated if needed, and safe to restore.")

    if input_data.contains_external_project_files:
        warnings.append("Backup contains external project files; restore may overwrite or expose project source data.")
        confirmations.append("Confirm external project files are intended and paths are safe.")

    if input_data.target_environment not in {"local", "single_user", "internal_beta", "production"}:
        warnings.append(f"Unknown target environment '{input_data.target_environment}'; operator review required.")

    if input_data.has_required_items:
        confirmations.append("Confirm sensitive artifacts and audit logs have been reviewed before restore.")

    status = RestorePreflightStatus.ALLOWED
    risk = BackupRestoreRisk.LOW
    if blockers:
        status = RestorePreflightStatus.BLOCKED
        risk = BackupRestoreRisk.BLOCKED
    elif warnings:
        status = RestorePreflightStatus.WARNING
        risk = BackupRestoreRisk.HIGH if (input_data.contains_provider_secrets or input_data.contains_external_project_files) else BackupRestoreRisk.MEDIUM

    return RestorePreflightResult(
        status=status,
        risk=risk,
        blockers=_dedupe(blockers),
        warnings=_dedupe(warnings),
        required_operator_confirmations=_dedupe(confirmations),
    )


def build_backup_operator_checklist() -> list[str]:
    """Return a human checklist for future backup tooling/operators."""

    return [
        "Stop the app or ensure no writes are in progress.",
        "Copy the AI Workbench SQLite database.",
        "Export the backup manifest and verify schema_version.",
        "Review run artifacts for sensitive logs or large files.",
        "Exclude or redact provider secrets.",
        "Exclude external project files unless explicitly requested.",
        "Verify the backup can be listed and checksummed before deleting any local data.",
    ]


def build_restore_operator_checklist() -> list[str]:
    """Return a human checklist for future restore tooling/operators."""

    return [
        "Back up the current state before restore.",
        "Verify manifest schema compatibility with the current app.",
        "Confirm overwrite of the target database/state.",
        "Review provider secrets and restore them manually only if intended.",
        "Review external project files and path boundaries before restore.",
        "Start the app and validate projects, runs, guards, approvals, and delivery reports after restore.",
    ]


def redact_manifest_for_report(manifest: BackupManifest) -> BackupManifest:
    """Return a manifest copy safe for human reports."""

    def redact_item(item: BackupManifestItem) -> BackupManifestItem:
        if item.redaction_required or item.sensitivity == BackupItemSensitivity.SECRET:
            return item.model_copy(update={"path_hint": "[redacted]"})
        return item

    return manifest.model_copy(
        update={
            "items": [redact_item(item) for item in manifest.items],
            "excluded_items": [redact_item(item) for item in manifest.excluded_items],
        }
    )


def _compare_schema_versions(left: str, right: str) -> int | None:
    left_parts = _schema_parts(left)
    right_parts = _schema_parts(right)
    if left_parts is None or right_parts is None:
        return None
    max_len = max(len(left_parts), len(right_parts))
    padded_left = left_parts + [0] * (max_len - len(left_parts))
    padded_right = right_parts + [0] * (max_len - len(right_parts))
    if padded_left > padded_right:
        return 1
    if padded_left < padded_right:
        return -1
    return 0


def _schema_parts(value: str) -> list[int] | None:
    if not value:
        return None
    parts: list[int] = []
    for raw_part in value.split("."):
        if not raw_part.isdigit():
            return None
        parts.append(int(raw_part))
    return parts


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        clean = str(value).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result

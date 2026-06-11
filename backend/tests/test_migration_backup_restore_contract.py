"""Tests for Migration / Backup / Restore Contract v1."""

from __future__ import annotations

import importlib
import inspect

from src.release import migration_backup_restore_contract as contract
from src.release.migration_backup_restore_contract import (
    BackupItemKind,
    BackupItemSensitivity,
    BackupManifest,
    BackupManifestItem,
    BackupRestoreRisk,
    RestorePreflightInput,
    RestorePreflightStatus,
    build_backup_operator_checklist,
    build_default_backup_manifest,
    build_restore_operator_checklist,
    classify_backup_item_sensitivity,
    evaluate_restore_preflight,
    redact_manifest_for_report,
    validate_backup_manifest,
)


def _items_by_kind(manifest: BackupManifest) -> dict[BackupItemKind, list[BackupManifestItem]]:
    grouped: dict[BackupItemKind, list[BackupManifestItem]] = {}
    for item in manifest.items:
        grouped.setdefault(item.kind, []).append(item)
    for item in manifest.excluded_items:
        grouped.setdefault(item.kind, []).append(item)
    return grouped


def _included_kinds(manifest: BackupManifest) -> set[BackupItemKind]:
    return {item.kind for item in manifest.items if item.include_by_default}


class TestManifestDefaults:
    def test_default_manifest_includes_database_item(self):
        manifest = build_default_backup_manifest()
        db_items = [item for item in manifest.items if item.kind == BackupItemKind.DATABASE]
        assert db_items
        assert db_items[0].required is True
        assert db_items[0].include_by_default is True

    def test_default_manifest_includes_source_of_truth(self):
        assert BackupItemKind.SOURCE_OF_TRUTH in _included_kinds(build_default_backup_manifest())

    def test_default_manifest_includes_module_map(self):
        assert BackupItemKind.MODULE_MAP in _included_kinds(build_default_backup_manifest())

    def test_default_manifest_includes_guard_results(self):
        assert BackupItemKind.GUARD_RESULTS in _included_kinds(build_default_backup_manifest())

    def test_default_manifest_includes_approvals_and_tool_calls(self):
        included = _included_kinds(build_default_backup_manifest())
        assert BackupItemKind.APPROVALS in included
        assert BackupItemKind.TOOL_CALLS in included

    def test_provider_secrets_excluded_by_default(self):
        grouped = _items_by_kind(build_default_backup_manifest())
        item = grouped[BackupItemKind.PROVIDER_SECRETS][0]
        assert item.include_by_default is False
        assert item.sensitivity == BackupItemSensitivity.SECRET

    def test_external_project_files_excluded_by_default(self):
        grouped = _items_by_kind(build_default_backup_manifest())
        item = grouped[BackupItemKind.EXTERNAL_PROJECT_FILES][0]
        assert item.include_by_default is False
        assert item.sensitivity == BackupItemSensitivity.SENSITIVE

    def test_run_artifacts_included_with_operator_review(self):
        manifest = build_default_backup_manifest()
        item = [item for item in manifest.items if item.kind == BackupItemKind.RUN_ARTIFACTS][0]
        assert item.include_by_default is True
        assert item.explicit_operator_confirmation is True
        assert "review" in item.notes.lower()

    def test_manifest_has_schema_version(self):
        assert build_default_backup_manifest().schema_version == contract.MIGRATION_BACKUP_RESTORE_SCHEMA_VERSION

    def test_manifest_redaction_removes_secret_path_hints(self):
        manifest = build_default_backup_manifest()
        redacted = redact_manifest_for_report(manifest)
        provider_item = [item for item in redacted.excluded_items if item.kind == BackupItemKind.PROVIDER_SECRETS][0]
        settings_item = [item for item in redacted.items if item.kind == BackupItemKind.SETTINGS][0]
        assert provider_item.path_hint == "[redacted]"
        assert settings_item.path_hint == "[redacted]"


class TestManifestValidation:
    def test_missing_database_blocks_manifest_validation(self):
        manifest = build_default_backup_manifest()
        manifest = manifest.model_copy(
            update={"items": [item for item in manifest.items if item.kind != BackupItemKind.DATABASE]}
        )
        result = validate_backup_manifest(manifest)
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("database" in blocker.lower() for blocker in result.blockers)

    def test_missing_schema_version_blocks_validation(self):
        manifest = build_default_backup_manifest(schema_version="")
        result = validate_backup_manifest(manifest)
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("schema_version" in blocker for blocker in result.blockers)

    def test_omitted_guard_results_warns(self):
        manifest = build_default_backup_manifest()
        manifest = manifest.model_copy(
            update={"items": [item for item in manifest.items if item.kind != BackupItemKind.GUARD_RESULTS]}
        )
        result = validate_backup_manifest(manifest)
        assert result.status == RestorePreflightStatus.WARNING
        assert any("guard_results" in warning for warning in result.warnings)

    def test_omitted_approvals_warns(self):
        manifest = build_default_backup_manifest()
        manifest = manifest.model_copy(
            update={"items": [item for item in manifest.items if item.kind != BackupItemKind.APPROVALS]}
        )
        result = validate_backup_manifest(manifest)
        assert any("approvals" in warning for warning in result.warnings)

    def test_omitted_tool_calls_warns(self):
        manifest = build_default_backup_manifest()
        manifest = manifest.model_copy(
            update={"items": [item for item in manifest.items if item.kind != BackupItemKind.TOOL_CALLS]}
        )
        result = validate_backup_manifest(manifest)
        assert any("tool_calls" in warning for warning in result.warnings)

    def test_provider_secrets_without_redaction_blocks(self):
        manifest = build_default_backup_manifest()
        bad_secret = BackupManifestItem(
            kind=BackupItemKind.PROVIDER_SECRETS,
            name="Unredacted provider secrets",
            path_hint=".env",
            sensitivity=BackupItemSensitivity.SECRET,
            include_by_default=True,
            redaction_required=False,
        )
        result = validate_backup_manifest(manifest.model_copy(update={"items": [*manifest.items, bad_secret]}))
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("Provider secrets" in blocker for blocker in result.blockers)

    def test_external_files_without_explicit_confirmation_warns(self):
        manifest = build_default_backup_manifest()
        external = BackupManifestItem(
            kind=BackupItemKind.EXTERNAL_PROJECT_FILES,
            name="External project files",
            path_hint="/project",
            sensitivity=BackupItemSensitivity.SENSITIVE,
            include_by_default=True,
            explicit_operator_confirmation=False,
        )
        result = validate_backup_manifest(manifest.model_copy(update={"items": [*manifest.items, external]}))
        assert result.status == RestorePreflightStatus.WARNING
        assert any("External project files" in warning for warning in result.warnings)

    def test_valid_default_manifest_passes_with_warnings_only(self):
        result = validate_backup_manifest(build_default_backup_manifest())
        assert result.status == RestorePreflightStatus.WARNING
        assert result.risk == BackupRestoreRisk.MEDIUM
        assert result.blockers == []
        assert result.warnings


class TestRestorePreflight:
    def test_missing_backup_database_blocks_restore(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="1.0",
                current_schema_version="1.0",
                allow_overwrite=True,
                has_backup_database=False,
                has_required_items=True,
            )
        )
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("backup database" in blocker.lower() for blocker in result.blockers)

    def test_newer_backup_schema_blocks_restore(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="2.0",
                current_schema_version="1.0",
                allow_overwrite=True,
                has_backup_database=True,
                has_required_items=True,
            )
        )
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("newer" in blocker.lower() for blocker in result.blockers)

    def test_overwrite_without_allow_overwrite_blocks_restore(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="1.0",
                current_schema_version="1.0",
                allow_overwrite=False,
                has_backup_database=True,
                has_required_items=True,
            )
        )
        assert result.status == RestorePreflightStatus.BLOCKED
        assert any("allow_overwrite" in blocker for blocker in result.blockers)

    def test_provider_secrets_produce_warning_and_confirmation(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="1.0",
                current_schema_version="1.0",
                allow_overwrite=True,
                has_backup_database=True,
                has_required_items=True,
                contains_provider_secrets=True,
            )
        )
        assert result.status == RestorePreflightStatus.WARNING
        assert any("provider secrets" in warning.lower() for warning in result.warnings)
        assert any("provider secrets" in confirmation.lower() for confirmation in result.required_operator_confirmations)

    def test_external_project_files_produce_warning_and_confirmation(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="1.0",
                current_schema_version="1.0",
                allow_overwrite=True,
                has_backup_database=True,
                has_required_items=True,
                contains_external_project_files=True,
            )
        )
        assert result.status == RestorePreflightStatus.WARNING
        assert any("external project files" in warning.lower() for warning in result.warnings)
        assert any("external project files" in confirmation.lower() for confirmation in result.required_operator_confirmations)

    def test_valid_same_version_restore_allowed(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="1.0",
                current_schema_version="1.0",
                target_environment="local",
                allow_overwrite=True,
                has_backup_database=True,
                has_required_items=True,
            )
        )
        assert result.status == RestorePreflightStatus.ALLOWED
        assert result.risk == BackupRestoreRisk.LOW
        assert result.blockers == []

    def test_older_backup_schema_allowed_with_warning(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="0.9",
                current_schema_version="1.0",
                allow_overwrite=True,
                has_backup_database=True,
                has_required_items=True,
            )
        )
        assert result.status == RestorePreflightStatus.WARNING
        assert any("older" in warning.lower() for warning in result.warnings)

    def test_blockers_and_warnings_are_operator_readable(self):
        result = evaluate_restore_preflight(
            RestorePreflightInput(
                manifest_schema_version="2.0",
                current_schema_version="1.0",
                allow_overwrite=False,
                has_backup_database=False,
                has_required_items=False,
                contains_provider_secrets=True,
                contains_external_project_files=True,
            )
        )
        combined = result.blockers + result.warnings + result.required_operator_confirmations
        assert combined
        assert all(isinstance(item, str) and len(item.split()) >= 3 for item in combined)


class TestOperatorChecklists:
    def test_backup_checklist_mentions_stop_app_copy_db_verify_manifest(self):
        text = "\n".join(build_backup_operator_checklist()).lower()
        assert "stop the app" in text
        assert "copy the ai workbench sqlite database" in text
        assert "verify schema_version" in text

    def test_restore_checklist_mentions_backup_current_state_first(self):
        text = "\n".join(build_restore_operator_checklist()).lower()
        assert "back up the current state" in text

    def test_restore_checklist_mentions_schema_compatibility(self):
        text = "\n".join(build_restore_operator_checklist()).lower()
        assert "schema compatibility" in text

    def test_restore_checklist_mentions_provider_secrets(self):
        text = "\n".join(build_restore_operator_checklist()).lower()
        assert "provider secrets" in text

    def test_restore_checklist_mentions_validation_after_restore(self):
        text = "\n".join(build_restore_operator_checklist()).lower()
        assert "validate projects" in text
        assert "after restore" in text


class TestContractSafety:
    def test_contract_module_has_no_subprocess(self):
        assert "subprocess" not in inspect.getsource(contract)

    def test_contract_module_has_no_os_system_or_popen(self):
        source = inspect.getsource(contract)
        assert "os.system" not in source
        assert "os.popen" not in source

    def test_contract_module_has_no_execute_run(self):
        assert "execute_run(" not in inspect.getsource(contract)

    def test_contract_module_has_no_asyncio_create_task(self):
        assert "asyncio.create_task(" not in inspect.getsource(contract)

    def test_contract_module_has_no_provider_imports_or_calls(self):
        source = inspect.getsource(contract)
        assert "src.providers" not in source
        assert "ollama.chat_completion" not in source
        assert "claude_provider" not in source
        assert "codex" not in source.lower()

    def test_contract_module_has_no_database_import_or_connection(self):
        source = inspect.getsource(contract)
        assert "src.storage.database" not in source
        assert "_connect" not in source

    def test_contract_module_does_not_read_or_write_files(self):
        source = inspect.getsource(contract)
        assert "open(" not in source
        assert ".read_text(" not in source
        assert ".write_text(" not in source
        assert ".write_bytes(" not in source

    def test_importing_module_has_no_side_effects(self):
        loaded = importlib.import_module("src.release.migration_backup_restore_contract")
        assert loaded.MIGRATION_BACKUP_RESTORE_SCHEMA_VERSION == "1.0"


class TestCompatibilitySignals:
    def test_sensitivity_classifier_marks_database_sensitive(self):
        item = BackupManifestItem(kind=BackupItemKind.DATABASE, name="db", path_hint="data/workbench.db")
        assert classify_backup_item_sensitivity(item) == BackupItemSensitivity.SENSITIVE

    def test_release_contract_module_exports_expected_helpers(self):
        for name in (
            "build_default_backup_manifest",
            "validate_backup_manifest",
            "evaluate_restore_preflight",
            "build_backup_operator_checklist",
            "build_restore_operator_checklist",
            "redact_manifest_for_report",
        ):
            assert hasattr(contract, name)

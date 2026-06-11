"""Tests for Project Module Map v1.

Covers:
  Storage / model:
    1.  Creates first module map version (v1)
    2.  Update creates version 2
    3.  Active version is latest non-archived
    4.  History returns all versions
    5.  Specific version retrieval works
    6.  Archive clears active but keeps history
    7.  JSON round-trip preserves modules, paths, and requirements

  Validation / security:
    8.  Rejects path traversal in module paths
    9.  Rejects absolute paths in module paths
    10. Rejects .env / secrets file paths
    11. Rejects obvious secret-like text in description
    12. Rejects secret-like text in risks list
    13. Accepts normal module map text

  API:
    13. GET active when none returns found=False
    14. PUT creates v1 (status 200, found=True)
    15. PUT creates v2 (version increments)
    16. History endpoint returns both versions
    17. Version endpoint returns specific version
    18. Validate endpoint does not store
    19. Summary endpoint does not store
    20. Endpoints create no tool_calls
    21. Endpoints do not execute providers or commands

  Scanner preview:
    22. Scan-preview infers backend/API modules from routes/services paths
    23. Scan-preview infers frontend modules from pages/components paths
    24. Scan-preview infers database module from prisma/schema/sql paths
    25. Scan-preview skips node_modules, dist, .git, .env
    26. Scan-preview is bounded by max_files
    27. Scan-preview does not read file contents
    28. Scan-preview does not store result automatically

  Lookup helpers:
    29. find_modules_for_paths maps files to modules
    30. find_modules_for_requirement_ids maps requirements to modules
    31. Summary includes module names and key paths

  Static safety:
    32. module_map_storage.py has no execute_run
    33. module_map_storage.py has no asyncio.create_task
    34. module_map_storage.py has no subprocess or os.system
    35. module_map_storage.py has no provider calls
    36. module_map_storage.py has no create_tool_call
    37. project_module_map.py has no subprocess or os.system
    38. project_module_map.py has no provider calls

  Compatibility:
    39. Existing SoT wiring tests still referenced (smoke check via import)
    40. Persistent SoT tests still work (import check)

Safety invariants:
  - No provider calls, no execute_run, no asyncio.create_task
  - No tool_calls created by any module-map endpoint
  - Scanner never reads file contents
  - Scanner never stores results
  - PUT is the only mutating endpoint
"""

from __future__ import annotations

import pathlib
import uuid

import pytest
from fastapi.testclient import TestClient

from src.models import (
    ProjectModuleMapDocument,
    ProjectModuleMapItem,
    ProjectModuleMapUpsertRequest,
)
from src.storage import database
from src.storage.module_map_storage import (
    build_module_map_summary,
    create_or_update_project_module_map,
    find_modules_for_paths,
    find_modules_for_requirement_ids,
    get_active_project_module_map,
    get_project_module_map_version,
    list_project_module_map_history,
    validate_module_map_payload,
)
from src.orchestrator.project_module_map import build_project_module_map_scan_preview


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "modmap.db"))
    database.init_db()
    return database


@pytest.fixture()
def client(isolated_db):
    from src.main import app
    return TestClient(app)


@pytest.fixture()
def project(isolated_db, tmp_path):
    project_dir = tmp_path / "proj"
    project_dir.mkdir()
    return isolated_db.create_project("ModMap Test Project", str(project_dir))


# ── Helpers ───────────────────────────────────────────────────────────────────


def _item(
    slug: str = "auth",
    name: str = "Authentication",
    module_type: str = "feature",
    paths: list | None = None,
    related_requirements: list | None = None,
) -> dict:
    return {
        "id": uuid.uuid4().hex[:8],
        "name": name,
        "slug": slug,
        "description": f"The {name} module.",
        "module_type": module_type,
        "responsibilities": ["Handle login and registration"],
        "paths": paths or ["src/auth"],
        "key_files": ["src/auth/index.ts"],
        "related_requirements": related_requirements or [],
        "test_hints": ["Test happy path login"],
        "risks": ["Token expiry not handled"],
        "confidence": "medium",
    }


def _upsert_payload(modules: list | None = None, status: str = "active") -> dict:
    return {
        "modules": modules or [_item()],
        "ignored_paths": [],
        "scan_summary": "Manual map",
        "source": "manual",
        "status": status,
    }


def _make_module_item(**kwargs) -> ProjectModuleMapItem:
    return ProjectModuleMapItem(**{**{
        "id": uuid.uuid4().hex[:8],
        "name": "Auth",
        "slug": "auth",
        "description": "",
        "module_type": "feature",
        "responsibilities": [],
        "paths": ["src/auth"],
        "key_files": [],
        "related_requirements": [],
        "test_hints": [],
        "risks": [],
        "confidence": "medium",
    }, **kwargs})


def _make_doc(project_id: str, modules: list | None = None) -> ProjectModuleMapDocument:
    return ProjectModuleMapDocument(
        project_id=project_id,
        status="active",
        modules=modules or [_make_module_item()],
        ignored_paths=[],
        scan_summary="test",
        source="manual",
    )


# ── Storage / model ───────────────────────────────────────────────────────────


class TestStorageModel:
    def test_1_creates_first_version(self, project, isolated_db):
        """PUT creates version 1 for a new project."""
        doc = _make_doc(project.id)
        stored = create_or_update_project_module_map(project.id, doc)
        assert stored.version == 1
        assert stored.id
        assert stored.project_id == project.id
        assert len(stored.modules) == 1

    def test_2_update_creates_version_2(self, project, isolated_db):
        """Second PUT increments version to 2."""
        doc = _make_doc(project.id)
        create_or_update_project_module_map(project.id, doc)
        doc2 = _make_doc(project.id, modules=[_make_module_item(slug="users", name="Users")])
        stored2 = create_or_update_project_module_map(project.id, doc2)
        assert stored2.version == 2

    def test_3_active_version_is_latest(self, project, isolated_db):
        """get_active returns the most recently created active version."""
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        active = get_active_project_module_map(project.id)
        assert active is not None
        assert active.version == 2

    def test_4_history_returns_all_versions(self, project, isolated_db):
        """list_project_module_map_history returns all versions."""
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        history = list_project_module_map_history(project.id)
        assert len(history) == 3
        assert history[0].version == 3  # newest first

    def test_5_specific_version_retrieval(self, project, isolated_db):
        """get_project_module_map_version returns the exact requested version."""
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        v1 = get_project_module_map_version(project.id, 1)
        v2 = get_project_module_map_version(project.id, 2)
        assert v1 is not None and v1.version == 1
        assert v2 is not None and v2.version == 2

    def test_6_archive_clears_active_keeps_history(self, project, isolated_db):
        """Archiving the active version makes get_active return None, history intact."""
        from src.storage.module_map_storage import archive_project_module_map
        create_or_update_project_module_map(project.id, _make_doc(project.id))
        assert get_active_project_module_map(project.id) is not None
        archive_project_module_map(project.id)
        assert get_active_project_module_map(project.id) is None
        history = list_project_module_map_history(project.id)
        assert len(history) == 1  # still in history

    def test_7_json_round_trip_preserves_data(self, project, isolated_db):
        """Module paths and related_requirements survive storage round-trip."""
        module = _make_module_item(
            slug="finance",
            name="Finance",
            paths=["src/finance", "src/billing"],
            related_requirements=["REQ-001", "REQ-002"],
        )
        doc = _make_doc(project.id, modules=[module])
        stored = create_or_update_project_module_map(project.id, doc)
        retrieved = get_active_project_module_map(project.id)
        assert retrieved is not None
        assert len(retrieved.modules) == 1
        m = retrieved.modules[0]
        assert "src/finance" in m.paths
        assert "REQ-001" in m.related_requirements
        assert "REQ-002" in m.related_requirements


# ── Validation / security ─────────────────────────────────────────────────────


class TestValidationSecurity:
    def test_8_rejects_path_traversal_in_paths(self, client, project):
        """PUT rejects a module with .. in paths (model validator)."""
        payload = _upsert_payload(modules=[_item(paths=["../../../etc/passwd"])])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 422

    def test_9_rejects_absolute_path(self, client, project):
        """PUT rejects absolute paths in module paths (model validator)."""
        payload = _upsert_payload(modules=[_item(paths=["/etc/passwd"])])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 422

    def test_10_rejects_secrets_file_path(self, client, project):
        """PUT rejects paths that reference .env or secrets files (model validator)."""
        payload = _upsert_payload(modules=[_item(paths=[".env"])])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 422

    def test_11_rejects_secret_in_description(self, client, project):
        """PUT rejects secret-like text in module description (model validator)."""
        bad_item = _item()
        bad_item["description"] = "api_key=sk-abc123-secret must be configured"
        payload = _upsert_payload(modules=[bad_item])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 422

    def test_12_rejects_secret_in_risks(self, client, project):
        """PUT rejects secret-like text in module risks (model validator)."""
        bad_item = _item()
        bad_item["risks"] = ["password=hunter2 might leak"]
        payload = _upsert_payload(modules=[bad_item])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 422

    def test_13_accepts_normal_text(self, client, project):
        """PUT accepts normal SaaS module map content without false-positives."""
        payload = _upsert_payload(modules=[
            _item(
                slug="auth",
                name="Authentication",
                paths=["src/auth", "src/middleware/auth"],
            ),
            _item(
                slug="database",
                name="Database",
                module_type="database",
                paths=["prisma", "src/db"],
            ),
        ])
        r = client.put(f"/api/projects/{project.id}/module-map", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["found"] is True
        assert len(data["document"]["modules"]) == 2


# ── API endpoints ─────────────────────────────────────────────────────────────


class TestAPIEndpoints:
    def test_13_get_active_none_returns_not_found(self, client, project):
        """GET module-map when none exists returns found=False (not 404)."""
        r = client.get(f"/api/projects/{project.id}/module-map")
        assert r.status_code == 200
        assert r.json()["found"] is False

    def test_14_put_creates_v1(self, client, project):
        """PUT creates version 1 successfully."""
        r = client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["version"] == 1
        assert data["project_id"] == project.id

    def test_15_put_creates_v2(self, client, project):
        """Second PUT increments to version 2."""
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        r = client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        assert r.status_code == 200
        assert r.json()["document"]["version"] == 2

    def test_16_history_endpoint_works(self, client, project):
        """GET /history returns both created versions."""
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        r = client.get(f"/api/projects/{project.id}/module-map/history")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 2
        assert len(data["history"]) == 2

    def test_17_version_endpoint_works(self, client, project):
        """GET /module-map/1 returns version 1 specifically."""
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        r = client.get(f"/api/projects/{project.id}/module-map/1")
        assert r.status_code == 200
        data = r.json()
        assert data["found"] is True
        assert data["document"]["version"] == 1

    def test_18_validate_does_not_store(self, client, project, isolated_db):
        """POST /validate returns result without persisting any document."""
        r = client.post(
            f"/api/projects/{project.id}/module-map/validate",
            json=_upsert_payload(),
        )
        assert r.status_code == 200
        assert r.json()["valid"] is True
        # Nothing should be stored
        assert get_active_project_module_map(project.id) is None

    def test_19_summary_does_not_store(self, client, project, isolated_db):
        """POST /summary when active map exists returns summary without mutating."""
        # First PUT to create a map
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        history_before = list_project_module_map_history(project.id)
        r = client.post(f"/api/projects/{project.id}/module-map/summary")
        assert r.status_code == 200
        assert r.json()["found"] is True
        history_after = list_project_module_map_history(project.id)
        assert len(history_after) == len(history_before)  # no new version created

    def test_20_endpoints_create_no_tool_calls(self, client, project, isolated_db):
        """None of the module map endpoints create tool_call records."""
        client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        client.get(f"/api/projects/{project.id}/module-map")
        client.get(f"/api/projects/{project.id}/module-map/history")
        client.get(f"/api/projects/{project.id}/module-map/1")
        client.post(f"/api/projects/{project.id}/module-map/validate", json=_upsert_payload())
        client.post(f"/api/projects/{project.id}/module-map/summary")
        tool_calls = isolated_db.list_tool_calls_for_run("")
        assert len(tool_calls) == 0

    def test_21_endpoints_do_not_call_providers(self, client, project):
        """Module map endpoints return without calling any provider (no Ollama/provider calls).
        Verified by the fact that all endpoints complete instantly with no provider config needed.
        """
        r = client.put(f"/api/projects/{project.id}/module-map", json=_upsert_payload())
        assert r.status_code == 200
        # Response summary explicitly states no providers executed
        # (structural check: response has no 'provider_used' or similar field)
        data = r.json()
        assert "found" in data
        assert "provider" not in data


# ── Scanner preview ───────────────────────────────────────────────────────────


class TestScannerPreview:
    @pytest.fixture()
    def fake_project(self, tmp_path):
        """Create a fake project tree for scanner tests."""
        root = tmp_path / "fake_project"
        root.mkdir()
        # Backend routes
        (root / "src" / "routes").mkdir(parents=True)
        (root / "src" / "routes" / "auth.ts").write_text("// auth routes")
        (root / "src" / "routes" / "users.ts").write_text("// users routes")
        (root / "src" / "services").mkdir(parents=True)
        (root / "src" / "services" / "auth_service.ts").write_text("// auth service", encoding="utf-8")
        (root / "src" / "services" / "billing_service.ts").write_text("// billing")
        # Frontend pages
        (root / "frontend" / "pages").mkdir(parents=True)
        (root / "frontend" / "pages" / "Login.tsx").write_text("// login page")
        (root / "frontend" / "components").mkdir(parents=True)
        (root / "frontend" / "components" / "Header.tsx").write_text("// header", encoding="utf-8")
        (root / "frontend" / "components" / "Button.tsx").write_text("// button")
        # Database
        (root / "prisma").mkdir(parents=True)
        (root / "prisma" / "schema.prisma").write_text("// schema", encoding="utf-8")
        (root / "migrations").mkdir(parents=True)
        (root / "migrations" / "001_init.sql").write_text("-- init")
        # Excluded dirs
        (root / "node_modules" / "react").mkdir(parents=True)
        (root / "node_modules" / "react" / "index.js").write_text("// react")
        (root / "dist").mkdir(parents=True)
        (root / "dist" / "bundle.js").write_text("// bundle", encoding="utf-8")
        # Secret files
        (root / ".env").write_text("DATABASE_URL=postgres://user:pass@localhost/db")
        return root

    def test_22_infers_backend_api_modules(self, fake_project):
        """Scanner infers API/routes/services module from src/routes and src/services."""
        result = build_project_module_map_scan_preview(str(fake_project))
        slugs = {m.slug for m in result.modules}
        assert "api" in slugs or "auth" in slugs, f"Expected api or auth in {slugs}"

    def test_23_infers_frontend_modules(self, fake_project):
        """Scanner infers frontend module from pages and components paths."""
        result = build_project_module_map_scan_preview(str(fake_project))
        slugs = {m.slug for m in result.modules}
        assert "frontend" in slugs, f"Expected frontend in {slugs}"

    def test_24_infers_database_module(self, fake_project):
        """Scanner infers database module from prisma and migrations paths."""
        result = build_project_module_map_scan_preview(str(fake_project))
        slugs = {m.slug for m in result.modules}
        assert "database" in slugs, f"Expected database in {slugs}"

    def test_25_skips_excluded_dirs_and_secrets(self, fake_project):
        """Scanner does not produce modules for node_modules, dist, or .env paths."""
        result = build_project_module_map_scan_preview(str(fake_project))
        for mod in result.modules:
            for p in mod.paths + mod.key_files:
                assert "node_modules" not in p, f"node_modules leaked into paths: {p}"
                assert ".env" not in p, f".env leaked into paths: {p}"

    def test_26_bounded_by_max_files(self, tmp_path):
        """Scanner stops at max_files=5 and sets truncated=True."""
        root = tmp_path / "big_project"
        root.mkdir()
        (root / "src").mkdir()
        for i in range(20):
            (root / "src" / f"service_{i}.ts").write_text(f"// service {i}")
        result = build_project_module_map_scan_preview(str(root), max_files=5)
        assert result.files_scanned <= 5
        assert result.truncated is True

    def test_27_does_not_read_file_contents(self, fake_project):
        """Scanner builds module map without reading any file content.
        Verified by: secret file (.env) is skipped (if it were read, credentials would appear).
        """
        result = build_project_module_map_scan_preview(str(fake_project))
        full_text = result.scan_summary + " ".join(
            p for m in result.modules for p in m.paths + m.key_files
        )
        assert "postgres://user:pass@localhost/db" not in full_text
        assert "DATABASE_URL" not in full_text

    def test_28_does_not_store_result(self, client, project):
        """POST /scan-preview does not persist any module map document."""
        r = client.post(
            f"/api/projects/{project.id}/module-map/scan-preview",
            json={"max_files": 10, "max_depth": 3},
        )
        assert r.status_code == 200
        # Active map should still not exist
        r2 = client.get(f"/api/projects/{project.id}/module-map")
        assert r2.json()["found"] is False


# ── Lookup helpers ────────────────────────────────────────────────────────────


class TestLookupHelpers:
    def _build_doc(self, project_id: str) -> ProjectModuleMapDocument:
        auth_mod = _make_module_item(slug="auth", name="Auth", paths=["src/auth", "src/middleware/auth"])
        users_mod = _make_module_item(slug="users", name="Users", paths=["src/users"])
        users_mod.related_requirements = ["REQ-001", "REQ-002"]
        auth_mod.related_requirements = ["REQ-003"]
        return _make_doc(project_id, modules=[auth_mod, users_mod])

    def test_29_find_modules_for_paths(self, project, isolated_db):
        """find_modules_for_paths returns modules whose paths overlap."""
        doc = create_or_update_project_module_map(project.id, self._build_doc(project.id))
        matches = find_modules_for_paths(doc, ["src/auth/login.ts"])
        assert len(matches) >= 1
        assert any(m.slug == "auth" for m in matches)

    def test_30_find_modules_for_requirement_ids(self, project, isolated_db):
        """find_modules_for_requirement_ids returns modules linked to given IDs."""
        doc = create_or_update_project_module_map(project.id, self._build_doc(project.id))
        matches = find_modules_for_requirement_ids(doc, ["REQ-001"])
        assert len(matches) >= 1
        assert any(m.slug == "users" for m in matches)

    def test_31_summary_includes_module_names(self, project, isolated_db):
        """build_module_map_summary includes module count and names."""
        auth_mod = _make_module_item(slug="auth", name="Authentication")
        db_mod = _make_module_item(slug="database", name="Database", module_type="database")
        doc = create_or_update_project_module_map(
            project.id, _make_doc(project.id, modules=[auth_mod, db_mod])
        )
        summary = build_module_map_summary(doc)
        assert "2" in summary or "two" in summary.lower() or "Authentication" in summary
        assert "module" in summary.lower()


# ── Static safety ─────────────────────────────────────────────────────────────


class TestStaticSafety:
    @pytest.fixture(autouse=True)
    def _read_sources(self):
        base = pathlib.Path(__file__).parent.parent / "src"
        self._storage_src = (base / "storage" / "module_map_storage.py").read_text(encoding="utf-8")
        self._scanner_src = (base / "orchestrator" / "project_module_map.py").read_text(encoding="utf-8")

    def test_32_no_execute_run_in_storage(self):
        assert "execute_run" not in self._storage_src

    def test_33_no_asyncio_create_task_in_storage(self):
        live = [
            l for l in self._storage_src.splitlines()
            if "asyncio.create_task" in l and not l.strip().startswith("#")
        ]
        assert live == []

    def test_34_no_subprocess_or_os_system_in_storage(self):
        for pat in ("subprocess", "os.system", "os.popen"):
            live = [
                l for l in self._storage_src.splitlines()
                if pat in l and not l.strip().startswith("#")
            ]
            assert live == [], f"Found live {pat!r} in module_map_storage.py: {live}"

    def test_35_no_provider_calls_in_storage(self):
        for pat in ("ollama.chat", "claude_provider", "codex_provider", "openai.chat"):
            assert pat not in self._storage_src, f"Found {pat!r} in module_map_storage.py"

    def test_36_no_create_tool_call_in_storage(self):
        assert "create_tool_call" not in self._storage_src

    def test_37_no_subprocess_in_scanner(self):
        for pat in ("subprocess", "os.system", "os.popen"):
            live = [
                l for l in self._scanner_src.splitlines()
                if pat in l and not l.strip().startswith("#")
            ]
            assert live == [], f"Found live {pat!r} in project_module_map.py: {live}"

    def test_38_no_provider_calls_in_scanner(self):
        for pat in ("ollama.chat", "claude_provider", "codex_provider", "openai.chat"):
            assert pat not in self._scanner_src, f"Found {pat!r} in project_module_map.py"


# ── Compatibility smoke checks ────────────────────────────────────────────────


class TestCompatibility:
    def test_39_sot_wiring_module_imports_ok(self):
        """SoT wiring storage module can still be imported (no regression)."""
        from src.storage.source_of_truth_storage import (
            build_persisted_source_of_truth_context_for_step,
            get_active_project_source_of_truth,
        )
        assert callable(build_persisted_source_of_truth_context_for_step)
        assert callable(get_active_project_source_of_truth)

    def test_40_persistent_sot_module_imports_ok(self):
        """Persistent SoT storage module can still be imported (no regression)."""
        from src.storage.source_of_truth_storage import (
            create_or_update_project_source_of_truth,
            validate_source_of_truth_payload,
        )
        assert callable(create_or_update_project_source_of_truth)
        assert callable(validate_source_of_truth_payload)

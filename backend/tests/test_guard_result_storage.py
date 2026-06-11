"""Tests for guard_result_storage.py — isolated CRUD helpers.

Uses the isolated_db pattern (monkeypatch DB_PATH to tmp_path).
Verifies serialization round-trips, staleness, linking, and safety.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from src.orchestrator.guard_result_storage_contract import (
    WorkflowGuardDecision,
    WorkflowGuardDriftRisk,
    WorkflowGuardSource,
    WorkflowGuardStaleReason,
    build_guard_input_snapshot,
    build_guard_result_snapshot,
    build_requirement_context_snapshot,
    build_workflow_guard_result_record,
)
from src.storage import database


@pytest.fixture()
def isolated_db(monkeypatch, tmp_path):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "workbench.db"))
    database.init_db()
    return database


@pytest.fixture()
def storage(isolated_db):
    """Import storage module after DB is patched."""
    from src.storage import guard_result_storage

    return guard_result_storage


def _make_record(
    *,
    record_id: str = "gr-001",
    run_id: str = "run-001",
    step_id: str = "step-001",
    project_id: str | None = None,
    decision: WorkflowGuardDecision = WorkflowGuardDecision.ALLOWED,
    drift_risk: WorkflowGuardDriftRisk = WorkflowGuardDriftRisk.LOW,
    proposed_action: str = "Add error handling to api_handler.py",
    file_path: str | None = "backend/src/api/handler.py",
    patch_summary: str | None = "Add try/except block",
    warning_acknowledged: bool = False,
    no_guard_override: bool = False,
    expires_at: datetime | None = None,
) -> "WorkflowGuardResultRecord":
    input_snap = build_guard_input_snapshot(
        proposed_action=proposed_action,
        file_path=file_path,
        patch_summary=patch_summary,
        old_text="old code here",
        new_text="new code here",
    )
    ctx_snap = build_requirement_context_snapshot(
        requirement_ids=["REQ-001", "REQ-002"],
        coverage_status="partially_covered",
        drift_risk=WorkflowGuardDriftRisk.MEDIUM,
        acceptance_criteria=["Tests pass", "No regressions"],
        constraints=["Do not modify database.py"],
        forbidden_changes=["Do not delete safety checks"],
        validation_notes=["Step covers auth module"],
        source_of_truth_summary="Auth module SoT v1",
    )
    result_snap = build_guard_result_snapshot(
        decision=decision,
        drift_risk=drift_risk,
        matched_requirement_ids=["REQ-001"],
        violated_constraints=[],
        forbidden_change_hits=[],
        warnings=["Minor drift detected"] if decision == WorkflowGuardDecision.WARNING else [],
        reasons=["Allowed by SoT guard"],
        recommended_next_step="Proceed with patch proposal",
    )
    return build_workflow_guard_result_record(
        id=record_id,
        run_id=run_id,
        step_id=step_id,
        project_id=project_id,
        input_snapshot=input_snap,
        requirement_context_snapshot=ctx_snap,
        result_snapshot=result_snap,
        source=WorkflowGuardSource.RUN_STEP_GUARD,
        warning_acknowledged=warning_acknowledged,
        no_guard_override=no_guard_override,
        expires_at=expires_at,
    )


class TestGuardResultsTableCreation:
    """Verify init_db creates the guard_results table."""

    def test_guard_results_table_exists(self, isolated_db):
        conn = database._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guard_results'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1
        assert tables[0]["name"] == "guard_results"

    def test_guard_results_indexes_exist(self, isolated_db):
        conn = database._connect()
        indexes = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_guard_results_%'"
        ).fetchall()
        conn.close()
        index_names = {row["name"] for row in indexes}
        assert "idx_guard_results_run_step" in index_names
        assert "idx_guard_results_project" in index_names
        assert "idx_guard_results_decision" in index_names
        assert "idx_guard_results_stale" in index_names


class TestCreateGuardResult:
    """Test create_guard_result persistence and round-trip."""

    def test_create_and_get(self, storage):
        record = _make_record()
        created = storage.create_guard_result(record)
        assert created.id == "gr-001"
        assert created.run_id == "run-001"
        assert created.step_id == "step-001"

        fetched = storage.get_guard_result("gr-001")
        assert fetched is not None
        assert fetched.id == "gr-001"
        assert fetched.run_id == "run-001"
        assert fetched.step_id == "step-001"
        assert fetched.source == WorkflowGuardSource.RUN_STEP_GUARD
        assert fetched.result_snapshot.decision == WorkflowGuardDecision.ALLOWED
        assert fetched.result_snapshot.drift_risk == WorkflowGuardDriftRisk.LOW

    def test_input_snapshot_round_trip(self, storage):
        record = _make_record(
            proposed_action="Refactor auth module",
            file_path="backend/src/auth.py",
            patch_summary="Extract helper functions",
        )
        storage.create_guard_result(record)
        fetched = storage.get_guard_result(record.id)
        assert fetched is not None
        assert fetched.input_snapshot.proposed_action == "Refactor auth module"
        assert fetched.input_snapshot.file_path == "backend/src/auth.py"
        assert fetched.input_snapshot.patch_summary == "Extract helper functions"
        assert fetched.input_snapshot.input_hash == record.input_snapshot.input_hash

    def test_requirement_context_snapshot_round_trip(self, storage):
        record = _make_record()
        storage.create_guard_result(record)
        fetched = storage.get_guard_result(record.id)
        assert fetched is not None
        ctx = fetched.requirement_context_snapshot
        assert ctx.requirement_ids == ["REQ-001", "REQ-002"]
        assert ctx.coverage_status == "partially_covered"
        assert ctx.acceptance_criteria == ["Tests pass", "No regressions"]
        assert ctx.constraints == ["Do not modify database.py"]
        assert ctx.forbidden_changes == ["Do not delete safety checks"]
        assert ctx.validation_notes == ["Step covers auth module"]
        assert ctx.source_of_truth_summary == "Auth module SoT v1"
        assert ctx.context_hash == record.requirement_context_snapshot.context_hash

    def test_result_snapshot_round_trip(self, storage):
        record = _make_record()
        storage.create_guard_result(record)
        fetched = storage.get_guard_result(record.id)
        assert fetched is not None
        rs = fetched.result_snapshot
        assert rs.decision == WorkflowGuardDecision.ALLOWED
        assert rs.drift_risk == WorkflowGuardDriftRisk.LOW
        assert rs.matched_requirement_ids == ["REQ-001"]
        assert rs.violated_constraints == []
        assert rs.forbidden_change_hits == []
        assert rs.reasons == ["Allowed by SoT guard"]
        assert rs.recommended_next_step == "Proceed with patch proposal"
        assert rs.result_hash == record.result_snapshot.result_hash

    def test_warning_acknowledged_round_trip(self, storage):
        record = _make_record(
            record_id="gr-ack",
            decision=WorkflowGuardDecision.WARNING,
            warning_acknowledged=True,
        )
        storage.create_guard_result(record)
        fetched = storage.get_guard_result("gr-ack")
        assert fetched is not None
        assert fetched.warning_acknowledged is True

    def test_no_guard_override_round_trip(self, storage):
        record = _make_record(
            record_id="gr-override",
            decision=WorkflowGuardDecision.WARNING,
            no_guard_override=True,
        )
        storage.create_guard_result(record)
        fetched = storage.get_guard_result("gr-override")
        assert fetched is not None
        assert fetched.no_guard_override is True

    def test_expires_at_round_trip(self, storage):
        future = datetime.now() + timedelta(hours=1)
        record = _make_record(record_id="gr-exp", expires_at=future)
        storage.create_guard_result(record)
        fetched = storage.get_guard_result("gr-exp")
        assert fetched is not None
        assert fetched.expires_at is not None
        # Compare to the second (datetime round-trip via isoformat).
        assert abs((fetched.expires_at - future).total_seconds()) < 1

    def test_get_nonexistent_returns_none(self, storage):
        assert storage.get_guard_result("does-not-exist") is None

    def test_raw_old_text_new_text_not_stored_in_db(self, storage, isolated_db):
        """The input_snapshot stores hashes, never raw old_text/new_text."""
        record = _make_record(record_id="gr-hash-check")
        storage.create_guard_result(record)

        # Read raw JSON from DB.
        conn = database._connect()
        row = conn.execute(
            "SELECT input_snapshot_json FROM guard_results WHERE id=?",
            ("gr-hash-check",),
        ).fetchone()
        conn.close()
        raw = json.loads(row["input_snapshot_json"])
        # Must have hashes, not raw text.
        assert "old_text_hash" in raw
        assert "new_text_hash" in raw
        assert raw["old_text_hash"] is not None
        assert raw["new_text_hash"] is not None
        # The raw text fields must not be present.
        assert "old_text" not in raw
        assert "new_text" not in raw


class TestListGuardResults:
    """Test list_guard_results with various filters."""

    def _seed(self, storage):
        for i in range(5):
            decision = WorkflowGuardDecision.WARNING if i == 2 else WorkflowGuardDecision.ALLOWED
            record = _make_record(
                record_id=f"gr-list-{i}",
                run_id="run-A" if i < 3 else "run-B",
                step_id=f"step-{i}",
                project_id="proj-1" if i < 4 else "proj-2",
                decision=decision,
            )
            storage.create_guard_result(record)

    def test_list_all_non_stale(self, storage):
        self._seed(storage)
        results = storage.list_guard_results()
        assert len(results) == 5

    def test_filter_by_run_id(self, storage):
        self._seed(storage)
        results = storage.list_guard_results(run_id="run-A")
        assert len(results) == 3
        assert all(r.run_id == "run-A" for r in results)

    def test_filter_by_step_id(self, storage):
        self._seed(storage)
        results = storage.list_guard_results(step_id="step-2")
        assert len(results) == 1
        assert results[0].step_id == "step-2"

    def test_filter_by_project_id(self, storage):
        self._seed(storage)
        results = storage.list_guard_results(project_id="proj-1")
        assert len(results) == 4

    def test_filter_by_decision(self, storage):
        self._seed(storage)
        results = storage.list_guard_results(decision="warning")
        assert len(results) == 1
        assert results[0].result_snapshot.decision == WorkflowGuardDecision.WARNING

    def test_include_stale_false_hides_stale(self, storage):
        self._seed(storage)
        storage.mark_guard_result_stale(
            "gr-list-0", WorkflowGuardStaleReason.EXPIRED
        )
        results = storage.list_guard_results(include_stale=False)
        assert len(results) == 4
        assert all(r.id != "gr-list-0" for r in results)

    def test_include_stale_true_includes_stale(self, storage):
        self._seed(storage)
        storage.mark_guard_result_stale(
            "gr-list-0", WorkflowGuardStaleReason.EXPIRED
        )
        results = storage.list_guard_results(include_stale=True)
        assert len(results) == 5

    def test_limit_and_offset(self, storage):
        self._seed(storage)
        results = storage.list_guard_results(limit=2, offset=0)
        assert len(results) == 2
        results2 = storage.list_guard_results(limit=2, offset=2)
        assert len(results2) == 2
        # No overlap.
        ids1 = {r.id for r in results}
        ids2 = {r.id for r in results2}
        assert ids1.isdisjoint(ids2)


class TestMarkGuardResultStale:
    """Test staleness marking."""

    def test_mark_stale_sets_flag_and_reason(self, storage):
        record = _make_record(record_id="gr-stale")
        storage.create_guard_result(record)
        updated = storage.mark_guard_result_stale(
            "gr-stale", WorkflowGuardStaleReason.PROPOSED_ACTION_CHANGED
        )
        assert updated is not None
        assert updated.is_stale is True
        assert WorkflowGuardStaleReason.PROPOSED_ACTION_CHANGED in updated.stale_reasons
        assert updated.updated_at is not None

    def test_mark_stale_accumulates_reasons(self, storage):
        record = _make_record(record_id="gr-multi-stale")
        storage.create_guard_result(record)
        storage.mark_guard_result_stale(
            "gr-multi-stale", WorkflowGuardStaleReason.FILE_PATH_CHANGED
        )
        updated = storage.mark_guard_result_stale(
            "gr-multi-stale", WorkflowGuardStaleReason.OLD_TEXT_CHANGED
        )
        assert updated is not None
        assert WorkflowGuardStaleReason.FILE_PATH_CHANGED in updated.stale_reasons
        assert WorkflowGuardStaleReason.OLD_TEXT_CHANGED in updated.stale_reasons

    def test_mark_stale_deduplicates_reasons(self, storage):
        record = _make_record(record_id="gr-dedup")
        storage.create_guard_result(record)
        storage.mark_guard_result_stale(
            "gr-dedup", WorkflowGuardStaleReason.EXPIRED
        )
        updated = storage.mark_guard_result_stale(
            "gr-dedup", WorkflowGuardStaleReason.EXPIRED
        )
        assert updated is not None
        assert updated.stale_reasons.count(WorkflowGuardStaleReason.EXPIRED) == 1

    def test_mark_stale_nonexistent_returns_none(self, storage):
        result = storage.mark_guard_result_stale(
            "nope", WorkflowGuardStaleReason.MANUAL_INVALIDATION
        )
        assert result is None


class TestLinkGuardResult:
    """Test proposal and apply linking."""

    def test_link_to_proposal(self, storage):
        record = _make_record(record_id="gr-link-p")
        storage.create_guard_result(record)
        updated = storage.link_guard_result_to_proposal("gr-link-p", "tc-proposal-001")
        assert updated is not None
        assert updated.proposal_tool_call_id == "tc-proposal-001"
        assert updated.updated_at is not None

    def test_link_to_apply(self, storage):
        record = _make_record(record_id="gr-link-a")
        storage.create_guard_result(record)
        updated = storage.link_guard_result_to_apply("gr-link-a", "tc-apply-001")
        assert updated is not None
        assert updated.apply_tool_call_id == "tc-apply-001"
        assert updated.updated_at is not None

    def test_link_proposal_nonexistent_returns_none(self, storage):
        result = storage.link_guard_result_to_proposal("nope", "tc-001")
        assert result is None

    def test_link_apply_nonexistent_returns_none(self, storage):
        result = storage.link_guard_result_to_apply("nope", "tc-001")
        assert result is None

    def test_filter_by_proposal_tool_call_id(self, storage):
        record = _make_record(record_id="gr-filter-p")
        storage.create_guard_result(record)
        storage.link_guard_result_to_proposal("gr-filter-p", "tc-proposal-filter")
        results = storage.list_guard_results(
            proposal_tool_call_id="tc-proposal-filter"
        )
        assert len(results) == 1
        assert results[0].id == "gr-filter-p"


class TestModuleIsolation:
    """Verify the storage module does not create tool_calls or touch forbidden modules."""

    def test_no_tool_calls_created(self, storage, isolated_db):
        record = _make_record(record_id="gr-no-tc")
        storage.create_guard_result(record)
        storage.mark_guard_result_stale(
            "gr-no-tc", WorkflowGuardStaleReason.EXPIRED
        )
        storage.link_guard_result_to_proposal("gr-no-tc", "tc-check")

        # Verify no tool_calls exist.
        tool_calls = database.list_tool_calls_for_run("run-001")
        assert len(tool_calls) == 0

    def test_module_has_no_forbidden_imports(self):
        """The storage module must not import routes, engine, tools, or providers."""
        import importlib
        import inspect

        mod = importlib.import_module("src.storage.guard_result_storage")
        source = inspect.getsource(mod)
        forbidden = [
            "from src.api",
            "from src.orchestrator.engine",
            "from src.project_tools",
            "from src.model_router",
            "import routes",
            "import engine",
        ]
        for pattern in forbidden:
            assert pattern not in source, f"Forbidden import found: {pattern}"

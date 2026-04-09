from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.workflow.service import (
    FailureListEntry,
    MemoryStats,
    WorkflowListEntry,
    WorkflowStats,
)

from .conftest import (
    make_settings,
    patch_cli_connection_pool,
    patch_cli_postgres_config,
    patch_cli_postgres_uow_factory,
    patch_cli_settings,
    patch_cli_workflow_service,
)


def test_main_stats_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stats = WorkflowStats(
        workspace_count=40,
        workflow_status_counts={
            "running": 28,
            "completed": 30,
            "failed": 0,
            "cancelled": 0,
        },
        attempt_status_counts={
            "running": 3,
            "succeeded": 55,
            "failed": 0,
            "cancelled": 0,
        },
        verify_status_counts={
            "pending": 1,
            "passed": 51,
            "failed": 0,
            "skipped": 6,
        },
        checkpoint_count=57,
        episode_count=34,
        memory_item_count=24,
        memory_embedding_count=3,
        checkpoint_auto_memory_recorded_count=12,
        checkpoint_auto_memory_skipped_count=45,
        workflow_completion_auto_memory_recorded_count=4,
        workflow_completion_auto_memory_skipped_count=54,
        interaction_memory_item_count=7,
        file_work_memory_item_count=9,
        derived_memory_item_count=0,
        derived_memory_item_state="canonical_only",
        derived_memory_item_reason=(
            "canonical summary state exists but derived memory items are not materialized"
        ),
        derived_memory_graph_status="graph_ready",
        memory_summary_count=9,
        memory_summary_membership_count=21,
        age_summary_graph_ready_count=1,
        age_summary_graph_stale_count=0,
        age_summary_graph_degraded_count=0,
        age_summary_graph_unknown_count=0,
        completion_summary_build_request_count=3,
        completion_summary_build_attempted_count=2,
        completion_summary_build_success_count=1,
        completion_summary_build_skipped_reason_counts={
            "summary_build_failed": 1,
            "workflow_summary_build_not_requested": 2,
        },
        latest_workflow_updated_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        latest_checkpoint_created_at=datetime(2026, 3, 15, 9, 1, 0, tzinfo=UTC),
        latest_verify_report_created_at=datetime(2026, 3, 15, 9, 2, 0, tzinfo=UTC),
        latest_episode_created_at=datetime(2026, 3, 15, 9, 3, 0, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 15, 9, 4, 0, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 15, 9, 5, 0, tzinfo=UTC),
    )

    class FakeStatsWorkflowService:
        def __init__(self, stats_result: WorkflowStats) -> None:
            self.stats_result = stats_result
            self.get_stats_calls = 0

        def get_stats(self) -> WorkflowStats:
            self.get_stats_calls += 1
            return self.stats_result

    settings = make_settings()
    fake_service = FakeStatsWorkflowService(stats)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["stats"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ctxledger stats" in captured.out
    assert "Workspaces:" in captured.out
    assert "- total: 40" in captured.out
    assert "Workflows:" in captured.out
    assert "- running: 28" in captured.out
    assert "- completed: 30" in captured.out
    assert "Attempts:" in captured.out
    assert "- running: 3" in captured.out
    assert "- succeeded: 55" in captured.out
    assert "Verify reports:" in captured.out
    assert "- pending: 1" in captured.out
    assert "- passed: 51" in captured.out
    assert "- skipped: 6" in captured.out
    assert "Memory:" in captured.out
    assert "- episodes: 34" in captured.out
    assert "- memory_items: 24" in captured.out
    assert "- memory_embeddings: 3" in captured.out
    assert "- interaction_memory_items: 7" in captured.out
    assert "- file_work_memory_items: 9" in captured.out
    assert "- derived_memory_items: 0" in captured.out
    assert "Remember-path observability:" in captured.out
    assert "- checkpoint_auto_memory_recorded: 12" in captured.out
    assert "- checkpoint_auto_memory_skipped: 45" in captured.out
    assert "- workflow_completion_auto_memory_recorded: 4" in captured.out
    assert "- workflow_completion_auto_memory_skipped: 54" in captured.out
    assert "AGE operator metrics:" in captured.out
    assert "- memory_summaries: 9" in captured.out
    assert "- memory_summary_memberships: 21" in captured.out
    assert "- age_summary_graph_ready: 1" in captured.out
    assert "- age_summary_graph_stale: 0" in captured.out
    assert "- age_summary_graph_degraded: 0" in captured.out
    assert "- age_summary_graph_unknown: 0" in captured.out
    assert "Completion summary build observability:" in captured.out
    assert "- request_count: 3" in captured.out
    assert "- attempted_count: 2" in captured.out
    assert "- success_count: 1" in captured.out
    assert (
        "- skipped_reason_counts: {'summary_build_failed': 1, 'workflow_summary_build_not_requested': 2}"
        in captured.out
    )
    assert "Derived memory state:" in captured.out
    assert "- derived_memory_item_state: canonical_only" in captured.out
    assert (
        "- derived_memory_item_reason: canonical summary state exists but derived memory items are not materialized"
        in captured.out
    )
    assert "- derived_memory_graph_status: graph_ready" in captured.out
    assert "Other:" in captured.out
    assert "- checkpoints: 57" in captured.out
    assert "Latest activity:" in captured.out
    assert "2026-03-15 09:00:00+00:00" in captured.out
    assert "2026-03-15 09:01:00+00:00" in captured.out
    assert "2026-03-15 09:02:00+00:00" in captured.out
    assert "2026-03-15 09:03:00+00:00" in captured.out
    assert "2026-03-15 09:04:00+00:00" in captured.out
    assert "2026-03-15 09:05:00+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.get_stats_calls == 1


def test_main_stats_renders_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeStatsWorkflowService:
        def __init__(self, stats_result: WorkflowStats) -> None:
            self.stats_result = stats_result

        def get_stats(self) -> WorkflowStats:
            return self.stats_result

    stats = WorkflowStats(
        workspace_count=2,
        workflow_status_counts={
            "running": 1,
            "completed": 1,
            "failed": 0,
            "cancelled": 0,
        },
        attempt_status_counts={
            "running": 1,
            "succeeded": 1,
            "failed": 0,
            "cancelled": 0,
        },
        verify_status_counts={
            "pending": 0,
            "passed": 2,
            "failed": 0,
            "skipped": 0,
        },
        checkpoint_count=5,
        episode_count=3,
        memory_item_count=4,
        memory_embedding_count=1,
        checkpoint_auto_memory_recorded_count=0,
        checkpoint_auto_memory_skipped_count=0,
        workflow_completion_auto_memory_recorded_count=0,
        workflow_completion_auto_memory_skipped_count=0,
        interaction_memory_item_count=2,
        file_work_memory_item_count=3,
        derived_memory_item_count=0,
        derived_memory_item_state="canonical_only",
        derived_memory_item_reason=(
            "canonical summary state exists but derived memory items are not materialized"
        ),
        derived_memory_graph_status="graph_ready",
        memory_summary_count=2,
        memory_summary_membership_count=5,
        age_summary_graph_ready_count=1,
        age_summary_graph_stale_count=0,
        age_summary_graph_degraded_count=0,
        age_summary_graph_unknown_count=0,
        completion_summary_build_request_count=4,
        completion_summary_build_attempted_count=3,
        completion_summary_build_success_count=2,
        completion_summary_build_skipped_reason_counts={
            "summary_build_failed": 1,
            "workflow_summary_build_not_requested": 1,
        },
        latest_workflow_updated_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        latest_checkpoint_created_at=None,
        latest_verify_report_created_at=None,
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
    )

    settings = make_settings()

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, FakeStatsWorkflowService(stats))

    exit_code = cli_module.main(["stats", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == {
        "age_summary_graph_degraded_count": 0,
        "age_summary_graph_ready_count": 1,
        "age_summary_graph_stale_count": 0,
        "age_summary_graph_unknown_count": 0,
        "attempt_status_counts": {
            "cancelled": 0,
            "failed": 0,
            "running": 1,
            "succeeded": 1,
        },
        "checkpoint_auto_memory_recorded_count": 0,
        "checkpoint_auto_memory_skipped_count": 0,
        "checkpoint_count": 5,
        "completion_summary_build_attempted_count": 3,
        "completion_summary_build_request_count": 4,
        "completion_summary_build_skipped_reason_counts": {
            "summary_build_failed": 1,
            "workflow_summary_build_not_requested": 1,
        },
        "completion_summary_build_success_count": 2,
        "derived_memory_graph_status": "graph_ready",
        "derived_memory_item_count": 0,
        "derived_memory_item_reason": "canonical summary state exists but derived memory items are not materialized",
        "derived_memory_item_state": "canonical_only",
        "episode_count": 3,
        "file_work_memory_item_count": 3,
        "interaction_memory_item_count": 2,
        "latest_checkpoint_created_at": None,
        "latest_episode_created_at": None,
        "latest_memory_embedding_created_at": None,
        "latest_memory_item_created_at": None,
        "latest_verify_report_created_at": None,
        "latest_workflow_updated_at": "2026-03-15T09:00:00+00:00",
        "memory_embedding_count": 1,
        "memory_item_count": 4,
        "memory_summary_count": 2,
        "memory_summary_membership_count": 5,
        "structured_checkpoint_coverage": {},
        "summary_backlog_count": 0,
        "verify_status_counts": {
            "failed": 0,
            "passed": 2,
            "pending": 0,
            "skipped": 0,
        },
        "workflow_completion_auto_memory_recorded_count": 0,
        "workflow_completion_auto_memory_skipped_count": 0,
        "workflow_status_counts": {
            "cancelled": 0,
            "completed": 1,
            "failed": 0,
            "running": 1,
        },
        "workspace_count": 2,
    }
    assert captured.err == ""


def test_main_stats_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_cli_settings(monkeypatch, make_settings(database_url=""))

    exit_code = cli_module.main(["stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_memory_stats_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stats = MemoryStats(
        episode_count=34,
        memory_item_count=24,
        memory_embedding_count=3,
        memory_relation_count=7,
        memory_item_provenance_counts={
            "derived": 2,
            "episode": 17,
            "explicit": 1,
            "interaction": 7,
            "workflow_complete_auto": 4,
        },
        checkpoint_auto_memory_recorded_count=12,
        checkpoint_auto_memory_skipped_count=45,
        workflow_completion_auto_memory_recorded_count=4,
        workflow_completion_auto_memory_skipped_count=54,
        interaction_memory_item_count=7,
        file_work_memory_item_count=9,
        memory_summary_count=9,
        memory_summary_membership_count=21,
        age_summary_graph_ready_count=1,
        age_summary_graph_stale_count=0,
        age_summary_graph_degraded_count=0,
        age_summary_graph_unknown_count=0,
        latest_episode_created_at=datetime(2026, 3, 15, 9, 3, 0, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 15, 9, 4, 0, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 15, 9, 5, 0, tzinfo=UTC),
        latest_memory_relation_created_at=datetime(2026, 3, 15, 9, 6, 0, tzinfo=UTC),
    )

    class FakeMemoryStatsWorkflowService:
        def __init__(self, stats_result: MemoryStats) -> None:
            self.stats_result = stats_result
            self.get_memory_stats_calls = 0

        def get_memory_stats(self) -> MemoryStats:
            self.get_memory_stats_calls += 1
            return self.stats_result

    settings = make_settings()
    fake_service = FakeMemoryStatsWorkflowService(stats)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["memory-stats"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ctxledger memory-stats" in captured.out
    assert "Counts:" in captured.out
    assert "- episodes: 34" in captured.out
    assert "- memory_items: 24" in captured.out
    assert "- memory_embeddings: 3" in captured.out
    assert "- memory_relations: 7" in captured.out
    assert "- interaction_memory_items: 7" in captured.out
    assert "- file_work_memory_items: 9" in captured.out
    assert "Remember-path observability:" in captured.out
    assert "- checkpoint_auto_memory_recorded: 12" in captured.out
    assert "- checkpoint_auto_memory_skipped: 45" in captured.out
    assert "- workflow_completion_auto_memory_recorded: 4" in captured.out
    assert "- workflow_completion_auto_memory_skipped: 54" in captured.out
    assert "AGE operator metrics:" in captured.out
    assert "- memory_summaries: 9" in captured.out
    assert "- memory_summary_memberships: 21" in captured.out
    assert "- age_summary_graph_ready: 1" in captured.out
    assert "- age_summary_graph_stale: 0" in captured.out
    assert "- age_summary_graph_degraded: 0" in captured.out
    assert "- age_summary_graph_unknown: 0" in captured.out
    assert "Memory item provenance:" in captured.out
    assert "- derived: 2" in captured.out
    assert "- episode: 17" in captured.out
    assert "- explicit: 1" in captured.out
    assert "- interaction: 7" in captured.out
    assert "- workflow_complete_auto: 4" in captured.out
    assert "Latest activity:" in captured.out
    assert "2026-03-15 09:03:00+00:00" in captured.out
    assert "2026-03-15 09:04:00+00:00" in captured.out
    assert "2026-03-15 09:05:00+00:00" in captured.out
    assert "2026-03-15 09:06:00+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.get_memory_stats_calls == 1


def test_format_stats_text_uses_zero_defaults_for_missing_fields() -> None:
    rendered = cli_module._format_stats_text(object())

    assert "ctxledger stats" in rendered
    assert "- total: 0" in rendered
    assert "- running: 0" in rendered
    assert "- completed: 0" in rendered
    assert "- failed: 0" in rendered
    assert "- cancelled: 0" in rendered
    assert "- episodes: 0" in rendered
    assert "- memory_items: 0" in rendered
    assert "- memory_embeddings: 0" in rendered
    assert "- derived_memory_items: 0" in rendered
    assert "- checkpoint_auto_memory_recorded: 0" in rendered
    assert "- checkpoint_auto_memory_skipped: 0" in rendered
    assert "- workflow_completion_auto_memory_recorded: 0" in rendered
    assert "- workflow_completion_auto_memory_skipped: 0" in rendered
    assert "- derived_memory_item_state: unknown" in rendered
    assert "- derived_memory_item_reason: None" in rendered
    assert "- derived_memory_graph_status: None" in rendered
    assert "- checkpoints: 0" in rendered
    assert "- workflow_updated_at: None" in rendered
    assert "- checkpoint_created_at: None" in rendered
    assert "- verify_report_created_at: None" in rendered
    assert "- episode_created_at: None" in rendered
    assert "- memory_item_created_at: None" in rendered
    assert "- memory_embedding_created_at: None" in rendered


def test_format_workflows_text_renders_none_fallbacks() -> None:
    workflow = WorkflowListEntry(
        workflow_instance_id=uuid4(),
        workspace_id=uuid4(),
        canonical_path=None,
        ticket_id="CLI-WF-NONE",
        workflow_status="running",
        latest_step_name=None,
        latest_verify_status=None,
        updated_at=datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC),
    )

    rendered = cli_module._format_workflows_text((workflow,))

    assert f"workspace={workflow.workspace_id}" in rendered
    assert "latest_step=none" in rendered
    assert "verify_status=none" in rendered
    assert "updated_at=2026-03-17 12:00:00+00:00" in rendered


def test_format_failures_text_renders_none_fallbacks() -> None:
    failure = FailureListEntry(
        failure_scope="workflow",
        failure_type="runtime",
        failure_status="open",
        target_path=None,
        error_code=None,
        error_message="boom",
        attempt_id=None,
        occurred_at=datetime(2026, 3, 17, 12, 30, 0, tzinfo=UTC),
        resolved_at=None,
        open_failure_count=1,
        retry_count=0,
    )

    rendered = cli_module._format_failures_text((failure,))

    assert "- open: runtime" in rendered
    assert "scope=workflow" in rendered
    assert "path=none" in rendered
    assert "error_code=none" in rendered
    assert "message=boom" in rendered
    assert "resolved_at=None" in rendered
    assert "retry_count=0" in rendered
    assert "open_failures=1" in rendered


def test_format_memory_stats_text_renders_none_when_no_provenance() -> None:
    stats = MemoryStats(
        episode_count=1,
        memory_item_count=2,
        memory_embedding_count=3,
        memory_relation_count=4,
        memory_item_provenance_counts={},
        latest_episode_created_at=datetime(2026, 3, 17, 13, 0, 0, tzinfo=UTC),
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
        latest_memory_relation_created_at=None,
    )

    rendered = cli_module._format_memory_stats_text(stats)

    assert "ctxledger memory-stats" in rendered
    assert "Counts:" in rendered
    assert "- episodes: 1" in rendered
    assert "- memory_items: 2" in rendered
    assert "- memory_embeddings: 3" in rendered
    assert "- memory_relations: 4" in rendered
    assert "- interaction_memory_items: 0" in rendered
    assert "- file_work_memory_items: 0" in rendered
    assert "Memory item provenance:" in rendered
    assert "- none" in rendered


def test_main_memory_stats_renders_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stats = MemoryStats(
        episode_count=3,
        memory_item_count=4,
        memory_embedding_count=1,
        memory_relation_count=0,
        memory_item_provenance_counts={
            "episode": 2,
            "interaction": 1,
            "workflow_complete_auto": 1,
        },
        interaction_memory_item_count=1,
        file_work_memory_item_count=2,
        derived_memory_item_count=0,
        derived_memory_item_state="unknown",
        derived_memory_item_reason=None,
        latest_episode_created_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
        latest_memory_relation_created_at=None,
        latest_derived_memory_item_created_at=None,
    )

    class FakeMemoryStatsWorkflowService:
        def __init__(self, stats_result: MemoryStats) -> None:
            self.stats_result = stats_result

        def get_memory_stats(self) -> MemoryStats:
            return self.stats_result

    settings = make_settings()

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(
        monkeypatch,
        lambda uow_factory: FakeMemoryStatsWorkflowService(stats),
    )

    exit_code = cli_module.main(["memory-stats", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == {
        "checkpoint_auto_memory_recorded_count": 0,
        "checkpoint_auto_memory_skipped_count": 0,
        "episode_count": 3,
        "file_work_memory_item_count": 2,
        "interaction_memory_item_count": 1,
        "derived_memory_item_count": 0,
        "derived_memory_item_state": "unknown",
        "derived_memory_item_reason": None,
        "derived_memory_graph_status": None,
        "latest_episode_created_at": "2026-03-15T09:00:00+00:00",
        "latest_memory_embedding_created_at": None,
        "latest_memory_item_created_at": None,
        "latest_memory_relation_created_at": None,
        "latest_derived_memory_item_created_at": None,
        "memory_embedding_count": 1,
        "memory_item_count": 4,
        "memory_item_provenance_counts": {
            "episode": 2,
            "interaction": 1,
            "workflow_complete_auto": 1,
        },
        "memory_relation_count": 0,
        "memory_summary_count": 0,
        "memory_summary_membership_count": 0,
        "age_summary_graph_ready_count": 0,
        "age_summary_graph_stale_count": 0,
        "age_summary_graph_degraded_count": 0,
        "age_summary_graph_unknown_count": 0,
        "workflow_completion_auto_memory_recorded_count": 0,
        "workflow_completion_auto_memory_skipped_count": 0,
    }
    assert captured.err == ""


def test_main_memory_stats_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_cli_settings(monkeypatch, make_settings(database_url=""))

    exit_code = cli_module.main(["memory-stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_stats_returns_error_when_stats_loading_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class ExplodingWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            self.uow_factory = uow_factory

        def get_stats(self) -> WorkflowStats:
            raise RuntimeError("stats exploded")

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, ExplodingWorkflowService)

    exit_code = cli_module.main(["stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: stats exploded" in captured.err


def test_main_memory_stats_returns_error_when_loading_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class ExplodingWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            self.uow_factory = uow_factory

        def get_memory_stats(self) -> MemoryStats:
            raise RuntimeError("memory stats exploded")

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, ExplodingWorkflowService)

    exit_code = cli_module.main(["memory-stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load memory stats: memory stats exploded" in captured.err

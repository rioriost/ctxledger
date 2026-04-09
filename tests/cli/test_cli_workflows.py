from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.workflow.service import FailureListEntry, MemoryStats, WorkflowListEntry

from .conftest import (
    make_settings,
    patch_cli_connection_pool,
    patch_cli_postgres_config,
    patch_cli_postgres_uow_factory,
    patch_cli_settings,
    patch_cli_workflow_service,
)


def test_main_workflows_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    workflows = (
        WorkflowListEntry(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            canonical_path=str(tmp_path),
            ticket_id="CLI-WF-1",
            workflow_status="running",
            latest_step_name="implement_cli_workflows",
            latest_verify_status="passed",
            updated_at=datetime(2026, 3, 15, 12, 0, 0, tzinfo=UTC),
        ),
    )

    class FakeWorkflowsService:
        def __init__(self, result: tuple[WorkflowListEntry, ...]) -> None:
            self.result = result
            self.calls: list[dict[str, object]] = []

        def list_workflows(
            self,
            *,
            limit: int,
            status: str | None = None,
            workspace_id: object | None = None,
            ticket_id: str | None = None,
        ) -> tuple[WorkflowListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "workspace_id": workspace_id,
                    "ticket_id": ticket_id,
                }
            )
            return self.result

    settings = make_settings()
    fake_service = FakeWorkflowsService(workflows)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["workflows"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ctxledger workflows" in captured.out
    assert f"- {workflow_instance_id} [running]" in captured.out
    assert f"workspace={tmp_path}" in captured.out
    assert "ticket=CLI-WF-1" in captured.out
    assert "latest_step=implement_cli_workflows" in captured.out
    assert "verify_status=passed" in captured.out
    assert "updated_at=2026-03-15 12:00:00+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 20,
            "status": None,
            "workspace_id": None,
            "ticket_id": None,
        }
    ]


def test_main_workflows_renders_json_output_and_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    workflows = (
        WorkflowListEntry(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            canonical_path=str(tmp_path),
            ticket_id="CLI-WF-JSON-1",
            workflow_status="completed",
            latest_step_name="ship_it",
            latest_verify_status="passed",
            updated_at=datetime(2026, 3, 15, 13, 30, 0, tzinfo=UTC),
        ),
    )

    class FakeWorkflowsService:
        def __init__(self, result: tuple[WorkflowListEntry, ...]) -> None:
            self.result = result
            self.calls: list[dict[str, object]] = []

        def list_workflows(
            self,
            *,
            limit: int,
            status: str | None = None,
            workspace_id: object | None = None,
            ticket_id: str | None = None,
        ) -> tuple[WorkflowListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "workspace_id": workspace_id,
                    "ticket_id": ticket_id,
                }
            )
            return self.result

    settings = make_settings()
    fake_service = FakeWorkflowsService(workflows)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(
        [
            "workflows",
            "--limit",
            "5",
            "--status",
            "completed",
            "--workspace-id",
            str(workspace_id),
            "--ticket-id",
            "CLI-WF-JSON-1",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == [
        {
            "canonical_path": str(tmp_path),
            "latest_step_name": "ship_it",
            "latest_verify_status": "passed",
            "ticket_id": "CLI-WF-JSON-1",
            "updated_at": "2026-03-15T13:30:00+00:00",
            "workflow_instance_id": str(workflow_instance_id),
            "workflow_status": "completed",
            "workspace_id": str(workspace_id),
        }
    ]
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 5,
            "status": "completed",
            "workspace_id": workspace_id,
            "ticket_id": "CLI-WF-JSON-1",
        }
    ]


def test_main_workflows_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_cli_settings(monkeypatch, make_settings(database_url=""))

    exit_code = cli_module.main(["workflows"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_workflows_returns_error_when_loading_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class ExplodingWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            self.uow_factory = uow_factory

        def list_workflows(
            self,
            *,
            limit: int,
            status: str | None = None,
            workspace_id: object | None = None,
            ticket_id: str | None = None,
        ) -> tuple[WorkflowListEntry, ...]:
            raise RuntimeError("workflows exploded")

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, ExplodingWorkflowService)

    exit_code = cli_module.main(["workflows"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load workflows: workflows exploded" in captured.err


def test_main_workflows_renders_text_output_for_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeWorkflowsService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def list_workflows(
            self,
            *,
            limit: int,
            status: str | None = None,
            workspace_id: object | None = None,
            ticket_id: str | None = None,
        ) -> tuple[WorkflowListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "workspace_id": workspace_id,
                    "ticket_id": ticket_id,
                }
            )
            return ()

    settings = make_settings()
    fake_service = FakeWorkflowsService()

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["workflows", "--limit", "0"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "ctxledger workflows\n\n- none\n"
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 1,
            "status": None,
            "workspace_id": None,
            "ticket_id": None,
        }
    ]


def test_main_failures_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    failures = (
        FailureListEntry(
            failure_scope="workflow",
            failure_type="runtime",
            failure_status="open",
            target_path=str(tmp_path),
            error_code="runtime_failed",
            error_message="tests failed",
            attempt_id=uuid4(),
            occurred_at=datetime(2026, 3, 15, 14, 0, 0, tzinfo=UTC),
            resolved_at=None,
            open_failure_count=1,
            retry_count=0,
        ),
    )

    class FakeFailuresWorkflowService:
        def __init__(self, result: tuple[FailureListEntry, ...]) -> None:
            self.result = result
            self.calls: list[dict[str, object]] = []

        def list_failures(
            self,
            *,
            limit: int,
            status: str | None = None,
            open_only: bool = False,
        ) -> tuple[FailureListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "open_only": open_only,
                }
            )
            return self.result

    settings = make_settings()
    fake_service = FakeFailuresWorkflowService(failures)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ctxledger failures" in captured.out
    assert "- open: runtime" in captured.out
    assert "scope=workflow" in captured.out
    assert f"path={tmp_path}" in captured.out
    assert "error_code=runtime_failed" in captured.out
    assert "message=tests failed" in captured.out
    assert "occurred_at=2026-03-15 14:00:00+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 20,
            "status": None,
            "open_only": False,
        }
    ]


def test_main_failures_renders_json_output_and_filters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:

    failures = (
        FailureListEntry(
            failure_scope="workflow",
            failure_type="runtime",
            failure_status="open",
            target_path=str(tmp_path),
            error_code="runtime_failed",
            error_message="schema exploded",
            attempt_id=uuid4(),
            occurred_at=datetime(2026, 3, 15, 14, 30, 0, tzinfo=UTC),
            resolved_at=None,
            open_failure_count=1,
            retry_count=0,
        ),
    )

    class FakeFailuresWorkflowService:
        def __init__(self, result: tuple[FailureListEntry, ...]) -> None:
            self.result = result
            self.calls: list[dict[str, object]] = []

        def list_failures(
            self,
            *,
            limit: int,
            status: str | None = None,
            open_only: bool = False,
        ) -> tuple[FailureListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "open_only": open_only,
                }
            )
            return self.result

    settings = make_settings()
    fake_service = FakeFailuresWorkflowService(failures)

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(
        [
            "failures",
            "--limit",
            "9",
            "--status",
            "open",
            "--open-only",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == [
        {
            "failure_scope": "workflow",
            "failure_type": "runtime",
            "failure_status": "open",
            "target_path": str(tmp_path),
            "error_code": "runtime_failed",
            "error_message": "schema exploded",
            "attempt_id": str(failures[0].attempt_id),
            "occurred_at": "2026-03-15T14:30:00+00:00",
            "resolved_at": None,
            "open_failure_count": 1,
            "retry_count": 0,
        }
    ]
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 9,
            "status": "open",
            "open_only": True,
        }
    ]


def test_main_failures_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_cli_settings(monkeypatch, make_settings(database_url=""))

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_main_failures_returns_error_when_loading_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class ExplodingWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            self.uow_factory = uow_factory

        def list_failures(
            self,
            *,
            limit: int,
            status: str | None = None,
            open_only: bool = False,
        ) -> tuple[FailureListEntry, ...]:
            raise RuntimeError("failures exploded")

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, ExplodingWorkflowService)

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load failures: failures exploded" in captured.err


def test_main_failures_renders_text_output_for_empty_result(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeFailuresWorkflowService:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def list_failures(
            self,
            *,
            limit: int,
            status: str | None = None,
            open_only: bool = False,
        ) -> tuple[FailureListEntry, ...]:
            self.calls.append(
                {
                    "limit": limit,
                    "status": status,
                    "open_only": open_only,
                }
            )
            return ()

    settings = make_settings()
    fake_service = FakeFailuresWorkflowService()

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(monkeypatch, fake_service)

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "ctxledger failures\n\n- none\n"
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 20,
            "status": None,
            "open_only": False,
        }
    ]


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
            "workflow_complete_auto": 4,
        },
        latest_episode_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
        latest_memory_relation_created_at=datetime(2026, 3, 15, 9, 5, 0, tzinfo=UTC),
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
    assert "Memory item provenance:" in captured.out
    assert "- derived: 2" in captured.out
    assert "- episode: 17" in captured.out
    assert "- explicit: 1" in captured.out
    assert "- workflow_complete_auto: 4" in captured.out
    assert "Latest activity:" in captured.out
    assert "2026-03-15 09:05:00+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.get_memory_stats_calls == 1


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
            "workflow_complete_auto": 2,
        },
        memory_summary_count=0,
        memory_summary_membership_count=0,
        age_summary_graph_ready_count=0,
        age_summary_graph_stale_count=0,
        age_summary_graph_degraded_count=0,
        age_summary_graph_unknown_count=0,
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
        "file_work_memory_item_count": 0,
        "interaction_memory_item_count": 0,
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
            "workflow_complete_auto": 2,
        },
        "memory_relation_count": 0,
        "memory_summary_count": 0,
        "memory_summary_membership_count": 0,
        "completion_summary_build_request_count": 0,
        "completion_summary_build_attempted_count": 0,
        "completion_summary_build_success_count": 0,
        "completion_summary_build_request_rate": 0.0,
        "completion_summary_build_request_rate_base": 0,
        "completion_summary_build_attempted_rate": 0.0,
        "completion_summary_build_attempted_rate_base": 0,
        "completion_summary_build_success_rate": 0.0,
        "completion_summary_build_success_rate_base": 0,
        "completion_summary_build_status_counts": {},
        "completion_summary_build_status_total_count": 0,
        "completion_summary_build_attempted_minus_status_total_count": 0,
        "completion_summary_build_skipped_reason_counts": {},
        "completion_summary_build_skipped_reason_total_count": 0,
        "completion_summary_build_status_minus_skipped_reason_total_count": 0,
        "age_summary_graph_ready_count": 0,
        "age_summary_graph_stale_count": 0,
        "age_summary_graph_degraded_count": 0,
        "age_summary_graph_unknown_count": 0,
        "unlinked_interaction_memory_item_count": 0,
        "weakly_linked_interaction_memory_item_count": 0,
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

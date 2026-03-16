from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.config import (
    AppSettings,
    DatabaseSettings,
    DebugSettings,
    EmbeddingProvider,
    EmbeddingSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
)
from ctxledger.workflow.service import (
    CreateCheckpointInput,
    FailureListEntry,
    MemoryStats,
    ProjectionArtifactType,
    ProjectionStatus,
    RegisterWorkspaceInput,
    ResumeIssue,
    StartWorkflowInput,
    WorkflowListEntry,
    WorkflowStats,
)


def make_settings(
    *, database_url: str = "postgresql://ctxledger:test@localhost:5432/ctxledger"
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.1.0",
        environment="test",
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
        ),
        http=HttpSettings(
            host="127.0.0.1",
            port=8080,
            path="/mcp",
        ),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=False,
        ),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
        ),
    )


class FakeWorkflowService:
    def __init__(self, resume_result: object) -> None:
        self.resume_result = resume_result
        self.resume_calls: list[object] = []

    def resume_workflow(self, data: object) -> object:
        self.resume_calls.append(data)
        return self.resume_result


def patch_cli_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: AppSettings,
) -> None:
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)


def patch_cli_postgres_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(
            settings=loaded_settings,
            database_url=loaded_settings.database.url,
        ),
    )


def patch_cli_postgres_uow_factory(
    monkeypatch: pytest.MonkeyPatch,
    factory: object,
) -> None:
    if callable(factory):
        monkeypatch.setattr(
            "ctxledger.db.postgres.build_postgres_uow_factory",
            factory,
        )
        return

    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: factory,
    )


def patch_cli_workflow_service(
    monkeypatch: pytest.MonkeyPatch,
    service: object,
) -> None:
    if callable(service):
        monkeypatch.setattr(
            "ctxledger.workflow.service.WorkflowService",
            service,
        )
        return

    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: service,
    )


def patch_cli_connection_pool(
    monkeypatch: pytest.MonkeyPatch,
    pool: object | None = None,
) -> object:
    if pool is None:
        pool = SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(
        "ctxledger.db.postgres.build_connection_pool",
        lambda config: pool,
    )
    return pool


class FakeWriter:
    instances: list["FakeWriter"] = []

    def __init__(
        self, *, workflow_service: object, projection_settings: object
    ) -> None:
        self.workflow_service = workflow_service
        self.projection_settings = projection_settings
        self.calls: list[dict[str, object]] = []
        type(self).instances.append(self)

    def write_and_reconcile_resume_projection(
        self,
        *,
        workspace_root: str | Path,
        workflow_instance_id: object,
        workspace_id: object,
    ) -> object:
        self.calls.append(
            {
                "workspace_root": workspace_root,
                "workflow_instance_id": workflow_instance_id,
                "workspace_id": workspace_id,
            }
        )
        return SimpleNamespace(
            json_path=Path(workspace_root) / ".agent" / "resume.json",
            markdown_path=Path(workspace_root) / ".agent" / "resume.md",
            state_updates=(),
            failure_updates=(),
        )


def test_main_write_resume_projection_uses_workflow_lookup_and_writer(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workspace_id = uuid4()
    workflow_instance_id = uuid4()

    settings = make_settings()
    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=workspace_id,
            canonical_path=str(tmp_path),
        )
    )
    fake_service = FakeWorkflowService(fake_resume)

    uow_factory_calls: list[object] = []
    workflow_service_ctor_args: list[object] = []

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)

    def fake_build_postgres_uow_factory(config: object, pool: object = None) -> object:
        uow_factory_calls.append(config)
        return "fake-uow-factory"


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
            "running": 28,
            "succeeded": 30,
            "failed": 0,
            "cancelled": 0,
        },
        verify_status_counts={
            "pending": 109,
            "passed": 239,
            "failed": 20,
            "skipped": 1,
        },
        checkpoint_count=369,
        episode_count=34,
        memory_item_count=24,
        memory_embedding_count=3,
        open_projection_failure_count=11,
        latest_workflow_updated_at=datetime(2026, 3, 15, 9, 45, 52, tzinfo=UTC),
        latest_checkpoint_created_at=datetime(2026, 3, 15, 10, 55, 8, tzinfo=UTC),
        latest_verify_report_created_at=datetime(2026, 3, 15, 10, 55, 8, tzinfo=UTC),
        latest_episode_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 15, 8, 57, 11, tzinfo=UTC),
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
    assert "- succeeded: 30" in captured.out
    assert "Verify reports:" in captured.out
    assert "- passed: 239" in captured.out
    assert "Memory:" in captured.out
    assert "- episodes: 34" in captured.out
    assert "- memory_items: 24" in captured.out
    assert "- memory_embeddings: 3" in captured.out
    assert "Other:" in captured.out
    assert "- checkpoints: 369" in captured.out
    assert "- open_projection_failures: 11" in captured.out
    assert "Latest activity:" in captured.out
    assert "2026-03-15 09:45:52+00:00" in captured.out
    assert captured.err == ""
    assert fake_service.get_stats_calls == 1


def test_main_stats_renders_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
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
        open_projection_failure_count=0,
        latest_workflow_updated_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        latest_checkpoint_created_at=None,
        latest_verify_report_created_at=None,
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
    )

    class FakeStatsWorkflowService:
        def __init__(self, stats_result: WorkflowStats) -> None:
            self.stats_result = stats_result

        def get_stats(self) -> WorkflowStats:
            return self.stats_result

    settings = make_settings()

    patch_cli_settings(monkeypatch, settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    patch_cli_postgres_uow_factory(monkeypatch, "fake-uow-factory")
    patch_cli_workflow_service(
        monkeypatch,
        lambda uow_factory: FakeStatsWorkflowService(stats),
    )

    exit_code = cli_module.main(["stats", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == {
        "attempt_status_counts": {
            "cancelled": 0,
            "failed": 0,
            "running": 1,
            "succeeded": 1,
        },
        "checkpoint_count": 5,
        "episode_count": 3,
        "latest_checkpoint_created_at": None,
        "latest_episode_created_at": None,
        "latest_memory_embedding_created_at": None,
        "latest_memory_item_created_at": None,
        "latest_verify_report_created_at": None,
        "latest_workflow_updated_at": "2026-03-15T09:00:00+00:00",
        "memory_embedding_count": 1,
        "memory_item_count": 4,
        "open_projection_failure_count": 0,
        "verify_status_counts": {
            "failed": 0,
            "passed": 2,
            "pending": 0,
            "skipped": 0,
        },
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
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        ExplodingWorkflowService,
    )

    exit_code = cli_module.main(["workflows"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load workflows: workflows exploded" in captured.err


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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: fake_service,
    )

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
        latest_episode_created_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
        latest_memory_relation_created_at=None,
    )

    class FakeMemoryStatsWorkflowService:
        def __init__(self, stats_result: MemoryStats) -> None:
            self.stats_result = stats_result

        def get_memory_stats(self) -> MemoryStats:
            return self.stats_result

    settings = make_settings()

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeMemoryStatsWorkflowService(stats),
    )

    exit_code = cli_module.main(["memory-stats", "--format", "json"])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == {
        "episode_count": 3,
        "latest_episode_created_at": "2026-03-15T09:00:00+00:00",
        "latest_memory_embedding_created_at": None,
        "latest_memory_item_created_at": None,
        "latest_memory_relation_created_at": None,
        "memory_embedding_count": 1,
        "memory_item_count": 4,
        "memory_item_provenance_counts": {
            "episode": 2,
            "workflow_complete_auto": 2,
        },
        "memory_relation_count": 0,
    }
    assert captured.err == ""


def test_main_memory_stats_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        ExplodingWorkflowService,
    )

    exit_code = cli_module.main(["memory-stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load memory stats: memory stats exploded" in captured.err


def test_main_failures_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failures = (
        FailureListEntry(
            failure_scope="projection",
            failure_type="resume_json",
            failure_status="open",
            projection_type="resume_json",
            target_path=".agent/resume.json",
            error_code="io_error",
            error_message="failed to write projection",
            attempt_id=uuid4(),
            occurred_at=datetime(2026, 3, 15, 10, 0, 0, tzinfo=UTC),
            resolved_at=None,
            open_failure_count=2,
            retry_count=1,
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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: fake_service,
    )

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ctxledger failures" in captured.out
    assert "- open: resume_json" in captured.out
    assert "scope=projection" in captured.out
    assert "path=.agent/resume.json" in captured.out
    assert "error_code=io_error" in captured.out
    assert "message=failed to write projection" in captured.out
    assert "occurred_at=2026-03-15 10:00:00+00:00" in captured.out
    assert "resolved_at=None" in captured.out
    assert "retry_count=1" in captured.out
    assert "open_failures=2" in captured.out
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
) -> None:
    attempt_id = uuid4()
    failures = (
        FailureListEntry(
            failure_scope="projection",
            failure_type="resume_md",
            failure_status="ignored",
            projection_type="resume_md",
            target_path=".agent/resume.md",
            error_code="permission_error",
            error_message="write intentionally ignored",
            attempt_id=attempt_id,
            occurred_at=datetime(2026, 3, 15, 9, 0, 0, tzinfo=UTC),
            resolved_at=datetime(2026, 3, 15, 9, 5, 0, tzinfo=UTC),
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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: fake_service,
    )

    exit_code = cli_module.main(
        [
            "failures",
            "--limit",
            "5",
            "--status",
            "ignored",
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload == [
        {
            "attempt_id": str(attempt_id),
            "error_code": "permission_error",
            "error_message": "write intentionally ignored",
            "failure_scope": "projection",
            "failure_status": "ignored",
            "failure_type": "resume_md",
            "occurred_at": "2026-03-15T09:00:00+00:00",
            "open_failure_count": 1,
            "projection_type": "resume_md",
            "resolved_at": "2026-03-15T09:05:00+00:00",
            "retry_count": 0,
            "target_path": ".agent/resume.md",
        }
    ]
    assert captured.err == ""
    assert fake_service.calls == [
        {
            "limit": 5,
            "status": "ignored",
            "open_only": False,
        }
    ]


def test_main_failures_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        ExplodingWorkflowService,
    )

    exit_code = cli_module.main(["failures"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load failures: failures exploded" in captured.err


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

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        ExplodingWorkflowService,
    )

    exit_code = cli_module.main(["stats"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: stats exploded" in captured.err


def test_main_resume_workflow_renders_text_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workflow_instance_id = uuid4()

    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=uuid4(),
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
            metadata={"team": "platform"},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=uuid4(),
            ticket_id="CLI-RESUME-1",
            status=SimpleNamespace(value="running"),
            metadata={"priority": "high"},
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_number=2,
            status=SimpleNamespace(value="running"),
            failure_reason=None,
            verify_status=SimpleNamespace(value="passed"),
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=None,
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=uuid4(),
            step_name="implement_cli",
            summary="Resume from latest checkpoint",
            checkpoint_json={"next_intended_action": "Run CLI resume command"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:01:00+00:00"),
        ),
        latest_verify_report=None,
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=0,
            ),
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_MD,
                status=ProjectionStatus.STALE,
                target_path=".agent/resume.md",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=1,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="stale_projection",
                message="resume projection is stale relative to canonical workflow state",
                details={"projection_type": "resume_md"},
            ),
        ),
        closed_projection_failures=(
            SimpleNamespace(
                status="resolved",
                projection_type=ProjectionArtifactType.RESUME_JSON,
                target_path=".agent/resume.json",
                attempt_id=uuid4(),
                error_code="io_error",
                error_message="previous projection write was resolved",
                occurred_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:00:30+00:00"
                ),
                resolved_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:00:45+00:00"
                ),
                open_failure_count=0,
                retry_count=1,
            ),
        ),
        next_hint="Run CLI resume command",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeWorkflowService(fake_resume),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert "Resume workflow" in captured.out
    assert f"Workflow: {workflow_instance_id}" in captured.out
    assert "Ticket: CLI-RESUME-1" in captured.out
    assert "Resumable status: resumable" in captured.out
    assert f"Workspace: {tmp_path}" in captured.out
    assert "Latest checkpoint step: implement_cli" in captured.out
    assert "Projections:" in captured.out
    assert "- resume_json: fresh [.agent/resume.json] failures=0" in captured.out
    assert "- resume_md: stale [.agent/resume.md] failures=1" in captured.out
    assert "Warnings:" in captured.out
    assert (
        "- stale_projection: resume projection is stale relative to canonical workflow state"
        in captured.out
    )
    assert "Closed projection failures:" in captured.out
    assert "- resolved: resume_json [path=.agent/resume.json]" in captured.out
    assert "[error_code=io_error]" in captured.out
    assert "[message=previous projection write was resolved]" in captured.out
    assert "[occurred_at=2024-01-01T00:00:30+00:00]" in captured.out
    assert "[resolved_at=2024-01-01T00:00:45+00:00]" in captured.out
    assert "[open_failures=0]" in captured.out
    assert "[retry_count=1]" in captured.out
    assert "Next hint: Run CLI resume command" in captured.out
    assert captured.err == ""


def test_main_resume_workflow_renders_ignored_projection_warning_details(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    workflow_instance_id = uuid4()

    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=uuid4(),
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
            metadata={},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=uuid4(),
            ticket_id="CLI-RESUME-IGNORED-1",
            status=SimpleNamespace(value="running"),
            metadata={},
        ),
        attempt=SimpleNamespace(
            attempt_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_number=1,
            status=SimpleNamespace(value="failed"),
            failure_reason="projection write failed previously",
            verify_status=None,
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:05:00+00:00"),
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=uuid4(),
            step_name="inspect_projection_failure",
            summary="Investigate ignored projection failures",
            checkpoint_json={"next_intended_action": "Review warning output"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:04:00+00:00"),
        ),
        latest_verify_report=None,
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FAILED,
                target_path=".agent/resume.json",
                last_successful_write_at=None,
                last_canonical_update_at=None,
                open_failure_count=0,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="ignored_projection_failure",
                message="resume projection has ignored or previously resolved write failures",
                details={
                    "projection_type": "resume_json",
                    "target_path": ".agent/resume.json",
                    "open_failure_count": 0,
                    "failures": [
                        {
                            "projection_type": "resume_json",
                            "target_path": ".agent/resume.json",
                            "attempt_id": "11111111-1111-1111-1111-111111111111",
                            "error_code": "permission_error",
                            "error_message": "previous projection write was ignored",
                            "occurred_at": "2024-01-01T00:03:00+00:00",
                            "resolved_at": "2024-01-01T00:04:00+00:00",
                            "open_failure_count": 1,
                            "retry_count": 0,
                            "status": "ignored",
                        }
                    ],
                },
            ),
        ),
        next_hint="Review warning output",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeWorkflowService(fake_resume),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0, captured.err
    assert "Warnings:" in captured.out
    assert (
        "- ignored_projection_failure: "
        "resume projection has ignored or previously resolved write failures "
        "[projection=resume_json] [path=.agent/resume.json] [open_failures=0]"
        in captured.out
    )
    assert "Next hint: Review warning output" in captured.out
    assert captured.err == ""


def test_main_resume_workflow_renders_json_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:

    workflow_instance_id = uuid4()
    workspace_id = uuid4()
    attempt_id = uuid4()

    fake_resume = SimpleNamespace(
        workspace=SimpleNamespace(
            workspace_id=workspace_id,
            repo_url="https://example.com/org/repo.git",
            canonical_path=str(tmp_path),
            default_branch="main",
            metadata={"team": "platform"},
        ),
        workflow_instance=SimpleNamespace(
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace_id,
            ticket_id="CLI-RESUME-JSON-1",
            status=SimpleNamespace(value="running"),
            metadata={"priority": "high"},
        ),
        attempt=SimpleNamespace(
            attempt_id=attempt_id,
            workflow_instance_id=workflow_instance_id,
            attempt_number=1,
            status=SimpleNamespace(value="running"),
            failure_reason=None,
            verify_status=SimpleNamespace(value="passed"),
            started_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:00:00+00:00"),
            finished_at=None,
        ),
        latest_checkpoint=SimpleNamespace(
            checkpoint_id=uuid4(),
            workflow_instance_id=workflow_instance_id,
            attempt_id=attempt_id,
            step_name="implement_cli",
            summary="Render JSON output",
            checkpoint_json={"next_intended_action": "Inspect JSON"},
            created_at=SimpleNamespace(isoformat=lambda: "2024-01-01T00:01:00+00:00"),
        ),
        latest_verify_report=None,
        projections=(
            SimpleNamespace(
                projection_type=ProjectionArtifactType.RESUME_JSON,
                status=ProjectionStatus.FRESH,
                target_path=".agent/resume.json",
                last_successful_write_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:02:00+00:00"
                ),
                last_canonical_update_at=SimpleNamespace(
                    isoformat=lambda: "2024-01-01T00:02:00+00:00"
                ),
                open_failure_count=0,
            ),
        ),
        resumable_status=SimpleNamespace(value="resumable"),
        warnings=(
            ResumeIssue(
                code="ignored_projection_failure",
                message="resume projection has ignored or previously resolved write failures",
                details={
                    "projection_type": "resume_json",
                    "target_path": ".agent/resume.json",
                    "open_failure_count": 0,
                    "failures": [
                        {
                            "projection_type": "resume_json",
                            "target_path": ".agent/resume.json",
                            "attempt_id": str(attempt_id),
                            "error_code": "io_error",
                            "error_message": "previous projection write was resolved",
                            "occurred_at": "2024-01-01T00:01:30+00:00",
                            "resolved_at": "2024-01-01T00:02:00+00:00",
                            "open_failure_count": 1,
                            "retry_count": 0,
                            "status": "resolved",
                        }
                    ],
                },
            ),
        ),
        next_hint="Inspect JSON",
    )

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())
    patch_cli_postgres_config(monkeypatch)
    patch_cli_connection_pool(monkeypatch)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: "fake-uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: FakeWorkflowService(fake_resume),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
            "--format",
            "json",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0, captured.err
    assert payload["workspace"]["workspace_id"] == str(workspace_id)
    assert payload["workflow"]["workflow_instance_id"] == str(workflow_instance_id)
    assert payload["attempt"]["attempt_id"] == str(attempt_id)
    assert payload["latest_checkpoint"]["step_name"] == "implement_cli"
    assert payload["projections"] == [
        {
            "last_canonical_update_at": "2024-01-01T00:02:00+00:00",
            "last_successful_write_at": "2024-01-01T00:02:00+00:00",
            "open_failure_count": 0,
            "projection_type": "resume_json",
            "status": "fresh",
            "target_path": ".agent/resume.json",
        }
    ]
    assert payload["resumable_status"] == "resumable"
    assert payload["next_hint"] == "Inspect JSON"
    assert payload["warnings"] == [
        {
            "code": "ignored_projection_failure",
            "message": "resume projection has ignored or previously resolved write failures",
            "details": {
                "projection_type": "resume_json",
                "target_path": ".agent/resume.json",
                "open_failure_count": 0,
                "failures": [
                    {
                        "projection_type": "resume_json",
                        "target_path": ".agent/resume.json",
                        "attempt_id": str(attempt_id),
                        "error_code": "io_error",
                        "error_message": "previous projection write was resolved",
                        "occurred_at": "2024-01-01T00:01:30+00:00",
                        "resolved_at": "2024-01-01T00:02:00+00:00",
                        "open_failure_count": 1,
                        "retry_count": 0,
                        "status": "resolved",
                    }
                ],
            },
        }
    ]
    assert captured.err == ""


def test_main_resume_workflow_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workflow_instance_id = uuid4()

    monkeypatch.setattr(cli_module, "UUID", lambda value: workflow_instance_id)
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module.main(
        [
            "resume-workflow",
            "--workflow-instance-id",
            str(workflow_instance_id),
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_build_parser_includes_expected_subcommands() -> None:
    parser = cli_module._build_parser()

    actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    assert len(actions) == 1

    subcommands = set(actions[0].choices)
    assert subcommands == {
        "stats",
        "workflows",
        "failures",
        "memory-stats",
        "serve",
        "print-schema-path",
        "apply-schema",
        "resume-workflow",
        "version",
    }


def test_schema_path_points_to_bundled_postgres_schema() -> None:
    path = cli_module._schema_path()

    assert path.name == "postgres.sql"
    assert path.parent.name == "schemas"
    assert path.exists()


def test_print_version_falls_back_when_metadata_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "importlib.metadata":
            raise RuntimeError("metadata unavailable")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    exit_code = cli_module._print_version()
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "0.5.3"
    assert captured.err == ""


def test_print_schema_path_outputs_relative_and_absolute_variants(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_module._print_schema_path(False)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip().endswith("schemas/postgres.sql")
    assert captured.err == ""

    exit_code = cli_module._print_schema_path(True)
    captured = capsys.readouterr()

    assert exit_code == 0
    assert Path(captured.out.strip()).is_absolute()
    assert captured.err == ""


def test_apply_schema_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module._apply_schema(argparse.Namespace(database_url=None))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )


def test_apply_schema_uses_explicit_database_url_and_commits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_sql: list[str] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str) -> None:
            executed_sql.append(query)

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def commit(self) -> None:
            commit_calls.append("commit")

    fake_psycopg = SimpleNamespace(
        connect=lambda database_url: (
            connect_calls.append(database_url) or FakeConnection()
        )
    )

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        lambda: "SELECT 1;",
    )

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "Schema applied successfully."
    assert captured.err == ""
    assert connect_calls == ["postgresql://explicit/db"]
    assert executed_sql == ["SELECT 1;"]
    assert commit_calls == ["commit"]


def test_apply_schema_reports_driver_import_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    real_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "psycopg":
            raise ImportError("missing psycopg")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Failed to import PostgreSQL driver. Install psycopg[binary] first."
        in captured.err
    )


def test_apply_schema_reports_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        lambda: (_ for _ in ()).throw(RuntimeError("schema exploded")),
    )

    fake_psycopg = SimpleNamespace(connect=lambda database_url: None)
    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to apply schema: schema exploded" in captured.err


def test_serve_returns_zero_when_run_server_result_is_not_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.server.run_server",
        lambda **kwargs: "ok",
    )

    result = cli_module._serve(argparse.Namespace(transport=None, host=None, port=None))

    assert result == 0


def test_main_dispatches_print_schema_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    monkeypatch.setattr(
        cli_module,
        "_print_schema_path",
        lambda absolute: called.append(absolute) or 7,
    )

    result = cli_module.main(["print-schema-path", "--absolute"])

    assert result == 7
    assert called == [True]


def test_main_dispatches_apply_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_urls: list[str | None] = []

    def fake_apply_schema(args: argparse.Namespace) -> int:
        received_urls.append(args.database_url)
        return 5

    monkeypatch.setattr(cli_module, "_apply_schema", fake_apply_schema)

    result = cli_module.main(
        ["apply-schema", "--database-url", "postgresql://override/db"]
    )

    assert result == 5
    assert received_urls == ["postgresql://override/db"]


def test_main_dispatches_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[str] = []

    monkeypatch.setattr(
        cli_module, "_print_version", lambda: called.append("version") or 3
    )

    result = cli_module.main(["version"])

    assert result == 3
    assert called == ["version"]


def test_main_defaults_to_serve_when_no_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[argparse.Namespace] = []

    def fake_serve(args: argparse.Namespace) -> int:
        called.append(args)
        return 0

    monkeypatch.setattr(cli_module, "_serve", fake_serve)

    result = cli_module.main([])

    assert result == 0
    assert len(called) == 1
    assert called[0].command is None


def test_main_returns_parser_error_for_unknown_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeParser:
        def parse_args(self, argv: list[str] | None) -> argparse.Namespace:
            return argparse.Namespace(command="mystery")

        def error(self, message: str) -> None:
            raise RuntimeError(message)

    monkeypatch.setattr(cli_module, "_build_parser", lambda: FakeParser())

    with pytest.raises(RuntimeError, match="Unknown command: mystery"):
        cli_module.main(["mystery"])


def test_main_dispatches_workflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[int, str | None, str | None, str]] = []

    def fake_workflows(args: argparse.Namespace) -> int:
        received.append((args.limit, args.status, args.workspace_id, args.format))
        return 8

    monkeypatch.setattr(cli_module, "_workflows", fake_workflows)

    result = cli_module.main(
        [
            "workflows",
            "--limit",
            "7",
            "--status",
            "running",
            "--workspace-id",
            "workspace-123",
            "--format",
            "json",
        ]
    )

    assert result == 8
    assert received == [(7, "running", "workspace-123", "json")]


def test_main_dispatches_memory_stats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_formats: list[str] = []

    def fake_memory_stats(args: argparse.Namespace) -> int:
        received_formats.append(args.format)
        return 6

    monkeypatch.setattr(cli_module, "_memory_stats", fake_memory_stats)

    result = cli_module.main(["memory-stats", "--format", "json"])

    assert result == 6
    assert received_formats == ["json"]


def test_main_dispatches_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[int, str | None, bool, str]] = []

    def fake_failures(args: argparse.Namespace) -> int:
        received.append((args.limit, args.status, args.open_only, args.format))
        return 4

    monkeypatch.setattr(cli_module, "_failures", fake_failures)

    result = cli_module.main(
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

    assert result == 4
    assert received == [(9, "open", True, "json")]


def test_main_dispatches_resume_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_ids: list[str] = []

    def fake_resume_workflow(args: argparse.Namespace) -> int:
        received_ids.append(args.workflow_instance_id)
        return 9

    monkeypatch.setattr(cli_module, "_resume_workflow", fake_resume_workflow)

    result = cli_module.main(
        ["resume-workflow", "--workflow-instance-id", "workflow-123"]
    )

    assert result == 9
    assert received_ids == ["workflow-123"]


def test_main_serve_renders_startup_summary_from_run_server(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received_kwargs: dict[str, object] = {}

    def fake_run_server(**kwargs: object) -> int:
        received_kwargs.update(kwargs)
        print("ctxledger 0.1.0 started", file=sys.stderr)
        print("health=ok", file=sys.stderr)
        print("readiness=ready", file=sys.stderr)
        print(
            "runtime=[{'transport': 'http', 'routes': ['runtime_introspection', "
            "'runtime_routes', 'runtime_tools', 'workflow_resume'], 'tools': []}]",
            file=sys.stderr,
        )
        print("mcp_endpoint=/mcp", file=sys.stderr)
        return 0

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert received_kwargs == {}
    assert captured.out == ""
    assert "ctxledger 0.1.0 started" in captured.err
    assert "health=ok" in captured.err
    assert "readiness=ready" in captured.err
    assert "runtime=[{'transport': 'http'" in captured.err
    assert "mcp_endpoint=/mcp" in captured.err


def test_main_serve_passes_transport_and_network_overrides(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    received_kwargs: dict[str, object] = {}

    def fake_run_server(**kwargs: object) -> int:
        received_kwargs.update(kwargs)
        print("ctxledger 0.1.0 started", file=sys.stderr)
        print("health=ok", file=sys.stderr)
        print("readiness=ready", file=sys.stderr)
        print(
            "runtime=[{'transport': 'http', 'routes': ['runtime_introspection', "
            "'runtime_routes', 'runtime_tools', 'workflow_resume'], 'tools': []}]",
            file=sys.stderr,
        )
        print("mcp_endpoint=/mcp", file=sys.stderr)
        return 0

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(
        [
            "serve",
            "--transport",
            "http",
            "--host",
            "0.0.0.0",
            "--port",
            "9090",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert received_kwargs == {
        "transport": "http",
        "host": "0.0.0.0",
        "port": 9090,
    }
    assert captured.out == ""
    assert "mcp_endpoint=/mcp" in captured.err


def test_main_serve_returns_failure_when_run_server_reports_startup_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_run_server(**kwargs: object) -> int:
        print(
            "Startup failed: database schema is not ready",
            file=sys.stderr,
        )
        return 1

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Startup failed: database schema is not ready" in captured.err


def test_main_serve_returns_failure_when_server_runtime_import_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    original_import = __import__

    def fake_import(
        name: str,
        globals: object | None = None,
        locals: object | None = None,
        fromlist: tuple[str, ...] = (),
        level: int = 0,
    ) -> object:
        if name == "ctxledger.server" or (
            level == 1
            and name == "server"
            and globals
            and globals.get("__package__") == "ctxledger"
        ):
            raise ImportError("server module unavailable")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    exit_code = cli_module.main(["serve"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to import server runtime: server module unavailable" in captured.err

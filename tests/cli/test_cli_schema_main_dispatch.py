from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.workflow.service import (
    MemoryStats,
    WorkflowStats,
)

from .conftest import make_settings


def test_main_unknown_command_uses_parser_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_calls: list[str] = []

    class FakeParser:
        def parse_args(self, argv: list[str] | None) -> argparse.Namespace:
            assert argv == ["mystery"]
            return argparse.Namespace(command="mystery")

        def error(self, message: str) -> None:
            parser_calls.append(message)
            raise SystemExit(2)

    monkeypatch.setattr(cli_module, "_build_parser", lambda: FakeParser())

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["mystery"])

    assert exc_info.value.code == 2
    assert parser_calls == ["Unknown command: mystery"]


def test_main_unknown_command_returns_two_when_parser_error_does_not_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_calls: list[str] = []
    build_calls: list[str] = []
    parse_calls: list[list[str] | None] = []

    class FakeParser:
        def parse_args(self, argv: list[str] | None) -> argparse.Namespace:
            parse_calls.append(argv)
            assert argv == ["mystery"]
            return argparse.Namespace(command="mystery")

        def error(self, message: str) -> None:
            parser_calls.append(message)

    def fake_build_parser() -> FakeParser:
        build_calls.append("built")
        return FakeParser()

    monkeypatch.setattr(cli_module, "_build_parser", fake_build_parser)

    assert cli_module.main(["mystery"]) == 2
    assert build_calls == ["built"]
    assert parse_calls == [["mystery"]]
    assert parser_calls == ["Unknown command: mystery"]


def test_main_dispatches_build_episode_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[str, str, bool, str]] = []

    def fake_build_episode_summary(args: argparse.Namespace) -> int:
        received.append(
            (
                args.episode_id,
                args.summary_kind,
                args.no_replace_existing,
                args.format,
            )
        )
        return 12

    monkeypatch.setattr(
        cli_module, "_build_episode_summary", fake_build_episode_summary
    )

    result = cli_module.main(
        [
            "build-episode-summary",
            "--episode-id",
            "11111111-1111-1111-1111-111111111111",
            "--summary-kind",
            "episode_summary",
            "--no-replace-existing",
            "--format",
            "json",
        ]
    )

    assert result == 12
    assert received == [
        (
            "11111111-1111-1111-1111-111111111111",
            "episode_summary",
            True,
            "json",
        )
    ]


def test_main_dispatches_refresh_age_summary_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received: list[tuple[str | None, str | None]] = []

    def fake_refresh_age_summary_graph(args: argparse.Namespace) -> int:
        received.append((args.database_url, args.graph_name))
        return 13

    monkeypatch.setattr(
        cli_module,
        "_refresh_age_summary_graph",
        fake_refresh_age_summary_graph,
    )

    result = cli_module.main(
        [
            "refresh-age-summary-graph",
            "--database-url",
            "postgresql://explicit/db",
            "--graph-name",
            "ctxledger_summary_graph",
        ]
    )

    assert result == 13
    assert received == [("postgresql://explicit/db", "ctxledger_summary_graph")]


def test_build_episode_summary_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_id = uuid4()

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("builder exploded")),
    )

    exit_code = cli_module._build_episode_summary(
        argparse.Namespace(
            episode_id=str(episode_id),
            summary_kind="episode_summary",
            no_replace_existing=True,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to build episode summary: builder exploded" in captured.err


def test_build_episode_summary_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_id = uuid4()

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._build_episode_summary(
        argparse.Namespace(
            episode_id=str(episode_id),
            summary_kind="episode_summary",
            no_replace_existing=False,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_build_episode_summary_renders_text_output_and_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_id = uuid4()
    summary_id = uuid4()
    workspace_id = uuid4()
    membership_id = uuid4()
    memory_id = uuid4()
    close_calls: list[str] = []

    result = SimpleNamespace(
        feature=SimpleNamespace(value="build_episode_summary"),
        implemented=True,
        message="Episode summary built successfully.",
        status="ok",
        available_in_version="0.9.0",
        timestamp=datetime(2024, 11, 6, tzinfo=UTC),
        summary_built=True,
        skipped_reason=None,
        replaced_existing_summary=False,
        summary=SimpleNamespace(
            memory_summary_id=summary_id,
            workspace_id=workspace_id,
            episode_id=episode_id,
            summary_text="Built summary text",
            summary_kind="episode_summary",
            metadata={"scope": "episode"},
            created_at=datetime(2024, 11, 6, tzinfo=UTC),
            updated_at=datetime(2024, 11, 6, tzinfo=UTC),
        ),
        memberships=(
            SimpleNamespace(
                memory_summary_membership_id=membership_id,
                memory_summary_id=summary_id,
                memory_id=memory_id,
                membership_order=1,
                metadata={"source": "test"},
                created_at=datetime(2024, 11, 6, tzinfo=UTC),
            ),
        ),
        details={"builder": "cli-test"},
    )

    received_requests: list[object] = []

    class DummyMemoryService:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def build_episode_summary(self, request: object) -> object:
            received_requests.append(request)
            return result

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), object(), DummyConnectionPool()),
    )
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url="postgresql://ctxledger/db"),
    )

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings: object) -> object:
            return SimpleNamespace(database_url="postgresql://ctxledger/db")

    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool: "uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresDatabaseHealthChecker",
        lambda config: "health-checker",
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.MemoryService",
        DummyMemoryService,
    )

    exit_code = cli_module._build_episode_summary(
        argparse.Namespace(
            episode_id=str(episode_id),
            summary_kind="episode_summary",
            no_replace_existing=False,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert "Build episode summary" in captured.out
    assert f"Episode: {episode_id}" in captured.out
    assert "Summary built: yes" in captured.out
    assert "Replaced existing summary: no" in captured.out
    assert f"Summary ID: {summary_id}" in captured.out
    assert f"Workspace ID: {workspace_id}" in captured.out
    assert "Summary text: Built summary text" in captured.out
    assert "Membership count: 1" in captured.out
    assert close_calls == ["close"]
    assert len(received_requests) == 1
    request = received_requests[0]
    assert request.episode_id == str(episode_id)
    assert request.summary_kind == "episode_summary"
    assert request.replace_existing is True


def test_build_episode_summary_renders_json_output_without_summary_and_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    episode_id = uuid4()
    close_calls: list[str] = []

    result = SimpleNamespace(
        feature=SimpleNamespace(value="build_episode_summary"),
        implemented=True,
        message="Episode summary skipped.",
        status="ok",
        available_in_version="0.9.0",
        timestamp=datetime(2024, 11, 7, tzinfo=UTC),
        summary_built=False,
        skipped_reason="already_exists",
        replaced_existing_summary=True,
        summary=None,
        memberships=(),
        details={"builder": "cli-test"},
    )

    class DummyMemoryService:
        def __init__(self, **kwargs: object) -> None:
            self.kwargs = kwargs

        def build_episode_summary(self, request: object) -> object:
            return result

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), object(), DummyConnectionPool()),
    )
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url="postgresql://ctxledger/db"),
    )

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, settings: object) -> object:
            return SimpleNamespace(database_url="postgresql://ctxledger/db")

    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool: "uow-factory",
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresDatabaseHealthChecker",
        lambda config: "health-checker",
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.MemoryService",
        DummyMemoryService,
    )

    exit_code = cli_module._build_episode_summary(
        argparse.Namespace(
            episode_id=str(episode_id),
            summary_kind="episode_summary",
            no_replace_existing=True,
            format="json",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["feature"] == "build_episode_summary"
    assert payload["summary_built"] is False
    assert payload["skipped_reason"] == "already_exists"
    assert payload["replaced_existing_summary"] is True
    assert payload["summary"] is None
    assert payload["memberships"] == []
    assert close_calls == ["close"]


def test_refresh_age_summary_graph_reports_failure_with_current_narrow_fake_graph_substrate(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [None]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))
            if "FROM public.memory_summary_memberships" in query:
                raise RuntimeError("summary graph refresh exploded")

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "FROM public.memory_summaries" in last_query:
                summary_id_one = UUID("11111111-1111-1111-1111-111111111111")
                summary_id_two = UUID("22222222-2222-2222-2222-222222222222")
                workspace_id_one = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
                workspace_id_two = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
                episode_id_one = UUID("33333333-3333-3333-3333-333333333333")
                return [
                    {
                        "memory_summary_id": summary_id_one,
                        "workspace_id": workspace_id_one,
                        "episode_id": episode_id_one,
                        "summary_kind": "episode_summary",
                    },
                    {
                        "memory_summary_id": summary_id_two,
                        "workspace_id": workspace_id_two,
                        "episode_id": None,
                        "summary_kind": "episode_summary",
                    },
                ]
            return []

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
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())

    exit_code = cli_module._refresh_age_summary_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_summary_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Failed to refresh AGE summary graph: summary graph refresh exploded"
        in captured.err
    )
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == []
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == (
        'SET search_path = ag_catalog, "$user", public',
        None,
    )
    assert executed_queries[2][1] == ("ctxledger_summary_graph",)
    assert (
        executed_queries[3][0]
        == "SELECT ag_catalog.create_graph('ctxledger_summary_graph')"
    )
    assert executed_queries[3][1] is None
    assert "MATCH (n:memory_summary)-[r:summarizes]->()" in executed_queries[4][0]
    assert "MATCH (n:memory_summary)" in executed_queries[5][0]
    assert "FROM public.memory_summaries" in executed_queries[6][0]
    assert "FROM public.memory_summary_memberships" in executed_queries[9][0]


def test_refresh_age_summary_graph_reports_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExplodingCursor:
        def __enter__(self) -> "ExplodingCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            raise RuntimeError("summary graph refresh exploded")

    class ExplodingConnection:
        def __enter__(self) -> "ExplodingConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> ExplodingCursor:
            return ExplodingCursor()

    fake_psycopg = SimpleNamespace(connect=lambda database_url: ExplodingConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())

    exit_code = cli_module._refresh_age_summary_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_summary_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Failed to refresh AGE summary graph: summary graph refresh exploded"
        in captured.err
    )


def test_main_dispatches_to_resume_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    args = argparse.Namespace(command="resume-workflow")
    parser = SimpleNamespace(parse_args=lambda argv: args)

    called_with: list[argparse.Namespace] = []

    monkeypatch.setattr(cli_module, "_build_parser", lambda: parser)
    monkeypatch.setattr(
        cli_module,
        "_resume_workflow",
        lambda passed_args: called_with.append(passed_args) or 17,
    )

    assert cli_module.main([]) == 17
    assert called_with == [args]


def test_main_dispatches_age_graph_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    received_database_urls: list[str | None] = []
    received_graph_names: list[str | None] = []

    def fake_age_graph_readiness(args: argparse.Namespace) -> int:
        received_database_urls.append(args.database_url)
        received_graph_names.append(args.graph_name)
        return 17

    monkeypatch.setattr(cli_module, "_age_graph_readiness", fake_age_graph_readiness)

    result = cli_module.main(
        [
            "age-graph-readiness",
            "--database-url",
            "postgresql://explicit/db",
            "--graph-name",
            "ctxledger_ready_graph",
        ]
    )

    assert result == 17
    assert received_database_urls == ["postgresql://explicit/db"]
    assert received_graph_names == ["ctxledger_ready_graph"]


def test_serve_propagates_runtime_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_server(**kwargs: object) -> int:
        raise ImportError("server missing")

    monkeypatch.setattr("ctxledger.server.run_server", fake_run_server)

    with pytest.raises(ImportError, match="server missing"):
        cli_module._serve(argparse.Namespace(transport=None, host=None, port=None))


def test_format_stats_text_renders_values() -> None:
    stats = WorkflowStats(
        workspace_count=1,
        workflow_status_counts={
            "running": 2,
            "completed": 3,
            "failed": 4,
            "cancelled": 5,
        },
        attempt_status_counts={
            "running": 6,
            "succeeded": 7,
            "failed": 8,
            "cancelled": 9,
        },
        verify_status_counts={
            "pending": 10,
            "passed": 11,
            "failed": 12,
            "skipped": 13,
        },
        checkpoint_count=14,
        episode_count=15,
        memory_item_count=16,
        memory_embedding_count=17,
        checkpoint_auto_memory_recorded_count=18,
        checkpoint_auto_memory_skipped_count=19,
        workflow_completion_auto_memory_recorded_count=20,
        workflow_completion_auto_memory_skipped_count=21,
        derived_memory_item_count=22,
        derived_memory_item_state="canonical_only",
        derived_memory_item_reason=(
            "canonical summary state exists but derived memory items are not materialized"
        ),
        derived_memory_graph_status="graph_ready",
        structured_checkpoint_coverage={
            "current_objective": 8,
            "next_intended_action": 9,
            "verify_target": 4,
            "resume_hint": 3,
            "blocker_or_risk": 2,
            "failure_guard": 1,
            "root_cause": 5,
            "recovery_pattern": 6,
            "what_remains": 7,
            "checkpoint_count": 14,
        },
        summary_backlog_count=0,
        completion_summary_build_request_count=29,
        completion_summary_build_attempted_count=30,
        completion_summary_build_success_count=31,
        completion_summary_build_skipped_reason_counts={
            "workflow_summary_build_not_requested": 12,
            "summary_build_failed": 1,
        },
        memory_summary_count=23,
        memory_summary_membership_count=24,
        age_summary_graph_ready_count=25,
        age_summary_graph_stale_count=26,
        age_summary_graph_degraded_count=27,
        age_summary_graph_unknown_count=28,
        latest_workflow_updated_at=datetime(2024, 10, 1, tzinfo=UTC),
        latest_checkpoint_created_at=datetime(2024, 10, 2, tzinfo=UTC),
        latest_verify_report_created_at=datetime(2024, 10, 3, tzinfo=UTC),
        latest_episode_created_at=datetime(2024, 10, 4, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2024, 10, 5, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2024, 10, 6, tzinfo=UTC),
    )

    rendered = cli_module._format_stats_text(stats)

    assert "ctxledger stats" in rendered
    assert "- total: 1" in rendered
    assert "- running: 2" in rendered
    assert "- completed: 3" in rendered
    assert "- failed: 4" in rendered
    assert "- cancelled: 5" in rendered
    assert "- succeeded: 7" in rendered
    assert "- pending: 10" in rendered
    assert "- passed: 11" in rendered
    assert "- episodes: 15" in rendered
    assert "- memory_items: 16" in rendered
    assert "- memory_embeddings: 17" in rendered
    assert "- derived_memory_items: 22" in rendered
    assert "- checkpoint_auto_memory_recorded: 18" in rendered
    assert "- checkpoint_auto_memory_skipped: 19" in rendered
    assert "- workflow_completion_auto_memory_recorded: 20" in rendered
    assert "- workflow_completion_auto_memory_skipped: 21" in rendered
    assert "- memory_summaries: 23" in rendered
    assert "- memory_summary_memberships: 24" in rendered
    assert "- age_summary_graph_ready: 25" in rendered
    assert "- age_summary_graph_stale: 26" in rendered
    assert "- age_summary_graph_degraded: 27" in rendered
    assert "- age_summary_graph_unknown: 28" in rendered
    assert "Completion summary build observability:" in rendered
    assert "- request_count: 29" in rendered
    assert "- attempted_count: 30" in rendered
    assert "- success_count: 31" in rendered
    assert "- skipped_reason_counts:" in rendered
    assert "  - summary_build_failed: 1" in rendered
    assert "  - workflow_summary_build_not_requested: 12" in rendered
    assert "- derived_memory_item_state: canonical_only" in rendered
    assert (
        "- derived_memory_item_reason: canonical summary state exists but derived memory items are not materialized"
        in rendered
    )
    assert "- derived_memory_graph_status: graph_ready" in rendered
    assert "- current_objective: 8" in rendered
    assert "- next_intended_action: 9" in rendered
    assert "- verify_target: 4" in rendered
    assert "- resume_hint: 3" in rendered
    assert "- blocker_or_risk: 2" in rendered
    assert "- failure_guard: 1" in rendered
    assert "- root_cause: 5" in rendered
    assert "- recovery_pattern: 6" in rendered
    assert "- what_remains: 7" in rendered
    assert "- checkpoints: 14" in rendered
    assert "- summary_backlog_count: 0" in rendered
    assert "2024-10-01 00:00:00+00:00" in rendered
    assert "2024-10-06 00:00:00+00:00" in rendered
    assert "- workflow_updated_at: 2024-10-01 00:00:00+00:00" in rendered
    assert "- memory_embedding_created_at: 2024-10-06 00:00:00+00:00" in rendered


def test_build_postgres_workflow_service_returns_settings_service_and_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = make_settings(database_url="postgresql://ctxledger/db")
    config_marker = object()
    pool_marker = object()
    uow_factory_marker = object()
    workflow_service_calls: list[object] = []

    class FakePostgresConfig:
        @classmethod
        def from_settings(cls, received_settings: object) -> object:
            assert received_settings is settings
            return config_marker

    def fake_build_connection_pool(received_config: object) -> object:
        assert received_config is config_marker
        return pool_marker

    def fake_build_postgres_uow_factory(
        received_config: object, received_pool: object
    ) -> object:
        assert received_config is config_marker
        assert received_pool is pool_marker
        return uow_factory_marker

    class FakeWorkflowService:
        def __init__(self, uow_factory: object) -> None:
            workflow_service_calls.append(uow_factory)

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_connection_pool", fake_build_connection_pool
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        fake_build_postgres_uow_factory,
    )
    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService", FakeWorkflowService
    )

    returned_settings, workflow_service, connection_pool = (
        cli_module._build_postgres_workflow_service()
    )

    assert returned_settings is settings
    assert isinstance(workflow_service, FakeWorkflowService)
    assert connection_pool is pool_marker
    assert workflow_service_calls == [uow_factory_marker]


def test_build_postgres_workflow_service_raises_for_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings", lambda: make_settings(database_url="")
    )

    with pytest.raises(RuntimeError, match="missing_database_url"):
        cli_module._build_postgres_workflow_service()


def test_stats_renders_json_output_and_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    stats = WorkflowStats(
        workspace_count=2,
        workflow_status_counts={"running": 1},
        attempt_status_counts={"succeeded": 3},
        verify_status_counts={"passed": 4},
        checkpoint_count=5,
        episode_count=6,
        memory_item_count=7,
        memory_embedding_count=8,
        checkpoint_auto_memory_recorded_count=9,
        checkpoint_auto_memory_skipped_count=10,
        workflow_completion_auto_memory_recorded_count=11,
        workflow_completion_auto_memory_skipped_count=12,
        structured_checkpoint_coverage={
            "current_objective": 2,
            "next_intended_action": 3,
            "verify_target": 1,
            "resume_hint": 1,
            "blocker_or_risk": 0,
            "failure_guard": 0,
            "root_cause": 2,
            "recovery_pattern": 2,
            "what_remains": 4,
            "checkpoint_count": 5,
        },
        summary_backlog_count=0,
        completion_summary_build_request_count=6,
        completion_summary_build_attempted_count=4,
        completion_summary_build_success_count=3,
        completion_summary_build_skipped_reason_counts={
            "workflow_summary_build_not_requested": 2,
            "summary_build_failed": 1,
        },
        completion_summary_build_request_rate=0.6,
        completion_summary_build_attempted_rate=0.4,
        completion_summary_build_success_rate=0.3,
        completion_summary_build_request_rate_base=10,
        completion_summary_build_attempted_rate_base=10,
        completion_summary_build_success_rate_base=10,
        completion_summary_build_status_counts={
            "built": 3,
            "skipped": 6,
        },
        completion_summary_build_status_total_count=9,
        completion_summary_build_skipped_reason_total_count=3,
        memory_summary_count=13,
        memory_summary_membership_count=14,
        age_summary_graph_ready_count=15,
        age_summary_graph_stale_count=16,
        age_summary_graph_degraded_count=17,
        age_summary_graph_unknown_count=18,
        latest_workflow_updated_at=datetime(2024, 11, 1, tzinfo=UTC),
        latest_checkpoint_created_at=None,
        latest_verify_report_created_at=None,
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
    )
    close_calls: list[str] = []

    class DummyWorkflowService:
        def get_stats(self) -> WorkflowStats:
            return stats

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), DummyWorkflowService(), DummyConnectionPool()),
    )

    exit_code = cli_module._stats(argparse.Namespace(format="json"))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    payload = json.loads(captured.out)
    assert payload["workspace_count"] == 2
    assert payload["memory_embedding_count"] == 8
    assert payload["checkpoint_auto_memory_recorded_count"] == 9
    assert payload["checkpoint_auto_memory_skipped_count"] == 10
    assert payload["workflow_completion_auto_memory_recorded_count"] == 11
    assert payload["workflow_completion_auto_memory_skipped_count"] == 12
    assert payload["structured_checkpoint_coverage"] == {
        "current_objective": 2,
        "next_intended_action": 3,
        "verify_target": 1,
        "resume_hint": 1,
        "blocker_or_risk": 0,
        "failure_guard": 0,
        "root_cause": 2,
        "recovery_pattern": 2,
        "what_remains": 4,
        "checkpoint_count": 5,
    }
    assert payload["summary_backlog_count"] == 0
    assert payload["completion_summary_build_request_count"] == 6
    assert payload["completion_summary_build_attempted_count"] == 4
    assert payload["completion_summary_build_success_count"] == 3
    assert payload["completion_summary_build_skipped_reason_counts"] == {
        "workflow_summary_build_not_requested": 2,
        "summary_build_failed": 1,
    }
    assert payload["completion_summary_build_request_rate"] == 0.6
    assert payload["completion_summary_build_attempted_rate"] == 0.4
    assert payload["completion_summary_build_success_rate"] == 0.3
    assert payload["completion_summary_build_request_rate_base"] == 10
    assert payload["completion_summary_build_attempted_rate_base"] == 10
    assert payload["completion_summary_build_success_rate_base"] == 10
    assert payload["completion_summary_build_status_counts"] == {
        "built": 3,
        "skipped": 6,
    }
    assert payload["completion_summary_build_status_total_count"] == 9
    assert payload["completion_summary_build_attempted_minus_status_total_count"] == -5
    assert payload["completion_summary_build_skipped_reason_total_count"] == 3
    assert (
        payload["completion_summary_build_status_minus_skipped_reason_total_count"] == 6
    )
    assert payload["memory_summary_count"] == 13
    assert payload["memory_summary_membership_count"] == 14
    assert payload["age_summary_graph_ready_count"] == 15
    assert payload["age_summary_graph_stale_count"] == 16
    assert payload["age_summary_graph_degraded_count"] == 17
    assert payload["age_summary_graph_unknown_count"] == 18
    assert payload["latest_workflow_updated_at"] == "2024-11-01T00:00:00+00:00"
    assert close_calls == ["close"]


def test_stats_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_stats_reports_get_stats_failure_and_still_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    close_calls: list[str] = []

    class ExplodingWorkflowService:
        def get_stats(self) -> WorkflowStats:
            raise RuntimeError("stats lookup exploded")

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), ExplodingWorkflowService(), DummyConnectionPool()),
    )

    exit_code = cli_module._stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: stats lookup exploded" in captured.err
    assert close_calls == ["close"]


def test_memory_stats_renders_text_output_and_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    memory_stats = MemoryStats(
        episode_count=3,
        memory_item_count=4,
        memory_embedding_count=5,
        memory_relation_count=6,
        memory_item_provenance_counts={"episode": 4},
        checkpoint_auto_memory_recorded_count=2,
        checkpoint_auto_memory_skipped_count=1,
        workflow_completion_auto_memory_recorded_count=3,
        workflow_completion_auto_memory_skipped_count=0,
        completion_summary_build_request_count=4,
        completion_summary_build_attempted_count=3,
        completion_summary_build_success_count=2,
        completion_summary_build_skipped_reason_counts={
            "summary_build_failed": 1,
            "workflow_summary_build_not_requested": 1,
        },
        completion_summary_build_request_rate=1.0,
        completion_summary_build_attempted_rate=0.75,
        completion_summary_build_success_rate=0.5,
        completion_summary_build_request_rate_base=4,
        completion_summary_build_attempted_rate_base=4,
        completion_summary_build_success_rate_base=4,
        completion_summary_build_status_counts={
            "built": 2,
            "skipped": 1,
        },
        completion_summary_build_status_total_count=3,
        completion_summary_build_skipped_reason_total_count=2,
        completion_summary_build_status_minus_skipped_reason_total_count=1,
        memory_summary_count=7,
        memory_summary_membership_count=8,
        age_summary_graph_ready_count=1,
        age_summary_graph_stale_count=0,
        age_summary_graph_degraded_count=0,
        age_summary_graph_unknown_count=0,
        latest_episode_created_at=datetime(2024, 11, 2, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2024, 11, 3, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2024, 11, 4, tzinfo=UTC),
        latest_memory_relation_created_at=datetime(2024, 11, 5, tzinfo=UTC),
    )
    close_calls: list[str] = []

    class DummyWorkflowService:
        def get_memory_stats(self) -> MemoryStats:
            return memory_stats

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), DummyWorkflowService(), DummyConnectionPool()),
    )

    exit_code = cli_module._memory_stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert "ctxledger memory-stats" in captured.out
    assert "- episodes: 3" in captured.out
    assert "- memory_items: 4" in captured.out
    assert "- memory_embeddings: 5" in captured.out
    assert "- memory_relations: 6" in captured.out
    assert "- checkpoint_auto_memory_recorded: 2" in captured.out
    assert "- checkpoint_auto_memory_skipped: 1" in captured.out
    assert "- workflow_completion_auto_memory_recorded: 3" in captured.out
    assert "- workflow_completion_auto_memory_skipped: 0" in captured.out
    assert "Completion summary build observability:" in captured.out
    assert "- request_count: 4" in captured.out
    assert "- attempted_count: 3" in captured.out
    assert "- success_count: 2" in captured.out
    assert "- skipped_reason_counts:" in captured.out
    assert "  - summary_build_failed: 1" in captured.out
    assert "  - workflow_summary_build_not_requested: 1" in captured.out
    assert "- request_rate: 1.000" in captured.out
    assert "- attempted_rate: 0.750" in captured.out
    assert "- success_rate: 0.500" in captured.out
    assert "- request_rate_base: 4" in captured.out
    assert "- attempted_rate_base: 4" in captured.out
    assert "- success_rate_base: 4" in captured.out
    assert "- status_counts:" in captured.out
    assert "  - built: 2" in captured.out
    assert "  - skipped: 1" in captured.out
    assert "- status_total: 3" in captured.out
    assert "- attempted_minus_status_total_count: 0" in captured.out
    assert "- skipped_reason_total: 2" in captured.out
    assert "- status_minus_skipped_reason_total_count: 1" in captured.out
    assert "- memory_summaries: 7" in captured.out
    assert "- memory_summary_memberships: 8" in captured.out
    assert "- age_summary_graph_ready: 1" in captured.out
    assert "- age_summary_graph_stale: 0" in captured.out
    assert "- age_summary_graph_degraded: 0" in captured.out
    assert "- age_summary_graph_unknown: 0" in captured.out
    assert "- memory_relation_created_at: 2024-11-05 00:00:00+00:00" in captured.out
    assert close_calls == ["close"]


def test_memory_stats_reports_service_failure_and_still_closes_pool(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    close_calls: list[str] = []

    class ExplodingWorkflowService:
        def get_memory_stats(self) -> MemoryStats:
            raise RuntimeError("memory stats exploded")

    class DummyConnectionPool:
        def close(self) -> None:
            close_calls.append("close")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), ExplodingWorkflowService(), DummyConnectionPool()),
    )

    exit_code = cli_module._memory_stats(argparse.Namespace(format="json"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load memory stats: memory stats exploded" in captured.err
    assert close_calls == ["close"]


def test_workflows_reports_invalid_workspace_id_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class DummyConnectionPool:
        def close(self) -> None:
            raise AssertionError("close should not be called")

    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (object(), object(), DummyConnectionPool()),
    )

    exit_code = cli_module._workflows(
        argparse.Namespace(
            limit=20,
            status=None,
            workspace_id="not-a-uuid",
            ticket_id=None,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Failed to load workflows: badly formed hexadecimal UUID string" in captured.err
    )

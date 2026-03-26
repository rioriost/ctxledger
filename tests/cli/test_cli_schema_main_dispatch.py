from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.version import get_app_version
from ctxledger.workflow.service import (
    FailureListEntry,
    MemoryStats,
    WorkflowListEntry,
    WorkflowStats,
)

from .conftest import make_settings


def test_main_unknown_command_uses_parser_error(monkeypatch: pytest.MonkeyPatch) -> None:
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

    monkeypatch.setattr(cli_module, "_build_episode_summary", fake_build_episode_summary)

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
        connect=lambda database_url: connect_calls.append(database_url) or FakeConnection()
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
    assert "Failed to refresh AGE summary graph: summary graph refresh exploded" in captured.err
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == []
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed_queries[2][1] == ("ctxledger_summary_graph",)
    assert executed_queries[3][0] == "SELECT ag_catalog.create_graph('ctxledger_summary_graph')"
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
    assert "Failed to refresh AGE summary graph: summary graph refresh exploded" in captured.err


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
        latest_workflow_updated_at=None,
        latest_checkpoint_created_at=None,
        latest_verify_report_created_at=None,
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
    )

    rendered = cli_module._format_stats_text(stats)

    assert "- total: 1" in rendered
    assert "- running: 2" in rendered
    assert "- completed: 3" in rendered
    assert "- failed: 4" in rendered
    assert "- cancelled: 5" in rendered
    assert "- succeeded: 7" in rendered
    assert "- pending: 10" in rendered
    assert "- passed: 11" in rendered
    assert "- skipped: 13" in rendered
    assert "- checkpoints: 14" in rendered
    assert "- episodes: 15" in rendered
    assert "- memory_items: 16" in rendered
    assert "- memory_embeddings: 17" in rendered


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
    assert "Failed to load workflows: badly formed hexadecimal UUID string" in captured.err

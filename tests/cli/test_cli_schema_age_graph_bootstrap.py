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


def test_bootstrap_age_graph_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )


def test_bootstrap_age_graph_uses_explicit_database_url_and_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [None, ("0",), ("0",)]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return []
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return []
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
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=0, supports edges repopulated=0)."
    )
    assert captured.err == ""
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == ["commit"]
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed_queries[2][1] == ("ctxledger_test_graph",)
    assert executed_queries[3][0] == "SELECT ag_catalog.create_graph('ctxledger_test_graph')"
    assert executed_queries[3][1] is None
    assert executed_queries[4][1] is None
    assert executed_queries[5][1] is None
    assert executed_queries[6][1] is None
    assert executed_queries[7][1] is None
    assert executed_queries[8][1] is None


def test_bootstrap_age_graph_uses_tuple_rows_for_memory_items_and_relations(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [None, {"count": "0"}, {"count": "0"}]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return [(uuid4(),)]
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return [(uuid4(), uuid4(), uuid4())]
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
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=0, supports edges repopulated=0)."
    )
    assert captured.err == ""
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == ["commit"]
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed_queries[2][1] == ("ctxledger_test_graph",)
    assert executed_queries[3][0] == "SELECT ag_catalog.create_graph('ctxledger_test_graph')"
    assert executed_queries[3][1] is None
    assert executed_queries[4][1] is None
    assert executed_queries[5][1] is None
    assert any(
        "CREATE (n:memory_item {memory_id: $memory_id})" in query and params is not None
        for query, params in executed_queries
    )
    assert any(
        "CREATE (source)-[r:supports {" in query and params is not None
        for query, params in executed_queries
    )


def test_bootstrap_age_graph_uses_mapping_rows_for_memory_items_and_relations(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [None, {"count": "0"}, {"count": "0"}]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return [{"memory_id": uuid4()}]
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return [
                    {
                        "memory_relation_id": uuid4(),
                        "source_memory_id": uuid4(),
                        "target_memory_id": uuid4(),
                    }
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
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=0, supports edges repopulated=0)."
    )
    assert captured.err == ""
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == ["commit"]
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed_queries[2][1] == ("ctxledger_test_graph",)
    assert executed_queries[3][0] == "SELECT ag_catalog.create_graph('ctxledger_test_graph')"
    assert executed_queries[3][1] is None
    assert executed_queries[4][1] is None
    assert executed_queries[5][1] is None
    assert any(
        "CREATE (n:memory_item {memory_id: $memory_id})" in query and params is not None
        for query, params in executed_queries
    )
    assert any(
        "CREATE (source)-[r:supports {" in query and params is not None
        for query, params in executed_queries
    )


def test_bootstrap_age_graph_skips_create_graph_when_graph_already_exists(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [(1,), ("0",), ("0",)]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return []
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return []
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
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=0, supports edges repopulated=0)."
    )
    assert captured.err == ""
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == ["commit"]
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == ('SET search_path = ag_catalog, "$user", public', None)
    assert executed_queries[2][1] == ("ctxledger_test_graph",)
    assert all(
        query != "SELECT ag_catalog.create_graph('ctxledger_test_graph')"
        for query, _ in executed_queries
    )


def test_bootstrap_age_graph_reports_driver_import_failure(
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

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to import PostgreSQL driver. Install psycopg[binary] first." in captured.err


def test_bootstrap_age_graph_reports_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExplodingCursor:
        def __enter__(self) -> "ExplodingCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            raise RuntimeError("graph exploded")

    class ExplodingConnection:
        def __enter__(self) -> "ExplodingConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> ExplodingCursor:
            return ExplodingCursor()

    fake_psycopg = SimpleNamespace(connect=lambda database_url: ExplodingConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to bootstrap AGE graph: graph exploded" in captured.err


def test_bootstrap_age_graph_requires_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()
    settings = settings.__class__(
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment,
        database=settings.database.__class__(
            url=settings.database.url,
            connect_timeout_seconds=settings.database.connect_timeout_seconds,
            statement_timeout_ms=settings.database.statement_timeout_ms,
            schema_name=settings.database.schema_name,
            pool_min_size=settings.database.pool_min_size,
            pool_max_size=settings.database.pool_max_size,
            pool_timeout_seconds=settings.database.pool_timeout_seconds,
            age_enabled=settings.database.age_enabled,
            age_graph_name="",
        ),
        http=settings.http,
        debug=settings.debug,
        logging=settings.logging,
        embedding=settings.embedding,
    )
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: settings,
    )

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url=None,
            graph_name=None,
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name."
        in captured.err
    )


def test_bootstrap_age_graph_uses_mapping_count_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [
                (1,),
                {"count": "2"},
                {"count": "3"},
            ]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return []
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return []
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

    fake_psycopg = SimpleNamespace(connect=lambda database_url: FakeConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=2, supports edges repopulated=3)."
    )
    assert commit_calls == ["commit"]


def test_bootstrap_age_graph_uses_tuple_count_rows(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [
                (1,),
                ("4",),
                ("5",),
            ]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

        def fetchall(self) -> list[object]:
            last_query = executed_queries[-1][0]
            if "SELECT memory_id" in last_query:
                return []
            if "SELECT\n                        mr.memory_relation_id" in last_query:
                return []
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

    fake_psycopg = SimpleNamespace(connect=lambda database_url: FakeConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: make_settings())

    exit_code = cli_module._bootstrap_age_graph(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.strip() == (
        "AGE graph bootstrap completed for 'ctxledger_test_graph' "
        "(memory_item nodes repopulated=4, supports edges repopulated=5)."
    )
    assert commit_calls == ["commit"]

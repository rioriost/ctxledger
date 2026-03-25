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
    assert captured.out.strip() == get_app_version()
    assert captured.err == ""


def test_print_missing_database_url_omits_override_hint_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli_module._print_missing_database_url()

    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert captured.err == "Database URL is required. Set CTXLEDGER_DATABASE_URL.\n"


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


def test_isoformat_or_none_returns_isoformat_for_datetime() -> None:
    class FakeDatetime:
        def isoformat(self) -> str:
            return "2026-03-17T11:00:00+00:00"

    assert cli_module._isoformat_or_none(FakeDatetime()) == "2026-03-17T11:00:00+00:00"


def test_isoformat_or_none_returns_none_for_none() -> None:
    assert cli_module._isoformat_or_none(None) is None


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
        connect=lambda database_url: connect_calls.append(database_url) or FakeConnection()
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
    assert "Failed to import PostgreSQL driver. Install psycopg[binary] first." in captured.err


def test_apply_schema_reports_connect_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    call_log: list[tuple[str, object]] = []

    def fake_load_postgres_schema_sql() -> str:
        call_log.append(("load_postgres_schema_sql", None))
        return "SELECT 1;"

    def fake_connect(database_url: str) -> object:
        call_log.append(("connect", database_url))
        raise RuntimeError(f"connect exploded: {database_url}")

    fake_psycopg = SimpleNamespace(connect=fake_connect)

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        fake_load_postgres_schema_sql,
    )

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to apply schema: connect exploded: postgresql://explicit/db" in captured.err
    assert call_log == [
        ("load_postgres_schema_sql", None),
        ("connect", "postgresql://explicit/db"),
    ]


def test_apply_schema_reports_cursor_execute_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExplodingCursor:
        def __enter__(self) -> "ExplodingCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str) -> None:
            raise RuntimeError("cursor execute exploded")

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> ExplodingCursor:
            return ExplodingCursor()

        def commit(self) -> None:
            raise AssertionError("commit should not be reached")

    fake_psycopg = SimpleNamespace(connect=lambda database_url: FakeConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        lambda: "SELECT 1;",
    )

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to apply schema: cursor execute exploded" in captured.err


def test_apply_schema_reports_commit_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_sql: list[str] = []

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
            raise RuntimeError("commit exploded")

    fake_psycopg = SimpleNamespace(connect=lambda database_url: FakeConnection())

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        lambda: "SELECT 1;",
    )

    exit_code = cli_module._apply_schema(
        argparse.Namespace(database_url="postgresql://explicit/db")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to apply schema: commit exploded" in captured.err
    assert executed_sql == ["SELECT 1;"]


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


def test_age_graph_readiness_reports_missing_database_url(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url=""),
    )

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        in captured.err
    )


def test_age_graph_readiness_requires_graph_name(
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
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert (
        "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name."
        in captured.err
    )


def test_age_graph_readiness_uses_explicit_database_url_and_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakePostgresConfig:
        def __init__(
            self,
            *,
            database_url: str,
            connect_timeout_seconds: int,
            statement_timeout_ms: int | None,
            schema_name: str,
            pool_min_size: int,
            pool_max_size: int,
            pool_timeout_seconds: int,
            age_enabled: bool,
            age_graph_name: str,
        ) -> None:
            self.database_url = database_url
            self.connect_timeout_seconds = connect_timeout_seconds
            self.statement_timeout_ms = statement_timeout_ms
            self.schema_name = schema_name
            self.pool_min_size = pool_min_size
            self.pool_max_size = pool_max_size
            self.pool_timeout_seconds = pool_timeout_seconds
            self.age_enabled = age_enabled
            self.age_graph_name = age_graph_name

    class GraphReadyStatus:
        value = "graph_ready"

    class FakeChecker:
        def __init__(self, config: object) -> None:
            self.config = config

        def age_graph_status(self, graph_name: str) -> GraphReadyStatus:
            assert graph_name == "ctxledger_explicit_graph"
            return GraphReadyStatus()

        def age_available(self) -> bool:
            return True

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresDatabaseHealthChecker", FakeChecker)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_explicit_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_explicit_graph",
        "age_available": True,
        "age_graph_status": "graph_ready",
        "summary_graph_mirroring": {
            "enabled": False,
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "graph_status": "graph_ready",
            "ready": True,
        },
        "workflow_summary_automation": {
            "orchestration_point": "workflow_completion_auto_memory",
            "default_requested": False,
            "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
            "trigger": "latest_checkpoint.build_episode_summary_true",
            "target_scope": "workflow_completion_auto_memory_episode",
            "summary_kind": "episode_summary",
            "replace_existing": True,
            "non_fatal": True,
        },
    }


def test_age_graph_readiness_reports_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class ExplodingPostgresConfig:
        def __init__(
            self,
            *,
            database_url: str,
            connect_timeout_seconds: int,
            statement_timeout_ms: int | None,
            schema_name: str,
            pool_min_size: int,
            pool_max_size: int,
            pool_timeout_seconds: int,
            age_enabled: bool,
            age_graph_name: str,
        ) -> None:
            raise RuntimeError("readiness exploded")

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", ExplodingPostgresConfig)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(database_url=None, graph_name=None)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to check AGE graph readiness: readiness exploded" in captured.err


def test_age_graph_readiness_serializes_non_enum_status_and_false_age_available(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    settings = make_settings()

    class FakePostgresConfig:
        def __init__(
            self,
            *,
            database_url: str,
            connect_timeout_seconds: int,
            statement_timeout_ms: int | None,
            schema_name: str,
            pool_min_size: int,
            pool_max_size: int,
            pool_timeout_seconds: int,
            age_enabled: bool,
            age_graph_name: str,
        ) -> None:
            self.database_url = database_url
            self.connect_timeout_seconds = connect_timeout_seconds
            self.statement_timeout_ms = statement_timeout_ms
            self.schema_name = schema_name
            self.pool_min_size = pool_min_size
            self.pool_max_size = pool_max_size
            self.pool_timeout_seconds = pool_timeout_seconds
            self.age_enabled = age_enabled
            self.age_graph_name = age_graph_name

    class FakeChecker:
        def __init__(self, config: object) -> None:
            self.config = config

        def age_graph_status(self, graph_name: str) -> str:
            assert graph_name == "ctxledger_explicit_graph"
            return "missing"

        def age_available(self) -> bool:
            return False

    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresConfig", FakePostgresConfig)
    monkeypatch.setattr("ctxledger.db.postgres.PostgresDatabaseHealthChecker", FakeChecker)

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_explicit_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_explicit_graph",
        "age_available": False,
        "age_graph_status": "missing",
        "summary_graph_mirroring": {
            "enabled": False,
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "derived_graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "refresh_command": "ctxledger refresh-age-summary-graph",
            "read_path_scope": "narrow_auxiliary_summary_member_traversal",
            "graph_status": "missing",
            "ready": False,
        },
        "workflow_summary_automation": {
            "orchestration_point": "workflow_completion_auto_memory",
            "default_requested": False,
            "request_field": "latest_checkpoint.checkpoint_json.build_episode_summary",
            "trigger": "latest_checkpoint.build_episode_summary_true",
            "target_scope": "workflow_completion_auto_memory_episode",
            "summary_kind": "episode_summary",
            "replace_existing": True,
            "non_fatal": True,
        },
    }


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


def test_apply_schema_reports_missing_database_url_from_settings(
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


def test_apply_schema_uses_settings_database_url_when_argument_is_none(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connect_calls: list[str] = []
    executed_sql: list[str] = []
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
        connect=lambda database_url: connect_calls.append(database_url) or FakeConnection()
    )

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(database_url="postgresql://from-settings/db"),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.load_postgres_schema_sql",
        lambda: "SELECT 42;",
    )

    exit_code = cli_module._apply_schema(argparse.Namespace(database_url=None))
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "Schema applied successfully."
    assert captured.err == ""
    assert connect_calls == ["postgresql://from-settings/db"]
    assert executed_sql == ["SELECT 42;"]
    assert commit_calls == ["commit"]


def test_stats_reraises_unexpected_runtime_error_from_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_builder() -> tuple[object, object, object]:
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(cli_module, "_build_postgres_workflow_service", fake_builder)

    exit_code = cli_module._stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: builder exploded" in captured.err


def test_workflows_reraises_unexpected_runtime_error_from_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_builder() -> tuple[object, object, object]:
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(cli_module, "_build_postgres_workflow_service", fake_builder)

    exit_code = cli_module._workflows(
        argparse.Namespace(
            format="text",
            workspace_id=None,
            limit=5,
            status=None,
            ticket_id=None,
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load workflows: builder exploded" in captured.err


def test_failures_reraises_unexpected_runtime_error_from_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_builder() -> tuple[object, object, object]:
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(cli_module, "_build_postgres_workflow_service", fake_builder)

    exit_code = cli_module._failures(
        argparse.Namespace(format="text", limit=5, status=None, open_only=False)
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load failures: builder exploded" in captured.err


def test_memory_stats_reraises_unexpected_runtime_error_from_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_builder() -> tuple[object, object, object]:
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(cli_module, "_build_postgres_workflow_service", fake_builder)

    exit_code = cli_module._memory_stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load memory stats: builder exploded" in captured.err


def test_resume_workflow_reraises_unexpected_runtime_error_from_builder(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fake_builder() -> tuple[object, object, object]:
        raise RuntimeError("builder exploded")

    monkeypatch.setattr(cli_module, "_build_postgres_workflow_service", fake_builder)

    exit_code = cli_module._resume_workflow(
        argparse.Namespace(workflow_instance_id=str(uuid4()), format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to resume workflow: builder exploded" in captured.err


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


def test_format_failures_text_renders_none_fallbacks() -> None:
    failure = FailureListEntry(
        failure_scope="workflow",
        failure_type="runtime",
        failure_status="open",
        target_path=None,
        error_code=None,
        error_message="failed",
        attempt_id=None,
        occurred_at=datetime(2026, 3, 17, 13, 0, 0, tzinfo=UTC),
        resolved_at=None,
        open_failure_count=0,
        retry_count=0,
    )

    rendered = cli_module._format_failures_text((failure,))

    assert "path=none" in rendered
    assert "error_code=none" in rendered
    assert "resolved_at=None" in rendered
    assert "retry_count=0" in rendered
    assert "open_failures=0" in rendered


def test_format_memory_stats_text_renders_none_when_provenance_missing() -> None:
    stats = SimpleNamespace(
        episode_count=0,
        memory_item_count=0,
        memory_embedding_count=0,
        memory_relation_count=0,
        memory_item_provenance_counts={},
        latest_episode_created_at=None,
        latest_memory_item_created_at=None,
        latest_memory_embedding_created_at=None,
        latest_memory_relation_created_at=None,
    )

    rendered = cli_module._format_memory_stats_text(stats)

    assert "ctxledger memory-stats" in rendered
    assert "Memory item provenance:" in rendered
    assert "- none" in rendered
    assert "- memory_relation_created_at: None" in rendered


def test_format_workflows_text_renders_empty_result() -> None:
    rendered = cli_module._format_workflows_text(())

    assert rendered == "ctxledger workflows\n\n- none"


def test_format_failures_text_renders_empty_result() -> None:
    rendered = cli_module._format_failures_text(())

    assert rendered == "ctxledger failures\n\n- none"


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


def test_workflows_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._workflows(
        argparse.Namespace(
            limit=20,
            status=None,
            workspace_id=None,
            ticket_id=None,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_failures_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._failures(
        argparse.Namespace(limit=20, status=None, open_only=False, format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_memory_stats_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._memory_stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


def test_resume_workflow_reports_missing_database_url_from_builder_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "UUID",
        lambda value: uuid4(),
    )
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("missing_database_url")),
    )

    exit_code = cli_module._resume_workflow(
        argparse.Namespace(workflow_instance_id=str(uuid4()), format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Database URL is required. Set CTXLEDGER_DATABASE_URL." in captured.err


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


def test_stats_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("stats exploded")),
    )

    exit_code = cli_module._stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load stats: stats exploded" in captured.err


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


def test_workflows_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("workflows exploded")),
    )

    exit_code = cli_module._workflows(
        argparse.Namespace(
            limit=20,
            status=None,
            workspace_id=None,
            ticket_id=None,
            format="text",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load workflows: workflows exploded" in captured.err


def test_failures_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("failures exploded")),
    )

    exit_code = cli_module._failures(
        argparse.Namespace(limit=20, status=None, open_only=False, format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load failures: failures exploded" in captured.err


def test_memory_stats_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("memory stats exploded")),
    )

    exit_code = cli_module._memory_stats(argparse.Namespace(format="text"))
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to load memory stats: memory stats exploded" in captured.err


def test_resume_workflow_reports_invalid_uuid_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        cli_module,
        "UUID",
        lambda value: (_ for _ in ()).throw(ValueError("resume uuid exploded")),
    )

    exit_code = cli_module._resume_workflow(
        argparse.Namespace(workflow_instance_id="not-a-uuid", format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to resume workflow: resume uuid exploded" in captured.err


def test_resume_workflow_reports_unexpected_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli_module, "UUID", lambda value: UUID(int=0))
    monkeypatch.setattr(
        cli_module,
        "_build_postgres_workflow_service",
        lambda: (_ for _ in ()).throw(RuntimeError("resume service exploded")),
    )

    exit_code = cli_module._resume_workflow(
        argparse.Namespace(workflow_instance_id=str(uuid4()), format="text")
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to resume workflow: resume service exploded" in captured.err


def test_format_memory_stats_text_renders_values() -> None:
    stats = MemoryStats(
        episode_count=2,
        memory_item_count=3,
        memory_embedding_count=4,
        memory_relation_count=5,
        memory_item_provenance_counts={
            "checkpoint": 1,
            "episode": 2,
        },
        latest_episode_created_at=datetime(2026, 3, 17, 12, 0, 0, tzinfo=UTC),
        latest_memory_item_created_at=datetime(2026, 3, 17, 12, 1, 0, tzinfo=UTC),
        latest_memory_embedding_created_at=datetime(2026, 3, 17, 12, 2, 0, tzinfo=UTC),
        latest_memory_relation_created_at=datetime(2026, 3, 17, 12, 3, 0, tzinfo=UTC),
    )

    rendered = cli_module._format_memory_stats_text(stats)

    assert "- episodes: 2" in rendered
    assert "- memory_items: 3" in rendered
    assert "- memory_embeddings: 4" in rendered
    assert "- memory_relations: 5" in rendered
    assert "- checkpoint: 1" in rendered
    assert "- episode: 2" in rendered
    assert "- episode_created_at: 2026-03-17 12:00:00+00:00" in rendered
    assert "- memory_relation_created_at: 2026-03-17 12:03:00+00:00" in rendered


def test_format_failures_text_renders_values() -> None:
    failure = FailureListEntry(
        failure_scope="workflow",
        failure_type="runtime",
        failure_status="open",
        target_path="/tmp/workflow",
        error_code="runtime_failed",
        error_message="workflow crashed",
        attempt_id=uuid4(),
        occurred_at=datetime(2026, 3, 17, 13, 0, 0, tzinfo=UTC),
        resolved_at=datetime(2026, 3, 17, 14, 0, 0, tzinfo=UTC),
        open_failure_count=2,
        retry_count=3,
    )

    rendered = cli_module._format_failures_text((failure,))

    assert "- open: runtime" in rendered
    assert "scope=workflow" in rendered
    assert "path=/tmp/workflow" in rendered
    assert "error_code=runtime_failed" in rendered
    assert "message=workflow crashed" in rendered
    assert "occurred_at=2026-03-17 13:00:00+00:00" in rendered
    assert "resolved_at=2026-03-17 14:00:00+00:00" in rendered
    assert "retry_count=3" in rendered
    assert "open_failures=2" in rendered

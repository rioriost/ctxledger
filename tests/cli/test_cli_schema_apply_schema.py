from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import ctxledger.__init__ as cli_module

from .conftest import make_settings


def test_print_json_payload_emits_sorted_indented_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_module._print_json_payload({"b": 2, "a": 1})
    captured = capsys.readouterr()

    assert captured.err == ""
    assert captured.out == '{\n  "a": 1,\n  "b": 2\n}\n'


def test_isoformat_or_none_returns_none_or_isoformatted_text() -> None:
    assert cli_module._isoformat_or_none(None) is None
    assert cli_module._isoformat_or_none(datetime(2024, 1, 1, tzinfo=UTC)) == (
        "2024-01-01T00:00:00+00:00"
    )


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
    assert (
        "Failed to apply schema: connect exploded: postgresql://explicit/db"
        in captured.err
    )
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
        connect=lambda database_url: (
            connect_calls.append(database_url) or FakeConnection()
        )
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


def test_refresh_age_summary_graph_reports_missing_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(
                url="postgresql://from-settings/db",
                age_graph_name="",
            )
        ),
    )

    exit_code = cli_module._refresh_age_summary_graph(
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


def test_refresh_age_summary_graph_reports_explainability_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [
                {"?column?": 1},
                {"count": 2},
                {"count": 3},
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

    assert exit_code == 0
    assert captured.err == ""
    output_lines = captured.out.strip().splitlines()
    assert output_lines[0] == (
        "AGE summary graph refresh completed for 'ctxledger_summary_graph' "
        "(memory_summary nodes rebuilt=2, summarizes edges rebuilt=3)."
    )
    assert json.loads(output_lines[1]) == {
        "graph_name": "ctxledger_summary_graph",
        "memory_summary_node_count": 2,
        "summarizes_edge_count": 3,
        "remember_path_explainability": {
            "canonical_source": [
                "memory_summaries",
                "memory_summary_memberships",
            ],
            "graph_labels": [
                "memory_summary",
                "memory_item",
                "summarizes",
            ],
            "summary_first_relation_reason_frontloaded": True,
            "graph_input_scope": "canonical_summary_membership_edges",
            "graph_truth_boundary": "derived_from_canonical_relational_state",
        },
    }
    assert connect_calls == ["postgresql://explicit/db"]
    assert commit_calls == ["commit"]


def test_refresh_age_summary_graph_uses_settings_database_url_and_graph_name(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    executed_queries: list[tuple[str, object | None]] = []
    connect_calls: list[str] = []
    commit_calls: list[str] = []

    class FakeCursor:
        def __init__(self) -> None:
            self.fetchone_results: list[object] = [
                {"?column?": 1},
                {"count": 0},
                {"count": 0},
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
            if "FROM public.memory_summaries" in last_query:
                return []
            if "FROM public.memory_summary_memberships" in last_query:
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
        connect=lambda database_url: (
            connect_calls.append(database_url) or FakeConnection()
        )
    )

    monkeypatch.setitem(sys.modules, "psycopg", fake_psycopg)
    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: SimpleNamespace(
            database=SimpleNamespace(
                url="postgresql://from-settings/db",
                age_graph_name="ctxledger_settings_graph",
            )
        ),
    )

    exit_code = cli_module._refresh_age_summary_graph(
        argparse.Namespace(
            database_url=None,
            graph_name=None,
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert (
        "AGE summary graph refresh completed for 'ctxledger_settings_graph' "
        "(memory_summary nodes rebuilt=0, summarizes edges rebuilt=0)." in captured.out
    )
    assert connect_calls == ["postgresql://from-settings/db"]
    assert commit_calls == ["commit"]
    assert executed_queries[0] == ("LOAD 'age'", None)
    assert executed_queries[1] == (
        'SET search_path = ag_catalog, "$user", public',
        None,
    )
    assert executed_queries[2] == (
        """
                SELECT 1
                FROM ag_catalog.ag_graph
                WHERE name = %s
                LIMIT 1
                """,
        ("ctxledger_settings_graph",),
    )
    assert "FROM public.memory_summaries" in executed_queries[5][0]
    assert "FROM public.memory_summary_memberships" in executed_queries[6][0]

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.version import get_app_version

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
            self.fetchone_results: list[object] = [("0",), ("0",)]

        def __enter__(self) -> "FakeCursor":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def execute(self, query: str, params: object = None) -> None:
            executed_queries.append((query, params))

        def fetchone(self) -> object:
            return self.fetchone_results.pop(0)

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
    assert executed_queries[2][1] == ("ctxledger_test_graph", "ctxledger_test_graph")
    assert executed_queries[3][1] == ("ctxledger_test_graph",)
    assert executed_queries[4][1] == ("ctxledger_test_graph",)
    assert executed_queries[5][1] == ("ctxledger_test_graph",)
    assert executed_queries[6][1] == ("ctxledger_test_graph",)


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
            raise RuntimeError("bootstrap exploded")

    class FakeConnection:
        def __enter__(self) -> "FakeConnection":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def cursor(self) -> ExplodingCursor:
            return ExplodingCursor()

        def commit(self) -> None:
            raise AssertionError("commit should not be called")

    fake_psycopg = SimpleNamespace(connect=lambda database_url: FakeConnection())
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
    assert "Failed to bootstrap AGE graph: bootstrap exploded" in captured.err


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


def test_age_graph_readiness_reports_json_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class FakeHealthChecker:
        def __init__(self, config: object) -> None:
            self.config = config
            self.requested_graph_names: list[str] = []

        def age_graph_status(self, graph_name: str) -> str:
            self.requested_graph_names.append(graph_name)
            return "graph_ready"

        def age_available(self) -> bool:
            return True

    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresDatabaseHealthChecker",
        FakeHealthChecker,
    )

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert json.loads(captured.out) == {
        "age_enabled": False,
        "age_graph_name": "ctxledger_test_graph",
        "age_available": True,
        "age_graph_status": "graph_ready",
    }


def test_age_graph_readiness_reports_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    class ExplodingHealthChecker:
        def __init__(self, config: object) -> None:
            self.config = config

        def age_graph_status(self, graph_name: str) -> str:
            raise RuntimeError("readiness exploded")

        def age_available(self) -> bool:
            return True

    monkeypatch.setattr(
        "ctxledger.config.get_settings",
        lambda: make_settings(),
    )
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresDatabaseHealthChecker",
        ExplodingHealthChecker,
    )

    exit_code = cli_module._age_graph_readiness(
        argparse.Namespace(
            database_url="postgresql://explicit/db",
            graph_name="ctxledger_test_graph",
        )
    )
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert "Failed to check AGE graph readiness: readiness exploded" in captured.err

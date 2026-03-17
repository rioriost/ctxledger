from __future__ import annotations

import argparse
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

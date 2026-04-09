from __future__ import annotations

from pathlib import Path

import pytest

import ctxledger.__init__ as cli_module
from ctxledger.version import get_app_version


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

from __future__ import annotations

import argparse
import sys

import pytest

import ctxledger.__init__ as cli_module


def test_serve_returns_zero_when_run_server_result_is_not_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.server.run_server",
        lambda **kwargs: "ok",
    )

    result = cli_module._serve(argparse.Namespace(transport=None, host=None, port=None))

    assert result == 0


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

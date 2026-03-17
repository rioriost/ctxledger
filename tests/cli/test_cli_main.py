from __future__ import annotations

import argparse

import pytest

import ctxledger.__init__ as cli_module


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

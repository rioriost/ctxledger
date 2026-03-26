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

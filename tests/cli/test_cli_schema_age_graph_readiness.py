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
            "relation_type": "summarizes",
            "selection_route": "graph_summary_auxiliary",
            "explainability_scope": "readiness",
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
            "relation_type": "summarizes",
            "selection_route": "graph_summary_auxiliary",
            "explainability_scope": "readiness",
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

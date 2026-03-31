from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ctxledger.config import (
    AppSettings,
    AzureOpenAIAuthMode,
    DatabaseSettings,
    DebugSettings,
    EmbeddingExecutionMode,
    EmbeddingProvider,
    EmbeddingSettings,
    HttpSettings,
    LoggingSettings,
    LogLevel,
)


def make_settings(
    *,
    database_url: str = "postgresql://ctxledger:test@localhost:5432/ctxledger",
) -> AppSettings:
    return AppSettings(
        app_name="ctxledger",
        app_version="0.9.0",
        environment="test",
        database=DatabaseSettings(
            url=database_url,
            connect_timeout_seconds=5,
            statement_timeout_ms=None,
            schema_name="public",
            pool_min_size=1,
            pool_max_size=10,
            pool_timeout_seconds=5,
            age_enabled=False,
            age_graph_name="ctxledger_memory",
        ),
        http=HttpSettings(
            host="127.0.0.1",
            port=8080,
            path="/mcp",
        ),
        debug=DebugSettings(enabled=True),
        logging=LoggingSettings(
            level=LogLevel.INFO,
            structured=False,
        ),
        embedding=EmbeddingSettings(
            provider=EmbeddingProvider.DISABLED,
            execution_mode=EmbeddingExecutionMode.APP_GENERATED,
            model="text-embedding-3-small",
            api_key=None,
            base_url=None,
            dimensions=None,
            enabled=False,
            azure_openai_endpoint=None,
            azure_openai_embedding_deployment=None,
            azure_openai_auth_mode=AzureOpenAIAuthMode.AUTO,
            azure_openai_subscription_key=None,
            azure_openai_api_version=None,
        ),
    )


@dataclass
class FakeBuildEpisodeSummaryResult:
    feature: object
    implemented: bool
    message: str
    status: str = "ok"
    available_in_version: str | None = None
    timestamp: datetime = datetime(2024, 1, 1, tzinfo=UTC)
    summary: object | None = None
    memberships: tuple[object, ...] = ()
    summary_built: bool = False
    skipped_reason: str | None = None
    replaced_existing_summary: bool = False
    details: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.details is None:
            self.details = {}


class FakeWorkflowService:
    def __init__(self, resume_result: object) -> None:
        self.resume_result = resume_result
        self.resume_calls: list[object] = []

    def resume_workflow(self, data: object) -> object:
        self.resume_calls.append(data)
        return self.resume_result


def patch_cli_settings(
    monkeypatch: pytest.MonkeyPatch,
    settings: AppSettings,
) -> None:
    monkeypatch.setattr("ctxledger.config.get_settings", lambda: settings)


def patch_cli_postgres_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.db.postgres.PostgresConfig.from_settings",
        lambda loaded_settings: SimpleNamespace(
            settings=loaded_settings,
            database_url=loaded_settings.database.url,
        ),
    )


def patch_cli_postgres_uow_factory(
    monkeypatch: pytest.MonkeyPatch,
    factory: object,
) -> None:
    if callable(factory):
        monkeypatch.setattr(
            "ctxledger.db.postgres.build_postgres_uow_factory",
            factory,
        )
        return

    monkeypatch.setattr(
        "ctxledger.db.postgres.build_postgres_uow_factory",
        lambda config, pool=None: factory,
    )


def patch_cli_workflow_service(
    monkeypatch: pytest.MonkeyPatch,
    service: object,
) -> None:
    if callable(service):
        monkeypatch.setattr(
            "ctxledger.workflow.service.WorkflowService",
            service,
        )
        return

    monkeypatch.setattr(
        "ctxledger.workflow.service.WorkflowService",
        lambda uow_factory: service,
    )


def patch_cli_connection_pool(
    monkeypatch: pytest.MonkeyPatch,
    pool: object | None = None,
) -> object:
    if pool is None:
        pool = SimpleNamespace(close=lambda: None)

    monkeypatch.setattr(
        "ctxledger.db.postgres.build_connection_pool",
        lambda config: pool,
    )
    return pool

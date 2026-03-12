from __future__ import annotations

from typing import TYPE_CHECKING

from ..config import AppSettings
from ..db.postgres import PostgresConfig, build_postgres_uow_factory
from ..runtime.protocols import (
    DatabaseHealthChecker,
    ServerRuntime,
    WorkflowServiceFactory,
)
from ..workflow.service import WorkflowService

if TYPE_CHECKING:
    from ..server import CtxLedgerServer


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    if not settings.database.url:
        return None

    postgres_config = PostgresConfig.from_settings(settings)
    uow_factory = build_postgres_uow_factory(postgres_config)

    def _factory() -> WorkflowService:
        return WorkflowService(uow_factory)

    return _factory


def create_server(
    settings: AppSettings,
    *,
    server_class: type[CtxLedgerServer],
    create_runtime,
    build_database_health_checker,
    db_health_checker: DatabaseHealthChecker | None = None,
    runtime: ServerRuntime | None = None,
    workflow_service_factory: WorkflowServiceFactory | None = None,
) -> CtxLedgerServer:
    server = server_class(
        settings=settings,
        db_health_checker=db_health_checker,
        runtime=None,
        workflow_service_factory=(
            workflow_service_factory
            if workflow_service_factory is not None
            else build_workflow_service_factory(settings)
        ),
    )
    server.runtime = (
        runtime if runtime is not None else create_runtime(settings, server)
    )
    return server


__all__ = [
    "build_workflow_service_factory",
    "create_server",
]

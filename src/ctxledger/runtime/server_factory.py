from __future__ import annotations

from ..config import AppSettings
from ..db.postgres import PostgresConfig, build_postgres_uow_factory
from ..runtime.protocols import WorkflowServiceFactory
from ..workflow.service import WorkflowService


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


__all__ = [
    "build_workflow_service_factory",
]

from __future__ import annotations

from ..config import AppSettings
from ..db.postgres import PostgresConfig, build_postgres_uow_factory
from ..memory.service import (
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
)
from ..runtime.protocols import WorkflowServiceFactory
from ..workflow.memory_bridge import WorkflowMemoryBridge
from ..workflow.service import WorkflowService


def build_workflow_service_factory(
    settings: AppSettings,
) -> WorkflowServiceFactory | None:
    if not settings.database.url:
        return None

    postgres_config = PostgresConfig.from_settings(settings)
    uow_factory = build_postgres_uow_factory(postgres_config)

    def _factory(uow=None) -> WorkflowService:
        if uow is not None:
            workflow_memory_bridge = WorkflowMemoryBridge(
                episode_repository=uow.memory_episodes,
                memory_item_repository=uow.memory_items,
                memory_embedding_repository=uow.memory_embeddings,
            )
            return WorkflowService(
                uow_factory,
                workflow_memory_bridge=workflow_memory_bridge,
            )

        workflow_memory_bridge = WorkflowMemoryBridge(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(
                uow_factory
            ),
        )
        return WorkflowService(
            uow_factory,
            workflow_memory_bridge=workflow_memory_bridge,
        )

    return _factory


__all__ = [
    "build_workflow_service_factory",
]

from __future__ import annotations

from typing import Any

from ..config import AppSettings
from ..db.postgres import (
    PostgresConfig,
    build_connection_pool,
    build_postgres_uow_factory,
)
from ..memory.service import (
    MemoryService,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkMemorySummaryMembershipRepository,
    UnitOfWorkMemorySummaryRepository,
    UnitOfWorkWorkflowLookupRepository,
    UnitOfWorkWorkspaceLookupRepository,
)
from ..runtime.protocols import WorkflowServiceFactory
from ..workflow.memory_bridge import WorkflowMemoryBridge
from ..workflow.service import WorkflowService


def build_workflow_service_factory(
    settings: AppSettings,
    *,
    connection_pool: Any | None = None,
) -> WorkflowServiceFactory | None:
    if not settings.database.url:
        return None

    postgres_config = PostgresConfig.from_settings(settings)
    build_workflow_service_factory_connection_pool = connection_pool

    def _factory(
        uow=None,
        connection_pool: Any | None = None,
    ) -> WorkflowService:
        shared_connection_pool = (
            connection_pool
            if connection_pool is not None
            else (
                build_connection_pool(postgres_config)
                if build_workflow_service_factory_connection_pool is None
                else build_workflow_service_factory_connection_pool
            )
        )
        uow_factory = build_postgres_uow_factory(
            postgres_config,
            pool=shared_connection_pool,
        )

        explicit_summary_builder = MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_summary_repository=UnitOfWorkMemorySummaryRepository(uow_factory),
            memory_summary_membership_repository=(
                UnitOfWorkMemorySummaryMembershipRepository(uow_factory)
            ),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
            workspace_lookup=UnitOfWorkWorkspaceLookupRepository(uow_factory),
        )

        if uow is not None:
            workflow_memory_bridge = WorkflowMemoryBridge(
                episode_repository=uow.memory_episodes,
                memory_item_repository=uow.memory_items,
                memory_embedding_repository=uow.memory_embeddings,
                summary_builder=explicit_summary_builder,
            )
            return WorkflowService(
                uow_factory,
                workflow_memory_bridge=workflow_memory_bridge,
            )

        workflow_memory_bridge = WorkflowMemoryBridge(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            memory_item_repository=UnitOfWorkMemoryItemRepository(uow_factory),
            memory_embedding_repository=UnitOfWorkMemoryEmbeddingRepository(uow_factory),
            summary_builder=explicit_summary_builder,
        )
        return WorkflowService(
            uow_factory,
            workflow_memory_bridge=workflow_memory_bridge,
        )

    return _factory


__all__ = [
    "build_workflow_service_factory",
]

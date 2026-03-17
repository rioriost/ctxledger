from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.memory.service import (
    MemoryService,
    RememberEpisodeRequest,
    UnitOfWorkEpisodeRepository,
    UnitOfWorkMemoryEmbeddingRepository,
    UnitOfWorkMemoryItemRepository,
    UnitOfWorkWorkflowLookupRepository,
)
from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    RegisterWorkspaceInput,
    StartWorkflowInput,
    WorkflowService,
)


def test_postgres_memory_item_and_embedding_repositories_round_trip(
    postgres_pooled_uow_factory,
) -> None:
    uow_factory = postgres_pooled_uow_factory
    workflow_service = WorkflowService(uow_factory)

    workspace = workflow_service.register_workspace(
        RegisterWorkspaceInput(
            repo_url="https://example.com/org/repo-memory-items.git",
            canonical_path="/tmp/integration-repo-memory-items",
            default_branch="main",
        )
    )
    started = workflow_service.start_workflow(
        StartWorkflowInput(
            workspace_id=workspace.workspace_id,
            ticket_id="INTEG-MEMITEM-001",
        )
    )

    episode = (
        MemoryService(
            episode_repository=UnitOfWorkEpisodeRepository(uow_factory),
            workflow_lookup=UnitOfWorkWorkflowLookupRepository(uow_factory),
        )
        .remember_episode(
            RememberEpisodeRequest(
                workflow_instance_id=str(
                    started.workflow_instance.workflow_instance_id
                ),
                summary="Episode backing semantic memory items",
                attempt_id=str(started.attempt.attempt_id),
                metadata={"kind": "integration"},
            )
        )
        .episode
    )
    assert episode is not None

    memory_id = uuid4()
    episode_id = episode.episode_id
    older_memory_item = MemoryItemRecord(
        memory_id=memory_id,
        workspace_id=workspace.workspace_id,
        episode_id=episode_id,
        type="episode_note",
        provenance="episode",
        content="Older semantic memory item",
        metadata={"kind": "investigation"},
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    newer_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace.workspace_id,
        episode_id=episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer semantic memory item",
        metadata={"kind": "implementation"},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )

    older_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-embedding-model",
        embedding=(0.1,) * 1536,
        content_hash="older-content-hash",
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
    )
    newer_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-embedding-model-v2",
        embedding=(0.4,) * 1536,
        content_hash="newer-content-hash",
        created_at=datetime(2024, 2, 4, tzinfo=UTC),
    )

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        created_older_item = uow.memory_items.create(older_memory_item)
        created_newer_item = uow.memory_items.create(newer_memory_item)
        created_older_embedding = uow.memory_embeddings.create(older_embedding)
        created_newer_embedding = uow.memory_embeddings.create(newer_embedding)
        uow.commit()

    assert created_older_item == older_memory_item
    assert created_newer_item == newer_memory_item
    assert created_older_embedding == older_embedding
    assert created_newer_embedding == newer_embedding

    with uow_factory() as uow:
        assert uow.memory_items is not None
        assert uow.memory_embeddings is not None

        workspace_items = uow.memory_items.list_by_workspace_id(
            workspace.workspace_id,
            limit=10,
        )
        episode_items = uow.memory_items.list_by_episode_id(
            episode_id,
            limit=10,
        )
        memory_embeddings = uow.memory_embeddings.list_by_memory_id(
            memory_id,
            limit=10,
        )

    assert [item.content for item in workspace_items] == [
        "Newer semantic memory item",
        "Older semantic memory item",
    ]
    assert [item.content for item in episode_items] == [
        "Newer semantic memory item",
        "Older semantic memory item",
    ]
    assert [embedding.embedding_model for embedding in memory_embeddings] == [
        "test-embedding-model-v2",
        "test-embedding-model",
    ]
    assert memory_embeddings[0].embedding == (0.4,) * 1536
    assert memory_embeddings[1].embedding == (0.1,) * 1536
    assert started.workflow_instance.workflow_instance_id is not None

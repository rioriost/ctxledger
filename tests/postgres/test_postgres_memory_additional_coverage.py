from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from ctxledger.workflow.service import (
    MemoryEmbeddingRecord,
    MemoryItemRecord,
    PersistenceError,
)
from tests.postgres.conftest import FakeConnection


def test_postgres_memory_item_repository_count_and_datetime_helpers() -> None:
    from ctxledger.db.postgres import PostgresMemoryItemRepository

    connection = FakeConnection()
    repo = PostgresMemoryItemRepository(connection)

    connection.fetchone_results.append({"count": 7})
    assert repo.count_all() == 7

    connection.fetchall_results.append(
        [
            {"provenance": "episode", "count": 3},
            {"provenance": "workflow_complete_auto", "count": 2},
        ]
    )
    assert repo.count_by_provenance() == {
        "episode": 3,
        "workflow_complete_auto": 2,
    }

    connection.fetchone_results.append({"count": 4})
    assert repo.count_with_any_file_work_metadata() == 4

    created_at = datetime(2024, 1, 12, tzinfo=UTC)
    connection.fetchone_results.append({"value": created_at})
    assert repo.max_datetime("created_at") == created_at

    updated_at = datetime(2024, 1, 13, tzinfo=UTC)
    connection.fetchone_results.append({"value": updated_at})
    assert repo.max_datetime("updated_at") == updated_at

    provenance_created_at = datetime(2024, 1, 14, tzinfo=UTC)
    connection.fetchone_results.append({"value": provenance_created_at})
    assert repo.max_datetime_for_provenance("derived") == provenance_created_at

    connection.fetchone_results.append(None)
    assert repo.max_datetime_for_provenance("episode") is None

    with pytest.raises(
        PersistenceError,
        match="Unsupported datetime field 'finished_at' for memory_items",
    ):
        repo.max_datetime("finished_at")


def test_postgres_memory_embedding_repository_max_datetime_and_invalid_field() -> None:
    from ctxledger.db.postgres import PostgresMemoryEmbeddingRepository

    connection = FakeConnection()
    repo = PostgresMemoryEmbeddingRepository(connection)

    created_at = datetime(2024, 1, 15, tzinfo=UTC)
    connection.fetchone_results.append({"value": created_at})
    assert repo.max_datetime("created_at") == created_at

    connection.fetchone_results.append(None)
    assert repo.max_datetime("created_at") is None

    with pytest.raises(
        PersistenceError,
        match="Unsupported datetime field 'updated_at' for memory_embeddings",
    ):
        repo.max_datetime("updated_at")


def test_postgres_memory_embedding_repository_create_via_postgres_azure_ai_branches() -> (
    None
):
    from ctxledger.db.postgres import PostgresMemoryEmbeddingRepository

    connection = FakeConnection()
    repo = PostgresMemoryEmbeddingRepository(connection)

    memory_id = uuid4()
    created_at = datetime(2024, 1, 16, tzinfo=UTC)

    with pytest.raises(
        PersistenceError,
        match="Cannot create PostgreSQL azure_ai embedding for empty content",
    ):
        repo.create_via_postgres_azure_ai(
            memory_id=memory_id,
            content="   ",
            embedding_model="azure-model",
            content_hash="hash",
            created_at=created_at,
            azure_openai_deployment="embed-deploy",
            azure_openai_dimensions=None,
        )

    connection.fetchone_results.append(
        {
            "memory_embedding_id": uuid4(),
            "memory_id": memory_id,
            "embedding_model": "azure-model",
            "embedding": "[0.1,0.2,0.3]",
            "content_hash": "provided-hash",
            "created_at": created_at,
        }
    )
    stored = repo.create_via_postgres_azure_ai(
        memory_id=memory_id,
        content="Persist via postgres azure ai",
        embedding_model="azure-model",
        content_hash="provided-hash",
        created_at=created_at,
        azure_openai_deployment="embed-deploy",
        azure_openai_dimensions=None,
    )
    assert stored.memory_id == memory_id
    assert stored.embedding_model == "azure-model"
    assert stored.embedding == (0.1, 0.2, 0.3)
    assert stored.content_hash == "provided-hash"

    first_query, first_params = connection.executed[-1]
    assert "azure_openai.create_embeddings" in first_query
    assert "dimensions => %s" not in first_query
    assert first_params is not None
    assert first_params[0] != memory_id
    assert first_params[1] == memory_id
    assert first_params[2] == "azure-model"
    assert first_params[3] == "embed-deploy"
    assert first_params[4] == "Persist via postgres azure ai"
    assert first_params[5] == "provided-hash"
    assert first_params[6] == created_at

    connection.fetchone_results.append(
        {
            "memory_embedding_id": uuid4(),
            "memory_id": memory_id,
            "embedding_model": "azure-model",
            "embedding": "[0.4,0.5]",
            "content_hash": "computed-hash",
            "created_at": created_at,
        }
    )
    stored_with_dimensions = repo.create_via_postgres_azure_ai(
        memory_id=memory_id,
        content="Persist with dimensions",
        embedding_model="azure-model",
        content_hash=None,
        created_at=created_at,
        azure_openai_deployment="embed-deploy",
        azure_openai_dimensions=1536,
    )
    assert stored_with_dimensions.embedding == (0.4, 0.5)

    second_query, second_params = connection.executed[-1]
    assert "dimensions => %s" in second_query
    assert second_params is not None
    assert second_params[0] != memory_id
    assert second_params[1] == memory_id
    assert second_params[2] == "azure-model"
    assert second_params[3] == "embed-deploy"
    assert second_params[4] == "Persist with dimensions"
    assert second_params[5] == 1536
    assert isinstance(second_params[6], str)
    assert second_params[6]
    assert second_params[7] == created_at

    connection.fetchone_results.append(None)
    with pytest.raises(
        PersistenceError,
        match="Failed to create PostgreSQL azure_ai memory embedding",
    ):
        repo.create_via_postgres_azure_ai(
            memory_id=memory_id,
            content="Persist failure",
            embedding_model="azure-model",
            content_hash="hash",
            created_at=created_at,
            azure_openai_deployment="embed-deploy",
            azure_openai_dimensions=8,
        )


def test_postgres_memory_embedding_repository_find_similar_by_query_via_postgres_azure_ai() -> (
    None
):
    from ctxledger.db.postgres import PostgresMemoryEmbeddingRepository

    connection = FakeConnection()
    repo = PostgresMemoryEmbeddingRepository(connection)

    workspace_id = uuid4()
    memory_id = uuid4()
    embedding_id = uuid4()
    created_at = datetime(2024, 1, 17, tzinfo=UTC)

    assert (
        repo.find_similar_by_query_via_postgres_azure_ai(
            "   ",
            azure_openai_deployment="embed-deploy",
            azure_openai_dimensions=None,
            limit=5,
            workspace_id=None,
        )
        == ()
    )

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding_id,
                "memory_id": memory_id,
                "embedding_model": "azure-model",
                "embedding": "[0.1,0.2,0.3]",
                "content_hash": "hash-1",
                "created_at": created_at,
            }
        ]
    )
    matches = repo.find_similar_by_query_via_postgres_azure_ai(
        "projection drift",
        azure_openai_deployment="embed-deploy",
        azure_openai_dimensions=None,
        limit=3,
        workspace_id=None,
    )
    assert len(matches) == 1
    assert matches[0].memory_id == memory_id

    first_query, first_params = connection.executed[-1]
    assert "azure_openai.create_embeddings" in first_query
    assert "dimensions => %s" not in first_query
    assert "JOIN memory_items mi ON mi.memory_id = me.memory_id" not in first_query
    assert first_params == ("embed-deploy", "projection drift", 3)

    connection.fetchall_results.append(
        [
            {
                "memory_embedding_id": embedding_id,
                "memory_id": memory_id,
                "embedding_model": "azure-model",
                "embedding": "[0.4,0.5]",
                "content_hash": "hash-2",
                "created_at": created_at,
            }
        ]
    )
    scoped_matches = repo.find_similar_by_query_via_postgres_azure_ai(
        "projection drift",
        azure_openai_deployment="embed-deploy",
        azure_openai_dimensions=1536,
        limit=4,
        workspace_id=workspace_id,
    )
    assert len(scoped_matches) == 1
    assert scoped_matches[0].memory_id == memory_id

    second_query, second_params = connection.executed[-1]
    assert "dimensions => %s" in second_query
    assert "INNER JOIN memory_items AS mi" in second_query
    assert "mi.workspace_id = %s" in second_query
    assert second_params == (
        workspace_id,
        "embed-deploy",
        "projection drift",
        1536,
        4,
    )

    connection.fetchall_results.append([])
    assert (
        repo.find_similar_by_query_via_postgres_azure_ai(
            "projection drift",
            azure_openai_deployment="embed-deploy",
            azure_openai_dimensions=8,
            limit=2,
            workspace_id=None,
        )
        == ()
    )


def test_postgres_memory_summary_repositories_count_all() -> None:
    from ctxledger.db.postgres import (
        PostgresMemorySummaryMembershipRepository,
        PostgresMemorySummaryRepository,
    )

    connection = FakeConnection()
    summary_repo = PostgresMemorySummaryRepository(connection)
    membership_repo = PostgresMemorySummaryMembershipRepository(connection)

    connection.fetchone_results.append({"count": 9})
    assert summary_repo.count_all() == 9

    connection.fetchone_results.append({"count": 11})
    assert membership_repo.count_all() == 11


def test_postgres_memory_item_repository_create_and_embedding_repository_create_roundtrip_shape() -> (
    None
):
    from ctxledger.db.postgres import (
        PostgresMemoryEmbeddingRepository,
        PostgresMemoryItemRepository,
    )

    connection = FakeConnection()
    item_repo = PostgresMemoryItemRepository(connection)
    embedding_repo = PostgresMemoryEmbeddingRepository(connection)

    workspace_id = uuid4()
    episode_id = uuid4()
    memory_id = uuid4()
    created_at = datetime(2024, 1, 18, tzinfo=UTC)

    memory_item = MemoryItemRecord(
        memory_id=memory_id,
        workspace_id=workspace_id,
        episode_id=episode_id,
        type="episode_note",
        provenance="episode",
        content="Stored memory item",
        metadata={"kind": "note", "component": "memory"},
        created_at=created_at,
        updated_at=created_at,
    )

    connection.fetchone_results.append(
        {
            "memory_id": memory_id,
            "workspace_id": workspace_id,
            "episode_id": episode_id,
            "type": "episode_note",
            "provenance": "episode",
            "content": "Stored memory item",
            "metadata_json": {"kind": "note", "component": "memory"},
            "created_at": created_at,
            "updated_at": created_at,
        }
    )
    created_item = item_repo.create(memory_item)
    assert created_item == memory_item

    embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=memory_id,
        embedding_model="test-model",
        embedding=(0.1, 0.2, 0.3),
        content_hash="hash-123",
        created_at=created_at,
    )

    connection.fetchone_results.append(
        {
            "memory_embedding_id": embedding.memory_embedding_id,
            "memory_id": embedding.memory_id,
            "embedding_model": embedding.embedding_model,
            "embedding": "[0.1,0.2,0.3]",
            "content_hash": embedding.content_hash,
            "created_at": embedding.created_at,
        }
    )
    created_embedding = embedding_repo.create(embedding)
    assert created_embedding.memory_id == memory_id
    assert created_embedding.embedding == (0.1, 0.2, 0.3)
    assert created_embedding.embedding_model == "test-model"

from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.config import (
    EmbeddingProvider,
    EmbeddingSettings,
)
from ctxledger.memory.embeddings import (
    DisabledEmbeddingGenerator,
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
    ExternalAPIEmbeddingGenerator,
    LocalStubEmbeddingGenerator,
    build_embedding_generator,
    compute_content_hash,
)
from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
    SearchMemoryResponse,
    SearchResultRecord,
    StubResponse,
)
from ctxledger.memory.types import MemoryRelationRecord
from ctxledger.runtime.introspection import RuntimeIntrospection
from ctxledger.runtime.serializers import (
    serialize_runtime_introspection,
    serialize_runtime_introspection_collection,
    serialize_search_memory_response,
    serialize_stub_response,
)
from ctxledger.workflow.service import (
    VerifyReport,
    VerifyStatus,
    WorkflowAttempt,
    WorkflowAttemptStatus,
    WorkflowCheckpoint,
    WorkflowInstance,
    WorkflowInstanceStatus,
)


def test_in_memory_memory_embedding_repository_find_similar_orders_by_similarity() -> None:
    repository = InMemoryMemoryEmbeddingRepository()
    first_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="first-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    second_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.5, 0.5, 0.0),
        content_hash="second-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    third_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0, 0.0),
        content_hash="third-hash",
        created_at=datetime(2024, 1, 3, tzinfo=UTC),
    )

    repository.create(first_embedding)
    repository.create(second_embedding)
    repository.create(third_embedding)

    matches = repository.find_similar((1.0, 0.0, 0.0), limit=2)

    assert matches == (first_embedding, second_embedding)


def test_in_memory_memory_embedding_repository_find_similar_ignores_dimension_mismatch() -> None:
    repository = InMemoryMemoryEmbeddingRepository()
    matching_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(0.0, 1.0),
        content_hash="matching-hash",
        created_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    mismatched_embedding = MemoryEmbeddingRecord(
        memory_embedding_id=uuid4(),
        memory_id=uuid4(),
        embedding_model="local-stub-v1",
        embedding=(1.0, 0.0, 0.0),
        content_hash="mismatched-hash",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    repository.create(matching_embedding)
    repository.create(mismatched_embedding)

    matches = repository.find_similar((0.0, 1.0), limit=5)

    assert matches == (matching_embedding,)


def test_in_memory_memory_embedding_repository_find_similar_returns_empty_for_empty_query() -> None:
    repository = InMemoryMemoryEmbeddingRepository()
    repository.create(
        MemoryEmbeddingRecord(
            memory_embedding_id=uuid4(),
            memory_id=uuid4(),
            embedding_model="local-stub-v1",
            embedding=(1.0, 0.0),
            content_hash="hash",
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )

    matches = repository.find_similar((), limit=5)

    assert matches == ()


def test_compute_content_hash_uses_text_and_metadata() -> None:
    first = compute_content_hash("same text", {"kind": "episode"})
    second = compute_content_hash("same text", {"kind": "episode"})
    different_text = compute_content_hash("other text", {"kind": "episode"})
    different_metadata = compute_content_hash("same text", {"kind": "checkpoint"})

    assert first == second
    assert first != different_text
    assert first != different_metadata


def test_in_memory_workflow_lookup_repository_workspace_id_by_workflow_id() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()

    repository = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-REPO-1",
            }
        }
    )

    assert repository.workspace_id_by_workflow_id(workflow_id) == workspace_id
    assert repository.workspace_id_by_workflow_id(uuid4()) is None


def test_in_memory_workflow_lookup_repository_workspace_id_by_workflow_id_without_workspace() -> (
    None
):
    workflow_id = uuid4()
    repository = InMemoryWorkflowLookupRepository(
        workflows_by_id={workflow_id: {"ticket_id": "TICKET-REPO-2"}}
    )

    assert repository.workspace_id_by_workflow_id(workflow_id) is None


def test_in_memory_memory_item_repository_get_by_memory_id_returns_none_for_unknown_id() -> None:
    repository = InMemoryMemoryItemRepository()

    assert repository.get_by_memory_id(uuid4()) is None


def test_in_memory_memory_item_repository_lists_items_by_memory_ids_in_request_order() -> None:
    repository = InMemoryMemoryItemRepository()
    workspace_id = uuid4()
    missing_memory_id = uuid4()

    first_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First root item",
        metadata={"kind": "first"},
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    second_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="Second episode item",
        metadata={"kind": "second"},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )

    repository.create(first_item)
    repository.create(second_item)

    assert repository.list_by_memory_ids(
        (
            second_item.memory_id,
            missing_memory_id,
            first_item.memory_id,
        ),
        limit=5,
    ) == (
        second_item,
        first_item,
    )


def test_in_memory_memory_item_repository_lists_items_by_episode_ids_in_recency_order() -> None:
    repository = InMemoryMemoryItemRepository()
    workspace_id = uuid4()
    first_episode_id = uuid4()
    second_episode_id = uuid4()
    missing_episode_id = uuid4()

    older_first_episode_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode_id,
        type="episode_note",
        provenance="episode",
        content="Older first episode item",
        metadata={"kind": "older-first"},
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    newer_second_episode_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer second episode item",
        metadata={"kind": "newer-second"},
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
        updated_at=datetime(2024, 2, 3, tzinfo=UTC),
    )
    newer_first_episode_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer first episode item",
        metadata={"kind": "newer-first"},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root item",
        metadata={"kind": "root"},
        created_at=datetime(2024, 2, 4, tzinfo=UTC),
        updated_at=datetime(2024, 2, 4, tzinfo=UTC),
    )

    repository.create(older_first_episode_item)
    repository.create(newer_second_episode_item)
    repository.create(newer_first_episode_item)
    repository.create(workspace_root_item)

    assert repository.list_by_episode_ids(
        (
            first_episode_id,
            missing_episode_id,
            second_episode_id,
        )
    ) == (
        newer_second_episode_item,
        newer_first_episode_item,
        older_first_episode_item,
    )


def test_in_memory_memory_item_repository_lists_items_by_episode_ids_for_empty_input() -> None:
    repository = InMemoryMemoryItemRepository()

    assert repository.list_by_episode_ids(()) == ()


def test_in_memory_memory_relation_repository_lists_source_and_target_matches_in_recency_order() -> (
    None
):
    repository = MemoryService()._memory_relation_repository
    source_memory_id = uuid4()
    target_memory_id = uuid4()
    other_source_memory_id = uuid4()
    other_target_memory_id = uuid4()

    older_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=other_target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    newer_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    target_match_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
    )

    repository.create(older_relation)
    repository.create(newer_relation)
    repository.create(target_match_relation)

    assert repository.list_by_source_memory_id(source_memory_id, limit=5) == (
        newer_relation,
        older_relation,
    )
    assert repository.list_by_target_memory_id(target_memory_id, limit=5) == (
        target_match_relation,
        newer_relation,
    )


def test_in_memory_memory_relation_repository_lists_matches_by_source_memory_ids_in_recency_order_duplicate_case() -> (
    None
):
    repository = InMemoryMemoryRelationRepository()
    source_memory_id = uuid4()
    other_source_memory_id = uuid4()
    unrelated_source_memory_id = uuid4()
    target_memory_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    older_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=created_at.replace(hour=1),
    )
    newer_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=uuid4(),
        relation_type="supports",
        created_at=created_at.replace(hour=2),
    )
    other_source_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_source_memory_id,
        target_memory_id=uuid4(),
        relation_type="references",
        created_at=created_at.replace(hour=3),
    )
    unrelated_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=unrelated_source_memory_id,
        target_memory_id=uuid4(),
        relation_type="related_to",
        created_at=created_at.replace(hour=4),
    )

    repository.create(older_relation)
    repository.create(newer_relation)
    repository.create(other_source_relation)
    repository.create(unrelated_relation)

    assert repository.list_by_source_memory_ids(
        (
            source_memory_id,
            other_source_memory_id,
        )
    ) == (
        other_source_relation,
        newer_relation,
        older_relation,
    )

    assert repository.list_by_source_memory_ids(()) == ()


def test_in_memory_memory_relation_repository_lists_matches_by_source_memory_ids_in_recency_order() -> (
    None
):
    repository = InMemoryMemoryRelationRepository()
    source_memory_id = uuid4()
    other_source_memory_id = uuid4()
    unrelated_source_memory_id = uuid4()
    target_memory_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    older_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        created_at=created_at.replace(hour=1),
    )
    newer_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=uuid4(),
        relation_type="supports",
        created_at=created_at.replace(hour=2),
    )
    other_source_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_source_memory_id,
        target_memory_id=uuid4(),
        relation_type="references",
        created_at=created_at.replace(hour=3),
    )
    unrelated_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=unrelated_source_memory_id,
        target_memory_id=uuid4(),
        relation_type="related_to",
        created_at=created_at.replace(hour=4),
    )

    repository.create(older_relation)
    repository.create(newer_relation)
    repository.create(other_source_relation)
    repository.create(unrelated_relation)

    assert repository.list_by_source_memory_ids(
        (
            source_memory_id,
            other_source_memory_id,
        )
    ) == (
        other_source_relation,
        newer_relation,
        older_relation,
    )

    assert repository.list_by_source_memory_ids(()) == ()


def test_in_memory_memory_relation_repository_lists_distinct_support_targets_by_source_memory_ids() -> (
    None
):
    repository = InMemoryMemoryRelationRepository()
    source_memory_id = uuid4()
    other_source_memory_id = uuid4()
    unrelated_source_memory_id = uuid4()
    repeated_target_memory_id = uuid4()
    newer_target_memory_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    older_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=repeated_target_memory_id,
        relation_type="supports",
        created_at=created_at.replace(hour=1),
    )
    newer_distinct_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=newer_target_memory_id,
        relation_type="supports",
        created_at=created_at.replace(hour=2),
    )
    duplicate_target_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=other_source_memory_id,
        target_memory_id=repeated_target_memory_id,
        relation_type="supports",
        created_at=created_at.replace(hour=3),
    )
    non_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=uuid4(),
        relation_type="references",
        created_at=created_at.replace(hour=4),
    )
    unrelated_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=unrelated_source_memory_id,
        target_memory_id=uuid4(),
        relation_type="supports",
        created_at=created_at.replace(hour=5),
    )

    repository.create(older_support_relation)
    repository.create(newer_distinct_support_relation)
    repository.create(duplicate_target_support_relation)
    repository.create(non_support_relation)
    repository.create(unrelated_support_relation)

    assert repository.list_distinct_support_target_memory_ids_by_source_memory_ids(
        (
            source_memory_id,
            other_source_memory_id,
        )
    ) == (
        newer_target_memory_id,
        repeated_target_memory_id,
    )


def test_in_memory_memory_relation_repository_lists_no_support_targets_for_empty_sources() -> None:
    repository = InMemoryMemoryRelationRepository()

    assert repository.list_distinct_support_target_memory_ids_by_source_memory_ids(()) == ()

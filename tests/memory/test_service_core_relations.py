from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
)
from ctxledger.memory.service import (
    BuildEpisodeSummaryRequest,
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
)


def test_memory_service_collect_supports_related_memory_items_returns_empty_without_lookup_support() -> (
    None
):
    service = MemoryService(
        memory_item_repository=SimpleNamespace(),
        memory_relation_repository=SimpleNamespace(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(uuid4()),
                    }
                ],
            },
        ),
        limit=3,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_returns_empty_when_limit_is_zero() -> (
    None
):
    service = MemoryService(
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_relation_repository=InMemoryMemoryRelationRepository(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(uuid4()),
                    }
                ],
            },
        ),
        limit=0,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_falls_back_to_relation_scan() -> None:
    workspace_id = uuid4()
    episode_id = uuid4()
    source_memory_id = uuid4()
    related_memory_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    target_memory_item = MemoryItemRecord(
        memory_id=related_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="related memory item",
        metadata={"kind": "related"},
        created_at=created_at,
        updated_at=created_at,
    )
    relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=related_memory_id,
        relation_type="supports",
        metadata={"kind": "supports-edge"},
        created_at=created_at,
    )

    class RelationRepositoryWithoutBulkLookup:
        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (relation,)

    class MemoryItemLookupRepository:
        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            assert memory_id == related_memory_id
            return target_memory_item

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            assert memory_ids == (related_memory_id,)
            assert limit == 2
            return (target_memory_item,)

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=RelationRepositoryWithoutBulkLookup(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(episode_id),
                "memory_items": [
                    {
                        "memory_id": str(source_memory_id),
                    }
                ],
            },
        ),
        limit=2,
        include_relation_metadata=True,
    )

    assert related_memory_items == (target_memory_item,)
    assert related_relations == (relation,)


def test_memory_service_collect_graph_summary_related_memory_items_returns_empty_when_relation_repository_is_missing() -> (
    None
):
    service = MemoryService(
        memory_item_repository=InMemoryMemoryItemRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": (),
            },
        ),
        limit=5,
    )

    assert related_memory_items == ()


def test_memory_service_collect_graph_summary_related_memory_items_returns_empty_when_graph_lookup_raises() -> (
    None
):
    class ExplodingGraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            raise RuntimeError("graph summary lookup exploded")

    source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="source memory item",
    )

    service = MemoryService(
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_relation_repository=ExplodingGraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(source_memory_item.episode_id),
                "memory_items": (source_memory_item,),
            },
        ),
        limit=5,
    )

    assert related_memory_items == ()


def test_memory_service_collect_graph_summary_related_memory_items_returns_empty_when_graph_lookup_returns_no_members() -> (
    None
):
    class EmptyGraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            return ()

    source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="source memory item",
    )

    service = MemoryService(
        memory_item_repository=InMemoryMemoryItemRepository(),
        memory_relation_repository=EmptyGraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(source_memory_item.episode_id),
                "memory_items": (source_memory_item,),
            },
        ),
        limit=5,
    )

    assert related_memory_items == ()

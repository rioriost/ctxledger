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
from ctxledger.memory.protocols import (
    MemoryRelationMemoryItemLookupRepository,
    MemoryRelationSupportsTargetLookupRepository,
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
    SearchResultRecord,
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


def test_memory_service_collect_supports_related_memory_items_skips_non_list_and_invalid_memory_ids() -> (
    None
):
    class RelationRepositoryWithoutBulkLookup:
        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == ()
            return ()

    class MemoryItemLookupRepository(MemoryRelationMemoryItemLookupRepository):
        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            raise AssertionError("get_by_memory_id should not be called")

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            raise AssertionError("list_by_memory_ids should not be called")

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=RelationRepositoryWithoutBulkLookup(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": "not-a-list",
            },
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    "not-a-dict",
                    {"memory_id": 123},
                    {"memory_id": "not-a-uuid"},
                ],
            },
        ),
        limit=2,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_prefers_bulk_support_targets_and_relation_metadata() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    target_memory_id = uuid4()
    other_relation_target_id = uuid4()
    created_at = datetime(2024, 2, 2, tzinfo=UTC)

    target_memory_item = MemoryItemRecord(
        memory_id=target_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="bulk support target",
        metadata={"kind": "bulk-related"},
        created_at=created_at,
        updated_at=created_at,
    )
    supports_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=target_memory_id,
        relation_type="supports",
        metadata={"kind": "supports-edge"},
        created_at=created_at,
    )
    non_supports_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=other_relation_target_id,
        relation_type="references",
        metadata={"kind": "non-supports-edge"},
        created_at=created_at,
    )

    class BulkLookupRelationRepository:
        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (non_supports_relation, supports_relation)

        def list_distinct_support_target_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (target_memory_id, target_memory_id)

    class MemoryItemLookupRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            assert memory_id == target_memory_id
            return target_memory_item

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            assert memory_ids == (target_memory_id,)
            assert limit == 2
            return (target_memory_item,)

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=BulkLookupRelationRepository(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
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
    assert related_relations == (supports_relation,)
    assert memory_item_repository.calls == [((target_memory_id,), 2)]


def test_memory_service_collect_supports_related_memory_items_skips_missing_bulk_target_items() -> (
    None
):
    source_memory_id = uuid4()
    target_memory_id = uuid4()

    class BulkLookupRelationRepository(MemoryRelationSupportsTargetLookupRepository):
        def list_by_source_memory_id(
            self,
            source_memory_id: UUID,
            *,
            limit: int,
        ) -> tuple[MemoryRelationRecord, ...]:
            raise AssertionError("list_by_source_memory_id should not be called")

        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return ()

        def list_distinct_support_target_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (target_memory_id,)

        def list_by_target_memory_id(
            self,
            target_memory_id: UUID,
            *,
            limit: int,
        ) -> tuple[MemoryRelationRecord, ...]:
            raise AssertionError("list_by_target_memory_id should not be called")

    class MemoryItemLookupRepository:
        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            assert memory_id == target_memory_id
            return None

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            assert memory_ids == (target_memory_id,)
            assert limit == 1
            return ()

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=BulkLookupRelationRepository(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(source_memory_id),
                    }
                ],
            },
        ),
        limit=1,
        include_relation_metadata=True,
    )

    assert related_memory_items == ()
    assert related_relations == ()


def test_memory_service_collect_supports_related_memory_items_returns_early_without_relation_metadata() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    first_target_memory_id = uuid4()
    second_target_memory_id = uuid4()
    created_at = datetime(2024, 2, 4, tzinfo=UTC)

    first_target_memory_item = MemoryItemRecord(
        memory_id=first_target_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="first related memory item",
        metadata={"kind": "first-related"},
        created_at=created_at,
        updated_at=created_at,
    )
    second_target_memory_item = MemoryItemRecord(
        memory_id=second_target_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="second related memory item",
        metadata={"kind": "second-related"},
        created_at=created_at,
        updated_at=created_at,
    )

    class BulkLookupRelationRepository(MemoryRelationSupportsTargetLookupRepository):
        def list_by_source_memory_id(
            self,
            source_memory_id: UUID,
            *,
            limit: int,
        ) -> tuple[MemoryRelationRecord, ...]:
            raise AssertionError("list_by_source_memory_id should not be called")

        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return ()

        def list_distinct_support_target_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (
                first_target_memory_id,
                second_target_memory_id,
            )

        def list_by_target_memory_id(
            self,
            target_memory_id: UUID,
            *,
            limit: int,
        ) -> tuple[MemoryRelationRecord, ...]:
            raise AssertionError("list_by_target_memory_id should not be called")

    class MemoryItemLookupRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            if memory_id == first_target_memory_id:
                return first_target_memory_item
            if memory_id == second_target_memory_id:
                return second_target_memory_item
            return None

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            assert limit == 1
            if memory_ids == (first_target_memory_id,):
                return (first_target_memory_item,)
            if memory_ids == (second_target_memory_id,):
                return (second_target_memory_item,)
            return ()

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=BulkLookupRelationRepository(),
    )

    related_memory_items = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(source_memory_id),
                    }
                ],
            },
        ),
        limit=1,
        include_relation_metadata=False,
    )

    assert related_memory_items == (first_target_memory_item,)
    assert memory_item_repository.calls == [((first_target_memory_id,), 1)]


def test_memory_service_collect_supports_related_memory_items_fallback_skips_seen_and_non_support_relations() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    first_target_memory_id = uuid4()
    duplicate_target_memory_id = first_target_memory_id
    non_support_target_memory_id = uuid4()
    created_at = datetime(2024, 2, 5, tzinfo=UTC)

    first_target_memory_item = MemoryItemRecord(
        memory_id=first_target_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="first fallback related memory item",
        metadata={"kind": "fallback-first"},
        created_at=created_at,
        updated_at=created_at,
    )

    supports_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=first_target_memory_id,
        relation_type="supports",
        metadata={"kind": "supports-edge"},
        created_at=created_at,
    )
    duplicate_supports_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=duplicate_target_memory_id,
        relation_type="supports",
        metadata={"kind": "duplicate-supports-edge"},
        created_at=created_at,
    )
    non_supports_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=source_memory_id,
        target_memory_id=non_support_target_memory_id,
        relation_type="references",
        metadata={"kind": "non-supports-edge"},
        created_at=created_at,
    )

    class RelationRepositoryWithoutBulkLookup:
        def list_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[MemoryRelationRecord, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (
                non_supports_relation,
                supports_relation,
                duplicate_supports_relation,
            )

    class MemoryItemLookupRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            assert memory_id == first_target_memory_id
            return first_target_memory_item

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            assert memory_ids == (first_target_memory_id,)
            assert limit == 3
            return (first_target_memory_item,)

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=RelationRepositoryWithoutBulkLookup(),
    )

    related_memory_items, related_relations = service._collect_supports_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": [
                    {
                        "memory_id": str(source_memory_id),
                    }
                ],
            },
        ),
        limit=3,
        include_relation_metadata=True,
    )

    assert related_memory_items == (first_target_memory_item,)
    assert related_relations == (supports_relation,)
    assert memory_item_repository.calls == [((first_target_memory_id,), 3)]


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


def test_memory_service_collect_graph_summary_related_memory_items_skips_invalid_detail_shapes() -> (
    None
):
    class EmptyGraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == ()
            return ()

    class MemoryItemLookupRepository:
        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            raise AssertionError("list_by_memory_ids should not be called")

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=EmptyGraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(uuid4()),
                "memory_items": (
                    SimpleNamespace(memory_id=None),
                    SimpleNamespace(),
                ),
            },
            {
                "episode_id": str(uuid4()),
                "memory_items": "not-an-iterable-of-items",
            },
        ),
        limit=3,
    )

    assert related_memory_items == ()


def test_memory_service_collect_graph_summary_related_memory_items_skips_duplicates_and_missing_members() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    direct_memory_id = uuid4()
    graph_member_memory_id = uuid4()
    missing_member_memory_id = uuid4()
    created_at = datetime(2024, 2, 3, tzinfo=UTC)

    source_memory_item = MemoryItemRecord(
        memory_id=source_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="source memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    direct_memory_item = MemoryItemRecord(
        memory_id=direct_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="direct memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    graph_member_memory_item = MemoryItemRecord(
        memory_id=graph_member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="graph summary member",
        created_at=created_at,
        updated_at=created_at,
    )

    class GraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id, direct_memory_id)
            return (
                direct_memory_id,
                graph_member_memory_id,
                graph_member_memory_id,
                missing_member_memory_id,
            )

    class MemoryItemLookupRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            if memory_id == graph_member_memory_id:
                return graph_member_memory_item
            if memory_id == missing_member_memory_id:
                return None
            raise AssertionError(f"unexpected memory_id: {memory_id!r}")

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            if memory_ids == (graph_member_memory_id,):
                return (graph_member_memory_item,)
            if memory_ids == (missing_member_memory_id,):
                return ()
            raise AssertionError(f"unexpected memory_ids: {memory_ids!r}")

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=GraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(source_memory_item.episode_id),
                "memory_items": (source_memory_item, direct_memory_item),
            },
        ),
        limit=5,
    )

    assert related_memory_items == (graph_member_memory_item,)
    assert memory_item_repository.calls == [
        ((graph_member_memory_id,), 5),
        ((missing_member_memory_id,), 5),
    ]


def test_memory_service_collect_graph_summary_related_memory_items_skips_duplicate_member_records() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    member_memory_id = uuid4()
    created_at = datetime(2024, 2, 7, tzinfo=UTC)

    source_memory_item = MemoryItemRecord(
        memory_id=source_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="source memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    older_member_memory_item = MemoryItemRecord(
        memory_id=member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="older duplicate graph member",
        created_at=datetime(2024, 2, 6, tzinfo=UTC),
        updated_at=datetime(2024, 2, 6, tzinfo=UTC),
    )
    newer_member_memory_item = MemoryItemRecord(
        memory_id=member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="newer duplicate graph member",
        created_at=created_at,
        updated_at=created_at,
    )

    class GraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (member_memory_id,)

    class MemoryItemLookupRepository(MemoryRelationMemoryItemLookupRepository):
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            if memory_id == member_memory_id:
                return newer_member_memory_item
            return None

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            assert memory_ids == (member_memory_id,)
            assert limit == 5
            return (newer_member_memory_item, older_member_memory_item)

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=GraphLookupRepository(),
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

    assert related_memory_items == (newer_member_memory_item,)
    assert memory_item_repository.calls == [((member_memory_id,), 5)]


def test_memory_service_collect_graph_summary_related_memory_items_returns_empty_when_limit_is_zero() -> (
    None
):
    workspace_id = uuid4()
    source_memory_id = uuid4()
    member_memory_id = uuid4()
    created_at = datetime(2024, 2, 8, tzinfo=UTC)

    source_memory_item = MemoryItemRecord(
        memory_id=source_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="source memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    member_memory_item = MemoryItemRecord(
        memory_id=member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="graph member that should be suppressed by limit zero",
        created_at=created_at,
        updated_at=created_at,
    )

    class GraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (source_memory_id,)
            return (member_memory_id,)

    class MemoryItemLookupRepository(MemoryRelationMemoryItemLookupRepository):
        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            if memory_id == member_memory_id:
                return member_memory_item
            return None

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            assert memory_ids == (member_memory_id,)
            assert limit == 0
            return ()

    service = MemoryService(
        memory_item_repository=MemoryItemLookupRepository(),
        memory_relation_repository=GraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(source_memory_item.episode_id),
                "memory_items": (source_memory_item,),
            },
        ),
        limit=0,
    )

    assert related_memory_items == ()


def test_memory_service_collect_graph_summary_related_memory_items_returns_early_at_limit() -> None:
    workspace_id = uuid4()
    first_source_memory_id = uuid4()
    second_source_memory_id = uuid4()
    first_member_memory_id = uuid4()
    second_member_memory_id = uuid4()
    created_at = datetime(2024, 2, 6, tzinfo=UTC)

    first_source_memory_item = MemoryItemRecord(
        memory_id=first_source_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="first source memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=second_source_memory_id,
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="episode_note",
        provenance="episode",
        content="second source memory item",
        created_at=created_at,
        updated_at=created_at,
    )
    first_member_memory_item = MemoryItemRecord(
        memory_id=first_member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="first graph member",
        created_at=created_at,
        updated_at=created_at,
    )
    second_member_memory_item = MemoryItemRecord(
        memory_id=second_member_memory_id,
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="second graph member",
        created_at=created_at,
        updated_at=created_at,
    )

    class GraphLookupRepository:
        def list_distinct_summary_member_memory_ids_by_source_memory_ids(
            self,
            source_memory_ids: tuple[UUID, ...],
        ) -> tuple[UUID, ...]:
            assert source_memory_ids == (
                first_source_memory_id,
                second_source_memory_id,
            )
            return (
                first_member_memory_id,
                second_member_memory_id,
            )

    class MemoryItemLookupRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[tuple[UUID, ...], int]] = []

        def get_by_memory_id(self, memory_id: UUID) -> MemoryItemRecord | None:
            if memory_id == first_member_memory_id:
                return first_member_memory_item
            if memory_id == second_member_memory_id:
                return second_member_memory_item
            return None

        def list_by_memory_ids(
            self,
            memory_ids: tuple[UUID, ...],
            *,
            limit: int,
        ) -> tuple[MemoryItemRecord, ...]:
            self.calls.append((memory_ids, limit))
            assert limit == 1
            if memory_ids == (first_member_memory_id,):
                return (first_member_memory_item,)
            if memory_ids == (second_member_memory_id,):
                return (second_member_memory_item,)
            return ()

    memory_item_repository = MemoryItemLookupRepository()
    service = MemoryService(
        memory_item_repository=memory_item_repository,
        memory_relation_repository=GraphLookupRepository(),
    )

    related_memory_items = service._collect_graph_summary_related_memory_items(
        memory_item_details=(
            {
                "episode_id": str(first_source_memory_item.episode_id),
                "memory_items": (
                    first_source_memory_item,
                    second_source_memory_item,
                ),
            },
        ),
        limit=1,
    )

    assert related_memory_items == (first_member_memory_item,)
    assert memory_item_repository.calls == [((first_member_memory_id,), 1)]

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryWorkflowLookupRepository,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
)


def test_memory_get_context_returns_supports_related_memory_items_for_episode_items() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000051")
    created_at = datetime(2024, 10, 18, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with supports-related context",
        metadata={"kind": "supports-related"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Primary episode memory item",
        metadata={"kind": "primary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Supporting workspace memory item",
        metadata={"kind": "support"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    unrelated_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Unrelated workspace memory item",
        metadata={"kind": "unrelated"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )

    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(supports_target_item)
    memory_item_repository.create(unrelated_target_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=direct_memory_item.memory_id,
            target_memory_id=supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-edge"},
            created_at=created_at.replace(hour=3),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=direct_memory_item.memory_id,
            target_memory_id=unrelated_target_item.memory_id,
            relation_type="related_to",
            metadata={"kind": "non-support-edge"},
            created_at=created_at.replace(hour=4),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with supports-related context"
    ]
    assert response.details["related_memory_items"] == [
        {
            "memory_id": str(supports_target_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Supporting workspace memory item",
            "metadata": {"kind": "support"},
            "created_at": supports_target_item.created_at.isoformat(),
            "updated_at": supports_target_item.updated_at.isoformat(),
        }
    ]
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is (
        False
    )
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == (
        "relation_supports_auxiliary"
    )
    assert response.details["related_context_returned_without_episode_matches"] is (
        False
    )
    assert response.details["flat_related_memory_items_is_compatibility_field"] is (
        True
    )
    assert (
        response.details[
            "flat_related_memory_items_matches_grouped_episode_related_items"
        ]
        is True
    )
    assert response.details["memory_context_groups"][0]["related_memory_items"] == [
        {
            "memory_id": str(supports_target_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Supporting workspace memory item",
            "metadata": {"kind": "support"},
            "created_at": supports_target_item.created_at.isoformat(),
            "updated_at": supports_target_item.updated_at.isoformat(),
        }
    ]
    assert "related_memory_items" not in response.details["memory_context_groups"][1]


def test_memory_get_context_ignores_non_supports_relations_in_related_memory_items() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000052")
    created_at = datetime(2024, 10, 19, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode without supports-related context",
        metadata={"kind": "non-supports-only"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Primary episode memory item",
        metadata={"kind": "primary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    non_support_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Non-support related workspace memory item",
        metadata={"kind": "non-support"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )

    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(non_support_target_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=direct_memory_item.memory_id,
            target_memory_id=non_support_target_item.memory_id,
            relation_type="related_to",
            metadata={"kind": "non-support-edge"},
            created_at=created_at.replace(hour=3),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-NON-SUPPORTS",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode without supports-related context"
    ]
    assert response.details["related_memory_items"] == []
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is (
        False
    )
    assert response.details["related_context_is_auxiliary"] is False
    assert response.details["related_context_relation_types"] == []
    assert response.details["related_context_selection_route"] is None
    assert response.details["related_context_returned_without_episode_matches"] is (
        False
    )
    assert response.details["flat_related_memory_items_is_compatibility_field"] is (
        False
    )
    assert (
        response.details[
            "flat_related_memory_items_matches_grouped_episode_related_items"
        ]
        is False
    )
    assert response.details["memory_context_groups"][0]["related_memory_items"] == []
    assert "related_memory_items" not in response.details["memory_context_groups"][1]

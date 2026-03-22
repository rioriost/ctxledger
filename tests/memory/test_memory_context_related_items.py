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


def test_memory_get_context_returns_supports_related_memory_items_for_episode_items() -> None:
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
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    unrelated_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="workspace_note",
        provenance="workspace",
        content="Unrelated workspace memory item",
        metadata={"kind": "unrelated"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )

    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(supports_target_item)
    memory_item_repository.create(workspace_root_item)
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
    assert response.details["inherited_context_returned_without_episode_matches"] is (False)
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 1
    assert response.details["primary_retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 1,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 1,
    }
    assert response.details["retrieval_route_presence"] == {
        "summary_first": {
            "group_present": False,
            "item_present": False,
        },
        "episode_direct": {
            "group_present": True,
            "item_present": True,
        },
        "workspace_inherited_auxiliary": {
            "group_present": True,
            "item_present": True,
        },
        "relation_supports_auxiliary": {
            "group_present": True,
            "item_present": True,
        },
    }
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 1,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 1,
            "relation": 0,
        },
        "relation_supports_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 1,
        },
    }
    assert response.details["retrieval_route_scope_item_counts"] == {
        "summary_first": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 1,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 2,
            "relation": 0,
        },
        "relation_supports_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 1,
        },
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [
            "episode",
        ],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [
            "relation",
        ],
    }
    assert response.details["related_context_returned_without_episode_matches"] is (False)
    assert response.details["flat_related_memory_items_is_compatibility_field"] is (True)
    assert (
        response.details["flat_related_memory_items_matches_grouped_episode_related_items"] is True
    )
    assert response.details["related_memory_items_by_episode_is_primary_structured_output"] is False
    assert response.details["related_memory_items_by_episode_are_compatibility_output"] is True
    assert response.details["relation_memory_context_groups_are_primary_output"] is True
    assert response.details["group_related_memory_items_are_convenience_output"] is (True)
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
    assert response.details["memory_context_groups"][0]["related_memory_item_provenance"] == [
        {
            "memory_id": str(supports_target_item.memory_id),
            "relation_type": "supports",
            "source_memory_id": str(direct_memory_item.memory_id),
            "target_memory_id": str(supports_target_item.memory_id),
            "source_group_scope": "episode",
            "target_group_scope": "workspace",
            "target_group_selection_kind": "supports_related_auxiliary",
        }
    ]
    assert response.details["memory_context_groups"][0]["related_memory_relation_edges"] == [
        {
            "memory_relation_id": str(memory_relation_repository.relations[0].memory_relation_id),
            "relation_type": "supports",
            "source_memory_id": str(direct_memory_item.memory_id),
            "target_memory_id": str(supports_target_item.memory_id),
            "metadata": {"kind": "supports-edge"},
            "created_at": memory_relation_repository.relations[0].created_at.isoformat(),
        }
    ]
    assert response.details["memory_context_groups"][1] == {
        "scope": "workspace",
        "scope_id": str(workspace_id),
        "parent_scope": None,
        "parent_scope_id": None,
        "parent_group_scope": None,
        "parent_group_id": None,
        "selection_kind": "inherited_workspace",
        "selection_route": "workspace_inherited_auxiliary",
        "memory_items": [
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
            },
            {
                "memory_id": str(workspace_root_item.memory_id),
                "workspace_id": str(workspace_id),
                "episode_id": None,
                "type": "workspace_note",
                "provenance": "workspace",
                "content": "Workspace root memory item",
                "metadata": {"kind": "workspace-root"},
                "created_at": workspace_root_item.created_at.isoformat(),
                "updated_at": workspace_root_item.updated_at.isoformat(),
            },
        ],
    }
    assert response.details["memory_context_groups"][2] == {
        "scope": "relation",
        "scope_id": "supports",
        "group_id": "relation:supports_auxiliary",
        "parent_scope": "workflow_instance",
        "parent_scope_id": str(workflow_id),
        "parent_group_scope": None,
        "parent_group_id": None,
        "selection_kind": "supports_related_auxiliary",
        "selection_route": "relation_supports_auxiliary",
        "relation_type": "supports",
        "source_episode_ids": [str(episode.episode_id)],
        "source_memory_ids": [str(direct_memory_item.memory_id)],
        "memory_items": [
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
        ],
    }


def test_memory_get_context_relation_auxiliary_stays_disabled_when_memory_items_are_off() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000055")
    created_at = datetime(2024, 10, 22, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with supports relation but memory items disabled",
        metadata={"kind": "supports-memory-items-disabled"},
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
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )

    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(supports_target_item)
    memory_item_repository.create(workspace_root_item)

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

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-MEMORY-OFF",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with supports relation but memory items disabled"
    ]
    assert response.details["memory_items"] == []
    assert response.details["related_memory_items"] == []
    assert response.details["related_memory_items_by_episode"] == {}
    assert response.details["related_context_is_auxiliary"] is False
    assert response.details["related_context_relation_types"] == []
    assert response.details["related_context_selection_route"] is None
    assert response.details["relation_supports_source_episode_count"] == 0
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_presence"] == {
        "summary_first": {
            "group_present": False,
            "item_present": False,
        },
        "episode_direct": {
            "group_present": False,
            "item_present": False,
        },
        "workspace_inherited_auxiliary": {
            "group_present": False,
            "item_present": False,
        },
        "relation_supports_auxiliary": {
            "group_present": False,
            "item_present": False,
        },
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == []


def test_memory_get_context_aggregates_supports_relation_auxiliary_group_across_multiple_sources() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000053")
    created_at = datetime(2024, 10, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode with supports source",
        metadata={"kind": "supports-source-first"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode with supports source",
        metadata={"kind": "supports-source-second"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First source memory item",
        metadata={"kind": "first-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second source memory item",
        metadata={"kind": "second-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    shared_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Shared supporting workspace memory item",
        metadata={"kind": "shared-support"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    first_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First-seen supporting workspace memory item",
        metadata={"kind": "first-seen-support"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    later_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Later-seen supporting workspace memory item",
        metadata={"kind": "later-seen-support"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )

    memory_item_repository.create(first_source_memory_item)
    memory_item_repository.create(second_source_memory_item)
    memory_item_repository.create(shared_supports_target_item)
    memory_item_repository.create(first_seen_supports_target_item)
    memory_item_repository.create(later_seen_supports_target_item)
    memory_item_repository.create(workspace_root_item)

    first_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=first_source_memory_item.memory_id,
        target_memory_id=shared_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "first-supports-edge"},
        created_at=created_at.replace(hour=5),
    )
    second_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=second_source_memory_item.memory_id,
        target_memory_id=shared_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "second-supports-edge"},
        created_at=created_at.replace(hour=6),
    )
    third_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=first_source_memory_item.memory_id,
        target_memory_id=first_seen_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "third-supports-edge"},
        created_at=created_at.replace(hour=7),
    )
    fourth_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=second_source_memory_item.memory_id,
        target_memory_id=later_seen_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "fourth-supports-edge"},
        created_at=created_at.replace(hour=8),
    )
    memory_relation_repository.create(first_support_relation)
    memory_relation_repository.create(second_support_relation)
    memory_relation_repository.create(third_support_relation)
    memory_relation_repository.create(fourth_support_relation)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-MULTI-SOURCE",
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
        "Second episode with supports source",
        "First episode with supports source",
    ]
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 2
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 2,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 4,
        "relation_supports_auxiliary": 3,
    }
    assert response.details["memory_context_groups"][3] == {
        "scope": "relation",
        "scope_id": "supports",
        "group_id": "relation:supports_auxiliary",
        "parent_scope": "workflow_instance",
        "parent_scope_id": str(workflow_id),
        "parent_group_scope": None,
        "parent_group_id": None,
        "selection_kind": "supports_related_auxiliary",
        "selection_route": "relation_supports_auxiliary",
        "relation_type": "supports",
        "source_episode_ids": sorted(
            [
                str(first_episode.episode_id),
                str(second_episode.episode_id),
            ]
        ),
        "source_memory_ids": sorted(
            [
                str(first_source_memory_item.memory_id),
                str(second_source_memory_item.memory_id),
            ]
        ),
        "memory_items": [
            {
                "memory_id": str(later_seen_supports_target_item.memory_id),
                "workspace_id": str(workspace_id),
                "episode_id": None,
                "type": "workspace_note",
                "provenance": "workspace",
                "content": "Later-seen supporting workspace memory item",
                "metadata": {"kind": "later-seen-support"},
                "created_at": later_seen_supports_target_item.created_at.isoformat(),
                "updated_at": later_seen_supports_target_item.updated_at.isoformat(),
            },
            {
                "memory_id": str(shared_supports_target_item.memory_id),
                "workspace_id": str(workspace_id),
                "episode_id": None,
                "type": "workspace_note",
                "provenance": "workspace",
                "content": "Shared supporting workspace memory item",
                "metadata": {"kind": "shared-support"},
                "created_at": shared_supports_target_item.created_at.isoformat(),
                "updated_at": shared_supports_target_item.updated_at.isoformat(),
            },
            {
                "memory_id": str(first_seen_supports_target_item.memory_id),
                "workspace_id": str(workspace_id),
                "episode_id": None,
                "type": "workspace_note",
                "provenance": "workspace",
                "content": "First-seen supporting workspace memory item",
                "metadata": {"kind": "first-seen-support"},
                "created_at": first_seen_supports_target_item.created_at.isoformat(),
                "updated_at": first_seen_supports_target_item.updated_at.isoformat(),
            },
        ],
    }


def test_memory_get_context_limit_truncates_constrained_relation_aggregation_after_distinct_first_seen_targets() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000054")
    created_at = datetime(2024, 10, 21, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode for low-limit supports aggregation",
        metadata={"kind": "low-limit-first"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode for low-limit supports aggregation",
        metadata={"kind": "low-limit-second"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First low-limit source memory item",
        metadata={"kind": "low-limit-first-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second low-limit source memory item",
        metadata={"kind": "low-limit-second-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    later_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Later-seen low-limit supporting target",
        metadata={"kind": "low-limit-later-seen"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    shared_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Shared low-limit supporting target",
        metadata={"kind": "low-limit-shared"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    first_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First-seen low-limit supporting target",
        metadata={"kind": "low-limit-first-seen"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=40),
        updated_at=created_at.replace(hour=0, minute=40),
    )

    memory_item_repository.create(first_source_memory_item)
    memory_item_repository.create(second_source_memory_item)
    memory_item_repository.create(later_seen_supports_target_item)
    memory_item_repository.create(shared_supports_target_item)
    memory_item_repository.create(first_seen_supports_target_item)
    memory_item_repository.create(workspace_root_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=later_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-first-edge"},
            created_at=created_at.replace(hour=5),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=shared_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-second-edge"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=shared_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-third-edge"},
            created_at=created_at.replace(hour=7),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=first_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-fourth-edge"},
            created_at=created_at.replace(hour=8),
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
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-LIMIT",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Second episode for low-limit supports aggregation",
        "First episode for low-limit supports aggregation",
    ]
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 2
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 2,
    }

    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 2,
    }


def test_memory_get_context_relation_auxiliary_does_not_survive_when_query_filters_out_all_episodes() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000055")
    created_at = datetime(2024, 10, 22, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before supports auxiliary can appear",
        metadata={"kind": "relation-query-filtered"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(episode)

    source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Source memory item hidden by query filtering",
        metadata={"kind": "relation-source"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Supporting target that should not survive without returned episodes",
        metadata={"kind": "relation-target"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace auxiliary item that still remains visible",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    memory_item_repository.create(source_memory_item)
    memory_item_repository.create(supports_target_item)
    memory_item_repository.create(workspace_root_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=source_memory_item.memory_id,
            target_memory_id=supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-edge"},
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
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-QUERY-FILTER-NO-MATCH",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="no surviving episode match",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert response.episodes == ()
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["all_episodes_filtered_out_by_query"] is True
    assert response.details["related_context_is_auxiliary"] is False
    assert response.details["related_context_relation_types"] == []
    assert response.details["related_context_returned_without_episode_matches"] is (False)
    assert response.details["related_memory_items"] == []
    assert response.details["related_memory_items_by_episode"] == {}
    assert response.details["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == []
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "workspace",
            "scope_id": str(workspace_id),
            "parent_scope": None,
            "parent_scope_id": None,
            "parent_group_scope": None,
            "parent_group_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(workspace_root_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Workspace auxiliary item that still remains visible",
                    "metadata": {"kind": "workspace-root"},
                    "created_at": workspace_root_item.created_at.isoformat(),
                    "updated_at": workspace_root_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(supports_target_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Supporting target that should not survive without returned episodes",
                    "metadata": {"kind": "relation-target"},
                    "created_at": supports_target_item.created_at.isoformat(),
                    "updated_at": supports_target_item.updated_at.isoformat(),
                },
            ],
        }
    ]
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": False,
            "explanation_basis": "query_filtered_out",
            "matched_summary": False,
            "matched_metadata_values": [],
        }
    ]


def test_memory_get_context_limit_truncates_constrained_relation_aggregation_after_distinct_first_seen_targets_under_query_filter() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000056")
    created_at = datetime(2024, 10, 23, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Matching episode for low-limit supports query case",
        metadata={"kind": "low-limit-query-matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Filtered episode for low-limit supports query case",
        metadata={"kind": "low-limit-query-filtered"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching low-limit query source memory item",
        metadata={"kind": "matching-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    filtered_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered low-limit query source memory item",
        metadata={"kind": "filtered-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    later_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Later-seen low-limit query supporting target",
        metadata={"kind": "low-limit-query-later-seen"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    first_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First-seen low-limit query supporting target",
        metadata={"kind": "low-limit-query-first-seen"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root item for low-limit query case",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )

    memory_item_repository.create(matching_source_memory_item)
    memory_item_repository.create(filtered_source_memory_item)
    memory_item_repository.create(later_seen_supports_target_item)
    memory_item_repository.create(first_seen_supports_target_item)
    memory_item_repository.create(workspace_root_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=matching_source_memory_item.memory_id,
            target_memory_id=later_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "matching-first-edge"},
            created_at=created_at.replace(hour=5),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=matching_source_memory_item.memory_id,
            target_memory_id=first_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "matching-second-edge"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=filtered_source_memory_item.memory_id,
            target_memory_id=workspace_root_item.memory_id,
            relation_type="supports",
            metadata={"kind": "filtered-edge"},
            created_at=created_at.replace(hour=7),
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
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-LIMIT-QUERY",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="matching episode",
            workflow_instance_id=str(workflow_id),
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Matching episode for low-limit supports query case",
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 1
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 1,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 1,
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [
            "episode",
        ],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [
            "relation",
        ],
    }
    assert [group["selection_route"] for group in response.details["memory_context_groups"]] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["memory_context_groups"][1]["memory_items"] == [
        {
            "memory_id": str(workspace_root_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Workspace root item for low-limit query case",
            "metadata": {"kind": "workspace-root"},
            "created_at": workspace_root_item.created_at.isoformat(),
            "updated_at": workspace_root_item.updated_at.isoformat(),
        }
    ]
    assert response.details["memory_context_groups"][2]["selection_route"] == (
        "relation_supports_auxiliary"
    )
    assert response.details["memory_context_groups"][2]["source_episode_ids"] == [
        str(matching_episode.episode_id)
    ]
    assert response.details["memory_context_groups"][2]["source_memory_ids"] == [
        str(matching_source_memory_item.memory_id)
    ]
    assert response.details["memory_context_groups"][2]["memory_items"] == [
        {
            "memory_id": str(first_seen_supports_target_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "First-seen low-limit query supporting target",
            "metadata": {"kind": "low-limit-query-first-seen"},
            "created_at": first_seen_supports_target_item.created_at.isoformat(),
            "updated_at": first_seen_supports_target_item.updated_at.isoformat(),
        }
    ]
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(matching_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        }
    ]


def test_memory_get_context_ignores_non_supports_relations_in_related_memory_items() -> None:
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
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    non_support_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=uuid4(),
        type="workspace_note",
        provenance="workspace",
        content="Non-support related workspace memory item",
        metadata={"kind": "non-support"},
        created_at=created_at.replace(hour=1, minute=30),
        updated_at=created_at.replace(hour=1, minute=30),
    )

    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(workspace_root_item)
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
    assert response.details["inherited_context_returned_without_episode_matches"] is (False)
    assert response.details["related_context_is_auxiliary"] is False
    assert response.details["related_context_relation_types"] == []
    assert response.details["related_context_selection_route"] is None
    assert response.details["relation_supports_source_episode_count"] == 0
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_presence"] == {
        "summary_first": {
            "group_present": False,
            "item_present": False,
        },
        "episode_direct": {
            "group_present": True,
            "item_present": True,
        },
        "workspace_inherited_auxiliary": {
            "group_present": True,
            "item_present": True,
        },
        "relation_supports_auxiliary": {
            "group_present": False,
            "item_present": False,
        },
    }
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 1,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 1,
            "relation": 0,
        },
        "relation_supports_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
    }
    assert response.details["retrieval_route_scope_item_counts"] == {
        "summary_first": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 1,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 1,
            "relation": 0,
        },
        "relation_supports_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [
            "episode",
        ],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["related_context_returned_without_episode_matches"] is (False)
    assert response.details["flat_related_memory_items_is_compatibility_field"] is (False)
    assert (
        response.details["flat_related_memory_items_matches_grouped_episode_related_items"] is False
    )
    assert response.details["related_memory_items_by_episode_is_primary_structured_output"] is False
    assert response.details["related_memory_items_by_episode_are_compatibility_output"] is False
    assert response.details["relation_memory_context_groups_are_primary_output"] is False
    assert response.details["group_related_memory_items_are_convenience_output"] is (False)
    assert response.details["memory_context_groups"][0]["related_memory_items"] == []
    assert response.details["memory_context_groups"][0]["related_memory_item_provenance"] == []
    assert response.details["memory_context_groups"][0]["related_memory_relation_edges"] == []
    assert response.details["memory_context_groups"][1] == {
        "scope": "workspace",
        "scope_id": str(workspace_id),
        "parent_scope": None,
        "parent_scope_id": None,
        "parent_group_scope": None,
        "parent_group_id": None,
        "selection_kind": "inherited_workspace",
        "selection_route": "workspace_inherited_auxiliary",
        "memory_items": [
            {
                "memory_id": str(workspace_root_item.memory_id),
                "workspace_id": str(workspace_id),
                "episode_id": None,
                "type": "workspace_note",
                "provenance": "workspace",
                "content": "Workspace root memory item",
                "metadata": {"kind": "workspace-root"},
                "created_at": workspace_root_item.created_at.isoformat(),
                "updated_at": workspace_root_item.updated_at.isoformat(),
            }
        ],
    }

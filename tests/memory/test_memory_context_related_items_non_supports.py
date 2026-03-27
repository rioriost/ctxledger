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


def test_memory_get_context_ignores_non_supports_relations_in_related_memory_items() -> None:
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 1,
        "graph_summary_auxiliary": 0,
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
        "graph_summary_auxiliary": [],
    }
    assert [group["selection_route"] for group in response.details["memory_context_groups"]] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "episode",
        "workspace",
        "relation",
    ]
    assert response.details["memory_context_groups"][1]["memory_items"] == [
        {
            "memory_id": str(workspace_root_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "provenance_kind": "other",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
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
            "provenance_kind": "other",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
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


def test_memory_get_context_ignores_non_supports_relations_in_related_memory_items_legacy_duplicate_case() -> (
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": [],
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
                "provenance_kind": "other",
                "interaction_role": None,
                "interaction_kind": None,
                "file_name": None,
                "file_path": None,
                "file_operation": None,
                "purpose": None,
                "content": "Workspace root memory item",
                "metadata": {"kind": "workspace-root"},
                "created_at": workspace_root_item.created_at.isoformat(),
                "updated_at": workspace_root_item.updated_at.isoformat(),
            }
        ],
    }

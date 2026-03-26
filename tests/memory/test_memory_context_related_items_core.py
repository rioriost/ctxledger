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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 1,
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
            "group_present": True,
            "item_present": True,
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
            "relation": 1,
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
            "workspace": 2,
            "relation": 0,
        },
        "relation_supports_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 1,
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
        "relation_supports_auxiliary": [
            "relation",
        ],
        "graph_summary_auxiliary": [],
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
            "source_memory_origin": None,
            "relation_reason": None,
            "source_memory_type": None,
            "target_memory_type": None,
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
    assert response.details["memory_context_groups"][0]["remember_path_memory_items"] == [
        {
            "memory_id": str(direct_memory_item.memory_id),
            "memory_type": "episode_note",
            "provenance": "episode",
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        }
    ]
    assert response.details["memory_context_groups"][0]["remember_path_memory_summary"] == {
        "memory_origin_counts": {},
        "promotion_field_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    assert response.details["memory_context_groups"][0]["remember_path_relation_explanations"] == [
        {
            "memory_relation_id": str(memory_relation_repository.relations[0].memory_relation_id),
            "relation_type": "supports",
            "relation_reason": None,
            "relation_description": None,
            "memory_origin": None,
            "source_memory_type": None,
            "target_memory_type": None,
            "source_memory_id": str(direct_memory_item.memory_id),
            "target_memory_id": str(supports_target_item.memory_id),
        }
    ]
    assert response.details["memory_context_groups"][0]["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    workspace_group = response.details["memory_context_groups"][1]
    assert workspace_group["scope"] == "workspace"
    assert workspace_group["scope_id"] == str(workspace_id)
    assert workspace_group["parent_scope"] is None
    assert workspace_group["parent_scope_id"] is None
    assert workspace_group.get("parent_group_scope") is None
    assert workspace_group.get("parent_group_id") is None
    assert workspace_group["selection_kind"] == "inherited_workspace"
    assert workspace_group["selection_route"] == "workspace_inherited_auxiliary"
    assert workspace_group["memory_items"] == [
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
    ]
    assert workspace_group.get("remember_path_memory_items", []) == []
    assert workspace_group.get("remember_path_memory_summary", {}) == {}
    assert workspace_group.get("remember_path_relation_explanations", []) == []
    assert workspace_group.get("remember_path_relation_summary", {}) == {}
    relation_group = response.details["memory_context_groups"][2]
    assert relation_group["scope"] == "relation"
    assert relation_group["scope_id"] == "supports"
    assert relation_group["group_id"] == "relation:supports_auxiliary"
    assert relation_group["parent_scope"] == "workflow_instance"
    assert relation_group["parent_scope_id"] == str(workflow_id)
    assert relation_group.get("parent_group_scope") is None
    assert relation_group.get("parent_group_id") is None
    assert relation_group["selection_kind"] == "supports_related_auxiliary"
    assert relation_group["selection_route"] == "relation_supports_auxiliary"
    assert relation_group["relation_type"] == "supports"
    assert relation_group["source_episode_ids"] == [str(episode.episode_id)]
    assert relation_group["source_memory_ids"] == [str(direct_memory_item.memory_id)]
    assert relation_group["memory_items"] == [
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
    assert relation_group["remember_path_relation_explanations"] == [
        {
            "memory_relation_id": str(memory_relation_repository.relations[0].memory_relation_id),
            "relation_type": "supports",
            "relation_reason": None,
            "relation_description": None,
            "memory_origin": None,
            "source_memory_type": None,
            "target_memory_type": None,
            "source_memory_id": str(direct_memory_item.memory_id),
            "target_memory_id": str(supports_target_item.memory_id),
        }
    ]
    assert relation_group["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
        "graph_summary_auxiliary": {
            "group_present": False,
            "item_present": False,
        },
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == []


def test_memory_get_context_relation_auxiliary_stays_disabled_when_memory_items_are_off_under_low_limit_query_shape() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000057")
    created_at = datetime(2024, 10, 24, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Matching episode with supports relation but memory items disabled",
        metadata={"kind": "supports-memory-items-disabled-matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Filtered episode with supports relation but memory items disabled",
        metadata={"kind": "supports-memory-items-disabled-filtered"},
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
        content="Matching source memory item hidden because memory items are disabled",
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
        content="Filtered source memory item hidden because memory items are disabled",
        metadata={"kind": "filtered-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    first_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First supporting workspace item that should remain hidden",
        metadata={"kind": "first-support"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    second_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Second supporting workspace item that should remain hidden",
        metadata={"kind": "second-support"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )

    memory_item_repository.create(matching_source_memory_item)
    memory_item_repository.create(filtered_source_memory_item)
    memory_item_repository.create(first_supports_target_item)
    memory_item_repository.create(second_supports_target_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=matching_source_memory_item.memory_id,
            target_memory_id=first_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "matching-first-edge"},
            created_at=created_at.replace(hour=5),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=matching_source_memory_item.memory_id,
            target_memory_id=second_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "matching-second-edge"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=filtered_source_memory_item.memory_id,
            target_memory_id=first_supports_target_item.memory_id,
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
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-MEMORY-OFF-LIMIT-QUERY",
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
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Matching episode with supports relation but memory items disabled"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["memory_items"] == []
    assert response.details["related_memory_items"] == []
    assert response.details["related_memory_items_by_episode"] == {}
    assert response.details["related_context_is_auxiliary"] is False
    assert response.details["related_context_relation_types"] == []
    assert response.details["related_context_selection_route"] is None
    assert response.details["relation_supports_source_episode_count"] == 0
    assert response.details["primary_retrieval_routes_present"] == []
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
        "graph_summary_auxiliary": {
            "group_present": False,
            "item_present": False,
        },
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == []
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

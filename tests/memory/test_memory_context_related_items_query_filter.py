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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
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
                    "provenance_kind": "other",
                    "interaction_role": None,
                    "interaction_kind": None,
                    "file_name": None,
                    "file_path": None,
                    "file_operation": None,
                    "purpose": None,
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
                    "provenance_kind": "other",
                    "interaction_role": None,
                    "interaction_kind": None,
                    "file_name": None,
                    "file_path": None,
                    "file_operation": None,
                    "purpose": None,
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


def test_memory_get_context_workspace_auxiliary_may_survive_query_filter_while_relation_auxiliary_does_not() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000058")
    created_at = datetime(2024, 10, 25, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before workspace-relation interaction survives",
        metadata={"kind": "workspace-relation-no-match"},
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
        content="Episode-side source memory hidden by query filtering",
        metadata={"kind": "episode-source"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Supports target that should not remain visible without returned episodes",
        metadata={"kind": "supports-target"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace auxiliary item that should remain visible",
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
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-RELATION-NO-MATCH",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="workspace auxiliary survives only",
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
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is True
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
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
                    "provenance_kind": "other",
                    "interaction_role": None,
                    "interaction_kind": None,
                    "file_name": None,
                    "file_path": None,
                    "file_operation": None,
                    "purpose": None,
                    "content": "Workspace auxiliary item that should remain visible",
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
                    "provenance_kind": "other",
                    "interaction_role": None,
                    "interaction_kind": None,
                    "file_name": None,
                    "file_path": None,
                    "file_operation": None,
                    "purpose": None,
                    "content": "Supports target that should not remain visible without returned episodes",
                    "metadata": {"kind": "supports-target"},
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

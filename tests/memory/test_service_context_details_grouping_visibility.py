from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryItemRecord,
    MemoryService,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
)


def test_memory_get_context_workspace_only_query_filter_may_leave_only_workspace_auxiliary_visible() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000056"
    created_at = datetime(2024, 10, 29, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First workspace-only episode filtered out before auxiliary-only shaping",
        metadata={"kind": "workspace-only-no-match-first"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second workspace-only episode filtered out before auxiliary-only shaping",
        metadata={"kind": "workspace-only-no-match-second"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First workspace-only direct memory item hidden after query filtering",
        metadata={"kind": "first-direct-memory"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second workspace-only direct memory item hidden after query filtering",
        metadata={"kind": "second-direct-memory"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace-only inherited item survives no-match shaping",
        metadata={"kind": "workspace-only-inherited"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    memory_item_repository.create(first_direct_memory_item)
    memory_item_repository.create(second_direct_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-NO-MATCH-AUXILIARY",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-NO-MATCH-AUXILIARY-OTHER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="workspace-only inherited token",
            workspace_id=workspace_id,
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert response.episodes == ()
    assert response.details["lookup_scope"] == "workspace"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["all_episodes_filtered_out_by_query"] is True
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
    assert response.details["retrieval_routes_present"] == []
    assert response.details["primary_retrieval_routes_present"] == []
    assert response.details["auxiliary_retrieval_routes_present"] == []
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
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["hierarchy_applied"] is False
    assert response.details["inherited_context_is_auxiliary"] is False
    assert response.details["inherited_context_returned_without_episode_matches"] is False
    assert (
        response.details["inherited_context_returned_as_auxiliary_without_episode_matches"] is False
    )
    assert response.details["memory_context_groups"] == []
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(first_workflow_id),
            "matched": False,
            "explanation_basis": "query_filtered_out",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(second_episode.episode_id),
            "workflow_instance_id": str(second_workflow_id),
            "matched": False,
            "explanation_basis": "query_filtered_out",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]


def test_memory_get_context_ticket_only_query_filter_may_leave_no_visible_grouped_routes() -> None:
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    first_workspace_id = "00000000-0000-0000-0000-000000000057"
    second_workspace_id = "00000000-0000-0000-0000-000000000058"
    created_at = datetime(2024, 10, 30, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First ticket-only episode filtered out before no-match shaping",
        metadata={"kind": "ticket-only-no-match-first"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second ticket-only episode filtered out before no-match shaping",
        metadata={"kind": "ticket-only-no-match-second"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(first_workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First ticket-only direct memory item hidden after query filtering",
        metadata={"kind": "first-direct-memory"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(second_workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second ticket-only direct memory item hidden after query filtering",
        metadata={"kind": "second-direct-memory"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_item_repository.create(first_direct_memory_item)
    memory_item_repository.create(second_direct_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": first_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-NO-MATCH-SHAPING",
                },
                second_workflow_id: {
                    "workspace_id": second_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-NO-MATCH-SHAPING",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="ticket-only absent token",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-NO-MATCH-SHAPING",
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert response.episodes == ()
    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["all_episodes_filtered_out_by_query"] is True
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
    assert response.details["retrieval_routes_present"] == []
    assert response.details["primary_retrieval_routes_present"] == []
    assert response.details["auxiliary_retrieval_routes_present"] == []
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
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["hierarchy_applied"] is False
    assert response.details["inherited_context_is_auxiliary"] is False
    assert response.details["inherited_context_returned_without_episode_matches"] is False
    assert (
        response.details["inherited_context_returned_as_auxiliary_without_episode_matches"] is False
    )
    assert response.details["memory_context_groups"] == []
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(first_workflow_id),
            "matched": False,
            "explanation_basis": "query_filtered_out",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(second_episode.episode_id),
            "workflow_instance_id": str(second_workflow_id),
            "matched": False,
            "explanation_basis": "query_filtered_out",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]


def test_memory_get_context_group_selection_metadata_is_explicit_and_consistent() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000039"
    created_at = datetime(2024, 10, 13, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with explicit selection metadata",
        metadata={"kind": "selection-metadata"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct item for selection metadata",
        metadata={"kind": "direct"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Inherited item for selection metadata",
        metadata={"kind": "inherited"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SELECTION-METADATA",
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

    assert response.details["hierarchy_applied"] is True
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
    assert response.details["memory_context_groups"] == [
        {
            "scope": "episode",
            "scope_id": str(episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": None,
            "parent_group_id": None,
            "selection_kind": "direct_episode",
            "selection_route": "episode_direct",
            "selected_via_summary_first": False,
            "memory_items": [
                {
                    "memory_id": str(direct_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Direct item for selection metadata",
                    "metadata": {"kind": "direct"},
                    "created_at": direct_memory_item.created_at.isoformat(),
                    "updated_at": direct_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "parent_group_scope": None,
            "parent_group_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited item for selection metadata",
                    "metadata": {"kind": "inherited"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
    ]


def test_memory_get_context_supports_relation_grouping_metadata_for_episode_items() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000041"
    created_at = datetime(2024, 10, 16, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode prepared for supports relation grouping",
        metadata={"kind": "supports-group"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    primary_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Primary memory item for supports grouping",
        metadata={"kind": "primary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    supporting_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Supporting memory item for relation grouping",
        metadata={"kind": "supporting"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(primary_memory_item)
    memory_item_repository.create(supporting_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUPPORTS-GROUP",
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

    assert response.details["memory_context_groups"][0]["scope"] == "episode"
    assert response.details["memory_context_groups"][0]["selection_kind"] == ("direct_episode")
    assert response.details["memory_context_groups"][1]["scope"] == "workspace"
    assert response.details["memory_context_groups"][1]["selection_kind"] == ("inherited_workspace")


def test_memory_get_context_supports_relation_grouping_metadata_survives_episode_query_filter() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000042"
    created_at = datetime(2024, 10, 17, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode matches supports relation query",
        metadata={"kind": "supports-query"},
        created_at=created_at,
        updated_at=created_at,
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode that should be filtered out",
        metadata={"kind": "other"},
        created_at=created_at.replace(day=16),
        updated_at=created_at.replace(day=16),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct memory item for matching episode",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Inherited supports relation helper",
        metadata={"kind": "supporting"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUPPORTS-FILTERED",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="matches supports relation query",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode matches supports relation query"
    ]
    assert response.details["memory_context_groups"] == [
        {
            "scope": "episode",
            "scope_id": str(matching_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": None,
            "parent_group_id": None,
            "selection_kind": "direct_episode",
            "selection_route": "episode_direct",
            "selected_via_summary_first": False,
            "memory_items": [
                {
                    "memory_id": str(matching_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(matching_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Direct memory item for matching episode",
                    "metadata": {"kind": "matching"},
                    "created_at": matching_memory_item.created_at.isoformat(),
                    "updated_at": matching_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "parent_group_scope": None,
            "parent_group_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited supports relation helper",
                    "metadata": {"kind": "supporting"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
    ]


def test_memory_get_context_supports_relation_grouping_metadata_for_episode_items_relation_aware_legacy() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000040"
    created_at = datetime(2024, 10, 14, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode prepared for future relation-aware grouping",
        metadata={"kind": "relation-aware-next"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    primary_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Primary memory item for supports grouping",
        metadata={"kind": "primary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    supporting_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Supporting memory item for relation grouping",
        metadata={"kind": "supporting"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(primary_memory_item)
    memory_item_repository.create(supporting_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUPPORTS-GROUP",
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

    assert response.details["memory_context_groups"][0]["scope"] == "episode"
    assert response.details["memory_context_groups"][0]["selection_kind"] == ("direct_episode")
    assert response.details["memory_context_groups"][1]["scope"] == "workspace"
    assert response.details["memory_context_groups"][1]["selection_kind"] == ("inherited_workspace")

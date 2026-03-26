from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryWorkflowLookupRepository,
    MemoryItemRecord,
    MemoryService,
)


def test_memory_get_context_summary_group_parent_scope_id_is_null_for_multi_workflow_resolution() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000043"
    created_at = datetime(2024, 10, 18, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First workflow summary group case",
        metadata={"kind": "multi-workflow-first"},
        created_at=created_at.replace(day=18),
        updated_at=created_at.replace(day=18),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second workflow summary group case",
        metadata={"kind": "multi-workflow-second"},
        created_at=created_at.replace(day=17),
        updated_at=created_at.replace(day=17),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First workflow memory item",
        metadata={"kind": "first"},
        created_at=created_at.replace(day=18, hour=2),
        updated_at=created_at.replace(day=18, hour=2),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second workflow memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=17, hour=2),
        updated_at=created_at.replace(day=17, hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            ticket_id="TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "workspace_and_ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 1,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
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
            "summary": 2,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "episode_direct": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
            "relation": 0,
        },
        "workspace_inherited_auxiliary": {
            "summary": 0,
            "episode": 0,
            "workspace": 0,
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
        "summary_first": [
            "summary",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": None,
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [
                str(first_episode.episode_id),
                str(second_episode.episode_id),
            ],
            "child_episode_count": 2,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(first_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
                {
                    "episode_id": str(second_episode.episode_id),
                    "workflow_instance_id": str(second_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
            ],
        }
    ]


def test_memory_get_context_multi_workflow_summary_first_with_memory_items_keeps_child_set_and_episode_parents() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000043"
    created_at = datetime(2024, 10, 18, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First workflow summary-first memory-items case",
        metadata={"kind": "multi-workflow-memory-first"},
        created_at=created_at.replace(day=18),
        updated_at=created_at.replace(day=18),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second workflow summary-first memory-items case",
        metadata={"kind": "multi-workflow-memory-second"},
        created_at=created_at.replace(day=17),
        updated_at=created_at.replace(day=17),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First workflow memory item",
        metadata={"kind": "first"},
        created_at=created_at.replace(day=18, hour=2),
        updated_at=created_at.replace(day=18, hour=2),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second workflow memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=17, hour=2),
        updated_at=created_at.replace(day=17, hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            ticket_id="TICKET-CONTEXT-MULTI-WORKFLOW-SUMMARY-GROUP",
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "workspace_and_ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "First workflow summary-first memory-items case",
        "Second workflow summary-first memory-items case",
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 2
    assert response.details["summary_first_child_episode_ids"] == [
        str(first_episode.episode_id),
        str(second_episode.episode_id),
    ]
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": None,
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [
                str(first_episode.episode_id),
                str(second_episode.episode_id),
            ],
            "child_episode_count": 2,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(first_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
                {
                    "episode_id": str(second_episode.episode_id),
                    "workflow_instance_id": str(second_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(first_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(first_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(first_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First workflow memory item",
                    "metadata": {"kind": "first"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "episode",
            "scope_id": str(second_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(second_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(second_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Second workflow memory item",
                    "metadata": {"kind": "second"},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]


def test_memory_get_context_ticket_only_multi_workflow_summary_first_with_memory_items_keeps_child_set_and_episode_parents() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000047"
    created_at = datetime(2024, 10, 22, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First ticket-only workflow summary-first memory-items case",
        metadata={"kind": "ticket-only-multi-workflow-first"},
        created_at=created_at.replace(day=22),
        updated_at=created_at.replace(day=22),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second ticket-only workflow summary-first memory-items case",
        metadata={"kind": "ticket-only-multi-workflow-second"},
        created_at=created_at.replace(day=21),
        updated_at=created_at.replace(day=21),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First ticket-only workflow memory item",
        metadata={"kind": "first"},
        created_at=created_at.replace(day=22, hour=2),
        updated_at=created_at.replace(day=22, hour=2),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second ticket-only workflow memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=21, hour=2),
        updated_at=created_at.replace(day=21, hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW",
                },
                second_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000099",
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW",
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "First ticket-only workflow summary-first memory-items case",
        "Second ticket-only workflow summary-first memory-items case",
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 2
    assert response.details["summary_first_child_episode_ids"] == [
        str(first_episode.episode_id),
        str(second_episode.episode_id),
    ]
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": None,
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [
                str(first_episode.episode_id),
                str(second_episode.episode_id),
            ],
            "child_episode_count": 2,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(first_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
                {
                    "episode_id": str(second_episode.episode_id),
                    "workflow_instance_id": str(second_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(first_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(first_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(first_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First ticket-only workflow memory item",
                    "metadata": {"kind": "first"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "episode",
            "scope_id": str(second_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(second_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(second_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Second ticket-only workflow memory item",
                    "metadata": {"kind": "second"},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]


def test_memory_get_context_ticket_only_multi_workflow_query_filter_summary_first_uses_surviving_child_set() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000050"
    created_at = datetime(2024, 10, 25, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Ticket-only multi-workflow summary matches surviving query",
        metadata={"kind": "ticket-only-multi-workflow-matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Ticket-only multi-workflow summary filtered out",
        metadata={"kind": "ticket-only-multi-workflow-filtered"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching ticket-only multi-workflow memory item",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered ticket-only multi-workflow memory item",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-QUERY-FILTER",
                },
                second_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000099",
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-QUERY-FILTER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-QUERY-FILTER",
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert [episode.summary for episode in response.episodes] == [
        "Ticket-only multi-workflow summary matches surviving query"
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is True
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": None,
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(matching_episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(matching_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(matching_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(first_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(matching_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(matching_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Matching ticket-only multi-workflow memory item",
                    "metadata": {"kind": "matching"},
                    "created_at": matching_memory_item.created_at.isoformat(),
                    "updated_at": matching_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(matching_episode.episode_id),
            "workflow_instance_id": str(first_workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        }
    ]


def test_memory_get_context_workspace_only_multi_workflow_summary_first_with_workspace_auxiliary_keeps_primary_and_auxiliary_surfaces_aligned() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000048"
    created_at = datetime(2024, 10, 23, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First workspace-only multi-workflow summary-first case",
        metadata={"kind": "workspace-only-multi-workflow-first"},
        created_at=created_at.replace(day=23),
        updated_at=created_at.replace(day=23),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second workspace-only multi-workflow summary-first case",
        metadata={"kind": "workspace-only-multi-workflow-second"},
        created_at=created_at.replace(day=22),
        updated_at=created_at.replace(day=22),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First workspace-only workflow memory item",
        metadata={"kind": "first"},
        created_at=created_at.replace(day=23, hour=2),
        updated_at=created_at.replace(day=23, hour=2),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second workspace-only workflow memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=22, hour=2),
        updated_at=created_at.replace(day=22, hour=2),
    )
    newer_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Newer workspace-only inherited item",
        metadata={"kind": "workspace-newer"},
        created_at=created_at.replace(day=23, hour=1),
        updated_at=created_at.replace(day=23, hour=1),
    )
    older_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Older workspace-only inherited item",
        metadata={"kind": "workspace-older"},
        created_at=created_at.replace(day=22, hour=1),
        updated_at=created_at.replace(day=22, hour=1),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)
    memory_item_repository.create(newer_inherited_workspace_item)
    memory_item_repository.create(older_inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-MULTI-WORKFLOW",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-MULTI-WORKFLOW",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "workspace"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "First workspace-only multi-workflow summary-first case",
        "Second workspace-only multi-workflow summary-first case",
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 2
    assert response.details["summary_first_child_episode_ids"] == [
        str(first_episode.episode_id),
        str(second_episode.episode_id),
    ]
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["inherited_memory_items"] == []
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": None,
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [
                str(first_episode.episode_id),
                str(second_episode.episode_id),
            ],
            "child_episode_count": 2,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(first_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
                {
                    "episode_id": str(second_episode.episode_id),
                    "workflow_instance_id": str(second_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                },
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(first_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(first_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(first_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First workspace-only workflow memory item",
                    "metadata": {"kind": "first"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "episode",
            "scope_id": str(second_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(second_workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(second_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Second workspace-only workflow memory item",
                    "metadata": {"kind": "second"},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]

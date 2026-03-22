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


def test_memory_get_context_returns_episode_oriented_results() -> None:
    workflow_id = uuid4()
    other_workflow_id = uuid4()
    attempt_id = uuid4()
    now = datetime(2024, 1, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    older_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Older episode",
        attempt_id=attempt_id,
        metadata={"kind": "design"},
        created_at=now,
        updated_at=now,
    )
    newer_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Newer episode",
        attempt_id=None,
        metadata={"kind": "fix"},
        created_at=datetime(2024, 1, 11, tzinfo=UTC),
        updated_at=datetime(2024, 1, 11, tzinfo=UTC),
    )
    unrelated_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=other_workflow_id,
        summary="Unrelated episode",
        attempt_id=None,
        metadata={"kind": "other"},
        created_at=datetime(2024, 1, 12, tzinfo=UTC),
        updated_at=datetime(2024, 1, 12, tzinfo=UTC),
    )

    episode_repository.create(older_episode)
    episode_repository.create(newer_episode)
    episode_repository.create(unrelated_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id, other_workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Newer episode",
        "Older episode",
    ]
    assert response.details["query"] is None
    assert response.details["normalized_query"] is None
    assert response.details["query_tokens"] == []
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 5
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is False
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 2
    assert response.details["episodes_returned"] == 2
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(newer_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(older_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]
    assert response.details["workflow_candidate_ordering"] == {
        "ordering_basis": "workflow_instance_id_priority",
        "workflow_instance_id_priority_applied": True,
        "signal_priority": [
            "workflow_is_terminal",
            "latest_attempt_is_terminal",
            "has_latest_attempt",
            "has_latest_checkpoint",
            "latest_checkpoint_created_at",
            "latest_verify_report_created_at",
            "latest_episode_created_at",
            "latest_attempt_started_at",
            "workflow_updated_at",
            "resolver_order",
        ],
        "workspace_candidate_ids": [],
        "ticket_candidate_ids": [],
        "resolver_candidate_ids": [],
        "final_candidate_ids": [str(workflow_id)],
        "candidate_signals": {
            str(workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": False,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": False,
                "latest_checkpoint_created_at": None,
                "latest_verify_report_created_at": None,
                "latest_episode_created_at": datetime(2024, 1, 11, tzinfo=UTC).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_respects_limit_and_include_episodes_flag() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    for index in range(3):
        episode_repository.create(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_id,
                summary=f"Episode {index}",
                metadata={"index": index},
                created_at=created_at.replace(day=index + 1),
                updated_at=created_at.replace(day=index + 1),
            )
        )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    limited_response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=True,
        )
    )
    no_episode_response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=False,
        )
    )

    assert [episode.summary for episode in limited_response.episodes] == [
        "Episode 2",
        "Episode 1",
    ]
    assert limited_response.details["lookup_scope"] == "workflow_instance"
    assert limited_response.details["resolved_workflow_count"] == 1
    assert limited_response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert limited_response.details["query_filter_applied"] is False
    assert limited_response.details["episodes_before_query_filter"] == 2
    assert limited_response.details["matched_episode_count"] == 2
    assert limited_response.details["episodes_returned"] == 2
    assert limited_response.details["episode_explanations"] == [
        {
            "episode_id": str(
                next(
                    episode.episode_id
                    for episode in limited_response.episodes
                    if episode.summary == "Episode 2"
                )
            ),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(
                next(
                    episode.episode_id
                    for episode in limited_response.episodes
                    if episode.summary == "Episode 1"
                )
            ),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]

    assert no_episode_response.episodes == ()
    assert no_episode_response.details["lookup_scope"] == "workflow_instance"
    assert no_episode_response.details["resolved_workflow_count"] == 1
    assert no_episode_response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert no_episode_response.details["query_tokens"] == []
    assert no_episode_response.details["query_filter_applied"] is False
    assert no_episode_response.details["episodes_before_query_filter"] == 0
    assert no_episode_response.details["matched_episode_count"] == 0
    assert no_episode_response.details["episodes_returned"] == 0
    assert no_episode_response.details["episode_explanations"] == []
    assert no_episode_response.details["memory_items"] == []
    assert no_episode_response.details["memory_item_counts_by_episode"] == {}
    assert no_episode_response.details["summaries"] == []
    assert no_episode_response.details["retrieval_routes_present"] == []
    assert no_episode_response.details["primary_retrieval_routes_present"] == []
    assert no_episode_response.details["auxiliary_retrieval_routes_present"] == []
    assert no_episode_response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert no_episode_response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert no_episode_response.details["retrieval_route_presence"] == {
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
    assert no_episode_response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 0,
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
    }
    assert no_episode_response.details["retrieval_route_scope_item_counts"] == {
        "summary_first": {
            "summary": 0,
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
    }
    assert no_episode_response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
    }
    assert no_episode_response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_include_episodes_false_keeps_response_episode_less_even_when_memory_items_are_enabled() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000031"
    created_at = datetime(2024, 10, 4, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode hidden by include_episodes false shaping",
        metadata={"kind": "episode-hidden"},
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
        content="Direct memory item that should stay hidden",
        metadata={"kind": "hidden-memory-item"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Inherited workspace item hidden by include_episodes false shaping",
        metadata={"kind": "hidden-workspace-item"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
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
                    "ticket_id": "TICKET-CONTEXT-INCLUDE-EPISODES-FALSE-SHAPING",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert response.episodes == ()
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_tokens"] == []
    assert response.details["query_filter_applied"] is False
    assert response.details["episodes_before_query_filter"] == 0
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["episode_explanations"] == []
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {}
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["memory_context_groups"] == [
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited workspace item hidden by include_episodes false shaping",
                    "metadata": {"kind": "hidden-workspace-item"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]
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
        "workspace_inherited_auxiliary": 1,
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
            "episode": 0,
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
            "episode": 0,
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
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_include_episodes_false_query_filter_keeps_response_episode_less_without_summary_first_groups() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000032"
    created_at = datetime(2024, 10, 5, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode hidden by include_episodes false query filter shaping",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before hidden shaping",
        metadata={"kind": "filtered"},
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
        content="Matching direct memory item that should stay hidden",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered direct memory item that should stay hidden",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Inherited workspace item still visible with include_episodes false",
        metadata={"kind": "workspace-item"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-INCLUDE-EPISODES-FALSE-QUERY-FILTER-SHAPING",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="hidden shaping",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.episodes == ()
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_tokens"] == ["hidden", "shaping"]
    assert response.details["query_filter_applied"] is False
    assert response.details["episodes_before_query_filter"] == 0
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["episode_explanations"] == []
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {}
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["memory_context_groups"] == [
        {
            "scope": "workspace",
            "scope_id": workspace_id,
            "parent_scope": None,
            "parent_scope_id": None,
            "selection_kind": "inherited_workspace",
            "selection_route": "workspace_inherited_auxiliary",
            "memory_items": [
                {
                    "memory_id": str(inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Inherited workspace item still visible with include_episodes false",
                    "metadata": {"kind": "workspace-item"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]
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
        "workspace_inherited_auxiliary": 1,
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
            "episode": 0,
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
            "episode": 0,
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
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_limit_truncates_workspace_inherited_auxiliary_output() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000031"
    created_at = datetime(2024, 10, 4, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with low-limit inherited workspace shaping",
        metadata={"kind": "workspace-limit"},
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
        content="Direct memory item for low-limit inherited workspace shaping",
        metadata={"kind": "direct-memory-item"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    newer_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Newer inherited workspace item",
        metadata={"kind": "newer-workspace-item"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    older_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Older inherited workspace item",
        metadata={"kind": "older-workspace-item"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(newer_inherited_workspace_item)
    memory_item_repository.create(older_inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-LIMIT",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with low-limit inherited workspace shaping"
    ]
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(newer_inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Newer inherited workspace item",
            "metadata": {"kind": "newer-workspace-item"},
            "created_at": newer_inherited_workspace_item.created_at.isoformat(),
            "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
        }
    ]
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
                    "content": "Direct memory item for low-limit inherited workspace shaping",
                    "metadata": {"kind": "direct-memory-item"},
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
                    "memory_id": str(newer_inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Newer inherited workspace item",
                    "metadata": {"kind": "newer-workspace-item"},
                    "created_at": newer_inherited_workspace_item.created_at.isoformat(),
                    "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
    ]


def test_memory_get_context_query_filter_keeps_workspace_inherited_auxiliary_limit_truncation() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000031"
    created_at = datetime(2024, 10, 4, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode survives workspace-limit query",
        metadata={"kind": "workspace-limit-matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before workspace-limit truncation",
        metadata={"kind": "workspace-limit-filtered"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct memory item for query-filtered workspace shaping",
        metadata={"kind": "direct-memory-item"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    newer_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Newer inherited workspace item after query filtering",
        metadata={"kind": "newer-workspace-item"},
        created_at=created_at.replace(hour=1, minute=30),
        updated_at=created_at.replace(hour=1, minute=30),
    )
    older_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Older inherited workspace item after query filtering",
        metadata={"kind": "older-workspace-item"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    filtered_episode_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered episode memory item that should not remain visible",
        metadata={"kind": "filtered-memory-item"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_item_repository.create(direct_memory_item)
    memory_item_repository.create(newer_inherited_workspace_item)
    memory_item_repository.create(older_inherited_workspace_item)
    memory_item_repository.create(filtered_episode_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-LIMIT-QUERY-FILTER",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="survives workspace-limit query",
            workflow_instance_id=str(workflow_id),
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode survives workspace-limit query"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(newer_inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Newer inherited workspace item after query filtering",
            "metadata": {"kind": "newer-workspace-item"},
            "created_at": newer_inherited_workspace_item.created_at.isoformat(),
            "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
        }
    ]
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
                    "memory_id": str(direct_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(matching_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Direct memory item for query-filtered workspace shaping",
                    "metadata": {"kind": "direct-memory-item"},
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
                    "memory_id": str(newer_inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Newer inherited workspace item after query filtering",
                    "metadata": {"kind": "newer-workspace-item"},
                    "created_at": newer_inherited_workspace_item.created_at.isoformat(),
                    "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
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


def test_memory_get_context_includes_episode_explanations_without_query_filter() -> None:
    workflow_id = uuid4()
    created_at = datetime(2024, 9, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Recent unfiltered episode",
        metadata={"kind": "recent"},
        created_at=created_at.replace(day=3),
        updated_at=created_at.replace(day=3),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Older unfiltered episode",
        metadata={"kind": "older"},
        created_at=created_at.replace(day=2),
        updated_at=created_at.replace(day=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
        {
            "episode_id": str(second_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    ]


def test_memory_get_context_includes_memory_items_and_summaries_details() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000031"
    created_at = datetime(2024, 10, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with two memory items",
        metadata={"kind": "first"},
        created_at=created_at.replace(day=2),
        updated_at=created_at.replace(day=2),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with one memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=1),
        updated_at=created_at.replace(day=1),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First episode note",
        metadata={"kind": "note"},
        created_at=created_at.replace(day=2, hour=1),
        updated_at=created_at.replace(day=2, hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="First episode checkpoint",
        metadata={"kind": "checkpoint"},
        created_at=created_at.replace(day=2, hour=2),
        updated_at=created_at.replace(day=2, hour=2),
    )
    third_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second episode note",
        metadata={"kind": "note"},
        created_at=created_at.replace(day=1, hour=1),
        updated_at=created_at.replace(day=1, hour=1),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)
    memory_item_repository.create(third_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-DETAILS",
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
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with two memory items",
        "Episode with one memory item",
    ]
    assert response.details["memory_items"] == [
        [
            {
                "memory_id": str(second_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(first_episode.episode_id),
                "type": "checkpoint_note",
                "provenance": "checkpoint",
                "content": "First episode checkpoint",
                "metadata": {"kind": "checkpoint"},
                "created_at": second_memory_item.created_at.isoformat(),
                "updated_at": second_memory_item.updated_at.isoformat(),
            },
            {
                "memory_id": str(first_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(first_episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "First episode note",
                "metadata": {"kind": "note"},
                "created_at": first_memory_item.created_at.isoformat(),
                "updated_at": first_memory_item.updated_at.isoformat(),
            },
        ],
        [
            {
                "memory_id": str(third_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(second_episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Second episode note",
                "metadata": {"kind": "note"},
                "created_at": third_memory_item.created_at.isoformat(),
                "updated_at": third_memory_item.updated_at.isoformat(),
            }
        ],
    ]
    assert response.details["memory_item_counts_by_episode"] == {
        str(first_episode.episode_id): 2,
        str(second_episode.episode_id): 1,
    }
    assert response.details["summaries"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 2,
            "memory_item_types": ["checkpoint_note", "episode_note"],
            "memory_item_provenance": ["checkpoint", "episode"],
        },
        {
            "episode_id": str(second_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        },
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
    assert response.details["primary_episode_groups_present_after_query_filter"] is True
    assert response.details["auxiliary_only_after_query_filter"] is False
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_presence"] == {
        "summary_first": {
            "group_present": True,
            "item_present": True,
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
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 1,
            "episode": 2,
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
    }
    assert response.details["retrieval_route_scope_item_counts"] == {
        "summary_first": {
            "summary": 2,
            "episode": 3,
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
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [
            "summary",
            "episode",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
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
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 2,
                    "memory_item_types": ["checkpoint_note", "episode_note"],
                    "memory_item_provenance": ["checkpoint", "episode"],
                },
                {
                    "episode_id": str(second_episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
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
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(first_episode.episode_id),
                    "type": "checkpoint_note",
                    "provenance": "checkpoint",
                    "content": "First episode checkpoint",
                    "metadata": {"kind": "checkpoint"},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(first_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First episode note",
                    "metadata": {"kind": "note"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                },
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
        {
            "scope": "episode",
            "scope_id": str(second_episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(third_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(second_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Second episode note",
                    "metadata": {"kind": "note"},
                    "created_at": third_memory_item.created_at.isoformat(),
                    "updated_at": third_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]


def test_memory_get_context_omits_memory_items_and_summaries_when_disabled() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000032"
    created_at = datetime(2024, 10, 5, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode without extra detail output",
        metadata={"kind": "single"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=uuid4(),
            workspace_id=UUID(workspace_id),
            episode_id=episode.episode_id,
            type="episode_note",
            provenance="episode",
            content="Stored memory item",
            metadata={"kind": "note"},
            created_at=created_at,
            updated_at=created_at,
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-DISABLED",
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
        "Episode without extra detail output"
    ]
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 1}
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None


def test_memory_get_context_includes_only_summaries_when_memory_items_disabled() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000033"
    created_at = datetime(2024, 10, 6, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with summary-only detail output",
        metadata={"kind": "summary-only"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Stored episode detail",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="Stored checkpoint detail",
        metadata={"kind": "checkpoint"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARIES-ONLY",
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
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with summary-only detail output"
    ]
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 2}
    assert response.details["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 2,
            "memory_item_types": ["checkpoint_note", "episode_note"],
            "memory_item_provenance": ["checkpoint", "episode"],
        }
    ]
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is False
    assert response.details["summary_first_is_summary_only"] is True
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 2,
                    "memory_item_types": ["checkpoint_note", "episode_note"],
                    "memory_item_provenance": ["checkpoint", "episode"],
                }
            ],
        }
    ]


def test_memory_get_context_includes_only_memory_items_when_summaries_disabled() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000034"
    created_at = datetime(2024, 10, 8, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with memory-item-only detail output",
        metadata={"kind": "memory-items-only"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Stored episode detail",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="Stored checkpoint detail",
        metadata={"kind": "checkpoint"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-MEMORY-ITEMS-ONLY",
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
        "Episode with memory-item-only detail output"
    ]
    assert response.details["memory_items"] == [
        [
            {
                "memory_id": str(second_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(episode.episode_id),
                "type": "checkpoint_note",
                "provenance": "checkpoint",
                "content": "Stored checkpoint detail",
                "metadata": {"kind": "checkpoint"},
                "created_at": second_memory_item.created_at.isoformat(),
                "updated_at": second_memory_item.updated_at.isoformat(),
            },
            {
                "memory_id": str(first_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Stored episode detail",
                "metadata": {"kind": "note"},
                "created_at": first_memory_item.created_at.isoformat(),
                "updated_at": first_memory_item.updated_at.isoformat(),
            },
        ]
    ]
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 2}
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None


def test_memory_get_context_summaries_disabled_keeps_primary_path_episode_direct() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000034"
    created_at = datetime(2024, 10, 8, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with summaries disabled primary path",
        metadata={"kind": "summaries-disabled-primary-path"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Stored episode detail",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="Stored checkpoint detail",
        metadata={"kind": "checkpoint"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARIES-DISABLED-PRIMARY-PATH",
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
        "Episode with summaries disabled primary path"
    ]
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["summary_first_has_episode_groups"] is False
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 0
    assert response.details["summary_first_child_episode_ids"] == []
    assert response.details["primary_episode_groups_present_after_query_filter"] is True
    assert response.details["auxiliary_only_after_query_filter"] is False
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == []
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 0,
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
        "episode_direct": [
            "episode",
        ],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
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
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(episode.episode_id),
                    "type": "checkpoint_note",
                    "provenance": "checkpoint",
                    "content": "Stored checkpoint detail",
                    "metadata": {"kind": "checkpoint"},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Stored episode detail",
                    "metadata": {"kind": "note"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                },
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        }
    ]


def test_memory_get_context_includes_inherited_workspace_items_in_details_shape() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000035"
    created_at = datetime(2024, 10, 9, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with inherited workspace memory context",
        metadata={"kind": "hierarchy"},
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
        content="Direct episode memory",
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
        content="Inherited workspace memory",
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
                    "ticket_id": "TICKET-CONTEXT-HIERARCHY-INHERITED",
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
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with inherited workspace memory context"
    ]
    assert response.details["memory_items"] == [
        [
            {
                "memory_id": str(direct_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Direct episode memory",
                "metadata": {"kind": "direct"},
                "created_at": direct_memory_item.created_at.isoformat(),
                "updated_at": direct_memory_item.updated_at.isoformat(),
            }
        ]
    ]
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 1}
    assert response.details["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        }
    ]
    assert response.details["hierarchy_applied"] is True
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
        "workspace_inherited_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(direct_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Direct episode memory",
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
                    "content": "Inherited workspace memory",
                    "metadata": {"kind": "inherited"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
    ]
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Inherited workspace memory",
            "metadata": {"kind": "inherited"},
            "created_at": inherited_workspace_item.created_at.isoformat(),
            "updated_at": inherited_workspace_item.updated_at.isoformat(),
        }
    ]


def test_memory_get_context_omits_inherited_workspace_items_when_memory_items_disabled() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000036"
    created_at = datetime(2024, 10, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with hidden inherited workspace memory",
        metadata={"kind": "flags"},
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
        content="Direct episode memory",
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
        content="Inherited workspace memory",
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
                    "ticket_id": "TICKET-CONTEXT-HIERARCHY-FLAGS",
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
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode with hidden inherited workspace memory"
    ]
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 1}
    assert response.details["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        }
    ]
    assert response.details["hierarchy_applied"] is False
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        }
    ]
    assert response.details["inherited_memory_items"] == []


def test_memory_get_context_keeps_inherited_workspace_items_when_query_matches_episode() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000037"
    created_at = datetime(2024, 10, 11, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary matches direct query",
        metadata={"kind": "query-direct"},
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
        content="Direct context note",
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
        content="Inherited workspace context",
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
                    "ticket_id": "TICKET-CONTEXT-HIERARCHY-QUERY-DIRECT",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="matches direct",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode summary matches direct query"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 1
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
        "workspace_inherited_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["hierarchy_applied"] is True
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is False
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": True,
            "child_episode_groups_emission_reason": "memory_items_enabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        },
        {
            "scope": "episode",
            "scope_id": str(episode.episode_id),
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "parent_group_scope": "summary",
            "parent_group_id": "summary:episode_summary_first",
            "selection_kind": "direct_episode",
            "selection_route": "summary_first",
            "selected_via_summary_first": True,
            "memory_items": [
                {
                    "memory_id": str(direct_memory_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Direct context note",
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
                    "content": "Inherited workspace context",
                    "metadata": {"kind": "inherited"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        },
    ]
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Inherited workspace context",
            "metadata": {"kind": "inherited"},
            "created_at": inherited_workspace_item.created_at.isoformat(),
            "updated_at": inherited_workspace_item.updated_at.isoformat(),
        }
    ]


def test_memory_get_context_summary_first_query_filter_uses_surviving_child_set() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000046"
    created_at = datetime(2024, 10, 21, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary matches surviving query",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary filtered out by query",
        metadata={"kind": "filtered"},
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
        content="Matching episode memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered episode memory item",
        metadata={"kind": "filtered-note"},
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
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-FIRST-QUERY-FILTER",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode summary matches surviving query"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["episodes_returned"] == 1
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
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
                    "workflow_instance_id": str(workflow_id),
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
            "parent_scope_id": str(workflow_id),
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
                    "content": "Matching episode memory item",
                    "metadata": {"kind": "matching-note"},
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
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        }
    ]


def test_memory_get_context_query_filter_keeps_summary_first_child_set_when_memory_items_disabled() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000048"
    created_at = datetime(2024, 10, 22, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Summary-only surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Summary-only filtered out by query",
        metadata={"kind": "filtered"},
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
        content="Matching summary-only memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered summary-only memory item",
        metadata={"kind": "filtered-note"},
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
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Summary-only surviving query match"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is False
    assert response.details["summary_first_is_summary_only"] is True
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(matching_episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(matching_episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
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


def test_memory_get_context_workspace_only_query_filter_summary_first_uses_surviving_child_set() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000049"
    created_at = datetime(2024, 10, 24, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Workspace-only summary matches surviving query",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=24),
        updated_at=created_at.replace(day=24),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Workspace-only summary filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=23),
        updated_at=created_at.replace(day=23),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching workspace-only memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=24, hour=2),
        updated_at=created_at.replace(day=24, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered workspace-only memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=23, hour=2),
        updated_at=created_at.replace(day=23, hour=2),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace-only inherited item not assumed to co-emit",
        metadata={"kind": "workspace-inherited"},
        created_at=created_at.replace(day=24, hour=1),
        updated_at=created_at.replace(day=24, hour=1),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-QUERY-FILTER",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-QUERY-FILTER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
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
        "Workspace-only summary matches surviving query"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
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
                    "content": "Matching workspace-only memory item",
                    "metadata": {"kind": "matching-note"},
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


def test_memory_get_context_workspace_only_query_filter_keeps_summary_first_child_set_when_memory_items_disabled() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000049"
    created_at = datetime(2024, 10, 24, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Workspace-only summary-only surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=24),
        updated_at=created_at.replace(day=24),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Workspace-only summary-only filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=23),
        updated_at=created_at.replace(day=23),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching workspace-only summary-only memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=24, hour=2),
        updated_at=created_at.replace(day=24, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered workspace-only summary-only memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=23, hour=2),
        updated_at=created_at.replace(day=23, hour=2),
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
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY-OTHER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            workspace_id=workspace_id,
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Workspace-only summary-only surviving query match"
    ]
    assert response.details["lookup_scope"] == "workspace"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is False
    assert response.details["summary_first_is_summary_only"] is True
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(matching_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        }
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


def test_memory_get_context_ticket_only_query_filter_keeps_summary_first_child_set_when_memory_items_disabled() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    first_workspace_id = "00000000-0000-0000-0000-000000000050"
    second_workspace_id = "00000000-0000-0000-0000-000000000051"
    created_at = datetime(2024, 10, 25, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Ticket-only summary-only surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=25),
        updated_at=created_at.replace(day=25),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Ticket-only summary-only filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=24),
        updated_at=created_at.replace(day=24),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(first_workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching ticket-only summary-only memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=25, hour=2),
        updated_at=created_at.replace(day=25, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(second_workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered ticket-only summary-only memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=24, hour=2),
        updated_at=created_at.replace(day=24, hour=2),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": first_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY",
                },
                second_workflow_id: {
                    "workspace_id": second_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-SUMMARY-FIRST-QUERY-FILTER-SUMMARY-ONLY",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Ticket-only summary-only surviving query match"
    ]
    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 2
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
        str(second_workflow_id),
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is False
    assert response.details["summary_first_is_summary_only"] is True
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is False
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(matching_episode.episode_id),
                    "workflow_instance_id": str(first_workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        }
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


def test_memory_get_context_ticket_only_low_limit_query_filter_summary_first_keeps_surviving_child_set() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    first_workspace_id = "00000000-0000-0000-0000-000000000052"
    second_workspace_id = "00000000-0000-0000-0000-000000000053"
    created_at = datetime(2024, 10, 26, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Ticket-only low-limit summary-first surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=26),
        updated_at=created_at.replace(day=26),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Ticket-only low-limit summary-first filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=25),
        updated_at=created_at.replace(day=25),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(first_workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching ticket-only low-limit summary-first memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=26, hour=2),
        updated_at=created_at.replace(day=26, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(second_workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered ticket-only low-limit summary-first memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=25, hour=2),
        updated_at=created_at.replace(day=25, hour=2),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": first_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY",
                },
                second_workflow_id: {
                    "workspace_id": second_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY",
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "Ticket-only low-limit summary-first surviving query match",
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
                str(matching_episode.episode_id),
            ],
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
                    "workspace_id": first_workspace_id,
                    "episode_id": str(matching_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Matching ticket-only low-limit summary-first memory item",
                    "metadata": {"kind": "matching-note"},
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


def test_memory_get_context_workspace_only_low_limit_query_filter_summary_first_keeps_surviving_child_set() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000054"
    created_at = datetime(2024, 10, 27, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Workspace-only low-limit summary-first surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=27),
        updated_at=created_at.replace(day=27),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Workspace-only low-limit summary-first filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=26),
        updated_at=created_at.replace(day=26),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching workspace-only low-limit summary-first memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=27, hour=2),
        updated_at=created_at.replace(day=27, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered workspace-only low-limit summary-first memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=26, hour=2),
        updated_at=created_at.replace(day=26, hour=2),
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
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-MULTI-WORKFLOW-LIMIT-QUERY",
                },
                second_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-MULTI-WORKFLOW-LIMIT-QUERY-OTHER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            workspace_id=workspace_id,
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "workspace"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "Workspace-only low-limit summary-first surviving query match",
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
                str(matching_episode.episode_id),
            ],
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
                    "content": "Matching workspace-only low-limit summary-first memory item",
                    "metadata": {"kind": "matching-note"},
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


def test_memory_get_context_ticket_only_query_filter_summary_first_uses_surviving_child_set() -> (
    None
):
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    first_workspace_id = "00000000-0000-0000-0000-000000000050"
    second_workspace_id = "00000000-0000-0000-0000-000000000051"
    created_at = datetime(2024, 10, 25, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="Ticket-only summary matches surviving query",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=25),
        updated_at=created_at.replace(day=25),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Ticket-only summary filtered out by query",
        metadata={"kind": "filtered"},
        created_at=created_at.replace(day=24),
        updated_at=created_at.replace(day=24),
    )
    episode_repository.create(matching_episode)
    episode_repository.create(filtered_episode)

    matching_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(first_workspace_id),
        episode_id=matching_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Matching ticket-only memory item",
        metadata={"kind": "matching-note"},
        created_at=created_at.replace(day=25, hour=2),
        updated_at=created_at.replace(day=25, hour=2),
    )
    filtered_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(second_workspace_id),
        episode_id=filtered_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Filtered ticket-only memory item",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(day=24, hour=2),
        updated_at=created_at.replace(day=24, hour=2),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": first_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-QUERY-FILTER",
                },
                second_workflow_id: {
                    "workspace_id": second_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-QUERY-FILTER",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-QUERY-FILTER",
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
        "Ticket-only summary matches surviving query"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
                    "workspace_id": first_workspace_id,
                    "episode_id": str(matching_episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Matching ticket-only memory item",
                    "metadata": {"kind": "matching-note"},
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


def test_memory_get_context_keeps_inherited_workspace_items_as_auxiliary_context_when_query_matches_only_inherited_context() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000038"
    created_at = datetime(2024, 10, 12, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary does not match inherited-only query",
        metadata={"kind": "query-inherited"},
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
        content="Direct context note",
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
        content="Inherited-only match token",
        metadata={"kind": "inherited-only"},
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
                    "ticket_id": "TICKET-CONTEXT-HIERARCHY-QUERY-INHERITED",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="inherited-only match token",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.episodes == ()
    assert response.details["query_filter_applied"] is True
    assert response.details["matched_episode_count"] == 0
    assert response.details["episodes_returned"] == 0
    assert response.details["primary_episode_groups_present_after_query_filter"] is False
    assert response.details["auxiliary_only_after_query_filter"] is True
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {}
    assert response.details["summaries"] == []
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
        "workspace_inherited_auxiliary": 1,
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
            "episode": 0,
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
            "episode": 0,
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
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["hierarchy_applied"] is True
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is True
    assert (
        response.details["inherited_context_returned_as_auxiliary_without_episode_matches"] is True
    )
    assert response.details["all_episodes_filtered_out_by_query"] is True
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
    # Inherited workspace items are an intentional auxiliary surface and do not
    # participate in episode-oriented query matching.
    assert response.details["memory_context_groups"] == [
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
                    "content": "Inherited-only match token",
                    "metadata": {"kind": "inherited-only"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Inherited-only match token",
            "metadata": {"kind": "inherited-only"},
            "created_at": inherited_workspace_item.created_at.isoformat(),
            "updated_at": inherited_workspace_item.updated_at.isoformat(),
        }
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


def test_memory_get_context_supports_relation_grouping_metadata_for_episode_items() -> None:
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [
            "summary",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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


def test_memory_get_context_group_ordering_is_summary_then_episodes_then_workspace() -> None:
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000048"
    created_at = datetime(2024, 10, 23, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=first_workflow_id,
        summary="First ticket-only workflow low-limit summary-first case",
        metadata={"kind": "ticket-only-multi-workflow-limit-first"},
        created_at=created_at.replace(day=23),
        updated_at=created_at.replace(day=23),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Second ticket-only workflow low-limit summary-first case",
        metadata={"kind": "ticket-only-multi-workflow-limit-second"},
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
        content="First ticket-only workflow low-limit memory item",
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
        content="Second ticket-only workflow low-limit memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=22, hour=2),
        updated_at=created_at.replace(day=22, hour=2),
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
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT",
                },
                second_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000099",
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT",
            limit=1,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "First ticket-only workflow low-limit summary-first case",
    ]
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [
        str(first_episode.episode_id),
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
            ],
            "child_episode_count": 1,
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
                }
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
                    "content": "First ticket-only workflow low-limit memory item",
                    "metadata": {"kind": "first"},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                }
            ],
            "related_memory_items": [],
            "related_memory_item_provenance": [],
            "related_memory_relation_edges": [],
        },
    ]


def test_memory_get_context_group_ordering_is_summary_then_episodes_then_workspace() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000044"
    created_at = datetime(2024, 10, 19, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    newer_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Newer episode for grouped ordering",
        metadata={"kind": "ordering-newer"},
        created_at=created_at.replace(day=19),
        updated_at=created_at.replace(day=19),
    )
    older_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Older episode for grouped ordering",
        metadata={"kind": "ordering-older"},
        created_at=created_at.replace(day=18),
        updated_at=created_at.replace(day=18),
    )
    episode_repository.create(older_episode)
    episode_repository.create(newer_episode)

    newer_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=newer_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer grouped-order memory item",
        metadata={"kind": "newer"},
        created_at=created_at.replace(day=19, hour=2),
        updated_at=created_at.replace(day=19, hour=2),
    )
    older_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=older_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Older grouped-order memory item",
        metadata={"kind": "older"},
        created_at=created_at.replace(day=18, hour=2),
        updated_at=created_at.replace(day=18, hour=2),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace grouped-order memory item",
        metadata={"kind": "workspace"},
        created_at=created_at.replace(day=19, hour=1),
        updated_at=created_at.replace(day=19, hour=1),
    )
    memory_item_repository.create(newer_memory_item)
    memory_item_repository.create(older_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-GROUP-ORDERING",
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
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Newer episode for grouped ordering",
        "Older episode for grouped ordering",
    ]
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
        "episode",
        "workspace",
    ]
    assert response.details["retrieval_routes_present"] == [
        "summary_first",
        "workspace_inherited_auxiliary",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 1,
            "episode": 2,
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
            "summary": 2,
            "episode": 2,
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
        "summary_first": [
            "summary",
            "episode",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert response.details["memory_context_groups"][0] == {
        "scope": "summary",
        "scope_id": None,
        "group_id": "summary:episode_summary_first",
        "parent_scope": "workflow_instance",
        "parent_scope_id": str(workflow_id),
        "selection_kind": "episode_summary_first",
        "selection_route": "summary_first",
        "child_episode_ids": [
            str(newer_episode.episode_id),
            str(older_episode.episode_id),
        ],
        "child_episode_count": 2,
        "child_episode_ordering": "returned_episode_order",
        "child_episode_groups_emitted": True,
        "child_episode_groups_emission_reason": "memory_items_enabled",
        "summaries": [
            {
                "episode_id": str(newer_episode.episode_id),
                "workflow_instance_id": str(workflow_id),
                "memory_item_count": 1,
                "memory_item_types": ["episode_note"],
                "memory_item_provenance": ["episode"],
            },
            {
                "episode_id": str(older_episode.episode_id),
                "workflow_instance_id": str(workflow_id),
                "memory_item_count": 1,
                "memory_item_types": ["episode_note"],
                "memory_item_provenance": ["episode"],
            },
        ],
    }
    assert response.details["memory_context_groups"][1] == {
        "scope": "episode",
        "scope_id": str(newer_episode.episode_id),
        "parent_scope": "workflow_instance",
        "parent_scope_id": str(workflow_id),
        "parent_group_scope": "summary",
        "parent_group_id": "summary:episode_summary_first",
        "selection_kind": "direct_episode",
        "selection_route": "summary_first",
        "selected_via_summary_first": True,
        "memory_items": [
            {
                "memory_id": str(newer_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(newer_episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Newer grouped-order memory item",
                "metadata": {"kind": "newer"},
                "created_at": newer_memory_item.created_at.isoformat(),
                "updated_at": newer_memory_item.updated_at.isoformat(),
            }
        ],
        "related_memory_items": [],
        "related_memory_item_provenance": [],
        "related_memory_relation_edges": [],
    }
    assert response.details["memory_context_groups"][2] == {
        "scope": "episode",
        "scope_id": str(older_episode.episode_id),
        "parent_scope": "workflow_instance",
        "parent_scope_id": str(workflow_id),
        "parent_group_scope": "summary",
        "parent_group_id": "summary:episode_summary_first",
        "selection_kind": "direct_episode",
        "selection_route": "summary_first",
        "selected_via_summary_first": True,
        "memory_items": [
            {
                "memory_id": str(older_memory_item.memory_id),
                "workspace_id": workspace_id,
                "episode_id": str(older_episode.episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Older grouped-order memory item",
                "metadata": {"kind": "older"},
                "created_at": older_memory_item.created_at.isoformat(),
                "updated_at": older_memory_item.updated_at.isoformat(),
            }
        ],
        "related_memory_items": [],
        "related_memory_item_provenance": [],
        "related_memory_relation_edges": [],
    }


def test_memory_get_context_marks_episode_groups_as_selected_via_summary_first() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000045"
    created_at = datetime(2024, 10, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode for summary-first grouped selection",
        metadata={"kind": "selected-first"},
        created_at=created_at,
        updated_at=created_at,
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode for summary-first grouped selection",
        metadata={"kind": "selected-second"},
        created_at=created_at.replace(day=19),
        updated_at=created_at.replace(day=19),
    )
    episode_repository.create(second_episode)
    episode_repository.create(first_episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First selected episode memory item",
        metadata={"kind": "first"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second selected episode memory item",
        metadata={"kind": "second"},
        created_at=created_at.replace(day=19, hour=2),
        updated_at=created_at.replace(day=19, hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-FIRST-GROUP-SELECTION",
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
            include_summaries=True,
        )
    )

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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
    }
    assert response.details["retrieval_route_scope_counts"] == {
        "summary_first": {
            "summary": 1,
            "episode": 2,
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
    }
    assert response.details["retrieval_route_scope_item_counts"] == {
        "summary_first": {
            "summary": 2,
            "episode": 2,
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
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [
            "summary",
            "episode",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
        "episode",
    ]
    assert response.details["memory_context_groups"][1]["selected_via_summary_first"] is True
    assert response.details["memory_context_groups"][2]["selected_via_summary_first"] is True
    assert response.details["memory_context_groups"][1]["selection_kind"] == ("direct_episode")
    assert response.details["memory_context_groups"][2]["selection_kind"] == ("direct_episode")


def test_memory_get_context_group_ordering_summary_only_has_no_placeholder_groups() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000045"
    created_at = datetime(2024, 10, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with summary-only ordering coverage",
        metadata={"kind": "summary-only-ordering"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Summary-only ordering note",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="Summary-only ordering checkpoint",
        metadata={"kind": "checkpoint"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-ONLY-ORDERING",
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
            include_summaries=True,
        )
    )

    assert [group["scope"] for group in response.details["memory_context_groups"]] == ["summary"]
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
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
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
    }
    assert response.details["retrieval_route_scope_item_counts"] == {
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
    }
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [
            "summary",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
    }
    assert response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [str(episode.episode_id)],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 2,
                    "memory_item_types": ["checkpoint_note", "episode_note"],
                    "memory_item_provenance": ["checkpoint", "episode"],
                }
            ],
        }
    ]


def test_memory_get_context_group_ordering_workspace_only_has_no_placeholder_groups() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000046"
    created_at = datetime(2024, 10, 21, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary does not match workspace-only ordering query",
        metadata={"kind": "workspace-only-ordering"},
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
        content="Direct workspace-only ordering note",
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
        content="Workspace-only ordering token",
        metadata={"kind": "workspace-only"},
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
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-ONLY-ORDERING",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="workspace-only ordering token",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.episodes == ()
    assert response.details["summaries"] == []
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
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
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
            "episode": 0,
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
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == ["workspace"]
    assert response.details["memory_context_groups"] == [
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
                    "content": "Workspace-only ordering token",
                    "metadata": {"kind": "workspace-only"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]

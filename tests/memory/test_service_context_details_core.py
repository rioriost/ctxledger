from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": None,
                "latest_episode_created_at": datetime(2024, 1, 11, tzinfo=UTC).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_surfaces_remember_path_explainability_details() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()
    episode_id = uuid4()
    objective_memory_id = uuid4()
    next_action_memory_id = uuid4()
    completion_note_memory_id = uuid4()
    relation_id = uuid4()
    created_at = datetime(2024, 2, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode_repository.create(
        EpisodeRecord(
            episode_id=episode_id,
            workflow_instance_id=workflow_id,
            summary="Checkpoint and completion memory accumulated for remember-path explainability",
            metadata={"kind": "remember-path"},
            created_at=created_at,
            updated_at=created_at,
        )
    )

    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=objective_memory_id,
            workspace_id=workspace_id,
            episode_id=episode_id,
            type="workflow_objective",
            provenance="workflow_checkpoint_auto",
            content="Strengthen checkpoint-driven remember-path accumulation",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "current_objective",
                "promotion_source": "checkpoint.current_objective",
                "checkpoint_id": "checkpoint-1",
                "step_name": "remember_path_checkpoint",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=next_action_memory_id,
            workspace_id=workspace_id,
            episode_id=episode_id,
            type="workflow_next_action",
            provenance="workflow_checkpoint_auto",
            content="Complete the end-to-end remember-path validation",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "next_intended_action",
                "promotion_source": "checkpoint.next_intended_action",
                "checkpoint_id": "checkpoint-1",
                "step_name": "remember_path_checkpoint",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )
    memory_item_repository.create(
        MemoryItemRecord(
            memory_id=completion_note_memory_id,
            workspace_id=workspace_id,
            episode_id=episode_id,
            type="workflow_completion_note",
            provenance="workflow_complete_auto",
            content="Completed the remember-path end-to-end validation flow",
            metadata={
                "memory_origin": "workflow_complete_auto",
                "step_name": "workflow_complete",
                "workflow_status": "completed",
                "attempt_status": "succeeded",
            },
            created_at=created_at,
            updated_at=created_at,
        )
    )

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=relation_id,
            source_memory_id=next_action_memory_id,
            target_memory_id=objective_memory_id,
            relation_type="supports",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "relation_reason": "next_action_supports_objective",
                "relation_description": "next intended action supports the current objective",
                "source_memory_type": "workflow_next_action",
                "target_memory_type": "workflow_objective",
            },
            created_at=created_at,
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
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

    assert response.details["remember_path_explainability_present"] is True
    assert response.details["remember_path_origin_counts"] == {
        "workflow_checkpoint_auto": 2,
        "workflow_complete_auto": 1,
    }
    assert response.details["remember_path_promotion_field_counts"] == {
        "current_objective": 1,
        "next_intended_action": 1,
    }
    assert response.details["remember_path_relation_reason_counts"] == {
        "next_action_supports_objective": 1,
    }

    explainability = response.details["remember_path_explainability_by_episode"][str(episode_id)]
    assert explainability["memory_summary"] == {
        "memory_origin_counts": {
            "workflow_checkpoint_auto": 2,
            "workflow_complete_auto": 1,
        },
        "promotion_field_counts": {
            "current_objective": 1,
            "next_intended_action": 1,
        },
        "checkpoint_origin_present": True,
        "completion_origin_present": True,
    }
    assert explainability["relation_summary"] == {
        "relation_reason_counts": {
            "next_action_supports_objective": 1,
        },
        "checkpoint_origin_present": True,
        "completion_origin_present": False,
    }
    assert sorted(
        explainability["memory_items"],
        key=lambda item: item["memory_id"],
    ) == sorted(
        [
            {
                "memory_id": str(completion_note_memory_id),
                "memory_type": "workflow_completion_note",
                "provenance": "workflow_complete_auto",
                "memory_origin": "workflow_complete_auto",
                "promotion_field": None,
                "promotion_source": None,
                "checkpoint_id": None,
                "step_name": "workflow_complete",
                "workflow_status": "completed",
                "attempt_status": "succeeded",
            },
            {
                "memory_id": str(next_action_memory_id),
                "memory_type": "workflow_next_action",
                "provenance": "workflow_checkpoint_auto",
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "next_intended_action",
                "promotion_source": "checkpoint.next_intended_action",
                "checkpoint_id": "checkpoint-1",
                "step_name": "remember_path_checkpoint",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            {
                "memory_id": str(objective_memory_id),
                "memory_type": "workflow_objective",
                "provenance": "workflow_checkpoint_auto",
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "current_objective",
                "promotion_source": "checkpoint.current_objective",
                "checkpoint_id": "checkpoint-1",
                "step_name": "remember_path_checkpoint",
                "workflow_status": "running",
                "attempt_status": "running",
            },
        ],
        key=lambda item: item["memory_id"],
    )
    assert explainability["relation_explanations"] == [
        {
            "memory_relation_id": str(relation_id),
            "relation_type": "supports",
            "relation_reason": "next_action_supports_objective",
            "relation_description": "next intended action supports the current objective",
            "memory_origin": "workflow_checkpoint_auto",
            "source_memory_type": "workflow_next_action",
            "target_memory_type": "workflow_objective",
            "source_memory_id": str(next_action_memory_id),
            "target_memory_id": str(objective_memory_id),
        }
    ]
    assert response.details["related_context_relation_types"] == ["supports"]


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
        "graph_summary_auxiliary": 0,
    }
    assert no_episode_response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": [],
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": [],
    }
    assert response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_summary_only_primary_path_differs_from_episode_less_shaping() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000033"
    created_at = datetime(2024, 10, 6, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Matching summary-only primary path episode",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Filtered episode outside the surviving child set",
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
        content="Direct memory item hidden by summary-only shaping when memory items are disabled",
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
        content="Filtered direct memory item hidden in both shapes",
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
        content="Inherited workspace item visible only in the episode-less shaping path",
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
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-ONLY-VS-EPISODE-LESS",
                }
            }
        ),
    )

    summary_only_response = service.get_context(
        GetMemoryContextRequest(
            query="summary-only primary path",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )
    episode_less_response = service.get_context(
        GetMemoryContextRequest(
            query="summary-only primary path",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in summary_only_response.episodes] == [
        "Matching summary-only primary path episode"
    ]
    assert summary_only_response.details["query_filter_applied"] is True
    assert summary_only_response.details["summary_selection_applied"] is True
    assert summary_only_response.details["summary_selection_kind"] == ("episode_summary_first")
    assert summary_only_response.details["summary_first_has_episode_groups"] is False
    assert summary_only_response.details["summary_first_is_summary_only"] is True
    assert summary_only_response.details["summary_first_child_episode_count"] == 1
    assert summary_only_response.details["summary_first_child_episode_ids"] == [
        str(matching_episode.episode_id),
    ]
    assert (
        summary_only_response.details["primary_episode_groups_present_after_query_filter"] is False
    )
    assert summary_only_response.details["auxiliary_only_after_query_filter"] is False
    assert summary_only_response.details["memory_context_groups"] == [
        {
            "scope": "summary",
            "scope_id": None,
            "group_id": "summary:episode_summary_first",
            "parent_scope": "workflow_instance",
            "parent_scope_id": str(workflow_id),
            "selection_kind": "episode_summary_first",
            "selection_route": "summary_first",
            "child_episode_ids": [
                str(matching_episode.episode_id),
            ],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(matching_episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": [
                        "episode_note",
                    ],
                    "memory_item_provenance": [
                        "episode",
                    ],
                    "remember_path_explainability": {},
                }
            ],
        }
    ]
    assert summary_only_response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert summary_only_response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert summary_only_response.details["auxiliary_retrieval_routes_present"] == []
    assert summary_only_response.details["retrieval_route_group_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }

    assert episode_less_response.episodes == ()
    assert episode_less_response.details["query_filter_applied"] is False
    assert episode_less_response.details["summary_selection_applied"] is False
    assert episode_less_response.details["summary_selection_kind"] is None
    assert "summary_first_has_episode_groups" not in episode_less_response.details
    assert "summary_first_is_summary_only" not in episode_less_response.details
    assert "summary_first_child_episode_count" not in episode_less_response.details
    assert "summary_first_child_episode_ids" not in episode_less_response.details
    assert "primary_episode_groups_present_after_query_filter" not in episode_less_response.details
    assert "auxiliary_only_after_query_filter" not in episode_less_response.details
    assert episode_less_response.details["memory_context_groups"] == [
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
                    "content": "Inherited workspace item visible only in the episode-less shaping path",
                    "metadata": {"kind": "workspace-item"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]
    assert episode_less_response.details["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert episode_less_response.details["primary_retrieval_routes_present"] == []
    assert episode_less_response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert episode_less_response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }


def test_memory_get_context_falls_back_to_episode_summary_when_canonical_summary_is_absent() -> (
    None
):
    workflow_id = uuid4()
    created_at = datetime(2024, 10, 6, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Fallback episode summary remains the summary source",
        metadata={"kind": "fallback"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID("00000000-0000-0000-0000-000000000101"),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct item should support the fallback episode summary path",
        metadata={"kind": "episode-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    memory_item_repository.create(memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
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

    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": [
                "episode_note",
            ],
            "memory_item_provenance": [
                "episode",
            ],
            "remember_path_explainability": {},
        }
    ]
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
                str(episode.episode_id),
            ],
            "child_episode_count": 1,
            "child_episode_ordering": "returned_episode_order",
            "child_episode_groups_emitted": False,
            "child_episode_groups_emission_reason": "memory_items_disabled",
            "summaries": [
                {
                    "episode_id": str(episode.episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": [
                        "episode_note",
                    ],
                    "memory_item_provenance": [
                        "episode",
                    ],
                    "remember_path_explainability": {},
                }
            ],
        }
    ]

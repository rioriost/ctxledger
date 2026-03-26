from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetContextResponse,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryWorkflowLookupRepository,
    MemoryFeature,
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

    assert isinstance(response, GetContextResponse)
    assert response.feature == MemoryFeature.GET_CONTEXT
    assert response.implemented is True
    assert response.status == "ok"
    assert response.available_in_version == "0.2.0"
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
    assert no_episode_response.details["workflow_instance_id"] == str(workflow_id)


def test_memory_get_context_intersects_workspace_and_ticket_scope() -> None:
    matching_workflow_id = uuid4()
    same_workspace_workflow_id = uuid4()
    same_ticket_workflow_id = uuid4()
    created_at = datetime(2024, 3, 13, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=matching_workflow_id,
            summary="Matching workflow context",
            metadata={"kind": "match"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=same_workspace_workflow_id,
            summary="Workspace-only workflow context",
            metadata={"kind": "workspace-only"},
            created_at=created_at.replace(day=14),
            updated_at=created_at.replace(day=14),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=same_ticket_workflow_id,
            summary="Ticket-only workflow context",
            metadata={"kind": "ticket-only"},
            created_at=created_at.replace(day=15),
            updated_at=created_at.replace(day=15),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                matching_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000001",
                    "ticket_id": "TICKET-NARROW",
                },
                same_workspace_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000001",
                    "ticket_id": "OTHER-TICKET",
                },
                same_ticket_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000002",
                    "ticket_id": "TICKET-NARROW",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="00000000-0000-0000-0000-000000000001",
            ticket_id="TICKET-NARROW",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == ["Matching workflow context"]
    assert (
        response.details
        | {
            "query": None,
            "normalized_query": None,
            "query_tokens": [],
            "lookup_scope": "workspace_and_ticket",
            "workspace_id": "00000000-0000-0000-0000-000000000001",
            "workflow_instance_id": None,
            "ticket_id": "TICKET-NARROW",
            "limit": 10,
            "include_episodes": True,
            "include_memory_items": False,
            "include_summaries": False,
            "workflow_candidate_ordering": {
                "ordering_basis": "workflow_freshness_signals",
                "workflow_instance_id_priority_applied": False,
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
                "workspace_candidate_ids": [
                    str(matching_workflow_id),
                    str(same_workspace_workflow_id),
                ],
                "ticket_candidate_ids": [
                    str(matching_workflow_id),
                    str(same_ticket_workflow_id),
                ],
                "resolver_candidate_ids": [str(matching_workflow_id)],
                "final_candidate_ids": [str(matching_workflow_id)],
                "candidate_signals": {
                    str(matching_workflow_id): {
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
                        "latest_episode_created_at": created_at.isoformat(),
                        "latest_attempt_started_at": None,
                        "workflow_updated_at": None,
                    }
                },
            },
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(matching_workflow_id)],
            "query_filter_applied": False,
            "episodes_before_query_filter": 1,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [
                {
                    "episode_id": str(response.episodes[0].episode_id),
                    "workflow_instance_id": str(matching_workflow_id),
                    "matched": True,
                    "explanation_basis": "unfiltered_episode_context",
                    "matched_summary": False,
                    "matched_metadata_values": [],
                }
            ],
            "memory_items": [],
            "related_memory_items_by_episode": {},
            "memory_item_counts_by_episode": {
                str(response.episodes[0].episode_id): 0,
            },
            "summaries": [],
            "summary_selection_applied": False,
            "summary_selection_kind": None,
            "hierarchy_applied": False,
            "inherited_context_is_auxiliary": False,
            "inherited_context_returned_without_episode_matches": False,
            "inherited_context_returned_as_auxiliary_without_episode_matches": False,
            "related_context_is_auxiliary": False,
            "related_context_relation_types": [],
            "related_context_selection_route": None,
            "related_context_returned_without_episode_matches": False,
            "all_episodes_filtered_out_by_query": False,
            "flat_related_memory_items_is_compatibility_field": False,
            "flat_related_memory_items_matches_grouped_episode_related_items": False,
            "related_memory_items_by_episode_is_primary_structured_output": False,
            "related_memory_items_by_episode_are_compatibility_output": False,
            "relation_memory_context_groups_are_primary_output": False,
            "group_related_memory_items_are_convenience_output": False,
            "retrieval_routes_present": [],
            "primary_retrieval_routes_present": [],
            "auxiliary_retrieval_routes_present": [],
            "retrieval_route_group_counts": {
                "summary_first": 0,
                "episode_direct": 0,
                "workspace_inherited_auxiliary": 0,
                "relation_supports_auxiliary": 0,
                "graph_summary_auxiliary": 0,
            },
            "retrieval_route_item_counts": {
                "summary_first": 0,
                "episode_direct": 0,
                "workspace_inherited_auxiliary": 0,
                "relation_supports_auxiliary": 0,
                "graph_summary_auxiliary": 0,
            },
            "retrieval_route_presence": {
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
            },
            "retrieval_route_scope_counts": {
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
            },
            "retrieval_route_scope_item_counts": {
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
            },
            "retrieval_route_scopes_present": {
                "summary_first": [],
                "episode_direct": [],
                "workspace_inherited_auxiliary": [],
                "relation_supports_auxiliary": [],
                "graph_summary_auxiliary": [],
            },
            "memory_context_groups": [],
            "inherited_memory_items": [],
            "related_memory_items": [],
        }
        == response.details
    )


def test_memory_get_context_intersects_workspace_and_ticket_scope_before_query_filtering() -> None:
    matching_workflow_id = uuid4()
    same_workspace_workflow_id = uuid4()
    same_ticket_workflow_id = uuid4()
    created_at = datetime(2024, 3, 16, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=matching_workflow_id,
            summary="Projection drift root cause",
            metadata={"kind": "match"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=same_workspace_workflow_id,
            summary="Projection drift workspace decoy",
            metadata={"kind": "workspace-only"},
            created_at=created_at.replace(day=17),
            updated_at=created_at.replace(day=17),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=same_ticket_workflow_id,
            summary="Projection drift ticket decoy",
            metadata={"kind": "ticket-only"},
            created_at=created_at.replace(day=18),
            updated_at=created_at.replace(day=18),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                matching_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000010",
                    "ticket_id": "TICKET-QUERY",
                },
                same_workspace_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000010",
                    "ticket_id": "OTHER-TICKET",
                },
                same_ticket_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000011",
                    "ticket_id": "TICKET-QUERY",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="root cause",
            workspace_id="00000000-0000-0000-0000-000000000010",
            ticket_id="TICKET-QUERY",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == ["Projection drift root cause"]
    assert (
        response.details
        | {
            "query": "root cause",
            "normalized_query": "root cause",
            "query_tokens": ["root", "cause"],
            "lookup_scope": "workspace_and_ticket",
            "workspace_id": "00000000-0000-0000-0000-000000000010",
            "workflow_instance_id": None,
            "ticket_id": "TICKET-QUERY",
            "limit": 10,
            "include_episodes": True,
            "include_memory_items": False,
            "include_summaries": False,
            "workflow_candidate_ordering": {
                "ordering_basis": "workflow_freshness_signals",
                "workflow_instance_id_priority_applied": False,
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
                "workspace_candidate_ids": [
                    str(matching_workflow_id),
                    str(same_workspace_workflow_id),
                ],
                "ticket_candidate_ids": [
                    str(matching_workflow_id),
                    str(same_ticket_workflow_id),
                ],
                "resolver_candidate_ids": [str(matching_workflow_id)],
                "final_candidate_ids": [str(matching_workflow_id)],
                "candidate_signals": {
                    str(matching_workflow_id): {
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
                        "latest_episode_created_at": created_at.isoformat(),
                        "latest_attempt_started_at": None,
                        "workflow_updated_at": None,
                    }
                },
            },
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(matching_workflow_id)],
            "query_filter_applied": True,
            "episodes_before_query_filter": 1,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [
                {
                    "episode_id": str(response.episodes[0].episode_id),
                    "workflow_instance_id": str(matching_workflow_id),
                    "matched": True,
                    "explanation_basis": "query_match_evaluation",
                    "matched_summary": True,
                    "matched_metadata_values": [],
                }
            ],
            "memory_items": [],
            "related_memory_items_by_episode": {},
            "memory_item_counts_by_episode": {
                str(response.episodes[0].episode_id): 0,
            },
            "summaries": [],
            "summary_selection_applied": False,
            "summary_selection_kind": None,
            "hierarchy_applied": False,
            "inherited_context_is_auxiliary": False,
            "inherited_context_returned_without_episode_matches": False,
            "inherited_context_returned_as_auxiliary_without_episode_matches": False,
            "related_context_is_auxiliary": False,
            "related_context_relation_types": [],
            "related_context_selection_route": None,
            "related_context_returned_without_episode_matches": False,
            "all_episodes_filtered_out_by_query": False,
            "flat_related_memory_items_is_compatibility_field": False,
            "flat_related_memory_items_matches_grouped_episode_related_items": False,
            "related_memory_items_by_episode_is_primary_structured_output": False,
            "related_memory_items_by_episode_are_compatibility_output": False,
            "relation_memory_context_groups_are_primary_output": False,
            "group_related_memory_items_are_convenience_output": False,
            "retrieval_routes_present": [],
            "primary_retrieval_routes_present": [],
            "auxiliary_retrieval_routes_present": [],
            "retrieval_route_group_counts": {
                "summary_first": 0,
                "episode_direct": 0,
                "workspace_inherited_auxiliary": 0,
                "relation_supports_auxiliary": 0,
                "graph_summary_auxiliary": 0,
            },
            "retrieval_route_item_counts": {
                "summary_first": 0,
                "episode_direct": 0,
                "workspace_inherited_auxiliary": 0,
                "relation_supports_auxiliary": 0,
                "graph_summary_auxiliary": 0,
            },
            "retrieval_route_presence": {
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
            },
            "retrieval_route_scope_counts": {
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
            },
            "retrieval_route_scope_item_counts": {
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
            },
            "retrieval_route_scopes_present": {
                "summary_first": [],
                "episode_direct": [],
                "workspace_inherited_auxiliary": [],
                "relation_supports_auxiliary": [],
                "graph_summary_auxiliary": [],
            },
            "memory_context_groups": [],
            "inherited_memory_items": [],
            "related_memory_items": [],
        }
        == response.details
    )


def test_memory_get_context_prefers_checkpoint_freshness_over_episode_recency() -> None:
    checkpoint_fresh_workflow_id = uuid4()
    episode_fresh_workflow_id = uuid4()
    created_at = datetime(2024, 3, 16, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=checkpoint_fresh_workflow_id,
            summary="Checkpoint freshness winner",
            metadata={"kind": "checkpoint-fresh"},
            created_at=created_at.replace(day=10),
            updated_at=created_at.replace(day=10),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=episode_fresh_workflow_id,
            summary="Episode recency only",
            metadata={"kind": "episode-fresh"},
            created_at=created_at.replace(day=20),
            updated_at=created_at.replace(day=20),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                checkpoint_fresh_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000020",
                    "ticket_id": "TICKET-FRESHNESS",
                    "latest_checkpoint_created_at": created_at.replace(day=21),
                    "latest_verify_report_created_at": created_at.replace(day=15),
                    "latest_attempt_started_at": created_at.replace(day=19),
                    "workflow_updated_at": created_at.replace(day=18),
                },
                episode_fresh_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000020",
                    "ticket_id": "TICKET-FRESHNESS",
                    "latest_checkpoint_created_at": created_at.replace(day=11),
                    "latest_verify_report_created_at": created_at.replace(day=12),
                    "latest_attempt_started_at": created_at.replace(day=17),
                    "workflow_updated_at": created_at.replace(day=17),
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="00000000-0000-0000-0000-000000000020",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Episode recency only",
        "Checkpoint freshness winner",
    ]
    assert response.details["workflow_candidate_ordering"] == {
        "ordering_basis": "workflow_freshness_signals",
        "workflow_instance_id_priority_applied": False,
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
        "workspace_candidate_ids": [
            str(checkpoint_fresh_workflow_id),
            str(episode_fresh_workflow_id),
        ],
        "ticket_candidate_ids": [],
        "resolver_candidate_ids": [
            str(checkpoint_fresh_workflow_id),
            str(episode_fresh_workflow_id),
        ],
        "final_candidate_ids": [
            str(checkpoint_fresh_workflow_id),
            str(episode_fresh_workflow_id),
        ],
        "candidate_signals": {
            str(checkpoint_fresh_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=21).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=15).isoformat()),
                "latest_episode_created_at": created_at.replace(day=10).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=19).isoformat(),
                "workflow_updated_at": created_at.replace(day=18).isoformat(),
            },
            str(episode_fresh_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=11).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=12).isoformat()),
                "latest_episode_created_at": created_at.replace(day=20).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=17).isoformat(),
                "workflow_updated_at": created_at.replace(day=17).isoformat(),
            },
        },
    }


def test_memory_get_context_prefers_verify_report_freshness_after_checkpoint_tie() -> None:
    verify_fresh_workflow_id = uuid4()
    verify_stale_workflow_id = uuid4()
    created_at = datetime(2024, 5, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=verify_fresh_workflow_id,
            summary="Verify-fresh workflow",
            metadata={"kind": "verify-fresh"},
            created_at=created_at.replace(day=3),
            updated_at=created_at.replace(day=3),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=verify_stale_workflow_id,
            summary="Verify-stale workflow",
            metadata={"kind": "verify-stale"},
            created_at=created_at.replace(day=4),
            updated_at=created_at.replace(day=4),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                verify_fresh_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000022",
                    "ticket_id": "TICKET-VERIFY",
                    "latest_checkpoint_created_at": created_at.replace(day=10),
                    "latest_verify_report_created_at": created_at.replace(day=12),
                    "latest_attempt_started_at": created_at.replace(day=9),
                    "workflow_updated_at": created_at.replace(day=9),
                },
                verify_stale_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000022",
                    "ticket_id": "TICKET-VERIFY",
                    "latest_checkpoint_created_at": created_at.replace(day=10),
                    "latest_verify_report_created_at": created_at.replace(day=11),
                    "latest_attempt_started_at": created_at.replace(day=9),
                    "workflow_updated_at": created_at.replace(day=9),
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="00000000-0000-0000-0000-000000000022",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["workflow_candidate_ordering"] == {
        "ordering_basis": "workflow_freshness_signals",
        "workflow_instance_id_priority_applied": False,
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
        "workspace_candidate_ids": [
            str(verify_fresh_workflow_id),
            str(verify_stale_workflow_id),
        ],
        "ticket_candidate_ids": [],
        "resolver_candidate_ids": [
            str(verify_fresh_workflow_id),
            str(verify_stale_workflow_id),
        ],
        "final_candidate_ids": [
            str(verify_fresh_workflow_id),
            str(verify_stale_workflow_id),
        ],
        "candidate_signals": {
            str(verify_fresh_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=10).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=12).isoformat()),
                "latest_episode_created_at": created_at.replace(day=3).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
            str(verify_stale_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=10).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=11).isoformat()),
                "latest_episode_created_at": created_at.replace(day=4).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
        },
    }


def test_memory_get_context_falls_back_to_episode_recency_after_verify_tie() -> None:
    first_workflow_id = uuid4()
    second_workflow_id = uuid4()
    created_at = datetime(2024, 6, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=first_workflow_id,
            summary="First workflow episode",
            metadata={"kind": "first"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=second_workflow_id,
            summary="Second workflow episode",
            metadata={"kind": "second"},
            created_at=created_at.replace(day=5),
            updated_at=created_at.replace(day=5),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                first_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000023",
                    "ticket_id": "TICKET-PROJECTION",
                    "latest_checkpoint_created_at": created_at.replace(day=10),
                    "latest_verify_report_created_at": created_at.replace(day=11),
                    "latest_attempt_started_at": created_at.replace(day=9),
                    "workflow_updated_at": created_at.replace(day=9),
                },
                second_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000023",
                    "ticket_id": "TICKET-PROJECTION",
                    "latest_checkpoint_created_at": created_at.replace(day=10),
                    "latest_verify_report_created_at": created_at.replace(day=11),
                    "latest_attempt_started_at": created_at.replace(day=9),
                    "workflow_updated_at": created_at.replace(day=9),
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="00000000-0000-0000-0000-000000000023",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["workflow_candidate_ordering"] == {
        "ordering_basis": "workflow_freshness_signals",
        "workflow_instance_id_priority_applied": False,
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
        "workspace_candidate_ids": [
            str(first_workflow_id),
            str(second_workflow_id),
        ],
        "ticket_candidate_ids": [],
        "resolver_candidate_ids": [
            str(first_workflow_id),
            str(second_workflow_id),
        ],
        "final_candidate_ids": [
            str(second_workflow_id),
            str(first_workflow_id),
        ],
        "candidate_signals": {
            str(first_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=10).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=11).isoformat()),
                "latest_episode_created_at": created_at.replace(day=2).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
            str(second_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (created_at.replace(day=10).isoformat()),
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": (created_at.replace(day=11).isoformat()),
                "latest_episode_created_at": created_at.replace(day=5).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
        },
    }


def test_memory_get_context_falls_back_to_episode_recency_without_checkpoint_signal() -> None:
    older_episode_workflow_id = uuid4()
    newer_episode_workflow_id = uuid4()
    created_at = datetime(2024, 4, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=older_episode_workflow_id,
            summary="Older episode workflow",
            metadata={"kind": "older"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=newer_episode_workflow_id,
            summary="Newer episode workflow",
            metadata={"kind": "newer"},
            created_at=created_at.replace(day=5),
            updated_at=created_at.replace(day=5),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                older_episode_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000021",
                    "ticket_id": "TICKET-FALLBACK",
                    "projection_open_failure_count": 0,
                    "latest_attempt_started_at": created_at.replace(day=1),
                    "workflow_updated_at": created_at.replace(day=1),
                },
                newer_episode_workflow_id: {
                    "workspace_id": "00000000-0000-0000-0000-000000000021",
                    "ticket_id": "TICKET-FALLBACK",
                    "projection_open_failure_count": 0,
                    "latest_attempt_started_at": created_at.replace(day=1),
                    "workflow_updated_at": created_at.replace(day=1),
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id="00000000-0000-0000-0000-000000000021",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Newer episode workflow",
        "Older episode workflow",
    ]
    assert response.details["workflow_candidate_ordering"] == {
        "ordering_basis": "workflow_freshness_signals",
        "workflow_instance_id_priority_applied": False,
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
        "workspace_candidate_ids": [
            str(older_episode_workflow_id),
            str(newer_episode_workflow_id),
        ],
        "ticket_candidate_ids": [],
        "resolver_candidate_ids": [
            str(older_episode_workflow_id),
            str(newer_episode_workflow_id),
        ],
        "final_candidate_ids": [
            str(newer_episode_workflow_id),
            str(older_episode_workflow_id),
        ],
        "candidate_signals": {
            str(newer_episode_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
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
                "latest_episode_created_at": created_at.replace(day=5).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=1).isoformat(),
                "workflow_updated_at": created_at.replace(day=1).isoformat(),
            },
            str(older_episode_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
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
                "latest_episode_created_at": created_at.replace(day=2).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=1).isoformat(),
                "workflow_updated_at": created_at.replace(day=1).isoformat(),
            },
        },
    }


def test_memory_get_context_surfaces_prior_mainline_when_newer_detour_is_deprioritized() -> None:
    prior_mainline_workflow_id = uuid4()
    newer_detour_workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000024"
    created_at = datetime(2024, 7, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=prior_mainline_workflow_id,
            summary="Primary workflow episode",
            metadata={"kind": "primary"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=newer_detour_workflow_id,
            summary="Coverage detour episode",
            metadata={"kind": "coverage"},
            created_at=created_at.replace(day=5),
            updated_at=created_at.replace(day=5),
        )
    )

    class RawOrderLookup:
        def workflow_exists(self, workflow_instance_id: UUID) -> bool:
            return workflow_instance_id in {
                prior_mainline_workflow_id,
                newer_detour_workflow_id,
            }

        def workflow_ids_by_workspace_id(
            self,
            workspace_id_value: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            assert workspace_id_value == workspace_id
            return (
                prior_mainline_workflow_id,
                newer_detour_workflow_id,
            )[:limit]

        def workflow_ids_by_workspace_id_raw_order(
            self,
            workspace_id_value: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            assert workspace_id_value == workspace_id
            return (
                newer_detour_workflow_id,
                prior_mainline_workflow_id,
            )[:limit]

        def workflow_ids_by_ticket_id(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            return ()

        def workflow_ids_by_ticket_id_raw_order(
            self,
            ticket_id: str,
            *,
            limit: int,
        ) -> tuple[UUID, ...]:
            return ()

        def workflow_freshness_by_id(
            self,
            workflow_instance_id: UUID,
        ) -> dict[str, datetime | int | str | bool | None]:
            if workflow_instance_id == prior_mainline_workflow_id:
                return {
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=2),
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "has_latest_attempt": True,
                    "latest_attempt_verify_status": None,
                    "latest_attempt_started_at": created_at.replace(day=2),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=2),
                    "latest_checkpoint_step_name": "resume_primary_flow",
                    "latest_checkpoint_summary": "Continue the main task thread",
                    "latest_checkpoint_current_objective": "Finish the primary workflow slice",
                    "latest_checkpoint_next_intended_action": None,
                    "latest_verify_report_created_at": None,
                }

            return {
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=6),
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "latest_attempt_started_at": created_at.replace(day=6),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=6),
                "latest_checkpoint_step_name": "coverage_followup",
                "latest_checkpoint_summary": "Improve coverage for recent task recall changes",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_verify_report_created_at": None,
            }

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=RawOrderLookup(),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["task_recall_selected_workflow_instance_id"] == str(
        prior_mainline_workflow_id
    )
    assert response.details["task_recall_latest_workflow_instance_id"] == str(
        newer_detour_workflow_id
    )
    assert response.details["task_recall_selected_equals_latest"] is False
    assert response.details["task_recall_latest_ticket_detour_like"] is False
    assert response.details["task_recall_latest_checkpoint_detour_like"] is True
    assert response.details["task_recall_selected_ticket_detour_like"] is False
    assert response.details["task_recall_selected_checkpoint_detour_like"] is False
    assert response.details["task_recall_detour_override_applied"] is True
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert response.details["task_recall_latest_vs_selected_explanations"] == [
        {
            "code": "selected_differs_from_latest",
            "message": "selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_differ",
            "message": "latest considered checkpoint differed from the selected continuation checkpoint",
        },
        {
            "code": "latest_and_selected_detour_classification_differs",
            "message": "latest considered candidate and selected continuation target differed in detour classification",
        },
        {
            "code": "latest_and_selected_return_target_basis_differs",
            "message": "latest considered candidate and selected continuation target differed in return-target basis",
        },
        {
            "code": "latest_and_selected_task_thread_basis_differs",
            "message": "latest considered candidate and selected continuation target differed in task-thread basis",
        },
    ]
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "summary_selected_differs_from_latest",
            "message": "summary comparison recorded that the selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_checkpoints_differ",
            "message": "summary comparison recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
        },
        {
            "code": "summary_latest_and_selected_detour_classification_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in detour classification",
        },
        {
            "code": "summary_latest_and_selected_return_target_basis_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in return-target basis",
        },
        {
            "code": "summary_latest_and_selected_task_thread_basis_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
        },
    ]
    assert response.details["task_recall_return_target_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_return_target_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_prior_mainline_present"] is True
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] == str(
        prior_mainline_workflow_id
    )
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_task_thread_source"] == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == "resume_primary_flow"
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Continue the main task thread"
    )
    assert (
        response.details["task_recall_latest_considered_checkpoint_step_name"]
        == "coverage_followup"
    )
    assert (
        response.details["task_recall_latest_considered_checkpoint_summary"]
        == "Improve coverage for recent task recall changes"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(newer_detour_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(newer_detour_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": None,
            "task_thread_basis": None,
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_flow",
            "checkpoint_summary": "Continue the main task thread",
            "primary_objective_text": "Finish the primary workflow slice",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": False,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(newer_detour_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(newer_detour_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": None,
            "task_thread_basis": None,
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_flow",
            "checkpoint_summary": "Continue the main task thread",
            "primary_objective_text": "Finish the primary workflow slice",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": False,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(newer_detour_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(newer_detour_workflow_id),
            "checkpoint_step_name": "coverage_followup",
            "checkpoint_summary": "Improve coverage for recent task recall changes",
            "primary_objective_text": None,
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": None,
            "task_thread_basis": None,
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_flow",
            "checkpoint_summary": "Continue the main task thread",
            "primary_objective_text": "Finish the primary workflow slice",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": False,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_primary_objective_present"] is True
    assert (
        response.details["task_recall_primary_objective_text"]
        == "Finish the primary workflow slice"
    )

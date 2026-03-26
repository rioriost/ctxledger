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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["hierarchy_applied"] is True
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is False
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
        "workspace",
    ]
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] == str(workflow_id)
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is True
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_enabled"
    assert summary_group["remember_path_summary_relation_reasons"] == []
    assert summary_group["remember_path_summary_relation_reason_primary"] is None
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert summary_group["summaries"][0]["remember_path_explainability"] == {
        "memory_origins": [],
        "promotion_fields": [],
        "promotion_sources": [],
        "relation_reasons": [],
        "relation_reason_primary": None,
        "relation_reasons_frontloaded": False,
        "relation_reason_count": 0,
        "relation_reason_counts": {},
        "relation_origins": [],
    }

    episode_group = response.details["memory_context_groups"][1]
    assert episode_group["scope_id"] == str(episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(workflow_id)
    assert episode_group["parent_group_scope"] == "summary"
    assert episode_group["parent_group_id"] == "summary:episode_summary_first"
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "summary_first"
    assert episode_group["selected_via_summary_first"] is True
    assert episode_group["memory_items"] == [
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
    ]
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []
    assert episode_group["remember_path_memory_items"] == [
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
    assert episode_group["remember_path_memory_summary"] == {
        "memory_origin_counts": {},
        "promotion_field_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    assert episode_group["remember_path_relation_explanations"] == []
    assert episode_group["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }

    workspace_group = response.details["memory_context_groups"][2]
    assert workspace_group["scope_id"] == workspace_id
    assert workspace_group["parent_scope"] is None
    assert workspace_group["parent_scope_id"] is None
    assert workspace_group.get("parent_group_scope") is None
    assert workspace_group.get("parent_group_id") is None
    assert workspace_group["selection_kind"] == "inherited_workspace"
    assert workspace_group["selection_route"] == "workspace_inherited_auxiliary"
    assert workspace_group["memory_items"] == [
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
    assert workspace_group.get("remember_path_memory_items", []) == []
    assert workspace_group.get("remember_path_memory_summary", {}) == {}
    assert workspace_group.get("remember_path_relation_explanations", []) == []
    assert workspace_group.get("remember_path_relation_summary", {}) == {}
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
    ]
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] == str(workflow_id)
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is True
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_enabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]

    episode_group = response.details["memory_context_groups"][1]
    assert episode_group["scope"] == "episode"
    assert episode_group["scope_id"] == str(matching_episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(workflow_id)
    assert episode_group["parent_group_scope"] == "summary"
    assert episode_group["parent_group_id"] == "summary:episode_summary_first"
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "summary_first"
    assert episode_group["selected_via_summary_first"] is True
    assert episode_group["memory_items"] == [
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
    ]
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []
    assert "remember_path_memory_items" in episode_group
    assert "remember_path_memory_summary" in episode_group
    assert "remember_path_relation_explanations" in episode_group
    assert "remember_path_relation_summary" in episode_group
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert len(response.details["memory_context_groups"]) == 1
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] == str(workflow_id)
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is False
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_disabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]
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


def test_memory_get_context_low_limit_query_filter_keeps_summary_first_child_set_when_memory_items_disabled() -> (
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
        summary="Low-limit summary-only surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Low-limit summary-only filtered out by query",
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
        content="Matching low-limit summary-only memory item",
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
        content="Filtered low-limit summary-only memory item",
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
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-FIRST-LIMIT-QUERY-FILTER-SUMMARY-ONLY",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            workflow_instance_id=str(workflow_id),
            limit=1,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Low-limit summary-only surviving query match"
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert len(response.details["memory_context_groups"]) == 1
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] == str(workflow_id)
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is False
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_disabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]
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
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)
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
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
    ]
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] is None
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is True
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_enabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(first_workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]

    episode_group = response.details["memory_context_groups"][1]
    assert episode_group["scope"] == "episode"
    assert episode_group["scope_id"] == str(matching_episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(first_workflow_id)
    assert episode_group["parent_group_scope"] == "summary"
    assert episode_group["parent_group_id"] == "summary:episode_summary_first"
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "summary_first"
    assert episode_group["selected_via_summary_first"] is True
    assert episode_group["memory_items"] == [
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
    ]
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []
    assert "remember_path_memory_items" in episode_group
    assert "remember_path_memory_summary" in episode_group
    assert "remember_path_relation_explanations" in episode_group
    assert "remember_path_relation_summary" in episode_group
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert len(response.details["memory_context_groups"]) == 1
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] is None
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is False
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_disabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(first_workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]
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


def test_memory_get_context_ticket_only_summary_only_low_limit_query_filter_keeps_surviving_child_set() -> (
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
        summary="Ticket-only low-limit summary-only surviving query match",
        metadata={"kind": "matching"},
        created_at=created_at.replace(day=26),
        updated_at=created_at.replace(day=26),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=second_workflow_id,
        summary="Ticket-only low-limit summary-only filtered out by query",
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
        content="Matching ticket-only low-limit summary-only memory item",
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
        content="Filtered ticket-only low-limit summary-only memory item",
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
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY-SUMMARY-ONLY",
                },
                second_workflow_id: {
                    "workspace_id": second_workspace_id,
                    "ticket_id": "TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY-SUMMARY-ONLY",
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="surviving query",
            ticket_id="TICKET-CONTEXT-TICKET-ONLY-MULTI-WORKFLOW-LIMIT-QUERY-SUMMARY-ONLY",
            limit=1,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )

    assert response.details["lookup_scope"] == "ticket"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [
        str(first_workflow_id),
    ]
    assert [episode.summary for episode in response.episodes] == [
        "Ticket-only low-limit summary-only surviving query match",
    ]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 1
    assert response.details["matched_episode_count"] == 1
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert len(response.details["memory_context_groups"]) == 1
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] is None
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is False
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_disabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(first_workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
    ]
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["scope_id"] is None
    assert summary_group["group_id"] == "summary:episode_summary_first"
    assert summary_group["parent_scope"] == "workflow_instance"
    assert summary_group["parent_scope_id"] is None
    assert summary_group["selection_kind"] == "episode_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(matching_episode.episode_id)]
    assert summary_group["child_episode_count"] == 1
    assert summary_group["child_episode_ordering"] == "returned_episode_order"
    assert summary_group["child_episode_groups_emitted"] is True
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_enabled"
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(matching_episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(first_workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 1
    assert summary_group["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert summary_group["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in summary_group["summaries"][0]

    episode_group = response.details["memory_context_groups"][1]
    assert episode_group["scope"] == "episode"
    assert episode_group["scope_id"] == str(matching_episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(first_workflow_id)
    assert episode_group["parent_group_scope"] == "summary"
    assert episode_group["parent_group_id"] == "summary:episode_summary_first"
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "summary_first"
    assert episode_group["selected_via_summary_first"] is True
    assert episode_group["memory_items"] == [
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
    ]
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []
    assert "remember_path_memory_items" in episode_group
    assert "remember_path_memory_summary" in episode_group
    assert "remember_path_relation_explanations" in episode_group
    assert "remember_path_relation_summary" in episode_group
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
    assert len(response.details["memory_context_groups"]) == 1
    workspace_group = response.details["memory_context_groups"][0]
    assert workspace_group["scope"] == "workspace"
    assert workspace_group["scope_id"] == workspace_id
    assert workspace_group["parent_scope"] is None
    assert workspace_group["parent_scope_id"] is None
    assert workspace_group["parent_group_scope"] is None
    assert workspace_group["parent_group_id"] is None
    assert workspace_group["selection_kind"] == "inherited_workspace"
    assert workspace_group["selection_route"] == "workspace_inherited_auxiliary"
    assert workspace_group["memory_items"] == [
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
    assert workspace_group.get("remember_path_memory_items", []) == []
    assert workspace_group.get("remember_path_memory_summary", {}) == {}
    assert workspace_group.get("remember_path_relation_explanations", []) == []
    assert workspace_group.get("remember_path_relation_summary", {}) == {}
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


def test_memory_get_context_limit_truncates_workspace_inherited_auxiliary_output_when_query_filters_out_all_episodes() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000055"
    created_at = datetime(2024, 10, 28, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before low-limit inherited workspace shaping",
        metadata={"kind": "workspace-no-match-low-limit"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    episode_repository.create(episode)

    direct_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct memory item hidden after no-match low-limit shaping",
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
        content="Newer inherited workspace item survives low-limit no-match shaping",
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
        content="Older inherited workspace item hidden by low-limit no-match shaping",
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
                    "ticket_id": "TICKET-CONTEXT-WORKSPACE-NO-MATCH-LIMIT",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="inherited-only token",
            workflow_instance_id=str(workflow_id),
            limit=1,
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
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["hierarchy_applied"] is True
    assert response.details["inherited_context_is_auxiliary"] is True
    assert response.details["inherited_context_returned_without_episode_matches"] is True
    assert (
        response.details["inherited_context_returned_as_auxiliary_without_episode_matches"] is True
    )
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
    assert len(response.details["memory_context_groups"]) == 1
    workspace_group = response.details["memory_context_groups"][0]
    assert workspace_group["scope"] == "workspace"
    assert workspace_group["scope_id"] == workspace_id
    assert workspace_group["parent_scope"] is None
    assert workspace_group["parent_scope_id"] is None
    assert workspace_group["parent_group_scope"] is None
    assert workspace_group["parent_group_id"] is None
    assert workspace_group["selection_kind"] == "inherited_workspace"
    assert workspace_group["selection_route"] == "workspace_inherited_auxiliary"
    assert workspace_group["memory_items"] == [
        {
            "memory_id": str(newer_inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Newer inherited workspace item survives low-limit no-match shaping",
            "metadata": {"kind": "newer-workspace-item"},
            "created_at": newer_inherited_workspace_item.created_at.isoformat(),
            "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
        }
    ]
    assert workspace_group.get("remember_path_memory_items", []) == []
    assert workspace_group.get("remember_path_memory_summary", {}) == {}
    assert workspace_group.get("remember_path_relation_explanations", []) == []
    assert workspace_group.get("remember_path_relation_summary", {}) == {}
    assert response.details["inherited_memory_items"] == [
        {
            "memory_id": str(newer_inherited_workspace_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": None,
            "type": "workspace_note",
            "provenance": "workspace",
            "content": "Newer inherited workspace item survives low-limit no-match shaping",
            "metadata": {"kind": "newer-workspace-item"},
            "created_at": newer_inherited_workspace_item.created_at.isoformat(),
            "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
        }
    ]

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


def test_memory_get_context_group_ordering_is_summary_then_episodes_then_workspace_ticket_only_low_limit() -> (
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
    assert response.details["memory_context_groups"][0]["scope"] == "summary"
    assert response.details["memory_context_groups"][0]["scope_id"] is None
    assert (
        response.details["memory_context_groups"][0]["group_id"] == "summary:episode_summary_first"
    )
    assert response.details["memory_context_groups"][0]["parent_scope"] == "workflow_instance"
    assert response.details["memory_context_groups"][0]["parent_scope_id"] is None
    assert response.details["memory_context_groups"][0]["selection_kind"] == "episode_summary_first"
    assert response.details["memory_context_groups"][0]["selection_route"] == "summary_first"
    assert response.details["memory_context_groups"][0]["child_episode_ids"] == [
        str(first_episode.episode_id),
    ]
    assert response.details["memory_context_groups"][0]["child_episode_count"] == 1
    assert response.details["memory_context_groups"][0]["child_episode_ordering"] == (
        "returned_episode_order"
    )
    assert response.details["memory_context_groups"][0]["child_episode_groups_emitted"] is True
    assert (
        response.details["memory_context_groups"][0]["child_episode_groups_emission_reason"]
        == "memory_items_enabled"
    )
    assert response.details["memory_context_groups"][0]["summaries"] == [
        {
            "episode_id": str(first_episode.episode_id),
            "workflow_instance_id": str(first_workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
            "memory_item_provenance_counts": {
                "episode": 1,
            },
            "interaction_memory_count": 0,
            "interaction_memory_present": False,
            "interaction_roles_present": [],
            "interaction_kinds_present": [],
            "remember_path_explainability": {
                "memory_origins": [],
                "promotion_fields": [],
                "promotion_sources": [],
                "relation_reasons": [],
                "relation_reason_primary": None,
                "relation_reasons_frontloaded": False,
                "relation_reason_count": 0,
                "relation_reason_counts": {},
                "relation_origins": [],
            },
        }
    ]

    assert response.details["memory_context_groups"][1]["scope"] == "episode"
    assert response.details["memory_context_groups"][1]["scope_id"] == str(first_episode.episode_id)
    assert response.details["memory_context_groups"][1]["parent_scope"] == "workflow_instance"
    assert response.details["memory_context_groups"][1]["parent_scope_id"] == str(first_workflow_id)
    assert response.details["memory_context_groups"][1]["parent_group_scope"] == "summary"
    assert (
        response.details["memory_context_groups"][1]["parent_group_id"]
        == "summary:episode_summary_first"
    )
    assert response.details["memory_context_groups"][1]["selection_kind"] == "direct_episode"
    assert response.details["memory_context_groups"][1]["selection_route"] == "summary_first"
    assert response.details["memory_context_groups"][1]["selected_via_summary_first"] is True
    assert response.details["memory_context_groups"][1]["memory_items"] == [
        {
            "memory_id": str(first_memory_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": str(first_episode.episode_id),
            "type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "content": "First ticket-only workflow low-limit memory item",
            "metadata": {"kind": "first"},
            "created_at": first_memory_item.created_at.isoformat(),
            "updated_at": first_memory_item.updated_at.isoformat(),
        }
    ]
    assert response.details["memory_context_groups"][1]["related_memory_items"] == []
    assert response.details["memory_context_groups"][1]["related_memory_item_provenance"] == []
    assert response.details["memory_context_groups"][1]["related_memory_relation_edges"] == []
    assert response.details["memory_context_groups"][1]["remember_path_memory_items"] == [
        {
            "memory_id": str(first_memory_item.memory_id),
            "memory_type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        }
    ]
    assert response.details["memory_context_groups"][1]["remember_path_memory_summary"] == {
        "memory_origin_counts": {},
        "promotion_field_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    assert response.details["memory_context_groups"][1]["remember_path_relation_explanations"] == []
    assert response.details["memory_context_groups"][1]["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }


def test_memory_get_context_group_ordering_is_summary_then_episodes_then_workspace_single_workflow() -> (
    None
):
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
            "episode",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert response.details["memory_context_groups"][0]["scope"] == "summary"
    assert response.details["memory_context_groups"][0]["scope_id"] is None
    assert (
        response.details["memory_context_groups"][0]["group_id"] == "summary:episode_summary_first"
    )
    assert response.details["memory_context_groups"][0]["parent_scope"] == "workflow_instance"
    assert response.details["memory_context_groups"][0]["parent_scope_id"] == str(workflow_id)
    assert response.details["memory_context_groups"][0]["selection_kind"] == "episode_summary_first"
    assert response.details["memory_context_groups"][0]["selection_route"] == "summary_first"
    assert response.details["memory_context_groups"][0]["child_episode_ids"] == [
        str(newer_episode.episode_id),
        str(older_episode.episode_id),
    ]
    assert response.details["memory_context_groups"][0]["child_episode_count"] == 2
    assert response.details["memory_context_groups"][0]["child_episode_ordering"] == (
        "returned_episode_order"
    )
    assert response.details["memory_context_groups"][0]["child_episode_groups_emitted"] is True
    assert (
        response.details["memory_context_groups"][0]["child_episode_groups_emission_reason"]
        == "memory_items_enabled"
    )
    assert response.details["memory_context_groups"][0]["summaries"] == [
        {
            "episode_id": str(newer_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
            "memory_item_provenance_counts": {
                "episode": 1,
            },
            "interaction_memory_count": 0,
            "interaction_memory_present": False,
            "interaction_roles_present": [],
            "interaction_kinds_present": [],
            "remember_path_explainability": {
                "memory_origins": [],
                "promotion_fields": [],
                "promotion_sources": [],
                "relation_reasons": [],
                "relation_reason_primary": None,
                "relation_reasons_frontloaded": False,
                "relation_reason_count": 0,
                "relation_reason_counts": {},
                "relation_origins": [],
            },
        },
        {
            "episode_id": str(older_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
            "memory_item_provenance_counts": {
                "episode": 1,
            },
            "interaction_memory_count": 0,
            "interaction_memory_present": False,
            "interaction_roles_present": [],
            "interaction_kinds_present": [],
            "remember_path_explainability": {
                "memory_origins": [],
                "promotion_fields": [],
                "promotion_sources": [],
                "relation_reasons": [],
                "relation_reason_primary": None,
                "relation_reasons_frontloaded": False,
                "relation_reason_count": 0,
                "relation_reason_counts": {},
                "relation_origins": [],
            },
        },
    ]

    assert response.details["memory_context_groups"][1]["scope"] == "episode"
    assert response.details["memory_context_groups"][1]["scope_id"] == str(newer_episode.episode_id)
    assert response.details["memory_context_groups"][1]["parent_scope"] == "workflow_instance"
    assert response.details["memory_context_groups"][1]["parent_scope_id"] == str(workflow_id)
    assert response.details["memory_context_groups"][1]["parent_group_scope"] == "summary"
    assert (
        response.details["memory_context_groups"][1]["parent_group_id"]
        == "summary:episode_summary_first"
    )
    assert response.details["memory_context_groups"][1]["selection_kind"] == "direct_episode"
    assert response.details["memory_context_groups"][1]["selection_route"] == "summary_first"
    assert response.details["memory_context_groups"][1]["selected_via_summary_first"] is True
    assert response.details["memory_context_groups"][1]["memory_items"] == [
        {
            "memory_id": str(newer_memory_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": str(newer_episode.episode_id),
            "type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "content": "Newer grouped-order memory item",
            "metadata": {"kind": "newer"},
            "created_at": newer_memory_item.created_at.isoformat(),
            "updated_at": newer_memory_item.updated_at.isoformat(),
        }
    ]
    assert response.details["memory_context_groups"][1]["related_memory_items"] == []
    assert response.details["memory_context_groups"][1]["related_memory_item_provenance"] == []
    assert response.details["memory_context_groups"][1]["related_memory_relation_edges"] == []
    assert response.details["memory_context_groups"][1]["remember_path_memory_items"] == [
        {
            "memory_id": str(newer_memory_item.memory_id),
            "memory_type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        }
    ]
    assert response.details["memory_context_groups"][1]["remember_path_memory_summary"] == {
        "memory_origin_counts": {},
        "promotion_field_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    assert response.details["memory_context_groups"][1]["remember_path_relation_explanations"] == []
    assert response.details["memory_context_groups"][1]["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }

    assert response.details["memory_context_groups"][2]["scope"] == "episode"
    assert response.details["memory_context_groups"][2]["scope_id"] == str(older_episode.episode_id)
    assert response.details["memory_context_groups"][2]["parent_scope"] == "workflow_instance"
    assert response.details["memory_context_groups"][2]["parent_scope_id"] == str(workflow_id)
    assert response.details["memory_context_groups"][2]["parent_group_scope"] == "summary"
    assert (
        response.details["memory_context_groups"][2]["parent_group_id"]
        == "summary:episode_summary_first"
    )
    assert response.details["memory_context_groups"][2]["selection_kind"] == "direct_episode"
    assert response.details["memory_context_groups"][2]["selection_route"] == "summary_first"
    assert response.details["memory_context_groups"][2]["selected_via_summary_first"] is True
    assert response.details["memory_context_groups"][2]["memory_items"] == [
        {
            "memory_id": str(older_memory_item.memory_id),
            "workspace_id": workspace_id,
            "episode_id": str(older_episode.episode_id),
            "type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "content": "Older grouped-order memory item",
            "metadata": {"kind": "older"},
            "created_at": older_memory_item.created_at.isoformat(),
            "updated_at": older_memory_item.updated_at.isoformat(),
        }
    ]
    assert response.details["memory_context_groups"][2]["related_memory_items"] == []
    assert response.details["memory_context_groups"][2]["related_memory_item_provenance"] == []
    assert response.details["memory_context_groups"][2]["related_memory_relation_edges"] == []
    assert response.details["memory_context_groups"][2]["remember_path_memory_items"] == [
        {
            "memory_id": str(older_memory_item.memory_id),
            "memory_type": "episode_note",
            "provenance": "episode",
            "provenance_kind": "episode_memory",
            "interaction_role": None,
            "interaction_kind": None,
            "file_name": None,
            "file_path": None,
            "file_operation": None,
            "purpose": None,
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        }
    ]
    assert response.details["memory_context_groups"][2]["remember_path_memory_summary"] == {
        "memory_origin_counts": {},
        "promotion_field_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
    }
    assert response.details["memory_context_groups"][2]["remember_path_relation_explanations"] == []
    assert response.details["memory_context_groups"][2]["remember_path_relation_summary"] == {
        "relation_reason_counts": {},
        "checkpoint_origin_present": False,
        "completion_origin_present": False,
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
            "episode",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
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
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [
            "summary",
        ],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
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
    assert summary_group["child_episode_groups_emitted"] is False
    assert summary_group["child_episode_groups_emission_reason"] == "memory_items_disabled"
    assert "remember_path_summary_relation_reasons" not in summary_group
    assert "remember_path_summary_relation_reason_primary" not in summary_group
    assert len(summary_group["summaries"]) == 1
    assert summary_group["summaries"][0]["episode_id"] == str(episode.episode_id)
    assert summary_group["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert summary_group["summaries"][0]["memory_item_count"] == 2
    assert summary_group["summaries"][0]["memory_item_types"] == [
        "checkpoint_note",
        "episode_note",
    ]
    assert summary_group["summaries"][0]["memory_item_provenance"] == [
        "checkpoint",
        "episode",
    ]
    assert summary_group["summaries"][0]["remember_path_explainability"] == {}


def test_memory_get_context_summary_only_group_frontloads_relation_reason_explainability() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000145")
    created_at = datetime(2024, 10, 25, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Summary-first relation reason emphasis coverage",
        metadata={"kind": "summary-relation-reason"},
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    objective_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_objective",
        provenance="workflow_checkpoint_auto",
        content="Objective member for summary-first relation reason emphasis",
        metadata={
            "memory_origin": "workflow_checkpoint_auto",
            "promotion_field": "current_objective",
            "promotion_source": "checkpoint.current_objective",
        },
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    next_action_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_next_action",
        provenance="workflow_checkpoint_auto",
        content="Next action member for summary-first relation reason emphasis",
        metadata={
            "memory_origin": "workflow_checkpoint_auto",
            "promotion_field": "next_intended_action",
            "promotion_source": "checkpoint.next_intended_action",
        },
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(objective_memory_item)
    memory_item_repository.create(next_action_memory_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=next_action_memory_item.memory_id,
            target_memory_id=objective_memory_item.memory_id,
            relation_type="supports",
            metadata={
                "memory_origin": "workflow_checkpoint_auto",
                "relation_reason": "next_action_supports_objective",
                "relation_description": "next intended action supports the current objective",
                "source_memory_type": "workflow_next_action",
                "target_memory_type": "workflow_objective",
            },
            created_at=created_at.replace(hour=3),
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

    assert response.details["memory_context_groups"][0]["scope"] == "summary"
    assert response.details["memory_context_groups"][0][
        "remember_path_summary_relation_reasons"
    ] == [
        "next_action_supports_objective",
    ]
    assert (
        response.details["memory_context_groups"][0][
            "remember_path_summary_relation_reason_primary"
        ]
        == "next_action_supports_objective"
    )
    assert response.details["memory_context_groups"][0]["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 2,
            "memory_item_types": [
                "workflow_next_action",
                "workflow_objective",
            ],
            "memory_item_provenance": [
                "workflow_checkpoint_auto",
                "workflow_checkpoint_auto",
            ],
            "memory_item_provenance_counts": {
                "workflow_checkpoint_auto": 2,
            },
            "interaction_memory_count": 0,
            "interaction_memory_present": False,
            "interaction_roles_present": [],
            "interaction_kinds_present": [],
            "remember_path_explainability": {
                "memory_origins": [
                    "workflow_checkpoint_auto",
                ],
                "promotion_fields": [
                    "current_objective",
                    "next_intended_action",
                ],
                "promotion_sources": [
                    "checkpoint.current_objective",
                    "checkpoint.next_intended_action",
                ],
                "relation_reasons": [
                    "next_action_supports_objective",
                ],
                "relation_reason_primary": "next_action_supports_objective",
                "relation_reasons_frontloaded": True,
                "relation_reason_count": 1,
                "relation_reason_counts": {
                    "next_action_supports_objective": 1,
                },
                "relation_origins": [
                    "workflow_checkpoint_auto",
                ],
            },
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
    assert response.details["retrieval_route_scopes_present"] == {
        "summary_first": [],
        "episode_direct": [],
        "workspace_inherited_auxiliary": [
            "workspace",
        ],
        "relation_supports_auxiliary": [],
        "graph_summary_auxiliary": [],
    }
    assert [group["scope"] for group in response.details["memory_context_groups"]] == ["workspace"]
    assert [group["selection_route"] for group in response.details["memory_context_groups"]] == [
        "workspace_inherited_auxiliary"
    ]
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
                    "provenance_kind": "other",
                    "interaction_role": None,
                    "interaction_kind": None,
                    "file_name": None,
                    "file_path": None,
                    "file_operation": None,
                    "purpose": None,
                    "content": "Workspace-only ordering token",
                    "metadata": {"kind": "workspace-only"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]

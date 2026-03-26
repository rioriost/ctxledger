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
            "remember_path_explainability": {},
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
                    "remember_path_explainability": {},
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
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
        "graph_summary_auxiliary": {
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
        "graph_summary_auxiliary": [],
    }
    assert len(response.details["memory_context_groups"]) == 1
    episode_group = response.details["memory_context_groups"][0]
    assert episode_group["scope"] == "episode"
    assert episode_group["scope_id"] == str(episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(workflow_id)
    assert episode_group["parent_group_scope"] is None
    assert episode_group["parent_group_id"] is None
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "episode_direct"
    assert episode_group["selected_via_summary_first"] is False
    assert episode_group["memory_items"] == [
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
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []
    assert episode_group["remember_path_memory_items"] == [
        {
            "memory_id": str(second_memory_item.memory_id),
            "memory_type": "checkpoint_note",
            "provenance": "checkpoint",
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        },
        {
            "memory_id": str(first_memory_item.memory_id),
            "memory_type": "episode_note",
            "provenance": "episode",
            "memory_origin": None,
            "promotion_field": None,
            "promotion_source": None,
            "checkpoint_id": None,
            "step_name": None,
            "workflow_status": None,
            "attempt_status": None,
        },
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
    assert len(response.details["summaries"]) == 1
    assert response.details["summaries"][0]["episode_id"] == str(episode.episode_id)
    assert response.details["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert response.details["summaries"][0]["memory_item_count"] == 1
    assert response.details["summaries"][0]["memory_item_types"] == ["episode_note"]
    assert response.details["summaries"][0]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in response.details["summaries"][0]
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
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 1,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
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
        "relation_origins": [],
    }

    episode_group = response.details["memory_context_groups"][1]
    assert episode_group["scope"] == "episode"
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
            "content": "Direct episode memory",
            "metadata": {"kind": "direct"},
            "created_at": direct_memory_item.created_at.isoformat(),
            "updated_at": direct_memory_item.updated_at.isoformat(),
        }
    ]
    assert episode_group["related_memory_items"] == []
    assert episode_group["related_memory_item_provenance"] == []
    assert episode_group["related_memory_relation_edges"] == []

    workspace_group = response.details["memory_context_groups"][2]
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
            "content": "Inherited workspace memory",
            "metadata": {"kind": "inherited"},
            "created_at": inherited_workspace_item.created_at.isoformat(),
            "updated_at": inherited_workspace_item.updated_at.isoformat(),
        }
    ]
    assert [group["scope"] for group in response.details["memory_context_groups"]] == [
        "summary",
        "episode",
        "workspace",
    ]
    assert [group["selection_route"] for group in response.details["memory_context_groups"]] == [
        "summary_first",
        "summary_first",
        "workspace_inherited_auxiliary",
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
            "remember_path_explainability": {},
        }
    ]
    assert response.details["hierarchy_applied"] is False
    assert len(response.details["memory_context_groups"]) == 1
    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
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
    assert summary_group["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
            "remember_path_explainability": {},
        }
    ]
    assert [group["scope"] for group in response.details["memory_context_groups"]] == ["summary"]
    assert [group["selection_route"] for group in response.details["memory_context_groups"]] == [
        "summary_first"
    ]
    assert response.details["inherited_memory_items"] == []


def test_memory_get_context_omits_memory_items_and_summaries_when_disabled() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000032"
    created_at = datetime(2024, 10, 5, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with hidden detail paths",
        metadata={"kind": "hidden-details"},
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
            content="Stored episode detail",
            metadata={"kind": "note"},
            created_at=created_at.replace(hour=1),
            updated_at=created_at.replace(hour=1),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-HIDDEN-DETAILS",
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
        "Episode with hidden detail paths"
    ]
    assert response.details["memory_items"] == []
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 1}
    assert response.details["summaries"] == []

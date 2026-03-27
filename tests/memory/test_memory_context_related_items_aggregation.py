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


def test_memory_get_context_aggregates_supports_relation_auxiliary_group_across_multiple_sources() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000053")
    created_at = datetime(2024, 10, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode with supports source",
        metadata={"kind": "supports-source-first"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode with supports source",
        metadata={"kind": "supports-source-second"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First source memory item",
        metadata={"kind": "first-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second source memory item",
        metadata={"kind": "second-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    shared_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Shared supporting workspace memory item",
        metadata={"kind": "shared-support"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    first_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First-seen supporting workspace memory item",
        metadata={"kind": "first-seen-support"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    later_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Later-seen supporting workspace memory item",
        metadata={"kind": "later-seen-support"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )

    memory_item_repository.create(first_source_memory_item)
    memory_item_repository.create(second_source_memory_item)
    memory_item_repository.create(shared_supports_target_item)
    memory_item_repository.create(first_seen_supports_target_item)
    memory_item_repository.create(later_seen_supports_target_item)
    memory_item_repository.create(workspace_root_item)

    first_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=first_source_memory_item.memory_id,
        target_memory_id=shared_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "first-supports-edge"},
        created_at=created_at.replace(hour=5),
    )
    second_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=second_source_memory_item.memory_id,
        target_memory_id=shared_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "second-supports-edge"},
        created_at=created_at.replace(hour=6),
    )
    third_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=first_source_memory_item.memory_id,
        target_memory_id=first_seen_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "third-supports-edge"},
        created_at=created_at.replace(hour=7),
    )
    fourth_support_relation = MemoryRelationRecord(
        memory_relation_id=uuid4(),
        source_memory_id=second_source_memory_item.memory_id,
        target_memory_id=later_seen_supports_target_item.memory_id,
        relation_type="supports",
        metadata={"kind": "fourth-supports-edge"},
        created_at=created_at.replace(hour=8),
    )
    memory_relation_repository.create(first_support_relation)
    memory_relation_repository.create(second_support_relation)
    memory_relation_repository.create(third_support_relation)
    memory_relation_repository.create(fourth_support_relation)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_relation_repository=memory_relation_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-MULTI-SOURCE",
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
        "Second episode with supports source",
        "First episode with supports source",
    ]
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 2
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 2,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 4,
        "relation_supports_auxiliary": 3,
        "graph_summary_auxiliary": 0,
    }
    relation_group = response.details["memory_context_groups"][3]
    assert relation_group["scope"] == "relation"
    assert relation_group["scope_id"] == "supports"
    assert relation_group["group_id"] == "relation:supports_auxiliary"
    assert relation_group["parent_scope"] == "workflow_instance"
    assert relation_group["parent_scope_id"] == str(workflow_id)
    assert relation_group["parent_group_scope"] is None
    assert relation_group["parent_group_id"] is None
    assert relation_group["selection_kind"] == "supports_related_auxiliary"
    assert relation_group["selection_route"] == "relation_supports_auxiliary"
    assert relation_group["relation_type"] == "supports"
    assert relation_group["source_episode_ids"] == sorted(
        [
            str(first_episode.episode_id),
            str(second_episode.episode_id),
        ]
    )
    assert relation_group["source_memory_ids"] == sorted(
        [
            str(first_source_memory_item.memory_id),
            str(second_source_memory_item.memory_id),
        ]
    )
    assert relation_group["memory_items"] == [
        {
            "memory_id": str(later_seen_supports_target_item.memory_id),
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
            "content": "Later-seen supporting workspace memory item",
            "metadata": {"kind": "later-seen-support"},
            "created_at": later_seen_supports_target_item.created_at.isoformat(),
            "updated_at": later_seen_supports_target_item.updated_at.isoformat(),
        },
        {
            "memory_id": str(shared_supports_target_item.memory_id),
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
            "content": "Shared supporting workspace memory item",
            "metadata": {"kind": "shared-support"},
            "created_at": shared_supports_target_item.created_at.isoformat(),
            "updated_at": shared_supports_target_item.updated_at.isoformat(),
        },
        {
            "memory_id": str(first_seen_supports_target_item.memory_id),
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
            "content": "First-seen supporting workspace memory item",
            "metadata": {"kind": "first-seen-support"},
            "created_at": first_seen_supports_target_item.created_at.isoformat(),
            "updated_at": first_seen_supports_target_item.updated_at.isoformat(),
        },
    ]
    assert len(relation_group["remember_path_relation_explanations"]) == 4
    assert relation_group["remember_path_relation_explanations"][0] == {
        "memory_relation_id": str(fourth_support_relation.memory_relation_id),
        "relation_type": "supports",
        "relation_reason": None,
        "relation_description": None,
        "memory_origin": None,
        "source_memory_type": None,
        "target_memory_type": None,
        "source_memory_id": str(fourth_support_relation.source_memory_id),
        "target_memory_id": str(fourth_support_relation.target_memory_id),
    }
    assert relation_group["remember_path_relation_explanations"][1] == {
        "memory_relation_id": str(second_support_relation.memory_relation_id),
        "relation_type": "supports",
        "relation_reason": None,
        "relation_description": None,
        "memory_origin": None,
        "source_memory_type": None,
        "target_memory_type": None,
        "source_memory_id": str(second_support_relation.source_memory_id),
        "target_memory_id": str(second_support_relation.target_memory_id),
    }
    assert {
        (
            explanation["memory_relation_id"],
            explanation["source_memory_id"],
            explanation["target_memory_id"],
        )
        for explanation in relation_group["remember_path_relation_explanations"][2:]
    } == {
        (
            str(first_support_relation.memory_relation_id),
            str(first_support_relation.source_memory_id),
            str(first_support_relation.target_memory_id),
        ),
        (
            str(third_support_relation.memory_relation_id),
            str(third_support_relation.source_memory_id),
            str(third_support_relation.target_memory_id),
        ),
    }
    assert all(
        explanation["relation_type"] == "supports"
        and explanation["relation_reason"] is None
        and explanation["relation_description"] is None
        and explanation["memory_origin"] is None
        and explanation["source_memory_type"] is None
        and explanation["target_memory_type"] is None
        for explanation in relation_group["remember_path_relation_explanations"][2:]
    )
    relation_summary = relation_group["remember_path_relation_summary"]
    assert relation_summary.get("relation_reasons", []) == []
    assert relation_summary.get("relation_reason_primary") is None
    assert relation_summary["relation_reason_counts"] == {}
    assert relation_summary["checkpoint_origin_present"] is False
    assert relation_summary["completion_origin_present"] is False


def test_memory_get_context_supports_target_lookup_boundary_preserves_relation_auxiliary_parity() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000059")
    created_at = datetime(2024, 10, 26, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode for supports lookup parity",
        metadata={"kind": "supports-parity-first"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode for supports lookup parity",
        metadata={"kind": "supports-parity-second"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First parity source memory item",
        metadata={"kind": "supports-parity-first-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second parity source memory item",
        metadata={"kind": "supports-parity-second-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    latest_support_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Latest parity supporting target",
        metadata={"kind": "supports-parity-latest"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    shared_support_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Shared parity supporting target",
        metadata={"kind": "supports-parity-shared"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    earlier_support_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Earlier parity supporting target",
        metadata={"kind": "supports-parity-earlier"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )

    memory_item_repository.create(first_source_memory_item)
    memory_item_repository.create(second_source_memory_item)
    memory_item_repository.create(latest_support_target_item)
    memory_item_repository.create(shared_support_target_item)
    memory_item_repository.create(earlier_support_target_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=shared_support_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-parity-shared-first"},
            created_at=created_at.replace(hour=5),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=shared_support_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-parity-shared-second"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=earlier_support_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-parity-earlier"},
            created_at=created_at.replace(hour=7),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=latest_support_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "supports-parity-latest"},
            created_at=created_at.replace(hour=8),
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
                    "ticket_id": "TICKET-CONTEXT-SUPPORTS-LOOKUP-PARITY",
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

    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 2
    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 3,
        "relation_supports_auxiliary": 3,
        "graph_summary_auxiliary": 0,
    }
    assert response.details["memory_context_groups"][3]["memory_items"] == [
        {
            "memory_id": str(latest_support_target_item.memory_id),
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
            "content": "Latest parity supporting target",
            "metadata": {"kind": "supports-parity-latest"},
            "created_at": latest_support_target_item.created_at.isoformat(),
            "updated_at": latest_support_target_item.updated_at.isoformat(),
        },
        {
            "memory_id": str(shared_support_target_item.memory_id),
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
            "content": "Shared parity supporting target",
            "metadata": {"kind": "supports-parity-shared"},
            "created_at": shared_support_target_item.created_at.isoformat(),
            "updated_at": shared_support_target_item.updated_at.isoformat(),
        },
        {
            "memory_id": str(earlier_support_target_item.memory_id),
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
            "content": "Earlier parity supporting target",
            "metadata": {"kind": "supports-parity-earlier"},
            "created_at": earlier_support_target_item.created_at.isoformat(),
            "updated_at": earlier_support_target_item.updated_at.isoformat(),
        },
    ]


def test_memory_get_context_limit_truncates_constrained_relation_aggregation_after_distinct_first_seen_targets() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000054")
    created_at = datetime(2024, 10, 21, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_relation_repository = InMemoryMemoryRelationRepository()

    first_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="First episode for low-limit supports aggregation",
        metadata={"kind": "low-limit-first"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Second episode for low-limit supports aggregation",
        metadata={"kind": "low-limit-second"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(first_episode)
    episode_repository.create(second_episode)

    first_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=first_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First low-limit source memory item",
        metadata={"kind": "low-limit-first-source"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_source_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=second_episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second low-limit source memory item",
        metadata={"kind": "low-limit-second-source"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    later_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Later-seen low-limit supporting target",
        metadata={"kind": "low-limit-later-seen"},
        created_at=created_at.replace(hour=0, minute=10),
        updated_at=created_at.replace(hour=0, minute=10),
    )
    shared_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Shared low-limit supporting target",
        metadata={"kind": "low-limit-shared"},
        created_at=created_at.replace(hour=0, minute=20),
        updated_at=created_at.replace(hour=0, minute=20),
    )
    first_seen_supports_target_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="First-seen low-limit supporting target",
        metadata={"kind": "low-limit-first-seen"},
        created_at=created_at.replace(hour=0, minute=30),
        updated_at=created_at.replace(hour=0, minute=30),
    )
    workspace_root_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace root memory item",
        metadata={"kind": "workspace-root"},
        created_at=created_at.replace(hour=0, minute=40),
        updated_at=created_at.replace(hour=0, minute=40),
    )

    memory_item_repository.create(first_source_memory_item)
    memory_item_repository.create(second_source_memory_item)
    memory_item_repository.create(later_seen_supports_target_item)
    memory_item_repository.create(shared_supports_target_item)
    memory_item_repository.create(first_seen_supports_target_item)
    memory_item_repository.create(workspace_root_item)

    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=later_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-first-edge"},
            created_at=created_at.replace(hour=5),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=second_source_memory_item.memory_id,
            target_memory_id=shared_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-second-edge"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=shared_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-third-edge"},
            created_at=created_at.replace(hour=7),
        )
    )
    memory_relation_repository.create(
        MemoryRelationRecord(
            memory_relation_id=uuid4(),
            source_memory_id=first_source_memory_item.memory_id,
            target_memory_id=first_seen_supports_target_item.memory_id,
            relation_type="supports",
            metadata={"kind": "low-limit-fourth-edge"},
            created_at=created_at.replace(hour=8),
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
                    "ticket_id": "TICKET-CONTEXT-RELATED-ITEMS-LIMIT",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=2,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Second episode for low-limit supports aggregation",
        "First episode for low-limit supports aggregation",
    ]
    assert response.details["related_context_is_auxiliary"] is True
    assert response.details["related_context_relation_types"] == ["supports"]
    assert response.details["related_context_selection_route"] == ("relation_supports_auxiliary")
    assert response.details["relation_supports_source_episode_count"] == 2
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
        "workspace_inherited_auxiliary",
        "relation_supports_auxiliary",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 1,
        "relation_supports_auxiliary": 2,
        "graph_summary_auxiliary": 0,
    }

    assert response.details["retrieval_route_item_counts"] == {
        "summary_first": 0,
        "episode_direct": 2,
        "workspace_inherited_auxiliary": 2,
        "relation_supports_auxiliary": 2,
        "graph_summary_auxiliary": 0,
    }

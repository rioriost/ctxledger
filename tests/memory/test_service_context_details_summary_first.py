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


def test_memory_get_context_include_summaries_false_suppresses_canonical_summary_first_path() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000102")
    created_at = datetime(2024, 10, 8, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Canonical summary exists but include_summaries is false",
        metadata={"kind": "suppressed-summary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Direct memory item should remain on the episode path",
        metadata={"kind": "episode-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    memory_item_repository.create(memory_item)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="This canonical summary should be ignored when summaries are disabled",
        summary_kind="episode_summary",
        metadata={"kind": "canonical-summary"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_summary_repository.create(summary)
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=memory_item.memory_id,
            membership_order=1,
            metadata={"kind": "membership"},
            created_at=created_at.replace(hour=5),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-SUMMARIES-DISABLED",
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

    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert response.details["retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["primary_retrieval_routes_present"] == [
        "episode_direct",
    ]
    assert response.details["retrieval_route_group_counts"] == {
        "summary_first": 0,
        "episode_direct": 1,
        "workspace_inherited_auxiliary": 0,
        "relation_supports_auxiliary": 0,
        "graph_summary_auxiliary": 0,
    }
    assert len(response.details["memory_context_groups"]) == 1
    episode_group = response.details["memory_context_groups"][0]
    assert episode_group["scope"] == "episode"
    assert episode_group["scope_id"] == str(episode.episode_id)
    assert episode_group["parent_scope"] == "workflow_instance"
    assert episode_group["parent_scope_id"] == str(workflow_id)
    assert episode_group["selection_kind"] == "direct_episode"
    assert episode_group["selection_route"] == "episode_direct"
    assert episode_group["memory_items"] == [
        {
            "memory_id": str(memory_item.memory_id),
            "workspace_id": str(workspace_id),
            "episode_id": str(episode.episode_id),
            "type": "episode_note",
            "provenance": "episode",
            "content": "Direct memory item should remain on the episode path",
            "metadata": {"kind": "episode-note"},
            "created_at": memory_item.created_at.isoformat(),
            "updated_at": memory_item.updated_at.isoformat(),
        }
    ]


def test_memory_get_context_include_episodes_false_keeps_canonical_summary_path_narrowed() -> None:
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000103"
    created_at = datetime(2024, 10, 9, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Canonical summary exists but episode-less shaping stays narrow",
        metadata={"kind": "episode-less"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    episode_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Episode child item should stay hidden in episode-less shaping",
        metadata={"kind": "episode-note"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Workspace item remains the only visible grouped output",
        metadata={"kind": "workspace-item"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(episode_memory_item)
    memory_item_repository.create(inherited_workspace_item)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=episode.episode_id,
        summary_text="Canonical summary should not surface in episode-less mode",
        summary_kind="episode_summary",
        metadata={"kind": "canonical-summary"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_summary_repository.create(summary)
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=episode_memory_item.memory_id,
            membership_order=1,
            metadata={"kind": "membership"},
            created_at=created_at.replace(hour=5),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-EPISODE-LESS-CANONICAL-SUMMARY",
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
            include_summaries=True,
        )
    )

    assert response.episodes == ()
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None
    assert "summary_first_has_episode_groups" not in response.details
    assert "summary_first_is_summary_only" not in response.details
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
                    "content": "Workspace item remains the only visible grouped output",
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


def test_memory_get_context_summary_first_orders_multiple_canonical_summaries_by_created_at_desc() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000104")
    created_at = datetime(2024, 10, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with multiple canonical summaries",
        metadata={"kind": "multi-summary"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    older_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Older summary member item",
        metadata={"rank": "older"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    newer_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Newer summary member item",
        metadata={"rank": "newer"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_item_repository.create(older_memory_item)
    memory_item_repository.create(newer_memory_item)

    older_summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Older canonical summary",
        summary_kind="episode_summary",
        metadata={"kind": "older-summary"},
        created_at=created_at.replace(hour=5),
        updated_at=created_at.replace(hour=5),
    )
    newer_summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Newer canonical summary",
        summary_kind="episode_summary",
        metadata={"kind": "newer-summary"},
        created_at=created_at.replace(hour=6),
        updated_at=created_at.replace(hour=6),
    )
    memory_summary_repository.create(older_summary)
    memory_summary_repository.create(newer_summary)

    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=older_summary.memory_summary_id,
            memory_id=older_memory_item.memory_id,
            membership_order=1,
            metadata={"kind": "older-membership"},
            created_at=created_at.replace(hour=7),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=newer_summary.memory_summary_id,
            memory_id=newer_memory_item.memory_id,
            membership_order=1,
            metadata={"kind": "newer-membership"},
            created_at=created_at.replace(hour=8),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-MULTI-SUMMARY-ORDERING",
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
    assert response.details["summary_selection_kind"] == "memory_summary_first"
    assert [summary["memory_summary_id"] for summary in response.details["summaries"]] == [
        str(newer_summary.memory_summary_id),
        str(older_summary.memory_summary_id),
    ]
    assert response.details["summaries"][0]["summary_text"] == "Newer canonical summary"
    assert response.details["summaries"][1]["summary_text"] == "Older canonical summary"
    assert response.details["retrieval_route_item_counts"]["summary_first"] == 2
    assert response.details["memory_context_groups"][0]["selection_kind"] == "memory_summary_first"
    assert [
        summary["memory_summary_id"]
        for summary in response.details["memory_context_groups"][0]["summaries"]
    ] == [
        str(newer_summary.memory_summary_id),
        str(older_summary.memory_summary_id),
    ]


def test_memory_get_context_summary_first_preserves_membership_order_when_expanding_member_items() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000105")
    created_at = datetime(2024, 10, 11, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with ordered canonical membership",
        metadata={"kind": "membership-order"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Membership order first item",
        metadata={"position": 1},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Membership order second item",
        metadata={"position": 2},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Canonical summary with ordered membership",
        summary_kind="episode_summary",
        metadata={"kind": "ordered-summary"},
        created_at=created_at.replace(hour=5),
        updated_at=created_at.replace(hour=5),
    )
    memory_summary_repository.create(summary)

    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=second_memory_item.memory_id,
            membership_order=1,
            metadata={"kind": "first-membership"},
            created_at=created_at.replace(hour=6),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=first_memory_item.memory_id,
            membership_order=2,
            metadata={"kind": "second-membership"},
            created_at=created_at.replace(hour=7),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-MEMBERSHIP-ORDER",
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

    assert response.details["summary_selection_kind"] == "memory_summary_first"
    assert response.details["summaries"] == [
        {
            "memory_summary_id": str(summary.memory_summary_id),
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical summary with ordered membership",
            "summary_kind": "episode_summary",
            "metadata": {"kind": "ordered-summary"},
            "member_memory_count": 2,
            "member_memory_ids": [
                str(second_memory_item.memory_id),
                str(first_memory_item.memory_id),
            ],
            "member_memory_items": [
                {
                    "memory_id": str(second_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Membership order second item",
                    "metadata": {"position": 2},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "Membership order first item",
                    "metadata": {"position": 1},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                },
            ],
        }
    ]


def test_memory_get_context_summary_first_handles_empty_membership_without_falling_back() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000106")
    created_at = datetime(2024, 10, 12, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with canonical summary but no members",
        metadata={"kind": "empty-membership"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    episode_repository.create(episode)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Canonical summary with empty membership",
        summary_kind="episode_summary",
        metadata={"kind": "empty-summary"},
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    memory_summary_repository.create(summary)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                    "ticket_id": "TICKET-CONTEXT-EMPTY-MEMBERSHIP",
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
    assert response.details["summary_selection_kind"] == "memory_summary_first"
    assert response.details["summaries"] == [
        {
            "memory_summary_id": str(summary.memory_summary_id),
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical summary with empty membership",
            "summary_kind": "episode_summary",
            "metadata": {"kind": "empty-summary"},
            "member_memory_count": 0,
            "member_memory_ids": [],
            "member_memory_items": [],
        }
    ]
    assert response.details["retrieval_route_item_counts"]["summary_first"] == 1
    assert response.details["memory_context_groups"][0]["selection_kind"] == "memory_summary_first"
    assert response.details["memory_context_groups"][0]["summaries"] == [
        {
            "memory_summary_id": str(summary.memory_summary_id),
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical summary with empty membership",
            "summary_kind": "episode_summary",
            "metadata": {"kind": "empty-summary"},
            "member_memory_count": 0,
            "member_memory_ids": [],
            "member_memory_items": [],
        }
    ]


def test_memory_get_context_summary_only_primary_path_differs_from_all_filtered_auxiliary_only_path() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000034"
    created_at = datetime(2024, 10, 7, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Summary-only surviving primary path episode",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out by current query",
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
        content="Matching episode memory item for summary-only primary shaping",
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
        content="Filtered episode memory item for auxiliary-only no-match shaping",
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
        content="Inherited workspace item visible in the auxiliary-only no-match path",
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
                    "ticket_id": "TICKET-CONTEXT-SUMMARY-ONLY-VS-AUXILIARY-ONLY-NO-MATCH",
                }
            }
        ),
    )

    summary_only_response = service.get_context(
        GetMemoryContextRequest(
            query="surviving primary path",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=True,
        )
    )
    auxiliary_only_no_match_response = service.get_context(
        GetMemoryContextRequest(
            query="no such surviving episode text",
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert [episode.summary for episode in summary_only_response.episodes] == [
        "Summary-only surviving primary path episode"
    ]
    assert summary_only_response.details["query_filter_applied"] is True
    assert summary_only_response.details["all_episodes_filtered_out_by_query"] is False
    assert summary_only_response.details["summary_selection_applied"] is True
    assert summary_only_response.details["summary_selection_kind"] == "episode_summary_first"
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
    assert summary_only_response.details["retrieval_routes_present"] == [
        "summary_first",
    ]
    assert summary_only_response.details["primary_retrieval_routes_present"] == [
        "summary_first",
    ]
    assert summary_only_response.details["auxiliary_retrieval_routes_present"] == []
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
                }
            ],
        }
    ]

    assert auxiliary_only_no_match_response.episodes == ()
    assert auxiliary_only_no_match_response.details["query_filter_applied"] is True
    assert auxiliary_only_no_match_response.details["all_episodes_filtered_out_by_query"] is True
    assert auxiliary_only_no_match_response.details["summary_selection_applied"] is False
    assert auxiliary_only_no_match_response.details["summary_selection_kind"] is None
    assert auxiliary_only_no_match_response.details["summary_first_has_episode_groups"] is False
    assert auxiliary_only_no_match_response.details["summary_first_is_summary_only"] is False
    assert auxiliary_only_no_match_response.details["summary_first_child_episode_count"] == 0
    assert auxiliary_only_no_match_response.details["summary_first_child_episode_ids"] == []
    assert (
        auxiliary_only_no_match_response.details[
            "primary_episode_groups_present_after_query_filter"
        ]
        is False
    )
    assert auxiliary_only_no_match_response.details["auxiliary_only_after_query_filter"] is True
    assert auxiliary_only_no_match_response.details["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert auxiliary_only_no_match_response.details["primary_retrieval_routes_present"] == []
    assert auxiliary_only_no_match_response.details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert auxiliary_only_no_match_response.details["memory_context_groups"] == [
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
                    "content": "Inherited workspace item visible in the auxiliary-only no-match path",
                    "metadata": {"kind": "workspace-item"},
                    "created_at": inherited_workspace_item.created_at.isoformat(),
                    "updated_at": inherited_workspace_item.updated_at.isoformat(),
                }
            ],
        }
    ]


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


def test_memory_get_context_include_episodes_false_low_limit_query_keeps_response_episode_less() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = "00000000-0000-0000-0000-000000000033"
    created_at = datetime(2024, 10, 6, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()

    matching_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode hidden by include_episodes false low-limit query shaping",
        metadata={"kind": "matching"},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    filtered_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode filtered out before episode-less low-limit shaping",
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
        content="Matching direct memory item that should stay hidden under low limit",
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
        content="Filtered direct memory item that should stay hidden under low limit",
        metadata={"kind": "filtered-note"},
        created_at=created_at.replace(hour=4),
        updated_at=created_at.replace(hour=4),
    )
    newer_inherited_workspace_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=UUID(workspace_id),
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="Newer inherited workspace item still visible with include_episodes false low limit",
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
        content="Older inherited workspace item hidden by low limit",
        metadata={"kind": "older-workspace-item"},
        created_at=created_at.replace(hour=0),
        updated_at=created_at.replace(hour=0),
    )
    memory_item_repository.create(matching_memory_item)
    memory_item_repository.create(filtered_memory_item)
    memory_item_repository.create(newer_inherited_workspace_item)
    memory_item_repository.create(older_inherited_workspace_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TICKET-CONTEXT-INCLUDE-EPISODES-FALSE-LIMIT-QUERY-SHAPING",
                }
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            query="hidden low limit",
            workflow_instance_id=str(workflow_id),
            limit=1,
            include_episodes=False,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.episodes == ()
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_tokens"] == ["hidden", "low", "limit"]
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
                    "memory_id": str(newer_inherited_workspace_item.memory_id),
                    "workspace_id": workspace_id,
                    "episode_id": None,
                    "type": "workspace_note",
                    "provenance": "workspace",
                    "content": "Newer inherited workspace item still visible with include_episodes false low limit",
                    "metadata": {"kind": "newer-workspace-item"},
                    "created_at": newer_inherited_workspace_item.created_at.isoformat(),
                    "updated_at": newer_inherited_workspace_item.updated_at.isoformat(),
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

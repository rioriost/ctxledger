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
        workflow_lookup=InMemoryWorkflowLookupRepository(
            {workflow_id, other_workflow_id}
        ),
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
                "latest_episode_created_at": datetime(
                    2024, 1, 11, tzinfo=UTC
                ).isoformat(),
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


def test_memory_get_context_includes_episode_explanations_without_query_filter() -> (
    None
):
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
    assert response.details["memory_item_counts_by_episode"] == {
        str(episode.episode_id): 1
    }
    assert response.details["summaries"] == []


def test_memory_get_context_includes_only_summaries_when_memory_items_disabled() -> (
    None
):
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
    assert response.details["memory_item_counts_by_episode"] == {
        str(episode.episode_id): 2
    }
    assert response.details["summaries"] == [
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 2,
            "memory_item_types": ["checkpoint_note", "episode_note"],
            "memory_item_provenance": ["checkpoint", "episode"],
        }
    ]


def test_memory_get_context_includes_only_memory_items_when_summaries_disabled() -> (
    None
):
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
    assert response.details["memory_item_counts_by_episode"] == {
        str(episode.episode_id): 2
    }
    assert response.details["summaries"] == []

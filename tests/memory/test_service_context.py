from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetContextResponse,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryItemRepository,
    InMemoryWorkflowLookupRepository,
    MemoryFeature,
    MemoryItemRecord,
    MemoryService,
)
from ctxledger.runtime.serializers import (
    serialize_get_context_response,
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


def test_memory_get_context_applies_initial_query_filtering() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 1, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Fix flaky postgres startup ordering",
            metadata={"kind": "stabilization", "component": "postgres"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Fix flaky postgres startup ordering"
    ]
    assert response.details["query"] == "postgres"
    assert response.details["normalized_query"] == "postgres"
    assert response.details["query_tokens"] == ["postgres"]
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 10
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": ["postgres"],
        }
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
                "latest_episode_created_at": created_at.replace(day=2).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_matches_query_against_metadata_keys() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 5, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Capture workflow evidence",
            metadata={"kind": "ops", "service": "postgres"},
            created_at=created_at.replace(day=6),
            updated_at=created_at.replace(day=6),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="component",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Document release checklist"
    ]
    assert response.details["query"] == "component"
    assert response.details["normalized_query"] == "component"
    assert response.details["query_tokens"] == ["component"]
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 10
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": False,
            "matched_metadata_values": ["component"],
        }
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
                "latest_episode_created_at": created_at.replace(day=6).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_matches_query_against_metadata_values() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 7, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"kind": "docs", "component": "release"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Capture workflow evidence",
            metadata={"kind": "ops", "service": "postgres"},
            created_at=created_at.replace(day=8),
            updated_at=created_at.replace(day=8),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="release",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Document release checklist"
    ]
    assert response.details["query"] == "release"
    assert response.details["normalized_query"] == "release"
    assert response.details["query_tokens"] == ["release"]
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 10
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": ["release"],
        }
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
                "latest_episode_created_at": created_at.replace(day=8).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_matches_multi_token_query_against_summary() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 9, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Fix postgres startup ordering in docker compose",
            metadata={"kind": "stabilization"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Fix startup race in compose stack",
            metadata={"kind": "stabilization"},
            created_at=created_at.replace(day=10),
            updated_at=created_at.replace(day=10),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres ordering",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Fix postgres startup ordering in docker compose"
    ]
    assert response.details["query"] == "postgres ordering"
    assert response.details["normalized_query"] == "postgres ordering"
    assert response.details["query_tokens"] == ["postgres", "ordering"]
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 10
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        }
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
                "latest_episode_created_at": created_at.replace(day=10).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


def test_memory_get_context_matches_multi_token_query_against_metadata() -> None:
    workflow_id = uuid4()
    episode_repository = InMemoryEpisodeRepository()
    created_at = datetime(2024, 3, 11, tzinfo=UTC)

    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Capture workflow evidence",
            metadata={"service": "postgres primary", "kind": "ops"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Document release checklist",
            metadata={"service": "release automation", "kind": "docs"},
            created_at=created_at.replace(day=12),
            updated_at=created_at.replace(day=12),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres primary",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Capture workflow evidence"
    ]
    assert response.details["query"] == "postgres primary"
    assert response.details["normalized_query"] == "postgres primary"
    assert response.details["query_tokens"] == ["postgres", "primary"]
    assert response.details["lookup_scope"] == "workflow_instance"
    assert response.details["workspace_id"] is None
    assert response.details["workflow_instance_id"] == str(workflow_id)
    assert response.details["ticket_id"] is None
    assert response.details["limit"] == 10
    assert response.details["include_episodes"] is True
    assert response.details["include_memory_items"] is False
    assert response.details["include_summaries"] is False
    assert response.details["resolved_workflow_count"] == 1
    assert response.details["resolved_workflow_ids"] == [str(workflow_id)]
    assert response.details["query_filter_applied"] is True
    assert response.details["episodes_before_query_filter"] == 2
    assert response.details["matched_episode_count"] == 1
    assert response.details["episodes_returned"] == 1
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": False,
            "matched_metadata_values": ["postgres primary"],
        }
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
                "latest_episode_created_at": created_at.replace(day=12).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


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

    assert [episode.summary for episode in response.episodes] == [
        "Matching workflow context"
    ]
    assert response.details == {
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
        "memory_item_counts_by_episode": {
            str(response.episodes[0].episode_id): 0,
        },
        "summaries": [],
    }


def test_memory_get_context_intersects_workspace_and_ticket_scope_before_query_filtering() -> (
    None
):
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

    assert [episode.summary for episode in response.episodes] == [
        "Projection drift root cause"
    ]
    assert response.details == {
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
        "memory_item_counts_by_episode": {
            str(response.episodes[0].episode_id): 0,
        },
        "summaries": [],
    }


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
                "latest_checkpoint_created_at": (
                    created_at.replace(day=21).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=15).isoformat()
                ),
                "latest_episode_created_at": (created_at.replace(day=10).isoformat()),
                "latest_attempt_started_at": (created_at.replace(day=19).isoformat()),
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
                "latest_checkpoint_created_at": (
                    created_at.replace(day=11).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=12).isoformat()
                ),
                "latest_episode_created_at": (created_at.replace(day=20).isoformat()),
                "latest_attempt_started_at": (created_at.replace(day=17).isoformat()),
                "workflow_updated_at": created_at.replace(day=17).isoformat(),
            },
        },
    }


def test_memory_get_context_prefers_verify_report_freshness_after_checkpoint_tie() -> (
    None
):
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
                "latest_checkpoint_created_at": (
                    created_at.replace(day=10).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=12).isoformat()
                ),
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
                "latest_checkpoint_created_at": (
                    created_at.replace(day=10).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=11).isoformat()
                ),
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
            str(second_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (
                    created_at.replace(day=10).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=11).isoformat()
                ),
                "latest_episode_created_at": created_at.replace(day=5).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
            str(first_workflow_id): {
                "workflow_status": None,
                "workflow_is_terminal": None,
                "latest_attempt_status": None,
                "latest_attempt_is_terminal": None,
                "has_latest_attempt": True,
                "latest_attempt_verify_status": None,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": (
                    created_at.replace(day=10).isoformat()
                ),
                "latest_verify_report_created_at": (
                    created_at.replace(day=11).isoformat()
                ),
                "latest_episode_created_at": created_at.replace(day=2).isoformat(),
                "latest_attempt_started_at": created_at.replace(day=9).isoformat(),
                "workflow_updated_at": created_at.replace(day=9).isoformat(),
            },
        },
    }


def test_memory_get_context_falls_back_to_episode_recency_without_checkpoint_signal() -> (
    None
):
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
                "latest_verify_report_created_at": None,
                "latest_episode_created_at": (created_at.replace(day=5).isoformat()),
                "latest_attempt_started_at": (created_at.replace(day=1).isoformat()),
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
                "latest_verify_report_created_at": None,
                "latest_episode_created_at": (created_at.replace(day=2).isoformat()),
                "latest_attempt_started_at": (created_at.replace(day=1).isoformat()),
                "workflow_updated_at": created_at.replace(day=1).isoformat(),
            },
        },
    }


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


def test_memory_get_context_includes_episode_explanations_for_query_matches() -> None:
    workflow_id = uuid4()
    created_at = datetime(2024, 9, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    summary_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Investigate postgres startup ordering",
        metadata={"kind": "summary-match"},
        created_at=created_at.replace(day=2),
        updated_at=created_at.replace(day=2),
    )
    metadata_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Capture workflow evidence",
        metadata={"service": "postgres primary", "kind": "metadata-match"},
        created_at=created_at.replace(day=3),
        updated_at=created_at.replace(day=3),
    )
    no_match_episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Document release checklist",
        metadata={"service": "release automation", "kind": "no-match"},
        created_at=created_at.replace(day=4),
        updated_at=created_at.replace(day=4),
    )
    episode_repository.create(summary_match_episode)
    episode_repository.create(metadata_match_episode)
    episode_repository.create(no_match_episode)

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository({workflow_id}),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            query="postgres ordering",
            limit=10,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert [episode.summary for episode in response.episodes] == [
        "Investigate postgres startup ordering",
    ]
    assert response.details["episode_explanations"] == [
        {
            "episode_id": str(summary_match_episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "matched": True,
            "explanation_basis": "query_match_evaluation",
            "matched_summary": True,
            "matched_metadata_values": [],
        },
    ]


def test_serialize_get_context_response_serializes_episode_payloads() -> None:
    workflow_id = uuid4()
    attempt_id = uuid4()
    created_at = datetime(2024, 3, 4, 5, 6, 7, tzinfo=UTC)
    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=uuid4(),
                workflow_instance_id=workflow_id,
                summary="Recovered context",
                attempt_id=attempt_id,
                metadata={"kind": "root-cause"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": "root cause",
            "normalized_query": "root cause",
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": True,
            "episodes_before_query_filter": 3,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [
                {
                    "episode_id": None,
                    "workflow_instance_id": str(workflow_id),
                    "matched": True,
                    "explanation_basis": "query_match_evaluation",
                    "matched_summary": False,
                    "matched_metadata_values": ["root-cause"],
                }
            ],
        },
    )

    payload = serialize_get_context_response(response)

    assert payload["feature"] == "memory_get_context"
    assert payload["implemented"] is True
    assert (
        payload["message"] == "Episode-oriented memory context retrieved successfully."
    )
    assert payload["status"] == "ok"
    assert payload["available_in_version"] == "0.2.0"
    assert payload["timestamp"] == created_at.isoformat()
    assert payload["details"] == {
        "query": "root cause",
        "normalized_query": "root cause",
        "lookup_scope": "workflow_instance",
        "workflow_instance_id": str(workflow_id),
        "resolved_workflow_count": 1,
        "resolved_workflow_ids": [str(workflow_id)],
        "query_filter_applied": True,
        "episodes_before_query_filter": 3,
        "matched_episode_count": 1,
        "episodes_returned": 1,
        "episode_explanations": [
            {
                "episode_id": None,
                "workflow_instance_id": str(workflow_id),
                "matched": True,
                "explanation_basis": "query_match_evaluation",
                "matched_summary": False,
                "matched_metadata_values": ["root-cause"],
            }
        ],
        "memory_items": [],
        "memory_item_counts_by_episode": {},
        "summaries": [],
    }
    assert payload["details"]["episode_explanations"][0]["matched"] is True
    assert (
        payload["details"]["episode_explanations"][0]["explanation_basis"]
        == "query_match_evaluation"
    )
    assert payload["details"]["episode_explanations"][0]["matched_summary"] is False
    assert payload["details"]["episode_explanations"][0]["matched_metadata_values"] == [
        "root-cause"
    ]
    assert payload["episodes"] == [
        {
            "episode_id": str(response.episodes[0].episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary": "Recovered context",
            "attempt_id": str(attempt_id),
            "metadata": {"kind": "root-cause"},
            "status": "recorded",
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat(),
        }
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


def test_serialize_get_context_response_preserves_memory_item_and_summary_details() -> (
    None
):
    workflow_id = uuid4()
    episode_id = uuid4()
    memory_id = uuid4()
    created_at = datetime(2024, 10, 7, 1, 2, 3, tzinfo=UTC)

    response = GetContextResponse(
        feature=MemoryFeature.GET_CONTEXT,
        implemented=True,
        message="Episode-oriented memory context retrieved successfully.",
        status="ok",
        available_in_version="0.2.0",
        timestamp=created_at,
        episodes=(
            EpisodeRecord(
                episode_id=episode_id,
                workflow_instance_id=workflow_id,
                summary="Serializer detail episode",
                attempt_id=None,
                metadata={"kind": "serializer"},
                status="recorded",
                created_at=created_at,
                updated_at=created_at,
            ),
        ),
        details={
            "query": None,
            "normalized_query": None,
            "lookup_scope": "workflow_instance",
            "workflow_instance_id": str(workflow_id),
            "resolved_workflow_count": 1,
            "resolved_workflow_ids": [str(workflow_id)],
            "query_filter_applied": False,
            "episodes_before_query_filter": 1,
            "matched_episode_count": 1,
            "episodes_returned": 1,
            "episode_explanations": [],
            "memory_items": [
                [
                    {
                        "memory_id": str(memory_id),
                        "workspace_id": str(workflow_id),
                        "episode_id": str(episode_id),
                        "type": "episode_note",
                        "provenance": "episode",
                        "content": "Serialized memory item",
                        "metadata": {"kind": "note"},
                        "created_at": created_at.isoformat(),
                        "updated_at": created_at.isoformat(),
                    }
                ]
            ],
            "memory_item_counts_by_episode": {
                str(episode_id): 1,
            },
            "summaries": [
                {
                    "episode_id": str(episode_id),
                    "workflow_instance_id": str(workflow_id),
                    "memory_item_count": 1,
                    "memory_item_types": ["episode_note"],
                    "memory_item_provenance": ["episode"],
                }
            ],
        },
    )

    payload = serialize_get_context_response(response)

    assert payload["details"]["memory_items"] == [
        [
            {
                "memory_id": str(memory_id),
                "workspace_id": str(workflow_id),
                "episode_id": str(episode_id),
                "type": "episode_note",
                "provenance": "episode",
                "content": "Serialized memory item",
                "metadata": {"kind": "note"},
                "created_at": created_at.isoformat(),
                "updated_at": created_at.isoformat(),
            }
        ]
    ]
    assert payload["details"]["memory_item_counts_by_episode"] == {
        str(episode_id): 1,
    }
    assert payload["details"]["summaries"] == [
        {
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        }
    ]

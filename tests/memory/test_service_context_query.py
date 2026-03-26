from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from ctxledger.memory.service import (
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryWorkflowLookupRepository,
    MemoryService,
)


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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
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

    assert [episode.summary for episode in response.episodes] == ["Document release checklist"]
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
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

    assert [episode.summary for episode in response.episodes] == ["Document release checklist"]
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
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

    assert [episode.summary for episode in response.episodes] == ["Capture workflow evidence"]
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
                "latest_checkpoint_step_name": None,
                "latest_checkpoint_summary": None,
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
                "latest_checkpoint_has_current_objective": False,
                "latest_checkpoint_has_next_intended_action": False,
                "latest_verify_report_created_at": None,
                "latest_episode_created_at": created_at.replace(day=12).isoformat(),
                "latest_attempt_started_at": None,
                "workflow_updated_at": None,
            }
        },
    }


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

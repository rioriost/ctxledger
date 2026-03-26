from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from ctxledger.memory.embeddings import (
    EmbeddingGenerationError,
    EmbeddingRequest,
    EmbeddingResult,
)
from ctxledger.memory.service import (
    BuildEpisodeSummaryRequest,
    EpisodeRecord,
    GetMemoryContextRequest,
    InMemoryEpisodeRepository,
    InMemoryMemoryEmbeddingRepository,
    InMemoryMemoryItemRepository,
    InMemoryMemoryRelationRepository,
    InMemoryMemorySummaryMembershipRepository,
    InMemoryMemorySummaryRepository,
    InMemoryWorkflowLookupRepository,
    MemoryEmbeddingRecord,
    MemoryErrorCode,
    MemoryFeature,
    MemoryItemRecord,
    MemoryRelationRecord,
    MemoryService,
    MemoryServiceError,
    MemorySummaryMembershipRecord,
    MemorySummaryRecord,
    RememberEpisodeRequest,
    RememberEpisodeResponse,
    SearchMemoryRequest,
)


def test_memory_service_summary_first_selection_prefers_canonical_memory_summaries() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000091")
    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-1",
            }
        }
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode-level summary text should no longer be the primary summary route",
        attempt_id=None,
        metadata={"kind": "episode"},
        status="recorded",
        created_at=datetime(2024, 2, 1, tzinfo=UTC),
        updated_at=datetime(2024, 2, 1, tzinfo=UTC),
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First child memory item for canonical summary expansion",
        metadata={"rank": 1},
        created_at=datetime(2024, 2, 2, tzinfo=UTC),
        updated_at=datetime(2024, 2, 2, tzinfo=UTC),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second child memory item for canonical summary expansion",
        metadata={"rank": 2},
        created_at=datetime(2024, 2, 3, tzinfo=UTC),
        updated_at=datetime(2024, 2, 3, tzinfo=UTC),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Canonical memory summary chosen before direct episode summary shaping",
        summary_kind="episode_summary",
        metadata={"source": "test"},
        created_at=datetime(2024, 2, 4, tzinfo=UTC),
        updated_at=datetime(2024, 2, 4, tzinfo=UTC),
    )
    memory_summary_repository.create(summary)

    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=first_memory_item.memory_id,
            membership_order=1,
            metadata={"source": "test"},
            created_at=datetime(2024, 2, 5, tzinfo=UTC),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=second_memory_item.memory_id,
            membership_order=2,
            metadata={"source": "test"},
            created_at=datetime(2024, 2, 6, tzinfo=UTC),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
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

    assert response.feature == MemoryFeature.GET_CONTEXT
    assert response.status == "ok"
    assert response.episodes == (episode,)
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "memory_summary_first"
    assert response.details["retrieval_routes_present"][0] == "summary_first"
    assert response.details["primary_retrieval_routes_present"][0] == "summary_first"
    assert response.details["retrieval_route_group_counts"]["summary_first"] == 1
    assert response.details["retrieval_route_item_counts"]["summary_first"] == 1
    assert response.details["summary_first_child_episode_count"] == 1
    assert response.details["summary_first_child_episode_ids"] == [str(episode.episode_id)]

    assert response.details["summaries"] == [
        {
            "memory_summary_id": str(summary.memory_summary_id),
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": "Canonical memory summary chosen before direct episode summary shaping",
            "summary_kind": "episode_summary",
            "metadata": {"source": "test"},
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
                    "content": "Second child memory item for canonical summary expansion",
                    "metadata": {"rank": 2},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First child memory item for canonical summary expansion",
                    "metadata": {"rank": 1},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                },
            ],
        }
    ]

    summary_group = response.details["memory_context_groups"][0]
    assert summary_group["scope"] == "summary"
    assert summary_group["selection_kind"] == "memory_summary_first"
    assert summary_group["selection_route"] == "summary_first"
    assert summary_group["child_episode_ids"] == [str(episode.episode_id)]
    assert summary_group["child_episode_count"] == 1


def test_memory_service_build_episode_summary_creates_canonical_summary_and_memberships() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000092")
    created_at = datetime(2024, 2, 7, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-1",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary source text",
        attempt_id=None,
        metadata={"kind": "episode"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First explicit child item",
        metadata={"rank": 1},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second explicit child item",
        metadata={"rank": 2},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
            metadata={"requested_by": "test"},
        )
    )

    assert result.feature == MemoryFeature.GET_CONTEXT
    assert result.implemented is True
    assert result.status == "built"
    assert result.available_in_version == "0.6.0"
    assert result.summary_built is True
    assert result.skipped_reason is None
    assert result.replaced_existing_summary is False
    assert result.summary is not None
    assert result.summary.workspace_id == workspace_id
    assert result.summary.episode_id == episode.episode_id
    assert result.summary.summary_kind == "episode_summary"
    assert result.summary.metadata == {
        "builder": "minimal_episode_summary_builder",
        "build_scope": "episode",
        "source_episode_id": str(episode.episode_id),
        "source_memory_item_count": 2,
        "build_version": "0.6.0-first-slice",
        "remember_path_memory_origins": [],
        "remember_path_promotion_fields": [],
        "remember_path_promotion_sources": [],
        "requested_by": "test",
    }
    assert result.summary.summary_text == (
        "Episode summary source text\n\nIncluded memory items:\n- "
        "Second explicit child item\n- First explicit child item"
    )
    assert len(result.memberships) == 2
    assert [membership.membership_order for membership in result.memberships] == [1, 2]
    assert [membership.memory_id for membership in result.memberships] == [
        second_memory_item.memory_id,
        first_memory_item.memory_id,
    ]
    assert result.details == {
        "episode_id": str(episode.episode_id),
        "summary_kind": "episode_summary",
        "member_memory_count": 2,
        "member_memory_ids": [
            str(second_memory_item.memory_id),
            str(first_memory_item.memory_id),
        ],
        "remember_path_memory_origins": [],
        "remember_path_promotion_fields": [],
        "remember_path_promotion_sources": [],
        "member_memory_explainability": [
            {
                "memory_id": str(second_memory_item.memory_id),
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
        ],
    }
    assert len(memory_summary_repository.summaries) == 1
    assert len(memory_summary_membership_repository.memberships) == 2


def test_memory_service_summary_first_selection_includes_remember_path_explainability() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000095")
    created_at = datetime(2024, 2, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-EXPLAINABILITY-1",
            }
        }
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Summary-first context should preserve remember-path explainability",
        attempt_id=None,
        metadata={"kind": "remember-path"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    checkpoint_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_objective",
        provenance="workflow_checkpoint_auto",
        content="Checkpoint-origin member included in summary-first response",
        metadata={
            "memory_origin": "workflow_checkpoint_auto",
            "promotion_field": "current_objective",
            "promotion_source": "checkpoint.current_objective",
            "checkpoint_id": "checkpoint-summary-1",
            "step_name": "summary_explainability",
            "workflow_status": "running",
            "attempt_status": "running",
        },
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    completion_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_completion_note",
        provenance="workflow_complete_auto",
        content="Completion-origin member included in summary-first response",
        metadata={
            "memory_origin": "workflow_complete_auto",
            "step_name": "workflow_complete",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
        },
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(checkpoint_memory_item)
    memory_item_repository.create(completion_memory_item)

    summary = MemorySummaryRecord(
        memory_summary_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        summary_text="Canonical summary with remember-path explainability",
        summary_kind="episode_summary",
        metadata={
            "source": "test",
            "remember_path_memory_origins": [
                "workflow_checkpoint_auto",
                "workflow_complete_auto",
            ],
            "remember_path_promotion_fields": [
                "current_objective",
            ],
            "remember_path_promotion_sources": [
                "checkpoint.current_objective",
            ],
        },
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    memory_summary_repository.create(summary)

    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=completion_memory_item.memory_id,
            membership_order=1,
            metadata={"source": "test"},
            created_at=created_at.replace(hour=4),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=summary.memory_summary_id,
            memory_id=checkpoint_memory_item.memory_id,
            membership_order=2,
            metadata={"source": "test"},
            created_at=created_at.replace(hour=5),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
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
            "summary_text": "Canonical summary with remember-path explainability",
            "summary_kind": "episode_summary",
            "metadata": {
                "source": "test",
                "remember_path_memory_origins": [
                    "workflow_checkpoint_auto",
                    "workflow_complete_auto",
                ],
                "remember_path_promotion_fields": [
                    "current_objective",
                ],
                "remember_path_promotion_sources": [
                    "checkpoint.current_objective",
                ],
            },
            "member_memory_count": 2,
            "member_memory_ids": [
                str(completion_memory_item.memory_id),
                str(checkpoint_memory_item.memory_id),
            ],
            "member_memory_items": [
                {
                    "memory_id": str(completion_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "workflow_completion_note",
                    "provenance": "workflow_complete_auto",
                    "content": "Completion-origin member included in summary-first response",
                    "metadata": {
                        "memory_origin": "workflow_complete_auto",
                        "step_name": "workflow_complete",
                        "workflow_status": "completed",
                        "attempt_status": "succeeded",
                    },
                    "created_at": completion_memory_item.created_at.isoformat(),
                    "updated_at": completion_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(checkpoint_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "workflow_objective",
                    "provenance": "workflow_checkpoint_auto",
                    "content": "Checkpoint-origin member included in summary-first response",
                    "metadata": {
                        "memory_origin": "workflow_checkpoint_auto",
                        "promotion_field": "current_objective",
                        "promotion_source": "checkpoint.current_objective",
                        "checkpoint_id": "checkpoint-summary-1",
                        "step_name": "summary_explainability",
                        "workflow_status": "running",
                        "attempt_status": "running",
                    },
                    "created_at": checkpoint_memory_item.created_at.isoformat(),
                    "updated_at": checkpoint_memory_item.updated_at.isoformat(),
                },
            ],
        }
    ]


def test_memory_service_build_episode_summary_skips_when_episode_has_no_memory_items() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000093")
    created_at = datetime(2024, 2, 8, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-2",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode without child memory items",
        attempt_id=None,
        metadata={"kind": "empty"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
        )
    )

    assert result.feature == MemoryFeature.GET_CONTEXT
    assert result.implemented is True
    assert result.status == "skipped"
    assert result.available_in_version == "0.6.0"
    assert result.summary is None
    assert result.memberships == ()
    assert result.summary_built is False
    assert result.skipped_reason == "no_episode_memory_items"
    assert result.replaced_existing_summary is False
    assert result.details == {
        "episode_id": str(episode.episode_id),
        "summary_kind": "episode_summary",
        "member_memory_count": 0,
    }


def test_memory_service_build_episode_summary_preserves_remember_path_explainability_metadata() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000094")
    created_at = datetime(2024, 2, 9, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-3",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Checkpoint-origin episode with promoted remember-path members",
        attempt_id=None,
        metadata={"kind": "remember-path"},
        status="recorded",
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
        content="Strengthen remember-path summary explainability",
        metadata={
            "memory_origin": "workflow_checkpoint_auto",
            "promotion_field": "current_objective",
            "promotion_source": "checkpoint.current_objective",
            "checkpoint_id": "checkpoint-remember-path-1",
            "step_name": "summary_explainability",
            "workflow_status": "running",
            "attempt_status": "running",
        },
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    recovery_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_recovery_pattern",
        provenance="workflow_checkpoint_auto",
        content="Expose member origin and promotion details in summary outputs",
        metadata={
            "memory_origin": "workflow_checkpoint_auto",
            "promotion_field": "recovery_pattern",
            "promotion_source": "checkpoint.recovery_pattern",
            "checkpoint_id": "checkpoint-remember-path-1",
            "step_name": "summary_explainability",
            "workflow_status": "running",
            "attempt_status": "running",
        },
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    completion_note_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="workflow_completion_note",
        provenance="workflow_complete_auto",
        content="Completion-origin note retained in the same summary build",
        metadata={
            "memory_origin": "workflow_complete_auto",
            "step_name": "workflow_complete",
            "workflow_status": "completed",
            "attempt_status": "succeeded",
        },
        created_at=created_at.replace(hour=3),
        updated_at=created_at.replace(hour=3),
    )
    memory_item_repository.create(objective_memory_item)
    memory_item_repository.create(recovery_memory_item)
    memory_item_repository.create(completion_note_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
            metadata={"requested_by": "remember-path-test"},
        )
    )

    assert result.status == "built"
    assert result.summary is not None
    assert result.summary.metadata == {
        "builder": "minimal_episode_summary_builder",
        "build_scope": "episode",
        "source_episode_id": str(episode.episode_id),
        "source_memory_item_count": 3,
        "build_version": "0.6.0-first-slice",
        "remember_path_memory_origins": [
            "workflow_checkpoint_auto",
            "workflow_complete_auto",
        ],
        "remember_path_promotion_fields": [
            "current_objective",
            "recovery_pattern",
        ],
        "remember_path_promotion_sources": [
            "checkpoint.current_objective",
            "checkpoint.recovery_pattern",
        ],
        "requested_by": "remember-path-test",
    }
    assert result.details == {
        "episode_id": str(episode.episode_id),
        "summary_kind": "episode_summary",
        "member_memory_count": 3,
        "member_memory_ids": [
            str(completion_note_memory_item.memory_id),
            str(recovery_memory_item.memory_id),
            str(objective_memory_item.memory_id),
        ],
        "remember_path_memory_origins": [
            "workflow_checkpoint_auto",
            "workflow_complete_auto",
        ],
        "remember_path_promotion_fields": [
            "current_objective",
            "recovery_pattern",
        ],
        "remember_path_promotion_sources": [
            "checkpoint.current_objective",
            "checkpoint.recovery_pattern",
        ],
        "member_memory_explainability": [
            {
                "memory_id": str(completion_note_memory_item.memory_id),
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
                "memory_id": str(recovery_memory_item.memory_id),
                "memory_type": "workflow_recovery_pattern",
                "provenance": "workflow_checkpoint_auto",
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "recovery_pattern",
                "promotion_source": "checkpoint.recovery_pattern",
                "checkpoint_id": "checkpoint-remember-path-1",
                "step_name": "summary_explainability",
                "workflow_status": "running",
                "attempt_status": "running",
            },
            {
                "memory_id": str(objective_memory_item.memory_id),
                "memory_type": "workflow_objective",
                "provenance": "workflow_checkpoint_auto",
                "memory_origin": "workflow_checkpoint_auto",
                "promotion_field": "current_objective",
                "promotion_source": "checkpoint.current_objective",
                "checkpoint_id": "checkpoint-remember-path-1",
                "step_name": "summary_explainability",
                "workflow_status": "running",
                "attempt_status": "running",
            },
        ],
    }
    assert len(memory_summary_repository.summaries) == 1
    assert (
        memory_summary_repository.summaries[0].memory_summary_id == result.summary.memory_summary_id
    )
    assert len(memory_summary_membership_repository.memberships) == 3
    assert [
        membership.memory_id for membership in memory_summary_membership_repository.memberships
    ] == [
        completion_note_memory_item.memory_id,
        recovery_memory_item.memory_id,
        objective_memory_item.memory_id,
    ]


def test_memory_service_build_episode_summary_marks_replace_existing_when_summary_kind_already_exists() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000094")
    created_at = datetime(2024, 2, 9, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-3",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with pre-existing summary",
        attempt_id=None,
        metadata={"kind": "replace"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Current child item",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(memory_item)

    existing_summary = memory_summary_repository.create(
        MemorySummaryRecord(
            memory_summary_id=uuid4(),
            workspace_id=workspace_id,
            episode_id=episode.episode_id,
            summary_text="Older summary",
            summary_kind="episode_summary",
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
            updated_at=created_at.replace(hour=2),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=existing_summary.memory_summary_id,
            memory_id=memory_item.memory_id,
            membership_order=1,
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )

    assert result.status == "built"
    assert result.summary_built is True
    assert result.replaced_existing_summary is True
    assert result.summary is not None
    assert result.summary.summary_kind == "episode_summary"
    assert len(memory_summary_repository.summaries) == 1
    assert (
        memory_summary_repository.summaries[0].memory_summary_id == result.summary.memory_summary_id
    )
    assert len(memory_summary_membership_repository.memberships) == 1
    assert (
        memory_summary_membership_repository.memberships[0].memory_summary_id
        == result.summary.memory_summary_id
    )


def test_memory_service_build_episode_summary_keeps_existing_summary_when_replace_is_disabled() -> (
    None
):
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000097")
    created_at = datetime(2024, 2, 12, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-4",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with existing summary kept by no-replace",
        attempt_id=None,
        metadata={"kind": "keep-existing"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Current child item for no-replace behavior",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(memory_item)

    existing_summary = memory_summary_repository.create(
        MemorySummaryRecord(
            memory_summary_id=uuid4(),
            workspace_id=workspace_id,
            episode_id=episode.episode_id,
            summary_text="Existing summary that should remain",
            summary_kind="episode_summary",
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
            updated_at=created_at.replace(hour=2),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=existing_summary.memory_summary_id,
            memory_id=memory_item.memory_id,
            membership_order=1,
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=False,
        )
    )

    assert result.status == "built"
    assert result.summary_built is True
    assert result.replaced_existing_summary is False
    assert result.summary is not None
    assert result.summary.summary_kind == "episode_summary"
    assert len(memory_summary_repository.summaries) == 2
    assert {summary.memory_summary_id for summary in memory_summary_repository.summaries} == {
        existing_summary.memory_summary_id,
        result.summary.memory_summary_id,
    }
    assert len(memory_summary_membership_repository.memberships) == 2


def test_memory_service_build_episode_summary_allows_multiple_summary_kinds_to_coexist() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000098")
    created_at = datetime(2024, 2, 13, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-5",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode with multi-kind summary behavior",
        attempt_id=None,
        metadata={"kind": "multi-kind"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Child item shared across summary kinds",
        metadata={"kind": "note"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    first_result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )
    second_result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary_compact",
            replace_existing=True,
        )
    )

    assert first_result.summary is not None
    assert second_result.summary is not None
    assert first_result.summary.summary_kind == "episode_summary"
    assert second_result.summary.summary_kind == "episode_summary_compact"
    assert first_result.replaced_existing_summary is False
    assert second_result.replaced_existing_summary is False
    assert len(memory_summary_repository.summaries) == 2
    assert {summary.summary_kind for summary in memory_summary_repository.summaries} == {
        "episode_summary",
        "episode_summary_compact",
    }
    assert len(memory_summary_membership_repository.memberships) == 2


def test_memory_service_built_episode_summary_is_used_by_summary_first_retrieval() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000095")
    created_at = datetime(2024, 2, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-RETRIEVAL-1",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode source summary for builder-driven retrieval",
        attempt_id=None,
        metadata={"kind": "builder-retrieval"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="First builder-driven child item",
        metadata={"rank": 1},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Second builder-driven child item",
        metadata={"rank": 2},
        created_at=created_at.replace(hour=2),
        updated_at=created_at.replace(hour=2),
    )
    memory_item_repository.create(first_memory_item)
    memory_item_repository.create(second_memory_item)

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    build_result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )

    assert build_result.summary is not None
    response = service.get_context(
        GetMemoryContextRequest(
            workflow_instance_id=str(workflow_id),
            limit=10,
            include_episodes=True,
            include_memory_items=True,
            include_summaries=True,
        )
    )

    assert response.feature == MemoryFeature.GET_CONTEXT
    assert response.status == "ok"
    assert response.episodes == (episode,)
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "memory_summary_first"
    assert response.details["summaries"] == [
        {
            "memory_summary_id": str(build_result.summary.memory_summary_id),
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(workflow_id),
            "summary_text": (
                "Episode source summary for builder-driven retrieval\n\n"
                "Included memory items:\n- "
                "Second builder-driven child item\n- First builder-driven child item"
            ),
            "summary_kind": "episode_summary",
            "metadata": {
                "builder": "minimal_episode_summary_builder",
                "build_scope": "episode",
                "source_episode_id": str(episode.episode_id),
                "source_memory_item_count": 2,
                "build_version": "0.6.0-first-slice",
                "remember_path_memory_origins": [],
                "remember_path_promotion_fields": [],
                "remember_path_promotion_sources": [],
            },
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
                    "content": "Second builder-driven child item",
                    "metadata": {"rank": 2},
                    "created_at": second_memory_item.created_at.isoformat(),
                    "updated_at": second_memory_item.updated_at.isoformat(),
                },
                {
                    "memory_id": str(first_memory_item.memory_id),
                    "workspace_id": str(workspace_id),
                    "episode_id": str(episode.episode_id),
                    "type": "episode_note",
                    "provenance": "episode",
                    "content": "First builder-driven child item",
                    "metadata": {"rank": 1},
                    "created_at": first_memory_item.created_at.isoformat(),
                    "updated_at": first_memory_item.updated_at.isoformat(),
                },
            ],
        }
    ]
    assert response.details["memory_context_groups"][0]["selection_kind"] == "memory_summary_first"
    assert response.details["memory_context_groups"][0]["selection_route"] == "summary_first"


def test_memory_service_rebuilt_episode_summary_replaces_older_summary_in_retrieval() -> None:
    workflow_id = uuid4()
    workspace_id = UUID("00000000-0000-0000-0000-000000000096")
    created_at = datetime(2024, 2, 11, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    memory_item_repository = InMemoryMemoryItemRepository()
    memory_summary_repository = InMemoryMemorySummaryRepository()
    memory_summary_membership_repository = InMemoryMemorySummaryMembershipRepository()
    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflow_ids={workflow_id},
        workflows_by_id={
            workflow_id: {
                "workspace_id": str(workspace_id),
                "ticket_id": "TICKET-SUMMARY-BUILD-RETRIEVAL-2",
            }
        },
    )

    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode source summary for rebuilt retrieval",
        attempt_id=None,
        metadata={"kind": "builder-rebuild"},
        status="recorded",
        created_at=created_at,
        updated_at=created_at,
    )
    episode_repository.create(episode)

    current_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="Current rebuilt child item",
        metadata={"kind": "current"},
        created_at=created_at.replace(hour=1),
        updated_at=created_at.replace(hour=1),
    )
    memory_item_repository.create(current_memory_item)

    existing_summary = memory_summary_repository.create(
        MemorySummaryRecord(
            memory_summary_id=uuid4(),
            workspace_id=workspace_id,
            episode_id=episode.episode_id,
            summary_text="Older summary that should disappear from retrieval",
            summary_kind="episode_summary",
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
            updated_at=created_at.replace(hour=2),
        )
    )
    memory_summary_membership_repository.create(
        MemorySummaryMembershipRecord(
            memory_summary_membership_id=uuid4(),
            memory_summary_id=existing_summary.memory_summary_id,
            memory_id=current_memory_item.memory_id,
            membership_order=1,
            metadata={"builder": "older"},
            created_at=created_at.replace(hour=2),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        memory_item_repository=memory_item_repository,
        memory_summary_repository=memory_summary_repository,
        memory_summary_membership_repository=memory_summary_membership_repository,
        workflow_lookup=workflow_lookup,
        workspace_lookup=workflow_lookup,
    )

    build_result = service.build_episode_summary(
        BuildEpisodeSummaryRequest(
            episode_id=str(episode.episode_id),
            summary_kind="episode_summary",
            replace_existing=True,
        )
    )

    assert build_result.summary is not None
    assert build_result.replaced_existing_summary is True

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
    assert len(response.details["summaries"]) == 1
    assert response.details["summaries"][0]["memory_summary_id"] == str(
        build_result.summary.memory_summary_id
    )
    assert (
        response.details["summaries"][0]["summary_text"]
        != "Older summary that should disappear from retrieval"
    )
    assert response.details["summaries"][0]["summary_text"] == (
        "Episode source summary for rebuilt retrieval\n\nIncluded memory items:\n- "
        "Current rebuilt child item"
    )
    assert len(memory_summary_repository.summaries) == 1
    assert (
        memory_summary_repository.summaries[0].memory_summary_id
        == build_result.summary.memory_summary_id
    )

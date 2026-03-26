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


def test_memory_service_resolve_workspace_id_and_has_text_helpers() -> None:
    workflow_id = uuid4()
    workspace_id = uuid4()
    service = MemoryService(
        workspace_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                workflow_id: {
                    "workspace_id": str(workspace_id),
                }
            }
        )
    )

    assert service._resolve_workspace_id(workflow_id) == workspace_id
    assert service._has_text(" value ") is True
    assert service._has_text("   ") is False
    assert service._has_text(None) is False


def test_memory_service_constructor_swallowing_embedding_builder_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ctxledger.memory.service.get_settings",
        lambda: SimpleNamespace(embedding=SimpleNamespace()),
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.build_embedding_generator",
        lambda settings: (_ for _ in ()).throw(RuntimeError("builder exploded")),
    )

    service = MemoryService(embedding_generator=None)

    assert service._embedding_generator is None


def test_memory_service_constructor_uses_built_embedding_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentinel_generator = object()

    monkeypatch.setattr(
        "ctxledger.memory.service.get_settings",
        lambda: SimpleNamespace(embedding=SimpleNamespace(provider="openai")),
    )
    monkeypatch.setattr(
        "ctxledger.memory.service.build_embedding_generator",
        lambda settings: sentinel_generator,
    )

    service = MemoryService(embedding_generator=None)

    assert service._embedding_generator is sentinel_generator


def test_memory_service_order_workflow_ids_by_freshness_with_empty_input() -> None:
    service = MemoryService()

    assert service._order_workflow_ids_by_freshness_signals(workflow_ids=(), limit=5) == ()


def test_memory_service_workflow_ordering_signals_without_lookup() -> None:
    workflow_id = uuid4()
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=workflow_id,
        summary="Episode summary",
        created_at=datetime(2024, 1, 4, tzinfo=UTC),
        updated_at=datetime(2024, 1, 4, tzinfo=UTC),
    )
    service = MemoryService(
        episode_repository=SimpleNamespace(
            list_by_workflow_id=lambda workflow_id_arg, limit: (episode,)
        )
    )

    signals = service._workflow_ordering_signals(workflow_ids=(workflow_id,))

    assert signals == {
        str(workflow_id): {
            "workflow_status": None,
            "workflow_is_terminal": None,
            "latest_attempt_status": None,
            "latest_attempt_is_terminal": None,
            "has_latest_attempt": None,
            "latest_attempt_verify_status": None,
            "has_latest_checkpoint": None,
            "latest_checkpoint_created_at": None,
            "latest_checkpoint_step_name": None,
            "latest_checkpoint_summary": None,
            "latest_checkpoint_current_objective": None,
            "latest_checkpoint_next_intended_action": None,
            "latest_checkpoint_has_current_objective": False,
            "latest_checkpoint_has_next_intended_action": False,
            "latest_verify_report_created_at": None,
            "latest_episode_created_at": episode.created_at.isoformat(),
            "latest_attempt_started_at": None,
            "workflow_updated_at": None,
        }
    }


def test_memory_service_build_memory_item_details_without_optional_outputs() -> None:
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
    )
    memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=episode.episode_id,
        content="content",
    )
    service = MemoryService(
        memory_item_repository=SimpleNamespace(
            list_by_episode_ids=lambda episode_ids: (memory_item,)
        )
    )

    details = service._build_memory_item_details_for_episodes(
        episodes=(episode,),
        include_memory_items=False,
        include_summaries=False,
    )

    assert details == (
        {
            "episode_id": str(episode.episode_id),
            "memory_item_count": 1,
        },
    )


def test_memory_service_build_episode_explanations_for_unfiltered_context() -> None:
    service = MemoryService()
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
        metadata={"kind": "note"},
    )

    explanations = service._build_episode_explanations(
        episodes=(episode,),
        normalized_query=None,
        query_tokens=(),
    )

    assert explanations == (
        {
            "episode_id": str(episode.episode_id),
            "workflow_instance_id": str(episode.workflow_instance_id),
            "matched": True,
            "explanation_basis": "unfiltered_episode_context",
            "matched_summary": False,
            "matched_metadata_values": [],
        },
    )


def test_memory_service_build_memory_item_details_with_summary_output() -> None:
    episode = EpisodeRecord(
        episode_id=uuid4(),
        workflow_instance_id=uuid4(),
        summary="Episode summary",
    )
    first_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=uuid4(),
        episode_id=episode.episode_id,
        type="episode_note",
        provenance="episode",
        content="first",
    )
    second_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=first_memory_item.workspace_id,
        episode_id=episode.episode_id,
        type="checkpoint_note",
        provenance="checkpoint",
        content="second",
    )
    service = MemoryService(
        memory_item_repository=SimpleNamespace(
            list_by_episode_ids=lambda episode_ids: (
                second_memory_item,
                first_memory_item,
            )
        )
    )

    details = service._build_memory_item_details_for_episodes(
        episodes=(episode,),
        include_memory_items=False,
        include_summaries=True,
    )

    assert len(details) == 1
    assert details[0]["episode_id"] == str(episode.episode_id)
    assert details[0]["memory_item_count"] == 2
    assert details[0]["summary"]["episode_id"] == str(episode.episode_id)
    assert details[0]["summary"]["workflow_instance_id"] == str(episode.workflow_instance_id)
    assert details[0]["summary"]["memory_item_count"] == 2
    assert details[0]["summary"]["memory_item_types"] == ["checkpoint_note", "episode_note"]
    assert details[0]["summary"]["memory_item_provenance"] == ["checkpoint", "episode"]
    assert "remember_path_explainability" in details[0]["summary"]


def test_memory_service_build_summary_selection_details_without_summaries() -> None:
    service = MemoryService()

    summaries, summary_selection_applied, summary_selection_kind = (
        service._build_summary_selection_details(
            (
                {
                    "episode_id": str(uuid4()),
                    "memory_item_count": 1,
                },
            )
        )
    )

    assert summaries == ()
    assert summary_selection_applied is False
    assert summary_selection_kind is None


def test_memory_service_build_summary_selection_details_with_summaries() -> None:
    service = MemoryService()
    episode_id = uuid4()
    workflow_instance_id = uuid4()

    summaries, summary_selection_applied, summary_selection_kind = (
        service._build_summary_selection_details(
            (
                {
                    "episode_id": str(episode_id),
                    "memory_item_count": 1,
                    "summary": {
                        "episode_id": str(episode_id),
                        "workflow_instance_id": str(workflow_instance_id),
                        "memory_item_count": 1,
                        "memory_item_types": ["episode_note"],
                        "memory_item_provenance": ["episode"],
                    },
                },
            )
        )
    )

    assert summaries == (
        {
            "episode_id": str(episode_id),
            "workflow_instance_id": str(workflow_instance_id),
            "memory_item_count": 1,
            "memory_item_types": ["episode_note"],
            "memory_item_provenance": ["episode"],
        },
    )
    assert summary_selection_applied is True
    assert summary_selection_kind == "episode_summary_first"


def test_memory_service_build_retrieval_route_details_marks_auxiliary_only_after_query_filter() -> (
    None
):
    service = MemoryService()
    episode_id = uuid4()
    workspace_id = uuid4()
    inherited_memory_item = MemoryItemRecord(
        memory_id=uuid4(),
        workspace_id=workspace_id,
        episode_id=None,
        type="workspace_note",
        provenance="workspace",
        content="workspace inherited",
    )

    details = service._build_retrieval_route_details(
        memory_item_details=(
            {
                "episode_id": str(episode_id),
                "memory_item_count": 0,
            },
        ),
        summaries=(),
        summary_selection_applied=False,
        matched_episode_count=1,
        include_memory_items=False,
        inherited_memory_items=(inherited_memory_item,),
        related_memory_items=(),
        graph_summary_related_memory_items=(),
    )

    assert details["retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert details["primary_retrieval_routes_present"] == []
    assert details["auxiliary_retrieval_routes_present"] == [
        "workspace_inherited_auxiliary",
    ]
    assert details["primary_episode_groups_present_after_query_filter"] is False
    assert details["auxiliary_only_after_query_filter"] is True
    assert details["summary_first_has_episode_groups"] is False
    assert details["summary_first_is_summary_only"] is False
    assert details["summary_first_child_episode_count"] == 0
    assert details["summary_first_child_episode_ids"] == []
    assert details["relation_supports_source_episode_count"] == 0


def test_memory_service_task_recall_context_surfaces_latest_detour_candidate_fields() -> None:
    primary_workflow_id = uuid4()
    detour_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=primary_workflow_id,
            summary="Primary implementation work",
            metadata={"kind": "primary"},
            created_at=created_at.replace(day=8),
            updated_at=created_at.replace(day=8),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=detour_workflow_id,
            summary="Recent coverage detour",
            metadata={"kind": "detour"},
            created_at=created_at.replace(day=10),
            updated_at=created_at.replace(day=10),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                primary_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TASK-PRIMARY",
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=8),
                    "has_latest_attempt": True,
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "latest_attempt_started_at": created_at.replace(day=8),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=8),
                    "latest_checkpoint_step_name": "resume_primary_work",
                    "latest_checkpoint_summary": "Return to the primary implementation thread",
                    "latest_checkpoint_current_objective": "Finish the hierarchical memory implementation",
                    "latest_checkpoint_next_intended_action": "Resume the primary implementation work",
                },
                detour_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TASK-COVERAGE",
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=10),
                    "has_latest_attempt": True,
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "latest_attempt_started_at": created_at.replace(day=10),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=10),
                    "latest_checkpoint_step_name": "coverage_followup",
                    "latest_checkpoint_summary": "Increase coverage for the recent retrieval changes",
                    "latest_checkpoint_current_objective": None,
                    "latest_checkpoint_next_intended_action": None,
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    assert response.details["task_recall_selected_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_latest_detour_candidate_present"] is True

    latest_detour_candidate_workflow_id = response.details[
        "task_recall_latest_detour_candidate_workflow_instance_id"
    ]
    latest_detour_candidate_details = response.details[
        "task_recall_latest_detour_candidate_details"
    ]

    assert latest_detour_candidate_workflow_id in {
        str(primary_workflow_id),
        str(detour_workflow_id),
    }
    assert response.details["task_recall_latest_detour_candidate_details_present"] is True
    assert (
        latest_detour_candidate_details["workflow_instance_id"]
        == latest_detour_candidate_workflow_id
    )
    assert latest_detour_candidate_details["ticket_detour_like"] is False
    assert latest_detour_candidate_details["checkpoint_detour_like"] is True
    assert latest_detour_candidate_details["detour_like"] is True
    assert latest_detour_candidate_details["workflow_terminal"] is False
    assert latest_detour_candidate_details["has_attempt_signal"] is True
    assert latest_detour_candidate_details["attempt_terminal"] is False
    assert latest_detour_candidate_details["has_checkpoint_signal"] is True
    assert latest_detour_candidate_details["task_thread_basis"] is None


def test_memory_service_task_recall_context_surfaces_prior_mainline_candidate_fields() -> None:
    primary_workflow_id = uuid4()
    detour_workflow_id = uuid4()
    older_background_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=primary_workflow_id,
            summary="Primary implementation work before detour",
            metadata={"kind": "primary"},
            created_at=created_at.replace(day=18),
            updated_at=created_at.replace(day=18),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=detour_workflow_id,
            summary="Latest coverage detour",
            metadata={"kind": "detour"},
            created_at=created_at.replace(day=20),
            updated_at=created_at.replace(day=20),
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=older_background_workflow_id,
            summary="Older background investigation",
            metadata={"kind": "background"},
            created_at=created_at.replace(day=17),
            updated_at=created_at.replace(day=17),
        )
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=InMemoryWorkflowLookupRepository(
            workflows_by_id={
                primary_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TASK-PRIMARY",
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=18),
                    "has_latest_attempt": True,
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "latest_attempt_started_at": created_at.replace(day=18),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=18),
                    "latest_checkpoint_step_name": "resume_primary_work",
                    "latest_checkpoint_summary": "Return to the primary implementation thread",
                    "latest_checkpoint_current_objective": "Finish the hierarchical memory implementation",
                    "latest_checkpoint_next_intended_action": "Resume the primary implementation work",
                },
                detour_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TASK-COVERAGE",
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=20),
                    "has_latest_attempt": True,
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "latest_attempt_started_at": created_at.replace(day=20),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=20),
                    "latest_checkpoint_step_name": "coverage_followup",
                    "latest_checkpoint_summary": "Increase coverage for the recent retrieval changes",
                    "latest_checkpoint_current_objective": None,
                    "latest_checkpoint_next_intended_action": None,
                },
                older_background_workflow_id: {
                    "workspace_id": workspace_id,
                    "ticket_id": "TASK-BACKGROUND",
                    "workflow_status": "in_progress",
                    "workflow_is_terminal": False,
                    "workflow_updated_at": created_at.replace(day=17),
                    "has_latest_attempt": True,
                    "latest_attempt_status": "running",
                    "latest_attempt_is_terminal": False,
                    "latest_attempt_started_at": created_at.replace(day=17),
                    "has_latest_checkpoint": True,
                    "latest_checkpoint_created_at": created_at.replace(day=17),
                    "latest_checkpoint_step_name": "background_investigation",
                    "latest_checkpoint_summary": "Investigate related background issue",
                    "latest_checkpoint_current_objective": None,
                    "latest_checkpoint_next_intended_action": None,
                },
            }
        ),
    )

    response = service.get_context(
        GetMemoryContextRequest(
            workspace_id=workspace_id,
            limit=5,
            include_episodes=True,
            include_memory_items=False,
            include_summaries=False,
        )
    )

    prior_mainline_workflow_id = response.details["task_recall_prior_mainline_workflow_instance_id"]
    prior_mainline_details = response.details["task_recall_prior_mainline_candidate_details"]

    assert response.details["task_recall_prior_mainline_present"] is True
    assert response.details["task_recall_prior_mainline_candidate_details_present"] is True
    assert prior_mainline_workflow_id in {
        str(primary_workflow_id),
        str(older_background_workflow_id),
    }
    assert prior_mainline_details["workflow_instance_id"] == prior_mainline_workflow_id
    assert prior_mainline_details["ticket_detour_like"] is False
    assert prior_mainline_details["checkpoint_detour_like"] is False
    assert prior_mainline_details["detour_like"] is False
    assert prior_mainline_details["workflow_terminal"] is False
    assert prior_mainline_details["has_attempt_signal"] is True
    assert prior_mainline_details["attempt_terminal"] is False
    assert prior_mainline_details["has_checkpoint_signal"] is True

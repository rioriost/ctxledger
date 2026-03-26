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


def test_memory_get_context_includes_episode_explanations_without_query_filter() -> None:
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
    assert response.details["summary_selection_applied"] is True
    assert response.details["summary_selection_kind"] == "episode_summary_first"
    assert response.details["summary_first_has_episode_groups"] is True
    assert response.details["summary_first_is_summary_only"] is False
    assert response.details["summary_first_child_episode_count"] == 2
    assert response.details["summary_first_child_episode_ids"] == [
        str(first_episode.episode_id),
        str(second_episode.episode_id),
    ]
    assert response.details["primary_episode_groups_present_after_query_filter"] is True
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
        "summary_first": 2,
        "episode_direct": 0,
        "workspace_inherited_auxiliary": 0,
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
            "episode": 3,
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
    assert response.details["task_recall_selection_present"] is True
    assert response.details["task_recall_selected_workflow_instance_id"] == str(workflow_id)
    assert response.details["task_recall_latest_workflow_instance_id"] is None
    assert response.details["task_recall_running_workflow_instance_id"] is None
    assert response.details["task_recall_selected_equals_latest"] is False
    assert response.details["task_recall_selected_equals_running"] is False
    assert response.details["task_recall_latest_workflow_terminal"] is False
    assert response.details["task_recall_latest_ticket_detour_like"] is False
    assert response.details["task_recall_latest_checkpoint_detour_like"] is False
    assert response.details["task_recall_selected_ticket_detour_like"] is False
    assert response.details["task_recall_selected_checkpoint_detour_like"] is False
    assert response.details["task_recall_detour_override_applied"] is False
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert response.details["task_recall_latest_vs_selected_explanations"] == [
        {
            "code": "selected_differs_from_latest",
            "message": "selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "latest_and_selected_return_target_basis_differs",
            "message": "latest considered candidate and selected continuation target differed in return-target basis",
        },
        {
            "code": "latest_and_selected_task_thread_basis_differs",
            "message": "latest considered candidate and selected continuation target differed in task-thread basis",
        },
    ]
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "summary_selected_differs_from_latest",
            "message": "summary comparison recorded that the selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_return_target_basis_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in return-target basis",
        },
        {
            "code": "summary_latest_and_selected_task_thread_basis_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
        },
    ]
    assert response.details["task_recall_explanations_present"] is True
    assert response.details["task_recall_explanations"] == [
        {
            "code": "latest_candidate_retained",
            "message": "latest workflow candidate remained the best continuation point",
        }
    ]
    assert response.details["task_recall_ranking_details_present"] is True
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 1
    ranking_entry = ranking_details[0]
    assert ranking_entry["workflow_instance_id"] == str(workflow_id)
    assert ranking_entry["resolver_order"] == 0
    assert ranking_entry["selected"] is True
    assert ranking_entry["is_latest"] is False
    assert ranking_entry["workflow_terminal"] is False
    assert ranking_entry["has_latest_attempt"] is False
    assert ranking_entry["latest_attempt_terminal"] is False
    assert ranking_entry["has_latest_checkpoint"] is False
    assert ranking_entry["ticket_detour_like"] is False
    assert ranking_entry["checkpoint_detour_like"] is False
    assert ranking_entry["checkpoint_has_current_objective"] is False
    assert ranking_entry["checkpoint_has_next_intended_action"] is False
    assert ranking_entry["detour_like"] is False
    assert ranking_entry["explicit_mainline_signal_present"] is False
    assert ranking_entry["return_target_candidate"] is True
    assert ranking_entry["return_target_basis"] == "non_detour_candidate"
    assert ranking_entry["task_thread_candidate"] is True
    assert ranking_entry["task_thread_basis"] == "non_detour_candidate"
    assert ranking_entry["primary_objective_present"] is False
    assert ranking_entry["score"] == 30
    assert [reason["code"] for reason in ranking_entry["reason_list"]] == [
        "workflow_non_terminal_bonus",
        "non_detour_candidate_bonus",
        "selected_candidate",
    ]
    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(workflow_id)
    assert response.details["task_recall_return_target_basis"] == "ranked_candidate"
    assert response.details["task_recall_return_target_source"] == "workflow_selection.ranking"
    assert response.details["task_recall_primary_objective_present"] is False
    assert response.details["task_recall_primary_objective_text"] is None
    assert response.details["task_recall_primary_objective_source"] is None
    assert response.details["task_recall_selected_workflow_terminal"] is False
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


def test_memory_get_context_task_recall_prefers_checkpoint_objective_signal() -> None:
    primary_workflow_id = uuid4()
    detour_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 1, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=primary_workflow_id,
            summary="Primary implementation work",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=detour_workflow_id,
            summary="Coverage detour work",
            metadata={"kind": "coverage"},
            created_at=created_at.replace(day=2),
            updated_at=created_at.replace(day=2),
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            primary_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-PRIMARY",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "implement task recall ranking",
                "latest_checkpoint_summary": "Continue the main feature slice",
                "latest_checkpoint_current_objective": ("Finish the task recall continuation path"),
                "latest_checkpoint_next_intended_action": (
                    "Add ranking signals for primary objective recovery"
                ),
            },
            detour_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "coverage-followup",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=3),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=3),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=3),
                "latest_checkpoint_step_name": "coverage cleanup",
                "latest_checkpoint_summary": "Increase test coverage for recent changes",
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    assert response.details["task_recall_selection_present"] is True
    assert response.details["task_recall_selected_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_latest_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_selected_equals_latest"] is True
    assert response.details["task_recall_latest_ticket_detour_like"] is False
    assert response.details["task_recall_latest_checkpoint_detour_like"] is False
    assert response.details["task_recall_selected_ticket_detour_like"] is False
    assert response.details["task_recall_selected_checkpoint_detour_like"] is False
    assert response.details["task_recall_detour_override_applied"] is False
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert response.details["task_recall_latest_vs_selected_explanations"] == [
        {
            "code": "selected_matches_latest",
            "message": "selected continuation target matched the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_match",
            "message": "latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "summary_selected_matches_latest",
            "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_checkpoints_match",
            "message": "summary comparison recorded that the latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_explanations_present"] is True
    assert response.details["task_recall_explanations"] == [
        {
            "code": "latest_attempt_present",
            "message": "candidate has a latest attempt signal that improves resumability confidence",
        },
        {
            "code": "latest_checkpoint_present",
            "message": "candidate has checkpoint history that improves resumability confidence",
        },
    ]
    assert response.details["task_recall_ranking_details_present"] is True
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 2

    selected_entry = ranking_details[0]
    assert selected_entry["workflow_instance_id"] == str(primary_workflow_id)
    assert selected_entry["resolver_order"] == 0
    assert selected_entry["selected"] is True
    assert selected_entry["is_latest"] is True
    assert selected_entry["workflow_terminal"] is False
    assert selected_entry["has_latest_attempt"] is True
    assert selected_entry["latest_attempt_terminal"] is False
    assert selected_entry["has_latest_checkpoint"] is True
    assert selected_entry["ticket_detour_like"] is False
    assert selected_entry["checkpoint_has_current_objective"] is True
    assert selected_entry["checkpoint_has_next_intended_action"] is True
    assert selected_entry["explicit_mainline_signal_present"] is True
    assert selected_entry["score"] >= 35
    assert [reason["code"] for reason in selected_entry["reason_list"]] == [
        "latest_candidate",
        "workflow_non_terminal_bonus",
        "latest_attempt_present_bonus",
        "latest_checkpoint_present_bonus",
        "checkpoint_current_objective_bonus",
        "checkpoint_next_intended_action_bonus",
        "selected_candidate",
    ]

    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(
        primary_workflow_id
    )
    assert response.details["task_recall_return_target_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_return_target_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_primary_objective_present"] is True
    assert (
        response.details["task_recall_primary_objective_text"]
        == "Finish the task recall continuation path"
    )
    assert (
        response.details["task_recall_primary_objective_source"]
        == "latest_checkpoint.current_objective"
    )

    detour_entry = ranking_details[1]
    assert detour_entry["workflow_instance_id"] == str(detour_workflow_id)
    assert detour_entry["resolver_order"] == 1
    assert detour_entry["selected"] is False
    assert detour_entry["is_latest"] is False
    assert detour_entry["workflow_terminal"] is False
    assert detour_entry["has_latest_attempt"] is True
    assert detour_entry["latest_attempt_terminal"] is False
    assert detour_entry["has_latest_checkpoint"] is True
    assert detour_entry["checkpoint_has_current_objective"] is False
    assert detour_entry["checkpoint_has_next_intended_action"] is False
    assert detour_entry["explicit_mainline_signal_present"] is False
    assert detour_entry["score"] <= selected_entry["score"]
    assert "non_detour_candidate_bonus" not in [
        reason["code"] for reason in detour_entry["reason_list"]
    ]
    assert "checkpoint_current_objective_bonus" not in [
        reason["code"] for reason in detour_entry["reason_list"]
    ]
    assert "checkpoint_next_intended_action_bonus" not in [
        reason["code"] for reason in detour_entry["reason_list"]
    ]
    assert "ticket_detour_like_penalty" in [
        reason["code"] for reason in detour_entry["reason_list"]
    ] or "checkpoint_detour_like_penalty" in [
        reason["code"] for reason in detour_entry["reason_list"]
    ]


def test_memory_get_context_task_recall_marks_next_action_as_explicit_mainline_signal() -> None:
    workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 10, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=workflow_id,
            summary="Resume the main implementation thread",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-NEXT-ACTION",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "resume main feature",
                "latest_checkpoint_summary": "Prepare the next mainline change",
                "latest_checkpoint_current_objective": "",
                "latest_checkpoint_next_intended_action": (
                    "Finish the primary continuation path after the detour"
                ),
            }
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    assert response.details["task_recall_selection_present"] is True
    assert response.details["task_recall_selected_workflow_instance_id"] == str(workflow_id)
    assert response.details["task_recall_selected_equals_latest"] is True
    assert response.details["task_recall_detour_override_applied"] is False
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert response.details["task_recall_latest_vs_selected_explanations"] == [
        {
            "code": "selected_matches_latest",
            "message": "selected continuation target matched the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_match",
            "message": "latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "summary_selected_matches_latest",
            "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_checkpoints_match",
            "message": "summary comparison recorded that the latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_ranking_details_present"] is True
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 1
    ranking_entry = ranking_details[0]
    assert ranking_entry["workflow_instance_id"] == str(workflow_id)
    assert ranking_entry["resolver_order"] == 0
    assert ranking_entry["selected"] is True
    assert ranking_entry["is_latest"] is True
    assert ranking_entry["workflow_terminal"] is False
    assert ranking_entry["has_latest_attempt"] is True
    assert ranking_entry["latest_attempt_terminal"] is False
    assert ranking_entry["has_latest_checkpoint"] is True
    assert ranking_entry["ticket_detour_like"] is False
    assert ranking_entry["checkpoint_has_current_objective"] is False
    assert ranking_entry["checkpoint_has_next_intended_action"] is True
    assert ranking_entry["detour_like"] is False
    assert ranking_entry["explicit_mainline_signal_present"] is True
    assert ranking_entry["return_target_candidate"] is True
    assert ranking_entry["return_target_basis"] == "checkpoint_next_intended_action"
    assert ranking_entry["task_thread_candidate"] is True
    assert ranking_entry["task_thread_basis"] == "checkpoint_objective_or_next_action"
    assert ranking_entry["primary_objective_present"] is False
    assert ranking_entry["score"] >= 35
    assert [reason["code"] for reason in ranking_entry["reason_list"]] == [
        "latest_candidate",
        "workflow_non_terminal_bonus",
        "latest_attempt_present_bonus",
        "latest_checkpoint_present_bonus",
        "checkpoint_next_intended_action_bonus",
        "selected_candidate",
    ]
    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(workflow_id)
    assert response.details["task_recall_return_target_basis"] == "checkpoint_next_intended_action"
    assert (
        response.details["task_recall_return_target_source"]
        == "latest_checkpoint.next_intended_action"
    )
    assert response.details["task_recall_primary_objective_present"] is False
    assert response.details["task_recall_primary_objective_text"] is None
    assert response.details["task_recall_primary_objective_source"] is None
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_next_intended_action"
    assert (
        response.details["task_recall_task_thread_source"]
        == "latest_checkpoint.next_intended_action"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == "resume main feature"
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Prepare the next mainline change"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(workflow_id),
        "selected_workflow_instance_id": str(workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "selected": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(workflow_id),
        "selected_workflow_instance_id": str(workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "selected": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(workflow_id),
        "selected_workflow_instance_id": str(workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "selected": {
            "workflow_instance_id": str(workflow_id),
            "checkpoint_step_name": "resume main feature",
            "checkpoint_summary": "Prepare the next mainline change",
            "primary_objective_text": None,
            "next_intended_action_text": "Finish the primary continuation path after the detour",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_prior_mainline_present"] is False
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] is None
    assert response.details["memory_context_groups"] == []


def test_memory_get_context_task_recall_separates_latest_detour_candidate_from_selected_continuation_target() -> (
    None
):
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
    assert response.details["task_recall_latest_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_selected_equals_latest"] is True
    assert response.details["task_recall_latest_detour_candidate_present"] is True
    latest_detour_candidate_workflow_id = response.details[
        "task_recall_latest_detour_candidate_workflow_instance_id"
    ]
    assert latest_detour_candidate_workflow_id in {
        str(primary_workflow_id),
        str(detour_workflow_id),
    }
    assert response.details["task_recall_latest_detour_candidate_details_present"] is True
    assert response.details["task_recall_latest_detour_candidate_details"] == {
        "workflow_instance_id": latest_detour_candidate_workflow_id,
        "checkpoint_step_name": (
            "coverage_followup"
            if latest_detour_candidate_workflow_id == str(detour_workflow_id)
            else "resume_primary_work"
        ),
        "checkpoint_summary": (
            "Increase coverage for the recent retrieval changes"
            if latest_detour_candidate_workflow_id == str(detour_workflow_id)
            else "Return to the primary implementation thread"
        ),
        "primary_objective_text": (
            None
            if latest_detour_candidate_workflow_id == str(detour_workflow_id)
            else "Finish the hierarchical memory implementation"
        ),
        "next_intended_action_text": (
            None
            if latest_detour_candidate_workflow_id == str(detour_workflow_id)
            else "Resume the primary implementation work"
        ),
        "ticket_detour_like": False,
        "checkpoint_detour_like": True,
        "detour_like": True,
        "workflow_terminal": False,
        "has_attempt_signal": True,
        "attempt_terminal": False,
        "has_checkpoint_signal": True,
        "return_target_basis": (
            None
            if latest_detour_candidate_workflow_id == str(detour_workflow_id)
            else "latest_candidate"
        ),
        "task_thread_basis": None,
    }
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert {
        explanation["code"]
        for explanation in response.details["task_recall_latest_vs_selected_explanations"]
    } == {
        "selected_matches_latest",
        "latest_and_selected_checkpoints_match",
    }
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert {
        explanation["code"]
        for explanation in response.details["task_recall_comparison_summary_explanations"]
    } == {
        "summary_selected_matches_latest",
        "summary_latest_and_selected_checkpoints_match",
    }
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(
        primary_workflow_id
    )
    assert response.details["task_recall_return_target_basis"] == "checkpoint_current_objective"
    assert response.details["task_recall_return_target_source"] == (
        "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_primary_objective_present"] is True
    assert response.details["task_recall_primary_objective_text"] == (
        "Finish the hierarchical memory implementation"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == "resume_primary_work"
    assert response.details["task_recall_selected_checkpoint_summary"] == (
        "Return to the primary implementation thread"
    )
    assert response.details["task_recall_ranking_details_present"] is True
    assert response.details["task_recall_ranking_details"][0]["workflow_instance_id"] == str(
        primary_workflow_id
    )
    assert response.details["task_recall_ranking_details"][0]["selected"] is True
    assert response.details["task_recall_ranking_details"][0]["is_latest"] is True
    assert response.details["task_recall_ranking_details"][1]["workflow_instance_id"] == str(
        detour_workflow_id
    )
    assert response.details["task_recall_ranking_details"][1]["selected"] is False
    assert response.details["task_recall_ranking_details"][1]["is_latest"] is False


def test_memory_get_context_task_recall_prefers_current_objective_over_non_detour_candidate() -> (
    None
):
    objective_workflow_id = uuid4()
    non_detour_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 20, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=objective_workflow_id,
            summary="Primary implementation thread",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=non_detour_workflow_id,
            summary="General feature follow-up",
            metadata={"kind": "feature"},
            created_at=created_at.replace(day=21),
            updated_at=created_at.replace(day=21),
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            objective_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-OBJECTIVE",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "resume primary implementation",
                "latest_checkpoint_summary": "Continue the main feature slice",
                "latest_checkpoint_current_objective": "Land the return-target detail surface",
                "latest_checkpoint_next_intended_action": None,
            },
            non_detour_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-GENERAL",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=22),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=22),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=22),
                "latest_checkpoint_step_name": "continue implementation",
                "latest_checkpoint_summary": "Continue implementation follow-up",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    assert response.details["task_recall_selected_workflow_instance_id"] == str(
        objective_workflow_id
    )
    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(
        objective_workflow_id
    )
    assert response.details["task_recall_return_target_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_return_target_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_primary_objective_present"] is True
    assert (
        response.details["task_recall_primary_objective_text"]
        == "Land the return-target detail surface"
    )
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 2
    selected_entry = ranking_details[0]
    fallback_entry = ranking_details[1]
    assert selected_entry["workflow_instance_id"] == str(objective_workflow_id)
    assert selected_entry["return_target_basis"] == "checkpoint_current_objective"
    assert selected_entry["task_thread_candidate"] is True
    assert selected_entry["task_thread_basis"] == "checkpoint_objective_or_next_action"
    assert selected_entry["primary_objective_present"] is True
    assert [reason["code"] for reason in selected_entry["reason_list"]] == [
        "latest_candidate",
        "workflow_non_terminal_bonus",
        "latest_attempt_present_bonus",
        "latest_checkpoint_present_bonus",
        "checkpoint_current_objective_bonus",
        "selected_candidate",
    ]
    assert fallback_entry["workflow_instance_id"] == str(non_detour_workflow_id)
    assert fallback_entry["return_target_basis"] == "non_detour_candidate"
    assert fallback_entry["task_thread_candidate"] is True
    assert fallback_entry["task_thread_basis"] == "non_detour_candidate"
    assert fallback_entry["primary_objective_present"] is False
    assert "non_detour_candidate_bonus" in [
        reason["code"] for reason in fallback_entry["reason_list"]
    ]
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_task_thread_source"] == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == (
        "resume primary implementation"
    )
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Continue the main feature slice"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(objective_workflow_id),
        "selected_workflow_instance_id": str(objective_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(objective_workflow_id),
        "selected_workflow_instance_id": str(objective_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(objective_workflow_id),
        "selected_workflow_instance_id": str(objective_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(objective_workflow_id),
            "checkpoint_step_name": "resume primary implementation",
            "checkpoint_summary": "Continue the main feature slice",
            "primary_objective_text": "Land the return-target detail surface",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_prior_mainline_present"] is False
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] is None


def test_memory_get_context_task_recall_prefers_next_action_over_non_detour_candidate() -> None:
    next_action_workflow_id = uuid4()
    non_detour_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 23, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=next_action_workflow_id,
            summary="Primary next-action workflow",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=non_detour_workflow_id,
            summary="Secondary continuation workflow",
            metadata={"kind": "feature"},
            created_at=created_at.replace(day=24),
            updated_at=created_at.replace(day=24),
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            next_action_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-NEXT-ACTION-ONLY",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "resume after interruption",
                "latest_checkpoint_summary": "Pick up the next main action",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": "Wire return-target fields into details",
            },
            non_detour_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-SECONDARY",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=25),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=25),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=25),
                "latest_checkpoint_step_name": "continue implementation",
                "latest_checkpoint_summary": "Continue implementation follow-up",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    assert response.details["task_recall_selected_workflow_instance_id"] == str(
        next_action_workflow_id
    )
    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(
        next_action_workflow_id
    )
    assert response.details["task_recall_return_target_basis"] == "checkpoint_next_intended_action"
    assert response.details["task_recall_return_target_source"] == (
        "latest_checkpoint.next_intended_action"
    )
    assert response.details["task_recall_primary_objective_present"] is False
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 2
    selected_entry = ranking_details[0]
    fallback_entry = ranking_details[1]
    assert selected_entry["workflow_instance_id"] == str(next_action_workflow_id)
    assert selected_entry["return_target_basis"] == "checkpoint_next_intended_action"
    assert selected_entry["task_thread_candidate"] is True
    assert selected_entry["task_thread_basis"] == "checkpoint_objective_or_next_action"
    assert [reason["code"] for reason in selected_entry["reason_list"]] == [
        "latest_candidate",
        "workflow_non_terminal_bonus",
        "latest_attempt_present_bonus",
        "latest_checkpoint_present_bonus",
        "checkpoint_next_intended_action_bonus",
        "selected_candidate",
    ]
    assert fallback_entry["workflow_instance_id"] == str(non_detour_workflow_id)
    assert fallback_entry["return_target_basis"] == "non_detour_candidate"
    assert fallback_entry["task_thread_candidate"] is True
    assert fallback_entry["task_thread_basis"] == "non_detour_candidate"
    assert "non_detour_candidate_bonus" in [
        reason["code"] for reason in fallback_entry["reason_list"]
    ]
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_next_intended_action"
    assert (
        response.details["task_recall_task_thread_source"]
        == "latest_checkpoint.next_intended_action"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == (
        "resume after interruption"
    )
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Pick up the next main action"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(next_action_workflow_id),
        "selected_workflow_instance_id": str(next_action_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(next_action_workflow_id),
            "checkpoint_step_name": "resume after interruption",
            "checkpoint_summary": "Pick up the next main action",
            "primary_objective_text": None,
            "next_intended_action_text": "Wire return-target fields into details",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "selected": {
            "workflow_instance_id": str(next_action_workflow_id),
            "checkpoint_step_name": "resume after interruption",
            "checkpoint_summary": "Pick up the next main action",
            "primary_objective_text": None,
            "next_intended_action_text": "Wire return-target fields into details",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(next_action_workflow_id),
        "selected_workflow_instance_id": str(next_action_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(next_action_workflow_id),
            "checkpoint_step_name": "resume after interruption",
            "checkpoint_summary": "Pick up the next main action",
            "primary_objective_text": None,
            "next_intended_action_text": "Wire return-target fields into details",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "selected": {
            "workflow_instance_id": str(next_action_workflow_id),
            "checkpoint_step_name": "resume after interruption",
            "checkpoint_summary": "Pick up the next main action",
            "primary_objective_text": None,
            "next_intended_action_text": "Wire return-target fields into details",
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_next_intended_action",
            "task_thread_basis": "checkpoint_next_intended_action",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_prior_mainline_present"] is False
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] is None


def test_memory_get_context_task_recall_recovers_prior_mainline_candidate_before_latest_detour() -> (
    None
):
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

    assert response.details["task_recall_selected_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_latest_workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_latest_detour_candidate_present"] is True
    latest_detour_candidate_workflow_id = response.details[
        "task_recall_latest_detour_candidate_workflow_instance_id"
    ]
    assert latest_detour_candidate_workflow_id in {
        str(primary_workflow_id),
        str(detour_workflow_id),
    }
    assert response.details["task_recall_latest_detour_candidate_details_present"] is True
    latest_detour_candidate_details = response.details[
        "task_recall_latest_detour_candidate_details"
    ]
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

    prior_mainline_workflow_id = response.details["task_recall_prior_mainline_workflow_instance_id"]
    assert prior_mainline_workflow_id in {
        str(primary_workflow_id),
        str(older_background_workflow_id),
    }
    assert response.details["task_recall_prior_mainline_present"] is True
    assert response.details["task_recall_prior_mainline_candidate_details_present"] is True
    prior_mainline_details = response.details["task_recall_prior_mainline_candidate_details"]
    assert prior_mainline_details["workflow_instance_id"] == prior_mainline_workflow_id
    assert prior_mainline_details["ticket_detour_like"] is False
    assert prior_mainline_details["checkpoint_detour_like"] is False
    assert prior_mainline_details["detour_like"] is False
    assert prior_mainline_details["workflow_terminal"] is False
    assert prior_mainline_details["has_attempt_signal"] is True
    assert prior_mainline_details["attempt_terminal"] is False
    assert prior_mainline_details["has_checkpoint_signal"] is True

    latest_vs_selected = response.details["task_recall_latest_vs_selected_candidate_details"]
    assert latest_vs_selected["latest_workflow_instance_id"] == str(primary_workflow_id)
    assert latest_vs_selected["selected_workflow_instance_id"] == str(primary_workflow_id)
    assert latest_vs_selected["comparison_source"] == "task_recall_checkpoint_comparison"
    assert latest_vs_selected["latest_considered"]["workflow_instance_id"] == str(
        primary_workflow_id
    )
    assert latest_vs_selected["selected"]["workflow_instance_id"] == str(primary_workflow_id)
    assert response.details["task_recall_explanations_present"] is True
    assert {
        explanation["code"]
        for explanation in response.details["task_recall_latest_vs_selected_explanations"]
    } == {
        "selected_matches_latest",
        "latest_and_selected_checkpoints_match",
    }


def test_memory_get_context_task_recall_keeps_detour_penalty_when_objective_text_is_detour_like() -> (
    None
):
    detour_like_objective_workflow_id = uuid4()
    stable_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 26, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=detour_like_objective_workflow_id,
            summary="Coverage-oriented objective workflow",
            metadata={"kind": "coverage"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=stable_workflow_id,
            summary="Stable implementation workflow",
            metadata={"kind": "feature"},
            created_at=created_at.replace(day=27),
            updated_at=created_at.replace(day=27),
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            detour_like_objective_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-COVERAGE",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "coverage follow-up",
                "latest_checkpoint_summary": "Coverage cleanup after the main change",
                "latest_checkpoint_current_objective": "Coverage cleanup and docs review",
                "latest_checkpoint_next_intended_action": None,
            },
            stable_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-STABLE",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=28),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=28),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=28),
                "latest_checkpoint_step_name": "resume main implementation",
                "latest_checkpoint_summary": "Resume the main implementation thread",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 2
    objective_entry = next(
        entry
        for entry in ranking_details
        if entry["workflow_instance_id"] == str(detour_like_objective_workflow_id)
    )
    stable_entry = next(
        entry
        for entry in ranking_details
        if entry["workflow_instance_id"] == str(stable_workflow_id)
    )
    assert objective_entry["detour_like"] is True
    assert objective_entry["primary_objective_present"] is True
    assert objective_entry["return_target_basis"] == "checkpoint_current_objective"
    assert objective_entry["task_thread_candidate"] is True
    assert objective_entry["task_thread_basis"] == "checkpoint_objective_or_next_action"
    assert "checkpoint_current_objective_bonus" not in [
        reason["code"] for reason in objective_entry["reason_list"]
    ]
    assert "non_detour_candidate_bonus" not in [
        reason["code"] for reason in objective_entry["reason_list"]
    ]
    assert "ticket_detour_like_penalty" in [
        reason["code"] for reason in objective_entry["reason_list"]
    ] or "checkpoint_detour_like_penalty" in [
        reason["code"] for reason in objective_entry["reason_list"]
    ]
    assert stable_entry["workflow_instance_id"] == str(stable_workflow_id)
    assert stable_entry["task_thread_candidate"] is True
    assert stable_entry["task_thread_basis"] == "non_detour_candidate"
    assert response.details["task_recall_latest_detour_candidate_present"] is True
    latest_detour_candidate_workflow_id = response.details[
        "task_recall_latest_detour_candidate_workflow_instance_id"
    ]
    assert latest_detour_candidate_workflow_id in {
        str(detour_like_objective_workflow_id),
        str(stable_workflow_id),
    }
    assert response.details["task_recall_latest_detour_candidate_details_present"] is True
    latest_detour_candidate_details = response.details[
        "task_recall_latest_detour_candidate_details"
    ]
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

    assert response.details["task_recall_primary_objective_present"] is True
    assert (
        response.details["task_recall_primary_objective_text"] == "Coverage cleanup and docs review"
    )
    assert (
        response.details["task_recall_primary_objective_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_task_thread_source"] == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == "coverage follow-up"
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Coverage cleanup after the main change"
    )
    assert response.details["task_recall_latest_considered_checkpoint_step_name"] == (
        "coverage follow-up"
    )
    assert response.details["task_recall_latest_considered_checkpoint_summary"] == (
        "Coverage cleanup after the main change"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    latest_vs_selected_checkpoint = response.details[
        "task_recall_latest_vs_selected_checkpoint_details"
    ]
    assert latest_vs_selected_checkpoint["latest_workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_checkpoint["selected_workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_checkpoint["comparison_source"] == "task_recall_checkpoint_comparison"
    assert latest_vs_selected_checkpoint["latest_considered"]["workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_checkpoint["selected"]["workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    latest_vs_selected_candidate = response.details[
        "task_recall_latest_vs_selected_candidate_details"
    ]
    assert latest_vs_selected_candidate["latest_workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_candidate["selected_workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_candidate["comparison_source"] == "task_recall_checkpoint_comparison"
    assert latest_vs_selected_candidate["latest_considered"]["workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert latest_vs_selected_candidate["selected"]["workflow_instance_id"] == str(
        detour_like_objective_workflow_id
    )
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_prior_mainline_present"] is True
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] == str(
        stable_workflow_id
    )
    assert response.details["task_recall_prior_mainline_candidate_details_present"] is True
    assert response.details["task_recall_prior_mainline_candidate_details"] == {
        "workflow_instance_id": str(stable_workflow_id),
        "checkpoint_step_name": "resume main implementation",
        "checkpoint_summary": "Resume the main implementation thread",
        "primary_objective_text": None,
        "next_intended_action_text": None,
        "ticket_detour_like": False,
        "checkpoint_detour_like": False,
        "detour_like": False,
        "workflow_terminal": False,
        "has_attempt_signal": True,
        "attempt_terminal": False,
        "has_checkpoint_signal": True,
        "return_target_basis": "non_detour_candidate",
        "task_thread_basis": "non_detour_candidate",
    }


def test_memory_get_context_surfaces_objective_selected_task_thread_details_under_current_ordering() -> (
    None
):
    prior_mainline_workflow_id = uuid4()
    newer_detour_workflow_id = uuid4()
    workspace_id = str(uuid4())
    created_at = datetime(2024, 4, 30, tzinfo=UTC)

    episode_repository = InMemoryEpisodeRepository()
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=prior_mainline_workflow_id,
            summary="Older primary implementation workflow",
            metadata={"kind": "feature"},
            created_at=created_at,
            updated_at=created_at,
        )
    )
    episode_repository.create(
        EpisodeRecord(
            episode_id=uuid4(),
            workflow_instance_id=newer_detour_workflow_id,
            summary="Newer coverage detour workflow",
            metadata={"kind": "coverage"},
            created_at=created_at.replace(day=1),
            updated_at=created_at.replace(day=1),
        )
    )

    workflow_lookup = InMemoryWorkflowLookupRepository(
        workflows_by_id={
            prior_mainline_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-RECALL-PRIMARY-OLDER",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at,
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at,
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at,
                "latest_checkpoint_step_name": "resume_primary_thread",
                "latest_checkpoint_summary": "Continue the primary implementation thread",
                "latest_checkpoint_current_objective": "Finish the main workflow before returning to side work",
                "latest_checkpoint_next_intended_action": None,
            },
            newer_detour_workflow_id: {
                "workspace_id": workspace_id,
                "ticket_id": "TASK-COVERAGE-DET-OLDER",
                "workflow_status": "in_progress",
                "workflow_is_terminal": False,
                "workflow_updated_at": created_at.replace(day=2),
                "has_latest_attempt": True,
                "latest_attempt_status": "running",
                "latest_attempt_is_terminal": False,
                "latest_attempt_started_at": created_at.replace(day=2),
                "has_latest_checkpoint": True,
                "latest_checkpoint_created_at": created_at.replace(day=2),
                "latest_checkpoint_step_name": "coverage_followup",
                "latest_checkpoint_summary": "Increase coverage for recent task recall changes",
                "latest_checkpoint_current_objective": None,
                "latest_checkpoint_next_intended_action": None,
            },
        }
    )

    service = MemoryService(
        episode_repository=episode_repository,
        workflow_lookup=workflow_lookup,
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

    assert response.details["task_recall_selected_workflow_instance_id"] == str(
        prior_mainline_workflow_id
    )
    assert response.details["task_recall_latest_workflow_instance_id"] == str(
        prior_mainline_workflow_id
    )
    assert response.details["task_recall_selected_equals_latest"] is True
    assert response.details["task_recall_latest_ticket_detour_like"] is False
    assert response.details["task_recall_latest_checkpoint_detour_like"] is False
    assert response.details["task_recall_selected_ticket_detour_like"] is False
    assert response.details["task_recall_selected_checkpoint_detour_like"] is False
    assert response.details["task_recall_detour_override_applied"] is False
    assert response.details["task_recall_latest_vs_selected_explanations_present"] is True
    assert response.details["task_recall_latest_vs_selected_explanations"] == [
        {
            "code": "selected_matches_latest",
            "message": "selected continuation target matched the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_match",
            "message": "latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_comparison_summary_explanations_present"] is True
    assert response.details["task_recall_comparison_summary_explanations"] == [
        {
            "code": "summary_selected_matches_latest",
            "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_checkpoints_match",
            "message": "summary comparison recorded that the latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]
    assert response.details["task_recall_return_target_present"] is True
    assert response.details["task_recall_return_target_workflow_instance_id"] == str(
        prior_mainline_workflow_id
    )
    assert response.details["task_recall_return_target_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_return_target_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_task_thread_present"] is True
    assert response.details["task_recall_task_thread_basis"] == "checkpoint_current_objective"
    assert (
        response.details["task_recall_task_thread_source"] == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_selected_checkpoint_step_name"] == (
        "resume_primary_thread"
    )
    assert (
        response.details["task_recall_selected_checkpoint_summary"]
        == "Continue the primary implementation thread"
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(prior_mainline_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_candidate_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_candidate_details"] == {
        "latest_workflow_instance_id": str(prior_mainline_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_latest_vs_selected_primary_block"] == "candidate_details"
    assert (
        response.details["task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias"]
        is True
    )
    assert response.details["task_recall_latest_vs_selected_checkpoint_details_present"] is True
    assert response.details["task_recall_latest_vs_selected_checkpoint_details"] == {
        "latest_workflow_instance_id": str(prior_mainline_workflow_id),
        "selected_workflow_instance_id": str(prior_mainline_workflow_id),
        "latest_considered": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "selected": {
            "workflow_instance_id": str(prior_mainline_workflow_id),
            "checkpoint_step_name": "resume_primary_thread",
            "checkpoint_summary": "Continue the primary implementation thread",
            "primary_objective_text": "Finish the main workflow before returning to side work",
            "next_intended_action_text": None,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "workflow_terminal": False,
            "has_attempt_signal": True,
            "attempt_terminal": False,
            "has_checkpoint_signal": True,
            "return_target_basis": "checkpoint_current_objective",
            "task_thread_basis": "checkpoint_current_objective",
        },
        "same_checkpoint_details": True,
        "comparison_source": "task_recall_checkpoint_comparison",
    }
    assert response.details["task_recall_prior_mainline_present"] is False
    assert response.details["task_recall_prior_mainline_workflow_instance_id"] is None
    assert response.details["task_recall_primary_objective_present"] is True
    assert (
        response.details["task_recall_primary_objective_text"]
        == "Finish the main workflow before returning to side work"
    )
    assert (
        response.details["task_recall_primary_objective_source"]
        == "latest_checkpoint.current_objective"
    )
    assert response.details["task_recall_explanations_present"] is True
    assert response.details["task_recall_explanations"] == [
        {
            "code": "latest_attempt_present",
            "message": "candidate has a latest attempt signal that improves resumability confidence",
        },
        {
            "code": "latest_checkpoint_present",
            "message": "candidate has checkpoint history that improves resumability confidence",
        },
    ]
    ranking_details = response.details["task_recall_ranking_details"]
    assert len(ranking_details) == 2
    selected_entry = ranking_details[0]
    latest_entry = ranking_details[1]
    assert selected_entry["workflow_instance_id"] == str(prior_mainline_workflow_id)
    assert selected_entry["selected"] is True
    assert selected_entry["is_latest"] is True
    assert selected_entry["return_target_basis"] == "checkpoint_current_objective"
    assert selected_entry["task_thread_candidate"] is True
    assert selected_entry["task_thread_basis"] == "checkpoint_objective_or_next_action"
    assert selected_entry["primary_objective_present"] is True
    assert [reason["code"] for reason in selected_entry["reason_list"]] == [
        "latest_candidate",
        "workflow_non_terminal_bonus",
        "latest_attempt_present_bonus",
        "latest_checkpoint_present_bonus",
        "checkpoint_current_objective_bonus",
        "selected_candidate",
    ]
    assert latest_entry["workflow_instance_id"] == str(newer_detour_workflow_id)
    assert latest_entry["selected"] is False
    assert latest_entry["is_latest"] is False
    assert latest_entry["return_target_basis"] == "detour_penalized_candidate"
    assert latest_entry["task_thread_candidate"] is False
    assert latest_entry["task_thread_basis"] == "detour_penalized_candidate"
    assert latest_entry["primary_objective_present"] is False
    assert "ticket_detour_like_penalty" in [
        reason["code"] for reason in latest_entry["reason_list"]
    ] or "checkpoint_detour_like_penalty" in [
        reason["code"] for reason in latest_entry["reason_list"]
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
    assert response.details["memory_item_counts_by_episode"] == {str(episode.episode_id): 1}
    assert response.details["summaries"] == []
    assert response.details["summary_selection_applied"] is False
    assert response.details["summary_selection_kind"] is None

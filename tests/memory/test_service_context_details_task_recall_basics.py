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
                "provenance_kind": "other",
                "interaction_role": None,
                "interaction_kind": None,
                "file_name": None,
                "file_path": None,
                "file_operation": None,
                "purpose": None,
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
                "provenance_kind": "episode_memory",
                "interaction_role": None,
                "interaction_kind": None,
                "file_name": None,
                "file_path": None,
                "file_operation": None,
                "purpose": None,
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
                "provenance_kind": "episode_memory",
                "interaction_role": None,
                "interaction_kind": None,
                "file_name": None,
                "file_path": None,
                "file_operation": None,
                "purpose": None,
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
    assert len(response.details["summaries"]) == 2
    assert response.details["summaries"][0]["episode_id"] == str(first_episode.episode_id)
    assert response.details["summaries"][0]["workflow_instance_id"] == str(workflow_id)
    assert response.details["summaries"][0]["memory_item_count"] == 2
    assert response.details["summaries"][0]["memory_item_types"] == [
        "checkpoint_note",
        "episode_note",
    ]
    assert response.details["summaries"][0]["memory_item_provenance"] == [
        "checkpoint",
        "episode",
    ]
    assert "remember_path_explainability" in response.details["summaries"][0]
    assert response.details["summaries"][1]["episode_id"] == str(second_episode.episode_id)
    assert response.details["summaries"][1]["workflow_instance_id"] == str(workflow_id)
    assert response.details["summaries"][1]["memory_item_count"] == 1
    assert response.details["summaries"][1]["memory_item_types"] == ["episode_note"]
    assert response.details["summaries"][1]["memory_item_provenance"] == ["episode"]
    assert "remember_path_explainability" in response.details["summaries"][1]
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

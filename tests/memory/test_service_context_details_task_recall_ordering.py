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

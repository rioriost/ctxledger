from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ctxledger.runtime.task_recall import (
    build_checkpoint_current_objective_bonus_reason,
    build_checkpoint_detour_like_penalty_reason,
    build_checkpoint_next_intended_action_bonus_reason,
    build_comparison_summary_explanations,
    build_detour_like_signal_details,
    build_latest_attempt_present_bonus_reason,
    build_latest_attempt_present_explanations,
    build_latest_attempt_terminal_explanations,
    build_latest_attempt_terminal_penalty_reason,
    build_latest_candidate_reason,
    build_latest_candidate_retained_explanations,
    build_latest_checkpoint_present_bonus_reason,
    build_latest_checkpoint_present_explanations,
    build_latest_vs_selected_explanations,
    build_non_detour_candidate_bonus_reason,
    build_resumability_explanations,
    build_running_workflow_priority_reason,
    build_selected_candidate_reason,
    build_task_recall_detour_override_applied,
    build_task_recall_ranking_entry,
    build_ticket_detour_like_penalty_reason,
    build_workflow_non_terminal_bonus_reason,
    build_workflow_terminal_penalty_reason,
    checkpoint_detour_text,
    checkpoint_mainline_signal_details,
    default_workspace_resume_selection_signals,
    workflow_ticket_is_detour_like,
)


def test_build_latest_candidate_retained_explanations_returns_expected_payload() -> None:
    assert build_latest_candidate_retained_explanations() == [
        {
            "code": "latest_candidate_retained",
            "message": "latest workflow candidate remained the best continuation point",
        }
    ]


def test_shared_candidate_reason_helpers_return_expected_payloads() -> None:
    assert build_workflow_terminal_penalty_reason() == {
        "code": "workflow_terminal_penalty",
        "message": "terminal workflows are less suitable for continuation",
        "impact": -25,
    }
    assert build_workflow_non_terminal_bonus_reason() == {
        "code": "workflow_non_terminal_bonus",
        "message": "non-terminal workflows are preferred for continuation",
        "impact": 25,
    }
    assert build_ticket_detour_like_penalty_reason() == {
        "code": "ticket_detour_like_penalty",
        "message": "workflow ticket looked detour-like",
        "impact": -10,
    }
    assert build_checkpoint_detour_like_penalty_reason() == {
        "code": "checkpoint_detour_like_penalty",
        "message": "latest checkpoint looked detour-like",
        "impact": -10,
    }
    assert build_non_detour_candidate_bonus_reason(impact=5) == {
        "code": "non_detour_candidate_bonus",
        "message": "candidate avoids detour-like wording and remains continuation-friendly",
        "impact": 5,
    }
    assert build_checkpoint_current_objective_bonus_reason(impact=10) == {
        "code": "checkpoint_current_objective_bonus",
        "message": "latest checkpoint carries an explicit current objective",
        "impact": 10,
    }
    assert build_checkpoint_next_intended_action_bonus_reason(impact=5) == {
        "code": "checkpoint_next_intended_action_bonus",
        "message": "latest checkpoint carries an explicit next intended action",
        "impact": 5,
    }
    assert build_latest_candidate_reason(context="resume") == {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for resume",
    }
    assert build_latest_candidate_reason(context="continuation") == {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for continuation",
    }
    assert build_selected_candidate_reason(context="workspace_resume") == {
        "code": "selected_candidate",
        "message": "candidate was selected after applying workspace resume heuristics",
    }
    assert build_selected_candidate_reason(context="task_recall") == {
        "code": "selected_candidate",
        "message": "candidate was selected after applying task recall heuristics",
    }


def test_remaining_shared_ranking_reason_helpers_return_expected_payloads() -> None:
    assert build_running_workflow_priority_reason() == {
        "code": "running_workflow_priority",
        "message": "running workflows are prioritized for continuation",
        "impact": 100,
    }
    assert build_latest_attempt_present_bonus_reason() == {
        "code": "latest_attempt_present_bonus",
        "message": "candidate has a latest attempt signal available",
        "impact": 5,
    }
    assert build_latest_attempt_terminal_penalty_reason() == {
        "code": "latest_attempt_terminal_penalty",
        "message": "latest attempt is terminal, reducing continuation confidence",
        "impact": -5,
    }
    assert build_latest_checkpoint_present_bonus_reason() == {
        "code": "latest_checkpoint_present_bonus",
        "message": "candidate has checkpoint history for resumability",
        "impact": 5,
    }


def test_resumability_explanation_helpers_return_expected_payloads() -> None:
    assert build_latest_attempt_present_explanations() == [
        {
            "code": "latest_attempt_present",
            "message": "candidate has a latest attempt signal that improves resumability confidence",
        }
    ]
    assert build_latest_attempt_terminal_explanations() == [
        {
            "code": "latest_attempt_terminal",
            "message": "candidate's latest attempt was terminal, reducing resumability confidence",
        }
    ]
    assert build_latest_checkpoint_present_explanations() == [
        {
            "code": "latest_checkpoint_present",
            "message": "candidate has checkpoint history that improves resumability confidence",
        }
    ]
    assert build_resumability_explanations(
        has_latest_attempt=True,
        latest_attempt_terminal=True,
        has_latest_checkpoint=True,
    ) == [
        {
            "code": "latest_attempt_present",
            "message": "candidate has a latest attempt signal that improves resumability confidence",
        },
        {
            "code": "latest_attempt_terminal",
            "message": "candidate's latest attempt was terminal, reducing resumability confidence",
        },
        {
            "code": "latest_checkpoint_present",
            "message": "candidate has checkpoint history that improves resumability confidence",
        },
    ]


def test_build_detour_like_signal_details_returns_expected_flags() -> None:
    workflow = SimpleNamespace(ticket_id="DOCS-123")
    checkpoint = SimpleNamespace(
        summary="Continue main implementation",
        step_name="implement_task_recall",
        checkpoint_json={},
    )

    assert build_detour_like_signal_details(
        workflow=workflow,
        checkpoint=checkpoint,
    ) == (True, False, True)

    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Cleanup temporary artifacts",
            step_name="mainline_step",
            checkpoint_json={},
        ),
    ) == (False, True, True)

    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Continue main implementation",
            step_name="implement_task_recall",
            checkpoint_json={},
        ),
    ) == (False, False, False)


def test_build_detour_like_signal_details_treats_current_objective_as_detour_signal() -> None:
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Continue main implementation",
            step_name="implement_task_recall",
            checkpoint_json={
                "current_objective": "Finish coverage cleanup for task recall helpers",
            },
        ),
    ) == (False, True, True)


def test_build_detour_like_signal_details_treats_next_intended_action_as_detour_signal() -> None:
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Continue main implementation",
            step_name="implement_task_recall",
            checkpoint_json={
                "next_intended_action": "Write docs follow-up for workspace resume behavior",
            },
        ),
    ) == (False, True, True)


def test_build_detour_like_signal_details_keeps_checkpoint_json_mainline_text_non_detour() -> None:
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Continue main implementation",
            step_name="implement_task_recall",
            checkpoint_json={
                "current_objective": "Finish task recall ranking implementation",
                "next_intended_action": "Resume primary workflow selection work",
            },
        ),
    ) == (False, False, False)


def test_build_detour_like_signal_details_treats_runbook_text_as_detour_signal() -> None:
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Update operator runbook for workspace resume behavior",
            step_name="runbook_followup",
            checkpoint_json={},
        ),
    ) == (False, True, True)


def test_build_detour_like_signal_details_treats_memo_review_and_checklist_text_as_detour_signal() -> (
    None
):
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Write design memo for task recall selection",
            step_name="review_checklist_followup",
            checkpoint_json={},
        ),
    ) == (False, True, True)


def test_build_detour_like_signal_details_treats_notes_text_as_detour_signal() -> None:
    assert build_detour_like_signal_details(
        workflow=SimpleNamespace(ticket_id="TASK-PRIMARY-1"),
        checkpoint=SimpleNamespace(
            summary="Prepare implementation notes for workspace resume heuristics",
            step_name="notes_followup",
            checkpoint_json={},
        ),
    ) == (False, True, True)


def test_build_task_recall_detour_override_applied_returns_expected_flag() -> None:
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="selected-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=True,
            selected_ticket_detour_like=False,
        )
        is True
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="selected-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=False,
            latest_checkpoint_detour_like=True,
            selected_ticket_detour_like=False,
        )
        is True
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="latest-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=True,
            selected_ticket_detour_like=False,
        )
        is False
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="selected-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=False,
            selected_ticket_detour_like=False,
        )
        is False
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="selected-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=True,
            selected_ticket_detour_like=True,
        )
        is False
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id="selected-workflow",
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=False,
            latest_checkpoint_detour_like=True,
            selected_ticket_detour_like=False,
            selected_checkpoint_detour_like=True,
        )
        is False
    )
    assert (
        build_task_recall_detour_override_applied(
            selected_workflow_id=None,
            latest_workflow_id="latest-workflow",
            latest_ticket_detour_like=True,
            selected_ticket_detour_like=False,
        )
        is False
    )


def test_checkpoint_detour_text_normalizes_summary_step_and_checkpoint_json_text() -> None:
    checkpoint = SimpleNamespace(
        summary="Coverage Cleanup",
        step_name="DocsFollowup",
        checkpoint_json={
            "current_objective": "Finish release notes",
            "next_intended_action": "Resume mainline task",
            "ignored": "should not be included",
        },
    )

    assert checkpoint_detour_text(checkpoint) == (
        "coverage cleanup docsfollowup finish release notes resume mainline task"
    )


def test_checkpoint_detour_text_returns_empty_string_for_missing_or_non_dict_checkpoint_json() -> (
    None
):
    assert checkpoint_detour_text(None) == ""
    assert (
        checkpoint_detour_text(
            SimpleNamespace(
                summary=None,
                step_name=None,
                checkpoint_json="not-a-dict",
            )
        )
        == ""
    )


def test_checkpoint_mainline_signal_details_tracks_objective_and_next_action_presence() -> None:
    assert checkpoint_mainline_signal_details(None) == (False, False, False)

    assert checkpoint_mainline_signal_details(SimpleNamespace(checkpoint_json={})) == (
        False,
        False,
        False,
    )

    assert checkpoint_mainline_signal_details(
        SimpleNamespace(
            checkpoint_json={
                "current_objective": "  Finish task recall ranking  ",
                "next_intended_action": "   ",
            }
        )
    ) == (True, False, True)

    assert checkpoint_mainline_signal_details(
        SimpleNamespace(
            checkpoint_json={
                "current_objective": "   ",
                "next_intended_action": "Resume workspace recovery",
            }
        )
    ) == (False, True, True)

    assert checkpoint_mainline_signal_details(
        SimpleNamespace(
            checkpoint_json={
                "current_objective": "Finish task recall ranking",
                "next_intended_action": "Resume workspace recovery",
            }
        )
    ) == (True, True, True)


def test_build_latest_vs_selected_explanations_covers_match_and_difference_paths() -> None:
    assert build_latest_vs_selected_explanations(
        selected_equals_latest=True,
        latest_checkpoint_step_name=" implement ",
        latest_checkpoint_summary="same summary ",
        selected_checkpoint_step_name="implement",
        selected_checkpoint_summary=" same summary",
        latest_detour_like=False,
        selected_detour_like=False,
        latest_return_target_basis="ranked_candidate",
        selected_return_target_basis="ranked_candidate",
        latest_task_thread_basis="non_detour_candidate",
        selected_task_thread_basis="non_detour_candidate",
    ) == [
        {
            "code": "selected_matches_latest",
            "message": "selected continuation target matched the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_match",
            "message": "latest considered checkpoint matched the selected continuation checkpoint",
        },
    ]

    assert build_latest_vs_selected_explanations(
        selected_equals_latest=False,
        latest_checkpoint_step_name="latest-step",
        latest_checkpoint_summary="latest summary",
        selected_checkpoint_step_name="selected-step",
        selected_checkpoint_summary="selected summary",
        latest_detour_like=False,
        selected_detour_like=True,
        latest_return_target_basis="latest_candidate",
        selected_return_target_basis="ranked_candidate",
        latest_task_thread_basis="latest_candidate",
        selected_task_thread_basis="non_detour_candidate",
    ) == [
        {
            "code": "selected_differs_from_latest",
            "message": "selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "latest_and_selected_checkpoints_differ",
            "message": "latest considered checkpoint differed from the selected continuation checkpoint",
        },
        {
            "code": "latest_and_selected_detour_classification_differs",
            "message": "latest considered candidate and selected continuation target differed in detour classification",
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


def test_build_comparison_summary_explanations_handles_empty_checkpoint_context_and_differences() -> (
    None
):
    assert build_comparison_summary_explanations(
        selected_equals_latest=True,
    ) == [
        {
            "code": "summary_selected_matches_latest",
            "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
        }
    ]

    assert build_comparison_summary_explanations(
        selected_equals_latest=False,
        latest_checkpoint_step_name="latest-step",
        latest_checkpoint_summary="latest summary",
        selected_checkpoint_step_name="selected-step",
        selected_checkpoint_summary="selected summary",
        latest_detour_like=True,
        selected_detour_like=False,
        latest_return_target_basis="latest_candidate",
        selected_return_target_basis="ranked_candidate",
        latest_task_thread_basis="latest_candidate",
        selected_task_thread_basis="non_detour_candidate",
    ) == [
        {
            "code": "summary_selected_differs_from_latest",
            "message": "summary comparison recorded that the selected continuation target differed from the latest considered workflow",
        },
        {
            "code": "summary_latest_and_selected_checkpoints_differ",
            "message": "summary comparison recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
        },
        {
            "code": "summary_latest_and_selected_detour_classification_differs",
            "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in detour classification",
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


def test_default_workspace_resume_selection_signals_returns_expected_flags() -> None:
    assert default_workspace_resume_selection_signals() == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": False,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": False,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": False,
        "ranking_details_present": False,
        "explanations_present": False,
    }


def test_build_task_recall_ranking_entry_returns_expected_payload_for_mainline_selected_candidate() -> (
    None
):
    assert build_task_recall_ranking_entry(
        workflow_id="workflow-1",
        resolver_order=0,
        is_latest=True,
        selected=True,
        workflow_terminal=False,
        has_latest_attempt=True,
        latest_attempt_terminal=False,
        has_latest_checkpoint=True,
        ticket_detour_like=False,
        checkpoint_detour_like=False,
    ) == {
        "workflow_instance_id": "workflow-1",
        "resolver_order": 0,
        "selected": True,
        "is_latest": True,
        "workflow_terminal": False,
        "has_latest_attempt": True,
        "latest_attempt_terminal": False,
        "has_latest_checkpoint": True,
        "ticket_detour_like": False,
        "checkpoint_detour_like": False,
        "checkpoint_has_current_objective": False,
        "checkpoint_has_next_intended_action": False,
        "detour_like": False,
        "explicit_mainline_signal_present": False,
        "return_target_candidate": True,
        "return_target_basis": "non_detour_candidate",
        "task_thread_candidate": True,
        "task_thread_basis": "non_detour_candidate",
        "primary_objective_present": False,
        "score": 40,
        "reason_list": [
            {
                "code": "latest_candidate",
                "message": "candidate is the latest workflow considered for continuation",
            },
            {
                "code": "workflow_non_terminal_bonus",
                "message": "non-terminal workflows are preferred for continuation",
                "impact": 25,
            },
            {
                "code": "latest_attempt_present_bonus",
                "message": "candidate has a latest attempt signal available",
                "impact": 5,
            },
            {
                "code": "latest_checkpoint_present_bonus",
                "message": "candidate has checkpoint history for resumability",
                "impact": 5,
            },
            {
                "code": "non_detour_candidate_bonus",
                "message": "candidate avoids detour-like wording and remains continuation-friendly",
                "impact": 5,
            },
            {
                "code": "selected_candidate",
                "message": "candidate was selected after applying task recall heuristics",
            },
        ],
    }


def test_build_task_recall_ranking_entry_returns_expected_payload_for_detour_terminal_candidate() -> (
    None
):
    assert build_task_recall_ranking_entry(
        workflow_id="workflow-2",
        resolver_order=3,
        is_latest=False,
        selected=False,
        workflow_terminal=True,
        has_latest_attempt=False,
        latest_attempt_terminal=True,
        has_latest_checkpoint=False,
        ticket_detour_like=True,
        checkpoint_detour_like=True,
    ) == {
        "workflow_instance_id": "workflow-2",
        "resolver_order": 3,
        "selected": False,
        "is_latest": False,
        "workflow_terminal": True,
        "has_latest_attempt": False,
        "latest_attempt_terminal": True,
        "has_latest_checkpoint": False,
        "ticket_detour_like": True,
        "checkpoint_detour_like": True,
        "checkpoint_has_current_objective": False,
        "checkpoint_has_next_intended_action": False,
        "detour_like": True,
        "explicit_mainline_signal_present": False,
        "return_target_candidate": False,
        "return_target_basis": "detour_penalized_candidate",
        "task_thread_candidate": False,
        "task_thread_basis": "detour_penalized_candidate",
        "primary_objective_present": False,
        "score": -40,
        "reason_list": [
            {
                "code": "workflow_terminal_penalty",
                "message": "terminal workflows are less suitable for continuation",
                "impact": -25,
            },
            {
                "code": "latest_attempt_terminal_penalty",
                "message": "latest attempt is terminal, reducing continuation confidence",
                "impact": -5,
            },
            {
                "code": "ticket_detour_like_penalty",
                "message": "workflow ticket looked detour-like",
                "impact": -10,
            },
            {
                "code": "checkpoint_detour_like_penalty",
                "message": "latest checkpoint looked detour-like",
                "impact": -10,
            },
        ],
    }


def test_task_recall_and_workspace_resume_use_different_mainline_bonus_weights() -> None:
    task_recall_entry = build_task_recall_ranking_entry(
        workflow_id="workflow-task-recall-mainline",
        resolver_order=0,
        is_latest=False,
        selected=False,
        workflow_terminal=False,
        has_latest_attempt=False,
        latest_attempt_terminal=False,
        has_latest_checkpoint=False,
        ticket_detour_like=False,
        checkpoint_detour_like=False,
    )

    assert task_recall_entry["score"] == 30
    assert task_recall_entry["reason_list"] == [
        {
            "code": "workflow_non_terminal_bonus",
            "message": "non-terminal workflows are preferred for continuation",
            "impact": 25,
        },
        {
            "code": "non_detour_candidate_bonus",
            "message": "candidate avoids detour-like wording and remains continuation-friendly",
            "impact": 5,
        },
    ]


def test_workflow_ticket_is_detour_like_matches_expected_tokens() -> None:
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id="COVERAGE-DET-1")) is True
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id="TASK-PRIMARY-1")) is False
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id=None)) is False

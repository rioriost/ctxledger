from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ctxledger.runtime.task_recall import (
    build_checkpoint_current_objective_bonus_reason,
    build_checkpoint_detour_like_penalty_reason,
    build_checkpoint_next_intended_action_bonus_reason,
    build_detour_like_signal_details,
    build_latest_attempt_present_bonus_reason,
    build_latest_attempt_present_explanations,
    build_latest_attempt_terminal_explanations,
    build_latest_attempt_terminal_penalty_reason,
    build_latest_candidate_reason,
    build_latest_candidate_retained_explanations,
    build_latest_checkpoint_present_bonus_reason,
    build_latest_checkpoint_present_explanations,
    build_non_detour_candidate_bonus_reason,
    build_resumability_explanations,
    build_running_workflow_priority_reason,
    build_selected_candidate_reason,
    build_task_recall_detour_override_applied,
    build_task_recall_ranking_entry,
    build_ticket_detour_like_penalty_reason,
    build_workflow_non_terminal_bonus_reason,
    build_workflow_terminal_penalty_reason,
    build_workspace_resume_ranking_entry,
    build_workspace_resume_selection,
    build_workspace_resume_selection_payload,
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
    workspace_resume_entry = build_workspace_resume_ranking_entry(
        workflow_id="workflow-workspace-resume-mainline",
        is_latest=False,
        is_running=False,
        workflow_terminal=False,
        has_latest_attempt=False,
        latest_attempt_terminal=False,
        has_latest_checkpoint=False,
        ticket_detour_like=False,
        checkpoint_detour_like=False,
    )

    assert task_recall_entry["score"] == 30
    assert workspace_resume_entry["score"] == 35
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
    assert workspace_resume_entry["reason_list"] == [
        {
            "code": "workflow_non_terminal_bonus",
            "message": "non-terminal workflows are preferred for continuation",
            "impact": 25,
        },
        {
            "code": "mainline_like_bonus",
            "message": "candidate looks aligned with the main task line",
            "impact": 10,
        },
    ]


def test_build_workspace_resume_ranking_entry_returns_expected_payload_for_latest_mainline_candidate() -> (
    None
):
    assert build_workspace_resume_ranking_entry(
        workflow_id="workflow-resume-1",
        is_latest=True,
        is_running=False,
        workflow_terminal=False,
        has_latest_attempt=True,
        latest_attempt_terminal=False,
        has_latest_checkpoint=True,
        ticket_detour_like=False,
        checkpoint_detour_like=False,
    ) == {
        "workflow_instance_id": "workflow-resume-1",
        "is_latest": True,
        "is_running": False,
        "workflow_terminal": False,
        "has_latest_attempt": True,
        "latest_attempt_terminal": False,
        "has_latest_checkpoint": True,
        "ticket_detour_like": False,
        "checkpoint_detour_like": False,
        "detour_like": False,
        "score": 45,
        "reason_list": [
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
                "code": "mainline_like_bonus",
                "message": "candidate looks aligned with the main task line",
                "impact": 10,
            },
            {
                "code": "latest_candidate",
                "message": "candidate is the latest workflow considered for resume",
            },
        ],
    }


def test_workspace_resume_selection_surfaces_resumability_explanations_for_latest_selected_candidate() -> (
    None
):
    latest_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-RESUME-1",
        latest_attempt=SimpleNamespace(status="running"),
    )
    latest_checkpoint = SimpleNamespace(
        summary="Resume primary workflow implementation",
        step_name="implement_task_recall",
        checkpoint_json={},
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_workflow,
        workflow_candidates=(latest_workflow,),
        latest_checkpoint=latest_checkpoint,
        candidate_checkpoints_by_workflow_id={
            str(latest_workflow.workflow_instance_id): latest_checkpoint,
        },
    )

    assert selected_workflow is latest_workflow
    assert selected_reason == "selected latest workflow because no running workflow was available"
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": True,
        "selected_equals_running": False,
        "latest_ticket_detour_like": False,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": False,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert explanations == [
        {
            "code": "latest_attempt_present",
            "message": "candidate has a latest attempt signal that improves resumability confidence",
        },
        {
            "code": "latest_checkpoint_present",
            "message": "candidate has checkpoint history that improves resumability confidence",
        },
    ]
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": True,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": True,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 45,
            "reason_list": [
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
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        }
    ]


def test_build_workspace_resume_ranking_entry_returns_expected_payload_for_running_detour_candidate() -> (
    None
):
    assert build_workspace_resume_ranking_entry(
        workflow_id="workflow-resume-2",
        is_latest=False,
        is_running=True,
        workflow_terminal=False,
        has_latest_attempt=True,
        latest_attempt_terminal=True,
        has_latest_checkpoint=False,
        ticket_detour_like=True,
        checkpoint_detour_like=False,
    ) == {
        "workflow_instance_id": "workflow-resume-2",
        "is_latest": False,
        "is_running": True,
        "workflow_terminal": False,
        "has_latest_attempt": True,
        "latest_attempt_terminal": True,
        "has_latest_checkpoint": False,
        "ticket_detour_like": True,
        "checkpoint_detour_like": False,
        "detour_like": True,
        "score": 115,
        "reason_list": [
            {
                "code": "running_workflow_priority",
                "message": "running workflows are prioritized for continuation",
                "impact": 100,
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
                "code": "latest_attempt_terminal_penalty",
                "message": "latest attempt is terminal, reducing continuation confidence",
                "impact": -5,
            },
            {
                "code": "ticket_detour_like_penalty",
                "message": "workflow ticket looked detour-like",
                "impact": -10,
            },
        ],
    }


def test_workflow_ticket_is_detour_like_matches_expected_tokens() -> None:
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id="COVERAGE-DET-1")) is True
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id="TASK-PRIMARY-1")) is False
    assert workflow_ticket_is_detour_like(SimpleNamespace(ticket_id=None)) is False


def test_build_workspace_resume_selection_prefers_non_terminal_candidate_over_latest_terminal() -> (
    None
):
    latest_terminal_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="completed",
        ticket_id="TASK-DONE-1",
    )
    older_non_terminal_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-1",
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_terminal_workflow,
        workflow_candidates=(
            latest_terminal_workflow,
            older_non_terminal_workflow,
        ),
    )

    assert selected_workflow is older_non_terminal_workflow
    assert (
        selected_reason
        == "selected non-terminal workflow candidate instead of latest terminal workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": True,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": False,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": False,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_terminal_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": True,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": -15,
            "reason_list": [
                {
                    "code": "workflow_terminal_penalty",
                    "message": "terminal workflows are less suitable for continuation",
                    "impact": -25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(older_non_terminal_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_workflow_terminal",
            "message": "latest workflow was terminal",
        },
        {
            "code": "selected_non_terminal_candidate",
            "message": "selected a non-terminal candidate instead",
        },
    ]


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_over_latest_detour_like() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="DOCS-DET-1",
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-1",
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": True,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": True,
            "checkpoint_detour_like": False,
            "detour_like": True,
            "score": 15,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "ticket_detour_like_penalty",
                    "message": "workflow ticket looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_ticket_detour_like",
            "message": "latest workflow ticket looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]


def test_build_workspace_resume_selection_payload_includes_selection_metadata() -> None:
    selected_workflow = SimpleNamespace(workflow_instance_id=uuid4())
    latest_workflow = SimpleNamespace(workflow_instance_id=uuid4())
    signals = {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": True,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    explanations = [
        {
            "code": "latest_workflow_detour_like",
            "message": "latest workflow looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
    ]

    ranking_details = [
        {
            "workflow_instance_id": str(latest_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "ticket_detour_like": True,
            "checkpoint_detour_like": False,
            "detour_like": True,
            "score": 15,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "ticket_detour_like_penalty",
                    "message": "workflow ticket looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(selected_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]

    payload = build_workspace_resume_selection_payload(
        strategy="running_or_latest",
        candidate_count=2,
        selected_workflow=selected_workflow,
        running_workflow=None,
        latest_workflow=latest_workflow,
        selected_reason=(
            "selected non-detour-like workflow candidate instead of latest detour-like workflow"
        ),
        selection_signals=signals,
        explanations=explanations,
        ranking_details=ranking_details,
    )

    assert payload == {
        "strategy": "running_or_latest",
        "candidate_count": 2,
        "selected_workflow_instance_id": str(selected_workflow.workflow_instance_id),
        "running_workflow_instance_id": None,
        "latest_workflow_instance_id": str(latest_workflow.workflow_instance_id),
        "selected_reason": (
            "selected non-detour-like workflow candidate instead of latest detour-like workflow"
        ),
        "latest_deprioritized": True,
        "signals": signals,
        "explanations": explanations,
        "ranking_details": ranking_details,
    }


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_when_latest_ticket_is_docs() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="DOCS-123",
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="FEATURE-PRIMARY-1",
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": True,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": True,
            "checkpoint_detour_like": False,
            "detour_like": True,
            "score": 15,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "ticket_detour_like_penalty",
                    "message": "workflow ticket looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_ticket_detour_like",
            "message": "latest workflow ticket looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_when_latest_ticket_is_cleanup() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="cleanup-followup",
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-2",
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": True,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": True,
            "checkpoint_detour_like": False,
            "detour_like": True,
            "score": 15,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "ticket_detour_like_penalty",
                    "message": "workflow ticket looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_ticket_detour_like",
            "message": "latest workflow ticket looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_when_latest_ticket_is_diagnostic() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="diagnostic-investigation",
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-3",
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": True,
        "latest_checkpoint_detour_like": False,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": True,
            "checkpoint_detour_like": False,
            "detour_like": True,
            "score": 15,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "ticket_detour_like_penalty",
                    "message": "workflow ticket looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": False,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 35,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_ticket_detour_like",
            "message": "latest workflow ticket looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_when_latest_checkpoint_summary_is_coverage() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-4",
    )
    latest_detour_checkpoint = SimpleNamespace(
        summary="Improve coverage for workflow selection helpers",
        step_name="coverage_followup",
        checkpoint_json={},
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-4-MAIN",
    )
    mainline_checkpoint = SimpleNamespace(
        summary="Continue main task thread",
        step_name="implement_task_recall",
        checkpoint_json={},
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
        latest_checkpoint=latest_detour_checkpoint,
        candidate_checkpoints_by_workflow_id={
            str(latest_detour_workflow.workflow_instance_id): latest_detour_checkpoint,
            str(mainline_workflow.workflow_instance_id): mainline_checkpoint,
        },
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": False,
        "latest_checkpoint_detour_like": True,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": True,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "score": 20,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "latest_checkpoint_present_bonus",
                    "message": "candidate has checkpoint history for resumability",
                    "impact": 5,
                },
                {
                    "code": "checkpoint_detour_like_penalty",
                    "message": "latest checkpoint looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": True,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 40,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "latest_checkpoint_present_bonus",
                    "message": "candidate has checkpoint history for resumability",
                    "impact": 5,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_checkpoint_detour_like",
            "message": "latest workflow checkpoint looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]


def test_build_workspace_resume_selection_prefers_non_detour_like_candidate_when_latest_checkpoint_summary_is_docs() -> (
    None
):
    latest_detour_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-5",
    )
    latest_detour_checkpoint = SimpleNamespace(
        summary="Update docs and handoff notes for summary retrieval",
        step_name="docs_followup",
        checkpoint_json={},
    )
    mainline_workflow = SimpleNamespace(
        workflow_instance_id=uuid4(),
        status="running",
        ticket_id="TASK-PRIMARY-5-MAIN",
    )
    mainline_checkpoint = SimpleNamespace(
        summary="Resume implementation of task recall ranking",
        step_name="implement_task_recall",
        checkpoint_json={},
    )

    (
        selected_workflow,
        selected_reason,
        selection_signals,
        explanations,
        ranking_details,
    ) = build_workspace_resume_selection(
        running_workflow=None,
        latest_workflow=latest_detour_workflow,
        workflow_candidates=(
            latest_detour_workflow,
            mainline_workflow,
        ),
        latest_checkpoint=latest_detour_checkpoint,
        candidate_checkpoints_by_workflow_id={
            str(latest_detour_workflow.workflow_instance_id): latest_detour_checkpoint,
            str(mainline_workflow.workflow_instance_id): mainline_checkpoint,
        },
    )

    assert selected_workflow is mainline_workflow
    assert (
        selected_reason
        == "selected non-detour-like workflow candidate instead of latest detour-like workflow"
    )
    assert selection_signals == {
        "running_workflow_available": False,
        "latest_workflow_terminal": False,
        "non_terminal_candidate_available": True,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": False,
        "latest_checkpoint_detour_like": True,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": True,
        "ranking_details_present": True,
        "explanations_present": True,
    }
    assert ranking_details == [
        {
            "workflow_instance_id": str(latest_detour_workflow.workflow_instance_id),
            "is_latest": True,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": True,
            "ticket_detour_like": False,
            "checkpoint_detour_like": True,
            "detour_like": True,
            "score": 20,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "latest_checkpoint_present_bonus",
                    "message": "candidate has checkpoint history for resumability",
                    "impact": 5,
                },
                {
                    "code": "checkpoint_detour_like_penalty",
                    "message": "latest checkpoint looked detour-like",
                    "impact": -10,
                },
                {
                    "code": "latest_candidate",
                    "message": "candidate is the latest workflow considered for resume",
                },
            ],
            "selected": False,
        },
        {
            "workflow_instance_id": str(mainline_workflow.workflow_instance_id),
            "is_latest": False,
            "is_running": False,
            "workflow_terminal": False,
            "has_latest_attempt": False,
            "latest_attempt_terminal": False,
            "has_latest_checkpoint": True,
            "ticket_detour_like": False,
            "checkpoint_detour_like": False,
            "detour_like": False,
            "score": 40,
            "reason_list": [
                {
                    "code": "workflow_non_terminal_bonus",
                    "message": "non-terminal workflows are preferred for continuation",
                    "impact": 25,
                },
                {
                    "code": "latest_checkpoint_present_bonus",
                    "message": "candidate has checkpoint history for resumability",
                    "impact": 5,
                },
                {
                    "code": "mainline_like_bonus",
                    "message": "candidate looks aligned with the main task line",
                    "impact": 10,
                },
                {
                    "code": "selected_candidate",
                    "message": "candidate was selected after applying workspace resume heuristics",
                },
            ],
            "selected": True,
        },
    ]
    assert explanations == [
        {
            "code": "latest_checkpoint_detour_like",
            "message": "latest workflow checkpoint looked detour-like",
        },
        {
            "code": "selected_non_detour_candidate",
            "message": "selected a non-detour-like candidate instead",
        },
        {
            "code": "candidate_reason_details_available",
            "message": "ranking details include candidate-level reasons for the selection outcome",
        },
    ]

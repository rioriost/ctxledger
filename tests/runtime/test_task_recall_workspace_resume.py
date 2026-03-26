from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from ctxledger.runtime.task_recall import (
    build_workspace_resume_ranking_entry,
    build_workspace_resume_selection,
    build_workspace_resume_selection_payload,
)


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

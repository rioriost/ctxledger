from __future__ import annotations

TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}

DETOUR_LIKE_TOKENS = (
    "coverage",
    "docs",
    "cleanup",
    "diagnostic",
    "runbook",
    "memo",
    "checklist",
    "review",
    "notes",
)

LATEST_WORKFLOW_TERMINAL_EXPLANATION = {
    "code": "latest_workflow_terminal",
    "message": "latest workflow was terminal",
}

SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION = {
    "code": "selected_non_terminal_candidate",
    "message": "selected a non-terminal candidate instead",
}

SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION = {
    "code": "selected_non_detour_candidate",
    "message": "selected a non-detour-like candidate instead",
}

SELECTED_DIFFERS_FROM_LATEST_EXPLANATION = {
    "code": "selected_differs_from_latest",
    "message": "selected continuation target differed from the latest considered workflow",
}

SELECTED_MATCHES_LATEST_EXPLANATION = {
    "code": "selected_matches_latest",
    "message": "selected continuation target matched the latest considered workflow",
}

LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION = {
    "code": "latest_and_selected_checkpoints_differ",
    "message": "latest considered checkpoint differed from the selected continuation checkpoint",
}

LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION = {
    "code": "latest_and_selected_checkpoints_match",
    "message": "latest considered checkpoint matched the selected continuation checkpoint",
}

LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_detour_classification_differs",
    "message": "latest considered candidate and selected continuation target differed in detour classification",
}

LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_return_target_basis_differs",
    "message": "latest considered candidate and selected continuation target differed in return-target basis",
}

LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_task_thread_basis_differs",
    "message": "latest considered candidate and selected continuation target differed in task-thread basis",
}

SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION = {
    "code": "summary_selected_differs_from_latest",
    "message": "summary comparison recorded that the selected continuation target differed from the latest considered workflow",
}

SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION = {
    "code": "summary_selected_matches_latest",
    "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
}

SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION = {
    "code": "summary_latest_and_selected_checkpoints_differ",
    "message": "summary comparison recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
}

SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION = {
    "code": "summary_latest_and_selected_checkpoints_match",
    "message": "summary comparison recorded that the latest considered checkpoint matched the selected continuation checkpoint",
}

SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_detour_classification_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in detour classification",
}

SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_return_target_basis_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in return-target basis",
}

SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_task_thread_basis_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
}

TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE = "task_recall_checkpoint_comparison"

SELECTED_EXPLICIT_RETURN_TARGET_EXPLANATION = {
    "code": "selected_explicit_return_target",
    "message": "selected the candidate with the strongest explicit return-target evidence",
}

CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION = {
    "code": "candidate_reason_details_available",
    "message": "ranking details include candidate-level reasons for the selection outcome",
}

LATEST_CANDIDATE_RETAINED_EXPLANATION = {
    "code": "latest_candidate_retained",
    "message": "latest workflow candidate remained the best continuation point",
}

WORKFLOW_TERMINAL_PENALTY_REASON = {
    "code": "workflow_terminal_penalty",
    "message": "terminal workflows are less suitable for continuation",
    "impact": -25,
}

WORKFLOW_NON_TERMINAL_BONUS_REASON = {
    "code": "workflow_non_terminal_bonus",
    "message": "non-terminal workflows are preferred for continuation",
    "impact": 25,
}

TICKET_DETOUR_LIKE_PENALTY_REASON = {
    "code": "ticket_detour_like_penalty",
    "message": "workflow ticket looked detour-like",
    "impact": -10,
}

CHECKPOINT_DETOUR_LIKE_PENALTY_REASON = {
    "code": "checkpoint_detour_like_penalty",
    "message": "latest checkpoint looked detour-like",
    "impact": -10,
}

NON_DETOUR_CANDIDATE_BONUS_REASON = {
    "code": "non_detour_candidate_bonus",
    "message": "candidate avoids detour-like wording and remains continuation-friendly",
}

CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON = {
    "code": "checkpoint_current_objective_bonus",
    "message": "latest checkpoint carries an explicit current objective",
}

CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON = {
    "code": "checkpoint_next_intended_action_bonus",
    "message": "latest checkpoint carries an explicit next intended action",
}

LATEST_CANDIDATE_REASON_BY_CONTEXT = {
    "resume": {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for resume",
    },
    "continuation": {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for continuation",
    },
}

SELECTED_CANDIDATE_REASON_BY_CONTEXT = {
    "workspace_resume": {
        "code": "selected_candidate",
        "message": "candidate was selected after applying workspace resume heuristics",
    },
    "task_recall": {
        "code": "selected_candidate",
        "message": "candidate was selected after applying task recall heuristics",
    },
}

RUNNING_WORKFLOW_PRIORITY_REASON = {
    "code": "running_workflow_priority",
    "message": "running workflows are prioritized for continuation",
    "impact": 100,
}

LATEST_ATTEMPT_PRESENT_BONUS_REASON = {
    "code": "latest_attempt_present_bonus",
    "message": "candidate has a latest attempt signal available",
    "impact": 5,
}

LATEST_ATTEMPT_TERMINAL_PENALTY_REASON = {
    "code": "latest_attempt_terminal_penalty",
    "message": "latest attempt is terminal, reducing continuation confidence",
    "impact": -5,
}

LATEST_CHECKPOINT_PRESENT_BONUS_REASON = {
    "code": "latest_checkpoint_present_bonus",
    "message": "candidate has checkpoint history for resumability",
    "impact": 5,
}

LATEST_ATTEMPT_PRESENT_EXPLANATION = {
    "code": "latest_attempt_present",
    "message": "candidate has a latest attempt signal that improves resumability confidence",
}

LATEST_ATTEMPT_TERMINAL_EXPLANATION = {
    "code": "latest_attempt_terminal",
    "message": "candidate's latest attempt was terminal, reducing resumability confidence",
}

LATEST_CHECKPOINT_PRESENT_EXPLANATION = {
    "code": "latest_checkpoint_present",
    "message": "candidate has checkpoint history that improves resumability confidence",
}

__all__ = [
    "CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION",
    "CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON",
    "CHECKPOINT_DETOUR_LIKE_PENALTY_REASON",
    "CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON",
    "DETOUR_LIKE_TOKENS",
    "LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION",
    "LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION",
    "LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION",
    "LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION",
    "LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION",
    "LATEST_ATTEMPT_PRESENT_BONUS_REASON",
    "LATEST_ATTEMPT_PRESENT_EXPLANATION",
    "LATEST_ATTEMPT_TERMINAL_EXPLANATION",
    "LATEST_ATTEMPT_TERMINAL_PENALTY_REASON",
    "LATEST_CANDIDATE_REASON_BY_CONTEXT",
    "LATEST_CANDIDATE_RETAINED_EXPLANATION",
    "LATEST_CHECKPOINT_PRESENT_BONUS_REASON",
    "LATEST_CHECKPOINT_PRESENT_EXPLANATION",
    "LATEST_WORKFLOW_TERMINAL_EXPLANATION",
    "NON_DETOUR_CANDIDATE_BONUS_REASON",
    "RUNNING_WORKFLOW_PRIORITY_REASON",
    "SELECTED_CANDIDATE_REASON_BY_CONTEXT",
    "SELECTED_DIFFERS_FROM_LATEST_EXPLANATION",
    "SELECTED_EXPLICIT_RETURN_TARGET_EXPLANATION",
    "SELECTED_MATCHES_LATEST_EXPLANATION",
    "SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION",
    "SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION",
    "SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION",
    "SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION",
    "SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION",
    "SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION",
    "SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION",
    "SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION",
    "SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION",
    "TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE",
    "TERMINAL_WORKFLOW_STATUSES",
    "TICKET_DETOUR_LIKE_PENALTY_REASON",
    "WORKFLOW_NON_TERMINAL_BONUS_REASON",
    "WORKFLOW_TERMINAL_PENALTY_REASON",
]

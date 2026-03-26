from __future__ import annotations

from typing import Any

from .task_recall_constants import (
    CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION,
    CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON,
    CHECKPOINT_DETOUR_LIKE_PENALTY_REASON,
    CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON,
    LATEST_ATTEMPT_PRESENT_BONUS_REASON,
    LATEST_ATTEMPT_PRESENT_EXPLANATION,
    LATEST_ATTEMPT_TERMINAL_EXPLANATION,
    LATEST_ATTEMPT_TERMINAL_PENALTY_REASON,
    LATEST_CANDIDATE_REASON_BY_CONTEXT,
    LATEST_CANDIDATE_RETAINED_EXPLANATION,
    LATEST_CHECKPOINT_PRESENT_BONUS_REASON,
    LATEST_CHECKPOINT_PRESENT_EXPLANATION,
    LATEST_WORKFLOW_TERMINAL_EXPLANATION,
    NON_DETOUR_CANDIDATE_BONUS_REASON,
    RUNNING_WORKFLOW_PRIORITY_REASON,
    SELECTED_CANDIDATE_REASON_BY_CONTEXT,
    SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION,
    SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION,
    TICKET_DETOUR_LIKE_PENALTY_REASON,
    WORKFLOW_NON_TERMINAL_BONUS_REASON,
    WORKFLOW_TERMINAL_PENALTY_REASON,
)
from .task_recall_context import build_memory_context_task_recall_details


def workflow_status_value(workflow: Any | None) -> str | None:
    if workflow is None:
        return None
    status = getattr(workflow, "status", None)
    return getattr(status, "value", status)


def default_workspace_resume_selection_signals() -> dict[str, bool]:
    return {
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


def build_detour_override_explanations(
    *,
    latest_ticket_detour_like: bool,
    latest_checkpoint_detour_like: bool,
    include_candidate_reason_details: bool = False,
) -> list[dict[str, str]]:
    explanations: list[dict[str, str]] = []

    if latest_ticket_detour_like:
        explanations.append(
            {
                "code": "latest_ticket_detour_like",
                "message": "latest workflow ticket looked detour-like",
            }
        )
    if latest_checkpoint_detour_like:
        explanations.append(
            {
                "code": "latest_checkpoint_detour_like",
                "message": "latest workflow checkpoint looked detour-like",
            }
        )

    explanations.append(dict(SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION))

    if include_candidate_reason_details:
        explanations.append(dict(CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION))

    return explanations


def build_terminal_override_explanations() -> list[dict[str, str]]:
    return [
        dict(LATEST_WORKFLOW_TERMINAL_EXPLANATION),
        dict(SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION),
    ]


def build_latest_candidate_retained_explanations() -> list[dict[str, str]]:
    return [dict(LATEST_CANDIDATE_RETAINED_EXPLANATION)]


def build_workflow_terminal_penalty_reason() -> dict[str, Any]:
    return dict(WORKFLOW_TERMINAL_PENALTY_REASON)


def build_workflow_non_terminal_bonus_reason() -> dict[str, Any]:
    return dict(WORKFLOW_NON_TERMINAL_BONUS_REASON)


def build_ticket_detour_like_penalty_reason() -> dict[str, Any]:
    return dict(TICKET_DETOUR_LIKE_PENALTY_REASON)


def build_checkpoint_detour_like_penalty_reason() -> dict[str, Any]:
    return dict(CHECKPOINT_DETOUR_LIKE_PENALTY_REASON)


def build_non_detour_candidate_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        **NON_DETOUR_CANDIDATE_BONUS_REASON,
        "impact": impact,
    }


def build_mainline_like_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        "code": "mainline_like_bonus",
        "message": "candidate looks aligned with the main task line",
        "impact": impact,
    }


def build_checkpoint_current_objective_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        **CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON,
        "impact": impact,
    }


def build_checkpoint_next_intended_action_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        **CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON,
        "impact": impact,
    }


def build_latest_candidate_reason(*, context: str) -> dict[str, Any]:
    return dict(LATEST_CANDIDATE_REASON_BY_CONTEXT[context])


def build_selected_candidate_reason(*, context: str) -> dict[str, Any]:
    return dict(SELECTED_CANDIDATE_REASON_BY_CONTEXT[context])


def build_running_workflow_priority_reason() -> dict[str, Any]:
    return dict(RUNNING_WORKFLOW_PRIORITY_REASON)


def build_latest_attempt_present_bonus_reason() -> dict[str, Any]:
    return dict(LATEST_ATTEMPT_PRESENT_BONUS_REASON)


def build_latest_attempt_terminal_penalty_reason() -> dict[str, Any]:
    return dict(LATEST_ATTEMPT_TERMINAL_PENALTY_REASON)


def build_latest_checkpoint_present_bonus_reason() -> dict[str, Any]:
    return dict(LATEST_CHECKPOINT_PRESENT_BONUS_REASON)


def build_latest_attempt_present_explanations() -> list[dict[str, str]]:
    return [dict(LATEST_ATTEMPT_PRESENT_EXPLANATION)]


def build_latest_attempt_terminal_explanations() -> list[dict[str, str]]:
    return [dict(LATEST_ATTEMPT_TERMINAL_EXPLANATION)]


def build_latest_checkpoint_present_explanations() -> list[dict[str, str]]:
    return [dict(LATEST_CHECKPOINT_PRESENT_EXPLANATION)]


def build_resumability_explanations(
    *,
    has_latest_attempt: bool,
    latest_attempt_terminal: bool,
    has_latest_checkpoint: bool,
) -> list[dict[str, str]]:
    explanations: list[dict[str, str]] = []

    if has_latest_attempt:
        explanations.extend(build_latest_attempt_present_explanations())
    if latest_attempt_terminal:
        explanations.extend(build_latest_attempt_terminal_explanations())
    if has_latest_checkpoint:
        explanations.extend(build_latest_checkpoint_present_explanations())

    return explanations


def build_task_recall_detour_override_applied(
    *,
    selected_workflow_id: str | None,
    latest_workflow_id: str | None,
    latest_ticket_detour_like: bool,
    latest_checkpoint_detour_like: bool = False,
    selected_ticket_detour_like: bool,
    selected_checkpoint_detour_like: bool = False,
) -> bool:
    return (
        selected_workflow_id is not None
        and latest_workflow_id is not None
        and selected_workflow_id != latest_workflow_id
        and (latest_ticket_detour_like or latest_checkpoint_detour_like)
        and not (selected_ticket_detour_like or selected_checkpoint_detour_like)
    )


def build_task_recall_ranking_entry(
    *,
    workflow_id: str,
    resolver_order: int,
    is_latest: bool,
    selected: bool,
    workflow_terminal: bool,
    has_latest_attempt: bool,
    latest_attempt_terminal: bool,
    has_latest_checkpoint: bool,
    ticket_detour_like: bool,
    checkpoint_detour_like: bool,
    checkpoint_has_current_objective: bool = False,
    checkpoint_has_next_intended_action: bool = False,
) -> dict[str, Any]:
    detour_like = ticket_detour_like or checkpoint_detour_like
    has_explicit_mainline_signal = (
        checkpoint_has_current_objective or checkpoint_has_next_intended_action
    )
    score = 0
    reason_list: list[dict[str, Any]] = []

    if is_latest:
        reason_list.append(build_latest_candidate_reason(context="continuation"))

    if workflow_terminal:
        score -= 25
        reason_list.append(build_workflow_terminal_penalty_reason())
    else:
        score += 25
        reason_list.append(build_workflow_non_terminal_bonus_reason())

    if has_latest_attempt:
        score += 5
        reason_list.append(build_latest_attempt_present_bonus_reason())

    if latest_attempt_terminal:
        score -= 5
        reason_list.append(build_latest_attempt_terminal_penalty_reason())

    if has_latest_checkpoint:
        score += 5
        reason_list.append(build_latest_checkpoint_present_bonus_reason())

    if detour_like:
        score -= 10
        if ticket_detour_like:
            reason_list.append(build_ticket_detour_like_penalty_reason())
        if checkpoint_detour_like:
            reason_list.append(build_checkpoint_detour_like_penalty_reason())
    else:
        if checkpoint_has_current_objective:
            score += 10
            reason_list.append(build_checkpoint_current_objective_bonus_reason(impact=10))
        if checkpoint_has_next_intended_action:
            score += 5
            reason_list.append(build_checkpoint_next_intended_action_bonus_reason(impact=5))
        if not has_explicit_mainline_signal:
            score += 5
            reason_list.append(build_non_detour_candidate_bonus_reason(impact=5))

    if selected:
        reason_list.append(build_selected_candidate_reason(context="task_recall"))

    return {
        "workflow_instance_id": workflow_id,
        "resolver_order": resolver_order,
        "selected": selected,
        "is_latest": is_latest,
        "workflow_terminal": workflow_terminal,
        "has_latest_attempt": has_latest_attempt,
        "latest_attempt_terminal": latest_attempt_terminal,
        "has_latest_checkpoint": has_latest_checkpoint,
        "ticket_detour_like": ticket_detour_like,
        "checkpoint_detour_like": checkpoint_detour_like,
        "checkpoint_has_current_objective": checkpoint_has_current_objective,
        "checkpoint_has_next_intended_action": checkpoint_has_next_intended_action,
        "detour_like": detour_like,
        "explicit_mainline_signal_present": has_explicit_mainline_signal,
        "return_target_candidate": selected or has_explicit_mainline_signal,
        "return_target_basis": (
            "checkpoint_current_objective"
            if checkpoint_has_current_objective
            else (
                "checkpoint_next_intended_action"
                if checkpoint_has_next_intended_action
                else ("non_detour_candidate" if not detour_like else "detour_penalized_candidate")
            )
        ),
        "task_thread_candidate": has_explicit_mainline_signal or not detour_like,
        "task_thread_basis": (
            "checkpoint_objective_or_next_action"
            if has_explicit_mainline_signal
            else ("non_detour_candidate" if not detour_like else "detour_penalized_candidate")
        ),
        "primary_objective_present": checkpoint_has_current_objective,
        "score": score,
        "reason_list": reason_list,
    }


__all__ = [
    "build_checkpoint_current_objective_bonus_reason",
    "build_checkpoint_detour_like_penalty_reason",
    "build_checkpoint_next_intended_action_bonus_reason",
    "build_detour_override_explanations",
    "build_latest_candidate_reason",
    "build_latest_candidate_retained_explanations",
    "build_latest_attempt_present_bonus_reason",
    "build_latest_attempt_present_explanations",
    "build_latest_attempt_terminal_penalty_reason",
    "build_latest_attempt_terminal_explanations",
    "build_latest_checkpoint_present_bonus_reason",
    "build_latest_checkpoint_present_explanations",
    "build_mainline_like_bonus_reason",
    "build_memory_context_task_recall_details",
    "build_non_detour_candidate_bonus_reason",
    "build_resumability_explanations",
    "build_running_workflow_priority_reason",
    "build_selected_candidate_reason",
    "build_task_recall_detour_override_applied",
    "build_task_recall_ranking_entry",
    "build_terminal_override_explanations",
    "build_ticket_detour_like_penalty_reason",
    "build_workflow_non_terminal_bonus_reason",
    "build_workflow_terminal_penalty_reason",
    "default_workspace_resume_selection_signals",
    "workflow_status_value",
]

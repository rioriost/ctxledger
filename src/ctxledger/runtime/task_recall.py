from __future__ import annotations

from typing import Any

_TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}
_DETOUR_LIKE_TOKENS = (
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
_LATEST_WORKFLOW_TERMINAL_EXPLANATION = {
    "code": "latest_workflow_terminal",
    "message": "latest workflow was terminal",
}
_SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION = {
    "code": "selected_non_terminal_candidate",
    "message": "selected a non-terminal candidate instead",
}
_SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION = {
    "code": "selected_non_detour_candidate",
    "message": "selected a non-detour-like candidate instead",
}
_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION = {
    "code": "selected_differs_from_latest",
    "message": "selected continuation target differed from the latest considered workflow",
}
_SELECTED_MATCHES_LATEST_EXPLANATION = {
    "code": "selected_matches_latest",
    "message": "selected continuation target matched the latest considered workflow",
}
_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION = {
    "code": "latest_and_selected_checkpoints_differ",
    "message": "latest considered checkpoint differed from the selected continuation checkpoint",
}
_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION = {
    "code": "latest_and_selected_checkpoints_match",
    "message": "latest considered checkpoint matched the selected continuation checkpoint",
}
_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_detour_classification_differs",
    "message": "latest considered candidate and selected continuation target differed in detour classification",
}
_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_return_target_basis_differs",
    "message": "latest considered candidate and selected continuation target differed in return-target basis",
}
_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION = {
    "code": "latest_and_selected_task_thread_basis_differs",
    "message": "latest considered candidate and selected continuation target differed in task-thread basis",
}
_SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION = {
    "code": "summary_selected_differs_from_latest",
    "message": "summary comparison recorded that the selected continuation target differed from the latest considered workflow",
}
_SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION = {
    "code": "summary_selected_matches_latest",
    "message": "summary comparison recorded that the selected continuation target matched the latest considered workflow",
}
_SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION = {
    "code": "summary_latest_and_selected_checkpoints_differ",
    "message": "summary comparison recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
}
_SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION = {
    "code": "summary_latest_and_selected_checkpoints_match",
    "message": "summary comparison recorded that the latest considered checkpoint matched the selected continuation checkpoint",
}
_SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_detour_classification_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in detour classification",
}
_SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_return_target_basis_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in return-target basis",
}
_SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION = {
    "code": "summary_latest_and_selected_task_thread_basis_differs",
    "message": "summary comparison recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
}
_TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE = "task_recall_checkpoint_comparison"
_SELECTED_EXPLICIT_RETURN_TARGET_EXPLANATION = {
    "code": "selected_explicit_return_target",
    "message": "selected the candidate with the strongest explicit return-target evidence",
}
_CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION = {
    "code": "candidate_reason_details_available",
    "message": "ranking details include candidate-level reasons for the selection outcome",
}
_LATEST_CANDIDATE_RETAINED_EXPLANATION = {
    "code": "latest_candidate_retained",
    "message": "latest workflow candidate remained the best continuation point",
}
_WORKFLOW_TERMINAL_PENALTY_REASON = {
    "code": "workflow_terminal_penalty",
    "message": "terminal workflows are less suitable for continuation",
    "impact": -25,
}
_WORKFLOW_NON_TERMINAL_BONUS_REASON = {
    "code": "workflow_non_terminal_bonus",
    "message": "non-terminal workflows are preferred for continuation",
    "impact": 25,
}
_TICKET_DETOUR_LIKE_PENALTY_REASON = {
    "code": "ticket_detour_like_penalty",
    "message": "workflow ticket looked detour-like",
    "impact": -10,
}
_CHECKPOINT_DETOUR_LIKE_PENALTY_REASON = {
    "code": "checkpoint_detour_like_penalty",
    "message": "latest checkpoint looked detour-like",
    "impact": -10,
}
_NON_DETOUR_CANDIDATE_BONUS_REASON = {
    "code": "non_detour_candidate_bonus",
    "message": "candidate avoids detour-like wording and remains continuation-friendly",
}
_CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON = {
    "code": "checkpoint_current_objective_bonus",
    "message": "latest checkpoint carries an explicit current objective",
}
_CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON = {
    "code": "checkpoint_next_intended_action_bonus",
    "message": "latest checkpoint carries an explicit next intended action",
}
_LATEST_CANDIDATE_REASON_BY_CONTEXT = {
    "resume": {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for resume",
    },
    "continuation": {
        "code": "latest_candidate",
        "message": "candidate is the latest workflow considered for continuation",
    },
}
_SELECTED_CANDIDATE_REASON_BY_CONTEXT = {
    "workspace_resume": {
        "code": "selected_candidate",
        "message": "candidate was selected after applying workspace resume heuristics",
    },
    "task_recall": {
        "code": "selected_candidate",
        "message": "candidate was selected after applying task recall heuristics",
    },
}
_RUNNING_WORKFLOW_PRIORITY_REASON = {
    "code": "running_workflow_priority",
    "message": "running workflows are prioritized for continuation",
    "impact": 100,
}
_LATEST_ATTEMPT_PRESENT_BONUS_REASON = {
    "code": "latest_attempt_present_bonus",
    "message": "candidate has a latest attempt signal available",
    "impact": 5,
}
_LATEST_ATTEMPT_TERMINAL_PENALTY_REASON = {
    "code": "latest_attempt_terminal_penalty",
    "message": "latest attempt is terminal, reducing continuation confidence",
    "impact": -5,
}
_LATEST_CHECKPOINT_PRESENT_BONUS_REASON = {
    "code": "latest_checkpoint_present_bonus",
    "message": "candidate has checkpoint history for resumability",
    "impact": 5,
}
_LATEST_ATTEMPT_PRESENT_EXPLANATION = {
    "code": "latest_attempt_present",
    "message": "candidate has a latest attempt signal that improves resumability confidence",
}
_LATEST_ATTEMPT_TERMINAL_EXPLANATION = {
    "code": "latest_attempt_terminal",
    "message": "candidate's latest attempt was terminal, reducing resumability confidence",
}
_LATEST_CHECKPOINT_PRESENT_EXPLANATION = {
    "code": "latest_checkpoint_present",
    "message": "candidate has checkpoint history that improves resumability confidence",
}


def workflow_status_value(workflow: Any | None) -> str | None:
    if workflow is None:
        return None
    status = getattr(workflow, "status", None)
    return getattr(status, "value", status)


def checkpoint_detour_text(checkpoint: Any | None) -> str:
    if checkpoint is None:
        return ""

    parts: list[str] = []

    summary = getattr(checkpoint, "summary", None)
    if isinstance(summary, str) and summary:
        parts.append(summary)

    step_name = getattr(checkpoint, "step_name", None)
    if isinstance(step_name, str) and step_name:
        parts.append(step_name)

    checkpoint_json = getattr(checkpoint, "checkpoint_json", None)
    if isinstance(checkpoint_json, dict):
        for key in ("current_objective", "next_intended_action"):
            value = checkpoint_json.get(key)
            if isinstance(value, str) and value:
                parts.append(value)

    return " ".join(parts).lower()


def checkpoint_mainline_signal_details(
    checkpoint: Any | None,
) -> tuple[bool, bool, bool]:
    if checkpoint is None:
        return (False, False, False)

    checkpoint_json = getattr(checkpoint, "checkpoint_json", None)
    if not isinstance(checkpoint_json, dict):
        return (False, False, False)

    current_objective = checkpoint_json.get("current_objective")
    next_intended_action = checkpoint_json.get("next_intended_action")

    has_current_objective = isinstance(current_objective, str) and bool(current_objective.strip())
    has_next_intended_action = isinstance(next_intended_action, str) and bool(
        next_intended_action.strip()
    )

    return (
        has_current_objective,
        has_next_intended_action,
        has_current_objective or has_next_intended_action,
    )


def checkpoint_is_detour_like(checkpoint: Any | None) -> bool:
    detour_text = checkpoint_detour_text(checkpoint)
    if not detour_text:
        return False
    return any(token in detour_text for token in _DETOUR_LIKE_TOKENS)


def workflow_ticket_is_detour_like(workflow: Any | None) -> bool:
    if workflow is None:
        return False
    ticket_id = getattr(workflow, "ticket_id", None)
    if not isinstance(ticket_id, str):
        return False
    normalized_ticket_id = ticket_id.lower()
    return any(token in normalized_ticket_id for token in _DETOUR_LIKE_TOKENS)


def workflow_or_checkpoint_is_detour_like(
    workflow: Any | None,
    checkpoint: Any | None,
) -> bool:
    return workflow_ticket_is_detour_like(workflow) or checkpoint_is_detour_like(checkpoint)


def build_detour_like_signal_details(
    *,
    workflow: Any | None,
    checkpoint: Any | None,
) -> tuple[bool, bool, bool]:
    ticket_detour_like = workflow_ticket_is_detour_like(workflow)
    checkpoint_detour_like = checkpoint_is_detour_like(checkpoint)
    return (
        ticket_detour_like,
        checkpoint_detour_like,
        ticket_detour_like or checkpoint_detour_like,
    )


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

    explanations.append(dict(_SELECTED_NON_DETOUR_CANDIDATE_EXPLANATION))

    if include_candidate_reason_details:
        explanations.append(dict(_CANDIDATE_REASON_DETAILS_AVAILABLE_EXPLANATION))

    return explanations


def build_terminal_override_explanations() -> list[dict[str, str]]:
    return [
        dict(_LATEST_WORKFLOW_TERMINAL_EXPLANATION),
        dict(_SELECTED_NON_TERMINAL_CANDIDATE_EXPLANATION),
    ]


def build_latest_candidate_retained_explanations() -> list[dict[str, str]]:
    return [dict(_LATEST_CANDIDATE_RETAINED_EXPLANATION)]


def build_latest_vs_selected_explanations(
    *,
    selected_equals_latest: bool,
    latest_checkpoint_step_name: str | None = None,
    latest_checkpoint_summary: str | None = None,
    selected_checkpoint_step_name: str | None = None,
    selected_checkpoint_summary: str | None = None,
    latest_detour_like: bool = False,
    selected_detour_like: bool = False,
    latest_return_target_basis: str | None = None,
    selected_return_target_basis: str | None = None,
    latest_task_thread_basis: str | None = None,
    selected_task_thread_basis: str | None = None,
) -> list[dict[str, str]]:
    explanations = [
        dict(
            _SELECTED_MATCHES_LATEST_EXPLANATION
            if selected_equals_latest
            else _SELECTED_DIFFERS_FROM_LATEST_EXPLANATION
        )
    ]

    latest_checkpoint_tuple = (
        latest_checkpoint_step_name.strip()
        if isinstance(latest_checkpoint_step_name, str)
        else None,
        latest_checkpoint_summary.strip() if isinstance(latest_checkpoint_summary, str) else None,
    )
    selected_checkpoint_tuple = (
        selected_checkpoint_step_name.strip()
        if isinstance(selected_checkpoint_step_name, str)
        else None,
        selected_checkpoint_summary.strip()
        if isinstance(selected_checkpoint_summary, str)
        else None,
    )

    if not (latest_checkpoint_tuple == (None, None) and selected_checkpoint_tuple == (None, None)):
        explanations.append(
            dict(
                _LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION
                if latest_checkpoint_tuple == selected_checkpoint_tuple
                else _LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION
            )
        )

    if latest_detour_like != selected_detour_like:
        explanations.append(dict(_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION))

    if latest_return_target_basis != selected_return_target_basis:
        explanations.append(dict(_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION))

    if latest_task_thread_basis != selected_task_thread_basis:
        explanations.append(dict(_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION))

    return explanations


def build_comparison_summary_explanations(
    *,
    selected_equals_latest: bool,
    latest_checkpoint_step_name: str | None = None,
    latest_checkpoint_summary: str | None = None,
    selected_checkpoint_step_name: str | None = None,
    selected_checkpoint_summary: str | None = None,
    latest_detour_like: bool = False,
    selected_detour_like: bool = False,
    latest_return_target_basis: str | None = None,
    selected_return_target_basis: str | None = None,
    latest_task_thread_basis: str | None = None,
    selected_task_thread_basis: str | None = None,
) -> list[dict[str, str]]:
    explanations = [
        dict(
            _SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION
            if selected_equals_latest
            else _SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION
        )
    ]

    latest_checkpoint_tuple = (
        latest_checkpoint_step_name.strip()
        if isinstance(latest_checkpoint_step_name, str)
        else None,
        latest_checkpoint_summary.strip() if isinstance(latest_checkpoint_summary, str) else None,
    )
    selected_checkpoint_tuple = (
        selected_checkpoint_step_name.strip()
        if isinstance(selected_checkpoint_step_name, str)
        else None,
        selected_checkpoint_summary.strip()
        if isinstance(selected_checkpoint_summary, str)
        else None,
    )

    if not (latest_checkpoint_tuple == (None, None) and selected_checkpoint_tuple == (None, None)):
        explanations.append(
            dict(
                _SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION
                if latest_checkpoint_tuple == selected_checkpoint_tuple
                else _SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION
            )
        )

    if latest_detour_like != selected_detour_like:
        explanations.append(
            dict(_SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION)
        )

    if latest_return_target_basis != selected_return_target_basis:
        explanations.append(
            dict(_SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION)
        )

    if latest_task_thread_basis != selected_task_thread_basis:
        explanations.append(
            dict(_SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION)
        )

    return explanations


def build_workflow_terminal_penalty_reason() -> dict[str, Any]:
    return dict(_WORKFLOW_TERMINAL_PENALTY_REASON)


def build_workflow_non_terminal_bonus_reason() -> dict[str, Any]:
    return dict(_WORKFLOW_NON_TERMINAL_BONUS_REASON)


def build_ticket_detour_like_penalty_reason() -> dict[str, Any]:
    return dict(_TICKET_DETOUR_LIKE_PENALTY_REASON)


def build_checkpoint_detour_like_penalty_reason() -> dict[str, Any]:
    return dict(_CHECKPOINT_DETOUR_LIKE_PENALTY_REASON)


def build_non_detour_candidate_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        **_NON_DETOUR_CANDIDATE_BONUS_REASON,
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
        **_CHECKPOINT_CURRENT_OBJECTIVE_BONUS_REASON,
        "impact": impact,
    }


def build_checkpoint_next_intended_action_bonus_reason(*, impact: int) -> dict[str, Any]:
    return {
        **_CHECKPOINT_NEXT_INTENDED_ACTION_BONUS_REASON,
        "impact": impact,
    }


def build_latest_candidate_reason(*, context: str) -> dict[str, Any]:
    return dict(_LATEST_CANDIDATE_REASON_BY_CONTEXT[context])


def build_selected_candidate_reason(*, context: str) -> dict[str, Any]:
    return dict(_SELECTED_CANDIDATE_REASON_BY_CONTEXT[context])


def build_running_workflow_priority_reason() -> dict[str, Any]:
    return dict(_RUNNING_WORKFLOW_PRIORITY_REASON)


def build_latest_attempt_present_bonus_reason() -> dict[str, Any]:
    return dict(_LATEST_ATTEMPT_PRESENT_BONUS_REASON)


def build_latest_attempt_terminal_penalty_reason() -> dict[str, Any]:
    return dict(_LATEST_ATTEMPT_TERMINAL_PENALTY_REASON)


def build_latest_checkpoint_present_bonus_reason() -> dict[str, Any]:
    return dict(_LATEST_CHECKPOINT_PRESENT_BONUS_REASON)


def build_latest_attempt_present_explanations() -> list[dict[str, str]]:
    return [dict(_LATEST_ATTEMPT_PRESENT_EXPLANATION)]


def build_latest_attempt_terminal_explanations() -> list[dict[str, str]]:
    return [dict(_LATEST_ATTEMPT_TERMINAL_EXPLANATION)]


def build_latest_checkpoint_present_explanations() -> list[dict[str, str]]:
    return [dict(_LATEST_CHECKPOINT_PRESENT_EXPLANATION)]


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


def build_memory_context_task_recall_details(
    *,
    selected_workflow: Any | None,
    latest_workflow: Any | None,
    running_workflow: Any | None,
    selection_signals: dict[str, bool | str | None],
    explanations: list[dict[str, str]] | None = None,
    ranking_details: list[dict[str, Any]] | None = None,
    selected_workflow_terminal: bool = False,
    selected_primary_objective_text: str | None = None,
    prior_mainline_workflow: Any | None = None,
    latest_checkpoint_step_name: str | None = None,
    latest_checkpoint_summary: str | None = None,
) -> dict[str, Any]:
    selected_workflow_instance_id = (
        str(selected_workflow.workflow_instance_id) if selected_workflow is not None else None
    )
    latest_workflow_instance_id = (
        str(latest_workflow.workflow_instance_id) if latest_workflow is not None else None
    )
    running_workflow_instance_id = (
        str(running_workflow.workflow_instance_id) if running_workflow is not None else None
    )
    explanations = explanations or []
    ranking_details = ranking_details or []

    return_target_basis = selection_signals.get("return_target_basis")
    return_target_source = selection_signals.get("return_target_source")
    task_thread_present = selection_signals.get("task_thread_present", False)
    task_thread_basis = selection_signals.get("task_thread_basis")
    task_thread_source = selection_signals.get("task_thread_source")
    if task_thread_basis is None:
        task_thread_basis = return_target_basis
    if task_thread_source is None:
        task_thread_source = return_target_source
    selected_checkpoint_step_name = selection_signals.get("selected_checkpoint_step_name")
    selected_checkpoint_summary = selection_signals.get("selected_checkpoint_summary")
    latest_considered_checkpoint_step_name = (
        latest_checkpoint_step_name.strip()
        if isinstance(latest_checkpoint_step_name, str) and latest_checkpoint_step_name.strip()
        else None
    )
    latest_considered_checkpoint_summary = (
        latest_checkpoint_summary.strip()
        if isinstance(latest_checkpoint_summary, str) and latest_checkpoint_summary.strip()
        else None
    )
    prior_mainline_workflow_instance_id = (
        str(prior_mainline_workflow.workflow_instance_id)
        if prior_mainline_workflow is not None
        else None
    )
    primary_objective_text = (
        selected_primary_objective_text.strip()
        if isinstance(selected_primary_objective_text, str)
        and selected_primary_objective_text.strip()
        else None
    )

    selected_equals_latest = bool(
        selection_signals.get(
            "selected_equals_latest",
            False,
        )
    )

    selected_checkpoint_step_name_value = (
        str(selected_checkpoint_step_name)
        if isinstance(selected_checkpoint_step_name, str)
        else None
    )
    selected_checkpoint_summary_value = (
        str(selected_checkpoint_summary) if isinstance(selected_checkpoint_summary, str) else None
    )
    latest_primary_objective_text = (
        latest_workflow.checkpoint_json.get("current_objective")
        if latest_workflow is not None
        and isinstance(getattr(latest_workflow, "checkpoint_json", None), dict)
        and isinstance(latest_workflow.checkpoint_json.get("current_objective"), str)
        and latest_workflow.checkpoint_json.get("current_objective").strip()
        else None
    )
    latest_next_intended_action_text = (
        latest_workflow.checkpoint_json.get("next_intended_action")
        if latest_workflow is not None
        and isinstance(getattr(latest_workflow, "checkpoint_json", None), dict)
        and isinstance(latest_workflow.checkpoint_json.get("next_intended_action"), str)
        and latest_workflow.checkpoint_json.get("next_intended_action").strip()
        else None
    )
    selected_primary_objective_text = (
        selected_primary_objective_text.strip()
        if isinstance(selected_primary_objective_text, str)
        and selected_primary_objective_text.strip()
        else None
    )
    selected_next_intended_action_text = (
        selected_workflow.checkpoint_json.get("next_intended_action")
        if selected_workflow is not None
        and isinstance(getattr(selected_workflow, "checkpoint_json", None), dict)
        and isinstance(selected_workflow.checkpoint_json.get("next_intended_action"), str)
        and selected_workflow.checkpoint_json.get("next_intended_action").strip()
        else None
    )
    latest_ticket_detour_like = bool(selection_signals.get("latest_ticket_detour_like", False))
    latest_checkpoint_detour_like = bool(
        selection_signals.get("latest_checkpoint_detour_like", False)
    )
    selected_ticket_detour_like = bool(selection_signals.get("selected_ticket_detour_like", False))
    selected_checkpoint_detour_like = bool(
        selection_signals.get("selected_checkpoint_detour_like", False)
    )
    latest_detour_like = latest_ticket_detour_like or latest_checkpoint_detour_like
    selected_detour_like = selected_ticket_detour_like or selected_checkpoint_detour_like
    latest_vs_selected_explanations = build_latest_vs_selected_explanations(
        selected_equals_latest=selected_equals_latest,
        latest_checkpoint_step_name=latest_considered_checkpoint_step_name,
        latest_checkpoint_summary=latest_considered_checkpoint_summary,
        selected_checkpoint_step_name=selected_checkpoint_step_name_value,
        selected_checkpoint_summary=selected_checkpoint_summary_value,
        latest_detour_like=latest_detour_like,
        selected_detour_like=selected_detour_like,
        latest_return_target_basis=(
            str(return_target_basis)
            if selected_equals_latest and isinstance(return_target_basis, str)
            else None
        ),
        selected_return_target_basis=(
            str(return_target_basis) if isinstance(return_target_basis, str) else None
        ),
        latest_task_thread_basis=(
            str(task_thread_basis)
            if selected_equals_latest and isinstance(task_thread_basis, str)
            else None
        ),
        selected_task_thread_basis=(
            str(task_thread_basis) if isinstance(task_thread_basis, str) else None
        ),
    )
    comparison_summary_explanations = build_comparison_summary_explanations(
        selected_equals_latest=selected_equals_latest,
        latest_checkpoint_step_name=latest_considered_checkpoint_step_name,
        latest_checkpoint_summary=latest_considered_checkpoint_summary,
        selected_checkpoint_step_name=selected_checkpoint_step_name_value,
        selected_checkpoint_summary=selected_checkpoint_summary_value,
        latest_detour_like=latest_detour_like,
        selected_detour_like=selected_detour_like,
        latest_return_target_basis=(
            str(return_target_basis)
            if selected_equals_latest and isinstance(return_target_basis, str)
            else None
        ),
        selected_return_target_basis=(
            str(return_target_basis) if isinstance(return_target_basis, str) else None
        ),
        latest_task_thread_basis=(
            str(task_thread_basis)
            if selected_equals_latest and isinstance(task_thread_basis, str)
            else None
        ),
        selected_task_thread_basis=(
            str(task_thread_basis) if isinstance(task_thread_basis, str) else None
        ),
    )
    latest_workflow_terminal = bool(
        selection_signals.get(
            "latest_workflow_terminal",
            False,
        )
    )
    selected_workflow_terminal = bool(selected_workflow_terminal)
    latest_has_attempt_signal = bool(
        selection_signals.get(
            "latest_has_attempt_signal",
            False,
        )
    )
    selected_has_attempt_signal = bool(
        selection_signals.get(
            "selected_has_attempt_signal",
            False,
        )
    )
    latest_attempt_terminal = bool(
        selection_signals.get(
            "latest_attempt_terminal",
            False,
        )
    )
    selected_attempt_terminal = bool(
        selection_signals.get(
            "selected_attempt_terminal",
            False,
        )
    )
    latest_has_checkpoint_signal = bool(
        selection_signals.get(
            "latest_has_checkpoint_signal",
            False,
        )
    )
    selected_has_checkpoint_signal = bool(
        selection_signals.get(
            "selected_has_checkpoint_signal",
            False,
        )
    )
    latest_vs_selected_candidate_details = {
        "latest_workflow_instance_id": latest_workflow_instance_id,
        "selected_workflow_instance_id": selected_workflow_instance_id,
        "latest_considered": {
            "workflow_instance_id": latest_workflow_instance_id,
            "checkpoint_step_name": latest_considered_checkpoint_step_name,
            "checkpoint_summary": latest_considered_checkpoint_summary,
            "primary_objective_text": latest_primary_objective_text,
            "next_intended_action_text": latest_next_intended_action_text,
            "ticket_detour_like": latest_ticket_detour_like,
            "checkpoint_detour_like": latest_checkpoint_detour_like,
            "detour_like": latest_detour_like,
            "workflow_terminal": latest_workflow_terminal,
            "has_attempt_signal": latest_has_attempt_signal,
            "attempt_terminal": latest_attempt_terminal,
            "has_checkpoint_signal": latest_has_checkpoint_signal,
            "return_target_basis": (
                str(return_target_basis)
                if selected_equals_latest and isinstance(return_target_basis, str)
                else None
            ),
            "task_thread_basis": (
                str(task_thread_basis)
                if selected_equals_latest and isinstance(task_thread_basis, str)
                else None
            ),
        },
        "selected": {
            "workflow_instance_id": selected_workflow_instance_id,
            "checkpoint_step_name": selected_checkpoint_step_name_value,
            "checkpoint_summary": selected_checkpoint_summary_value,
            "primary_objective_text": selected_primary_objective_text,
            "next_intended_action_text": selected_next_intended_action_text,
            "ticket_detour_like": selected_ticket_detour_like,
            "checkpoint_detour_like": selected_checkpoint_detour_like,
            "detour_like": selected_detour_like,
            "workflow_terminal": selected_workflow_terminal,
            "has_attempt_signal": selected_has_attempt_signal,
            "attempt_terminal": selected_attempt_terminal,
            "has_checkpoint_signal": selected_has_checkpoint_signal,
            "return_target_basis": (
                str(return_target_basis) if isinstance(return_target_basis, str) else None
            ),
            "task_thread_basis": (
                str(task_thread_basis) if isinstance(task_thread_basis, str) else None
            ),
        },
        "same_checkpoint_details": (
            latest_considered_checkpoint_step_name == selected_checkpoint_step_name_value
            and latest_considered_checkpoint_summary == selected_checkpoint_summary_value
            and latest_primary_objective_text == selected_primary_objective_text
            and latest_next_intended_action_text == selected_next_intended_action_text
            and latest_ticket_detour_like == selected_ticket_detour_like
            and latest_checkpoint_detour_like == selected_checkpoint_detour_like
            and latest_detour_like == selected_detour_like
            and latest_workflow_terminal == selected_workflow_terminal
            and latest_has_attempt_signal == selected_has_attempt_signal
            and latest_attempt_terminal == selected_attempt_terminal
            and latest_has_checkpoint_signal == selected_has_checkpoint_signal
            and (
                (
                    str(return_target_basis)
                    if selected_equals_latest and isinstance(return_target_basis, str)
                    else None
                )
                == (str(return_target_basis) if isinstance(return_target_basis, str) else None)
            )
            and (
                (
                    str(task_thread_basis)
                    if selected_equals_latest and isinstance(task_thread_basis, str)
                    else None
                )
                == (str(task_thread_basis) if isinstance(task_thread_basis, str) else None)
            )
        ),
        "comparison_source": _TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE,
    }

    return {
        "task_recall_selection_present": selected_workflow is not None,
        "task_recall_selected_workflow_instance_id": selected_workflow_instance_id,
        "task_recall_latest_workflow_instance_id": latest_workflow_instance_id,
        "task_recall_running_workflow_instance_id": running_workflow_instance_id,
        "task_recall_return_target_present": selected_workflow is not None,
        "task_recall_return_target_workflow_instance_id": selected_workflow_instance_id,
        "task_recall_return_target_basis": (
            str(return_target_basis) if isinstance(return_target_basis, str) else None
        ),
        "task_recall_return_target_source": (
            str(return_target_source) if isinstance(return_target_source, str) else None
        ),
        "task_recall_task_thread_present": bool(task_thread_present),
        "task_recall_task_thread_basis": (
            str(task_thread_basis) if isinstance(task_thread_basis, str) else None
        ),
        "task_recall_task_thread_source": (
            str(task_thread_source) if isinstance(task_thread_source, str) else None
        ),
        "task_recall_selected_checkpoint_step_name": selected_checkpoint_step_name_value,
        "task_recall_selected_checkpoint_summary": selected_checkpoint_summary_value,
        "task_recall_latest_considered_checkpoint_step_name": latest_considered_checkpoint_step_name,
        "task_recall_latest_considered_checkpoint_summary": latest_considered_checkpoint_summary,
        "task_recall_latest_vs_selected_candidate_details_present": bool(
            latest_considered_checkpoint_step_name is not None
            or latest_considered_checkpoint_summary is not None
            or selected_checkpoint_step_name_value is not None
            or selected_checkpoint_summary_value is not None
        ),
        "task_recall_latest_vs_selected_candidate_details": latest_vs_selected_candidate_details,
        "task_recall_latest_vs_selected_checkpoint_details_present": bool(
            latest_considered_checkpoint_step_name is not None
            or latest_considered_checkpoint_summary is not None
            or selected_checkpoint_step_name_value is not None
            or selected_checkpoint_summary_value is not None
        ),
        "task_recall_latest_vs_selected_checkpoint_details": latest_vs_selected_candidate_details,
        "task_recall_latest_vs_selected_primary_block": "candidate_details",
        "task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias": True,
        "task_recall_prior_mainline_present": prior_mainline_workflow is not None,
        "task_recall_prior_mainline_workflow_instance_id": prior_mainline_workflow_instance_id,
        "task_recall_primary_objective_present": primary_objective_text is not None,
        "task_recall_primary_objective_text": primary_objective_text,
        "task_recall_primary_objective_source": (
            "latest_checkpoint.current_objective" if primary_objective_text is not None else None
        ),
        "task_recall_selected_equals_latest": selected_equals_latest,
        "task_recall_selected_equals_running": selection_signals.get(
            "selected_equals_running",
            False,
        ),
        "task_recall_latest_workflow_terminal": selection_signals.get(
            "latest_workflow_terminal",
            False,
        ),
        "task_recall_latest_ticket_detour_like": selection_signals.get(
            "latest_ticket_detour_like",
            False,
        ),
        "task_recall_latest_checkpoint_detour_like": selection_signals.get(
            "latest_checkpoint_detour_like",
            False,
        ),
        "task_recall_selected_ticket_detour_like": selection_signals.get(
            "selected_ticket_detour_like",
            False,
        ),
        "task_recall_selected_checkpoint_detour_like": selection_signals.get(
            "selected_checkpoint_detour_like",
            False,
        ),
        "task_recall_detour_override_applied": selection_signals.get(
            "detour_override_applied",
            False,
        ),
        "task_recall_latest_vs_selected_explanations_present": bool(
            latest_vs_selected_explanations
        ),
        "task_recall_latest_vs_selected_explanations": latest_vs_selected_explanations,
        "task_recall_comparison_summary_explanations_present": bool(
            comparison_summary_explanations
        ),
        "task_recall_comparison_summary_explanations": comparison_summary_explanations,
        "task_recall_explanations_present": bool(explanations),
        "task_recall_explanations": explanations,
        "task_recall_ranking_details_present": bool(ranking_details),
        "task_recall_ranking_details": ranking_details,
        "task_recall_selected_workflow_terminal": selected_workflow_terminal,
    }


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


def build_workspace_resume_ranking_entry(
    *,
    workflow_id: str,
    is_latest: bool,
    is_running: bool,
    workflow_terminal: bool,
    has_latest_attempt: bool,
    latest_attempt_terminal: bool,
    has_latest_checkpoint: bool,
    ticket_detour_like: bool,
    checkpoint_detour_like: bool,
) -> dict[str, Any]:
    detour_like = ticket_detour_like or checkpoint_detour_like
    score = 0
    reason_list: list[dict[str, Any]] = []

    if is_running:
        score += 100
        reason_list.append(build_running_workflow_priority_reason())

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
        score += 10
        reason_list.append(build_mainline_like_bonus_reason(impact=10))

    if is_latest:
        reason_list.append(build_latest_candidate_reason(context="resume"))

    return {
        "workflow_instance_id": workflow_id,
        "is_latest": is_latest,
        "is_running": is_running,
        "workflow_terminal": workflow_terminal,
        "has_latest_attempt": has_latest_attempt,
        "latest_attempt_terminal": latest_attempt_terminal,
        "has_latest_checkpoint": has_latest_checkpoint,
        "ticket_detour_like": ticket_detour_like,
        "checkpoint_detour_like": checkpoint_detour_like,
        "detour_like": detour_like,
        "score": score,
        "reason_list": reason_list,
    }


def build_workspace_resume_selection(
    *,
    running_workflow: Any | None,
    latest_workflow: Any | None,
    workflow_candidates: tuple[Any, ...],
    latest_checkpoint: Any | None = None,
    candidate_checkpoints_by_workflow_id: dict[str, Any] | None = None,
) -> tuple[Any | None, str, dict[str, bool], list[dict[str, str]], list[dict[str, Any]]]:
    candidate_checkpoints_by_workflow_id = candidate_checkpoints_by_workflow_id or {}

    latest_workflow_terminal = (
        workflow_status_value(latest_workflow) in _TERMINAL_WORKFLOW_STATUSES
        if latest_workflow is not None
        else False
    )
    non_terminal_candidate_available = any(
        workflow_status_value(workflow) not in _TERMINAL_WORKFLOW_STATUSES
        for workflow in workflow_candidates
    )
    latest_ticket_detour_like = workflow_ticket_is_detour_like(latest_workflow)
    latest_checkpoint_detour_like = checkpoint_is_detour_like(latest_checkpoint)
    latest_detour_like = latest_ticket_detour_like or latest_checkpoint_detour_like

    explanations: list[dict[str, str]] = []
    ranking_details: list[dict[str, Any]] = []

    latest_workflow_id = (
        str(latest_workflow.workflow_instance_id) if latest_workflow is not None else None
    )
    running_workflow_id = (
        str(running_workflow.workflow_instance_id) if running_workflow is not None else None
    )

    selection_signals = {
        "running_workflow_available": running_workflow is not None,
        "latest_workflow_terminal": latest_workflow_terminal,
        "non_terminal_candidate_available": non_terminal_candidate_available,
        "selected_equals_latest": False,
        "selected_equals_running": False,
        "latest_ticket_detour_like": latest_ticket_detour_like,
        "latest_checkpoint_detour_like": latest_checkpoint_detour_like,
        "selected_ticket_detour_like": False,
        "selected_checkpoint_detour_like": False,
        "detour_override_applied": False,
        "ranking_details_present": False,
        "explanations_present": False,
    }
    selected_workflow = running_workflow or latest_workflow
    selected_reason = (
        "selected running workflow for workspace resume"
        if running_workflow is not None
        else "selected latest workflow because no running workflow was available"
    )

    def _candidate_ranking_entry(workflow: Any) -> dict[str, Any]:
        workflow_id = str(workflow.workflow_instance_id)
        checkpoint = candidate_checkpoints_by_workflow_id.get(workflow_id)
        workflow_terminal = workflow_status_value(workflow) in _TERMINAL_WORKFLOW_STATUSES
        latest_attempt = getattr(workflow, "latest_attempt", None)
        latest_attempt_status = workflow_status_value(latest_attempt)
        has_latest_attempt = latest_attempt is not None
        latest_attempt_terminal = latest_attempt_status in _TERMINAL_WORKFLOW_STATUSES
        has_latest_checkpoint = checkpoint is not None
        (
            ticket_detour_like,
            checkpoint_detour_like,
            _,
        ) = build_detour_like_signal_details(
            workflow=workflow,
            checkpoint=checkpoint,
        )
        is_latest = workflow_id == latest_workflow_id
        is_running = workflow_id == running_workflow_id

        return build_workspace_resume_ranking_entry(
            workflow_id=workflow_id,
            is_latest=is_latest,
            is_running=is_running,
            workflow_terminal=workflow_terminal,
            has_latest_attempt=has_latest_attempt,
            latest_attempt_terminal=latest_attempt_terminal,
            has_latest_checkpoint=has_latest_checkpoint,
            ticket_detour_like=ticket_detour_like,
            checkpoint_detour_like=checkpoint_detour_like,
        )

    ranking_details = [_candidate_ranking_entry(workflow) for workflow in workflow_candidates]

    if running_workflow is None and latest_workflow is not None:
        if latest_workflow_terminal:
            preferred_non_terminal_workflow = next(
                (
                    workflow
                    for workflow in workflow_candidates
                    if workflow_status_value(workflow) not in _TERMINAL_WORKFLOW_STATUSES
                ),
                None,
            )
            if preferred_non_terminal_workflow is not None:
                selected_workflow = preferred_non_terminal_workflow
                selected_reason = (
                    "selected non-terminal workflow candidate instead of latest terminal workflow"
                )
                explanations.extend(build_terminal_override_explanations())
        elif latest_detour_like:
            preferred_non_detour_workflow = next(
                (
                    workflow
                    for workflow in workflow_candidates
                    if workflow_status_value(workflow) not in _TERMINAL_WORKFLOW_STATUSES
                    and not workflow_or_checkpoint_is_detour_like(
                        workflow,
                        candidate_checkpoints_by_workflow_id.get(
                            str(workflow.workflow_instance_id)
                        ),
                    )
                ),
                None,
            )
            if preferred_non_detour_workflow is not None:
                selected_workflow = preferred_non_detour_workflow
                selected_reason = "selected non-detour-like workflow candidate instead of latest detour-like workflow"
                selection_signals["detour_override_applied"] = (
                    build_task_recall_detour_override_applied(
                        selected_workflow_id=str(
                            preferred_non_detour_workflow.workflow_instance_id
                        ),
                        latest_workflow_id=latest_workflow_id,
                        latest_ticket_detour_like=latest_ticket_detour_like,
                        latest_checkpoint_detour_like=latest_checkpoint_detour_like,
                        selected_ticket_detour_like=workflow_ticket_is_detour_like(
                            preferred_non_detour_workflow
                        ),
                        selected_checkpoint_detour_like=checkpoint_is_detour_like(
                            candidate_checkpoints_by_workflow_id.get(
                                str(preferred_non_detour_workflow.workflow_instance_id)
                            )
                        ),
                    )
                )
                explanations.extend(
                    build_detour_override_explanations(
                        latest_ticket_detour_like=latest_ticket_detour_like,
                        latest_checkpoint_detour_like=latest_checkpoint_detour_like,
                        include_candidate_reason_details=True,
                    )
                )
        elif latest_workflow is not None and selected_workflow == latest_workflow:
            latest_attempt = getattr(selected_workflow, "latest_attempt", None)
            latest_attempt_status = workflow_status_value(latest_attempt)
            explanations.extend(
                build_resumability_explanations(
                    has_latest_attempt=latest_attempt is not None,
                    latest_attempt_terminal=(latest_attempt_status in _TERMINAL_WORKFLOW_STATUSES),
                    has_latest_checkpoint=latest_checkpoint is not None,
                )
            )

    if selected_workflow is not None:
        selected_checkpoint = candidate_checkpoints_by_workflow_id.get(
            str(selected_workflow.workflow_instance_id)
        )
        selection_signals["selected_equals_latest"] = latest_workflow is not None and (
            str(selected_workflow.workflow_instance_id) == str(latest_workflow.workflow_instance_id)
        )
        selection_signals["selected_equals_running"] = running_workflow is not None and (
            str(selected_workflow.workflow_instance_id)
            == str(running_workflow.workflow_instance_id)
        )
        selection_signals["selected_ticket_detour_like"] = workflow_ticket_is_detour_like(
            selected_workflow
        )
        selection_signals["selected_checkpoint_detour_like"] = checkpoint_is_detour_like(
            selected_checkpoint
        )

        for entry in ranking_details:
            entry["selected"] = entry["workflow_instance_id"] == str(
                selected_workflow.workflow_instance_id
            )
            if entry["selected"]:
                entry.setdefault("reason_list", []).append(
                    build_selected_candidate_reason(context="workspace_resume")
                )

    selection_signals["ranking_details_present"] = bool(ranking_details)
    selection_signals["explanations_present"] = bool(explanations)

    return selected_workflow, selected_reason, selection_signals, explanations, ranking_details


def build_workspace_resume_selection_payload(
    *,
    strategy: str,
    candidate_count: int,
    selected_workflow: Any,
    running_workflow: Any | None,
    latest_workflow: Any | None,
    selected_reason: str,
    selection_signals: dict[str, bool],
    explanations: list[dict[str, str]] | None = None,
    ranking_details: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "candidate_count": candidate_count,
        "selected_workflow_instance_id": str(selected_workflow.workflow_instance_id),
        "running_workflow_instance_id": (
            str(running_workflow.workflow_instance_id) if running_workflow is not None else None
        ),
        "latest_workflow_instance_id": (
            str(latest_workflow.workflow_instance_id) if latest_workflow is not None else None
        ),
        "selected_reason": selected_reason,
        "latest_deprioritized": (
            latest_workflow is not None
            and str(latest_workflow.workflow_instance_id)
            != str(selected_workflow.workflow_instance_id)
        ),
        "signals": selection_signals,
        "explanations": explanations or [],
        "ranking_details": ranking_details or [],
    }


__all__ = [
    "build_checkpoint_detour_like_penalty_reason",
    "build_detour_like_signal_details",
    "build_detour_override_explanations",
    "build_latest_candidate_reason",
    "build_latest_candidate_retained_explanations",
    "build_latest_attempt_present_bonus_reason",
    "build_latest_attempt_present_explanations",
    "build_latest_attempt_terminal_penalty_reason",
    "build_latest_attempt_terminal_explanations",
    "build_comparison_summary_explanations",
    "build_latest_vs_selected_explanations",
    "build_checkpoint_current_objective_bonus_reason",
    "build_checkpoint_next_intended_action_bonus_reason",
    "build_latest_checkpoint_present_bonus_reason",
    "build_latest_checkpoint_present_explanations",
    "build_mainline_like_bonus_reason",
    "build_non_detour_candidate_bonus_reason",
    "build_resumability_explanations",
    "build_memory_context_task_recall_details",
    "build_running_workflow_priority_reason",
    "build_task_recall_detour_override_applied",
    "build_task_recall_ranking_entry",
    "build_workspace_resume_ranking_entry",
    "build_selected_candidate_reason",
    "build_terminal_override_explanations",
    "build_ticket_detour_like_penalty_reason",
    "build_workflow_non_terminal_bonus_reason",
    "build_workflow_terminal_penalty_reason",
    "build_workspace_resume_selection",
    "build_workspace_resume_selection_payload",
    "checkpoint_detour_text",
    "checkpoint_is_detour_like",
    "default_workspace_resume_selection_signals",
    "workflow_or_checkpoint_is_detour_like",
    "workflow_status_value",
    "workflow_ticket_is_detour_like",
]

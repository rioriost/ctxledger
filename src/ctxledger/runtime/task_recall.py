from __future__ import annotations

from typing import Any

_TERMINAL_WORKFLOW_STATUSES = {"completed", "failed", "cancelled"}
_DETOUR_LIKE_TOKENS = (
    "coverage",
    "docs",
    "cleanup",
    "diagnostic",
)


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


def build_memory_context_task_recall_details(
    *,
    selected_workflow: Any | None,
    latest_workflow: Any | None,
    running_workflow: Any | None,
    selection_signals: dict[str, bool],
    explanations: list[dict[str, str]] | None = None,
    ranking_details: list[dict[str, Any]] | None = None,
    selected_workflow_terminal: bool = False,
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

    return {
        "task_recall_selection_present": selected_workflow is not None,
        "task_recall_selected_workflow_instance_id": selected_workflow_instance_id,
        "task_recall_latest_workflow_instance_id": latest_workflow_instance_id,
        "task_recall_running_workflow_instance_id": running_workflow_instance_id,
        "task_recall_selected_equals_latest": selection_signals.get(
            "selected_equals_latest",
            False,
        ),
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
        "task_recall_explanations_present": bool(explanations),
        "task_recall_explanations": explanations,
        "task_recall_ranking_details_present": bool(ranking_details),
        "task_recall_ranking_details": ranking_details,
        "task_recall_selected_workflow_terminal": selected_workflow_terminal,
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
        ticket_detour_like = workflow_ticket_is_detour_like(workflow)
        checkpoint_detour_like = checkpoint_is_detour_like(checkpoint)
        detour_like = ticket_detour_like or checkpoint_detour_like
        score = 0
        score += (
            100
            if running_workflow is not None
            and workflow_id == str(running_workflow.workflow_instance_id)
            else 0
        )
        score += 25 if not workflow_terminal else -25
        score += -10 if detour_like else 10
        return {
            "workflow_instance_id": workflow_id,
            "is_latest": latest_workflow is not None
            and workflow_id == str(latest_workflow.workflow_instance_id),
            "is_running": running_workflow is not None
            and workflow_id == str(running_workflow.workflow_instance_id),
            "workflow_terminal": workflow_terminal,
            "ticket_detour_like": ticket_detour_like,
            "checkpoint_detour_like": checkpoint_detour_like,
            "detour_like": detour_like,
            "score": score,
        }

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
                explanations.extend(
                    [
                        {
                            "code": "latest_workflow_terminal",
                            "message": "latest workflow was terminal",
                        },
                        {
                            "code": "selected_non_terminal_candidate",
                            "message": "selected a non-terminal candidate instead",
                        },
                    ]
                )
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
                selection_signals["detour_override_applied"] = True
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
                explanations.append(
                    {
                        "code": "selected_non_detour_candidate",
                        "message": "selected a non-detour-like candidate instead",
                    }
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
    "build_memory_context_task_recall_details",
    "build_workspace_resume_selection",
    "build_workspace_resume_selection_payload",
    "checkpoint_detour_text",
    "checkpoint_is_detour_like",
    "default_workspace_resume_selection_signals",
    "workflow_or_checkpoint_is_detour_like",
    "workflow_status_value",
    "workflow_ticket_is_detour_like",
]

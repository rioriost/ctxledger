from __future__ import annotations

from typing import Any

from .task_recall_constants import TERMINAL_WORKFLOW_STATUSES
from .task_recall_detour import (
    build_detour_like_signal_details,
    checkpoint_is_detour_like,
    workflow_or_checkpoint_is_detour_like,
    workflow_ticket_is_detour_like,
)
from .task_recall_ranking import (
    build_checkpoint_detour_like_penalty_reason,
    build_detour_override_explanations,
    build_latest_attempt_present_bonus_reason,
    build_latest_attempt_terminal_penalty_reason,
    build_latest_candidate_reason,
    build_latest_checkpoint_present_bonus_reason,
    build_mainline_like_bonus_reason,
    build_resumability_explanations,
    build_running_workflow_priority_reason,
    build_selected_candidate_reason,
    build_task_recall_detour_override_applied,
    build_terminal_override_explanations,
    build_ticket_detour_like_penalty_reason,
    build_workflow_non_terminal_bonus_reason,
    build_workflow_terminal_penalty_reason,
    workflow_status_value,
)


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
        workflow_status_value(latest_workflow) in TERMINAL_WORKFLOW_STATUSES
        if latest_workflow is not None
        else False
    )
    non_terminal_candidate_available = any(
        workflow_status_value(workflow) not in TERMINAL_WORKFLOW_STATUSES
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
        workflow_terminal = workflow_status_value(workflow) in TERMINAL_WORKFLOW_STATUSES
        latest_attempt = getattr(workflow, "latest_attempt", None)
        latest_attempt_status = workflow_status_value(latest_attempt)
        has_latest_attempt = latest_attempt is not None
        latest_attempt_terminal = latest_attempt_status in TERMINAL_WORKFLOW_STATUSES
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
                    if workflow_status_value(workflow) not in TERMINAL_WORKFLOW_STATUSES
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
                    if workflow_status_value(workflow) not in TERMINAL_WORKFLOW_STATUSES
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
                    latest_attempt_terminal=(latest_attempt_status in TERMINAL_WORKFLOW_STATUSES),
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
    "build_workspace_resume_ranking_entry",
    "build_workspace_resume_selection",
    "build_workspace_resume_selection_payload",
]

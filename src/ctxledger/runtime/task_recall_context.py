from __future__ import annotations

from typing import Any

from .task_recall_constants import TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE
from .task_recall_detour import (
    build_comparison_summary_explanations,
    build_latest_vs_selected_explanations,
)


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

    selected_equals_latest = bool(selection_signals.get("selected_equals_latest", False))

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
    selected_primary_objective_text_value = (
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

    latest_return_target_basis = (
        str(return_target_basis)
        if selected_equals_latest and isinstance(return_target_basis, str)
        else None
    )
    selected_return_target_basis = (
        str(return_target_basis) if isinstance(return_target_basis, str) else None
    )
    latest_task_thread_basis = (
        str(task_thread_basis)
        if selected_equals_latest and isinstance(task_thread_basis, str)
        else None
    )
    selected_task_thread_basis = (
        str(task_thread_basis) if isinstance(task_thread_basis, str) else None
    )

    latest_vs_selected_explanations = build_latest_vs_selected_explanations(
        selected_equals_latest=selected_equals_latest,
        latest_checkpoint_step_name=latest_considered_checkpoint_step_name,
        latest_checkpoint_summary=latest_considered_checkpoint_summary,
        selected_checkpoint_step_name=selected_checkpoint_step_name_value,
        selected_checkpoint_summary=selected_checkpoint_summary_value,
        latest_detour_like=latest_detour_like,
        selected_detour_like=selected_detour_like,
        latest_return_target_basis=latest_return_target_basis,
        selected_return_target_basis=selected_return_target_basis,
        latest_task_thread_basis=latest_task_thread_basis,
        selected_task_thread_basis=selected_task_thread_basis,
    )
    comparison_summary_explanations = build_comparison_summary_explanations(
        selected_equals_latest=selected_equals_latest,
        latest_checkpoint_step_name=latest_considered_checkpoint_step_name,
        latest_checkpoint_summary=latest_considered_checkpoint_summary,
        selected_checkpoint_step_name=selected_checkpoint_step_name_value,
        selected_checkpoint_summary=selected_checkpoint_summary_value,
        latest_detour_like=latest_detour_like,
        selected_detour_like=selected_detour_like,
        latest_return_target_basis=latest_return_target_basis,
        selected_return_target_basis=selected_return_target_basis,
        latest_task_thread_basis=latest_task_thread_basis,
        selected_task_thread_basis=selected_task_thread_basis,
    )

    latest_workflow_terminal = bool(selection_signals.get("latest_workflow_terminal", False))
    selected_workflow_terminal_value = bool(selected_workflow_terminal)
    latest_has_attempt_signal = bool(selection_signals.get("latest_has_attempt_signal", False))
    selected_has_attempt_signal = bool(selection_signals.get("selected_has_attempt_signal", False))
    latest_attempt_terminal = bool(selection_signals.get("latest_attempt_terminal", False))
    selected_attempt_terminal = bool(selection_signals.get("selected_attempt_terminal", False))
    latest_has_checkpoint_signal = bool(
        selection_signals.get("latest_has_checkpoint_signal", False)
    )
    selected_has_checkpoint_signal = bool(
        selection_signals.get("selected_has_checkpoint_signal", False)
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
            "return_target_basis": latest_return_target_basis,
            "task_thread_basis": latest_task_thread_basis,
        },
        "selected": {
            "workflow_instance_id": selected_workflow_instance_id,
            "checkpoint_step_name": selected_checkpoint_step_name_value,
            "checkpoint_summary": selected_checkpoint_summary_value,
            "primary_objective_text": selected_primary_objective_text_value,
            "next_intended_action_text": selected_next_intended_action_text,
            "ticket_detour_like": selected_ticket_detour_like,
            "checkpoint_detour_like": selected_checkpoint_detour_like,
            "detour_like": selected_detour_like,
            "workflow_terminal": selected_workflow_terminal_value,
            "has_attempt_signal": selected_has_attempt_signal,
            "attempt_terminal": selected_attempt_terminal,
            "has_checkpoint_signal": selected_has_checkpoint_signal,
            "return_target_basis": selected_return_target_basis,
            "task_thread_basis": selected_task_thread_basis,
        },
        "same_checkpoint_details": (
            latest_considered_checkpoint_step_name == selected_checkpoint_step_name_value
            and latest_considered_checkpoint_summary == selected_checkpoint_summary_value
            and latest_primary_objective_text == selected_primary_objective_text_value
            and latest_next_intended_action_text == selected_next_intended_action_text
            and latest_ticket_detour_like == selected_ticket_detour_like
            and latest_checkpoint_detour_like == selected_checkpoint_detour_like
            and latest_detour_like == selected_detour_like
            and latest_workflow_terminal == selected_workflow_terminal_value
            and latest_has_attempt_signal == selected_has_attempt_signal
            and latest_attempt_terminal == selected_attempt_terminal
            and latest_has_checkpoint_signal == selected_has_checkpoint_signal
            and latest_return_target_basis == selected_return_target_basis
            and latest_task_thread_basis == selected_task_thread_basis
        ),
        "comparison_source": TASK_RECALL_CHECKPOINT_COMPARISON_SOURCE,
    }

    details = {
        "task_recall_selection_present": selected_workflow is not None,
        "task_recall_selected_workflow_instance_id": selected_workflow_instance_id,
        "task_recall_latest_workflow_instance_id": latest_workflow_instance_id,
        "task_recall_running_workflow_instance_id": running_workflow_instance_id,
        "task_recall_return_target_present": selected_workflow is not None,
        "task_recall_return_target_workflow_instance_id": selected_workflow_instance_id,
        "task_recall_return_target_basis": selected_return_target_basis,
        "task_recall_return_target_source": (
            str(return_target_source) if isinstance(return_target_source, str) else None
        ),
        "task_recall_task_thread_present": bool(task_thread_present),
        "task_recall_task_thread_basis": selected_task_thread_basis,
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
        "task_recall_selected_workflow_terminal": selected_workflow_terminal_value,
    }

    return details


__all__ = ["build_memory_context_task_recall_details"]

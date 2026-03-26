from __future__ import annotations

from typing import Any

from .task_recall_constants import (
    DETOUR_LIKE_TOKENS,
    LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION,
    LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION,
    LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION,
    LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION,
    LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION,
    SELECTED_DIFFERS_FROM_LATEST_EXPLANATION,
    SELECTED_MATCHES_LATEST_EXPLANATION,
    SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION,
    SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION,
    SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION,
    SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION,
    SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION,
    SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION,
    SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION,
)


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
    return any(token in detour_text for token in DETOUR_LIKE_TOKENS)


def workflow_ticket_is_detour_like(workflow: Any | None) -> bool:
    if workflow is None:
        return False
    ticket_id = getattr(workflow, "ticket_id", None)
    if not isinstance(ticket_id, str):
        return False
    normalized_ticket_id = ticket_id.lower()
    return any(token in normalized_ticket_id for token in DETOUR_LIKE_TOKENS)


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


def _normalized_checkpoint_tuple(
    *,
    checkpoint_step_name: str | None,
    checkpoint_summary: str | None,
) -> tuple[str | None, str | None]:
    return (
        checkpoint_step_name.strip() if isinstance(checkpoint_step_name, str) else None,
        checkpoint_summary.strip() if isinstance(checkpoint_summary, str) else None,
    )


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
            SELECTED_MATCHES_LATEST_EXPLANATION
            if selected_equals_latest
            else SELECTED_DIFFERS_FROM_LATEST_EXPLANATION
        )
    ]

    latest_checkpoint_tuple = _normalized_checkpoint_tuple(
        checkpoint_step_name=latest_checkpoint_step_name,
        checkpoint_summary=latest_checkpoint_summary,
    )
    selected_checkpoint_tuple = _normalized_checkpoint_tuple(
        checkpoint_step_name=selected_checkpoint_step_name,
        checkpoint_summary=selected_checkpoint_summary,
    )

    if not (latest_checkpoint_tuple == (None, None) and selected_checkpoint_tuple == (None, None)):
        explanations.append(
            dict(
                LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION
                if latest_checkpoint_tuple == selected_checkpoint_tuple
                else LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION
            )
        )

    if latest_detour_like != selected_detour_like:
        explanations.append(dict(LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION))

    if latest_return_target_basis != selected_return_target_basis:
        explanations.append(dict(LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION))

    if latest_task_thread_basis != selected_task_thread_basis:
        explanations.append(dict(LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION))

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
            SUMMARY_SELECTED_MATCHES_LATEST_EXPLANATION
            if selected_equals_latest
            else SUMMARY_SELECTED_DIFFERS_FROM_LATEST_EXPLANATION
        )
    ]

    latest_checkpoint_tuple = _normalized_checkpoint_tuple(
        checkpoint_step_name=latest_checkpoint_step_name,
        checkpoint_summary=latest_checkpoint_summary,
    )
    selected_checkpoint_tuple = _normalized_checkpoint_tuple(
        checkpoint_step_name=selected_checkpoint_step_name,
        checkpoint_summary=selected_checkpoint_summary,
    )

    if not (latest_checkpoint_tuple == (None, None) and selected_checkpoint_tuple == (None, None)):
        explanations.append(
            dict(
                SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_MATCH_EXPLANATION
                if latest_checkpoint_tuple == selected_checkpoint_tuple
                else SUMMARY_LATEST_AND_SELECTED_CHECKPOINTS_DIFFER_EXPLANATION
            )
        )

    if latest_detour_like != selected_detour_like:
        explanations.append(
            dict(SUMMARY_LATEST_AND_SELECTED_DETOUR_CLASSIFICATION_DIFFERS_EXPLANATION)
        )

    if latest_return_target_basis != selected_return_target_basis:
        explanations.append(
            dict(SUMMARY_LATEST_AND_SELECTED_RETURN_TARGET_BASIS_DIFFERS_EXPLANATION)
        )

    if latest_task_thread_basis != selected_task_thread_basis:
        explanations.append(dict(SUMMARY_LATEST_AND_SELECTED_TASK_THREAD_BASIS_DIFFERS_EXPLANATION))

    return explanations


__all__ = [
    "build_comparison_summary_explanations",
    "build_detour_like_signal_details",
    "build_latest_vs_selected_explanations",
    "checkpoint_detour_text",
    "checkpoint_is_detour_like",
    "checkpoint_mainline_signal_details",
    "workflow_or_checkpoint_is_detour_like",
    "workflow_ticket_is_detour_like",
]

from __future__ import annotations

from typing import Any
from uuid import UUID

from .helpers import metadata_query_strings


def selected_task_recall_bonus_enabled(
    *,
    selected_task_recall_workflow_id: str | None,
    latest_task_recall_workflow_id: str | None,
) -> bool:
    return (
        selected_task_recall_workflow_id is not None
        and latest_task_recall_workflow_id is not None
        and selected_task_recall_workflow_id != latest_task_recall_workflow_id
    )


def apply_semantic_only_discount(
    *,
    lexical_score: float,
    semantic_score: float,
    lexical_component: float,
    semantic_component: float,
    semantic_only_discount: float,
) -> tuple[float, str, bool]:
    score_mode = "hybrid"
    hybrid_score = lexical_component + semantic_component
    semantic_only_discount_applied = False

    if lexical_score <= 0 and semantic_score > 0:
        hybrid_score = semantic_component * semantic_only_discount
        score_mode = "semantic_only_discounted"
        semantic_only_discount_applied = True
    elif lexical_score > 0 and semantic_score <= 0:
        score_mode = "lexical_only"

    return hybrid_score, score_mode, semantic_only_discount_applied


def build_search_ranking_reasons(
    *,
    lexical_score: float,
    semantic_score: float,
    score_mode: str,
    semantic_only_discount_applied: bool,
    semantic_only_discount: float,
    selected_continuation_target_bonus_applied: bool,
    selected_task_recall_memory_bonus: float,
) -> list[dict[str, Any]]:
    ranking_reasons: list[dict[str, Any]] = []

    if lexical_score > 0:
        ranking_reasons.append(
            {
                "code": "lexical_signal_present",
                "message": "lexical overlap contributed to the ranking score",
                "value": lexical_score,
            }
        )
    else:
        ranking_reasons.append(
            {
                "code": "lexical_signal_absent",
                "message": "no lexical overlap contributed to the ranking score",
                "value": lexical_score,
            }
        )

    if semantic_score > 0:
        ranking_reasons.append(
            {
                "code": "semantic_signal_present",
                "message": "semantic similarity contributed to the ranking score",
                "value": semantic_score,
            }
        )
    else:
        ranking_reasons.append(
            {
                "code": "semantic_signal_absent",
                "message": "no semantic similarity contributed to the ranking score",
                "value": semantic_score,
            }
        )

    if score_mode == "hybrid":
        ranking_reasons.append(
            {
                "code": "hybrid_score_mode",
                "message": "both lexical and semantic components were combined",
            }
        )
    elif score_mode == "lexical_only":
        ranking_reasons.append(
            {
                "code": "lexical_only_score_mode",
                "message": "the result ranked using lexical evidence only",
            }
        )
    else:
        ranking_reasons.append(
            {
                "code": "semantic_only_discounted_score_mode",
                "message": "semantic-only evidence was discounted to avoid outranking lexical matches too aggressively",
            }
        )

    if semantic_only_discount_applied:
        ranking_reasons.append(
            {
                "code": "semantic_only_discount_applied",
                "message": "semantic-only scoring discount was applied",
                "value": semantic_only_discount,
            }
        )

    if selected_continuation_target_bonus_applied:
        ranking_reasons.append(
            {
                "code": "selected_continuation_target_bonus",
                "message": "the memory item aligned with the selected continuation target",
                "value": selected_task_recall_memory_bonus,
            }
        )

    return ranking_reasons


def build_search_task_recall_detail(
    *,
    memory_item: Any,
    combined_fields: tuple[str, ...],
    workspace_id: UUID | None,
    latest_task_recall_workflow_id: str | None,
    selected_task_recall_workflow_id: str | None,
    task_recall_selected_equals_latest: bool,
    latest_task_recall_signals: dict[str, Any],
    selected_task_recall_signals: dict[str, Any],
    latest_task_recall_ticket_detour_like: bool,
    latest_task_recall_checkpoint_detour_like: bool,
    selected_task_recall_ticket_detour_like: bool,
    selected_task_recall_checkpoint_detour_like: bool,
    selected_continuation_target_bonus_applied: bool,
    selected_task_recall_memory_bonus: float,
) -> dict[str, Any]:
    latest_vs_selected_comparison_present = (
        selected_task_recall_workflow_id is not None
        and latest_task_recall_workflow_id is not None
        and selected_task_recall_workflow_id != latest_task_recall_workflow_id
    )

    latest_vs_selected_candidate_details = (
        {
            "latest_workflow_instance_id": latest_task_recall_workflow_id,
            "selected_workflow_instance_id": selected_task_recall_workflow_id,
            "latest_considered": {
                "workflow_instance_id": latest_task_recall_workflow_id,
                "checkpoint_step_name": latest_task_recall_signals.get(
                    "latest_checkpoint_step_name"
                ),
                "checkpoint_summary": latest_task_recall_signals.get("latest_checkpoint_summary"),
                "primary_objective_text": latest_task_recall_signals.get(
                    "latest_checkpoint_current_objective"
                ),
                "next_intended_action_text": latest_task_recall_signals.get(
                    "latest_checkpoint_next_intended_action"
                ),
                "ticket_detour_like": latest_task_recall_ticket_detour_like,
                "checkpoint_detour_like": latest_task_recall_checkpoint_detour_like,
                "detour_like": (
                    latest_task_recall_ticket_detour_like
                    or latest_task_recall_checkpoint_detour_like
                ),
                "workflow_terminal": bool(
                    latest_task_recall_signals.get("workflow_is_terminal", False)
                ),
                "has_attempt_signal": bool(
                    latest_task_recall_signals.get("has_latest_attempt", False)
                ),
                "attempt_terminal": bool(
                    latest_task_recall_signals.get("latest_attempt_is_terminal", False)
                ),
                "has_checkpoint_signal": bool(
                    latest_task_recall_signals.get("has_latest_checkpoint", False)
                ),
            },
            "selected": {
                "workflow_instance_id": selected_task_recall_workflow_id,
                "checkpoint_step_name": selected_task_recall_signals.get(
                    "latest_checkpoint_step_name"
                ),
                "checkpoint_summary": selected_task_recall_signals.get("latest_checkpoint_summary"),
                "primary_objective_text": selected_task_recall_signals.get(
                    "latest_checkpoint_current_objective"
                ),
                "next_intended_action_text": selected_task_recall_signals.get(
                    "latest_checkpoint_next_intended_action"
                ),
                "ticket_detour_like": selected_task_recall_ticket_detour_like,
                "checkpoint_detour_like": selected_task_recall_checkpoint_detour_like,
                "detour_like": (
                    selected_task_recall_ticket_detour_like
                    or selected_task_recall_checkpoint_detour_like
                ),
                "workflow_terminal": bool(
                    selected_task_recall_signals.get("workflow_is_terminal", False)
                ),
                "has_attempt_signal": bool(
                    selected_task_recall_signals.get("has_latest_attempt", False)
                ),
                "attempt_terminal": bool(
                    selected_task_recall_signals.get("latest_attempt_is_terminal", False)
                ),
                "has_checkpoint_signal": bool(
                    selected_task_recall_signals.get("has_latest_checkpoint", False)
                ),
            },
            "same_workflow": task_recall_selected_equals_latest,
            "same_checkpoint_details": (
                latest_task_recall_signals.get("latest_checkpoint_step_name")
                == selected_task_recall_signals.get("latest_checkpoint_step_name")
                and latest_task_recall_signals.get("latest_checkpoint_summary")
                == selected_task_recall_signals.get("latest_checkpoint_summary")
                and latest_task_recall_signals.get("latest_checkpoint_current_objective")
                == selected_task_recall_signals.get("latest_checkpoint_current_objective")
                and latest_task_recall_signals.get("latest_checkpoint_next_intended_action")
                == selected_task_recall_signals.get("latest_checkpoint_next_intended_action")
                and latest_task_recall_ticket_detour_like == selected_task_recall_ticket_detour_like
                and latest_task_recall_checkpoint_detour_like
                == selected_task_recall_checkpoint_detour_like
                and bool(latest_task_recall_signals.get("workflow_is_terminal", False))
                == bool(selected_task_recall_signals.get("workflow_is_terminal", False))
                and bool(latest_task_recall_signals.get("has_latest_attempt", False))
                == bool(selected_task_recall_signals.get("has_latest_attempt", False))
                and bool(latest_task_recall_signals.get("latest_attempt_is_terminal", False))
                == bool(selected_task_recall_signals.get("latest_attempt_is_terminal", False))
                and bool(latest_task_recall_signals.get("has_latest_checkpoint", False))
                == bool(selected_task_recall_signals.get("has_latest_checkpoint", False))
            ),
            "comparison_source": "memory_search_task_recall_context",
        }
        if latest_vs_selected_comparison_present
        else {
            "latest_workflow_instance_id": None,
            "selected_workflow_instance_id": None,
            "latest_considered": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "selected": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "same_workflow": True,
            "same_checkpoint_details": True,
            "comparison_source": "memory_search_task_recall_context",
        }
    )

    return {
        "matched_fields": list(combined_fields),
        "memory_item_type": memory_item.type,
        "memory_item_provenance": memory_item.provenance,
        "metadata_match_candidates": list(metadata_query_strings(memory_item.metadata)),
        "workspace_constrained": workspace_id is not None,
        "task_recall_context_present": (
            workspace_id is not None and selected_task_recall_workflow_id is not None
        ),
        "latest_considered_workflow_instance_id": latest_task_recall_workflow_id,
        "selected_workflow_instance_id": selected_task_recall_workflow_id,
        "selected_equals_latest": task_recall_selected_equals_latest,
        "latest_considered_checkpoint_step_name": latest_task_recall_signals.get(
            "latest_checkpoint_step_name"
        ),
        "latest_considered_checkpoint_summary": latest_task_recall_signals.get(
            "latest_checkpoint_summary"
        ),
        "latest_considered_primary_objective_text": latest_task_recall_signals.get(
            "latest_checkpoint_current_objective"
        ),
        "latest_considered_next_intended_action_text": latest_task_recall_signals.get(
            "latest_checkpoint_next_intended_action"
        ),
        "selected_checkpoint_step_name": selected_task_recall_signals.get(
            "latest_checkpoint_step_name"
        ),
        "selected_checkpoint_summary": selected_task_recall_signals.get(
            "latest_checkpoint_summary"
        ),
        "selected_primary_objective_text": selected_task_recall_signals.get(
            "latest_checkpoint_current_objective"
        ),
        "selected_next_intended_action_text": selected_task_recall_signals.get(
            "latest_checkpoint_next_intended_action"
        ),
        "latest_considered_ticket_detour_like": latest_task_recall_ticket_detour_like,
        "latest_considered_checkpoint_detour_like": (latest_task_recall_checkpoint_detour_like),
        "selected_ticket_detour_like": selected_task_recall_ticket_detour_like,
        "selected_checkpoint_detour_like": selected_task_recall_checkpoint_detour_like,
        "latest_considered_workflow_terminal": bool(
            latest_task_recall_signals.get("workflow_is_terminal", False)
        ),
        "selected_workflow_terminal": bool(
            selected_task_recall_signals.get("workflow_is_terminal", False)
        ),
        "latest_vs_selected_comparison_present": latest_vs_selected_comparison_present,
        "latest_vs_selected_candidate_details": latest_vs_selected_candidate_details,
        "selected_continuation_target_bonus_applied": (selected_continuation_target_bonus_applied),
        "selected_continuation_target_bonus": (
            selected_task_recall_memory_bonus if selected_continuation_target_bonus_applied else 0.0
        ),
    }


def build_latest_vs_selected_search_context(
    *,
    latest_task_recall_workflow_id: str | None,
    selected_task_recall_workflow_id: str | None,
    latest_task_recall_signals: dict[str, Any],
    selected_task_recall_signals: dict[str, Any],
    latest_task_recall_ticket_detour_like: bool,
    latest_task_recall_checkpoint_detour_like: bool,
    selected_task_recall_ticket_detour_like: bool,
    selected_task_recall_checkpoint_detour_like: bool,
    task_recall_selected_equals_latest: bool,
) -> tuple[bool, dict[str, Any]]:
    latest_vs_selected_search_context_present = (
        selected_task_recall_workflow_id is not None
        and latest_task_recall_workflow_id is not None
        and selected_task_recall_workflow_id != latest_task_recall_workflow_id
    )

    latest_vs_selected_search_context = (
        {
            "latest_workflow_instance_id": latest_task_recall_workflow_id,
            "selected_workflow_instance_id": selected_task_recall_workflow_id,
            "latest_considered": {
                "workflow_instance_id": latest_task_recall_workflow_id,
                "checkpoint_step_name": latest_task_recall_signals.get(
                    "latest_checkpoint_step_name"
                ),
                "checkpoint_summary": latest_task_recall_signals.get("latest_checkpoint_summary"),
                "primary_objective_text": latest_task_recall_signals.get(
                    "latest_checkpoint_current_objective"
                ),
                "next_intended_action_text": latest_task_recall_signals.get(
                    "latest_checkpoint_next_intended_action"
                ),
                "ticket_detour_like": latest_task_recall_ticket_detour_like,
                "checkpoint_detour_like": latest_task_recall_checkpoint_detour_like,
                "detour_like": (
                    latest_task_recall_ticket_detour_like
                    or latest_task_recall_checkpoint_detour_like
                ),
                "workflow_terminal": bool(
                    latest_task_recall_signals.get("workflow_is_terminal", False)
                ),
                "has_attempt_signal": bool(
                    latest_task_recall_signals.get("has_latest_attempt", False)
                ),
                "attempt_terminal": bool(
                    latest_task_recall_signals.get("latest_attempt_is_terminal", False)
                ),
                "has_checkpoint_signal": bool(
                    latest_task_recall_signals.get("has_latest_checkpoint", False)
                ),
            },
            "selected": {
                "workflow_instance_id": selected_task_recall_workflow_id,
                "checkpoint_step_name": selected_task_recall_signals.get(
                    "latest_checkpoint_step_name"
                ),
                "checkpoint_summary": selected_task_recall_signals.get("latest_checkpoint_summary"),
                "primary_objective_text": selected_task_recall_signals.get(
                    "latest_checkpoint_current_objective"
                ),
                "next_intended_action_text": selected_task_recall_signals.get(
                    "latest_checkpoint_next_intended_action"
                ),
                "ticket_detour_like": selected_task_recall_ticket_detour_like,
                "checkpoint_detour_like": selected_task_recall_checkpoint_detour_like,
                "detour_like": (
                    selected_task_recall_ticket_detour_like
                    or selected_task_recall_checkpoint_detour_like
                ),
                "workflow_terminal": bool(
                    selected_task_recall_signals.get("workflow_is_terminal", False)
                ),
                "has_attempt_signal": bool(
                    selected_task_recall_signals.get("has_latest_attempt", False)
                ),
                "attempt_terminal": bool(
                    selected_task_recall_signals.get("latest_attempt_is_terminal", False)
                ),
                "has_checkpoint_signal": bool(
                    selected_task_recall_signals.get("has_latest_checkpoint", False)
                ),
            },
            "same_workflow": task_recall_selected_equals_latest,
            "same_checkpoint_details": (
                latest_task_recall_signals.get("latest_checkpoint_step_name")
                == selected_task_recall_signals.get("latest_checkpoint_step_name")
                and latest_task_recall_signals.get("latest_checkpoint_summary")
                == selected_task_recall_signals.get("latest_checkpoint_summary")
                and latest_task_recall_signals.get("latest_checkpoint_current_objective")
                == selected_task_recall_signals.get("latest_checkpoint_current_objective")
                and latest_task_recall_signals.get("latest_checkpoint_next_intended_action")
                == selected_task_recall_signals.get("latest_checkpoint_next_intended_action")
                and latest_task_recall_ticket_detour_like == selected_task_recall_ticket_detour_like
                and latest_task_recall_checkpoint_detour_like
                == selected_task_recall_checkpoint_detour_like
                and bool(latest_task_recall_signals.get("workflow_is_terminal", False))
                == bool(selected_task_recall_signals.get("workflow_is_terminal", False))
                and bool(latest_task_recall_signals.get("has_latest_attempt", False))
                == bool(selected_task_recall_signals.get("has_latest_attempt", False))
                and bool(latest_task_recall_signals.get("latest_attempt_is_terminal", False))
                == bool(selected_task_recall_signals.get("latest_attempt_is_terminal", False))
                and bool(latest_task_recall_signals.get("has_latest_checkpoint", False))
                == bool(selected_task_recall_signals.get("has_latest_checkpoint", False))
            ),
            "comparison_source": "memory_search_task_recall_context",
        }
        if latest_vs_selected_search_context_present
        else {
            "latest_workflow_instance_id": None,
            "selected_workflow_instance_id": None,
            "latest_considered": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "selected": {
                "workflow_instance_id": None,
                "checkpoint_step_name": None,
                "checkpoint_summary": None,
                "primary_objective_text": None,
                "next_intended_action_text": None,
                "ticket_detour_like": False,
                "checkpoint_detour_like": False,
                "detour_like": False,
                "workflow_terminal": False,
                "has_attempt_signal": False,
                "attempt_terminal": False,
                "has_checkpoint_signal": False,
            },
            "same_workflow": True,
            "same_checkpoint_details": True,
            "comparison_source": "memory_search_task_recall_context",
        }
    )

    return latest_vs_selected_search_context_present, latest_vs_selected_search_context


def build_latest_vs_selected_search_comparison_summary_explanations(
    *,
    latest_vs_selected_search_context_present: bool,
    latest_task_recall_signals: dict[str, Any],
    selected_task_recall_signals: dict[str, Any],
    latest_task_recall_ticket_detour_like: bool,
    latest_task_recall_checkpoint_detour_like: bool,
    selected_task_recall_ticket_detour_like: bool,
    selected_task_recall_checkpoint_detour_like: bool,
) -> list[dict[str, str]]:
    if not latest_vs_selected_search_context_present:
        return []

    selected_return_target_basis = (
        "checkpoint_current_objective"
        if bool(
            selected_task_recall_signals.get(
                "latest_checkpoint_has_current_objective",
                False,
            )
        )
        else (
            "checkpoint_next_intended_action"
            if bool(
                selected_task_recall_signals.get(
                    "latest_checkpoint_has_next_intended_action",
                    False,
                )
            )
            else "ranked_candidate"
        )
    )
    latest_return_target_basis = (
        "detour_penalized_candidate"
        if (latest_task_recall_ticket_detour_like or latest_task_recall_checkpoint_detour_like)
        else "latest_candidate"
    )

    selected_task_thread_basis = (
        "checkpoint_objective_or_next_action"
        if bool(
            selected_task_recall_signals.get(
                "latest_checkpoint_has_current_objective",
                False,
            )
        )
        or bool(
            selected_task_recall_signals.get(
                "latest_checkpoint_has_next_intended_action",
                False,
            )
        )
        else "non_detour_candidate"
    )
    latest_task_thread_basis = (
        "detour_penalized_candidate"
        if (latest_task_recall_ticket_detour_like or latest_task_recall_checkpoint_detour_like)
        else "non_detour_candidate"
    )

    explanations: list[dict[str, str]] = [
        {
            "code": "search_selected_differs_from_latest",
            "message": "search task-recall context recorded that the selected continuation target differed from the latest considered workflow",
        }
    ]

    checkpoints_differ = (
        latest_task_recall_signals.get("latest_checkpoint_step_name")
        != selected_task_recall_signals.get("latest_checkpoint_step_name")
        or latest_task_recall_signals.get("latest_checkpoint_summary")
        != selected_task_recall_signals.get("latest_checkpoint_summary")
        or latest_task_recall_signals.get("latest_checkpoint_current_objective")
        != selected_task_recall_signals.get("latest_checkpoint_current_objective")
        or latest_task_recall_signals.get("latest_checkpoint_next_intended_action")
        != selected_task_recall_signals.get("latest_checkpoint_next_intended_action")
    )
    if checkpoints_differ:
        explanations.append(
            {
                "code": "search_latest_and_selected_checkpoints_differ",
                "message": "search task-recall context recorded that the latest considered checkpoint differed from the selected continuation checkpoint",
            }
        )

    detour_classification_differs = (
        latest_task_recall_ticket_detour_like != selected_task_recall_ticket_detour_like
        or latest_task_recall_checkpoint_detour_like != selected_task_recall_checkpoint_detour_like
    )
    if detour_classification_differs:
        explanations.append(
            {
                "code": "search_latest_and_selected_detour_classification_differs",
                "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in detour classification",
            }
        )

    if selected_return_target_basis != latest_return_target_basis:
        explanations.append(
            {
                "code": "search_latest_and_selected_return_target_basis_differs",
                "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in return-target basis",
            }
        )

    if selected_task_thread_basis != latest_task_thread_basis:
        explanations.append(
            {
                "code": "search_latest_and_selected_task_thread_basis_differs",
                "message": "search task-recall context recorded that the latest considered candidate and selected continuation target differed in task-thread basis",
            }
        )

    return explanations


def build_search_response_details(
    *,
    request: Any,
    normalized_query: str,
    search_mode: str,
    memory_items_considered: int,
    semantic_result_count: int,
    semantic_query_generated: bool,
    lexical_weight: float,
    semantic_weight: float,
    semantic_only_discount: float,
    result_mode_counts: dict[str, int],
    result_composition: dict[str, int],
    results_returned: int,
    semantic_generation_skipped_reason: str | None,
    workspace_id: UUID | None,
    latest_task_recall_workflow_id: str | None,
    selected_task_recall_workflow_id: str | None,
    task_recall_selected_equals_latest: bool,
    latest_vs_selected_search_context_present: bool,
    latest_vs_selected_search_context: dict[str, Any],
    latest_vs_selected_search_comparison_summary_explanations: list[dict[str, str]],
) -> dict[str, Any]:
    details = {
        "query": request.query,
        "normalized_query": normalized_query,
        "workspace_id": request.workspace_id,
        "limit": request.limit,
        "filters": request.filters,
        "search_mode": search_mode,
        "memory_items_considered": memory_items_considered,
        "semantic_candidates_considered": semantic_result_count,
        "semantic_query_generated": semantic_query_generated,
        "hybrid_scoring": {
            "lexical_weight": lexical_weight,
            "semantic_weight": semantic_weight,
            "semantic_only_discount": semantic_only_discount,
        },
        "result_mode_counts": result_mode_counts,
        "result_composition": result_composition,
        "results_returned": results_returned,
        "semantic_generation_skipped_reason": semantic_generation_skipped_reason,
        "task_recall_context_present": (
            workspace_id is not None and selected_task_recall_workflow_id is not None
        ),
        "task_recall_latest_considered_workflow_instance_id": latest_task_recall_workflow_id,
        "task_recall_selected_workflow_instance_id": selected_task_recall_workflow_id,
        "task_recall_selected_equals_latest": task_recall_selected_equals_latest,
        "task_recall_latest_vs_selected_comparison_present": (
            latest_vs_selected_search_context_present
        ),
        "task_recall_latest_vs_selected_candidate_details": latest_vs_selected_search_context,
        "task_recall_latest_vs_selected_primary_block": "candidate_details",
        "task_recall_latest_vs_selected_checkpoint_details_is_compatibility_alias": True,
        "task_recall_latest_vs_selected_checkpoint_details_present": (
            latest_vs_selected_search_context_present
        ),
        "task_recall_latest_vs_selected_checkpoint_details": latest_vs_selected_search_context,
        "task_recall_comparison_summary_explanations_present": bool(
            latest_vs_selected_search_comparison_summary_explanations
        ),
        "task_recall_comparison_summary_explanations": (
            latest_vs_selected_search_comparison_summary_explanations
        ),
    }
    if semantic_generation_skipped_reason is not None:
        details["semantic_generation_skipped_reason"] = semantic_generation_skipped_reason
    return details


__all__ = [
    "apply_semantic_only_discount",
    "build_latest_vs_selected_search_comparison_summary_explanations",
    "build_latest_vs_selected_search_context",
    "build_search_ranking_reasons",
    "build_search_response_details",
    "build_search_task_recall_detail",
    "selected_task_recall_bonus_enabled",
]

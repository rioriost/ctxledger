from __future__ import annotations

from typing import Any


def _normalize_graph_status(graph_status: str | None) -> str | None:
    if graph_status is None:
        return None

    normalized = str(graph_status).strip()
    return normalized or None


def _graph_readiness_state_from_status(graph_status: str | None) -> str:
    normalized_status = _normalize_graph_status(graph_status)

    if normalized_status == "graph_ready":
        return "ready"
    if normalized_status == "graph_stale":
        return "stale"
    if normalized_status in {
        "age_unavailable",
        "graph_unavailable",
        "graph_degraded",
        "graph_read_failed",
    }:
        return "degraded"
    if normalized_status == "unknown":
        return "unknown"

    return "degraded" if normalized_status is not None else "unknown"


def _graph_readiness_operator_action(
    readiness_state: str,
    *,
    graph_status: str | None,
) -> str:
    if readiness_state == "ready":
        return "no_action_required"
    if readiness_state == "stale":
        return "refresh_age_summary_graph"
    if readiness_state == "degraded":
        normalized_status = _normalize_graph_status(graph_status)
        if normalized_status == "age_unavailable":
            return "verify_age_extension_and_database_image"
        if normalized_status == "graph_unavailable":
            return "bootstrap_or_refresh_age_summary_graph"
        if normalized_status == "graph_read_failed":
            return "inspect_graph_read_failure_and_refresh_if_needed"
        return "inspect_readiness_then_refresh_or_rebuild"
    return "inspect_age_graph_readiness"


def build_age_summary_graph_mirroring_details(
    *,
    age_enabled: bool,
    age_available: bool | None = None,
    graph_status: str | None = None,
    ready: bool | None = None,
) -> dict[str, Any]:
    normalized_status = _normalize_graph_status(graph_status)
    readiness_state = _graph_readiness_state_from_status(normalized_status)

    details: dict[str, Any] = {
        "enabled": age_enabled,
        "canonical_source": [
            "memory_summaries",
            "memory_summary_memberships",
        ],
        "derived_graph_labels": [
            "memory_summary",
            "memory_item",
            "summarizes",
        ],
        "relation_type": "summarizes",
        "selection_route": "graph_summary_auxiliary",
        "explainability_scope": "readiness",
        "refresh_command": "ctxledger refresh-age-summary-graph",
        "read_path_scope": "narrow_auxiliary_summary_member_traversal",
        "readiness_state": readiness_state,
        "stale": readiness_state == "stale",
        "degraded": readiness_state == "degraded",
        "operator_action": _graph_readiness_operator_action(
            readiness_state,
            graph_status=normalized_status,
        ),
    }

    if age_available is not None:
        details["age_available"] = age_available
    if normalized_status is not None:
        details["graph_status"] = normalized_status
    if ready is not None:
        details["ready"] = ready
    elif normalized_status is not None:
        details["ready"] = normalized_status == "graph_ready"

    return details

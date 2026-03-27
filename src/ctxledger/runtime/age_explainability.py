from __future__ import annotations

from typing import Any


def build_age_summary_graph_mirroring_details(
    *,
    age_enabled: bool,
    age_available: bool | None = None,
    graph_status: str | None = None,
    ready: bool | None = None,
) -> dict[str, Any]:
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
    }

    if age_available is not None:
        details["age_available"] = age_available
    if graph_status is not None:
        details["graph_status"] = graph_status
    if ready is not None:
        details["ready"] = ready

    return details

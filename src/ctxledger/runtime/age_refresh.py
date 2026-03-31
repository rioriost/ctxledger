from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def refresh_age_summary_graph(
    *,
    database_url: str,
    graph_name: str,
    psycopg_module: Any,
) -> dict[str, int | str]:
    """
    Rebuild the derived AGE summary graph from canonical relational summary state.

    This helper intentionally mirrors the current bounded refresh behavior used by
    the CLI/runtime flow:

    - ensure the AGE graph exists
    - remove existing derived `memory_summary` nodes and `summarizes` edges
    - rebuild summary nodes from `public.memory_summaries`
    - rebuild summary membership edges from `public.memory_summary_memberships`

    Returns a small operator-facing payload with rebuilt counts.
    """
    if not database_url or not database_url.strip():
        raise ValueError("database_url must be a non-empty string")
    if not graph_name or not graph_name.strip():
        raise ValueError("graph_name must be a non-empty string")
    if psycopg_module is None:
        raise ValueError("psycopg_module is required")

    normalized_database_url = database_url.strip()
    normalized_graph_name = graph_name.strip()
    graph_name_literal = "'" + normalized_graph_name.replace("'", "''") + "'"

    summary_node_count = 0
    membership_edge_count = 0

    with psycopg_module.connect(normalized_database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("LOAD 'age'")
            cursor.execute('SET search_path = ag_catalog, "$user", public')

            cursor.execute(
                """
                SELECT 1
                FROM ag_catalog.ag_graph
                WHERE name = %s
                LIMIT 1
                """,
                (normalized_graph_name,),
            )
            if cursor.fetchone() is None:
                cursor.execute(f"SELECT ag_catalog.create_graph({graph_name_literal})")

            cursor.execute(
                f"""
                SELECT *
                FROM cypher(
                    {graph_name_literal},
                    $$
                    MATCH (n:memory_summary)-[r:summarizes]->()
                    DELETE r
                    RETURN 1 AS cleared
                    $$
                ) AS (cleared agtype)
                """
            )
            cursor.execute(
                f"""
                SELECT *
                FROM cypher(
                    {graph_name_literal},
                    $$
                    MATCH (n:memory_summary)
                    DETACH DELETE n
                    RETURN 1 AS cleared
                    $$
                ) AS (cleared agtype)
                """
            )

            cursor.execute(
                """
                SELECT
                    memory_summary_id,
                    workspace_id,
                    episode_id,
                    summary_kind
                FROM public.memory_summaries
                ORDER BY created_at DESC, memory_summary_id DESC
                """
            )
            summary_rows = cursor.fetchall()
            for summary_row in summary_rows:
                if isinstance(summary_row, tuple):
                    (
                        raw_memory_summary_id,
                        raw_workspace_id,
                        raw_episode_id,
                        raw_summary_kind,
                    ) = summary_row
                else:
                    raw_memory_summary_id = summary_row["memory_summary_id"]
                    raw_workspace_id = summary_row["workspace_id"]
                    raw_episode_id = summary_row["episode_id"]
                    raw_summary_kind = summary_row["summary_kind"]

                summary_params = json.dumps(
                    {
                        "memory_summary_id": str(raw_memory_summary_id),
                        "workspace_id": str(raw_workspace_id),
                        "episode_id": (str(raw_episode_id) if raw_episode_id is not None else None),
                        "summary_kind": str(raw_summary_kind),
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                cursor.execute(
                    f"""
                    SELECT *
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        CREATE (n:memory_summary {{memory_summary_id: $memory_summary_id, workspace_id: $workspace_id, episode_id: $episode_id, summary_kind: $summary_kind}})
                        RETURN n
                        $$,
                        %s
                    ) AS (n agtype)
                    """,
                    (summary_params,),
                )

            cursor.execute(
                """
                SELECT
                    memory_summary_membership_id,
                    memory_summary_id,
                    memory_id,
                    membership_order
                FROM public.memory_summary_memberships
                ORDER BY
                    memory_summary_id ASC,
                    membership_order ASC NULLS LAST,
                    created_at ASC,
                    memory_summary_membership_id ASC
                """
            )
            membership_rows = cursor.fetchall()
            for membership_row in membership_rows:
                if isinstance(membership_row, tuple):
                    (
                        raw_membership_id,
                        raw_memory_summary_id,
                        raw_memory_id,
                        raw_membership_order,
                    ) = membership_row
                else:
                    raw_membership_id = membership_row["memory_summary_membership_id"]
                    raw_memory_summary_id = membership_row["memory_summary_id"]
                    raw_memory_id = membership_row["memory_id"]
                    raw_membership_order = membership_row["membership_order"]

                membership_params = json.dumps(
                    {
                        "memory_summary_membership_id": str(raw_membership_id),
                        "memory_summary_id": str(raw_memory_summary_id),
                        "memory_id": str(raw_memory_id),
                        "membership_order": raw_membership_order,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                )
                cursor.execute(
                    f"""
                    SELECT *
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH (summary:memory_summary {{memory_summary_id: $memory_summary_id}})
                        MATCH (item:memory_item {{memory_id: $memory_id}})
                        CREATE (summary)-[r:summarizes {{memory_summary_membership_id: $memory_summary_membership_id, memory_summary_id: $memory_summary_id, memory_id: $memory_id, membership_order: $membership_order}}]->(item)
                        RETURN r
                        $$,
                        %s
                    ) AS (r agtype)
                    """,
                    (membership_params,),
                )

            cursor.execute(
                f"""
                SELECT *
                FROM cypher(
                    {graph_name_literal},
                    $$
                    MATCH (n:memory_summary)
                    RETURN count(n) AS node_count
                    $$
                ) AS (node_count agtype)
                """
            )
            summary_node_count_row = cursor.fetchone()
            if summary_node_count_row is not None:
                raw_summary_node_count = (
                    summary_node_count_row[0]
                    if isinstance(summary_node_count_row, tuple)
                    else summary_node_count_row["node_count"]
                )
                summary_node_count = int(str(raw_summary_node_count).strip('"'))

            cursor.execute(
                f"""
                SELECT *
                FROM cypher(
                    {graph_name_literal},
                    $$
                    MATCH (:memory_summary)-[r:summarizes]->(:memory_item)
                    RETURN count(r) AS edge_count
                    $$
                ) AS (edge_count agtype)
                """
            )
            membership_edge_count_row = cursor.fetchone()
            if membership_edge_count_row is not None:
                raw_membership_edge_count = (
                    membership_edge_count_row[0]
                    if isinstance(membership_edge_count_row, tuple)
                    else membership_edge_count_row["edge_count"]
                )
                membership_edge_count = int(str(raw_membership_edge_count).strip('"'))

        connection.commit()

    payload = {
        "graph_name": normalized_graph_name,
        "memory_summary_node_count": int(summary_node_count),
        "summarizes_edge_count": int(membership_edge_count),
    }
    logger.info("AGE summary graph refresh completed", extra=payload)
    return payload


__all__ = ["refresh_age_summary_graph"]

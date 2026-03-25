from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from uuid import UUID


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ctxledger",
        description="ctxledger durable workflow runtime bootstrap CLI",
    )

    subparsers = parser.add_subparsers(dest="command")

    stats_parser = subparsers.add_parser(
        "stats",
        help="Display workflow and memory observability summary",
    )
    stats_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    workflows_parser = subparsers.add_parser(
        "workflows",
        help="List recent workflows and their operational status",
    )
    workflows_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of workflows to return",
    )
    workflows_parser.add_argument(
        "--status",
        choices=("running", "completed", "failed", "cancelled"),
        help="Filter by workflow status",
    )
    workflows_parser.add_argument(
        "--workspace-id",
        help="Filter by workspace ID",
    )
    workflows_parser.add_argument(
        "--ticket-id",
        help="Filter by ticket ID",
    )
    workflows_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    failures_parser = subparsers.add_parser(
        "failures",
        help="List recent failures and their lifecycle state",
    )
    failures_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of failures to return",
    )
    failures_parser.add_argument(
        "--status",
        choices=("open", "resolved", "ignored"),
        help="Filter by failure status",
    )
    failures_parser.add_argument(
        "--open-only",
        action="store_true",
        help="Show only open failures",
    )
    failures_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    memory_stats_parser = subparsers.add_parser(
        "memory-stats",
        help="Display canonical memory observability summary",
    )
    memory_stats_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the ctxledger server",
    )
    serve_parser.add_argument(
        "--transport",
        choices=("http",),
        help="Transport mode to run",
    )
    serve_parser.add_argument(
        "--host",
        help="Host to bind for HTTP transport",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        help="Port to bind for HTTP transport",
    )

    schema_parser = subparsers.add_parser(
        "print-schema-path",
        help="Print the bundled PostgreSQL schema file path",
    )
    schema_parser.add_argument(
        "--absolute",
        action="store_true",
        help="Print the absolute schema path",
    )

    apply_schema_parser = subparsers.add_parser(
        "apply-schema",
        help="Apply the bundled PostgreSQL schema to the configured database",
    )
    apply_schema_parser.add_argument(
        "--database-url",
        help="Override the database URL instead of using CTXLEDGER_DATABASE_URL",
    )

    bootstrap_age_graph_parser = subparsers.add_parser(
        "bootstrap-age-graph",
        help="Create and populate the constrained AGE prototype graph",
    )
    bootstrap_age_graph_parser.add_argument(
        "--database-url",
        help="Override the database URL instead of using CTXLEDGER_DATABASE_URL",
    )
    bootstrap_age_graph_parser.add_argument(
        "--graph-name",
        help="Override the AGE graph name instead of using CTXLEDGER_DB_AGE_GRAPH_NAME",
    )

    age_graph_readiness_parser = subparsers.add_parser(
        "age-graph-readiness",
        help="Check constrained AGE prototype graph readiness",
    )
    age_graph_readiness_parser.add_argument(
        "--database-url",
        help="Override the database URL instead of using CTXLEDGER_DATABASE_URL",
    )
    age_graph_readiness_parser.add_argument(
        "--graph-name",
        help="Override the AGE graph name instead of using CTXLEDGER_DB_AGE_GRAPH_NAME",
    )

    refresh_age_summary_graph_parser = subparsers.add_parser(
        "refresh-age-summary-graph",
        help="Refresh derived AGE summary mirroring from canonical relational summaries",
    )
    refresh_age_summary_graph_parser.add_argument(
        "--database-url",
        help="Override the database URL instead of using CTXLEDGER_DATABASE_URL",
    )
    refresh_age_summary_graph_parser.add_argument(
        "--graph-name",
        help="Override the AGE graph name instead of using CTXLEDGER_DB_AGE_GRAPH_NAME",
    )

    build_episode_summary_parser = subparsers.add_parser(
        "build-episode-summary",
        help="Build one canonical episode summary from the episode's memory items",
    )
    build_episode_summary_parser.add_argument(
        "--episode-id",
        required=True,
        help="Episode ID to summarize",
    )
    build_episode_summary_parser.add_argument(
        "--summary-kind",
        default="episode_summary",
        help="Summary kind to build",
    )
    build_episode_summary_parser.add_argument(
        "--no-replace-existing",
        action="store_true",
        help="Keep existing summaries of the same kind instead of replacing them",
    )
    build_episode_summary_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    resume_workflow_parser = subparsers.add_parser(
        "resume-workflow",
        help="Display resumable workflow state for a workflow instance",
    )
    resume_workflow_parser.add_argument(
        "--workflow-instance-id",
        required=True,
        help="Workflow instance ID to inspect",
    )
    resume_workflow_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )

    subparsers.add_parser(
        "version",
        help="Print the ctxledger package version",
    )

    return parser


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "postgres.sql"


def _print_version() -> int:
    from .version import get_app_version

    print(get_app_version())
    return 0


def _print_schema_path(absolute: bool) -> int:
    path = _schema_path()
    print(path if absolute else path.as_posix())
    return 0


def _bootstrap_age_graph(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings

        try:
            import psycopg
        except ImportError:
            print(
                "Failed to import PostgreSQL driver. Install psycopg[binary] first.",
                file=sys.stderr,
            )
            return 1

        settings = get_settings()
        database_url = args.database_url or settings.database.url
        graph_name = args.graph_name or settings.database.age_graph_name

        if not database_url:
            return _print_missing_database_url(include_override_hint=True)

        if not graph_name:
            print(
                "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name.",
                file=sys.stderr,
            )
            return 1

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("LOAD 'age'")
                cursor.execute('SET search_path = ag_catalog, "$user", public')
                graph_name_literal = "'" + graph_name.replace("'", "''") + "'"
                cursor.execute(
                    """
                    SELECT 1
                    FROM ag_catalog.ag_graph
                    WHERE name = %s
                    LIMIT 1
                    """,
                    (graph_name,),
                )
                if cursor.fetchone() is None:
                    cursor.execute(f"SELECT ag_catalog.create_graph({graph_name_literal})")
                cursor.execute(
                    f"""
                    SELECT *
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH (n)
                        DETACH DELETE n
                        RETURN 1 AS cleared
                        $$
                    ) AS (cleared agtype)
                    """,
                )
                cursor.execute(
                    f"""
                    SELECT *
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        UNWIND [] AS ignored
                        RETURN ignored
                        $$
                    ) AS (ignored agtype)
                    WHERE false
                    """,
                )
                cursor.execute(
                    """
                    SELECT memory_id
                    FROM public.memory_items
                    """,
                )
                memory_item_rows = cursor.fetchall()
                for memory_item_row in memory_item_rows:
                    raw_memory_id = (
                        memory_item_row[0]
                        if isinstance(memory_item_row, tuple)
                        else memory_item_row["memory_id"]
                    )
                    memory_item_params = json.dumps(
                        {"memory_id": str(raw_memory_id)},
                        separators=(",", ":"),
                        sort_keys=True,
                    )
                    cursor.execute(
                        f"""
                        SELECT *
                        FROM cypher(
                            {graph_name_literal},
                            $$
                            CREATE (n:memory_item {memory_id: $memory_id})
                            RETURN n
                            $$,
                            %s
                        ) AS (n agtype)
                        """,
                        (memory_item_params,),
                    )
                cursor.execute(
                    """
                    SELECT
                        mr.memory_relation_id,
                        mr.source_memory_id,
                        mr.target_memory_id
                    FROM public.memory_relations AS mr
                    WHERE mr.relation_type = 'supports'
                    """,
                )
                supports_rows = cursor.fetchall()
                for supports_row in supports_rows:
                    if isinstance(supports_row, tuple):
                        (
                            raw_memory_relation_id,
                            raw_source_memory_id,
                            raw_target_memory_id,
                        ) = supports_row
                    else:
                        raw_memory_relation_id = supports_row["memory_relation_id"]
                        raw_source_memory_id = supports_row["source_memory_id"]
                        raw_target_memory_id = supports_row["target_memory_id"]

                    supports_params = json.dumps(
                        {
                            "memory_relation_id": str(raw_memory_relation_id),
                            "source_memory_id": str(raw_source_memory_id),
                            "target_memory_id": str(raw_target_memory_id),
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
                            MATCH (source:memory_item {memory_id: $source_memory_id})
                            MATCH (target:memory_item {memory_id: $target_memory_id})
                            CREATE (source)-[r:supports {
                            memory_relation_id: $memory_relation_id,
                                source_memory_id: $source_memory_id,
                                target_memory_id: $target_memory_id
                            }]->(target)
                            RETURN r
                            $$,
                            %s
                        ) AS (r agtype)
                        """,
                        (supports_params,),
                    )
                cursor.execute(
                    f"""
                    SELECT count(*)
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH (n:memory_item)
                        RETURN count(n) AS node_count
                        $$
                    ) AS (node_count agtype)
                    """,
                )
                memory_item_node_count_row = cursor.fetchone()
                memory_item_node_count = (
                    memory_item_node_count_row[0]
                    if isinstance(memory_item_node_count_row, tuple)
                    else memory_item_node_count_row["count"]
                )

                cursor.execute(
                    f"""
                    SELECT count(*)
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH ()-[r:supports]->()
                        RETURN count(r) AS edge_count
                        $$
                    ) AS (edge_count agtype)
                    """,
                )
                supports_edge_count_row = cursor.fetchone()
                supports_edge_count = (
                    supports_edge_count_row[0]
                    if isinstance(supports_edge_count_row, tuple)
                    else supports_edge_count_row["count"]
                )
            connection.commit()

        print(
            f"AGE graph bootstrap completed for '{graph_name}' "
            f"(memory_item nodes repopulated={memory_item_node_count}, "
            f"supports edges repopulated={supports_edge_count})."
        )
        return 0
    except Exception as exc:
        print(f"Failed to bootstrap AGE graph: {exc}", file=sys.stderr)
        return 1


def _age_graph_readiness(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings
        from .db.postgres import PostgresConfig, PostgresDatabaseHealthChecker

        settings = get_settings()
        database_url = args.database_url or settings.database.url
        graph_name = args.graph_name or settings.database.age_graph_name

        if not database_url:
            return _print_missing_database_url(include_override_hint=True)

        if not graph_name:
            print(
                "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name.",
                file=sys.stderr,
            )
            return 1

        config = PostgresConfig(
            database_url=database_url,
            connect_timeout_seconds=settings.database.connect_timeout_seconds,
            statement_timeout_ms=settings.database.statement_timeout_ms,
            schema_name=settings.database.schema_name,
            pool_min_size=settings.database.pool_min_size,
            pool_max_size=settings.database.pool_max_size,
            pool_timeout_seconds=settings.database.pool_timeout_seconds,
            age_enabled=settings.database.age_enabled,
            age_graph_name=graph_name,
        )
        checker = PostgresDatabaseHealthChecker(config)
        status = checker.age_graph_status(graph_name)
        status_value = getattr(status, "value", str(status))
        age_available = checker.age_available()

        print(
            json.dumps(
                {
                    "age_enabled": settings.database.age_enabled,
                    "age_graph_name": graph_name,
                    "age_available": age_available,
                    "age_graph_status": status_value,
                    "summary_graph_mirroring": {
                        "enabled": settings.database.age_enabled,
                        "canonical_source": [
                            "memory_summaries",
                            "memory_summary_memberships",
                        ],
                        "derived_graph_labels": [
                            "memory_summary",
                            "memory_item",
                            "summarizes",
                        ],
                        "refresh_command": "ctxledger refresh-age-summary-graph",
                        "read_path_scope": "narrow_auxiliary_summary_member_traversal",
                        "graph_status": status_value,
                        "ready": status_value == "graph_ready",
                    },
                    "workflow_summary_automation": {
                        "orchestration_point": "workflow_completion_auto_memory",
                        "requested": False,
                        "trigger": "latest_checkpoint.build_episode_summary_true",
                        "target_scope": "workflow_completion_auto_memory_episode",
                        "summary_kind": "episode_summary",
                        "replace_existing": True,
                        "non_fatal": True,
                    },
                }
            )
        )
        return 0
    except Exception as exc:
        print(f"Failed to check AGE graph readiness: {exc}", file=sys.stderr)
        return 1


def _refresh_age_summary_graph(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings

        try:
            import psycopg
        except ImportError:
            print(
                "Failed to import PostgreSQL driver. Install psycopg[binary] first.",
                file=sys.stderr,
            )
            return 1

        settings = get_settings()
        database_url = args.database_url or settings.database.url
        graph_name = args.graph_name or settings.database.age_graph_name

        if not database_url:
            return _print_missing_database_url(include_override_hint=True)

        if not graph_name:
            print(
                "AGE graph name is required. Set CTXLEDGER_DB_AGE_GRAPH_NAME or pass --graph-name.",
                file=sys.stderr,
            )
            return 1

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute("LOAD 'age'")
                cursor.execute('SET search_path = ag_catalog, "$user", public')
                graph_name_literal = "'" + graph_name.replace("'", "''") + "'"
                cursor.execute(
                    """
                    SELECT 1
                    FROM ag_catalog.ag_graph
                    WHERE name = %s
                    LIMIT 1
                    """,
                    (graph_name,),
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
                    """,
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
                    """,
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
                            "episode_id": (
                                str(raw_episode_id) if raw_episode_id is not None else None
                            ),
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
                    SELECT count(*)
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH (n:memory_summary)
                        RETURN count(n) AS node_count
                        $$
                    ) AS (node_count agtype)
                    """,
                )
                summary_node_count_row = cursor.fetchone()
                summary_node_count = (
                    summary_node_count_row[0]
                    if isinstance(summary_node_count_row, tuple)
                    else summary_node_count_row["count"]
                )

                cursor.execute(
                    f"""
                    SELECT count(*)
                    FROM cypher(
                        {graph_name_literal},
                        $$
                        MATCH (:memory_summary)-[r:summarizes]->(:memory_item)
                        RETURN count(r) AS edge_count
                        $$
                    ) AS (edge_count agtype)
                    """,
                )
                membership_edge_count_row = cursor.fetchone()
                membership_edge_count = (
                    membership_edge_count_row[0]
                    if isinstance(membership_edge_count_row, tuple)
                    else membership_edge_count_row["count"]
                )
            connection.commit()

        print(
            f"AGE summary graph refresh completed for '{graph_name}' "
            f"(memory_summary nodes rebuilt={summary_node_count}, "
            f"summarizes edges rebuilt={membership_edge_count})."
        )
        return 0
    except Exception as exc:
        print(f"Failed to refresh AGE summary graph: {exc}", file=sys.stderr)
        return 1


def _apply_schema(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings
        from .db.postgres import load_postgres_schema_sql

        try:
            import psycopg
        except ImportError:
            print(
                "Failed to import PostgreSQL driver. Install psycopg[binary] first.",
                file=sys.stderr,
            )
            return 1

        database_url = args.database_url
        if database_url is None:
            settings = get_settings()
            database_url = settings.database.url

        if not database_url:
            return _print_missing_database_url(include_override_hint=True)

        schema_sql = load_postgres_schema_sql()

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
            connection.commit()

        print("Schema applied successfully.")
        return 0
    except Exception as exc:
        print(f"Failed to apply schema: {exc}", file=sys.stderr)
        return 1


def _print_missing_database_url(*, include_override_hint: bool = False) -> int:
    message = "Database URL is required. Set CTXLEDGER_DATABASE_URL"
    if include_override_hint:
        message += " or pass --database-url"
    print(f"{message}.", file=sys.stderr)
    return 1


def _build_postgres_workflow_service() -> tuple[object, object, object]:
    from .config import get_settings
    from .db.postgres import (
        PostgresConfig,
        build_connection_pool,
        build_postgres_uow_factory,
    )
    from .workflow.service import WorkflowService

    settings = get_settings()

    if not settings.database.url:
        raise RuntimeError("missing_database_url")

    postgres_config = PostgresConfig.from_settings(settings)
    connection_pool = build_connection_pool(postgres_config)
    uow_factory = build_postgres_uow_factory(postgres_config, connection_pool)

    workflow_service = WorkflowService(uow_factory)
    return settings, workflow_service, connection_pool


def _print_json_payload(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _isoformat_or_none(value: object) -> str | None:
    return value.isoformat() if value is not None else None


def _apply_schema(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings
        from .db.postgres import load_postgres_schema_sql

        try:
            import psycopg
        except ImportError:
            print(
                "Failed to import PostgreSQL driver. Install psycopg[binary] first.",
                file=sys.stderr,
            )
            return 1

        database_url = args.database_url
        if database_url is None:
            settings = get_settings()
            database_url = settings.database.url

        if not database_url:
            return _print_missing_database_url(include_override_hint=True)

        schema_sql = load_postgres_schema_sql()

        with psycopg.connect(database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(schema_sql)
            connection.commit()

        print("Schema applied successfully.")
        return 0
    except Exception as exc:
        print(f"Failed to apply schema: {exc}", file=sys.stderr)
        return 1


def _format_stats_text(stats: object) -> str:
    workflow_status_counts = getattr(stats, "workflow_status_counts", {})
    attempt_status_counts = getattr(stats, "attempt_status_counts", {})
    verify_status_counts = getattr(stats, "verify_status_counts", {})

    lines = [
        "ctxledger stats",
        "",
        "Workspaces:",
        f"- total: {getattr(stats, 'workspace_count', 0)}",
        "",
        "Workflows:",
        f"- running: {workflow_status_counts.get('running', 0)}",
        f"- completed: {workflow_status_counts.get('completed', 0)}",
        f"- failed: {workflow_status_counts.get('failed', 0)}",
        f"- cancelled: {workflow_status_counts.get('cancelled', 0)}",
        "",
        "Attempts:",
        f"- running: {attempt_status_counts.get('running', 0)}",
        f"- succeeded: {attempt_status_counts.get('succeeded', 0)}",
        f"- failed: {attempt_status_counts.get('failed', 0)}",
        f"- cancelled: {attempt_status_counts.get('cancelled', 0)}",
        "",
        "Verify reports:",
        f"- pending: {verify_status_counts.get('pending', 0)}",
        f"- passed: {verify_status_counts.get('passed', 0)}",
        f"- failed: {verify_status_counts.get('failed', 0)}",
        f"- skipped: {verify_status_counts.get('skipped', 0)}",
        "",
        "Memory:",
        f"- episodes: {getattr(stats, 'episode_count', 0)}",
        f"- memory_items: {getattr(stats, 'memory_item_count', 0)}",
        f"- memory_embeddings: {getattr(stats, 'memory_embedding_count', 0)}",
        "",
        "Other:",
        f"- checkpoints: {getattr(stats, 'checkpoint_count', 0)}",
        "",
        "Latest activity:",
        f"- workflow_updated_at: {getattr(stats, 'latest_workflow_updated_at', None)}",
        f"- checkpoint_created_at: {getattr(stats, 'latest_checkpoint_created_at', None)}",
        f"- verify_report_created_at: {getattr(stats, 'latest_verify_report_created_at', None)}",
        f"- episode_created_at: {getattr(stats, 'latest_episode_created_at', None)}",
        f"- memory_item_created_at: {getattr(stats, 'latest_memory_item_created_at', None)}",
        f"- memory_embedding_created_at: {getattr(stats, 'latest_memory_embedding_created_at', None)}",
    ]
    return "\n".join(lines)


def _stats(args: argparse.Namespace) -> int:
    try:
        try:
            _, workflow_service, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        try:
            stats = workflow_service.get_stats()
        finally:
            connection_pool.close()

        if args.format == "json":
            _print_json_payload(
                {
                    "workspace_count": stats.workspace_count,
                    "workflow_status_counts": stats.workflow_status_counts,
                    "attempt_status_counts": stats.attempt_status_counts,
                    "verify_status_counts": stats.verify_status_counts,
                    "checkpoint_count": stats.checkpoint_count,
                    "episode_count": stats.episode_count,
                    "memory_item_count": stats.memory_item_count,
                    "memory_embedding_count": stats.memory_embedding_count,
                    "latest_workflow_updated_at": _isoformat_or_none(
                        stats.latest_workflow_updated_at
                    ),
                    "latest_checkpoint_created_at": _isoformat_or_none(
                        stats.latest_checkpoint_created_at
                    ),
                    "latest_verify_report_created_at": _isoformat_or_none(
                        stats.latest_verify_report_created_at
                    ),
                    "latest_episode_created_at": _isoformat_or_none(
                        stats.latest_episode_created_at
                    ),
                    "latest_memory_item_created_at": _isoformat_or_none(
                        stats.latest_memory_item_created_at
                    ),
                    "latest_memory_embedding_created_at": _isoformat_or_none(
                        stats.latest_memory_embedding_created_at
                    ),
                }
            )
        else:
            print(_format_stats_text(stats))

        return 0
    except Exception as exc:
        print(f"Failed to load stats: {exc}", file=sys.stderr)
        return 1


def _format_workflows_text(workflows: list[object] | tuple[object, ...]) -> str:
    lines = ["ctxledger workflows", ""]

    if not workflows:
        lines.append("- none")
        return "\n".join(lines)

    for workflow in workflows:
        lines.append(
            f"- {getattr(workflow, 'workflow_instance_id', '')} "
            f"[{getattr(workflow, 'workflow_status', 'unknown')}]"
        )
        lines.append(
            f"  workspace={getattr(workflow, 'canonical_path', None) or getattr(workflow, 'workspace_id', '')}"
        )
        lines.append(f"  ticket={getattr(workflow, 'ticket_id', '')}")
        lines.append(f"  latest_step={getattr(workflow, 'latest_step_name', None) or 'none'}")
        lines.append(f"  verify_status={getattr(workflow, 'latest_verify_status', None) or 'none'}")
        lines.append(f"  updated_at={getattr(workflow, 'updated_at', None)}")
        lines.append("")

    if lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _workflows(args: argparse.Namespace) -> int:
    try:
        try:
            _, workflow_service, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        workspace_id = UUID(args.workspace_id) if args.workspace_id else None

        try:
            workflows = workflow_service.list_workflows(
                limit=max(args.limit, 1),
                status=args.status,
                workspace_id=workspace_id,
                ticket_id=args.ticket_id,
            )
        finally:
            connection_pool.close()

        if args.format == "json":
            _print_json_payload(
                [
                    {
                        "workflow_instance_id": str(workflow.workflow_instance_id),
                        "workspace_id": str(workflow.workspace_id),
                        "canonical_path": workflow.canonical_path,
                        "ticket_id": workflow.ticket_id,
                        "workflow_status": workflow.workflow_status,
                        "latest_step_name": workflow.latest_step_name,
                        "latest_verify_status": workflow.latest_verify_status,
                        "updated_at": _isoformat_or_none(workflow.updated_at),
                    }
                    for workflow in workflows
                ]
            )
        else:
            print(_format_workflows_text(workflows))

        return 0
    except Exception as exc:
        print(f"Failed to load workflows: {exc}", file=sys.stderr)
        return 1


def _format_memory_stats_text(stats: object) -> str:
    provenance_counts = getattr(stats, "memory_item_provenance_counts", {})

    lines = [
        "ctxledger memory-stats",
        "",
        "Counts:",
        f"- episodes: {getattr(stats, 'episode_count', 0)}",
        f"- memory_items: {getattr(stats, 'memory_item_count', 0)}",
        f"- memory_embeddings: {getattr(stats, 'memory_embedding_count', 0)}",
        f"- memory_relations: {getattr(stats, 'memory_relation_count', 0)}",
        "",
        "Memory item provenance:",
    ]

    if provenance_counts:
        for provenance in sorted(provenance_counts):
            lines.append(f"- {provenance}: {provenance_counts[provenance]}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Latest activity:",
            f"- episode_created_at: {getattr(stats, 'latest_episode_created_at', None)}",
            f"- memory_item_created_at: {getattr(stats, 'latest_memory_item_created_at', None)}",
            f"- memory_embedding_created_at: {getattr(stats, 'latest_memory_embedding_created_at', None)}",
            f"- memory_relation_created_at: {getattr(stats, 'latest_memory_relation_created_at', None)}",
        ]
    )

    return "\n".join(lines)


def _format_failures_text(failures: list[object] | tuple[object, ...]) -> str:
    lines = ["ctxledger failures", ""]

    if not failures:
        lines.append("- none")
        return "\n".join(lines)

    for failure in failures:
        lines.append(
            f"- {getattr(failure, 'failure_status', 'unknown')}: "
            f"{getattr(failure, 'failure_type', 'unknown')}"
        )
        lines.append(f"  scope={getattr(failure, 'failure_scope', 'unknown')}")
        lines.append(f"  path={getattr(failure, 'target_path', None) or 'none'}")
        lines.append(f"  error_code={getattr(failure, 'error_code', None) or 'none'}")
        lines.append(f"  message={getattr(failure, 'error_message', '')}")
        lines.append(f"  occurred_at={getattr(failure, 'occurred_at', None)}")
        lines.append(f"  resolved_at={getattr(failure, 'resolved_at', None)}")
        lines.append(f"  retry_count={getattr(failure, 'retry_count', 0)}")
        lines.append(f"  open_failures={getattr(failure, 'open_failure_count', 0)}")
        lines.append("")

    if lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _failures(args: argparse.Namespace) -> int:
    try:
        try:
            _, workflow_service, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        try:
            failures = workflow_service.list_failures(
                limit=args.limit,
                status=args.status,
                open_only=args.open_only,
            )
        finally:
            connection_pool.close()

        if args.format == "json":
            _print_json_payload(
                [
                    {
                        "failure_scope": failure.failure_scope,
                        "failure_type": failure.failure_type,
                        "failure_status": failure.failure_status,
                        "target_path": failure.target_path,
                        "error_code": failure.error_code,
                        "error_message": failure.error_message,
                        "attempt_id": (
                            str(failure.attempt_id) if failure.attempt_id is not None else None
                        ),
                        "occurred_at": _isoformat_or_none(failure.occurred_at),
                        "resolved_at": _isoformat_or_none(failure.resolved_at),
                        "open_failure_count": failure.open_failure_count,
                        "retry_count": failure.retry_count,
                    }
                    for failure in failures
                ]
            )
        else:
            print(_format_failures_text(failures))

        return 0
    except Exception as exc:
        print(f"Failed to load failures: {exc}", file=sys.stderr)
        return 1


def _memory_stats(args: argparse.Namespace) -> int:
    try:
        try:
            _, workflow_service, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        try:
            stats = workflow_service.get_memory_stats()
        finally:
            connection_pool.close()

        if args.format == "json":
            _print_json_payload(
                {
                    "episode_count": stats.episode_count,
                    "memory_item_count": stats.memory_item_count,
                    "memory_embedding_count": stats.memory_embedding_count,
                    "memory_relation_count": stats.memory_relation_count,
                    "memory_item_provenance_counts": (stats.memory_item_provenance_counts),
                    "latest_episode_created_at": _isoformat_or_none(
                        stats.latest_episode_created_at
                    ),
                    "latest_memory_item_created_at": _isoformat_or_none(
                        stats.latest_memory_item_created_at
                    ),
                    "latest_memory_embedding_created_at": _isoformat_or_none(
                        stats.latest_memory_embedding_created_at
                    ),
                    "latest_memory_relation_created_at": _isoformat_or_none(
                        stats.latest_memory_relation_created_at
                    ),
                }
            )
        else:
            print(_format_memory_stats_text(stats))

        return 0
    except Exception as exc:
        print(f"Failed to load memory stats: {exc}", file=sys.stderr)
        return 1


def _build_episode_summary(args: argparse.Namespace) -> int:
    try:
        from .memory import service as memory_service_module

        try:
            _, _, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        try:
            from .config import get_settings
            from .db.postgres import (
                PostgresConfig,
                PostgresDatabaseHealthChecker,
                build_postgres_uow_factory,
            )

            settings = get_settings()
            postgres_config = PostgresConfig.from_settings(settings)
            uow_factory = build_postgres_uow_factory(postgres_config, connection_pool)
            db_health_checker = PostgresDatabaseHealthChecker(postgres_config)

            memory_service = memory_service_module.MemoryService(
                episode_repository=memory_service_module.UnitOfWorkEpisodeRepository(uow_factory),
                memory_item_repository=memory_service_module.UnitOfWorkMemoryItemRepository(
                    uow_factory
                ),
                memory_summary_repository=memory_service_module.UnitOfWorkMemorySummaryRepository(
                    uow_factory
                ),
                memory_summary_membership_repository=(
                    memory_service_module.UnitOfWorkMemorySummaryMembershipRepository(uow_factory)
                ),
                workflow_lookup=memory_service_module.UnitOfWorkWorkflowLookupRepository(
                    uow_factory
                ),
                workspace_lookup=memory_service_module.UnitOfWorkWorkspaceLookupRepository(
                    uow_factory
                ),
                memory_relation_repository=(
                    memory_service_module.UnitOfWorkMemoryRelationRepository(
                        uow_factory,
                        config=postgres_config,
                        health_checker=db_health_checker,
                    )
                ),
            )

            result = memory_service.build_episode_summary(
                memory_service_module.BuildEpisodeSummaryRequest(
                    episode_id=args.episode_id,
                    summary_kind=args.summary_kind,
                    replace_existing=not args.no_replace_existing,
                )
            )
        finally:
            connection_pool.close()

        payload = {
            "feature": result.feature.value,
            "implemented": result.implemented,
            "message": result.message,
            "status": result.status,
            "available_in_version": result.available_in_version,
            "timestamp": result.timestamp.isoformat(),
            "summary_built": result.summary_built,
            "skipped_reason": result.skipped_reason,
            "replaced_existing_summary": result.replaced_existing_summary,
            "summary": (
                {
                    "memory_summary_id": str(result.summary.memory_summary_id),
                    "workspace_id": str(result.summary.workspace_id),
                    "episode_id": (
                        str(result.summary.episode_id)
                        if result.summary.episode_id is not None
                        else None
                    ),
                    "summary_text": result.summary.summary_text,
                    "summary_kind": result.summary.summary_kind,
                    "metadata": result.summary.metadata,
                    "created_at": result.summary.created_at.isoformat(),
                    "updated_at": result.summary.updated_at.isoformat(),
                }
                if result.summary is not None
                else None
            ),
            "memberships": [
                {
                    "memory_summary_membership_id": str(membership.memory_summary_membership_id),
                    "memory_summary_id": str(membership.memory_summary_id),
                    "memory_id": str(membership.memory_id),
                    "membership_order": membership.membership_order,
                    "metadata": membership.metadata,
                    "created_at": membership.created_at.isoformat(),
                }
                for membership in result.memberships
            ],
            "details": result.details,
        }

        if args.format == "json":
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
            return 0

        print("Build episode summary")
        print(f"Episode: {args.episode_id}")
        print(f"Summary kind: {args.summary_kind}")
        print(f"Status: {result.status}")
        print(f"Summary built: {'yes' if result.summary_built else 'no'}")
        print(f"Replaced existing summary: {'yes' if result.replaced_existing_summary else 'no'}")
        print(f"Skipped reason: {result.skipped_reason or 'none'}")

        if result.summary is not None:
            print(f"Summary ID: {result.summary.memory_summary_id}")
            print(f"Workspace ID: {result.summary.workspace_id}")
            print(f"Summary text: {result.summary.summary_text}")
        else:
            print("Summary ID: none")

        print(f"Membership count: {len(result.memberships)}")
        return 0
    except Exception as exc:
        print(f"Failed to build episode summary: {exc}", file=sys.stderr)
        return 1


def _resume_workflow(args: argparse.Namespace) -> int:
    try:
        from .runtime.serializers import serialize_workflow_resume
        from .workflow.service import ResumeWorkflowInput

        workflow_instance_id = UUID(args.workflow_instance_id)

        try:
            _, workflow_service, connection_pool = _build_postgres_workflow_service()
        except RuntimeError as exc:
            if str(exc) == "missing_database_url":
                return _print_missing_database_url()
            raise

        try:
            resume = workflow_service.resume_workflow(
                ResumeWorkflowInput(workflow_instance_id=workflow_instance_id)
            )
        finally:
            connection_pool.close()

        if args.format == "json":
            payload = serialize_workflow_resume(resume)
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
            return 0

        print("Resume workflow")
        print(f"Workflow: {resume.workflow_instance.workflow_instance_id}")
        print(f"Ticket: {resume.workflow_instance.ticket_id}")
        print(f"Workflow status: {resume.workflow_instance.status.value}")
        print(f"Resumable status: {resume.resumable_status.value}")
        print(f"Workspace: {resume.workspace.canonical_path}")
        print(f"Repository: {resume.workspace.repo_url}")

        if resume.attempt is not None:
            print(
                "Attempt: "
                f"{resume.attempt.attempt_id} "
                f"(#{resume.attempt.attempt_number}, {resume.attempt.status.value})"
            )
            if resume.attempt.verify_status is not None:
                print(f"Verify status: {resume.attempt.verify_status.value}")
        else:
            print("Attempt: none")

        if resume.latest_checkpoint is not None:
            print(f"Latest checkpoint step: {resume.latest_checkpoint.step_name}")
            if resume.latest_checkpoint.summary:
                print(f"Latest checkpoint summary: {resume.latest_checkpoint.summary}")
        else:
            print("Latest checkpoint: none")

        print("Warnings:")
        if not resume.warnings:
            print("- none")
        else:
            for warning in resume.warnings:
                print(f"- {warning.code}: {warning.message}")

        print(f"Next hint: {resume.next_hint or 'none'}")
        return 0
    except Exception as exc:
        print(f"Failed to resume workflow: {exc}", file=sys.stderr)
        return 1


def _serve(args: argparse.Namespace) -> int:
    try:
        from .server import run_server
    except ImportError as exc:
        print(f"Failed to import server runtime: {exc}", file=sys.stderr)
        return 1

    kwargs: dict[str, object] = {}
    if args.transport is not None:
        kwargs["transport"] = args.transport
    if args.host is not None:
        kwargs["host"] = args.host
    if args.port is not None:
        kwargs["port"] = args.port

    result = run_server(**kwargs)
    return int(result) if isinstance(result, int) else 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    command = args.command or "serve"

    if command == "stats":
        return _stats(args)
    if command == "workflows":
        return _workflows(args)
    if command == "failures":
        return _failures(args)
    if command == "memory-stats":
        return _memory_stats(args)
    if command == "serve":
        return _serve(args)
    if command == "print-schema-path":
        return _print_schema_path(args.absolute)
    if command == "apply-schema":
        return _apply_schema(args)
    if command == "bootstrap-age-graph":
        return _bootstrap_age_graph(args)
    if command == "age-graph-readiness":
        return _age_graph_readiness(args)
    if command == "refresh-age-summary-graph":
        return _refresh_age_summary_graph(args)
    if command == "build-episode-summary":
        return _build_episode_summary(args)
    if command == "resume-workflow":
        return _resume_workflow(args)
    if command == "version":
        return _print_version()

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

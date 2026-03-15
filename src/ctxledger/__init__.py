from __future__ import annotations

import argparse
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

    write_resume_projection_parser = subparsers.add_parser(
        "write-resume-projection",
        help="Write resume projections for a workflow instance",
    )
    write_resume_projection_parser.add_argument(
        "--workflow-instance-id",
        required=True,
        help="Workflow instance ID to project",
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
    try:
        from importlib.metadata import version

        print(version("ctxledger"))
    except Exception:
        print("0.2.0")
    return 0


def _print_schema_path(absolute: bool) -> int:
    path = _schema_path()
    print(path if absolute else path.as_posix())
    return 0


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
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url.",
                file=sys.stderr,
            )
            return 1

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


def _write_resume_projection(args: argparse.Namespace) -> int:
    try:
        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .projection.writer import ResumeProjectionWriter
        from .workflow.service import ResumeWorkflowInput, WorkflowService

        workflow_instance_id = UUID(args.workflow_instance_id)
        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(settings))
        )

        resume = workflow_service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workflow_instance_id)
        )
        workspace = resume.workspace

        writer = ResumeProjectionWriter(
            workflow_service=workflow_service,
            projection_settings=settings.projection,
        )
        result = writer.write_and_reconcile_resume_projection(
            workspace_root=workspace.canonical_path,
            workflow_instance_id=workflow_instance_id,
            workspace_id=workspace.workspace_id,
        )

        print("Resume projection written successfully.")
        if result.json_path is not None:
            print(f"JSON: {result.json_path}")
        if result.markdown_path is not None:
            print(f"Markdown: {result.markdown_path}")
        print(
            "Summary: "
            f"{len(result.state_updates)} state update(s), "
            f"{len(result.failure_updates)} failure update(s)"
        )
        return 0
    except Exception as exc:
        print(f"Failed to write resume projection: {exc}", file=sys.stderr)
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
        f"- open_projection_failures: {getattr(stats, 'open_projection_failure_count', 0)}",
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
        import json

        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .workflow.service import WorkflowService

        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(settings))
        )
        stats = workflow_service.get_stats()

        if args.format == "json":
            print(
                json.dumps(
                    {
                        "workspace_count": stats.workspace_count,
                        "workflow_status_counts": stats.workflow_status_counts,
                        "attempt_status_counts": stats.attempt_status_counts,
                        "verify_status_counts": stats.verify_status_counts,
                        "checkpoint_count": stats.checkpoint_count,
                        "episode_count": stats.episode_count,
                        "memory_item_count": stats.memory_item_count,
                        "memory_embedding_count": stats.memory_embedding_count,
                        "open_projection_failure_count": (
                            stats.open_projection_failure_count
                        ),
                        "latest_workflow_updated_at": (
                            stats.latest_workflow_updated_at.isoformat()
                            if stats.latest_workflow_updated_at is not None
                            else None
                        ),
                        "latest_checkpoint_created_at": (
                            stats.latest_checkpoint_created_at.isoformat()
                            if stats.latest_checkpoint_created_at is not None
                            else None
                        ),
                        "latest_verify_report_created_at": (
                            stats.latest_verify_report_created_at.isoformat()
                            if stats.latest_verify_report_created_at is not None
                            else None
                        ),
                        "latest_episode_created_at": (
                            stats.latest_episode_created_at.isoformat()
                            if stats.latest_episode_created_at is not None
                            else None
                        ),
                        "latest_memory_item_created_at": (
                            stats.latest_memory_item_created_at.isoformat()
                            if stats.latest_memory_item_created_at is not None
                            else None
                        ),
                        "latest_memory_embedding_created_at": (
                            stats.latest_memory_embedding_created_at.isoformat()
                            if stats.latest_memory_embedding_created_at is not None
                            else None
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
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
        lines.append(
            f"  latest_step={getattr(workflow, 'latest_step_name', None) or 'none'}"
        )
        lines.append(
            f"  verify_status={getattr(workflow, 'latest_verify_status', None) or 'none'}"
        )
        lines.append(f"  updated_at={getattr(workflow, 'updated_at', None)}")
        lines.append("")

    if lines[-1] == "":
        lines.pop()

    return "\n".join(lines)


def _workflows(args: argparse.Namespace) -> int:
    try:
        import json

        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .workflow.service import WorkflowService

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(get_settings()))
        )
        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workspace_id = UUID(args.workspace_id) if args.workspace_id else None
        workflows = workflow_service.list_workflows(
            limit=args.limit,
            status=args.status,
            workspace_id=workspace_id,
            ticket_id=args.ticket_id,
        )

        if args.format == "json":
            print(
                json.dumps(
                    [
                        {
                            "workflow_instance_id": str(workflow.workflow_instance_id),
                            "workspace_id": str(workflow.workspace_id),
                            "canonical_path": workflow.canonical_path,
                            "ticket_id": workflow.ticket_id,
                            "workflow_status": workflow.workflow_status,
                            "latest_step_name": workflow.latest_step_name,
                            "latest_verify_status": workflow.latest_verify_status,
                            "updated_at": (
                                workflow.updated_at.isoformat()
                                if workflow.updated_at is not None
                                else None
                            ),
                        }
                        for workflow in workflows
                    ],
                    indent=2,
                    sort_keys=True,
                )
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
        import json

        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .workflow.service import WorkflowService

        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(settings))
        )
        failures = workflow_service.list_failures(
            limit=args.limit,
            status=args.status,
            open_only=args.open_only,
        )

        if args.format == "json":
            print(
                json.dumps(
                    [
                        {
                            "failure_scope": failure.failure_scope,
                            "failure_type": failure.failure_type,
                            "failure_status": failure.failure_status,
                            "projection_type": failure.projection_type,
                            "target_path": failure.target_path,
                            "error_code": failure.error_code,
                            "error_message": failure.error_message,
                            "attempt_id": (
                                str(failure.attempt_id)
                                if failure.attempt_id is not None
                                else None
                            ),
                            "occurred_at": (
                                failure.occurred_at.isoformat()
                                if failure.occurred_at is not None
                                else None
                            ),
                            "resolved_at": (
                                failure.resolved_at.isoformat()
                                if failure.resolved_at is not None
                                else None
                            ),
                            "open_failure_count": failure.open_failure_count,
                            "retry_count": failure.retry_count,
                        }
                        for failure in failures
                    ],
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(_format_failures_text(failures))

        return 0
    except Exception as exc:
        print(f"Failed to load failures: {exc}", file=sys.stderr)
        return 1


def _memory_stats(args: argparse.Namespace) -> int:
    try:
        import json

        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .workflow.service import WorkflowService

        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(settings))
        )
        stats = workflow_service.get_memory_stats()

        if args.format == "json":
            print(
                json.dumps(
                    {
                        "episode_count": stats.episode_count,
                        "memory_item_count": stats.memory_item_count,
                        "memory_embedding_count": stats.memory_embedding_count,
                        "memory_relation_count": stats.memory_relation_count,
                        "memory_item_provenance_counts": (
                            stats.memory_item_provenance_counts
                        ),
                        "latest_episode_created_at": (
                            stats.latest_episode_created_at.isoformat()
                            if stats.latest_episode_created_at is not None
                            else None
                        ),
                        "latest_memory_item_created_at": (
                            stats.latest_memory_item_created_at.isoformat()
                            if stats.latest_memory_item_created_at is not None
                            else None
                        ),
                        "latest_memory_embedding_created_at": (
                            stats.latest_memory_embedding_created_at.isoformat()
                            if stats.latest_memory_embedding_created_at is not None
                            else None
                        ),
                        "latest_memory_relation_created_at": (
                            stats.latest_memory_relation_created_at.isoformat()
                            if stats.latest_memory_relation_created_at is not None
                            else None
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
        else:
            print(_format_memory_stats_text(stats))

        return 0
    except Exception as exc:
        print(f"Failed to load memory stats: {exc}", file=sys.stderr)
        return 1


def _resume_workflow(args: argparse.Namespace) -> int:
    try:
        import json

        from .config import get_settings
        from .db.postgres import PostgresConfig, build_postgres_uow_factory
        from .runtime.serializers import serialize_workflow_resume
        from .workflow.service import ResumeWorkflowInput, WorkflowService

        workflow_instance_id = UUID(args.workflow_instance_id)
        settings = get_settings()

        if not settings.database.url:
            print(
                "Database URL is required. Set CTXLEDGER_DATABASE_URL.",
                file=sys.stderr,
            )
            return 1

        workflow_service = WorkflowService(
            build_postgres_uow_factory(PostgresConfig.from_settings(settings))
        )
        resume = workflow_service.resume_workflow(
            ResumeWorkflowInput(workflow_instance_id=workflow_instance_id)
        )

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

        print("Projections:")
        if not resume.projections:
            print("- none")
        else:
            for projection in resume.projections:
                line = (
                    f"- {projection.projection_type.value}: {projection.status.value}"
                )
                if projection.target_path:
                    line += f" [{projection.target_path}]"
                line += f" failures={projection.open_failure_count}"
                print(line)

        print("Warnings:")
        if not resume.warnings:
            print("- none")
        else:
            for warning in resume.warnings:
                line = f"- {warning.code}: {warning.message}"
                details = warning.details or {}
                projection_type = details.get("projection_type")
                target_path = details.get("target_path")
                open_failure_count = details.get("open_failure_count")

                if projection_type:
                    line += f" [projection={projection_type}]"
                if target_path:
                    line += f" [path={target_path}]"
                if open_failure_count is not None:
                    line += f" [open_failures={open_failure_count}]"

                print(line)

        print("Closed projection failures:")
        closed_projection_failures = tuple(
            getattr(resume, "closed_projection_failures", ())
        )
        if not closed_projection_failures:
            print("- none")
        else:
            for failure in closed_projection_failures:
                line = (
                    f"- {failure.status}: {failure.projection_type.value} "
                    f"[path={failure.target_path}]"
                )
                if getattr(failure, "attempt_id", None) is not None:
                    line += f" [attempt_id={failure.attempt_id}]"
                if failure.error_code:
                    line += f" [error_code={failure.error_code}]"
                line += f" [message={failure.error_message}]"
                if failure.occurred_at is not None:
                    line += f" [occurred_at={failure.occurred_at.isoformat()}]"
                if failure.resolved_at is not None:
                    line += f" [resolved_at={failure.resolved_at.isoformat()}]"
                line += f" [open_failures={failure.open_failure_count}]"
                line += f" [retry_count={failure.retry_count}]"
                print(line)

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
    if command == "write-resume-projection":
        return _write_resume_projection(args)
    if command == "resume-workflow":
        return _resume_workflow(args)
    if command == "version":
        return _print_version()

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

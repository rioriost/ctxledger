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

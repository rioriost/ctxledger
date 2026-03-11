from __future__ import annotations

import argparse
import sys
from pathlib import Path


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
        choices=("http", "stdio"),
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
        print("0.1.0")
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
        except ImportError as exc:
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
        from uuid import UUID

        from .projection.writer import write_resume_projection

        write_resume_projection(UUID(args.workflow_instance_id))
        print("Resume projection written successfully.")
        return 0
    except Exception as exc:
        print(f"Failed to write resume projection: {exc}", file=sys.stderr)
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
    if command == "version":
        return _print_version()

    parser.error(f"Unknown command: {command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

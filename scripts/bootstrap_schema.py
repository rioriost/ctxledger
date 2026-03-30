#!/usr/bin/env python3
"""
Bootstrap the ctxledger PostgreSQL schema for the Azure large deployment path.

This script is designed for deployment automation, especially after Azure Database
for PostgreSQL Flexible Server has been provisioned and the required extensions
have already been allowlisted and bootstrapped.

Behavior:
1. Waits for PostgreSQL connectivity.
2. Verifies required extensions exist:
   - vector
   - azure_ai
   - age (optional, controlled by flag)
3. Applies the bundled ctxledger schema.
4. Optionally runs post-schema SQL statements.
5. Verifies representative schema objects exist.

The script is intended to be safe to rerun. The bundled schema is expected to be
idempotent enough for deployment-time bootstrap use.

Examples:

    python scripts/bootstrap_schema.py \
      --database-url "postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require"

    CTXLEDGER_DATABASE_URL="postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require" \
    python scripts/bootstrap_schema.py --ensure-age

    python scripts/bootstrap_schema.py \
      --database-url "postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require" \
      --post-sql "SELECT 1;" \
      --post-sql "ANALYZE;"
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_CONNECT_TIMEOUT_SECONDS: Final[int] = 5
DEFAULT_WAIT_TIMEOUT_SECONDS: Final[int] = 300
DEFAULT_WAIT_INTERVAL_SECONDS: Final[int] = 5
DEFAULT_DATABASE_URL: Final[str] = ""
DEFAULT_EXPECTED_TABLES: Final[tuple[str, ...]] = (
    "workspaces",
    "workflow_instances",
    "workflow_attempts",
    "workflow_checkpoints",
    "memory_episodes",
    "memory_items",
)
DEFAULT_EXPECTED_SCHEMAS: Final[tuple[str, ...]] = ("public",)


class BootstrapSchemaError(RuntimeError):
    """Raised when schema bootstrap fails."""


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_schema_path() -> Path:
    return project_root() / "schemas" / "postgres.sql"


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _parse_positive_int(raw: str, *, name: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise BootstrapSchemaError(f"{name} must be an integer") from exc
    if value <= 0:
        raise BootstrapSchemaError(f"{name} must be greater than 0")
    return value


def ensure_connect_timeout(database_url: str, timeout_seconds: int) -> str:
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(timeout_seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def redact_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    netloc = parsed.netloc

    if "@" in netloc:
        credentials, host_part = netloc.rsplit("@", 1)
        if ":" in credentials:
            username, _ = credentials.split(":", 1)
            credentials = f"{username}:<redacted>"
        else:
            credentials = "<redacted>"
        redacted_netloc = f"{credentials}@{host_part}"
    else:
        redacted_netloc = netloc

    return urlunparse(parsed._replace(netloc=redacted_netloc))


def load_sql_file(path: Path) -> str:
    if not path.exists():
        raise BootstrapSchemaError(f"Schema file does not exist: {path}")
    if not path.is_file():
        raise BootstrapSchemaError(f"Schema path is not a file: {path}")

    sql = path.read_text(encoding="utf-8")
    if not sql.strip():
        raise BootstrapSchemaError(f"Schema file is empty: {path}")
    return sql


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bootstrap_schema.py",
        description=(
            "Wait for PostgreSQL readiness, verify expected extensions, and apply "
            "the bundled ctxledger schema."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=_get_env("CTXLEDGER_DATABASE_URL", DEFAULT_DATABASE_URL),
        help=(
            "PostgreSQL connection URL. Defaults to CTXLEDGER_DATABASE_URL. "
            "Must point at the target ctxledger database."
        ),
    )
    parser.add_argument(
        "--schema-path",
        default=str(default_schema_path()),
        help=(f"Path to the SQL schema file to apply. Defaults to {default_schema_path()}."),
    )
    parser.add_argument(
        "--wait-timeout-seconds",
        default=str(DEFAULT_WAIT_TIMEOUT_SECONDS),
        help=(
            "Maximum time to wait for PostgreSQL readiness before failing. "
            f"Default: {DEFAULT_WAIT_TIMEOUT_SECONDS}."
        ),
    )
    parser.add_argument(
        "--wait-interval-seconds",
        default=str(DEFAULT_WAIT_INTERVAL_SECONDS),
        help=(
            "Interval between PostgreSQL readiness checks. "
            f"Default: {DEFAULT_WAIT_INTERVAL_SECONDS}."
        ),
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        default=str(DEFAULT_CONNECT_TIMEOUT_SECONDS),
        help=(f"Per-connection timeout in seconds. Default: {DEFAULT_CONNECT_TIMEOUT_SECONDS}."),
    )
    parser.add_argument(
        "--ensure-age",
        action="store_true",
        help="Require the age extension to exist before applying the schema.",
    )
    parser.add_argument(
        "--skip-extension-checks",
        action="store_true",
        help="Skip verification of required extensions before applying the schema.",
    )
    parser.add_argument(
        "--post-sql",
        action="append",
        default=[],
        help=(
            "Optional SQL statement to execute after applying the main schema. "
            "Can be specified multiple times."
        ),
    )
    parser.add_argument(
        "--skip-verification",
        action="store_true",
        help="Skip representative schema verification after applying the schema.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without connecting or modifying PostgreSQL.",
    )
    return parser


def wait_for_database(
    *,
    database_url: str,
    wait_timeout_seconds: int,
    wait_interval_seconds: int,
) -> None:
    deadline = time.monotonic() + wait_timeout_seconds
    last_error: Exception | None = None

    print(
        f"Waiting for PostgreSQL readiness: timeout={wait_timeout_seconds}s "
        f"interval={wait_interval_seconds}s"
    )

    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise BootstrapSchemaError(
            "psycopg is required to run bootstrap_schema.py. Install project dependencies first."
        ) from exc

    while time.monotonic() < deadline:
        try:
            with psycopg.connect(database_url, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            print("PostgreSQL is reachable.")
            return
        except Exception as exc:  # pragma: no cover - runtime connectivity behavior
            last_error = exc
            print(f"PostgreSQL not ready yet: {exc}")
            time.sleep(wait_interval_seconds)

    raise BootstrapSchemaError(
        f"Timed out waiting for PostgreSQL readiness after {wait_timeout_seconds} seconds. "
        f"Last error: {last_error}"
    )


def verify_extension_exists(conn, extension_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_extension
            WHERE extname = %s
            LIMIT 1
            """,
            (extension_name,),
        )
        row = cur.fetchone()

    if row is None:
        raise BootstrapSchemaError(
            f"Required PostgreSQL extension is missing: {extension_name}. "
            "This should normally be created by the deployment bootstrap phase."
        )


def verify_required_extensions(conn, *, ensure_age: bool) -> None:
    verify_extension_exists(conn, "vector")
    verify_extension_exists(conn, "azure_ai")
    if ensure_age:
        verify_extension_exists(conn, "age")


def apply_schema(conn, sql: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def execute_post_sql(conn, statements: list[str]) -> None:
    if not statements:
        return

    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)
    conn.commit()


def verify_schema_exists(conn, schema_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.schemata
            WHERE schema_name = %s
            LIMIT 1
            """,
            (schema_name,),
        )
        row = cur.fetchone()

    if row is None:
        raise BootstrapSchemaError(f"Expected schema was not found after bootstrap: {schema_name}")


def verify_table_exists(conn, *, schema_name: str, table_name: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
            LIMIT 1
            """,
            (schema_name, table_name),
        )
        row = cur.fetchone()

    if row is None:
        raise BootstrapSchemaError(
            f"Expected table was not found after bootstrap: {schema_name}.{table_name}"
        )


def verify_representative_schema(conn) -> None:
    for schema_name in DEFAULT_EXPECTED_SCHEMAS:
        verify_schema_exists(conn, schema_name)

    for table_name in DEFAULT_EXPECTED_TABLES:
        verify_table_exists(conn, schema_name="public", table_name=table_name)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    database_url = (args.database_url or "").strip()
    if not database_url:
        print(
            "Schema bootstrap failed: Database URL is required. "
            "Set CTXLEDGER_DATABASE_URL or pass --database-url.",
            file=sys.stderr,
        )
        return 1

    try:
        wait_timeout_seconds = _parse_positive_int(
            str(args.wait_timeout_seconds),
            name="--wait-timeout-seconds",
        )
        wait_interval_seconds = _parse_positive_int(
            str(args.wait_interval_seconds),
            name="--wait-interval-seconds",
        )
        connect_timeout_seconds = _parse_positive_int(
            str(args.connect_timeout_seconds),
            name="--connect-timeout-seconds",
        )

        database_url = ensure_connect_timeout(database_url, connect_timeout_seconds)
        schema_path = Path(args.schema_path).expanduser().resolve()
        schema_sql = load_sql_file(schema_path)

        if args.dry_run:
            print("dry_run=true")
            print(f"database_url={redact_database_url(database_url)}")
            print(f"schema_path={schema_path}")
            print(f"schema_sql_bytes={len(schema_sql.encode('utf-8'))}")
            print(f"wait_timeout_seconds={wait_timeout_seconds}")
            print(f"wait_interval_seconds={wait_interval_seconds}")
            print(f"connect_timeout_seconds={connect_timeout_seconds}")
            print(f"ensure_age={bool(args.ensure_age)}")
            print(f"skip_extension_checks={bool(args.skip_extension_checks)}")
            print(f"skip_verification={bool(args.skip_verification)}")
            print(f"post_sql_count={len(args.post_sql)}")
            return 0

        wait_for_database(
            database_url=database_url,
            wait_timeout_seconds=wait_timeout_seconds,
            wait_interval_seconds=wait_interval_seconds,
        )

        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover
            raise BootstrapSchemaError(
                "psycopg is required to run bootstrap_schema.py. Install project dependencies first."
            ) from exc

        with psycopg.connect(database_url) as conn:
            if not args.skip_extension_checks:
                verify_required_extensions(conn, ensure_age=bool(args.ensure_age))
                print("Verified required PostgreSQL extensions.")

            apply_schema(conn, schema_sql)
            print(f"Applied schema from {schema_path}")

            if args.post_sql:
                execute_post_sql(conn, list(args.post_sql))
                print(f"Executed {len(args.post_sql)} post-schema SQL statement(s).")

            if not args.skip_verification:
                verify_representative_schema(conn)
                print("Verified representative ctxledger schema objects.")

        print("Schema bootstrap completed successfully.")
        return 0

    except BootstrapSchemaError as exc:
        print(f"Schema bootstrap failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected schema bootstrap failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

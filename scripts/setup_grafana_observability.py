#!/usr/bin/env python3
"""
Initialize Grafana observability database objects idempotently.

This helper is intended for the default local ctxledger stack, where Grafana is
enabled by default and should be able to read operator-facing observability
views without requiring a manual SQL session each time a fresh database is
created.

What this script does:

1. Applies `docs/sql/observability_views.sql`
2. Ensures the Grafana read-only role exists
3. Ensures the role password is set to the configured value
4. Grants database/schema/table/default privileges needed for Grafana reads
5. Revokes broad access from the `public` schema for that role

The script is designed to be safe to run repeatedly.

Example usage:

    python scripts/setup_grafana_observability.py

    CTXLEDGER_DATABASE_URL=postgresql://ctxledger:ctxledger@localhost:5432/ctxledger \
    CTXLEDGER_GRAFANA_POSTGRES_PASSWORD=replace-with-a-strong-secret \
    python scripts/setup_grafana_observability.py
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit

import psycopg

DEFAULT_DATABASE_URL: Final[str] = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
DEFAULT_GRAFANA_ROLE: Final[str] = "ctxledger_grafana"
DEFAULT_OBSERVABILITY_SQL_PATH: Final[Path] = Path("docs/sql/observability_views.sql")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Apply observability SQL views and ensure the Grafana read-only "
            "database role exists with the required privileges."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CTXLEDGER_DATABASE_URL", DEFAULT_DATABASE_URL),
        help=(
            "PostgreSQL connection URL used for setup "
            f"(default: CTXLEDGER_DATABASE_URL or {DEFAULT_DATABASE_URL})"
        ),
    )
    parser.add_argument(
        "--grafana-role",
        default=os.environ.get("CTXLEDGER_GRAFANA_POSTGRES_USER", DEFAULT_GRAFANA_ROLE),
        help=(
            "Grafana read-only PostgreSQL role name "
            f"(default: CTXLEDGER_GRAFANA_POSTGRES_USER or {DEFAULT_GRAFANA_ROLE})"
        ),
    )
    parser.add_argument(
        "--grafana-password",
        default=os.environ.get("CTXLEDGER_GRAFANA_POSTGRES_PASSWORD"),
        help=(
            "Grafana read-only PostgreSQL role password "
            "(default: CTXLEDGER_GRAFANA_POSTGRES_PASSWORD)"
        ),
    )
    parser.add_argument(
        "--observability-sql-path",
        default=str(DEFAULT_OBSERVABILITY_SQL_PATH),
        help=(f"Path to the observability SQL file (default: {DEFAULT_OBSERVABILITY_SQL_PATH})"),
    )
    return parser.parse_args()


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def single_quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def derive_database_name(database_url: str) -> str:
    path = urlsplit(database_url).path.lstrip("/")
    if not path:
        raise ValueError("database URL must include a database name")
    return path.split("/", 1)[0]


def read_sql_file(path_str: str) -> str:
    path = Path(path_str)
    if not path.exists():
        raise FileNotFoundError(f"observability SQL file not found: {path}")
    return path.read_text(encoding="utf-8")


def apply_observability_views(conn: psycopg.Connection, sql_text: str) -> None:
    with conn.cursor() as cur:
        cur.execute(sql_text)


def ensure_role_exists(conn: psycopg.Connection, role_name: str) -> None:
    role_literal = single_quote_literal(role_name)
    role_ident = quote_ident(role_name)

    sql = f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_roles
        WHERE rolname = {role_literal}
    ) THEN
        EXECUTE 'CREATE ROLE {role_ident} LOGIN';
    END IF;
END
$$;
"""
    with conn.cursor() as cur:
        cur.execute(sql)


def ensure_role_password(conn: psycopg.Connection, role_name: str, password: str | None) -> None:
    if not password:
        return

    role_ident = quote_ident(role_name)
    password_literal = single_quote_literal(password)

    sql = f"ALTER ROLE {role_ident} PASSWORD {password_literal};"
    with conn.cursor() as cur:
        cur.execute(sql)


def grant_grafana_privileges(conn: psycopg.Connection, database_name: str, role_name: str) -> None:
    database_ident = quote_ident(database_name)
    role_ident = quote_ident(role_name)

    statements = [
        f"GRANT CONNECT ON DATABASE {database_ident} TO {role_ident};",
        f"GRANT USAGE ON SCHEMA observability TO {role_ident};",
        f"GRANT SELECT ON ALL TABLES IN SCHEMA observability TO {role_ident};",
        (
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA observability "
            f"GRANT SELECT ON TABLES TO {role_ident};"
        ),
        f"REVOKE ALL ON SCHEMA public FROM {role_ident};",
        f"REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {role_ident};",
        f"REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {role_ident};",
        f"REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM {role_ident};",
    ]

    with conn.cursor() as cur:
        for statement in statements:
            cur.execute(statement)


def main() -> int:
    args = parse_args()

    if not args.grafana_password:
        print(
            "error: missing Grafana PostgreSQL password. "
            "Set CTXLEDGER_GRAFANA_POSTGRES_PASSWORD or pass --grafana-password.",
            file=sys.stderr,
        )
        return 2

    try:
        database_name = derive_database_name(args.database_url)
        observability_sql = read_sql_file(args.observability_sql_path)

        with psycopg.connect(args.database_url, autocommit=True) as conn:
            apply_observability_views(conn, observability_sql)
            ensure_role_exists(conn, args.grafana_role)
            ensure_role_password(conn, args.grafana_role, args.grafana_password)
            grant_grafana_privileges(conn, database_name, args.grafana_role)

        print("Grafana observability setup completed.")
        print(f"- database: {database_name}")
        print(f"- role: {args.grafana_role}")
        print(f"- observability SQL: {args.observability_sql_path}")
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

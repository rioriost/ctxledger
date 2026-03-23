#!/usr/bin/env python3
"""
Ensure the Apache AGE extension exists in the target PostgreSQL database.

This helper is intended for the local ctxledger startup path, where the
repository-owned PostgreSQL image already contains the AGE binaries but the
database may still need `CREATE EXTENSION age` to be run before graph bootstrap.

The script is designed to be safe to run repeatedly.

Example usage:

    python scripts/ensure_age_extension.py

    CTXLEDGER_DATABASE_URL=postgresql://ctxledger:ctxledger@localhost:55432/ctxledger \
    python scripts/ensure_age_extension.py

    python scripts/ensure_age_extension.py \
        --database-url postgresql://ctxledger:ctxledger@localhost:55432/ctxledger
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Final

import psycopg

DEFAULT_DATABASE_URL: Final[str] = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Ensure the Apache AGE extension exists in the configured PostgreSQL database."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CTXLEDGER_DATABASE_URL", DEFAULT_DATABASE_URL),
        help=(
            f"PostgreSQL connection URL (default: CTXLEDGER_DATABASE_URL or {DEFAULT_DATABASE_URL})"
        ),
    )
    return parser.parse_args()


def extension_exists(conn: psycopg.Connection) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_extension
            WHERE extname = 'age'
            LIMIT 1
            """
        )
        return cur.fetchone() is not None


def ensure_age_extension(conn: psycopg.Connection) -> bool:
    already_exists = extension_exists(conn)

    with conn.cursor() as cur:
        cur.execute("CREATE EXTENSION IF NOT EXISTS age")

    return not already_exists


def main() -> int:
    args = parse_args()

    try:
        with psycopg.connect(args.database_url, autocommit=True) as conn:
            created = ensure_age_extension(conn)

        if created:
            print("AGE extension created successfully.")
        else:
            print("AGE extension already exists.")

        return 0
    except Exception as exc:
        print(f"Failed to ensure AGE extension: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

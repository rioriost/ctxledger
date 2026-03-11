from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

DEFAULT_DATABASE_URL = "postgresql://ctxledger:ctxledger@localhost:5432/ctxledger"
CONNECT_TIMEOUT_SECONDS = 5


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def schema_path() -> Path:
    return project_root() / "schemas" / "postgres.sql"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="apply_schema.py",
        description="Apply the bundled ctxledger PostgreSQL schema.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("CTXLEDGER_DATABASE_URL", DEFAULT_DATABASE_URL),
        help=(
            "PostgreSQL connection URL. "
            "Defaults to CTXLEDGER_DATABASE_URL or local ctxledger database."
        ),
    )
    parser.add_argument(
        "--schema-path",
        default=str(schema_path()),
        help="Path to the SQL schema file to apply.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate inputs and print what would be applied without executing SQL.",
    )
    return parser


def ensure_connect_timeout(database_url: str, timeout_seconds: int) -> str:
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(timeout_seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def load_schema(schema_file: Path) -> str:
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file does not exist: {schema_file}")
    if not schema_file.is_file():
        raise FileNotFoundError(f"Schema path is not a file: {schema_file}")

    sql = schema_file.read_text(encoding="utf-8")
    if not sql.strip():
        raise ValueError(f"Schema file is empty: {schema_file}")
    return sql


def apply_schema(database_url: str, sql: str) -> None:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "psycopg is required to apply the PostgreSQL schema. "
            "Install dependencies first."
        ) from exc

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        connection.commit()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    schema_file = Path(args.schema_path).expanduser().resolve()

    try:
        sql = load_schema(schema_file)
        database_url = ensure_connect_timeout(
            args.database_url,
            CONNECT_TIMEOUT_SECONDS,
        )

        if args.dry_run:
            print(f"schema_path={schema_file}")
            print("database_url=<redacted>")
            print(f"sql_bytes={len(sql.encode('utf-8'))}")
            print("dry_run=true")
            return 0

        apply_schema(database_url, sql)
        print(f"Applied schema from {schema_file}")
        return 0
    except Exception as exc:
        print(f"Failed to apply schema: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

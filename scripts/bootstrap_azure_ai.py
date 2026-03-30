#!/usr/bin/env python3
"""
Bootstrap PostgreSQL azure_ai / Azure OpenAI settings for the ctxledger Azure large deployment.

This script is intended to be used after Azure Database for PostgreSQL Flexible
Server has been provisioned and extension allowlisting has been configured.

Design posture:
- This bootstrap path is for persistence-oriented AI work.
- It prepares PostgreSQL to call Azure OpenAI through the azure_ai extension.
- It is appropriate for patterns such as:
  - generating embeddings for stored records
  - storing AI-derived results in tables or columns
  - validating PostgreSQL-side materialization paths
- It is not the right path for interactive AI responses that should be returned
  directly to an MCP client without first being stored.

Behavior:
1. Waits for PostgreSQL connectivity.
2. Ensures required extensions exist:
   - azure_ai
   - vector
   - age (optional, controlled by flag)
3. Configures azure_ai settings for Azure OpenAI according to the selected auth mode:
   - auto
   - subscription_key
   - managed_identity
4. Verifies the written settings.
5. Optionally validates the embedding deployment by calling
   azure_openai.create_embeddings(...).

The script is safe to rerun.

Examples:

    python scripts/bootstrap_azure_ai.py \
      --database-url \
        "postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require" \
      --azure-openai-endpoint \
        "https://example.openai.azure.com" \
      --azure-openai-auth-mode auto \
      --azure-openai-subscription-key "replace-me" \
      --embedding-deployment "embeddings" \
      --embedding-dimensions 1536 \
      --validate-embeddings

    python scripts/bootstrap_azure_ai.py \
      --database-url \
        "postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require" \
      --azure-openai-endpoint \
        "https://example.openai.azure.com" \
      --azure-openai-auth-mode managed_identity \
      --embedding-deployment "embeddings" \
      --validate-embeddings

    CTXLEDGER_DATABASE_URL=\
"postgresql://user:pass@server.postgres.database.azure.com:5432/ctxledger?sslmode=require" \
    CTXLEDGER_AZURE_OPENAI_ENDPOINT=\
"https://example.openai.azure.com" \
    CTXLEDGER_AZURE_OPENAI_AUTH_MODE="managed_identity" \
    CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT="embeddings" \
    python scripts/bootstrap_azure_ai.py --validate-embeddings
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    import psycopg
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "psycopg is required to run bootstrap_azure_ai.py. Install project dependencies first."
    ) from exc

DEFAULT_CONNECT_TIMEOUT_SECONDS: Final[int] = 5
DEFAULT_WAIT_TIMEOUT_SECONDS: Final[int] = 300
DEFAULT_WAIT_INTERVAL_SECONDS: Final[int] = 5
DEFAULT_EMBEDDING_TEST_INPUT: Final[str] = "ctxledger azure ai bootstrap validation"


class BootstrapError(RuntimeError):
    """Raised when bootstrap validation or execution fails."""


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    database_url: str
    azure_openai_endpoint: str
    azure_openai_auth_mode: str
    azure_openai_subscription_key: str | None
    embedding_deployment: str
    embedding_dimensions: int | None
    wait_timeout_seconds: int
    wait_interval_seconds: int
    connect_timeout_seconds: int
    validate_embeddings: bool
    validation_input: str
    ensure_age: bool
    dry_run: bool

    @property
    def resolved_auth_mode(self) -> str:
        if self.azure_openai_auth_mode == "auto":
            return (
                "managed_identity"
                if self.azure_openai_subscription_key is None
                else "subscription_key"
            )
        return self.azure_openai_auth_mode


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
        raise BootstrapError(f"{name} must be an integer") from exc
    if value <= 0:
        raise BootstrapError(f"{name} must be greater than 0")
    return value


def _parse_optional_positive_int(raw: str | None, *, name: str) -> int | None:
    if raw is None or not raw.strip():
        return None
    return _parse_positive_int(raw, name=name)


def ensure_connect_timeout(database_url: str, timeout_seconds: int) -> str:
    parsed = urlparse(database_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("connect_timeout", str(timeout_seconds))
    return urlunparse(parsed._replace(query=urlencode(query)))


def normalize_endpoint(endpoint: str) -> str:
    cleaned = endpoint.strip().rstrip("/")
    parsed = urlparse(cleaned)
    if parsed.scheme != "https" or not parsed.netloc:
        raise BootstrapError(
            "Azure OpenAI endpoint must be a valid absolute HTTPS URL, "
            "for example: https://example.openai.azure.com"
        )
    return cleaned


def normalize_auth_mode(auth_mode: str) -> str:
    normalized = auth_mode.strip().lower().replace("-", "_")
    if normalized not in {"auto", "subscription_key", "managed_identity"}:
        raise BootstrapError(
            "--azure-openai-auth-mode must be one of "
            "'auto', 'subscription_key', or 'managed_identity'"
        )
    return normalized


def redact_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    netloc = parsed.netloc

    if "@" in netloc:
        credentials, host_part = netloc.rsplit("@", 1)
        if ":" in credentials:
            username, _ = credentials.split(":", 1)
            redacted_credentials = f"{username}:<redacted>"
        else:
            redacted_credentials = "<redacted>"
        redacted_netloc = f"{redacted_credentials}@{host_part}"
    else:
        redacted_netloc = netloc

    return urlunparse(parsed._replace(netloc=redacted_netloc))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bootstrap_azure_ai.py",
        description=(
            "Wait for Azure Database for PostgreSQL connectivity, enable required "
            "extensions, and configure azure_ai for Azure OpenAI."
        ),
    )
    parser.add_argument(
        "--database-url",
        default=_get_env("CTXLEDGER_DATABASE_URL"),
        help="PostgreSQL connection URL. Defaults to CTXLEDGER_DATABASE_URL.",
    )
    parser.add_argument(
        "--azure-openai-endpoint",
        default=_get_env("CTXLEDGER_AZURE_OPENAI_ENDPOINT"),
        help="Azure OpenAI endpoint. Defaults to CTXLEDGER_AZURE_OPENAI_ENDPOINT.",
    )
    parser.add_argument(
        "--azure-openai-auth-mode",
        default=_get_env("CTXLEDGER_AZURE_OPENAI_AUTH_MODE", "auto"),
        help=(
            "Azure OpenAI authentication mode. Supported values: "
            "auto, subscription_key, managed_identity. Defaults to "
            "CTXLEDGER_AZURE_OPENAI_AUTH_MODE or auto."
        ),
    )
    parser.add_argument(
        "--azure-openai-subscription-key",
        default=_get_env("CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY"),
        help=(
            "Azure OpenAI subscription key. Required when "
            "--azure-openai-auth-mode=subscription_key. Defaults to "
            "CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY."
        ),
    )
    parser.add_argument(
        "--embedding-deployment",
        default=_get_env("CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        help=(
            "Azure OpenAI embedding deployment name. Defaults to "
            "CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT."
        ),
    )
    parser.add_argument(
        "--embedding-dimensions",
        default=_get_env("CTXLEDGER_EMBEDDING_DIMENSIONS"),
        help=(
            "Optional expected embedding dimensions for validation. Defaults to "
            "CTXLEDGER_EMBEDDING_DIMENSIONS if set."
        ),
    )
    parser.add_argument(
        "--wait-timeout-seconds",
        default=str(DEFAULT_WAIT_TIMEOUT_SECONDS),
        help=(
            "Maximum time to wait for PostgreSQL readiness. "
            f"Default: {DEFAULT_WAIT_TIMEOUT_SECONDS}."
        ),
    )
    parser.add_argument(
        "--wait-interval-seconds",
        default=str(DEFAULT_WAIT_INTERVAL_SECONDS),
        help=(
            "Wait interval between PostgreSQL readiness checks. "
            f"Default: {DEFAULT_WAIT_INTERVAL_SECONDS}."
        ),
    )
    parser.add_argument(
        "--connect-timeout-seconds",
        default=str(DEFAULT_CONNECT_TIMEOUT_SECONDS),
        help=(f"PostgreSQL connect timeout. Default: {DEFAULT_CONNECT_TIMEOUT_SECONDS}."),
    )
    parser.add_argument(
        "--validate-embeddings",
        action="store_true",
        help=(
            "After configuring azure_ai, call azure_openai.create_embeddings(...) "
            "to validate the selected deployment."
        ),
    )
    parser.add_argument(
        "--validation-input",
        default=DEFAULT_EMBEDDING_TEST_INPUT,
        help=(
            "Text used when --validate-embeddings is enabled. "
            f"Default: {DEFAULT_EMBEDDING_TEST_INPUT!r}."
        ),
    )
    parser.add_argument(
        "--skip-age",
        action="store_true",
        help="Do not attempt to ensure the age extension exists.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended actions without modifying PostgreSQL.",
    )
    return parser


def load_config(args: argparse.Namespace) -> BootstrapConfig:
    database_url = (args.database_url or "").strip()
    if not database_url:
        raise BootstrapError(
            "Database URL is required. Set CTXLEDGER_DATABASE_URL or pass --database-url."
        )

    azure_openai_endpoint = normalize_endpoint(args.azure_openai_endpoint or "")
    azure_openai_auth_mode = normalize_auth_mode(args.azure_openai_auth_mode or "")
    azure_openai_subscription_key = (args.azure_openai_subscription_key or "").strip() or None

    if azure_openai_auth_mode == "subscription_key" and not azure_openai_subscription_key:
        raise BootstrapError(
            "Azure OpenAI subscription key is required when "
            "--azure-openai-auth-mode=subscription_key. Set "
            "CTXLEDGER_AZURE_OPENAI_SUBSCRIPTION_KEY or pass "
            "--azure-openai-subscription-key."
        )

    if azure_openai_auth_mode == "managed_identity" and azure_openai_subscription_key:
        raise BootstrapError(
            "Azure OpenAI subscription key must not be provided when "
            "--azure-openai-auth-mode=managed_identity."
        )

    embedding_deployment = (args.embedding_deployment or "").strip()
    if not embedding_deployment:
        raise BootstrapError(
            "Embedding deployment is required. Set "
            "CTXLEDGER_AZURE_OPENAI_EMBEDDING_DEPLOYMENT or pass "
            "--embedding-deployment."
        )

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
    embedding_dimensions = _parse_optional_positive_int(
        args.embedding_dimensions,
        name="--embedding-dimensions",
    )

    validation_input = (args.validation_input or "").strip()
    if args.validate_embeddings and not validation_input:
        raise BootstrapError("--validation-input must not be empty when validation is enabled")

    return BootstrapConfig(
        database_url=ensure_connect_timeout(database_url, connect_timeout_seconds),
        azure_openai_endpoint=azure_openai_endpoint,
        azure_openai_auth_mode=azure_openai_auth_mode,
        azure_openai_subscription_key=azure_openai_subscription_key,
        embedding_deployment=embedding_deployment,
        embedding_dimensions=embedding_dimensions,
        wait_timeout_seconds=wait_timeout_seconds,
        wait_interval_seconds=wait_interval_seconds,
        connect_timeout_seconds=connect_timeout_seconds,
        validate_embeddings=bool(args.validate_embeddings),
        validation_input=validation_input or DEFAULT_EMBEDDING_TEST_INPUT,
        ensure_age=not bool(args.skip_age),
        dry_run=bool(args.dry_run),
    )


def wait_for_database(config: BootstrapConfig) -> None:
    deadline = time.monotonic() + config.wait_timeout_seconds
    last_error: Exception | None = None

    print(
        f"Waiting for PostgreSQL readiness: timeout={config.wait_timeout_seconds}s "
        f"interval={config.wait_interval_seconds}s"
    )

    while time.monotonic() < deadline:
        try:
            with psycopg.connect(config.database_url, autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            print("PostgreSQL is reachable.")
            return
        except Exception as exc:  # pragma: no cover - runtime connectivity behavior
            last_error = exc
            print(f"PostgreSQL not ready yet: {exc}")
            time.sleep(config.wait_interval_seconds)

    raise BootstrapError(
        f"Timed out waiting for PostgreSQL readiness after "
        f"{config.wait_timeout_seconds} seconds. Last error: {last_error}"
    )


def extension_exists(conn: psycopg.Connection, name: str) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT 1
            FROM pg_extension
            WHERE extname = %s
            LIMIT 1
            """,
            (name,),
        )
        return cur.fetchone() is not None


def ensure_extension(conn: psycopg.Connection, name: str) -> bool:
    already_exists = extension_exists(conn, name)
    with conn.cursor() as cur:
        if name == "vector":
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
        else:
            cur.execute(f"CREATE EXTENSION IF NOT EXISTS {name}")
    return not already_exists


def print_execution_boundary_note() -> None:
    print("Bootstrap scope: PostgreSQL-side persistence/materialization path for azure_ai.")
    print(
        "Interactive AI responses that should be returned directly to MCP "
        "clients should use an application-side path instead of this bootstrap."
    )


def set_azure_ai_setting(conn: psycopg.Connection, key: str, value: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT azure_ai.set_setting(%s, %s)",
            (key, value),
        )
        cur.fetchone()


def get_azure_ai_setting(conn: psycopg.Connection, key: str) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT azure_ai.get_setting(%s)",
            (key,),
        )
        row = cur.fetchone()
    if row is None or row[0] is None:
        raise BootstrapError(f"azure_ai setting {key!r} was not returned")
    return str(row[0])


def configure_azure_openai_auth(conn: psycopg.Connection, config: BootstrapConfig) -> None:
    auth_mode = config.resolved_auth_mode

    if config.azure_openai_auth_mode == "auto":
        print(
            "Azure OpenAI auth mode auto-selected:",
            auth_mode,
        )

    if auth_mode == "managed_identity":
        set_azure_ai_setting(conn, "azure_openai.auth_type", "managed-identity")
        set_azure_ai_setting(conn, "azure_openai.endpoint", config.azure_openai_endpoint)

        stored_auth_type = get_azure_ai_setting(conn, "azure_openai.auth_type")
        stored_endpoint = get_azure_ai_setting(conn, "azure_openai.endpoint")

        if stored_auth_type != "managed-identity":
            raise BootstrapError(
                "azure_ai auth_type verification failed after write. "
                f"Expected 'managed-identity', got {stored_auth_type!r}."
            )

        if stored_endpoint != config.azure_openai_endpoint:
            raise BootstrapError(
                "azure_ai endpoint verification failed after write. "
                f"Expected {config.azure_openai_endpoint!r}, got {stored_endpoint!r}."
            )

        print("Configured azure_ai setting: azure_openai.auth_type=managed-identity")
        print("Configured azure_ai setting: azure_openai.endpoint")
        return

    if auth_mode == "subscription_key":
        if not config.azure_openai_subscription_key:
            raise BootstrapError(
                "Azure OpenAI subscription key is required for subscription_key auth mode."
            )

        set_azure_ai_setting(conn, "azure_openai.auth_type", "subscription-key")
        set_azure_ai_setting(conn, "azure_openai.endpoint", config.azure_openai_endpoint)
        set_azure_ai_setting(
            conn,
            "azure_openai.subscription_key",
            config.azure_openai_subscription_key,
        )

        stored_auth_type = get_azure_ai_setting(conn, "azure_openai.auth_type")
        stored_endpoint = get_azure_ai_setting(conn, "azure_openai.endpoint")
        stored_key = get_azure_ai_setting(conn, "azure_openai.subscription_key")

        if stored_auth_type != "subscription-key":
            raise BootstrapError(
                "azure_ai auth_type verification failed after write. "
                f"Expected 'subscription-key', got {stored_auth_type!r}."
            )

        if stored_endpoint != config.azure_openai_endpoint:
            raise BootstrapError(
                "azure_ai endpoint verification failed after write. "
                f"Expected {config.azure_openai_endpoint!r}, got {stored_endpoint!r}."
            )

        if stored_key != config.azure_openai_subscription_key:
            raise BootstrapError("azure_ai subscription key verification failed after write.")

        print("Configured azure_ai setting: azure_openai.auth_type=subscription-key")
        print("Configured azure_ai setting: azure_openai.endpoint")
        print("Configured azure_ai setting: azure_openai.subscription_key")
        return

    raise BootstrapError(f"Unsupported Azure OpenAI auth mode: {config.azure_openai_auth_mode!r}")


def validate_embedding_call(conn: psycopg.Connection, config: BootstrapConfig) -> int:
    if config.embedding_dimensions is None:
        sql = """
            SELECT array_length(
                azure_openai.create_embeddings(%s, %s),
                1
            )
        """
        params = (config.embedding_deployment, config.validation_input)
    else:
        sql = """
            SELECT array_length(
                azure_openai.create_embeddings(
                    %s,
                    %s,
                    dimensions => %s
                ),
                1
            )
        """
        params = (
            config.embedding_deployment,
            config.validation_input,
            config.embedding_dimensions,
        )

    with conn.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()

    if row is None or row[0] is None:
        raise BootstrapError("azure_openai.create_embeddings(...) returned no embedding length")

    dimension_count = int(row[0])

    if config.embedding_dimensions is not None and dimension_count != config.embedding_dimensions:
        raise BootstrapError(
            "Embedding validation succeeded but returned an unexpected dimension count: "
            f"expected {config.embedding_dimensions}, got {dimension_count}"
        )

    return dimension_count


def run_bootstrap(config: BootstrapConfig) -> None:
    if config.dry_run:
        print("dry_run=true")
        print_execution_boundary_note()
        print(f"database_url={redact_database_url(config.database_url)}")
        print(f"azure_openai_endpoint={config.azure_openai_endpoint}")
        print(f"azure_openai_auth_mode={config.azure_openai_auth_mode}")
        print(f"resolved_azure_openai_auth_mode={config.resolved_auth_mode}")
        print(f"embedding_deployment={config.embedding_deployment}")
        print(f"embedding_dimensions={config.embedding_dimensions}")
        print(f"ensure_age={config.ensure_age}")
        print(f"validate_embeddings={config.validate_embeddings}")
        print("would_wait_for_database=true")
        print("would_ensure_extensions=azure_ai,vector" + (",age" if config.ensure_age else ""))
        if config.resolved_auth_mode == "managed_identity":
            print("would_set_azure_ai_settings=azure_openai.auth_type,azure_openai.endpoint")
        else:
            print(
                "would_set_azure_ai_settings="
                "azure_openai.auth_type,azure_openai.endpoint,"
                "azure_openai.subscription_key"
            )
        if config.validate_embeddings:
            print("would_validate_embeddings=true")
        return

    print_execution_boundary_note()
    wait_for_database(config)

    with psycopg.connect(config.database_url, autocommit=True) as conn:
        created_azure_ai = ensure_extension(conn, "azure_ai")
        created_vector = ensure_extension(conn, "vector")

        if created_azure_ai:
            print("Created extension: azure_ai")
        else:
            print("Extension already exists: azure_ai")

        if created_vector:
            print("Created extension: vector")
        else:
            print("Extension already exists: vector")

        if config.ensure_age:
            created_age = ensure_extension(conn, "age")
            if created_age:
                print("Created extension: age")
            else:
                print("Extension already exists: age")

        configure_azure_openai_auth(conn, config)

        if config.validate_embeddings:
            dimension_count = validate_embedding_call(conn, config)
            print(
                "Validated azure_openai.create_embeddings(...): "
                f"deployment={config.embedding_deployment} dimensions={dimension_count}"
            )

    print("Azure AI bootstrap completed successfully.")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args)
        run_bootstrap(config)
        return 0
    except BootstrapError as exc:
        print(f"Azure AI bootstrap failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected bootstrap failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

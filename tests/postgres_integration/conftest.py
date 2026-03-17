from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest

from ctxledger.db.postgres import (
    PostgresConfig,
    build_connection_pool,
    build_postgres_uow_factory,
)
from ctxledger.workflow.service import WorkflowService

DOCKER_COMPOSE_FILE = (
    Path(__file__).resolve().parents[2] / "docker" / "docker-compose.yml"
)
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE_URL = "postgresql://ctxledger:ctxledger@localhost:55432/ctxledger"
POSTGRES_SERVICE_NAME = "postgres"
POSTGRES_CONTAINER_NAME = "ctxledger-postgres"
TEST_SCHEMA_PREFIX = "ctxledger_test_"


def _docker_compose_cmd(*args: str) -> list[str]:
    return [
        "docker",
        "compose",
        "-f",
        str(DOCKER_COMPOSE_FILE),
        *args,
    ]


def _run_command(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [*args],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=check,
    )


def _run_compose(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run_command(*_docker_compose_cmd(*args), check=check)


def _is_docker_available() -> bool:
    try:
        completed = _run_command("docker", "--version", check=False)
    except OSError:
        return False
    return completed.returncode == 0


def _wait_for_postgres_ready(timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_compose("ps", "--format", "json", check=False)
        if last_result.returncode == 0 and "healthy" in last_result.stdout.lower():
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL container did not become healthy in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _run_psql(sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            POSTGRES_CONTAINER_NAME,
            "psql",
            "-U",
            "ctxledger",
            "-d",
            "ctxledger",
            "-v",
            "ON_ERROR_STOP=1",
        ],
        cwd=PROJECT_ROOT,
        text=True,
        input=sql,
        capture_output=True,
        check=False,
    )


def _wait_for_database_accepting_connections(timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_psql("SELECT 1;")
        if last_result.returncode == 0:
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL did not start accepting connections in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _apply_schema(schema_name: str) -> None:
    schema_path = PROJECT_ROOT / "schemas" / "postgres.sql"
    quoted_schema_name = _quote_ident(schema_name)
    schema_sql = schema_path.read_text(encoding="utf-8")
    schema_sql = schema_sql.replace(
        "CREATE OR REPLACE FUNCTION set_updated_at()",
        f"CREATE OR REPLACE FUNCTION {quoted_schema_name}.set_updated_at()",
    )
    schema_sql = schema_sql.replace(
        "EXECUTE FUNCTION set_updated_at();",
        f"EXECUTE FUNCTION {quoted_schema_name}.set_updated_at();",
    )
    completed = _run_psql(
        f"""
        CREATE SCHEMA IF NOT EXISTS {quoted_schema_name};
        SET search_path TO {quoted_schema_name}, public;
        {schema_sql}
        """
    )
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to apply PostgreSQL schema.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


def _wait_for_schema_ready(schema_name: str, timeout_seconds: float = 60.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    sql = f"""
    SELECT EXISTS (
      SELECT 1
      FROM information_schema.tables
      WHERE table_schema = '{schema_name}'
        AND table_name = 'workspaces'
    );
    """
    last_result: subprocess.CompletedProcess[str] | None = None

    while time.monotonic() < deadline:
        last_result = _run_psql(sql)
        if last_result.returncode == 0 and "t" in last_result.stdout.lower():
            return
        time.sleep(1.0)

    logs = _run_compose("logs", POSTGRES_SERVICE_NAME, check=False)
    stdout = "" if last_result is None else last_result.stdout
    stderr = "" if last_result is None else last_result.stderr
    raise AssertionError(
        "PostgreSQL schema did not become ready in time.\n"
        f"stdout:\n{stdout}\n"
        f"stderr:\n{stderr}\n"
        f"logs:\n{logs.stdout}\n{logs.stderr}"
    )


def _ensure_schema_ready(schema_name: str) -> None:
    _wait_for_database_accepting_connections()
    _apply_schema(schema_name)
    _wait_for_schema_ready(schema_name)


def _drop_schema(schema_name: str) -> None:
    quoted_schema_name = _quote_ident(schema_name)
    completed = _run_psql(f"DROP SCHEMA IF EXISTS {quoted_schema_name} CASCADE;")
    if completed.returncode != 0:
        raise AssertionError(
            "Failed to drop PostgreSQL test schema.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )


@pytest.fixture(scope="session")
def postgres_integration_environment() -> Iterator[None]:
    if not _is_docker_available():
        pytest.skip("Docker is required for PostgreSQL integration tests")

    try:
        import psycopg  # noqa: F401
    except ImportError:
        pytest.skip("psycopg is required for PostgreSQL integration tests")

    up_result = _run_compose("up", "-d", POSTGRES_SERVICE_NAME, check=False)
    if up_result.returncode != 0:
        pytest.skip(
            "Could not start PostgreSQL container for integration tests.\n"
            f"{up_result.stdout}\n{up_result.stderr}"
        )

    _wait_for_postgres_ready()
    yield


@pytest.fixture
def postgres_test_schema(
    postgres_integration_environment: None,
) -> Iterator[str]:
    schema_name = f"{TEST_SCHEMA_PREFIX}{uuid4().hex}"
    _ensure_schema_ready(schema_name)
    try:
        yield schema_name
    finally:
        _drop_schema(schema_name)


@pytest.fixture
def postgres_database_url(postgres_integration_environment: None) -> str:
    return os.getenv("CTXLEDGER_TEST_DATABASE_URL", DEFAULT_DATABASE_URL)


@pytest.fixture
def openai_test_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is required for real OpenAI integration tests")
    return api_key


@pytest.fixture
def openai_test_model() -> str:
    return os.getenv("OPENAI_MODEL", "text-embedding-3-small")


@pytest.fixture
def openai_test_base_url() -> str:
    return os.getenv(
        "OPENAI_BASE_URL",
        "https://api.openai.com/v1/embeddings",
    )


@pytest.fixture
def clean_postgres_database(
    postgres_test_schema: str,
) -> Iterator[str]:
    yield postgres_test_schema


@pytest.fixture
def postgres_pooled_uow_factory(
    postgres_database_url: str,
    clean_postgres_database: str,
) -> Iterator:
    config = PostgresConfig(
        database_url=postgres_database_url,
        connect_timeout_seconds=5,
        statement_timeout_ms=5000,
        schema_name=clean_postgres_database,
    )
    connection_pool = build_connection_pool(config)
    try:
        yield build_postgres_uow_factory(config, connection_pool)
    finally:
        connection_pool.close()


@pytest.fixture
def postgres_workflow_service(
    postgres_pooled_uow_factory,
) -> WorkflowService:
    return WorkflowService(postgres_pooled_uow_factory)

from __future__ import annotations

from typing import Any, Protocol
from urllib.parse import parse_qs, urlparse


class DatabaseHealthChecker(Protocol):
    def ping(self) -> None: ...
    def schema_ready(self) -> bool: ...


from .errors import ServerBootstrapError


class DefaultDatabaseHealthChecker:
    """
    Lightweight placeholder health checker.

    This implementation intentionally avoids a hard dependency on a specific
    PostgreSQL driver in the initial runtime bootstrap. It validates that a DB
    URL is configured and treats schema readiness as a deploy-time guarantee.

    When a PostgreSQL driver is available, use `build_database_health_checker()`
    to get a real health checker instead of instantiating this class directly.
    """

    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    def ping(self) -> None:
        if not self._database_url:
            raise ServerBootstrapError("database_url is not configured")

    def schema_ready(self) -> bool:
        return bool(self._database_url)


class PostgresDatabaseHealthChecker:
    def __init__(self, database_url: str | None) -> None:
        self._database_url = database_url

    def _connect_timeout_seconds(self) -> int:
        if not self._database_url:
            return 5

        parsed = urlparse(self._database_url)
        query = parse_qs(parsed.query)
        raw_timeout = query.get("connect_timeout", [None])[0]
        if raw_timeout is None:
            return 5

        try:
            timeout = int(raw_timeout)
        except ValueError:
            return 5

        return timeout if timeout > 0 else 5

    def _connect(self) -> Any:
        if not self._database_url:
            raise ServerBootstrapError("database_url is not configured")

        try:
            import psycopg
        except ImportError as exc:
            raise ServerBootstrapError(
                "PostgreSQL health checker requires psycopg to be installed"
            ) from exc

        return psycopg.connect(
            self._database_url,
            connect_timeout=self._connect_timeout_seconds(),
        )

    def ping(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def schema_ready(self) -> bool:
        required_tables = (
            "workspaces",
            "workflow_instances",
            "workflow_attempts",
            "workflow_checkpoints",
            "verify_reports",
            "projection_states",
        )

        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name = %s
        )
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                for table_name in required_tables:
                    cursor.execute(query, (table_name,))
                    row = cursor.fetchone()
                    if row is None or row[0] is not True:
                        return False

        return True


def build_database_health_checker(database_url: str | None) -> DatabaseHealthChecker:
    if not database_url:
        return DefaultDatabaseHealthChecker(database_url)

    try:
        import psycopg  # noqa: F401
    except ImportError:
        return DefaultDatabaseHealthChecker(database_url)

    return PostgresDatabaseHealthChecker(database_url)


__all__ = [
    "DatabaseHealthChecker",
    "DefaultDatabaseHealthChecker",
    "PostgresDatabaseHealthChecker",
    "ServerBootstrapError",
    "build_database_health_checker",
]

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)


class ServerRuntime(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...


class CompositeRuntimeAdapter:
    """
    Aggregates multiple runtime adapters behind a single lifecycle boundary.
    """

    def __init__(self, runtimes: list[ServerRuntime]) -> None:
        self._runtimes = runtimes
        self._started = False

    def start(self) -> None:
        started: list[ServerRuntime] = []
        try:
            for runtime in self._runtimes:
                runtime.start()
                started.append(runtime)
            self._started = True
        except Exception:
            for runtime in reversed(started):
                try:
                    runtime.stop()
                except Exception:
                    logger.exception("Failed to stop partially started runtime")
            raise

    def stop(self) -> None:
        if not self._started:
            return

        for runtime in reversed(self._runtimes):
            try:
                runtime.stop()
            except Exception:
                logger.exception("Runtime shutdown failed")

        self._started = False


__all__ = [
    "CompositeRuntimeAdapter",
    "ServerRuntime",
]

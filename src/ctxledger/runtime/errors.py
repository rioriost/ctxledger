from __future__ import annotations


class ServerBootstrapError(RuntimeError):
    """
    Shared bootstrap/runtime configuration error for ctxledger startup helpers.

    Use this when a failure is caused by missing configuration, unavailable
    bootstrap dependencies, or invalid startup-time runtime state that should
    abort server initialization cleanly.
    """

    pass


__all__ = ["ServerBootstrapError"]

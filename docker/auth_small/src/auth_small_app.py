from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import FastAPI, Header, Response


@dataclass(frozen=True, slots=True)
class AuthSettings:
    expected_bearer_token: str
    auth_user: str
    auth_mode: str


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip()
    return normalized if normalized else default


def load_settings() -> AuthSettings:
    expected_bearer_token = _get_env("AUTH_SMALL_BEARER_TOKEN")
    if expected_bearer_token is None:
        raise RuntimeError("AUTH_SMALL_BEARER_TOKEN is required")

    return AuthSettings(
        expected_bearer_token=expected_bearer_token,
        auth_user=_get_env("AUTH_SMALL_USER", "local-dev") or "local-dev",
        auth_mode=_get_env("AUTH_SMALL_MODE", "static-token") or "static-token",
    )


def _extract_bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None

    normalized = authorization.strip()
    if not normalized:
        return None

    scheme, separator, token = normalized.partition(" ")
    if separator == "" or scheme.lower() != "bearer":
        return None

    token = token.strip()
    return token or None


settings = load_settings()
app = FastAPI(title="ctxledger-auth-small", version="0.1.0")


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth/verify")
def verify(
    response: Response,
    x_forwarded_uri: str | None = Header(default=None),
    x_forwarded_method: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    presented_token = _extract_bearer_token(authorization)
    if presented_token is None:
        response.status_code = 401
        response.headers["www-authenticate"] = 'Bearer realm="ctxledger-proxy"'
        return {
            "error": "missing_bearer_token",
            "message": "Authorization header must contain a bearer token",
        }

    if presented_token != settings.expected_bearer_token:
        response.status_code = 401
        response.headers["www-authenticate"] = 'Bearer realm="ctxledger-proxy"'
        return {
            "error": "invalid_bearer_token",
            "message": "Bearer token is invalid",
        }

    response.headers["X-Auth-User"] = settings.auth_user
    response.headers["X-Auth-Mode"] = settings.auth_mode
    if x_forwarded_uri:
        response.headers["X-Forwarded-Authenticated-Uri"] = x_forwarded_uri
    if x_forwarded_method:
        response.headers["X-Forwarded-Authenticated-Method"] = x_forwarded_method

    return {
        "status": "ok",
        "user": settings.auth_user,
        "mode": settings.auth_mode,
    }

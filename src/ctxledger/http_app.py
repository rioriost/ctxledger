from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Request, Response

from .config import AppSettings
from .runtime.http_handlers import (
    build_closed_projection_failures_http_handler,
    build_mcp_http_handler,
    build_projection_failures_ignore_http_handler,
    build_projection_failures_resolve_http_handler,
    build_runtime_introspection_http_handler,
    build_runtime_routes_http_handler,
    build_runtime_tools_http_handler,
    build_workflow_resume_http_handler,
)
from .server import CtxLedgerServer, create_server


def _authorization_query_value(request: Request) -> str | None:
    return _normalized_non_empty_string(request.headers.get("authorization"))


def _query_items_with_authorization(request: Request) -> list[tuple[str, str]]:
    items = list(request.query_params.multi_items())
    authorization = _authorization_query_value(request)
    if authorization is None:
        return items

    return [item for item in items if item[0] != "authorization"] + [
        ("authorization", authorization)
    ]


def _encode_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def _response_from_runtime_result(result: Any) -> Response:
    payload = getattr(result, "payload", {})
    status_code = getattr(result, "status_code", 200)
    headers = dict(getattr(result, "headers", {}) or {})
    headers.setdefault("content-type", "application/json")
    return Response(
        content=_encode_payload(payload),
        status_code=status_code,
        headers=headers,
        media_type="application/json",
    )


def _query_string_from_request(request: Request) -> str:
    items = _query_items_with_authorization(request)
    if not items:
        return ""
    return urlencode(items)


def _full_path_with_query(request: Request) -> str:
    query_string = _query_string_from_request(request)
    if not query_string:
        return request.url.path
    return f"{request.url.path}?{query_string}"


def _request_body_text(body: bytes) -> str | None:
    if not body:
        return None
    return body.decode("utf-8")


def _server_not_ready_response() -> Response:
    return Response(
        content=_encode_payload(
            {
                "error": {
                    "code": "server_not_ready",
                    "message": "runtime is not initialized",
                }
            }
        ),
        status_code=503,
        media_type="application/json",
    )


def _normalized_non_empty_string(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    return normalized


def _forward_get_request(
    request: Request,
    *,
    server: CtxLedgerServer,
    handler: Callable[[str], Any],
) -> Response:
    if server.runtime is None:
        return _server_not_ready_response()
    path = _full_path_with_query(request)
    result = handler(path)
    return _response_from_runtime_result(result)


def _build_get_route(
    server: CtxLedgerServer,
    handler_factory: Callable[[CtxLedgerServer], Callable[[str], Any]],
) -> Callable[[Request], Response]:
    handler = handler_factory(server)

    async def _handler(request: Request) -> Response:
        return _forward_get_request(
            request,
            server=server,
            handler=handler,
        )

    return _handler


def _build_post_route(
    server: CtxLedgerServer,
    handler_factory: Callable[[Any, CtxLedgerServer], Callable[[str, str | None], Any]],
) -> Callable[[Request], Response]:
    runtime = server.runtime
    handler = None if runtime is None else handler_factory(runtime, server)

    async def _handler(request: Request) -> Response:
        if handler is None:
            return _server_not_ready_response()
        body = await request.body()
        result = handler(
            _full_path_with_query(request),
            _request_body_text(body),
        )
        return _response_from_runtime_result(result)

    return _handler


def create_fastapi_app(server: CtxLedgerServer) -> FastAPI:
    @asynccontextmanager
    async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
        server.startup()
        try:
            yield
        finally:
            server.shutdown()

    app = FastAPI(
        title=server.settings.app_name,
        version=server.settings.app_version,
        lifespan=_lifespan,
    )

    mcp_path = server.settings.http.path
    if not mcp_path.startswith("/"):
        mcp_path = f"/{mcp_path}"

    app.add_api_route(
        mcp_path,
        _build_post_route(server, build_mcp_http_handler),
        methods=["POST"],
    )
    app.add_api_route(
        "/debug/runtime",
        _build_get_route(server, build_runtime_introspection_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/debug/routes",
        _build_get_route(server, build_runtime_routes_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/debug/tools",
        _build_get_route(server, build_runtime_tools_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/workflow-resume/{workflow_instance_id}",
        _build_get_route(server, build_workflow_resume_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/workflow-resume/{workflow_instance_id}/closed-projection-failures",
        _build_get_route(server, build_closed_projection_failures_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/projection_failures_ignore",
        _build_get_route(server, build_projection_failures_ignore_http_handler),
        methods=["GET"],
    )
    app.add_api_route(
        "/projection_failures_resolve",
        _build_get_route(server, build_projection_failures_resolve_http_handler),
        methods=["GET"],
    )

    return app


def create_fastapi_app_from_settings(settings: AppSettings) -> FastAPI:
    server = create_server(settings)
    return create_fastapi_app(server)


def create_default_fastapi_app() -> FastAPI:
    from .config import get_settings

    settings = get_settings()
    return create_fastapi_app_from_settings(settings)


app = create_default_fastapi_app()


__all__ = [
    "app",
    "create_default_fastapi_app",
    "create_fastapi_app",
    "create_fastapi_app_from_settings",
]

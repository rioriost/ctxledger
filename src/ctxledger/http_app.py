from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import FastAPI, Request, Response

from .config import AppSettings
from .server import CtxLedgerServer, create_server


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
    if not request.query_params:
        return ""
    return urlencode(list(request.query_params.multi_items()))


def _full_path_with_query(request: Request) -> str:
    query_string = _query_string_from_request(request)
    if not query_string:
        return request.url.path
    return f"{request.url.path}?{query_string}"


def _request_body_text(body: bytes) -> str | None:
    if not body:
        return None
    return body.decode("utf-8")


def _build_get_route(
    server: CtxLedgerServer,
    route_name: str,
) -> Callable[[Request], Response]:
    async def _handler(request: Request) -> Response:
        runtime = server.runtime
        if runtime is None:
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
        path = _full_path_with_query(request)
        result = runtime.dispatch(route_name, path)
        return _response_from_runtime_result(result)

    return _handler


def _build_post_route(
    server: CtxLedgerServer,
    route_name: str,
) -> Callable[[Request], Response]:
    async def _handler(request: Request) -> Response:
        runtime = server.runtime
        if runtime is None:
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
        body = await request.body()
        path = _full_path_with_query(request)
        result = runtime.dispatch(
            route_name,
            path,
            _request_body_text(body),
        )
        return _response_from_runtime_result(result)

    return _handler


def create_fastapi_app(server: CtxLedgerServer) -> FastAPI:
    app = FastAPI(
        title=server.settings.app_name,
        version=server.settings.app_version,
    )

    mcp_path = server.settings.http.path
    if not mcp_path.startswith("/"):
        mcp_path = f"/{mcp_path}"

    app.add_api_route(
        mcp_path,
        _build_post_route(server, "mcp_rpc"),
        methods=["POST"],
    )
    app.add_api_route(
        "/debug/runtime",
        _build_get_route(server, "runtime_introspection"),
        methods=["GET"],
    )
    app.add_api_route(
        "/debug/routes",
        _build_get_route(server, "runtime_routes"),
        methods=["GET"],
    )
    app.add_api_route(
        "/debug/tools",
        _build_get_route(server, "runtime_tools"),
        methods=["GET"],
    )
    app.add_api_route(
        "/workflow-resume/{workflow_instance_id}",
        _build_get_route(server, "workflow_resume"),
        methods=["GET"],
    )
    app.add_api_route(
        "/workflow-resume/{workflow_instance_id}/closed-projection-failures",
        _build_get_route(server, "workflow_closed_projection_failures"),
        methods=["GET"],
    )
    app.add_api_route(
        "/projection_failures_ignore",
        _build_get_route(server, "projection_failures_ignore"),
        methods=["GET"],
    )
    app.add_api_route(
        "/projection_failures_resolve",
        _build_get_route(server, "projection_failures_resolve"),
        methods=["GET"],
    )

    return app


def create_fastapi_app_from_settings(settings: AppSettings) -> FastAPI:
    server = create_server(settings)
    if server.runtime is not None and hasattr(server.runtime, "_server"):
        server.runtime._server = server
    server.startup()
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

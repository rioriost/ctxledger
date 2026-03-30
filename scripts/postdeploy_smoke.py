#!/usr/bin/env python3
"""
Post-deployment smoke test for the deployed ctxledger MCP endpoint.

This script is intended for Azure large deployment workflows, especially `azd`
postdeploy hooks. It validates that:

1. The deployed MCP endpoint URL is present.
2. The endpoint is reachable over HTTPS.
3. The endpoint responds in a way that indicates the deployment is alive.
4. Optional authentication expectations are enforced when configured.
5. Optional MCP initialize probing can be used to validate protocol-level reachability.
6. Optional MCP tools/list probing can be used to validate that the deployed endpoint
   can answer a basic MCP capability request after initialization.
7. Optional MCP resources/list probing can be used to validate that the deployed endpoint
   can answer a basic MCP resource capability request after initialization.

By default, this script performs a lightweight HTTP probe against the MCP
endpoint and treats the following as success signals:

- HTTP 200
- HTTP 401
- HTTP 403

These are all useful post-deploy signals:
- 200 usually means the endpoint is reachable and currently accessible
- 401 usually means the endpoint is reachable and correctly enforcing auth
- 403 usually means the endpoint is reachable and the caller is blocked as expected

The script can also enforce exact expected status codes if desired.

Environment variables supported:
- MCP_ENDPOINT_URL
- CTXLEDGER_DEPLOYED_MCP_ENDPOINT
- CTXLEDGER_EXPECT_SMOKE_STATUS
- CTXLEDGER_SMOKE_TIMEOUT_SECONDS
- CTXLEDGER_SMOKE_AUTH_BEARER_TOKEN
- CTXLEDGER_SMOKE_PROBE_MODE
- CTXLEDGER_SMOKE_PROTOCOL_VERSION
- CTXLEDGER_SMOKE_TOOLS_LIST_AFTER_INITIALIZE
- CTXLEDGER_SMOKE_RESOURCES_LIST_AFTER_INITIALIZE

Examples:

    python scripts/postdeploy_smoke.py

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/postdeploy_smoke.py --expect-status 401

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    CTXLEDGER_SMOKE_AUTH_BEARER_TOKEN="replace-me" \
    python scripts/postdeploy_smoke.py --expect-status 200

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/postdeploy_smoke.py --probe-mode initialize

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/postdeploy_smoke.py --probe-mode tools_list

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/postdeploy_smoke.py --probe-mode resources_list
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Final
from urllib.parse import urlparse

DEFAULT_TIMEOUT_SECONDS: Final[int] = 20
DEFAULT_ACCEPTABLE_STATUSES: Final[tuple[int, ...]] = (200, 401, 403)


class SmokeError(RuntimeError):
    """Raised when smoke validation fails."""


@dataclass(frozen=True, slots=True)
class SmokeConfig:
    endpoint_url: str
    timeout_seconds: int
    expect_status: int | None
    bearer_token: str | None
    method: str
    probe_mode: str
    protocol_version: str
    tools_list_after_initialize: bool
    resources_list_after_initialize: bool


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
        raise SmokeError(f"{name} must be an integer") from exc
    if value <= 0:
        raise SmokeError(f"{name} must be greater than 0")
    return value


def _normalize_endpoint_url(raw: str) -> str:
    value = raw.strip()
    parsed = urlparse(value)

    if parsed.scheme != "https":
        raise SmokeError("MCP endpoint URL must use https")
    if not parsed.netloc:
        raise SmokeError("MCP endpoint URL must be an absolute URL with a host")
    if not parsed.path:
        raise SmokeError("MCP endpoint URL must include the MCP path, such as /mcp")

    return value


def _resolve_endpoint_url(cli_value: str | None) -> str:
    if cli_value:
        return _normalize_endpoint_url(cli_value)

    env_value = _get_env("MCP_ENDPOINT_URL") or _get_env("CTXLEDGER_DEPLOYED_MCP_ENDPOINT")
    if not env_value:
        raise SmokeError(
            "MCP endpoint URL is required. Set MCP_ENDPOINT_URL or pass --endpoint-url."
        )

    return _normalize_endpoint_url(env_value)


def _resolve_timeout(cli_value: str | None) -> int:
    if cli_value is not None:
        return _parse_positive_int(cli_value, name="--timeout-seconds")

    env_value = _get_env("CTXLEDGER_SMOKE_TIMEOUT_SECONDS")
    if env_value is not None:
        return _parse_positive_int(env_value, name="CTXLEDGER_SMOKE_TIMEOUT_SECONDS")

    return DEFAULT_TIMEOUT_SECONDS


def _resolve_expected_status(cli_value: str | None) -> int | None:
    raw = cli_value or _get_env("CTXLEDGER_EXPECT_SMOKE_STATUS")
    if raw is None:
        return None

    value = _parse_positive_int(raw, name="expected status")
    if value < 100 or value > 599:
        raise SmokeError("Expected status must be a valid HTTP status code between 100 and 599")
    return value


def _resolve_bearer_token(cli_value: str | None) -> str | None:
    if cli_value is not None:
        token = cli_value.strip()
        return token or None

    env_value = _get_env("CTXLEDGER_SMOKE_AUTH_BEARER_TOKEN")
    if env_value is not None:
        return env_value

    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="postdeploy_smoke.py",
        description="Run a lightweight smoke test against the deployed ctxledger MCP endpoint.",
    )
    parser.add_argument(
        "--endpoint-url",
        help="Absolute HTTPS URL of the deployed MCP endpoint. Defaults to MCP_ENDPOINT_URL.",
    )
    parser.add_argument(
        "--timeout-seconds",
        help=f"HTTP timeout in seconds. Defaults to {DEFAULT_TIMEOUT_SECONDS}.",
    )
    parser.add_argument(
        "--expect-status",
        help=(
            "Exact expected HTTP status. If omitted, 200/401/403 are all treated "
            "as acceptable smoke-test success signals."
        ),
    )
    parser.add_argument(
        "--bearer-token",
        help=(
            "Optional bearer token used for the probe. Defaults to "
            "CTXLEDGER_SMOKE_AUTH_BEARER_TOKEN if set."
        ),
    )
    parser.add_argument(
        "--method",
        choices=("GET", "POST"),
        help=(
            "HTTP method used for the probe. If omitted, the method is chosen "
            "automatically based on the selected probe mode."
        ),
    )
    parser.add_argument(
        "--probe-mode",
        choices=("http", "initialize", "tools_list", "resources_list"),
        help=(
            "Probe mode. 'http' performs a lightweight HTTP reachability check. "
            "'initialize' sends an MCP initialize request body. "
            "'tools_list' performs initialize followed by tools/list. "
            "'resources_list' performs initialize followed by resources/list."
        ),
    )
    parser.add_argument(
        "--protocol-version",
        help=(
            "Protocol version used for MCP initialize probes. Defaults to "
            "CTXLEDGER_SMOKE_PROTOCOL_VERSION or 2024-11-05."
        ),
    )
    parser.add_argument(
        "--tools-list-after-initialize",
        action="store_true",
        help=(
            "When probe mode is initialize, also issue a follow-up MCP tools/list "
            "request after initialize succeeds."
        ),
    )
    parser.add_argument(
        "--resources-list-after-initialize",
        action="store_true",
        help=(
            "When probe mode is initialize, also issue a follow-up MCP resources/list "
            "request after initialize succeeds."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the result as JSON in addition to the human-readable summary.",
    )
    return parser


def load_config(args: argparse.Namespace) -> SmokeConfig:
    endpoint_url = _resolve_endpoint_url(args.endpoint_url)
    timeout_seconds = _resolve_timeout(args.timeout_seconds)
    expect_status = _resolve_expected_status(args.expect_status)
    bearer_token = _resolve_bearer_token(args.bearer_token)

    probe_mode = args.probe_mode or _get_env("CTXLEDGER_SMOKE_PROBE_MODE", "http")
    if probe_mode not in {"http", "initialize", "tools_list", "resources_list"}:
        raise SmokeError(
            "Probe mode must be one of 'http', 'initialize', 'tools_list', or 'resources_list'"
        )

    method = args.method or (
        "POST" if probe_mode in {"initialize", "tools_list", "resources_list"} else "GET"
    )
    protocol_version = (
        args.protocol_version
        or _get_env("CTXLEDGER_SMOKE_PROTOCOL_VERSION", "2024-11-05")
        or "2024-11-05"
    )
    tools_list_after_initialize = bool(args.tools_list_after_initialize)
    if probe_mode == "tools_list":
        tools_list_after_initialize = True
    elif not tools_list_after_initialize:
        env_value = _get_env("CTXLEDGER_SMOKE_TOOLS_LIST_AFTER_INITIALIZE")
        tools_list_after_initialize = (env_value or "").lower() in {"1", "true", "yes", "on"}

    resources_list_after_initialize = bool(args.resources_list_after_initialize)
    if probe_mode == "resources_list":
        resources_list_after_initialize = True
    elif not resources_list_after_initialize:
        env_value = _get_env("CTXLEDGER_SMOKE_RESOURCES_LIST_AFTER_INITIALIZE")
        resources_list_after_initialize = (env_value or "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    return SmokeConfig(
        endpoint_url=endpoint_url,
        timeout_seconds=timeout_seconds,
        expect_status=expect_status,
        bearer_token=bearer_token,
        method=method,
        probe_mode=probe_mode,
        protocol_version=protocol_version,
        tools_list_after_initialize=tools_list_after_initialize,
        resources_list_after_initialize=resources_list_after_initialize,
    )


def build_request(
    config: SmokeConfig,
    *,
    body: dict[str, object] | None = None,
    method: str | None = None,
) -> urllib.request.Request:
    headers = {
        "User-Agent": "ctxledger-postdeploy-smoke/1.0",
        "Accept": "application/json, text/plain, */*",
    }

    if config.bearer_token:
        headers["Authorization"] = f"Bearer {config.bearer_token}"

    data: bytes | None = None

    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    return urllib.request.Request(
        url=config.endpoint_url,
        headers=headers,
        method=method or config.method,
        data=data,
    )


def run_single_request(
    config: SmokeConfig,
    *,
    body: dict[str, object] | None = None,
    method: str | None = None,
) -> tuple[int, str]:
    request = build_request(config, body=body, method=method)

    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            body_text = response.read(4096).decode("utf-8", errors="replace")
            return response.status, body_text
    except urllib.error.HTTPError as exc:
        body_text = exc.read(4096).decode("utf-8", errors="replace")
        return exc.code, body_text
    except urllib.error.URLError as exc:
        raise SmokeError(f"Endpoint probe failed to connect: {exc}") from exc
    except TimeoutError as exc:
        raise SmokeError(
            f"Endpoint probe timed out after {config.timeout_seconds} seconds"
        ) from exc


def build_initialize_body(config: SmokeConfig) -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "postdeploy-smoke-initialize",
        "method": "initialize",
        "params": {
            "protocolVersion": config.protocol_version,
            "capabilities": {},
            "clientInfo": {
                "name": "ctxledger-postdeploy-smoke",
                "version": "1.0.0",
            },
        },
    }


def build_tools_list_body() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "postdeploy-smoke-tools-list",
        "method": "tools/list",
        "params": {},
    }


def build_resources_list_body() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": "postdeploy-smoke-resources-list",
        "method": "resources/list",
        "params": {},
    }


def run_probe(config: SmokeConfig) -> tuple[int, str]:
    if config.probe_mode == "http":
        return run_single_request(config)

    initialize_status, initialize_body = run_single_request(
        config,
        body=build_initialize_body(config),
        method="POST",
    )

    if initialize_status not in DEFAULT_ACCEPTABLE_STATUSES:
        return initialize_status, initialize_body

    response_sections = [f"initialize_response:\n{initialize_body}"]
    final_status = initialize_status

    if config.probe_mode == "tools_list" or config.tools_list_after_initialize:
        tools_status, tools_body = run_single_request(
            config,
            body=build_tools_list_body(),
            method="POST",
        )
        response_sections.append(f"tools_list_response:\n{tools_body}")
        final_status = tools_status

        if tools_status not in DEFAULT_ACCEPTABLE_STATUSES:
            return tools_status, "\n\n".join(response_sections)

    if config.probe_mode == "resources_list" or config.resources_list_after_initialize:
        resources_status, resources_body = run_single_request(
            config,
            body=build_resources_list_body(),
            method="POST",
        )
        response_sections.append(f"resources_list_response:\n{resources_body}")
        final_status = resources_status

        if resources_status not in DEFAULT_ACCEPTABLE_STATUSES:
            return resources_status, "\n\n".join(response_sections)

    return final_status, "\n\n".join(response_sections)


def validate_status(config: SmokeConfig, status: int) -> None:
    if config.expect_status is not None:
        if status != config.expect_status:
            raise SmokeError(
                f"Smoke test returned HTTP {status}, expected HTTP {config.expect_status}"
            )
        return

    if status not in DEFAULT_ACCEPTABLE_STATUSES:
        raise SmokeError(
            "Smoke test returned an unexpected HTTP status: "
            f"{status}. Expected one of {DEFAULT_ACCEPTABLE_STATUSES}."
        )


def summarize_status(status: int) -> str:
    if status == 200:
        return "endpoint reachable and accepted request"
    if status == 401:
        return "endpoint reachable and auth boundary appears to be enforced"
    if status == 403:
        return "endpoint reachable and caller is forbidden as expected"
    return f"endpoint returned HTTP {status}"


def print_human_result(config: SmokeConfig, status: int, body: str) -> None:
    print("ctxledger post-deploy smoke test passed")
    print(f"endpoint: {config.endpoint_url}")
    print(f"probe_mode: {config.probe_mode}")
    print(f"method: {config.method}")
    print(f"http_status: {status}")
    print(f"interpretation: {summarize_status(status)}")

    if config.probe_mode in {"initialize", "tools_list", "resources_list"}:
        print(f"protocol_version: {config.protocol_version}")

    follow_up_probes: list[str] = []
    if config.probe_mode == "tools_list" or config.tools_list_after_initialize:
        follow_up_probes.append("tools/list")
    if config.probe_mode == "resources_list" or config.resources_list_after_initialize:
        follow_up_probes.append("resources/list")

    if follow_up_probes:
        print(f"follow_up_probes: {', '.join(follow_up_probes)}")

    if body.strip():
        preview = body.strip()
        if len(preview) > 400:
            preview = preview[:400] + "..."
        print(f"body_preview: {preview}")


def print_json_result(config: SmokeConfig, status: int, body: str) -> None:
    preview = body.strip()
    if len(preview) > 400:
        preview = preview[:400] + "..."

    payload = {
        "ok": True,
        "endpoint": config.endpoint_url,
        "probe_mode": config.probe_mode,
        "method": config.method,
        "protocol_version": config.protocol_version
        if config.probe_mode in {"initialize", "tools_list", "resources_list"}
        else None,
        "tools_list_after_initialize": config.tools_list_after_initialize,
        "resources_list_after_initialize": config.resources_list_after_initialize,
        "http_status": status,
        "interpretation": summarize_status(status),
        "body_preview": preview,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args)
        status, body = run_probe(config)
        validate_status(config, status)
        print_human_result(config, status, body)
        if args.json:
            print_json_result(config, status, body)
        return 0
    except SmokeError as exc:
        print(f"Post-deploy smoke test failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected smoke test failure: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

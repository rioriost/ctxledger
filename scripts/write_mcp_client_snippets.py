#!/usr/bin/env python3
"""
Write ready-to-copy MCP client configuration snippets for a deployed ctxledger endpoint.

This script is intended for Azure large deployment workflows, especially after a
successful `azd up`. It reads the deployed MCP endpoint URL and writes snippet
files for representative clients so the final user task is reduced to copying or
adapting the desired client configuration.

Supported outputs:
- Zed JSON snippet
- VS Code snippet
- Claude Code JSON snippet
- summary metadata JSON

The script supports auth-aware snippet rendering. Callers can choose whether
authentication material should be rendered as:
- standard HTTP headers
- a placeholder auth header mode aligned with the intended large-pattern gateway contract

The generated summary metadata is also intended to serve as lightweight release
evidence for the deployment handoff path.

Environment variables supported:
- MCP_ENDPOINT_URL
- CTXLEDGER_DEPLOYED_MCP_ENDPOINT
- CTXLEDGER_MCP_SERVER_NAME
- CTXLEDGER_MCP_SNIPPETS_DIR
- CTXLEDGER_MCP_AUTH_MODE
- CTXLEDGER_MCP_AUTH_HEADER_NAME
- AZURE_ENV_NAME
- AZURE_LOCATION
- AZURE_ENV_TYPE
- CTXLEDGER_POSTDEPLOY_SMOKE_STATUS
- CTXLEDGER_POSTDEPLOY_SMOKE_PROBE_MODE
- CTXLEDGER_POSTDEPLOY_SMOKE_PROTOCOL_VERSION
- CTXLEDGER_POSTDEPLOY_SMOKE_FOLLOW_UP_PROBES
- CTXLEDGER_POSTDEPLOY_SMOKE_BODY_PREVIEW
- CTXLEDGER_DEPLOYMENT_TIMESTAMP
- CTXLEDGER_APP_VERSION

Examples:

    python scripts/write_mcp_client_snippets.py

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/write_mcp_client_snippets.py --output-dir .azure/snippets

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/write_mcp_client_snippets.py --bearer-token "replace-me"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final
from urllib.parse import urlparse

DEFAULT_SERVER_NAME: Final[str] = "ctxledger"
DEFAULT_OUTPUT_DIR: Final[str] = ".azure/mcp-snippets"


class SnippetError(RuntimeError):
    """Raised when snippet generation fails."""


@dataclass(frozen=True, slots=True)
class SnippetConfig:
    endpoint_url: str
    server_name: str
    output_dir: Path
    bearer_token: str | None
    auth_mode: str
    auth_header_name: str
    azure_environment_name: str | None
    azure_location: str | None
    azure_environment_type: str | None
    smoke_status: str | None
    smoke_probe_mode: str | None
    smoke_protocol_version: str | None
    smoke_follow_up_probes: str | None
    smoke_body_preview: str | None
    deployment_timestamp: str | None
    app_version: str | None


def _get_env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    stripped = value.strip()
    return stripped if stripped else default


def _normalize_endpoint_url(raw: str) -> str:
    value = raw.strip()
    parsed = urlparse(value)

    if parsed.scheme != "https":
        raise SnippetError("MCP endpoint URL must use https")
    if not parsed.netloc:
        raise SnippetError("MCP endpoint URL must be an absolute URL with a host")
    if not parsed.path:
        raise SnippetError("MCP endpoint URL must include the MCP path, such as /mcp")

    return value


def _resolve_endpoint_url(cli_value: str | None) -> str:
    if cli_value:
        return _normalize_endpoint_url(cli_value)

    env_value = _get_env("MCP_ENDPOINT_URL") or _get_env("CTXLEDGER_DEPLOYED_MCP_ENDPOINT")
    if not env_value:
        raise SnippetError(
            "MCP endpoint URL is required. Set MCP_ENDPOINT_URL or pass --endpoint-url."
        )

    return _normalize_endpoint_url(env_value)


def _resolve_server_name(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_SERVER_NAME", DEFAULT_SERVER_NAME)
    if value is None:
        return DEFAULT_SERVER_NAME

    normalized = value.strip()
    if not normalized:
        raise SnippetError("Server name must not be empty")
    return normalized


def _resolve_output_dir(cli_value: str | None) -> Path:
    value = cli_value or _get_env("CTXLEDGER_MCP_SNIPPETS_DIR", DEFAULT_OUTPUT_DIR)
    if value is None:
        value = DEFAULT_OUTPUT_DIR

    path = Path(value).expanduser()
    return path


def _resolve_bearer_token(cli_value: str | None) -> str | None:
    if cli_value is None:
        return None

    token = cli_value.strip()
    return token or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="write_mcp_client_snippets.py",
        description="Write MCP client configuration snippets for the deployed ctxledger endpoint.",
    )
    parser.add_argument(
        "--endpoint-url",
        help="Absolute HTTPS URL of the deployed MCP endpoint. Defaults to MCP_ENDPOINT_URL.",
    )
    parser.add_argument(
        "--server-name",
        help=f"Logical MCP server name. Defaults to {DEFAULT_SERVER_NAME!r}.",
    )
    parser.add_argument(
        "--output-dir",
        help=f"Directory where snippet files are written. Defaults to {DEFAULT_OUTPUT_DIR!r}.",
    )
    parser.add_argument(
        "--bearer-token",
        help=(
            "Optional bearer token to include in the generated snippets. "
            "If omitted, snippets are generated without Authorization headers."
        ),
    )
    parser.add_argument(
        "--auth-mode",
        choices=("none", "bearer_header", "custom_header"),
        help=(
            "Authentication rendering mode. "
            "'none' omits headers. "
            "'bearer_header' renders Authorization: Bearer <token>. "
            "'custom_header' renders a configurable header name."
        ),
    )
    parser.add_argument(
        "--auth-header-name",
        help=(
            "Header name used when --auth-mode=custom_header. "
            "Defaults to CTXLEDGER_MCP_AUTH_HEADER_NAME or Authorization."
        ),
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Also print the generated snippets to stdout after writing files.",
    )
    return parser


def _resolve_auth_mode(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_AUTH_MODE", "none")
    if value is None:
        return "none"

    normalized = value.strip()
    if normalized not in {"none", "bearer_header", "custom_header"}:
        raise SnippetError("Auth mode must be one of 'none', 'bearer_header', or 'custom_header'")
    return normalized


def _resolve_auth_header_name(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_AUTH_HEADER_NAME", "Authorization")
    if value is None:
        return "Authorization"

    normalized = value.strip()
    if not normalized:
        raise SnippetError("Auth header name must not be empty")
    return normalized


def load_config(args: argparse.Namespace) -> SnippetConfig:
    endpoint_url = _resolve_endpoint_url(args.endpoint_url)
    server_name = _resolve_server_name(args.server_name)
    output_dir = _resolve_output_dir(args.output_dir)
    bearer_token = _resolve_bearer_token(args.bearer_token)
    auth_mode = _resolve_auth_mode(args.auth_mode)
    auth_header_name = _resolve_auth_header_name(args.auth_header_name)

    return SnippetConfig(
        endpoint_url=endpoint_url,
        server_name=server_name,
        output_dir=output_dir,
        bearer_token=bearer_token,
        auth_mode=auth_mode,
        auth_header_name=auth_header_name,
        azure_environment_name=_get_env("AZURE_ENV_NAME"),
        azure_location=_get_env("AZURE_LOCATION"),
        azure_environment_type=_get_env("AZURE_ENV_TYPE"),
        smoke_status=_get_env("CTXLEDGER_POSTDEPLOY_SMOKE_STATUS"),
        smoke_probe_mode=_get_env("CTXLEDGER_POSTDEPLOY_SMOKE_PROBE_MODE"),
        smoke_protocol_version=_get_env("CTXLEDGER_POSTDEPLOY_SMOKE_PROTOCOL_VERSION"),
        smoke_follow_up_probes=_get_env("CTXLEDGER_POSTDEPLOY_SMOKE_FOLLOW_UP_PROBES"),
        smoke_body_preview=_get_env("CTXLEDGER_POSTDEPLOY_SMOKE_BODY_PREVIEW"),
        deployment_timestamp=_get_env("CTXLEDGER_DEPLOYMENT_TIMESTAMP"),
        app_version=_get_env("CTXLEDGER_APP_VERSION"),
    )


def _headers_block(config: SnippetConfig) -> dict[str, str] | None:
    if config.auth_mode == "none":
        return None

    if config.auth_mode == "bearer_header":
        if not config.bearer_token:
            return {"Authorization": "Bearer <replace-with-your-token>"}
        return {"Authorization": f"Bearer {config.bearer_token}"}

    if config.auth_mode == "custom_header":
        if not config.bearer_token:
            return {config.auth_header_name: "<replace-with-your-auth-value>"}
        return {config.auth_header_name: config.bearer_token}

    raise SnippetError(f"Unsupported auth mode: {config.auth_mode}")


def build_zed_snippet(config: SnippetConfig) -> str:
    payload: dict[str, object] = {
        config.server_name: {
            "url": config.endpoint_url,
        }
    }

    headers = _headers_block(config)
    if headers is not None:
        payload[config.server_name]["headers"] = headers  # type: ignore[index]

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_claude_code_snippet(config: SnippetConfig) -> str:
    server_payload: dict[str, object] = {
        "url": config.endpoint_url,
    }

    headers = _headers_block(config)
    if headers is not None:
        server_payload["headers"] = headers

    payload = {
        "mcpServers": {
            config.server_name: server_payload,
        }
    }

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_vscode_snippet(config: SnippetConfig) -> str:
    server_payload: dict[str, object] = {
        "url": config.endpoint_url,
        "type": "http",
    }

    headers = _headers_block(config)
    if headers is not None:
        server_payload["headers"] = headers

    payload = {
        "servers": {
            config.server_name: server_payload,
        }
    }

    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_summary_json(config: SnippetConfig, files: dict[str, str]) -> str:
    if config.auth_mode == "none":
        auth_usage_hint = (
            "Use the generated snippets as-is when the environment does not require "
            "client auth headers."
        )
    elif config.auth_mode == "bearer_header":
        auth_usage_hint = (
            "Use the generated snippets as a bearer-header starting point. Replace any "
            "placeholder token value before configuring your MCP client."
        )
    else:
        auth_usage_hint = (
            "Use the generated snippets as a custom-header starting point. Confirm that "
            "the configured header name matches the intended gateway contract before use."
        )

    if config.azure_environment_type == "dev":
        environment_usage_hint = (
            "Development handoff is intended to stay low-friction. Prefer the generated "
            "snippet files directly unless your environment has added extra auth layers."
        )
    elif config.azure_environment_type == "staging":
        environment_usage_hint = (
            "Staging handoff should rehearse the intended shared-environment client shape. "
            "Review auth headers and smoke metadata before sharing snippets broadly."
        )
    elif config.azure_environment_type == "prod":
        environment_usage_hint = (
            "Production-oriented handoff should be treated as the strongest contract. "
            "Verify auth header expectations and smoke metadata before distributing snippets."
        )
    else:
        environment_usage_hint = (
            "Review the generated snippets together with the environment and auth metadata "
            "before using them."
        )

    payload = {
        "schemaVersion": "1.0",
        "evidenceType": "ctxledger.mcp_handoff",
        "serverName": config.server_name,
        "endpointUrl": config.endpoint_url,
        "outputDirectory": str(config.output_dir),
        "artifacts": {
            "preferredArtifact": str(config.output_dir / "README.md"),
            "files": files,
        },
        "environment": {
            "azureEnvName": config.azure_environment_name,
            "azureLocation": config.azure_location,
            "azureEnvType": config.azure_environment_type,
        },
        "auth": {
            "mode": config.auth_mode,
            "headerName": (
                config.auth_header_name
                if config.auth_mode in {"bearer_header", "custom_header"}
                else None
            ),
            "includesConcreteCredential": config.bearer_token is not None,
        },
        "smoke": {
            "status": config.smoke_status,
            "probeMode": config.smoke_probe_mode,
            "protocolVersion": config.smoke_protocol_version,
            "followUpProbes": config.smoke_follow_up_probes,
            "bodyPreview": config.smoke_body_preview,
        },
        "deployment": {
            "timestamp": config.deployment_timestamp,
            "appVersion": config.app_version,
        },
        "recommendedUsage": {
            "authHint": auth_usage_hint,
            "environmentHint": environment_usage_hint,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise SnippetError(f"Output path is not a directory: {path}")


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def print_stdout_block(title: str, content: str) -> None:
    print()
    print(f"=== {title} ===")
    print(content.rstrip())
    print()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args)
        ensure_output_dir(config.output_dir)

        zed_path = config.output_dir / "zed.json"
        vscode_path = config.output_dir / "vscode.json"
        claude_code_path = config.output_dir / "claude-code.json"
        summary_path = config.output_dir / "summary.json"

        zed_content = build_zed_snippet(config)
        vscode_content = build_vscode_snippet(config)
        claude_code_content = build_claude_code_snippet(config)

        write_text_file(zed_path, zed_content)
        write_text_file(vscode_path, vscode_content)
        write_text_file(claude_code_path, claude_code_content)

        summary_content = build_summary_json(
            config,
            files={
                "zed": str(zed_path),
                "vscode": str(vscode_path),
                "claudeCode": str(claude_code_path),
            },
        )
        write_text_file(summary_path, summary_content)

        print("Wrote MCP client configuration snippets successfully.")
        print(f"endpoint: {config.endpoint_url}")
        print(f"server_name: {config.server_name}")
        print(f"output_dir: {config.output_dir}")
        print(f"auth_mode: {config.auth_mode}")
        if config.auth_mode == "custom_header":
            print(f"auth_header_name: {config.auth_header_name}")
        print(f"zed: {zed_path}")
        print(f"vscode: {vscode_path}")
        print(f"claude_code: {claude_code_path}")
        print(f"summary: {summary_path}")

        if args.stdout:
            print_stdout_block("Zed", zed_content)
            print_stdout_block("VS Code", vscode_content)
            print_stdout_block("Claude Code", claude_code_content)

        return 0
    except SnippetError as exc:
        print(f"Failed to write MCP client snippets: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected failure while writing MCP client snippets: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

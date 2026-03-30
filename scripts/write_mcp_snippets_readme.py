#!/usr/bin/env python3
"""
Render a small README artifact for generated MCP client snippets.

The script is intended for the Azure large deployment flow after MCP client
snippet files have already been written to disk. It creates a human-readable
Markdown summary that points to the generated snippet files and includes
copy-friendly examples for representative clients.

The script also supports auth-aware README rendering. Callers can choose whether
authentication guidance should be rendered as:
- no auth headers
- standard bearer Authorization headers
- a custom header name for future large-pattern gateway alignment

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

    python scripts/write_mcp_snippets_readme.py

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/write_mcp_snippets_readme.py --output-dir .azure/mcp-snippets

    MCP_ENDPOINT_URL="https://example.example/mcp" \
    python scripts/write_mcp_snippets_readme.py --bearer-token "replace-me"
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
DEFAULT_README_NAME: Final[str] = "README.md"


class ReadmeError(RuntimeError):
    """Raised when README artifact generation fails."""


@dataclass(frozen=True, slots=True)
class ReadmeConfig:
    endpoint_url: str
    server_name: str
    output_dir: Path
    output_path: Path
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
        raise ReadmeError("MCP endpoint URL must use https")
    if not parsed.netloc:
        raise ReadmeError("MCP endpoint URL must be an absolute URL with a host")
    if not parsed.path:
        raise ReadmeError("MCP endpoint URL must include the MCP path, such as /mcp")

    return value


def _resolve_endpoint_url(cli_value: str | None) -> str:
    if cli_value:
        return _normalize_endpoint_url(cli_value)

    env_value = _get_env("MCP_ENDPOINT_URL") or _get_env("CTXLEDGER_DEPLOYED_MCP_ENDPOINT")
    if not env_value:
        raise ReadmeError(
            "MCP endpoint URL is required. Set MCP_ENDPOINT_URL or pass --endpoint-url."
        )

    return _normalize_endpoint_url(env_value)


def _resolve_server_name(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_SERVER_NAME", DEFAULT_SERVER_NAME)
    if value is None:
        return DEFAULT_SERVER_NAME

    normalized = value.strip()
    if not normalized:
        raise ReadmeError("Server name must not be empty")
    return normalized


def _resolve_output_dir(cli_value: str | None) -> Path:
    value = cli_value or _get_env("CTXLEDGER_MCP_SNIPPETS_DIR", DEFAULT_OUTPUT_DIR)
    if value is None:
        value = DEFAULT_OUTPUT_DIR
    return Path(value).expanduser()


def _resolve_bearer_token(cli_value: str | None) -> str | None:
    if cli_value is None:
        return None
    token = cli_value.strip()
    return token or None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="write_mcp_snippets_readme.py",
        description="Write a rendered README artifact for generated MCP client snippets.",
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
        help=f"Directory containing MCP snippet artifacts. Defaults to {DEFAULT_OUTPUT_DIR!r}.",
    )
    parser.add_argument(
        "--output-path",
        help=(
            f"Optional explicit README output path. Defaults to <output-dir>/{DEFAULT_README_NAME}."
        ),
    )
    parser.add_argument(
        "--bearer-token",
        help=(
            "Optional bearer token note for the rendered examples. "
            "If omitted, placeholder auth values are rendered when auth mode "
            "requires them."
        ),
    )
    parser.add_argument(
        "--auth-mode",
        choices=("none", "bearer_header", "custom_header"),
        help=(
            "Authentication rendering mode. "
            "'none' omits auth guidance. "
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
        help="Also print the rendered README content to stdout after writing.",
    )
    return parser


def _resolve_auth_mode(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_AUTH_MODE", "none")
    if value is None:
        return "none"

    normalized = value.strip()
    if normalized not in {"none", "bearer_header", "custom_header"}:
        raise ReadmeError("Auth mode must be one of 'none', 'bearer_header', or 'custom_header'")
    return normalized


def _resolve_auth_header_name(cli_value: str | None) -> str:
    value = cli_value or _get_env("CTXLEDGER_MCP_AUTH_HEADER_NAME", "Authorization")
    if value is None:
        return "Authorization"

    normalized = value.strip()
    if not normalized:
        raise ReadmeError("Auth header name must not be empty")
    return normalized


def load_config(args: argparse.Namespace) -> ReadmeConfig:
    endpoint_url = _resolve_endpoint_url(args.endpoint_url)
    server_name = _resolve_server_name(args.server_name)
    output_dir = _resolve_output_dir(args.output_dir)

    output_path = (
        Path(args.output_path).expanduser()
        if args.output_path
        else output_dir / DEFAULT_README_NAME
    )

    return ReadmeConfig(
        endpoint_url=endpoint_url,
        server_name=server_name,
        output_dir=output_dir,
        output_path=output_path,
        bearer_token=_resolve_bearer_token(args.bearer_token),
        auth_mode=_resolve_auth_mode(args.auth_mode),
        auth_header_name=_resolve_auth_header_name(args.auth_header_name),
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


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ReadmeError(f"Output path is not a directory: {path}")


def build_zed_example(config: ReadmeConfig) -> str:
    payload: dict[str, object] = {
        config.server_name: {
            "url": config.endpoint_url,
        }
    }

    headers = _auth_headers(config)
    if headers is not None:
        payload[config.server_name]["headers"] = headers  # type: ignore[index]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_vscode_example(config: ReadmeConfig) -> str:
    payload: dict[str, object] = {
        "servers": {
            config.server_name: {
                "url": config.endpoint_url,
                "type": "http",
            }
        }
    }

    headers = _auth_headers(config)
    if headers is not None:
        payload["servers"][config.server_name]["headers"] = headers  # type: ignore[index]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_claude_code_example(config: ReadmeConfig) -> str:
    payload: dict[str, object] = {
        "mcpServers": {
            config.server_name: {
                "url": config.endpoint_url,
            }
        }
    }

    headers = _auth_headers(config)
    if headers is not None:
        payload["mcpServers"][config.server_name]["headers"] = headers  # type: ignore[index]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _auth_headers(config: ReadmeConfig) -> dict[str, str] | None:
    if config.auth_mode == "none":
        return None

    if config.auth_mode == "bearer_header":
        if config.bearer_token:
            return {"Authorization": f"Bearer {config.bearer_token}"}
        return {"Authorization": "Bearer <replace-with-your-token>"}

    if config.auth_mode == "custom_header":
        if config.bearer_token:
            return {config.auth_header_name: config.bearer_token}
        return {config.auth_header_name: "<replace-with-your-auth-value>"}

    raise ReadmeError(f"Unsupported auth mode: {config.auth_mode}")


def build_token_note(config: ReadmeConfig) -> str:
    if config.auth_mode == "none":
        return (
            "This README was generated without auth headers. If your final large-pattern "
            "gateway requires authentication, add the appropriate headers before using "
            "the snippets.\n"
        )

    if config.auth_mode == "bearer_header":
        if config.bearer_token:
            return (
                "A bearer token was supplied when this README was generated, so the example "
                "snippets below include an `Authorization` header.\n"
            )
        return (
            "Bearer-header mode was selected, but no concrete token was supplied when this "
            "README was generated. The example snippets below therefore include a placeholder "
            "`Authorization` header value.\n"
        )

    if config.auth_mode == "custom_header":
        if config.bearer_token:
            return (
                f"Custom-header auth mode was selected, so the example snippets below include "
                f"the header `{config.auth_header_name}`.\n"
            )
        return (
            f"Custom-header auth mode was selected, but no concrete auth value was supplied "
            f"when this README was generated. The example snippets below therefore include a "
            f"placeholder for the header `{config.auth_header_name}`.\n"
        )

    raise ReadmeError(f"Unsupported auth mode: {config.auth_mode}")


def render_readme(config: ReadmeConfig) -> str:
    zed_example = build_zed_example(config)
    vscode_example = build_vscode_example(config)
    claude_code_example = build_claude_code_example(config)

    if config.auth_mode == "none":
        auth_usage_hint = (
            "Use the generated snippets as-is when the environment does not require "
            "client auth headers."
        )
    elif config.auth_mode == "bearer_header":
        auth_usage_hint = (
            "Use the generated snippets as a bearer-header starting point. Replace "
            "any placeholder token value before configuring your MCP client."
        )
    else:
        auth_usage_hint = (
            "Use the generated snippets as a custom-header starting point. Confirm "
            "that the configured header name matches the intended gateway contract "
            "before use."
        )

    if config.azure_environment_type == "dev":
        environment_usage_hint = (
            "Development handoff is intended to stay low-friction. Prefer the "
            "generated snippet files directly unless your environment has added "
            "extra auth layers."
        )
    elif config.azure_environment_type == "staging":
        environment_usage_hint = (
            "Staging handoff should rehearse the intended shared-environment client "
            "shape. Review auth headers and smoke metadata before sharing snippets "
            "broadly."
        )
    elif config.azure_environment_type == "prod":
        environment_usage_hint = (
            "Production-oriented handoff should be treated as the strongest "
            "contract. Verify auth header expectations and smoke metadata before "
            "distributing snippets."
        )
    else:
        environment_usage_hint = (
            "Review the generated snippets together with the environment and auth "
            "metadata before using them."
        )

    return f"""# Generated MCP Client Snippets

This directory contains generated MCP client configuration artifacts
for the deployed `ctxledger` endpoint.

## Deployment summary

- server name:
  - `{config.server_name}`
- MCP endpoint:
  - `{config.endpoint_url}`
- Azure environment name:
  - `{config.azure_environment_name or "unknown"}`
- Azure location:
  - `{config.azure_location or "unknown"}`
- Azure environment type:
  - `{config.azure_environment_type or "unknown"}`
- postdeploy smoke status:
  - `{config.smoke_status or "unknown"}`
- postdeploy smoke probe mode:
  - `{config.smoke_probe_mode or "unknown"}`
- postdeploy smoke protocol version:
  - `{config.smoke_protocol_version or "unknown"}`
- postdeploy smoke follow-up probes:
  - `{config.smoke_follow_up_probes or "unknown"}`
- postdeploy smoke body preview:
  - `{config.smoke_body_preview or "unknown"}`
- deployment timestamp:
  - `{config.deployment_timestamp or "unknown"}`
- application version:
  - `{config.app_version or "unknown"}`

## Files in this directory

- `zed.json`
- `vscode.json`
- `claude-code.json`
- `summary.json`
- `README.md`

## How to use these artifacts

1. Choose the client you want to configure.
2. Open the matching JSON snippet file in this directory.
3. Copy the relevant block into your MCP client configuration.
4. If needed, adapt authentication headers for your environment.

## Authentication note

{build_token_note(config).rstrip()}

## Authentication mode summary

- auth mode:
  - `{config.auth_mode}`
- auth header name:
  - `{config.auth_header_name if config.auth_mode == "custom_header" else "Authorization"}`
- intended reading:
  - `dev` usually aligns with `none`
  - `staging` usually aligns with `bearer_header`
  - `prod` can align with `custom_header` when the gateway requires it

## Recommended usage hints

- auth handoff hint:
  - `{auth_usage_hint}`
- environment handoff hint:
  - `{environment_usage_hint}`
- preferred artifact:
  - `{config.output_dir / "README.md"}`

## Postdeploy smoke summary

- smoke status:
  - `{config.smoke_status or "unknown"}`
- smoke probe mode:
  - `{config.smoke_probe_mode or "unknown"}`
- smoke protocol version:
  - `{config.smoke_protocol_version or "unknown"}`
- smoke follow-up probes:
  - `{config.smoke_follow_up_probes or "unknown"}`
- smoke body preview:
  - `{config.smoke_body_preview or "unknown"}`

## Deployment metadata

- timestamp:
  - `{config.deployment_timestamp or "unknown"}`
- application version:
  - `{config.app_version or "unknown"}`

## Zed example

```json
{zed_example}
```

## VS Code example

```json
{vscode_example}
```

## Claude Code example

```json
{claude_code_example}
```

## Recommended user handoff

After a successful Azure large deployment:

1. confirm the deployed MCP endpoint is the expected one
2. choose the MCP client you want to configure
3. copy the matching snippet from this directory
4. paste it into your client configuration
5. add any auth headers required by your final large-pattern gateway posture

## Artifact location

This README was generated in:

- `{config.output_path}`

The snippet directory is:

- `{config.output_dir}`
"""


def write_text_file(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args)
        ensure_output_dir(config.output_dir)

        content = render_readme(config)
        write_text_file(config.output_path, content)

        print("Wrote MCP snippet README successfully.")
        print(f"endpoint: {config.endpoint_url}")
        print(f"server_name: {config.server_name}")
        print(f"output_dir: {config.output_dir}")
        print(f"readme: {config.output_path}")

        if args.stdout:
            print()
            print(content.rstrip())
            print()

        return 0
    except ReadmeError as exc:
        print(f"Failed to write MCP snippet README: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover
        print(f"Unexpected failure while writing MCP snippet README: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

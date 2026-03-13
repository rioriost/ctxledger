from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8080"
DEFAULT_MCP_PATH = "/mcp"


@dataclass(frozen=True)
class JsonRpcResponse:
    status_code: int
    payload: dict[str, Any]


class SmokeFailure(RuntimeError):
    """Raised when the MCP smoke check fails."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mcp_http_smoke",
        description="Minimal HTTP MCP smoke test for ctxledger",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Base server URL (default: {DEFAULT_BASE_URL})",
    )
    parser.add_argument(
        "--mcp-path",
        default=DEFAULT_MCP_PATH,
        help=f"MCP HTTP path (default: {DEFAULT_MCP_PATH})",
    )
    parser.add_argument(
        "--bearer-token",
        default=None,
        help="Optional bearer token for authenticated MCP endpoints",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--scenario",
        choices=("basic", "workflow"),
        default="basic",
        help="Smoke scenario to run (default: basic)",
    )
    parser.add_argument(
        "--tool-name",
        default="memory_get_context",
        help="Tool name to call during the smoke test (default: memory_get_context)",
    )
    parser.add_argument(
        "--tool-arguments",
        default='{"workflow_instance_id":"smoke-workflow","limit":1,"include_episodes":true,"include_memory_items":false,"include_summaries":true}',
        help="JSON object string passed as tool arguments",
    )
    parser.add_argument(
        "--resource-uri",
        default=None,
        help="Optional resource URI to verify with resources/read after resources/list",
    )
    parser.add_argument(
        "--workflow-resource-read",
        action="store_true",
        help="When running the workflow scenario, also read workflow resources for the created workflow",
    )
    return parser


def _normalize_url(base_url: str, mcp_path: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = mcp_path if mcp_path.startswith("/") else f"/{mcp_path}"
    return f"{normalized_base}{normalized_path}"


def _post_json(
    *,
    url: str,
    payload: dict[str, Any],
    bearer_token: str | None,
    timeout_seconds: float,
) -> JsonRpcResponse:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "content-type": "application/json",
        "accept": "application/json",
    }
    if bearer_token:
        headers["authorization"] = f"Bearer {bearer_token}"

    request = urllib.request.Request(
        url=url,
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise SmokeFailure("HTTP response body was not a JSON object")
            return JsonRpcResponse(status_code=response.status, payload=parsed)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = {"raw_error_body": raw}
        if not isinstance(parsed, dict):
            parsed = {"raw_error_body": raw}
        return JsonRpcResponse(status_code=exc.code, payload=parsed)
    except urllib.error.URLError as exc:
        raise SmokeFailure(f"Failed to connect to MCP endpoint: {exc}") from exc


def _require_jsonrpc_success(
    response: JsonRpcResponse,
    *,
    expected_id: int,
    method_name: str,
) -> dict[str, Any]:
    if response.status_code != 200:
        raise SmokeFailure(
            f"{method_name} returned HTTP {response.status_code}: "
            f"{json.dumps(response.payload, ensure_ascii=False)}"
        )

    payload = response.payload
    if payload.get("jsonrpc") != "2.0":
        raise SmokeFailure(f"{method_name} response missing jsonrpc=2.0")
    if payload.get("id") != expected_id:
        raise SmokeFailure(
            f"{method_name} response id mismatch: expected {expected_id}, got {payload.get('id')}"
        )
    if "error" in payload:
        raise SmokeFailure(
            f"{method_name} returned JSON-RPC error: "
            f"{json.dumps(payload['error'], ensure_ascii=False)}"
        )

    result = payload.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"{method_name} response result was not an object")
    return result


def _parse_tool_arguments(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SmokeFailure(f"--tool-arguments must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise SmokeFailure("--tool-arguments must decode to a JSON object")
    return value


def _extract_text_content(result: dict[str, Any], *, method_name: str) -> str:
    content = result.get("content")
    if not isinstance(content, list) or not content:
        raise SmokeFailure(f"{method_name} result did not contain content[]")

    first = content[0]
    if not isinstance(first, dict):
        raise SmokeFailure(f"{method_name} first content item was not an object")

    text = first.get("text")
    if not isinstance(text, str):
        raise SmokeFailure(f"{method_name} content item did not contain text")
    return text


def _print_step(name: str, data: dict[str, Any]) -> None:
    print(f"[ok] {name}")
    print(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True))


def _call_tool(
    *,
    endpoint_url: str,
    bearer_token: str | None,
    timeout_seconds: float,
    request_id: int,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    tools_call_request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }
    tools_call_response = _post_json(
        url=endpoint_url,
        payload=tools_call_request,
        bearer_token=bearer_token,
        timeout_seconds=timeout_seconds,
    )
    tools_call_result = _require_jsonrpc_success(
        tools_call_response,
        expected_id=request_id,
        method_name="tools/call",
    )
    tool_text = _extract_text_content(tools_call_result, method_name="tools/call")
    try:
        parsed_tool_payload = json.loads(tool_text)
    except json.JSONDecodeError:
        parsed_tool_payload = {"raw_text": tool_text}
    if not isinstance(parsed_tool_payload, dict):
        raise SmokeFailure(
            f"tools/call for '{tool_name}' did not return a JSON object payload"
        )
    return parsed_tool_payload


def _require_tool_success(
    tool_payload: dict[str, Any],
    *,
    tool_name: str,
) -> dict[str, Any]:
    if tool_payload.get("ok") is not True:
        raise SmokeFailure(
            f"{tool_name} did not succeed: {json.dumps(tool_payload, ensure_ascii=False)}"
        )
    result = tool_payload.get("result")
    if not isinstance(result, dict):
        raise SmokeFailure(f"{tool_name} result was not an object")
    return result


def _run_workflow_scenario(
    *,
    endpoint_url: str,
    bearer_token: str | None,
    timeout_seconds: float,
    read_resources: bool = False,
) -> None:
    workspace_result = _require_tool_success(
        _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
            request_id=10,
            tool_name="workspace_register",
            arguments={
                "repo_url": f"https://example.com/ctxledger-smoke-{timeout_seconds}.git",
                "canonical_path": f"/tmp/ctxledger-smoke-{timeout_seconds}",
                "default_branch": "main",
                "metadata": {
                    "scenario": "workflow",
                    "source": "mcp_http_smoke",
                },
            },
        ),
        tool_name="workspace_register",
    )
    workspace_id = workspace_result.get("workspace_id")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise SmokeFailure("workspace_register did not return workspace_id")
    _print_step("workspace_register", workspace_result)

    workflow_start_result = _require_tool_success(
        _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
            request_id=11,
            tool_name="workflow_start",
            arguments={
                "workspace_id": workspace_id,
                "ticket_id": "SMOKE-CTXLEDGER-001",
                "metadata": {
                    "scenario": "workflow",
                    "source": "mcp_http_smoke",
                },
            },
        ),
        tool_name="workflow_start",
    )
    workflow_instance_id = workflow_start_result.get("workflow_instance_id")
    attempt_id = workflow_start_result.get("attempt_id")
    if not isinstance(workflow_instance_id, str) or not workflow_instance_id:
        raise SmokeFailure("workflow_start did not return workflow_instance_id")
    if not isinstance(attempt_id, str) or not attempt_id:
        raise SmokeFailure("workflow_start did not return attempt_id")
    _print_step("workflow_start", workflow_start_result)

    workflow_checkpoint_result = _require_tool_success(
        _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
            request_id=12,
            tool_name="workflow_checkpoint",
            arguments={
                "workflow_instance_id": workflow_instance_id,
                "attempt_id": attempt_id,
                "step_name": "smoke_validation",
                "summary": "Created by MCP smoke workflow scenario",
                "checkpoint_json": {
                    "next_action": "complete_workflow",
                    "scenario": "workflow",
                },
                "verify_status": "passed",
                "verify_report": {
                    "status": "passed",
                    "checks": ["mcp_http_smoke"],
                },
            },
        ),
        tool_name="workflow_checkpoint",
    )
    _print_step("workflow_checkpoint", workflow_checkpoint_result)

    workflow_resume_result = _require_tool_success(
        _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
            request_id=13,
            tool_name="workflow_resume",
            arguments={
                "workflow_instance_id": workflow_instance_id,
            },
        ),
        tool_name="workflow_resume",
    )
    _print_step("workflow_resume", workflow_resume_result)

    if read_resources:
        workspace_resume_uri = f"workspace://{workspace_id}/resume"
        workspace_resume_request = {
            "jsonrpc": "2.0",
            "id": 15,
            "method": "resources/read",
            "params": {
                "uri": workspace_resume_uri,
            },
        }
        workspace_resume_response = _post_json(
            url=endpoint_url,
            payload=workspace_resume_request,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
        )
        workspace_resume_result = _require_jsonrpc_success(
            workspace_resume_response,
            expected_id=15,
            method_name="resources/read",
        )
        workspace_resume_contents = workspace_resume_result.get("contents")
        if (
            not isinstance(workspace_resume_contents, list)
            or not workspace_resume_contents
            or not isinstance(workspace_resume_contents[0], dict)
        ):
            raise SmokeFailure(
                "resources/read for workspace resume did not return a valid contents[] payload"
            )
        _print_step("resources/read workspace resume", workspace_resume_contents[0])

        workflow_detail_uri = (
            f"workspace://{workspace_id}/workflow/{workflow_instance_id}"
        )
        workflow_detail_request = {
            "jsonrpc": "2.0",
            "id": 16,
            "method": "resources/read",
            "params": {
                "uri": workflow_detail_uri,
            },
        }
        workflow_detail_response = _post_json(
            url=endpoint_url,
            payload=workflow_detail_request,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
        )
        workflow_detail_result = _require_jsonrpc_success(
            workflow_detail_response,
            expected_id=16,
            method_name="resources/read",
        )
        workflow_detail_contents = workflow_detail_result.get("contents")
        if (
            not isinstance(workflow_detail_contents, list)
            or not workflow_detail_contents
            or not isinstance(workflow_detail_contents[0], dict)
        ):
            raise SmokeFailure(
                "resources/read for workflow detail did not return a valid contents[] payload"
            )
        _print_step("resources/read workflow detail", workflow_detail_contents[0])

    workflow_complete_result = _require_tool_success(
        _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=bearer_token,
            timeout_seconds=timeout_seconds,
            request_id=14,
            tool_name="workflow_complete",
            arguments={
                "workflow_instance_id": workflow_instance_id,
                "attempt_id": attempt_id,
                "workflow_status": "completed",
                "summary": "Completed by MCP smoke workflow scenario",
                "verify_status": "passed",
                "verify_report": {
                    "status": "passed",
                    "checks": ["mcp_http_smoke"],
                },
            },
        ),
        tool_name="workflow_complete",
    )
    _print_step("workflow_complete", workflow_complete_result)


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        endpoint_url = _normalize_url(args.base_url, args.mcp_path)
        tool_arguments = _parse_tool_arguments(args.tool_arguments)

        initialize_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "ctxledger-mcp-http-smoke",
                    "version": "0.1.0",
                },
            },
        }
        initialize_response = _post_json(
            url=endpoint_url,
            payload=initialize_request,
            bearer_token=args.bearer_token,
            timeout_seconds=args.timeout_seconds,
        )
        initialize_result = _require_jsonrpc_success(
            initialize_response,
            expected_id=1,
            method_name="initialize",
        )
        protocol_version = initialize_result.get("protocolVersion")
        if not isinstance(protocol_version, str) or not protocol_version:
            raise SmokeFailure("initialize result did not include protocolVersion")
        _print_step("initialize", initialize_result)

        tools_list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        tools_list_response = _post_json(
            url=endpoint_url,
            payload=tools_list_request,
            bearer_token=args.bearer_token,
            timeout_seconds=args.timeout_seconds,
        )
        tools_list_result = _require_jsonrpc_success(
            tools_list_response,
            expected_id=2,
            method_name="tools/list",
        )
        tools = tools_list_result.get("tools")
        if not isinstance(tools, list):
            raise SmokeFailure("tools/list result did not contain tools[]")
        tool_names = [
            item.get("name")
            for item in tools
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        ]
        if args.tool_name not in tool_names:
            raise SmokeFailure(
                f"tools/list did not advertise expected tool '{args.tool_name}'"
            )
        _print_step(
            "tools/list",
            {
                "tool_count": len(tools),
                "tool_names": tool_names,
            },
        )

        parsed_tool_payload = _call_tool(
            endpoint_url=endpoint_url,
            bearer_token=args.bearer_token,
            timeout_seconds=args.timeout_seconds,
            request_id=3,
            tool_name=args.tool_name,
            arguments=tool_arguments,
        )
        _print_step(
            "tools/call",
            {
                "tool_name": args.tool_name,
                "tool_response": parsed_tool_payload,
            },
        )

        resources_list_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {},
        }
        resources_list_response = _post_json(
            url=endpoint_url,
            payload=resources_list_request,
            bearer_token=args.bearer_token,
            timeout_seconds=args.timeout_seconds,
        )
        resources_list_result = _require_jsonrpc_success(
            resources_list_response,
            expected_id=4,
            method_name="resources/list",
        )
        resources = resources_list_result.get("resources")
        if not isinstance(resources, list):
            raise SmokeFailure("resources/list result did not contain resources[]")

        resource_uris = [
            item.get("uri")
            for item in resources
            if isinstance(item, dict) and isinstance(item.get("uri"), str)
        ]
        _print_step(
            "resources/list",
            {
                "resource_count": len(resources),
                "resource_uris": resource_uris,
            },
        )

        if args.resource_uri:
            resources_read_request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "resources/read",
                "params": {
                    "uri": args.resource_uri,
                },
            }
            resources_read_response = _post_json(
                url=endpoint_url,
                payload=resources_read_request,
                bearer_token=args.bearer_token,
                timeout_seconds=args.timeout_seconds,
            )
            resources_read_result = _require_jsonrpc_success(
                resources_read_response,
                expected_id=5,
                method_name="resources/read",
            )
            contents = resources_read_result.get("contents")
            if not isinstance(contents, list) or not contents:
                raise SmokeFailure("resources/read result did not contain contents[]")
            first = contents[0]
            if not isinstance(first, dict):
                raise SmokeFailure(
                    "resources/read first content item was not an object"
                )
            _print_step("resources/read", first)

        if args.scenario == "workflow":
            _run_workflow_scenario(
                endpoint_url=endpoint_url,
                bearer_token=args.bearer_token,
                timeout_seconds=args.timeout_seconds,
                read_resources=args.workflow_resource_read,
            )

        print("[ok] MCP HTTP smoke test completed")
        return 0
    except SmokeFailure as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

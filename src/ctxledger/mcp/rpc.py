from __future__ import annotations

import json
from typing import Any, Protocol

from ..memory.service import MemoryServiceError
from .lifecycle import (
    McpLifecycleState,
    build_jsonrpc_success_response,
    dispatch_lifecycle_method,
)
from .tool_schemas import McpToolSchema, serialize_mcp_tool_schema


def build_mcp_interaction_request_event(
    *,
    method: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(tool_name, str) or not tool_name.strip():
            return None
        if not isinstance(arguments, dict):
            arguments = {}
        return {
            "interaction_role": "user",
            "interaction_direction": "inbound",
            "transport": "mcp",
            "interaction_kind": "tool_call",
            "method": method,
            "tool_name": tool_name.strip(),
            "arguments": arguments,
        }

    if method == "resources/read":
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            return None
        return {
            "interaction_role": "user",
            "interaction_direction": "inbound",
            "transport": "mcp",
            "interaction_kind": "resource_read",
            "method": method,
            "resource_uri": uri.strip(),
        }

    return None


def build_mcp_interaction_response_event(
    *,
    method: str,
    params: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any] | None:
    if method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        if not isinstance(tool_name, str) or not tool_name.strip():
            return None
        if not isinstance(arguments, dict):
            arguments = {}
        return {
            "interaction_role": "agent",
            "interaction_direction": "outbound",
            "transport": "mcp",
            "interaction_kind": "tool_result",
            "method": method,
            "tool_name": tool_name.strip(),
            "arguments": arguments,
            "result": result,
        }

    if method == "resources/read":
        uri = params.get("uri")
        if not isinstance(uri, str) or not uri.strip():
            return None
        return {
            "interaction_role": "agent",
            "interaction_direction": "outbound",
            "transport": "mcp",
            "interaction_kind": "resource_result",
            "method": method,
            "resource_uri": uri.strip(),
            "result": result,
        }

    return None


class McpRpcRuntime(Protocol):
    settings: Any

    def registered_tools(self) -> tuple[str, ...]: ...
    def registered_resources(self) -> tuple[str, ...]: ...
    def tool_schema(self, tool_name: str) -> McpToolSchema: ...
    def dispatch_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any: ...
    def dispatch_resource(self, uri: str) -> Any: ...


def _extract_interaction_scope_ids(
    *,
    request_event: dict[str, Any] | None,
    response_event: dict[str, Any] | None,
) -> tuple[str | None, str | None]:
    normalized_request_event = request_event or {}
    normalized_response_event = response_event or {}

    workspace_id: str | None = None
    workflow_instance_id: str | None = None

    arguments = normalized_request_event.get("arguments")
    if isinstance(arguments, dict):
        if arguments.get("workspace_id") is not None:
            workspace_id = str(arguments["workspace_id"])
        if arguments.get("workflow_instance_id") is not None:
            workflow_instance_id = str(arguments["workflow_instance_id"])

    result_payload = normalized_response_event.get("result")
    if isinstance(result_payload, dict):
        contents = result_payload.get("contents")
        if isinstance(contents, list) and contents:
            first_content = contents[0]
            if isinstance(first_content, dict):
                text_payload = first_content.get("text")
                if isinstance(text_payload, str) and text_payload.strip():
                    try:
                        parsed_payload = json.loads(text_payload)
                    except json.JSONDecodeError:
                        parsed_payload = None

                    if isinstance(parsed_payload, dict):
                        resource_payload = parsed_payload.get("resource")
                        if isinstance(resource_payload, dict):
                            nested_workspace = resource_payload.get("workspace")
                            if workspace_id is None and isinstance(nested_workspace, dict):
                                if nested_workspace.get("workspace_id") is not None:
                                    workspace_id = str(nested_workspace["workspace_id"])
                            if (
                                workspace_id is None
                                and resource_payload.get("workspace_id") is not None
                            ):
                                workspace_id = str(resource_payload["workspace_id"])

                            nested_workflow = resource_payload.get("workflow")
                            if (
                                workflow_instance_id is None
                                and isinstance(nested_workflow, dict)
                                and nested_workflow.get("workflow_instance_id") is not None
                            ):
                                workflow_instance_id = str(nested_workflow["workflow_instance_id"])
                            if (
                                workflow_instance_id is None
                                and resource_payload.get("workflow_instance_id") is not None
                            ):
                                workflow_instance_id = str(resource_payload["workflow_instance_id"])

                        selection_payload = parsed_payload.get("selection")
                        if (
                            workflow_instance_id is None
                            and isinstance(selection_payload, dict)
                            and selection_payload.get("selected_workflow_instance_id") is not None
                        ):
                            workflow_instance_id = str(
                                selection_payload["selected_workflow_instance_id"]
                            )

                        workspace_payload = parsed_payload.get("workspace")
                        if (
                            workspace_id is None
                            and isinstance(workspace_payload, dict)
                            and workspace_payload.get("workspace_id") is not None
                        ):
                            workspace_id = str(workspace_payload["workspace_id"])

                        workflow_payload = parsed_payload.get("workflow")
                        if (
                            workflow_instance_id is None
                            and isinstance(workflow_payload, dict)
                            and workflow_payload.get("workflow_instance_id") is not None
                        ):
                            workflow_instance_id = str(workflow_payload["workflow_instance_id"])
                        if (
                            workspace_id is None
                            and isinstance(workflow_payload, dict)
                            and workflow_payload.get("workspace_id") is not None
                        ):
                            workspace_id = str(workflow_payload["workspace_id"])

    return workspace_id, workflow_instance_id


def _persist_interaction_event_pair(
    runtime: McpRpcRuntime,
    *,
    request_event: dict[str, Any] | None,
    response_event: dict[str, Any] | None,
) -> None:
    if request_event is None or response_event is None:
        return

    server = getattr(runtime, "_server", None)
    workflow_service = getattr(server, "workflow_service", None) if server is not None else None
    if server is None or workflow_service is None:
        return

    memory_service_builder = getattr(runtime, "_build_workflow_backed_memory_service", None)
    if not callable(memory_service_builder):
        return

    if not hasattr(runtime, "_persisted_interaction_events"):
        return

    persistence_service = memory_service_builder(server)
    persist_interaction_memory = getattr(
        persistence_service,
        "persist_interaction_memory",
        None,
    )
    if not callable(persist_interaction_memory):
        return

    workspace_id, workflow_instance_id = _extract_interaction_scope_ids(
        request_event=request_event,
        response_event=response_event,
    )

    request_content = json.dumps(request_event, ensure_ascii=False, sort_keys=True)
    response_content = json.dumps(response_event, ensure_ascii=False, sort_keys=True)

    try:
        persist_interaction_memory(
            content=request_content,
            interaction_role=str(request_event.get("interaction_role", "user")),
            interaction_kind="interaction_request",
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            metadata=dict(request_event),
        )
        persist_interaction_memory(
            content=response_content,
            interaction_role=str(response_event.get("interaction_role", "agent")),
            interaction_kind="interaction_response",
            workspace_id=workspace_id,
            workflow_instance_id=workflow_instance_id,
            metadata=dict(response_event),
        )
    except MemoryServiceError:
        return


LIFECYCLE_METHODS = frozenset(
    {
        "initialize",
        "initialized",
        "notifications/initialized",
        "ping",
        "shutdown",
    }
)


def ensure_lifecycle_state(runtime: McpRpcRuntime) -> McpLifecycleState:
    lifecycle_state = getattr(runtime, "_mcp_lifecycle_state", None)
    if lifecycle_state is None:
        lifecycle_state = McpLifecycleState()
        setattr(runtime, "_mcp_lifecycle_state", lifecycle_state)
    return lifecycle_state


def handle_mcp_rpc_request(
    runtime: McpRpcRuntime,
    req: dict[str, Any],
) -> dict[str, Any] | None:
    method = req.get("method")
    params = req.get("params") or {}
    req_id = req.get("id")

    normalized_method = method if isinstance(method, str) else ""
    normalized_params = params if isinstance(params, dict) else {}
    interaction_request_event = build_mcp_interaction_request_event(
        method=normalized_method,
        params=normalized_params,
    )
    if interaction_request_event is not None:
        setattr(runtime, "_last_mcp_interaction_request_event", interaction_request_event)

    lifecycle_result = _dispatch_lifecycle_request(runtime, method, params)
    if method in LIFECYCLE_METHODS:
        if req_id is None or lifecycle_result is None:
            return None
        return build_jsonrpc_success_response(req_id, lifecycle_result)

    result = dispatch_rpc_method(
        runtime,
        method=method,
        params=params,
    )

    interaction_response_event = build_mcp_interaction_response_event(
        method=normalized_method,
        params=normalized_params,
        result=result,
    )
    if interaction_response_event is not None:
        setattr(runtime, "_last_mcp_interaction_response_event", interaction_response_event)

    _persist_interaction_event_pair(
        runtime,
        request_event=interaction_request_event,
        response_event=interaction_response_event,
    )

    if req_id is None:
        return None

    return build_jsonrpc_success_response(req_id, result)


def dispatch_rpc_method(
    runtime: McpRpcRuntime,
    *,
    method: Any,
    params: Any,
) -> dict[str, Any]:
    dispatch_table = {
        "tools/list": lambda: _build_tools_list_result(runtime),
        "tools/call": lambda: _build_tools_call_result(runtime, params),
        "resources/list": lambda: _build_resources_list_result(runtime),
        "resources/read": lambda: _build_resources_read_result(runtime, params),
    }

    if method == "exit":
        raise SystemExit(0)

    handler = dispatch_table.get(method)
    if handler is None:
        raise ValueError(f"Unknown method: {method}")
    return handler()


def _dispatch_lifecycle_request(
    runtime: McpRpcRuntime,
    method: Any,
    params: Any,
) -> dict[str, Any] | None:
    lifecycle_state = ensure_lifecycle_state(runtime)
    return dispatch_lifecycle_method(
        runtime,
        lifecycle_state,
        method if isinstance(method, str) else None,
        params if isinstance(params, dict) else None,
    )


def _build_tools_list_result(runtime: McpRpcRuntime) -> dict[str, Any]:
    return {
        "tools": [
            {
                "name": tool_name,
                "description": f"{tool_name} tool",
                "inputSchema": serialize_mcp_tool_schema(runtime.tool_schema(tool_name)),
            }
            for tool_name in runtime.registered_tools()
        ]
    }


def _build_tools_call_result(
    runtime: McpRpcRuntime,
    params: Any,
) -> dict[str, Any]:
    validated_params = _require_object_params(
        params,
        method_name="tools/call",
    )
    name = _require_non_empty_string_field(
        validated_params,
        field_name="name",
        method_name="tools/call",
    )
    arguments = _require_object_field(
        validated_params,
        field_name="arguments",
        method_name="tools/call",
        default={},
    )

    response = runtime.dispatch_tool(name, arguments)
    return {
        "content": [
            {
                "type": "text",
                "text": _json_text_payload(response.payload),
            }
        ]
    }


def _build_resources_list_result(runtime: McpRpcRuntime) -> dict[str, Any]:
    return {
        "resources": [
            {
                "uri": resource_uri,
                "name": resource_uri,
                "description": f"{resource_uri} resource",
            }
            for resource_uri in runtime.registered_resources()
        ]
    }


def _build_resources_read_result(
    runtime: McpRpcRuntime,
    params: Any,
) -> dict[str, Any]:
    validated_params = _require_object_params(
        params,
        method_name="resources/read",
    )
    normalized_uri = _require_non_empty_string_field(
        validated_params,
        field_name="uri",
        method_name="resources/read",
    )

    response = runtime.dispatch_resource(normalized_uri)
    return {
        "contents": [
            {
                "uri": normalized_uri,
                "mimeType": "application/json",
                "text": _json_text_payload(response.payload),
            }
        ]
    }


def _require_object_params(
    params: Any,
    *,
    method_name: str,
) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError(f"{method_name} requires 'params' (object)")
    return params


def _require_non_empty_string_field(
    params: dict[str, Any],
    *,
    field_name: str,
    method_name: str,
) -> str:
    value = params.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{method_name} requires '{field_name}' (string)")
    return value.strip()


def _require_object_field(
    params: dict[str, Any],
    *,
    field_name: str,
    method_name: str,
    default: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value = params.get(field_name)
    if value is None:
        value = default if default is not None else {}
    if not isinstance(value, dict):
        raise ValueError(f"{method_name} requires '{field_name}' (object)")
    return value


def _json_text_payload(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False)


__all__ = [
    "LIFECYCLE_METHODS",
    "McpRpcRuntime",
    "build_mcp_interaction_request_event",
    "build_mcp_interaction_response_event",
    "dispatch_rpc_method",
    "ensure_lifecycle_state",
    "handle_mcp_rpc_request",
]

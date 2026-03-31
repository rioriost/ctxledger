from __future__ import annotations

import json
from typing import Any, Protocol

_FILE_TOUCHING_TOOL_NAMES = frozenset(
    {
        "edit_file",
        "copy_path",
        "move_path",
        "delete_path",
        "save_file",
        "restore_file_from_disk",
    }
)


class FileWorkRecordHandler(Protocol):
    def __call__(self, arguments: dict[str, Any]) -> Any: ...


def is_file_touching_tool(tool_name: str | None) -> bool:
    if not isinstance(tool_name, str):
        return False
    return tool_name.strip() in _FILE_TOUCHING_TOOL_NAMES


def extract_file_work_metadata(
    *,
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    normalized_tool_name = tool_name.strip()

    def _first_non_empty_string(value: Any) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _string_list(value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        results: list[str] = []
        for item in value:
            if isinstance(item, str) and item.strip():
                results.append(item.strip())
        return results

    metadata: dict[str, Any] = {}

    direct_file_path = _first_non_empty_string(arguments.get("path"))
    direct_source_path = _first_non_empty_string(arguments.get("source_path"))
    direct_destination_path = _first_non_empty_string(arguments.get("destination_path"))
    direct_file_name = _first_non_empty_string(arguments.get("file_name"))
    direct_purpose = _first_non_empty_string(arguments.get("purpose"))

    if direct_source_path is not None and direct_destination_path is not None:
        metadata["file_path"] = direct_destination_path
        metadata["file_paths"] = [direct_source_path, direct_destination_path]
        metadata["file_work_paths"] = [direct_source_path, direct_destination_path]
    elif direct_file_path is not None:
        metadata["file_path"] = direct_file_path

    if direct_file_name is not None:
        metadata["file_name"] = direct_file_name
    elif direct_file_path is not None:
        metadata["file_name"] = direct_file_path.rsplit("/", 1)[-1]
    elif direct_destination_path is not None:
        metadata["file_name"] = direct_destination_path.rsplit("/", 1)[-1]
    elif direct_source_path is not None:
        metadata["file_name"] = direct_source_path.rsplit("/", 1)[-1]

    if direct_purpose is not None:
        metadata["purpose"] = direct_purpose

    if normalized_tool_name == "read_file":
        if direct_file_path is not None:
            metadata["file_operation"] = "read"
    elif normalized_tool_name == "edit_file":
        if direct_file_path is not None:
            mode = _first_non_empty_string(arguments.get("mode"))
            if mode == "create":
                metadata["file_operation"] = "create"
            elif mode == "overwrite":
                metadata["file_operation"] = "overwrite"
            else:
                metadata["file_operation"] = "modify"
    elif normalized_tool_name == "copy_path":
        if direct_source_path is not None and direct_destination_path is not None:
            metadata["file_operation"] = "copy"
    elif normalized_tool_name == "move_path":
        if direct_source_path is not None and direct_destination_path is not None:
            metadata["file_operation"] = "move"
    elif normalized_tool_name == "delete_path":
        if direct_file_path is not None:
            metadata["file_operation"] = "delete"
    elif normalized_tool_name == "save_file":
        file_paths = _string_list(arguments.get("paths"))
        if file_paths:
            metadata["file_operation"] = "save"
            metadata["file_path"] = file_paths[0]
            metadata["file_paths"] = file_paths
            metadata["file_work_paths"] = file_paths
            metadata["file_work_count"] = len(file_paths)
            if "file_name" not in metadata:
                metadata["file_name"] = file_paths[0].rsplit("/", 1)[-1]
    elif normalized_tool_name == "restore_file_from_disk":
        file_paths = _string_list(arguments.get("paths"))
        if file_paths:
            metadata["file_operation"] = "restore"
            metadata["file_path"] = file_paths[0]
            metadata["file_paths"] = file_paths
            metadata["file_work_paths"] = file_paths
            metadata["file_work_count"] = len(file_paths)
            if "file_name" not in metadata:
                metadata["file_name"] = file_paths[0].rsplit("/", 1)[-1]

    if "file_paths" in metadata and "file_work_count" not in metadata:
        file_paths_value = metadata.get("file_paths")
        if isinstance(file_paths_value, list):
            metadata["file_work_count"] = len(file_paths_value)

    return metadata


def build_auto_file_work_summary(
    *,
    tool_name: str,
    file_operation: str,
    file_path: str,
    purpose: str | None = None,
) -> str:
    summary = f"Auto-recorded file-work after {tool_name}: {file_operation} {file_path}"
    if isinstance(purpose, str) and purpose.strip():
        summary += f" ({purpose.strip()})"
    return summary


def extract_result_text_payload(result_payload: dict[str, Any]) -> str | None:
    content_items = result_payload.get("content")
    if not isinstance(content_items, list):
        return None

    for item in content_items:
        if not isinstance(item, dict):
            continue
        text_value = item.get("text")
        if isinstance(text_value, str) and text_value.strip():
            return text_value.strip()

    return None


def parse_result_text_json(result_text: str | None) -> dict[str, Any] | None:
    if not isinstance(result_text, str) or not result_text.strip():
        return None

    try:
        parsed_result = json.loads(result_text)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed_result, dict):
        return parsed_result
    return None


def should_auto_record_file_work(
    *,
    tool_name: str,
    file_work_metadata: dict[str, Any],
    workflow_instance_id: str | None,
    response_payload: dict[str, Any],
    allow_tool_error_for_file_touching_tools: bool = False,
) -> bool:
    if tool_name.strip() == "file_work_record":
        return False

    file_path = file_work_metadata.get("file_path")
    file_operation = file_work_metadata.get("file_operation")

    if not isinstance(file_path, str) or not file_path.strip():
        return False
    if not isinstance(file_operation, str) or not file_operation.strip():
        return False
    if not isinstance(workflow_instance_id, str) or not workflow_instance_id.strip():
        return False

    if "error" in response_payload and not (
        allow_tool_error_for_file_touching_tools and is_file_touching_tool(tool_name)
    ):
        return False

    result_wrapper = response_payload.get("result")
    if isinstance(result_wrapper, dict) and isinstance(result_wrapper.get("error"), dict):
        return False

    result_text = extract_result_text_payload(response_payload)
    parsed_result = parse_result_text_json(result_text)
    if isinstance(parsed_result, dict) and isinstance(parsed_result.get("error"), dict):
        return False

    return True


def record_file_work_automation(
    *,
    remember_handler: FileWorkRecordHandler,
    workflow_instance_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    response_payload: dict[str, Any],
    recording_mode: str,
    extra_metadata: dict[str, Any] | None = None,
) -> bool:
    file_work_metadata = extract_file_work_metadata(
        tool_name=tool_name,
        arguments=arguments,
    )

    if not should_auto_record_file_work(
        tool_name=tool_name,
        file_work_metadata=file_work_metadata,
        workflow_instance_id=workflow_instance_id,
        response_payload=response_payload,
        allow_tool_error_for_file_touching_tools=True,
    ):
        return False

    file_path = str(file_work_metadata["file_path"]).strip()
    file_operation = str(file_work_metadata["file_operation"]).strip()
    purpose_value = file_work_metadata.get("purpose")
    purpose = (
        purpose_value.strip() if isinstance(purpose_value, str) and purpose_value.strip() else None
    )

    metadata: dict[str, Any] = {
        "recording_mode": recording_mode,
        "source_tool_name": tool_name,
        "source_arguments": dict(arguments),
        "source_response": response_payload,
    }

    result_wrapper = response_payload.get("result")
    if isinstance(result_wrapper, dict):
        metadata["source_result_wrapper"] = result_wrapper

    result_text = extract_result_text_payload(response_payload)
    parsed_result = parse_result_text_json(result_text)
    if parsed_result is not None:
        metadata["source_result_text_json"] = parsed_result
    elif result_text is not None:
        metadata["source_result_text"] = result_text

    if isinstance(extra_metadata, dict):
        metadata.update(extra_metadata)

    remember_handler(
        {
            "workflow_instance_id": workflow_instance_id.strip(),
            "summary": build_auto_file_work_summary(
                tool_name=tool_name,
                file_operation=file_operation,
                file_path=file_path,
                purpose=purpose,
            ),
            "file_path": file_path,
            "file_name": file_work_metadata.get("file_name"),
            "file_operation": file_operation,
            "purpose": purpose,
            "metadata": metadata,
        }
    )
    return True


__all__ = [
    "FileWorkRecordHandler",
    "build_auto_file_work_summary",
    "extract_file_work_metadata",
    "extract_result_text_payload",
    "is_file_touching_tool",
    "parse_result_text_json",
    "record_file_work_automation",
    "should_auto_record_file_work",
]

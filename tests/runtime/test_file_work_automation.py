from __future__ import annotations

import json

from ctxledger.runtime.file_work_automation import (
    build_auto_file_work_summary,
    extract_file_work_metadata,
    extract_result_text_payload,
    is_file_touching_tool,
    parse_result_text_json,
    record_file_work_automation,
    should_auto_record_file_work,
)


def test_is_file_touching_tool_handles_known_unknown_and_blank_values() -> None:
    assert is_file_touching_tool("edit_file") is True
    assert is_file_touching_tool(" save_file ") is True
    assert is_file_touching_tool("read_file") is False
    assert is_file_touching_tool("unknown_tool") is False
    assert is_file_touching_tool("") is False
    assert is_file_touching_tool(None) is False


def test_extract_file_work_metadata_for_edit_file_modes_and_derived_name() -> None:
    create_metadata = extract_file_work_metadata(
        tool_name="edit_file",
        arguments={
            "path": "ctxledger/tests/runtime/test_file_work_automation.py",
            "mode": "create",
            "purpose": "add tests",
        },
    )
    assert create_metadata == {
        "file_path": "ctxledger/tests/runtime/test_file_work_automation.py",
        "file_name": "test_file_work_automation.py",
        "purpose": "add tests",
        "file_operation": "create",
    }

    overwrite_metadata = extract_file_work_metadata(
        tool_name="edit_file",
        arguments={
            "path": "ctxledger/tests/runtime/test_file_work_automation.py",
            "mode": "overwrite",
        },
    )
    assert overwrite_metadata["file_operation"] == "overwrite"
    assert overwrite_metadata["file_name"] == "test_file_work_automation.py"

    modify_metadata = extract_file_work_metadata(
        tool_name="edit_file",
        arguments={
            "path": "ctxledger/tests/runtime/test_file_work_automation.py",
            "mode": "edit",
        },
    )
    assert modify_metadata["file_operation"] == "modify"
    assert modify_metadata["file_name"] == "test_file_work_automation.py"


def test_extract_file_work_metadata_for_copy_move_save_restore_and_delete() -> None:
    copy_metadata = extract_file_work_metadata(
        tool_name="copy_path",
        arguments={
            "source_path": "ctxledger/src/source.py",
            "destination_path": "ctxledger/tests/copied.py",
        },
    )
    assert copy_metadata == {
        "file_path": "ctxledger/tests/copied.py",
        "file_paths": ["ctxledger/src/source.py", "ctxledger/tests/copied.py"],
        "file_work_paths": ["ctxledger/src/source.py", "ctxledger/tests/copied.py"],
        "file_name": "copied.py",
        "file_operation": "copy",
        "file_work_count": 2,
    }

    move_metadata = extract_file_work_metadata(
        tool_name="move_path",
        arguments={
            "source_path": "ctxledger/tests/old_name.py",
            "destination_path": "ctxledger/tests/new_name.py",
        },
    )
    assert move_metadata["file_operation"] == "move"
    assert move_metadata["file_name"] == "new_name.py"

    save_metadata = extract_file_work_metadata(
        tool_name="save_file",
        arguments={
            "paths": [
                "ctxledger/tests/a.py",
                "",
                123,
                "ctxledger/tests/b.py",
            ],
        },
    )
    assert save_metadata == {
        "file_operation": "save",
        "file_path": "ctxledger/tests/a.py",
        "file_paths": ["ctxledger/tests/a.py", "ctxledger/tests/b.py"],
        "file_work_paths": ["ctxledger/tests/a.py", "ctxledger/tests/b.py"],
        "file_work_count": 2,
        "file_name": "a.py",
    }

    restore_metadata = extract_file_work_metadata(
        tool_name="restore_file_from_disk",
        arguments={"paths": ["ctxledger/tests/restored.py"]},
    )
    assert restore_metadata == {
        "file_operation": "restore",
        "file_path": "ctxledger/tests/restored.py",
        "file_paths": ["ctxledger/tests/restored.py"],
        "file_work_paths": ["ctxledger/tests/restored.py"],
        "file_work_count": 1,
        "file_name": "restored.py",
    }

    delete_metadata = extract_file_work_metadata(
        tool_name="delete_path",
        arguments={"path": "ctxledger/tests/deleted.py"},
    )
    assert delete_metadata == {
        "file_path": "ctxledger/tests/deleted.py",
        "file_name": "deleted.py",
        "file_operation": "delete",
    }


def test_extract_result_text_payload_and_parse_result_text_json_cover_edge_cases() -> (
    None
):
    assert extract_result_text_payload({}) is None
    assert extract_result_text_payload({"content": "not-a-list"}) is None
    assert (
        extract_result_text_payload({"content": [1, {"text": "  "}, {"text": "ok"}]})
        == "ok"
    )

    assert parse_result_text_json(None) is None
    assert parse_result_text_json("") is None
    assert parse_result_text_json("not-json") is None
    assert parse_result_text_json("[1,2,3]") is None
    assert parse_result_text_json('{"ok": true}') == {"ok": True}


def test_should_auto_record_file_work_rejects_invalid_inputs_and_errors() -> None:
    base_metadata = {
        "file_path": "ctxledger/tests/runtime/test_file_work_automation.py",
        "file_operation": "modify",
    }

    assert (
        should_auto_record_file_work(
            tool_name="file_work_record",
            file_work_metadata=base_metadata,
            workflow_instance_id="workflow-1",
            response_payload={},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata={"file_operation": "modify"},
            workflow_instance_id="workflow-1",
            response_payload={},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata={"file_path": "ctxledger/tests/x.py"},
            workflow_instance_id="workflow-1",
            response_payload={},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata=base_metadata,
            workflow_instance_id="   ",
            response_payload={},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata=base_metadata,
            workflow_instance_id="workflow-1",
            response_payload={"error": {"message": "failed"}},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata=base_metadata,
            workflow_instance_id="workflow-1",
            response_payload={"result": {"error": {"message": "nested failed"}}},
        )
        is False
    )
    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata=base_metadata,
            workflow_instance_id="workflow-1",
            response_payload={
                "content": [{"text": json.dumps({"error": {"message": "text failed"}})}]
            },
        )
        is False
    )


def test_should_auto_record_file_work_allows_file_touching_tool_error_when_enabled() -> (
    None
):
    metadata = {
        "file_path": "ctxledger/tests/runtime/test_file_work_automation.py",
        "file_operation": "modify",
    }

    assert (
        should_auto_record_file_work(
            tool_name="edit_file",
            file_work_metadata=metadata,
            workflow_instance_id="workflow-1",
            response_payload={"error": {"message": "top-level tool error"}},
            allow_tool_error_for_file_touching_tools=True,
        )
        is True
    )

    assert (
        should_auto_record_file_work(
            tool_name="read_file",
            file_work_metadata=metadata,
            workflow_instance_id="workflow-1",
            response_payload={"error": {"message": "top-level tool error"}},
            allow_tool_error_for_file_touching_tools=True,
        )
        is False
    )


def test_build_auto_file_work_summary_includes_optional_purpose() -> None:
    assert (
        build_auto_file_work_summary(
            tool_name="edit_file",
            file_operation="modify",
            file_path="ctxledger/tests/runtime/test_file_work_automation.py",
        )
        == "Auto-recorded file-work after edit_file: modify ctxledger/tests/runtime/test_file_work_automation.py"
    )
    assert (
        build_auto_file_work_summary(
            tool_name="edit_file",
            file_operation="modify",
            file_path="ctxledger/tests/runtime/test_file_work_automation.py",
            purpose="add tests",
        )
        == "Auto-recorded file-work after edit_file: modify ctxledger/tests/runtime/test_file_work_automation.py (add tests)"
    )


def test_record_file_work_automation_returns_false_when_gating_fails() -> None:
    recorded: list[dict[str, object]] = []

    result = record_file_work_automation(
        remember_handler=recorded.append,
        workflow_instance_id="workflow-1",
        tool_name="edit_file",
        arguments={"mode": "edit"},
        response_payload={},
        recording_mode="auto",
    )

    assert result is False
    assert recorded == []


def test_record_file_work_automation_records_wrapper_parsed_json_and_extra_metadata() -> (
    None
):
    recorded: list[dict[str, object]] = []

    response_payload = {
        "result": {"status": "ok", "memory_id": "123"},
        "content": [{"text": json.dumps({"saved": True, "count": 2})}],
    }

    result = record_file_work_automation(
        remember_handler=recorded.append,
        workflow_instance_id=" workflow-1 ",
        tool_name="edit_file",
        arguments={
            "path": "ctxledger/tests/runtime/test_file_work_automation.py",
            "mode": "edit",
            "purpose": "  add tests  ",
        },
        response_payload=response_payload,
        recording_mode="auto",
        extra_metadata={"session": "abc"},
    )

    assert result is True
    assert len(recorded) == 1

    payload = recorded[0]
    assert payload["workflow_instance_id"] == "workflow-1"
    assert (
        payload["file_path"] == "ctxledger/tests/runtime/test_file_work_automation.py"
    )
    assert payload["file_name"] == "test_file_work_automation.py"
    assert payload["file_operation"] == "modify"
    assert payload["purpose"] == "add tests"
    assert payload["summary"] == (
        "Auto-recorded file-work after edit_file: modify "
        "ctxledger/tests/runtime/test_file_work_automation.py (add tests)"
    )

    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["recording_mode"] == "auto"
    assert metadata["source_tool_name"] == "edit_file"
    assert metadata["source_arguments"] == {
        "path": "ctxledger/tests/runtime/test_file_work_automation.py",
        "mode": "edit",
        "purpose": "  add tests  ",
    }
    assert metadata["source_response"] == response_payload
    assert metadata["source_result_wrapper"] == {"status": "ok", "memory_id": "123"}
    assert metadata["source_result_text_json"] == {"saved": True, "count": 2}
    assert metadata["session"] == "abc"


def test_record_file_work_automation_records_raw_text_when_json_parse_fails() -> None:
    recorded: list[dict[str, object]] = []

    result = record_file_work_automation(
        remember_handler=recorded.append,
        workflow_instance_id="workflow-2",
        tool_name="save_file",
        arguments={"paths": ["ctxledger/tests/runtime/test_file_work_automation.py"]},
        response_payload={"content": [{"text": "saved successfully"}]},
        recording_mode="manual",
    )

    assert result is True
    assert len(recorded) == 1

    metadata = recorded[0]["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["recording_mode"] == "manual"
    assert metadata["source_result_text"] == "saved successfully"
    assert "source_result_text_json" not in metadata

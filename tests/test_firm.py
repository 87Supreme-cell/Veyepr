import json
from io import StringIO
from pathlib import Path

import pytest

from ai_observability.firm import FirmExecutionLog, read_host_events
from ai_observability.firm_mcp import dispatch, serve, tool_definitions
from ai_observability.sentinel import AgentAction, SentinelPolicy

ROOT = Path(__file__).parent.parent


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def build_log() -> FirmExecutionLog:
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))
    execution_log = FirmExecutionLog(policy)
    read_host_events(ROOT / "fixtures/firm-host-events.ndjson", execution_log)
    return execution_log


def test_host_adapter_records_review_only_digest_chain() -> None:
    execution_log = build_log()

    assert [entry.decision.disposition for entry in execution_log.entries] == [
        "no_review_required",
        "review_required",
    ]
    assert all(entry.decision.response_mode == "review_only" for entry in execution_log.entries)
    assert execution_log.entries[1].previous_digest == execution_log.entries[0].entry_digest
    assert execution_log.verify_chain()


def test_host_adapter_exports_markdown_and_text_without_raw_content(tmp_path: Path) -> None:
    markdown_log = build_log()
    markdown_path = markdown_log.export(tmp_path / "markdown", "markdown")
    markdown = markdown_path.read_text(encoding="utf-8")

    assert markdown_path.name == "firm-execution-log.md"
    assert "host-observed metadata only" in markdown
    assert "review_required" in markdown
    assert "sensitive content" not in markdown

    text_log = build_log()
    text_path = text_log.export(tmp_path / "text", "text")
    text = text_path.read_text(encoding="utf-8")

    assert text_path.name == "firm-execution-log.txt"
    assert "authority_boundary=host_controlled_review_only" in text
    assert "decision=review_required" in text


def test_host_adapter_refuses_overwrite_and_unknown_action_metadata(tmp_path: Path) -> None:
    execution_log = build_log()
    execution_log.export(tmp_path, "markdown")

    with pytest.raises(FileExistsError):
        execution_log.export(tmp_path, "markdown")

    record = load_json("fixtures/normal-agent-action.json")
    record["source"] = "model_declared"
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))
    empty_log = FirmExecutionLog(policy)

    with pytest.raises(ValueError, match="unexpected fields"):
        empty_log.record_host_event(record)
    assert empty_log.entries == ()


def test_mcp_exposes_only_read_only_evidence_tools(tmp_path: Path) -> None:
    execution_log = build_log()
    log_path = execution_log.export(tmp_path, "markdown")
    tool_names = {tool["name"] for tool in tool_definitions()}

    assert tool_names == {"veyepr_execution_log_summary", "veyepr_policy_boundary"}
    assert all(tool["annotations"]["readOnlyHint"] is True for tool in tool_definitions())

    response = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "veyepr_execution_log_summary", "arguments": {}},
        },
        log_path=log_path,
        policy_path=ROOT / "policy/mock-sentinel-policy.json",
    )
    payload = json.loads(response["result"]["content"][0]["text"])

    assert response["result"]["isError"] is False
    assert payload["entry_count"] == 2
    assert payload["review_required_count"] == 1
    assert payload["model_authority"] == "none"


def test_mcp_rejects_arguments_and_explains_authority_boundary(tmp_path: Path) -> None:
    log_path = build_log().export(tmp_path, "markdown")
    invalid = dispatch(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "veyepr_execution_log_summary", "arguments": {"path": "/tmp/other"}},
        },
        log_path=log_path,
        policy_path=ROOT / "policy/mock-sentinel-policy.json",
    )
    assert invalid["error"]["code"] == -32602

    input_stream = StringIO(
        '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
        '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"veyepr_policy_boundary","arguments":{}}}\n'
    )
    output_stream = StringIO()
    serve(
        input_stream,
        output_stream,
        log_path=log_path,
        policy_path=ROOT / "policy/mock-sentinel-policy.json",
    )
    responses = [json.loads(line) for line in output_stream.getvalue().splitlines()]
    boundary = json.loads(responses[1]["result"]["content"][0]["text"])

    assert responses[0]["result"]["capabilities"] == {"tools": {}}
    assert boundary["model_authority"] == "none"
    assert "grant access" in boundary["model_cannot"]
    assert "change policy" in boundary["model_cannot"]

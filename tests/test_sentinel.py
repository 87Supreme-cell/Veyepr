import json
from pathlib import Path

import pytest

from ai_observability.sentinel import (
    AgentAction,
    SentinelPolicy,
    build_audit_package,
    evaluate_action,
    verify_audit_package,
)

ROOT = Path(__file__).parent.parent


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_normal_action_needs_no_review() -> None:
    action = AgentAction.from_record(load_json("fixtures/normal-agent-action.json"))
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))

    decision = evaluate_action(action, policy)

    assert decision.disposition == "no_review_required"
    assert decision.response_mode == "review_only"
    assert decision.findings == ()


def test_sensitive_export_is_routed_to_human_review() -> None:
    action = AgentAction.from_record(load_json("fixtures/suspicious-agent-action.json"))
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))

    decision = evaluate_action(action, policy)

    assert decision.disposition == "review_required"
    assert {finding.rule_id for finding in decision.findings} == {
        "oauth_scope_outside_allowlist",
        "sensitive_export_requires_review",
    }


def test_audit_package_is_metadata_only_and_tamper_evident() -> None:
    action = AgentAction.from_record(load_json("fixtures/suspicious-agent-action.json"))
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))
    package = build_audit_package(
        action=action,
        policy=policy,
        decision=evaluate_action(action, policy),
        review_case_id="case-test",
    )

    assert package["response_mode"] == "review_only"
    assert package["review_parties"] == ["security_reviewer", "session_subject"]
    assert "prompt" not in package["action_metadata"]
    assert verify_audit_package(package)

    package["decision"]["disposition"] = "no_review_required"
    assert not verify_audit_package(package)


def test_action_rejects_raw_content_or_unknown_fields() -> None:
    record = load_json("fixtures/normal-agent-action.json")
    record["raw_prompt"] = "sensitive content"

    with pytest.raises(ValueError, match="unexpected fields"):
        AgentAction.from_record(record)

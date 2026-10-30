"""Metadata-only, review-only policy evaluation for supplied agent actions.

This module is a local reference for a future runtime sentinel. It does not
intercept traffic, inspect OAuth tokens, execute tools, capture screens, or
enforce a block. Callers must provide a sanitized action record that contains
opaque references and content hashes instead of raw prompts or tool outputs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping

ActionType = Literal["oauth_scope_request", "data_export", "asset_mutation", "tool_read"]
Classification = Literal["public", "internal", "sensitive"]
DestinationClass = Literal["internal", "approved_external", "unknown_external"]
Severity = Literal["low", "medium", "high"]

ACTION_FIELDS = frozenset(
    {
        "event_type",
        "session_id",
        "action_id",
        "actor_ref",
        "timestamp",
        "tool_name",
        "action_type",
        "target_ref",
        "data_classification",
        "destination_class",
        "requested_scopes",
        "estimated_bytes",
        "prompt_hash",
        "tool_output_hash",
    }
)

HASH_PREFIX = "sha256:"


@dataclass(frozen=True, slots=True)
class AgentAction:
    """A sanitized tool-action record, never a raw prompt or raw tool result."""

    session_id: str
    action_id: str
    actor_ref: str
    timestamp: datetime
    tool_name: str
    action_type: ActionType
    target_ref: str
    data_classification: Classification
    destination_class: DestinationClass
    requested_scopes: tuple[str, ...]
    estimated_bytes: int
    prompt_hash: str
    tool_output_hash: str

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "AgentAction":
        missing = ACTION_FIELDS - set(record)
        unexpected = set(record) - ACTION_FIELDS
        if missing:
            raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
        if unexpected:
            raise ValueError(f"unexpected fields: {', '.join(sorted(unexpected))}")
        if record["event_type"] != "agent_tool_action":
            raise ValueError("event_type must be 'agent_tool_action'")

        bounded_strings = ("session_id", "action_id", "actor_ref", "tool_name")
        for field in bounded_strings:
            value = record[field]
            if not isinstance(value, str) or not value.strip() or len(value) > 128:
                raise ValueError(f"{field} must be a non-empty string of at most 128 characters")
        target_ref = record["target_ref"]
        if not isinstance(target_ref, str) or not target_ref.strip() or len(target_ref) > 256:
            raise ValueError("target_ref must be a non-empty string of at most 256 characters")

        action_type = record["action_type"]
        if action_type not in {"oauth_scope_request", "data_export", "asset_mutation", "tool_read"}:
            raise ValueError("action_type is not supported")
        data_classification = record["data_classification"]
        if data_classification not in {"public", "internal", "sensitive"}:
            raise ValueError("data_classification is not supported")
        destination_class = record["destination_class"]
        if destination_class not in {"internal", "approved_external", "unknown_external"}:
            raise ValueError("destination_class is not supported")

        scopes = record["requested_scopes"]
        if (
            not isinstance(scopes, list)
            or len(scopes) > 32
            or len(set(scopes)) != len(scopes)
            or any(not isinstance(scope, str) or not scope or len(scope) > 128 for scope in scopes)
        ):
            raise ValueError("requested_scopes must contain up to 32 unique bounded strings")
        estimated_bytes = record["estimated_bytes"]
        if isinstance(estimated_bytes, bool) or not isinstance(estimated_bytes, int) or estimated_bytes < 0:
            raise ValueError("estimated_bytes must be a non-negative integer")

        timestamp = record["timestamp"]
        if not isinstance(timestamp, str):
            raise TypeError("timestamp must be an RFC 3339 string")
        parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if parsed_timestamp.tzinfo is None:
            raise ValueError("timestamp must include a timezone")

        for field in ("prompt_hash", "tool_output_hash"):
            _validate_hash(field, record[field])

        return cls(
            session_id=record["session_id"].strip(),
            action_id=record["action_id"].strip(),
            actor_ref=record["actor_ref"].strip(),
            timestamp=parsed_timestamp.astimezone(timezone.utc),
            tool_name=record["tool_name"].strip(),
            action_type=action_type,
            target_ref=target_ref.strip(),
            data_classification=data_classification,
            destination_class=destination_class,
            requested_scopes=tuple(scopes),
            estimated_bytes=estimated_bytes,
            prompt_hash=record["prompt_hash"],
            tool_output_hash=record["tool_output_hash"],
        )

    def to_record(self) -> dict[str, object]:
        record = asdict(self)
        record["event_type"] = "agent_tool_action"
        record["timestamp"] = self.timestamp.isoformat()
        record["requested_scopes"] = list(self.requested_scopes)
        return {"event_type": record.pop("event_type"), **record}


@dataclass(frozen=True, slots=True)
class SentinelPolicy:
    """Policy inputs for review-only routing."""

    policy_id: str
    policy_version: str
    response_mode: Literal["review_only"]
    retention_mode: Literal["metadata_and_hashes_only"]
    approved_oauth_scopes: frozenset[str]
    approved_destination_classes: frozenset[str]
    sensitive_export_review_threshold_bytes: int
    review_sensitive_asset_mutation: bool

    @classmethod
    def from_record(cls, record: Mapping[str, Any]) -> "SentinelPolicy":
        expected = {
            "policy_id",
            "policy_version",
            "response_mode",
            "retention_mode",
            "approved_oauth_scopes",
            "approved_destination_classes",
            "sensitive_export_review_threshold_bytes",
            "review_sensitive_asset_mutation",
        }
        if set(record) != expected:
            raise ValueError("policy fields do not match the local policy contract")
        if record["response_mode"] != "review_only":
            raise ValueError("only review_only response mode is supported by this prototype")
        if record["retention_mode"] != "metadata_and_hashes_only":
            raise ValueError("only metadata_and_hashes_only retention is supported")
        for field in ("policy_id", "policy_version"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise ValueError(f"{field} must be a non-empty string")
        for field in ("approved_oauth_scopes", "approved_destination_classes"):
            values = record[field]
            if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
                raise ValueError(f"{field} must be a list of non-empty strings")
        threshold = record["sensitive_export_review_threshold_bytes"]
        if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
            raise ValueError("sensitive_export_review_threshold_bytes must be a non-negative integer")
        if not isinstance(record["review_sensitive_asset_mutation"], bool):
            raise TypeError("review_sensitive_asset_mutation must be a boolean")
        return cls(
            policy_id=record["policy_id"].strip(),
            policy_version=record["policy_version"].strip(),
            response_mode="review_only",
            retention_mode="metadata_and_hashes_only",
            approved_oauth_scopes=frozenset(record["approved_oauth_scopes"]),
            approved_destination_classes=frozenset(record["approved_destination_classes"]),
            sensitive_export_review_threshold_bytes=threshold,
            review_sensitive_asset_mutation=record["review_sensitive_asset_mutation"],
        )


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    rule_id: str
    severity: Severity
    explanation: str


@dataclass(frozen=True, slots=True)
class ReviewDecision:
    disposition: Literal["no_review_required", "review_required"]
    response_mode: Literal["review_only"]
    findings: tuple[ReviewFinding, ...]


def evaluate_action(action: AgentAction, policy: SentinelPolicy) -> ReviewDecision:
    """Evaluate sanitized metadata and require human review when a rule matches."""
    findings: list[ReviewFinding] = []
    unexpected_scopes = sorted(set(action.requested_scopes) - policy.approved_oauth_scopes)
    if unexpected_scopes:
        findings.append(
            ReviewFinding(
                "oauth_scope_outside_allowlist",
                "medium",
                "Requested scopes are outside the policy allowlist.",
            )
        )
    if action.action_type == "data_export" and action.data_classification == "sensitive":
        if (
            action.destination_class not in policy.approved_destination_classes
            or action.estimated_bytes >= policy.sensitive_export_review_threshold_bytes
        ):
            findings.append(
                ReviewFinding(
                    "sensitive_export_requires_review",
                    "high",
                    "Sensitive export metadata requires human review under this policy.",
                )
            )
    if (
        action.action_type == "asset_mutation"
        and action.data_classification == "sensitive"
        and policy.review_sensitive_asset_mutation
    ):
        findings.append(
            ReviewFinding(
                "sensitive_asset_mutation_requires_review",
                "medium",
                "Sensitive asset mutation metadata requires human review under this policy.",
            )
        )

    return ReviewDecision(
        disposition="review_required" if findings else "no_review_required",
        response_mode="review_only",
        findings=tuple(findings),
    )


def build_audit_package(
    *,
    action: AgentAction,
    policy: SentinelPolicy,
    decision: ReviewDecision,
    review_case_id: str,
) -> dict[str, object]:
    """Create a tamper-evident local package without raw prompts or outputs.

    A SHA-256 digest makes later modification detectable when the original
    package digest is retained independently. It is not immutable storage and
    it is not a digital signature.
    """
    if not review_case_id.strip():
        raise ValueError("review_case_id must be non-empty")
    package = {
        "package_version": "0.1.0",
        "review_case_id": review_case_id,
        "review_parties": ["security_reviewer", "session_subject"],
        "response_mode": "review_only",
        "retention_mode": "metadata_and_hashes_only",
        "action_metadata": action.to_record(),
        "content_hashes": {
            "prompt_hash": action.prompt_hash,
            "tool_output_hash": action.tool_output_hash,
        },
        "policy": {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
        },
        "decision": {
            "disposition": decision.disposition,
            "findings": [asdict(finding) for finding in decision.findings],
        },
        "limitations": [
            "The package contains no raw prompt or tool-output content.",
            "A review-required result is not a finding of misconduct or malicious intent.",
            "The local integrity digest is tamper-evident only when stored independently.",
        ],
    }
    digest = sha256(_canonical_json(package).encode("utf-8")).hexdigest()
    return {**package, "integrity": {"algorithm": "sha256", "payload_sha256": digest}}


def verify_audit_package(package: Mapping[str, Any]) -> bool:
    """Verify a local audit package's structural digest."""
    package_copy = dict(package)
    integrity = package_copy.pop("integrity", None)
    if not isinstance(integrity, Mapping) or integrity.get("algorithm") != "sha256":
        return False
    digest = integrity.get("payload_sha256")
    return isinstance(digest, str) and sha256(_canonical_json(package_copy).encode("utf-8")).hexdigest() == digest


def validate_agent_action_contract(contract: Mapping[str, Any]) -> None:
    """Verify the schema invariants that protect metadata-only evaluation.

    The runtime parser remains the executable validator. This check binds the
    mock-deployment preflight to the published JSON Schema so an edited schema
    cannot silently weaken the documented contract while retaining its title.
    """
    if contract.get("title") != "Veyepr sanitized agent action":
        raise ValueError("agent action contract title does not match the expected contract")
    if contract.get("type") != "object" or contract.get("additionalProperties") is not False:
        raise ValueError("agent action contract must reject unknown object fields")
    required = contract.get("required")
    if not isinstance(required, list) or set(required) != ACTION_FIELDS or len(required) != len(ACTION_FIELDS):
        raise ValueError("agent action contract required fields do not match the runtime contract")
    properties = contract.get("properties")
    if not isinstance(properties, Mapping) or set(properties) != ACTION_FIELDS:
        raise ValueError("agent action contract properties do not match the runtime contract")
    if properties["event_type"].get("const") != "agent_tool_action":
        raise ValueError("agent action contract event_type is not bound to agent_tool_action")
    if properties["action_type"].get("enum") != [
        "oauth_scope_request",
        "data_export",
        "asset_mutation",
        "tool_read",
    ]:
        raise ValueError("agent action contract action_type values do not match the runtime contract")
    expected_hash_pattern = r"^sha256:[a-f0-9]{64}$"
    for field in ("prompt_hash", "tool_output_hash"):
        if properties[field].get("pattern") != expected_hash_pattern:
            raise ValueError(f"agent action contract {field} must require a sha256 hash")


def load_json(path: Path) -> dict[str, Any]:
    """Read a JSON object with an explicit helpful error for non-object files."""
    with path.open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def _validate_hash(field: str, value: object) -> None:
    if not isinstance(value, str) or not value.startswith(HASH_PREFIX) or len(value) != len(HASH_PREFIX) + 64:
        raise ValueError(f"{field} must be a sha256-prefixed 64-character hexadecimal digest")
    if any(character not in "0123456789abcdef" for character in value[len(HASH_PREFIX) :]):
        raise ValueError(f"{field} must be a sha256-prefixed 64-character hexadecimal digest")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

"""Fixture-only failure and recovery drills for the local sentinel model."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
from typing import Any, Literal, Mapping

from .mock_deploy import write_json
from .sentinel import (
    AgentAction,
    ReviewFinding,
    SentinelPolicy,
    evaluate_action,
    load_json,
    validate_agent_action_contract,
)

Disposition = Literal["no_review_required", "review_required", "rejected"]


@dataclass(frozen=True, slots=True)
class DrillOutcome:
    scenario_id: str
    expected_disposition: Disposition
    actual_disposition: Disposition
    matched_expectation: bool
    findings: tuple[ReviewFinding, ...]
    evidence: dict[str, object]
    recovery: str


def evaluate_scenario(scenario: Mapping[str, Any], policy: SentinelPolicy) -> DrillOutcome:
    """Evaluate an inert scenario with no tool execution or network activity."""
    scenario_id = scenario.get("scenario_id")
    expected = scenario.get("expected_disposition")
    records = scenario.get("actions")
    if not isinstance(scenario_id, str) or not scenario_id:
        raise ValueError("scenario_id must be a non-empty string")
    if expected not in {"no_review_required", "review_required", "rejected"}:
        raise ValueError("expected_disposition is not supported")
    if not isinstance(records, list) or not records:
        raise ValueError("actions must be a non-empty list")

    actions: list[AgentAction] = []
    try:
        for record in records:
            if not isinstance(record, Mapping):
                raise ValueError("action record must be an object")
            actions.append(AgentAction.from_record(record))
    except (TypeError, ValueError):
        actual: Disposition = "rejected"
        return DrillOutcome(
            scenario_id=scenario_id,
            expected_disposition=expected,
            actual_disposition=actual,
            matched_expectation=actual == expected,
            findings=(
                ReviewFinding(
                    "contract_rejection",
                    "medium",
                    "The action was rejected before policy evaluation because it did not match the published contract.",
                ),
            ),
            evidence={
                "record_count": len(records),
                "raw_content_retained": False,
                "rejection_reason": "action did not match the published contract",
            },
            recovery="Correct the record against the published contract and submit it as a new action.",
        )

    findings: list[ReviewFinding] = []
    action_ids: set[str] = set()
    previous_timestamp: datetime | None = None
    for action in actions:
        if action.action_id in action_ids:
            findings.append(
                ReviewFinding(
                    "duplicate_action_id",
                    "medium",
                    "The session includes the same action identifier more than once.",
                )
            )
        action_ids.add(action.action_id)
        if previous_timestamp is not None and action.timestamp < previous_timestamp:
            findings.append(
                ReviewFinding(
                    "timestamp_regression",
                    "low",
                    "The supplied action timestamps are out of order.",
                )
            )
        previous_timestamp = action.timestamp
        findings.extend(evaluate_action(action, policy).findings)

    actual = "review_required" if findings else "no_review_required"
    evidence = {
        "record_count": len(actions),
        "session_refs": sorted({action.session_id for action in actions}),
        "action_ids": [action.action_id for action in actions],
        "content_hashes": [
            {"prompt_hash": action.prompt_hash, "tool_output_hash": action.tool_output_hash} for action in actions
        ],
        "raw_content_retained": False,
    }
    return DrillOutcome(
        scenario_id=scenario_id,
        expected_disposition=expected,
        actual_disposition=actual,
        matched_expectation=actual == expected,
        findings=tuple(findings),
        evidence=evidence,
        recovery=(
            "Preserve the drill evidence, correct ordering or identifiers in a new record sequence, "
            "then evaluate the new sequence independently."
            if findings
            else "No recovery action is required; the independent valid action remains eligible for normal review routing."
        ),
    )


def run_drills(fixture_path: Path, policy_path: Path, contract_path: Path) -> dict[str, object]:
    """Run all declared fixture drills and create a tamper-evident report."""
    fixture = load_json(fixture_path)
    if fixture.get("drill_suite_version") != "0.1.0":
        raise ValueError("unsupported drill suite version")
    scenarios = fixture.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("drill fixture must include scenarios")

    validate_agent_action_contract(load_json(contract_path))
    policy = SentinelPolicy.from_record(load_json(policy_path))
    outcomes = [evaluate_scenario(scenario, policy) for scenario in scenarios if isinstance(scenario, Mapping)]
    if len(outcomes) != len(scenarios):
        raise ValueError("each drill scenario must be an object")
    if not all(outcome.matched_expectation for outcome in outcomes):
        raise RuntimeError("one or more drill scenarios did not match their expected disposition")

    report_without_integrity = {
        "report_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "suite_version": fixture["drill_suite_version"],
        "policy": {"policy_id": policy.policy_id, "policy_version": policy.policy_version},
        "contract": {"path": str(contract_path), "contract_checked": True},
        "response_mode": "review_only",
        "network_or_tool_execution": False,
        "outcomes": [
            {
                **asdict(outcome),
                "findings": [asdict(finding) for finding in outcome.findings],
            }
            for outcome in outcomes
        ],
        "summary": {
            "scenario_count": len(outcomes),
            "expectations_matched": True,
            "rejected_count": sum(outcome.actual_disposition == "rejected" for outcome in outcomes),
            "review_required_count": sum(outcome.actual_disposition == "review_required" for outcome in outcomes),
            "no_review_required_count": sum(
                outcome.actual_disposition == "no_review_required" for outcome in outcomes
            ),
        },
        "limitations": [
            "The scenarios are local fixtures and do not test a live agent, network, OAuth flow, or data source.",
            "Review-required is a request for human context, not a finding of misconduct.",
            "The report is tamper-evident only when its digest is stored independently.",
        ],
        "runtime": {"python_version": platform.python_version()},
    }
    digest = sha256(_canonical_json(report_without_integrity).encode("utf-8")).hexdigest()
    return {
        **report_without_integrity,
        "integrity": {"algorithm": "sha256", "payload_sha256": digest},
    }


def verify_drill_report(report: Mapping[str, Any]) -> bool:
    """Verify a drill report's local structural digest."""
    copy = dict(report)
    integrity = copy.pop("integrity", None)
    return (
        isinstance(integrity, Mapping)
        and integrity.get("algorithm") == "sha256"
        and isinstance(integrity.get("payload_sha256"), str)
        and integrity["payload_sha256"] == sha256(_canonical_json(copy).encode("utf-8")).hexdigest()
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures/failure-drills.json"))
    parser.add_argument("--policy", type=Path, default=Path("policy/mock-sentinel-policy.json"))
    parser.add_argument("--contract", type=Path, default=Path("contracts/agent-action.schema.json"))
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = run_drills(args.fixtures, args.policy, args.contract)
    write_json(args.report, report)
    print(
        "Failure drills passed: "
        f"{report['summary']['scenario_count']} scenarios, "
        f"{report['summary']['review_required_count']} review-required, "
        f"{report['summary']['rejected_count']} rejected."
    )
    print(f"Drill report: {args.report}")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


if __name__ == "__main__":
    main()

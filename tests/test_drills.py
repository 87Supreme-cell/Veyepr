import json
from pathlib import Path

import pytest

from ai_observability.drills import evaluate_scenario, run_drills, verify_drill_report
from ai_observability.sentinel import SentinelPolicy

ROOT = Path(__file__).parent.parent


def load_json(relative_path: str) -> dict[str, object]:
    return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


def test_failure_drills_match_declared_outcomes() -> None:
    report = run_drills(
        ROOT / "fixtures/failure-drills.json",
        ROOT / "policy/mock-sentinel-policy.json",
        ROOT / "contracts/agent-action.schema.json",
    )

    assert report["summary"] == {
        "scenario_count": 5,
        "expectations_matched": True,
        "rejected_count": 1,
        "review_required_count": 3,
        "no_review_required_count": 1,
    }
    assert verify_drill_report(report)


def test_contract_rejection_preserves_no_raw_content() -> None:
    fixture = load_json("fixtures/failure-drills.json")
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))

    outcome = evaluate_scenario(fixture["scenarios"][0], policy)

    assert outcome.actual_disposition == "rejected"
    assert outcome.evidence["raw_content_retained"] is False
    assert outcome.evidence["rejection_reason"] == "action did not match the published contract"


def test_clean_recovery_remains_independent_after_prior_drills() -> None:
    fixture = load_json("fixtures/failure-drills.json")
    policy = SentinelPolicy.from_record(load_json("policy/mock-sentinel-policy.json"))

    outcome = evaluate_scenario(fixture["scenarios"][-1], policy)

    assert outcome.actual_disposition == "no_review_required"
    assert outcome.findings == ()


def test_failure_drills_reject_weakened_contract(tmp_path: Path) -> None:
    contract = load_json("contracts/agent-action.schema.json")
    contract["additionalProperties"] = True
    weakened_contract = tmp_path / "agent-action.schema.json"
    weakened_contract.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(ValueError, match="reject unknown object fields"):
        run_drills(
            ROOT / "fixtures/failure-drills.json",
            ROOT / "policy/mock-sentinel-policy.json",
            weakened_contract,
        )

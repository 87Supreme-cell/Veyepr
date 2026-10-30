"""Local mock-deployment preflight for the Veyepr review-only sentinel."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import platform
import sys
from typing import Any, Mapping

from .sentinel import (
    AgentAction,
    SentinelPolicy,
    build_audit_package,
    evaluate_action,
    load_json,
    validate_agent_action_contract,
    verify_audit_package,
)

CONFIG_FIELDS = frozenset(
    {
        "deployment_id",
        "deployment_version",
        "environment",
        "response_mode",
        "retention_mode",
        "agent_action_contract",
        "policy_file",
        "sample_action",
        "known_limitations",
    }
)


def run_preflight(config_path: Path, repository_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    """Validate mock-deployment inputs and produce a local evidence package.

    This command never deploys a service, reaches a network endpoint, or
    reads a credential. It is intended to show which local artifacts would
    participate in a review-only deployment.
    """
    config = load_json(config_path)
    if set(config) != CONFIG_FIELDS:
        raise ValueError("mock deployment configuration fields do not match the local contract")
    if config["environment"] != "mock_local":
        raise ValueError("only mock_local environment is supported")
    if config["response_mode"] != "review_only":
        raise ValueError("only review_only response mode is supported")
    if config["retention_mode"] != "metadata_and_hashes_only":
        raise ValueError("only metadata_and_hashes_only retention is supported")
    if not isinstance(config["known_limitations"], list) or not all(
        isinstance(limitation, str) and limitation for limitation in config["known_limitations"]
    ):
        raise ValueError("known_limitations must be a non-empty list of strings")

    contract_path = _repository_path(repository_root, config["agent_action_contract"])
    policy_path = _repository_path(repository_root, config["policy_file"])
    action_path = _repository_path(repository_root, config["sample_action"])
    for path in (contract_path, policy_path, action_path):
        if not path.is_file():
            raise FileNotFoundError(f"required mock deployment artifact is missing: {path}")

    contract = load_json(contract_path)
    validate_agent_action_contract(contract)
    policy = SentinelPolicy.from_record(load_json(policy_path))
    action = AgentAction.from_record(load_json(action_path))
    decision = evaluate_action(action, policy)
    package = build_audit_package(
        action=action,
        policy=policy,
        decision=decision,
        review_case_id=f"case-{action.session_id}-{action.action_id}",
    )
    if not verify_audit_package(package):
        raise RuntimeError("generated audit package did not verify")

    checks = [
        _check("configuration", config_path, "passed"),
        _check("agent action contract", contract_path, "passed"),
        _check("review-only policy", policy_path, "passed"),
        _check("sanitized sample action", action_path, "passed"),
        _check("generated audit package integrity", None, "passed"),
    ]
    report = {
        "report_version": "0.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "deployment": {
            "deployment_id": config["deployment_id"],
            "deployment_version": config["deployment_version"],
            "environment": config["environment"],
            "response_mode": config["response_mode"],
            "retention_mode": config["retention_mode"],
        },
        "checks": checks,
        "result": "passed",
        "review_outcome": {
            "disposition": decision.disposition,
            "finding_count": len(decision.findings),
            "enforcement_performed": False,
        },
        "known_limitations": config["known_limitations"],
        "runtime": {
            "implementation": "python-reference",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    return report, package


def write_json(path: Path, content: Mapping[str, Any]) -> None:
    """Write a JSON artifact, refusing to overwrite an existing report."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("deployment/mock-deploy.json"))
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--report", type=Path, required=True, help="New path for the preflight evidence report.")
    parser.add_argument("--audit-package", type=Path, required=True, help="New path for the review package.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.report == args.audit_package:
        raise ValueError("--report and --audit-package must be different paths")
    existing_outputs = [path for path in (args.report, args.audit_package) if path.exists()]
    if existing_outputs:
        rendered_paths = ", ".join(str(path) for path in existing_outputs)
        raise FileExistsError(f"refusing to overwrite existing artifact(s): {rendered_paths}")
    report, package = run_preflight(args.config, args.repository_root)
    write_json(args.report, report)
    write_json(args.audit_package, package)
    print(
        "Mock deployment preflight passed: "
        f"{report['review_outcome']['disposition']} with "
        f"{report['review_outcome']['finding_count']} finding(s)."
    )
    print(f"Evidence report: {args.report}")
    print(f"Review package: {args.audit_package}")


def _repository_path(repository_root: Path, raw_path: object) -> Path:
    if not isinstance(raw_path, str) or not raw_path:
        raise ValueError("artifact path must be a non-empty string")
    root = repository_root.resolve()
    candidate = (root / raw_path).resolve()
    if root not in candidate.parents and candidate != root:
        raise ValueError("artifact path must remain inside repository root")
    return candidate


def _check(name: str, path: Path | None, result: str) -> dict[str, object]:
    check: dict[str, object] = {"name": name, "result": result}
    if path is not None:
        check["path"] = str(path)
        check["sha256"] = sha256(path.read_bytes()).hexdigest()
    return check


if __name__ == "__main__":
    main()

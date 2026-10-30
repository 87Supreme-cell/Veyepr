"""Host-controlled execution logging for The Firm integration layer.

The adapter consumes sanitized NDJSON events emitted by an approved host or
client wrapper. It is intentionally not an LLM tool: the model cannot select
the policy, alter the host-owned export directory, grant permission, or erase
prior entries. The adapter only records review-only evidence.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Literal, Mapping, TextIO

from .sentinel import AgentAction, ReviewDecision, SentinelPolicy, load_json
from .sentinel import evaluate_action

ExportFormat = Literal["markdown", "text"]


@dataclass(frozen=True, slots=True)
class ExecutionEntry:
    """A normalized host-observed action and its review-only decision."""

    sequence: int
    observed_at: datetime
    action: AgentAction
    decision: ReviewDecision
    previous_digest: str | None
    entry_digest: str

    def to_record(self) -> dict[str, object]:
        return {
            "entry_version": "0.1.0",
            "source": "host_observed",
            "sequence": self.sequence,
            "observed_at": self.observed_at.isoformat(),
            "action": self.action.to_record(),
            "policy_decision": {
                "disposition": self.decision.disposition,
                "response_mode": self.decision.response_mode,
                "findings": [asdict(finding) for finding in self.decision.findings],
            },
            "previous_digest": self.previous_digest,
            "entry_digest": self.entry_digest,
        }


class FirmExecutionLog:
    """Append-only in-memory ledger for a host-owned execution session."""

    def __init__(self, policy: SentinelPolicy) -> None:
        self._policy = policy
        self._entries: list[ExecutionEntry] = []

    @property
    def entries(self) -> tuple[ExecutionEntry, ...]:
        return tuple(self._entries)

    @property
    def policy(self) -> SentinelPolicy:
        return self._policy

    def record_host_event(self, record: Mapping[str, Any]) -> ExecutionEntry:
        """Validate one host event and append its review-only evidence.

        ``AgentAction.from_record`` rejects raw content and unknown fields. The
        adapter adds the source marker itself, so callers cannot label a model
        declaration as host-observed evidence.
        """
        action = AgentAction.from_record(record)
        decision = evaluate_action(action, self._policy)
        previous_digest = self._entries[-1].entry_digest if self._entries else None
        payload = {
            "entry_version": "0.1.0",
            "source": "host_observed",
            "sequence": len(self._entries) + 1,
            "action": action.to_record(),
            "policy": {
                "policy_id": self._policy.policy_id,
                "policy_version": self._policy.policy_version,
                "response_mode": self._policy.response_mode,
            },
            "decision": {
                "disposition": decision.disposition,
                "response_mode": decision.response_mode,
                "findings": [asdict(finding) for finding in decision.findings],
            },
            "previous_digest": previous_digest,
        }
        entry = ExecutionEntry(
            sequence=payload["sequence"],
            observed_at=datetime.now(timezone.utc),
            action=action,
            decision=decision,
            previous_digest=previous_digest,
            entry_digest=_digest(payload),
        )
        self._entries.append(entry)
        return entry

    def verify_chain(self) -> bool:
        """Verify the in-memory digest chain before exporting it."""
        previous_digest: str | None = None
        for entry in self._entries:
            payload = {
                "entry_version": "0.1.0",
                "source": "host_observed",
                "sequence": entry.sequence,
                "action": entry.action.to_record(),
                "policy": {
                    "policy_id": self._policy.policy_id,
                    "policy_version": self._policy.policy_version,
                    "response_mode": self._policy.response_mode,
                },
                "decision": {
                    "disposition": entry.decision.disposition,
                    "response_mode": entry.decision.response_mode,
                    "findings": [asdict(finding) for finding in entry.decision.findings],
                },
                "previous_digest": previous_digest,
            }
            if entry.previous_digest != previous_digest or entry.entry_digest != _digest(payload):
                return False
            previous_digest = entry.entry_digest
        return True

    def export(self, export_directory: Path, export_format: ExportFormat) -> Path:
        """Write a new host-controlled Markdown or text export.

        The output name is fixed by the selected format. The model never
        supplies a filesystem path; a human or host process configures
        ``export_directory`` when it starts the adapter.
        """
        if export_format not in {"markdown", "text"}:
            raise ValueError("export_format must be markdown or text")
        if not self.verify_chain():
            raise RuntimeError("execution digest chain did not verify")
        filename = "firm-execution-log.md" if export_format == "markdown" else "firm-execution-log.txt"
        output_path = export_directory / filename
        if output_path.exists():
            raise FileExistsError(f"refusing to overwrite existing export: {output_path}")
        export_directory.mkdir(parents=True, exist_ok=True)
        renderer = _render_markdown if export_format == "markdown" else _render_text
        output_path.write_text(renderer(self), encoding="utf-8")
        return output_path


def read_host_events(input_path: Path, execution_log: FirmExecutionLog) -> None:
    """Read one sanitized action JSON object per non-empty NDJSON line."""
    with input_path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{input_path}:{line_number}: invalid JSON event") from error
            if not isinstance(record, Mapping):
                raise ValueError(f"{input_path}:{line_number}: event must be a JSON object")
            execution_log.record_host_event(record)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Host-emitted sanitized NDJSON action events.")
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("policy/mock-sentinel-policy.json"),
        help="Host-owned review-only policy file.",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        required=True,
        help="New or empty host-owned directory for the Markdown or text export.",
    )
    parser.add_argument("--format", choices=("markdown", "text"), default="markdown")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    policy = SentinelPolicy.from_record(load_json(args.policy))
    execution_log = FirmExecutionLog(policy)
    read_host_events(args.input, execution_log)
    output_path = execution_log.export(args.export_dir, args.format)
    review_count = sum(entry.decision.disposition == "review_required" for entry in execution_log.entries)
    print(
        f"Firm execution log exported: {len(execution_log.entries)} host-observed event(s), "
        f"{review_count} review-required."
    )
    print(f"Export: {output_path}")


def _render_markdown(execution_log: FirmExecutionLog) -> str:
    lines = [
        "# The Firm Execution Log",
        "",
        "## Authority boundary",
        "",
        "This export was produced by a host-controlled adapter. It records sanitized, host-observed metadata only.",
        "It does not grant access, block an action, make a personnel decision, or contain raw prompts or tool outputs.",
        "",
        "## Policy",
        "",
        f"- Policy: `{execution_log.policy.policy_id}` version `{execution_log.policy.policy_version}`",
        f"- Response mode: `{execution_log.policy.response_mode}`",
        f"- Retention mode: `{execution_log.policy.retention_mode}`",
        f"- Entry count: `{len(execution_log.entries)}`",
        "",
        "## Entries",
        "",
    ]
    for entry in execution_log.entries:
        findings = ", ".join(finding.rule_id for finding in entry.decision.findings) or "none"
        lines.extend(
            [
                f"### {entry.sequence}. `{entry.action.action_id}`",
                "",
                f"- Source: `host_observed`",
                f"- Session: `{entry.action.session_id}`",
                f"- Tool action: `{entry.action.tool_name}` / `{entry.action.action_type}`",
                f"- Classification and destination: `{entry.action.data_classification}` / `{entry.action.destination_class}`",
                f"- Estimated bytes: `{entry.action.estimated_bytes}`",
                f"- Decision: `{entry.decision.disposition}` (`{entry.decision.response_mode}`)",
                f"- Findings: `{findings}`",
                f"- Prompt hash: `{entry.action.prompt_hash}`",
                f"- Tool-output hash: `{entry.action.tool_output_hash}`",
                f"- Previous entry digest: `{entry.previous_digest or 'none'}`",
                f"- Entry digest: `{entry.entry_digest}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Interpretation",
            "",
            "A `review_required` entry requests human context. It is not a finding of malicious intent, misconduct, or policy violation.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_text(execution_log: FirmExecutionLog) -> str:
    lines = [
        "THE FIRM EXECUTION LOG",
        "authority_boundary=host_controlled_review_only",
        f"policy={execution_log.policy.policy_id}@{execution_log.policy.policy_version}",
        f"retention={execution_log.policy.retention_mode}",
        f"entry_count={len(execution_log.entries)}",
        "",
    ]
    for entry in execution_log.entries:
        findings = ",".join(finding.rule_id for finding in entry.decision.findings) or "none"
        lines.extend(
            [
                f"[{entry.sequence}] source=host_observed action_id={entry.action.action_id}",
                f"session_id={entry.action.session_id}",
                f"tool={entry.action.tool_name} action_type={entry.action.action_type}",
                f"classification={entry.action.data_classification} destination={entry.action.destination_class}",
                f"estimated_bytes={entry.action.estimated_bytes}",
                f"decision={entry.decision.disposition} response_mode={entry.decision.response_mode}",
                f"findings={findings}",
                f"prompt_hash={entry.action.prompt_hash}",
                f"tool_output_hash={entry.action.tool_output_hash}",
                f"previous_digest={entry.previous_digest or 'none'}",
                f"entry_digest={entry.entry_digest}",
                "",
            ]
        )
    lines.append("interpretation=review_required_is_not_a_finding_of_misconduct")
    return "\n".join(lines) + "\n"


def _digest(value: object) -> str:
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(rendered.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    main()

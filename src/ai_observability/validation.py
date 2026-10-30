"""Strict, dependency-free validation for the public telemetry wire contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .models import TrainingTelemetry

REQUIRED_FIELDS = frozenset(
    {
        "event_type",
        "run_id",
        "step",
        "loss",
        "gradient_norm",
        "batch_size",
        "timestamp",
    }
)


def training_event_from_record(record: Mapping[str, Any]) -> TrainingTelemetry:
    """Validate a JSON-like record and return a normalized telemetry event.

    The rules intentionally mirror ``contracts/training-event.schema.json``.
    Keeping this validation dependency-free makes the Python reference runtime
    straightforward to inspect, while the Rust verifier provides an
    independent implementation for deployment assurance.
    """
    field_names = set(record)
    missing = REQUIRED_FIELDS - field_names
    unexpected = field_names - REQUIRED_FIELDS
    if missing:
        raise ValueError(f"missing required fields: {', '.join(sorted(missing))}")
    if unexpected:
        raise ValueError(f"unexpected fields: {', '.join(sorted(unexpected))}")
    if record["event_type"] != "training_step":
        raise ValueError("event_type must be 'training_step'")

    run_id = record["run_id"]
    if not isinstance(run_id, str) or len(run_id.strip()) > 128:
        raise ValueError("run_id must be a non-empty string of at most 128 characters")

    timestamp = record["timestamp"]
    if not isinstance(timestamp, str):
        raise TypeError("timestamp must be an RFC 3339 string")
    parsed_timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if parsed_timestamp.tzinfo is None:
        raise ValueError("timestamp must include a timezone")

    event = TrainingTelemetry.from_training_step(
        run_id=run_id,
        step=record["step"],
        loss=record["loss"],
        gradient_norm=record["gradient_norm"],
        batch_size=record["batch_size"],
        timestamp=parsed_timestamp,
    )
    if event.gradient_norm < 0:
        raise ValueError("gradient_norm must be non-negative")
    return event

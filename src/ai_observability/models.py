"""Telemetry event types and conversion helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


def _as_number(value: Any, field_name: str) -> float:
    """Convert Python numbers or scalar tensor-like values to a float."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be numeric, not bool")

    item = getattr(value, "item", None)
    if callable(item):
        value = item()

    try:
        converted = float(value)
    except (TypeError, ValueError) as error:
        raise TypeError(f"{field_name} must be numeric") from error

    if converted != converted or converted in (float("inf"), float("-inf")):
        raise ValueError(f"{field_name} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class TrainingTelemetry:
    """A normalized record emitted once per training step.

    The conversion accepts scalar PyTorch tensors through their ``.item()``
    method without making PyTorch a required dependency.
    """

    run_id: str
    step: int
    loss: float
    gradient_norm: float
    batch_size: int
    timestamp: datetime

    @classmethod
    def from_training_step(
        cls,
        *,
        run_id: str,
        step: int,
        loss: Any,
        gradient_norm: Any,
        batch_size: Any,
        timestamp: datetime | None = None,
    ) -> "TrainingTelemetry":
        if not isinstance(run_id, str) or not run_id.strip() or len(run_id.strip()) > 128:
            raise ValueError("run_id must be a non-empty string of at most 128 characters")
        normalized_step = _as_number(step, "step")
        if not normalized_step.is_integer() or normalized_step < 0:
            raise ValueError("step must be a non-negative integer")

        normalized_batch_size = _as_number(batch_size, "batch_size")
        if not normalized_batch_size.is_integer() or normalized_batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")

        event_time = timestamp or datetime.now(timezone.utc)
        if event_time.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")

        normalized_gradient_norm = _as_number(gradient_norm, "gradient_norm")
        if normalized_gradient_norm < 0:
            raise ValueError("gradient_norm must be non-negative")

        return cls(
            run_id=run_id.strip(),
            step=int(normalized_step),
            loss=_as_number(loss, "loss"),
            gradient_norm=normalized_gradient_norm,
            batch_size=int(normalized_batch_size),
            timestamp=event_time.astimezone(timezone.utc),
        )

    def to_record(self) -> dict[str, object]:
        """Return a JSON-like structured record suitable for a log pipeline."""
        return {
            "event_type": "training_step",
            "run_id": self.run_id,
            "step": self.step,
            "loss": self.loss,
            "gradient_norm": self.gradient_norm,
            "batch_size": self.batch_size,
            "timestamp": self.timestamp.isoformat(),
        }

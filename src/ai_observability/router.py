"""An explicit local equivalent of a capture, transform, and route pipeline."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal

from prometheus_client import CollectorRegistry, Counter, Gauge, generate_latest

from .models import TrainingTelemetry
from .validation import training_event_from_record

RouteName = Literal["prometheus", "dropped"]


@dataclass(frozen=True, slots=True)
class CapturedEvent:
    """A normalized event plus local-pipeline metadata."""

    event_type: str
    run_id: str
    step: int
    loss: float
    gradient_norm: float
    batch_size: int
    timestamp: str
    captured_at: str
    pipeline: str


class EventCapture:
    """Thread-safe bounded capture buffer, analogous to inspecting Stream input."""

    def __init__(self, max_events: int = 1_000) -> None:
        if max_events < 1:
            raise ValueError("max_events must be positive")
        self._events: deque[CapturedEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def append(self, event: CapturedEvent) -> None:
        with self._lock:
            self._events.append(event)

    def recent(self, limit: int = 20) -> list[CapturedEvent]:
        if limit < 1:
            raise ValueError("limit must be positive")
        with self._lock:
            return list(self._events)[-limit:]


class PrometheusTrainingMetrics:
    """Prometheus sink for the normalized training telemetry."""

    def __init__(self, registry: CollectorRegistry | None = None) -> None:
        self.registry = registry or CollectorRegistry(auto_describe=True)
        labels = ("run_id",)
        self.loss = Gauge(
            "ai_training_loss",
            "Latest training loss by run.",
            labels,
            registry=self.registry,
        )
        self.gradient_norm = Gauge(
            "ai_training_gradient_norm",
            "Latest gradient L2 norm by run.",
            labels,
            registry=self.registry,
        )
        self.batch_size = Gauge(
            "ai_training_batch_size",
            "Latest training batch size by run.",
            labels,
            registry=self.registry,
        )
        self.current_step = Gauge(
            "ai_training_current_step",
            "Latest completed training step by run.",
            labels,
            registry=self.registry,
        )
        self.events = Counter(
            "ai_telemetry_events",
            "Training telemetry events processed by local route.",
            ("route",),
            registry=self.registry,
        )
        self.validation_events = Counter(
            "ai_telemetry_validation_events",
            "Telemetry records accepted or rejected by the contract validator.",
            ("outcome",),
            registry=self.registry,
        )

    def observe(self, event: CapturedEvent) -> None:
        labels = {"run_id": event.run_id}
        self.loss.labels(**labels).set(event.loss)
        self.gradient_norm.labels(**labels).set(event.gradient_norm)
        self.batch_size.labels(**labels).set(event.batch_size)
        self.current_step.labels(**labels).set(event.step)
        self.events.labels(route="prometheus").inc()

    def record_drop(self) -> None:
        self.events.labels(route="dropped").inc()

    def record_validation(self, outcome: Literal["accepted", "rejected"]) -> None:
        self.validation_events.labels(outcome=outcome).inc()

    def render_latest(self) -> bytes:
        return generate_latest(self.registry)


class LocalStreamPipeline:
    """Capture, transform, and route training telemetry to Prometheus.

    This deliberately mirrors the conceptual stages of a Cribl Stream route:
    capture raw events, normalize/enrich them, select a route, then deliver
    to the destination. It is local-only and does not use a Cribl SDK.
    """

    def __init__(
        self,
        *,
        capture: EventCapture | None = None,
        metrics: PrometheusTrainingMetrics | None = None,
    ) -> None:
        self.capture = capture or EventCapture()
        self.metrics = metrics or PrometheusTrainingMetrics()

    def process(self, telemetry: TrainingTelemetry | dict[str, Any]) -> RouteName:
        try:
            event = self._transform(telemetry)
        except (TypeError, ValueError):
            self.metrics.record_validation("rejected")
            raise
        self.capture.append(event)

        if event.event_type == "training_step":
            self.metrics.observe(event)
            self.metrics.record_validation("accepted")
            return "prometheus"

        self.metrics.record_drop()
        self.metrics.record_validation("rejected")
        return "dropped"

    @staticmethod
    def _transform(telemetry: TrainingTelemetry | dict[str, Any]) -> CapturedEvent:
        if isinstance(telemetry, TrainingTelemetry):
            record = telemetry.to_record()
        elif isinstance(telemetry, dict):
            if telemetry.get("event_type") == "training_step":
                record = training_event_from_record(telemetry).to_record()
            else:
                record = telemetry
        else:
            raise TypeError("telemetry must be TrainingTelemetry or a dictionary")

        event_type = record.get("event_type")
        if event_type != "training_step":
            return CapturedEvent(
                event_type=str(event_type),
                run_id="unknown",
                step=0,
                loss=0.0,
                gradient_norm=0.0,
                batch_size=0,
                timestamp=datetime.now(timezone.utc).isoformat(),
                captured_at=datetime.now(timezone.utc).isoformat(),
                pipeline="local-cribl-equivalent",
            )

        normalized = TrainingTelemetry.from_training_step(
            run_id=record.get("run_id", ""),
            step=record.get("step", 0),
            loss=record.get("loss"),
            gradient_norm=record.get("gradient_norm"),
            batch_size=record.get("batch_size"),
            timestamp=_parse_timestamp(record.get("timestamp")),
        )
        record = normalized.to_record()
        return CapturedEvent(
            **record,
            captured_at=datetime.now(timezone.utc).isoformat(),
            pipeline="local-cribl-equivalent",
        )

    def recent_records(self, limit: int = 20) -> list[dict[str, object]]:
        return [asdict(event) for event in self.capture.recent(limit)]


def _parse_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("timestamp must be an ISO 8601 string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return parsed

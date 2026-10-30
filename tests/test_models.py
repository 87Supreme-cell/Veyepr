from datetime import datetime, timezone

import pytest

from ai_observability.models import TrainingTelemetry


class ScalarLike:
    def __init__(self, value: float) -> None:
        self.value = value

    def item(self) -> float:
        return self.value


def test_training_event_converts_scalar_tensor_like_values() -> None:
    event = TrainingTelemetry.from_training_step(
        run_id=" run-42 ",
        step=3,
        loss=ScalarLike(0.125),
        gradient_norm=ScalarLike(1.75),
        batch_size=ScalarLike(32),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )

    assert event.run_id == "run-42"
    assert event.loss == 0.125
    assert event.gradient_norm == 1.75
    assert event.batch_size == 32
    assert event.to_record()["event_type"] == "training_step"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("batch_size", 0),
        ("batch_size", 4.5),
        ("batch_size", True),
        ("step", 1.5),
        ("gradient_norm", -0.1),
    ],
)
def test_training_event_rejects_invalid_contract_values(field: str, value: object) -> None:
    arguments: dict[str, object] = {
        "run_id": "run",
        "step": 1,
        "loss": 1.0,
        "gradient_norm": 1.0,
        "batch_size": 32,
    }
    arguments[field] = value
    with pytest.raises((TypeError, ValueError)):
        TrainingTelemetry.from_training_step(**arguments)

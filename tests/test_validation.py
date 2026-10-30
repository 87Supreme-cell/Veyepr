import json
from pathlib import Path

import pytest
from prometheus_client import CollectorRegistry

from ai_observability.router import LocalStreamPipeline, PrometheusTrainingMetrics
from ai_observability.validation import training_event_from_record

FIXTURES = Path(__file__).parent.parent / "fixtures"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_contract_fixture_is_accepted_by_python_validator() -> None:
    event = training_event_from_record(load_fixture("valid-training-event.json"))

    assert event.run_id == "verification-run"
    assert event.step == 42


def test_invalid_contract_fixture_is_rejected() -> None:
    with pytest.raises(ValueError):
        training_event_from_record(load_fixture("invalid-training-event.json"))


def test_router_reports_contract_validation_outcomes() -> None:
    metrics = PrometheusTrainingMetrics(registry=CollectorRegistry())
    pipeline = LocalStreamPipeline(metrics=metrics)

    assert pipeline.process(load_fixture("valid-training-event.json")) == "prometheus"
    with pytest.raises(ValueError):
        pipeline.process(load_fixture("invalid-training-event.json"))

    exposition = metrics.render_latest().decode("utf-8")
    assert 'ai_telemetry_validation_events_total{outcome="accepted"} 1.0' in exposition
    assert 'ai_telemetry_validation_events_total{outcome="rejected"} 1.0' in exposition


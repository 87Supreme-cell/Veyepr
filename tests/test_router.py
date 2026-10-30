from prometheus_client import CollectorRegistry

from ai_observability.models import TrainingTelemetry
from ai_observability.router import LocalStreamPipeline, PrometheusTrainingMetrics


def test_pipeline_captures_transforms_routes_and_exposes_metrics() -> None:
    metrics = PrometheusTrainingMetrics(registry=CollectorRegistry())
    pipeline = LocalStreamPipeline(metrics=metrics)
    event = TrainingTelemetry.from_training_step(
        run_id="experiment-a",
        step=9,
        loss=0.42,
        gradient_norm=1.2,
        batch_size=16,
    )

    assert pipeline.process(event) == "prometheus"

    captured = pipeline.recent_records()
    assert len(captured) == 1
    assert captured[0]["pipeline"] == "local-cribl-equivalent"
    assert captured[0]["step"] == 9

    exposition = metrics.render_latest().decode("utf-8")
    assert 'ai_training_loss{run_id="experiment-a"} 0.42' in exposition
    assert 'ai_training_gradient_norm{run_id="experiment-a"} 1.2' in exposition
    assert 'ai_training_batch_size{run_id="experiment-a"} 16.0' in exposition
    assert 'ai_training_current_step{run_id="experiment-a"} 9.0' in exposition
    assert 'ai_telemetry_events_total{route="prometheus"} 1.0' in exposition


def test_pipeline_counts_unroutable_event_as_dropped() -> None:
    metrics = PrometheusTrainingMetrics(registry=CollectorRegistry())
    pipeline = LocalStreamPipeline(metrics=metrics)

    assert pipeline.process({"event_type": "unknown"}) == "dropped"

    exposition = metrics.render_latest().decode("utf-8")
    assert 'ai_telemetry_events_total{route="dropped"} 1.0' in exposition


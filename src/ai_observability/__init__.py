"""Local AI observability pipeline demo."""

from .models import TrainingTelemetry

__all__ = ["LocalStreamPipeline", "PrometheusTrainingMetrics", "TrainingTelemetry"]


def __getattr__(name: str) -> object:
    """Load Prometheus-backed components only when a caller requests them."""
    if name in {"LocalStreamPipeline", "PrometheusTrainingMetrics"}:
        from .router import LocalStreamPipeline, PrometheusTrainingMetrics

        return {
            "LocalStreamPipeline": LocalStreamPipeline,
            "PrometheusTrainingMetrics": PrometheusTrainingMetrics,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Training telemetry producers with optional real PyTorch execution."""

from __future__ import annotations

import math
import random
from collections.abc import Iterator

from .models import TrainingTelemetry


def simulated_training_events(
    *,
    run_id: str,
    batch_size: int,
    seed: int = 7,
) -> Iterator[TrainingTelemetry]:
    """Emit deterministic, plausibly shaped training metrics indefinitely."""
    random_source = random.Random(seed)
    step = 0
    while True:
        step += 1
        trend = 1.8 * math.exp(-step / 80)
        noise = random_source.uniform(-0.035, 0.035)
        loss = max(0.02, trend + noise)
        gradient_norm = max(0.01, 2.4 * math.exp(-step / 110) + random_source.uniform(-0.08, 0.08))
        yield TrainingTelemetry.from_training_step(
            run_id=run_id,
            step=step,
            loss=loss,
            gradient_norm=gradient_norm,
            batch_size=batch_size,
        )


def torch_training_events(*, run_id: str, batch_size: int, seed: int = 7) -> Iterator[TrainingTelemetry]:
    """Run a tiny PyTorch regression loop, imported only when explicitly selected."""
    try:
        import torch
    except ImportError as error:
        raise RuntimeError(
            "PyTorch is not installed. Use --backend simulated or install with `pip install -e '.[torch]'`."
        ) from error

    torch.manual_seed(seed)
    model = torch.nn.Linear(4, 1)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.05)
    step = 0
    while True:
        step += 1
        inputs = torch.randn(batch_size, 4)
        targets = inputs.sum(dim=1, keepdim=True) * 0.5
        optimizer.zero_grad()
        loss = torch.nn.functional.mse_loss(model(inputs), targets)
        loss.backward()
        gradient_norm = torch.sqrt(
            sum(parameter.grad.detach().pow(2).sum() for parameter in model.parameters() if parameter.grad is not None)
        )
        optimizer.step()
        yield TrainingTelemetry.from_training_step(
            run_id=run_id,
            step=step,
            loss=loss,
            gradient_norm=gradient_norm,
            batch_size=batch_size,
        )


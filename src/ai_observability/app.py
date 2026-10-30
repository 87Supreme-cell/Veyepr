"""Run the local AI telemetry pipeline and expose Prometheus metrics."""

from __future__ import annotations

import argparse
import json
import logging
import signal
import time
from collections.abc import Iterator
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from threading import Event, Thread
from typing import cast
from urllib.parse import urlparse

from .models import TrainingTelemetry
from .router import LocalStreamPipeline
from .simulator import simulated_training_events, torch_training_events

LOGGER = logging.getLogger(__name__)


class PipelineRequestHandler(BaseHTTPRequestHandler):
    pipeline: LocalStreamPipeline

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/metrics":
            body = self.pipeline.metrics.render_latest()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path == "/healthz":
            self._send_json(HTTPStatus.OK, {"status": "ok"})
            return
        if path == "/events":
            self._send_json(HTTPStatus.OK, self.pipeline.recent_records())
            return
        static_files = {
            "/": ("index.html", "text/html; charset=utf-8"),
            "/triolingo": ("triolingo.html", "text/html; charset=utf-8"),
            "/assets/styles.css": ("styles.css", "text/css; charset=utf-8"),
            "/assets/app.js": ("app.js", "application/javascript; charset=utf-8"),
            "/assets/vioer.svg": ("vioer.svg", "image/svg+xml"),
        }
        asset = static_files.get(path)
        if asset:
            self._send_static(*asset)
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not found"})

    def log_message(self, format: str, *args: object) -> None:
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _send_json(self, status: HTTPStatus, body: object) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_static(self, filename: str, content_type: str) -> None:
        body = files("ai_observability").joinpath("static", filename).read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(
    *,
    pipeline: LocalStreamPipeline,
    events: Iterator[TrainingTelemetry],
    interval_seconds: float,
    port: int,
) -> None:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    stop_event = Event()
    handler = type("ConfiguredPipelineRequestHandler", (PipelineRequestHandler,), {"pipeline": pipeline})
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    server_thread = Thread(target=server.serve_forever, name="metrics-server", daemon=True)
    server_thread.start()
    LOGGER.info("Metrics endpoint available at http://localhost:%d/metrics", port)

    def stop_handler(signum: int, _frame: object) -> None:
        LOGGER.info("Received signal %s; shutting down.", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    try:
        while not stop_event.is_set():
            event = next(events)
            route = pipeline.process(event)
            LOGGER.info(
                "captured run_id=%s step=%d loss=%.5f gradient_norm=%.5f batch_size=%d route=%s",
                event.run_id,
                event.step,
                event.loss,
                event.gradient_norm,
                event.batch_size,
                route,
            )
            stop_event.wait(interval_seconds)
    finally:
        server.shutdown()
        server.server_close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("simulated", "torch"), default="simulated")
    parser.add_argument("--run-id", default="demo-run")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--log-level", default="INFO")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    logging.basicConfig(level=args.log_level.upper(), format="%(asctime)s %(levelname)s %(message)s")
    pipeline = LocalStreamPipeline()
    if args.backend == "torch":
        events = torch_training_events(run_id=args.run_id, batch_size=args.batch_size)
    else:
        events = simulated_training_events(run_id=args.run_id, batch_size=args.batch_size)
    run(
        pipeline=pipeline,
        events=cast(Iterator[TrainingTelemetry], events),
        interval_seconds=args.interval_seconds,
        port=args.port,
    )


if __name__ == "__main__":
    main()

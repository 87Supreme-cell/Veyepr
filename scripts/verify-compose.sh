#!/usr/bin/env sh
set -eu

cleanup() {
  docker compose down --volumes --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT INT TERM

export TELEMETRY_PORT=18000
export PROMETHEUS_PORT=19090
export GRAFANA_PORT=13000

docker compose up --build --detach

attempt=0
until curl --fail --silent "http://127.0.0.1:${TELEMETRY_PORT}/healthz" >/dev/null; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Veyepr did not pass its health check within 60 seconds." >&2
    exit 1
  fi
  sleep 2
done

curl --fail --silent "http://127.0.0.1:${TELEMETRY_PORT}/metrics" | grep -q '^ai_training_loss'
curl --fail --silent "http://127.0.0.1:${TELEMETRY_PORT}/metrics" | grep -q '^ai_telemetry_validation_events_total'
curl --fail --silent "http://127.0.0.1:${TELEMETRY_PORT}/events" | grep -q '"pipeline": "local-cribl-equivalent"'

attempt=0
until curl --fail --silent "http://127.0.0.1:${PROMETHEUS_PORT}/api/v1/targets" | grep -q '"health":"up"'; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo "Prometheus did not report the telemetry target as healthy within 60 seconds." >&2
    exit 1
  fi
  sleep 2
done

echo "Verification passed: app health, contract metrics, event capture, and Prometheus scrape target are healthy."

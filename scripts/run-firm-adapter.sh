#!/usr/bin/env sh
set -eu

output_dir="${1:-artifacts/firm-demo}"
format="${2:-markdown}"

if [ -e "$output_dir" ]; then
  echo "Refusing to overwrite existing export directory: $output_dir" >&2
  exit 1
fi

PYTHONPATH=src python3 -m ai_observability.firm \
  --input fixtures/firm-host-events.ndjson \
  --policy policy/mock-sentinel-policy.json \
  --export-dir "$output_dir" \
  --format "$format"

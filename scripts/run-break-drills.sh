#!/usr/bin/env sh
set -eu

output_dir="${1:-artifacts/break-b4-buying}"

if [ -e "$output_dir" ]; then
  echo "Refusing to overwrite existing evidence directory: $output_dir" >&2
  exit 1
fi

PYTHONPATH=src python3 -m ai_observability.drills \
  --fixtures fixtures/failure-drills.json \
  --policy policy/mock-sentinel-policy.json \
  --contract contracts/agent-action.schema.json \
  --report "$output_dir/drill-report.json"

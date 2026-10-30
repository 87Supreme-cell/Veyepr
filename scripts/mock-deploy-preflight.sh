#!/usr/bin/env sh
set -eu

output_dir="${1:-artifacts/mock-deploy}"

if [ -e "$output_dir" ]; then
  echo "Refusing to overwrite existing evidence directory: $output_dir" >&2
  exit 1
fi

PYTHONPATH=src python3 -m ai_observability.mock_deploy \
  --config deployment/mock-deploy.json \
  --repository-root . \
  --report "$output_dir/preflight-report.json" \
  --audit-package "$output_dir/review-package.json"
